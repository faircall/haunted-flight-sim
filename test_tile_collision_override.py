import pickle
import unittest
from unittest import mock

import g_update_and_render as game


class TileCollisionOverrideTests(unittest.TestCase):
    def make_map(self, width=3, height=3):
        return game.make_tile_map(width, height, 10, 10)

    def tile(self, tile_map, x, y):
        return tile_map["tiles"][y * tile_map["map_width"] + x]

    def test_non_collidable_art_can_be_forced_solid_per_placed_tile(self):
        tile_map = self.make_map()
        carpet = self.tile(tile_map, 1, 1)
        carpet["index"] = 1
        self.assertFalse(game.tile_is_collidable(carpet, tile_map))
        game.set_tile_force_collidable(carpet, True)
        self.assertTrue(game.tile_is_collidable(carpet, tile_map))
        self.assertEqual(tile_map["tile_types"][carpet["index"]]["type"], "carpet")

    def test_disabling_override_removes_serialised_key_and_restores_type_policy(self):
        tile_map = self.make_map()
        carpet = self.tile(tile_map, 1, 1)
        carpet["index"] = 1
        game.set_tile_force_collidable(carpet, True)
        game.set_tile_force_collidable(carpet, False)
        self.assertNotIn("force_collidable", carpet)
        self.assertFalse(game.tile_is_collidable(carpet, tile_map))
        wall = self.tile(tile_map, 2, 1)
        wall["index"] = 3
        self.assertTrue(game.tile_is_collidable(wall, tile_map))

    def test_forced_collision_uses_selected_triangle_shape(self):
        tile_map = self.make_map()
        carpet = self.tile(tile_map, 1, 1)
        carpet.update({"index": 1, "shape_index": 1, "force_collidable": True})
        solid = game.get_tile_shape_collision({"tile_x": 1, "tile_y": 1, "x": 2.0, "y": 2.0}, tile_map)
        empty = game.get_tile_shape_collision({"tile_x": 1, "tile_y": 1, "x": 9.0, "y": 9.0}, tile_map)
        self.assertTrue(solid["collides"])
        self.assertFalse(empty["collides"])
        self.assertEqual(solid["shape_index"], 1)

    def test_a_star_routes_around_forced_collision_tile(self):
        tile_map = self.make_map()
        blocked = self.tile(tile_map, 1, 1)
        blocked.update({"index": 1, "force_collidable": True})
        start = self.tile(tile_map, 0, 1)
        target = self.tile(tile_map, 2, 1)
        path = game.reconstruct_path(game.a_star_path(start, target, tile_map), target, start)
        self.assertNotIn(blocked, path)
        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], target)

    def test_flood_fill_applies_override_without_changing_art_identity(self):
        tile_map = self.make_map(2, 2)
        for tile in tile_map["tiles"]:
            tile["index"] = 1
        game.do_flood_fill_replace(1, 1, 0, 0, tile_map, 2, {}, force_collidable=True)
        self.assertTrue(all(tile.get("force_collidable") is True for tile in tile_map["tiles"]))
        self.assertTrue(all(tile["index"] == 1 for tile in tile_map["tiles"]))
        restored = pickle.loads(pickle.dumps(tile_map))
        self.assertTrue(all(tile.get("force_collidable") is True for tile in restored["tiles"]))

    def test_pink_tint_is_editor_only(self):
        tile = {"force_collidable": True}
        self.assertTrue(game.should_tint_forced_collision_tile(tile, "tile"))
        self.assertTrue(game.should_tint_forced_collision_tile(tile, "entity"))
        self.assertTrue(game.should_tint_forced_collision_tile(tile, "environment"))
        self.assertFalse(game.should_tint_forced_collision_tile(tile, "play"))
        self.assertFalse(game.should_tint_forced_collision_tile({}, "tile"))

    def test_triangle_tint_preview_uses_triangle_geometry(self):
        with mock.patch.object(game.pr, "draw_triangle") as draw_triangle, mock.patch.object(game.pr, "draw_rectangle") as draw_rectangle:
            game.draw_tile_shape_tint(game.pr.Vector2(10.0, 20.0), 1, 16, 16, game.pr.PINK)
        draw_triangle.assert_called_once()
        draw_rectangle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
