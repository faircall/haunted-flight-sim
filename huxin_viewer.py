"""The Still Lake / 湖心亭: independent, silent lake pavilion art prototype."""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
from pathlib import Path
from types import SimpleNamespace
import math
import json
import time
import argparse
import statistics
import pyray as pr
from PIL import Image,ImageDraw
from g_huxin import Explorer,SHOTS,LIGHTS,COLUMNS,PATH,DECK,PUZZLE_RADIUS,FUTURE_RING,REVIEW_ROUTE,trees,PLAYER_SCALE,walk_height,SPAWN
from g_temple_living import LivingScene
from temple_interior_viewer import Hall,camera,snapshot
from temple_intro_sky import Sky

ROOT=Path(__file__).parent;KIT=ROOT/'art'/'temple'/'huxin';WIDTH,HEIGHT=640,360

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
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None;self.reflection=None;self.water_shader=None;self.last_shot=0
        try:
            self.manifest=json.loads((KIT/'manifest.json').read_text())
            self.shader=pr.load_shader(str(ROOT/'shaders'/'huxin.vs'),str(ROOT/'shaders'/'huxin.fs'))
            self.water_shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'huxin_water.fs'))
            for s in (self.shader,self.water_shader):
                if s.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake shader compilation failed')
                s.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(s,'matModel');s.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(s,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='huxin.fs')
            names=('eyePosition','time','inspection','opacity','emission','surfaceKind','reflectionPass','lampCount','lamps','windStrength','deckHeight')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in names} for s in (self.shader,self.player.skin,self.water_shader)}
            for name in self.manifest['models']:self.load(name,KIT/(name+'.glb'))
            for n in ('chinese_pine_a','chinese_pine_b','chinese_pine_c'):self.load(n,ROOT/'art'/'temple'/'intro'/(n+'.glb'))
            self.raw=pr.load_render_texture(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT);self.reflection=pr.load_render_texture(WIDTH,HEIGHT)
            pr.set_texture_filter(self.reflection.texture,pr.TEXTURE_FILTER_BILINEAR)
            water=self.models['lake_surface']
            for i in range(water.materialCount):
                water.materials[i].shader=self.water_shader;water.materials[i].maps[pr.MATERIAL_MAP_NORMAL].texture=self.reflection.texture
            self.water_shader.locs[pr.SHADER_LOC_MAP_NORMAL]=pr.get_shader_location(self.water_shader,'reflectionTexture')
            pr.set_shader_value(self.water_shader,pr.get_shader_location(self.water_shader,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'temple_interior_post.fs'))
            if self.post.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake post shader compilation failed')
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.sky=Sky();im=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK);self.smoke=pr.load_texture_from_image(im);pr.unload_image(im)
        except Exception:self.close();raise

    def environment(self,cam,clock,inspection,reflection):
        for s in (self.shader,self.player.skin,self.water_shader):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.),('surfaceKind',0.),('reflectionPass',float(reflection)),('windStrength',0.)):self.uniform(s,name,value)
            self.uniform(s,'deckHeight',DECK);self.uniform(s,'lampCount',len(LIGHTS),'int')
            if self.locations[s.id]['lamps']>=0:pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in LIGHTS for v in p]),pr.SHADER_UNIFORM_VEC3,len(LIGHTS))

    def geometry(self,e,cam,clock,reflection,show_player):
        scale=(1,-1,1) if reflection else 1
        for n in ('pavilion_posts','pavilion_brackets','pavilion_roofs','pavilion_ceiling','pavilion_details','pavilion_inscriptions'):self.draw(n,scale=scale)
        self.uniform(self.shader,'surfaceKind',1.)
        for n in ('causeway','pavilion_base'):self.draw(n,scale=scale)
        self.uniform(self.shader,'surfaceKind',4.);self.draw('lake_bank',scale=scale)
        self.uniform(self.shader,'surfaceKind',2.);self.draw('lake_mountains',scale=scale)
        self.uniform(self.shader,'surfaceKind',3.);self.uniform(self.shader,'windStrength',1.)
        pr.rl.rlDisableBackfaceCulling();self.draw('lake_plants',scale=scale)
        fx,fz=cam.target.x-cam.position.x,cam.target.z-cam.position.z;length=math.hypot(fx,fz);fx/=max(.01,length);fz/=max(.01,length)
        for x,y,z,size,yaw,variant in trees():
            if (x-cam.position.x)*fx+(z-cam.position.z)*fz< -15:continue
            self.draw(('chinese_pine_a','chinese_pine_b','chinese_pine_c')[variant],(x,-y if reflection else y,z),(size,-size if reflection else size,size),yaw)
        if not reflection:pr.rl.rlEnableBackfaceCulling()
        self.uniform(self.shader,'surfaceKind',0.);self.uniform(self.shader,'windStrength',0.);self.uniform(self.shader,'emission',1.);self.draw('lake_lamps',scale=scale);self.uniform(self.shader,'emission',0.)
        if show_player:
            if not reflection:pr.draw_cylinder_ex(pr.Vector3(e.x,e.height+.012,e.z),pr.Vector3(e.x,e.height+.014,e.z),.24,.24,24,pr.Color(3,9,10,95))
            pr.draw_model_ex(self.player.player,pr.Vector3(e.x,-e.height-.01 if reflection else e.height+.01,e.z),pr.Vector3(0,1,0),180-math.degrees(e.yaw),pr.Vector3(PLAYER_SCALE,-PLAYER_SCALE if reflection else PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)

    def render(self,e,clock,inspection=False,override=None,show_player=True,assembly=False):
        shot,cam=auto_camera(e) if override is None else (e.shot,override);self.last_shot=shot
        clip=e.clip if e.clip in self.player.clips else 'idle';phase=e.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
        self.player.pose(clip,phase,1/60)
        fog=pr.Color(*(tuple((99,116,115)) if inspection else (45,60,63)),255)
        weather=SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.24 if inspection else .70)
        # A real reflected geometry pass at native game resolution, warped only by the water.
        self.environment(cam,clock,inspection,True)
        pr.begin_texture_mode(self.reflection);pr.clear_background(fog)
        mirrored=camera((cam.position.x,-cam.position.y,cam.position.z),(cam.target.x,-cam.target.y,cam.target.z),cam.fovy);mirrored.up=pr.Vector3(0,-1,0)
        self.sky.draw(mirrored,weather,fog,WIDTH,HEIGHT);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);pr.rl.rlDisableBackfaceCulling()
        self.geometry(e,cam,clock,True,show_player);pr.rl.rlEnableBackfaceCulling();pr.end_mode_3d();pr.end_texture_mode()
        self.environment(cam,clock,inspection,False)
        pr.begin_texture_mode(self.raw);pr.clear_background(fog)
        self.sky.draw(cam,weather,fog,WIDTH,HEIGHT);pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(fog.r,fog.g,fog.b,56))
        pr.begin_mode_3d(cam);self.geometry(e,cam,clock,False,show_player);self.draw('lake_surface')
        pr.rl.rlDisableDepthMask()
        for x,y,z in LIGHTS:pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y,z),.85,pr.Color(232,176,91,22))
        pr.rl.rlEnableDepthMask()
        if assembly:
            for radius in FUTURE_RING:pr.draw_cylinder_wires(pr.Vector3(0,.08,0),radius,radius,.03,120,pr.Color(119,183,177,255))
            pr.draw_cylinder_wires(pr.Vector3(0,DECK+.035,0),PUZZLE_RADIUS,PUZZLE_RADIUS,.03,64,pr.Color(233,174,91,255))
        pr.end_mode_3d();pr.end_texture_mode();pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.draw_texture_pro(self.raw.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode();return cam

    def close(self):
        super().close()
        if self.reflection:pr.unload_render_texture(self.reflection);self.reflection=None
        if self.water_shader:pr.unload_shader(self.water_shader);self.water_shader=None

def run(review=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / The Still Lake');pr.set_target_fps(0 if review else 60);scene=None
    try:
        start=time.perf_counter();scene=Lake();startup=time.perf_counter()-start;e=Explorer()
        if review:return review_scene(scene,e,startup)
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True;assembly=False
        while not pr.window_should_close():
            dt=min(pr.get_frame_time(),.05);clock+=dt
            if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
            if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
            if pr.is_key_pressed(pr.KEY_F3):assembly=not assembly
            if pr.is_key_pressed(pr.KEY_HOME):e=Explorer();manual=None;free=False;pr.enable_cursor()
            if pr.is_key_pressed(pr.KEY_ZERO):manual=None;free=False;pr.enable_cursor()
            for i in range(9):
                if pr.is_key_pressed(pr.KEY_ONE+i):manual=i;free=False;pr.enable_cursor()
            if pr.is_key_pressed(pr.KEY_F):
                free=not free
                if free:
                    e.clip='idle';s=SHOTS[manual if manual is not None else scene.last_shot];eye=list(s['eye']);v=[s['target'][i]-eye[i] for i in range(3)]
                    yaw=math.atan2(v[0],-v[2]);pitch=math.atan2(v[1],math.hypot(v[0],v[2]));pr.disable_cursor()
                else:pr.enable_cursor()
            forward=int(pr.is_key_down(pr.KEY_W))-int(pr.is_key_down(pr.KEY_S));turn=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A));override=None
            if free:
                mouse=pr.get_mouse_delta();yaw+=mouse.x*.002;pitch=max(-1.45,min(1.45,pitch-mouse.y*.002));speed=10 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 3.5
                eye[0]+=(math.sin(yaw)*forward+math.cos(yaw)*turn)*speed*dt;eye[2]+=(-math.cos(yaw)*forward+math.sin(yaw)*turn)*speed*dt
                eye[1]+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*speed*dt
                override=camera(eye,(eye[0]+math.sin(yaw)*math.cos(pitch),eye[1]+math.sin(pitch),eye[2]-math.cos(yaw)*math.cos(pitch)),70)
            else:
                e.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
                if manual is not None:s=SHOTS[manual];override=camera(s['eye'],s['target'],s['fov'])
            scene.render(e,clock,inspection,override,show_player,assembly)
            pr.begin_drawing();pr.clear_background(pr.BLACK);w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible:
                pr.draw_rectangle(0,h-52,w,52,pr.Color(10,20,22,226))
                pr.draw_text('W/S move  A/D turn  Shift run  1-9 cameras  0 auto  F free look  L daylight  F3 assembly space',18,h-42,16,pr.Color(206,213,198,255))
                pr.draw_text('Free: mouse + WASD, Q/E height | Tab player | H help | Home reset | F12 capture | Esc exit',18,h-21,14,pr.Color(147,178,175,255))
                pr.draw_text('Free camera' if free else SHOTS[manual if manual is not None else scene.last_shot]['name'],19,18,18,pr.Color(206,213,198,255))
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                out=ROOT/'artifacts'/'huxin';out.mkdir(parents=True,exist_ok=True);snapshot(scene.frame,out/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png'))
    finally:
        pr.enable_cursor()
        if scene:scene.close()
        pr.close_window()

def review_scene(scene,e,startup):
    out=ROOT/'artifacts'/'huxin';out.mkdir(parents=True,exist_ok=True)
    positions=(SPAWN,(-11,63),(-8,42),(-3,22),(0,10),(0,0),(0,-2),(0,0),(0,3))
    samples=[(s['name'],s['eye'],s['target'],s['fov'],False,positions[i],False) for i,s in enumerate(SHOTS)]
    samples.extend((('The roof from below',(1.2,2.0,1.6),(0,6.4,0),85,True,(0,0),False),
        ('The tiled double eaves',(13,11,14),(0,5.2,0),65,True,(0,0),False),
        ('Space for what comes next',(65,46,68),(0,0,9),63,True,(0,0),True)))
    sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*6),(12,23,25));labels=ImageDraw.Draw(sheet)
    for i,(name,eye,target,fov,day,pos,assembly) in enumerate(samples):
        e.x,e.z=pos;e.height=walk_height(*pos);scene.render(e,32,day,camera(eye,target,fov),i<9,assembly)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(scene.frame,dest)
        x=i%2*WIDTH;y=i//2*(HEIGHT+25);sheet.paste(Image.open(dest).convert('RGB'),(x,y));labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(203,211,195))
    sheet.save(out/'lake-review.png');frames=[];timings=[];zones=set();e=Explorer();steps=0;blocked=[]
    for name,eye,target,day in (
        ('shore-entrance',(-8,3.8,84),(-12,1.,75),False),
        ('shore-entrance-day',(-6,6.2,86),(-12,.4,77),True),
        ('shore-from-water',(-18,2.5,69),(-12,.7,80),True),
        ('shore-overhead',(-12,14,80),(-12,0,79),True)):
        scene.render(e,32,day,camera(eye,target,62),False);snapshot(scene.frame,out/(name+'.png'))
    for x,z in REVIEW_ROUTE:
        for _ in range(1200):
            dx,dz=x-e.x,z-e.z
            if math.hypot(dx,dz)<.12:break
            e.yaw=math.atan2(dx,-dz);distance=e.tick(.05,1);steps+=1
            if distance<1e-6:raise AssertionError(('Blocked causeway',x,z,e.x,e.z))
            if steps%14==0:
                t=time.perf_counter();cam=scene.render(e,32+steps*.05);zones.add(scene.last_shot)
                if not clear_view((cam.position.x,cam.position.y,cam.position.z),(e.x,e.height+.93,e.z)):blocked.append((e.x,e.z))
                im=pr.load_image_from_texture(scene.frame.texture);pr.image_flip_vertical(im)
                frames.append(Image.frombytes('RGBA',(WIDTH,HEIGHT),bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4))).convert('RGB'));pr.unload_image(im)
                timings.append((time.perf_counter()-t)*1000)
        else:raise AssertionError(('Unreachable lake waypoint',x,z))
    if blocked:raise AssertionError(('Obstructed lake cameras',blocked))
    frames[0].save(out/'lake-walkthrough.gif',save_all=True,append_images=frames[1:],duration=95,loop=0,optimize=True)
    report=dict(audio='No audio device opened',startup_seconds=startup,frames=len(frames),camera_zones=sorted(zones),
        median_frame_and_readback_ms=statistics.median(timings),blocked_camera_samples=blocked,final=(e.x,e.z),
        triangles=scene.manifest['total_triangles'],pine_instances=len(trees()),puzzle_clear_diameter=PUZZLE_RADIUS*2,reserved_water_ring=FUTURE_RING,enemy_count=0)
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',action='store_true');run(p.parse_args().review)
