import unittest
from unittest import mock

import g_audio
import g_effects
import g_update_and_render as game


def make_redhead(entity_id=1, tile_x=4, tile_y=4, x=8.0, y=8.0):
    entity = {
        "id": entity_id,
        "type": "red head",
        "position": {
            "tile_x": tile_x, "tile_y": tile_y,
            "x": x, "y": y,
        },
        "entity_width": 16,
        "entity_height": 16,
        "current_state": "idle",
        "previous_state": "idle",
    }
    game.give_entity_stats_from_type(entity, "red head")
    return entity


def make_player():
    player = game.make_default_player(8, 8, 0)
    player["position"].update({"tile_x": 1, "tile_y": 1})
    return player


class SweptSegmentTests(unittest.TestCase):
    def test_cardinal_and_diagonal_segments_hit_exact_box(self):
        rectangle = {"x": 40.0, "y": 40.0, "width": 20.0, "height": 20.0}
        self.assertAlmostEqual(game.segment_aabb_intersection_fraction(
            {"x": 0.0, "y": 50.0}, {"x": 100.0, "y": 50.0}, rectangle,
        ), 0.4)
        self.assertAlmostEqual(game.segment_aabb_intersection_fraction(
            {"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 100.0}, rectangle,
        ), 0.4)
        self.assertIsNone(game.segment_aabb_intersection_fraction(
            {"x": 0.0, "y": 20.0}, {"x": 100.0, "y": 20.0}, rectangle,
        ))

    def test_segment_starting_inside_hurtbox_hits_immediately(self):
        fraction = game.segment_aabb_intersection_fraction(
            {"x": 50.0, "y": 50.0}, {"x": 100.0, "y": 100.0},
            {"x": 40.0, "y": 40.0, "width": 20.0, "height": 20.0},
        )
        self.assertEqual(fraction, 0.0)

    def test_redhead_hurtbox_tracks_visible_body_across_tile_boundaries(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        entity = make_redhead(tile_x=4, tile_y=4, x=2.0, y=2.0)
        hurtbox = game.get_redhead_bullet_hurtbox(entity, tile_map)
        self.assertEqual(hurtbox, {
            "x": 48.0, "y": 47.0, "width": 12.0, "height": 17.0,
        })
        # This diagonal crosses the visible body without entering anchor tile 4,4.
        hit = game.find_first_redhead_bullet_hit(
            {"x": 20.0, "y": 80.0}, {"x": 80.0, "y": 20.0},
            {entity["id"]: entity}, tile_map,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit["entity_id"], entity["id"])

    def test_legacy_copied_hurtbox_does_not_pin_old_dimensions(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        entity = make_redhead(tile_x=4, tile_y=4, x=2.0, y=2.0)
        entity["bullet_hurtbox"] = {
            "offset": {"x": -20.0, "y": -22.0},
            "size": {"x": 16.0, "y": 22.0},
        }

        self.assertEqual(game.get_redhead_bullet_hurtbox(entity, tile_map), {
            "x": 48.0, "y": 47.0, "width": 12.0, "height": 17.0,
        })
        self.assertNotIn("bullet_hurtbox", entity)

    def test_headshot_box_is_inset_inside_projectile_hurtbox(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        entity = make_redhead(tile_x=4, tile_y=4, x=2.0, y=2.0)

        self.assertEqual(game.get_redhead_headshot_box(entity, tile_map), {
            "x": 49.0, "y": 49.0, "width": 10.0, "height": 6.0,
        })
        debug_item = game.make_redhead_headshot_debug_item(entity, tile_map)
        self.assertEqual(debug_item["color"], "RED")
        self.assertIn("dumb entities", debug_item["debug_modes"])

    def test_redhead_collision_debug_item_uses_movement_box_in_player_view(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        entity = make_redhead(tile_x=4, tile_y=4, x=2.0, y=2.0)
        item = game.make_redhead_collision_debug_item(entity, tile_map)
        self.assertEqual(
            {key: item[key] for key in ("x", "y", "width", "height")},
            game.get_redhead_collision_box(entity, tile_map),
        )
        self.assertEqual(game.get_redhead_collision_box(entity, tile_map), {
            "x": 50.0, "y": 54.0, "width": 8.0, "height": 8.0,
        })
        self.assertIs(item["drawing_function"], game.draw_debug_rect_outline)
        self.assertIn("player_debug", item["debug_modes"])
        self.assertIn("dumb entities", item["debug_modes"])

    def test_redhead_bullet_hurtbox_remains_in_collision_debug_view(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        entity = make_redhead(tile_x=4, tile_y=4, x=2.0, y=2.0)
        item = game.make_redhead_hurtbox_debug_item(entity, tile_map)
        self.assertIn("collisions", item["debug_modes"])
        self.assertIn("dumb entities", item["debug_modes"])
        self.assertNotIn("player_debug", item["debug_modes"])

    def test_actor_aabb_collision_slides_along_redhead_edge(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        player = game.make_default_player(2.0, 2.0, 0.0)
        player["position"].update({"tile_x": 3, "tile_y": 3})
        redhead = make_redhead(tile_x=4, tile_y=4, x=8.0, y=4.0)
        entities = {"brains": {redhead["id"]: redhead}}
        game.rebuild_actor_collision_index(tile_map, player, entities)

        velocity = {"x": 10.0, "y": 10.0}
        result = game.move_entity_with_velocity(
            player, velocity, tile_map, None, 0.1,
        )
        world = game.make_pos_abs(result, 16, 16)

        # The diagonal is blocked, but X remains tangent to the top edge.
        self.assertAlmostEqual(world["x"], 51.0)
        self.assertAlmostEqual(world["y"], 50.0)
        self.assertEqual(velocity, {"x": 10.0, "y": 0})

    def test_collision_index_carries_each_actors_real_aabb(self):
        tile_map = game.make_tile_map(10, 10, 16, 16)
        player = game.make_default_player(8.0, 8.0, 0.0)
        player["position"].update({"tile_x": 2, "tile_y": 2})
        redhead = make_redhead(tile_x=4, tile_y=4, x=8.0, y=8.0)
        game.rebuild_actor_collision_index(
            tile_map, player, {"brains": {redhead["id"]: redhead}},
        )
        records = [
            record
            for tile in tile_map["tiles"]
            for record in tile.get("current_entities", {}).values()
        ]
        boxes = {record["entity_type"]: record["collision_box"] for record in records}
        self.assertEqual((boxes["player"]["width"], boxes["player"]["height"]), (12.0, 12.0))
        self.assertEqual((boxes["red head"]["width"], boxes["red head"]["height"]), (8.0, 8.0))

    def test_nearest_redhead_wins_and_wall_fraction_limits_candidates(self):
        tile_map = game.make_tile_map(12, 6, 16, 16)
        near = make_redhead(1, tile_x=3, tile_y=3, x=8.0, y=8.0)
        far = make_redhead(2, tile_x=6, tile_y=3, x=8.0, y=8.0)
        start, end = {"x": 0.0, "y": 50.0}, {"x": 140.0, "y": 50.0}
        hit = game.find_first_redhead_bullet_hit(
            start, end, {1: near, 2: far}, tile_map,
        )
        self.assertEqual(hit["entity_id"], 1)
        self.assertIsNone(game.find_first_redhead_bullet_hit(
            start, end, {2: far}, tile_map, maximum_fraction=0.4,
        ))

    def test_wall_trace_reports_first_physical_tile(self):
        tile_map = game.make_tile_map(8, 5, 16, 16)
        tile_map["tiles"][3 + 2 * 8]["index"] = 3
        hit = game.first_solid_tile_hit_on_segment(
            {"x": 0.0, "y": 40.0}, {"x": 100.0, "y": 40.0}, tile_map,
        )
        self.assertIsNotNone(hit)
        self.assertEqual((hit["tile_x"], hit["tile_y"]), (3, 2))
        self.assertAlmostEqual(hit["position"]["x"], 48.0)

    def test_projectile_ids_do_not_overwrite_sparse_live_ids(self):
        self.assertEqual(game.allocate_projectile_id({0: {}, 2: {}}), 3)

    def test_absolute_position_uses_independent_tile_dimensions(self):
        self.assertEqual(game.tile_and_offset_to_absolute(
            {"tile_width": 16, "tile_height": 24},
            {"tile_x": 2, "tile_y": 3, "x": 1, "y": 2},
        ), {"x": 33, "y": 74})


class ActorPassthroughTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(12, 8, 16, 16)

    def set_collision_center(self, entity, center_x, center_y):
        offset = game.get_entity_collision_center_offset(entity)
        entity["position"] = game.move_position_along_tiles({
            "tile_x": 0,
            "tile_y": 0,
            "x": center_x - offset["x"],
            "y": center_y - offset["y"],
        }, 16, 16)

    def collision_center(self, entity):
        return game.get_entity_collision_world_position(entity, self.tile_map)

    def test_sustained_redhead_block_enables_only_that_pair(self):
        mover = make_redhead(1)
        blocker = make_redhead(2)
        third = make_redhead(3)
        self.set_collision_center(mover, 64.0, 64.0)
        self.set_collision_center(blocker, 72.0, 64.0)
        self.set_collision_center(third, 56.0, 64.0)
        entities = {"brains": {1: mover, 2: blocker, 3: third}}
        game.rebuild_actor_collision_index(self.tile_map, None, entities)

        for _frame in range(3):
            velocity = {"x": 70.0, "y": 0.0}
            mover["position"] = game.move_entity_with_velocity(
                mover, velocity, self.tile_map, None, 0.10,
            )
        self.assertFalse(game.actor_passthrough_pair_is_active(
            self.tile_map, mover["id"], blocker["id"],
        ))
        velocity = {"x": 70.0, "y": 0.0}
        mover["position"] = game.move_entity_with_velocity(
            mover, velocity, self.tile_map, None, 0.10,
        )

        self.assertTrue(game.actor_passthrough_pair_is_active(
            self.tile_map, mover["id"], blocker["id"],
        ))
        right_candidate = game.move_position_by_velocity(
            mover["position"], {"x": 1.0, "y": 0.0}, 1.0, 16, 16,
        )
        left_candidate = game.move_position_by_velocity(
            mover["position"], {"x": -1.0, "y": 0.0}, 1.0, 16, 16,
        )
        self.assertTrue(game.entity_position_is_legal(
            right_candidate, mover, self.tile_map,
        ))
        self.assertFalse(game.entity_position_is_legal(
            left_candidate, mover, self.tile_map,
        ))
        self.assertFalse(game.actor_passthrough_pair_is_active(
            self.tile_map, mover["id"], third["id"],
        ))

    def test_passthrough_clears_after_redheads_cross(self):
        mover = make_redhead(1)
        blocker = make_redhead(2)
        self.set_collision_center(mover, 64.0, 64.0)
        self.set_collision_center(blocker, 72.0, 64.0)
        entities = {"brains": {1: mover, 2: blocker}}
        game.rebuild_actor_collision_index(self.tile_map, None, entities)

        for _frame in range(4):
            velocity = {"x": 70.0, "y": 0.0}
            mover["position"] = game.move_entity_with_velocity(
                mover, velocity, self.tile_map, None, 0.10,
            )
        for _frame in range(3):
            velocity = {"x": 70.0, "y": 0.0}
            mover["position"] = game.move_entity_with_velocity(
                mover, velocity, self.tile_map, None, 0.10,
            )

        self.assertGreater(
            self.collision_center(mover)["x"],
            self.collision_center(blocker)["x"],
        )
        self.assertFalse(game.actor_passthrough_pair_is_active(
            self.tile_map, mover["id"], blocker["id"],
        ))
        crossed_x = self.collision_center(mover)["x"]
        reverse_velocity = {"x": -70.0, "y": 0.0}
        mover["position"] = game.move_entity_with_velocity(
            mover, reverse_velocity, self.tile_map, None, 0.10,
        )
        self.assertAlmostEqual(self.collision_center(mover)["x"], crossed_x)

    def test_redhead_never_earns_passthrough_through_player(self):
        mover = make_redhead(1)
        player = game.make_default_player(0.0, 0.0, 0.0)
        player["id"] = "player"
        self.set_collision_center(mover, 64.0, 64.0)
        self.set_collision_center(player, 74.0, 64.0)
        game.rebuild_actor_collision_index(
            self.tile_map, player, {"brains": {1: mover}},
        )

        for _frame in range(6):
            velocity = {"x": 70.0, "y": 0.0}
            mover["position"] = game.move_entity_with_velocity(
                mover, velocity, self.tile_map, None, 0.10,
            )

        self.assertAlmostEqual(self.collision_center(mover)["x"], 64.0)
        self.assertFalse(game.actor_passthrough_pair_is_active(
            self.tile_map, mover["id"], player["id"],
        ))


class BulletUpdateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(12, 8, 16, 16)
        self.redhead = make_redhead(tile_x=4, tile_y=4)
        self.audio = g_audio.make_audio_runtime()
        self.entities = {
            "brains": {self.redhead["id"]: self.redhead},
            "pickups": {},
            "projectiles": {},
        }

    def update(self, effects_runtime=None):
        with mock.patch.object(
                game, "transition_entity_state",
                side_effect=lambda entity, state, *args: state), \
                mock.patch.object(g_audio, "update_actor_footstep_travel"):
            game.update_entities(
                self.entities, self.tile_map, make_player(), "play", "regular",
                0.01, self.audio, g_audio.make_audio_profile(),
                effects_runtime=effects_runtime,
            )

    def test_diagonal_cross_tile_shot_damages_redhead_once(self):
        bullet = game.make_projectile(
            "player", {"x": 20.0, "y": 100.0},
            {"x": 8000.0, "y": -8000.0}, 0, "bullet",
        )
        self.entities["projectiles"][0] = bullet
        self.update()
        self.assertEqual(self.redhead["health"], 40)
        self.assertEqual(self.redhead["current_state"], "stagger")
        self.assertEqual(self.entities["projectiles"], {})

    def test_wall_before_redhead_blocks_damage(self):
        self.tile_map["tiles"][3 + 3 * 12]["index"] = 3
        bullet = game.make_projectile(
            "player", {"x": 0.0, "y": 60.0},
            {"x": 10000.0, "y": 0.0}, 0, "bullet",
        )
        self.entities["projectiles"][0] = bullet
        self.update()
        self.assertEqual(self.redhead["health"], 60)
        self.assertEqual(self.entities["projectiles"], {})
        self.assertEqual(
            [event["type"] for event in self.audio["event_queue"]],
            ["bullet_wall_impact"],
        )

    def test_wall_hit_spawns_gpu_debris_at_confirmed_impact(self):
        self.tile_map["tiles"][3 + 3 * 12]["index"] = 3
        bullet = game.make_projectile(
            "player", {"x": 0.0, "y": 60.0},
            {"x": 10000.0, "y": 0.0}, 0, "bullet",
        )
        self.entities["projectiles"][0] = bullet
        effects_runtime = g_effects.make_effects_runtime()

        self.update(effects_runtime)

        self.assertEqual(effects_runtime["bursts"], {})
        emitters = g_effects.collect_transient_effect_emitters(effects_runtime)
        self.assertEqual(len(emitters), 1)
        debris = next(iter(emitters.values()))
        self.assertEqual(debris["runtime_kind"], "wall_debris")
        self.assertAlmostEqual(debris["direction"]["x"], -1.0)
        self.assertAlmostEqual(debris["direction"]["y"], 0.0)

    def test_dumb_entities_freezes_ai_but_keeps_bullet_damage(self):
        original_position = dict(self.redhead["position"])
        self.redhead["ai_velocity"] = {"x": 50.0, "y": -20.0}
        bullet = game.make_projectile(
            "player", {"x": 20.0, "y": 100.0},
            {"x": 8000.0, "y": -8000.0}, 0, "bullet",
        )
        self.entities["projectiles"][0] = bullet

        with mock.patch.object(game, "transition_entity_state") as transition, \
                mock.patch.object(
                    g_audio, "update_actor_footstep_travel",
                ) as footsteps:
            game.update_entities(
                self.entities, self.tile_map, make_player(),
                "play", "regular", 0.01, self.audio,
                g_audio.make_audio_profile(), debug_state="dumb entities",
            )

        transition.assert_not_called()
        footsteps.assert_not_called()
        self.assertEqual(self.redhead["position"], original_position)
        self.assertEqual(self.redhead["health"], 40)
        self.assertEqual(self.redhead["current_state"], "idle")
        self.assertEqual(self.redhead["ai_velocity"], {"x": 0.0, "y": 0.0})
        self.assertEqual(self.redhead["bullet_impulse"], {"x": 0.0, "y": 0.0})
        self.assertEqual(self.entities["projectiles"], {})

    def test_dumb_entities_is_in_debug_mode_cycle(self):
        self.assertEqual(
            game.transition_debug_state("slow_bullets"), "dumb entities",
        )
        self.assertEqual(game.transition_debug_state("dumb entities"), "clear")


class BulletImpulseTests(unittest.TestCase):
    def setUp(self):
        self.tile_map = game.make_tile_map(20, 10, 16, 16)
        self.audio = g_audio.make_audio_runtime()

    def redhead_at_collision_tile(self, tile_x=6, tile_y=5):
        entity = make_redhead(tile_x=tile_x, tile_y=tile_y)
        entity["position"] = game.entity_position_for_collision_tile_center(
            entity, tile_x, tile_y, self.tile_map,
        )
        return entity

    def bullet(self, velocity, **impact_overrides):
        return game.make_projectile(
            "player", {"x": 0.0, "y": 0.0}, velocity, 1, "bullet",
            **impact_overrides,
        )

    def world_position(self, entity):
        return game.make_pos_abs(entity["position"], 16, 16)

    def apply_hit(self, entity, bullet, state_before="angry chase", impact_dt=0.0):
        game.apply_bullet_hit_to_redhead(
            entity, entity["id"], bullet, state_before, self.tile_map,
            self.audio, impact_dt=impact_dt,
        )

    def test_impact_strength_is_independent_from_projectile_travel_speed(self):
        slow = self.redhead_at_collision_tile(5, 4)
        fast = self.redhead_at_collision_tile(10, 4)

        self.apply_hit(slow, self.bullet({"x": 100.0, "y": 0.0}))
        self.apply_hit(fast, self.bullet({"x": 10000.0, "y": 0.0}))

        self.assertAlmostEqual(
            game.vec2_norm(slow["bullet_impulse"]),
            game.DEFAULT_BULLET_IMPACT_SPEED,
        )
        self.assertAlmostEqual(
            game.vec2_norm(fast["bullet_impulse"]),
            game.DEFAULT_BULLET_IMPACT_SPEED,
        )

    def test_qualified_headshot_doubles_damage_only_for_its_target(self):
        headshot_target = self.redhead_at_collision_tile(5, 4)
        other_target = self.redhead_at_collision_tile(10, 4)
        other_target["id"] = 2
        bullet = self.bullet({"x": 1000.0, "y": 0.0})
        bullet.update({
            "headshot_target_id": headshot_target["id"],
            "headshot_damage_multiplier": 2.0,
        })

        self.apply_hit(headshot_target, bullet)
        self.apply_hit(other_target, bullet)

        self.assertEqual(headshot_target["health"], 20.0)
        self.assertTrue(headshot_target["last_hit_was_headshot"])
        self.assertEqual(headshot_target["last_damage_received"], 40.0)
        self.assertEqual(other_target["health"], 40.0)
        self.assertFalse(other_target["last_hit_was_headshot"])

    def test_impulse_is_immediate_and_clamped_to_zero(self):
        entity = self.redhead_at_collision_tile()
        entity["ai_velocity"] = {"x": -500.0, "y": 20.0}
        start_x = self.world_position(entity)["x"]

        self.apply_hit(
            entity, self.bullet({"x": 10000.0, "y": 0.0}), impact_dt=0.05,
        )
        immediate_x = self.world_position(entity)["x"]
        game.advance_redhead_bullet_impulse(entity, self.tile_map, None, 0.05)
        final_x = self.world_position(entity)["x"]

        self.assertAlmostEqual(immediate_x - start_x, 7.5, places=4)
        self.assertAlmostEqual(final_x - start_x, 10.0, places=4)
        self.assertEqual(entity["bullet_impulse"], {"x": 0.0, "y": 0.0})
        self.assertEqual(entity["ai_velocity"], {"x": 0.0, "y": 0.0})

    def test_repeated_hits_accumulate_but_respect_cap(self):
        entity = self.redhead_at_collision_tile()
        bullet = self.bullet({"x": 1000.0, "y": 0.0})

        self.apply_hit(entity, bullet)
        # The update loop retains the state from before all projectile traces;
        # current entity state must still make this count as a repeated hit.
        self.apply_hit(entity, bullet, state_before="angry chase")

        self.assertAlmostEqual(
            game.vec2_norm(entity["bullet_impulse"]),
            game.DEFAULT_BULLET_COMBINED_IMPACT_CAP,
        )

    def test_wall_collision_stops_impulse_without_reversing_it(self):
        entity = self.redhead_at_collision_tile(1, 5)
        self.tile_map["tiles"][2 + 5 * 20]["index"] = 3
        start_x = self.world_position(entity)["x"]
        self.apply_hit(entity, self.bullet({"x": 1000.0, "y": 0.0}))

        game.advance_redhead_bullet_impulse(entity, self.tile_map, None, 0.10)
        stopped_x = self.world_position(entity)["x"]
        game.advance_redhead_bullet_impulse(entity, self.tile_map, None, 0.10)

        self.assertGreaterEqual(stopped_x, start_x)
        self.assertLessEqual(stopped_x - start_x, 4.01)
        self.assertAlmostEqual(self.world_position(entity)["x"], stopped_x)
        self.assertEqual(entity["bullet_impulse"], {"x": 0.0, "y": 0.0})

    def test_dead_redhead_uses_same_impulse_and_keeps_death_pose(self):
        entity = self.redhead_at_collision_tile()
        entity["health"] = 20
        start_x = self.world_position(entity)["x"]
        self.apply_hit(entity, self.bullet({"x": 1000.0, "y": 0.0}))

        self.assertEqual(entity["current_state"], "dead")
        game.death_state(
            entity, "dead", {}, self.tile_map, None,
            game.DEFAULT_BULLET_IMPACT_DURATION,
        )

        self.assertAlmostEqual(self.world_position(entity)["x"] - start_x, 10.0)
        self.assertEqual(entity["animation_frame"], "death_frame_start")
        self.assertEqual(entity["bullet_impulse"], {"x": 0.0, "y": 0.0})


if __name__ == "__main__":
    unittest.main()
