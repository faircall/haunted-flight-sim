"""Authored procedural environment effects and CPU gameplay bursts.

Smoke, fire, and embers are described by serialisable emitter dictionaries and
generated entirely by local fragment shaders.  This
module deliberately creates no live particles for those continuous effects.
Only short gameplay bursts whose state matters (currently blood) are simulated
on the CPU.
"""

import copy
import math
import time


RENDER_GROUPS = ("floor_lit", "world_behind", "world_front", "emissive")
PROCEDURAL_EFFECT_TYPES = ("smoke", "fire", "ember")
EFFECT_SHADER_VERSION = 2


def _common_emitter(effect_type, position, *, area_size, render_group, seed):
    return {
        "type": effect_type,
        "enabled": True,
        "position": copy.deepcopy(position),
        "area_size": copy.deepcopy(area_size),
        "seed": int(seed),
        "render_group": render_group,
        "preview_enabled": True,
        "shader_version": EFFECT_SHADER_VERSION,
    }


def make_default_smoke_emitter(position):
    result = _common_emitter(
        "smoke", position, area_size={"x": 16.0, "y": 4.0},
        render_group="world_front", seed=1103,
    )
    result.update({
        "size": {"x": 34.0, "y": 52.0},
        "density": 0.72,
        "speed": 0.46,
        "evolution_speed": 0.62,
        "turbulence": 0.78,
        "detail_scale": 0.16,
        "warp_strength": 0.85,
        "wind_response": 0.36,
        "opacity": 0.58,
        "posterize_levels": 6,
        "color": [0.42, 0.43, 0.48, 1.0],
    })
    return result


def make_default_fire_emitter(position):
    result = _common_emitter(
        "fire", position, area_size={"x": 18.0, "y": 4.0},
        render_group="world_front", seed=2207,
    )
    result.update({
        "size": {"x": 18.0, "y": 26.0},
        "density": 0.92,
        "speed": 1.0,
        "turbulence": 0.82,
        "wind_response": 0.42,
        "opacity": 0.94,
        "posterize_levels": 5,
        "ember_density": 0.18,
        "ember_height": 18.0,
        "palette": {
            "core": [1.0, 0.94, 0.55, 1.0],
            "hot": [1.0, 0.67, 0.18, 1.0],
            "mid": [0.92, 0.25, 0.045, 1.0],
            "outer": [0.30, 0.025, 0.012, 1.0],
        },
        "light": {
            "enabled": True,
            "color": [1.0, 0.45, 0.16],
            "radius": 70.0,
            "intensity": 0.8,
            "height": 18.0,
            "flicker_strength": 0.15,
            "flicker_speed": 7.0,
            "affects_world": True,
            "affects_entities": True,
            "affects_fog": True,
            "affects_ai": False,
            "casts_wall_shadows": True,
        },
    })
    return result


def make_default_ember_emitter(position):
    """Create a standalone procedural ember field using effect_fire.fs."""
    result = _common_emitter(
        "ember", position, area_size={"x": 18.0, "y": 6.0},
        render_group="emissive", seed=3301,
    )
    result.update({
        "size": {"x": 24.0, "y": 42.0},
        "density": 0.22,
        "speed": 0.78,
        "turbulence": 0.55,
        "wind_response": 0.72,
        "opacity": 0.92,
        "posterize_levels": 4,
        "color": [1.0, 0.52, 0.12, 1.0],
    })
    return result


_FACTORIES = {
    "smoke": make_default_smoke_emitter,
    "fire": make_default_fire_emitter,
    "ember": make_default_ember_emitter,
}


_OBSOLETE_FIELDS = {
    "spawn_rate", "max_particles", "lifetime", "lifetime_variation",
    "start_size", "end_size", "starting_height", "height_variation",
    "fall_speed", "splash_amount", "angular_speed", "gravity",
    "collision_mode", "material", "emissive_fraction", "smoke_rate",
    "ember_rate", "drift",
}


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, float(value)))


