"""Real temporary files, transport preservation and safe concurrent edits."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import default_document, load_direction, save_direction, profile_from_document
from g_huxin_canals_editor import DirectionEditor
from g_huxin_canals_live import (DirectionWatcher, DirectionConflictError,
    apply_live_direction, merge_directions, save_direction_checked)
from g_huxin_canals_sequence import CanalSequence


class LiveFileFixture(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='canals-live-')
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'direction.json'
        self.base=default_document()
        save_direction(self.base,self.path)

    def remote(self,value=2.,axis=0):
        doc=deepcopy(self.base);doc['banks']['near']['offset'][axis]=value
        save_direction(doc,self.path)
        return load_direction(self.path)


class DirectionWatcherTests(LiveFileFixture):
    def test_atomic_replacement_settles_once_and_retains_validated_document(self):
        watcher=DirectionWatcher(self.path,self.base)
        remote=self.remote()
        self.assertIsNone(watcher.poll(0.));self.assertIsNone(watcher.poll(.1))
        self.assertEqual(watcher.poll(.3),remote)
        self.assertEqual(watcher.document,remote)
        self.assertIsNone(watcher.poll(.6));self.assertIsNone(watcher.error)

    def test_content_changes_are_detected_with_identical_file_metadata(self):
        watcher=DirectionWatcher(self.path,self.base)
        original=self.path.stat()
        data=self.path.read_bytes().replace(b'"scale": 1.0',b'"scale": 2.0',1)
        self.path.write_bytes(data);os.utime(self.path,ns=(original.st_atime_ns,original.st_mtime_ns))
        self.assertEqual(self.path.stat().st_size,original.st_size)
        self.assertEqual(self.path.stat().st_mtime_ns,original.st_mtime_ns)
        self.assertIsNone(watcher.poll(0.))
        self.assertEqual(watcher.poll(.3)['banks']['near']['scale'],2.)

    def test_rapid_updates_deliver_only_the_latest_stable_snapshot(self):
        watcher=DirectionWatcher(self.path,self.base)
        self.remote(2.);self.assertIsNone(watcher.poll(0.))
        latest=self.remote(3.);self.assertIsNone(watcher.poll(.3))
        self.assertEqual(watcher.poll(.6),latest)
        self.assertIsNone(watcher.poll(.9))

    def test_partial_invalid_and_missing_files_keep_last_good_and_recover(self):
        watcher=DirectionWatcher(self.path,self.base)
        self.path.write_text('{"version":',encoding='utf8')
        watcher.poll(0.);self.assertIsNone(watcher.poll(.3));self.assertTrue(watcher.error)
        self.assertEqual(watcher.document,self.base)
        self.path.unlink();self.assertIsNone(watcher.poll(.6));self.assertTrue(watcher.error)
        latest=self.remote(4.);self.assertIsNone(watcher.poll(.9))
        self.assertEqual(watcher.poll(1.2),latest);self.assertIsNone(watcher.error)

    def test_own_acknowledgement_does_not_swallow_a_concurrent_file_change(self):
        watcher=DirectionWatcher(self.path,self.base)
        latest=self.remote(3.)
        self.assertFalse(watcher.acknowledge(self.base))
        self.assertIsNone(watcher.poll(0.));self.assertEqual(watcher.poll(.3),latest)
        self.assertTrue(watcher.acknowledge(latest));self.assertIsNone(watcher.poll(.6))

    def test_format_only_change_and_exact_recovery_do_not_emit_false_edits(self):
        watcher=DirectionWatcher(self.path,self.base)
        original=self.path.read_bytes()
        self.path.write_text(json.dumps(self.base),encoding='utf8')
        watcher.poll(0.);self.assertIsNone(watcher.poll(.3))
        accepted=self.path.read_bytes()
        self.path.write_text('invalid',encoding='utf8')
        watcher.poll(.6);watcher.poll(.9);self.assertTrue(watcher.error)
        self.path.write_bytes(accepted);self.assertIsNone(watcher.poll(1.2));self.assertIsNone(watcher.error)
        self.path.write_bytes(original)
        watcher.poll(1.5);self.assertIsNone(watcher.poll(1.8))

    def test_checked_save_rejects_concurrent_bytes_and_cleans_temporary_file(self):
        expected=self.path.read_bytes();latest=self.remote(4.)
        with self.assertRaises(DirectionConflictError):save_direction_checked(self.base,self.path,expected)
        self.assertEqual(load_direction(self.path),latest)
        self.assertFalse(list(self.path.parent.glob('*.tmp')))


class LiveEditorTests(LiveFileFixture):
    def setUp(self):
        super().setUp();self.editor=DirectionEditor(path=self.path)

    def deliver(self,now=0.,busy=False):
        self.editor.poll_external(now,busy=busy)
        return self.editor.poll_external(now+.3,busy=busy)

    def test_clean_auto_apply_is_undoable_and_preserves_transport_and_selection(self):
        editor=self.editor;editor.select('middle_start');editor.elapsed=13.75
        editor.band='far';editor.select_target('house-133');editor.playing=True;editor.loop=True
        latest=self.remote(2.);self.assertTrue(self.deliver())
        self.assertEqual(editor.document,latest);self.assertEqual(editor.saved,latest)
        self.assertFalse(editor.dirty);self.assertEqual(editor.elapsed,13.75)
        self.assertTrue(editor.playing);self.assertTrue(editor.loop)
        self.assertEqual((editor.selected,editor.band,editor.target_id),('middle_start','far','house-133'))
        self.assertTrue(editor.undo());self.assertEqual(editor.document,self.base);self.assertTrue(editor.dirty)

    def test_busy_gesture_defers_application_but_keeps_latest_remote(self):
        self.remote(2.);self.deliver(busy=True)
        self.assertEqual(self.editor.document,self.base);self.assertTrue(self.editor.external_pending)
        latest=self.remote(3.);self.deliver(.6,busy=True)
        self.editor.poll_external(1.2,busy=False)
        self.assertEqual(self.editor.document,latest);self.assertFalse(self.editor.external_pending)

    def test_disjoint_xyz_and_camera_edits_merge_without_losing_local_work(self):
        editor=self.editor;editor.set_bank('offset',1.,0)
        latest=self.remote(2.,1);self.deliver()
        self.assertEqual(editor.document['banks']['near']['offset'],[1.,2.,0.])
        self.assertEqual(editor.saved,latest);self.assertTrue(editor.dirty)
        editor.save();self.assertEqual(load_direction(self.path),editor.document)
        self.assertFalse(editor.dirty);self.assertIsNone(editor.poll_external(.6))

    def test_conflict_holds_latest_remote_and_use_file_is_undoable(self):
        editor=self.editor;editor.set_bank('offset',1.,0);local=editor.checkpoint()
        self.remote(2.);self.deliver()
        self.assertEqual(editor.document,local);self.assertTrue(editor.external_pending)
        self.assertIn('banks.near.offset.0',editor.external_conflicts)
        latest=self.remote(3.)
        editor.resolve_external('file')
        self.assertEqual(editor.document,latest);self.assertFalse(editor.external_pending)
        self.assertTrue(editor.undo());self.assertEqual(editor.document,local)

    def test_save_checks_unpolled_remote_conflicts_and_keep_mine_is_explicit(self):
        editor=self.editor;editor.set_bank('offset',1.,0);latest=self.remote(3.)
        with self.assertRaises(DirectionConflictError):editor.save()
        self.assertEqual(load_direction(self.path),latest)
        editor.resolve_external('mine')
        self.assertEqual(load_direction(self.path),editor.document)
        self.assertEqual(editor.document['banks']['near']['offset'][0],1.)
        self.assertFalse(editor.external_pending);self.assertFalse(editor.dirty)

    def test_save_merges_unpolled_disjoint_edits_before_atomic_replacement(self):
        editor=self.editor;editor.set_bank('offset',1.,0);self.remote(3.,2)
        editor.save()
        self.assertEqual(load_direction(self.path)['banks']['near']['offset'],[1.,0.,3.])
        self.assertFalse(editor.dirty)

    def test_invalid_combined_timing_stays_pending_even_without_same_leaf_conflict(self):
        editor=self.editor;editor.set_time('build_end',5.8);local=editor.checkpoint()
        remote=deepcopy(self.base);remote['cues']['blend_end']=5.5;save_direction(remote,self.path)
        self.deliver()
        self.assertEqual(editor.document,local);self.assertTrue(editor.external_pending)
        self.assertTrue(editor.external_conflicts[0].startswith('Combined edits are invalid'))

    def test_invalid_file_blocks_save_and_exact_recovery_clears_visible_error(self):
        editor=self.editor;original=self.path.read_bytes()
        self.path.write_text('{bad',encoding='utf8');self.deliver()
        self.assertTrue(editor.watcher.error);self.assertTrue(editor.external_pending)
        with self.assertRaises(DirectionConflictError):editor.save()
        self.assertEqual(self.path.read_text(encoding='utf8'),'{bad')
        self.path.write_bytes(original)
        status=editor.poll_external(.6)
        self.assertIn('valid again',status)
        self.assertFalse(editor.external_pending);self.assertIsNone(editor.watcher.error)
        self.assertEqual(editor.document,self.base)

    def test_missing_existing_file_blocks_save_but_first_unsaved_document_can_save(self):
        self.path.unlink()
        with self.assertRaises(DirectionConflictError):self.editor.save()
        self.editor.resolve_external('mine');self.assertTrue(self.path.exists())
        newpath=self.path.parent/'new.json'
        editor=DirectionEditor(document=self.base,path=newpath);editor.save()
        self.assertEqual(load_direction(newpath),self.base)

    def test_new_remote_conflict_replaces_old_pending_snapshot(self):
        editor=self.editor;editor.set_bank('offset',1.,0)
        self.remote(2.);self.deliver()
        latest=self.remote(4.);self.deliver(.6)
        self.assertEqual(editor._pending_external,latest)
        self.assertEqual(editor.document['banks']['near']['offset'][0],1.)


class RuntimeLiveDirectionTests(unittest.TestCase):
    def profile(self,**cues):
        document=default_document();document['cues'].update(cues)
        return profile_from_document(document)

    def test_active_runtime_keeps_objects_events_clock_and_camera_locks(self):
        sequence=CanalSequence();sequence.seek(9.)
        sequence.events.append('existing');sequence.swaps.append(('existing',.7));sequence.bells=4
        sequence.world_time=17.;sequence.next_creak=23.;sequence._direction_camera_released=True
        sequence.locked_camera=object();sequence.locked_pose=(1.,.325,2.,.4);sequence.locked_shot=5
        objects={key:getattr(sequence,key) for key in ('inventory','events','swaps','locked_camera','locked_pose')}
        profile=self.profile(blend_end=11.)
        self.assertTrue(apply_live_direction(sequence,profile))
        self.assertEqual(sequence.elapsed,9.);self.assertEqual(sequence.state,'canals')
        self.assertTrue(sequence.revealed);self.assertEqual(sequence.world_blend,1.)
        self.assertEqual((sequence.world_time,sequence.next_creak,sequence.bells),(17.,23.,4))
        self.assertTrue(sequence._direction_camera_released)
        for key,value in objects.items():self.assertIs(getattr(sequence,key),value)
        self.assertEqual(sequence.events,['existing']);self.assertFalse(apply_live_direction(sequence,profile))

    def test_entering_update_can_commit_without_replaying_events(self):
        sequence=CanalSequence();sequence.seek(5.8);sequence.events.append('existing')
        self.assertTrue(sequence.movement_locked)
        apply_live_direction(sequence,self.profile(blend_end=5.5))
        self.assertEqual(sequence.elapsed,5.8);self.assertFalse(sequence.movement_locked)
        self.assertTrue(sequence.revealed);self.assertEqual(sequence.events,['existing'])
        self.assertEqual(sequence.swaps,[])

    def test_ordinary_stays_ordinary_and_shorter_end_never_rewinds_committed_clock(self):
        sequence=CanalSequence();inventory=deepcopy(sequence.inventory)
        apply_live_direction(sequence,self.profile(near_end=15.))
        self.assertEqual(sequence.state,'ordinary');self.assertFalse(sequence.disc_placed)
        self.assertEqual(sequence.inventory,inventory);self.assertEqual(sequence.elapsed,0.)
        sequence.seek(44.)
        apply_live_direction(sequence,self.profile(end=35.))
        sequence.tick(.1,SimpleNamespace(x=1.65,z=1.65))
        self.assertEqual(sequence.elapsed,44.);self.assertEqual(sequence.world_blend,1.)
        sequence.seek(2.);self.assertEqual(sequence.world_blend,0.)


if __name__=='__main__':unittest.main()
