"""Native-window exploration review driven through the gameplay input adapter.

All writes go to artifacts; the shipped scene and the user's progress are never
changed. Captures include the actual low-resolution UI and native editor UI.
"""
from copy import deepcopy
import itertools
import json
import math
import pyray as pr
import g_temple_cameras as cameras
import g_inventory as inventory
import g_puzzles as puzzles


class Review:
    def __init__(self, gameplay, editor, folder):
        self.gameplay, self.editor, self.folder = gameplay, editor, folder
        folder.mkdir(parents=True, exist_ok=True)
        self.original_path = gameplay.scene.path
        gameplay.scene.path = folder/'edited.scene.json'
        self.done = False
        self.capture = None
        self.frames = 0
        self.steps = 0
        self.audio_events = 0
        self.missing_audio = set()
        self.metrics = {}
        self.script = self.run()

    def wait(self, frames=10, capture=None):
        for i in range(frames):
            if capture and i == frames-1:
                self.capture = capture
            yield set(), set(), False

    def press(self, *names):
        yield set(), set(names), False

    def confirm_pickup(self):
        yield from self.press('E')
        yield from self.wait(capture='pickup-confirmation' if not self.metrics else None)
        assert self.gameplay.modal and self.gameplay.modal['kind'] == 'dialogue'
        yield from self.press('LEFT', 'ENTER')
        yield from self.wait(8)
        assert self.gameplay.modal is None

    def move(self, destination):
        gameplay = self.gameplay
        for _ in range(700):
            dx, dz = destination[0]-gameplay.walk.x, destination[1]-gameplay.walk.y
            if math.hypot(dx, dz) < 2.2:
                yield from self.wait(1)
                return
            basis = gameplay.walk.intent.basis or cameras.movement_basis(gameplay.walk.director.shot)
            right, forward = basis
            choices = []
            for horizontal, vertical in itertools.product((-1, 0, 1), repeat=2):
                if not (horizontal or vertical):
                    continue
                x, z = right[0]*horizontal+forward[0]*vertical, right[1]*horizontal+forward[1]*vertical
                dot = (x*dx+z*dz)/math.hypot(x, z)
                keys = ({'d' if horizontal > 0 else 'a'} if horizontal else set()) | \
                       ({'w' if vertical > 0 else 's'} if vertical else set())
                choices.append((dot, keys))
            yield max(choices, key=lambda c: c[0])[1], set(), True
        raise AssertionError(('Route got stuck', destination, gameplay.walk.x, gameplay.walk.y))

    def run(self):
        g, editor = self.gameplay, self.editor
        assert g.can_walk(256, 334)
        assert not g.can_walk(472, 264) and not g.can_walk(488, 264)
        self.metrics['closed_door_blocks_both_leaves'] = True
        yield from self.wait(capture='01-exploration-start')
        yield from self.confirm_pickup()  # medicine is next to the initial spawn
        assert inventory.count(g.player['inventory'], 'health') == 1
        g.player['health'] = 75
        yield from self.press('TAB')
        frozen = (g.walk.x, g.walk.y, g.clock)
        for _ in range(8):
            yield {'d'}, set(), True
            assert (g.walk.x, g.walk.y, g.clock) == frozen
        yield from self.press('RIGHT', 'E')
        assert g.player['health'] == 100
        assert inventory.count(g.player['inventory'], 'health') == 0
        self.capture = '02-inventory'
        yield from self.wait(2)
        yield from self.press('TAB')
        yield from self.move((336, 334))
        yield from self.confirm_pickup()
        assert inventory.count(g.player['inventory'], 'key') == 1
        self.metrics['inventory_and_modal_pause'] = True
        yield from self.move((480, 334))
        yield from self.move((480, 286))
        self.capture = '03-locked-entrance'
        yield from self.wait(2)
        yield from self.press('E')
        assert not g.can_walk(480, 264)
        yield from self.press('E')
        assert g.can_walk(480, 264)
        yield from self.move((480, 248))
        self.capture = '04-open-temple'
        yield from self.wait(2)
        yield from self.press('E')
        yield from self.wait(capture='05-inspection-dialogue')
        for _ in range(6):
            if not g.modal:
                break
            if g.modal.get('choices') and g.modal['choice'] != 0:
                yield from self.press('LEFT')
            yield from self.press('ENTER')
            yield from self.wait(10)
        assert g.modal is None
        assert g.arena['puzzle_state']['facts']['inscription_button:altar-inscription']
        self.metrics['inspection_callback'] = True
        snapshot = deepcopy(g.snapshot())
        save_path = self.folder/'progress.json'
        g.save(save_path)
        g.player['inventory'][:] = [None]*8
        g.arena['puzzle_state']['objects'].clear()
        g.set_position(256, 334)
        g.load(save_path)
        assert g.snapshot() == snapshot
        self.metrics['progress_round_trip'] = True
        editor.toggle(g)
        scene = g.scene
        before = scene.checkpoint()
        bowl = scene.get('bowl:approach')
        bowl['position'] = [230, 344]
        bowl['rotation'] = 30
        scene.commit(before)
        assert scene.undo() and scene.redo()
        duplicate = scene.duplicate('temple-key')
        assert duplicate != 'temple-key'
        scene.add(dict(kind='note', position=[446, 334], text='Move the lantern here / 把灯移到这里', color=0), markup=True)
        scene.add(dict(kind='arrow', position=[422, 318], end=[446, 334], text='Lighting', color=1), markup=True)
        scene.add(dict(kind='area', position=[404, 200], end=[552, 252], text='Temple interior', color=2), markup=True)
        scene.save()
        from g_temple_scene import Scene
        assert Scene.load(scene.path).document == scene.document
        g.apply_scene()
        assert g.arena['entities']['emitters']['approach']['position']['x'] == 230
        assert 'bridge-medicine' not in g.arena['entities']['pickups']
        editor.selected = 'bowl:approach'
        editor.focus = [390, 268]
        editor.span = 240
        from g_temple_editor import gameplay_camera
        from g_temple_scene import prop_origin
        camera = editor.camera(gameplay_camera(g))
        prop = g.arena['entities']['lake_props']['lantern:0']
        origin = prop_origin('lantern:0', prop, editor.records)
        rec = editor.records[prop['asset'].removeprefix('baked:')]
        center = [(lo+hi)/2 for lo, hi in zip(rec['position_min'], rec['position_max'])]
        p = pr.get_world_to_screen_ex(pr.Vector3(origin[0]+center[0], origin[1]+center[2], origin[2]+center[1]), camera, 480, 270)
        assert editor.pick(camera, (p.x, p.y), g.arena['tile_map']) == 'lantern:0'
        self.metrics['native_prop_picking'] = True
        yield from self.wait(3, '06-editor-overhead')
        editor.overhead = False
        yield from self.wait(3, '07-editor-game-camera')
        editor.toggle(g)
        yield from self.wait(2, '08-progress-restored')
        self.metrics.update(scene_edit_round_trip=True, footsteps=self.steps, frames=self.frames,
                            accepted_audio_events=self.audio_events, missing_audio=sorted(self.missing_audio))
        assert self.steps > 5
        assert self.audio_events > 0
        assert not any(name.startswith('footsteps.') for name in self.missing_audio)
        (self.folder/'report.json').write_text(json.dumps(self.metrics, indent=2)+'\n', encoding='utf-8')
        self.done = True

    def input(self):
        self.frames += 1
        if self.frames > 1800:
            raise AssertionError('Exploration review exceeded its frame budget.')
        try:
            return next(self.script)
        except StopIteration:
            self.done = True
            return set(), set(), False

    def after_frame(self, target, camera):
        self.steps += len(self.gameplay.footsteps)
        if self.capture:
            image = pr.load_image_from_texture(target.texture)
            pr.image_flip_vertical(image)
            pr.export_image(image, str(self.folder/(self.capture+'.png')))
            pr.unload_image(image)
            self.capture = None

    def capture_ui(self):
        pr.rl_draw_render_batch_active()
        image = pr.load_image_from_screen()
        pr.export_image(image, str(self.folder/(self.capture+'-ui.png')))
        pr.unload_image(image)

    def audio_stats(self, stats):
        self.audio_events += stats['accepted_events']
        self.missing_audio.update(stats['missing_asset_families'])

    def close(self):
        self.gameplay.scene.path = self.original_path
