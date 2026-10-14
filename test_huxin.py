"""Lake route, reserved assembly space, exported surfaces and camera visibility."""
from pathlib import Path
from functools import lru_cache
import math
import json
import struct
import unittest
import numpy as np
from PIL import Image
from test_temple_living import accessor
from test_santana_car import intersections
from g_huxin import (Explorer,DECK,PATH,SPAWN,REVIEW_ROUTE,PUZZLE_RADIUS,FUTURE_RING,
                     COLUMNS,BENCHES,can_walk,path_distance,trees,walk_height,SHORE_LAMPS,LIGHTS,shore_height,path_halfwidth)

KIT=Path(__file__).parent/'art'/'temple'/'huxin'

@lru_cache(maxsize=None)
def geometry(name):
    raw=(KIT/(name+'.glb')).read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+size]);blob=raw[28+size:];points=[]
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            xyz=accessor(doc,blob,p['attributes']['POSITION']);ids=accessor(doc,blob,p['indices']).reshape(-1)
            points.append(xyz[ids].reshape(-1,3,3))
    return doc,np.concatenate(points)

@lru_cache(maxsize=1)
def walks():
    route=(SPAWN,)+REVIEW_ROUTE;result=[]
    for reverse in (False,True):
        points=route[::-1] if reverse else route;e=Explorer();e.x,e.z=points[0];e.height=walk_height(e.x,e.z);samples=[];steps=0
        for x,z in points[1:]:
            for _ in range(1200):
                dx,dz=x-e.x,z-e.z
                if math.hypot(dx,dz)<.12:break
                e.yaw=math.atan2(dx,-dz);old_height=e.height;distance=e.tick(.05,1);steps+=1
                assert distance>1e-6,('Blocked',reverse,x,z,e.x,e.z)
                assert abs(e.height-old_height)<.02,('Abrupt shore step',e.height,old_height)
                if steps%8==0:samples.append((e.x,e.z))
            else:raise AssertionError(('Unreachable',reverse,x,z))
        result.append(samples)
    return result

