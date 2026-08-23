import copy
import math


SORT_LAYER_ORDER = {"floor": 0, "world": 100, "overlay": 200}
ENTITY_RENDER_METADATA_VERSION = 1
PLAYER_WEAPON_BEZIER_DEFAULTS = {
    # Local-space values: X is along the aim direction and Y is perpendicular.
    "control_1_radial_fraction": 0.99,
    "control_1_perpendicular": 1.5,
    "control_2_radial_fraction": 0.99,
    "control_2_perpendicular": 1.0,
}

# First-pass cutout rig tuning. These values deliberately live in the
# reloadable render module so the animation can be tuned while the game runs.
# All pivots are in the shared 32x32 player-asset coordinate space.
PLAYER_CUTOUT_RIG_DEFAULTS = {
    "enabled": True,
    # Footstep distance comes from the audio profile. Zero degrees means that
    # queued footfalls land exactly on keyframes 0 and 2 below.
    "footfall_phase_degrees": 0.0,
    "movement_blend_response": 14.0,
    "profile_blend_response": 10.0,
    "canvas_size": 32.0,
    # The torso keeps the original bind hip while each leg gets its own
    # attachment. The far attachment sits one pixel toward the back and one
    # pixel higher in the right-facing source pose; X mirrors when facing left.
    "hip": {"x": 16.0, "y": 22.0},
    "near_hip": {"x": 16.0, "y": 22.0},
    "far_hip": {"x": 15.0, "y": 21.0},
    "knee": {"x": 16.0, "y": 26.0},
    "neck": {"x": 16.0, "y": 10.0},
    "far_leg_tint": [190, 190, 205, 255],
    "far_arm_tint": [190, 190, 205, 255],
}

# Four equally spaced poses make up each complete two-step cycle. Numeric
# values are smoothstepped between poses and wrap from pose 3 back to pose 0.
# Near and far limbs are authored independently on the same timeline. This
# keeps alternating contacts while preventing both sides from retracing the
# same silhouette with only a tint and half-cycle offset to distinguish them.
PLAYER_CUTOUT_GAIT_PROFILES = {
    "walk": [
        # Contact, passing, opposite contact, recovery.
        {"near_upper_leg_degrees": 24.0, "near_knee_bend_degrees": 0.0,
         "far_upper_leg_degrees": -26.0, "far_knee_bend_degrees": 0.0,
         "near_upper_arm_degrees": -15.0, "near_elbow_bend_degrees": 18.0,
         "far_upper_arm_degrees": 12.0, "far_elbow_bend_degrees": 24.0,
         "body_y_pixels": 0.0, "torso_degrees": 0.5},
        {"near_upper_leg_degrees": 0.0, "near_knee_bend_degrees": 22.0,
         "far_upper_leg_degrees": -8.0, "far_knee_bend_degrees": 30.0,
         "near_upper_arm_degrees": -4.0, "near_elbow_bend_degrees": 24.0,
         "far_upper_arm_degrees": 8.0, "far_elbow_bend_degrees": 32.0,
         "body_y_pixels": -0.75, "torso_degrees": -1.0},
        {"near_upper_leg_degrees": -24.0, "near_knee_bend_degrees": -6.0,
         "far_upper_leg_degrees": 20.0, "far_knee_bend_degrees": 4.0,
         "near_upper_arm_degrees": 15.0, "near_elbow_bend_degrees": 18.0,
         "far_upper_arm_degrees": -11.0, "far_elbow_bend_degrees": 20.0,
         "body_y_pixels": 0.0, "torso_degrees": 0.5},
        {"near_upper_leg_degrees": 0.0, "near_knee_bend_degrees": 34.0,
         "far_upper_leg_degrees": 7.0, "far_knee_bend_degrees": 24.0,
         "near_upper_arm_degrees": 4.0, "near_elbow_bend_degrees": 28.0,
         "far_upper_arm_degrees": -6.0, "far_elbow_bend_degrees": 28.0,
         "body_y_pixels": -0.75, "torso_degrees": 1.5},
    ],
    "run": [
        # Contact, recoil/passing, opposite contact, flight/recovery.
        {"near_upper_leg_degrees": 65.0, "near_knee_bend_degrees": 60.0,
         "far_upper_leg_degrees": -26.0, "far_knee_bend_degrees": 24.0,
         "near_upper_arm_degrees": -38.0, "near_elbow_bend_degrees": 90.0,
         "far_upper_arm_degrees": 42.0, "far_elbow_bend_degrees": 42.0,
         "body_y_pixels": 0.0, "torso_degrees": 1.0},
        {"near_upper_leg_degrees": -4.0, "near_knee_bend_degrees": 58.0,
         "far_upper_leg_degrees": 12.0, "far_knee_bend_degrees": 52.0,
         "near_upper_arm_degrees": -16.0, "near_elbow_bend_degrees": 60.0,
         "far_upper_arm_degrees": 24.0, "far_elbow_bend_degrees": 48.0,
         "body_y_pixels": -1.75, "torso_degrees": 1.5},
        {"near_upper_leg_degrees": -32.0, "near_knee_bend_degrees": 18.0,
         "far_upper_leg_degrees": 52.0, "far_knee_bend_degrees": 48.0,
         "near_upper_arm_degrees": 60.0, "near_elbow_bend_degrees": 38.0,
         "far_upper_arm_degrees": -30.0, "far_elbow_bend_degrees": 72.0,
         "body_y_pixels": 0.0, "torso_degrees": 1.0},
        {"near_upper_leg_degrees": 6.0, "near_knee_bend_degrees": 64.0,
         "far_upper_leg_degrees": -10.0, "far_knee_bend_degrees": 54.0,
         "near_upper_arm_degrees": 8.0, "near_elbow_bend_degrees": 64.0,
         "far_upper_arm_degrees": -14.0, "far_elbow_bend_degrees": 56.0,
         "body_y_pixels": -1.75, "torso_degrees": 2.0},
    ],
}

