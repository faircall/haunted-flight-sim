import copy
import pickle
import types
import unittest

import g_effects
import g_graphics


POSITION = {"tile_x": 2, "tile_y": 3, "x": 4.0, "y": 5.0}
TILE_MAP = {
    "tile_width": 16,
    "tile_height": 16,
    "map_width": 8,
    "map_height": 8,
    "tile_types": [{"type": "blank_tile"}, {"type": "wall"}],
    "tiles": [{"index": 0} for _ in range(64)],
}


class EffectFactoryAndMigrationTests(unittest.TestCase):
    def test_emitter_defaults_use_fresh_nested_data(self):
        factories = (
            g_effects.make_default_smoke_emitter,
            g_effects.make_default_fire_emitter,
            g_effects.make_default_ember_emitter,
        )
        for factory in factories:
            first = factory(POSITION)
            second = factory(POSITION)
            first["position"]["x"] = 999.0
            first["area_size"]["x"] = 999.0
            self.assertNotEqual(second["position"]["x"], 999.0)
            self.assertNotEqual(second["area_size"]["x"], 999.0)
        first_fire = g_effects.make_default_fire_emitter(POSITION)
        second_fire = g_effects.make_default_fire_emitter(POSITION)
        first_fire["palette"]["core"][0] = 0.0
        self.assertEqual(second_fire["palette"]["core"][0], 1.0)

    def test_authored_emitters_are_serialisable(self):
        authored = {"emitters": {
            effect_type: factory(POSITION)
            for effect_type, factory in (
                ("smoke", g_effects.make_default_smoke_emitter),
                ("fire", g_effects.make_default_fire_emitter),
                ("ember", g_effects.make_default_ember_emitter),
            )
        }}
        self.assertEqual(pickle.loads(pickle.dumps(authored)), authored)

    def test_shader_defaults_are_bounded_and_valid(self):
        for factory in (
            g_effects.make_default_smoke_emitter,
            g_effects.make_default_fire_emitter,
            g_effects.make_default_ember_emitter,
        ):
            emitter = factory(POSITION)
            self.assertGreaterEqual(emitter["density"], 0.0)
            self.assertLessEqual(emitter["density"], 1.0)
            self.assertGreaterEqual(emitter["posterize_levels"], 2)
            self.assertEqual(emitter["shader_version"], g_effects.EFFECT_SHADER_VERSION)

    def test_legacy_cpu_fields_migrate_to_shader_fields(self):
        emitter = {
            "type": "smoke", "position": copy.deepcopy(POSITION),
            "area_size": {"x": 8.0, "y": 8.0},
            "spawn_rate": 9.0, "max_particles": 80,
            "rise_speed": 13.0, "lifetime": 2.8,
            "start_size": 3.0, "end_size": 11.0,
        }
        g_effects.migrate_emitter(emitter)
        self.assertIn("density", emitter)
        self.assertIn("size", emitter)
        self.assertIn("speed", emitter)
        self.assertNotIn("spawn_rate", emitter)
        self.assertNotIn("max_particles", emitter)
        self.assertNotIn("lifetime", emitter)

    def test_migration_preserves_authored_shader_values(self):
        emitter = g_effects.make_default_fire_emitter(POSITION)
        emitter["density"] = 0.123
        emitter["palette"]["core"] = [0.2, 0.3, 0.4, 1.0]
        before = copy.deepcopy(emitter)
        g_effects.migrate_emitter(emitter)
        self.assertEqual(emitter["density"], before["density"])
        self.assertEqual(emitter["palette"], before["palette"])

    def test_removed_rain_and_leaf_emitters_are_pruned_during_migration(self):
        emitters = {
            "rain:1": {"type": "rain"},
            "leaf:1": {"type": "leaf"},
            "smoke:1": g_effects.make_default_smoke_emitter(POSITION),
        }
        g_effects.migrate_emitters(emitters)
        self.assertEqual(set(emitters), {"smoke:1"})

    def test_smoke_has_independent_time_evolution(self):
        emitter = g_effects.make_default_smoke_emitter(POSITION)
        self.assertGreater(emitter["evolution_speed"], 0.0)
        with open("shaders/effect_smoke.fs", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertIn("uniform float evolutionSpeed", source)
        self.assertIn("float evolution = time * evolutionSpeed", source)
        self.assertIn("fbm3(vec3", source)

    def test_continuous_emitters_create_no_runtime_particle_arrays(self):
        emitters = {"smoke:1": g_effects.make_default_smoke_emitter(POSITION)}
        runtime = g_effects.make_effects_runtime()
        g_effects.update_effects(runtime, emitters, g_effects.make_wind_profile(), 0.0, 1.0, TILE_MAP)
        self.assertNotIn("emitters", runtime)
        self.assertEqual(runtime["bursts"], {})
        self.assertEqual(runtime["stats"]["live_particle_count"], 0)

    def test_wall_debris_is_a_short_lived_directional_gpu_emitter(self):
        runtime = g_effects.make_effects_runtime()
        emitter_id = g_effects.spawn_wall_debris_puff(
            runtime,
            {"x": 100.0, "y": 0.0},
            {"x": 48.0, "y": 50.0},
            TILE_MAP,
        )

        self.assertEqual(runtime["bursts"], {})
        emitter = g_effects.collect_transient_effect_emitters(runtime)[emitter_id]
        self.assertEqual(emitter["type"], "smoke")
        self.assertEqual(emitter["runtime_kind"], "wall_debris")
        self.assertEqual(emitter["direction"], {"x": -1.0, "y": -0.0})
        self.assertAlmostEqual(emitter["position"]["x"], 45.5)
        self.assertAlmostEqual(emitter["position"]["y"], 50.0)
        self.assertEqual(emitter["size"], {"x": 2.0, "y": 3.0})

        g_effects.update_effects(
            runtime, {}, g_effects.make_wind_profile(), 0.05, 0.05,
            TILE_MAP,
        )
        emitter = g_effects.collect_transient_effect_emitters(runtime)[emitter_id]
        self.assertGreater(emitter["size"]["x"], 2.0)
        self.assertGreater(emitter["opacity"], 0.0)
        self.assertEqual(runtime["stats"]["transient_emitter_count"], 1)

        g_effects.update_effects(
            runtime, {}, g_effects.make_wind_profile(), 0.25, 0.20,
            TILE_MAP,
        )
        self.assertEqual(g_effects.collect_transient_effect_emitters(runtime), {})
        self.assertEqual(runtime["stats"]["transient_emitter_count"], 0)

    def test_smoke_shader_supports_direction_without_changing_default_upward_flow(self):
        with open("shaders/effect_smoke.fs", encoding="utf-8") as source_file:
            source = source_file.read()
        self.assertIn("uniform vec2 effectDirection", source)
        self.assertIn("smokeDirection = vec2(0.0, -1.0)", source)
        self.assertIn("dot(screenFromBase, smokeDirection)", source)


class ProceduralReferenceAndBoundsTests(unittest.TestCase):
    def test_reference_hash_is_deterministic_and_spatially_varied(self):
        value = g_effects.procedural_hash(12, -4, 4409)
        self.assertEqual(value, g_effects.procedural_hash(12, -4, 4409))
        self.assertNotEqual(value, g_effects.procedural_hash(13, -4, 4409))
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)

    def test_wind_sampling_is_stable_and_smooth(self):
        wind = g_effects.make_wind_profile()
        first = g_effects.sample_wind(wind, 12.0, 34.0, 5.0)
        self.assertEqual(first, g_effects.sample_wind(wind, 12.0, 34.0, 5.0))
        nearby = g_effects.sample_wind(wind, 12.0, 34.0, 5.01)
        self.assertLess(abs(first["x"] - nearby["x"]), 1.0)

    def test_fire_bounds_cover_flame_and_ember_height(self):
        emitter = g_effects.make_default_fire_emitter(POSITION)
        bounds = g_effects.emitter_world_bounds(emitter, TILE_MAP)
        anchor = g_effects.position_to_world(POSITION, TILE_MAP)
        self.assertLessEqual(bounds["y"], anchor["y"] - emitter["size"]["y"] - emitter["ember_height"])
        self.assertGreaterEqual(bounds["y"] + bounds["height"], anchor["y"])

    def test_directed_fire_bounds_extend_along_its_direction(self):
        emitter = g_effects.make_default_fire_emitter({"x": 40.0, "y": 50.0})
        emitter.update({
            "size": {"x": 4.0, "y": 8.0},
            "area_size": {"x": 4.0, "y": 4.0},
            "direction": {"x": 1.0, "y": 0.0},
            "ember_height": 0.0,
            "wind_response": 0.0,
        })
        bounds = g_effects.emitter_world_bounds(emitter, TILE_MAP)
        self.assertLessEqual(bounds["x"], 40.0)
        self.assertGreaterEqual(bounds["x"] + bounds["width"], 48.0)
        self.assertLess(bounds["y"], 50.0)
        self.assertGreater(bounds["y"] + bounds["height"], 50.0)

    def test_disabled_emitter_submits_no_draw(self):
        emitter = g_effects.make_default_smoke_emitter(POSITION)
        emitter["enabled"] = False
        scene = types.SimpleNamespace(texture=types.SimpleNamespace(width=480, height=270))
        camera = types.SimpleNamespace(x=0.0, y=0.0)
        runtime = g_effects.make_effects_runtime()
        result = g_graphics.render_effect_group(
            scene, camera, {"effects_runtime": runtime}, {}, None, "world_front",
            True, {"e": emitter}, TILE_MAP, g_effects.make_wind_profile(), 0.0,
        )
        self.assertEqual(result["draw_calls"], 0)

    def test_offscreen_emitter_submits_no_draw(self):
        emitter = g_effects.make_default_smoke_emitter({"x": 10000.0, "y": 10000.0})
        scene = types.SimpleNamespace(texture=types.SimpleNamespace(width=480, height=270))
        camera = types.SimpleNamespace(x=0.0, y=0.0)
        runtime = g_effects.make_effects_runtime()
        result = g_graphics.render_effect_group(
            scene, camera, {"effects_runtime": runtime}, {}, None, "world_front",
            True, {"e": emitter}, TILE_MAP, g_effects.make_wind_profile(), 0.0,
        )
        self.assertEqual(result["draw_calls"], 0)
        self.assertEqual(runtime["stats"]["culled_emitters"], 1)

    def test_fire_has_one_body_and_one_emissive_submission(self):
        emitter = g_effects.make_default_fire_emitter(POSITION)
        body = g_graphics._procedural_effect_submission(emitter, "world_front")
        core = g_graphics._procedural_effect_submission(emitter, "emissive")
        self.assertEqual(body["material"], "lit_alpha")
        self.assertEqual(core["material"], "emissive_additive")
        self.assertEqual((body["pass_mode"], core["pass_mode"]), (0, 1))


