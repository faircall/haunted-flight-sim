import unittest
from unittest import mock

import g_audio
import g_update_and_render as game
from test_redhead_state import make_player, make_redhead


class RedheadBehaviorImprovementTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(20, 10, 16, 16)
        self.player = make_player(12, 5)
        self.player["id"] = "player"
        self.redhead = make_redhead(8, 5)
        self.redhead["id"] = 1
        self.audio = g_audio.make_audio_runtime()

    def test_light_uses_short_startle_then_commits_to_chase(self):
        self.redhead["pending_awareness_stimulus"] = {
            "type": "light",
            "source_world_position": {"x": 200.0, "y": 88.0},
            "strength": 0.5,
        }
        state = game.idle_redhead_state(
            self.redhead, "idle", self.player, self.tile_map, None, 0.01,
        )
        self.assertEqual(state, "light startle")
        self.assertEqual(
            self.redhead["last_seen_player_pos"]["tile_x"],
            self.player["position"]["tile_x"],
        )

        self.redhead["current_state"] = state
        self.redhead["previous_state"] = "idle"
        with mock.patch.object(
                game, "prepare_redhead_pursuit_path", return_value=True):
            state = game.transition_entity_state(
                self.redhead, state, self.player, self.tile_map, None,
                self.audio, 0.10,
            )
        self.assertEqual(state, "angry chase")

    def test_shot_refreshes_player_memory_and_idle_stagger_resumes_chase(self):
        bullet = {"velocity": {"x": 100.0, "y": 0.0}}
        game.apply_bullet_hit_to_redhead(
            self.redhead, 1, bullet, "idle", self.tile_map, self.audio,
            player_info=self.player,
        )
        self.assertEqual(
            self.redhead["last_seen_player_pos"]["tile_x"],
            self.player["position"]["tile_x"],
        )
        with mock.patch.object(
                game, "prepare_redhead_pursuit_path", return_value=True):
            state = game.stagger_state(
                self.redhead, "stagger", self.player, self.tile_map, None, 0.10,
            )
        self.assertEqual(state, "angry chase")

    def test_low_health_stagger_transitions_to_flee(self):
        ally = make_redhead(5, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}
        self.redhead["health"] = 40
        game.apply_bullet_hit_to_redhead(
            self.redhead, 1, {"velocity": {"x": 0.0, "y": 0.0}},
            "angry chase", self.tile_map, self.audio,
            player_info=self.player,
        )
        state = game.stagger_state(
            self.redhead, "stagger", self.player, self.tile_map, None, 0.10,
            {"entities": entities},
        )
        self.assertEqual(state, "flee")

    def test_low_health_redhead_alone_resumes_fighting(self):
        self.redhead["health"] = 20
        self.redhead.update({
            "stagger_timer": 0.0,
            "bullet_hit_magnitude": 0.0,
            "bullet_normalized": {"x": 0.0, "y": 0.0},
            "bullet_impulse": {"x": 0.0, "y": 0.0},
            "previous_state_on_stagger": "angry chase",
        })
        entities = {"brains": {1: self.redhead}}

        state = game.stagger_state(
            self.redhead, "stagger", self.player, self.tile_map, None, 0.10,
            {"entities": entities},
        )

        self.assertEqual(state, "angry chase")

    def test_dead_or_distant_redheads_do_not_enable_flee(self):
        self.redhead["health"] = 20
        self.redhead["flee_settings"]["ally_search_radius_tiles"] = 4
        dead_ally = make_redhead(7, 5)
        dead_ally.update({"id": 2, "health": 0, "current_state": "dead"})
        distant_ally = make_redhead(15, 5)
        distant_ally["id"] = 3

        self.assertFalse(game.redhead_should_flee(
            self.redhead,
            {"brains": {1: self.redhead, 2: dead_ally, 3: distant_ally}},
            self.tile_map,
        ))

    def test_flee_without_a_nearby_living_ally_returns_to_chase(self):
        self.redhead["current_state"] = "flee"
        state = game.flee_redhead_state(
            self.redhead, "flee", self.player, self.tile_map, None,
            1.0 / 60.0,
            {"entities": {"brains": {1: self.redhead}}},
        )
        self.assertEqual(state, "angry chase")

    def test_flee_arrival_returns_to_idle_with_gate_spent(self):
        ally = make_redhead(9, 5)
        ally["id"] = 2
        self.redhead.update({
            "current_state": "flee",
            "ai_velocity": {"x": -70.0, "y": 0.0},
            "navigation": {
                "intent": "flee",
                "target_ally_id": 2,
                "path": [
                    {"tile_x": 8, "tile_y": 5},
                    {"tile_x": 9, "tile_y": 5},
                ],
                "waypoint_index": 1,
                "geometry_revision": self.tile_map["geometry_revision"],
                "replan_timer": 0.0,
            },
        })
        context = {"entities": {"brains": {1: self.redhead, 2: ally}}}

        with mock.patch.object(game, "choose_redhead_flee_navigation") as plan:
            state = game.flee_redhead_state(
                self.redhead, "flee", self.player, self.tile_map, None,
                1.0 / 60.0, context,
            )

        self.assertEqual(state, "idle")
        self.assertTrue(self.redhead["has_fled"])
        self.assertEqual(self.redhead["ai_velocity"], {"x": 0.0, "y": 0.0})
        self.assertNotIn("navigation", self.redhead)
        plan.assert_not_called()

    def test_completed_flee_can_notice_player_but_never_flees_again(self):
        ally = make_redhead(9, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}
        self.redhead.update({
            "current_state": "flee",
            "health": 20,
            "ai_velocity": {"x": 0.0, "y": 0.0},
        })
        state = game.flee_redhead_state(
            self.redhead, "flee", self.player, self.tile_map, None,
            1.0 / 60.0, {"entities": entities},
        )
        self.assertEqual(state, "idle")

        self.redhead["current_state"] = "idle"
        self.redhead["previous_state"] = "flee"
        with mock.patch.object(
                game, "sample_redhead_player_perception",
                return_value=(True, self.player["position"], False)):
            state = game.transition_entity_state(
                self.redhead, "idle", self.player, self.tile_map, None,
                self.audio, 0.01, {"entities": entities},
            )
        self.assertEqual(state, "noticing")
        self.assertFalse(game.redhead_should_flee(
            self.redhead, entities, self.tile_map,
        ))

        self.redhead.update({
            "current_state": "stagger",
            "previous_state_on_stagger": "angry chase",
            "stagger_timer": 0.0,
            "bullet_impulse": {"x": 0.0, "y": 0.0},
        })
        state = game.stagger_state(
            self.redhead, "stagger", self.player, self.tile_map, None, 0.10,
            {"entities": entities},
        )
        self.assertEqual(state, "angry chase")

    def test_exhausted_flee_path_waits_instead_of_rejoining_chase(self):
        ally = make_redhead(4, 5)
        ally["id"] = 2
        self.redhead.update({
            "current_state": "flee",
            "ai_velocity": {"x": -70.0, "y": 0.0},
            "navigation": {
                "intent": "flee",
                "target_ally_id": 2,
                "path": [{"tile_x": 8, "tile_y": 5}],
                "waypoint_index": 1,
                "geometry_revision": self.tile_map["geometry_revision"],
                "replan_timer": 0.0,
            },
        })
        context = {"entities": {"brains": {1: self.redhead, 2: ally}}}

        state = game.flee_redhead_state(
            self.redhead, "flee", self.player, self.tile_map, None,
            1.0 / 60.0, context,
        )

        self.assertEqual(state, "flee")
        self.assertEqual(self.redhead["ai_velocity"], {"x": 0.0, "y": 0.0})
        self.assertNotIn("navigation", self.redhead)

    def test_flee_plan_targets_a_living_redhead_and_is_locally_bounded(self):
        ally = make_redhead(3, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}
        navigation = game.choose_redhead_flee_navigation(
            self.redhead, self.player, self.tile_map, entities,
        )
        self.assertIsNotNone(navigation)
        self.assertEqual(navigation["target_ally_id"], 2)
        self.assertLessEqual(
            len(navigation["path"]),
            self.redhead["flee_settings"]["local_plan_radius_tiles"] + 1,
        )

    def test_flee_planning_budget_defers_a_second_same_frame_search(self):
        ally = make_redhead(5, 5)
        ally["id"] = 2
        context = {
            "entities": {"brains": {1: self.redhead, 2: ally}},
            "flee_plans_remaining": 0,
        }
        with mock.patch.object(game, "choose_redhead_flee_navigation") as plan:
            state = game.flee_redhead_state(
                self.redhead, "flee", self.player, self.tile_map, None,
                1.0 / 60.0, context,
            )
        self.assertEqual(state, "flee")
        plan.assert_not_called()

    def test_failed_flee_plan_waits_before_retrying(self):
        ally = make_redhead(4, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}

        with mock.patch.object(
                game, "choose_redhead_flee_navigation", return_value=None) as plan:
            first_state = game.flee_redhead_state(
                self.redhead, "flee", self.player, self.tile_map, None,
                1.0 / 60.0, {"entities": entities},
            )
            second_state = game.flee_redhead_state(
                self.redhead, "flee", self.player, self.tile_map, None,
                1.0 / 60.0, {"entities": entities},
            )

        self.assertEqual((first_state, second_state), ("flee", "flee"))
        self.assertEqual(plan.call_count, 1)
        self.assertGreater(self.redhead["flee_plan_retry_timer"], 0.0)

    def test_ally_alert_waits_until_startle_commits_to_chase(self):
        ally = make_redhead(10, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}
        self.redhead.update({
            "current_state": "idle",
            "previous_state": "idle",
        })
        with mock.patch.object(
                game, "sample_redhead_player_perception",
                return_value=(True, self.player["position"], False)), \
                mock.patch.object(
                    game, "prepare_redhead_pursuit_path", return_value=True,
                ), \
                mock.patch.object(
                    game, "alice_can_raycast_to_bob", return_value=True,
                ) as ally_visibility:
            state = game.transition_entity_state(
                self.redhead, "idle", self.player, self.tile_map, None,
                self.audio, 0.01, {"entities": entities},
            )
            self.assertEqual(state, "noticing")
            self.assertNotIn("pending_awareness_stimulus", ally)
            ally_visibility.assert_not_called()

            self.redhead["current_state"] = "noticing"
            state = game.transition_entity_state(
                self.redhead, "noticing", self.player, self.tile_map, None,
                self.audio, 1.0, {"entities": entities},
            )

        self.assertEqual(state, "angry chase")
        self.assertEqual(
            ally["pending_awareness_stimulus"]["type"], "ally_alert",
        )
        ally_visibility.assert_called_once()

    def test_aborted_startle_does_not_alert_neighbours(self):
        ally = make_redhead(10, 5)
        ally["id"] = 2
        entities = {"brains": {1: self.redhead, 2: ally}}
        self.redhead.update({
            "current_state": "noticing",
            "previous_state": "idle",
        })
        with mock.patch.object(
                game, "sample_redhead_player_perception",
                return_value=(False, None, False)), \
                mock.patch.object(game, "alert_visible_redhead_allies") as alert:
            state = game.transition_entity_state(
                self.redhead, "noticing", self.player, self.tile_map, None,
                self.audio, 1.0, {"entities": entities},
            )

        self.assertEqual(state, "idle")
        self.assertNotIn("pending_awareness_stimulus", ally)
        alert.assert_not_called()

    def test_ally_alert_does_not_pass_through_walls(self):
        ally = make_redhead(10, 5)
        ally["id"] = 2
        # Collision centres lie in tiles 7 and 9; block the tile between.
        self.tile_map["tiles"][8 + 5 * 20]["index"] = 3

        alerted = game.alert_visible_redhead_allies(
            self.redhead, {"brains": {1: self.redhead, 2: ally}},
            self.tile_map,
        )

        self.assertEqual(alerted, 0)
        self.assertNotIn("pending_awareness_stimulus", ally)


if __name__ == "__main__":
    unittest.main()
