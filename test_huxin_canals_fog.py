"""CPU contracts for the real direct/reflected fog-pass integration.

These checks capture uniform uploads and render-target routing without opening
a window. They deliberately do not reproduce the GLSL density implementation;
native image checks remain responsible for the cloud's shape and concealment.
"""
import math
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

os.environ['HAUNTED_MUTE_AUDIO']='1'
import pyray as pr
from g_huxin_canals_sequence import (CanalSequence,ENTRY_SWAP,ENTRY_DURATION,
    FOG_ARRIVAL_DURATION,REVEAL_START_RADIUS,REVEAL_END_RADIUS)
from huxin_canals_fog import COVERAGE_BOUNDS
from huxin_canals_viewer import Lake,WIDTH,HEIGHT
from temple_interior_viewer import camera


class FogGridDouble:
    """Tiny observable CPU field for the renderer's upload ownership contract."""
    bounds=(-96.,-96.,96.,96.)
    def __init__(self,size=192,value=0):
        self.size=size;self.revision=0;self.value=value;self.pixel_calls=0
    def pixels(self):
        self.pixel_calls+=1
        return bytes((self.value,83,171,255))*(self.size*self.size)
    @property
    def clear_fraction(self):return self.value/255.


def capture_mist_pass(lake,cam,player,clock,inspection=False,reflected=False):
    """Run production setup; replace only GPU uploads/drawing with recorders."""
    source=SimpleNamespace(texture=object(),depth=object())
    target=object();uniforms={};textures=[];destinations=[];draws=[];locations={}
    sizes={pr.SHADER_UNIFORM_FLOAT:1,pr.SHADER_UNIFORM_VEC2:2,pr.SHADER_UNIFORM_VEC3:3,pr.SHADER_UNIFORM_VEC4:4}

    def locate(shader,name):
        if name not in locations:locations[name]=len(locations)
        return locations[name]

    def uniform_name(location):return next(name for name,value in locations.items() if value==location)

    def upload(shader,location,value,kind):
        values=tuple(float(value[i]) for i in range(sizes[kind]))
        uniforms[uniform_name(location)]=values[0] if len(values)==1 else values

    original=pr.rl
    class CpuDistances:
        def __getattr__(self,name):
            if name=='rlGetCullDistanceNear':return lambda:.01
            if name=='rlGetCullDistanceFar':return lambda:1000.
            return getattr(original,name)

    with ExitStack() as stack:
        stack.enter_context(patch.object(pr,'rl',CpuDistances()))
        stack.enter_context(patch.object(pr,'get_shader_location',side_effect=locate))
        stack.enter_context(patch.object(pr,'set_shader_value',side_effect=upload))
        stack.enter_context(patch.object(pr,'set_shader_value_texture',side_effect=lambda shader,location,texture:textures.append((uniform_name(location),texture))))
        stack.enter_context(patch.object(pr,'begin_texture_mode',side_effect=destinations.append))
        stack.enter_context(patch.object(pr,'draw_texture_pro',side_effect=lambda *args:draws.append(args)))
        for name in ('clear_background','begin_shader_mode','end_shader_mode','end_texture_mode'):
            stack.enter_context(patch.object(pr,name))
        lake.mist_pass(source,target,cam,player,clock,inspection,reflected)
    return SimpleNamespace(uniforms=uniforms,source=source,target=target,
                           textures=textures,destinations=destinations,draws=draws)


