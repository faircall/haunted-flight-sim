"""Geometry handoff waits for authored surface growth, including live edits."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from g_huxin_canals_direction import default_document, profile_from_document
from g_huxin_canals_sequence import CanalSequence
from g_huxin_canals_editor import DirectionEditor
from g_huxin_canals_live import apply_live_direction
from g_huxin_canals_surface_settings import default_surface_document, surface_blend_window


def profile(build=8.,enabled=True,amount=1.,span=1.):
    document=default_document();document['cues']['blend_end']=document['cues']['build_end']+span
    document['surface_fog']=default_surface_document(document['cues'])
    document['surface_fog'].update(enabled=enabled,amount=amount,build_end=build,
        reveal_start=max(8.,build+span),reveal_end=max(32.,build+span+.1))
    return profile_from_document(document)


class SurfaceTimingTests(unittest.TestCase):
    def test_disabled_absent_and_zero_amount_keep_exact_old_handoff(self):
        for direction in (profile_from_document(default_document()),profile(enabled=False),profile(amount=0.)):
            self.assertEqual(surface_blend_window(direction),(5.,6.))
            sequence=CanalSequence(direction);sequence.seek(5.5)
            self.assertEqual(sequence.world_blend,.5);self.assertEqual(sequence.entry_duration,6.)

    def test_extended_growth_delays_blend_and_control_release(self):
        direction=profile();self.assertEqual(surface_blend_window(direction),(8.,9.))
        sequence=CanalSequence(direction)
        for time,blend,locked in ((5.5,0.,True),(8.,0.,True),(8.5,.5,True),(9.,1.,False)):
            sequence.seek(time)
            self.assertEqual(sequence.world_blend,blend)
            self.assertEqual(sequence.movement_locked,locked)
            self.assertEqual(sequence.revealed,not locked)
        self.assertEqual(sequence.world_time,0.)

    def test_preserves_authored_blend_span(self):
        direction=profile(build=8.,span=2.)
        self.assertEqual(surface_blend_window(direction),(8.,10.))
        sequence=CanalSequence(direction);sequence.seek(9.)
        self.assertEqual(sequence.world_blend,.5)

    def test_ticks_commit_once_at_effective_end_at_sixty_fps(self):
        sequence=CanalSequence(profile());sequence.seek(0.)
        actor=SimpleNamespace(x=1.65,z=1.65)
        for _ in range(539):sequence.tick(1./60,actor)
        self.assertFalse(sequence.revealed);self.assertEqual(sequence.swaps,[])
        sequence.tick(1./60,actor)
        self.assertEqual(sequence.elapsed,9.);self.assertTrue(sequence.revealed)
        self.assertEqual(len(sequence.swaps),1)
        sequence.tick(1./60,actor);self.assertEqual(len(sequence.swaps),1)

    def test_live_edit_waits_for_new_effective_end_without_resetting_state(self):
        sequence=CanalSequence();sequence.seek(5.5);sequence.events[:]=['keep']
        inventory=sequence.inventory;camera=object();sequence.locked_camera=camera
        apply_live_direction(sequence,profile())
        self.assertFalse(sequence.revealed);self.assertEqual(sequence.world_blend,0.)
        self.assertIs(sequence.inventory,inventory);self.assertIs(sequence.locked_camera,camera)
        self.assertEqual(sequence.events,['keep']);self.assertEqual(sequence.elapsed,5.5)
        sequence.elapsed=8.5
        apply_live_direction(sequence,profile(build=9.))
        self.assertEqual(sequence.state,'entering');self.assertFalse(sequence.revealed)

    def test_live_shortening_commits_only_after_effective_end_and_never_reverses(self):
        sequence=CanalSequence(profile(build=10.));sequence.seek(9.5)
        apply_live_direction(sequence,profile(build=8.))
        self.assertTrue(sequence.revealed);self.assertEqual(sequence.world_blend,1.)
        apply_live_direction(sequence,profile(build=12.))
        self.assertTrue(sequence.revealed);self.assertFalse(sequence.movement_locked)
        self.assertEqual(sequence.world_blend,1.)

    def test_build_field_extends_dependent_clear_and_undo_restores_it(self):
        document=default_document();document['surface_fog']=default_surface_document(document['cues'])
        document['surface_fog']['enabled']=True
        model=DirectionEditor(document,Path(tempfile.gettempdir())/'unused-surface-timing.json')
        before=deepcopy(model.document)
        model.set_surface('build_end',8.)
        self.assertEqual(model.surface_settings['build_end'],8.)
        self.assertEqual(model.surface_settings['reveal_start'],9.)
        self.assertEqual(surface_blend_window(model.profile),(8.,9.))
        self.assertEqual(len(model.undo_stack),1)
        model.undo();self.assertEqual(model.document,before)
        with self.assertRaises(ValueError):model.set_surface('build_end',45.)
        self.assertEqual(model.document,before)


if __name__=='__main__':unittest.main()
