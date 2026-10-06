"""Budgets, embedded texture sheets and renderable exported Santana geometry."""
from io import BytesIO
import json
from pathlib import Path
import struct
import unittest
import numpy as np
from PIL import Image
from test_temple_living import accessor
from g_santana_geometry import (AXLES,WHEEL_Y,ACTOR_SCALE,actor_point,roof_height,
                                window_panes,wiper_pose,WIPER_PIVOTS,inside_cabin,
                                CABIN_EYE,REFERENCE_SIDE)

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


class SantanaTests(unittest.TestCase):
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
        self.assertEqual(manifest['car']['budget'],12000)
        self.assertTrue(11000<=total<=13000,total)

    def test_car_proportions_follow_the_reference_independently_of_occupants(self):
        def positions(name):
            d,b=glb(name)
            return np.concatenate([accessor(d,b,p['attributes']['POSITION']) for m in d['meshes'] for p in m['primitives']])
        body=positions('sedan_exterior');length=float(np.ptp(body[:,2]))
        tyre=positions('tyre');height=float(body[:,1].max()-(WHEEL_Y+tyre[:,1].min()))
        # Mirrors sit above the beltline; measure the actual painted body/bumper.
        width=float(np.ptp(body[body[:,1]<.99,0]))
        self.assertTrue(4.45<length<4.60,length)
        self.assertTrue(.32<height/length<.35,(height,length))
        self.assertTrue(.37<width/length<.40,(width,length))
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
