import math
import random
import time

import pyray as pr
from pyrsistent import m, pmap, v

import g_light_visibility as light_visibility
import g_effects
import g_render_order
import g_update_and_render as game

CINEMATIC_SHADOW_DEBUG_ENABLED = False

ENTITY_SELF_SHADOW_MODES = {"none": 0, "upright_box": 1, "directional_profiles": 2}
_REPORTED_DIRECTIONAL_PROFILE_ASSET_ERRORS = set()

def make_lighting_profile(profile_name="inky"):
    profiles = {
        "soft": {
            "name": "soft",
            "ambient_color": [0.28, 0.24, 0.38],
            "ambient_strength": 0.45,
            "direct_light_strength": 1.0,
            "shadow_color": [0.18, 0.15, 0.25],
            "black_point": 0.025,
            "shadow_softness": 0.22,
            "shadow_detail": 0.75,
            "contrast": 1.05,
            "light_posterize_enabled": True,
            "light_posterize_levels": 20.0,
            "light_dither_enabled": False,
            "light_dither_strength": 1.0,
            "posterize_ambient": False
        },
        "inky": {
            "name": "inky",
            "ambient_color": [0.18, 0.14, 0.26],
            "ambient_strength": 0.30,
            "direct_light_strength": 1.0,
            "shadow_color": [0.008, 0.005, 0.018],
            "black_point": 0.10,
            "shadow_softness": 0.025,
            "shadow_detail": 0.0,
            "contrast": 1.18,
            "light_posterize_enabled": True,
            "light_posterize_levels": 8.0,
            "light_dither_enabled": True,
            "light_dither_strength": 0.5,
            "posterize_ambient": False
        }
    }

    return dict(profiles.get(profile_name, profiles["soft"]))

def make_fog_profile(profile_name="misty"):
    profiles = {
        "misty": {
            "name": "misty",
            "enabled": True,
            "color": [0.62, 0.70, 0.86],
            "density": 0.65,
            "opacity": 0.75,
            "world_scale": 0.018,
            "detail_scale": 2.7,
            "drift": {"x": 5.0, "y": 1.2},
            "cutoff": 0.42,
            "softness": 0.20,
            "light_strength": 1.35,
            "ambient_strength": 0.0,
            "veil_strength": 0.10,
            "evolution_speed": 0.10,
            "warp_scale": 0.55,
            "warp_strength": 0.75,
            "detail_drift": {"x": -2.0, "y": 3.5},
            "detail_evolution_speed": 0.17,
            "global_amount": 0.0,
            "posterize_enabled": True,
            "posterize_levels": 20.0,
            "dither_enabled": False,
            "dither_strength": 0.2,
            "dither_mode": "bayer"
        }
    }

    dithered_profile = dict(profiles["misty"])
    dithered_profile["name"] = "misty_dithered"
    dithered_profile["dither_enabled"] = True
    dithered_profile["dither_strength"] = 0.75
    profiles["misty_dithered"] = dithered_profile

    selected = profiles.get(profile_name, profiles["misty"])
    result = dict(selected)
    result["color"] = list(selected["color"])
    result["drift"] = dict(selected["drift"])
    result["detail_drift"] = dict(selected["detail_drift"])
    return result

def get_or_create_render_target(game_assets, name, width, height):
    render_targets = game_assets.get("render_targets")

    if render_targets is None:
        render_targets = {}
        game_assets["render_targets"] = render_targets

    target = render_targets.get(name)

    if target is not None and (target.texture.width != width or target.texture.height != height):
        pr.unload_render_texture(target)
        target = None

    if target is None:
        target = pr.load_render_texture(width, height)
        render_targets[name] = target

    return target


def rain_exposure_texture_cache_key(tile_map):
    return (
        id(tile_map),
        max(0, int((tile_map or {}).get("map_width", 0))),
        max(0, int((tile_map or {}).get("map_height", 0))),
        int((tile_map or {}).get("rain_exposure_revision", 0)),
    )


def rain_exposure_texture_cache_action(cache_metadata, tile_map):
    """Pure cache decision used by the GPU path and unit tests."""
    source_identity, width, height, revision = rain_exposure_texture_cache_key(tile_map)
    if not isinstance(cache_metadata, dict) or cache_metadata.get("texture") is None:
        return "recreate"
    if cache_metadata.get("source_identity") != source_identity:
        return "recreate"
    if cache_metadata.get("width") != width or cache_metadata.get("height") != height:
        return "recreate"
    if cache_metadata.get("last_revision") != revision:
        return "update"
    return "reuse"


def _load_rgba8_texture(width, height, pixel_data):
    # Image retains the Python buffer for the duration of this immediate upload.
    buffer = bytearray(pixel_data)
    image = pr.Image(
        buffer, width, height, 1,
        int(pr.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8),
    )
    texture = pr.load_texture_from_image(image)
    pr.set_texture_filter(texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
    return texture


def ensure_rain_exposure_texture(game_assets, tile_map):
    """Create/update the one-texel-per-tile exposure texture on revision changes."""
    cache = game_assets.get("rain_exposure_texture_cache")
    action = rain_exposure_texture_cache_action(cache, tile_map)
    source_identity, width, height, revision = rain_exposure_texture_cache_key(tile_map)
    # Raylib cannot create a zero-sized texture; invalid maps have no rain asset.
    if width <= 0 or height <= 0:
        if isinstance(cache, dict) and cache.get("texture") is not None:
            pr.unload_texture(cache["texture"])
        game_assets.pop("rain_exposure_texture_cache", None)
        return None

    if action == "reuse":
        return cache["texture"]

    pixels = g_effects.build_rain_exposure_pixel_data(tile_map)
    exposed_count = g_effects.count_exposed_rain_tiles(tile_map)
    rebuild_count = int(cache.get("rebuild_count", 0)) if isinstance(cache, dict) else 0
    texture = cache.get("texture") if isinstance(cache, dict) else None
    if action == "update" and texture is not None:
        pixel_bytes = bytearray(pixels)
        pixel_buffer = pr.ffi.from_buffer("unsigned char[]", pixel_bytes)
        pr.update_texture(texture, pr.ffi.cast("void *", pixel_buffer))
    else:
        if texture is not None:
            pr.unload_texture(texture)
        texture = _load_rgba8_texture(width, height, pixels)
        rebuild_count += 1

    pr.set_texture_filter(texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
    game_assets["rain_exposure_texture_cache"] = {
        "texture": texture,
        "source_identity": source_identity,
        "width": width,
        "height": height,
        "last_revision": revision,
        "exposed_tile_count": exposed_count,
        "rebuild_count": rebuild_count,
    }
    return texture


def clear_rain_runtime_assets(game_assets):
    cache = game_assets.pop("rain_exposure_texture_cache", None)
    if isinstance(cache, dict) and cache.get("texture") is not None:
        pr.unload_texture(cache["texture"])
    render_targets = game_assets.get("render_targets", {})
    target = render_targets.pop("rain_composite", None)
    if target is not None:
        pr.unload_render_texture(target)
    game_assets.pop("rain_stats", None)

def set_shader_texture(shader, location, texture):
    if location < 0:
        return
    pr.set_shader_value_texture(shader, location, texture)

def set_shader_float(shader, location, value):
    if location < 0:
        return
    value_ptr = pr.ffi.new("float *", float(value))
    pr.set_shader_value(shader, location, value_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT)

def set_shader_int(shader, location, value):
    if location < 0:
        return
    value_ptr = pr.ffi.new("int *", int(value))
    pr.set_shader_value(shader, location, value_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_INT)

def set_shader_vec2(shader, location, x, y):
    if location < 0:
        return
    value_ptr = pr.ffi.new("float[2]", [float(x), float(y)])
    pr.set_shader_value(shader, location, value_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_VEC2)

def set_shader_vec3(shader, location, x, y, z):
    if location < 0:
        return
    value_ptr = pr.ffi.new("float[3]", [float(x), float(y), float(z)])
    pr.set_shader_value(shader, location, value_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_VEC3)

def set_shader_vec4(shader, location, x, y, z, w):
    if location < 0:
        return
    value_ptr = pr.ffi.new("float[4]", [float(x), float(y), float(z), float(w)])
    pr.set_shader_value(shader, location, value_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_VEC4)

_EFFECT_SHADER_UNIFORMS = {
    "effect_fire": (
        "resolution", "boundsMin", "boundsSize", "anchorInBounds", "effectSize",
        "wind", "time", "seed", "density", "speed", "turbulence",
        "windResponse", "opacity", "posterizeLevels", "emberDensity",
        "emberHeight", "passMode", "colorCore", "colorHot", "colorMid",
        "colorOuter",
    ),
    "effect_smoke": (
        "resolution", "boundsMin", "boundsSize", "anchorInBounds", "effectSize",
        "wind", "time", "seed", "density", "speed", "turbulence",
        "detailScale", "warpStrength", "evolutionSpeed", "windResponse", "opacity",
        "posterizeLevels", "smokeColor",
    ),
}

_RAIN_SHADER_UNIFORMS = (
    "lightTexture", "rainExposureTexture", "resolution", "cameraPosition",
    "tileSize", "mapSize", "time", "seed", "density", "speed",
    "direction", "cellSize", "streakLength", "unlitOpacity", "litOpacity",
    "lightThreshold", "lightResponse", "lightColorInfluence",
    "ambientRainColor", "opacityLevels", "distortionEnabled",
    "distortionStrength", "distortionDensity", "debugMode", "showExposureOverlay",
    "disableStreakColor", "disableDistortion",
)

def load_effect_shaders(shader_registry):
    """Load procedural environment shaders and cache all uniform locations."""
    for shader_name, uniforms in _EFFECT_SHADER_UNIFORMS.items():
        shader = pr.load_shader("", f"shaders/{shader_name}.fs")
        info = {"shader": shader}
        for uniform in uniforms:
            info[f"{uniform}_location"] = pr.get_shader_location(shader, uniform)
        shader_registry[shader_name] = info
    rain_shader = pr.load_shader("", "shaders/rain_composite.fs")
    rain_info = {"shader": rain_shader}
    for uniform in _RAIN_SHADER_UNIFORMS:
        rain_info[f"{uniform}_location"] = pr.get_shader_location(rain_shader, uniform)
    shader_registry["rain_composite"] = rain_info
    return shader_registry

def normalize_light_color(color):
    red = float(color[0])
    green = float(color[1])
    blue = float(color[2])

    if max(red, green, blue) > 1.0:
        red /= 255.0
        green /= 255.0
        blue /= 255.0

    return red, green, blue

def get_light_world_position(light, tile_map):
    position = light.get("position", {})

    if "tile_x" in position and "tile_y" in position:
        return game.make_pos_abs(position, tile_map["tile_width"], tile_map["tile_height"])

    return {"x": position.get("x", 0.0), "y": position.get("y", 0.0)}

def draw_fog_volume_to_mask(volume, game_camera, tile_map, mask_target, volume_shader):
    if not volume.get("enabled", True):
        return

    world_position = get_light_world_position(volume, tile_map)
    size = volume.get("size", {})
    width = max(0.0, float(size.get("x", 0.0)))
    height = max(0.0, float(size.get("y", 0.0)))
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y
    area_min_x = screen_x - width * 0.5
    area_min_y = screen_y - height * 0.5
    area_max_x = screen_x + width * 0.5
    area_max_y = screen_y + height * 0.5
    target_width = mask_target.texture.width
    target_height = mask_target.texture.height

    if area_max_x < 0 or area_max_y < 0 or area_min_x >= target_width or area_min_y >= target_height:
        return

    shape_type = 1 if volume.get("shape", "ellipse") == "ellipse" else 0
    edge_softness = max(0.0, float(volume.get("edge_softness", 24.0)))
    strength = max(0.0, float(volume.get("strength", 1.0)))
    shader = volume_shader["shader"]

    set_shader_vec2(shader, volume_shader["resolution_location"], target_width, target_height)
    set_shader_vec2(shader, volume_shader["area_min_location"], area_min_x, area_min_y)
    set_shader_vec2(shader, volume_shader["area_max_location"], area_max_x, area_max_y)
    set_shader_int(shader, volume_shader["shape_type_location"], shape_type)
    set_shader_float(shader, volume_shader["edge_softness_location"], edge_softness)
    set_shader_float(shader, volume_shader["strength_location"], strength)

    draw_x = max(0, math.floor(area_min_x))
    draw_y = max(0, math.floor(area_min_y))
    draw_max_x = min(target_width, math.ceil(area_max_x))
    draw_max_y = min(target_height, math.ceil(area_max_y))

    if draw_max_x <= draw_x or draw_max_y <= draw_y:
        return

    pr.begin_shader_mode(shader)
    pr.draw_rectangle(draw_x, draw_y, draw_max_x - draw_x, draw_max_y - draw_y, pr.WHITE)
    pr.end_shader_mode()

def render_fog_volume_mask(game_camera, entities, tile_map, scene_target, game_assets):
    width = scene_target.texture.width
    height = scene_target.texture.height
    mask_target = get_or_create_render_target(game_assets, "fog_volume_mask", width, height)
    volume_shader = game_assets["shaders"]["fog_volume_mask"]
    fog_volumes = entities.setdefault("fog_volumes", {})

    pr.begin_texture_mode(mask_target)
    pr.clear_background(pr.BLACK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)

    for volume in fog_volumes.values():
        draw_fog_volume_to_mask(volume, game_camera, tile_map, mask_target, volume_shader)

    pr.end_blend_mode()
    pr.end_texture_mode()
    return mask_target

def make_player_pointlight(player_entity, tile_map):
    player_world_position = game.make_pos_abs(player_entity.get("position", {}), tile_map["tile_width"], tile_map["tile_height"])
    result = {
        "type": "point",
            "position": player_world_position,
            #"color": [0.86, 0.74, 1.0],
            "color": [1.0, 1.0, 1.0],
            "radius": 25.0,
            "intensity": 0.5,
            "falloff": 1.0,
            "casts_shadows": False,
            "casts_wall_shadows": False,
            "casts_cinematic_shadows": False,
            "affects_scene": True,
            "affects_world": False,
            "affects_entities": True,
            "affects_fog": False,
            "affects_ai": False,
            "gameplay_intensity": 0.0,
            "mobility": "dynamic",
            "render_style": "readability",
            "owner_id": "player",
            "height": 18.0,
            "entity_lighting_mode": "omni",
            "shadow_bias": 0.25,
            "enabled": True
    }
    return result

def make_player_flashlight(player_entity, tile_map):
    direction = game.vec2_normalize(player_entity.get("aim_direction", {"x": 1.0, "y": 0.0}))

    if game.vec2_norm(direction) == 0:
        direction = {"x": 1.0, "y": 0.0}

    settings = get_player_flashlight_settings(player_entity)
    player_world_position = game.make_pos_abs(player_entity.get("position", {}), tile_map["tile_width"], tile_map["tile_height"])

    side_direction = {"x": -direction["y"], "y": direction["x"]}    
    forward_offset = game.vec2_scale(direction, settings["forward_offset"])
    side_offset = game.vec2_scale(side_direction, settings["side_offset"])
    flashlight_position = game.vec2_add(player_world_position, game.vec2_add(forward_offset, side_offset))

    

    return {
        "type": "spot",
        "position": flashlight_position,
        # The cone starts slightly in front of the player, but rotating that
        # offset around a nearby entity must not change which authored side
        # profile the light represents.  Entity-profile direction therefore
        # uses this stable world-space origin while cone coverage, wall rays and
        # attenuation continue using position above.
        "entity_direction_origin": dict(player_world_position),
        "direction": direction,
        "color": [1.0, 0.82, 0.62],
        "radius": 180.0,
        "visibility_radius": 340.0,
        "intensity": 1.2,
        "falloff": 1.4,
        "casts_shadows": True,
        "casts_wall_shadows": True,
        "casts_cinematic_shadows": True,
        "affects_scene": True,
        "affects_world": True,
        "affects_entities": True,
        "affects_fog": True,
        "affects_ai": True,
        "gameplay_intensity": 1.0,
        "mobility": "dynamic",
        "render_style": "world",
        "owner_id": "player",
        "height": 22.0,
        "shadow_bias": 0.25,
        "near_fade_distance": 14.0,
        "inner_angle": 13.0,
        "outer_angle": 27.0,
        "enabled": player_entity.get("flashlight_enabled", True)
    }

def ensure_light_collision_grid(game_assets, tile_map):
    tile_map.setdefault("geometry_revision", 0)
    cached_grid = game_assets.get("light_collision_grid")
    expected = (
        id(tile_map),
        int(tile_map["geometry_revision"]),
        int(tile_map["map_width"]),
        int(tile_map["map_height"]),
        int(tile_map["tile_width"]),
        int(tile_map["tile_height"]),
        light_visibility.LIGHT_GEOMETRY_CACHE_VERSION,
        light_visibility.LIGHT_GEOMETRY_RUNTIME_GENERATION
    )
    actual = None

    if cached_grid is not None:
        actual = (
            cached_grid.get("source_map_identity"),
            cached_grid.get("geometry_revision"),
            cached_grid.get("map_width"),
            cached_grid.get("map_height"),
            cached_grid.get("tile_width"),
            cached_grid.get("tile_height"),
            cached_grid.get("cache_version"),
            cached_grid.get("runtime_generation")
        )

    if actual != expected:
        # Per-placed-tile force_collidable overrides are gameplay/pathfinding
        # volumes, not new wall geometry; keep them out of the global light DDA.
        collidable_tile_indices = {
            index for index, tile_type in enumerate(tile_map["tile_types"])
            if game.tile_type_is_collidable(tile_type.get("type", ""))
        }
        cached_grid = light_visibility.build_light_collision_grid(tile_map, collidable_tile_indices)
        game_assets["light_collision_grid"] = cached_grid
        game_assets["light_visibility_cache"] = {}

    return cached_grid

def apply_light_capability_defaults(light):
    result = dict(light)
    legacy_scene = bool(result.get("affects_scene", True))
    result.setdefault("enabled", True)
    result.setdefault("affects_scene", legacy_scene)
    result.setdefault("affects_world", legacy_scene)
    result.setdefault("affects_entities", legacy_scene)
    result.setdefault("affects_fog", True)
    result.setdefault("affects_ai", True)
    result.setdefault("casts_wall_shadows", result.get("casts_shadows", True))
    result.setdefault("casts_cinematic_shadows", False)
    result.setdefault("gameplay_intensity", 1.0)
    result.setdefault("mobility", "static")
    result.setdefault("render_style", "world")
    result.setdefault("height", 180.0 if result.get("type") == "top_down" else 32.0)
    return result

def collect_light_records(entities, player_entity, tile_map, game_assets):
    records = []

    for light_id, light in entities.setdefault("lights", {}).items():
        records.append({"id": str(light_id), "light": apply_light_capability_defaults(light)})

    runtime_lights = game_assets.get("runtime_lights", {})

    if isinstance(runtime_lights, dict):
        runtime_items = []

        for light_id, item in runtime_lights.items():
            if isinstance(item, dict) and "light" in item:
                runtime_items.append((item.get("id", light_id), item["light"]))
            else:
                runtime_items.append((light_id, item))
    else:
        runtime_items = []

        for index, item in enumerate(runtime_lights):
            if isinstance(item, dict) and "light" in item:
                runtime_items.append((item.get("id", f"runtime:{index}"), item["light"]))
            else:
                runtime_items.append((f"runtime:{index}", item))

    for light_id, light in runtime_items:
        if isinstance(light, dict):
            records.append({"id": str(light_id), "light": apply_light_capability_defaults(light)})

    records.append({"id": "runtime:player_flashlight", "light": apply_light_capability_defaults(make_player_flashlight(player_entity, tile_map))})
    records.append({"id": "runtime:player_readability", "light": apply_light_capability_defaults(make_player_pointlight(player_entity, tile_map))})
    return records

def radial_light_intersects_viewport(world_position, radius, game_camera, scene_target):
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y
    width = scene_target.texture.width
    height = scene_target.texture.height
    return not (screen_x + radius < 0 or screen_y + radius < 0 or screen_x - radius >= width or screen_y - radius >= height)

def top_down_light_intersects_viewport(light, world_position, game_camera, scene_target):
    size = light.get("size", {})
    half_width = max(0.0, float(size.get("x", 0.0))) * 0.5
    half_height = max(0.0, float(size.get("y", 0.0))) * 0.5
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y
    return not (screen_x + half_width < 0 or screen_y + half_height < 0 or screen_x - half_width >= scene_target.texture.width or screen_y - half_height >= scene_target.texture.height)

def prepare_lighting_frame(game_camera, entities, player_entity, tile_map, scene_target, game_assets):
    prepare_started = time.perf_counter()
    collision_grid = ensure_light_collision_grid(game_assets, tile_map)
    cache = game_assets.setdefault("light_visibility_cache", {})
    frame_number = int(game_assets.get("lighting_frame_counter", 0)) + 1
    game_assets["lighting_frame_counter"] = frame_number
    records = collect_light_records(entities, player_entity, tile_map, game_assets)
    prepared_lights = []
    prepared_by_id = {}
    stats = {
        "active_light_count": 0,
        "shadowed_radial_light_count": 0,
        "unshadowed_radial_light_count": 0,
        "top_down_light_count": 0,
        "visibility_cache_hits": 0,
        "visibility_cache_misses": 0,
        "visibility_rebuilds": 0,
        "total_visibility_rays": 0,
        "total_dda_tile_steps": 0,
        "max_dda_tile_steps_for_one_ray": 0,
        "boundary_vertex_candidates": 0,
        "adaptive_rays_added": 0,
        "prepare_time_ms": 0.0,
        "scene_draw_time_ms": 0.0,
        "fog_draw_time_ms": 0.0
    }

    for record in records:
        light = record["light"]

        if not light.get("enabled", True):
            continue

        light_type = light.get("type", "point")
        world_position = light_visibility.get_light_world_position(light, collision_grid)
        radius = max(0.0, float(light.get("visibility_radius", light.get("radius", 100.0))))

        if light_type == "top_down":
            if not top_down_light_intersects_viewport(light, world_position, game_camera, scene_target):
                continue
        elif not radial_light_intersects_viewport(world_position, radius, game_camera, scene_target):
            continue

        prepared = {
            "id": record["id"],
            "light": light,
            "world_position": world_position,
            "screen_bounds": {
                "min_x": world_position["x"] - game_camera.x - radius,
                "min_y": world_position["y"] - game_camera.y - radius,
                "max_x": world_position["x"] - game_camera.x + radius,
                "max_y": world_position["y"] - game_camera.y + radius
            },
            "visibility_polygon": None,
            "cinematic_visibility_polygon": None,
            "hit_tile_ids": set(),
            "receiver_tile_ids": [],
            "receiver_polygons": [],
            "affects_scene": light["affects_scene"],
            "affects_world": light["affects_world"],
            "affects_entities": light["affects_entities"],
            "affects_fog": light["affects_fog"],
            "affects_ai": light["affects_ai"],
            "casts_wall_shadows": light["casts_wall_shadows"],
            "casts_cinematic_shadows": light["casts_cinematic_shadows"],
            "geometry_cache_hit": False
        }
        stats["active_light_count"] += 1

        if light_type == "top_down":
            stats["top_down_light_count"] += 1
        elif light["casts_wall_shadows"]:
            stats["shadowed_radial_light_count"] += 1
            geometry_key = light_visibility.make_light_geometry_key(record, world_position, collision_grid)
            cache_entry = cache.get(record["id"])

            if cache_entry is not None and cache_entry.get("geometry_key") == geometry_key:
                geometry = cache_entry["geometry"]
                cache_entry["last_used_frame"] = frame_number
                prepared["geometry_cache_hit"] = True
                stats["visibility_cache_hits"] += 1
            else:
                geometry = light_visibility.build_light_visibility_polygon_dda(light, world_position, collision_grid)
                cache[record["id"]] = {"geometry_key": geometry_key, "geometry": geometry, "last_used_frame": frame_number}
                stats["visibility_cache_misses"] += 1
                stats["visibility_rebuilds"] += 1
                stats["total_visibility_rays"] += geometry["ray_count"]
                stats["total_dda_tile_steps"] += geometry["dda_tile_steps"]
                stats["max_dda_tile_steps_for_one_ray"] = max(stats["max_dda_tile_steps_for_one_ray"], geometry["max_dda_tile_steps_for_one_ray"])
                stats["boundary_vertex_candidates"] += geometry["corner_candidate_count"]
                stats["adaptive_rays_added"] += geometry["adaptive_rays_added"]

            prepared["visibility_polygon"] = geometry["polygon"]
            prepared["cinematic_visibility_polygon"] = geometry["unbiased_polygon"]
            prepared["hit_tile_ids"] = geometry["hit_tile_ids"]
            prepared["ray_count"] = geometry["ray_count"]
            prepared["dda_tile_steps"] = geometry["dda_tile_steps"]
            prepared["corner_candidate_count"] = geometry["corner_candidate_count"]
            prepared["adaptive_rays_added"] = geometry["adaptive_rays_added"]
            if light["affects_world"]:
                receiver_ids, receiver_polygons = light_visibility.query_receiver_polygons(world_position, radius, collision_grid, light)
                prepared["receiver_tile_ids"] = receiver_ids
                prepared["receiver_polygons"] = receiver_polygons
        else:
            stats["unshadowed_radial_light_count"] += 1

        prepared_lights.append(prepared)
        prepared_by_id[record["id"]] = prepared

    stats["pruned_cache_entries"] = light_visibility.prune_light_visibility_cache(cache, frame_number, int(game_assets.get("light_visibility_cache_max_unused_frames", 600)))
    stats["prepare_time_ms"] = (time.perf_counter() - prepare_started) * 1000.0
    lighting_frame = {"collision_grid": collision_grid, "prepared_lights": prepared_lights, "prepared_by_id": prepared_by_id, "stats": stats}
    game_assets["lighting_frame_stats"] = stats
    return lighting_frame

def point_is_on_segment(point, segment_start, segment_end, epsilon=0.0001):
    segment_x = segment_end["x"] - segment_start["x"]
    segment_y = segment_end["y"] - segment_start["y"]
    point_x = point["x"] - segment_start["x"]
    point_y = point["y"] - segment_start["y"]
    cross = segment_x * point_y - segment_y * point_x

    if abs(cross) > epsilon:
        return False

    dot = point_x * segment_x + point_y * segment_y
    segment_length_squared = segment_x * segment_x + segment_y * segment_y
    return dot >= -epsilon and dot <= segment_length_squared + epsilon

def point_in_polygon(point, polygon):
    if len(polygon) < 3:
        return False

    inside = False

    for index, vertex in enumerate(polygon):
        next_vertex = polygon[(index + 1) % len(polygon)]

        if point_is_on_segment(point, vertex, next_vertex):
            return True

        crosses_y = (vertex["y"] > point["y"]) != (next_vertex["y"] > point["y"])

        if not crosses_y:
            continue

        edge_x = vertex["x"] + (point["y"] - vertex["y"]) * (next_vertex["x"] - vertex["x"]) / (next_vertex["y"] - vertex["y"])

        if point["x"] < edge_x:
            inside = not inside

    return inside

def smoothstep_cpu(edge_start, edge_end, value):
    if edge_end <= edge_start:
        return 1.0 if value >= edge_end else 0.0

    amount = max(0.0, min(1.0, (value - edge_start) / (edge_end - edge_start)))
    return amount * amount * (3.0 - 2.0 * amount)

def prepared_light_reaches_point(prepared_light, point):
    light = prepared_light.get("light", {})

    if light.get("type", "point") == "top_down" or not prepared_light.get("casts_wall_shadows", False):
        return True

    polygon = prepared_light.get("visibility_polygon") or []

    if light.get("type", "point") == "spot":
        polygon = [prepared_light["world_position"]] + polygon

    return point_in_polygon(point, polygon)


def get_prepared_gameplay_light_strength_at_world_point(
        prepared_light, world_point, collision_grid):
    """Measure authored AI light using already-prepared wall visibility.

    This mirrors the pure gameplay-light query without launching another DDA
    ray for every AI receiver. The lighting frame's visibility polygon has
    already paid for, and cached, the wall-occlusion work.
    """
    if not isinstance(prepared_light, dict):
        return 0.0
    light = prepared_light.get("light", {})
    if (not light.get("enabled", True)
            or not prepared_light.get(
                "affects_ai", light.get("affects_ai", True))):
        return 0.0
    strength = light_visibility.get_unoccluded_light_strength_at_world_point(
        light, world_point, collision_grid,
    )
    if strength <= 0.0 or not prepared_light_reaches_point(
            prepared_light, world_point):
        return 0.0
    return strength * max(
        0.0, float(light.get("gameplay_intensity", 1.0)),
    )

def get_light_height(light):
    if "height" in light:
        return max(0.0, float(light["height"]))
    if light.get("type", "point") == "top_down":
        return 180.0
    if light.get("owner_id") == "player":
        return 22.0 if light.get("type") == "spot" else 18.0
    return 32.0

def segment_rectangle_intersection_fraction(start, end, center, size):
    half_width = max(0.0, float(size.get("x", 0.0))) * 0.5
    half_height = max(0.0, float(size.get("y", 0.0))) * 0.5

    if half_width <= 0.000001 or half_height <= 0.000001:
        return None

    minimum = {"x": center["x"] - half_width, "y": center["y"] - half_height}
    maximum = {"x": center["x"] + half_width, "y": center["y"] + half_height}
    direction = {"x": end["x"] - start["x"], "y": end["y"] - start["y"]}
    entry = 0.0
    exit_fraction = 1.0

    for axis in ("x", "y"):
        if abs(direction[axis]) <= 0.000001:
            if start[axis] < minimum[axis] or start[axis] > maximum[axis]:
                return None
            continue

        first = (minimum[axis] - start[axis]) / direction[axis]
        second = (maximum[axis] - start[axis]) / direction[axis]
        entry = max(entry, min(first, second))
        exit_fraction = min(exit_fraction, max(first, second))

        if entry > exit_fraction:
            return None

    return entry if 0.0 <= entry <= 1.0 else None

def segment_ellipse_intersection_fraction(start, end, center, size):
    radius_x = max(0.0, float(size.get("x", 0.0))) * 0.5
    radius_y = max(0.0, float(size.get("y", 0.0))) * 0.5

    if radius_x <= 0.000001 or radius_y <= 0.000001:
        return None

    start_x = (start["x"] - center["x"]) / radius_x
    start_y = (start["y"] - center["y"]) / radius_y
    direction_x = (end["x"] - start["x"]) / radius_x
    direction_y = (end["y"] - start["y"]) / radius_y

    if start_x * start_x + start_y * start_y <= 1.0:
        return 0.0

    a = direction_x * direction_x + direction_y * direction_y
    b = 2.0 * (start_x * direction_x + start_y * direction_y)
    c = start_x * start_x + start_y * start_y - 1.0

    if a <= 0.000001:
        return None

    discriminant = b * b - 4.0 * a * c

    if discriminant < 0.0:
        return None

    root = math.sqrt(discriminant)
    intersections = [fraction for fraction in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)) if 0.0 <= fraction <= 1.0]
    return min(intersections) if intersections else None

