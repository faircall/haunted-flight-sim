import inspect
import math
import pickle
import unittest
from unittest import mock

import pyray as pr

import g_update_and_render as game


class PlayerAimHeadingTests(unittest.TestCase):
    def test_default_player_starts_aiming_right(self):
        player = game.make_default_player(0, 0, 0)
        self.assertEqual(player["aim_heading"], 0.0)
        self.assertAlmostEqual(player["aim_direction"]["x"], 1.0)
        self.assertAlmostEqual(player["aim_direction"]["y"], 0.0)
        self.assertEqual(
            player["aim_cursor_offset"],
            {"x": game.DEFAULT_AIM_CURSOR_DISTANCE, "y": 0.0},
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

    def test_interaction_no_longer_aims_at_absolute_mouse_position(self):
        source = inspect.getsource(game.update_player_interaction)
        self.assertIn("pr.get_mouse_delta()", source)
        self.assertIn("mouse_delta.y", source)
        self.assertNotIn("g_ui.get_mouse_position()", source)
        self.assertNotIn("vec2_subtract(mouse", source)

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
