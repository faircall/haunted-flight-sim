import unittest
import inspect
import math

import g_graphics
import g_render_order
import g_update_and_render


class RenderOrderTests(unittest.TestCase):
    @staticmethod
    def rig_part(parts, joint, side=None):
        return next(
            part for part in parts
            if part.get("rig_joint") == joint
            and (side is None or part.get("rig_side") == side)
        )

    def test_environment_composites_place_rain_between_emissive_fog_and_outlines(self):
        source = inspect.getsource(g_update_and_render.update_and_render)
        emissive = source.index('"emissive", False')
        rain = source.index("g_graphics.apply_rain_composite(")
        fog = source.index("g_graphics.apply_illuminated_fog(")
        outlines = source.index("g_graphics.draw_render_item_occlusion_outlines(")
        self.assertLess(emissive, rain)
        self.assertLess(rain, fog)
        self.assertLess(fog, outlines)

    def setUp(self):
        self.tile_map = {"tile_width": 16, "tile_height": 16}
        self.assets = {
            "sprite_sheets": {
                "blue_oxford_texture_sheet": {"right_frame_start": 2},
                "red_head_texture_sheet": {"left_frame_start": 3}
            },
            "textures": {}
        }

    def test_metadata_defaults_are_fresh(self):
        first = g_render_order.make_default_entity_render_metadata("buddha")
        second = g_render_order.make_default_entity_render_metadata("buddha")
        first["render_base_offset"]["y"] = 2.0
        self.assertEqual(second["render_base_offset"]["y"], 61.0)

    def test_ensure_preserves_authored_metadata(self):
        entity = {"type": "buddha", "visual_height": 90.0, "render_base_offset": {"x": 1.0, "y": 2.0}, "self_shadow": {"back_fill": 0.12}}
        g_render_order.ensure_entity_render_metadata(entity)
        self.assertEqual(entity["visual_height"], 90.0)
        self.assertEqual(entity["render_base_offset"], {"x": 1.0, "y": 2.0})
        self.assertEqual(entity["self_shadow"]["back_fill"], 0.12)
        self.assertTrue(entity["occludes_render_items"])

    def test_legacy_cinematic_shadow_migrates_once(self):
        entity = {"type": "buddha", "cinematic_shadow": {"enabled": True, "opacity": 0.77, "near_width": 0.8}}
        g_render_order.ensure_entity_render_metadata(entity)
        self.assertNotIn("cinematic_shadow", entity)
        self.assertEqual(entity["shadow"]["mode"], "upright")
        self.assertEqual(entity["shadow"]["opacity"], 0.77)

    def test_sort_uses_base_y(self):
        items = [
            {"sort_layer": "world", "sort_y": 20.0, "id": "later"},
            {"sort_layer": "world", "sort_y": 10.0, "id": "earlier"}
        ]
        result = g_render_order.sort_world_render_items(items)
        self.assertEqual([item["id"] for item in result], ["earlier", "later"])

    def test_builder_preserves_current_sprite_anchors(self):
        player = {"id": "player", "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0}, "animation_frame": "right_frame_start"}
        red_head = {"type": "red head", "position": {"tile_x": 2, "tile_y": 4, "x": 4.0, "y": 5.0}, "animation_frame": "left_frame_start"}
        items = g_render_order.build_sorted_world_render_items({"brains": {7: red_head}}, player, self.tile_map, self.assets)
        player_item = g_render_order.get_player_render_item(items)
        red_item = next(item for item in items if item["source"] == "red head")
        self.assertEqual(player_item["dest_rect"]["x"], 20.0)
        self.assertEqual(player_item["source_rect"]["x"], 64.0)
        self.assertEqual(red_item["dest_rect"]["x"], 12.0)
        self.assertEqual(red_item["source_rect"]["x"], 72.0)

    def test_animation_debug_override_is_render_only(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_direction": "right",
            "procedural_gait": {
                "phase": 0.0, "blend": 0.0, "run_blend": 0.0,
            },
        }
        original = {
            "animation_direction": player["animation_direction"],
            "procedural_gait": dict(player["procedural_gait"]),
        }
        self.assets["animation_debug_render_override"] = {
            "collection": "player",
            "id": "player",
            "fields": {
                "animation_direction": "left",
                "procedural_gait": {
                    "phase": math.pi, "blend": 1.0,
                    "run_blend": 1.0, "mode": "run", "speed": 0.0,
                },
            },
        }
        item = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        near_leg = self.rig_part(
            item["draw_data"]["cutout_rig_parts"], "upper_leg", "near",
        )
        self.assertEqual(player["animation_direction"], original["animation_direction"])
        self.assertEqual(player["procedural_gait"], original["procedural_gait"])
        self.assertTrue(near_leg["flip_x"])
        self.assertAlmostEqual(
            near_leg["rotation"],
            -g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["run"][2][
                "near_upper_leg_degrees"
            ],
        )

    def test_player_weapon_visibility_tracks_aiming_state(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_frame": "right_frame_start",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": False,
        }
        lowered = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        self.assertFalse(lowered["draw_data"]["aiming"])
        self.assertFalse(g_graphics._player_weapon_is_visible(lowered))

        player["aiming"] = True
        raised = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        self.assertTrue(raised["draw_data"]["aiming"])
        self.assertTrue(g_graphics._player_weapon_is_visible(raised))

        player["aiming"] = False
        player["weapon_transition"] = {
            "progress": 0.5, "target": 0.0, "phase": "holstering",
        }
        holstering = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        self.assertTrue(g_graphics._player_weapon_is_visible(holstering))

    def test_player_weapon_bezier_preserves_endpoints_and_adds_arc(self):
        center = {"x": 10.0, "y": 20.0}
        aim = {"x": 1.0, "y": 0.0}
        tucked = g_render_order.player_weapon_bezier_world_position(
            center, aim, 4.0, 0.0,
        )
        halfway = g_render_order.player_weapon_bezier_world_position(
            center, aim, 4.0, 0.5,
        )
        extended = g_render_order.player_weapon_bezier_world_position(
            center, aim, 4.0, 1.0,
        )

        self.assertEqual(tucked, center)
        self.assertEqual(extended, {"x": 14.0, "y": 20.0})
        self.assertGreater(halfway["x"], center["x"])
        self.assertLess(halfway["x"], extended["x"])
        self.assertGreater(halfway["y"], center["y"])

    def test_side_facing_player_builds_layered_cutout_rig(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_direction": "right",
            "animation_frame": "right_frame_start",
            "procedural_gait": {"phase": 0.0, "blend": 1.0},
        }
        drawing = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        parts = drawing["draw_data"]["cutout_rig_parts"]
        self.assertEqual(len(parts), 10)
        self.assertIn(
            "player_cutout_torso_right",
            [part["texture"] for part in parts],
        )
        self.assertEqual(parts[-1]["texture"], "player_cutout_head_right")
        self.assertNotEqual(
            self.rig_part(parts, "upper_leg", "far")["rotation"],
            self.rig_part(parts, "upper_leg", "near")["rotation"],
        )
        self.assertNotIn("player_cutout_gun_right", [
            part["texture"] for part in parts
        ])

    def test_near_and_far_limbs_use_independent_poses_and_shared_art(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {
                "phase": 0.0, "blend": 1.0, "run_blend": 0.0,
            },
        }
        parts = g_render_order.build_player_cutout_rig_parts(player)
        pose = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["walk"][0]
        near_arm = self.rig_part(parts, "upper_arm", "near")
        far_arm = self.rig_part(parts, "upper_arm", "far")
        near_leg = self.rig_part(parts, "upper_leg", "near")
        far_leg = self.rig_part(parts, "upper_leg", "far")

        self.assertEqual(near_arm["texture"], far_arm["texture"])
        self.assertEqual(near_leg["texture"], far_leg["texture"])
        self.assertNotEqual(near_arm["pivot_local"], far_arm["pivot_local"])
        self.assertNotEqual(near_leg["pivot_local"], far_leg["pivot_local"])
        self.assertAlmostEqual(
            near_arm["rotation"],
            pose["torso_degrees"] + pose["near_upper_arm_degrees"],
        )
        self.assertAlmostEqual(
            far_arm["rotation"],
            pose["torso_degrees"] + pose["far_upper_arm_degrees"],
        )
        self.assertAlmostEqual(
            near_leg["rotation"], pose["near_upper_leg_degrees"],
        )
        self.assertAlmostEqual(
            far_leg["rotation"], pose["far_upper_leg_degrees"],
        )

    def test_walk_arms_counter_swing_and_use_authored_elbow_bend(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {
                "phase": 0.0, "blend": 1.0, "run_blend": 0.0,
            },
        }
        parts = g_render_order.build_player_cutout_rig_parts(player)
        profile = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["walk"][0]
        near_upper_arm = self.rig_part(parts, "upper_arm", "near")
        near_lower_arm = self.rig_part(parts, "lower_arm", "near")
        near_upper_leg = self.rig_part(parts, "upper_leg", "near")
        expected_upper = (
            profile["torso_degrees"] + profile["near_upper_arm_degrees"]
        )
        self.assertAlmostEqual(near_upper_arm["rotation"], expected_upper)
        self.assertAlmostEqual(
            near_lower_arm["rotation"] - near_upper_arm["rotation"],
            -profile["near_elbow_bend_degrees"],
        )
        self.assertLess(
            (near_upper_arm["rotation"] - profile["torso_degrees"])
            * near_upper_leg["rotation"],
            0.0,
        )

    def test_leading_forearm_bends_toward_facing_direction(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {
                "phase": 0.0, "blend": 1.0, "run_blend": 1.0,
            },
        }
        right_parts = g_render_order.build_player_cutout_rig_parts(player)
        right_upper = self.rig_part(right_parts, "upper_arm", "near")
        right_lower = self.rig_part(right_parts, "lower_arm", "near")
        self.assertLess(right_upper["rotation"], 0.0)
        self.assertLess(right_lower["rotation"], right_upper["rotation"])

        player["animation_direction"] = "left"
        left_parts = g_render_order.build_player_cutout_rig_parts(player)
        left_upper = self.rig_part(left_parts, "upper_arm", "near")
        left_lower = self.rig_part(left_parts, "lower_arm", "near")
        self.assertGreater(left_upper["rotation"], 0.0)
        self.assertGreater(left_lower["rotation"], left_upper["rotation"])

    def test_running_arms_use_run_profile_and_far_arm_subdues_while_aiming(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "procedural_gait": {
                "phase": 0.0, "blend": 1.0, "run_blend": 1.0,
            },
        }
        moving = g_render_order.build_player_cutout_rig_parts(player)
        run_profile = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["run"]
        near_arm = self.rig_part(moving, "upper_arm", "near")
        self.assertAlmostEqual(
            near_arm["rotation"],
            run_profile[0]["torso_degrees"]
            + run_profile[0]["near_upper_arm_degrees"],
        )

        player.update({
            "aiming": True,
            "weapon_transition": {
                "progress": 1.0, "target": 1.0, "phase": "unholstered",
            },
        })
        aiming = g_render_order.build_player_cutout_rig_parts(player)
        far_arm = self.rig_part(aiming, "upper_arm", "far")
        self.assertAlmostEqual(
            far_arm["rotation"],
            run_profile[0]["torso_degrees"]
            + run_profile[0]["far_upper_arm_degrees"]
            * g_render_order.PLAYER_CUTOUT_ARM_DEFAULTS[
                "far_arm_aim_motion_scale"
            ],
        )

    def test_aimed_player_builds_authored_arm_chain_and_native_gun(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_direction": "right",
            "animation_frame": "right_frame_start",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
            "weapon_transition": {
                "progress": 1.0, "target": 1.0, "phase": "unholstered",
            },
            "procedural_gait": {"phase": 0.0, "blend": 0.0},
        }
        drawing = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        parts = drawing["draw_data"]["cutout_rig_parts"]
        self.assertEqual(len(parts), 11)
        upper_arm = self.rig_part(parts, "upper_arm", "near")
        lower_arm = self.rig_part(parts, "lower_arm", "near")
        gun = self.rig_part(parts, "gun", "near")
        self.assertEqual(upper_arm["texture"], "player_cutout_upper_arm_right")
        self.assertEqual(lower_arm["texture"], "player_cutout_lower_arm_right")
        self.assertEqual(gun["texture"], "player_cutout_gun_right")
        self.assertTrue(drawing["draw_data"]["weapon_in_cutout_rig"])
        arm_settings = g_render_order.PLAYER_CUTOUT_ARM_DEFAULTS
        shoulder = arm_settings["shoulder"]
        self.assertAlmostEqual(upper_arm["pivot_local"]["x"], shoulder["x"])
        self.assertAlmostEqual(upper_arm["pivot_local"]["y"], shoulder["y"])
        self.assertAlmostEqual(
            gun["pivot_local"]["x"],
            shoulder["x"] + arm_settings["aim_reach"],
        )
        self.assertAlmostEqual(
            gun["pivot_local"]["y"],
            shoulder["y"] + arm_settings["gun_grip_perpendicular_offset"],
        )
        self.assertAlmostEqual(upper_arm["rotation"], -90.0)
        self.assertAlmostEqual(lower_arm["rotation"], -90.0)
        self.assertAlmostEqual(gun["rotation"], 0.0)

    def test_arm_chain_bends_during_weapon_transition(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
            "weapon_transition": {
                "progress": 0.5, "target": 1.0, "phase": "unholstering",
            },
            "procedural_gait": {"phase": 0.0, "blend": 0.0},
        }
        parts = g_render_order.build_player_cutout_rig_parts(player)
        upper_arm = self.rig_part(parts, "upper_arm", "near")
        lower_arm = self.rig_part(parts, "lower_arm", "near")
        self.assertNotAlmostEqual(
            upper_arm["rotation"], lower_arm["rotation"],
        )

    def test_cutout_gun_recoil_rotates_at_fixed_grip(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
            "weapon_transition": {
                "progress": 1.0, "target": 1.0, "phase": "unholstered",
            },
            "weapon_visual_recoil": {"rotation_degrees": 14.0},
            "procedural_gait": {"phase": 0.0, "blend": 0.0},
        }
        kicked = self.rig_part(
            g_render_order.build_player_cutout_rig_parts(player),
            "gun", "near",
        )
        player["weapon_visual_recoil"]["rotation_degrees"] = 0.0
        resting = self.rig_part(
            g_render_order.build_player_cutout_rig_parts(player),
            "gun", "near",
        )
        self.assertEqual(kicked["pivot_local"], resting["pivot_local"])
        self.assertEqual(kicked["rotation"], -14.0)
        self.assertEqual(resting["rotation"], 0.0)

    def test_footstep_clock_maps_each_sound_interval_to_half_a_gait_cycle(self):
        stride = 13.0
        self.assertAlmostEqual(
            g_render_order.player_cutout_gait_phase_from_step_state(
                {"stride_index": 0, "distance": 0.0}, stride,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            g_render_order.player_cutout_gait_phase_from_step_state(
                {"stride_index": 0, "distance": stride * 0.5}, stride,
            ),
            math.pi * 0.5,
        )
        self.assertAlmostEqual(
            g_render_order.player_cutout_gait_phase_from_step_state(
                {"stride_index": 1, "distance": 0.0}, stride,
            ),
            math.pi,
        )

    def test_default_footfall_phase_is_a_split_leg_contact_pose(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {"phase": 0.0, "blend": 1.0},
        }
        parts = g_render_order.build_player_cutout_rig_parts(player)
        profile = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["walk"]
        self.assertAlmostEqual(
            self.rig_part(parts, "upper_leg", "far")["rotation"],
            profile[0]["far_upper_leg_degrees"],
        )
        self.assertAlmostEqual(
            self.rig_part(parts, "upper_leg", "near")["rotation"],
            profile[0]["near_upper_leg_degrees"],
        )

    def test_four_pose_gait_profile_hits_authored_keyframes(self):
        profile = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["walk"]
        for index, expected in enumerate(profile):
            sampled = g_render_order.sample_player_cutout_gait_profile(
                profile, math.tau * index / 4.0,
            )
            self.assertEqual(sampled, expected)

    def test_gait_profile_interpolation_is_smoothstep_and_cyclic(self):
        profile = [
            {"value": 0.0}, {"value": 8.0},
            {"value": 0.0}, {"value": -8.0},
        ]
        quarter_segment = g_render_order.sample_player_cutout_gait_profile(
            profile, math.tau / 16.0,
        )
        three_quarter_segment = g_render_order.sample_player_cutout_gait_profile(
            profile, math.tau * 3.0 / 16.0,
        )
        wrapped = g_render_order.sample_player_cutout_gait_profile(
            profile, math.tau,
        )
        self.assertAlmostEqual(quarter_segment["value"], 1.25)
        self.assertAlmostEqual(three_quarter_segment["value"], 6.75)
        self.assertEqual(wrapped, profile[0])

    def test_run_profile_can_be_selected_independently_from_walk(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {
                "phase": 0.0, "blend": 1.0, "run_blend": 1.0,
            },
        }
        parts = g_render_order.build_player_cutout_rig_parts(player)
        run_profile = g_render_order.PLAYER_CUTOUT_GAIT_PROFILES["run"]
        self.assertAlmostEqual(
            self.rig_part(parts, "upper_leg", "near")["rotation"],
            run_profile[0]["near_upper_leg_degrees"],
        )
        torso = next(
            part for part in parts
            if part["texture"] == "player_cutout_torso_right"
        )
        self.assertAlmostEqual(
            torso["rotation"], run_profile[0]["torso_degrees"],
        )

    def test_left_cutout_pose_mirrors_right_pose(self):
        player = {
            "id": "player",
            "animation_direction": "right",
            "procedural_gait": {"phase": 0.0, "blend": 1.0},
        }
        right_parts = g_render_order.build_player_cutout_rig_parts(player)
        player["animation_direction"] = "left"
        left_parts = g_render_order.build_player_cutout_rig_parts(player)
        for right, left in zip(right_parts, left_parts):
            self.assertAlmostEqual(
                right["pivot_local"]["x"] + left["pivot_local"]["x"], 32.0,
            )
            self.assertEqual(left["rotation"], -right["rotation"])
            self.assertTrue(left["flip_x"])

    def test_non_side_facing_player_keeps_sprite_fallback(self):
        player = {
            "id": "player",
            "animation_direction": "up",
            "procedural_gait": {"phase": 1.0, "blend": 1.0},
        }
        self.assertEqual(g_render_order.build_player_cutout_rig_parts(player), [])

    def test_weapon_path_is_continuous_when_transition_reverses(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_frame": "right_frame_start",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
            "weapon_transition": {
                "progress": 0.4, "target": 1.0, "phase": "unholstering",
            },
        }
        drawing = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        player["aiming"] = False
        player["weapon_transition"].update({
            "target": 0.0, "phase": "holstering",
        })
        holstering = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )

        self.assertEqual(
            drawing["draw_data"]["gun_world"],
            holstering["draw_data"]["gun_world"],
        )
        self.assertEqual(
            drawing["draw_data"]["pistol_world"],
            holstering["draw_data"]["pistol_world"],
        )

    def test_visual_recoil_rotates_pistol_without_translating_it(self):
        player = {
            "id": "player",
            "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0},
            "animation_frame": "right_frame_start",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
            "weapon_transition": {
                "progress": 1.0, "target": 1.0, "phase": "unholstered",
            },
            "weapon_visual_recoil": {
                "amount": 1.0, "rotation_degrees": 14.0,
            },
        }
        kicked = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )
        player["weapon_visual_recoil"]["rotation_degrees"] = 0.0
        resting = g_render_order.build_player_render_item(
            player, self.tile_map, self.assets,
        )

        self.assertEqual(
            kicked["draw_data"]["pistol_world"],
            resting["draw_data"]["pistol_world"],
        )
        self.assertEqual(
            kicked["draw_data"]["gun_world"],
            resting["draw_data"]["gun_world"],
        )
        self.assertEqual(kicked["draw_data"]["pistol_angle"], -14.0)
        self.assertEqual(resting["draw_data"]["pistol_angle"], 0.0)

    def test_player_occluder_requires_later_sort_and_overlap(self):
        player = {"source": "player", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}}
        behind = {"source": "buddha", "sort_y": 10.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        in_front = {"source": "buddha", "sort_y": 30.0, "bounds_world": {"x": 5.0, "y": 5.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        distant = {"source": "buddha", "sort_y": 40.0, "bounds_world": {"x": 50.0, "y": 50.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        self.assertEqual(g_render_order.find_player_occluders([behind, player, in_front, distant]), [in_front])

    def test_outline_filter_is_explicit(self):
        player = {"source": "player", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}}
        red_head = {"source": "red head", "sort_y": 30.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": False}
        self.assertEqual(g_render_order.find_player_occluders([player, red_head]), [red_head])
        self.assertEqual(g_render_order.find_player_occluders([player, red_head], require_outline=True), [])

    def test_buddha_base_line_changes_front_back_order(self):
        buddha = {"type": "buddha", "position": {"tile_x": 5, "tile_y": 5, "x": 0.0, "y": 0.0}}
        player = {"id": "player", "position": {"tile_x": 5, "tile_y": 5, "x": 0.0, "y": 0.0}}
        behind_items = g_render_order.build_sorted_world_render_items({"brains": {"b": buddha}}, player, self.tile_map, self.assets)
        self.assertEqual([item["source"] for item in behind_items], ["player", "buddha"])
        self.assertEqual([item["source"] for item in g_render_order.find_player_occluders(behind_items)], ["buddha"])
        player["position"]["y"] = 48.0
        in_front_items = g_render_order.build_sorted_world_render_items({"brains": {"b": buddha}}, player, self.tile_map, self.assets)
        self.assertEqual([item["source"] for item in in_front_items], ["buddha", "player"])
        self.assertEqual(g_render_order.find_player_occluders(in_front_items), [])

    def test_pickups_join_sorted_items_once(self):
        player = {"id": "player", "position": {"tile_x": 1, "tile_y": 1, "x": 0.0, "y": 0.0}}
        pickup = {"id": 4, "type": "health_pickup", "position": {"tile_x": 2, "tile_y": 2, "x": 0.0, "y": 0.0}}
        items = g_render_order.build_sorted_world_render_items({"brains": {}, "pickups": {4: pickup}}, player, self.tile_map, self.assets)
        pickup_items = [item for item in items if item["source_id"] == "pickups:4"]
        self.assertEqual(len(pickup_items), 1)
        self.assertEqual(pickup_items[0]["outline"]["policy"], "shared_player_occluder")

    def test_nested_policy_defaults_are_independent(self):
        first = g_render_order.make_default_entity_render_metadata("red head")
        second = g_render_order.make_default_entity_render_metadata("red head")
        first["self_shadow"]["back_fill"] = 0.5
        first["ground_footprint"]["size"]["x"] = 99.0
        self.assertEqual(second["self_shadow"]["back_fill"], 0.06)
        self.assertEqual(second["ground_footprint"]["size"]["x"], 14.0)

        first_buddha = g_render_order.make_default_entity_render_metadata("buddha")
        second_buddha = g_render_order.make_default_entity_render_metadata("buddha")
        first_buddha["self_shadow"]["response_texture"]["name"] = "changed"
        first_buddha["self_shadow"]["direction_basis"]["rect"]["x"] = 99.0
        first_buddha["self_shadow"]["direction_basis"]["ray_grid"]["columns"] = 1
        self.assertEqual(second_buddha["self_shadow"]["response_texture"]["name"], "buddha_light_response")
        self.assertEqual(second_buddha["self_shadow"]["direction_basis"]["rect"]["x"], 6.0)
        self.assertEqual(second_buddha["self_shadow"]["direction_basis"]["ray_grid"]["columns"], 7)

    def test_authored_directional_profile_metadata_is_preserved(self):
        entity = {
            "type": "buddha",
            "self_shadow": {
                "mode": "directional_profiles",
                "response_texture": {"collection": "custom", "name": "authored_response"},
                "direction_basis": {
                    "mode": "sprite_rect",
                    "rect": {"x": 7.0, "y": 80.0, "width": 100.0, "height": 30.0},
                    "ray_grid": {"columns": 5, "rows": 2},
                    "corner_blend_fraction": 0.15,
                    "maximum_adjacent_weight": 0.20
                },
                "strength": 0.67,
                "minimum_direct": 0.12,
                "fallback_mode": "none"
            }
        }
        g_render_order.ensure_entity_render_metadata(entity)
        self.assertEqual(entity["self_shadow"]["mode"], "directional_profiles")
        self.assertEqual(entity["self_shadow"]["response_texture"], {"collection": "custom", "name": "authored_response"})
        self.assertEqual(entity["self_shadow"]["direction_basis"], {
            "mode": "sprite_rect",
            "rect": {"x": 7.0, "y": 80.0, "width": 100.0, "height": 30.0},
            "ray_grid": {"columns": 5, "rows": 2},
            "corner_blend_fraction": 0.15,
            "maximum_adjacent_weight": 0.20
        })
        self.assertEqual(entity["self_shadow"]["strength"], 0.67)
        self.assertEqual(entity["self_shadow"]["minimum_direct"], 0.12)
        self.assertEqual(entity["self_shadow"]["fallback_mode"], "none")

    def test_buddha_directional_profile_defaults_and_occlusion_are_independent(self):
        metadata = g_render_order.make_default_entity_render_metadata("buddha")
        self.assertEqual(metadata["self_shadow"], {
            "mode": "directional_profiles",
            "response_texture": {"collection": "textures", "name": "buddha_light_response"},
            "direction_basis": {
                "mode": "sprite_rect",
                "rect": {"x": 6.0, "y": 86.0, "width": 110.0, "height": 36.0},
                "ray_grid": {"columns": 7, "rows": 3},
                "corner_blend_fraction": 0.20,
                "maximum_adjacent_weight": 0.50
            },
            "profile_divider": {
                "enabled": True,
                "top": {"x": 61.0, "y": 20.0},
                "bottom": {"x": 61.0, "y": 104.0}
            },
            "strength": 1.0,
            "minimum_direct": 0.04,
            "fallback_mode": "upright_box",
            "softness": 0.14,
            "back_fill": 0.04
        })
        self.assertTrue(metadata["entity_light_occluder"]["enabled"])
        self.assertTrue(metadata["entity_light_occluder"]["blocks_entity_lighting"])

    def test_red_head_remains_upright_and_non_occluding(self):
        metadata = g_render_order.make_default_entity_render_metadata("red head")
        self.assertEqual(metadata["self_shadow"]["mode"], "upright_box")
        self.assertFalse(metadata["entity_light_occluder"]["enabled"])
        self.assertFalse(metadata["entity_light_occluder"]["blocks_entity_lighting"])

    def test_failed_directional_lighting_metadata_is_retired(self):
        entity = {"type": "red head", "entity_lighting": {"front_direction_mode": "facing", "back_fill": 0.9}, "ground_footprint": {"shape": "ellipse", "offset": {"x": 0.0, "y": 0.0}, "size": {"x": 14.0, "y": 8.0}}}
        g_render_order.ensure_entity_render_metadata(entity)
        self.assertNotIn("entity_lighting", entity)
        self.assertEqual(entity["self_shadow"]["mode"], "upright_box")
        self.assertEqual(entity["ground_footprint"]["shape"], "rectangle")

    def test_shared_occluder_outlines_player_hostile_and_pickup(self):
        player = {"source_id": "player", "sort_y": 10.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}, "outline": {"policy": "player_when_occluded", "priority": 30}}
        hostile = {"source_id": "brains:h", "sort_y": 11.0, "bounds_world": {"x": 1.0, "y": 1.0, "width": 20.0, "height": 20.0}, "outline": {"policy": "shared_player_occluder", "priority": 20}}
        pickup = {"source_id": "pickups:p", "sort_y": 12.0, "bounds_world": {"x": 2.0, "y": 2.0, "width": 20.0, "height": 20.0}, "outline": {"policy": "shared_player_occluder", "priority": 10}}
        buddha = {"source_id": "brains:b", "sort_y": 20.0, "bounds_world": {"x": -5.0, "y": -5.0, "width": 40.0, "height": 40.0}, "occludes_render_items": True, "outline": {"policy": "never"}}
        outlined = g_render_order.find_items_requiring_outline([player, hostile, pickup, buddha])
        self.assertEqual({entry["item"]["source_id"] for entry in outlined}, {"player", "brains:h", "pickups:p"})

    def test_shared_outline_requires_same_player_occluder(self):
        player = {"source_id": "player", "sort_y": 10.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}, "outline": {"policy": "player_when_occluded"}}
        hostile = {"source_id": "brains:h", "sort_y": 10.0, "bounds_world": {"x": 100.0, "y": 0.0, "width": 10.0, "height": 10.0}, "outline": {"policy": "shared_player_occluder"}}
        player_wall = {"source_id": "prop:p", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}, "occludes_render_items": True, "outline": {"policy": "never"}}
        hostile_wall = {"source_id": "prop:h", "sort_y": 20.0, "bounds_world": {"x": 100.0, "y": 0.0, "width": 10.0, "height": 10.0}, "occludes_render_items": True, "outline": {"policy": "never"}}
        outlined = g_render_order.find_items_requiring_outline([player, hostile, player_wall, hostile_wall])
        self.assertEqual([entry["item"]["source_id"] for entry in outlined], ["player"])

    def test_never_policy_prop_remains_unoutlined(self):
        prop = {"source_id": "prop", "sort_y": 10.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}, "outline": {"policy": "never"}}
        wall = {"source_id": "wall", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}, "occludes_render_items": True, "outline": {"policy": "never"}}
        self.assertEqual(g_render_order.find_items_requiring_outline([prop, wall]), [])


if __name__ == "__main__":
    unittest.main()