def migrate_emitter(emitter):
    """Migrate one legacy CPU-oriented emitter in place.

    Authored values are retained where they still have shader meaning.  Legacy
    spawn budgets are converted to a bounded density before obsolete controls
    are removed, so existing levels continue to produce a useful result.
    """
    if not isinstance(emitter, dict):
        return emitter
    effect_type = emitter.get("type")
    factory = _FACTORIES.get(effect_type)
    if factory is None:
        return emitter

    defaults = factory(emitter.get("position", {}))
    old_rate = float(emitter.get("spawn_rate", 0.0))
    old_maximum = float(emitter.get("max_particles", 0.0))
    if "density" not in emitter:
        scale = {"smoke": 18.0, "fire": 30.0, "ember": 24.0}[effect_type]
        emitter["density"] = _clamp(max(old_rate, old_maximum * 0.25) / scale, 0.02, 1.0)

    if "size" not in emitter:
        emitter["size"] = copy.deepcopy(defaults.get("size", emitter.get("area_size", {"x": 8.0, "y": 8.0})))
        if effect_type == "fire" and "height" in emitter:
            emitter["size"]["y"] = max(1.0, float(emitter["height"]))
        if effect_type == "smoke":
            emitter["size"]["x"] = max(float(emitter.get("end_size", 11.0)) * 3.0, 4.0)
            emitter["size"]["y"] = max(float(emitter.get("rise_speed", 13.0)) * float(emitter.get("lifetime", 2.8)), 8.0)

    if "speed" not in emitter:
        if effect_type == "smoke":
            emitter["speed"] = _clamp(float(emitter.get("rise_speed", 13.0)) / 28.0, 0.02, 4.0)
        else:
            emitter["speed"] = defaults.get("speed", 1.0)

    legacy_color = emitter.get("flame_color") if effect_type == "fire" else emitter.get("color")
    for key, value in defaults.items():
        if key not in emitter:
            emitter[key] = copy.deepcopy(value)
    if effect_type == "fire" and legacy_color is not None and "palette" in emitter:
        values = list(legacy_color)
        while len(values) < 4:
            values.append(1.0)
        emitter["palette"]["mid"] = values[:4]

    for key in _OBSOLETE_FIELDS:
        emitter.pop(key, None)
    emitter.pop("flame_color", None)
    emitter.pop("core_color", None)
    emitter["shader_version"] = EFFECT_SHADER_VERSION
    return emitter


def migrate_emitters(emitters):
    if not isinstance(emitters, dict):
        return emitters
    for emitter_id in list(emitters):
        emitter = emitters[emitter_id]
        if emitter.get("type") in {"rain", "leaf"}:
            del emitters[emitter_id]
            continue
        migrate_emitter(emitter)
    return emitters


def make_wind_profile(profile_name="default"):
    return {
        "name": str(profile_name),
        "direction": {"x": 1.0, "y": 0.0},
        "strength": 8.0,
        "gust_strength": 5.0,
        "gust_speed": 0.35,
        "spatial_scale": 0.015,
        "vertical_flutter": 0.0,
    }


def make_rain_profile(profile_name="default"):
    """Return fresh, serialisable global weather state for GPU-authored rain."""
    return {
        "name": str(profile_name),
        "enabled": False,
        "density": 0.30,
        "speed": 1.0,
        "direction": {"x": 0.12, "y": 1.0},
        "seed": 4409,
        "cell_size": {"x": 9.0, "y": 14.0},
        "streak_length": 4.0,
        "unlit_opacity": 0.012,
        "lit_opacity": 0.20,
        "light_threshold": 0.04,
        "light_response": 1.0,
        "light_color_influence": 0.70,
        "ambient_color": [0.40, 0.48, 0.62],
        "opacity_levels": 4,
        "distortion_enabled": True,
        "distortion_strength": 1.0,
        "distortion_density": 0.16,
        "distortion_scale": 18.0,
        "distortion_speed": 0.55,
    }


