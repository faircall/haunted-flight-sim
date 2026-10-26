"""State safety and quick-preview contracts for the teahouse renderer."""
import copy
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from g_huxin_moon import DECK
from g_huxin_moon_sequence import MoonSequence,SOLUTION,MARK,support
from huxin_moon_viewer import Lake,reset_player


class MoonTargetRuntimeTests(unittest.TestCase):
    def test_quick_preview_is_an_ordinary_aligned_puzzle_not_a_forced_swap(self):
        scene=SimpleNamespace()
        actor=reset_player(scene,puzzle=True)
        q=scene.sequence
        self.assertIs(actor.encounter,q)
        self.assertEqual((actor.x,actor.height,actor.z),(1.65,DECK,1.65))
        self.assertEqual((q.yaw,q.pitch),SOLUTION)
        self.assertEqual(q.state,'ordinary')
        self.assertFalse(q.revealed)
        self.assertFalse(q.focus)
        self.assertAlmostEqual(q.approach,1.)
        self.assertLess(sum((a-b)**2 for a,b in zip(q.hit(),MARK)),1.e-10)
        self.assertIsNotNone(support(actor.x,actor.z,actor.height,False))
        q.focus=True;q.tick(1.2,actor)
        self.assertEqual(q.state,'entering')
        self.assertEqual(q.events,['bell'])
        old=q
        reset_player(scene,puzzle=True)
        self.assertIsNot(scene.sequence,old)
        self.assertEqual(scene.sequence.state,'ordinary')

    def test_render_endpoints_never_modify_encounter_state_or_inventory(self):
        scene=object.__new__(Lake);scene.sequence=MoonSequence();scene._world_override=None
        q=scene.sequence;q.state='entering';q.elapsed=8.;q.revealed=True
        q.inventory[0]={'kind':'key','count':1}
        before=copy.deepcopy(vars(q));observed=[]
        scene._render_world_frame=lambda *args:observed.append(scene.render_revealed)
        for endpoint in (False,True):
            scene._render_world(None,None,12.,False,True,False,endpoint,None)
            self.assertIsNone(scene._world_override)
            self.assertEqual(vars(q),before)
        self.assertEqual(observed,[False,True])
        self.assertTrue(scene.render_revealed)

    def test_failed_endpoint_render_restores_the_previous_override(self):
        scene=object.__new__(Lake);scene.sequence=MoonSequence();scene._world_override=False
        scene._render_world_frame=Mock(side_effect=RuntimeError('render failed'))
        with self.assertRaisesRegex(RuntimeError,'render failed'):
            scene._render_world(None,None,12.,False,True,False,True,None)
        self.assertIs(scene._world_override,False)
        self.assertFalse(scene.render_revealed)


if __name__=='__main__':unittest.main()
