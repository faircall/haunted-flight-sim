import copy
import math
import unittest
from types import SimpleNamespace
from unittest import mock

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

    def test_entity_draw_snaps_camera_relative_position_to_pixel_grid(self):
        item = {
            "source_rect": {"x": 0.0, "y": 0.0, "width": 128.0, "height": 128.0},
            "dest_rect": {"x": 20.25, "y": 40.75, "width": 128.0, "height": 128.0},
        }
        with mock.patch.object(g_graphics.pr, "draw_texture_pro") as draw_texture:
            g_graphics._draw_render_item_main_shape(item, object(), SimpleNamespace(x=2.6, y=3.2))

        destination = draw_texture.call_args.args[2]
        self.assertEqual(destination.x, 18.0)
        self.assertEqual(destination.y, 38.0)

    def test_player_flashlight_has_stable_entity_direction_origin(self):
        player = {
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "aim_direction": {"x": 0.0, "y": -1.0},
            "animation_direction": "up",
        }
        flashlight = g_graphics.make_player_flashlight(player, {"tile_width": 16, "tile_height": 16})
        self.assertEqual(flashlight["entity_direction_origin"], {"x": 36.0, "y": 53.0})
        self.assertEqual(flashlight["position"], {"x": 36.0, "y": 43.0})

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

    def test_top_down_light_can_explicitly_opt_into_directional_handling(self):
        light = make_prepared_light("top-directional", 20, 0, light_type="top_down")
        light["light"]["entity_lighting_mode"] = "directional_profiles"
        summary, _ = self.prepare(light)
        self.assertAlmostEqual(summary["omni_exposure"], 0.0)
        self.assertAlmostEqual(summary["face_exposure"][3], 1.0)

    def test_readability_light_is_not_folded_into_world_self_shadow(self):
        target = make_item("target", 0, 0)
        light = make_prepared_light("readability", 0, -20, render_style="readability")
        g_graphics.prepare_entity_self_shadows([target], [light], [], COLLISION_GRID)
        summary = target["self_shadow_summary"]
        self.assertEqual(summary["sampled_world_strength"], 0.0)
        self.assertEqual(summary["world_occlusion_scale"], 1.0)

    def test_entity_light_scratch_does_not_project_floor_wall_polygon_through_sprite(self):
        prepared = make_prepared_light("wall-overlap", 20.0, 20.0)
        scratch = SimpleNamespace(texture=SimpleNamespace(width=64, height=64))
        assets = {"shaders": {"light_accumulation": {}}}
        with mock.patch.object(g_graphics, "draw_prepared_light_to_target") as draw_light, \
             mock.patch.object(g_graphics.pr, "begin_texture_mode"), \
             mock.patch.object(g_graphics.pr, "clear_background"), \
             mock.patch.object(g_graphics.pr, "begin_blend_mode"), \
             mock.patch.object(g_graphics.pr, "end_blend_mode"), \
             mock.patch.object(g_graphics.pr, "end_texture_mode"):
            g_graphics._render_single_prepared_entity_light(prepared, SimpleNamespace(x=0.0, y=0.0), scratch, assets)
        draw_light.assert_called_once_with(
            prepared,
            mock.ANY,
            scratch,
            assets,
            include_receivers=False,
            clip_to_wall_visibility=False,
        )

    def test_ordinary_world_light_rendering_still_uses_wall_visibility(self):
        prepared = make_prepared_light("world-wall", 20.0, 20.0)
        target = SimpleNamespace(texture=SimpleNamespace(width=64, height=64))
        assets = {"shaders": {"light_accumulation": {}}}
        with mock.patch.object(g_graphics, "draw_prepared_radial_light_to_target") as draw_radial:
            g_graphics.draw_prepared_light_to_target(prepared, SimpleNamespace(x=0.0, y=0.0), target, assets)
        self.assertTrue(draw_radial.call_args.kwargs["clip_to_wall_visibility"])


