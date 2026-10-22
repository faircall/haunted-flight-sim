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
    FOG_ARRIVAL_DURATION,WORLD_BLEND_START,WORLD_BLEND_END,
    FOG_CLEAR_START,FOG_CLEAR_DURATION,SEQUENCE_DURATION)
from huxin_canals_viewer import Lake,WIDTH,HEIGHT
from temple_interior_viewer import camera


class FakePuzzleFog:
    """CPU stand-in for the GPU target; actual Lake.mist_pass is still executed."""
    def __init__(self):
        self.texture=object();self.calls=[]

    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False):
        self.calls.append(dict(source=source,camera=cam,sequence=sequence,clock=clock,
                               colour=colour,water_y=water_y,reflected=reflected))
        return self.texture


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
        self.lake.puzzle_fog=FakePuzzleFog()
        self.player=SimpleNamespace(x=1.65,height=.325,z=1.65)
        self.camera=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)

    def test_activation_preserves_the_incoming_fog_exactly(self):
        q=self.lake.sequence;q.tick(0.,self.player)
        before=capture_mist_pass(self.lake,self.camera,self.player,87.25)
        self.assertTrue(q.activate(self.player))
        after=capture_mist_pass(self.lake,self.camera,self.player,87.25)
        self.assertEqual(before.uniforms,after.uniforms)
        self.assertNotIn('crest',after.uniforms)
        self.assertEqual(after.uniforms['clearing'],0.)
        self.assertEqual(before.textures[1:],after.textures[1:])

    def test_direct_and_reflected_views_receive_the_same_world_cloud(self):
        q=self.lake.sequence
        # The growing waves, concealed handoff and individual fade share one field.
        # Reflection flips its ray only inside the shader.
        states=(('ordinary',False,0.,.5),('entering',False,ENTRY_SWAP/2,1.),
                ('entering',False,ENTRY_DURATION-.001,1.),('canals',True,ENTRY_DURATION,1.),
                ('canals',True,FOG_CLEAR_START+FOG_CLEAR_DURATION/2,1.),
                ('canals',True,SEQUENCE_DURATION,1.))
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
                    self.assertAlmostEqual(a['arrival'],q.fog_source_arrival,places=6)
                    self.assertAlmostEqual(a['clearing'],q.fog_clear,places=6)
                    self.assertAlmostEqual(a['voidWorld'],q.void_tone,places=6)
                    self.assertAlmostEqual(a['sourceArrival'],q.fog_source_arrival,places=6)
                    self.assertNotIn('crest',a)
                    self.assertNotIn('canalWorld',a)
                    self.assertNotIn('fogGridActive',a)
                    self.assertNotIn('retreatRadius',a)
                    self.assertNotIn('concealRadius',a)

    def test_each_pass_uses_its_own_scene_depth_and_destination(self):
        direct=capture_mist_pass(self.lake,self.camera,self.player,40.)
        reflected=capture_mist_pass(self.lake,self.camera,self.player,40.,reflected=True)
        for result in (direct,reflected):
            self.assertEqual(result.textures,[('depthMap',result.source.depth),('particleMap',self.lake.puzzle_fog.texture)])
            self.assertNotIn('coverageBounds',result.uniforms)
            self.assertEqual(result.destinations,[result.target])
            self.assertEqual(len(result.draws),1)
            texture,source_rect,destination_rect,origin,angle,tint=result.draws[0]
            self.assertIs(texture,result.source.texture)
            self.assertEqual((source_rect.width,source_rect.height),(WIDTH,-HEIGHT))
            self.assertEqual((destination_rect.width,destination_rect.height),(WIDTH,HEIGHT))
        self.assertIsNot(direct.source.depth,reflected.source.depth)
        self.assertIsNot(direct.target,reflected.target)
        a,b=self.lake.puzzle_fog.calls[-2:]
        self.assertIs(a['source'],direct.source)
        self.assertIs(b['source'],reflected.source)
        self.assertIs(a['camera'],self.camera);self.assertIs(b['camera'],self.camera)
        self.assertFalse(a['reflected']);self.assertTrue(b['reflected'])
        self.assertIs(a['sequence'],self.lake.sequence)

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

    def test_endpoint_water_and_particle_pass_follow_render_override_without_changing_logic(self):
        q=self.lake.sequence;q.state='entering';q.elapsed=ENTRY_DURATION-.001;q.revealed=False
        logical=(q.state,q.elapsed,q.revealed,q.world_blend)
        for endpoint,height in ((False,0.),(True,-1.55)):
            self.lake._world_override=endpoint
            direct=capture_mist_pass(self.lake,self.camera,self.player,87.)
            reflected=capture_mist_pass(self.lake,self.camera,self.player,87.,reflected=True)
            for result in (direct,reflected):
                self.assertAlmostEqual(result.uniforms['waterY'],height,places=6)
                self.assertIn(('particleMap',self.lake.puzzle_fog.texture),result.textures)
                self.assertNotIn('coverageBounds',result.uniforms)
            a,b=dict(direct.uniforms),dict(reflected.uniforms)
            a.pop('reflectedView');b.pop('reflectedView');self.assertEqual(a,b)
            self.assertEqual((q.state,q.elapsed,q.revealed,q.world_blend),logical)
            a,b=self.lake.puzzle_fog.calls[-2:]
            self.assertEqual((a['water_y'],b['water_y']),(height,height))
            self.assertEqual((a['clock'],b['clock']),(87.,87.))


