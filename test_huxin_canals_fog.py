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
from g_huxin_canals_sequence import CanalSequence,ENTRY_SWAP,ENTRY_CLEAR,ENTRY_DURATION,ENTRY_BLEND_START,ENTRY_BLEND_END
from huxin_canals_fog import COVERAGE_BOUNDS
from huxin_canals_viewer import Lake,WIDTH,HEIGHT
from temple_interior_viewer import camera


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
        self.player=SimpleNamespace(x=1.65,height=.325,z=1.65)
        self.camera=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)

    def test_direct_and_reflected_views_receive_the_same_world_cloud(self):
        q=self.lake.sequence
        # The ordinary build-up, crescendo, swap, retreat and completed scene
        # all share one field. Reflection flips its ray only inside the shader.
        states=(('ordinary',False,0.,.5),('entering',False,4.,1.),
                ('entering',True,ENTRY_SWAP,1.),('entering',True,ENTRY_CLEAR,1.),
                ('entering',True,24.,1.),('entering',True,ENTRY_DURATION-.001,1.),
                ('canals',True,0.,1.))
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
                    self.assertAlmostEqual(a['clearing'],q.fog_clear,places=6)
                    self.assertAlmostEqual(a['retreatRadius'],q.fog_retreat_radius,places=4)
                    self.assertAlmostEqual(a['voidWorld'],q.void_tone,places=6)

    def test_each_pass_uses_its_own_scene_depth_and_destination(self):
        direct=capture_mist_pass(self.lake,self.camera,self.player,40.)
        reflected=capture_mist_pass(self.lake,self.camera,self.player,40.,reflected=True)
        for result in (direct,reflected):
            self.assertEqual(result.textures,[('depthMap',result.source.depth),('buildingCoverage',self.lake.building_coverage)])
            self.assertEqual(result.uniforms['coverageBounds'],COVERAGE_BOUNDS)
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
        q=self.lake.sequence;q.state='entering';q.elapsed=ENTRY_SWAP;q.revealed=True
        logical=(q.state,q.elapsed,q.revealed,q.world_blend)
        for endpoint,height in ((False,0.),(True,-1.55)):
            self.lake._world_override=endpoint
            direct=capture_mist_pass(self.lake,self.camera,self.player,87.)
            reflected=capture_mist_pass(self.lake,self.camera,self.player,87.,reflected=True)
            for result in (direct,reflected):
                self.assertAlmostEqual(result.uniforms['waterY'],height,places=6)
                self.assertIn(('buildingCoverage',self.lake.building_coverage),result.textures)
                self.assertEqual(result.uniforms['coverageBounds'],COVERAGE_BOUNDS)
            a,b=dict(direct.uniforms),dict(reflected.uniforms)
            a.pop('reflectedView');b.pop('reflectedView');self.assertEqual(a,b)
            self.assertEqual((q.state,q.elapsed,q.revealed,q.world_blend),logical)


class CanalWorldBlendTests(unittest.TestCase):
    def test_blend_spans_logical_commit_and_is_continuous_at_both_ends(self):
        q=CanalSequence();q.state='entering'
        self.assertLess(ENTRY_BLEND_START,ENTRY_SWAP);self.assertGreater(ENTRY_BLEND_END,ENTRY_SWAP)
        values=[]
        for i in range(int(ENTRY_DURATION*60)+1):
            q.elapsed=i/60;values.append(q.world_blend)
        self.assertEqual(values[0],0.);self.assertEqual(values[-1],1.)
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertLess(max(b-a for a,b in zip(values,values[1:])),.01)
        for boundary,expected in ((ENTRY_BLEND_START,0.),(ENTRY_BLEND_END,1.)):
            for offset in (-.001,0.,.001):
                q.elapsed=boundary+offset;self.assertAlmostEqual(q.world_blend,expected,places=8)

    def test_logical_commit_cannot_jump_visual_weight(self):
        q=CanalSequence();q.state='entering';q.elapsed=ENTRY_SWAP
        q.revealed=False;before=q.world_blend
        q.revealed=True;self.assertEqual(q.world_blend,before)
        self.assertGreater(before,0.);self.assertLess(before,1.)
        q.state='ordinary';q.revealed=False;self.assertEqual(q.world_blend,0.)
        q.state='canals';q.revealed=True;self.assertEqual(q.world_blend,1.)


if __name__=='__main__':unittest.main()
