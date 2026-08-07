import json
import math
import pickle
import random
import unittest
from unittest import mock

import g_audio


class FakeSound:
    instances = []

    def __init__(self, engine, path):
        self.engine = engine
        self.path = path
        self.looping = False
        self.volume = 1.0
        self.pitch = 1.0
        self.pan = 0.0
        self.spatialization_enabled = True
        self.is_playing = False
        self.at_end = False
        self.start_count = 0
        self.closed = False
        FakeSound.instances.append(self)

    def start(self):
        self.is_playing = True
        self.at_end = False
        self.start_count += 1

    def stop(self):
        self.is_playing = False

    def seek(self, frame):
        self.at_end = False

    def close(self):
        self.stop()
        self.closed = True


def make_map(width=2, height=2, surface="wood"):
    tile_type = {"type": surface, "audio_surface": surface if surface in g_audio.AUDIO_SURFACES else "generic"}
    return {
        "map_width": width,
        "map_height": height,
        "tile_width": 16,
        "tile_height": 16,
        "geometry_revision": 7,
        "acoustic_revision": 0,
        "acoustic_zones": g_audio.make_default_acoustic_zones(),
        "tile_types": [tile_type],
        "tiles": [
            {"index": 0, "tile_x": x, "tile_y": y, "shape_index": 0,
             "force_collidable": (x + y) % 2 == 0}
            for y in range(height) for x in range(width)
        ],
    }


def listener(x=0.0, y=0.0):
    return {"source_id": "player", "world_position": {"x": x, "y": y}}


class AudioProfileAndEventTests(unittest.TestCase):
    def test_profile_is_fresh_nested_serialisable_data(self):
        first = g_audio.make_audio_profile()
        second = g_audio.make_audio_profile()
        first["pitch_variation"]["impact"] = 99.0
        self.assertNotEqual(first["pitch_variation"], second["pitch_variation"])
        json.dumps(second)
        pickle.dumps(second)

    def test_profile_normalisation_clamps_policy(self):
        profile = g_audio.make_audio_profile()
        profile.update({"maximum_pan": 4.0, "maximum_distance": -1.0,
                        "minimum_distance": 20.0, "enemy_footsteps_per_frame": 0})
        g_audio.normalize_audio_profile(profile)
        self.assertEqual(profile["maximum_pan"], 1.0)
        self.assertGreater(profile["maximum_distance"], profile["minimum_distance"])
        self.assertEqual(profile["enemy_footsteps_per_frame"], 1)

    def test_queued_events_are_plain_copies(self):
        runtime = g_audio.make_audio_runtime()
        event = {"type": "footstep", "source_id": "player", "source_kind": "player",
                 "world_position": {"x": 2.0, "y": 3.0}, "data": {"gait": "walk"}}
        self.assertTrue(g_audio.queue_audio_event(runtime, event))
        event["data"]["gait"] = "changed"
        queued = runtime["event_queue"][0]
        self.assertEqual(queued["data"]["gait"], "walk")
        pickle.dumps(queued)

    def test_malformed_or_unknown_events_are_rejected(self):
        runtime = g_audio.make_audio_runtime()
        self.assertFalse(g_audio.queue_audio_event(runtime, None))
        self.assertFalse(g_audio.queue_audio_event(runtime, {"type": "imaginary"}))
        self.assertFalse(g_audio.queue_audio_event(runtime, {"type": "ui_hover", "sound": object()}))
        self.assertFalse(g_audio.queue_audio_event(runtime, {"type": "footstep", "gain": "loud"}))
        self.assertFalse(g_audio.queue_audio_event(runtime, {"type": "footstep", "world_position": []}))
        self.assertEqual(runtime["event_queue"], [])

    def test_processing_clears_events_and_ui_bypasses_distance(self):
        runtime = g_audio.make_audio_runtime(object())
        g_audio.queue_audio_event(runtime, {
            "type": "ui_hover", "source_id": "ui:test", "source_kind": "ui",
            "world_position": {"x": 99999.0, "y": 0.0},
        })
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            stats = g_audio.update_audio(
                runtime, runtime["engine"], 0.016, listener(), make_map(), {}, {}, {},
                g_audio.make_audio_profile(),
            )
        self.assertEqual(runtime["event_queue"], [])
        self.assertEqual(stats["accepted_events"], 1)
        self.assertEqual(stats["discarded_events"], 0)


