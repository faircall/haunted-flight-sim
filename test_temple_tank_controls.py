"""Gameplay-facing input contracts across camera cuts, aim and saved progress."""
import math
import unittest
from g_temple_cameras import TankWalkthrough
from test_temple_exploration import exploration


class TankControlsTests(unittest.TestCase):
    def test_turn_in_place_and_backward_preserve_body_heading(self):
        walk=TankWalkthrough()
        origin=(walk.x,walk.y)
        walk.step({'a'},.5,lambda x,z:True)
        self.assertEqual((walk.x,walk.y),origin)
        self.assertAlmostEqual(math.degrees(math.atan2(*walk.facing)),30)
        self.assertEqual(walk.turning,-120)
        facing=walk.facing
        walk.step({'s'},.2,lambda x,z:True,42,running=True)
        self.assertEqual(walk.facing,facing)
        self.assertTrue(walk.backwards);self.assertFalse(walk.running)
        self.assertAlmostEqual(math.dist(origin,(walk.x,walk.y)),2.6)
        self.assertAlmostEqual(sum(a*b for a,b in zip(walk.heading,walk.facing)),-1)

    def test_camera_cut_and_key_release_do_not_change_forward(self):
        walk=TankWalkthrough(395,334)
        for _ in range(8):walk.step({'w'},.05,lambda x,z:True,42)
        self.assertEqual(walk.director.active,'landing')
        walk.step(set(),.05,lambda x,z:True)
        origin=walk.x,walk.y
        walk.step({'w'},.05,lambda x,z:True,42)
        self.assertAlmostEqual(walk.y,origin[1]);self.assertGreater(walk.x,origin[0])
        self.assertEqual(walk.facing,(1.,0.))

    def test_mouse_owns_yaw_and_strafe_is_slower_than_forward(self):
        walk=TankWalkthrough()
        origin=walk.x,walk.y
        target=walk.x,walk.y-100
        walk.step({'d'},.5,lambda x,z:True,42,True,target,True)
        self.assertAlmostEqual(walk.facing[0],0);self.assertAlmostEqual(walk.facing[1],-1)
        self.assertEqual(walk.turning,0)
        self.assertAlmostEqual(walk.x,origin[0]-3.5);self.assertEqual(walk.y,origin[1])
        self.assertFalse(walk.running)
        walk.step({'w','d'},.5,lambda x,z:True,42,True,(walk.x,walk.y-100))
        self.assertAlmostEqual(math.dist((origin[0]-3.5,origin[1]),(walk.x,walk.y)),6.)

    def test_simultaneous_turn_and_forward_and_opposite_keys(self):
        walk=TankWalkthrough()
        walk.step({'w','d'},.05,lambda x,z:True,20)
        self.assertTrue(walk.moving);self.assertEqual(walk.turning,120)
        self.assertAlmostEqual(sum(a*b for a,b in zip(walk.heading,walk.facing)),1.)
        origin=walk.x,walk.y;facing=walk.facing
        walk.step({'w','s','a','d'},.05,lambda x,z:True)
        self.assertEqual((walk.x,walk.y),origin);self.assertEqual(walk.facing,facing)
        self.assertFalse(walk.moving);self.assertEqual(walk.turning,0)

    def test_blocked_travel_still_allows_rotation(self):
        walk=TankWalkthrough();origin=walk.x,walk.y
        walk.step({'w','a'},.05,lambda x,z:False)
        self.assertFalse(walk.moving);self.assertEqual((walk.x,walk.y),origin)
        self.assertNotEqual(walk.facing,(1,0));self.assertGreater(walk.turn_distance,0)

    def test_gameplay_save_restores_stationary_facing_and_pause_freezes_it(self):
        g=exploration();origin=g.walk.x,g.walk.y
        for _ in range(15):g.tick(.05,{'a'})
        saved=g.snapshot();facing=g.walk.facing
        self.assertEqual((g.walk.x,g.walk.y),origin)
        g.tick(.05,{'d'},pressed={'TAB'})
        for _ in range(4):g.tick(.05,{'d'})
        self.assertEqual(g.walk.facing,facing);self.assertEqual(g.walk.turning,0)
        g.restore(saved)
        self.assertEqual(g.walk.facing,facing)
        self.assertEqual(g.snapshot(),saved)

    def test_aim_heading_is_applied_before_motion_and_survives_aim_release(self):
        g=exploration();origin=g.walk.x,g.walk.y
        target=(origin[0]+100,18.5,origin[1])
        g.tick(.05,{'a'},aiming=True,aim=target)
        self.assertAlmostEqual(g.walk.x,origin[0]);self.assertGreater(g.walk.y,origin[1])
        facing=g.walk.facing
        g.tick(.05)
        self.assertEqual(g.walk.facing,facing)
        g.tick(.05,{'s'})
        self.assertEqual(g.walk.facing,facing);self.assertTrue(g.walk.backwards)


if __name__=='__main__':unittest.main()
