"""Rockery navigation, real multilevel crossings, geometry and camera contracts."""
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
from g_rockery import Explorer,NODES,EDGES,ROOMS,REVIEW_ROUTES,ENCOUNTERS,can_walk,support_height,OBSTACLES,PAVILION,review_points
from rockery_camera import RockField,Director

KIT=Path(__file__).parent/'art'/'temple'/'rockery'

@lru_cache(maxsize=None)
def geometry(name):
    data=(KIT/(name+'.glb')).read_bytes();size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);blob=data[28+size:];points=[]
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            xyz=accessor(doc,blob,p['attributes']['POSITION']);ids=accessor(doc,blob,p['indices']).reshape(-1);points.append(xyz[ids].reshape(-1,3,3))
    return doc,np.concatenate(points)

@lru_cache(maxsize=1)
def walks():
    results=[]
    for title,nodes in REVIEW_ROUTES:
        for reverse in (False,True):
            route=nodes[::-1] if reverse else nodes;e=Explorer();e.x,e.floor,e.z=NODES[route[0]];e.height=e.floor;samples=[];steps=0
            for x,h,z in review_points(route)[1:]:
                name=(x,h,z)
                for _ in range(800):
                    dx,dz=x-e.x,z-e.z
                    if math.hypot(dx,dz)<.11:break
                    e.yaw=math.atan2(dx,-dz);before=e.floor;distance=e.tick(.05,1);steps+=1
                    assert distance>.00001,('Blocked',title,reverse,name,e.x,e.floor,e.z)
                    assert abs(e.floor-before)<.195,('Unexpected step',before,e.floor)
                    if steps%6==0:samples.append((e.x,e.floor,e.z))
                else:raise AssertionError(('Unreachable',title,name))
            results.append((title,reverse,tuple(samples)))
    return tuple(results)

