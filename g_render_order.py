import copy
import math


SORT_LAYER_ORDER = {"floor": 0, "world": 100, "overlay": 200}


def world_to_screen_pixel(world_x, world_y, game_camera):
    """Snap world and camera independently so stationary sprites stay registered."""
    if isinstance(game_camera, dict):
        camera_x = float(game_camera.get("x", 0.0))
        camera_y = float(game_camera.get("y", 0.0))
    else:
        camera_x = float(getattr(game_camera, "x", 0.0))
        camera_y = float(getattr(game_camera, "y", 0.0))
    return {
        "x": round(float(world_x)) - round(camera_x),
        "y": round(float(world_y)) - round(camera_y),
    }


def moving_world_to_screen_pixel(world_x, world_y, game_camera):
    """Snap relative motion once so co-moving actor/camera fractions cannot jitter."""
    if isinstance(game_camera, dict):
        camera_x = float(game_camera.get("x", 0.0))
        camera_y = float(game_camera.get("y", 0.0))
    else:
        camera_x = float(getattr(game_camera, "x", 0.0))
        camera_y = float(getattr(game_camera, "y", 0.0))
    return {
        "x": round(float(world_x) - camera_x),
        "y": round(float(world_y) - camera_y),
    }


def make_default_entity_render_metadata(entity_type):
    entity_type = str(entity_type or "").lower().replace("_", " ")
    common = {
        "render_anchor_offset": {"x": 0.0, "y": 0.0},
        "render_base_offset": {"x": 0.0, "y": 0.0},
        "visual_height": 0.0,
        "light_sample_height": 0.0,
        "ground_footprint": {"shape": "rectangle", "offset": {"x": 0.0, "y": 0.0}, "size": {"x": 8.0, "y": 5.0}},
        "self_shadow": {"mode": "none", "strength": 0.0, "softness": 0.10, "back_fill": 0.06},
        "entity_light_occluder": {"enabled": False, "height": 0.0, "blocks_entity_lighting": False},
        "shadow": {"mode": "none", "cast_height": 0.0, "length_scale": 1.0, "minimum_length": 2.0, "maximum_length": 16.0, "opacity": 0.35, "near_width": 0.70, "far_width": 1.0, "color": [0.008, 0.004, 0.018], "near_offset": 1.0, "lateral_skew": 0.0, "max_light_distance": 220.0, "fade_with_light_strength": True},
        "outline": {"policy": "never", "color": [0.55, 0.66, 0.72, 0.48], "width": 1.0, "priority": 0},
        "render_style": "world",
        "occludes_render_items": False,
        "fog_interaction": {"mode": "standard"},
        "water_interaction": {"mode": "standard"}
    }
    presets = {
        "player": {
            "render_anchor_offset": {"x": -16.0, "y": -16.0}, "render_base_offset": {"x": 0.0, "y": 14.0}, "visual_height": 32.0, "light_sample_height": 18.0,
            "ground_footprint": {"shape": "rectangle", "offset": {"x": 0.0, "y": -2.0}, "size": {"x": 12.0, "y": 7.0}},
            "self_shadow": {"mode": "upright_box", "strength": 0.78, "softness": 0.12, "back_fill": 0.08},
            "outline": {"policy": "player_when_occluded", "color": [0.50, 0.66, 0.74, 0.52], "width": 1.25, "priority": 30}
        },
        "red head": {
            "render_anchor_offset": {"x": -24.0, "y": -24.0}, "render_base_offset": {"x": -12.0, "y": -3.0}, "visual_height": 24.0, "light_sample_height": 14.0,
            "ground_footprint": {"shape": "rectangle", "offset": {"x": 0.0, "y": 0.0}, "size": {"x": 14.0, "y": 8.0}},
            "self_shadow": {"mode": "upright_box", "strength": 0.86, "softness": 0.10, "back_fill": 0.06},
            "shadow": {"mode": "upright", "cast_height": 24.0, "length_scale": 0.80, "minimum_length": 2.0, "maximum_length": 72.0, "opacity": 0.58, "near_width": 0.65, "far_width": 1.15, "color": [0.008, 0.004, 0.018], "near_offset": 1.0, "lateral_skew": 0.0, "max_light_distance": 180.0, "fade_with_light_strength": True},
            "outline": {"policy": "shared_player_occluder", "color": [0.74, 0.30, 0.20, 0.52], "width": 1.0, "priority": 20}, "occludes_render_items": False
        },
        "buddha": {
            "render_anchor_offset": {"x": -64.0, "y": -64.0}, "render_base_offset": {"x": -6.0, "y": 61.0}, "visual_height": 128.0, "light_sample_height": 82.0,
            "ground_footprint": {"shape": "rectangle", "offset": {"x": 6.0, "y": 0.0}, "size": {"x": 62.0, "y": 22.0}},
            # Response RGBA stores direct-light survival for down (+Y), up (-Y), left (-X), right (+X).
            "self_shadow": {
                "mode": "directional_profiles",
                "response_texture": {"collection": "textures", "name": "buddha_light_response"},
                "direction_basis": {
                    "mode": "sprite_rect",
                    "rect": {"x": 6.0, "y": 86.0, "width": 110.0, "height": 36.0},
                    # Equal-area base-plate intervals; 0.50 makes an exact corner
                    # a continuous half-and-half handoff between adjacent sides.
                    "ray_grid": {"columns": 7, "rows": 3},
                    "corner_blend_fraction": 0.20,
                    "maximum_adjacent_weight": 0.50
                },
                # A cheap internal occluder for the statue's up/back response.
                # Rays crossing this sprite-local centre line suppress only the
                # green channel, so an upper-left light does not also illuminate
                # the upper-right response (and vice versa). Other profiles keep
                # their authored behaviour, and a centred rear light reaches both.
                "profile_divider": {
                    "enabled": True,
                    "top": {"x": 61.0, "y": 20.0},
                    "bottom": {"x": 61.0, "y": 104.0}
                },
                "strength": 1.0,
                "minimum_direct": 0.04,
                "fallback_mode": "upright_box",
                "softness": 0.14,
                "back_fill": 0.04
            },
            "entity_light_occluder": {"enabled": True, "height": 128.0, "blocks_entity_lighting": True},
            "shadow": {"mode": "upright", "cast_height": 128.0, "length_scale": 1.0, "minimum_length": 8.0, "maximum_length": 160.0, "opacity": 0.48, "near_width": 0.90, "far_width": 1.30, "color": [0.008, 0.004, 0.018], "near_offset": 1.0, "lateral_skew": 0.0, "max_light_distance": 240.0, "fade_with_light_strength": True},
            "outline": {"policy": "never", "color": [0.55, 0.66, 0.72, 0.45], "width": 1.0, "priority": 0}, "occludes_render_items": True
        },
        "pickup": {
            "render_anchor_offset": {"x": -12.0, "y": -12.0}, "render_base_offset": {"x": 0.0, "y": 10.0}, "visual_height": 12.0, "light_sample_height": 6.0,
            "ground_footprint": {"shape": "ellipse", "offset": {"x": 0.0, "y": -1.0}, "size": {"x": 9.0, "y": 5.0}},
            "self_shadow": {"mode": "none", "strength": 0.0, "softness": 0.10, "back_fill": 1.0},
            "outline": {"policy": "shared_player_occluder", "color": [0.78, 0.61, 0.24, 0.55], "width": 1.0, "priority": 10}, "render_style": "readability"
        },
        "grounded": {
            "visual_height": 5.0, "light_sample_height": 2.0,
            "self_shadow": {"mode": "none", "strength": 0.0, "softness": 0.10, "back_fill": 1.0},
            "shadow": {"mode": "grounded", "cast_height": 3.0, "length_scale": 0.45, "minimum_length": 1.0, "maximum_length": 10.0, "opacity": 0.32, "near_width": 0.75, "far_width": 0.90, "color": [0.008, 0.004, 0.018], "near_offset": 0.0, "lateral_skew": 0.0, "max_light_distance": 180.0, "fade_with_light_strength": True}
        }
    }
    result = copy.deepcopy(common)
    deep_fill(result, presets.get(entity_type, {}), overwrite=True)
    return result


