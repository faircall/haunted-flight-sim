import unittest
from unittest import mock

import g_audio
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
            "x": 46.0, "y": 44.0, "width": 16.0, "height": 22.0,
        })
        # This diagonal crosses the visible body without entering anchor tile 4,4.
        hit = game.find_first_redhead_bullet_hit(
            {"x": 20.0, "y": 80.0}, {"x": 80.0, "y": 20.0},
            {entity["id"]: entity}, tile_map,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit["entity_id"], entity["id"])

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

    def update(self):
        with mock.patch.object(
                game, "transition_entity_state",
                side_effect=lambda entity, state, *args: state), \
                mock.patch.object(g_audio, "update_actor_footstep_travel"):
            game.update_entities(
                self.entities, self.tile_map, make_player(), "play", "regular",
                0.01, self.audio, g_audio.make_audio_profile(),
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


if __name__ == "__main__":
    unittest.main()
