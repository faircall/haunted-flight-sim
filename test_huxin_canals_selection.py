"""CPU selection ownership across the independently rendered world endpoints."""
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

os.environ['HAUNTED_MUTE_AUDIO']='1'
import pyray as pr
from g_huxin_canals_sequence import (CanalSequence,WORLD_BLEND_START,WORLD_BLEND_END,
                                    ENTRY_SWAP,ENTRY_DURATION)
from huxin_canals_viewer import Lake
from temple_interior_viewer import camera


class CanalBlendSelectionTests(unittest.TestCase):
    def setUp(self):
        self.lake=lake=Lake.__new__(Lake)
        lake.sequence=CanalSequence();lake.sequence.state='canals';lake.sequence.revealed=True;lake.sequence.elapsed=ENTRY_DURATION
        lake._world_override=None;lake._codex_frame_paused=False
        lake.last_camera=camera((4.05,3.2,3.05),(-.7,1.5,-1.2),78);lake.last_shot=5
        lake.frame=SimpleNamespace(texture=object())
        lake.blend_old_frame=SimpleNamespace(texture=object());lake.blend_new_frame=SimpleNamespace(texture=object())
        lake.blend_shader=object();self.poses=[]
        lake.player=SimpleNamespace(clips={'idle'},pose=lambda *args:self.poses.append(args))
        self.records=[]
        lake.codex_selection=SimpleNamespace(enabled=True,
            register_model=lambda model,name,*args,**kwargs:self.records.append((name,kwargs.get('metadata'))))
        lake.models={name:object() for name in ('pavilion_posts','causeway','lake_bank','canal_ground')}
        self.actor=SimpleNamespace(x=1.65,height=.325,z=1.65,yaw=0.,clip='idle',phase=0.,shot=5)
        lake.sequence.locked_camera=lake.last_camera;lake.sequence.locked_shot=lake.last_shot;lake.sequence.locked_pose=(1.65,.325,1.65,0.)
        self.endpoints=[]

        def endpoint(*args):
            self.endpoints.append((lake.render_revealed,lake.water_y,lake.sequence.revealed))
            lake.draw('pavilion_posts');lake.draw('causeway')
            lake.draw('canal_ground' if lake.render_revealed else 'lake_bank')
        lake._render_world_frame=endpoint
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name in ('begin_texture_mode','clear_background','begin_shader_mode','set_shader_value',
                     'set_shader_value_texture','draw_texture_pro','end_shader_mode','end_texture_mode','draw_model_ex'):
            self.stack.enter_context(patch.object(pr,name))
        self.stack.enter_context(patch.object(pr,'get_shader_location',return_value=0))

    def test_smooth_blend_captures_one_world_and_one_shared_pavilion(self):
        lake=self.lake;q=lake.sequence
        for elapsed in (0.,WORLD_BLEND_START,WORLD_BLEND_START+.25,
                        (WORLD_BLEND_START+WORLD_BLEND_END)/2,ENTRY_DURATION-.001,
                        ENTRY_DURATION,ENTRY_DURATION+.001,ENTRY_DURATION+1.):
            with self.subTest(elapsed=elapsed):
                q.elapsed=elapsed;q.state='entering' if elapsed<ENTRY_DURATION else 'canals';q.revealed=elapsed>=ENTRY_SWAP
                self.records.clear();self.endpoints.clear();self.poses.clear()
                original=lake.codex_selection;logical=(q.state,q.elapsed,q.revealed)
                lake.render(self.actor,87.)
                selected_world=q.world_blend>=.5
                names=[name for name,_ in self.records]
                self.assertEqual(names.count('pavilion_posts'),1)
                self.assertEqual(names.count('causeway'),1)
                self.assertIn('canal_ground' if selected_world else 'lake_bank',names)
                self.assertNotIn('lake_bank' if selected_world else 'canal_ground',names)
                # The captured old causeway must retain its old-world shader
                # visibility, independently of the timed gameplay commit.
                metadata=next(m for name,m in self.records if name=='causeway')
                self.assertEqual(metadata['_reject_hit']((0.,.325,20.)),selected_world)
                self.assertIs(lake.codex_selection,original);self.assertIsNone(lake._world_override)
                self.assertEqual((q.state,q.elapsed,q.revealed),logical)
                self.assertEqual(lake.last_world_weights,{'lake':1.-q.world_blend,'canals':q.world_blend})
                self.assertEqual(len(self.poses),1);self.assertEqual(self.poses[0][-1],0.)
                self.assertEqual(len(self.endpoints),2 if 0.<q.world_blend<1. else 1)
                self.assertTrue(all(commit==logical[2] for _,_,commit in self.endpoints))

    def test_nondominant_endpoint_restores_selection_and_world_after_failure(self):
        lake=self.lake;session=lake.codex_selection
        def fail(*args):
            self.assertIsNone(lake.codex_selection)
            self.assertFalse(lake.render_revealed);self.assertEqual(lake.water_y,0.)
            self.assertTrue(lake.sequence.revealed)
            raise RuntimeError('fixture endpoint failure')
        lake._render_world_frame=fail
        with self.assertRaisesRegex(RuntimeError,'fixture endpoint failure'):
            lake._render_world(self.actor,lake.last_camera,87.,False,True,False,False,lake.frame,False)
        self.assertIs(lake.codex_selection,session);self.assertIsNone(lake._world_override)
        self.assertTrue(lake.sequence.revealed)

    def test_selection_closing_frame_keeps_pose_frozen_until_following_frame(self):
        lake=self.lake;lake.sequence.elapsed=ENTRY_DURATION-.001
        lake.sequence.state='entering';lake.sequence.revealed=False
        for enabled,blocked,expected in ((True,True,0.),(False,True,0.),(False,False,1/60)):
            lake.codex_selection.enabled=enabled;lake._codex_frame_paused=blocked
            self.poses.clear();lake.render(self.actor,87.)
            self.assertEqual(len(self.poses),1)
            self.assertEqual(self.poses[0][-1],expected)


if __name__=='__main__':unittest.main()
