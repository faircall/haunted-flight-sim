"""Portable contracts for the exported rig, foliage and preserved sprite sources."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct
import unittest

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
KIT=ROOT/'photo_asset_pipeline'/'temple3d'/'living'


def glb(name):
    raw=(KIT/'models'/(name+'.glb')).read_bytes()
    magic,version,size=struct.unpack_from('<III',raw)
    assert magic==0x46546C67 and version==2 and size==len(raw)
    length,kind=struct.unpack_from('<II',raw,12)
    assert kind==0x4E4F534A
    document=json.loads(raw[20:20+length])
    start=20+length
    count,kind=struct.unpack_from('<II',raw,start)
    assert kind==0x004E4942
    binary=raw[start+8:start+8+count]
    return document,binary


def accessor(document,binary,index):
    data=document['accessors'][index]
    view=document['bufferViews'][data['bufferView']]
    dtype={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[data['componentType']]
    components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[data['type']]
    offset=view.get('byteOffset',0)+data.get('byteOffset',0)
    stride=view.get('byteStride',np.dtype(dtype).itemsize*components)
    return np.ndarray((data['count'],components),dtype=dtype,buffer=binary,offset=offset,strides=(stride,np.dtype(dtype).itemsize))


class LivingAssetTests(unittest.TestCase):
    def test_player_has_compact_adult_proportions_and_a_ps1_detail_budget(self):
        document,binary=glb('player')
        skin=document['skins'][0]
        bind=accessor(document,binary,skin['inverseBindMatrices'])
        joints={document['nodes'][index]['name']:np.linalg.inv(value.reshape(4,4).T)[:3,3]
                for index,value in zip(skin['joints'],bind)}
        positions=[];head_positions=[];triangles=0
        head_joint=next(i for i,index in enumerate(skin['joints']) if document['nodes'][index]['name']=='head')
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes']
                vertices=accessor(document,binary,attrs['POSITION'])
                positions.append(vertices)
                weights=accessor(document,binary,attrs['WEIGHTS_0'])
                indices=accessor(document,binary,attrs['JOINTS_0'])
                head_positions.append(vertices[np.any((indices==head_joint)&(weights>.8),axis=1)])
                triangles+=len(accessor(document,binary,primitive['indices']))//3
        positions=np.concatenate(positions)
        height=float(np.max(positions[:,1])-np.min(positions[:,1]))
        # A moderate PS1-era mesh has enough silhouette detail without using
        # geometry density to compensate for a poor low-resolution texture.
        self.assertTrue(1800<=triangles<=5000,triangles)
        self.assertTrue(25.5<height<27.,height)
        self.assertTrue(.46<joints['root'][1]/height<.51)
        # A larger head and slimmer shoulders keep the reference character's
        # compact silhouette while preserving human limb proportions.
        head=np.concatenate(head_positions)
        self.assertTrue(.15<np.ptp(head[:,1])/height<.19)
        self.assertTrue(1.5<(joints['arm.R'][0]-joints['arm.L'][0])/np.ptp(head[:,0])<2.2)
        for side in ('L','R'):
            thigh=np.linalg.norm(joints['thigh.'+side]-joints['shin.'+side])
            shin=np.linalg.norm(joints['shin.'+side]-joints['foot.'+side])
            self.assertTrue(.95<thigh/shin<1.05,(side,thigh,shin))
            self.assertTrue(.42<(thigh+shin)/height<.47)
            shoulder=joints['arm.'+side];wrist=joints['hand.'+side]
            self.assertTrue(.095<abs(shoulder[0])/height<.125)
            self.assertTrue(.30<(shoulder[1]-wrist[1])/height<.35)

    def test_embedded_player_atlas_has_the_requested_costume_palette(self):
        document,binary=glb('player')
        image=document['images'][0];view=document['bufferViews'][image['bufferView']]
        offset=view.get('byteOffset',0)
        atlas=Image.open(BytesIO(binary[offset:offset+view['byteLength']])).convert('RGB')
        self.assertEqual(atlas.size,(256,256))
        rgb=np.asarray(atlas,dtype=np.float32).reshape(-1,3)
        r,g,b=rgb.T
        colors={
            'blue shirtjacket':(b>r*1.15)&(b>g*1.04)&(b>40),
            'brown pants and shoes':(r>g*1.15)&(g>b*1.12)&(r>35)&(r<160),
            'white t-shirt':(np.min(rgb,axis=1)>170)&(np.ptp(rgb,axis=1)<35),
            'warm skin':(r>145)&(g>85)&(g<200)&(b>55)&(b<165)&(r>g+15)&(g>b+8),
            'dark hair':np.max(rgb,axis=1)<60,
        }
        for label,mask in colors.items():
            self.assertGreater(np.count_nonzero(mask),128,label)

    def test_neck_has_substantial_width_relative_to_the_portrait_head(self):
        from photo_asset_pipeline.temple3d.living.player_texture import PANELS
        document,binary=glb('player')
        names=[document['nodes'][node]['name'] for node in document['skins'][0]['joints']]
        head_id=names.index('head');spine_id=names.index('spine');heads=[];necks=[]
        x0,y0,x1,y1=PANELS['skin']
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes'];vertices=accessor(document,binary,attrs['POSITION'])
                joints=accessor(document,binary,attrs['JOINTS_0']);weights=accessor(document,binary,attrs['WEIGHTS_0'])
                uv=accessor(document,binary,attrs['TEXCOORD_0'])*256
                heads.append(vertices[np.any((joints==head_id)&(weights>.8),axis=1)])
                skin=(uv[:,0]>x0)&(uv[:,0]<x1)&(uv[:,1]>y0)&(uv[:,1]<y1)
                neck=skin&np.any(np.isin(joints,[head_id,spine_id])&(weights>.01),axis=1)
                necks.append(vertices[neck])
        head=np.concatenate(heads);neck=np.concatenate(necks)
        # The same head silhouette must sit on a wider neck even when the
        # jacket and shoulders are tapered independently.
        self.assertTrue(.50<np.ptp(neck[:,0])/np.ptp(head[:,0])<.75)

    def test_white_tee_stays_on_the_front_torso_and_out_of_jacket_panels(self):
        from photo_asset_pipeline.temple3d.living.player_texture import PANELS
        document,binary=glb('player');image=document['images'][0]
        skin=document['skins'][0]
        root_joint=next(i for i,node in enumerate(skin['joints']) if document['nodes'][node]['name']=='root')
        pelvis_height=np.linalg.inv(accessor(document,binary,skin['inverseBindMatrices'])[root_joint].reshape(4,4).T)[1,3]
        view=document['bufferViews'][image['bufferView']];offset=view.get('byteOffset',0)
        atlas=np.asarray(Image.open(BytesIO(binary[offset:offset+view['byteLength']])).convert('RGB'))
        for name in ('jacket_front','jacket_back','sleeve','collar'):
            x0,y0,x1,y1=PANELS[name];rgb=atlas[y0:y1,x0:x1].astype(float)
            ivory=(np.min(rgb,axis=2)>170)&(np.ptp(rgb,axis=2)<35)
            self.assertFalse(np.any(ivory),name+' samples the white tee')
        tee_keys=set();other_keys=set();tee_edges={};other_edges=set()
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes'];uv=accessor(document,binary,attrs['TEXCOORD_0'])*256
                positions=accessor(document,binary,attrs['POSITION'])
                x0,y0,x1,y1=PANELS['tee']
                tee=(uv[:,0]>x0)&(uv[:,0]<x1)&(uv[:,1]>y0)&(uv[:,1]<y1)
                for triangle in accessor(document,binary,primitive['indices']).reshape(-1,3):
                    vertices=positions[triangle];key=tuple(sorted(tuple(p.round(5)) for p in vertices))
                    if np.all(tee[triangle]):
                        tee_keys.add(key)
                        self.assertGreater(float(vertices[:,2].mean()),.4,'Tee appeared on the side or back')
                        self.assertGreater(float(vertices[:,1].min()),pelvis_height,'White tee extended below the pelvis')
                        for a,b in zip(key,key[1:]+key[:1]):
                            edge=tuple(sorted((a,b)));tee_edges[edge]=tee_edges.get(edge,0)+1
                    else:
                        other_keys.add(key)
                        other_edges.update(tuple(sorted((a,b))) for a,b in zip(key,key[1:]+key[:1]))
        self.assertGreater(len(tee_keys),6,'The tee has no integrated front torso surface')
        self.assertFalse(tee_keys&other_keys,'Separate tee and jacket faces overlap')
        boundary={edge for edge,count in tee_edges.items() if count==1}
        self.assertGreater(len(boundary),6,'The tee became a disconnected closed garment layer')
        self.assertTrue(boundary<=other_edges,'The tee border no longer shares the jacket surface')

    def test_source_art_is_preserved_and_textures_have_crisp_alpha(self):
        record=json.loads((KIT/'sources.json').read_text())
        for item in record['sources']:
            self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['sha256'])
        for file in (KIT/'textures').glob('*.png'):
            alpha=np.asarray(Image.open(file).convert('RGBA'))[:,:,3]
            self.assertTrue(set(np.unique(alpha)) <= {0,255},file.name)
            if file.stem!='willow_leaves':self.assertTrue(np.all(alpha==255))

    def test_skin_has_valid_weights_and_only_embedded_resources(self):
        document,binary=glb('player')
        count=len(document['skins'][0]['joints'])
        self.assertEqual(count,15)
        names={document['nodes'][index]['name'] for index in document['skins'][0]['joints']}
        self.assertTrue({'foot.L','foot.R','hand.L','hand.R'}<=names)
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes']
                weights=accessor(document,binary,attrs['WEIGHTS_0'])
                joints=accessor(document,binary,attrs['JOINTS_0'])
                self.assertTrue(np.all((joints>=0)&(joints<count)))
                self.assertTrue(np.all(weights>=0))
                np.testing.assert_allclose(weights.sum(axis=1),1.,atol=1e-6)
                self.assertTrue(np.isfinite(accessor(document,binary,attrs['POSITION'])).all())
        for image in document['images']:self.assertIn('bufferView',image)

    def test_shoulders_elbows_and_wrists_have_blended_skin_weights(self):
        document,binary=glb('player')
        ids={document['nodes'][node]['name']:i for i,node in enumerate(document['skins'][0]['joints'])}
        for side in ('L','R'):
            for parent,child in (('root','spine'),('spine','arm.'+side),('arm.'+side,'forearm.'+side),('forearm.'+side,'hand.'+side)):
                shared=0
                for mesh in document['meshes']:
                    for p in mesh['primitives']:
                        w=accessor(document,binary,p['attributes']['WEIGHTS_0'])
                        j=accessor(document,binary,p['attributes']['JOINTS_0'])
                        shared+=np.count_nonzero(np.any((j==ids[parent])&(w>.05),axis=1)&np.any((j==ids[child])&(w>.05),axis=1))
                self.assertGreater(shared,8,(parent,child))

    def test_wrists_animate_independently_of_forearms(self):
        document,binary=glb('player')
        nodes={n['name']:i for i,n in enumerate(document['nodes']) if 'name' in n}
        for animation in document['animations']:
            if animation['name']=='idle':continue
            for side in ('L','R'):
                channels=[c for c in animation['channels'] if c['target']==dict(node=nodes['hand.'+side],path='rotation')]
                self.assertEqual(len(channels),1)
                values=accessor(document,binary,animation['samplers'][channels[0]['sampler']]['output'])
                self.assertGreater(float(np.max(np.ptp(values,axis=0))),.025)

    def test_jacket_shoulders_and_hands_form_one_connected_surface(self):
        document,binary=glb('player')
        names=[document['nodes'][node]['name'] for node in document['skins'][0]['joints']]
        graph={};influences={}
        for mesh in document['meshes']:
            for p in mesh['primitives']:
                a=p['attributes'];positions=accessor(document,binary,a['POSITION'])
                joints=accessor(document,binary,a['JOINTS_0']);weights=accessor(document,binary,a['WEIGHTS_0'])
                # UV/normal seams duplicate vertices in GLB. Weld those copies
                # spatially to inspect surface continuity through the joints.
                keys=[tuple(np.round(v,5)) for v in positions]
                for key,js,ws in zip(keys,joints,weights):
                    graph.setdefault(key,set())
                    influences.setdefault(key,set()).update(names[j] for j,w in zip(js,ws) if w>.05)
                for triangle in accessor(document,binary,p['indices']).reshape(-1,3):
                    for i in triangle:graph[keys[i]].update(keys[j] for j in triangle if j!=i)
        start=next(k for k,v in influences.items() if v=={'spine'})
        visited={start};pending=[start]
        while pending:
            for neighbor in graph[pending.pop()]-visited:
                visited.add(neighbor);pending.append(neighbor)
        connected=set().union(*(influences[k] for k in visited))
        self.assertTrue({'spine','arm.L','arm.R','forearm.L','forearm.R','hand.L','hand.R'}<=connected)

    def test_animation_clips_are_loopable(self):
        document,binary=glb('player')
        self.assertEqual({a['name'] for a in document['animations']},{'idle','walk','run'})
        for animation in document['animations']:
            self.assertTrue(any(len(accessor(document,binary,s['input']))>10 for s in animation['samplers']))
            for sampler in animation['samplers']:
                # Raylib 5.5 applies the last channel's interpolation to the
                # whole bone; constant STEP scale tracks would step rotations.
                self.assertEqual(sampler.get('interpolation','LINEAR'),'LINEAR')
                times=accessor(document,binary,sampler['input'])[:,0]
                values=accessor(document,binary,sampler['output'])
                self.assertGreaterEqual(len(times),2)
                self.assertAlmostEqual(float(times[0]),0.,places=5)
                self.assertTrue(np.all(np.diff(times)>0))
                np.testing.assert_allclose(values[0],values[-1],atol=.001,err_msg=animation['name'])

    def test_willow_is_volumetric_and_encodes_rooted_wind_weights(self):
        document,binary=glb('willow')
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                positions=accessor(document,binary,primitive['attributes']['POSITION'])
                wind=accessor(document,binary,primitive['attributes']['TEXCOORD_1'])
                self.assertGreater(np.ptp(positions[:,0]),60)
                self.assertGreater(np.ptp(positions[:,2]),60)
                self.assertLessEqual(np.max(np.abs(wind[:,0])),1.)
                if 'trunk' in mesh['name']:
                    self.assertTrue(np.all(wind[:,0]<0))
                    ground=np.abs(positions[:,1])<1.
                    self.assertTrue(np.any(ground))
                    self.assertLess(np.max(np.abs(wind[ground,0])),.001)
                else:self.assertTrue(np.all(wind[:,0]>0))


class SurfaceClearanceTests(unittest.TestCase):
    def test_distances_use_triangle_interiors_edges_and_vertices(self):
        from temple_living_smoke import surface_distance
        triangle=np.array([[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]])
        points=np.array([[.25,.25,2.],[2.,0.,0.],[-1.,-1.,0.]])
        np.testing.assert_allclose(surface_distance(points,triangle),[2.,1.,np.sqrt(2)])

    def test_ray_crossings_distinguish_inside_from_nearby_outside(self):
        from temple_living_smoke import points_inside_mesh
        vertices=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                           [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],dtype=float)
        faces=np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                        [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
        np.testing.assert_array_equal(points_inside_mesh(np.array([[0.,0.,0.],[.99,0.,0.],[1.1,0.,0.]]),vertices[faces]),[True,True,False])


if __name__=='__main__':
    unittest.main()
