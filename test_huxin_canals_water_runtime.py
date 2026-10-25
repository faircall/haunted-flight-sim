"""GPU-free contracts for moving water, its mesh and reflected scene together."""
from collections import defaultdict
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest

import pyray as pr

from g_huxin_canals_direction import default_document,profile_from_document
from g_huxin_canals_layout import WATER_Y
from g_huxin_canals_sequence import CanalSequence
from g_huxin_canals_surface_settings import default_surface_document
from g_huxin_canals_water_fog import render_water_height
from huxin_canals_viewer import Lake
from temple_interior_viewer import camera
from test_huxin_canals_fog import capture_mist_pass


def profile(**changes):
    document=default_document()
    document['cues'].update(build_end=24.,blend_end=25.,middle_start=38.,near_end=43.,
        far_start=47.,middle_end=53.,far_end=64.,end=74.)
    document['surface_fog']=default_surface_document(document['cues'])
    document['surface_fog'].update(enabled=True,evolution='condense',water_mask=True,
        water_settle=True,water_settle_start=35.,water_settle_end=47.,foot_curve=4.8)
    document['surface_fog'].update(changes)
    return profile_from_document(document)


class FogRecorder:
    def __init__(self):self.texture=object();self.calls=[];self.last_active=True
    def clear(self):return self.texture
    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False,base_texture=None,surface_renderer=None):
        self.calls.append((water_y,reflected))
        return self.texture


def cpu_lake(direction):
    lake=Lake.__new__(Lake);lake.sequence=CanalSequence(direction);lake._world_override=None
    lake.shader=SimpleNamespace(id=1);lake.water_shader=SimpleNamespace(id=3)
    lake.player=SimpleNamespace(skin=SimpleNamespace(id=2))
    lake.locations={i:defaultdict(lambda:-1) for i in (1,2,3)}
    lake.models={'moon_mirror':SimpleNamespace(transform=None)}
    lake.canals_manifest={'models':{'canal_ground':{},'canal_water':{}}}
    lake.raw=object();lake.reflection_raw=object();lake.reflection=object()
    lake.post=SimpleNamespace(id=4);lake.smoke=object();lake.sky=SimpleNamespace(draw=Mock())
    lake.draw=Mock();lake.uniform=Mock();lake.surface_material=None
    return lake


class WaterHeightTests(unittest.TestCase):
    def test_water_stays_at_lake_level_through_handoff_then_descends_continuously(self):
        p=profile()
        for elapsed in (0.,24.,24.5,25.,34.,35.):
            self.assertEqual(render_water_height(p,elapsed),0.)
        self.assertEqual(render_water_height(p,41.),WATER_Y*.5)
        self.assertEqual(render_water_height(p,47.),WATER_Y)
        self.assertEqual(render_water_height(p,90.),WATER_Y)
        heights=[render_water_height(p,35.+i*.1) for i in range(121)]
        self.assertTrue(all(a>=b for a,b in zip(heights,heights[1:])))
        for edge in (35.,47.):
            self.assertLess(abs(render_water_height(p,edge-.001)-render_water_height(p,edge+.001)),1.e-8)

    def test_fog_datum_does_not_raise_actual_water_and_backward_seeks_are_exact(self):
        p=profile(base_y=.8);times=(47.,24.5,41.,35.,44.,25.,36.,60.)
        first={time:render_water_height(p,time) for time in times}
        self.assertEqual(first[35.],0.)
        self.assertEqual(first[41.],WATER_Y*.5)
        self.assertEqual(first[47.],WATER_Y)
        for time in reversed(times):
            self.assertEqual(render_water_height(p,time),first[time])
            self.assertEqual(render_water_height(p,time,state='entering'),first[time])
        self.assertEqual(p.surface_fog.base_y,.8)

    def test_old_world_and_legacy_disabled_or_inactive_modes_keep_previous_heights(self):
        legacy=profile_from_document(default_document())
        for elapsed in (0.,24.5,41.,90.):
            self.assertEqual(render_water_height(legacy,elapsed),WATER_Y)
            self.assertEqual(render_water_height(legacy,elapsed,revealed=False),0.)
            self.assertEqual(render_water_height(profile(),elapsed,revealed=False),0.)
        for changes in ({'enabled':False},{'amount':0.},{'water_mask':False},{'water_settle':False}):
            with self.subTest(changes=changes):
                self.assertEqual(render_water_height(profile(**changes),41.),WATER_Y)
        self.assertEqual(render_water_height(profile(),41.,state='ordinary'),WATER_Y)


