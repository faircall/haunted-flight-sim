"""Deterministic cloud births and independent target reveals for the canals.

Legacy bank mode preserves its original layout, near-to-far timing and renderer
pocket. Building mode lazily reads a small authored target catalog and places
separate world-anchored envelopes around houses, roofs and water. Each target
has its own editable reveal times. Neither mode depends on a camera or player;
the renderer supplies depth-tested billboards. Atlas pixels are unchanged
straight-alpha RGBA8, and each particle owns its alpha without a global fade.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import random
from hashlib import sha256
from typing import NamedTuple

import numpy as np
from g_huxin_canals_direction import DEFAULT_DIRECTION


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


class BuildingCloudParticle(NamedTuple):
    """Immutable C-allocated packets keep thousands of target cards affordable."""
    id: int
    center: tuple[float, float, float]
    width: float
    height: float
    rotation: float
    alpha: float
    variant: int
    layer: str
    group_id: str


@dataclass(frozen=True, slots=True, eq=False)
class BuildingFrame:
    """Shared read-only arrays; native rendering allocates no card objects."""
    ids: np.ndarray
    centers: np.ndarray
    widths: np.ndarray
    heights: np.ndarray
    rotations: np.ndarray
    alphas: np.ndarray
    variants: np.ndarray
    group_ids: np.ndarray
    layers: np.ndarray

    def __len__(self):
        return len(self.ids)


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
class BuildingParticleLifetime(ParticleLifetime):
    group_id: str


@dataclass(frozen=True, slots=True)
class _TargetSeed:
    id: int
    group_id: str
    center: tuple[float,float,float]
    width: float
    height: float
    alpha: float
    variant: int
    layer: str
    wave: int
    birth: float
    fade_in: float
    phase: float
    speed: float
    drift: float
    stagger: float
    density: float


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


_BAND_CUES = {
    'near': ('start', 'build_end', 'blend_end', 'near_end', 'end'),
    'middle': ('start', 'build_end', 'middle_start', 'middle_end', 'end'),
    'far': ('start', 'build_end', 'far_start', 'far_end', 'end'),
}


def _map_time(value, source, target):
    """Map one bank's lifecycle without changing its authored birth pattern."""
    if source == target:return value
    if value <= source[0]:return target[0]
    if value >= source[-1]:return target[-1]
    for index, end in enumerate(source[1:]):
        if value <= end:
            if value == end:return target[index + 1]
            t = (value - source[index]) / (end - source[index])
            return target[index] + t * (target[index + 1] - target[index])
    return target[-1]


@lru_cache(maxsize=8)
def _direction_bands(direction):
    return {name: (tuple(direction.cue(cue) for cue in cues),
                   tuple(DEFAULT_DIRECTION.cue(cue) for cue in cues),
                   direction.band(name)) for name, cues in _BAND_CUES.items()}


