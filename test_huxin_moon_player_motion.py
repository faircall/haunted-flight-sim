"""Player movement and animation cadence agree in the Moon scene."""
import unittest
from importlib import import_module

from g_huxin_moon import Explorer, GAIT, PLAYER_SCALE


class MoonPlayerMotionTests(unittest.TestCase):
    def test_outdoor_scenes_use_jog_stride_and_walking_stride_when_backwards(self):
        from player_jog import JOG_STRIDE
        for module in ('g_huxin','g_huxin_moon','g_huxin_canals','g_huxin_canals_flooded','g_bamboo_grove'):
            with self.subTest(scene=module):
                scene=import_module(module)
                actor=scene.Explorer();distance=actor.tick(.05,forward=1,run=True)
                self.assertGreater(distance,0.)
                self.assertEqual(actor.clip,'run')
                self.assertAlmostEqual(actor.phase,distance/(JOG_STRIDE*scene.PLAYER_SCALE))
                actor=scene.Explorer();distance=actor.tick(.05,forward=-1,run=True)
                self.assertGreater(distance,0.)
                self.assertEqual(actor.clip,'walk_back')
                self.assertAlmostEqual(actor.phase,distance/(GAIT['walk']['stride']*scene.PLAYER_SCALE))

    def test_shift_backwards_keeps_walking_cadence(self):
        # Shift only increases forward speed; backwards always uses walk_back.
        # Its phase must therefore use the walk stride, even while Shift is held.
        ordinary = Explorer()
        shifted = Explorer()
        normal_distance = ordinary.tick(.05, forward=-1, run=False)
        shift_distance = shifted.tick(.05, forward=-1, run=True)
        self.assertGreater(normal_distance, 0.)
        self.assertAlmostEqual(shift_distance, normal_distance)
        self.assertEqual((ordinary.clip, shifted.clip), ('walk_back', 'walk_back'))
        expected = normal_distance / (GAIT['walk']['stride'] * PLAYER_SCALE)
        self.assertAlmostEqual(ordinary.phase, expected)
        self.assertAlmostEqual(shifted.phase, expected)

    def test_forward_run_still_uses_run_stride_and_speed(self):
        walk = Explorer()
        run = Explorer()
        walk_distance = walk.tick(.05, forward=1, run=False)
        run_distance = run.tick(.05, forward=1, run=True)
        self.assertGreater(run_distance, walk_distance)
        self.assertEqual((walk.clip, run.clip), ('walk', 'run'))
        self.assertAlmostEqual(walk.phase, walk_distance / (GAIT['walk']['stride'] * PLAYER_SCALE))
        self.assertAlmostEqual(run.phase, run_distance / (GAIT['run']['stride'] * PLAYER_SCALE))


if __name__ == '__main__':
    unittest.main()
