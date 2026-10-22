"""Void canals: real movement, exported architecture, one-way entry and isolation."""
import copy
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from g_inventory import add
from g_huxin_canals import Explorer, DECK
from g_huxin_canals_sequence import (CanalSequence, DISC_ITEM, ENTRY_SWAP,
    ENTRY_DURATION, FOG_ARRIVAL_DURATION, WORLD_BLEND_START, WORLD_BLEND_END,
    FOG_CLEAR_START, FOG_CLEAR_DURATION, SEQUENCE_DURATION, causeway_point)
from g_huxin_moon_sequence import MoonSequence
from test_temple_living import accessor
from test_santana_car import intersections

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'art' / 'temple' / 'huxin_canals'


@lru_cache(maxsize=None)
def geometry(name):
    raw = (KIT / (name + '.glb')).read_bytes()
    magic, version, size = struct.unpack_from('<III', raw)
    assert (magic, version, size) == (0x46546c67, 2, len(raw))
    length, kind = struct.unpack_from('<II', raw, 12)
    assert kind == 0x4e4f534a
    doc = json.loads(raw[20:20 + length])
    offset = 20 + length
    count, kind = struct.unpack_from('<II', raw, offset)
    assert kind == 0x004e4942
    binary = raw[offset + 8:offset + 8 + count]
    points = []
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            xyz = accessor(doc, binary, primitive['attributes']['POSITION'])
            indices = accessor(doc, binary, primitive['indices']).reshape(-1)
            points.append(xyz[indices].reshape(-1, 3, 3))
    return doc, np.concatenate(points)


class TriangleIndex:
    """Exact coarse AABBs keep dense exported-mesh ray tests proportional.

    Buckets contain complete triangles, including those crossing a cell edge;
    their bounds come from vertices, so no intersection can be discarded.
    """
    def __init__(self,triangles):
        low,high=triangles.min(axis=1),triangles.max(axis=1)
        cells=np.floor((low[:,(0,2)]+high[:,(0,2)])/8).astype(np.int64)
        keys=cells[:,0]*10000+cells[:,1];order=np.argsort(keys)
        cuts=np.flatnonzero(np.diff(keys[order]))+1
        self.parts=[];bounds=[]
        for indices in np.split(order,cuts):
            self.parts.append((triangles[indices],low[indices],high[indices]))
            bounds.append((low[indices].min(axis=0),high[indices].max(axis=0)))
        self.low=np.array([b[0] for b in bounds]);self.high=np.array([b[1] for b in bounds])

    def query(self,a,b,margin=.001):
        low=np.minimum(a,b)-margin;high=np.maximum(a,b)+margin
        ids=np.flatnonzero(np.all(self.high>=low,axis=1)&np.all(self.low<=high,axis=1))
        matches=[]
        for i in ids:
            triangles,lo,hi=self.parts[i]
            matches.append(triangles[np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1)])
        return np.concatenate(matches) if matches else np.empty((0,3,3),dtype=np.float32)


def front_intersections(triangles,origin,direction,tolerance=1e-6):
    """Raylib culls back faces, so an inward backing cannot close a hole."""
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    return intersections(triangles[normals@direction < -1e-9],origin,direction,tolerance)


@lru_cache(maxsize=1)
def path_cache():
    """Optional on-disk trajectories for repeated mesh-only rebuild checks.

    Actual controller/navigation/test sources and exported accessible portals
    are fingerprinted; any relevant change forces real controls to run again.
    Normal test invocations remain uncached unless the runner opts in.
    """
    destination=os.environ.get('HAUNTED_TEST_PATH_CACHE')
    if not destination:return None,None
    digest=hashlib.sha256()
    for name in ('test_huxin_canals.py','g_huxin_canals.py','g_huxin_canals_layout.py',
                 'g_huxin_canals_sequence.py','canals_house_plan.py','g_inventory.py',
                 'g_interaction_data.py','photo_asset_pipeline/temple3d/living/gait.py'):
        digest.update((ROOT/name).read_bytes())
    houses=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))['houses']
    portals=[(h['seed'],h.get('door_portals',())) for h in houses if h.get('enterable')]
    digest.update(json.dumps(portals,sort_keys=True).encode())
    digest.update((str(tuple(os.sys.version_info))+np.__version__).encode())
    path=Path(destination);key=digest.hexdigest()
    if path.exists():
        record=json.loads(path.read_text(encoding='utf-8'))
        if record.get('fingerprint')==key:return path,record
    return path,dict(fingerprint=key,paths={})


def cached_path(key,value=None):
    path,record=path_cache()
    if path is None:return None
    key=json.dumps(key)
    if value is None:return record['paths'].get(key)
    record['paths'][key]=value;path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record),encoding='utf-8',newline='\n')
    temporary.replace(path)


def at_basin():
    q = CanalSequence()
    e = Explorer()
    e.encounter = q
    e.x, e.z, e.height = 1.65, 1.65, DECK
    q.tick(.01, e)
    return q, e


def camera_signature(cam):
    return tuple(getattr(vector, axis) for vector in (cam.position, cam.target, cam.up)
                 for axis in ('x', 'y', 'z')) + (cam.fovy, cam.projection)


def enter(q, e):
    assert q.activate(e)
    for _ in range(int(ENTRY_DURATION / .05) + 2):
        q.tick(.05, e)
    assert q.state == 'canals'


@lru_cache(maxsize=1)
def entered_template():
    """One real entry, reused as independent completed-state navigation fixtures."""
    q,e=at_basin();enter(q,e)
    return q,e


def navigation_fixture():
    return copy.deepcopy(entered_template())


@lru_cache(maxsize=None)
def walk_tour(reverse=False, run=False, room=None, washing=None):
    """Exercise the real tank controller over the entire interconnected route."""
    from g_huxin_canals_layout import REVIEW_ROUTE, ROOM_ROUTES, WASHING_ROUTES
    key=('walk_tour',reverse,run,room,washing);stored=cached_path(key)
    if stored is not None:return [tuple(p) for p in stored]
    points = WASHING_ROUTES[washing] if washing is not None else REVIEW_ROUTE if room is None else ROOM_ROUTES[room]
    route = points[::-1] if reverse else points
    q, e = navigation_fixture()
    e.x, e.z = route[0]
    e.height = DECK
    result = [(e.x, e.height, e.z)]
    steps = 0
    for x, z in route[1:]:
        for _ in range(2400):
            dx, dz = x - e.x, z - e.z
            if math.hypot(dx, dz) < .075:
                break
            e.yaw = math.atan2(dx, -dz)
            old = e.height
            distance = e.tick(.025 if run else .04, 1., 0., run)
            q.tick(.025 if run else .04, e)
            steps += 1
            assert distance > 1e-6, ('Blocked route', reverse, run, (x, z), (e.x, e.height, e.z))
            assert abs(e.height - old) < .235, ('Abrupt riser', old, e.height)
            assert q.world == 'canals' and q.state == 'canals'
            if steps % 5 == 0:
                result.append((e.x, e.height, e.z))
        else:
            raise AssertionError(('Unreachable route', reverse, run, (x, z), (e.x, e.height, e.z)))
    result.append((e.x, e.height, e.z))
    cached_path(key,result)
    return result


