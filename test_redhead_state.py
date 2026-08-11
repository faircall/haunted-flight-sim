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


class RedheadPerceptionCadenceTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(12, 4, 16, 16)
        self.entity = make_redhead(tile_x=1)
        self.player = make_player(tile_x=8)

    def test_perception_settings_are_fresh_and_clamped(self):
        other = make_redhead()
        self.entity["perception_settings"][
            "line_of_sight_checks_per_second"
        ] = 1000.0
        self.entity["perception_settings"]["flashlight_notice_duration"] = -2.0
        self.entity["perception_settings"]["flashlight_intensity_threshold"] = 99.0
        settings = game.get_redhead_perception_settings(self.entity)
        self.assertEqual(
            settings["line_of_sight_checks_per_second"], 60.0,
        )
        self.assertEqual(settings["flashlight_notice_duration"], 0.0)
        self.assertEqual(settings["flashlight_intensity_threshold"], 10.0)
        self.assertEqual(
            other["perception_settings"][
                "line_of_sight_checks_per_second"
            ],
            4.0,
        )
        self.assertEqual(
            other["perception_settings"]["flashlight_notice_duration"], 0.1,
        )

    def test_sixty_updates_issue_four_los_and_corridor_samples(self):
        visible = (True, self.player["position"])
        with mock.patch.object(
                game, "alice_can_see_bob_points", return_value=visible,
        ) as visibility, mock.patch.object(
                game, "alice_can_move_to_bob", return_value=True,
        ) as corridor:
            game.sample_redhead_player_perception(
                self.entity, self.player, self.tile_map, None, 0.0,
                include_direct_movement=True, force=True,
            )
            visibility.reset_mock()
            corridor.reset_mock()
            results = [
                game.sample_redhead_player_perception(
                    self.entity, self.player, self.tile_map, None, 1.0 / 60.0,
                    include_direct_movement=True,
                )
                for _frame in range(60)
            ]

        self.assertEqual(visibility.call_count, 4)
        self.assertEqual(corridor.call_count, 4)
        self.assertTrue(all(result[0] and result[2] for result in results))
        self.assertEqual(
            self.entity["perception_runtime"]["sample_count"], 5,
        )

    def test_cached_seen_position_is_an_independent_snapshot(self):
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"]),
        ) as visibility:
            _visible, seen_position, _direct = (
                game.sample_redhead_player_perception(
                    self.entity, self.player, self.tile_map, None, 0.01,
                )
            )
            self.player["position"]["tile_x"] = 9
            _visible, cached_position, _direct = (
                game.sample_redhead_player_perception(
                    self.entity, self.player, self.tile_map, None, 0.01,
                )
            )

        self.assertEqual(visibility.call_count, 1)
        self.assertEqual(seen_position["tile_x"], 8)
        self.assertEqual(cached_position["tile_x"], 8)

    def test_forced_and_geometry_changed_samples_bypass_fresh_cache(self):
        with mock.patch.object(
                game, "alice_can_see_bob_points", return_value=(False, None),
        ) as visibility:
            game.sample_redhead_player_perception(
                self.entity, self.player, self.tile_map, None, 0.01,
            )
            game.sample_redhead_player_perception(
                self.entity, self.player, self.tile_map, None, 0.01,
                force=True,
            )
            self.tile_map["geometry_revision"] += 1
            game.sample_redhead_player_perception(
                self.entity, self.player, self.tile_map, None, 0.01,
            )

        self.assertEqual(visibility.call_count, 3)

    def test_flashlight_exposure_turns_then_queues_generic_awareness(self):
        lighting_frame = {
            "prepared_by_id": {"runtime:player_flashlight": {"light": {}}},
            "collision_grid": {},
        }
        with mock.patch.object(
                game.g_graphics,
                "get_prepared_gameplay_light_strength_at_world_point",
                return_value=0.5,
        ):
            game.update_redhead_flashlight_awareness(
                {"brains": {7: self.entity}}, self.player, self.tile_map,
                lighting_frame, 0.06,
            )
            self.assertNotIn("pending_awareness_stimulus", self.entity)
            game.update_redhead_flashlight_awareness(
                {"brains": {7: self.entity}}, self.player, self.tile_map,
                lighting_frame, 0.05,
            )

        stimulus = self.entity["pending_awareness_stimulus"]
        self.assertEqual(stimulus["type"], "light")
        self.assertEqual(stimulus["strength"], 0.5)
        facing = game.vector_from_angle(self.entity["sight_angle"])
        self.assertGreater(facing["x"], 0.99)

        with mock.patch.object(
                game, "alice_can_see_bob_points", return_value=(False, None),
        ) as visibility:
            state = game.idle_redhead_state(
                self.entity, "idle", self.player, self.tile_map, None, 0.01,
            )
        self.assertEqual(state, "noticing")
        visibility.assert_not_called()
        self.assertEqual(self.entity["last_awareness_stimulus"]["type"], "light")

    def test_continuous_flashlight_exposure_latches_until_light_leaves(self):
        lighting_frame = {
            "prepared_by_id": {"runtime:player_flashlight": {"light": {}}},
            "collision_grid": {},
        }
        with mock.patch.object(
                game.g_graphics,
                "get_prepared_gameplay_light_strength_at_world_point",
                return_value=0.5,
        ):
            game.update_redhead_flashlight_awareness(
                {"brains": {7: self.entity}}, self.player, self.tile_map,
                lighting_frame, 0.11,
            )
            self.entity.pop("pending_awareness_stimulus")
            game.update_redhead_flashlight_awareness(
                {"brains": {7: self.entity}}, self.player, self.tile_map,
                lighting_frame, 1.0,
            )
        self.assertNotIn("pending_awareness_stimulus", self.entity)

        with mock.patch.object(
                game.g_graphics,
                "get_prepared_gameplay_light_strength_at_world_point",
                return_value=0.0,
        ):
            game.update_redhead_flashlight_awareness(
                {"brains": {7: self.entity}}, self.player, self.tile_map,
                lighting_frame, 0.01,
            )
        self.assertFalse(
            self.entity["awareness_runtime"]["flashlight_latched"],
        )

    def test_prepared_gameplay_light_uses_visibility_polygon_without_new_ray(self):
        prepared = {
            "light": {
                "type": "point", "position": {"x": 0.0, "y": 0.0},
                "radius": 100.0, "falloff": 1.0, "intensity": 1.0,
                "gameplay_intensity": 1.0, "enabled": True,
                "affects_ai": True,
            },
            "world_position": {"x": 0.0, "y": 0.0},
            "affects_ai": True,
            "casts_wall_shadows": True,
            "visibility_polygon": [
                {"x": -20.0, "y": -20.0},
                {"x": 20.0, "y": -20.0},
                {"x": 20.0, "y": 20.0},
                {"x": -20.0, "y": 20.0},
            ],
        }
        self.assertGreater(
            game.g_graphics.get_prepared_gameplay_light_strength_at_world_point(
                prepared, {"x": 10.0, "y": 0.0}, {},
            ),
            0.0,
        )
        self.assertEqual(
            game.g_graphics.get_prepared_gameplay_light_strength_at_world_point(
                prepared, {"x": 50.0, "y": 0.0}, {},
            ),
            0.0,
        )


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
        self.entity["evade_settings"]["search_radius_tiles"] = 0
        self.entity["evade_settings"]["top_candidate_count"] = 0
        self.entity["evade_settings"]["minimum_lateral_tiles"] = -1.0
        settings = game.get_redhead_evade_settings(self.entity)
        self.assertEqual(settings["chance"], 1.0)
        self.assertEqual(settings["duration_min"], 2.0)
        self.assertEqual(settings["duration_max"], 2.0)
        self.assertEqual(settings["search_radius_tiles"], 1)
        self.assertEqual(settings["top_candidate_count"], 1)
        self.assertEqual(settings["minimum_lateral_tiles"], 0.0)
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
                mock.patch.object(
                    game, "prepare_redhead_evade_navigation", return_value=True,
                ) as prepare_evade, \
                mock.patch.object(game.random, "random", return_value=0.0):
            self.assertEqual(game.angry_chase_state(
                self.entity, "angry chase", self.player, self.tile_map,
                None, self.audio, 0.01,
            ), "evade")
        prepare_evade.assert_called_once()

    def test_evade_entry_initialises_once_and_queues_positional_bark(self):
        self.entity.update({
            "current_state": "evade", "previous_state": "angry chase",
            "evade_side": -1.0,
            "navigation": {
                "intent": "evade", "preferred_side": -1.0,
                "path": [{"tile_x": 5, "tile_y": 2}],
            },
        })
        with mock.patch.object(game.random, "uniform", return_value=1.5), \
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

    def test_evade_navigation_selects_a_lateral_reachable_path(self):
        target = game.make_pos_abs(self.player["position"], 16, 16)
        with mock.patch.object(
                game.random, "choice", side_effect=lambda values: values[0]), \
                mock.patch.object(game, "a_star_path") as global_pathfinder:
            navigation = game.choose_redhead_evade_navigation(
                self.entity, self.player, target, self.tile_map,
                preferred_side=1.0,
            )

        self.assertIsNotNone(navigation)
        self.assertEqual(navigation["intent"], "evade")
        self.assertGreaterEqual(len(navigation["path"]), 2)
        self.assertEqual(navigation["path"][0], {"tile_x": 5, "tile_y": 2})
        self.assertGreaterEqual(
            navigation["score_components"]["lateral_tiles"],
            self.entity["evade_settings"]["minimum_lateral_tiles"],
        )
        self.assertLessEqual(
            -navigation["score_components"]["progress_tiles"],
            self.entity["evade_settings"]["maximum_retreat_tiles"],
        )
        global_pathfinder.assert_not_called()

    def test_tactical_reachability_rejects_walls_and_map_edge_footprints(self):
        wall = self.tile_map["tiles"][2 * 16 + 4]
        wall["index"] = 3

        reachability = game.build_redhead_tactical_reachability(
            self.entity, self.tile_map, 4,
        )

        self.assertNotIn((4, 2), reachability["cost"])
        self.assertFalse(any(
            tile_y in {0, 5} for _tile_x, tile_y in reachability["cost"]
        ))

    def test_candidate_cover_component_is_an_explicit_scoring_hook(self):
        target = game.make_pos_abs(self.player["position"], 16, 16)
        self.entity["evade_settings"]["cover_score_weight"] = 2.0
        with mock.patch.object(
                game, "redhead_evade_cover_score", return_value=0.0):
            uncovered = game.score_redhead_evade_candidate(
                self.entity, (4, 4), 2.0, self.player, target,
                self.tile_map, 1.0,
            )
        with mock.patch.object(
                game, "redhead_evade_cover_score", return_value=5.0):
            covered = game.score_redhead_evade_candidate(
                self.entity, (4, 4), 2.0, self.player, target,
                self.tile_map, 1.0,
            )

        self.assertEqual(covered["components"]["cover"], 5.0)
        self.assertAlmostEqual(covered["score"] - uncovered["score"], 10.0)

    def test_evade_waypoints_advance_without_touching_pursuit_path(self):
        pursuit_path = [{"tile_x": 5, "tile_y": 2}]
        self.entity["path_to_player"] = pursuit_path
        self.entity["navigation"] = {
            "intent": "evade",
            "path": [
                {"tile_x": 5, "tile_y": 2},
                {"tile_x": 4, "tile_y": 3},
                {"tile_x": 3, "tile_y": 4},
            ],
            "waypoint_index": 1,
        }

        waypoint, target = game.get_redhead_evade_waypoint(
            self.entity, self.tile_map,
        )
        self.assertEqual(waypoint, {"tile_x": 4, "tile_y": 3})
        self.assertEqual(target, {"x": 72.0, "y": 56.0})

        self.entity["position"] = {
            "tile_x": 4, "tile_y": 3, "x": 8.0, "y": 8.0,
        }
        waypoint, _ = game.get_redhead_evade_waypoint(
            self.entity, self.tile_map,
        )
        self.assertEqual(waypoint, {"tile_x": 3, "tile_y": 4})
        self.assertIs(self.entity["path_to_player"], pursuit_path)

    def test_evade_state_follows_planned_waypoint_not_lateral_steering(self):
        self.entity.update({
            "current_state": "evade", "previous_state": "evade",
            "evade_elapsed": 0.0, "evade_duration": 2.0,
            "navigation": {
                "intent": "evade",
                "path": [
                    {"tile_x": 5, "tile_y": 2},
                    {"tile_x": 4, "tile_y": 3},
                ],
                "waypoint_index": 1,
                "geometry_revision": 0,
                "preferred_side": 1.0,
            },
        })
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"])), \
                mock.patch.object(
                    game, "move_entity_towards_target_abs",
                    return_value=dict(self.entity["position"]),
                ) as move_to_waypoint, \
                mock.patch.object(game, "move_redhead_in_direction") as steering:
            state = game.evade_redhead_state(
                self.entity, "evade", self.player, self.tile_map, None, 0.1,
            )

        self.assertEqual(state, "evade")
        self.assertEqual(move_to_waypoint.call_args.args[1], {
            "x": 72.0, "y": 56.0,
        })
        self.assertEqual(
            move_to_waypoint.call_args.kwargs["arrival_radius"],
            self.entity["evade_settings"]["waypoint_arrival_radius"],
        )
        steering.assert_not_called()

    def test_failed_tactical_plan_keeps_chasing_and_sets_retry_delay(self):
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
                mock.patch.object(
                    game, "prepare_redhead_evade_navigation", return_value=False,
                ), \
                mock.patch.object(game.random, "random", return_value=0.0):
            state = game.angry_chase_state(
                self.entity, "angry chase", self.player, self.tile_map,
                None, self.audio, 0.01,
            )

        self.assertEqual(state, "angry chase")
        self.assertEqual(
            self.entity["evade_retry_timer"],
            self.entity["evade_settings"]["failed_retry_delay"],
        )

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
        })
        self.player["position"]["tile_x"] = 14
        self.player["aim_direction"] = {"x": -1.0, "y": 0.0}
        before = game.make_pos_abs(self.entity["position"], 16, 16)
        target = game.make_pos_abs(self.player["position"], 16, 16)
        before_distance = game.vec2_distance(before, target)
        with mock.patch.object(
                game, "alice_can_see_bob_points",
                return_value=(True, self.player["position"])), \
                mock.patch.object(
                    game.random, "choice", side_effect=lambda values: values[0],
                ):
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
            "navigation": {
                "intent": "evade", "preferred_side": 1.0,
                "path": [{"tile_x": 5, "tile_y": 2}],
            },
        })
        with mock.patch.object(game, "evade_redhead_state", return_value="evade"):
            game.transition_entity_state(
                self.entity, "evade", self.player, self.tile_map, None,
                self.audio, 0.1,
            )
        self.assertEqual(self.entity["evade_elapsed"], 0.7)
        self.assertEqual(self.audio["event_queue"], [])


class RedheadLocomotionTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(24, 8, 16, 16)
        self.entity = make_redhead(tile_x=8, tile_y=3)

    def test_movement_settings_are_fresh_and_have_slower_authored_defaults(self):
        other = make_redhead()
        self.entity["movement_settings"]["max_speed"] = 12.0

        self.assertEqual(
            other["movement_settings"]["max_speed"],
            game.REDHEAD_MOVEMENT_DEFAULTS["max_speed"],
        )
        self.assertEqual(game.REDHEAD_MOVEMENT_DEFAULTS["max_speed"], 70.0)
        self.assertEqual(game.REDHEAD_MOVEMENT_DEFAULTS["acceleration"], 140.0)

    def test_movement_settings_clamp_and_fall_back_from_invalid_values(self):
        self.entity["movement_settings"].update({
            "max_speed": -5.0,
            "acceleration": float("nan"),
            "deceleration": -2.0,
            "reverse_acceleration": None,
            "arrival_radius": -4.0,
            "evade_speed_multiplier": -1.0,
        })

        settings = game.get_redhead_movement_settings(self.entity)

        self.assertEqual(settings["max_speed"], 0.0)
        self.assertEqual(
            settings["acceleration"],
            game.REDHEAD_MOVEMENT_DEFAULTS["acceleration"],
        )
        self.assertEqual(settings["deceleration"], 0.0)
        self.assertEqual(
            settings["reverse_acceleration"],
            game.REDHEAD_MOVEMENT_DEFAULTS["reverse_acceleration"],
        )
        self.assertEqual(settings["arrival_radius"], 0.0)
        self.assertEqual(settings["evade_speed_multiplier"], 0.0)

    def test_legacy_top_level_fields_and_evade_multiplier_migrate(self):
        self.entity.pop("movement_settings")
        self.entity.update({
            "speed": 48.0,
            "acceleration": 90.0,
            "reverse_acceleration": 175.0,
            "arrival_radius": 6.0,
        })
        self.entity["evade_settings"]["speed_multiplier"] = 1.25

        settings = game.ensure_redhead_movement_settings(self.entity)

        self.assertEqual(settings["max_speed"], 48.0)
        self.assertEqual(settings["acceleration"], 90.0)
        self.assertEqual(settings["reverse_acceleration"], 175.0)
        self.assertEqual(settings["arrival_radius"], 6.0)
        self.assertEqual(settings["evade_speed_multiplier"], 1.25)
        self.assertIs(self.entity["movement_settings"], settings)

    def test_accelerates_instead_of_reaching_maximum_speed_immediately(self):
        before = game.make_pos_abs(self.entity["position"], 16, 16)

        self.entity["position"] = game.move_redhead_in_direction(
            self.entity, {"x": 1.0, "y": 0.0},
            self.tile_map, None, 0.1,
        )

        after = game.make_pos_abs(self.entity["position"], 16, 16)
        self.assertAlmostEqual(self.entity["ai_velocity"]["x"], 14.0)
        self.assertAlmostEqual(self.entity["ai_velocity"]["y"], 0.0)
        self.assertAlmostEqual(after["x"] - before["x"], 1.4)
        self.assertLess(
            self.entity["current_speed"],
            self.entity["movement_settings"]["max_speed"],
        )

    def test_deceleration_and_reverse_acceleration_use_distinct_limits(self):
        self.entity["ai_velocity"] = {"x": 70.0, "y": 0.0}
        game.move_redhead_with_locomotion(
            self.entity, {"x": 0.0, "y": 0.0},
            self.tile_map, None, 0.1,
        )
        self.assertAlmostEqual(self.entity["ai_velocity"]["x"], 48.0)

        self.entity["ai_velocity"] = {"x": 70.0, "y": 0.0}
        game.move_redhead_with_locomotion(
            self.entity, {"x": -1.0, "y": 0.0},
            self.tile_map, None, 0.1,
        )
        self.assertAlmostEqual(self.entity["ai_velocity"]["x"], 42.0)

    def test_target_adapter_uses_braking_distance_near_arrival_radius(self):
        origin = game.make_pos_abs(self.entity["position"], 16, 16)
        target = {"x": origin["x"] + 4.0, "y": origin["y"]}

        with mock.patch.object(
                game, "move_redhead_with_locomotion",
                return_value=dict(self.entity["position"])) as move:
            game.move_entity_towards_target_abs(
                self.entity, target, self.tile_map, None, 0.1,
                arrival_radius=3.0,
            )

        self.assertAlmostEqual(
            move.call_args.kwargs["desired_speed"],
            (2.0 * 220.0 * 1.0) ** 0.5,
        )
        self.assertEqual(move.call_args.args[1], {"x": 1.0, "y": 0.0})

    def test_chase_and_evade_adapters_share_persistent_velocity(self):
        target = {"x": 300.0, "y": 56.0}
        first_position = game.move_entity_towards_target_abs(
            self.entity, target, self.tile_map, None, 0.1,
        )
        first_speed = game.vec2_norm(self.entity["ai_velocity"])
        self.entity["position"] = first_position

        self.entity["position"] = game.move_redhead_in_direction(
            self.entity, {"x": 1.0, "y": 0.0},
            self.tile_map, None, 0.1,
        )

        self.assertAlmostEqual(first_speed, 14.0)
        self.assertAlmostEqual(game.vec2_norm(self.entity["ai_velocity"]), 28.0)


if __name__ == "__main__":
    unittest.main()
