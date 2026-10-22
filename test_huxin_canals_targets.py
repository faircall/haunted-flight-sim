"""The compact fog catalog must cover real geometry without merging houses."""
from dataclasses import FrozenInstanceError
import json
import unittest

from g_huxin_canals_targets import (MANIFEST_PATH,CATALOG_PATH,catalog_from_manifest,
                                   target_groups,target_group,coverage_bounds)
from g_huxin_canals_direction import building_document,profile_from_document


class FogTargetTests(unittest.TestCase):
    def test_catalog_is_small_cached_and_matches_current_exported_roofs(self):
        manifest=json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        catalog=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        expected=json.loads(json.dumps(catalog_from_manifest(manifest)))
        self.assertEqual(catalog,expected)
        self.assertLess(CATALOG_PATH.stat().st_size,100000)
        self.assertIs(target_groups(),target_groups())
        self.assertEqual(sum(t.kind=='house' for t in target_groups()),142)
        self.assertEqual(len({t.id for t in target_groups()}),170)
        self.assertEqual({t.kind for t in target_groups()}, {'house','water','quay','bridge','backdrop','foreground'})
        # Source reuses seed2309 for two different actual houses. Both need
        # independent settings and stable, unambiguous selection identifiers.
        self.assertGreater(target_group('house-2309-east').center[0],0.)
        self.assertLess(target_group('house-2309-west').center[0],0.)
        for source,target in zip(manifest['houses'],(t for t in target_groups() if t.kind=='house')):
            low=tuple(c-h for c,h in zip(target.center,target.half_extents))
            high=tuple(c+h for c,h in zip(target.center,target.half_extents))
            for corner in source['bounds_corners']:
                for axis in range(3):self.assertTrue(low[axis]-1e-9<=corner[axis]<=high[axis]+1e-9)
            self.assertLessEqual(low[1],source['foundation_bottom']+1e-9)
            self.assertGreater(high[1],max(p[1] for p in source['bounds_corners'])+.65)
        with self.assertRaises(FrozenInstanceError):target_groups()[0].center=(0.,0.,0.)

    def test_editor_envelope_scales_locally_and_moves_with_only_its_target(self):
        target=target_group('house-410');doc=building_document()
        a=coverage_bounds(target,profile_from_document(doc).group(target.id))
        doc['fog']['groups'][target.id].update(scale=2.,offset=[1.,2.,3.])
        b=coverage_bounds(target,profile_from_document(doc).group(target.id))
        for endpoint_a,endpoint_b in zip(a,b):
            expected=tuple(c+2*(v-c)+o for c,v,o in zip(target.center,endpoint_a,(1.,2.,3.)))
            for x,y in zip(expected,endpoint_b):self.assertAlmostEqual(x,y)


if __name__=='__main__':unittest.main()