class VariantAndManifestTests(unittest.TestCase):
    def test_new_player_surface_families_use_all_authored_variants(self):
        runtime = g_audio.make_audio_runtime()
        for surface in ("carpet", "wood", "stone", "grass"):
            paths = g_audio.resolve_available_family_paths(
                runtime, f"footsteps.player.{surface}",
            )
            self.assertEqual(len(paths), 5)
            self.assertTrue(all(
                f"/player/{surface}/player_{surface}_" in path
                for path in paths
            ))

    def test_redhead_surface_families_use_all_authored_variants(self):
        runtime = g_audio.make_audio_runtime()
        for surface in ("carpet", "wood", "stone", "grass"):
            paths = g_audio.resolve_available_family_paths(
                runtime, f"footsteps.enemy_contact.{surface}",
            )
            self.assertEqual(len(paths), 5)
            self.assertTrue(all(
                f"/redhead/{surface}/redhead_{surface}_" in path
                for path in paths
            ))

    def test_shuffle_bag_visits_every_variant_before_reshuffle(self):
        state = {}
        variants = ["a", "b", "c", "d"]
        selected = [
            g_audio.select_shuffle_bag_variant(state, "test", variants, random.Random(8))
            for _ in variants
        ]
        self.assertEqual(set(selected), set(variants))

    def test_shuffle_bag_is_deterministic_and_avoids_boundary_repeat(self):
        def sequence():
            state = {}
            rng = random.Random(17)
            return [g_audio.select_shuffle_bag_variant(state, "f", ["a", "b", "c"], rng) for _ in range(9)]
        first = sequence()
        self.assertEqual(first, sequence())
        self.assertTrue(all(a != b for a, b in zip(first[2::3], first[3::3])))

    def test_missing_variants_use_real_fallback(self):
        runtime = g_audio.make_audio_runtime()
        runtime["manifest"] = {"test": g_audio._family(
            variants=["sounds/does_not_exist.wav"], fallback="sounds/ui_hover.wav"
        )}
        self.assertEqual(g_audio.resolve_available_family_paths(runtime, "test"), ["sounds/ui_hover.wav"])
        self.assertIn("sounds/does_not_exist.wav", runtime["missing_asset_path_warnings"])

    def test_missing_optional_family_is_silent_and_safe(self):
        runtime = g_audio.make_audio_runtime()
        self.assertEqual(g_audio.resolve_available_family_paths(runtime, "fire.fire_crackle"), [])
        self.assertIn("fire.fire_crackle", runtime["missing_asset_warnings"])

    def test_prepared_muffled_variant_is_distinct_from_dry_fallback(self):
        runtime = g_audio.make_audio_runtime()
        runtime["manifest"] = {"test": g_audio._family(
            fallback="sounds/ammo_pickup.wav",
            muffled_variants=["sounds/ui_hover.wav"],
        )}
        self.assertEqual(
            g_audio.resolve_available_family_paths(runtime, "test"),
            ["sounds/ammo_pickup.wav"],
        )
        self.assertEqual(
            g_audio.resolve_available_muffled_family_paths(runtime, "test"),
            ["sounds/ui_hover.wav"],
        )


class SpatialAudioTests(unittest.TestCase):
    def test_attenuation_endpoints_and_continuity(self):
        origin = {"x": 0.0, "y": 0.0}
        self.assertEqual(g_audio.distance_attenuation(origin, origin, 10.0, 100.0), 1.0)
        self.assertEqual(g_audio.distance_attenuation(origin, {"x": 101.0, "y": 0.0}, 10.0, 100.0), 0.0)
        samples = [g_audio.distance_attenuation(origin, {"x": x, "y": 0.0}, 10.0, 100.0) for x in range(10, 101)]
        self.assertTrue(all(a >= b for a, b in zip(samples, samples[1:])))
        self.assertLess(max(abs(a - b) for a, b in zip(samples, samples[1:])), 0.03)

    def test_pan_direction_and_clamp(self):
        origin = {"x": 0.0, "y": 0.0}
        self.assertLess(g_audio.stereo_pan(origin, {"x": -50.0, "y": 0.0}, 100.0, 0.85), 0.0)
        self.assertGreater(g_audio.stereo_pan(origin, {"x": 50.0, "y": 0.0}, 100.0, 0.85), 0.0)
        self.assertEqual(g_audio.stereo_pan(origin, {"x": 999.0, "y": 0.0}, 100.0, 0.7), 0.7)

    def test_ui_audibility_ignores_world_distance(self):
        event = {"type": "ui_hover", "source_kind": "ui", "gain": 0.8,
                 "world_position": {"x": 10000.0, "y": 0.0}}
        self.assertEqual(g_audio.estimate_event_audibility(
            event, listener(), {"direct_gain": 1.0}, g_audio.make_audio_profile()), 0.8)