class DirectionBasisGeometryTests(unittest.TestCase):
    def make_basis_item(self, destination=None):
        return {
            "source_rect": {"x": 0.0, "y": 0.0, "width": 128.0, "height": 128.0},
            "dest_rect": destination or {"x": 0.0, "y": 0.0, "width": 128.0, "height": 128.0},
            "base_world": {"x": 64.0, "y": 104.0},
            "self_shadow": {
                "mode": "directional_profiles",
                "direction_basis": {
                    "mode": "sprite_rect",
                    "rect": {"x": 6.0, "y": 86.0, "width": 110.0, "height": 36.0},
                    "ray_grid": {"columns": 7, "rows": 3},
                    "corner_blend_fraction": 0.20,
                    "maximum_adjacent_weight": 0.50
                }
            }
        }

    def test_unscaled_frame_local_rectangle_maps_exactly(self):
        self.assertEqual(g_graphics.get_render_item_direction_basis_world_rect(self.make_basis_item()), {"x": 6.0, "y": 86.0, "width": 110.0, "height": 36.0})

    def test_scaled_destination_maps_proportionally(self):
        rectangle = g_graphics.get_render_item_direction_basis_world_rect(self.make_basis_item({"x": 10.0, "y": 20.0, "width": 256.0, "height": 256.0}))
        self.assertEqual(rectangle, {"x": 22.0, "y": 192.0, "width": 220.0, "height": 72.0})

    def test_profile_divider_maps_from_sprite_local_to_world(self):
        item = self.make_basis_item({"x": 10.0, "y": 20.0, "width": 256.0, "height": 256.0})
        item["self_shadow"]["profile_divider"] = {
            "enabled": True,
            "top": {"x": 61.0, "y": 20.0},
            "bottom": {"x": 61.0, "y": 104.0},
        }
        self.assertEqual(g_graphics.get_render_item_profile_divider_world_line(item), {
            "top": {"x": 132.0, "y": 60.0},
            "bottom": {"x": 132.0, "y": 228.0},
        })

    def test_buddha_ray_grid_has_seven_by_three_equal_area_samples(self):
        samples = g_graphics.get_render_item_direction_basis_ray_samples(self.make_basis_item())
        self.assertEqual(len(samples), 21)
        self.assertEqual({sample["column"] for sample in samples}, set(range(7)))
        self.assertEqual({sample["row"] for sample in samples}, set(range(3)))
        self.assertTrue(all(6.0 < sample["world"]["x"] < 116.0 and 86.0 < sample["world"]["y"] < 122.0 for sample in samples))

    def test_bundle_uses_all_active_rays_for_a_point_light(self):
        item = self.make_basis_item()
        light = make_prepared_light("above", 61.0, 0.0)
        light["light"]["radius"] = 200.0
        bundle = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)
        self.assertEqual(bundle["total_ray_count"], 21)
        self.assertEqual(bundle["active_ray_count"], 21)
        self.assertGreater(bundle["weights"]["up"], 0.95)
        self.assertAlmostEqual(sum(bundle["weights"].values()), 1.0)

    def test_bundle_uses_only_intervals_reached_by_narrow_spotlight(self):
        item = self.make_basis_item()
        light = make_prepared_light("spot", -40.0, 104.0, light_type="spot")
        light["light"].update({
            "radius": 300.0,
            "direction": {"x": 1.0, "y": 0.0},
            "inner_angle": 1.0,
            "outer_angle": 4.0
        })
        bundle = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)
        active = [ray for ray in bundle["rays"] if ray["active"]]
        self.assertEqual(len(active), 7)
        self.assertEqual({ray["row"] for ray in active}, {1})
        self.assertEqual(bundle["weights"], {"down": 0.0, "up": 0.0, "left": 1.0, "right": 0.0})

    def test_flashlight_profile_direction_is_stable_when_cone_reaches_plate(self):
        item = self.make_basis_item()
        light = make_prepared_light("player-flashlight", -40.0, 80.0, light_type="spot")
        light["light"].update({
            "radius": 300.0,
            "inner_angle": 2.0,
            "outer_angle": 5.0,
            "entity_direction_origin": {"x": -40.0, "y": 104.0},
        })

        light["light"]["direction"] = {"x": -1.0, "y": 0.0}
        before = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)
        self.assertEqual(before["active_ray_count"], 0)

        to_centre = {"x": 101.0, "y": 24.0}
        length = math.hypot(to_centre["x"], to_centre["y"])
        light["light"]["direction"] = {"x": to_centre["x"] / length, "y": to_centre["y"] / length}
        after = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)
        self.assertGreater(after["active_ray_count"], 0)

        expected = {"down": 0.0, "up": 0.0, "left": 1.0, "right": 0.0}
        self.assertEqual(before["weights"], expected)
        self.assertEqual(after["weights"], expected)
        self.assertTrue(before["stable_direction_origin"])
        self.assertTrue(after["stable_direction_origin"])

    def test_spotlight_sprite_overlap_survives_gaps_between_cpu_samples(self):
        item = self.make_basis_item()
        item["bounds_world"] = {"x": 0.0, "y": 0.0, "width": 128.0, "height": 128.0}
        light = make_prepared_light("grazing-spot", 180.0, 30.0, light_type="spot")
        light["light"].update({
            "radius": 300.0,
            "direction": {"x": -1.0, "y": 0.0},
            "inner_angle": 2.0,
            "outer_angle": 8.0,
        })
        with mock.patch.object(g_graphics, "get_render_item_light_sample_points", return_value=[]):
            strength = g_graphics.get_prepared_light_strength_for_render_item(light, item, COLLISION_GRID)
        self.assertGreater(strength, 0.000001)

    def test_bundle_full_sweep_has_no_large_corner_handoff(self):
        item = self.make_basis_item()
        previous = None
        maximum_channel_step = 0.0
        for degrees in range(361):
            angle = math.radians(degrees)
            light = make_prepared_light("sweep", 61.0 + math.cos(angle) * 150.0, 104.0 + math.sin(angle) * 150.0)
            light["light"]["radius"] = 300.0
            weights = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)["weights"]
            if previous is not None:
                maximum_channel_step = max(maximum_channel_step, max(abs(weights[side] - previous[side]) for side in weights))
            previous = weights
        self.assertLess(maximum_channel_step, 0.05)

    def assert_entry(self, position, side, side_position):
        entry = g_graphics.calculate_render_item_light_direction_entry(self.make_basis_item(), position)
        self.assertEqual(entry["side"], side)
        self.assertAlmostEqual(entry["side_position"], side_position)
        return entry

    def test_light_above_centre_enters_up_at_half(self):
        self.assert_entry({"x": 61.0, "y": 0.0}, "up", 0.5)

    def test_light_above_left_quarter_still_enters_up(self):
        entry = g_graphics.calculate_render_item_light_direction_entry(self.make_basis_item(), {"x": 33.5, "y": 0.0})
        self.assertEqual(entry["side"], "up")
        self.assertEqual(entry["weights"], {"down": 0.0, "up": 1.0, "left": 0.0, "right": 0.0})

    def test_light_directly_left_enters_left_at_half(self):
        self.assert_entry({"x": -20.0, "y": 104.0}, "left", 0.5)

    def test_light_directly_right_enters_right(self):
        self.assert_entry({"x": 150.0, "y": 104.0}, "right", 0.5)

    def test_light_directly_below_enters_down(self):
        self.assert_entry({"x": 61.0, "y": 160.0}, "down", 0.5)

    def test_light_inside_rectangle_is_neutral(self):
        entry = g_graphics.calculate_render_item_light_direction_entry(self.make_basis_item(), {"x": 61.0, "y": 104.0})
        self.assertTrue(entry["inside"])
        self.assertTrue(entry["omni"])
        self.assertEqual(sum(entry["weights"].values()), 0.0)

    def test_focused_debug_draws_hollow_transformed_rectangle(self):
        with mock.patch.object(g_graphics.pr, "draw_rectangle_lines") as draw_rectangle, mock.patch.object(g_graphics.pr, "draw_circle"):
            count = g_graphics.draw_entity_direction_basis_debug([self.make_basis_item()], SimpleNamespace(x=2.0, y=20.0))
        self.assertEqual(count, 1)
        draw_rectangle.assert_called_once_with(4, 66, 110, 36, g_graphics.pr.ORANGE)


    def test_focused_debug_draws_every_point_and_flashlight_entry_ray(self):
        item = self.make_basis_item()
        point_entry = g_graphics.calculate_render_item_light_direction_entry(item, {"x": -20.0, "y": 104.0})
        flashlight_entry = g_graphics.calculate_render_item_light_direction_entry(item, {"x": 150.0, "y": 104.0})
        item["self_shadow_summary"] = {"per_light": [
            {"light_id": "point", "light_position": {"x": -20.0, "y": 104.0}, "direction_entry": point_entry, "weights": point_entry["weights"], "blocked": False},
            {"light_id": "flashlight", "light_position": {"x": 150.0, "y": 104.0}, "direction_entry": flashlight_entry, "weights": flashlight_entry["weights"], "blocked": False}
        ]}
        prepared = [
            {"id": "point", "light": {"type": "point"}},
            {"id": "flashlight", "light": {"type": "spot", "owner_id": "player"}}
        ]
        with mock.patch.object(g_graphics.pr, "draw_rectangle_lines"), mock.patch.object(g_graphics.pr, "draw_circle"), mock.patch.object(g_graphics.pr, "draw_line") as draw_line, mock.patch.object(g_graphics.pr, "draw_text") as draw_text:
            g_graphics.draw_entity_direction_basis_debug([item], SimpleNamespace(x=0.0, y=0.0), prepared)
        self.assertEqual(draw_line.call_count, 2)
        draw_text.assert_not_called()
        self.assertEqual(draw_line.call_args_list[0].args[-1], g_graphics.pr.SKYBLUE)
        self.assertEqual(draw_line.call_args_list[1].args[-1], g_graphics.pr.GOLD)

    def test_focused_debug_draws_all_bundle_rays_without_text(self):
        item = self.make_basis_item()
        light = make_prepared_light("bundle-point", 61.0, 0.0)
        light["light"]["radius"] = 200.0
        bundle = g_graphics.calculate_render_item_light_direction_bundle(item, light, COLLISION_GRID)
        item["self_shadow_summary"] = {"per_light": [{
            "light_id": light["id"],
            "light_position": light["world_position"],
            "direction_entry": bundle,
            "weights": bundle["weights"],
            "blocked": False
        }]}
        with mock.patch.object(g_graphics.pr, "draw_rectangle_lines"), mock.patch.object(g_graphics.pr, "draw_circle"), mock.patch.object(g_graphics.pr, "draw_line") as draw_line, mock.patch.object(g_graphics.pr, "draw_text") as draw_text:
            g_graphics.draw_entity_direction_basis_debug([item], SimpleNamespace(x=0.0, y=0.0), [light])
        self.assertEqual(draw_line.call_count, 21)
        self.assertTrue(all(call.args[-1] == g_graphics.pr.SKYBLUE for call in draw_line.call_args_list))
        draw_text.assert_not_called()


