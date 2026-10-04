"""Fixed camera cuts must preserve movement and the existing scene collision."""
import math
import unittest

from pyrsistent import pmap

import g_night
import g_temple_cameras as cameras
import g_temple_structure as structure
import g_update_and_render as game
from moonlit_water_temple_blender import review_arena
from temple_3d_viewer import can_walk


class CameraControlTests(unittest.TestCase):
    def test_route_changes_shots_in_both_directions(self):
        director = cameras.CameraDirector()
        sequence = []
        for point in cameras.REVIEW_ROUTE:
            director.update(*point)
            sequence.append(director.active)
        self.assertEqual(tuple(sequence), cameras.REVIEW_SHOTS)
        self.assertEqual(director.cut_count, 4)

    def test_overlap_prevents_boundary_chatter(self):
        director = cameras.CameraDirector()
        for x in (368, 367, 369, 360, 344):
            director.update(x, 334)
            self.assertEqual(director.active, 'landing')
        director.update(343, 334)
        self.assertEqual(director.active, 'approach')

        director.update(480, 267)
        self.assertEqual(director.active, 'sanctum')
        for y in (268, 269, 267, 275, 279):
            director.update(480, y)
            self.assertEqual(director.active, 'sanctum')
        director.update(480, 280)
        self.assertEqual(director.active, 'landing')
        self.assertEqual(director.cut_count, 4)

    def test_held_input_keeps_world_direction_until_full_release(self):
        director = cameras.CameraDirector()
        intent = cameras.MovementIntent()
        before = intent.direction({'d'}, director)
        director.update(480, 334)
        self.assertEqual(intent.direction({'d'}, director), before)
        # Adding/removing another key also retains the original camera basis.
        intent.direction({'w', 'd'}, director)
        self.assertEqual(intent.direction({'d'}, director), before)
        self.assertEqual(intent.direction({'w', 's'}, director), (0., 0.))
        self.assertEqual(intent.direction({'d'}, director), before)
        self.assertEqual(intent.direction(set(), director), (0., 0.))
        after = intent.direction({'d'}, director)
        self.assertNotEqual(after, before)
        self.assertEqual(intent.source_camera, 'landing')

    def test_diagonal_speed_and_screen_direction(self):
        director = cameras.CameraDirector()
        for name in director.shots:
            director.active = name
            intent = cameras.MovementIntent()
            direction = intent.direction({'w', 'd'}, director)
            self.assertAlmostEqual(math.hypot(*direction), 1.)
            right, forward = cameras.movement_basis(director.shot)
            self.assertAlmostEqual(sum(a*b for a, b in zip(right, forward)), 0.)
            # Right points to screen right for Raylib's world-up camera.
            self.assertGreater(right[0], 0.)
            self.assertLess(forward[1], 0.)

    def test_actual_step_is_continuous_at_camera_cut(self):
        walk = cameras.Walkthrough(x=367, y=334)
        walk.step({'d'}, .05, lambda x, y: True)
        self.assertEqual(walk.director.active, 'landing')
        first = walk.x - 367, walk.y - 334
        previous = walk.x, walk.y
        walk.step({'d'}, .05, lambda x, y: True)
        self.assertAlmostEqual(walk.x-previous[0], first[0])
        self.assertAlmostEqual(walk.y-previous[1], first[1])

    def test_swept_collision_stops_at_thin_wall_and_slides(self):
        # The far side is valid ground, so an endpoint-only check would tunnel.
        permitted = lambda x, y: not (10 <= x <= 14)
        x, y = cameras.move_with_collision(0, 0, 1, 0, 100, permitted)
        self.assertLess(x, 10)
        self.assertEqual(y, 0)
        diagonal = math.sqrt(.5)
        x, y = cameras.move_with_collision(0, 0, diagonal, diagonal, 100, permitted)
        self.assertLess(x, 10)
        self.assertGreater(y, 70)

    def test_character_faces_actual_motion_when_sliding_along_a_wall(self):
        walk=cameras.Walkthrough(x=300,y=334)
        walk.step({'d'},.1,lambda x,y:y<=334)
        self.assertGreater(walk.x,300)
        self.assertEqual(walk.y,334)
        self.assertAlmostEqual(walk.heading[0],1.)
        self.assertAlmostEqual(walk.heading[1],0.)


class TempleWalkabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        arena = review_arena(game, pmap(dict(
            entities={}, tile_map=game.make_tile_map(1, 1, 16, 16),
            player_info=game.make_default_player(0, 0, 0))))
        cls.source_arena=arena
        arena=structure.prepare(arena)
        g_night.sync_collision(arena)
        cls.arena=arena
        cls.tile_map = arena['tile_map']

    def test_entire_review_route_is_reachable_without_teleporting(self):
        x, y = cameras.REVIEW_ROUTE[0]
        self.assertTrue(can_walk(self.tile_map, x, y))
        for tx, ty in cameras.REVIEW_ROUTE[1:]:
            length = math.hypot(tx-x, ty-y)
            dx, dy = (tx-x)/length, (ty-y)/length
            x, y = cameras.move_with_collision(
                x, y, dx, dy, length,
                lambda px, py: can_walk(self.tile_map, px, py))
            self.assertAlmostEqual(x, tx)
            self.assertAlmostEqual(y, ty)

    def test_doorway_open_but_wall_and_lake_remain_blocked(self):
        for point in ((480, 276), (480, 270), (480, 258)):
            self.assertTrue(can_walk(self.tile_map, *point), point)
        for point in ((424, 270), (504, 270), (320, 300), (-5, 334)):
            self.assertFalse(can_walk(self.tile_map, *point), point)


if __name__ == '__main__':
    unittest.main()
