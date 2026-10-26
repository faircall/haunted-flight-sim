"""Native camera authoring against the Moon scene, with isolated preview state."""
if __name__=='__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()

from copy import deepcopy
from pathlib import Path
import math
import pyray as pr

from g_huxin_moon_direction import DEFAULT_PATH,DirectionEditor,CameraConflictError
from g_scene_cameras import sample_shot
from g_huxin_moon import Explorer,DECK
from g_huxin_moon_sequence import MoonSequence,ENTRY_SWAP,ENTRY_DURATION,causeway_progress
from g_temple_cinematics import fly_pose,orbit_pose
from temple_cinematics_editor import Input,contains,label
from temple_intro_viewer import camera_from_pose

WIDTH,HEIGHT=640,360
BG=pr.Color(13,20,23,255);PANEL=pr.Color(21,30,34,255);FIELD=pr.Color(31,43,48,255)
INK=pr.Color(221,232,229,255);MUTED=pr.Color(133,160,163,255)
ACCENT=pr.Color(228,183,113,255);BLUE=pr.Color(58,106,122,255);GREEN=pr.Color(61,119,104,255)


class MoonCinematographer:
    def __init__(self,scene,actor=None,clock=0.,path=None,live_input=True,document=None):
        self.scene=scene;self.state=DirectionEditor(document=document,path=path or DEFAULT_PATH)
        self.live_input=live_input;self.clock=float(clock);self.actor=Explorer();self.sequence=MoonSequence()
        self.actor.encounter=self.sequence
        self.tab='camera';self.preview=False;self.scroll=0;self.speed=3.
        self.entry=None;self.drag=None;self.closed=False;self.close_prompt=False;self.close_error=None
        self.live_enabled=True;self._poll_elapsed=0.
        self.preview_camera=None;self.events=Input();self._released=False
        self._previous={name:getattr(scene,name,None) for name in ('sequence','last_camera','last_shot','camera_director')}
        previous_camera=self._previous['last_camera']
        self._game_pose=None if previous_camera is None else {
            'eye':[previous_camera.position.x,previous_camera.position.y,previous_camera.position.z],
            'target':[previous_camera.target.x,previous_camera.target.y,previous_camera.target.z],'fov':previous_camera.fovy}
        self._game_actor=None if actor is None else [actor.x,actor.height,actor.z]
        self._game_yaw=None if actor is None else actor.yaw
        self.status='Select a shot. Edit its keys, then Preview behavior to test it.'
        active=getattr(getattr(scene,'camera_director',None),'active_id',None)
        selected=active if any(s['id']==active for s in self.state.document['shots']) else next((s['id'] for s in self.state.document['shots'] if s['activation']['type']=='reveal'),0)
        self.state.select(selected)
        self.ensure_selected_visible();self.reset_actor();self.scene.sequence=self.sequence

    @property
    def duration(self):
        return max(self.state.shot['duration'],ENTRY_DURATION if self.state.shot['preview']['phase']=='reveal' else 0.)

    def layout(self):
        w,h=pr.get_screen_width(),pr.get_screen_height();left=260;right=w-338;bottom=h-126
        area=(left+18,135,right-left-36,bottom-258)
        scale=max(.1,min(area[2]/WIDTH,area[3]/HEIGHT))
        view=(area[0]+(area[2]-WIDTH*scale)/2,area[1]+(area[3]-HEIGHT*scale)/2,WIDTH*scale,HEIGHT*scale)
        return dict(w=w,h=h,left=left,right=right,bottom=bottom,viewport=view,timeline=(26,bottom+54,w-52,26),
                    list=(8,102,244,bottom-160))

    def controls(self):
        a=self.layout();x=a['right']+14;b=a['bottom'];w=a['w'];shot=self.state.shot
        buttons=[('save','Save to game',(264,14,122,30),False),('reload','Reload',(394,14,76,30),False),
                 ('undo','Undo',(478,14,66,30),False),('redo','Redo',(552,14,66,30),False),
                 ('play','Pause' if self.state.playing else 'Play',(632,14,70,30),self.state.playing),
                 ('loop','Loop',(710,14,68,30),self.state.loop),
                 ('live','Live: ON' if self.live_enabled else 'Live: OFF',(788,14,88,30),self.live_enabled),
                 ('close','Return / exit',(w-146,14,130,30),False),
                 ('preview','Preview behavior' if self.preview else 'Edit camera keys',(a['left']+18,71,174,31),self.preview),
                 ('phase','Scene: '+shot['preview']['phase'].title(),(a['left']+202,71,160,31),False),
                 ('reset_actor','Reset test actor',(a['left']+18,b-116,145,28),False),
                 ('use_game_view','Use game view',(a['left']+173,b-116,145,28),False),
                 ('tab:camera','CAMERA',(x,71,96,29),self.tab=='camera'),
                 ('tab:behavior','BEHAVIOR',(x+104,71,96,29),self.tab=='behavior'),
                 ('tab:activation','ACTIVATION',(x+208,71,102,29),self.tab=='activation'),
                 ('duplicate','Duplicate',(12,b-46,112,29),False),('new_zone','New zone',(134,b-46,112,29),False)]
        if getattr(self.state,'conflict',False):buttons.append(('keep_mine','Keep mine / save',(886,14,139,30),False))
        rows=max(1,int(a['list'][3]//42));shots=self.state.document['shots'];self.scroll=min(max(0,self.scroll),max(0,len(shots)-rows))
        for i,entry in enumerate(shots[self.scroll:self.scroll+rows]):
            buttons.append(('shot:'+entry['id'],entry['label'],(10,104+i*42,238,38),entry['id']==self.state.selected))
        fields=[];labels=[]
        def field(path,title,y,x0=x,width=310):
            labels.append((title,x0,y-17));fields.append((path,(x0,y,width,30)))
        def vector(path,title,y):
            labels.append((title,x,y-17))
            for i in range(3):fields.append((path+(i,),(x+i*106,y,98,30)))
        if self.tab=='camera':
            buttons.extend([('start','START',(x,115,150,31),self.state.key=='start'),('end','END',(x+160,115,150,31),self.state.key=='end')])
            field(('label',),'SHOT NAME',181)
            vector((self.state.key,'eye'),'CAMERA POSITION / world metres',250)
            vector((self.state.key,'target'),'LOOK AT / world metres',319)
            field((self.state.key,'fov'),'LENS / vertical degrees',388)
            buttons.extend([('aim_player','Aim this key at player',(x,442,310,30),False),
                            ('match_key','Match other key',(x,484,150,30),False),('hold','Hold this shot',(x+160,484,150,30),False)])
            labels.extend([('RMB + WASD: edit camera / Q,E: down,up',x,542),('Shift: fast / Ctrl: slow / RMB wheel: speed',x,564),
                           ('MMB: orbit / Shift+MMB: pan / wheel: lens',x,586),('Changes apply directly to the selected key.',x,620),
                           ('Save to keep them for normal gameplay.',x,642)])
        elif self.tab=='behavior':
            for i,(prop,title) in enumerate((('movement','Movement'),('aim','Aim'),('lens','Lens'),('easing','Easing'))):
                buttons.append(('cycle:'+prop,title+': '+shot[prop].replace('_',' ').title(),(x,122+i*42,310,31),False))
            field(('duration',),'SHOT DURATION / seconds',325)
            vector(('aim_offset',),'PLAYER AIM OFFSET / metres',394)
            labels.extend([('Movement and aim are independent.',x,452),('Locked: fixed eye. Path: start to end.',x,476),
                           ('Follow: eye follows the test actor displacement.',x,500),('Fixed: start aim. Pan: start to end aim.',x,536),
                           ('Player: always aim at the actor.',x,560),('Keep visible: pan only near frame edges.',x,584),
                           ('Follow keys use the saved test-actor reference.',x,625),('Reset test actor before composing, or re-anchor:',x,647)])
            buttons.append(('follow_reference','Use actor as follow reference',(x,678,310,30),False))
        else:
            act=shot['activation']
            buttons.extend([('enabled','Override in game: '+('ON' if shot['enabled'] else 'OFF'),(x,122,310,31),shot['enabled']),
                            ('activation_type','Trigger: '+act['type'].title(),(x,165,310,31),False)])
            field(('activation','priority'),'PRIORITY / higher wins',232)
            if act['type'] in ('lake','room'):field(('activation','index'),'BASE CAMERA INDEX / zero based',300)
            if act['type']=='zone':
                buttons.append(('zone_phase','World: '+act['phase'].title(),(x,280,310,31),False))
                vector(('activation','bounds','min'),'ZONE MINIMUM / X Y Z',360)
                vector(('activation','bounds','max'),'ZONE MAXIMUM / X Y Z',429)
                buttons.append(('zone_actor','Centre zone on test actor',(x,485,310,30),False))
            buttons.append(('remove','Remove selected shot',(x,552,310,30),False))
            labels.extend([('Lake / Room replaces an existing camera slot.',x,608),('Zone overrides cameras inside its bounds.',x,630),
                           ('Reveal and Focus follow the puzzle state.',x,652),('Disabled uses the normal game camera.',x,678)])
        self._labels=labels
        if self.close_prompt:
            cx,cy=w/2-253,a['h']/2-90
            return [('close_save','Save and return',(cx+15,cy+104,148,32),False),
                    ('close_discard','Discard and return',(cx+174,cy+104,153,32),False),
                    ('close_cancel','Keep editing',(cx+338,cy+104,153,32),False)],[]
        return buttons,fields

    def reset_actor(self):
        p=self.state.shot['preview'];self.actor.x,self.actor.height,self.actor.z=p['actor'];self.actor.yaw=p['yaw']
        self.actor.clip='idle';self.actor.phase=0.;self.actor.encounter=self.sequence

    def ensure_selected_visible(self):
        index=next(i for i,shot in enumerate(self.state.document['shots']) if shot['id']==self.state.selected)
        rows=max(1,int(self.layout()['list'][3]//42))
        if index<self.scroll:self.scroll=index
        elif index>=self.scroll+rows:self.scroll=index-rows+1

    def select(self,identity):
        self.state.select(identity);self.preview=False;self.reset_actor();self.entry=None
        self.ensure_selected_visible()
        self.status='Editing '+self.state.shot['label']+' / '+self.state.key.upper()

    def seek(self,value):
        self.state.elapsed=max(0.,min(self.duration,float(value)));self.state.playing=False;self.preview=True

    def field_value(self,path):
        value=self.state.shot
        for part in path:value=value[part]
        return value

    def set_value(self,path,value):
        def operation(shot):
            node=shot
            for part in path[:-1]:node=node[part]
            node[path[-1]]=value
        elapsed=self.state.elapsed
        self.state.change(operation)
        self.state.elapsed=min(elapsed,self.duration)

    def edit_field(self,path):
        self.state.playing=False
        self.entry=dict(path=path,text=str(self.field_value(path)) if path==('label',) else f'{self.field_value(path):.3f}',replace=True)

    def finish_entry(self,cancel=False):
        if not self.entry:return True
        if not cancel:
            try:
                path=self.entry['path'];value=self.entry['text'] if path==('label',) else float(self.entry['text'])
                if path in (('activation','index'),('activation','priority')):
                    if value!=int(value):raise ValueError('Use a whole number for index or priority.')
                    value=int(value)
                self.set_value(path,value);self.status='Updated. Save to game keeps this edit.'
            except (ValueError,TypeError,KeyError,OverflowError) as exc:self.status=str(exc);return False
        self.entry=None;return True

    def finish_drag(self,cancel=False):
        if not self.drag:return
        drag=self.drag;self.drag=None
        if drag['kind']!='seek':
            if cancel:self.state.document=drag['before']
            else:
                try:self.state.commit(drag['before']);self.status='Camera key updated.'
                except (ValueError,TypeError,KeyError) as exc:self.status=str(exc)
        if drag['kind']=='fly' and self.live_input:pr.enable_cursor()

    def activation(self,kind):
        old=self.state.shot['activation'];act={'type':kind,'priority':old.get('priority',0)}
        if kind in ('lake','room'):act['index']=0
        elif kind=='zone':
            x,y,z=self.actor.x,self.actor.height,self.actor.z
            act.update(priority=max(10,act['priority']),phase='any',bounds={'min':[x-2,y-.5,z-2],'max':[x+2,y+3,z+2]})
        self.set_value(('activation',),act)

    def action(self,name):
        self.finish_drag()
        if name=='close' and not self.finish_entry():self.finish_entry(cancel=True)
        try:
            if name=='close_cancel':self.close_prompt=False;self.close_error=None;return
            if name=='close_discard':self.state.discard();self.closed=True;return
            if name=='close_save':
                self.state.save();self.closed=True;return
            if name=='close':
                self.state.playing=False
                if self.state.dirty:self.close_prompt=True;self.close_error=None
                else:self.closed=True
            elif name=='save':self.state.save();self.status='Saved. Normal Moon playback now uses these camera shots.'
            elif name=='keep_mine':self.state.save(force=True);self.status='Your editor version was explicitly saved over the external version.'
            elif name=='live':self.live_enabled=not self.live_enabled
            elif name=='reload':self.state.reload();self.ensure_selected_visible();self.reset_actor();self.status='Reloaded saved cameras. Undo restores the prior document.'
            elif name in ('undo','redo'):
                if getattr(self.state,name)():self.ensure_selected_visible();self.reset_actor();self.status=name.title()+' applied.'
            elif name.startswith('shot:'):self.select(name[5:])
            elif name.startswith('tab:'):self.tab=name[4:]
            elif name in ('start','end'):
                self.state.key=name;self.state.elapsed=0. if name=='start' else self.state.shot['duration'];self.state.playing=False;self.preview=False
            elif name=='preview':
                self.preview=not self.preview;self.state.playing=False
                if not self.preview:self.state.elapsed=0. if self.state.key=='start' else self.state.shot['duration']
            elif name=='play':
                self.preview=True;self.state.playing=not self.state.playing
                if self.state.elapsed>=self.duration:self.state.elapsed=0.
            elif name=='loop':self.state.loop=not self.state.loop
            elif name=='phase':
                values=('lake','teahouse','reveal');old=self.state.shot['preview']['phase']
                self.set_value(('preview','phase'),values[(values.index(old)+1)%3]);self.state.elapsed=min(self.state.elapsed,self.duration)
            elif name=='reset_actor':self.reset_actor()
            elif name=='use_game_view':
                if self._game_pose is None:
                    self.status='No captured game view. Open this editor with F2 while playing to use this button.'
                else:
                    def capture(shot):
                        if shot['movement']=='follow' and self._game_actor is not None:
                            offset=[v-a for v,a in zip(self._game_actor,shot['preview']['actor'])]
                            for key in ('start','end'):shot[key]['eye']=[v+d for v,d in zip(shot[key]['eye'],offset)]
                            shot['preview']['actor']=list(self._game_actor);shot['preview']['yaw']=self._game_yaw
                        shot[self.state.key]=deepcopy(self._game_pose)
                    self.state.change(capture);self.preview=False;self.state.playing=False;self.reset_actor()
                    self.status='Captured game view into '+self.state.key.upper()+'. Preview still applies the selected movement and aim.'
            elif name=='follow_reference':
                actor=[self.actor.x,self.actor.height,self.actor.z]
                def reanchor(shot):
                    offset=[v-a for v,a in zip(actor,shot['preview']['actor'])]
                    if shot['movement']=='follow':
                        for key in ('start','end'):shot[key]['eye']=[v+d for v,d in zip(shot[key]['eye'],offset)]
                    shot['preview']['actor']=actor;shot['preview']['yaw']=self.actor.yaw
                self.state.change(reanchor);self.status='Follow reference updated; its current camera position is preserved.'
            elif name.startswith('cycle:'):
                prop=name[6:];values={'movement':('locked','path','follow'),'aim':('fixed','pan','player','keep_visible'),
                                    'lens':('fixed','zoom'),'easing':('linear','smooth')}[prop]
                self.set_value((prop,),values[(values.index(self.state.shot[prop])+1)%len(values)])
            elif name=='enabled':self.set_value(('enabled',),not self.state.shot['enabled'])
            elif name=='activation_type':
                values=('lake','room','focus','reveal','zone');self.activation(values[(values.index(self.state.shot['activation']['type'])+1)%5])
            elif name=='zone_phase':
                values=('any','lake','teahouse');self.set_value(('activation','phase'),values[(values.index(self.state.shot['activation']['phase'])+1)%3])
            elif name=='zone_actor':
                act=self.state.shot['activation'];a,b=act['bounds']['min'],act['bounds']['max'];mid=(self.actor.x,self.actor.height+1.,self.actor.z)
                bounds={'min':[mid[i]-(b[i]-a[i])*.5 for i in range(3)],'max':[mid[i]+(b[i]-a[i])*.5 for i in range(3)]}
                self.set_value(('activation','bounds'),bounds)
            elif name=='aim_player':
                frame=deepcopy(self.state.frame);frame['target']=[self.actor.x,self.actor.height+.95,self.actor.z];self.state.set_frame(frame)
            elif name=='match_key':self.set_value(('end' if self.state.key=='start' else 'start',),deepcopy(self.state.frame))
            elif name=='hold':
                frame=deepcopy(self.state.frame)
                self.state.change(lambda shot:shot.update(start=deepcopy(frame),end=deepcopy(frame),movement='locked',aim='fixed',lens='fixed'))
            elif name in ('duplicate','new_zone'):
                self.state.duplicate()
                if name=='new_zone':self.activation('zone');self.tab='activation'
                self.ensure_selected_visible();self.reset_actor()
            elif name=='remove':self.state.remove();self.ensure_selected_visible();self.reset_actor()
        except (OSError,ValueError,TypeError,KeyError,OverflowError,CameraConflictError) as exc:
            self.status=str(exc)
            if self.close_prompt:self.close_error=str(exc)

    def handle(self,event,dt):
        self.events=event;dt=max(0.,min(.1,float(dt)));control=bool(event.down&{'LEFT_CONTROL','RIGHT_CONTROL'});shift=bool(event.down&{'LEFT_SHIFT','RIGHT_SHIFT'})
        self._poll_elapsed+=dt
        if self.live_enabled and self._poll_elapsed>=.5 and not(self.entry or self.drag or self.close_prompt):
            self._poll_elapsed=0.;selected=self.state.selected;elapsed=self.state.elapsed
            try:
                if self.state.poll():
                    if self.state.selected!=selected:self.reset_actor()
                    else:self.state.elapsed=min(elapsed,self.duration)
                    self.ensure_selected_visible()
                    self.status='Live camera edits reloaded. Preview position and playhead retained.'
            except (OSError,ValueError,TypeError,KeyError) as exc:self.status=str(exc)
        if self.entry:
            close_click=event.left_pressed and any(name=='close' and contains(rect,event.mouse) for name,_,rect,_ in self.controls()[0])
            if 'F2' in event.pressed or close_click:
                self.action('close');return
            if control and 'S' in event.pressed:
                if self.finish_entry():self.action('save')
                return
            for char in event.chars:
                if self.entry['path']==('label',) or char in '0123456789+-.eE':
                    if self.entry['replace']:self.entry['text']='';self.entry['replace']=False
                    if len(self.entry['text'])<100:self.entry['text']+=char
            if 'BACKSPACE' in event.pressed:self.entry['text']='' if self.entry['replace'] else self.entry['text'][:-1];self.entry['replace']=False
            if 'ESCAPE' in event.pressed:self.finish_entry(True);return
            if 'ENTER' in event.pressed:self.finish_entry();return
            if event.left_pressed:
                rect=next((r for p,r in self.controls()[1] if p==self.entry['path']),None)
                if rect is None or not contains(rect,event.mouse):
                    if not self.finish_entry():return
            if self.entry:return
        if self.close_prompt:
            if 'ESCAPE' in event.pressed:self.action('close_cancel');return
            if event.left_pressed:
                for name,_,rect,_ in self.controls()[0]:
                    if contains(rect,event.mouse):self.action(name);return
            return
        if self.drag:
            drag=self.drag
            if 'ESCAPE' in event.pressed:self.finish_drag(True);return
            if drag['kind']=='seek':
                self.seek(self.time_at(event.mouse[0]))
                if event.left_released or not event.left_down:self.finish_drag()
            elif drag['kind']=='fly':
                if event.right_released or not event.right_down:self.finish_drag()
                else:
                    if event.wheel:self.speed=max(.1,min(50.,self.speed*1.25**event.wheel))
                    movement=(int('D' in event.down)-int('A' in event.down),int('W' in event.down)-int('S' in event.down),int('E' in event.down)-int('Q' in event.down))
                    self.state.shot[self.state.key]=fly_pose(self.state.frame,event.delta if drag['ready'] else (0,0),movement,dt,self.speed*(3 if shift else .25 if control else 1));drag['ready']=True
            else:
                if event.middle_released or not event.middle_down:self.finish_drag()
                else:self.state.shot[self.state.key]=orbit_pose(self.state.frame,event.delta,shift)
            return
        if event.pressed&{'ESCAPE','F2'}:self.action('close');return
        if control:
            for key,name in (('S','save'),('O','reload'),('Z','undo'),('Y','redo')):
                if key in event.pressed:self.action(name)
        else:
            if 'SPACE' in event.pressed:self.action('play')
            if 'HOME' in event.pressed:self.seek(0.)
            if 'LEFT' in event.pressed:self.seek(self.state.elapsed-(1. if shift else 1/30))
            if 'RIGHT' in event.pressed:self.seek(self.state.elapsed+(1. if shift else 1/30))
        a=self.layout()
        if event.left_pressed:
            for name,_,rect,_ in self.controls()[0]:
                if contains(rect,event.mouse):self.action(name);return
            for path,rect in self.controls()[1]:
                if contains(rect,event.mouse):self.edit_field(path);return
            if contains(a['timeline'],event.mouse):self.seek(self.time_at(event.mouse[0]));self.drag={'kind':'seek'};return
        if event.wheel and contains(a['list'],event.mouse):self.scroll=max(0,self.scroll-int(event.wheel));return
        if contains(a['viewport'],event.mouse):
            if event.right_pressed or event.middle_pressed or event.wheel:
                if self.preview:self.status='Camera flight is disabled in Preview. Click Preview behavior to edit camera keys.'
                elif event.wheel:
                    frame=deepcopy(self.state.frame);frame['fov']=max(15.,min(110.,frame['fov']-event.wheel*(.5 if shift else 2.)));self.state.set_frame(frame)
                else:
                    self.state.playing=False;self.drag=dict(kind='fly' if event.right_pressed else 'orbit',before=self.state.checkpoint(),ready=False)
                    if event.right_pressed and self.live_input:pr.disable_cursor()
        if self.preview and not control and not event.right_down:
            self.actor.tick(dt,int('W' in event.down)-int('S' in event.down),int('D' in event.down)-int('A' in event.down),shift)
        if self.state.playing:
            self.state.elapsed+=dt
            if self.state.elapsed>=self.duration:
                if self.state.loop:self.state.elapsed%=self.duration
                else:self.state.elapsed=self.duration;self.state.playing=False

    def update(self,dt,events=None):self.handle(events or Input.read(),dt)

    def time_at(self,x):
        rect=self.layout()['timeline'];return (x-rect[0])/rect[2]*self.duration

    def sync(self):
        q=self.sequence;phase=self.state.shot['preview']['phase'];t=self.state.elapsed
        q.focus=False;q.elapsed=t;q.locked_camera=None;q.locked_pose=None
        q.approach=causeway_progress(self.actor.x,self.actor.z);q.return_progress=1.-q.approach
        if phase=='reveal':q.state='entering' if t<ENTRY_DURATION else 'revealed';q.revealed=t>=ENTRY_SWAP;q.entry_veil=.72;q.entry_arrival=.93
        else:q.state='revealed' if phase=='teahouse' else 'ordinary';q.revealed=phase=='teahouse'
        self.scene.sequence=q;self.actor.encounter=q

    def render_scene(self):
        self.sync()
        frame=sample_shot(self.state.shot,self.state.elapsed,self.actor) if self.preview else self.state.frame
        if not isinstance(frame,dict):frame={'eye':frame.eye,'target':frame.target,'fov':frame.fov}
        self.preview_camera=camera_from_pose(frame)
        self.scene.render(self.actor,self.clock+self.state.elapsed,override=self.preview_camera,authoring=True)
        return self.preview_camera

    @staticmethod
    def draw_button(title,rect,active=False):
        pr.draw_rectangle_rec(pr.Rectangle(*rect),BLUE if active else FIELD)
        pr.draw_text(label(title,rect[2]-14,13),int(rect[0]+7),int(rect[1]+(rect[3]-13)/2),13,INK)

    def draw_zone_guides(self,viewport):
        activation=self.state.shot['activation'];cam=self.preview_camera
        if self.tab!='activation' or activation['type']!='zone' or cam is None:return
        low,high=activation['bounds']['min'],activation['bounds']['max']
        eye=(cam.position.x,cam.position.y,cam.position.z)
        forward=(cam.target.x-eye[0],cam.target.y-eye[1],cam.target.z-eye[2]);length=math.sqrt(sum(v*v for v in forward))
        corners=[tuple((high if i&(1<<axis) else low)[axis] for axis in range(3)) for i in range(8)]
        front=[sum((p[axis]-eye[axis])*forward[axis] for axis in range(3))>.05*length for p in corners]
        points=[]
        for p,visible in zip(corners,front):
            if not visible:points.append(None);continue
            point=pr.get_world_to_screen_ex(pr.Vector3(*p),cam,WIDTH,HEIGHT)
            points.append(pr.Vector2(viewport[0]+point.x/WIDTH*viewport[2],viewport[1]+point.y/HEIGHT*viewport[3]))
        actor=(self.actor.x,self.actor.height,self.actor.z)
        inside=all(a<=v<=b for a,v,b in zip(low,actor,high))
        phase='teahouse' if self.sequence.revealed else 'lake'
        eligible=inside and self.state.shot['enabled'] and activation['phase'] in ('any',phase)
        colour=pr.Color(129,208,173,220) if eligible else pr.Color(228,183,113,195)
        pr.begin_scissor_mode(*(int(v) for v in viewport))
        try:
            for i in range(8):
                for bit in (1,2,4):
                    other=i^bit
                    if i<other and points[i] is not None and points[other] is not None:pr.draw_line_ex(points[i],points[other],1.5,colour)
            title='Actor '+('inside' if inside else 'outside')+' zone'
            if inside and not self.state.shot['enabled']:title+=' / override OFF'
            elif inside and not eligible:title+=' / different world'
            pr.draw_rectangle(int(viewport[0]+6),int(viewport[1]+6),min(int(viewport[2]-12),pr.measure_text(title,12)+16),25,pr.Color(13,20,23,220))
            pr.draw_text(title,int(viewport[0]+14),int(viewport[1]+13),12,colour)
        finally:pr.end_scissor_mode()

    def draw(self):
        a=self.layout();w,h,b=a['w'],a['h'],a['bottom'];x=a['right']+14
        pr.clear_background(BG);pr.draw_rectangle(0,0,w,58,PANEL);pr.draw_rectangle(0,60,a['left'],b-60,PANEL)
        pr.draw_rectangle(a['right'],60,w-a['right'],b-60,PANEL);pr.draw_rectangle(0,b,w,h-b,PANEL)
        pr.draw_text('MOON CAMERAS'+(' *' if self.state.dirty else ''),14,14,21,INK)
        pr.draw_text('CINEMATOGRAPHER / isolated preview',14,39,10,MUTED)
        pr.draw_text('SHOTS / scroll for more',14,77,12,MUTED)
        prompt=self.close_prompt;self.close_prompt=False;buttons,fields=self.controls();self.close_prompt=prompt
        for name,title,rect,active in buttons:
            if name.startswith('shot:'):
                shot=next(s for s in self.state.document['shots'] if s['id']==name[5:]);self.draw_button('',rect,active)
                pr.draw_text(label(title,rect[2]-14,12),int(rect[0]+7),int(rect[1]+5),12,INK)
                pr.draw_text(shot['activation']['type'].upper()+(' / OFF' if not shot['enabled'] else ''),int(rect[0]+7),int(rect[1]+23),10,MUTED)
            else:self.draw_button(title,rect,active)
        for title,lx,ly in self._labels:pr.draw_text(label(title,310,11),int(lx),int(ly),11,MUTED)
        for path,rect in fields:
            active=self.entry is not None and self.entry['path']==path
            pr.draw_rectangle_rec(pr.Rectangle(*rect),BLUE if active else FIELD)
            value=self.entry['text']+'_' if active else str(self.field_value(path)) if path==('label',) else f'{self.field_value(path):.2f}'
            if isinstance(path[-1],int):value='XYZ'[path[-1]]+' '+value
            pr.draw_text(label(value,rect[2]-12,13),int(rect[0]+6),int(rect[1]+9),13,INK)
        viewport=a['viewport']
        pr.draw_texture_pro(self.scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(*viewport),pr.Vector2(0,0),0,pr.WHITE)
        self.draw_zone_guides(viewport)
        heading='PREVIEW / behavior active / mouse camera edits disabled' if self.preview else 'EDIT '+self.state.key.upper()+' / direct key editing'
        pr.draw_text(label(heading,a['right']-a['left']-36,13),a['left']+18,111,13,ACCENT)
        pr.draw_text('Preview: WASD moves / turns the test actor. Your game is untouched.',a['left']+18,b-74,11,MUTED)
        pr.draw_text(label(self.state.shot['label'],a['right']-a['left']-36,16),a['left']+18,b-44,16,INK)
        pr.draw_text(label(getattr(self.state,'error',None) or self.status,w-220,12),16,b+12,12,ACCENT)
        pr.draw_text('Unsaved changes' if self.state.dirty else 'Saved / unchanged',w-180,b+12,12,MUTED)
        tx,ty,tw,th=a['timeline'];pr.draw_rectangle_rec(pr.Rectangle(tx,ty,tw,th),FIELD)
        px=tx+tw*self.state.elapsed/self.duration;pr.draw_rectangle(int(tx),int(ty),max(1,int(px-tx)),int(th),BLUE)
        for frac in (0.,.25,.5,.75,1.):
            xx=tx+tw*frac;pr.draw_line(int(xx),int(ty-5),int(xx),int(ty+th+5),MUTED)
            pr.draw_text(f'{self.duration*frac:.1f}s',int(min(w-64,xx)),int(ty-20),10,MUTED)
        pr.draw_line_ex(pr.Vector2(px,ty-7),pr.Vector2(px,ty+th+7),2,ACCENT)
        pr.draw_text(f'{self.state.elapsed:06.2f}s  /  Space play  /  arrows frame step  /  Shift+arrow 1s  /  Ctrl+S save',24,h-25,12,INK)
        if prompt:
            pr.draw_rectangle(0,0,w,h,pr.Color(0,0,0,195));cx,cy=w/2-253,h/2-90
            pr.draw_rectangle(int(cx),int(cy),506,155,PANEL)
            pr.draw_text('Keep your camera edits?',int(cx+18),int(cy+17),22,INK)
            pr.draw_text('Save, discard, or return to editing.',int(cx+18),int(cy+51),13,MUTED)
            if self.close_error:pr.draw_text(label(self.close_error,470,11),int(cx+18),int(cy+76),11,ACCENT)
            for _,title,rect,active in self.controls()[0]:self.draw_button(title,rect,active)

    def release(self):
        if self._released:return
        self.finish_drag(cancel=True);self.finish_entry(cancel=True)
        for name,value in self._previous.items():setattr(self.scene,name,value)
        self._released=True
        if self.live_input:pr.enable_cursor()


Editor=MoonCinematographer


def editor_loop(editor):
    editor.render_scene();pr.begin_drawing();editor.draw();pr.end_drawing()
    close_requested=False
    while not editor.closed:
        requested=pr.window_should_close()
        if not requested:close_requested=False
        elif not close_requested:close_requested=True;editor.action('close')
        if editor.closed:break
        editor.update(min(pr.get_frame_time(),.1))
        if editor.closed:break
        editor.render_scene();pr.begin_drawing();editor.draw();pr.end_drawing()


def edit_scene(scene,actor=None,clock=0.,path=None):
    pr.enable_cursor();editor=MoonCinematographer(scene,actor,clock,path)
    try:editor_loop(editor);return not editor.state.dirty
    finally:editor.release();pr.enable_cursor()


def run(path=DEFAULT_PATH):
    from huxin_moon_viewer import Lake
    pr.set_config_flags(pr.FLAG_WINDOW_RESIZABLE);pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(1440,900,'The Moon in the Water / Cinematographer');pr.set_window_min_size(1360,900)
    pr.set_target_fps(60);pr.set_exit_key(pr.KEY_NULL);scene=None
    try:scene=Lake();edit_scene(scene,path=path)
    finally:
        if scene:scene.close()
        pr.enable_cursor();pr.close_window()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Author Moon scene cameras against an isolated real-scene preview.')
    parser.add_argument('--direction',type=Path,default=DEFAULT_PATH)
    run(parser.parse_args().direction)