class MovingWaterRenderTests(unittest.TestCase):
    def setUp(self):
        self.lake=cpu_lake(profile())
        self.actor=SimpleNamespace(x=1.65,height=.325,z=1.65)
        self.camera=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78.)

    def capture_world_frame(self,elapsed,revealed=True):
        lake=self.lake;lake.sequence.seek(elapsed);lake._world_override=revealed
        lake.draw.reset_mock();lake.uniform.reset_mock();lake.sky.draw.reset_mock()
        lake.mist_pass=Mock()
        # Vector/matrix maths remain real. Every actual GPU entry point used
        # by this render path is replaced; no window or audio device is opened.
        original=pr.rl
        class CpuOnlyRl:
            def __getattr__(self,name):
                if name in ('rlDisableBackfaceCulling','rlEnableBackfaceCulling',
                            'rlDrawRenderBatchActive','rlDisableDepthMask','rlEnableDepthMask'):
                    return lambda *args:None
                return getattr(original,name)
        with ExitStack() as stack:
            stack.enter_context(patch.object(pr,'rl',CpuOnlyRl()))
            for name in ('begin_texture_mode','end_texture_mode','clear_background','draw_rectangle',
                         'begin_mode_3d','end_mode_3d','draw_billboard'):
                stack.enter_context(patch.object(pr,name))
            lake._render_world_frame(self.actor,self.camera,87.+elapsed,False,False,False,object())
        return lake

    def test_water_mesh_and_reflected_objects_use_the_same_intermediate_plane(self):
        for elapsed,expected in ((25.,0.),(35.,0.),(41.,WATER_Y*.5),(47.,WATER_Y),(41.,WATER_Y*.5)):
            with self.subTest(elapsed=elapsed):
                lake=self.capture_world_frame(elapsed)
                self.assertEqual(lake.water_y,expected)
                water=[call.args for call in lake.draw.call_args_list if call.args[0]=='canal_water']
                self.assertEqual(len(water),1)
                offset=water[0][1] if len(water[0])>1 else (0,0,0)
                self.assertAlmostEqual(WATER_Y+offset[1],expected)
                self.assertEqual((offset[0],offset[2]),(0,0))
                posts=[call.args for call in lake.draw.call_args_list if call.args[0]=='pavilion_posts']
                self.assertEqual(posts[0][1],(0,2*expected,0))
                self.assertEqual(posts[1][1],(0,0,0))
                self.assertEqual(posts[0][2],(1,-1,1))
                mirror_camera=lake.sky.draw.call_args_list[0].args[0]
                self.assertAlmostEqual(mirror_camera.position.y,2*expected-self.camera.position.y,places=5)
                self.assertAlmostEqual(mirror_camera.target.y,2*expected-self.camera.target.y,places=5)
                heights=[call.args[2] for call in lake.uniform.call_args_list if call.args[1]=='waterY']
                self.assertEqual(heights,[expected]*6)
                self.assertTrue(lake.mist_pass.call_args_list[0].kwargs['reflected'])

    def test_legacy_revealed_mesh_is_unshifted_and_old_world_remains_at_zero(self):
        self.lake.sequence=CanalSequence(profile_from_document(default_document()))
        lake=self.capture_world_frame(41.)
        self.assertEqual(lake.water_y,WATER_Y)
        water=next(call.args for call in lake.draw.call_args_list if call.args[0]=='canal_water')
        self.assertEqual(water[1] if len(water)>1 else (0,0,0),(0,0,0))
        self.lake.sequence=CanalSequence(profile())
        lake=self.capture_world_frame(41.,revealed=False)
        self.assertEqual(lake.water_y,0.)
        water=next(call.args for call in lake.draw.call_args_list if call.args[0]=='lake_surface')
        self.assertEqual(water[1] if len(water)>1 else (0,0,0),(0,0,0))

    def test_direct_reflected_post_and_all_fog_layers_share_the_animated_water_height(self):
        lake=self.lake
        lake.sequence=CanalSequence(replace(profile(),volumes=replace(profile().volumes,enabled=True,particle_mix=1.)))
        layers=[FogRecorder() for _ in range(4)]
        lake.puzzle_fog,lake.volume_fog,lake.surface_fog,lake.surface_veil=layers
        for elapsed in (25.,35.,41.,47.,41.):
            lake.sequence.seek(elapsed)
            height=render_water_height(lake.sequence.direction,elapsed)
            direct=capture_mist_pass(lake,self.camera,self.actor,87.+elapsed)
            reflected=capture_mist_pass(lake,self.camera,self.actor,87.+elapsed,reflected=True)
            self.assertAlmostEqual(direct.uniforms['waterY'],height,places=6)
            self.assertAlmostEqual(reflected.uniforms['waterY'],height,places=6)
            for layer in layers:self.assertEqual(layer.calls[-2:],[(height,False),(height,True)])


if __name__=='__main__':unittest.main()
