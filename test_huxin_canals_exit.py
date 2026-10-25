"""Discard exits safely even when live files cannot be loaded."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from g_huxin_canals_direction import default_document,save_direction
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_editor import Editor,Input


class EditorExitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='canals-exit-')
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'direction.json'
        self.document=default_document();save_direction(self.document,self.path)
        self.scene=SimpleNamespace(sequence=CanalSequence(),last_camera=None,last_shot=5)
        self.previous=self.scene.sequence
        self.editor=Editor(self.scene,path=self.path,live_input=False,
                           selection_output_path=self.path.parent/'selection.json')
        self.addCleanup(self.editor.close)
        for name,value in (('get_screen_width',1440),('get_screen_height',900)):
            p=patch('huxin_canals_editor.pr.'+name,return_value=value)
            p.start();self.addCleanup(p.stop)
        self.editor.state.set_bank('opacity',.55)

    def click(self,name):
        rect=next(rect for key,_,rect,_ in self.editor.controls()[0] if key==name)
        self.editor.update(0.,Input(mouse=(rect[0]+rect[2]/2,rect[1]+rect[3]/2),left_pressed=True))

    def test_discard_exits_with_invalid_unsupported_or_missing_live_file(self):
        future=deepcopy(self.document);future['unsupported_future_setting']=True
        for data in (b'{invalid',json.dumps(future).encode(),None):
            with self.subTest(data=data):
                e=self.editor;e.closed=False
                e.state.set_bank('opacity',.55)
                if data is None:self.path.unlink(missing_ok=True)
                else:self.path.write_bytes(data)
                # An error in the live watcher is also external_pending.
                e.state.watcher.error='Cannot load live direction'
                self.click('close');self.assertTrue(e.close_prompt)
                self.click('close_discard')
                self.assertTrue(e.closed,e.status)
                self.assertFalse(e.close_prompt);self.assertFalse(e.state.dirty)
                self.assertEqual(e.state.document,self.document)
                self.assertEqual(self.path.read_bytes() if self.path.exists() else None,data)

    def test_discard_uses_latest_valid_external_file_without_saving_local_edits(self):
        remote=deepcopy(self.document);remote['banks']['near']['opacity']=.25
        save_direction(remote,self.path);before=self.path.read_bytes()
        self.editor.poll_external(now=0.);self.editor.poll_external(now=.3)
        self.assertTrue(self.editor.state.external_pending)
        self.click('close');self.click('close_discard')
        self.assertTrue(self.editor.closed)
        self.assertEqual(self.editor.state.document,remote)
        self.assertEqual(self.path.read_bytes(),before)
        self.editor.close();self.assertIs(self.scene.sequence,self.previous)

    def test_cancel_keeps_edits_and_failed_save_keeps_dialog_open(self):
        self.click('close');self.click('close_cancel')
        self.assertFalse(self.editor.closed);self.assertFalse(self.editor.close_prompt)
        self.assertEqual(self.editor.state.bank['opacity'],.55)
        self.path.write_bytes(b'{invalid');self.click('close');self.click('close_save')
        self.assertFalse(self.editor.closed);self.assertTrue(self.editor.close_prompt)
        self.assertTrue(self.editor.close_error)
        self.assertEqual(self.path.read_bytes(),b'{invalid')
        self.click('close_discard');self.assertTrue(self.editor.closed)

    def test_normal_save_and_return_saves_then_exits(self):
        self.click('close');self.click('close_save')
        self.assertTrue(self.editor.closed);self.assertFalse(self.editor.state.dirty)
        self.assertEqual(json.loads(self.path.read_bytes())['banks']['near']['opacity'],.55)

    def test_invalid_number_can_be_kept_or_discarded_without_validation_trap(self):
        e=self.editor;before=self.path.read_bytes()
        e.edit_number(('opacity',));e.entry['text']='not a number'
        self.click('close');self.assertTrue(e.close_prompt)
        self.click('close_cancel')
        self.assertEqual(e.entry['text'],'not a number')
        self.assertEqual(e.state.bank['opacity'],.55)
        self.click('close');self.click('close_save')
        self.assertFalse(e.closed);self.assertTrue(e.close_prompt)
        self.assertTrue(e.close_error)
        self.click('close_discard')
        self.assertTrue(e.closed);self.assertIsNone(e.entry)
        self.assertEqual(self.path.read_bytes(),before)

    def test_close_button_still_works_in_selection_mode(self):
        self.editor.selection.enabled=True
        self.click('close');self.assertTrue(self.editor.close_prompt)
        self.click('close_discard');self.assertTrue(self.editor.closed)


if __name__=='__main__':unittest.main()
