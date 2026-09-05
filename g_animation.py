"""Pure cutout pose evaluation; no editor, graphics or filesystem dependency."""
import math
import g_animation_redhead_data as data

def _rotate_rig_vector(x, y, angle_degrees):
    angle = math.radians(float(angle_degrees))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return {
        "x": float(x) * cosine - float(y) * sine,
        "y": float(x) * sine + float(y) * cosine,
    }


def make_cutout_part(texture_name, source_pivot, target_pivot,
                              rotation, facing_left=False, tint=None,
                              source_canvas_width=None, scale_x=1.0,
                              scale_y=1.0, target_canvas_width=None):
    canvas_size = float(
        target_canvas_width or 32.0
    )
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
        "scale": {"x": float(scale_x), "y": float(scale_y)},
        "tint": list(tint or [255, 255, 255, 255]),
    }


def sample_gait_profile(profile, phase):
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


def _blended_redhead_cutout_gait_pose(phase, run_blend, profiles):
    walk = sample_gait_profile(
        profiles["walk"], phase,
    )
    run = sample_gait_profile(
        profiles["run"], phase,
    )
    amount = max(0.0, min(1.0, float(run_blend)))
    return {
        key: float(walk.get(key, 0.0)) + (
            float(run.get(key, walk.get(key, 0.0)))
            - float(walk.get(key, 0.0))
        ) * amount
        for key in walk
    }


def _make_redhead_cutout_part(texture_name, source_pivot, target_pivot,
                               rotation, mirror=False, tint=None, canvas_size=24.0):
    return make_cutout_part(
        texture_name, source_pivot, target_pivot, rotation,
        facing_left=mirror, tint=tint,
        source_canvas_width=canvas_size,
        target_canvas_width=canvas_size,
    )


def highlight_component_parts(parts, highlight):
    """Tint only the selected texture instance; selection is never authored data."""
    field = highlight.get("field", "")
    side = field.split("_", 1)[0] if field.startswith(("near_", "far_")) else None
    if "upper_leg" in field:
        joints = {"upper_leg"}
    elif "knee_bend" in field:
        joints = {"lower_leg"}
    elif "knee_" in field:
        joints = {"upper_leg"}
    elif "foot_" in field:
        joints = {"lower_leg"}
    elif "front_leg" in field:
        joints = {"upper_leg", "lower_leg"}
    elif "elbow_bend" in field:
        joints = {"lower_arm"}
    elif "elbow_" in field:
        joints = {"upper_arm"}
    elif "hand_" in field:
        joints = {"lower_arm"}
    elif "arm" in field:
        joints = {"upper_arm"}
    elif "torso" in field:
        joints = {"torso"}
    elif field.startswith("body_"):
        joints = {"torso", "head"}
    else:
        joints = set()
    amount = max(0.0, min(1.0, float(highlight.get("amount", 0.0))))
    result = []
    for part in parts:
        if part.get("rig_joint") in joints and (side is None or part.get("rig_side") == side):
            tint = part.get("tint", [255, 255, 255, 255])
            part = dict(part, tint=[round(tint[i] + (target - tint[i]) * amount)
                                   for i, target in enumerate((255, 65, 220))] + [tint[3]])
        result.append(part)
    return result


