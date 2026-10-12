"""Interior export, complete ceiling/floor and independent exploration contracts."""
from pathlib import Path
import json
import struct
import unittest
from collections import deque
import numpy as np
from PIL import Image
from g_temple_interior import Explorer,SPAWN,COLUMNS,SHOTS,can_walk,camera_zone
from test_temple_living import accessor
from test_santana_car import intersections

KIT=Path(__file__).parent/'art'/'temple'/'interior'

def geometry(name):
    raw=(KIT/(name+'.glb')).read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+size]);blob=raw[28+size:];triangles=[]
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            xyz=accessor(doc,blob,p['attributes']['POSITION']);ids=accessor(doc,blob,p['indices']).reshape(-1)
            triangles.append(xyz[ids].reshape(-1,3,3))
    return doc,blob,np.concatenate(triangles)

class InteriorTests(unittest.TestCase):
    def test_assets_have_embedded_textures_and_portable_indices(self):
        manifest=json.loads((KIT/'manifest.json').read_text());total=0
        for name in manifest['models']:
            doc,blob,triangles=geometry(name);total+=len(triangles)
            self.assertTrue(np.isfinite(triangles).all())
            self.assertTrue(all('bufferView' in image for image in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123)
        self.assertGreater(total,40000);self.assertLess(total,120000)
        self.assertTrue(manifest['separate_from_intro'])
        for name,size in (('architecture.png',(1024,1024)),('murals.png',(1024,1024))):
            with Image.open(KIT/name) as image:self.assertEqual(image.size,size)

    def test_interior_has_solid_floor_and_weatherproof_roof(self):
        floor=geometry('hall_shell')[2];ceiling=np.concatenate([geometry(n)[2] for n in ('hall_ceiling','hall_roof','hall_timber')])
        for x in np.linspace(-9,9,9):
            for z in np.linspace(-9,7,9):
                origin=np.array((x,1.7,z));down=intersections(floor,origin,np.array((0.,-1.,0.)),tolerance=1e-5)
                up=intersections(ceiling,origin,np.array((0.,1.,0.)),tolerance=1e-5)
                self.assertGreater(len(down),0,(x,z,'floor hole'));self.assertGreater(len(up),0,(x,z,'ceiling hole'))
                self.assertLess(down.min(),1.76);self.assertLess(up.min(),8)

    def test_central_caisson_is_recessed_and_has_no_beam_through_its_middle(self):
        ceiling=np.concatenate([geometry(n)[2] for n in ('hall_ceiling','hall_timber')])
        for x in (-6,0,6):
            hits=intersections(ceiling,np.array((x,5.,-3.)),np.array((0.,1.,0.)),tolerance=1e-5)
            self.assertGreater(len(hits),0);self.assertGreater(hits.min(),2.7)

    def test_oblique_ceiling_views_see_the_roof_underside_not_the_sky(self):
        shell=np.concatenate([geometry(n)[2] for n in ('hall_roof','hall_ceiling','hall_timber','hall_shell')])
        normals=np.cross(shell[:,1]-shell[:,0],shell[:,2]-shell[:,0])
        for x in (-6,0,6):
            for dx in (-.9,-.5,0,.5,.9):
                for dz in (-.9,-.5,0,.5,.9):
                    direction=np.array((dx,1.,dz));direction/=np.linalg.norm(direction)
                    faces=shell[normals.dot(direction)<-1e-6]
                    hits=intersections(faces,np.array((x,5.,-3.)),direction,tolerance=1e-5)
                    self.assertGreater(len(hits),0,(x,dx,dz,'Back-facing or absent roof'))

    def test_tank_controls_collision_and_reverse_animation(self):
        e=Explorer()
        for _ in range(150):e.tick(.1,1)
        self.assertTrue(can_walk(e.x,e.z));self.assertGreater(e.z,-2.3)
        before=(e.x,e.z);e.tick(.1,-1)
        self.assertEqual(e.clip,'walk_back');self.assertGreater(e.z,before[1])
        e.tick(.1,0,1);self.assertEqual(e.clip,'turn_right')
        for x,z,r in COLUMNS:self.assertFalse(can_walk(x,z))
        self.assertFalse(can_walk(0,-5));self.assertFalse(can_walk(10,0));self.assertFalse(can_walk(4,8))

    def test_all_mural_aisles_are_reachable_from_the_porch(self):
        start=(0,20);queue=deque([start]);seen={start}
        while queue:
            node=queue.popleft()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt=(node[0]+dx,node[1]+dz)
                if nxt not in seen and can_walk(nxt[0]*.5,nxt[1]*.5):seen.add(nxt);queue.append(nxt)
        for p in ((0,-18),(-16,-4),(16,-4),(0,8)):self.assertIn(p,seen)
        zones={camera_zone(x*.5,z*.5) for x,z in seen}
        self.assertTrue({0,1,2,3,4}<=zones)
        self.assertEqual(camera_zone(-4.7,0,2),2);self.assertEqual(camera_zone(-4.4,0,2),1)

    def test_paintings_are_vertical_and_visible_from_their_aisles(self):
        murals=geometry('hall_murals')[2]
        self.assertGreater(len(murals),20)
        for side in (-1,1):
            for z in (-7.15,-2.7,1.75,5.85):
                hits=intersections(murals,np.array((side*8.,2.7,z)),np.array((side,0.,0.)))
                self.assertTrue(len(hits));self.assertLess(hits.min(),2.)
        for shot in SHOTS:
            self.assertTrue(np.isfinite(shot['eye']).all());self.assertGreater(shot['fov'],40)

if __name__=='__main__':unittest.main()
