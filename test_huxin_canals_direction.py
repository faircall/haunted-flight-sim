"""Pure direction-data tests; persistence always uses temporary files."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
import json
import math
import tempfile
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import (
    BANDS, CUES, CUE_LABELS, DEFAULT_DIRECTION, DEFAULT_PROFILE, DEFAULT_PATH,
    CameraPose, DirectionError, default_document, document_from_profile,
    load_direction, profile_from_document, sample_camera, save_direction,
    validate_document,
)


class DirectionDocumentTests(unittest.TestCase):
    def test_defaults_preserve_v17_and_the_checked_in_document(self):
        expected = dict(zip(CUES, (0.,5.,6.,12.,14.,20.,22.,32.,46.)))
        self.assertEqual(default_document()['cues'], expected)
        self.assertEqual(set(CUE_LABELS), set(CUES))
        self.assertIs(DEFAULT_PROFILE, DEFAULT_DIRECTION)
        self.assertEqual(profile_from_document(load_direction(DEFAULT_PATH)), DEFAULT_DIRECTION)
        self.assertEqual(document_from_profile(DEFAULT_DIRECTION), default_document())
        self.assertFalse(DEFAULT_DIRECTION.camera_enabled)
        for name in CUES:
            self.assertEqual(DEFAULT_DIRECTION.cue(name), expected[name])
            self.assertEqual(DEFAULT_DIRECTION.time(name), expected[name])
            key = DEFAULT_DIRECTION.camera(name)
            self.assertEqual(key.eye, (4.05,3.2,3.05))
            self.assertEqual(key.target, (-.7,1.5,-1.2))
            self.assertEqual(key.fov, 78.)
        for name in BANDS:
            bank = DEFAULT_DIRECTION.band(name)
            self.assertEqual((bank.offset,bank.scale,bank.opacity), ((0.,0.,0.),1.,1.))
        with self.assertRaises(KeyError):DEFAULT_DIRECTION.cue('typo')
        with self.assertRaises(KeyError):DEFAULT_DIRECTION.band('typo')
        with self.assertRaises(KeyError):DEFAULT_DIRECTION.camera('typo')

    def test_normalization_and_profile_do_not_share_editable_nested_state(self):
        source = default_document()
        source['banks']['near']['offset'] = (2,3,4)
        normalized = validate_document(source)
        profile = profile_from_document(source)
        self.assertIsInstance(normalized['cues']['end'], float)
        self.assertEqual(normalized['banks']['near']['offset'], [2.,3.,4.])
        normalized['banks']['near']['offset'][0] = 80.
        source['cameras']['keys']['start']['eye'][0] = 100.
        source['cues']['end'] = 60.
        self.assertEqual(profile.band('near').offset, (2.,3.,4.))
        self.assertEqual(profile.camera('start').eye, (4.05,3.2,3.05))
        self.assertEqual(profile.cue('end'), 46.)
        another = document_from_profile(profile)
        another['banks']['near']['offset'][0] = -50.
        self.assertEqual(profile.band('near').offset, (2.,3.,4.))
        self.assertEqual(default_document(), document_from_profile(DEFAULT_DIRECTION))
        self.assertEqual(hash(profile), hash(profile_from_document(document_from_profile(profile))))
        with self.assertRaises(FrozenInstanceError):profile.camera_enabled = True
        with self.assertRaises(FrozenInstanceError):profile.band('near').scale = 2.

    def test_invalid_timings_fields_and_numbers_report_their_location(self):
        cases = (
            (('cues','start'), .1, 'cues.start'),
            (('cues','blend_end'), 5., 'cues.blend_end'),
            (('cues','near_end'), 11., 'cues.near_end'),
            (('cues','end'), 1800.1, 'cues.end'),
            (('cues','end'), math.nan, 'cues.end'),
            (('cues','end'), math.inf, 'cues.end'),
            (('cues','end'), True, 'cues.end'),
            (('cues','end'), '46', 'cues.end'),
            (('banks','near','offset'), [0,0,math.inf], 'banks.near.offset'),
            (('banks','near','offset'), [0,0], 'banks.near.offset'),
            (('banks','near','offset'), [1001,0,0], 'banks.near.offset'),
            (('banks','middle','scale'), 0, 'banks.middle.scale'),
            (('banks','far','opacity'), -1, 'banks.far.opacity'),
            (('cameras','enabled'), 1, 'cameras.enabled'),
            (('cameras','keys','start','fov'), 111, 'cameras.keys.start.fov'),
            (('version',), True, 'version'),
            (('version',), 2, 'version'),
        )
        for path,value,message in cases:
            with self.subTest(path=path,value=value):
                doc=default_document(); target=doc
                for key in path[:-1]:target=target[key]
                target[path[-1]]=value
                with self.assertRaisesRegex(DirectionError,message):validate_document(doc)
        doc=default_document(); doc['cues']['blend_end']=5.1
        self.assertEqual(validate_document(doc)['cues']['blend_end'],5.1)
        doc=default_document(); doc['cues']['new_cue']=25
        with self.assertRaisesRegex(DirectionError,'unknown field new_cue'):validate_document(doc)
        doc=default_document(); del doc['banks']['middle']
        with self.assertRaisesRegex(DirectionError,'missing middle'):validate_document(doc)
        doc=default_document(); doc['cameras']['keys']['start']['target']=doc['cameras']['keys']['start']['eye'][:]
        with self.assertRaisesRegex(DirectionError,'distinct'):validate_document(doc)


class DirectionPersistenceTests(unittest.TestCase):
    def test_save_reload_and_fresh_profile_use_the_edited_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'subdir'/'direction.json'
            doc=default_document(); doc['cues']['end']=65.
            doc['banks']['near'].update(offset=[1.25,-.5,2.],scale=1.2,opacity=.7)
            doc['cameras']['enabled']=True
            doc['cameras']['keys']['end']['eye']=[7.,4.,5.]
            source=deepcopy(doc)
            self.assertEqual(save_direction(doc,path),path)
            self.assertEqual(doc,source)
            raw=path.read_bytes()
            self.assertNotIn(b'\r',raw)
            self.assertTrue(raw.endswith(b'\n'))
            fresh=profile_from_document(load_direction(path))
            self.assertEqual(fresh,profile_from_document(doc))
            self.assertEqual(fresh.cue('end'),65.)
            self.assertEqual(fresh.band('near').offset,(1.25,-.5,2.))
            self.assertTrue(fresh.camera_enabled)
            self.assertEqual(fresh.camera('end').eye,(7.,4.,5.))
            self.assertEqual(list(path.parent.iterdir()),[path])

    def test_invalid_save_and_failed_atomic_replace_keep_the_last_good_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'direction.json'
            save_direction(default_document(),path); original=path.read_bytes()
            bad=default_document(); bad['cues']['end']=math.nan
            with self.assertRaises(DirectionError):save_direction(bad,path)
            self.assertEqual(path.read_bytes(),original)
            changed=default_document(); changed['cues']['end']=60.
            with patch('g_huxin_canals_direction.os.replace',side_effect=OSError('simulated replace failure')):
                with self.assertRaisesRegex(DirectionError,'simulated replace failure'):
                    save_direction(changed,path)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(path.parent.iterdir()),[path])

    def test_missing_invalid_and_duplicate_files_never_silently_use_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'direction.json'
            with self.assertRaisesRegex(DirectionError,'Cannot load direction'):load_direction(path)
            self.assertFalse(path.exists())
            for payload in ('{bad json', '{"version":1,"version":1}',
                            json.dumps({'version':2}), json.dumps({**default_document(),'cues':{}})):
                path.write_text(payload,encoding='utf-8')
                with self.assertRaises(DirectionError):load_direction(path)
                self.assertEqual(path.read_text(encoding='utf-8'),payload)


class DirectionCameraTests(unittest.TestCase):
    @staticmethod
    def moving_document():
        doc=default_document(); doc['cameras']['enabled']=True
        doc['cameras']['keys']={
            'start': {'eye':[4.,3.,4.],'target':[0.,1.,0.],'fov':70.},
            'build_end': {'eye':[8.,5.,4.],'target':[0.,2.,0.],'fov':80.},
            'end': {'eye':[12.,6.,6.],'target':[1.,2.,0.],'fov':90.},
        }
        return doc

    def test_disabled_keys_require_explicit_preview(self):
        self.assertIsNone(sample_camera(DEFAULT_DIRECTION,2.))
        self.assertEqual(sample_camera(DEFAULT_DIRECTION,2.,include_disabled=True),
                         CameraPose((4.05,3.2,3.05),(-.7,1.5,-1.2),78.))
        doc=default_document(); doc['cameras']['keys']={}
        self.assertIsNone(sample_camera(profile_from_document(doc),2.,include_disabled=True))
        doc['cameras']['enabled']=True
        with self.assertRaisesRegex(DirectionError,'add a camera key'):validate_document(doc)

    def test_camera_interpolates_partial_keys_at_saved_cue_times_and_holds_ends(self):
        profile=profile_from_document(self.moving_document())
        self.assertEqual(sample_camera(profile,-1.),CameraPose((4.,3.,4.),(0.,1.,0.),70.))
        self.assertEqual(sample_camera(profile,2.5),CameraPose((6.,4.,4.),(0.,1.5,0.),75.))
        self.assertEqual(sample_camera(profile,5.),CameraPose((8.,5.,4.),(0.,2.,0.),80.))
        self.assertEqual(sample_camera(profile,500.),CameraPose((12.,6.,6.),(1.,2.,0.),90.))
        for t in (0.,5.,46.):
            center=sample_camera(profile,t)
            for sample in (sample_camera(profile,t-.001),sample_camera(profile,t+.001)):
                self.assertLess(math.dist(center.eye,sample.eye),1e-8)
        doc=self.moving_document(); doc['cues']['build_end']=4.
        shifted=profile_from_document(doc)
        self.assertEqual(sample_camera(shifted,2.),CameraPose((6.,4.,4.),(0.,1.5,0.),75.))
        with self.assertRaises(DirectionError):sample_camera(profile,math.nan)

    def test_camera_path_cannot_cross_its_own_target_between_valid_keys(self):
        doc=default_document()
        doc['cameras']['keys']={
            'start':{'eye':[1.,0.,0.],'target':[0.,0.,0.],'fov':70.},
            'end':{'eye':[-1.,0.,0.],'target':[0.,0.,0.],'fov':70.},
        }
        with self.assertRaisesRegex(DirectionError,'crosses its target'):validate_document(doc)


if __name__ == '__main__':unittest.main()
