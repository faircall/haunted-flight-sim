"""CPU-only behavioral checks for position-driven encounter fog."""
import math
import unittest

from g_exploration_fog import ExplorationFog


class ExplorationFogTests(unittest.TestCase):
    def test_distance_configuration_is_read_only(self):
        fog = ExplorationFog(inner_distance=3., outer_distance=15.)
        self.assertEqual(fog.inner_distance, 3.)
        self.assertEqual(fog.outer_distance, 15.)
        for name in ('inner_distance', 'outer_distance'):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    setattr(fog, name, 10.)

    def test_puzzle_dead_zone_and_clear_endpoints(self):
        fog = ExplorationFog(inner_distance=3., outer_distance=15.)
        self.assertEqual(fog.clear_fraction, 0.)
        self.assertEqual(fog.furthest_distance, 0.)
        for distance in (0., 1., 2.99, 3.):
            self.assertEqual(fog.update(distance, 0., 0.), 0.)
        self.assertEqual(fog.update(9., 0., 0.), .5)
        self.assertEqual(fog.update(15., 0., 0.), 1.)
        self.assertEqual(fog.update(100., 0., 0.), 1.)

    def test_idle_updates_and_property_reads_do_not_advance(self):
        fog = ExplorationFog()
        clear = fog.update(12., .325, 4.)
        distance = fog.furthest_distance
        # Equivalent to a minute at 100 updates/second, without any clock input.
        for _ in range(6000):
            self.assertEqual(fog.update(12., .325, 4.), clear)
            self.assertEqual(fog.clear_fraction, clear)
        self.assertEqual(fog.furthest_distance, distance)

    def test_backtracking_and_repeated_route_cannot_farm_clearing(self):
        fog = ExplorationFog()
        discovered = fog.update(0., 0., 18.)
        for _ in range(20):
            for z in (12., 6., 0., 6., 12., 18.):
                self.assertEqual(fog.update(0., 0., z), discovered)
        self.assertGreater(fog.update(0., 0., 19.), discovered)

    def test_circling_does_not_accumulate_distance_walked(self):
        fog = ExplorationFog()
        initial = fog.update(12., 0., 0.)
        for degrees in range(1441):
            angle = math.radians(degrees)
            fog.update(12.*math.cos(angle), 0., 12.*math.sin(angle))
        self.assertAlmostEqual(fog.clear_fraction, initial, places=14)
        self.assertAlmostEqual(fog.furthest_distance, 12., places=13)

    def test_route_sampling_and_speed_do_not_change_final_discovery(self):
        sparse = ExplorationFog()
        dense = ExplorationFog()
        for x, z in ((0., 0.), (4., 12.), (10., 18.), (3., 10.)):
            sparse.update(x, 0., z)
        route = ((0., 0.), (4., 12.), (10., 18.), (3., 10.))
        for a, b in zip(route, route[1:]):
            for step in range(101):
                t = step/100.
                dense.update(a[0]+(b[0]-a[0])*t, 0., a[1]+(b[1]-a[1])*t)
        self.assertEqual(sparse.furthest_distance, dense.furthest_distance)
        self.assertEqual(sparse.clear_fraction, dense.clear_fraction)

    def test_origin_translation_and_direction_do_not_change_progress(self):
        a = ExplorationFog(origin=(0., .325, 0.))
        b = ExplorationFog(origin=(100., 7., -40.))
        self.assertEqual(a.update(9., .325, 12.), b.update(88., 7., -31.))
        self.assertEqual(a.furthest_distance, 15.)
        self.assertEqual(b.furthest_distance, 15.)

    def test_elevation_is_ignored_by_default(self):
        fog = ExplorationFog(origin=(0., .325, 0.))
        before = fog.update(4., .325, 3.)
        self.assertEqual(fog.update(4., 20., 3.), before)
        self.assertEqual(fog.update(4., -20., 3.), before)

    def test_optional_elevation_discovers_upper_floor_without_refogging(self):
        fog = ExplorationFog(inner_distance=2.5, outer_distance=11.,
                             origin=(0., .325, 0.), vertical_weight=2.)
        ground = fog.update(5., .325, 0.)
        upstairs = fog.update(5., 4.125, 0.)
        self.assertGreater(upstairs, ground)
        self.assertAlmostEqual(fog.furthest_distance, math.hypot(5., 7.6))
        self.assertEqual(fog.update(5., .325, 0.), upstairs)
        self.assertEqual(fog.update(8., 4.125, 0.), 1.)

    def test_progress_is_bounded_monotonic_and_soft_at_endpoints(self):
        fog = ExplorationFog(inner_distance=2., outer_distance=12.)
        values = [fog.update(i/100., 0., 0.) for i in range(1501)]
        self.assertTrue(all(0. <= value <= 1. for value in values))
        self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))
        self.assertLess(values[201]-values[200], 1e-7)
        self.assertLess(values[1200]-values[1199], 1e-7)
        self.assertGreater(values[701]-values[700], .001)

    def test_invalid_positions_leave_previous_discovery_intact(self):
        fog = ExplorationFog()
        before = fog.update(18., 0., 0.)
        for point in ((math.nan, 0., 0.), (0., math.inf, 0.), (0., 0., -math.inf)):
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    fog.update(*point)
                self.assertEqual(fog.clear_fraction, before)
                self.assertEqual(fog.furthest_distance, 18.)

    def test_invalid_configuration_is_rejected(self):
        for options in (
            {'inner_distance': -1.}, {'inner_distance': 5., 'outer_distance': 5.},
            {'outer_distance': math.inf}, {'outer_distance': math.nan},
            {'vertical_weight': -1.}, {'vertical_weight': math.inf},
            {'origin': (0., 0.)}, {'origin': (0., 0., 0., 0.)},
            {'origin': (0., math.nan, 0.)},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    ExplorationFog(**options)


if __name__ == '__main__':
    unittest.main()
