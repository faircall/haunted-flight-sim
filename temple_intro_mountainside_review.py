"""Muted native inspection of the pass, mountain courts and forest silhouettes."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
from pathlib import Path
import json
import time
import numpy as np
from PIL import Image,ImageDraw
import pyray as pr
from g_temple_intro import Intro,load_script
from temple_intro_viewer import View,Audio,camera_from_pose,WIDTH,HEIGHT
from temple_intro_polish_review import pil_frame
from temple_intro_atmosphere_review import Clock,road_clearance
from g_intro_temple_layout import grove

OUT=Path(__file__).parent/'artifacts'/'intro-mountainside'

def review():
    OUT.mkdir(parents=True,exist_ok=True);pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Mountainside / muted')
    view=None;audio=None
    try:
        start=time.perf_counter();view=View();startup=time.perf_counter()-start
        intro=Intro(load_script());audio=Audio(automated=True);assert audio.engine.volume==0
        shots=[('pass-day',144,(4,4,8),(-1,2,-25),68,True,'exterior'),
               ('climb-inside',151,(.02,1.235,.53),(.02,1.28,-4),75,False,'interior'),
               ('clearing-day',170,(8,7,15),(0,10,-34),68,True,'exterior'),
               ('temple-night',170,(5,3.6,9),(0,15,-40),66,False,'exterior'),
               ('western-hillside',172,(-86,33,31),(-28,22,-49),78,True,'exterior'),
               ('eastern-hillside',172,(96,43,9),(16,24,-74),78,True,'exterior'),
               ('upper-courts',172,(18,73,-54),(0,31,-81),76,True,'exterior'),
               ('steps',172,(1,1.7,-11),(0,13,-43),65,True,'exterior')]
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*4),(18,25,25));draw=ImageDraw.Draw(sheet)
        for i,(name,t,eye,target,fov,day,mode) in enumerate(shots):
            intro.elapsed=t;camera=camera_from_pose(dict(eye=eye,target=target,fov=fov))
            view.render(Clock(intro,day),camera_override=camera,scene_view=mode,overlays=False,apply_fade=False,trails=False)
            image=pil_frame(view.frame);image.save(OUT/(name+'.png'));x=i%2*WIDTH;y=i//2*(HEIGHT+24)
            sheet.paste(image,(x,y));draw.text((x+8,y+HEIGHT+5),name.replace('-',' ').upper(),fill=(220,230,220))
        sheet.save(OUT/'mountainside-review.png')
        frames=[];timings=[]
        for t in np.linspace(137,173,180):
            intro.elapsed=float(t);start=time.perf_counter()
            view.render(intro,overlays=True,apply_fade=False,trails=False);frames.append(pil_frame(view.frame));timings.append(time.perf_counter()-start)
        frames[0].save(OUT/'mountain-approach.gif',save_all=True,append_images=frames[1:],duration=200,loop=0)
        report=dict(audio_gain=audio.engine.volume,startup_seconds=startup,max_draw_calls=view.max_draw_calls,
                    median_frame_and_readback_ms=float(np.median(timings)*1000),temple_grove_trees=len(grove()),
                    road_clearance=road_clearance(view))
        (OUT/'mountainside-report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if view:view.close()
        pr.close_window()

if __name__=='__main__':review()
