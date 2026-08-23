import copy
import math

import pyray as pr

import g_audio
import g_effects
import g_render_order
import g_ui

EDITOR_MODES = ("play", "tile", "entity", "animation", "environment")
EDITOR_TOOLS = ("select", "place")
ANIMATION_DEBUG_PLAYBACK_MODES = ("continuous", "keyframe")
PLACEMENT_TYPES = ()
RENDER_STYLES = ("world", "readability")
MOBILITY_OPTIONS = ("static", "dynamic")

def make_editor_state():
    return {
        "tool": "place",
        "placement_type": "point_light",
        "placement_radius_overrides": {},
        "selected_kind": None,
        "selected_collection": None,
        "selected_id": None,
        "drag_kind": None,
        "drag_offset": {"x": 0.0, "y": 0.0},
        "tile_paint_previous": None,
        "tile_paint_mode": None,
        "preview_effects": True,
        "tile_edit_mode": "appearance",
        "rain_exposure_value": 1.0,
        "show_rain_exposure_overlay": True,
        "acoustic_zone_value": 0,
        "footstep_overlay_value": "none",
        "show_acoustic_zone_overlay": True,
        "show_footstep_overlay": True,
        "audio_debug": {
            "show_stats": False,
            "show_world": False,
            "show_acoustic_zones": False,
            "show_contact_overlays": False,
        },
        "animation_debug": {
            "playback": "continuous",
            "track": "walk",
            "facing": "right",
            "keyframe": 0,
            "phase": 0.0,
            "cycle_seconds": 1.0,
            "target_key": None,
        },
        "rain_debug": {
            "show_exposure_overlay": False,
            "show_raw_exposure_texture": False,
            "show_raw_streak_mask": False,
            "show_distortion_mask": False,
            "show_sampled_light_amount": False,
            "disable_streak_color": False,
            "disable_distortion": False,
            "show_stats": False,
        },
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
            "fog_stylisation": False,
            "wind": True,
            "rain": True,
            "rain_debug": False,
            "audio": False,
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
        for key, value in defaults["rain_debug"].items():
            editor_state["rain_debug"].setdefault(key, value)
        for key, value in defaults["audio_debug"].items():
            editor_state["audio_debug"].setdefault(key, value)
        for key, value in defaults["animation_debug"].items():
            editor_state["animation_debug"].setdefault(key, value)

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

    g_effects.migrate_emitters(entities.get("emitters", {}))
    g_audio.migrate_sound_emitters(entities.get("sound_emitters", {}))

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

def adjust_environment_object_radius(object_value, radial, wheel_amount):
    try:
        wheel_amount = float(wheel_amount)
    except (TypeError, ValueError, OverflowError):
        return False

    if not math.isfinite(wheel_amount) or abs(wheel_amount) <= 0.000001:
        return False

    if not isinstance(object_value, dict) or not isinstance(radial, dict):
        return False

    field = radial.get("field")
    if not isinstance(field, str) or field not in object_value:
        return False
    try:
        current = float(object_value[field])
        step = max(0.000001, float(radial.get("step", 8.0)))
        minimum = float(radial.get("minimum", 0.0))
        maximum = max(minimum, float(radial.get("maximum", 4000.0)))
        minimum_field = radial.get("minimum_field")
        if isinstance(minimum_field, str):
            minimum = max(
                minimum,
                float(object_value.get(minimum_field, minimum))
                + float(radial.get("minimum_gap", 0.0)),
            )
    except (TypeError, ValueError, OverflowError):
        return False

    adjusted = max(minimum, min(maximum, current + wheel_amount * step))
    if abs(adjusted - current) <= 0.000001:
        return False
    object_value[field] = adjusted
    return True

def adjust_selected_environment_radius(entities, editor_state, wheel_amount):
    """Adjust the selected object's primary radial extent from editor input."""
    selected = get_selected_object(entities, editor_state)
    if selected is None:
        return False
    _registry_key, registry_entry = registry_entry_for_object(
        editor_state.get("selected_kind"), selected,
    )
    radial = registry_entry.get("radial_wheel") if registry_entry else None
    if not adjust_environment_object_radius(selected, radial, wheel_amount):
        return False
    if editor_state.get("selected_kind") == "sound_emitter":
        g_audio.normalize_sound_emitter(selected)
    return True

def apply_placement_radius_override(editor_state, placement_type, object_value):
    registry_entry = ENVIRONMENT_OBJECT_REGISTRY.get(placement_type, {})
    radial = registry_entry.get("radial_wheel")
    overrides = editor_state.setdefault("placement_radius_overrides", {})
    if not isinstance(radial, dict) or placement_type not in overrides:
        return object_value
    field = radial.get("field")
    if isinstance(field, str) and field in object_value:
        object_value[field] = float(overrides[placement_type])
        if registry_entry.get("selected_kind") == "sound_emitter":
            g_audio.normalize_sound_emitter(object_value)
    return object_value

def adjust_placement_preview_radius(editor_state, wheel_amount):
    placement_type = editor_state.get("placement_type", "point_light")
    registry_entry = ENVIRONMENT_OBJECT_REGISTRY.get(placement_type, {})
    radial = registry_entry.get("radial_wheel")
    if not isinstance(radial, dict):
        return False
    preview = registry_entry["factory"]({
        "tile_x": 0, "tile_y": 0, "x": 0.0, "y": 0.0,
    })
    apply_placement_radius_override(editor_state, placement_type, preview)
    if not adjust_environment_object_radius(preview, radial, wheel_amount):
        return False
    if registry_entry.get("selected_kind") == "sound_emitter":
        g_audio.normalize_sound_emitter(preview)
    editor_state.setdefault("placement_radius_overrides", {})[
        placement_type
    ] = float(preview[radial["field"]])
    return True

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

GAMEPLAY_ENTITY_COLLECTIONS = ("brains", "pickups")

def gameplay_entity_selection_bounds(entity, tile_map):
    entity_type = str(entity.get("type", ""))
    world = tile_position_to_world(entity.get("position", {}), tile_map)
    anchor = entity.get("render_anchor_offset", {})
    default_size = {
        "player": (32.0, 32.0),
        "buddha": (128.0, 128.0),
        "red head": (24.0, 24.0),
        "pistol_ammo_pickup": (24.0, 24.0),
        "health_pickup": (24.0, 24.0),
    }.get("player" if entity.get("id") == "player" else entity_type, (
        max(8.0, float(entity.get("entity_width", 16.0))),
        max(8.0, float(entity.get("entity_height", 16.0))),
    ))
    return {
        "x": world["x"] + float(anchor.get("x", -default_size[0] * 0.5)),
        "y": world["y"] + float(anchor.get("y", -default_size[1] * 0.5)),
        "width": default_size[0], "height": default_size[1],
    }

def gameplay_entity_bounds_contains(bounds, world_point, padding=3.0):
    return (
        bounds["x"] - padding <= world_point["x"] <= bounds["x"] + bounds["width"] + padding
        and bounds["y"] - padding <= world_point["y"] <= bounds["y"] + bounds["height"] + padding
    )

def get_selected_gameplay_entity(entities, editor_state):
    if editor_state.get("selected_kind") != "gameplay_entity":
        return None
    collection_name = editor_state.get("selected_collection")
    if collection_name not in GAMEPLAY_ENTITY_COLLECTIONS:
        return None
    return entities.get(collection_name, {}).get(editor_state.get("selected_id"))


def iter_animation_debug_entities(entities, player_entity=None):
    if isinstance(player_entity, dict):
        yield "player", player_entity.get("id", "player"), player_entity
    for collection_name in GAMEPLAY_ENTITY_COLLECTIONS:
        for entity_id, entity in entities.get(collection_name, {}).items():
            if isinstance(entity, dict):
                yield collection_name, entity_id, entity


def get_selected_animation_entity(entities, player_entity, editor_state):
    if editor_state.get("selected_kind") != "animation_entity":
        return None
    collection_name = editor_state.get("selected_collection")
    entity_id = editor_state.get("selected_id")
    if collection_name == "player":
        if (isinstance(player_entity, dict)
                and entity_id == player_entity.get("id", "player")):
            return player_entity
        return None
    if collection_name not in GAMEPLAY_ENTITY_COLLECTIONS:
        return None
    return entities.get(collection_name, {}).get(entity_id)


def select_animation_entity_at(entities, player_entity, editor_state,
                               world_point, tile_map):
    previous_collection = editor_state.get("selected_collection")
    previous_id = editor_state.get("selected_id")
    candidates = []
    for collection_name, entity_id, entity in iter_animation_debug_entities(
            entities, player_entity):
        bounds = gameplay_entity_selection_bounds(entity, tile_map)
        if not gameplay_entity_bounds_contains(bounds, world_point):
            continue
        centre_x = bounds["x"] + bounds["width"] * 0.5
        centre_y = bounds["y"] + bounds["height"] * 0.5
        distance = (
            (world_point["x"] - centre_x) ** 2
            + (world_point["y"] - centre_y) ** 2
        )
        candidates.append({
            "sort_key": (
                0 if (collection_name == previous_collection
                      and entity_id == previous_id) else 1,
                bounds["width"] * bounds["height"], distance,
                collection_name, str(entity_id),
            ),
            "collection": collection_name,
            "id": entity_id,
        })
    if not candidates:
        editor_state.update({
            "selected_kind": None, "selected_collection": None,
            "selected_id": None, "drag_kind": None,
        })
        return None
    chosen = min(candidates, key=lambda candidate: candidate["sort_key"])
    editor_state.update({
        "selected_kind": "animation_entity",
        "selected_collection": chosen["collection"],
        "selected_id": chosen["id"],
        "drag_kind": None,
    })
    return chosen["collection"], chosen["id"]


PLAYER_ANIMATION_DEBUG_POSE_NAMES = {
    "walk": ("contact", "passing", "opposite contact", "recovery"),
    "run": ("contact", "recoil / passing", "opposite contact", "flight / recovery"),
}


def player_animation_debug_pose_names(profile_name, profile):
    authored = PLAYER_ANIMATION_DEBUG_POSE_NAMES.get(profile_name, ())
    if len(authored) == len(profile):
        return authored
    return tuple(f"pose {index + 1}" for index in range(len(profile)))


def animation_debug_tracks_for_entity(entity, collection_name):
    if collection_name == "player" or entity.get("id") == "player":
        return {
            profile_name: {
                "kind": "procedural_gait",
                "pose_names": player_animation_debug_pose_names(
                    profile_name, profile,
                ),
            }
            for profile_name, profile in
            g_render_order.PLAYER_CUTOUT_GAIT_PROFILES.items()
        }
    if str(entity.get("type", "")) == "red head":
        return {
            "direction poses": {
                "kind": "sprite_frames",
                "pose_names": ("down", "right", "up", "left"),
                "frames": (
                    "down_frame_start", "right_frame_start",
                    "up_frame_start", "left_frame_start",
                ),
            },
        }
    return {}


def update_animation_debug_preview(editor_state, editor_mode, entities,
                                   player_entity, dt):
    if editor_mode != "animation":
        return None
    entity = get_selected_animation_entity(
        entities, player_entity, editor_state,
    )
    if entity is None:
        return None
    collection_name = editor_state.get("selected_collection")
    entity_id = editor_state.get("selected_id")
    tracks = animation_debug_tracks_for_entity(entity, collection_name)
    if not tracks:
        return None

    debug = editor_state.setdefault(
        "animation_debug", make_editor_state()["animation_debug"],
    )
    target_key = (collection_name, entity_id)
    if debug.get("target_key") != target_key:
        debug["target_key"] = target_key
        debug["phase"] = 0.0
        debug["keyframe"] = 0
    track_name = debug.get("track")
    if track_name not in tracks:
        track_name = next(iter(tracks))
        debug["track"] = track_name
        debug["phase"] = 0.0
        debug["keyframe"] = 0
    track = tracks[track_name]
    pose_names = tuple(track.get("pose_names", ()))
    pose_count = max(1, len(pose_names))
    playback = debug.get("playback", "continuous")
    if playback not in ANIMATION_DEBUG_PLAYBACK_MODES:
        playback = "continuous"
        debug["playback"] = playback
    try:
        phase = float(debug.get("phase", 0.0)) % math.tau
    except (TypeError, ValueError, OverflowError):
        phase = 0.0
    if not math.isfinite(phase):
        phase = 0.0
    keyframe = int(debug.get("keyframe", 0)) % pose_count
    if playback == "continuous":
        try:
            cycle_seconds = max(
                0.1, min(10.0, float(debug.get("cycle_seconds", 1.0))),
            )
        except (TypeError, ValueError, OverflowError):
            cycle_seconds = 1.0
        debug["cycle_seconds"] = cycle_seconds
        phase = (
            phase + math.tau * max(0.0, float(dt)) / cycle_seconds
        ) % math.tau
        keyframe = int(math.floor(phase / math.tau * pose_count)) % pose_count
    else:
        phase = math.tau * keyframe / pose_count
    debug["phase"] = phase
    debug["keyframe"] = keyframe

    fields = {}
    if track.get("kind") == "procedural_gait":
        facing = debug.get("facing", "right")
        if facing not in {"left", "right"}:
            facing = "right"
            debug["facing"] = facing
        fields = {
            "animation_direction": facing,
            "animation_frame": f"{facing}_frame_start",
            "procedural_gait": {
                "phase": phase,
                "blend": 1.0,
                "run_blend": 1.0 if track_name == "run" else 0.0,
                "mode": track_name,
                "speed": 0.0,
            },
            "aim_requested": False,
            "aiming": False,
            "weapon_transition": {
                "progress": 0.0, "target": 0.0, "phase": "holstered",
            },
            "weapon_visual_recoil": {
                "amount": 0.0, "rotation_degrees": 0.0,
            },
        }
    elif track.get("kind") == "sprite_frames":
        frames = tuple(track.get("frames", ()))
        if frames:
            fields["animation_frame"] = frames[keyframe % len(frames)]

    return {
        "collection": collection_name,
        "id": entity_id,
        "track": track_name,
        "pose_count": pose_count,
        "pose_index": keyframe,
        "pose_name": pose_names[keyframe] if pose_names else "pose",
        "playback": playback,
        "phase": phase,
        "fields": fields,
    }

def select_gameplay_entity_at(entities, editor_state, world_point, tile_map):
    previous_collection = editor_state.get("selected_collection")
    previous_id = editor_state.get("selected_id")
    candidates = []
    for collection_name in GAMEPLAY_ENTITY_COLLECTIONS:
        for entity_id, entity in entities.get(collection_name, {}).items():
            if not isinstance(entity, dict):
                continue
            bounds = gameplay_entity_selection_bounds(entity, tile_map)
            if not gameplay_entity_bounds_contains(bounds, world_point):
                continue
            centre_x = bounds["x"] + bounds["width"] * 0.5
            centre_y = bounds["y"] + bounds["height"] * 0.5
            distance = (world_point["x"] - centre_x) ** 2 + (world_point["y"] - centre_y) ** 2
            already_selected = collection_name == previous_collection and entity_id == previous_id
            candidates.append({
                "sort_key": (
                    0 if already_selected else 1,
                    bounds["width"] * bounds["height"], distance,
                    collection_name, str(entity_id),
                ),
                "collection": collection_name,
                "id": entity_id,
            })
    if not candidates:
        editor_state.update({
            "selected_kind": None, "selected_collection": None,
            "selected_id": None, "drag_kind": None,
        })
        return None
    chosen = min(candidates, key=lambda candidate: candidate["sort_key"])
    editor_state.update({
        "selected_kind": "gameplay_entity",
        "selected_collection": chosen["collection"],
        "selected_id": chosen["id"],
    })
    return chosen["collection"], chosen["id"]

def delete_selected_gameplay_entity(entities, editor_state):
    collection_name = editor_state.get("selected_collection")
    entity_id = editor_state.get("selected_id")
    if (editor_state.get("selected_kind") != "gameplay_entity"
            or collection_name not in GAMEPLAY_ENTITY_COLLECTIONS
            or entity_id not in entities.get(collection_name, {})):
        return False
    del entities[collection_name][entity_id]
    editor_state.update({
        "selected_kind": None, "selected_collection": None,
        "selected_id": None, "drag_kind": None,
    })
    return True

def move_selected_gameplay_entity(entities, editor_state, world_point, tile_map):
    entity = get_selected_gameplay_entity(entities, editor_state)
    if entity is None:
        return False
    offset = editor_state.get("drag_offset", {})
    destination = {
        "x": float(world_point["x"]) + float(offset.get("x", 0.0)),
        "y": float(world_point["y"]) + float(offset.get("y", 0.0)),
    }
    destination = snap_world_position(destination, editor_state)
    entity["position"] = world_to_tile_position(destination, tile_map)
    return True

def allocate_gameplay_entity_id(collection):
    numeric_ids = []
    for entity_id in collection:
        try:
            numeric_ids.append(int(entity_id))
        except (TypeError, ValueError):
            continue
    return max(numeric_ids, default=-1) + 1

def draw_gameplay_entity_selection(editor_state, entities, game_camera, tile_map):
    entity = get_selected_gameplay_entity(entities, editor_state)
    if entity is None:
        return
    bounds = gameplay_entity_selection_bounds(entity, tile_map)
    screen = world_to_screen({"x": bounds["x"], "y": bounds["y"]}, game_camera)
    color = pr.Color(255, 225, 90, 235)
    pr.draw_rectangle_lines_ex(
        pr.Rectangle(screen["x"], screen["y"], bounds["width"], bounds["height"]),
        1.0, color,
    )
    pr.draw_text(
        f"{entity.get('type', 'entity')} [{editor_state.get('selected_id')}]",
        int(screen["x"]), int(screen["y"] - 9), 8, color,
    )


def draw_animation_entity_selection(editor_state, entities, player_entity,
                                    game_camera, tile_map):
    entity = get_selected_animation_entity(
        entities, player_entity, editor_state,
    )
    if entity is None:
        return
    bounds = gameplay_entity_selection_bounds(entity, tile_map)
    screen = world_to_screen(
        {"x": bounds["x"], "y": bounds["y"]}, game_camera,
    )
    color = pr.Color(100, 225, 255, 235)
    pr.draw_rectangle_lines_ex(
        pr.Rectangle(
            screen["x"], screen["y"], bounds["width"], bounds["height"],
        ),
        1.0, color,
    )
    label = "player" if entity.get("id") == "player" else entity.get(
        "type", "entity",
    )
    pr.draw_text(
        f"{label} [{editor_state.get('selected_id')}]",
        int(screen["x"]), int(screen["y"] - 9), 8, color,
    )

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

def hit_test_emitter(world_point, emitter, tile_map):
    centre = tile_position_to_world(emitter.get("position", {}), tile_map)
    area = emitter.get("area_size", {})
    return (
        abs(world_point["x"] - centre["x"]) <= max(7.0, float(area.get("x", 0.0)) * 0.5 + 3.0)
        and abs(world_point["y"] - centre["y"]) <= max(7.0, float(area.get("y", 0.0)) * 0.5 + 3.0)
    )

def hit_test_sound_emitter(world_point, emitter, tile_map):
    centre = tile_position_to_world(emitter.get("position", {}), tile_map)
    return distance_squared(world_point, centre) <= 9.0 ** 2

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
    editor_state["inspector_tab"] = "object"
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

    if selected_kind == "emitter":
        area = selected.get("area_size", {})
        x_handle = {"x": centre["x"] + float(area.get("x", 0.0)) * 0.5, "y": centre["y"]}
        y_handle = {"x": centre["x"], "y": centre["y"] + float(area.get("y", 0.0)) * 0.5}
        if distance_squared(world_point, x_handle) <= 7.0 ** 2:
            return "size_x"
        if distance_squared(world_point, y_handle) <= 7.0 ** 2:
            return "size_y"
        return None

    if selected_kind == "sound_emitter":
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
        size = selected["area_size"] if selected_kind == "emitter" else selected["size"]
        size["x"] = max(4.0, abs(world_point["x"] - centre["x"]) * 2.0)
    elif drag_kind == "size_y":
        size = selected["area_size"] if selected_kind == "emitter" else selected["size"]
        size["y"] = max(4.0, abs(world_point["y"] - centre["y"]) * 2.0)
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

def draw_emitter_handles(object_id, emitter, game_camera, tile_map, selected):
    centre_world = tile_position_to_world(emitter["position"], tile_map)
    centre = world_to_screen(centre_world, game_camera)
    area = emitter.get("area_size", {})
    width = float(area.get("x", 0.0))
    height = float(area.get("y", 0.0))
    colors = {
        "smoke": pr.Color(170, 175, 190, 255),
        "fire": pr.Color(255, 120, 45, 255),
        "ember": pr.Color(255, 190, 60, 255),
    }
    color = colors.get(emitter.get("type"), pr.MAGENTA) if emitter.get("enabled", True) else pr.GRAY
    outline = pr.Color(255, 230, 115, 255) if selected else color
    rect = pr.Rectangle(centre["x"] - width * 0.5, centre["y"] - height * 0.5, width, height)
    pr.draw_rectangle_lines_ex(rect, 2.0 if selected else 1.0, outline)
    draw_handle(centre, outline, 4 if selected else 3)
    if selected:
        draw_handle({"x": centre["x"] + width * 0.5, "y": centre["y"]}, outline)
        draw_handle({"x": centre["x"], "y": centre["y"] + height * 0.5}, outline)
        pr.draw_text(str(object_id), int(centre["x"] + 6), int(centre["y"] - 10), 8, outline)

def draw_sound_emitter_handles(object_id, emitter, game_camera, tile_map, selected):
    g_audio.normalize_sound_emitter(emitter)
    centre_world = tile_position_to_world(emitter["position"], tile_map)
    centre = world_to_screen(centre_world, game_camera)
    color = pr.Color(150, 220, 255, 255) if emitter.get("enabled", True) else pr.GRAY
    outline = pr.Color(255, 230, 115, 255) if selected else color
    if selected:
        pr.draw_circle_lines(
            int(centre["x"]), int(centre["y"]),
            float(emitter["maximum_distance"]), pr.Color(90, 180, 235, 150),
        )
        pr.draw_circle_lines(
            int(centre["x"]), int(centre["y"]),
            float(emitter["minimum_distance"]), pr.Color(150, 230, 255, 190),
        )
    draw_handle(centre, outline, 5 if selected else 4)
    pr.draw_text("S", int(centre["x"] - 2), int(centre["y"] - 3), 6, pr.BLACK)
    if selected:
        pr.draw_text(
            f"{object_id} {emitter['family']} ({emitter['playback_mode']})",
            int(centre["x"] + 7), int(centre["y"] - 10), 8, outline,
        )
        pr.draw_text(
            f"min {emitter['minimum_distance']:g}  max {emitter['maximum_distance']:g}",
            int(centre["x"] + 7), int(centre["y"]), 8,
            pr.Color(150, 230, 255, 220),
        )

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
    apply_placement_radius_override(editor_state, placement_type, preview)

    ENVIRONMENT_OBJECT_REGISTRY[placement_type]["handles"]("new", preview, game_camera, tile_map, True)

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

    control_down = (
        pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL)
        or pr.is_key_down(pr.KeyboardKey.KEY_RIGHT_CONTROL)
    )
    if control_down and ui_state.get("focused_id") is None:
        wheel_amount = pr.get_mouse_wheel_move()
        adjusted = (
            adjust_placement_preview_radius(editor_state, wheel_amount)
            if editor_state.get("tool") == "place"
            else adjust_selected_environment_radius(
                entities, editor_state, wheel_amount,
            )
        )
        if adjusted:
            ui_state["mouse_captured"] = True
            return

    if editor_state.get("tool") == "place":
        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
            placement_type = editor_state.get("placement_type", "point_light")
            snapped_world = snap_world_position(mouse_world, editor_state)
            kind, object_id = create_environment_object(entities, placement_type, world_to_tile_position(snapped_world, tile_map))
            registry_entry = ENVIRONMENT_OBJECT_REGISTRY[placement_type]
            apply_placement_radius_override(
                editor_state, placement_type,
                entities[registry_entry["target_collection"]][object_id],
            )
            editor_state["selected_kind"] = kind
            editor_state["selected_id"] = object_id
            editor_state["inspector_tab"] = "object"
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

