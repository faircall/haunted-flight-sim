"""Pure moon targeting, optical timing and exported-architecture coverage."""
import math
import unittest
from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from g_huxin_moon_fog import MOON_FOG_REGIONS,moon_fog_frame
from test_huxin_moon import geometry


def sequence(state='entering',elapsed=0.,progress=0.,revealed=False):
    return SimpleNamespace(state=state,elapsed=elapsed,return_progress=progress,revealed=revealed)


def covered(points,regions=MOON_FOG_REGIONS):
    points=np.asarray(points)
    result=np.zeros(points.shape[:-1],bool)
    for region in regions:
        result|=np.all(np.abs(points-region.center)<=np.asarray(region.half_extents)+region.edge,axis=-1)
    return result


class MoonFogTests(unittest.TestCase):
    def test_ordinary_approach_and_settled_worlds_have_no_targeted_fog(self):
        original=MOON_FOG_REGIONS
        for state in ('ordinary','revealed','returned'):
            frame=moon_fog_frame(sequence(state,elapsed=8.,progress=.5))
            self.assertFalse(frame.active)
            self.assertEqual((frame.strength,frame.build,frame.clearing,frame.depth_hold),(0.,0.,0.,0.))
            self.assertTrue(all(region.density==0 for region in frame.regions))
        self.assertEqual(MOON_FOG_REGIONS,original)

    def test_frame_keeps_fixed_region_identity_and_bounds_when_scrubbing(self):
        for elapsed in (0.,4.,8.,16.,24.,8.,-2.,30.):
            frame=moon_fog_frame(sequence(elapsed=elapsed))
            self.assertEqual(len(frame.regions),24)
            for authored,sampled in zip(MOON_FOG_REGIONS,frame.regions):
                self.assertEqual(replace(sampled,density=authored.density),authored)
                self.assertTrue(math.isfinite(sampled.density))
                self.assertGreaterEqual(sampled.density,0.)
                self.assertLessEqual(sampled.density,authored.density)
        self.assertEqual(moon_fog_frame(sequence(elapsed=8.)),moon_fog_frame(sequence(elapsed=8.)))

    def test_full_mask_spans_hidden_handoff_for_both_world_endpoints(self):
        for elapsed in np.linspace(7.5,8.5,21):
            before=moon_fog_frame(sequence(elapsed=elapsed,revealed=False))
            after=moon_fog_frame(sequence(elapsed=elapsed,revealed=True))
            self.assertEqual(before,after)
            self.assertEqual(before.regions,MOON_FOG_REGIONS)
            self.assertEqual(before.depth_hold,1.)
        for progress in np.linspace(.47,.53,21):
            before=moon_fog_frame(sequence('leaving',progress=progress,revealed=False))
            after=moon_fog_frame(sequence('leaving',progress=progress,revealed=True))
            self.assertEqual(before,after)
            self.assertEqual(before.regions,MOON_FOG_REGIONS)
            self.assertEqual(before.depth_hold,1.)

    def test_optical_clearing_starts_after_handoff_and_reveals_details_in_stages(self):
        clear_times=[]
        for i,region in enumerate(MOON_FOG_REGIONS):
            self.assertGreater(region.clear_start,8.5)
            halfway=(region.clear_start+region.clear_end)*.5
            density=moon_fog_frame(sequence(elapsed=halfway)).regions[i].density
            # Half the optical reveal has happened halfway through this bank's
            # window; reducing raw density by half would still look opaque.
            transmittance=math.exp(-8.*density/region.density)
            self.assertAlmostEqual(transmittance,(1.+math.exp(-8.))*.5)
            samples=[moon_fog_frame(sequence(elapsed=t)).regions[i].density
                     for t in np.linspace(8.5,24.,80)]
            self.assertTrue(all(a>=b for a,b in zip(samples,samples[1:])))
            clear_times.append(region.clear_end)
        self.assertGreater(max(clear_times)-min(clear_times),6.)
        self.assertFalse(moon_fog_frame(sequence(elapsed=24.)).active)

    def test_formation_opacity_follows_progress_instead_of_saturating_early(self):
        for q in (sequence(elapsed=3.6),sequence('leaving',progress=(.025+.43)*.5)):
            frame=moon_fog_frame(q)
            self.assertAlmostEqual(frame.build,.5)
            authored=MOON_FOG_REGIONS[0]
            transmission=math.exp(-8.*frame.regions[0].density/authored.density)
            self.assertAlmostEqual(transmission,(1.+math.exp(-8.))*.5)
        early=moon_fog_frame(sequence('leaving',progress=.20))
        transmission=math.exp(-8.*early.regions[0].density/MOON_FOG_REGIONS[0].density)
        self.assertGreater(transmission,.6)

    def test_initial_lens_has_no_local_bank_and_delayed_lanterns_follow_camera_cut(self):
        first_eye=(2.85,3.6,2.4)
        later_eye=(-2.6,3.6,-2.8)
        for elapsed,eye in ((1.,first_eye),(3.99,first_eye),(4.,later_eye),(8.,later_eye)):
            active=tuple(r for r in moon_fog_frame(sequence(elapsed=elapsed)).regions if r.density>0)
            self.assertFalse(covered([eye],active)[0],(elapsed,eye))
        lamps=[r for r in moon_fog_frame(sequence(elapsed=4.)).regions if r.role=='lantern']
        self.assertTrue(all(r.density==0 for r in lamps))
        self.assertTrue(all(r.density>0 for r in moon_fog_frame(sequence(elapsed=6.)).regions if r.role=='lantern'))

    def test_fields_leave_central_puzzle_and_lake_open(self):
        points=[(x,y,z) for x in (-1.,0.,1.) for z in (-1.,0.,1.) for y in (.325,1.3,2.4)]
        self.assertFalse(covered(points).any())
        self.assertFalse(covered([(20.,0.,0.),(0.,0.,20.),(-20.,0.,0.),(0.,0.,-20.)]).any())
        self.assertFalse(covered([(0.,1.5,6.),(0.,1.5,8.)]).any())

    def test_changed_exported_architecture_and_balcony_piers_have_local_coverage(self):
        names=('pavilion_brackets','pavilion_roofs','pavilion_ceiling','pavilion_inscriptions',
               'tea_frame','tea_walls','tea_lattice','tea_floors','tea_stairs','tea_roofs',
               'tea_ceiling','tea_furniture','tea_lanterns')
        for name in names:
            points=geometry(name)[1].reshape(-1,3)
            # The unchanged paving hides the two central foundation triangles.
            points=points[points[:,1]>.37]
            self.assertTrue(covered(points).all(),name)
        points=geometry('tea_foundation')[1].reshape(-1,3)
        balcony=points[(points[:,2]>7.7)&(points[:,1]>0.)]
        self.assertGreater(len(balcony),100)
        self.assertTrue(covered(balcony).all())

    def test_return_is_reversible_position_sampling_without_a_clock_or_world_jump(self):
        for progress in (.02,.2,.45,.5,.68,.85,.98,1.):
            q=sequence('leaving',elapsed=1.,progress=progress)
            first=moon_fog_frame(q)
            q.elapsed=1000.
            self.assertEqual(first,moon_fog_frame(q))
            q.return_progress=.95
            moon_fog_frame(q)
            q.return_progress=progress
            self.assertEqual(first,moon_fog_frame(q))
        self.assertFalse(moon_fog_frame(sequence('leaving',progress=.02)).active)
        self.assertFalse(moon_fog_frame(sequence('leaving',progress=.98)).active)

    def test_invalid_active_progress_cannot_contaminate_shader_uniforms(self):
        for bad in (float('nan'),float('inf'),-float('inf')):
            for q in (sequence(elapsed=bad),sequence('leaving',progress=bad)):
                with self.assertRaises(ValueError):moon_fog_frame(q)


if __name__=='__main__':unittest.main()
