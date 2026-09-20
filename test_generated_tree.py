import unittest

import g_effects
import g_generated_tree as generated


class GeneratedTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strands = generated.build()

    def test_generation_is_repeatable_and_seeded(self):
        self.assertEqual(self.strands, generated.build())
        self.assertNotEqual(self.strands, generated.build(seed=18))
        self.assertGreater(len(self.strands), 40)
        self.assertGreater(sum(len(s['leaves']) for s in self.strands),1000)

    def test_roots_stay_pinned(self):
        for strand in self.strands:
            for time in (0., 3., 9.):
                self.assertEqual(generated.point(strand,-1.,time,.12,4.,1.5),strand['part']['pivot'])

    def test_calm_and_rest_match_and_do_not_drift(self):
        calm = dict(g_effects.make_wind_profile(),strength=0.,gust_strength=0.)
        self.assertEqual(generated.pose(self.strands,0.,calm),generated.pose(self.strands,3.,calm))
        self.assertEqual(generated.pose(self.strands,0.,calm),
                         generated.pose(self.strands,3.,g_effects.make_wind_profile(),still=True))

    def test_motion_preserves_leaf_identities_colors_and_topology(self):
        profile = g_effects.make_wind_profile()
        first = generated.pose(self.strands,0.,profile)[1]
        second = generated.pose(self.strands,3.,profile)[1]
        self.assertEqual([p[1] for p in first],[p[1] for p in second])
        self.assertEqual([p[3] for p in first],[p[3] for p in second])
        visible_moves = sum(max(abs(a-b) for pa,pb in zip(x[0],y[0]) for a,b in zip(pa,pb)) > .5
                            for x,y in zip(first,second))
        self.assertGreater(visible_moves,len(first)//4)
        self.assertEqual(second,generated.pose(self.strands,3.,profile)[1])


if __name__ == '__main__':
    unittest.main()
