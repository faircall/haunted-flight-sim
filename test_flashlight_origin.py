"""A projected flashlight cone and its physical wall rays have distinct origins."""
import math
import unittest
from unittest import mock

import g_graphics as graphics
import g_light_visibility as visibility
import g_render_order as order
import g_update_and_render as game


class FlashlightOriginTests(unittest.TestCase):
    def test_beam_stays_on_animated_lens_through_all_aim_directions(self):
        tm=game.make_tile_map(20,20,16,16)
        for angle in range(0,360,45):
            direction={'x':math.cos(math.radians(angle)),'y':math.sin(math.radians(angle))}
            player=game.make_default_player(120.,120.,0.)
            player.update(aim_heading=angle,aim_direction=direction,animation_direction=('right','down','left','up')[((angle+45)//90)%4],
                          procedural_gait={'phase':.7,'blend':1.,'run_blend':0.})
            lens=order.player_cutout_flashlight_world(player,tm)['position']
            torch=graphics.make_player_flashlight(player,tm)
            self.assertEqual(torch['render_position'],lens)
            self.assertAlmostEqual(torch['position']['y'],lens['y']+torch['height'])

    def test_wall_clamp_does_not_drag_the_visible_lens(self):
        tm=game.make_tile_map(20,20,16,16)
        for x in range(20):tm['tiles'][6*20+x]['index']=3
        grid=visibility.build_light_collision_grid(tm,{3})
        player=game.make_default_player(104.,108.,0.)
        player['aim_direction']={'x':0.,'y':-1.}
        lens={'x':104.,'y':70.}
        with mock.patch.object(order,'player_cutout_flashlight_world',return_value={'position':lens}):
            torch=graphics.make_player_flashlight(player,tm,grid)
        self.assertEqual(torch['render_position'],lens)
        self.assertGreater(torch['position']['y'],112.)
        self.assertLess(torch['position']['y'],114.)

    def test_projected_cone_and_physical_surface_sampling_are_separate(self):
        tm=game.make_tile_map(20,20,16,16);grid=visibility.build_light_collision_grid(tm,{3})
        torch=dict(type='spot',position={'x':80.,'y':120.},render_position={'x':80.,'y':98.},
                   direction={'x':1.,'y':0.},radius=180.,inner_angle=13.,outer_angle=27.,visibility_type='point')
        point={'x':100.,'y':98.}
        self.assertGreater(visibility.get_gameplay_light_strength_at_world_point(torch,point,grid),.5)
        self.assertEqual(visibility.get_unoccluded_light_strength_at_world_point(torch,point,grid,projected=False),0.)
        polygon=visibility.build_light_visibility_polygon_dda(torch,torch['position'],grid)['polygon']
        self.assertTrue(graphics.point_in_polygon(point,polygon),'physical visibility clips the correctly placed beam')
        key=visibility.make_light_geometry_key({'light':torch},torch['position'],grid)
        self.assertNotEqual(key,visibility.make_light_geometry_key({'light':dict(torch,visibility_type='spot')},torch['position'],grid))


if __name__=='__main__':unittest.main()