PLAYER_CUTOUT_TEXTURES = {
    "head": "player_cutout_head_right",
    "torso": "player_cutout_torso_right",
    "upper_leg": "player_cutout_upper_leg_right",
    "lower_leg": "player_cutout_lower_leg_right",
    "upper_arm": "player_cutout_upper_arm_right",
    "lower_arm": "player_cutout_lower_arm_right",
    "gun": "player_cutout_gun_right",
}

# Arm pivots are taken from the authored neutral and aimed references. The
# actual arm textures stay in their clean vertical bind pose; two-bone IK bends
# that chain while the hand smoothsteps between hanging and fully aimed.
PLAYER_CUTOUT_ARM_DEFAULTS = {
    # These describe pixels in the authored vertical source art and normally
    # should not be tuned with the animation pose.
    "bind_pose": {
        "shoulder": {"x": 15.5, "y": 11.0},
        "elbow": {"x": 15.5, "y": 14.0},
        "hand": {"x": 15.5, "y": 17.5},
    },
    # Independently tunable torso attachment points. The existing shoulder is
    # retained as the near-arm position so previous tuning remains valid.
    "shoulder": {"x": 15.5, "y": 12.0},
    "far_shoulder": {"x": 14.5, "y": 11.0},
    "aim_reach": 6.5,
    "gun_grip": {"x": 0.0, "y": 2.0},
    "gun_source_size": 4.0,
    # The hand meets the top of the grip; the gun pivot sits one pixel below
    # the aim line, matching player_aim_reference_right.png.
    "gun_grip_perpendicular_offset": 1.0,
    "ik_bend_side": 1.0,
    "far_arm_aim_motion_scale": 0.25,
}


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
    normalized_render_type = str(render_type).lower().replace("_", " ")
    if (entity.get("_render_metadata_version")
            == ENTITY_RENDER_METADATA_VERSION
            and entity.get("_render_metadata_type") == normalized_render_type):
        return entity
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
    entity["_render_metadata_version"] = ENTITY_RENDER_METADATA_VERSION
    entity["_render_metadata_type"] = normalized_render_type
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
        "light_sample_height": float(entity.get("light_sample_height", entity.get("visual_height", height) * 0.55)), "ground_footprint": entity.get("ground_footprint", {}),
        "self_shadow": entity.get("self_shadow", {}), "entity_light_occluder": entity.get("entity_light_occluder", {}), "shadow": entity.get("shadow", {}), "render_style": entity.get("render_style", "world"),
        "outline": entity.get("outline", {}), "occludes_render_items": bool(entity.get("occludes_render_items", False)), "fog_interaction": entity.get("fog_interaction", {"mode": "standard"}),
        "water_interaction": entity.get("water_interaction", {"mode": "standard"}), "draw_data": draw_data or {}
    }


