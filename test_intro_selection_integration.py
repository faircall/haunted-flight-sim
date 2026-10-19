"""Input ownership through the regular intro loop, with hidden/muted output."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ['HAUNTED_MUTE_AUDIO']='1'
import pyray as pr
import temple_intro_viewer as viewer


class IntroSelectionTests(unittest.TestCase):
    def test_toggle_frames_freeze_ride_and_preserve_existing_pause(self):
        frames=[];audio_frames=[];current=[-1]
        keys={1:{pr.KEY_F8,pr.KEY_ENTER,pr.KEY_F2},
              2:{pr.KEY_ENTER,pr.KEY_HOME,pr.KEY_F2},3:{pr.KEY_ESCAPE},
              5:{pr.KEY_ESCAPE},6:{pr.KEY_F8},7:{pr.KEY_ESCAPE},8:{pr.KEY_ESCAPE}}
        def should_close():
            current[0]+=1
            return current[0]>=9
        class Preview:
            def __init__(self):
                self.fonts={};self.frame=pr.load_render_texture(480,270)
                self.codex_selection=None;self.car_height=0.;self.car_pitch=0.
            def render(self,intro,*args,**kwargs):
                frames.append((intro.elapsed,intro.yaw,intro.pitch,intro.paused,self.codex_selection.enabled))
                self.codex_selection.begin_frame()
                pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.end_texture_mode()
                return pr.Camera3D(pr.Vector3(0,1,3),pr.Vector3(0,1,0),pr.Vector3(0,1,0),55,0)
            def close(self):pr.unload_render_texture(self.frame)
        class SilentAudio:
            def __init__(self,automated=False):pass
            def update(self,intro):audio_frames.append(intro.paused)
            def close(self):pass
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'selection.json'
            pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
            with patch.object(viewer,'View',Preview),patch.object(viewer,'Audio',SilentAudio),\
                 patch.object(viewer.text,'font'),patch('codex_selection.DEFAULT_PATH',target),\
                 patch.object(pr,'window_should_close',side_effect=should_close),\
                 patch.object(pr,'is_key_pressed',side_effect=lambda key:key in keys.get(current[0],set())),\
                 patch.object(pr,'is_mouse_button_pressed',return_value=False),\
                 patch.object(pr,'get_frame_time',return_value=.02),\
                 patch.object(pr,'get_mouse_delta',return_value=pr.Vector2(0,0)):
                self.assertEqual(viewer.run_intro(),'quit')
            self.assertTrue(target.exists())
        self.assertEqual(len(frames),9)
        self.assertEqual(frames[0][:3],frames[1][:3])
        self.assertEqual(frames[1][:3],frames[2][:3])
        self.assertEqual(frames[2][:3],frames[3][:3])
        self.assertTrue(frames[1][4]);self.assertTrue(frames[2][4])
        self.assertFalse(frames[3][3]);self.assertFalse(frames[3][4])
        self.assertGreater(frames[4][0],frames[3][0])
        self.assertTrue(frames[5][3]);self.assertTrue(frames[6][3])
        self.assertTrue(frames[7][3]);self.assertFalse(frames[7][4])
        self.assertFalse(frames[8][3])
        self.assertTrue(audio_frames[1]);self.assertTrue(audio_frames[2])
        self.assertFalse(audio_frames[3]);self.assertTrue(audio_frames[7])


if __name__=='__main__':unittest.main()