class CanalTimedFogRenderingTests(unittest.TestCase):
    def test_timer_clears_every_view_identically_even_without_movement(self):
        lake=Lake.__new__(Lake);lake.sequence=CanalSequence();lake.post=SimpleNamespace(id=412)
        lake.puzzle_fog=FakePuzzleFog()
        q=lake.sequence;q.state='canals';q.revealed=True
        cam=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)
        players=(SimpleNamespace(x=1.65,height=.325,z=1.65),
                 SimpleNamespace(x=-14.,height=.325,z=32.),
                 SimpleNamespace(x=8.,height=-1.4,z=48.))
        values=[]
        for elapsed in (ENTRY_DURATION,FOG_CLEAR_START,
                        FOG_CLEAR_START+FOG_CLEAR_DURATION/4,
                        FOG_CLEAR_START+FOG_CLEAR_DURATION/2,SEQUENCE_DURATION):
            q.elapsed=elapsed;values.append(q.fog_clear)
            captures=[capture_mist_pass(lake,cam,p,elapsed).uniforms for p in players]
            for u in captures:
                self.assertAlmostEqual(u['clearing'],q.fog_clear,places=6)
                self.assertAlmostEqual(u['arrival'],q.fog_source_arrival,places=6)
                self.assertNotIn('crest',u)
            # Actor location is uploaded for the unchanged ordinary approach,
            # but cannot alter the post-trigger timed clearing uniform.
            for u in captures:u.pop('playerCenter')
            self.assertEqual(captures[0],captures[1]);self.assertEqual(captures[1],captures[2])
        self.assertEqual(values[:2],[0.,0.]);self.assertEqual(values[-1],1.)
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertGreater(values[-2],.5);self.assertLess(values[-2],1.)

    def test_reset_has_no_persistent_texture_or_discovery_state(self):
        lake=Lake.__new__(Lake);lake.sequence=CanalSequence();lake.post=SimpleNamespace(id=412)
        lake.puzzle_fog=FakePuzzleFog()
        player=SimpleNamespace(x=1.65,height=.325,z=1.65)
        cam=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)
        lake.sequence.tick(0.,player)
        initial=capture_mist_pass(lake,cam,player,0.)
        lake.sequence.state='canals';lake.sequence.elapsed=SEQUENCE_DURATION;lake.sequence.revealed=True
        complete=capture_mist_pass(lake,cam,player,0.)
        self.assertEqual(complete.uniforms['clearing'],1.)
        lake.sequence=CanalSequence();lake.sequence.tick(0.,player)
        reset=capture_mist_pass(lake,cam,player,0.)
        self.assertEqual(initial.uniforms,reset.uniforms)
        self.assertEqual([name for name,_ in reset.textures],['depthMap','particleMap'])

    def test_renderer_blends_hidden_endpoints_then_unlocks_with_the_same_camera(self):
        lake=Lake.__new__(Lake);lake.sequence=CanalSequence()
        q=lake.sequence;q.state='entering';q.elapsed=(WORLD_BLEND_START+WORLD_BLEND_END)/2
        self.assertFalse(q.revealed);self.assertEqual(q.world_blend,.5)
        cam=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)
        lake.last_camera=cam;lake.last_shot=5
        lake.player=SimpleNamespace(clips=('idle',),pose=lambda *args:None)
        lake.player_pose_dt=lambda:0.
        lake.blend_old_frame=SimpleNamespace(texture=object())
        lake.blend_new_frame=SimpleNamespace(texture=object())
        lake.frame=object();lake.blend_shader=SimpleNamespace(id=514)
        player=SimpleNamespace(x=1.65,height=.325,z=1.65,yaw=0.,clip='idle')
        endpoints=[]
        lake._render_world=lambda *args:endpoints.append((args[6],args[7],args[8]))
        with ExitStack() as stack:
            for name in ('begin_texture_mode','clear_background','begin_shader_mode',
                         'set_shader_value','set_shader_value_texture','draw_texture_pro',
                         'end_shader_mode','end_texture_mode'):
                stack.enter_context(patch.object(pr,name))
            stack.enter_context(patch.object(pr,'get_shader_location',return_value=0))
            result=lake.render(player,81.)
            blended_endpoints=[(False,lake.blend_old_frame,False),(True,lake.blend_new_frame,True)]
            self.assertEqual(endpoints,blended_endpoints)
            self.assertEqual(lake.last_world_weights,{'lake':.5,'canals':.5})
            self.assertTrue(q.movement_locked)
            q.tick(ENTRY_DURATION-q.elapsed,player)
            self.assertTrue(q.revealed);self.assertFalse(q.movement_locked)
            result_after=lake.render(player,81.5)
        self.assertIs(result,cam)
        self.assertIs(result_after,cam)
        self.assertEqual(endpoints,blended_endpoints+[(True,lake.frame,True)])
        self.assertEqual(lake.last_world_weights,{'lake':0.,'canals':1.})
        self.assertEqual(q.state,'canals')


