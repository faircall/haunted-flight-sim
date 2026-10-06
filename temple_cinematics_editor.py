"""Native timeline and camera editor, using the actual PS1 intro renderer."""
from copy import deepcopy
from dataclasses import dataclass,field
from pathlib import Path
import json
import math
import pyray as pr
from g_cinematics_editor import Cinematics
from g_temple_intro import Intro,SCRIPT,load_script
from g_temple_cinematics import fly_pose,orbit_pose,inside_cabin,sample_camera
from temple_intro_viewer import View,Audio,camera_from_pose,capture,WIDTH,HEIGHT

ROOT=Path(__file__).resolve().parent
BG=pr.Color(15,20,25,255);PANEL=pr.Color(22,29,36,255);FIELD=pr.Color(30,40,49,255)
INK=pr.Color(220,229,235,255);MUTED=pr.Color(138,156,170,255);ACCENT=pr.Color(237,174,99,255)
BLUE=pr.Color(78,128,157,255);GREEN=pr.Color(91,154,132,255)


def contains(rect,point):return rect[0]<=point[0]<rect[0]+rect[2] and rect[1]<=point[1]<rect[1]+rect[3]


def timestamp(t):return f'{int(t)//60:02}:{t%60:05.2f}'


def label(value,width,size=16):
    while value and pr.measure_text(value,size)>width:value=value[:-1]
    return value


@dataclass
class Input:
    mouse:tuple=(0,0)
    delta:tuple=(0,0)
    pressed:set=field(default_factory=set)
    down:set=field(default_factory=set)
    left_pressed:bool=False
    left_down:bool=False
    left_released:bool=False
    right_pressed:bool=False
    right_down:bool=False
    right_released:bool=False
    middle_pressed:bool=False
    middle_down:bool=False
    middle_released:bool=False
    wheel:float=0
    chars:str=''

    @classmethod
    def read(cls):
        point=pr.get_mouse_position();delta=pr.get_mouse_delta()
        keys=('ESCAPE','F2','SPACE','HOME','LEFT','RIGHT','S','O','Z','Y','W','A','D','Q','E','ENTER','BACKSPACE','TAB','DELETE','LEFT_CONTROL','RIGHT_CONTROL','LEFT_SHIFT','RIGHT_SHIFT')
        chars=[];code=pr.get_char_pressed()
        while code:
            chars.append(chr(code));code=pr.get_char_pressed()
        return cls(mouse=(point.x,point.y),delta=(delta.x,delta.y),
            pressed={name for name in keys if pr.is_key_pressed(getattr(pr,'KEY_'+name))},
            down={name for name in keys if pr.is_key_down(getattr(pr,'KEY_'+name))},
            left_pressed=pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT),left_down=pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT),left_released=pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT),
            right_pressed=pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_RIGHT),right_down=pr.is_mouse_button_down(pr.MOUSE_BUTTON_RIGHT),right_released=pr.is_mouse_button_released(pr.MOUSE_BUTTON_RIGHT),
            middle_pressed=pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_MIDDLE),middle_down=pr.is_mouse_button_down(pr.MOUSE_BUTTON_MIDDLE),middle_released=pr.is_mouse_button_released(pr.MOUSE_BUTTON_MIDDLE),
            wheel=pr.get_mouse_wheel_move(),chars=''.join(chars))


