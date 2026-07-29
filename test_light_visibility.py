import math
import unittest

import g_light_visibility as visibility


def make_tile_map(width=5, height=5, tile_size=10):
    return {
        "map_width": width,
        "map_height": height,
        "tile_width": tile_size,
        "tile_height": tile_size,
        "geometry_revision": 0,
        "tiles": [{"index": 0, "shape_index": 0} for _ in range(width * height)]
    }


def make_grid(solids=(), width=5, height=5, tile_size=10):
    tile_map = make_tile_map(width, height, tile_size)

    for tile_x, tile_y, shape_index in solids:
        tile_map["tiles"][tile_y * width + tile_x] = {"index": 1, "shape_index": shape_index}

    return visibility.build_light_collision_grid(tile_map, {1})


class FullTileTests(unittest.TestCase):
    def setUp(self):
        self.grid = make_grid([(2, 2, 0)])

    def test_horizontal_vertical_and_diagonal_entry(self):
        cases = [
            ({"x": 0, "y": 25}, {"x": 1, "y": 0}, 20.0),
            ({"x": 25, "y": 0}, {"x": 0, "y": 1}, 20.0),
            ({"x": 0, "y": 0}, {"x": 1, "y": 1}, math.sqrt(800.0))
        ]

        for origin, direction, expected in cases:
            with self.subTest(origin=origin, direction=direction):
                hit = visibility.dda_first_light_hit(origin, direction, 100.0, self.grid)
                self.assertIsNotNone(hit)
                self.assertAlmostEqual(hit["distance"], expected)

    def test_miss_and_origin_inside(self):
        self.assertIsNone(visibility.dda_first_light_hit({"x": 0, "y": 5}, {"x": 1, "y": 0}, 100.0, self.grid))
        hit = visibility.dda_first_light_hit({"x": 25, "y": 25}, {"x": 1, "y": 0}, 100.0, self.grid)
        self.assertEqual(hit["distance"], 0.0)

    def test_compact_grid_removes_shared_full_edges_and_keeps_receivers(self):
        grid = make_grid([(1, 1, 0), (2, 1, 0)], width=4, height=3)
        self.assertIsInstance(grid["shape_codes"], bytearray)
        self.assertEqual(len(grid["boundary_segments"]), 6)
        self.assertEqual(len(grid["boundary_vertices"]), 6)
        self.assertIsNotNone(grid["receiver_polygons"][5])
        self.assertIsNone(grid["receiver_polygons"][0])


class TriangleTests(unittest.TestCase):
    solid_and_empty_points = {
        1: ({"x": 2, "y": 2}, {"x": 8, "y": 8}, {"x": 1, "y": 0}),
        2: ({"x": 8, "y": 2}, {"x": 2, "y": 8}, {"x": -1, "y": 0}),
        3: ({"x": 8, "y": 8}, {"x": 2, "y": 2}, {"x": -1, "y": 0}),
        4: ({"x": 2, "y": 8}, {"x": 8, "y": 2}, {"x": 1, "y": 0})
    }

    def test_all_triangle_solid_and_empty_halves(self):
        for shape_index, (solid, empty, empty_direction) in self.solid_and_empty_points.items():
            with self.subTest(shape_index=shape_index):
                grid = make_grid([(0, 0, shape_index)], width=1, height=1)
                solid_hit = visibility.dda_first_light_hit(solid, {"x": 1, "y": 0}, 1.0, grid)
                empty_hit = visibility.dda_first_light_hit(empty, empty_direction, 1.0, grid)
                self.assertIsNotNone(solid_hit)
                self.assertEqual(solid_hit["distance"], 0.0)
                self.assertIsNone(empty_hit)

    def test_triangle_diagonal_and_corner_grazes_are_not_long_blocks(self):
        for shape_index in range(1, 5):
            with self.subTest(shape_index=shape_index):
                grid = make_grid([(1, 1, shape_index)], width=3, height=3)
                hit = visibility.dda_first_light_hit({"x": 0, "y": 0}, {"x": 1, "y": 1}, 50.0, grid)

                if hit is not None:
                    self.assertLessEqual(hit["distance"], math.sqrt(800.0) + visibility.DDA_EPSILON)

    def test_empty_triangle_half_continues_to_later_wall(self):
        grid = make_grid([(1, 1, 1), (2, 1, 0)], width=4, height=3)
        hit = visibility.dda_first_light_hit({"x": 19, "y": 19}, {"x": 1, "y": 0}, 30.0, grid)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["tile_x"], 2)
        self.assertAlmostEqual(hit["distance"], 1.0)


