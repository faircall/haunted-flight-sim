import unittest
from types import SimpleNamespace
import g_player_reveal as reveal
import g_render_order as order


def item(identity,y=10.,x=0.,blocks=True):
    return dict(source_id=identity,sort_y=y,occludes_render_items=blocks,
                bounds_world=dict(x=x,y=0.,width=32.,height=32.),
                dest_rect=dict(x=x,y=0.,width=32.,height=32.))


class PlayerRevealTests(unittest.TestCase):
    def test_only_overlapping_opaque_objects_drawn_after_player_are_candidates(self):
        player=item('player',blocks=False)
        behind=item('behind',y=9.)
        front=item('front',y=11.)
        beside=item('beside',y=11.,x=40.)
        prop=item('prop',y=11.,blocks=False)
        hidden=item('hidden',y=11.);hidden['opacity']=0.
        selected,blockers=reveal.candidates(order.sort_world_render_items([front,beside,player,behind,prop,hidden]))
        self.assertIs(selected,player)
        self.assertEqual(blockers,[front])

    def test_equal_depth_uses_real_draw_order_and_supports_multiple_blockers(self):
        player=item('player')
        before=item('a');after=item('z');tree=item('tree',y=12.)
        self.assertEqual(reveal.candidates(order.sort_world_render_items([tree,after,player,before]))[1],[after,tree])
        self.assertEqual(reveal.candidates([tree]),(None,[]))

    def test_patch_uses_the_same_camera_rounding_as_the_player_sprite(self):
        player=item('player',x=10.2);player['dest_rect']['y']=7.8
        player['screen_snap']='relative_motion'
        camera=SimpleNamespace(x=.6,y=.6)
        self.assertEqual(reveal.screen_region(player,camera),(10,7,32.,32.))
        player.pop('screen_snap')
        self.assertEqual(reveal.screen_region(player,camera),(9,7,32.,32.))


if __name__=='__main__':unittest.main()
