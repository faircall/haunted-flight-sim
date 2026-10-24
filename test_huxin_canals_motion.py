"""Behavioral contracts for moving building fog, independent of rendering."""
from copy import deepcopy
import unittest

import numpy as np

from g_huxin_canals_direction import building_document, profile_from_document
from g_huxin_canals_particles import building_frame_at
from g_huxin_canals_targets import coverage_bounds, target_group


class BuildingFogMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = building_document()
        cls.profile = profile_from_document(cls.document)

    def profile_with(self, changes):
        document = deepcopy(self.document)
        for ident, values in changes.items():
            document['fog']['groups'][ident].update(values)
        return profile_from_document(document)

    @staticmethod
    def group(frame, ident):
        mask = frame.group_ids == ident
        return frame.ids[mask], frame.centers[mask], frame.alphas[mask]

    def assert_same_ids(self, *samples):
        for sample in samples[1:]:
            np.testing.assert_array_equal(samples[0][0], sample[0])

    def test_visible_circulation_continues_smoothly_across_five_and_six_seconds(self):
        # Follow both clocks as normal playback does. Births may stop at the
        # crest, but existing house clouds must visibly keep travelling.
        h = .01
        for boundary in (5., 6.):
            with self.subTest(boundary=boundary):
                frames = [building_frame_at(t, 87. + t, self.profile)
                          for t in (boundary-h, boundary, boundary+h)]
                ids = frames[0].ids
                for frame in frames[1:]:
                    np.testing.assert_array_equal(ids, frame.ids)
                houses = np.array([ident.startswith('house-')
                                   for ident in frames[0].group_ids])
                before = (frames[1].centers-frames[0].centers)[houses]/h
                after = (frames[2].centers-frames[1].centers)[houses]/h
                speeds = np.linalg.norm((before+after)*.5, axis=1)
                self.assertGreater(float(np.median(speeds)), .12)
                self.assertLess(float(np.median(speeds)), 1.2)
                # A reset, new clock or snapped position at either cue would
                # produce a large acceleration spike in these finite steps.
                self.assertLess(float(np.max(np.linalg.norm(after-before, axis=1))), .12)

    def test_recession_is_visible_before_opacity_starts_falling(self):
        profile = self.profile_with({'house-110': {'reveal_start': 8., 'reveal_end': 16.}})
        samples = [self.group(building_frame_at(t, 92., profile), 'house-110')
                   for t in (8., 8.9)]
        self.assert_same_ids(*samples)
        # Holding scene time isolates the reveal movement from idle rolling.
        moved = np.linalg.norm(samples[1][1]-samples[0][1], axis=1)
        self.assertGreater(float(np.median(moved)), .03)
        np.testing.assert_allclose(samples[1][2], samples[0][2], atol=1e-12, rtol=0.)

    def test_opposite_canal_banks_retreat_away_from_their_local_water(self):
        changes = {ident: {'reveal_start': 8., 'reveal_end': 16.}
                   for ident in ('house-110', 'house-211')}
        profile = self.profile_with(changes)
        start = building_frame_at(8., 92., profile)
        moving = building_frame_at(11., 92., profile)
        for ident in changes:
            with self.subTest(group=ident):
                a, b = self.group(start, ident), self.group(moving, ident)
                self.assert_same_ids(a, b)
                outward = np.sign(target_group(ident).center[0])
                retreat = (b[1][:, 0]-a[1][:, 0])*outward
                self.assertGreater(float(np.median(retreat)), .4)
                self.assertGreater(float(np.mean(retreat > 0.)), .9)

    def test_changing_one_reveal_does_not_move_other_building_curtains(self):
        early = self.profile_with({'house-110': {'reveal_start': 8., 'reveal_end': 16.}})
        late = self.profile_with({'house-110': {'reveal_start': 14., 'reveal_end': 22.}})
        a, b = (building_frame_at(11., 92., profile) for profile in (early, late))
        for name in ('ids', 'centers', 'alphas', 'widths', 'heights', 'rotations'):
            np.testing.assert_array_equal(getattr(a, name)[a.group_ids != 'house-110'],
                                          getattr(b, name)[b.group_ids != 'house-110'])
        first, second = self.group(a, 'house-110'), self.group(b, 'house-110')
        self.assert_same_ids(first, second)
        self.assertGreater(float(np.median(np.linalg.norm(first[1]-second[1], axis=1))), .4)

    def test_fade_lag_does_not_extend_authored_reveal_end(self):
        # Exercise a normal window and the editor's shortest legal window.
        for end in (8.1, 16.):
            with self.subTest(end=end):
                profile = self.profile_with({'house-110': {'reveal_start': 8., 'reveal_end': end}})
                peak = self.group(building_frame_at(8., 92., profile), 'house-110')
                faded = self.group(building_frame_at(end, 92., profile), 'house-110')
                self.assertTrue(np.isfinite(faded[1]).all())
                self.assertTrue(np.isfinite(faded[2]).all())
                self.assertLess(float(faded[2].sum()/peak[2].sum()), .015)

    def test_group_scale_and_offset_apply_to_the_complete_moving_envelope(self):
        ident = 'house-110'
        scale = 1.4
        offset = np.array((2.1, -.4, 1.3))
        transformed = self.profile_with({ident: {'scale': scale, 'offset': offset.tolist()}})
        center = np.array(target_group(ident).center)
        for elapsed in (5., 9., 12.):
            with self.subTest(elapsed=elapsed):
                a = building_frame_at(elapsed, 87.+elapsed, self.profile)
                b = building_frame_at(elapsed, 87.+elapsed, transformed)
                source, changed = self.group(a, ident), self.group(b, ident)
                self.assert_same_ids(source, changed)
                np.testing.assert_allclose(changed[1], center+(source[1]-center)*scale+offset,
                                           atol=1e-12, rtol=0.)
                np.testing.assert_array_equal(changed[2], source[2])
                for name in ('widths', 'heights'):
                    np.testing.assert_allclose(getattr(b, name)[b.group_ids == ident],
                                               getattr(a, name)[a.group_ids == ident]*scale,
                                               atol=1e-12, rtol=0.)

    def test_low_water_fog_does_not_rise_into_a_new_pavilion_curtain(self):
        identifiers = ('water-west-basin', 'water-east-basin', 'waterline-1', 'waterline-4')
        first = building_frame_at(5., 92., self.profile)
        for elapsed in (6., 9., 12., 16.):
            frame = building_frame_at(elapsed, 87.+elapsed, self.profile)
            for ident in identifiers:
                with self.subTest(elapsed=elapsed, group=ident):
                    a, b = self.group(first, ident), self.group(frame, ident)
                    _, ia, ib = np.intersect1d(a[0], b[0], return_indices=True)
                    self.assertGreater(len(ia), 0)
                    self.assertLess(float(np.max(np.abs(b[1][ib, 1]-a[1][ia, 1]))), .45)

    def test_scrubbing_reproduces_identical_read_only_motion_samples(self):
        a = building_frame_at(10.75, 97.75, self.profile)
        saved = {name: getattr(a, name).copy()
                 for name in ('ids', 'centers', 'widths', 'heights', 'rotations', 'alphas')}
        for t in (29., 1., 16., 5., 8., 2.):
            building_frame_at(t, 87.+t, self.profile)
        b = building_frame_at(10.75, 97.75, self.profile)
        for name, expected in saved.items():
            np.testing.assert_array_equal(getattr(a, name), expected)
            np.testing.assert_array_equal(getattr(b, name), expected)
            self.assertFalse(getattr(b, name).flags.writeable)

    def test_editor_envelopes_contain_moving_house_billboards(self):
        # Billboards can turn with either viewing angle. Their circumscribed
        # radius is the conservative bound needed by the editor handles.
        for elapsed in (5., 10., 14., 20., 31.):
            frame = building_frame_at(elapsed, 87.+elapsed, self.profile)
            for ident in ('house-110', 'house-211', 'house-410', 'house-423'):
                with self.subTest(elapsed=elapsed, group=ident):
                    mask = frame.group_ids == ident
                    if not mask.any():
                        continue
                    low, high = (np.array(v) for v in
                                 coverage_bounds(target_group(ident), self.profile.group(ident)))
                    radius = np.hypot(frame.widths[mask], frame.heights[mask])*.5
                    self.assertTrue(np.all(frame.centers[mask]-radius[:, None] >= low-1e-8))
                    self.assertTrue(np.all(frame.centers[mask]+radius[:, None] <= high+1e-8))


if __name__ == '__main__':
    unittest.main()
