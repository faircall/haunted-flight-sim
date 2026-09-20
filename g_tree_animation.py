"""Stateless willow wind rig. Coordinates are pixels on the authored 128px canvas."""
import math
from functools import lru_cache

import g_effects


# The centres of the five magenta crosses in willow_tree_pivotst.png.
# Draw rear crown first; the foreground curtains overlap their branch attachments.
PARTS = (
    dict(name="top_left", pivot=(56, 19), bounds=(35, 11, 67, 67), stiffness=0.65, phase=0.8,
         exposure=.85, lag=.25, response=.7, flutter=.65, bend_gain=.65),
    dict(name="top_right", pivot=(77, 12), bounds=(60, 5, 100, 76), stiffness=0.75, phase=1.7,
         exposure=1., lag=.4, response=.9, flutter=.5, bend_gain=.8),
    dict(name="left_outer", pivot=(32, 31), bounds=(10, 27, 39, 102), stiffness=1.0, phase=2.4,
         exposure=1.1, lag=.12, response=.35, flutter=.85, bend_gain=1.15),
    dict(name="left_inner", pivot=(46, 45), bounds=(30, 41, 62, 113), stiffness=0.85, phase=3.5,
         exposure=.6, lag=.55, response=.8, flutter=.55, bend_gain=.9),
    dict(name="right_outer", pivot=(102, 43), bounds=(78, 40, 119, 121), stiffness=0.95, phase=4.7,
         exposure=1., lag=.3, response=.5, flutter=.7, bend_gain=1.25),
)


def regular_motion(part, elapsed, wind_profile, world=(0.0, 0.0), mode="hybrid"):
    """Slow correlated branch response plus delayed, smaller frond-tip movement."""
    if mode == "still":
        return 0.0, 0.0
    wind = g_effects.sample_wind(wind_profile, *world, elapsed)
    delayed = g_effects.sample_wind(wind_profile, *world, elapsed - 0.18 * part["phase"])
    # World Y contributes less in this upright sprite's projected view.
    force = (0.8 * wind["x"] + 0.2 * delayed["x"] + 0.2 * wind["y"]) / 13.0
    strength = min(2.0, math.hypot(wind["x"], wind["y"]) / 13.0)
    phase = part["phase"] + world[0] * .019 + world[1] * .013
    angle = -part["stiffness"] * (2.6 * force + .45 * strength * math.sin(elapsed * 1.7 + phase))
    bend = 0.0
    if mode == "hybrid":
        bend = part["stiffness"] * (1.5 * force + strength * (
            .7 * math.sin(elapsed * 2.3 + phase) + .25 * math.sin(elapsed * 4.1 + phase * 1.6)))
    return math.radians(max(-7.0, min(7.0, angle))), max(-5.0, min(5.0, bend))


def smooth_noise(value, seed):
    """Deterministic random targets with smooth velocity/acceleration at joins."""
    cell = math.floor(value)
    fraction = value - cell
    blend = fraction ** 3 * (fraction * (fraction * 6.0 - 15.0) + 10.0)
    # procedural_hash already returns 0..1, rather than a raw uint32.
    a = g_effects.procedural_hash(cell, seed, 7919) * 2.0 - 1.0
    b = g_effects.procedural_hash(cell + 1, seed, 7919) * 2.0 - 1.0
    return a + (b - a) * blend


def irregular_wind(profile, world, elapsed):
    """Shared gust envelope, sampled later by slower/heavier foliage clusters."""
    seed = int(profile.get("tree_seed", 17))
    phase = (world[0] * .73 + world[1] * 1.19) * profile.get("spatial_scale", .015)
    t = elapsed * max(0., profile.get("gust_speed", .35)) + phase
    gust = .75 * smooth_noise(t, seed) + .25 * smooth_noise(t * 2.7, seed + 1)
    # Long lulls modulate both the prevailing wind and the shorter gusts.
    lull = .75 + .25 * smooth_noise(t * .27, seed + 2)
    local = dict(profile, strength=(profile.get("strength", 8.) +
        profile.get("gust_strength", 5.) * gust) * lull, gust_strength=0.)
    return g_effects.sample_wind(local, *world, elapsed)


