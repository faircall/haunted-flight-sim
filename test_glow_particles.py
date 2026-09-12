import unittest
from unittest.mock import patch
from types import SimpleNamespace
import g_glow_particles as motes
import g_glow


class MoteTests(unittest.TestCase):
    def test_edges_are_on_silhouette_and_normals_point_outward(self):
        points = motes.edge_samples(bytes([255]*25),5,5,(0,0,5,5))
        self.assertEqual(len(points),16)
        self.assertTrue(all(x in (.5,4.5) or y in (.5,4.5) for x,y,_,_ in points))
        self.assertIn((.5,2.5,-1.,0.),points)
        self.assertEqual(motes.edge_samples(bytes(25),5,5,(0,0,5,5)),[])

    def test_caps_offscreen_and_disabled_fadeout(self):
        assets = {}
        camera = SimpleNamespace(x=0,y=0)
        objects = []
        for i in range(20):
            item = dict(source_id=str(i),dest_rect=dict(x=1,y=1,width=8,height=8),
                        glow=dict(enabled=True,particles=dict(enabled=True,rate=40.,lifetime=4.)))
            objects.append((item,g_glow.settings(item)))
        with patch.object(motes,"shapes",return_value=[(1.,1.,-1.,0.)]):
            for frame in range(100):
                motes.update(assets,objects,camera,100,100,frame*.1)
            pool = assets["glow_particles"]["particles"]
            self.assertLessEqual(len(pool),motes.MAX_PARTICLES)
            self.assertTrue(all(sum(p["owner"]==str(i) for p in pool)<=motes.MAX_PER_OBJECT for i in range(20)))
            camera.x = 1000
            for frame in range(100,150):
                motes.update(assets,objects,camera,100,100,frame*.1)
            self.assertEqual(assets["glow_particles"]["particles"],[])
            self.assertEqual(assets["glow_particles"]["sources"],{})
