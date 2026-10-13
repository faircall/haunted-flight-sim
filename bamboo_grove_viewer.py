"""Play or silently review the independent Bamboo Hermitage scene."""
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
from g_bamboo_grove import Explorer,SHOTS,LIGHTS,SPAWN,PATH,can_walk,floor_height,ground_height,PLAYER_SCALE,GAIT
from g_temple_living import LivingScene
from temple_interior_viewer import Hall,camera,snapshot
from temple_intro_sky import Sky

ROOT=Path(__file__).resolve().parent;KIT=ROOT/'art'/'temple'/'bamboo';WIDTH,HEIGHT=640,360

class Grove(Hall):
    """Reuse the hall's GLB ownership/upload helpers, with independent assets/state."""
    def __init__(self):
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None
        try:
            self.manifest=json.loads((KIT/'manifest.json').read_text())
            self.shader=pr.load_shader(str(ROOT/'shaders'/'bamboo_grove.vs'),str(ROOT/'shaders'/'bamboo_grove.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Bamboo shader failed')
            self.shader.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(self.shader,'matModel')
            self.shader.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(self.shader,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='bamboo_grove.fs')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in ('eyePosition','time','inspection','opacity','emission','lampCount','lamps','windStrength','waterPass')} for s in (self.shader,self.player.skin)}
            for name in self.manifest['models']:self.load(name,KIT/(name+'.glb'))
            self.raw=pr.load_render_texture(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'temple_interior_post.fs'))
            if self.post.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Grove post shader failed')
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.sky=Sky();im=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK)
            self.smoke=pr.load_texture_from_image(im);pr.unload_image(im)
        except Exception:self.close();raise

    def environment(self,cam,clock,inspection):
        for s in (self.shader,self.player.skin):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.),('windStrength',0.),('waterPass',0.)):self.uniform(s,name,value)
            self.uniform(s,'lampCount',len(LIGHTS),'int')
            pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in LIGHTS for v in p]),pr.SHADER_UNIFORM_VEC3,len(LIGHTS))

    def render(self,explorer,clock,inspection=False,override=None,show_player=True):
        sh=SHOTS[explorer.shot];cam=override or camera(sh['eye'],sh['target'],sh['fov']);self.environment(cam,clock,inspection)
        pr.begin_texture_mode(self.raw);pr.clear_background(pr.Color(26,42,39,255))
        fog=pr.Color(*(tuple((83,103,86)) if inspection else (31,48,46)),255)
        self.sky.draw(cam,SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.18 if inspection else .69),fog,WIDTH,HEIGHT)
        pr.begin_mode_3d(cam)
        for name in ('grove_ground','grove_path','chan_shell','chan_timber','chan_roof','chan_props','chan_scrolls'):self.draw(name)
        self.uniform(self.shader,'windStrength',1.)
        for i in range(6):self.draw('bamboo_culms_'+str(i))
        pr.rl.rlDisableBackfaceCulling()
        for i in range(6):self.draw('bamboo_leaves_'+str(i))
        self.uniform(self.shader,'windStrength',.09);self.draw('grove_flowers');self.draw('grove_understory')
        pr.rl.rlEnableBackfaceCulling();self.uniform(self.shader,'windStrength',0.)
        self.uniform(self.shader,'emission',1.);self.draw('grove_lamps');self.uniform(self.shader,'emission',0.)
        # The small rain basin catches a muted sky reflection and expanding rings.
        pr.begin_shader_mode(self.shader);self.uniform(self.shader,'waterPass',1.)
        pr.draw_cylinder(pr.Vector3(-6.5,.60,-1),.52,.52,.008,32,pr.Color(61,89,76,255));self.uniform(self.shader,'waterPass',0.);pr.end_shader_mode()
        if show_player:
            pr.draw_cylinder_ex(pr.Vector3(explorer.x,explorer.height+.013,explorer.z),pr.Vector3(explorer.x,explorer.height+.016,explorer.z),.24,.24,24,pr.Color(4,12,9,95))
            clip=explorer.clip if explorer.clip in self.player.clips else 'idle'
            phase=explorer.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
            self.player.pose(clip,phase,1/60)
            pr.draw_model_ex(self.player.player,pr.Vector3(explorer.x,explorer.height+.01,explorer.z),pr.Vector3(0,1,0),180-math.degrees(explorer.yaw),pr.Vector3(PLAYER_SCALE,PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)
        # Transparent wisps and restrained lantern halos; no sound device is opened.
        pr.rl.rlDisableDepthMask()
        for i in range(18):
            t=(clock*.085+i/18)%1
            pr.draw_billboard(cam,self.smoke,pr.Vector3(.25+math.sin(t*8+clock*.2)*t*.12,1.82+t*1.5,-11.4),.07+t*.24,pr.Color(180,183,151,int(17*math.sin(t*math.pi))))
        for x,y,z in sorted(LIGHTS,key=lambda p:-sum((p[i]-(cam.position.x,cam.position.y,cam.position.z)[i])**2 for i in range(3))):
            pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y-.05,z),.85,pr.Color(229,167,70,23))
        for i in range(55):
            x=math.sin(i*37.6)*13;z=math.cos(i*17.8)*23+10;y=.45+(i*.312+clock*.016)%5
            pr.draw_billboard(cam,self.smoke,pr.Vector3(x+math.sin(clock*.11+i)*.17,y,z),.02,pr.Color(180,193,144,45))
        pr.rl.rlEnableDepthMask()
        # A few falling narrow leaves; dense foliage itself sways entirely on GPU.
        for i in range(22):
            z=5+(i*3.13)%35;x=math.sin(i*45.9)*10;t=(clock*.12+i*.34)%1;y=11*(1-t);a=clock*.4+i
            p=pr.Vector3(x+math.sin(a)*.4,y,z)
            q=pr.Vector3(p.x+.11*math.cos(a),y-.02,p.z+.11*math.sin(a));r=pr.Vector3(p.x-.025*math.sin(a),y+.014,p.z+.025*math.cos(a))
            pr.draw_triangle_3d(p,q,r,pr.Color(75,91,42,255));pr.draw_triangle_3d(r,q,p,pr.Color(75,91,42,255))
        pr.end_mode_3d();pr.end_texture_mode()
        pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.draw_texture_pro(self.raw.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode();return cam

def run(review=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / Bamboo Hermitage');pr.set_target_fps(0 if review else 60)
    grove=None
    try:
        start=time.perf_counter();grove=Grove();startup=time.perf_counter()-start;e=Explorer()
        if review:return review_grove(grove,e,startup)
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True
        while not pr.window_should_close():
            dt=min(pr.get_frame_time(),.05);clock+=dt
            if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
            if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
            if pr.is_key_pressed(pr.KEY_HOME):e=Explorer();manual=None;free=False;pr.enable_cursor()
            if pr.is_key_pressed(pr.KEY_ZERO):manual=None;free=False;pr.enable_cursor()
            for i in range(len(SHOTS)):
                if pr.is_key_pressed(pr.KEY_ONE+i):manual=i;free=False;pr.enable_cursor()
            if pr.is_key_pressed(pr.KEY_F):
                free=not free
                if free:
                    e.clip='idle';sh=SHOTS[manual if manual is not None else e.shot];eye=list(sh['eye']);v=[sh['target'][i]-eye[i] for i in range(3)]
                    yaw=math.atan2(v[0],-v[2]);pitch=math.atan2(v[1],math.hypot(v[0],v[2]));pr.disable_cursor()
                else:pr.enable_cursor()
            forward=int(pr.is_key_down(pr.KEY_W))-int(pr.is_key_down(pr.KEY_S));turn=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A));override=None
            if free:
                mouse=pr.get_mouse_delta();yaw+=mouse.x*.002;pitch=max(-1.45,min(1.45,pitch-mouse.y*.002));speed=5 if pr.is_key_down(pr.KEY_LEFT_SHIFT) else 2.4
                eye[0]+=(math.sin(yaw)*forward+math.cos(yaw)*turn)*speed*dt;eye[2]+=(-math.cos(yaw)*forward+math.sin(yaw)*turn)*speed*dt
                eye[1]+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*speed*dt
                override=camera(eye,(eye[0]+math.sin(yaw)*math.cos(pitch),eye[1]+math.sin(pitch),eye[2]-math.cos(yaw)*math.cos(pitch)),70)
            else:
                e.tick(dt,forward,turn,pr.is_key_down(pr.KEY_LEFT_SHIFT))
                if manual is not None:sh=SHOTS[manual];override=camera(sh['eye'],sh['target'],sh['fov'])
            grove.render(e,clock,inspection,override,show_player)
            pr.begin_drawing();pr.clear_background(pr.BLACK);w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(grove.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible:
                pr.draw_rectangle(0,h-51,w,51,pr.Color(9,17,14,219))
                pr.draw_text('W/S move   A/D turn   Shift run   1-8 cameras   0 auto   F free look   L daylight   H hide help',18,h-42,16,pr.Color(207,213,179,255))
                pr.draw_text('Free look: mouse + WASD, Q/E height   |   Home reset   Tab player   F12 capture   Esc exit',18,h-21,14,pr.Color(139,169,148,255))
                name='Free camera' if free else SHOTS[manual if manual is not None else e.shot]['name']
                pr.draw_text(name,19,18,18,pr.Color(207,213,179,255))
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                folder=ROOT/'artifacts'/'bamboo-grove';folder.mkdir(parents=True,exist_ok=True);snapshot(grove.frame,folder/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png'))
    finally:
        pr.enable_cursor()
        if grove:grove.close()
        pr.close_window()

def review_grove(grove,e,startup):
    out=ROOT/'artifacts'/'bamboo-grove';out.mkdir(parents=True,exist_ok=True)
    samples=[(s['name'],s['eye'],s['target'],s['fov'],False) for s in SHOTS]
    samples.extend((('The last bend',(3.7,1.7,5.4),(0,2.7,-7.5),65,False),
        ('Round window',(-2.2,2.0,-8.6),(.1,2.4,-12.9),66,False),
        ('Roof and canopy',(8,8.5,-1),(0,3,-9),70,True),
        ('Daylight garden',(10.2,3.3,8.5),(-.7,2.25,-4.8),66,True)))
    positions=((0,38),(-6.6,23),(-2,13),(1.5,1),(0,-8.2),(0,-7),(-5.7,21),(-8,-3))
    sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*6),(13,24,20));labels=ImageDraw.Draw(sheet)
    for i,(name,eye,target,fov,inspection) in enumerate(samples):
        e.x,e.z=positions[min(i,7)];e.height=floor_height(e.x,e.z)
        grove.render(e,16.3,inspection,camera(eye,target,fov),show_player=i<8)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(grove.frame,dest)
        im=Image.open(dest).convert('RGB');x=i%2*WIDTH;y=i//2*(HEIGHT+25);sheet.paste(im,(x,y));labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(210,216,185))
    sheet.save(out/'grove-review.png')
    # Follow the actual controller through every bend, up the stairs and inside.
    route=[p for p in PATH if -.4<p[1]<=40]+[(0,-1),(0,-2),(0,-3.6),(0,-4.4),(0,-6.6),(1.05,-8.3),(1.05,-10.0),(-.7,-11.2)]
    e=Explorer();visited=set();frames=[];timings=[];steps=0
    for x,z in route:
        for _ in range(260):
            dx,dz=x-e.x,z-e.z
            if math.hypot(dx,dz)<.13:break
            e.yaw=math.atan2(dx,-dz);distance=e.tick(.05,1,0,False);steps+=1
            if steps%9==0:
                start=time.perf_counter();grove.render(e,16+steps*.05)
                im=pr.load_image_from_texture(grove.frame.texture);pr.image_flip_vertical(im)
                frames.append(Image.frombytes('RGBA',(WIDTH,HEIGHT),bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4))).convert('RGB'));pr.unload_image(im)
                timings.append((time.perf_counter()-start)*1000);visited.add(e.shot)
            if distance<.00001:raise AssertionError(('Walkthrough blocked',e.x,e.z,(x,z)))
        else:raise AssertionError(('Could not reach route point',x,z))
    if frames:frames[0].save(out/'grove-walkthrough.gif',save_all=True,append_images=frames[1:],duration=90,loop=0,optimize=True)
    report=dict(audio='No audio device opened',startup_seconds=startup,frames=len(frames),camera_zones=sorted(visited),
        median_frame_and_readback_ms=statistics.median(timings),bamboo_count=grove.manifest['bamboo_count'],
        triangles=grove.manifest['total_triangles'],final_position=(e.x,e.z),scene='Independent bamboo grove and Chan room')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',action='store_true');run(parser.parse_args().review)
