import copy
import importlib
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import g_animation
import g_animation_authoring as authoring
import g_editor
import g_main
import g_render_order


class AnimationAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "animation_data.py"
        self.path.write_bytes(authoring.data_path().read_bytes())
        self.draft = authoring.new_draft(self.path)
        self.live = copy.deepcopy({name: getattr(authoring.data, name) for name in authoring.NAMES})
        self.addCleanup(lambda: authoring.data.__dict__.update(self.live))

    def edit(self, value=-45, linked=False):
        authoring.edit_pose(self.draft, "walk", 0, "near_upper_leg_degrees", value, linked)

    def test_save_roundtrip_and_dirty_history(self):
        self.edit()
        self.assertTrue(authoring.dirty(self.draft))
        review = authoring.prepare_save(self.draft)
        self.assertTrue(any("-45" in line for line in review["diff"]))
        authoring.save(self.draft, self.path)
        self.assertEqual(authoring.parse_source(self.path.read_text()), self.draft["document"])
        self.assertFalse(authoring.dirty(self.draft))
        authoring.history(self.draft)
        self.assertTrue(authoring.dirty(self.draft))
        authoring.history(self.draft, redo=True)
        self.assertFalse(authoring.dirty(self.draft))
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_invalid_values_do_not_modify_draft_or_history(self):
        for value in (math.nan, math.inf, -181, True, "20"):
            with self.assertRaises(ValueError):
                self.edit(value)
        self.assertFalse(authoring.dirty(self.draft))
        self.assertEqual(self.draft["undo"], [])

    def test_link_edits_opposite_limb_half_cycle_later(self):
        self.edit(linked=True)
        poses = self.draft["document"]["REDHEAD_CUTOUT_GAIT_PROFILES"]["walk"]
        self.assertEqual(poses[2]["far_upper_leg_degrees"], -45)
        self.assertNotEqual(poses[0]["far_upper_leg_degrees"], -45)
        authoring.history(self.draft)
        self.assertFalse(authoring.dirty(self.draft))

    def test_copy_paste_reset_and_branching_undo(self):
        self.edit()
        authoring.copy_pose(self.draft, "walk", 0)
        authoring.paste_pose(self.draft, "run", 3)
        self.assertEqual(self.draft["document"]["REDHEAD_CUTOUT_GAIT_PROFILES"]["run"][3],
                         self.draft["clipboard"])
        authoring.reset_pose(self.draft, "run", 3)
        self.assertEqual(self.draft["document"]["REDHEAD_CUTOUT_GAIT_PROFILES"]["run"][3],
                         self.draft["baseline"]["REDHEAD_CUTOUT_GAIT_PROFILES"]["run"][3])
        authoring.history(self.draft)
        self.edit(-30)
        self.assertFalse(self.draft["redo"])

    def test_external_change_and_stale_review_block_save(self):
        self.edit()
        authoring.prepare_save(self.draft)
        self.edit(-30)
        with self.assertRaisesRegex(ValueError, "Review"):
            authoring.save(self.draft, self.path)
        authoring.prepare_save(self.draft)
        self.path.write_text(self.path.read_text() + "\n# external edit\n")
        external = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "externally"):
            authoring.save(self.draft, self.path)
        self.assertEqual(self.path.read_bytes(), external)
        self.assertTrue(authoring.dirty(self.draft))

    def test_failed_atomic_replace_retains_file_and_draft(self):
        original = self.path.read_bytes()
        self.edit()
        authoring.prepare_save(self.draft)
        with mock.patch.object(authoring.os, "replace", side_effect=OSError("busy")):
            with self.assertRaises(OSError):
                authoring.save(self.draft, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.assertTrue(authoring.dirty(self.draft))

    def test_invalid_reload_keeps_last_working_module(self):
        for source in ("REDHEAD_CUTOUT_TEXTURES = {", "raise RuntimeError('executed')",
                       self.path.read_text().replace("-26.0", "-9999.0")):
            self.path.write_text(source)
            with self.assertRaises((ValueError, SyntaxError)):
                authoring.reload_data(self.path)
            self.assertEqual(authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES,
                             self.live["REDHEAD_CUTOUT_GAIT_PROFILES"])

    def test_reload_reaches_renderer_without_stale_aliases(self):
        self.edit()
        authoring.prepare_save(self.draft)
        authoring.save(self.draft, self.path)
        authoring.reload_data(self.path)
        self.assertIs(g_render_order.REDHEAD_CUTOUT_GAIT_PROFILES,
                      authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES)
        parts = g_render_order.build_redhead_cutout_rig_parts({
            "animation_direction": "right", "procedural_gait": {"blend": 1, "phase": 0}})
        near = next(p for p in parts if p.get("rig_joint") == "upper_leg" and p["rig_side"] == "near")
        self.assertEqual(near["rotation"], -45)

    def test_upgrade_reload_removes_pre_extraction_constant_aliases(self):
        g_render_order.REDHEAD_CUTOUT_GAIT_PROFILES = {"stale": True}
        importlib.reload(g_render_order)
        self.assertIs(g_render_order.REDHEAD_CUTOUT_GAIT_PROFILES,
                      authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES)

    def test_catalog_previews_work_with_no_level_entities(self):
        state = g_editor.make_editor_state()
        for source in ("Redhead preview", "Player preview"):
            state["animation_debug"].update(preview_source=source, target_key=None)
            preview = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0.25)
            self.assertEqual(preview["collection"], "__animation_preview__")
            self.assertEqual(preview["id"], source)
            self.assertAlmostEqual(preview["phase"], math.pi / 2)
            specimen = g_editor.get_selected_animation_entity({}, None, state)
            specimen.update(preview["fields"])
            build = (g_render_order.build_player_cutout_rig_parts if source == "Player preview"
                     else g_render_order.build_redhead_cutout_rig_parts)
            self.assertTrue(build(specimen))
            self.assertIsNone(state["selected_id"])

    def test_catalog_draft_does_not_override_previous_level_selection(self):
        self.edit()
        state = g_editor.make_editor_state()
        entity = {"id": 7, "type": "red head"}
        state.update(selected_kind="animation_entity", selected_collection="brains", selected_id=7,
                     redhead_animation_draft=self.draft)
        state["animation_debug"]["preview_source"] = "Redhead preview"
        preview = g_editor.update_animation_debug_preview(state, "animation", {"brains": {7: entity}}, None, 0)
        self.assertIs(preview["fields"]["animation_profile_override"], self.draft["document"])
        unchanged = g_render_order.entity_with_animation_debug_override(
            {"animation_debug_render_override": preview}, "brains", 7, entity)
        self.assertEqual(unchanged, entity)
        state["animation_debug"]["preview_source"] = "Level selection"
        self.assertIs(g_editor.get_selected_animation_entity({"brains": {7: entity}}, None, state), entity)

    def test_screen_preview_scales_without_mutating_pose(self):
        import g_graphics
        parts = g_animation.build_redhead_cutout_rig_parts({"animation_direction": "right"})
        original = copy.deepcopy(parts)
        with mock.patch.object(g_graphics, "_draw_cutout_rig", return_value=True) as draw:
            self.assertTrue(g_graphics.draw_screen_cutout_preview(parts, {"x": 100, "y": 120}, 4, {}))
        item, camera, _ = draw.call_args.args
        self.assertEqual((camera.x, camera.y), (0, 0))
        self.assertEqual(item["dest_rect"], {"x": 100, "y": 120})
        self.assertEqual(item["draw_data"]["cutout_rig_parts"][0]["pivot_local"]["x"],
                         parts[0]["pivot_local"]["x"] * 4)
        self.assertEqual(parts, original)

    def test_clicking_level_entity_leaves_catalog_preview(self):
        state = g_editor.make_editor_state()
        state["animation_debug"]["preview_source"] = "Redhead preview"
        entity = {"id": 7, "type": "red head"}
        with mock.patch.object(g_editor, "gameplay_entity_selection_bounds",
                               return_value={"x": 0, "y": 0, "width": 10, "height": 10}):
            selected = g_editor.select_animation_entity_at(
                {"brains": {7: entity}}, None, state, {"x": 5, "y": 5}, {})
        self.assertEqual(selected, ("brains", 7))
        self.assertEqual(state["animation_debug"]["preview_source"], "Level selection")
        self.assertIs(g_editor.get_selected_animation_entity({"brains": {7: entity}}, None, state), entity)

    def test_component_highlight_only_tints_selected_texture_instance(self):
        for facing in ("right", "left", "up", "down"):
            entity = {"animation_direction": facing}
            normal = g_animation.build_redhead_cutout_rig_parts(entity)
            original = copy.deepcopy(normal)
            for field, joints in (("far_knee_bend_degrees", {"lower_leg"}),
                                  ("far_front_leg_y_pixels", {"upper_leg", "lower_leg"})):
                highlighted = g_animation.highlight_component_parts(normal, {"field": field, "amount": 1})
                for before, after in zip(normal, highlighted):
                    selected = before.get("rig_side") == "far" and before.get("rig_joint") in joints
                    self.assertEqual(after["tint"] != before["tint"], selected)
                    self.assertEqual(after["pivot_local"], before["pivot_local"])
                self.assertEqual(g_animation.highlight_component_parts(normal, {"field": field, "amount": 0}), normal)
            self.assertEqual(normal, original)

    def test_component_flash_animates_while_pose_is_frozen_and_is_preview_only(self):
        state = g_editor.make_editor_state()
        state["animation_debug"].update(preview_source="Redhead preview", authoring=True,
                                        highlight_component=True, edit_field="near_upper_arm_degrees",
                                        playback="keyframe")
        first = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0)
        later = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0.25)
        self.assertEqual(first["phase"], later["phase"])
        self.assertNotEqual(first["fields"]["animation_component_highlight"]["amount"],
                            later["fields"]["animation_component_highlight"]["amount"])
        state["animation_debug"]["highlight_component"] = False
        off = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0)
        self.assertNotIn("animation_component_highlight", off["fields"])
        self.assertIsNone(g_editor.update_animation_debug_preview(state, "play", {}, None, 0))

    def test_editor_preview_is_isolated_and_draft_survives_reload(self):
        self.edit()
        state = g_editor.make_editor_state()
        entity = {"id": 7, "type": "red head", "animation_direction": "right"}
        original = copy.deepcopy(entity)
        state.update(selected_kind="animation_entity", selected_collection="brains", selected_id=7,
                     redhead_animation_draft=self.draft)
        state["animation_debug"]["playback"] = "keyframe"
        preview = g_editor.update_animation_debug_preview(state, "animation", {"brains": {7: entity}}, None, 0)
        self.assertIs(preview["fields"]["animation_profile_override"], self.draft["document"])
        self.assertEqual(entity, original)
        self.assertEqual(authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES, self.live["REDHEAD_CUTOUT_GAIT_PROFILES"])
        importlib.reload(g_editor)
        self.assertIs(g_editor.get_or_create_editor_state({"editor_state": state})["redhead_animation_draft"], self.draft)
        self.draft["preview"] = False
        preview = g_editor.update_animation_debug_preview(state, "animation", {"brains": {7: entity}}, None, 0)
        self.assertNotIn("animation_profile_override", preview["fields"])
        self.assertIsNone(g_editor.update_animation_debug_preview(state, "play", {"brains": {7: entity}}, None, 0))

    def test_reload_watcher_uses_validated_loader(self):
        with mock.patch.object(g_main, "g_reloadable_modules", [("g_animation_redhead_data", authoring.data)]), \
                mock.patch.object(g_main, "get_file_write_time", return_value=2), \
                mock.patch.object(g_main, "render_error_message"), \
                mock.patch.object(authoring, "reload_data", side_effect=ValueError("invalid")):
            times = {"g_animation_redhead_data": 1}
            self.assertEqual(g_main.reload_modules_if_needed(times), set())
            self.assertEqual(times["g_animation_redhead_data"], 1)


if __name__ == "__main__":
    unittest.main()
