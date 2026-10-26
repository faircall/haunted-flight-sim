"""Authored shot playback and editor/game state boundaries, without a GPU."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from g_huxin_moon import Explorer,DECK
from g_huxin_moon_sequence import MoonSequence
from g_huxin_moon_direction import default_document
from huxin_moon_camera import wide_reveal_camera,interior_camera
from huxin_moon_camera_runtime import MoonCameraDirector
from huxin_moon_viewer import Lake,auto_camera,edit_cameras
from temple_interior_viewer import camera


def values(cam):
    return tuple(getattr(v,axis) for v in (cam.position,cam.target) for axis in ('x','y','z'))+(cam.fovy,)


class MoonCinematographerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'cameras.json'
        self.actor=Explorer();self.actor.x=self.actor.z=1.65;self.actor.height=DECK
        self.scene=object.__new__(Lake);self.scene.sequence=MoonSequence()
        self.actor.encounter=self.scene.sequence;self.scene.targeted=True
        self.scene.last_camera=None;self.scene.last_shot=0;self.scene._authored_hold=False
        self.scene.camera_director=MoonCameraDirector(self.path)

    def write(self,document):
        self.path.write_text(json.dumps(document),encoding='utf-8')
        self.scene.camera_director.reload(force=True)

    def test_missing_profile_preserves_existing_camera_compositions(self):
        q=self.scene.sequence;q.state='entering';q.elapsed=8.
        self.assertEqual(values(self.scene._select_camera(self.actor,8.)[1]),values(wide_reveal_camera()[1]))
        q.state='revealed';q.revealed=True;q.locked_camera=None;self.scene._authored_hold=False
        self.assertEqual(values(self.scene._select_camera(self.actor,24.)[1]),values(interior_camera(self.actor)[1]))
        q.state='ordinary';q.revealed=False;self.actor.x=-12.;self.actor.z=76.;self.actor.tick(0.)
        self.assertEqual(values(self.scene._select_camera(self.actor,30.)[1]),values(auto_camera(self.actor)[1]))
        self.assertFalse(self.path.exists())

    def test_authored_reveal_is_used_during_transition_and_live_reload_updates_held_view(self):
        doc=default_document();shot=next(s for s in doc['shots'] if s['activation']['type']=='reveal')
        shot['start']['eye']=[13.,8.,21.];shot['start']['fov']=63.
        self.write(doc);q=self.scene.sequence;q.state='entering';q.elapsed=8.
        _,first=self.scene._select_camera(self.actor,100.)
        self.assertEqual((first.position.x,first.position.y,first.position.z,first.fovy),(13.,8.,21.,63.))
        q.state='revealed';q.revealed=True;q.elapsed=24.
        q.inventory[0]={'kind':'kept-object'};before=deepcopy(q.inventory)
        shot['start']['eye'][0]=15.;self.write(doc)
        _,held=self.scene._select_camera(self.actor,120.)
        self.assertEqual(held.position.x,15.);self.assertEqual(q.inventory,before)
        self.actor.x+=.1
        _,released=self.scene._select_camera(self.actor,120.1)
        self.assertEqual(values(released),values(interior_camera(self.actor)[1]))

    def test_zone_camera_runs_from_activation_and_restarts_after_reentry(self):
        doc=default_document();shot=deepcopy(doc['shots'][0]);shot['id']='runtime-zone';shot['label']='Runtime zone'
        shot['enabled']=True;shot['duration']=4.;shot['movement']='path';shot['aim']='fixed';shot['easing']='linear'
        shot['start']={'eye':[10.,5.,10.],'target':[0.,1.,0.],'fov':60.}
        shot['end']={'eye':[14.,5.,10.],'target':[0.,1.,0.],'fov':60.}
        shot['activation']={'type':'zone','priority':100,'phase':'any','bounds':{'min':[-2.,-1.,-2.],'max':[3.,3.,3.]}}
        doc['shots'].append(shot);self.write(doc);director=self.scene.camera_director;q=self.scene.sequence
        a=director.camera({'type':'lake','index':5},self.actor,q,10.)
        b=director.camera({'type':'lake','index':5},self.actor,q,12.)
        self.assertEqual(a[0],'runtime-zone');self.assertEqual(a[1]['eye'][0],10.);self.assertEqual(b[1]['eye'][0],12.)
        self.actor.z=20.;director.camera({'type':'lake','index':3},self.actor,q,13.)
        self.actor.z=1.65;c=director.camera({'type':'lake','index':5},self.actor,q,14.)
        self.assertEqual(c[1]['eye'][0],10.)

    def test_partial_external_file_retains_valid_shots_until_repaired(self):
        doc=default_document();self.write(doc);director=self.scene.camera_director
        valid=deepcopy(director.document);self.path.write_text('{"version":',encoding='utf-8')
        director.reload(force=True)
        self.assertEqual(director.document,valid);self.assertTrue(director.error)
        self.write(doc);self.assertFalse(director.error)

    def test_number_key_camera_uses_saved_rig_and_does_not_restart_its_path(self):
        doc=default_document();shot=next(s for s in doc['shots'] if s['activation'].get('type')=='room' and s['activation'].get('index')==6)
        shot['movement']='path';shot['aim']='fixed';shot['duration']=4.;shot['easing']='linear'
        shot['start']['eye']=[20.,9.,24.];shot['end']['eye']=[24.,9.,24.]
        zone=deepcopy(shot);zone['id']='manual-test-zone'
        zone['activation']={'type':'zone','priority':100,'phase':'any','bounds':{'min':[-3.,-1.,-3.],'max':[3.,3.,3.]}}
        zone['start']['eye'][0]=100.;doc['shots'].append(zone)
        self.write(doc);self.scene.sequence.state='revealed';self.scene.sequence.revealed=True
        index,first=self.scene._select_camera(self.actor,10.,manual_shot=6)
        _,middle=self.scene._select_camera(self.actor,12.,manual_shot=6)
        self.assertEqual(index,6);self.assertEqual(first.position.x,20.);self.assertEqual(middle.position.x,22.)

    def test_editor_camera_bypasses_gameplay_director_without_changing_live_sequence(self):
        q=self.scene.sequence;q.state='entering';q.elapsed=8.;before=deepcopy(vars(q))
        authored=camera((9,4,11),(0,1,0),70)
        with patch.object(self.scene.camera_director,'camera',side_effect=AssertionError('Preview called runtime director')):
            shot,cam=self.scene._select_camera(self.actor,123.,override=authored,authoring=True)
        self.assertEqual(shot,-1);self.assertEqual(values(cam),values(authored));self.assertEqual(vars(q),before)

    def test_modal_finally_restores_game_context_and_consumes_closing_escape(self):
        scene=self.scene;q=scene.sequence;q.elapsed=7.;q.inventory[0]={'id':'kept'}
        actor_before=deepcopy(vars(self.actor));original_camera=camera((1,2,3),(0,0,0),60);scene.last_camera=original_camera
        api=Mock();api.get_screen_width.return_value=1280;api.get_screen_height.return_value=720
        api.is_window_state.return_value=False
        def runner(actual,actor,clock,path):
            self.assertIs(actual,scene);self.assertEqual(path,self.path)
            actual.sequence=MoonSequence();actual.last_camera=None;actual.last_shot=999;actual._authored_hold=True
            raise RuntimeError('Editor failed')
        with patch('huxin_moon_viewer.pr',api):
            with self.assertRaisesRegex(RuntimeError,'Editor failed'):edit_cameras(scene,self.actor,None,12.,runner)
        self.assertIs(scene.sequence,q);self.assertIs(scene.last_camera,original_camera)
        self.assertEqual(scene.last_shot,0);self.assertFalse(scene._authored_hold)
        self.assertEqual(q.elapsed,7.);self.assertEqual(q.inventory[0],{'id':'kept'})
        self.assertEqual(self.actor.x,actor_before['x']);self.assertEqual(self.actor.z,actor_before['z'])
        api.poll_input_events.assert_called_once();api.set_window_size.assert_any_call(1280,720)


if __name__=='__main__':unittest.main()