class Editor:
    def __init__(self,intro,view,audio=None,path=SCRIPT,live_input=True):
        self.state=Cinematics(intro.document,path);self.state.seek(intro.elapsed)
        self.intro=intro;self.view=view;self.audio=audio;self.live_input=live_input
        self.events=Input();self.drag=None;self.entry=None;self.guides=True;self.subtitles=True;self.audio_enabled=False
        self.speed=2.;self.scroll=0;self.status='Select a shot, then frame its START or END camera.';self.closed=False
        self.sync()

    def layout(self):
        w,h=pr.get_screen_width(),pr.get_screen_height();left=222;right=w-310;bottom=h-152
        area=(left+16,110,right-left-32,bottom-215)
        scale=min(area[2]/WIDTH,area[3]/HEIGHT)
        viewport=(area[0]+(area[2]-WIDTH*scale)/2,area[1]+(area[3]-HEIGHT*scale)/2,WIDTH*scale,HEIGHT*scale)
        return dict(w=w,h=h,left=left,right=right,bottom=bottom,viewport=viewport,timeline=(16,bottom+51,w-32,37))

    def controls(self):
        layout=self.layout();w=layout['w'];x=layout['right']+16;b=layout['bottom'];camera=self.state.shot['camera']
        buttons=[('play','Pause' if self.state.playing else 'Play', (322,14,82,30),self.state.playing),
                 ('loop','Loop shot',(414,14,100,30),self.state.loop),('audio','Audio',(524,14,78,30),self.audio_enabled),
                 ('save','Save to game',(620,14,132,30),False),('reload','Reload',(762,14,82,30),False),
                 ('undo','Undo',(854,14,72,30),False),('redo','Redo',(936,14,72,30),False),
                 ('close','Return / exit',(w-166,14,150,30),False),
                 ('start','START',(x,102,134,32),self.state.key=='start'),('end','END',(x+144,102,134,32),self.state.key=='end'),
                 ('mode','Mouse look: '+('ON' if camera['mode']=='interactive' else 'OFF'),(x,155,278,30),camera['mode']=='interactive'),
                 ('scene','View: '+camera['view'].title(),(x,196,278,30),False),
                 ('ease','Move: '+('Ease in / out' if camera['ease']=='smooth' else 'Constant speed'),(x,237,278,30),False),
                 ('still','Match other key',(x,473,134,30),False),('reset','Reset camera',(x+144,473,134,30),False),
                 ('car','Aim at car',(x,516,134,30),False),('player','Aim at player',(x+144,516,134,30),False),
                 ('split','Split at cursor',(12,b-81,98,30),False),('remove','Remove shot',(120,b-81,90,30),False),
                 ('guides','Thirds',(layout['left']+16,b-42,82,26),self.guides),
                 ('subtitles','Subtitles',(layout['left']+108,b-42,96,26),self.subtitles)]
        fields=[]
        for prop,y in (('eye',306),('target',376)):
            for i in range(3):fields.append(((prop,i),(x+i*95,y,88,32)))
        fields.append((('fov',None),(x+174,424,104,32)))
        return buttons,fields

    def sync(self):
        self.intro.document=self.state.document;self.intro.elapsed=self.state.elapsed
        self.intro.paused=False;self.intro.skipped=False;self.intro.yaw=0.;self.intro.pitch=-8.

    def key_time(self):
        self.state.playing=False
        self.state.elapsed=self.state.shot['start'] if self.state.key=='start' else self.state.shot['end']-1e-5

    def set_pose(self,frame):
        camera=self.state.shot['camera'];camera[self.state.key]=frame
        camera['view']='interior' if inside_cabin(frame['eye']) else 'exterior'
        if camera['view']=='exterior':camera['mode']='fixed'

    def finish_drag(self,cancel=False):
        if not self.drag:return
        drag=self.drag;self.drag=None
        if drag['kind']!='seek':
            if cancel:self.state.document=drag['before']
            else:
                try:self.state.commit(drag['before']);self.status='Camera updated.' if drag['kind'] in ('fly','orbit') else 'Cut timing updated.'
                except ValueError as exc:self.status=str(exc)
        if drag['kind']=='fly' and self.live_input:
            pr.enable_cursor();pr.set_mouse_position(int(drag['mouse'][0]),int(drag['mouse'][1]))

    def action(self,name):
        self.finish_drag()
        try:
            if name=='play':
                self.state.playing=not self.state.playing
                if self.state.elapsed>=self.state.document['duration']-.01:self.state.elapsed=0;self.state.selected=0
            elif name=='loop':self.state.loop=not self.state.loop
            elif name=='audio':self.audio_enabled=not self.audio_enabled
            elif name=='save':self.state.save();self.status='Saved. The game now uses these shots.'
            elif name=='reload':self.state.reload();self.key_time();self.status='Reloaded saved shots. Undo restores your edits.'
            elif name in ('undo','redo'):
                if getattr(self.state,name)():self.key_time();self.status=name.title()+' applied.'
            elif name=='close':self.closed=True
            elif name in ('start','end'):self.state.key=name;self.key_time()
            elif name=='mode':
                self.state.change(lambda:self.state.shot['camera'].__setitem__('mode','fixed' if self.state.shot['camera']['mode']=='interactive' else 'interactive'))
            elif name=='scene':
                self.state.change(lambda:self.state.shot['camera'].__setitem__('view','exterior' if self.state.shot['camera']['view']=='interior' else 'interior'))
            elif name=='ease':
                self.state.change(lambda:self.state.shot['camera'].__setitem__('ease','linear' if self.state.shot['camera']['ease']=='smooth' else 'smooth'))
            elif name=='still':self.state.match_keys();self.status='Start and end cameras now match.'
            elif name=='reset':self.state.reset_camera();self.key_time();self.status='Original camera restored for this shot.'
            elif name in ('car','player'):
                frame=deepcopy(self.state.frame);frame['target']=[0,.87,0] if name=='car' else [0,1.43,.82]
                self.state.set_frame(frame);self.key_time()
            elif name=='split':self.state.split();self.scroll=max(0,self.state.selected-7);self.status='New cut added at the cursor.'
            elif name=='remove':self.state.remove();self.status='Shot removed; the adjacent shot covers its time.'
            elif name=='guides':self.guides=not self.guides
            elif name=='subtitles':self.subtitles=not self.subtitles
        except (OSError,ValueError,KeyError,TypeError) as exc:self.status=str(exc)
        self.sync()

    def edit_number(self,path):
        self.key_time();prop,index=path;value=self.state.frame[prop] if index is None else self.state.frame[prop][index]
        self.entry=dict(path=path,text=f'{value:.3f}',replace=True);self.status='Type a value. Enter applies; Escape cancels.'

    def finish_entry(self,cancel=False):
        if not self.entry:return True
        if not cancel:
            try:
                value=float(self.entry['text']);frame=deepcopy(self.state.frame);prop,index=self.entry['path']
                if index is None:frame[prop]=value
                else:frame[prop][index]=value
                if prop=='eye':self.state.change(lambda:self.set_pose(frame))
                else:self.state.set_frame(frame)
                self.status='Camera value updated.'
            except (ValueError,OverflowError) as exc:self.status=str(exc);return False
        else:self.status='Value edit canceled.'
        self.entry=None;return True

    def update(self,dt,events=None):
        self.events=events or Input.read();event=self.events;layout=self.layout();buttons,fields=self.controls()
        control=bool(event.down&{'LEFT_CONTROL','RIGHT_CONTROL'});shift=bool(event.down&{'LEFT_SHIFT','RIGHT_SHIFT'})
        if self.entry:
            for char in event.chars:
                if char in '0123456789+-.eE':
                    if self.entry['replace']:self.entry['text']='';self.entry['replace']=False
                    if len(self.entry['text'])<24:self.entry['text']+=char
            if 'BACKSPACE' in event.pressed:
                self.entry['text']='' if self.entry['replace'] else self.entry['text'][:-1];self.entry['replace']=False
            if 'ESCAPE' in event.pressed:
                self.finish_entry(True);self.sync();return
            elif 'ENTER' in event.pressed:self.finish_entry()
            elif event.left_pressed:
                active=next(rect for path,rect in fields if path==self.entry['path'])
                if not contains(active,event.mouse) and not self.finish_entry():self.sync();return
            self.sync()
            if self.entry:return
        if self.drag:
            kind=self.drag['kind']
            if 'ESCAPE' in event.pressed:self.finish_drag(True);self.sync();return
            if kind=='fly':
                if event.right_released or not event.right_down:self.finish_drag()
                else:
                    if event.wheel:self.speed=max(.1,min(30,self.speed*1.25**event.wheel))
                    movement=(int('D' in event.down)-int('A' in event.down),int('W' in event.down)-int('S' in event.down),int('E' in event.down)-int('Q' in event.down))
                    delta=event.delta if self.drag['ready'] else (0,0);self.drag['ready']=True
                    self.set_pose(fly_pose(self.state.frame,delta,movement,dt,self.speed*(3 if shift else .25 if control else 1)))
            elif kind=='orbit':
                if event.middle_released or not event.middle_down:self.finish_drag()
                else:self.set_pose(orbit_pose(self.state.frame,event.delta,shift))
            elif kind=='seek':
                self.state.seek(self.time_at(event.mouse[0]))
                if event.left_released or not event.left_down:self.finish_drag()
            elif kind=='cut':
                index=self.drag['index'];shots=self.state.document['shots']
                time=round(self.time_at(event.mouse[0]),2 if shift else 1)
                time=self.state.cut_time(index,time)
                shots[index-1]['end']=time;shots[index]['start']=time
                self.state.seek(self.state.elapsed)
                if event.left_released or not event.left_down:self.finish_drag()
            self.sync();return
        if event.pressed&{'F2','ESCAPE'}:self.action('close');return
        if control:
            for key,name in (('S','save'),('O','reload'),('Z','undo'),('Y','redo')):
                if key in event.pressed:self.action(name)
        else:
            if 'SPACE' in event.pressed:self.action('play')
            if 'HOME' in event.pressed:self.state.seek(0)
            if 'LEFT' in event.pressed:self.state.seek(self.state.elapsed-(1 if shift else 1/30))
            if 'RIGHT' in event.pressed:self.state.seek(self.state.elapsed+(1 if shift else 1/30))
            if 'DELETE' in event.pressed:self.action('remove')
        if event.left_pressed:
            for name,_,rect,_ in buttons:
                if contains(rect,event.mouse):self.action(name);return
            for path,rect in fields:
                if contains(rect,event.mouse):self.edit_number(path);self.sync();return
            if contains((8,100,206,layout['bottom']-194),event.mouse):
                index=int((event.mouse[1]-100)//58)+self.scroll
                if index<len(self.state.document['shots']):self.state.select(index);self.sync();return
            timeline=layout['timeline']
            if contains((timeline[0],timeline[1]-22,timeline[2],91),event.mouse):
                boundaries=[(abs(self.x_at(s['start'])-event.mouse[0]),i) for i,s in enumerate(self.state.document['shots']) if i and abs(self.x_at(s['start'])-event.mouse[0])<7 and timeline[1]<=event.mouse[1]<timeline[1]+timeline[3]]
                boundary=min(boundaries)[1] if boundaries else None
                if boundary is not None:self.drag=dict(kind='cut',index=boundary,before=self.state.checkpoint());self.state.playing=False
                else:self.drag=dict(kind='seek');self.state.seek(self.time_at(event.mouse[0]))
        if contains(layout['viewport'],event.mouse):
            if event.right_pressed or event.middle_pressed:
                self.key_time();self.drag=dict(kind='fly' if event.right_pressed else 'orbit',before=self.state.checkpoint(),mouse=event.mouse,ready=False)
                if event.right_pressed and self.live_input:pr.disable_cursor()
            elif event.wheel:
                frame=deepcopy(self.state.frame);frame['fov']=max(15,min(110,frame['fov']-event.wheel*(.5 if shift else 2)))
                self.state.set_frame(frame);self.key_time()
        elif event.wheel and event.mouse[0]<layout['left']:
            self.scroll=max(0,min(max(0,len(self.state.document['shots'])-8),self.scroll-int(event.wheel)))
        self.state.tick(dt);self.sync()

    def x_at(self,time):
        rect=self.layout()['timeline'];return rect[0]+rect[2]*time/self.state.document['duration']

    def time_at(self,x):
        rect=self.layout()['timeline'];return max(0,min(self.state.document['duration']-1e-5,(x-rect[0])/rect[2]*self.state.document['duration']))

    def render_scene(self):
        self.sync()
        # The editor shows the authored pose directly, without mouse-look offsets
        # or suspension bob; playback still uses the same shot interpolation.
        camera=camera_from_pose(sample_camera(self.intro.shot,self.intro.elapsed))
        self.view.render(self.intro,False,camera_override=camera,overlays=self.subtitles,apply_fade=False,trails=self.state.playing)
        if self.audio:
            self.intro.paused=not (self.state.playing and self.audio_enabled);self.audio.update(self.intro);self.intro.paused=False
        return camera

    def draw(self):
        layout=self.layout();w,h,b=layout['w'],layout['h'],layout['bottom'];x=layout['right']+16
        pr.clear_background(BG);pr.draw_rectangle(0,0,w,58,PANEL)
        pr.draw_text('CINEMATICS'+(' *' if self.state.dirty else ''),16,12,20,INK)
        pr.draw_text('THE ROAD TO THE TEMPLE',16,36,10,MUTED)
        pr.draw_rectangle(0,58,222,b-58,PANEL);pr.draw_rectangle(layout['right'],58,310,b-58,PANEL)
        pr.draw_text('SHOTS',12,77,16,INK);pr.draw_text(str(len(self.state.document['shots'])),185,78,14,MUTED)
        visible=max(1,int((b-194)/58))
        for i,shot in enumerate(self.state.document['shots'][self.scroll:self.scroll+visible],self.scroll):
            y=100+(i-self.scroll)*58;selected=i==self.state.selected
            pr.draw_rectangle(8,y,206,52,FIELD if selected else PANEL)
            if selected:pr.draw_rectangle(8,y,3,52,ACCENT)
            pr.draw_text(f'{i+1:02}',18,y+10,16,ACCENT if selected else MUTED)
            pr.draw_text(label(shot['id'].replace('-',' ').title(),154,14),48,y+9,14,INK)
            pr.draw_text(f"{timestamp(shot['start'])}  -  {timestamp(shot['end'])}",48,y+30,12,MUTED)
        pr.draw_text('CAMERA KEY',x,77,16,INK)
        pr.draw_text('POSITION  /  metres',x,284,12,MUTED);pr.draw_text('LOOK AT  /  metres',x,354,12,MUTED)
        pr.draw_text('LENS  /  degrees',x,434,12,MUTED)
        buttons,fields=self.controls()
        for name,title,rect,selected in buttons:
            hovered=contains(rect,self.events.mouse);fill=BLUE if selected else FIELD
            if hovered:fill=pr.Color(min(255,fill.r+15),min(255,fill.g+15),min(255,fill.b+15),255)
            pr.draw_rectangle_rec(pr.Rectangle(*rect),fill)
            size=14 if rect[2]>=98 else 12;tw=pr.measure_text(title,size)
            pr.draw_text(title,int(rect[0]+(rect[2]-tw)/2),int(rect[1]+(rect[3]-size)/2),size,INK)
        for path,rect in fields:
            prop,index=path;value=self.state.frame[prop] if index is None else self.state.frame[prop][index]
            active=self.entry is not None and self.entry['path']==path
            pr.draw_rectangle_rec(pr.Rectangle(*rect),BLUE if active else FIELD)
            prefix='' if index is None else 'XYZ'[index]+' '
            value=self.entry['text']+'_' if active else f'{value:.2f}'
            pr.draw_text(label(prefix+value,rect[2]-12,14),int(rect[0]+6),int(rect[1]+9),14,INK)
        pr.draw_text('Click a number to type an exact value.',x,562,12,MUTED)
        pr.draw_text('Ctrl+S save  /  Ctrl+O reload',x,585,12,MUTED)
        pr.draw_text('Ctrl+Z undo  /  Ctrl+Y redo',x,607,12,MUTED)
        viewrect=layout['viewport'];pr.draw_rectangle_rec(pr.Rectangle(*viewrect),pr.BLACK)
        pr.draw_texture_pro(self.view.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(*viewrect),pr.Vector2(0,0),0,pr.WHITE)
        if self.guides:
            for i in (1,2):
                gx=viewrect[0]+viewrect[2]*i/3;gy=viewrect[1]+viewrect[3]*i/3
                pr.draw_line(int(gx),int(viewrect[1]),int(gx),int(viewrect[1]+viewrect[3]),pr.Color(224,230,235,55))
                pr.draw_line(int(viewrect[0]),int(gy),int(viewrect[0]+viewrect[2]),int(gy),pr.Color(224,230,235,55))
        pr.draw_text(label(self.state.shot['id'].replace('-',' ').title(),400,18),238,73,18,INK)
        pr.draw_text(f"{timestamp(self.state.elapsed)}   |   {self.state.key.upper()} key",layout['right']-259,76,14,ACCENT)
        pr.draw_text('RMB + WASD: fly  /  Q,E: down,up  /  Shift: fast',238,b-83,14,MUTED)
        pr.draw_text('MMB: orbit  /  Shift+MMB: pan  /  Wheel: lens',238,b-62,14,MUTED)
        pr.draw_text(f'Fly speed  {self.speed:.1f} m/s',layout['right']-196,b-38,12,MUTED)
        pr.draw_rectangle(0,b,w,h-b,PANEL)
        pr.draw_text(label(self.status,w-380,14),16,b+10,14,ACCENT)
        pr.draw_text('Space: play  /  arrows: frame step',w-302,b+12,12,MUTED)
        timeline=layout['timeline']
        for t in range(0,int(self.state.document['duration'])+1,10):
            px=self.x_at(t);pr.draw_line(int(px),int(timeline[1]-7),int(px),int(timeline[1]-2),MUTED)
            pr.draw_text(timestamp(t)[:5],int(px)+3,int(timeline[1]-18),10,MUTED)
        for i,shot in enumerate(self.state.document['shots']):
            a=self.x_at(shot['start']);z=self.x_at(shot['end']);fill=GREEN if shot['camera']['mode']=='interactive' else BLUE
            pr.draw_rectangle(int(a)+1,int(timeline[1]),max(1,int(z-a)-2),int(timeline[3]),fill)
            if i==self.state.selected:pr.draw_rectangle_lines_ex(pr.Rectangle(a,timeline[1],z-a,timeline[3]),2,ACCENT)
            pr.draw_text(label(f"{i+1:02}  {shot['id'].replace('-',' ')}",max(0,z-a-12),12),int(a)+6,int(timeline[1])+11,12,INK)
            if i:pr.draw_rectangle(int(a)-2,int(timeline[1])+3,4,int(timeline[3])-6,INK)
        for line in self.state.document['lines']:
            a=self.x_at(line['start']);z=self.x_at(line['end'])
            pr.draw_rectangle(int(a),int(timeline[1])+47,max(1,int(z-a)),10,pr.Color(90,98,112,255))
        cursor=self.x_at(self.state.elapsed)
        pr.draw_line_ex(pr.Vector2(cursor,timeline[1]-21),pr.Vector2(cursor,timeline[1]+63),2,ACCENT)
        pr.draw_text('CUTS: drag a boundary  /  SCRUB: drag the cursor  /  grey bars: dialogue',16,h-20,12,MUTED)
        pr.draw_text('Unsaved changes' if self.state.dirty else 'Saved',w-159,h-20,12,ACCENT if self.state.dirty else MUTED)


def edit_intro(intro,view,audio=None):
    old_pause=intro.paused;old_look=(intro.yaw,intro.pitch)
    pr.enable_cursor();editor=Editor(intro,view,audio)
    try:
        # Finish the frame that opened the modal so its F2 press cannot also
        # trigger the editor's close command in the first input update.
        editor.render_scene();pr.begin_drawing();editor.draw();pr.end_drawing()
        while not pr.window_should_close() and not editor.closed:
            editor.update(pr.get_frame_time());editor.render_scene()
            pr.begin_drawing();editor.draw();pr.end_drawing()
    finally:
        editor.finish_drag();editor.finish_entry();editor.sync()
        intro.paused=old_pause;intro.yaw,intro.pitch=old_look
        if audio:audio.update(intro)
        pr.enable_cursor()


def run(review=False):
    if review:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1440,810,'Temple / cinematics editor');pr.set_target_fps(60);pr.set_exit_key(pr.KEY_NULL)
    view=None;audio=None
    try:
        intro=Intro(load_script());view=View()
        try:audio=Audio()
        except (RuntimeError,OSError):pass
        if review:review_editor(intro,view,audio)
        else:edit_intro(intro,view,audio)
    finally:
        pr.enable_cursor()
        if audio:audio.close()
        if view:view.close()
        pr.close_window()