def segment_footprint_intersection_fraction(start, end, footprint):
    if footprint.get("shape", "rectangle") == "ellipse":
        return segment_ellipse_intersection_fraction(start, end, footprint["center"], footprint["size"])
    return segment_rectangle_intersection_fraction(start, end, footprint["center"], footprint["size"])

def query_entity_light_occlusion(prepared_light, target_item, major_occluders):
    light = prepared_light.get("light", {})
    light_position = prepared_light["world_position"]
    target_position = target_item["base_world"]
    light_height = get_light_height(light)
    target_height = max(0.0, float(target_item.get("light_sample_height", 0.0)))
    owner_id = str(light.get("owner_id", ""))
    tests = []

    for occluder in major_occluders:
        source_id = str(occluder.get("source_id", occluder.get("id", "")))

        if occluder is target_item or source_id == str(target_item.get("source_id", target_item.get("id", ""))) or source_id == owner_id:
            continue

        footprint_data = occluder.get("ground_footprint_world")

        if footprint_data is None:
            footprint = occluder.get("ground_footprint", {})
            offset = footprint.get("offset", {})
            base = occluder.get("base_world", {})
            footprint_data = {"shape": footprint.get("shape", "rectangle"), "center": {"x": float(base.get("x", 0.0)) + float(offset.get("x", 0.0)), "y": float(base.get("y", 0.0)) + float(offset.get("y", 0.0))}, "size": footprint.get("size", {})}

        fraction = segment_footprint_intersection_fraction(light_position, target_position, footprint_data)

        if fraction is None:
            continue

        ray_height = light_height + (target_height - light_height) * fraction
        policy = occluder.get("entity_light_occluder", {})
        occluder_height = max(0.0, float(policy.get("height", occluder.get("visual_height", 0.0))))
        test = {"occluder": occluder, "intersection_fraction": fraction, "ray_height": ray_height, "occluder_height": occluder_height, "blocked": occluder_height + 0.000001 >= ray_height}
        tests.append(test)

        if test["blocked"]:
            return test, tests

    return None, tests

def find_blocking_entity_light_occluder(prepared_light, target_item, major_occluders):
    blocking, ignore = query_entity_light_occlusion(prepared_light, target_item, major_occluders)
    return blocking

def get_render_item_light_sample_points(render_item):
    base = render_item.get("base_world", {})
    bounds = render_item.get("bounds_world", {})
    left = float(bounds.get("x", base.get("x", 0.0)))
    top = float(bounds.get("y", base.get("y", 0.0)))
    width = float(bounds.get("width", 0.0))
    height = float(bounds.get("height", 0.0))
    center_x = left + width * 0.5
    points = [
        {"x": float(base.get("x", center_x)), "y": float(base.get("y", top + height))},
        {"x": center_x, "y": top + height * 0.50},
        {"x": left + width * 0.20, "y": top + height * 0.50},
        {"x": left + width * 0.80, "y": top + height * 0.50}
    ]
    points.extend(sample["world"] for sample in get_render_item_direction_basis_ray_samples(render_item))
    return points

def _segments_intersect(start_a, end_a, start_b, end_b, epsilon=0.000001):
    direction_a = {"x": end_a["x"] - start_a["x"], "y": end_a["y"] - start_a["y"]}
    direction_b = {"x": end_b["x"] - start_b["x"], "y": end_b["y"] - start_b["y"]}
    denominator = direction_a["x"] * direction_b["y"] - direction_a["y"] * direction_b["x"]
    offset = {"x": start_b["x"] - start_a["x"], "y": start_b["y"] - start_a["y"]}
    if abs(denominator) <= epsilon:
        return False
    fraction_a = (offset["x"] * direction_b["y"] - offset["y"] * direction_b["x"]) / denominator
    fraction_b = (offset["x"] * direction_a["y"] - offset["y"] * direction_a["x"]) / denominator
    return -epsilon <= fraction_a <= 1.0 + epsilon and -epsilon <= fraction_b <= 1.0 + epsilon

def polygon_intersects_rectangle(polygon, rectangle):
    """Conservative 2D overlap used to avoid sparse entity-light eligibility gaps."""
    if not polygon or rectangle.get("width", 0.0) <= 0.0 or rectangle.get("height", 0.0) <= 0.0:
        return False
    left = float(rectangle["x"])
    top = float(rectangle["y"])
    right = left + float(rectangle["width"])
    bottom = top + float(rectangle["height"])
    corners = [
        {"x": left, "y": top}, {"x": right, "y": top},
        {"x": right, "y": bottom}, {"x": left, "y": bottom}
    ]
    if any(point_is_inside_rectangle(point, rectangle) for point in polygon):
        return True
    if any(point_in_polygon(corner, polygon) for corner in corners):
        return True
    rectangle_edges = [(corners[index], corners[(index + 1) % 4]) for index in range(4)]
    polygon_edges = [(polygon[index], polygon[(index + 1) % len(polygon)]) for index in range(len(polygon))]
    return any(_segments_intersect(poly_start, poly_end, rect_start, rect_end) for poly_start, poly_end in polygon_edges for rect_start, rect_end in rectangle_edges)

def make_spot_light_coverage_polygon(prepared_light, arc_segments=12):
    light = prepared_light.get("light", {})
    origin = prepared_light.get("world_position", {})
    if "x" not in origin or "y" not in origin:
        return []
    direction = light_visibility.normalize_vector(light.get("direction", {"x": 1.0, "y": 0.0})) or {"x": 1.0, "y": 0.0}
    radius = max(0.0, float(light.get("radius", 0.0)))
    outer_angle = math.radians(max(0.0, float(light.get("outer_angle", 35.0))))
    centre_angle = math.atan2(direction["y"], direction["x"])
    segment_count = max(2, int(arc_segments))
    polygon = [dict(origin)]
    for index in range(segment_count + 1):
        angle = centre_angle - outer_angle + outer_angle * 2.0 * index / segment_count
        polygon.append({"x": origin["x"] + math.cos(angle) * radius, "y": origin["y"] + math.sin(angle) * radius})
    return polygon

def spot_light_conservatively_intersects_render_item(prepared_light, render_item):
    bounds = render_item.get("bounds_world", {})
    if not polygon_intersects_rectangle(make_spot_light_coverage_polygon(prepared_light), bounds):
        return False
    if prepared_light.get("casts_wall_shadows", False):
        visibility = prepared_light.get("visibility_polygon") or []
        if visibility:
            wall_visible_area = [dict(prepared_light["world_position"])] + list(visibility)
            if not polygon_intersects_rectangle(wall_visible_area, bounds):
                return False
    return True

def get_prepared_light_strength_for_render_item(prepared_light, render_item, collision_grid):
    light = prepared_light.get("light", {})
    strengths = []

    for point in get_render_item_light_sample_points(render_item):
        strength = light_visibility.get_unoccluded_light_strength_at_world_point(light, point, collision_grid)
        strengths.append(strength if strength > 0.0 and prepared_light_reaches_point(prepared_light, point) else 0.0)

    strongest_sample = max(strengths, default=0.0)
    if strongest_sample <= 0.000001 and light.get("type", "point") == "spot" and spot_light_conservatively_intersects_render_item(prepared_light, render_item):
        # The GPU's per-pixel light texture remains authoritative. This tiny
        # sentinel only keeps the light's entity pass alive when a narrow cone
        # overlaps visible sprite pixels between the finite CPU samples.
        return 0.00001
    return strongest_sample

def make_empty_entity_self_shadow_summary():
    return {"face_exposure": [1.0, 0.0, 0.0, 0.0], "omni_exposure": 0.0, "world_occlusion_scale": 1.0, "blocked_direct_count": 0, "sampled_world_strength": 0.0, "visible_world_strength": 0.0, "per_light": []}

def calculate_entity_self_shadow_at_u(summary, policy, local_u):
    if policy.get("mode", "none") != "upright_box":
        return 1.0

    exposure = list(summary.get("face_exposure", [1.0, 0.0, 0.0, 0.0]))

    while len(exposure) < 4:
        exposure.append(0.0)

    softness = max(0.001, min(0.49, float(policy.get("softness", 0.10))))
    right_mask = smoothstep_cpu(0.5 - softness, 0.5 + softness, max(0.0, min(1.0, float(local_u))))
    shaped = float(summary.get("omni_exposure", 0.0)) + exposure[0] + exposure[1] * max(0.0, min(1.0, float(policy.get("back_fill", 0.06)))) + exposure[2] * (1.0 - right_mask) + exposure[3] * right_mask
    strength = max(0.0, min(1.0, float(policy.get("strength", 0.0))))
    return (1.0 - strength) + strength * max(0.0, min(1.0, shaped))

def calculate_directional_profile_attenuation(summary, policy, response_rgba, profile_divider_visibility=1.0):
    """Blend an authored RGBA survival sample in down/up/left/right order.

    The result attenuates one ordinary direct-light contribution. Callers add
    surviving per-light contributions; ambient and readability remain separate.
    """
    exposure = list(summary.get("face_exposure", [0.0, 0.0, 0.0, 0.0]))
    response = list(response_rgba)

    while len(exposure) < 4:
        exposure.append(0.0)
    while len(response) < 4:
        response.append(0.0)

    response = [max(0.0, min(1.0, float(value))) for value in response]
    divider_visibility = max(0.0, min(1.0, float(profile_divider_visibility)))
    authored_exposure = (
        response[0] * float(exposure[0]) +
        response[1] * float(exposure[1]) * divider_visibility +
        response[2] * float(exposure[2]) +
        response[3] * float(exposure[3])
    )
    minimum_direct = max(0.0, min(1.0, float(policy.get("minimum_direct", 0.0))))
    shaped_exposure = max(minimum_direct, min(1.0, float(summary.get("omni_exposure", 0.0)) + authored_exposure))
    strength = max(0.0, min(1.0, float(policy.get("strength", 0.0))))
    return (1.0 - strength) + strength * shaped_exposure

def calculate_profile_divider_visibility(local_uv, light_origin_local, divider_top, divider_bottom):
    """CPU reference for the shader's sprite-local centre-divider occlusion."""
    ray_start = {"x": float(light_origin_local["x"]), "y": float(light_origin_local["y"])}
    ray_end = {"x": float(local_uv["x"]), "y": float(local_uv["y"])}
    top = {"x": float(divider_top["x"]), "y": float(divider_top["y"])}
    bottom = {"x": float(divider_bottom["x"]), "y": float(divider_bottom["y"])}
    return 0.0 if _segments_intersect(ray_start, ray_end, top, bottom) else 1.0

