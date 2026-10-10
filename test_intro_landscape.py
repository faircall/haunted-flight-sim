"""Placement and portable geometry contracts for the lakeside approach."""
import json
import math
from pathlib import Path
import struct
import unittest
import numpy as np
from PIL import Image
from g_intro_landscape import (scenery,ridges,TREE_MODELS,LAKE_HEIGHT,LAKE_EDGE,
                               STAIR_COUNT,STAIR_RISE,last_electric_light,BRIDGES,bank_height,
                               road_slope,road_curve,world_point,local_point,road_x,
                               road_height,car_pose,car_point,DEFAULT_ARRIVAL,
                               power_pole,power_wire,POLE_SPACING,BRIDGE_HALF,DRAW_BEHIND,DRAW_AHEAD,
                               junction_station,trail_fraction,main_road_height,main_road_x,
                               main_side_on_section,terrain_point,main_coordinates,shore_distance,river_height,river_station,
                               stair_z,STAIR_TREAD,RIVER_UPSTREAM,RIVER_DOWNSTREAM,main_bank_height)
from g_temple_intro import Intro,load_script
from test_temple_living import accessor

KIT=Path(__file__).parent/'art'/'temple'/'intro'


def mesh_data(name):
    raw=(KIT/(name+'.glb')).read_bytes();size=struct.unpack_from('<I',raw,12)[0]
    doc=json.loads(raw[20:20+size]);return doc,raw[28+size:]


