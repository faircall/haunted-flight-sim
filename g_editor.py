import copy
import math

import pyray as pr

import g_ui

EDITOR_MODES = ("play", "tile", "entity", "environment")
EDITOR_TOOLS = ("select", "place")
PLACEMENT_TYPES = ("point_light", "spot_light", "top_down_light", "fog_volume")
RENDER_STYLES = ("world", "readability")
MOBILITY_OPTIONS = ("static", "dynamic")

def make_editor_state():
    return {
        "tool": "select",
        "placement_type": "point_light",
        "selected_kind": None,
        "selected_id": None,
        "drag_kind": None,
        "drag_offset": {"x": 0.0, "y": 0.0},
        "preview_effects": True,
        "show_handles": True,
        "snap_enabled": False,
        "snap_size": 4.0,
        "inspector_tab": "object",
        "inspector_collapsed": False,
        "inspector_scroll": 0.0,
        "sections": {
            "lighting_appearance": True,
            "lighting_stylisation": True,
            "fog_appearance": True,
            "fog_motion": False,
            "fog_lighting": False,
            "fog_stylisation": False
        }
    }

def get_or_create_editor_state(game_assets):
    editor_state = game_assets.get("editor_state")

    if editor_state is None:
        editor_state = make_editor_state()
        game_assets["editor_state"] = editor_state
    else:
        defaults = make_editor_state()

        for key, value in defaults.items():
            editor_state.setdefault(key, copy.deepcopy(value))

    return editor_state

def migrate_editor_mode(editor_mode):
    return {
        "editing": "tile",
        "entity_placing": "entity",
        "light_placing": "environment"
    }.get(editor_mode, editor_mode if editor_mode in EDITOR_MODES else "tile")

def tile_position_to_world(position, tile_map):
    return {
        "x": float(position.get("tile_x", 0)) * tile_map["tile_width"] + float(position.get("x", 0.0)),
        "y": float(position.get("tile_y", 0)) * tile_map["tile_height"] + float(position.get("y", 0.0))
    }

def world_to_tile_position(world_position, tile_map):
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    world_x = float(world_position.get("x", 0.0))
    world_y = float(world_position.get("y", 0.0))
    tile_x = math.floor(world_x / tile_width)
    tile_y = math.floor(world_y / tile_height)
    return {
        "tile_x": int(tile_x),
        "tile_y": int(tile_y),
        "x": world_x - tile_x * tile_width,
        "y": world_y - tile_y * tile_height
    }

def snap_world_position(world_position, editor_state):
    if not editor_state.get("snap_enabled", False):
        return dict(world_position)

    snap_size = max(0.001, float(editor_state.get("snap_size", 4.0)))
    return {
        "x": round(world_position["x"] / snap_size) * snap_size,
        "y": round(world_position["y"] / snap_size) * snap_size
    }

def make_default_point_light(position):
    return {
        "type": "point",
        "position": copy.deepcopy(position),
        "color": [1.0, 0.82, 0.62],
        "radius": 120.0,
        "intensity": 1.0,
        "falloff": 1.6,
        "enabled": True,
        "affects_scene": True,
        "affects_world": True,
        "affects_entities": True,
        "affects_fog": True,
        "affects_ai": True,
        "casts_wall_shadows": True,
        "casts_cinematic_shadows": False,
        "gameplay_intensity": 1.0,
        "mobility": "static",
        "render_style": "world",
        "height": 32.0,
        "shadow_bias": 0.25
    }

def make_default_spot_light(position):
    result = make_default_point_light(position)
    result["type"] = "spot"
    result["direction"] = {"x": 1.0, "y": 0.0}
    result["near_fade_distance"] = 8.0
    result["inner_angle"] = 18.0
    result["outer_angle"] = 32.0
    return result

def make_default_top_down_light(position):
    return {
        "type": "top_down",
        "position": copy.deepcopy(position),
        "size": {"x": 180.0, "y": 110.0},
        "color": [0.72, 0.76, 1.0],
        "intensity": 0.65,
        "edge_softness": 24.0,
        "enabled": True,
        "affects_scene": True,
        "affects_world": True,
        "affects_entities": True,
        "affects_fog": True,
        "affects_ai": True,
        "mobility": "static",
        "render_style": "world",
        "height": 180.0
    }

def make_default_fog_volume(position):
    return {
        "type": "fog_volume",
        "shape": "ellipse",
        "position": copy.deepcopy(position),
        "size": {"x": 180.0, "y": 110.0},
        "edge_softness": 24.0,
        "strength": 1.0,
        "enabled": True
    }

def migrate_environment_data(entities):
    collection_names = {entry["target_collection"] for entry in ENVIRONMENT_OBJECT_REGISTRY.values()}

    for collection_name in collection_names:
        entities.setdefault(collection_name, {})

    lights = entities["lights"]
    maximum_id = 0

    for collection_name in collection_names:
        for object_id in entities[collection_name]:
            try:
                maximum_id = max(maximum_id, int(str(object_id).rsplit(":", 1)[-1]))
            except ValueError:
                pass

    entities["next_environment_object_id"] = max(int(entities.get("next_environment_object_id", 1)), maximum_id + 1)

    for light in lights.values():
        light.setdefault("render_style", "world")
        legacy_scene = bool(light.get("affects_scene", True))
        light.setdefault("affects_world", legacy_scene)
        light.setdefault("affects_entities", legacy_scene)
        light.setdefault("height", 180.0 if light.get("type") == "top_down" else 32.0)

    return entities

def allocate_environment_object_id(entities, prefix):
    migrate_environment_data(entities)
    next_id = int(entities["next_environment_object_id"])
    entities["next_environment_object_id"] = next_id + 1
    return f"{prefix}:{next_id}"