def get_render_item_direction_basis_world_rect(render_item):
    """Transform a current-frame sprite-local direction rectangle into world space."""
    basis = render_item.get("self_shadow", {}).get("direction_basis", {})
    if basis.get("mode") != "sprite_rect":
        return None
    local = basis.get("rect", {})
    source = render_item.get("source_rect", {})
    destination = render_item.get("dest_rect", {})
    source_width = abs(float(source.get("width", 0.0)))
    source_height = abs(float(source.get("height", 0.0)))
    if source_width <= 0.000001 or source_height <= 0.000001:
        return None
    scale_x = float(destination.get("width", 0.0)) / source_width
    scale_y = float(destination.get("height", 0.0)) / source_height
    return {
        "x": float(destination.get("x", 0.0)) + float(local.get("x", 0.0)) * scale_x,
        "y": float(destination.get("y", 0.0)) + float(local.get("y", 0.0)) * scale_y,
        "width": max(0.0, float(local.get("width", 0.0)) * scale_x),
        "height": max(0.0, float(local.get("height", 0.0)) * scale_y)
    }

def get_render_item_profile_divider_world_line(render_item):
    divider = render_item.get("self_shadow", {}).get("profile_divider", {})
    if not divider.get("enabled", False):
        return None
    source = render_item.get("source_rect", {})
    destination = render_item.get("dest_rect", {})
    source_width = abs(float(source.get("width", 0.0)))
    source_height = abs(float(source.get("height", 0.0)))
    if source_width <= 0.000001 or source_height <= 0.000001:
        return None
    scale_x = float(destination.get("width", 0.0)) / source_width
    scale_y = float(destination.get("height", 0.0)) / source_height
    top = divider.get("top", {})
    bottom = divider.get("bottom", {})
    return {
        "top": {
            "x": float(destination.get("x", 0.0)) + float(top.get("x", 0.0)) * scale_x,
            "y": float(destination.get("y", 0.0)) + float(top.get("y", 0.0)) * scale_y
        },
        "bottom": {
            "x": float(destination.get("x", 0.0)) + float(bottom.get("x", 0.0)) * scale_x,
            "y": float(destination.get("y", 0.0)) + float(bottom.get("y", 0.0)) * scale_y
        }
    }


def point_is_inside_rectangle(point, rectangle):
    return rectangle["x"] <= point["x"] <= rectangle["x"] + rectangle["width"] and rectangle["y"] <= point["y"] <= rectangle["y"] + rectangle["height"]

def intersect_segment_with_rectangle_entry(start, end, rectangle):
    """Return the first boundary crossing for a segment ending inside a rectangle."""
    if rectangle["width"] <= 0.000001 or rectangle["height"] <= 0.000001:
        return None
    if point_is_inside_rectangle(start, rectangle):
        return {"inside": True, "side": None, "side_position": None, "entry_world": dict(start), "t": 0.0}

    left = rectangle["x"]
    right = left + rectangle["width"]
    top = rectangle["y"]
    bottom = top + rectangle["height"]
    delta_x = float(end["x"] - start["x"])
    delta_y = float(end["y"] - start["y"])
    candidates = []

    if abs(delta_x) > 0.000001:
        for boundary, side in ((left, "left"), (right, "right")):
            t = (boundary - start["x"]) / delta_x
            y = start["y"] + delta_y * t
            if -0.000001 <= t <= 1.000001 and top - 0.000001 <= y <= bottom + 0.000001:
                candidates.append((max(0.0, t), side, {"x": boundary, "y": y}))

    if abs(delta_y) > 0.000001:
        for boundary, side in ((top, "up"), (bottom, "down")):
            t = (boundary - start["y"]) / delta_y
            x = start["x"] + delta_x * t
            if -0.000001 <= t <= 1.000001 and left - 0.000001 <= x <= right + 0.000001:
                candidates.append((max(0.0, t), side, {"x": x, "y": boundary}))

    if not candidates:
        return None
    t, side, entry = min(candidates, key=lambda value: (value[0], {"up": 0, "down": 1, "left": 2, "right": 3}[value[1]]))
    if side in {"up", "down"}:
        side_position = (entry["x"] - left) / rectangle["width"]
    else:
        side_position = (entry["y"] - top) / rectangle["height"]
    return {"inside": False, "side": side, "side_position": max(0.0, min(1.0, side_position)), "entry_world": entry, "t": t}

def calculate_corner_blend_directional_weights(side, side_position, corner_blend_fraction=0.20, maximum_adjacent_weight=0.50):
    weights = {"down": 0.0, "up": 0.0, "left": 0.0, "right": 0.0}
    if side not in weights:
        return weights
    position = max(0.0, min(1.0, float(side_position)))
    fraction = max(0.000001, min(0.5, float(corner_blend_fraction)))
    maximum = max(0.0, min(0.5, float(maximum_adjacent_weight)))
    adjacency = {
        "up": ("left", "right"), "down": ("left", "right"),
        "left": ("up", "down"), "right": ("up", "down")
    }
    adjacent_side = None
    adjacent_weight = 0.0
    if position < fraction:
        adjacent_side = adjacency[side][0]
        adjacent_weight = maximum * (1.0 - smoothstep_cpu(0.0, fraction, position))
    elif position > 1.0 - fraction:
        adjacent_side = adjacency[side][1]
        adjacent_weight = maximum * smoothstep_cpu(1.0 - fraction, 1.0, position)
    weights[side] = 1.0 - adjacent_weight
    if adjacent_side is not None:
        weights[adjacent_side] = adjacent_weight
    return weights

def calculate_render_item_light_direction_entry(render_item, light_position):
    rectangle = get_render_item_direction_basis_world_rect(render_item)
    if rectangle is None:
        return None
    centre = {"x": rectangle["x"] + rectangle["width"] * 0.5, "y": rectangle["y"] + rectangle["height"] * 0.5}
    intersection = intersect_segment_with_rectangle_entry(light_position, centre, rectangle)
    if intersection is None:
        return None
    basis = render_item.get("self_shadow", {}).get("direction_basis", {})
    result = dict(intersection)
    result["rect_world"] = rectangle
    result["centre_world"] = centre
    if intersection["inside"]:
        result["weights"] = {"down": 0.0, "up": 0.0, "left": 0.0, "right": 0.0}
        result["omni"] = True
    else:
        result["weights"] = calculate_corner_blend_directional_weights(intersection["side"], intersection["side_position"], basis.get("corner_blend_fraction", 0.20), basis.get("maximum_adjacent_weight", 0.50))
        result["omni"] = False
    return result

def get_render_item_direction_basis_ray_samples(render_item):
    """Return equal-area cell centres for the optional sprite-rectangle ray grid.

    Each cell represents an interval of the authored base plate.  Sampling several
    intervals keeps a narrow spotlight tied to the part of the plate it actually
    reaches instead of classifying the whole entity with one centre ray.
    """
    rectangle = get_render_item_direction_basis_world_rect(render_item)
    if rectangle is None:
        return []
    basis = render_item.get("self_shadow", {}).get("direction_basis", {})
    grid = basis.get("ray_grid", {})
    columns = max(1, min(15, int(grid.get("columns", 7))))
    rows = max(1, min(15, int(grid.get("rows", 3))))
    result = []
    for row in range(rows):
        v = (row + 0.5) / rows
        for column in range(columns):
            u = (column + 0.5) / columns
            result.append({
                "column": column,
                "row": row,
                "u": u,
                "v": v,
                "world": {
                    "x": rectangle["x"] + rectangle["width"] * u,
                    "y": rectangle["y"] + rectangle["height"] * v
                }
            })
    return result

def calculate_render_item_light_direction_bundle(render_item, prepared_light, collision_grid):
    """Blend a prepared light's rectangle-entry directions over equal-area ray intervals."""
    rectangle = get_render_item_direction_basis_world_rect(render_item)
    if rectangle is None:
        return None
    light_position = prepared_light.get("world_position", {})
    if "x" not in light_position or "y" not in light_position:
        return None
    light = prepared_light.get("light", {})
    direction_origin = light.get("entity_direction_origin")
    has_stable_direction_origin = isinstance(direction_origin, dict) and "x" in direction_origin and "y" in direction_origin
    if not has_stable_direction_origin:
        direction_origin = light_position
    centre = {"x": rectangle["x"] + rectangle["width"] * 0.5, "y": rectangle["y"] + rectangle["height"] * 0.5}
    if point_is_inside_rectangle(direction_origin, rectangle):
        return {
            "inside": True,
            "omni": True,
            "side": None,
            "side_position": None,
            "entry_world": dict(direction_origin),
            "centre_world": centre,
            "rect_world": rectangle,
            "weights": {"down": 0.0, "up": 0.0, "left": 0.0, "right": 0.0},
            "rays": [],
            "direction_origin_world": dict(direction_origin)
        }

    basis = render_item.get("self_shadow", {}).get("direction_basis", {})
    rays = []
    totals = {"down": 0.0, "up": 0.0, "left": 0.0, "right": 0.0}
    total_strength = 0.0
    entry_x_total = 0.0
    entry_y_total = 0.0

    for sample in get_render_item_direction_basis_ray_samples(render_item):
        sample_world = sample["world"]
        entry = intersect_segment_with_rectangle_entry(light_position, sample_world, rectangle)
        if entry is None or entry.get("inside", False):
            continue
        weights = calculate_corner_blend_directional_weights(
            entry["side"], entry["side_position"],
            basis.get("corner_blend_fraction", 0.20), basis.get("maximum_adjacent_weight", 0.50)
        )
        sample_strength = light_visibility.get_unoccluded_light_strength_at_world_point(light, sample_world, collision_grid)
        if sample_strength > 0.000001 and not prepared_light_reaches_point(prepared_light, sample_world):
            sample_strength = 0.0
        ray = dict(sample)
        ray.update({
            "entry_world": entry["entry_world"],
            "side": entry["side"],
            "side_position": entry["side_position"],
            "weights": weights,
            "sample_strength": sample_strength,
            "active": sample_strength > 0.000001
        })
        rays.append(ray)
        if sample_strength <= 0.000001:
            continue
        total_strength += sample_strength
        entry_x_total += entry["entry_world"]["x"] * sample_strength
        entry_y_total += entry["entry_world"]["y"] * sample_strength
        for side in totals:
            totals[side] += weights[side] * sample_strength

    # A spotlight's rotating render-origin offset and changing cone coverage
    # must not select a different authored response profile.  When a stable
    # direction origin is supplied, the base-plate entry alone selects the
    # profile; the ordinary direct-light texture still determines exactly which
    # sprite pixels the cone reaches.  Keep the physical-origin ray bundle above
    # for diagnostics.
    if has_stable_direction_origin:
        stable_entry = calculate_render_item_light_direction_entry(render_item, direction_origin)
        if stable_entry is None:
            return None
        stable_entry["rays"] = rays
        stable_entry["active_ray_count"] = sum(1 for ray in rays if ray["active"])
        stable_entry["total_ray_count"] = len(rays)
        stable_entry["direction_origin_world"] = dict(direction_origin)
        stable_entry["stable_direction_origin"] = True
        return stable_entry

    if total_strength <= 0.000001:
        fallback = calculate_render_item_light_direction_entry(render_item, light_position)
        if fallback is None:
            return None
        fallback["rays"] = rays
        fallback["bundle_fallback"] = True
        return fallback

    weights = {side: value / total_strength for side, value in totals.items()}
    primary_side = max(weights, key=weights.get)
    primary_rays = [ray for ray in rays if ray["active"] and ray["side"] == primary_side]
    primary_strength = sum(ray["sample_strength"] for ray in primary_rays)
    side_position = sum(ray["side_position"] * ray["sample_strength"] for ray in primary_rays) / primary_strength if primary_strength > 0.000001 else 0.5
    return {
        "inside": False,
        "omni": False,
        "side": primary_side,
        "side_position": side_position,
        "entry_world": {"x": entry_x_total / total_strength, "y": entry_y_total / total_strength},
        "centre_world": centre,
        "rect_world": rectangle,
        "weights": weights,
        "rays": rays,
        "active_ray_count": sum(1 for ray in rays if ray["active"]),
        "total_ray_count": len(rays)
    }

def calculate_center_directional_weights(render_item, light_position):
    to_light = light_visibility.normalize_vector({"x": light_position["x"] - render_item["base_world"]["x"], "y": light_position["y"] - render_item["base_world"]["y"]})
    if to_light is None:
        return None
    scale = max(0.000001, abs(to_light["x"]) + abs(to_light["y"]))
    return {
        "down": max(0.0, to_light["y"]) / scale,
        "up": max(0.0, -to_light["y"]) / scale,
        "left": max(0.0, -to_light["x"]) / scale,
        "right": max(0.0, to_light["x"]) / scale
    }

def directional_weights_as_rgba(weights):
    return [float(weights.get("down", 0.0)), float(weights.get("up", 0.0)), float(weights.get("left", 0.0)), float(weights.get("right", 0.0))]

def calculate_per_light_profile_survival(response_rgba, weights, policy, omni=False):
    if omni:
        return 1.0
    return calculate_directional_profile_attenuation({"face_exposure": directional_weights_as_rgba(weights), "omni_exposure": 0.0}, policy, response_rgba)

def accumulate_surviving_direct_contributions(contributions):
    result = [0.0, 0.0, 0.0]
    for contribution in contributions:
        if contribution.get("blocked", False):
            continue
        color = list(contribution.get("rgb", [0.0, 0.0, 0.0]))
        survival = max(0.0, float(contribution.get("survival", 1.0)))
        while len(color) < 3:
            color.append(0.0)
        for index in range(3):
            result[index] += max(0.0, float(color[index])) * survival
    return result

def combine_independent_entity_lighting(ambient_rgb, direct_rgb, readability_rgb):
    channels = []
    for values in (ambient_rgb, direct_rgb, readability_rgb):
        value = list(values)
        while len(value) < 3:
            value.append(0.0)
        channels.append(value)
    return [max(0.0, float(channels[0][index])) + max(0.0, float(channels[1][index])) + max(0.0, float(channels[2][index])) for index in range(3)]

def prepare_entity_self_shadows(render_items, prepared_lights, major_occluders, collision_grid, collect_diagnostics=False):
    summaries = {}
    diagnostics = []

    for item in render_items:
        policy = item.get("self_shadow", {})
        summary = make_empty_entity_self_shadow_summary()
        face_totals = [0.0, 0.0, 0.0, 0.0]
        omni_total = 0.0
        sampled_total = 0.0
        visible_total = 0.0
        per_light = []

        for prepared_light in prepared_lights:
            light = prepared_light.get("light", {})

            if not prepared_light.get("affects_entities", light.get("affects_entities", light.get("affects_scene", True))) or not light.get("enabled", True) or light.get("render_style", "world") != "world":
                continue

            strength = get_prepared_light_strength_for_render_item(prepared_light, item, collision_grid)

            if strength <= 0.000001:
                continue

            sampled_total += strength
            bypass_occlusion = light.get("type") == "top_down" and not light.get("entity_occlusion_enabled", False)
            blocking, occlusion_tests = (None, []) if bypass_occlusion else query_entity_light_occlusion(prepared_light, item, major_occluders)

            if collect_diagnostics:
                for test in occlusion_tests:
                    diagnostics.append({"light_id": prepared_light.get("id"), "target_id": item.get("source_id"), "occluder_id": test["occluder"].get("source_id"), "light_position": dict(prepared_light["world_position"]), "target_position": dict(item["base_world"]), "intersection_fraction": test["intersection_fraction"], "ray_height": test["ray_height"], "occluder_height": test["occluder_height"], "blocked": test["blocked"]})

            mode = policy.get("mode", "none")
            explicit_directional = light.get("entity_lighting_mode") in {"directional", "directional_profiles"}
            is_omni = mode not in {"upright_box", "directional_profiles"} or (light.get("type") == "top_down" and not explicit_directional) or light.get("entity_lighting_mode") in {"omni", "overhead"}
            direction_entry = None
            weights = {"down": 0.0, "up": 0.0, "left": 0.0, "right": 0.0}

            if not is_omni:
                if mode == "directional_profiles" and policy.get("direction_basis", {}).get("mode") == "sprite_rect":
                    direction_entry = calculate_render_item_light_direction_bundle(item, prepared_light, collision_grid)
                    if direction_entry is None or direction_entry.get("omni", False):
                        is_omni = True
                    else:
                        weights = dict(direction_entry["weights"])
                else:
                    center_weights = calculate_center_directional_weights(item, prepared_light["world_position"])
                    if center_weights is None:
                        is_omni = True
                    else:
                        weights = center_weights

            light_record = {
                "light_id": prepared_light.get("id"),
                "light_position": dict(prepared_light["world_position"]),
                "direction_origin_world": dict(direction_entry.get("direction_origin_world", prepared_light["world_position"])) if direction_entry is not None else dict(prepared_light["world_position"]),
                "sampled_strength": strength,
                "blocked": blocking is not None,
                "omni": is_omni,
                "weights": weights,
                "face_exposure": directional_weights_as_rgba(weights),
                "omni_exposure": 1.0 if is_omni else 0.0,
                "direction_entry": direction_entry,
                "self_shadow_mode": mode
            }
            per_light.append(light_record)

            if blocking is not None:
                summary["blocked_direct_count"] += 1
                continue

            visible_total += strength

            if is_omni:
                omni_total += strength
                continue

            rgba_weights = directional_weights_as_rgba(weights)
            for index in range(4):
                face_totals[index] += strength * rgba_weights[index]

        summary["sampled_world_strength"] = sampled_total
        summary["visible_world_strength"] = visible_total

        if sampled_total > 0.000001:
            summary["world_occlusion_scale"] = max(0.0, min(1.0, visible_total / sampled_total))

        if visible_total > 0.000001:
            summary["face_exposure"] = [value / visible_total for value in face_totals]
            summary["omni_exposure"] = omni_total / visible_total

        summary["per_light"] = per_light

        item["self_shadow_summary"] = summary
        summaries[item.get("source_id", str(item.get("id")))] = summary

    return {"summaries": summaries, "occlusion_tests": diagnostics}

def get_spot_light_strength_at_world_point(light, world_point, tile_map):
    light_position = get_light_world_position(light, tile_map)
    from_light = game.vec2_subtract(world_point, light_position)
    distance_from_light = game.vec2_norm(from_light)
    radius = max(0.0001, float(light.get("radius", 100.0)))

    if distance_from_light >= radius:
        return 0.0

    radial_strength = 1.0 - distance_from_light / radius
    radial_strength = max(0.0, min(1.0, radial_strength)) ** max(0.0001, float(light.get("falloff", 2.0)))
    cone_strength = 1.0

    if light.get("type", "point") == "spot" and distance_from_light > 0.0001:
        direction_to_point = game.vec2_scale(from_light, 1.0 / distance_from_light)
        light_direction = game.vec2_normalize(light.get("direction", {"x": 1.0, "y": 0.0}))
        alignment = direction_to_point["x"] * light_direction["x"] + direction_to_point["y"] * light_direction["y"]
        inner_angle = float(light.get("inner_angle", 20.0))
        outer_angle = max(inner_angle + 0.001, float(light.get("outer_angle", 35.0)))
        inner_cone_cos = math.cos(math.radians(inner_angle))
        outer_cone_cos = math.cos(math.radians(outer_angle))
        cone_strength = smoothstep_cpu(outer_cone_cos, inner_cone_cos, alignment)

    near_strength = 1.0
    near_fade_distance = max(0.0, float(light.get("near_fade_distance", 0.0)))

    if near_fade_distance > 0.0:
        near_strength = smoothstep_cpu(0.0, near_fade_distance, distance_from_light)

    strength = radial_strength * cone_strength * near_strength * max(0.0, float(light.get("intensity", 1.0)))
    return max(0.0, min(1.0, strength))

def build_cinematic_shadow_quad(sprite_info, shadow_settings, flashlight_position, light_height):
    floor_anchor = dict(sprite_info["base_world"])
    from_light = game.vec2_subtract(floor_anchor, flashlight_position)
    distance_from_light = game.vec2_norm(from_light)

    if distance_from_light <= 0.0001:
        return None

    projection_direction = game.vec2_scale(from_light, 1.0 / distance_from_light)
    side_direction = {"x": -projection_direction["y"], "y": projection_direction["x"]}
    cast_height = max(0.0, float(shadow_settings.get("cast_height", sprite_info.get("visual_height", 0.0))))
    length = g_render_order.calculate_shadow_length(shadow_settings, distance_from_light, light_height, sprite_info.get("visual_height", 0.0))
    if length is None:
        return None
    near_offset = float(shadow_settings.get("near_offset", 1.0))
    lateral_skew = float(shadow_settings.get("lateral_skew", 0.0))
    near_half_width = sprite_info["sprite_width"] * max(0.0, float(shadow_settings.get("near_width", 0.70))) * 0.5
    far_half_width = sprite_info["sprite_width"] * max(0.0, float(shadow_settings.get("far_width", 1.20))) * 0.5
    near_center = game.vec2_add(floor_anchor, game.vec2_scale(projection_direction, near_offset))
    far_center = game.vec2_add(near_center, game.vec2_add(game.vec2_scale(projection_direction, length), game.vec2_scale(side_direction, lateral_skew * length)))

    return {
        "floor_anchor": floor_anchor,
        "near_center": near_center,
        "far_center": far_center,
        "near_left": game.vec2_subtract(near_center, game.vec2_scale(side_direction, near_half_width)),
        "near_right": game.vec2_add(near_center, game.vec2_scale(side_direction, near_half_width)),
        "far_left": game.vec2_subtract(far_center, game.vec2_scale(side_direction, far_half_width)),
        "far_right": game.vec2_add(far_center, game.vec2_scale(side_direction, far_half_width)),
        "length": length,
        "cast_height": cast_height,
        "light_height": light_height
    }