def make_grounded_entity_render_metadata():
    return make_default_entity_render_metadata("grounded")


def deep_fill(target, defaults, overwrite=False):
    for key, value in defaults.items():
        if key not in target or overwrite:
            target[key] = copy.deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            deep_fill(target[key], value)
    return target


def get_entity_render_type(entity):
    if entity.get("id") == "player":
        return "player"
    entity_type = str(entity.get("type", "")).lower().replace("_", " ")
    if entity_type in {"pistol ammo pickup", "health pickup"}:
        return "pickup"
    return entity_type


def ensure_entity_render_metadata(entity, entity_type=None):
    render_type = entity_type or get_entity_render_type(entity)
    if str(render_type).lower().replace("_", " ") in {"pistol ammo pickup", "health pickup"}:
        render_type = "pickup"
    defaults = make_default_entity_render_metadata(render_type)
    retired_entity_lighting = entity.pop("entity_lighting", None)

    if retired_entity_lighting is not None and str(render_type).lower().replace("_", " ") in {"player", "red head", "buddha"}:
        footprint = entity.get("ground_footprint", {})
        default_footprint = defaults["ground_footprint"]

        if footprint.get("shape") == "ellipse" and footprint.get("size") == default_footprint["size"]:
            footprint["shape"] = "rectangle"
    had_shadow = "shadow" in entity
    legacy_shadow = entity.get("cinematic_shadow")
    deep_fill(entity, defaults)
    if legacy_shadow and not had_shadow:
        shadow = entity["shadow"]
        shadow["mode"] = "upright" if legacy_shadow.get("enabled", True) else "none"
        for old_key, new_key in (("opacity", "opacity"), ("near_width", "near_width"), ("far_width", "far_width"), ("color", "color"), ("near_offset", "near_offset"), ("lateral_skew", "lateral_skew"), ("max_light_distance", "max_light_distance"), ("fade_with_light_strength", "fade_with_light_strength")):
            if old_key in legacy_shadow:
                shadow[new_key] = copy.deepcopy(legacy_shadow[old_key])
    entity.pop("cinematic_shadow", None)
    entity.setdefault("occludes_player", bool(entity.get("occludes_render_items", False)))
    entity.setdefault("outline_player_when_behind", bool(entity.get("occludes_render_items", False)))
    return entity


