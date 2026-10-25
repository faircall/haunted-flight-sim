"""Contract checks for staggered pulls, persistent wisps and reversible time."""
import unittest
from g_huxin_canals_condense import condense_phases,condense_window


class CondensationTimingTests(unittest.TestCase):
    def test_long_pull_spreads_material_emergence_across_the_full_motion(self):
        point=(4.,3.,-12.);window=(15.,41.);hold=.28;duration=7.
        start=15.+26.*hold
        early=condense_phases(point,window,start+duration*.08,hold,duration,pattern=0.)
        late=condense_phases(point,window,start+duration*.92,hold,duration,pattern=0.)
        self.assertGreater(early[3],0.)
        self.assertLess(late[3],1.)
        quarter=condense_phases(point,window,start+duration*.25,hold,duration,pattern=0.)
        self.assertAlmostEqual(quarter[1],.15625)
        tail=condense_phases(point,window,start+duration+1.,hold,duration,pattern=0.)
        self.assertEqual(tail[3],1.)
        self.assertGreater(tail[2],.5)

    def test_pull_is_a_short_event_with_a_separate_residual_tail(self):
        p=(4.,3.,-12.);window=(10.,20.)
        self.assertEqual(condense_phases(p,window,9.),(0.,0.,1.,0.))
        before=condense_phases(p,window,14.,pattern=0.)
        self.assertGreater(before[0],.8)
        self.assertEqual(before[1:],(0.,1.,0.))
        middle=condense_phases(p,window,15.575,pattern=0.)
        self.assertAlmostEqual(middle[1],.5)
        self.assertGreater(middle[3],.3)
        after=condense_phases(p,window,17.,pattern=0.)
        self.assertEqual(after[1],1.)
        self.assertEqual(after[3],1.)
        self.assertGreater(after[2],.5)
        self.assertEqual(condense_phases(p,window,20.),(1.,1.,0.,1.))

    def test_pull_duration_is_in_seconds_for_short_and_long_house_windows(self):
        for window in ((8.,16.),(12.,42.)):
            start=sum(window)*.5
            for offset,expected in ((0.,0.),(.575,.5),(1.15,1.)):
                phases=condense_phases((0,0,0),window,start+offset,pattern=0.)
                self.assertAlmostEqual(phases[1],expected)

    def test_extreme_valid_controls_still_finish_within_the_authored_window(self):
        for span in (.1,.3,1.,10.,30.):
            for hold in (.2,.5,.9):
                for duration in (.1,1.15,5.,7.,15.):
                    with self.subTest(span=span,hold=hold,duration=duration):
                        window=(8.5,8.5+span)
                        phases=condense_phases((35.1,2.7,-22.6),window,window[1],hold,duration,pattern=1.)
                        self.assertEqual(phases,(1.,1.,0.,1.))

    def test_spatial_delay_is_smooth_and_scrubbing_is_deterministic(self):
        point=(8.,4.,20.);window=(8.5,18.)
        samples=[condense_phases(point,window,8.5+i*.01) for i in range(951)]
        for a,b in zip(samples,samples[1:]):
            self.assertLessEqual(a[0],b[0]+1e-10)
            self.assertLessEqual(a[1],b[1]+1e-10)
            self.assertGreaterEqual(a[2],b[2]-1e-10)
            self.assertLessEqual(a[3],b[3]+1e-10)
            self.assertLess(max(abs(x-y) for x,y in zip(a,b)),.04)
        for i in (950,200,700,0,450):self.assertEqual(samples[i],condense_phases(point,window,8.5+i*.01))
        a=condense_phases(point,window,13.6)
        b=condense_phases((8.0001,4.,20.),window,13.6)
        self.assertLess(max(abs(x-y) for x,y in zip(a,b)),.001)
        distinct=condense_phases((-2.,7.,15.),window,13.6)
        self.assertGreater(abs(a[1]-distinct[1]),.001)

    def test_slow_parallel_house_windows_keep_full_pull_and_a_residual_tail(self):
        windows=((15.,41.),(16.,43.),(18.,46.),(20.,48.))
        intervals=[]
        for window in windows:
            start,duration=condense_window(window,.28,7.)
            self.assertGreaterEqual(duration,6.)
            self.assertEqual(duration,7.)
            intervals.append((start,start+duration))
            phases=condense_phases((0,0,0),window,start+3.5,.28,7.,pattern=0.)
            self.assertAlmostEqual(phases[1],.5)
            self.assertEqual(phases[2],1.)
            after=condense_phases((0,0,0),window,start+duration+1.,.28,7.,pattern=0.)
            self.assertEqual(after[1],1.)
            self.assertGreater(after[2],.5)
        # All four example houses are in their pull at the same time. This
        # guards against long durations accidentally serializing the reveal.
        self.assertLess(max(a for a,_ in intervals),min(b for _,b in intervals))

    def test_effective_duration_reports_shortened_windows_instead_of_global_request(self):
        self.assertEqual(condense_window((10.,40.),.28,7.),(18.4,7.))
        start,duration=condense_window((10.,12.),.5,7.)
        self.assertEqual(start,11.)
        self.assertAlmostEqual(duration,.55)


if __name__=='__main__':unittest.main()
