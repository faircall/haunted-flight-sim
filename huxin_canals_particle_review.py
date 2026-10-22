"""Hidden, muted native review of growing and dissipating puzzle-fog waves."""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch, PropertyMock
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

import numpy as np
from PIL import Image, ImageDraw
import pyray as pr

from g_huxin_canals import DECK, camera_zone
from g_huxin_canals_layout import REVIEW_ROUTE, DOOR_ROUTES
from g_huxin_canals_sequence import (
    CanalSequence, ENTRY_DURATION, ENTRY_SWAP, FOG_ARRIVAL_DURATION,
    WORLD_BLEND_START, WORLD_BLEND_END, FOG_CLEAR_START, FOG_CLEAR_DURATION,
    SEQUENCE_DURATION,
)
from g_huxin_canals_particles import (NEAR_CLEAR_END, MIDDLE_CLEAR_START, MIDDLE_CLEAR_END,
                                     FAR_CLEAR_START, FAR_CLEAR_END)
from huxin_canals_audio import EncounterAudio
from huxin_canals_review import camera_signature, delta_report, pixels, protected_hashes, texture_pixels
from huxin_canals_viewer import Lake, Explorer, WIDTH, HEIGHT, draw_puzzle_timer
from temple_interior_viewer import camera


ROOT = Path(__file__).parent
BASE = ROOT / 'artifacts' / 'huxin-canals-smooth-v17'
PRODUCTION = ('g_huxin_canals_sequence.py', 'huxin_canals_viewer.py', 'shaders/huxin_canals_post.fs',
              'g_huxin_canals_particles.py', 'huxin_canals_particles.py',
              'shaders/huxin_canals_particles.vs', 'shaders/huxin_canals_particles.fs')
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


