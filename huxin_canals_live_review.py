"""Short, hidden and muted native check of live Canals direction-file edits."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import tempfile
import time

os.environ['HAUNTED_MUTE_AUDIO'] = '1'

from PIL import Image
import pyray as pr

from g_huxin_canals_direction import DEFAULT_PATH, building_document, load_direction, save_direction, profile_from_document
from g_huxin_canals import DECK, camera_zone
from huxin_canals_audio import EncounterAudio
from huxin_canals_editor import Editor
from huxin_canals_editor_review import WidgetReview, GUARDS
from huxin_canals_review import pixels, camera_signature, protected_hashes, delta_report
from huxin_canals_viewer import Lake, LiveDirectionReload, reset_player
from temple_cinematics_editor import Input


ROOT = Path(__file__).parent
OUT = ROOT / 'artifacts/huxin-canals-live'
SOURCES = ('g_huxin_canals_direction.py', 'g_huxin_canals_live.py',
           'g_huxin_canals_editor.py', 'huxin_canals_editor.py',
           'g_huxin_canals_sequence.py', 'huxin_canals_viewer.py')


def hashes(names):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def optional_bytes(path):
    return path.read_bytes() if path.exists() else None


def pose(actor):
    return (actor.x, actor.height, actor.z, actor.yaw, actor.phase, actor.clip)


class PollClock:
    """Exercise the real byte debounce without sleeping or changing game time."""
    def __init__(self):
        self.now = time.monotonic() + 1.

    def settle(self, callback):
        self.now += 1.
        first = callback(now=self.now)
        self.now += .3
        second = callback(now=self.now)
        return [first, second]


def editor_review(scene, path, out):
    editor = Editor(scene, path=path, live_input=False,
                    selection_output_path=path.parent / 'selection.json')
    ui = WidgetReview(editor, out)
    clock = PollClock()
    records = []
    try:
        ui.button('target:house-110')
        ui.button('focus_target')
        editor.state.seek(12.25)
        editor.update(0., Input(pressed={'F8'}))
        assert editor.selection.enabled
        before = ui.capture('01-editor-before-live-edit')
        # Select actual exported geometry, rather than fabricating an F8 item.
        target = editor.state.target
        origin = editor.preview_camera.position
        point = pr.Vector3(target.center[0], target.center[1] + target.half_extents[1] * .65, target.center[2])
        direction = pr.vector3_normalize(pr.vector3_subtract(point, origin))
        hit = editor.selection.pick_ray(tuple(getattr(origin, k) for k in 'xyz'),
                                        tuple(getattr(direction, k) for k in 'xyz'))
        assert hit is not None, 'Native target framing should have selectable geometry'
        editor.selection.select_hit(hit)
        ui.capture('01b-editor-f8-selected')
        context = deepcopy(editor.selection.context)
        selected = deepcopy(editor.selection.selected)
        framing = camera_signature(scene.last_camera)
        transport = (editor.state.elapsed, editor.state.selected, editor.state.target_id, pose(editor.actor))

        remote = load_direction(path)
        remote['fog']['groups']['house-110'].update(opacity=.05)
        remote['fog']['groups']['house-110']['offset'][0] += 3.
        save_direction(remote, path)
        result = clock.settle(editor.poll_external)
        after = ui.capture('02-editor-external-update')
        difference, _ = delta_report(before, after)
        assert difference['mean'] > .001, ('External file did not change the actual rendered fog', difference)
        assert editor.state.document == remote
        assert transport == (editor.state.elapsed, editor.state.selected, editor.state.target_id, pose(editor.actor))
        assert camera_signature(scene.last_camera) == framing
        assert editor.selection.enabled and editor.selection.context == context
        assert editor.selection.selected == selected
        records.append({'case': 'external_render_update', 'poll': result, 'image_difference': difference,
                        'playhead': editor.state.elapsed, 'target': editor.state.target_id,
                        'camera_and_f8_context_preserved': True, 'selected_object': hit['id']})

        good = editor.state.checkpoint()
        path.write_text('{ "fog": ', encoding='utf-8', newline='\n')
        result = clock.settle(editor.poll_external)
        invalid = ui.capture('03-editor-invalid-file-held')
        difference, _ = delta_report(after, invalid)
        assert editor.state.document == good and difference['peak'] == 0.
        assert editor.state.watcher.error
        records.append({'case': 'invalid_file_retains_last_good', 'poll': result,
                        'image_difference': difference, 'error': editor.state.watcher.error})

        corrected = deepcopy(remote)
        corrected['fog']['groups']['house-110']['opacity'] = .8
        save_direction(corrected, path)
        result = clock.settle(editor.poll_external)
        recovered = ui.capture('04-editor-recovered-file')
        assert editor.state.document == corrected and not editor.state.watcher.error
        difference, _ = delta_report(invalid, recovered)
        assert difference['mean'] > .001
        records.append({'case': 'corrected_file_recovers', 'poll': result, 'image_difference': difference})

        # Real widget creates an unsaved local edit; a different remote field
        # merges while preserving both the authoring context and local value.
        editor.update(0., Input(pressed={'F8'}))
        ui.field(('scale',), 1.2)
        remote = load_direction(path)
        remote['fog']['groups']['house-121']['offset'][2] += 2.25
        save_direction(remote, path)
        disk = path.read_bytes()
        result = clock.settle(editor.poll_external)
        assert editor.state.group['scale'] == 1.2
        assert editor.state.document['fog']['groups']['house-121']['offset'][2] == remote['fog']['groups']['house-121']['offset'][2]
        assert editor.state.dirty and not editor.state.external_pending
        assert path.read_bytes() == disk, 'Automatic merge must not overwrite the external file'
        ui.capture('05-editor-independent-merge')
        records.append({'case': 'independent_merge', 'poll': result, 'local_scale': 1.2,
                        'remote_target': 'house-121', 'disk_not_overwritten': True})

        # Same field on both sides is intentionally held until a choice.
        ui.field(('opacity',), .35)
        remote = load_direction(path)
        remote['fog']['groups']['house-110']['opacity'] = .9
        save_direction(remote, path)
        disk = path.read_bytes()
        result = clock.settle(editor.poll_external)
        assert editor.state.external_pending and editor.state.group['opacity'] == .35
        ui.button('save')
        assert path.read_bytes() == disk, 'Save silently overwrote an unresolved external conflict'
        ui.capture('06-editor-conflict-held')
        conflicts = deepcopy(editor.state.external_conflicts)
        ui.button('use_file')
        assert not editor.state.external_pending and editor.state.group['opacity'] == .9
        records.append({'case': 'same_field_conflict_held', 'poll': result,
                        'conflicts': conflicts, 'save_did_not_overwrite': True,
                        'explicit_file_choice_applied': True})
        return {'cases': records, 'widget_actions': ui.actions}
    finally:
        editor.close()


def game_review(scene, path, out):
    document = load_direction(path)
    actor = reset_player(scene, puzzle=True, direction=profile_from_document(document))
    actor.x, actor.height, actor.z = -2., DECK, 16.
    actor.yaw, actor.phase, actor.clip = .45, .7, 'idle'
    actor.shot = camera_zone(actor.x, actor.z)
    q = scene.sequence
    q.seek(12.25)
    q._direction_camera_released = True
    watcher = LiveDirectionReload(path, document)
    clock = PollClock()
    scene.player.pose('idle', 0., dt=None)
    scene.render(actor, 99.)
    before = pixels(scene)
    Image.fromarray(before).save(out / '07-game-before-live-edit.png')
    retained = (id(q), q.elapsed, q.state, q.revealed, q.disc_placed, pose(actor),
                deepcopy(q.inventory), deepcopy(q.events), camera_signature(scene.last_camera))
    changed = deepcopy(document)
    changed['fog']['groups']['house-110']['opacity'] = .02
    save_direction(changed, path)
    result = clock.settle(lambda now: watcher.poll(scene, now=now))
    assert scene.sequence is q and q.direction == profile_from_document(changed)
    scene.render(actor, 99.)
    after = pixels(scene)
    Image.fromarray(after).save(out / '08-game-external-update.png')
    assert retained == (id(q), q.elapsed, q.state, q.revealed, q.disc_placed, pose(actor),
                        deepcopy(q.inventory), deepcopy(q.events), camera_signature(scene.last_camera))
    difference, _ = delta_report(before, after)
    assert difference['mean'] > .001
    return {'poll': result, 'image_difference': difference, 'sequence_identity_preserved': True,
            'position_time_inventory_events_camera_preserved': True, 'playhead': q.elapsed,
            'position': [actor.x, actor.height, actor.z]}


def run(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source, guards, protected = hashes(SOURCES), hashes(GUARDS), protected_hashes()
    live_config = DEFAULT_PATH.read_bytes()
    selection_path = ROOT / 'codex_selection.json'
    live_selection = optional_bytes(selection_path)
    pr.set_config_flags(pr.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.LOG_WARNING)
    pr.init_window(1440, 900, 'Muted live Canals direction review')
    scene = audio = None
    try:
        scene = Lake()
        audio = EncounterAudio(automated=True)
        with tempfile.TemporaryDirectory(prefix='haunted-canals-live-') as folder:
            path = Path(folder) / 'direction.json'
            save_direction(building_document(), path)
            editor = editor_review(scene, path, out)
            gameplay = game_review(scene, path, out)
        assert hashes(SOURCES) == source and hashes(GUARDS) == guards
        assert protected_hashes() == protected
        assert DEFAULT_PATH.read_bytes() == live_config
        assert optional_bytes(selection_path) == live_selection
        assert audio.muted and not pr.is_audio_device_ready()
        report = {'status': 'passed', 'editor': editor, 'gameplay': gameplay,
                  'source_sha256': source, 'protected_sha256': guards, 'protected_scenes': protected,
                  'live_direction_unchanged': True, 'live_codex_selection_unchanged': True,
                  'hidden': True, 'muted': True, 'audio_device_opened': False}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps(report, indent=2), flush=True)
        return report
    finally:
        if audio:audio.close()
        if scene:scene.close()
        pr.close_window()


if __name__ == '__main__':
    run()