@lru_cache(maxsize=4)
def particle_schedule(direction=None):
    """Immutable lifetime metadata for diagnostics and native review reports."""
    if direction is not None and direction.fog_mode == 'buildings':
        return _building_schedule(direction)
    if direction is not None and direction != DEFAULT_DIRECTION:
        bands = _direction_bands(direction)
        result = []
        for s in particle_schedule():
            edited, authored, placement = bands[s.band]
            remap = lambda value: _map_time(value, authored, edited)
            result.append(ParticleLifetime(s.id, s.wave, remap(s.birth), remap(s.opaque_at),
                                          remap(s.clear_start), direction.cue('end'),
                                          min(1., s.max_alpha * placement.opacity), s.layer,
                                          s.band, remap(s.clear_end), s.radius))
        return tuple(result)
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
def particles_at(elapsed, clock, direction=None):
    """Sample independent cloud lifetimes without simulation or player state.

    Waves accumulate throughout the authored arrival with bounded local drift,
    never a travelling radial curtain. Legacy banks retain their depth stages;
    building envelopes follow independent group reveal windows. Surviving
    cards are submitted until their alpha reaches ``ALPHA_CUTOFF``; all are
    gone at the authored end cue (DURATION for the default legacy profile).
    """
    elapsed, clock = float(elapsed), float(clock)
    if not math.isfinite(elapsed) or not math.isfinite(clock):
        raise ValueError('Particle times must be finite')
    if direction is not None and direction.fog_mode == 'buildings':
        return _building_particles(elapsed,clock,direction)
    custom = direction is not None and direction != DEFAULT_DIRECTION
    duration = direction.cue('end') if custom else DURATION
    if elapsed <= 0. or elapsed >= duration:return ()
    bands = _direction_bands(direction) if custom else None
    times = {name: _map_time(elapsed, edited, authored)
             for name, (edited, authored, _) in bands.items()} if custom else None
    births = {name: _arrival_clock(value) for name, value in times.items()} if custom else None
    birth_clock = _arrival_clock(elapsed) if not custom else 0.
    result = []
    for seed in _layout():
        local_time = times[seed.band] if custom else elapsed
        born = births[seed.band] if custom else birth_clock
        if born <= seed.birth:continue
        opacity = _ease((born - seed.birth) / seed.fade_in)
        alpha = seed.alpha * opacity * _decay(local_time, seed.clear_start, seed.tau)
        placement = bands[seed.band][2] if custom else None
        if custom:alpha = min(1., alpha * placement.opacity)
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
        width, height = seed.width, seed.height
        if custom:
            x = x * placement.scale + placement.offset[0]
            y = y * placement.scale + placement.offset[1]
            z = z * placement.scale + placement.offset[2]
            width *= placement.scale; height *= placement.scale
        result.append(CloudParticle(
            seed.id, (x, y, z), width, height,
            seed.rotation + .022 * math.sin(phase * .53), alpha, seed.variant, seed.layer))
    return tuple(result)


