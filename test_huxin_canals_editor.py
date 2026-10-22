"""Authoring transactions and saved directions consumed by actual gameplay."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from g_huxin_canals_direction import (default_document, load_direction,
                                     profile_from_document, sample_camera)
from g_huxin_canals_editor import DirectionEditor
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


if __name__ == '__main__':
    unittest.main()
