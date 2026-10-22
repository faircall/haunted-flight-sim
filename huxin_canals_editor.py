"""Native direction editor for the Void Canals fog reveal."""
if __name__ == '__main__':
    from setup_temple_3d import ensure_runtime
    ensure_runtime()

from copy import deepcopy
from pathlib import Path
import math
import pyray as pr

from g_huxin_canals_editor import DirectionEditor
from g_huxin_canals_direction import CUES, CUE_LABELS, DEFAULT_PATH, default_document, sample_camera
from g_huxin_canals_sequence import CanalSequence
from g_huxin_canals import Explorer, DECK
from g_temple_cinematics import fly_pose, orbit_pose
from temple_cinematics_editor import Input, contains, label
from temple_interior_viewer import camera
from huxin_canals_viewer import Lake, WIDTH, HEIGHT
from codex_selection import SelectionSession

BG=pr.Color(13,20,23,255); PANEL=pr.Color(21,30,34,255); FIELD=pr.Color(31,43,48,255)
INK=pr.Color(221,232,229,255); MUTED=pr.Color(133,160,163,255)
ACCENT=pr.Color(228,183,113,255); BLUE=pr.Color(58,106,122,255); GREEN=pr.Color(61,119,104,255)
AXES=(pr.Color(235,128,116,255),pr.Color(135,209,139,255),pr.Color(116,177,237,255))
SHORT_LABELS=('Puzzle activated','Fog fully formed','Hidden blend finished','Middle starts clearing',
              'Nearby mostly clear','Distant starts clearing','Middle mostly clear','Distant mostly clear','Last traces gone')


def pose_dict(pose):return dict(eye=list(pose.eye),target=list(pose.target),fov=pose.fov)


