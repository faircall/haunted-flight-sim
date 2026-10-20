"""Muted low-water review, plus a read-only smoke of the preserved flooded scene."""
from pathlib import Path
import argparse,hashlib,json,math,time
from unittest.mock import patch
import numpy as np
import pyray as pr
from PIL import Image,ImageDraw
from g_huxin_canals import PATH,SPAWN,DECK
from g_huxin_canals_layout import REVIEW_ROUTE,ROOM_ROUTES,WASHING_ROUTES,THROUGH_HOUSE_ROUTES,UPPER,CAMERA_SHOTS
from g_huxin_canals_sequence import (ENTRY_SWAP,ENTRY_DURATION,FOG_ARRIVAL_DURATION,
                                   REVEAL_START_RADIUS,REVEAL_END_RADIUS)
from temple_interior_viewer import camera,snapshot

ROOT=Path(__file__).parent;OUT=ROOT/'artifacts'/'huxin-canals-grid-v10'/'walkthrough';WIDTH,HEIGHT=640,360

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
    OUT.mkdir(parents=True,exist_ok=True);q=scene.sequence;clock=32.;steps=0;cards=[];frames=[];reveal=[];timings=[];visibility=[];camera_changes=[]
    def render(label=None,record=False,override=None,player=True):
        start=time.perf_counter();scene.render(e,clock,override=override,show_player=player);im=pixels(scene);timings.append((time.perf_counter()-start)*1000)
        if label:cards.append((label,im));Image.fromarray(im).save(OUT/(label+'.png'))
        if record and not quick:frames.append(Image.fromarray(im))
        return im
    def check_visible(label):
        a=render();b=render(player=False);n=int((np.max(np.abs(a.astype(float)-b.astype(float)),axis=2)>3).sum())
        visibility.append((label,n,scene.last_shot))
        if n<=25:print('VISIBILITY',label,n,scene.last_shot,(e.x,e.height,e.z),flush=True)
    def check_spatial_blend():
        """Audit complete endpoint images at real positions reached by walking."""
        weight=q.world_blend
        if not 0.<weight<1.:return
        level=next((v for v in (.15,.5,.85) if weight>=v and v not in blend_levels),None)
        if level is None:return
        passes=[];mist_pass=scene.mist_pass;logical=q.revealed
        def track_pass(*args,**kwargs):
            passes.append((scene.render_revealed,scene.water_y,bool(kwargs.get('reflected',False))))
            return mist_pass(*args,**kwargs)
        with patch.object(scene,'mist_pass',side_effect=track_pass):frame=render()
        old=texture_pixels(scene.blend_old_frame.texture).astype(float)
        new=texture_pixels(scene.blend_new_frame.texture).astype(float)
        composition,_=delta_report(frame,old*(1.-weight)+new*weight)
        assert composition['peak']<=2,composition
        assert passes==[(False,0.,True),(False,0.,False),(True,-1.55,True),(True,-1.55,False)],passes
        assert q.revealed==logical
        assert scene.last_world_weights=={'lake':1.-weight,'canals':weight}
        reached=q.exploration.furthest_distance
        assert REVEAL_START_RADIUS<reached<REVEAL_END_RADIUS,reached
        blend_checks.append({'reached_radius':reached,'position':[e.x,e.height,e.z],
                             'weight':weight,'endpoint_composition':composition,'endpoint_water_passes':passes})
        blend_levels.add(level)
    def walk(points,record=True):
        nonlocal clock,steps
        for x,z in points:
            for _ in range(3000):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.09:break
                clearing=q.fog_clear
                e.yaw=math.atan2(dx,-dz);dist=e.tick(.05,1);q.tick(.05,e);audio.drain(q);clock+=.05;steps+=1
                if q.state=='canals':assert q.fog_clear>=clearing,'Retracing the route rebuilt the fog'
                if q.state=='canals':check_spatial_blend()
                if dist<1e-6:raise AssertionError(('Blocked route',x,z,e.x,e.height,e.z))
                if record and steps%20==0:render(record=True)
            else:raise AssertionError(('Route timeout',x,z))
    preserved_before=protected_hashes()
    assert scene.water_y==0.
    render('01-familiar-lake',override=camera((18,6,25),(0,3,0),61),player=False)
    walk(tuple(p for p in PATH[::4] if 4<p[1]<SPAWN[1])+((0,3.3),(1.65,1.65)))
    e.clip='idle';pose=(e.x,e.height,e.z,e.yaw)
    before_frame=render('02-before-the-annulus')
    stationary_camera=camera_signature(scene.last_camera);stationary_shot=scene.last_shot
    if not quick:reveal.extend([Image.fromarray(before_frame)]*5)
    assert q.activate(e);audio.drain(q)
    render('02-the-stone-annulus')
    assert camera_signature(scene.last_camera)==stationary_camera
    swap_delta=None;reflection_delta=None;reflection_raw_delta=None;blend_checks=[];blend_levels=set();unlock_delta=None;saved_times=set();retreat_samples=[]
    for i in range(int((ENTRY_DURATION+1.)*30)+1):
        q.tick(1/30,e);audio.drain(q)
        clock+=1/30
        frame=render(record=i%6==0)
        if camera_signature(scene.last_camera)!=stationary_camera or scene.last_shot!=stationary_shot:
            camera_changes.append({'frame':i,'state':q.state,'elapsed':q.elapsed,'camera':camera_signature(scene.last_camera)})
        if i%6==0 and not quick:reveal.append(Image.fromarray(frame))
        for t in (1,2,ENTRY_SWAP-1.,ENTRY_DURATION,ENTRY_DURATION+1.):
            if t not in saved_times and q.elapsed>=t:
                saved_times.add(t);render('03-stationary-mist-%02d'%round(t))
                retreat_samples.append({'elapsed':q.elapsed,'grid_revision':q.fog_grid.revision,'veil':q.veil,
                                        'arrival':q.fog_arrival,'trailing_depth':q.fog_depth,
                                        'world_blend':q.world_blend,'void_tone':q.void_tone})
        assert q.world_blend==0. and q.void_tone==0.,'Time alone revealed or regraded the village'
        assert scene.last_world_weights=={'lake':1.,'canals':0.}
        if not q.transitioning and unlock_delta is None:
            # Control/collision state commits at five seconds, but the visible
            # world is still the lake. Hold time, camera and actor position;
            # exclude animation blending from this exact state-boundary check.
            saved=(q.state,q.elapsed,q.revealed)
            q.state='entering';q.elapsed=ENTRY_DURATION;q.revealed=False
            a=render(player=False);ra=texture_pixels(scene.reflection.texture);raw_a=texture_pixels(scene.reflection_raw.texture)
            q.state='canals';q.elapsed=ENTRY_DURATION;q.revealed=True
            b=render(player=False);rb=texture_pixels(scene.reflection.texture);raw_b=texture_pixels(scene.reflection_raw.texture)
            swap_delta,delta=delta_report(a,b);reflection_delta,reflected=delta_report(ra,rb)
            reflection_raw_delta,_=delta_report(raw_a,raw_b)
            Image.fromarray(np.minimum(255,delta*8).astype('uint8')).save(OUT/'swap-difference-x8.png')
            Image.fromarray(np.minimum(255,reflected*8).astype('uint8')).save(OUT/'reflection-swap-difference-x8.png')
            unlock_delta=swap_delta
            Image.fromarray(np.minimum(255,delta*8).astype('uint8')).save(OUT/'unlock-difference-x8.png')
            q.state,q.elapsed,q.revealed=saved
    assert q.state=='canals' and pose==(e.x,e.height,e.z,e.yaw)
    assert scene.last_world_weights=={'lake':1.,'canals':0.} and e.height==DECK
    render('04-controls-restored-lake-retained');check_visible('after control release')
    idle_before=(q.fog_clear,q.fog_grid.revision,q.veil,q.world_blend,q.void_tone)
    arrival_before=(q.fog_arrival,q.fog_depth)
    for frame in range(60*60):
        q.tick(1/60,e);audio.drain(q);clock+=1/60
        if frame+1 in (5*60,15*60,30*60,60*60):
            render('04-idle-%02d-seconds'%((frame+1)//60))
            assert scene.last_world_weights=={'lake':1.,'canals':0.}
            assert camera_signature(scene.last_camera)==stationary_camera and scene.last_shot==stationary_shot
    assert (q.fog_clear,q.fog_grid.revision,q.veil,q.world_blend,q.void_tone)==idle_before
    assert q.elapsed==FOG_ARRIVAL_DURATION
    assert q.fog_arrival>=arrival_before[0] and q.fog_depth>=arrival_before[1]
    assert q.fog_clear==0. and not q.movement_locked
    check_visible('after stationary fog arrival')
    assert not camera_changes,camera_changes[:3]
    if not quick:
        reveal[0].save(OUT/'void-canals-reveal.gif',save_all=True,append_images=reveal[1:],duration=200,loop=0,optimize=True)
    (OUT/'reveal-report.json').write_text(json.dumps({
        'entry_duration':ENTRY_DURATION,'swap_difference':swap_delta,
        'unlock_difference':unlock_delta,'retreat_samples':retreat_samples,
        'stationary_camera_changes':camera_changes,'stationary_world_blend':q.world_blend,
        'idle_60_seconds_no_discovery_or_grade':True,'fog_arrival_duration':FOG_ARRIVAL_DURATION,
        'audio_muted':audio.muted,'audio_device_opened':audio.opened},indent=2))
    # Actual controls follow the complete, interconnected district.
    rooms_visited=set();visits=room_visit_schedule()
    rear_visits={len(ROOM_ROUTES)+r['washing_index']:r for r in THROUGH_HOUSE_ROUTES}
    for i,p in enumerate(REVIEW_ROUTE[1:]):
        for _,room,projection in visits.get(i,()):
            route=(ROOM_ROUTES+WASHING_ROUTES)[room]
            if room not in rooms_visited:
                walk((projection,))
                walk((route[0],))
                for step,station in enumerate(route[1:]):
                    label='rear-house-%s'%rear_visits[room]['seed'] if room in rear_visits else 'room-%02d'%room
                    walk((station,));check_visible('%s-step-%02d'%(label,step))
                    if step==len(route)//2-1:render('05-'+label+'-landing' if room in rear_visits else '05-vacant-room-%02d'%room)
                walk((projection,));rooms_visited.add(room)
        walk((p,));check_visible('route-%02d'%i)
        if i in (2,5,9,12,14,15,18,22,25,29,31,34):render('05-route-%02d'%i)
    assert len(rooms_visited)==len(ROOM_ROUTES)+len(WASHING_ROUTES),rooms_visited
    assert q.state=='canals' and q.revealed and len(q.swaps)==1
    assert q.world_blend==1. and q.void_tone==q.fog_clear
    from g_huxin_canals_layout import REVIEW_VIEWS
    for index,view in enumerate(REVIEW_VIEWS):
        render('06-%02d-%s'%(index,view['name']),override=camera(view['eye'],view['target'],view.get('fov',65)),player=False)
    sheet=Image.new('RGB',(1280,384*math.ceil(len(cards)/2)),(15,20,21));draw=ImageDraw.Draw(sheet)
    for i,(label,im) in enumerate(cards):
        x=i%2*640;y=i//2*384;sheet.paste(Image.fromarray(im),(x,y));draw.text((x+8,y+365),label,fill=(201,207,202))
    sheet.save(OUT/'canals-review.png')
    if not quick:
        frames[0].save(OUT/'void-canals-walkthrough.gif',save_all=True,append_images=frames[1:],duration=200,loop=0,optimize=True)
    hashes=json.loads((ROOT/'art/temple/huxin_canals/origin_snapshot.json').read_text())['original_sha256']
    preserved=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    protection=protected_hashes();assert protection==preserved_before
    portals=[p for h in scene.canals_manifest['houses'] for p in h.get('door_portals',()) if p.get('accessible')]
    report={'state':q.state,'swaps':q.swaps,'original_files_unchanged':preserved,'protected_files':len(hashes),
            'protected_scenes':protection,'water_y':scene.water_y,'deck_y':DECK,
            'swap_difference':swap_delta,'reflection_swap_difference':reflection_delta,
            'reflection_raw_swap_difference':reflection_raw_delta,
            'reflection_note':'Raw/reflection targets hold the last rendered endpoint during blending; complete-frame continuity and weighted endpoint composition are authoritative.',
            'world_blend_checks':blend_checks,'idle_60_seconds_no_discovery_or_grade':True,'exploration_clearing':q.fog_clear,
            'fog_arrival_duration':FOG_ARRIVAL_DURATION,'spatial_reveal_radii':[REVEAL_START_RADIUS,REVEAL_END_RADIUS],
            'unlock_difference':unlock_delta,'retreat_samples':retreat_samples,'entry_duration':ENTRY_DURATION,
            'stationary_camera_changes':camera_changes,'stationary_camera':stationary_camera,
            'player_visibility':visibility,'audio_muted':audio.muted,'audio_device_opened':audio.opened,
            'accessible_door_bays':len(portals),'front_door_bays':sum(p.get('side','front')=='front' for p in portals),
            'rear_door_bays':sum(p.get('side')=='rear' for p in portals),'through_house_rear_excursions':len(THROUGH_HOUSE_ROUTES),
            'washing_landings':len(WASHING_ROUTES),'excursions_completed':len(rooms_visited),
            'frames':len(frames),'walk_steps':steps,'median_render_readback_ms':float(np.median(timings)),
            'startup_seconds':startup,'triangles':scene.canals_manifest['total_triangles'],'buildings':scene.canals_manifest.get('building_count')}
    (OUT/'review-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
    assert preserved and not audio.opened
    assert swap_delta['mean']<1.5 and swap_delta['p99']<8 and swap_delta['peak']<8,swap_delta
    assert unlock_delta['mean']<1.5 and unlock_delta['p99']<8 and unlock_delta['peak']<8,unlock_delta
    assert reflection_delta['peak']<2 and reflection_raw_delta['peak']<2,(reflection_delta,reflection_raw_delta)
    assert blend_levels=={.15,.5,.85} and len(blend_checks)==3,blend_checks
    assert all(n>25 for label,n,shot in visibility),visibility

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