@lru_cache(maxsize=1)
def _building_layout():
    """Separate envelopes outside each target, never one pavilion-wide shell."""
    from g_huxin_canals_targets import target_groups
    result = []
    for target in target_groups():
        stable = int.from_bytes(sha256(target.id.encode()).digest()[:4],'big')
        rng = random.Random(stable)
        local = []
        cx,cy,cz = target.center
        hx,hy,hz = target.half_extents

        def add(x,y,z,width,height,alpha,layer='bank',drift=.25,variant=None):
            index = len(local)
            wave = (index*5+rng.randrange(3))%WAVE_COUNT
            birth = max(0.,(0.,.95,2.1,3.35,4.8,6.25)[wave]+rng.uniform(-.20,.45))/3.
            fade = rng.uniform(3.1,4.9)/3.
            tile=rng.randrange(4) if layer=='wisp' else rng.randrange(4,8)
            local.append(_TargetSeed(stable*4096+index,target.id,(x,y,z),width,height,alpha,
                                     tile if variant is None else variant,
                                     layer,wave,birth,fade,rng.uniform(-math.pi,math.pi),
                                     rng.uniform(.055,.105),drift,rng.uniform(0.,.06),rng.uniform(.0018,.0032)))

        if target.kind == 'house':
            shells = 3 if target.band=='near' else 2 if target.band=='middle' else 1
            if target.id in ('house-410','house-423','house-437','house-449'):shells+=1
            columns = 3 if target.band=='near' else 2
            rows = 3 if target.band!='far' else 2
            # Each side has overlapping layers OUTSIDE the padded house
            # footprint. Scene depth cannot discard this fog inside a wall.
            for shell in range(shells):
                for axis in (0,2):
                    across = hz if axis==0 else hx
                    outward = hx if axis==0 else hz
                    for side in (-1,1):
                        for row in range(rows):
                            y = cy-hy+(row+.5)*2*hy/rows+rng.uniform(-.2,.2)
                            for col in range(columns):
                                along = -across+(col+.5)*2*across/columns+rng.uniform(-.25,.25)
                                normal = side*(outward+.65+shell*.85+rng.uniform(-.15,.15))
                                x,z = (cx+normal,cz+along) if axis==0 else (cx+along,cz+normal)
                                width = max(4.3,2*across/columns*1.85)*rng.uniform(.94,1.08)
                                height = max(4.2,2*hy/rows*1.85)*rng.uniform(.94,1.08)
                                add(x,y,z,width,height,rng.uniform(.80,.94))
            # Staggered overhead layers soften and obscure the roof silhouette
            # as well as windows. These are not clipped at the target bounds.
            for roof in range(2 if target.band!='far' else 1):
                for sx in (-.55,.55):
                    for sz in (-.55,.55):
                        add(cx+sx*hx+rng.uniform(-.25,.25),cy+hy+.45+roof*.65,
                            cz+sz*hz+rng.uniform(-.25,.25),max(5.,hx*1.5),max(4.5,hy*1.25),
                            rng.uniform(.78,.91))
            if target.id in ('house-437','house-110'):
                # These upper east corners sit between facade rows and the
                # two perpendicular envelopes. Local overlap covers the actual
                # exposed corner without thickening every house or the centre.
                # Appending preserves all existing seeds and their stable IDs.
                for side in (-1,1):
                    for corner_layer in range(4):
                        distance=.4+corner_layer*.6
                        add(cx+hx+distance,cy+hy*.4,cz+side*(hz+distance),
                            4.8,4.2,.94,drift=.08,variant=4+corner_layer)
            if target.id=='house-410':
                # Two gaps between the east-facing rows look across the
                # basin. Fill only those local wall strips, below the eaves.
                for y in (cy-hy+4.1,cy-hy+7.4):
                    for facade_layer in range(4):
                        add(cx+hx+.45+facade_layer*.6,y,cz+hz-2.1,
                            4.5,3.2,.94,drift=.08,variant=4+facade_layer)
                for facade_layer in range(4):
                    add(cx+hx+.45+facade_layer*.6,cy-hy+5.65,cz+hz-2.1,
                        4.5,3.2,.94,drift=.08,variant=4+facade_layer)
            if target.id=='house-211':
                for facade_layer in range(4):
                    add(cx-.8,cy+hy*.34,cz-hz-.5-facade_layer*.6,
                        4.3,3.6,.94,drift=.08,variant=4+facade_layer)
                for facade_layer in range(4):
                    add(cx-2.8,cy+hy*.34,cz-hz-.5-facade_layer*.6,
                        4.3,3.6,.94,drift=.08,variant=4+facade_layer)
        elif target.id.startswith('waterline-'):
            # Follow each real hex edge, not a tall radial wall. Small low
            # overlapping fragments cover the narrow strip between the deck
            # and the first depth-visible water sample in either endpoint.
            edge=int(target.id.rsplit('-',1)[1])-1
            a=(7.2*math.cos(edge*math.tau/6),7.2*math.sin(edge*math.tau/6))
            b=(7.2*math.cos((edge+1)*math.tau/6),7.2*math.sin((edge+1)*math.tau/6))
            normal=(math.cos((edge+.5)*math.tau/6),math.sin((edge+.5)*math.tau/6))
            for layer in range(3):
                for column in range(9):
                    t=(column+.5+rng.uniform(-.12,.12))/9.
                    distance=-.12+layer*.47+rng.uniform(-.05,.05)
                    x=a[0]+(b[0]-a[0])*t+normal[0]*distance
                    z=a[1]+(b[1]-a[1])*t+normal[1]*distance
                    add(x,-.55+rng.uniform(-.05,.05),z,rng.uniform(2.7,3.3),rng.uniform(2.7,3.1),
                        rng.uniform(.84,.94),'low',.08)
            # The submerged layer's soft upper fringe cannot conceal the old
            # y=0 water by itself. A second shallow layer puts actual cloud
            # cores above that surface, while its top remains below eye height.
            # Append it so existing edge-card seeds and IDs stay unchanged.
            for layer in range(3):
                for column in range(9):
                    t=(column+.5+rng.uniform(-.12,.12))/9.
                    distance=.35+layer*.55+rng.uniform(-.05,.05)
                    x=a[0]+(b[0]-a[0])*t+normal[0]*distance
                    z=a[1]+(b[1]-a[1])*t+normal[1]*distance
                    add(x,.45+rng.uniform(-.05,.05),z,rng.uniform(3.,3.6),rng.uniform(1.9,2.2),
                        rng.uniform(.86,.95),'low',.08)
            if edge in (0,2,5):
                # The northwest rim and two eastern tips show the water
                # through the soft upper fringe. Place small cloud cores just
                # over these actual stone edges; their tops stay at ~2m.
                columns=range(9) if edge==2 else range(3)
                for layer in range(3):
                    for column in columns:
                        t=(column+.5+rng.uniform(-.04,.04))/9.
                        distance=-.45+layer*.42
                        x=a[0]+(b[0]-a[0])*t+normal[0]*distance
                        z=a[1]+(b[1]-a[1])*t+normal[1]*distance
                        add(x,.95,z,3.8,2.2,.94,'low',.05,variant=4+layer)
        elif target.kind == 'backdrop':
            # Large distant fragments sit on actual outer world strips, not
            # near the camera. Their horizon coverage hides old lake hills.
            nx,nz = max(2,math.ceil(2*hx/24)),max(2,math.ceil(2*hz/24))
            for iz in range(nz):
                for ix in range(nx):
                    for row in range(2):
                        add(cx-hx+(ix+.5)*2*hx/nx+rng.uniform(-3.,3.),
                            cy-hy*.35+row*hy*.75,
                            cz-hz+(iz+.5)*2*hz/nz+rng.uniform(-3.,3.),
                            rng.uniform(30.,39.),rng.uniform(25.,34.),rng.uniform(.69,.85),'far',.6)
        elif target.kind == 'foreground':
            for _ in range(42):
                x,z = cx+rng.uniform(-hx,hx),cz+rng.uniform(-hz,hz)
                if abs(x)<6.7 and abs(z)<7.4:continue
                add(x,rng.uniform(.4,2.),z,rng.uniform(1.7,3.4),rng.uniform(1.1,2.3),
                    rng.uniform(.08,.19),'wisp',.23)
        else:
            # A low, broad overlap across BOTH water datums. Quay/bridge
            # volumes follow authored rectangles; none crosses the pavilion.
            spacing = 3. if target.kind=='water' else 2.8
            nx,nz = max(2,math.ceil(2*hx/spacing)),max(2,math.ceil(2*hz/spacing))
            for iz in range(nz):
                for ix in range(nx):
                    for row in range(2):
                        x = cx-hx+(ix+.5)*2*hx/nx+rng.uniform(-.25,.25)
                        z = cz-hz+(iz+.5)*2*hz/nz+rng.uniform(-.25,.25)
                        if abs(x)<6.7 and abs(z)<7.4:continue
                        y = (.45 if row==0 else 1.1)+rng.uniform(-.15,.15)
                        if target.kind=='bridge':y+=.45
                        add(x,y,z,rng.uniform(4.1,5.2),rng.uniform(3.2,4.4),
                            rng.uniform(.64,.82),'low',.18)
            if target.id=='water-west-basin':
                # Short north-cap overlap joins the basin's low layer to the
                # adjacent rim. It covers the oblique water sightline while
                # staying well below the surrounding house envelopes.
                for cap_layer in range(4):
                    add(-7.0-cap_layer*.6,1.55,5.35+cap_layer*.15,
                        4.5,2.2,.94,'low',.05,variant=4+cap_layer)
        if len(local)>=4096:raise ValueError(f'Too many particles for target {target.id}')
        result.extend(local)
    return tuple(result)


