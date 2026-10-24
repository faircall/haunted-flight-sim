"""Saved building fog directions reach the real encounter and both render passes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import math
import tempfile
import unittest

from g_huxin_canals_direction import (
    building_document, load_direction, save_direction, profile_from_document,
)
from g_huxin_canals_targets import target_groups
from g_huxin_canals_particles import particles_at
from g_huxin_canals_sequence import CanalSequence
from huxin_canals_viewer import Lake, reset_player
from temple_interior_viewer import camera
from test_huxin_canals_fog import FakePuzzleFog, capture_mist_pass
import pyray as pr


class BuildingFogRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.document = building_document()
        self.houses = [target for target in target_groups() if target.kind == 'house']
        self.assertGreater(len(self.houses), 2)

    def test_saved_target_placement_is_consumed_by_fresh_game(self):
        document = deepcopy(self.document)
        target = self.houses[0]
        document['fog']['groups'][target.id]['offset'][0] += 2.5
        document['fog']['groups'][target.id]['opacity'] *= .6
        with tempfile.TemporaryDirectory(prefix='haunted-building-direction-') as folder:
            path = Path(folder) / 'direction.json'
            save_direction(document, path)
            loaded = load_direction(path)
            scene = SimpleNamespace()
            with patch('huxin_canals_viewer.load_direction', return_value=loaded):
                actor = reset_player(scene, puzzle=True)
            self.assertIs(actor.encounter, scene.sequence)
            self.assertEqual(scene.sequence.direction, profile_from_document(loaded))
            base = {p.id: p for p in particles_at(5., 87., profile_from_document(self.document))}
            edited = {p.id: p for p in particles_at(5., 87., scene.sequence.direction)}
            self.assertEqual(base.keys(), edited.keys())
            owned = [p for p in base.values() if p.group_id == target.id]
            self.assertTrue(owned)
            for identity, original in base.items():
                changed = edited[identity]
                if original.group_id != target.id:
                    self.assertEqual(changed, original)
                else:
                    self.assertAlmostEqual(changed.center[0], original.center[0] + 2.5)
                    self.assertEqual(changed.center[1:], original.center[1:])
                    self.assertAlmostEqual(changed.alpha, original.alpha * .6)

    def test_independent_target_reveal_does_not_fade_neighbour(self):
        document = deepcopy(self.document)
        early, late = self.houses[:2]
        document['fog']['groups'][early.id].update(reveal_start=6., reveal_end=10.)
        document['fog']['groups'][late.id].update(reveal_start=20., reveal_end=30.)
        profile = profile_from_document(document)
        peak = {p.id: p for p in particles_at(5., 87., profile)}
        current = {p.id: p for p in particles_at(12., 87., profile)}
        early_peak = [p for p in peak.values() if p.group_id == early.id]
        late_peak = [p for p in peak.values() if p.group_id == late.id]
        self.assertTrue(early_peak and late_peak)
        for original in early_peak:
            self.assertLessEqual(current.get(original.id, SimpleNamespace(alpha=0.)).alpha,
                                 original.alpha * .011)
        for original in late_peak:
            self.assertEqual(current[original.id], original)

    def test_real_mist_setup_routes_same_building_profile_to_both_water_datums(self):
        profile = profile_from_document(self.document)
        lake = Lake.__new__(Lake)
        lake.sequence = CanalSequence(profile)
        lake.post = SimpleNamespace(id=412)
        lake.puzzle_fog = FakePuzzleFog()
        actor = SimpleNamespace(x=1.65, height=.325, z=1.65)
        view = camera((4.05, 3.2, 3.05), (-.7, 1.5, -1.2), 78)
        for elapsed in (2.5, 5.5, 12., 30.):
            lake.sequence.seek(elapsed)
            for revealed, water_y in ((False, 0.), (True, -1.55)):
                lake._world_override = revealed
                calls = []
                for reflected in (True, False):
                    result = capture_mist_pass(lake, view, actor, 87., reflected=reflected)
                    self.assertAlmostEqual(result.uniforms['waterY'], water_y, places=5)
                    call = lake.puzzle_fog.calls[-1]
                    self.assertIs(call['sequence'].direction, profile)
                    calls.append(call)
                self.assertEqual(calls[0]['clock'], calls[1]['clock'])
                self.assertEqual(calls[0]['water_y'], calls[1]['water_y'])
                self.assertTrue(calls[0]['reflected'])
                self.assertFalse(calls[1]['reflected'])
                self.assertEqual(lake.sequence.elapsed, elapsed)

    def test_vectorized_submission_matches_scalar_frustum_and_depth_order(self):
        """Independent scalar reference for the new cached/vectorized path."""
        from test_huxin_canals_fog import ParticleCardIntegrationTests
        profile = profile_from_document(self.document)
        sequence = CanalSequence(profile)
        sequence.seek(5.5)
        packets = particles_at(5.5, 87., profile)
        helper = ParticleCardIntegrationTests()
        views = (camera((4.05, 3.2, 3.05), (-.7, 1.5, -1.2), 78),
                 camera((3.5, 3.1, -3.5), (-1., 2.1, 7.), 78))
        for view in views:
            forward = pr.vector3_normalize(pr.vector3_subtract(view.target, view.position))
            right = pr.vector3_normalize(pr.vector3_cross_product(forward, view.up))
            up = pr.vector3_cross_product(right, forward)
            eye = (view.position.x, view.position.y, view.position.z)
            axes = tuple((v.x, v.y, v.z) for v in (forward, right, up))
            vertical = math.tan(math.radians(view.fovy) * .5)
            horizontal = vertical * 640. / 360.
            for water in (0., -1.55):
                for reflected in (False, True):
                    # Production must consume the readonly array frame, not
                    # rebuild thousands of diagnostic Python packets per draw.
                    with patch('huxin_canals_particles.particles_at',
                               side_effect=AssertionError('Building renderer requested packets')):
                        result = helper.render_cards(sequence, water, reflected, view=view)
                    self.assertIsNone(result.fog._signature)
                    self.assertIsNone(result.fog._groups)
                    expected = []
                    for packet in packets:
                        point = list(packet.center)
                        if reflected:point[1] = 2. * water - point[1]
                        offset = tuple(p - e for p, e in zip(point, eye))
                        depth, across, height = (sum(a * b for a, b in zip(offset, axis)) for axis in axes)
                        radius = math.hypot(packet.width, packet.height) * .5
                        if depth + radius <= 0.:continue
                        if abs(across) > depth * horizontal + radius * math.sqrt(1. + horizontal ** 2):continue
                        if abs(height) > depth * vertical + radius * math.sqrt(1. + vertical ** 2):continue
                        expected.append((depth, packet, point))
                    expected.sort(key=lambda row: row[0], reverse=True)
                    self.assertEqual(len(result.draws), len(expected))
                    self.assertEqual(result.fog.last_draw_count, len(expected))
                    for draw, (_, packet, point) in zip(result.draws, expected):
                        for name, value in zip(('x', 'y', 'z'), point):
                            self.assertAlmostEqual(getattr(draw[3], name), value, delta=3e-5)
                        packed = draw[8].r + draw[8].a * 256
                        self.assertEqual(packed, round(65535 * packet.alpha))
                    self.assertEqual(result.fog.last_signature,
                                     tuple((p.id, p.center, p.alpha) for p in packets))

    def test_internal_flow_uses_shared_scene_clock_not_reveal_time(self):
        from test_huxin_canals_fog import ParticleCardIntegrationTests
        sequence = CanalSequence(profile_from_document(self.document))
        sequence.seek(5.5)
        helper = ParticleCardIntegrationTests()
        for clock in (87., 87.125):
            for water in (0., -1.55):
                for reflected in (False, True):
                    result = helper.render_cards(sequence, water, reflected, clock=clock)
                    self.assertEqual(result.uniforms['flowTime'], clock)
                    self.assertEqual(result.uniforms['targetedFog'], 1.)
        self.assertEqual(sequence.elapsed, 5.5)


if __name__ == '__main__':
    unittest.main()
