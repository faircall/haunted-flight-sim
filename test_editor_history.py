import copy
import unittest
from unittest.mock import patch
import g_editor_history as h
import g_editor
from test_puzzles import make_arena, place


class EditorHistoryTests(unittest.TestCase):
    def setUp(self):
        self.arena = make_arena().set("editor_mode", "tile")
        self.editor = g_editor.make_editor_state()
        self.assets = {"editor_state": self.editor}
        self.history = h.state(self.assets)

    def capture(self):
        return h.snapshot(self.arena, self.editor, "tile")

    def test_stroke_groups_and_keeps_runtime_data(self):
        before = self.capture()
        self.arena["tile_map"]["tiles"][3]["index"] = 3
        h.record(self.history, before, self.capture(), "mouse")
        before = self.capture()
        self.arena["tile_map"]["tiles"][4]["index"] = 3
        h.record(self.history, before, self.capture(), "mouse")
        h.flush(self.history)
        self.assertEqual(len(self.history["undo"]), 1)
        self.arena["player_info"]["health"] = 72
        self.arena["tile_map"]["tiles"][3]["decals"] = ["blood"]
        self.arena = h.undo(self.arena, self.assets)
        self.assertEqual(self.arena["tile_map"]["tiles"][3]["index"], 0)
        self.assertEqual(self.arena["tile_map"]["tiles"][4]["index"], 0)
        self.assertEqual(self.arena["tile_map"]["tiles"][3]["decals"], ["blood"])
        self.assertEqual(self.arena["player_info"]["health"], 72)
        self.assertGreater(self.arena["tile_map"]["geometry_revision"], 0)

    def test_place_delete_restore_identity_and_door_blocking(self):
        before = self.capture()
        door = place(self.arena, "key door")
        identity = door["id"]
        h.record(self.history, before, self.capture())
        self.arena = h.undo(self.arena, self.assets)
        self.assertNotIn(identity, self.arena["entities"]["puzzles"])
        door = place(self.arena, "key door")
        before = self.capture()
        self.arena["entities"]["puzzles"].pop(door["id"])
        h.record(self.history, before, self.capture())
        self.arena = h.undo(self.arena, self.assets)
        self.assertEqual(self.arena["entities"]["puzzles"][door["id"]]["persistent_id"], door["persistent_id"])
        self.assertTrue(self.arena["tile_map"]["tiles"][6 * 30 + 6]["puzzle_blocked"])

    def test_noop_and_limits(self):
        before = self.capture()
        self.arena["entities"]["emitters"] = {"a": {"type": "fire", "seed": 4}}
        baseline = self.capture()
        self.arena["entities"]["emitters"]["a"]["_fire_activity"] = (2., .5)
        h.record(self.history, baseline, self.capture())
        self.assertEqual(self.history["undo"], [])
        for i in range(h.LIMIT + 4):
            baseline = self.capture()
            self.arena["tile_map"]["tiles"][0]["index"] = i + 1
            h.record(self.history, baseline, self.capture())
        self.assertEqual(len(self.history["undo"]), h.LIMIT)

    def test_selection_default_materialization_is_not_an_edit(self):
        obj = {"position": {"x": 1}, "movement_settings": {}}
        self.arena["entities"]["brains"] = {"actor": obj}
        before = self.capture()
        self.editor.update(selected_collection="brains", selected_id="actor")
        obj["movement_settings"]["max_speed"] = 30
        obj["glow"] = {"enabled": False}
        h.record(self.history, before, self.capture())
        self.assertEqual(self.history["undo"], [])

    def test_entity_properties_preserve_health(self):
        obj = {"position": {"x": 1}, "health": 20, "glow": {"strength": .2}}
        self.arena["entities"]["brains"] = {"actor": obj}
        before = self.capture()
        obj["glow"]["strength"] = .9
        obj["health"] = 10
        h.record(self.history, before, self.capture())
        self.arena = h.apply(self.arena, self.editor, self.history["undo"].pop())
        self.assertEqual(obj["glow"]["strength"], .2)
        self.assertEqual(obj["health"], 10)

    def test_play_clears_history(self):
        self.history["undo"] = ["sentinel"]
        h.begin(self.arena.set("editor_mode", "play"), self.assets)
        self.assertNotIn("editor_history", self.assets)

    def test_environment_properties_and_tile_metadata(self):
        self.arena = self.arena.set("lighting_profile", {"ambient_strength": .3})
        self.arena["entities"]["lights"] = {"lamp": {"radius": 80., "position": {"x": 1}}}
        before = self.capture()
        self.arena["entities"]["lights"]["lamp"]["radius"] = 150.
        self.arena["lighting_profile"]["ambient_strength"] = .8
        self.arena["tile_map"]["tiles"][1].update(rain_exposure=.7, acoustic_zone_id=2, footstep_overlay="water")
        h.record(self.history, before, self.capture())
        self.arena = h.undo(self.arena, self.assets)
        self.assertEqual(self.arena["entities"]["lights"]["lamp"]["radius"], 80.)
        self.assertEqual(self.arena["lighting_profile"]["ambient_strength"], .3)
        self.assertNotIn("acoustic_zone_id", self.arena["tile_map"]["tiles"][1])
        self.assertNotIn("rain_exposure", self.arena["tile_map"]["tiles"][1])
        self.assertNotIn("footstep_overlay", self.arena["tile_map"]["tiles"][1])

    def test_animation_shortcut_and_numeric_edit_cancellation(self):
        import g_animation_authoring
        draft = g_animation_authoring.new_draft()
        document = copy.deepcopy(draft["document"])
        previous = document["REDHEAD_CUTOUT_RIG_DEFAULTS"]["movement_blend_response"]
        document["REDHEAD_CUTOUT_RIG_DEFAULTS"]["movement_blend_response"] = previous + 1
        g_animation_authoring.commit(draft, document)
        self.editor["redhead_animation_draft"] = draft
        with patch.object(h.pr, "is_key_down", side_effect=lambda k: k == h.pr.KeyboardKey.KEY_LEFT_CONTROL), patch.object(h.pr, "is_key_pressed", side_effect=lambda k: k == h.pr.KeyboardKey.KEY_Z), patch.object(h.pr, "is_mouse_button_down", return_value=False):
            h.begin(self.arena.set("editor_mode", "animation"), self.assets)
            self.assertEqual(previous, draft["document"]["REDHEAD_CUTOUT_RIG_DEFAULTS"]["movement_blend_response"])
            self.assets["ui_state"] = {"focused_id": "radius", "text_buffers": {"radius": "123"}, "pending_numeric_commits": {}}
            self.history["undo"] = ["not popped"]
            h.begin(self.arena, self.assets)
            self.assertIsNone(self.assets["ui_state"]["focused_id"])
            self.assertEqual(self.history["undo"], ["not popped"])

    def test_sequence_transaction_restores_definition_and_draft(self):
        self.arena = self.arena.set("world_sequences", {"sequences": {}})
        self.editor["sequence_editor"] = {"draft": {"points": [dict(x=1, y=2)]}}
        before = h.snapshot(self.arena, self.editor, "sequences")
        self.arena["world_sequences"]["sequences"]["path"] = {"points": [dict(x=1, y=2)]}
        self.editor["sequence_editor"]["draft"] = None
        h.record(self.history, before, h.snapshot(self.arena, self.editor, "sequences"))
        self.arena = h.apply(self.arena, self.editor, self.history["undo"].pop())
        self.assertEqual(self.arena["world_sequences"]["sequences"], {})
        self.assertEqual(self.editor["sequence_editor"]["draft"]["points"], [dict(x=1, y=2)])


if __name__ == "__main__":
    unittest.main()
