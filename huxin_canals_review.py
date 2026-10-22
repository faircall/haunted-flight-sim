"""Muted low-water review, plus a read-only smoke of the preserved flooded scene."""
from pathlib import Path
import argparse,hashlib,json,math,time
from unittest.mock import patch
import numpy as np
import pyray as pr
from PIL import Image,ImageDraw
from g_huxin_canals import PATH,SPAWN,DECK
from g_huxin_canals_layout import REVIEW_ROUTE,ROOM_ROUTES,WASHING_ROUTES,THROUGH_HOUSE_ROUTES,UPPER,CAMERA_SHOTS
from temple_interior_viewer import camera,snapshot

ROOT=Path(__file__).parent;OUT=ROOT/'artifacts'/'huxin-canals-smooth-v17'/'walkthrough';WIDTH,HEIGHT=640,360

def protected_hashes():
    original=json.loads((ROOT/'art/temple/huxin_canals/origin_snapshot.json').read_text())['original_sha256']
    flooded=json.loads((ROOT/'art/temple/huxin_canals_flooded/frozen_snapshot.json').read_text())['sha256']
    result={}
    for name,hashes in (('original',original),('flooded',flooded)):
        changed=[p for p,value in hashes.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=value]
        result[name]={'count':len(hashes),'changed':changed}
        assert not changed,(name,changed)
    return result

def texture_pixels(texture):
    im=pr.load_image_from_texture(texture);pr.image_flip_vertical(im)
    a=np.frombuffer(bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4)),np.uint8).reshape(HEIGHT,WIDTH,4)[:,:,:3].copy()
    pr.unload_image(im);return a

def pixels(scene):return texture_pixels(scene.frame.texture)

def camera_signature(cam):
    return tuple(getattr(v,a) for v in (cam.position,cam.target,cam.up) for a in ('x','y','z'))+(cam.fovy,cam.projection)

def delta_report(a,b):
    delta=np.abs(a.astype(float)-b.astype(float))
    return {'mean':float(delta.mean()),'p99':float(np.percentile(delta,99)),'peak':float(delta.max())},delta

def room_visit_schedule():
    """Join each doorway demo at its nearest point on the complete quay tour."""
    visits={}
    for room,points in enumerate(ROOM_ROUTES+WASHING_ROUTES):
        p=points[0];candidates=[]
        for i,(a,b) in enumerate(zip(REVIEW_ROUTE,REVIEW_ROUTE[1:])):
            dx,dz=b[0]-a[0],b[1]-a[1];length=dx*dx+dz*dz
            if length<1e-8:continue
            t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/length))
            projection=(a[0]+t*dx,a[1]+t*dz)
            candidates.append((math.dist(projection,p),i,t,projection))
        distance,i,t,projection=min(candidates)
        assert distance<2.6,('Doorway is disconnected from review tour',room,distance)
        visits.setdefault(i,[]).append((t,room,projection))
    return {i:sorted(v) for i,v in visits.items()}

def review_scene(scene,e,audio,startup,quick=False):
    """Keep the standard --review launcher on the particle-fog contract."""
    from huxin_canals_particle_review import review_scene as particle_review
    return particle_review(scene,e,audio,startup,quick=quick,out=OUT)


def flooded_smoke():
    """Load only frozen modules/assets; outputs live outside the frozen clone."""
    from huxin_canals_flooded_viewer import Lake,Explorer
    from huxin_canals_flooded_audio import EncounterAudio
    from g_huxin_canals_flooded_layout import REVIEW_ROUTE as frozen_route
    from g_huxin_canals_flooded_sequence import ENTRY_SWAP as swap_time,ENTRY_DURATION as duration
    OUT.mkdir(parents=True,exist_ok=True)
    before=protected_hashes();scene=None;audio=None
    try:
        scene=Lake();e=Explorer();e.encounter=q=scene.sequence;audio=EncounterAudio(True)
        e.x,e.z,e.height=1.65,1.65,DECK;q.tick(.01,e);scene.render(e,32.)
        Image.fromarray(pixels(scene)).save(OUT/'flooded-preserved-lake.png')
        camera_before=camera_signature(scene.last_camera);assert scene.water_y==0.
        assert q.activate(e);difference=None
        for frame in range(int((duration+1)*10)):
            q.tick(.1,e);audio.drain(q);scene.render(e,32.+frame*.1)
            assert camera_signature(scene.last_camera)==camera_before
            assert scene.water_y==0.
            if q.revealed and difference is None:
                saved=q.elapsed;q.elapsed=swap_time;q.revealed=False;scene.render(e,40.);a=pixels(scene)
                q.revealed=True;scene.render(e,40.);difference,_=delta_report(a,pixels(scene));q.elapsed=saved
        assert q.state=='canals'
        Image.fromarray(pixels(scene)).save(OUT/'flooded-preserved-reveal.png')
        steps=0
        for x,z in frozen_route[1:11]:
            for _ in range(2000):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.09:break
                e.yaw=math.atan2(dx,-dz);assert e.tick(.05,1)>1e-6
                q.tick(.05,e);steps+=1
            else:raise AssertionError(('Frozen route blocked',x,z))
            scene.render(e,60.+steps*.05)
        Image.fromarray(pixels(scene)).save(OUT/'flooded-preserved-quay.png')
        after=protected_hashes();assert before==after
        report={'protected_scenes':after,'water_y':scene.water_y,'state':q.state,
                'swap_difference':difference,'stationary_camera':camera_before,
                'walk_steps':steps,'audio_muted':audio.muted,'audio_device_opened':audio.opened}
        (OUT/'flooded-smoke-report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2),flush=True)
        assert difference['peak']<8 and not audio.opened
    finally:
        if scene:scene.close()
        if audio:audio.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');p.add_argument('--flooded-smoke',action='store_true');args=p.parse_args()
    from huxin_canals_viewer import Lake,Explorer
    from huxin_canals_audio import EncounterAudio
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Void canals muted review')
    scene=None;audio=None
    try:
        if args.flooded_smoke:flooded_smoke()
        else:
            start=time.perf_counter();scene=Lake();e=Explorer();e.encounter=scene.sequence;audio=EncounterAudio(True)
            review_scene(scene,e,audio,time.perf_counter()-start,args.quick)
    finally:
        if scene:scene.close()
        if audio:audio.close()
        pr.close_window()
