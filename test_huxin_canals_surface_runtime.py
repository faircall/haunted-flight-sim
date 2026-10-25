"""GPU-free semantic timing rows consumed by the surface fog shader."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import numpy as np

from g_huxin_canals_direction import (FogGroupSettings, default_document,
                                     profile_from_document)
from g_huxin_canals_surface_settings import SurfaceFogSettings, surface_blend_window
from g_huxin_canals_targets import TargetGroup
from huxin_canals_surface_fog import timing_rows,owner_rows,SurfaceFog,surface_noise_lattice
from huxin_canals_volumes import noise_lattice


def fixture_profile(**surface_changes):
    profile=profile_from_document(default_document())
    settings=SurfaceFogSettings(enabled=True,build_end=9.,reveal_start=11.,reveal_end=25.)
    groups=(FogGroupSettings('house-a',(0.,0.,0.),1.,1.,8.,18.),
            FogGroupSettings('house-b',(0.,0.,0.),1.,1.,12.,22.),
            FogGroupSettings('house-c',(0.,0.,0.),1.,1.,7.,9.))
    return replace(profile,groups=groups,surface_fog=replace(settings,**surface_changes))


class SurfaceTimingRowsTests(unittest.TestCase):
    def test_painted_texture_preserves_the_existing_three_dimensional_noise(self):
        old,w,h=noise_lattice();new,nw,nh=surface_noise_lattice()
        self.assertEqual((w,h),(nw,nh))
        a=np.frombuffer(old,np.uint8).reshape(h,w,4)
        b=np.frombuffer(new,np.uint8).reshape(h,w,4)
        np.testing.assert_array_equal(a[:,:,:3],b[:,:,:3])
        self.assertEqual(len(np.unique(b[:,:,3])),6)
        self.assertGreater(int(b[:,:,3].max())-int(b[:,:,3].min()),100)

    def test_baked_owner_order_resolves_names_and_reserves_generic_row_zero(self):
        profile=fixture_profile();before=hash(profile)
        rows=timing_rows(profile,('house-b','missing-building','house-a'))
        self.assertEqual(rows.shape,(256,4));self.assertEqual(rows.dtype,np.float32)
        self.assertTrue(rows.flags.c_contiguous)
        np.testing.assert_array_equal(rows[0],[11.,25.,0.,0.])
        np.testing.assert_array_equal(rows[1],[12.,22.,0.,0.])
        np.testing.assert_array_equal(rows[2],[11.,25.,0.,0.])
        np.testing.assert_array_equal(rows[3],[10.,18.,0.,0.])
        np.testing.assert_array_equal(rows[255],[11.,25.,0.,0.])
        self.assertEqual(hash(profile),before)
        self.assertEqual(profile.groups[0].reveal_start,8.)

    def test_building_clear_waits_for_complete_geometry_handoff(self):
        profile=fixture_profile()
        self.assertEqual(surface_blend_window(profile),(9.,10.))
        rows=timing_rows(profile,('house-a','house-c'))
        self.assertEqual(rows[1,0],10.)
        self.assertEqual(rows[2,0],10.)
        self.assertAlmostEqual(float(rows[2,1]),10.1,places=5)
        self.assertGreater(rows[2,1],rows[2,0])

    def test_unowned_fallback_is_also_clamped_for_direct_runtime_callers(self):
        # Validation rejects this incomplete authored window. Runtime callers
        # constructing a frozen profile directly still cannot clear mid-blend.
        profile=fixture_profile(reveal_start=8.,reveal_end=9.5)
        rows=timing_rows(profile,('missing-building',))
        np.testing.assert_array_equal(rows[:,0],np.full(256,10.,dtype=np.float32))
        np.testing.assert_allclose(rows[:,1],10.1,atol=1e-6)
        np.testing.assert_array_equal(rows[:,2:],np.zeros((256,2),dtype=np.float32))

    def test_disabling_building_timing_applies_one_global_window_to_every_owner(self):
        profile=fixture_profile(use_building_timing=False)
        rows=timing_rows(profile,('house-a','house-b','house-c'))
        expected=np.tile(np.array([11.,25.,0.,0.],dtype=np.float32),(256,1))
        np.testing.assert_array_equal(rows,expected)
        # Fresh arrays prevent a caller's staging-buffer edit from mutating
        # the next upload or the immutable direction profile.
        rows[0,0]=-100.
        np.testing.assert_array_equal(timing_rows(profile,()),expected)

    def test_owner_capacity_has_explicit_guard_instead_of_index_overrun(self):
        profile=fixture_profile()
        ids=tuple(f'house-{i}' for i in range(255))
        self.assertEqual(timing_rows(profile,ids).shape,(256,4))
        with self.assertRaisesRegex(ValueError,'255|owner|building'):
            timing_rows(profile,ids+('one-too-many',))


class SurfaceOwnerRowsTests(unittest.TestCase):
    def test_metadata_uses_actual_unpadded_roof_and_horizontal_dimensions(self):
        profile=fixture_profile(base_y=-1.5)
        target=TargetGroup('house-b','Test house','house',(9.,3.,14.),(4.05,4.,6.05),'near')
        rows=owner_rows(profile,('missing-building','house-b'),targets=(target,))
        self.assertEqual(rows.shape,(3,256,4));self.assertEqual(rows.dtype,np.float32)
        self.assertTrue(rows.flags.c_contiguous)
        np.testing.assert_array_equal(rows[0],timing_rows(profile,('missing-building','house-b')))
        # Padded roof top 7 -> actual 6.3, and base -1.5 -> 7.8m rise.
        np.testing.assert_allclose(rows[1,2],[9.,-1.5,14.,7.8],atol=1e-6)
        np.testing.assert_allclose(rows[2,2],[3.,5.,0.,0.],atol=1e-6)
        np.testing.assert_array_equal(rows[1,0],[0.,-1.5,0.,9.])
        np.testing.assert_array_equal(rows[1,1],[0.,-1.5,0.,9.])
        np.testing.assert_array_equal(rows[2,0],np.zeros(4))
        np.testing.assert_array_equal(rows[2,1],np.zeros(4))

    def test_owner_order_and_base_height_edits_leave_reveal_timings_identical(self):
        profile=fixture_profile(base_y=0.)
        a=TargetGroup('house-a','A','house',(-4.,2.,9.),(2.,3.,4.),'near')
        b=TargetGroup('house-b','B','house',(8.,3.,17.),(4.,4.,5.),'near')
        owners=('house-b','house-a')
        rows=owner_rows(profile,owners,targets={'house-a':a,'house-b':b})
        shifted=owner_rows(replace(profile,surface_fog=replace(profile.surface_fog,base_y=2.)),owners,targets=(b,a))
        np.testing.assert_array_equal(rows[0],shifted[0])
        np.testing.assert_array_equal(rows[2],shifted[2])
        self.assertEqual(rows[1,1,0],8.);self.assertEqual(rows[1,2,0],-4.)
        np.testing.assert_allclose(shifted[1,1:3,3],rows[1,1:3,3]-2.,atol=1e-6)
        np.testing.assert_array_equal(shifted[1,:,1],np.full(256,2.))
        self.assertEqual(profile.surface_fog.base_y,0.)

    def test_sync_profile_uploads_three_rows_once_and_refreshes_live_metadata(self):
        renderer=SurfaceFog.__new__(SurfaceFog)
        renderer.prepare=Mock();renderer.field=SimpleNamespace(owners=('house-a','house-b'))
        renderer.sync_support=Mock(return_value=False)
        renderer.timing_texture=object();renderer._profile=None
        renderer.last_owner_rows=None;renderer.last_rows=None
        profile=fixture_profile()
        with patch('huxin_canals_surface_fog.pr.update_texture') as upload:
            self.assertTrue(renderer.sync_profile(profile))
            self.assertEqual(upload.call_count,1)
            self.assertEqual(renderer.last_owner_rows.shape,(3,256,4))
            np.testing.assert_array_equal(renderer.last_rows,timing_rows(profile,renderer.field.owners))
            self.assertFalse(renderer.sync_profile(profile))
            self.assertEqual(upload.call_count,1)
            updated=replace(profile,surface_fog=replace(profile.surface_fog,base_y=-1.))
            self.assertTrue(renderer.sync_profile(updated))
            self.assertEqual(upload.call_count,2)
            np.testing.assert_array_equal(renderer.last_owner_rows[1,:,1],np.full(256,-1.))
            np.testing.assert_array_equal(renderer.last_rows,timing_rows(profile,renderer.field.owners))
            self.assertIs(renderer._profile,updated)


if __name__=='__main__':unittest.main()