def motion(part, elapsed, wind_profile, world=(0.0, 0.0), mode="hybrid"):
    if not wind_profile.get("tree_irregular", True):
        return regular_motion(part, elapsed, wind_profile, world, mode)
    if mode == "still":
        return 0., 0.
    t = elapsed - part["lag"]
    # Average delayed samples: a stateless approximation of a slower branch response.
    samples = [irregular_wind(wind_profile, world, t - part["response"] * offset)
               for offset in (0., .5, 1.)]
    wx = sum(w["x"] for w in samples) / 3.
    wy = sum(w["y"] for w in samples) / 3.
    force = (wx + .2 * wy) / 13. * part["exposure"]
    strength = min(2., math.hypot(wx, wy) / 13.) * part["exposure"]
    seed = int(wind_profile.get("tree_seed", 17)) + int(part["phase"] * 100)
    spatial_phase = world[0] * .019 + world[1] * .013
    local_sway = smooth_noise(t * .4 + spatial_phase, seed)
    # Keep small detail slow and low-amplitude to avoid noisy one-pixel flicker.
    flutter = smooth_noise(t * part["flutter"] + spatial_phase, seed + 1)
    angle = -part["stiffness"] * (2.6 * force + .6 * strength * local_sway)
    bend = (part["bend_gain"] * (1.6 * force + .85 * strength * flutter)
            if mode == "hybrid" else 0.)
    return math.radians(max(-7., min(7., angle))), max(-5., min(5., bend))


def deform_point(point, part, angle, bend):
    """Pin the attachment exactly; let displacement increase along hanging fronds."""
    px, py = part["pivot"]
    x, y = point[0] - px, point[1] - py
    length = max(1.0, part["bounds"][3] - py)
    weight = max(0.0, min(1.0, y / length))
    x += bend * weight * weight
    c, s = math.cos(angle), math.sin(angle)
    return px + x * c - y * s, py + x * s + y * c


def strip_mesh(part, elapsed, wind_profile, world=(0.0, 0.0), mode="hybrid"):
    """Connected textured quads, with UVs into the unchanged full-size source art."""
    angle, bend = motion(part, elapsed, wind_profile, world, mode)
    left, top, right, bottom = part["bounds"]
    rows = list(range(top, bottom, 4)) + [bottom]
    for y0, y1 in zip(rows, rows[1:]):
        yield tuple((*deform_point((x, y), part, angle, bend), x / 128.0, y / 128.0)
                    for x, y in ((left, y0), (left, y1), (right, y1), (right, y0)))


def grid_deform_point(point, part, angle, bend, elapsed, strength, phase):
    """Broad strand-like regions move together; adjacent columns move differently."""
    px, py = part["pivot"]
    x, y = point
    width = part["bounds"][2] - part["bounds"][0]
    length = max(1., part["bounds"][3] - py)
    along = max(0., min(1., (y - py) / length))
    # Pin a small attachment region. Elsewhere even the upper foliage can rustle.
    attachment = min(1., math.hypot(x - px, y - py) / 8.)
    attachment = attachment * attachment * (3. - 2. * attachment)
    weight = attachment * (.25 + .75 * along)
    strand_phase = (x - px) / max(1., width) * math.tau * 1.25 + phase
    t = elapsed - part["lag"] - along * .3
    # Continuous low-frequency motion underneath the shared irregular gusts.
    wave = (math.sin(t * 1.35 + strand_phase) +
            .35 * math.sin(t * 2.05 - strand_phase * .7 + phase))
    dx = strength * part["bend_gain"] * weight * 1.35 * wave
    dy = strength * weight * .3 * math.sin(t * 1.6 + strand_phase + .8)
    local_bend = bend * (.8 + .2 * math.sin(strand_phase))
    return deform_point((x + dx, y + dy), part, angle, local_bend)


