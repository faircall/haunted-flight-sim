"""Muted native landscape review; never edits authored cameras or progress."""
from setup_temple_3d import ensure_runtime
if __name__=='__main__':ensure_runtime()
import json
import time
from pathlib import Path
from PIL import Image,ImageDraw
import pyray as pr
from g_temple_intro import Intro,load_script,local_point
from temple_intro_viewer import View,Audio,camera_from_pose,capture,WIDTH,HEIGHT

OUT=Path(__file__).parent/'artifacts'/'intro-landscape'


def pixels(target):
    import numpy as np
    image=pr.load_image_from_texture(target.texture)
    pr.image_format(image,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
    values=np.frombuffer(bytes(pr.ffi.buffer(image.data,WIDTH*HEIGHT*4)),dtype=np.uint8).reshape(HEIGHT,WIDTH,4)
    pr.unload_image(image);return values[:,:,:3].astype(float)


def gpu_contracts(view,intro):
    """Exercise real depth sampling and UV wind, without rain/camera motion."""
    import numpy as np
    from g_intro_landscape import car_pose,car_point
    intro.elapsed=114.;height,pitch=car_pose(intro.distance,intro.arrival_station)
    cp=lambda p:car_point(p,height,pitch)
    camera=camera_from_pose(dict(eye=cp((0,1,0)),target=cp((0,1,-5)),fov=60))
    camera.up=pr.Vector3(*car_point((0,1,0),height,pitch,True))
    camera.projection=pr.CAMERA_ORTHOGRAPHIC;camera.fovy=3
    fog=pr.Color(24,37,47,255);s=view.scene_shader
    view.uniform(s,'eyePosition',cp((0,1,0)));view.uniform(s,'dusk',1.)
    view.uniform(s,'headlights',0.);view.uniform(s,'interior',0.)
    view.uniform(s,'surface',0,'int');view.uniform(s,'fogEnd',0.)
    differences=[];view.car_height=height;view.car_pitch=pitch;view.car_space=True
    for depth in (3,32):
        pr.begin_texture_mode(view.world);pr.clear_background(pr.BLACK)
        pr.begin_mode_3d(camera)
        view.draw('cube',(0,1,-depth),(20,20,.3),tint=pr.Color(80,90,85,255))
        pr.end_mode_3d();pr.end_texture_mode()
        before=pixels(view.world)
        view.mist.draw(view.misty_world,view.world,camera,intro,fog,view.copy)
        after=pixels(view.misty_world)
        differences.append(float(np.abs(before-after).mean()))
    # A near opaque wall cuts off the volume, a far wall admits the headlight mist.
    assert differences[1]>differences[0]+2,differences
    view.car_space=False
    camera=camera_from_pose(dict(eye=(8,4,8),target=(0,3.2,0),fov=45))
    tree=view.models['chinese_pine_a'];mesh=tree.meshes[0]
    vertices=bytes(pr.ffi.buffer(mesh.vertices,mesh.vertexCount*12));frames=[]
    view.uniform(s,'dusk',.18);view.uniform(s,'surface',3,'int')
    view.uniform(s,'eyePosition',(8,4,8))
    for t in (0,1.7):
        view.uniform(s,'time',t)
        pr.begin_texture_mode(view.world);pr.clear_background(pr.Color(105,121,115,255))
        pr.begin_mode_3d(camera);pr.rl.rlDisableBackfaceCulling();view.draw('chinese_pine_a')
        pr.rl.rlEnableBackfaceCulling();pr.end_mode_3d();pr.end_texture_mode()
        frames.append(pixels(view.world))
    changed=int(np.count_nonzero(np.any(frames[0]!=frames[1],axis=2)))
    assert changed>100,changed
    assert vertices==bytes(pr.ffi.buffer(mesh.vertices,mesh.vertexCount*12))
    capture(view.world,OUT/'pine-wind-inspection.png')
    # Freeze the opaque scene and road position: only the volume's clock moves.
    from types import SimpleNamespace
    camera=camera_from_pose(dict(eye=(50,3,0),target=(130,1,-45),fov=62))
    clock=SimpleNamespace(elapsed=45.,distance=472.5,dusk=.18,headlights=0.)
    pr.begin_texture_mode(view.world);pr.clear_background(pr.Color(35,72,59,255));pr.end_texture_mode()
    volume=[]
    for t in (45.,53.):
        clock.elapsed=t;view.mist.draw(view.misty_world,view.world,camera,clock,pr.Color(179,198,182,255),view.copy)
        volume.append(pixels(view.misty_world))
    rolling=float(np.abs(volume[0]-volume[1]).mean());assert rolling>.3,rolling
    return dict(near_wall_fog_difference=differences[0],far_wall_fog_difference=differences[1],
                wind_changed_pixels=changed,wind_keeps_cpu_mesh=True,rolling_volume_only_difference=rolling)


def review():
    OUT.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(WIDTH,HEIGHT,'Lakeside approach / muted review')
    view=None;audio=None;report=[]
    shots=[('01-lakeside',45.,(-.8,3.5,9),(70,12,-38),68),
           ('02-road-and-mountains',50.,(12,7,12),(-20,12,-33),66),
           ('03-pine-boughs',24.,(-.5,2,5),(-5,4.1,-3),56),
           ('04-headlight-mist',114.,(6,3.2,4),(-.5,1,-13),61),
           ('05-lake-at-night',114.,(-6,4,8),(30,4,-22),62)]
    try:
        view=View();audio=Audio(automated=True);assert audio.engine.volume==0
        intro=Intro(load_script())
        for name,t,eye,target,fov in shots:
            intro.elapsed=t;camera=camera_from_pose(dict(eye=eye,target=target,fov=fov))
            start=time.perf_counter()
            view.render(intro,camera_override=camera,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
            capture(view.frame,OUT/(name+'.png'))
            report.append(dict(name=name,draw_calls=view.draw_calls,seconds=time.perf_counter()-start))
        intro.elapsed=intro.duration-4
        x,z=local_point(intro.arrival_station,0,intro.distance)
        camera=camera_from_pose(dict(eye=(2,1.65,3),target=(x,4.3,z),fov=58))
        view.render(intro,camera_override=camera,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
        capture(view.frame,OUT/'06-arrival-steps.png')
        # Compare the real GPU volume toggle, including the shared scene depth.
        intro.elapsed=114.;camera=camera_from_pose(dict(eye=(6,3.2,4),target=(-.5,1,-13),fov=61))
        view.mist.enabled=False
        view.render(intro,camera_override=camera,scene_view='exterior',overlays=False,apply_fade=False,trails=False)
        capture(view.frame,OUT/'fog-disabled.png');view.mist.enabled=True
        with Image.open(OUT/'04-headlight-mist.png') as a,Image.open(OUT/'fog-disabled.png') as b:
            import numpy as np
            difference=float(np.abs(np.array(a,dtype=float)-np.array(b,dtype=float)).mean())
        assert difference>.3,difference
        assert view.max_draw_calls<540
        contracts=gpu_contracts(view,intro)
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+25)*3),(19,26,29));labels=ImageDraw.Draw(sheet)
        for i,name in enumerate([s[0] for s in shots]+['06-arrival-steps']):
            x=(i%2)*WIDTH;y=(i//2)*(HEIGHT+25)
            with Image.open(OUT/(name+'.png')) as picture:sheet.paste(picture,(x,y))
            labels.text((x+8,y+HEIGHT+6),name[3:].replace('-',' ').upper(),fill=(204,217,206))
        sheet.save(OUT/'landscape-review.png')
        (OUT/'report.json').write_text(json.dumps(dict(samples=report,max_draw_calls=view.max_draw_calls,
                 fog_image_difference=difference,audio_output_gain=audio.engine.volume,
                 depth_texture=True,gpu_contracts=contracts),indent=2)+'\n')
        print('Muted landscape review passed:',report,'fog image difference',difference,flush=True)
    finally:
        if audio:audio.close()
        if view:view.close()
        pr.close_window()


if __name__=='__main__':review()
