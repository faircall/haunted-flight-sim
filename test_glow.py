import copy
import pickle
import unittest
import g_glow as glow
from test_puzzles import make_arena


class GlowTests(unittest.TestCase):
    def test_linked_light_tracks_color_pulse_center_and_cleanup(self):
        arena = make_arena()
        statue = dict(type="buddha",id="statue",position=dict(tile_x=4,tile_y=5,x=8.,y=8.))
        arena["entities"].setdefault("brains",{})["statue"] = statue
        glow.set_glow(arena,"brains:statue",strength=.8,color=[.1,.8,.3],pulse="periodic",
                      pulse_speed=.5,pulse_depth=1.,light=dict(enabled=True,radius=90.,intensity=2.))
        before = copy.deepcopy(statue)
        lights = glow.build_runtime_lights(arena,{},0.)
        light = lights["effect:glow:brains:statue"]
        self.assertEqual(light["position"],{"x":72.,"y":88.})
        self.assertAlmostEqual(light["intensity"],1.6)
        self.assertEqual(light["color"],[.1,.8,.3])
        self.assertEqual(light["owner_id"],"brains:statue")
        self.assertEqual(statue,before)
        self.assertEqual(glow.build_runtime_lights(arena,{},1.),{})
        runtime = dict(lights, unrelated={"enabled":True})
        glow.replace_runtime_lights(runtime,{})
        self.assertEqual(runtime,{"unrelated":{"enabled":True}})
        statue["position"]["x"] += 3.
        self.assertEqual(glow.build_runtime_lights(arena,{},2.)["effect:glow:brains:statue"]["position"]["x"],75.)
        glow.set_glow(arena,"brains:statue",enabled=False)
        self.assertEqual(glow.build_runtime_lights(arena,{},2.),{})

    def test_rim_width_pulses_independently_of_brightness(self):
        obj = {"glow": dict(enabled=True, mode="edge", pulse="periodic",
                            pulse_speed=.5, pulse_depth=0., edge_width=5., edge_pulse=1.)}
        peak, trough = glow.settings(obj, 0.), glow.settings(obj, 1.)
        self.assertEqual(peak["edge_width"], 5.)
        self.assertEqual(trough["edge_width"], 1.)
        self.assertEqual(peak["strength"], trough["strength"])
        obj["glow"]["edge_min_width"] = 0.
        self.assertEqual(glow.settings(obj, 1.)["edge_width"], 0.)
        self.assertEqual(glow.settings(obj, 1.)["strength"], peak["strength"])
        obj["glow"]["edge_min_width"] = 10.
        self.assertEqual(glow.settings(obj, 1.)["edge_width"], 5.)
        obj["glow"]["edge_pulse"] = 0.
        self.assertEqual(glow.settings(obj, 1.)["edge_width"], 5.)

    def test_periodic_range_and_disabled_pulse(self):
        value = dict(pulse="periodic", pulse_speed=.5, pulse_depth=.8)
        self.assertAlmostEqual(glow.pulse_multiplier(value, 0.), 1.)
        self.assertAlmostEqual(glow.pulse_multiplier(value, 1.), .2)
        self.assertAlmostEqual(glow.pulse_multiplier(value, 2.), 1.)
        for override in ({"pulse": "none"}, {"pulse_speed": 0.}, {"pulse_depth": 0.}):
            self.assertEqual(glow.pulse_multiplier(dict(value, **override), 1.), 1.)

    def test_random_pulse_is_smooth_seeded_and_serializable(self):
        value = dict(pulse="random seeded", pulse_speed=1., pulse_depth=.75, pulse_seed=123)
        times = [i/120. for i in range(1200)]
        samples = [glow.pulse_multiplier(value, t) for t in times]
        self.assertTrue(all(.25 <= x <= 1. for x in samples))
        self.assertLess(max(abs(b-a) for a,b in zip(samples,samples[1:])), .03)
        restored = pickle.loads(pickle.dumps(value))
        self.assertEqual(samples[::-1], [glow.pulse_multiplier(restored,t) for t in times[::-1]])
        self.assertNotEqual(samples, [glow.pulse_multiplier(dict(value,pulse_seed=124),t) for t in times])

    def test_fade_retarget_uses_envelope_not_pulsed_brightness(self):
        arena = make_arena().set("time_elapsed", 0.)
        glow.set_glow(arena, "player", strength=.8, pulse="periodic", pulse_depth=.5, pulse_speed=.5)
        arena = arena.set("time_elapsed", 1.)
        player = arena["player_info"]
        before = glow.settings(player, 1.)["strength"]
        glow.set_glow(arena, "player", enabled=False, fade=2.)
        self.assertAlmostEqual(glow.settings(player, 1.)["strength"], before)
        self.assertAlmostEqual(glow.settings(player, 2.)["strength"], .4)
        self.assertEqual(glow.settings(player, 3.)["strength"], 0.)

    def test_fade_retarget_and_save(self):
        arena = make_arena().set("time_elapsed", 10.)
        glow.set_glow(arena, "player", strength=.8, color=[0., 1., .3], fade=2.)
        player = arena["player_info"]
        self.assertEqual(glow.settings(player, 10.)["strength"], 0.)
        self.assertAlmostEqual(glow.settings(player, 11.)["strength"], .4)
        arena = pickle.loads(pickle.dumps(arena)).set("time_elapsed", 11.)
        glow.set_glow(arena, "player", enabled=False, fade=2.)
        player = arena["player_info"]
        self.assertAlmostEqual(glow.settings(player, 11.)["strength"], .4)
        self.assertAlmostEqual(glow.settings(player, 12.)["strength"], .2)
        self.assertEqual(glow.settings(player, 13.)["strength"], 0.)

    def test_defaults_and_missing_target(self):
        arena = make_arena()
        before = copy.deepcopy(arena)
        with self.assertRaises(ValueError):
            glow.set_glow(arena, "missing")
        self.assertEqual(arena, before)
        self.assertEqual(glow.settings({})["strength"], 0.)
        self.assertEqual(glow.settings({"type": "fire"}, effect=True)["strength"], .25)
        self.assertEqual(glow.settings({"type": "fire", "glow": {"enabled": False}}, effect=True)["strength"], 0.)
        glow.set_glow(arena, "player", mode="edge")
        self.assertEqual(glow.settings(arena["player_info"])["mode"], "edge")
        self.assertEqual(glow.settings({})["mode"], "whole")
        with self.assertRaises(ValueError):
            glow.set_glow(arena, "player", mode="invalid")
