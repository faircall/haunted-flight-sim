"""Void canals: real movement, exported architecture, one-way entry and isolation."""
import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from g_inventory import add
from g_huxin_canals import Explorer, DECK
from g_huxin_canals_sequence import (CanalSequence, DISC_ITEM, ENTRY_SWAP,
    ENTRY_DURATION, causeway_point)
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


@lru_cache(maxsize=12)
def walk_tour(reverse=False, run=False, room=None):
    """Exercise the real tank controller over the entire interconnected route."""
    from g_huxin_canals_layout import REVIEW_ROUTE, ROOM_ROUTES
    points = REVIEW_ROUTE if room is None else ROOM_ROUTES[room]
    route = points[::-1] if reverse else points
    q, e = at_basin()
    enter(q, e)
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
    return result


class CanalSequenceTests(unittest.TestCase):
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
        lake.environment = stop_before_drawing
        with self.assertRaises(CameraSelected):
            lake.render(e, 30.)
        before = camera_signature(lake.last_camera)
        shot = lake.last_shot
        self.assertTrue(q.activate(e))
        # Exercise the actual selection branch at 60 Hz across both state
        # changes, the old ten-second cut, and one stationary second afterward.
        for frame in range(int((ENTRY_DURATION + 1.) * 60)):
            q.tick(1 / 60, e)
            with self.assertRaises(CameraSelected):
                lake.render(e, 30. + (frame + 1) / 60)
            self.assertEqual(camera_signature(lake.last_camera), before, (q.state, q.elapsed))
            self.assertEqual(lake.last_shot, shot, (q.state, q.elapsed))

    def test_complete_original_pavilion_is_drawn_identically_in_both_worlds_and_reflections(self):
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
                                               ('entering', True, 15.), ('canals', True, 0.)):
                    q.state, q.revealed, q.elapsed = state, shown, elapsed
                    self.assertEqual(lake.water_y, 0., (state, reflected))
                    calls = []
                    lake.draw = lambda *args: calls.append(args)
                    lake.geometry(e, cam, 45., reflected, False)
                    retained = [call for call in calls if call[0] in shared]
                    self.assertEqual({call[0] for call in retained}, set(shared), (state, reflected))
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
                self.assertGreater(q.veil, .999)
                self.assertIsNotNone(support(e.x, e.z, e.height))
            was_revealed = q.revealed
        self.assertEqual(len(swaps), 1)
        self.assertEqual(q.world, 'canals')
        self.assertEqual(q.state, 'canals')
        self.assertFalse(q.movement_locked)
        self.assertEqual(q.veil, 0.)
        # The old departure thresholds are intentionally powerless here.
        for progress in np.linspace(1., 0., 41):
            e.x, e.z = causeway_point(progress)
            q.tick(.1, e)
            self.assertEqual(q.state, 'canals')
            self.assertEqual(q.world, 'canals')
            self.assertTrue(q.revealed)
            self.assertEqual(q.veil, 0.)
        self.assertFalse(q.activate(e))
        self.assertEqual(q.inventory, inventory)

    def test_original_lake_and_moon_scenes_remain_byte_for_byte_unchanged(self):
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
    def test_vacant_houses_can_be_entered_and_left_through_their_real_doorways(self):
        from g_huxin_canals_layout import ROOM_ROUTES, HOUSE_SPECS, in_house
        houses = [house for house in HOUSE_SPECS if house.get('enterable')]
        self.assertEqual(len(ROOM_ROUTES), len(houses))
        for room, house in enumerate(houses):
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
        low, high = triangles.min(axis=1), triangles.max(axis=1)
        from g_huxin_canals_layout import ROOM_ROUTES
        from g_huxin_canals_sequence import support
        samples = walk_tour()[::12] + [p for room in range(len(ROOM_ROUTES)) for p in walk_tour(room=room)[::3]]
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
                    nearby = triangles[np.all(high >= np.minimum(eye, body), axis=1) &
                                       np.all(low <= np.maximum(eye, body), axis=1)]
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
        names = manifest['walkable_models'] + ['pavilion_base', 'causeway', 'canal_interiors', 'canal_shadow']
        triangles = np.concatenate([geometry(name)[1] for name in names])
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        triangles = triangles[normals[:, 1] > 1e-7]
        low, high = triangles.min(axis=1), triangles.max(axis=1)
        from g_huxin_canals_layout import ROOM_ROUTES
        samples = walk_tour() + [p for room in range(len(ROOM_ROUTES)) for p in walk_tour(room=room)]
        for x, y, z in samples:
            nearby = triangles[(low[:, 0] <= x + .001) & (high[:, 0] >= x - .001) &
                               (low[:, 2] <= z + .001) & (high[:, 2] >= z - .001)]
            hits = intersections(nearby, np.array((x, y + .22, z)), np.array((0., -1., 0.)), tolerance=1e-5)
            self.assertTrue(any(abs(hits - .22) < .045), ('Missing floor', x, y, z, hits.tolist()))


if __name__ == '__main__':
    unittest.main()
