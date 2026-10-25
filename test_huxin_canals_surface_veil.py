"""GPU-free safety checks for the fixed-datum water concealment layer."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch,Mock
import unittest
import math

from g_huxin_canals_direction import default_document,profile_from_document
from g_huxin_canals_surface_settings import SurfaceFogSettings,surface_blend_window
from g_huxin_canals_water_fog import lake_fog_frame
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

    def test_settling_veil_reveals_a_thick_ray_progressively_instead_of_saturating(self):
        p=profile();p.surface_fog.water_settle=True
        for t in (14.,15.,21.,22.):
            self.assertEqual(veil_frame(p,t).strength,1.)
        for t in (24.,27.,30.,33.,36.,39.,42.,44.):
            frame=veil_frame(p,t)
            opacity=1.-math.exp(-12.*frame.strength)
            self.assertAlmostEqual(opacity,(1.-frame.clearing)*(1.-math.exp(-12.)),places=12)
        middle=veil_frame(p,33.)
        self.assertAlmostEqual(1.-math.exp(-12.*middle.strength),.5*(1.-math.exp(-12.)),places=12)
        self.assertEqual(veil_frame(p,44.).strength,0.)
        # Ordinary saved profiles retain their previous density envelope.
        p.surface_fog.water_settle=False
        legacy=veil_frame(p,33.)
        self.assertEqual(legacy.strength,(1.-legacy.clearing)**2.2)
        self.assertGreater(1.-math.exp(-12.*legacy.strength),.9)

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
                    self.assertEqual(values['formationBaseY'],0.)
                    self.assertEqual(values['depthHold'],1.)
                    self.assertEqual(values['waterY'],-1.55)
                    self.assertEqual(values['reflectedView'],float(reflected))

            p.surface_fog.wispy_formation=True
            p.surface_fog.water_settle=True
            p.surface_fog.water_settle_start=35.
            p.surface_fog.water_settle_end=47.
            p.surface_fog.build_end=24.
            p.surface_fog.reveal_start=28.
            p.surface_fog.reveal_end=60.
            for elapsed in (24.,24.5,25.,35.,41.,47.):
                sequence.elapsed=elapsed
                expected=lake_fog_frame(p,elapsed)
                for water_y in (0.,-1.55):
                    for reflected in (False,True):
                        layer.uniform.reset_mock()
                        layer.render(source,cam,sequence,elapsed,(.3,.4,.5),water_y,reflected=reflected)
                        values=dict(call.args for call in layer.uniform.call_args_list)
                        self.assertEqual(values['baseY'],expected.base_y)
                        self.assertEqual(values['formationBaseY'],0.)
                        self.assertEqual(values['depthHold'],expected.depth_hold)
                        self.assertEqual(layer.last_frame.descent,expected.descent)

    def test_visible_curve_borrows_the_prepared_field_and_releases_only_own_resources(self):
        p=profile()
        p.surface_fog.foot_curve=4.8
        p.surface_fog.wispy_formation=True
        p.surface_fog.evolution='condense'
        sequence=SimpleNamespace(direction=p,elapsed=14.,state='canals')
        vector=SimpleNamespace(x=0.,y=0.,z=1.)
        cam=SimpleNamespace(position=SimpleNamespace(x=-4.8,y=1.9,z=-2.2),
                            target=vector,up=vector,fovy=78.)
        field_texture=SimpleNamespace(width=2048,height=1024)
        timing_texture=object()
        surface=SimpleNamespace(field=SimpleNamespace(origin=(-120.,-14.,-180.),shape=(244,68,627),
                                spacing=.6,distance_cap=16.),field_texture=field_texture,
                                timing_texture=timing_texture,atlas_columns=7)
        layer=LakeSurfaceVeil(640,360)
        layer.prepare=Mock();layer.uniform=Mock()
        layer.shader=object();own_noise=layer.noise=object()
        layer.target=SimpleNamespace(texture=object())
        layer.locations={'depthMap':1,'noiseMap':2,'fieldMap':3,'timingMap':4}
        source=SimpleNamespace(depth=object())
        with patch('huxin_canals_surface_veil.pr') as api:
            api.vector3_normalize.return_value=vector
            api.vector3_cross_product.return_value=vector
            for reflected in (False,True):
                layer.uniform.reset_mock();api.set_shader_value_texture.reset_mock()
                layer.render(source,cam,sequence,14.,(.3,.4,.5),0.,reflected=reflected,surface_renderer=surface)
                values=dict(call.args for call in layer.uniform.call_args_list)
                self.assertEqual(values['curveRadius'],4.8)
                self.assertEqual(values['curveBuild'],1.)
                self.assertEqual(values['curveDescent'],0.)
                self.assertEqual(values['fieldOrigin'],surface.field.origin)
                self.assertEqual(values['atlasSize'],(2048,1024))
                self.assertEqual(values['atlasColumns'],7)
                maps={call.args[1]:call.args[2] for call in api.set_shader_value_texture.call_args_list}
                self.assertIs(maps[3],field_texture)
                self.assertIs(maps[4],timing_texture)
                self.assertEqual(layer.last_curve_radius,4.8)

            p.surface_fog.foot_curve=0.
            layer.uniform.reset_mock();api.set_shader_value_texture.reset_mock()
            layer.render(source,cam,sequence,14.,(.3,.4,.5),0.,surface_renderer=surface)
            values=dict(call.args for call in layer.uniform.call_args_list)
            self.assertEqual(values['curveRadius'],0.)
            self.assertEqual([call.args[1] for call in api.set_shader_value_texture.call_args_list],[1,2])
            self.assertNotIn('fieldOrigin',values)
            layer.close()
            api.unload_texture.assert_called_once_with(own_noise)
            self.assertIs(surface.field_texture,field_texture)
            self.assertIs(surface.timing_texture,timing_texture)


if __name__=='__main__':unittest.main()
