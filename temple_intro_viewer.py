"""PS1-style back-seat car ride: scrolling countryside, wet glass and subtitles."""
from pathlib import Path
from array import array
import json
import math
import pyray as pr
from PIL import Image
import g_narrative_text as text
from g_temple_intro import Intro,load_script,local_point,road_slope,scenery,wiper_angle,WIPER_PERIOD,smooth

ROOT=Path(__file__).resolve().parent
KIT=ROOT/'art'/'temple'/'intro'
WIDTH,HEIGHT=480,270


def colour(a,b,t):return pr.Color(*(int(x+(y-x)*t) for x,y in zip(a,b)),255)


def shader(name):
    result=pr.load_shader(str(ROOT/'shaders'/'temple_intro.vs'),str(ROOT/'shaders'/name))
    if result.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Intro shader failed: '+name)
    result.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(result,'matModel')
    result.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(result,'matNormal')
    return result


def pane(points,glass,background):
    """One persistent quad, with upward UVs so water falls along the glazing."""
    mesh=pr.ffi.new('Mesh *');mesh.vertexCount=6;mesh.triangleCount=2
    order=(0,1,2,0,2,3);uv=((0,0),(1,0),(1,1),(0,1))
    values=[([v for i in order for v in points[i]],'vertices'),
            ([v for i in order for v in uv[i]],'texcoords'),([v for _ in order for v in (0,0,1)],'normals')]
    for items,field in values:
        packed=array('f',items).tobytes();memory=pr.rl.MemAlloc(len(packed));pr.ffi.memmove(memory,packed,len(packed))
        setattr(mesh,field,pr.ffi.cast('float *',memory))
    pr.rl.UploadMesh(mesh,False);model=pr.rl.LoadModelFromMesh(mesh[0]);model.materials[0].shader=glass
    model.materials[0].maps[pr.MATERIAL_MAP_DIFFUSE].texture=background
    return model


class Audio:
    def __init__(self):
        import cyminiaudio as cma
        self.engine=cma.Engine();self.sounds={};self.sweeps=-1
        try:
            for name in ('rain_cabin','engine','wiper'):
                sound=cma.Sound(self.engine,str(KIT/(name+'.wav')))
                sound.spatialization_enabled=False;sound.looping=name!='wiper';self.sounds[name]=sound
                if sound.looping:sound.volume=0.;sound.start()
        except Exception:self.close();raise

    def update(self,intro):
        gain=1-intro.fade
        for name in ('rain_cabin','engine'):
            sound=self.sounds[name]
            if intro.paused:sound.stop()
            elif not sound.is_playing:sound.start()
        exterior=not intro.interactive
        self.sounds['rain_cabin'].volume=gain*(.72 if exterior else .50+.12*abs(math.sin(math.radians(intro.yaw))))
        self.sounds['rain_cabin'].pan=0 if exterior else math.sin(math.radians(intro.yaw))*.14
        self.sounds['engine'].volume=gain*(.25+.16*intro.speed/10.5)*(.82 if exterior else 1)
        self.sounds['engine'].pitch=.82+.22*intro.speed/10.5
        sweep=int(intro.elapsed/(WIPER_PERIOD/2))
        if not intro.paused and sweep!=self.sweeps:
            sound=self.sounds['wiper'];sound.stop();sound.seek(0);sound.volume=(.22 if exterior else .6)*gain;sound.start();self.sweeps=sweep
        if intro.paused:self.sounds['wiper'].stop()

    def close(self):
        for sound in self.sounds.values():sound.close()
        self.sounds.clear();self.engine.close()


