"""The Moon in the Water: independent, explorable lake pavilion encounter."""
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
from g_huxin_moon import Explorer,SHOTS,LIGHTS,COLUMNS,PATH,DECK,PUZZLE_RADIUS,FUTURE_RING,REVIEW_ROUTE,trees,PLAYER_SCALE,walk_height,SPAWN
from g_temple_living import LivingScene
from temple_interior_viewer import Hall,camera,snapshot
from temple_intro_viewer import camera_from_pose
from huxin_moon_sky import MoonSky
from g_huxin_moon_sequence import MoonSequence,UPPER,MIRROR,BASIN,MARK,TEA_LIGHTS,ease
from huxin_moon_camera import interior_camera,mist_camera,wide_reveal_camera,TEA_SHOTS,FOCUS_EYE,FOCUS_TARGET
from huxin_moon_audio import EncounterAudio
from temple_intro_fog import depth_target

ROOT=Path(__file__).parent;KIT=ROOT/'art'/'temple'/'huxin_moon';WIDTH,HEIGHT=640,360

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
    def __init__(self,targeted=True,camera_path=None):
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None;self.reflection=None;self.reflection_raw=None;self.water_shader=None;self.last_shot=0;self.sequence=MoonSequence();self.last_camera=None
        self.targeted=targeted;self.target_fog=None;self._world_override=None
        self.camera_director=None;self._authored_hold=False
        try:
            self.manifest=json.loads((KIT/'manifest.json').read_text())
            self.shader=pr.load_shader(str(ROOT/'shaders'/'huxin_moon.vs'),str(ROOT/'shaders'/'huxin_moon.fs'))
            self.water_shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'huxin_moon_water.fs'))
            for s in (self.shader,self.water_shader):
                if s.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake shader compilation failed')
                s.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(s,'matModel');s.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(s,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='huxin_moon.fs')
            names=('eyePosition','time','inspection','opacity','emission','surfaceKind','reflectionPass','lampCount','lamps','windStrength','deckHeight','veil','enclosed','warmth','flatPaving')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in names} for s in (self.shader,self.player.skin,self.water_shader)}
            for name in self.manifest['models']:self.load(name,KIT/(name+'.glb'))
            self.tea_manifest=json.loads((KIT/'teahouse_manifest.json').read_text())
            for name in self.tea_manifest['models']:self.load(name,KIT/(name+'.glb'))
            for n in ('chinese_pine_a','chinese_pine_b','chinese_pine_c'):self.load(n,ROOT/'art'/'temple'/'intro'/(n+'.glb'))
            self.raw=depth_target(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT);self.reflection=pr.load_render_texture(WIDTH,HEIGHT)
            self.reflection_raw=depth_target(WIDTH,HEIGHT)
            pr.set_texture_filter(self.reflection.texture,pr.TEXTURE_FILTER_BILINEAR)
            water=self.models['lake_surface']
            for i in range(water.materialCount):
                water.materials[i].shader=self.water_shader;water.materials[i].maps[pr.MATERIAL_MAP_NORMAL].texture=self.reflection.texture
            self.water_shader.locs[pr.SHADER_LOC_MAP_NORMAL]=pr.get_shader_location(self.water_shader,'reflectionTexture')
            pr.set_shader_value(self.water_shader,pr.get_shader_location(self.water_shader,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'huxin_moon_post.fs'))
            if self.post.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake post shader compilation failed')
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            if targeted:
                from huxin_moon_target_fog import MoonTargetFog
                from huxin_moon_camera_runtime import MoonCameraDirector
                self.target_fog=MoonTargetFog(WIDTH,HEIGHT)
                self.target_fog.prepare()
                self.camera_director=MoonCameraDirector(camera_path)
            self.sky=MoonSky();im=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK);self.smoke=pr.load_texture_from_image(im);pr.unload_image(im)
        except Exception:self.close();raise

    @property
    def render_revealed(self):
        return self.sequence.revealed if self._world_override is None else self._world_override

    def environment(self,cam,clock,inspection,reflection):
        lights=LIGHTS+TEA_LIGHTS
        for s in (self.shader,self.player.skin,self.water_shader):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.),('surfaceKind',0.),('reflectionPass',float(reflection)),('windStrength',0.)):self.uniform(s,name,value)
            self.uniform(s,'deckHeight',DECK);self.uniform(s,'lampCount',len(lights),'int');self.uniform(s,'veil',self.sequence.veil);self.uniform(s,'enclosed',float(self.render_revealed))
            self.uniform(s,'warmth',self.sequence.warmth)
            self.uniform(s,'flatPaving',0.)
            if self.locations[s.id]['lamps']>=0:pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in lights for v in p]),pr.SHADER_UNIFORM_VEC3,len(lights))

    def geometry(self,e,cam,clock,reflection,show_player):
        scale=(1,-1,1) if reflection else 1
        if self.render_revealed:
            self.uniform(self.shader,'surfaceKind',6.)
            for n in ('pavilion_posts','pavilion_details'):self.draw(n,scale=scale)
            self.uniform(self.shader,'surfaceKind',0.)
            for n in ('tea_frame','tea_walls','tea_lattice','tea_floors','tea_stairs','tea_ceiling','tea_furniture'):self.draw(n,scale=scale)
            self.uniform(self.shader,'surfaceKind',7.);self.draw('tea_roofs',scale=scale);self.uniform(self.shader,'surfaceKind',0.)
        else:
            for n in ('pavilion_posts','pavilion_brackets','pavilion_roofs','pavilion_ceiling','pavilion_details','pavilion_inscriptions'):self.draw(n,scale=scale)
        self.draw('moon_basin',scale=scale)
        self.uniform(self.shader,'surfaceKind',8.);self.draw('moon_fixture',scale=scale);self.uniform(self.shader,'surfaceKind',0.)
        # A local +Z disc is rotated to the exact normal used for ray reflection.
        normal=pr.Vector3(*self.sequence.normal);rotation=pr.quaternion_to_matrix(pr.quaternion_from_vector3_to_vector3(pr.Vector3(0,0,1),normal))
        self.models['moon_mirror'].transform=rotation
        self.uniform(self.shader,'surfaceKind',5.)
        self.draw('moon_mirror',(MIRROR[0],-MIRROR[1] if reflection else MIRROR[1],MIRROR[2]),scale)
        self.uniform(self.shader,'surfaceKind',0.)
        hit=self.sequence.hit()
        if hit is not None:
            y=-BASIN[1] if reflection else BASIN[1]
            # A small pale lunar image in the dark water, not an emissive marker.
            pr.draw_cylinder_ex(pr.Vector3(hit[0],y+.003,hit[2]),pr.Vector3(hit[0],y+.005,hit[2]),.067,.067,32,pr.Color(171,191,183,255))
        self.uniform(self.shader,'surfaceKind',1.)
        self.draw('causeway',scale=scale)
        self.uniform(self.shader,'flatPaving',1.);self.draw('pavilion_base',scale=scale);self.uniform(self.shader,'flatPaving',0.)
        if self.render_revealed:
            self.draw('tea_foundation',scale=scale);self.draw('tea_ground',scale=scale)
        self.uniform(self.shader,'surfaceKind',4.);self.draw('lake_bank',scale=scale)
        self.uniform(self.shader,'surfaceKind',2.);self.draw('lake_mountains',scale=scale)
        self.uniform(self.shader,'surfaceKind',3.);self.uniform(self.shader,'windStrength',1.)
        pr.rl.rlDisableBackfaceCulling();self.draw('lake_plants',scale=scale)
        fx,fz=cam.target.x-cam.position.x,cam.target.z-cam.position.z;length=math.hypot(fx,fz);fx/=max(.01,length);fz/=max(.01,length)
        for x,y,z,size,yaw,variant in trees():
            if (x-cam.position.x)*fx+(z-cam.position.z)*fz< -15:continue
            self.draw(('chinese_pine_a','chinese_pine_b','chinese_pine_c')[variant],(x,-y if reflection else y,z),(size,-size if reflection else size,size),yaw)
        if not reflection:pr.rl.rlEnableBackfaceCulling()
        self.uniform(self.shader,'surfaceKind',0.);self.uniform(self.shader,'windStrength',0.);self.uniform(self.shader,'emission',1.);self.draw('lake_lamps',scale=scale)
        if self.render_revealed:self.draw('tea_lanterns',scale=scale)
        self.uniform(self.shader,'emission',0.)
        if show_player:
            if not reflection:pr.draw_cylinder_ex(pr.Vector3(e.x,e.height+.012,e.z),pr.Vector3(e.x,e.height+.014,e.z),.24,.24,24,pr.Color(3,9,10,95))
            pr.draw_model_ex(self.player.player,pr.Vector3(e.x,-e.height-.01 if reflection else e.height+.01,e.z),pr.Vector3(0,1,0),180-math.degrees(e.yaw),pr.Vector3(PLAYER_SCALE,-PLAYER_SCALE if reflection else PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)

    def _select_camera(self,e,clock,override=None,authoring=False,manual_shot=None):
        if authoring:
            if override is None:raise ValueError('Camera authoring requires an explicit preview camera.')
            return -1,override
        q=self.sequence
        director=getattr(self,'camera_director',None)
        if director is not None:director.update(clock)

        def authored(trigger,index,fallback,manual=False):
            result=director.camera(trigger,e,q,clock,include_zones=not manual) if director is not None else None
            if result is None:return index,fallback
            _,pose=result
            return index,camera_from_pose(pose)

        def outdoor():
            index,fallback=auto_camera(e)
            return authored({'type':'lake','index':index},index,fallback)

        pose=(e.x,e.height,e.z,e.yaw)
        if q.locked_camera is not None and not q.transitioning and q.locked_pose!=pose:
            q.locked_camera=None;self._authored_hold=False
        if (override is not None or manual_shot is not None) and not q.transitioning:
            q.locked_camera=None;self._authored_hold=False
        if q.transitioning:
            if q.camera_stage=='walking':
                self._authored_hold=False;shot,cam=outdoor()
            elif self.targeted:
                self._authored_hold=True
                index,fallback=wide_reveal_camera()
                shot,cam=authored({'type':'reveal'},index,fallback)
            else:shot,cam=mist_camera(q,e)
            # Hold the last cinematic view until the player next moves.
            q.locked_camera=cam;q.locked_pose=pose
        elif q.locked_camera is not None:
            if getattr(self,'_authored_hold',False) and director is not None:
                shot,cam=authored({'type':'reveal'},self.last_shot,q.locked_camera)
                q.locked_camera=cam
            else:shot,cam=self.last_shot,q.locked_camera
        elif q.focus:shot,cam=authored({'type':'focus'},5,camera(FOCUS_EYE,FOCUS_TARGET,57))
        elif override is not None:
            if director is not None:director.reset()
            shot,cam=e.shot,override
        elif manual_shot is not None:
            stations=TEA_SHOTS if q.revealed else SHOTS
            index=max(0,min(len(stations)-1,int(manual_shot)));spec=stations[index]
            shot,cam=authored({'type':'room' if q.revealed else 'lake','index':index},
                              index,camera(spec['eye'],spec['target'],spec['fov']),manual=True)
        elif q.revealed and e.z<8.5:
            index,fallback=interior_camera(e)
            shot,cam=authored({'type':'room','index':index},index,fallback)
        else:shot,cam=outdoor()
        return shot,cam

    def render(self,e,clock,inspection=False,override=None,show_player=True,assembly=False,authoring=False,manual_shot=None):
        shot,cam=self._select_camera(e,clock,override,authoring,manual_shot)
        self.last_shot=shot;self.last_camera=cam
        clip=e.clip if e.clip in self.player.clips else 'idle';phase=e.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
        self.player.pose(clip,phase,1/60)
        # Local mist fully conceals the original logical handoff. Render its
        # committed world once, including reflection, without a second scene.
        self._render_world(e,cam,clock,inspection,show_player,assembly,self.sequence.revealed,self.frame)
        return cam

    def _render_world(self,e,cam,clock,inspection,show_player,assembly,revealed,target):
        previous=self._world_override;self._world_override=bool(revealed)
        try:self._render_world_frame(e,cam,clock,inspection,show_player,assembly,target)
        finally:self._world_override=previous

    def _render_world_frame(self,e,cam,clock,inspection,show_player,assembly,target):
        fog=pr.Color(*(tuple((99,116,115)) if inspection else (45,60,63)),255)
        weather=SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.24 if inspection else .70)
        # A real reflected geometry pass at native game resolution, warped only by the water.
        self.environment(cam,clock,inspection,True)
        pr.begin_texture_mode(self.reflection_raw);pr.clear_background(fog)
        self.sky.draw(cam,weather,fog,WIDTH,HEIGHT,reflected=True);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);pr.rl.rlDisableBackfaceCulling()
        self.geometry(e,cam,clock,True,show_player);pr.rl.rlEnableBackfaceCulling();pr.end_mode_3d();pr.end_texture_mode()
        self.mist_pass(self.reflection_raw,self.reflection,cam,e,clock,inspection,reflected=True)
        self.environment(cam,clock,inspection,False)
        pr.begin_texture_mode(self.raw);pr.clear_background(fog)
        self.sky.draw(cam,weather,fog,WIDTH,HEIGHT);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);self.geometry(e,cam,clock,False,show_player);self.draw('lake_surface')
        # Flush billboards on either side of the depth-mask change: otherwise
        # transparent glow rectangles can acquire depth and cut holes in fog.
        if self.targeted:pr.rl.rlDrawRenderBatchActive()
        pr.rl.rlDisableDepthMask()
        for x,y,z in (TEA_LIGHTS+LIGHTS[-2:] if self.render_revealed else LIGHTS):pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y,z),.85,pr.Color(232,176,91,22))
        if self.targeted:pr.rl.rlDrawRenderBatchActive()
        pr.rl.rlEnableDepthMask()
        if assembly:
            for radius in FUTURE_RING:pr.draw_cylinder_wires(pr.Vector3(0,.08,0),radius,radius,.03,120,pr.Color(119,183,177,255))
            pr.draw_cylinder_wires(pr.Vector3(0,DECK+.035,0),PUZZLE_RADIUS,PUZZLE_RADIUS,.03,64,pr.Color(233,174,91,255))
        pr.end_mode_3d();pr.end_texture_mode()
        self.mist_pass(self.raw,target,cam,e,clock,inspection)

    def mist_pass(self,source,target,cam,e,clock,inspection,reflected=False):
        """One world-space fog field for direct sight and the reflected light path."""
        q=self.sequence
        veil,arrival,returning=q.veil,q.fog_arrival,float(q.state=='leaving')
        crest=ease(0.,6.,q.elapsed) if q.state=='entering' else 0.
        if self.targeted and q.state=='entering':
            veil=q.entry_veil*(1.-q.fog_clear);arrival=q.entry_arrival;crest=0.
        elif self.targeted and q.state=='leaving':
            veil*=.35;arrival*=.90;returning=0.
        for name,value in (('veil',veil),('time',clock),('arrival',arrival),('clearing',q.fog_clear),('returning',returning),
                           ('crest',crest),('travelling',float(q.state in ('ordinary','leaving'))),
                           ('reflectedView',float(reflected))):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',[value]),pr.SHADER_UNIFORM_FLOAT)
        fog_colour=(.39,.455,.45) if inspection else (.175,.235,.248)
        texture=None
        if self.target_fog is not None:
            texture=self.target_fog.render(source,cam,q,clock,fog_colour,reflected,
                player_center=(e.x,e.height+1.05,e.z))
        pr.set_shader_value(self.post,pr.get_shader_location(self.post,'targetActive'),pr.ffi.new('float[]',[float(texture is not None)]),pr.SHADER_UNIFORM_FLOAT)
        pr.set_shader_value(self.post,pr.get_shader_location(self.post,'fogColour'),pr.ffi.new('float[]',fog_colour),pr.SHADER_UNIFORM_VEC3)
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position));right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up));up=pr.vector3_cross_product(right,forward)
        for name,value in (('eye',cam.position),('forward',forward),('right',right),('up',up)):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',[value.x,value.y,value.z]),pr.SHADER_UNIFORM_VEC3)
        pr.set_shader_value(self.post,pr.get_shader_location(self.post,'playerCenter'),pr.ffi.new('float[]',[e.x,e.height+1.05,e.z]),pr.SHADER_UNIFORM_VEC3)
        for name,value in (('lens',(math.tan(math.radians(cam.fovy)*.5),WIDTH/HEIGHT)),('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar()))):
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,name),pr.ffi.new('float[]',value),pr.SHADER_UNIFORM_VEC2)
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.set_shader_value_texture(self.post,pr.get_shader_location(self.post,'depthMap'),source.depth)
        if texture is not None:pr.set_shader_value_texture(self.post,pr.get_shader_location(self.post,'targetMap'),texture)
        pr.draw_texture_pro(source.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode()

    def close(self):
        if self.target_fog:self.target_fog.close();self.target_fog=None
        super().close()
        if self.reflection:pr.unload_render_texture(self.reflection);self.reflection=None
        if self.reflection_raw:pr.unload_render_texture(self.reflection_raw);self.reflection_raw=None
        if self.water_shader:pr.unload_shader(self.water_shader);self.water_shader=None

def reset_player(scene,puzzle=False):
    e=Explorer();scene.sequence=MoonSequence();e.encounter=scene.sequence
    scene.last_camera=None;scene.last_shot=0
    scene._authored_hold=False
    if getattr(scene,'camera_director',None) is not None:scene.camera_director.reset()
    if puzzle:
        from g_huxin_moon_sequence import SOLUTION
        e.x,e.height,e.z=1.65,DECK,1.65
        e.yaw=math.atan2(MIRROR[0]-e.x,e.z-MIRROR[2])
        scene.sequence.yaw,scene.sequence.pitch=SOLUTION
        scene.sequence.tick(0.,e)
    return e


def edit_cameras(scene,actor,audio,clock,editor_runner=None):
    """Pause play for camera authoring; preview never replaces gameplay state."""
    if editor_runner is None:
        from huxin_moon_cinematographer import edit_scene
        editor_runner=edit_scene
    old_size=(pr.get_screen_width(),pr.get_screen_height())
    was_resizable=pr.is_window_state(pr.FLAG_WINDOW_RESIZABLE)
    previous={name:getattr(scene,name) for name in ('sequence','last_camera','last_shot','_authored_hold')}
    if audio:
        for sound in audio.sounds.values():pr.stop_sound(sound)
    pr.enable_cursor();pr.set_exit_key(pr.KEY_NULL)
    pr.set_window_state(pr.FLAG_WINDOW_RESIZABLE)
    pr.set_window_size(max(1360,old_size[0]),max(900,old_size[1]))
    pr.set_window_min_size(1360,900)
    try:
        return editor_runner(scene,actor,clock,path=scene.camera_director.path)
    finally:
        for name,value in previous.items():setattr(scene,name,value)
        scene.camera_director.reload(force=True)
        pr.set_window_min_size(320,180);pr.set_window_size(*old_size)
        if not was_resizable:pr.clear_window_state(pr.FLAG_WINDOW_RESIZABLE)
        # Consume the editor's closing Escape while the game exit key is off.
        # Otherwise that same keypress can also quit the underlying game.
        pr.poll_input_events()
        pr.set_exit_key(pr.KEY_ESCAPE);pr.enable_cursor()


def run(review=False,legacy_fog=False,puzzle_test=False,muted=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / The Moon in the Water');pr.set_target_fps(0 if review else 60);scene=None;audio=None
    try:
        start=time.perf_counter();scene=Lake(targeted=not legacy_fog);startup=time.perf_counter()-start
        e=reset_player(scene,puzzle_test);audio=EncounterAudio(review or muted or puzzle_test)
        if review:
            from huxin_moon_review import review_scene
            return review_scene(scene,e,audio,startup)
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True;assembly=False
        while not pr.window_should_close():
            dt=min(pr.get_frame_time(),.05);clock+=dt
            if pr.is_key_pressed(pr.KEY_F2) and scene.targeted:
                edit_cameras(scene,e,audio,clock)
                if free:pr.disable_cursor()
                continue
            if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
            if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
            if pr.is_key_pressed(pr.KEY_F3):assembly=not assembly
            if pr.is_key_pressed(pr.KEY_HOME):e=reset_player(scene,puzzle_test);manual=None;free=False;pr.enable_cursor()
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
                if q.focus:q.focus=False
                elif q.state=='ordinary' and math.hypot(e.x-MIRROR[0],e.z-MIRROR[2])<2.1:q.focus=True;manual=None;e.clip='idle'
            if free:
                mouse=pr.get_mouse_delta();yaw+=mouse.x*.002;pitch=max(-1.45,min(1.45,pitch-mouse.y*.002));speed=10 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 3.5
                eye[0]+=(math.sin(yaw)*forward+math.cos(yaw)*turn)*speed*dt;eye[2]+=(-math.cos(yaw)*forward+math.sin(yaw)*turn)*speed*dt
                eye[1]+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*speed*dt
                override=camera(eye,(eye[0]+math.sin(yaw)*math.cos(pitch),eye[1]+math.sin(pitch),eye[2]-math.cos(yaw)*math.cos(pitch)),70)
            else:
                if q.focus:q.adjust(dt,int(pr.is_key_down(pr.KEY_RIGHT))-int(pr.is_key_down(pr.KEY_LEFT)),int(pr.is_key_down(pr.KEY_UP))-int(pr.is_key_down(pr.KEY_DOWN)))
                elif not q.movement_locked:e.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
                else:e.clip='idle'
            q.tick(dt,e);audio.drain(q)
            scene.render(e,clock,inspection,override,show_player,assembly,manual_shot=None if free else manual)
            pr.begin_drawing();pr.clear_background(pr.BLACK);w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible and not q.movement_locked:
                pr.draw_rectangle(0,h-52,w,52,pr.Color(10,20,22,226))
                pr.draw_text(q.prompt(e) or 'W/S move   A/D turn   Shift run   E examine   1-9 cameras   0 auto   F free look',18,h-42,16,pr.Color(206,213,198,255))
                editor_hint='F2 camera editor | ' if scene.targeted else ''
                pr.draw_text(editor_hint+'L daylight | Tab player | H help | Home restart | F12 capture | Esc exit',18,h-21,14,pr.Color(147,178,175,255))
                if free:pr.draw_text('Free camera',19,18,18,pr.Color(206,213,198,255))
            if puzzle_test:
                label=('Teahouse reveal  %.2fs'%q.elapsed if q.state=='entering' else
                       'Return along causeway  %.1f%%'%(q.return_progress*100.) if q.state=='leaving' else
                       'E: begin mirror reveal   Home: reset at puzzle' if q.state=='ordinary' else
                       'Walk back along the causeway   Home: reset at puzzle')
                pr.draw_rectangle(12,12,min(w-24,pr.measure_text(label,16)+24),30,pr.Color(10,20,22,220))
                pr.draw_text(label,24,20,16,pr.Color(206,213,198,255))
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                out=ROOT/'artifacts'/'huxin_moon';out.mkdir(parents=True,exist_ok=True);snapshot(scene.frame,out/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png'))
    finally:
        pr.enable_cursor()
        if scene:scene.close()
        if audio:audio.close()
        pr.close_window()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',action='store_true')
    p.add_argument('--legacy-fog',action='store_true',help='Use the previous broad-fog teahouse transition')
    p.add_argument('--puzzle-test',action='store_true',help='Start at the aligned mirror with a muted timer preview')
    p.add_argument('--muted',action='store_true')
    args=p.parse_args();run(args.review,args.legacy_fog,args.puzzle_test,args.muted)
