"""Viewer timing and UI controls must inspect the same samples as the game."""
import unittest
from animation_viewer_3d import Playback,controls,click,TIMELINE


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.state=Playback(dict(idle=2.,walk=1.,run=1.),dict(idle=118,walk=59,run=59))

    def test_playback_speed_and_pause_use_game_cadence(self):
        s=self.state;s.advance(s.period/4)
        self.assertAlmostEqual(s.phase,.25)
        s.action('play');s.advance(10)
        self.assertAlmostEqual(s.phase,.25)
        s.action('speed:0.25');s.action('play');s.advance(s.period)
        self.assertAlmostEqual(s.phase,.5)

    def test_steps_pause_and_wrap_native_samples_in_both_directions(self):
        s=self.state;s.step(-1)
        self.assertFalse(s.playing);self.assertEqual(s.frame,58)
        s.step(1);self.assertEqual(s.frame,0)
        for frame in range(1,59):s.step(1);self.assertEqual(s.frame,frame)

    def test_scrubbing_to_right_edge_stays_on_last_frame(self):
        s=self.state;s.scrub(1.)
        self.assertEqual(s.frame,58);self.assertLess(s.phase,1.)
        s.advance(10);self.assertEqual(s.frame,58)
        s.scrub(-.5);self.assertEqual(s.frame,0)

    def test_running_steps_inspect_source_samples_at_a_different_game_cadence(self):
        s=self.state;s.action('clip:run');s.step(20)
        self.assertEqual(s.frame,20)
        self.assertAlmostEqual(s.phase,20*.017/s.source_seconds['run'])
        self.assertNotAlmostEqual(s.period,s.source_seconds['run'])
        s.scrub(1.);self.assertEqual(s.frame,58)
        s.step(1);self.assertEqual(s.frame,0)

    def test_clip_buttons_and_timeline_use_their_drawn_hit_regions(self):
        s=self.state
        for clip in ('idle','run','walk'):
            _,_,r,_=next(b for b in controls(s) if b[0]=='clip:'+clip)
            self.assertTrue(click(s,r[0]+5,r[1]+5));self.assertEqual(s.clip,clip)
            self.assertEqual(s.phase,0.)
        x,y,w,h=TIMELINE
        self.assertTrue(click(s,x+w*.5,y+h*.5));self.assertEqual(s.frame,29)
        self.assertFalse(click(s,-1,-1))

    def test_camera_presets_and_overlays_do_not_change_pose(self):
        s=self.state;s.scrub(.7);frame=s.frame
        for action in ('view:front','skeleton','trails','pixels','ground_motion'):
            s.action(action);self.assertEqual(s.frame,frame)
        self.assertEqual(s.azimuth,0.);self.assertTrue(s.skeleton)
        self.assertTrue(s.trails);self.assertFalse(s.pixels)


if __name__=='__main__':unittest.main()