def position_to_world(position, tile_map):
    return {"x": float(position.get("tile_x", 0)) * float(tile_map.get("tile_width", 0)) + float(position.get("x", 0.0)), "y": float(position.get("tile_y", 0)) * float(tile_map.get("tile_height", 0)) + float(position.get("y", 0.0))}


def offset_point(point, offset):
    return {"x": float(point["x"]) + float(offset.get("x", 0.0)), "y": float(point["y"]) + float(offset.get("y", 0.0))}


def make_texture_reference(collection, name, field=None):
    result = {"collection": collection, "name": name}
    if field is not None:
        result["field"] = field
    return result


def make_world_render_item(kind, source, source_id, object_id, entity, world_position, width, height, texture, source_rect, draw_data=None):
    ensure_entity_render_metadata(entity, source if source in {"player", "red head", "buddha"} else kind)
    anchor = entity.get("render_anchor_offset", {})
    base = offset_point(world_position, entity.get("render_base_offset", {}))
    dest = {"x": world_position["x"] + float(anchor.get("x", 0.0)), "y": world_position["y"] + float(anchor.get("y", 0.0)), "width": float(width), "height": float(height)}
    return {
        "kind": kind, "source": source, "source_id": source_id, "id": object_id, "texture": texture, "source_rect": dict(source_rect), "dest_rect": dest,
        "sort_layer": "world", "sort_y": float(base["y"]), "base_world": base, "bounds_world": dict(dest), "visual_height": float(entity.get("visual_height", height)),
        "light_sample_height": float(entity.get("light_sample_height", entity.get("visual_height", height) * 0.55)), "ground_footprint": copy.deepcopy(entity.get("ground_footprint", {})),
        "self_shadow": copy.deepcopy(entity.get("self_shadow", {})), "entity_light_occluder": copy.deepcopy(entity.get("entity_light_occluder", {})), "shadow": copy.deepcopy(entity.get("shadow", {})), "render_style": entity.get("render_style", "world"),
        "outline": copy.deepcopy(entity.get("outline", {})), "occludes_render_items": bool(entity.get("occludes_render_items", False)), "fog_interaction": copy.deepcopy(entity.get("fog_interaction", {"mode": "standard"})),
        "water_interaction": copy.deepcopy(entity.get("water_interaction", {"mode": "standard"})), "draw_data": copy.deepcopy(draw_data or {})
    }


def _asset_dimension(game_assets, collection, name, dimension, fallback):
    asset = game_assets.get(collection, {}).get(name)
    if isinstance(asset, dict):
        asset = asset.get("sheet")
    try:
        return float(getattr(asset, dimension, fallback) if asset is not None else fallback)
    except (TypeError, ValueError):
        return float(fallback)


