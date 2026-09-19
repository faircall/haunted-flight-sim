import pickle
import unittest

import g_editor
import g_graphics
import g_render_order as render
import g_update_and_render as game


class TreeGameTests(unittest.TestCase):
    def test_placed_numeric_id_resolves_animated_texture(self):
        entity_id = g_editor.allocate_gameplay_entity_id({})
        self.assertIsInstance(entity_id, int)
        tree = dict(type="willow tree", id=entity_id,
                    position=dict(tile_x=10, tile_y=12, x=0., y=0.))
        game.give_entity_stats_from_type(tree, "willow tree")
        texture = object()
        assets = {"tree_textures": {str(entity_id): texture}}
        item = render.build_brain_render_item(entity_id, tree, dict(tile_width=16, tile_height=16), assets)
        self.assertIs(g_graphics.resolve_render_item_texture(item, assets), texture)
        self.assertEqual(item["source_rect"]["width"], 160.)

    def test_place_save_and_build_tree_at_root(self):
        self.assertIn("willow tree", game.load_entity_types())
        self.assertEqual(game.categorise_entity_type("willow tree"), "brains")
        tree = dict(type="willow tree", id="willow", position=dict(tile_x=10, tile_y=12, x=0., y=0.))
        game.give_entity_stats_from_type(tree, "willow tree")
        tree = pickle.loads(pickle.dumps(tree))
        tile_map = dict(tile_width=16, tile_height=16)
        item = render.build_brain_render_item("willow", tree, tile_map, {"tree_textures": {"willow": object()}})
        self.assertEqual(item["sort_y"], 192.)
        self.assertEqual(item["dest_rect"], dict(x=60., y=53., width=160., height=160.))
        self.assertEqual(item["texture"], dict(collection="tree_textures", name="willow"))
        self.assertEqual(g_editor.gameplay_entity_selection_bounds(tree, tile_map), item["bounds_world"])
        preview = render.build_brain_render_item("preview", tree, tile_map, {})
        self.assertEqual(preview["dest_rect"]["x"] + 84, item["dest_rect"]["x"] + 100)
        self.assertEqual(preview["dest_rect"]["y"] + 123, item["dest_rect"]["y"] + 139)


if __name__ == "__main__":
    unittest.main()