class CanalFogPassTests(unittest.TestCase):
    def setUp(self):
        self.lake=Lake.__new__(Lake)
        self.lake.sequence=CanalSequence()
        self.lake.post=SimpleNamespace(id=412)
        self.lake.building_coverage=object();self.lake.coverage_bounds=COVERAGE_BOUNDS
        self.lake.sequence.fog_grid=FogGridDouble()
        self.lake.fog_grid_texture=SimpleNamespace(id=801,width=192,height=192)
        self.lake.fog_grid_bounds=self.lake.sequence.fog_grid.bounds
        self.lake._fog_grid_source=self.lake.sequence.fog_grid;self.lake._fog_grid_revision=0
        self.player=SimpleNamespace(x=1.65,height=.325,z=1.65)
        self.camera=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)

    def test_activation_enables_zero_clear_grid_without_changing_incoming_fog(self):
        q=self.lake.sequence;q.tick(0.,self.player)
        before=capture_mist_pass(self.lake,self.camera,self.player,87.25)
        self.assertTrue(q.activate(self.player))
        after=capture_mist_pass(self.lake,self.camera,self.player,87.25)
        a,b=dict(before.uniforms),dict(after.uniforms)
        self.assertEqual(a.pop('fogGridActive'),0.)
        self.assertEqual(b.pop('fogGridActive'),1.)
        self.assertEqual(a,b)
        self.assertEqual(b['crest'],0.)
        self.assertEqual(q.fog_grid.value,0)
        self.assertEqual(before.textures[1:],after.textures[1:])

    def test_direct_and_reflected_views_receive_the_same_world_cloud(self):
        q=self.lake.sequence
        # The ordinary build-up, crescendo, swap, retreat and completed scene
        # all share one field. Reflection flips its ray only inside the shader.
        states=(('ordinary',False,0.,.5),('entering',False,ENTRY_SWAP/2,1.),
                ('entering',False,ENTRY_DURATION-.001,1.),('canals',True,ENTRY_DURATION,1.),
                ('canals',True,(ENTRY_DURATION+FOG_ARRIVAL_DURATION)/2,1.),
                ('canals',True,FOG_ARRIVAL_DURATION,1.))
        for state,revealed,elapsed,approach in states:
            q.state,q.revealed,q.elapsed,q.approach=state,revealed,elapsed,approach
            for inspection in (False,True):
                with self.subTest(state=state,elapsed=elapsed,inspection=inspection):
                    direct=capture_mist_pass(self.lake,self.camera,self.player,87.25,inspection)
                    reflected=capture_mist_pass(self.lake,self.camera,self.player,87.25,inspection,True)
                    a,b=dict(direct.uniforms),dict(reflected.uniforms)
                    self.assertEqual(a.pop('reflectedView'),0.)
                    self.assertEqual(b.pop('reflectedView'),1.)
                    self.assertEqual(a,b)
                    self.assertAlmostEqual(a['time'],87.25)
                    self.assertAlmostEqual(a['waterY'],-1.55 if revealed else 0.,places=6)
                    self.assertAlmostEqual(a['veil'],q.veil,places=6)
                    self.assertAlmostEqual(a['arrival'],q.fog_arrival,places=6)
                    self.assertEqual(a['fogGridActive'],float(state in ('entering','canals')))
                    self.assertEqual(a['fogGridBounds'],q.fog_grid.bounds)
                    self.assertAlmostEqual(a['voidWorld'],q.void_tone,places=6)
                    self.assertAlmostEqual(a['sourceArrival'],q.fog_source_arrival,places=6)
                    self.assertAlmostEqual(a['crest'],q.fog_depth,places=6)
                    self.assertEqual(a['canalWorld'],float(revealed))
                    self.assertNotIn('clearing',a)
                    self.assertNotIn('retreatRadius',a)
                    self.assertNotIn('concealRadius',a)

    def test_each_pass_uses_its_own_scene_depth_and_destination(self):
        direct=capture_mist_pass(self.lake,self.camera,self.player,40.)
        reflected=capture_mist_pass(self.lake,self.camera,self.player,40.,reflected=True)
        for result in (direct,reflected):
            self.assertEqual(result.textures,[('depthMap',result.source.depth),('buildingCoverage',self.lake.building_coverage),('fogGrid',self.lake.fog_grid_texture)])
            self.assertEqual(result.uniforms['coverageBounds'],COVERAGE_BOUNDS)
            self.assertEqual(result.uniforms['fogGridBounds'],self.lake.sequence.fog_grid.bounds)
            for texel in result.uniforms['fogGridTexel']:self.assertAlmostEqual(texel,1./192.,places=8)
            self.assertEqual(result.destinations,[result.target])
            self.assertEqual(len(result.draws),1)
            texture,source_rect,destination_rect,origin,angle,tint=result.draws[0]
            self.assertIs(texture,result.source.texture)
            self.assertEqual((source_rect.width,source_rect.height),(WIDTH,-HEIGHT))
            self.assertEqual((destination_rect.width,destination_rect.height),(WIDTH,HEIGHT))
        self.assertIsNot(direct.source.depth,reflected.source.depth)
        self.assertIsNot(direct.target,reflected.target)

    def test_camera_and_player_coordinates_are_not_mirrored_before_the_shader(self):
        q=self.lake.sequence;q.state='canals';q.revealed=True
        player=SimpleNamespace(x=23.,height=-1.25,z=40.)
        cam=camera((30.,3.,47.),(23.,.3,40.),61)
        result=capture_mist_pass(self.lake,cam,player,129.5,reflected=True)
        u=result.uniforms
        self.assertEqual(u['eye'],(30.,3.,47.))
        self.assertAlmostEqual(u['playerCenter'][0],23.)
        self.assertAlmostEqual(u['playerCenter'][1],-.20,places=6)
        self.assertAlmostEqual(u['playerCenter'][2],40.)
        self.assertAlmostEqual(u['waterY'],-1.55,places=6)
        for direction in ('forward','right','up'):
            self.assertAlmostEqual(math.sqrt(sum(v*v for v in u[direction])),1.,places=6)
        self.assertAlmostEqual(sum(a*b for a,b in zip(u['forward'],u['right'])),0.,places=6)
        self.assertAlmostEqual(sum(a*b for a,b in zip(u['forward'],u['up'])),0.,places=6)
        self.assertAlmostEqual(u['lens'][0],math.tan(math.radians(61)/2),places=6)
        self.assertAlmostEqual(u['lens'][1],WIDTH/HEIGHT,places=6)
        self.assertAlmostEqual(u['clip'][0],.01,places=6)
        self.assertEqual(u['clip'][1],1000.)

    def test_endpoint_water_and_coverage_follow_render_override_without_changing_logic(self):
        q=self.lake.sequence;q.state='canals';q.elapsed=ENTRY_SWAP;q.revealed=True
        q.exploration.update((REVEAL_START_RADIUS+REVEAL_END_RADIUS)/2,.325,0.)
        logical=(q.state,q.elapsed,q.revealed,q.world_blend)
        for endpoint,height in ((False,0.),(True,-1.55)):
            self.lake._world_override=endpoint
            direct=capture_mist_pass(self.lake,self.camera,self.player,87.)
            reflected=capture_mist_pass(self.lake,self.camera,self.player,87.,reflected=True)
            for result in (direct,reflected):
                self.assertAlmostEqual(result.uniforms['waterY'],height,places=6)
                self.assertEqual(result.uniforms['canalWorld'],float(endpoint))
                self.assertIn(('buildingCoverage',self.lake.building_coverage),result.textures)
                self.assertIn(('fogGrid',self.lake.fog_grid_texture),result.textures)
                self.assertEqual(result.uniforms['coverageBounds'],COVERAGE_BOUNDS)
                self.assertEqual(result.uniforms['fogGridBounds'],q.fog_grid.bounds)
            a,b=dict(direct.uniforms),dict(reflected.uniforms)
            a.pop('reflectedView');b.pop('reflectedView');self.assertEqual(a,b)
            self.assertEqual((q.state,q.elapsed,q.revealed,q.world_blend),logical)


