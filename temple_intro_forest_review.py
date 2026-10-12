"""Muted native acceptance views of the continuing public road and both verges."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
from pathlib import Path
import json
import time
import math
from PIL import Image,ImageDraw
import pyray as pr
from g_temple_intro import Intro,load_script
from temple_intro_viewer import View,Audio,camera_from_pose,WIDTH,HEIGHT
from temple_intro_atmosphere_review import Clock,road_clearance
from temple_intro_polish_review import pil_frame
from g_intro_landscape import junction_station,world_point,local_world_point,main_road_height,car_pose

def review():
    out=Path(__file__).parent/'artifacts'/'intro-forest';out.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Forest review / muted')
    view=None;audio=None
    try:
        start=time.perf_counter();view=View();startup=time.perf_counter()-start;intro=Intro(load_script());audio=Audio(automated=True)
        assert audio.engine.volume==0
        shots=(('The road not taken',120,(8,8,17),(8,0,-32),70,True),
               ('Fork from above',126,(3,23,18),(13,0,-10),74,True),
               ('Continuing lakeside road',135,(16,14,12),(60,-5,12),70,True),
               ('Right-hand forest',148,(-1,4,5),(24,5,-14),68,True),
               ('Both wooded verges',151,(0,7,17),(0,6,-30),67,True),
               ('Night climb',152,(2,3.5,10),(0,4,-28),66,False))
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*3),(16,22,23));draw=ImageDraw.Draw(sheet)
        for i,(name,t,eye,target,fov,day) in enumerate(shots):
            intro.elapsed=t
            if name=='Continuing lakeside road':
                station=junction_station(intro.arrival_station)+80
                height,pitch=car_pose(intro.distance,intro.arrival_station);c,s=math.cos(pitch),math.sin(pitch)
                def anchored(station,side,lift):
                    x,z=local_world_point(*world_point(station,side,main=True),intro.distance,intro.arrival_station)
                    y=main_road_height(station)+lift-height
                    return x,y*c+z*s,-y*s+z*c
                eye=anchored(station,-3.8,3.2);target=anchored(station+35,0,1.2)
            view.render(Clock(intro,day),camera_override=camera_from_pose(dict(eye=eye,target=target,fov=fov)),scene_view='exterior',overlays=False,apply_fade=False,trails=False)
            image=pil_frame(view.frame);image.save(out/(name.lower().replace(' ','-')+'.png'));x=i%2*WIDTH;y=i//2*(HEIGHT+24)
            sheet.paste(image,(x,y));draw.text((x+8,y+HEIGHT+5),name.upper(),fill=(218,225,212))
        sheet.save(out/'forest-review.png')
        report=dict(audio_gain=audio.engine.volume,startup_seconds=startup,max_draw_calls=view.max_draw_calls,road_clearance=road_clearance(view))
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if view:view.close()
        pr.close_window()

if __name__=='__main__':review()