class CornerBlendTests(unittest.TestCase):
    def weights(self, side, position):
        return g_graphics.calculate_corner_blend_directional_weights(side, position, 0.20, 0.25)

    def test_up_start_blends_left(self):
        self.assertEqual(self.weights("up", 0.0), {"down": 0.0, "up": 0.75, "left": 0.25, "right": 0.0})

    def test_up_middle_is_pure(self):
        self.assertEqual(self.weights("up", 0.5), {"down": 0.0, "up": 1.0, "left": 0.0, "right": 0.0})

    def test_up_end_blends_right(self):
        self.assertEqual(self.weights("up", 1.0), {"down": 0.0, "up": 0.75, "left": 0.0, "right": 0.25})

    def test_left_endpoints_blend_up_and_down(self):
        self.assertEqual(self.weights("left", 0.0), {"down": 0.0, "up": 0.25, "left": 0.75, "right": 0.0})
        self.assertEqual(self.weights("left", 1.0), {"down": 0.25, "up": 0.0, "left": 0.75, "right": 0.0})

    def test_weights_are_normalised_non_negative_and_bounded(self):
        for side in ("down", "up", "left", "right"):
            for index in range(101):
                weights = self.weights(side, index / 100.0)
                self.assertTrue(all(value >= 0.0 for value in weights.values()))
                self.assertAlmostEqual(sum(weights.values()), 1.0)
                self.assertLessEqual(sum(value for key, value in weights.items() if key != side), 0.25)

    def test_corner_band_transition_is_continuous(self):
        before = self.weights("up", 0.20 - 0.000001)
        after = self.weights("up", 0.20 + 0.000001)
        self.assertLess(abs(before["up"] - after["up"]), 0.00001)
        self.assertLess(abs(before["left"] - after["left"]), 0.00001)

    def test_half_weight_endpoint_is_continuous_across_geometric_corner(self):
        from_up = g_graphics.calculate_corner_blend_directional_weights("up", 0.0, 0.20, 0.50)
        from_left = g_graphics.calculate_corner_blend_directional_weights("left", 0.0, 0.20, 0.50)
        self.assertEqual(from_up, from_left)
        self.assertEqual(from_up, {"down": 0.0, "up": 0.5, "left": 0.5, "right": 0.0})


