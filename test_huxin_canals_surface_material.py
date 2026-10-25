"""GPU-free material binding and deterministic late material reveal tests."""
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

import numpy as np
import pyray as pr

from huxin_canals_surface_material import SurfaceMaterialReveal,material_reveal_weight


def texture(identity):
    value=pr.ffi.new('Texture2D *')
    value.id=identity;value.width=32;value.height=32;value.mipmaps=1;value.format=7
    return value[0]


def model():
    maps=pr.ffi.new('MaterialMap[]',12)
    for index in range(12):maps[index].texture=texture(100+index)
    material=SimpleNamespace(maps=maps)
    return SimpleNamespace(materialCount=1,materials=[material])


class SurfaceMaterialBindingTests(unittest.TestCase):
    def setUp(self):
        self.uniforms={};self.locations={};self.reverse={}
        def location(shader,name):
            if name not in self.locations:
                self.locations[name]=len(self.locations);self.reverse[self.locations[name]]=name
            return self.locations[name]
        def value(shader,where,data,kind):
            count=3 if kind==pr.SHADER_UNIFORM_VEC3 else 1
            self.uniforms[self.reverse[where]]=tuple(float(data[i]) for i in range(count))
        self.patch_location=patch('huxin_canals_surface_material.pr.get_shader_location',side_effect=location)
        self.patch_value=patch('huxin_canals_surface_material.pr.set_shader_value',side_effect=value)
        self.patch_location.start();self.patch_value.start()
        self.addCleanup(self.patch_location.stop);self.addCleanup(self.patch_value.stop)
        self.shader=SimpleNamespace(locs=[-1]*32)
        self.models={name:model() for name in ('canal_roofs','canal_windows','canal_water','canal_annulus','pavilion_posts')}
        self.reveal=SurfaceMaterialReveal(self.shader,self.models)
        self.addCleanup(self.reveal.close)
        field=SimpleNamespace(origin=(-10.,-3.,-20.),shape=(30,20,50),spacing=.6,metadata={'atlas':{'columns':4}})
        self.renderer=SimpleNamespace(field=field,field_texture=texture(901),timing_texture=texture(902),last_rows=np.zeros((3,256,4)))
        self.renderer.sync_profile=Mock()
        self.settings=SimpleNamespace(enabled=True,amount=1.,evolution='rise_resolve',settle_fraction=.65)
        self.sequence=SimpleNamespace(direction=SimpleNamespace(surface_fog=self.settings),elapsed=15.,state='canals')

    def test_binds_only_incoming_models_to_unused_map_slots_and_restores_them(self):
        self.assertTrue(self.reveal.sync(self.renderer,self.sequence))
        for name,asset in self.models.items():
            maps=asset.materials[0].maps
            changed=name in ('canal_roofs','canal_windows')
            self.assertEqual(maps[pr.MATERIAL_MAP_METALNESS].texture.id,901 if changed else 101)
            self.assertEqual(maps[pr.MATERIAL_MAP_ROUGHNESS].texture.id,902 if changed else 103)
            self.assertEqual(maps[pr.MATERIAL_MAP_DIFFUSE].texture.id,100)
            self.assertEqual(maps[pr.MATERIAL_MAP_NORMAL].texture.id,102)
        self.assertEqual(self.shader.locs[pr.SHADER_LOC_MAP_NORMAL],-1)
        self.reveal.close()
        for asset in self.models.values():
            self.assertEqual(asset.materials[0].maps[pr.MATERIAL_MAP_METALNESS].texture.id,101)
            self.assertEqual(asset.materials[0].maps[pr.MATERIAL_MAP_ROUGHNESS].texture.id,103)
        self.assertEqual(self.shader.locs[pr.SHADER_LOC_MAP_METALNESS],-1)
        self.assertEqual(self.shader.locs[pr.SHADER_LOC_MAP_ROUGHNESS],-1)

    def test_sync_uploads_current_frame_and_profile_before_geometry(self):
        self.reveal.sync(self.renderer,self.sequence)
        self.renderer.sync_profile.assert_called_once_with(self.sequence.direction)
        self.assertEqual(self.uniforms['surfaceResolveElapsed'],(15.,))
        self.assertAlmostEqual(self.uniforms['surfaceResolveSettle'][0],.65,places=6)
        self.assertEqual(self.uniforms['surfaceMaterialShape'],(30.,20.,50.))
        self.assertEqual(self.uniforms['surfaceMaterialOrigin'],(-10.,-3.,-20.))
        self.sequence.elapsed=8.5;self.settings.settle_fraction=.8;self.settings.amount=.4
        self.reveal.sync(self.renderer,self.sequence)
        self.assertEqual(self.uniforms['surfaceResolveElapsed'],(8.5,))
        self.assertAlmostEqual(self.uniforms['surfaceResolveSettle'][0],.8,places=6)
        self.assertAlmostEqual(self.uniforms['surfaceResolveAmount'][0],.4,places=6)

    def test_old_mode_disabled_settings_and_unactivated_sequence_never_enable_coat(self):
        for property_name,value in (('evolution','erode'),('enabled',False),('amount',0.)):
            with self.subTest(property=property_name):
                original=getattr(self.settings,property_name);setattr(self.settings,property_name,value)
                self.assertFalse(self.reveal.sync(self.renderer,self.sequence))
                self.assertEqual(self.uniforms['surfaceResolveActive'],(0.,))
                setattr(self.settings,property_name,original)
        self.sequence.state='ordinary'
        self.assertFalse(self.reveal.sync(self.renderer,self.sequence))
        self.renderer.sync_profile.assert_not_called()

    def test_recreated_texture_rebinds_without_losing_original_materials(self):
        self.reveal.sync(self.renderer,self.sequence)
        self.renderer.timing_texture=texture(903)
        self.reveal.sync(self.renderer,self.sequence)
        self.assertEqual(self.models['canal_roofs'].materials[0].maps[pr.MATERIAL_MAP_ROUGHNESS].texture.id,903)
        self.assertEqual(len(self.reveal._saved),4)
        self.reveal.close()
        self.assertEqual(self.models['canal_roofs'].materials[0].maps[pr.MATERIAL_MAP_ROUGHNESS].texture.id,103)

    def test_condense_uses_live_pull_controls_and_switches_back_to_original_mode(self):
        self.settings.evolution='condense'
        self.settings.pull_duration=1.4
        self.settings.noise_size=2.1
        self.settings.pattern_amount=.8
        self.assertTrue(self.reveal.sync(self.renderer,self.sequence))
        self.assertEqual(self.uniforms['surfaceCondense'],(1.,))
        self.assertAlmostEqual(self.uniforms['surfacePullDuration'][0],1.4,places=6)
        self.assertAlmostEqual(self.uniforms['surfaceNoiseSize'][0],2.1,places=6)
        self.assertAlmostEqual(self.uniforms['surfacePatternAmount'][0],.8,places=6)
        self.settings.pull_duration=.8;self.settings.settle_fraction=.5
        self.sequence.elapsed=12.
        self.reveal.sync(self.renderer,self.sequence)
        self.assertAlmostEqual(self.uniforms['surfacePullDuration'][0],.8,places=6)
        self.assertEqual(self.uniforms['surfaceResolveSettle'],(.5,))
        self.assertEqual(self.uniforms['surfaceResolveElapsed'],(12.,))
        self.settings.evolution='rise_resolve'
        self.assertTrue(self.reveal.sync(self.renderer,self.sequence))
        self.assertEqual(self.uniforms['surfaceCondense'],(0.,))
        self.settings.evolution='erode'
        self.assertFalse(self.reveal.sync(self.renderer,self.sequence))
        self.assertEqual(self.uniforms['surfaceResolveActive'],(0.,))


