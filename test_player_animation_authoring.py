import copy
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import g_animation_authoring as authoring
import g_editor
import g_main
import g_render_order


class PlayerAnimationAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "player_data.py"
        self.path.write_bytes(authoring.data_path("player").read_bytes())
        self.draft = authoring.new_draft(self.path, character="player")
        self.original = copy.deepcopy(self.draft["document"])
        self.redhead = copy.deepcopy(authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES)
        self.addCleanup(lambda: authoring.player_data.__dict__.update(self.original))

    def edit(self, facing="right", group="legs", track="walk", key="near_upper_leg_degrees", value=-40):
        path = authoring.pose_path("player", facing, group, track)
        authoring.edit_pose(self.draft, track, 0, key, value, profile_path=path)
        return path

    def test_all_directional_profile_paths_roundtrip_without_touching_redhead(self):
        for facing in ("right", "left", "up", "down"):
            for group in ("legs", "arms", "body"):
                for track in ("walk", "run"):
                    path = authoring.pose_path("player", facing, group, track)
                    pose = authoring.get_path(self.draft["document"], path)[0]
                    key = next(iter(pose))
                    authoring.edit_pose(self.draft, track, 0, key, pose[key] + 0.1, profile_path=path)
        authoring.prepare_save(self.draft)
        authoring.save(self.draft, self.path)
        self.assertEqual(authoring.new_draft(self.path, "player")["document"], self.draft["document"])
        self.assertFalse(authoring.dirty(self.draft))
        self.assertEqual(authoring.data.REDHEAD_CUTOUT_GAIT_PROFILES, self.redhead)

    def test_draft_changes_rendered_pose_without_leaking_to_next_entity(self):
        self.edit()
        entity = {"id": "player", "animation_direction": "right",
                  "procedural_gait": {"phase": 0, "blend": 1}}
        original = g_render_order.build_player_cutout_rig_parts(entity)
        preview = g_render_order.build_player_cutout_rig_parts(dict(entity, animation_profile_override=self.draft["document"]))
        self.assertNotEqual(preview, original)
        self.assertEqual(g_render_order.build_player_cutout_rig_parts(entity), original)
        self.assertEqual(authoring.player_data.PLAYER_CUTOUT_GAIT_PROFILES,
                         self.original["PLAYER_CUTOUT_GAIT_PROFILES"])
        with mock.patch.object(g_render_order, "_build_player_cutout_rig_parts", side_effect=ValueError("bad pose")):
            with self.assertRaises(ValueError):
                g_render_order.build_player_cutout_rig_parts(dict(entity, animation_profile_override=self.draft["document"]))
        self.assertIsNone(g_render_order._PLAYER_PREVIEW_DATA.get())

    def test_front_pixel_offsets_change_only_the_authored_direction(self):
        self.edit("up", "legs", "walk", "near_foot_x_pixels", 2.0)
        for direction in ("up", "down"):
            entity = {"id": "player", "animation_direction": direction,
                      "procedural_gait": {"phase": 0, "blend": 1}}
            normal = g_render_order.build_player_cutout_rig_parts(entity)
            preview = g_render_order.build_player_cutout_rig_parts(dict(entity, animation_profile_override=self.draft["document"]))
            self.assertEqual(normal == preview, direction == "down")

    def test_player_linked_pixel_edits_and_incompatible_paste(self):
        path = authoring.pose_path("player", "up", "arms", "run")
        authoring.edit_pose(self.draft, "run", 0, "near_hand_y_pixels", -3.0, True, path)
        self.assertEqual(authoring.get_path(self.draft["document"], path)[2]["far_hand_y_pixels"], -3)
        authoring.copy_pose(self.draft, "run", 0, path)
        walk_path = authoring.pose_path("player", "up", "arms", "walk")
        before = copy.deepcopy(self.draft["document"])
        with self.assertRaisesRegex(ValueError, "different fields"):
            authoring.paste_pose(self.draft, "walk", 0, walk_path)
        self.assertEqual(self.draft["document"], before)
        authoring.history(self.draft)
        self.assertFalse(authoring.dirty(self.draft))
        authoring.history(self.draft, redo=True)
        authoring.reset_pose(self.draft, "run", 0, path)
        self.assertEqual(authoring.get_path(self.draft["document"], path)[0],
                         authoring.get_path(self.original, path)[0])

    def test_player_save_conflict_and_invalid_reload_retain_working_values(self):
        self.edit()
        authoring.prepare_save(self.draft)
        self.path.write_text(self.path.read_text() + "\n# hand edit\n")
        with self.assertRaisesRegex(ValueError, "externally"):
            authoring.save(self.draft, self.path)
        self.path.write_text("PLAYER_CUTOUT_RIG_DEFAULTS = {}")
        with self.assertRaises(ValueError):
            authoring.reload_data(self.path, "player")
        self.assertEqual(authoring.player_data.PLAYER_CUTOUT_GAIT_PROFILES,
                         self.original["PLAYER_CUTOUT_GAIT_PROFILES"])
        self.assertTrue(authoring.dirty(self.draft))

    def test_player_data_reload_reaches_renderer_and_has_watcher(self):
        self.edit()
        authoring.prepare_save(self.draft)
        authoring.save(self.draft, self.path)
        authoring.reload_data(self.path, "player")
        self.assertIs(g_render_order.PLAYER_CUTOUT_GAIT_PROFILES, authoring.player_data.PLAYER_CUTOUT_GAIT_PROFILES)
        self.assertIn("g_animation_player_data", dict(g_main.g_reloadable_modules))
        g_render_order.PLAYER_CUTOUT_GAIT_PROFILES = {"stale": True}
        importlib.reload(g_render_order)
        self.assertIs(g_render_order.PLAYER_CUTOUT_GAIT_PROFILES, authoring.player_data.PLAYER_CUTOUT_GAIT_PROFILES)

    def test_player_catalog_uses_player_draft_and_highlight(self):
        self.edit()
        state = g_editor.make_editor_state()
        state["player_animation_draft"] = self.draft
        state["redhead_animation_draft"] = authoring.new_draft()
        state["animation_debug"].update(preview_source="Player preview", authoring=True,
                                        highlight_component=True, edit_field="near_foot_y_pixels")
        preview = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0)
        self.assertIs(preview["fields"]["animation_profile_override"], self.draft["document"])
        self.assertIn("animation_component_highlight", preview["fields"])
        state["animation_debug"]["preview_source"] = "Redhead preview"
        preview = g_editor.update_animation_debug_preview(state, "animation", {}, None, 0)
        self.assertIs(preview["fields"]["animation_profile_override"], state["redhead_animation_draft"]["document"])


if __name__ == "__main__":
    unittest.main()