class DirectionalProfileTests(unittest.TestCase):
    def attenuation(self, face_exposure, response, **policy_values):
        summary = {"face_exposure": face_exposure, "omni_exposure": policy_values.pop("omni_exposure", 0.0)}
        policy = {"mode": "directional_profiles", "strength": 1.0, "minimum_direct": 0.0}
        policy.update(policy_values)
        return g_graphics.calculate_directional_profile_attenuation(summary, policy, response)

    def test_none_mode_remains_neutral(self):
        summary = {"face_exposure": [0.0, 1.0, 0.0, 0.0], "omni_exposure": 0.0}
        self.assertEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, {"mode": "none", "strength": 1.0}, 0.5), 1.0)

    def test_upright_box_reference_output_is_unchanged(self):
        summary = {"face_exposure": [0.0, 0.25, 0.30, 0.45], "omni_exposure": 0.10}
        policy = {"mode": "upright_box", "strength": 0.86, "softness": 0.10, "back_fill": 0.06}
        self.assertAlmostEqual(g_graphics.calculate_entity_self_shadow_at_u(summary, policy, 0.20), 0.4969)

    def test_pure_down_exposure_uses_only_red(self):
        self.assertAlmostEqual(self.attenuation([1.0, 0.0, 0.0, 0.0], [0.11, 0.22, 0.33, 0.44]), 0.11)

    def test_pure_up_exposure_uses_only_green(self):
        self.assertAlmostEqual(self.attenuation([0.0, 1.0, 0.0, 0.0], [0.11, 0.22, 0.33, 0.44]), 0.22)

    def test_pure_left_exposure_uses_only_blue(self):
        self.assertAlmostEqual(self.attenuation([0.0, 0.0, 1.0, 0.0], [0.11, 0.22, 0.33, 0.44]), 0.33)

    def test_pure_right_exposure_uses_only_alpha(self):
        self.assertAlmostEqual(self.attenuation([0.0, 0.0, 0.0, 1.0], [0.11, 0.22, 0.33, 0.44]), 0.44)

    def test_upper_left_diagonal_interpolates_green_and_blue(self):
        self.assertAlmostEqual(self.attenuation([0.0, 0.5, 0.5, 0.0], [0.0, 0.2, 0.8, 0.0]), 0.5)

    def test_corner_profile_combines_only_primary_and_adjacent_channels(self):
        response = [0.1, 0.2, 0.8, 0.9]
        weights = g_graphics.calculate_corner_blend_directional_weights("up", 0.0, 0.20, 0.25)
        policy = {"strength": 1.0, "minimum_direct": 0.0}
        self.assertAlmostEqual(g_graphics.calculate_per_light_profile_survival(response, weights, policy), 0.2 * 0.75 + 0.8 * 0.25)

    def test_directional_preparation_uses_down_up_left_right_order(self):
        target = make_item("target", 0, 0, mode="directional_profiles")
        directions = [("down", 0, 20, 0), ("up", 0, -20, 1), ("left", -20, 0, 2), ("right", 20, 0, 3)]
        for light_id, x, y, channel in directions:
            with self.subTest(light_id=light_id):
                g_graphics.prepare_entity_self_shadows([target], [make_prepared_light(light_id, x, y)], [], COLLISION_GRID)
                exposure = target["self_shadow_summary"]["face_exposure"]
                self.assertAlmostEqual(exposure[channel], 1.0)
                self.assertAlmostEqual(sum(exposure), 1.0)

    def test_omni_exposure_preserves_direct_light_independently(self):
        self.assertAlmostEqual(self.attenuation([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], omni_exposure=0.72), 0.72)

    def test_strength_zero_is_neutral(self):
        self.assertEqual(self.attenuation([1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], strength=0.0), 1.0)

    def test_minimum_direct_is_respected(self):
        self.assertEqual(self.attenuation([1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], minimum_direct=0.04), 0.04)

    def test_profile_divider_blocks_ray_to_far_side(self):
        visibility = g_graphics.calculate_profile_divider_visibility(
            {"x": 0.75, "y": 0.50}, {"x": -0.25, "y": -0.25},
            {"x": 0.50, "y": 0.0}, {"x": 0.50, "y": 0.8125}
        )
        self.assertEqual(visibility, 0.0)

    def test_profile_divider_preserves_near_side_and_central_back_light(self):
        divider_top = {"x": 0.50, "y": 0.0}
        divider_bottom = {"x": 0.50, "y": 0.8125}
        near_side = g_graphics.calculate_profile_divider_visibility(
            {"x": 0.25, "y": 0.50}, {"x": -0.25, "y": -0.25}, divider_top, divider_bottom
        )
        central_left = g_graphics.calculate_profile_divider_visibility(
            {"x": 0.25, "y": 0.50}, {"x": 0.50, "y": -0.25}, divider_top, divider_bottom
        )
        central_right = g_graphics.calculate_profile_divider_visibility(
            {"x": 0.75, "y": 0.50}, {"x": 0.50, "y": -0.25}, divider_top, divider_bottom
        )
        self.assertEqual((near_side, central_left, central_right), (1.0, 1.0, 1.0))

    def test_profile_divider_suppresses_only_up_back_channel(self):
        policy = {"mode": "directional_profiles", "strength": 1.0, "minimum_direct": 0.0}
        response = [0.11, 0.22, 0.33, 0.44]
        expected = [0.11, 0.0, 0.33, 0.44]
        for channel in range(4):
            exposure = [0.0, 0.0, 0.0, 0.0]
            exposure[channel] = 1.0
            actual = g_graphics.calculate_directional_profile_attenuation(
                {"face_exposure": exposure, "omni_exposure": 0.0},
                policy,
                response,
                profile_divider_visibility=0.0,
            )
            self.assertAlmostEqual(actual, expected[channel])

    def test_missing_response_texture_selects_upright_box_fallback(self):
        item = {"self_shadow": {"mode": "directional_profiles", "response_texture": {"collection": "textures", "name": "missing"}, "fallback_mode": "upright_box"}}
        resources = g_graphics.resolve_entity_self_shadow_resources(item, SimpleNamespace(width=128, height=128), {"textures": {}}, report_errors=False)
        self.assertEqual(resources["active_mode"], "upright_box")
        self.assertTrue(resources["fallback_used"])
        self.assertIsNone(resources["response_texture"])

    def test_invalid_response_dimensions_select_fallback(self):
        item = {"self_shadow": {"mode": "directional_profiles", "response_texture": {"collection": "textures", "name": "wrong_size"}, "fallback_mode": "upright_box"}}
        assets = {"textures": {"wrong_size": SimpleNamespace(id=2, width=64, height=128)}}
        resources = g_graphics.resolve_entity_self_shadow_resources(item, SimpleNamespace(width=128, height=128), assets, report_errors=False)
        self.assertEqual(resources["active_mode"], "upright_box")
        self.assertTrue(resources["fallback_used"])

    def test_missing_response_warning_is_reported_once(self):
        item = {"self_shadow": {"mode": "directional_profiles", "response_texture": {"collection": "textures", "name": "once_only_test"}, "fallback_mode": "upright_box"}}
        key_prefix = (repr("textures"), repr("once_only_test"))
        g_graphics._REPORTED_DIRECTIONAL_PROFILE_ASSET_ERRORS = {key for key in g_graphics._REPORTED_DIRECTIONAL_PROFILE_ASSET_ERRORS if key[:2] != key_prefix}
        with mock.patch("builtins.print") as print_mock:
            g_graphics.resolve_entity_self_shadow_resources(item, SimpleNamespace(width=128, height=128), {"textures": {}})
            g_graphics.resolve_entity_self_shadow_resources(item, SimpleNamespace(width=128, height=128), {"textures": {}})
        print_mock.assert_called_once()


