"""Checks for the isolated Chorus review and playable figure study."""
import math
from types import SimpleNamespace
import unittest

from chorus_figure_review import ReviewState,controls,inside
from chorus_grasper_animation import GAITS,CLIP_SECONDS,BRISK_WALK_SPEED
from g_chorus_trial import FigureMotion
from g_huxin_moon import PLAYER_SCALE,can_walk
from g_huxin_moon_sequence import CAUSEWAY_LENGTH,causeway_point,causeway_progress


def actor(progress):
    x,z=causeway_point(progress);return SimpleNamespace(x=x,z=z)


class ChorusTrialTests(unittest.TestCase):
    def test_follow_moves_on_causeway_and_uses_distance_calibrated_phase(self):
        motion=FigureMotion(progress=.65);player=actor(.8)
        before=motion.position;motion.tick(.05,player);after=motion.position
        distance=math.hypot(after[0]-before[0],after[2]-before[2])
        self.assertEqual(motion.clip,'enemy_walk');self.assertEqual(motion.pace,'brisk')
        self.assertGreater(distance,0.)
        self.assertAlmostEqual(motion.phase,distance/(GAITS['enemy_walk']['stride']*PLAYER_SCALE))
        self.assertAlmostEqual(distance,BRISK_WALK_SPEED*.05,places=3)
        self.assertTrue(can_walk(after[0],after[2]))
        for i in range(700):
            motion.tick(.05,player)
            x,y,z=motion.position
            self.assertTrue(can_walk(x,z),(i,x,z))
            self.assertTrue(math.isfinite(y))
        self.assertEqual(motion.clip,'enemy_idle')
        self.assertLessEqual(abs(causeway_progress(player.x,player.z)-motion.progress)*CAUSEWAY_LENGTH,1.16)

    def test_figure_follows_in_both_directions_without_teleporting(self):
        motion=FigureMotion(progress=.7);player=actor(.6)
        before=motion.position;motion.tick(.05,player);after=motion.position
        self.assertLess(motion.progress,.7)
        self.assertLessEqual(math.dist(before,after),BRISK_WALK_SPEED*.05+1e-4)
        self.assertTrue(math.isfinite(motion.yaw))

    def test_pose_review_modes_use_game_speed_but_do_not_move_actor(self):
        motion=FigureMotion();player=actor(.9);at=motion.position
        for mode in ('walk','brisk'):
            motion.mode=mode;motion.phase=0.;motion.tick(.1,player);gait=GAITS['enemy_walk']
            self.assertEqual(motion.position,at)
            self.assertEqual(motion.clip,'enemy_walk');self.assertEqual(motion.pace,mode)
            speed=BRISK_WALK_SPEED if mode=='brisk' else gait['speed']
            self.assertAlmostEqual(motion.phase,.1*speed/(gait['stride']*PLAYER_SCALE))
        motion.paused=True;before=vars(motion).copy();motion.tick(.1,player)
        self.assertEqual(vars(motion),before)

    def test_review_controls_and_timeline_follow_clip_duration(self):
        s=ReviewState();self.assertEqual(s.clip,'enemy_walk')
        self.assertAlmostEqual(s.period,GAITS['enemy_walk']['stride']*PLAYER_SCALE/GAITS['enemy_walk']['speed'])
        s.action('clip:brisk');self.assertEqual(s.clip,'enemy_walk')
        self.assertGreater(BRISK_WALK_SPEED,GAITS['enemy_walk']['speed'])
        self.assertLess(BRISK_WALK_SPEED,GAITS['enemy_run']['speed'])
        self.assertAlmostEqual(s.period,GAITS['enemy_walk']['stride']*PLAYER_SCALE/BRISK_WALK_SPEED)
        s.action('next');self.assertFalse(s.playing);self.assertAlmostEqual(s.phase,.017)
        s.action('clip:idle');s.action('next');self.assertAlmostEqual(s.phase,.017/CLIP_SECONDS['enemy_idle'])
        s.action('portrait');self.assertTrue(s.portrait)
        buttons=controls(s)
        for i,a in enumerate(buttons):
            for b in buttons[i+1:]:self.assertFalse(inside(a[2],b[2][0]+1,b[2][1]+1))


if __name__=='__main__':unittest.main()
