import copy
import math
from types import SimpleNamespace
import unittest
from unittest import mock

import g_animation
import g_graphics as graphics
import g_render_order as render
import g_update_and_render as game


class CharacterShadowTests(unittest.TestCase):
    def item(self, facing="right", phase=0.0, player=False):
        entity = {"id": "player" if player else 7, "type": "red head",
                  "animation_direction": facing, "position": {"x": 100, "y": 100},
                  "procedural_gait": {"phase": phase, "blend": 1, "run_blend": 0}}
        assets = {"sprite_sheets": {}}
        tile_map = {"tile_width": 16, "tile_height": 16}
        return (render.build_player_render_item(entity, tile_map, assets) if player else
                render.build_brain_render_item(7, entity, tile_map, assets))

    def assets(self, item):
        size = 32 if item["source"] == "player" else 24
        return {"textures": {p["texture"]: SimpleNamespace(width=size, height=size)
                             for p in item["draw_data"]["cutout_rig_parts"]}}

    def test_animated_shadow_resolves_pose_without_old_sprite_sheet(self):
        for player in (False, True):
            for facing in ("up", "down", "left", "right"):
                item = self.item(facing, math.pi / 2, player)
                info = graphics.get_render_item_shadow_sprite_info(item, self.assets(item))
                self.assertIs(info["pose_parts"], item["draw_data"]["cutout_rig_parts"])
                self.assertEqual(info["base_world"], item["base_world"])
                self.assertGreater(info["pose_bounds"]["width"], 0)

    def test_bounds_include_rotated_scaled_equipment_and_placeholder(self):
        part = {"texture": "gun", "origin": {"x": 0, "y": 0},
                "pivot_local": {"x": 40, "y": -10}, "rotation": 90,
                "scale": {"x": 2, "y": 3}, "flip_x": True}
        bounds = graphics.cutout_shadow_bounds([part], {"gun": SimpleNamespace(width=5, height=2)})
        self.assertLessEqual(bounds["x"], 34)
        self.assertGreaterEqual(bounds["x"] + bounds["width"], 40)
        self.assertLessEqual(bounds["y"], -10)
        self.assertGreaterEqual(bounds["y"] + bounds["height"], 0)
        placeholder = dict(part, placeholder_rect=True, placeholder_size={"x": 5, "y": 2})
        self.assertEqual(graphics.cutout_shadow_bounds([placeholder], {}), bounds)

    def test_static_shadow_fallback_is_preserved(self):
        texture = SimpleNamespace(width=48, height=24)
        item = {"texture": {"collection": "textures", "name": "statue"},
                "source_rect": {"x": 24, "y": 0, "width": 24, "height": 24},
                "dest_rect": {"width": 24, "height": 24}, "base_world": {"x": 0, "y": 0}}
        info = graphics.get_render_item_shadow_sprite_info(item, {"textures": {"statue": texture}})
        self.assertIs(info["texture"], texture)
        self.assertNotIn("pose_parts", info)

    def test_padding_does_not_move_projected_foot_anchor(self):
        item = self.item()
        info = graphics.get_render_item_shadow_sprite_info(item, self.assets(item))
        for bounds in ({"x": 0, "y": 0, "width": 24, "height": 24},
                       {"x": -25, "y": -17, "width": 80, "height": 67}):
            info["pose_bounds"] = bounds
            quad = graphics.build_cinematic_shadow_quad(info, item["shadow"], {"x": 10, "y": 130}, 50)
            u = (info["pose_anchor"]["x"] - bounds["x"]) / bounds["width"]
            v = (info["pose_anchor"]["y"] - bounds["y"]) / bounds["height"]
            for axis in ("x", "y"):
                projected = (quad["far_left"][axis] + u * (quad["far_right"][axis] - quad["far_left"][axis])
                             + v * (quad["near_left"][axis] - quad["far_left"][axis]))
                self.assertAlmostEqual(projected, quad["near_center"][axis])

    def test_contact_follows_mirrored_feet_and_fades_with_lift(self):
        right, left = self.item(), self.item("left")
        for a, b in zip(graphics.character_foot_contacts(right), graphics.character_foot_contacts(left)):
            self.assertAlmostEqual(a["x"] + b["x"] - 2 * right["dest_rect"]["x"], 24)
        contacts = graphics.character_foot_contacts(self.item(phase=math.pi / 2))
        near = next(c for c in contacts if c["side"] == "near")
        far = next(c for c in contacts if c["side"] == "far")
        self.assertLess(far["opacity"], near["opacity"])
        self.assertEqual(far["y"], near["y"])
        raised = self.item()
        for part in raised["draw_data"]["cutout_rig_parts"]:
            if "foot_local" in part:
                part["foot_local"]["y"] -= 10
        self.assertTrue(all(c["opacity"] == 0 for c in graphics.character_foot_contacts(raised)))
        raised["contact_shadow"]["enabled"] = False
        self.assertEqual(graphics.character_foot_contacts(raised), [])

    def test_scaled_foot_marker_matches_rendered_transform(self):
        part = {"pivot_local": {"x": 8, "y": 9}, "origin": {"x": 18.5, "y": 18.5},
                "scale": {"x": 1, "y": 0.5}, "rotation": 90, "flip_x": True}
        g_animation.attach_foot_marker(part, {"x": 13.5, "y": 21}, 32)
        self.assertAlmostEqual(part["foot_local"]["x"], 6.75)
        self.assertAlmostEqual(part["foot_local"]["y"], 9)

    def test_existing_entities_gain_contact_policy_without_overwriting_authored_shadow(self):
        entity = {"type": "red head", "_render_metadata_version": 1,
                  "_render_metadata_type": "red head", "shadow": {"opacity": 0.41}}
        render.ensure_entity_render_metadata(entity)
        self.assertTrue(entity["contact_shadow"]["enabled"])
        self.assertEqual(entity["contact_shadow"]["fade_height"], 3.0)
        self.assertEqual(entity["shadow"]["opacity"], 0.41)

    def test_dead_redhead_has_no_foot_contacts(self):
        parts = g_animation.build_redhead_cutout_rig_parts({"current_state": "dead", "animation_direction": "right"})
        self.assertEqual(graphics.character_foot_contacts({"draw_data": {"cutout_rig_parts": parts}}), [])

    def test_atlas_uses_alpha_only_and_inverted_render_texture_uvs(self):
        item = self.item()
        assets = self.assets(item)
        assets["shaders"] = {"character_shadow_mask": {"shader": object()}}
        info = graphics.get_render_item_shadow_sprite_info(item, assets)
        original = copy.deepcopy(info["pose_parts"])
        target = SimpleNamespace(texture=SimpleNamespace(width=128, height=128))
        with mock.patch.object(graphics, "get_or_create_render_target", return_value=target), \
                mock.patch.object(graphics, "_draw_cutout_rig", return_value=True) as draw, \
                mock.patch.multiple(graphics.pr, begin_texture_mode=mock.DEFAULT, end_texture_mode=mock.DEFAULT,
                                    clear_background=mock.DEFAULT, begin_shader_mode=mock.DEFAULT, end_shader_mode=mock.DEFAULT):
            graphics.prepare_character_shadow_atlas({"shadows": [{"sprite_info": info}]}, assets)
        self.assertLess(info["source_rect"].height, 0)
        self.assertIs(info["texture"], target.texture)
        self.assertTrue(all(p["tint"] == [255]*4 for p in draw.call_args.args[0]["draw_data"]["cutout_rig_parts"]))
        self.assertEqual(info["pose_parts"], original)


if __name__ == "__main__":
    unittest.main()
