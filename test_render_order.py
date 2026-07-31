import unittest

import g_render_order


class RenderOrderTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = {"tile_width": 16, "tile_height": 16}
        self.assets = {
            "sprite_sheets": {
                "blue_oxford_texture_sheet": {"right_frame_start": 2},
                "red_head_texture_sheet": {"left_frame_start": 3}
            },
            "textures": {}
        }

    def test_metadata_defaults_are_fresh(self):
        first = g_render_order.make_default_entity_render_metadata("buddha")
        second = g_render_order.make_default_entity_render_metadata("buddha")
        first["render_base_offset"]["y"] = 2.0
        self.assertEqual(second["render_base_offset"]["y"], 61.0)

    def test_ensure_preserves_authored_metadata(self):
        entity = {"type": "buddha", "visual_height": 90.0, "render_base_offset": {"x": 1.0, "y": 2.0}}
        g_render_order.ensure_entity_render_metadata(entity)
        self.assertEqual(entity["visual_height"], 90.0)
        self.assertEqual(entity["render_base_offset"], {"x": 1.0, "y": 2.0})
        self.assertTrue(entity["occludes_player"])

    def test_sort_uses_base_y(self):
        items = [
            {"sort_layer": "world", "sort_y": 20.0, "id": "later"},
            {"sort_layer": "world", "sort_y": 10.0, "id": "earlier"}
        ]
        result = g_render_order.sort_world_render_items(items)
        self.assertEqual([item["id"] for item in result], ["earlier", "later"])

    def test_builder_preserves_current_sprite_anchors(self):
        player = {"id": "player", "position": {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0}, "animation_frame": "right_frame_start"}
        red_head = {"type": "red head", "position": {"tile_x": 2, "tile_y": 4, "x": 4.0, "y": 5.0}, "animation_frame": "left_frame_start"}
        items = g_render_order.build_sorted_world_render_items({"brains": {7: red_head}}, player, self.tile_map, self.assets)
        player_item = g_render_order.get_player_render_item(items)
        red_item = next(item for item in items if item["source"] == "red head")
        self.assertEqual(player_item["dest_rect"]["x"], 20.0)
        self.assertEqual(player_item["source_rect"]["x"], 64.0)
        self.assertEqual(red_item["dest_rect"]["x"], 12.0)
        self.assertEqual(red_item["source_rect"]["x"], 72.0)

    def test_player_occluder_requires_later_sort_and_overlap(self):
        player = {"source": "player", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}}
        behind = {"source": "buddha", "sort_y": 10.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        in_front = {"source": "buddha", "sort_y": 30.0, "bounds_world": {"x": 5.0, "y": 5.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        distant = {"source": "buddha", "sort_y": 40.0, "bounds_world": {"x": 50.0, "y": 50.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": True}
        self.assertEqual(g_render_order.find_player_occluders([behind, player, in_front, distant]), [in_front])

    def test_outline_filter_is_explicit(self):
        player = {"source": "player", "sort_y": 20.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}}
        red_head = {"source": "red head", "sort_y": 30.0, "bounds_world": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0}, "occludes_player": True, "outline_player_when_behind": False}
        self.assertEqual(g_render_order.find_player_occluders([player, red_head]), [red_head])
        self.assertEqual(g_render_order.find_player_occluders([player, red_head], require_outline=True), [])

    def test_buddha_base_line_changes_front_back_order(self):
        buddha = {"type": "buddha", "position": {"tile_x": 5, "tile_y": 5, "x": 0.0, "y": 0.0}}
        player = {"id": "player", "position": {"tile_x": 5, "tile_y": 5, "x": 0.0, "y": 0.0}}
        behind_items = g_render_order.build_sorted_world_render_items({"brains": {"b": buddha}}, player, self.tile_map, self.assets)
        self.assertEqual([item["source"] for item in behind_items], ["player", "buddha"])
        self.assertEqual([item["source"] for item in g_render_order.find_player_occluders(behind_items)], ["buddha"])
        player["position"]["y"] = 48.0
        in_front_items = g_render_order.build_sorted_world_render_items({"brains": {"b": buddha}}, player, self.tile_map, self.assets)
        self.assertEqual([item["source"] for item in in_front_items], ["buddha", "player"])
        self.assertEqual(g_render_order.find_player_occluders(in_front_items), [])


if __name__ == "__main__":
    unittest.main()
