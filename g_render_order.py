import copy
import math


SORT_LAYER_ORDER = {
    "floor": 0,
    "world": 100,
    "overlay": 200
}


def make_default_entity_render_metadata(entity_type):
    entity_type = str(entity_type or "").lower().replace("_", " ")
    presets = {
        "player": {
            "render_anchor_offset": {"x": -16.0, "y": -16.0},
            "render_base_offset": {"x": 0.0, "y": 14.0},
            "visual_height": 32.0,
            "occludes_player": False,
            "outline_player_when_behind": False
        },
        "red head": {
            "render_anchor_offset": {"x": -24.0, "y": -24.0},
            "render_base_offset": {"x": -12.0, "y": -3.0},
            "visual_height": 24.0,
            "occludes_player": True,
            "outline_player_when_behind": False
        },
        "buddha": {
            "render_anchor_offset": {"x": -64.0, "y": -64.0},
            "render_base_offset": {"x": -6.0, "y": 61.0},
            "visual_height": 128.0,
            "occludes_player": True,
            "outline_player_when_behind": True
        }
    }
    return copy.deepcopy(presets.get(entity_type, {
        "render_anchor_offset": {"x": 0.0, "y": 0.0},
        "render_base_offset": {"x": 0.0, "y": 0.0},
        "visual_height": 0.0,
        "occludes_player": False,
        "outline_player_when_behind": False
    }))


def get_entity_render_type(entity):
    if entity.get("id") == "player":
        return "player"
    return str(entity.get("type", "")).lower().replace("_", " ")


def ensure_entity_render_metadata(entity, entity_type=None):
    defaults = make_default_entity_render_metadata(entity_type or get_entity_render_type(entity))
    for key, value in defaults.items():
        if key not in entity:
            entity[key] = copy.deepcopy(value)
    return entity


def position_to_world(position, tile_map):
    return {
        "x": float(position.get("tile_x", 0)) * float(tile_map.get("tile_width", 0)) + float(position.get("x", 0.0)),
        "y": float(position.get("tile_y", 0)) * float(tile_map.get("tile_height", 0)) + float(position.get("y", 0.0))
    }


def offset_point(point, offset):
    return {"x": float(point["x"]) + float(offset.get("x", 0.0)), "y": float(point["y"]) + float(offset.get("y", 0.0))}


def make_texture_reference(collection, name, field=None):
    result = {"collection": collection, "name": name}
    if field is not None:
        result["field"] = field
    return result


def make_world_render_item(source, object_id, entity, world_position, width, height, texture, source_rect, draw_data=None):
    ensure_entity_render_metadata(entity, source)
    anchor = entity.get("render_anchor_offset", {})
    base = offset_point(world_position, entity.get("render_base_offset", {}))
    dest = {"x": world_position["x"] + float(anchor.get("x", 0.0)), "y": world_position["y"] + float(anchor.get("y", 0.0)), "width": float(width), "height": float(height)}
    bounds = {"x": dest["x"], "y": dest["y"], "width": dest["width"], "height": dest["height"]}
    return {
        "kind": "entity",
        "source": source,
        "id": object_id,
        "texture": texture,
        "source_rect": dict(source_rect),
        "dest_rect": dest,
        "sort_layer": "world",
        "sort_y": float(base["y"]),
        "base_world": base,
        "bounds_world": bounds,
        "visual_height": float(entity.get("visual_height", height)),
        "occludes_player": bool(entity.get("occludes_player", False)),
        "outline_player_when_behind": bool(entity.get("outline_player_when_behind", False)),
        "can_receive_outline": source == "player",
        "draw_data": copy.deepcopy(draw_data or {})
    }


def _asset_dimension(game_assets, collection, name, dimension, fallback):
    asset = game_assets.get(collection, {}).get(name)
    if isinstance(asset, dict):
        asset = asset.get("sheet")
    value = getattr(asset, dimension, fallback) if asset is not None else fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def build_player_render_item(player_entity, tile_map, game_assets):
    ensure_entity_render_metadata(player_entity, "player")
    world_position = position_to_world(player_entity.get("position", {}), tile_map)
    sprite_sheet = game_assets.get("sprite_sheets", {}).get("blue_oxford_texture_sheet", {})
    frame_key = player_entity.get("animation_frame", 0)
    frame_number = sprite_sheet.get(frame_key, 0)
    aim = normalize_vector(player_entity.get("aim_direction", {"x": 0.0, "y": 0.0}))
    gun_position = {"x": world_position["x"] + aim["x"] * 4.0, "y": world_position["y"] + aim["y"] * 4.0}
    pistol_position = dict(gun_position)
    pistol_texture = "pistol_texture"
    pistol_angle = math.degrees(math.atan2(aim["y"], aim["x"]))
    if aim["x"] < 0.0:
        pistol_position = {"x": gun_position["x"] + aim["x"] * 4.0, "y": gun_position["y"] + aim["y"] * 4.0}
        pistol_texture = "pistol_texture_flipped"
        pistol_angle += 180.0
    draw_data = {
        "center_world": dict(world_position),
        "gun_world": gun_position,
        "pistol_world": pistol_position,
        "pistol_texture": pistol_texture,
        "pistol_angle": pistol_angle
    }
    return make_world_render_item("player", player_entity.get("id", "player"), player_entity, world_position, 32.0, 32.0, make_texture_reference("sprite_sheets", "blue_oxford_texture_sheet", "sheet"), {"x": float(frame_number) * 32.0, "y": 0.0, "width": 32.0, "height": 32.0}, draw_data)