def normalize_rain_profile(rain_profile):
    """Fill and constrain a rain profile in place, including a safe direction."""
    profile = rain_profile if isinstance(rain_profile, dict) else make_rain_profile()
    defaults = make_rain_profile(profile.get("name", "default"))
    for key, value in defaults.items():
        if key not in profile:
            profile[key] = copy.deepcopy(value)

    direction = profile.get("direction")
    if not isinstance(direction, dict):
        direction = {}
    dx = float(direction.get("x", defaults["direction"]["x"]))
    dy = float(direction.get("y", defaults["direction"]["y"]))
    length = math.hypot(dx, dy)
    if length <= 0.000001:
        dx, dy, length = 0.0, 1.0, 1.0
    profile["direction"] = {"x": dx / length, "y": dy / length}

    cell_size = profile.get("cell_size")
    if not isinstance(cell_size, dict):
        cell_size = defaults["cell_size"]
    profile["cell_size"] = {
        "x": _clamp(cell_size.get("x", 9.0), 2.0, 128.0),
        "y": _clamp(cell_size.get("y", 14.0), 2.0, 128.0),
    }
    profile["enabled"] = bool(profile.get("enabled", False))
    profile["density"] = _clamp(profile.get("density", 0.30), 0.0, 1.0)
    profile["speed"] = _clamp(profile.get("speed", 1.0), 0.0, 20.0)
    profile["seed"] = int(profile.get("seed", 4409))
    profile["streak_length"] = _clamp(profile.get("streak_length", 4.0), 1.0, 8.0)
    profile["unlit_opacity"] = _clamp(profile.get("unlit_opacity", 0.012), 0.0, 1.0)
    profile["lit_opacity"] = _clamp(profile.get("lit_opacity", 0.20), 0.0, 1.0)
    profile["light_threshold"] = _clamp(profile.get("light_threshold", 0.04), 0.0, 1.0)
    profile["light_response"] = _clamp(profile.get("light_response", 1.0), 0.0, 20.0)
    profile["light_color_influence"] = _clamp(profile.get("light_color_influence", 0.70), 0.0, 1.0)
    ambient = list(profile.get("ambient_color", defaults["ambient_color"]))[:3]
    while len(ambient) < 3:
        ambient.append(defaults["ambient_color"][len(ambient)])
    profile["ambient_color"] = [_clamp(value, 0.0, 1.0) for value in ambient]
    profile["opacity_levels"] = max(2, min(64, int(round(float(profile.get("opacity_levels", 4))))))
    profile["distortion_enabled"] = bool(profile.get("distortion_enabled", True))
    # This milestone has a hard one-internal-pixel displacement contract.
    profile["distortion_strength"] = _clamp(profile.get("distortion_strength", 1.0), 0.0, 1.0)
    profile["distortion_density"] = _clamp(profile.get("distortion_density", 0.16), 0.0, 1.0)
    profile["distortion_scale"] = _clamp(profile.get("distortion_scale", 18.0), 2.0, 128.0)
    profile["distortion_speed"] = _clamp(profile.get("distortion_speed", 0.55), 0.0, 20.0)
    return profile


def get_tile_rain_exposure(tile):
    if not isinstance(tile, dict):
        return 0.0
    return _clamp(tile.get("rain_exposure", 0.0), 0.0, 1.0)


def set_tile_rain_exposure(tile, exposure):
    """Set independent authored exposure and report whether its value changed."""
    if not isinstance(tile, dict):
        return False
    value = _clamp(exposure, 0.0, 1.0)
    previous = get_tile_rain_exposure(tile)
    if value <= 0.0:
        tile.pop("rain_exposure", None)
    else:
        tile["rain_exposure"] = float(value)
    return previous != value


