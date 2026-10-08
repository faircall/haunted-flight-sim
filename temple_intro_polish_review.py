"""Muted cabin, bridge, winding-road and moving-mist acceptance captures."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
import json
import time
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
import pyray as pr
from g_temple_intro import Intro,load_script
from temple_intro_viewer import View,Audio,camera_from_pose,capture,WIDTH,HEIGHT

OUT=Path(__file__).parent/'artifacts'/'intro-polish'
ACTORS={'driver','colleague','driver_head','colleague_head','player_seated','player_lap'}


def pil_frame(target):
    im=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(im)
    pr.image_format(im,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
    result=Image.frombytes('RGBA',(WIDTH,HEIGHT),bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4))).convert('RGB')
    pr.unload_image(im);return result


def review():
    OUT.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Intro polish / muted')
    v=None;audio=None
    shots=[
        ('01-cabin-day',25,(.02,1.235,.53),(.02,1.06,-1),75,'interior',False),
        ('02-unused-rear-belts',25,(0,1.24,.12),(0,.76,.85),80,'interior',True),
        ('03-driver-belt',25,(.14,1.21,-.82),(-.40,.87,-.31),63,'interior',False),
        ('04-passenger-belt',25,(-.14,1.21,-.82),(.40,.87,-.31),63,'interior',False),
        ('05-rear-footwell',25,(.02,1.235,.53),(.20,.21,.16),77,'interior',False),
        ('06-front-footwell',25,(.34,.94,-.28),(.45,.20,-1.05),78,'interior',True),
        ('07-headliner',25,(0,1.22,.44),(0,1.48,.19),90,'interior',True),
        ('08-first-stone-bridge',30,(7,2.8,7),(0,-.12,-1),67,'exterior',False),
        ('09-second-stone-bridge',748/10.5,(-7,4,7),(0,-.05,-1),64,'exterior',False),
        ('10-third-bridge-at-dusk',1120/10.5,(8,3,7),(0,0,-3),66,'exterior',False),
        ('11-winding-road',67,(20,18,21),(-8,3,-48),65,'exterior',False),
        ('12-lake-and-mist',45,(-.8,3.5,9),(70,6,-38),68,'exterior',False),
        ('13-green-hillside',25,(.5,2.7,4),(-18,7,-25),67,'exterior',False),
    ]
    try:
        v=View();intro=Intro(load_script());audio=Audio(automated=True);assert audio.engine.volume==0
        original=v.draw
        for name,t,eye,target,fov,mode,empty in shots:
            def draw(model,*args,**kw):
                if empty and model in ACTORS:return
                return original(model,*args,**kw)
            v.draw=draw;intro.elapsed=t
            cam=camera_from_pose(dict(eye=eye,target=target,fov=fov))
            v.render(intro,camera_override=cam,scene_view=mode,overlays=False,apply_fade=False,trails=False)
            capture(v.frame,OUT/(name+'.png'))
        v.draw=original
        class WeatherClock:
            def __init__(self,source):self.source=source;self.elapsed=source.elapsed
            def __getattr__(self,key):return getattr(self.source,key)
        intro.elapsed=45;weather=WeatherClock(intro)
        camera=camera_from_pose(dict(eye=(-.8,3.5,9),target=(70,6,-38),fov=68));frames=[];timings=[]
        for i in range(56):
            weather.elapsed=45+i*.22;t=time.perf_counter()
            v.render(weather,camera_override=camera,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
            pr.rl.rlDrawRenderBatchActive();frames.append(pil_frame(v.frame));timings.append(time.perf_counter()-t)
        changed=float(np.abs(np.asarray(frames[0],dtype=float)-np.asarray(frames[-1],dtype=float)).mean())
        assert changed>1.,changed
        frames[0].save(OUT/'rolling-lake-mist.gif',save_all=True,append_images=frames[1:],duration=100,loop=0)
        # Drive through all three crossings and chunk boundaries with no rebuilds.
        cache=set(v.terrain.chunks);before={i:id(m['road']) for i,m in v.terrain.chunks.items()}
        for timestamp in (4.5,4.6,29.8,30,30.5,70.8,71.3,106,107):
            intro.elapsed=timestamp;v.render(intro,overlays=False,apply_fade=False,trails=False)
        assert cache==set(v.terrain.chunks)
        assert before=={i:id(m['road']) for i,m in v.terrain.chunks.items()}
        for name,selection in (('cabin-review',(0,1,2,3,4,5,6)),('scenery-review',(7,8,9,10,11,12))):
            sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*((len(selection)+1)//2)),(19,27,26));labels=ImageDraw.Draw(sheet)
            for j,index in enumerate(selection):
                label=shots[index][0];x=j%2*WIDTH;y=j//2*(HEIGHT+24)
                with Image.open(OUT/(label+'.png')) as image:sheet.paste(image,(x,y))
                labels.text((x+8,y+HEIGHT+6),label[3:].replace('-',' ').upper(),fill=(220,229,219))
            sheet.save(OUT/(name+'.png'))
        report=dict(audio_gain=audio.engine.volume,shots=len(shots),fog_animation_frames=len(frames),
                    animated_image_difference=changed,frame_with_readback_median_ms=float(np.median(timings)*1000),
                    preloaded_chunks=len(cache),crossings_reuse_uploaded_meshes=True,max_draw_calls=v.max_draw_calls)
        (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if v:v.close()
        pr.close_window()


if __name__=='__main__':review()