def capture_editor_ui_regions(ui_state, editor_state, editor_mode,
                              show_editor=True):
    if not show_editor:
        # Hidden editor controls must not retain focus/capture or an in-progress
        # world drag. Gameplay uses captured relative mouse input in this state.
        g_ui.ui_release_mouse(ui_state)
        editor_state["drag_kind"] = None
        return False

    mouse = g_ui.get_mouse_position()
    toolbar_rect = pr.Rectangle(0, 0, 480, 38)
    inspector_rect = pr.Rectangle(306, 38, 174, 232)

    inspector_visible = editor_mode in {
        "environment", "entity", "animation",
    } and not editor_state.get("inspector_collapsed", False)

    if g_ui.ui_point_in_rect(mouse, toolbar_rect) or (inspector_visible and g_ui.ui_point_in_rect(mouse, inspector_rect)):
        g_ui.ui_capture_mouse(ui_state)
    return ui_state.get("mouse_captured", False)


def draw_rain_exposure_overlay(editor_state, editor_mode, game_camera, tile_map,
                               viewport_width=480, viewport_height=270):
    """Draw the authoring-only tile overlay after scene composites and before UI."""
    if editor_mode not in {"tile", "audio_debug"}:
        return
    if (editor_state.get("tile_edit_mode", "appearance") != "rain_exposure"
            and not editor_state.get("show_rain_exposure_overlay", True)):
        return
    width = int(tile_map.get("map_width", 0))
    height = int(tile_map.get("map_height", 0))
    tile_width = max(1, int(tile_map.get("tile_width", 16)))
    tile_height = max(1, int(tile_map.get("tile_height", 16)))
    tiles = tile_map.get("tiles", ())
    start_x = max(0, int(math.floor(game_camera.x / tile_width)))
    start_y = max(0, int(math.floor(game_camera.y / tile_height)))
    end_x = min(width, start_x + int(viewport_width / tile_width) + 2)
    end_y = min(height, start_y + int(viewport_height / tile_height) + 2)
    for tile_y in range(start_y, end_y):
        for tile_x in range(start_x, end_x):
            flat_index = tile_y * width + tile_x
            if flat_index >= len(tiles):
                continue
            exposure = g_effects.get_tile_rain_exposure(tiles[flat_index])
            if exposure <= 0.0:
                continue
            alpha = max(1, min(150, int(round(28.0 + exposure * 92.0))))
            screen_position = g_render_order.world_to_screen_pixel(
                tile_x * tile_width, tile_y * tile_height, game_camera,
            )
            pr.draw_rectangle(
                screen_position["x"], screen_position["y"],
                tile_width, tile_height, pr.Color(35, 190, 235, alpha),
            )