def build_brain_render_item(object_id, entity, tile_map, game_assets):
    entity_type = get_entity_render_type(entity)
    if entity_type not in {"red head", "buddha"}:
        return None
    ensure_entity_render_metadata(entity, entity_type)
    world_position = position_to_world(entity.get("position", {}), tile_map)
    if entity_type == "red head":
        sprite_sheet = game_assets.get("sprite_sheets", {}).get("red_head_texture_sheet", {})
        frame_number = sprite_sheet.get(entity.get("animation_frame", 0), 0)
        return make_world_render_item(entity_type, object_id, entity, world_position, 24.0, 24.0, make_texture_reference("sprite_sheets", "red_head_texture_sheet", "sheet"), {"x": float(frame_number) * 24.0, "y": 0.0, "width": 24.0, "height": 24.0})
    width = _asset_dimension(game_assets, "textures", "buddha_texture", "width", 128.0)
    height = _asset_dimension(game_assets, "textures", "buddha_texture", "height", 128.0)
    return make_world_render_item(entity_type, object_id, entity, world_position, width, height, make_texture_reference("textures", "buddha_texture"), {"x": 0.0, "y": 0.0, "width": width, "height": height})


def build_sorted_world_render_items(entities, player_entity, tile_map, game_assets):
    render_items = []
    if player_entity is not None:
        render_items.append(build_player_render_item(player_entity, tile_map, game_assets))
    for object_id, entity in entities.get("brains", {}).items():
        item = build_brain_render_item(object_id, entity, tile_map, game_assets)
        if item is not None:
            render_items.append(item)
    return sort_world_render_items(render_items)


def render_item_sort_key(item):
    return (SORT_LAYER_ORDER.get(item.get("sort_layer", "world"), 100), float(item.get("sort_y", 0.0)), str(item.get("id", "")))


def sort_world_render_items(render_items):
    return sorted(render_items, key=render_item_sort_key)


def bounds_overlap(a, b):
    return a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"] and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"]


def world_bounds_to_screen(bounds, game_camera):
    camera_x = float(game_camera.get("x", 0.0)) if isinstance(game_camera, dict) else float(getattr(game_camera, "x", 0.0))
    camera_y = float(game_camera.get("y", 0.0)) if isinstance(game_camera, dict) else float(getattr(game_camera, "y", 0.0))
    return {"x": bounds["x"] - camera_x, "y": bounds["y"] - camera_y, "width": bounds["width"], "height": bounds["height"]}


def find_player_occluders(render_items, game_camera=None, require_outline=False):
    player_item = next((item for item in render_items if item.get("source") == "player"), None)
    if player_item is None:
        return []
    player_bounds = world_bounds_to_screen(player_item["bounds_world"], game_camera) if game_camera is not None else player_item["bounds_world"]
    result = []
    for item in render_items:
        if item is player_item or not item.get("occludes_player", False):
            continue
        if float(item.get("sort_y", 0.0)) <= float(player_item.get("sort_y", 0.0)):
            continue
        if require_outline and not item.get("outline_player_when_behind", False):
            continue
        item_bounds = world_bounds_to_screen(item["bounds_world"], game_camera) if game_camera is not None else item["bounds_world"]
        if bounds_overlap(player_bounds, item_bounds):
            result.append(item)
    return result


def get_player_render_item(render_items):
    return next((item for item in render_items if item.get("source") == "player"), None)


def normalize_vector(value):
    x = float(value.get("x", 0.0))
    y = float(value.get("y", 0.0))
    length = math.sqrt(x * x + y * y)
    if length <= 0.000001:
        return {"x": 0.0, "y": 0.0}
    return {"x": x / length, "y": y / length}
