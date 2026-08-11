import unittest

import g_update_and_render as game


def position(tile_x, tile_y, x=8.0, y=8.0):
    return {"tile_x": tile_x, "tile_y": tile_y, "x": x, "y": y}


class GameplayLineOfSightTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(10, 10, 16, 16)

    def ray_hits(self, origin, target, end_range=900.0):
        origin_abs = game.tile_and_offset_to_absolute(self.tile_map, origin)
        target_abs = game.tile_and_offset_to_absolute(self.tile_map, target)
        direction = game.vec2_normalize(game.vec2_subtract(target_abs, origin_abs))
        return game.ray_along_tiles_hits_target_tile(
            origin, target, end_range, 10.0, direction, self.tile_map,
        )

    def test_entity_boundary_points_are_centred_on_entity_position(self):
        centre = position(5, 5)
        points = game.make_entity_boundary_points(
            centre, 12, 8, 16, 16, 4,
        )
        absolute_points = [
            game.tile_and_offset_to_absolute(self.tile_map, point)
            for point in points.values()
        ]
        centre_abs = game.tile_and_offset_to_absolute(self.tile_map, centre)

        self.assertEqual(min(point["x"] for point in absolute_points), centre_abs["x"] - 6)
        self.assertEqual(max(point["x"] for point in absolute_points), centre_abs["x"] + 6)
        self.assertEqual(min(point["y"] for point in absolute_points), centre_abs["y"] - 4)
        self.assertEqual(max(point["y"] for point in absolute_points), centre_abs["y"] + 4)

    def test_legal_bottom_row_entity_generates_only_in_bounds_points(self):
        points = game.make_entity_boundary_points(
            position(5, 9), 12, 12, 16, 16, 4,
        )

        self.assertTrue(points)
        self.assertTrue(all(
            game.tile_in_bounds(point["tile_x"], point["tile_y"], self.tile_map)
            for point in points.values()
        ))

    def test_out_of_bounds_target_coordinates_do_not_index_or_alias_tiles(self):
        origin = position(5, 5)
        for target in (
                position(5, 10),
                position(5, -1),
                position(10, 5),
                position(-1, 5)):
            with self.subTest(target=target):
                self.assertFalse(self.ray_hits(origin, target))

    def test_clear_ray_reaches_valid_target_without_tracing_past_it(self):
        self.assertTrue(self.ray_hits(position(2, 2), position(7, 7)))

    def test_ray_stops_at_wall_before_target(self):
        self.tile_map["tiles"][2 * 10 + 4]["index"] = 3

        self.assertFalse(self.ray_hits(position(2, 2), position(7, 2)))

    def test_target_beyond_requested_range_is_not_reported_visible(self):
        self.assertFalse(self.ray_hits(
            position(2, 2), position(7, 2), end_range=20.0,
        ))

    def test_bottom_edge_visibility_query_is_safe_and_can_see_player(self):
        redhead = {
            "position": position(5, 7),
            "sight_angle": 270,
            "sight_range": 900,
        }
        player = {
            "position": position(5, 9),
            "entity_width": 12,
            "entity_height": 12,
        }

        can_see, found_position = game.alice_can_see_bob_points(
            redhead, player, self.tile_map, None,
        )

        self.assertTrue(can_see)
        self.assertIsNotNone(found_position)
        self.assertTrue(game.tile_in_bounds(
            found_position["tile_x"], found_position["tile_y"], self.tile_map,
        ))


if __name__ == "__main__":
    unittest.main()