def create_environment_object(entities, placement_type, position):
    registry_entry = ENVIRONMENT_OBJECT_REGISTRY[placement_type]
    collection = entities.setdefault(registry_entry["target_collection"], {})
    object_id = allocate_environment_object_id(entities, registry_entry["id_prefix"])
    collection[object_id] = registry_entry["factory"](position)
    return registry_entry["selected_kind"], object_id

def seed_example_environment(entities, tile_map):
    migrate_environment_data(entities)

    if entities.get("environment_examples_seeded", False):
        return

    point_position = world_to_tile_position({"x": 200.0, "y": 300.0}, tile_map)
    fog_position = world_to_tile_position({"x": 648.0, "y": 40.0}, tile_map)
    create_environment_object(entities, "point_light", point_position)
    create_environment_object(entities, "fog_volume", fog_position)
    entities["environment_examples_seeded"] = True

def registry_entry_for_object(selected_kind, object_value):
    object_type = object_value.get("type")

    for registry_key, registry_entry in ENVIRONMENT_OBJECT_REGISTRY.items():
        if registry_entry["selected_kind"] == selected_kind and registry_entry["object_type"] == object_type:
            return registry_key, registry_entry

    return None, None

def collection_name_for_selected_kind(selected_kind):
    for registry_entry in ENVIRONMENT_OBJECT_REGISTRY.values():
        if registry_entry["selected_kind"] == selected_kind:
            return registry_entry["target_collection"]

    return None

def get_selected_object(entities, editor_state):
    selected_kind = editor_state.get("selected_kind")
    selected_id = editor_state.get("selected_id")
    collection_name = collection_name_for_selected_kind(selected_kind)

    if collection_name is None:
        return None

    return entities.get(collection_name, {}).get(selected_id)

def validate_selection(entities, editor_state):
    if get_selected_object(entities, editor_state) is None:
        editor_state["selected_kind"] = None
        editor_state["selected_id"] = None
        editor_state["drag_kind"] = None

def delete_selected_environment_object(entities, editor_state):
    selected_kind = editor_state.get("selected_kind")
    selected_id = editor_state.get("selected_id")
    collection_name = collection_name_for_selected_kind(selected_kind)

    if collection_name is None or selected_id not in entities.get(collection_name, {}):
        return False

    del entities[collection_name][selected_id]
    editor_state["selected_kind"] = None
    editor_state["selected_id"] = None
    editor_state["drag_kind"] = None
    return True

def duplicate_selected_environment_object(entities, editor_state, tile_map):
    selected = get_selected_object(entities, editor_state)

    if selected is None:
        return None

    selected_kind = editor_state["selected_kind"]
    registry_key, registry_entry = registry_entry_for_object(selected_kind, selected)

    if registry_entry is None:
        return None

    collection_name = registry_entry["target_collection"]
    prefix = registry_entry["id_prefix"]
    duplicate = copy.deepcopy(selected)
    world_position = tile_position_to_world(duplicate["position"], tile_map)
    world_position["x"] += 8.0
    world_position["y"] += 8.0
    duplicate["position"] = world_to_tile_position(world_position, tile_map)
    object_id = allocate_environment_object_id(entities, prefix)
    entities[collection_name][object_id] = duplicate
    editor_state["selected_id"] = object_id
    return object_id

def normalize_spot_direction(direction):
    x = float(direction.get("x", 0.0))
    y = float(direction.get("y", 0.0))
    length = math.hypot(x, y)

    if length <= 0.000001:
        return {"x": 1.0, "y": 0.0}

    return {"x": x / length, "y": y / length}

def clamp_spot_angles(inner_angle, outer_angle, minimum_separation=0.5):
    inner = max(0.0, min(88.5, float(inner_angle)))
    outer = max(inner + minimum_separation, min(89.0, float(outer_angle)))

    if outer > 89.0:
        outer = 89.0
        inner = min(inner, outer - minimum_separation)

    return inner, outer

