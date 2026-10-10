"""Muted native river, turning manoeuvre and terraced-temple acceptance review."""
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

OUT=Path(__file__).parent/'artifacts'/'intro-arrival'


def review(full=True):
    OUT.mkdir(parents=True,exist_ok=True);pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Temple arrival / muted')
    view=None;audio=None
    try:
        start=time.perf_counter();view=View();startup=time.perf_counter()-start
        intro=Intro(load_script());audio=Audio(automated=True);assert audio.engine.volume==0
        samples=[('river-upstream',30,(10,6,8),(-100,7,-12),68,True),
                 ('river-mouth',30,(-12,6,12),(25,0,-7),65,True),
                 ('shoreline',47,(-1,2.6,6),(16,0,-14),65,True),
                 ('junction-before',118,(10,10,16),(-6,0,-25),66,True),
                 ('junction-turning',125,(10,10,16),(4,0,-12),66,True),
                 ('main-road-left-behind',148,(0,8,-6),(8,-1,35),66,True),
                 ('forest-climb',154,(3,2.6,7),(0,3,-30),62,False),
                 ('clearing-day',170,(8,7,15),(0,10,-34),68,True),
                 ('temple-night',170,(5,3.6,9),(0,15,-40),66,False),
                 ('terraced-complex',172,(43,37,22),(0,15,-58),67,True),
                 ('steps-human-scale',172,(1,1.7,-11),(0,13,-43),65,True),
                 ('arrival-camera',169,None,None,None,False)]
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*6),(18,25,25));draw=ImageDraw.Draw(sheet)
        for i,(name,t,eye,target,fov,day) in enumerate(samples):
            intro.elapsed=t
            camera=camera_from_pose(dict(eye=eye,target=target,fov=fov)) if eye else None
            view.render(Clock(intro,day),camera_override=camera,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
            image=pil_frame(view.frame);image.save(OUT/(name+'.png'));x=i%2*WIDTH;y=i//2*(HEIGHT+24)
            sheet.paste(image,(x,y));draw.text((x+8,y+HEIGHT+5),name.replace('-',' ').upper(),fill=(220,230,220))
        sheet.save(OUT/'arrival-review.png')
        if full:
            for name,seconds in (('turnoff',np.linspace(115,144,232)),('temple-reveal',np.linspace(153,173,160))):
                frames=[]
                for t in seconds:
                    intro.elapsed=float(t);view.render(intro,overlays=True,apply_fade=False,trails=False);frames.append(pil_frame(view.frame))
                frames[0].save(OUT/(name+'.gif'),save_all=True,append_images=frames[1:],duration=125,loop=0)
            clearance=road_clearance(view)
            report=dict(audio_gain=audio.engine.volume,startup_seconds=startup,max_draw_calls=view.max_draw_calls,road_clearance=clearance)
            (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if view:view.close()
        pr.close_window()


if __name__=='__main__':review()