def layer_pixels(scene):
    layer = pr.load_image_from_texture(scene.puzzle_fog.target.texture)
    try:
        pr.image_flip_vertical(layer)
        pr.image_format(layer, pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
        return np.frombuffer(pr.ffi.buffer(layer.data, layer.width * layer.height * 4),
                             dtype=np.uint8).reshape(layer.height, layer.width, 4).copy()
    finally:
        pr.unload_image(layer)


def phase(q, elapsed):
    q.elapsed = min(SEQUENCE_DURATION, elapsed)
    q.state = 'entering' if elapsed < ENTRY_DURATION else 'canals'
    q.revealed = elapsed >= ENTRY_SWAP


def state(q):
    return {'elapsed': q.elapsed, 'state': q.state, 'locked': q.movement_locked,
            'arrival': q.fog_arrival, 'depth': q.fog_depth, 'blend': q.world_blend,
            'clearing': q.fog_clear, 'grade': q.void_tone}


class ParticleReview:
    def __init__(self, scene, actor, audio, out, quick=False):
        self.scene, self.actor, self.audio = scene, actor, audio
        self.out, self.quick = out, quick
        self.clock = 40.
        self.timings, self.mixture_peaks, self.visibility = [], [], []
        self.steps = self.uniform_audits = 0
        self.walk_frames = []
        self.concealment_failures = []
        self.visibility_failures = []
        self.particle_audits = []

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
        original_particles = scene.puzzle_fog.render
        particle_passes = []

        def particles(source, cam, sequence, clock, colour, water_y, reflected=False):
            result = original_particles(source, cam, sequence, clock, colour, water_y, reflected)
            particle_passes.append({'reflected': reflected, 'water_y': water_y,
                                   'depth': int(source.depth.id), 'texture': int(result.id),
                                   'count': scene.puzzle_fog.last_count,
                                   'drawn': scene.puzzle_fog.last_draw_count,
                                   'signature': scene.puzzle_fog.last_signature})
            return result

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
                stack.enter_context(patch.object(scene.puzzle_fog, 'render', side_effect=particles))
            scene.render(self.actor, t, override=view, show_player=player)
        image = pixels(scene)
        self.timings.append((time.perf_counter() - start) * 1000)
        assert state(q) == before, 'Rendering advanced or changed encounter state'
        assert scene.last_world_weights == {'lake': 1. - q.world_blend, 'canals': q.world_blend}
        if 0. < q.world_blend < 1.:
            old = texture_pixels(scene.blend_old_frame.texture).astype(float)
            new = texture_pixels(scene.blend_new_frame.texture).astype(float)
            difference, _ = delta_report(image, old * (1. - q.world_blend) + new * q.world_blend)
            assert difference['peak'] < 2., difference
            self.mixture_peaks.append(difference['peak'])
        if audit:
            expected = [False, False, True, True] if 0. < q.world_blend < 1. else [bool(q.world_blend)] * 2
            assert [p['endpoint'] for p in passes] == expected
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
            assert len(particle_passes) == len(passes)
            assert all(p['signature'] == particle_passes[0]['signature'] for p in particle_passes)
            if q.elapsed <= 0. or q.elapsed >= SEQUENCE_DURATION:
                assert all(p['count'] == p['drawn'] == 0 for p in particle_passes)
            elif q.elapsed == FOG_ARRIVAL_DURATION:
                assert all(p['count'] > 0 for p in particle_passes)
            for mist_record, packet in zip(passes, particle_passes):
                assert mist_record['reflected'] == packet['reflected']
                assert mist_record['textures']['particleMap'] == packet['texture']
                assert mist_record['textures']['depthMap'] == packet['depth']
                assert packet['water_y'] == (-1.55 if mist_record['endpoint'] else 0.)
            self.particle_audits.append({'elapsed': q.elapsed, 'clock': t,
                                        'passes': [{k: v for k, v in p.items() if k != 'signature'} for p in particle_passes]})
        if label:
            save_image(self.out / (label + '.png'), image)
        return image

    def visible(self, label):
        image = self.render(label, audit=True)
        hidden = self.render(view=self.scene.last_camera, player=False)
        count = int((np.max(np.abs(image.astype(float) - hidden.astype(float)), axis=2) > 3).sum())
        record = {'label': label, 'pixels': count, 'shot': self.scene.last_shot, **state(self.q)}
        self.visibility.append(record)
        if count <= 25:
            self.visibility_failures.append(record)
            if not self.quick:
                raise AssertionError(('Actor hidden', record))
        return image

    def concealment(self, view_name):
        """Force both complete endpoints with identical fog, pose and camera."""
        records = []
        for elapsed in (WORLD_BLEND_START, (WORLD_BLEND_START + WORLD_BLEND_END) / 2., WORLD_BLEND_END):
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
                scalar = np.max(delta, axis=2)
                y, x = np.unravel_index(np.argmax(scalar), scalar.shape)
                record['largest_difference_xy'] = [int(x), int(y)]
                record['pixels_over_7'] = int((scalar >= 8).sum())
                records.append(record)
                if cloud == 87.:
                    stem = '%s-hidden-endpoints-%05.2f' % (view_name, elapsed)
                    save_image(self.out / (stem + '-lake.png'), endpoint_frames[0])
                    save_image(self.out / (stem + '-canals.png'), endpoint_frames[1])
                    save_image(self.out / (stem + '-difference-x8.png'), np.minimum(255, delta * 8))
                save_json(self.out / (view_name + '-concealment.partial.json'), records)
                # The full player image includes visible water. Standalone
                # reflection RTs have differing mirror planes and are diagnostic.
                if difference['peak'] >= 8.:
                    self.concealment_failures.append({'view': view_name, **record})
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
                            self.visibility_failures.append(record)
                            save_json(self.out / 'visibility-failures.partial.json', self.visibility_failures)
                            if not self.quick:
                                raise AssertionError(('Actor hidden between movement stations', record))
                    if not self.quick:
                        self.walk_frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
            else:
                raise AssertionError(('Route timeout', label, index))
            self.visible('%s-%02d' % (label, index))
            records.append({'position': [self.actor.x, self.actor.height, self.actor.z], **state(self.q)})
        return records

    def optics(self):
        """Side/oblique depth views and absolute-time particle drift."""
        records = []
        for name, settings in (
            ('low-side', ((8., 1.3, -8.), (0., 1.5, 0.), 70)),
            ('oblique', ((11., 6., 6.), (0., 1.5, 0.), 70)),
        ):
            cam = camera(*settings)
            for elapsed in (FOG_ARRIVAL_DURATION, NEAR_CLEAR_END, MIDDLE_CLEAR_END):
                phase(self.q, elapsed)
                self.scene._render_world(self.actor, cam, 87., False, True, False,
                                         True, self.scene.frame, False)
                save_image(self.out / ('%s-%02d.png' % (name, elapsed)), pixels(self.scene))
                Image.fromarray(layer_pixels(self.scene)).save(self.out / ('%s-particles-%02d.png' % (name, elapsed)))
        phase(self.q, FOG_ARRIVAL_DURATION)
        cam = camera((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)
        layers = []
        for clock in (87., 88., 87.):
            self.scene._render_world(self.actor, cam, clock, False, True, False,
                                     True, self.scene.frame, False)
            layers.append(layer_pixels(self.scene))
        drift, _ = delta_report(layers[0], layers[1])
        repeat, _ = delta_report(layers[0], layers[2])
        assert drift['mean'] > .005, drift
        assert repeat['peak'] == 0, repeat
        records.append({'particle_drift_one_second': drift, 'absolute_time_repeat': repeat})
        return records

    def ordinary_baseline(self):
        """Render three untriggered approach stations with the saved baseline shader."""
        old_path = BASE / 'before' / 'shaders' / 'huxin_canals_post.fs'
        if not old_path.exists():
            old_path = ROOT / 'artifacts' / 'huxin-canals-waves-v13' / 'final' / 'source' / 'shaders' / 'huxin_canals_post.fs'
            reference = json.loads((old_path.parents[2] / 'report.json').read_text())
            assert hashlib.sha256(old_path.read_bytes()).hexdigest() == reference['source_sha256']['shaders/huxin_canals_post.fs']
        old_shader = pr.load_shader(pr.ffi.NULL, str(old_path))
        assert old_shader.id != pr.rl.rlGetShaderIdDefault()
        pr.set_shader_value(old_shader, pr.get_shader_location(old_shader, 'resolution'),
                            pr.ffi.new('float[]', [WIDTH, HEIGHT]), pr.SHADER_UNIFORM_VEC2)
        current_shader = self.scene.post
        records = []
        try:
            for index, (x, z) in enumerate(((0., 21.), (0., 12.), (1.65, 1.65))):
                self.scene.sequence = self.actor.encounter = CanalSequence()
                self.actor.x, self.actor.height, self.actor.z = x, DECK, z
                self.actor.shot = camera_zone(x, z)
                self.actor.yaw = self.actor.phase = 0.
                self.actor.clip = 'idle'
                self.q.tick(.01, self.actor)
                pair = []
                for shader in (old_shader, current_shader):
                    self.scene.post = shader
                    pair.append(self.render(clock=87.))
                difference, _ = delta_report(*pair)
                record = {'position': [x, DECK, z], 'difference': difference}
                records.append(record)
                save_image(self.out / ('ordinary-before-%d.png' % index), pair[0])
                save_image(self.out / ('ordinary-after-%d.png' % index), pair[1])
                assert difference['peak'] <= 1., record
        finally:
            self.scene.post = current_shader
            pr.unload_shader(old_shader)
        return records

    def fade_isolation(self):
        """Measure assembled coverage with pose, camera and cloud clock fixed."""
        cam = camera((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)
        records = []
        previous = None
        for elapsed in (FOG_CLEAR_START, 10., NEAR_CLEAR_END, 18., MIDDLE_CLEAR_END,
                        28., FAR_CLEAR_END, 38., SEQUENCE_DURATION - .1, SEQUENCE_DURATION):
            phase(self.q, elapsed)
            self.scene._render_world(self.actor, cam, 87., False, True, False,
                                     True, self.scene.frame, False)
            layer = layer_pixels(self.scene)
            alpha = layer[:, :, 3].astype(float)
            if previous is not None:
                assert float((alpha - previous).max()) <= 1., ('Coverage increased during fade', elapsed)
            previous = alpha
            records.append({'seconds': elapsed, 'mean_alpha_255': float(alpha.mean()),
                            'nonzero_pixels': int((alpha > 0).sum()),
                            'live_particles': self.scene.puzzle_fog.last_count})
            save_image(self.out / ('fixed-clock-fade-%05.1f.png' % elapsed), pixels(self.scene))
        assert records[-1]['mean_alpha_255'] == 0.
        assert records[5]['mean_alpha_255'] < records[0]['mean_alpha_255'] * .8
        assert records[-3]['mean_alpha_255'] < records[0]['mean_alpha_255'] * .15
        return records

    def ambient_independence(self):
        """Ambient clearing cannot multiply the completed particle layer."""
        phase(self.q, FOG_ARRIVAL_DURATION)
        cam = camera((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)
        frames, layers = [], []
        for clearing in (0., 1.):
            with patch.object(type(self.q), 'fog_clear', new_callable=PropertyMock, return_value=clearing), \
                 patch.object(type(self.q), 'void_tone', new_callable=PropertyMock, return_value=0.):
                self.scene._render_world(self.actor, cam, 87., False, True, False,
                                         True, self.scene.frame, False)
                frames.append(pixels(self.scene))
                layers.append(layer_pixels(self.scene))
        assert np.array_equal(layers[0], layers[1]), 'Ambient progress changed particle lifecycle'
        opaque = layers[0][:, :, 3] == 255
        assert int(opaque.sum()) > 100, 'No opaque particle pixels to test independent composition'
        difference = np.abs(frames[0].astype(float) - frames[1].astype(float))[opaque]
        assert float(difference.max()) <= 1., ('Ambient clearing faded particles', difference.max())
        return {'opaque_pixels': int(opaque.sum()), 'maximum_difference_255': float(difference.max())}

    def depth_progression(self):
        """Authored distance bands expose overlapping local fade deadlines."""
        from g_huxin_canals_particles import particles_at, particle_schedule
        import huxin_canals_particles as renderer
        peak = {p.id: p for p in particles_at(FOG_ARRIVAL_DURATION, 87.)}
        schedule = {p.id: p for p in particle_schedule()}
        bands = {'near': set(), 'middle': set(), 'far': set()}
        for ident in peak:
            bands[schedule[ident].band].add(ident)
        starts = {}
        for name, ids in bands.items():
            values = [schedule[i].clear_start for i in ids]
            starts[name] = {'count': len(ids), 'first': min(values), 'last': max(values),
                            'median': float(np.median(values))}
        assert starts['near']['median'] < starts['middle']['median'] < starts['far']['median']
        cam = camera((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)
        samples = []
        deadlines = {'near': NEAR_CLEAR_END, 'middle': MIDDLE_CLEAR_END, 'far': FAR_CLEAR_END}
        for elapsed in (FOG_CLEAR_START, 10., MIDDLE_CLEAR_START, NEAR_CLEAR_END, 18.,
                        FAR_CLEAR_START, MIDDLE_CLEAR_END, 28., FAR_CLEAR_END, 38., SEQUENCE_DURATION):
            live = {p.id: p for p in particles_at(elapsed, 87.)}
            sample = {'seconds': elapsed, 'bands': {}}
            for name, ids in bands.items():
                alpha = [live[i].alpha / peak[i].alpha if i in live else 0. for i in ids]
                sample['bands'][name] = {'mean_remaining_alpha': float(np.mean(alpha)),
                                        'median_remaining_alpha': float(np.median(alpha)),
                                        'maximum_remaining_alpha': max(alpha),
                                        'remaining_particles': len(ids & live.keys())}
                if elapsed >= deadlines[name]:
                    assert max(alpha) <= .01, ('Band missed its fade deadline', name, elapsed, max(alpha))
                if elapsed in (FOG_CLEAR_START, NEAR_CLEAR_END, MIDDLE_CLEAR_END, FAR_CLEAR_END, 38.):
                    phase(self.q, elapsed)
                    def subset(t, clock, allowed=ids):
                        return tuple(p for p in particles_at(t, clock) if p.id in allowed)
                    with patch.object(renderer, 'particles_at', side_effect=subset):
                        self.scene._render_world(self.actor, cam, 87., False, True, False,
                                                 True, self.scene.frame, False)
                        layer = layer_pixels(self.scene)
                    sample['bands'][name]['isolated_layer_mean_alpha_255'] = float(layer[:, :, 3].mean())
                    Image.fromarray(layer).save(self.out / ('depth-%s-%03d.png' % (name, elapsed)))
            if 10. <= elapsed <= MIDDLE_CLEAR_END:
                near, middle, far = (sample['bands'][n]['mean_remaining_alpha'] for n in ('near', 'middle', 'far'))
                assert near < middle <= far, ('Distant cards cleared before nearby cards', sample)
            samples.append(sample)
        report = {'radius_bands_metres': {'near': [0, 14], 'middle': [14, 35], 'far': [35, None]},
                  'onset': starts, 'samples': samples}
        save_json(self.out / 'near-first-depth-progression.json', report)
        return report

    def timer_captures(self):
        """Draw the production test HUD, separate from pixel-comparison frames."""
        pr.set_window_size(1280, 720)
        try:
            for elapsed in ((WORLD_BLEND_START + WORLD_BLEND_END) / 2.,
                            MIDDLE_CLEAR_START + .5, FAR_CLEAR_END + .5, SEQUENCE_DURATION):
                phase(self.q, elapsed)
                self.render(clock=40. + elapsed)
                pr.begin_drawing()
                try:
                    pr.clear_background(pr.BLACK)
                    pr.draw_texture_pro(self.scene.frame.texture,
                                        pr.Rectangle(0, 0, WIDTH, -HEIGHT),
                                        pr.Rectangle(0, 0, 1280, 720), pr.Vector2(0, 0), 0, pr.WHITE)
                    draw_puzzle_timer(self.q, 1280)
                    pr.rl.rlDrawRenderBatchActive()
                    screenshot = pr.load_image_from_screen()
                    try:
                        pr.export_image(screenshot, str(self.out / ('puzzle-timer-%04.1f.png' % elapsed)))
                    finally:
                        pr.unload_image(screenshot)
                finally:
                    pr.end_drawing()
        finally:
            pr.set_window_size(WIDTH, HEIGHT)

    def arrival_progression(self):
        """Measure actual overlapping-card opacity over fixed peak pixels."""
        import huxin_canals_particles as renderer
        reference = load_reference_particles()
        times = sorted({FOG_ARRIVAL_DURATION * fraction for fraction in
                        (0., .03125, .0625, .09375, .125, .1875, .25, .375, .5, .625, .75, .875, 1.)})
        report = []
        for name, settings in VIEWS:
            held = self.begin(camera(*settings) if settings else None)
            held_camera = self.scene.last_camera
            phase(self.q, FOG_ARRIVAL_DURATION)
            self.render(clock=87., view=held_camera, audit=True)
            peak = layer_pixels(self.scene)[:, :, 3].astype(float)
            mask = peak >= 16
            assert mask.sum() > 100
            denominator = peak[mask].sum()
            samples, thumbnails = [], []
            for elapsed in times:
                phase(self.q, elapsed)
                current = self.render(clock=87., view=held_camera, audit=True)
                assert camera_signature(self.scene.last_camera) == held
                current_layer = layer_pixels(self.scene)
                def old_packets(t, clock):
                    return reference.particles_at(t * reference.ARRIVAL_DURATION / FOG_ARRIVAL_DURATION, clock)
                with patch.object(renderer, 'particles_at', side_effect=old_packets):
                    before = self.render(clock=87., view=held_camera)
                    before_layer = layer_pixels(self.scene)
                values = {}
                for tag, frame, layer in (('current', current, current_layer), ('v16', before, before_layer)):
                    alpha = layer[:, :, 3].astype(float)
                    values[tag] = {
                        'coverage_relative_to_peak': float(alpha[mask].sum() / denominator),
                        'mean_alpha_255': float(alpha[mask].mean()),
                        'fraction_peak_mask_over_90pct_opacity': float((alpha[mask] >= 230).mean()),
                        'fraction_peak_mask_with_visible_fog': float((alpha[mask] > 0).mean()),
                    }
                    stem = '%s-arrival-%s-%06.3f' % (name, tag, elapsed)
                    save_image(self.out / (stem + '.png'), frame)
                    Image.fromarray(layer).save(self.out / (stem + '-layer.png'))
                thumbnails.append((elapsed, current))
                samples.append({'seconds': elapsed, **values})
            assert samples[0]['current']['coverage_relative_to_peak'] == 0.
            assert abs(samples[-1]['current']['coverage_relative_to_peak'] - 1.) < 1e-12
            sheet = Image.new('RGB', (4 * 320, 4 * 202), '#15191b')
            pen = ImageDraw.Draw(sheet)
            for index, (elapsed, frame) in enumerate(thumbnails):
                x, y = index % 4 * 320, index // 4 * 202
                sheet.paste(Image.fromarray(frame).resize((320, 180), Image.Resampling.NEAREST), (x, y + 22))
                ratio = samples[index]['current']['coverage_relative_to_peak']
                pen.text((x + 5, y + 5), '%5.3f s   peak coverage %.1f%%' % (elapsed, ratio * 100), fill='white')
            sheet.save(self.out / (name + '-arrival-contact.png'))
            report.append({'view': name, 'cloud_clock': 87., 'peak_mask_pixels': int(mask.sum()),
                           'peak_mask_threshold_255': 16, 'samples': samples})
        save_json(self.out / 'arrival-progression.json', report)
        return report

    def temporal_progression(self, baseline=False):
        """Real 30 fps pose, camera, endpoint and cloud motion through the crest."""
        import huxin_canals_particles as renderer
        results = []
        with ExitStack() as stack:
            if baseline:
                reference = load_reference_particles()
                with patch.dict(sys.modules, {'g_huxin_canals_particles': reference}):
                    module = load_python_source(BASE / 'before' / 'g_huxin_canals_sequence.py', '_v16_sequence')
                stack.enter_context(patch.dict(globals(), {'CanalSequence': module.CanalSequence}))
                stack.enter_context(patch.object(renderer, 'particles_at', side_effect=reference.particles_at))
            for name, settings in VIEWS:
                held = self.begin(camera(*settings) if settings else None)
                pose = (self.actor.x, self.actor.height, self.actor.z, self.actor.yaw)
                self.tick(3.)
                frames, records, landmarks, largest = [], [], [], []
                previous_image = previous_layer = previous_small = None
                for index in range(151):
                    if index:self.tick(1. / 30.)
                    elapsed = 3. + index / 30.
                    if 0. < self.q.world_blend < 1.:
                        direct_layers = []
                        original = self.scene.puzzle_fog.render
                        def read_direct_layer(*args, **kwargs):
                            texture = original(*args, **kwargs)
                            reflected = kwargs.get('reflected', args[6] if len(args) > 6 else False)
                            if not reflected:direct_layers.append(layer_pixels(self.scene)[:, :, 3].astype(float))
                            return texture
                        with patch.object(self.scene.puzzle_fog, 'render', side_effect=read_direct_layer):
                            image = self.render(audit=index % 15 == 0)
                        assert len(direct_layers) == 2
                        layer = direct_layers[0] * (1. - self.q.world_blend) + direct_layers[1] * self.q.world_blend
                    else:
                        image = self.render(audit=index % 15 == 0)
                        layer = layer_pixels(self.scene)[:, :, 3]
                    small = np.asarray(Image.fromarray(image).resize((128, 72), Image.Resampling.BILINEAR))
                    assert camera_signature(self.scene.last_camera) == held
                    assert (self.actor.x, self.actor.height, self.actor.z, self.actor.yaw) == pose
                    record = {'seconds': elapsed, 'frame': index, **state(self.q),
                              'particle_layer_mean_alpha_255': float(layer.mean())}
                    if previous_image is not None:
                        record['frame_difference'], _ = delta_report(previous_image, image)
                        record['low_frequency_difference'], _ = delta_report(previous_small, small)
                        change = np.abs(layer.astype(float) - previous_layer.astype(float))
                        record['particle_alpha_difference'] = {'mean': float(change.mean()),
                                                               'p99': float(np.percentile(change, 99)),
                                                               'peak': float(change.max())}
                        largest.append((record['low_frequency_difference']['mean'], elapsed,
                                        previous_image.copy(), image.copy()))
                        largest = sorted(largest, key=lambda v:v[0], reverse=True)[:3]
                    if index % 15 == 0:
                        landmarks.append((elapsed, image.copy()))
                    records.append(record)
                    frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
                    previous_image, previous_layer, previous_small = image, layer, small
                frames[0].save(self.out / (name + '-crest-30fps.gif'), save_all=True,
                               append_images=frames[1:],
                               duration=[30 if i % 3 != 2 else 40 for i in range(len(frames))],
                               loop=0, optimize=False)
                sheet = Image.new('RGB', (4 * 320, 3 * 202), '#15191b')
                pen = ImageDraw.Draw(sheet)
                for i, (elapsed, frame) in enumerate(landmarks):
                    x, y = i % 4 * 320, i // 4 * 202
                    sheet.paste(Image.fromarray(frame).resize((320, 180), Image.Resampling.NEAREST), (x, y + 22))
                    pen.text((x + 5, y + 5), '%.3f seconds' % elapsed, fill='white')
                sheet.save(self.out / (name + '-crest-contact.png'))
                for i, (magnitude, elapsed, before, after) in enumerate(largest):
                    save_image(self.out / ('%s-largest-motion-%d-before.png' % (name, i)), before)
                    save_image(self.out / ('%s-largest-motion-%d-after.png' % (name, i)), after)
                result = {'view': name, 'fps': 30, 'baseline_v16': baseline,
                          'camera_constant': True, 'pose_constant': True,
                          'maximum_frame_mean_255': max(r['frame_difference']['mean'] for r in records[1:]),
                          'maximum_low_frequency_mean_255': max(r['low_frequency_difference']['mean'] for r in records[1:]),
                          'largest_low_frequency_changes': [{'seconds': t, 'mean': m} for m,t,_,_ in largest],
                          'frames': records}
                if not baseline:
                    assert result['maximum_frame_mean_255'] < .5, ('Large 30fps image jump', result['view'])
                    blends = [r['blend'] for r in records]
                    assert all(0. <= b - a < .07 for a, b in zip(blends, blends[1:])), 'Discontinuous world blend'
                results.append(result)
        save_json(self.out / 'temporal-progression.json', results)
        return results


def load_reference_particles():
    return load_python_source(BASE / 'before' / 'g_huxin_canals_particles.py', '_v16_particle_reference')


def load_python_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    reference = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reference
    try:
        spec.loader.exec_module(reference)
        return reference
    finally:
        del sys.modules[spec.name]


def incoming_retiming():
    """Peak is unchanged; every clearing phase now lasts exactly twice as long."""
    from g_huxin_canals_particles import particles_at
    reference = load_reference_particles()
    try:
        records = []
        pairs = [(FOG_ARRIVAL_DURATION, 4.), ((FOG_ARRIVAL_DURATION + FOG_CLEAR_START) / 2., 4.)]
        pairs += [(FOG_CLEAR_START + 2. * (old - 4.), old) for old in
                  (4., 4.5, 6., 7., 8., 10., 11., 12., 15., 17., 20., 23., 24.)]
        for elapsed, baseline_elapsed in pairs:
            current = particles_at(elapsed, 87.)
            previous = reference.particles_at(baseline_elapsed, 87.)
            assert [(p.id, p.layer, p.variant) for p in current] == [(p.id, p.layer, p.variant) for p in previous]
            difference = max((abs(a - b) for p, old in zip(current, previous)
                              for a, b in zip((*p.center, p.width, p.height, p.rotation, p.alpha),
                                              (*old.center, old.width, old.height, old.rotation, old.alpha))), default=0.)
            assert difference < 1e-12, ('Peak or retimed clearing field changed', elapsed, difference)
            records.append({'elapsed': elapsed, 'baseline_elapsed': baseline_elapsed,
                            'matching_packets': len(current), 'maximum_numeric_difference': difference})
        return records
    finally:
        del reference


def review_scene(scene, actor, audio, startup=0., quick=False, out=None, arrival_only=False,
                 temporal_only=False, baseline_v16=False):
    out = Path(out) if out else BASE / 'after'
    out.mkdir(parents=True, exist_ok=True)
    production = hashes(PRODUCTION)
    preserved = hashes(GUARDS)
    baseline = protected_hashes()
    for name in PRODUCTION:
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    review = ParticleReview(scene, actor, audio, out, quick)
    if temporal_only:
        temporal = review.temporal_progression(baseline_v16)
        assert hashes(PRODUCTION) == production
        assert hashes(GUARDS) == preserved and protected_hashes() == baseline
        assert not audio.opened
        report = {'status':'passed', 'kind':'30fps crest diagnostic', 'baseline_v16':baseline_v16,
                  'temporal_progression':temporal, 'source_sha256':production,
                  'protected_sources_sha256':preserved, 'protected_scenes':baseline,
                  'audio_muted':audio.muted, 'audio_device_opened':audio.opened, 'windows_hidden':True}
        save_json(out / 'report.json', report)
        print('30fps crest diagnostic passed', flush=True)
        return report
    arrival = review.arrival_progression()
    if arrival_only:
        assert hashes(PRODUCTION) == production
        assert hashes(GUARDS) == preserved and protected_hashes() == baseline
        assert not audio.opened
        report = {'status': 'passed', 'kind': 'arrival calibration', 'arrival_progression': arrival,
                  'source_sha256': production, 'protected_sources_sha256': preserved,
                  'protected_scenes': baseline, 'audio_muted': audio.muted,
                  'audio_device_opened': audio.opened, 'windows_hidden': True}
        save_json(out / 'report.json', report)
        print(json.dumps(report, indent=2), flush=True)
        return report
    for view in arrival:
        coverage = {s['seconds']: s['current']['coverage_relative_to_peak'] for s in view['samples']}
        assert all(b >= a - 1e-12 for a, b in zip(coverage.values(), list(coverage.values())[1:])), 'Coverage receded during arrival'
        quarter, half, three_quarters = (FOG_ARRIVAL_DURATION * v for v in (.25, .5, .75))
        assert .03 < coverage[quarter] < .40, ('Arrival saturates too early', view['view'], coverage)
        assert .30 < coverage[half] < .75, ('Buildup is not distributed through midpoint', view['view'], coverage)
        assert .70 < coverage[three_quarters] < 1., ('Crest finishes prematurely', view['view'], coverage)
        assert all(coverage[b] - coverage[a] > .02 for a, b in
                   ((0., quarter), (quarter, half), (half, three_quarters)))
        # The bounded arrival curve deliberately flattens into the crest;
        # actual 30fps motion below guards its final approach and handoff.
    ordinary_baseline = review.ordinary_baseline()
    retiming = incoming_retiming()
    from g_huxin_canals_particles import build_particle_atlas, particle_schedule, particles_at
    atlas, atlas_w, atlas_h = build_particle_atlas()
    Image.frombytes('RGBA', (atlas_w, atlas_h), atlas).save(out / 'particle-atlas.png')
    preflight = {}
    for name, settings in VIEWS:
        review.begin(camera(*settings) if settings else None)
        preflight[name] = review.concealment(name)
    save_json(out / 'concealment-preflight.json', preflight)
    if not quick:
        assert not review.concealment_failures, review.concealment_failures
    view_reports = []
    capture_times = tuple(sorted({0., 1., 2., 3., 4., FOG_ARRIVAL_DURATION, ENTRY_DURATION,
                                 8., 10., MIDDLE_CLEAR_START, NEAR_CLEAR_END, 18., FAR_CLEAR_START,
                                 MIDDLE_CLEAR_END, 28., FAR_CLEAR_END, 38., 42., SEQUENCE_DURATION}))
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
                layer = layer_pixels(scene)
                if t == 0. or t == SEQUENCE_DURATION:
                    assert not layer.any(), 'Inactive particle target retained previous pixels'
                Image.fromarray(layer).save(out / ('%s-particles-%02d.png' % (name, t)))
                packet = particles_at(review.q.elapsed, review.clock)
                alpha = [p.alpha for p in packet]
                samples.append({'seconds': t, 'particle_alpha_mean': float(layer[:, :, 3].mean()),
                                'particle_alpha_nonzero_pixels': int((layer[:, :, 3] > 0).sum()),
                                'live_particles': len(packet), 'particle_alpha_sum': sum(alpha),
                                'particle_alpha_max': max(alpha, default=0.),
                                **state(review.q)})
            if not quick:
                frames.append(Image.fromarray(image).resize((480, 270), Image.Resampling.NEAREST))
        assert np.isclose(review.q.fog_clear, 1.)
        review.visible(name + '-stationary-final-player')
        concealment = preflight[name]
        boundaries = []
        for boundary in sorted({WORLD_BLEND_START, ENTRY_DURATION, FOG_CLEAR_START,
                                MIDDLE_CLEAR_START, NEAR_CLEAR_END, FAR_CLEAR_START, MIDDLE_CLEAR_END,
                                FAR_CLEAR_END, SEQUENCE_DURATION}):
            pair = []
            for elapsed in (boundary - .001, boundary + .001):
                phase(review.q, elapsed)
                pair.append(review.render(clock=87., audit=True))
            difference, delta = delta_report(*pair)
            record = {'seconds': boundary, 'difference': difference}
            if boundary != WORLD_BLEND_END:
                phase(review.q, boundary - .003)
                adjacent = review.render(clock=87.)
                control, _ = delta_report(adjacent, pair[0])
                record['adjacent_equal_duration_difference'] = control
                # Faster alpha evolution can legitimately cross two RGB levels
                # in 2 ms. A stage boundary must add no jump above that slope.
                assert difference['peak'] <= control['peak'] + 1., record
            boundaries.append(record)
            assert difference['peak'] < 8, record
            save_image(out / ('%s-boundary-%02d-x8.png' % (name, boundary)), np.minimum(255, delta * 8))
        if frames:
            frames[0].save(out / (name + '-timed-reveal.gif'), save_all=True,
                           append_images=frames[1:], duration=200, loop=0, optimize=False)
            arrival_frames = frames[:round(ENTRY_DURATION / .2) + 1]
            arrival_frames[0].save(out / (name + '-wave-arrival.gif'), save_all=True,
                                   append_images=arrival_frames[1:], duration=200, loop=0, optimize=False)
        view_reports.append({'name': name, 'samples': samples, 'concealment': concealment,
                             'boundaries': boundaries})
        save_json(out / 'stationary-report.partial.json', view_reports)
        print('Particle stationary review passed:', name, flush=True)

    optical_checks = review.optics()
    temporal = review.temporal_progression()
    ambient_independence = review.ambient_independence()
    isolated_fade = review.fade_isolation()
    depth_progression = review.depth_progression()
    review.timer_captures()
    save_json(out / 'optical-report.partial.json',
              {'optical_checks': optical_checks, 'assembled_particle_fade': isolated_fade,
               'particle_opacity_independent_of_ambient_clearing': ambient_independence,
               'ordinary_approach_baseline': ordinary_baseline,
               'near_first_depth_progression': depth_progression})
    # The same particle clock advances for a stationary control and a walker.
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
    interior_before = review.visible('interior-on-arrival')
    review.tick(max(0., SEQUENCE_DURATION - review.q.elapsed))
    interior_after = review.visible('interior-after-clearing')
    # Match camera and cloud clock to isolate individual particle lifetimes.
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
        'status': 'passed' if not (review.concealment_failures or review.visibility_failures) else 'failed native checks', 'views': view_reports, 'walk_after_unlock': route,
        'interior_route': interior_route, 'walking_and_stationary_fade_equal': True,
        'stopping_walking_does_not_stop_clearing': True,
        'interior_fixed_clock_difference': interior_difference,
        'visibility': review.visibility, 'controller_steps': review.steps,
        'uniform_parity_audits': review.uniform_audits,
        'particle_pass_audits': review.particle_audits,
        'concealment_failures': review.concealment_failures,
        'visibility_failures': review.visibility_failures,
        'optical_checks': optical_checks,
        'assembled_particle_fade': isolated_fade,
        'particle_opacity_independent_of_ambient_clearing': ambient_independence,
        'near_first_depth_progression': depth_progression,
        'ordinary_approach_baseline': ordinary_baseline,
        'peak_and_twice_duration_clearing_equivalent_to_v16': retiming,
        'arrival_progression': arrival,
        'temporal_progression': temporal,
        'wave_schedule': [{'wave': wave,
                           'count': sum(s.wave == wave for s in particle_schedule()),
                           'birth_min': min(s.birth for s in particle_schedule() if s.wave == wave),
                           'birth_max': max(s.birth for s in particle_schedule() if s.wave == wave),
                           'clear_start_min': min(s.clear_start for s in particle_schedule() if s.wave == wave),
                           'clear_start_max': max(s.clear_start for s in particle_schedule() if s.wave == wave)}
                          for wave in sorted({s.wave for s in particle_schedule()})],
        'composition_peak': max(review.mixture_peaks, default=0.),
        'source_sha256': production, 'protected_sources_sha256': preserved,
        'protected_scenes': baseline, 'startup_seconds': startup,
        'render_readback_ms': {'median': float(np.median(review.timings)), 'p95': float(np.percentile(review.timings, 95))},
        'audio_muted': audio.muted, 'audio_device_opened': audio.opened, 'windows_hidden': True,
    }
    save_json(out / 'report.json', report)
    print(json.dumps(report, indent=2), flush=True)
    assert not review.concealment_failures, review.concealment_failures
    assert not review.visibility_failures, review.visibility_failures
    return report


def run(label='after', quick=False, arrival_only=False, temporal_only=False, baseline_v16=False):
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(WIDTH, HEIGHT, 'Muted Canals particle fog review')
    scene = audio = None
    try:
        start = time.perf_counter()
        scene = Lake()
        actor = Explorer()
        actor.encounter = scene.sequence
        audio = EncounterAudio(True)
        review_scene(scene, actor, audio, time.perf_counter() - start, quick, BASE / label,
                     arrival_only, temporal_only, baseline_v16)
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
    parser.add_argument('--arrival-only', action='store_true')
    parser.add_argument('--temporal-only', action='store_true')
    parser.add_argument('--baseline-v16', action='store_true')
    args = parser.parse_args()
    run(args.label, args.quick, args.arrival_only, args.temporal_only, args.baseline_v16)
