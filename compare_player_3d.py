"""Synchronized, silent comparison of the game's original and refined player."""
from dataclasses import dataclass
import math
from pathlib import Path

from g_player_locomotion import SETTINGS, stride_for
from g_huxin_moon import PLAYER_SCALE

ROOT=Path(__file__).resolve().parent
VIEWS={'side':(90.,7.),'front':(0.,7.),'back':(180.,7.),'three-quarter':(40.,12.)}
CLIPS=('idle','walk','run','walk_back','turn_left','turn_right','aim')
SPEEDS=(.25,.5,1.,2.)


@dataclass
class CompareState:
    clip:str='walk'
    cycles:float=0.
    playing:bool=True
    speed:float=1.
    azimuth:float=90.
    elevation:float=7.
    zoom:float=39.
    ground_motion:bool=True
    compare_run_timing:bool=False

    @property
    def phase(self):return self.cycles%1.
    @property
    def period(self):
        gait='walk' if self.clip=='walk_back' else self.clip
        # Moon/Canals advance phase by distance with these actual move speeds;
        # the older animation viewer's source speed is not the gameplay speed.
        return SETTINGS[gait]['stride']*PLAYER_SCALE/(3.15 if gait=='run' else 1.55) if gait in SETTINGS else 2. if gait=='idle' else 1.
    def display_phase(self,sprint=False):
        if self.clip=='run' and sprint:
            return (self.cycles*SETTINGS['run']['stride']/stride_for('run','sprint'))%1.
        return self.phase
    def advance(self,dt):
        if self.playing:self.cycles+=max(0.,min(.1,float(dt)))*self.speed/self.period
    def action(self,name):
        if name.startswith('clip:'):self.clip=name[5:];self.cycles=0.
        elif name.startswith('view:'):self.azimuth,self.elevation=VIEWS[name[5:]]
        elif name.startswith('speed:'):self.speed=float(name[6:])
        elif name=='play':self.playing=not self.playing
        elif name=='prev':self.playing=False;self.cycles-=.017/(2. if self.clip=='idle' else 1.)
        elif name=='next':self.playing=False;self.cycles+=.017/(2. if self.clip=='idle' else 1.)
        elif name=='ground':self.ground_motion=not self.ground_motion
        elif name=='timing':self.compare_run_timing=not self.compare_run_timing
        elif name=='reset':self.cycles=0.;self.playing=False


def controls(s):
    rows=[]
    def row(y,items):
        x=16
        for name,title,width,active in items:
            rows.append((name,title,(x,y,width,30),active));x+=width+6
    row(48,[(f'clip:{name}',title,width,s.clip==name) for name,title,width in (
        ('idle','1 Idle',90),('walk','2 Walk',90),('run','3 Jog',90),('walk_back','4 Backward',112),
        ('turn_left','5 Turn left',112),('turn_right','6 Turn right',118),('aim','7 Aim',90))]+
        [('play','Pause' if s.playing else 'Play',74,s.playing),('prev','< Frame',84,False),('next','Frame >',84,False),('reset','Reset',70,False)])
    row(85,[(f'view:{name}',title,112,(s.azimuth,s.elevation)==VIEWS[name]) for name,title in (
        ('side','Side'),('front','Front'),('back','Back'),('three-quarter','Three-quarter'))]+
        [(f'speed:{value}',f'{value:g}x',65,s.speed==value) for value in SPEEDS]+
        [('ground','Moving ground',145,s.ground_motion),
         ('timing','Jog / sprint [T]',165,s.compare_run_timing)])
    return rows


def inside(rect,x,y):return rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3]