def resolve_texture_reference(reference, game_assets):
    """Resolve the serialisable {collection, name, optional field} asset shape."""
    if not isinstance(reference, dict):
        return None
    collection = reference.get("collection")
    name = reference.get("name")
    field = reference.get("field")
    if not isinstance(collection, str) or not collection or not isinstance(name, str) or not name or (field is not None and not isinstance(field, str)):
        return None
    assets = game_assets.get(collection, {})
    asset = assets.get(name) if isinstance(assets, dict) else None
    return asset.get(field) if isinstance(asset, dict) and field is not None else asset

def resolve_render_item_texture(render_item, game_assets):
    return resolve_texture_reference(render_item.get("texture", {}), game_assets)

def _matching_texture_dimensions(source_texture, response_texture):
    try:
        source_size = (int(source_texture.width), int(source_texture.height))
        response_size = (int(response_texture.width), int(response_texture.height))
        response_id = getattr(response_texture, "id", None)
        return source_size[0] > 0 and source_size[1] > 0 and response_size == source_size and (response_id is None or int(response_id) > 0)
    except (AttributeError, TypeError, ValueError):
        return False

def _report_directional_profile_asset_error_once(reference, reason, fallback_mode):
    key = (repr(reference.get("collection")), repr(reference.get("name")), repr(reference.get("field")), reason, fallback_mode) if isinstance(reference, dict) else (None, None, None, reason, fallback_mode)
    if key in _REPORTED_DIRECTIONAL_PROFILE_ASSET_ERRORS:
        return
    _REPORTED_DIRECTIONAL_PROFILE_ASSET_ERRORS.add(key)
    texture_name = reference.get("name", "<invalid reference>") if isinstance(reference, dict) else "<invalid reference>"
    print(f"warning: directional self-shadow response texture '{texture_name}' {reason}; using {fallback_mode} fallback")

def resolve_entity_self_shadow_resources(render_item, source_texture, game_assets, report_errors=True):
    policy = render_item.get("self_shadow", {})
    requested_mode = policy.get("mode", "none")
    active_mode = requested_mode if isinstance(requested_mode, str) and requested_mode in ENTITY_SELF_SHADOW_MODES else "none"
    response_reference = policy.get("response_texture", {})
    response_texture = None
    fallback_used = False
    failure_reason = None

    if active_mode == "directional_profiles":
        response_texture = resolve_texture_reference(response_reference, game_assets)
        if response_texture is None:
            failure_reason = "is missing or invalid"
        elif not _matching_texture_dimensions(source_texture, response_texture):
            failure_reason = "does not match the source texture dimensions"

        if failure_reason is not None:
            response_texture = None
            fallback_mode = policy.get("fallback_mode", "upright_box")
            active_mode = fallback_mode if isinstance(fallback_mode, str) and fallback_mode in {"none", "upright_box"} else "upright_box"
            fallback_used = True
            if report_errors:
                _report_directional_profile_asset_error_once(response_reference, failure_reason, active_mode)

    runtime = {
        "requested_mode": requested_mode,
        "active_mode": active_mode,
        "response_texture_name": response_reference.get("name") if response_texture is not None and isinstance(response_reference, dict) else None,
        "requested_response_texture_name": response_reference.get("name") if isinstance(response_reference, dict) else None,
        "fallback_used": fallback_used,
        "failure_reason": failure_reason
    }
    render_item["self_shadow_runtime"] = runtime
    return dict(runtime, response_texture=response_texture, mode_value=ENTITY_SELF_SHADOW_MODES[active_mode])

def set_entity_self_shadow_shader_values(shader_info, render_item, texture, lighting_profile, entity_lighting, entity_readability_lighting, game_assets, debug_output_mode=0, self_shadow_pass=0):
    shader = shader_info["shader"]
    summary = render_item.get("self_shadow_summary", {})
    policy = render_item.get("self_shadow", {})
    resources = resolve_entity_self_shadow_resources(render_item, texture, game_assets)
    ambient = normalize_light_color(lighting_profile.get("ambient_color", [0.18, 0.14, 0.26]))
    shadow = normalize_light_color(lighting_profile.get("shadow_color", [0.0, 0.0, 0.0]))
    exposure = list(summary.get("face_exposure", [1.0, 0.0, 0.0, 0.0]))

    while len(exposure) < 4:
        exposure.append(0.0)

    source = render_item["source_rect"]
    destination = render_item["dest_rect"]
    texture_width = max(1.0, float(texture.width))
    texture_height = max(1.0, float(texture.height))
    set_shader_vec2(shader, shader_info["resolution_location"], entity_lighting.texture.width, entity_lighting.texture.height)
    set_shader_vec2(shader, shader_info["source_uv_min_location"], source["x"] / texture_width, source["y"] / texture_height)
    set_shader_vec2(shader, shader_info["source_uv_max_location"], (source["x"] + source["width"]) / texture_width, (source["y"] + source["height"]) / texture_height)
    set_shader_vec4(shader, shader_info["face_exposure_location"], exposure[0], exposure[1], exposure[2], exposure[3])
    set_shader_float(shader, shader_info["omni_exposure_location"], summary.get("omni_exposure", 0.0))
    set_shader_float(shader, shader_info["world_occlusion_scale_location"], summary.get("world_occlusion_scale", 1.0))
    set_shader_int(shader, shader_info["self_shadow_mode_location"], resources["mode_value"])
    set_shader_float(shader, shader_info["self_shadow_strength_location"], policy.get("strength", 0.0))
    set_shader_float(shader, shader_info["self_shadow_softness_location"], policy.get("softness", 0.10))
    set_shader_float(shader, shader_info["self_shadow_back_fill_location"], policy.get("back_fill", 0.06))
    set_shader_float(shader, shader_info["self_shadow_minimum_direct_location"], max(0.0, min(1.0, float(policy.get("minimum_direct", 0.0)))))
    divider = policy.get("profile_divider", {})
    divider_enabled = resources["mode_value"] == ENTITY_SELF_SHADOW_MODES["directional_profiles"] and bool(divider.get("enabled", False))
    source_width = max(0.000001, abs(float(source.get("width", 0.0))))
    source_height = max(0.000001, abs(float(source.get("height", 0.0))))
    divider_top = divider.get("top", {})
    divider_bottom = divider.get("bottom", {})
    direction_origin = summary.get("direction_origin_world", {})
    destination_width = float(destination.get("width", 0.0))
    destination_height = float(destination.get("height", 0.0))
    if not isinstance(direction_origin, dict) or "x" not in direction_origin or "y" not in direction_origin or abs(destination_width) <= 0.000001 or abs(destination_height) <= 0.000001:
        divider_enabled = False
        direction_origin = {"x": float(destination.get("x", 0.0)), "y": float(destination.get("y", 0.0))}
    set_shader_int(shader, shader_info.get("profile_divider_enabled_location", -1), 1 if divider_enabled else 0)
    set_shader_vec2(shader, shader_info.get("profile_divider_top_location", -1), float(divider_top.get("x", 0.0)) / source_width, float(divider_top.get("y", 0.0)) / source_height)
    set_shader_vec2(shader, shader_info.get("profile_divider_bottom_location", -1), float(divider_bottom.get("x", 0.0)) / source_width, float(divider_bottom.get("y", 0.0)) / source_height)
    set_shader_vec2(shader, shader_info.get("profile_light_origin_location", -1), (float(direction_origin["x"]) - float(destination.get("x", 0.0))) / (destination_width if abs(destination_width) > 0.000001 else 1.0), (float(direction_origin["y"]) - float(destination.get("y", 0.0))) / (destination_height if abs(destination_height) > 0.000001 else 1.0))
    set_shader_int(shader, shader_info["self_shadow_debug_output_location"], debug_output_mode)
    set_shader_int(shader, shader_info["self_shadow_pass_location"], self_shadow_pass)
    set_shader_vec3(shader, shader_info["ambient_color_location"], ambient[0], ambient[1], ambient[2])
    set_shader_vec3(shader, shader_info["shadow_color_location"], shadow[0], shadow[1], shadow[2])
    set_shader_float(shader, shader_info["ambient_strength_location"], lighting_profile.get("ambient_strength", 0.3))
    set_shader_float(shader, shader_info["direct_light_strength_location"], lighting_profile.get("direct_light_strength", 1.0))
    set_shader_float(shader, shader_info["black_point_location"], lighting_profile.get("black_point", 0.1))
    set_shader_float(shader, shader_info["shadow_softness_location"], lighting_profile.get("shadow_softness", 0.03))
    set_shader_float(shader, shader_info["shadow_detail_location"], lighting_profile.get("shadow_detail", 0.0))
    set_shader_float(shader, shader_info["contrast_location"], lighting_profile.get("contrast", 1.0))
    set_shader_float(shader, shader_info["light_posterize_enabled_location"], 1.0 if lighting_profile.get("light_posterize_enabled", True) else 0.0)
    set_shader_float(shader, shader_info["light_posterize_levels_location"], lighting_profile.get("light_posterize_levels", 8.0))
    set_shader_float(shader, shader_info["light_dither_enabled_location"], 1.0 if lighting_profile.get("light_dither_enabled", False) else 0.0)
    set_shader_float(shader, shader_info["light_dither_strength_location"], lighting_profile.get("light_dither_strength", 0.5))
    set_shader_float(shader, shader_info["posterize_ambient_location"], 1.0 if lighting_profile.get("posterize_ambient", False) else 0.0)
    return resources

def begin_entity_self_shadow_shader(shader_info, render_item, texture, lighting_profile, entity_lighting, entity_readability_lighting, game_assets, debug_output_mode=0, self_shadow_pass=0):
    resources = set_entity_self_shadow_shader_values(shader_info, render_item, texture, lighting_profile, entity_lighting, entity_readability_lighting, game_assets, debug_output_mode, self_shadow_pass)
    pr.begin_shader_mode(shader_info["shader"])
    set_shader_texture(shader_info["shader"], shader_info["entity_light_texture_location"], entity_lighting.texture)
    set_shader_texture(shader_info["shader"], shader_info["entity_readability_light_texture_location"], entity_readability_lighting.texture)
    if resources["mode_value"] == ENTITY_SELF_SHADOW_MODES["directional_profiles"]:
        set_shader_texture(shader_info["shader"], shader_info["directional_response_texture_location"], resources["response_texture"])
    return resources