class Editor:
    def __init__(self,scene,actor=None,path=DEFAULT_PATH,document=None,live_input=True,selection_output_path=None):
        self.scene=scene;self.state=DirectionEditor(document,path)
        self.state.select('build_end')
        self.actor=Explorer();self.actor.x,self.actor.height,self.actor.z=1.65,DECK,1.65
        self.actor.yaw=math.atan2(1.35-self.actor.x,self.actor.z+.15);self.actor.shot=5
        if actor is not None:
            for name in ('x','height','z','yaw','phase','shot'):setattr(self.actor,name,getattr(actor,name))
        self.actor.clip='idle'
        self.live_input=live_input;self.events=Input();self.drag=None;self.entry=None
        self.tab='fog';self.speed=3.;self.guides=True;self.closed=False;self.close_prompt=False
        self.status='Select a point to jump. Drag timeline markers to retime the reveal.'
        self.preview_camera=None;self.inspection=None;self._profile=None;self._released=False
        self._previous_sequence=scene.sequence
        self._previous_selection=getattr(scene,'codex_selection',None)
        self._previous_paused=getattr(scene,'_codex_frame_paused',False)
        self._previous_camera=scene.last_camera;self._previous_shot=scene.last_shot
        self._previous_pose=getattr(scene,'last_pose',None)
        self.selection=SelectionSession('huxin_canals_editor',__file__,selection_output_path)
        self.sync()

    def layout(self):
        w,h=pr.get_screen_width(),pr.get_screen_height();left=236;right=w-300;bottom=h-190
        area=(left+18,108,right-left-36,bottom-185)
        scale=max(.1,min(area[2]/WIDTH,area[3]/HEIGHT))
        viewport=(area[0]+(area[2]-WIDTH*scale)/2,area[1]+(area[3]-HEIGHT*scale)/2,WIDTH*scale,HEIGHT*scale)
        return dict(w=w,h=h,left=left,right=right,bottom=bottom,viewport=viewport,
                    timeline=(26,bottom+61,w-52,24))

    def controls(self):
        a=self.layout();x=a['right']+14;b=a['bottom'];w=a['w']
        buttons=[('play','Pause' if self.state.playing else 'Play',(246,14,70,30),self.state.playing),
                 ('loop','Loop interval',(324,14,108,30),self.state.loop),
                 ('save','Save to game',(448,14,122,30),False),('reload','Reload',(578,14,74,30),False),
                 ('undo','Undo',(660,14,66,30),False),('redo','Redo',(734,14,66,30),False),
                 ('close','Return / exit',(w-142,14,126,30),False),
                 ('previous','Previous point',(a['left']+18,67,126,28),False),
                 ('next','Next point',(a['left']+154,67,110,28),False),
                 ('tab:fog','FOG PLACEMENT',(x,69,134,30),self.tab=='fog'),
                 ('tab:camera','CAMERA',(x+142,69,130,30),self.tab=='camera'),
                 ('game_view','Authored view',(a['left']+18,b-60,122,27),self.inspection is None),
                 ('reverse_view','Reverse view',(a['left']+150,b-60,112,27),self.inspection=='reverse'),
                 ('top_view','Overhead',(a['left']+272,b-60,94,27),self.inspection=='top'),
                 ('guides','Guides',(a['left']+376,b-60,74,27),self.guides),
                 ('defaults','Restore V17 defaults',(12,b-47,211,29),False)]
        for i,cue in enumerate(CUES):
            buttons.append(('cue:'+cue,SHORT_LABELS[i],(10,103+i*43,216,38),cue==self.state.selected))
        fields=[(('time',),(x+140,124,132,32))]
        if self.tab=='fog':
            for i,band in enumerate(('near','middle','far')):
                buttons.append(('bank:'+band,('Nearby','Middle','Distant')[i],(x+i*94,185,86,30),self.state.band==band))
            fields.extend([(('offset',i),(x+i*94,253,86,32)) for i in range(3)])
            fields.extend([(('scale',),(x+140,304,132,32)),(('opacity',),(x+140,348,132,32))])
            for i,(name,title) in enumerate((('x-','X -'),('y-','Y -'),('z-','Z -'),('x+','X +'),('y+','Y +'),('z+','Z +'))):
                buttons.append(('nudge:'+name,title,(x+(i%3)*94,408+(i//3)*38,86,29),False))
            buttons.append(('reset_bank','Reset this bank',(x,500,272,30),False))
        else:
            buttons.append(('camera_enabled','Camera path in game: '+('ON' if self.state.document['cameras']['enabled'] else 'OFF'),(x,185,272,30),self.state.document['cameras']['enabled']))
            fields.extend([((prop,i),(x+i*94,y,86,32)) for prop,y in (('eye',253),('target',322)) for i in range(3)])
            fields.append((('fov',),(x+140,374,132,32)))
            buttons.extend([('match_camera','Hold this view at all points',(x,426,272,30),False),
                            ('reset_camera','Reset selected camera',(x,466,272,30),False)])
        if self.close_prompt:
            x0,y0=w/2-232,a['h']/2-74
            buttons=[('close_save','Save and return',(x0,y0+87,146,33),False),
                     ('close_discard','Discard and return',(x0+157,y0+87,150,33),False),
                     ('close_cancel','Keep editing',(x0+318,y0+87,146,33),False)]
            fields=[]
        return buttons,fields

    def cue_handles(self):
        y=self.layout()['timeline'][1]
        return [(cue,(self.x_at(self.state.document['cues'][cue])-7,y-6,14,37)) for cue in CUES]

    def timeline_end(self):
        if self.drag and self.drag['kind']=='cue':return self.drag['timeline_end']
        return self.state.duration+max(2.,self.state.duration*.08)

    def x_at(self,t):
        x,_,w,_=self.layout()['timeline'];return x+w*t/self.timeline_end()

    def time_at(self,x):
        start,_,width,_=self.layout()['timeline']
        return max(0.,min(self.timeline_end(),(x-start)/width*self.timeline_end()))

    def field_value(self,path):
        prop=path[0]
        if prop=='time':return self.state.document['cues'][self.state.selected]
        source=self.state.bank if prop in ('offset','scale','opacity') else self.state.frame
        return source[prop][path[1]] if len(path)>1 else source[prop]

    def edit_number(self,path):
        self.state.playing=False
        self.entry=dict(path=path,text=f'{self.field_value(path):.3f}',replace=True)
        self.status='Type a number. Enter applies; Escape cancels.'

    def finish_entry(self,cancel=False):
        if not self.entry:return True
        if not cancel:
            try:
                value=float(self.entry['text']);path=self.entry['path'];prop=path[0]
                if prop=='time':self.state.set_time(self.state.selected,value)
                elif prop in ('offset','scale','opacity'):self.state.set_bank(prop,value,path[1] if len(path)>1 else None)
                else:
                    frame=deepcopy(self.state.frame)
                    if len(path)>1:frame[prop][path[1]]=value
                    else:frame[prop]=value
                    self.state.set_camera(frame);self.inspection=None;self.state.select(self.state.selected)
                self.status='Updated. Save to game keeps this edit for normal playback.'
            except (ValueError,TypeError,OverflowError) as exc:self.status=str(exc);return False
        self.entry=None
        return True

    def finish_drag(self,cancel=False):
        if not self.drag:return
        drag=self.drag;self.drag=None
        if 'before' in drag:
            if cancel:self.state.document=drag['before'];self.state.seek(drag['elapsed'])
            else:
                try:self.state.commit(drag['before'])
                except ValueError as exc:self.status=str(exc)
        if drag['kind'] in ('fly','inspect_fly') and self.live_input:pr.enable_cursor()

    def action(self,name):
        self.finish_drag()
        if not self.finish_entry():return
        try:
            if name=='play':
                if self.state.elapsed>=self.state.duration:self.state.elapsed=0.
                if self.state.loop:
                    index=CUES.index(self.state.selected);end=self.state.document['cues'][CUES[index+1]] if index<len(CUES)-1 else self.state.duration
                    if not self.state.document['cues'][self.state.selected]<=self.state.elapsed<end:self.state.elapsed=self.state.document['cues'][self.state.selected]
                self.state.playing=not self.state.playing
            elif name=='loop':self.state.loop=not self.state.loop
            elif name.startswith('cue:'):self.state.select(name[4:])
            elif name.startswith('bank:'):self.state.band=name[5:]
            elif name.startswith('tab:'):self.tab=name[4:]
            elif name in ('previous','next'):
                index=CUES.index(self.state.selected)+(1 if name=='next' else -1)
                self.state.select(CUES[max(0,min(len(CUES)-1,index))])
            elif name=='save':self.state.save();self.status='Saved to direction.json. Normal play uses these settings.'
            elif name=='reload':self.state.reload();self.status='Reloaded saved direction. Undo restores your previous edits.'
            elif name in ('undo','redo'):getattr(self.state,name)();self.status=name.title()+' applied.'
            elif name=='defaults':self.state.defaults();self.status='V17 defaults restored in the editor. Undo or save as needed.'
            elif name=='reset_bank':
                self.state.change(lambda:self.state.document['banks'].__setitem__(self.state.band,deepcopy(default_document()['banks'][self.state.band])))
            elif name.startswith('nudge:'):
                axis='xyz'.index(name[-2]);amount=(-.25 if name[-1]=='-' else .25)
                self.state.set_bank('offset',self.state.bank['offset'][axis]+amount,axis)
            elif name=='camera_enabled':self.state.change(lambda:self.state.document['cameras'].__setitem__('enabled',not self.state.document['cameras']['enabled']))
            elif name=='match_camera':
                frame=deepcopy(self.state.frame)
                def apply():
                    self.state.document['cameras']['keys']={cue:deepcopy(frame) for cue in CUES}
                    self.state.document['cameras']['enabled']=True
                self.state.change(apply)
            elif name=='reset_camera':self.state.set_camera(default_document()['cameras']['keys'][self.state.selected])
            elif name=='game_view':self.inspection=None
            elif name=='reverse_view':self.inspection='reverse'
            elif name=='top_view':self.inspection='top'
            elif name=='guides':self.guides=not self.guides
            elif name=='close':
                self.state.playing=False
                if self.state.dirty:self.close_prompt=True
                else:self.closed=True
            elif name=='close_cancel':self.close_prompt=False
            elif name=='close_save':self.state.save();self.closed=True;self.close_prompt=False
            elif name=='close_discard':
                self.state.document=deepcopy(self.state.saved);self.state.seek(self.state.elapsed)
                self.closed=True;self.close_prompt=False
        except (OSError,ValueError,TypeError,KeyError) as exc:self.status=str(exc)
        self.sync()

    def gizmo_handles(self):
        if not self.guides or self.tab!='fog' or self.state.playing or self.preview_camera is None:return []
        view=self.layout()['viewport'];base=list(self.state.bank['offset']);base[1]+=2.
        def project(p):
            eye=self.preview_camera.position;target=self.preview_camera.target
            if sum((p[i]-(eye.x,eye.y,eye.z)[i])*((target.x,target.y,target.z)[i]-(eye.x,eye.y,eye.z)[i]) for i in range(3))<=0:return None
            point=pr.get_world_to_screen_ex(pr.Vector3(*p),self.preview_camera,WIDTH,HEIGHT)
            return (view[0]+point.x/WIDTH*view[2],view[1]+point.y/HEIGHT*view[3])
        origin=project(base)
        if origin is None:return []
        handles=[]
        for axis in range(3):
            point=base[:];point[axis]+=3.;end=project(point)
            if end is None or not contains(view,end):continue
            if math.dist(origin,end)<8:continue
            handles.append((axis,(end[0]-9,end[1]-9,18,18),origin,end))
        return handles

    def update(self,dt,events=None):
        event=self.events=events or Input.read()
        control=bool(event.down&{'LEFT_CONTROL','RIGHT_CONTROL'});shift=bool(event.down&{'LEFT_SHIFT','RIGHT_SHIFT'})
        if self.close_prompt:
            if 'ESCAPE' in event.pressed:self.action('close_cancel')
            elif event.left_pressed:
                for name,_,rect,_ in self.controls()[0]:
                    if contains(rect,event.mouse):self.action(name);break
            return
        if 'F8' in event.pressed:
            self.finish_drag();self.finish_entry(cancel=True);self.state.playing=False
            self.selection.set_enabled(not self.selection.enabled);return
        if self.selection.enabled:
            if 'ESCAPE' in event.pressed:self.selection.set_enabled(False)
            elif 'BACKSPACE' in event.pressed:self.selection.clear()
            return
        if self.entry:
            for char in event.chars:
                if char in '0123456789+-.eE':
                    if self.entry['replace']:self.entry['text']='';self.entry['replace']=False
                    if len(self.entry['text'])<24:self.entry['text']+=char
            if 'BACKSPACE' in event.pressed:
                self.entry['text']='' if self.entry['replace'] else self.entry['text'][:-1];self.entry['replace']=False
            if 'ESCAPE' in event.pressed:self.finish_entry(True);return
            if 'ENTER' in event.pressed:self.finish_entry()
            elif event.left_pressed:
                active=next(rect for path,rect in self.controls()[1] if path==self.entry['path'])
                if not contains(active,event.mouse):self.finish_entry()
            if self.entry:return
        if self.drag:
            drag=self.drag;kind=drag['kind']
            if 'ESCAPE' in event.pressed:self.finish_drag(True);self.sync();return
            if kind=='cue':
                if abs(event.mouse[0]-drag['mouse'][0])>2:drag['moved']=True
                if drag['moved']:
                    cue=drag['cue'];value=round(self.time_at(event.mouse[0]),2 if shift else 1)
                    self.state.document['cues'][cue]=self.state.clamp_time(cue,value)
                    self.state.elapsed=self.state.document['cues'][cue]
                if event.left_released or not event.left_down:self.finish_drag()
            elif kind=='seek':
                self.state.seek(self.time_at(event.mouse[0]))
                if event.left_released or not event.left_down:self.finish_drag()
            elif kind=='bank':
                dx,dy=drag['vector'];length=dx*dx+dy*dy
                travel=((event.mouse[0]-drag['mouse'][0])*dx+(event.mouse[1]-drag['mouse'][1])*dy)/length*3.
                self.state.bank['offset'][drag['axis']]=max(-1000.,min(1000.,drag['value']+travel))
                if event.left_released or not event.left_down:self.finish_drag()
            elif kind in ('fly','inspect_fly'):
                if event.right_released or not event.right_down:self.finish_drag()
                else:
                    if event.wheel:self.speed=max(.1,min(50.,self.speed*1.25**event.wheel))
                    movement=(int('D' in event.down)-int('A' in event.down),int('W' in event.down)-int('S' in event.down),int('E' in event.down)-int('Q' in event.down))
                    frame=fly_pose(self.inspection if kind=='inspect_fly' else self.state.frame,event.delta if drag['ready'] else (0,0),movement,dt,self.speed*(3 if shift else .25 if control else 1))
                    if kind=='inspect_fly':self.inspection=frame
                    else:
                        self.state.document['cameras']['keys'][self.state.selected]=frame
                        self.state.document['cameras']['enabled']=True
                    drag['ready']=True
            elif kind in ('orbit','inspect_orbit'):
                if event.middle_released or not event.middle_down:self.finish_drag()
                else:
                    if kind=='inspect_orbit':self.inspection=orbit_pose(self.inspection,event.delta,shift)
                    else:
                        self.state.document['cameras']['keys'][self.state.selected]=orbit_pose(self.state.frame,event.delta,shift)
                        self.state.document['cameras']['enabled']=True
            self.sync();return
        if event.pressed&{'ESCAPE','F2'}:self.action('close');return
        if control:
            for key,name in (('S','save'),('O','reload'),('Z','undo'),('Y','redo')):
                if key in event.pressed:self.action(name)
        else:
            if 'SPACE' in event.pressed:self.action('play')
            if 'HOME' in event.pressed:self.state.select('start')
            if 'LEFT' in event.pressed:self.state.seek(self.state.elapsed-(1. if shift else 1/30))
            if 'RIGHT' in event.pressed:self.state.seek(self.state.elapsed+(1. if shift else 1/30))
        if event.left_pressed:
            for name,_,rect,_ in self.controls()[0]:
                if contains(rect,event.mouse):self.action(name);return
            for path,rect in self.controls()[1]:
                if contains(rect,event.mouse):self.edit_number(path);return
            for axis,rect,origin,end in self.gizmo_handles():
                if contains(rect,event.mouse):
                    self.state.playing=False
                    self.drag=dict(kind='bank',axis=axis,mouse=event.mouse,vector=(end[0]-origin[0],end[1]-origin[1]),
                                   value=self.state.bank['offset'][axis],before=self.state.checkpoint(),elapsed=self.state.elapsed)
                    return
            hits=[(abs(rect[0]+rect[2]/2-event.mouse[0]),cue) for cue,rect in self.cue_handles() if contains(rect,event.mouse)]
            if hits:
                cue=min(hits)[1];self.state.select(cue)
                if cue!='start':self.drag=dict(kind='cue',cue=cue,before=self.state.checkpoint(),elapsed=self.state.elapsed,timeline_end=self.timeline_end(),mouse=event.mouse,moved=False)
                return
            timeline=self.layout()['timeline']
            if contains((timeline[0],timeline[1]-23,timeline[2],113),event.mouse):
                self.state.seek(self.time_at(event.mouse[0]));self.drag=dict(kind='seek');return
        if contains(self.layout()['viewport'],event.mouse):
            if event.right_pressed or event.middle_pressed:
                if self.tab=='camera':
                    self.state.select(self.state.selected);self.inspection=None
                    self.drag=dict(kind='fly' if event.right_pressed else 'orbit',before=self.state.checkpoint(),elapsed=self.state.elapsed,ready=False)
                else:
                    self.state.playing=False;self.inspection=self.current_frame()
                    self.drag=dict(kind='inspect_fly' if event.right_pressed else 'inspect_orbit',elapsed=self.state.elapsed,ready=False)
                if event.right_pressed and self.live_input:pr.disable_cursor()
            elif self.tab=='camera' and event.wheel:
                frame=deepcopy(self.state.frame);frame['fov']=max(15.,min(110.,frame['fov']-event.wheel*(.5 if shift else 2.)))
                self.state.set_camera(frame);self.state.select(self.state.selected);self.inspection=None
            elif event.wheel:
                frame=self.current_frame();frame['fov']=max(15.,min(110.,frame['fov']-event.wheel*2.));self.inspection=frame
        self.state.tick(dt);self.sync()

    def sync(self):
        try:profile=self.state.profile
        except (ValueError,TypeError,KeyError) as exc:
            # A continuous camera gesture can briefly propose a singular
            # look-at path. Keep its last valid preview instead of crashing.
            self.status=str(exc)
            self.state.document=deepcopy(self.state._profile_document or self.state.saved)
            self.state.elapsed=min(self.state.elapsed,self.state.duration)
            profile=self.state.profile
        if profile!=self._profile:
            self.scene.sequence=CanalSequence(direction=profile);self._profile=profile
        self.scene.sequence.seek(self.state.elapsed)
        self.actor.encounter=self.scene.sequence

    def current_frame(self):
        if isinstance(self.inspection,dict):return deepcopy(self.inspection)
        pose=sample_camera(self.state.profile,self.state.elapsed,include_disabled=True)
        frame=pose_dict(pose) if pose is not None else deepcopy(self.state.frame)
        if self.inspection=='reverse':frame=dict(eye=[3.5,3.1,-3.5],target=[-1.,2.1,7.],fov=78.)
        elif self.inspection=='top':frame=dict(eye=[0.,48.,20.],target=[0.,0.,0.],fov=65.)
        return frame

    def render_scene(self):
        self.sync()
        frame=self.current_frame()
        self.preview_camera=camera(frame['eye'],frame['target'],frame['fov'])
        self.scene.codex_selection=self.selection
        self.scene._codex_frame_paused=True
        self.selection.begin_frame()
        # Seeking must not retain a partly blended walk/run pose from gameplay.
        self.scene.player.pose('idle',(87.+self.state.elapsed)/2,dt=None)
        self.scene.render(self.actor,87.+self.state.elapsed,override=self.preview_camera,editor_override=True)
        return self.preview_camera

    def draw_button(self,title,rect,selected=False):
        colour=BLUE if selected else FIELD
        if contains(rect,self.events.mouse):colour=pr.Color(min(255,colour.r+12),min(255,colour.g+12),min(255,colour.b+12),255)
        pr.draw_rectangle_rec(pr.Rectangle(*rect),colour)
        size=13
        title=label(title,rect[2]-12,size)
        pr.draw_text(title,int(rect[0]+(rect[2]-pr.measure_text(title,size))/2),int(rect[1]+(rect[3]-size)/2),size,INK)

    def draw(self):
        a=self.layout();w,h,b=a['w'],a['h'],a['bottom'];x=a['right']+14
        pr.clear_background(BG);pr.draw_rectangle(0,0,w,57,PANEL)
        pr.draw_rectangle(0,58,a['left'],b-58,PANEL);pr.draw_rectangle(a['right'],58,w-a['right'],b-58,PANEL)
        pr.draw_text('VOID CANALS'+(' *' if self.state.dirty else ''),14,12,21,INK)
        pr.draw_text('FOG / DIRECTION EDITOR',14,37,10,MUTED)
        pr.draw_text('JUMP POINTS',13,76,15,INK)
        buttons,fields=self.controls()
        # Draw the standard interface underneath a dirty-close dialog as well.
        prompt=self.close_prompt;self.close_prompt=False;normal_buttons,normal_fields=self.controls();self.close_prompt=prompt
        for name,title,rect,active in normal_buttons:
            if name.startswith('cue:'):
                cue=name[4:];self.draw_button('',rect,active)
                pr.draw_text(title,int(rect[0]+8),int(rect[1]+6),12,INK)
                pr.draw_text(f"{self.state.document['cues'][cue]:05.2f} s",int(rect[0]+8),int(rect[1]+22),11,ACCENT)
            else:self.draw_button(title,rect,active)
        pr.draw_text('POINT TIME / seconds',x,107,11,MUTED)
        pr.draw_text('Fixed start' if self.state.selected=='start' else 'Exact time',x,135,13,MUTED)
        pr.draw_text(f'{self.state.elapsed:06.2f} s',a['right']-123,76,18,ACCENT)
        if self.tab=='fog':
            pr.draw_text('SPAWN BANK',x,165,12,MUTED)
            pr.draw_text('OFFSET / world metres',x,233,12,MUTED)
            pr.draw_text('Spread / size',x,314,13,INK);pr.draw_text('Opacity multiplier',x,358,13,INK)
            pr.draw_text('NUDGE / 0.25 metres',x,387,11,MUTED)
            pr.draw_text('Drag the coloured X / Y / Z handles',x,548,11,MUTED)
            pr.draw_text('to move this entire spawn bank.',x,565,11,MUTED)
            pr.draw_text('RMB + WASD: inspect without editing',x,584,10,MUTED)
        else:
            pr.draw_text('POSITION / world metres',x,233,12,MUTED)
            pr.draw_text('LOOK AT / world metres',x,302,12,MUTED)
            pr.draw_text('Lens / degrees',x,384,13,INK)
            pr.draw_text('RMB + WASD: fly  /  Q,E: down,up',x,515,11,MUTED)
            pr.draw_text('MMB: orbit  /  Shift+MMB: pan',x,533,11,MUTED)
            pr.draw_text('Camera edits enable the saved path.',x,557,11,MUTED)
        for path,rect in normal_fields:
            active=self.entry is not None and self.entry['path']==path
            pr.draw_rectangle_rec(pr.Rectangle(*rect),BLUE if active else FIELD)
            prefix=('XYZ'[path[1]]+' ') if len(path)>1 else ''
            value=self.entry['text']+'_' if active else f'{self.field_value(path):.2f}'
            pr.draw_text(label(prefix+value,rect[2]-10,13),int(rect[0]+5),int(rect[1]+10),13,INK)
        viewport=a['viewport']
        pr.draw_texture_pro(self.scene.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),pr.Rectangle(*viewport),pr.Vector2(0,0),0,pr.WHITE)
        for axis,rect,origin,end in self.gizmo_handles():
            pr.draw_line_ex(pr.Vector2(*origin),pr.Vector2(*end),2,AXES[axis])
            pr.draw_rectangle_rec(pr.Rectangle(*rect),AXES[axis])
            pr.draw_text('XYZ'[axis],int(rect[0]+5),int(rect[1]+3),12,BG)
        pr.draw_text(label(CUE_LABELS[self.state.selected],a['right']-a['left']-44,14),a['left']+18,b-86,14,INK)
        pr.draw_text('F8: Codex selection  /  Space: play  /  arrows: frame step',a['left']+18,b-21,11,MUTED)
        pr.draw_rectangle(0,b,w,h-b,PANEL)
        pr.draw_text(label(self.status,w-230,13),16,b+10,13,ACCENT)
        pr.draw_text('Unsaved changes' if self.state.dirty else 'Saved to game',w-166,b+10,12,ACCENT if self.state.dirty else MUTED)
        timeline=a['timeline'];ty=timeline[1]
        step=5 if self.state.duration<=90 else 10 if self.state.duration<=240 else 60
        for t in range(0,int(self.timeline_end())+1,step):
            px=self.x_at(t);pr.draw_line(int(px),int(ty-15),int(px),int(ty+94),pr.Color(80,105,110,60))
            pr.draw_text(f'{t}s',int(px)+3,int(ty-20),10,MUTED)
        for i,cue in enumerate(CUES[:-1]):
            left=self.x_at(self.state.document['cues'][cue]);right=self.x_at(self.state.document['cues'][CUES[i+1]])
            pr.draw_rectangle(int(left),int(ty),max(1,int(right-left)-1),24,BLUE if i<2 else FIELD)
        for cue,rect in self.cue_handles():
            px=rect[0]+7;pr.draw_rectangle(int(px)-2,int(ty)-3,4,30,ACCENT if cue==self.state.selected else INK)
        tracks=(('near','blend_end','near_end'),('middle','middle_start','middle_end'),('far','far_start','far_end'))
        for i,(band,start,end) in enumerate(tracks):
            left=self.x_at(self.state.document['cues'][start]);right=self.x_at(self.state.document['cues'][end]);y=ty+36+i*18
            pr.draw_rectangle(int(left),int(y),max(1,int(right-left)),13,GREEN if band==self.state.band else BLUE)
            pr.draw_text(band.upper(),int(left)+4,int(y)+1,10,INK)
        cursor=self.x_at(self.state.elapsed)
        pr.draw_line_ex(pr.Vector2(cursor,ty-23),pr.Vector2(cursor,ty+91),2,ACCENT)
        pr.draw_text('MARKERS: drag to retime  /  TRACKS: click to scrub  /  Shift: finer adjustments',16,h-18,11,MUTED)
        if self.preview_camera is not None:
            self.selection.present(self.preview_camera,viewport,{'world':'canals' if self.scene.sequence.world_blend>=.5 else 'lake',
                'phase':self.scene.sequence.state,'time':self.state.elapsed,'cue':self.state.selected,'fog_bank':self.state.band})
        if prompt:
            pr.draw_rectangle(0,0,w,h,pr.Color(0,0,0,195));x0,y0=w/2-252,h/2-96
            pr.draw_rectangle(int(x0),int(y0),504,170,PANEL)
            pr.draw_text('Keep your scene edits?',int(x0)+20,int(y0)+19,22,INK)
            pr.draw_text('Save them to the game, discard them, or keep editing.',int(x0)+20,int(y0)+55,13,MUTED)
            for _,title,rect,active in buttons:self.draw_button(title,rect,active)

    def close(self):
        if self._released:return
        self.finish_drag(cancel=True);self.finish_entry(cancel=True)
        self.selection.close();self.scene.codex_selection=self._previous_selection
        self.scene.sequence=self._previous_sequence;self.scene.last_camera=self._previous_camera
        self.scene.last_shot=self._previous_shot;self.scene.last_pose=self._previous_pose
        self.scene._codex_frame_paused=self._previous_paused
        self._released=True


def editor_loop(editor):
    """Always draw before reading the F2 press that opened an embedded editor."""
    close_requested=False
    editor.render_scene();pr.begin_drawing();editor.draw();pr.end_drawing()
    while not editor.closed:
        requested=pr.window_should_close()
        if not requested:close_requested=False
        elif not close_requested:
            close_requested=True;editor.action('close')
        editor.update(min(pr.get_frame_time(),.1))
        editor.render_scene();pr.begin_drawing();editor.draw();pr.end_drawing()


def run_embedded(scene,e,audio,clock):
    old_size=(pr.get_screen_width(),pr.get_screen_height())
    elapsed=scene.sequence.elapsed if scene.sequence.state!='ordinary' else 0.
    if audio:
        for sound in audio.sounds.values():pr.stop_sound(sound)
    pr.enable_cursor();pr.set_window_size(max(1280,old_size[0]),max(800,old_size[1]))
    editor=Editor(scene,e)
    editor.state.selected=max((cue for cue in CUES if editor.state.document['cues'][cue]<=elapsed),key=lambda cue:editor.state.document['cues'][cue],default='start')
    editor.state.seek(elapsed)
    try:
        editor_loop(editor)
        profile=editor.state.profile;elapsed=editor.state.elapsed;pose=editor.actor
        cam=editor.preview_camera;inspecting=editor.inspection is not None
    finally:editor.close();pr.enable_cursor();pr.set_window_size(*old_size)
    scene.sequence=CanalSequence(direction=profile);scene.sequence.seek(elapsed)
    e.x,e.height,e.z,e.yaw=pose.x,pose.height,pose.z,pose.yaw;e.shot=5;e.clip='idle';e.encounter=scene.sequence
    scene.last_camera=cam;scene.last_shot=5
    scene.sequence.locked_camera=cam;scene.sequence.locked_shot=5
    scene.sequence.locked_pose=(e.x,e.height,e.z,e.yaw)
    scene.sequence._direction_camera_released=inspecting
    return 87.+elapsed


def run():
    pr.set_config_flags(pr.FLAG_WINDOW_RESIZABLE)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(1440,900,'Void Canals / Fog direction editor')
    pr.set_window_min_size(1280,800);pr.set_target_fps(60);pr.set_exit_key(pr.KEY_NULL)
    scene=editor=None
    try:
        scene=Lake();editor=Editor(scene);editor_loop(editor)
    finally:
        if editor:editor.close()
        if scene:scene.close()
        pr.enable_cursor();pr.close_window()


if __name__=='__main__':run()
