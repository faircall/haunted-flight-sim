"""Native editor controller integration, using no graphics/audio device."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import building_document, save_direction
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_editor import Editor, Input


class SurfaceEditorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='haunted-surface-ui-');self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'surface.json';self.document=building_document();save_direction(self.document,self.path)
        self.scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        self.editor=Editor(self.scene,path=self.path,live_input=False,selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(self.editor.close)
        for name,value in (('get_screen_width',1360),('get_screen_height',900)):
            patcher=patch('huxin_canals_editor.pr.'+name,return_value=value);patcher.start();self.addCleanup(patcher.stop)
        self.editor.action('tab:surface')

    def test_opening_surface_tab_is_nonmutating_and_all_pages_fit(self):
        e=self.editor
        for page in ('shape','flow','timing'):
            e.action('surface:page:'+page)
            buttons,fields=e.controls();rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
            for i,(name,a) in enumerate(rects):
                self.assertGreaterEqual(a[0],0,name);self.assertLessEqual(a[0]+a[2],1360,name)
                self.assertLessEqual(a[1]+a[3],710,name)
                for other,b in rects[i+1:]:
                    overlap=min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
                    self.assertFalse(overlap,(page,name,other))
        self.assertEqual(e.state.document,self.document)

    def test_surface_edits_keep_other_layers_and_undo(self):
        e=self.editor;quads=deepcopy(e.state.document['fog']);e.action('surface:enabled')
        self.assertTrue(e.state.surface_settings['enabled'])
        e.edit_number(('surface','wind',2));e.entry['text']='-1.5';self.assertTrue(e.finish_entry())
        self.assertEqual(e.state.surface_settings['wind'][2],-1.5)
        e.action('undo');self.assertEqual(e.state.surface_settings['wind'][2],-.31)
        e.action('surface:house_timing');self.assertFalse(e.state.surface_settings['use_building_timing'])
        self.assertEqual(e.state.document['fog'],quads)

    def test_timing_drag_is_single_undo_and_clamped_after_blend(self):
        e=self.editor;e.action('surface:enabled');e.action('surface:page:timing')
        self.assertEqual(e.surface_panel.clamp_time('reveal_start',0.),e.state.document['cues']['blend_end'])
        key,rect=next((key,rect) for key,rect in e.surface_panel.time_handles() if key=='reveal_end')
        start=e.state.surface_settings[key];count=len(e.state.undo_stack);mouse=(rect[0]+8,rect[1]+10)
        e.update(0.,Input(mouse=mouse,left_pressed=True,left_down=True))
        self.assertEqual(e.drag['kind'],'surface_time')
        e.update(0.,Input(mouse=(e.x_at(36.),mouse[1]),left_down=True))
        e.update(0.,Input(mouse=(e.x_at(36.),mouse[1]),left_released=True))
        self.assertAlmostEqual(e.state.surface_settings[key],36.,places=1)
        self.assertEqual(len(e.state.undo_stack),count+1)
        e.action('undo');self.assertEqual(e.state.surface_settings[key],start)

    def test_shared_quad_amount_and_house_window_editor(self):
        e=self.editor;e.action('surface:enabled');e.state.select_target('house-423')
        e.edit_number(('vol_global','particle_mix'));e.entry['text']='0.25';self.assertTrue(e.finish_entry())
        self.assertEqual(e.state.volume_settings['particle_mix'],.25)
        self.assertFalse(e.state.volume_settings['enabled'])
        e.action('surface:house');self.assertEqual(e.tab,'fog');self.assertEqual(e.state.target_id,'house-423')
        e.action('tab:surface');e.action('surface:frame')
        self.assertEqual(e.inspection['target'],list(e.state.target.center))

    def test_live_f8_surface_edits_keep_playhead_and_camera(self):
        e=self.editor;e.action('surface:enabled');e.action('save');e.state.seek(10.5)
        e.inspection=dict(eye=[7.,4.,-2.],target=[0.,1.,0.],fov=62.);before=deepcopy(e.inspection)
        e.selection.enabled=True
        remote=deepcopy(e.state.document);remote['surface_fog']['pattern_amount']=.4;save_direction(remote,self.path)
        e.poll_external(now=0.);e.poll_external(now=.3)
        self.assertEqual(e.state.surface_settings['pattern_amount'],.4)
        self.assertEqual(self.scene.sequence.direction.surface_fog.pattern_amount,.4)
        self.assertEqual(e.state.elapsed,10.5);self.assertEqual(e.inspection,before)
        self.assertTrue(e.selection.enabled)

    def test_build_number_entry_delays_geometry_and_moves_fallback_in_one_undo(self):
        e=self.editor;e.action('surface:enabled');before=deepcopy(e.state.document)
        count=len(e.state.undo_stack)
        e.edit_number(('surface','build_end'));e.entry['text']='8.0'
        self.assertTrue(e.finish_entry())
        e.state.seek(6.);e.sync()
        self.assertEqual(e.state.surface_settings['build_end'],8.)
        self.assertEqual(e.state.surface_settings['reveal_start'],9.)
        self.assertEqual(self.scene.sequence.world_blend,0.)
        self.assertEqual(self.scene.sequence.entry_duration,9.)
        self.assertTrue(self.scene.sequence.movement_locked)
        self.assertEqual(len(e.state.undo_stack),count+1)
        e.action('undo');self.assertEqual(e.state.document,before)

    def test_build_drag_restores_dependent_windows_when_dragged_back(self):
        e=self.editor;e.action('surface:enabled');e.action('surface:page:timing')
        initial=deepcopy(e.state.surface_settings);count=len(e.state.undo_stack)
        _,rect=next((key,rect) for key,rect in e.surface_panel.time_handles() if key=='build_end')
        mouse=(rect[0]+8,rect[1]+10)
        e.update(0.,Input(mouse=mouse,left_pressed=True,left_down=True))
        e.update(0.,Input(mouse=(e.x_at(10.),mouse[1]),left_down=True))
        self.assertEqual(e.state.surface_settings['reveal_start'],11.)
        e.update(0.,Input(mouse=(e.x_at(6.),mouse[1]),left_down=True))
        self.assertEqual(e.state.surface_settings['reveal_start'],initial['reveal_start'])
        e.update(0.,Input(mouse=(e.x_at(6.),mouse[1]),left_released=True))
        self.assertEqual(e.state.surface_settings['build_end'],6.)
        self.assertEqual(len(e.state.undo_stack),count+1)
        e.action('undo');self.assertEqual(e.state.surface_settings,initial)

    def test_rise_mode_percentage_controls_and_mode_switch_preserve_settings(self):
        e=self.editor;e.action('surface:evolution')
        self.assertEqual(e.state.profile.surface_fog.evolution,'rise_resolve')
        self.assertEqual(e.field_value(('surface','initial_scale')),40.)
        e.edit_number(('surface','initial_scale'));e.entry['text']='35'
        self.assertTrue(e.finish_entry());self.assertEqual(e.state.profile.surface_fog.initial_scale,.35)
        e.action('surface:page:timing')
        self.assertEqual(e.field_value(('surface','settle_fraction')),65.)
        e.edit_number(('surface','settle_fraction'));e.entry['text']='72'
        self.assertTrue(e.finish_entry());self.assertEqual(e.state.profile.surface_fog.settle_fraction,.72)
        for page in ('shape','flow','timing'):
            e.action('surface:page:'+page)
            buttons,fields=e.controls()
            rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
            for i,(name,a) in enumerate(rects):
                self.assertLessEqual(a[1]+a[3],710,name)
                for other,b in rects[i+1:]:
                    overlap=min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
                    self.assertFalse(overlap,(page,name,other))
        e.action('surface:evolution');self.assertEqual(e.state.profile.surface_fog.evolution,'condense')
        e.action('surface:evolution');self.assertEqual(e.state.profile.surface_fog.evolution,'erode')
        e.action('surface:evolution')
        self.assertEqual(e.field_value(('surface','initial_scale')),35.)
        self.assertEqual(e.field_value(('surface','settle_fraction')),72.)
        self.assertNotIn('base_y',e.state.surface_settings)

    def test_condense_controls_fit_edit_in_native_units_and_undo_without_changing_others(self):
        e=self.editor;e.action('surface:evolution');e.action('surface:evolution')
        self.assertEqual(e.state.profile.surface_fog.evolution,'condense')
        quads=deepcopy(e.state.document['fog']);before=deepcopy(e.state.document)
        self.assertEqual(e.field_value(('surface','pull_duration')),1.15)
        self.assertEqual(e.field_value(('surface','wisp_amount')),.35)
        for path,value,expected in ((('surface','settle_fraction'),'50',.5),
                                    (('surface','pull_duration'),'0.9',.9),
                                    (('surface','wisp_amount'),'0.6',.6)):
            e.edit_number(path);e.entry['text']=value;self.assertTrue(e.finish_entry())
            self.assertEqual(getattr(e.state.profile.surface_fog,path[1]),expected)
        self.assertEqual(e.state.document['fog'],quads)
        for page in ('shape','flow','timing'):
            e.action('surface:page:'+page);buttons,fields=e.controls()
            rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
            for i,(name,a) in enumerate(rects):
                self.assertGreaterEqual(a[0],0,name);self.assertLessEqual(a[0]+a[2],1360,name)
                self.assertLessEqual(a[1]+a[3],710,name)
                for other,b in rects[i+1:]:
                    overlap=min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
                    self.assertFalse(overlap,(page,name,other))
            paths={path for path,_ in fields}
            if page=='flow':
                self.assertIn(('surface','wisp_amount'),paths)
                self.assertIn(('surface','texture_grit'),paths)
                self.assertIn(('surface','pixel_grain'),paths)
            if page=='shape':
                self.assertIn('surface:water_mask',{name for name,_,_,_ in buttons})
                self.assertIn('surface:wispy_formation',{name for name,_,_,_ in buttons})
            if page=='timing':
                self.assertIn(('surface','pull_duration'),paths)
                self.assertIn(('surface','settle_fraction'),paths)
        for _ in range(3):e.action('undo')
        self.assertEqual(e.state.document,before)

    def test_condense_invalid_number_entry_keeps_saved_value_and_mode_cycle_preserves_options(self):
        e=self.editor;e.action('surface:evolution');e.action('surface:evolution')
        e.edit_number(('surface','pull_duration'));e.entry['text']='1.4';self.assertTrue(e.finish_entry())
        e.edit_number(('surface','pull_duration'));e.entry['text']='0';self.assertFalse(e.finish_entry())
        e.entry=None
        self.assertEqual(e.state.profile.surface_fog.pull_duration,1.4)
        for mode in ('erode','rise_resolve','condense'):
            e.action('surface:evolution')
            self.assertEqual(e.state.profile.surface_fog.evolution,mode)
            self.assertEqual(e.state.profile.surface_fog.pull_duration,1.4)

    def test_slow_condense_controls_accept_long_pulls_grit_and_water_toggle_with_undo(self):
        e=self.editor;e.action('surface:evolution');e.action('surface:evolution')
        self.assertEqual(e.field_value(('surface','texture_grit')),0.)
        e.edit_number(('surface','pull_duration'));e.entry['text']='7';self.assertTrue(e.finish_entry())
        e.edit_number(('surface','texture_grit'));e.entry['text']='0.65';self.assertTrue(e.finish_entry())
        e.action('surface:water_mask')
        self.assertEqual(e.state.profile.surface_fog.pull_duration,7.)
        self.assertEqual(e.state.profile.surface_fog.texture_grit,.65)
        self.assertTrue(e.state.profile.surface_fog.water_mask)
        e.action('save');e.action('reload')
        self.assertEqual(e.state.profile.surface_fog.pull_duration,7.)
        self.assertTrue(e.state.profile.surface_fog.water_mask)
        e.action('surface:water_mask');self.assertFalse(e.state.profile.surface_fog.water_mask)
        e.action('undo');self.assertTrue(e.state.profile.surface_fog.water_mask)

    def test_wispy_and_pixel_controls_save_undo_and_keep_the_24_second_handoff_safe(self):
        e=self.editor;e.action('surface:enabled');e.action('surface:evolution');e.action('surface:evolution')
        quads=deepcopy(e.state.document['fog'])
        self.assertEqual(e.field_value(('surface','pixel_grain')),0.)
        e.action('surface:wispy_formation');self.assertTrue(e.state.profile.surface_fog.wispy_formation)
        e.edit_number(('surface','pixel_grain'));e.entry['text']='0.85';self.assertTrue(e.finish_entry())
        self.assertEqual(e.state.profile.surface_fog.pixel_grain,.85)
        e.action('undo');self.assertEqual(e.state.profile.surface_fog.pixel_grain,0.)
        e.action('redo');self.assertEqual(e.state.profile.surface_fog.pixel_grain,.85)
        e.edit_number(('surface','build_end'));e.entry['text']='24';self.assertTrue(e.finish_entry())
        self.assertEqual(e.state.profile.surface_fog.build_end,24.)
        self.assertEqual(e.state.profile.surface_fog.reveal_start,25.)
        e.state.seek(23.);e.sync()
        self.assertEqual(self.scene.sequence.entry_duration,25.)
        self.assertEqual(self.scene.sequence.world_blend,0.)
        self.assertEqual(e.state.document['fog'],quads)
        e.action('save');e.action('reload')
        self.assertTrue(e.state.profile.surface_fog.wispy_formation)
        self.assertEqual(e.state.profile.surface_fog.pixel_grain,.85)
        self.assertEqual(e.state.profile.surface_fog.build_end,24.)

    def test_live_wispy_controls_preserve_selection_camera_and_playhead(self):
        e=self.editor;e.action('surface:enabled');e.action('surface:evolution');e.action('surface:evolution')
        e.action('save');e.state.seek(18.5)
        e.inspection=dict(eye=[5.,2.,3.],target=[0.,1.,0.],fov=64.)
        before=deepcopy(e.inspection);e.selection.enabled=True
        remote=deepcopy(e.state.document);remote['surface_fog'].update(wispy_formation=True,pixel_grain=.7)
        save_direction(remote,self.path);e.poll_external(now=0.);e.poll_external(now=.3)
        self.assertTrue(e.state.profile.surface_fog.wispy_formation)
        self.assertEqual(e.state.profile.surface_fog.pixel_grain,.7)
        self.assertEqual(e.state.elapsed,18.5);self.assertEqual(e.inspection,before)
        self.assertTrue(e.selection.enabled)


if __name__=='__main__':unittest.main()
