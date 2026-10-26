"""Optics, continuity, real stairs/floors, sightlines and original-scene safety."""
import copy,hashlib,json,math,unittest,wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from g_huxin_moon import Explorer,DECK,inside_platform
from g_huxin_moon_sequence import (MoonSequence,UPPER,BASIN,MARK,SOLUTION,support,
    ENTRY_SWAP,ENTRY_CLEAR,ENTRY_DURATION,FOG_STOP_RADIUS,RETURN_SWAP,RETURN_CLEAR,
    causeway_progress,causeway_point)
from g_inventory import add,count
from test_huxin_moon import geometry,KIT
from test_santana_car import intersections

TOUR=((1.65,1.65),(2.9,1.7),(5.6,.1),(7.5,.1),(8.1,1.95),(10.5,1.95),
      (8.1,1.95),(7.6,.1),(5.6,.1),(2.9,1.7),(0,3.2),(-3.1,3.2),(-5.65,5.25),
      (-5.65,4.6),(-5.65,-4.95),(-3.4,-5.1),(-1,-3.7),(.8,-.8),(3.8,-.8),
      (3.8,-2.7),(4.5,-3.5),(3.8,-2.7),(3.8,-.8),(0,1),(0,5.3),(0,7.2),(4.8,7.2),
      (0,7.2),(0,5.2),(-3.6,2),(-3.6,-5.0),(-5.65,-5.0),(-5.65,4.8),(-5.65,5.35),(-3.1,3.2),(0,3.2),(0,7))
def tour():
    q=MoonSequence();q.revealed=True;q.state='revealed';e=Explorer();e.encounter=q;e.x,e.z=TOUR[0];e.height=DECK;samples=[];steps=0
    for x,z in TOUR[1:]:
        for _ in range(2000):
            dx,dz=x-e.x,z-e.z
            if math.hypot(dx,dz)<.09:break
            old=e.height;e.yaw=math.atan2(dx,-dz);dist=e.tick(.05,1);steps+=1
            assert dist>1e-5,('Blocked',x,z,e.x,e.height,e.z)
            assert abs(e.height-old)<.18,('Invalid stair step',old,e.height)
            if steps%5==0:samples.append((e.x,e.height,e.z))
        else:raise AssertionError('Route failed')
    return samples

def station(q,e,progress):
    """Place a test explorer at a measured station along the causeway."""
    e.x,e.z=causeway_point(progress);e.height=DECK;q.tick(.05,e)

def camera_values(cam):
    return np.array((cam.position.x,cam.position.y,cam.position.z,
                     cam.target.x,cam.target.y,cam.target.z,cam.fovy))

