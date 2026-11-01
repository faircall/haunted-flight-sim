"""Comparison controls and non-destructive in-scene player swapping."""
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest

from compare_player_3d import CompareState,controls,inside
from g_temple_living import animation_samples
from huxin_moon_viewer import Lake


def player(name,shader):
    return SimpleNamespace(variant=name,skin=SimpleNamespace(id=shader),
                           clips={'idle':0,'walk':1,'run':2},pose=Mock(),close=Mock())


class PlayerVariantRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.scene=object.__new__(Lake);self.original=player('original',2)
        self.candidate=player('refined',3);self.scene.player=self.original
        self.scene._player_variants={'original':self.original};self.scene.locations={}
        self.scene.sequence=SimpleNamespace(state='revealed',inventory=['keep'])

    def test_switch_reuses_both_rigs_and_keeps_gameplay_and_sample_phase(self):
        sequence=self.scene.sequence
        with patch('huxin_moon_viewer.LivingScene',return_value=self.candidate) as construct, \
             patch('huxin_moon_viewer.pr.get_shader_location',return_value=7):
            self.assertEqual(self.scene.set_player_variant('refined','run',.37),'refined')
            self.assertIs(self.scene.player,self.candidate)
            self.candidate.pose.assert_called_once_with('run',.37)
            self.assertEqual(self.scene.set_player_variant('original','walk',.61),'original')
            self.original.pose.assert_called_once_with('walk',.61)
            self.scene.set_player_variant('refined','run',.75)
            construct.assert_called_once()
        self.assertIs(self.scene.sequence,sequence);self.assertEqual(sequence.inventory,['keep'])

    def test_failed_load_leaves_old_player_in_place(self):
        with patch('huxin_moon_viewer.LivingScene',side_effect=RuntimeError('Unavailable')):
            with self.assertRaisesRegex(RuntimeError,'Unavailable'):self.scene.set_player_variant('refined')
        self.assertIs(self.scene.player,self.original)
        self.assertEqual(set(self.scene._player_variants),{'original'})
        with self.assertRaises(ValueError):self.scene.set_player_variant('unknown')

    def test_review_uses_game_stride_and_frame_controls(self):
        from g_huxin_moon import PLAYER_SCALE
        from g_player_locomotion import SETTINGS,stride_for
        s=CompareState();walk_period=s.period;s.action('clip:run')
        self.assertAlmostEqual(walk_period,SETTINGS['walk']['stride']*PLAYER_SCALE/1.55)
        self.assertAlmostEqual(s.period,SETTINGS['run']['stride']*PLAYER_SCALE/3.15)
        s.action('next');self.assertFalse(s.playing);self.assertAlmostEqual(s.phase,.017)
        s.action('clip:idle');s.action('next');self.assertAlmostEqual(s.phase,.0085)
        s.action('clip:walk_back');self.assertAlmostEqual(s.period,walk_period)
        s.action('view:front');self.assertEqual((s.azimuth,s.elevation),(0.,7.))
        s.action('timing');self.assertTrue(s.compare_run_timing)
        s.action('clip:run');s.cycles=.3
        self.assertAlmostEqual(s.display_phase(True)*stride_for('run','sprint'),s.display_phase()*stride_for('run'))
        s.action('timing');self.assertFalse(s.compare_run_timing)
        self.assertTrue(all(not inside(a[2],b[2][0]+1,b[2][1]+1)
                            for i,a in enumerate(controls(s)) for b in controls(s)[i+1:]))

    def test_subframe_sampling_wraps_smoothly_at_real_clip_end(self):
        self.assertEqual(animation_samples(0.,1.,59),(0,1,0.))
        a,b,w=animation_samples(.017,1.,59)
        self.assertEqual((a,b),(1,2));self.assertAlmostEqual(w,0.)
        a,b,w=animation_samples(.993,1.,59)
        self.assertEqual((a,b),(58,0));self.assertAlmostEqual(w,.5)
        self.assertGreater(animation_samples(.999999,1.,59)[2],.999)
        self.assertEqual(animation_samples(1.,1.,59),(0,1,0.))
        a,b,w=animation_samples(.998,2.,118)
        self.assertEqual((a,b),(117,0));self.assertGreater(w,.5)
        self.assertEqual(animation_samples(.4,1.,1),(0,0,0.))


if __name__=='__main__':unittest.main()