@lru_cache(maxsize=4)
def _building_parameters(direction):
    from g_huxin_canals_targets import target_groups
    targets = {target.id:target for target in target_groups()}
    settings = {group.id:group for group in direction.groups}
    result = []
    end = direction.cue('end')
    for seed in _building_layout():
        target,setting = targets[seed.group_id],settings[seed.group_id]
        span = setting.reveal_end-setting.reveal_start
        # Reveal begins with spatial recession. Give that movement a readable
        # lead before thinning the cloud; the authored end still means clear.
        start = setting.reveal_start+span*seed.stagger+min(1.4,span*.18)
        onset = span*.05
        effective = setting.reveal_end-start-onset*(-math.expm1(-(setting.reveal_end-start)/onset))
        tau = effective/-math.log(seed.density)
        duration = end-start
        total = duration-onset*(-math.expm1(-duration/onset))
        tail_tau = max(.1,(end-setting.reveal_start)*.35)
        fast_endpoint,tail_endpoint = math.exp(-total/tau),math.exp(-total/tail_tau)
        result.append((seed,target,setting,start,onset,tau,tail_tau,fast_endpoint,tail_endpoint))
    return tuple(result)


def _building_decay(elapsed,start,onset,tau,tail_tau,fast_endpoint,tail_endpoint):
    if elapsed<=start:return 1.
    age=elapsed-start
    age-=onset*(-math.expm1(-age/onset))
    fast=max(0.,(math.exp(-age/tau)-fast_endpoint)/(1.-fast_endpoint))
    tail=max(0.,(math.exp(-age/tail_tau)-tail_endpoint)/(1.-tail_endpoint))
    return .994*fast+.006*tail


