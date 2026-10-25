"""The Void Canals: a separate one-way passage into an impossible water town."""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
from pathlib import Path
from types import SimpleNamespace
import math
import json
import time
import argparse
import pyray as pr
from g_huxin_canals import Explorer,SHOTS,LIGHTS,COLUMNS,PATH,DECK,PUZZLE_RADIUS,FUTURE_RING,REVIEW_ROUTE,trees,PLAYER_SCALE,walk_height,SPAWN,camera_zone
from g_temple_living import LivingScene
from temple_interior_viewer import Hall,camera,snapshot
from huxin_canals_sky import MoonSky
from g_huxin_canals_sequence import CanalSequence,UPPER,MIRROR,BASIN,MARK,ease,SEQUENCE_DURATION,WORLD_BLEND_START,FOG_CLEAR_START
from g_huxin_canals_particles import NEAR_CLEAR_END,MIDDLE_CLEAR_START,MIDDLE_CLEAR_END,FAR_CLEAR_START,FAR_CLEAR_END
from huxin_canals_camera import canal_camera,mist_camera,FOCUS_EYE,FOCUS_TARGET
from huxin_canals_audio import EncounterAudio
from g_huxin_canals_layout import CAMERA_SHOTS,WATER_Y,START
from temple_intro_fog import depth_target
from g_huxin_canals_direction import (load_direction,profile_from_document,document_from_profile,
                                    sample_camera,DEFAULT_PATH,DirectionError)
from g_huxin_canals_live import DirectionWatcher,apply_live_direction

ROOT=Path(__file__).parent;KIT=ROOT/'art'/'temple'/'huxin_canals';WIDTH,HEIGHT=640,360

class LiveDirectionReload:
    """Apply saved direction data without rebuilding the running encounter."""
    def __init__(self,path=DEFAULT_PATH,document=None):
        self.path=Path(path)
        if document is None:document=load_direction(self.path)
        self.watcher=DirectionWatcher(self.path,document=document)
        self._message=None;self._message_until=0.

    def poll(self,scene,now=None):
        now=time.monotonic() if now is None else float(now)
        document=self.watcher.poll(now)
        if document is None:return False
        changed=apply_live_direction(scene.sequence,profile_from_document(document))
        if changed:
            self._message='Direction updated from saved file'
            self._message_until=now+5.
        return changed

    def load_for_reset(self):
        """Home uses the latest complete save, or the last good file on error."""
        try:document=load_direction(self.path)
        except DirectionError as error:
            self.watcher.error=str(error)
            document=self.watcher.document
        else:self.watcher.acknowledge(document)
        return profile_from_document(document)

    def acknowledge_scene(self,scene):
        # The editor may have saved this profile. The watcher only accepts it
        # if the bytes still match, so an external save during F2 isn't lost.
        return self.watcher.acknowledge(document_from_profile(scene.sequence.direction))

    def status(self,now=None):
        if self.watcher.error:
            error=str(self.watcher.error).replace(str(self.path),self.path.name)
            return ('Direction reload: '+error,True)
        now=time.monotonic() if now is None else float(now)
        if self._message and now<self._message_until:return (self._message,False)
        return None


def draw_live_direction_status(live,width,height):
    status=live.status()
    if status is None:return
    text,is_error=status
    max_width=max(80,width-36)
    while text and pr.measure_text(text,12)>max_width:
        text=text[:-4]+'...'
    y=max(12,height-76)
    pr.draw_rectangle(12,y-5,min(max_width+12,pr.measure_text(text,12)+12),24,pr.Color(10,20,22,215))
    pr.draw_text(text,18,y,12,pr.Color(235,164,144,255) if is_error else pr.Color(180,210,195,255))


def clear_view(eye,body):
    dx,dz=body[0]-eye[0],body[2]-eye[2];length=dx*dx+dz*dz
    for x,z,r in COLUMNS:
        t=max(0.,min(1.,((x-eye[0])*dx+(z-eye[2])*dz)/max(length,1e-8)))
        y=eye[1]+(body[1]-eye[1])*t
        if .02<t<.98 and DECK<y<DECK+3.85 and math.hypot(x-eye[0]-t*dx,z-eye[2]-t*dz)<r+.075:return False
    return True

def auto_camera(e):
    body=(e.x,e.height+.93,e.z);preferred=e.shot;candidates=[]
    for i,s in enumerate(SHOTS):
        eye=s['eye'];distance=math.dist(eye,body)
        if distance<2.0 or distance>42 or not clear_view(eye,body):continue
        candidates.append((abs(i-preferred)*1.5+abs(distance-8.)*.08,i))
    i=min(candidates)[1] if candidates else preferred;s=SHOTS[i]
    # Fixed positions with a small pan at the margins keep the full player framed.
    eye=pr.Vector3(*s['eye']);target=pr.Vector3(*s['target']);forward=pr.vector3_normalize(pr.vector3_subtract(target,eye))
    right=pr.vector3_normalize(pr.vector3_cross_product(forward,pr.Vector3(0,1,0)));up=pr.vector3_cross_product(right,forward)
    d=pr.vector3_subtract(pr.Vector3(*body),eye);depth=pr.vector3_dot_product(d,forward);tan=math.tan(math.radians(s['fov'])/2)
    visible=depth>1 and abs(pr.vector3_dot_product(d,right))<depth*tan*16/9*.82 and abs(pr.vector3_dot_product(d,up))+.88<depth*tan*.84
    return i,camera(s['eye'],s['target'] if visible else body,s['fov'])

