import math
import random
import time

import pyray as pr
from pyrsistent import m, pmap, v

import g_light_visibility as light_visibility
import g_update_and_render as game

CINEMATIC_SHADOW_DEBUG_ENABLED = True

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

def get_or_create_test_fog_volumes(entities, tile_map):
    fog_volumes = game.get_or_set(entities, "fog_volumes", {})

    if "test_fog_volume" not in fog_volumes:
        fog_volumes["test_fog_volume"] = {
            "type": "fog_volume",
            "shape": "ellipse",
            "position": {
                "tile_x": 40,
                "tile_y": 2,
                "x": 8.0,
                "y": 8.0
            },
            "size": {
                "x": 180.0,
                "y": 110.0
            },
            "edge_softness": 24.0,
            "strength": 1.0,
            "enabled": True
        }

    return fog_volumes

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
    fog_volumes = get_or_create_test_fog_volumes(entities, tile_map)

    pr.begin_texture_mode(mask_target)
    pr.clear_background(pr.BLACK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)

    for volume in fog_volumes.values():
        draw_fog_volume_to_mask(volume, game_camera, tile_map, mask_target, volume_shader)

    pr.end_blend_mode()
    pr.end_texture_mode()
    return mask_target

def draw_fog_volume_debug(volume, game_camera, tile_map):
    if not volume.get("enabled", True):
        return

    world_position = get_light_world_position(volume, tile_map)
    size = volume.get("size", {})
    width = max(0.0, float(size.get("x", 0.0)))
    height = max(0.0, float(size.get("y", 0.0)))
    screen_x = world_position["x"] - game_camera.x
    screen_y = world_position["y"] - game_camera.y
    color = pr.Color(150, 210, 255, 220)

    if volume.get("shape", "ellipse") == "ellipse":
        pr.draw_ellipse_lines(int(screen_x), int(screen_y), width * 0.5, height * 0.5, color)
    else:
        rectangle = pr.Rectangle(screen_x - width * 0.5, screen_y - height * 0.5, width, height)
        pr.draw_rectangle_lines_ex(rectangle, 1.0, color)

    pr.draw_circle(int(screen_x), int(screen_y), 2.0, pr.YELLOW)

def get_or_create_test_lights(entities, tile_map):
    lights = game.get_or_set(entities, "lights", {})

    # Remove the previous ring-light test record.
    if "test_light" in lights and "type" not in lights["test_light"]:
        del lights["test_light"]

    if "test_point" not in lights:
        lights["test_point"] = {
            "type": "point",
            "position": game.get_tile_index_and_offset_from_pos({"x": 200.0, "y": 300.0}, tile_map),
            "color": [0.86, 0.74, 1.0],
            "radius": 150.0,
            "intensity": 1.0,
            "falloff": 2.0,
            "casts_shadows": True,
            "shadow_bias": 0.25,
            "enabled": True
        }

    if "test_top_down" not in lights:
        lights["test_top_down"] = {
            "type": "top_down",
            "position": {
                "tile_x": 20,
                "tile_y": 15,
                "x": 8.0,
                "y": 8.0
            },
            "size": {
                "x": 320.0,
                "y": 180.0
            },
            "color": [0.55, 0.62, 0.78],
            "intensity": 0.55,
            "edge_softness": 24.0,
            "enabled": True,
            "casts_shadows": False
        }

    return lights

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
            "affects_fog": False,
            "affects_ai": False,
            "gameplay_intensity": 0.0,
            "mobility": "dynamic",
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
        "direction": direction,
        "color": [1.0, 0.82, 0.62],
        "radius": 180.0,
        "intensity": 1.2,
        "falloff": 1.4,
        "casts_shadows": True,
        "casts_wall_shadows": True,
        "casts_cinematic_shadows": True,
        "affects_scene": True,
        "affects_fog": True,
        "affects_ai": True,
        "gameplay_intensity": 1.0,
        "mobility": "dynamic",
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
    result.setdefault("enabled", True)
    result.setdefault("affects_scene", True)
    result.setdefault("affects_fog", True)
    result.setdefault("affects_ai", True)
    result.setdefault("casts_wall_shadows", result.get("casts_shadows", True))
    result.setdefault("casts_cinematic_shadows", False)
    result.setdefault("gameplay_intensity", 1.0)
    result.setdefault("mobility", "static")
    return result

def collect_light_records(entities, player_entity, tile_map, game_assets):
    records = []

    for light_id, light in get_or_create_test_lights(entities, tile_map).items():
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
            if light["affects_scene"]:
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

def make_default_cinematic_shadow(entity_type):
    presets = {
        "red head": {
            "enabled": True,
            "source": "sprite_alpha",
            "length": 52.0,
            "near_width": 0.65,
            "far_width": 1.15,
            "lateral_skew": 0.0,
            "opacity": 0.58,
            "color": [0.008, 0.004, 0.018],
            "anchor_offset": {"x": -12.0, "y": -3.0},
            "near_offset": 1.0,
            "max_light_distance": 180.0,
            "fade_with_light_strength": True
        },
        "buddha": {
            "enabled": True,
            "source": "sprite_alpha",
            "length": 68.0,
            "near_width": 0.90,
            "far_width": 1.30,
            "lateral_skew": 0.0,
            "opacity": 0.48,
            "color": [0.008, 0.004, 0.018],
            "anchor_offset": {"x": -6.0, "y": 61.0},
            "near_offset": 1.0,
            "max_light_distance": 180.0,
            "fade_with_light_strength": True
        }
    }
    return presets.get(entity_type)

