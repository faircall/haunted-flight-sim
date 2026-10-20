"""Fog discovery driven by reached positions, independent of clocks and frames.

Create a tracker when an encounter starts, then call ``update`` only while the
player can explore. Use the pavilion centre as ``origin`` and keep its puzzle
area inside ``inner_distance``. The owning sequence handles its entry cutscene,
any explicit return transition, and conversion from fraction to shader radius.
"""
import math


class ExplorationFog:
    """Remember the furthest outward discovery and smoothly map it to clearing.

    Distances are world metres. ``vertical_weight`` scales height displacement
    before measuring distance; zero ignores elevation, while two makes a metre
    upstairs count like two horizontal metres. No time or distance walked is
    accumulated, so waiting, circling, and retracing a route cannot clear more.
    """

    def __init__(self, inner_distance=2.5, outer_distance=36.,
                 origin=(0., 0., 0.), vertical_weight=0.):
        inner = float(inner_distance)
        outer = float(outer_distance)
        weight = float(vertical_weight)
        centre = tuple(float(value) for value in origin)
        if (not all(math.isfinite(value) for value in (inner, outer, weight))
                or inner < 0. or outer <= inner or weight < 0.):
            raise ValueError('Fog distances must be finite, 0 <= inner < outer; '
                             'vertical weight must be finite and non-negative.')
        if len(centre) != 3 or not all(math.isfinite(value) for value in centre):
            raise ValueError('Fog origin must contain three finite coordinates.')
        self._inner_distance = inner
        self._outer_distance = outer
        self._origin = centre
        self._vertical_weight = weight
        self._furthest_distance = 0.

    @property
    def inner_distance(self):
        """Radius of the initial exploration dead zone, in metric metres."""
        return self._inner_distance

    @property
    def outer_distance(self):
        """Reached distance at which discovery has completely cleared fog."""
        return self._outer_distance

    @property
    def furthest_distance(self):
        """Maximum reached distance under the configured spatial metric."""
        return self._furthest_distance

    @property
    def clear_fraction(self):
        """Monotonic 0..1 clearing; querying it never advances the effect."""
        t = (self._furthest_distance-self._inner_distance) / (
            self._outer_distance-self._inner_distance)
        if t <= 0.:
            return 0.
        if t >= 1.:
            return 1.
        # Quintic spatial easing gives zero slope and curvature at either end.
        return t*t*t*(t*(t*6.-15.)+10.)

    def update(self, x, y, z):
        """Record a reached world position and return its new clear fraction.

        There is deliberately no dt or time argument and no delayed smoothing:
        stopping at a position stops clearing on that same update. Backtracking
        preserves the widest discovery instead of closing the fog again.
        """
        point = (float(x), float(y), float(z))
        if not all(math.isfinite(value) for value in point):
            raise ValueError('Fog position must contain three finite coordinates.')
        dx = point[0]-self._origin[0]
        dy = (point[1]-self._origin[1])*self._vertical_weight
        dz = point[2]-self._origin[2]
        distance = math.hypot(dx, dy, dz)
        if not math.isfinite(distance):
            raise ValueError('Fog position exceeds the supported world range.')
        self._furthest_distance = max(self._furthest_distance, distance)
        return self.clear_fraction
