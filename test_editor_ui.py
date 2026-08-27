import math
import pickle
import unittest

import g_editor
import g_graphics
import g_ui


class EnvironmentEditorDataTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = {"tile_width": 16, "tile_height": 16}

    def test_factories_return_fresh_nested_data(self):
        position = {"tile_x": 1, "tile_y": 2, "x": 3.0, "y": 4.0}
        first = g_editor.make_default_spot_light(position)
        second = g_editor.make_default_spot_light(position)
        first["position"]["x"] = 99.0
        first["color"][0] = 0.0
        first["direction"]["x"] = 0.0
        self.assertEqual(second["position"]["x"], 3.0)
        self.assertEqual(second["color"][0], 1.0)
        self.assertEqual(second["direction"]["x"], 1.0)

    def test_environment_registry_has_explicit_editor_dispatch(self):
        required = {"target_collection", "factory", "display_name", "icon", "debug_color", "inspector", "hit_test", "handles", "handle_hit_test", "manipulate"}

        for placement_type in g_editor.PLACEMENT_TYPES:
            self.assertTrue(required.issubset(g_editor.ENVIRONMENT_OBJECT_REGISTRY[placement_type]))

    def test_stable_id_allocation_does_not_reuse_deleted_ids(self):
        entities = {}
        first = g_editor.allocate_environment_object_id(entities, "light")
        second = g_editor.allocate_environment_object_id(entities, "fog")
        self.assertEqual(first, "light:1")
        self.assertEqual(second, "fog:2")
        entities.setdefault("lights", {})[first] = {}
        del entities["lights"][first]
        self.assertEqual(g_editor.allocate_environment_object_id(entities, "light"), "light:3")

    def test_world_tile_conversion_canonicalises_offsets(self):
        position = g_editor.world_to_tile_position({"x": -1.5, "y": 34.25}, self.tile_map)
        self.assertEqual(position["tile_x"], -1)
        self.assertEqual(position["tile_y"], 2)
        self.assertAlmostEqual(position["x"], 14.5)
        self.assertAlmostEqual(position["y"], 2.25)
        self.assertEqual(g_editor.tile_position_to_world(position, self.tile_map), {"x": -1.5, "y": 34.25})

    def test_light_and_fog_hit_testing(self):
        position = g_editor.world_to_tile_position({"x": 32.0, "y": 48.0}, self.tile_map)
        light = g_editor.make_default_point_light(position)
        fog = g_editor.make_default_fog_volume(position)
        self.assertTrue(g_editor.hit_test_light({"x": 32.0, "y": 48.0}, light, self.tile_map))
        self.assertTrue(g_editor.hit_test_light({"x": 152.0, "y": 48.0}, light, self.tile_map))
        self.assertFalse(g_editor.hit_test_light({"x": 80.0, "y": 80.0}, light, self.tile_map))
        self.assertTrue(g_editor.point_in_fog_volume({"x": 32.0, "y": 48.0}, fog, self.tile_map))
        self.assertFalse(g_editor.point_in_fog_volume({"x": 200.0, "y": 200.0}, fog, self.tile_map))

    def test_overlapping_selection_prefers_selected_then_small_handle(self):
        position = g_editor.world_to_tile_position({"x": 32.0, "y": 48.0}, self.tile_map)
        fog_position = g_editor.world_to_tile_position({"x": 40.0, "y": 48.0}, self.tile_map)
        entities = {
            "lights": {"light:1": g_editor.make_default_point_light(position)},
            "fog_volumes": {"fog:2": g_editor.make_default_fog_volume(fog_position)},
            "next_environment_object_id": 3
        }
        state = g_editor.make_editor_state()
        state["selected_kind"] = "fog_volume"
        state["selected_id"] = "fog:2"
        self.assertEqual(g_editor.select_environment_object_at(entities, state, {"x": 32.0, "y": 48.0}, self.tile_map), ("fog_volume", "fog:2"))
        state["selected_kind"] = None
        state["selected_id"] = None
        self.assertEqual(g_editor.select_environment_object_at(entities, state, {"x": 32.0, "y": 48.0}, self.tile_map), ("light", "light:1"))

    def test_duplicate_gets_new_id_and_independent_nested_data(self):
        entities = {}
        position = g_editor.world_to_tile_position({"x": 32.0, "y": 48.0}, self.tile_map)
        kind, object_id = g_editor.create_environment_object(entities, "spot_light", position)
        state = g_editor.make_editor_state()
        state["selected_kind"] = kind
        state["selected_id"] = object_id
        duplicate_id = g_editor.duplicate_selected_environment_object(entities, state, self.tile_map)
        entities["lights"][duplicate_id]["color"][0] = 0.0
        entities["lights"][duplicate_id]["direction"]["x"] = 0.0
        self.assertNotEqual(object_id, duplicate_id)
        self.assertEqual(entities["lights"][object_id]["color"][0], 1.0)
        self.assertEqual(entities["lights"][object_id]["direction"]["x"], 1.0)

    def test_delete_clears_selection_and_does_not_seed_replacement(self):
        entities = {}
        kind, object_id = g_editor.create_environment_object(entities, "fog_volume", g_editor.world_to_tile_position({"x": 0.0, "y": 0.0}, self.tile_map))
        state = g_editor.make_editor_state()
        state["selected_kind"] = kind
        state["selected_id"] = object_id
        self.assertTrue(g_editor.delete_selected_environment_object(entities, state))
        self.assertEqual(entities["fog_volumes"], {})
        self.assertIsNone(state["selected_id"])

    def test_old_render_style_migrates_to_world(self):
        entities = {"lights": {"old": {"type": "point"}}, "fog_volumes": {}}
        g_editor.migrate_environment_data(entities)
        self.assertEqual(entities["lights"]["old"]["render_style"], "world")

    def test_spot_direction_and_angles_are_constrained(self):
        direction = g_editor.normalize_spot_direction({"x": 3.0, "y": 4.0})
        self.assertAlmostEqual(math.hypot(direction["x"], direction["y"]), 1.0)
        self.assertEqual(g_editor.normalize_spot_direction({"x": 0.0, "y": 0.0}), {"x": 1.0, "y": 0.0})
        inner, outer = g_editor.clamp_spot_angles(40.0, 20.0)
        self.assertLess(inner, outer)
        self.assertGreaterEqual(outer - inner, 0.5)

    def test_authored_environment_data_serialises_without_editor_state(self):
        entities = {}
        g_editor.create_environment_object(entities, "point_light", g_editor.world_to_tile_position({"x": 10.0, "y": 20.0}, self.tile_map))
        g_editor.create_environment_object(entities, "fog_volume", g_editor.world_to_tile_position({"x": 30.0, "y": 40.0}, self.tile_map))
        restored = pickle.loads(pickle.dumps(entities))
        self.assertEqual(restored["next_environment_object_id"], 3)
        self.assertNotIn("editor_state", restored)

    def test_player_readability_light_has_constrained_capabilities(self):
        player = {"position": {"tile_x": 1, "tile_y": 1, "x": 0.0, "y": 0.0}}
        light = g_graphics.make_player_pointlight(player, self.tile_map)
        self.assertEqual(light["render_style"], "readability")
        self.assertTrue(light["affects_scene"])
        self.assertFalse(light["affects_fog"])
        self.assertFalse(light["affects_ai"])
        self.assertFalse(light["casts_wall_shadows"])