class FireAndBloodTests(unittest.TestCase):
    def test_fire_produces_at_most_one_deterministic_runtime_light(self):
        emitters = {"a": g_effects.make_default_fire_emitter(POSITION)}
        first = g_effects.build_fire_runtime_lights(emitters, TILE_MAP, 3.25)
        second = g_effects.build_fire_runtime_lights(emitters, TILE_MAP, 3.25)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)
        emitters["b"] = g_effects.make_default_smoke_emitter(POSITION)
        self.assertEqual(len(g_effects.build_fire_runtime_lights(emitters, TILE_MAP, 3.25)), 1)
        emitters["a"]["light"]["enabled"] = False
        self.assertEqual(g_effects.build_fire_runtime_lights(emitters, TILE_MAP, 3.25), {})

    def test_fire_runtime_lights_are_replaced_cleanly(self):
        lights = {"other": {"type": "point"}, "effect:fire:old": {}}
        result = g_effects.replace_fire_runtime_lights(lights, {"effect:fire:new": {"type": "point"}})
        self.assertIn("other", result)
        self.assertNotIn("effect:fire:old", result)
        self.assertIn("effect:fire:new", result)

    def test_blood_still_uses_cpu_burst_and_emits_decal_events(self):
        runtime = g_effects.make_effects_runtime()
        burst_id = g_effects.spawn_blood_spatter(runtime, 5, 0.1, {"x": 100.0, "y": 0.0}, POSITION, TILE_MAP)
        self.assertEqual(len(runtime["bursts"][burst_id]["particles"]), 5)
        self.assertTrue(all(particle["effect_type"] == "blood" for particle in runtime["bursts"][burst_id]["particles"]))
        g_effects.update_effects(runtime, {}, g_effects.make_wind_profile(), 0.0, 0.2, TILE_MAP)
        events = g_effects.drain_effect_events(runtime)
        self.assertEqual(len([event for event in events if event["type"] == "blood_decal"]), 5)
        self.assertEqual(runtime["bursts"], {})


if __name__ == "__main__":
    unittest.main()
