import json
import pickle
from pathlib import Path
import unittest

import g_effects
import g_graphics
import g_update_and_render as game


def make_map(width=3, height=2):
    return game.make_tile_map(width, height, 16, 16)


class RainProfileTests(unittest.TestCase):
    def test_rain_is_not_a_local_emitter_or_cpu_particle_type(self):
        self.assertNotIn("rain", g_effects.PROCEDURAL_EFFECT_TYPES)
        self.assertNotIn("rain", g_effects._FACTORIES)

    def test_profile_is_fresh_nested_and_serialisable(self):
        first = g_effects.make_rain_profile()
        second = g_effects.make_rain_profile()
        first["direction"]["x"] = 99.0
        first["cell_size"]["y"] = 99.0
        first["ambient_color"][0] = 0.0
        self.assertEqual(second["direction"], {"x": 0.12, "y": 1.0})
        self.assertEqual(second["cell_size"], {"x": 9.0, "y": 14.0})
        self.assertEqual(second["ambient_color"][0], 0.40)
        json.dumps(second)

    def test_constraints_and_safe_direction(self):
        profile = g_effects.make_rain_profile()
        profile.update({
            "direction": {"x": 0.0, "y": 0.0},
            "density": 5.0,
            "unlit_opacity": -2.0,
            "lit_opacity": 3.0,
            "distortion_strength": 8.0,
            "opacity_levels": 1,
        })
        g_effects.normalize_rain_profile(profile)
        self.assertEqual(profile["direction"], {"x": 0.0, "y": 1.0})
        self.assertEqual(profile["density"], 1.0)
        self.assertEqual(profile["unlit_opacity"], 0.0)
        self.assertEqual(profile["lit_opacity"], 1.0)
        self.assertEqual(profile["distortion_strength"], 1.0)
        self.assertEqual(profile["opacity_levels"], 2)


class RainExposureDataTests(unittest.TestCase):
    def test_profile_exposure_and_revision_survive_level_serialisation(self):
        tile_map = make_map(2, 1)
        g_effects.set_tile_rain_exposure(tile_map["tiles"][1], 0.375)
        g_effects.mark_rain_exposure_dirty(tile_map)
        arena = {"tile_map": tile_map, "rain_profile": g_effects.make_rain_profile("default")}
        restored = pickle.loads(pickle.dumps(arena))
        self.assertEqual(g_effects.get_tile_rain_exposure(restored["tile_map"]["tiles"][1]), 0.375)
        self.assertEqual(restored["tile_map"]["rain_exposure_revision"], 1)
        self.assertEqual(restored["rain_profile"], arena["rain_profile"])

    def test_missing_clamping_and_zero_storage(self):
        tile = {}
        self.assertEqual(g_effects.get_tile_rain_exposure(tile), 0.0)
        self.assertTrue(g_effects.set_tile_rain_exposure(tile, 2.0))
        self.assertEqual(tile["rain_exposure"], 1.0)
        self.assertFalse(g_effects.set_tile_rain_exposure(tile, 1.5))
        self.assertTrue(g_effects.set_tile_rain_exposure(tile, -1.0))
        self.assertNotIn("rain_exposure", tile)
        self.assertFalse(g_effects.set_tile_rain_exposure(tile, 0.0))

    def test_change_dirtying_is_independent_from_geometry(self):
        tile_map = make_map(1, 1)
        geometry_before = tile_map["geometry_revision"]
        revision_before = tile_map["rain_exposure_revision"]
        tile = tile_map["tiles"][0]
        if g_effects.set_tile_rain_exposure(tile, 1.0):
            g_effects.mark_rain_exposure_dirty(tile_map)
        self.assertEqual(tile_map["rain_exposure_revision"], revision_before + 1)
        if g_effects.set_tile_rain_exposure(tile, 1.0):
            g_effects.mark_rain_exposure_dirty(tile_map)
        self.assertEqual(tile_map["rain_exposure_revision"], revision_before + 1)
        self.assertEqual(tile_map["geometry_revision"], geometry_before)

    def test_pixel_order_count_and_byte_length(self):
        tile_map = make_map(3, 2)
        values = (0.0, 0.25, 0.5, 0.75, 1.0, 0.0)
        for tile, value in zip(tile_map["tiles"], values):
            g_effects.set_tile_rain_exposure(tile, value)
        pixels = g_effects.build_rain_exposure_pixel_data(tile_map)
        self.assertEqual(len(pixels), 3 * 2 * 4)
        self.assertEqual(list(pixels[0::4]), [0, 64, 128, 191, 255, 0])
        self.assertTrue(all(channel == 255 for channel in pixels[3::4]))
        self.assertEqual(g_effects.count_exposed_rain_tiles(tile_map), 4)


