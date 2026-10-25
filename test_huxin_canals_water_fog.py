"""Timeline and depth-restoration checks for the delayed lake-fog descent."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from g_huxin_canals_direction import default_document,profile_from_document
from g_huxin_canals_layout import WATER_Y
from g_huxin_canals_surface_settings import SurfaceFogSettings,surface_blend_window
from g_huxin_canals_water_fog import LakeFogFrame,lake_fog_frame,descent_progress


def profile(**changes):
    p=profile_from_document(default_document())
    settings=SurfaceFogSettings(enabled=True,build_end=24.,reveal_start=28.,reveal_end=60.)
    values={key:getattr(settings,key) for key in settings.__dataclass_fields__}
    values.update(water_settle=True,water_settle_start=35.,water_settle_end=47.)
    values.update(changes)
    return replace(p,surface_fog=SimpleNamespace(**values))


class LakeFogFrameTests(unittest.TestCase):
    def test_lowering_has_visible_early_motion_and_steady_middle_speed(self):
        self.assertGreater(descent_progress(.1),.04)
        self.assertLess(descent_progress(.9),.96)
        steps=[descent_progress(t+.05)-descent_progress(t) for t in (.2,.3,.4,.5,.6,.7)]
        self.assertLess(max(steps)-min(steps),1.e-12)
        for boundary in (0.,.12,.88,1.):
            h=1.e-5
            left=(descent_progress(boundary)-descent_progress(boundary-h))/h
            right=(descent_progress(boundary+h)-descent_progress(boundary))/h
            self.assertLess(abs(left-right),1.e-6)

    def test_handoff_is_unchanged_and_later_descent_reaches_the_actual_canal(self):
        p=profile()
        self.assertEqual(surface_blend_window(p),(24.,25.))
        for time in (-5.,0.,24.,24.5,25.,34.,35.):
            self.assertEqual(lake_fog_frame(p,time),LakeFogFrame(0.,0.,1.))
        middle=lake_fog_frame(p,41.)
        self.assertEqual(middle.descent,.5)
        self.assertEqual(middle.base_y,WATER_Y*.5)
        self.assertLess(middle.depth_hold,.1)
        for time in (47.,48.,200.):
            self.assertEqual(lake_fog_frame(p,time),LakeFogFrame(WATER_Y,1.,0.))

    def test_legacy_disabled_and_inactive_modes_keep_the_original_datum(self):
        legacy=profile_from_document(default_document())
        self.assertEqual(lake_fog_frame(legacy,100.),LakeFogFrame(0.,0.,1.))
        for changes in ({'water_settle':False},{'enabled':False},{'amount':0.}):
            p=profile(base_y=.2,**changes)
            self.assertEqual(lake_fog_frame(p,100.),LakeFogFrame(.2,0.,1.))
        p=profile(base_y=.2)
        del p.surface_fog.water_settle
        self.assertEqual(lake_fog_frame(p,100.),LakeFogFrame(.2,0.,1.))
        self.assertEqual(lake_fog_frame(profile(),100.,'ordinary'),LakeFogFrame(0.,0.,1.))

    def test_curve_is_monotone_and_has_no_jump_or_slope_at_either_end(self):
        p=profile()
        samples=[lake_fog_frame(p,35.+i*.1) for i in range(121)]
        self.assertTrue(all(a.base_y>=b.base_y for a,b in zip(samples,samples[1:])))
        self.assertTrue(all(a.depth_hold>=b.depth_hold for a,b in zip(samples,samples[1:])))
        self.assertTrue(all(0.<=f.descent<=1. and 0.<=f.depth_hold<=1. for f in samples))
        for edge in (35.,47.):
            a=lake_fog_frame(p,edge-.001);b=lake_fog_frame(p,edge+.001)
            self.assertLess(abs(a.base_y-b.base_y),1.e-8)
            self.assertLess(abs(a.depth_hold-b.depth_hold),1.e-8)

    def test_late_handoff_shifts_the_full_descent_instead_of_shortening_it(self):
        p=profile(build_end=40.)
        self.assertEqual(surface_blend_window(p),(40.,41.))
        for t in (35.,40.,40.5,41.):
            self.assertEqual(lake_fog_frame(p,t),LakeFogFrame(0.,0.,1.))
        self.assertEqual(lake_fog_frame(p,47.).descent,.5)
        self.assertEqual(lake_fog_frame(p,53.),LakeFogFrame(WATER_Y,1.,0.))

    def test_seeking_is_stateless_and_does_not_modify_the_formation_base(self):
        p=profile(base_y=.2)
        before=dict(vars(p.surface_fog))
        times=(47.,24.,40.,35.,44.,25.,41.,48.)
        values={t:lake_fog_frame(p,t) for t in times}
        for t in reversed(times):
            self.assertEqual(lake_fog_frame(p,t,'entering'),values[t])
            self.assertEqual(lake_fog_frame(p,t,'canals'),values[t])
        self.assertEqual(vars(p.surface_fog),before)
        self.assertEqual(values[47.].base_y,WATER_Y)
        self.assertEqual(values[35.].base_y,.2)


if __name__=='__main__':unittest.main()
