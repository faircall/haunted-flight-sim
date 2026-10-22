"""Hidden, muted native QA for building-targeted fog and its authoring widgets."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import argparse
import cProfile
import ctypes
import gc
import hashlib
import json
import os
import tempfile
import time
import pstats

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

import numpy as np
from PIL import Image, ImageDraw
import pyray as pr

from g_huxin_canals import DECK, camera_zone
from g_huxin_canals_layout import REVIEW_ROUTE, DOOR_ROUTES
from g_huxin_canals_direction import (
    DEFAULT_PATH, default_document, building_document, load_direction, profile_from_document,
)
from g_huxin_canals_targets import target_groups
from g_huxin_canals_particles import particles_at, building_frame_at
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_audio import EncounterAudio
from huxin_canals_editor import Editor
from huxin_canals_editor_review import WidgetReview, GUARDS, middle
from huxin_canals_particle_review import ParticleReview, phase, state
from huxin_canals_review import pixels, camera_signature, protected_hashes, delta_report
from huxin_canals_viewer import Lake, Explorer, reset_player
from temple_cinematics_editor import Input
from temple_interior_viewer import camera


ROOT = Path(__file__).parent
BASE = ROOT / 'artifacts/huxin-canals-buildings'
SOURCES = (
    'g_huxin_canals_direction.py', 'g_huxin_canals_targets.py',
    'g_huxin_canals_particles.py', 'g_huxin_canals_sequence.py',
    'g_huxin_canals_editor.py', 'huxin_canals_editor.py',
    'huxin_canals_particles.py', 'huxin_canals_viewer.py',
    'shaders/huxin_canals_particles.fs', 'shaders/huxin_canals_post.fs',
    'art/temple/huxin_canals/fog_targets.json',
)
VIEWS = (
    ('gameplay', None),
    ('reverse', ((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78)),
)


def hashes(names):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')


def contact_sheet(images, labels, path, columns=4):
    width, height = 400, 225
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new('RGB', (width * columns, (height + 23) * rows), '#10191c')
    draw = ImageDraw.Draw(sheet)
    for index, (image, label) in enumerate(zip(images, labels)):
        x, y = index % columns * width, index // columns * (height + 23)
        sheet.paste(Image.fromarray(image).resize((width, height)), (x, y + 23))
        draw.text((x + 5, y + 5), label, fill='#dae4dc')
    sheet.save(path)


class BuildingReview(ParticleReview):
    def __init__(self, scene, actor, audio, out, profile, quick=False):
        super().__init__(scene, actor, audio, out, quick)
        self.profile = profile

    def ordinary_approach(self):
        records = []
        legacy = profile_from_document(default_document())
        from g_huxin_canals_sequence import causeway_point
        for progress in (0., .5, 1.):
            frames = []
            for profile in (legacy, self.profile):
                self.actor.encounter = self.scene.sequence = CanalSequence(profile)
                self.actor.x, self.actor.z = causeway_point(progress)
                self.actor.height = DECK
                self.actor.yaw = self.actor.phase = 0.
                self.actor.clip = 'idle'
                self.actor.shot = camera_zone(self.actor.x, self.actor.z)
                self.q.tick(0., self.actor)
                self.scene.player.pose('idle', 0., None)
                self.scene.render(self.actor, 87.)
                frames.append(pixels(self.scene))
            difference, _ = delta_report(*frames)
            records.append({'causeway_progress': progress, 'difference': difference})
            assert difference['peak'] == 0., ('Ordinary approach changed', records[-1])
        return records

    def begin(self, view=None):
        e = self.actor
        e.encounter = self.scene.sequence = CanalSequence(self.profile)
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

    def timeline(self, name):
        times = (0., 1., 2.5, 4., 5., 5.5, 6., 8., 12., 20., 32., 46.)
        records, images = [], []
        expected_camera = camera_signature(self.scene.last_camera)
        for elapsed in times:
            phase(self.q, elapsed)
            self.clock = 40. + elapsed
            image = self.render('%s-%05.2f' % (name, elapsed), audit=True)
            assert camera_signature(self.scene.last_camera) == expected_camera
            images.append(image)
            records.append({**state(self.q), 'particles': self.scene.puzzle_fog.last_count,
                            'groups': list(getattr(self.scene.puzzle_fog, 'last_groups', ()))})
        contact_sheet(images, ['%s %.2fs' % (name, t) for t in times],
                      self.out / (name + '-timeline.jpg'))
        return records

    def transition_motion(self, name):
        frames, records = [], []
        previous = None
        expected_camera = camera_signature(self.scene.last_camera)
        for index in range(61):
            elapsed = 4.5 + index / 30.
            phase(self.q, elapsed)
            self.clock = 40. + elapsed
            image = self.render(audit=index % 15 == 0)
            assert camera_signature(self.scene.last_camera) == expected_camera
            if previous is not None:
                difference, _ = delta_report(previous, image)
                records.append({'elapsed': elapsed, 'difference': difference})
            previous = image
            frames.append(Image.fromarray(image).resize((640, 360), Image.Resampling.NEAREST))
        frames[0].save(self.out / (name + '-handoff.gif'), save_all=True,
                       append_images=frames[1:], duration=[30, 30, 40] * 20 + [30], loop=0)
        save_json(self.out / (name + '-temporal.json'), records)
        return {'frames': len(frames), 'max_mean_delta': max(r['difference']['mean'] for r in records),
                'max_peak_delta': max(r['difference']['peak'] for r in records)}

    def warm_benchmark(self):
        """Time production drawing only: no pixels(), mock wrappers or selection."""
        self.begin()
        records = []
        for elapsed in (5., 5.5, 12., 20., 46.):
            phase(self.q, elapsed)
            for index in range(5):
                self.scene.render(self.actor, 87. + index / 60.)
            times, drawn = [], []
            for index in range(20):
                start = time.perf_counter()
                self.scene.render(self.actor, 88. + index / 60.)
                times.append((time.perf_counter() - start) * 1000.)
                drawn.append(self.scene.puzzle_fog.last_draw_count)
            records.append({'elapsed': elapsed, 'frames': len(times),
                            'median_ms': float(np.median(times)),
                            'p95_ms': float(np.percentile(times, 95)),
                            'live_cards': self.scene.puzzle_fog.last_count,
                            'last_direct_visible_cards_min': min(drawn),
                            'last_direct_visible_cards_max': max(drawn)})
        save_json(self.out / 'warm-render-benchmark.json', records)
        return records

    def reveal_motion(self, name):
        frames = []
        for elapsed in np.arange(0., self.profile.cue('end') + .125, .25):
            phase(self.q, float(elapsed))
            self.clock = 40. + elapsed
            image = self.render()
            frames.append(Image.fromarray(image).resize((640, 360), Image.Resampling.NEAREST))
        frames[0].save(self.out / (name + '-building-reveal.gif'), save_all=True,
                       append_images=frames[1:], duration=250, loop=0)
        return {'frames': len(frames), 'duration_seconds': len(frames) * .25}


def target_editor_review(scene, out, document):
    """Use the public widget rectangles; all saved files live in a temporary folder."""
    with tempfile.TemporaryDirectory(prefix='haunted-building-editor-') as folder:
        path = Path(folder) / 'direction.json'
        editor = Editor(scene, path=path, document=document, live_input=False,
                        selection_output_path=Path(folder) / 'selection.json')
        ui = WidgetReview(editor, out)
        try:
            buttons, _ = editor.controls()
            houses = {target.id for target in target_groups() if target.kind == 'house'}
            target_id = next(name[7:] for name, title, rect, active in buttons
                             if name.startswith('target:') and name[7:] in houses)
            ui.button('target:' + target_id)
            assert editor.state.target_id == target_id
            ui.button('focus_target')
            editor.state.seek(editor.state.duration)
            editor.render_scene()
            target = next(target for target in target_groups() if target.id == target_id)
            pick_point = editor.project((target.center[0],
                                         target.center[1] + target.half_extents[1] * .8,
                                         target.center[2]))
            assert pick_point is not None
            other_id = next(name[7:] for name, title, rect, active in editor.controls()[0]
                            if name.startswith('target:') and name[7:] != target_id and name[7:] in houses)
            ui.button('target:' + other_id)
            ui.click(pick_point)
            assert editor.state.target_id == target_id, 'Viewport pick did not select the framed house'
            ui.actions.append({'viewport_picked_target': target_id})
            ui.capture('editor-00-viewport-selected-house')
            editor.state.seek(5.)
            before = ui.capture('editor-01-selected-target')
            original = editor.state.checkpoint()
            # Drag the actual projected target-placement handle, then undo it.
            axis, rectangle, origin, tip = editor.gizmo_handles()[0]
            start = middle(rectangle)
            end = (start[0] + .2 * (tip[0] - origin[0]),
                   start[1] + .2 * (tip[1] - origin[1]))
            history = len(editor.state.undo_stack)
            editor.update(0., Input(mouse=start, left_pressed=True, left_down=True))
            editor.update(0., Input(mouse=end, left_down=True))
            editor.update(0., Input(mouse=end, left_released=True))
            offset = editor.state.document['fog']['groups'][target_id]['offset'][axis]
            assert abs(offset - original['fog']['groups'][target_id]['offset'][axis] - .6) < 1e-8
            assert len(editor.state.undo_stack) == history + 1
            ui.capture('editor-01b-target-handle')
            ui.shortcut('Z')
            assert editor.state.document == original
            reveal = next(rect for prop, rect in editor.reveal_handles() if prop == 'reveal_end')
            reveal_start = middle(reveal)
            desired_end = original['fog']['groups'][target_id]['reveal_end'] + .5
            reveal_finish = (editor.x_at(desired_end), reveal_start[1])
            history = len(editor.state.undo_stack)
            editor.update(0., Input(mouse=reveal_start, left_pressed=True, left_down=True))
            editor.update(0., Input(mouse=reveal_finish, left_down=True))
            editor.update(0., Input(mouse=reveal_finish, left_released=True))
            assert abs(editor.state.document['fog']['groups'][target_id]['reveal_end'] - desired_end) < .11
            assert len(editor.state.undo_stack) == history + 1
            assert editor.state.document['cues'] == original['cues']
            ui.shortcut('Z')
            assert editor.state.document == original
            undo_count = len(editor.state.undo_stack)
            old_group = deepcopy(original['fog']['groups'][target_id])
            ui.field(('offset', 0), old_group['offset'][0] + 2.5)
            ui.field(('scale',), old_group['scale'] * 1.15)
            ui.field(('opacity',), .55)
            ui.field(('reveal_start',), old_group['reveal_start'] + .75)
            ui.field(('reveal_end',), old_group['reveal_end'] + 1.25)
            assert len(editor.state.undo_stack) == undo_count + 5
            edited = editor.state.checkpoint()
            for identity, group in original['fog']['groups'].items():
                if identity != target_id:
                    assert edited['fog']['groups'][identity] == group
            editor.state.seek(5.)
            after = ui.capture('editor-02-edited-target')
            difference, _ = delta_report(before, after)
            assert difference['mean'] > .002, 'Selected fog placement had no visible effect'
            ui.shortcut('Z')
            assert editor.state.document['fog']['groups'][target_id]['reveal_end'] == old_group['reveal_end']
            ui.shortcut('Y')
            assert editor.state.document == edited
            ui.button('save')
            assert not editor.state.dirty
            saved = load_direction(path)
            assert saved == edited
            ui.field(('opacity',), .7)
            ui.button('reload')
            assert editor.state.document == saved and not editor.state.dirty
            (out / 'saved-target-test.json').write_bytes(path.read_bytes())
            ui.capture('editor-03-saved-target')
            profile = profile_from_document(saved)
            peak = {p.id: p for p in particles_at(5., 87., profile_from_document(original))}
            changed = {p.id: p for p in particles_at(5., 87., profile)}
            assert peak.keys() == changed.keys()
            unrelated = [identity for identity, p in peak.items() if p.group_id != target_id]
            assert unrelated and all(peak[identity] == changed[identity] for identity in unrelated)
            result = {'selected_target': target_id, 'widget_actions': ui.actions,
                      'image_difference': difference, 'unrelated_packets_unchanged': len(unrelated),
                      'saved_profile': profile}
        finally:
            editor.close()
        # This is the same saved-profile constructor used by normal gameplay.
        actor = reset_player(scene, puzzle=True, direction=result.pop('saved_profile'))
        assert scene.sequence.direction.group(target_id).offset[0] == old_group['offset'][0] + 2.5
        assert scene.sequence.direction.group(target_id).scale == old_group['scale'] * 1.15
        scene.sequence.seek(12.)
        scene.render(actor, 99.)
        Image.fromarray(pixels(scene)).save(out / 'editor-04-saved-game-playback.png')
        result['fresh_game_uses_saved_group'] = True
        return result


def run(label='trial1', quick=False, visual_only=False, coverage_only=False):
    out = BASE / label
    out.mkdir(parents=True, exist_ok=True)
    source_paths = tuple(name for name in SOURCES if not (visual_only and 'editor.py' in name))
    source_before, guards_before = hashes(source_paths), hashes(GUARDS)
    protected = protected_hashes()
    live_config = DEFAULT_PATH.read_bytes()
    document = building_document()
    profile = profile_from_document(document)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(1440, 900, 'Muted building-fog review')
    scene = audio = None
    try:
        scene = Lake()
        actor = reset_player(scene, puzzle=True, direction=profile)
        audio = EncounterAudio(automated=True)
        review = BuildingReview(scene, actor, audio, out, profile, quick=True)
        ordinary = [] if coverage_only else review.ordinary_approach()
        timelines, concealment, motion = {}, {}, {}
        if not coverage_only:
            for name, description in VIEWS:
                view = camera(*description) if description else None
                review.begin(view)
                timelines[name] = review.timeline(name)
        # Early image panels are available before the more expensive audit.
        save_json(out / 'timeline.json', timelines)
        if not visual_only:
            for name, description in VIEWS:
                review.begin(camera(*description) if description else None)
                concealment[name] = review.concealment(name)
                if not quick and not coverage_only:
                    motion[name] = review.transition_motion(name)
                    motion[name]['full_reveal'] = review.reveal_motion(name)
            benchmark = None if coverage_only else review.warm_benchmark()
            save_json(out / 'render-preflight.json', {
                'concealment': concealment, 'concealment_failures': review.concealment_failures,
                'warm_scene_render_benchmark': benchmark,
                'ordinary_approach_pixel_equality': ordinary, 'source_sha256': source_before,
            })
            editor = None if coverage_only else target_editor_review(scene, out, document)
            walking = None
            if not quick and not coverage_only:
                review.begin()
                review.tick(profile.cue('blend_end'))
                idle_actor = Explorer()
                idle_actor.x, idle_actor.height, idle_actor.z = 1.65, DECK, 1.65
                idle = CanalSequence(profile)
                idle.tick(.01, idle_actor)
                assert idle.activate(idle_actor)
                idle.tick(profile.cue('blend_end'), idle_actor)
                quay = review.walk(REVIEW_ROUTE[1:6], idle, idle_actor, 'walk-quay')
                door = next(route for route in DOOR_ROUTES if route['seed'] == 110 and route['bay'] == 1)
                house = review.walk(door['points'][:5], idle, idle_actor, 'walk-house')
                review.tick(max(0., profile.cue('end') - review.q.elapsed))
                review.visible('walk-interior-after-clearing')
                walking = {'steps': review.steps, 'quay': quay, 'house': house,
                           'visibility_samples': review.visibility,
                           'visibility_failures': review.visibility_failures}
        else:
            editor = walking = benchmark = None
        report = {'status': 'passed' if not (review.concealment_failures or review.visibility_failures) else 'failed',
                  'concealment_status': 'not_run' if visual_only else
                                        ('failed' if review.concealment_failures else 'passed'),
                  'visibility_status': 'not_run' if walking is None else
                                      ('failed' if review.visibility_failures else 'passed'),
                  'scope': 'concealment_only' if coverage_only else 'visual_only' if visual_only else 'quick' if quick else 'full',
                  'timeline': timelines, 'concealment': concealment, 'motion': motion,
                  'concealment_failures': review.concealment_failures,
                  'reflection_and_uniform_audits': review.uniform_audits,
                  'native_editor': editor, 'source_sha256': source_before,
                  'walking': walking,
                  'warm_scene_render_benchmark': benchmark,
                  'ordinary_approach_pixel_equality': ordinary,
                  'protected_sha256': guards_before, 'protected_scenes': protected,
                  'timing_ms': {'median': float(np.median(review.timings)),
                                'p95': float(np.percentile(review.timings, 95))},
                  'hidden': True, 'muted': audio.muted,
                  'audio_device_opened': bool(pr.is_audio_device_ready())}
        assert hashes(source_paths) == source_before, 'Production changed while native review ran'
        assert hashes(GUARDS) == guards_before and protected_hashes() == protected
        assert DEFAULT_PATH.read_bytes() == live_config, 'Review changed live authoring data'
        assert audio.muted and not report['audio_device_opened']
        save_json(out / 'report.json', report)
        print(json.dumps(report, indent=2), flush=True)
        assert not review.concealment_failures, 'See saved full-frame endpoint differences'
        assert not review.visibility_failures, 'See saved gameplay visibility samples'
        return report
    finally:
        if audio:audio.close()
        if scene:scene.close()
        pr.close_window()


def profile_render(label='profile'):
    """Separate Python submission, GPU completion, and canonical packet sampling."""
    out = BASE / label
    out.mkdir(parents=True, exist_ok=True)
    source_before, guards_before = hashes(SOURCES), hashes(GUARDS)
    protected = protected_hashes()
    live_config = DEFAULT_PATH.read_bytes()
    profile = profile_from_document(building_document())
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(640, 360, 'Muted building-fog render profile')
    scene = audio = None
    try:
        # glFinish waits for commands already submitted by the actual renderer;
        # it adds no texture readback or altered drawing path.
        finish = ctypes.WinDLL('opengl32').glFinish
        finish.argtypes = []
        finish.restype = None
        scene = Lake()
        actor = reset_player(scene, puzzle=True, direction=profile)
        audio = EncounterAudio(automated=True)
        review = BuildingReview(scene, actor, audio, out, profile, quick=True)
        review.begin()
        results = []
        for mode, profile in (('legacy', profile_from_document(default_document())),
                              ('buildings', profile_from_document(building_document()))):
            review.profile = profile
            review.begin()
            for elapsed in (5., 5.5):
                phase(review.q, elapsed)
                for index in range(8):
                    scene.render(actor, 40. + index / 60.)
                finish()
                packet_times = []
                sampler = building_frame_at if mode == 'buildings' else particles_at
                for index in range(15):
                    start = time.perf_counter()
                    packet = sampler(elapsed, 70. + index / 60., profile)
                    packet_times.append((time.perf_counter() - start) * 1000.)
                submission, completion, gc_events = [], [], []
                gc_starts = {}
                def record_gc(stage, info):
                    generation = info['generation']
                    if stage == 'start':gc_starts[generation] = time.perf_counter()
                    else:
                        gc_events.append({'generation': generation, 'collected': info['collected'],
                                          'milliseconds': (time.perf_counter() - gc_starts[generation]) * 1000.})
                gc.callbacks.append(record_gc)
                try:
                    for index in range(60):
                        finish()
                        start = time.perf_counter()
                        scene.render(actor, 90. + index / 60.)
                        submitted = time.perf_counter()
                        finish()
                        completed = time.perf_counter()
                        submission.append((submitted - start) * 1000.)
                        completion.append((completed - submitted) * 1000.)
                finally:
                    gc.callbacks.remove(record_gc)
                # Scoped diagnostic only; restore automatic collection before
                # profiling or returning to any application logic.
                was_enabled = gc.isenabled()
                gc.disable()
                no_gc = []
                try:
                    for index in range(15):
                        finish()
                        start = time.perf_counter()
                        scene.render(actor, 120. + index / 60.)
                        no_gc.append((time.perf_counter() - start) * 1000.)
                    finish()
                finally:
                    if was_enabled:gc.enable()
                gc.collect()
                profiler = cProfile.Profile()
                profiler.enable()
                for index in range(5):
                    scene.render(actor, 140. + index / 60.)
                profiler.disable()
                finish()
                stem = '%s-elapsed-%04.1f' % (mode, elapsed)
                profiler.dump_stats(str(out / (stem + '.prof')))
                with (out / (stem + '-cumulative.txt')).open('w', encoding='utf-8', newline='\n') as stream:
                    pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(50)
                with (out / (stem + '-tottime.txt')).open('w', encoding='utf-8', newline='\n') as stream:
                    pstats.Stats(profiler, stream=stream).sort_stats('tottime').print_stats(50)
                results.append({'mode': mode, 'elapsed': elapsed,
                                'packet_count': len(packet.ids) if mode == 'buildings' else len(packet),
                                'sample_api': sampler.__name__, 'frames': 60,
                                'sample_miss_median_ms': float(np.median(packet_times)),
                                'render_submission_median_ms': float(np.median(submission)),
                                'render_submission_p95_ms': float(np.percentile(submission, 95)),
                                'gpu_finish_wait_median_ms': float(np.median(completion)),
                                'gpu_finish_wait_p95_ms': float(np.percentile(completion, 95)),
                                'total_median_ms': float(np.median(np.array(submission) + completion)),
                                'gc_events': gc_events,
                                'gc_total_ms': sum(item['milliseconds'] for item in gc_events),
                                'gc_disabled_render_median_ms': float(np.median(no_gc)),
                                'gc_disabled_render_p95_ms': float(np.percentile(no_gc, 95)),
                                'last_direct_visible_cards': scene.puzzle_fog.last_draw_count})
                save_json(out / 'profile.partial.json', results)
        assert hashes(SOURCES) == source_before and hashes(GUARDS) == guards_before
        assert protected_hashes() == protected and DEFAULT_PATH.read_bytes() == live_config
        report = {'status': 'passed', 'results': results, 'source_sha256': source_before,
                  'protected_sha256': guards_before, 'protected_scenes': protected,
                  'hidden': True, 'muted': audio.muted, 'audio_device_opened': pr.is_audio_device_ready()}
        assert audio.muted and not report['audio_device_opened']
        save_json(out / 'profile-report.json', report)
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if audio:audio.close()
        if scene:scene.close()
        pr.close_window()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='trial1')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--visual-only', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--coverage-only', action='store_true')
    args = parser.parse_args()
    if args.profile:profile_render(args.label)
    else:run(args.label, args.quick, args.visual_only, args.coverage_only)
