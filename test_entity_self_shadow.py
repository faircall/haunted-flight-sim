import copy
import unittest

import g_graphics
import g_render_order


COLLISION_GRID = {"tile_width": 16, "tile_height": 16}


def make_item(source_id, x, y, sample_height=12.0, mode="upright_box"):
    return {
        "source_id": source_id,
        "id": source_id,
        "base_world": {"x": float(x), "y": float(y)},
        "bounds_world": {"x": float(x) - 8.0, "y": float(y) - 16.0, "width": 16.0, "height": 16.0},
        "sort_y": float(y),
        "visual_height": 24.0,
        "light_sample_height": float(sample_height),
        "ground_footprint": {"shape": "rectangle", "offset": {"x": 0.0, "y": 0.0}, "size": {"x": 8.0, "y": 8.0}},
        "self_shadow": {"mode": mode, "strength": 1.0, "softness": 0.1, "back_fill": 0.05},
        "entity_light_occluder": {"enabled": False, "height": 0.0, "blocks_entity_lighting": False},
        "outline": {"policy": "never", "color": [1.0, 1.0, 1.0, 0.5], "width": 1.0, "priority": 0},
        "occludes_render_items": False
    }


def make_prepared_light(light_id, x, y, height=22.0, render_style="world", light_type="point"):
    light = {"type": light_type, "position": {"x": float(x), "y": float(y)}, "height": float(height), "radius": 100.0, "intensity": 1.0, "falloff": 1.0, "color": [1.0, 0.8, 0.6], "enabled": True, "affects_entities": True, "render_style": render_style, "casts_wall_shadows": False}
    if light_type == "top_down":
        light["size"] = {"x": 100.0, "y": 100.0}
    return {"id": light_id, "light": light, "world_position": dict(light["position"]), "affects_entities": True, "casts_wall_shadows": False, "visibility_polygon": None}


class EntitySelfShadowTests(unittest.TestCase):
    def prepare(self, light):
        target = make_item("target", 0, 0)
        g_graphics.prepare_entity_self_shadows([target], [light], [], COLLISION_GRID)
        return target["self_shadow_summary"], target["self_shadow"]

    def test_camera_front_light_preserves_original_composite_across_sprite(self):
        summary, policy = self.prepare(make_prepared_light("front", 0, 20))
        self.assertAlmostEqual(summary["face_exposure"][0], 1.0)
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.0), 1.0)
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.5), 1.0)
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 1.0), 1.0)

    def test_rear_light_darkens_visible_camera_face(self):
        summary, policy = self.prepare(make_prepared_light("rear", 0, -20))
        self.assertAlmostEqual(summary["face_exposure"][1], 1.0)
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.5), policy["back_fill"])

    def test_side_light_keeps_near_half_and_darkens_away_half(self):
        summary, policy = self.prepare(make_prepared_light("right", 20, 0))
        self.assertAlmostEqual(summary["face_exposure"][3], 1.0)
        self.assertLess(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.2), 0.1)
        self.assertGreater(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.8), 0.9)

    def test_top_down_light_is_omnidirectional(self):
        summary, policy = self.prepare(make_prepared_light("top", 0, 0, light_type="top_down"))
        self.assertAlmostEqual(summary["omni_exposure"], 1.0)
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.2), 1.0)

    def test_readability_light_is_not_folded_into_world_self_shadow(self):
        target = make_item("target", 0, 0)
        light = make_prepared_light("readability", 0, -20, render_style="readability")
        g_graphics.prepare_entity_self_shadows([target], [light], [], COLLISION_GRID)
        summary = target["self_shadow_summary"]
        self.assertEqual(summary["sampled_world_strength"], 0.0)
        self.assertEqual(summary["world_occlusion_scale"], 1.0)