def mark_rain_exposure_dirty(tile_map):
    tile_map["rain_exposure_revision"] = int(tile_map.get("rain_exposure_revision", 0)) + 1
    return tile_map["rain_exposure_revision"]


def build_rain_exposure_pixel_data(tile_map):
    """Build row-major RGBA8 data with one opaque pixel per authored map tile."""
    width = max(0, int((tile_map or {}).get("map_width", 0)))
    height = max(0, int((tile_map or {}).get("map_height", 0)))
    tiles = (tile_map or {}).get("tiles", ())
    pixels = bytearray(width * height * 4)
    for flat_index in range(width * height):
        exposure = get_tile_rain_exposure(tiles[flat_index] if flat_index < len(tiles) else None)
        channel = max(0, min(255, int(round(exposure * 255.0))))
        offset = flat_index * 4
        pixels[offset] = channel
        pixels[offset + 1] = 0
        pixels[offset + 2] = 0
        pixels[offset + 3] = 255
    return bytes(pixels)


def count_exposed_rain_tiles(tile_map):
    width = max(0, int((tile_map or {}).get("map_width", 0)))
    height = max(0, int((tile_map or {}).get("map_height", 0)))
    tiles = (tile_map or {}).get("tiles", ())
    return sum(
        1 for index in range(min(width * height, len(tiles)))
        if get_tile_rain_exposure(tiles[index]) > 0.0
    )


def flood_fill_rain_exposure(tile_map, start_x, start_y, target_exposure):
    """Iteratively replace a four-connected region matching the start exposure."""
    width = max(0, int((tile_map or {}).get("map_width", 0)))
    height = max(0, int((tile_map or {}).get("map_height", 0)))
    tiles = (tile_map or {}).get("tiles", ())
    start_x = int(start_x)
    start_y = int(start_y)
    replacement = _clamp(target_exposure, 0.0, 1.0)
    if start_x < 0 or start_y < 0 or start_x >= width or start_y >= height:
        return 0
    start_index = start_y * width + start_x
    if start_index >= len(tiles):
        return 0
    initial = get_tile_rain_exposure(tiles[start_index])
    if initial == replacement:
        return 0

    changed = 0
    pending = [(start_x, start_y)]
    seen = set()
    while pending:
        x, y = pending.pop()
        if (x, y) in seen or x < 0 or y < 0 or x >= width or y >= height:
            continue
        seen.add((x, y))
        flat_index = y * width + x
        if flat_index >= len(tiles) or get_tile_rain_exposure(tiles[flat_index]) != initial:
            continue
        if set_tile_rain_exposure(tiles[flat_index], replacement):
            changed += 1
        pending.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    if changed:
        mark_rain_exposure_dirty(tile_map)
    return changed


def fill_map_rain_exposure(tile_map, target_exposure):
    width = max(0, int((tile_map or {}).get("map_width", 0)))
    height = max(0, int((tile_map or {}).get("map_height", 0)))
    tiles = (tile_map or {}).get("tiles", ())
    changed = sum(
        1 for tile in tiles[:width * height]
        if set_tile_rain_exposure(tile, target_exposure)
    )
    if changed:
        mark_rain_exposure_dirty(tile_map)
    return changed


def sample_wind(wind_profile, world_x, world_y, time_elapsed):
    profile = wind_profile or make_wind_profile()
    direction = profile.get("direction", {})
    dx = float(direction.get("x", 1.0))
    dy = float(direction.get("y", 0.0))
    length = math.hypot(dx, dy)
    if length <= 0.000001:
        dx, dy, length = 1.0, 0.0, 1.0
    dx /= length
    dy /= length
    spatial = float(profile.get("spatial_scale", 0.015))
    phase = (float(world_x) * 0.73 + float(world_y) * 1.19) * spatial
    gust = math.sin(float(time_elapsed) * float(profile.get("gust_speed", 0.35)) * math.tau + phase)
    cross = math.sin(float(time_elapsed) * 0.41 + phase * 1.7) * float(profile.get("vertical_flutter", 0.0))
    magnitude = float(profile.get("strength", 8.0)) + gust * float(profile.get("gust_strength", 5.0))
    return {"x": dx * magnitude - dy * cross, "y": dy * magnitude + dx * cross}


