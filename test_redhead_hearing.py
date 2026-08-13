import unittest
from unittest import mock

import g_audio
import g_update_and_render as game
from test_redhead_state import make_player, make_redhead


class RedheadHearingTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(24, 12, 16, 16)
        self.player = make_player(3, 5)
        self.player["id"] = "player"
        self.audio = g_audio.make_audio_runtime()

    def redhead_on_tile(self, entity_id, tile_x, tile_y=5):
        entity = make_redhead(tile_x, tile_y)
        entity["id"] = entity_id
        entity["position"] = game.entity_position_for_collision_tile_center(
            entity, tile_x, tile_y, self.tile_map,
        )
        return entity

    def sound_event(self, event_type="footstep", tile_x=3, tile_y=5,
                    gait="walk", source_kind="player", source_id="player"):
        return {
            "type": event_type,
            "source_id": source_id,
            "source_kind": source_kind,
            "world_position": {
                "x": tile_x * 16.0 + 8.0,
                "y": tile_y * 16.0 + 8.0,
            },
            "priority": 1.0,
            "gain": 1.0,
            "data": {"gait": gait},
        }

    def test_sound_flood_is_bounded_and_blocked_by_walls(self):
        for tile_y in range(self.tile_map["map_height"]):
            self.tile_map["tiles"][tile_y * 24 + 5]["index"] = 3

        distances = game.propagate_ai_sound_distances(
            self.sound_event()["world_position"], self.tile_map, 10.0,
        )

        self.assertIn((4, 5), distances)
        self.assertNotIn((5, 5), distances)
        self.assertNotIn((7, 5), distances)
        self.assertTrue(all(distance <= 10 for distance in distances.values()))

    def test_footstep_falloff_contributes_more_to_nearer_redhead(self):
        near = self.redhead_on_tile(1, 4)
        far = self.redhead_on_tile(2, 8)
        entities = {"brains": {1: near, 2: far}}

        game.update_redhead_sound_awareness(
            entities, self.tile_map, [self.sound_event()], 0.1,
        )

        near_alert = near["sound_awareness"]["accumulator"]
        far_alert = far["sound_awareness"]["accumulator"]
        self.assertGreater(near_alert, far_alert)
        self.assertGreater(far_alert, 0.0)

    def test_only_player_footsteps_contribute(self):
        entity = self.redhead_on_tile(1, 4)
        entities = {"brains": {1: entity}}

        stats = game.update_redhead_sound_awareness(
            entities, self.tile_map,
            [self.sound_event(source_kind="enemy", source_id="enemy:7")],
            0.1,
        )

        self.assertEqual(stats["sound_groups"], 0)
        self.assertEqual(entity["sound_awareness"]["accumulator"], 0.0)

    def test_same_tile_footsteps_coalesce_into_one_propagation(self):
        entity = self.redhead_on_tile(1, 4)
        entity["hearing_settings"].update({
            "startle_threshold": 10.0,
            "chase_threshold": 20.0,
        })
        events = [self.sound_event(), self.sound_event()]

        stats = game.update_redhead_sound_awareness(
            {"brains": {1: entity}}, self.tile_map, events, 0.1,
        )

        self.assertEqual(stats["sound_groups"], 1)
        self.assertEqual(stats["floods"], 1)
        expected = 2.0 * 0.40 * (1.0 - 1.0 / 8.0)
        self.assertAlmostEqual(
            entity["sound_awareness"]["accumulator"], expected,
        )

    def test_running_footstep_is_louder_and_reaches_farther(self):
        walking_listener = self.redhead_on_tile(1, 11)
        running_listener = self.redhead_on_tile(2, 11)

        game.update_redhead_sound_awareness(
            {"brains": {1: walking_listener}}, self.tile_map,
            [self.sound_event(gait="walk")], 0.1,
        )
        game.update_redhead_sound_awareness(
            {"brains": {2: running_listener}}, self.tile_map,
            [self.sound_event(gait="run")], 0.1,
        )

        self.assertEqual(
            walking_listener["sound_awareness"]["accumulator"], 0.0,
        )
        self.assertGreater(
            running_listener["sound_awareness"]["accumulator"], 0.0,
        )

    def test_cumulative_footsteps_startle_then_commit_to_chase(self):
        entity = self.redhead_on_tile(1, 4)
        entity["hearing_settings"].update({
            "walk_footstep_contribution": 0.6,
            "startle_threshold": 0.5,
            "chase_threshold": 1.0,
        })
        entities = {"brains": {1: entity}}
        event = self.sound_event()

        game.update_redhead_sound_awareness(
            entities, self.tile_map, [event], 0.1,
        )
        self.assertEqual(
            entity["pending_awareness_stimulus"]["type"], "sound",
        )
        self.assertNotIn("pending_player_sound_chase", entity)
        state = game.idle_redhead_state(
            entity, "idle", self.player, self.tile_map, None, 0.01,
        )
        self.assertEqual(state, "noticing")
        entity.update({"current_state": "noticing", "previous_state": "idle"})

        game.update_redhead_sound_awareness(
            entities, self.tile_map, [event], 0.1,
        )
        self.assertIn("pending_player_sound_chase", entity)
        with mock.patch.object(
                game, "prepare_redhead_pursuit_path", return_value=True), \
                mock.patch.object(game, "alert_visible_redhead_allies") as alert:
            state = game.transition_entity_state(
                entity, "noticing", self.player, self.tile_map, None,
                self.audio, 0.01, {"entities": entities},
            )

        self.assertEqual(state, "angry chase")
        alert.assert_called_once()

    def test_ten_seconds_of_silence_resets_cumulative_alert(self):
        entity = self.redhead_on_tile(1, 4)
        entities = {"brains": {1: entity}}
        game.update_redhead_sound_awareness(
            entities, self.tile_map, [self.sound_event()], 0.1,
        )

        game.update_redhead_sound_awareness(
            entities, self.tile_map, [], 9.9,
        )
        self.assertGreater(entity["sound_awareness"]["accumulator"], 0.0)
        game.update_redhead_sound_awareness(
            entities, self.tile_map, [], 0.1,
        )

        self.assertEqual(entity["sound_awareness"], {
            "accumulator": 0.0,
            "silence_timer": 0.0,
            "startle_triggered": False,
            "chase_triggered": False,
        })

    def test_inaudible_footstep_does_not_interrupt_silence(self):
        entity = self.redhead_on_tile(1, 20)
        entity["sound_awareness"].update({
            "accumulator": 0.5,
            "silence_timer": 9.5,
            "startle_triggered": True,
        })

        game.update_redhead_sound_awareness(
            {"brains": {1: entity}}, self.tile_map,
            [self.sound_event(tile_x=3)], 0.5,
        )

        self.assertEqual(entity["sound_awareness"]["accumulator"], 0.0)

    def test_gunshot_skips_startle_and_requests_chase(self):
        entity = self.redhead_on_tile(1, 12)
        entities = {"brains": {1: entity}}
        game.update_redhead_sound_awareness(
            entities, self.tile_map,
            [self.sound_event(event_type="gunshot")], 0.1,
        )

        self.assertIn("pending_player_sound_chase", entity)
        self.assertNotIn("pending_awareness_stimulus", entity)
        with mock.patch.object(
                game, "prepare_redhead_pursuit_path", return_value=True), \
                mock.patch.object(game, "alert_visible_redhead_allies") as alert:
            state = game.transition_entity_state(
                entity, "idle", self.player, self.tile_map, None,
                self.audio, 0.01, {"entities": entities},
            )

        self.assertEqual(state, "angry chase")
        alert.assert_not_called()

    def test_flee_retains_immediate_chase_until_retreat_finishes(self):
        entity = self.redhead_on_tile(1, 4)
        entity["current_state"] = "flee"
        game.update_redhead_sound_awareness(
            {"brains": {1: entity}}, self.tile_map,
            [self.sound_event(event_type="gunshot")], 0.1,
        )

        forced, _committed = game.consume_redhead_pending_sound_chase(
            entity, "flee", self.tile_map,
        )
        self.assertIsNone(forced)
        self.assertIn("pending_player_sound_chase", entity)
        with mock.patch.object(
                game, "prepare_redhead_pursuit_path", return_value=True):
            forced, committed = game.consume_redhead_pending_sound_chase(
                entity, "idle", self.tile_map,
            )

        self.assertEqual(forced, "angry chase")
        self.assertFalse(committed)

    def test_stagger_retains_immediate_chase_until_reaction_finishes(self):
        entity = self.redhead_on_tile(1, 4)
        entity["current_state"] = "stagger"
        game.update_redhead_sound_awareness(
            {"brains": {1: entity}}, self.tile_map,
            [self.sound_event(event_type="gunshot")], 0.1,
        )

        forced, _committed = game.consume_redhead_pending_sound_chase(
            entity, "stagger", self.tile_map,
        )

        self.assertIsNone(forced)
        self.assertIn("pending_player_sound_chase", entity)

    def test_footstep_cannot_downgrade_queued_gunshot_chase(self):
        entity = self.redhead_on_tile(1, 4)
        entity["hearing_settings"].update({
            "startle_threshold": 0.1,
            "chase_threshold": 0.2,
        })

        game.update_redhead_sound_awareness(
            {"brains": {1: entity}}, self.tile_map,
            [
                self.sound_event(event_type="gunshot"),
                self.sound_event(event_type="footstep"),
            ],
            0.1,
        )

        self.assertFalse(
            entity["pending_player_sound_chase"][
                "from_cumulative_startle"
            ],
        )


if __name__ == "__main__":
    unittest.main()