def review_editor(intro,view,audio):
    """Exercise the same native widgets and input handler against an isolated file."""
    folder=ROOT/'artifacts'/'cinematics-editor';folder.mkdir(parents=True,exist_ok=True)
    original=SCRIPT.read_bytes();path=folder/'review-shots.json'
    # Exercise a reproducible timeline even after artists save different cuts.
    from test_cinematics_editor import fixture_document
    baseline=fixture_document();intro.document=deepcopy(intro.document)
    intro.document['duration']=baseline['duration'];intro.document['shots']=baseline['shots']
    path.write_text(json.dumps(intro.document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    editor=Editor(intro,view,audio,path,live_input=False);target=pr.load_render_texture(1440,810)
    def snapshot(name):
        editor.render_scene();pr.begin_texture_mode(target);editor.draw();pr.end_texture_mode();capture(target,folder/(name+'.png'))
    def click(name):
        rect=next(rect for key,_,rect,_ in editor.controls()[0] if key==name)
        editor.update(0,Input(mouse=(rect[0]+rect[2]/2,rect[1]+rect[3]/2),left_pressed=True))
    def shortcut(key):editor.update(0,Input(pressed={key},down={'LEFT_CONTROL'}))
    def number(path,value):
        rect=next(rect for key,rect in editor.controls()[1] if key==path)
        editor.update(0,Input(mouse=(rect[0]+10,rect[1]+10),left_pressed=True))
        editor.update(0,Input(chars=value,pressed={'ENTER'}))
    try:
        Input.read() # Check the actual Raylib input API as well as injected events.
        editor.state.seek(3.7);snapshot('01-opening-editor')
        # Select a shot through the list and edit its END frame with native fly input.
        editor.update(0,Input(mouse=(86,100+2*58+20),left_pressed=True));assert editor.state.selected==2
        click('end');before=editor.state.checkpoint();viewport=editor.layout()['viewport']
        mouse=(viewport[0]+viewport[2]/2,viewport[1]+viewport[3]/2)
        editor.update(0,Input(mouse=mouse,right_pressed=True,right_down=True))
        frozen=editor.state.elapsed
        for _ in range(8):editor.update(.05,Input(mouse=mouse,delta=(3,-1),right_down=True,down={'W','D'}))
        editor.update(0,Input(mouse=mouse,right_released=True))
        assert editor.state.elapsed==frozen and editor.state.document!=before
        changed=editor.state.checkpoint();assert len(editor.state.undo_stack)==1
        shortcut('Z');assert editor.state.document==before
        shortcut('Y');assert editor.state.document==changed
        # Orbit and pan are separate undoable gestures and keep a stable target.
        target_before=deepcopy(editor.state.frame['target'])
        editor.update(0,Input(mouse=mouse,middle_pressed=True,middle_down=True))
        editor.update(.05,Input(mouse=mouse,delta=(20,-6),middle_down=True))
        editor.update(0,Input(mouse=mouse,middle_released=True))
        assert editor.state.frame['target']==target_before
        old_eye=deepcopy(editor.state.frame['eye'])
        editor.update(0,Input(mouse=mouse,middle_pressed=True,middle_down=True))
        editor.update(.05,Input(mouse=mouse,delta=(8,4),middle_down=True,down={'LEFT_SHIFT'}))
        editor.update(0,Input(mouse=mouse,middle_released=True));assert editor.state.frame['eye']!=old_eye
        number(('fov',None),'54');assert editor.state.frame['fov']==54
        good=editor.state.checkpoint();number(('fov',None),'1e999')
        assert editor.state.document==good and editor.entry is not None
        editor.update(0,Input(pressed={'ESCAPE'}));assert editor.entry is None and not editor.closed
        snapshot('02-authored-camera-end')
        # Drag a shared boundary, preserving complete coverage and dialogue times.
        timeline=editor.layout()['timeline'];boundary=editor.x_at(44)
        editor.update(0,Input(mouse=(boundary,timeline[1]+15),left_pressed=True,left_down=True))
        editor.update(0,Input(mouse=(editor.x_at(47.5),timeline[1]+15),left_down=True))
        editor.update(0,Input(mouse=(editor.x_at(47.5),timeline[1]+15),left_released=True))
        assert editor.state.document['shots'][1]['end']==47.5==editor.state.document['shots'][2]['start']
        assert editor.state.document['lines']==intro.document['lines']
        # Split at the scrubbed playhead; the new camera keys meet at the cut.
        editor.state.seek(51.5);click('split');assert len(editor.state.document['shots'])==8
        a,b=editor.state.document['shots'][2:4]
        assert a['camera']['end']==b['camera']['start']
        click('remove');assert len(editor.state.document['shots'])==7
        # Save through the toolbar and prove the actual game reads the edited lens.
        click('save');assert not editor.state.dirty
        reloaded=load_script(path);assert reloaded==editor.state.document
        runtime=Intro(reloaded,elapsed=55.99)
        actual=view.camera(runtime);expected=sample_camera(runtime.shot,runtime.elapsed)
        assert abs(actual.fovy-expected['fov'])<1e-4
        assert math.dist((actual.position.x,actual.position.y,actual.position.z),expected['eye'])<1e-4
        saved=editor.state.checkpoint();number(('fov',None),'67');assert editor.state.dirty
        click('reload');assert editor.state.document==saved and not editor.state.dirty
        shortcut('Z');assert editor.state.dirty;shortcut('Y');assert not editor.state.dirty
        # Scrub the night transition and loop it without losing clock synchronization.
        editor.update(0,Input(mouse=(editor.x_at(103),timeline[1]+51),left_pressed=True,left_down=True))
        editor.update(0,Input(mouse=(editor.x_at(103),timeline[1]+51),left_released=True))
        assert editor.state.selected==4 and abs(editor.intro.elapsed-103)<1e-4
        snapshot('03-night-shot-timeline')
        click('loop');click('play');editor.state.elapsed=113.98
        editor.update(.05,Input());assert 95<=editor.state.elapsed<95.1 and editor.state.selected==4
        click('play');assert not editor.state.playing
        if audio:editor.render_scene();assert not audio.sounds['engine'].is_playing
        # Every shot can be selected and rendered at either camera key.
        for index in range(len(editor.state.document['shots'])):
            for key in ('start','end'):
                editor.state.select(index,key);editor.render_scene()
        click('close');assert editor.closed
        # The embedded editor preserves first-person look/pause and the native
        # window. It draws its opening frame before reading the next F2 press.
        from unittest.mock import patch
        intro.elapsed=17.;intro.yaw=31.;intro.pitch=-12.;intro.paused=True
        history=[];draw=Editor.draw
        def record_draw(instance):history.append('draw');draw(instance)
        def return_input():history.append('input');return Input(pressed={'F2'})
        with patch.object(Editor,'draw',record_draw),patch.object(Input,'read',side_effect=return_input):
            edit_intro(intro,view,audio)
        assert history[0]=='draw' and 'input' in history
        assert intro.paused and (intro.yaw,intro.pitch)==(31.,-12.) and pr.is_window_ready()
        assert SCRIPT.read_bytes()==original,'Native review must not modify the real cinematic.'
        report=dict(native_widgets=True,camera_flight=True,orbit_and_pan=True,exact_lens=True,
                    invalid_number_rejected=True,undo_redo=True,cut_drag=True,scrub=True,split_remove=True,
                    save_reload=True,runtime_reads_saved_camera=True,loop_and_pause=True,
                    all_shot_keys_rendered=True,embedded_editor_round_trip=True,source_untouched=True,shots=len(reloaded['shots']))
        (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print('Cinematics editor native review passed: camera controls, timeline, undo/redo, save/reload and game playback.',flush=True)
    finally:pr.unload_render_texture(target)


if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
    run()