class SurfaceAndOverlayTests(unittest.TestCase):
    def test_surface_migration_and_resolution(self):
        expected = {"wood": "wood", "grass": "grass", "stone": "stone",
                    "carpet": "carpet", "blank_tile": "dirt"}
        for tile_name, surface in expected.items():
            tile_map = make_map()
            tile_map["tile_types"][0] = {"type": tile_name}
            g_audio.migrate_tile_audio_data(tile_map)
            self.assertEqual(g_audio.get_tile_audio_surface(tile_map, {"x": 1.0, "y": 1.0}), surface)

    def test_legacy_carpet_and_stone_surface_defaults_migrate_once(self):
        tile_map = make_map()
        tile_map["tile_types"] = [
            {"type": "carpet", "audio_surface": "generic"},
            {"type": "stone", "audio_surface": "tile"},
        ]
        g_audio.migrate_tile_audio_data(tile_map)
        self.assertEqual(tile_map["tile_types"][0]["audio_surface"], "carpet")
        self.assertEqual(tile_map["tile_types"][1]["audio_surface"], "stone")
        self.assertEqual(
            tile_map["audio_surface_schema_revision"],
            g_audio.AUDIO_SURFACE_SCHEMA_REVISION,
        )
        tile_map["tile_types"][0]["audio_surface"] = "metal"
        g_audio.migrate_tile_audio_data(tile_map)
        self.assertEqual(tile_map["tile_types"][0]["audio_surface"], "metal")

    def test_malformed_and_outside_tiles_are_generic(self):
        tile_map = make_map()
        tile_map["tiles"][0]["index"] = 99
        self.assertEqual(g_audio.get_tile_audio_surface(tile_map, {"x": 1.0, "y": 1.0}), "generic")
        self.assertEqual(g_audio.get_tile_audio_surface(tile_map, {"x": -1.0, "y": 1.0}), "generic")

    def test_puddle_overlay_preserves_base_surface(self):
        tile_map = make_map()
        tile_map["tiles"][0]["footstep_overlay"] = "puddle"
        contact = g_audio.resolve_footstep_contact({"x": 2.0, "y": 2.0}, tile_map, {})
        self.assertEqual(contact["base_surface"], "wood")
        self.assertEqual(contact["overlay"], "puddle")

    def test_puddle_decal_is_recognised(self):
        tile_map = make_map()
        tile_map["tiles"][0]["decals"] = [{"type": "puddle"}]
        self.assertEqual(g_audio.resolve_footstep_contact(
            {"x": 2.0, "y": 2.0}, tile_map, {})["overlay"], "puddle")

    def test_corpse_contact_requires_dead_red_head_and_beats_puddle(self):
        tile_map = make_map()
        tile_map["tiles"][0]["footstep_overlay"] = "puddle"
        corpse = {"type": "red head", "current_state": "dead",
                  "position": {"tile_x": 0, "tile_y": 0, "x": 4.0, "y": 4.0},
                  "ground_footprint": {"offset": {"x": 0.0, "y": 0.0},
                                       "size": {"x": 14.0, "y": 8.0}}}
        contact = g_audio.resolve_footstep_contact(
            {"x": 4.0, "y": 4.0}, tile_map, {"brains": {"corpse": corpse}}
        )
        self.assertEqual(contact["base_surface"], "wood")
        self.assertEqual(contact["overlay"], "corpse")
        corpse["current_state"] = "idle"
        self.assertEqual(g_audio.resolve_footstep_contact(
            {"x": 4.0, "y": 4.0}, tile_map, {"brains": {"living": corpse}}
        )["overlay"], "puddle")

    def test_buddha_never_becomes_corpse_contact(self):
        buddha = {"type": "buddha", "current_state": "dead",
                  "position": {"tile_x": 0, "tile_y": 0, "x": 2.0, "y": 2.0}}
        self.assertIsNone(g_audio.resolve_footstep_contact(
            {"x": 2.0, "y": 2.0}, make_map(), {"brains": {"b": buddha}}
        )["overlay"])