def _target_motion(seed,target):
    """Local retreat destination and circulation, independent of any camera.

    House clouds recede into their district, away from the adjacent canal.
    Water runs along its channel. This is deliberately not an expanding ring
    from the puzzle, nor a displacement towards a facade's outward normal.
    """
    cx,_,cz=target.center
    variation=.5+.5*math.sin(seed.phase*1.7)
    side=-1. if cx<0. else 1.
    arm=-1. if cz<0. else 1.
    if target.kind=='house':
        axis=(side,.24*math.sin(cx*.31+cz*.19))
        distance=3.8+variation*1.6
        lift=.35+variation*.65
    elif target.kind=='backdrop':
        axis=(side,0.) if abs(cx)>abs(cz) else (0.,arm)
        distance=6.+variation*2.;lift=.8
    elif target.id.startswith('waterline-'):
        # Shallow fragments slip along the rim towards the side basins; they
        # never rise into another chest-high enclosure around the player.
        axis=(side,.35*math.sin(cx+cz))
        distance=1.4+variation*.7;lift=-.10
    else:
        axis=(.23*math.sin(cx*.3),arm)
        distance=2.+variation*1.4;lift=0. if seed.layer=='low' else .3
    length=math.hypot(*axis)
    normal=(axis[0]/length,0.,axis[1]/length)
    tangent=(-normal[2],0.,normal[0])
    low=seed.layer=='low'
    amplitude=(max(.24,min(.65,seed.drift*3.5)) if low
               else max(.65,min(2.,seed.drift*4.2)))
    rise=.025 if low else .18 if target.kind=='house' else .28
    rate=seed.speed*(4. if seed.layer=='far' else 6.)
    retreat=(normal[0]*distance,lift,normal[2]*distance)
    bend_amount=(.35 if low else 1.15)*math.sin(seed.phase*1.3)
    bend=(tangent[0]*bend_amount,0. if low else .25*variation,tangent[2]*bend_amount)
    if target.kind=='house':
        # Circulate along each individual facade until its reveal, keeping
        # the shallow depth component outside the padded building bounds.
        # The later retreat still follows the districtward destination above.
        dx,dz=seed.center[0]-cx,seed.center[2]-cz
        hx,_,hz=target.half_extents
        normal=((math.copysign(1.,dx),0.,0.) if abs(dx)-hx>abs(dz)-hz
                else (0.,0.,math.copysign(1.,dz)))
        tangent=(-normal[2],0.,normal[0])
    return normal,tangent,amplitude,rise,rate,retreat,bend