class HuxinTests(unittest.TestCase):
    def test_causeway_and_pavilion_are_traversable_in_both_directions(self):
        for route in walks():
            self.assertGreater(len(route),100)
            for x,z in route:self.assertTrue(can_walk(x,z))
        e=Explorer();e.tick(.1,-1);self.assertEqual(e.clip,'walk_back');e.tick(.1,0,1);self.assertEqual(e.clip,'turn_right')

    def test_water_columns_and_benches_stop_the_player_even_when_running(self):
        for x,z,r in COLUMNS:self.assertFalse(can_walk(x,z))
        for x,z,rx,rz in BENCHES:self.assertFalse(can_walk(x,z))
        for p in ((10,0),(-10,0),(0,-8),(0,30),(30,30),(-14.7,77),(-9.3,77)):self.assertFalse(can_walk(*p))
        e=Explorer();e.x,e.z=PATH[70];e.yaw=math.pi/2
        for _ in range(40):e.tick(.1,1,run=True)
        self.assertTrue(can_walk(e.x,e.z));self.assertLess(path_distance(e.x,e.z),path_halfwidth(e.z)-.23)

    def test_exported_floors_support_the_entire_route_and_shore_path(self):
        tri=np.concatenate([geometry(n)[1] for n in ('causeway','pavilion_base','lake_bank')]);normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);tri=tri[normals[:,1]>1e-7]
        samples=walks()[0]+[(x+dx,z) for x,z in PATH if 73<z<91.8 for dx in (-.65,0,.65)]
        low,high=tri.min(axis=1),tri.max(axis=1)
        for x,z in samples:
            near=tri[(low[:,0]<=x+.001)&(high[:,0]>=x-.001)&(low[:,2]<=z+.001)&(high[:,2]>=z-.001)]
            hits=intersections(near,np.array((x,walk_height(x,z)+.10,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertTrue(len(hits),(x,z));self.assertAlmostEqual(hits.min(),.10,delta=.05 if z>75 else .01,msg=str((x,z)))

    def test_two_entrance_lamps_are_grounded_and_frame_an_open_walk(self):
        self.assertEqual(len(SHORE_LAMPS),2);self.assertEqual(len(LIGHTS),5)
        stone=geometry('pavilion_details')[1].reshape(-1,3);glow=geometry('lake_lamps')[1].reshape(-1,3)
        bank=geometry('lake_bank')[1]
        for x,z in SHORE_LAMPS:
            mask=np.linalg.norm(stone[:,[0,2]]-(x,z),axis=1)<.30
            lowest=stone[mask,1].min();hits=intersections(bank,np.array((x,10.,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertTrue(len(hits));self.assertLess(abs(lowest-(10-hits.min())),.06)
            light_y=next(y for lx,y,lz in LIGHTS if (lx,lz)==(x,z))
            self.assertTrue(np.any((np.linalg.norm(glow[:,[0,2]]-(x,z),axis=1)<.25)&(abs(glow[:,1]-light_y)<.25)))
            self.assertFalse(can_walk(x,z))
        self.assertTrue(can_walk(-12,76.6))

    def test_roof_has_closed_undersides_and_clear_headroom(self):
        tri=geometry('pavilion_ceiling')[1];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);down=tri[n[:,1]<-1e-7]
        for radius in (0.1,1.7,3.0,4.3,5.1):
            for angle in np.linspace(.02,math.tau-.03,31):
                origin=np.array((math.cos(angle)*radius,DECK+1.85,math.sin(angle)*radius))
                hits=intersections(down,origin,np.array((0.,1.,0.)),tolerance=1e-5)
                self.assertTrue(len(hits),(radius,angle));self.assertGreater(hits.min(),2.)

    def test_puzzle_space_is_clear_of_props_and_has_complete_paving(self):
        solid=np.concatenate([geometry(n)[1] for n in ('pavilion_posts','pavilion_brackets','pavilion_details','pavilion_roofs')])
        centers=solid.mean(axis=1);inside=(np.linalg.norm(centers[:,[0,2]],axis=1)<PUZZLE_RADIUS)&(centers[:,1]>DECK+.02)&(centers[:,1]<DECK+2.5)
        self.assertFalse(inside.any())
        for radius in (0.,.7,1.5,PUZZLE_RADIUS):
            for angle in np.linspace(0,math.tau,40):self.assertTrue(can_walk(radius*math.cos(angle),radius*math.sin(angle)))

    def test_reserved_water_stays_clear_except_for_the_approach(self):
        for name in ('lake_bank','lake_mountains','lake_plants'):
            points=geometry(name)[1].reshape(-1,3)
            self.assertGreater(np.linalg.norm(points[:,[0,2]],axis=1).min(),FUTURE_RING[1]+10)
        for x,y,z,scale,yaw,variant in trees():self.assertGreater(math.hypot(x,z)-scale*5,FUTURE_RING[1])
        for name in ('pavilion_posts','pavilion_roofs','pavilion_base','pavilion_brackets','pavilion_ceiling'):
            points=geometry(name)[1].reshape(-1,3);self.assertLess(np.linalg.norm(points[:,[0,2]],axis=1).max(),FUTURE_RING[0])
        points=geometry('pavilion_details')[1].reshape(-1,3);r=np.linalg.norm(points[:,[0,2]],axis=1)
        for x,y,z in points[(r>FUTURE_RING[0])&(r<FUTURE_RING[1])][::15]:self.assertLess(path_distance(x,z),1.3)
        plan=json.loads((KIT/'assembly_space.json').read_text());self.assertFalse(plan['puzzle']['implemented']);self.assertFalse(plan['surrounding_structure']['implemented'])

    def test_fixed_cameras_do_not_look_through_exported_architecture(self):
        from huxin_viewer import auto_camera
        tri=np.concatenate([geometry(n)[1] for n in ('pavilion_posts','pavilion_brackets','pavilion_details','pavilion_roofs','pavilion_base','causeway','lake_bank')]);low,high=tri.min(axis=1),tri.max(axis=1)
        e=Explorer()
        for samples in walks():
            for x,z in samples[::2]:
                e.x,e.z=x,z;e.tick(0);index,cam=auto_camera(e);eye=np.array((cam.position.x,cam.position.y,cam.position.z));body=np.array((x,e.height+.93,z));delta=body-eye;length=np.linalg.norm(delta)
                near=tri[np.all(high>=np.minimum(eye,body),axis=1)&np.all(low<=np.maximum(eye,body),axis=1)]
                hits=intersections(near,eye,delta/length,tolerance=1e-5)
                self.assertFalse(any((hits>.10)&(hits<length-.12)),(index,x,z))

    def test_assets_have_embedded_textures_and_portable_indices(self):
        manifest=json.loads((KIT/'manifest.json').read_text());self.assertTrue(manifest['separate_scene']);self.assertEqual(manifest['enemy_count'],0)
        for name in manifest['models']:
            doc,tri=geometry(name);self.assertTrue(np.isfinite(tri).all())
            self.assertTrue(all('bufferView' in im for im in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123)
        with Image.open(KIT/'materials.png') as im:self.assertEqual(im.size,(1024,1024))

if __name__=='__main__':unittest.main()