class LandscapeTests(unittest.TestCase):
    def test_entire_mountain_meshes_clear_the_full_winding_road_envelope(self):
        meshes={}
        for name in ('ridge_a','ridge_b','ridge_c'):
            doc,blob=mesh_data(name)
            meshes[name]=np.concatenate([accessor(doc,blob,p['attributes']['POSITION']) for m in doc['meshes'] for p in m['primitives']])
        for distance in range(0,1450,23):
            heading=math.atan(road_slope(distance));c,s=math.cos(heading),math.sin(heading)
            for ridge in ridges(distance):
                x,_,z=ridge['position'];world_x=x*c-z*s+road_x(distance)
                footprint=world_x+meshes[ridge['kind']][:,0]*ridge['scale'][0]
                # Clear the entire sharper, 150m-left mountain branch.
                if ridge['layer']==0:self.assertLess(float(footprint.max()),-200)
                else:self.assertGreater(float(footprint.min()),37)

    def test_hills_change_grade_and_final_approach_climbs_to_level_forecourt(self):
        for arrival in (DEFAULT_ARRIVAL,1750.):
            stations=np.arange(0,arrival-290,2)
            pitch=np.degrees([car_pose(s,arrival)[1] for s in stations])
            self.assertGreater(pitch.max(),2.);self.assertLess(pitch.min(),-2.)
            heights=[road_height(s,arrival) for s in np.arange(junction_station(arrival),arrival-34,2)]
            self.assertTrue(all(b>=a-.005 for a,b in zip(heights[33:],heights[34:])))
            self.assertGreater(heights[-1]-heights[0],15.)
            self.assertAlmostEqual(road_height(arrival-30,arrival),road_height(arrival+20,arrival))
            for s in (arrival-10,arrival,arrival+10):
                for side in (-10,-5,0,5,10):
                    self.assertAlmostEqual(bank_height(s,side,arrival),road_height(s,arrival)-.035)

    def test_vehicle_wheels_track_road_heights_without_pitch_snaps(self):
        from g_santana_geometry import AXLES,WHEEL_Y,TYRE_RADIUS
        last=None
        for station in np.arange(0,DEFAULT_ARRIVAL,1):
            height,pitch=car_pose(station)
            if last is not None:self.assertLess(abs(pitch-last),.006)
            last=pitch;metric=math.sqrt(1+road_slope(station)**2)
            for z in AXLES:
                _,y,zz=car_point((0,WHEEL_Y,z),height,pitch)
                road=road_height(station-zz/metric)+.007
                self.assertLess(abs((y-TYRE_RADIUS)-road),.016,(station,z))

    def test_uphill_powerline_has_unbroken_sagging_spans_and_no_roadside_poles(self):
        for station in range(-36,1500,POLE_SPACING):
            x,y,z=power_pole(station)
            self.assertGreater(y,main_road_height(station)+2.)
            self.assertLess(x,main_road_x(station)-13.)
            for conductor in (-1,0,1):
                a=power_wire(station,conductor);b=power_wire(station+POLE_SPACING,conductor)
                self.assertTrue(np.allclose(a[-1],b[0]))
                self.assertLess(a[6][1],(a[0][1]+a[-1][1])/2-.60)

    def test_bends_change_heading_and_keep_a_constant_road_width(self):
        headings=np.degrees(np.arctan([road_slope(s) for s in range(0,1400,4)]))
        self.assertGreater(np.ptp(headings),45.)
        self.assertGreater(sum(np.sign(road_curve(s))!=np.sign(road_curve(s+20)) for s in range(0,1400,20)),5)
        for station in range(0,1450,13):
            a=np.array(world_point(station,-1.92));b=np.array(world_point(station,1.92))
            self.assertAlmostEqual(np.linalg.norm(b-a),3.84,places=6)
            self.assertTrue(np.allclose(local_point(station,1.92,station),(1.92,0),atol=1e-8))

    def test_bridges_cross_real_water_channels_and_meet_dry_banks(self):
        self.assertEqual(len(BRIDGES),3)
        for station in BRIDGES:
            self.assertLess(bank_height(station,0),LAKE_HEIGHT)
            self.assertLess(bank_height(station,-10),LAKE_HEIGHT)
            for offset in (-BRIDGE_HALF-.3,BRIDGE_HALF+.3):self.assertGreater(bank_height(station+offset,0),-.05)
            self.assertFalse(any(abs(t['station']-station)<12 for t in scenery(station)))

    def test_undergrowth_is_compact_textured_and_has_wind(self):
        for name in ('shrub','fern'):
            doc,blob=mesh_data(name);triangles=0
            for mesh in doc['meshes']:
                for p in mesh['primitives']:
                    triangles+=len(accessor(doc,blob,p['indices']))//3
                    weights=accessor(doc,blob,p['attributes']['TEXCOORD_1'])[:,0]
                    self.assertGreater(weights.max()-weights.min(),.3)
            self.assertLess(triangles,100)
            self.assertTrue(all('bufferView' in image for image in doc['images']))
        with Image.open(KIT/'undergrowth.png') as image:
            self.assertEqual(image.size,(256,256));self.assertEqual(image.mode,'RGBA')

    def test_trees_keep_water_open_and_clear_the_drivable_road(self):
        for distance in (0,173,850,1400,1e6):
            trees=list(scenery(distance));left=[t for t in trees if t['side']<0];right=[t for t in trees if t['side']>0]
            self.assertGreater(len(left),len(right)*2)
            self.assertTrue(all(abs(t['side'])>2.7 for t in trees))
            self.assertTrue(all(t['side']<LAKE_EDGE or trail_fraction(t['station'])>.5 for t in trees))
            self.assertTrue(all(t['kind'] in TREE_MODELS for t in trees))
            self.assertLessEqual(len(trees),300)

    def test_private_track_leaves_a_separate_continuing_public_road(self):
        for arrival in (DEFAULT_ARRIVAL,1750):
            junction=junction_station(arrival)
            self.assertAlmostEqual(road_x(junction,arrival),main_road_x(junction))
            self.assertGreater(main_road_x(arrival)-road_x(arrival,arrival),140)
            self.assertLess(main_road_height(arrival),road_height(arrival,arrival)-15)
            for s in np.arange(junction+20,arrival+120,9):
                side=main_side_on_section(s,0,arrival)
                ms,offset=main_coordinates(*terrain_point(s,side,arrival))
                self.assertLess(abs(offset),.001)
                self.assertLess(bank_height(s,side,arrival),main_road_height(ms)+.015)

    def test_shore_has_bays_and_broad_slopes_and_rivers_reach_the_lake(self):
        shores=[shore_distance(s) for s in range(0,1100,3)]
        self.assertGreater(max(shores)-min(shores),10)
        self.assertGreater(min(shores),6)
        for s in range(0,1100,31):
            if min(abs(s-b) for b in BRIDGES)<25:continue
            self.assertGreater(bank_height(s,4),LAKE_HEIGHT)
            self.assertLess(abs(bank_height(s,shore_distance(s))-LAKE_HEIGHT),.20)
        for bridge in BRIDGES:
            for side in (-60,-30,-10,0,10,20,35):
                self.assertLess(bank_height(river_station(bridge,side),side),river_height(side)-.3)

    def test_looking_back_retains_trees_hundreds_of_metres_behind(self):
        self.assertGreaterEqual(DRAW_BEHIND,250);self.assertGreaterEqual(DRAW_AHEAD,250)
        for distance in (400,700,1000):
            trees=list(scenery(distance))
            self.assertGreater(sum(t['z']>150 for t in trees),20)

    def test_mountains_stay_bounded_and_span_both_sides_of_the_lake(self):
        for distance in (0,200,700,1e6):
            values=list(ridges(distance));self.assertEqual(len(values),18)
            self.assertEqual({m['layer'] for m in values},{0,1,2})
            self.assertTrue(all(np.isfinite(m['position']).all() for m in values))
            self.assertTrue(all(m['position'][1]<LAKE_HEIGHT for m in values))
            self.assertEqual(values,list(ridges(distance)))

    def test_mountain_mesh_edges_reach_the_submerged_base(self):
        for name in ('ridge_a','ridge_b','ridge_c'):
            doc,blob=mesh_data(name)
            xyz=np.concatenate([accessor(doc,blob,p['attributes']['POSITION']) for m in doc['meshes'] for p in m['primitives']])
            rim=xyz[(np.abs(xyz[:,0])>.999)|(np.abs(xyz[:,2])>.999)]
            self.assertGreater(len(rim),100)
            self.assertLess(float(rim[:,1].max()),1e-6,'Open elevated mountain edge')

    def test_final_approach_leaves_the_inhabited_stretch_behind(self):
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
        centre=vertices[np.abs(vertices[:,0])<5.5]
        for step in range(STAIR_COUNT):
            y=(step+1)*STAIR_RISE;z=stair_z(step)
            self.assertTrue(np.any((abs(centre[:,1]-y)<.001)&(abs(centre[:,2]-z)<.23)))
        self.assertGreater(vertices[:,1].max(),20.)
        self.assertGreater(vertices[:,0].max()-vertices[:,0].min(),65.)
        self.assertGreaterEqual(STAIR_COUNT,50)

    def test_rivers_continue_beyond_the_full_visibility_radius(self):
        self.assertGreater(-RIVER_UPSTREAM,DRAW_AHEAD+150)
        self.assertGreater(RIVER_DOWNSTREAM,shore_distance(BRIDGES[0])+40)
        for bridge in BRIDGES:
            for side in range(RIVER_UPSTREAM,0,11):
                self.assertLess(main_bank_height(river_station(bridge,side),side),river_height(side)-.3)

    def test_temple_has_depth_and_uint16_safe_batches(self):
        doc,blob=mesh_data('temple_halls');parts=[]
        for mesh in doc['meshes']:
            for p in mesh['primitives']:
                self.assertEqual(doc['accessors'][p['indices']]['componentType'],5123)
                parts.append(accessor(doc,blob,p['attributes']['POSITION']))
        xyz=np.concatenate(parts)
        self.assertGreater(xyz[:,1].max(),35)
        self.assertLess(xyz[:,2].min(),-110)
        self.assertGreater(np.ptp(xyz[:,0]),65)

    def test_distant_hills_never_project_onto_unrelated_road_bends(self):
        for station in range(1200,1800,3):
            for side in (-180,-140,-84,-38,54,140,220):
                point=terrain_point(station,side)
                projected,_=main_coordinates(*point)
                self.assertLess(abs(projected+point[1]),30)
                self.assertLess(bank_height(station,side),110)


if __name__=='__main__':unittest.main()
