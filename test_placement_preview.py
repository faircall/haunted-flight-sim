import unittest
from types import SimpleNamespace as Point
import g_placement_preview as preview


class PlacementPreviewTests(unittest.TestCase):
    def test_position_matches_each_placement_policy(self):
        tile_map = dict(tile_width=16,tile_height=16,map_width=20,map_height=20)
        mouse,camera = Point(x=19.5,y=23.25),Point(x=2.,y=4.)
        state = dict(snap_enabled=True,snap_size=8.)
        self.assertEqual(preview.placement_position("entity",mouse,camera,tile_map,state),dict(tile_x=1,tile_y=1,x=5.5,y=11.25))
        self.assertEqual(preview.placement_position("tile",mouse,camera,tile_map,state),dict(tile_x=1,tile_y=1,x=0.,y=0.))
        self.assertEqual(preview.placement_position("environment",mouse,camera,tile_map,state),dict(tile_x=1,tile_y=1,x=8.,y=8.))
        self.assertIsNone(preview.placement_position("entity",Point(x=-20,y=0),camera,tile_map,state))

    def test_ghost_alpha_stays_translucent(self):
        values = [preview.opacity(i*.01) for i in range(200)]
        self.assertGreaterEqual(min(values),.34)
        self.assertLessEqual(max(values),.62)
        self.assertGreater(max(values)-min(values),.2)
