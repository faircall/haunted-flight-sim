"""Exploration and authoring regressions without a graphics window."""
from copy import deepcopy
from pathlib import Path
import json
import math
import tempfile
import unittest
from unittest.mock import patch
from pyrsistent import pmap

import g_update_and_render as game
import g_interactions as interactions
import g_inventory as inventory
import g_puzzles as puzzles
import g_temple_structure as structure
from moonlit_water_temple_blender import review_arena
from g_temple_gameplay import Exploration
from g_temple_scene import Scene, default_document
from g_temple_editor import ground_point
from g_temple_editor import Editor
import g_temple_editor as editor_module


def exploration(path=None):
    arena = structure.prepare(review_arena(game, pmap(dict(entities={},
        tile_map=game.make_tile_map(1, 1, 16, 16), player_info=game.make_default_player(0, 0, 0)))))
    return Exploration(arena, Scene(default_document(arena), path or 'unused-test-scene.json'))


class ExplorationTests(unittest.TestCase):
    def test_world_position_camera_chord_and_swept_collision(self):
        g = exploration()
        for _ in range(50):
            g.tick(.05, {'d'}, running=True)
        pos = game.tile_and_offset_to_absolute(g.arena['tile_map'], g.player['position'])
        self.assertEqual((pos['x'], pos['y']), (g.walk.x, g.walk.y))
        self.assertGreater(g.walk.distance, 0)
        g.set_position(480, 283)
        for _ in range(100):
            g.tick(1, {'w'}, running=True)
        self.assertGreaterEqual(g.walk.y, 275)
        self.assertFalse(g.can_walk(472, 264))
        self.assertFalse(g.can_walk(488, 264))

    def test_pickup_door_loop_and_occupied_other_leaf(self):
        g = exploration()
        g.set_position(480, 286)
        g.tick(.05, pressed={'E'})
        self.assertIn('locked', g.arena['puzzle_runtime']['message'])
        key = g.arena['entities']['puzzles']['temple-key']
        g.arena = interactions.take(g.arena, ['puzzles', key['id']])
        g.tick(.05, pressed={'E'})
        self.assertFalse(g.can_walk(480, 264))
        g.tick(.05, pressed={'E'})
        self.assertTrue(g.can_walk(480, 264))
        # The non-selected right half must also prevent a door closing on us.
        g.set_position(488, 264)
        g.activate_door(g.arena['entities']['puzzles']['temple-entrance:0'])
        self.assertTrue(g.can_walk(488, 264))
        self.assertIn('occupied', g.arena['puzzle_runtime']['message'])

    def test_modal_open_close_and_editor_frames_own_movement(self):
        g = exploration()
        frozen = (g.walk.x, g.walk.y, g.clock)
        g.tick(.05, {'d'}, True, {'TAB'})
        for _ in range(5):
            g.tick(.05, {'d'}, True)
        self.assertEqual((g.walk.x, g.walk.y, g.clock), frozen)
        g.tick(.05, {'d'}, True, {'TAB'})
        self.assertEqual((g.walk.x, g.walk.y, g.clock), frozen)
        self.assertFalse(g.footsteps)
        g.tick(.05, {'d'}, True, editor=True)
        self.assertEqual((g.walk.x, g.walk.y, g.clock), frozen)
        g.arena = interactions.open_dialogue(g.arena, ['test'])
        with patch.object(interactions.text, 'wrap', return_value=['test']):
            g.tick(.05, {'d'}, True, {'ENTER'})
        for _ in range(6):
            g.tick(.05, {'d'}, True)
        self.assertIsNone(g.modal)
        self.assertEqual((g.walk.x, g.walk.y, g.clock), frozen)
        g.tick(.05, {'d'}, True)
        self.assertGreater(g.walk.x, frozen[0])

    def test_footsteps_use_resolved_distance_and_stop_when_blocked(self):
        g = exploration()
        count = 0
        for _ in range(40):
            g.tick(.05, {'d'}, True)
            count += len(g.footsteps)
        self.assertGreater(count, 0)
        g.set_position(480, 283)
        for _ in range(40):
            g.tick(.05, {'w'}, True)
        self.assertFalse(g.footsteps)
        g.tick(.05, pressed={'TAB'})
        for _ in range(30):
            g.tick(.05, {'d'}, True)
            self.assertFalse(g.footsteps)

    def test_progress_round_trip_fresh_runtime_and_failed_load_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'progress.json'
            g = exploration()
            g.arena = interactions.take(g.arena, ['puzzles', 'temple-key'])
            g.arena = interactions.take(g.arena, ['pickups', 'bridge-medicine'])
            g.tick(.05)
            g.set_position(480, 286)
            g.tick(.05, pressed={'E'})
            g.tick(.05, pressed={'E'})
            g.set_position(480, 248)
            puzzles.set_fact(g.arena, 'visited', True)
            g.save(path)
            restored = exploration()
            restored.load(path)
            self.assertEqual(restored.snapshot(), g.snapshot())
            self.assertTrue(restored.can_walk(480, 264))
            self.assertNotIn('bridge-medicine', restored.arena['entities']['pickups'])
            self.assertIsNone(restored.modal)
            value = json.loads(path.read_text())
            value['player']['inventory'][0]['count'] = -2
            path.write_text(json.dumps(value))
            before = restored.snapshot()
            with self.assertRaises(ValueError):
                restored.load(path)
            self.assertEqual(before, restored.snapshot())

    def test_scene_edits_move_collision_light_and_preserve_collected_state(self):
        g = exploration()
        g.arena = interactions.take(g.arena, ['pickups', 'bridge-medicine'])
        g.tick(.05)
        before = g.scene.checkpoint()
        g.scene.get('bowl:approach')['position'] = [300, 334]
        g.scene.commit(before)
        g.apply_scene()
        self.assertFalse(g.can_walk(300, 334))
        self.assertTrue(g.can_walk(222, 334))
        self.assertEqual(g.arena['entities']['emitters']['approach']['position'], dict(x=300, y=334))
        self.assertNotIn('bridge-medicine', g.arena['entities']['pickups'])
        g.scene.delete('bowl:approach')
        g.apply_scene()
        self.assertTrue(g.can_walk(300, 334))
        self.assertNotIn('approach', g.arena['entities']['emitters'])

    def test_full_inventory_key_pickup_remains_available(self):
        g = exploration()
        g.player['inventory'][:] = [dict(kind='health', count=1) for _ in range(8)]
        g.arena = interactions.take(g.arena, ['puzzles', 'temple-key'])
        self.assertFalse(g.arena['puzzle_state']['objects'].get('temple-key', {}).get('collected'))
        self.assertEqual(inventory.count(g.player['inventory'], 'key'), 0)

    def test_leaving_editor_recovers_from_a_prop_placed_on_player(self):
        g = exploration()
        editor = Editor(g.scene)
        editor.toggle(g)
        g.scene.get('bowl:approach')['position'] = [g.walk.x, g.walk.y]
        editor.toggle(g)
        self.assertTrue(g.can_walk(g.walk.x, g.walk.y))
        self.assertEqual(g.player['audio_step_state']['distance'], 0)


