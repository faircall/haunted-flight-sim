"""CPU contracts for remembered local fog, independent of rendering or clocks."""
import math
import unittest
import numpy as np
from g_canals_fog_grid import (CanalFogGrid,FOG_GRID_BOUNDS,FOG_GRID_SIZE,
                               ATMOSPHERE_CLEAR_AREA,MAX_INTERPOLATED_DISTANCE)


def pixels(grid):
    return np.frombuffer(grid.pixels(),np.uint8).reshape(grid.height,grid.width,4)


class CanalFogGridTests(unittest.TestCase):
    def test_empty_grid_pixel_contract_and_world_anchored_spatial_channels(self):
        grid=CanalFogGrid();a=pixels(grid)
        self.assertEqual(grid.bounds,FOG_GRID_BOUNDS)
        self.assertEqual((grid.size,grid.width,grid.height),(FOG_GRID_SIZE,)*3)
        self.assertEqual(grid.cell_size,(1.,1.));self.assertEqual(grid.revision,0)
        self.assertFalse(a[:,:,0].any());self.assertTrue((a[:,:,3]==255).all())
        self.assertGreater(float(a[:,:,1].std()),20.);self.assertGreater(float(a[:,:,2].std()),20.)
        smaller=CanalFogGrid(bounds=(-64.,-64.,64.,64.),size=128)
        self.assertTrue(np.array_equal(a[32:160,32:160,1:],pixels(smaller)[:,:,1:]))
        self.assertEqual(grid.coverage_fraction,0.);self.assertEqual(grid.clear_fraction,0.)

    def test_local_visit_has_full_core_soft_irregular_feather_and_fog_beyond(self):
        grid=CanalFogGrid();grid.update(0.,.325,0.)
        for angle in np.linspace(0.,math.tau,24,endpoint=False):
            self.assertEqual(grid.sample(math.cos(angle)*6.,math.sin(angle)*6.),1.)
            self.assertEqual(grid.sample(math.cos(angle)*25.,math.sin(angle)*25.),0.)
        feather=[grid.sample(math.cos(a)*14.,math.sin(a)*14.) for a in np.linspace(0.,math.tau,80,endpoint=False)]
        self.assertTrue(all(0.<v<1. for v in feather))
        self.assertGreater(np.std(feather),.025,'The feather should not form a uniform ring')
        dense=np.array([grid.sample(x,4.25) for x in np.linspace(7.,24.,1701)])
        self.assertLess(np.max(abs(np.diff(dense))),.004,'No cell-width opacity steps')

    def test_equal_puzzle_radius_lateral_places_are_discovered_independently(self):
        grid=CanalFogGrid();grid.update(25.,.325,0.)
        self.assertEqual(grid.sample(25.,0.),1.)
        self.assertEqual(grid.sample(0.,25.),0.)
        old=grid.pixels();before=grid.clear_fraction
        grid.update(0.,.325,25.)
        self.assertEqual(grid.sample(0.,25.),1.)
        self.assertEqual(grid.sample(25.,0.),1.)
        self.assertNotEqual(old,grid.pixels());self.assertGreater(grid.clear_fraction,before)
        self.assertEqual(grid.sample(-32.,-32.),0.)

    def test_entering_a_lateral_room_clears_that_room_without_clearing_opposite_bank(self):
        grid=CanalFogGrid()
        for z in np.linspace(0.,30.,31):grid.update(0.,.325,z)
        before=grid.sample(15.,22.);opposite=grid.sample(-18.,22.)
        self.assertLess(before,.95)
        for x in np.linspace(0.,15.,31):grid.update(x,.325,22.)
        self.assertEqual(grid.sample(15.,22.),1.)
        self.assertAlmostEqual(grid.sample(-18.,22.),opposite)
        self.assertEqual(grid.sample(-38.,22.),0.)

    def test_waiting_repeated_points_and_full_strength_backtracking_do_not_erode(self):
        grid=CanalFogGrid();route=[(x,10.+x*.3) for x in np.linspace(-12.,12.,97)]
        for x,z in route:grid.update(x,.325,z)
        before=grid.pixels();revision=grid.revision;grade=grid.clear_fraction
        for _ in range(1000):grid.update(*[route[-1][0],.325,route[-1][1]])
        for x,z in reversed(route):grid.update(x,.325,z)
        for x,z in route:grid.update(x,.325,z)
        self.assertEqual(grid.pixels(),before);self.assertEqual(grid.revision,revision)
        self.assertEqual(grid.clear_fraction,grade)

    def test_gate_strength_zero_and_repeated_lower_strength_do_not_paint(self):
        grid=CanalFogGrid();grid.update(0.,.325,0.,0.)
        self.assertEqual(grid.revision,0);self.assertEqual(grid.sample(0.,0.),0.)
        grid.update(0.,.325,0.,.4)
        self.assertAlmostEqual(grid.sample(0.,0.),.4)
        before=grid.pixels();revision=grid.revision
        for value in (.4,.1,0.,.4):grid.update(0.,.325,0.,value)
        self.assertEqual(grid.pixels(),before);self.assertEqual(grid.revision,revision)
        grid.update(0.,.325,0.,1.)
        self.assertEqual(grid.sample(0.,0.),1.);self.assertGreater(grid.revision,revision)

    def test_swept_short_segment_matches_dense_sampling_exactly(self):
        coarse=CanalFogGrid();fine=CanalFogGrid()
        for t in (0.,.5,1.):coarse.update(-8.+16.*t,.325,-3.+8.*t)
        for t in np.linspace(0.,1.,321):fine.update(-8.+16.*t,.325,-3.+8.*t)
        self.assertEqual(coarse.pixels(),fine.pixels())
        for t in np.linspace(0.,1.,101):self.assertEqual(coarse.sample(-8.+16.*t,-3.+8.*t),1.)

    def test_gated_30_and_60hz_walks_match_visible_clearance(self):
        grids=[]
        for fps in (30,60):
            grid=CanalFogGrid();count=math.ceil(10./1.55*fps)
            for x in np.linspace(0.,10.,count+1):grid.update(x,.325,0.,x/10.)
            grids.append(grid)
        difference=np.abs(pixels(grids[0])[:,:,0].astype(int)-pixels(grids[1])[:,:,0].astype(int))
        # R8 quantization may differ by one level at a feather threshold. The
        # bilinear GPU sample removes cell edges; no dt accumulates in the map.
        self.assertLessEqual(int(difference.max()),1)
        self.assertLess(abs(grids[0].clear_fraction-grids[1].clear_fraction),1e-5)

    def test_teleport_does_not_draw_a_discovery_line_between_endpoints(self):
        grid=CanalFogGrid();self.assertLess(MAX_INTERPOLATED_DISTANCE,100.)
        grid.update(-50.,.325,0.);grid.update(50.,.325,0.)
        self.assertEqual(grid.sample(-50.,0.),1.);self.assertEqual(grid.sample(50.,0.),1.)
        self.assertEqual(grid.sample(0.,0.),0.)

    def test_bilinear_sampling_matches_pixel_centres_and_fractional_positions(self):
        grid=CanalFogGrid();grid.update(0.,.325,0.);a=pixels(grid)[:,:,0]
        for i,j in ((96,96),(108,99),(110,91),(113,100)):
            self.assertAlmostEqual(grid.sample(i-95.5,j-95.5),float(a[j,i])/255.)
            expected=float(a[j:j+2,i:i+2].astype(float).mean())/255.
            self.assertAlmostEqual(grid.sample(i-95.,j-95.),expected)
        self.assertEqual(grid.sample(-97.,0.),0.);self.assertEqual(grid.sample(0.,97.),0.)

    def test_deterministic_pixels_monotonic_memory_and_area_summary(self):
        a=CanalFogGrid();b=CanalFogGrid();last=pixels(a)[:,:,0].copy()
        for x,z,strength in ((-10.,-8.,.2),(-6.,-5.,.55),(0.,0.,1.),(8.,4.,1.),(35.,24.,1.)):
            for grid in (a,b):grid.update(x,.325,z,strength)
            current=pixels(a)[:,:,0]
            self.assertTrue((current>=last).all());last=current.copy()
            self.assertEqual(a.pixels(),b.pixels());self.assertEqual(a.revision,b.revision)
        effective_area=float(pixels(a)[:,:,0].sum(dtype=np.int64))/255.
        self.assertAlmostEqual(a.coverage_fraction,effective_area/(192.*192.))
        self.assertAlmostEqual(a.clear_fraction,min(1.,effective_area/ATMOSPHERE_CLEAR_AREA))

    def test_full_preview_is_idempotent_and_preserves_spatial_channels(self):
        grid=CanalFogGrid();noise=pixels(grid)[:,:,1:].copy();grid.reveal_all()
        self.assertTrue((pixels(grid)[:,:,0]==255).all());self.assertEqual(grid.clear_fraction,1.)
        self.assertEqual(grid.coverage_fraction,1.);self.assertTrue(np.array_equal(noise,pixels(grid)[:,:,1:]))
        before=grid.pixels();revision=grid.revision
        grid.reveal_all();grid.update(10.,.325,12.)
        self.assertEqual(grid.pixels(),before);self.assertEqual(grid.revision,revision)

    def test_invalid_values_are_rejected_without_mutating_memory(self):
        for bounds,size in (((0.,0.,0.,1.),10),((0.,0.,1.,math.inf),10),(FOG_GRID_BOUNDS,0),(FOG_GRID_BOUNDS,2.5),(FOG_GRID_BOUNDS,True)):
            with self.assertRaises(ValueError):CanalFogGrid(bounds=bounds,size=size)
        grid=CanalFogGrid();before=grid.pixels()
        for visit in ((math.nan,0.,0.,1.),(0.,math.inf,0.,1.),(0.,0.,-math.inf,1.),(0.,0.,0.,-.1),(0.,0.,0.,1.1),(0.,0.,0.,math.nan)):
            with self.assertRaises(ValueError):grid.update(*visit)
        for point in ((math.inf,0.),(0.,math.nan)):
            with self.assertRaises(ValueError):grid.sample(*point)
        self.assertEqual(grid.pixels(),before);self.assertEqual(grid.revision,0)


if __name__=='__main__':unittest.main()
