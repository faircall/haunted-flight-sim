"""Hidden, muted native review of spatial Canals fog discovery.

The controller walks the real quay, doubles back, enters a house and reaches
its rear washing steps. The lateral excursion never exceeds the earlier
distance from the puzzle, so a radial reveal cannot satisfy this review.
"""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import argparse
import copy
import hashlib
import json
import math
import os
import time

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

import numpy as np
from PIL import Image, ImageDraw
import pyray as pr

from g_huxin_canals import DECK, camera_zone
from g_huxin_canals_layout import REVIEW_ROUTE, THROUGH_HOUSE_ROUTES
from g_huxin_canals_sequence import CanalSequence, ENTRY_DURATION, FOG_ARRIVAL_DURATION
from huxin_canals_audio import EncounterAudio
from huxin_canals_review import camera_signature, delta_report, pixels, protected_hashes, texture_pixels
from huxin_canals_viewer import Lake, Explorer, WIDTH, HEIGHT
from temple_interior_viewer import camera


ROOT = Path(__file__).parent
BASE = ROOT / 'artifacts' / 'huxin-canals-grid-v10'
PRODUCTION = (
    'g_canals_fog_grid.py', 'g_huxin_canals_sequence.py',
    'huxin_canals_viewer.py', 'shaders/huxin_canals_post.fs',
)
MOON_AND_METADATA = (
    'g_huxin_moon_sequence.py', 'huxin_moon_viewer.py',
    'shaders/huxin_moon_post.fs', 'huxin_moon_review.py',
    'huxin_moon_fog_review.py', 'test_huxin_moon_encounter.py',
    'art/temple/huxin_canals/origin_snapshot.json',
    'art/temple/huxin_canals_flooded/origin_snapshot.json',
    'art/temple/huxin_canals_flooded/frozen_snapshot.json',
)
PASS_SIZES = {
    pr.SHADER_UNIFORM_FLOAT: 1, pr.SHADER_UNIFORM_VEC2: 2,
    pr.SHADER_UNIFORM_VEC3: 3, pr.SHADER_UNIFORM_VEC4: 4,
}
VIEWS = (
    ('gameplay', None),
    ('reverse', ((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)),
)


def hashes(paths):
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def grid_bytes(grid):
    return bytes(grid.pixels())


def grid_array(grid):
    return np.frombuffer(grid_bytes(grid), np.uint8).reshape(grid.height, grid.width, 4).copy()


def grid_identity(grid):
    return {
        'revision': grid.revision,
        'sha256': hashlib.sha256(grid_bytes(grid)).hexdigest(),
        'clear_fraction': grid.clear_fraction,
    }


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def save_image(path, value):
    Image.fromarray(np.asarray(value, dtype=np.uint8)).save(path)


def state(q):
    return {
        'state': q.state, 'elapsed': q.elapsed, 'locked': q.movement_locked,
        'arrival': q.fog_arrival, 'depth': q.fog_depth,
        'blend': q.world_blend, 'grade': q.void_tone,
        'radial_handoff_reached': q.exploration.furthest_distance,
        'grid': grid_identity(q.fog_grid),
    }


class Review:
    def __init__(self, out, quick=False):
        self.out = out
        self.quick = quick
        self.scene = Lake()
        self.audio = EncounterAudio(True)
        self.actor = Explorer()
        self.clock = 40.
        self.steps = 0
        self.path = []
        self.frames = []
        self.audit_count = 0
        self.composition_peaks = []
        self.timings = []
        self.visibility = []

    @property
    def q(self):
        return self.scene.sequence

    def begin(self, view=None):
        q = self.scene.sequence = CanalSequence()
        e = self.actor
        e.encounter = q
        e.x, e.height, e.z = 1.65, DECK, 1.65
        e.yaw = e.phase = 0.
        e.clip = 'idle'
        e.shot = camera_zone(e.x, e.z)
        q.tick(.01, e)
        self.clock = 40.
        self.scene.player.pose('idle', 0., None)
        self.scene.render(e, self.clock, override=view)
        held = camera_signature(self.scene.last_camera)
        assert q.activate(e)
        self.audio.drain(q)
        return held

    def tick(self, seconds, turn=False):
        remaining = seconds
        while remaining > 1e-8:
            dt = min(1 / 60, remaining)
            if turn:
                assert not self.q.movement_locked
                self.actor.tick(dt, 0., 1.)
            self.q.tick(dt, self.actor)
            self.audio.drain(self.q)
            self.clock += dt
            remaining -= dt

    def render(self, label=None, override=None, show_player=True, audit=False, clock=None):
        """Capture real shader uploads while leaving all GPU calls intact."""
        scene, e, q = self.scene, self.actor, self.q
        before = grid_identity(q.fog_grid)
        logical = (q.state, q.elapsed, q.revealed)
        t = self.clock if clock is None else clock
        passes, locations, active, draws = [], {}, [], []
        get_location = pr.get_shader_location
        set_value = pr.set_shader_value
        set_texture = pr.set_shader_value_texture
        mist_pass, draw = scene.mist_pass, scene.draw

        def locate(shader, name):
            location = get_location(shader, name)
            if shader.id == scene.post.id and location >= 0:
                locations[location] = name
            return location

        def upload(shader, location, data, kind):
            if active and shader.id == scene.post.id and location in locations:
                values = tuple(float(data[i]) for i in range(PASS_SIZES[kind]))
                active[-1]['uniforms'][locations[location]] = values
            return set_value(shader, location, data, kind)

        def texture(shader, location, value):
            if active and shader.id == scene.post.id and location in locations:
                active[-1]['textures'][locations[location]] = int(value.id)
            return set_texture(shader, location, value)

        def mist(*args, **kwargs):
            reflected = kwargs.get('reflected', args[6] if len(args) > 6 else False)
            record = {
                'world': 'canals' if scene.render_revealed else 'lake',
                'reflected': bool(reflected),
                'uniforms': {}, 'textures': {},
            }
            active.append(record)
            try:
                return mist_pass(*args, **kwargs)
            finally:
                active.pop()
                passes.append(record)

        def drawn(name, *args, **kwargs):
            draws.append(name)
            return draw(name, *args, **kwargs)

        start = time.perf_counter()
        with ExitStack() as stack:
            stack.enter_context(patch.object(scene, 'draw', side_effect=drawn))
            if audit:
                stack.enter_context(patch.object(scene, 'mist_pass', side_effect=mist))
                stack.enter_context(patch.object(pr, 'get_shader_location', side_effect=locate))
                stack.enter_context(patch.object(pr, 'set_shader_value', side_effect=upload))
                stack.enter_context(patch.object(pr, 'set_shader_value_texture', side_effect=texture))
            scene.render(e, t, override=override, show_player=show_player)
        image = pixels(scene)
        self.timings.append((time.perf_counter() - start) * 1000)
        assert grid_identity(q.fog_grid) == before, 'Rendering edited the CPU fog map'
        assert (q.state, q.elapsed, q.revealed) == logical
        if q.world_blend == 0.:
            unexpected = [name for name in draws if name.startswith('canal_') and name != 'canal_annulus']
            assert not unexpected, ('Village rendered without exploration', unexpected)
        if 0. < q.world_blend < 1.:
            old = texture_pixels(scene.blend_old_frame.texture).astype(float)
            new = texture_pixels(scene.blend_new_frame.texture).astype(float)
            mixture, _ = delta_report(image, old * (1 - q.world_blend) + new * q.world_blend)
            self.composition_peaks.append(mixture['peak'])
            assert mixture['peak'] < 2., mixture
        if audit:
            self.check_passes(passes)
            self.audit_count += 1
        if label:
            save_image(self.out / (label + '.png'), image)
        return image, passes

    def check_passes(self, passes):
        grid = self.q.fog_grid
        for world, weight in self.scene.last_world_weights.items():
            pair = [p for p in passes if p['world'] == world]
            assert len(pair) == (2 if weight > 0 else 0), (world, passes)
            if not pair:
                continue
            assert [p['reflected'] for p in pair] == [True, False]
            a, b = copy.deepcopy(pair)
            assert a['uniforms'].pop('reflectedView') == (1.,)
            assert b['uniforms'].pop('reflectedView') == (0.,)
            assert a['uniforms'] == b['uniforms'], 'Reflected and direct fog fields diverged'
            a['textures'].pop('depthMap')
            b['textures'].pop('depthMap')
            assert a['textures'] == b['textures'], 'Reflections received a different fog map'
            assert 'fogGrid' in a['textures'] and a['textures']['fogGrid'] > 0
            assert np.allclose(a['uniforms']['fogGridBounds'], grid.bounds)
            assert np.allclose(a['uniforms']['fogGridTexel'], (1 / grid.width, 1 / grid.height))
            assert a['uniforms']['fogGridActive'] == (1.,)
            assert np.isclose(a['uniforms']['waterY'][0], -1.55 if world == 'canals' else 0.)

    def check_texture(self):
        texture = self.scene.fog_grid_texture
        image = pr.load_image_from_texture(texture)
        try:
            actual = bytes(pr.ffi.buffer(image.data, image.width * image.height * 4))
            assert (image.width, image.height) == (self.q.fog_grid.width, self.q.fog_grid.height)
            assert actual == grid_bytes(self.q.fog_grid), 'GPU fog texture is stale or vertically flipped'
        finally:
            pr.unload_image(image)

    def visible(self, label):
        image, passes = self.render(label, audit=True)
        view = self.scene.last_camera
        hidden, _ = self.render(override=view, show_player=False)
        count = int((np.max(np.abs(image.astype(float) - hidden.astype(float)), axis=2) > 3).sum())
        self.visibility.append({'label': label, 'pixels': count, 'shot': self.scene.last_shot})
        assert count > 25, ('Actor hidden', label, count, state(self.q))
        return image, passes

    def walk(self, points, label, inspect_every_station=True):
        records = []
        for index, (x, z) in enumerate(points):
            for _ in range(3000):
                e = self.actor
                dx, dz = x - e.x, z - e.z
                distance = math.hypot(dx, dz)
                if distance < 1e-6:
                    break
                dt = min(.04, distance / 1.55)
                e.yaw = math.atan2(dx, -dz)
                previous = grid_array(self.q.fog_grid)[:, :, 0]
                assert e.tick(dt, 1.) > 1e-8, ('Blocked actual route', label, index, x, z, e.x, e.z)
                self.q.tick(dt, e)
                self.audio.drain(self.q)
                self.clock += dt
                self.steps += 1
                self.path.append((e.x, e.z))
                assert np.all(grid_array(self.q.fog_grid)[:, :, 0] >= previous), 'Visited area refogged'
                if self.steps % 3 == 0:
                    image, _ = self.render(audit=self.steps % 15 == 0)
                    assert self.q.locked_camera is None, 'Camera remained locked during walking'
                    if not self.quick:
                        self.frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
            else:
                raise AssertionError(('Route timeout', label, index))
            if inspect_every_station:
                self.visible('%s-%02d' % (label, index))
            records.append({'position': [self.actor.x, self.actor.height, self.actor.z], **state(self.q)})
        return records

    def map(self, label, probes):
        grid = self.q.fog_grid
        rgba = grid_array(grid)
        save_image(self.out / (label + '-rgba.png'), rgba)
        for channel, name in enumerate(('clearance', 'arrival-lag', 'resistance')):
            Image.fromarray(rgba[:, :, channel]).resize((576, 576), Image.Resampling.NEAREST).save(
                self.out / (label + '-' + name + '.png'))
        image = Image.fromarray(rgba[:, :, 0]).convert('RGB').resize((768, 768), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(image)
        min_x, min_z, max_x, max_z = grid.bounds
        def pixel(p):
            return ((p[0] - min_x) / (max_x - min_x) * 768,
                    (p[1] - min_z) / (max_z - min_z) * 768)
        for house in self.scene.canals_manifest['houses']:
            floor_y = min(p[1] for p in house['bounds_corners'])
            corners = [(p[0], p[2]) for p in house['bounds_corners'] if abs(p[1] - floor_y) < .01]
            centre = tuple(sum(p[i] for p in corners) / len(corners) for i in range(2))
            corners.sort(key=lambda p: math.atan2(p[1] - centre[1], p[0] - centre[0]))
            draw.polygon([pixel(p) for p in corners], outline=(92, 112, 120))
        if len(self.path) > 1:
            draw.line([pixel(p) for p in self.path], fill=(220, 161, 69), width=3)
        for name, point in probes.items():
            x, y = pixel(point)
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(222, 83, 85))
            draw.text((x + 7, y + 2), name, fill=(230, 200, 193))
        draw.text((10, 10), 'R: visited clearance. Row 0 = minimum world Z.', fill=(234, 234, 234))
        image.save(self.out / (label + '-map.png'))

    def close(self):
        self.scene.close()
        self.audio.close()


def run(label='after', quick=False):
    out = BASE / label
    out.mkdir(parents=True, exist_ok=True)
    baseline = protected_hashes()
    protected_sources = hashes(MOON_AND_METADATA)
    production = hashes(PRODUCTION)
    for name in PRODUCTION:
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(WIDTH, HEIGHT, 'Muted Canals spatial fog review')
    review = None
    try:
        review = Review(out, quick)
        idle_reports = []
        for name, settings in VIEWS:
            view = camera(*settings) if settings else None
            signature = review.begin(view)
            initial = grid_identity(review.q.fog_grid)
            stationary_frames, samples = [], []
            timeline = (0., 1., 2., 5., 15., 30., 60.) if quick else sorted(
                set(np.arange(0., 30.001, .2).tolist() + [5., 15., 30., 60.]))
            previous = 0.
            for t in timeline:
                review.tick(t - previous)
                previous = t
                image, _ = review.render(audit=t in (5., 30., 60.))
                assert grid_identity(review.q.fog_grid) == initial, 'Idle arrival edited visited fog'
                assert review.q.world_blend == 0.
                assert camera_signature(review.scene.last_camera) == signature
                if t in (0., 1., 2., 5., 15., 30., 60.):
                    save_image(out / ('%s-idle-%02d.png' % (name, t)), image)
                    samples.append({'seconds': t, **state(review.q)})
                if not quick and t <= 30:
                    stationary_frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
            assert not review.q.movement_locked
            review.visible(name + '-settled-player')
            unlock = []
            for cloud_clock in (40., 87., 140., 219.):
                pair = []
                for elapsed in (ENTRY_DURATION - .001, ENTRY_DURATION + .001):
                    review.q.elapsed = elapsed
                    review.q.state = 'entering' if elapsed < ENTRY_DURATION else 'canals'
                    review.q.revealed = elapsed >= ENTRY_DURATION
                    image, _ = review.render(clock=cloud_clock, audit=True)
                    pair.append(image)
                difference, _ = delta_report(*pair)
                assert difference['peak'] < 8, difference
                unlock.append(difference)
            if stationary_frames:
                stationary_frames[0].save(
                    out / (name + '-stationary-arrival.gif'), save_all=True,
                    append_images=stationary_frames[1:], duration=200, loop=0, optimize=False)
            idle_reports.append({'view': name, 'samples': samples, 'unlock': unlock})
            print('Stationary grid checks passed:', name, flush=True)

        # Walk beyond this house before returning to it: furthest-radius logic
        # remains constant throughout the later sideways interior excursion.
        review.begin()
        review.tick(ENTRY_DURATION)
        quay_records = review.walk(REVIEW_ROUTE[1:8], 'quay')
        assert review.q.world_blend == 1.
        house_route = next(r for r in THROUGH_HOUSE_ROUTES if r['seed'] == 110)
        half = len(house_route['points']) // 2 + 1
        lateral_points = house_route['points'][:half]
        review.walk((REVIEW_ROUTE[6], REVIEW_ROUTE[5], lateral_points[0]), 'return-to-house')
        review.tick(max(0., FOG_ARRIVAL_DURATION - review.q.elapsed))
        before_grid = copy.deepcopy(review.q.fog_grid)
        reached = review.q.exploration.furthest_distance
        target = min(lateral_points[4:], key=lambda p: before_grid.sample(*p))
        opposite_house = next(h for h in review.scene.canals_manifest['houses'] if h['id'] == 'house-2377')
        opposite = (opposite_house['center'][0], opposite_house['center'][2])
        probes = {'rear-house-target': target, 'untouched-opposite': opposite}
        assert before_grid.sample(*target) < .95, ('Lateral target already fully visited', target)
        assert before_grid.sample(*opposite) == 0.
        review.map('before-house', probes)
        local_records = review.walk(lateral_points[1:], 'through-house')
        assert review.q.exploration.furthest_distance == reached, 'Lateral test accidentally advanced radial reveal'
        after_grid = review.q.fog_grid
        assert after_grid.sample(*target) > before_grid.sample(*target) + .02
        assert after_grid.sample(*target) > .95
        assert after_grid.sample(*opposite) == 0., 'Unvisited opposite district cleared'
        assert after_grid.clear_fraction > before_grid.clear_fraction
        review.map('after-house', probes)
        review.check_texture()

        # Hold camera, actor position, time, endpoint and geometry constant.
        # Only the persisted visited-cell map differs in these comparison pairs.
        comparisons = []
        unvisited_grid = CanalSequence().fog_grid
        fixed_views = (
            ('inside', camera((-9.3, DECK + 2.0, 14.1), (-5.4, DECK + 1.1, 16.3), 72)),
            ('outside', camera((1.8, 3.6, 17.), (-7.3, 1.7, 16.1), 71)),
            ('opposite', camera((24., 3.1, 17.), tuple(opposite_house['center'][i] + (1.5 if i == 1 else 0.) for i in range(3)), 67)),
        )
        for name, view in fixed_views:
            frames = {}
            for stage, grid in (('unvisited', unvisited_grid), ('quay-only', before_grid), ('visited', after_grid)):
                with patch.object(review.q, 'fog_grid', grid):
                    image, _ = review.render('comparison-' + name + '-' + stage,
                                             override=view, show_player=False, audit=True, clock=120.)
                    frames[stage] = image
            whole, _ = delta_report(frames['unvisited'], frames['visited'])
            lateral, _ = delta_report(frames['quay-only'], frames['visited'])
            comparisons.append({'view': name, 'unvisited_to_visited': whole, 'lateral_only': lateral})
        assert comparisons[0]['unvisited_to_visited']['mean'] > .1, 'House image did not respond to its changed fog map'

        held_grid = grid_identity(review.q.fog_grid)
        review.tick(60., turn=True)
        assert grid_identity(review.q.fog_grid) == held_grid, 'Turning in place painted the field'
        backtrack = review.walk(house_route['points'][half:], 'backtrack')
        assert review.q.fog_grid.sample(*target) >= after_grid.sample(*target)
        assert review.q.fog_grid.sample(*opposite) == 0.
        review.map('final', probes)
        if review.frames:
            review.frames[0].save(out / 'quay-and-house-walk.gif', save_all=True,
                                  append_images=review.frames[1:], duration=120, loop=0, optimize=False)
        assert hashes(PRODUCTION) == production, 'Production code changed during native review'
        assert hashes(MOON_AND_METADATA) == protected_sources
        assert protected_hashes() == baseline
        assert not review.audio.opened
        report = {
            'status': 'passed', 'stationary': idle_reports,
            'quay': quay_records, 'lateral': local_records, 'backtrack': backtrack,
            'lateral_target': target, 'target_before': before_grid.sample(*target),
            'target_after': after_grid.sample(*target),
            'opposite_house': opposite_house['id'], 'opposite_clearance': after_grid.sample(*opposite),
            'lateral_radial_handoff_unchanged_at': reached,
            'same_camera_comparisons': comparisons,
            'shader_pass_audits': review.audit_count,
            'endpoint_composition_peak': max(review.composition_peaks, default=0.),
            'visibility': review.visibility, 'actual_controller_steps': review.steps,
            'render_readback_ms': {'median': float(np.median(review.timings)), 'p95': float(np.percentile(review.timings, 95))},
            'production_sha256': production, 'protected_sources_sha256': protected_sources,
            'protected_scenes': baseline,
            'audio_muted': review.audio.muted, 'audio_device_opened': review.audio.opened,
            'windows_hidden': True,
        }
        save_json(out / 'report.json', report)
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if review:
            review.close()
        pr.close_window()


def continuity_only(label='after'):
    """Isolate one walked frame's field edit from pose, camera, time and world."""
    out = BASE / label
    out.mkdir(parents=True, exist_ok=True)
    production = hashes(PRODUCTION)
    protected = protected_hashes()
    preserved = hashes(MOON_AND_METADATA)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(WIDTH, HEIGHT, 'Muted Canals field continuity')
    review = None
    try:
        review = Review(out, quick=True)
        review.begin()
        review.tick(ENTRY_DURATION)
        house = next(r for r in THROUGH_HOUSE_ROUTES if r['seed'] == 110)
        points = house['points'][:len(house['points']) // 2 + 1]
        route = tuple(REVIEW_ROUTE[1:8]) + (REVIEW_ROUTE[6], REVIEW_ROUTE[5]) + tuple(points)
        samples = []
        worst = -1.
        for x, z in route:
            for _ in range(3000):
                e, q = review.actor, review.q
                dx, dz = x - e.x, z - e.z
                distance = math.hypot(dx, dz)
                if distance < 1e-6:
                    break
                measured = q.world_blend == 1. and review.steps % 20 == 0
                before = copy.deepcopy(q.fog_grid) if measured else None
                dt = min(.04, distance / 1.55)
                e.yaw = math.atan2(dx, -dz)
                assert e.tick(dt, 1.) > 1e-8
                q.tick(dt, e)
                review.audio.drain(q)
                review.clock += dt
                review.steps += 1
                if not measured:
                    continue
                current, _ = review.render(show_player=False, audit=True)
                view = review.scene.last_camera
                with patch.object(q, 'fog_grid', before):
                    previous, _ = review.render(override=view, show_player=False, audit=True)
                difference, delta = delta_report(previous, current)
                cell_delta = grid_array(q.fog_grid)[:, :, 0].astype(int) - grid_array(before)[:, :, 0]
                assert np.all(cell_delta >= 0)
                record = {
                    'position': [e.x, e.height, e.z], 'dt': dt,
                    'distance': dt * 1.55, 'pixel_difference': difference,
                    'maximum_clearance_byte_change': int(cell_delta.max()),
                    'changed_cells': int(np.count_nonzero(cell_delta)),
                }
                samples.append(record)
                if difference['peak'] > worst:
                    worst = difference['peak']
                    save_image(out / 'field-step-before.png', previous)
                    save_image(out / 'field-step-after.png', current)
                    save_image(out / 'field-step-difference-x8.png', np.minimum(255, delta * 8))
                assert difference['mean'] < .5 and difference['p99'] < 3 and difference['peak'] < 12, record
            else:
                raise AssertionError(('Continuity route blocked', x, z))
        assert len(samples) >= 15
        assert hashes(PRODUCTION) == production
        assert protected_hashes() == protected and hashes(MOON_AND_METADATA) == preserved
        report = {
            'status': 'passed', 'samples': samples,
            'maximum_same_camera_field_step_peak': max(s['pixel_difference']['peak'] for s in samples),
            'maximum_same_camera_field_step_mean': max(s['pixel_difference']['mean'] for s in samples),
            'maximum_clearance_byte_change': max(s['maximum_clearance_byte_change'] for s in samples),
            'source_sha256': production, 'protected': protected,
            'audio_muted': review.audio.muted, 'audio_device_opened': review.audio.opened,
            'windows_hidden': True,
        }
        save_json(out / 'field-continuity.json', report)
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if review:
            review.close()
        pr.close_window()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='after')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--continuity-only', action='store_true')
    args = parser.parse_args()
    if args.continuity_only:
        continuity_only(args.label)
    else:
        run(args.label, args.quick)
