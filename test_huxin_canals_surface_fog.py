"""Actual triangle rasterization, nearest-surface ownership and cache assets."""
from pathlib import Path
import json
import math
import struct
import tempfile
import unittest

import numpy as np

from g_huxin_canals_surface_fog import (SurfaceField, bake_surface_field,
    glb_triangles, rasterize_triangles, truncated_distance_transform,
    save_surface_field, load_surface_field)


def write_glb(path,triangles,node=None):
    vertices=np.asarray(triangles,dtype='<f4').reshape(-1,3)
    indices=np.arange(len(vertices),dtype='<u4')
    positions=vertices.tobytes();binary=positions+indices.tobytes()
    document=dict(asset={'version':'2.0'},scenes=[{'nodes':[0]}],nodes=[dict(mesh=0,**(node or {}))],
        meshes=[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
        buffers=[{'byteLength':len(binary)}],
        bufferViews=[{'buffer':0,'byteOffset':0,'byteLength':len(positions)},
                     {'buffer':0,'byteOffset':len(positions),'byteLength':indices.nbytes}],
        accessors=[{'bufferView':0,'componentType':5126,'count':len(vertices),'type':'VEC3'},
                   {'bufferView':1,'componentType':5125,'count':len(indices),'type':'SCALAR'}])
    encoded=json.dumps(document).encode();encoded+=b' '*((-len(encoded))%4)
    data=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))
    data+=struct.pack('<II',len(encoded),0x4e4f534a)+encoded
    data+=struct.pack('<II',len(binary),0x004e4942)+binary
    path.write_bytes(data)


