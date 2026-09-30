"""Compare native geometry with both existing Python reference paths."""
import math
from pathlib import Path
import random
import sys
import numpy as np

# Import the original game before making the native extension visible.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import g_graphics as reference
sys.path.insert(0, str(Path(__file__).resolve().parent / 'build' / 'runtime'))
import native_geometry as native


def run():
    rng = random.Random(72803)
    point_count = rectangle_count = 0
    for case in range(400):
        count = (0, 1, 2, 3, 4, 13, 23, 24, 25, 64, 180)[case % 11]
        angles = sorted(rng.uniform(-math.pi, math.pi) for _ in range(count))
        polygon = [dict(x=math.cos(angle)*rng.uniform(20, 100),
                        y=math.sin(angle)*rng.uniform(20, 100)) for angle in angles]
        if count > 3 and case % 5 == 0:
            polygon[1] = dict(polygon[0])
        points = [(rng.uniform(-140, 140), rng.uniform(-140, 140)) for _ in range(80)]
        points += [(p['x'], p['y']) for p in polygon]
        expected = reference.points_in_polygon(points, polygon)
        actual = native.points_in_polygon(points, polygon)
        if not np.array_equal(expected, actual):
            raise AssertionError(('point coverage', case, np.flatnonzero(expected != actual)))
        point_count += len(points)
        for index in range(20):
            rectangle = dict(x=rng.uniform(-140, 140), y=rng.uniform(-140, 140),
                             width=rng.uniform(0, 120), height=rng.uniform(0, 120))
            if index == 0:
                rectangle['width'] = 0.
            expected = reference.polygon_intersects_rectangle(polygon, rectangle)
            actual = native.polygon_intersects_rectangle(polygon, rectangle)
            if bool(expected) != actual:
                raise AssertionError(('rectangle overlap', case, rectangle))
            rectangle_count += 1
    print(f'Native geometry: {point_count} points, {rectangle_count} rectangles; no differences.')


if __name__ == '__main__':
    run()