class EncounterTests(unittest.TestCase):
    def test_new_floors_do_not_overlap_the_original_pavilion_paving(self):
        for name in ('tea_ground','tea_foundation','tea_floors'):
            tri=geometry(name)[1];normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);center=tri.mean(axis=1)
            near=tri[(normal[:,1]>1e-7)&(center[:,1]>DECK-.04)&(center[:,1]<DECK+.04)]
            self.assertFalse(any(inside_platform(x,z,.001) for x,y,z in near.mean(axis=1)),name)

    def test_warm_lighting_is_continuous_at_both_architecture_swaps(self):
        for state in ('entering','leaving'):
            q=MoonSequence();q.state=state
            q.elapsed=ENTRY_SWAP-.001;q.return_progress=RETURN_SWAP-.0001;before=q.warmth
            q.elapsed=ENTRY_SWAP+.001;q.return_progress=RETURN_SWAP+.0001;after=q.warmth
            self.assertLess(abs(after-before),.01)
            q.revealed=False;a=q.warmth;q.revealed=True;self.assertEqual(a,q.warmth)

    def test_mirror_uses_reflected_ray_and_requires_a_settled_alignment(self):
        q=MoonSequence();e=Explorer();q.focus=True
        self.assertGreater(math.dist(q.hit(),MARK),.1)
        q.tick(5,e);self.assertEqual(q.state,'ordinary')
        for _ in range(18):q.adjust(.05,-1,0)
        for _ in range(11):q.adjust(.05,0,-1)
        self.assertLess(math.dist(q.hit(),MARK),.025)
        q.tick(.6,e);self.assertEqual(q.state,'ordinary')
        q.focus=False;q.tick(1,e);self.assertEqual(q.state,'ordinary')
        q.focus=True;q.tick(.6,e);self.assertEqual(q.state,'ordinary')
        q.tick(.6,e);self.assertEqual(q.state,'entering');self.assertEqual(q.events,['bell'])
        q.yaw,q.pitch=SOLUTION;self.assertLess(math.dist(q.hit(),MARK),1e-7)

    def test_both_swaps_are_hidden_and_keep_player_and_existing_inventory(self):
        e=Explorer();e.x,e.z=1.65,1.65;e.yaw=.8;q=MoonSequence();e.encounter=q
        self.assertTrue(add(q.inventory,{'kind':'key','count':1,'group':'encounter-proof'}))
        inventory=copy.deepcopy(q.inventory);player=(e.x,e.z,e.yaw,e.height)
        q.focus=True;q.yaw,q.pitch=SOLUTION;q.tick(1.2,e)
        for _ in range(math.ceil(ENTRY_DURATION/.1)+1):q.tick(.1,e)
        self.assertEqual(q.state,'revealed');self.assertTrue(q.revealed)
        self.assertEqual(player,(e.x,e.z,e.yaw,e.height));self.assertEqual(inventory,q.inventory)
        for progress in np.linspace(.97,0,100):
            station(q,e,progress)
            self.assertFalse(q.movement_locked)
            self.assertEqual(inventory,q.inventory)
        self.assertEqual(q.state,'returned');self.assertFalse(q.revealed)
        self.assertEqual([s for s,v in q.swaps],['entering','leaving'])
        self.assertTrue(all(abs(v-1)<1e-4 for s,v in q.swaps));self.assertEqual(q.bells,1)
        self.assertIsNotNone(support(e.x,e.z,DECK,False));self.assertEqual(count(q.inventory,'key'),1)
        q.focus=True;q.tick(10,e);self.assertEqual(q.state,'returned');self.assertEqual(q.bells,1)

    def test_approach_fog_builds_by_position_and_crescendo_stops_at_columns(self):
        from g_huxin_moon import shore_radius
        q=MoonSequence();e=Explorer();e.encounter=q;amounts=[];arrivals=[]
        for progress in np.linspace(0,1,101):
            station(q,e,progress);amounts.append(q.veil);arrivals.append(q.fog_arrival)
            self.assertFalse(q.movement_locked)
        self.assertAlmostEqual(amounts[0],0);self.assertGreater(amounts[-1],.65)
        self.assertLess(amounts[-1],1);self.assertGreater(arrivals[-1],.9)
        self.assertTrue(all(b>=a-1e-8 for a,b in zip(amounts,amounts[1:])))
        self.assertLess(max(np.diff(amounts)),.02)
        # Standing still at the mirror must not create another timed roll-in.
        before=(q.veil,q.fog_arrival)
        for _ in range(600):q.tick(.05,e)
        self.assertEqual(before,(q.veil,q.fog_arrival))
        q.focus=True;q.yaw,q.pitch=SOLUTION;q.tick(1.2,e)
        self.assertEqual(q.state,'entering');self.assertTrue(q.movement_locked)
        for a in np.linspace(-math.pi,math.pi,40):
            x,z=math.cos(a)*20,math.sin(a)*20
            ordinary=MoonSequence();station(ordinary,e,0)
            self.assertAlmostEqual(ordinary.fog_front(x,z),shore_radius(a)-6.)
            fronts=[]
            for t in np.linspace(0,ENTRY_SWAP,50):
                q.elapsed=t;fronts.append(q.fog_front(x,z))
            self.assertTrue(all(b<=a+1e-8 for a,b in zip(fronts,fronts[1:])))
            self.assertAlmostEqual(fronts[-1],FOG_STOP_RADIUS)
            q.elapsed=(ENTRY_CLEAR+ENTRY_DURATION)*.5
            self.assertAlmostEqual(q.fog_front(x,z),FOG_STOP_RADIUS)
            self.assertAlmostEqual(q.fog_clear,.5)

    def test_causeway_progress_measures_position_not_turning_or_time(self):
        q=MoonSequence();e=Explorer();e.encounter=q
        for p in np.linspace(0,1,101):
            x,z=causeway_point(p);self.assertAlmostEqual(causeway_progress(x,z),p,places=5)
        self.assertAlmostEqual(causeway_point(0)[1],76,places=3)
        self.assertAlmostEqual(causeway_point(1)[1],7,places=3)
        station(q,e,.45);before=(q.approach,q.veil,q.fog_arrival)
        for _ in range(200):e.tick(.05,0,1);q.tick(.05,e)
        self.assertEqual(before,(q.approach,q.veil,q.fog_arrival))
        station(q,e,.2);self.assertLess(q.veil,before[1])

    def test_return_fog_peaks_smoothly_at_halfway_and_clears_symmetrically(self):
        q=MoonSequence();q.state='leaving';values=[];arrivals=[]
        self.assertEqual(RETURN_SWAP,.5);self.assertEqual(RETURN_CLEAR,.5)
        for progress in np.linspace(0.,1.,1001):
            q.return_progress=progress;values.append(q.veil);arrivals.append(q.fog_arrival)
            self.assertEqual(q.camera_stage,'walking');self.assertFalse(q.movement_locked)
        self.assertEqual(values[0],0.);self.assertEqual(values[-1],0.)
        self.assertEqual(values[500],1.);self.assertEqual(arrivals[500],1.)
        self.assertTrue(np.allclose(values,values[::-1],atol=1e-12))
        self.assertTrue(all(b>=a for a,b in zip(values[:500],values[1:501])))
        self.assertTrue(all(b<=a for a,b in zip(values[500:],values[501:])))
        self.assertLess(max(abs(np.diff(values))),.004)
        self.assertLess(max(abs(np.diff(values,n=2))),.000025)
        # The front reaches the columns at the swap and stays there as the bank
        # thins, rather than reversing through the player on the way to shore.
        for progress in (.5,.6,.8,1.):
            q.return_progress=progress
            self.assertAlmostEqual(q.fog_front(20.,0.),FOG_STOP_RADIUS)
        self.assertLess(1.-values[499],1e-6);self.assertLess(1.-values[501],1e-6)

    def test_walk_and_run_keep_moving_through_midpoint_swap_and_clear_at_shore(self):
        durations=[];swapped_at=[]
        for run in (False,True):
            q=MoonSequence();q.state='revealed';q.revealed=True
            e=Explorer();e.encounter=q;station(q,e,1.);distance_after_swap=0.;elapsed=0.;swap_station=None
            for _ in range(1800):
                p=causeway_progress(e.x,e.z);x,z=causeway_point(max(0.,p-.012))
                e.yaw=math.atan2(x-e.x,-(z-e.z));previous=(e.x,e.z)
                self.assertFalse(q.movement_locked);e.tick(.05,1,0,run);q.tick(.05,e);elapsed+=.05
                distance=math.dist(previous,(e.x,e.z))
                self.assertGreater(distance,1e-5,('blocked',run,e.x,e.z,q.state))
                self.assertEqual(e.clip,'run' if run else 'walk')
                if q.state=='leaving':self.assertEqual(q.camera_stage,'walking')
                if not q.revealed:
                    distance_after_swap+=distance
                    if swap_station is None:swap_station=q.return_progress
                if q.state=='returned':break
            else:self.fail(('Return never finished',run,e.x,e.z,q.state))
            durations.append(elapsed);swapped_at.append(swap_station)
            self.assertGreater(distance_after_swap,30.)
            self.assertFalse(q.revealed);self.assertEqual(len(q.swaps),1)
            self.assertGreater(q.swaps[0][1],.99999)
            self.assertGreaterEqual(swap_station,.5);self.assertLess(swap_station,.504)
            self.assertAlmostEqual(q.veil,0.);self.assertAlmostEqual(q.fog_arrival,0.)
            self.assertLess(causeway_progress(e.x,e.z),.002)
        self.assertGreater(durations[0],durations[1]*1.8)
        self.assertLess(abs(swapped_at[0]-swapped_at[1]),.004)

    def test_return_stopping_backtracking_and_one_time_swap_are_safe(self):
        q=MoonSequence();q.state='revealed';q.revealed=True;e=Explorer();e.encounter=q
        station(q,e,.6);self.assertEqual(q.state,'leaving')
        before=(q.veil,q.fog_arrival,q.return_progress)
        for _ in range(1000):q.tick(.05,e)
        self.assertEqual(before,(q.veil,q.fog_arrival,q.return_progress))
        self.assertTrue(q.revealed);self.assertFalse(q.movement_locked)
        station(q,e,.5001);self.assertEqual(q.camera_stage,'walking');self.assertTrue(q.revealed)
        peak=q.veil
        station(q,e,.8);self.assertLess(q.veil,peak);self.assertEqual(q.camera_stage,'walking')
        station(q,e,1.);self.assertEqual(q.state,'revealed');self.assertTrue(q.revealed)
        self.assertEqual(q.swaps,[])
        station(q,e,1.-RETURN_SWAP-.0001);self.assertFalse(q.revealed)
        self.assertIsNotNone(support(e.x,e.z,e.height,False));self.assertEqual(len(q.swaps),1)
        at_peak=(q.veil,q.fog_arrival,q.return_progress)
        for _ in range(1000):q.tick(.05,e)
        self.assertEqual(at_peak,(q.veil,q.fog_arrival,q.return_progress));self.assertEqual(len(q.swaps),1)
        station(q,e,.8);self.assertFalse(q.revealed);self.assertFalse(q.movement_locked)
        station(q,e,1.);self.assertEqual(q.state,'returned');self.assertFalse(q.revealed)
        for p in np.linspace(1,0,80):station(q,e,p)
        self.assertEqual(len(q.swaps),1);self.assertEqual(q.veil,0.)

    def test_authored_cuts_are_clear_of_both_swap_instants(self):
        from huxin_moon_camera import mist_camera
        from huxin_moon_viewer import auto_camera
        q=MoonSequence();e=Explorer();e.x,e.z=1.65,1.65;e.height=DECK
        q.state='entering';q.elapsed=ENTRY_SWAP-.001;stage=q.camera_stage;_,a=mist_camera(q,e)
        q.elapsed=ENTRY_SWAP+.001;_,b=mist_camera(q,e)
        self.assertEqual(stage,q.camera_stage);self.assertLess(np.max(abs(camera_values(a)-camera_values(b))),.01)
        q=MoonSequence();q.state='revealed';q.revealed=True;e.encounter=q
        station(q,e,1.-RETURN_SWAP+.0001);e.tick(0.);stage=q.camera_stage;shot_a,a=auto_camera(e)
        station(q,e,1.-RETURN_SWAP-.0001);e.tick(0.);shot_b,b=auto_camera(e)
        self.assertEqual(stage,'walking');self.assertEqual(stage,q.camera_stage);self.assertEqual(shot_a,shot_b)
        self.assertLess(np.max(abs(camera_values(a)-camera_values(b))),.025)

    def test_viewer_uses_normal_auto_cameras_through_entire_return(self):
        from huxin_moon_viewer import Lake,auto_camera
        class CameraSelected(Exception):pass
        def stop_before_drawing(*args):raise CameraSelected
        q=MoonSequence();q.state='revealed';q.revealed=True;e=Explorer();e.encounter=q
        # Exercise render's actual selection branch, stopping before any GPU
        # work. A return-specific tracking shot must not silently reappear.
        lake=Lake.__new__(Lake);lake.sequence=q;lake.last_camera=None;lake.last_shot=0
        lake.player=SimpleNamespace(clips={'idle','walk'},pose=lambda *args:None)
        lake.frame=None
        lake._render_world=stop_before_drawing
        for progress in np.linspace(.97,.002,100):
            station(q,e,progress);e.tick(0.)
            expected_shot,expected=auto_camera(e)
            self.assertEqual(q.camera_stage,'walking')
            with self.assertRaises(CameraSelected):lake.render(e,40.)
            self.assertEqual(lake.last_shot,expected_shot)
            self.assertTrue(np.allclose(camera_values(lake.last_camera),camera_values(expected)))

    def test_basin_doors_rails_and_stacked_surfaces(self):
        self.assertIsNone(support(0,0,DECK,False));self.assertIsNone(support(0,0,DECK,True))
        self.assertEqual(support(0,6.1,DECK,True),DECK)
        self.assertEqual(support(6.9,0,DECK,True),DECK)
        self.assertEqual(support(3.8,-1.9,UPPER,True),UPPER)
        self.assertIsNone(support(-4.5,0,UPPER,True));self.assertIsNone(support(0,8.2,UPPER,True))
        self.assertEqual(support(2,2,DECK,True),DECK);self.assertEqual(support(2,2,UPPER,True),UPPER)
        self.assertIsNone(support(-5.6,-4,DECK,True))

    def test_tour_has_real_exported_floors_and_stair_treads(self):
        tri=np.concatenate([geometry(n)[1] for n in ('pavilion_base','tea_ground','tea_floors','tea_stairs','causeway')])
        low,high=tri.min(axis=1),tri.max(axis=1);heights=[]
        for x,y,z in tour():
            near=tri[(low[:,0]<=x)&(high[:,0]>=x)&(low[:,2]<=z)&(high[:,2]>=z)]
            hits=intersections(near,np.array((x,y+.23,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertTrue(any(abs(hits-.23)<.04),(x,y,z,hits));heights.append(y)
        self.assertGreater(len(set(heights)),20);self.assertEqual(max(heights),UPPER);self.assertEqual(heights[-1],DECK)

    def test_interior_cameras_see_the_player_through_actual_geometry(self):
        from huxin_moon_camera import interior_camera
        names=('tea_frame','tea_walls','tea_lattice','tea_floors','tea_stairs','tea_roofs','tea_ceiling','tea_furniture')
        old=np.concatenate([geometry(n)[1] for n in ('pavilion_posts','pavilion_details')]);old=old[old[:,:,1].max(axis=1)<DECK+3.55]
        tri=np.concatenate([geometry(n)[1] for n in names]+[old,geometry('moon_basin')[1]]);low,high=tri.min(axis=1),tri.max(axis=1);fail=[];e=Explorer()
        samples=tour()+[(x,y,z) for y in (DECK,UPPER) for x in np.arange(-6.3,11.9,.75) for z in np.arange(-5.3,8.1,.75)
                        if (h:=support(x,z,y,True)) is not None and abs(h-y)<.1]
        for x,y,z in samples:
            e.x,e.height,e.z=x,y,z;i,cam=interior_camera(e)
            eye=np.array((cam.position.x,cam.position.y,cam.position.z));body=np.array((x,y+.92,z));delta=body-eye;length=np.linalg.norm(delta)
            near=tri[np.all(high>=np.minimum(eye,body),axis=1)&np.all(low<=np.maximum(eye,body),axis=1)]
            hits=intersections(near,eye,delta/length,tolerance=1e-5)
            if any((hits>.1)&(hits<length-.12)):fail.append((i,tuple(round(v,2) for v in (x,y,z))))
        self.assertEqual(fail,[])

    def test_expansion_assets_are_portable_and_original_scene_is_untouched(self):
        info=json.loads((KIT/'teahouse_manifest.json').read_text())
        for name in info['models']:
            doc,tri=geometry(name);self.assertTrue(np.isfinite(tri).all())
            self.assertTrue(all('bufferView' in image for image in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123)
        original=json.loads((KIT/'origin_snapshot.json').read_text())['original_sha256'];root=Path(__file__).parent
        for name,expected in original.items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected,name)

    def test_audio_is_one_strike_without_clipping_and_review_opens_no_device(self):
        from huxin_moon_audio import EncounterAudio
        audio=EncounterAudio(automated=True)
        try:
            self.assertTrue(audio.muted);self.assertFalse(audio.opened)
            q=MoonSequence();q.events=['bell'];audio.drain(q);audio.drain(q);self.assertEqual(audio.played,['bell'])
        finally:audio.close()
        with wave.open(str(KIT/'bell.wav')) as sound:
            self.assertEqual(sound.getnchannels(),1);samples=np.frombuffer(sound.readframes(sound.getnframes()),dtype='<i2')/32768
        self.assertLess(abs(samples).max(),.9);self.assertGreater(abs(samples).max(),.5)
        self.assertLess(np.sqrt(np.mean(samples[-44100:]**2)),.004)

if __name__=='__main__':unittest.main()