@lru_cache(maxsize=4)
def _building_arrays(direction):
    """Cache immutable profile data; only vectorized time samples vary/frame."""
    parameters=_building_parameters(direction)
    seeds=tuple(p[0] for p in parameters)
    target=np.array([p[1].center for p in parameters])
    scale=np.array([p[2].scale for p in parameters])
    offset=np.array([p[2].offset for p in parameters])
    centers=np.array([seed.center for seed in seeds])
    arrays={name:np.array([getattr(seed,name) for seed in seeds])
            for name in ('birth','fade_in','phase','speed','drift','alpha','width','height')}
    arrays.update({name:np.array([p[index] for p in parameters]) for name,index in
                   (('start',3),('onset',4),('tau',5),('tail_tau',6),('fast_end',7),('tail_end',8))})
    arrays['base']=target+(centers-target)*scale[:,None]+offset
    arrays['drift']*=scale
    arrays['width']*=scale;arrays['height']*=scale
    arrays['opacity']=np.array([p[2].opacity for p in parameters])
    arrays['ids']=np.array([seed.id for seed in seeds],dtype=np.int64)
    arrays['variants']=np.array([seed.variant for seed in seeds],dtype=np.int32)
    arrays['group_ids']=np.array([seed.group_id for seed in seeds],dtype=object)
    arrays['layers']=np.array([seed.layer for seed in seeds],dtype=object)
    motion=tuple(_target_motion(p[0],p[1]) for p in parameters)
    for index,name in enumerate(('normal','tangent','roll','rise','flow_rate','retreat','bend')):
        arrays[name]=np.array([m[index] for m in motion])
    for name in ('roll','rise'):arrays[name]*=scale
    for name in ('retreat','bend'):arrays[name]*=scale[:,None]
    spans=np.array([p[2].reveal_end-p[2].reveal_start for p in parameters])
    arrays['move_start']=np.array([p[2].reveal_start+p[0].stagger*span
                                   for p,span in zip(parameters,spans)])
    arrays['move_duration']=spans*(.48+.10*(.5+.5*np.sin(arrays['phase'])))
    arrays['stretch']=np.array([.025 if s.layer=='low' else .055 for s in seeds])
    arrays['vertical_stretch']=np.array([0. if s.layer=='low' else .045 for s in seeds])
    for array in arrays.values():array.setflags(write=False)
    return seeds,arrays


@lru_cache(maxsize=1)
def _empty_building_frame():
    arrays=(np.empty(0,dtype=np.int64),np.empty((0,3)),
            *(np.empty(0) for _ in range(4)),np.empty(0,dtype=np.int32),
            np.empty(0,dtype=object),np.empty(0,dtype=object))
    for array in arrays:array.setflags(write=False)
    return BuildingFrame(*arrays)


