"""Authoring transactions and saved directions consumed by actual gameplay."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from g_huxin_canals_direction import (default_document, building_document, load_direction,
                                     profile_from_document, sample_camera)
from g_huxin_canals_editor import DirectionEditor, pick_target_bounds
from g_huxin_canals_sequence import CanalSequence
from g_huxin_canals_particles import particles_at, particle_schedule


class DirectionEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='haunted-canals-editor-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'direction.json'
        self.editor = DirectionEditor(document=default_document(), path=self.path)

    def test_seek_and_cue_jumps_do_not_edit_or_accumulate_history(self):
        editor = self.editor
        before = editor.checkpoint()
        for cue, elapsed in before['cues'].items():
            editor.select(cue)
            self.assertAlmostEqual(editor.elapsed, elapsed)
            self.assertFalse(editor.playing)
        for elapsed in (19., 2., 5.5, 0., 46., 5.5):
            editor.seek(elapsed)
            self.assertAlmostEqual(editor.elapsed, elapsed)
        editor.seek(-5.)
        self.assertEqual(editor.elapsed, 0.)
        editor.seek(1e6)
        self.assertEqual(editor.elapsed, before['cues']['end'])
        self.assertEqual(editor.document, before)
        self.assertFalse(editor.dirty)
        self.assertFalse(editor.undo())

    def test_invalid_timing_is_atomic_and_never_reorders_authored_cues(self):
        editor = self.editor
        before = editor.checkpoint()
        for cue, value in (('build_end', 7.), ('near_end', 11.), ('start', 1.),
                           ('end', float('nan')), ('far_end', float('inf'))):
            with self.assertRaises(ValueError):
                editor.set_time(cue, value)
            self.assertEqual(editor.document, before)
            self.assertFalse(editor.dirty)
        self.assertFalse(editor.undo())

    def test_drag_updates_commit_as_one_undo_and_new_edit_clears_redo(self):
        editor = self.editor
        editor.select('near_end')
        before = editor.checkpoint()
        for value in (14.1, 14.2, 14.8):
            editor.document['cues']['near_end'] = editor.clamp_time('near_end', value)
        self.assertTrue(editor.commit(before))
        after = editor.checkpoint()
        self.assertTrue(editor.undo())
        self.assertEqual(editor.document, before)
        self.assertFalse(editor.undo())
        self.assertTrue(editor.redo())
        self.assertEqual(editor.document, after)
        editor.undo()
        editor.set_time('near_end', 15.)
        self.assertFalse(editor.redo())

    def test_camera_and_bank_changes_are_independent_undo_transactions(self):
        editor = self.editor
        before = editor.checkpoint()
        editor.select('middle_start')
        frame = deepcopy(editor.document['cameras']['keys']['middle_start'])
        frame['eye'][0] += .75
        frame['fov'] = 68.
        editor.set_camera(frame)
        camera_changed = editor.checkpoint()
        editor.band = 'near'
        editor.set_bank('offset', 2.5, axis=0)
        self.assertEqual(editor.document['banks']['near']['offset'][0], 2.5)
        self.assertEqual(editor.document['banks']['far'], before['banks']['far'])
        self.assertTrue(editor.undo())
        self.assertEqual(editor.document, camera_changed)
        self.assertTrue(editor.undo())
        self.assertEqual(editor.document, before)
        self.assertTrue(editor.redo())
        self.assertTrue(editor.redo())

    def test_save_reload_is_atomic_and_undoable_without_touching_live_config(self):
        editor = self.editor
        editor.set_time('near_end', 15.)
        editor.save()
        saved = self.path.read_bytes()
        self.assertFalse(editor.dirty)
        self.assertNotIn(b'\r\n', saved)
        self.assertFalse(self.path.with_suffix('.json.tmp').exists())
        editor.set_time('near_end', 16.)
        edited = editor.checkpoint()
        editor.reload()
        self.assertEqual(editor.document, load_direction(self.path))
        self.assertFalse(editor.dirty)
        self.assertTrue(editor.undo())
        self.assertEqual(editor.document, edited)
        self.assertTrue(editor.dirty)
        self.assertTrue(editor.redo())
        self.assertFalse(editor.dirty)
        editor.document['cues']['end'] = float('nan')
        with self.assertRaises(ValueError):
            editor.save()
        self.assertEqual(self.path.read_bytes(), saved)

    def test_saved_timing_camera_and_bank_drive_fresh_runtime_objects(self):
        editor = self.editor
        editor.set_time('near_end', 16.)
        editor.band = 'near'
        editor.set_bank('offset', 2.5, axis=0)
        editor.set_bank('opacity', .65)
        editor.change(lambda: editor.document['cameras'].__setitem__('enabled', True))
        editor.select('middle_start')
        frame = deepcopy(editor.document['cameras']['keys']['middle_start'])
        frame['eye'][0] += 1.25
        editor.set_camera(frame)
        editor.save()
        profile = profile_from_document(load_direction(self.path))
        sequence = CanalSequence(profile)
        self.assertEqual(sequence.cue('near_end'), 16.)
        self.assertEqual(sequence.entry_duration, editor.document['cues']['blend_end'])
        self.assertEqual(sequence.duration, editor.document['cues']['end'])
        pose = sample_camera(profile, profile.cue('middle_start'))
        self.assertEqual(list(pose.eye), frame['eye'])
        self.assertEqual(list(pose.target), frame['target'])
        self.assertEqual(pose.fov, frame['fov'])
        defaults = profile_from_document(default_document())
        default_peak = {p.id: p for p in particles_at(defaults.cue('build_end'), 87., defaults)}
        edited_peak = {p.id: p for p in particles_at(profile.cue('build_end'), 87., profile)}
        bands = {p.id: p.band for p in particle_schedule(defaults)}
        self.assertEqual(default_peak.keys(), edited_peak.keys())
        for identity, before in default_peak.items():
            after = edited_peak[identity]
            if bands[identity] == 'near':
                self.assertAlmostEqual(after.center[0] - before.center[0], 2.5)
                self.assertEqual(after.center[1:], before.center[1:])
                self.assertAlmostEqual(after.alpha, before.alpha * .65)
            else:
                self.assertEqual(after, before)

    def test_arbitrary_runtime_seek_is_deterministic_and_silent(self):
        profile = profile_from_document(default_document())
        sequence = CanalSequence(profile)
        snapshots = {}
        for elapsed in (2., 5.5, 20., 1., 5.5, 20., 2.):
            sequence.seek(elapsed)
            signature = (sequence.elapsed, sequence.state, sequence.revealed,
                         sequence.world_blend, sequence.fog_clear, sequence.movement_locked,
                         particles_at(elapsed, 87., profile))
            if elapsed in snapshots:
                self.assertEqual(signature, snapshots[elapsed])
            snapshots[elapsed] = signature
            self.assertFalse(sequence.events, 'Scrubbing must not play encounter sounds')
        self.assertGreater(snapshots[5.5][3], 0.)
        self.assertLess(snapshots[5.5][3], 1.)

    def building_editor(self):
        return DirectionEditor(document=building_document(),path=self.path)

    def test_target_selection_does_not_edit_playhead_or_document(self):
        editor=self.building_editor();before=editor.checkpoint();editor.seek(12.25)
        for target in editor.targets:
            editor.select_target(target.id)
            self.assertEqual(editor.target.id,target.id)
            self.assertEqual(editor.elapsed,12.25)
        self.assertEqual(editor.document,before)
        self.assertFalse(editor.dirty);self.assertFalse(editor.undo())

    def test_group_edits_are_independent_and_survive_bank_comparison(self):
        editor=self.building_editor();before=editor.checkpoint();identity=editor.target_id
        editor.set_group('offset',3.25,0);editor.set_group('scale',1.2);editor.set_group('opacity',.65)
        edited=deepcopy(editor.group)
        for other,group in before['fog']['groups'].items():
            if other!=identity:self.assertEqual(editor.document['fog']['groups'][other],group)
        self.assertEqual(editor.document['banks'],before['banks'])
        editor.set_fog_mode('banks');self.assertEqual(editor.fog_mode,'banks')
        self.assertEqual(editor.document['fog']['groups'][identity],edited)
        editor.set_bank('opacity',.5)
        editor.set_fog_mode('buildings');self.assertEqual(editor.group,edited)
        self.assertEqual(editor.document['banks']['near']['opacity'],.5)

    def test_reveal_edits_validate_atomically_and_do_not_modify_global_cues(self):
        editor=self.building_editor();before=editor.checkpoint()
        for prop,value in (('reveal_start',-1.),('reveal_end',editor.duration+1.),
                           ('reveal_end',editor.group['reveal_start']),('scale',0.),
                           ('offset',float('nan'))):
            with self.assertRaises(ValueError):editor.set_group(prop,value,0 if prop=='offset' else None)
            self.assertEqual(editor.document,before)
        self.assertFalse(editor.undo())
        editor.set_group('reveal_start',editor.document['cues']['blend_end']+.125)
        editor.set_group('reveal_end',editor.duration-1.25)
        self.assertEqual(editor.document['cues'],before['cues'])
        self.assertTrue(editor.undo());self.assertTrue(editor.undo())
        self.assertEqual(editor.document,before)

    def test_global_retime_clamps_only_invalid_group_times_in_one_undo(self):
        editor=self.building_editor();before=editor.checkpoint()
        editor.set_time('blend_end',8.)
        for identity,group in editor.document['fog']['groups'].items():
            previous=before['fog']['groups'][identity]
            self.assertEqual(group['reveal_start'],max(8.,previous['reveal_start']))
            self.assertEqual(group['reveal_end'],max(group['reveal_start']+.1,previous['reveal_end']))
        self.assertEqual(len(editor.undo_stack),1)
        self.assertTrue(editor.undo());self.assertEqual(editor.document,before)
        editor.set_time('end',35.)
        self.assertTrue(all(6.<=g['reveal_start']<g['reveal_end']<=35. for g in editor.document['fog']['groups'].values()))
        self.assertTrue(editor.undo());self.assertEqual(editor.document,before)

    def test_reset_one_group_preserves_other_edits_and_authored_timing(self):
        editor=self.building_editor();editor.set_time('blend_end',7.)
        identity=editor.target_id;other=editor.targets[1].id
        editor.select_target(other);editor.set_group('opacity',.3)
        editor.select_target(identity);editor.set_group('offset',4.,2);editor.set_group('reveal_end',44.)
        before=editor.checkpoint();editor.reset_group()
        base=deepcopy(before);base.pop('fog')
        self.assertEqual(editor.group,building_document(base)['fog']['groups'][identity])
        self.assertEqual(editor.document['fog']['groups'][other],before['fog']['groups'][other])
        self.assertEqual(editor.document['cues'],before['cues'])
        self.assertTrue(editor.undo());self.assertEqual(editor.document,before)

    def test_saved_groups_are_loaded_by_fresh_game_profile(self):
        editor=self.building_editor();editor.select_target('house-110')
        editor.set_group('offset',1.75,1);editor.set_group('opacity',.4)
        editor.set_group('reveal_start',9.25);editor.set_group('reveal_end',19.75)
        editor.save();profile=profile_from_document(load_direction(self.path))
        self.assertEqual(profile.fog_mode,'buildings')
        group=profile.group('house-110')
        self.assertEqual(group.offset,(0.,1.75,0.));self.assertEqual(group.opacity,.4)
        self.assertEqual((group.reveal_start,group.reveal_end),(9.25,19.75))
        editor.set_group('scale',1.5);editor.reload()
        self.assertEqual(editor.profile,profile);self.assertFalse(editor.dirty)

    def test_semantic_ray_pick_uses_nearest_box_and_parallel_slab_rules(self):
        near=SimpleNamespace(id='near',center=(0.,0.,5.),half_extents=(1.,2.,1.))
        far=SimpleNamespace(id='far',center=(0.,0.,9.),half_extents=(2.,2.,1.))
        self.assertEqual(pick_target_bounds((0.,0.,0.),(0.,0.,1.),[far,near]),'near')
        self.assertEqual(pick_target_bounds((0.,0.,12.),(0.,0.,-1.),[near,far]),'far')
        self.assertIsNone(pick_target_bounds((3.,0.,0.),(0.,0.,1.),[near,far]))
        self.assertIsNone(pick_target_bounds((0.,0.,0.),(0.,0.,-1.),[near,far]))
        self.assertIsNone(pick_target_bounds((0.,0.,0.),(0.,0.,0.),[near]))
        with self.assertRaises(ValueError):pick_target_bounds((float('nan'),0.,0.),(0.,0.,1.),[near])

    def test_actual_widget_click_does_not_round_fractional_group_times(self):
        # Exercise the real input controller without creating a graphics/audio
        # device. Clicking a timeline handle must not be a hidden edit.
        from huxin_canals_editor import Editor, Input
        scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        editor=Editor(scene,path=self.path,document=building_document(),live_input=False,
                      selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(editor.close)
        editor.state.set_group('reveal_start',6.125)
        editor.state.set_group('reveal_end',20.375)
        before=editor.state.checkpoint();history=len(editor.state.undo_stack)
        with patch('huxin_canals_editor.pr.get_screen_width',return_value=1360),patch('huxin_canals_editor.pr.get_screen_height',return_value=900):
            for prop,rect in editor.reveal_handles():
                point=(rect[0]+rect[2]/2,rect[1]+rect[3]/2)
                editor.update(0.,Input(mouse=point,left_pressed=True,left_down=True))
                self.assertEqual(editor.drag['kind'],'reveal')
                self.assertEqual(editor.state.elapsed,before['fog']['groups'][editor.state.target_id][prop])
                editor.update(0.,Input(mouse=(point[0]+1.,point[1]),left_released=True))
                self.assertEqual(editor.state.elapsed,before['fog']['groups'][editor.state.target_id][prop])
                self.assertEqual(editor.state.document,before)
                self.assertEqual(len(editor.state.undo_stack),history)

    def test_controls_do_not_overlap_at_minimum_window_and_search_finds_all_groups(self):
        from huxin_canals_editor import Editor, Input
        scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        editor=Editor(scene,path=self.path,document=building_document(),live_input=False,
                      selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(editor.close)
        with patch('huxin_canals_editor.pr.get_screen_width',return_value=1360),patch('huxin_canals_editor.pr.get_screen_height',return_value=900):
            for mode in ('buildings','banks'):
                editor.action('mode:'+mode)
                buttons,fields=editor.controls()
                rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
                for i,(name,a) in enumerate(rects):
                    self.assertGreaterEqual(a[0],0.);self.assertGreaterEqual(a[1],0.)
                    self.assertLessEqual(a[0]+a[2],1360.);self.assertLessEqual(a[1]+a[3],900.)
                    for other,b in rects[i+1:]:
                        overlap=min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0])>0 and min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1])>0
                        self.assertFalse(overlap,(name,other))
            editor.action('mode:buildings');editor.action('search_targets')
            editor.update(0.,Input(chars='house-110'))
            matches=editor.filtered_targets();self.assertIn('house-110',[target.id for target in matches])
            self.assertTrue(all('house-110' in target.id for target in matches))
            self.assertIn('target:house-110',[name for name,_,_,_ in editor.controls()[0]])


if __name__ == '__main__':
    unittest.main()