def procedural_hash(cell_x, cell_y, seed):
    """Stable CPU reference for the shaders' integer cell hash."""
    value = (int(cell_x) * 374761393 + int(cell_y) * 668265263 + int(seed) * 69069) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16
    return (value & 0xFFFFFFFF) / 4294967295.0


def position_to_world(position, tile_map=None):
    position = position or {}
    if "tile_x" in position or "tile_y" in position:
        tile_width = float((tile_map or {}).get("tile_width", 16.0))
        tile_height = float((tile_map or {}).get("tile_height", 16.0))
        return {
            "x": float(position.get("tile_x", 0)) * tile_width + float(position.get("x", 0.0)),
            "y": float(position.get("tile_y", 0)) * tile_height + float(position.get("y", 0.0)),
        }
    return {"x": float(position.get("x", 0.0)), "y": float(position.get("y", 0.0))}


def emitter_world_bounds(emitter, tile_map=None):
    """Return the exact conservative shader quad in world screen-plane units."""
    effect_type = emitter.get("type", "")
    centre = position_to_world(emitter.get("position", {}), tile_map)
    area = emitter.get("area_size", {})
    area_width = max(1.0, float(area.get("x", 1.0)))
    area_height = max(1.0, float(area.get("y", 1.0)))

    if effect_type in {"smoke", "fire", "ember"}:
        size = emitter.get("size", {})
        width = max(area_width, float(size.get("x", area_width)))
        height = max(area_height, float(size.get("y", area_height)))
        extra_height = float(emitter.get("ember_height", 0.0)) if effect_type == "fire" else 0.0
        wind_pad = min(height * 0.45, abs(float(emitter.get("wind_response", 0.0))) * 10.0)
        direction = emitter.get("direction")
        if isinstance(direction, dict):
            direction_x = float(direction.get("x", 0.0))
            direction_y = float(direction.get("y", 0.0))
            direction_length = math.hypot(direction_x, direction_y)
            if direction_length > 0.000001:
                direction_x /= direction_length
                direction_y /= direction_length
                perpendicular_x = -direction_y
                perpendicular_y = direction_x
                half_width = width * 0.5 + wind_pad
                flame_length = height + extra_height
                points = [
                    (centre["x"] + perpendicular_x * side * half_width,
                     centre["y"] + perpendicular_y * side * half_width)
                    for side in (-1.0, 1.0)
                ]
                points.extend([
                    (centre["x"] + direction_x * flame_length
                     + perpendicular_x * side * half_width,
                     centre["y"] + direction_y * flame_length
                     + perpendicular_y * side * half_width)
                    for side in (-1.0, 1.0)
                ])
                padding = 2.0
                minimum_x = min(point[0] for point in points) - padding
                maximum_x = max(point[0] for point in points) + padding
                minimum_y = min(point[1] for point in points) - padding
                maximum_y = max(point[1] for point in points) + padding
                return {
                    "x": minimum_x, "y": minimum_y,
                    "width": maximum_x - minimum_x,
                    "height": maximum_y - minimum_y,
                    "anchor_x": centre["x"], "anchor_y": centre["y"],
                }
        return {
            "x": centre["x"] - width * 0.5 - wind_pad,
            "y": centre["y"] - height - extra_height,
            "width": width + wind_pad * 2.0,
            "height": height + extra_height + max(2.0, area_height * 0.5),
            "anchor_x": centre["x"], "anchor_y": centre["y"],
        }

    return {
        "x": centre["x"] - area_width * 0.5,
        "y": centre["y"] - area_height * 0.5,
        "width": area_width, "height": area_height,
        "anchor_x": centre["x"], "anchor_y": centre["y"],
    }


