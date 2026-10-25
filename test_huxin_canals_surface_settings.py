"""Compatibility, validation and authoring transactions for surface fog."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from g_huxin_canals_direction import (building_document, default_document,
    profile_from_document, document_from_profile, validate_document, save_direction)
from g_huxin_canals_editor import DirectionEditor
from g_huxin_canals_surface_settings import (DEFAULT_SURFACE_SETTINGS,
    SURFACE_OPTIONAL_FIELDS, default_surface_document, surface_settings_from_document, document_from_surface_settings,
    surface_blend_window)


class SurfaceSettingsTests(unittest.TestCase):
    def document(self):
        document=building_document()
        document['surface_fog']=default_surface_document(document['cues'])
        return document

    def test_old_documents_roundtrip_without_adding_surface_section(self):
        for document in (default_document(),building_document()):
            profile=profile_from_document(document)
            self.assertFalse(profile.surface_fog.enabled)
            self.assertEqual(profile.surface_fog,DEFAULT_SURFACE_SETTINGS)
            self.assertEqual(document_from_profile(profile),document)
        explicit=self.document()
        self.assertEqual(document_from_profile(profile_from_document(explicit)),explicit)

    def test_immutable_snapshot_and_lossless_json_roundtrip(self):
        document=self.document();document['surface_fog']['enabled']=True
        profile=profile_from_document(document)
        document['surface_fog']['wind'][0]=19.
        self.assertEqual(profile.surface_fog.wind[0],.26)
        self.assertIsInstance(hash(profile),int)
        self.assertEqual(surface_settings_from_document(document_from_surface_settings(profile.surface_fog)),profile.surface_fog)

    def test_rejects_invalid_controls_and_unknown_fields(self):
        changes=(('enabled',1),('density',0.),('thickness',12.1),('edge',1.),
                 ('noise_size',.1),('pattern_amount',1.1),('wind',[0,float('nan'),0]),
                 ('wind',[0,0]),('amount',True),('surprise',1),('use_building_timing','yes'))
        for key,value in changes:
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)

    def test_windows_protect_blend_and_have_positive_duration(self):
        for key,value in (('build_start',5.),('build_end',9.),('reveal_start',4.),('reveal_end',8.)):
            with self.subTest(key=key):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)
        document=self.document()
        document['cues']={name:i*.1 for i,name in enumerate(document['cues'])}
        # Group windows are absent in this compact schema test.
        document.pop('fog');document['surface_fog']=default_surface_document(document['cues'])
        validate_document(document)

    def test_global_retime_clamps_surface_and_undo_restores_both(self):
        model=DirectionEditor(self.document(),Path(tempfile.gettempdir())/'unused-surface-direction.json')
        original=deepcopy(model.document)
        model.set_time('blend_end',9.)
        self.assertEqual(model.surface_settings['reveal_start'],9.)
        self.assertTrue(model.surface_settings['use_building_timing'])
        model.undo();self.assertEqual(model.document,original)

    def test_live_surface_edits_merge_or_report_same_field_conflict(self):
        with tempfile.TemporaryDirectory(prefix='haunted-surface-live-') as directory:
            path=Path(directory)/'direction.json';document=self.document();save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('density',3.)
            remote=deepcopy(document);remote['surface_fog']['thickness']=5.
            save_direction(remote,path);model.poll_external(0.);model.poll_external(.3)
            self.assertEqual(model.surface_settings['density'],3.)
            self.assertEqual(model.surface_settings['thickness'],5.)
            self.assertFalse(model.external_pending)
            remote['surface_fog']['density']=4.;save_direction(remote,path)
            model.poll_external(1.);model.poll_external(1.3)
            self.assertTrue(model.external_pending)
            self.assertEqual(model.surface_settings['density'],3.)

    def test_evolution_fields_are_optional_and_old_saved_bytes_are_preserved(self):
        document=self.document()
        self.assertFalse(set(SURFACE_OPTIONAL_FIELDS)&document['surface_fog'].keys())
        profile=profile_from_document(document)
        self.assertEqual(profile.surface_fog.evolution,'erode')
        self.assertEqual(profile.surface_fog.initial_scale,.4)
        self.assertEqual(profile.surface_fog.settle_fraction,.65)
        self.assertEqual(profile.surface_fog.base_y,0.)
        with tempfile.TemporaryDirectory(prefix='haunted-surface-compat-') as directory:
            path=Path(directory)/'direction.json';save_direction(document,path);before=path.read_bytes()
            save_direction(document_from_profile(profile),path)
            self.assertEqual(path.read_bytes(),before)

    def test_explicit_optional_defaults_and_changed_runtime_values_roundtrip(self):
        document=self.document()
        document['surface_fog'].update(evolution='erode',initial_scale=.4,settle_fraction=.65,base_y=0.)
        profile=profile_from_document(document)
        self.assertEqual(document_from_profile(profile),document)
        old=profile_from_document(self.document())
        changed=replace(old,surface_fog=replace(old.surface_fog,evolution='rise_resolve',initial_scale=.55))
        new=document_from_profile(changed)['surface_fog']
        self.assertEqual(new['evolution'],'rise_resolve');self.assertEqual(new['initial_scale'],.55)
        self.assertNotIn('base_y',new);self.assertNotIn('settle_fraction',new)

    def test_evolution_validation_rejects_invalid_modes_ranges_and_nonfinite_base(self):
        for key,value in (('evolution','rise'),('initial_scale',.149),('initial_scale',1.01),
                          ('settle_fraction',.019),('settle_fraction',.901),('base_y',float('nan'))):
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)

    def test_short_hold_values_roundtrip_without_changing_defaults_or_handoff(self):
        for hold in (.02,.06,.9):
            document=self.document()
            document['surface_fog'].update(enabled=True,evolution='condense',settle_fraction=hold,pull_duration=12.)
            profile=profile_from_document(document)
            self.assertEqual(profile.surface_fog.settle_fraction,hold)
            self.assertEqual(profile.surface_fog.pull_duration,12.)
            self.assertEqual(surface_blend_window(profile),(5.,6.))
            self.assertEqual(document_from_profile(profile),document)
        self.assertEqual(profile_from_document(self.document()).surface_fog.settle_fraction,.65)

    def test_live_optional_evolution_edits_merge_without_populating_other_defaults(self):
        with tempfile.TemporaryDirectory(prefix='haunted-surface-evolution-') as directory:
            path=Path(directory)/'direction.json';document=self.document();save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('initial_scale',.5)
            remote=deepcopy(document);remote['surface_fog']['evolution']='rise_resolve'
            save_direction(remote,path);model.poll_external(0.);model.poll_external(.3)
            self.assertFalse(model.external_pending)
            self.assertEqual(model.profile.surface_fog.initial_scale,.5)
            self.assertEqual(model.profile.surface_fog.evolution,'rise_resolve')
            self.assertNotIn('base_y',model.surface_settings)
            self.assertNotIn('settle_fraction',model.surface_settings)

    def test_condense_optional_defaults_preserve_prior_mode_documents(self):
        for mode in ('erode','rise_resolve'):
            document=self.document();document['surface_fog']['evolution']=mode
            profile=profile_from_document(document)
            self.assertEqual(profile.surface_fog.pull_duration,1.15)
            self.assertEqual(profile.surface_fog.wisp_amount,.35)
            self.assertEqual(document_from_profile(profile),document)
        document=self.document()
        document['surface_fog'].update(evolution='condense',pull_duration=1.15,wisp_amount=.35)
        self.assertEqual(document_from_profile(profile_from_document(document)),document)
        runtime=replace(profile_from_document(self.document()),surface_fog=replace(
            DEFAULT_SURFACE_SETTINGS,evolution='condense',pull_duration=.8,wisp_amount=.2))
        encoded=document_from_profile(runtime)['surface_fog']
        self.assertEqual(encoded['evolution'],'condense')
        self.assertEqual(encoded['pull_duration'],.8);self.assertEqual(encoded['wisp_amount'],.2)
        self.assertNotIn('base_y',encoded)

    def test_condense_controls_validate_finite_values_and_bounds(self):
        for key,value in (('pull_duration',.099),('pull_duration',15.01),('pull_duration',True),
                          ('pull_duration',float('inf')),('wisp_amount',-.01),('wisp_amount',1.01),
                          ('wisp_amount',float('nan')),('wisp_amount','0.3')):
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'].update(evolution='condense')
                document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)
        for duration,wisps in ((.1,0.),(15.,1.)):
            document=self.document()
            document['surface_fog'].update(evolution='condense',pull_duration=duration,wisp_amount=wisps)
            validate_document(document)

    def test_condense_live_controls_merge_independently_without_extra_defaults(self):
        with tempfile.TemporaryDirectory(prefix='haunted-surface-condense-') as directory:
            path=Path(directory)/'direction.json';document=self.document()
            document['surface_fog']['evolution']='condense';save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('pull_duration',.75)
            remote=deepcopy(document);remote['surface_fog']['wisp_amount']=.6;save_direction(remote,path)
            model.poll_external(0.);model.poll_external(.3)
            self.assertFalse(model.external_pending)
            self.assertEqual(model.profile.surface_fog.pull_duration,.75)
            self.assertEqual(model.profile.surface_fog.wisp_amount,.6)
            self.assertNotIn('settle_fraction',model.surface_settings)

    def test_grit_and_water_mask_are_optional_and_preserve_saved_legacy_modes(self):
        for mode in ('erode','rise_resolve','condense'):
            document=self.document();document['surface_fog']['evolution']=mode
            profile=profile_from_document(document)
            self.assertEqual(profile.surface_fog.texture_grit,0.)
            self.assertFalse(profile.surface_fog.water_mask)
            self.assertEqual(document_from_profile(profile),document)
            document['surface_fog'].update(texture_grit=0.,water_mask=False)
            self.assertEqual(document_from_profile(profile_from_document(document)),document)
        document['surface_fog'].update(texture_grit=.65,water_mask=True,pull_duration=7.)
        profile=profile_from_document(document)
        self.assertEqual(profile.surface_fog.pull_duration,7.)
        self.assertEqual(profile.surface_fog.texture_grit,.65)
        self.assertTrue(profile.surface_fog.water_mask)
        self.assertEqual(document_from_profile(profile),document)

    def test_grit_and_water_mask_validate_types_and_ranges(self):
        for key,value in (('texture_grit',-.01),('texture_grit',1.01),('texture_grit',True),
                          ('texture_grit',float('nan')),('water_mask',1),('water_mask','true')):
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)

    def test_live_grit_and_water_controls_merge_without_adding_other_optional_fields(self):
        with tempfile.TemporaryDirectory(prefix='haunted-surface-water-') as directory:
            path=Path(directory)/'direction.json';document=self.document()
            document['surface_fog']['evolution']='condense';save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('texture_grit',.65)
            remote=deepcopy(document);remote['surface_fog']['water_mask']=True;save_direction(remote,path)
            model.poll_external(0.);model.poll_external(.3)
            self.assertFalse(model.external_pending)
            self.assertEqual(model.profile.surface_fog.texture_grit,.65)
            self.assertTrue(model.profile.surface_fog.water_mask)
            self.assertNotIn('pull_duration',model.surface_settings)

    def test_wispy_and_pixel_options_preserve_legacy_saved_bytes_and_explicit_defaults(self):
        for mode in ('erode','rise_resolve','condense'):
            document=self.document();document['surface_fog']['evolution']=mode
            profile=profile_from_document(document)
            self.assertFalse(profile.surface_fog.wispy_formation)
            self.assertEqual(profile.surface_fog.pixel_grain,0.)
            self.assertEqual(document_from_profile(profile),document)
            with tempfile.TemporaryDirectory(prefix='haunted-wispy-compat-') as directory:
                path=Path(directory)/'direction.json';save_direction(document,path)
                before=path.read_bytes();save_direction(document_from_profile(profile),path)
                self.assertEqual(path.read_bytes(),before)
            document['surface_fog'].update(wispy_formation=False,pixel_grain=0.)
            self.assertEqual(document_from_profile(profile_from_document(document)),document)
        active=replace(profile_from_document(self.document()),surface_fog=replace(
            DEFAULT_SURFACE_SETTINGS,evolution='condense',wispy_formation=True,pixel_grain=.8))
        encoded=document_from_profile(active)['surface_fog']
        self.assertTrue(encoded['wispy_formation']);self.assertEqual(encoded['pixel_grain'],.8)

    def test_wispy_and_pixel_options_validate_types_and_ranges(self):
        for key,value in (('wispy_formation',1),('wispy_formation','true'),('pixel_grain',-.01),
                          ('pixel_grain',1.01),('pixel_grain',True),('pixel_grain',float('nan'))):
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)
        for amount in (0.,1.):
            document=self.document();document['surface_fog'].update(wispy_formation=True,pixel_grain=amount)
            validate_document(document)

    def test_wispy_and_pixel_live_edits_merge_independently(self):
        with tempfile.TemporaryDirectory(prefix='haunted-wispy-live-') as directory:
            path=Path(directory)/'direction.json';document=self.document()
            document['surface_fog']['evolution']='condense';save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('wispy_formation',True)
            remote=deepcopy(document);remote['surface_fog']['pixel_grain']=.8;save_direction(remote,path)
            model.poll_external(0.);model.poll_external(.3)
            self.assertFalse(model.external_pending)
            self.assertTrue(model.profile.surface_fog.wispy_formation)
            self.assertEqual(model.profile.surface_fog.pixel_grain,.8)
            self.assertNotIn('texture_grit',model.surface_settings)

    def test_wispy_preset_can_align_global_markers_and_actual_24_second_handoff(self):
        document=default_document()
        document['cues'].update(build_end=24.,blend_end=25.,middle_start=38.,near_end=43.,
            far_start=47.,middle_end=53.,far_end=64.,end=74.)
        document['surface_fog']=default_surface_document(document['cues'])
        document['surface_fog'].update(enabled=True,evolution='condense',wispy_formation=True,
            pixel_grain=.85,build_end=24.,reveal_start=32.,reveal_end=58.,pull_duration=7.)
        profile=profile_from_document(document)
        self.assertEqual(surface_blend_window(profile),(24.,25.))
        self.assertEqual((profile.cue('build_end'),profile.cue('blend_end')),surface_blend_window(profile))
        self.assertEqual(profile.surface_fog.reveal_start,32.)
        self.assertEqual(profile.surface_fog.reveal_end,58.)
        self.assertEqual(profile.cue('end'),74.)
        self.assertEqual(document_from_profile(profile),document)

    def test_lake_options_preserve_legacy_bytes_and_explicit_defaults(self):
        for mode in ('erode','rise_resolve','condense'):
            document=self.document();document['surface_fog']['evolution']=mode
            profile=profile_from_document(document)
            self.assertEqual(profile.surface_fog.foot_curve,0.)
            self.assertFalse(profile.surface_fog.water_settle)
            self.assertEqual((profile.surface_fog.water_settle_start,profile.surface_fog.water_settle_end),(35.,47.))
            self.assertEqual(document_from_profile(profile),document)
            with tempfile.TemporaryDirectory(prefix='haunted-lake-compat-') as directory:
                path=Path(directory)/'direction.json';save_direction(document,path)
                before=path.read_bytes();save_direction(document_from_profile(profile),path)
                self.assertEqual(path.read_bytes(),before)
            # Explicit default endpoints are valid on this longer authored timeline.
            document['cues']['end']=74.
            document['surface_fog'].update(foot_curve=0.,water_settle=False,water_settle_start=35.,water_settle_end=47.)
            self.assertEqual(document_from_profile(profile_from_document(document)),document)

    def test_lake_controls_reject_invalid_values_and_unsafe_enabled_window(self):
        for key,value in (('foot_curve',-.01),('foot_curve',8.01),('foot_curve',True),
                          ('foot_curve',float('nan')),('water_settle',1),('water_settle','true'),
                          ('water_settle_start',-1.),('water_settle_start',float('inf')),
                          ('water_settle_end',47.),('water_settle_end',True)):
            with self.subTest(key=key,value=value):
                document=self.document();document['surface_fog'][key]=value
                with self.assertRaises(ValueError):validate_document(document)
        for start,end in ((5.,20.),(35.,35.),(35.,35.09),(35.,47.)):
            with self.subTest(start=start,end=end):
                document=self.document()
                document['surface_fog'].update(water_settle=True,water_settle_start=start,water_settle_end=end)
                with self.assertRaises(ValueError):validate_document(document)
        document=self.document()
        document['surface_fog'].update(foot_curve=8.,water_settle=True,water_settle_start=35.,water_settle_end=46.)
        validate_document(document)
        document['surface_fog'].update(enabled=True,build_end=36.,reveal_start=37.,reveal_end=46.)
        with self.assertRaisesRegex(ValueError,'hidden blend'):validate_document(document)

    def test_lowering_toggle_fits_defaults_and_undo_restores_optional_omission(self):
        model=DirectionEditor(self.document(),Path(tempfile.gettempdir())/'unused-lake-direction.json')
        before=deepcopy(model.document);model.set_surface('water_settle',True)
        self.assertEqual(model.profile.surface_fog.water_settle_start,35.)
        self.assertEqual(model.profile.surface_fog.water_settle_end,46.)
        self.assertEqual(len(model.undo_stack),1)
        model.undo();self.assertEqual(model.document,before)
        model.set_time('end',34.);unsettled=deepcopy(model.document)
        self.assertNotIn('water_settle_start',model.surface_settings)
        self.assertNotIn('water_settle_end',model.surface_settings)
        model.set_surface('water_settle',True)
        self.assertAlmostEqual(model.profile.surface_fog.water_settle_start,33.9)
        self.assertEqual(model.profile.surface_fog.water_settle_end,34.)
        model.undo();self.assertEqual(model.document,unsettled)

    def test_surface_and_global_retimes_keep_lowering_after_handoff_in_one_undo(self):
        document=self.document()
        document['surface_fog'].update(water_settle=True,water_settle_start=35.,water_settle_end=46.)
        model=DirectionEditor(document,Path(tempfile.gettempdir())/'unused-lake-retime.json')
        before=deepcopy(model.document);model.set_surface('build_end',38.)
        self.assertEqual(model.profile.surface_fog.water_settle_start,39.)
        self.assertEqual(model.profile.surface_fog.water_settle_end,46.)
        self.assertEqual(len(model.undo_stack),1)
        model.undo();self.assertEqual(model.document,before)
        model.set_time('end',34.)
        self.assertAlmostEqual(model.profile.surface_fog.water_settle_start,33.9)
        self.assertEqual(model.profile.surface_fog.water_settle_end,34.)
        model.undo();self.assertEqual(model.document,before)

    def test_lake_live_edits_merge_independently_and_preserve_other_options(self):
        with tempfile.TemporaryDirectory(prefix='haunted-lake-live-') as directory:
            path=Path(directory)/'direction.json';document=self.document();save_direction(document,path)
            model=DirectionEditor(path=path);model.set_surface('foot_curve',4.8)
            remote=deepcopy(document)
            remote['surface_fog'].update(water_settle=True,water_settle_start=35.,water_settle_end=45.)
            save_direction(remote,path);model.poll_external(0.);model.poll_external(.3)
            self.assertFalse(model.external_pending)
            self.assertEqual(model.profile.surface_fog.foot_curve,4.8)
            self.assertTrue(model.profile.surface_fog.water_settle)
            self.assertEqual(model.profile.surface_fog.water_settle_end,45.)
            self.assertNotIn('pixel_grain',model.surface_settings)


if __name__=='__main__':unittest.main()
