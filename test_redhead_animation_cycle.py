import math
import unittest

import g_animation


def pose(phase, run=0.0, facing="right"):
    return g_animation.build_redhead_cutout_rig_parts({
        "animation_direction": facing,
        "procedural_gait": {"phase": phase, "blend": 1.0, "run_blend": run},
    })


def foot(parts, side):
    part = next(p for p in parts if p.get("rig_side") == side and p.get("rig_joint") == "lower_leg")
    offset = g_animation._rotate_rig_vector(0, 2.5, part["rotation"])
    return {axis: part["pivot_local"][axis] + offset[axis] for axis in ("x", "y")}


class RedheadAnimationCycleTests(unittest.TestCase):
    def test_walk_support_and_recovery_happen_in_the_correct_half_cycles(self):
        quarters = [pose(i * math.pi / 2) for i in range(4)]
        near = [foot(p, "near") for p in quarters]
        far = [foot(p, "far") for p in quarters]
        # The grounded near foot travels backwards under a forward-moving body.
        self.assertGreater(near[0]["x"], near[1]["x"])
        self.assertGreater(near[1]["x"], near[2]["x"])
        self.assertLess(max(p["y"] for p in near[:3]) - min(p["y"] for p in near[:3]), 0.5)
        # Lift the recovering foot, not the current support foot.
        self.assertLess(far[1]["y"], near[1]["y"] - 1.0)
        self.assertLess(near[3]["y"], far[3]["y"] - 1.0)

    def test_full_cycles_keep_limb_identity_and_transform_continuity(self):
        for facing in ("right", "left", "up", "down"):
            for run in (0.0, 0.5, 1.0):
                previous = pose(0, run, facing)
                order = [(p.get("rig_side"), p["rig_joint"]) for p in previous]
                for sample in range(1, 241):
                    current = pose(sample * math.tau / 240, run, facing)
                    self.assertEqual([(p.get("rig_side"), p["rig_joint"]) for p in current], order)
                    for before, after in zip(previous, current):
                        self.assertLess(abs(after["rotation"] - before["rotation"]), 4.0)
                        self.assertLess(math.dist(tuple(before["pivot_local"].values()),
                                                  tuple(after["pivot_local"].values())), 0.3)
                    previous = current
                self.assertEqual(previous, pose(0, run, facing))
                # Approach each keyframe from both directions, including the wrap.
                for index in range(5):
                    phase = index * math.pi / 2
                    for before, after in zip(pose(phase - 1e-6, run, facing), pose(phase + 1e-6, run, facing)):
                        self.assertAlmostEqual(before["rotation"], after["rotation"], places=5)


if __name__ == "__main__":
    unittest.main()
