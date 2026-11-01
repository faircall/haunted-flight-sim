"""Silent, interactive animation and proportion review for the Chorus figure."""
from dataclasses import dataclass
import math

from chorus_grasper_animation import GAITS,CLIP_SECONDS,BRISK_WALK_SPEED
from g_huxin_moon import PLAYER_SCALE

WIDTH,HEIGHT=1280,820
VIEWS={'front':(0.,7.),'side':(90.,7.),'back':(180.,7.),'three-quarter':(40.,12.)}


@dataclass
class ReviewState:
    mode:str='walk'
    cycles:float=0.
    playing:bool=True
    speed:float=1.
    azimuth:float=40.
    elevation:float=12.
    zoom:float=39.
    portrait:bool=False
    ground:bool=True
    neutral:bool=True

    @property
    def phase(self):return self.cycles%1.
    @property
    def clip(self):return 'enemy_idle' if self.mode=='idle' else 'enemy_walk'
    @property
    def period(self):
        if self.clip in GAITS:
            gait=GAITS[self.clip];speed=BRISK_WALK_SPEED if self.mode=='brisk' else gait['speed']
            return gait['stride']*PLAYER_SCALE/speed
        return CLIP_SECONDS[self.clip]
    def advance(self,dt):
        if self.playing:self.cycles+=max(0.,min(.1,float(dt)))*self.speed/self.period
    def action(self,name):
        if name.startswith('clip:'):
            mode=name[5:]
            if mode not in ('idle','walk','brisk'):raise ValueError('Unknown figure mode')
            self.mode=mode;self.cycles=0.
        elif name.startswith('view:'):self.azimuth,self.elevation=VIEWS[name[5:]]
        elif name.startswith('speed:'):self.speed=float(name[6:])
        elif name=='play':self.playing=not self.playing
        elif name=='previous':self.playing=False;self.cycles-=.017/CLIP_SECONDS[self.clip]
        elif name=='next':self.playing=False;self.cycles+=.017/CLIP_SECONDS[self.clip]
        elif name=='portrait':self.portrait=not self.portrait
        elif name=='ground':self.ground=not self.ground
        elif name=='light':self.neutral=not self.neutral
        elif name=='reset':self.cycles=0.;self.playing=False


def controls(state):
    buttons=[]
    def row(y,items):
        x=16
        for action,label,width,active in items:
            buttons.append((action,label,(x,y,width,30),active));x+=width+6
    row(48,[(f'clip:{name}',title,width,state.mode==name) for name,title,width in
            (('idle','1 Idle',100),('walk','2 Walk',100),('brisk','3 Brisk walk',145))]+[
        ('play','Pause' if state.playing else 'Play',78,state.playing),('previous','< Frame',90,False),
        ('next','Frame >',90,False),('reset','Reset',75,False),('portrait','Portrait [P]',115,state.portrait),
        ('light','Neutral light' if state.neutral else 'Moonlight',130,state.neutral)])
    row(85,[(f'view:{name}',label,112,(state.azimuth,state.elevation)==VIEWS[name]) for name,label in
            (('front','Front'),('side','Side'),('back','Back'),('three-quarter','Three-quarter'))]+[
        (f'speed:{value}',f'{value:g}x',65,state.speed==value) for value in (.25,.5,1.,2.)]+[
        ('ground','Moving ground',145,state.ground)])
    return buttons


def inside(rect,x,y):return rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3]


