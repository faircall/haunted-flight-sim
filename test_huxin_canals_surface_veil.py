"""GPU-free safety checks for the fixed-datum water concealment layer."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch,Mock
import unittest

from g_huxin_canals_direction import default_document,profile_from_document
from g_huxin_canals_surface_settings import SurfaceFogSettings,surface_blend_window
from huxin_canals_surface_veil import LakeSurfaceVeil,shared_causeway_points,veil_frame


def profile():
    original=profile_from_document(default_document())
    settings=SurfaceFogSettings(enabled=True,build_end=14.,reveal_start=22.,reveal_end=44.)
    # A SimpleNamespace also exercises optional fields on older settings.
    values={key:getattr(settings,key) for key in settings.__dataclass_fields__}
    values['water_mask']=True
    return replace(original,surface_fog=SimpleNamespace(**values))


class SurfaceVeilTimingTests(unittest.TestCase):
    def test_water_mask_is_prepared_before_puzzle_activation(self):
        from huxin_canals_viewer import reset_player
        scene=SimpleNamespace(surface_fog=Mock(),surface_veil=Mock())
        actor=reset_player(scene,puzzle=True,direction=profile())
        self.assertEqual(scene.sequence.state,'ordinary')
        scene.surface_veil.prepare.assert_called_once_with()
        self.assertFalse(scene.sequence.disc_placed)
        self.assertIs(actor.encounter,scene.sequence)

    def test_test_timer_uses_the_delayed_geometry_handoff(self):
        from huxin_canals_viewer import draw_puzzle_timer
        from g_huxin_canals_sequence import CanalSequence
        q=CanalSequence(profile())
        with patch('huxin_canals_viewer.pr.draw_rectangle'),patch('huxin_canals_viewer.pr.draw_text') as draw:
            q.seek(10.);draw_puzzle_timer(q,640)
            self.assertIn('Fog building',[call.args[0] for call in draw.call_args_list])
            draw.reset_mock();q.seek(14.5);draw_puzzle_timer(q,640)
            self.assertIn('Fog crest - hidden transition',[call.args[0] for call in draw.call_args_list])

    def test_mask_is_full_through_both_geometry_endpoints_and_the_later_hold(self):
        p=profile();start,end=surface_blend_window(p)
        self.assertEqual((start,end),(14.,15.))
        for elapsed in (start,(start+end)*.5,end,21.,22.):
            with self.subTest(elapsed=elapsed):
                frame=veil_frame(p,elapsed)
                self.assertTrue(frame.active)
                self.assertEqual(frame.strength,1.)
                self.assertEqual(frame.clearing,0.)

    def test_build_and_clear_are_smooth_monotone_and_finish_exactly(self):
        p=profile()
        values=[veil_frame(p,i*.1).strength for i in range(141)]
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertEqual(values[0],0.)
        self.assertLess(veil_frame(p,1.).strength,.001)
        self.assertLess(veil_frame(p,7.).strength,.25)
        values=[veil_frame(p,22.+i*.1).strength for i in range(221)]
        self.assertTrue(all(a>=b for a,b in zip(values,values[1:])))
        self.assertEqual(values[-1],0.)
        self.assertFalse(veil_frame(p,46.).active)

    def test_old_profiles_and_inactive_modes_have_exact_texture_identity(self):
        scene=SimpleNamespace(direction=profile_from_document(default_document()),elapsed=14.,state='canals')
        layer=LakeSurfaceVeil(640,360);base=object()
        with patch.object(layer,'prepare',side_effect=AssertionError('Inactive layer allocated GPU resources')):
            self.assertIs(layer.render(None,None,scene,80.,(1.,1.,1.),-1.55,base_texture=base),base)
            self.assertIsNone(layer.render(None,None,scene,80.,(1.,1.,1.),0.))
            scene.direction=profile();scene.state='ordinary'
            self.assertIs(layer.render(None,None,scene,80.,(1.,1.,1.),0.,base_texture=base),base)
            scene.state='canals';scene.elapsed=46.
            self.assertIs(layer.render(None,None,scene,80.,(1.,1.,1.),-1.55,base_texture=base),base)

    def test_fixed_datum_and_live_hold_retiming_do_not_follow_water_height(self):
        p=profile();p.surface_fog.base_y=.2
        self.assertEqual(veil_frame(p,14.).base_y,.2)
        self.assertEqual(veil_frame(p,30.).base_y,.2)
        p.surface_fog.build_end=25.;p.surface_fog.reveal_start=22.
        # Even a direct runtime caller cannot clear before a delayed handoff.
        self.assertEqual(surface_blend_window(p),(25.,26.))
        self.assertEqual(veil_frame(p,26.).strength,1.)
        self.assertEqual(veil_frame(p,26.).clearing,0.)

    def test_shared_clearance_tracks_the_actual_curved_path(self):
        from g_huxin_canals import path_distance
        points=shared_causeway_points()
        self.assertEqual(len(points),6)
        self.assertEqual(points[0][1],4.)
        self.assertEqual(points[-1][1],12.)
        self.assertLess(points[-1][0],-1.)
        for x,z in points:self.assertLess(path_distance(x,z),1.e-6)

    def test_depth_preservation_is_opt_in_and_refreshes_in_both_camera_passes(self):
        p=profile()
        # Simulate an older caller that has no optional formation field.
        del p.surface_fog.wispy_formation
        sequence=SimpleNamespace(direction=p,elapsed=14.,state='canals')
        vector=SimpleNamespace(x=0.,y=0.,z=1.)
        cam=SimpleNamespace(position=SimpleNamespace(x=-4.8,y=1.9,z=-2.2),
                            target=vector,up=vector,fovy=78.)
        layer=LakeSurfaceVeil(640,360)
        layer.prepare=Mock();layer.uniform=Mock()
        layer.shader=object();layer.noise=object()
        layer.target=SimpleNamespace(texture=object())
        layer.locations={'depthMap':1,'noiseMap':2}
        source=SimpleNamespace(depth=object())
        with patch('huxin_canals_surface_veil.pr') as api:
            api.vector3_normalize.return_value=vector
            api.vector3_cross_product.return_value=vector
            for setting in (None,True,False):
                if setting is not None:p.surface_fog.wispy_formation=setting
                for reflected in (False,True):
                    layer.uniform.reset_mock()
                    result=layer.render(source,cam,sequence,18.,(.3,.4,.5),-1.55,reflected=reflected)
                    self.assertIs(result,layer.target.texture)
                    values=dict(call.args for call in layer.uniform.call_args_list)
                    self.assertEqual(values['wispyFormation'],float(bool(setting)))
                    self.assertEqual(values['baseY'],0.)
                    self.assertEqual(values['waterY'],-1.55)
                    self.assertEqual(values['reflectedView'],float(reflected))


if __name__=='__main__':unittest.main()