@lru_cache(maxsize=1)
def door_tours():
    """Natural straight approaches to every advertised accessible ground bay.

    These paths come from exported mesh apertures, not the hand-picked room
    demonstration route. Lateral offsets catch the former central-only collider.
    """
    from g_huxin_canals_layout import support
    stored=cached_path(('door_tours',))
    if stored is not None:return stored
    manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
    tours=[]
    for house in manifest['houses']:
        if not house.get('enterable'):continue
        assert house.get('door_portals'),('Missing accessible doors',house['seed'])
        for bay,portal in enumerate(house['door_portals']):
            if not portal.get('accessible'):continue
            normal=np.asarray(portal['normal'],float)
            tangent=np.asarray(portal['tangent'],float);tangent/=np.linalg.norm(tangent)
            offset=min(.25,portal['clear_width']/2-.28)
            assert offset>0,('Door too narrow for player',house['seed'],bay)
            for side in (-offset,0.,offset):
                start=np.asarray(portal['approach'],float)+tangent*side
                finish=np.asarray(portal['inside'],float)+tangent*side
                for run in (False,True):
                    q,e=navigation_fixture()
                    e.x,e.height,e.z=map(float,start)
                    assert support(e.x,e.z,e.height) is not None,('No doorway approach',house['seed'],bay,side,start)
                    samples=[(e.x,e.height,e.z)]
                    for goal in (finish,start):
                        for _ in range(1000):
                            dx,dz=goal[0]-e.x,goal[2]-e.z
                            if math.hypot(dx,dz)<.055:break
                            e.yaw=math.atan2(dx,-dz)
                            distance=e.tick(.02,1.,0.,run)
                            assert distance>1e-6,('Natural doorway blocked',house['seed'],bay,side,run,(e.x,e.height,e.z),goal)
                            samples.append((e.x,e.height,e.z))
                        else:raise AssertionError(('Doorway timed out',house['seed'],bay))
                    tours.append(dict(seed=house['seed'],bay=bay,offset=side,run=run,
                                      portal=portal,samples=samples))
    assert len({t['seed'] for t in tours})>=4,'Several houses must be genuinely accessible'
    cached_path(('door_tours',),tours)
    return tours


