import unittest

import g_effects
import g_tree_animation as rig


class TreeAnimationTests(unittest.TestCase):
    def test_cached_pose_matches_original_triangles(self):
        for mesh in ("grid", "strips"):
            for irregular in (True, False):
                for strength in (0., 8., 42.):
                    profile = dict(g_effects.make_wind_profile(), tree_mesh=mesh,
                                   tree_irregular=irregular, strength=strength,
                                   gust_strength=strength * .7, tree_seed=93)
                    for part in rig.PARTS:
                        topology = rig.mesh_topology(tuple(part["bounds"]), tuple(part["pivot"]), mesh == "strips")
                        for elapsed in (0., 3., 17.):
                            positions, angle = rig.mesh_pose(part, elapsed, profile, (137., -43.))
                            self.assertEqual(angle, rig.motion(part, elapsed, profile, (137., -43.))[0])
                            expected = [quad[i] for quad in rig.foliage_mesh(part, elapsed, profile, (137., -43.))
                                        for i in (0, 1, 2, 0, 2, 3)]
                            for index, vertex in zip(topology[2], expected):
                                self.assertEqual(positions[index], vertex[:2])
                                self.assertEqual(tuple(v / 128. for v in topology[0][index]), vertex[2:])
                            self.assertEqual(len(topology[2]), len(expected))

    def test_topology_cache_keys_include_edited_bounds_pivot_and_mode(self):
        part = rig.PARTS[0]
        key = (tuple(part["bounds"]), tuple(part["pivot"]))
        original = rig.mesh_topology(*key)
        self.assertIs(original, rig.mesh_topology(*key))
        self.assertIsNot(original, rig.mesh_topology(key[0], (55, 20)))
        self.assertIsNot(original, rig.mesh_topology((34, 10, 68, 68), key[1]))
        self.assertIsNot(original, rig.mesh_topology(*key, True))

    def test_grid_shared_vertices_are_identical_and_triangles_do_not_fold(self):
        profile = dict(g_effects.make_wind_profile(), strength=42., gust_strength=27.)
        for part in rig.PARTS:
            for elapsed in (0., 1., 3., 7.):
                vertices = {}
                for quad in rig.grid_mesh(part, elapsed, profile):
                    for vertex in quad:
                        uv = vertex[2:]
                        if uv in vertices:
                            self.assertEqual(vertex, vertices[uv])
                        vertices[uv] = vertex
                    for a, b, c in ((quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])):
                        area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
                        self.assertLess(area, 0.)
                px, py = part['pivot']
                self.assertEqual(vertices[px/128., py/128.][:2], (px, py))

    def test_grid_calm_and_still_preserve_art(self):
        for mode, strength in (('hybrid', 0.), ('still', 8.)):
            profile = dict(g_effects.make_wind_profile(), strength=strength, gust_strength=0.)
            for part in rig.PARTS:
                for quad in rig.grid_mesh(part, 3., profile, mode=mode):
                    for x, y, u, v in quad:
                        self.assertEqual((x, y), (u*128., v*128.))

    def test_grid_motion_varies_across_same_row_and_remains_visible(self):
        part = rig.PARTS[2]
        profile = g_effects.make_wind_profile()
        x0, y0, x1, y1 = part['bounds']
        points = [(x0 + 4, y1 - 8), ((x0+x1)/2, y1 - 8), (x1 - 4, y1 - 8)]
        motions = []
        for point in points:
            displacements = []
            for i in range(121):
                t = i / 20.
                angle, bend = rig.motion(part, t, profile)
                x, y = rig.grid_deform_point(point, part, angle, bend, t, 1., part['phase'])
                displacements.append(x-point[0])
            self.assertGreater(max(displacements)-min(displacements), 1.)
            motions.append(displacements)
        self.assertGreater(max(abs(a-b) for a,b in zip(motions[0], motions[-1])), .5)

    def test_noise_has_meaningful_range(self):
        values = [rig.smooth_noise(i / 4., 17) for i in range(160)]
        self.assertGreater(max(values), .5)
        self.assertLess(min(values), -.5)
        self.assertTrue(all(-1. <= value <= 1. for value in values))

    def test_default_wind_moves_each_cluster_at_native_pixel_scale(self):
        profile = g_effects.make_wind_profile()
        for part in rig.PARTS:
            tips = []
            for frame in range(601):
                angle, bend = rig.motion(part, frame / 60., profile)
                tip = (part['pivot'][0], part['bounds'][3])
                tips.append(rig.deform_point(tip, part, angle, bend)[0])
            self.assertGreater(max(tips) - min(tips), .5, part['name'])

    def test_noise_is_continuous_at_random_target_boundaries(self):
        for boundary in range(-4, 5):
            self.assertAlmostEqual(rig.smooth_noise(boundary - .00001, 17),
                                   rig.smooth_noise(boundary + .00001, 17), places=8)

    def test_seed_is_reproducible_and_changes_motion(self):
        profile = g_effects.make_wind_profile()
        part = rig.PARTS[0]
        pose = rig.motion(part, 4., profile)
        self.assertEqual(pose, rig.motion(part, 4., profile))
        self.assertNotEqual(pose, rig.motion(part, 4., dict(profile, tree_seed=18)))
        self.assertNotEqual(pose, rig.motion(part, 4., dict(profile, tree_irregular=False)))

    def test_pivots_remain_fixed_in_wind(self):
        profile = g_effects.make_wind_profile()
        for part in rig.PARTS:
            for elapsed in (0, 1, 3, 10):
                angle, bend = rig.motion(part, elapsed, profile)
                self.assertEqual(rig.deform_point(part['pivot'], part, angle, bend), part['pivot'])

    def test_calm_matches_original_canvas(self):
        profile = g_effects.make_wind_profile()
        profile.update(strength=0, gust_strength=0)
        for part in rig.PARTS:
            for quad in rig.strip_mesh(part, 4, profile):
                for x, y, u, v in quad:
                    self.assertEqual((x, y), (u * 128, v * 128))

    def test_mesh_is_connected_and_motion_varies(self):
        profile = g_effects.make_wind_profile()
        for part in rig.PARTS:
            mesh = list(rig.strip_mesh(part, 1, profile))
            for upper, lower in zip(mesh, mesh[1:]):
                self.assertEqual(upper[1], lower[0])
                self.assertEqual(upper[2], lower[3])
            self.assertNotEqual(mesh, list(rig.strip_mesh(part, 2, profile)))
            self.assertNotEqual(mesh, list(rig.strip_mesh(part, 1, profile, mode='rigid')))


if __name__ == '__main__':
    unittest.main()
