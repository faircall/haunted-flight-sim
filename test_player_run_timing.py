"""Checks for the isolated run-timing revision; no renderer or audio needed."""
import math
from pathlib import Path
import unittest

import numpy as np

from photo_asset_pipeline.temple3d.living import gait
import player_run_timing as revision
from test_player_refined_assets import animation_channel, glb, joints
from test_temple_living import accessor

ROOT = Path(__file__).resolve().parent


class PlayerRunTimingTests(unittest.TestCase):
    def test_peak_is_crossed_more_briskly_with_same_extreme_pose(self):
        h = 1e-5
        old = gait._run_swing_angles
        new = revision.swing_angles
        for phase in (.82, .84):
            def speed(fn): return abs((fn(phase+h)[0]-fn(phase-h)[0])/(2*h))
            self.assertGreater(speed(new), speed(old)*1.3)
        self.assertAlmostEqual(new(revision.DRIVE_PHASE)[0], old(revision.DRIVE_PHASE)[0], places=8)
        for phase in (revision.PASSING_PHASE, revision.DRIVE_PHASE, 1.):
            self.assertAlmostEqual(new(phase)[0], old(phase)[0], places=8)
            self.assertAlmostEqual((new(phase+h)[0]-new(phase-h)[0])/(2*h),
                                   (old(phase+h)[0]-old(phase-h)[0])/(2*h), places=2)

    def test_rear_recovery_keeps_moving_without_changing_support(self):
        h = 1e-5
        old = gait._run_swing_angles
        new = revision.swing_angles
        for phase in (.42, .44, .46):
            old_speed = (old(phase+h)[0]-old(phase-h)[0])/(2*h)
            new_speed = (new(phase+h)[0]-new(phase-h)[0])/(2*h)
            self.assertGreater(new_speed, old_speed*1.25)
        for phase in (gait.SETTINGS['run']['stance'], .38, .48):
            if phase != .38:
                self.assertAlmostEqual(new(phase)[0], old(phase)[0], places=8)
            left = (new(phase)[0]-new(phase-h)[0])/h
            right = (new(phase+h)[0]-new(phase)[0])/h
            self.assertAlmostEqual(left, right, places=2)

    def test_knee_opens_continuously_into_same_soft_landing(self):
        peak = gait.SETTINGS['run']['recovery_peak']
        samples = [revision.swing_angles(peak+(1.-peak)*i/600)[1] for i in range(601)]
        self.assertTrue(all(a >= b-1e-8 for a, b in zip(samples, samples[1:])))
        old = gait._run_swing_angles
        self.assertAlmostEqual(samples[-1], old(1.)[1], places=8)
        h = 1e-5
        for p in (peak, revision.DRIVE_PHASE, 1.):
            left = (revision.swing_angles(p)[1]-revision.swing_angles(p-h)[1])/h
            right = (revision.swing_angles(p+h)[1]-revision.swing_angles(p)[1])/h
            self.assertAlmostEqual(left, right, places=2)

    def test_ankle_does_not_stall_at_forward_reversal(self):
        def minimum_speed():
            h = .0001
            speeds = []
            for p in (i/10000 for i in range(8300, 8401)):
                before = gait.leg_3d('run', p-h)['ankle']
                after = gait.leg_3d('run', p+h)['ankle']
                speeds.append(math.dist(before, after)/(2*h))
            return min(speeds)
        original = minimum_speed()
        with revision.timing_revision():
            revised = minimum_speed()
        self.assertGreater(revised, original*1.05)

    def test_only_airborne_thigh_changes_and_shoes_stay_above_floor(self):
        original = gait._run_swing_angles
        baseline = [gait.foot('run', p/1000) for p in range(1000)]
        with revision.timing_revision():
            revised = [gait.foot('run', p/1000) for p in range(1000)]
            for p in range(1000):
                a, b = baseline[p], revised[p]
                if p/1000 < gait.SETTINGS['run']['stance']:
                    self.assertEqual(a, b)
                else:
                    self.assertGreaterEqual(b['clearance'], -1e-6, p)
                self.assertAlmostEqual(a['pitch'], b['pitch'])
                self.assertEqual(a['stance'], b['stance'])
        self.assertIs(gait._run_swing_angles, original)

    def test_export_retains_rig_upper_body_and_has_distinct_legs(self):
        original, data = glb(ROOT/'art'/'temple'/'combat'/'player.glb')
        revised, new_data = glb(ROOT/'art'/'temple'/'player_run_timing'/'run.glb')
        self.assertEqual(joints(original), joints(revised))
        np.testing.assert_allclose(accessor(original, data, original['skins'][0]['inverseBindMatrices']),
                                   accessor(revised, new_data, revised['skins'][0]['inverseBindMatrices']), atol=1e-5)
        self.assertEqual([a['name'] for a in revised['animations']], ['run'])
        for bone in ('root','spine','head','arm.L','forearm.L','hand.L','arm.R','forearm.R','hand.R'):
            for path in ('rotation','translation'):
                t, old = animation_channel(original, data, 'run', bone, path)
                u, new = animation_channel(revised, new_data, 'run', bone, path)
                np.testing.assert_allclose(t, u, atol=1e-6)
                np.testing.assert_allclose(old, new, atol=1e-5)
        for side in ('L', 'R'):
            _, old = animation_channel(original, data, 'run', 'thigh.'+side, 'rotation')
            _, new = animation_channel(revised, new_data, 'run', 'thigh.'+side, 'rotation')
            dot = np.abs(np.sum(old*new, axis=1))
            self.assertLess(float(dot.min()), .9999)
            self.assertAlmostEqual(abs(float(np.dot(new[0], new[-1]))), 1., places=4)


if __name__ == '__main__':
    unittest.main()