class MaterialRevealTimingTests(unittest.TestCase):
    def test_condensation_material_and_volume_share_identical_spatial_phase_math(self):
        # The volume and opaque material compile separately. A divergent
        # local pull schedule can expose textured geometry through its fog.
        root=Path(__file__).resolve().parent/'shaders'
        reference=(root/'huxin_canals_condense.glsl').read_text().strip()
        for filename in ('huxin_canals.fs','huxin_canals_surface_fog.fs'):
            with self.subTest(shader=filename):
                source=(root/filename).read_text()
                self.assertEqual(source.count('// BEGIN CONDENSE'),1)
                self.assertEqual(source.count('// END CONDENSE'),1)
                first=source.index('// BEGIN CONDENSE')
                last=source.index('// END CONDENSE')+len('// END CONDENSE')
                shared=source[first:last].strip()
                self.assertEqual(shared,reference)

    def test_colour_stays_ghostly_until_settled_then_smoothly_reaches_real_material(self):
        for value in (-1.,0.,.3,.65):self.assertEqual(material_reveal_weight(value),0.)
        self.assertAlmostEqual(material_reveal_weight(.825),.5)
        self.assertEqual(material_reveal_weight(1.),1.)
        self.assertEqual(material_reveal_weight(2.),1.)
        values=[material_reveal_weight(p) for p in np.linspace(0.,1.,101)]
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertLess(material_reveal_weight(.65001),1e-10)
        self.assertLess(1.-material_reveal_weight(.99999),1e-10)
        self.assertEqual(material_reveal_weight(.75,.8),0.)
        self.assertAlmostEqual(material_reveal_weight(.9,.8),.5)


if __name__=='__main__':unittest.main()