def _asset_dimension(game_assets, collection, name, dimension, fallback):
    asset = game_assets.get(collection, {}).get(name)
    if isinstance(asset, dict):
        asset = asset.get("sheet")
    try:
        return float(getattr(asset, dimension, fallback) if asset is not None else fallback)
    except (TypeError, ValueError):
        return float(fallback)


def cubic_bezier_scalar(start, control_1, control_2, end, progress):
    t = max(0.0, min(1.0, float(progress)))
    inverse = 1.0 - t
    return (
        inverse * inverse * inverse * float(start)
        + 3.0 * inverse * inverse * t * float(control_1)
        + 3.0 * inverse * t * t * float(control_2)
        + t * t * t * float(end)
    )


def player_weapon_bezier_world_position(center, aim, end_distance, progress,
                                         settings=None):
    settings = settings or PLAYER_WEAPON_BEZIER_DEFAULTS
    end_distance = float(end_distance)
    radial = cubic_bezier_scalar(
        0.0,
        end_distance * float(settings["control_1_radial_fraction"]),
        end_distance * float(settings["control_2_radial_fraction"]),
        end_distance,
        progress,
    )
    perpendicular_offset = cubic_bezier_scalar(
        0.0,
        float(settings["control_1_perpendicular"]),
        float(settings["control_2_perpendicular"]),
        0.0,
        progress,
    )
    perpendicular = {"x": -aim["y"], "y": aim["x"]}
    return {
        "x": center["x"] + aim["x"] * radial
             + perpendicular["x"] * perpendicular_offset,
        "y": center["y"] + aim["y"] * radial
             + perpendicular["y"] * perpendicular_offset,
    }


def _rotate_rig_vector(x, y, angle_degrees):
    angle = math.radians(float(angle_degrees))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return {
        "x": float(x) * cosine - float(y) * sine,
        "y": float(x) * sine + float(y) * cosine,
    }


def _make_player_cutout_part(texture_name, source_pivot, target_pivot,
                              rotation, facing_left=False, tint=None,
                              source_canvas_width=None):
    canvas_size = float(PLAYER_CUTOUT_RIG_DEFAULTS["canvas_size"])
    source_canvas_width = float(source_canvas_width or canvas_size)
    target_x = float(target_pivot["x"])
    origin_x = float(source_pivot["x"])
    if facing_left:
        target_x = canvas_size - target_x
        origin_x = source_canvas_width - origin_x
        rotation = -float(rotation)
    return {
        "texture": texture_name,
        "pivot_local": {"x": target_x, "y": float(target_pivot["y"])},
        "origin": {"x": origin_x, "y": float(source_pivot["y"])},
        "rotation": float(rotation),
        "flip_x": bool(facing_left),
        "tint": list(tint or [255, 255, 255, 255]),
    }


def player_cutout_gait_phase_from_step_state(step_state, stride_distance):
    """Map the shared footstep clock to a two-foot procedural gait cycle."""
    step_state = step_state if isinstance(step_state, dict) else {}
    stride = max(1.0, float(stride_distance))
    distance = max(0.0, float(step_state.get("distance", 0.0)))
    stride_index = int(step_state.get("stride_index", 0))
    half_cycle_progress = min(1.0, distance / stride)
    return (stride_index * math.pi + half_cycle_progress * math.pi) % math.tau


def sample_player_cutout_gait_profile(profile, phase):
    """Smoothly sample an equally spaced, cyclic gait pose profile."""
    poses = profile if isinstance(profile, (list, tuple)) else []
    if not poses:
        return {}
    try:
        normalized_phase = (float(phase) % math.tau) / math.tau
    except (TypeError, ValueError, OverflowError):
        normalized_phase = 0.0
    if not math.isfinite(normalized_phase):
        normalized_phase = 0.0
    scaled_phase = normalized_phase * len(poses)
    pose_index = int(math.floor(scaled_phase)) % len(poses)
    next_index = (pose_index + 1) % len(poses)
    amount = scaled_phase - math.floor(scaled_phase)
    amount = amount * amount * (3.0 - 2.0 * amount)
    current = poses[pose_index]
    following = poses[next_index]
    return {
        key: float(current.get(key, 0.0)) + (
            float(following.get(key, current.get(key, 0.0)))
            - float(current.get(key, 0.0))
        ) * amount
        for key in current
    }


