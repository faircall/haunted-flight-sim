"""Real volume editing controller paths, without opening a graphics device."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import building_document, save_direction
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_editor import Editor, Input


class VolumeEditorControllerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='haunted-volume-ui-');self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'volumes.json';self.document=building_document()
        save_direction(self.document,self.path)
        self.scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        self.editor=Editor(self.scene,path=self.path,live_input=False,selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(self.editor.close)
        for name,value in (('get_screen_width',1360),('get_screen_height',900)):
            patcher=patch('huxin_canals_editor.pr.'+name,return_value=value);patcher.start();self.addCleanup(patcher.stop)
        self.editor.action('tab:volumes')

    def test_three_pages_fit_without_overlap_and_keep_existing_tabs(self):
        e=self.editor
        for added in (False,True):
            if added:e.action('vol:add:box')
            for page in ('shape','flow','timing'):
                e.action('vol:page:'+page)
                buttons,fields=e.controls();names=[name for name,*_ in buttons]
                self.assertTrue({'tab:fog','tab:camera','tab:volumes'}<=set(names))
                rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
                for i,(name,a) in enumerate(rects):
                    self.assertGreaterEqual(a[0],0,name);self.assertLessEqual(a[0]+a[2],1360,name)
                    self.assertLessEqual(a[1]+a[3],710,name)
                    for other,b in rects[i+1:]:
                        overlap=min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
                        self.assertFalse(overlap,(page,name,other))

    def test_create_edit_duplicate_delete_and_undo_leave_quad_data_intact(self):
        e=self.editor;e.state.seek(5.25);quads=deepcopy(e.state.document['fog'])
        e.action('vol:add:ellipsoid');first=e.state.volume_id
        e.edit_number(('vol','label'));e.entry['text']='Water beside the western stairs'
        self.assertTrue(e.finish_entry());self.assertEqual(e.state.volume['label'],'Water beside the western stairs')
        e.edit_number(('vol','center',0));e.entry['text']='-17.25'
        self.assertTrue(e.finish_entry());self.assertEqual(e.state.volume['center'][0],-17.25)
        e.action('vol:duplicate');second=e.state.volume_id
        self.assertNotEqual(first,second);self.assertEqual(len(e.state.volume_regions),2)
        e.action('vol:remove');self.assertEqual(len(e.state.volume_regions),1)
        e.action('undo');self.assertIn(second,e.state.volume_regions)
        self.assertEqual(e.state.document['fog'],quads);self.assertEqual(e.state.elapsed,5.25)

    def test_fit_building_and_layer_presets_are_independent(self):
        e=self.editor
        e.selection.enabled=True;e.selection.selected=[{'fog_target':'house-410'}]
        e.update(0.,Input(pressed={'F8'}));target=e.state.target
        self.assertEqual(target.id,'house-410')
        e.action('vol:fit')
        self.assertEqual(e.state.volume['center'],list(target.center))
        self.assertTrue(all(a>=b for a,b in zip(e.state.volume['half_extents'],target.half_extents)))
        region=deepcopy(e.state.volume);quads=deepcopy(e.state.document['fog'])
        for preset,enabled,particles in (('quads',False,1.),('volume',True,0.),('hybrid',True,1.)):
            e.action('vol:preset:'+preset)
            self.assertEqual(e.state.volume_settings['enabled'],enabled)
            self.assertEqual(e.state.volume_settings['particle_mix'],particles)
            self.assertEqual(e.state.volume,region);self.assertEqual(e.state.document['fog'],quads)
        e.action('vol:frame');self.assertEqual(e.inspection['target'],region['center'])

    def test_volume_drag_is_one_undo_transaction(self):
        e=self.editor;e.action('vol:add:box');start=e.state.volume['center'][0];count=len(e.state.undo_stack)
        handle=(0,(480,190,18,18),(400,200),(489,200))
        with patch.object(e,'gizmo_handles',return_value=[handle]):
            e.update(0.,Input(mouse=(489,200),left_pressed=True,left_down=True))
            self.assertEqual(e.drag['kind'],'volume')
            e.update(0.,Input(mouse=(578,200),left_down=True))
            e.update(0.,Input(mouse=(578,200),left_released=True))
        self.assertAlmostEqual(e.state.volume['center'][0],start+3.)
        self.assertEqual(len(e.state.undo_stack),count+1)
        e.action('undo');self.assertEqual(e.state.volume['center'][0],start)

    def test_timing_handles_clamp_against_hidden_blend(self):
        e=self.editor;e.action('vol:add:box');e.action('vol:page:timing')
        region=e.state.volume
        self.assertEqual(e.volume_panel.clamp_time('reveal_start',0.),e.state.document['cues']['blend_end'])
        self.assertLess(e.volume_panel.clamp_time('fade_in_start',1000.),region['fade_in_end'])
        key,rect=next((key,rect) for key,rect in e.volume_panel.time_handles() if key=='reveal_end')
        mouse=(rect[0]+8,rect[1]+10);count=len(e.state.undo_stack)
        e.update(0.,Input(mouse=mouse,left_pressed=True,left_down=True))
        self.assertEqual(e.drag['kind'],'volume_time')
        e.update(0.,Input(mouse=(e.x_at(29.),mouse[1]),left_down=True))
        e.update(0.,Input(mouse=(e.x_at(29.),mouse[1]),left_released=True))
        self.assertAlmostEqual(e.state.volume[key],29.,places=1)
        self.assertEqual(len(e.state.undo_stack),count+1)

    def test_custom_path_save_and_live_volume_reload(self):
        e=self.editor;e.action('vol:add:box');e.action('save')
        e.selection.enabled=True;identity=e.state.volume_id
        remote=deepcopy(e.state.document);remote['volumes']['regions'][identity]['wind'][0]=1.5
        save_direction(remote,self.path)
        e.poll_external(now=0.);e.poll_external(now=.3)
        self.assertEqual(e.state.volume['wind'][0],1.5)
        self.assertTrue(e.selection.enabled);self.assertEqual(e.state.volume_id,identity)
        self.assertEqual(self.scene.sequence.direction.volumes.region(identity).wind[0],1.5)


if __name__=='__main__':unittest.main()