def grid_mesh(part, elapsed, wind_profile, world=(0.0, 0.0), mode="hybrid"):
    """A connected 4px grid; UVs remain fixed to the original artwork."""
    angle, bend = motion(part, elapsed, wind_profile, world, mode)
    sample = irregular_wind if wind_profile.get("tree_irregular", True) else g_effects.sample_wind
    wind = (sample(wind_profile, world, elapsed) if sample is irregular_wind else
            sample(wind_profile, *world, elapsed))
    strength = min(1.5, math.hypot(wind["x"], wind["y"]) / 8.) * part["exposure"]
    if mode != "hybrid":
        strength = 0.
    phase = part["phase"] + world[0] * .019 + world[1] * .013 + int(wind_profile.get("tree_seed", 17)) * .37
    left, top, right, bottom = part["bounds"]
    # Include the actual pivot as a vertex so interpolated triangles also pin it.
    columns = sorted(set([*range(left, right, 4), right, part["pivot"][0]]))
    rows = sorted(set([*range(top, bottom, 4), bottom, part["pivot"][1]]))
    vertices = {}
    for y in rows:
        for x in columns:
            pos = (grid_deform_point((x, y), part, angle, bend, elapsed, strength, phase)
                   if mode == "hybrid" else deform_point((x, y), part, angle, bend))
            vertices[x, y] = (*pos, x / 128., y / 128.)
    for y0, y1 in zip(rows, rows[1:]):
        for x0, x1 in zip(columns, columns[1:]):
            yield tuple(vertices[point] for point in ((x0, y0), (x0, y1), (x1, y1), (x1, y0)))


def foliage_mesh(part, elapsed, wind_profile, world=(0.0, 0.0), mode="hybrid"):
    builder = strip_mesh if wind_profile.get("tree_mesh", "grid") == "strips" else grid_mesh
    return builder(part, elapsed, wind_profile, world, mode)


@lru_cache(maxsize=64)
def mesh_topology(bounds, pivot, strips=False):
    """Immutable shared vertices, UVs, indices and rest-pose deformation weights."""
    left, top, right, bottom = bounds
    px, py = pivot
    columns = [left, right] if strips else sorted(set([*range(left, right, 4), right, px]))
    rows = list(range(top, bottom, 4)) + [bottom]
    if not strips:
        rows = sorted(set([*rows, py]))
    points, weights, indices = [], [], []
    for y in rows:
        for x in columns:
            along = max(0., min(1., (y - py) / max(1., bottom - py)))
            attachment = min(1., math.hypot(x - px, y - py) / 8.)
            attachment = attachment * attachment * (3. - 2. * attachment)
            points.append((x, y))
            weights.append((along, attachment * (.25 + .75 * along),
                            (x - px) / max(1., right - left) * math.tau * 1.25))
    width = len(columns)
    for row in range(len(rows) - 1):
        for col in range(width - 1):
            a = row * width + col
            b, c, d = a + width, a + width + 1, a + 1
            indices.extend((a, b, c, a, c, d))
    return tuple(points), tuple(weights), tuple(indices)


def mesh_pose(part, elapsed, profile, world=(0., 0.)):
    """Evaluate each shared vertex once, with fixed weights and per-part rotation."""
    strips = profile.get("tree_mesh", "grid") == "strips"
    points, weights, _ = mesh_topology(tuple(part["bounds"]), tuple(part["pivot"]), strips)
    angle, bend = motion(part, elapsed, profile, world)
    c, s = math.cos(angle), math.sin(angle)
    px, py = part["pivot"]
    length = max(1., part["bounds"][3] - py)
    strength = 0.
    if not strips:
        wind = (irregular_wind(profile, world, elapsed) if profile.get("tree_irregular", True)
                else g_effects.sample_wind(profile, *world, elapsed))
        strength = min(1.5, math.hypot(wind["x"], wind["y"]) / 8.) * part["exposure"]
    phase = part["phase"] + world[0] * .019 + world[1] * .013 + int(profile.get("tree_seed", 17)) * .37
    positions = []
    for (x, y), (along, weight, phase_offset) in zip(points, weights):
        local_bend = bend
        if not strips:
            strand_phase = phase_offset + phase
            t = elapsed - part["lag"] - along * .3
            wave = math.sin(t * 1.35 + strand_phase) + .35 * math.sin(t * 2.05 - strand_phase * .7 + phase)
            x += strength * part["bend_gain"] * weight * 1.35 * wave
            y += strength * weight * .3 * math.sin(t * 1.6 + strand_phase + .8)
            local_bend *= .8 + .2 * math.sin(strand_phase)
        x, y = x - px, y - py
        # Re-evaluate bend weight after vertical movement, as in deform_point.
        bend_weight = max(0., min(1., y / length))
        x += local_bend * bend_weight * bend_weight
        positions.append((px + x * c - y * s, py + x * s + y * c))
    return positions, angle
