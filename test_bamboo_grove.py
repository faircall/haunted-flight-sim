"""Playable route, camera access and watertight exported Chan-room geometry."""
from pathlib import Path
from functools import lru_cache
from collections import deque
import json
import struct
import math
import unittest
import numpy as np
from PIL import Image
from test_temple_living import accessor
from test_santana_car import intersections
from g_bamboo_grove import Explorer,PATH,SHOTS,SPAWN,can_walk,floor_height,camera_zone,bamboo_layout,path_distance

KIT=Path(__file__).parent/'art'/'temple'/'bamboo'

@lru_cache(maxsize=None)
def geometry(name):
    raw=(KIT/(name+'.glb')).read_bytes();length=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+length]);blob=raw[28+length:];points=[]
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            vertices=accessor(doc,blob,p['attributes']['POSITION']);indices=accessor(doc,blob,p['indices']).reshape(-1)
            points.append(vertices[indices].reshape(-1,3,3))
    return doc,np.concatenate(points)

class BambooGroveTests(unittest.TestCase):
    def test_exports_embed_materials_and_use_portable_mesh_indices(self):
        manifest=json.loads((KIT/'manifest.json').read_text());total=0
        self.assertTrue(manifest['separate_scene'])
        for name in manifest['models']:
            doc,points=geometry(name);total+=len(points)
            self.assertTrue(np.isfinite(points).all(),name)
            self.assertTrue(all('bufferView' in im for im in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:
                    self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123,name)
        self.assertGreater(total,300000);self.assertLess(total,1500000)
        for name in ('materials.png','scrolls.png'):
            with Image.open(KIT/name) as im:self.assertEqual(im.size,(1024,1024))

    def test_full_path_is_walkable_and_stems_clear_the_stones(self):
        for x,z in PATH:
            if -.3<z<41:self.assertTrue(can_walk(x,z),(x,z))
        for x,z,height,r,angle,far in bamboo_layout():
            self.assertGreaterEqual(path_distance(x,z),2.05-1e-3)
        self.assertGreater(len(bamboo_layout()),1000)

    def test_controller_enters_room_without_walking_through_props(self):
        e=Explorer()
        route=[p for p in PATH if -.4<p[1]<=40]+[(0,-1),(0,-2),(0,-3.6),(0,-4.4),(0,-6.6),(1.05,-8.3),(1.05,-10),(-.7,-11.2)]
        seen={e.shot};height=e.height
        for target in route:
            for _ in range(260):
                dx,dz=target[0]-e.x,target[1]-e.z
                if math.hypot(dx,dz)<.13:break
                e.yaw=math.atan2(dx,-dz);travel=e.tick(.05,1)
                self.assertGreater(travel,.00001,(e.x,e.z,target));self.assertTrue(can_walk(e.x,e.z))
                self.assertLess(abs(e.height-height),.14);height=e.height;seen.add(e.shot)
            else:self.fail('Route point not reached: '+str(target))
        self.assertEqual(seen,{0,1,2,3,4,5});self.assertAlmostEqual(e.height,.63,places=2)
        for x,z in ((0,-9.25),(.25,-11.4),(-6.5,-1),(2.7,-11.4),(4.6,-9),(-3.8,-9.5)):
            self.assertFalse(can_walk(x,z),(x,z))
        e=Explorer();e.tick(.1,-1);self.assertEqual(e.clip,'walk_back')
        e.tick(.1,0,1);self.assertEqual(e.clip,'turn_right')

    def test_garden_and_both_room_sides_are_reachable(self):
        # Start at the clearing and prove that no decorative mesh collision seals it.
        start=(0,0);seen={start};queue=deque([start]);spacing=.4
        while queue:
            node=queue.popleft()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                p=(node[0]+dx,node[1]+dz)
                if p not in seen and can_walk(p[0]*spacing,p[1]*spacing):seen.add(p);queue.append(p)
        for x,z in ((-8,-3),(8,-3),(-2,-8),(2,-8),(-2,-11),(0,40)):
            self.assertIn((round(x/spacing),round(z/spacing)),seen,(x,z))
        self.assertEqual(camera_zone(-8,-3),7)

    def test_roof_is_visible_from_inside_in_every_upward_direction(self):
        shell=np.concatenate([geometry(n)[1] for n in ('chan_roof','chan_shell','chan_timber')])
        normals=np.cross(shell[:,1]-shell[:,0],shell[:,2]-shell[:,0])
        for x in (-3,0,3):
            for z in (-12,-9,-6):
                for dx in (-.6,0,.6):
                    for dz in (-.6,0,.6):
                        ray=np.array((dx,1.,dz));ray/=np.linalg.norm(ray)
                        visible=shell[normals.dot(ray)<-1e-6]
                        hits=intersections(visible,np.array((x,2.35,z)),ray,tolerance=1e-5)
                        self.assertGreater(len(hits),0,(x,z,dx,dz,'sky hole or back-facing roof'))
                        self.assertLess(hits.min(),7.)

    def test_rendered_floor_matches_controller_at_steps_and_inside(self):
        shell=geometry('chan_shell')[1];normals=np.cross(shell[:,1]-shell[:,0],shell[:,2]-shell[:,0]);up=shell[normals[:,1]>1e-6]
        for z in (-.5,-1.1,-1.7,-2.3,-3.2,-4.2,-7,-10):
            hits=intersections(up,np.array((0,2.,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertGreater(len(hits),0)
            self.assertLess(abs(2.-hits.min()-floor_height(0,z)),.012,(z,hits.min(),floor_height(0,z)))

    def test_interior_camera_sightlines_are_clear_of_lattice_and_furniture(self):
        solid=np.concatenate([geometry(n)[1] for n in ('chan_shell','chan_timber','chan_roof','chan_props')])
        for index,player in ((4,(0,1.95,-8.2)),(5,(0,1.95,-7.))):
            eye=np.array(SHOTS[index]['eye']);delta=np.array(player)-eye;length=np.linalg.norm(delta)
            hits=intersections(solid,eye,delta/length,tolerance=1e-5)
            self.assertFalse(any(hits<length-.1),(index,hits))
        self.assertEqual(camera_zone(0,30.6,0),0)
        self.assertEqual(camera_zone(0,30.0,0),1)

    def test_round_window_has_opaque_spandrels_and_real_openings(self):
        shell=geometry('chan_shell')[1];normal=np.cross(shell[:,1]-shell[:,0],shell[:,2]-shell[:,0]);interior=shell[normal[:,2]>1e-6]
        for x,y in ((1.4,2.45),(-1.4,2.45),(0,3.45),(0,1.4),(1.,3.3),(-1.,1.6)):
            hits=intersections(interior,np.array((x,y,-11.5)),np.array((0.,0.,-1.)),tolerance=1e-5)
            self.assertTrue(any(hits<1.6),(x,y,'Missing plaster around round window'))
        hits=intersections(shell,np.array((.13,2.6,-11.5)),np.array((0.,0.,-1.)),tolerance=1e-5)
        self.assertFalse(any(hits<2.),'Window opening filled by plaster')

if __name__=='__main__':unittest.main()
