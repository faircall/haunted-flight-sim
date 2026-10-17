"""Muted native-render encounter review, using the same controls and collisions."""
from pathlib import Path
import math,json,time,statistics,hashlib
from g_inventory import add,count
import pyray as pr
from PIL import Image,ImageDraw
from g_huxin_moon import PATH,DECK,SPAWN,walk_height
from g_huxin_moon_sequence import UPPER
from huxin_moon_camera import TEA_SHOTS,FOCUS_EYE,FOCUS_TARGET
from huxin_moon_fog_review import walk_out
from temple_interior_viewer import camera,snapshot

def review_scene(scene,e,audio,startup):
    out=Path(__file__).parent/'artifacts'/'huxin_moon';out.mkdir(exist_ok=True,parents=True)
    q=scene.sequence;clock=32.;frames=[];timings=[];route=[];captures=[];camera_locks=[]
    def render(name=None,override=None,record=False,player=True):
        start=time.perf_counter();cam=scene.render(e,clock,False,override,player)
        if name:snapshot(scene.frame,out/(name+'.png'));captures.append(name)
        if record:
            im=pr.load_image_from_texture(scene.frame.texture);pr.image_flip_vertical(im)
            frames.append(Image.frombytes('RGBA',(640,360),bytes(pr.ffi.buffer(im.data,640*360*4))).convert('RGB'));pr.unload_image(im)
        timings.append((time.perf_counter()-start)*1000)
        return cam
    steps=0
    def walk(points):
        nonlocal clock,steps
        for x,z in points:
            for _ in range(2500):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.09:break
                e.yaw=math.atan2(dx,-dz);dist=e.tick(.05,1);clock+=.05;steps+=1
                q.tick(.05,e);audio.drain(q)
                if dist<.00001:raise AssertionError(('Blocked route',x,z,e.x,e.height,e.z))
                if steps%18==0:
                    route.append((e.x,e.height,e.z));render(record=True)
            else:raise AssertionError(('Route timeout',x,z))
    render('01-the-familiar-pavilion',camera((18,6,25),(0,3,0),61),player=False)
    walk(tuple(p for p in PATH[::4] if p[1]<SPAWN[1] and p[1]>4)+((0,3.3),(1.65,1.65)))
    q.focus=True;e.clip='idle';render('02-moon-in-the-basin')
    for h,v,ticks in ((-1,0,18),(0,-1,11),(0,0,30)):
        for _ in range(ticks):q.adjust(.05,h,v);q.tick(.05,e);clock+=.05;audio.drain(q)
    assert q.state=='entering',(q.state,q.hit())
    position=(e.x,e.height,e.z,e.yaw)
    def transition(prefix):
        nonlocal clock
        before=(e.x,e.height,e.z,e.yaw);entry=q.state=='entering';render();tick=0;last_stage=None
        def camera_pose(cam):return (cam.position.x,cam.position.y,cam.position.z,cam.target.x,cam.target.y,cam.target.z,cam.fovy)
        while q.transitioning:
            old_swaps=len(q.swaps);old_camera=camera_pose(scene.last_camera);old_stage=q.camera_stage;old_shot=scene.last_shot
            if not entry:walk_out(e,q,.1)
            q.tick(.1,e);clock+=.1;audio.drain(q)
            cam=render(record=tick%2==0);tick+=1
            if len(q.swaps)!=old_swaps:
                assert q.camera_stage==old_stage
                if entry:assert camera_pose(cam)==old_camera,(camera_pose(cam),old_camera)
                else:
                    assert scene.last_shot==old_shot
                    assert camera_pose(cam)[:3]==old_camera[:3] and cam.fovy==old_camera[-1]
                    assert math.dist(camera_pose(cam)[3:6],old_camera[3:6])<.2
                camera_locks.append(True);render(prefix+'-mist-pocket')
            if q.camera_stage!=last_stage and q.transitioning:
                render(prefix+'-'+q.camera_stage);last_stage=q.camera_stage
        if entry:assert before==(e.x,e.height,e.z,e.yaw)
        else:assert math.hypot(e.x-before[0],e.z-before[2])>5.
        render(prefix+'-after')
    transition('03-reveal')
    render('04-a-house-on-the-lake',camera((26,10,30),(1,5,0),60),player=False)
    render('05-main-chamber')
    walk(((2.9,1.7),(5.6,.1),(7.5,.1),(8.1,1.95),(10.5,1.95)))
    render('06-three-empty-chairs')
    walk(((8.1,1.95),(7.6,.1),(5.6,.1),(2.9,1.7),(0,3.2),(-3.1,3.2),(-5.65,5.25),(-5.65,4.6),(-5.65,-4.95)))
    assert abs(e.height-UPPER)<.001
    render('07-real-stair-and-landing')
    walk(((-3.4,-5.1),(-1,-3.7),(.8,-.8),(3.8,-.8),(3.8,-2.7),(4.5,-3.5)))
    render('08-the-empty-tray')
    # Future inventory data is intentionally independent of architecture state.
    assert add(q.inventory,{'kind':'key','group':'review-retention-probe','count':1})
    walk(((3.8,-2.7),(3.8,-.8),(0,1),(0,5.3),(0,7.2),(4.8,7.2)))
    render('09-upper-balcony')
    walk(((0,7.2),(0,5.2),(-3.6,2),(-3.6,-5.0),(-5.65,-5.0),(-5.65,4.8),(-5.65,5.35),(-3.1,3.2),(0,3.2),(0,5.4)))
    assert abs(e.height-DECK)<.001
    walk(((0,7),(-1.3,11),(-3,16),(-3.1,18.3)))
    assert q.state=='leaving'
    transition('10-return')
    assert q.state=='returned' and not q.revealed and q.bells==1
    assert count(q.inventory,'key')==1
    render('11-ordinary-again',camera((18,6,25),(0,3,0),61),player=False)
    frames[0].save(out/'moon-encounter.gif',save_all=True,append_images=frames[1:],duration=200,loop=0,optimize=True)
    sheet=Image.new('RGB',(1280,385*math.ceil(len(captures)/2)),(12,23,25));labels=ImageDraw.Draw(sheet)
    for i,name in enumerate(captures):
        x=i%2*640;y=i//2*385;sheet.paste(Image.open(out/(name+'.png')).convert('RGB'),(x,y));labels.text((x+8,y+365),name,fill=(203,211,195))
    sheet.save(out/'moon-review.png')
    root=Path(__file__).parent;original=json.loads((root/'art'/'temple'/'huxin_moon'/'origin_snapshot.json').read_text())['original_sha256']
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in original.items())
    report=dict(audio_muted=audio.muted,audio_device_opened=audio.opened,audio_events=audio.played,swaps=q.swaps,
        state=q.state,inventory_preserved=True,camera_continuity_at_swaps=camera_locks,player_preserved_at_reveal=position,
        walk_steps=steps,route=route,frames=len(frames),startup_seconds=startup,
        median_frame_readback_ms=statistics.median(timings),added_triangles=scene.tea_manifest['total_triangles'],original_assets_unchanged=True)
    (out/'encounter-report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='route'},indent=2),flush=True)
