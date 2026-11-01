"""Contracts for the separate Chorus figure and its baked motion."""
from io import BytesIO
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from chorus_grasper_animation import CLIP_SECONDS, GAITS, MOTION_LIBRARY
from test_player_refined_assets import animation_channel, glb, joints
from test_temple_living import accessor

ROOT = Path(__file__).resolve().parent
FIGURE = ROOT / 'art' / 'temple' / 'chorus_grasper'


class ChorusGrasperAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.binary = glb(FIGURE / 'chorus_grasper.glb')
        cls.player, cls.player_binary = glb(ROOT / 'art' / 'temple' / 'combat' / 'player.glb')

    def test_rebuild_library_and_clip_manifest(self):
        self.assertTrue(MOTION_LIBRARY.exists(), 'Editable motion library missing')
        self.assertGreater(MOTION_LIBRARY.stat().st_size, 1000)
        manifest = json.loads((FIGURE / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['chorus_grasper']['clips'], CLIP_SECONDS)
        self.assertEqual({a['name'] for a in self.doc['animations']}, set(CLIP_SECONDS))
        for action in self.doc['animations']:
            for sampler in action['samplers']:
                times = accessor(self.doc, self.binary, sampler['input'])[:, 0]
                self.assertAlmostEqual(float(times[0]), 0., places=4)
                self.assertAlmostEqual(float(times[-1]), CLIP_SECONDS[action['name']], places=4)
                self.assertTrue(np.all(np.diff(times) > 0))

    def test_compatible_skin_and_taller_oversized_head(self):
        self.assertEqual(joints(self.doc), joints(self.player))
        self.assertEqual(len(joints(self.doc)), 15)
        inverse = accessor(self.doc, self.binary, self.doc['skins'][0]['inverseBindMatrices'])
        original = accessor(self.player, self.player_binary, self.player['skins'][0]['inverseBindMatrices'])
        np.testing.assert_allclose(inverse, original, atol=1e-5)
        def vertices(doc, binary):
            return np.concatenate([accessor(doc, binary, p['attributes']['POSITION'])
                for mesh in doc['meshes'] for p in mesh['primitives']])
        character = vertices(self.doc, self.binary)
        player = vertices(self.player, self.player_binary)
        self.assertGreater(np.ptp(character[:, 1]), np.ptp(player[:, 1]))
        self.assertLess(np.ptp(character[:, 1]), np.ptp(player[:, 1]) * 1.15)
        for mesh in self.doc['meshes']:
            for part in mesh['primitives']:
                attrs = part['attributes']
                weights = accessor(self.doc, self.binary, attrs['WEIGHTS_0'])
                indices = accessor(self.doc, self.binary, attrs['JOINTS_0'])
                np.testing.assert_allclose(weights.sum(axis=1), 1., atol=1e-5)
                self.assertLess(int(indices.max()), 15)
        image = self.doc['images'][0]
        view = self.doc['bufferViews'][image['bufferView']]
        offset = view.get('byteOffset', 0)
        with Image.open(BytesIO(self.binary[offset:offset + view['byteLength']])) as atlas:
            self.assertEqual(atlas.size, (256, 256))

    def test_motion_loops_are_continuous_and_run_has_distinct_arms(self):
        for clip in ('enemy_idle', 'enemy_walk', 'enemy_run'):
            action = next(a for a in self.doc['animations'] if a['name'] == clip)
            for channel in action['channels']:
                sampler = action['samplers'][channel['sampler']]
                values = accessor(self.doc, self.binary, sampler['output'])
                if channel['target']['path'] == 'rotation':
                    self.assertAlmostEqual(abs(float(np.dot(values[0], values[-1]))), 1., places=4)
                else:
                    np.testing.assert_allclose(values[0], values[-1], atol=.001)
        for side in ('L', 'R'):
            _, walk = animation_channel(self.doc, self.binary, 'enemy_walk', 'arm.'+side, 'rotation')
            _, run = animation_channel(self.doc, self.binary, 'enemy_run', 'arm.'+side, 'rotation')
            similarity = np.abs(np.sum(walk * run, axis=1))
            self.assertLess(float(np.mean(similarity)), .98)

    def test_cadence_matches_authored_plant_travel(self):
        for gait in GAITS.values():
            self.assertAlmostEqual(gait['stride'] * gait['stance'], gait['front'] + gait['back'])
            self.assertGreater(gait['speed'], 0.)
        self.assertGreater(GAITS['enemy_run']['speed'], GAITS['enemy_walk']['speed'])


if __name__ == '__main__':
    unittest.main()
