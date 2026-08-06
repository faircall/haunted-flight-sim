import unittest
from types import SimpleNamespace
from unittest import mock

import pyray as pr

import g_graphics
import g_render_order
import g_update_and_render as game


class CameraRenderAlignmentTests(unittest.TestCase):
    def test_world_pixel_snap_rounds_world_and_camera_independently(self):
        camera = SimpleNamespace(x=2.6, y=3.2)
        self.assertEqual(
            g_render_order.world_to_screen_pixel(16.0, 16.0, camera),
            {"x": 13, "y": 13},
        )

    def test_fractionally_placed_entity_stays_locked_to_tiles_during_camera_motion(self):
        relative_offsets = []
        for camera_x in (2.4, 2.6, 3.4, 3.6):
            camera = SimpleNamespace(x=camera_x, y=0.0)
            tile = g_render_order.world_to_screen_pixel(0.0, 0.0, camera)
            entity = g_render_order.world_to_screen_pixel(20.25, 0.0, camera)
            relative_offsets.append(entity["x"] - tile["x"])

        self.assertEqual(relative_offsets, [20, 20, 20, 20])

    def test_moving_actor_snap_uses_relative_position_once(self):
        screen_positions = []
        for world_x, camera_x in ((100.4, -139.4), (100.6, -139.2)):
            screen_positions.append(
                g_render_order.moving_world_to_screen_pixel(
                    world_x, 40.25, SimpleNamespace(x=camera_x, y=-20.0),
                )["x"]
            )
        # Both pairs have the same 239.8-pixel relative separation. Independent
        # rounding would incorrectly produce 239 then 240.
        self.assertEqual(screen_positions, [240, 240])

    def test_tile_sprite_uses_same_camera_relative_snap_as_world_entities(self):
        camera = SimpleNamespace(x=2.6, y=3.2)
        tile_map = {
            "map_width": 1,
            "map_height": 1,
            "tile_width": 16,
            "tile_height": 16,
            "tile_types": [{"type": "stone", "color": "GREY"}],
            "tiles": [{"index": 0, "shape_index": 0}],
        }
        with mock.patch.object(game, "draw_masked_tile_texture") as draw_tile:
            game._render_world_scene_phase(
                camera, {}, tile_map, pr.Vector2(0.0, 0.0),
                0, 0, 0, False, {"textures": {"grey_tile_texture": object()}},
                False, {}, "play", [], True, False,
            )

        tile_position = draw_tile.call_args.args[1]
        expected = g_render_order.world_to_screen_pixel(0.0, 0.0, camera)
        self.assertEqual((tile_position.x, tile_position.y), (expected["x"], expected["y"]))

    def test_entity_sprite_uses_shared_camera_relative_snap(self):
        camera = SimpleNamespace(x=2.6, y=3.2)
        item = {
            "source_rect": {"x": 0.0, "y": 0.0, "width": 16.0, "height": 16.0},
            "dest_rect": {"x": 20.0, "y": 40.0, "width": 16.0, "height": 16.0},
        }
        with mock.patch.object(g_graphics.pr, "draw_texture_pro") as draw_texture:
            g_graphics._draw_render_item_main_shape(item, object(), camera)

        destination = draw_texture.call_args.args[2]
        expected = g_render_order.world_to_screen_pixel(20.0, 40.0, camera)
        self.assertEqual((destination.x, destination.y), (expected["x"], expected["y"]))

    def test_player_sprite_uses_moving_relative_snap(self):
        camera = SimpleNamespace(x=-139.4, y=3.2)
        item = {
            "source": "player",
            "screen_snap": "relative_motion",
            "source_rect": {"x": 0.0, "y": 0.0, "width": 32.0, "height": 32.0},
            "dest_rect": {"x": 100.4, "y": 40.25, "width": 32.0, "height": 32.0},
        }
        with mock.patch.object(g_graphics.pr, "draw_texture_pro") as draw_texture:
            g_graphics._draw_render_item_main_shape(item, object(), camera)

        destination = draw_texture.call_args.args[2]
        expected = g_render_order.moving_world_to_screen_pixel(100.4, 40.25, camera)
        self.assertEqual((destination.x, destination.y), (expected["x"], expected["y"]))


if __name__ == "__main__":
    unittest.main()