def distance_squared(a, b):
    return (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2

def point_in_fog_volume(world_point, volume, tile_map, padding=0.0):
    centre = tile_position_to_world(volume.get("position", {}), tile_map)
    size = volume.get("size", {})
    half_width = max(0.0, float(size.get("x", 0.0))) * 0.5 + padding
    half_height = max(0.0, float(size.get("y", 0.0))) * 0.5 + padding
    dx = world_point["x"] - centre["x"]
    dy = world_point["y"] - centre["y"]

    if volume.get("shape", "ellipse") == "rectangle":
        return abs(dx) <= half_width and abs(dy) <= half_height

    if half_width <= 0.0 or half_height <= 0.0:
        return False

    return (dx / half_width) ** 2 + (dy / half_height) ** 2 <= 1.0

def hit_test_fog_volume(world_point, volume, tile_map):
    return point_in_fog_volume(world_point, volume, tile_map, 4.0)

def hit_test_light(world_point, light, tile_map, handle_radius=7.0):
    centre = tile_position_to_world(light.get("position", {}), tile_map)

    if distance_squared(world_point, centre) <= handle_radius ** 2:
        return True

    light_type = light.get("type", "point")

    if light_type in {"point", "spot"}:
        radius = max(0.0, float(light.get("radius", 0.0)))
        radius_handle = {"x": centre["x"] + radius, "y": centre["y"]}

        if distance_squared(world_point, radius_handle) <= handle_radius ** 2:
            return True

        if light_type == "spot":
            direction = normalize_spot_direction(light.get("direction", {}))
            direction_handle = {"x": centre["x"] + direction["x"] * min(radius, 48.0), "y": centre["y"] + direction["y"] * min(radius, 48.0)}
            return distance_squared(world_point, direction_handle) <= handle_radius ** 2

    if light_type == "top_down":
        size = light.get("size", {})
        half_width = max(0.0, float(size.get("x", 0.0))) * 0.5
        half_height = max(0.0, float(size.get("y", 0.0))) * 0.5
        resize_handle = {"x": centre["x"] + half_width, "y": centre["y"] + half_height}
        return distance_squared(world_point, resize_handle) <= handle_radius ** 2

    return False

def selection_hit_priority(world_point, object_value, selected_kind, tile_map):
    centre = tile_position_to_world(object_value.get("position", {}), tile_map)

    if distance_squared(world_point, centre) <= 7.0 ** 2:
        return 0, distance_squared(world_point, centre)

    registry_key, registry_entry = registry_entry_for_object(selected_kind, object_value)

    if registry_entry is not None and registry_entry["hit_test"](world_point, object_value, tile_map):
        return registry_entry.get("hit_priority", 1), distance_squared(world_point, centre)

    return None

def select_environment_object_at(entities, editor_state, world_point, tile_map):
    selected_kind = editor_state.get("selected_kind")
    selected_id = editor_state.get("selected_id")
    candidates = []

    seen_objects = set()

    for registry_entry in ENVIRONMENT_OBJECT_REGISTRY.values():
        collection_name = registry_entry["target_collection"]

        for object_id, object_value in entities.get(collection_name, {}).items():
            object_key = (collection_name, object_id)

            if object_key in seen_objects or object_value.get("type") != registry_entry["object_type"]:
                continue

            seen_objects.add(object_key)
            object_kind = registry_entry["selected_kind"]
            hit = selection_hit_priority(world_point, object_value, object_kind, tile_map)

            if hit is not None:
                candidates.append((0 if selected_kind == object_kind and selected_id == object_id else 1, hit[0], hit[1], object_kind, object_id))

    if not candidates:
        editor_state["selected_kind"] = None
        editor_state["selected_id"] = None
        return None

    chosen = min(candidates)
    editor_state["selected_kind"] = chosen[3]
    editor_state["selected_id"] = chosen[4]
    return chosen[3], chosen[4]

def get_drag_handle(world_point, selected, selected_kind, tile_map):
    centre = tile_position_to_world(selected["position"], tile_map)

    if distance_squared(world_point, centre) <= 7.0 ** 2:
        return "move"

    if selected_kind == "fog_volume":
        size = selected.get("size", {})
        x_handle = {"x": centre["x"] + float(size.get("x", 0.0)) * 0.5, "y": centre["y"]}
        y_handle = {"x": centre["x"], "y": centre["y"] + float(size.get("y", 0.0)) * 0.5}

        if distance_squared(world_point, x_handle) <= 7.0 ** 2:
            return "size_x"
        if distance_squared(world_point, y_handle) <= 7.0 ** 2:
            return "size_y"
        return None

    light_type = selected.get("type", "point")

    if light_type in {"point", "spot"}:
        radius = float(selected.get("radius", 0.0))
        radius_handle = {"x": centre["x"] + radius, "y": centre["y"]}

        if distance_squared(world_point, radius_handle) <= 7.0 ** 2:
            return "radius"

        if light_type == "spot":
            direction = normalize_spot_direction(selected.get("direction", {}))
            direction_handle = {"x": centre["x"] + direction["x"] * min(radius, 48.0), "y": centre["y"] + direction["y"] * min(radius, 48.0)}

            if distance_squared(world_point, direction_handle) <= 7.0 ** 2:
                return "direction"

    if light_type == "top_down":
        size = selected.get("size", {})
        resize_handle = {"x": centre["x"] + float(size.get("x", 0.0)) * 0.5, "y": centre["y"] + float(size.get("y", 0.0)) * 0.5}

        if distance_squared(world_point, resize_handle) <= 7.0 ** 2:
            return "size_xy"

    return None

def apply_environment_drag(selected, selected_kind, drag_kind, world_point, tile_map, editor_state):
    centre = tile_position_to_world(selected["position"], tile_map)

    if drag_kind == "move":
        drag_offset = editor_state.get("drag_offset", {"x": 0.0, "y": 0.0})
        moved_position = {"x": world_point["x"] + drag_offset.get("x", 0.0), "y": world_point["y"] + drag_offset.get("y", 0.0)}
        selected["position"] = world_to_tile_position(snap_world_position(moved_position, editor_state), tile_map)
    elif drag_kind == "radius":
        selected["radius"] = max(4.0, math.hypot(world_point["x"] - centre["x"], world_point["y"] - centre["y"]))
    elif drag_kind == "direction":
        selected["direction"] = normalize_spot_direction({"x": world_point["x"] - centre["x"], "y": world_point["y"] - centre["y"]})
    elif drag_kind == "size_x":
        selected["size"]["x"] = max(4.0, abs(world_point["x"] - centre["x"]) * 2.0)
    elif drag_kind == "size_y":
        selected["size"]["y"] = max(4.0, abs(world_point["y"] - centre["y"]) * 2.0)
    elif drag_kind == "size_xy":
        selected["size"]["x"] = max(4.0, abs(world_point["x"] - centre["x"]) * 2.0)
        selected["size"]["y"] = max(4.0, abs(world_point["y"] - centre["y"]) * 2.0)

def mouse_world_position(game_camera):
    mouse = g_ui.get_mouse_position()
    return {"x": mouse.x + game_camera.x, "y": mouse.y + game_camera.y}

def world_to_screen(world_position, game_camera):
    return {"x": world_position["x"] - game_camera.x, "y": world_position["y"] - game_camera.y}

def draw_handle(screen_position, color, radius=3):
    pr.draw_circle(int(screen_position["x"]), int(screen_position["y"]), radius + 1, pr.BLACK)
    pr.draw_circle(int(screen_position["x"]), int(screen_position["y"]), radius, color)

def draw_light_handles(object_id, light, game_camera, tile_map, selected):
    centre_world = tile_position_to_world(light["position"], tile_map)
    centre = world_to_screen(centre_world, game_camera)
    enabled = light.get("enabled", True)
    color = pr.Color(255, 205, 90, 255) if enabled else pr.Color(110, 105, 120, 220)
    selected_color = pr.Color(100, 230, 255, 255)
    draw_handle(centre, selected_color if selected else color, 4 if selected else 3)
    light_type = light.get("type", "point")

    if light_type in {"point", "spot"}:
        radius = max(0.0, float(light.get("radius", 0.0)))
        pr.draw_circle_lines(int(centre["x"]), int(centre["y"]), radius, selected_color if selected else color)
        radius_handle = {"x": centre["x"] + radius, "y": centre["y"]}
        draw_handle(radius_handle, selected_color if selected else color)

        if light_type == "spot":
            direction = normalize_spot_direction(light.get("direction", {}))
            inner, outer = clamp_spot_angles(light.get("inner_angle", 18.0), light.get("outer_angle", 32.0))

            for angle, cone_color in ((-outer, color), (outer, color), (-inner, selected_color), (inner, selected_color)):
                base_angle = math.atan2(direction["y"], direction["x"]) + math.radians(angle)
                end = {"x": centre["x"] + math.cos(base_angle) * radius, "y": centre["y"] + math.sin(base_angle) * radius}
                pr.draw_line(int(centre["x"]), int(centre["y"]), int(end["x"]), int(end["y"]), cone_color)

            direction_handle = {"x": centre["x"] + direction["x"] * min(radius, 48.0), "y": centre["y"] + direction["y"] * min(radius, 48.0)}
            pr.draw_line(int(centre["x"]), int(centre["y"]), int(direction_handle["x"]), int(direction_handle["y"]), selected_color)
            draw_handle(direction_handle, selected_color)
    else:
        size = light.get("size", {})
        width = float(size.get("x", 0.0))
        height = float(size.get("y", 0.0))
        rect = pr.Rectangle(centre["x"] - width * 0.5, centre["y"] - height * 0.5, width, height)
        pr.draw_rectangle_lines_ex(rect, 2.0 if selected else 1.0, selected_color if selected else color)
        draw_handle({"x": rect.x + rect.width, "y": rect.y + rect.height}, selected_color if selected else color)

    if selected:
        pr.draw_text(str(object_id), int(centre["x"] + 6), int(centre["y"] - 10), 8, selected_color)

def draw_fog_volume_handles(object_id, volume, game_camera, tile_map, selected):
    centre_world = tile_position_to_world(volume["position"], tile_map)
    centre = world_to_screen(centre_world, game_camera)
    size = volume.get("size", {})
    width = float(size.get("x", 0.0))
    height = float(size.get("y", 0.0))
    color = pr.Color(120, 205, 255, 255) if volume.get("enabled", True) else pr.Color(95, 105, 115, 220)
    selected_color = pr.Color(255, 230, 115, 255)
    outline = selected_color if selected else color

    if volume.get("shape", "ellipse") == "ellipse":
        pr.draw_ellipse_lines(int(centre["x"]), int(centre["y"]), width * 0.5, height * 0.5, outline)
    else:
        pr.draw_rectangle_lines_ex(pr.Rectangle(centre["x"] - width * 0.5, centre["y"] - height * 0.5, width, height), 2.0 if selected else 1.0, outline)

    softness = max(0.0, float(volume.get("edge_softness", 0.0)))

    if selected and softness > 0.0:
        inner_width = max(0.0, width - softness * 2.0)
        inner_height = max(0.0, height - softness * 2.0)
        pr.draw_rectangle_lines_ex(pr.Rectangle(centre["x"] - inner_width * 0.5, centre["y"] - inner_height * 0.5, inner_width, inner_height), 1.0, pr.Color(120, 205, 255, 130))

    draw_handle(centre, outline, 4 if selected else 3)
    draw_handle({"x": centre["x"] + width * 0.5, "y": centre["y"]}, outline)
    draw_handle({"x": centre["x"], "y": centre["y"] + height * 0.5}, outline)

    if selected:
        pr.draw_text(str(object_id), int(centre["x"] + 6), int(centre["y"] - 10), 8, selected_color)

def draw_environment_handles(entities, editor_state, game_camera, tile_map):
    if not editor_state.get("show_handles", True):
        return

    drawn_objects = set()

    for registry_entry in ENVIRONMENT_OBJECT_REGISTRY.values():
        collection_name = registry_entry["target_collection"]

        for object_id, object_value in entities.get(collection_name, {}).items():
            object_key = (collection_name, object_id)

            if object_key in drawn_objects or object_value.get("type") != registry_entry["object_type"]:
                continue

            drawn_objects.add(object_key)
            selected = editor_state.get("selected_kind") == registry_entry["selected_kind"] and editor_state.get("selected_id") == object_id
            registry_entry["handles"](object_id, object_value, game_camera, tile_map, selected)

def draw_placement_preview(editor_state, game_camera, tile_map):
    placement_type = editor_state.get("placement_type", "point_light")
    world_position = snap_world_position(mouse_world_position(game_camera), editor_state)
    position = world_to_tile_position(world_position, tile_map)
    preview = ENVIRONMENT_OBJECT_REGISTRY[placement_type]["factory"](position)

    if placement_type == "fog_volume":
        draw_fog_volume_handles("new", preview, game_camera, tile_map, True)
    else:
        draw_light_handles("new", preview, game_camera, tile_map, True)

def update_environment_world(entities, editor_state, ui_state, game_camera, tile_map):
    validate_selection(entities, editor_state)
    mouse_world = mouse_world_position(game_camera)
    selected = get_selected_object(entities, editor_state)
    registry_key, registry_entry = registry_entry_for_object(editor_state.get("selected_kind"), selected) if selected else (None, None)

    escape_pressed = pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE) and ui_state.get("focused_id") is None
    cancel_pressed = pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT) or escape_pressed

    if cancel_pressed:
        had_drag = editor_state.get("drag_kind") is not None
        editor_state["drag_kind"] = None

        if editor_state.get("tool") == "place":
            editor_state["tool"] = "select"
        elif escape_pressed and not had_drag:
            editor_state["selected_kind"] = None
            editor_state["selected_id"] = None

    if ui_state.get("mouse_captured"):
        return

    if editor_state.get("tool") == "place":
        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
            placement_type = editor_state.get("placement_type", "point_light")
            snapped_world = snap_world_position(mouse_world, editor_state)
            kind, object_id = create_environment_object(entities, placement_type, world_to_tile_position(snapped_world, tile_map))
            editor_state["selected_kind"] = kind
            editor_state["selected_id"] = object_id
        return

    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        drag_kind = registry_entry["handle_hit_test"](mouse_world, selected, editor_state.get("selected_kind"), tile_map) if registry_entry else None

        if drag_kind is None:
            select_environment_object_at(entities, editor_state, mouse_world, tile_map)
            selected = get_selected_object(entities, editor_state)
            registry_key, registry_entry = registry_entry_for_object(editor_state.get("selected_kind"), selected) if selected else (None, None)
            drag_kind = registry_entry["handle_hit_test"](mouse_world, selected, editor_state.get("selected_kind"), tile_map) if registry_entry else None

        editor_state["drag_kind"] = drag_kind

        if drag_kind == "move" and selected is not None:
            centre = tile_position_to_world(selected["position"], tile_map)
            editor_state["drag_offset"] = {"x": centre["x"] - mouse_world["x"], "y": centre["y"] - mouse_world["y"]}

    if editor_state.get("drag_kind") and pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT):
        selected = get_selected_object(entities, editor_state)
        registry_key, registry_entry = registry_entry_for_object(editor_state.get("selected_kind"), selected) if selected else (None, None)

        if registry_entry is not None:
            registry_entry["manipulate"](selected, editor_state["selected_kind"], editor_state["drag_kind"], mouse_world, tile_map, editor_state)
            ui_state["mouse_captured"] = True

    if pr.is_mouse_button_released(pr.MouseButton.MOUSE_BUTTON_LEFT):
        editor_state["drag_kind"] = None

