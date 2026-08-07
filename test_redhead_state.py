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


if __name__ == "__main__":
    unittest.main()