def _blended_player_cutout_gait_pose(phase, run_blend):
    walk = sample_player_cutout_gait_profile(
        PLAYER_CUTOUT_GAIT_PROFILES["walk"], phase,
    )
    run = sample_player_cutout_gait_profile(
        PLAYER_CUTOUT_GAIT_PROFILES["run"], phase,
    )
    amount = max(0.0, min(1.0, float(run_blend)))
    return {
        key: float(walk.get(key, 0.0)) + (
            float(run.get(key, walk.get(key, 0.0)))
            - float(walk.get(key, 0.0))
        ) * amount
        for key in walk
    }


def _rig_vector_angle_degrees(source, target):
    source_angle = math.atan2(float(source["y"]), float(source["x"]))
    target_angle = math.atan2(float(target["y"]), float(target["x"]))
    result = math.degrees(target_angle - source_angle)
    return (result + 180.0) % 360.0 - 180.0


def _solve_player_arm_ik(shoulder, target, upper_length, lower_length,
                         bend_side=1.0):
    """Return elbow and reachable hand points for a two-segment arm."""
    delta_x = float(target["x"]) - float(shoulder["x"])
    delta_y = float(target["y"]) - float(shoulder["y"])
    distance = math.hypot(delta_x, delta_y)
    if distance <= 0.000001:
        delta_x, delta_y, distance = 0.0, 1.0, 1.0
    direction_x = delta_x / distance
    direction_y = delta_y / distance
    minimum_reach = abs(float(upper_length) - float(lower_length))
    maximum_reach = float(upper_length) + float(lower_length)
    reachable_distance = max(minimum_reach, min(maximum_reach, distance))
    hand = {
        "x": float(shoulder["x"]) + direction_x * reachable_distance,
        "y": float(shoulder["y"]) + direction_y * reachable_distance,
    }
    along = (
        float(upper_length) * float(upper_length)
        - float(lower_length) * float(lower_length)
        + reachable_distance * reachable_distance
    ) / max(0.000001, 2.0 * reachable_distance)
    height_squared = max(
        0.0, float(upper_length) * float(upper_length) - along * along,
    )
    height = math.sqrt(height_squared) * (1.0 if bend_side >= 0.0 else -1.0)
    elbow = {
        "x": float(shoulder["x"]) + direction_x * along - direction_y * height,
        "y": float(shoulder["y"]) + direction_y * along + direction_x * height,
    }
    return elbow, hand


def _player_weapon_transition_progress(player_entity):
    transition = player_entity.get("weapon_transition", {})
    try:
        progress = max(0.0, min(1.0, float(transition.get(
            "progress", 1.0 if player_entity.get("aiming", False) else 0.0,
        ))))
    except (TypeError, ValueError, OverflowError):
        progress = 0.0
    return progress if math.isfinite(progress) else 0.0


def _player_arm_shoulder(body_hip, torso_angle, is_far=False):
    attachment = PLAYER_CUTOUT_ARM_DEFAULTS[
        "far_shoulder" if is_far else "shoulder"
    ]
    hip = PLAYER_CUTOUT_RIG_DEFAULTS["hip"]
    shoulder_from_hip = _rotate_rig_vector(
        float(attachment["x"]) - float(hip["x"]),
        float(attachment["y"]) - float(hip["y"]),
        torso_angle,
    )
    return {
        "x": float(body_hip["x"]) + shoulder_from_hip["x"],
        "y": float(body_hip["y"]) + shoulder_from_hip["y"],
    }