class Lake(Hall):
    def __init__(self):
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None;self.reflection=None;self.reflection_raw=None;self.water_shader=None;self.last_shot=0;self.sequence=CanalSequence();self.last_camera=None
        self.blend_shader=None;self.blend_old_frame=None;self.blend_new_frame=None;self.puzzle_fog=None;self.volume_fog=None;self.surface_fog=None;self.surface_material=None;self.surface_veil=None
        self._world_override=None;self.last_world_weights={'lake':1.,'canals':0.}
        try:
            self.manifest=json.loads((KIT/'manifest.json').read_text())
            self.shader=pr.load_shader(str(ROOT/'shaders'/'huxin_canals.vs'),str(ROOT/'shaders'/'huxin_canals.fs'))
            self.water_shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'huxin_canals_water.fs'))
            for s in (self.shader,self.water_shader):
                if s.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake shader compilation failed')
                s.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(s,'matModel');s.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(s,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='huxin_canals.fs')
            names=('eyePosition','time','inspection','opacity','emission','surfaceKind','reflectionPass','lampCount','lamps','windStrength','deckHeight','veil','enclosed','warmth','flatPaving','voidWorld','worldMaterial','waterY','preservePlatform','shadowAmount','twinPart','joiningStone')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in names} for s in (self.shader,self.player.skin,self.water_shader)}
            for name in self.manifest['models']:self.load(name,KIT/(name+'.glb'))
            for name in ('moon_basin','moon_fixture','moon_mirror'):self.load(name,KIT/(name+'.glb'))
            self.canals_manifest=json.loads((KIT/'canals_manifest.json').read_text())
            for name in self.canals_manifest['models']:self.load(name,KIT/(name+'.glb'))
            # Raylib binds this secondary atlas with each mesh material, so the
            # two independently authored stone sets blend in world coordinates.
            lake_model,canal_model=self.models['causeway'],self.models['canal_ground']
            lake_stone=lake_model.materials[lake_model.meshMaterial[0]].maps[pr.MATERIAL_MAP_DIFFUSE].texture
            canal_stone=canal_model.materials[canal_model.meshMaterial[0]].maps[pr.MATERIAL_MAP_DIFFUSE].texture
            self.shader.locs[pr.SHADER_LOC_MAP_NORMAL]=pr.get_shader_location(self.shader,'otherStone')
            for name in ('causeway','canal_ground','canal_masonry'):
                model=self.models[name]
                for i in range(model.materialCount):model.materials[i].maps[pr.MATERIAL_MAP_NORMAL].texture=canal_stone if name=='causeway' else lake_stone
            for n in ('chinese_pine_a','chinese_pine_b','chinese_pine_c'):self.load(n,ROOT/'art'/'temple'/'intro'/(n+'.glb'))
            self.raw=depth_target(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT);self.reflection=pr.load_render_texture(WIDTH,HEIGHT)
            self.reflection_raw=depth_target(WIDTH,HEIGHT)
            pr.set_texture_filter(self.reflection.texture,pr.TEXTURE_FILTER_BILINEAR)
            for name in ('lake_surface','canal_water'):
                water=self.models[name]
                for i in range(water.materialCount):
                    water.materials[i].shader=self.water_shader;water.materials[i].maps[pr.MATERIAL_MAP_NORMAL].texture=self.reflection.texture
            self.water_shader.locs[pr.SHADER_LOC_MAP_NORMAL]=pr.get_shader_location(self.water_shader,'reflectionTexture')
            pr.set_shader_value(self.water_shader,pr.get_shader_location(self.water_shader,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'huxin_canals_post.fs'))
            if self.post.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake post shader compilation failed')
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.blend_shader=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'huxin_canals_blend.fs'))
            if self.blend_shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake world blend shader compilation failed')
            # Prepare the two short-lived world views at scene load so the
            # concealed handoff never allocates render targets mid-sequence.
            self.blend_old_frame=pr.load_render_texture(WIDTH,HEIGHT)
            self.blend_new_frame=pr.load_render_texture(WIDTH,HEIGHT)
            from huxin_canals_particles import PuzzleFog
            self.puzzle_fog=PuzzleFog(WIDTH,HEIGHT)
            from huxin_canals_volumes import FogVolumes
            self.volume_fog=FogVolumes(WIDTH,HEIGHT)
            from huxin_canals_surface_fog import SurfaceFog
            self.surface_fog=SurfaceFog(WIDTH,HEIGHT)
            from huxin_canals_surface_veil import LakeSurfaceVeil
            self.surface_veil=LakeSurfaceVeil(WIDTH,HEIGHT)
            from huxin_canals_surface_material import SurfaceMaterialReveal
            self.surface_material=SurfaceMaterialReveal(self.shader,self.models)
            self.sky=MoonSky();im=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK);self.smoke=pr.load_texture_from_image(im);pr.unload_image(im)
        except Exception:self.close();raise

    def environment(self,cam,clock,inspection,reflection):
        material=getattr(self,'surface_material',None)
        if material is not None:material.sync(self.surface_fog,self.sequence)
        lights=LIGHTS[:3] if self.render_revealed else LIGHTS
        for s in (self.shader,self.player.skin,self.water_shader):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.),('surfaceKind',0.),('reflectionPass',float(reflection)),('windStrength',0.)):self.uniform(s,name,value)
            self.uniform(s,'deckHeight',DECK);self.uniform(s,'lampCount',len(lights),'int');self.uniform(s,'veil',self.sequence.veil);self.uniform(s,'enclosed',float(self.render_revealed))
            self.uniform(s,'warmth',self.sequence.warmth)
            self.uniform(s,'flatPaving',0.);self.uniform(s,'worldMaterial',0.);self.uniform(s,'voidWorld',self.sequence.void_tone)
            self.uniform(s,'waterY',self.water_y);self.uniform(s,'preservePlatform',float(self.hold_pavilion))
            self.uniform(s,'shadowAmount',0.);self.uniform(s,'twinPart',0.);self.uniform(s,'joiningStone',0.)
            if self.locations[s.id]['lamps']>=0:pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in lights for v in p]),pr.SHADER_UNIFORM_VEC3,len(lights))

    @property
    def render_revealed(self):
        override=getattr(self,'_world_override',None)
        return self.sequence.revealed if override is None else override
    @property
    def water_y(self):return WATER_Y if self.render_revealed else 0.
    @property
    def hold_pavilion(self):return True

    def selection_metadata(self,name):
        # Match the shader's ownership cuts: hidden lips and the old distant
        # causeway are still present in the GLB but must never win a click.
        revealed=self.render_revealed
        if name=='causeway':
            def rejected(point):
                x,_,z=point
                inside=max(x*math.cos((i+.5)*1.04719755)+z*math.sin((i+.5)*1.04719755) for i in range(6))<6.2353829
                return inside or (revealed and z>12.)
            return {'_reject_hit':rejected}
        if name=='lake_lamps' and revealed:return {'_reject_hit':lambda point:point[2]>12.}
        if name=='pavilion_base':return {'_reject_hit':lambda point:point[1]>DECK+.00001}
        return None

    def geometry(self,e,cam,clock,reflection,show_player):
        scale=(1,-1,1) if reflection else 1
        offset=(0,2*self.water_y,0) if reflection else (0,0,0)
        def draw(name):self.draw(name,offset,scale)
        q=self.sequence;revealed=self.render_revealed
        if revealed:
            self.uniform(self.shader,'worldMaterial',1.)
            for name in self.canals_manifest['models']:
                if name not in ('canal_water','canal_annulus'):
                    self.uniform(self.shader,'shadowAmount',1. if name=='canal_interiors' else .78 if name=='canal_shadow' else .50 if name=='canal_recess' else 0.)
                    self.uniform(self.shader,'joiningStone',1. if name in ('canal_ground','canal_masonry') else 0.)
                    draw(name)
            self.uniform(self.shader,'shadowAmount',0.)
            self.uniform(self.shader,'joiningStone',0.)
            self.uniform(self.shader,'worldMaterial',0.)
        if not revealed or self.hold_pavilion:
            for n in ('pavilion_posts','pavilion_brackets','pavilion_roofs','pavilion_ceiling','pavilion_details','pavilion_inscriptions'):draw(n)
            self.uniform(self.shader,'surfaceKind',1.);self.uniform(self.shader,'twinPart',1.);self.uniform(self.shader,'joiningStone',2.);draw('causeway');self.uniform(self.shader,'twinPart',0.);self.uniform(self.shader,'joiningStone',0.)
            self.uniform(self.shader,'flatPaving',1.);draw('pavilion_base');self.uniform(self.shader,'flatPaving',0.)
            self.uniform(self.shader,'surfaceKind',0.)
        draw('moon_basin')
        self.uniform(self.shader,'surfaceKind',8.);draw('moon_fixture');self.uniform(self.shader,'surfaceKind',0.)
        normal=pr.Vector3(*q.normal)
        self.models['moon_mirror'].transform=pr.quaternion_to_matrix(pr.quaternion_from_vector3_to_vector3(pr.Vector3(0,0,1),normal))
        self.uniform(self.shader,'surfaceKind',5.)
        self.draw('moon_mirror',(MIRROR[0],2*self.water_y-MIRROR[1] if reflection else MIRROR[1],MIRROR[2]),scale)
        self.uniform(self.shader,'surfaceKind',0.)
        if q.disc_placed:draw('canal_annulus')
        if not revealed:
            self.uniform(self.shader,'surfaceKind',4.);draw('lake_bank')
            self.uniform(self.shader,'surfaceKind',2.);draw('lake_mountains')
            self.uniform(self.shader,'surfaceKind',3.);self.uniform(self.shader,'windStrength',1.)
            pr.rl.rlDisableBackfaceCulling();draw('lake_plants')
            fx,fz=cam.target.x-cam.position.x,cam.target.z-cam.position.z;length=math.hypot(fx,fz);fx/=max(.01,length);fz/=max(.01,length)
            for x,y,z,size,yaw,variant in trees():
                if (x-cam.position.x)*fx+(z-cam.position.z)*fz< -15:continue
                self.draw(('chinese_pine_a','chinese_pine_b','chinese_pine_c')[variant],(x,-y if reflection else y,z),(size,-size if reflection else size,size),yaw)
            if not reflection:pr.rl.rlEnableBackfaceCulling()
            self.uniform(self.shader,'surfaceKind',0.);self.uniform(self.shader,'windStrength',0.)
        if not revealed or self.hold_pavilion:
            self.uniform(self.shader,'twinPart',1.);self.uniform(self.shader,'emission',1.);draw('lake_lamps');self.uniform(self.shader,'emission',0.);self.uniform(self.shader,'twinPart',0.)
        if show_player:
            if not reflection:pr.draw_cylinder_ex(pr.Vector3(e.x,e.height+.012,e.z),pr.Vector3(e.x,e.height+.014,e.z),.24,.24,24,pr.Color(3,9,10,95))
            pr.draw_model_ex(self.player.player,pr.Vector3(e.x,2*self.water_y-e.height-.01 if reflection else e.height+.01,e.z),pr.Vector3(0,1,0),180-math.degrees(e.yaw),pr.Vector3(PLAYER_SCALE,-PLAYER_SCALE if reflection else PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)
            if not reflection:self.register_player_selection((e.x,e.height+.01,e.z),PLAYER_SCALE,180-math.degrees(e.yaw))

    def render(self,e,clock,inspection=False,override=None,show_player=True,assembly=False,editor_override=False):
        q=self.sequence
        pose=(e.x,e.height,e.z,e.yaw)
        selection_paused=getattr(self,'_codex_frame_paused',False) or getattr(getattr(self,'codex_selection',None),'enabled',False)
        if not selection_paused and not editor_override:
            if q.locked_camera is not None and not q.transitioning and q.locked_pose!=pose:
                q.locked_camera=None;q._direction_camera_released=True
            if override is not None and not q.transitioning:
                q.locked_camera=None;q._direction_camera_released=True
        directed=None
        if (not editor_override and not selection_paused and q.disc_placed
                and q.direction.camera_enabled and not q._direction_camera_released):
            directed=sample_camera(q.direction,q.elapsed)
        if editor_override and override is not None:
            shot,cam=self.last_shot,override
        elif selection_paused and override is not None:
            # Inspect the displayed frame without dismissing a retained reveal
            # camera. The encounter resumes with its original camera state.
            shot,cam=self.last_shot,override
        elif directed is not None:
            shot,cam=5,camera(directed.eye,directed.target,directed.fov)
            if q.locked_pose is None:q.locked_pose=pose
            q.locked_camera=cam;q.locked_shot=shot
        elif q.transitioning:
            # Capture the actual preceding frame, including an inspection view.
            # Nothing reframes during the fog: near pavilion geometry is the
            # exact same twin in both worlds. Only the hidden surroundings swap.
            if q.locked_camera is None:
                if self.last_camera is None:shot,cam=auto_camera(e)
                else:shot,cam=self.last_shot,self.last_camera
                q.locked_camera=cam;q.locked_shot=shot;q.locked_pose=pose
            shot,cam=q.locked_shot,q.locked_camera
        elif q.locked_camera is not None:shot,cam=q.locked_shot,q.locked_camera
        elif q.focus:shot,cam=5,camera(FOCUS_EYE,FOCUS_TARGET,57)
        elif override is not None:shot,cam=e.shot,override
        elif q.revealed:shot,cam=canal_camera(e)
        else:shot,cam=auto_camera(e)
        self.last_shot=shot;self.last_camera=cam
        clip=e.clip if e.clip in self.player.clips else 'idle';phase=e.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
        self.player.pose(clip,phase,self.player_pose_dt())
        blend=q.world_blend
        self.last_world_weights={'lake':1.-blend,'canals':blend}
        if 0.<blend<1.:
            if self.blend_old_frame is None:
                self.blend_old_frame=pr.load_render_texture(WIDTH,HEIGHT)
                self.blend_new_frame=pr.load_render_texture(WIDTH,HEIGHT)
            # Both images use the same pose, time and camera. Opaque common
            # objects retain unit coverage; only their surroundings dissolve.
            self._render_world(e,cam,clock,inspection,show_player,assembly,False,self.blend_old_frame,blend<.5)
            self._render_world(e,cam,clock,inspection,show_player,assembly,True,self.blend_new_frame,blend>=.5)
            pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.blend_shader)
            pr.set_shader_value(self.blend_shader,pr.get_shader_location(self.blend_shader,'worldBlend'),pr.ffi.new('float[]',[blend]),pr.SHADER_UNIFORM_FLOAT)
            pr.set_shader_value_texture(self.blend_shader,pr.get_shader_location(self.blend_shader,'previousFrame'),self.blend_old_frame.texture)
            pr.draw_texture_pro(self.blend_new_frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
            pr.end_shader_mode();pr.end_texture_mode()
        else:
            self._render_world(e,cam,clock,inspection,show_player,assembly,blend>=1.,self.frame,True)
        return cam

    def _render_world(self,e,cam,clock,inspection,show_player,assembly,revealed,target,capture=True):
        """Render one complete endpoint without altering the encounter state.

        During a dissolve raw/reflection buffers contain the final endpoint
        rendered, while frame contains the actual composited player view.
        Selection records the dominant visible world once, including twins.
        """
        previous=self._world_override;selection=getattr(self,'codex_selection',None)
        self._world_override=bool(revealed)
        if not capture:self.codex_selection=None
        try:self._render_world_frame(e,cam,clock,inspection,show_player,assembly,target)
        finally:
            self._world_override=previous
            if not capture:self.codex_selection=selection

    def _render_world_frame(self,e,cam,clock,inspection,show_player,assembly,target):
        q=self.sequence
        base=(99,116,115) if inspection else (45,60,63)
        fog=pr.Color(*(int(a+(b-a)*q.void_tone) for a,b in zip(base,(42,46,46))),255)
        weather=SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.24 if inspection else .70,void_world=q.void_tone)
        # A real reflected geometry pass at native game resolution, warped only by the water.
        self.environment(cam,clock,inspection,True)
        pr.begin_texture_mode(self.reflection_raw);pr.clear_background(fog)
        mirrored=camera((cam.position.x,2*self.water_y-cam.position.y,cam.position.z),(cam.target.x,2*self.water_y-cam.target.y,cam.target.z),cam.fovy);mirrored.up=pr.Vector3(0,-1,0)
        self.sky.draw(mirrored,weather,fog,WIDTH,HEIGHT);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);pr.rl.rlDisableBackfaceCulling()
        self.geometry(e,cam,clock,True,show_player);pr.rl.rlEnableBackfaceCulling();pr.end_mode_3d();pr.end_texture_mode()
        self.mist_pass(self.reflection_raw,self.reflection,cam,e,clock,inspection,reflected=True)
        self.environment(cam,clock,inspection,False)
        pr.begin_texture_mode(self.raw);pr.clear_background(fog)
        self.sky.draw(cam,weather,fog,WIDTH,HEIGHT);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);self.geometry(e,cam,clock,False,show_player);self.draw('canal_water' if self.render_revealed else 'lake_surface')
        # Raylib batches billboards. Flush on both sides of the depth-mask
        # change, otherwise their transparent rectangles acquire near depth
        # when the batch is eventually submitted, leaking the hidden scene.
        pr.rl.rlDrawRenderBatchActive();pr.rl.rlDisableDepthMask()
        for x,y,z in (LIGHTS[:3] if self.render_revealed else LIGHTS):pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y,z),.85,pr.Color(232,176,91,22))
        pr.rl.rlDrawRenderBatchActive();pr.rl.rlEnableDepthMask()
        if assembly:
            for radius in FUTURE_RING:pr.draw_cylinder_wires(pr.Vector3(0,.08,0),radius,radius,.03,120,pr.Color(119,183,177,255))
            pr.draw_cylinder_wires(pr.Vector3(0,DECK+.035,0),PUZZLE_RADIUS,PUZZLE_RADIUS,.03,64,pr.Color(233,174,91,255))
        pr.end_mode_3d();pr.end_texture_mode()
        self.mist_pass(self.raw,target,cam,e,clock,inspection)

    def mist_pass(self,source,target,cam,e,clock,inspection,reflected=False):
        """Mix lake mist, bounded 3D volumes and puzzle cards in both views."""
        q=self.sequence
        for name,value in (('veil',q.veil),('time',clock),('arrival',q.fog_source_arrival),('returning',0.),
                           ('sourceArrival',q.fog_source_arrival),
                           ('clearing',q.fog_clear),
                           ('reflectedView',float(reflected)),('voidWorld',q.void_tone),('waterY',self.water_y)):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',[value]),pr.SHADER_UNIFORM_FLOAT)
        fog_colour=tuple(a+(b-a)*q.void_tone for a,b in zip((.39,.455,.45) if inspection else (.175,.235,.248),(.165,.180,.180)))
        volumes=getattr(q.direction,'volumes',None)
        volume_renderer=getattr(self,'volume_fog',None)
        volume_active=bool(volumes and volumes.enabled and volume_renderer)
        surface=getattr(q.direction,'surface_fog',None)
        surface_renderer=getattr(self,'surface_fog',None)
        surface_active=bool(surface and surface.enabled and surface_renderer)
        particle_mix=volumes.particle_mix if volume_active or surface_active else 1.
        particle_texture=self.puzzle_fog.render(source,cam,q,clock,fog_colour,self.water_y,reflected) if particle_mix>0. else self.puzzle_fog.clear()
        volume_texture=volume_renderer.render(source,cam,q,clock,fog_colour,self.water_y,reflected) if volume_active else None
        if surface_active:volume_texture=surface_renderer.render(source,cam,q,clock,fog_colour,self.water_y,reflected,base_texture=volume_texture)
        veil_renderer=getattr(self,'surface_veil',None)
        if surface_active and veil_renderer is not None:
            volume_texture=veil_renderer.render(source,cam,q,clock,fog_colour,self.water_y,reflected,base_texture=volume_texture)
        water_veil_active=bool(surface_active and getattr(surface,'water_mask',False) and
                               veil_renderer is not None and veil_renderer.last_active)
        for name,value in (('volumeActive',float(volume_active or surface_active)),('particleMix',particle_mix),
                           ('waterVeilActive',float(water_veil_active))):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',[value]),pr.SHADER_UNIFORM_FLOAT)
        pr.set_shader_value(self.post,pr.get_shader_location(self.post,'fogColour'),pr.ffi.new('float[]',fog_colour),pr.SHADER_UNIFORM_VEC3)
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position));right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up));up=pr.vector3_cross_product(right,forward)
        for name,value in (('eye',cam.position),('forward',forward),('right',right),('up',up)):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',[value.x,value.y,value.z]),pr.SHADER_UNIFORM_VEC3)
        pr.set_shader_value(self.post,pr.get_shader_location(self.post,'playerCenter'),pr.ffi.new('float[]',[e.x,e.height+1.05,e.z]),pr.SHADER_UNIFORM_VEC3)
        for name,value in (('lens',(math.tan(math.radians(cam.fovy)*.5),WIDTH/HEIGHT)),('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar()))):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',value),pr.SHADER_UNIFORM_VEC2)
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.set_shader_value_texture(self.post,pr.get_shader_location(self.post,'depthMap'),source.depth)
        pr.set_shader_value_texture(self.post,pr.get_shader_location(self.post,'particleMap'),particle_texture)
        if volume_texture is not None:pr.set_shader_value_texture(self.post,pr.get_shader_location(self.post,'volumeMap'),volume_texture)
        pr.draw_texture_pro(source.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode()

    def close(self):
        material=getattr(self,'surface_material',None)
        if material is not None:material.close();self.surface_material=None
        super().close()
        if self.blend_old_frame:pr.unload_render_texture(self.blend_old_frame);self.blend_old_frame=None
        if self.blend_new_frame:pr.unload_render_texture(self.blend_new_frame);self.blend_new_frame=None
        if self.blend_shader:pr.unload_shader(self.blend_shader);self.blend_shader=None
        if self.puzzle_fog:self.puzzle_fog.close();self.puzzle_fog=None
        if self.volume_fog:self.volume_fog.close();self.volume_fog=None
        if self.surface_fog:self.surface_fog.close();self.surface_fog=None
        if getattr(self,'surface_veil',None):self.surface_veil.close();self.surface_veil=None
        if self.reflection:pr.unload_render_texture(self.reflection);self.reflection=None
        if self.reflection_raw:pr.unload_render_texture(self.reflection_raw);self.reflection_raw=None
        if self.water_shader:pr.unload_shader(self.water_shader);self.water_shader=None

def reset_player(scene,puzzle=False,direction=None):
    """A fresh encounter; the test shortcut is ready for E without any walking."""
    if direction is None:direction=profile_from_document(load_direction())
    # Upload the baked field during scene/reset setup, never on the first
    # animated frame after the player activates the puzzle.
    surface_renderer=getattr(scene,'surface_fog',None)
    if surface_renderer is not None and direction.surface_fog.enabled:surface_renderer.prepare()
    veil_renderer=getattr(scene,'surface_veil',None)
    if veil_renderer is not None and direction.surface_fog.enabled and direction.surface_fog.water_mask:
        veil_renderer.prepare()
    e=Explorer();scene.sequence=CanalSequence(direction);e.encounter=scene.sequence
    scene.last_camera=None;scene.last_shot=0
    if puzzle:
        e.x,e.height,e.z=1.65,DECK,1.65
        e.yaw=math.atan2(MIRROR[0]-e.x,e.z-MIRROR[2])
        e.shot=camera_zone(e.x,e.z)
        scene.sequence.tick(0.,e)  # Match the mist reached by walking here.
        scene.last_shot,scene.last_camera=auto_camera(e)
    return e


def draw_puzzle_timer(sequence,width,paused=False):
    """Test-only clock using the same elapsed time that drives the fog."""
    elapsed=sequence.elapsed;cue=sequence.cue
    if sequence.state=='ordinary':phase='Ready - press E to start'
    elif elapsed<sequence.entry_start:phase='Fog building'
    elif elapsed<sequence.entry_duration:phase='Fog crest - hidden transition'
    elif getattr(sequence.direction,'fog_mode','banks')=='buildings' and elapsed<sequence.duration:
        groups=sequence.direction.groups
        clearing=sum(g.reveal_start<=elapsed<g.reveal_end for g in groups)
        cleared=sum(elapsed>=g.reveal_end for g in groups)
        phase=f'{cleared} revealed  |  {clearing} clearing'
    elif elapsed<cue('near_end'):phase='Nearby + middle clearing' if elapsed>=cue('middle_start') else 'Nearby fog clearing'
    elif elapsed<cue('middle_end'):phase='Middle + distant clearing' if elapsed>=cue('far_start') else 'Middle fog clearing'
    elif elapsed<cue('far_end'):phase='Distant fog clearing'
    elif elapsed<sequence.duration:phase='Final wisps fading'
    else:phase='Fog cleared'
    x,y=max(12,width-326),40
    ink=pr.Color(224,233,220,255);muted=pr.Color(155,185,180,255)
    pr.draw_rectangle(x,y,310,120,pr.Color(9,18,22,224))
    pr.draw_text('PUZZLE TIMER'+('  |  PAUSED' if paused else ''),x+14,y+10,14,muted)
    pr.draw_text(f'{elapsed:05.1f} s',x+14,y+30,32,ink)
    pr.draw_text(phase,x+14,y+70,16,ink)
    footer=f'Clearing +{elapsed-sequence.entry_duration:.1f} s  |  Home resets' if elapsed>=sequence.entry_duration else 'Since activation  |  Home resets'
    pr.draw_text(footer,x+14,y+98,12,muted)


def run(review=False,direct=False,puzzle=False,direction_path=DEFAULT_PATH):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / The Void Canals');pr.set_target_fps(0 if review else 60);scene=None;audio=None;selection=None
    try:
        start=time.perf_counter();scene=Lake();startup=time.perf_counter()-start
        scene.direction_path=Path(direction_path)
        e=reset_player(scene,puzzle,profile_from_document(load_direction(scene.direction_path)));audio=EncounterAudio(review)
        if review:
            from huxin_canals_review import review_scene
            return review_scene(scene,e,audio,startup)
        if direct:
            e.x,e.height,e.z=START;scene.sequence.revealed=True;scene.sequence.state='canals';scene.sequence.disc_placed=True;e.encounter=scene.sequence
            # Direct inspection skips the completed fog sequence.
            scene.sequence.elapsed=scene.sequence.duration
            scene.sequence.inventory[:]=[s if s is None or s.get('group')!='void_disc' else None for s in scene.sequence.inventory]
        from codex_selection import SelectionSession
        selection=SelectionSession('huxin_canals',__file__);scene.codex_selection=selection
        live_direction=LiveDirectionReload(scene.direction_path,document=document_from_profile(scene.sequence.direction))
        pr.set_exit_key(pr.KEY_NULL);selected_camera=None
        paused_sounds=[]
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True;assembly=False
        while not pr.window_should_close():
            # Saved data continues to reload while F8 pauses gameplay. This
            # does not advance time, release the held camera or replay cues.
            live_direction.poll(scene)
            was_selecting=selection.enabled
            if selection.handle_keys():break
            blocked=was_selecting or selection.enabled
            scene._codex_frame_paused=blocked
            dt=min(pr.get_frame_time(),.05)
            if selection.enabled and not was_selecting:
                paused_sounds=[sound for sound in audio.sounds.values() if pr.is_sound_playing(sound)]
                for sound in paused_sounds:pr.pause_sound(sound)
            elif was_selecting and not selection.enabled:
                for sound in paused_sounds:pr.resume_sound(sound)
                paused_sounds=[]
            if not blocked and pr.is_key_pressed(pr.KEY_F2):
                from huxin_canals_editor import run_embedded
                manual=None;free=False;pr.enable_cursor()
                clock=run_embedded(scene,e,audio,clock)
                live_direction.acknowledge_scene(scene)
                selected_camera=scene.last_camera
                continue
            if blocked:
                override=selected_camera
            else:
                clock+=dt
                if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
                if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
                if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
                if pr.is_key_pressed(pr.KEY_F3):assembly=not assembly
                if pr.is_key_pressed(pr.KEY_HOME):
                    e=reset_player(scene,puzzle,live_direction.load_for_reset());manual=None;free=False;pr.enable_cursor()
                    if puzzle:
                        clock=0.
                        for sound in audio.sounds.values():pr.stop_sound(sound)
                        paused_sounds=[]
                if pr.is_key_pressed(pr.KEY_ZERO):manual=None;free=False;pr.enable_cursor()
                for i in range(9):
                    if pr.is_key_pressed(pr.KEY_ONE+i):manual=i;free=False;pr.enable_cursor()
                if pr.is_key_pressed(pr.KEY_F):
                    free=not free
                    if free:
                        e.clip='idle';scene.sequence.focus=False
                        current=scene.last_camera or auto_camera(e)[1]
                        eye=[current.position.x,current.position.y,current.position.z];v=[current.target.x-eye[0],current.target.y-eye[1],current.target.z-eye[2]]
                        yaw=math.atan2(v[0],-v[2]);pitch=math.atan2(v[1],math.hypot(v[0],v[2]));pr.disable_cursor()
                    else:pr.enable_cursor()
                forward=int(pr.is_key_down(pr.KEY_W))-int(pr.is_key_down(pr.KEY_S));turn=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A));override=None
                q=scene.sequence
                if not free and not q.transitioning and pr.is_key_pressed(pr.KEY_E):
                    if q.activate(e):manual=None;e.clip='idle'
                if free:
                    mouse=pr.get_mouse_delta();yaw+=mouse.x*.002;pitch=max(-1.45,min(1.45,pitch-mouse.y*.002));speed=10 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 3.5
                    eye[0]+=(math.sin(yaw)*forward+math.cos(yaw)*turn)*speed*dt;eye[2]+=(-math.cos(yaw)*forward+math.sin(yaw)*turn)*speed*dt
                    eye[1]+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*speed*dt
                    override=camera(eye,(eye[0]+math.sin(yaw)*math.cos(pitch),eye[1]+math.sin(pitch),eye[2]-math.cos(yaw)*math.cos(pitch)),70)
                else:
                    if not q.movement_locked:e.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
                    else:e.clip='idle'
                    if manual is not None:s=(CAMERA_SHOTS if q.revealed else SHOTS)[manual];override=camera(s['eye'],s['target'],s['fov'])
                q.tick(dt,e);audio.drain(q)
            q=scene.sequence
            selection.begin_frame()
            selected_camera=scene.render(e,clock,inspection,override,show_player,assembly)
            pr.begin_drawing();pr.clear_background(pr.BLACK);w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible and not q.movement_locked:
                pr.draw_rectangle(0,h-52,w,52,pr.Color(10,20,22,226))
                pr.draw_text(q.prompt(e) or 'W/S move   A/D turn   Shift run   E place object   1-9 cameras   0 auto   F free look',18,h-42,16,pr.Color(206,213,198,255))
                pr.draw_text('L daylight | Tab player | H help | Home restart | F2 scene editor | F8 select | F12 capture | Esc exit',18,h-21,14,pr.Color(147,178,175,255))
                if free:pr.draw_text('Free camera',19,18,18,pr.Color(206,213,198,255))
            if puzzle:draw_puzzle_timer(q,w,blocked)
            draw_live_direction_status(live_direction,w,h)
            selection.present(selected_camera,(0,0,w,h),{'world':'canals' if q.revealed else 'lake','world_blend':q.world_blend,'selection_world':'canals' if q.world_blend>=.5 else 'lake','phase':q.state,'clock':clock,'player':{'position':[e.x,e.height,e.z],'yaw':e.yaw,'clip':e.clip},'shot':scene.last_shot,'free_camera':free})
            if pr.is_key_pressed(pr.KEY_F12):
                out=ROOT/'artifacts'/'huxin_canals';out.mkdir(parents=True,exist_ok=True);capture=out/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png')
                if puzzle:
                    pr.rl.rlDrawRenderBatchActive()
                    image=pr.load_image_from_screen()
                    try:pr.export_image(image,str(capture))
                    finally:pr.unload_image(image)
                else:snapshot(scene.frame,capture)
            pr.end_drawing()
    finally:
        if selection:selection.close()
        pr.enable_cursor()
        if scene:scene.close()
        if audio:audio.close()
        pr.close_window()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',action='store_true')
    p.add_argument('--direction',type=Path,default=DEFAULT_PATH,help='Independent scene direction and fog preset')
    start=p.add_mutually_exclusive_group()
    start.add_argument('--canals',action='store_true',help='Start directly inside the canal world')
    start.add_argument('--puzzle',action='store_true',help='Start beside the unsolved puzzle with a timing overlay; Home resets here')
    start.add_argument('--editor',action='store_true',help='Open the Void Canals scene timeline and placement editor')
    args=p.parse_args()
    if args.editor:
        from huxin_canals_editor import run as run_editor
        run_editor(args.direction)
    else:run(args.review,args.canals,args.puzzle,args.direction)