class CompareViewer:
    def __init__(self,pr):
        from g_temple_living import LivingScene
        self.pr=pr;self.state=CompareState();self.players=[];self.targets=[]
        try:
            for variant in ('original','refined'):
                self.players.append(LivingScene(include_willow=False,combat=True,variant=variant))
                target=pr.load_render_texture(304,285);pr.set_texture_filter(target.texture,pr.TEXTURE_FILTER_POINT);self.targets.append(target)
        except Exception:
            self.close();raise

    def camera(self):
        p=self.pr;s=self.state;a,e=math.radians(s.azimuth),math.radians(s.elevation)
        return p.Camera3D(p.Vector3(80*math.sin(a)*math.cos(e),14+80*math.sin(e),80*math.cos(a)*math.cos(e)),
                          p.Vector3(0,14,0),p.Vector3(0,1,0),s.zoom,p.CAMERA_ORTHOGRAPHIC)

    def update(self,dt):
        p=self.pr;s=self.state
        for key,name in ((p.KEY_ONE,'clip:idle'),(p.KEY_TWO,'clip:walk'),(p.KEY_THREE,'clip:run'),
                         (p.KEY_FOUR,'clip:walk_back'),(p.KEY_FIVE,'clip:turn_left'),(p.KEY_SIX,'clip:turn_right'),
                         (p.KEY_SEVEN,'clip:aim'),(p.KEY_SPACE,'play'),(p.KEY_LEFT,'prev'),(p.KEY_RIGHT,'next'),(p.KEY_HOME,'reset'),
                         (p.KEY_T,'timing')):
            if p.is_key_pressed(key):s.action(name)
        mouse=p.get_mouse_position()
        if p.is_mouse_button_pressed(p.MOUSE_BUTTON_LEFT):
            for name,_,rect,_ in controls(s):
                if inside(rect,mouse.x,mouse.y):s.action(name);break
            if inside((24,746,1232,20),mouse.x,mouse.y):s.playing=False;s.cycles=max(0.,min(.999,(mouse.x-24)/1232))
        if 130<mouse.y<720:
            if p.is_mouse_button_down(p.MOUSE_BUTTON_RIGHT):
                delta=p.get_mouse_delta();s.azimuth=(s.azimuth-delta.x*.4)%360;s.elevation=max(-5.,min(65.,s.elevation+delta.y*.25))
            s.zoom=max(30.,min(75.,s.zoom-p.get_mouse_wheel_move()*2))
        s.advance(dt)

    def scene(self,player,target):
        p=self.pr;s=self.state;cam=self.camera()
        sprint=s.compare_run_timing and player is self.players[0]
        player.use_improved_run=True;player.run_style='sprint' if sprint else 'jog'
        player.environment(0.,True,[]);player.pose(s.clip,s.display_phase(sprint))
        p.begin_texture_mode(target);p.clear_background(p.Color(23,32,39,255));p.begin_mode_3d(cam)
        p.draw_plane(p.Vector3(0,-.04,0),p.Vector2(160,160),p.Color(31,42,48,255))
        gait='walk' if s.clip=='walk_back' else s.clip
        travel=(s.cycles*SETTINGS[gait]['stride']*(-1 if s.clip=='walk_back' else 1)
                if s.ground_motion and gait in SETTINGS else 0.)
        for n in range(-12,13):
            color=p.Color(45,59,65,255);z=n*5-travel%5
            p.draw_line_3d(p.Vector3(-60,0,z),p.Vector3(60,0,z),color)
            p.draw_line_3d(p.Vector3(n*5,0,-60),p.Vector3(n*5,0,60),color)
        player.yaw=0.;player.draw_player(0,0,0)
        if s.clip=='aim':player.draw_pistol(0,0,0)
        p.end_mode_3d();p.end_texture_mode()

    def draw(self):
        p=self.pr;s=self.state
        for player,target in zip(self.players,self.targets):self.scene(player,target)
        p.begin_drawing();p.clear_background(p.Color(12,18,24,255))
        p.draw_text('PLAYER / SYNCHRONIZED COMPARISON',20,12,23,p.Color(224,233,231,255))
        p.draw_text('Both use the actual game cadence. Right-drag to orbit; wheel to zoom.',665,20,14,p.Color(148,170,176,255))
        for _,title,rect,active in controls(s):
            p.draw_rectangle_rec(p.Rectangle(*rect),p.Color(54,105,105,255) if active else p.Color(34,46,56,255))
            p.draw_text(title,int(rect[0]+7),int(rect[1]+8),14,p.Color(220,230,228,255))
        labels=('ORIGINAL MODEL / SPRINT','REBUILT MODEL / JOG') if s.compare_run_timing and s.clip=='run' else ('ORIGINAL','REBUILT PLAYER')
        for i,(target,label) in enumerate(zip(self.targets,labels)):
            x=16+i*624;p.draw_text(label,x+5,123,18,p.Color(226,214,171,255))
            p.draw_texture_pro(target.texture,p.Rectangle(0,0,304,-285),p.Rectangle(x,147,608,570),p.Vector2(0,0),0,p.WHITE)
        p.draw_rectangle(24,746,1232,15,p.Color(34,47,55,255));p.draw_rectangle(24,746,int(1232*s.phase),15,p.Color(67,137,139,255))
        p.draw_line(int(24+1232*s.phase),740,int(24+1232*s.phase),768,p.Color(237,205,148,255))
        p.draw_text(f'{"JOG" if s.clip=="run" else s.clip.upper()}   {s.phase*100:5.1f}% of cycle   {s.speed:g}x   {s.period:.2f}s per cycle',24,778,17,p.Color(210,225,226,255))
        p.draw_text('Space play/pause  |  arrows step  |  click timeline  |  Esc exit',744,780,14,p.Color(148,170,176,255))
        p.end_drawing()

    def close(self):
        for target in self.targets:self.pr.unload_render_texture(target)
        for player in self.players:player.close()
        self.targets.clear();self.players.clear()


def main():
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
    import pyray as pr
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1280,820,'Player / Compare motion');pr.set_target_fps(60)
    viewer=None
    try:
        viewer=CompareViewer(pr)
        while not pr.window_should_close():viewer.update(pr.get_frame_time());viewer.draw()
    finally:
        if viewer:viewer.close()
        pr.close_window()


if __name__=='__main__':main()
