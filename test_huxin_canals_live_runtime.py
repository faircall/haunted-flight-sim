"""Regular-game direction reloads preserve the current encounter and input."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from g_huxin_canals_direction import (building_document,load_direction,save_direction,
                                    profile_from_document)
from g_huxin_canals_particles import building_frame_at
from huxin_canals_viewer import LiveDirectionReload,reset_player


class LiveDirectionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory(prefix='haunted-live-runtime-')
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'direction.json'
        self.document=building_document()
        save_direction(self.document,self.path)
        self.live=LiveDirectionReload(self.path)
        self.scene=SimpleNamespace(_codex_frame_paused=True)
        self.actor=reset_player(self.scene,puzzle=True,direction=profile_from_document(self.document))
        self.camera=self.scene.last_camera

    def accepted(self,document,at=0.):
        save_direction(document,self.path)
        self.assertFalse(self.live.poll(self.scene,at))
        return self.live.poll(self.scene,at+.25)

    def retimed(self,multiplier):
        document=deepcopy(self.document)
        for cue in document['cues']:document['cues'][cue]*=multiplier
        for group in document['fog']['groups'].values():
            group['reveal_start']*=multiplier;group['reveal_end']*=multiplier
        return document

    def test_paused_reload_changes_real_fog_without_resetting_actor_or_encounter(self):
        sequence=self.scene.sequence;sequence.seek(5.)
        sequence.locked_pose=(1.65,.325,1.65,.7)
        sequence.locked_camera=self.camera;sequence.locked_shot=5
        sequence._direction_camera_released=True
        sequence.events[:]=['existing'];sequence.swaps[:]=[('existing',.7)]
        sequence.world_time=13.;sequence.bells=1
        before=(self.actor.x,self.actor.height,self.actor.z,self.actor.yaw,self.actor.clip)
        inventory=sequence.inventory;events=sequence.events
        peak=building_frame_at(5.,87.,sequence.direction)
        document=deepcopy(self.document)
        document['fog']['groups']['house-110']['offset'][0]+=2.
        self.assertTrue(self.accepted(document))
        self.assertIs(self.scene.sequence,sequence)
        self.assertIs(self.actor.encounter,sequence)
        self.assertIs(sequence.inventory,inventory);self.assertIs(sequence.events,events)
        self.assertEqual(events,['existing']);self.assertEqual(sequence.swaps,[('existing',.7)])
        self.assertEqual((sequence.elapsed,sequence.world_time,sequence.bells),(5.,13.,1))
        self.assertIs(sequence.locked_camera,self.camera)
        self.assertIs(self.scene.last_camera,self.camera)
        self.assertEqual(sequence.locked_pose,(1.65,.325,1.65,.7))
        self.assertTrue(sequence._direction_camera_released)
        self.assertTrue(self.scene._codex_frame_paused)
        self.assertEqual(before,(self.actor.x,self.actor.height,self.actor.z,self.actor.yaw,self.actor.clip))
        current=building_frame_at(5.,87.,sequence.direction)
        owned=peak.group_ids=='house-110'
        self.assertTrue((current.centers[~owned]==peak.centers[~owned]).all())
        self.assertTrue((abs(current.centers[owned,0]-peak.centers[owned,0]-2.)<1e-12).all())
        self.assertEqual(self.live.status(.5),('Direction updated from saved file',False))
        self.assertIsNone(self.live.status(6.))

    def test_invalid_partial_file_keeps_last_good_until_a_complete_recovery(self):
        sequence=self.scene.sequence;old=sequence.direction
        self.path.write_text('{"cues":',encoding='utf-8')
        self.assertFalse(self.live.poll(self.scene,0.))
        self.assertFalse(self.live.poll(self.scene,.25))
        self.assertIs(sequence.direction,old)
        self.assertTrue(self.live.status(100.)[1])
        self.assertIn('invalid',self.live.status(100.)[0])
        document=deepcopy(self.document);document['fog']['groups']['house-110']['opacity']=.6
        self.assertTrue(self.accepted(document,1.))
        self.assertIsNone(self.live.watcher.error)
        self.assertEqual(sequence.direction.group('house-110').opacity,.6)

    def test_home_reads_fresh_save_and_acknowledges_it_without_a_reload_echo(self):
        document=deepcopy(self.document);document['fog']['groups']['house-110']['scale']=1.2
        save_direction(document,self.path)
        profile=self.live.load_for_reset()
        actor=reset_player(self.scene,puzzle=True,direction=profile)
        self.assertEqual(profile,profile_from_document(document))
        self.assertIs(actor.encounter,self.scene.sequence)
        self.assertFalse(self.live.poll(self.scene,0.))
        self.assertFalse(self.live.poll(self.scene,.25))
        self.assertIsNone(self.live.status(1.))

    def test_home_invalid_file_uses_last_good_and_keeps_error_visible(self):
        self.path.write_text('not json',encoding='utf-8')
        profile=self.live.load_for_reset()
        self.assertEqual(profile,profile_from_document(self.document))
        self.assertTrue(self.live.status(1.)[1])
        self.live.poll(self.scene,0.);self.live.poll(self.scene,.25)
        self.assertTrue(self.live.status(100.)[1])
        save_direction(self.document,self.path)
        self.live.poll(self.scene,.5)
        self.assertIsNone(self.live.status(100.))

    def test_f2_acknowledges_own_saved_profile_but_not_an_external_race(self):
        document=deepcopy(self.document);document['fog']['groups']['house-110']['scale']=1.1
        save_direction(document,self.path)
        self.scene.sequence.direction=profile_from_document(document)
        self.assertTrue(self.live.acknowledge_scene(self.scene))
        self.assertFalse(self.live.poll(self.scene,0.))
        external=deepcopy(document);external['fog']['groups']['house-110']['scale']=1.3
        save_direction(external,self.path)
        self.assertFalse(self.live.acknowledge_scene(self.scene))
        self.assertFalse(self.live.poll(self.scene,.25))
        self.assertTrue(self.live.poll(self.scene,.5))
        self.assertEqual(self.scene.sequence.direction,profile_from_document(external))

    def test_home_concurrent_external_save_is_not_swallowed(self):
        first=deepcopy(self.document);first['fog']['groups']['house-110']['scale']=1.1
        later=deepcopy(self.document);later['fog']['groups']['house-110']['scale']=1.4
        def read_then_external_save(path):
            save_direction(later,path)
            return first
        with patch('huxin_canals_viewer.load_direction',side_effect=read_then_external_save):
            selected=self.live.load_for_reset()
        reset_player(self.scene,puzzle=True,direction=selected)
        self.assertFalse(self.live.poll(self.scene,0.))
        self.assertTrue(self.live.poll(self.scene,.25))
        self.assertEqual(self.scene.sequence.direction,profile_from_document(later))

    def test_retiming_cannot_reverse_an_already_revealed_world(self):
        sequence=self.scene.sequence;sequence.seek(8.)
        inventory=deepcopy(sequence.inventory);sequence.events[:]=['keep']
        self.assertTrue(self.accepted(self.retimed(2.)))
        self.assertEqual(sequence.elapsed,8.)
        self.assertTrue(sequence.revealed)
        self.assertEqual(sequence.world_blend,1.)
        self.assertFalse(sequence.movement_locked)
        self.assertEqual(sequence.inventory,inventory);self.assertEqual(sequence.events,['keep'])
        sequence.tick(.05,self.actor)
        self.assertGreater(sequence.elapsed,8.)
        self.assertEqual(sequence.world_blend,1.)

    def test_shorter_timings_do_not_rewind_elapsed_or_replay_the_world_swap(self):
        sequence=self.scene.sequence;sequence.seek(3.)
        sequence.events[:]=['keep'];sequence.swaps[:]=[('keep',.5)]
        sequence.locked_camera=self.camera;sequence.locked_pose=(1.,.325,2.,.5)
        self.assertTrue(self.accepted(self.retimed(.4)))
        self.assertEqual(sequence.elapsed,3.)
        self.assertEqual(sequence.state,'canals');self.assertTrue(sequence.revealed)
        self.assertEqual(sequence.events,['keep']);self.assertEqual(sequence.swaps,[('keep',.5)])
        self.assertIs(sequence.locked_camera,self.camera)
        sequence.elapsed=30.
        sequence.tick(.05,self.actor)
        self.assertEqual(sequence.elapsed,30.)


if __name__=='__main__':unittest.main()
