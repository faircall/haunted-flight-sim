"""Hidden, muted native review of incoming fog and uniform timed dissipation."""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import argparse
import hashlib
import json
import math
import os
import time

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

import numpy as np
from PIL import Image
import pyray as pr

from g_huxin_canals import DECK, camera_zone
from g_huxin_canals_layout import REVIEW_ROUTE, DOOR_ROUTES
from g_huxin_canals_sequence import (
    CanalSequence, ENTRY_DURATION, ENTRY_SWAP, FOG_ARRIVAL_DURATION,
    WORLD_BLEND_START, WORLD_BLEND_END, FOG_CLEAR_START, FOG_CLEAR_DURATION,
    SEQUENCE_DURATION,
)
from huxin_canals_audio import EncounterAudio
from huxin_canals_review import camera_signature, delta_report, pixels, protected_hashes, texture_pixels
from huxin_canals_viewer import Lake, Explorer, WIDTH, HEIGHT
from temple_interior_viewer import camera


ROOT = Path(__file__).parent
BASE = ROOT / 'artifacts' / 'huxin-canals-uniform-v11'
PRODUCTION = ('g_huxin_canals_sequence.py', 'huxin_canals_viewer.py', 'shaders/huxin_canals_post.fs')
GUARDS = (
    'g_huxin_moon_sequence.py', 'huxin_moon_viewer.py', 'shaders/huxin_moon_post.fs',
    'huxin_moon_review.py', 'huxin_moon_fog_review.py', 'test_huxin_moon_encounter.py',
    'art/temple/huxin_canals/origin_snapshot.json',
    'art/temple/huxin_canals_flooded/origin_snapshot.json',
    'art/temple/huxin_canals_flooded/frozen_snapshot.json',
)
VIEWS = (
    ('gameplay', None),
    ('reverse', ((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)),
)
SIZES = {pr.SHADER_UNIFORM_FLOAT: 1, pr.SHADER_UNIFORM_VEC2: 2,
         pr.SHADER_UNIFORM_VEC3: 3, pr.SHADER_UNIFORM_VEC4: 4}


def hashes(paths):
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def save_image(path, value):
    Image.fromarray(np.asarray(value, dtype=np.uint8)).save(path)


def phase(q, elapsed):
    q.elapsed = min(SEQUENCE_DURATION, elapsed)
    q.state = 'entering' if elapsed < ENTRY_DURATION else 'canals'
    q.revealed = elapsed >= ENTRY_SWAP


def state(q):
    return {'elapsed': q.elapsed, 'state': q.state, 'locked': q.movement_locked,
            'arrival': q.fog_arrival, 'depth': q.fog_depth, 'blend': q.world_blend,
            'clearing': q.fog_clear, 'grade': q.void_tone}


class TimedReview:
    def __init__(self, scene, actor, audio, out, quick=False):
        self.scene, self.actor, self.audio = scene, actor, audio
        self.out, self.quick = out, quick
        self.clock = 40.
        self.timings, self.mixture_peaks, self.visibility = [], [], []
        self.steps = self.uniform_audits = 0
        self.walk_frames = []

    @property
    def q(self):
        return self.scene.sequence

    def begin(self, view=None):
        e = self.actor
        e.encounter = self.scene.sequence = CanalSequence()
        e.x, e.height, e.z = 1.65, DECK, 1.65
        e.yaw = e.phase = 0.
        e.clip = 'idle'
        e.shot = camera_zone(e.x, e.z)
        self.q.tick(.01, e)
        self.clock = 40.
        self.scene.player.pose('idle', 0., None)
        self.scene.render(e, self.clock, override=view)
        signature = camera_signature(self.scene.last_camera)
        assert self.q.activate(e)
        self.audio.drain(self.q)
        return signature

    def tick(self, duration):
        remaining = duration
        while remaining > 1e-8:
            dt = min(1 / 60, remaining)
            if not self.q.movement_locked:
                self.actor.tick(dt, 0.)
            self.q.tick(dt, self.actor)
            self.audio.drain(self.q)
            self.clock += dt
            remaining -= dt

    def render(self, label=None, view=None, player=True, clock=None, audit=False):
        scene, q = self.scene, self.q
        before = state(q)
        t = self.clock if clock is None else clock
        passes, active, locations = [], [], {}
        original_mist = scene.mist_pass
        original_location = pr.get_shader_location
        original_uniform = pr.set_shader_value
        original_texture = pr.set_shader_value_texture

        def locate(shader, name):
            location = original_location(shader, name)
            if shader.id == scene.post.id and location >= 0:
                locations[location] = name
            return location

        def uniform(shader, location, value, kind):
            if active and shader.id == scene.post.id and location in locations:
                active[-1]['uniforms'][locations[location]] = tuple(float(value[i]) for i in range(SIZES[kind]))
            return original_uniform(shader, location, value, kind)

        def texture(shader, location, value):
            if active and shader.id == scene.post.id and location in locations:
                active[-1]['textures'][locations[location]] = int(value.id)
            return original_texture(shader, location, value)

        def mist(*args, **kwargs):
            reflected = kwargs.get('reflected', args[6] if len(args) > 6 else False)
            record = {'endpoint': bool(scene.render_revealed), 'reflected': bool(reflected),
                      'uniforms': {}, 'textures': {}}
            active.append(record)
            try:
                return original_mist(*args, **kwargs)
            finally:
                active.pop()
                passes.append(record)

        start = time.perf_counter()
        with ExitStack() as stack:
            if audit:
                stack.enter_context(patch.object(scene, 'mist_pass', side_effect=mist))
                stack.enter_context(patch.object(pr, 'get_shader_location', side_effect=locate))
                stack.enter_context(patch.object(pr, 'set_shader_value', side_effect=uniform))
                stack.enter_context(patch.object(pr, 'set_shader_value_texture', side_effect=texture))
            scene.render(self.actor, t, override=view, show_player=player)
        image = pixels(scene)
        self.timings.append((time.perf_counter() - start) * 1000)
        assert state(q) == before, 'Rendering advanced or changed encounter state'
        if 0. < q.world_blend < 1.:
            old = texture_pixels(scene.blend_old_frame.texture).astype(float)
            new = texture_pixels(scene.blend_new_frame.texture).astype(float)
            difference, _ = delta_report(image, old * (1 - q.world_blend) + new * q.world_blend)
            assert difference['peak'] < 2., difference
            self.mixture_peaks.append(difference['peak'])
        if audit:
            for endpoint in (False, True):
                pair = [p for p in passes if p['endpoint'] == endpoint]
                if not pair:
                    continue
                assert [p['reflected'] for p in pair] == [True, False]
                a, b = pair
                assert a['uniforms'].pop('reflectedView') == (1.,)
                assert b['uniforms'].pop('reflectedView') == (0.,)
                assert a['uniforms'] == b['uniforms'], 'Direct/reflected global fog differs'
                assert np.isclose(a['uniforms']['clearing'][0], q.fog_clear)
                assert np.isclose(a['uniforms']['waterY'][0], -1.55 if endpoint else 0.)
                assert not ({'fogGrid', 'retreatRadius', 'concealRadius'} & set(a['uniforms']))
                assert 'fogGrid' not in a['textures'] and 'fogGrid' not in b['textures']
            self.uniform_audits += 1
        if label:
            save_image(self.out / (label + '.png'), image)
        return image

    def visible(self, label):
        image = self.render(label, audit=True)
        hidden = self.render(view=self.scene.last_camera, player=False)
        count = int((np.max(np.abs(image.astype(float) - hidden.astype(float)), axis=2) > 3).sum())
        record = {'label': label, 'pixels': count, 'shot': self.scene.last_shot, **state(self.q)}
        self.visibility.append(record)
        assert count > 25, ('Actor hidden', record)
        return image

    def concealment(self, view_name):
        """Force both complete endpoints with identical fog, pose and camera."""
        records = []
        for elapsed in (WORLD_BLEND_START, (WORLD_BLEND_START + WORLD_BLEND_END) / 2, WORLD_BLEND_END - .001):
            phase(self.q, elapsed)
            for cloud in (40., 87., 140., 219.):
                self.render(clock=cloud, audit=True)
                cam = self.scene.last_camera
                endpoint_frames, reflected, raw_reflected = [], [], []
                logical = state(self.q)
                for endpoint in (False, True):
                    self.scene._render_world(self.actor, cam, cloud, False, True, False,
                                             endpoint, self.scene.frame, False)
                    endpoint_frames.append(pixels(self.scene))
                    reflected.append(texture_pixels(self.scene.reflection.texture))
                    raw_reflected.append(texture_pixels(self.scene.reflection_raw.texture))
                assert state(self.q) == logical
                difference, delta = delta_report(*endpoint_frames)
                reflection, _ = delta_report(*reflected)
                raw, _ = delta_report(*raw_reflected)
                record = {'elapsed': elapsed, 'cloud_clock': cloud,
                          'final_image': difference, 'reflection_buffer': reflection,
                          'raw_reflection_buffer': raw}
                records.append(record)
                if cloud == 87.:
                    stem = '%s-hidden-endpoints-%05.2f' % (view_name, elapsed)
                    save_image(self.out / (stem + '-lake.png'), endpoint_frames[0])
                    save_image(self.out / (stem + '-canals.png'), endpoint_frames[1])
                    save_image(self.out / (stem + '-difference-x8.png'), np.minimum(255, delta * 8))
                save_json(self.out / (view_name + '-concealment.partial.json'), records)
                # The full player image includes visible water. Standalone
                # reflection RTs have differing mirror planes and are diagnostic.
                assert difference['peak'] < 8., record
        return records

    def walk(self, points, idle_reference, reference_actor, label):
        records = []
        for index, (x, z) in enumerate(points):
            for _ in range(3000):
                e = self.actor
                distance = math.hypot(x - e.x, z - e.z)
                if distance < 1e-6:
                    break
                assert not self.q.movement_locked
                dt = min(.04, distance / 1.55)
                e.yaw = math.atan2(x - e.x, -(z - e.z))
                assert e.tick(dt, 1.) > 1e-8, ('Route blocked', label, index, e.x, e.z)
                self.q.tick(dt, e)
                idle_reference.tick(dt, reference_actor)
                self.audio.drain(self.q)
                self.clock += dt
                self.steps += 1
                assert np.isclose(self.q.fog_clear, idle_reference.fog_clear, atol=1e-12)
                assert np.isclose(self.q.world_blend, idle_reference.world_blend, atol=1e-12)
                if self.steps % 3 == 0:
                    image = self.render(audit=self.steps % 15 == 0)
                    assert self.q.locked_camera is None
                    if self.q.elapsed <= ENTRY_DURATION + 8.:
                        hidden = self.render(view=self.scene.last_camera, player=False)
                        count = int((np.max(np.abs(image.astype(float) - hidden.astype(float)), axis=2) > 3).sum())
                        record = {'label': 'early-walk-frame-%04d' % self.steps,
                                  'pixels': count, 'shot': self.scene.last_shot,
                                  'position': [e.x, e.height, e.z], **state(self.q)}
                        self.visibility.append(record)
                        if count <= 25:
                            save_image(self.out / (record['label'] + '.png'), image)
                            raise AssertionError(('Actor hidden between movement stations', record))
                    if not self.quick:
                        self.walk_frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
            else:
                raise AssertionError(('Route timeout', label, index))
            self.visible('%s-%02d' % (label, index))
            records.append({'position': [self.actor.x, self.actor.height, self.actor.z], **state(self.q)})
        return records


def review_scene(scene, actor, audio, startup=0., quick=False, out=None):
    out = Path(out) if out else BASE / 'after'
    out.mkdir(parents=True, exist_ok=True)
    production = hashes(PRODUCTION)
    preserved = hashes(GUARDS)
    baseline = protected_hashes()
    for name in PRODUCTION:
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    review = TimedReview(scene, actor, audio, out, quick)
    view_reports = []
    capture_times = (0., 2., 5., 8., 12., 14., 16., 18., 24., 30., 42., 54., 66., SEQUENCE_DURATION)
    for name, settings in VIEWS:
        held = review.begin(camera(*settings) if settings else None)
        pose = (actor.x, actor.height, actor.z, actor.yaw)
        frames, samples = [], []
        timeline = capture_times if quick else sorted(set(np.arange(0., SEQUENCE_DURATION + .001, .2).tolist() + list(capture_times)))
        previous, last_clear = 0., 0.
        for t in timeline:
            review.tick(t - previous)
            previous = t
            image = review.render(audit=t in capture_times)
            assert (actor.x, actor.height, actor.z, actor.yaw) == pose
            assert camera_signature(scene.last_camera) == held
            assert review.q.fog_clear >= last_clear
            last_clear = review.q.fog_clear
            if t < WORLD_BLEND_START:
                assert review.q.world_blend == 0.
            if t >= WORLD_BLEND_END + .001:
                assert review.q.world_blend == 1.
            if t <= FOG_CLEAR_START:
                assert review.q.fog_clear == 0.
            if t in capture_times:
                save_image(out / ('%s-stationary-%02d.png' % (name, t)), image)
                samples.append({'seconds': t, **state(review.q)})
            if not quick:
                frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
        assert np.isclose(review.q.fog_clear, 1.)
        review.visible(name + '-stationary-final-player')
        concealment = review.concealment(name)
        boundaries = []
        for boundary in (WORLD_BLEND_START, ENTRY_DURATION, FOG_CLEAR_START, SEQUENCE_DURATION):
            pair = []
            for elapsed in (boundary - .001, boundary + .001):
                phase(review.q, elapsed)
                pair.append(review.render(clock=87., audit=True))
            difference, delta = delta_report(*pair)
            boundaries.append({'seconds': boundary, 'difference': difference})
            assert difference['peak'] < 8, boundaries[-1]
            save_image(out / ('%s-boundary-%02d-x8.png' % (name, boundary)), np.minimum(255, delta * 8))
        if frames:
            frames[0].save(out / (name + '-timed-reveal.gif'), save_all=True,
                           append_images=frames[1:], duration=200, loop=0, optimize=False)
        view_reports.append({'name': name, 'samples': samples, 'concealment': concealment,
                             'boundaries': boundaries})
        save_json(out / 'stationary-report.partial.json', view_reports)
        print('Timed stationary review passed:', name, flush=True)

    # The same clock advances for a stationary control and an actual walker.
    review.begin()
    review.tick(ENTRY_DURATION)
    reference_actor = Explorer()
    reference_actor.x, reference_actor.height, reference_actor.z = 1.65, DECK, 1.65
    idle_reference = CanalSequence()
    idle_reference.tick(.01, reference_actor)
    assert idle_reference.activate(reference_actor)
    idle_reference.tick(ENTRY_DURATION, reference_actor)
    assert not review.q.movement_locked and review.q.fog_clear == 0.
    route = review.walk(REVIEW_ROUTE[1:6], idle_reference, reference_actor, 'walk-after-unlock')
    # Stopping the walker does not pause the global dissipation.
    before_pause = review.q.fog_clear
    review.tick(10.)
    idle_reference.tick(10., reference_actor)
    assert review.q.fog_clear > before_pause
    assert np.isclose(review.q.fog_clear, idle_reference.fog_clear, atol=1e-12)
    review.visible('paused-walking-fog-still-clears')
    house = next(r for r in DOOR_ROUTES if r['seed'] == 110 and r['bay'] == 1)
    interior_route = review.walk(house['points'][:5], idle_reference, reference_actor, 'enter-house')
    interior_before = review.visible('interior-during-clearing')
    review.tick(max(0., SEQUENCE_DURATION - review.q.elapsed))
    interior_after = review.visible('interior-after-clearing')
    # Match camera and cloud clock to isolate the global fog factor.
    view = scene.last_camera
    pair = []
    for elapsed in (FOG_CLEAR_START, SEQUENCE_DURATION):
        phase(review.q, elapsed)
        pair.append(review.render('interior-fixed-%02d' % elapsed, view=view, player=False, clock=120., audit=True))
    interior_difference, _ = delta_report(*pair)
    assert interior_difference['mean'] > .1, interior_difference
    review.render('district-after-clearing', view=camera((1.2, 3.3, 19.8), (-1., 2.7, 42.), 66), player=False, audit=True)
    if review.walk_frames:
        review.walk_frames[0].save(out / 'walk-during-clearing.gif', save_all=True,
                                  append_images=review.walk_frames[1:], duration=120, loop=0, optimize=False)
    assert hashes(PRODUCTION) == production
    assert hashes(GUARDS) == preserved and protected_hashes() == baseline
    assert not audio.opened
    report = {
        'status': 'passed', 'views': view_reports, 'walk_after_unlock': route,
        'interior_route': interior_route, 'walking_and_stationary_fade_equal': True,
        'stopping_walking_does_not_stop_clearing': True,
        'interior_fixed_clock_difference': interior_difference,
        'visibility': review.visibility, 'controller_steps': review.steps,
        'uniform_parity_audits': review.uniform_audits,
        'composition_peak': max(review.mixture_peaks, default=0.),
        'source_sha256': production, 'protected_sources_sha256': preserved,
        'protected_scenes': baseline, 'startup_seconds': startup,
        'render_readback_ms': {'median': float(np.median(review.timings)), 'p95': float(np.percentile(review.timings, 95))},
        'audio_muted': audio.muted, 'audio_device_opened': audio.opened, 'windows_hidden': True,
    }
    save_json(out / 'report.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def run(label='after', quick=False):
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(WIDTH, HEIGHT, 'Muted Canals uniform timed fog review')
    scene = audio = None
    try:
        start = time.perf_counter()
        scene = Lake()
        actor = Explorer()
        actor.encounter = scene.sequence
        audio = EncounterAudio(True)
        review_scene(scene, actor, audio, time.perf_counter() - start, quick, BASE / label)
    finally:
        if scene:
            scene.close()
        if audio:
            audio.close()
        pr.close_window()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='after')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    run(args.label, args.quick)