class FootstepTravelAndArbitrationTests(unittest.TestCase):
    def test_travel_distance_triggers_and_subtracts_stride(self):
        actor = {}
        g_audio.update_actor_footstep_travel(actor, {"x": 0.0, "y": 0.0}, 10.0, "p", "player")
        events = g_audio.update_actor_footstep_travel(actor, {"x": 25.0, "y": 0.0}, 10.0, "p", "player")
        self.assertEqual(len(events), 2)
        self.assertAlmostEqual(actor["audio_step_state"]["distance"], 5.0)

    def test_stationary_and_blocked_movement_emit_no_steps(self):
        actor = {}
        for _ in range(10):
            events = g_audio.update_actor_footstep_travel(actor, {"x": 4.0, "y": 4.0}, 5.0, "p", "player")
            self.assertEqual(events, [])

    def test_walk_and_run_stride_can_differ(self):
        walk = {}
        run = {}
        for actor in (walk, run):
            g_audio.update_actor_footstep_travel(actor, {"x": 0.0, "y": 0.0}, 10.0, "p", "player")
        self.assertEqual(len(g_audio.update_actor_footstep_travel(
            walk, {"x": 15.0, "y": 0.0}, 10.0, "p", "player")), 1)
        self.assertEqual(len(g_audio.update_actor_footstep_travel(
            run, {"x": 15.0, "y": 0.0}, 20.0, "p", "player")), 0)

    def test_nearest_enemy_step_wins_and_rejections_are_not_queued(self):
        runtime = g_audio.make_audio_runtime()
        runtime["time"] = 1.0
        events = [
            {"type": "footstep", "source_id": "near", "source_kind": "enemy",
             "world_position": {"x": 20.0, "y": 0.0}, "priority": 1.0, "gain": 1.0, "data": {}},
            {"type": "footstep", "source_id": "far", "source_kind": "enemy",
             "world_position": {"x": 200.0, "y": 0.0}, "priority": 1.0, "gain": 1.0, "data": {}},
        ]
        accepted = g_audio.arbitrate_enemy_footsteps(
            events, runtime, listener(), make_map(), g_audio.make_audio_profile()
        )
        self.assertEqual([event["source_id"] for event in accepted], ["near"])
        self.assertEqual(runtime["event_queue"], [])

    def test_enemy_group_spacing_and_voice_limit(self):
        runtime = g_audio.make_audio_runtime()
        runtime["time"] = 2.0
        runtime["cooldowns"]["enemy_footstep_group"] = 1.98
        event = {"type": "footstep", "source_id": "e", "source_kind": "enemy",
                 "world_position": {"x": 1.0, "y": 0.0}, "priority": 1.0, "gain": 1.0, "data": {}}
        self.assertEqual(g_audio.arbitrate_enemy_footsteps(
            [event], runtime, listener(), make_map(), g_audio.make_audio_profile()), [])
        runtime["cooldowns"].clear()
        runtime["active_voices"] = [
            {"source_id": f"e{i}", "source_kind": "enemy", "event_type": "footstep"}
            for i in range(4)
        ]
        self.assertEqual(g_audio.arbitrate_enemy_footsteps(
            [event], runtime, listener(), make_map(), g_audio.make_audio_profile()), [])

    def test_player_step_is_not_part_of_enemy_arbitration(self):
        runtime = g_audio.make_audio_runtime(object())
        runtime["cooldowns"]["enemy_footstep_group"] = 0.0
        runtime["time"] = 0.01
        g_audio.queue_audio_event(runtime, {"type": "footstep", "source_id": "player",
            "source_kind": "player", "world_position": {"x": 0.0, "y": 0.0}})
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            stats = g_audio.update_audio(runtime, runtime["engine"], 0.01, listener(),
                make_map(), {}, {}, {}, g_audio.make_audio_profile())
        self.assertEqual(stats["accepted_events"], 1)

    def test_redhead_surface_step_is_positional(self):
        FakeSound.instances = []
        runtime = g_audio.make_audio_runtime(object())
        profile = g_audio.make_audio_profile()
        profile.update({
            "minimum_distance": 0.0, "maximum_distance": 100.0,
            "pan_distance": 40.0, "maximum_pan": 1.0,
        })
        g_audio.queue_audio_event(runtime, {
            "type": "footstep", "source_id": "enemy:redhead:7",
            "source_kind": "enemy", "world_position": {"x": 20.0, "y": 0.0},
            "priority": 0.75,
        })
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            stats = g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(),
                make_map(surface="stone"), {}, {}, {}, profile,
            )
        self.assertEqual(stats["accepted_events"], 1)
        self.assertIn("/redhead/stone/redhead_stone_", FakeSound.instances[-1].path)
        self.assertGreater(FakeSound.instances[-1].pan, 0.0)
        self.assertLess(FakeSound.instances[-1].volume, 1.0)