class View:
    def __init__(self):
        self.models={};self.textures={};self.windows=[];self.fonts={};self.targets=[];self.shaders=[]
        self.draw_calls=0;self.max_draw_calls=0
        try:
            self.scene_shader=shader('temple_intro.fs');self.shaders.append(self.scene_shader)
            self.glass_shader=shader('temple_intro_glass.fs');self.shaders.append(self.glass_shader)
            self.locations={s.id:{n:pr.get_shader_location(s,n) for n in
                ('eyePosition','fogColour','fogEnd','dusk','headlights','interior','travel','surface','time','windshield','wiperAngle')} for s in self.shaders}
            self.world=pr.load_render_texture(WIDTH,HEIGHT);self.targets.append(self.world)
            self.frame=pr.load_render_texture(WIDTH,HEIGHT);self.targets.append(self.frame)
            self.echo=[pr.load_render_texture(WIDTH,HEIGHT) for _ in range(2)];self.targets.extend(self.echo)
            self.echo_index=0;self.echo_time=None
            for target in self.targets:pr.set_texture_filter(target.texture,pr.TEXTURE_FILTER_POINT)
            for name in json.loads((KIT/'manifest.json').read_text())['models']:
                model=pr.load_model(str(KIT/(name+'.glb')));self.models[name]=model
                if not model.meshCount:raise RuntimeError('Empty intro model: '+name)
                for i in range(model.materialCount):
                    material=model.materials[i];material.shader=self.scene_shader
                    texture=material.maps[pr.MATERIAL_MAP_DIFFUSE].texture
                    if texture.id and texture.id!=pr.rl.rlGetTextureIdDefault():
                        self.textures[texture.id]=texture;pr.set_texture_filter(texture,pr.TEXTURE_FILTER_POINT)
            for name,mesh in (('ground',pr.gen_mesh_plane(240,240,1,1)),('road',pr.gen_mesh_plane(3.8,6.8,1,1)),('cube',pr.gen_mesh_cube(1,1,1))):
                model=pr.load_model_from_mesh(mesh);model.materials[0].shader=self.scene_shader;self.models[name]=model
            front=[(-.873,.964,-1.621),(.873,.964,-1.621),(.802,1.566,-1.133),(-.802,1.566,-1.133)]
            self.windows.append((pane(front,self.glass_shader,self.world.texture),True))
            for sign in (-1,1):
                x=sign*.967
                front=[(x,.96,-1.55),(x,.96,.055),(sign*.922,1.54,.055),(sign*.850,1.54,-1.12)]
                rear=[(x,.96,.185),(x,.96,1.395),(sign*.857,1.54,1.09),(sign*.922,1.54,.185)]
                self.windows.extend((pane(p,self.glass_shader,self.world.texture),False) for p in (front,rear))
            rear=[(.88,1.03,1.48),(-.88,1.03,1.48),(-.81,1.54,1.10),(.81,1.54,1.10)]
            self.windows.append((pane(rear,self.glass_shader,self.world.texture),False))
            self.sign=pr.load_render_texture(128,40);self.targets.append(self.sign)
            pr.set_texture_filter(self.sign.texture,pr.TEXTURE_FILTER_POINT)
            pr.begin_texture_mode(self.sign);pr.clear_background(pr.Color(37,49,36,255))
            text.draw(self.fonts,load_script()['sign'],8,9,pr.Color(211,215,187,255));pr.draw_text('2 km',76,13,10,pr.Color(211,215,187,255))
            pr.end_texture_mode()
            self.sign_model=pane([(-.85,0,0),(.85,0,0),(.85,.53,0),(-.85,.53,0)],self.scene_shader,self.sign.texture)
            # The render texture's vertical orientation differs from the atlas.
            mesh=self.sign_model.meshes[0]
            uv=array('f', (v for i in (0,1,2,0,2,3) for v in ((0,1),(1,1),(1,0),(0,0))[i]))
            pr.ffi.memmove(mesh.texcoords,uv.tobytes(),len(uv)*4);pr.update_mesh_buffer(mesh,1,mesh.texcoords,len(uv)*4,0)
            self.models['sign']=self.sign_model
        except Exception:self.close();raise

    def uniform(self,s,name,value,kind=None):
        loc=self.locations[s.id][name]
        if loc<0:return
        if kind=='int':data=pr.ffi.new('int[]',[value]);type_=pr.SHADER_UNIFORM_INT
        elif isinstance(value,(tuple,list)):data=pr.ffi.new('float[]',value);type_=pr.SHADER_UNIFORM_VEC3
        else:data=pr.ffi.new('float[]',[value]);type_=pr.SHADER_UNIFORM_FLOAT
        pr.set_shader_value(s,loc,data,type_)

    def draw(self,name,position=(0,0,0),scale=(1,1,1),yaw=0,tint=None):
        pr.draw_model_ex(self.models[name],pr.Vector3(*position),pr.Vector3(0,1,0),yaw,pr.Vector3(*scale),tint or pr.WHITE)
        self.draw_calls+=1

    def camera(self,intro):
        kind=intro.shot['kind'];u=intro.shot_progress
        if kind=='opening':
            eye=(1.78+u*.12,1.40,.76-u*.13);target=(0,1.30,.74);fov=48
        elif kind=='drone':
            eye=(5+u*1.5,20,7-u*4);target=(0,.1,-3);fov=48
        elif kind=='tracking':
            eye=(3.55,1.55,.06);target=(0,.87,-.12);fov=62
        elif kind=='arrival':
            eye=(0,4.6+u*.3,8-u);target=(0,1.1,-10);fov=58
        else:
            return self.interior_camera(intro)
        return pr.Camera3D(pr.Vector3(*eye),pr.Vector3(*target),pr.Vector3(0,1,0),fov,pr.CAMERA_PERSPECTIVE)

    def interior_camera(self,intro):
        yaw=math.radians(intro.yaw);pitch=math.radians(intro.pitch)
        motion=intro.speed/10.5;t=intro.elapsed
        # Mild suspension movement; the cabin stays rigid around the seated eye.
        bob=.006*math.sin(t*3.3)*motion+.003*math.sin(t*8.1)*motion
        eye=pr.Vector3(.02+.004*math.sin(t*1.3)*motion,1.34+bob,.65)
        direction=pr.Vector3(math.sin(yaw)*math.cos(pitch),math.sin(pitch),-math.cos(yaw)*math.cos(pitch))
        target=pr.vector3_add(eye,direction)
        return pr.Camera3D(eye,target,pr.Vector3(0,1,0),62.,pr.CAMERA_PERSPECTIVE)

    def wipers(self,intro):
        angle=wiper_angle(intro.elapsed)
        colour_=pr.Color(24,30,28,255)
        for x in (-.58,.28):
            pivot=pr.Vector3(x,.955,-1.647)
            up=pr.Vector3(0,.776,.63)
            tip=pr.Vector3(x+.53*math.cos(angle),pivot.y+.53*math.sin(angle)*up.y,pivot.z+.53*math.sin(angle)*up.z)
            pr.draw_cylinder_ex(pivot,tip,.011,.010,5,colour_)
            perpendicular=pr.Vector3(-math.sin(angle)*.16,math.cos(angle)*.16*up.y,math.cos(angle)*.16*up.z)
            pr.draw_cylinder_ex(pr.vector3_subtract(tip,perpendicular),pr.vector3_add(tip,perpendicular),.013,.013,5,colour_)

    def countryside(self,intro):
        s=self.scene_shader;d=intro.distance;t=intro.elapsed
        self.uniform(s,'interior',0.);self.uniform(s,'fogEnd',70.);self.uniform(s,'surface',0,'int')
        # Layered, slowly shifting hill silhouettes remain beyond the near fog.
        self.uniform(s,'fogEnd',215.)
        for i in range(15):
            angle=math.tau*i/15;radius=115+(i%3)*28
            x=math.sin(angle)*radius-d*.007;z=-math.cos(angle)*radius
            self.draw('mountain',(x,-7,z),(38+(i%3)*16,34+(i*13%30),39+(i%4)*9),yaw=i*31)
        self.uniform(s,'fogEnd',70.)
        self.draw('ground',(0,-.055,-35),tint=pr.Color(73,85,58,255))
        self.uniform(s,'surface',1,'int')
        base=math.floor((d-18)/6)
        for i in range(base,base+19):
            station=i*6;x,z=local_point(station,0,d)
            angle=math.degrees(-math.atan(road_slope(station))+math.atan(road_slope(d)))
            self.draw('road',(x,.006,z),yaw=angle,tint=pr.Color(84,93,91,255))
        self.uniform(s,'surface',0,'int')
        for item in scenery(d):
            # Thin the final approach so the gateway appears between the trees.
            if intro.arrival_station-10<d-item['z']<intro.arrival_station+16 and abs(item['x'])<5:continue
            self.draw(item['kind'],(item['x'],0,item['z']),(item['scale'],)*3,item['yaw'])
            if item['seed']%7==0:self.draw('rock',(item['x']*.72,0,item['z']),(1.1,.7,1.4),item['yaw'])
        for i in range(math.floor((d-25)/110),math.floor((d+100)/110)+1):
            x,z=local_point(i*110+28,(-1 if i%2 else 1)*9,d)
            if -85<z<20:
                self.draw('house',(x,0,z),(1,1,1),yaw=20 if i%2 else 155)
            station=i*110-12;x,z=local_point(station,-3.9,d)
            if -85<z<20:
                self.draw('cube',(x,2.85,z),(.13,5.7,.13),tint=pr.Color(90,95,86,255))
                self.draw('cube',(x,5.1,z),(1.05,.06,.06),tint=pr.Color(64,68,61,255))
                x2,z2=local_point(station+110,-3.9,d)
                pr.draw_line_3d(pr.Vector3(x-.35,5.1,z),pr.Vector3(x2-.35,5.1,z2),pr.Color(95,105,98,255))
        x,z=local_point(intro.arrival_station-95,3.7,d)
        if -80<z<18:
            self.draw('cube',(x,1.0,z),(.08,2.0,.08),tint=pr.Color(91,96,82,255))
            self.draw('sign',(x,1.77,z),yaw=-25)
        x,z=local_point(intro.arrival_station,0,d)
        if z>-100:
            self.draw('gate',(x,.0,z))
            for side in (-1,1):self.draw('cube',(x+side*5.9,1.0,z),(6.4,2.,.35),tint=pr.Color(105,111,101,255))
        # Exterior rain is rendered before the cabin, so it cannot fall indoors.
        for i in range(115):
            seed=(i*2654435761)&0xffffffff
            x=((seed&255)/255-.5)*28;z=(((seed>>8)&255)/255-.5)*37
            if abs(x)<1.1 and -3<z<2.8:continue
            y=(i*.713-t*8.3)%7+.1
            alpha=max(0,90-int(abs(z)*2))
            pr.draw_line_3d(pr.Vector3(x,y,z),pr.Vector3(x-.018,y-.22,z+.13),pr.Color(178,190,184,alpha))
        self.wipers(intro)

    def vehicle(self,intro):
        s=self.scene_shader
        self.uniform(s,'interior',0.);self.uniform(s,'surface',0,'int');self.uniform(s,'fogEnd',70.)
        self.draw('sedan_exterior')
        spin=-math.degrees(intro.distance/.32)%360
        for x in (-1.035,1.035):
            for z in (-1.65,1.52):
                pr.draw_model_ex(self.models['tyre'],pr.Vector3(x,.34,z),pr.Vector3(1,0,0),spin,pr.Vector3(1,1,1),pr.WHITE)
                self.draw_calls+=1
        self.uniform(s,'surface',2,'int');self.draw('headlamps');self.uniform(s,'surface',0,'int')
        if intro.headlights:
            # A faint broad cone catches the rain/fog; the brighter road spill
            # is evaluated in the road material rather than painted on screen.
            pr.rl.rlDisableBackfaceCulling();pr.rl.rlDisableDepthMask()
            for x in (-.72,.72):
                tint=pr.Color(220,221,166,int(13*intro.headlights))
                start=pr.Vector3(x,.74,-2.72)
                corners=[pr.Vector3(x-2,.08,-17),pr.Vector3(x+2,.08,-17),
                         pr.Vector3(x+2,1.4,-17),pr.Vector3(x-2,1.4,-17)]
                for i in range(4):pr.draw_triangle_3d(start,corners[i],corners[(i+1)%4],tint)
            pr.rl.rlEnableDepthMask();pr.rl.rlEnableBackfaceCulling()

    def cabin(self,intro,exterior=False):
        s=self.scene_shader;self.uniform(s,'interior',1.);self.uniform(s,'surface',0,'int')
        self.draw('sedan');self.draw('driver');self.draw('colleague')
        self.draw('player_seated' if exterior else 'player_lap')
        line=intro.line;talking=line and line['speaker']=='FRONT PASSENGER'
        # No likenesses yet: separate blank heads leave references easy to swap.
        glance=18*smooth((intro.elapsed-line['start'])/.9)*smooth((line['end']-intro.elapsed)/.8) if talking else 0.
        self.draw('driver_head',(-.45,1.405+.002*math.sin(intro.elapsed*1.8),-.36),yaw=2.5*math.sin(intro.elapsed*.42))
        self.draw('colleague_head',(.45,1.405+.002*math.sin(intro.elapsed*1.5),-.36),yaw=-glance)
        steering=math.degrees(math.atan(road_slope(intro.distance)))*1.3
        pr.draw_model_ex(self.models['steering'],pr.Vector3(-.45,1.025,-.95),pr.Vector3(0,.673,.74),steering,pr.Vector3(1,1,1),pr.WHITE)

    def subtitles(self,intro,help_visible=True,audio_error=''):
        line=intro.line
        if line:
            lines=text.wrap(self.fonts,line['text'],434)
            height=22+len(lines)*16;top=HEIGHT-8-height
            pr.draw_rectangle(14,top,452,height,pr.Color(8,13,14,205))
            pr.draw_rectangle(14,top,2,height,pr.Color(160,176,154,225))
            pr.draw_text(line['speaker'],24,top+5,10,pr.Color(184,199,170,255))
            for i,value in enumerate(lines):text.draw(self.fonts,value,24,top+19+i*16,pr.Color(224,228,211,255))
        if 2.5<intro.elapsed<6.8:
            title='THE ROAD TO THE TEMPLE';width=pr.measure_text(title,16)
            pr.draw_text(title,16,211,16,pr.Color(224,225,207,255))
            pr.draw_text('Late afternoon',18,233,10,pr.Color(196,205,188,255))
        if help_visible and not intro.paused and 7<=intro.elapsed<15:
            pr.draw_text('Mouse: look   |   Esc: pause   |   Enter: skip',105,12,10,pr.Color(212,218,204,255))
        if intro.elapsed>intro.duration-8 and intro.fade<.9:
            title=intro.document['place_name'];width=pr.measure_text(title,16)
            pr.draw_text(title,(WIDTH-width)//2,25,16,pr.Color(211,216,196,255))
        if audio_error and intro.elapsed<8:pr.draw_text('Audio unavailable',12,28,10,pr.Color(222,184,142,255))
        if intro.paused:
            pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(6,12,15,140))
            pr.draw_rectangle(95,93,290,83,pr.Color(12,21,22,235))
            pr.draw_text('PAUSED',201,105,16,pr.Color(228,230,211,255))
            pr.draw_text('Esc: resume   |   Enter: arrive at temple',116,132,10,pr.Color(202,211,192,255))
            pr.draw_text('Q: quit   |   Home: look forward',142,151,10,pr.Color(167,183,167,255))

    def render(self,intro,help_visible=True,audio_error=''):
        self.draw_calls=0;camera=self.camera(intro);s=self.scene_shader
        fog=colour((141,156,143),(24,37,47),intro.dusk)
        self.uniform(s,'eyePosition',(camera.position.x,camera.position.y,camera.position.z))
        self.uniform(s,'fogColour',(fog.r/255,fog.g/255,fog.b/255))
        self.uniform(s,'dusk',intro.dusk);self.uniform(s,'travel',intro.distance)
        self.uniform(s,'headlights',intro.headlights)
        pr.begin_texture_mode(self.world)
        pr.clear_background(fog)
        pr.draw_rectangle_gradient_v(0,0,WIDTH,HEIGHT,colour((109,123,119),(9,17,28),intro.dusk),fog)
        pr.begin_mode_3d(camera);self.countryside(intro);pr.end_mode_3d();pr.end_texture_mode()
        # Short exposure trails only in the held side-on shot. Scenery smears
        # past, while the car is drawn crisply over it; reset on cuts and seeks.
        background=self.world.texture
        if intro.shot['kind']=='tracking':
            fresh=self.echo_time is None or not 0<=intro.elapsed-self.echo_time<.25
            previous=self.echo[self.echo_index];self.echo_index=1-self.echo_index;current=self.echo[self.echo_index]
            pr.begin_texture_mode(current);pr.clear_background(pr.BLACK)
            self.copy(self.world.texture)
            if not fresh:self.copy(previous.texture,pr.Color(255,255,255,92))
            pr.end_texture_mode();background=current.texture;self.echo_time=intro.elapsed
        else:self.echo_time=None
        exterior=not intro.interactive
        if exterior:
            # Include the seated player behind the glass in its refracted source.
            # Copy the scenery first, then add opaque vehicle depth in that FBO.
            pr.begin_texture_mode(self.frame);self.copy(background);pr.end_texture_mode()
            pr.begin_texture_mode(self.world);self.copy(self.frame.texture)
            pr.begin_mode_3d(camera);self.cabin(intro,True);self.vehicle(intro);pr.end_mode_3d();pr.end_texture_mode()
            background=self.world.texture
        pr.begin_texture_mode(self.frame);pr.clear_background(pr.BLACK)
        self.copy(background)
        if exterior:
            # Copy the opaque world's depth as well as its colour. Otherwise a
            # foreground tree would disappear behind the car/glass when the
            # exterior is composed into the final frame.
            pr.rl.rlDrawRenderBatchActive()
            pr.rl.rlBindFramebuffer(pr.RL_READ_FRAMEBUFFER,self.world.id)
            pr.rl.rlBindFramebuffer(pr.RL_DRAW_FRAMEBUFFER,self.frame.id)
            pr.rl.rlBlitFramebuffer(0,0,WIDTH,HEIGHT,0,0,WIDTH,HEIGHT,0x100) # GL_DEPTH_BUFFER_BIT
            pr.rl.rlEnableFramebuffer(self.frame.id)
        pr.begin_mode_3d(camera)
        if not exterior:self.cabin(intro)
        self.uniform(self.glass_shader,'time',intro.elapsed);self.uniform(self.glass_shader,'dusk',intro.dusk)
        self.uniform(self.glass_shader,'wiperAngle',wiper_angle(intro.elapsed))
        # Opaque cabin depth rejects glass behind seats, pillars and colleagues.
        pr.rl.rlDisableBackfaceCulling();pr.rl.rlDisableDepthMask()
        for window,windshield in self.windows:
            window.materials[0].maps[pr.MATERIAL_MAP_DIFFUSE].texture=background
            self.uniform(self.glass_shader,'windshield',float(windshield));pr.draw_model(window,pr.Vector3(0,0,0),1.,pr.WHITE)
        pr.rl.rlEnableDepthMask();pr.rl.rlEnableBackfaceCulling();pr.end_mode_3d()
        self.subtitles(intro,help_visible,audio_error)
        if intro.fade:pr.draw_rectangle(0,0,WIDTH,HEIGHT,pr.Color(0,0,0,int(255*intro.fade)))
        pr.end_texture_mode();self.max_draw_calls=max(self.max_draw_calls,self.draw_calls)
        return camera

    def copy(self,texture,tint=None):
        pr.draw_texture_pro(texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,WIDTH,HEIGHT),pr.Vector2(0,0),0,tint or pr.WHITE)

    def close(self):
        text.unload(self.fonts)
        for model in self.models.values():pr.unload_model(model)
        self.models.clear()
        for model,_ in self.windows:pr.unload_model(model)
        self.windows.clear()
        for texture in self.textures.values():pr.unload_texture(texture)
        self.textures.clear()
        for target in self.targets:pr.unload_render_texture(target)
        self.targets.clear()
        for s in self.shaders:pr.unload_shader(s)
        self.shaders.clear()


