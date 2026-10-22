"""Deterministic local cloud births and near-to-far dissipation for the canals.

No graphics, filesystem, player, or sequence dependencies live here. The
renderer owns depth-tested billboards and the fixed pavilion pocket. Each
particle owns its entire alpha lifecycle; there is no global opacity fade.
Atlas pixels are unchanged straight-alpha RGBA8.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import random

import numpy as np


ARRIVAL_DURATION = 5.0
NEAR_CLEAR_START = 6.0
NEAR_CLEAR_END = 14.0
MIDDLE_CLEAR_START = 12.0
MIDDLE_CLEAR_END = 22.0
FAR_CLEAR_START = 20.0
FAR_CLEAR_END = 32.0
CLEAR_START = NEAR_CLEAR_START
CLEAR_DURATION = 40.0
DURATION = CLEAR_START + CLEAR_DURATION
ALPHA_CUTOFF = .0001
WAVE_COUNT = 6
ATLAS_COLUMNS = 4
ATLAS_ROWS = 2
ATLAS_VARIANTS = ATLAS_COLUMNS * ATLAS_ROWS
DEFAULT_TILE_SIZE = 64


@dataclass(frozen=True, slots=True)
class CloudParticle:
    id: int
    center: tuple[float, float, float]
    width: float
    height: float
    rotation: float  # Radians around the billboard normal.
    alpha: float
    variant: int
    layer: str


@dataclass(frozen=True, slots=True)
class ParticleLifetime:
    id: int
    wave: int
    birth: float
    opaque_at: float  # Fully faded in, not necessarily opaque.
    clear_start: float
    end: float
    max_alpha: float
    layer: str
    band: str
    clear_end: float  # Dominant clearing is complete; only a faint tail remains.
    radius: float  # Authored anchor radius, unaffected by local animation drift.


@dataclass(frozen=True, slots=True)
class _CloudSeed:
    id: int
    center: tuple[float, float, float]
    width: float
    height: float
    rotation: float
    alpha: float
    variant: int
    layer: str
    wave: int
    birth: float
    fade_in: float
    clear_start: float
    tau: float
    band: str
    clear_end: float
    phase: float
    speed: float
    drift: float


def _ease(value):
    t = min(1.0, max(0.0, value))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# The authored birth envelopes still occupy their original four-second
# clock. The real clock reaches that crest smoothly at five seconds, then
# stays there throughout the world handoff. Local drift uses neither clock.
_ARRIVAL_RAW_END = 4.0
_ARRIVAL_VALUES = (0., .38, .675, 1.1, 2.35, _ARRIVAL_RAW_END)
_ARRIVAL_SECANTS = tuple(b - a for a, b in zip(_ARRIVAL_VALUES, _ARRIVAL_VALUES[1:]))
_ARRIVAL_SLOPES = (0., *(2. * a * b / (a + b)
                       for a, b in zip(_ARRIVAL_SECANTS, _ARRIVAL_SECANTS[1:])), 0.)
_CLEAR_TIME_SCALE = 2.0


def _arrival_clock(elapsed):
    """A monotone Hermite birth clock with a gentle, stationary crest.

    Early coverage stays close to the approved gradual buildup. Harmonic
    interior tangents preserve monotonicity without overshoot; zero endpoint
    tangents avoid compressing the late waves into an accelerating final
    instant. Only birth envelopes use this map, never particle positions.
    """
    if elapsed <= 0.:return 0.
    if elapsed >= ARRIVAL_DURATION:return _ARRIVAL_RAW_END
    position = elapsed * (len(_ARRIVAL_VALUES) - 1) / ARRIVAL_DURATION
    index = min(len(_ARRIVAL_VALUES) - 2, int(position))
    t = position - index
    t2, t3 = t * t, t * t * t
    return ((2. * t3 - 3. * t2 + 1.) * _ARRIVAL_VALUES[index]
            + (t3 - 2. * t2 + t) * _ARRIVAL_SLOPES[index]
            + (-2. * t3 + 3. * t2) * _ARRIVAL_VALUES[index + 1]
            + (t3 - t2) * _ARRIVAL_SLOPES[index + 1])


def _arrival_time(clock):
    """Report real activation-relative times for the retimed wave metadata."""
    if clock <= 0.:return 0.
    if clock >= _ARRIVAL_RAW_END:return ARRIVAL_DURATION
    low, high = 0., ARRIVAL_DURATION
    for _ in range(48):
        middle = (low + high) * .5
        if _arrival_clock(middle) < clock:low = middle
        else:high = middle
    return (low + high) * .5


@lru_cache(maxsize=1)
def _layout():
    """Small interleaved clouds with births scattered across every depth.

    No particle travels in from the horizon. Near clouds stay small; coverage
    comes from overlapping independent layers and heights. Wave indices are
    distributed through every layer, never assigned to concentric bands.
    """
    rng = random.Random(0xCA13A15)
    result = []
    birth_centres = (0., .95, 2.1, 3.35, 4.8, 6.25)

    def add(x, y, z, width, height, alpha, layer, drift):
        wave = (len(result) * 5 + rng.randrange(3)) % WAVE_COUNT
        birth = max(0., birth_centres[wave] + rng.uniform(-.20, .45)) / 3.
        fade_in = rng.uniform(3.1, 4.9) / 3.
        # Preserve the exact random draw order of the approved layout. Only
        # time values change: no new draws can move or resize another cloud.
        stagger = rng.uniform(0., .80)
        tau = rng.uniform(18., 19.5) if layer == 'wisp' else rng.uniform(22., 24.)
        if layer == 'low':tau = rng.uniform(21., 23.)
        radius = math.hypot(x, z)
        if radius < 14.:
            band, stage_start, clear_end = 'near', NEAR_CLEAR_START, NEAR_CLEAR_END
        elif radius < 35.:
            band, stage_start, clear_end = 'middle', MIDDLE_CLEAR_START, MIDDLE_CLEAR_END
        else:
            band, stage_start, clear_end = 'far', FAR_CLEAR_START, FAR_CLEAR_END
        clear_start = stage_start + _CLEAR_TIME_SCALE * ((WAVE_COUNT - 1 - wave) * .012 + stagger * .25)
        # Set each fast exponential from the required END of its stage. It
        # must be nearly invisible then, not merely beginning to dissipate.
        end_ratio = .0018 + .0014 * (tau - 18.) / 6.
        tau = _soft_time(clear_end - clear_start) / -math.log(end_ratio)
        result.append(_CloudSeed(
            len(result), (x, y, z), width, height,
            rng.uniform(-.18, .18) if layer != 'low' else rng.uniform(-.075, .075),
            alpha, rng.randrange(4) if layer == 'wisp' else rng.randrange(4, 8),
            layer, wave, birth, fade_in, clear_start, tau, band, clear_end,
            rng.uniform(-math.pi, math.pi), rng.uniform(.06, .11), drift))

    # Foreground fragments form gently amongst the larger backing, with no
    # stretched wall-sized sprite suddenly taking over the view.
    for i in range(144):
        angle = math.tau * (i + rng.uniform(-.47, .47)) / 144.
        radius = 7.8 + 1.3 * math.sin(angle * 3. + .7) + rng.uniform(-.7, 1.4)
        add(math.cos(angle) * radius, rng.uniform(.5, 5.8), math.sin(angle) * radius,
            rng.uniform(1.25, 3.35), rng.uniform(.85, 2.65), rng.uniform(.12, .30),
            'wisp', .32)

    # Four depths and six staggered heights replace the previous giant near
    # cards. Adjacent fragments overlap enough to obscure the nearest facades
    # while each visible piece remains roughly four to six metres across.
    for band, base_radius in enumerate((7.6, 8.7, 10.3, 12.5)):
        for row, base_y in enumerate((.8, 3.2, 5.6, 8.0, 10.4, 12.8)):
            for i in range(56):
                angle = math.tau * (i + band * .31 + row * .43 + rng.uniform(-.29, .29)) / 56.
                radius = base_radius + .45 * math.sin(angle * 3. + band * .8) + rng.uniform(-.22, .22)
                add(math.cos(angle) * radius, base_y + rng.uniform(-.45, .45), math.sin(angle) * radius,
                    rng.uniform(4.1, 5.8), rng.uniform(4.1, 5.8), rng.uniform(.55, .73),
                    'bank', .38)

    # Middle and distant banks can have larger chunks: they provide depth,
    # not a screen-filling moving card in front of the player.
    for i in range(96):
        angle = math.tau * (i + rng.uniform(-.4, .4)) / 96.
        radius = 19. + 2.6 * math.sin(angle * 4. + .3) + rng.uniform(-1., 2.)
        add(math.cos(angle) * radius, rng.uniform(3., 11.), math.sin(angle) * radius,
            rng.uniform(7., 10.5), rng.uniform(7., 12.), rng.uniform(.52, .75), 'bank', .65)
    for i in range(64):
        angle = math.tau * (i + rng.uniform(-.4, .4)) / 64.
        radius = 27. + 3.5 * math.sin(angle * 3. + 1.2) + rng.uniform(-2., 2.)
        add(math.cos(angle) * radius, rng.uniform(12., 18.), math.sin(angle) * radius,
            rng.uniform(11., 18.), rng.uniform(10., 16.), rng.uniform(.52, .76), 'bank', .85)

    # Raised low fragments cover the camera-to-water path; deeper fragments
    # overlap both water datums. No single near-water billboard is huge.
    for band, base_radius in enumerate((6.9, 8.2, 9.8, 12.1)):
        for i in range(48):
            angle = math.tau * (i + band * .39 + rng.uniform(-.35, .35)) / 48.
            radius = base_radius + .50 * math.sin(angle * 4. + band) + rng.uniform(-.25, .25)
            raised = band < 2
            add(math.cos(angle) * radius, rng.uniform(.55, .95) if raised else rng.uniform(-.45, -.10),
                math.sin(angle) * radius, rng.uniform(4.2, 5.8),
                rng.uniform(2.9, 4.2) if raised else rng.uniform(4.2, 5.6),
                rng.uniform(.77, .91), 'low', .28)

    for iz in range(-6, 7):
        for ix in range(-6, 7):
            x = ix * 21. + rng.uniform(-8., 8.)
            z = iz * 21. + rng.uniform(-8., 8.)
            if math.hypot(x, z) < 32.:continue
            add(x, rng.uniform(4., 13.), z, rng.uniform(22., 36.), rng.uniform(15., 24.),
                rng.uniform(.39, .60), 'far', .95)

    # Append a small raised overlap before the closest water intersection.
    # Keeping this at the end preserves every previously authored particle's
    # seed, position and lifecycle. The pavilion's fixed fragment pocket still
    # protects its centre; these cards only fill the near outer water band.
    for i in range(96):
        angle = math.tau * (i + rng.uniform(-.43, .43)) / 96.
        radius = 6.6 + .30 * math.sin(angle * 5. + .7) + rng.uniform(-.20, .20)
        add(math.cos(angle) * radius, rng.uniform(.65, 1.), math.sin(angle) * radius,
            rng.uniform(3., 4.5), rng.uniform(2.5, 3.4), rng.uniform(.72, .90),
            'low', .22)
    return tuple(result)


@lru_cache(maxsize=1)
def particle_schedule():
    """Immutable lifetime metadata for diagnostics and native review reports."""
    return tuple(ParticleLifetime(s.id, s.wave, _arrival_time(s.birth), _arrival_time(s.birth + s.fade_in),
                                  s.clear_start, DURATION, s.alpha, s.layer,
                                  s.band, s.clear_end, math.hypot(s.center[0], s.center[2]))
                 for s in _layout())


def _soft_time(t):
    """Brief zero-slope onset, followed by ordinary elapsed time."""
    onset = .16 * _CLEAR_TIME_SCALE
    return t - onset * (-math.expm1(-t / onset))


def _decay(elapsed, start, tau):
    if elapsed <= start:return 1.
    if elapsed >= DURATION:return 0.
    t = _soft_time(elapsed - start)
    end = _soft_time(DURATION - start)
    def exponential(scale):
        endpoint = math.exp(-end / scale)
        return max(0., (math.exp(-t / scale) - endpoint) / (1. - endpoint))
    # The dominant mass clears inside its short stage. A sub-one-percent
    # slow component preserves a few gentle traces without leaving a dense
    # overlapping wall. The complete onset, stagger and tail run at half the
    # previous speed; both components reach exactly zero by 46 seconds.
    return .992 * exponential(tau) + .008 * exponential(8. * _CLEAR_TIME_SCALE)


@lru_cache(maxsize=4)
def particles_at(elapsed, clock):
    """Sample independent cloud lifetimes without simulation or player state.

    Overlapping birth waves accumulate throughout the five-second arrival. Clock-driven
    displacement is bounded local drift, with no radial inward motion or scale
    growth. Nearby clouds dissipate first, with overlapping starts farther out.
    Surviving cards are submitted
    until their own alpha reaches ``ALPHA_CUTOFF``; all are gone by DURATION.
    """
    elapsed, clock = float(elapsed), float(clock)
    if not math.isfinite(elapsed) or not math.isfinite(clock):
        raise ValueError('Particle times must be finite')
    if elapsed <= 0. or elapsed >= DURATION:return ()
    birth_clock = _arrival_clock(elapsed)
    result = []
    for seed in _layout():
        if birth_clock <= seed.birth:continue
        opacity = _ease((birth_clock - seed.birth) / seed.fade_in)
        alpha = seed.alpha * opacity * _decay(elapsed, seed.clear_start, seed.tau)
        if alpha <= ALPHA_CUTOFF:continue
        x, y, z = seed.center
        radius = math.hypot(x, z)
        nx, nz = x / radius, z / radius
        phase = seed.phase + clock * seed.speed
        tangent = math.sin(phase * .73) * seed.drift
        radial = math.sin(phase * 1.17) * seed.drift * .42
        x += nx * radial - nz * tangent
        z += nz * radial + nx * tangent
        y += math.sin(phase * .89 + 1.3) * (.10 if seed.layer == 'low' else .18)
        result.append(CloudParticle(
            seed.id, (x, y, z), seed.width, seed.height,
            seed.rotation + .022 * math.sin(phase * .53), alpha, seed.variant, seed.layer))
    return tuple(result)


def atlas_rect(variant, tile_size=DEFAULT_TILE_SIZE):
    """Pixel rectangle for a variant, with conventional top-left image rows."""
    if isinstance(variant, bool) or not isinstance(variant, int) or not 0 <= variant < ATLAS_VARIANTS:
        raise ValueError('Cloud variant must be an integer from 0 through 7')
    if isinstance(tile_size, bool) or not isinstance(tile_size, int) or tile_size < 16:
        raise ValueError('Cloud atlas tiles must contain at least sixteen pixels')
    return ((variant % ATLAS_COLUMNS) * tile_size,
            (variant // ATLAS_COLUMNS) * tile_size, tile_size, tile_size)


def _smooth_array(t):
    t = np.clip(t, 0., 1.)
    return t * t * (3. - 2. * t)


def _texture_noise(rng, size, columns, rows):
    """Low-frequency value noise sampled without image/GPU dependencies."""
    values = rng.random((rows + 1, columns + 1))
    xx = np.linspace(0., columns, size, endpoint=False)
    yy = np.linspace(0., rows, size, endpoint=False)
    xi = np.floor(xx).astype(int); yi = np.floor(yy).astype(int)
    tx = _smooth_array(xx - xi)[None, :]
    ty = _smooth_array(yy - yi)[:, None]
    a = values[yi[:, None], xi[None, :]]
    b = values[yi[:, None], xi[None, :] + 1]
    c = values[yi[:, None] + 1, xi[None, :]]
    d = values[yi[:, None] + 1, xi[None, :] + 1]
    return (a + (b - a) * tx) * (1. - ty) + (c + (d - c) * tx) * ty


@lru_cache(maxsize=4)
def build_particle_atlas(tile_size=DEFAULT_TILE_SIZE):
    """Return ``(RGBA_bytes, width, height)`` for eight coarse cloud tiles.

    Wide, overlapping lobes and warped gaps form layered bank fragments rather
    than uniformly shaded circular smoke puffs. RGB has six coarse shaded grey
    steps; alpha stays smoothly feathered and is zero at every tile border.
    Pixels are straight alpha, ready for the renderer's chosen tint/blend mode.
    """
    atlas_rect(0, tile_size)  # Validate without allocating anything first.
    atlas = np.zeros((ATLAS_ROWS * tile_size, ATLAS_COLUMNS * tile_size, 4), dtype=np.uint8)
    axis = (np.arange(tile_size, dtype=np.float64) + .5) / tile_size * 2. - 1.
    xx, yy = np.meshgrid(axis, axis)
    border = _smooth_array((1. - np.maximum(abs(xx), abs(yy))) * 9.)
    border[:2, :] = border[-2:, :] = border[:, :2] = border[:, -2:] = 0.
    for variant in range(ATLAS_VARIANTS):
        rng = np.random.default_rng(0xF06A71 + variant * 7919)
        broad = _texture_noise(rng, tile_size, 4, 4)
        medium = _texture_noise(rng, tile_size, 9, 7)
        fine = _texture_noise(rng, tile_size, 19, 16)
        noise = .60 * broad + .29 * medium + .11 * fine
        warp_x = xx + (medium - .5) * .17
        warp_y = yy + (broad - .5) * .24
        # Clustered horizontal lobes leave asymmetric top and bottom contours.
        # The probabilistic union avoids visible boundaries where lobes overlap.
        empty = np.ones_like(xx)
        for i in range(5):
            cx = -.63 + i * .315 + rng.uniform(-.09, .09)
            cy = rng.uniform(-.21, .21)
            rx, ry = rng.uniform(.38, .59), rng.uniform(.39, .63)
            distance = np.sqrt(((warp_x - cx) / rx) ** 2 + ((warp_y - cy) / ry) ** 2)
            lobe = 1. - _smooth_array((distance - .30) / .86)
            empty *= 1. - lobe
        silhouette = 1. - empty
        if variant < 4:
            # Uneven transparent channels expose lower cloud layers. The
            # visible front is broad wisps, not a row of round puff centres.
            channels = _smooth_array((noise - .19) / .55)
            alpha = silhouette * (.08 + .74 * channels) * border
        else:
            # Dense interiors remain mottled but never contain arbitrary
            # pinholes; several overlapping back tiles conceal the world swap.
            density = .79 + .20 * _smooth_array((noise - .17) / .60)
            alpha = silhouette * density * border
        # Broad, visibly shaded fragments survive several translucent layers.
        # Normalize the coarse field rather than shading each lobe like a lit
        # sphere: the result is a broken cloud bank, not a row of smoke balls.
        dark, bright = np.quantile(noise, (.06, .94))
        light = np.clip((noise - dark) / max(.001, bright - dark)
                        + .055 * (.3 - yy), 0., 1.)
        grey = np.rint(90. + 155. * np.rint(light * 5.) / 5.).astype(np.uint8)
        tile = np.empty((tile_size, tile_size, 4), dtype=np.uint8)
        tile[:, :, :3] = grey[:, :, None]
        tile[:, :, 3] = np.rint(np.clip(alpha, 0., 1.) * 255.).astype(np.uint8)
        x, y, _, _ = atlas_rect(variant, tile_size)
        atlas[y:y + tile_size, x:x + tile_size] = tile
    return atlas.tobytes(), ATLAS_COLUMNS * tile_size, ATLAS_ROWS * tile_size
