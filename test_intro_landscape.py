"""Placement and portable geometry contracts for the lakeside approach."""
import json
from pathlib import Path
import struct
import unittest
import numpy as np
from PIL import Image
from g_intro_landscape import (scenery,ridges,TREE_MODELS,LAKE_HEIGHT,LAKE_EDGE,
                               STAIR_COUNT,STAIR_RISE,last_electric_light)
from g_temple_intro import Intro,load_script
from test_temple_living import accessor

KIT=Path(__file__).parent/'art'/'temple'/'intro'


def mesh_data(name):
    raw=(KIT/(name+'.glb')).read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+size]);return doc,raw[28+size:]


class LandscapeTests(unittest.TestCase):
    def test_trees_keep_water_open_and_clear_the_drivable_road(self):
        for distance in (0,173,850,1400,1e6):
            trees=list(scenery(distance));left=[t for t in trees if t['side']<0];right=[t for t in trees if t['side']>0]
            self.assertGreater(len(left),len(right)*4)
            self.assertTrue(all(abs(t['side'])>2.7 for t in trees))
            self.assertTrue(all(t['side']<LAKE_EDGE for t in trees))
            self.assertTrue(all(t['kind'] in TREE_MODELS for t in trees))
            self.assertLessEqual(len(trees),36)

    def test_mountains_stay_bounded_and_span_both_sides_of_the_lake(self):
        for distance in (0,200,700,1e6):
            values=list(ridges(distance));self.assertEqual(len(values),18)
            self.assertEqual({m['layer'] for m in values},{0,1,2})
            self.assertTrue(all(np.isfinite(m['position']).all() for m in values))
            self.assertTrue(all(m['position'][1]<LAKE_HEIGHT for m in values))
            self.assertEqual(values,list(ridges(distance)))

    def test_final_approach_has_no_electric_poles(self):
        intro=Intro(load_script());intro.elapsed=intro.duration-12
        self.assertGreater(intro.distance-25,last_electric_light(intro.arrival_station))

    def test_pines_have_embedded_alpha_foliage_and_real_wind_weights(self):
        for name in TREE_MODELS:
            doc,blob=mesh_data(name);leaves=0;wood=0;triangles=0
            self.assertTrue(all('bufferView' in image for image in doc['images']))
            for mesh in doc['meshes']:
                for primitive in mesh['primitives']:
                    weights=accessor(doc,blob,primitive['attributes']['TEXCOORD_1'])[:,0]
                    leaves+=int(np.count_nonzero(weights>.1));wood+=int(np.count_nonzero(weights<0))
                    triangles+=len(accessor(doc,blob,primitive['indices']))//3
            self.assertGreater(leaves,300);self.assertGreater(wood,100)
            self.assertLess(triangles,3000)
        with Image.open(KIT/'pine_foliage.png') as image:
            self.assertEqual(image.size,(256,256));alpha=np.asarray(image)[:,:,3]
            self.assertGreater(np.count_nonzero(alpha<16),alpha.size*.2)
            self.assertGreater(np.count_nonzero(alpha>240),alpha.size*.15)

    def test_main_approach_has_a_real_ascending_stair_flight(self):
        doc,blob=mesh_data('temple_facade')
        vertices=np.concatenate([accessor(doc,blob,p['attributes']['POSITION']) for m in doc['meshes'] for p in m['primitives']])
        # glTF coordinates are game coordinates; the top of every tread exists.
        centre=vertices[np.abs(vertices[:,0])<3.61]
        for step in range(STAIR_COUNT):
            y=(step+1)*STAIR_RISE;z=8.2-step*.43
            self.assertTrue(np.any((abs(centre[:,1]-y)<.001)&(abs(centre[:,2]-z)<.23)))
        self.assertGreater(vertices[:,1].max(),8.)
        self.assertGreater(vertices[:,0].max()-vertices[:,0].min(),15.)


if __name__=='__main__':unittest.main()