class SceneTests(unittest.TestCase):
    def editor_frame(self, editor, gameplay, pressed=(), held=(), mouse=(1200, 790), click=False, release=False):
        pr = editor_module.pr
        with patch.object(pr, 'is_key_pressed', side_effect=lambda key: key in pressed), \
             patch.object(pr, 'is_key_down', side_effect=lambda key: key in held), \
             patch.object(pr, 'get_mouse_position', return_value=pr.Vector2(*mouse)), \
             patch.object(pr, 'get_mouse_wheel_move', return_value=0), \
             patch.object(pr, 'is_mouse_button_pressed', return_value=click), \
             patch.object(pr, 'is_mouse_button_released', return_value=release), \
             patch.object(pr, 'is_mouse_button_down', return_value=click), \
             patch.object(pr, 'get_char_pressed', return_value=0):
            editor.update(gameplay, None, .05)

    def test_editor_keyboard_duplicate_nudge_rotate_undo_save_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            g = exploration(Path(folder)/'scene.json')
            editor = Editor(g.scene)
            editor.toggle(g)
            editor.selected = 'temple-key'
            pr = editor_module.pr
            self.editor_frame(editor, g, {pr.KEY_D}, {pr.KEY_LEFT_CONTROL})
            duplicate = editor.selected
            self.assertNotEqual(duplicate, 'temple-key')
            self.editor_frame(editor, g, {pr.KEY_RIGHT, pr.KEY_E})
            self.assertEqual(g.scene.get(duplicate)['position'], [360, 334])
            self.assertEqual(g.scene.get(duplicate)['rotation'], 40)
            self.editor_frame(editor, g, {pr.KEY_Z}, {pr.KEY_LEFT_CONTROL})
            self.assertEqual(g.scene.get(duplicate)['position'], [356, 334])
            self.editor_frame(editor, g, {pr.KEY_Y}, {pr.KEY_LEFT_CONTROL})
            self.editor_frame(editor, g, {pr.KEY_S}, {pr.KEY_LEFT_CONTROL})
            self.assertFalse(g.scene.dirty)
            self.editor_frame(editor, g, {pr.KEY_DELETE})
            self.assertIsNone(g.scene.get(duplicate))
            self.editor_frame(editor, g, {pr.KEY_O}, {pr.KEY_LEFT_CONTROL})
            self.assertIsNotNone(g.scene.get(duplicate))

    def test_editor_mouse_place_note_arrow_and_text_commit(self):
        g = exploration()
        editor = Editor(g.scene)
        editor.toggle(g)
        pr = editor_module.pr
        editor.tool, editor.palette_index = 1, 1
        self.editor_frame(editor, g, mouse=(570, 405), click=True)
        medicine = g.scene.get(editor.selected)
        self.assertEqual(medicine['kind'], 'medicine')
        self.assertEqual(medicine['position'], [256, 336])
        editor.tool = 2
        self.editor_frame(editor, g, mouse=(570, 405), click=True)
        note_id = editor.selected
        codes = iter([ord(c) for c in 'Move this lamp']+[0])
        with patch.object(pr, 'get_char_pressed', side_effect=lambda: next(codes)), \
             patch.object(pr, 'is_key_pressed', side_effect=lambda key: key == pr.KEY_ENTER):
            editor.update(g, None, .05)
        self.assertEqual(g.scene.get(note_id)['text'], 'Move this lamp')
        g.scene.undo()
        self.assertEqual(g.scene.get(note_id)['text'], '')
        editor.tool = 3
        self.editor_frame(editor, g, mouse=(570, 405), click=True)
        self.assertIsNotNone(editor.pending)
        self.editor_frame(editor, g, mouse=(610, 405), click=True)
        self.assertEqual(g.scene.get(editor.selected)['kind'], 'arrow')
        self.assertIsNone(editor.pending)

    def test_undo_redo_serialization_unicode_and_distinct_duplicate_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            g = exploration(Path(folder)/'scene.json')
            scene = g.scene
            initial = scene.checkpoint()
            identity = scene.add(dict(kind='arrow', position=[400, 310], end=[480, 290],
                text='这里需要更宽的通道', color=1), markup=True)
            self.assertTrue(scene.dirty)
            self.assertTrue(scene.undo())
            self.assertEqual(scene.document, initial)
            self.assertTrue(scene.redo())
            duplicate = scene.duplicate('temple-key')
            self.assertNotEqual(duplicate, 'temple-key')
            scene.save()
            self.assertFalse(scene.dirty)
            self.assertEqual(Scene.load(scene.path).document, scene.document)
            self.assertEqual(scene.get(identity)['text'], '这里需要更宽的通道')
            scene.delete(identity)
            scene.reload()
            self.assertIsNotNone(scene.get(identity))
            scene.undo()
            self.assertIsNone(scene.get(identity))

    def test_invalid_scene_never_replaces_running_document(self):
        scene = exploration().scene
        invalid = scene.checkpoint()
        invalid['objects'].append(deepcopy(invalid['objects'][0]))
        with self.assertRaises(ValueError):
            Scene(invalid)
        invalid = scene.checkpoint()
        invalid['spawn'] = [float('nan'), 0]
        with self.assertRaises(ValueError):
            Scene(invalid)

    def test_overhead_and_side_ground_pick_uses_elevated_floor(self):
        g = exploration()
        floor = lambda x, z: structure.floor_height(g.arena['tile_map'], x, z)
        p = ground_point((480, 400, 334), (480, 0, 334), (0, 0, -1), 180, (240, 135), floor)
        self.assertEqual(p, (480., 334.))
        self.assertEqual(floor(*p), 16)
        p = ground_point((480, 200, 450), (480, 24, 240), (0, 1, 0), 180, (240, 135), floor)
        self.assertAlmostEqual(p[0], 480)
        self.assertAlmostEqual(p[1], 240)


if __name__ == '__main__':
    unittest.main()