def make_effects_runtime():
    return {
        "bursts": {},
        "next_runtime_id": 1,
        "events": [],
        "authored_visible": True,
        "stats": _empty_stats(),
        "debug_submissions": [],
    }


def ensure_effects_runtime(game_assets):
    runtime = game_assets.get("effects_runtime")
    if not isinstance(runtime, dict):
        runtime = make_effects_runtime()
        game_assets["effects_runtime"] = runtime
    # Retire runtime data produced by the removed continuous particle system.
    runtime.pop("emitters", None)
    runtime.setdefault("bursts", {})
    runtime.setdefault("events", [])
    runtime.setdefault("next_runtime_id", 1)
    runtime.setdefault("stats", _empty_stats())
    runtime.setdefault("debug_submissions", [])
    return runtime


def clear_effects_runtime(game_assets):
    game_assets.pop("effects_runtime", None)


def discard_legacy_particle_systems(entities):
    if isinstance(entities, dict):
        entities.pop("particle_systems", None)


def _empty_stats():
    return {
        "authored_emitter_count": 0,
        "active_emitter_count": 0,
        "live_particle_count": 0,
        "burst_count": 0,
        "procedural_draw_calls": 0,
        "draw_calls_by_type": {},
        "culled_emitters": 0,
        "burst_draw_calls": 0,
        "update_time_ms": 0.0,
        "submission_time_ms": 0.0,
    }


def reset_render_stats(runtime, emitters, authored_visible):
    stats = runtime.setdefault("stats", _empty_stats())
    stats.update(_empty_stats())
    stats["authored_emitter_count"] = len(emitters or {})
    stats["active_emitter_count"] = sum(
        1 for emitter in (emitters or {}).values()
        if emitter.get("enabled", True)
    ) if authored_visible else 0
    runtime["debug_submissions"] = []
    return stats


def _next_random(state):
    value = int(state.get("random_state", 1)) & 0xFFFFFFFF
    value = (1664525 * value + 1013904223) & 0xFFFFFFFF
    state["random_state"] = value
    return value / 4294967296.0


def _random_signed(state):
    return _next_random(state) * 2.0 - 1.0


def _alpha_color(color, alpha=1.0):
    values = [float(value) for value in color]
    if len(values) == 3:
        values.append(float(alpha))
    while len(values) < 4:
        values.append(1.0)
    return values[:4]


def _base_blood_particle(owner_id, x, y, z, lifetime, size, start_color, end_color):
    return {
        "x": float(x), "y": float(y), "z": float(z),
        "vx": 0.0, "vy": 0.0, "vz": 0.0,
        "age": 0.0, "lifetime": max(0.001, float(lifetime)),
        "size": float(size), "start_size": float(size), "end_size": float(size),
        "start_color": list(start_color), "end_color": list(end_color),
        "render_group": "world_front", "material": "lit_alpha",
        "effect_type": "blood", "owner_id": owner_id,
        "collision_mode": "stop_on_solid", "gravity": 0.0,
    }


def _tile_is_solid(world_x, world_y, tile_map):
    if not tile_map:
        return False
    width = int(tile_map.get("map_width", 0))
    height = int(tile_map.get("map_height", 0))
    tile_width = max(1.0, float(tile_map.get("tile_width", 16.0)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16.0)))
    tile_x = math.floor(world_x / tile_width)
    tile_y = math.floor(world_y / tile_height)
    if tile_x < 0 or tile_y < 0 or tile_x >= width or tile_y >= height:
        return True
    tiles = tile_map.get("tiles", [])
    flat = tile_y * width + tile_x
    if flat < 0 or flat >= len(tiles):
        return True
    tile = tiles[flat]
    if tile.get("force_collidable", False):
        return True
    index = int(tile.get("index", 0))
    types = tile_map.get("tile_types", [])
    return 0 <= index < len(types) and types[index].get("type") == "wall"