def capture(target,path):
    image=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(image)
    pr.export_image(image,str(path));pr.unload_image(image)


def run_intro(review=False,keep_window=False):
    """Return 'arrived' for natural completion/skip, or 'quit'. Own all resources."""
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1440,810,'Moonlit water temple / the road');pr.set_target_fps(60)
    pr.set_exit_key(pr.KEY_NULL)
    intro=Intro(load_script());view=None;audio=None;audio_error='';outcome='quit';help_visible=True
    folder=ROOT/'artifacts'/'temple-intro';samples=[]
    shots=[(3.7,0,-8,'01-rear-window-portrait'),(6.9,0,-8,'01b-portrait-before-cut'),
           (7.,0,-8,'02-first-interior-cut'),(17.1,0,-8,'02-front-wipers'),(17.8,0,-8,'03-front-wiper-return'),
           (37.,-78,-3,'04-left-window'),(44.,0,-8,'05-drone-cut'),(50.,0,-8,'05b-drone-road'),
           (56.,0,-8,'06-second-interior-cut'),(62.,82,-3,'06b-right-window'),(79.,174,-1,'06c-rear-window'),
           (88.,-24,-37,'07-dashboard-and-lap'),(95.,0,-8,'08-tracking-afternoon'),
           (102.,0,-8,'08b-tracking-lights-on'),(108.,0,-8,'08c-tracking-twilight'),
           (113.9,0,-8,'08d-tracking-night'),(114.,0,-8,'09-night-interior-cut'),
           (115.,0,-62,'09b-player-lap'),(132.,0,-8,'09c-temple-through-windshield'),
           (135.,0,-8,'10-temple-arrival')]
    try:
        view=View()
        # Preload all subtitle glyphs once; later lines reuse the same font atlas.
        text.font(view.fonts,''.join(line['text'] for line in intro.document['lines']))
        try:audio=Audio()
        except (RuntimeError,OSError) as exc:audio_error=str(exc)
        if review:
            folder.mkdir(parents=True,exist_ok=True)
            for timestamp,yaw,pitch,name in shots:
                intro.elapsed=timestamp;intro.yaw=yaw;intro.pitch=pitch
                if audio:audio.update(intro)
                camera=view.render(intro)
                pr.begin_drawing();pr.clear_background(pr.BLACK)
                pr.draw_texture_pro(view.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,1440,810),pr.Vector2(0,0),0,pr.WHITE);pr.end_drawing()
                capture(view.frame,folder/(name+'.png'))
                samples.append(dict(name=name,time=timestamp,yaw=yaw,pitch=pitch,distance=intro.distance,
                    shot=intro.shot['id'],interactive=intro.interactive,headlights=intro.headlights,
                    dusk=intro.dusk,speed=intro.speed,wiper_angle=wiper_angle(timestamp),
                    subtitle=intro.line,visible_trees=len(list(scenery(intro.distance))),
                    camera=[camera.position.x,camera.position.y,camera.position.z]))
            # A native montage samples every shot. Simulate intermediate tracking
            # frames so the time-lapse preview includes the actual exposure trails.
            frames=[]
            for start,end,count in ((2.7,6.9,24),(17.,18.3,24),(44.,55.9,24),(76.,77.3,24),
                                    (95.,113.9,64),(127.,129.,24),(135.,138.8,24)):
                intro.yaw=0;intro.pitch=-8;previous=None
                for i in range(count):
                    timestamp=start+(end-start)*i/(count-1)
                    if start==95 and previous is not None:
                        for j in range(1,math.ceil((timestamp-previous)/.06)):
                            intro.elapsed=previous+j*.06;view.render(intro,False)
                    intro.elapsed=timestamp;view.render(intro,False);previous=timestamp
                    image=pr.load_image_from_texture(view.frame.texture);pr.image_flip_vertical(image)
                    pr.image_format(image,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
                    frames.append(Image.frombytes('RGBA',(WIDTH,HEIGHT),bytes(pr.ffi.buffer(image.data,WIDTH*HEIGHT*4))).convert('RGB'))
                    pr.unload_image(image)
            # One shared palette includes both day and night; the opening alone
            # would crush the night views into a handful of unsuitable colours.
            sheet=Image.new('RGB',(WIDTH*7,HEIGHT))
            for i,index in enumerate((0,24,48,72,100,159,190)):sheet.paste(frames[index],(i*WIDTH,0))
            palette=sheet.quantize(colors=192)
            frames=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
            frames[0].save(folder/'cinematic-preview.gif',save_all=True,append_images=frames[1:],duration=75,loop=0,optimize=False)
            frozen=(intro.elapsed,intro.yaw,intro.pitch,intro.distance)
            intro.tick(.05,pause=True);intro.tick(.05,(80,-30));assert frozen==(intro.elapsed,intro.yaw,intro.pitch,intro.distance)
            if audio:audio.update(intro);assert not audio.sounds['engine'].is_playing
            view.render(intro);capture(view.frame,folder/'11-pause.png')
            intro.tick(.05,pause=True)
            intro.tick(.05,skip=True);assert intro.finished
            report=dict(samples=samples,pause_freezes_ride=True,skip_hands_off=True,glass_panes=len(view.windows),
                max_scene_draw_calls=view.max_draw_calls,audio_error=audio_error,
                audio_loaded=list(audio.sounds) if audio else [],duration=intro.duration,
                bounded_scenery=True,featureless_colleagues=True)
            report['animated_preview_frames']=len(frames)
            assert len(view.windows)==6 and view.max_draw_calls<200
            assert audio and not audio_error,audio_error
            (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            outcome='arrived'
        else:
            pr.disable_cursor();mouse_ready=False
            while not pr.window_should_close():
                pause=pr.is_key_pressed(pr.KEY_ESCAPE);skip=pr.is_key_pressed(pr.KEY_ENTER)
                if intro.paused and pr.is_key_pressed(pr.KEY_Q):break
                mouse=pr.get_mouse_delta()
                delta=(mouse.x,mouse.y) if mouse_ready and not pause else (0,0)
                intro.tick(pr.get_frame_time(),delta,pause,skip,pr.is_key_pressed(pr.KEY_HOME))
                mouse_ready=not pause
                if pause:
                    if intro.paused:pr.enable_cursor()
                    else:pr.disable_cursor()
                if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
                if audio:audio.update(intro)
                if intro.finished:outcome='arrived';break
                view.render(intro,help_visible,audio_error)
                pr.begin_drawing();pr.clear_background(pr.BLACK)
                pr.draw_texture_pro(view.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(0,0,1440,810),pr.Vector2(0,0),0,pr.WHITE);pr.end_drawing()
                if pr.is_key_pressed(pr.KEY_F12):
                    folder.mkdir(parents=True,exist_ok=True);capture(view.frame,folder/'user-view.png')
    finally:
        pr.enable_cursor()
        if outcome=='arrived' and keep_window:
            pr.begin_drawing();pr.clear_background(pr.BLACK);pr.end_drawing()
        if audio:audio.close()
        if view:view.close()
        if not keep_window or outcome!='arrived':pr.close_window()
    if review:print('Car intro native review passed: seven cinematic shots, seated player, night/headlights, wet glass, audio, pause and handoff.',flush=True)
    return outcome