def build_player_render_item(player_entity, tile_map, game_assets):
    ensure_entity_render_metadata(player_entity, "player")
    world_position = position_to_world(player_entity.get("position", {}), tile_map)
    sprite_sheet = game_assets.get("sprite_sheets", {}).get("blue_oxford_texture_sheet", {})
    frame_number = sprite_sheet.get(player_entity.get("animation_frame", 0), 0)
    aim = normalize_vector(player_entity.get("aim_direction", {"x": 0.0, "y": 0.0})) or {"x": 0.0, "y": 0.0}
    gun_position = {"x": world_position["x"] + aim["x"] * 4.0, "y": world_position["y"] + aim["y"] * 4.0}
    pistol_position = dict(gun_position)
    pistol_texture = "pistol_texture"
    pistol_angle = math.degrees(math.atan2(aim["y"], aim["x"]))
    if aim["x"] < 0.0:
        pistol_position = {"x": gun_position["x"] + aim["x"] * 4.0, "y": gun_position["y"] + aim["y"] * 4.0}
        pistol_texture = "pistol_texture_flipped"
        pistol_angle += 180.0
    draw_data = {"center_world": dict(world_position), "gun_world": gun_position, "pistol_world": pistol_position, "pistol_texture": pistol_texture, "pistol_angle": pistol_angle}
    render_item = make_world_render_item("entity", "player", "player", player_entity.get("id", "player"), player_entity, world_position, 32.0, 32.0, make_texture_reference("sprite_sheets", "blue_oxford_texture_sheet", "sheet"), {"x": float(frame_number) * 32.0, "y": 0.0, "width": 32.0, "height": 32.0}, draw_data)
    render_item["screen_snap"] = "relative_motion"
    return render_item


def build_brain_render_item(object_id, entity, tile_map, game_assets):
    entity_type = get_entity_render_type(entity)
    if entity_type not in {"red head", "buddha"}:
        return None
    ensure_entity_render_metadata(entity, entity_type)
    world_position = position_to_world(entity.get("position", {}), tile_map)
    if entity_type == "red head":
        sprite_sheet = game_assets.get("sprite_sheets", {}).get("red_head_texture_sheet", {})
        frame_number = sprite_sheet.get(entity.get("animation_frame", 0), 0)
        return make_world_render_item("entity", entity_type, f"brains:{object_id}", object_id, entity, world_position, 24.0, 24.0, make_texture_reference("sprite_sheets", "red_head_texture_sheet", "sheet"), {"x": float(frame_number) * 24.0, "y": 0.0, "width": 24.0, "height": 24.0})
    width = _asset_dimension(game_assets, "textures", "buddha_texture", "width", 128.0)
    height = _asset_dimension(game_assets, "textures", "buddha_texture", "height", 128.0)
    return make_world_render_item("entity", entity_type, f"brains:{object_id}", object_id, entity, world_position, width, height, make_texture_reference("textures", "buddha_texture"), {"x": 0.0, "y": 0.0, "width": width, "height": height})


def build_pickup_render_item(object_id, entity, tile_map, game_assets):
    pickup_type = str(entity.get("type", ""))
    texture_names = {"pistol_ammo_pickup": "pistol_ammo_pickup_texture", "health_pickup": "health_pickup_texture"}
    texture_name = texture_names.get(pickup_type)
    if texture_name is None:
        return None
    ensure_entity_render_metadata(entity, "pickup")
    world_position = position_to_world(entity.get("position", {}), tile_map)
    source_width = _asset_dimension(game_assets, "textures", texture_name, "width", 8.0)
    source_height = _asset_dimension(game_assets, "textures", texture_name, "height", 8.0)
    return make_world_render_item("pickup", pickup_type, f"pickups:{object_id}", object_id, entity, world_position, source_width * 3.0, source_height * 3.0, make_texture_reference("textures", texture_name), {"x": 0.0, "y": 0.0, "width": source_width, "height": source_height})


def build_sorted_world_render_items(entities, player_entity, tile_map, game_assets):
    render_items = []
    if player_entity is not None:
        render_items.append(build_player_render_item(player_entity, tile_map, game_assets))
    for object_id, entity in entities.get("brains", {}).items():
        item = build_brain_render_item(object_id, entity, tile_map, game_assets)
        if item is not None:
            render_items.append(item)
    for object_id, entity in entities.get("pickups", {}).items():
        item = build_pickup_render_item(object_id, entity, tile_map, game_assets)
        if item is not None:
            render_items.append(item)
    return sort_world_render_items(render_items)


def render_item_sort_key(item):
    return (SORT_LAYER_ORDER.get(item.get("sort_layer", "world"), 100), float(item.get("sort_y", 0.0)), str(item.get("source_id", item.get("id", ""))))


def sort_world_render_items(render_items):
    return sorted(render_items, key=render_item_sort_key)


def bounds_overlap(a, b):
    return a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"] and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"]


def world_bounds_to_screen(bounds, game_camera):
    camera_x = float(game_camera.get("x", 0.0)) if isinstance(game_camera, dict) else float(getattr(game_camera, "x", 0.0))
    camera_y = float(game_camera.get("y", 0.0)) if isinstance(game_camera, dict) else float(getattr(game_camera, "y", 0.0))
    return {"x": bounds["x"] - camera_x, "y": bounds["y"] - camera_y, "width": bounds["width"], "height": bounds["height"]}