def _update_blood_particle(particle, dt, tile_map, runtime):
    particle["age"] = float(particle.get("age", 0.0)) + dt
    if particle["age"] >= float(particle.get("lifetime", 0.0)):
        if particle.get("emit_blood_decal", False):
            runtime["events"].append({
                "type": "blood_decal",
                "x": float(particle.get("x", 0.0)),
                "y": float(particle.get("y", 0.0)),
                "size": float(particle.get("size", 2.0)) + 1.0,
            })
        return False

    particle["vz"] -= float(particle.get("gravity", 0.0)) * dt
    next_x = particle["x"] + particle.get("vx", 0.0) * dt
    next_y = particle["y"] + particle.get("vy", 0.0) * dt
    if _tile_is_solid(next_x, next_y, tile_map):
        particle["vx"] = 0.0
        particle["vy"] = 0.0
    else:
        particle["x"] = next_x
        particle["y"] = next_y
    particle["z"] = max(0.0, particle["z"] + particle.get("vz", 0.0) * dt)
    amount = min(1.0, particle["age"] / max(0.001, particle["lifetime"]))
    particle["size"] = particle["start_size"] + (particle["end_size"] - particle["start_size"]) * amount
    return True


def update_effects(runtime, emitters, wind_profile, time_elapsed, dt, tile_map=None,
                   update_authored=True, update_bursts=True, respect_preview_enabled=False):
    """Update CPU gameplay bursts; authored emitters have no live runtime state."""
    started = time.perf_counter()
    runtime["authored_visible"] = bool(update_authored)
    stats = reset_render_stats(runtime, emitters, update_authored)
    if respect_preview_enabled and update_authored:
        stats["active_emitter_count"] = sum(
            1 for emitter in (emitters or {}).values()
            if emitter.get("enabled", True) and emitter.get("preview_enabled", True)
        )

    if update_bursts:
        bursts = runtime.setdefault("bursts", {})
        for burst_id in list(bursts):
            particles = bursts[burst_id].get("particles", [])
            particles[:] = [particle for particle in particles if _update_blood_particle(particle, dt, tile_map, runtime)]
            if not particles:
                del bursts[burst_id]
    stats["burst_count"] = len(runtime.get("bursts", {}))
    stats["live_particle_count"] = sum(len(burst.get("particles", ())) for burst in runtime.get("bursts", {}).values())
    stats["update_time_ms"] = (time.perf_counter() - started) * 1000.0
    return stats


def _new_burst(runtime, effect_type, particles):
    runtime_id = int(runtime.get("next_runtime_id", 1))
    runtime["next_runtime_id"] = runtime_id + 1
    runtime.setdefault("bursts", {})[runtime_id] = {
        "particles": particles, "effect_type": effect_type, "finished": False,
    }
    return runtime_id