def _build_player_locomotion_arm_pose(arm_phase, run_blend, movement_blend,
                                       body_hip, torso_angle, facing_left,
                                       is_far=False, motion_scale=1.0):
    settings = PLAYER_CUTOUT_ARM_DEFAULTS
    bind_pose = settings["bind_pose"]
    source_shoulder = bind_pose["shoulder"]
    source_elbow = bind_pose["elbow"]
    source_hand = bind_pose["hand"]
    upper_bind = {
        "x": float(source_elbow["x"]) - float(source_shoulder["x"]),
        "y": float(source_elbow["y"]) - float(source_shoulder["y"]),
    }
    lower_bind = {
        "x": float(source_hand["x"]) - float(source_elbow["x"]),
        "y": float(source_hand["y"]) - float(source_elbow["y"]),
    }
    gait_pose = _blended_player_cutout_gait_pose(arm_phase, run_blend)
    swing_scale = max(0.0, float(motion_scale)) * float(movement_blend)
    side = "far" if is_far else "near"
    upper_angle = torso_angle + float(
        gait_pose.get(f"{side}_upper_arm_degrees", 0.0)
    ) * swing_scale
    lower_angle = upper_angle - float(
        gait_pose.get(f"{side}_elbow_bend_degrees", 0.0)
    ) * swing_scale
    shoulder = _player_arm_shoulder(body_hip, torso_angle, is_far)
    elbow_offset = _rotate_rig_vector(
        upper_bind["x"], upper_bind["y"], upper_angle,
    )
    elbow = {
        "x": shoulder["x"] + elbow_offset["x"],
        "y": shoulder["y"] + elbow_offset["y"],
    }
    hand_offset = _rotate_rig_vector(
        lower_bind["x"], lower_bind["y"], lower_angle,
    )
    hand = {
        "x": elbow["x"] + hand_offset["x"],
        "y": elbow["y"] + hand_offset["y"],
    }
    tint = PLAYER_CUTOUT_RIG_DEFAULTS["far_arm_tint"] if is_far else None
    upper_part = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["upper_arm"], source_shoulder, shoulder,
        upper_angle, facing_left, tint,
    )
    lower_part = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["lower_arm"], source_elbow, elbow,
        lower_angle, facing_left, tint,
    )
    upper_part.update({"rig_side": side, "rig_joint": "upper_arm"})
    lower_part.update({"rig_side": side, "rig_joint": "lower_arm"})
    return {
        "shoulder": shoulder,
        "elbow": elbow,
        "hand": hand,
        "upper_part": upper_part,
        "lower_part": lower_part,
    }


