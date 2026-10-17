"""Muted native review: spatial accumulation, a quiet crescendo and a moving return."""
from pathlib import Path
import argparse,json,math,time
import numpy as np
import pyray as pr
from PIL import Image,ImageDraw
from huxin_moon_viewer import Lake,WIDTH,HEIGHT,auto_camera
from g_huxin_moon import Explorer,DECK,PATH
from g_huxin_moon_sequence import MoonSequence,SOLUTION,ENTRY_SWAP,ENTRY_DURATION,causeway_point,RETURN_SWAP
from temple_interior_viewer import snapshot,camera


def pixels(scene,target=None):
    im=pr.load_image_from_texture((scene.frame if target is None else target).texture);pr.image_flip_vertical(im)
    result=np.frombuffer(bytes(pr.ffi.buffer(im.data,WIDTH*HEIGHT*4)),dtype=np.uint8).reshape(HEIGHT,WIDTH,4)[:,:,:3].copy()
    pr.unload_image(im);return result


def walk_out(e,q,dt,run=False):
    if q.movement_locked:return
    target=next((p for p in reversed(PATH) if p[1]>e.z+1.),PATH[0])
    e.yaw=math.atan2(target[0]-e.x,e.z-target[1]);return e.tick(dt,1,0,run)


def review(quick=False):
    out=Path(__file__).parent/'artifacts'/'huxin_moon';out.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(WIDTH,HEIGHT,'Moon subtle mist review');scene=None
    try:
        scene=Lake();e=Explorer();e.height=DECK;e.encounter=scene.sequence;q=scene.sequence
        cards=[];render_ms=[];visible_pixels=[]
        def capture(label,clock):
            start=time.perf_counter();scene.render(e,clock);im=pixels(scene);render_ms.append((time.perf_counter()-start)*1000)
            cards.append((label,im));Image.fromarray(im).save(out/(label+'.png'))
            if q.state in ('ordinary','leaving','returned'):
                scene.render(e,clock,show_player=False);without=pixels(scene)
                visible_pixels.append((label,int((np.max(np.abs(im.astype(float)-without.astype(float)),axis=2)>2).sum())))
            return im
        for p in (0,.2,.4,.6,.8,1.):
            e.x,e.z=causeway_point(p);e.tick(0);q.tick(0,e);e.phase=p*35
            if p==1.:e.x,e.z=1.65,1.65;q.focus=True;e.clip='idle'
            capture('subtle-approach-%03d'%round(p*100),40+p*48)
        # The puzzle adds only the last part of an already accumulated bank.
        q.focus=False;q.yaw,q.pitch=SOLUTION;q.state='entering'
        for t in (0,4,8,12,16,20,24):
            q.elapsed=t;q.revealed=t>=ENTRY_SWAP;capture('subtle-crescendo-%03d'%round(t),88+t)
        q.elapsed=ENTRY_SWAP;q.revealed=False;scene.render(e,96);before=pixels(scene)
        q.revealed=True;scene.render(e,96);after=pixels(scene)
        delta=np.abs(before.astype(float)-after.astype(float));report={
            'entry_crescendo_seconds':ENTRY_DURATION,'swap_mean_rgb_delta':float(delta.mean()),'swap_p99_rgb_delta':float(np.percentile(delta,99)),
            # Whole-frame averages miss small, conspicuous reveals such as a
            # lantern cage popping into the top edge. Check the worst pixel too.
            'swap_max_rgb_delta':float(delta.max()),
            'peak_luminance_std':float(after.mean(axis=2).std()),'peak_mean_rgb':after.mean(axis=(0,1)).tolist(),'audio_device_opened':False}
        Image.fromarray(np.minimum(255,delta*8).astype('uint8')).save(out/'subtle-swap-difference-x8.png')
        # Continuity at 60 Hz, with a fixed camera isolating only the volume.
        q.state='ordinary';q.focus=False;q.revealed=False;e.x,e.z=causeway_point(.65);e.tick(0)
        fixed=camera((15,9,30),(0,3,0),62);q.approach=.65;scene.render(e,70,override=fixed);a=pixels(scene)
        q.approach=.65+(3.15/70)/60;scene.render(e,70+1/60,override=fixed);b=pixels(scene)
        report['fog_only_frame_mean_rgb_delta']=float(np.abs(a.astype(float)-b.astype(float)).mean())
        q=MoonSequence();scene.sequence=q;e.encounter=q;q.state='revealed';q.revealed=True;e.x,e.z=causeway_point(1.);e.yaw=math.pi
        exit_frames=[];last_stage=None;stages=[];next_card=0.;walk_distance=0.;exit_swapped=False;normal_stations=0
        for i in range(1500):
            t=i*.05;old=(e.x,e.z);walk_out(e,q,.05);q.tick(.05,e)
            walk_distance+=math.dist(old,(e.x,e.z))
            if q.camera_stage!=last_stage:stages.append((q.camera_stage,round(q.return_progress,3)));last_stage=q.camera_stage
            if q.state=='leaving':
                assert q.camera_stage=='walking' and not q.movement_locked
                normal_stations+=1
            if q.return_progress>=next_card or (len(q.swaps)>0 and not exit_swapped):
                capture('subtle-return-%03d'%round(q.return_progress*100),130+t)
                while q.return_progress>=next_card:next_card+=.10
            if len(q.swaps)>0 and not exit_swapped:
                # Same frame and normal gameplay camera, architecture only.
                q.revealed=True;scene.render(e,130+t);a=pixels(scene)
                reflection_a=pixels(scene,scene.reflection);raw_a=pixels(scene,scene.reflection_raw)
                q.revealed=False;scene.render(e,130+t);b=pixels(scene)
                reflection_b=pixels(scene,scene.reflection);raw_b=pixels(scene,scene.reflection_raw)
                delta=np.abs(a.astype(float)-b.astype(float))
                reflected_delta=np.abs(reflection_a.astype(float)-reflection_b.astype(float))
                raw_delta=np.abs(raw_a.astype(float)-raw_b.astype(float))
                report.update(return_swap_progress=q.return_progress,return_swap_mean_rgb_delta=float(delta.mean()),
                              return_swap_p99_rgb_delta=float(np.percentile(delta,99)),return_swap_max_rgb_delta=float(delta.max()),
                              reflection_swap_mean_rgb_delta=float(reflected_delta.mean()),reflection_swap_max_rgb_delta=float(reflected_delta.max()),
                              reflection_raw_swap_max_rgb_delta=float(raw_delta.max()))
                Image.fromarray(a).save(out/'subtle-return-midpoint-before.png')
                Image.fromarray(b).save(out/'subtle-return-midpoint-after.png')
                Image.fromarray(np.minimum(255,delta*8).astype('uint8')).save(out/'subtle-return-difference-x8.png')
                Image.fromarray(reflection_a).save(out/'subtle-return-reflection-before.png')
                Image.fromarray(reflection_b).save(out/'subtle-return-reflection-after.png')
                Image.fromarray(raw_a).save(out/'subtle-return-reflection-without-volume.png')
                Image.fromarray(np.minimum(255,reflected_delta*8).astype('uint8')).save(out/'subtle-return-reflection-difference-x8.png')
                # Pausing or taking longer to explore changes the cloud phase.
                # Each must conceal the same swap, including its water image.
                phases=[]
                for phase in (0.,50.,300.,600.):
                    q.revealed=True;scene.render(e,phase);a=pixels(scene)
                    q.revealed=False;scene.render(e,phase);b=pixels(scene)
                    phases.append((phase,float(np.abs(a.astype(float)-b.astype(float)).max())))
                report['return_swap_phase_max_rgb_delta']=phases
                exit_swapped=True
            if not quick and i%4==0:
                scene.render(e,130+t);exit_frames.append(Image.fromarray(pixels(scene)))
            if q.state=='returned':break
        assert q.state=='returned'
        report.update(return_seconds=round(t,2),return_walk_distance=walk_distance,normal_camera_stations=normal_stations,
                      return_camera_stages=stages,shore_fog=q.veil,median_capture_ms=float(np.median(render_ms)),player_visible_pixels=visible_pixels)
        sheet=Image.new('RGB',(WIDTH*2,(HEIGHT+24)*math.ceil(len(cards)/2)));draw=ImageDraw.Draw(sheet)
        for i,(label,im) in enumerate(cards):
            x=i%2*WIDTH;y=i//2*(HEIGHT+24);sheet.paste(Image.fromarray(im),(x,y));draw.text((x+8,y+HEIGHT+5),label,fill=(210,215,203))
        sheet.save(out/'subtle-mist-progression.png');(out/'mist-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
        if not quick:
            q=MoonSequence();scene.sequence=q;e.encounter=q;animation=[]
            for t in np.linspace(0,48,241):
                p=float(t)/48;e.x,e.z=causeway_point(p)
                ahead=causeway_point(min(.99999,p+.001));behind=causeway_point(max(0.,p-.001))
                e.yaw=math.atan2(ahead[0]-behind[0],behind[1]-ahead[1]);e.tick(0);e.phase=p*35;e.clip='walk';q.tick(0,e)
                scene.render(e,40+t);animation.append(Image.fromarray(pixels(scene)))
            clock=88.;steps=0
            for x,z in ((0,3.3),(1.65,1.65)):
                for _ in range(500):
                    if math.hypot(x-e.x,z-e.z)<.08:break
                    e.yaw=math.atan2(x-e.x,e.z-z);e.tick(.05,1);q.tick(.05,e);clock+=.05;steps+=1
                    if steps%4==0:scene.render(e,clock);animation.append(Image.fromarray(pixels(scene)))
                else:raise AssertionError('Preview approach is blocked')
            e.clip='idle';q.yaw,q.pitch=SOLUTION;q.focus=True
            for _ in range(8):
                q.tick(.2,e);clock+=.2;scene.render(e,clock);animation.append(Image.fromarray(pixels(scene)))
            q.state='entering';q.focus=False
            for t in np.linspace(0,ENTRY_DURATION,121):
                q.elapsed=float(t);q.revealed=t>=ENTRY_SWAP;scene.render(e,clock+t);animation.append(Image.fromarray(pixels(scene)))
            animation[0].save(out/'mist-roll-in.gif',save_all=True,append_images=animation[1:],duration=200,loop=0,optimize=True)
            exit_frames[0].save(out/'mist-causeway-return.gif',save_all=True,append_images=exit_frames[1:],duration=200,loop=0,optimize=True)
        assert report['swap_mean_rgb_delta']<1.5 and report['swap_p99_rgb_delta']<8,report
        assert report['swap_max_rgb_delta']<8,report
        assert report['return_swap_mean_rgb_delta']<1.5 and report['return_swap_p99_rgb_delta']<8,report
        assert report['return_swap_max_rgb_delta']<8,report
        assert all(peak<8 for phase,peak in report['return_swap_phase_max_rgb_delta']),report
        # At the waterline the reflected ray has almost no distance to travel;
        # the final pass supplies that pixel's camera-to-water fog. Check the
        # two-segment result above, and substantial attenuation in the reflected
        # segment separately rather than demanding double fog at the waterline.
        assert report['reflection_swap_max_rgb_delta']<report['reflection_raw_swap_max_rgb_delta']*.2,report
        assert report['reflection_swap_mean_rgb_delta']<.1,report
        assert report['reflection_raw_swap_max_rgb_delta']>20,report # The test really sees the changed reflected building.
        assert RETURN_SWAP<=report['return_swap_progress']<RETURN_SWAP+.005,report
        assert report['fog_only_frame_mean_rgb_delta']<.3,report
        assert report['return_walk_distance']>65 and report['shore_fog']==0,report
        assert all(n>=30 for label,n in visible_pixels),visible_pixels
    finally:
        if scene:scene.close()
        pr.close_window()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--quick',action='store_true');review(parser.parse_args().quick)
