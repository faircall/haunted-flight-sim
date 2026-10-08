"""Budgets, embedded texture sheets and renderable exported Santana geometry."""
from io import BytesIO
from collections import defaultdict,Counter
import json
from pathlib import Path
import struct
import unittest
import numpy as np
from PIL import Image
from test_temple_living import accessor
from g_santana_geometry import (AXLES,WHEEL_Y,ACTOR_SCALE,actor_point,roof_height,roof_rim,
                                window_panes,wiper_pose,WIPER_PIVOTS,inside_cabin,
                                CABIN_EYE,REFERENCE_SIDE,REAR_BODY_END,TRUNK_START)

KIT=Path(__file__).resolve().parent/'art'/'temple'/'intro'
PARTS={'sedan_exterior':1,'sedan':1,'headlamps':1,'tyre':4,'steering':1}
INTERIOR_PARTS={'sedan_interior':1,'cabin_fittings':1,'steering_interior':1}


def glb(name):
    raw=(KIT/(name+'.glb')).read_bytes()
    magic,version,size=struct.unpack_from('<III',raw)
    assert (magic,version,size)==(0x46546c67,2,len(raw))
    length,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
    document=json.loads(raw[20:20+length]);offset=20+length
    count,kind=struct.unpack_from('<II',raw,offset);assert kind==0x004e4942
    return document,raw[offset+8:offset+8+count]


def intersections(points,origin,direction):
    a,b,c=points.transpose(1,0,2);ab=b-a;ac=c-a
    h=np.cross(direction,ac);det=np.einsum('ij,ij->i',ab,h)
    inv=np.divide(1.,det,out=np.zeros_like(det),where=np.abs(det)>1e-9)
    s=origin-a;u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,ab)
    v=np.einsum('j,ij->i',direction,q)*inv;t=np.einsum('ij,ij->i',ac,q)*inv
    return t[(np.abs(det)>1e-9)&(u>=0)&(v>=0)&(u+v<=1)&(t>=0)]