class DdaTraversalTests(unittest.TestCase):
    def test_cardinal_and_all_diagonal_directions(self):
        solids = [(3, 2, 0), (1, 2, 0), (2, 3, 0), (2, 1, 0), (3, 3, 0), (1, 3, 0), (3, 1, 0), (1, 1, 0)]
        grid = make_grid(solids)
        origin = {"x": 25, "y": 25}

        for direction in (
            {"x": 1, "y": 0}, {"x": -1, "y": 0}, {"x": 0, "y": 1}, {"x": 0, "y": -1},
            {"x": 1, "y": 1}, {"x": -1, "y": 1}, {"x": 1, "y": -1}, {"x": -1, "y": -1}
        ):
            with self.subTest(direction=direction):
                self.assertIsNotNone(visibility.dda_first_light_hit(origin, direction, 100.0, grid))

    def test_boundary_origin_corner_crossing_map_exit_and_short_radius(self):
        grid = make_grid([(0, 1, 0), (2, 2, 0)], width=3, height=3)
        boundary_hit = visibility.dda_first_light_hit({"x": 10, "y": 15}, {"x": -1, "y": 0}, 20.0, grid)
        self.assertIsNotNone(boundary_hit)
        self.assertAlmostEqual(boundary_hit["distance"], 0.0)
        self.assertIsNone(visibility.dda_first_light_hit({"x": 5, "y": 5}, {"x": -1, "y": 0}, 100.0, grid))
        self.assertIsNone(visibility.dda_first_light_hit({"x": 5, "y": 25}, {"x": 1, "y": 0}, 4.0, grid))
        self.assertIsNone(visibility.dda_first_light_hit({"x": 0, "y": 0}, {"x": 1, "y": 1}, 12.0, grid))

    def test_corner_only_touch_does_not_enter_side_tile(self):
        grid = make_grid([(1, 0, 0)], width=3, height=3)
        self.assertIsNone(visibility.dda_first_light_hit({"x": 0, "y": 0}, {"x": 1, "y": 1}, 40.0, grid))

    def test_outside_origin_zero_direction_and_first_cell(self):
        grid = make_grid([(0, 0, 0)], width=2, height=2)
        hit = visibility.dda_first_light_hit({"x": -5, "y": 5}, {"x": 1, "y": 0}, 30.0, grid)
        self.assertAlmostEqual(hit["distance"], 5.0)
        self.assertIsNone(visibility.dda_first_light_hit({"x": -5, "y": 30}, {"x": 1, "y": 0}, 30.0, grid))
        self.assertIsNone(visibility.dda_first_light_hit({"x": 5, "y": 5}, {"x": 0, "y": 0}, 30.0, grid))
        self.assertEqual(visibility.dda_first_light_hit({"x": 5, "y": 5}, {"x": 1, "y": 0}, 30.0, grid)["distance"], 0.0)


class VisibilityPolygonTests(unittest.TestCase):
    def test_point_angles_are_sorted_bounded_and_deduplicated(self):
        grid = make_grid([(1, 1, 0), (2, 1, 0), (1, 2, 0), (2, 2, 0)], width=4, height=4)
        light = {"type": "point", "radius": 50.0, "visibility_ray_count": 16, "visibility_max_rays": 24}
        result = visibility.build_visibility_ray_angles(light, {"x": 5, "y": 5}, grid)
        self.assertEqual(result["angles"], sorted(result["angles"]))
        self.assertLessEqual(len(result["angles"]), 24)
        self.assertEqual(len(result["angles"]), len({round(angle, 8) for angle in result["angles"]}))
        self.assertEqual(result["baseline_ray_count"], 16)

    def test_spot_angles_stay_inside_cone_and_polygon_reports_stats(self):
        grid = make_grid([(2, 2, 0)])
        light = {"type": "spot", "position": {"x": 5, "y": 25}, "direction": {"x": 1, "y": 0}, "outer_angle": 20.0, "radius": 50.0, "visibility_ray_count": 12, "visibility_max_rays": 32}
        angle_data = visibility.build_visibility_ray_angles(light, light["position"], grid)

        for angle in angle_data["angles"]:
            self.assertLessEqual(abs(visibility.normalize_angle_signed(angle)), math.radians(20.0) + visibility.DDA_EPSILON)

        geometry = visibility.build_light_visibility_polygon_dda(light, light["position"], grid)
        self.assertEqual(len(geometry["polygon"]), geometry["ray_count"])
        self.assertEqual(len(geometry["unbiased_polygon"]), geometry["ray_count"])
        self.assertGreater(geometry["dda_tile_steps"], 0)