class AcousticZoneTests(unittest.TestCase):
    def test_same_zone_is_clear_and_different_zone_requests_treatment(self):
        tile_map = make_map()
        tile_map["tiles"][1]["acoustic_zone_id"] = 1
        same = g_audio.resolve_source_listener_acoustic_context(
            {"x": 2.0, "y": 2.0}, {"x": 3.0, "y": 3.0}, tile_map)
        different = g_audio.resolve_source_listener_acoustic_context(
            {"x": 18.0, "y": 2.0}, {"x": 2.0, "y": 2.0}, tile_map)
        self.assertTrue(same["same_zone"])
        self.assertEqual(same["direct_gain"], 1.0)
        self.assertFalse(different["same_zone"])
        self.assertLess(different["direct_gain"], 1.0)
        self.assertIsNotNone(different["low_pass_hz"])

    def test_outdoor_source_to_indoor_listener_requests_muffling(self):
        tile_map = make_map()
        tile_map["tiles"][1]["acoustic_zone_id"] = 1
        context = g_audio.resolve_source_listener_acoustic_context(
            {"x": 2.0, "y": 2.0}, {"x": 18.0, "y": 2.0}, tile_map)
        self.assertEqual(context["transmission"], "outdoor_to_indoor")
        self.assertTrue(context["muffled_weather"])

    def test_missing_zone_resolves_to_default(self):
        self.assertEqual(g_audio.get_acoustic_zone_definition(make_map(), 999)["id"], 0)

    def test_tile_referencing_missing_zone_uses_default_context(self):
        tile_map = make_map()
        tile_map["tiles"][0]["acoustic_zone_id"] = 999
        self.assertEqual(
            g_audio.get_acoustic_zone_at_world_position(tile_map, {"x": 2.0, "y": 2.0}), 0,
        )
        context = g_audio.resolve_source_listener_acoustic_context(
            {"x": 2.0, "y": 2.0}, {"x": 18.0, "y": 2.0}, tile_map,
        )
        self.assertTrue(context["same_zone"])

    def test_acoustic_paint_and_flood_do_not_dirty_geometry_or_other_tile_data(self):
        tile_map = make_map(3, 2)
        original = [(tile["index"], tile["shape_index"], tile["force_collidable"])
                    for tile in tile_map["tiles"]]
        changed = g_audio.flood_fill_acoustic_zone(tile_map, 0, 0, 2)
        self.assertEqual(changed, 6)
        self.assertEqual(tile_map["acoustic_revision"], 1)
        self.assertEqual(tile_map["geometry_revision"], 7)
        self.assertEqual(original, [(tile["index"], tile["shape_index"], tile["force_collidable"])
                                    for tile in tile_map["tiles"]])

    def test_acoustic_flood_is_four_connected_and_only_matches_start(self):
        tile_map = make_map(3, 3)
        for index in (1, 3):
            tile_map["tiles"][index]["acoustic_zone_id"] = 1
        tile_map["tiles"][4]["acoustic_zone_id"] = 2
        changed = g_audio.flood_fill_acoustic_zone(tile_map, 0, 0, 3)
        self.assertEqual(changed, 1)
        self.assertEqual(g_audio.get_tile_acoustic_zone(tile_map["tiles"][8]), 0)


