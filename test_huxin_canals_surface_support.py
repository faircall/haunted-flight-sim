"""Temporary roof-to-water density preserves the actual architectural field."""
import math
import unittest

import numpy as np

from g_huxin_canals_surface_fog import (SurfaceField,build_surface_support,
                                      truncated_distance_transform)


def fixture(roofs=()):
    origin=(-4.,-2.,-4.);spacing=.5;shape=(17,21,17)
    occupied=np.zeros((shape[1],shape[2],shape[0]),dtype=bool)
    labels=np.zeros_like(occupied,dtype=np.uint8)
    for x,y,z,owner in roofs:
        ix,iy,iz=np.rint((np.array((x,y,z))-origin)/spacing).astype(int)
        occupied[iy,iz,ix]=True;labels[iy,iz,ix]=owner
    distance,owners=truncated_distance_transform(occupied,labels,spacing,4.)
    for array in (distance,owners,occupied):array.setflags(write=False)
    return SurfaceField(origin,spacing,shape,4.,distance,owners,occupied,('house-left','house-right'),(),{})


def plane(y,low=-2.,high=2.,owner=1):
    return [(float(x),y,float(z),owner) for x in np.arange(low,high+.01,.5)
            for z in np.arange(low,high+.01,.5)]


def value(field,array,point):
    x,y,z=np.rint((np.array(point)-field.origin)/field.spacing).astype(int)
    return float(array[y,z,x])*field.distance_cap/255.


class SurfaceSupportTests(unittest.TestCase):
    def test_support_bridges_empty_room_without_changing_hollow_source(self):
        field=fixture(plane(5.))
        before=tuple(array.copy() for array in (field.distance,field.owner,field.occupancy))
        self.assertGreater(field.sample((0.,1.,0.)).distance,3.)
        self.assertFalse(field.sample((0.,1.,0.)).occupied)
        support=build_surface_support(field)
        self.assertEqual(value(field,support,(0.,1.,0.)),0.)
        self.assertEqual(value(field,support,(0.,-.5,0.)),0.)
        self.assertGreater(value(field,support,(0.,-1.5,0.)),.3)
        self.assertGreater(value(field,support,(0.,6.5,0.)),.8)
        for array,original in zip((field.distance,field.owner,field.occupancy),before):
            np.testing.assert_array_equal(array,original)
            self.assertFalse(array.flags.writeable)
        self.assertFalse(support.flags.writeable)

    def test_roof_setbacks_do_not_become_one_full_height_box(self):
        field=fixture(plane(3.,-3.,3.)+plane(6.,-1.,1.))
        support=build_surface_support(field)
        self.assertEqual(value(field,support,(2.5,2.,0.)),0.)
        self.assertEqual(value(field,support,(0.,5.,0.)),0.)
        self.assertGreater(value(field,support,(2.5,4.5,0.)),.8)

    def test_unroofed_courtyard_and_separate_house_gap_remain_open(self):
        roof=[p for p in plane(5.,-3.,3.) if abs(p[0])>=2. or abs(p[2])>=2.]
        field=fixture(roof);support=build_surface_support(field)
        self.assertGreater(value(field,support,(0.,2.,0.)),1.4)
        self.assertEqual(value(field,support,(2.5,2.,0.)),0.)
        roof=[p for p in plane(5.,-3.,3.) if abs(p[0])>=2.]
        field=fixture(roof);support=build_surface_support(field)
        self.assertGreater(value(field,support,(0.,2.,0.)),1.4)

    def test_generic_quay_and_submerged_foundation_do_not_fill_the_lake(self):
        for roofs in (plane(.5,owner=0),plane(-1.,owner=1),()):
            with self.subTest(roofs=len(roofs)):
                field=fixture(roofs)
                self.assertTrue(np.all(build_surface_support(field)==255))

    def test_alternate_datum_and_padding_change_only_the_support(self):
        field=fixture(plane(5.))
        shallow=build_surface_support(field,base_y=1.,below=0.)
        self.assertGreater(value(field,shallow,(0.,0.,0.)),.3)
        deep=build_surface_support(field,base_y=1.,below=2.5)
        self.assertEqual(value(field,deep,(0.,-1.5,0.)),0.)
        self.assertTrue(np.all(build_surface_support(field,base_y=6.)==255))
        for kwargs in ({'base_y':math.nan},{'base_y':math.inf},{'below':-1.},{'below':math.inf}):
            with self.assertRaises(ValueError):build_surface_support(field,**kwargs)

    def test_alpha_packing_preserves_every_rgb_byte_and_copies_gutters(self):
        field=fixture(plane(5.));support=build_surface_support(field)
        original,w,h,columns,rows=field.atlas()
        packed,pw,ph,pc,pr=field.atlas(support=support)
        self.assertEqual((w,h,columns,rows),(pw,ph,pc,pr))
        original=np.frombuffer(original,np.uint8).reshape(h,w,4)
        packed=np.frombuffer(packed,np.uint8).reshape(h,w,4)
        np.testing.assert_array_equal(original[:,:,:3],packed[:,:,:3])
        self.assertTrue(np.all(original[:,:,3]==255))
        nx,ny,nz=field.shape;tx,tz=nx+2,nz+2
        for y in range(ny):
            tile=packed[(y//columns)*tz:(y//columns+1)*tz,(y%columns)*tx:(y%columns+1)*tx]
            np.testing.assert_array_equal(tile[1:-1,1:-1,3],support[y])
            np.testing.assert_array_equal(tile[0],tile[1])
            np.testing.assert_array_equal(tile[-1],tile[-2])
            np.testing.assert_array_equal(tile[:,0],tile[:,1])
            np.testing.assert_array_equal(tile[:,-1],tile[:,-2])
        self.assertEqual(field.atlas()[0],original.tobytes())

    def test_invalid_support_is_rejected_before_integer_cast_or_upload(self):
        field=fixture(plane(5.))
        for support in (np.zeros((2,2,2),dtype=np.uint8),
                        np.zeros(field.distance.shape,dtype=np.float32),
                        np.full(field.distance.shape,256,dtype=np.int16),
                        np.full(field.distance.shape,math.nan)):
            with self.assertRaises(ValueError):field.atlas(support=support)


if __name__=='__main__':unittest.main()