class RainFloodFillTests(unittest.TestCase):
    def test_four_way_matching_and_unrelated_fields_are_untouched(self):
        tile_map = make_map(3, 3)
        # Diagonal exposed tiles do not join the covered four-connected region.
        g_effects.set_tile_rain_exposure(tile_map["tiles"][0], 1.0)
        g_effects.set_tile_rain_exposure(tile_map["tiles"][4], 1.0)
        for index, tile in enumerate(tile_map["tiles"]):
            tile["index"] = index % 4
            tile["shape_index"] = index % 5
            if index % 2:
                tile["force_collidable"] = True
        unrelated = [
            (tile["index"], tile["shape_index"], tile.get("force_collidable", False))
            for tile in tile_map["tiles"]
        ]
        geometry_before = tile_map["geometry_revision"]
        changed = g_effects.flood_fill_rain_exposure(tile_map, 0, 1, 1.0)
        self.assertEqual(changed, 7)
        self.assertTrue(all(g_effects.get_tile_rain_exposure(tile) == 1.0 for tile in tile_map["tiles"]))
        self.assertEqual(tile_map["rain_exposure_revision"], 1)
        self.assertEqual(tile_map["geometry_revision"], geometry_before)
        self.assertEqual(unrelated, [
            (tile["index"], tile["shape_index"], tile.get("force_collidable", False))
            for tile in tile_map["tiles"]
        ])
        self.assertEqual(g_effects.flood_fill_rain_exposure(tile_map, 0, 0, 1.0), 0)
        self.assertEqual(tile_map["rain_exposure_revision"], 1)

    def test_only_starting_exposure_is_replaced(self):
        tile_map = make_map(3, 1)
        for tile, value in zip(tile_map["tiles"], (0.0, 0.5, 0.0)):
            g_effects.set_tile_rain_exposure(tile, value)
        self.assertEqual(g_effects.flood_fill_rain_exposure(tile_map, 0, 0, 1.0), 1)
        self.assertEqual([g_effects.get_tile_rain_exposure(tile) for tile in tile_map["tiles"]], [1.0, 0.5, 0.0])


class RainExposureCacheTests(unittest.TestCase):
    def test_cache_decisions(self):
        tile_map = make_map(2, 2)
        identity, width, height, revision = g_graphics.rain_exposure_texture_cache_key(tile_map)
        cache = {
            "texture": object(), "source_identity": identity,
            "width": width, "height": height, "last_revision": revision,
        }
        self.assertEqual(g_graphics.rain_exposure_texture_cache_action(cache, tile_map), "reuse")
        tile_map["rain_exposure_revision"] += 1
        self.assertEqual(g_graphics.rain_exposure_texture_cache_action(cache, tile_map), "update")
        resized = make_map(3, 2)
        resized_cache = dict(cache, source_identity=id(resized), last_revision=0)
        self.assertEqual(g_graphics.rain_exposure_texture_cache_action(resized_cache, resized), "recreate")
        replacement = make_map(2, 2)
        self.assertEqual(g_graphics.rain_exposure_texture_cache_action(cache, replacement), "recreate")


class RainShaderContractTests(unittest.TestCase):
    def test_displacement_is_integer_vertical_only_and_clamped_to_one_texel(self):
        source = Path("shaders/rain_composite.fs").read_text(encoding="utf-8")
        self.assertIn("float offsetPixels = offsetSign * floor(distortionAmount + 0.5);", source)
        self.assertIn("offsetPixels = clamp(offsetPixels, -1.0, 1.0);", source)
        self.assertIn("vec2 displacedUv = fragTexCoord + vec2(0.0, offsetPixels / resolution.y);", source)
        self.assertNotIn("fragTexCoord + vec2(offsetPixels", source)

    def test_exposure_is_resolved_before_displaced_scene_sampling(self):
        source = Path("shaders/rain_composite.fs").read_text(encoding="utf-8")
        exposure = source.index("float exposure = exposureAtWorld(worldPosition);")
        displaced = source.index("vec4 sceneSample = texture(texture0, displacedUv);")
        self.assertLess(exposure, displaced)

    def test_distortion_reuses_the_visible_streak_geometry_and_motion(self):
        source = Path("shaders/rain_composite.fs").read_text(encoding="utf-8")
        self.assertNotIn("distortionField", source)
        self.assertIn("float distortionMask = streakGeometry * distortionSelection * exposure;", source)
        self.assertEqual(source.count("vec2 movingWorld ="), 1)


if __name__ == "__main__":
    unittest.main()
