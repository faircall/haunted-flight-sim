"""Camera composition and authoring tests; no window, sound or GPU required."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from g_scene_cameras import CameraValidationError, resolve_shot, sample_shot
from g_huxin_moon_direction import (CameraConflictError, CameraDocument, CameraWatcher,
    DirectionEditor, default_document, load_document, validate_document)


def rig():
    document=default_document();shot=document['shots'][-1]
    shot.update(movement='locked',aim='fixed',lens='fixed',easing='linear',duration=10.,
                start=dict(eye=[0.,3.,10.],target=[0.,2.,0.],fov=60.),
                end=dict(eye=[10.,6.,10.],target=[4.,2.,0.],fov=90.),
                preview=dict(phase='reveal',actor=[0.,0.,0.],yaw=0.),aim_offset=[0.,1.,0.])
    document['shots']=[shot]
    return document,shot


class CompositionTests(unittest.TestCase):
    def test_defaults_reproduce_existing_stations_and_offsets(self):
        from g_huxin_moon import SHOTS
        document=default_document();self.assertEqual(len(document['shots']),22)
        self.assertEqual([s['id'] for s in document['shots']],
                         [f'lake-{i}' for i in range(9)]+[f'room-{i}' for i in range(11)]+['focus','reveal'])
        for actual,expected in zip(document['shots'],SHOTS):
            self.assertEqual(actual['start'],dict(eye=list(expected['eye']),target=list(expected['target']),fov=expected['fov']))
            self.assertEqual(actual['aim_offset'],[0.,.93,0.])
        for actual in document['shots'][9:20]:self.assertEqual(actual['aim_offset'],[0.,.92,0.])
        self.assertEqual(document['shots'][-1]['start'],dict(eye=[18.,7.6,26.],target=[2.,4.5,0.],fov=51.))
        document['shots'][0]['start']['eye'][0]=888
        self.assertEqual(default_document()['shots'][0]['start']['eye'][0],-8.2)

    def test_path_does_not_pan_or_zoom_unless_requested(self):
        document,shot=rig();shot['movement']='path';validate_document(document)
        pose=sample_shot(shot,5)
        self.assertEqual(pose,dict(eye=[5.,4.5,10.],target=[0.,2.,0.],fov=60.))
        shot.update(aim='pan',lens='zoom')
        self.assertEqual(sample_shot(shot,5),dict(eye=[5.,4.5,10.],target=[2.,2.,0.],fov=75.))

    def test_all_default_preview_actors_stand_on_walkable_ground_and_can_move(self):
        from g_huxin_moon_sequence import support
        for shot in default_document()['shots']:
            with self.subTest(shot=shot['id']):
                x,y,z=shot['preview']['actor'];revealed=shot['preview']['phase']=='teahouse'
                height=support(x,z,y,revealed)
                self.assertIsNotNone(height);self.assertAlmostEqual(y,height)
                for dx,dz in ((.08,0),(-.08,0),(0,.08),(0,-.08)):
                    self.assertIsNotNone(support(x+dx,z+dz,y,revealed))
                if shot['preview']['phase']=='reveal':
                    self.assertIsNotNone(support(x,z,y,True))

    def test_pan_and_zoom_do_not_move_eye(self):
        _,shot=rig();shot.update(aim='pan',lens='zoom')
        pose=sample_shot(shot,7.5)
        self.assertEqual(pose['eye'],shot['start']['eye']);self.assertEqual(pose['target'],[3.,2.,0.]);self.assertEqual(pose['fov'],82.5)

    def test_follow_uses_world_axis_anchor_and_keeps_aim_independent(self):
        _,shot=rig();shot['movement']='follow';shot['preview']['actor']=[2.,1.,3.]
        actor=SimpleNamespace(x=5.,height=2.,z=9.,yaw=math.pi/2)
        pose=sample_shot(shot,3,actor)
        self.assertEqual(pose['eye'],[3.,4.,16.]);self.assertEqual(pose['target'],[0.,2.,0.])
        shot['aim']='player';self.assertEqual(sample_shot(shot,3,actor)['target'],[5.,3.,9.])
        shot['preview']['yaw']=2.8;self.assertEqual(sample_shot(shot,3,actor)['eye'],pose['eye'])

    def test_keep_visible_retains_composition_until_actor_leaves_margin(self):
        _,shot=rig();shot['aim']='keep_visible';shot['start']['target']=[0.,1.,0.]
        self.assertEqual(sample_shot(shot,0,[0,0,0])['target'],[0.,1.,0.])
        self.assertEqual(sample_shot(shot,0,[40,0,0])['target'],[40.,1.,0.])
        self.assertEqual(sample_shot(shot,0,[0,0,11])['target'],[0.,1.,11.])

    def test_smooth_easing_and_endpoint_clamping(self):
        _,shot=rig();shot.update(movement='path',easing='smooth')
        self.assertEqual(sample_shot(shot,-1)['eye'],shot['start']['eye'])
        self.assertEqual(sample_shot(shot,100)['eye'],shot['end']['eye'])
        self.assertAlmostEqual(sample_shot(shot,2.5)['eye'][0],1.03515625)

    def test_dynamic_player_target_collision_has_safe_direction(self):
        _,shot=rig();shot['aim']='player'
        pose=sample_shot(shot,0,[0.,2.,10.])
        self.assertAlmostEqual(math.dist(pose['eye'],pose['target']),.25)
        self.assertTrue(all(math.isfinite(v) for v in pose['target']))

    def test_authored_path_crossing_target_is_rejected(self):
        document,shot=rig();shot.update(movement='path')
        shot['start']['eye']=[-1,2,0];shot['end']['eye']=[1,2,0]
        with self.assertRaisesRegex(CameraValidationError,'crosses'):validate_document(document)

    def test_validation_rejects_nonfinite_unknown_and_invalid_activation(self):
        mutations=(lambda s:s['start']['eye'].__setitem__(0,float('nan')),
                   lambda s:s['end'].__setitem__('fov',float('inf')),
                   lambda s:s.update(duration=0),lambda s:s.update(movement='execute'),
                   lambda s:s.update(activation={'type':'lake','index':9}),
                   lambda s:s.update(activation={'type':'reveal','bounds':{}}),
                   lambda s:s.update(activation={'type':'zone','bounds':{'min':[0,0,0],'max':[0,1,1]}}),
                   lambda s:s.update(enabled=1))
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                document,shot=rig();mutate(shot)
                with self.assertRaises(CameraValidationError):validate_document(document)
        document,_=rig();document['shots'].append(deepcopy(document['shots'][0]))
        with self.assertRaisesRegex(CameraValidationError,'duplicate'):validate_document(document)

    def test_zone_priority_phase_and_focus_protection(self):
        document=default_document();zone=deepcopy(document['shots'][0]);zone['id']='porch'
        zone['activation']=dict(type='zone',phase='teahouse',priority=10,bounds={'min':[-2,0,-2],'max':[2,2,2]})
        document['shots'].append(zone);document=validate_document(document)
        self.assertEqual(resolve_shot(document,{'type':'room','index':0},[0,.325,0],'teahouse')['id'],'porch')
        self.assertEqual(resolve_shot(document,{'type':'lake','index':0},[0,.325,0],'lake')['id'],'lake-0')
        self.assertEqual(resolve_shot(document,{'type':'room','index':0},[3,.325,0],'teahouse')['id'],'room-0')
        for kind in ('reveal','focus'):
            self.assertEqual(resolve_shot(document,{'type':kind},[0,.325,0],'teahouse')['id'],kind)
        document['shots'][-1]['enabled']=False
        self.assertEqual(resolve_shot(document,{'type':'room','index':0},[0,.325,0],'teahouse')['id'],'room-0')


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)/'cameras.json'
    def write(self,document):self.path.write_text(json.dumps(document),encoding='utf-8')

    def test_missing_profile_stays_missing_until_explicit_save(self):
        state=DirectionEditor(path=self.path);CameraWatcher(self.path);load_document(self.path)
        self.assertFalse(self.path.exists());self.assertFalse(state.dirty)
        state.change(lambda s:s.update(label='A new composition'));self.assertTrue(state.dirty)
        state.save();self.assertFalse(state.dirty);self.assertEqual(load_document(self.path)['shots'][0]['label'],'A new composition')
        self.assertTrue(self.path.read_text(encoding='utf-8').endswith('\n'))

    def test_atomic_gesture_history_and_validation_rollback(self):
        state=CameraDocument(self.path);original=deepcopy(state.frame);before=state.checkpoint()
        state.frame['eye'][0]+=1;state.frame['eye'][0]+=2;state.commit(before)
        self.assertTrue(state.undo());self.assertEqual(state.frame,original);self.assertFalse(state.undo())
        self.assertTrue(state.redo());self.assertEqual(state.frame['eye'][0],original['eye'][0]+3)
        valid=deepcopy(state.document)
        with self.assertRaises(CameraValidationError):state.change(lambda s:s.update(duration=-20))
        self.assertEqual(state.document,valid)
        with self.assertRaises(CameraValidationError):state.set_frame(dict(eye=[0,0,0],target=[0,0,0],fov=60))
        self.assertEqual(state.document,valid)

    def test_duplicate_priority_and_removal_history_restore_selection(self):
        state=CameraDocument(self.path);identity=state.selected;copy=state.duplicate();copied=copy['id']
        self.assertNotEqual(identity,copied);self.assertEqual(copy['activation']['priority'],1)
        self.assertEqual(resolve_shot(state.document,{'type':'lake','index':0},[0,0,0],'lake')['id'],copied)
        state.undo();self.assertEqual(state.selected,identity);self.assertEqual(len(state.document['shots']),22)
        state.redo();self.assertEqual(state.selected,copied)
        state.remove();self.assertNotEqual(state.selected,copied);state.undo();self.assertEqual(state.selected,copied)
        tiny,_=rig();single=CameraDocument(self.path,document=tiny)
        with self.assertRaises(ValueError):single.remove()

    def test_selection_keys_and_looped_timeline(self):
        state=CameraDocument(self.path);state.select('reveal');state.key='end'
        self.assertEqual(state.elapsed,24);state.seek(5);self.assertEqual(state.key,'end')
        state.loop=True;state.playing=True;state.tick(25);self.assertEqual(state.elapsed,6)
        state.loop=False;state.tick(25);self.assertEqual(state.elapsed,24);self.assertFalse(state.playing)
        state.select(0);self.assertEqual(state.key,'start');self.assertEqual(state.elapsed,0)

    def test_external_save_conflict_never_overwrites_without_explicit_choice(self):
        state=CameraDocument(self.path);state.save();state.change(lambda s:s.update(label='Mine'))
        external=default_document();external['shots'][0]['label']='Outside';self.write(external)
        with self.assertRaises(CameraConflictError):state.save()
        self.assertEqual(load_document(self.path)['shots'][0]['label'],'Outside');self.assertTrue(state.conflict)
        state.save(force=True);self.assertEqual(load_document(self.path)['shots'][0]['label'],'Mine');self.assertFalse(state.conflict)

    def test_failed_atomic_replace_keeps_original_and_cleans_temporary(self):
        state=CameraDocument(self.path);state.save();original=self.path.read_bytes()
        state.change(lambda s:s.update(label='Unsaved'))
        with patch('g_huxin_moon_direction.os.replace',side_effect=PermissionError('busy')):
            with self.assertRaises(PermissionError):state.save()
        self.assertEqual(self.path.read_bytes(),original);self.assertTrue(state.dirty)
        self.assertEqual(list(self.path.parent.iterdir()),[self.path])

    def test_watcher_retains_last_good_on_partial_write_and_recovers(self):
        watcher=CameraWatcher(self.path);external=default_document();external['shots'][0]['label']='New';self.write(external)
        self.assertTrue(watcher.poll(force=True));signature=watcher.signature
        self.path.write_text('{"shots":',encoding='utf-8');self.assertFalse(watcher.poll(force=True))
        self.assertEqual(watcher.document['shots'][0]['label'],'New');self.assertEqual(watcher.signature,signature);self.assertTrue(watcher.error)
        external['shots'][0]['label']='Repaired';self.write(external)
        self.assertTrue(watcher.poll(force=True));self.assertIsNone(watcher.error)
        self.path.unlink();self.assertTrue(watcher.poll(force=True));self.assertEqual(watcher.document,default_document())

    def test_bad_initial_file_and_duplicate_json_keys_are_safe(self):
        self.path.write_text('{"version":1,"version":1}',encoding='utf-8')
        watcher=CameraWatcher(self.path);self.assertEqual(watcher.document,default_document());self.assertTrue(watcher.error)
        state=CameraDocument(self.path);self.assertTrue(state.error)
        with self.assertRaises(CameraConflictError):state.save()
        self.path.write_text('__import__("os").system("bad")',encoding='utf-8')
        with self.assertRaises(CameraValidationError):load_document(self.path)

    def test_clean_live_reload_preserves_selection_time_and_dirty_conflict(self):
        state=CameraDocument(self.path);state.save();state.select('reveal');state.key='end';state.seek(7);state.playing=True
        external=default_document();external['shots'][-1]['label']='Collaborator';self.write(external)
        self.assertTrue(state.poll(force=True));self.assertEqual(state.selected,'reveal');self.assertEqual(state.key,'end')
        self.assertEqual(state.elapsed,7);self.assertTrue(state.playing);self.assertFalse(state.dirty)
        state.change(lambda s:s.update(label='Local'));external['shots'][-1]['label']='Another change';self.write(external)
        self.assertFalse(state.poll(force=True));self.assertTrue(state.conflict);self.assertEqual(state.shot['label'],'Local')
        state.reload();self.assertEqual(state.shot['label'],'Another change');self.assertFalse(state.dirty)
        state.undo();self.assertEqual(state.shot['label'],'Local');self.assertTrue(state.dirty)

    def test_invalid_reload_preserves_edits_and_discard_restores_saved(self):
        state=CameraDocument(self.path);state.save();state.change(lambda s:s.update(label='Local'))
        self.path.write_text('{',encoding='utf-8');before=deepcopy(state.document)
        with self.assertRaises(CameraValidationError):state.reload()
        self.assertEqual(state.document,before);state.discard();self.assertFalse(state.dirty)


if __name__=='__main__':unittest.main()