class LoopAndRainTests(unittest.TestCase):
    def setUp(self):
        FakeSound.instances = []
        self.runtime = g_audio.make_audio_runtime(object())
        self.runtime["manifest"] = {
            "loop": g_audio._family(fallback="sounds/ui_hover.wav", voice_count=1,
                                     spatial=False, bus="ambience")
        }
        self.profile = g_audio.make_audio_profile()
        self.profile["loop_attack_seconds"] = 0.1
        self.profile["loop_release_seconds"] = 0.1

    def test_repeated_loop_requests_reuse_voice_and_change_target(self):
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            loop = g_audio.request_loop(self.runtime, "key", "loop", 1.0)
            g_audio.update_loop_voices(self.runtime, 0.1, listener(), self.profile)
            sound = loop["sound"]
            g_audio.request_loop(self.runtime, "key", "loop", 0.4)
            g_audio.update_loop_voices(self.runtime, 0.05, listener(), self.profile)
        self.assertIs(loop["sound"], sound)
        self.assertEqual(sound.start_count, 1)
        self.assertEqual(loop["target_gain"], 0.4)

    def test_zero_target_does_not_create_an_absent_loop(self):
        self.assertIsNone(g_audio.request_loop(self.runtime, "silent", "loop", 0.0))
        self.assertNotIn("silent", self.runtime["loop_voices"])

    def test_spatial_loop_uses_cross_zone_gain_fallback(self):
        treatment = {"direct_gain": 0.5, "low_pass_hz": 1800.0}
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            loop = g_audio.request_loop(
                self.runtime, "spatial", "loop", 1.0,
                {"x": 0.0, "y": 0.0}, True, treatment,
            )
            g_audio.update_loop_voices(self.runtime, 0.1, listener(), self.profile)
        self.assertAlmostEqual(loop["sound"].volume, 0.5 * 0.82 * 0.8, places=6)

    def test_unrequested_loop_fades_stops_and_is_removed(self):
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            g_audio.request_loop(self.runtime, "key", "loop", 1.0)
            g_audio.update_loop_voices(self.runtime, 0.1, listener(), self.profile)
            sound = self.runtime["loop_voices"]["key"]["sound"]
            self.runtime["frame"] += 1
            g_audio.update_loop_voices(self.runtime, 0.1, listener(), self.profile)
        self.assertNotIn("key", self.runtime["loop_voices"])
        self.assertTrue(sound.closed)

    def test_rain_state_targets_open_covered_and_indoor_layers(self):
        tile_map = make_map()
        tile_map["tiles"][0]["rain_exposure"] = 1.0
        rain = {"enabled": True}
        state, targets = g_audio.resolve_listener_rain_state({"x": 2.0, "y": 2.0}, tile_map, rain)
        self.assertEqual(state, "exposed_outdoor")
        self.assertGreater(targets["rain_open_body"], targets["rain_roof"])
        tile_map["tiles"][0].pop("rain_exposure")
        state, targets = g_audio.resolve_listener_rain_state({"x": 2.0, "y": 2.0}, tile_map, rain)
        self.assertEqual(state, "covered_exterior")
        self.assertGreater(targets["rain_roof"], targets["rain_open_body"])
        tile_map["tiles"][0]["acoustic_zone_id"] = 1
        state, targets = g_audio.resolve_listener_rain_state({"x": 2.0, "y": 2.0}, tile_map, rain)
        self.assertEqual(state, "indoors")
        self.assertGreater(targets["rain_muffled"], targets["rain_open_body"])

    def test_ambience_zone_transition_keeps_fading_previous_state(self):
        runtime = g_audio.make_audio_runtime(None)
        tile_map = make_map()
        profile = g_audio.make_audio_profile()
        g_audio.update_audio(runtime, None, 0.1, listener(2.0, 2.0), tile_map, {}, {}, {}, profile)
        old_key = "ambience:0:base"
        self.assertIn(old_key, runtime["loop_voices"])
        tile_map["tiles"][1]["acoustic_zone_id"] = 1
        g_audio.update_audio(runtime, None, 0.1, listener(18.0, 2.0), tile_map, {}, {}, {}, profile)
        self.assertIn(old_key, runtime["loop_voices"])
        self.assertIn("ambience:1:base", runtime["loop_voices"])
        self.assertEqual(runtime["loop_voices"][old_key]["target_gain"], 0.0)

    def test_deleted_fire_emitter_loop_eventually_disappears(self):
        runtime = g_audio.make_audio_runtime(None)
        tile_map = make_map()
        profile = g_audio.make_audio_profile()
        profile["loop_release_seconds"] = 0.1
        emitter = {"type": "fire", "enabled": True, "seed": 2,
                   "position": {"tile_x": 0, "tile_y": 0, "x": 4.0, "y": 4.0},
                   "size": {"x": 16.0, "y": 16.0}}
        g_audio.update_audio(runtime, None, 0.1, listener(), tile_map, {}, {}, {"f": emitter}, profile)
        self.assertIn("fire:f:bed", runtime["loop_voices"])
        g_audio.update_audio(runtime, None, 0.1, listener(), tile_map, {}, {}, {}, profile)
        self.assertNotIn("fire:f:bed", runtime["loop_voices"])