class CanalFogGridUploadTests(unittest.TestCase):
    def setUp(self):
        self.lake=Lake.__new__(Lake)
        self.grid=FogGridDouble()
        self.lake.sequence=SimpleNamespace(fog_grid=self.grid)
        self.lake.fog_grid_texture=None;self.lake._fog_grid_source=None;self.lake._fog_grid_revision=-1

    def test_initial_upload_updates_only_on_revision_and_reuses_same_texture(self):
        uploads=[];updates=[]
        def load(image):
            uploads.append(bytes(pr.ffi.buffer(image.data,image.width*image.height*4)))
            return SimpleNamespace(id=801,width=image.width,height=image.height)
        def update(texture,memory):
            updates.append((texture,bytes(pr.ffi.buffer(memory,texture.width*texture.height*4))))
        # MemAlloc/Image/UnloadImage stay real CPU operations; all GPU calls
        # are mocked. This also checks we release native-owned image storage.
        with patch.object(pr,'load_texture_from_image',side_effect=load), \
             patch.object(pr,'unload_image',wraps=pr.unload_image) as release, \
             patch.object(pr,'set_texture_filter') as filtering, \
             patch.object(pr,'set_texture_wrap') as wrapping, \
             patch.object(pr,'update_texture',side_effect=update):
            texture=self.lake._sync_fog_grid()
            for _ in range(4):self.assertIs(self.lake._sync_fog_grid(),texture)
            self.assertEqual(self.grid.pixel_calls,1)
            self.assertEqual(len(uploads),1);self.assertEqual(updates,[])
            release.assert_called_once()
            filtering.assert_called_once_with(texture,pr.TEXTURE_FILTER_BILINEAR)
            wrapping.assert_called_once_with(texture,pr.TEXTURE_WRAP_CLAMP)
            self.grid.value=255;self.grid.revision+=1
            for _ in range(4):self.assertIs(self.lake._sync_fog_grid(),texture)
            self.assertEqual(self.grid.pixel_calls,2)
            self.assertEqual(len(updates),1)
            self.assertEqual(updates[0][1],bytes((255,83,171,255))*(192*192))
            self.assertEqual(uploads[0],bytes((0,83,171,255))*(192*192))

    def test_restart_with_equal_revision_refreshes_cached_field(self):
        old_texture=SimpleNamespace(id=801,width=192,height=192)
        self.lake.fog_grid_texture=old_texture
        self.lake._fog_grid_source=self.grid;self.lake._fog_grid_revision=0
        replacement=FogGridDouble(value=19);self.lake.sequence.fog_grid=replacement
        with patch.object(pr,'update_texture') as update:
            self.assertIs(self.lake._sync_fog_grid(),old_texture)
            self.assertIs(self.lake._sync_fog_grid(),old_texture)
            update.assert_called_once()
        self.assertEqual(replacement.pixel_calls,1)
        self.assertIs(self.lake._fog_grid_source,replacement)

    def test_resize_replaces_and_unloads_the_old_texture_once(self):
        old_texture=SimpleNamespace(id=801,width=192,height=192)
        self.lake.fog_grid_texture=old_texture
        self.lake.sequence.fog_grid=FogGridDouble(size=64)
        new_texture=SimpleNamespace(id=802,width=64,height=64)
        with patch.object(pr,'load_texture_from_image',return_value=new_texture), \
             patch.object(pr,'set_texture_filter'),patch.object(pr,'set_texture_wrap'), \
             patch.object(pr,'unload_texture') as unload:
            self.assertIs(self.lake._sync_fog_grid(),new_texture)
            self.assertIs(self.lake._sync_fog_grid(),new_texture)
            unload.assert_called_once_with(old_texture)

    def test_failed_initial_upload_frees_image_and_does_not_cache_revision(self):
        with patch.object(pr,'load_texture_from_image',return_value=SimpleNamespace(id=0)), \
             patch.object(pr,'unload_image',wraps=pr.unload_image) as release:
            with self.assertRaises(RuntimeError):self.lake._sync_fog_grid()
            release.assert_called_once()
        self.assertIsNone(self.lake.fog_grid_texture)
        self.assertEqual(self.lake._fog_grid_revision,-1)

    def test_close_releases_grid_once_and_clears_cache(self):
        texture=SimpleNamespace(id=801,width=192,height=192)
        self.lake.fog_grid_texture=texture;self.lake._fog_grid_source=self.grid;self.lake._fog_grid_revision=0
        for name in ('blend_old_frame','blend_new_frame','blend_shader','building_coverage','reflection','reflection_raw','water_shader'):
            setattr(self.lake,name,None)
        with patch('huxin_canals_viewer.Hall.close'),patch.object(pr,'unload_texture') as unload:
            self.lake.close();self.lake.close()
            unload.assert_called_once_with(texture)
        self.assertIsNone(self.lake._fog_grid_source)
        self.assertEqual(self.lake._fog_grid_revision,-1)