def draw_audio_tile_overlays(editor_state, editor_mode, game_camera, tile_map,
                             viewport_width=480, viewport_height=270):
    if editor_mode not in {"tile", "audio_debug"}:
        return
    mode = editor_state.get("tile_edit_mode", "appearance")
    show_zones = mode == "acoustic_zone" or editor_state.get("show_acoustic_zone_overlay", False)
    show_contacts = mode == "footstep_overlay" or editor_state.get("show_footstep_overlay", False)
    if not show_zones and not show_contacts:
        return
    width = int(tile_map.get("map_width", 0))
    height = int(tile_map.get("map_height", 0))
    tile_width = max(1, int(tile_map.get("tile_width", 16)))
    tile_height = max(1, int(tile_map.get("tile_height", 16)))
    tiles = tile_map.get("tiles", ())
    start_x = max(0, int(math.floor(game_camera.x / tile_width)))
    start_y = max(0, int(math.floor(game_camera.y / tile_height)))
    end_x = min(width, start_x + int(viewport_width / tile_width) + 2)
    end_y = min(height, start_y + int(viewport_height / tile_height) + 2)
    for tile_y in range(start_y, end_y):
        for tile_x in range(start_x, end_x):
            index = tile_y * width + tile_x
            if index >= len(tiles) or not isinstance(tiles[index], dict):
                continue
            tile = tiles[index]
            screen = g_render_order.world_to_screen_pixel(
                tile_x * tile_width, tile_y * tile_height, game_camera,
            )
            if show_zones:
                zone_id = g_audio.get_tile_acoustic_zone(tile)
                if zone_id > 0:
                    color = pr.Color(
                        80 + (zone_id * 53) % 130,
                        65 + (zone_id * 89) % 140,
                        95 + (zone_id * 37) % 120,
                        76,
                    )
                    pr.draw_rectangle(screen["x"], screen["y"], tile_width, tile_height, color)
            if show_contacts and tile.get("footstep_overlay") == "puddle":
                pr.draw_rectangle(
                    screen["x"], screen["y"], tile_width, tile_height,
                    pr.Color(40, 125, 215, 105),
                )
                pr.draw_rectangle_lines(
                    screen["x"], screen["y"], tile_width, tile_height,
                    pr.Color(85, 215, 245, 180),
                )


