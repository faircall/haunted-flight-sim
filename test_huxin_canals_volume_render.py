"""Pure renderer math: periodic noise, conservative culling and reflections.

Importing the rendering module loads raylib's bindings, but these tests never
create a window, texture, audio device or graphics context.
"""
from dataclasses import replace
import math
from types import SimpleNamespace
import unittest

import numpy as np

from g_huxin_canals_volumes import (default_region_document,
    default_volume_document, settings_from_document, local_point)
from huxin_canals_volumes import noise_lattice, projected_bounds


def camera(position=(0.,0.,0.),target=(0.,0.,1.),fov=60.):
    def vector(values):return SimpleNamespace(**dict(zip(('x','y','z'),values)))
    return SimpleNamespace(position=vector(position),target=vector(target),
                           up=vector((0.,1.,0.)),fovy=fov)


def region(**changes):
    document=default_volume_document()
    document['regions']['test']=default_region_document()
    value=settings_from_document(document).regions[0]
    return replace(value,**changes)


def bilinear(atlas,pixel):
    """Reference normalized texture lookup, expressed in texel coordinates."""
    x,y=pixel
    ix,iy=math.floor(x-.5),math.floor(y-.5)
    fx,fy=x-.5-ix,y-.5-iy
    return ((1.-fy)*((1.-fx)*atlas[iy,ix,:3]+fx*atlas[iy,ix+1,:3])+
            fy*((1.-fx)*atlas[iy+1,ix,:3]+fx*atlas[iy+1,ix+1,:3]))/255.