def _render_single_prepared_entity_light(prepared_light, game_camera, scratch_target, game_assets):
    pr.begin_texture_mode(scratch_target)
    pr.clear_background(pr.BLACK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
    # Entity eligibility/occlusion is resolved at its ground/basis samples.  Reusing
    # the floor-plane wall polygon here would project that 2D edge vertically through
    # an upright sprite, producing wall-shaped black slices through tall entities.
    draw_prepared_light_to_target(prepared_light, game_camera, scratch_target, game_assets, include_receivers=False, clip_to_wall_visibility=False)
    pr.end_blend_mode()
    pr.end_texture_mode()

def _make_per_light_render_item(render_item, light_record, mode_override=None):
    result = dict(render_item)
    if mode_override is not None:
        result["self_shadow"] = {"mode": mode_override, "strength": 0.0}
    result["self_shadow_summary"] = {
        "face_exposure": list(light_record.get("face_exposure", [0.0, 0.0, 0.0, 0.0])),
        "omni_exposure": float(light_record.get("omni_exposure", 0.0)),
        "world_occlusion_scale": 1.0,
        "direction_origin_world": dict(light_record.get("direction_origin_world", light_record.get("light_position", {})))
    }
    return result

def _draw_render_item_main_shape(render_item, texture, game_camera):
    source = render_item["source_rect"]
    destination = render_item["dest_rect"]
    # Static world items snap world and camera independently to stay registered
    # with tiles. Moving actors snap their relative position once so co-moving
    # fractional player/camera motion cannot toggle by a pixel. Every entity
    # lighting pass comes through this same policy.
    snap = (
        g_render_order.moving_world_to_screen_pixel
        if render_item.get("screen_snap") == "relative_motion"
        else g_render_order.world_to_screen_pixel
    )
    screen_position = snap(destination["x"], destination["y"], game_camera)
    pr.draw_texture_pro(
        texture,
        pr.Rectangle(source["x"], source["y"], source["width"], source["height"]),
        pr.Rectangle(screen_position["x"], screen_position["y"], destination["width"], destination["height"]),
        pr.Vector2(0, 0), 0, pr.WHITE
    )

def _player_weapon_is_visible(render_item):
    return (
        render_item.get("source") == "player"
        and bool(render_item.get("draw_data", {}).get("weapon_visible", False))
    )


def _get_player_pistol_part(render_item, game_camera, game_assets):
    if not _player_weapon_is_visible(render_item):
        return None
    draw_data = render_item.get("draw_data", {})
    texture = game_assets.get("textures", {}).get(draw_data.get("pistol_texture", "pistol_texture"))
    if texture is None:
        return None
    position = draw_data.get("pistol_world", {})
    pseudo_item = dict(render_item)
    pseudo_item["source_rect"] = {"x": 0.0, "y": 0.0, "width": float(texture.width), "height": float(texture.height)}
    pseudo_item["self_shadow"] = {"mode": "none", "strength": 0.0}
    screen_position = g_render_order.moving_world_to_screen_pixel(
        position.get("x", 0.0), position.get("y", 0.0), game_camera,
    )
    return {
        "texture": texture,
        "render_item": pseudo_item,
        "screen_position": pr.Vector2(screen_position["x"], screen_position["y"]),
        "angle": float(draw_data.get("pistol_angle", 0.0))
    }

def _draw_player_pistol_part(part):
    pr.draw_texture_ex(part["texture"], part["screen_position"], part["angle"], 0.5, pr.WHITE)

def _reset_entity_direct_shape(shader_info, render_item, texture, draw_shape, scratch_target, readability_target, lighting_profile, game_assets):
    begin_entity_self_shadow_shader(shader_info, render_item, texture, lighting_profile, scratch_target, readability_target, game_assets, self_shadow_pass=2)
    draw_shape()
    pr.end_shader_mode()

def _add_entity_direct_shape(shader_info, render_item, texture, draw_shape, scratch_target, readability_target, lighting_profile, game_assets):
    begin_entity_self_shadow_shader(shader_info, render_item, texture, lighting_profile, scratch_target, readability_target, game_assets, self_shadow_pass=1)
    draw_shape()
    pr.end_shader_mode()

def _composite_entity_layer_to_scene(scene_target, albedo_target, direct_target, readability_target, game_assets, lighting_profile):
    width = albedo_target.texture.width
    height = albedo_target.texture.height
    composite_target = get_or_create_render_target(game_assets, "entity_lighting_composite", width, height)
    composite_shader = game_assets["shaders"]["lighting_composite"]
    shader = composite_shader["shader"]
    ambient = normalize_light_color(lighting_profile.get("ambient_color", [0.2, 0.2, 0.3]))
    shadow = normalize_light_color(lighting_profile.get("shadow_color", [0.0, 0.0, 0.0]))
    set_shader_vec3(shader, composite_shader["ambient_color_location"], ambient[0], ambient[1], ambient[2])
    set_shader_vec3(shader, composite_shader["shadow_color_location"], shadow[0], shadow[1], shadow[2])
    set_shader_float(shader, composite_shader["ambient_strength_location"], lighting_profile.get("ambient_strength", 0.3))
    set_shader_float(shader, composite_shader["direct_light_strength_location"], lighting_profile.get("direct_light_strength", 1.0))
    set_shader_float(shader, composite_shader["black_point_location"], lighting_profile.get("black_point", 0.1))
    set_shader_float(shader, composite_shader["shadow_softness_location"], lighting_profile.get("shadow_softness", 0.03))
    set_shader_float(shader, composite_shader["shadow_detail_location"], lighting_profile.get("shadow_detail", 0.0))
    set_shader_float(shader, composite_shader["contrast_location"], lighting_profile.get("contrast", 1.0))
    set_shader_float(shader, composite_shader["light_posterize_enabled_location"], 1.0 if lighting_profile.get("light_posterize_enabled", True) else 0.0)
    set_shader_float(shader, composite_shader["light_posterize_levels_location"], lighting_profile.get("light_posterize_levels", 8.0))
    set_shader_float(shader, composite_shader["light_dither_enabled_location"], 1.0 if lighting_profile.get("light_dither_enabled", False) else 0.0)
    set_shader_float(shader, composite_shader["light_dither_strength_location"], lighting_profile.get("light_dither_strength", 0.5))
    set_shader_float(shader, composite_shader["posterize_ambient_location"], 1.0 if lighting_profile.get("posterize_ambient", False) else 0.0)
    full_source = pr.Rectangle(0, 0, width, -height)
    full_destination = pr.Rectangle(0, 0, width, height)
    pr.begin_texture_mode(composite_target)
    pr.clear_background(pr.BLANK)
    pr.begin_shader_mode(shader)
    set_shader_texture(shader, composite_shader["light_texture_location"], direct_target.texture)
    set_shader_texture(shader, composite_shader["readability_light_texture_location"], readability_target.texture)
    pr.draw_texture_pro(albedo_target.texture, full_source, full_destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_shader_mode()
    pr.end_texture_mode()
    pr.begin_texture_mode(scene_target)
    pr.draw_texture_pro(composite_target.texture, full_source, full_destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()
    return composite_target

def _add_entity_light_layer_to_direct(light_layer_target, direct_target):
    width = direct_target.texture.width
    height = direct_target.texture.height
    pr.rl_set_blend_factors_separate(pr.RL_ONE, pr.RL_ONE, pr.RL_ZERO, pr.RL_ONE, pr.RL_FUNC_ADD, pr.RL_FUNC_ADD)
    pr.begin_texture_mode(direct_target)
    pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
    pr.draw_texture_pro(light_layer_target.texture, pr.Rectangle(0, 0, width, -height), pr.Rectangle(0, 0, width, height), pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_blend_mode()
    pr.end_texture_mode()

def draw_sorted_world_render_items(render_items, scene_target, game_camera, game_assets, lighting_profile, prepared_lights=None, entity_readability_lighting=None, player_entity=None):
    prepared_lights = list(prepared_lights or [])
    shader_info = game_assets.get("shaders", {}).get("entity_self_shadow")
    if entity_readability_lighting is None or shader_info is None:
        pr.begin_texture_mode(scene_target)
        for item in render_items:
            texture = resolve_render_item_texture(item, game_assets)
            if texture is not None:
                _draw_render_item_main_shape(item, texture, game_camera)
                if _player_weapon_is_visible(item):
                    draw_data = item.get("draw_data", {})
                    center = draw_data.get("center_world", {})
                    gun = draw_data.get("gun_world", {})
                    center_pixel = g_render_order.moving_world_to_screen_pixel(
                        center.get("x", 0.0), center.get("y", 0.0), game_camera,
                    )
                    gun_pixel = g_render_order.moving_world_to_screen_pixel(
                        gun.get("x", 0.0), gun.get("y", 0.0), game_camera,
                    )
                    center_screen = pr.Vector2(center_pixel["x"], center_pixel["y"])
                    gun_screen = pr.Vector2(gun_pixel["x"], gun_pixel["y"])
                    if player_entity is not None:
                        player_entity["gun_render_pos"] = {"x": gun_screen.x, "y": gun_screen.y}
                    pr.draw_line(int(center_screen.x), int(center_screen.y), int(gun_screen.x), int(gun_screen.y), pr.Color(174, 164, 175, 255))
                    pistol_part = _get_player_pistol_part(item, game_camera, game_assets)
                    if pistol_part is not None:
                        _draw_player_pistol_part(pistol_part)
        pr.end_texture_mode()
        return {"entity_direct_light": None, "single_light_scratch": None, "scratch_light_draws": 0, "survival_draws": 0}

    width = scene_target.texture.width
    height = scene_target.texture.height
    albedo_target = get_or_create_render_target(game_assets, "entity_albedo", width, height)
    direct_target = get_or_create_render_target(game_assets, "entity_direct_light", width, height)
    scratch_target = get_or_create_render_target(game_assets, "entity_single_light_scratch", width, height)
    light_layer_target = get_or_create_render_target(game_assets, "entity_single_light_survival", width, height)
    scratch_light_draws = 0
    survival_draws = 0

    pr.begin_texture_mode(albedo_target)
    pr.clear_background(pr.BLANK)
    pr.end_texture_mode()
    pr.begin_texture_mode(direct_target)
    pr.clear_background(pr.BLANK)
    pr.end_texture_mode()

    eligible_lights = []
    for prepared_light in prepared_lights:
        light = prepared_light.get("light", {})
        if not light.get("enabled", True) or not prepared_light.get("affects_entities", light.get("affects_entities", False)) or light.get("render_style", "world") != "world":
            continue
        light_id = prepared_light.get("id")
        if any(any(record.get("light_id") == light_id and not record.get("blocked", False) for record in item.get("self_shadow_summary", {}).get("per_light", [])) for item in render_items):
            eligible_lights.append(prepared_light)

    for prepared_light in eligible_lights:
        light_id = prepared_light.get("id")
        _render_single_prepared_entity_light(prepared_light, game_camera, scratch_target, game_assets)
        scratch_light_draws += 1
        pr.begin_texture_mode(light_layer_target)
        pr.clear_background(pr.BLANK)
        pr.end_texture_mode()

        for item in render_items:
            texture = resolve_render_item_texture(item, game_assets)
            if texture is None:
                continue
            light_record = next((record for record in item.get("self_shadow_summary", {}).get("per_light", []) if record.get("light_id") == light_id), None)
            main_shape = lambda current=item, current_texture=texture: _draw_render_item_main_shape(current, current_texture, game_camera)
            pr.begin_texture_mode(light_layer_target)
            _reset_entity_direct_shape(shader_info, item, texture, main_shape, scratch_target, entity_readability_lighting, lighting_profile, game_assets)
            pr.end_texture_mode()

            if light_record is not None and not light_record.get("blocked", False):
                per_light_item = _make_per_light_render_item(item, light_record)
                pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA, pr.RL_ONE, pr.RL_ZERO, pr.RL_ONE, pr.RL_FUNC_ADD, pr.RL_FUNC_ADD)
                pr.begin_texture_mode(light_layer_target)
                pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
                _add_entity_direct_shape(shader_info, per_light_item, texture, main_shape, scratch_target, entity_readability_lighting, lighting_profile, game_assets)
                pr.end_blend_mode()
                pr.end_texture_mode()
                survival_draws += 1

            pistol_part = _get_player_pistol_part(item, game_camera, game_assets)
            if pistol_part is not None:
                pistol_shape = lambda current=pistol_part: _draw_player_pistol_part(current)
                pr.begin_texture_mode(light_layer_target)
                _reset_entity_direct_shape(shader_info, pistol_part["render_item"], pistol_part["texture"], pistol_shape, scratch_target, entity_readability_lighting, lighting_profile, game_assets)
                pr.end_texture_mode()
                if light_record is not None and not light_record.get("blocked", False):
                    pistol_item = _make_per_light_render_item(pistol_part["render_item"], light_record, mode_override="none")
                    pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA, pr.RL_ONE, pr.RL_ZERO, pr.RL_ONE, pr.RL_FUNC_ADD, pr.RL_FUNC_ADD)
                    pr.begin_texture_mode(light_layer_target)
                    pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
                    _add_entity_direct_shape(shader_info, pistol_item, pistol_part["texture"], pistol_shape, scratch_target, entity_readability_lighting, lighting_profile, game_assets)
                    pr.end_blend_mode()
                    pr.end_texture_mode()
                    survival_draws += 1

        _add_entity_light_layer_to_direct(light_layer_target, direct_target)

    for item in render_items:
        texture = resolve_render_item_texture(item, game_assets)
        if texture is None:
            continue
        pistol_part = _get_player_pistol_part(item, game_camera, game_assets)
        pr.begin_texture_mode(albedo_target)
        _draw_render_item_main_shape(item, texture, game_camera)
        if _player_weapon_is_visible(item):
            draw_data = item.get("draw_data", {})
            center = draw_data.get("center_world", {})
            gun = draw_data.get("gun_world", {})
            center_pixel = g_render_order.moving_world_to_screen_pixel(
                center.get("x", 0.0), center.get("y", 0.0), game_camera,
            )
            gun_pixel = g_render_order.moving_world_to_screen_pixel(
                gun.get("x", 0.0), gun.get("y", 0.0), game_camera,
            )
            center_screen = pr.Vector2(center_pixel["x"], center_pixel["y"])
            gun_screen = pr.Vector2(gun_pixel["x"], gun_pixel["y"])
            if player_entity is not None:
                player_entity["gun_render_pos"] = {"x": gun_screen.x, "y": gun_screen.y}
            pr.draw_line(int(center_screen.x), int(center_screen.y), int(gun_screen.x), int(gun_screen.y), pr.Color(174, 164, 175, 255))
            if pistol_part is not None:
                _draw_player_pistol_part(pistol_part)
        pr.end_texture_mode()

    composite_target = _composite_entity_layer_to_scene(scene_target, albedo_target, direct_target, entity_readability_lighting, game_assets, lighting_profile)
    return {
        "entity_albedo": albedo_target,
        "entity_direct_light": direct_target,
        "single_light_scratch": scratch_target,
        "single_light_survival": light_layer_target,
        "entity_composite": composite_target,
        "scratch_light_draws": scratch_light_draws,
        "survival_draws": survival_draws
    }

def draw_entity_self_shadow_debug(render_items, major_occluders, entity_self_shadow_frame, game_camera, game_assets=None, lighting_profile=None, entity_lighting=None, entity_readability_lighting=None):
    blocker_ids = {item.get("source_id") for item in major_occluders}
    game_assets = game_assets or {}
    lighting_profile = lighting_profile or {}
    show_response_preview = bool(game_assets.get("show_entity_response_texture_preview", False))
    show_attenuation_preview = bool(game_assets.get("show_entity_attenuation_preview", False))

    for item in render_items:
        base = item["base_world"]
        base_x = base["x"] - game_camera.x
        base_y = base["y"] - game_camera.y
        summary = item.get("self_shadow_summary", {})
        exposure = summary.get("face_exposure", [0.0, 0.0, 0.0, 0.0])
        source_texture = resolve_render_item_texture(item, game_assets)
        resources = resolve_entity_self_shadow_resources(item, source_texture, game_assets) if source_texture is not None else {
            "requested_mode": item.get("self_shadow", {}).get("mode", "none"), "active_mode": "none", "response_texture_name": None,
            "requested_response_texture_name": None, "fallback_used": False, "response_texture": None
        }
        pr.draw_line(int(base_x), int(base_y), int(base_x), int(base_y + 14.0), pr.YELLOW)
        footprint = g_render_order.get_world_ground_footprint(item)
        centre_x = footprint["center"]["x"] - game_camera.x
        centre_y = footprint["center"]["y"] - game_camera.y
        size = footprint["size"]
        color = pr.MAGENTA if item.get("source_id") in blocker_ids else pr.SKYBLUE

        if footprint["shape"] == "rectangle":
            pr.draw_rectangle_lines(int(centre_x - size["x"] * 0.5), int(centre_y - size["y"] * 0.5), int(size["x"]), int(size["y"]), color)
        else:
            pr.draw_ellipse_lines(int(centre_x), int(centre_y), size["x"] * 0.5, size["y"] * 0.5, color)

        basis_rectangle = get_render_item_direction_basis_world_rect(item)
        if basis_rectangle is not None:
            basis_local = item.get("self_shadow", {}).get("direction_basis", {}).get("rect", {})
            basis_x = basis_rectangle["x"] - game_camera.x
            basis_y = basis_rectangle["y"] - game_camera.y
            pr.draw_rectangle_lines(int(basis_x), int(basis_y), int(basis_rectangle["width"]), int(basis_rectangle["height"]), pr.ORANGE)
            basis_centre = {"x": basis_rectangle["x"] + basis_rectangle["width"] * 0.5, "y": basis_rectangle["y"] + basis_rectangle["height"] * 0.5}
            pr.draw_circle(int(basis_centre["x"] - game_camera.x), int(basis_centre["y"] - game_camera.y), 2.0, pr.YELLOW)
            basis_text = f"basis local={basis_local.get('x', 0.0):.0f},{basis_local.get('y', 0.0):.0f} {basis_local.get('width', 0.0):.0f}x{basis_local.get('height', 0.0):.0f} world={basis_rectangle['x']:.1f},{basis_rectangle['y']:.1f} {basis_rectangle['width']:.1f}x{basis_rectangle['height']:.1f}"
            pr.draw_text(basis_text, int(base_x + 3), int(base_y + 29), 6, pr.ORANGE)

        debug_light_id = game_assets.get("entity_lighting_debug_light_id")
        per_light_records = summary.get("per_light", [])
        selected_light_record = next((record for record in per_light_records if debug_light_id is not None and str(record.get("light_id")) == str(debug_light_id)), None)
        if selected_light_record is None:
            selected_light_record = next((record for record in per_light_records if record.get("direction_entry") is not None), None)
        if selected_light_record is not None and selected_light_record.get("direction_entry") is not None:
            entry = selected_light_record["direction_entry"]
            light_position = selected_light_record["light_position"]
            entry_world = entry["entry_world"]
            centre_world = entry["centre_world"]
            pr.draw_line(int(light_position["x"] - game_camera.x), int(light_position["y"] - game_camera.y), int(centre_world["x"] - game_camera.x), int(centre_world["y"] - game_camera.y), pr.GOLD)
            pr.draw_circle(int(entry_world["x"] - game_camera.x), int(entry_world["y"] - game_camera.y), 2.0, pr.LIME)
            weights = selected_light_record.get("weights", {})
            side_text = "inside/omni" if entry.get("inside", False) else f"{entry.get('side')} t={entry.get('side_position', 0.0):.2f}"
            detail_text = f"light={selected_light_record.get('light_id')} {side_text} DULR={weights.get('down', 0.0):.2f}/{weights.get('up', 0.0):.2f}/{weights.get('left', 0.0):.2f}/{weights.get('right', 0.0):.2f} mode={selected_light_record.get('self_shadow_mode')}"
            pr.draw_text(detail_text, int(base_x + 3), int(base_y + 22), 6, pr.GOLD)

        requested_response_name = resources.get("requested_response_texture_name")
        response_name = resources.get("response_texture_name") or (f"{requested_response_name}(unresolved)" if requested_response_name else "-")
        fallback_text = f" fallback->{resources['active_mode']}" if resources.get("fallback_used") else ""
        mode_text = f"mode={resources['active_mode']} response={response_name}{fallback_text}"
        exposure_text = f"faces RGBA={exposure[0]:.2f}/{exposure[1]:.2f}/{exposure[2]:.2f}/{exposure[3]:.2f} omni={summary.get('omni_exposure', 0.0):.2f} occ={summary.get('world_occlusion_scale', 1.0):.2f}"
        pr.draw_text(mode_text, int(base_x + 3), int(base_y + 8), 6, color)
        pr.draw_text(exposure_text, int(base_x + 3), int(base_y + 15), 6, color)

        if not show_response_preview and not show_attenuation_preview:
            continue

        source = item.get("source_rect", {})
        destination = item.get("dest_rect", {})
        source_rect = pr.Rectangle(float(source.get("x", 0.0)), float(source.get("y", 0.0)), float(source.get("width", 1.0)), float(source.get("height", 1.0)))
        preview_width = min(48.0, max(1.0, float(destination.get("width", source_rect.width))))
        preview_height = min(48.0, max(1.0, float(destination.get("height", source_rect.height))))
        preview_x = base_x + 3.0
        preview_y = base_y + 38.0

        if show_response_preview and resources.get("response_texture") is not None:
            response_destination = pr.Rectangle(preview_x, preview_y, preview_width, preview_height)
            pr.draw_texture_pro(resources["response_texture"], source_rect, response_destination, pr.Vector2(0, 0), 0, pr.WHITE)
            pr.draw_text("response RGBA", int(preview_x), int(preview_y + preview_height + 1.0), 6, color)
            preview_x += preview_width + 4.0

        shader_info = game_assets.get("shaders", {}).get("entity_self_shadow")
        if show_attenuation_preview and source_texture is not None and shader_info is not None and entity_lighting is not None and entity_readability_lighting is not None:
            attenuation_destination = pr.Rectangle(preview_x, preview_y, preview_width, preview_height)
            preview_item = item
            if selected_light_record is not None:
                preview_item = _make_per_light_render_item(item, selected_light_record)
                preview_item["self_shadow_summary"]["world_occlusion_scale"] = 0.0 if selected_light_record.get("blocked", False) else 1.0
            begin_entity_self_shadow_shader(shader_info, preview_item, source_texture, lighting_profile, entity_lighting, entity_readability_lighting, game_assets, debug_output_mode=2)
            pr.draw_texture_pro(source_texture, source_rect, attenuation_destination, pr.Vector2(0, 0), 0, pr.WHITE)
            pr.end_shader_mode()
            pr.draw_text("per-light survival", int(preview_x), int(preview_y + preview_height + 1.0), 6, color)

    for test in entity_self_shadow_frame.get("occlusion_tests", []):
        start = test["light_position"]
        end = test["target_position"]
        fraction = test["intersection_fraction"]
        intersection_x = start["x"] + (end["x"] - start["x"]) * fraction
        intersection_y = start["y"] + (end["y"] - start["y"]) * fraction
        color = pr.RED if test.get("blocked", False) else pr.LIME
        pr.draw_line(int(start["x"] - game_camera.x), int(start["y"] - game_camera.y), int(end["x"] - game_camera.x), int(end["y"] - game_camera.y), color)
        pr.draw_text(f"{'blocked' if test.get('blocked', False) else 'passed'} z={test['ray_height']:.1f}/{test['occluder_height']:.1f}", int(intersection_x - game_camera.x), int(intersection_y - game_camera.y), 6, color)

    if game_assets.get("show_entity_direct_light_preview", False) and entity_lighting is not None:
        preview_width = min(160.0, float(entity_lighting.texture.width))
        preview_height = preview_width * float(entity_lighting.texture.height) / max(1.0, float(entity_lighting.texture.width))
        pr.draw_texture_pro(entity_lighting.texture, pr.Rectangle(0, 0, entity_lighting.texture.width, -entity_lighting.texture.height), pr.Rectangle(4, 44, preview_width, preview_height), pr.Vector2(0, 0), 0, pr.WHITE)
        pr.draw_text("accumulated entity direct", 4, int(45 + preview_height), 6, pr.LIME)

def draw_entity_direction_basis_debug(render_items, game_camera, prepared_lights=None, color=None):
    """Draw direction bases and every radial light's basis-ray bundle, without text."""
    color = color or pr.ORANGE
    prepared_by_id = {prepared_light.get("id"): prepared_light for prepared_light in prepared_lights or []}
    rectangles_drawn = 0
    for item in render_items:
        rectangle = get_render_item_direction_basis_world_rect(item)
        if rectangle is None:
            continue
        pr.draw_rectangle_lines(
            int(round(rectangle["x"] - game_camera.x)),
            int(round(rectangle["y"] - game_camera.y)),
            max(1, int(round(rectangle["width"]))),
            max(1, int(round(rectangle["height"]))),
            color
        )
        centre = {"x": rectangle["x"] + rectangle["width"] * 0.5, "y": rectangle["y"] + rectangle["height"] * 0.5}
        pr.draw_circle(int(round(centre["x"] - game_camera.x)), int(round(centre["y"] - game_camera.y)), 2.0, pr.YELLOW)
        divider_line = get_render_item_profile_divider_world_line(item)
        if divider_line is not None:
            pr.draw_line(
                int(round(divider_line["top"]["x"] - game_camera.x)),
                int(round(divider_line["top"]["y"] - game_camera.y)),
                int(round(divider_line["bottom"]["x"] - game_camera.x)),
                int(round(divider_line["bottom"]["y"] - game_camera.y)),
                pr.MAGENTA
            )

        for record in item.get("self_shadow_summary", {}).get("per_light", []):
            prepared_light = prepared_by_id.get(record.get("light_id"))
            light = prepared_light.get("light", {}) if prepared_light is not None else {}
            light_type = light.get("type", "point")
            if light_type not in {"point", "spot"}:
                continue
            entry = record.get("direction_entry")
            if entry is None:
                continue
            light_position = record.get("light_position", prepared_light.get("world_position", {}) if prepared_light is not None else {})
            if "x" not in light_position or "y" not in light_position:
                continue
            bundle_rays = entry.get("rays", [])
            if bundle_rays:
                base_ray_color = pr.RED if record.get("blocked", False) else pr.GOLD if light_type == "spot" or light.get("owner_id") == "player" or "flashlight" in str(record.get("light_id", "")).lower() else pr.SKYBLUE
                for ray in bundle_rays:
                    sample_world = ray.get("world", {})
                    entry_world = ray.get("entry_world", {})
                    if "x" not in sample_world or "y" not in sample_world or "x" not in entry_world or "y" not in entry_world:
                        continue
                    ray_color = base_ray_color if ray.get("active", False) or record.get("blocked", False) else pr.DARKGRAY
                    pr.draw_line(
                        int(round(light_position["x"] - game_camera.x)),
                        int(round(light_position["y"] - game_camera.y)),
                        int(round(sample_world["x"] - game_camera.x)),
                        int(round(sample_world["y"] - game_camera.y)),
                        ray_color
                    )
                    pr.draw_circle(int(round(entry_world["x"] - game_camera.x)), int(round(entry_world["y"] - game_camera.y)), 1.0, ray_color)
                continue
            centre_world = entry.get("centre_world", centre)
            entry_world = entry.get("entry_world")
            if not isinstance(entry_world, dict):
                continue
            light_id = str(record.get("light_id", "?"))
            is_flashlight = light_type == "spot" or light.get("owner_id") == "player" or "flashlight" in light_id.lower()
            ray_color = pr.RED if record.get("blocked", False) else pr.GOLD if is_flashlight else pr.SKYBLUE
            pr.draw_line(
                int(round(light_position["x"] - game_camera.x)),
                int(round(light_position["y"] - game_camera.y)),
                int(round(centre_world["x"] - game_camera.x)),
                int(round(centre_world["y"] - game_camera.y)),
                ray_color
            )
            pr.draw_circle(int(round(entry_world["x"] - game_camera.x)), int(round(entry_world["y"] - game_camera.y)), 2.0, ray_color)
        rectangles_drawn += 1
    return rectangles_drawn

def get_render_item_shadow_sprite_info(render_item, game_assets):
    texture = resolve_render_item_texture(render_item, game_assets)
    if texture is None:
        return None
    source = render_item.get("source_rect", {})
    return {
        "texture": texture,
        "source_rect": pr.Rectangle(float(source.get("x", 0.0)), float(source.get("y", 0.0)), float(source.get("width", texture.width)), float(source.get("height", texture.height))),
        "base_world": dict(render_item.get("base_world", {})),
        "sprite_width": float(render_item.get("dest_rect", {}).get("width", source.get("width", texture.width))),
        "sprite_height": float(render_item.get("dest_rect", {}).get("height", source.get("height", texture.height))),
        "visual_height": float(render_item.get("visual_height", source.get("height", texture.height)))
    }

def draw_textured_quad(texture, source_rect, far_left, far_right, near_right, near_left):
    texture_width = max(1.0, float(texture.width))
    texture_height = max(1.0, float(texture.height))
    u_left = source_rect.x / texture_width
    u_right = (source_rect.x + source_rect.width) / texture_width
    v_top = source_rect.y / texture_height
    v_bottom = (source_rect.y + source_rect.height) / texture_height
    pr.rl_begin(pr.RL_TRIANGLES)
    pr.rl_set_texture(texture.id)
    
    pr.rl_color4ub(255, 255, 255, 255)

    pr.rl_tex_coord2f(u_left, v_top)
    pr.rl_vertex2f(far_left["x"], far_left["y"])
    pr.rl_tex_coord2f(u_left, v_bottom)
    pr.rl_vertex2f(near_left["x"], near_left["y"])
    pr.rl_tex_coord2f(u_right, v_bottom)
    pr.rl_vertex2f(near_right["x"], near_right["y"])

    pr.rl_tex_coord2f(u_left, v_top)
    pr.rl_vertex2f(far_left["x"], far_left["y"])
    pr.rl_tex_coord2f(u_right, v_bottom)
    pr.rl_vertex2f(near_right["x"], near_right["y"])
    pr.rl_tex_coord2f(u_right, v_top)
    pr.rl_vertex2f(far_right["x"], far_right["y"])

    pr.rl_end()
    pr.rl_set_texture(0)

def build_cinematic_shadow_frame_data(render_items, game_assets, prepared_flashlight):
    if prepared_flashlight is None or not prepared_flashlight.get("casts_cinematic_shadows", False):
        return None

    flashlight = prepared_flashlight["light"]
    flashlight_position = prepared_flashlight["world_position"]
    light_height = max(0.0, float(flashlight.get("height", 22.0)))
    visibility_light = flashlight
    visibility_polygon = prepared_flashlight.get("cinematic_visibility_polygon") or prepared_flashlight.get("visibility_polygon") or []
    visibility_area = [flashlight_position] + visibility_polygon if flashlight.get("type") == "spot" else visibility_polygon
    shadows = []
    skipped = []

    for render_item in render_items:
        source_id = render_item.get("source_id", str(render_item.get("id")))
        shadow_settings = render_item.get("shadow", {})
        shadow_mode = shadow_settings.get("mode", "none")
        if not shadow_settings.get("enabled", True):
            skipped.append({"source_id": source_id, "reason": "disabled"})
            continue
        if shadow_mode == "none":
            skipped.append({"source_id": source_id, "reason": "shadow mode none"})
            continue
        cast_height = max(0.0, float(shadow_settings.get("cast_height", render_item.get("visual_height", 0.0))))
        if cast_height <= 0.0001:
            skipped.append({"source_id": source_id, "reason": "zero/invalid height"})
            continue
        sprite_info = get_render_item_shadow_sprite_info(render_item, game_assets)
        if sprite_info is None:
            skipped.append({"source_id": source_id, "reason": "missing texture/frame"})
            continue
        shadow_quad = build_cinematic_shadow_quad(sprite_info, shadow_settings, flashlight_position, light_height)
        if shadow_quad is None:
            skipped.append({"source_id": source_id, "reason": "invalid projection"})
            continue
        floor_anchor = shadow_quad["floor_anchor"]
        distance_from_light = game.vec2_distance(floor_anchor, flashlight_position)
        if distance_from_light > max(0.0, float(shadow_settings.get("max_light_distance", 180.0))):
            skipped.append({"source_id": source_id, "reason": "outside light radius"})
            continue
        if distance_from_light > max(0.0, float(flashlight.get("radius", 180.0))):
            skipped.append({"source_id": source_id, "reason": "outside light radius"})
            continue
        flashlight_strength = light_visibility.get_unoccluded_light_strength_at_world_point(flashlight, floor_anchor, {"tile_width": 1, "tile_height": 1})
        if flashlight_strength <= 0.0:
            skipped.append({"source_id": source_id, "reason": "outside cone"})
            continue
        if not point_in_polygon(floor_anchor, visibility_area):
            skipped.append({"source_id": source_id, "reason": "behind tile wall"})
            continue
        shadow_opacity = max(0.0, min(1.0, float(shadow_settings.get("opacity", 0.58))))
        if shadow_settings.get("fade_with_light_strength", True):
            shadow_opacity *= flashlight_strength
        shadows.append({
            "render_item": render_item,
            "sprite_info": sprite_info,
            "settings": shadow_settings,
            "quad": shadow_quad,
            "opacity": shadow_opacity
        })

    return {
        "flashlight": flashlight,
        "flashlight_position": flashlight_position,
        "visibility_light": visibility_light,
        "visibility_polygon": visibility_polygon,
        "shadows": shadows,
        "skipped": skipped,
        "light_height": light_height
    }

def draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, light_shader, include_receivers=True, shader_mode_active=False, clip_to_wall_visibility=True):
    light = prepared_light["light"]

    if not light.get("enabled", True):
        return

    radius = max(1.0, float(light.get("radius", 100.0)))
    intensity = max(0.0, float(light.get("intensity", 1.0)))
    falloff = max(0.0001, float(light.get("falloff", 2.0)))
    near_fade_distance = max(0.0, float(light.get("near_fade_distance", 0.0)))

    world_position = prepared_light["world_position"]
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y

    target_width = lighting_target.texture.width
    target_height = lighting_target.texture.height

    if screen_x + radius < 0 or screen_y + radius < 0 or screen_x - radius >= target_width or screen_y - radius >= target_height:
        return

    direction = game.vec2_normalize(light.get("direction", {"x": 1.0, "y": 0.0}))

    if game.vec2_norm(direction) == 0:
        direction = {"x": 1.0, "y": 0.0}

    red, green, blue = normalize_light_color(light.get("color", [1.0, 1.0, 1.0]))
    inner_angle = float(light.get("inner_angle", 20.0))
    outer_angle = max(inner_angle + 0.001, float(light.get("outer_angle", 35.0)))
    inner_cone_cos = math.cos(math.radians(inner_angle))
    outer_cone_cos = math.cos(math.radians(outer_angle))
    light_type = 1 if light.get("type", "point") == "spot" else 0
    shader = light_shader["shader"]

    set_shader_vec2(shader, light_shader["resolution_location"], target_width, target_height)
    set_shader_vec2(shader, light_shader["light_position_location"], screen_x, screen_y)
    set_shader_vec2(shader, light_shader["light_direction_location"], direction["x"], direction["y"])
    set_shader_vec3(shader, light_shader["light_color_location"], red, green, blue)
    set_shader_float(shader, light_shader["radius_location"], radius)
    set_shader_float(shader, light_shader["intensity_location"], intensity)
    set_shader_float(shader, light_shader["falloff_location"], falloff)
    set_shader_float(shader, light_shader["near_fade_distance_location"], near_fade_distance)
    set_shader_float(shader, light_shader["inner_cone_cos_location"], inner_cone_cos)
    set_shader_float(shader, light_shader["outer_cone_cos_location"], outer_cone_cos)
    set_shader_int(shader, light_shader["light_type_location"], light_type)

    if not shader_mode_active:
        pr.begin_shader_mode(shader)

    if prepared_light["casts_wall_shadows"] and clip_to_wall_visibility:
        draw_light_visibility_polygon(light, world_position, prepared_light["visibility_polygon"], game_camera)

        if include_receivers:
            draw_receiver_polygons(prepared_light["receiver_polygons"], game_camera)
    else:
        draw_x = int(screen_x - radius)
        draw_y = int(screen_y - radius)
        draw_size = int(math.ceil(radius * 2.0))
        pr.draw_rectangle(draw_x, draw_y, draw_size, draw_size, pr.WHITE)

    if not shader_mode_active:
        pr.end_shader_mode()

def draw_prepared_top_down_light_to_target(prepared_light, game_camera, lighting_target, top_down_shader, shader_mode_active=False):
    light = prepared_light["light"]

    if not light.get("enabled", True):
        return

    world_position = prepared_light["world_position"]
    size = light.get("size", {})
    width = max(0.0, float(size.get("x", 0.0)))
    height = max(0.0, float(size.get("y", 0.0)))
    intensity = max(0.0, float(light.get("intensity", 1.0)))
    edge_softness = max(0.0, float(light.get("edge_softness", 0.0)))
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y
    area_min_x = screen_x - width * 0.5
    area_min_y = screen_y - height * 0.5
    area_max_x = screen_x + width * 0.5
    area_max_y = screen_y + height * 0.5
    target_width = lighting_target.texture.width
    target_height = lighting_target.texture.height

    if area_max_x < 0 or area_max_y < 0 or area_min_x >= target_width or area_min_y >= target_height:
        return

    red, green, blue = normalize_light_color(light.get("color", [1.0, 1.0, 1.0]))
    shader = top_down_shader["shader"]

    set_shader_vec2(shader, top_down_shader["resolution_location"], target_width, target_height)
    set_shader_vec2(shader, top_down_shader["area_min_location"], area_min_x, area_min_y)
    set_shader_vec2(shader, top_down_shader["area_max_location"], area_max_x, area_max_y)
    set_shader_vec3(shader, top_down_shader["light_color_location"], red, green, blue)
    set_shader_float(shader, top_down_shader["intensity_location"], intensity)
    set_shader_float(shader, top_down_shader["edge_softness_location"], edge_softness)

    if not shader_mode_active:
        pr.begin_shader_mode(shader)
    pr.draw_rectangle(0, 0, target_width, target_height, pr.WHITE)
    if not shader_mode_active:
        pr.end_shader_mode()

def draw_prepared_light_to_target(prepared_light, game_camera, lighting_target, game_assets, include_receivers=True, clip_to_wall_visibility=True):
    if prepared_light["light"].get("type", "point") == "top_down":
        draw_prepared_top_down_light_to_target(prepared_light, game_camera, lighting_target, game_assets["shaders"]["top_down_light"])
        return

    draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, game_assets["shaders"]["light_accumulation"], include_receivers, clip_to_wall_visibility=clip_to_wall_visibility)