class CanalWorldBlendTests(unittest.TestCase):
    def test_visual_blend_is_a_continuous_outward_discovery(self):
        q=CanalSequence();q.state='canals';q.revealed=True;q.elapsed=ENTRY_DURATION
        values=[]
        step=.025
        for i in range(math.ceil((REVEAL_END_RADIUS+1.)/step)+1):
            q.exploration.update(i*step,.325,0.);values.append(q.world_blend)
        self.assertEqual(values[0],0.);self.assertEqual(values[-1],1.)
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertLess(max(b-a for a,b in zip(values,values[1:])),2.*step/(REVEAL_END_RADIUS-REVEAL_START_RADIUS))
        for boundary,expected in ((REVEAL_START_RADIUS,0.),(REVEAL_END_RADIUS,1.)):
            for offset in (-.001,0.,.001):
                q=CanalSequence();q.state='canals';q.revealed=True
                q.exploration.update(boundary+offset,.325,0.);self.assertAlmostEqual(q.world_blend,expected,places=8)

    def test_logical_commit_and_waiting_cannot_reveal_or_regrade_the_village(self):
        q=CanalSequence();q.state='entering';q.elapsed=ENTRY_SWAP
        q.revealed=False;self.assertEqual(q.world_blend,0.)
        q.revealed=True;self.assertEqual(q.world_blend,0.)
        q.state='canals'
        for elapsed in (ENTRY_DURATION,FOG_ARRIVAL_DURATION,60.,600.):
            q.elapsed=elapsed;self.assertEqual(q.world_blend,0.);self.assertEqual(q.void_tone,0.)
        q.state='ordinary';q.revealed=False;self.assertEqual(q.world_blend,0.)

    def test_equal_discovery_gives_equal_blend_despite_different_arrival_clocks(self):
        a,b=CanalSequence(),CanalSequence()
        for q in (a,b):q.state='canals';q.revealed=True
        a.elapsed=ENTRY_DURATION;b.elapsed=FOG_ARRIVAL_DURATION
        for radius in (3.,REVEAL_START_RADIUS,6.,8.,REVEAL_END_RADIUS,16.):
            for q in (a,b):q.exploration.update(radius,.325,0.)
            self.assertEqual(a.world_blend,b.world_blend)
            self.assertEqual(a.void_tone,b.void_tone)


if __name__=='__main__':unittest.main()