class AuthoredSoundEmitterTests(unittest.TestCase):
    def setUp(self):
        FakeSound.instances = []
        self.tile_map = make_map(20, 20)
        self.profile = g_audio.make_audio_profile()
        self.profile["loop_attack_seconds"] = 0.1
        self.profile["loop_release_seconds"] = 0.1

    def make_emitter(self, world_x=80.0, world_y=32.0):
        emitter = g_audio.make_default_sound_emitter({
            "tile_x": int(world_x // 16), "tile_y": int(world_y // 16),
            "x": world_x % 16, "y": world_y % 16,
        })
        emitter["minimum_distance"] = 0.0
        emitter["maximum_distance"] = 200.0
        emitter["pan_distance"] = 100.0
        return emitter

    def test_factory_is_serialisable_and_normalisation_clamps(self):
        emitter = self.make_emitter()
        emitter.update({"gain": 99.0, "maximum_pan": 2.0,
                        "cadence_seconds": 0.0, "playback_mode": "wrong"})
        g_audio.normalize_sound_emitter(emitter)
        self.assertEqual(emitter["gain"], 2.0)
        self.assertEqual(emitter["maximum_pan"], 1.0)
        self.assertEqual(emitter["cadence_seconds"], 0.25)
        self.assertEqual(emitter["playback_mode"], "loop")
        json.dumps(emitter)

    def test_loop_is_positional_reused_and_fades_after_deletion(self):
        runtime = g_audio.make_audio_runtime(object())
        entities = {"sound_emitters": {"bell": self.make_emitter()}}
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(0.0, 32.0),
                self.tile_map, entities, {}, {}, self.profile,
            )
            loop = runtime["loop_voices"]["sound_emitter:bell:loop"]
            sound = loop["sound"]
            self.assertGreater(sound.pan, 0.0)
            g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(160.0, 32.0),
                self.tile_map, entities, {}, {}, self.profile,
            )
            self.assertIs(loop["sound"], sound)
            self.assertLess(sound.pan, 0.0)
            entities["sound_emitters"].clear()
            g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(),
                self.tile_map, entities, {}, {}, self.profile,
            )
        self.assertNotIn("sound_emitter:bell:loop", runtime["loop_voices"])
        self.assertTrue(sound.closed)

    def test_cadence_is_deterministic_and_deferred(self):
        first = self.make_emitter()
        second = self.make_emitter()
        first.update({"playback_mode": "cadence", "cadence_seconds": 4.0,
                      "cadence_variation": 1.0, "seed": 17})
        second.update(first)
        self.assertEqual(
            [g_audio.sound_emitter_cadence_interval(first, index) for index in range(6)],
            [g_audio.sound_emitter_cadence_interval(second, index) for index in range(6)],
        )
        runtime = g_audio.make_audio_runtime(object())
        entities = {"sound_emitters": {"bell": first}}
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            first_stats = g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(),
                self.tile_map, entities, {}, {}, self.profile,
            )
            self.assertEqual(first_stats["accepted_events"], 0)
            self.assertEqual(len(runtime["event_queue"]), 1)
            second_stats = g_audio.update_audio(
                runtime, runtime["engine"], 0.1, listener(),
                self.tile_map, entities, {}, {}, self.profile,
            )
        self.assertEqual(second_stats["accepted_events"], 1)
        self.assertEqual(runtime["event_queue"], [])
        self.assertEqual(FakeSound.instances[-1].looping, False)

    def test_emitter_distance_overrides_global_profile(self):
        event = {
            "type": "sound_emitter_cadence", "source_kind": "sound_emitter",
            "world_position": {"x": 60.0, "y": 0.0}, "gain": 1.0,
            "data": {"spatial_policy": {
                "minimum_distance": 0.0, "maximum_distance": 50.0,
                "pan_distance": 50.0, "maximum_pan": 1.0,
            }},
        }
        self.assertEqual(g_audio.estimate_event_audibility(
            event, listener(), {"direct_gain": 1.0}, self.profile,
        ), 0.0)