def ensure_default_cinematic_shadow(entity):
    if entity.get("type") not in {"red head", "buddha"}:
        return entity

    if "cinematic_shadow" not in entity:
        entity["cinematic_shadow"] = make_default_cinematic_shadow(entity.get("type"))

    return entity

def get_entity_cinematic_shadow_sprite_info(entity, game_assets, tile_map):
    entity_type = entity.get("type")
    world_anchor = game.make_pos_abs(entity.get("position", {}), tile_map["tile_width"], tile_map["tile_height"])

    if entity_type == "red head":
        sprite_sheet = game_assets.get("sprite_sheets", {}).get("red_head_texture_sheet", {})
        texture = sprite_sheet.get("sheet")

        if texture is None:
            return None

        frame_key = entity.get("animation_frame", 0)
        frame_number = sprite_sheet.get(frame_key, 0)
        return {
            "texture": texture,
            "source_rect": pr.Rectangle(float(frame_number) * 24.0, 0.0, 24.0, 24.0),
            "world_anchor": world_anchor,
            "sprite_width": 24.0,
            "sprite_height": 24.0
        }

    if entity_type == "buddha":
        texture = game_assets.get("textures", {}).get("buddha_texture")

        if texture is None:
            return None

        return {
            "texture": texture,
            "source_rect": pr.Rectangle(0.0, 0.0, float(texture.width), float(texture.height)),
            "world_anchor": world_anchor,
            "sprite_width": float(texture.width),
            "sprite_height": float(texture.height)
        }

    return None

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

def build_cinematic_shadow_quad(sprite_info, shadow_settings, flashlight_position):
    anchor_offset = shadow_settings.get("anchor_offset", {})
    floor_anchor = {
        "x": sprite_info["world_anchor"]["x"] + float(anchor_offset.get("x", 0.0)),
        "y": sprite_info["world_anchor"]["y"] + float(anchor_offset.get("y", 0.0))
    }
    from_light = game.vec2_subtract(floor_anchor, flashlight_position)
    distance_from_light = game.vec2_norm(from_light)

    if distance_from_light <= 0.0001:
        return None

    projection_direction = game.vec2_scale(from_light, 1.0 / distance_from_light)
    side_direction = {"x": -projection_direction["y"], "y": projection_direction["x"]}
    length = max(0.0, float(shadow_settings.get("length", 56.0)))
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
        "far_right": game.vec2_add(far_center, game.vec2_scale(side_direction, far_half_width))
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

def build_cinematic_shadow_frame_data(entities, player_entity, tile_map, game_assets, prepared_flashlight):
    if prepared_flashlight is None or not prepared_flashlight.get("casts_cinematic_shadows", False):
        return None

    flashlight = prepared_flashlight["light"]
    flashlight_position = prepared_flashlight["world_position"]
    visibility_light = flashlight
    visibility_polygon = prepared_flashlight.get("cinematic_visibility_polygon") or prepared_flashlight.get("visibility_polygon") or []
    visibility_area = [flashlight_position] + visibility_polygon if flashlight.get("type") == "spot" else visibility_polygon
    shadows = []

    for entity in entities.get("brains", {}).values():
        ensure_default_cinematic_shadow(entity)
        shadow_settings = entity.get("cinematic_shadow")

        if not shadow_settings or not shadow_settings.get("enabled", True) or shadow_settings.get("source", "sprite_alpha") != "sprite_alpha":
            continue

        sprite_info = get_entity_cinematic_shadow_sprite_info(entity, game_assets, tile_map)

        if sprite_info is None:
            continue

        shadow_quad = build_cinematic_shadow_quad(sprite_info, shadow_settings, flashlight_position)

        if shadow_quad is None:
            continue

        floor_anchor = shadow_quad["floor_anchor"]
        distance_from_light = game.vec2_distance(floor_anchor, flashlight_position)

        if distance_from_light > max(0.0, float(shadow_settings.get("max_light_distance", 180.0))):
            continue

        flashlight_strength = get_spot_light_strength_at_world_point(flashlight, floor_anchor, tile_map)

        if flashlight_strength <= 0.0 or not point_in_polygon(floor_anchor, visibility_area):
            continue

        shadow_opacity = max(0.0, min(1.0, float(shadow_settings.get("opacity", 0.58))))

        if shadow_settings.get("fade_with_light_strength", True):
            shadow_opacity *= flashlight_strength

        shadows.append({
            "entity": entity,
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
        "shadows": shadows
    }

def draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, light_shader, include_receivers=True, shader_mode_active=False):
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

    if prepared_light["casts_wall_shadows"]:
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

