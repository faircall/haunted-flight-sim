import copy
import importlib
import pickle
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from pyrsistent import pmap
import g_update_and_render as game
import g_puzzles as p
import g_puzzle_ui as ui
import g_editor
import g_light_visibility as visibility


def make_arena():
    return p.ensure_arena(pmap({"entities": {}, "tile_map": game.make_tile_map(30, 20, 16, 16),
                                "player_info": game.make_default_player(24, 24, 0)}))


def place(arena, kind, x=6, y=6, group=1):
    obj = {"type": kind, "position": {"tile_x": x, "tile_y": y, "x": 8., "y": 8.}}
    game.give_entity_stats_from_type(obj, kind)
    collection = arena["entities"].setdefault("puzzles", {})
    obj["id"] = g_editor.allocate_gameplay_entity_id(collection)
    obj["puzzle_group"] = group
    collection[obj["id"]] = obj
    p.sync_door_tiles(arena)
    return obj


class PuzzleTests(unittest.TestCase):
    def setUp(self):
        self.arena = make_arena()

    def use(self, obj, code=None):
        self.arena = p.interact(self.arena, obj["persistent_id"], code)

    def test_key_unlock_open_close_and_group_isolation(self):
        door = place(self.arena, "key door")
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))
        wrong_key = place(self.arena, "puzzle key", group=2)
        self.use(wrong_key)
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))
        key = place(self.arena, "puzzle key")
        self.use(key)
        self.use(key)
        self.assertEqual(self.arena["puzzle_state"]["inventory"]["1"], 1)
        self.use(door)
        self.assertTrue(p.object_state(self.arena, door)["unlocked"])
        self.assertFalse(p.object_state(self.arena, door).get("open", False))
        self.use(door)
        self.assertTrue(p.object_state(self.arena, door)["open"])
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door)["open"])
        self.assertEqual([e["type"] for e in self.arena["puzzle_runtime"]["sounds"]],
                         ["reload_start", "weapon_unholster", "weapon_unholster"])

    def test_authored_conditions_spawn_once_even_after_save_reload_and_death(self):
        door = place(self.arena, "authored door")
        key = place(self.arena, "puzzle key", x=2)
        lever = place(self.arena, "puzzle lever", x=3)
        marker = place(self.arena, "puzzle spawn", x=12)
        self.use(door)
        self.use(key)
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))
        self.use(lever)
        self.use(door)
        self.assertTrue(p.object_state(self.arena, door)["unlocked"])
        self.assertEqual(len(self.arena["entities"]["brains"]), 1)
        self.assertTrue(self.arena["puzzle_state"]["facts"]["ritual_unlocked:" + door["persistent_id"]])
        self.arena["entities"]["brains"].clear()
        self.arena = pickle.loads(pickle.dumps(self.arena))
        importlib.reload(p.data)
        self.use(door)
        self.use(door)
        self.assertEqual(len(self.arena["entities"]["brains"]), 0)

    def test_authored_bad_marker_does_not_partially_unlock(self):
        door = place(self.arena, "authored door")
        self.use(place(self.arena, "puzzle key", x=2))
        self.use(place(self.arena, "puzzle lever", x=3))
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))
        marker = place(self.arena, "puzzle spawn", x=12)
        self.arena["tile_map"]["tiles"][6 * 30 + 12]["force_collidable"] = True
        self.use(door)
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))
        self.assertFalse(self.arena["puzzle_runtime"]["sounds"])

    def test_lever_opens_and_closes_only_matching_doors(self):
        door = place(self.arena, "lever door")
        other = place(self.arena, "lever door", x=8, group=2)
        lever = place(self.arena, "puzzle lever", x=3)
        self.use(lever)
        self.assertTrue(p.object_state(self.arena, door)["open"])
        self.assertFalse(p.object_state(self.arena, other).get("open"))
        self.use(lever)
        self.assertFalse(p.object_state(self.arena, door)["open"])

    def test_code_requires_four_digits_including_leading_zero(self):
        door = place(self.arena, "code door")
        keypad = place(self.arena, "puzzle keypad", x=3)
        self.use(keypad)
        for code in ("451", "1451", "00451", "abcd"):
            self.use(keypad, code)
            self.assertFalse(p.object_state(self.arena, door).get("open"))
        self.use(keypad, "0451")
        self.assertTrue(p.object_state(self.arena, door)["open"])
        self.assertIsNone(self.arena["puzzle_runtime"]["keypad"])

    def test_closed_door_collision_bullets_light_and_original_floor_preserved(self):
        door = place(self.arena, "key door")
        tm = self.arena["tile_map"]
        tile = tm["tiles"][6 * 30 + 6]
        tile["shape_index"] = 1
        self.assertTrue(game.get_tile_shape_collision(dict(tile_x=6, tile_y=6, x=15, y=15), tm)["collides"])
        self.assertIsNotNone(game.first_solid_tile_hit_on_segment({"x": 80, "y": 104}, {"x": 120, "y": 104}, tm))
        self.assertEqual(visibility.build_light_collision_grid(tm, {2})["shape_codes"][186], 0)
        revision = tm["geometry_revision"]
        p.unlock_door(self.arena, door)
        p.set_door_open(self.arena, door, True)
        self.assertGreater(tm["geometry_revision"], revision)
        self.assertFalse(game.tile_is_collidable(tile, tm))
        self.assertEqual(tile["index"], 0)
        self.assertEqual(tile["shape_index"], 1)
        self.assertIsNone(game.first_solid_tile_hit_on_segment({"x": 80, "y": 104}, {"x": 120, "y": 104}, tm))
        self.assertEqual(visibility.build_light_collision_grid(tm, {2})["shape_codes"][186], 255)

    def test_occupied_door_cannot_close(self):
        door = place(self.arena, "lever door")
        lever = place(self.arena, "puzzle lever", x=3)
        self.use(lever)
        self.arena["player_info"]["position"] = dict(door["position"])
        self.use(lever)
        self.assertTrue(p.object_state(self.arena, door)["open"])
        self.assertTrue(p.object_state(self.arena, lever)["active"])

    def test_editor_ids_persist_and_move_delete_clear_geometry(self):
        door = place(self.arena, "key door")
        identity = door["persistent_id"]
        state = g_editor.make_editor_state()
        state.update(selected_kind="gameplay_entity", selected_collection="puzzles", selected_id=door["id"])
        self.assertIs(g_editor.get_selected_gameplay_entity(self.arena["entities"], state), door)
        g_editor.move_selected_gameplay_entity(self.arena["entities"], state, {"x": 168, "y": 104}, self.arena["tile_map"])
        p.sync_door_tiles(self.arena)
        self.assertEqual(identity, door["persistent_id"])
        self.assertFalse(self.arena["tile_map"]["tiles"][186]["puzzle_blocked"])
        self.assertTrue(g_editor.delete_selected_gameplay_entity(self.arena["entities"], state))
        p.sync_door_tiles(self.arena)
        replacement = place(self.arena, "key door")
        self.assertNotEqual(identity, replacement["persistent_id"])

    def test_interaction_does_not_reach_through_walls(self):
        key = place(self.arena, "puzzle key", x=3, y=1)
        self.assertIsNone(p.nearest_interactable(self.arena))  # too far
        self.arena["player_info"]["position"] = dict(tile_x=1, tile_y=1, x=15, y=8)
        self.assertIs(p.nearest_interactable(self.arena), key)
        self.arena["tile_map"]["tiles"][32]["index"] = 3
        self.assertIsNone(p.nearest_interactable(self.arena))

    def test_keypad_keyboard_submit_cancel_and_input_gate(self):
        door = place(self.arena, "code door")
        keypad = place(self.arena, "puzzle keypad", x=1, y=1)
        self.use(keypad)
        with patch.object(ui.pr, "get_char_pressed", side_effect=[48, 52, 53, 49, 0]), \
             patch.object(ui.pr, "is_key_pressed", side_effect=lambda key: key == ui.pr.KeyboardKey.KEY_ENTER):
            self.arena = ui.update_input(self.arena, True, .01)
        self.assertTrue(p.object_state(self.arena, door)["open"])
        self.use(keypad)
        with patch.object(ui.pr, "is_key_pressed", return_value=True):
            self.arena = ui.update_input(self.arena, True, .01)
        self.assertIsNone(self.arena["puzzle_runtime"]["keypad"])
        self.use(keypad)
        self.arena = ui.update_input(self.arena, False, .01)
        self.assertIsNone(self.arena["puzzle_runtime"]["keypad"])

    def test_missing_handler_is_diagnostic_and_arena_return_is_used(self):
        door = place(self.arena, "authored door")
        door["on_unlock"] = "missing"
        self.use(door)
        self.assertIn("Unknown", self.arena["puzzle_runtime"]["message"])
        with patch.dict(p.data.HANDLERS, {"missing": lambda arena, event: arena.set("custom_fact", 42)}):
            self.use(door)
        self.assertEqual(self.arena["custom_fact"], 42)

    def test_actual_save_load_keeps_progress_but_drops_modal_and_pending_audio(self):
        door = place(self.arena, "key door")
        key = place(self.arena, "puzzle key")
        self.use(key)
        self.use(door)
        self.arena["puzzle_runtime"]["keypad"] = "stale"
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(game, "g_save_directory", directory), patch.object(game.pr, "draw_text"):
            game.save_state(self.arena)
            files = list(Path(directory).glob("*.pkl"))
            self.assertEqual(len(files), 1)
            loaded = game.load_state(files[0].name)
        self.assertNotIn("puzzle_runtime", loaded)
        loaded = p.ensure_arena(loaded)
        self.assertTrue(p.has_key(loaded, door))
        self.assertTrue(p.object_state(loaded, door)["unlocked"])
        self.assertEqual(loaded["puzzle_runtime"]["sounds"], [])

    def test_reset_preserves_definitions_and_removes_only_puzzle_enemies(self):
        door = place(self.arena, "authored door")
        key = place(self.arena, "puzzle key", x=2)
        lever = place(self.arena, "puzzle lever", x=3)
        place(self.arena, "puzzle spawn", x=12)
        for obj in (key, lever, door):
            self.use(obj)
        self.arena["entities"]["brains"][123] = {"type": "red head"}
        self.arena = p.reset_progress(self.arena)
        self.assertEqual(list(self.arena["entities"]["brains"]), [123])
        self.assertEqual(len(self.arena["entities"]["puzzles"]), 4)
        self.assertFalse(p.has_key(self.arena, door))
        self.assertFalse(p.object_state(self.arena, key).get("collected"))
        self.assertFalse(p.object_state(self.arena, door).get("unlocked"))


if __name__ == "__main__":
    unittest.main()
