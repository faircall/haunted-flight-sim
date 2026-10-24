"""Spatial fog envelopes, backward-compatible direction data and authoring."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import math
import tempfile
import unittest

from g_huxin_canals_direction import (DirectionError, default_document,
    validate_document, profile_from_document, document_from_profile)
from g_huxin_canals_editor import DirectionEditor
from g_huxin_canals_live import merge_directions
from g_huxin_canals_volumes import (MAX_VOLUMES, DEFAULT_VOLUME_SETTINGS,
    default_region_document, default_volume_document, demo_volume_document,
    settings_from_document, volume_frame_at, ray_interval, envelope_density)


def authored():
    document=default_document()
    document['volumes']=demo_volume_document(document['cues'])
    return document


class VolumeSchemaTests(unittest.TestCase):
    def test_absent_extension_has_exact_legacy_round_trip_and_no_volume_frames(self):
        document=default_document()
        profile=profile_from_document(document)
        self.assertEqual(profile.volumes,DEFAULT_VOLUME_SETTINGS)
        self.assertFalse(profile.volume_authored)
        self.assertEqual(document_from_profile(profile),document)
        self.assertEqual(volume_frame_at(5.,100.,profile.volumes),())

    def test_explicit_disabled_settings_round_trip_and_frozen_snapshot(self):
        document=default_document();document['volumes']=default_volume_document()
        profile=profile_from_document(document)
        self.assertTrue(profile.volume_authored)
        self.assertEqual(document_from_profile(profile),document)
        with self.assertRaises(FrozenInstanceError):profile.volumes.mix=.3
        self.assertIsInstance(hash(profile),int)

    def test_demo_round_trip_preserves_ids_and_fills_local_spaces_not_pavilion(self):
        document=authored();profile=profile_from_document(document)
        self.assertEqual(document_from_profile(profile),document)
        self.assertEqual(len(profile.volumes.regions),14)
        self.assertTrue(any(r.hollow>0. for r in profile.volumes.regions))
        self.assertTrue(any(r.shape=='ellipsoid' for r in profile.volumes.regions))
        for point in ((0.,1.,0.),(0.,2.,2.)):
            self.assertEqual(sum(envelope_density(point,r) for r in profile.volumes.regions),0.)
        document['volumes']['regions']['volume-house-410']['center'][0]+=10.
        self.assertNotEqual(profile.volumes.region('volume-house-410').center[0],
                            document['volumes']['regions']['volume-house-410']['center'][0])

    def test_validation_reports_invalid_spatial_and_temporal_values(self):
        changes=(('half_extents',[2.,0.,2.]),('center',[0.,math.inf,0.]),
            ('density',True),('edge',0.),('noise_size',0.),('hollow',1.),
            ('shape','sphere'),('fade_in_end',0.),('reveal_start',2.),
            ('reveal_end',6.),('wind',[1.,2.]),('enabled',1))
        for key,value in changes:
            with self.subTest(key=key):
                document=authored();document['volumes']['regions']['volume-house-410'][key]=value
                with self.assertRaisesRegex(DirectionError,'volumes.regions.volume-house-410'):
                    validate_document(document)
        document=authored();document['volumes']['quality']='ultra'
        with self.assertRaisesRegex(DirectionError,'volumes.quality'):validate_document(document)

    def test_stable_ids_and_region_limit_are_validated(self):
        document=authored();value=next(iter(document['volumes']['regions'].values()))
        document['volumes']['regions']={'Not a stable ID':value}
        with self.assertRaisesRegex(DirectionError,'IDs must'):validate_document(document)
        document['volumes']['regions']={f'volume-{i}':deepcopy(value) for i in range(MAX_VOLUMES+1)}
        with self.assertRaisesRegex(DirectionError,'at most 24'):validate_document(document)

    def test_new_region_properties_merge_without_overwriting_other_live_edits(self):
        base=authored();local=deepcopy(base);remote=deepcopy(base)
        local['volumes']['regions']['volume-house-410']['center'][0]+=1.
        remote['volumes']['regions']['volume-house-423']['density']=.6
        merged,conflicts=merge_directions(base,local,remote)
        self.assertFalse(conflicts)
        self.assertEqual(merged['volumes']['regions']['volume-house-410']['center'],
                         local['volumes']['regions']['volume-house-410']['center'])
        self.assertEqual(merged['volumes']['regions']['volume-house-423']['density'],.6)
        remote['volumes']['regions']['volume-house-410']['center'][0]-=2.
        _,conflicts=merge_directions(base,local,remote)
        self.assertTrue(any('volume-house-410.center' in path for path in conflicts))


class VolumeSpatialTests(unittest.TestCase):
    def setUp(self):
        section=default_volume_document();section['enabled']=True
        value=default_region_document()
        value.update(center=[0.,0.,0.],half_extents=[1.,2.,4.],fade_in_end=5.,
                     reveal_start=6.,reveal_end=18.,retreat=[4.,0.,3.])
        section['regions']['test']=value
        self.settings=settings_from_document(section)
        self.region=self.settings.regions[0]

    def test_rays_intersect_oriented_boxes_ellipsoids_and_inside_camera(self):
        self.assertEqual(ray_interval((-10.,0.,0.),(1.,0.,0.),self.region),(9.,11.))
        rotated=replace(self.region,yaw=90.)
        a,b=ray_interval((-10.,0.,0.),(1.,0.,0.),rotated)
        self.assertAlmostEqual(a,6.);self.assertAlmostEqual(b,14.)
        # Positive yaw in the gizmo maps local +X toward world +Z. Its ray
        # must be transformed back with the inverse rotation, not doubled.
        c=math.sqrt(.5)
        a,b=ray_interval((-10.*c,0.,-10.*c),(c,0.,c),replace(self.region,yaw=45.))
        self.assertAlmostEqual(a,9.);self.assertAlmostEqual(b,11.)
        self.assertEqual(ray_interval((0.,0.,0.),(1.,0.,0.),self.region),(0.,1.))
        self.assertIsNone(ray_interval((-10.,3.,0.),(1.,0.,0.),self.region))
        self.assertIsNone(ray_interval((0.,0.,0.),(0.,0.,0.),self.region))
        sphere=replace(self.region,shape='ellipsoid',half_extents=(2.,2.,2.))
        self.assertEqual(ray_interval((-5.,0.,0.),(1.,0.,0.),sphere),(3.,7.))
        self.assertIsNone(ray_interval((-5.,3.,0.),(1.,0.,0.),sphere))

    def test_hollow_region_leaves_interior_clear_and_feathers_outer_boundary(self):
        region=replace(self.region,half_extents=(4.,4.,4.),hollow=.5,edge=.3)
        self.assertEqual(envelope_density((0.,0.,0.),region),0.)
        self.assertEqual(envelope_density((4.,0.,0.),region),0.)
        self.assertEqual(envelope_density((5.,0.,0.),region),0.)
        self.assertGreater(envelope_density((3.,0.,0.),region),.05)
        self.assertGreater(envelope_density((3.,0.,0.),region),envelope_density((3.9,0.,0.),region))

    def test_arrival_is_gradual_and_continuous_through_five_seconds(self):
        self.assertEqual(volume_frame_at(0.,5.,self.settings),())
        one=volume_frame_at(1.,5.,self.settings)[0]
        three=volume_frame_at(3.,5.,self.settings)[0]
        peak=volume_frame_at(5.,5.,self.settings)[0]
        self.assertLess(one.density,peak.density*.1)
        self.assertLess(one.density,three.density)
        self.assertAlmostEqual(peak.density,self.region.density)
        self.assertAlmostEqual(volume_frame_at(4.999,5.,self.settings)[0].density,peak.density,places=8)
        self.assertEqual(volume_frame_at(5.001,5.,self.settings)[0].density,peak.density)

    def test_retreat_precedes_fading_and_ends_without_live_particles(self):
        start=volume_frame_at(6.,5.,self.settings)[0]
        moving=volume_frame_at(8.,5.,self.settings)[0]
        fading=volume_frame_at(12.,5.,self.settings)[0]
        self.assertNotEqual(start.center,moving.center)
        self.assertEqual(start.density,moving.density)
        self.assertLess(fading.density,start.density)
        self.assertGreater(fading.center[1],0.)
        self.assertEqual(volume_frame_at(18.,5.,self.settings),())

    def test_sampling_is_history_free_and_density_mix_has_physical_meaning(self):
        first=volume_frame_at(12.,34.,self.settings)
        volume_frame_at(2.,1.,self.settings)
        self.assertEqual(first,volume_frame_at(12.,34.,self.settings))
        self.assertEqual(first,volume_frame_at(12.,99.,self.settings))
        stronger=volume_frame_at(12.,34.,replace(self.settings,mix=1.5))
        self.assertAlmostEqual(stronger[0].density,first[0].density*1.5)
        self.assertEqual(volume_frame_at(5.,2.,replace(self.settings,enabled=False)),())
        self.assertEqual(volume_frame_at(5.,2.,replace(self.settings,mix=0.)),())
        with self.assertRaises(ValueError):volume_frame_at(math.nan,0.,self.settings)


class VolumeEditorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='canals-volumes-')
        self.addCleanup(temporary.cleanup)
        self.editor=DirectionEditor(default_document(),Path(temporary.name)/'direction.json')

    def test_add_duplicate_remove_undo_redo_preserves_region_and_selection(self):
        editor=self.editor
        self.assertIsNone(editor.volume)
        first=editor.add_volume(target_id='house-410')
        self.assertEqual(editor.volume_id,first)
        self.assertGreater(editor.volume['hollow'],0.)
        duplicate=editor.duplicate_volume()
        self.assertNotEqual(first,duplicate)
        editor.remove_volume()
        self.assertEqual(editor.volume_id,first)
        editor.undo();self.assertEqual(editor.volume_id,duplicate)
        editor.undo();self.assertEqual(editor.volume_id,first)
        editor.undo();self.assertIsNone(editor.volume_id)
        self.assertNotIn('volumes',editor.document)
        editor.redo();self.assertEqual(editor.volume_id,first)
        editor.redo();self.assertEqual(editor.volume_id,duplicate)

    def test_invalid_edit_rolls_back_and_cue_edits_fit_region_windows(self):
        editor=self.editor;editor.set_volume_demo()
        before=editor.checkpoint()
        with self.assertRaises(DirectionError):editor.set_volume('half_extents',0.,axis=1)
        self.assertEqual(editor.document,before)
        editor.set_time('end',33.)
        self.assertLessEqual(max(r['reveal_end'] for r in editor.volume_regions.values()),33.)
        editor.undo();self.assertEqual(editor.document,before)
        editor.set_time('blend_end',11.)
        self.assertGreaterEqual(min(r['reveal_start'] for r in editor.volume_regions.values()),11.)

    def test_external_region_deletion_repairs_selection_and_is_undoable(self):
        editor=self.editor;editor.set_volume_demo()
        chosen=editor.volume_id
        remote=deepcopy(editor.document);remote['volumes']['regions'].pop(chosen)
        editor._apply_external(remote,remote)
        self.assertNotEqual(editor.volume_id,chosen)
        self.assertIsNotNone(editor.volume)
        editor.undo();self.assertEqual(editor.volume_id,chosen)

    def test_volume_settings_and_region_edits_save_reload(self):
        editor=self.editor;identity=editor.add_volume(shape='ellipsoid')
        editor.set_volume_setting('enabled',True)
        editor.set_volume_setting('particle_mix',.35)
        editor.set_volume('center',18.,axis=2)
        editor.save()
        other=DirectionEditor(path=editor.path)
        self.assertEqual(other.volume_id,identity)
        self.assertEqual(other.volume['center'][2],18.)
        self.assertTrue(other.profile.volumes.enabled)
        self.assertEqual(other.profile.volumes.particle_mix,.35)
        self.assertFalse(other.dirty)


if __name__=='__main__':unittest.main()
