"""Camera authoring, data integrity and persistence into the actual intro script."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from g_cinematics_editor import Cinematics
from g_temple_intro import Intro,load_script,validate_script
from g_temple_cinematics import default_camera,fly_pose,orbit_pose,sample_camera


def fixture_document():
    # Tests must keep passing after an artist saves different cameras or cuts.
    shots=[('rear-window-portrait','opening',0,7),('dispatch-conversation','interior',7,44),('over-the-road','drone',44,56),
           ('temple-stories','interior',56,95),('night-falls','tracking',95,114),('approaching-the-temple','interior',114,135),('arrival','arrival',135,142)]
    return dict(duration=142,place_name='Water-Moon Temple',sign='水月寺',
                shots=[dict(id=name,kind=kind,start=start,end=end) for name,kind,start,end in shots],
                lines=[dict(start=7,end=13,speaker='DRIVER',text='Test dialogue.')])


class CinematicsTests(unittest.TestCase):
    def setUp(self):self.editor=Cinematics(fixture_document())

    def test_default_pose_matches_the_existing_exterior_compositions(self):
        for shot in self.editor.document['shots']:
            sample=sample_camera(shot,shot['start'])
            self.assertEqual(sample,default_camera(shot['kind'])['start'])
            self.assertEqual(sample_camera(shot,shot['end']),default_camera(shot['kind'])['end'])

    def test_camera_keys_interpolate_and_zoom_without_mutating_the_document(self):
        editor=self.editor;editor.select(2);before=editor.checkpoint();camera=editor.shot['camera']
        camera['ease']='linear';camera['end']['fov']=80
        frame=sample_camera(editor.shot,(editor.shot['start']+editor.shot['end'])/2)
        self.assertEqual(frame['fov'],64)
        self.assertEqual(frame['eye'],[(a+b)/2 for a,b in zip(camera['start']['eye'],camera['end']['eye'])])
        self.assertNotEqual(editor.document,before)
        sampled_before=editor.checkpoint();sample_camera(editor.shot,-100);self.assertEqual(editor.document,sampled_before)

    def test_invalid_camera_values_roll_back_and_cannot_replace_a_good_save(self):
        editor=self.editor;before=editor.checkpoint()
        for value in (float('nan'),float('inf'),0,120):
            frame=deepcopy(editor.frame);frame['fov']=value
            with self.assertRaises(ValueError):editor.set_frame(frame)
            self.assertEqual(editor.document,before)
        frame=deepcopy(editor.frame);frame['target']=frame['eye'][:]
        with self.assertRaises(ValueError):editor.set_frame(frame)
        self.assertEqual(editor.document,before)

    def test_camera_flight_preserves_target_distance_and_has_frame_independent_speed(self):
        frame=default_camera('tracking')['start'];results=[]
        for dt in (.02,.05,.1):
            result=deepcopy(frame)
            for _ in range(round(1/dt)):result=fly_pose(result,movement=(0,1,0),dt=dt,speed=2)
            results.append(result)
            self.assertAlmostEqual(math.dist(frame['eye'],result['eye']),2)
            self.assertAlmostEqual(math.dist(result['eye'],result['target']),math.dist(frame['eye'],frame['target']))
        for result in results[1:]:self.assertLess(math.dist(results[0]['eye'],result['eye']),1e-10)
        result=fly_pose(frame,(0,-10000));self.assertTrue(all(math.isfinite(v) for v in result['target']))

    def test_orbit_and_pan_keep_a_coherent_look_at_camera(self):
        frame=default_camera('drone')['start'];result=orbit_pose(frame,(30,12))
        self.assertEqual(result['target'],frame['target'])
        self.assertAlmostEqual(math.dist(result['eye'],result['target']),math.dist(frame['eye'],frame['target']))
        result=orbit_pose(frame,(10,4),pan=True)
        for i in range(3):self.assertAlmostEqual(result['eye'][i]-frame['eye'][i],result['target'][i]-frame['target'][i])

    def test_a_gesture_is_one_undo_and_redo_restores_it(self):
        editor=self.editor;before=editor.checkpoint()
        editor.frame['eye'][0]+=1;editor.frame['eye'][1]+=.2;editor.commit(before);changed=editor.checkpoint()
        self.assertEqual(len(editor.undo_stack),1);self.assertTrue(editor.dirty)
        self.assertTrue(editor.undo());self.assertEqual(editor.document,before);self.assertFalse(editor.dirty)
        self.assertTrue(editor.redo());self.assertEqual(editor.document,changed)
        editor.undo();editor.match_keys();self.assertFalse(editor.redo_stack)

    def test_cut_edits_preserve_coverage_dialogue_and_night_transition(self):
        editor=self.editor;lines=deepcopy(editor.document['lines'])
        editor.set_cut(2,47.5);self.assertEqual(editor.document['shots'][1]['end'],47.5)
        self.assertEqual(editor.document['shots'][2]['start'],47.5);self.assertEqual(editor.document['lines'],lines)
        editor.set_cut(2,200);self.assertEqual(editor.document['shots'][2]['start'],55)
        validate_script(editor.document)
        editor.set_cut(5,110);intro=Intro(editor.document,elapsed=110)
        self.assertEqual(intro.dusk,1);self.assertEqual(intro.headlights,1)

    def test_split_meets_at_the_cut_and_remove_keeps_full_coverage(self):
        editor=self.editor;editor.seek(50);before=editor.checkpoint();expected=sample_camera(editor.shot,50)
        editor.split();shots=editor.document['shots'];self.assertEqual(len(shots),8)
        self.assertEqual(shots[2]['camera']['end'],expected);self.assertEqual(shots[3]['camera']['start'],expected)
        editor.remove();self.assertEqual(len(editor.document['shots']),7);validate_script(editor.document)
        editor.undo();editor.undo();self.assertEqual(editor.document,before)

    def test_night_transition_is_preserved_when_other_shots_are_removed(self):
        editor=self.editor;editor.seek(102)
        with self.assertRaises(ValueError):editor.remove()
        with self.assertRaises(ValueError):editor.split()
        editor.select(0);editor.remove();validate_script(editor.document)
        self.assertEqual(editor.document['shots'][0]['start'],0)

    def test_seek_loop_pause_and_end_of_playback(self):
        editor=self.editor;editor.seek(102);editor.loop=True;editor.playing=True;editor.elapsed=113.98
        editor.tick(.05);self.assertAlmostEqual(editor.elapsed,95.03);self.assertEqual(editor.selected,4)
        editor.playing=False;editor.tick(.05);self.assertAlmostEqual(editor.elapsed,95.03)
        editor.loop=False;editor.playing=True;editor.elapsed=141.98;editor.tick(.05)
        self.assertFalse(editor.playing);self.assertLess(editor.elapsed,142)
        editor.seek(-100);self.assertEqual(editor.elapsed,0);editor.seek(1000);self.assertLess(editor.elapsed,142)

    def test_atomic_save_reload_and_undo_feed_normal_game_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'shots.json';editor=Cinematics(fixture_document(),path);editor.select(2,'end')
            frame=deepcopy(editor.frame);frame['eye'][0]+=2;frame['fov']=54;editor.set_frame(frame);editor.save()
            saved=path.read_bytes();self.assertFalse(editor.dirty);self.assertFalse(path.with_suffix('.json.tmp').exists())
            self.assertNotIn(b'\r\n',saved)
            loaded=load_script(path);state=Intro(loaded,elapsed=56-1e-5)
            self.assertAlmostEqual(sample_camera(state.shot,state.elapsed)['fov'],54)
            self.assertAlmostEqual(sample_camera(state.shot,state.elapsed)['eye'][0],frame['eye'][0])
            editor.frame['fov']=0
            with self.assertRaises(ValueError):editor.save()
            self.assertEqual(path.read_bytes(),saved)
            editor.frame['fov']=70;editor.reload();self.assertEqual(editor.document,loaded);self.assertFalse(editor.dirty)
            editor.undo();self.assertTrue(editor.dirty);editor.redo();self.assertFalse(editor.dirty)
            self.assertIn('水月寺',path.read_text(encoding='utf-8'))

    def test_fixed_interior_camera_does_not_capture_player_look_input(self):
        editor=self.editor;editor.select(1);editor.shot['camera']['mode']='fixed'
        state=Intro(editor.document,elapsed=17);state.tick(0,(500,500))
        self.assertEqual((state.yaw,state.pitch),(0,-8))
        editor.shot['camera']['mode']='interactive';state.tick(0,(100,-100))
        self.assertAlmostEqual(state.yaw,14)

    def test_crossing_a_look_at_point_remains_finite_and_renderable(self):
        shot=deepcopy(self.editor.document['shots'][2]);shot['camera']['start']['eye']=[-2,1,0]
        shot['camera']['end']['eye']=[2,1,0]
        for key in ('start','end'):shot['camera'][key]['target']=[0,1,0]
        frame=sample_camera(shot,(shot['start']+shot['end'])/2)
        self.assertGreaterEqual(math.dist(frame['eye'],frame['target']),.0499)


if __name__=='__main__':unittest.main()