class ImmediateModeUIHelperTests(unittest.TestCase):
    def test_numeric_input_parsing(self):
        self.assertEqual(g_ui.parse_numeric_input("-1.25e2"), -125.0)
        self.assertEqual(g_ui.parse_numeric_input("42", True), 42)
        self.assertEqual(g_ui.parse_numeric_input("1e2", True), 100)
        self.assertIsNone(g_ui.parse_numeric_input("-"))
        self.assertIsNone(g_ui.parse_numeric_input("."))
        self.assertIsNone(g_ui.parse_numeric_input("1e"))

    def test_slider_clamping_and_snapping(self):
        self.assertEqual(g_ui.ui_clamp(12.0, 0.0, 10.0), 10.0)
        self.assertEqual(g_ui.ui_clamp(-1.0, 0.0, 10.0), 0.0)
        self.assertAlmostEqual(g_ui.ui_snap_value(1.24, 0.1), 1.2)

    def test_numeric_focus_change_queues_a_clamped_commit(self):
        state = g_ui.make_ui_state()
        state["focused_id"] = "number:a"
        state["text_buffers"]["number:a"] = "12.5"
        state["numeric_edit_metadata"]["number:a"] = {"original_value": 2.0, "integer": False, "minimum": 0.0, "maximum": 10.0}
        g_ui.ui_queue_focused_numeric_commit(state)
        self.assertEqual(state["pending_numeric_commits"]["number:a"], 10.0)
        self.assertIsNone(state["focused_id"])


if __name__ == "__main__":
    unittest.main()
