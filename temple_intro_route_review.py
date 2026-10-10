"""Muted native acceptance: rolling road, uphill arrival, belts and wiper cycle."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
import json
import math
import time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import pyray as pr
from g_temple_intro import Intro,load_script,WIPER_PERIOD
from g_intro_landscape import car_pose
from temple_intro_viewer import View,Audio,camera_from_pose,capture,WIDTH,HEIGHT
from temple_intro_polish_review import pil_frame

OUT=Path(__file__).parent/'artifacts'/'intro-route'


def sheet(images,labels,path):
    result=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*math.ceil(len(images)/2)),(18,27,26));draw=ImageDraw.Draw(result)
    for i,(picture,label) in enumerate(zip(images,labels)):
        x=i%2*WIDTH;y=i//2*(HEIGHT+24);result.paste(picture,(x,y));draw.text((x+8,y+HEIGHT+5),label,fill=(220,230,220))
    result.save(path)


def review():
    OUT.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Road / muted review')
    v=None;audio=None
    try:
        v=View();intro=Intro(load_script());audio=Audio(automated=True);assert audio.engine.volume==0
        shots=[('Rolling lakeside road',23.,(8,5,12),(-3,1,-32),65,'exterior'),
               ('Continuous uphill utility line',56.,(2,3,5),(-21,9,-45),68,'exterior'),
               ('Bridge approach',29.,(7,3.8,10),(0,0,-10),62,'exterior'),
               ('Last bridge before climb',1120/10.5,(9,4,10),(-2,0,-10),62,'exterior'),
               ('Climbing toward the temple',intro.duration-22,(6,3.5,10),(0,2,-25),64,'exterior'),
               ('Level forecourt and steps',intro.duration-6,(2,2.3,5),(0,11,-30),58,'exterior'),
               ('Rear belt from occupied seat',34.,(.02,1.235,.53),(.63,.84,.74),74,'interior'),
               ('Driver view uphill',intro.duration-25,(.02,1.235,.53),(.02,1.12,-1),75,'interior')]
        pictures=[];labels=[]
        for i,(label,t,eye,target,fov,mode) in enumerate(shots):
            intro.elapsed=t
            v.render(intro,camera_override=camera_from_pose(dict(eye=eye,target=target,fov=fov)),scene_view=mode,overlays=False,apply_fade=False,trails=False)
            picture=pil_frame(v.frame);pictures.append(picture);labels.append(label)
            picture.save(OUT/f'{i+1:02d}.png')
        sheet(pictures,labels,OUT/'route-review.png')
        # Freeze vehicle progress to isolate a complete wiper cycle, inside/out.
        class WeatherClock:
            def __init__(self,source):self.source=source;self.elapsed=source.elapsed
            def __getattr__(self,key):return getattr(self.source,key)
        intro.elapsed=37.;clock=WeatherClock(intro);frames=[];poses=[];pose_labels=[]
        for i in range(60):
            clock.elapsed=20*WIPER_PERIOD+i*WIPER_PERIOD/60
            pair=Image.new('RGB',(WIDTH*2,HEIGHT))
            for j,(mode,eye,target,fov) in enumerate((
                    ('interior',(.02,1.235,.53),(.02,1.10,-1),75),
                    ('exterior',(1.2,1.95,-3.3),(0,1.15,-.9),49))):
                v.render(clock,camera_override=camera_from_pose(dict(eye=eye,target=target,fov=fov)),scene_view=mode,overlays=False,apply_fade=False,trails=False)
                image=pil_frame(v.frame);pair.paste(image,(j*WIDTH,0))
                if i in (0,15,30,45):poses.append(image);pose_labels.append(f'{mode}: cycle {i}/60')
            frames.append(pair)
        frames[0].save(OUT/'wipers-inside-out.gif',save_all=True,append_images=frames[1:],duration=round(WIPER_PERIOD*1000/60),loop=0)
        sheet(poses,pose_labels,OUT/'wiper-poses.png')
        # Look down on the car through the entire route to catch clipped tyres,
        # terrain crossings and bad chunk transitions; this is all native GPU.
        route=[];route_labels=[];timings=[];ids={i:id(m['road']) for i,m in v.terrain.chunks.items()}
        for i,t in enumerate(np.linspace(0,intro.duration-3,280)):
            intro.elapsed=float(t)
            cam=camera_from_pose(dict(eye=(5,4.8,7),target=(0,0,-3),fov=65))
            start=time.perf_counter();v.render(intro,camera_override=cam,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
            im=pil_frame(v.frame);timings.append(time.perf_counter()-start)
            if i%14==0 or i==279:
                route.append(im);h,p=car_pose(intro.distance,intro.arrival_station)
                route_labels.append(f'{t:.1f}s / height {h:.1f}m / pitch {math.degrees(p):.1f} degrees')
        sheet(route,route_labels,OUT/'full-route-contact-sheet.png')
        assert ids=={i:id(m['road']) for i,m in v.terrain.chunks.items()}
        assert v.max_draw_calls<540,v.max_draw_calls
        report=dict(audio_gain=audio.engine.volume,route_frames=280,wiper_frames=60,
                    maximum_draw_calls=v.max_draw_calls,median_frame_and_readback_ms=float(np.median(timings)*1000),
                    preloaded_chunks=len(ids),final_road_height=car_pose(intro.distance,intro.arrival_station)[0])
        (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if v:v.close()
        pr.close_window()


if __name__=='__main__':review()
