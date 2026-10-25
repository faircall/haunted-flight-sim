"""Live datum changes update support alpha without recreating GPU resources."""
from dataclasses import replace
from unittest.mock import Mock,patch
import unittest

import numpy as np
import pyray as pr

from g_huxin_canals_surface_fog import build_surface_support
from huxin_canals_surface_fog import SurfaceFog
from test_huxin_canals_surface_support import fixture,plane
from test_huxin_canals_surface_runtime import fixture_profile


class SurfaceSupportLiveTests(unittest.TestCase):
    def renderer(self):
        renderer=SurfaceFog.__new__(SurfaceFog)
        renderer.prepare=Mock()
        renderer.field=fixture(plane(5.))
        renderer.field_texture=object();renderer.timing_texture=object()
        renderer._support_base_y=0.;renderer._profile=None
        renderer.last_owner_rows=None;renderer.last_rows=None
        initial=renderer.field.atlas(support=build_surface_support(renderer.field))
        renderer._field_atlas_shape=initial[1:]
        return renderer,initial[0]

    def test_only_datum_edits_rebuild_and_upload_alpha_on_the_same_texture(self):
        renderer,original=self.renderer();uploads=[]
        original_field=renderer.field;texture=renderer.field_texture
        byte_count=len(original)
        def upload(target,pointer):
            if target is texture:uploads.append(bytes(pr.ffi.buffer(pointer,byte_count)))
        with patch('g_huxin_canals_surface_fog.build_surface_support',wraps=build_surface_support) as build,\
             patch('huxin_canals_surface_fog.pr.update_texture',side_effect=upload) as gpu_upload,\
             patch('huxin_canals_surface_fog.pr.load_texture_from_image') as allocate,\
             patch('huxin_canals_surface_fog.pr.unload_texture') as unload:
            profile=fixture_profile()
            self.assertTrue(renderer.sync_profile(profile))
            self.assertFalse(renderer.sync_profile(profile))
            wind=replace(profile,surface_fog=replace(profile.surface_fog,wind=(1.,0.,0.)))
            self.assertTrue(renderer.sync_profile(wind))
            build.assert_not_called();self.assertEqual(len(uploads),0)
            negative=replace(wind,surface_fog=replace(wind.surface_fog,base_y=-1.5))
            self.assertTrue(renderer.sync_profile(negative))
            self.assertFalse(renderer.sync_profile(negative))
            self.assertEqual(build.call_count,1);self.assertEqual(len(uploads),1)
            build.assert_called_with(original_field,base_y=-1.5)
            self.assertEqual(renderer._support_base_y,-1.5)
            self.assertIs(renderer.field_texture,texture);self.assertIs(renderer.field,original_field)
            a=np.frombuffer(original,np.uint8).reshape(-1,4)
            b=np.frombuffer(uploads[0],np.uint8).reshape(-1,4)
            np.testing.assert_array_equal(a[:,:3],b[:,:3])
            self.assertTrue(np.any(a[:,3]!=b[:,3]))
            self.assertTrue(renderer.sync_profile(profile))
            self.assertEqual(build.call_count,2);self.assertEqual(len(uploads),2)
            self.assertEqual(uploads[1],original)
            allocate.assert_not_called();unload.assert_not_called()

    def test_failed_rebuild_keeps_the_previous_profile_datum_and_texture(self):
        renderer,_=self.renderer();old=fixture_profile()
        renderer._profile=old;renderer.last_owner_rows=np.zeros((3,256,4),np.float32)
        new=replace(old,surface_fog=replace(old.surface_fog,base_y=-2.))
        with patch('g_huxin_canals_surface_fog.build_surface_support',side_effect=ValueError('bad support')) as build,\
             patch('huxin_canals_surface_fog.pr.update_texture') as upload:
            with self.assertRaisesRegex(ValueError,'bad support'):renderer.sync_profile(new)
            self.assertIs(renderer._profile,old)
            self.assertEqual(renderer._support_base_y,0.)
            upload.assert_not_called()


if __name__=='__main__':unittest.main()
