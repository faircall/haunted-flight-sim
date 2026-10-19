"""Separate playable rockery maze, with silent native review and encounter overlay."""
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
from g_rockery import Explorer,SHOTS,LIGHTS,NODES,EDGES,ROOMS,ENCOUNTERS,REVIEW_ROUTES,PLAYER_SCALE,GAIT,review_points,edge_point,edge_frame,edge_path
from g_temple_living import LivingScene
from temple_interior_viewer import Hall,camera,snapshot
from temple_intro_sky import Sky
from rockery_camera import RockField,Director

ROOT=Path(__file__).resolve().parent;KIT=ROOT/'art'/'temple'/'rockery';WIDTH,HEIGHT=640,360

class Rockery(Hall):
    def __init__(self):
        self.models={};self.textures={};self.shader=None;self.player=None;self.sky=None;self.post=None;self.raw=None;self.frame=None;self.smoke=None;self.field=None
        try:
            self.manifest=json.loads((KIT/'manifest.json').read_text());self.field_info=json.loads((KIT/'field.json').read_text())
            self.director=Director(RockField(KIT))
            self.shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'rockery.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Rockery shader failed')
            self.shader.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(self.shader,'matModel');self.shader.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(self.shader,'matNormal')
            self.player=LivingScene(include_willow=False,combat=True,fragment_shader='rockery.fs')
            names=('eyePosition','time','inspection','opacity','emission','surfaceKind','lampCount','lamps','fieldOrigin','fieldSize','fieldAtlas')
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in names} for s in (self.shader,self.player.skin)}
            self.field=pr.load_texture(str(KIT/'rock_field.png'));pr.set_texture_filter(self.field,pr.TEXTURE_FILTER_BILINEAR)
            for name in self.manifest['models']:self.load(name,KIT/(name+'.glb'))
            for model in list(self.models.values())+[self.player.player]:
                for i in range(model.materialCount):model.materials[i].maps[pr.MATERIAL_MAP_NORMAL].texture=self.field
            for s in (self.shader,self.player.skin):s.locs[pr.SHADER_LOC_MAP_NORMAL]=pr.get_shader_location(s,'rockField')
            self.raw=pr.load_render_texture(WIDTH,HEIGHT);self.frame=pr.load_render_texture(WIDTH,HEIGHT)
            self.post=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders'/'temple_interior_post.fs'))
            pr.set_shader_value(self.post,pr.get_shader_location(self.post,'resolution'),pr.ffi.new('float[]',[WIDTH,HEIGHT]),pr.SHADER_UNIFORM_VEC2)
            self.sky=Sky();im=pr.gen_image_gradient_radial(32,32,0.,pr.WHITE,pr.BLANK);self.smoke=pr.load_texture_from_image(im);pr.unload_image(im)
        except Exception:self.close();raise

    def environment(self,cam,clock,inspection):
        for s in (self.shader,self.player.skin):
            for name,value in (('eyePosition',(cam.position.x,cam.position.y,cam.position.z)),('time',clock),('inspection',float(inspection)),('opacity',1.),('emission',0.),('surfaceKind',0.),
                 ('fieldOrigin',self.field_info['origin']),('fieldSize',self.field_info['size']),('fieldAtlas',self.field_info['atlas']+[self.field_info['step']])):self.uniform(s,name,value)
            self.uniform(s,'lampCount',len(LIGHTS),'int');pr.set_shader_value_v(s,self.locations[s.id]['lamps'],pr.ffi.new('float[]',[v for p in LIGHTS for v in p]),pr.SHADER_UNIFORM_VEC3,len(LIGHTS))

    def render(self,e,clock,inspection=False,override=None,show_player=True,encounters=False):
        if override:cam=override
        else:
            e.shot,eye,target,fov=self.director.select(e);cam=camera(eye,target,fov)
        self.environment(cam,clock,inspection)
        pr.begin_texture_mode(self.raw);pr.clear_background(pr.Color(24,33,36,255))
        fog=pr.Color(*(tuple((76,89,85)) if inspection else (28,38,42)),255)
        self.sky.draw(cam,SimpleNamespace(distance=0,arrival_station=1485.75,elapsed=clock,dusk=.18 if inspection else .78),fog,WIDTH,HEIGHT)
        pr.begin_mode_3d(cam)
        for name in ('garden_floor','garden_walls','garden_roofs','pavilion','garden_props','garden_inscriptions'):self.draw(name)
        self.uniform(self.shader,'surfaceKind',4.);self.draw('high_walk')
        self.uniform(self.shader,'surfaceKind',3.);self.draw('stone_paths')
        self.uniform(self.shader,'surfaceKind',1.)
        for i in range(6):self.draw('taihu_rockery_'+str(i))
        self.uniform(self.shader,'surfaceKind',0.);pr.rl.rlDisableBackfaceCulling();self.draw('garden_plants');pr.rl.rlEnableBackfaceCulling()
        self.uniform(self.shader,'surfaceKind',2.);self.draw('garden_water');self.uniform(self.shader,'surfaceKind',0.)
        self.uniform(self.shader,'emission',1.);self.draw('garden_lamps');self.uniform(self.shader,'emission',0.)
        if show_player:
            pr.draw_cylinder_ex(pr.Vector3(e.x,e.height+.013,e.z),pr.Vector3(e.x,e.height+.016,e.z),.24,.24,24,pr.Color(4,9,11,95))
            clip=e.clip if e.clip in self.player.clips else 'idle';phase=e.phase if clip in ('walk','run','walk_back') else clock if clip.startswith('turn') else clock/2
            self.player.pose(clip,phase,self.player_pose_dt());pr.draw_model_ex(self.player.player,pr.Vector3(e.x,e.height+.01,e.z),pr.Vector3(0,1,0),180-math.degrees(e.yaw),pr.Vector3(PLAYER_SCALE,PLAYER_SCALE,PLAYER_SCALE),pr.WHITE)
            self.register_player_selection((e.x,e.height+.01,e.z),PLAYER_SCALE,180-math.degrees(e.yaw))
        pr.rl.rlDisableDepthMask()
        for x,y,z in LIGHTS:pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y-.03,z),.58,pr.Color(233,174,80,18))
        for i in range(40):
            x=math.sin(i*19.7)*15;z=math.cos(i*38.9)*25;y=.45+(i*.71+clock*.008)%5
            pr.draw_billboard(cam,self.smoke,pr.Vector3(x,y,z),.017,pr.Color(149,171,165,36))
        pr.rl.rlEnableDepthMask()
        if encounters:
            for area in ENCOUNTERS:
                x,y,z=area['center'];pr.draw_cylinder_wires(pr.Vector3(x,y+.03,z),area['radius'],area['radius'],.035,40,pr.Color(199,146,69,230))
                for xx,yy,zz in area['spawns']:pr.draw_sphere_wires(pr.Vector3(xx,yy+.9,zz),.25,5,8,pr.Color(224,134,103,255))
        pr.end_mode_3d();pr.end_texture_mode();pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK);pr.begin_shader_mode(self.post)
        pr.draw_texture_pro(self.raw.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode();return cam

    def close(self):
        super().close()
        if self.field:pr.unload_texture(self.field);self.field=None

def run(review=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,720,'Temple / The Hollow Garden');pr.set_target_fps(0 if review else 60);scene=None;selection=None
    try:
        before=time.perf_counter();scene=Rockery();startup=time.perf_counter()-before;e=Explorer()
        if review:return review_scene(scene,e,startup)
        from codex_selection import SelectionSession
        selection=SelectionSession('rockery',__file__);scene.codex_selection=selection
        pr.set_exit_key(pr.KEY_NULL);selected_camera=None
        clock=0.;inspection=False;manual=None;free=False;eye=None;yaw=0.;pitch=0.;help_visible=True;show_player=True;encounters=False;plan=False
        while not pr.window_should_close():
            was_selecting=selection.enabled
            if selection.handle_keys():break
            blocked=was_selecting or selection.enabled
            scene._codex_frame_paused=blocked
            dt=min(pr.get_frame_time(),.05)
            if blocked:
                override=selected_camera
            else:
                clock+=dt
                if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
                if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
                if pr.is_key_pressed(pr.KEY_TAB):show_player=not show_player
                if pr.is_key_pressed(pr.KEY_F3):encounters=not encounters
                if pr.is_key_pressed(pr.KEY_M):plan=not plan
                if pr.is_key_pressed(pr.KEY_HOME):e=Explorer();manual=None;free=False;pr.enable_cursor()
                if pr.is_key_pressed(pr.KEY_ZERO):manual=None;free=False;pr.enable_cursor()
                for i in range(9):
                    if pr.is_key_pressed(pr.KEY_ONE+i):manual=i;free=False;pr.enable_cursor()
                for key,step in ((pr.KEY_LEFT_BRACKET,-1),(pr.KEY_RIGHT_BRACKET,1)):
                    if pr.is_key_pressed(key):manual=((manual if manual is not None else e.shot)+step)%len(SHOTS);free=False;pr.enable_cursor()
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
            selection.begin_frame()
            selected_camera=scene.render(e,clock,inspection,override,show_player,encounters)
            pr.begin_drawing();pr.clear_background(pr.BLACK);w,h=pr.get_screen_width(),pr.get_screen_height()
            pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
            if help_visible:
                pr.draw_rectangle(0,h-52,w,52,pr.Color(10,16,18,222))
                pr.draw_text('W/S move  A/D turn  Shift run  1-9 or [ ] cameras  0 auto  F free look  L daylight  M plan',18,h-42,16,pr.Color(211,208,183,255))
                pr.draw_text('Free: mouse + WASD, Q/E height | F3 encounter study | Tab player | H help | Home reset | F8 select | F12 capture',18,h-21,14,pr.Color(153,173,166,255))
                pr.draw_text('Free camera' if free else SHOTS[manual if manual is not None else e.shot]['name'],19,18,18,pr.Color(211,208,183,255))
            if plan and not selection.enabled:draw_plan(e,w,h,encounters)
            selection.present(selected_camera,(0,0,w,h),{'world':'rockery','phase':'exploration','clock':clock,'player':{'position':[e.x,e.height,e.z],'yaw':e.yaw,'clip':e.clip},'shot':e.shot,'free_camera':free})
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                out=ROOT/'artifacts'/'rockery';out.mkdir(parents=True,exist_ok=True);snapshot(scene.frame,out/('capture-'+time.strftime('%Y%m%d-%H%M%S')+'.png'))
    finally:
        if selection:selection.close()
        pr.enable_cursor()
        if scene:scene.close()
        pr.close_window()

def draw_plan(e,w,h,encounters=False):
    left=w-350;top=70;scale=5.2
    pr.draw_rectangle(left-12,top-32,350,360,pr.Color(11,20,23,240));pr.draw_text('ROCKERY STUDY / M to close',left,top-23,14,pr.Color(205,205,180,255))
    def point(x,z):return pr.Vector2(left+165+x*scale,top+155+z*scale)
    for na,nb,r,roof in EDGES:
        a,b=NODES[na],NODES[nb];path=edge_path(na,nb)
        for (_,p),(_,q) in zip(path,path[1:]):
            pr.draw_line_ex(point(p[0],p[2]),point(q[0],q[2]),3,pr.Color(206,167,101,255) if max(a[1],b[1])>.2 else pr.Color(111,155,146,255))
    for name,x,z,rx,rz,y,roof in ROOMS:
        p=point(x,z);pr.draw_circle_lines(int(p.x),int(p.y),min(rx,rz)*scale,pr.Color(111,155,146,255))
    if encounters:
        for i,area in enumerate(ENCOUNTERS):
            x,y,z=area['center'];p=point(x,z)
            pr.draw_circle_lines(int(p.x),int(p.y),max(4,area['radius']*scale),pr.Color(230,164,82,255))
            pr.draw_text(str(i+1),int(p.x)+5,int(p.y)-5,12,pr.Color(238,187,122,255))
    p=point(e.x,e.z);pr.draw_circle_v(p,4,pr.Color(245,217,157,255))
    pr.draw_line_ex(p,point(e.x+math.sin(e.yaw)*1.5,e.z-math.cos(e.yaw)*1.5),2,pr.WHITE)
    pr.draw_text('Jade: lower paths   Ochre: upper route',left,top+308,13,pr.Color(205,205,180,255))

def review_scene(scene,e,startup):
    out=ROOT/'artifacts'/'rockery';out.mkdir(parents=True,exist_ok=True)
    positions=[NODES[n] for n in ('gate','throat','fork','reveal','fern','grotto','east_bend','bridge_mid','court','stair_east','stair_west','north','window')]
    from g_rockery import edge_height
    for index,na,nb,t in ((9,'east_bend','stair_east',.40),(10,'fern','stair_west',.35)):
        a,b=NODES[na],NODES[nb];p=edge_point(na,nb,t);positions[index]=(p[0],edge_height(a,b,t),p[2])
    samples=[(s['name'],s['eye'],s['target'],s['fov'],False,positions[i]) for i,s in enumerate(SHOTS[:13])]
    samples.extend((('Garden from above',(26,23,32),(0,1.6,-1),61,True,NODES['reveal']),
        ('The open court',(4.8,2.4,-18.8),(-1.5,1.8,-23),74,False,NODES['court']),
        ('Limestone daylight',(-3,3,5.6),(1.3,1.4,1.5),75,True,NODES['reveal'])))
    sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*8),(14,22,24));labels=ImageDraw.Draw(sheet)
    for i,(name,eye,target,fov,inspection,pos) in enumerate(samples):
        e.x,e.floor,e.z=pos;e.height=e.floor;scene.render(e,18.,inspection,camera(eye,target,fov),i<13)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(scene.frame,dest)
        x=i%2*WIDTH;y=i//2*(HEIGHT+25);sheet.paste(Image.open(dest).convert('RGB'),(x,y));labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(215,213,186))
    sheet.save(out/'rockery-review.png')
    stair_views=(
        ('Eastern ascent',(13,1.55,-4.7),(15,2.2,1),72,'east_bend','stair_east',.55),
        ('Western ascent',(-13.1,1.55,3.4),(-15,2.4,7),72,'fern','stair_west',.55),
        ('Eastern landing',SHOTS[9]['eye'],SHOTS[9]['target'],76,'east_bend','stair_east',.40),
        ('Western landing',SHOTS[10]['eye'],SHOTS[10]['target'],76,'fern','stair_west',.35),
    )
    stair_sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*3),(14,22,24));stair_labels=ImageDraw.Draw(stair_sheet)
    for i,(name,eye,target,fov,na,nb,t) in enumerate(stair_views):
        a,b=NODES[na],NODES[nb];p,d=edge_frame(na,nb,t);e.x,e.z=p[0],p[2]
        e.floor=edge_height(a,b,t);e.height=e.floor;e.yaw=math.atan2(d[0],-d[1])
        scene.render(e,18.,True,camera(eye,target,fov),True)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(scene.frame,dest)
        x=i%2*WIDTH;y=i//2*(HEIGHT+25);stair_sheet.paste(Image.open(dest).convert('RGB'),(x,y))
        stair_labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(215,213,186))
    for i,(name,shot,node) in enumerate((('Upper corridor daylight',SHOTS[7],'bridge_mid'),('The rounded western bend',SHOTS[22],'bridge_west')),start=4):
        e.x,e.floor,e.z=NODES[node];e.height=e.floor
        if i==5:
            p=edge_point('bridge_west','stair_west',.55);e.x,e.z=p[0],p[2]
            e.floor=edge_height(NODES['bridge_west'],NODES['stair_west'],.55);e.height=e.floor
        scene.render(e,18.,True,camera(shot['eye'],shot['target'],shot['fov']),True)
        dest=out/(name.lower().replace(' ','-')+'.png');snapshot(scene.frame,dest)
        x=i%2*WIDTH;y=i//2*(HEIGHT+25);stair_sheet.paste(Image.open(dest).convert('RGB'),(x,y))
        stair_labels.text((x+8,y+HEIGHT+5),name.upper(),fill=(215,213,186))
    stair_sheet.save(out/'carved-stairs-review.png')
    # Exercise the design overlays in the native renderer as well as the scene.
    study=pr.load_render_texture(1280,720)
    try:
        e.x,e.floor,e.z=NODES['reveal'];e.height=e.floor
        scene.render(e,18.,False,camera((-3,3,5.6),(1.3,1.4,1.5),75),True,True)
        pr.begin_texture_mode(study);pr.clear_background(pr.BLACK)
        pr.draw_texture_pro(scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,1280,720),pr.Vector2(0,0),0,pr.WHITE)
        draw_plan(e,1280,720,True)
        pr.draw_rectangle(0,668,1280,52,pr.Color(10,16,18,230))
        pr.draw_text('THE HOLLOW GARDEN / potential encounter areas',20,678,20,pr.Color(220,207,173,255))
        pr.draw_text('No enemies active. M: route plan. F3: encounter study.',20,703,13,pr.Color(168,189,178,255))
        pr.end_texture_mode();snapshot(study,out/'encounter-study.png')
    finally:pr.unload_render_texture(study)
    frames=[];timings=[];zones=set();reports=[]
    for title,route in REVIEW_ROUTES:
        e=Explorer();e.x,e.floor,e.z=NODES[route[0]];e.height=e.floor;steps=0;maxheight=e.floor;uncovered=[]
        scene.director.current=0
        for x,height,z in review_points(route)[1:]:
            name=(x,height,z)
            for _ in range(800):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.11:break
                e.yaw=math.atan2(dx,-dz);distance=e.tick(.05,1);steps+=1;maxheight=max(maxheight,e.floor)
                if distance<.00001:raise AssertionError(('Blocked route',title,name,e.x,e.floor,e.z))
                if steps%12==0:
                    before=time.perf_counter();scene.render(e,18+steps*.05);zones.add(e.shot)
                    if not scene.director.last_clear:uncovered.append((e.x,e.floor,e.z))
                    im=pr.load_image_from_texture(scene.frame.texture);pr.image_flip_vertical(im)
                    if title in ('main','upper_crossing'):frames.append(Image.frombytes('RGBA',(WIDTH,HEIGHT),bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4))).convert('RGB'))
                    pr.unload_image(im);timings.append((time.perf_counter()-before)*1000)
            else:raise AssertionError(('Unreachable waypoint',title,name))
        reports.append(dict(route=title,final=(e.x,e.floor,e.z),max_height=maxheight,uncovered_camera_samples=uncovered))
    if frames:frames[0].save(out/'rockery-walkthrough.gif',save_all=True,append_images=frames[1:],duration=90,loop=0,optimize=True)
    report=dict(audio='No audio device opened',startup_seconds=startup,frames=len(frames),camera_zones=sorted(zones),
        median_frame_and_readback_ms=statistics.median(timings),triangles=scene.manifest['total_triangles'],enemy_count=0,routes=reports)
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',action='store_true');run(parser.parse_args().review)