def draw_tile_edit_controls(ui_state, editor_state, tile_map):
    modes = ("appearance", "rain_exposure", "acoustic_zone", "footstep_overlay")
    mode = editor_state.get("tile_edit_mode", "appearance")
    mode = mode if mode in modes else "appearance"
    pr.draw_text("Tile edit", 332, 32, 8, pr.WHITE)
    mode, _ = g_ui.ui_dropdown(
        ui_state, "tile:edit_mode", "", mode, modes,
        pr.Rectangle(332, 42, 138, 15), 4,
    )
    editor_state["tile_edit_mode"] = mode

    if mode == "appearance":
        return
    if mode == "rain_exposure":
        pr.draw_text("Rain exposure", 332, 61, 8, pr.WHITE)
        covered_rect = pr.Rectangle(332, 71, 67, 15)
        exposed_rect = pr.Rectangle(401, 71, 69, 15)
        exposure = 1.0 if float(editor_state.get("rain_exposure_value", 1.0)) > 0.0 else 0.0
        if g_ui.ui_button(
                ui_state, "tile:rain:covered", "Covered", covered_rect,
                selected=exposure <= 0.0):
            exposure = 0.0
        if g_ui.ui_button(
                ui_state, "tile:rain:exposed", "Exposed", exposed_rect,
                selected=exposure > 0.0):
            exposure = 1.0
        editor_state["rain_exposure_value"] = exposure
        editor_state["show_rain_exposure_overlay"], _ = g_ui.ui_checkbox(
            ui_state, "tile:rain:overlay", "show overlay",
            editor_state.get("show_rain_exposure_overlay", True),
            pr.Rectangle(332, 89, 138, 14),
        )
        if g_ui.ui_button(ui_state, "tile:rain:fill_covered", "Fill map covered", pr.Rectangle(332, 105, 138, 15)):
            g_effects.fill_map_rain_exposure(tile_map, 0.0)
        if g_ui.ui_button(ui_state, "tile:rain:fill_exposed", "Fill map exposed", pr.Rectangle(332, 122, 138, 15)):
            g_effects.fill_map_rain_exposure(tile_map, 1.0)
        return
    if mode == "acoustic_zone":
        pr.draw_text("Acoustic zone", 332, 61, 8, pr.WHITE)
        zones = tile_map.get("acoustic_zones", {})
        zone_ids = sorted({0} | {
            int(key) for key in zones.keys()
            if str(key).lstrip("-").isdigit() and int(key) >= 0
        })
        zone_value = int(editor_state.get("acoustic_zone_value", 0))
        if zone_value not in zone_ids:
            zone_value = 0
        zone_value, _ = g_ui.ui_dropdown(
            ui_state, "tile:acoustic:zone", "zone", zone_value, zone_ids,
            pr.Rectangle(332, 71, 138, 15), 6,
        )
        editor_state["acoustic_zone_value"] = int(zone_value)
        definition = g_audio.get_acoustic_zone_definition(tile_map, zone_value)
        pr.draw_text(str(definition.get("name", "zone")), 332, 89, 8, g_ui.UI_MUTED)
        editor_state["show_acoustic_zone_overlay"], _ = g_ui.ui_checkbox(
            ui_state, "tile:acoustic:overlay", "show zones",
            editor_state.get("show_acoustic_zone_overlay", True),
            pr.Rectangle(332, 102, 138, 14),
        )
        return
    pr.draw_text("Foot contact", 332, 61, 8, pr.WHITE)
    overlay = editor_state.get("footstep_overlay_value", "none")
    overlay, _ = g_ui.ui_dropdown(
        ui_state, "tile:footstep:overlay_value", "", overlay,
        g_audio.FOOTSTEP_OVERLAYS, pr.Rectangle(332, 71, 138, 15), 2,
    )
    editor_state["footstep_overlay_value"] = overlay
    editor_state["show_footstep_overlay"], _ = g_ui.ui_checkbox(
        ui_state, "tile:footstep:overlay", "show contacts",
        editor_state.get("show_footstep_overlay", True),
        pr.Rectangle(332, 89, 138, 14),
    )

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
    editor_mode, _ = g_ui.ui_dropdown(ui_state, "toolbar:mode", "", editor_mode, EDITOR_MODES, pr.Rectangle(2, 2, 78, 16), 5)
    if editor_mode == "animation":
        g_ui.ui_label(
            ui_state, "toolbar:animation_hint",
            "click select  arrows step  space play/freeze",
            pr.Rectangle(84, 3, 250, 14), g_ui.UI_MUTED, 8,
        )
        return editor_mode
    editor_state["tool"], _ = g_ui.ui_dropdown(ui_state, "toolbar:tool", "", editor_state.get("tool", "place"), EDITOR_TOOLS, pr.Rectangle(82, 2, 66, 16), 2)

    if editor_mode == "environment":
        editor_state["placement_type"], _ = g_ui.ui_dropdown(ui_state, "toolbar:placement", "", editor_state.get("placement_type", "point_light"), get_environment_placement_types(), pr.Rectangle(150, 2, 98, 16), 8)

    editor_state["preview_effects"], _ = g_ui.ui_checkbox(ui_state, "toolbar:preview", "fx", editor_state.get("preview_effects", True), pr.Rectangle(252, 3, 38, 14))
    editor_state["snap_enabled"], _ = g_ui.ui_checkbox(ui_state, "toolbar:snap", "snap", editor_state.get("snap_enabled", False), pr.Rectangle(292, 3, 48, 14))
    editor_state["snap_size"], _ = g_ui.ui_number_input_float(ui_state, "toolbar:snap_size", "", editor_state.get("snap_size", 4.0), 0.25, 64.0, pr.Rectangle(342, 2, 52, 16))

    if get_selected_object(entities, editor_state) is not None:
        if g_ui.ui_button(ui_state, "toolbar:duplicate", "dup", pr.Rectangle(396, 2, 38, 16)):
            duplicate_selected_environment_object(entities, editor_state, tile_map)
        if g_ui.ui_button(ui_state, "toolbar:delete", "del", pr.Rectangle(436, 2, 40, 16)):
            delete_selected_environment_object(entities, editor_state)

    if pr.is_key_down(pr.KeyboardKey.KEY_H):
        g_ui.ui_label(ui_state, "toolbar:hint", "Q select  P place  Ctrl+wheel radius  Ctrl+D duplicate  Del delete", pr.Rectangle(4, 22, 390, 12), g_ui.UI_MUTED, 8)
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