def draw_ringed_circular_light(x, y, rings, ring_size, ring_radius, red, green, blue, base_alpha, alpha_multiplier):    
    for i in range(rings, 0,-ring_size):
        t = i / rings
        radius = ring_radius * t
        strength = 1.0 - t
        alpha = int(base_alpha+ strength*alpha_multiplier)
        pr.draw_circle(int(x), int(y), radius, pr.Color(red,green,blue,alpha))

def render_prepared_lights_to_target(prepared_lights, game_camera, lighting_target, game_assets, target_kind, render_style=None):
    if target_kind not in {"world", "entities", "fog"}:
        raise ValueError(f"unknown prepared light target kind: {target_kind}")

    draw_started = time.perf_counter()
    pr.begin_texture_mode(lighting_target)
    pr.clear_background(pr.BLACK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)

    capability = {"world": "affects_world", "entities": "affects_entities", "fog": "affects_fog"}[target_kind]

    target_lights = [prepared_light for prepared_light in prepared_lights if prepared_light[capability]]

    if render_style is not None:
        target_lights = [prepared_light for prepared_light in target_lights if prepared_light["light"].get("render_style", "world") == render_style]
    radial_lights = [prepared_light for prepared_light in target_lights if prepared_light["light"].get("type", "point") != "top_down"]
    top_down_lights = [prepared_light for prepared_light in target_lights if prepared_light["light"].get("type", "point") == "top_down"]

    if radial_lights:
        light_shader = game_assets["shaders"]["light_accumulation"]
        pr.begin_shader_mode(light_shader["shader"])

        for prepared_light in radial_lights:
            pr.rl_draw_render_batch_active()
            draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, light_shader, target_kind == "world", True)

        pr.end_shader_mode()

    if top_down_lights:
        top_down_shader = game_assets["shaders"]["top_down_light"]
        pr.begin_shader_mode(top_down_shader["shader"])

        for prepared_light in top_down_lights:
            pr.rl_draw_render_batch_active()
            draw_prepared_top_down_light_to_target(prepared_light, game_camera, lighting_target, top_down_shader, True)

        pr.end_shader_mode()

    pr.end_blend_mode()
    pr.end_texture_mode()
    return (time.perf_counter() - draw_started) * 1000.0

def render_prepared_lighting(lighting_frame, game_camera, lighting_target, game_assets):
    fog_light_target = get_or_create_render_target(game_assets, "fog_light", lighting_target.texture.width, lighting_target.texture.height)
    readability_light_target = get_or_create_render_target(game_assets, "readability_light", lighting_target.texture.width, lighting_target.texture.height)
    entity_readability_light_target = get_or_create_render_target(game_assets, "entity_readability_light", lighting_target.texture.width, lighting_target.texture.height)
    lighting_frame["stats"]["fog_draw_time_ms"] = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, fog_light_target, game_assets, "fog")
    world_draw_time = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, lighting_target, game_assets, "world", "world")
    readability_draw_time = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, readability_light_target, game_assets, "world", "readability")
    entity_readability_draw_time = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, entity_readability_light_target, game_assets, "entities", "readability")
    lighting_frame["stats"]["scene_draw_time_ms"] = world_draw_time + readability_draw_time
    lighting_frame["stats"]["entity_draw_time_ms"] = entity_readability_draw_time
    return fog_light_target, readability_light_target, None, entity_readability_light_target

def draw_lighting_stats_debug(stats, x=4, y=4):
    cache_lookups = stats.get("visibility_cache_hits", 0) + stats.get("visibility_cache_misses", 0)
    cache_rate = stats.get("visibility_cache_hits", 0) / max(1, cache_lookups) * 100.0
    lines = [
        f"lights {stats.get('active_light_count', 0)} shadowed {stats.get('shadowed_radial_light_count', 0)}",
        f"cache {cache_rate:.0f}% rebuilds {stats.get('visibility_rebuilds', 0)}",
        f"rays {stats.get('total_visibility_rays', 0)} dda {stats.get('total_dda_tile_steps', 0)}",
        f"entity scratch {stats.get('entity_scratch_light_draws', 0)} survival {stats.get('entity_survival_draws', 0)}",
        f"prep {stats.get('prepare_time_ms', 0.0):.2f}ms entity {stats.get('entity_prepare_time_ms', 0.0):.2f}ms draw {stats.get('scene_draw_time_ms', 0.0) + stats.get('entity_draw_time_ms', 0.0) + stats.get('fog_draw_time_ms', 0.0):.2f}ms"
    ]

    for line_index, line in enumerate(lines):
        pr.draw_text(line, x, y + line_index * 10, 8, pr.LIME)

# Retired all-segments reference implementation. Production lighting uses
# g_light_visibility DDA through prepare_lighting_frame().
def legacy_all_segments_cross_2d(a, b):
    return a["x"] * b["y"] - a["y"] * b["x"]

def legacy_all_segments_normalize_angle_signed(angle):
    return (angle + math.pi) % (math.pi * 2.0) - math.pi

def legacy_all_segments_ray_segment_intersection_distance(origin, direction, segment_start, segment_end):
    segment_direction = game.vec2_subtract(segment_end, segment_start)
    denominator = legacy_all_segments_cross_2d(direction, segment_direction)

    if abs(denominator) < 0.0000001:
        return None

    origin_to_segment = game.vec2_subtract(segment_start, origin)
    ray_distance = legacy_all_segments_cross_2d(origin_to_segment, segment_direction) / denominator
    segment_amount = legacy_all_segments_cross_2d(origin_to_segment, direction) / denominator

    if ray_distance < 0.0001:
        return None

    if segment_amount < -0.000001 or segment_amount > 1.000001:
        return None

    return ray_distance

def legacy_all_segments_tile_shape_local_vertices(shape_index, tile_width, tile_height):
    if shape_index == 0:
        return [
            {"x": 0.0, "y": 0.0},
            {"x": float(tile_width), "y": 0.0},
            {"x": float(tile_width), "y": float(tile_height)},
            {"x": 0.0, "y": float(tile_height)}
        ]

    if shape_index == 1:
        return [
            {"x": 0.0, "y": 0.0},
            {"x": float(tile_width), "y": 0.0},
            {"x": 0.0, "y": float(tile_height)}
        ]

    if shape_index == 2:
        return [
            {"x": 0.0, "y": 0.0},
            {"x": float(tile_width), "y": 0.0},
            {"x": float(tile_width), "y": float(tile_height)}
        ]

    if shape_index == 3:
        return [
            {"x": float(tile_width), "y": 0.0},
            {"x": float(tile_width), "y": float(tile_height)},
            {"x": 0.0, "y": float(tile_height)}
        ]

    if shape_index == 4:
        return [
            {"x": 0.0, "y": 0.0},
            {"x": float(tile_width), "y": float(tile_height)},
            {"x": 0.0, "y": float(tile_height)}
        ]

    return []

def legacy_all_segments_get_nearby_tile_occluders(light_position, radius, tile_map):
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]

    min_tile_x = max(0, math.floor((light_position["x"] - radius) / tile_width) - 1)
    max_tile_x = min(map_width - 1, math.floor((light_position["x"] + radius) / tile_width) + 1)
    min_tile_y = max(0, math.floor((light_position["y"] - radius) / tile_height) - 1)
    max_tile_y = min(map_height - 1, math.floor((light_position["y"] + radius) / tile_height) + 1)

    occluders = []

    for tile_y in range(min_tile_y, max_tile_y + 1):
        for tile_x in range(min_tile_x, max_tile_x + 1):
            tile = tile_map["tiles"][tile_y * map_width + tile_x]
            tile_type = tile_map["tile_types"][tile.get("index", 0)]

            if not game.tile_type_is_collidable(tile_type.get("type", "")):
                continue

            local_vertices = legacy_all_segments_tile_shape_local_vertices(tile.get("shape_index", 0), tile_width, tile_height)
            world_vertices = []

            for vertex in local_vertices:
                world_vertices.append({
                    "x": tile_x * tile_width + vertex["x"],
                    "y": tile_y * tile_height + vertex["y"]
                })

            segments = []

            for vertex_index in range(len(world_vertices)):
                segments.append({
                    "start": world_vertices[vertex_index],
                    "end": world_vertices[(vertex_index + 1) % len(world_vertices)]
                })

            occluders.append({
                "tile_x": tile_x,
                "tile_y": tile_y,
                "vertices": world_vertices,
                "segments": segments
            })

    return occluders

def legacy_all_segments_ray_occluder_entry_exit_distances(origin, direction, occluder):
    intersection_distances = []

    for segment in occluder["segments"]:
        intersection_distance = legacy_all_segments_ray_segment_intersection_distance(origin, direction, segment["start"], segment["end"])

        if intersection_distance is not None:
            intersection_distances.append(intersection_distance)

    if not intersection_distances:
        return None

    return {
        "entry": min(intersection_distances),
        "exit": max(intersection_distances)
    }

def legacy_all_segments_ray_first_occluder_entry_distance(origin, direction, radius, occluders):
    closest_entry_distance = radius
    found_occluder = False
    minimum_interval_size = 0.0001

    for occluder in occluders:
        intersection = legacy_all_segments_ray_occluder_entry_exit_distances(origin, direction, occluder)

        if intersection is None:
            continue

        entry_distance = intersection["entry"]
        exit_distance = intersection["exit"]

        # Ignore rays that merely graze one corner.
        if exit_distance - entry_distance <= minimum_interval_size:
            continue

        if entry_distance < closest_entry_distance and entry_distance <= radius:
            closest_entry_distance = entry_distance
            found_occluder = True

    if not found_occluder:
        return None

    return closest_entry_distance

def legacy_all_segments_ray_first_solid_run_exit_distance(origin, direction, radius, occluders):
    intervals = []
    merge_epsilon = 0.001
    minimum_interval_size = 0.0001

    for occluder in occluders:
        intersection = legacy_all_segments_ray_occluder_entry_exit_distances(origin, direction, occluder)

        if intersection is None:
            continue

        entry_distance = intersection["entry"]
        exit_distance = intersection["exit"]

        if entry_distance > radius:
            continue

        exit_distance = min(exit_distance, radius)

        # A single corner touch should not behave as though the ray
        # travelled through a solid object.
        if exit_distance - entry_distance <= minimum_interval_size:
            continue

        intervals.append({
            "entry": entry_distance,
            "exit": exit_distance
        })

    if not intervals:
        return None

    intervals.sort(key=lambda interval: interval["entry"])

    first_run_entry = intervals[0]["entry"]
    first_run_exit = intervals[0]["exit"]

    for interval in intervals[1:]:
        # This solid begins before, or effectively exactly where,
        # the current solid run ends. Treat them as one wall mass.
        if interval["entry"] <= first_run_exit + merge_epsilon:
            first_run_exit = max(first_run_exit, interval["exit"])
            continue

        # There is empty space before this next occluder, so it is
        # genuinely behind the first wall and must remain shadowed.
        break

    return {
        "entry": first_run_entry,
        "exit": first_run_exit
    }

def legacy_all_segments_get_visibility_ray_angles(light, light_position, occluders):
    light_type = light.get("type", "point")
    endpoint_epsilon = 0.0005

    if light_type == "spot":
        direction = game.vec2_normalize(light.get("direction", {"x": 1.0, "y": 0.0}))

        if game.vec2_norm(direction) == 0:
            direction = {"x": 1.0, "y": 0.0}

        centre_angle = math.atan2(direction["y"], direction["x"])
        outer_angle = math.radians(float(light.get("outer_angle", 35.0)))
        ray_deltas = []
        seen_deltas = set()
        baseline_ray_count = 32

        def add_delta(delta):
            if delta < -outer_angle or delta > outer_angle:
                return

            key = round(delta, 7)

            if key not in seen_deltas:
                seen_deltas.add(key)
                ray_deltas.append(delta)

        for ray_index in range(baseline_ray_count + 1):
            amount = ray_index / baseline_ray_count
            add_delta(-outer_angle + amount * outer_angle * 2.0)

        for occluder in occluders:
            for vertex in occluder["vertices"]:
                vertex_angle = math.atan2(vertex["y"] - light_position["y"], vertex["x"] - light_position["x"])
                vertex_delta = legacy_all_segments_normalize_angle_signed(vertex_angle - centre_angle)

                add_delta(vertex_delta - endpoint_epsilon)
                add_delta(vertex_delta)
                add_delta(vertex_delta + endpoint_epsilon)

        ray_deltas.sort()
        return [centre_angle + delta for delta in ray_deltas]

    ray_angles = []
    seen_angles = set()
    baseline_ray_count = 64

    def add_angle(angle):
        normalized_angle = angle % (math.pi * 2.0)
        key = round(normalized_angle, 7)

        if key not in seen_angles:
            seen_angles.add(key)
            ray_angles.append(normalized_angle)

    for ray_index in range(baseline_ray_count):
        add_angle((ray_index / baseline_ray_count) * math.pi * 2.0)

    for occluder in occluders:
        for vertex in occluder["vertices"]:
            vertex_angle = math.atan2(vertex["y"] - light_position["y"], vertex["x"] - light_position["x"])

            add_angle(vertex_angle - endpoint_epsilon)
            add_angle(vertex_angle)
            add_angle(vertex_angle + endpoint_epsilon)

    ray_angles.sort()
    return ray_angles