class ParticleCardIntegrationTests(unittest.TestCase):
    def render_cards(self,sequence,water_y=0.,reflected=False,clock=87.,view=None):
        from huxin_canals_particles import PuzzleFog
        fog=PuzzleFog.__new__(PuzzleFog)
        fog.width,fog.height=WIDTH,HEIGHT
        fog.texture=SimpleNamespace(width=256,height=128,id=19)
        fog.target=SimpleNamespace(texture=object());fog.shader=object()
        fog.locations={'depthMap':7};fog.last_count=91;fog.last_signature=('stale',)
        uniforms={};draws=[];bindings=[];events=[];clears=[]
        fog.uniform=lambda name,value:uniforms.__setitem__(name,value)
        cam=view or camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78)
        source=SimpleNamespace(depth=object())
        class RenderState:
            def __getattr__(self,name):
                if name=='rlGetCullDistanceNear':return lambda:.01
                if name=='rlGetCullDistanceFar':return lambda:1000.
                return lambda *args:events.append(name)
        def billboard(*args):
            # Renderer reuses its native structs between cards. Capture their
            # values at submission time, as the actual native draw does.
            captured=list(args)
            for index,fields in ((3,('x','y','z')),(4,('x','y','z')),
                                 (5,('x','y')),(6,('x','y')),(8,('r','g','b','a'))):
                captured[index]=SimpleNamespace(**{name:getattr(args[index],name) for name in fields})
            events.append('card');draws.append(tuple(captured))
        with ExitStack() as stack:
            stack.enter_context(patch.object(pr,'rl',RenderState()))
            stack.enter_context(patch.object(pr,'draw_billboard_pro',side_effect=billboard))
            stack.enter_context(patch.object(pr,'set_shader_value_texture',side_effect=lambda *args:bindings.append(args)))
            stack.enter_context(patch.object(pr,'clear_background',side_effect=clears.append))
            for name in ('begin_texture_mode','end_texture_mode','begin_mode_3d','end_mode_3d',
                         'begin_shader_mode','end_shader_mode','rl_set_blend_factors_separate',
                         'begin_blend_mode','end_blend_mode'):
                stack.enter_context(patch.object(pr,name))
            result=fog.render(source,cam,sequence,clock,(.175,.235,.248),water_y,reflected)
        self.assertIs(result,fog.target.texture)
        return SimpleNamespace(fog=fog,draws=draws,uniforms=uniforms,source=source,
                               bindings=bindings,events=events,clears=clears,camera=cam)

    def test_actual_cards_mirror_about_the_endpoint_water_and_use_its_depth(self):
        from g_huxin_canals_particles import particles_at
        q=CanalSequence();q.state='entering';q.elapsed=FOG_ARRIVAL_DURATION
        clouds=particles_at(q.elapsed,87.)
        self.assertGreater(len(clouds),0)
        for water_y in (0.,-1.55):
            direct=self.render_cards(q,water_y)
            reflected=self.render_cards(q,water_y,True)
            self.assertEqual(direct.fog.last_signature,reflected.fog.last_signature)
            self.assertEqual(direct.fog.last_count,len(clouds))
            for result,mirror in ((direct,False),(reflected,True)):
                self.assertEqual(result.bindings,[(result.fog.shader,7,result.source.depth)])
                self.assertEqual(result.uniforms['reflectionPass'],float(mirror))
                self.assertEqual(result.uniforms['waterY'],water_y)
                self.assertEqual(result.uniforms['nearFade'],direct.uniforms['nearFade'])
                forward=pr.vector3_normalize(pr.vector3_subtract(result.camera.target,result.camera.position))
                def point(p):
                    x,y,z=p.center;return (x,2*water_y-y if mirror else y,z)
                depths=[]
                self.assertGreater(len(result.draws),0)
                for args in result.draws:
                    position=args[3];up=args[4]
                    actual_point=(position.x,position.y,position.z)
                    particle=min(clouds,key=lambda p:math.dist(actual_point,point(p)))
                    for actual,wanted in zip((position.x,position.y,position.z),point(particle)):
                        self.assertAlmostEqual(actual,wanted,places=4)
                    depths.append(sum(a*b for a,b in zip(actual_point,(forward.x,forward.y,forward.z))))
                    self.assertEqual(up.y,-1 if mirror else 1)
                    self.assertAlmostEqual(args[6].x,particle.width*.5,places=4)
                    self.assertAlmostEqual(args[6].y,particle.height*.5,places=4)
                    self.assertAlmostEqual(args[5].x,particle.width,places=4)
                    self.assertAlmostEqual(args[5].y,particle.height,places=4)
                    code=math.floor(particle.alpha*65535+.5)
                    self.assertEqual(args[-1].r,code&255)
                    self.assertEqual(args[-1].a,code>>8)
                    decoded=(args[-1].a*256+args[-1].r)/65535
                    self.assertLessEqual(abs(decoded-particle.alpha),.500001/65535)
                self.assertTrue(all(a>=b-.0001 for a,b in zip(depths,depths[1:])))
                self.assertLess(result.events.index('rlDisableDepthMask'),result.events.index('card'))
                self.assertGreater(result.events.index('rlEnableDepthMask'),len(result.events)-1-result.events[::-1].index('card'))

    def test_ordinary_zero_time_and_finished_encounters_clear_stale_layers(self):
        q=CanalSequence()
        for phase_name,elapsed in (('ordinary',0.),('entering',0.),('canals',SEQUENCE_DURATION)):
            q.state=phase_name;q.elapsed=elapsed
            result=self.render_cards(q)
            self.assertEqual(result.draws,[])
            self.assertEqual(result.fog.last_count,0)
            self.assertEqual(result.fog.last_signature,())
            self.assertEqual(len(result.clears),1)
            self.assertEqual(tuple(result.clears[0])[-1],0)

    def test_each_submitted_card_fades_in_its_own_alpha(self):
        q=CanalSequence();q.state='canals';q.elapsed=FOG_CLEAR_START+1.
        early=self.render_cards(q);early_clear=q.fog_clear
        q.elapsed=FOG_CLEAR_START+5.;late=self.render_cards(q)
        self.assertGreater(q.fog_clear,early_clear)
        a={p[0]:p for p in early.fog.last_signature}
        b={p[0]:p for p in late.fog.last_signature}
        common=a.keys()&b.keys();self.assertGreater(len(common),0)
        self.assertTrue(all(a[i][1]==b[i][1] for i in common))
        self.assertTrue(all(a[i][2]>=b[i][2] for i in common))
        self.assertTrue(any(a[i][2]>b[i][2]+.001 for i in common))
        submitted=lambda result:sum((d[-1].a*256+d[-1].r)/65535 for d in result.draws)
        self.assertGreater(submitted(early),submitted(late))

    def test_ambient_clearing_cannot_despawn_live_cards(self):
        # The ordinary mist progress is not the particle lifecycle.
        q=SimpleNamespace(state='canals',elapsed=FOG_ARRIVAL_DURATION,fog_clear=1.)
        result=self.render_cards(q)
        self.assertGreater(result.fog.last_count,0)
        self.assertGreater(len(result.draws),0)

    def test_outside_camera_softening_is_shared_with_its_reflection(self):
        q=CanalSequence();q.state='canals';q.elapsed=FOG_CLEAR_START+1.
        inner=self.render_cards(q)
        view=camera((4.8,3.4,10.5),(0.,1.,7.),70)
        outer=self.render_cards(q,view=view)
        reflected=self.render_cards(q,reflected=True,view=view)
        self.assertEqual(inner.uniforms['nearFade'],(.18,1.25))
        self.assertAlmostEqual(outer.uniforms['nearFade'][0],.78)
        self.assertAlmostEqual(outer.uniforms['nearFade'][1],10.)
        self.assertEqual(reflected.uniforms['nearFade'],outer.uniforms['nearFade'])
        self.assertEqual(outer.fog.last_signature,inner.fog.last_signature)
        self.assertEqual(outer.fog.last_signature,reflected.fog.last_signature)


if __name__=='__main__':unittest.main()