def inspect_emitter(ui_state, editor_state, object_id, emitter, tile_map):
    widget_id = f"object:{object_id}"
    g_effects.migrate_emitter(emitter)
    effect_type = emitter.get("type", "smoke")
    emitter["enabled"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:enabled", "enabled", emitter.get("enabled", True))
    emitter["preview_enabled"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:preview", "preview", emitter.get("preview_enabled", True))
    g_ui.ui_label(ui_state, f"{widget_id}:type", f"type: {effect_type}", font_size=8)
    emitter["position"] = edit_world_position(ui_state, f"{widget_id}:position", emitter["position"], tile_map)
    emitter["area_size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:area", "area", emitter.get("area_size", {"x": 8.0, "y": 8.0}), 0.0, 4000.0)
    emitter["seed"], _ = g_ui.ui_number_input_int(ui_state, f"{widget_id}:seed", "seed", int(emitter.get("seed", 1)), 1, 2147483647)
    emitter["render_group"], _ = g_ui.ui_dropdown(ui_state, f"{widget_id}:group", "group", emitter.get("render_group", "world_front"), g_effects.RENDER_GROUPS)
    for name, minimum, maximum in (("density", 0.0, 1.0), ("speed", 0.0, 8.0), ("opacity", 0.0, 1.0), ("posterize_levels", 2.0, 16.0)):
        emitter[name], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:{name}", name.replace("_", " "), emitter.get(name, minimum), minimum, maximum)

    if effect_type == "smoke":
        emitter["size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:size", "effect size", emitter.get("size", {"x": 34.0, "y": 52.0}), 1.0, 1000.0)
        for name, minimum, maximum in (("turbulence", 0.0, 2.0), ("detail_scale", 0.01, 2.0), ("warp_strength", 0.0, 3.0), ("evolution_speed", 0.0, 4.0), ("wind_response", 0.0, 4.0)):
            emitter[name], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:{name}", name.replace("_", " "), emitter.get(name, minimum), minimum, maximum)
        color = emitter.get("color", [0.42, 0.43, 0.48, 1.0])
        edited, _ = g_ui.ui_color3_editor(ui_state, f"{widget_id}:color", "smoke colour", color[:3])
        emitter["color"] = list(edited) + [color[3] if len(color) > 3 else 1.0]

    elif effect_type == "fire":
        emitter["size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:size", "flame size", emitter.get("size", {"x": 18.0, "y": 26.0}), 1.0, 1000.0)
        for name, minimum, maximum in (("turbulence", 0.0, 2.0), ("wind_response", 0.0, 4.0), ("ember_density", 0.0, 1.0), ("ember_height", 0.0, 300.0)):
            emitter[name], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:{name}", name.replace("_", " "), emitter.get(name, minimum), minimum, maximum)
        palette = emitter.setdefault("palette", {})
        for name, fallback in (("core", [1.0, 0.94, 0.55, 1.0]), ("hot", [1.0, 0.67, 0.18, 1.0]), ("mid", [0.92, 0.25, 0.045, 1.0]), ("outer", [0.30, 0.025, 0.012, 1.0])):
            color = list(palette.get(name, fallback))
            edited, _ = g_ui.ui_color3_editor(ui_state, f"{widget_id}:{name}", name, color[:3])
            palette[name] = list(edited) + [color[3] if len(color) > 3 else 1.0]
        light = emitter.setdefault("light", {})
        light["enabled"], _ = g_ui.ui_checkbox(ui_state, f"{widget_id}:light", "linked light", light.get("enabled", True))
        light["radius"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:light_radius", "light radius", light.get("radius", 70.0), 0.0, 2000.0)
        light["intensity"], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:light_intensity", "light intensity", light.get("intensity", 0.8), 0.0, 10.0)
    elif effect_type == "ember":
        emitter["size"], _ = g_ui.ui_vec2_input(ui_state, f"{widget_id}:size", "field size", emitter.get("size", {"x": 24.0, "y": 42.0}), 1.0, 1000.0)
        for name, minimum, maximum in (("turbulence", 0.0, 2.0), ("wind_response", 0.0, 4.0)):
            emitter[name], _ = g_ui.ui_number_input_float(ui_state, f"{widget_id}:{name}", name.replace("_", " "), emitter.get(name, minimum), minimum, maximum)
        color = emitter.get("color", [1.0, 0.52, 0.12, 1.0])
        edited, _ = g_ui.ui_color3_editor(ui_state, f"{widget_id}:color", "ember colour", color[:3])
        emitter["color"] = list(edited) + [color[3] if len(color) > 3 else 1.0]

def inspect_smoke_emitter(ui_state, editor_state, object_id, emitter, tile_map):
    inspect_emitter(ui_state, editor_state, object_id, emitter, tile_map)

def inspect_fire_emitter(ui_state, editor_state, object_id, emitter, tile_map):
    inspect_emitter(ui_state, editor_state, object_id, emitter, tile_map)

def inspect_ember_emitter(ui_state, editor_state, object_id, emitter, tile_map):
    inspect_emitter(ui_state, editor_state, object_id, emitter, tile_map)

def inspect_sound_emitter(ui_state, editor_state, object_id, emitter, tile_map):
    widget_id = f"object:{object_id}"
    g_audio.normalize_sound_emitter(emitter)
    emitter["enabled"], _ = g_ui.ui_checkbox(
        ui_state, f"{widget_id}:enabled", "enabled", emitter["enabled"],
    )
    emitter["family"], _ = g_ui.ui_dropdown(
        ui_state, f"{widget_id}:family", "sound", emitter["family"],
        g_audio.SOUND_EMITTER_FAMILIES,
    )
    emitter["playback_mode"], _ = g_ui.ui_dropdown(
        ui_state, f"{widget_id}:mode", "mode", emitter["playback_mode"],
        ("loop", "cadence"),
    )
    emitter["position"] = edit_world_position(
        ui_state, f"{widget_id}:position", emitter["position"], tile_map,
    )
    emitter["gain"], _ = g_ui.ui_slider_float(
        ui_state, f"{widget_id}:gain", "gain", emitter["gain"], 0.0, 2.0, 0.01,
    )
    for name, minimum, maximum in (
        ("minimum_distance", 0.0, 2000.0),
        ("maximum_distance", 1.0, 4000.0),
        ("pan_distance", 1.0, 4000.0),
        ("maximum_pan", 0.0, 1.0),
    ):
        emitter[name], _ = g_ui.ui_number_input_float(
            ui_state, f"{widget_id}:{name}", {
                "minimum_distance": "emitter min radius",
                "maximum_distance": "emitter max radius",
            }.get(name, name.replace("_", " ")),
            emitter[name], minimum, maximum,
        )
    if emitter["playback_mode"] == "cadence":
        emitter["cadence_seconds"], _ = g_ui.ui_number_input_float(
            ui_state, f"{widget_id}:cadence", "cadence seconds",
            emitter["cadence_seconds"], 0.25, 3600.0,
        )
        emitter["cadence_variation"], _ = g_ui.ui_number_input_float(
            ui_state, f"{widget_id}:variation", "cadence variation",
            emitter["cadence_variation"], 0.0, 3600.0,
        )
        emitter["seed"], _ = g_ui.ui_number_input_int(
            ui_state, f"{widget_id}:seed", "seed", emitter["seed"],
            0, 2147483647,
        )
    g_ui.ui_label(
        ui_state, f"{widget_id}:spatial_note",
        "2D positional (mono source recommended)",
        color=g_ui.UI_MUTED, font_size=8,
    )
    g_audio.normalize_sound_emitter(emitter)

def get_environment_placement_types():
    return tuple(ENVIRONMENT_OBJECT_REGISTRY.keys())

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

def inspect_wind_profile(ui_state, editor_state, profile):
    if not section_button(ui_state, editor_state, "wind", "Wind"):
        return
    direction, changed = g_ui.ui_vec2_input(ui_state, "world:wind:direction", "direction", profile.get("direction", {"x": 1.0, "y": 0.0}), -1.0, 1.0)
    if changed:
        profile["direction"] = normalize_spot_direction(direction)
    for name, minimum, maximum in (
        ("strength", 0.0, 100.0),
        ("gust_strength", 0.0, 100.0),
        ("gust_speed", 0.0, 10.0),
        ("spatial_scale", 0.0001, 1.0),
        ("vertical_flutter", 0.0, 100.0),
    ):
        profile[name], _ = g_ui.ui_number_input_float(ui_state, f"world:wind:{name}", name.replace("_", " "), profile.get(name, minimum), minimum, maximum)


def inspect_rain_profile(ui_state, editor_state, profile):
    if not section_button(ui_state, editor_state, "rain", "Rain"):
        return
    profile = g_effects.normalize_rain_profile(profile)
    profile["enabled"], _ = g_ui.ui_checkbox(ui_state, "world:rain:enabled", "enabled", profile["enabled"])
    for name, minimum, maximum in (
        ("density", 0.0, 1.0), ("speed", 0.0, 20.0),
    ):
        profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:rain:{name}", name, profile[name], minimum, maximum, 0.01)
    direction, changed = g_ui.ui_vec2_input(ui_state, "world:rain:direction", "direction", profile["direction"], -1.0, 1.0)
    if changed:
        profile["direction"] = direction
    profile["seed"], _ = g_ui.ui_number_input_int(ui_state, "world:rain:seed", "seed", profile["seed"], -2147483648, 2147483647)
    profile["cell_size"], _ = g_ui.ui_vec2_input(ui_state, "world:rain:cell", "cell size", profile["cell_size"], 2.0, 128.0)
    for name, minimum, maximum, step in (
        ("streak_length", 1.0, 8.0, 0.25),
        ("unlit_opacity", 0.0, 1.0, 0.001),
        ("lit_opacity", 0.0, 1.0, 0.005),
        ("light_threshold", 0.0, 1.0, 0.005),
        ("light_response", 0.0, 20.0, 0.05),
        ("light_color_influence", 0.0, 1.0, 0.01),
    ):
        profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:rain:{name}", name.replace("_", " "), profile[name], minimum, maximum, step)
    profile["ambient_color"], _ = g_ui.ui_color3_editor(ui_state, "world:rain:ambient", "ambient rain", profile["ambient_color"])
    profile["opacity_levels"], _ = g_ui.ui_number_input_int(ui_state, "world:rain:levels", "opacity levels", profile["opacity_levels"], 2, 64)
    profile["distortion_enabled"], _ = g_ui.ui_checkbox(ui_state, "world:rain:distortion", "distortion", profile["distortion_enabled"])
    for name, minimum, maximum, step in (
        ("distortion_strength", 0.0, 1.0, 0.05),
        ("distortion_density", 0.0, 1.0, 0.01),
    ):
        profile[name], _ = g_ui.ui_slider_float(ui_state, f"world:rain:{name}", name.replace("_", " "), profile[name], minimum, maximum, step)
    g_effects.normalize_rain_profile(profile)

    if section_button(ui_state, editor_state, "rain_debug", "Rain debug"):
        debug = editor_state.setdefault("rain_debug", make_editor_state()["rain_debug"])
        for name, label in (
            ("show_exposure_overlay", "exposure in play"),
            ("show_raw_exposure_texture", "raw exposure texture"),
            ("show_raw_streak_mask", "raw streak mask"),
            ("show_distortion_mask", "distortion mask"),
            ("show_sampled_light_amount", "sampled light"),
            ("disable_streak_color", "disable streak colour"),
            ("disable_distortion", "disable distortion"),
            ("show_stats", "show statistics"),
        ):
            debug[name], _ = g_ui.ui_checkbox(ui_state, f"world:rain:debug:{name}", label, debug.get(name, False))


def inspect_audio_profile(ui_state, editor_state, profile, audio_runtime=None):
    if not section_button(ui_state, editor_state, "audio", "Audio"):
        return
    profile = g_audio.normalize_audio_profile(profile)
    for name in (
        "master_gain", "sfx_gain", "footstep_gain", "weapon_gain",
        "ambience_gain", "weather_gain", "ui_gain",
    ):
        profile[name], _ = g_ui.ui_slider_float(
            ui_state, f"world:audio:{name}", name.replace("_", " "),
            profile[name], 0.0, 2.0, 0.01,
        )
    for name, minimum, maximum in (
        ("minimum_distance", 0.0, 500.0),
        ("maximum_distance", 1.0, 2000.0),
        ("pan_distance", 1.0, 1000.0),
        ("maximum_pan", 0.0, 1.0),
        ("loop_attack_seconds", 0.01, 5.0),
        ("loop_release_seconds", 0.01, 5.0),
    ):
        profile[name], _ = g_ui.ui_number_input_float(
            ui_state, f"world:audio:{name}", {
                "minimum_distance": "global min distance",
                "maximum_distance": "global max distance",
            }.get(name, name.replace("_", " ")),
            profile[name], minimum, maximum,
        )
    debug = editor_state.setdefault("audio_debug", make_editor_state()["audio_debug"])
    for name, label in (
        ("show_stats", "audio statistics"),
        ("show_world", "world sources"),
        ("show_acoustic_zones", "zone overlay"),
        ("show_contact_overlays", "contact overlay"),
    ):
        debug[name], _ = g_ui.ui_checkbox(
            ui_state, f"world:audio:debug:{name}", label, debug.get(name, False)
        )
    if audio_runtime is not None:
        capabilities = audio_runtime.get("capabilities", {})
        g_ui.ui_label(
            ui_state, "world:audio:capabilities",
            f"DSP: {capabilities.get('treatment_mode', 'gain_fallback')}",
            color=g_ui.UI_MUTED, font_size=8,
        )


def draw_inspector(ui_state, editor_state, entities, lighting_profile, fog_profile, wind_profile, tile_map, rain_profile=None, audio_profile=None, audio_runtime=None):
    collapse_rect = pr.Rectangle(308, 40, 14, 14)

    if g_ui.ui_button(ui_state, "inspector:collapse", "<" if editor_state.get("inspector_collapsed", False) else ">", collapse_rect):
        editor_state["inspector_collapsed"] = not editor_state.get("inspector_collapsed", False)

    if editor_state.get("inspector_collapsed", False):
        return

    panel_rect = pr.Rectangle(324, 38, 156, 232)

    if g_ui.ui_point_in_rect(g_ui.get_mouse_position(), panel_rect) and ui_state.get("open_dropdown_id") is None:
        editor_state["inspector_scroll"] = max(0.0, editor_state.get("inspector_scroll", 0.0) - pr.get_mouse_wheel_move() * 18.0)

    g_ui.ui_begin_panel(ui_state, "inspector:panel", panel_rect, "Environment", editor_state.get("inspector_scroll", 0.0))
    active_tab = editor_state.get("inspector_tab", "object")
    object_tab = g_ui.ui_button(
        ui_state, "inspector:object_tab", "Object",
        g_ui.ui_next_rect(ui_state, 14, 70), selected=active_tab == "object",
    )
    world_tab = g_ui.ui_button(
        ui_state, "inspector:world_tab", "World",
        g_ui.ui_next_rect(ui_state, 14, 70), selected=active_tab == "world",
    )

    if object_tab:
        editor_state["inspector_tab"] = "object"
    if world_tab:
        editor_state["inspector_tab"] = "world"

    if editor_state.get("inspector_tab", "object") == "world":
        inspect_lighting_profile(ui_state, editor_state, lighting_profile)
        g_ui.ui_separator(ui_state, "inspector:world_separator")
        inspect_fog_profile(ui_state, editor_state, fog_profile)
        g_ui.ui_separator(ui_state, "inspector:wind_separator")
        inspect_wind_profile(ui_state, editor_state, wind_profile)
        g_ui.ui_separator(ui_state, "inspector:rain_separator")
        inspect_rain_profile(ui_state, editor_state, rain_profile or g_effects.make_rain_profile())
        g_ui.ui_separator(ui_state, "inspector:audio_separator")
        inspect_audio_profile(
            ui_state, editor_state,
            audio_profile or g_audio.make_audio_profile(), audio_runtime,
        )
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

def draw_gameplay_entity_inspector(ui_state, editor_state, entities,
                                   movement_defaults=None,
                                   evade_defaults=None,
                                   perception_defaults=None,
                                   flee_defaults=None):
    collapse_rect = pr.Rectangle(308, 40, 14, 14)
    if g_ui.ui_button(
            ui_state, "entity_inspector:collapse",
            "<" if editor_state.get("inspector_collapsed", False) else ">",
            collapse_rect):
        editor_state["inspector_collapsed"] = not editor_state.get(
            "inspector_collapsed", False,
        )
    if editor_state.get("inspector_collapsed", False):
        return

    panel_rect = pr.Rectangle(324, 38, 156, 232)
    if (g_ui.ui_point_in_rect(g_ui.get_mouse_position(), panel_rect)
            and ui_state.get("open_dropdown_id") is None):
        editor_state["entity_inspector_scroll"] = max(
            0.0,
            editor_state.get("entity_inspector_scroll", 0.0)
            - pr.get_mouse_wheel_move() * 18.0,
        )
    g_ui.ui_begin_panel(
        ui_state, "entity_inspector:panel", panel_rect, "Entity",
        editor_state.get("entity_inspector_scroll", 0.0),
    )
    entity = get_selected_gameplay_entity(entities, editor_state)
    if entity is None:
        g_ui.ui_label(
            ui_state, "entity_inspector:none", "No entity selected",
            color=g_ui.UI_MUTED, font_size=8,
        )
        g_ui.ui_end_panel(ui_state)
        return

    entity_id = editor_state.get("selected_id")
    entity_type = str(entity.get("type", "entity"))
    g_ui.ui_label(
        ui_state, "entity_inspector:selected",
        f"{entity_type} [{entity_id}]", color=g_ui.UI_ACCENT, font_size=8,
    )
    g_ui.ui_label(
        ui_state, "entity_inspector:state",
        f"state: {entity.get('current_state', 'n/a')}",
        color=g_ui.UI_MUTED, font_size=8,
    )

    if entity_type == "red head" and isinstance(movement_defaults, dict):
        movement = entity.setdefault("movement_settings", {})
        if not isinstance(movement, dict):
            movement = {}
            entity["movement_settings"] = movement
        legacy_fields = {
            "max_speed": "speed",
            "acceleration": "acceleration",
            "reverse_acceleration": "reverse_acceleration",
            "arrival_radius": "arrival_radius",
        }
        ranges = (
            ("max_speed", "max speed", 0.0, 300.0),
            ("acceleration", "acceleration", 0.0, 1000.0),
            ("deceleration", "deceleration", 0.0, 1500.0),
            ("reverse_acceleration", "reverse accel", 0.0, 2000.0),
            ("arrival_radius", "arrival radius", 0.0, 64.0),
            ("evade_speed_multiplier", "evade speed", 0.0, 3.0),
        )
        for name, label, minimum, maximum in ranges:
            fallback = movement_defaults.get(name, minimum)
            legacy_name = legacy_fields.get(name)
            if name == "evade_speed_multiplier":
                evade = entity.get("evade_settings", {})
                if isinstance(evade, dict):
                    fallback = evade.get("speed_multiplier", fallback)
            elif legacy_name is not None:
                fallback = entity.get(legacy_name, fallback)
            movement[name], _ = g_ui.ui_number_input_float(
                ui_state, f"entity_inspector:movement:{name}", label,
                movement.get(name, fallback), minimum, maximum,
            )

        if isinstance(perception_defaults, dict):
            g_ui.ui_separator(
                ui_state, "entity_inspector:perception_separator",
            )
            g_ui.ui_label(
                ui_state, "entity_inspector:perception_label", "Perception",
                color=g_ui.UI_ACCENT, font_size=8,
            )
            perception = entity.setdefault("perception_settings", {})
            if not isinstance(perception, dict):
                perception = {}
                entity["perception_settings"] = perception
            for setting_name, label, minimum, maximum in (
                    ("line_of_sight_checks_per_second", "LOS checks / sec", 0.25, 60.0),
                    ("flashlight_checks_per_second", "light checks / sec", 1.0, 60.0),
                    ("flashlight_notice_duration", "light notice time", 0.0, 5.0),
                    ("flashlight_intensity_threshold", "light threshold", 0.0, 10.0),
                    ("light_startle_duration", "light startle", 0.0, 2.0)):
                perception[setting_name], _ = g_ui.ui_number_input_float(
                    ui_state, f"entity_inspector:perception:{setting_name}",
                    label,
                    perception.get(
                        setting_name,
                        perception_defaults.get(setting_name, minimum),
                    ),
                    minimum, maximum,
                )

        if isinstance(evade_defaults, dict):
            g_ui.ui_separator(ui_state, "entity_inspector:evade_separator")
            g_ui.ui_label(
                ui_state, "entity_inspector:evade_label", "Evade planning",
                color=g_ui.UI_ACCENT, font_size=8,
            )
            evade = entity.setdefault("evade_settings", {})
            if not isinstance(evade, dict):
                evade = {}
                entity["evade_settings"] = evade
            for name, label, minimum, maximum in (
                    ("chance", "chance", 0.0, 1.0),
                    ("duration_min", "duration min", 0.05, 5.0),
                    ("duration_max", "duration max", 0.05, 5.0),
                    ("minimum_lateral_tiles", "minimum lateral", 0.0, 8.0),
                    ("maximum_retreat_tiles", "maximum retreat", 0.0, 4.0),
                    ("heading_reversal_limit", "heading limit", -1.0, 1.0),
                    ("lateral_score_weight", "lateral weight", 0.0, 10.0),
                    ("aim_clearance_score_weight", "aim clearance", 0.0, 10.0),
                    ("progress_score_weight", "progress weight", 0.0, 10.0),
                    ("path_cost_score_weight", "path cost", 0.0, 10.0),
                    ("preferred_side_score", "side preference", 0.0, 10.0),
                    ("waypoint_arrival_radius", "waypoint radius", 0.0, 16.0),
                    ("stuck_replan_delay", "stuck replan", 0.05, 2.0)):
                evade[name], _ = g_ui.ui_number_input_float(
                    ui_state, f"entity_inspector:evade:{name}", label,
                    evade.get(name, evade_defaults.get(name, minimum)),
                    minimum, maximum,
                )
            for name, label, minimum, maximum in (
                    ("search_radius_tiles", "search radius", 1, 10),
                    ("top_candidate_count", "top candidates", 1, 12)):
                evade[name], _ = g_ui.ui_number_input_int(
                    ui_state, f"entity_inspector:evade:{name}", label,
                    int(evade.get(name, evade_defaults.get(name, minimum))),
                    minimum, maximum,
                )

        if isinstance(flee_defaults, dict):
            g_ui.ui_separator(ui_state, "entity_inspector:flee_separator")
            g_ui.ui_label(
                ui_state, "entity_inspector:flee_label", "Flee planning",
                color=g_ui.UI_ACCENT, font_size=8,
            )
            flee = entity.setdefault("flee_settings", {})
            if not isinstance(flee, dict):
                flee = {}
                entity["flee_settings"] = flee
            for name, label, minimum, maximum in (
                    ("health_fraction", "health fraction", 0.0, 1.0),
                    ("ally_arrival_distance", "ally arrival", 0.0, 96.0),
                    ("speed_multiplier", "speed multiplier", 0.0, 4.0),
                    ("replan_interval", "replan interval", 0.1, 3.0),
                    ("waypoint_arrival_radius", "waypoint radius", 0.0, 16.0)):
                flee[name], _ = g_ui.ui_number_input_float(
                    ui_state, f"entity_inspector:flee:{name}", label,
                    flee.get(name, flee_defaults.get(name, minimum)),
                    minimum, maximum,
                )
            flee["ally_search_radius_tiles"], _ = g_ui.ui_number_input_int(
                ui_state, "entity_inspector:flee:ally_search_radius_tiles",
                "ally search radius",
                int(flee.get(
                    "ally_search_radius_tiles",
                    flee_defaults.get("ally_search_radius_tiles", 1),
                )), 1, 32,
            )
            flee["local_plan_radius_tiles"], _ = g_ui.ui_number_input_int(
                ui_state, "entity_inspector:flee:local_plan_radius_tiles",
                "local plan radius",
                int(flee.get(
                    "local_plan_radius_tiles",
                    flee_defaults.get("local_plan_radius_tiles", 1),
                )), 1, 16,
            )

    g_ui.ui_end_panel(ui_state)


def step_animation_debug_keyframe(editor_state, pose_count, amount):
    debug = editor_state.setdefault(
        "animation_debug", make_editor_state()["animation_debug"],
    )
    count = max(1, int(pose_count))
    debug["playback"] = "keyframe"
    debug["keyframe"] = (
        int(debug.get("keyframe", 0)) + int(amount)
    ) % count
    debug["phase"] = math.tau * debug["keyframe"] / count
    return debug["keyframe"]


def update_animation_debug_shortcuts(editor_state, pose_count, ui_state):
    if (ui_state.get("focused_id") is not None
            or ui_state.get("open_dropdown_id") is not None):
        return
    debug = editor_state.setdefault(
        "animation_debug", make_editor_state()["animation_debug"],
    )
    if pr.is_key_pressed(pr.KeyboardKey.KEY_SPACE):
        debug["playback"] = (
            "keyframe" if debug.get("playback") == "continuous"
            else "continuous"
        )
    if pr.is_key_pressed(pr.KeyboardKey.KEY_LEFT):
        step_animation_debug_keyframe(editor_state, pose_count, -1)
    if pr.is_key_pressed(pr.KeyboardKey.KEY_RIGHT):
        step_animation_debug_keyframe(editor_state, pose_count, 1)


def draw_animation_debug_inspector(ui_state, editor_state, entities,
                                   player_entity):
    collapse_rect = pr.Rectangle(308, 40, 14, 14)
    if g_ui.ui_button(
            ui_state, "animation_inspector:collapse",
            "<" if editor_state.get("inspector_collapsed", False) else ">",
            collapse_rect):
        editor_state["inspector_collapsed"] = not editor_state.get(
            "inspector_collapsed", False,
        )
    if editor_state.get("inspector_collapsed", False):
        return

    panel_rect = pr.Rectangle(324, 38, 156, 232)
    g_ui.ui_begin_panel(
        ui_state, "animation_inspector:panel", panel_rect, "Animation",
    )
    entity = get_selected_animation_entity(
        entities, player_entity, editor_state,
    )
    if entity is None:
        g_ui.ui_label(
            ui_state, "animation_inspector:none",
            "Click an entity to inspect", color=g_ui.UI_MUTED, font_size=8,
        )
        g_ui.ui_end_panel(ui_state)
        return

    collection_name = editor_state.get("selected_collection")
    entity_id = editor_state.get("selected_id")
    entity_name = (
        "player" if collection_name == "player"
        else str(entity.get("type", "entity"))
    )
    g_ui.ui_label(
        ui_state, "animation_inspector:selected",
        f"{entity_name} [{entity_id}]", color=g_ui.UI_ACCENT, font_size=8,
    )
    tracks = animation_debug_tracks_for_entity(entity, collection_name)
    if not tracks:
        g_ui.ui_label(
            ui_state, "animation_inspector:unsupported",
            "No debug animation tracks", color=g_ui.UI_MUTED, font_size=8,
        )
        g_ui.ui_end_panel(ui_state)
        return

    debug = editor_state.setdefault(
        "animation_debug", make_editor_state()["animation_debug"],
    )
    track_name = debug.get("track")
    if track_name not in tracks:
        track_name = next(iter(tracks))
    track_name, track_changed = g_ui.ui_dropdown(
        ui_state, "animation_inspector:track", "track", track_name,
        tuple(tracks), max_visible=6,
    )
    if track_changed or debug.get("track") != track_name:
        debug["track"] = track_name
        debug["phase"] = 0.0
        debug["keyframe"] = 0
    track = tracks[track_name]
    pose_names = tuple(track.get("pose_names", ("pose",)))
    pose_count = max(1, len(pose_names))

    if collection_name == "player":
        debug["facing"], _ = g_ui.ui_dropdown(
            ui_state, "animation_inspector:facing", "facing",
            debug.get("facing", "right"), ("right", "left"),
            max_visible=2,
        )
    debug["playback"], _ = g_ui.ui_dropdown(
        ui_state, "animation_inspector:playback", "playback",
        debug.get("playback", "continuous"),
        ANIMATION_DEBUG_PLAYBACK_MODES, max_visible=2,
    )
    debug["cycle_seconds"], _ = g_ui.ui_number_input_float(
        ui_state, "animation_inspector:cycle_seconds", "cycle seconds",
        debug.get("cycle_seconds", 1.0), 0.1, 10.0,
    )
    keyframe = int(debug.get("keyframe", 0)) % pose_count
    g_ui.ui_label(
        ui_state, "animation_inspector:pose",
        f"pose {keyframe + 1}/{pose_count}: {pose_names[keyframe]}",
        color=g_ui.UI_TEXT, font_size=8,
    )
    if g_ui.ui_button(
            ui_state, "animation_inspector:previous", "< previous pose"):
        step_animation_debug_keyframe(editor_state, pose_count, -1)
    if g_ui.ui_button(
            ui_state, "animation_inspector:next", "next pose >"):
        step_animation_debug_keyframe(editor_state, pose_count, 1)
    update_animation_debug_shortcuts(editor_state, pose_count, ui_state)
    g_ui.ui_separator(ui_state, "animation_inspector:hint_separator")
    g_ui.ui_label(
        ui_state, "animation_inspector:hint1",
        "Left/Right: step", color=g_ui.UI_MUTED, font_size=8,
    )
    g_ui.ui_label(
        ui_state, "animation_inspector:hint2",
        "Space: play/freeze", color=g_ui.UI_MUTED, font_size=8,
    )
    g_ui.ui_end_panel(ui_state)


def draw_editor_overlay(ui_state, editor_state, editor_mode, entities, lighting_profile, fog_profile, wind_profile, game_camera, tile_map, show_editor, rain_profile=None, audio_profile=None, audio_runtime=None, redhead_movement_defaults=None, redhead_evade_defaults=None, redhead_perception_defaults=None, redhead_flee_defaults=None, player_entity=None):
    if not show_editor:
        return editor_mode
    editor_mode = draw_editor_toolbar(ui_state, editor_state, editor_mode, entities, tile_map)

    if editor_mode == "environment":
        update_editor_shortcuts(entities, editor_state, ui_state, tile_map)
        update_environment_world(entities, editor_state, ui_state, game_camera, tile_map)
        draw_environment_handles(entities, editor_state, game_camera, tile_map)

        if editor_state.get("tool") == "place" and not ui_state.get("mouse_captured"):
            draw_placement_preview(editor_state, game_camera, tile_map)

        draw_inspector(
            ui_state, editor_state, entities, lighting_profile, fog_profile,
            wind_profile, tile_map, rain_profile, audio_profile, audio_runtime,
        )
    elif editor_mode == "entity" and ui_state.get("focused_id") is None:
        if pr.is_key_pressed(pr.KeyboardKey.KEY_Q):
            editor_state["tool"] = "select"
        if pr.is_key_pressed(pr.KeyboardKey.KEY_P):
            editor_state["tool"] = "place"

    if editor_mode == "entity":
        draw_gameplay_entity_inspector(
            ui_state, editor_state, entities, redhead_movement_defaults,
            redhead_evade_defaults, redhead_perception_defaults,
            redhead_flee_defaults,
        )
    elif editor_mode == "animation":
        draw_animation_debug_inspector(
            ui_state, editor_state, entities, player_entity,
        )

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
        "manipulate": apply_environment_drag,
        "radial_wheel": {
            "field": "radius", "step": 8.0,
            "minimum": 4.0, "maximum": 2000.0,
        },
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
        "manipulate": apply_environment_drag,
        "radial_wheel": {
            "field": "radius", "step": 8.0,
            "minimum": 4.0, "maximum": 2000.0,
        },
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
    },
    "smoke_emitter": {
        "target_collection": "emitters", "object_type": "smoke", "factory": g_effects.make_default_smoke_emitter,
        "display_name": "Smoke emitter", "icon": "~", "debug_color": (170, 175, 190),
        "selected_kind": "emitter", "id_prefix": "emitter", "inspector": inspect_smoke_emitter,
        "hit_test": hit_test_emitter, "hit_priority": 3, "handles": draw_emitter_handles,
        "handle_hit_test": get_drag_handle, "manipulate": apply_environment_drag
    },
    "fire_emitter": {
        "target_collection": "emitters", "object_type": "fire", "factory": g_effects.make_default_fire_emitter,
        "display_name": "Fire emitter", "icon": "^", "debug_color": (255, 120, 45),
        "selected_kind": "emitter", "id_prefix": "emitter", "inspector": inspect_fire_emitter,
        "hit_test": hit_test_emitter, "hit_priority": 3, "handles": draw_emitter_handles,
        "handle_hit_test": get_drag_handle, "manipulate": apply_environment_drag
    },
    "ember_emitter": {
        "target_collection": "emitters", "object_type": "ember", "factory": g_effects.make_default_ember_emitter,
        "display_name": "Ember emitter", "icon": ".", "debug_color": (255, 190, 60),
        "selected_kind": "emitter", "id_prefix": "emitter", "inspector": inspect_ember_emitter,
        "hit_test": hit_test_emitter, "hit_priority": 3, "handles": draw_emitter_handles,
        "handle_hit_test": get_drag_handle, "manipulate": apply_environment_drag
    },
    "sound_emitter": {
        "target_collection": "sound_emitters", "object_type": "sound",
        "factory": g_audio.make_default_sound_emitter,
        "display_name": "Sound emitter", "icon": "S", "debug_color": (150, 220, 255),
        "selected_kind": "sound_emitter", "id_prefix": "sound",
        "inspector": inspect_sound_emitter,
        "hit_test": hit_test_sound_emitter, "hit_priority": 2,
        "handles": draw_sound_emitter_handles,
        "handle_hit_test": get_drag_handle, "manipulate": apply_environment_drag,
        "radial_wheel": {
            "field": "maximum_distance", "step": 16.0,
            "minimum": 1.0, "maximum": 4000.0,
            "minimum_field": "minimum_distance", "minimum_gap": 1.0,
        },
    },
}

# Kept as a compatibility export, but derived from the registry so it cannot
# drift away from the environment editor's actual supported object types.
PLACEMENT_TYPES = get_environment_placement_types()