class VoiceAndLifecycleTests(unittest.TestCase):
    def test_low_priority_voice_can_be_stolen(self):
        active = [{"priority": 0.1, "estimated_gain": 0.05, "started_at": 0.0,
                   "event_type": "footstep", "source_kind": "enemy", "looping": False}]
        incoming = {"priority": 1.0, "event_type": "stagger_impact", "source_kind": "player"}
        self.assertEqual(g_audio.choose_voice_to_steal(active, incoming), 0)

    def test_player_gunshot_and_loops_are_protected_from_enemy_step(self):
        voices = [
            {"priority": 2.0, "estimated_gain": 1.0, "started_at": 0.0,
             "event_type": "gunshot", "source_kind": "player", "looping": False},
            {"priority": 0.0, "estimated_gain": 0.0, "started_at": 0.0,
             "event_type": "ambience", "source_kind": "world", "looping": True},
        ]
        incoming = {"priority": 0.5, "event_type": "footstep", "source_kind": "enemy"}
        self.assertIsNone(g_audio.choose_voice_to_steal(voices, incoming))

    def test_same_frame_pool_reuse_has_one_active_registration(self):
        runtime = g_audio.make_audio_runtime(object())
        runtime["manifest"] = {
            "single": g_audio._family(
                fallback="sounds/ui_hover.wav", voice_count=1, spatial=False,
            )
        }
        profile = g_audio.make_audio_profile()
        event = {"type": "ui_hover", "source_kind": "ui", "source_id": "ui:a",
                 "priority": 1.0, "gain": 1.0, "pitch": 1.0}
        with mock.patch.object(g_audio.cma, "Sound", FakeSound):
            g_audio._play_family_layer(runtime, "single", event, listener(), {}, profile)
            event["priority"] = 2.0
            g_audio._play_family_layer(runtime, "single", event, listener(), {}, profile)
        self.assertEqual(len(runtime["active_voices"]), 1)

    def test_shutdown_closes_one_shots_and_loops(self):
        one_shot = FakeSound(None, "one")
        loop = FakeSound(None, "loop")
        assets = {"audio_runtime": g_audio.make_audio_runtime(None)}
        assets["audio_runtime"]["voice_pools"] = {"x": {"voices": [{"sound": one_shot}]}}
        assets["audio_runtime"]["loop_voices"] = {"x": {"sound": loop}}
        g_audio.shutdown_audio_runtime(assets)
        self.assertTrue(one_shot.closed)
        self.assertTrue(loop.closed)

    def test_runtime_objects_do_not_enter_persistent_data(self):
        persistent = {"audio_profile": g_audio.make_audio_profile(),
                      "tile_map": make_map()}
        pickle.dumps(persistent)
        self.assertNotIn("audio_runtime", persistent)

    def test_reported_capabilities_match_binding_contract(self):
        capabilities = g_audio.detect_audio_capabilities()
        self.assertTrue(capabilities["pan"])
        self.assertTrue(capabilities["node_graph"])
        self.assertFalse(capabilities["per_sound_filter_routing"])
        self.assertFalse(capabilities["custom_processing_nodes"])
        self.assertFalse(capabilities["reverb"])
        self.assertEqual(capabilities["treatment_mode"], "gain_fallback")


if __name__ == "__main__":
    unittest.main()