def legacy_all_segments_build_light_visibility_polygon(light, light_position, radius, occluders):
    ray_angles = legacy_all_segments_get_visibility_ray_angles(light, light_position, occluders)
    shadow_bias = max(0.0, float(light.get("shadow_bias", 0.25)))
    polygon = []

    for ray_angle in ray_angles:
        ray_direction = {"x": math.cos(ray_angle), "y": math.sin(ray_angle)}
        first_entry_distance = legacy_all_segments_ray_first_occluder_entry_distance(light_position, ray_direction, radius, occluders)
        ray_distance = radius

        if first_entry_distance is not None:
            ray_distance = max(0.0, first_entry_distance - shadow_bias)

        polygon.append({
            "x": light_position["x"] + ray_direction["x"] * ray_distance,
            "y": light_position["y"] + ray_direction["y"] * ray_distance
        })

    return polygon

def draw_occluder_light_receiver(occluder, game_camera):
    world_vertices = occluder.get("vertices", [])

    if len(world_vertices) < 3:
        return

    screen_vertices = []

    for vertex in world_vertices:
        screen_vertices.append(pr.Vector2(vertex["x"] - game_camera.x, vertex["y"] - game_camera.y))

    first_vertex = screen_vertices[0]

    for vertex_index in range(1, len(screen_vertices) - 1):
        current_vertex = screen_vertices[vertex_index]
        next_vertex = screen_vertices[vertex_index + 1]

        # The stored vertices are clockwise in the game's
        # screen-down coordinate system, so reverse the final two.
        pr.draw_triangle(first_vertex, next_vertex, current_vertex, pr.WHITE)

def draw_tile_light_receivers(occluders, game_camera):
    for occluder in occluders:
        if not occluder.get("receives_light", True):
            continue

        draw_occluder_light_receiver(occluder, game_camera)

def draw_receiver_polygons(receiver_polygons, game_camera):
    triangle_strip = []

    for polygon in receiver_polygons:
        if len(polygon) < 3:
            continue

        first = (polygon[0]["x"] - game_camera.x, polygon[0]["y"] - game_camera.y)

        for vertex_index in range(1, len(polygon) - 1):
            current = (polygon[vertex_index]["x"] - game_camera.x, polygon[vertex_index]["y"] - game_camera.y)
            next_vertex = (polygon[vertex_index + 1]["x"] - game_camera.x, polygon[vertex_index + 1]["y"] - game_camera.y)
            triangle = (first, next_vertex, current)

            if triangle_strip:
                triangle_strip.extend((triangle_strip[-1], triangle[0], triangle[0], triangle[1], triangle[2]))
            else:
                triangle_strip.extend(triangle)

    if triangle_strip:
        point_array = pr.ffi.new("Vector2[]", triangle_strip)
        pr.draw_triangle_strip(pr.ffi.cast("Vector2 *", point_array), len(triangle_strip), pr.WHITE)

def draw_light_visibility_polygon(light, light_position, polygon, game_camera):
    if len(polygon) < 2:
        return

    screen_points = [(light_position["x"] - game_camera.x, light_position["y"] - game_camera.y)]
    screen_points.extend((point["x"] - game_camera.x, point["y"] - game_camera.y) for point in reversed(polygon))

    if light.get("type", "point") == "point" and len(polygon) >= 3:
        screen_points.append(screen_points[1])

    point_array = pr.ffi.new("Vector2[]", screen_points)
    pr.draw_triangle_fan(pr.ffi.cast("Vector2 *", point_array), len(screen_points), pr.WHITE)

def world_point_to_screen(point, game_camera):
    return {"x": point["x"] - game_camera.x, "y": point["y"] - game_camera.y}

def render_cinematic_shadow_visibility_mask(frame_data, game_camera, visibility_target):
    pr.begin_texture_mode(visibility_target)
    pr.clear_background(pr.BLACK)
    draw_light_visibility_polygon(frame_data["visibility_light"], frame_data["flashlight_position"], frame_data["visibility_polygon"], game_camera)
    pr.end_texture_mode()

def render_cinematic_shadow_raw(frame_data, game_camera, raw_target, projection_shader):
    shader = projection_shader["shader"]

    pr.begin_texture_mode(raw_target)
    pr.clear_background(pr.BLANK)

    for shadow in frame_data["shadows"]:
        sprite_info = shadow["sprite_info"]
        shadow_settings = shadow["settings"]
        shadow_quad = shadow["quad"]
        red, green, blue = normalize_light_color(shadow_settings.get("color", [0.008, 0.004, 0.018]))
        set_shader_vec3(shader, projection_shader["shadow_color_location"], red, green, blue)
        set_shader_float(shader, projection_shader["shadow_opacity_location"], shadow["opacity"])
        set_shader_float(shader, projection_shader["alpha_cutoff_location"], 0.02)
        far_left = world_point_to_screen(shadow_quad["far_left"], game_camera)
        far_right = world_point_to_screen(shadow_quad["far_right"], game_camera)
        near_right = world_point_to_screen(shadow_quad["near_right"], game_camera)
        near_left = world_point_to_screen(shadow_quad["near_left"], game_camera)

        pr.begin_shader_mode(shader)
        draw_textured_quad(sprite_info["texture"], sprite_info["source_rect"], far_left, far_right, near_right, near_left)
        pr.end_shader_mode()

    pr.end_texture_mode()

