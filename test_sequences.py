import copy
import pickle
import unittest
from unittest.mock import patch

import g_sequences as s
import g_sequence_editor as editor
import g_puzzles as p
import g_audio
import g_editor
import g_ui
from test_puzzles import make_arena, place


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.arena = s.ensure(make_arena())

    def sequence(self, count=3):
        definition = s.make_sequence()
        definition["targets"] = [s.create_torch(self.arena, {"x":100.+i*30, "y":100.}) for i in range(count)]
        self.arena["world_sequences"]["sequences"]["test"] = definition
        return definition

    def test_frame_skip_fires_all_steps_and_completion_once(self):
        definition = self.sequence()
        definition.update(delay=.2, interval=.1, fade_in=.3)
        s.start_sequence(self.arena, "test")
        s.update_sequences(self.arena, .15)
        self.assertEqual(self.arena["sequence_runtime"]["sounds"], [])
        s.update_sequences(self.arena, 1.)
        self.assertEqual(len(self.arena["sequence_runtime"]["sounds"]), 5)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 1)
        s.update_sequences(self.arena, 20.)
        s.start_sequence(self.arena, "test")
        self.assertEqual(len(self.arena["sequence_runtime"]["sounds"]), 5)

    def test_torch_seeds_upgrade_once_and_survive_save(self):
        with patch.object(s, "new_id", side_effect=["torch:a", "torch:b", "torch:c"]):
            definition = self.sequence()
        torches = [s.resolve(self.arena, ref) for ref in definition["targets"]]
        self.assertEqual(len({obj["seed"] for obj in torches}), 3)
        for obj in torches:
            obj.pop("individual_fire_seed")
        torches[0]["seed"] = 2207
        torches[1].pop("seed")
        torches[2]["seed"] = 123
        self.arena = s.ensure(self.arena)
        self.assertEqual([obj["seed"] for obj in torches],
                         [s.fire_seed("torch:a"), s.fire_seed("torch:b"), 123])
        # After migration, even an intentional default seed is left alone.
        torches[0]["seed"] = 2207
        restored = s.ensure(pickle.loads(pickle.dumps(self.arena)))
        self.assertEqual(restored["entities"]["emitters"], self.arena["entities"]["emitters"])

    def test_save_mid_sequence_preserves_cursor_without_replaying_cues(self):
        self.sequence()
        s.start_sequence(self.arena, "test")
        s.update_sequences(self.arena, .1)
        self.assertEqual(len(self.arena["sequence_runtime"]["sounds"]), 2)
        self.arena = s.ensure(pickle.loads(pickle.dumps(self.arena.remove("sequence_runtime"))))
        s.update_sequences(self.arena, .3)
        self.assertEqual(len(self.arena["sequence_runtime"]["sounds"]), 1)
        self.assertEqual(self.arena["sequence_state"]["sequences"]["test"]["next"], 2)

    def test_preview_and_runtime_do_not_mutate_authored_intensities(self):
        definition = self.sequence(1)
        ref = definition["targets"][0]
        original = copy.deepcopy(s.resolve(self.arena, ref))
        before = copy.deepcopy(self.arena["sequence_state"])
        preview = editor.make_preview(self.arena, "test", definition)
        preview["elapsed"] = .3
        projected = s.presentation_entities(self.arena, preview)
        self.assertAlmostEqual(projected["emitters"][ref["id"]]["light"]["intensity"], original["light"]["intensity"]*.5)
        self.assertEqual(s.resolve(self.arena, ref), original)
        self.assertEqual(self.arena["sequence_state"], before)
        self.assertFalse(s.presentation_entities(self.arena)["emitters"][ref["id"]]["enabled"])

    def test_path_constant_distance_and_caps(self):
        points = [{"x":0.,"y":0.},{"x":10.,"y":0.},{"x":10.,"y":90.}]
        sites = s.path_sites(points, 20)
        self.assertEqual([site["distance"] for site in sites], [0,20,40,60,80,100])
        self.assertEqual(sites[1]["point"], {"x":10.,"y":10.})
        self.assertLessEqual(len(s.path_sites([points[0],{"x":100000.,"y":0.}], 1)), s.MAX_PATH_SITES)
        definition = s.make_sequence()
        definition.update(mode="path", points=points, spacing=1., speed=10.)
        preview = editor.make_preview(self.arena, "path", definition)
        preview["elapsed"] = 100.
        emitters = s.presentation_entities(self.arena, preview)["emitters"]
        self.assertLessEqual(sum(obj["light"]["enabled"] for obj in emitters.values()), s.MAX_PATH_LIGHTS)
        self.assertEqual(set(emitters), set(s.presentation_entities(self.arena, preview)["emitters"]))
        seeds = {key: obj["seed"] for key, obj in emitters.items()}
        self.assertEqual(len(set(seeds.values())), len(seeds))
        preview = pickle.loads(pickle.dumps(preview))
        preview["elapsed"] += 1.
        self.assertEqual(seeds, {key: obj["seed"] for key, obj in
                                s.presentation_entities(self.arena, preview)["emitters"].items()})

    def test_pulse_and_fill_timing(self):
        definition = self.sequence(2)
        definition.update(interval=1., fade_in=.5, hold=.5, fade_out=.5, style="pulse")
        sites = s.schedule(self.arena, definition)
        self.assertEqual(s.site_weight(definition, sites, sites[0], 1.5), 0.)
        self.assertEqual(s.site_weight(definition, sites, sites[1], 1.5), 1.)
        definition["style"] = "fill"
        self.assertEqual(s.site_weight(definition, sites, sites[0], 1.5), 1.)
        self.assertEqual(s.sequence_duration(definition, sites), 2.5)

    def trigger(self):
        area = s.make_trigger([[3,3],[4,3]])
        area.update(on_enter="none", on_exit="none", repeat="every entry")
        self.arena["world_sequences"]["triggers"]["area"] = area
        return area

    def move_player(self, x, y):
        self.arena["player_info"]["position"] = dict(tile_x=x,tile_y=y,x=8.,y=8.)
        s.update_triggers(self.arena)

    def test_trigger_crossings_not_internal_tiles_and_load_inside_silent(self):
        self.trigger()
        s.update_triggers(self.arena)
        self.move_player(3,3)
        self.move_player(4,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 1)
        self.arena = s.ensure(pickle.loads(pickle.dumps(self.arena.remove("sequence_runtime"))))
        self.move_player(3,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 1)
        self.move_player(5,3)
        self.assertEqual(self.arena["sequence_state"]["events"][-1]["type"], "trigger_exit")

    def test_trigger_once_cooldown_and_enabled(self):
        area = self.trigger()
        area["repeat"] = "once"
        s.update_triggers(self.arena)
        for _ in range(2):
            self.move_player(3,3)
            self.move_player(5,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 2)
        area["repeat"] = "cooldown"
        self.move_player(3,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 2)
        self.arena["sequence_state"]["time"] = 10.
        self.move_player(5,3)
        self.move_player(3,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 4)
        s.set_trigger_enabled(self.arena, "area", False)
        self.move_player(5,3)
        self.assertEqual(len(self.arena["sequence_state"]["events"]), 4)

    def encounter(self):
        a, b = place(self.arena,"puzzle spawn",x=10),place(self.arena,"puzzle spawn",x=15)
        self.arena["world_sequences"]["encounters"]["fight"] = {"spawns":[
            {"marker":a["persistent_id"],"type":"red head","at":0.},
            {"marker":b["persistent_id"],"type":"red head","at":2.}],"on_complete":"none","data":{}}
        s.spawn_encounter(self.arena,"fight")
        return a,b

    def test_multiwave_membership_death_vs_unload_and_repeat_instances(self):
        self.encounter()
        s.update_encounters(self.arena, .1)
        record = self.arena["sequence_state"]["encounters"]["fight"]
        enemy_id = next(iter(record["members"]))
        enemy = self.arena["entities"]["brains"].pop(enemy_id)
        s.update_encounters(self.arena, 3.)
        self.assertEqual(record["status"],"running")
        for eid in record["members"]:
            s.record_defeat(self.arena,eid)
        s.update_encounters(self.arena, 0.)
        self.assertEqual(record["status"],"completed")
        self.assertEqual(len(self.arena["sequence_state"]["events"]),1)
        s.update_encounters(self.arena, 5.)
        s.spawn_encounter(self.arena,"fight",restart=True)
        self.assertEqual(self.arena["sequence_state"]["encounters"]["fight"]["generation"],2)

    def test_blocked_spawn_retries_and_delays_completion(self):
        a,b = self.encounter()
        self.arena["tile_map"]["tiles"][6*30+10]["force_collidable"] = True
        s.update_encounters(self.arena, .1)
        record = self.arena["sequence_state"]["encounters"]["fight"]
        self.assertEqual(record["spawned"],[])
        self.arena["tile_map"]["tiles"][6*30+10]["force_collidable"] = False
        s.update_encounters(self.arena, .1)
        self.assertEqual(record["spawned"],[0])
        eid = next(iter(record["members"]))
        self.arena["entities"]["brains"][eid]["health"] = 0
        s.update_encounters(self.arena, .1)
        self.assertEqual(record["status"],"running")

    def test_event_queue_chaining_and_errors_are_bounded(self):
        def chain(arena,event):
            return s.queue_event(arena,"next","x","chain")
        with patch.dict(s.data.HANDLERS,{"chain":chain}):
            s.queue_event(self.arena,"first","x","chain")
            self.arena = s.dispatch_events(self.arena)
        self.assertEqual(len(self.arena["sequence_runtime"]["log"]),s.MAX_EVENTS_PER_FRAME)
        self.arena = s.dispatch_events(self.arena)
        self.assertEqual(len(self.arena["sequence_runtime"]["errors"]),1)

    def test_authoring_draft_cancellation_and_finish(self):
        st = editor.state({})
        st["tool"] = "Place torches"
        draft = editor.begin_draft(st)
        draft["entries"] = [{"point":{"x":100.,"y":100.}},{"point":{"x":140.,"y":100.}}]
        self.assertEqual(self.arena["entities"].get("emitters",{}),{})
        self.arena = editor.finish_draft(self.arena,st)
        sequence = self.arena["world_sequences"]["sequences"][st["selected"]]
        self.assertEqual(len(sequence["targets"]),2)
        self.assertIsNone(st["draft"])

    def test_circle_path_and_existing_trigger_edit_preserve_identity(self):
        st = editor.state({})
        st.update(tool="Circle",circle_fire=True)
        draft=editor.begin_draft(st)
        draft.update(centre={"x":100.,"y":100.},edge={"x":140.,"y":100.})
        editor.finish_draft(self.arena,st)
        definition = self.arena["world_sequences"]["sequences"][st["selected"]]
        self.assertTrue(definition["closed"])
        self.assertEqual(definition["mode"],"path")
        self.trigger()
        st.update(tool="Trigger paint",selected="area",kind="triggers")
        draft=editor.begin_draft(st)
        draft.update(replace="area",cells=[[7,8]])
        editor.finish_draft(self.arena,st)
        self.assertEqual(list(self.arena["world_sequences"]["triggers"]),["area"])
        self.assertEqual(self.arena["world_sequences"]["triggers"]["area"]["cells"],[[7,8]])

    def test_courtyard_complete_chain(self):
        editor.create_courtyard(self.arena,{"x":200.,"y":140.})
        demo=self.arena["world_sequences"]["demo"]
        s.update_triggers(self.arena)
        self.move_player(12,12)
        self.arena=s.dispatch_events(self.arena)
        self.assertIn(demo["sequence"],self.arena["sequence_state"]["sequences"])
        self.arena=s.update(self.arena,10.)
        self.arena=s.update(self.arena,.1)
        self.assertEqual(len(self.arena["entities"]["brains"]),2)
        for enemy in self.arena["entities"]["brains"].values():
            enemy["health"]=0
        self.arena=s.update(self.arena,.1)
        self.assertTrue(self.arena["puzzle_state"]["facts"]["courtyard_guardians_defeated"])
        self.assertEqual(self.arena["sequence_state"]["music"]["track"],"silence")
        door=next(obj for obj in p.objects(self.arena) if obj["type"] in p.DOOR_TYPES)
        self.assertTrue(p.object_state(self.arena,door)["unlocked"])

    def test_music_request_reuses_loop_and_fades_out(self):
        runtime={"manifest":{},"frame":1,"sequence_music":{"track":"ritual_bells","fade":3.}}
        g_audio.request_sequence_music(runtime)
        loop=runtime["loop_voices"]["sequence_music:ritual_bells"]
        self.assertEqual(loop["fade_seconds"],3.)
        runtime["frame"]=2
        g_audio.request_sequence_music(runtime)
        self.assertIs(loop,runtime["loop_voices"]["sequence_music:ritual_bells"])
        runtime["frame"]=3
        runtime["sequence_music"]={"track":"silence","fade":2.}
        g_audio.request_sequence_music(runtime)
        self.assertEqual(loop["last_requested_frame"],2)
        self.assertEqual(loop["fade_seconds"],2.)

    def test_shared_target_latest_started_sequence_owns_activation(self):
        definition=self.sequence(1)
        ref=definition["targets"][0]
        s.start_sequence(self.arena,"test")
        s.update_sequences(self.arena,3.)
        next_definition=copy.deepcopy(definition)
        next_definition.update(delay=1.,style="pulse",fade_in=0.,hold=.1,fade_out=0.)
        self.arena["world_sequences"]["sequences"]["next"]=next_definition
        s.start_sequence(self.arena,"next")
        self.assertFalse(s.presentation_entities(self.arena)["emitters"][ref["id"]]["enabled"])
        s.update_sequences(self.arena,1.05)
        self.assertTrue(s.torch_is_active(self.arena,ref))
        s.update_sequences(self.arena,1.)
        self.assertFalse(s.torch_is_active(self.arena,ref))
        self.assertFalse(s.presentation_entities(self.arena)["emitters"][ref["id"]]["enabled"])

    def test_existing_disabled_light_can_be_activated_without_overwriting_authoring(self):
        light=g_editor.make_default_point_light({"tile_x":2,"tile_y":2,"x":8.,"y":8.})
        light.update(enabled=False,intensity=2.5)
        self.arena["entities"]["lights"]={"lamp":light}
        definition=s.make_sequence()
        definition["targets"]=[{"collection":"lights","id":"lamp"}]
        self.arena["world_sequences"]["sequences"]["light"]=definition
        s.start_sequence(self.arena,"light")
        s.update_sequences(self.arena,1.)
        projected=s.presentation_entities(self.arena)["lights"]["lamp"]
        self.assertTrue(projected["enabled"])
        self.assertEqual(projected["intensity"],2.5)
        self.assertFalse(light["enabled"])

    def test_scrubbing_suppresses_loops_even_with_audition_enabled(self):
        definition=self.sequence(1)
        preview=editor.make_preview(self.arena,"test",definition)
        preview["elapsed"]=1.
        entities=s.presentation_entities(self.arena,preview)
        self.assertEqual(editor.audio_emitters(entities,preview,True),{})
        preview["playing"]=True
        self.assertTrue(editor.audio_emitters(entities,preview,True))
        self.assertEqual(editor.audio_emitters(entities,preview,False),{})

    def test_editor_click_place_cancel_and_gap_free_trigger_paint(self):
        ed={}
        st=editor.state(ed)
        st["tool"]="Place torches"
        ui=g_ui.make_ui_state()
        camera=editor.pr.Vector3(0,0,0)
        def tick(x,y,key=None,held=True):
            with patch.object(g_ui,"get_mouse_position",return_value=editor.pr.Vector2(x,y)), \
                 patch.object(g_ui,"interactive_mouse_left_pressed",return_value=held), \
                 patch.object(g_ui,"interactive_mouse_left_down",return_value=held), \
                 patch.object(editor.pr,"is_mouse_button_released",return_value=False), \
                 patch.object(editor.pr,"is_key_pressed",side_effect=lambda k:k==key), \
                 patch.object(editor.pr,"is_key_down",return_value=False):
                self.arena=editor.update_editor(self.arena,ed,ui,camera,True,.01)
        tick(80,80)
        self.assertEqual(len(st["draft"]["entries"]),1)
        tick(80,80,editor.pr.KeyboardKey.KEY_ESCAPE,False)
        self.assertIsNone(st["draft"])
        self.assertEqual(self.arena["entities"].get("emitters",{}),{})
        st["tool"]="Trigger paint"
        tick(80,80)
        tick(160,80)
        self.assertEqual(st["draft"]["cells"],[[x,5] for x in range(5,11)])

    def test_direction_start_member_and_sound_overrides(self):
        definition=self.sequence()
        definition.update(start_index=1,reverse=True)
        sites=s.schedule(self.arena,definition)
        self.assertEqual([site["ref"] for site in sites],[definition["targets"][1],definition["targets"][0],definition["targets"][2]])
        definition["sound_overrides"][s.ref_key(sites[0]["ref"]) ]="none"
        s.start_sequence(self.arena,"test")
        s.update_sequences(self.arena,.1)
        self.assertEqual(len(self.arena["sequence_runtime"]["sounds"]),1) # start only

    def test_readable_names_resolve_without_changing_saved_identity(self):
        definition=self.sequence(1)
        definition["label"]="Courtyard torches"
        s.start_sequence(self.arena,"Courtyard torches")
        self.assertIn("test",self.arena["sequence_state"]["sequences"])
        self.arena["world_sequences"]["sequences"]["duplicate"]=copy.deepcopy(definition)
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            s.start_sequence(self.arena,"Courtyard torches")

    def test_failed_callback_survives_save_for_explicit_retry(self):
        s.queue_event(self.arena,"test","area","unknown")
        self.arena=s.dispatch_events(self.arena)
        self.arena=s.ensure(pickle.loads(pickle.dumps(self.arena.remove("sequence_runtime"))))
        self.assertEqual(len(self.arena["sequence_runtime"]["errors"]),1)
        event=self.arena["sequence_runtime"]["errors"].pop()["event"]
        self.arena["sequence_state"]["events"].append(event)
        with patch.dict(s.data.HANDLERS,{"unknown":lambda arena,event:arena.set("retry_worked",True)}):
            self.arena=s.dispatch_events(self.arena)
        self.assertTrue(self.arena["retry_worked"])
        self.assertFalse(self.arena["sequence_state"]["failed_events"])

    def test_deleted_member_blocks_completion_instead_of_unlocking_on_missing_object(self):
        definition=self.sequence(1)
        s.start_sequence(self.arena,"test")
        del self.arena["entities"]["emitters"][definition["targets"][0]["id"]]
        s.update_sequences(self.arena,100.)
        record=self.arena["sequence_state"]["sequences"]["test"]
        self.assertEqual(record["status"],"running")
        self.assertTrue(record["blocked"])
        self.assertFalse(self.arena["sequence_state"]["events"])

    def test_world_validation_and_saved_encounter_membership(self):
        self.encounter()
        s.update_encounters(self.arena,3.)
        self.arena=s.ensure(pickle.loads(pickle.dumps(self.arena.remove("sequence_runtime"))))
        count=len(self.arena["entities"]["brains"])
        s.update_encounters(self.arena,.1)
        self.assertEqual(len(self.arena["entities"]["brains"]),count)
        self.trigger()["on_enter"]="missing_handler"
        self.assertTrue(any("unknown on_enter" in error for error in s.validate_world(self.arena)))


if __name__ == "__main__":
    unittest.main()