class PerLightAccumulationTests(unittest.TestCase):
    def test_each_light_survives_independently_and_combined_is_sum(self):
        light_a = {"rgb": [0.8, 0.2, 0.1], "survival": 0.25}
        light_b = {"rgb": [0.1, 0.6, 0.4], "survival": 0.75}
        surviving_a = g_graphics.accumulate_surviving_direct_contributions([light_a])
        surviving_b = g_graphics.accumulate_surviving_direct_contributions([light_b])
        combined = g_graphics.accumulate_surviving_direct_contributions([light_a, light_b])
        self.assertEqual(combined, [surviving_a[index] + surviving_b[index] for index in range(3)])
        self.assertTrue(all(combined[index] >= surviving_a[index] for index in range(3)))
        self.assertTrue(all(combined[index] >= surviving_b[index] for index in range(3)))

    def test_blocked_light_contributes_zero_without_suppressing_visible_light(self):
        visible = {"rgb": [0.4, 0.3, 0.2], "survival": 0.5}
        blocked = {"rgb": [1.0, 1.0, 1.0], "survival": 1.0, "blocked": True}
        self.assertEqual(g_graphics.accumulate_surviving_direct_contributions([visible, blocked]), g_graphics.accumulate_surviving_direct_contributions([visible]))

    def test_ambient_and_readability_remain_independent(self):
        direct = g_graphics.accumulate_surviving_direct_contributions([{"rgb": [0.4, 0.2, 0.1], "survival": 0.5}])
        total = g_graphics.combine_independent_entity_lighting([0.1, 0.1, 0.1], direct, [0.3, 0.0, 0.2])
        for actual, expected in zip(total, [0.6, 0.2, 0.35]):
            self.assertAlmostEqual(actual, expected)


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
