"""Scene-state integration for authored camera memory; no rendering or audio."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from g_huxin_moon import Explorer
from g_huxin_moon_sequence import MoonSequence
from g_huxin_moon_direction import default_document
from huxin_moon_camera_runtime import MoonCameraDirector, moon_camera_facts
from huxin_moon_viewer import Lake, gameplay_camera, safety_camera, edit_cameras


def pose(cam):return tuple(getattr(v,k) for v in (cam.position,cam.target) for k in ('x','y','z'))+(cam.fovy,)


class MoonDirectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'cameras.json'
        self.doc=default_document();self.actor=Explorer();self.q=MoonSequence()
        self.actor.encounter=self.q
        self.director=MoonCameraDirector(self.path)
        self.scene=object.__new__(Lake);self.scene.sequence=self.q
        self.scene.targeted=True;self.scene.camera_director=self.director
        self.scene._authored_hold=False;self.scene.last_camera=None;self.scene.last_shot=0

    def write(self):
        self.path.write_text(json.dumps(self.doc),encoding='utf-8');self.director.reload(force=True)

    def tracking(self):
        shot=deepcopy(self.doc['shots'][0]);shot['id']='story-tracking'
        shot['activation']={'type':'rule','phase':'any','priority':20}
        shot['movement']='follow';shot['aim']='player'
        shot['rule'].update(start_event='scene.start',hold='event',release_event='scene.end',repeat='run')
        self.doc['shots'].append(shot);return shot

    def test_disabled_and_deleted_base_stations_never_resurrect(self):
        self.write();before=self.scene._select_camera(self.actor,0.)
        identity=self.director.active_id
        next(s for s in self.doc['shots'] if s['id']==identity)['enabled']=False
        self.write();after=self.scene._select_camera(self.actor,1.)
        self.assertNotEqual(self.director.active_id,identity)
        self.assertNotEqual(pose(before[1]),pose(after[1]))
        self.doc['shots']=[s for s in self.doc['shots'] if s['activation']['type']!='lake']
        for shot in self.doc['shots']:shot['enabled']=False
        self.write();index,cam=self.scene._select_camera(self.actor,2.)
        self.assertEqual(index,-1);self.assertEqual(pose(cam),pose(safety_camera(self.actor)[1]))
        self.assertIsNone(self.director.active_id)

    def test_rules_can_run_when_all_indexed_cameras_are_disabled(self):
        for shot in self.doc['shots']:shot['enabled']=False
        shot=self.tracking();shot['enabled']=True;self.write()
        self.director.emit('scene.start');self.scene._select_camera(self.actor,0.)
        self.assertEqual(self.director.active_id,shot['id'])

    def test_disabling_special_shots_uses_gameplay_and_clears_reveal_lock(self):
        self.q.state='entering';self.q.elapsed=4.;self.write()
        self.scene._select_camera(self.actor,0.);self.assertTrue(self.scene._authored_hold)
        for shot in self.doc['shots']:
            if shot['activation']['type'] in ('focus','reveal'):shot['enabled']=False
        self.write();self.scene._select_camera(self.actor,1.)
        self.assertFalse(self.scene._authored_hold);self.assertIsNone(self.q.locked_camera)
        self.assertNotEqual(self.director.active_id,'reveal')
        self.q.state='ordinary';self.q.focus=True
        self.scene._select_camera(self.actor,2.);self.assertNotEqual(self.director.active_id,'focus')

    def test_game_facts_are_read_only_and_events_do_not_consume_audio_queue(self):
        before=deepcopy(vars(self.q));facts=moon_camera_facts(self.q,self.actor)
        self.assertFalse(facts['puzzle.solved']);self.assertEqual(vars(self.q),before)
        self.director.camera({'type':'lake','index':0},self.actor,self.q,0.)
        self.q.state='entering';self.q.bells=1;self.q.events=['bell'];self.q.elapsed=1.
        self.director.camera({'type':'reveal'},self.actor,self.q,1.)
        self.assertIn('puzzle.solved',self.director.engine.events);self.assertEqual(self.q.events,['bell'])
        self.q.revealed=True
        self.director.camera({'type':'reveal'},self.actor,self.q,2.)
        self.assertIn('world.revealed',self.director.engine.events)
        self.assertNotIn('puzzle.solved',self.director.engine.events)
        self.q.state='returned';self.q.revealed=False;self.q.elapsed=0.
        self.director.camera({'type':'lake','index':0},self.actor,self.q,3.)
        self.assertTrue(self.director.engine.facts['puzzle.solved'])
        self.assertIn('world.returned',self.director.engine.events)

    def test_hot_reload_keeps_running_clock_and_once_memory(self):
        shot=self.tracking();self.write();self.director.emit('scene.start')
        trigger={'type':'lake','index':0}
        self.director.camera(trigger,self.actor,self.q,10.);self.assertEqual(self.director.started,10.)
        self.doc['shots'][1]['label']='An unrelated edit';self.write()
        self.director.camera(trigger,self.actor,self.q,12.)
        self.assertEqual(self.director.active_id,shot['id']);self.assertEqual(self.director.started,10.)
        self.director.emit('scene.end');self.director.camera(trigger,self.actor,self.q,13.)
        self.assertNotEqual(self.director.active_id,shot['id'])
        self.director.reload(force=True);self.director.emit('scene.start')
        self.director.camera(trigger,self.actor,self.q,14.)
        self.assertNotEqual(self.director.active_id,shot['id'])

    def test_preview_and_exported_memory_are_isolated_from_gameplay(self):
        shot=self.tracking();self.write();self.director.emit('scene.start')
        trigger={'type':'lake','index':0};self.director.camera(trigger,self.actor,self.q,1.)
        self.director.remember('story.visited',True);saved=self.director.snapshot_memory()
        preview=MoonCameraDirector(document=self.doc)
        preview.fact_overrides['puzzle.solved']=True
        preview.camera(trigger,self.actor,self.q,2.)
        self.assertTrue(preview.engine.facts['puzzle.solved']);self.assertFalse(self.q.bells)
        self.assertEqual(self.director.snapshot_memory(),saved)
        restored=MoonCameraDirector(document=self.doc);restored.restore_memory(json.loads(json.dumps(saved)))
        restored.emit('scene.start');restored.camera(trigger,self.actor,self.q,3.)
        self.assertNotEqual(restored.active_id,shot['id']);self.assertTrue(restored.engine.facts['story.visited'])
        restored.reset(clear_memory=True);restored.emit('scene.start')
        restored.camera(trigger,self.actor,self.q,4.);self.assertEqual(restored.active_id,shot['id'])

    def test_custom_scene_facts_and_event_hooks(self):
        shot=self.tracking();shot['rule']['conditions']=[{'fact':'story.secret_seen','op':'eq','value':True}]
        director=MoonCameraDirector(document=self.doc)
        director.register_fact_provider(lambda actor,sequence:{'story.secret_seen':sequence.inventory[0] is not None})
        self.q.inventory[0]={'id':'secret'};before=deepcopy(self.q.inventory)
        director.emit('scene.start');director.camera({'type':'lake','index':0},self.actor,self.q,1.)
        self.assertEqual(director.active_id,shot['id']);self.assertEqual(self.q.inventory,before)

    def test_combined_provider_limit_reports_error_without_breaking_playback(self):
        director=MoonCameraDirector(document=self.doc)
        director.register_fact_provider(lambda actor,sequence:{f'first.{i}':i for i in range(300)})
        director.register_fact_provider(lambda actor,sequence:{f'second.{i}':i for i in range(300)})
        result=director.camera({'type':'lake','index':0},self.actor,self.q,1.)
        self.assertIsNotNone(result);self.assertIn('combined limit',director.error)
        self.assertIn('first.299',director.engine.facts);self.assertNotIn('second.0',director.engine.facts)

    def test_new_visit_preserves_story_but_does_not_invent_phase_change_events(self):
        self.q.revealed=True;self.q.bells=1;self.q.state='revealed'
        self.director.camera({'type':'room','index':0},self.actor,self.q,1.)
        self.director.remember('story.visited',True);self.director.new_visit()
        self.q=MoonSequence();self.actor.encounter=self.q
        self.director.camera({'type':'lake','index':0},self.actor,self.q,2.)
        self.assertNotIn('world.returned',self.director.engine.events)
        self.assertTrue(self.director.engine.facts['story.visited'])

    def test_manual_number_can_leave_an_indexed_hold_without_resetting_next_move(self):
        first=self.doc['shots'][0];first['rule'].update(hold='event',release_event='end',min_hold=60.)
        second=self.doc['shots'][1];second.update(movement='path',easing='linear',duration=10.)
        second['end']['eye'][0]+=10.
        self.write();self.scene._select_camera(self.actor,0.,manual_shot=0)
        _,start=self.scene._select_camera(self.actor,1.,manual_shot=1)
        self.assertEqual(self.director.active_id,second['id'])
        _,later=self.scene._select_camera(self.actor,3.,manual_shot=1)
        self.assertAlmostEqual(later.position.x-start.position.x,2.,places=5)

    def test_failed_editor_restores_live_director_and_its_memory(self):
        original=self.director;original.remember('story.visited',True)
        before=original.snapshot_memory();api=Mock()
        api.get_screen_width.return_value=1280;api.get_screen_height.return_value=720
        api.is_window_state.return_value=False
        def fail(scene,actor,clock,path):
            scene.camera_director=MoonCameraDirector(document=self.doc)
            raise RuntimeError('Preview constructor failed')
        with patch('huxin_moon_viewer.pr',api):
            with self.assertRaises(RuntimeError):edit_cameras(self.scene,self.actor,None,0.,fail)
        self.assertIs(self.scene.camera_director,original)
        self.assertEqual(original.snapshot_memory(),before)


if __name__=='__main__':unittest.main()