def _build_player_weapon_cutout_parts(player_entity, body_hip, torso_angle,
                                       facing_left, locomotion_pose=None):
    progress = _player_weapon_transition_progress(player_entity)
    if progress <= 0.000001:
        return []

    settings = PLAYER_CUTOUT_ARM_DEFAULTS
    bind_pose = settings["bind_pose"]
    source_shoulder = bind_pose["shoulder"]
    source_elbow = bind_pose["elbow"]
    source_hand = bind_pose["hand"]
    shoulder = (
        locomotion_pose["shoulder"] if isinstance(locomotion_pose, dict)
        else _player_arm_shoulder(body_hip, torso_angle)
    )

    aim = normalize_vector(player_entity.get("aim_direction", {}))
    if aim is None:
        aim = {"x": -1.0 if facing_left else 1.0, "y": 0.0}
    # Solve the right-facing bind pose, then mirror the completed part records.
    canonical_aim = {
        "x": -float(aim["x"]) if facing_left else float(aim["x"]),
        "y": float(aim["y"]),
    }
    canonical_aim = normalize_vector(canonical_aim) or {"x": 1.0, "y": 0.0}

    if isinstance(locomotion_pose, dict):
        neutral_elbow = locomotion_pose["elbow"]
        neutral_hand = locomotion_pose["hand"]
    else:
        bind_arm = {
            "x": float(source_hand["x"]) - float(source_shoulder["x"]),
            "y": float(source_hand["y"]) - float(source_shoulder["y"]),
        }
        neutral_arm = _rotate_rig_vector(
            bind_arm["x"], bind_arm["y"], torso_angle,
        )
        neutral_elbow = {
            "x": shoulder["x"],
            "y": shoulder["y"] + math.hypot(
                float(source_elbow["x"]) - float(source_shoulder["x"]),
                float(source_elbow["y"]) - float(source_shoulder["y"]),
            ),
        }
        neutral_hand = {
            "x": shoulder["x"] + neutral_arm["x"],
            "y": shoulder["y"] + neutral_arm["y"],
        }
    aimed_hand = {
        "x": shoulder["x"] + canonical_aim["x"] * float(settings["aim_reach"]),
        "y": shoulder["y"] + canonical_aim["y"] * float(settings["aim_reach"]),
    }
    pose_amount = progress * progress * (3.0 - 2.0 * progress)
    requested_hand = {
        "x": neutral_hand["x"] + (aimed_hand["x"] - neutral_hand["x"]) * pose_amount,
        "y": neutral_hand["y"] + (aimed_hand["y"] - neutral_hand["y"]) * pose_amount,
    }

    upper_bind = {
        "x": float(source_elbow["x"]) - float(source_shoulder["x"]),
        "y": float(source_elbow["y"]) - float(source_shoulder["y"]),
    }
    lower_bind = {
        "x": float(source_hand["x"]) - float(source_elbow["x"]),
        "y": float(source_hand["y"]) - float(source_elbow["y"]),
    }
    shoulder_to_hand = {
        "x": neutral_hand["x"] - shoulder["x"],
        "y": neutral_hand["y"] - shoulder["y"],
    }
    shoulder_to_elbow = {
        "x": neutral_elbow["x"] - shoulder["x"],
        "y": neutral_elbow["y"] - shoulder["y"],
    }
    bend_cross = (
        shoulder_to_hand["x"] * shoulder_to_elbow["y"]
        - shoulder_to_hand["y"] * shoulder_to_elbow["x"]
    )
    bend_side = (
        1.0 if bend_cross > 0.000001 else
        -1.0 if bend_cross < -0.000001 else settings["ik_bend_side"]
    )
    elbow, hand = _solve_player_arm_ik(
        shoulder, requested_hand,
        math.hypot(upper_bind["x"], upper_bind["y"]),
        math.hypot(lower_bind["x"], lower_bind["y"]),
        bend_side,
    )
    upper_angle = _rig_vector_angle_degrees(
        upper_bind,
        {"x": elbow["x"] - shoulder["x"], "y": elbow["y"] - shoulder["y"]},
    )
    lower_angle = _rig_vector_angle_degrees(
        lower_bind,
        {"x": hand["x"] - elbow["x"], "y": hand["y"] - elbow["y"]},
    )

    neutral_direction = normalize_vector({
        "x": neutral_hand["x"] - neutral_elbow["x"],
        "y": neutral_hand["y"] - neutral_elbow["y"],
    }) or {"x": 0.0, "y": 1.0}
    gun_direction = normalize_vector({
        "x": neutral_direction["x"] + (
            canonical_aim["x"] - neutral_direction["x"]
        ) * pose_amount,
        "y": neutral_direction["y"] + (
            canonical_aim["y"] - neutral_direction["y"]
        ) * pose_amount,
    }) or canonical_aim
    gun_perpendicular = {"x": -gun_direction["y"], "y": gun_direction["x"]}
    gun_grip = {
        "x": hand["x"] + gun_perpendicular["x"] * float(
            settings["gun_grip_perpendicular_offset"]
        ),
        "y": hand["y"] + gun_perpendicular["y"] * float(
            settings["gun_grip_perpendicular_offset"]
        ),
    }
    try:
        recoil_degrees = max(0.0, float(
            player_entity.get("weapon_visual_recoil", {}).get(
                "rotation_degrees", 0.0,
            )
        ))
    except (TypeError, ValueError, OverflowError):
        recoil_degrees = 0.0
    if not math.isfinite(recoil_degrees):
        recoil_degrees = 0.0
    gun_angle = math.degrees(math.atan2(gun_direction["y"], gun_direction["x"]))
    gun_angle -= recoil_degrees

    upper_part = _make_player_cutout_part(
            PLAYER_CUTOUT_TEXTURES["upper_arm"], source_shoulder, shoulder,
            upper_angle, facing_left,
        )
    lower_part = _make_player_cutout_part(
            PLAYER_CUTOUT_TEXTURES["lower_arm"], source_elbow, elbow,
            lower_angle, facing_left,
        )
    gun_part = _make_player_cutout_part(
            PLAYER_CUTOUT_TEXTURES["gun"], settings["gun_grip"], gun_grip,
            gun_angle, facing_left, source_canvas_width=settings["gun_source_size"],
        )
    upper_part.update({"rig_side": "near", "rig_joint": "upper_arm"})
    lower_part.update({"rig_side": "near", "rig_joint": "lower_arm"})
    gun_part.update({"rig_side": "near", "rig_joint": "gun"})
    return [upper_part, lower_part, gun_part]