def apply_cinematic_shadow_composite(scene, raw_target, visibility_target, composite_target, composite_shader):
    width = scene.texture.width
    height = scene.texture.height
    shader = composite_shader["shader"]
    source = pr.Rectangle(0, 0, width, -height)
    destination = pr.Rectangle(0, 0, width, height)

    pr.begin_texture_mode(composite_target)
    pr.clear_background(pr.BLACK)
    pr.begin_shader_mode(shader)

    # Additional sampler textures must be rebound after BeginShaderMode().
    set_shader_texture(shader, composite_shader["shadow_texture_location"], raw_target.texture)
    set_shader_texture(shader, composite_shader["visibility_texture_location"], visibility_target.texture)
    pr.draw_texture_pro(scene.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)

    pr.end_shader_mode()
    pr.end_texture_mode()

    pr.begin_texture_mode(scene)
    pr.clear_background(pr.BLACK)
    pr.draw_texture_pro(composite_target.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()

def render_and_apply_cinematic_entity_shadows(scene, game_camera, render_items, game_assets, prepared_flashlight):
    frame_data = build_cinematic_shadow_frame_data(render_items, game_assets, prepared_flashlight)

    if frame_data is None:
        return

    width = scene.texture.width
    height = scene.texture.height
    raw_target = get_or_create_render_target(game_assets, "cinematic_shadow_raw", width, height)
    visibility_target = get_or_create_render_target(game_assets, "cinematic_shadow_visibility", width, height)
    composite_target = get_or_create_render_target(game_assets, "cinematic_shadow_composite", width, height)

    render_cinematic_shadow_visibility_mask(frame_data, game_camera, visibility_target)
    render_cinematic_shadow_raw(frame_data, game_camera, raw_target, game_assets["shaders"]["cinematic_shadow_projection"])
    apply_cinematic_shadow_composite(scene, raw_target, visibility_target, composite_target, game_assets["shaders"]["cinematic_shadow_composite"])

def draw_cinematic_shadow_debug(game_camera, render_items, game_assets, prepared_flashlight):
    frame_data = build_cinematic_shadow_frame_data(render_items, game_assets, prepared_flashlight)

    if frame_data is None:
        return

    visibility_color = pr.Color(80, 180, 255, 220)
    quad_color = pr.Color(210, 110, 255, 230)
    near_color = pr.Color(255, 220, 70, 255)
    far_color = pr.Color(255, 90, 90, 255)
    flashlight_screen = world_point_to_screen(frame_data["flashlight_position"], game_camera)
    visibility_points = [world_point_to_screen(point, game_camera) for point in frame_data["visibility_polygon"]]

    if visibility_points:
        previous = flashlight_screen

        for point in visibility_points:
            pr.draw_line_ex(pr.Vector2(previous["x"], previous["y"]), pr.Vector2(point["x"], point["y"]), 1.0, visibility_color)
            previous = point

        pr.draw_line_ex(pr.Vector2(previous["x"], previous["y"]), pr.Vector2(flashlight_screen["x"], flashlight_screen["y"]), 1.0, visibility_color)

    for shadow in frame_data["shadows"]:
        quad = shadow["quad"]
        points = [quad["near_left"], quad["near_right"], quad["far_right"], quad["far_left"]]

        for index, point in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            screen_point = world_point_to_screen(point, game_camera)
            next_screen_point = world_point_to_screen(next_point, game_camera)
            pr.draw_line_ex(pr.Vector2(screen_point["x"], screen_point["y"]), pr.Vector2(next_screen_point["x"], next_screen_point["y"]), 1.0, quad_color)

        near_center = world_point_to_screen(quad["near_center"], game_camera)
        far_center = world_point_to_screen(quad["far_center"], game_camera)
        pr.draw_circle(int(near_center["x"]), int(near_center["y"]), 2.0, near_color)
        pr.draw_circle(int(far_center["x"]), int(far_center["y"]), 2.0, far_color)
        pr.draw_text(f"{shadow['render_item'].get('source_id')} {shadow['settings'].get('mode')} h={quad['cast_height']:.0f}/{quad['light_height']:.0f} len={quad['length']:.0f}", int(near_center["x"] + 3), int(near_center["y"] + 3), 7, quad_color)

    for index, skipped in enumerate(frame_data.get("skipped", [])):
        pr.draw_text(f"shadow skip {skipped['source_id']}: {skipped['reason']}", 4, 44 + index * 8, 6, pr.ORANGE)

def get_player_flashlight_settings(player_entity):
    facing = player_entity.get("animation_direction", "down")

    # this can cause an issue with our new lighting system
    # settings = {
    #     "up": {"forward_offset": 10.0, "side_offset": -2.0, "near_fade_distance": 18.0},
    #     "down": {"forward_offset": 3.0, "side_offset": 2.0, "near_fade_distance": 10.0},
    #     "left": {"forward_offset": 4.0, "side_offset": -1.0, "near_fade_distance": 14.0},
    #     "right": {"forward_offset": 4.0, "side_offset": 1.0, "near_fade_distance": 14.0}
    # }

    settings = {
        "up": {"forward_offset": 10.0, "side_offset": 0.0, "near_fade_distance": 18.0},
        "down": {"forward_offset": 10.0, "side_offset": 0.0, "near_fade_distance": 18.0},
        "left": {"forward_offset": 10.0, "side_offset": 0.0, "near_fade_distance": 18.0},
        "right": {"forward_offset": 10.0, "side_offset":    0.0, "near_fade_distance": 18.0}
    }

    return settings.get(facing, settings["down"])

def light_timer_oscilate(t):
    slow = math.sin(t / 100) * 20
    med = math.sin(t / 10) * 5
    fast =  math.sin(t / 2) *10
    result = slow + med + fast
    return result

def apply_lighting(scene, lighting, readability_lighting, game_assets, lighting_profile, preserve_transparency=False):
    width = scene.texture.width
    height = scene.texture.height

    composite_target = get_or_create_render_target(game_assets, "lighting_composite", width, height)
    composite_shader = game_assets["shaders"]["lighting_composite"]
    shader = composite_shader["shader"]

    ambient_red, ambient_green, ambient_blue = normalize_light_color(lighting_profile.get("ambient_color", [0.2, 0.2, 0.3]))
    shadow_red, shadow_green, shadow_blue = normalize_light_color(lighting_profile.get("shadow_color", [0.0, 0.0, 0.0]))

    set_shader_vec3(shader, composite_shader["ambient_color_location"], ambient_red, ambient_green, ambient_blue)
    set_shader_vec3(shader, composite_shader["shadow_color_location"], shadow_red, shadow_green, shadow_blue)
    set_shader_float(shader, composite_shader["ambient_strength_location"], lighting_profile.get("ambient_strength", 0.3))
    set_shader_float(shader, composite_shader["direct_light_strength_location"], lighting_profile.get("direct_light_strength", 1.0))
    set_shader_float(shader, composite_shader["black_point_location"], lighting_profile.get("black_point", 0.1))
    set_shader_float(shader, composite_shader["shadow_softness_location"], lighting_profile.get("shadow_softness", 0.03))
    set_shader_float(shader, composite_shader["shadow_detail_location"], lighting_profile.get("shadow_detail", 0.0))
    set_shader_float(shader, composite_shader["contrast_location"], lighting_profile.get("contrast", 1.0))
    set_shader_float(shader, composite_shader["light_posterize_enabled_location"], 1.0 if lighting_profile.get("light_posterize_enabled", True) else 0.0)
    set_shader_float(shader, composite_shader["light_posterize_levels_location"], lighting_profile.get("light_posterize_levels", 12.0))
    set_shader_float(shader, composite_shader["light_dither_enabled_location"], 1.0 if lighting_profile.get("light_dither_enabled", False) else 0.0)
    set_shader_float(shader, composite_shader["light_dither_strength_location"], lighting_profile.get("light_dither_strength", 1.0))
    set_shader_float(shader, composite_shader["posterize_ambient_location"], 1.0 if lighting_profile.get("posterize_ambient", False) else 0.0)

    source = pr.Rectangle(0, 0, width, -height)
    destination = pr.Rectangle(0, 0, width, height)

    pr.begin_texture_mode(composite_target)
    pr.clear_background(pr.BLANK if preserve_transparency else pr.BLACK)

    pr.begin_shader_mode(shader)

    # Additional sampler textures must be rebound after BeginShaderMode().
    set_shader_texture(shader, composite_shader["light_texture_location"], lighting.texture)
    set_shader_texture(shader, composite_shader["readability_light_texture_location"], readability_lighting.texture)

    pr.draw_texture_pro(scene.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)

    pr.end_shader_mode()
    pr.end_texture_mode()

    pr.begin_texture_mode(scene)
    pr.clear_background(pr.BLANK if preserve_transparency else pr.BLACK)
    if preserve_transparency:
        pr.begin_blend_mode(pr.BlendMode.BLEND_ALPHA_PREMULTIPLY)
    pr.draw_texture_pro(composite_target.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    if preserve_transparency:
        pr.end_blend_mode()
    pr.end_texture_mode()

def _gameplay_burst_color(particle):
    age_amount = min(1.0, max(0.0, float(particle.get("age", 0.0)) / max(0.001, float(particle.get("lifetime", 1.0)))))
    start = list(particle.get("start_color", [1.0, 1.0, 1.0, 1.0]))
    end = list(particle.get("end_color", start))
    while len(start) < 4:
        start.append(1.0)
    while len(end) < 4:
        end.append(1.0)
    values = [start[index] + (end[index] - start[index]) * age_amount for index in range(4)]
    if max(values) <= 1.0:
        values = [value * 255.0 for value in values]
    return pr.Color(*(max(0, min(255, int(round(value)))) for value in values))

def _draw_gameplay_burst_particle(particle, game_camera):
    screen_x = float(particle.get("x", 0.0)) - float(game_camera.x)
    screen_y = float(particle.get("y", 0.0)) - float(game_camera.y) - float(particle.get("z", 0.0))
    size = max(0.5, float(particle.get("size", 1.0)))
    color = _gameplay_burst_color(particle)
    # Continuous environmental effects never reach this path. Blood deliberately
    # retains its small gameplay-state CPU burst representation.
    pr.draw_circle(int(screen_x), int(screen_y), size, color)

def _draw_gameplay_burst_batch(particles, game_camera):
    for particle in particles:
        _draw_gameplay_burst_particle(particle, game_camera)

def _composite_effect_target(scene, layer, premultiplied=False):
    width = scene.texture.width
    height = scene.texture.height
    source = pr.Rectangle(0, 0, width, -height)
    destination = pr.Rectangle(0, 0, width, height)
    pr.begin_texture_mode(scene)
    if premultiplied:
        pr.begin_blend_mode(pr.BlendMode.BLEND_ALPHA_PREMULTIPLY)
    pr.draw_texture_pro(layer.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    if premultiplied:
        pr.end_blend_mode()
    pr.end_texture_mode()

def _normalise_effect_color(color, fallback):
    values = list(color or fallback)
    while len(values) < 4:
        values.append(1.0)
    if max(values) > 1.0:
        values = [value / 255.0 for value in values]
    return values[:4]

def _set_effect_float(info, name, value):
    set_shader_float(info["shader"], info.get(f"{name}_location", -1), value)

def _set_effect_int(info, name, value):
    set_shader_int(info["shader"], info.get(f"{name}_location", -1), value)

def _set_effect_vec2(info, name, value_x, value_y):
    set_shader_vec2(info["shader"], info.get(f"{name}_location", -1), value_x, value_y)

def _set_effect_vec4(info, name, color, fallback):
    values = _normalise_effect_color(color, fallback)
    set_shader_vec4(info["shader"], info.get(f"{name}_location", -1), *values)

def _effect_screen_bounds(emitter, tile_map, game_camera, viewport_width, viewport_height):
    world = g_effects.emitter_world_bounds(emitter, tile_map)
    left = math.floor(world["x"] - float(game_camera.x))
    top = math.floor(world["y"] - float(game_camera.y))
    right = math.ceil(world["x"] + world["width"] - float(game_camera.x))
    bottom = math.ceil(world["y"] + world["height"] - float(game_camera.y))
    clipped_left = max(0, left)
    clipped_top = max(0, top)
    clipped_right = min(int(viewport_width), right)
    clipped_bottom = min(int(viewport_height), bottom)
    if clipped_right <= clipped_left or clipped_bottom <= clipped_top:
        return None
    return {
        "left": left, "top": top, "right": right, "bottom": bottom,
        "width": max(1, right - left), "height": max(1, bottom - top),
        "clip": pr.Rectangle(clipped_left, clipped_top, clipped_right - clipped_left, clipped_bottom - clipped_top),
        "world": world,
    }

def _procedural_effect_submission(emitter, render_group):
    effect_type = emitter.get("type")
    authored_group = emitter.get("render_group", "world_front")
    if effect_type == "fire":
        if render_group == authored_group:
            return {"shader": "effect_fire", "material": "lit_alpha", "pass_mode": 0}
        if render_group == "emissive":
            return {"shader": "effect_fire", "material": "emissive_additive", "pass_mode": 1}
        return None
    if effect_type == "ember":
        return {"shader": "effect_fire", "material": "emissive_additive", "pass_mode": 2} if render_group == authored_group else None
    if render_group != authored_group:
        return None
    if effect_type == "smoke":
        return {"shader": "effect_smoke", "material": "lit_alpha", "pass_mode": 0}
    return None

def _bind_effect_uniforms(info, emitter, bounds, game_camera, tile_map, wind_profile,
                          time_elapsed, pass_mode, viewport_width, viewport_height):
    effect_type = emitter.get("type")
    world = bounds["world"]
    anchor_x = world["anchor_x"] - world["x"]
    anchor_y = world["anchor_y"] - world["y"]
    position = g_effects.position_to_world(emitter.get("position", {}), tile_map)
    area = emitter.get("area_size", {})
    area_width = max(1.0, float(area.get("x", 1.0)))
    area_height = max(1.0, float(area.get("y", 1.0)))
    wind = g_effects.sample_wind(wind_profile, position["x"], position["y"], time_elapsed)
    size = emitter.get("size", area)

    _set_effect_vec2(info, "resolution", viewport_width, viewport_height)
    _set_effect_vec2(info, "boundsMin", bounds["left"], bounds["top"])
    _set_effect_vec2(info, "boundsSize", bounds["width"], bounds["height"])
    _set_effect_vec2(info, "anchorInBounds", anchor_x, anchor_y)
    _set_effect_vec2(info, "effectSize", max(1.0, float(size.get("x", area_width))), max(1.0, float(size.get("y", area_height))))
    _set_effect_vec2(info, "cameraPosition", game_camera.x, game_camera.y)
    _set_effect_vec2(info, "areaMin", position["x"] - area_width * 0.5, position["y"] - area_height * 0.5)
    _set_effect_vec2(info, "areaSize", area_width, area_height)
    _set_effect_vec2(info, "wind", wind["x"], wind["y"])
    _set_effect_float(info, "time", time_elapsed)
    _set_effect_float(info, "seed", int(emitter.get("seed", 1)) % 65521)
    _set_effect_float(info, "density", max(0.0, min(1.0, float(emitter.get("density", 0.5)))))
    _set_effect_float(info, "speed", max(0.0, float(emitter.get("speed", 1.0))))
    _set_effect_float(info, "turbulence", emitter.get("turbulence", 0.7))
    _set_effect_float(info, "detailScale", emitter.get("detail_scale", 0.16))
    _set_effect_float(info, "warpStrength", emitter.get("warp_strength", 0.8))
    _set_effect_float(info, "evolutionSpeed", emitter.get("evolution_speed", 0.62))
    _set_effect_float(info, "windResponse", emitter.get("wind_response", 0.3))
    _set_effect_float(info, "opacity", max(0.0, min(1.0, float(emitter.get("opacity", 1.0)))))
    _set_effect_float(info, "posterizeLevels", max(2.0, float(emitter.get("posterize_levels", 5))))
    _set_effect_float(info, "emberDensity", emitter.get("ember_density", emitter.get("density", 0.2)))
    _set_effect_float(info, "emberHeight", emitter.get("ember_height", size.get("y", 24.0)))
    _set_effect_int(info, "passMode", pass_mode)
    if effect_type == "fire":
        palette = emitter.get("palette", {})
        _set_effect_vec4(info, "colorCore", palette.get("core"), [1.0, 0.94, 0.55, 1.0])
        _set_effect_vec4(info, "colorHot", palette.get("hot"), [1.0, 0.67, 0.18, 1.0])
        _set_effect_vec4(info, "colorMid", palette.get("mid"), [0.92, 0.25, 0.045, 1.0])
        _set_effect_vec4(info, "colorOuter", palette.get("outer"), [0.30, 0.025, 0.012, 1.0])
    elif effect_type == "ember":
        color = emitter.get("color", [1.0, 0.52, 0.12, 1.0])
        _set_effect_vec4(info, "colorHot", color, [1.0, 0.52, 0.12, 1.0])
    elif effect_type == "smoke":
        _set_effect_vec4(info, "smokeColor", emitter.get("color"), [0.42, 0.43, 0.48, 1.0])

def _draw_procedural_submission(submission, emitter_id, emitter, bounds, scene, game_camera, game_assets, tile_map, wind_profile, time_elapsed, runtime, render_group):
    info = game_assets["shaders"][submission["shader"]]
    _bind_effect_uniforms(
        info, emitter, bounds, game_camera, tile_map, wind_profile, time_elapsed,
        submission["pass_mode"], scene.texture.width, scene.texture.height,
    )
    pr.begin_shader_mode(info["shader"])
    pr.draw_rectangle_rec(bounds["clip"], pr.WHITE)
    pr.end_shader_mode()
    runtime.setdefault("debug_submissions", []).append({
        "id": emitter_id, "type": emitter.get("type"), "shader": submission["shader"],
        "render_group": render_group, "material": submission["material"],
        "seed": int(emitter.get("seed", 1)), "density": float(emitter.get("density", 0.0)),
        "bounds": (bounds["left"], bounds["top"], bounds["width"], bounds["height"]),
        "world": (bounds["world"]["anchor_x"], bounds["world"]["anchor_y"]),
    })

def render_effect_group(scene, game_camera, game_assets, lighting_profile, lighting_target,
                        render_group, apply_world_lighting=True, emitters=None,
                        tile_map=None, wind_profile=None, time_elapsed=0.0,
                        respect_preview_enabled=False):
    """Submit one local shader quad per visible authored effect pass."""
    runtime = game_assets.get("effects_runtime")
    if not isinstance(runtime, dict):
        return {"emitters": 0, "draw_calls": 0, "submission_time_ms": 0.0}
    started = time.perf_counter()
    emitters = emitters or {}
    width = scene.texture.width
    height = scene.texture.height
    grouped = {"lit_alpha": [], "unlit_alpha": [], "emissive_additive": []}
    stats = runtime.setdefault("stats", {})
    for emitter_id, emitter in emitters.items():
        if not emitter.get("enabled", True) or (respect_preview_enabled and not emitter.get("preview_enabled", True)):
            continue
        submission = _procedural_effect_submission(emitter, render_group)
        if submission is None:
            continue
        bounds = _effect_screen_bounds(emitter, tile_map, game_camera, width, height)
        if bounds is None:
            stats["culled_emitters"] = int(stats.get("culled_emitters", 0)) + 1
            continue
        grouped[submission["material"]].append((submission, emitter_id, emitter, bounds))

    burst_particles = g_effects.collect_gameplay_burst_particles(runtime, render_group, "lit_alpha")
    draw_calls = sum(len(values) for values in grouped.values()) + (1 if burst_particles else 0)
    if draw_calls == 0:
        return {"emitters": 0, "draw_calls": 0, "submission_time_ms": 0.0}

    lit_submissions = grouped["lit_alpha"]
    if lit_submissions or burst_particles:
        if apply_world_lighting and lighting_target is not None:
            layer = get_or_create_render_target(game_assets, f"effects_{render_group}_albedo", width, height)
            blank_readability = get_or_create_render_target(game_assets, "effects_blank_readability", width, height)
            pr.begin_texture_mode(blank_readability)
            pr.clear_background(pr.BLANK)
            pr.end_texture_mode()
            pr.begin_texture_mode(layer)
            pr.clear_background(pr.BLANK)
            for values in lit_submissions:
                _draw_procedural_submission(*values, scene, game_camera, game_assets, tile_map, wind_profile, time_elapsed, runtime, render_group)
            _draw_gameplay_burst_batch(burst_particles, game_camera)
            pr.end_texture_mode()
            if game_assets.get("effect_debug_output", "final") == "raw":
                _composite_effect_target(scene, layer, False)
            else:
                apply_lighting(layer, lighting_target, blank_readability, game_assets, lighting_profile, True)
                _composite_effect_target(scene, layer, True)
        else:
            pr.begin_texture_mode(scene)
            for values in lit_submissions:
                _draw_procedural_submission(*values, scene, game_camera, game_assets, tile_map, wind_profile, time_elapsed, runtime, render_group)
            _draw_gameplay_burst_batch(burst_particles, game_camera)
            pr.end_texture_mode()

    if grouped["unlit_alpha"]:
        pr.begin_texture_mode(scene)
        for values in grouped["unlit_alpha"]:
            _draw_procedural_submission(*values, scene, game_camera, game_assets, tile_map, wind_profile, time_elapsed, runtime, render_group)
        pr.end_texture_mode()

    if grouped["emissive_additive"]:
        pr.begin_texture_mode(scene)
        pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
        for values in grouped["emissive_additive"]:
            _draw_procedural_submission(*values, scene, game_camera, game_assets, tile_map, wind_profile, time_elapsed, runtime, render_group)
        pr.end_blend_mode()
        pr.end_texture_mode()

    elapsed = (time.perf_counter() - started) * 1000.0
    stats["procedural_draw_calls"] = int(stats.get("procedural_draw_calls", 0)) + sum(len(values) for values in grouped.values())
    calls_by_type = stats.setdefault("draw_calls_by_type", {})
    for material_submissions in grouped.values():
        for _submission, _emitter_id, emitter, _bounds in material_submissions:
            effect_type = emitter.get("type", "unknown")
            calls_by_type[effect_type] = int(calls_by_type.get(effect_type, 0)) + 1
    stats["burst_draw_calls"] = int(stats.get("burst_draw_calls", 0)) + (1 if burst_particles else 0)
    stats["submission_time_ms"] = float(stats.get("submission_time_ms", 0.0)) + elapsed
    return {"emitters": sum(len(values) for values in grouped.values()), "draw_calls": draw_calls, "submission_time_ms": elapsed}

def draw_effect_stats_debug(runtime, x=4, y=58):
    stats = (runtime or {}).get("stats", {})
    for submission in (runtime or {}).get("debug_submissions", ()):
        left, top, width, height = submission["bounds"]
        color = {
            "fire": pr.ORANGE, "ember": pr.GOLD, "smoke": pr.GRAY,
        }.get(submission["type"], pr.MAGENTA)
        pr.draw_rectangle_lines_ex(pr.Rectangle(left, top, width, height), 1.0, color)
        world_x, world_y = submission.get("world", (0.0, 0.0))
        pr.draw_text(
            f"{submission['shader']} s{submission['seed']} d{submission['density']:.2f} "
            f"@{world_x:.0f},{world_y:.0f}",
            int(left), int(top) - 9, 7, color,
        )
    by_type = stats.get("draw_calls_by_type", {})
    type_text = " ".join(f"{name}:{count}" for name, count in sorted(by_type.items()))
    pr.draw_text(
        f"fx emit {stats.get('active_emitter_count', 0)}/{stats.get('authored_emitter_count', 0)} "
        f"gpu draws {stats.get('procedural_draw_calls', 0)} culled {stats.get('culled_emitters', 0)} "
        f"blood {stats.get('live_particle_count', 0)} "
        f"{stats.get('update_time_ms', 0.0):.2f}+{stats.get('submission_time_ms', 0.0):.2f}ms",
        x, y, 8, pr.LIME,
    )
    if type_text:
        pr.draw_text(type_text, x, y + 9, 8, pr.LIME)

def draw_render_item_occlusion_outline(scene, render_item, game_camera, game_assets):
    if render_item is None:
        return
    outline_shader = game_assets.get("shaders", {}).get("render_item_outline")
    if outline_shader is None:
        return
    texture_reference = render_item.get("texture", {})
    asset = game_assets.get(texture_reference.get("collection", ""), {}).get(texture_reference.get("name"))
    texture = asset.get(texture_reference.get("field")) if isinstance(asset, dict) and texture_reference.get("field") is not None else asset
    if texture is None:
        return
    width = scene.texture.width
    height = scene.texture.height
    mask_target = get_or_create_render_target(game_assets, "render_item_outline_mask", width, height)
    source_data = render_item["source_rect"]
    dest_data = render_item["dest_rect"]
    sprite_source = pr.Rectangle(source_data["x"], source_data["y"], source_data["width"], source_data["height"])
    screen_position = g_render_order.world_to_screen_pixel(
        dest_data["x"], dest_data["y"], game_camera,
    )
    sprite_destination = pr.Rectangle(
        screen_position["x"], screen_position["y"],
        dest_data["width"], dest_data["height"],
    )
    full_source = pr.Rectangle(0, 0, width, -height)
    full_destination = pr.Rectangle(0, 0, width, height)
    pr.begin_texture_mode(mask_target)
    pr.clear_background(pr.BLANK)
    pr.draw_texture_pro(texture, sprite_source, sprite_destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()
    shader = outline_shader["shader"]
    outline = render_item.get("outline", {})
    color = list(outline.get("color", [0.50, 0.66, 0.74, 0.52]))
    while len(color) < 4:
        color.append(1.0)
    if max(color) > 1.0:
        color = [component / 255.0 for component in color]
    set_shader_vec2(shader, outline_shader["resolution_location"], width, height)
    set_shader_vec4(shader, outline_shader["outline_color_location"], color[0], color[1], color[2], color[3])
    set_shader_float(shader, outline_shader["outline_width_location"], max(0.5, float(outline.get("width", 1.0))))
    pr.begin_texture_mode(scene)
    pr.begin_shader_mode(shader)
    pr.draw_texture_pro(mask_target.texture, full_source, full_destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_shader_mode()
    pr.end_texture_mode()

def draw_render_item_occlusion_outlines(scene, outlined_items, game_camera, game_assets):
    for entry in outlined_items:
        draw_render_item_occlusion_outline(scene, entry.get("item"), game_camera, game_assets)


def _rain_debug_mode(debug):
    if debug.get("show_raw_exposure_texture", False):
        return 5
    if debug.get("show_raw_streak_mask", False):
        return 2
    if debug.get("show_distortion_mask", False):
        return 3
    if debug.get("show_sampled_light_amount", False):
        return 4
    return 0


def apply_rain_composite(scene, world_light_target, rain_exposure_texture,
                         rain_profile, game_assets, game_camera, tile_map,
                         time_elapsed):
    """Refract the completed scene vertically and composite light-revealed rain."""
    started = time.perf_counter()
    stats = game_assets.setdefault("rain_stats", {})
    stats["composite_draw_calls"] = 0
    stats["composite_submission_time_ms"] = 0.0
    cache = game_assets.get("rain_exposure_texture_cache", {})
    stats["enabled"] = bool((rain_profile or {}).get("enabled", False))
    stats["exposed_tile_count"] = int(cache.get("exposed_tile_count", 0))
    stats["exposure_texture_revision"] = cache.get("last_revision", -1)
    stats["exposure_texture_rebuild_count"] = int(cache.get("rebuild_count", 0))

    if not stats["enabled"] or stats["exposed_tile_count"] <= 0:
        return False
    if scene is None or world_light_target is None or rain_exposure_texture is None:
        return False
    if getattr(scene.texture, "id", 0) <= 0 or getattr(world_light_target.texture, "id", 0) <= 0:
        return False
    rain_shader = game_assets.get("shaders", {}).get("rain_composite")
    if not isinstance(rain_shader, dict) or rain_shader.get("shader") is None:
        return False

    profile = g_effects.normalize_rain_profile(rain_profile)
    width = int(scene.texture.width)
    height = int(scene.texture.height)
    composite_target = get_or_create_render_target(game_assets, "rain_composite", width, height)
    shader = rain_shader["shader"]
    direction = profile["direction"]
    cell_size = profile["cell_size"]
    ambient = profile["ambient_color"]
    debug = game_assets.get("rain_debug", {})

    set_shader_vec2(shader, rain_shader["resolution_location"], width, height)
    set_shader_vec2(shader, rain_shader["cameraPosition_location"], game_camera.x, game_camera.y)
    set_shader_vec2(shader, rain_shader["tileSize_location"], tile_map.get("tile_width", 16), tile_map.get("tile_height", 16))
    set_shader_vec2(shader, rain_shader["mapSize_location"], tile_map.get("map_width", 0), tile_map.get("map_height", 0))
    set_shader_float(shader, rain_shader["time_location"], time_elapsed)
    set_shader_float(shader, rain_shader["seed_location"], profile["seed"])
    set_shader_float(shader, rain_shader["density_location"], profile["density"])
    set_shader_float(shader, rain_shader["speed_location"], profile["speed"])
    set_shader_vec2(shader, rain_shader["direction_location"], direction["x"], direction["y"])
    set_shader_vec2(shader, rain_shader["cellSize_location"], cell_size["x"], cell_size["y"])
    set_shader_float(shader, rain_shader["streakLength_location"], profile["streak_length"])
    set_shader_float(shader, rain_shader["unlitOpacity_location"], profile["unlit_opacity"])
    set_shader_float(shader, rain_shader["litOpacity_location"], profile["lit_opacity"])
    set_shader_float(shader, rain_shader["lightThreshold_location"], profile["light_threshold"])
    set_shader_float(shader, rain_shader["lightResponse_location"], profile["light_response"])
    set_shader_float(shader, rain_shader["lightColorInfluence_location"], profile["light_color_influence"])
    set_shader_vec3(shader, rain_shader["ambientRainColor_location"], ambient[0], ambient[1], ambient[2])
    set_shader_float(shader, rain_shader["opacityLevels_location"], profile["opacity_levels"])
    set_shader_float(shader, rain_shader["distortionEnabled_location"], 1.0 if profile["distortion_enabled"] else 0.0)
    set_shader_float(shader, rain_shader["distortionStrength_location"], profile["distortion_strength"])
    set_shader_float(shader, rain_shader["distortionDensity_location"], profile["distortion_density"])
    set_shader_int(shader, rain_shader["debugMode_location"], _rain_debug_mode(debug))
    set_shader_float(shader, rain_shader["showExposureOverlay_location"], 1.0 if debug.get("show_exposure_overlay", False) else 0.0)
    set_shader_float(shader, rain_shader["disableStreakColor_location"], 1.0 if debug.get("disable_streak_color", False) else 0.0)
    set_shader_float(shader, rain_shader["disableDistortion_location"], 1.0 if debug.get("disable_distortion", False) else 0.0)

    source = pr.Rectangle(0, 0, width, -height)
    destination = pr.Rectangle(0, 0, width, height)
    point_filter = pr.TextureFilter.TEXTURE_FILTER_POINT
    pr.set_texture_filter(scene.texture, point_filter)
    pr.set_texture_filter(world_light_target.texture, point_filter)
    pr.set_texture_filter(rain_exposure_texture, point_filter)
    pr.set_texture_filter(composite_target.texture, point_filter)

    pr.begin_texture_mode(composite_target)
    pr.clear_background(pr.BLANK)
    pr.begin_shader_mode(shader)
    set_shader_texture(shader, rain_shader["lightTexture_location"], world_light_target.texture)
    set_shader_texture(shader, rain_shader["rainExposureTexture_location"], rain_exposure_texture)
    pr.draw_texture_pro(scene.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_shader_mode()
    pr.end_texture_mode()

    pr.begin_texture_mode(scene)
    pr.clear_background(pr.BLANK)
    pr.draw_texture_pro(composite_target.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()

    stats["composite_draw_calls"] = 1
    stats["composite_submission_time_ms"] = (time.perf_counter() - started) * 1000.0
    return True


def draw_rain_stats_debug(game_assets, x=4, y=54):
    stats = game_assets.get("rain_stats", {})
    pr.draw_text(
        f"rain {'on' if stats.get('enabled', False) else 'off'} exposed {stats.get('exposed_tile_count', 0)} "
        f"rev {stats.get('exposure_texture_revision', -1)} rebuilds {stats.get('exposure_texture_rebuild_count', 0)} "
        f"draws {stats.get('composite_draw_calls', 0)} {stats.get('composite_submission_time_ms', 0.0):.2f}ms",
        x, y, 8, pr.SKYBLUE,
    )

def apply_illuminated_fog(scene, fog_lighting, fog_volume_mask, game_assets, fog_profile, game_camera, time_elapsed):
    if not fog_profile.get("enabled", True):
        return

    width = scene.texture.width
    height = scene.texture.height
    composite_target = get_or_create_render_target(game_assets, "fog_composite", width, height)
    fog_shader = game_assets["shaders"]["illuminated_fog"]
    shader = fog_shader["shader"]
    drift = fog_profile.get("drift", {"x": 0.0, "y": 0.0})
    detail_drift = fog_profile.get("detail_drift", {"x": -2.0, "y": 3.5})
    fog_red, fog_green, fog_blue = normalize_light_color(fog_profile.get("color", [0.62, 0.70, 0.86]))

    set_shader_vec2(shader, fog_shader["resolution_location"], width, height)
    set_shader_vec2(shader, fog_shader["camera_position_location"], game_camera.x, game_camera.y)
    set_shader_vec2(shader, fog_shader["fog_drift_location"], drift.get("x", 0.0), drift.get("y", 0.0))
    set_shader_vec2(shader, fog_shader["detail_drift_location"], detail_drift.get("x", -2.0), detail_drift.get("y", 3.5))
    set_shader_vec3(shader, fog_shader["fog_color_location"], fog_red, fog_green, fog_blue)
    set_shader_float(shader, fog_shader["time_location"], time_elapsed)
    set_shader_float(shader, fog_shader["density_location"], fog_profile.get("density", 0.65))
    set_shader_float(shader, fog_shader["opacity_location"], fog_profile.get("opacity", 0.75))
    set_shader_float(shader, fog_shader["world_scale_location"], fog_profile.get("world_scale", 0.018))
    set_shader_float(shader, fog_shader["detail_scale_location"], fog_profile.get("detail_scale", 2.7))
    set_shader_float(shader, fog_shader["cutoff_location"], fog_profile.get("cutoff", 0.42))
    set_shader_float(shader, fog_shader["softness_location"], fog_profile.get("softness", 0.20))
    set_shader_float(shader, fog_shader["light_strength_location"], fog_profile.get("light_strength", 1.35))
    set_shader_float(shader, fog_shader["ambient_strength_location"], fog_profile.get("ambient_strength", 0.0))
    set_shader_float(shader, fog_shader["veil_strength_location"], fog_profile.get("veil_strength", 0.10))
    set_shader_float(shader, fog_shader["evolution_speed_location"], fog_profile.get("evolution_speed", 0.10))
    set_shader_float(shader, fog_shader["warp_scale_location"], fog_profile.get("warp_scale", 0.55))
    set_shader_float(shader, fog_shader["warp_strength_location"], fog_profile.get("warp_strength", 0.75))
    set_shader_float(shader, fog_shader["detail_evolution_speed_location"], fog_profile.get("detail_evolution_speed", 0.17))
    set_shader_float(shader, fog_shader["global_amount_location"], fog_profile.get("global_amount", 0.0))
    set_shader_float(shader, fog_shader["posterize_enabled_location"], 1.0 if fog_profile.get("posterize_enabled", True) else 0.0)
    set_shader_float(shader, fog_shader["posterize_levels_location"], fog_profile.get("posterize_levels", 6.0))
    set_shader_float(shader, fog_shader["dither_enabled_location"], 1.0 if fog_profile.get("dither_enabled", False) else 0.0)
    set_shader_float(shader, fog_shader["dither_strength_location"], fog_profile.get("dither_strength", 1.0))

    source = pr.Rectangle(0, 0, width, -height)
    destination = pr.Rectangle(0, 0, width, height)

    pr.begin_texture_mode(composite_target)
    pr.clear_background(pr.BLACK)
    pr.begin_shader_mode(shader)

    # Additional sampler textures must be rebound after BeginShaderMode().
    set_shader_texture(shader, fog_shader["light_texture_location"], fog_lighting.texture)
    set_shader_texture(shader, fog_shader["volume_texture_location"], fog_volume_mask.texture)

    pr.draw_texture_pro(scene.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)

    pr.end_shader_mode()
    pr.end_texture_mode()

    pr.begin_texture_mode(scene)
    pr.clear_background(pr.BLACK)
    pr.draw_texture_pro(composite_target.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()