def sample_noise(atlas,point):
    """CPU reference for the shader's two-slice Hermite lookup."""
    point=np.mod(point,32.);cell=np.floor(point);blend=point-cell
    blend=blend*blend*(3.-2.*blend)
    xy=cell[:2]+blend[:2]+1.5
    z=int(cell[2]);other=(z+1)%32
    first=bilinear(atlas,xy+np.array((z%8,z//8))*34)
    second=bilinear(atlas,xy+np.array((other%8,other//8))*34)
    return first*(1.-blend[2])+second*blend[2]


class VolumeNoiseLatticeTests(unittest.TestCase):
    def setUp(self):
        data,width,height=noise_lattice()
        self.assertEqual((width,height),(272,136))
        self.atlas=np.frombuffer(data,dtype=np.uint8).reshape(height,width,4)

    def test_every_slice_has_periodic_xy_gutters_including_corners(self):
        atlas=self.atlas
        self.assertTrue(np.all(atlas[:,:,3]==255))
        for z in range(32):
            with self.subTest(z=z):
                x,y=(z%8)*34,(z//8)*34
                tile=atlas[y:y+34,x:x+34,:3]
                np.testing.assert_array_equal(tile[:,0],tile[:,32])
                np.testing.assert_array_equal(tile[:,33],tile[:,1])
                np.testing.assert_array_equal(tile[0,:],tile[32,:])
                np.testing.assert_array_equal(tile[33,:],tile[1,:])
        self.assertGreater(float(atlas[:,:,:3].std()),65.)

    def test_integer_noise_positions_land_on_texel_centers(self):
        for x,y,z in ((0,0,0),(31,31,31),(8,17,7),(23,1,8)):
            with self.subTest(point=(x,y,z)):
                expected=self.atlas[(z//8)*34+1+y,(z%8)*34+1+x,:3]/255.
                np.testing.assert_allclose(sample_noise(self.atlas,(x,y,z)),expected,atol=1e-12)

    def test_sampling_is_periodic_and_continuous_across_all_three_axes(self):
        point=np.array((7.23,11.41,15.68))
        original=sample_noise(self.atlas,point)
        for axis in range(3):
            with self.subTest(axis=axis):
                offset=np.zeros(3);offset[axis]=32.
                np.testing.assert_allclose(sample_noise(self.atlas,point+offset),original,atol=1e-12)
                np.testing.assert_allclose(sample_noise(self.atlas,point-offset),original,atol=1e-12)
                left=point.copy();right=point.copy()
                left[axis]=32.-1e-5;right[axis]=1e-5
                np.testing.assert_allclose(sample_noise(self.atlas,left),sample_noise(self.atlas,right),atol=1e-8)

    def test_last_z_slice_blends_into_first_not_adjacent_atlas_row(self):
        a=sample_noise(self.atlas,(13.,9.,31.))
        b=sample_noise(self.atlas,(13.,9.,0.))
        np.testing.assert_allclose(sample_noise(self.atlas,(13.,9.,31.5)),(a+b)*.5,atol=1e-12)


class VolumeProjectedBoundsTests(unittest.TestCase):
    def test_yawed_corners_match_cpu_inverse_transform_and_screen_rectangle(self):
        fog=region(center=(4.,2.,10.),half_extents=(1.,2.,6.),yaw=37.)
        cam=camera(position=(0.,3.,-20.),target=(0.,3.,0.))
        width,height=960,600
        rectangle=projected_bounds(fog,cam,width,height)
        c,s=math.cos(math.radians(37.)),math.sin(math.radians(37.))
        tangent=math.tan(math.radians(30.))
        pixels=[]
        for x in (-1.,1.):
            for y in (-2.,2.):
                for z in (-6.,6.):
                    world=(4.+c*x-s*z,2.+y,10.+s*x+c*z)
                    np.testing.assert_allclose(local_point(world,fog),(x,y,z),atol=1e-12)
                    # This camera looks along +Z; right points toward -X.
                    depth=world[2]+20.
                    px=width*.5-world[0]*height/(2.*depth*tangent)
                    py=height*.5-(world[1]-3.)*height/(2.*depth*tangent)
                    pixels.append((px,py))
        lo=np.min(pixels,axis=0);hi=np.max(pixels,axis=0)
        expected=(max(0,math.floor(lo[0])-2),max(0,math.floor(lo[1])-2),
                  min(width,math.ceil(hi[0])+2),min(height,math.ceil(hi[1])+2))
        self.assertEqual(rectangle,(expected[0],expected[1],expected[2]-expected[0],expected[3]-expected[1]))
        self.assertNotEqual(rectangle,projected_bounds(replace(fog,yaw=-37.),cam,width,height))

    def test_all_behind_camera_is_culled(self):
        fog=region(center=(0.,0.,-10.),half_extents=(2.,2.,2.),yaw=30.)
        self.assertIsNone(projected_bounds(fog,camera(),800,600))

    def test_camera_inside_or_near_plane_crossing_uses_full_view(self):
        fog=region(center=(0.,0.,0.),half_extents=(2.,2.,2.),yaw=45.)
        self.assertEqual(projected_bounds(fog,camera(),800,600),(0,0,800,600))
        # Conservative full-view handling also avoids slicing nearby fog
        # when the camera is just outside a region crossing the view plane.
        fog=replace(fog,center=(3.,0.,.2))
        self.assertEqual(projected_bounds(fog,camera(),800,600),(0,0,800,600))

    def test_offscreen_front_volume_is_culled_and_edge_bounds_are_clamped(self):
        cam=camera()
        fog=region(center=(100.,0.,10.),half_extents=(1.,1.,1.))
        self.assertIsNone(projected_bounds(fog,cam,800,600))
        fog=replace(fog,center=(7.,0.,10.),half_extents=(2.,2.,2.))
        bounds=projected_bounds(fog,cam,800,600)
        self.assertIsNotNone(bounds)
        x,y,w,h=bounds
        self.assertGreater(w,0);self.assertGreater(h,0)
        self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
        self.assertLessEqual(x+w,800);self.assertLessEqual(y+h,600)

    def test_reflected_bounds_equal_mirrored_geometry_and_have_vertical_symmetry(self):
        fog=region(center=(2.,3.,14.),half_extents=(2.,1.,3.),yaw=27.)
        cam=camera();width,height=960,600
        direct=projected_bounds(fog,cam,width,height)
        reflected=projected_bounds(fog,cam,width,height,water_y=0.,reflected=True)
        mirror=projected_bounds(replace(fog,center=(2.,-3.,14.)),cam,width,height)
        self.assertEqual(reflected,mirror)
        self.assertEqual(reflected[0],direct[0]);self.assertEqual(reflected[2],direct[2])
        self.assertEqual(reflected[3],direct[3])
        self.assertEqual(reflected[1],height-direct[1]-direct[3])
        # A nonzero endpoint water level must move the reflection plane too.
        shifted=projected_bounds(fog,cam,width,height,water_y=1.25,reflected=True)
        self.assertEqual(shifted,projected_bounds(replace(fog,center=(2.,-.5,14.)),cam,width,height))


if __name__=='__main__':unittest.main()
