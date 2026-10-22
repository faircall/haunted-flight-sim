"""Hidden, muted QA of real Canals direction-editor widgets and saved playback."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import os
import tempfile

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

import numpy as np
from PIL import Image
import pyray as pr
import huxin_canals_editor as editor_module

from g_huxin_canals_direction import (DEFAULT_PATH, default_document, load_direction,
                                     profile_from_document)
from g_huxin_canals_particles import particles_at
from huxin_canals_editor import Editor
from temple_cinematics_editor import Input
from huxin_canals_review import protected_hashes, pixels, camera_signature, delta_report
from huxin_canals_viewer import Lake, Explorer, reset_player


ROOT = Path(__file__).parent
OUT = ROOT / 'artifacts' / 'huxin-canals-editor'
SOURCES = ('g_huxin_canals_direction.py', 'g_huxin_canals_editor.py',
           'huxin_canals_editor.py', 'g_huxin_canals_sequence.py',
           'g_huxin_canals_particles.py', 'huxin_canals_particles.py',
           'huxin_canals_viewer.py')
GUARDS = ('g_huxin_moon_sequence.py', 'huxin_moon_viewer.py',
          'shaders/huxin_moon_post.fs', 'huxin_moon_review.py',
          'huxin_moon_fog_review.py', 'test_huxin_moon_encounter.py',
          'art/temple/huxin_canals/origin_snapshot.json',
          'art/temple/huxin_canals_flooded/origin_snapshot.json',
          'art/temple/huxin_canals_flooded/frozen_snapshot.json')


def hashes(names):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def middle(rect):
    if hasattr(rect, 'x'):
        return rect.x + rect.width / 2., rect.y + rect.height / 2.
    return rect[0] + rect[2] / 2., rect[1] + rect[3] / 2.


class WidgetReview:
    def __init__(self, editor, out):
        self.editor, self.out = editor, out
        self.actions = []

    def click(self, point):
        self.editor.update(0., Input(mouse=point, left_pressed=True, left_down=True))
        self.editor.update(0., Input(mouse=point, left_released=True))

    def button(self, identity):
        buttons, _ = self.editor.controls()
        rectangle = next(rect for name, title, rect, active in buttons if name == identity)
        self.click(middle(rectangle))
        self.actions.append({'button': identity})

    def field(self, path, value):
        _, fields = self.editor.controls()
        rectangle = next(rect for name, rect in fields if name == path)
        self.click(middle(rectangle))
        self.editor.update(0., Input(chars=str(value), pressed={'ENTER'}))
        self.actions.append({'field': list(path), 'value': value})

    def shortcut(self, key):
        self.editor.update(0., Input(pressed={key}, down={'LEFT_CONTROL'}))
        self.actions.append({'shortcut': 'Ctrl+' + key})

    def capture(self, name):
        self.editor.render_scene()
        image = pixels(self.editor.scene)
        Image.fromarray(image).save(self.out / (name + '-scene.png'))
        pr.begin_drawing()
        try:
            pr.clear_background(pr.BLACK)
            self.editor.draw()
            pr.rl.rlDrawRenderBatchActive()
            screen = pr.load_image_from_screen()
            try:
                pr.export_image(screen, str(self.out / (name + '-editor.png')))
            finally:
                pr.unload_image(screen)
        finally:
            pr.end_drawing()
        return image

    def scrub(self, elapsed):
        timeline = self.editor.layout()['timeline']
        point = (self.editor.x_at(elapsed), middle(timeline)[1])
        self.click(point)
        assert abs(self.editor.state.elapsed - elapsed) < .05
        self.actions.append({'scrub': elapsed})

    def drag_cue(self, cue, destination):
        rectangle = next(rect for name, rect in self.editor.cue_handles() if name == cue)
        start = middle(rectangle)
        end = (self.editor.x_at(destination), start[1])
        self.editor.update(0., Input(mouse=start, left_pressed=True, left_down=True))
        for fraction in (.25, .5, .75, 1.):
            point = (start[0] + (end[0] - start[0]) * fraction, start[1])
            self.editor.update(0., Input(mouse=point, left_down=True))
        self.editor.update(0., Input(mouse=end, left_released=True))
        self.actions.append({'drag_cue': cue, 'destination': destination})

    def drag_bank(self):
        self.editor.render_scene()
        handles = self.editor.gizmo_handles()
        assert handles, 'Selected bank has no visible drag handle'
        axis, rectangle, origin, tip = handles[0]
        start = middle(rectangle)
        end = (start[0] + (tip[0] - origin[0]) * .2,
               start[1] + (tip[1] - origin[1]) * .2)
        before = self.editor.state.checkpoint()
        count = len(self.editor.state.undo_stack)
        self.editor.update(0., Input(mouse=start, left_pressed=True, left_down=True))
        self.editor.update(0., Input(mouse=end, left_down=True))
        self.editor.update(0., Input(mouse=end, left_released=True))
        expected = before['banks'][self.editor.state.band]['offset'][axis] + .6
        assert abs(self.editor.state.bank['offset'][axis] - expected) < 1e-8
        assert len(self.editor.state.undo_stack) == count + 1
        after = self.editor.state.checkpoint()
        self.capture('03b-bank-gizmo-moved')
        self.shortcut('Z')
        assert self.editor.state.document == before
        self.shortcut('Y')
        assert self.editor.state.document == after
        self.shortcut('Z')
        assert self.editor.state.document == before
        self.actions.append({'bank_gizmo_axis': axis, 'metres': .6, 'single_undo_transaction': True})

    def reflection_seek_check(self, times):
        scene, editor = self.editor.scene, self.editor
        original = scene.puzzle_fog.render
        repeated = {}
        records = []
        for elapsed in times:
            editor.state.seek(elapsed)
            calls = []
            def record(source, cam, sequence, clock, colour, water_y, reflected=False):
                texture = original(source, cam, sequence, clock, colour, water_y, reflected)
                expected = tuple((p.id, p.center, p.alpha) for p in particles_at(sequence.elapsed, clock, sequence.direction))
                assert scene.puzzle_fog.last_signature == expected
                calls.append({'reflected': reflected, 'water_y': water_y, 'clock': clock,
                              'signature': expected, 'profile': sequence.direction})
                return texture
            with patch.object(scene.puzzle_fog, 'render', side_effect=record):
                editor.render_scene()
            image = pixels(scene)
            assert calls and len(calls) % 2 == 0
            for a, b in zip(calls[::2], calls[1::2]):
                assert a['reflected'] and not b['reflected']
                assert a['signature'] == b['signature'] and a['profile'] == b['profile']
                assert a['clock'] == b['clock'] and a['water_y'] == b['water_y']
            record = {'seconds': elapsed, 'passes': len(calls),
                      'camera': camera_signature(scene.last_camera)}
            if elapsed in repeated:
                difference, _ = delta_report(repeated[elapsed], image)
                record['repeat_difference'] = difference
                assert difference['peak'] == 0., ('Seek left animation/render residue', record)
            repeated[elapsed] = image
            records.append(record)
        return records


def run(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source_hashes, guard_hashes, protected = hashes(SOURCES), hashes(GUARDS), protected_hashes()
    live_bytes = DEFAULT_PATH.read_bytes()
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(1440, 900, 'Muted Canals direction-editor review')
    scene = editor = None
    try:
        scene = Lake()
        with tempfile.TemporaryDirectory(prefix='haunted-canals-editor-native-') as folder:
            path = Path(folder) / 'direction.json'
            editor = Editor(scene, path=path, document=default_document(), live_input=False,
                            selection_output_path=Path(folder) / 'selection.json')
            actor = editor.actor
            ui = WidgetReview(editor, out)
            ui.capture('01-open-fog-editor')
            original = editor.state.checkpoint()
            assert editor.state.elapsed == original['cues']['build_end']
            ui.button('top_view')
            ui.capture('01b-overhead-fog-placement')
            assert editor.state.document == original and not editor.state.dirty
            ui.button('game_view')
            editor.update(0., Input(pressed={'F8'}))
            assert editor.selection.enabled
            selection_counts = []
            for _ in range(3):
                editor.render_scene()
                selection_counts.append(len(editor.selection.instances))
            assert selection_counts[0] > 0 and len(set(selection_counts)) == 1
            editor.update(0., Input(pressed={'ESCAPE'}))
            assert not editor.selection.enabled and not editor.closed
            ui.button('cue:middle_start')
            assert editor.state.elapsed == original['cues']['middle_start']
            ui.scrub(18.5)
            assert editor.state.document == original and not editor.state.dirty
            before = editor.state.checkpoint()
            undo_count = len(editor.state.undo_stack)
            ui.drag_cue('near_end', 15.2)
            assert abs(editor.state.document['cues']['near_end'] - 15.2) < .11
            assert len(editor.state.undo_stack) == undo_count + 1
            changed = editor.state.checkpoint()
            ui.shortcut('Z')
            assert editor.state.document == before
            ui.shortcut('Y')
            assert editor.state.document == changed
            ui.capture('02-dragged-cue')
            ui.button('cue:middle_start')
            ui.field(('time',), 12.5)
            assert editor.state.document['cues']['middle_start'] == 12.5
            ui.button('cue:near_end')
            ui.field(('time',), 15.25)
            exact = editor.state.checkpoint()
            history_count = len(editor.state.undo_stack)
            marker = next(rect for cue, rect in editor.cue_handles() if cue == 'near_end')
            ui.click(middle(marker))
            assert editor.state.document == exact, 'Selecting a marker must preserve fractional timing'
            assert len(editor.state.undo_stack) == history_count
            ui.actions.append({'fractional_marker_click_preserves_exact_time': 15.25})
            ui.button('cue:middle_start')
            good = editor.state.checkpoint()
            ui.field(('time',), 100.)
            assert editor.state.document == good
            editor.update(0., Input(pressed={'ESCAPE'}))
            assert editor.state.document == good and not editor.closed
            ui.button('tab:fog')
            ui.button('bank:near')
            editor.state.seek(2.5)
            before_fog = ui.capture('03-fog-before-edit')
            ui.drag_bank()
            ui.field(('offset', 0), 2.5)
            ui.field(('opacity',), .65)
            assert editor.state.document['banks']['near']['offset'][0] == 2.5
            assert editor.state.document['banks']['near']['opacity'] == .65
            editor.state.seek(2.5)
            after_fog = ui.capture('04-fog-position-edited')
            fog_difference, _ = delta_report(before_fog, after_fog)
            assert fog_difference['mean'] > .01
            ui.button('tab:camera')
            ui.button('cue:middle_start')
            ui.field(('eye', 0), 4.8)
            assert editor.state.document['cameras']['enabled']
            ui.capture('05-camera-key-edited')
            ui.button('save')
            assert path.exists() and not editor.state.dirty
            saved = load_direction(path)
            assert saved == editor.state.document
            (out / 'saved-test-direction.json').write_bytes(path.read_bytes())
            ui.field(('eye', 0), 5.1)
            assert editor.state.dirty
            ui.button('close')
            assert not editor.closed
            ui.capture('06-dirty-close-protection')
            ui.button('close_cancel')
            assert not editor.closed and editor.state.dirty
            ui.button('reload')
            assert editor.state.document == saved and not editor.state.dirty
            seeks = ui.reflection_seek_check((2.5, 5.5, 18., 1., 5.5, 18., 2.5))
            ui.capture('07-scrubbed-preview')
            ui.button('tab:fog')
            ui.field(('opacity',), .6)
            ui.button('close')
            ui.button('close_discard')
            assert editor.closed and load_direction(path) == saved
            editor.close()
            editor = Editor(scene, actor=actor, path=path, document=saved, live_input=False)
            ui2 = WidgetReview(editor, out)
            ui2.field(('opacity',), .55)
            ui2.button('close')
            ui2.button('close_save')
            assert editor.closed and not editor.state.dirty
            saved = load_direction(path)
            assert saved['banks']['near']['opacity'] == .55
            (out / 'saved-test-direction.json').write_bytes(path.read_bytes())
            editor.close()
            fresh_profile = profile_from_document(load_direction(path))
            fresh = reset_player(scene, puzzle=True, direction=fresh_profile)
            assert scene.sequence.direction == fresh_profile
            assert scene.sequence.cue('middle_start') == 12.5
            assert scene.sequence.direction.band('near').offset[0] == 2.5
            scene.sequence.seek(fresh_profile.cue('middle_start'))
            scene.render(fresh, 40. + scene.sequence.elapsed)
            assert abs(scene.last_camera.position.x - 4.8) < 1e-6
            Image.fromarray(pixels(scene)).save(out / '08-saved-camera-in-game.png')
            fresh.x, fresh.z, fresh.yaw = 0., 9., 1.2
            scene.sequence.seek(18.)
            scene.player.pose('walk', .37, dt=None)
            game_pose = (fresh.x, fresh.height, fresh.z, fresh.yaw)
            embedded = {}
            original_editor = editor_module.Editor
            def isolated_editor(active_scene, active_actor=None):
                return original_editor(active_scene, active_actor, path=path,
                                       document=load_direction(path), live_input=False)
            def scripted_loop(active_editor):
                assert active_editor.state.elapsed == 18.
                assert (active_editor.actor.x, active_editor.actor.height,
                        active_editor.actor.z, active_editor.actor.yaw) == game_pose
                active_ui = WidgetReview(active_editor, out)
                active_ui.scrub(18.5)
                active_ui.button('reverse_view')
                assert not active_editor.state.dirty
                active_ui.capture('09-embedded-return')
                first_idle = pixels(active_editor.scene)
                active_editor.render_scene()
                difference, _ = delta_report(first_idle, pixels(active_editor.scene))
                assert difference['peak'] == 0., 'Opening from a walk left a blended preview pose'
                embedded['camera'] = camera_signature(active_editor.preview_camera)
                embedded['walk_pose_reset_difference'] = difference
                active_ui.button('close')
                assert active_editor.closed
            with patch.object(editor_module, 'Editor', side_effect=isolated_editor), \
                 patch.object(editor_module, 'editor_loop', side_effect=scripted_loop):
                resumed_clock = editor_module.run_embedded(scene, fresh, None, 105.)
            assert abs(scene.sequence.elapsed - 18.5) < .05
            assert abs(resumed_clock - (87. + scene.sequence.elapsed)) < 1e-9
            assert (fresh.x, fresh.height, fresh.z, fresh.yaw) == game_pose
            assert camera_signature(scene.last_camera) == embedded['camera']
            scene.render(fresh, resumed_clock)
            assert camera_signature(scene.last_camera) == embedded['camera']
            embedded.update({'returned_elapsed': scene.sequence.elapsed,
                             'returned_clock': resumed_clock, 'player_pose_preserved': True,
                             'inspection_camera_preserved_on_first_game_frame': True})
            report = {'status': 'passed', 'actions': ui.actions + ui2.actions, 'seek_checks': seeks,
                      'fog_edit_image_difference': fog_difference,
                      'saved_config_feeds_fresh_game': True, 'live_config_untouched': True,
                      'selection_instance_counts_repeated_frames': selection_counts,
                      'embedded_roundtrip': embedded,
                      'source_sha256': source_hashes, 'protected_sources_sha256': guard_hashes,
                      'protected_scenes': protected, 'windows_hidden': True,
                      'audio_muted': True, 'audio_device_opened': pr.is_audio_device_ready()}
            assert not report['audio_device_opened']
        assert hashes(SOURCES) == source_hashes
        assert hashes(GUARDS) == guard_hashes and protected_hashes() == protected
        assert DEFAULT_PATH.read_bytes() == live_bytes
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(report, indent=2), flush=True)
        return report
    finally:
        if editor:editor.close()
        if scene:scene.close()
        pr.close_window()


if __name__ == '__main__':
    run()
