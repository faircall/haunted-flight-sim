import unittest
from types import SimpleNamespace
from unittest import mock

import g_editor
import g_effects
import g_update_and_render as game


def make_map(width, height):
    return {
        "map_width": width,
        "map_height": height,
        "tile_width": 16,
        "tile_height": 16,
        "geometry_revision": 0,
        "rain_exposure_revision": 0,
        "acoustic_revision": 0,
        "tiles": [
            {"index": 0, "shape_index": index % 5}
            for index in range(width * height)
        ],
    }


class TileStrokeInterpolationTests(unittest.TestCase):
    def test_fast_horizontal_and_diagonal_lines_have_no_gaps(self):
        self.assertEqual(
            game.interpolate_tile_line((1, 3), (7, 3)),
            [(x, 3) for x in range(1, 8)],
        )
        diagonal = game.interpolate_tile_line((0, 0), (7, 4))
        self.assertEqual(diagonal[0], (0, 0))
        self.assertEqual(diagonal[-1], (7, 4))
        self.assertTrue(all(
            max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
            for a, b in zip(diagonal, diagonal[1:])
        ))

    def test_consecutive_held_frames_paint_every_intermediate_tile(self):
        tile_map = make_map(8, 1)
        state = g_editor.make_editor_state()
        with mock.patch.object(game.g_ui, "interactive_mouse_left_down", return_value=True):
            game.update_tile_editor_paint(
                state, tile_map, SimpleNamespace(x=0, y=0),
                2, 3, True, 1.0, 0, "none",
            )
            game.update_tile_editor_paint(
                state, tile_map, SimpleNamespace(x=7, y=0),
                2, 3, True, 1.0, 0, "none",
            )
        self.assertTrue(all(tile["index"] == 2 for tile in tile_map["tiles"]))
        self.assertTrue(all(tile["shape_index"] == 3 for tile in tile_map["tiles"]))
        self.assertTrue(all(tile["force_collidable"] for tile in tile_map["tiles"]))
        self.assertEqual(tile_map["geometry_revision"], 2)

    def test_property_stroke_uses_its_own_revision_only_once_per_batch(self):
        tile_map = make_map(6, 1)
        tile_map["geometry_revision"] = 9
        changed = game.paint_tile_editor_points(
            tile_map, game.interpolate_tile_line((0, 0), (5, 0)),
            "rain_exposure", rain_exposure=1.0,
        )
        self.assertEqual(changed, 6)
        self.assertEqual(tile_map["rain_exposure_revision"], 1)
        self.assertEqual(tile_map["geometry_revision"], 9)
        self.assertTrue(all(
            g_effects.get_tile_rain_exposure(tile) == 1.0
            for tile in tile_map["tiles"]
        ))


class IterativeAppearanceFloodFillTests(unittest.TestCase):
    def test_large_region_does_not_use_python_recursion(self):
        tile_map = make_map(150, 20)
        original_shapes = [tile["shape_index"] for tile in tile_map["tiles"]]
        changed = game.do_flood_fill_replace(
            0, 2, 0, 0, tile_map, 150, {}, force_collidable=True,
        )
        self.assertEqual(changed, 3000)
        self.assertEqual(tile_map["geometry_revision"], 1)
        self.assertTrue(all(tile["index"] == 2 for tile in tile_map["tiles"]))
        self.assertTrue(all(tile["force_collidable"] for tile in tile_map["tiles"]))
        self.assertEqual(
            [tile["shape_index"] for tile in tile_map["tiles"]], original_shapes,
        )

    def test_fill_is_four_connected_and_only_replaces_matching_appearance(self):
        tile_map = make_map(3, 3)
        for index, value in enumerate((0, 1, 1, 1, 0, 1, 1, 1, 0)):
            tile_map["tiles"][index]["index"] = value
        unchanged = [dict(tile) for tile in tile_map["tiles"]]
        changed = game.do_flood_fill_replace(
            0, 2, 0, 0, tile_map, 3, {}, force_collidable=False,
        )
        self.assertEqual(changed, 1)
        self.assertEqual(tile_map["tiles"][0]["index"], 2)
        self.assertEqual(tile_map["tiles"][4], unchanged[4])
        self.assertEqual(tile_map["tiles"][8], unchanged[8])
        self.assertEqual(tile_map["geometry_revision"], 1)


if __name__ == "__main__":
    unittest.main()