class SurfaceDistanceTests(unittest.TestCase):
    def test_truncated_distance_and_owner_match_brute_force_reference(self):
        shape=(9,11,12);occupancy=np.zeros(shape,dtype=bool)
        owner=np.zeros(shape,dtype=np.uint8)
        seeds=((2,3,4),(6,8,9))
        for i,point in enumerate(seeds):occupancy[point]=True;owner[point]=i+1
        spacing=.5;cap=3.
        distance,labels=truncated_distance_transform(occupancy,owner,spacing,cap)
        coordinates=np.stack(np.indices(shape),axis=-1)
        squared=np.stack([np.sum((coordinates-point)**2,axis=-1) for point in seeds])
        nearest=squared.min(axis=0)
        metres=np.maximum(0,np.sqrt(nearest)*spacing-spacing*math.sqrt(3)*.5)
        expected=np.rint(np.minimum(metres,cap)/cap*255).astype(np.uint8)
        np.testing.assert_array_equal(distance,expected)
        unique=(squared[0]!=squared[1])&(metres<cap)
        np.testing.assert_array_equal(labels[unique],(np.argmin(squared,axis=0)+1)[unique])
        self.assertTrue(np.all(labels[metres>=cap]==0))

    def test_open_wall_gap_is_not_filled_by_bounding_box_raster(self):
        # Two wall wings with a two metre open doorway between them.
        triangles=np.array([
            [[-3,0,0],[-1,0,0],[-1,3,0]],[[-3,0,0],[-1,3,0],[-3,3,0]],
            [[1,0,0],[3,0,0],[3,3,0]],[[1,0,0],[3,3,0],[1,3,0]],
        ],dtype=np.float32)
        spacing=.2;origin=(-4.,-1.,-2.);shape=(41,26,21)
        occupancy=np.zeros((shape[1],shape[2],shape[0]),dtype=bool)
        samples=rasterize_triangles(occupancy,triangles,origin,spacing)
        self.assertGreater(samples,500)
        def occupied(point):
            x,y,z=np.rint((np.asarray(point)-origin)/spacing).astype(int)
            return occupancy[y,z,x]
        self.assertTrue(occupied((-2.,1.,0.)))
        self.assertTrue(occupied((2.,1.,0.)))
        self.assertFalse(occupied((0.,1.,0.)))
        distance,owners=truncated_distance_transform(occupancy,np.zeros_like(occupancy,dtype=np.uint8),spacing,2.)
        field=SurfaceField(origin,spacing,shape,2.,distance,owners,occupancy,(),(),{})
        self.assertGreater(field.sample((0.,1.,0.)).distance,.7)
        self.assertEqual(field.sample((-2.,1.,0.)).distance,0.)
        self.assertEqual(field.sample((100.,0.,0.)).distance,2.)

    def test_atlas_clamps_slice_edges_and_preserves_semantic_channel(self):
        shape=(3,2,4)
        distance=np.arange(24,dtype=np.uint8).reshape(2,4,3)
        owners=(distance%2+1).astype(np.uint8)
        occupancy=(distance%3==0)
        field=SurfaceField((0.,0.,0.),1.,shape,6.,distance,owners,occupancy,('a','b'),(),{})
        data,width,height,columns,rows=field.atlas()
        atlas=np.frombuffer(data,dtype=np.uint8).reshape(height,width,4)
        self.assertEqual((width,height),(columns*5,rows*6))
        for y in range(2):
            tile=atlas[(y//columns)*6:(y//columns+1)*6,(y%columns)*5:(y%columns+1)*5]
            np.testing.assert_array_equal(tile[1:-1,1:-1,0],distance[y])
            np.testing.assert_array_equal(tile[1:-1,1:-1,2],owners[y])
            np.testing.assert_array_equal(tile[0],tile[1])
            np.testing.assert_array_equal(tile[-1],tile[-2])
            np.testing.assert_array_equal(tile[:,0],tile[:,1])
            np.testing.assert_array_equal(tile[:,-1],tile[:,-2])
            self.assertTrue(np.all(tile[:,:,3]==255))


class SurfaceGlbCacheTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='surface-fog-')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)

    def test_glb_node_translation_rotation_scale_are_applied_to_actual_triangles(self):
        path=self.root/'test.glb'
        face=np.array([[[1.,0.,0.],[0.,1.,0.],[0.,0.,0.]]])
        write_glb(path,face,node={'translation':[5.,2.,3.],
            'rotation':[0.,math.sqrt(.5),0.,math.sqrt(.5)],'scale':[2.,3.,4.]})
        triangles=np.concatenate(list(glb_triangles(path)))
        np.testing.assert_allclose(triangles,[[[5.,2.,1.],[5.,5.,3.],[5.,2.,3.]]],atol=1e-6)

    def test_actual_glb_bake_save_load_and_source_hash_guard(self):
        face=[[[0.,0.,0.],[2.,0.,0.],[0.,2.,0.]]]
        write_glb(self.root/'canal_walls.glb',face)
        # Excluded lake water must not expand geometry bounds or the field.
        manifest={'models':{'canal_walls':{'bounds':[[0.,0.,0.],[2.,2.,0.]]},
            'canal_water':{'bounds':[[-100,-1,-100],[100,-1,100]]}},
            'houses':[{'id':'house-1','bounds_corners':[[0.,0.,-.1],[2.,2.,.1]],'foundation_bottom':0.}]}
        (self.root/'canals_manifest.json').write_text(json.dumps(manifest))
        field=bake_surface_field(self.root,spacing=.25,distance_cap=2.,padding=2.)
        self.assertEqual(field.metadata['triangles'],1)
        self.assertLess(max(field.shape),30)
        self.assertEqual(field.sample((.5,.5,0.)).owner,'house-1')
        self.assertEqual(field.sample((.5,.5,0.)).distance,0.)
        path=self.root/'surface_fog.npz';save_surface_field(field,path)
        loaded=load_surface_field(path,verify_sources=True)
        np.testing.assert_array_equal(field.distance,loaded.distance)
        np.testing.assert_array_equal(field.owner,loaded.owner)
        self.assertEqual(field.source_digests,loaded.source_digests)
        self.assertFalse(loaded.distance.flags.writeable)
        # Detect changes to source bytes rather than timestamps alone.
        (self.root/'canal_walls.glb').write_bytes((self.root/'canal_walls.glb').read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'stale'):load_surface_field(path,verify_sources=True)
        self.assertTrue(path.exists())


if __name__=='__main__':unittest.main()
