"""Live file edits through the real editor controller, without a window/audio."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import building_document, save_direction
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_editor import Editor, Input


class LiveEditorControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='haunted-live-ui-')
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'direction.json'
        self.document=building_document()
        save_direction(self.document,self.path)
        self.scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        self.editor=Editor(self.scene,path=self.path,live_input=False,
                           selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(self.editor.close)
        self.editor.state.select_target('house-410')
        self.editor.state.seek(11.125)

    def external(self,identity='house-410',opacity=.4):
        document=deepcopy(self.document)
        document['fog']['groups'][identity]['opacity']=opacity
        save_direction(document,self.path)
        return document

    def poll(self,start=0.):
        self.editor.poll_external(now=start)
        self.editor.poll_external(now=start+.3)

    def test_f8_pause_still_reloads_and_retains_inspection_and_target(self):
        e=self.editor
        e.selection.enabled=True
        e.inspection=dict(eye=[7.,4.,-2.],target=[0.,1.,0.],fov=62.)
        old_view=deepcopy(e.inspection)
        document=self.external()
        poll=e.state.poll_external
        for now in (0.,.3):
            with patch.object(e.state,'poll_external',side_effect=lambda **kw:poll(now=now,busy=kw['busy'])):
                e.update(0.,Input())
        self.assertEqual(e.state.document,document)
        self.assertEqual(e.state.target_id,'house-410')
        self.assertEqual(e.state.elapsed,11.125)
        self.assertEqual(e.inspection,old_view)
        self.assertTrue(e.selection.enabled)
        self.assertEqual(self.scene.sequence.direction.group('house-410').opacity,.4)
        # Repeated successful reloads share the same status text. They still
        # update the paused scene even when no new status message is emitted.
        self.external(opacity=.2)
        self.poll(1.)
        self.assertEqual(self.scene.sequence.direction.group('house-410').opacity,.2)

    def test_unfinished_number_is_merged_only_after_commit(self):
        e=self.editor
        e.edit_number(('opacity',));e.entry['text']='0.55';e.entry['replace']=False
        self.external('house-423',.35)
        self.poll()
        self.assertEqual(e.state.group['opacity'],1.)
        self.assertEqual(e.state.document['fog']['groups']['house-423']['opacity'],1.)
        self.assertTrue(e.finish_entry())
        e.poll_external(now=.6)
        self.assertEqual(e.state.group['opacity'],.55)
        self.assertEqual(e.state.document['fog']['groups']['house-423']['opacity'],.35)
        self.assertTrue(e.state.dirty)

    def test_live_toggle_and_conflict_buttons_preserve_undo(self):
        e=self.editor
        e.action('live');self.external()
        self.poll()
        self.assertEqual(e.state.group['opacity'],1.)
        e.action('live');self.poll(1.)
        self.assertEqual(e.state.group['opacity'],.4)
        e.state.set_group('opacity',.65)
        self.document=deepcopy(e.state.saved)
        self.external(opacity=.25);self.poll(2.)
        self.assertTrue(e.state.external_pending)
        self.assertEqual(e.state.group['opacity'],.65)
        with patch('huxin_canals_editor.pr.get_screen_width',return_value=1360),patch('huxin_canals_editor.pr.get_screen_height',return_value=900):
            buttons,fields=e.controls()
            self.assertIn('use_file',[name for name,*_ in buttons])
            self.assertIn('keep_mine',[name for name,*_ in buttons])
            rects=[(name,rect) for name,_,rect,_ in buttons]+[(str(path),rect) for path,rect in fields]
            for i,(name,a) in enumerate(rects):
                for other,b in rects[i+1:]:
                    overlaps=(min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and
                              min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1]))
                    self.assertFalse(overlaps,(name,other))
        e.action('use_file')
        self.assertEqual(e.state.group['opacity'],.25)
        self.assertFalse(e.state.external_pending)
        e.action('undo')
        self.assertEqual(e.state.group['opacity'],.65)


if __name__=='__main__':unittest.main()