def build_player_cutout_rig_parts(player_entity):
    """Build one composite side-view pose from the aligned cutout textures."""
    settings = PLAYER_CUTOUT_RIG_DEFAULTS
    if not settings.get("enabled", True):
        return []
    direction = player_entity.get("animation_direction")
    if direction is None:
        frame_name = str(player_entity.get("animation_frame", ""))
        direction = next(
            (name for name in ("left", "right") if frame_name.startswith(name)),
            None,
        )
    if direction not in {"left", "right"}:
        return []

    gait = player_entity.get("procedural_gait", {})
    try:
        phase = (
            float(gait.get("phase", 0.0))
            + math.radians(float(settings["footfall_phase_degrees"]))
        ) % math.tau
        blend = max(0.0, min(1.0, float(gait.get("blend", 0.0))))
        run_blend = max(0.0, min(1.0, float(gait.get("run_blend", 0.0))))
    except (TypeError, ValueError, OverflowError):
        phase = 0.0
        blend = 0.0
        run_blend = 0.0
    if not math.isfinite(phase):
        phase = 0.0
    if not math.isfinite(blend):
        blend = 0.0
    if not math.isfinite(run_blend):
        run_blend = 0.0

    hip = settings["hip"]
    knee = settings["knee"]
    neck = settings["neck"]
    upper_length = {
        "x": float(knee["x"]) - float(hip["x"]),
        "y": float(knee["y"]) - float(hip["y"]),
    }
    body_pose = _blended_player_cutout_gait_pose(phase, run_blend)
    bob = float(body_pose.get("body_y_pixels", 0.0)) * blend
    torso_angle = float(body_pose.get("torso_degrees", 0.0)) * blend
    body_hip = {"x": float(hip["x"]), "y": float(hip["y"]) + bob}
    neck_from_hip = _rotate_rig_vector(
        float(neck["x"]) - float(hip["x"]),
        float(neck["y"]) - float(hip["y"]),
        torso_angle,
    )
    body_neck = {
        "x": body_hip["x"] + neck_from_hip["x"],
        "y": body_hip["y"] + neck_from_hip["y"],
    }
    facing_left = direction == "left"

    leg_parts = []
    for is_far in (True, False):
        side = "far" if is_far else "near"
        attachment = settings[f"{side}_hip"]
        hip_offset = _rotate_rig_vector(
            float(attachment["x"]) - float(hip["x"]),
            float(attachment["y"]) - float(hip["y"]),
            torso_angle,
        )
        target_hip = {
            "x": body_hip["x"] + hip_offset["x"],
            "y": body_hip["y"] + hip_offset["y"],
        }
        upper_angle = float(
            body_pose.get(f"{side}_upper_leg_degrees", 0.0)
        ) * blend
        knee_bend = float(
            body_pose.get(f"{side}_knee_bend_degrees", 0.0)
        ) * blend
        lower_angle = upper_angle + knee_bend
        knee_offset = _rotate_rig_vector(
            upper_length["x"], upper_length["y"], upper_angle,
        )
        target_knee = {
            "x": target_hip["x"] + knee_offset["x"],
            "y": target_hip["y"] + knee_offset["y"],
        }
        tint = settings["far_leg_tint"] if is_far else None
        lower_part = _make_player_cutout_part(
                PLAYER_CUTOUT_TEXTURES["lower_leg"], knee, target_knee,
                lower_angle, facing_left, tint,
            )
        upper_part = _make_player_cutout_part(
                PLAYER_CUTOUT_TEXTURES["upper_leg"], hip, target_hip,
                upper_angle, facing_left, tint,
            )
        lower_part.update({"rig_side": side, "rig_joint": "lower_leg"})
        upper_part.update({"rig_side": side, "rig_joint": "upper_leg"})
        leg_parts.append((lower_part, upper_part))

    torso = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["torso"], hip, body_hip, torso_angle,
        facing_left,
    )
    # Keeping the head level makes the torso movement readable without making
    # the character's view look mechanically tied to every step.
    head = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["head"], neck, body_neck, 0.0,
        facing_left,
    )
    weapon_progress = _player_weapon_transition_progress(player_entity)
    far_motion_scale = 1.0 - weapon_progress * (
        1.0 - float(PLAYER_CUTOUT_ARM_DEFAULTS["far_arm_aim_motion_scale"])
    )
    far_arm = _build_player_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle,
        facing_left, is_far=True, motion_scale=far_motion_scale,
    )
    near_arm = _build_player_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle,
        facing_left, is_far=False,
    )
    weapon_parts = _build_player_weapon_cutout_parts(
        player_entity, body_hip, torso_angle, facing_left, near_arm,
    )
    near_arm_parts = weapon_parts or [
        near_arm["upper_part"], near_arm["lower_part"],
    ]
    far_lower, far_upper = leg_parts[0]
    near_lower, near_upper = leg_parts[1]
    return [
        far_arm["lower_part"], far_arm["upper_part"],
        far_lower, far_upper, torso, near_lower, near_upper,
        *near_arm_parts, head,
    ]


