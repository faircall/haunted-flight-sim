"""GPU-free checks for moon target uploads, reflected coordinates and lifetime."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest

import numpy as np

from g_huxin_moon_fog import MOON_FOG_REGIONS,moon_fog_frame
from g_huxin_moon_sequence import MoonSequence
from huxin_moon_target_fog import MoonTargetFog,MAX_REGIONS,noise_lattice,region_rows


class MoonTargetRuntimeTests(unittest.TestCase):
    def test_noise_tiles_are_repeatable_and_have_wrapped_gutters(self):
        data,width,height=noise_lattice()
        self.assertEqual((width,height),(272,136))
        self.assertEqual(data,noise_lattice()[0])
        pixels=np.frombuffer(data,np.uint8).reshape(height,width,4)
        for z in (0,7,8,31):
            y,x=(z//8)*34,(z%8)*34
            tile=pixels[y:y+34,x:x+34]
            np.testing.assert_array_equal(tile[0,1:33],tile[32,1:33])
            np.testing.assert_array_equal(tile[33,1:33],tile[1,1:33])
            np.testing.assert_array_equal(tile[:,0],tile[:,32])
            np.testing.assert_array_equal(tile[:,33],tile[:,1])
        self.assertGreater(len(np.unique(pixels[:,:,0])),200)

    def test_upload_preserves_effective_extinction_without_a_second_envelope(self):
        q=MoonSequence();q.state='entering';q.elapsed=15.
        frame=moon_fog_frame(q);rows=region_rows(frame.regions)
        self.assertEqual(rows.shape,(4,MAX_REGIONS,4))
        self.assertEqual(rows.dtype,np.float32)
        for i,region in enumerate(frame.regions):
            np.testing.assert_allclose(rows[0,i],(*region.center,region.density))
            np.testing.assert_allclose(rows[1,i],(*region.half_extents,region.edge))
            np.testing.assert_allclose(rows[2,i],(*region.wind,region.noise_size))
        with self.assertRaises(ValueError):region_rows(MOON_FOG_REGIONS+(MOON_FOG_REGIONS[0],))
        with self.assertRaises(ValueError):region_rows((replace(MOON_FOG_REGIONS[0],density=float('nan')),))

    def test_original_approach_and_finished_encounter_allocate_nothing(self):
        q=MoonSequence();renderer=MoonTargetFog(640,360)
        renderer.prepare=Mock(side_effect=AssertionError('Inactive fog allocated GPU resources'))
        for state in ('ordinary','revealed','returned'):
            q.state=state;q.approach=1.
            self.assertIsNone(renderer.render(None,None,q,20.,(.2,.3,.3)))
            self.assertFalse(renderer.last_active)
        q.state='entering';q.elapsed=24.
        self.assertIsNone(renderer.render(None,None,q,24.,(.2,.3,.3)))

    def test_reflection_unfolds_camera_but_keeps_player_regions_and_clock_in_same_world(self):
        q=MoonSequence();q.state='entering';q.elapsed=8.
        renderer=MoonTargetFog(640,360)
        renderer.prepare=Mock();renderer.uniform=Mock()
        renderer.shader=object();renderer.noise=object()
        renderer.target=SimpleNamespace(texture=object())
        names=('regionCount','regionCenters','regionHalves','regionFlow','regionBanks','depthMap','noiseMap')
        renderer.locations={name:i for i,name in enumerate(names)}
        source=SimpleNamespace(depth=object())
        vec=SimpleNamespace(x=.1,y=-.2,z=.9)
        cam=SimpleNamespace(position=SimpleNamespace(x=-2.6,y=3.6,z=-2.8),target=vec,up=vec,fovy=45.)
        center=(1.3,1.4,.2)
        captures=[]
        with patch('huxin_moon_target_fog.pr') as api:
            api.vector3_normalize.return_value=vec
            api.vector3_cross_product.return_value=vec
            for reflected in (False,True):
                q.revealed=reflected
                renderer.uniform.reset_mock()
                texture=renderer.render(source,cam,q,32.,(.175,.235,.248),reflected=reflected,player_center=center)
                self.assertIs(texture,renderer.target.texture)
                values=dict(call.args for call in renderer.uniform.call_args_list)
                captures.append((values,renderer.last_rows.copy()))
                self.assertEqual(values['playerCenter'],center)
                self.assertEqual(values['clock'],32.)
                self.assertEqual(values['resolution'],(640,360))
                self.assertEqual(values['lens'][1],640/360)
                self.assertEqual(values['depthHold'],1.)
                self.assertTrue(renderer.last_active)
                api.set_shader_value_texture.assert_any_call(renderer.shader,renderer.locations['depthMap'],source.depth)
                api.draw_rectangle.assert_called_with(0,0,640,360,api.WHITE)
        ordinary,reflected=captures
        np.testing.assert_array_equal(ordinary[1],reflected[1])
        for name in ('eye','forward','right','up'):
            a,b=ordinary[0][name],reflected[0][name]
            self.assertEqual(b,(a[0],-a[1],a[2]))


if __name__=='__main__':unittest.main()
