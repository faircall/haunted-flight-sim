"""Muted V2 review: stationary reveal, reflected mist and hollow architecture."""
from pathlib import Path
import argparse,hashlib,json,math,time
import numpy as np
import pyray as pr
from PIL import Image,ImageDraw
from g_huxin_canals_flooded import PATH,SPAWN,DECK
from g_huxin_canals_flooded_layout import REVIEW_ROUTE,ROOM_ROUTES,UPPER,CAMERA_SHOTS
from g_huxin_canals_flooded_sequence import ENTRY_SWAP,ENTRY_DURATION
from temple_interior_viewer import camera,snapshot

ROOT=Path(__file__).parent;OUT=ROOT/'artifacts'/'huxin_canals_flooded_v2';WIDTH,HEIGHT=640,360

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

def review_scene(scene,e,audio,startup,quick=False):
    OUT.mkdir(parents=True,exist_ok=True);q=scene.sequence;clock=32.;steps=0;cards=[];frames=[];reveal=[];timings=[];visibility=[];camera_changes=[]
    def render(label=None,record=False,override=None,player=True):
        start=time.perf_counter();scene.render(e,clock,override=override,show_player=player);im=pixels(scene);timings.append((time.perf_counter()-start)*1000)
        if label:cards.append((label,im));Image.fromarray(im).save(OUT/(label+'.png'))
        if record and not quick:frames.append(Image.fromarray(im))
        return im
    def check_visible(label):
        a=render();b=render(player=False);n=int((np.max(np.abs(a.astype(float)-b.astype(float)),axis=2)>3).sum())
        visibility.append((label,n,scene.last_shot))
    def walk(points,record=True):
        nonlocal clock,steps
        for x,z in points:
            for _ in range(3000):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.09:break
                e.yaw=math.atan2(dx,-dz);dist=e.tick(.05,1);q.tick(.05,e);audio.drain(q);clock+=.05;steps+=1
                if dist<1e-6:raise AssertionError(('Blocked route',x,z,e.x,e.height,e.z))
                if record and steps%20==0:render(record=True)
            else:raise AssertionError(('Route timeout',x,z))
    render('01-familiar-lake',override=camera((18,6,25),(0,3,0),61),player=False)
    walk(tuple(p for p in PATH[::4] if 4<p[1]<SPAWN[1])+((0,3.3),(1.65,1.65)))
    e.clip='idle';pose=(e.x,e.height,e.z,e.yaw)
    before_frame=render('02-before-the-annulus')
    stationary_camera=camera_signature(scene.last_camera);stationary_shot=scene.last_shot
    if not quick:reveal.extend([Image.fromarray(before_frame)]*5)
    assert q.activate(e);audio.drain(q)
    render('02-the-stone-annulus')
    assert camera_signature(scene.last_camera)==stationary_camera
    swap_delta=None;reflection_delta=None;reflection_raw_delta=None;saved_times=set()
    for i in range(int((ENTRY_DURATION+1.)*30)+1):
        if q.transitioning:
            q.tick(1/30,e);audio.drain(q)
        clock+=1/30
        frame=render(record=i%6==0)
        if camera_signature(scene.last_camera)!=stationary_camera or scene.last_shot!=stationary_shot:
            camera_changes.append({'frame':i,'state':q.state,'elapsed':q.elapsed,'camera':camera_signature(scene.last_camera)})
        if i%6==0 and not quick:reveal.append(Image.fromarray(frame))
        for t in (4,ENTRY_SWAP,10,14,18,ENTRY_DURATION-.1):
            if t not in saved_times and q.transitioning and q.elapsed>=t:
                saved_times.add(t);render('03-stationary-mist-%02d'%round(t))
        if q.revealed and swap_delta is None:
            saved=q.elapsed;q.elapsed=ENTRY_SWAP;q.revealed=False;a=render();ra=texture_pixels(scene.reflection.texture);raw_a=texture_pixels(scene.reflection_raw.texture)
            q.revealed=True;b=render();rb=texture_pixels(scene.reflection.texture);raw_b=texture_pixels(scene.reflection_raw.texture)
            swap_delta,delta=delta_report(a,b);reflection_delta,reflected=delta_report(ra,rb)
            reflection_raw_delta,_=delta_report(raw_a,raw_b)
            Image.fromarray(np.minimum(255,delta*8).astype('uint8')).save(OUT/'swap-difference-x8.png')
            Image.fromarray(np.minimum(255,reflected*8).astype('uint8')).save(OUT/'reflection-swap-difference-x8.png');q.elapsed=saved
    assert q.state=='canals' and pose==(e.x,e.height,e.z,e.yaw)
    render('04-same-pavilion-other-world');check_visible('after reveal')
    assert not camera_changes,camera_changes[:3]
    # Actual controls follow the complete, interconnected district.
    rooms_visited=set()
    for i,p in enumerate(REVIEW_ROUTE[1:]):
        walk((p,));check_visible('route-%02d'%i)
        if i in (2,5,9,12,14,15,18,22,25,29,31,34):render('05-route-%02d'%i)
        for room,route in enumerate(ROOM_ROUTES):
            if room not in rooms_visited and math.dist(p,route[0])<4.:
                walk((route[0],))
                for step,station in enumerate(route[1:]):
                    walk((station,));check_visible('room-%02d-step-%02d'%(room,step))
                    if step==len(route)//2-1:render('05-vacant-room-%02d'%room)
                walk((p,));rooms_visited.add(room)
    assert len(rooms_visited)==len(ROOM_ROUTES),rooms_visited
    assert q.state=='canals' and q.revealed and len(q.swaps)==1
    from g_huxin_canals_flooded_layout import REVIEW_VIEWS
    for index,view in enumerate(REVIEW_VIEWS):
        render('06-%02d-%s'%(index,view['name']),override=camera(view['eye'],view['target'],view.get('fov',65)),player=False)
    sheet=Image.new('RGB',(1280,384*math.ceil(len(cards)/2)),(15,20,21));draw=ImageDraw.Draw(sheet)
    for i,(label,im) in enumerate(cards):
        x=i%2*640;y=i//2*384;sheet.paste(Image.fromarray(im),(x,y));draw.text((x+8,y+365),label,fill=(201,207,202))
    sheet.save(OUT/'canals-review.png')
    if not quick:
        reveal[0].save(OUT/'void-canals-reveal.gif',save_all=True,append_images=reveal[1:],duration=200,loop=0,optimize=True)
        frames[0].save(OUT/'void-canals-walkthrough.gif',save_all=True,append_images=frames[1:],duration=200,loop=0,optimize=True)
    hashes=json.loads((ROOT/'art/temple/huxin_canals_flooded/origin_snapshot.json').read_text())['original_sha256']
    preserved=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    report={'state':q.state,'swaps':q.swaps,'original_files_unchanged':preserved,'protected_files':len(hashes),
            'swap_difference':swap_delta,'reflection_swap_difference':reflection_delta,
            'reflection_raw_swap_difference':reflection_raw_delta,
            'reflected_difference_ratio':reflection_delta['mean']/max(.000001,reflection_raw_delta['mean']),
            'stationary_camera_changes':camera_changes,'stationary_camera':stationary_camera,
            'player_visibility':visibility,'audio_muted':audio.muted,'audio_device_opened':audio.opened,
            'frames':len(frames),'walk_steps':steps,'median_render_readback_ms':float(np.median(timings)),
            'startup_seconds':startup,'triangles':scene.canals_manifest['total_triangles'],'buildings':scene.canals_manifest.get('building_count')}
    (OUT/'review-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
    assert preserved and not audio.opened
    assert swap_delta['mean']<1.5 and swap_delta['p99']<8 and swap_delta['peak']<8,swap_delta
    # This RT contains only the surface-to-reflected-object leg. The final
    # composite above also fogs the camera-to-water leg and is the authoritative
    # all-visible-pixels concealment check. RT-only pixels can include quays
    # close to the water or texels never sampled by any visible water fragment.
    # Require a large reduction to catch a lost reflection-fog pass, without
    # fitting a fragile percentage to this one composition's visible quays.
    assert reflection_delta['mean'] < max(.01,reflection_raw_delta['mean']*.25),(reflection_raw_delta,reflection_delta)
    assert all(n>25 for label,n,shot in visibility),visibility

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true');args=p.parse_args()
    from huxin_canals_flooded_viewer import Lake,Explorer
    from huxin_canals_flooded_audio import EncounterAudio
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Void canals muted review')
    scene=None;audio=None
    try:
        start=time.perf_counter();scene=Lake();e=Explorer();e.encounter=scene.sequence;audio=EncounterAudio(True)
        review_scene(scene,e,audio,time.perf_counter()-start,args.quick)
    finally:
        if scene:scene.close()
        if audio:audio.close()
        pr.close_window()