def entity_with_animation_debug_override(game_assets, collection_name,
                                         object_id, entity):
    override = game_assets.get("animation_debug_render_override")
    if (not isinstance(override, dict)
            or override.get("collection") != collection_name
            or override.get("id") != object_id
            or not isinstance(override.get("fields"), dict)):
        return entity
    result = dict(entity)
    for key, value in override["fields"].items():
        result[key] = copy.deepcopy(value)
    return result


def build_player_render_item(player_entity, tile_map, game_assets):
    player_entity = entity_with_animation_debug_override(
        game_assets, "player", player_entity.get("id", "player"), player_entity,
    )
    world_position = position_to_world(player_entity.get("position", {}), tile_map)
    sprite_sheet = game_assets.get("sprite_sheets", {}).get("blue_oxford_texture_sheet", {})
    frame_number = sprite_sheet.get(player_entity.get("animation_frame", 0), 0)
    aim = normalize_vector(player_entity.get("aim_direction", {"x": 0.0, "y": 0.0})) or {"x": 0.0, "y": 0.0}
    transition = player_entity.get("weapon_transition", {})
    try:
        transition_progress = max(
            0.0, min(1.0, float(transition.get(
                "progress", 1.0 if player_entity.get("aiming", False) else 0.0,
            ))),
        )
    except (TypeError, ValueError, OverflowError):
        transition_progress = 0.0
    cutout_parts = build_player_cutout_rig_parts(player_entity)
    body_bob = 0.0
    if cutout_parts:
        torso_part = next((
            part for part in cutout_parts
            if part.get("texture") == PLAYER_CUTOUT_TEXTURES["torso"]
        ), None)
        if torso_part is not None:
            body_bob = float(torso_part["pivot_local"]["y"]) - float(
                PLAYER_CUTOUT_RIG_DEFAULTS["hip"]["y"]
            )
    weapon_center = {
        "x": float(world_position["x"]),
        "y": float(world_position["y"]) + body_bob,
    }
    gun_position = player_weapon_bezier_world_position(
        weapon_center, aim, 4.0, transition_progress,
    )
    pistol_distance = 4.0
    pistol_texture = "pistol_texture"
    pistol_angle = math.degrees(math.atan2(aim["y"], aim["x"]))
    visual_recoil = player_entity.get("weapon_visual_recoil", {})
    try:
        recoil_degrees = max(
            0.0, float(visual_recoil.get("rotation_degrees", 0.0)),
        )
    except (TypeError, ValueError, OverflowError):
        recoil_degrees = 0.0
    if not math.isfinite(recoil_degrees):
        recoil_degrees = 0.0
    if aim["x"] < 0.0:
        pistol_distance = 8.0
        pistol_texture = "pistol_texture_flipped"
        pistol_angle += 180.0 + recoil_degrees
    else:
        pistol_angle -= recoil_degrees
    pistol_position = player_weapon_bezier_world_position(
        weapon_center, aim, pistol_distance, transition_progress,
    )
    draw_data = {
        "center_world": weapon_center,
        "gun_world": gun_position,
        "pistol_world": pistol_position,
        "pistol_texture": pistol_texture,
        "pistol_angle": pistol_angle,
        "pistol_recoil_degrees": recoil_degrees,
        "aiming": bool(player_entity.get("aiming", False)),
        "weapon_transition_progress": transition_progress,
        "weapon_transition_phase": transition.get("phase", "holstered"),
        "weapon_visible": transition_progress > 0.000001,
        "cutout_rig_parts": cutout_parts,
        "weapon_in_cutout_rig": any(
            part.get("texture") == PLAYER_CUTOUT_TEXTURES["gun"]
            for part in cutout_parts
        ),
    }
    render_item = make_world_render_item("entity", "player", "player", player_entity.get("id", "player"), player_entity, world_position, 32.0, 32.0, make_texture_reference("sprite_sheets", "blue_oxford_texture_sheet", "sheet"), {"x": float(frame_number) * 32.0, "y": 0.0, "width": 32.0, "height": 32.0}, draw_data)
    render_item["screen_snap"] = "relative_motion"
    return render_item


def build_brain_render_item(object_id, entity, tile_map, game_assets):
    entity = entity_with_animation_debug_override(
        game_assets, "brains", object_id, entity,
    )
    entity_type = get_entity_render_type(entity)
    if entity_type not in {"red head", "buddha"}:
        return None
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
