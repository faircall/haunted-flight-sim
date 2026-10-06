"""Inspect the Santana in the actual intro renderer, without changing shot data.

Run with artifacts/temple3d-env/Scripts/python.exe temple_car_review.py.
The empty-cabin views temporarily hide actors to expose normally obscured trim.
"""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageOps
import pyray as pr
from g_temple_intro import Intro, load_script
from temple_intro_viewer import View, camera_from_pose, capture, WIDTH, HEIGHT

ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'artifacts'/'santana-car'
ACTORS={'driver','colleague','driver_head','colleague_head','player_seated','player_lap'}


def reference_comparison():
    """QA only: compare equally sized empty side profiles from reference/game."""
    reference=ROOT/'artdev'/'car_reference_2.png'
    if not reference.exists():return
    with Image.open(reference) as original:
        ref=original.convert('RGB').crop((738,136,1438,400))
    with Image.open(FOLDER/'09-side-profile.png') as native:
        car=ImageOps.mirror(native.convert('RGB')).crop((16,63,455,217))
    sheet=Image.new('RGB',(960,750),(26,31,33));labels=ImageDraw.Draw(sheet)
    for name,picture,top in (('SUPPLIED REFERENCE / SIDE VIEW',ref,38),
                             ('REBUILT CAR / EMPTY GAME ORTHOGRAPHIC VIEW',car,406)):
        h=round(picture.height*860/picture.width)
        picture=picture.resize((860,h),Image.Resampling.NEAREST)
        sheet.paste(picture,(50,top));labels.text((50,top-23),name,fill=(221,225,213))
    labels.text((50,718),'Profiles use the same bumper-to-bumper image span. No occupants in the rebuilt car.',fill=(173,188,177))
    sheet.save(FOLDER/'reference-comparison.png')


def review():
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(960,540,'Santana / native asset review')
    view=None
    shots=[
        ('01-front-quarter',(3.7,1.70,-5.4),(0,.76,-.15),40,'exterior',18.,True),
        ('02-rear-quarter',(-3.7,1.70,5.4),(0,.78,-.12),40,'exterior',18.,True),
        ('03-dashboard',(0,1.22,-.22),(0,.81,-.88),75,'interior',18.,True),
        ('04-door-card',(-.18,1.12,.53),(.77,.70,.53),67,'interior',18.,True),
        ('05-front-seats',(0,1.31,.76),(0,.69,-.28),75,'interior',18.,True),
        ('06-rear-seats',(0,1.31,.18),(0,.79,.81),80,'interior',18.,True),
        ('07-night-front',(3.7,1.70,-5.4),(0,.76,-.15),40,'exterior',113.,True),
        ('08-occupied-back-seat',(.02,1.235,.53),(.02,1.04,-1.3),75,'interior',18.,False),
        ('09-side-profile',(3.15,.80,0),(0,.80,0),60,'exterior',18.,True),
        ('10-front-profile',(0,.80,-4),(0,.80,0),60,'exterior',18.,True),
        ('11-top-profile',(0,6,0),(0,0,0),60,'exterior',18.,True),
    ]
    try:
        view=View();intro=Intro(load_script());draw=view.draw
        FOLDER.mkdir(parents=True,exist_ok=True)
        samples=[]
        for name,eye,target,fov,mode,timestamp,empty in shots:
            view.draw=lambda name,*args,**kwargs: None if empty and name in ACTORS else draw(name,*args,**kwargs)
            intro.elapsed=timestamp
            camera=camera_from_pose(dict(eye=eye,target=target,fov=fov))
            if name in ('09-side-profile','10-front-profile','11-top-profile'):
                camera.projection=pr.CAMERA_ORTHOGRAPHIC;camera.fovy=2.85
                if name=='11-top-profile':camera.up=pr.Vector3(0,0,-1);camera.fovy=5.2
            view.render(intro,camera_override=camera,scene_view=mode,overlays=False,apply_fade=False,trails=False)
            pr.begin_drawing();pr.clear_background(pr.BLACK)
            pr.draw_texture_pro(view.frame.texture,pr.Rectangle(0,0,WIDTH,-HEIGHT),
                                pr.Rectangle(0,0,960,540),pr.Vector2(0,0),0,pr.WHITE)
            pr.end_drawing();capture(view.frame,FOLDER/(name+'.png'))
            samples.append(dict(name=name,camera=eye,target=target,view=mode,actors_hidden=empty,time=timestamp))
        sheet=Image.new('RGB',(WIDTH*3,(HEIGHT+24)*2),(19,24,26));labels=ImageDraw.Draw(sheet)
        for i,(name,*_) in enumerate(shots[:6]):
            x=(i%3)*WIDTH;y=(i//3)*(HEIGHT+24)
            with Image.open(FOLDER/(name+'.png')) as frame:sheet.paste(frame,(x,y))
            labels.text((x+10,y+HEIGHT+5),name[3:].replace('-',' ').upper(),fill=(212,222,212))
        sheet.save(FOLDER/'santana-review.png')
        reference_comparison()
        (FOLDER/'report.json').write_text(json.dumps(dict(samples=samples,glass_panes=len(view.windows),
            actual_game_renderer=True,resolution=[WIDTH,HEIGHT]),indent=2)+'\n',encoding='utf-8')
        assert len(view.windows)==6
    finally:
        if view:view.close()
        pr.close_window()
    print('Santana native review passed: exterior, dashboard, doors, both seat rows, night and occupied cabin.')


if __name__=='__main__':review()