def capture_editor_ui_regions(ui_state, editor_state, editor_mode):
    mouse = g_ui.get_mouse_position()
    toolbar_rect = pr.Rectangle(0, 0, 480, 38)
    inspector_rect = pr.Rectangle(306, 38, 174, 232)

    inspector_visible = editor_mode == "environment" and not editor_state.get("inspector_collapsed", False)

    if g_ui.ui_point_in_rect(mouse, toolbar_rect) or (inspector_visible and g_ui.ui_point_in_rect(mouse, inspector_rect)):
        g_ui.ui_capture_mouse(ui_state)

def update_editor_shortcuts(entities, editor_state, ui_state, tile_map):
    if ui_state.get("focused_id") is not None:
        return

    control_down = pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KeyboardKey.KEY_RIGHT_CONTROL)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_DELETE):
        delete_selected_environment_object(entities, editor_state)
    if control_down and pr.is_key_pressed(pr.KeyboardKey.KEY_D):
        duplicate_selected_environment_object(entities, editor_state, tile_map)
    if pr.is_key_pressed(pr.KeyboardKey.KEY_Q):
        editor_state["tool"] = "select"
    if pr.is_key_pressed(pr.KeyboardKey.KEY_P):
        editor_state["tool"] = "place"

def draw_editor_toolbar(ui_state, editor_state, editor_mode, entities, tile_map):
    pr.draw_rectangle(0, 0, 480, 38, g_ui.UI_BACKGROUND)
    editor_mode, _ = g_ui.ui_dropdown(ui_state, "toolbar:mode", "", editor_mode, EDITOR_MODES, pr.Rectangle(2, 2, 78, 16), 4)
    editor_state["tool"], _ = g_ui.ui_dropdown(ui_state, "toolbar:tool", "", editor_state.get("tool", "select"), EDITOR_TOOLS, pr.Rectangle(82, 2, 66, 16), 2)

    if editor_mode == "environment":
        editor_state["placement_type"], _ = g_ui.ui_dropdown(ui_state, "toolbar:placement", "", editor_state.get("placement_type", "point_light"), PLACEMENT_TYPES, pr.Rectangle(150, 2, 98, 16), 4)

    editor_state["preview_effects"], _ = g_ui.ui_checkbox(ui_state, "toolbar:preview", "fx", editor_state.get("preview_effects", True), pr.Rectangle(252, 3, 38, 14))
    editor_state["snap_enabled"], _ = g_ui.ui_checkbox(ui_state, "toolbar:snap", "snap", editor_state.get("snap_enabled", False), pr.Rectangle(292, 3, 48, 14))
    editor_state["snap_size"], _ = g_ui.ui_number_input_float(ui_state, "toolbar:snap_size", "", editor_state.get("snap_size", 4.0), 0.25, 64.0, pr.Rectangle(342, 2, 52, 16))

    if get_selected_object(entities, editor_state) is not None:
        if g_ui.ui_button(ui_state, "toolbar:duplicate", "dup", pr.Rectangle(396, 2, 38, 16)):
            duplicate_selected_environment_object(entities, editor_state, tile_map)
        if g_ui.ui_button(ui_state, "toolbar:delete", "del", pr.Rectangle(436, 2, 40, 16)):
            delete_selected_environment_object(entities, editor_state)

    if pr.is_key_down(pr.KeyboardKey.KEY_H):
        g_ui.ui_label(ui_state, "toolbar:hint", "Q select  P place  Ctrl+D duplicate  Del delete", pr.Rectangle(4, 22, 310, 12), g_ui.UI_MUTED, 8)
    return editor_mode