def draw_prepared_light_to_target(prepared_light, game_camera, lighting_target, game_assets, include_receivers=True):
    if prepared_light["light"].get("type", "point") == "top_down":
        draw_prepared_top_down_light_to_target(prepared_light, game_camera, lighting_target, game_assets["shaders"]["top_down_light"])
        return

    draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, game_assets["shaders"]["light_accumulation"], include_receivers)

def draw_ringed_circular_light(x, y, rings, ring_size, ring_radius, red, green, blue, base_alpha, alpha_multiplier):    
    for i in range(rings, 0,-ring_size):
        t = i / rings
        radius = ring_radius * t
        strength = 1.0 - t
        alpha = int(base_alpha+ strength*alpha_multiplier)
        pr.draw_circle(int(x), int(y), radius, pr.Color(red,green,blue,alpha))

def render_prepared_lights_to_target(prepared_lights, game_camera, lighting_target, game_assets, target_kind):
    if target_kind not in {"scene", "fog"}:
        raise ValueError(f"unknown prepared light target kind: {target_kind}")

    draw_started = time.perf_counter()
    pr.begin_texture_mode(lighting_target)
    pr.clear_background(pr.BLACK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)

    capability = "affects_scene" if target_kind == "scene" else "affects_fog"

    target_lights = [prepared_light for prepared_light in prepared_lights if prepared_light[capability]]
    radial_lights = [prepared_light for prepared_light in target_lights if prepared_light["light"].get("type", "point") != "top_down"]
    top_down_lights = [prepared_light for prepared_light in target_lights if prepared_light["light"].get("type", "point") == "top_down"]

    if radial_lights:
        light_shader = game_assets["shaders"]["light_accumulation"]
        pr.begin_shader_mode(light_shader["shader"])

        for prepared_light in radial_lights:
            pr.rl_draw_render_batch_active()
            draw_prepared_radial_light_to_target(prepared_light, game_camera, lighting_target, light_shader, target_kind == "scene", True)

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
    lighting_frame["stats"]["fog_draw_time_ms"] = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, fog_light_target, game_assets, "fog")
    lighting_frame["stats"]["scene_draw_time_ms"] = render_prepared_lights_to_target(lighting_frame["prepared_lights"], game_camera, lighting_target, game_assets, "scene")
    return fog_light_target

def draw_lighting_stats_debug(stats, x=4, y=4):
    cache_lookups = stats.get("visibility_cache_hits", 0) + stats.get("visibility_cache_misses", 0)
    cache_rate = stats.get("visibility_cache_hits", 0) / max(1, cache_lookups) * 100.0
    lines = [
        f"lights {stats.get('active_light_count', 0)} shadowed {stats.get('shadowed_radial_light_count', 0)}",
        f"cache {cache_rate:.0f}% rebuilds {stats.get('visibility_rebuilds', 0)}",
        f"rays {stats.get('total_visibility_rays', 0)} dda {stats.get('total_dda_tile_steps', 0)}",
        f"prep {stats.get('prepare_time_ms', 0.0):.2f}ms draw {stats.get('scene_draw_time_ms', 0.0) + stats.get('fog_draw_time_ms', 0.0):.2f}ms"
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

def render_and_apply_cinematic_entity_shadows(scene, game_camera, entities, player_entity, tile_map, game_assets, prepared_flashlight):
    frame_data = build_cinematic_shadow_frame_data(entities, player_entity, tile_map, game_assets, prepared_flashlight)

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

def draw_cinematic_shadow_debug(game_camera, entities, player_entity, tile_map, game_assets, prepared_flashlight):
    if not CINEMATIC_SHADOW_DEBUG_ENABLED:
        return

    frame_data = build_cinematic_shadow_frame_data(entities, player_entity, tile_map, game_assets, prepared_flashlight)

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

def get_player_flashlight_settings(player_entity):
    facing = player_entity.get("animation_direction", "down")

    settings = {
        "up": {"forward_offset": 10.0, "side_offset": -2.0, "near_fade_distance": 18.0},
        "down": {"forward_offset": 3.0, "side_offset": 2.0, "near_fade_distance": 10.0},
        "left": {"forward_offset": 4.0, "side_offset": -1.0, "near_fade_distance": 14.0},
        "right": {"forward_offset": 4.0, "side_offset": 1.0, "near_fade_distance": 14.0}
    }

    return settings.get(facing, settings["down"])

def light_timer_oscilate(t):
    slow = math.sin(t / 100) * 20
    med = math.sin(t / 10) * 5
    fast =  math.sin(t / 2) *10
    result = slow + med + fast
    return result

def apply_lighting(scene, lighting, game_assets, lighting_profile):
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
    pr.clear_background(pr.BLACK)

    pr.begin_shader_mode(shader)

    # Additional sampler textures must be rebound after BeginShaderMode().
    set_shader_texture(shader, composite_shader["light_texture_location"], lighting.texture)

    pr.draw_texture_pro(scene.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)

    pr.end_shader_mode()
    pr.end_texture_mode()

    pr.begin_texture_mode(scene)
    pr.clear_background(pr.BLACK)
    pr.draw_texture_pro(composite_target.texture, source, destination, pr.Vector2(0, 0), 0, pr.WHITE)
    pr.end_texture_mode()

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
