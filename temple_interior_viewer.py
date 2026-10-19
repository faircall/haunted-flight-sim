"""Separate playable temple interior art study, with fixed survival-horror cameras."""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
from pathlib import Path
from types import SimpleNamespace
import math
import json
import time
import argparse
import random
import pyray as pr
from PIL import Image,ImageDraw
from g_temple_interior import Explorer,SHOTS,LIGHTS,COLUMNS,SPAWN,can_walk,PLAYER_SCALE,GAIT
from g_temple_living import LivingScene
from temple_intro_sky import Sky

ROOT=Path(__file__).resolve().parent;KIT=ROOT/'art'/'temple'/'interior'
WIDTH,HEIGHT=640,360

def camera(eye,target,fov=65):return pr.Camera3D(pr.Vector3(*eye),pr.Vector3(*target),pr.Vector3(0,1,0),fov,pr.CAMERA_PERSPECTIVE)

class Hall:
    def __init__(self):
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None
        try:
            self.shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'temple_interior.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Interior shader failed')
            self.shader.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(self.shader,'matModel')
            self.shader.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(self.shader,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='temple_interior.fs')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in ('eyePosition','time','inspection','opacity','emission','lampCount','lamps','columns')} for s in (self.shader,self.player.skin)}
            for name in json.loads((KIT/'manifest.json').read_text())['models']:self.load(name,KIT/(name+'.glb'))
            for name in ('temple_cypress_a','lacebark_pine','ridge_a'):self.load(name,ROOT/'art'/'temple'/'intro'/(name+'.glb'))
            self.raw=pr.load_render_texture(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'temple_interior_post.fs'))
            if self.post.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Interior post shader failed')
            location=pr.get_shader_location(self.post,'resolution')
            pr.set_shader_value(self.post,location,pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.sky=Sky();rng=random.Random(341)
            self.trees=[(side*rng.uniform(13,26),rng.uniform(13,46),rng.uniform(.65,.95),rng.random()*360) for side in (-1,1) for i in range(12)]
            image=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK);self.smoke=pr.load_texture_from_image(image);pr.unload_image(image)
        except Exception:self.close();raise

    def load(self,name,path):
        # Subclasses use their own constructors, so keep source tracking lazy.
        if not hasattr(self,'_model_paths'):self._model_paths={}
        self._model_paths[name]=Path(path)
        model=pr.load_model(str(path));self.models[name]=model
        if not model.meshCount:raise RuntimeError('Empty hall model: '+name)
        for i in range(model.materialCount):
            material=model.materials[i];material.shader=self.shader;t=material.maps[pr.MATERIAL_MAP_DIFFUSE].texture
            if t.id and t.id!=pr.rl.rlGetTextureIdDefault():
                owned=pr.ffi.new('Texture2D *',t)
                pr.gen_texture_mipmaps(owned)
                material.maps[pr.MATERIAL_MAP_DIFFUSE].texture=owned[0]
                self.textures[t.id]=owned[0]
                pr.set_texture_filter(owned[0],pr.TEXTURE_FILTER_TRILINEAR)

    def uniform(self,s,name,values,kind=None):
        location=self.locations[s.id][name]
        if location<0:return
        if kind=='int':pr.set_shader_value(s,location,pr.ffi.new('int[]',[values]),pr.SHADER_UNIFORM_INT);return
        values=values if isinstance(values,(tuple,list)) else [values]
        pr.set_shader_value(s,location,pr.ffi.new('float[]',values),{1:pr.SHADER_UNIFORM_FLOAT,3:pr.SHADER_UNIFORM_VEC3}[len(values)])

    def environment(self,cam,clock,inspection):
        for s in (self.shader,self.player.skin):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.)):self.uniform(s,name,value)
            self.uniform(s,'lampCount',len(LIGHTS),'int')
            pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in LIGHTS for v in p]),pr.SHADER_UNIFORM_VEC3,len(LIGHTS))
            pr.set_shader_value_v(s,self.locations[s.id]['columns'],pr.ffi.new('float[]',[v for p in COLUMNS for v in p]),pr.SHADER_UNIFORM_VEC3,len(COLUMNS))

    def draw(self,name,position=(0,0,0),scale=1.,yaw=0.):
        scales=(scale,)*3 if isinstance(scale,(float,int)) else scale
        selection=getattr(self,'codex_selection',None)
        # The lake renderers draw reflected instances with negative Y scale.
        # Only the direct scene belongs in the selection ray's world.
        if selection is not None and selection.enabled and scales[1]>0:
            selection.register_model(self.models[name],name,getattr(self,'_model_paths',{}).get(name),
                position,scales,yaw,metadata=self.selection_metadata(name))
        pr.draw_model_ex(self.models[name],pr.Vector3(*position),pr.Vector3(0,1,0),yaw,pr.Vector3(*scales),pr.WHITE)

    def selection_metadata(self,name):
        return None

    def register_player_selection(self,position,scale,yaw):
        selection=getattr(self,'codex_selection',None)
        if selection is not None and selection.enabled:
            x,y,z=position
            selection.register_model(self.player.player,'player',self.player.asset_root/'player.glb',
                position,scale,yaw,identity='player',metadata={'kind':'actor','animated':True,
                    'world_bounds':{'min':[x-.35,y,z-.35],'max':[x+.35,y+1.85,z+.35]}})

    def player_pose_dt(self):
        paused=getattr(self,'_codex_frame_paused',False) or getattr(getattr(self,'codex_selection',None),'enabled',False)
        return 0. if paused else 1/60

    def render(self,explorer,clock,inspection=False,override=None,show_player=True):
        shot=SHOTS[explorer.shot];cam=override or camera(shot['eye'],shot['target'],shot['fov'])
        self.environment(cam,clock,inspection)
        pr.begin_texture_mode(self.raw);pr.clear_background(pr.Color(17,25,30,255))
        fog=pr.Color(*(tuple((79,91,90)) if inspection else (19,29,38)),255)
        self.sky.draw(cam,SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.1 if inspection else .95),fog,WIDTH,HEIGHT)
        pr.begin_mode_3d(cam)
        for name in ('hall_courtyard','hall_shell','hall_timber','hall_ceiling','hall_roof','hall_altar','hall_statues','hall_props','hall_murals'):self.draw(name)
        self.uniform(self.shader,'emission',1.);self.draw('hall_lamps');self.uniform(self.shader,'emission',0.)
        pr.rl.rlDisableBackfaceCulling()
        for i,(x,z,size,yaw) in enumerate(self.trees):self.draw('lacebark_pine' if i%4==0 else 'temple_cypress_a',(x,-.1,z),size,yaw)
        pr.rl.rlEnableBackfaceCulling()
        for x in (-70,0,75):self.draw('ridge_a',(x,-2,120),(55,45,60))
        if show_player:
            # Soft contact shadow grounds the character without changing the rig.
            pr.draw_cylinder_ex(pr.Vector3(explorer.x,.015,explorer.z),pr.Vector3(explorer.x,.018,explorer.z),.25,.25,24,pr.Color(6,10,11,75))
            clip=explorer.clip if explorer.clip in self.player.clips else 'idle'
            phase=explorer.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
            self.player.pose(clip,phase,self.player_pose_dt())
            pr.draw_model_ex(self.player.player,pr.Vector3(explorer.x,.035,explorer.z),pr.Vector3(0,1,0),180-math.degrees(explorer.yaw),pr.Vector3(PLAYER_SCALE,PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)
            self.register_player_selection((explorer.x,.035,explorer.z),PLAYER_SCALE,180-math.degrees(explorer.yaw))
        # Small incense wisps and motes hold depth against the complete interior.
        pr.rl.rlDisableDepthMask()
        for base in ((0,1.92,-2.95),(-8.9,1.74,-7.5),(8.9,1.74,-7.5)):
            for i in range(16):
                t=((clock*.11+i/16)%1);p=pr.Vector3(base[0]+.13*math.sin(t*8+clock*.25)*t,base[1]+t*1.9,base[2]+.10*math.cos(t*7+clock*.2)*t)
                pr.draw_billboard(cam,self.smoke,p,.12+t*.30,pr.Color(153,159,149,int(16*math.sin(t*math.pi))))
        for i in range(45):
            x=math.sin(i*91.7)*8;y=(i*.417+clock*.017)%5.8+.2;z=math.cos(i*12.3)*8
            if abs(x)<3.5 and z>0:pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y,z),.028,pr.Color(165,179,170,50))
        pr.rl.rlEnableDepthMask()
        # Exterior-only rainfall never passes through the hall roof.
        for i in range(160):
            x=math.sin(i*17.91)*19;z=12+(i*1.73)%28;y=(i*.819-clock*8)%13
            pr.draw_line_3d(pr.Vector3(x,y,z),pr.Vector3(x-.03,y-.38,z),pr.Color(116,142,151,83))
        pr.end_mode_3d();pr.end_texture_mode()
        pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.draw_texture_pro(self.raw.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode();return cam

    def close(self):
        if self.player:self.player.close();self.player=None
        for m in self.models.values():pr.unload_model(m)
        for t in self.textures.values():pr.unload_texture(t)
        self.models.clear();self.textures.clear()
        if self.sky:self.sky.close();self.sky=None
        if self.smoke:pr.unload_texture(self.smoke);self.smoke=None
        for name in ('raw','frame'):
            target=getattr(self,name)
            if target:pr.unload_render_texture(target);setattr(self,name,None)
        for name in ('shader','post'):
            s=getattr(self,name)
            if s:pr.unload_shader(s);setattr(self,name,None)

def snapshot(target,path):
    image=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(image);pr.export_image(image,str(path));pr.unload_image(image)

def run(review=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / Hall of Returning Rain');pr.set_target_fps(0 if review else 60)
    hall=None;selection=None
    try:
        start=time.perf_counter();hall=Hall();startup=time.perf_counter()-start;explorer=Explorer()
        if review:return review_hall(hall,explorer,startup)
        from codex_selection import SelectionSession
        selection=SelectionSession('temple_interior',__file__);hall.codex_selection=selection
        pr.set_exit_key(pr.KEY_NULL);selected_camera=None
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True
        while not pr.window_should_close():
            was_selecting=selection.enabled
            if selection.handle_keys():break
            blocked=was_selecting or selection.enabled
            hall._codex_frame_paused=blocked
            dt=min(pr.get_frame_time(),.05)
            if blocked:
                override=selected_camera
            else:
                clock+=dt
                if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
                if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
                if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
                if pr.is_key_pressed(pr.KEY_HOME):explorer=Explorer();manual=None;free=False;pr.enable_cursor()
                if pr.is_key_pressed(pr.KEY_ZERO):manual=None;free=False;pr.enable_cursor()
                for i in range(len(SHOTS)):
                    if pr.is_key_pressed(pr.KEY_ONE+i):manual=i;free=False;pr.enable_cursor()
                if pr.is_key_pressed(pr.KEY_F):
                    free=not free
                    if free:
                        explorer.clip='idle'
                        sh=SHOTS[manual if manual is not None else explorer.shot];eye=list(sh['eye']);v=[sh['target'][i]-eye[i] for i in range(3)]
                        yaw=math.atan2(v[0],-v[2]);pitch=math.atan2(v[1],math.hypot(v[0],v[2]));pr.disable_cursor()
                    else:pr.enable_cursor()
                forward=int(pr.is_key_down(pr.KEY_W))-int(pr.is_key_down(pr.KEY_S));turn=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A))
                override=None
                if free:
                    mouse=pr.get_mouse_delta();yaw+=mouse.x*.002;pitch=max(-1.45,min(1.45,pitch-mouse.y*.002))
                    speed=5 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 2.4
                    eye[0]+=(math.sin(yaw)*forward+math.cos(yaw)*turn)*speed*dt;eye[2]+=(-math.cos(yaw)*forward+math.sin(yaw)*turn)*speed*dt
                    eye[1]+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*speed*dt
                    target=(eye[0]+math.sin(yaw)*math.cos(pitch),eye[1]+math.sin(pitch),eye[2]-math.cos(yaw)*math.cos(pitch))
                    override=camera(eye,target,70)
                else:
                    explorer.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
                    if manual is not None:
                        sh=SHOTS[manual];override=camera(sh['eye'],sh['target'],sh['fov'])
            selection.begin_frame()
            selected_camera=hall.render(explorer,clock,inspection,override,show_player)
            pr.begin_drawing();pr.clear_background(pr.BLACK)
            w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(hall.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible:
                pr.draw_rectangle(0,h-52,w,52,pr.Color(9,13,15,215))
                pr.draw_text('W/S move   A/D turn   Shift run   1-7 cameras   0 auto   F free look   L lighting   H hide help',18,h-42,16,pr.Color(210,209,187,255))
                pr.draw_text('Free look: mouse + WASD, Q/E height   |   Home reset   Tab player   F8 select | F12 capture   Esc exit',18,h-21,14,pr.Color(139,160,158,255))
            selection.present(selected_camera,(0,0,w,h),{'world':'temple_interior','phase':'exploration','clock':clock,'player':{'position':[explorer.x,0.,explorer.z],'yaw':explorer.yaw,'clip':explorer.clip},'shot':explorer.shot,'free_camera':free})
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                folder=ROOT/'artifacts'/'temple-interior';folder.mkdir(parents=True,exist_ok=True);snapshot(hall.frame,folder/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png'))
    finally:
        if selection:selection.close()
        pr.enable_cursor()
        if hall:hall.close()
        pr.close_window()

def review_hall(hall,explorer,startup):
    out=ROOT/'artifacts'/'temple-interior';out.mkdir(parents=True,exist_ok=True)
    samples=[(s['name'],s['eye'],s['target'],s['fov'],False) for s in SHOTS]
    samples.extend((('Guanyin close',(0,1.9,-9.3),(0,3.2,-7.08),72,False),
                    ('Ceiling close',(0,5.0,-2.1),(0,7.9,-3),88,True),
                    ('Rainy porch',(7.3,1.9,16),(0,3.5,2),73,False),
                    ('Altar detail',(2.3,1.8,-.4),(0,2.65,-5.8),54,False),
                    ('Daylight study',(8.6,3.2,5.2),(-2.1,2.9,-3.6),73,True)))
    sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*6),(14,19,20));labels=ImageDraw.Draw(sheet)
    explorer.x,explorer.z=(-3.9,2.6)
    for i,(name,eye,target,fov,inspection) in enumerate(samples):
        hall.render(explorer,13.5,inspection,camera(eye,target,fov),show_player=i<7)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(hall.frame,dest)
        image=Image.open(dest).convert('RGB');x=i%2*WIDTH;y=i//2*(HEIGHT+25);sheet.paste(image,(x,y));labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(218,216,193))
    sheet.save(out/'interior-review.png')
    # Exercise collision and camera cuts with the same controller used by play.
    from collections import deque
    step=.25;start=(0,40);target=(0,-36);queue=deque([start]);parents={start:None}
    while queue and target not in parents:
        node=queue.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            nxt=(node[0]+dx,node[1]+dz)
            if nxt not in parents and can_walk(nxt[0]*step,nxt[1]*step):parents[nxt]=node;queue.append(nxt)
    assert target in parents,'Rear mural aisle is inaccessible'
    nodes=[];n=target
    while n is not None:nodes.append(n);n=parents[n]
    nodes.reverse();frames=[];timings=[];visited=set();explorer=Explorer()
    for i,node in enumerate(nodes):
        x,z=node[0]*step,node[1]*step
        if i:
            explorer.yaw=math.atan2(x-explorer.x,-(z-explorer.z));explorer.tick(.1,1.,0.,False)
            explorer.tick(.1,1.,0.,False)
        # Camera review samples the known collision-free path; motion uses the rig.
        explorer.x,explorer.z=x,z;explorer.tick(0);explorer.clip='walk';explorer.phase=i*.25/(GAIT['walk']['stride']*PLAYER_SCALE)
        visited.add(explorer.shot);before=time.perf_counter();hall.render(explorer,15+i*.12)
        im=pr.load_image_from_texture(hall.frame.texture);pr.image_flip_vertical(im)
        raw=bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4));pr.unload_image(im)
        frames.append(Image.frombytes('RGBA',(WIDTH,HEIGHT),raw).convert('RGB'));timings.append(time.perf_counter()-before)
    frames[0].save(out/'interior-walkthrough.gif',save_all=True,append_images=frames[1:],duration=120,loop=0)
    report=dict(audio='No audio device opened',startup_seconds=startup,frames=len(frames),camera_zones=sorted(visited),
                median_frame_and_readback_ms=sorted(timings)[len(timings)//2]*1000,models=len(hall.models),
                scene='Independent temple interior; intro and water-courtyard saves untouched')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--review',action='store_true');run(parser.parse_args().review)
