"""Muted acceptance captures for mirrors, rear visibility, rivers and temple turnoff."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
import json
import time
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
import pyray as pr
from g_temple_intro import Intro,load_script
from g_intro_landscape import junction_station,road_x,road_height,world_point,main_road_height,CHUNK_LENGTH,DEFAULT_ARRIVAL
from temple_intro_viewer import View,Audio,camera_from_pose,WIDTH,HEIGHT,capture
from temple_intro_polish_review import pil_frame

OUT=Path(__file__).parent/'artifacts'/'intro-atmosphere'


class Clock:
    def __init__(self,source,day=False):self.source=source;self.day=day
    def __getattr__(self,key):return getattr(self.source,key)
    @property
    def dusk(self):return .18 if self.day else self.source.dusk
    @property
    def headlights(self):return 0. if self.day else self.source.headlights


def road_clearance(view):
    """Ray-check uploaded terrain, including far offset strips that can fold."""
    from test_santana_car import intersections
    banks={}
    for index,models in view.terrain.chunks.items():
        mesh=models['bank'].meshes[0]
        vertices=np.frombuffer(pr.ffi.buffer(mesh.vertices,mesh.vertexCount*12),dtype='<f4').copy().reshape(-1,3)
        vertices+=np.array((road_x(index*CHUNK_LENGTH),0,-index*CHUNK_LENGTH))
        banks[index]=vertices.reshape(-1,3,3)
    maximum=-100.;samples=0;offenders=[]
    for main,stations in ((False,range(0,int(DEFAULT_ARRIVAL)+1,4)),(True,range(int(junction_station())+25,int(DEFAULT_ARRIVAL)+148,4))):
        for station in stations:
            x,z=world_point(station,0,main=main);height=main_road_height(station) if main else road_height(station)
            indices=range(int(station//CHUNK_LENGTH)-3,int(station//CHUNK_LENGTH)+4)
            triangles=np.concatenate([banks[i] for i in indices if i in banks])
            # Uploaded float32 triangles can round to either side of a seam.
            hits=intersections(triangles,np.array((x,100.,z)),np.array((0.,-1.,0.)),tolerance=3e-6)
            assert len(hits),(main,station,'Terrain hole')
            overlap=100.-hits.min()-height;maximum=max(maximum,overlap);samples+=1
            if overlap>.025:offenders.append((main,station,round(float(overlap),4)))
    assert not offenders,('Terrain above road',offenders[:15])
    return dict(samples=samples,highest_terrain_relative_to_road=float(maximum))


def review():
    OUT.mkdir(parents=True,exist_ok=True);pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Atmosphere / muted')
    view=None;audio=None
    try:
        started=time.perf_counter();view=View();startup=time.perf_counter()-started
        intro=Intro(load_script());audio=Audio(automated=True);assert audio.engine.volume==0
        junction=intro.duration-57
        shots=[('01-overcast-lake',45,(-2,4,9),(45,12,-32),68,'exterior',False),
               ('02-river-crossing',30,(14,6,6),(-15,1,-2),62,'exterior',False),
               ('03-river-toward-lake',30,(-10,5,8),(18,-.5,-4),67,'exterior',False),
               ('04-rear-window',62,(.02,1.235,.53),(.02,1.26,7),74,'interior',False),
               ('05-interior-mirror',35,(0,1.31,-.22),(0,1.343,-.584),35,'interior',False),
               ('06-door-mirror',35,(1.25,1.23,.02),(.91,1.07,-.98),28,'exterior',False),
               ('07-turnoff-day-inspection',junction+3,(9,16,20),(8,-1,-22),66,'exterior',True),
               ('08-trail-day-inspection',intro.duration-26,(11,13,20),(0,0,-15),66,'exterior',True),
               ('09-private-track',intro.duration-23,(5,3,8),(-2,1,-23),64,'exterior',False),
               ('10-night-cabin-climb',intro.duration-23,(.02,1.235,.53),(.02,1.08,-1),75,'interior',False),
               ('11-temple-arrival',intro.duration-6,(3,3,8),(0,13,-35),62,'exterior',False),
               ('12-storm-clouds',38,(1,2.8,7),(9,17,-24),67,'exterior',False),
               ('13-paint',38,(3.2,1.6,-4.6),(0,.8,-.2),42,'exterior',False)]
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*7),(18,25,25));labels=ImageDraw.Draw(sheet)
        for i,(name,t,eye,target,fov,mode,day) in enumerate(shots):
            intro.elapsed=t;view.mirror_clock=None;clock=Clock(intro,day)
            view.render(clock,camera_override=camera_from_pose(dict(eye=eye,target=target,fov=fov)),scene_view=mode,overlays=False,apply_fade=False,trails=False)
            image=pil_frame(view.frame);image.save(OUT/(name+'.png'));x=i%2*WIDTH;y=i//2*(HEIGHT+24)
            sheet.paste(image,(x,y));labels.text((x+8,y+HEIGHT+5),name[3:].replace('-',' ').upper(),fill=(220,230,220))
        sheet.save(OUT/'atmosphere-review.png')
        # Mirrors use one rear scenery view plus a cabin composition, at 10Hz.
        intro.elapsed=35.;view.render(intro,overlays=False,apply_fade=False,trails=False)
        capture(view.mirror_world,OUT/'mirror-environment.png');capture(view.mirror_cabin,OUT/'mirror-cabin.png')
        before=view.mirror_updates
        for delta in (.01,.02,.03):intro.elapsed=35+delta;view.render(intro,overlays=False,apply_fade=False,trails=False)
        assert view.mirror_updates==before
        intro.elapsed=36;view.render(intro,overlays=False,apply_fade=False,trails=False)
        assert view.mirror_updates==before+1
        capture(view.mirror_world,OUT/'mirror-environment-later.png')
        with Image.open(OUT/'mirror-environment.png') as a,Image.open(OUT/'mirror-environment-later.png') as b:
            difference=float(np.abs(np.asarray(a,dtype=float)-np.asarray(b,dtype=float)).mean())
        assert difference>.5,difference
        # Look backward while crossing several geometry chunk boundaries.
        frames=[];times=[]
        camera=camera_from_pose(dict(eye=(.02,1.235,.53),target=(.02,1.28,9),fov=74))
        for t in np.linspace(60,68,80):
            intro.elapsed=float(t);start=time.perf_counter()
            view.render(intro,camera_override=camera,scene_view='interior',overlays=False,apply_fade=False,trails=False)
            frames.append(pil_frame(view.frame));times.append(time.perf_counter()-start)
        frames[0].save(OUT/'rear-window-drive.gif',save_all=True,append_images=frames[1:],duration=100,loop=0)
        clearance=road_clearance(view)
        report=dict(audio_gain=audio.engine.volume,mirror_resolution=[128,64],mirror_max_refresh_hz=10,mirror_image_change=difference,
                    rearward_frames=len(frames),max_draw_calls=view.max_draw_calls,median_frame_and_readback_ms=float(np.median(times)*1000),
                    preloaded_chunks=len(view.terrain.chunks),startup_seconds=startup,road_clearance=clearance)
        (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
    finally:
        if audio:audio.close()
        if view:view.close()
        pr.close_window()


if __name__=='__main__':review()