class StageReview:
    def __init__(self,pr):
        from g_temple_living import LivingScene
        self.pr=pr;self.state=ReviewState();self.players=[];self.targets=[]
        try:
            self.players.append(LivingScene(include_willow=False,combat=True))
            self.players.append(LivingScene(include_willow=False,actor='chorus_grasper'))
            for _ in self.players:
                target=pr.load_render_texture(304,285);pr.set_texture_filter(target.texture,pr.TEXTURE_FILTER_POINT);self.targets.append(target)
        except Exception:
            self.close();raise

    def camera(self):
        p=self.pr;s=self.state;a,e=math.radians(s.azimuth),math.radians(s.elevation)
        height=22. if s.portrait else 13.8;span=16. if s.portrait else s.zoom
        return p.Camera3D(p.Vector3(80*math.sin(a)*math.cos(e),height+80*math.sin(e),80*math.cos(a)*math.cos(e)),
                          p.Vector3(0,height,0),p.Vector3(0,1,0),span,p.CAMERA_ORTHOGRAPHIC)

    def update(self,dt):
        p=self.pr;s=self.state
        for key,name in ((p.KEY_ONE,'clip:idle'),(p.KEY_TWO,'clip:walk'),(p.KEY_THREE,'clip:brisk'),
                         (p.KEY_SPACE,'play'),(p.KEY_LEFT,'previous'),(p.KEY_RIGHT,'next'),
                         (p.KEY_HOME,'reset'),(p.KEY_P,'portrait'),(p.KEY_L,'light')):
            if p.is_key_pressed(key):s.action(name)
        mouse=p.get_mouse_position()
        if p.is_mouse_button_pressed(p.MOUSE_BUTTON_LEFT):
            for action,_,rect,_ in controls(s):
                if inside(rect,mouse.x,mouse.y):s.action(action);break
            if inside((24,746,1232,20),mouse.x,mouse.y):
                s.playing=False;s.cycles=max(0.,min(.999,(mouse.x-24)/1232))
        if 130<mouse.y<720:
            if p.is_mouse_button_down(p.MOUSE_BUTTON_RIGHT):
                delta=p.get_mouse_delta();s.azimuth=(s.azimuth-delta.x*.4)%360;s.elevation=max(-5.,min(65.,s.elevation+delta.y*.25))
            if not s.portrait:s.zoom=max(30.,min(75.,s.zoom-p.get_mouse_wheel_move()*2))
        s.advance(dt)

    def draw_model(self,rig,target,is_figure):
        p=self.pr;s=self.state;cam=self.camera()
        clip=s.clip if is_figure else 'idle'
        phase=s.phase if is_figure else s.cycles*s.period/2.
        rig.environment(s.cycles*s.period,s.neutral,[]);rig.pose(clip,phase)
        # Keep the ink-dark clothing readable when inspecting the silhouette.
        p.begin_texture_mode(target);p.clear_background(p.Color(53,62,63,255));p.begin_mode_3d(cam)
        p.draw_plane(p.Vector3(0,-.04,0),p.Vector2(160,160),p.Color(43,53,55,255))
        travel=s.cycles*GAITS[s.clip]['stride'] if is_figure and s.ground and s.clip in GAITS else 0.
        for n in range(-12,13):
            color=p.Color(62,74,75,255);z=n*5-travel%5
            p.draw_line_3d(p.Vector3(-60,0,z),p.Vector3(60,0,z),color)
            p.draw_line_3d(p.Vector3(n*5,0,-60),p.Vector3(n*5,0,60),color)
        rig.yaw=0.;rig.draw_player(0,0,0);p.end_mode_3d();p.end_texture_mode()

    def draw(self):
        p=self.pr;s=self.state
        for i,(rig,target) in enumerate(zip(self.players,self.targets)):self.draw_model(rig,target,bool(i))
        p.begin_drawing();p.clear_background(p.Color(12,18,24,255))
        p.draw_text('THE CHORUS / FIGURE STUDY',20,12,23,p.Color(224,233,231,255))
        p.draw_text('Right-drag to orbit  |  wheel to zoom  |  P portrait',760,20,14,p.Color(148,170,176,255))
        for _,title,rect,active in controls(s):
            p.draw_rectangle_rec(p.Rectangle(*rect),p.Color(54,105,105,255) if active else p.Color(34,46,56,255))
            p.draw_text(title,int(rect[0]+7),int(rect[1]+8),14,p.Color(220,230,228,255))
        for i,(target,label) in enumerate(zip(self.targets,('PLAYER / SCALE','CHORUS FIGURE'))):
            x=16+i*624;p.draw_text(label,x+5,123,18,p.Color(226,214,171,255))
            p.draw_texture_pro(target.texture,p.Rectangle(0,0,304,-285),p.Rectangle(x,147,608,570),p.Vector2(0,0),0,p.WHITE)
        p.draw_rectangle(24,746,1232,15,p.Color(34,47,55,255));p.draw_rectangle(24,746,int(1232*s.phase),15,p.Color(67,137,139,255))
        p.draw_line(int(24+1232*s.phase),740,int(24+1232*s.phase),768,p.Color(237,205,148,255))
        title='BRISK WALK' if s.mode=='brisk' else s.mode.upper()
        p.draw_text(f'{title}   {s.phase*100:5.1f}% of cycle   {s.speed:g}x   {s.period:.2f}s per cycle',24,778,17,p.Color(210,225,226,255))
        p.draw_text('Space pause  |  arrows step  |  click timeline  |  Esc exit',745,780,14,p.Color(148,170,176,255));p.end_drawing()

    def close(self):
        for target in self.targets:self.pr.unload_render_texture(target)
        for rig in self.players:rig.close()
        self.targets.clear();self.players.clear()


def run():
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
    import pyray as pr
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'The Chorus / Figure study');pr.set_target_fps(60)
    viewer=None
    try:
        viewer=StageReview(pr)
        while not pr.window_should_close():viewer.update(pr.get_frame_time());viewer.draw()
    finally:
        if viewer:viewer.close()
        pr.close_window()


if __name__=='__main__':run()