class SelectiveEntityOcclusionTests(unittest.TestCase):
    def setUp(self):
        self.light = make_prepared_light("light", -20, 0, 22.0)
        self.target = make_item("target", 20, 0, 12.0)
        self.blocker = make_item("buddha", 0, 0, 82.0)
        self.blocker["entity_light_occluder"] = {"enabled": True, "height": 128.0, "blocks_entity_lighting": True}
        self.blocker["ground_footprint"] = {"shape": "rectangle", "offset": {"x": 0.0, "y": 0.0}, "size": {"x": 10.0, "y": 10.0}}

    def test_tall_buddha_blocks_low_ray(self):
        blocking = g_graphics.find_blocking_entity_light_occluder(self.light, self.target, [self.blocker])
        self.assertEqual(blocking["occluder"]["source_id"], "buddha")

    def test_target_does_not_self_block(self):
        self.target["entity_light_occluder"] = {"enabled": True, "height": 128.0, "blocks_entity_lighting": True}
        self.assertIsNone(g_graphics.find_blocking_entity_light_occluder(self.light, self.target, [self.target]))

    def test_low_corpse_does_not_block_higher_ray(self):
        self.blocker["entity_light_occluder"]["height"] = 3.0
        self.assertIsNone(g_graphics.find_blocking_entity_light_occluder(self.light, self.target, [self.blocker]))

    def test_high_light_passes_over_short_blocker(self):
        self.light["light"]["height"] = 120.0
        self.blocker["entity_light_occluder"]["height"] = 24.0
        self.assertIsNone(g_graphics.find_blocking_entity_light_occluder(self.light, self.target, [self.blocker]))

    def test_blocked_world_light_scales_direct_texture_without_touching_ambient(self):
        g_graphics.prepare_entity_self_shadows([self.target], [self.light], [self.blocker], COLLISION_GRID)
        summary = self.target["self_shadow_summary"]
        self.assertEqual(summary["blocked_direct_count"], 1)
        self.assertEqual(summary["world_occlusion_scale"], 0.0)

    def test_selective_blocking_does_not_mutate_wall_geometry(self):
        self.light["casts_wall_shadows"] = True
        self.light["visibility_polygon"] = [{"x": -30.0, "y": -30.0}, {"x": 30.0, "y": -30.0}, {"x": 30.0, "y": 30.0}, {"x": -30.0, "y": 30.0}]
        original = copy.deepcopy(self.light["visibility_polygon"])
        g_graphics.prepare_entity_self_shadows([self.target], [self.light], [self.blocker], COLLISION_GRID)
        self.assertEqual(self.light["visibility_polygon"], original)


class HeightAwareShadowTests(unittest.TestCase):
    def test_taller_entity_casts_longer_shadow(self):
        low = {"mode": "upright", "cast_height": 20.0, "length_scale": 1.0, "minimum_length": 1.0, "maximum_length": 200.0}
        tall = dict(low, cast_height=40.0)
        self.assertGreater(g_render_order.calculate_shadow_length(tall, 50.0, 100.0), g_render_order.calculate_shadow_length(low, 50.0, 100.0))

    def test_higher_light_shortens_shadow(self):
        shadow = {"mode": "upright", "cast_height": 30.0, "length_scale": 1.0, "minimum_length": 1.0, "maximum_length": 200.0}
        self.assertLess(g_render_order.calculate_shadow_length(shadow, 50.0, 150.0), g_render_order.calculate_shadow_length(shadow, 50.0, 80.0))

    def test_entity_taller_than_light_clamps_safely(self):
        shadow = {"mode": "upright", "cast_height": 128.0, "length_scale": 1.0, "minimum_length": 8.0, "maximum_length": 160.0}
        self.assertEqual(g_render_order.calculate_shadow_length(shadow, 80.0, 22.0), 160.0)

    def test_grounded_shadow_is_short(self):
        shadow = {"mode": "grounded", "cast_height": 3.0, "length_scale": 1.0, "minimum_length": 1.0, "maximum_length": 80.0}
        self.assertLessEqual(g_render_order.calculate_shadow_length(shadow, 100.0, 22.0), 16.0)

    def test_shadow_none_skips(self):
        self.assertIsNone(g_render_order.calculate_shadow_length({"mode": "none"}, 50.0, 22.0))

    def test_buddha_default_shadow_exceeds_sprite_footprint(self):
        shadow = g_render_order.make_default_entity_render_metadata("buddha")["shadow"]
        self.assertGreater(g_render_order.calculate_shadow_length(shadow, 80.0, 22.0), 128.0)


if __name__ == "__main__":
    unittest.main()