class CacheTests(unittest.TestCase):
    def test_geometry_key_includes_geometry_and_excludes_appearance(self):
        grid = make_grid()
        base = {"type": "point", "radius": 40.0, "casts_wall_shadows": True, "color": [1, 1, 1], "intensity": 1.0}
        position = {"x": 15.0, "y": 15.0}
        first = visibility.make_light_geometry_key({"id": "light", "light": base}, position, grid)
        appearance_change = dict(base, color=[1, 0, 0], intensity=8.0, gameplay_intensity=0.2)
        self.assertEqual(first, visibility.make_light_geometry_key({"id": "light", "light": appearance_change}, position, grid))
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "light", "light": dict(base, radius=41.0)}, position, grid))
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "light", "light": base}, {"x": 15.1, "y": 15.0}, grid))
        self.assertEqual(first, visibility.make_light_geometry_key({"id": "light", "light": dict(base, mobility="dynamic")}, position, grid))

        revised_grid = dict(grid, geometry_revision=grid["geometry_revision"] + 1)
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "light", "light": base}, position, revised_grid))
        reloaded_grid = dict(grid, runtime_generation=grid["runtime_generation"] + 1)
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "light", "light": base}, position, reloaded_grid))

    def test_cache_pruning(self):
        cache = {"fresh": {"last_used_frame": 10}, "old": {"last_used_frame": 1}}
        self.assertEqual(visibility.prune_light_visibility_cache(cache, 12, 5), 1)
        self.assertEqual(set(cache), {"fresh"})

    def test_spot_rotation_and_adaptive_settings_change_key(self):
        grid = make_grid()
        light = {"type": "spot", "radius": 40.0, "direction": {"x": 1, "y": 0}, "outer_angle": 25.0, "casts_wall_shadows": True}
        position = {"x": 15.0, "y": 15.0}
        first = visibility.make_light_geometry_key({"id": "spot", "light": light}, position, grid)
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "spot", "light": dict(light, direction={"x": 0, "y": 1})}, position, grid))
        self.assertNotEqual(first, visibility.make_light_geometry_key({"id": "spot", "light": dict(light, visibility_max_rays=128)}, position, grid))


class GameplayQueryTests(unittest.TestCase):
    def setUp(self):
        self.grid = make_grid([(2, 2, 0)])
        self.light = {
            "type": "point", "position": {"x": 5, "y": 25}, "radius": 50.0,
            "falloff": 1.0, "intensity": 1.0, "gameplay_intensity": 1.0,
            "enabled": True, "affects_ai": True
        }

    def test_visible_and_blocked_points(self):
        visible = visibility.get_gameplay_light_strength_at_world_point(self.light, {"x": 15, "y": 25}, self.grid)
        blocked = visibility.get_gameplay_light_strength_at_world_point(self.light, {"x": 35, "y": 25}, self.grid)
        self.assertAlmostEqual(visible, 0.8)
        self.assertEqual(blocked, 0.0)

    def test_disabled_ai_and_readability_lights_return_zero(self):
        for changes in ({"enabled": False}, {"affects_ai": False}, {"affects_ai": False, "gameplay_intensity": 0.0}):
            with self.subTest(changes=changes):
                self.assertEqual(visibility.get_gameplay_light_strength_at_world_point(dict(self.light, **changes), {"x": 15, "y": 25}, self.grid), 0.0)

    def test_spotlight_cone_and_total_contribution(self):
        spot = dict(self.light, type="spot", direction={"x": 1, "y": 0}, inner_angle=10.0, outer_angle=20.0)
        self.assertGreater(visibility.get_gameplay_light_strength_at_world_point(spot, {"x": 15, "y": 25}, self.grid), 0.0)
        self.assertEqual(visibility.get_gameplay_light_strength_at_world_point(spot, {"x": 5, "y": 15}, self.grid), 0.0)
        total = visibility.get_total_gameplay_light_strength_at_world_point([{"id": "a", "light": self.light}, {"id": "b", "light": dict(self.light, affects_ai=False)}], {"x": 15, "y": 25}, self.grid)
        self.assertAlmostEqual(total, 0.8)


if __name__ == "__main__":
    unittest.main()
