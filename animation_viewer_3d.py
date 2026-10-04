"""Standalone player animation review using the game's exported model and shader."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import math
from datetime import datetime

from photo_asset_pipeline.temple3d.living.gait import SETTINGS, HAND

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'artifacts'/'animation-viewer-3d'
SAMPLE_SECONDS=.017
VIEWS={'side':(90.,6.),'front':(0.,6.),'back':(180.,6.),'three-quarter':(40.,12.)}
VIEWPORT=(16,76,960,576)
TIMELINE=(32,684,1216,96)


@dataclass
class Playback:
    source_seconds:dict
    frame_counts:dict
    clip:str='walk'
    cycles:float=0.
    playing:bool=True
    speed:float=1.
    azimuth:float=90.
    elevation:float=6.
    zoom:float=40.
    skeleton:bool=False
    trails:bool=False
    ground_motion:bool=True
    pixels:bool=True

    @property
    def phase(self):return self.cycles%1.

    @property
    def frame(self):
        return min(self.frame_counts[self.clip]-1,int((self.phase+1e-9)*self.source_seconds[self.clip]/SAMPLE_SECONDS))

    @property
    def period(self):
        return 2. if self.clip=='idle' else SETTINGS[self.clip]['stride']/SETTINGS[self.clip]['speed']

    def advance(self,dt):
        if self.playing:self.cycles+=max(0.,dt)*self.speed/self.period

    def step(self,direction):
        self.playing=False
        frame=(self.frame+direction)%self.frame_counts[self.clip]
        self.cycles=frame*SAMPLE_SECONDS/self.source_seconds[self.clip]

    def scrub(self,fraction):
        self.playing=False
        frame=round(max(0.,min(1.,fraction))*(self.frame_counts[self.clip]-1))
        self.cycles=frame*SAMPLE_SECONDS/self.source_seconds[self.clip]

    def action(self,name):
        if name.startswith('clip:'):
            self.clip=name.split(':')[1];self.cycles=0.
        elif name.startswith('speed:'):self.speed=float(name.split(':')[1])
        elif name.startswith('view:'):
            self.azimuth,self.elevation=VIEWS[name.split(':')[1]]
        elif name=='play':self.playing=not self.playing
        elif name=='previous':self.step(-1)
        elif name=='next':self.step(1)
        elif name=='restart':self.cycles=0.
        elif name in ('skeleton','trails','ground_motion','pixels'):setattr(self,name,not getattr(self,name))
        elif name=='reset':
            self.cycles=0.;self.azimuth,self.elevation=VIEWS['side'];self.zoom=40.


def controls(state):
    """One layout for both mouse hit-testing and drawing."""
    result=[]
    def row(y,items):
        width=264/len(items)
        for i,(name,label,selected) in enumerate(items):
            result.append((name,label,(992+i*width,y,width-6,32),selected))
    row(104,[(f'clip:{c}',c.title(),state.clip==c) for c in ('idle','walk','run')])
    row(158,[('play','Pause' if state.playing else 'Play',state.playing),('restart','Restart',False)])
    row(198,[('previous','< Frame',False),('next','Frame >',False)])
    row(256,[(f'speed:{v}',f'{v:g}x',state.speed==v) for v in (.25,.5,1.,2.)])
    row(314,[(f'view:{v}',label,state.azimuth==VIEWS[v][0]) for v,label in (('side','Side'),('front','Front'))])
    row(354,[(f'view:{v}',label,state.azimuth==VIEWS[v][0]) for v,label in (('back','Back'),('three-quarter','Three-quarter'))])
    row(408,[('skeleton','Skeleton [B]',state.skeleton),('trails','Foot paths [T]',state.trails)])
    row(448,[('ground_motion','Ground motion',state.ground_motion),('pixels','Pixel view [P]',state.pixels)])
    return result


def within(rect,x,y):
    a,b,w,h=rect
    return a<=x<a+w and b<=y<b+h


def click(state,x,y):
    for name,_,rect,_ in controls(state):
        if within(rect,x,y):state.action(name);return True
    if within(TIMELINE,x,y):state.scrub((x-TIMELINE[0])/TIMELINE[2]);return True
    return False


def joint_angle(a,b,c):
    u=tuple(x-y for x,y in zip(a,b));v=tuple(x-y for x,y in zip(c,b))
    length=math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
    return math.degrees(math.acos(max(-1.,min(1.,sum(x*y for x,y in zip(u,v))/length))))


def sample_pose(pr,assets,ids):
    points={};angles={}
    def transform(name,point=None):
        index=ids[name]
        value=pr.vector3_transform(point or assets.player.bindPose[index].translation,assets.player.meshes[0].boneMatrices[index])
        return (value.x,value.y,value.z)
    points['hip']=transform('root');points['neck']=transform('head')
    root_rest=assets.player.bindPose[ids['root']].translation
    points['pelvis_up']=transform('root',pr.Vector3(root_rest.x,root_rest.y+2,root_rest.z))
    for side in ('L','R'):
        for label,bone in (('hip','thigh'),('knee','shin'),('ankle','foot'),('shoulder','arm'),('elbow','forearm'),('wrist','hand')):
            points[label+'.'+side]=transform(bone+'.'+side)
        x=assets.player.bindPose[ids['foot.'+side]].translation.x
        points['toe.'+side]=transform('foot.'+side,pr.Vector3(x,.1,2.2))
        points['heel.'+side]=transform('foot.'+side,pr.Vector3(x,.1,-1.1))
        hand_rest=assets.player.bindPose[ids['hand.'+side]].translation
        points['hand.'+side]=transform('hand.'+side,pr.Vector3(hand_rest.x,hand_rest.y-HAND,hand_rest.z))
        angles['knee.'+side]=180-joint_angle(*(points[k+'.'+side] for k in ('hip','knee','ankle')))
        angles['elbow.'+side]=joint_angle(*(points[k+'.'+side] for k in ('shoulder','elbow','wrist')))
        angles['wrist.'+side]=180-joint_angle(*(points[k+'.'+side] for k in ('elbow','wrist','hand')))
    h,n=points['hip'],points['neck']
    angles['lean']=math.degrees(math.atan2(n[2]-h[2],n[1]-h[1]))
    up=points['pelvis_up']
    angles['pelvis_lean']=math.degrees(math.atan2(up[2]-h[2],up[1]-h[1]))
    angles['pelvis_bank']=math.degrees(math.atan2(up[0]-h[0],up[1]-h[1]))
    soles={side:min(points[key+'.'+side][1] for key in ('heel','toe')) for side in ('L','R')}
    return dict(points=points,angles=angles,sole_clearance=soles,
                airborne=min(soles.values())>.12)


class Viewer:
    def __init__(self,pr):
        from g_temple_living import LivingScene
        self.pr=pr;self.assets=LivingScene(include_willow=False)
        self.targets=[]
        self.pixel=self.target(480,288);self.full=self.target(960,576);self.small=self.target(64,64)
        self.screen=self.target(1280,820)
        self.state=Playback(self.assets.clip_seconds,{c:self.assets.animations[i].frameCount for c,i in self.assets.clips.items()})
        self.samples={};self.message='';self.message_until=0.;self.scrubbing=False
        ids={pr.ffi.string(self.assets.player.bones[i].name).decode():i for i in range(self.assets.player.boneCount)}
        for clip,count in self.state.frame_counts.items():
            samples=[]
            for frame in range(count):
                phase=frame*SAMPLE_SECONDS/self.state.source_seconds[clip]
                self.assets.pose(clip,phase+1e-9)
                samples.append(sample_pose(pr,self.assets,ids))
            self.samples[clip]=samples

    def target(self,width,height):
        target=self.pr.load_render_texture(width,height)
        self.pr.set_texture_filter(target.texture,self.pr.TEXTURE_FILTER_POINT)
        self.targets.append(target)
        return target

    def camera(self,span):
        pr=self.pr;s=self.state
        a,e=math.radians(s.azimuth),math.radians(s.elevation)
        eye=pr.Vector3(80*math.sin(a)*math.cos(e),14+80*math.sin(e),80*math.cos(a)*math.cos(e))
        return pr.Camera3D(eye,pr.Vector3(0,14,0),pr.Vector3(0,1,0),span,pr.CAMERA_ORTHOGRAPHIC)

    def draw_scene(self,target,small=False):
        pr=self.pr;s=self.state;camera=self.camera(64. if small else s.zoom)
        pr.begin_texture_mode(target);pr.clear_background(pr.Color(23,32,39,255))
        pr.begin_mode_3d(camera)
        pr.draw_plane(pr.Vector3(0,-.04,0),pr.Vector2(160,160),pr.Color(31,42,48,255))
        travel=s.cycles*SETTINGS[s.clip]['stride'] if s.ground_motion and s.clip!='idle' else 0.
        for n in range(-12,13):
            color=pr.Color(45,59,65,255)
            z=n*5-travel%5
            pr.draw_line_3d(pr.Vector3(-60,0,z),pr.Vector3(60,0,z),color)
            pr.draw_line_3d(pr.Vector3(n*5,0,-60),pr.Vector3(n*5,0,60),color)
        colors={'L':pr.Color(95,213,186,255),'R':pr.Color(244,153,119,255)}
        if s.trails and not small:
            for side,color in colors.items():
                path=[sample['points']['ankle.'+side] for sample in self.samples[s.clip]]
                for a,b in zip(path,path[1:]+path[:1]):pr.draw_line_3d(pr.Vector3(*a),pr.Vector3(*b),color)
        self.assets.yaw=0.;self.assets.draw_player(0,0,0)
        pr.end_mode_3d()
        if s.skeleton and not small:
            points=self.samples[s.clip][s.frame]['points']
            def projected(name):return pr.get_world_to_screen_ex(pr.Vector3(*points[name]),camera,target.texture.width,target.texture.height)
            for side,color in colors.items():
                for chain in (('hip','knee','ankle','toe'),('shoulder','elbow','wrist','hand')):
                    for a,b in zip(chain,chain[1:]):
                        start,end=projected(a+'.'+side),projected(b+'.'+side)
                        pr.draw_line_ex(start,end,2.,color)
                        pr.draw_circle_v(start,2.2,color)
                    pr.draw_circle_v(end,2.2,color)
            pr.draw_line_ex(projected('hip'),projected('neck'),2.,pr.Color(232,213,147,255))
            pr.draw_line_ex(projected('hip.L'),projected('hip.R'),2.,pr.Color(232,213,147,255))
            pr.draw_line_ex(projected('hip'),projected('pelvis_up'),2.,pr.Color(255,234,179,255))
        pr.end_texture_mode()

    def update(self,dt):
        pr=self.pr;s=self.state;mouse=pr.get_mouse_position()
        for key,action in ((pr.KEY_SPACE,'play'),(pr.KEY_LEFT,'previous'),(pr.KEY_RIGHT,'next'),
                           (pr.KEY_ONE,'clip:idle'),(pr.KEY_TWO,'clip:walk'),(pr.KEY_THREE,'clip:run'),
                           (pr.KEY_B,'skeleton'),(pr.KEY_T,'trails'),(pr.KEY_P,'pixels'),(pr.KEY_G,'ground_motion'),
                           (pr.KEY_HOME,'reset')):
            if pr.is_key_pressed(key):s.action(action)
        if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
            self.scrubbing=within(TIMELINE,mouse.x,mouse.y)
            click(s,mouse.x,mouse.y)
        if self.scrubbing and pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT):
            s.scrub((mouse.x-TIMELINE[0])/TIMELINE[2])
        if pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT):self.scrubbing=False
        if within(VIEWPORT,mouse.x,mouse.y):
            if pr.is_mouse_button_down(pr.MOUSE_BUTTON_RIGHT):
                delta=pr.get_mouse_delta();s.azimuth=(s.azimuth-delta.x*.4)%360
                s.elevation=max(-5.,min(65.,s.elevation+delta.y*.25))
            s.zoom=max(30.,min(80.,s.zoom-pr.get_mouse_wheel_move()*2))
        hovered=any(within(r,mouse.x,mouse.y) for _,_,r,_ in controls(s)) or within(TIMELINE,mouse.x,mouse.y)
        pr.set_mouse_cursor(pr.MOUSE_CURSOR_POINTING_HAND if hovered else pr.MOUSE_CURSOR_DEFAULT)
        s.advance(dt)

    def draw(self):
        pr=self.pr;s=self.state
        self.assets.environment(0.,True,[])
        # Address the selected sample explicitly, including just before the
        # loop boundary; epsilon on a continuous phase could wrap it to zero.
        sample_phase=(s.frame+1e-6)*SAMPLE_SECONDS/s.source_seconds[s.clip]
        self.assets.pose(s.clip,sample_phase)
        assert self.assets.animation_frame==s.frame
        target=self.pixel if s.pixels else self.full
        self.draw_scene(target);self.draw_scene(self.small,True)
        # Keep the complete current frame in a texture. Reading the window's
        # back buffer after SwapBuffers can return the preceding frame.
        pr.begin_texture_mode(self.screen);pr.clear_background(pr.Color(12,18,24,255))
        def label(text,x,y,size=18,color=None):pr.draw_text(text,int(x),int(y),size,color or pr.Color(207,220,226,255))
        def blit(tex,rect):
            pr.draw_texture_pro(tex,pr.Rectangle(0,0,tex.width,-tex.height),pr.Rectangle(*rect),pr.Vector2(0,0),0,pr.WHITE)
        label('PLAYER  /  ANIMATION REVIEW',24,18,25)
        label('Right-drag to orbit  |  Wheel to zoom  |  Space play/pause  |  Arrows step  |  F12 save pose',24,49,17)
        blit(target.texture,VIEWPORT)
        pr.draw_rectangle(984,76,280,576,pr.Color(24,32,40,255))
        for text,y in (('ANIMATION   [1 / 2 / 3]',82),('PLAYBACK',140),('SPEED',236),('CAMERA',294)):
            label(text,992,y,15,pr.Color(142,162,176,255))
        mouse=pr.get_mouse_position()
        for _,text,rect,selected in controls(s):
            hover=within(rect,mouse.x,mouse.y)
            color=pr.Color(48,99,99,255) if selected else pr.Color(55,68,81,255) if hover else pr.Color(35,46,57,255)
            pr.draw_rectangle_rec(pr.Rectangle(*rect),color)
            width=pr.measure_text(text,16)
            label(text,rect[0]+(rect[2]-width)/2,rect[1]+8,16)
        label('Game scale / 2x',992,487,15)
        blit(self.small.texture,(992,510,128,128))
        info=self.samples[s.clip][s.frame]['angles']
        for i,(title,value) in enumerate((('L knee',info['knee.L']),('R knee',info['knee.R']),
                                          ('L elbow',info['elbow.L']),('R elbow',info['elbow.R']),
                                          ('Lean',info['lean']),('Pelvis',info['pelvis_lean']))):
            label(f'{title}: {value:.0f}',1130,514+i*18,15)
        label('Angles in degrees',1130,629,13,pr.Color(142,162,176,255))
        pose=self.samples[s.clip][s.frame]
        label('AIRBORNE' if pose['airborne'] else 'GROUNDED',30,92,17,
              pr.Color(243,212,147,255) if pose['airborne'] else pr.Color(142,162,176,255))
        label('Knee bend',32,666,15)
        label('LEFT',156,666,15,pr.Color(95,213,186,255))
        label('RIGHT',214,666,15,pr.Color(244,153,119,255))
        label('Click or drag this graph / timeline to inspect a pose',650,666,16)
        pr.draw_rectangle(32,688,1216,63,pr.Color(22,31,39,255))
        for side,color in (('L',pr.Color(95,213,186,255)),('R',pr.Color(244,153,119,255))):
            values=[v['angles']['knee.'+side] for v in self.samples[s.clip]]
            for i,(a,b) in enumerate(zip(values,values[1:])):
                x=32+1216*i/(len(values)-1);nx=32+1216*(i+1)/(len(values)-1)
                pr.draw_line_ex(pr.Vector2(x,749-a*.48),pr.Vector2(nx,749-b*.48),2,color)
        fraction=s.frame/max(1,s.frame_counts[s.clip]-1);cursor=32+1216*fraction
        pr.draw_line(int(cursor),686,int(cursor),751,pr.Color(243,212,147,255))
        pr.draw_rectangle(32,762,1216,10,pr.Color(39,51,63,255))
        pr.draw_rectangle(32,762,int(1216*fraction),10,pr.Color(69,142,144,255))
        pr.draw_circle(int(cursor),767,7,pr.Color(243,212,147,255))
        pose_phase=s.frame*SAMPLE_SECONDS/s.source_seconds[s.clip]
        label(f'{s.clip.upper()}   Frame {s.frame+1:02d} / {s.frame_counts[s.clip]}   Pose {pose_phase*100:5.1f}%   {s.speed:g}x   Cycle {s.period:.2f}s',32,788,17)
        label('Elbow = inside angle; smaller is tighter',860,788,15,pr.Color(142,162,176,255))
        if self.message and pr.get_time()<self.message_until:label(self.message,30,624,15,pr.Color(243,212,147,255))
        pr.end_texture_mode()
        pr.begin_drawing();pr.clear_background(pr.BLACK)
        blit(self.screen.texture,(0,0,1280,820))
        pr.end_drawing()

    def save(self,name=None):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        s=self.state
        name=name or f'{datetime.now():%Y%m%d-%H%M%S-%f}-{s.clip}-frame-{s.frame+1:02d}'
        path=OUTPUT/(name+'.png')
        # Use the exact displayed frame, with the requested destination path.
        capture=self.pr.load_image_from_texture(self.screen.texture)
        self.pr.image_flip_vertical(capture)
        try:
            if not self.pr.export_image(capture,str(path)):raise RuntimeError('Could not save '+str(path))
        finally:self.pr.unload_image(capture)
        data=dict(clip=s.clip,frame=s.frame+1,sample_index=s.frame,phase=s.phase,playback_speed=s.speed,
                  pose_phase=s.frame*SAMPLE_SECONDS/s.source_seconds[s.clip],
                  cycle_seconds=s.period,camera=dict(azimuth=s.azimuth,elevation=s.elevation,span=s.zoom),
                  skeleton=s.skeleton,foot_paths=s.trails,pixel_view=s.pixels,
                  **self.samples[s.clip][s.frame])
        path.with_suffix('.json').write_text(json.dumps(data,indent=2)+'\n')
        self.message=f'Saved {path.name} + pose notes';self.message_until=self.pr.get_time()+4
        return path

    def close(self):
        for target in self.targets:self.pr.unload_render_texture(target)
        self.assets.close()


def main():
    from setup_temple_3d import ensure_runtime
    ensure_runtime()
    import pyray as pr
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true',help='Verify controls, save review frames and exit')
    args=parser.parse_args()
    if args.smoke:pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(1280,820,'Player / 3D animation viewer');pr.set_target_fps(60)
    viewer=None
    try:
        viewer=Viewer(pr)
        if args.smoke:
            from PIL import Image,ImageStat
            for clip,phase,bones,view in (('walk',.72,True,'side'),('run',.02,False,'side'),('idle',.15,True,'three-quarter')):
                s=viewer.state
                # Exercise the same button hit-testing used by real clicks.
                _,_,rect,_=next(b for b in controls(s) if b[0]=='clip:'+clip)
                assert click(s,rect[0]+10,rect[1]+10)
                s.playing=False;s.cycles=phase;s.skeleton=bones;s.trails=bones;s.action('view:'+view)
                viewer.message='';viewer.draw();path=viewer.save('review-'+clip)
                capture=Image.open(path).convert('RGB')
                assert capture.size==(1280,820) and max(ImageStat.Stat(capture).var)>100,'Empty viewer capture'
            viewer.state.action('pixels');viewer.draw();viewer.save('review-full-resolution')
            for name,clip,phase,view in (('walk-contact','walk',.98,'side'),
                                        ('run-flight','run',.41,'side'),
                                        ('shoulders-front','idle',0.,'front'),
                                        ('shoulders-run','run',0.,'three-quarter'),
                                        ('run-transfer-left','run',.15,'front'),
                                        ('run-transfer-right','run',.65,'front'),
                                        ('walk-support','walk',.25,'side'),
                                        ('walk-hands','walk',.25,'front'),
                                        ('run-arm-downsweep','run',.31,'side'),
                                        ('run-arm-reversal','run',0.,'side')):
                s=viewer.state;s.clip=clip;s.cycles=phase;s.skeleton=False;s.trails=False
                s.action('view:'+view);viewer.message='';viewer.draw();viewer.save('review-'+name)
                if name=='run-flight':assert viewer.samples[clip][s.frame]['airborne']
            print('Animation viewer rendered all clips, skeletons, paths, graph, game-scale inset and both resolutions.')
        else:
            while not pr.window_should_close():
                viewer.update(min(.1,pr.get_frame_time()));viewer.draw()
                if pr.is_key_pressed(pr.KEY_F12):viewer.save()
    finally:
        if viewer:viewer.close()
        pr.close_window()


if __name__=='__main__':main()