def spawn_blood_spatter(runtime, particle_amount, total_duration, bullet_velocity,
                        spawn_position, tile_map=None, start_color=None, end_color=None):
    origin = position_to_world(spawn_position, tile_map)
    vx = float((bullet_velocity or {}).get("x", 0.0))
    vy = float((bullet_velocity or {}).get("y", 0.0))
    magnitude = math.hypot(vx, vy)
    nx, ny = (1.0, 0.0) if magnitude <= 0.000001 else (vx / magnitude, vy / magnitude)
    state = {"random_state": (
        int(runtime.get("next_runtime_id", 1)) * 104729
        + int(origin["x"] * 17.0) + int(origin["y"] * 31.0)
    ) & 0xFFFFFFFF}
    start = _alpha_color(start_color or [0.42, 0.035, 0.035, 1.0])
    end = _alpha_color(end_color or [0.28, 0.015, 0.015, 0.0])
    particles = []
    for _ in range(max(0, int(particle_amount))):
        angle = math.atan2(ny, nx) + math.radians(_random_signed(state) * 10.0)
        speed = magnitude / max(1.0, 8.0 + _next_random(state) * 4.0)
        particle = _base_blood_particle(
            None,
            origin["x"] + _random_signed(state) * 7.0,
            origin["y"] + _random_signed(state) * 7.0,
            3.0 + _next_random(state) * 4.0,
            total_duration,
            1.0 + _next_random(state) * 2.0,
            start, end,
        )
        particle["vx"] = math.cos(angle) * speed
        particle["vy"] = math.sin(angle) * speed
        particle["vz"] = 4.0 + _next_random(state) * 10.0
        particle["gravity"] = 18.0
        particle["emit_blood_decal"] = True
        particles.append(particle)
    burst_id = _new_burst(runtime, "blood", particles)
    for particle in particles:
        particle["owner_id"] = burst_id
    return burst_id


def drain_effect_events(runtime):
    events = list(runtime.get("events", ()))
    runtime["events"] = []
    return events


def collect_gameplay_burst_particles(runtime, render_group=None, material=None):
    result = []
    for burst in runtime.get("bursts", {}).values():
        result.extend(burst.get("particles", ()))
    if render_group is not None:
        result = [particle for particle in result if particle.get("render_group") == render_group]
    if material is not None:
        result = [particle for particle in result if particle.get("material") == material]
    return result


def build_fire_runtime_lights(emitters, tile_map, time_elapsed):
    lights = {}
    for emitter_id, emitter in (emitters or {}).items():
        if emitter.get("type") != "fire" or not emitter.get("enabled", True):
            continue
        settings = emitter.get("light", {})
        if not settings.get("enabled", False):
            continue
        position = position_to_world(emitter.get("position", {}), tile_map)
        seed_phase = (int(emitter.get("seed", 1)) % 997) / 997.0 * math.tau
        flicker = math.sin(float(time_elapsed) * float(settings.get("flicker_speed", 7.0)) + seed_phase)
        intensity = float(settings.get("intensity", 0.8)) * (
            1.0 + flicker * float(settings.get("flicker_strength", 0.15))
        )
        light_id = f"effect:fire:{emitter_id}"
        lights[light_id] = {
            "type": "point", "position": position,
            "color": list(settings.get("color", [1.0, 0.45, 0.16])),
            "radius": float(settings.get("radius", 70.0)),
            "intensity": max(0.0, intensity), "falloff": 1.6,
            "enabled": True,
            "affects_scene": bool(settings.get("affects_world", True) or settings.get("affects_entities", True)),
            "affects_world": bool(settings.get("affects_world", True)),
            "affects_entities": bool(settings.get("affects_entities", True)),
            "affects_fog": bool(settings.get("affects_fog", True)),
            "affects_ai": bool(settings.get("affects_ai", False)),
            "casts_wall_shadows": bool(settings.get("casts_wall_shadows", True)),
            "casts_cinematic_shadows": False,
            "gameplay_intensity": intensity if settings.get("affects_ai", False) else 0.0,
            "mobility": "dynamic", "render_style": "world",
            "height": float(settings.get("height", 18.0)),
            "shadow_bias": 0.25, "effect_owner": emitter_id,
        }
    return lights


def replace_fire_runtime_lights(runtime_lights, fire_lights):
    if isinstance(runtime_lights, dict):
        target = runtime_lights
    else:
        target = {}
        for index, item in enumerate(runtime_lights or ()):
            if isinstance(item, dict) and "light" in item:
                target[str(item.get("id", f"runtime:legacy:{index}"))] = item
            else:
                target[f"runtime:legacy:{index}"] = item
    for light_id in [key for key in target if str(key).startswith("effect:fire:")]:
        del target[light_id]
    target.update(fire_lights)
    return target