def edit_world_position(ui_state, widget_id, value, tile_map):
    world = tile_position_to_world(value, tile_map)
    edited, changed = g_ui.ui_vec2_input(ui_state, widget_id, "position", world)
    return world_to_tile_position(edited, tile_map) if changed else value

def inspect_common_light(ui_state, widget_id, light, include_shadows=True):
    light["enabled"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:enabled", "enabled", light.get("enabled", True))
    g_ui.ui_label(ui_state, f"{widget_id}:type", f"type: {light.get('type', 'point')}", font_size=8)
    light["render_style"], _ = g_ui.ui_dropdown(ui_state, f"{widget_id}:render_style", "style", light.get("render_style", "world"), RENDER_STYLES)
    light["mobility"], _ = g_ui.ui_dropdown(ui_state, f"{widget_id}:mobility", "mobility", light.get("mobility", "static"), MOBILITY_OPTIONS)
    light["color"], _ = g_ui.ui_color3_editor(ui_state, f"{widget_id}:color", "color", light.get("color", [1.0, 1.0, 1.0]))
    light["intensity"], _ = g_ui.ui_slider_float(ui_state, f"{widget_id}:intensity", "intensity", light.get("intensity", 1.0), 0.0, 5.0, 0.01)
    light["affects_world"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:world", "affects world", light.get("affects_world", light.get("affects_scene", True)))
    light["affects_entities"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:entities", "affects entities", light.get("affects_entities", light.get("affects_scene", True)))
    light["affects_scene"] = light["affects_world"] or light["affects_entities"]
    light["affects_fog"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:fog", "affects fog", light.get("affects_fog", True))
    light["affects_ai"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:ai", "affects ai", light.get("affects_ai", True))
    light["gameplay_intensity"], _ = g_ui.ui_slider_float(ui_state, f"{widget_id}:gameplay", "gameplay", light.get("gameplay_intensity", 1.0), 0.0, 5.0, 0.05)
    light["height"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:height", "height", light.get("height", 32.0), 0.0, 1000.0)

    if include_shadows:
        light["casts_wall_shadows"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:wall_shadows", "wall shadows", light.get("casts_wall_shadows", True))
        light["casts_cinematic_shadows"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:cinematic", "cinematic shadows", light.get("casts_cinematic_shadows", False))

def inspect_point_light(ui_state, editor_state, object_id, light, tile_map):
    widget_id = f"object:{object_id}"
    inspect_common_light(ui_state, widget_id, light)
    light["position"] = edit_world_position(ui_state, f"{widget_id}:position", light["position"], tile_map)
    light["radius"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:radius", "radius", light.get("radius", 120.0), 4.0, 2000.0)
    light["falloff"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:falloff", "falloff", light.get("falloff", 1.6), 0.01, 10.0)
    light["shadow_bias"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:bias", "shadow bias", light.get("shadow_bias", 0.25), 0.0, 8.0)

def inspect_spot_light(ui_state, editor_state, object_id, light, tile_map):
    inspect_point_light(ui_state, editor_state, object_id, light, tile_map)
    widget_id = f"object:{object_id}"
    direction, changed = g_ui.ui_vec2_input(ui_state, f"{widget_id}:direction", "direction", light.get("direction", {"x": 1.0, "y": 0.0}), -1.0, 1.0)

    if changed:
        light["direction"] = normalize_spot_direction(direction)

    light["near_fade_distance"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:near", "near fade", light.get("near_fade_distance", 8.0), 0.0, 500.0)
    inner, _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:inner", "inner angle", light.get("inner_angle", 18.0), 0.0, 88.5)
    outer, _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:outer", "outer angle", light.get("outer_angle", 32.0), 0.5, 89.0)
    light["inner_angle"], light["outer_angle"] = clamp_spot_angles(inner, outer)

def inspect_top_down_light(ui_state, editor_state, object_id, light, tile_map):
    widget_id = f"object:{object_id}"
    inspect_common_light(ui_state, widget_id, light, False)
    light["position"] = edit_world_position(ui_state, f"{widget_id}:position", light["position"], tile_map)
    light["size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:size", "size", light.get("size", {"x": 180.0, "y": 110.0}), 4.0, 4000.0)
    light["edge_softness"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:softness", "edge softness", light.get("edge_softness", 24.0), 0.0, 1000.0)

def inspect_fog_volume(ui_state, editor_state, object_id, volume, tile_map):
    widget_id = f"object:{object_id}"
    volume["enabled"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:enabled", "enabled", volume.get("enabled", True))
    volume["shape"], _ = g_ui.ui_dropdown(ui_state, f"{widget_id}:shape", "shape", volume.get("shape", "ellipse"), ("rectangle", "ellipse"))
    volume["position"] = edit_world_position(ui_state, f"{widget_id}:position", volume["position"], tile_map)
    volume["size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:size", "size", volume.get("size", {"x": 180.0, "y": 110.0}), 4.0, 4000.0)
    volume["edge_softness"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:softness", "edge softness", volume.get("edge_softness", 24.0), 0.0, 1000.0)
    volume["strength"], _ = g_ui.ui_slider_float(ui_state, f"{widget_id}:strength", "strength", volume.get("strength", 1.0), 0.0, 2.0, 0.01)

def section_button(ui_state, editor_state, section_id, title):
    sections = editor_state.setdefault("sections", {})
    opened = sections.get(section_id, True)

    if g_ui.ui_button(ui_state, f"section:{section_id}", f"{'-' if opened else '+'} {title}"):
        opened = not opened
        sections[section_id] = opened

    return opened

def inspect_lighting_profile(ui_state, editor_state, profile):
    if section_button(ui_state, editor_state, "lighting_appearance", "Lighting appearance"):
        profile["ambient_color"], _ = g_ui.ui_color3_editor(ui_state, "world:lighting:ambient_color", "ambient color", profile.get("ambient_color", [0.2, 0.2, 0.3]))
        profile["ambient_strength"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:ambient_strength", "ambient", profile.get("ambient_strength", 0.3), 0.0, 2.0, 0.01)
        profile["direct_light_strength"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:direct", "direct", profile.get("direct_light_strength", 1.0), 0.0, 3.0, 0.01)
        profile["shadow_color"], _ = g_ui.ui_color3_editor(ui_state, "world:lighting:shadow_color", "shadow color", profile.get("shadow_color", [0.0, 0.0, 0.0]))
        profile["black_point"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:black", "black point", profile.get("black_point", 0.1), 0.0, 1.0, 0.005)
        profile["shadow_softness"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:softness", "softness", profile.get("shadow_softness", 0.03), 0.0, 1.0, 0.005)
        profile["shadow_detail"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:detail", "detail", profile.get("shadow_detail", 0.0), 0.0, 1.0, 0.01)
        profile["contrast"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:contrast", "contrast", profile.get("contrast", 1.0), 0.25, 3.0, 0.01)

    if section_button(ui_state, editor_state, "lighting_stylisation", "Lighting stylisation"):
        profile["light_posterize_enabled"], _ = g_ui.ui_checkbox(ui_state, "world:lighting:posterize", "posterize", profile.get("light_posterize_enabled", True))
        profile["light_posterize_levels"], _ = g_ui.ui_number_input_float(ui_state, "world:lighting:levels", "levels", profile.get("light_posterize_levels", 12.0), 2.0, 64.0)
        profile["light_dither_enabled"], _ = g_ui.ui_checkbox(ui_state, "world:lighting:dither", "dither", profile.get("light_dither_enabled", False))
        profile["light_dither_strength"], _ = g_ui.ui_slider_float(ui_state, "world:lighting:dither_strength", "dither", profile.get("light_dither_strength", 1.0), 0.0, 4.0, 0.01)
        profile["posterize_ambient"], _ = g_ui.ui_checkbox(ui_state, "world:lighting:posterize_ambient", "posterize ambient", profile.get("posterize_ambient", False))

def inspect_fog_profile(ui_state, editor_state, profile):
    if section_button(ui_state, editor_state, "fog_appearance", "Fog appearance"):
        profile["enabled"], _ = g_ui.ui_checkbox(ui_state, "world:fog:enabled", "enabled", profile.get("enabled", True))
        profile["color"], _ = g_ui.ui_color3_editor(ui_state, "world:fog:color", "color", profile.get("color", [0.62, 0.70, 0.86]))

        for name, minimum, maximum in (("density", 0.0, 2.0), ("opacity", 0.0, 1.0), ("world_scale", 0.001, 0.2), ("detail_scale", 0.1, 10.0), ("cutoff", 0.0, 1.0), ("softness", 0.001, 1.0), ("global_amount", 0.0, 1.0)):
            profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:fog:{name}", name.replace("_", " "), profile.get(name, minimum), minimum, maximum, 0.005)

    if section_button(ui_state, editor_state, "fog_motion", "Fog motion"):
        profile["drift"], _ = g_ui.ui_vec2_input(ui_state, "world:fog:drift", "drift", profile.get("drift", {"x": 0.0, "y": 0.0}), -100.0, 100.0)
        profile["detail_drift"], _ = g_ui.ui_vec2_input(ui_state, "world:fog:detail_drift", "detail drift", profile.get("detail_drift", {"x": -2.0, "y": 3.5}), -100.0, 100.0)

        for name, minimum, maximum in (("evolution_speed", 0.0, 2.0), ("warp_scale", 0.01, 4.0), ("warp_strength", 0.0, 5.0), ("detail_evolution_speed", 0.0, 2.0)):
            profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:fog:{name}", name.replace("_", " "), profile.get(name, minimum), minimum, maximum, 0.005)

    if section_button(ui_state, editor_state, "fog_lighting", "Fog lighting"):
        for name, minimum, maximum in (("light_strength", 0.0, 5.0), ("ambient_strength", 0.0, 3.0), ("veil_strength", 0.0, 1.0)):
            profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:fog:{name}", name.replace("_", " "), profile.get(name, minimum), minimum, maximum, 0.01)

    if section_button(ui_state, editor_state, "fog_stylisation", "Fog stylisation"):
        profile["posterize_enabled"], _ = g_ui.ui_checkbox(ui_state, "world:fog:posterize", "posterize", profile.get("posterize_enabled", True))
        profile["posterize_levels"], _ = g_ui.ui_number_input_float(ui_state, "world:fog:levels", "levels", profile.get("posterize_levels", 6.0), 2.0, 64.0)
        profile["dither_enabled"], _ = g_ui.ui_checkbox(ui_state, "world:fog:dither", "dither", profile.get("dither_enabled", False))
        profile["dither_strength"], _ = g_ui.ui_slider_float(ui_state, "world:fog:dither_strength", "dither", profile.get("dither_strength", 1.0), 0.0, 4.0, 0.01)

def draw_inspector(ui_state, editor_state, entities, lighting_profile, fog_profile, tile_map):
    collapse_rect = pr.Rectangle(308, 40, 14, 14)

    if g_ui.ui_button(ui_state, "inspector:collapse", "<" if editor_state.get("inspector_collapsed", False) else ">", collapse_rect):
        editor_state["inspector_collapsed"] = not editor_state.get("inspector_collapsed", False)

    if editor_state.get("inspector_collapsed", False):
        return

    panel_rect = pr.Rectangle(324, 38, 156, 232)

    if g_ui.ui_point_in_rect(g_ui.get_mouse_position(), panel_rect) and ui_state.get("open_dropdown_id") is None:
        editor_state["inspector_scroll"] = max(0.0, editor_state.get("inspector_scroll", 0.0) - pr.get_mouse_wheel_move() * 18.0)

    g_ui.ui_begin_panel(ui_state, "inspector:panel", panel_rect, "Environment", editor_state.get("inspector_scroll", 0.0))
    object_tab = g_ui.ui_button(ui_state, "inspector:object_tab", "Object", g_ui.ui_next_rect(ui_state, 14, 70))
    world_tab = g_ui.ui_button(ui_state, "inspector:world_tab", "World", g_ui.ui_next_rect(ui_state, 14, 70))

    if object_tab:
        editor_state["inspector_tab"] = "object"
    if world_tab:
        editor_state["inspector_tab"] = "world"

    if editor_state.get("inspector_tab", "object") == "world":
        inspect_lighting_profile(ui_state, editor_state, lighting_profile)
        g_ui.ui_separator(ui_state, "inspector:world_separator")
        inspect_fog_profile(ui_state, editor_state, fog_profile)
    else:
        selected = get_selected_object(entities, editor_state)

        if selected is None:
            g_ui.ui_label(ui_state, "inspector:none", "No environment object selected", color=g_ui.UI_MUTED, font_size=8)
        else:
            object_id = editor_state["selected_id"]
            registry_key, registry_entry = registry_entry_for_object(editor_state["selected_kind"], selected)
            g_ui.ui_label(ui_state, "inspector:selected", object_id, color=g_ui.UI_ACCENT, font_size=8)

            if registry_entry is not None:
                registry_entry["inspector"](ui_state, editor_state, object_id, selected, tile_map)

    g_ui.ui_end_panel(ui_state)

def draw_editor_overlay(ui_state, editor_state, editor_mode, entities, lighting_profile, fog_profile, game_camera, tile_map, show_editor):
    if not show_editor:
        return editor_mode
    editor_mode = draw_editor_toolbar(ui_state, editor_state, editor_mode, entities, tile_map)

    if editor_mode == "environment":
        update_editor_shortcuts(entities, editor_state, ui_state, tile_map)
        update_environment_world(entities, editor_state, ui_state, game_camera, tile_map)
        draw_environment_handles(entities, editor_state, game_camera, tile_map)

        if editor_state.get("tool") == "place" and not ui_state.get("mouse_captured"):
            draw_placement_preview(editor_state, game_camera, tile_map)

        draw_inspector(ui_state, editor_state, entities, lighting_profile, fog_profile, tile_map)

    return editor_mode

ENVIRONMENT_OBJECT_REGISTRY = {
    "point_light": {
        "target_collection": "lights",
        "object_type": "point",
        "factory": make_default_point_light,
        "display_name": "Point light",
        "icon": "*",
        "debug_color": (255, 205, 90),
        "selected_kind": "light",
        "id_prefix": "light",
        "inspector": inspect_point_light,
        "hit_test": hit_test_light,
        "hit_priority": 1,
        "handles": draw_light_handles,
        "handle_hit_test": get_drag_handle,
        "manipulate": apply_environment_drag
    },
    "spot_light": {
        "target_collection": "lights",
        "object_type": "spot",
        "factory": make_default_spot_light,
        "display_name": "Spot light",
        "icon": ">",
        "debug_color": (255, 160, 80),
        "selected_kind": "light",
        "id_prefix": "light",
        "inspector": inspect_spot_light,
        "hit_test": hit_test_light,
        "hit_priority": 1,
        "handles": draw_light_handles,
        "handle_hit_test": get_drag_handle,
        "manipulate": apply_environment_drag
    },
    "top_down_light": {
        "target_collection": "lights",
        "object_type": "top_down",
        "factory": make_default_top_down_light,
        "display_name": "Top-down light",
        "icon": "[]",
        "debug_color": (180, 195, 255),
        "selected_kind": "light",
        "id_prefix": "light",
        "inspector": inspect_top_down_light,
        "hit_test": hit_test_light,
        "hit_priority": 1,
        "handles": draw_light_handles,
        "handle_hit_test": get_drag_handle,
        "manipulate": apply_environment_drag
    },
    "fog_volume": {
        "target_collection": "fog_volumes",
        "object_type": "fog_volume",
        "factory": make_default_fog_volume,
        "display_name": "Fog volume",
        "icon": "~",
        "debug_color": (120, 205, 255),
        "selected_kind": "fog_volume",
        "id_prefix": "fog",
        "inspector": inspect_fog_volume,
        "hit_test": hit_test_fog_volume,
        "hit_priority": 2,
        "handles": draw_fog_volume_handles,
        "handle_hit_test": get_drag_handle,
        "manipulate": apply_environment_drag
    }
}