class SantanaTests(unittest.TestCase):
    def assert_side_is_opaque(self,points,sign,y,z,label):
        hits=intersections(points,np.array((sign*1.12,y,z)),np.array((-sign,0,0)))
        self.assertTrue((hits<.48).any(),(label,sign,y,z))

    def test_center_door_frames_close_the_gap_to_the_beltline(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        points=xyz[accessor(doc,binary,p['indices']).reshape(-1,3)]
        for sign in (-1,1):
            panes=window_panes();front=np.asarray(panes[1+(2 if sign==1 else 0)][0])
            rear=np.asarray(panes[2+(2 if sign==1 else 0)][0])
            for height in (-.015,.04,.25,.55,.82,.96):
                a=front[1]*(1-height)+front[2]*height;b=rear[0]*(1-height)+rear[3]*height
                for across in (.06,.28,.50,.73,.94):
                    sample=a*(1-across)+b*across
                    self.assert_side_is_opaque(points,sign,sample[1],sample[2],'Daylight beside B-post')

    def test_rear_quarters_fill_the_section_between_the_two_windows(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        points=xyz[accessor(doc,binary,p['indices']).reshape(-1,3)]
        panes=window_panes();back=np.asarray(panes[-1][0])
        for sign in (-1,1):
            side=np.asarray(panes[2+(2 if sign==1 else 0)][0])
            for height in (.05,.25,.55,.85):
                edge=side[1]*(1-height)+side[2]*height;y=edge[1]
                back_fraction=(y-back[0,1])/(back[3,1]-back[0,1])
                back_z=back[0,2]*(1-back_fraction)+back[3,2]*back_fraction
                for across in (.25,.55,.85):
                    z=edge[2]*(1-across)+back_z*across
                    self.assert_side_is_opaque(points,sign,y,z,'Open rear quarter section')

    def test_first_person_version_has_an_independent_complete_interior_budget(self):
        manifest=json.loads((KIT/'manifest.json').read_text());interior=manifest['car']['interior'];total=0
        self.assertEqual(set(interior['models']),set(INTERIOR_PARTS))
        for name in INTERIOR_PARTS:
            doc,binary=glb(name)
            triangles=sum(len(accessor(doc,binary,p['indices']))//3 for m in doc['meshes'] for p in m['primitives'])
            self.assertEqual(triangles,manifest['models'][name]['triangles'],name);total+=triangles
        self.assertEqual(total,interior['triangles'])
        self.assertEqual(interior['budget'],[12000,15000])
        self.assertTrue(12000<=total<=15000,total)
        self.assertEqual(sum(interior['features'].values()),manifest['models']['cabin_fittings']['triangles'])
        self.assertEqual(interior['editable_source'],'santana_interior.blend')

    def test_complete_vehicle_budget_counts_four_wheels_and_agrees_with_exports(self):
        manifest=json.loads((KIT/'manifest.json').read_text());total=0
        for name,copies in PARTS.items():
            doc,binary=glb(name)
            triangles=sum(len(accessor(doc,binary,p['indices']))//3
                          for m in doc['meshes'] for p in m['primitives'])
            self.assertEqual(triangles,manifest['models'][name]['triangles'],name)
            total+=triangles*copies
        self.assertEqual(total,manifest['car']['triangles'])
        self.assertEqual(manifest['car']['wheel_instances'],4)
        self.assertEqual(manifest['car']['glass_triangles'],12)
        self.assertEqual(manifest['car']['budget'],[18000,22000])
        self.assertTrue(18000<=total<=22000,total)

    def test_front_and_rear_pillar_tops_fit_beneath_the_roof_profile(self):
        doc,binary=glb('sedan_exterior')
        xyz=np.concatenate([accessor(doc,binary,p['attributes']['POSITION'])
                            for mesh in doc['meshes'] for p in mesh['primitives']])
        # Include the roof corners as well as pillar returns: no opaque corner
        # may project above the crown or out past its gutter at the same height.
        corners=xyz[(xyz[:,1]>1.41)&(np.abs(xyz[:,2])>.35)]
        for x,y,z in corners:
            self.assertLessEqual(float(y),roof_height(float(x),float(z))+.009,
                                 ('Pillar projects above roof',(float(x),float(y),float(z))))
            t=max(0.,min(1.,(float(z)-roof_rim(1,0)[2])/(roof_rim(1,1)[2]-roof_rim(1,0)[2])))
            width=roof_rim(1,t)[0]
            self.assertLessEqual(abs(float(x)),float(width)+.022,
                                 ('Pillar projects beyond gutter',(float(x),float(y),float(z))))

    def test_roof_is_a_closed_shell_with_consistent_outward_winding(self):
        # Exported UV/normal seams duplicate vertices. Weld positions first,
        # then find the connected roof containing the car's highest vertex.
        doc,binary=glb('sedan_exterior');primitive=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,primitive['attributes']['POSITION'])
        indices=accessor(doc,binary,primitive['indices']).reshape(-1,3)
        vertices,weld=np.unique(np.round(xyz,6),axis=0,return_inverse=True)
        triangles=weld[indices];edges=defaultdict(list)
        for face,tri in enumerate(triangles):
            for a,b in zip(tri,np.roll(tri,-1)):
                edges[tuple(sorted((int(a),int(b))))].append(face)
        seed=int(np.where(triangles==vertices[:,1].argmax())[0][0])
        connected={seed};todo=[seed]
        while todo:
            tri=triangles[todo.pop()]
            for a,b in zip(tri,np.roll(tri,-1)):
                for neighbour in edges[tuple(sorted((int(a),int(b))))]:
                    if neighbour not in connected:connected.add(neighbour);todo.append(neighbour)
        uses=Counter();winding=Counter()
        for face in connected:
            tri=triangles[face]
            for a,b in zip(tri,np.roll(tri,-1)):
                edge=tuple(sorted((int(a),int(b))))
                uses[edge]+=1;winding[edge]+=1 if a<b else -1
        self.assertGreater(len(connected),500)
        self.assertEqual(set(uses.values()),{2},'Roof has an open or non-manifold seam')
        self.assertEqual(set(winding.values()),{0},'Roof faces disagree at a join')
        points=vertices[triangles[list(connected)]]
        volume=np.einsum('ij,ij->i',points[:,0],np.cross(points[:,1],points[:,2])).sum()/6
        self.assertGreater(volume,.05,'Roof normals must point out of the closed shell')
        roof_points=points.reshape(-1,3)
        glass_width=2*max(abs(p[0]) for pane,_ in window_panes() for p in pane if p[1]>1.40)
        self.assertAlmostEqual(float(np.ptp(roof_points[:,0])),glass_width,delta=.025)
        self.assertGreater(float(np.ptp(roof_points[:,2])),1.50)
        # A sealed crown can still leave daylight above its windows. Rays aimed
        # just above each glazing top must meet the nearby header/gutter, rather
        # than travelling across the empty cabin to the opposite side.
        a,b,c=points.transpose(1,0,2);ab=b-a;ac=c-a
        for pane,_ in window_panes():
            pane=np.asarray(pane);middle=pane.mean(axis=0)
            outward=np.zeros(3);axis=0 if abs(middle[0])>.4 else 2
            outward[axis]=np.sign(middle[axis]);direction=-outward
            h=np.cross(direction,ac);det=np.einsum('ij,ij->i',ab,h)
            inv=np.divide(1.,det,out=np.zeros_like(det),where=np.abs(det)>1e-9)
            for fraction in np.linspace(.08,.92,7):
                edge=pane[3]*(1-fraction)+pane[2]*fraction
                for lift in (.006,.012):
                    origin=edge+outward*.30+np.array((0,lift,0))
                    s=origin-a;u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,ab)
                    v=np.einsum('j,ij->i',direction,q)*inv;t=np.einsum('ij,ij->i',ac,q)*inv
                    hit=(np.abs(det)>1e-9)&(u>=0)&(v>=0)&(u+v<=1)&(t>=0)&(t<.34)
                    self.assertTrue(hit.any(),('Daylight above glazing',edge,lift))

    def test_car_proportions_follow_the_reference_independently_of_occupants(self):
        def positions(name):
            d,b=glb(name)
            return np.concatenate([accessor(d,b,p['attributes']['POSITION']) for m in d['meshes'] for p in m['primitives']])
        body=positions('sedan_exterior');length=float(np.ptp(body[:,2]))
        tyre=positions('tyre');height=float(body[:,1].max()-(WHEEL_Y+tyre[:,1].min()))
        # Mirrors sit above the beltline; measure the actual painted body/bumper.
        width=float(np.ptp(body[body[:,1]<.99,0]))
        # The shorter rear deck follows the latest side-profile correction;
        # cabin height/width stay independent of this reduced overall length.
        self.assertTrue(4.10<length<4.20,length)
        self.assertAlmostEqual(height/length,REFERENCE_SIDE['car_height_px']/REFERENCE_SIDE['length_px'],delta=.018)
        self.assertTrue(1.70<width<1.80,width)
        self.assertAlmostEqual((AXLES[1]-AXLES[0])/length,
            REFERENCE_SIDE['wheelbase_px']/REFERENCE_SIDE['length_px'],delta=.015)
        roof=body[body[:,1]>1.425]
        self.assertAlmostEqual(float(np.ptp(roof[:,2]))/length,
            REFERENCE_SIDE['roof_px']/REFERENCE_SIDE['length_px'],delta=.035)
        front=np.asarray(window_panes()[1][0])
        self.assertAlmostEqual(float(np.ptp(front[:,1]))/height,
            REFERENCE_SIDE['glass_height_px']/REFERENCE_SIDE['car_height_px'],delta=.04)
        # The broad cabin is no longer a roof-sized glass box.
        self.assertLess(float(np.ptp(front[:,1])),.425)
        rear_window_end=max(p[2] for p in window_panes()[2][0])
        self.assertTrue(0<=AXLES[1]-rear_window_end<=.09,'Rear wheel sits behind the side window')
        self.assertTrue(.77<float(body[:,2].max())-AXLES[1]<.84,'Rear overhang is too long')
        self.assertTrue(.45<REAR_BODY_END-TRUNK_START<.50,'Trunk deck is too long')
        self.assertAlmostEqual(float(np.ptp(tyre[:,1]))/height,
            REFERENCE_SIDE['wheel_diameter_px']/REFERENCE_SIDE['car_height_px'],delta=.020)
        post=(front[1,2]+window_panes()[2][0][0][2])/2
        self.assertAlmostEqual((post-AXLES[0])/(AXLES[1]-AXLES[0]),
            (REFERENCE_SIDE['center_post_px']-REFERENCE_SIDE['front_axle_px'])/REFERENCE_SIDE['wheelbase_px'],delta=.025)
        # Check the exported wheel-well crown, as well as the runtime anchor.
        arch=body[(np.abs(body[:,1]-(WHEEL_Y+.407))<1e-5)&
                  (np.abs(body[:,0])>.80)&(body[:,2]>.5)]
        self.assertGreater(len(arch),0)
        self.assertTrue(np.all(np.abs(arch[:,2]-AXLES[1])<1e-5),'Rear wheel and well do not line up')

    def test_trunk_lid_is_nearly_level_in_the_export(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        triangles=xyz[accessor(doc,binary,p['indices']).reshape(-1,3)]
        heights=[]
        for z in np.linspace(TRUNK_START+.07,REAR_BODY_END-.06,9):
            hits=intersections(triangles,np.array((0,2,z)),np.array((0,-1,0)))
            self.assertGreater(len(hits),0,'Missing trunk lid')
            heights.append(2-float(hits.min()))
        self.assertLess(max(heights)-min(heights),.006,'Trunk lid slopes down instead of remaining flat')
        self.assertTrue(1.015<min(heights)<1.030,heights)

    def test_glazing_headers_have_no_daylight_from_oblique_exterior_angles(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        triangles=xyz[accessor(doc,binary,p['indices']).reshape(-1,3)]
        for pane,_ in window_panes():
            pane=np.asarray(pane);middle=pane.mean(axis=0)
            axis=0 if abs(middle[0])>.4 else 2
            for fraction in np.linspace(.01,.99,9):
                edge=pane[3]*(1-fraction)+pane[2]*fraction
                for lift in (.002,.012):
                    for elevation in (.2,1.1):
                        for skew in (-.45,.45):
                            outward=np.zeros(3);outward[axis]=np.sign(middle[axis])
                            outward[2-axis]=skew;outward[1]=elevation;outward/=np.linalg.norm(outward)
                            origin=edge+np.array((0,lift,0))+.3*outward
                            hits=intersections(triangles,origin,-outward)
                            self.assertTrue((hits<.315).any(),('Open glazing/header join',edge,lift,elevation,skew))

    def test_cabin_floor_is_hidden_behind_sills_and_above_the_pan(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        body=xyz[accessor(doc,binary,p['indices']).reshape(-1,3)]
        for name in ('sedan','sedan_interior'):
            d,b=glb(name);p=d['meshes'][0]['primitives'][0]
            xyz=accessor(d,b,p['attributes']['POSITION']);floor=xyz[xyz[:,1]<.22]
            self.assertGreater(len(floor),0)
            # Check actual exported floor corners, just inside their boundary.
            for x,y,z in np.unique(floor,axis=0):
                z+=.001 if z<0 else -.001
                for sign in (-1,1):
                    hits=intersections(body,np.array((sign*1.1,y,z)),np.array((-sign,0,0)))
                    self.assertTrue((hits<1.1-abs(x)).any(),('Floor visible beyond sill',name,x,y,z))
                hits=intersections(body,np.array((x,-.1,z)),np.array((0,1,0)))
                self.assertTrue((hits<y+.1).any(),('Floor visible beneath pan',name,x,y,z))

    def test_rear_door_upper_rubber_border_stays_visible_below_the_roof(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION'])
        uv=accessor(doc,binary,p['attributes']['TEXCOORD_0'])
        indices=accessor(doc,binary,p['indices']).reshape(-1,3)
        a,b,c=xyz[indices].transpose(1,0,2);ab=b-a;ac=c-a
        face_uv=uv[indices].mean(axis=1)
        for pane_index in (2,4):
            pane=np.asarray(window_panes()[pane_index][0]);sign=np.sign(pane[0,0])
            # The supplied screenshot camera and two nearby viewing angles.
            for x,y,z in ((1.56,1.47,.21),(2.,1.58,.40),(2.,1.45,.10)):
                origin=np.array((sign*x,y,z))
                for fraction in np.linspace(.06,.94,15):
                    edge=pane[3]*(1-fraction)+pane[2]*fraction
                    for lift in (.002,.006,.010):
                        direction=edge+np.array((0,lift,0))-origin
                        distance=np.linalg.norm(direction);direction/=distance
                        h=np.cross(direction,ac);det=np.einsum('ij,ij->i',ab,h)
                        inv=np.divide(1.,det,out=np.zeros_like(det),where=det>1e-9)
                        s=origin-a;u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,ab)
                        v=np.einsum('j,ij->i',direction,q)*inv;t=np.einsum('ij,ij->i',ac,q)*inv
                        hits=np.where((det>1e-9)&(u>=0)&(v>=0)&(u+v<=1)&(t>=0))[0]
                        self.assertGreater(len(hits),0,'Missing upper window trim')
                        first=hits[t[hits].argmin()];u,v=face_uv[first]
                        # No-daylight tests also pass when paint covers the
                        # gasket. The first visible face must use black rubber.
                        self.assertTrue(u>224/256 and 160/256<v<192/256,
                            ('Roof hides rear door trim',pane_index,fraction,lift,origin.tolist()))
                        self.assertLess(abs(t[first]-distance),.025,'Ray passed through the near trim')

    def test_bumpers_wrap_both_corners_with_closed_outward_surfaces(self):
        doc,binary=glb('sedan_exterior');p=doc['meshes'][0]['primitives'][0]
        xyz=accessor(doc,binary,p['attributes']['POSITION']);uv=accessor(doc,binary,p['attributes']['TEXCOORD_0'])
        indices=accessor(doc,binary,p['indices']).reshape(-1,3)
        patch=(uv[:,0]<96/256)&(uv[:,1]>160/256)&(uv[:,1]<192/256)
        for rear in (False,True):
            end_zone=xyz[:,2]>1.40 if rear else xyz[:,2]<-2.03
            points=xyz[indices[(patch&end_zone)[indices].all(axis=1)]]
            # The side rubbing strips also use this atlas region, but belong
            # to separate connected surfaces. Start at the end-most face.
            vertices,weld=np.unique(np.round(points.reshape(-1,3),6),axis=0,return_inverse=True)
            faces=weld.reshape(-1,3);edges=defaultdict(list)
            for i,tri in enumerate(faces):
                for a,b in zip(tri,np.roll(tri,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
            end=int(vertices[:,2].argmax() if rear else vertices[:,2].argmin())
            seed=int(np.where(faces==end)[0][0]);connected={seed};todo=[seed]
            while todo:
                tri=faces[todo.pop()]
                for a,b in zip(tri,np.roll(tri,-1)):
                    for neighbour in edges[tuple(sorted((int(a),int(b))))]:
                        if neighbour not in connected:connected.add(neighbour);todo.append(neighbour)
            uses=Counter();winding=Counter()
            for face in connected:
                for a,b in zip(faces[face],np.roll(faces[face],-1)):
                    key=tuple(sorted((int(a),int(b))));uses[key]+=1;winding[key]+=1 if a<b else -1
            self.assertEqual(set(uses.values()),{2},'Open bumper skin')
            self.assertEqual(set(winding.values()),{0},'Inverted bumper return')
            bumper=vertices[faces[list(connected)]]
            volume=np.einsum('ij,ij->i',bumper[:,0],np.cross(bumper[:,1],bumper[:,2])).sum()/6
            self.assertGreater(volume,0.)
            self.assertGreater(float(np.ptp(bumper[:,:,2])),.38 if rear else .24,'Bumper ends as a separate bar')
            for sign in (-1,1):
                side=bumper.reshape(-1,3);side=side[side[:,0]*sign>.83]
                self.assertGreater(float(np.ptp(side[:,2])),.25 if rear else .13,'Missing side return')

    def test_uniformly_resized_seated_actors_fit_the_finished_car(self):
        for name,rear in (('player_seated',True),('driver',False),('colleague',False)):
            d,b=glb(name)
            p=np.concatenate([accessor(d,b,a['attributes']['POSITION']) for m in d['meshes'] for a in m['primitives']])
            points=np.asarray([actor_point(v,rear) for v in p])
            if rear:
                head=points[points[:,1].argmax()]
            else:
                d,b=glb(name+'_head')
                top=max(float(accessor(d,b,a['attributes']['POSITION'])[:,1].max()) for m in d['meshes'] for a in m['primitives'])
                head=actor_point((-.45 if name=='driver' else .45,1.405+top,-.36))
            self.assertTrue(inside_cabin(head),(name,head))
            self.assertLess(head[1],roof_height(head[0],head[2])-.075)
            self.assertGreater(float(points[:,1].min()),.21,name)
        self.assertEqual(ACTOR_SCALE,.88)

    def test_wipers_remain_on_the_new_sloping_windshield(self):
        panes=window_panes();self.assertEqual(len(panes),6)
        self.assertEqual(sum(flag for _,flag in panes),1)
        a,b,c=np.asarray(panes[0][0][:3]);normal=np.cross(b-a,c-a);normal/=np.linalg.norm(normal)
        for x in WIPER_PIVOTS:
            for angle in np.linspace(np.radians(8),np.radians(102),31):
                pivot,tip,offset=wiper_pose(x,angle)
                for p in (pivot,tip,np.array(tip)+offset,np.array(tip)-offset):
                    self.assertLess(abs(float(np.dot(np.array(p)-a,normal))),.035)

    def test_editor_camera_classification_uses_sloping_glass_and_lower_roof(self):
        self.assertTrue(inside_cabin(CABIN_EYE))
        self.assertTrue(inside_cabin((-.42,.78,-.30)))
        for pose in ((0,1.46,.65),(.810,1.35,.6),(0,1.34,-1.0),(0,1.30,1.10)):
            self.assertFalse(inside_cabin(pose),pose)

    def test_dedicated_sheets_are_small_portable_and_match_embedded_pixels(self):
        manifest=json.loads((KIT/'manifest.json').read_text())
        self.assertEqual(manifest['car']['atlases'],dict(santana_exterior=[256,256],
            santana_interior=[256,256],santana_wheels=[128,128]))
        atlases={**manifest['car']['atlases'],**manifest['car']['interior']['atlases']}
        self.assertEqual(manifest['car']['interior']['atlases'],dict(santana_cabin=[256,256],santana_cabin_details=[256,256]))
        for name in {**PARTS,**INTERIOR_PARTS}:
            doc,binary=glb(name);atlas=manifest['models'][name]['atlas']
            self.assertEqual(len(doc['images']),1)
            self.assertNotIn('uri',doc['images'][0])
            view=doc['bufferViews'][doc['images'][0]['bufferView']]
            start=view.get('byteOffset',0);end=start+view['byteLength']
            with Image.open(BytesIO(binary[start:end])) as embedded,Image.open(KIT/(atlas+'.png')) as source:
                self.assertEqual(list(embedded.size),atlases[atlas])
                self.assertEqual(embedded.convert('RGBA').tobytes(),source.convert('RGBA').tobytes())
            self.assertEqual(doc['samplers'][0]['magFilter'],9728)

    def test_triangles_are_non_degenerate_and_atlas_coordinates_are_in_bounds(self):
        for name in {**PARTS,**INTERIOR_PARTS}:
            doc,binary=glb(name)
            for mesh in doc['meshes']:
                for p in mesh['primitives']:
                    attrs=p['attributes'];positions=accessor(doc,binary,attrs['POSITION'])
                    uv=accessor(doc,binary,attrs['TEXCOORD_0']);normals=accessor(doc,binary,attrs['NORMAL'])
                    indices=accessor(doc,binary,p['indices']).reshape(-1,3)
                    self.assertTrue(np.isfinite(positions).all(),name)
                    self.assertTrue(np.isfinite(normals).all(),name)
                    self.assertTrue(np.isfinite(uv).all() and (uv>=0).all() and (uv<=1).all(),name)
                    self.assertLess(int(indices.max()),len(positions),name)
                    a,b,c=positions[indices].transpose(1,0,2)
                    area=np.linalg.norm(np.cross(b-a,c-a),axis=1)
                    self.assertTrue((area>1e-9).all(),(name,float(area.min())))


if __name__=='__main__':unittest.main()