def get_world_ground_footprint(render_item):
    footprint = render_item.get("ground_footprint", {})
    offset = footprint.get("offset", {})
    base = render_item.get("base_world", {})
    size = footprint.get("size", {})
    return {"shape": footprint.get("shape", "rectangle"), "center": {"x": float(base.get("x", 0.0)) + float(offset.get("x", 0.0)), "y": float(base.get("y", 0.0)) + float(offset.get("y", 0.0))}, "size": {"x": max(0.0, float(size.get("x", 0.0))), "y": max(0.0, float(size.get("y", 0.0)))}}


def build_major_entity_light_occluders(render_items):
    return [item for item in render_items if item.get("entity_light_occluder", {}).get("enabled", False) and item.get("entity_light_occluder", {}).get("blocks_entity_lighting", False)]


def find_occluders_for_item(render_items, target_item):
    result = []
    target_bounds = target_item.get("bounds_world", {})
    target_sort_y = float(target_item.get("sort_y", 0.0))
    for item in render_items:
        if item is target_item or not item.get("occludes_render_items", item.get("occludes_player", False)) or float(item.get("sort_y", 0.0)) <= target_sort_y:
            continue
        if bounds_overlap(target_bounds, item.get("bounds_world", {})):
            result.append(item)
    return result


def build_render_occlusion_groups(render_items):
    targets = {}
    occluders = {}
    for item in render_items:
        item_occluders = find_occluders_for_item(render_items, item)
        if not item_occluders:
            continue
        source_id = item.get("source_id", str(item.get("id")))
        targets[source_id] = item_occluders
        for occluder in item_occluders:
            occluder_id = occluder.get("source_id", str(occluder.get("id")))
            occluders.setdefault(occluder_id, []).append(item)
    return {"targets": targets, "occluders": occluders}


def find_items_requiring_outline(render_items, occlusion_groups=None):
    groups = occlusion_groups or build_render_occlusion_groups(render_items)
    target_groups = groups.get("targets", {})
    player_occluders = {item.get("source_id", str(item.get("id"))) for item in target_groups.get("player", [])}
    result = []
    for item in render_items:
        source_id = item.get("source_id", str(item.get("id")))
        item_occluders = target_groups.get(source_id, [])
        if not item_occluders:
            continue
        policy = item.get("outline", {}).get("policy", "never")
        eligible = policy in {"always_when_occluded", "player_when_occluded"}
        if policy == "shared_player_occluder":
            eligible = any(occluder.get("source_id", str(occluder.get("id"))) in player_occluders for occluder in item_occluders)
        if eligible:
            result.append({"item": item, "occluders": item_occluders})
    return sorted(result, key=lambda entry: int(entry["item"].get("outline", {}).get("priority", 0)))


def find_player_occluders(render_items, game_camera=None, require_outline=False):
    player = get_player_render_item(render_items)
    if player is None:
        return []
    result = find_occluders_for_item(render_items, player)
    if require_outline:
        if player.get("outline", {}).get("policy") == "never":
            return []
        result = [item for item in result if item.get("outline_player_when_behind", item.get("occludes_render_items", False))]
    return result


def get_player_render_item(render_items):
    return next((item for item in render_items if item.get("source_id") == "player" or item.get("source") == "player"), None)


def calculate_shadow_length(shadow, horizontal_distance, light_height, fallback_cast_height=0.0):
    mode = shadow.get("mode", "none")
    if mode == "none":
        return None
    cast_height = max(0.0, float(shadow.get("cast_height", fallback_cast_height)))
    if cast_height <= 0.0001:
        return None
    minimum = max(0.0, float(shadow.get("minimum_length", 2.0)))
    maximum = max(minimum, float(shadow.get("maximum_length", 160.0)))
    if float(light_height) > cast_height + 0.0001:
        raw_length = max(0.0, float(horizontal_distance)) * cast_height / (float(light_height) - cast_height)
    else:
        raw_length = maximum
    length = raw_length * max(0.0, float(shadow.get("length_scale", 1.0)))
    if mode == "grounded":
        maximum = min(maximum, 16.0)
    return max(minimum, min(maximum, length))


def normalize_vector(value):
    x = float(value.get("x", 0.0))
    y = float(value.get("y", 0.0))
    length = math.hypot(x, y)
    if length <= 0.000001:
        return None
    return {"x": x / length, "y": y / length}