class RockeryTests(unittest.TestCase):
    def test_every_route_works_in_both_directions_without_height_jumps(self):
        routes=walks();self.assertEqual(len(routes),10)
        for name,reverse,samples in routes:
            self.assertTrue(samples)
            for x,h,z in samples:self.assertTrue(can_walk(x,z,h),(name,reverse,x,h,z))
            if name=='upper_crossing':self.assertGreater(max(p[1] for p in samples),3.2)
        e=Explorer();e.tick(.1,-1);self.assertEqual(e.clip,'walk_back');e.tick(.1,0,1);self.assertEqual(e.clip,'turn_right')

    def test_layout_contains_loops_and_a_deliberate_blind_branch(self):
        neighbours={n:set() for n in NODES}
        for a,b,w,roof in EDGES:neighbours[a].add(b);neighbours[b].add(a)
        seen={'gate'};queue=['gate']
        while queue:
            for n in neighbours[queue.pop()]-seen:seen.add(n);queue.append(n)
        self.assertEqual(seen,set(NODES));self.assertGreaterEqual(len(EDGES)-len(NODES)+1,3)
        self.assertEqual(len(neighbours['window']),1)

    def test_encounter_spawns_have_room_and_are_disabled(self):
        manifest=json.loads((KIT/'manifest.json').read_text());notes=json.loads((KIT/'encounters.json').read_text())
        self.assertEqual(manifest['enemy_count'],0);self.assertFalse(notes['enabled']);self.assertEqual(len(notes['areas']),4)
        for area in ENCOUNTERS:
            self.assertTrue(area['exits'])
            for x,h,z in area['spawns']:self.assertTrue(can_walk(x,z,h,radius=.32),(area['id'],x,z))
        for x,z,r,h in OBSTACLES:self.assertFalse(can_walk(x,z,.08))

    def test_baked_rock_clearance_agrees_with_the_playable_routes(self):
        field=RockField(KIT);points=[]
        for name,reverse,samples in walks():
            if reverse:continue
            for x,h,z in samples[::3]:
                for y in (.2,.9,1.73):
                    for dx,dz in ((0,0),(.23,0),(-.23,0),(0,.23),(0,-.23)):points.append((x+dx,h+y,z+dz))
        values=field.sample(points);bad=np.flatnonzero(values<-.08)
        self.assertEqual(len(bad),0,[(points[i],values[i]) for i in bad[:8]])

    def test_camera_positions_cover_the_maze_without_looking_through_rock(self):
        field=RockField(KIT)
        solid=np.concatenate([geometry(n)[1] for n in ('high_walk','garden_props','pavilion')])
        low=solid.min(axis=1);high=solid.max(axis=1)
        for name,reverse,samples in walks():
            director=Director(field);e=Explorer()
            for x,h,z in samples[::3]:
                e.x=x;e.z=z;e.floor=h;e.height=h
                index,eye,target,fov=director.select(e)
                self.assertTrue(director.last_clear,(name,reverse,x,h,z))
                # Independently ray-test the exported decks, rails, lamps and posts.
                eye=np.asarray(eye);body=np.array((x,h+.93,z));ray=body-eye;length=np.linalg.norm(ray)
                near=solid[np.all(high>=np.minimum(eye,body),axis=1)&np.all(low<=np.maximum(eye,body),axis=1)]
                hits=intersections(near,eye,ray/length,tolerance=1e-5)
                self.assertFalse(any((hits>.1)&(hits<length-.12)),(name,reverse,index,x,h,z))

    def test_upper_and_lower_routes_cross_without_teleporting_between_floors(self):
        a=np.array(NODES['fork'])[[0,2]];b=np.array(NODES['reveal'])[[0,2]]
        c=np.array(NODES['bridge_mid'])[[0,2]];d=np.array(NODES['bridge_west'])[[0,2]]
        t,u=np.linalg.solve(np.column_stack((b-a,c-d)),c-a);p=a+(b-a)*t
        self.assertTrue(0<t<1 and 0<u<1)
        self.assertAlmostEqual(support_height(*p,.08),.08)
        self.assertAlmostEqual(support_height(*p,3.28),3.28)
        for height,name in ((.08,'stone_paths'),(3.28,'high_walk')):
            tri=geometry(name)[1];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);up=tri[n[:,1]>1e-7]
            hits=intersections(up,np.array((p[0],height+.06,p[1])),np.array((0.,-1.,0.)),tolerance=1e-5)
            self.assertTrue(len(hits))
            # The upper surface now has shallow worn hollows below its support height.
            self.assertAlmostEqual(hits.min(),.06,delta=.020 if height>1 else .001)

    def test_walkable_surfaces_match_the_exported_stairs_and_floors(self):
        tri=np.concatenate([geometry(n)[1] for n in ('stone_paths','high_walk','pavilion')]);normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);tri=tri[normal[:,1]>1e-7]
        low=tri.min(axis=1);high=tri.max(axis=1)
        for name,reverse,samples in walks():
            if reverse:continue
            for x,h,z in samples[::5]:
                near=tri[(low[:,0]<=x+.001)&(high[:,0]>=x-.001)&(low[:,2]<=z+.001)&(high[:,2]>=z-.001)]
                hits=intersections(near,np.array((x,h+.065,z)),np.array((0.,-1.,0.)),tolerance=1e-5)
                self.assertTrue(len(hits),(name,x,h,z));self.assertLess(abs(hits.min()-.065),.025,(name,x,h,z,hits.min()))

    def test_perforations_and_cave_roofs_are_real_geometry(self):
        tri=np.concatenate([geometry('taihu_rockery_'+str(i))[1] for i in range(6)]);low=tri.min(axis=1);high=tri.max(axis=1);covered=0
        for x,z in ((0,21),(-3.8,15),(-3.8,12),(-8,-11)):
            near=tri[(low[:,0]<=x)&(high[:,0]>=x)&(low[:,2]<=z)&(high[:,2]>=z)]
            hits=intersections(near,np.array((x,.28,z)),np.array((0.,1.,0.)),tolerance=1e-5)
            if len(hits):
                self.assertGreater(hits.min(),1.80);covered+=1
        self.assertGreaterEqual(covered,2)
        near=tri[(high[:,0]>-.51)&(low[:,0]<-.49)&(high[:,1]>1.57)&(low[:,1]<1.59)]
        hits=intersections(near,np.array((-.5,1.58,-8.)),np.array((0.,0.,-1.)),tolerance=1e-5)
        self.assertFalse(any(hits<4.0),'The stone eye was filled in')

    def test_assets_are_portable_and_self_contained(self):
        manifest=json.loads((KIT/'manifest.json').read_text());total=0
        self.assertTrue(manifest['separate_scene'])
        for name in manifest['models']:
            doc,tri=geometry(name);total+=len(tri);self.assertTrue(np.isfinite(tri).all())
            self.assertTrue(all('bufferView' in i for i in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123)
        self.assertGreater(total,100000);self.assertLess(total,1600000)
        with Image.open(KIT/'materials.png') as im:self.assertEqual(im.size,(1024,1024))

if __name__=='__main__':unittest.main()