@lru_cache(maxsize=4)
def building_frame_at(elapsed,clock,direction):
    """Sample a camera-independent array frame shared by every render pass.

    Float64 values match the diagnostic packet API exactly. Static IDs and
    strings are cached once per profile; only the live array slices and drift
    are produced for a new time sample. No per-particle Python object is made.
    """
    elapsed,clock=float(elapsed),float(clock)
    if not math.isfinite(elapsed) or not math.isfinite(clock):
        raise ValueError('Particle times must be finite')
    if direction.fog_mode!='buildings':
        raise ValueError('Building frames require a buildings fog profile')
    if elapsed<=0. or elapsed>=direction.cue('end'):return _empty_building_frame()
    born=_arrival_clock(elapsed*ARRIVAL_DURATION/direction.cue('build_end'))
    _,a=_building_arrays(direction)
    u=np.clip((born-a['birth'])/a['fade_in'],0.,1.)
    alpha=a['alpha']*u*u*u*(u*(u*6.-15.)+10.)
    age=np.maximum(0.,elapsed-a['start'])
    age-=a['onset']*(-np.expm1(-age/a['onset']))
    fast=np.maximum(0.,(np.exp(-age/a['tau'])-a['fast_end'])/(1.-a['fast_end']))
    tail=np.maximum(0.,(np.exp(-age/a['tail_tau'])-a['tail_end'])/(1.-a['tail_end']))
    alpha=np.minimum(1.,alpha*(.994*fast+.006*tail)*a['opacity'])
    live=np.flatnonzero(alpha>ALPHA_CUTOFF)
    if not len(live):return _empty_building_frame()
    # This independent clock never eases to a stop at the five-second crest.
    # Neighbouring layers slide past one another in three dimensions while
    # births, world blending and each building's reveal keep their own times.
    phase=a['phase'][live]+clock*a['flow_rate'][live]
    roll=a['roll'][live]
    centers=a['base'][live]
    slide=roll*(np.sin(phase)+.22*np.sin(phase*.47+a['phase'][live]))
    depth=roll*.38*np.cos(phase*.83+1.1)
    centers+=a['tangent'][live]*slide[:,None]+a['normal'][live]*depth[:,None]
    centers[:,1]+=np.sin(phase*.71+1.2)*a['rise'][live]
    progress=np.clip((elapsed-a['move_start'][live])/a['move_duration'][live],0.,1.)
    progress=progress*progress*progress*(progress*(progress*6.-15.)+10.)
    centers+=a['retreat'][live]*progress[:,None]
    centers+=a['bend'][live]*(4.*progress*(1.-progress))[:,None]
    width=a['width'][live]*(1.+a['stretch'][live]*np.sin(phase*.67))
    height=a['height'][live]*(1.+a['vertical_stretch'][live]*np.cos(phase*.79+.8))
    rotation=(.075*np.sin(phase*.53)+.018*np.sin(phase*1.13))
    rotation*=np.where(a['layers'][live]=='low',.3,1.)
    arrays=(a['ids'][live],centers,width,height,
            rotation,alpha[live],a['variants'][live],
            a['group_ids'][live],a['layers'][live])
    for array in arrays:array.setflags(write=False)
    return BuildingFrame(*arrays)


def _building_particles(elapsed,clock,direction):
    # CPU consumers can still request serializable immutable packets. Native
    # rendering consumes building_frame_at directly and skips this conversion.
    frame=building_frame_at(elapsed,clock,direction)
    rows=zip(frame.ids.tolist(),frame.centers.tolist(),frame.widths.tolist(),
             frame.heights.tolist(),frame.rotations.tolist(),frame.alphas.tolist(),
             frame.variants.tolist(),frame.layers.tolist(),frame.group_ids.tolist())
    return tuple(BuildingCloudParticle(ident,tuple(center),width,height,rotation,alpha,
                                      variant,layer,group_id)
                 for ident,center,width,height,rotation,alpha,variant,layer,group_id in rows)


def _building_schedule(direction):
    result=[]
    arrival_scale=direction.cue('build_end')/ARRIVAL_DURATION
    for seed,target,setting,start,*_ in _building_parameters(direction):
        result.append(BuildingParticleLifetime(seed.id,seed.wave,_arrival_time(seed.birth)*arrival_scale,
                        _arrival_time(seed.birth+seed.fade_in)*arrival_scale,start,direction.cue('end'),
                        min(1.,seed.alpha*setting.opacity),seed.layer,target.band,setting.reveal_end,
                        math.hypot(seed.center[0],seed.center[2]),seed.group_id))
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
