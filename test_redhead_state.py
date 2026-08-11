import unittest
from unittest import mock

import g_audio
import g_update_and_render as game


def make_redhead(tile_x=1, tile_y=1):
    entity = {
        "id": 7,
        "type": "red head",
        "position": {"tile_x": tile_x, "tile_y": tile_y, "x": 8.0, "y": 8.0},
        "entity_width": 24,
        "entity_height": 24,
        "current_state": "idle",
        "previous_state": "idle",
    }
    game.give_entity_stats_from_type(entity, "red head")
    return entity


def make_player(tile_x=4, tile_y=1):
    return {
        "position": {"tile_x": tile_x, "tile_y": tile_y, "x": 8.0, "y": 8.0},
        "entity_width": 24,
        "entity_height": 24,
        "health": 100,
    }


class RedheadNoticeStateTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(8, 4, 16, 16)
        self.entity = make_redhead()
        self.player = make_player()
        self.audio = g_audio.make_audio_runtime()

    def transition(self, dt):
        current = self.entity["current_state"]
        next_state = game.transition_entity_state(
            self.entity, current, self.player, self.tile_map, None,
            self.audio, dt,
        )
        self.entity["current_state"] = next_state
        return next_state

    def test_startle_then_confirmed_pursuit_hiss_fire_once_on_entries(self):
        visible = (True, self.player["position"])
        with mock.patch.object(game, "alice_can_see_bob_points", return_value=visible):
            self.assertEqual(self.transition(0.1), "noticing")
            self.assertEqual(self.audio["event_queue"], [])

            self.assertEqual(self.transition(0.4), "noticing")
            self.assertEqual(
                [event["type"] for event in self.audio["event_queue"]],
                ["redhead_startle"],
            )

            self.assertEqual(self.transition(0.6), "angry chase")
            self.assertEqual(
                [event["type"] for event in self.audio["event_queue"]],
                ["redhead_startle"],
            )

            with mock.patch.object(
                    game, "angry_chase_state", return_value="angry chase"):
                self.assertEqual(self.transition(0.1), "angry chase")
                self.assertEqual(self.transition(0.1), "angry chase")

        self.assertEqual(
            [event["type"] for event in self.audio["event_queue"]],
            ["redhead_startle", "redhead_pursuit_hiss"],
        )
        self.assertTrue(all(
            event["source_kind"] == "enemy"
            and event["world_position"] == {"x": 24.0, "y": 24.0}
            for event in self.audio["event_queue"]
        ))

    def test_failed_visibility_check_returns_idle_without_hiss(self):
        visible = (True, self.player["position"])
        with mock.patch.object(game, "alice_can_see_bob_points", return_value=visible):
            self.assertEqual(self.transition(0.1), "noticing")
            self.assertEqual(self.transition(0.5), "noticing")
        with mock.patch.object(
                game, "alice_can_see_bob_points", return_value=(False, None)):
            self.assertEqual(self.transition(0.5), "idle")
        self.assertEqual(
            [event["type"] for event in self.audio["event_queue"]],
            ["redhead_startle"],
        )

    def test_returning_to_chase_from_attack_does_not_hiss(self):
        self.entity.update({
            "current_state": "angry chase",
            "previous_state": "angry and attacking",
        })
        with mock.patch.object(
                game, "angry_chase_state", return_value="angry chase"):
            self.assertEqual(self.transition(0.1), "angry chase")
        self.assertEqual(self.audio["event_queue"], [])


class RedheadAttackRangeTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(12, 4, 16, 16)
        self.entity = make_redhead(tile_x=1)
        self.entity.update({
            "current_state": "angry and attacking",
            "previous_state": "angry and attacking",
            "path_to_player": [self.tile_map["tiles"][1 + 1 * 12]],
            "path_to_player_current_index": 0,
        })
        self.player = make_player(tile_x=8)

    def test_out_of_range_must_persist_for_one_second_before_chase(self):
        visible = (True, self.player["position"])
        with mock.patch.object(game, "alice_can_see_bob_points", return_value=visible):
            self.assertEqual(game.attack_state(
                self.entity, "angry and attacking", self.player,
                self.tile_map, None, None, 0.5,
            ), "angry and attacking")
            self.assertAlmostEqual(self.entity["attack_out_of_range_timer"], 0.5)
            self.assertEqual(game.attack_state(
                self.entity, "angry and attacking", self.player,
                self.tile_map, None, None, 0.49,
            ), "angry and attacking")
            self.assertEqual(game.attack_state(
                self.entity, "angry and attacking", self.player,
                self.tile_map, None, None, 0.01,
            ), "angry chase")
        self.assertEqual(self.entity["attack_out_of_range_timer"], 0.0)
        self.assertEqual(self.entity["attack_substate"], "windup")
        self.assertEqual(self.entity["attack_timer"], 0.0)

    def test_returning_in_range_cancels_pending_chase(self):
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"]),
        ):
            game.attack_state(
                self.entity, "angry and attacking", self.player,
                self.tile_map, None, None, 0.6,
            )
            self.player["position"]["tile_x"] = 2
            game.attack_state(
                self.entity, "angry and attacking", self.player,
                self.tile_map, None, None, 0.1,
            )
        self.assertEqual(self.entity["attack_out_of_range_timer"], 0.0)


class RedheadEvadeStateTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(16, 6, 16, 16)
        self.entity = make_redhead(tile_x=5, tile_y=2)
        self.player = make_player(tile_x=1, tile_y=2)
        self.player["aim_direction"] = {"x": 1.0, "y": 0.0}
        self.audio = g_audio.make_audio_runtime()

    def test_evade_settings_are_fresh_and_clamped(self):
        other = make_redhead()
        self.entity["evade_settings"]["chance"] = 2.0
        self.entity["evade_settings"]["duration_min"] = 2.0
        self.entity["evade_settings"]["duration_max"] = 1.0
        settings = game.get_redhead_evade_settings(self.entity)
        self.assertEqual(settings["chance"], 1.0)
        self.assertEqual(settings["duration_min"], 2.0)
        self.assertEqual(settings["duration_max"], 2.0)
        self.assertEqual(
            other["evade_settings"]["chance"],
            game.REDHEAD_EVADE_DEFAULTS["chance"],
        )

    def test_aim_threat_uses_player_heading_and_expanded_body_hurtbox(self):
        self.assertTrue(game.player_is_aiming_near_redhead(
            self.player, self.entity, self.tile_map,
        ))
        self.player["aim_direction"] = {"x": 0.0, "y": -1.0}
        self.assertFalse(game.player_is_aiming_near_redhead(
            self.player, self.entity, self.tile_map,
        ))
        self.player["aim_direction"] = {"x": -1.0, "y": 0.0}
        self.assertFalse(game.player_is_aiming_near_redhead(
            self.player, self.entity, self.tile_map,
        ))

    def test_trigger_requires_reaction_time_and_rolls_once(self):
        settings = self.entity["evade_settings"]
        settings.update({"chance": 1.0, "reaction_time": 0.15})
        with mock.patch.object(game.random, "random", return_value=0.0):
            self.assertFalse(game.update_redhead_evade_trigger(
                self.entity, self.player, self.tile_map, True, 0.10,
            ))
            self.assertTrue(game.update_redhead_evade_trigger(
                self.entity, self.player, self.tile_map, True, 0.05,
            ))
        self.assertEqual(self.entity["evade_reaction_timer"], 0.0)

    def test_failed_roll_sets_retry_delay(self):
        self.entity["evade_settings"].update({
            "chance": 0.0, "reaction_time": 0.0,
            "failed_retry_delay": 0.6,
        })
        self.assertFalse(game.update_redhead_evade_trigger(
            self.entity, self.player, self.tile_map, True, 0.01,
        ))
        self.assertEqual(self.entity["evade_retry_timer"], 0.6)
        self.assertFalse(game.update_redhead_evade_trigger(
            self.entity, self.player, self.tile_map, True, 1.0,
        ))

    def test_angry_chase_enters_evade_when_confirmed_aim_roll_succeeds(self):
        self.entity["evade_settings"].update({
            "chance": 1.0, "reaction_time": 0.0,
        })
        self.entity.update({
            "current_state": "angry chase",
            "previous_state": "angry chase",
            "path_to_player": [self.tile_map["tiles"][2 * 16 + 5]],
            "path_to_player_current_index": 0,
            "last_seen_player_pos": dict(self.player["position"]),
        })
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"])), \
                mock.patch.object(game, "alice_can_move_to_bob", return_value=True), \
                mock.patch.object(
                    game, "move_entity_towards_target_abs",
                    return_value=dict(self.entity["position"])), \
                mock.patch.object(game.random, "random", return_value=0.0):
            self.assertEqual(game.angry_chase_state(
                self.entity, "angry chase", self.player, self.tile_map,
                None, self.audio, 0.01,
            ), "evade")

    def test_evade_entry_initialises_once_and_queues_positional_bark(self):
        self.entity.update({
            "current_state": "evade", "previous_state": "angry chase",
        })
        with mock.patch.object(game.random, "uniform", side_effect=(1.5, 0.4)), \
                mock.patch.object(game.random, "random", return_value=0.25), \
                mock.patch.object(game, "evade_redhead_state", return_value="evade"):
            next_state = game.transition_entity_state(
                self.entity, "evade", self.player, self.tile_map, None,
                self.audio, 0.1,
            )
            self.entity["current_state"] = next_state
            game.transition_entity_state(
                self.entity, "evade", self.player, self.tile_map, None,
                self.audio, 0.1,
            )
        self.assertEqual(self.entity["evade_duration"], 1.5)
        self.assertEqual(self.entity["evade_side"], -1.0)
        self.assertEqual(
            [event["type"] for event in self.audio["event_queue"]],
            ["redhead_evade"],
        )
        self.assertEqual(
            self.audio["event_queue"][0]["world_position"],
            {"x": 88.0, "y": 40.0},
        )

    def test_evade_direction_has_lateral_and_forward_components(self):
        target = {"x": 200.0, "y": 40.0}
        right = game.redhead_evade_direction(
            self.entity, target, self.tile_map, side=1.0,
        )
        left = game.redhead_evade_direction(
            self.entity, target, self.tile_map, side=-1.0,
        )
        self.assertGreater(right["x"], 0.0)
        self.assertGreater(right["y"], 0.0)
        self.assertGreater(left["x"], 0.0)
        self.assertLess(left["y"], 0.0)

    def test_evade_moves_forward_then_resumes_existing_chase_path(self):
        path = [
            self.tile_map["tiles"][2 * 16 + tile_x]
            for tile_x in range(5, 13)
        ]
        self.entity.update({
            "current_state": "evade", "previous_state": "evade",
            "path_to_player": path,
            "path_to_player_current_index": 0,
            "last_seen_player_pos": dict(self.player["position"]),
            "evade_elapsed": 0.0,
            "evade_duration": 0.2,
            "evade_side": 1.0,
            "evade_side_switch_timer": 1.0,
        })
        self.player["position"]["tile_x"] = 14
        before = game.make_pos_abs(self.entity["position"], 16, 16)
        target = game.make_pos_abs(self.player["position"], 16, 16)
        before_distance = game.vec2_distance(before, target)
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"])), \
                mock.patch.object(game, "alice_can_move_to_bob", return_value=True):
            self.assertEqual(game.evade_redhead_state(
                self.entity, "evade", self.player, self.tile_map, None, 0.1,
            ), "evade")
            self.assertEqual(game.evade_redhead_state(
                self.entity, "evade", self.player, self.tile_map, None, 0.1,
            ), "angry chase")
        after = game.make_pos_abs(self.entity["position"], 16, 16)
        self.assertLess(game.vec2_distance(after, target), before_distance)
        self.assertIs(self.entity["path_to_player"], path)

    def test_stagger_resume_does_not_restart_or_rebark_evade(self):
        self.entity.update({
            "current_state": "evade", "previous_state": "stagger",
            "previous_state_on_stagger": "evade",
            "evade_elapsed": 0.7, "evade_duration": 1.4,
            "evade_side": 1.0, "evade_side_switch_timer": 0.2,
        })
        with mock.patch.object(game, "evade_redhead_state", return_value="evade"):
            game.transition_entity_state(
                self.entity, "evade", self.player, self.tile_map, None,
                self.audio, 0.1,
            )
        self.assertEqual(self.entity["evade_elapsed"], 0.7)
        self.assertEqual(self.audio["event_queue"], [])


if __name__ == "__main__":
    unittest.main()