class CanalSequenceTests(unittest.TestCase):
    def test_incoming_fog_keeps_activation_opacity_and_is_thick_before_handoff(self):
        q,e=at_basin();opacity=q.veil;arrival=q.fog_arrival
        self.assertEqual(FOG_ARRIVAL_DURATION,5.)
        self.assertEqual(FOG_ARRIVAL_DURATION,WORLD_BLEND_START)
        self.assertEqual(WORLD_BLEND_END-WORLD_BLEND_START,1.)
        self.assertEqual(ENTRY_SWAP,WORLD_BLEND_END)
        self.assertEqual(ENTRY_DURATION,WORLD_BLEND_END)
        self.assertEqual(FOG_CLEAR_START,ENTRY_DURATION)
        self.assertTrue(q.activate(e))
        self.assertEqual(q.veil,opacity);self.assertEqual(q.fog_arrival,arrival)
        self.assertEqual(q.fog_depth,0.)
        self.assertTrue(q.movement_locked)
        depths=[];blends=[]
        for _ in range(math.ceil((ENTRY_DURATION+.1)*60)):
            q.tick(1/60,e)
            self.assertAlmostEqual(q.veil,opacity,places=10)
            self.assertEqual(q.fog_source_arrival,arrival)
            depths.append(q.fog_depth);blends.append(q.world_blend)
            if q.elapsed<=FOG_CLEAR_START:self.assertEqual(q.fog_clear,0.)
            else:
                self.assertEqual(q.world_blend,1.)
                self.assertFalse(q.movement_locked)
            if q.elapsed<WORLD_BLEND_START:self.assertEqual(q.world_blend,0.)
            if q.world_blend>0.:
                self.assertEqual(q.fog_depth,1.);self.assertEqual(q.fog_arrival,1.)
            if q.elapsed<ENTRY_DURATION:self.assertTrue(q.movement_locked)
        self.assertEqual(q.state,'canals');self.assertFalse(q.movement_locked)
        self.assertEqual(q.world_blend,1.)
        self.assertEqual(q.void_tone,q.fog_clear)
        self.assertLess(q.fog_clear,.001,'The first unlocked frames must join the crest gently')
        self.assertEqual(depths[-1],1.)
        self.assertEqual(q.fog_arrival,1.)
        self.assertGreaterEqual(q.elapsed,ENTRY_DURATION)
        self.assertTrue(all(b>=a for a,b in zip(depths,depths[1:])))
        self.assertTrue(all(b>=a for a,b in zip(blends,blends[1:])))
        self.assertGreater(sum(0.<b<1. for b in blends),50,
                           'The hidden world must dissolve, not switch on a single frame')

    def test_stationary_player_sees_clearing_after_smooth_handoff(self):
        q,e=at_basin();self.assertTrue(q.activate(e));q.tick(ENTRY_DURATION,e)
        pose=(e.x,e.height,e.z,e.yaw);self.assertEqual(q.fog_clear,0.)
        self.assertFalse(q.movement_locked);self.assertEqual(FOG_CLEAR_DURATION,40.)
        self.assertEqual(SEQUENCE_DURATION,46.)
        q.tick(FOG_CLEAR_START-q.elapsed,e);self.assertEqual(q.fog_clear,0.)
        samples=[]
        for _ in range(int(FOG_CLEAR_DURATION*30)):
            q.tick(1/30,e);samples.append(q.fog_clear)
            self.assertFalse(q.movement_locked)
            self.assertEqual(q.world_blend,1.);self.assertEqual(q.void_tone,q.fog_clear)
        self.assertEqual((e.x,e.height,e.z,e.yaw),pose)
        self.assertTrue(all(b>=a for a,b in zip(samples,samples[1:])))
        self.assertGreater(samples[6*30-1],.25)
        self.assertLess(samples[6*30-1],.35)
        quarter=samples[int(FOG_CLEAR_DURATION*30*.25)-1]
        half=samples[len(samples)//2-1]
        self.assertGreater(quarter,.4);self.assertLess(quarter,.6)
        self.assertGreater(half,.7);self.assertLess(half,.9)
        self.assertAlmostEqual(q.fog_clear,1.,places=9)
        q.tick(120.,e);self.assertEqual(q.elapsed,SEQUENCE_DURATION)
        self.assertEqual(q.fog_clear,1.);self.assertEqual(q.state,'canals')

    def test_hidden_world_blend_eases_at_both_ends_at_playback_rate(self):
        q,e=at_basin();self.assertTrue(q.activate(e))
        for fps in (30,60):
            dt=1/fps
            for boundary in (WORLD_BLEND_START,WORLD_BLEND_END):
                samples=[]
                for offset in (-2,-1,0,1,2):
                    q.elapsed=boundary+offset*dt;samples.append(q.world_blend)
                changes=[b-a for a,b in zip(samples,samples[1:])]
                self.assertTrue(all(change>=0. for change in changes))
                self.assertLess(max(changes),.003,'No one-frame handoff at a blend boundary')
            q.elapsed=(WORLD_BLEND_START+WORLD_BLEND_END)/2
            self.assertAlmostEqual(q.world_blend,.5)

    def test_global_clearing_has_zero_slope_at_both_endpoints(self):
        q,e=at_basin();self.assertTrue(q.activate(e));q.tick(ENTRY_DURATION,e)
        h=.001
        q.elapsed=FOG_CLEAR_START-h;self.assertEqual(q.fog_clear,0.)
        q.elapsed=FOG_CLEAR_START+h;opening_slope=q.fog_clear/h
        q.elapsed=SEQUENCE_DURATION-h;closing_slope=(1.-q.fog_clear)/h
        q.elapsed=SEQUENCE_DURATION+h;self.assertEqual(q.fog_clear,1.)
        self.assertGreaterEqual(opening_slope,0.);self.assertLess(opening_slope,.001)
        self.assertGreaterEqual(closing_slope,0.);self.assertLess(closing_slope,.001)

    def test_actual_walk_run_and_idle_have_identical_fog_at_equal_clocks(self):
        fixtures=[];points=((1.2,3.),(0.,5.8),(0.,7.),(-1.84,12.),(-2.,16.))
        for mode in ('idle','walk','run'):
            q,e=at_basin();enter(q,e);fixtures.append([q,e,mode,0,0.])
        for _ in range(20*30):
            values=[]
            for fixture in fixtures:
                q,e,mode,index,_=fixture
                self.assertFalse(q.movement_locked)
                if mode!='idle' and index<len(points):
                    x,z=points[index]
                    dx,dz=x-e.x,z-e.z;distance=math.hypot(dx,dz)
                    if distance<.12:fixture[3]+=1
                    else:
                        e.yaw=math.atan2(dx,-dz);travel=e.tick(1/30,1.,run=mode=='run')
                        self.assertGreater(travel,1e-6,('Blocked reveal route',mode,x,z,e.x,e.z))
                        fixture[4]+=travel
                q.tick(1/30,e)
                values.append((q.world_blend,q.fog_clear,q.void_tone,q.fog_arrival,q.fog_depth,q.veil))
            self.assertEqual(values[0],values[1]);self.assertEqual(values[0],values[2])
        self.assertEqual(fixtures[0][4],0.)
        self.assertGreater(fixtures[1][4],10.);self.assertGreater(fixtures[2][4],10.)
        self.assertGreater(fixtures[0][0].fog_clear,0.)

    def test_different_locations_and_heights_do_not_change_global_fog_timing(self):
        fixtures=[at_basin() for _ in range(4)]
        for q,e in fixtures:self.assertTrue(q.activate(e))
        positions=((1.65,DECK,1.65),(0.,DECK,24.),(-7.,DECK,16.),(5.,DECK+3.8,7.))
        for elapsed in (3.,FOG_ARRIVAL_DURATION,(WORLD_BLEND_START+WORLD_BLEND_END)/2,
                        ENTRY_DURATION,FOG_CLEAR_START,FOG_CLEAR_START+FOG_CLEAR_DURATION/2,SEQUENCE_DURATION):
            values=[]
            for (q,e),position in zip(fixtures,positions):
                e.x,e.height,e.z=position;q.tick(elapsed-q.elapsed,e)
                values.append((q.world_blend,q.fog_clear,q.void_tone,q.fog_arrival,q.fog_depth,q.veil))
            self.assertTrue(all(v==values[0] for v in values))

    def test_dt_partition_does_not_change_handoff_or_clearing(self):
        for total in (5.,FOG_ARRIVAL_DURATION,(WORLD_BLEND_START+WORLD_BLEND_END)/2,
                      ENTRY_DURATION,FOG_CLEAR_START,FOG_CLEAR_START+FOG_CLEAR_DURATION/2,SEQUENCE_DURATION,120.):
            states=[]
            for step in (1/60,.2,7.3,total):
                q,e=at_basin();self.assertTrue(q.activate(e));remaining=total
                while remaining>1e-9:
                    dt=min(step,remaining);q.tick(dt,e);remaining-=dt
                states.append((q.state,q.revealed,q.movement_locked,len(q.swaps),q.elapsed,
                               q.world_blend,q.fog_clear,q.void_tone,q.fog_depth,q.fog_arrival))
            for state in states[1:]:
                self.assertEqual(state[:4],states[0][:4],(total,state,states[0]))
                self.assertTrue(np.allclose(state[4:],states[0][4:],atol=1e-9,rtol=0.),(total,state,states[0]))

    def test_actual_renderer_keeps_the_preinteraction_camera_until_player_moves(self):
        from huxin_canals_viewer import Lake
        class CameraSelected(Exception):
            pass
        def stop_before_drawing(*args):
            raise CameraSelected
        q, e = at_basin()
        lake = Lake.__new__(Lake)
        lake.sequence = q
        lake.last_camera = None
        lake.last_shot = 0
        lake.last_pose = None
        lake.player = SimpleNamespace(clips={'idle', 'walk'}, pose=lambda *args: None)
        lake.frame = object()
        lake.blend_old_frame = object()
        lake.blend_new_frame = object()
        # Stop at the endpoint renderer, after real camera/transition selection
        # but before either world's GPU calls or the frame compositor.
        lake._render_world = stop_before_drawing
        with self.assertRaises(CameraSelected):
            lake.render(e, 30.)
        before = camera_signature(lake.last_camera)
        shot = lake.last_shot
        self.assertTrue(q.activate(e))
        # Exercise the actual selection branch at 60 Hz through the concealed
        # handoff and a stationary second, then genuinely resume movement.
        for frame in range(int((ENTRY_DURATION + 1.) * 60)):
            q.tick(1 / 60, e)
            with self.assertRaises(CameraSelected):
                lake.render(e, 30. + (frame + 1) / 60)
            self.assertEqual(camera_signature(lake.last_camera), before, (q.state, q.elapsed))
            self.assertEqual(lake.last_shot, shot, (q.state, q.elapsed))
        self.assertIsNotNone(q.locked_camera)
        e.yaw=math.pi
        self.assertGreater(e.tick(.1,1.),0.)
        q.tick(.1,e)
        with self.assertRaises(CameraSelected):lake.render(e,40.)
        self.assertIsNone(q.locked_camera)

    def test_original_pavilion_is_retained_and_reflects_about_each_worlds_water_level(self):
        from huxin_canals_viewer import Lake
        from temple_interior_viewer import camera
        import pyray as pr
        shared = ('pavilion_posts', 'pavilion_brackets', 'pavilion_roofs',
                  'pavilion_ceiling', 'pavilion_details', 'pavilion_inscriptions',
                  'pavilion_base', 'lake_lamps', 'moon_basin', 'moon_fixture')
        for name in shared:
            self.assertEqual((KIT / (name + '.glb')).read_bytes(),
                             (ROOT / 'art/temple/huxin_moon' / (name + '.glb')).read_bytes(), name)
        q, e = at_basin()
        lake = Lake.__new__(Lake)
        lake.sequence = q
        lake.models = {'moon_mirror': SimpleNamespace(transform=None)}
        lake.shader = SimpleNamespace(id=1)
        lake.canals_manifest = {'models': {}}
        lake.uniform = lambda *args: None
        cam = camera((4., 3.4, 5.), (0., 1., 0.), 65)
        original_library = pr.rl
        class WithoutGpu:
            def __getattr__(self, name):
                if name in ('rlDisableBackfaceCulling', 'rlEnableBackfaceCulling'):
                    return lambda *args: None
                return getattr(original_library, name)
        with patch.object(pr, 'rl', WithoutGpu()):
            for reflected in (False, True):
                baseline = None
                for state, shown, elapsed in (('ordinary', False, 0.), ('entering', True, ENTRY_SWAP),
                                               ('entering', True, (ENTRY_SWAP+ENTRY_DURATION)/2), ('canals', True, 0.)):
                    q.state, q.revealed, q.elapsed = state, shown, elapsed
                    self.assertEqual(lake.water_y, -1.55 if shown else 0., (state, reflected))
                    calls = []
                    lake.draw = lambda *args: calls.append(args)
                    lake.geometry(e, cam, 45., reflected, False)
                    retained = [call for call in calls if call[0] in shared]
                    self.assertEqual({call[0] for call in retained}, set(shared), (state, reflected))
                    expected_offset=(0,2*lake.water_y,0) if reflected else (0,0,0)
                    self.assertTrue(all(call[1]==expected_offset for call in retained))
                    retained=[(call[0],(0,0,0),*call[2:]) for call in retained]
                    if baseline is None:
                        baseline = retained
                    self.assertEqual(retained, baseline, (state, reflected))

    def test_only_the_matching_precollected_disc_can_start_the_encounter(self):
        q, e = at_basin()
        matching = lambda item: item and item.get('kind') == DISC_ITEM['kind'] and item.get('group') == DISC_ITEM['group']
        self.assertEqual(sum(item['count'] for item in q.inventory if matching(item)), 1)
        q.inventory[:] = [None if matching(item) else item for item in q.inventory]
        self.assertTrue(add(q.inventory, {'kind': 'key', 'group': 'unrelated_door', 'count': 1}))
        inventory = copy.deepcopy(q.inventory)
        self.assertFalse(q.activate(e))
        q.focus = True
        q.tick(30., e)
        self.assertEqual(q.world, 'lake')
        self.assertEqual(q.state, 'ordinary')
        self.assertEqual(q.inventory, inventory)

    def test_placement_is_nearby_and_atomic_and_preserves_other_inventory(self):
        q, e = at_basin()
        self.assertTrue(add(q.inventory, {'kind': 'ammo', 'count': 5}))
        self.assertTrue(add(q.inventory, {'kind': 'key', 'group': 'archive', 'count': 1}))
        before = copy.deepcopy(q.inventory)
        pose = (e.x, e.height, e.z, e.yaw, e.phase)
        e.x, e.z = causeway_point(.3)
        self.assertFalse(q.activate(e))
        self.assertEqual(q.inventory, before)
        e.x, e.height, e.z, e.yaw, e.phase = pose
        self.assertTrue(q.activate(e))
        self.assertTrue(q.disc_placed)
        self.assertEqual(q.state, 'entering')
        expected = [None if item and item.get('group') == DISC_ITEM['group'] else item for item in before]
        self.assertEqual(q.inventory, expected)
        placed = copy.deepcopy(q.inventory)
        self.assertFalse(q.activate(e))
        self.assertEqual(q.inventory, placed)
        self.assertEqual((e.x, e.height, e.z, e.yaw, e.phase), pose)

    def test_lake_approach_uses_the_established_distance_driven_mist(self):
        q, e = at_basin()
        old = MoonSequence()
        for progress in np.linspace(0., 1., 51):
            e.x, e.z = causeway_point(progress)
            q.tick(.05, e)
            old.tick(.05, e)
            self.assertEqual(q.world, 'lake')
            self.assertAlmostEqual(q.veil, old.veil)
            self.assertAlmostEqual(q.fog_arrival, old.fog_arrival)
        still = (q.veil, q.fog_arrival)
        for _ in range(200):
            e.tick(.05, 0., 1.)
            q.tick(.05, e)
        self.assertEqual((q.veil, q.fog_arrival), still)

    def test_reveal_preserves_position_and_inventory_and_has_no_automatic_exit(self):
        from g_huxin_canals_layout import support
        q, e = at_basin()
        self.assertTrue(add(q.inventory, {'kind': 'health', 'count': 1, 'value': 17}))
        self.assertTrue(q.activate(e))
        activation_opacity=q.veil
        original = (e.x, e.height, e.z, e.yaw, e.phase)
        inventory = copy.deepcopy(q.inventory)
        was_revealed = False
        swaps = []
        for _ in range(int(ENTRY_DURATION / .025) + 2):
            q.tick(.025, e)
            self.assertEqual(q.inventory, inventory)
            self.assertEqual((e.x, e.height, e.z, e.yaw, e.phase), original)
            if q.revealed != was_revealed:
                swaps.append((q.elapsed, q.veil))
                self.assertGreaterEqual(q.elapsed, ENTRY_SWAP)
                self.assertLess(q.elapsed, ENTRY_SWAP + .03)
                self.assertEqual(q.veil, activation_opacity)
                self.assertIsNotNone(support(e.x, e.z, e.height))
            was_revealed = q.revealed
        self.assertEqual(len(swaps), 1)
        self.assertEqual(q.world, 'canals')
        self.assertEqual(q.state, 'canals')
        self.assertFalse(q.movement_locked)
        self.assertEqual(q.veil, activation_opacity)
        # The old departure thresholds are intentionally powerless here.
        for progress in np.linspace(1., 0., 41):
            e.x, e.z = causeway_point(progress)
            q.tick(.1, e)
            self.assertEqual(q.state, 'canals')
            self.assertEqual(q.world, 'canals')
            self.assertTrue(q.revealed)
            self.assertEqual(q.veil, activation_opacity)
        self.assertFalse(q.activate(e))
        self.assertEqual(q.inventory, inventory)

    def test_lake_and_moon_sources_match_the_documented_protected_baseline(self):
        snapshot = json.loads((KIT / 'origin_snapshot.json').read_text(encoding='utf-8'))
        hashes = snapshot['original_sha256']
        self.assertIn('g_huxin.py', hashes)
        self.assertIn('huxin_viewer.py', hashes)
        self.assertIn('g_huxin_moon_sequence.py', hashes)
        self.assertIn('huxin_moon_viewer.py', hashes)
        self.assertTrue(any(name.startswith('art/temple/huxin/') for name in hashes))
        self.assertTrue(any(name.startswith('art/temple/huxin_moon/') for name in hashes))
        for name, expected in hashes.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_flooded_version_is_an_unchanged_independent_high_water_scene(self):
        from huxin_canals_flooded_viewer import Lake
        from g_huxin_canals_flooded_sequence import CanalSequence as FloodedSequence
        frozen=json.loads((ROOT/'art/temple/huxin_canals_flooded/frozen_snapshot.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(frozen['sha256']),80)
        for name,expected in frozen['sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)
        lake=Lake.__new__(Lake);lake.sequence=FloodedSequence()
        self.assertEqual(lake.water_y,0.)
        lake.sequence.revealed=True;lake.sequence.state='canals'
        self.assertEqual(lake.water_y,0.)

    def test_automated_scene_checks_open_no_audio_device(self):
        from huxin_canals_audio import EncounterAudio
        audio = EncounterAudio(automated=True)
        try:
            self.assertTrue(audio.muted)
            self.assertFalse(audio.opened)
            q, e = at_basin()
            enter(q, e)
            audio.drain(q)
            audio.drain(q)
            self.assertEqual(audio.played, ['bell'])
        finally:
            audio.close()


class CanalArchitectureTests(unittest.TestCase):
    def test_exposed_bank_sides_and_bottom_caps_face_the_water(self):
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        edges=manifest['solid_bank_edges'];self.assertGreater(len(edges),30)
        spatial=TriangleIndex(np.concatenate([geometry(n)[1] for n in ('canal_ground','canal_masonry','canal_timber','canal_distant')]))
        missing=[]
        surfaces=[('stone',i,a,b,manifest['bank_bottom'],(DECK-.015,DECK-.16,manifest['water']+.12))
                  for i,(a,b) in enumerate(edges)]
        timber_bottom=manifest['timber_bottom']
        surfaces.extend(('timber',i,a,b,timber_bottom,(DECK-.015,(DECK+timber_bottom)/2,timber_bottom+.015))
                        for i,(a,b) in enumerate(manifest['timber_bank_edges']))
        for material,edge_index,a,b,bottom,levels in surfaces:
            a,b=np.asarray(a,float),np.asarray(b,float);delta=b-a;length=np.linalg.norm(delta)
            if length<.035:continue
            outward=np.array((delta[1],0.,-delta[0]))/length
            for t in (.2,.5,.8):
                x,z=a+(b-a)*t
                for y in levels:
                    surface=np.array((x,y,z));origin=surface+outward*.12;end=surface-outward*.06
                    hits=front_intersections(spatial.query(origin,end),origin,-outward)
                    if not any((hits>.001)&(hits<.18)):missing.append(('bank_side',material,edge_index,t,y))
                # A downward-facing cap must close the underside too, rather
                # than merely hiding a reversed wall behind two-sided shading.
                origin=np.array((x,bottom-.12,z))-outward*.015;end=origin+np.array((0.,.20,0.))
                hits=front_intersections(spatial.query(origin,end),origin,np.array((0.,1.,0.)))
                if not any(abs(hits-.12)<.025):missing.append(('bank_bottom',material,edge_index,t))
        self.assertFalse(missing,('Open or inward bank shell',len(missing),missing[:30]))

    def test_washing_flanks_risers_and_mouth_caps_are_front_facing_and_closed(self):
        from g_huxin_canals_layout import step_point
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        spatial=TriangleIndex(geometry('canal_masonry')[1]);missing=[]
        for stair in manifest['washing_steps']:
            direction=np.array((math.cos(stair['angle']),0.,math.sin(stair['angle'])))
            for index,tread in enumerate(stair['treads']):
                polygon=np.asarray(tread['polygon']);y=tread['center'][1]
                for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
                    edge=b-a;length=np.linalg.norm(edge)
                    if length<.025:continue
                    outward=np.array((edge[1],0.,-edge[0]))/length
                    if np.dot(outward,direction)<-.5:continue # Hidden inside uphill neighbour.
                    x,z=(a+b)*.5;surface=np.array((x,y-.04,z))
                    origin=surface+outward*.10;end=surface-outward*.05
                    hits=front_intersections(spatial.query(origin,end),origin,-outward)
                    if not any((hits>.001)&(hits<.15)):missing.append(('side_or_riser',stair['id'],index,x,z))
                x,_,z=tread['center'];origin=np.array((x,stair['bank_bottom']-.1,z));end=origin+np.array((0.,.15,0.))
                hits=front_intersections(spatial.query(origin,end),origin,np.array((0.,1.,0.)))
                if not any(abs(hits-.1)<.02):missing.append(('bottom',stair['id'],index))
            # The full-width quay cut must meet real stone at both shoulders;
            # a narrower worn tread contour must not leave an open vertical slit.
            spec={**stair,'top':(stair['top'][0],stair['top'][2])}
            for side in (-1,1):
                x,z=step_point(spec,.08,side*(stair['width']/2-.005))
                origin=np.array((x,DECK+.1,z));end=origin-np.array((0.,.20,0.))
                hits=front_intersections(spatial.query(origin,end),origin,np.array((0.,-1.,0.)))
                if not any(abs(hits-.1)<.025):missing.append(('mouth_cap',stair['id'],side))
        self.assertFalse(missing,('Open or inward washing shell',len(missing),missing[:30]))

    def test_accessible_room_floors_meet_the_inner_walls_without_light_slits(self):
        from g_huxin_canals_layout import transform
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        spatial=TriangleIndex(np.concatenate([geometry(n)[1] for n in ('canal_interiors','canal_shadow')]))
        for house in manifest['houses']:
            if not house.get('enterable'):continue
            plan=house['ground_plan'];w=house['width']/2;back=house['depth']/2
            # Probe 2mm inside each actual wall face. The former 1cm slab
            # inset gap was far from the walking centerline but leaked light.
            inset=plan['wall_thickness']+.002
            middle=(plan['frontwall']+back)/2
            spec=dict(cx=house['center'][0],cz=house['center'][2],width=house['width'],depth=house['depth'],yaw=house['yaw'])
            for u,v in ((-w+inset,middle),(w-inset,middle),(-w*.55,back-inset),(w*.55,back-inset)):
                x,z=transform(spec,u,v);y=plan['ground_y']
                origin=np.array((x,y+.10,z));end=origin-np.array((0.,.2,0.))
                hits=front_intersections(spatial.query(origin,end),origin,np.array((0.,-1.,0.)),tolerance=1e-6)
                self.assertTrue(any(abs(hits-.10)<.005),('Room floor light slit',house['id'],u,v,hits.tolist()))

    def test_most_washing_flights_are_behind_houses_with_real_rear_doorways(self):
        from g_huxin_canals_layout import local_point
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        houses={h['seed']:h for h in manifest['houses']}
        stairs=manifest['washing_steps'];rear=[s for s in stairs if s.get('side')=='rear']
        self.assertGreater(len(rear),len(stairs)/2)
        opposite=[s for s in rear if s.get('opposite_bank')]
        self.assertGreaterEqual(len(opposite),2,'The visible opposite houses need real rear washing flights')
        self.assertTrue(all(not s['walkable'] for s in opposite))
        for stair in rear:
            h=houses[stair['house_seed']]
            self.assertTrue(h['ground_plan']['rear_access'],h['id'])
            portals=[p for p in h['door_portals'] if p.get('side')=='rear']
            self.assertTrue(portals,('Rear stairs have no doorway',h['id']))
            spec=dict(cx=h['center'][0],cz=h['center'][2],width=h['width'],depth=h['depth'],yaw=h['yaw'])
            for tread in stair['treads']:
                x,y,z=tread['center'];u,v=local_point(spec,x,z)
                self.assertGreater(v,h['depth']/2+.05,('Stair runs beneath house',h['id'],stair['id'],v))
            for portal in portals:
                normal=np.asarray(portal['normal']);approach=np.asarray(portal['approach']);inside=np.asarray(portal['inside'])
                self.assertGreater(np.dot(approach-inside,normal),1.,('Reversed rear portal',h['id']))
                self.assertGreaterEqual(portal['clear_width'],1.35)

    def test_rear_landings_are_reached_through_the_house_and_walked_back(self):
        from g_huxin_canals_layout import THROUGH_HOUSE_ROUTES,WASHING_STAIRS,HOUSE_SPECS,local_point,WATER_Y
        houses={h['seed']:h for h in HOUSE_SPECS}
        exported={h['seed']:h for h in json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))['houses']}
        expected={s['id'] for s in WASHING_STAIRS if s.get('side')=='rear' and s['walkable']}
        self.assertTrue(expected)
        self.assertEqual({r['stair_id'] for r in THROUGH_HOUSE_ROUTES},expected)
        for record in THROUGH_HOUSE_ROUTES:
            house=houses[record['seed']]
            x0,z0,x1,z1=exported[record['seed']]['rooms'][0]['local']
            for run in (False,True):
                samples=walk_tour(run=run,washing=record['washing_index'])
                local=[(*local_point(house,x,z),y) for x,y,z in samples]
                interior=next((i for i,(u,v,y) in enumerate(local) if x0+.1<u<x1-.1 and z0+.1<v<z1-.1),None)
                self.assertIsNotNone(interior,('Rear flight bypasses house',record['seed']))
                outside=next((i for i,(u,v,y) in enumerate(local) if v>house['depth']/2+.5),None)
                self.assertIsNotNone(outside)
                self.assertLess(interior,outside)
                low=next(i for i,(x,y,z) in enumerate(samples) if y<WATER_Y+.65)
                self.assertLess(outside,low)
                self.assertLess(math.dist(samples[0],samples[-1]),.1)

    def test_causeway_join_has_real_continuous_floor_across_its_usable_width(self):
        from g_huxin_canals import PATH
        from g_huxin_canals_layout import support
        source=geometry('causeway')[1];new=geometry('canal_ground')[1]
        indices=(TriangleIndex(np.concatenate((source,new))),TriangleIndex(new))
        for z in (11.45,11.85,11.99,12.01,12.15,12.55):
            a,b=next((a,b) for a,b in zip(PATH,PATH[1:]) if min(a[1],b[1])<=z<=max(a[1],b[1]))
            t=(z-a[1])/(b[1]-a[1]);center=a[0]+t*(b[0]-a[0])
            # Beyond z12 the old mesh is clipped by the actual renderer;
            # it must not conceal a missing new quay floor in the ray check.
            spatial=indices[int(z>=12.)]
            for side in (-.55,0.,.55):
                x=center+side
                self.assertIsNotNone(support(x,z,DECK),('Unsupported causeway seam',x,z))
                origin=np.array((x,DECK+.10,z));end=origin-np.array((0.,.2,0.))
                hits=front_intersections(spatial.query(origin,end),origin,np.array((0.,-1.,0.)),tolerance=1e-5)
                self.assertTrue(any(abs(hits-.10)<.025),('Missing causeway seam floor',x,z))

    def test_blocked_quay_ends_have_a_visible_physical_break(self):
        from g_huxin_canals_layout import support
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(manifest['blocked_ends']),2)
        triangles=np.concatenate([geometry(name)[1] for name in ('canal_ground','canal_masonry','canal_details','canal_distant')])
        low,high=triangles.min(axis=1),triangles.max(axis=1)
        for end in manifest['blocked_ends']:
            a=np.array(end['approach']);b=np.array(end['beyond']);direction=b-a;direction/=np.linalg.norm(direction)
            self.assertIsNotNone(support(*a,DECK),end['name'])
            self.assertIsNone(support(*b,DECK),end['name'])
            q,e=at_basin();enter(q,e);e.x,e.z=a;e.height=DECK;e.yaw=math.atan2(direction[0],-direction[1])
            for _ in range(90):e.tick(.05,1.,0.,True)
            self.assertGreater(math.dist((e.x,e.z),b),.6,end['name'])
            # The stopped player sees an actual exposed bank edge and open
            # water beyond it, rather than a continuous floor behind a wall.
            midpoint=np.asarray(end['edge']).mean(axis=0)
            origin=np.array((midpoint[0]+direction[0]*.6,DECK-.45,midpoint[1]+direction[1]*.6))
            nearby=triangles[(high[:,0]>=midpoint[0]-1.5)&(low[:,0]<=midpoint[0]+1.5)&
                             (high[:,2]>=midpoint[1]-1.5)&(low[:,2]<=midpoint[1]+1.5)]
            hits=intersections(nearby,origin,np.array((-direction[0],0.,-direction[1])),tolerance=1e-5)
            self.assertTrue(any((hits>.001)&(hits<1.2)),('Invisible quay limit',end['name']))
            nearby=triangles[(low[:,0]<=b[0]+.001)&(high[:,0]>=b[0]-.001)&(low[:,2]<=b[1]+.001)&(high[:,2]>=b[1]-.001)]
            hits=intersections(nearby,np.array((b[0],DECK+.10,b[1])),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertFalse(any(hits<.25),('Intact floor beyond invisible boundary',end['name']))

    def test_every_house_has_a_real_frontage_walkway_and_exposed_water_bank(self):
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        solid=[name for name in manifest['models'] if name not in ('canal_water','canal_annulus')]
        triangles=np.concatenate([geometry(name)[1] for name in solid])
        low,high=triangles.min(axis=1),triangles.max(axis=1)
        self.assertEqual(len(manifest['houses']),manifest['building_count'])
        holes=[]
        for h in manifest['houses']:
            frontage=h['frontage'];polygon=np.asarray(frontage['polygon'],float)
            self.assertGreaterEqual(len(polygon),4,h['id'])
            self.assertEqual(frontage['walk_y'],DECK,h['id'])
            self.assertLess(frontage['bank_bottom'],manifest['water']-.4,h['id'])
            center=polygon.mean(axis=0)
            # The metadata must correspond to actual exported horizontal stone
            # or timber, including houses well beyond the playable district.
            near=triangles[(low[:,0]<=center[0]+.001)&(high[:,0]>=center[0]-.001)&
                           (low[:,2]<=center[1]+.001)&(high[:,2]>=center[1]-.001)]
            hits=intersections(near,np.array((center[0],DECK+.4,center[1])),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertTrue(any(abs(hits-.4)<.06),('House has no frontage floor',h['id']))
            edge=np.asarray(frontage['water_edge'],float);middle=edge.mean(axis=0)
            outward=middle-np.array((h['center'][0],h['center'][2]));outward/=np.linalg.norm(outward)
            near=triangles[(high[:,0]>=middle[0]-1.2)&(low[:,0]<=middle[0]+1.2)&
                           (high[:,2]>=middle[1]-1.2)&(low[:,2]<=middle[1]+1.2)]
            for y in (manifest['water']+.12,DECK-.20):
                origin=np.array((middle[0]+outward[0]*.45,y,middle[1]+outward[1]*.45))
                direction=np.array((-outward[0],0.,-outward[1]))
                hits=intersections(near,origin,direction,tolerance=1e-5)
                if not any((hits>.001)&(hits<1.)):holes.append((h['id'],y))
        self.assertFalse(holes,('Frontage banks have holes',holes))

    def test_washing_stairs_reach_the_lower_water_and_return_to_the_quay(self):
        from g_huxin_canals_layout import WASHING_ROUTES,WATER_Y
        self.assertGreaterEqual(len(WASHING_ROUTES),3)
        for stair in range(len(WASHING_ROUTES)):
            for run in (False,True):
                samples=walk_tour(run=run,washing=stair)
                heights=[p[1] for p in samples]
                self.assertLess(min(heights),WATER_Y+.65)
                self.assertGreater(min(heights),WATER_Y)
                self.assertAlmostEqual(heights[-1],DECK)
                self.assertLess(math.dist(samples[0],samples[-1]),.10)

    def test_exported_washing_flights_continue_below_water_with_supported_landings(self):
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        stairs=manifest['washing_steps'];self.assertGreaterEqual(len(stairs),6)
        triangles=geometry('canal_masonry')[1]
        low,high=triangles.min(axis=1),triangles.max(axis=1)
        for stair in stairs:
            treads=stair['treads'];heights=[t['center'][1] for t in treads]
            self.assertGreaterEqual(len(treads),12)
            self.assertAlmostEqual(heights[0],DECK)
            self.assertLess(heights[-1],manifest['water'])
            self.assertTrue(all(.08<a-b<.22 for a,b in zip(heights,heights[1:])),stair['id'])
            surfaces=treads+[stair['landing_geometry']] if stair['landing_geometry'] else treads
            for tread in surfaces:
                x,y,z=tread['center']
                nearby=triangles[(low[:,0]<=x+.001)&(high[:,0]>=x-.001)&(low[:,2]<=z+.001)&(high[:,2]>=z-.001)]
                hits=front_intersections(nearby,np.array((x,y+.10,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
                self.assertTrue(any(abs(hits-.10)<.025),('Missing washing tread',stair['id'],tread['center']))
            # Both sides of each riser must remain stone. The previous worn
            # contours separated neighbouring treads by a few millimetres,
            # which center-of-tread probes could not see.
            for a,b in zip(treads,treads[1:]):
                pa,pb=np.asarray(a['center']),np.asarray(b['center'])
                direction=pb-pa;direction[1]=0.;direction/=np.linalg.norm(direction)
                for side,y in ((-.001,pa[1]),(.001,pb[1])):
                    x,_,z=(pa+pb)*.5+direction*side
                    nearby=triangles[(low[:,0]<=x+1e-5)&(high[:,0]>=x-1e-5)&(low[:,2]<=z+1e-5)&(high[:,2]>=z-1e-5)]
                    hits=front_intersections(nearby,np.array((x,y+.10,z)),np.array((0.,-1.,0.)),tolerance=1e-6)
                    self.assertTrue(any(abs(hits-.10)<.005),('Gap beside washing riser',stair['id'],x,y,z,hits.tolist()))

    def test_lower_water_exposes_complete_house_foundations(self):
        from g_huxin_canals_layout import WATER_Y,transform
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(DECK,.325)
        self.assertEqual(WATER_Y,-1.55)
        self.assertEqual(manifest['water'],WATER_Y)
        water=geometry('canal_water')[1]
        self.assertTrue(np.all(abs(water[:,:,1]-WATER_Y)<1e-5))
        self.assertGreater(DECK-WATER_Y,1.8)
        solid=[name for name in manifest['models'] if name not in ('canal_water','canal_annulus')]
        triangles=np.concatenate([geometry(name)[1] for name in solid])
        low,high=triangles.min(axis=1),triangles.max(axis=1)
        for h in manifest['houses']:
            self.assertLessEqual(h['foundation_bottom'],WATER_Y-.5,h['id'])
            self.assertEqual(h['water_y'],WATER_Y,h['id'])
            s=dict(cx=h['center'][0],cz=h['center'][2],width=h['width'],depth=h['depth'],yaw=h['yaw'])
            w,d=h['width']/2,h['depth']/2
            corners=np.array([transform(s,x,z) for x,z in ((-w,-d),(w,-d),(w,d),(-w,d))])
            near=triangles[(high[:,0]>=corners[:,0].min()-.8)&(low[:,0]<=corners[:,0].max()+.8)&
                           (high[:,2]>=corners[:,1].min()-.8)&(low[:,2]<=corners[:,1].max()+.8)&(low[:,1]<DECK+.1)]
            for a,b in zip(corners,np.roll(corners,-1,axis=0)):
                middle=(a+b)*.5;edge=b-a
                outward=np.array((edge[1],0.,-edge[0]));outward/=np.linalg.norm(outward)
                for y in (WATER_Y+.1,(WATER_Y+DECK)*.5,DECK-.16):
                    origin=np.array((middle[0],y,middle[1]))+outward*.5
                    hits=front_intersections(near,origin,-outward,tolerance=1e-5)
                    self.assertTrue(any((hits>.001)&(hits<1.1)),('Exposed foundation hole',h['id'],middle,y))

    def test_every_advertised_door_bay_accepts_natural_straight_capsule_entry(self):
        manifest=json.loads((KIT/'canals_manifest.json').read_text(encoding='utf-8'))
        solid=[name for name in manifest['models'] if name not in ('canal_water','canal_annulus','canal_distant')]
        triangles=np.concatenate([geometry(name)[1] for name in solid])
        spatial=TriangleIndex(triangles)
        # Controller crossings are exercised by the route/camera/floor checks.
        # Keep this independent mesh check cheap enough to rerun after a prop
        # move without replaying every traversal a second time.
        tours=[]
        for house in manifest['houses']:
            for bay,portal in enumerate(house.get('door_portals',())):
                if not portal.get('accessible'):continue
                offset=min(.25,portal['clear_width']/2-.28)
                for side in (-offset,0.,offset):
                    tours.append(dict(seed=house['seed'],bay=bay,offset=side,portal=portal))
        self.assertGreaterEqual(len(tours),90)
        for tour in tours:
            portal=tour['portal'];normal=np.asarray(portal['normal'],float)
            tangent=np.asarray(portal['tangent'],float);tangent/=np.linalg.norm(tangent)
            # Check actual exported geometry at both sides of the capsule,
            # across the whole porch-to-room crossing, not just its center ray.
            for side in (-.18,.18):
                a=np.asarray(portal['approach'],float)+tangent*(tour['offset']+side)
                b=np.asarray(portal['inside'],float)+tangent*(tour['offset']+side)
                for height in (.35,.95,1.65):
                    origin=a+np.array((0,height,0));end=b+np.array((0,height,0))
                    direction=end-origin;distance=np.linalg.norm(direction)
                    nearby=spatial.query(origin,end)
                    hits=intersections(nearby,origin,direction/distance,tolerance=1e-5)
                    self.assertFalse(any((hits>.001)&(hits<distance-.001)),
                                     ('Visible doorway blocks capsule',tour['seed'],tour['bay'],tour['offset'],side,height,hits.tolist()))

    def test_vacant_houses_can_be_entered_and_left_through_their_real_doorways(self):
        from g_huxin_canals_layout import ROOM_ROUTES, DOOR_ROUTES, HOUSE_SPECS, in_house
        houses = {house['seed']:house for house in HOUSE_SPECS if house.get('enterable')}
        self.assertEqual(len(ROOM_ROUTES), len(DOOR_ROUTES))
        self.assertEqual({route['seed'] for route in DOOR_ROUTES},set(houses))
        for room, route in enumerate(DOOR_ROUTES):
            house=houses[route['seed']]
            for run in (False, True):
                samples = walk_tour(run=run, room=room)
                self.assertTrue(any(in_house(house,x,z,-.5) for x,y,z in samples), house['seed'])
                self.assertLess(math.dist(samples[0], samples[-1]), .10)

    def test_house_openings_have_real_depth_and_enclosed_hollow_rooms(self):
        manifest = json.loads((KIT / 'canals_manifest.json').read_text(encoding='utf-8'))
        houses = [house for house in manifest['houses'] if house.get('rooms') and house.get('openings')]
        self.assertGreaterEqual(len(houses), 12)
        names = [name for name in manifest['models']
                 if name not in ('canal_water', 'canal_annulus', 'canal_distant')]
        triangles = np.concatenate([geometry(name)[1] for name in names])
        low, high = triangles.min(axis=1), triangles.max(axis=1)
        def ray(origin, direction, distance):
            end = origin + direction * distance
            near = triangles[np.all(high >= np.minimum(origin, end)-.001, axis=1) &
                             np.all(low <= np.maximum(origin, end)+.001, axis=1)]
            return intersections(near, origin, direction, tolerance=1e-5)
        tested = {'door': 0, 'window': 0, 'screen': 0}
        for house in houses[:24]:
            # Side apertures may abut a neighbouring party wall. The visible
            # canal frontage must open through its own wall into the room.
            frontage = np.array((math.sin(house['yaw']), 0., -math.cos(house['yaw'])))
            for kind in ('door', 'window'):
                aperture = next((opening for opening in house['openings']
                                 if opening['kind'] == kind and not opening.get('covered') and
                                 np.dot(opening['normal'], frontage) > .95), None)
                if aperture is None:
                    continue
                center = np.asarray(aperture['center'])
                normal = np.asarray(aperture['normal'])
                normal /= np.linalg.norm(normal)
                origin = center + normal * .35
                hits = ray(origin, -normal, aperture['room_depth'] + 1.)
                # The view must pass the wall thickness into an actual room.
                # A flat black rectangle or an uncut solid house fails here.
                self.assertFalse(any(hits < .35 + aperture['wall_thickness'] + .25),
                                 (house['id'], kind, 'Opening is sealed', hits.tolist()))
                tested[kind] += 1
            panel = next((opening for opening in house['openings'] if opening.get('covered')), None)
            if panel is not None and tested['screen'] < 8:
                center = np.asarray(panel['center'])
                normal = np.asarray(panel['normal']);normal /= np.linalg.norm(normal)
                tangent = np.array((normal[2], 0., -normal[0]))
                clear = 0
                for horizontal in (-.37, -.18, .02, .22, .38):
                    for vertical in (-.35, -.13, .09, .31):
                        origin = center + normal*.35 + tangent*(horizontal*panel['clear_width'])
                        origin[1] += vertical*panel['clear_height']
                        limit = .35 + panel['wall_thickness'] + .25
                        hits = ray(origin, -normal, limit)
                        clear += not any(hits < limit)
                self.assertGreaterEqual(clear, 5, (house['id'], 'Screen is an opaque panel', clear))
                tested['screen'] += 1
            for room in house['rooms']:
                center = np.asarray(room['world_corners']).mean(axis=0)
                center[1] = (room['y'] + room['ceiling']) * .5
                down = ray(center, np.array((0., -1., 0.)), 6.)
                up = ray(center, np.array((0., 1., 0.)), 6.)
                self.assertTrue(len(down), (house['id'], 'No interior floor'))
                self.assertTrue(len(up), (house['id'], 'No interior ceiling'))
                self.assertGreater(down.min(), .45, (house['id'], 'Room filled with solid geometry'))
                self.assertGreater(up.min(), .45, (house['id'], 'Room filled with solid geometry'))
                self.assertAlmostEqual(center[1]-down.min(), room['y'], delta=.16)
                self.assertAlmostEqual(center[1]+up.min(), room['ceiling'], delta=.22)
        self.assertGreaterEqual(tested['door'], 12)
        self.assertGreaterEqual(tested['window'], 5)
        self.assertGreaterEqual(tested['screen'], 6)

    def test_new_paving_leaves_the_original_pavilion_floor_uncovered(self):
        from g_huxin_canals import inside_platform
        triangles = geometry('canal_ground')[1]
        normal = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
        center = triangles.mean(axis=1)
        top = center[(normal[:, 1] > 1e-7) & (abs(center[:, 1]-DECK) < .08)]
        self.assertFalse(any(inside_platform(x, z, .02) for x, y, z in top))

    def test_authored_route_cameras_see_the_player_through_exported_architecture(self):
        from huxin_canals_camera import canal_camera
        from g_huxin_canals import camera_zone
        manifest = json.loads((KIT / 'canals_manifest.json').read_text(encoding='utf-8'))
        solid = [name for name in manifest['models']
                 if name not in ('canal_water', 'canal_annulus', 'canal_distant')]
        solid += ['pavilion_posts', 'pavilion_brackets', 'pavilion_roofs',
                  'pavilion_ceiling', 'pavilion_details', 'moon_basin', 'moon_fixture']
        triangles = np.concatenate([geometry(name)[1] for name in solid])
        spatial=TriangleIndex(triangles)
        from g_huxin_canals_layout import ROOM_ROUTES,WASHING_ROUTES
        from g_huxin_canals_sequence import support
        samples = walk_tour()[::12] + [p for room in range(len(ROOM_ROUTES)) for p in walk_tour(room=room)[::3]]
        samples += [p for tour in door_tours() if not tour['run'] and tour['offset']==0.
                    for p in tour['samples'][::8]]
        samples += [p for stair in range(len(WASHING_ROUTES)) for p in walk_tour(washing=stair)[::3]]
        samples += [(x,DECK,z) for x in (-4.,-2.,0.,2.,4.) for z in (-4.,-2.,0.,2.,4.,6.)
                    if support(x,z,DECK,True) is not None]
        for x, y, z in samples:
            shot, cam = canal_camera(SimpleNamespace(x=x, z=z, height=y, shot=camera_zone(x,z)))
            eye = np.array((cam.position.x, cam.position.y, cam.position.z))
            view = np.array((x, y + .93, z)) - eye
            right = np.array((-view[2], 0., view[0]))
            right /= np.linalg.norm(right)
            clear = False
            # Partial occlusion by a thin post or rail is natural. An opaque
            # wall, roof or stair must not hide the whole player volume.
            for height in (.5, 1.0, 1.65):
                for side in (-.18, .18):
                    body = np.array((x, y + height, z)) + right * side
                    direction = body - eye
                    distance = np.linalg.norm(direction)
                    nearby = spatial.query(eye,body)
                    hits = intersections(nearby, eye, direction / distance, tolerance=1e-5)
                    clear |= not any((hits > .1) & (hits < distance - .12))
            self.assertTrue(clear, ('Player hidden behind geometry', shot, x, y, z))

    def test_new_architecture_exports_are_finite_self_contained_and_portable(self):
        manifest = json.loads((KIT / 'canals_manifest.json').read_text(encoding='utf-8'))
        for name, info in manifest['models'].items():
            doc, triangles = geometry(name)
            self.assertTrue(np.isfinite(triangles).all(), name)
            self.assertEqual(len(triangles), info['triangles'], name)
            self.assertTrue(all('uri' not in buffer for buffer in doc['buffers']), name)
            self.assertTrue(all('bufferView' in image for image in doc.get('images', [])), name)
            for mesh in doc['meshes']:
                for primitive in mesh['primitives']:
                    self.assertEqual(doc['accessors'][primitive['indices']]['componentType'], 5123, name)
        # Actual surrounding architecture reaches far beyond the compact loop.
        # A fog plane or a large empty water mesh cannot satisfy this check.
        from g_huxin_canals_layout import REVIEW_ROUTE
        distant = geometry('canal_distant')[1].reshape(-1, 3)
        playable_extent = np.ptp(np.asarray(REVIEW_ROUTE), axis=0)
        background_extent = np.ptp(distant[:, [0, 2]], axis=0)
        self.assertTrue(np.all(background_extent > playable_extent * 2.))

    def test_controller_tour_walks_and_runs_both_ways_over_real_height_changes(self):
        from g_huxin_canals_layout import support, BRIDGES
        for reverse in (False, True):
            for run in (False, True):
                samples = walk_tour(reverse, run)
                self.assertGreater(len(samples), 150)
                heights = [y for x, y, z in samples]
                self.assertGreater(max(heights), DECK + max(bridge['rise'] for bridge in BRIDGES) * .9)
                self.assertAlmostEqual(heights[-1], DECK)
                self.assertGreater(len(set(round(y, 5) for y in heights)), 12)
                for x, y, z in samples:
                    self.assertIsNotNone(support(x, z, y), (reverse, run, x, y, z))

    def test_open_water_and_building_interiors_cannot_be_used_as_shortcuts(self):
        from g_huxin_canals_layout import support, WALL_PROBES, WATER_PROBES, UPPER
        for x, z in WALL_PROBES + WATER_PROBES:
            for y in (DECK, UPPER):
                self.assertIsNone(support(x, z, y), (x, y, z))
        # Try real running input toward each forbidden water/wall point from
        # its closest valid station on the tour, rather than teleporting there.
        for target_x, target_z in WATER_PROBES + WALL_PROBES:
            q, e = at_basin()
            enter(q, e)
            e.x, e.height, e.z = min(walk_tour(), key=lambda p: math.hypot(p[0]-target_x,p[2]-target_z))
            e.yaw = math.atan2(target_x-e.x, -(target_z-e.z))
            for _ in range(80):
                e.tick(.1, 1., 0., True)
                self.assertIsNotNone(support(e.x, e.z, e.height))
                self.assertGreater(math.hypot(e.x-target_x,e.z-target_z), .19)

    def test_exported_floors_and_stair_treads_match_every_walked_surface(self):
        manifest = json.loads((KIT / 'canals_manifest.json').read_text(encoding='utf-8'))
        names = list(dict.fromkeys(manifest['walkable_models'] +
                     ['pavilion_base', 'causeway', 'canal_interiors', 'canal_shadow']))
        pieces=[geometry(name)[1] for name in names]
        clipped_causeway=np.concatenate([np.full(len(piece),name=='causeway') for name,piece in zip(names,pieces)])
        triangles = np.concatenate(pieces)
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        upwards=normals[:,1]>1e-7
        triangles = triangles[upwards];clipped_causeway=clipped_causeway[upwards]
        low, high = triangles.min(axis=1), triangles.max(axis=1)
        from g_huxin_canals_layout import ROOM_ROUTES,WASHING_ROUTES
        samples = walk_tour() + [p for room in range(len(ROOM_ROUTES)) for p in walk_tour(room=room)]
        samples += [p for tour in door_tours() for p in tour['samples'][::4]]
        samples += [p for stair in range(len(WASHING_ROUTES)) for p in walk_tour(washing=stair)]
        missing=[]
        for x, y, z in samples:
            eligible=(low[:,0]<=x+.001)&(high[:,0]>=x-.001)&(low[:,2]<=z+.001)&(high[:,2]>=z-.001)
            if z>12.:eligible&=~clipped_causeway
            nearby=triangles[eligible]
            hits = intersections(nearby, np.array((x, y + .22, z)), np.array((0., -1., 0.)), tolerance=1e-5)
            if not any(abs(hits-.22)<.045):missing.append((x,y,z,hits.tolist()))
        self.assertFalse(missing,('Missing floors',len(missing),missing[:30]))


if __name__ == '__main__':
    unittest.main()
