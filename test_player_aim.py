import inspect
import math
import pickle
import unittest
from unittest import mock

import pyray as pr

import g_audio
import g_update_and_render as game


class PlayerAimHeadingTests(unittest.TestCase):
    def test_left_down_frame_boundary_mirrors_right_down_boundary(self):
        self.assertEqual(game.direction_from_angle(185.0), "right")
        self.assertEqual(game.direction_from_angle(185.01), "down")
        self.assertEqual(game.direction_from_angle(355.0), "left")
        self.assertEqual(game.direction_from_angle(354.99), "down")

    def test_direction_ranges_have_no_fractional_down_frame_gaps(self):
        self.assertEqual(game.direction_from_angle(44.5), "left")
        self.assertEqual(game.direction_from_angle(45.0), "up")
        self.assertEqual(game.direction_from_angle(149.5), "up")
        self.assertEqual(game.direction_from_angle(150.0), "right")

    def test_direction_selection_normalizes_wrapped_angles(self):
        self.assertEqual(game.direction_from_angle(-5.0), "left")
        self.assertEqual(game.direction_from_angle(360.0), "left")
        self.assertEqual(game.direction_from_angle(720.0), "left")

    def test_default_player_starts_aiming_right(self):
        player = game.make_default_player(0, 0, 0)
        self.assertEqual(player["aim_heading"], 0.0)
        self.assertAlmostEqual(player["aim_direction"]["x"], 1.0)
        self.assertAlmostEqual(player["aim_direction"]["y"], 0.0)
        self.assertEqual(
            player["aim_cursor_offset"],
            {"x": game.DEFAULT_AIM_CURSOR_DISTANCE, "y": 0.0},
        )
        self.assertFalse(player["aim_requested"])
        self.assertFalse(player["aiming"])
        self.assertEqual(player["weapon_transition"], {
            "progress": 0.0,
            "target": 0.0,
            "phase": "holstered",
        })
        self.assertTrue(player["flashlight_enabled"])
        self.assertTrue(player["flashlight_requested"])
        self.assertEqual(player["flashlight_transition"], {
            "progress": 1.0,
            "target": 1.0,
            "phase": "unholstered",
        })
        self.assertNotIn("weapon_transition_settings", player)

    def test_flashlight_turns_on_only_after_unholster_and_off_before_holster(self):
        player = game.make_default_player(0, 0, 0)
        player.update({
            "flashlight_requested": False,
            "flashlight_enabled": False,
            "flashlight_transition": {
                "progress": 0.0, "target": 0.0, "phase": "holstered",
            },
        })
        runtime = g_audio.make_audio_runtime()
        settings = game.get_player_flashlight_transition_settings(player)

        state = game.update_player_flashlight_transition(
            player, True, settings["unholster_duration"] * 0.5,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertAlmostEqual(state["progress"], 0.5)
        self.assertEqual(state["phase"], "unholstering")
        self.assertFalse(player["flashlight_enabled"])
        self.assertEqual(runtime["event_queue"], [])

        game.update_player_flashlight_transition(
            player, True, settings["unholster_duration"] * 0.5,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertTrue(player["flashlight_enabled"])
        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["flashlight_click"],
        )

        runtime["event_queue"].clear()
        state = game.update_player_flashlight_transition(
            player, False, settings["holster_duration"] * 0.5,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertFalse(player["flashlight_enabled"])
        self.assertAlmostEqual(state["progress"], 0.5)
        self.assertEqual(state["phase"], "holstering")
        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["flashlight_click"],
        )

    def test_reversing_partial_flashlight_draw_never_switches_beam_on(self):
        player = game.make_default_player(0, 0, 0)
        player.update({
            "flashlight_requested": False,
            "flashlight_enabled": False,
            "flashlight_transition": {
                "progress": 0.0, "target": 0.0, "phase": "holstered",
            },
        })
        runtime = g_audio.make_audio_runtime()
        settings = game.get_player_flashlight_transition_settings(player)
        game.update_player_flashlight_transition(
            player, True, settings["unholster_duration"] * 0.6,
            runtime, {"x": 0.0, "y": 0.0},
        )
        state = game.update_player_flashlight_transition(
            player, False, settings["holster_duration"] * 0.6,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertEqual(state["progress"], 0.0)
        self.assertFalse(player["flashlight_enabled"])
        self.assertEqual(runtime["event_queue"], [])

    def test_reload_holsters_and_restores_a_requested_flashlight(self):
        player = game.make_default_player(0, 0, 0)
        runtime = g_audio.make_audio_runtime()
        settings = game.get_player_flashlight_transition_settings(player)

        self.assertTrue(game.update_player_reload(
            player, "pistol", True, 0.05, runtime,
            {"x": 0.0, "y": 0.0},
        ))
        animation = player["reload_animation"]
        self.assertTrue(animation["restore_flashlight"])
        self.assertAlmostEqual(animation["start_flashlight_progress"], 1.0)
        self.assertAlmostEqual(
            animation["flashlight_holster_reload_fraction"],
            settings["holster_duration"] / game.get_reload_time("pistol"),
        )
        self.assertFalse(player["flashlight_requested"])
        self.assertFalse(player["flashlight_enabled"])
        self.assertEqual(player["flashlight_transition"]["target"], 0.0)
        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["reload_start", "flashlight_click"],
        )

        # F is ignored while reload owns both hands; it cannot cancel the
        # stored intent to restore the previously active light.
        with mock.patch.object(game.pr, "is_key_pressed", return_value=True):
            game.update_player_flashlight_toggle(
                player, "play", "unpaused", runtime,
                settings["holster_duration"],
                {"tile_width": 16, "tile_height": 16},
            )
        self.assertEqual(player["flashlight_transition"]["progress"], 0.0)
        self.assertFalse(player["flashlight_requested"])
        self.assertTrue(player["reload_animation"]["restore_flashlight"])

        self.assertFalse(game.update_player_reload(
            player, "pistol", False, game.get_reload_time("pistol"), runtime,
            {"x": 0.0, "y": 0.0},
        ))
        self.assertTrue(player["flashlight_requested"])
        self.assertFalse(player["flashlight_enabled"])
        self.assertEqual(player["flashlight_transition"]["target"], 1.0)
        self.assertEqual(
            player["flashlight_transition"]["phase"], "unholstering",
        )

        with mock.patch.object(game.pr, "is_key_pressed", return_value=False):
            game.update_player_flashlight_toggle(
                player, "play", "unpaused", runtime,
                settings["unholster_duration"],
                {"tile_width": 16, "tile_height": 16},
            )
        self.assertTrue(player["flashlight_enabled"])
        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]].count(
                "flashlight_click"
            ),
            2,
        )

    def test_reload_does_not_accept_a_new_flashlight_toggle(self):
        player = game.make_default_player(0, 0, 0)
        player.update({
            "flashlight_requested": False,
            "flashlight_enabled": False,
            "flashlight_transition": {
                "progress": 0.0, "target": 0.0, "phase": "holstered",
            },
        })
        runtime = g_audio.make_audio_runtime()
        game.update_player_reload(
            player, "pistol", True, 0.0, runtime, {"x": 0.0, "y": 0.0},
        )
        with mock.patch.object(game.pr, "is_key_pressed", return_value=True):
            game.update_player_flashlight_toggle(
                player, "play", "unpaused", runtime, 0.1,
                {"tile_width": 16, "tile_height": 16},
            )
        self.assertFalse(player["flashlight_requested"])
        self.assertFalse(player["reload_animation"]["restore_flashlight"])

        game.update_player_reload(
            player, "pistol", False, game.get_reload_time("pistol"), runtime,
            {"x": 0.0, "y": 0.0},
        )
        self.assertFalse(player["flashlight_requested"])
        self.assertEqual(player["flashlight_transition"]["target"], 0.0)

    def test_live_transition_defaults_are_not_pinned_to_player_state(self):
        player = game.make_default_player(0, 0, 0)
        with mock.patch.dict(
                game.PLAYER_WEAPON_TRANSITION_DEFAULTS,
                {"unholster_duration": 0.91}):
            self.assertEqual(
                game.get_player_weapon_transition_settings(player)[
                    "unholster_duration"
                ],
                0.91,
            )

        player["weapon_transition_overrides"] = {"holster_duration": 0.44}
        with mock.patch.dict(
                game.PLAYER_WEAPON_TRANSITION_DEFAULTS,
                {"unholster_duration": 0.82}):
            settings = game.get_player_weapon_transition_settings(player)
        self.assertEqual(settings["unholster_duration"], 0.82)
        self.assertEqual(settings["holster_duration"], 0.44)

    def test_legacy_copied_transition_settings_are_retired(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition_settings"] = {
            "unholster_duration": 99.0,
        }

        game.ensure_player_weapon_transition_state(player)

        self.assertNotIn("weapon_transition_settings", player)
        self.assertEqual(
            game.get_player_weapon_transition_settings(player)[
                "unholster_duration"
            ],
            game.PLAYER_WEAPON_TRANSITION_DEFAULTS["unholster_duration"],
        )

    def test_weapon_transition_reaches_both_normalized_endpoints(self):
        player = game.make_default_player(0, 0, 0)
        runtime = g_audio.make_audio_runtime()
        settings = game.get_player_weapon_transition_settings(player)

        state = game.update_player_weapon_transition(
            player, True, settings["unholster_duration"] * 0.5,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertAlmostEqual(state["progress"], 0.5)
        self.assertEqual(state["phase"], "unholstering")
        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["sound_instance_stop", "weapon_unholster"],
        )

        runtime["event_queue"].clear()
        state = game.update_player_weapon_transition(
            player, True, settings["unholster_duration"] * 0.5,
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertEqual(state["progress"], 1.0)
        self.assertEqual(state["phase"], "unholstered")
        self.assertEqual(runtime["event_queue"], [])

        state = game.update_player_weapon_transition(
            player, False, settings["holster_duration"],
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertEqual(state["progress"], 0.0)
        self.assertEqual(state["phase"], "holstered")

    def test_aim_mode_is_not_ready_until_unholster_finishes(self):
        player = game.make_default_player(0, 0, 0)
        runtime = g_audio.make_audio_runtime()
        duration = game.get_player_weapon_transition_settings(player)[
            "unholster_duration"
        ]
        player["aim_requested"] = True

        game.update_player_weapon_transition(
            player, True, duration * 0.5, runtime,
            {"x": 0.0, "y": 0.0},
        )
        self.assertFalse(game.player_weapon_is_ready(player))

        game.update_player_weapon_transition(
            player, True, duration * 0.5, runtime,
            {"x": 0.0, "y": 0.0},
        )
        self.assertTrue(game.player_weapon_is_ready(player))

        player["aim_requested"] = False
        game.update_player_weapon_transition(
            player, False, 0.0, runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertFalse(game.player_weapon_is_ready(player))

    def test_brief_aim_release_stops_unholster_without_holster_tail(self):
        player = game.make_default_player(0, 0, 0)
        runtime = g_audio.make_audio_runtime()
        game.update_player_weapon_transition(
            player, True, 0.02, runtime, {"x": 0.0, "y": 0.0},
        )
        runtime["event_queue"].clear()

        game.update_player_weapon_transition(
            player, False, 0.01, runtime, {"x": 0.0, "y": 0.0},
        )

        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["sound_instance_stop"],
        )

    def test_meaningful_reversal_seeks_into_opposite_sound(self):
        player = game.make_default_player(0, 0, 0)
        runtime = g_audio.make_audio_runtime()
        duration = game.get_player_weapon_transition_settings(player)[
            "unholster_duration"
        ]
        game.update_player_weapon_transition(
            player, True, duration * 0.5, runtime,
            {"x": 0.0, "y": 0.0},
        )
        runtime["event_queue"].clear()

        game.update_player_weapon_transition(
            player, False, 0.0, runtime, {"x": 0.0, "y": 0.0},
        )

        self.assertEqual(
            [event["type"] for event in runtime["event_queue"]],
            ["sound_instance_stop", "weapon_holster"],
        )
        self.assertAlmostEqual(
            runtime["event_queue"][1]["data"]["start_fraction"], 0.5,
        )

    def test_legacy_aim_vector_migrates_to_heading(self):
        player = {"aim_direction": {"x": 0.0, "y": 20.0}}
        direction = game.ensure_player_aim_state(player)
        self.assertAlmostEqual(player["aim_heading"], 90.0)
        self.assertAlmostEqual(direction["x"], 0.0, places=7)
        self.assertAlmostEqual(direction["y"], 1.0, places=7)

    def test_relative_turn_accumulates_and_wraps(self):
        player = {"aim_heading": 350.0}
        game.apply_player_aim_turn(player, 25.0)
        self.assertAlmostEqual(player["aim_heading"], 15.0)
        game.apply_player_aim_turn(player, -30.0)
        self.assertAlmostEqual(player["aim_heading"], 345.0)

    def test_horizontal_and_vertical_deltas_move_current_virtual_cursor(self):
        player = game.make_default_player(0, 0, 0)
        game.apply_player_aim_cursor_delta(player, 0.0, 72.0)
        self.assertEqual(player["aim_cursor_offset"], {"x": 72.0, "y": 72.0})
        self.assertAlmostEqual(player["aim_heading"], 45.0)

        game.apply_player_aim_cursor_delta(player, -72.0, 0.0)
        self.assertEqual(player["aim_cursor_offset"], {"x": 0.0, "y": 72.0})
        self.assertAlmostEqual(player["aim_heading"], 90.0)

    def test_mouse_delta_uses_both_axes_and_authored_sensitivity(self):
        player = game.make_default_player(0, 0, 0)
        player["mouse_aim_sensitivity"] = 0.5
        game.apply_player_mouse_aim_delta(player, -24.0, 20.0)
        self.assertEqual(player["aim_cursor_offset"], {"x": 60.0, "y": 10.0})
        self.assertAlmostEqual(player["aim_heading"], math.degrees(math.atan2(10.0, 60.0)))

    def test_window_mouse_delta_is_scaled_to_internal_resolution(self):
        delta = game.scale_mouse_delta_to_internal(40.0, 20.0, 1920, 1080)
        self.assertEqual(delta, {"x": 10.0, "y": 5.0})

    def test_virtual_cursor_is_clamped_without_changing_its_direction(self):
        player = game.make_default_player(0, 0, 0)
        game.apply_player_aim_cursor_delta(player, 1000.0, 1000.0)
        cursor = player["aim_cursor_offset"]
        self.assertAlmostEqual(
            math.hypot(cursor["x"], cursor["y"]), game.MAX_AIM_CURSOR_DISTANCE,
        )
        self.assertAlmostEqual(player["aim_heading"], math.degrees(math.atan2(cursor["y"], cursor["x"])))

    def test_direction_remains_unit_length(self):
        player = {"aim_heading": 0.0}
        for turn in (1.25, 97.0, -31.5, 720.0):
            direction = game.apply_player_aim_turn(player, turn)
            self.assertAlmostEqual(math.hypot(direction["x"], direction["y"]), 1.0)

    def test_heading_is_serialisable_persistent_gameplay_state(self):
        player = game.make_default_player(0, 0, 0)
        game.apply_player_aim_turn(player, 123.5)
        restored = pickle.loads(pickle.dumps(player))
        self.assertAlmostEqual(restored["aim_heading"], 123.5)
        self.assertEqual(restored["aim_direction"], player["aim_direction"])
        self.assertEqual(restored["aim_cursor_offset"], player["aim_cursor_offset"])

    def test_aim_cursor_uses_heading_and_camera_only_for_projection(self):
        player = game.make_default_player(0, 0, 0)
        player["position"].update({"tile_x": 10, "tile_y": 8, "x": 3.0, "y": 5.0})
        game.apply_player_aim_turn(player, 90.0)
        cursor = game.get_player_aim_cursor_screen_position(
            player, {"tile_width": 16, "tile_height": 16}, pr.Vector3(20.0, 30.0, 0.0),
        )
        self.assertAlmostEqual(cursor.x, 143.0)
        self.assertAlmostEqual(cursor.y, 175.0)
        self.assertAlmostEqual(player["aim_heading"], 90.0)

    def test_cursor_outline_only_draws_once_quick_draw_can_fire(self):
        player = game.make_default_player(0, 0, 0)
        tile_map = {"tile_width": 16, "tile_height": 16}
        camera = pr.Vector3(0.0, 0.0, 0.0)
        with mock.patch.object(game.pr, "draw_circle_lines") as outline, \
                mock.patch.object(game.pr, "draw_circle") as center:
            game.draw_player_aim_cursor(player, tile_map, camera)
            outline.assert_not_called()
            center.assert_called_once()

            player["aim_requested"] = True
            player["aiming"] = True
            player["weapon_transition"].update({
                "progress": game.PLAYER_AIM_ACCURACY_DEFAULTS[
                    "minimum_fire_progress"
                ],
                "target": 1.0,
                "phase": "unholstering",
            })
            game.draw_player_aim_cursor(player, tile_map, camera)
            outline.assert_called_once()
            self.assertGreater(outline.call_args.args[2], 3.0)
            self.assertEqual(center.call_count, 2)

    def test_player_collision_debug_item_uses_movement_box(self):
        player = game.make_default_player(3.0, 5.0, 0.0)
        player["position"].update({"tile_x": 10, "tile_y": 8})
        tile_map = {"tile_width": 16, "tile_height": 16}
        item = game.make_player_collision_debug_item(player, tile_map)
        self.assertEqual({
            key: item[key] for key in ("x", "y", "width", "height")
        }, {
            "x": 157.0, "y": 127.0, "width": 12.0, "height": 12.0,
        })
        self.assertEqual(item["color"], "BLUE")
        self.assertIn("player_debug", item["debug_modes"])
        self.assertIn("dumb entities", item["debug_modes"])
        self.assertIs(item["drawing_function"], game.draw_debug_rect_outline)

    def test_interaction_no_longer_aims_at_absolute_mouse_position(self):
        source = inspect.getsource(game.update_player_interaction)
        self.assertIn("pr.get_mouse_delta()", source)
        self.assertIn("mouse_delta.y", source)
        self.assertNotIn("g_ui.get_mouse_position()", source)
        self.assertNotIn("vec2_subtract(mouse", source)
        self.assertIn("player_weapon_can_fire", source)
        self.assertIn("player_weapon_bezier_world_position", source)
        self.assertIn("sample_player_shot_direction", source)
        self.assertLess(
            source.index("sample_player_shot_direction"),
            source.index("apply_player_shot_recoil_bloom"),
        )
        self.assertLess(
            source.index("roll_player_headshot_qualification"),
            source.index("apply_player_shot_recoil_bloom"),
        )

    def test_quick_draw_can_fire_before_weapon_is_fully_ready(self):
        player = game.make_default_player(0, 0, 0)
        player["aim_requested"] = True
        minimum = game.get_player_aim_accuracy_settings(player)[
            "minimum_fire_progress"
        ]
        player["weapon_transition"].update({
            "progress": minimum * 0.5,
            "target": 1.0,
            "phase": "unholstering",
        })
        self.assertFalse(game.player_weapon_can_fire(player))

        player["weapon_transition"]["progress"] = minimum
        self.assertTrue(game.player_weapon_can_fire(player))
        self.assertFalse(game.player_weapon_is_ready(player))

    def test_reload_blocks_aim_readiness_and_firing_until_complete(self):
        player = game.make_default_player(0, 0, 0)
        player["ammo"].update({"pistol": 4, "spare_pistol": 30})
        player["aim_requested"] = True
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        runtime = g_audio.make_audio_runtime()

        active = game.update_player_reload(
            player, "pistol", True, 0.0, runtime,
            {"x": 0.0, "y": 0.0},
        )
        self.assertTrue(active)
        self.assertEqual(
            player["reload_animation"]["start_weapon_progress"], 1.0,
        )
        self.assertEqual(
            player["reload_animation"]["start_aim_direction"],
            {"x": 1.0, "y": 0.0},
        )
        self.assertFalse(game.player_weapon_can_fire(player, True))
        self.assertFalse(game.player_weapon_is_ready(player, True))
        game.update_player_weapon_transition(
            player, False,
            game.get_player_weapon_transition_settings(player)[
                "holster_duration"
            ],
            runtime, {"x": 0.0, "y": 0.0},
        )

        active = game.update_player_reload(
            player, "pistol", False, game.get_reload_time("pistol"),
            runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertFalse(active)
        self.assertEqual(player["reload_state"], "reloaded")
        self.assertEqual(player["ammo"]["pistol"], 20)
        self.assertEqual(player["ammo"]["spare_pistol"], 14)

        # Held raw aim is converted back to effective aim by the interaction
        # update, which then follows this ordinary unholster path.
        player["aim_requested"] = True
        game.update_player_weapon_transition(
            player, True, 0.01, runtime, {"x": 0.0, "y": 0.0},
        )
        self.assertEqual(player["weapon_transition"]["target"], 1.0)
        self.assertEqual(player["weapon_transition"]["phase"], "unholstering")

    def test_reload_disables_active_reticle_outline(self):
        player = game.make_default_player(0, 0, 0)
        player["aim_requested"] = True
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        player["reload_state"] = "reloading"
        with mock.patch.object(game.pr, "draw_circle_lines") as outline, \
                mock.patch.object(game.pr, "draw_circle") as center:
            game.draw_player_aim_cursor(
                player, {"tile_width": 16, "tile_height": 16},
                pr.Vector3(0.0, 0.0, 0.0),
            )
        outline.assert_not_called()
        center.assert_called_once()

    def test_held_aim_restarts_unholster_when_reload_finishes(self):
        player = game.make_default_player(8.0, 8.0, 0.0)
        player["aim_requested"] = True
        player["aiming"] = True
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        runtime = g_audio.make_audio_runtime()
        tile_map = game.make_tile_map(8, 8, 16, 16)

        with mock.patch.object(
                game.pr, "is_mouse_button_down", return_value=True), \
                mock.patch.object(
                    game.pr, "is_mouse_button_pressed", return_value=False,
                ), \
                mock.patch.object(
                    game.pr, "is_key_pressed", return_value=True,
                ), \
                mock.patch.object(game.pr, "draw_text"):
            game.update_player_interaction(
                tile_map, player, pr.Vector3(0.0, 0.0, 0.0), {}, runtime,
                0.01, "clear", None, aim_input_enabled=False,
                mouse_delta=pr.Vector2(0.0, 0.0),
            )
        self.assertTrue(game.player_is_reloading(player))
        self.assertFalse(player["aim_requested"])
        self.assertFalse(player["weapon_can_fire"])
        self.assertEqual(player["weapon_transition"]["target"], 0.0)
        self.assertNotIn(
            "weapon_holster",
            [event["type"] for event in runtime["event_queue"]],
        )

        # The long reload would have completed the silent lowering transition.
        player["weapon_transition"].update({
            "progress": 0.0, "target": 0.0, "phase": "holstered",
        })
        player["reload_timer"] = game.get_reload_time("pistol") - 0.01
        runtime["event_queue"].clear()
        with mock.patch.object(
                game.pr, "is_mouse_button_down", return_value=True), \
                mock.patch.object(
                    game.pr, "is_mouse_button_pressed", return_value=False,
                ), \
                mock.patch.object(
                    game.pr, "is_key_pressed", return_value=False,
                ), \
                mock.patch.object(game.pr, "draw_text"):
            game.update_player_interaction(
                tile_map, player, pr.Vector3(0.0, 0.0, 0.0), {}, runtime,
                0.01, "clear", None, aim_input_enabled=False,
                mouse_delta=pr.Vector2(0.0, 0.0),
            )
        self.assertEqual(player["reload_state"], "reloaded")
        self.assertTrue(player["aim_requested"])
        self.assertEqual(player["weapon_transition"]["target"], 1.0)
        self.assertEqual(player["weapon_transition"]["phase"], "unholstering")
        self.assertIn(
            "weapon_unholster",
            [event["type"] for event in runtime["event_queue"]],
        )

    def test_interaction_spawns_quick_draw_shot_at_minimum_progress(self):
        tile_map = game.make_tile_map(8, 8, 16, 16)
        minimum = game.PLAYER_AIM_ACCURACY_DEFAULTS[
            "minimum_fire_progress"
        ]

        def interact_at_progress(progress):
            player = game.make_default_player(8.0, 8.0, 0.0)
            player["weapon_transition"].update({
                "progress": progress,
                "target": 1.0,
                "phase": "unholstering",
            })
            entities = {}
            with mock.patch.object(
                    game.pr, "is_mouse_button_down", return_value=True), \
                    mock.patch.object(
                        game.pr, "is_mouse_button_pressed", return_value=True,
                    ), \
                    mock.patch.object(
                        game.pr, "is_key_pressed", return_value=False,
                    ), \
                    mock.patch.object(game.pr, "draw_text"):
                game.update_player_interaction(
                    tile_map, player, pr.Vector3(0.0, 0.0, 0.0), entities,
                    g_audio.make_audio_runtime(), 0.0, "clear", None,
                    aim_input_enabled=False, mouse_delta=pr.Vector2(0.0, 0.0),
                )
            return entities, player

        blocked_entities, blocked_player = interact_at_progress(minimum * 0.5)
        self.assertNotIn("projectiles", blocked_entities)
        self.assertIsNone(blocked_player["muzzle_flash"]["light"])

        fired_entities, fired_player = interact_at_progress(minimum)
        projectiles = fired_entities["projectiles"]
        self.assertEqual(len(projectiles), 1)
        self.assertIsNotNone(fired_player["muzzle_flash"]["light"])

    def test_unholster_bloom_recovers_independently_from_animation(self):
        player = game.make_default_player(0, 0, 0)
        player["aim_accuracy_overrides"] = {
            "bloom_unholster_recovery": 0.4,
        }
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        self.assertEqual(game.get_player_transition_instability(player), 1.0)

        game.update_player_aim_accuracy(player, True, 0.1)
        self.assertEqual(player["weapon_transition"]["progress"], 1.0)
        self.assertAlmostEqual(
            player["aim_accuracy"]["unholster_instability"], 0.75,
        )
        self.assertGreater(game.get_player_transition_instability(player), 0.0)

        for _ in range(3):
            game.update_player_aim_accuracy(player, True, 0.1)
        self.assertEqual(game.get_player_transition_instability(player), 0.0)

        game.update_player_aim_accuracy(player, False, 0.01)
        self.assertEqual(game.get_player_transition_instability(player), 1.0)

    def test_motion_and_transition_instability_combine_without_simple_clamp(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition"].update({
            "progress": 0.5, "target": 1.0,
        })
        player["aim_accuracy"].update({
            "motion_instability": 0.5,
            "unholster_instability": 0.5,
        })
        self.assertAlmostEqual(
            game.get_player_total_aim_instability(player), 0.75,
        )

    def test_transition_and_motion_have_independent_visual_and_spread_caps(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition"].update({
            "progress": 0.0, "target": 1.0,
        })
        player["aim_accuracy"].update({
            "motion_instability": 0.0,
            "unholster_instability": 1.0,
        })
        self.assertEqual(game.get_player_accuracy_reticle_radius(player), 12.0)
        self.assertEqual(game.get_player_maximum_shot_deviation(player), 10.0)

        player["weapon_transition"]["progress"] = 1.0
        player["aim_accuracy"].update({
            "motion_instability": 1.0,
            "unholster_instability": 0.0,
        })
        self.assertEqual(game.get_player_accuracy_reticle_radius(player), 8.0)
        self.assertEqual(game.get_player_maximum_shot_deviation(player), 6.0)

    def test_headshot_qualification_uses_reticle_box_and_pre_shot_bloom(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        player = game.make_default_player(0, 0, 0)
        target = {
            "id": 7,
            "type": "red head",
            "position": {"tile_x": 4, "tile_y": 4, "x": 2.0, "y": 2.0},
            "current_state": "idle",
        }
        game.give_entity_stats_from_type(target, "red head")
        headshot_box = game.get_redhead_headshot_box(target, tile_map)
        player["aim_cursor_offset"] = {
            "x": headshot_box["x"] + headshot_box["width"] * 0.5,
            "y": headshot_box["y"] + headshot_box["height"] * 0.5,
        }
        player["aim_accuracy"].update({
            "motion_instability": 0.0,
            "shot_instability": 0.0,
            "unholster_instability": 0.0,
        })
        rng = mock.Mock()

        perfect = game.roll_player_headshot_qualification(
            player, {target["id"]: target}, tile_map, rng,
        )
        self.assertTrue(perfect["qualified"])
        self.assertEqual(perfect["target_id"], target["id"])
        self.assertEqual(perfect["chance"], 1.0)
        rng.random.assert_not_called()

        player["aim_accuracy"]["shot_instability"] = 0.5
        rng.random.return_value = 0.49
        bloomed_success = game.roll_player_headshot_qualification(
            player, {target["id"]: target}, tile_map, rng,
        )
        self.assertAlmostEqual(bloomed_success["chance"], 0.5)
        self.assertTrue(bloomed_success["qualified"])

        rng.random.return_value = 0.51
        bloomed_failure = game.roll_player_headshot_qualification(
            player, {target["id"]: target}, tile_map, rng,
        )
        self.assertFalse(bloomed_failure["qualified"])
        self.assertIsNone(bloomed_failure["target_id"])

        player["aim_cursor_offset"]["y"] = headshot_box["y"] - 0.01
        outside = game.roll_player_headshot_qualification(
            player, {target["id"]: target}, tile_map, rng,
        )
        self.assertIsNone(outside["candidate_id"])

    def test_shot_recoil_adds_bloom_for_followup_shots_and_caps(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        player["aim_accuracy"]["unholster_instability"] = 0.0
        recoil = game.get_player_aim_accuracy_settings(player)[
            "recoil_bloom_per_shot"
        ]

        first = game.apply_player_shot_recoil_bloom(player)
        self.assertEqual(first, recoil)
        self.assertGreater(game.get_player_accuracy_reticle_radius(player), 3.0)
        self.assertGreater(game.get_player_maximum_shot_deviation(player), 0.0)

        for _ in range(10):
            game.apply_player_shot_recoil_bloom(player)
        self.assertEqual(player["aim_accuracy"]["shot_instability"], 1.0)
        self.assertEqual(game.get_player_accuracy_reticle_radius(player), 8.0)
        self.assertEqual(game.get_player_maximum_shot_deviation(player), 6.0)

    def test_shot_and_motion_bloom_recover_independently(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        player["aim_accuracy"].update({
            "motion_instability": 1.0,
            "shot_instability": 1.0,
        })
        player["aim_accuracy_overrides"] = {
            "bloom_motion_recovery": 1.0,
            "bloom_shot_recovery": 2.0,
        }

        game.update_player_aim_accuracy(player, False, 0.1)

        self.assertAlmostEqual(
            player["aim_accuracy"]["motion_instability"], 0.9,
        )
        self.assertAlmostEqual(
            player["aim_accuracy"]["shot_instability"], 0.95,
        )

    def test_visual_recoil_has_independent_kick_and_return_settings(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_visual_recoil_overrides"] = {
            "kick_degrees": 20.0,
            "return_seconds": 0.4,
        }

        self.assertEqual(game.apply_player_weapon_visual_recoil(player), 20.0)
        self.assertEqual(player["weapon_visual_recoil"]["amount"], 1.0)
        self.assertEqual(player["aim_accuracy"]["shot_instability"], 0.0)

        game.update_player_weapon_visual_recoil(player, 0.1)
        self.assertAlmostEqual(player["weapon_visual_recoil"]["amount"], 0.75)
        self.assertAlmostEqual(
            player["weapon_visual_recoil"]["rotation_degrees"], 11.25,
        )
        self.assertEqual(player["aim_accuracy"]["shot_instability"], 0.0)

    def test_muzzle_flash_uses_transient_visual_only_light(self):
        player = game.make_default_player(0, 0, 0)
        player["muzzle_flash_overrides"] = {
            "duration_seconds": 0.2,
            "radius": 80.0,
            "intensity": 3.0,
            "fade_exponent": 1.0,
        }

        light = game.trigger_player_muzzle_flash(
            player, {"x": 12.0, "y": 34.0}, {"x": 0.0, "y": 1.0},
        )
        self.assertEqual(light["position"], {"x": 12.0, "y": 34.0})
        self.assertEqual(light["radius"], 80.0)
        self.assertEqual(light["intensity"], 3.0)
        self.assertFalse(light["affects_ai"])
        self.assertEqual(light["gameplay_intensity"], 0.0)
        self.assertEqual(player["aim_accuracy"]["shot_instability"], 0.0)
        self.assertEqual(player["weapon_visual_recoil"]["amount"], 0.0)
        flame = game.build_player_muzzle_flash_emitter(player)
        self.assertEqual(flame["type"], "fire")
        self.assertEqual(flame["position"], {"x": 12.0, "y": 34.0})
        self.assertEqual(flame["direction"], {"x": 0.0, "y": 1.0})
        self.assertEqual(flame["size"], {"x": 5.0, "y": 9.0})
        self.assertEqual(flame["ember_density"], 0.0)
        self.assertFalse(flame["light"]["enabled"])
        self.assertLess(flame["palette"]["core"][2], 0.5)

        player.update({
            "position": {"x": 10.0, "y": 20.0},
            "animation_direction": "right",
            "aim_direction": {"x": 1.0, "y": 0.0},
            "aiming": True,
        })
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        # The rendered gun has already kicked when the flash is drawn.  The
        # discharge itself must still use the shot/reticle direction rather
        # than inheriting that visual rotation.
        player["weapon_visual_recoil"]["rotation_degrees"] = 14.0
        barrel = game.g_render_order.player_cutout_gun_barrel_world(
            player, {"tile_width": 16, "tile_height": 16},
        )
        attached_flame = game.build_player_muzzle_flash_emitter(
            player, {"tile_width": 16, "tile_height": 16},
        )
        self.assertEqual(attached_flame["position"], barrel["position"])
        self.assertEqual(attached_flame["direction"], {"x": 1.0, "y": 0.0})
        self.assertNotAlmostEqual(barrel["direction"]["y"], 0.0)
        self.assertEqual(
            player["muzzle_flash"]["light"]["position"], barrel["position"],
        )

        records = game.g_graphics.collect_light_records(
            {}, player, game.make_tile_map(4, 4, 16, 16), {},
        )
        flash_record = next(
            record for record in records
            if record["id"] == "runtime:player_muzzle_flash"
        )
        self.assertEqual(flash_record["light"]["intensity"], 3.0)

        game.update_player_muzzle_flash(player, 0.1)
        self.assertAlmostEqual(player["muzzle_flash"]["light"]["intensity"], 1.5)
        self.assertIsNotNone(game.build_player_muzzle_flash_emitter(player))
        game.update_player_muzzle_flash(player, 0.1)
        self.assertIsNone(player["muzzle_flash"]["light"])
        self.assertIsNone(game.build_player_muzzle_flash_emitter(player))

    def test_muzzle_flame_stays_on_flashlight_cone_centreline(self):
        tile_map = {"tile_width": 16, "tile_height": 16}
        aims = {
            "right": {"x": 1.0, "y": 0.0},
            "left": {"x": -1.0, "y": 0.0},
            "up": {"x": 0.0, "y": -1.0},
            "down": {"x": 0.0, "y": 1.0},
        }
        for facing, aim in aims.items():
            player = game.make_default_player(100.0, 100.0, 0.0)
            player.update({
                "animation_direction": facing,
                "aim_direction": dict(aim),
                "aiming": True,
                "flashlight_enabled": True,
            })
            player["weapon_transition"].update({
                "progress": 1.0, "target": 1.0,
                "phase": "unholstered",
            })
            game.trigger_player_muzzle_flash(
                player, {"x": 100.0, "y": 100.0}, aim,
            )

            flashlight = game.g_graphics.make_player_flashlight(
                player, tile_map,
            )
            flame = game.build_player_muzzle_flash_emitter(player, tile_map)
            from_flashlight = {
                "x": flame["position"]["x"] - flashlight["position"]["x"],
                "y": flame["position"]["y"] - flashlight["position"]["y"],
            }
            lateral_distance = abs(
                from_flashlight["x"] * aim["y"]
                - from_flashlight["y"] * aim["x"]
            )

            # The cone now originates from the flashlight in the spare hand,
            # rather than the player centre. It remains close and parallel to
            # the pistol flash while preserving distinct hand placement. A
            # missing (-16, -16) player render anchor violates this heavily.
            self.assertLessEqual(lateral_distance, 8.0, msg=facing)
            self.assertAlmostEqual(flame["direction"]["x"], aim["x"])
            self.assertAlmostEqual(flame["direction"]["y"], aim["y"])

    def test_fast_turn_blooms_more_than_slow_turn_and_then_recovers(self):
        slow = game.make_default_player(0, 0, 0)
        game.apply_player_aim_turn(slow, 0.2)
        game.update_player_aim_accuracy(slow, True, 1.0 / 60.0)

        fast = game.make_default_player(0, 0, 0)
        game.apply_player_aim_turn(fast, 20.0)
        game.update_player_aim_accuracy(fast, True, 1.0 / 60.0)
        bloomed = fast["aim_accuracy"]["motion_instability"]

        self.assertGreater(
            bloomed, slow["aim_accuracy"]["motion_instability"],
        )
        game.update_player_aim_accuracy(fast, True, 0.16)
        self.assertLess(fast["aim_accuracy"]["motion_instability"], bloomed)

    def test_perfect_accuracy_is_exact_and_bloomed_spread_is_bounded(self):
        player = game.make_default_player(0, 0, 0)
        player["weapon_transition"].update({
            "progress": 1.0, "target": 1.0, "phase": "unholstered",
        })
        player["aim_accuracy"]["unholster_instability"] = 0.0
        random_source = mock.Mock()
        exact = game.sample_player_shot_direction(
            player, {"x": 1.0, "y": 0.0}, random_source,
        )
        self.assertEqual(exact, {"x": 1.0, "y": 0.0})
        random_source.triangular.assert_not_called()

        player["aim_accuracy"]["unholster_instability"] = 1.0
        random_source.triangular.return_value = 6.0
        spread = game.sample_player_shot_direction(
            player, {"x": 1.0, "y": 0.0}, random_source,
        )
        random_source.triangular.assert_called_once_with(-10.0, 10.0, 0.0)
        self.assertAlmostEqual(
            game.aim_heading_from_direction(spread), 6.0,
        )

    def test_relative_mouse_capture_transitions_once_and_suppresses_jump(self):
        assets = {}
        with mock.patch.object(game.pr, "disable_cursor") as disable, \
                mock.patch.object(game.pr, "enable_cursor") as enable, \
                mock.patch.object(game.pr, "hide_cursor") as hide:
            self.assertTrue(game.update_play_mouse_capture(assets, True))
            self.assertTrue(game.update_play_mouse_capture(assets, True))
            disable.assert_called_once_with()
            self.assertTrue(assets["suppress_aim_mouse_delta_once"])
            self.assertFalse(game.update_play_mouse_capture(assets, False))
            enable.assert_called_once_with()
            hide.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