def build_redhead_cutout_rig_parts(entity):
    """Build the red head's cardinal, speed-blended procedural locomotion."""
    draft = entity.get("animation_profile_override") or {}
    settings = draft.get("REDHEAD_CUTOUT_RIG_DEFAULTS", data.REDHEAD_CUTOUT_RIG_DEFAULTS)
    profiles = draft.get("REDHEAD_CUTOUT_GAIT_PROFILES", data.REDHEAD_CUTOUT_GAIT_PROFILES)
    if (not settings.get("enabled", True)
            or entity.get("current_state") == "dead"):
        return []
    direction = entity.get("animation_direction")
    if direction is None:
        frame_name = str(entity.get("animation_frame", ""))
        direction = next((
            name for name in ("left", "right", "up", "down")
            if frame_name.startswith(name)
        ), None)
    if direction not in {"left", "right", "up", "down"}:
        return []

    gait = entity.get("procedural_gait", {})
    try:
        phase = (
            float(gait.get("phase", 0.0))
            + math.radians(float(settings["footfall_phase_degrees"]))
        ) % math.tau
        blend = max(0.0, min(1.0, float(gait.get("blend", 0.0))))
        run_blend = max(
            0.0, min(1.0, float(gait.get("run_blend", 0.0)))
        )
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

    pose = _blended_redhead_cutout_gait_pose(phase, run_blend, profiles)
    front_facing = direction in {"up", "down"}
    rig = settings["front" if front_facing else "side"]
    texture_direction = direction if direction != "left" else "right"
    textures = data.REDHEAD_CUTOUT_TEXTURES[texture_direction]
    facing_left = direction == "left"
    body_x = float(pose.get("body_x_pixels", 0.0)) * blend
    body_y = float(pose.get("body_y_pixels", 0.0)) * blend
    torso_key = (
        "front_torso_degrees" if front_facing else "side_torso_degrees"
    )
    torso_angle = float(pose.get(torso_key, 0.0)) * blend
    bind_hip = rig["hip"]
    body_hip = {
        "x": float(bind_hip["x"]) + body_x,
        "y": float(bind_hip["y"]) + body_y,
    }
    neck = rig["neck"]
    neck_offset = _rotate_rig_vector(
        float(neck["x"]) - float(bind_hip["x"]),
        float(neck["y"]) - float(bind_hip["y"]), torso_angle,
    )
    body_neck = {
        "x": body_hip["x"] + neck_offset["x"],
        "y": body_hip["y"] + neck_offset["y"],
    }

    torso = _make_redhead_cutout_part(
        textures["torso"], bind_hip, body_hip, torso_angle, facing_left, canvas_size=settings["canvas_size"],
    )
    torso.update({
        "rig_joint": "torso", "body_bob": body_y,
        "body_sway": body_x,
    })
    head = _make_redhead_cutout_part(
        textures["head"], neck, body_neck, 0.0, facing_left, canvas_size=settings["canvas_size"],
    )
    head.update({"rig_joint": "head"})

    if front_facing:
        source_hip = rig["limb_hip"]
        source_shoulder = rig["shoulder"]
    else:
        source_hip = rig["hip"]
        source_shoulder = rig["shoulder"]
    source_knee = rig["knee"]
    source_foot = rig["foot"]
    source_elbow = rig["elbow"]
    upper_leg_vector = {
        "x": float(source_knee["x"]) - float(source_hip["x"]),
        "y": float(source_knee["y"]) - float(source_hip["y"]),
    }
    upper_arm_vector = {
        "x": float(source_elbow["x"]) - float(source_shoulder["x"]),
        "y": float(source_elbow["y"]) - float(source_shoulder["y"]),
    }

    legs = {}
    arms = {}
    for is_far in (True, False):
        side = "far" if is_far else "near"
        mirror_part = facing_left or (front_facing and is_far)
        tint = settings["far_limb_tint"] if is_far else None
        # Front-facing far pieces are mirrored by the part renderer. Build
        # their canonical pivots with inverse body sway so both sides follow
        # the same screen-space weight transfer after mirroring.
        canonical_body_hip = dict(body_hip)
        if front_facing and is_far:
            canonical_body_hip["x"] = float(bind_hip["x"]) - body_x

        if front_facing:
            hip_attachment = source_hip
            shoulder_attachment = source_shoulder
        else:
            hip_attachment = rig[f"{side}_hip"]
            shoulder_attachment = rig[f"{side}_shoulder"]
        hip_offset = _rotate_rig_vector(
            float(hip_attachment["x"]) - float(bind_hip["x"]),
            float(hip_attachment["y"]) - float(bind_hip["y"]),
            torso_angle,
        )
        shoulder_offset = _rotate_rig_vector(
            float(shoulder_attachment["x"]) - float(bind_hip["x"]),
            float(shoulder_attachment["y"]) - float(bind_hip["y"]),
            torso_angle,
        )
        target_hip = {
            "x": canonical_body_hip["x"] + hip_offset["x"],
            "y": canonical_body_hip["y"] + hip_offset["y"],
        }
        target_shoulder = {
            "x": canonical_body_hip["x"] + shoulder_offset["x"],
            "y": canonical_body_hip["y"] + shoulder_offset["y"],
        }

        upper_leg_angle = float(
            pose.get(f"{side}_upper_leg_degrees", 0.0)
        ) * blend
        lower_leg_angle = upper_leg_angle + float(
            pose.get(f"{side}_knee_bend_degrees", 0.0)
        ) * blend
        if front_facing:
            # Screen-space rotations turn a depth stride into sideways scissoring.
            # Translate the intact leg under the torso, preserving its fixed lane.
            upper_leg_angle = lower_leg_angle = 0.0
            target_hip = {
                "x": float(source_hip["x"]),
                "y": float(source_hip["y"]) + float(
                    pose.get(f"{side}_front_leg_y_pixels", 0.0)
                ) * blend,
            }
        knee_offset = _rotate_rig_vector(
            upper_leg_vector["x"], upper_leg_vector["y"],
            upper_leg_angle,
        )
        target_knee = {
            "x": target_hip["x"] + knee_offset["x"],
            "y": target_hip["y"] + knee_offset["y"],
        }
        upper_leg = _make_redhead_cutout_part(
            textures["upper_leg"], source_hip, target_hip,
            upper_leg_angle, mirror_part, tint, canvas_size=settings["canvas_size"],
        )
        lower_leg = _make_redhead_cutout_part(
            textures["lower_leg"], source_knee, target_knee,
            lower_leg_angle, mirror_part, tint, canvas_size=settings["canvas_size"],
        )
        upper_leg.update({"rig_side": side, "rig_joint": "upper_leg"})
        lower_leg.update({"rig_side": side, "rig_joint": "lower_leg"})
        legs[side] = [lower_leg, upper_leg]

        upper_arm_angle = torso_angle + float(
            pose.get(f"{side}_upper_arm_degrees", 0.0)
        ) * blend
        if front_facing:
            upper_arm_angle = torso_angle + (upper_arm_angle - torso_angle) * float(
                pose.get("front_arm_angle_scale", 1.0)
            )
        elbow_scale = float(pose.get("front_elbow_angle_scale", 1.0)) if front_facing else 1.0
        lower_arm_angle = upper_arm_angle + float(
            pose.get(f"{side}_elbow_bend_degrees", 0.0)
        ) * blend * elbow_scale
        elbow_offset = _rotate_rig_vector(
            upper_arm_vector["x"], upper_arm_vector["y"],
            upper_arm_angle,
        )
        target_elbow = {
            "x": target_shoulder["x"] + elbow_offset["x"],
            "y": target_shoulder["y"] + elbow_offset["y"],
        }
        upper_arm = _make_redhead_cutout_part(
            textures["upper_arm"], source_shoulder, target_shoulder,
            upper_arm_angle, mirror_part, tint, canvas_size=settings["canvas_size"],
        )
        lower_arm = _make_redhead_cutout_part(
            textures["lower_arm"], source_elbow, target_elbow,
            lower_arm_angle, mirror_part, tint, canvas_size=settings["canvas_size"],
        )
        upper_arm.update({"rig_side": side, "rig_joint": "upper_arm"})
        lower_arm.update({"rig_side": side, "rig_joint": "lower_arm"})
        arms[side] = [lower_arm, upper_arm]

    if direction == "up":
        parts = [
            *arms["far"], *legs["far"], *legs["near"],
            *arms["near"], torso, head,
        ]
    else:
        parts = [
            *arms["far"], *legs["far"], torso,
            *legs["near"], *arms["near"], head,
        ]
    return highlight_component_parts(parts, entity.get("animation_component_highlight", {}))
