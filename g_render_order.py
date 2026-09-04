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
    "far_hip": {"x": 16.0, "y": 22.0},
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
         "far_upper_leg_degrees": -24.0, "far_knee_bend_degrees": -10.0,
         "near_upper_arm_degrees": -15.0, "near_elbow_bend_degrees": 18.0,
         "far_upper_arm_degrees": 1.0, "far_elbow_bend_degrees": -20.0,
         "body_y_pixels": 0.0, "torso_degrees": 0.5},
        {"near_upper_leg_degrees": 0.0, "near_knee_bend_degrees": 22.0,
         "far_upper_leg_degrees": -8.0, "far_knee_bend_degrees": 30.0,
         "near_upper_arm_degrees": -4.0, "near_elbow_bend_degrees": 24.0,
         "far_upper_arm_degrees": -5.0, "far_elbow_bend_degrees": 32.0,
         "body_y_pixels": -0.75, "torso_degrees": -1.0},
        {"near_upper_leg_degrees": -24.0, "near_knee_bend_degrees": -6.0,
         "far_upper_leg_degrees": 20.0, "far_knee_bend_degrees": 4.0,
         "near_upper_arm_degrees": 40.0, "near_elbow_bend_degrees": 28.0,
         "far_upper_arm_degrees": -18.0, "far_elbow_bend_degrees": 20.0,
         "body_y_pixels": 0.0, "torso_degrees": 0.5},
        {"near_upper_leg_degrees": 0.0, "near_knee_bend_degrees": -10.0,
         "far_upper_leg_degrees": 7.0, "far_knee_bend_degrees": 24.0,
         "near_upper_arm_degrees": 4.0, "near_elbow_bend_degrees": 28.0,
         "far_upper_arm_degrees": -6.0, "far_elbow_bend_degrees": 28.0,
         "body_y_pixels": -0.75, "torso_degrees": 1.5},
    ],
    "run": [
        # Contact, recoil/passing, opposite contact, flight/recovery.
        {"near_upper_leg_degrees": 65.0, "near_knee_bend_degrees": 60.0,
         "far_upper_leg_degrees": -56.0, "far_knee_bend_degrees": 24.0,
         "near_upper_arm_degrees": -38.0, "near_elbow_bend_degrees": 90.0,
         "far_upper_arm_degrees": 42.0, "far_elbow_bend_degrees": 0.0,
         "body_y_pixels": 0.0, "torso_degrees": 10.0},
        {"near_upper_leg_degrees": -4.0, "near_knee_bend_degrees": 58.0,
         "far_upper_leg_degrees": 12.0, "far_knee_bend_degrees": 52.0,
         "near_upper_arm_degrees": -16.0, "near_elbow_bend_degrees": 60.0,
         "far_upper_arm_degrees": 24.0, "far_elbow_bend_degrees": 48.0,
         "body_y_pixels": -1.75, "torso_degrees": 10.5},
        {"near_upper_leg_degrees": -52.0, "near_knee_bend_degrees": 18.0,
         "far_upper_leg_degrees": 52.0, "far_knee_bend_degrees": 70.0,
         "near_upper_arm_degrees": 60.0, "near_elbow_bend_degrees": 10.0,
         "far_upper_arm_degrees": -30.0, "far_elbow_bend_degrees": 72.0,
         "body_y_pixels": 0.0, "torso_degrees": 10.0},
        {"near_upper_leg_degrees": 6.0, "near_knee_bend_degrees": 64.0,
         "far_upper_leg_degrees": -10.0, "far_knee_bend_degrees": 54.0,
         "near_upper_arm_degrees": 8.0, "near_elbow_bend_degrees": 64.0,
         "far_upper_arm_degrees": -14.0, "far_elbow_bend_degrees": 56.0,
         "body_y_pixels": -1.75, "torso_degrees": 10.0},
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

PLAYER_CUTOUT_DIRECTION_TEXTURES = {
    "right": PLAYER_CUTOUT_TEXTURES,
    # Left continues to mirror the right-facing art.
    "left": PLAYER_CUTOUT_TEXTURES,
    "up": {
        "head": "player_cutout_head_up",
        "torso": "player_cutout_torso_up",
        "upper_leg": "player_cutout_upper_leg_up",
        "lower_leg": "player_cutout_lower_leg_up",
        "upper_arm": "player_cutout_upper_arm_up",
        "lower_arm": "player_cutout_lower_arm_up",
        "gun": "player_cutout_gun_right",
    },
    "down": {
        "head": "player_cutout_head_down",
        "torso": "player_cutout_torso_down",
        "upper_leg": "player_cutout_upper_leg_down",
        "lower_leg": "player_cutout_lower_leg_down",
        "upper_arm": "player_cutout_upper_arm_down",
        "lower_arm": "player_cutout_lower_arm_down",
        "gun": "player_cutout_gun_right",
    },
}

# The red head uses the same aligned-canvas cutout convention as the player,
# but keeps its smaller 24x24 authored silhouette.  Left mirrors the right
# artwork; front and back have their own head/torso readability.
REDHEAD_CUTOUT_TEXTURES = {
    direction: {
        part: f"redhead_cutout_{part}_{direction}"
        for part in (
            "head", "torso", "upper_leg", "lower_leg",
            "upper_arm", "lower_arm",
        )
    }
    for direction in ("right", "up", "down")
}

REDHEAD_CUTOUT_RIG_DEFAULTS = {
    "enabled": True,
    "canvas_size": 24.0,
    "footfall_phase_degrees": 0.0,
    "movement_blend_response": 16.0,
    "profile_blend_response": 8.0,
    "run_blend_start_speed_fraction": 0.52,
    "run_blend_full_speed_fraction": 0.90,
    "far_limb_tint": [182, 188, 184, 255],
    "side": {
        "hip": {"x": 11.5, "y": 16.5},
        "near_hip": {"x": 11.5, "y": 16.5},
        "far_hip": {"x": 12.25, "y": 16.5},
        "knee": {"x": 11.5, "y": 18.5},
        "foot": {"x": 11.5, "y": 21.0},
        "neck": {"x": 11.5, "y": 13.0},
        "shoulder": {"x": 12.5, "y": 13.5},
        "near_shoulder": {"x": 12.5, "y": 13.5},
        "far_shoulder": {"x": 11.75, "y": 13.5},
        "elbow": {"x": 12.5, "y": 15.5},
        "hand": {"x": 12.5, "y": 17.5},
    },
    "front": {
        "hip": {"x": 12.0, "y": 16.5},
        "limb_hip": {"x": 13.5, "y": 16.5},
        "knee": {"x": 13.5, "y": 18.5},
        "foot": {"x": 13.5, "y": 21.0},
        "neck": {"x": 11.5, "y": 13.0},
        "shoulder": {"x": 13.5, "y": 13.5},
        # The diagonal arm pieces meet at the first pixel of the lower arm.
        "elbow": {"x": 15.5, "y": 14.5},
        "hand": {"x": 17.5, "y": 16.5},
    },
}

# A four-pose two-step cycle. Walking deliberately transfers the body over
# each planted foot for a playful penguin-like sway. Running retains that
# imbalance while adding a pronounced forward pitch and uneven flight poses.
REDHEAD_CUTOUT_GAIT_PROFILES = {
    "walk": [
        {"near_upper_leg_degrees": 12.0, "near_knee_bend_degrees": -5.0,
         "far_upper_leg_degrees": -13.0, "far_knee_bend_degrees": 12.0,
         "near_upper_arm_degrees": -12.0, "near_elbow_bend_degrees": 4.0,
         "far_upper_arm_degrees": 12.0, "far_elbow_bend_degrees": -4.0,
         "body_x_pixels": 0.75, "body_y_pixels": 0.0,
         "side_torso_degrees": 4.0, "front_torso_degrees": 5.0},
        {"near_upper_leg_degrees": -3.0, "near_knee_bend_degrees": 18.0,
         "far_upper_leg_degrees": 4.0, "far_knee_bend_degrees": 5.0,
         "near_upper_arm_degrees": 3.0, "near_elbow_bend_degrees": 5.0,
         "far_upper_arm_degrees": -4.0, "far_elbow_bend_degrees": 5.0,
         "body_x_pixels": 0.10, "body_y_pixels": -0.35,
         "side_torso_degrees": -1.0, "front_torso_degrees": 0.5},
        {"near_upper_leg_degrees": -13.0, "near_knee_bend_degrees": 12.0,
         "far_upper_leg_degrees": 12.0, "far_knee_bend_degrees": -5.0,
         "near_upper_arm_degrees": 12.0, "near_elbow_bend_degrees": -4.0,
         "far_upper_arm_degrees": -12.0, "far_elbow_bend_degrees": 4.0,
         "body_x_pixels": -0.75, "body_y_pixels": 0.0,
         "side_torso_degrees": -4.0, "front_torso_degrees": -5.0},
        {"near_upper_leg_degrees": 4.0, "near_knee_bend_degrees": 5.0,
         "far_upper_leg_degrees": -3.0, "far_knee_bend_degrees": 18.0,
         "near_upper_arm_degrees": -4.0, "near_elbow_bend_degrees": 5.0,
         "far_upper_arm_degrees": 3.0, "far_elbow_bend_degrees": 5.0,
         "body_x_pixels": -0.10, "body_y_pixels": -0.35,
         "side_torso_degrees": 1.0, "front_torso_degrees": -0.5},
    ],
    "run": [
        {"near_upper_leg_degrees": 42.0, "near_knee_bend_degrees": 24.0,
         "far_upper_leg_degrees": -34.0, "far_knee_bend_degrees": 35.0,
         "near_upper_arm_degrees": -38.0, "near_elbow_bend_degrees": 18.0,
         "far_upper_arm_degrees": 34.0, "far_elbow_bend_degrees": 8.0,
         "body_x_pixels": 0.45, "body_y_pixels": 0.0,
         "side_torso_degrees": 14.0, "front_torso_degrees": 4.0},
        {"near_upper_leg_degrees": -8.0, "near_knee_bend_degrees": 48.0,
         "far_upper_leg_degrees": 14.0, "far_knee_bend_degrees": 34.0,
         "near_upper_arm_degrees": -12.0, "near_elbow_bend_degrees": 20.0,
         "far_upper_arm_degrees": 18.0, "far_elbow_bend_degrees": 15.0,
         "body_x_pixels": -0.20, "body_y_pixels": -1.20,
         "side_torso_degrees": 20.0, "front_torso_degrees": -3.0},
        {"near_upper_leg_degrees": -34.0, "near_knee_bend_degrees": 35.0,
         "far_upper_leg_degrees": 42.0, "far_knee_bend_degrees": 24.0,
         "near_upper_arm_degrees": 34.0, "near_elbow_bend_degrees": 8.0,
         "far_upper_arm_degrees": -38.0, "far_elbow_bend_degrees": 18.0,
         "body_x_pixels": -0.45, "body_y_pixels": 0.0,
         "side_torso_degrees": 13.0, "front_torso_degrees": -4.0},
        {"near_upper_leg_degrees": 14.0, "near_knee_bend_degrees": 34.0,
         "far_upper_leg_degrees": -8.0, "far_knee_bend_degrees": 48.0,
         "near_upper_arm_degrees": 18.0, "near_elbow_bend_degrees": 15.0,
         "far_upper_arm_degrees": -12.0, "far_elbow_bend_degrees": 20.0,
         "body_x_pixels": 0.25, "body_y_pixels": -0.85,
         "side_torso_degrees": 22.0, "front_torso_degrees": 3.0},
    ],
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
    # Authored points in player_gun_right.png. The barrel occupies the upper
    # row; it does not pass through the lower grip pivot.
    "gun_muzzle": {"x": 4.0, "y": 0.5},
    "gun_barrel_direction": {"x": 1.0, "y": 0.0},
    # The hand meets the top of the grip; the gun pivot sits one pixel below
    # the aim line, matching player_aim_reference_right.png.
    "gun_grip_perpendicular_offset": 1.0,
    "ik_bend_side": 1.0,
    "far_arm_aim_motion_scale": 0.25,
}

# Spare-arm held-light prototype. The optional texture is expected to be a
# small right-facing prop with its grip at (0, 1); until it exists the same
# transform draws a compact rectangle, so animation tuning can proceed now.
PLAYER_FLASHLIGHT_POSE_DEFAULTS = {
    "texture": "player_cutout_flashlight_right",
    "grip": {"x": 0.0, "y": 1.0},
    "source_width": 5.0,
    "placeholder_size": {"x": 5.0, "y": 2.0},
    "placeholder_color": [205, 210, 196, 255],
    "aim_reach": 6.0,
    # Keep the spare hand on the opposite side of the aim line from the gun.
    "grip_perpendicular_offset": -0.75,
    "tip_distance": 5.0,
}

# Up/down artwork is authored as the screen-right limb on the same aligned
# 32x32 canvas. The opposite limb is a mirrored instance with its own gait
# pose, so it remains independently animated without requiring duplicate art.
# These settings are deliberately separate from the side-view rig: the front
# and back views need much smaller screen-plane swings and their own joints.
PLAYER_FRONT_CUTOUT_RIG_DEFAULTS = {
    "body_hip": {"x": 16.0, "y": 20.0},
    "neck": {"x": 16.0, "y": 10.0},
    "leg_bind_pose": {
        "hip": {"x": 17.5, "y": 20.0},
        "knee": {"x": 17.5, "y": 25.0},
        "foot": {"x": 17.5, "y": 31.0},
    },
    "near_hip": {"x": 17.5, "y": 20.0},
    "far_hip": {"x": 16.5, "y": 20.0},
    # The down idle art retains its angled feet, while locomotion borrows the
    # straight-footed up leg pieces. Torso, head and arms remain down-facing.
    "down_locomotion_uses_up_leg_art": True,
    "locomotion_leg_art_blend_threshold": 0.02,
    "leg_lateral_scale": 1.0,
    "leg_lift_scale": 1.0,
    "arm_angle_scale": 0.42,
    "elbow_angle_scale": 0.34,
    "torso_angle_scale": 0.12,
}

# Front/back legs are posed as joint targets rather than side-view angles.
# X values provide only a little separation; negative Y values shorten/lift a
# limb into the screen. Contact poses remain at 0 and 2, matching footsteps.
PLAYER_FRONT_CUTOUT_LEG_PROFILES = {
    "up": {
        "walk": [
            # Near contact; far leg lifted.
            {"near_knee_x_pixels": 0.35, "near_knee_y_pixels": 0.0,
             "near_foot_x_pixels": 0.0, "near_foot_y_pixels": 0.0,
             "far_knee_x_pixels": 0, "far_knee_y_pixels": -0.5,
             "far_foot_x_pixels": 0.0, "far_foot_y_pixels": -2.0,
             "body_y_pixels": 0.0, "torso_degrees": 0.5},
            # Passing: near lifts while far extends toward contact.
            {"near_knee_x_pixels": -0.1, "near_knee_y_pixels": -0.8,
             "near_foot_x_pixels": 0.25, "near_foot_y_pixels": -1.6,
             "far_knee_x_pixels": 0.2, "far_knee_y_pixels": -0.2,
             "far_foot_x_pixels": 0.4, "far_foot_y_pixels": -0.4,
             "body_y_pixels": -0.6, "torso_degrees": -0.5},
            # Far contact; near leg lifted.
            {"near_knee_x_pixels": -0.15, "near_knee_y_pixels": -0.5,
             "near_foot_x_pixels": -0.00, "near_foot_y_pixels": -2.0,
             "far_knee_x_pixels": 0.35, "far_knee_y_pixels": 0.0,
             "far_foot_x_pixels": 0.0, "far_foot_y_pixels": 0.0,
             "body_y_pixels": 0.0, "torso_degrees": 0.5},
            # Passing: far lifts while near extends toward contact.
            {"near_knee_x_pixels": 0.2, "near_knee_y_pixels": -0.2,
             "near_foot_x_pixels": 0.4, "near_foot_y_pixels": -0.4,
             "far_knee_x_pixels": -0.1, "far_knee_y_pixels": -0.8,
             "far_foot_x_pixels": 0.25, "far_foot_y_pixels": -1.6,
             "body_y_pixels": -0.6, "torso_degrees": 0.5},
        ],
        "run": [
            # Near contact; far knee tucked high.
            {"near_knee_x_pixels": 0.45, "near_knee_y_pixels": 0.0,
             "near_foot_x_pixels": -1.8, "near_foot_y_pixels": 0.0,
             "far_knee_x_pixels": -0.2, "far_knee_y_pixels": -1.4,
             "far_foot_x_pixels": -0.35, "far_foot_y_pixels": -3.6,
             "body_y_pixels": 0.0, "torso_degrees": 1.0},
            # Flight: both legs are compressed beneath the body.
            {"near_knee_x_pixels": -0.1, "near_knee_y_pixels": -1.0,
             "near_foot_x_pixels": -0.2, "near_foot_y_pixels": -2.8,
             "far_knee_x_pixels": 0.1, "far_knee_y_pixels": -0.8,
             "far_foot_x_pixels": 0.2, "far_foot_y_pixels": -2.2,
             "body_y_pixels": -1.5, "torso_degrees": 1.5},
            # Far contact; near knee tucked high.
            {"near_knee_x_pixels": -0.2, "near_knee_y_pixels": -1.4,
             "near_foot_x_pixels": -0.35, "near_foot_y_pixels": -3.6,
             "far_knee_x_pixels": 0.45, "far_knee_y_pixels": 0.0,
             "far_foot_x_pixels": -1.8, "far_foot_y_pixels": 0.0,
             "body_y_pixels": 0.0, "torso_degrees": 1.0},
            # Flight: opposite compression before the next contact.
            {"near_knee_x_pixels": 0.1, "near_knee_y_pixels": -0.8,
             "near_foot_x_pixels": 0.2, "near_foot_y_pixels": -2.2,
             "far_knee_x_pixels": -0.1, "far_knee_y_pixels": -1.0,
             "far_foot_x_pixels": -0.2, "far_foot_y_pixels": -2.8,
             "body_y_pixels": -1.5, "torso_degrees": 1.5},
        ],
    },
    "down": {
        "walk": [
            # Near contact; far leg lifted.
            {"near_knee_x_pixels": 0.35, "near_knee_y_pixels": 0.0,
             "near_foot_x_pixels": 0.0, "near_foot_y_pixels": 0.0,
             "far_knee_x_pixels": -0.15, "far_knee_y_pixels": -0.5,
             "far_foot_x_pixels": -1.25, "far_foot_y_pixels": -2.0,
             "body_y_pixels": 0.0, "torso_degrees": 0.5},
            # Passing: near lifts while far extends toward contact.
            {"near_knee_x_pixels": -0.1, "near_knee_y_pixels": -0.8,
             "near_foot_x_pixels": -0.25, "near_foot_y_pixels": -1.6,
             "far_knee_x_pixels": 0.2, "far_knee_y_pixels": -0.2,
             "far_foot_x_pixels": 0.4, "far_foot_y_pixels": -0.4,
             "body_y_pixels": -0.6, "torso_degrees": -0.5},
            # Far contact; near leg lifted.
            {"near_knee_x_pixels": -0.15, "near_knee_y_pixels": -0.5,
             "near_foot_x_pixels": -1.25, "near_foot_y_pixels": -2.0,
             "far_knee_x_pixels": 0.35, "far_knee_y_pixels": 0.0,
             "far_foot_x_pixels": 0.0, "far_foot_y_pixels": 0.0,
             "body_y_pixels": 0.0, "torso_degrees": 0.5},
            # Passing: far lifts while near extends toward contact.
            {"near_knee_x_pixels": 0.2, "near_knee_y_pixels": -0.2,
             "near_foot_x_pixels": 0.4, "near_foot_y_pixels": -0.4,
             "far_knee_x_pixels": -0.1, "far_knee_y_pixels": -0.8,
             "far_foot_x_pixels": -0.25, "far_foot_y_pixels": -1.6,
             "body_y_pixels": -0.6, "torso_degrees": 0.5},
        ],
        "run": [
            # Near contact; far knee tucked high.
            {"near_knee_x_pixels": 0.45, "near_knee_y_pixels": 0.0,
             "near_foot_x_pixels": -1.5, "near_foot_y_pixels": 0.0,
             "far_knee_x_pixels": -0.2, "far_knee_y_pixels": -1.4,
             "far_foot_x_pixels": -1.35, "far_foot_y_pixels": -3.6,
             "body_y_pixels": 0.0, "torso_degrees": 1.0},
            # Flight: both legs are compressed beneath the body.
            {"near_knee_x_pixels": -0.1, "near_knee_y_pixels": -1.0,
             "near_foot_x_pixels": -0.2, "near_foot_y_pixels": -2.8,
             "far_knee_x_pixels": 0.1, "far_knee_y_pixels": -0.8,
             "far_foot_x_pixels": 0.2, "far_foot_y_pixels": -2.2,
             "body_y_pixels": -1.5, "torso_degrees": 1.5},
            # Far contact; near knee tucked high.
            {"near_knee_x_pixels": -0.2, "near_knee_y_pixels": -1.4,
             "near_foot_x_pixels": -1.35, "near_foot_y_pixels": -3.6,
             "far_knee_x_pixels": 0.45, "far_knee_y_pixels": 0.0,
             "far_foot_x_pixels": -1.5, "far_foot_y_pixels": 0.0,
             "body_y_pixels": 0.0, "torso_degrees": 1.0},
            # Flight: opposite compression before the next contact.
            {"near_knee_x_pixels": 0.1, "near_knee_y_pixels": -0.8,
             "near_foot_x_pixels": 0.2, "near_foot_y_pixels": -2.2,
             "far_knee_x_pixels": -0.1, "far_knee_y_pixels": -1.0,
             "far_foot_x_pixels": -0.2, "far_foot_y_pixels": -2.8,
             "body_y_pixels": -1.5, "torso_degrees": 1.5},
        ],
    },
}

PLAYER_FRONT_CUTOUT_ARM_DEFAULTS = {
    "bind_pose": {
        "shoulder": {"x": 19.5, "y": 11.0},
        "elbow": {"x": 20.0, "y": 15.0},
        "hand": {"x": 20.0, "y": 19.0},
    },
    "shoulder": {"x": 19.5, "y": 11.0},
    "far_shoulder": {"x": 18.5, "y": 11.0},
    "aim_reach": 6.5,
    # Up aiming and the centre/right portion of down aiming use the arm's full
    # authored length. Down-left is a cross-body pose and can retain a bend.
    "straight_aim_reach_scale": 1.0,
    "down_cross_body_aim_reach": 6.5,
    "down_cross_body_reach_exponent": 1.0,
    "down_cross_body_ik_bend_side": -1.0,
    "gun_grip": {"x": 0.0, "y": 2.0},
    "gun_source_size": 4.0,
    "gun_grip_perpendicular_offset": 1.0,
    "ik_bend_side": 1.0,
    "far_arm_aim_motion_scale": 0.25,
}

# Reload poses share the ordinary arm and gun art. Progress is supplied by the
# gameplay reload state, while these hot-reloadable values control only the
# visual pose. Hand and gun positions for up/down are offsets from body_hip in
# the canonical (screen-right limb) 32x32 canvas.
PLAYER_RELOAD_POSE_DEFAULTS = {
    "enter_fraction": 0.16,
    "exit_fraction": 0.14,
    "side": {
        "aim_direction": {"x": 0.42, "y": 0.91},
        # The spare hand meets the lowered pistol around its grip once the
        # flashlight has returned to its locomotion/holstered endpoint.
        "support_hand_from_gun": {"x": 0.0, "y": 0.0},
        "support_bend_side": 1.0,
    },
    "down": {
        "near_hand_from_body_hip": {"x": 1.0, "y": -3.5},
        "far_hand_from_body_hip": {"x": 1.0, "y": -3.5},
        "gun_from_body_hip": {"x": 0.0, "y": -3.5},
        "gun_degrees": 90.0,
        "near_bend_side": 1.0,
        "far_bend_side": 1.0,
    },
    "up": {
        "near_hand_from_body_hip": {"x": 0.8, "y": -2.5},
        "far_hand_from_body_hip": {"x": 0.8, "y": -2.5},
        "gun_from_body_hip": {"x": 0.0, "y": -1.8},
        "gun_degrees": 90.0,
        "near_bend_side": 1.0,
        "far_bend_side": 1.0,
    },
}

# Front/back arm animation is authored independently for each facing. Walking
# uses angular shoulder/elbow poses; running uses screen-space compression and
# extension so the arms pump in depth rather than swinging sideways.
PLAYER_FRONT_CUTOUT_ARM_PROFILES = {
    "up": {
        "walk": [
            {"near_upper_arm_degrees": -15.0,
             "near_elbow_bend_degrees": 18.0,
             "far_upper_arm_degrees": 15.0,
             "far_elbow_bend_degrees": -45.0},
            {"near_upper_arm_degrees": -4.0,
             "near_elbow_bend_degrees": 12.0,
             "far_upper_arm_degrees": -5.0,
             "far_elbow_bend_degrees": 12.0},
            {"near_upper_arm_degrees": 40.0,
             "near_elbow_bend_degrees": 28.0,
             "far_upper_arm_degrees": -18.0,
             "far_elbow_bend_degrees": 20.0},
            {"near_upper_arm_degrees": 4.0,
             "near_elbow_bend_degrees": 12.0,
             "far_upper_arm_degrees": -1.0,
             "far_elbow_bend_degrees": 12.0},
        ],
        "run": [
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -0.8,
             "near_hand_x_pixels": -2.0, "near_hand_y_pixels": -4.4,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": 0.15,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": 0.4},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -0.45,
             "near_hand_x_pixels": 0.0, "near_hand_y_pixels": -1.2,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.2,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": -0.6},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": 0.15,
             "near_hand_x_pixels": 0.0, "near_hand_y_pixels": 0.4,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.8,
             "far_hand_x_pixels": -2.0, "far_hand_y_pixels": -4.5},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -0.2,
             "near_hand_x_pixels": 0.0, "near_hand_y_pixels": -0.6,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.45,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": -1.2},
        ],
    },
    "down": {
        "walk": [
            {"near_upper_arm_degrees": -15.0,
             "near_elbow_bend_degrees": 18.0,
             "far_upper_arm_degrees": 10.0,
             "far_elbow_bend_degrees": -50.0},
            {"near_upper_arm_degrees": -4.0,
             "near_elbow_bend_degrees": 14.0,
             "far_upper_arm_degrees": -1.0,
             "far_elbow_bend_degrees": 12.0},
            {"near_upper_arm_degrees": 40.0,
             "near_elbow_bend_degrees": 28.0,
             "far_upper_arm_degrees": -18.0,
             "far_elbow_bend_degrees": 20.0},
            {"near_upper_arm_degrees": 4.0,
             "near_elbow_bend_degrees": 28.0,
             "far_upper_arm_degrees": -1.0,
             "far_elbow_bend_degrees": 12.0},
        ],
        "run": [
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -2.8,
             "near_hand_x_pixels": 1.0, "near_hand_y_pixels": -1.0,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": 0.15,
             "far_hand_x_pixels": -1.4, "far_hand_y_pixels": -2.4},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -0.45,
             "near_hand_x_pixels": 0.0, "near_hand_y_pixels": -1.2,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.2,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": -0.6},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": 0.15,
             "near_hand_x_pixels": -1.0, "near_hand_y_pixels": -1.0,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.8,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": -2.0},
            {"near_elbow_x_pixels": 0.0, "near_elbow_y_pixels": -0.2,
             "near_hand_x_pixels": 0.0, "near_hand_y_pixels": -0.6,
             "far_elbow_x_pixels": 0.0, "far_elbow_y_pixels": -0.45,
             "far_hand_x_pixels": 0.0, "far_hand_y_pixels": -1.2},
        ],
    },
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
                              source_canvas_width=None, scale_x=1.0,
                              scale_y=1.0, target_canvas_width=None):
    canvas_size = float(
        target_canvas_width or PLAYER_CUTOUT_RIG_DEFAULTS["canvas_size"]
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


def _blended_player_front_leg_pose(direction, phase, run_blend):
    direction_profiles = PLAYER_FRONT_CUTOUT_LEG_PROFILES[direction]
    walk = sample_player_cutout_gait_profile(
        direction_profiles["walk"], phase,
    )
    run = sample_player_cutout_gait_profile(
        direction_profiles["run"], phase,
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


def _lerp_rig_vector_by_angle(start, end, amount):
    """Interpolate a limb vector without collapsing through the shoulder."""
    start_length = math.hypot(float(start["x"]), float(start["y"]))
    end_length = math.hypot(float(end["x"]), float(end["y"]))
    if start_length <= 0.000001:
        start = end
        start_length = end_length
    if end_length <= 0.000001:
        end = start
        end_length = start_length
    start_angle = math.atan2(float(start["y"]), float(start["x"]))
    end_angle = math.atan2(float(end["y"]), float(end["x"]))
    delta = (end_angle - start_angle + math.pi) % math.tau - math.pi
    t = max(0.0, min(1.0, float(amount)))
    angle = start_angle + delta * t
    length = start_length + (end_length - start_length) * t
    return {"x": math.cos(angle) * length, "y": math.sin(angle) * length}


def _player_cutout_aim_reach(settings, animation_direction, canonical_aim,
                              maximum_reach):
    if animation_direction not in {"up", "down"}:
        return float(settings["aim_reach"])
    straight_reach = float(maximum_reach) * float(
        settings.get("straight_aim_reach_scale", 1.0)
    )
    if animation_direction == "up" or float(canonical_aim["x"]) >= 0.0:
        return straight_reach
    cross_body_amount = max(0.0, min(1.0, -float(canonical_aim["x"])))
    exponent = max(
        0.01, float(settings.get("down_cross_body_reach_exponent", 1.0))
    )
    cross_body_amount = cross_body_amount ** exponent
    cross_body_reach = float(
        settings.get("down_cross_body_aim_reach", settings["aim_reach"])
    )
    return straight_reach + (
        cross_body_reach - straight_reach
    ) * cross_body_amount


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


def _player_rig_side_for_hand(direction, hand):
    """Map anatomical hands onto the direction-dependent near/far rig slots."""
    right_hand_is_near = direction in {"right", "up"}
    if hand == "right":
        return "near" if right_hand_is_near else "far"
    if hand == "left":
        return "far" if right_hand_is_near else "near"
    raise ValueError(f"Unsupported player hand: {hand!r}")


def _player_reload_pose_timing(player_entity):
    if player_entity.get("reload_state", "") != "reloading":
        return {"progress": 0.0, "enter": 0.0, "leave": 0.0}
    try:
        progress = max(0.0, min(1.0, float(
            player_entity.get("reload_animation", {}).get("progress", 0.0)
        )))
    except (TypeError, ValueError, OverflowError):
        progress = 0.0
    if not math.isfinite(progress):
        progress = 0.0
    enter = max(0.0001, float(
        PLAYER_RELOAD_POSE_DEFAULTS["enter_fraction"]
    ))
    exit_fraction = max(0.0001, float(
        PLAYER_RELOAD_POSE_DEFAULTS["exit_fraction"]
    ))
    entering = max(0.0, min(1.0, progress / enter))
    leaving = max(0.0, min(1.0, (1.0 - progress) / exit_fraction))
    entering = entering * entering * (3.0 - 2.0 * entering)
    leaving = leaving * leaving * (3.0 - 2.0 * leaving)
    return {"progress": progress, "enter": entering, "leave": leaving}


def _player_reload_pose_amount(player_entity):
    timing = _player_reload_pose_timing(player_entity)
    return min(timing["enter"], timing["leave"])


def _player_reload_support_pose_amount(player_entity, timing=None):
    """Delay the support-hand entry until a deployed flashlight is stowed."""
    timing = timing or _player_reload_pose_timing(player_entity)
    # Exit remains shared by both hands so the complete reload pose resolves
    # together before any requested item is drawn again.
    if timing["progress"] >= 0.5:
        return timing["leave"]
    animation = player_entity.get("reload_animation", {})
    if not isinstance(animation, dict):
        animation = {}
    try:
        release = max(0.0, min(0.45, float(
            animation.get("flashlight_holster_reload_fraction", 0.0)
        )))
    except (TypeError, ValueError, OverflowError):
        release = 0.0
    enter_fraction = max(
        0.0001, float(PLAYER_RELOAD_POSE_DEFAULTS["enter_fraction"]),
    )
    amount = max(
        0.0, min(1.0, (timing["progress"] - release) / enter_fraction),
    )
    return amount * amount * (3.0 - 2.0 * amount)


def _player_reload_start_weapon_state(player_entity):
    animation = player_entity.get("reload_animation", {})
    if not isinstance(animation, dict):
        animation = {}
    try:
        progress = max(0.0, min(1.0, float(
            animation.get("start_weapon_progress", 0.0)
        )))
    except (TypeError, ValueError, OverflowError):
        progress = 0.0
    aim = normalize_vector(animation.get("start_aim_direction", {}))
    if aim is None:
        aim = normalize_vector(player_entity.get("aim_direction", {}))
    return progress, aim


def _lerp_player_cutout_part(start, end, amount):
    """Blend matching rig parts while taking the shortest rotation path."""
    t = max(0.0, min(1.0, float(amount)))
    result = copy.deepcopy(end)
    for key in ("x", "y"):
        result["pivot_local"][key] = (
            float(start["pivot_local"][key])
            + (float(end["pivot_local"][key])
               - float(start["pivot_local"][key])) * t
        )
        result["scale"][key] = (
            float(start["scale"][key])
            + (float(end["scale"][key]) - float(start["scale"][key])) * t
        )
    start_rotation = float(start["rotation"])
    rotation_delta = (
        (float(end["rotation"]) - start_rotation + 180.0) % 360.0
    ) - 180.0
    result["rotation"] = start_rotation + rotation_delta * t
    result["tint"] = [
        int(round(float(start["tint"][index]) + (
            float(end["tint"][index]) - float(start["tint"][index])
        ) * t))
        for index in range(4)
    ]
    return result


def _lerp_player_cutout_parts(start_parts, end_parts, amount):
    if len(start_parts) != len(end_parts):
        return end_parts
    return [
        _lerp_player_cutout_part(start, end, amount)
        for start, end in zip(start_parts, end_parts)
    ]


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
                                       facing_left, locomotion_pose=None,
                                       arm_settings=None, textures=None,
                                       animation_direction=None,
                                       rig_side="near", rig_hand="right"):
    progress = _player_weapon_transition_progress(player_entity)
    if progress <= 0.000001:
        return []

    settings = arm_settings or PLAYER_CUTOUT_ARM_DEFAULTS
    textures = textures or PLAYER_CUTOUT_TEXTURES
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
    upper_length = math.hypot(upper_bind["x"], upper_bind["y"])
    lower_length = math.hypot(lower_bind["x"], lower_bind["y"])
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
    aim_reach = _player_cutout_aim_reach(
        settings, animation_direction, canonical_aim,
        upper_length + lower_length,
    )
    aimed_hand = {
        "x": shoulder["x"] + canonical_aim["x"] * aim_reach,
        "y": shoulder["y"] + canonical_aim["y"] * aim_reach,
    }
    pose_amount = progress * progress * (3.0 - 2.0 * progress)
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
    if (animation_direction == "down"
            and float(canonical_aim["x"]) < 0.0):
        bend_side = float(settings.get(
            "down_cross_body_ik_bend_side", bend_side,
        ))

    if animation_direction in {"up", "down"}:
        aimed_elbow, aimed_hand = _solve_player_arm_ik(
            shoulder, aimed_hand, upper_length, lower_length, bend_side,
        )
        neutral_upper = {
            "x": neutral_elbow["x"] - shoulder["x"],
            "y": neutral_elbow["y"] - shoulder["y"],
        }
        neutral_lower = {
            "x": neutral_hand["x"] - neutral_elbow["x"],
            "y": neutral_hand["y"] - neutral_elbow["y"],
        }
        aimed_upper = {
            "x": aimed_elbow["x"] - shoulder["x"],
            "y": aimed_elbow["y"] - shoulder["y"],
        }
        aimed_lower = {
            "x": aimed_hand["x"] - aimed_elbow["x"],
            "y": aimed_hand["y"] - aimed_elbow["y"],
        }
        upper_vector = _lerp_rig_vector_by_angle(
            neutral_upper, aimed_upper, pose_amount,
        )
        lower_vector = _lerp_rig_vector_by_angle(
            neutral_lower, aimed_lower, pose_amount,
        )
        elbow = {
            "x": shoulder["x"] + upper_vector["x"],
            "y": shoulder["y"] + upper_vector["y"],
        }
        hand = {
            "x": elbow["x"] + lower_vector["x"],
            "y": elbow["y"] + lower_vector["y"],
        }
    else:
        requested_hand = {
            "x": neutral_hand["x"] + (
                aimed_hand["x"] - neutral_hand["x"]
            ) * pose_amount,
            "y": neutral_hand["y"] + (
                aimed_hand["y"] - neutral_hand["y"]
            ) * pose_amount,
        }
        elbow, hand = _solve_player_arm_ik(
            shoulder, requested_hand,
            upper_length, lower_length, bend_side,
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
    if animation_direction in {"up", "down"}:
        gun_direction = normalize_vector(_lerp_rig_vector_by_angle(
            neutral_direction, canonical_aim, pose_amount,
        )) or canonical_aim
    else:
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

    arm_tint = (
        PLAYER_CUTOUT_RIG_DEFAULTS["far_arm_tint"]
        if rig_side == "far" else None
    )
    upper_part = _make_player_cutout_part(
            textures["upper_arm"], source_shoulder, shoulder,
            upper_angle, facing_left, arm_tint,
        )
    lower_part = _make_player_cutout_part(
            textures["lower_arm"], source_elbow, elbow,
            lower_angle, facing_left, arm_tint,
        )
    gun_part = _make_player_cutout_part(
            textures["gun"], settings["gun_grip"], gun_grip,
            gun_angle, facing_left, source_canvas_width=settings["gun_source_size"],
        )
    upper_part.update({
        "rig_side": rig_side, "rig_hand": rig_hand,
        "rig_joint": "upper_arm",
    })
    lower_part.update({
        "rig_side": rig_side, "rig_hand": rig_hand,
        "rig_joint": "lower_arm",
    })
    gun_part.update({
        "rig_side": rig_side, "rig_hand": rig_hand, "rig_joint": "gun",
    })
    return [upper_part, lower_part, gun_part]


def _player_flashlight_transition_progress(player_entity):
    transition = player_entity.get("flashlight_transition", {})
    try:
        progress = float(transition.get(
            "progress", 1.0 if player_entity.get("flashlight_enabled", False)
            else 0.0,
        ))
    except (AttributeError, TypeError, ValueError, OverflowError):
        progress = 0.0
    return max(0.0, min(1.0, progress))


def _build_player_flashlight_cutout_parts(
        player_entity, body_hip, torso_angle, mirror_parts,
        locomotion_pose, arm_settings=None, textures=None,
        animation_direction=None, rig_side="far", rig_hand="left"):
    """Pose the spare arm with the weapon IK, substituting a held light."""
    progress = _player_flashlight_transition_progress(player_entity)
    if progress <= 0.000001:
        return []
    pose = PLAYER_FLASHLIGHT_POSE_DEFAULTS
    flashlight_player = dict(player_entity)
    flashlight_player["weapon_transition"] = {
        "progress": progress, "target": 1.0, "phase": "unholstering",
    }
    flashlight_player["weapon_visual_recoil"] = {"rotation_degrees": 0.0}
    flashlight_settings = dict(arm_settings or PLAYER_CUTOUT_ARM_DEFAULTS)
    flashlight_settings.update({
        "aim_reach": float(pose["aim_reach"]),
        "gun_grip": dict(pose["grip"]),
        "gun_source_size": float(pose["source_width"]),
        "gun_grip_perpendicular_offset": float(
            pose["grip_perpendicular_offset"]
        ),
    })
    flashlight_textures = dict(textures or PLAYER_CUTOUT_TEXTURES)
    flashlight_textures["gun"] = pose["texture"]
    parts = _build_player_weapon_cutout_parts(
        flashlight_player, body_hip, torso_angle, mirror_parts,
        locomotion_pose, arm_settings=flashlight_settings,
        textures=flashlight_textures,
        animation_direction=animation_direction,
        rig_side=rig_side, rig_hand=rig_hand,
    )
    if len(parts) != 3:
        return []
    item = parts[2]
    item.update({
        "rig_side": rig_side,
        "rig_hand": rig_hand,
        "rig_joint": "flashlight",
        "placeholder_rect": True,
        "placeholder_size": dict(pose["placeholder_size"]),
        "placeholder_color": list(pose["placeholder_color"]),
        "held_item_tip_distance": float(pose["tip_distance"]),
    })
    return parts


def _build_player_side_reload_parts(player_entity, body_hip, torso_angle,
                                    facing_left, locomotion_pose,
                                    rig_side="near", rig_hand="right"):
    timing = _player_reload_pose_timing(player_entity)
    start_progress, start_aim = _player_reload_start_weapon_state(player_entity)
    direction = PLAYER_RELOAD_POSE_DEFAULTS["side"]["aim_direction"]
    reload_player = dict(player_entity)
    reload_player["aim_direction"] = {
        "x": -float(direction["x"]) if facing_left else float(direction["x"]),
        "y": float(direction["y"]),
    }
    # Once the entry has landed, the ordinary exit envelope returns the arm to
    # neutral before the held-aim unholster begins.
    target_progress = (
        timing["enter"] if start_progress <= 0.000001
        else 1.0
    )
    if timing["enter"] >= 0.999999:
        target_progress = timing["leave"]
    reload_player["weapon_transition"] = {
        "progress": target_progress,
        "target": 1.0,
        "phase": "reload",
    }
    reload_player["weapon_visual_recoil"] = {"rotation_degrees": 0.0}
    parts = _build_player_weapon_cutout_parts(
        reload_player, body_hip, torso_angle, facing_left, locomotion_pose,
        rig_side=rig_side, rig_hand=rig_hand,
    )

    # An aimed reload must depart from the exact visible aim pose, rather than
    # briefly snapping through the hanging locomotion arm.
    if (start_progress > 0.000001 and timing["enter"] < 0.999999
            and start_aim is not None):
        start_player = dict(player_entity)
        start_player["aim_direction"] = start_aim
        start_player["weapon_transition"] = {
            "progress": start_progress,
            "target": 1.0,
            "phase": "reload_start",
        }
        start_player["weapon_visual_recoil"] = {"rotation_degrees": 0.0}
        start_parts = _build_player_weapon_cutout_parts(
            start_player, body_hip, torso_angle, facing_left, locomotion_pose,
            rig_side=rig_side, rig_hand=rig_hand,
        )
        parts = _lerp_player_cutout_parts(
            start_parts, parts, timing["enter"],
        )
    for part in parts:
        part["rig_pose"] = "reload"
    return parts


def _build_player_side_reload_support_parts(
        player_entity, facing_left, locomotion_pose, gun_part,
        rig_side="far", rig_hand="left"):
    """Move the spare side-view hand onto the lowered reload weapon."""
    timing = _player_reload_pose_timing(player_entity)
    pose_amount = _player_reload_support_pose_amount(player_entity, timing)
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
    upper_length = math.hypot(upper_bind["x"], upper_bind["y"])
    lower_length = math.hypot(lower_bind["x"], lower_bind["y"])
    offset = PLAYER_RELOAD_POSE_DEFAULTS["side"]["support_hand_from_gun"]
    target_hand = {
        "x": float(gun_part["pivot_local"]["x"])
             + (-float(offset["x"]) if facing_left else float(offset["x"])),
        "y": float(gun_part["pivot_local"]["y"]) + float(offset["y"]),
    }
    requested_hand = {
        "x": float(locomotion_pose["hand"]["x"]) + (
            target_hand["x"] - float(locomotion_pose["hand"]["x"])
        ) * pose_amount,
        "y": float(locomotion_pose["hand"]["y"]) + (
            target_hand["y"] - float(locomotion_pose["hand"]["y"])
        ) * pose_amount,
    }
    shoulder = locomotion_pose["shoulder"]
    elbow, hand = _solve_player_arm_ik(
        shoulder, requested_hand, upper_length, lower_length,
        PLAYER_RELOAD_POSE_DEFAULTS["side"]["support_bend_side"],
    )
    upper_angle = _rig_vector_angle_degrees(
        upper_bind,
        {"x": elbow["x"] - shoulder["x"],
         "y": elbow["y"] - shoulder["y"]},
    )
    lower_angle = _rig_vector_angle_degrees(
        lower_bind,
        {"x": hand["x"] - elbow["x"], "y": hand["y"] - elbow["y"]},
    )
    tint = (
        PLAYER_CUTOUT_RIG_DEFAULTS["far_arm_tint"]
        if rig_side == "far" else None
    )
    upper_part = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["upper_arm"], source_shoulder, shoulder,
        upper_angle, facing_left, tint,
    )
    lower_part = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["lower_arm"], source_elbow, elbow,
        lower_angle, facing_left, tint,
    )
    upper_part.update({
        "rig_side": rig_side, "rig_hand": rig_hand,
        "rig_joint": "upper_arm", "rig_pose": "reload",
    })
    lower_part.update({
        "rig_side": rig_side, "rig_hand": rig_hand,
        "rig_joint": "lower_arm", "rig_pose": "reload",
    })
    return [upper_part, lower_part]


def _build_player_front_reload_arm_parts(
        locomotion_pose, body_hip, torso_angle, direction, textures,
        is_far, pose_amount, rig_hand):
    arm_settings = PLAYER_FRONT_CUTOUT_ARM_DEFAULTS
    bind_pose = arm_settings["bind_pose"]
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
    upper_length = math.hypot(upper_bind["x"], upper_bind["y"])
    lower_length = math.hypot(lower_bind["x"], lower_bind["y"])
    side = "far" if is_far else "near"
    pose_settings = PLAYER_RELOAD_POSE_DEFAULTS[direction]
    hand_offset = pose_settings[f"{side}_hand_from_body_hip"]
    rotated_offset = _rotate_rig_vector(
        hand_offset["x"], hand_offset["y"], torso_angle,
    )
    target_hand = {
        "x": float(body_hip["x"]) + rotated_offset["x"],
        "y": float(body_hip["y"]) + rotated_offset["y"],
    }
    shoulder = locomotion_pose["shoulder"]
    target_elbow, target_hand = _solve_player_arm_ik(
        shoulder, target_hand, upper_length, lower_length,
        pose_settings[f"{side}_bend_side"],
    )
    neutral_upper = {
        "x": float(locomotion_pose["elbow"]["x"]) - shoulder["x"],
        "y": float(locomotion_pose["elbow"]["y"]) - shoulder["y"],
    }
    neutral_lower = {
        "x": float(locomotion_pose["hand"]["x"])
             - float(locomotion_pose["elbow"]["x"]),
        "y": float(locomotion_pose["hand"]["y"])
             - float(locomotion_pose["elbow"]["y"]),
    }
    target_upper = {
        "x": target_elbow["x"] - shoulder["x"],
        "y": target_elbow["y"] - shoulder["y"],
    }
    target_lower = {
        "x": target_hand["x"] - target_elbow["x"],
        "y": target_hand["y"] - target_elbow["y"],
    }
    upper_vector = _lerp_rig_vector_by_angle(
        neutral_upper, target_upper, pose_amount,
    )
    lower_vector = _lerp_rig_vector_by_angle(
        neutral_lower, target_lower, pose_amount,
    )
    elbow = {
        "x": shoulder["x"] + upper_vector["x"],
        "y": shoulder["y"] + upper_vector["y"],
    }
    hand = {
        "x": elbow["x"] + lower_vector["x"],
        "y": elbow["y"] + lower_vector["y"],
    }
    upper_angle = _rig_vector_angle_degrees(
        upper_bind,
        {"x": elbow["x"] - shoulder["x"],
         "y": elbow["y"] - shoulder["y"]},
    )
    lower_angle = _rig_vector_angle_degrees(
        lower_bind,
        {"x": hand["x"] - elbow["x"], "y": hand["y"] - elbow["y"]},
    )
    tint = PLAYER_CUTOUT_RIG_DEFAULTS["far_arm_tint"] if is_far else None
    upper_part = _make_player_cutout_part(
        textures["upper_arm"], source_shoulder, shoulder,
        upper_angle, is_far, tint,
    )
    lower_part = _make_player_cutout_part(
        textures["lower_arm"], source_elbow, elbow,
        lower_angle, is_far, tint,
    )
    upper_part.update({
        "rig_side": side, "rig_hand": rig_hand,
        "rig_joint": "upper_arm", "rig_pose": "reload",
    })
    lower_part.update({
        "rig_side": side, "rig_hand": rig_hand,
        "rig_joint": "lower_arm", "rig_pose": "reload",
    })
    return [upper_part, lower_part]


def _build_player_front_reload_parts(
        player_entity, body_hip, torso_angle, direction, textures,
        weapon_arm, support_arm, weapon_side, support_side):
    timing = _player_reload_pose_timing(player_entity)
    start_progress, start_aim = _player_reload_start_weapon_state(player_entity)
    if timing["enter"] <= 0.000001 and start_progress <= 0.000001:
        return None
    pose_settings = PLAYER_RELOAD_POSE_DEFAULTS[direction]
    if timing["enter"] < 0.999999:
        support_amount = _player_reload_support_pose_amount(
            player_entity, timing,
        )
        weapon_amount = 1.0 if start_progress > 0.000001 else timing["enter"]
    else:
        support_amount = _player_reload_support_pose_amount(
            player_entity, timing,
        )
        weapon_amount = timing["leave"]
    support_parts = _build_player_front_reload_arm_parts(
        support_arm, body_hip, torso_angle, direction, textures,
        support_side == "far", support_amount, "left",
    )
    weapon_parts = _build_player_front_reload_arm_parts(
        weapon_arm, body_hip, torso_angle, direction, textures,
        weapon_side == "far", weapon_amount, "right",
    )
    gun_offset = _rotate_rig_vector(
        pose_settings["gun_from_body_hip"]["x"],
        pose_settings["gun_from_body_hip"]["y"], torso_angle,
    )
    gun_pivot = {
        "x": float(body_hip["x"]) + gun_offset["x"],
        "y": float(body_hip["y"]) + gun_offset["y"],
    }
    gun = _make_player_cutout_part(
        textures["gun"], PLAYER_FRONT_CUTOUT_ARM_DEFAULTS["gun_grip"],
        gun_pivot, float(pose_settings["gun_degrees"]) + torso_angle,
        source_canvas_width=PLAYER_FRONT_CUTOUT_ARM_DEFAULTS["gun_source_size"],
    )
    gun.update({
        "rig_side": weapon_side, "rig_hand": "right",
        "rig_joint": "gun", "rig_pose": "reload",
    })

    if (start_progress > 0.000001 and timing["enter"] < 0.999999
            and start_aim is not None):
        start_player = dict(player_entity)
        start_player["aim_direction"] = start_aim
        start_player["weapon_transition"] = {
            "progress": start_progress,
            "target": 1.0,
            "phase": "reload_start",
        }
        start_player["weapon_visual_recoil"] = {"rotation_degrees": 0.0}
        start_parts = _build_player_weapon_cutout_parts(
            start_player, body_hip, torso_angle, weapon_side == "far",
            weapon_arm,
            arm_settings=PLAYER_FRONT_CUTOUT_ARM_DEFAULTS,
            textures=textures,
            animation_direction=direction,
            rig_side=weapon_side, rig_hand="right",
        )
        blended = _lerp_player_cutout_parts(
            start_parts, [*weapon_parts, gun], timing["enter"],
        )
        weapon_parts = blended[:2]
        gun = blended[2]
        for part in [*weapon_parts, gun]:
            part["rig_pose"] = "reload"
    return {
        support_side: support_parts,
        weapon_side: [*weapon_parts, gun],
    }


def _build_player_side_cutout_rig_parts(player_entity):
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
    torso.update({"rig_joint": "torso", "body_bob": bob})
    # Keeping the head level makes the torso movement readable without making
    # the character's view look mechanically tied to every step.
    head = _make_player_cutout_part(
        PLAYER_CUTOUT_TEXTURES["head"], neck, body_neck, 0.0,
        facing_left,
    )
    head.update({"rig_joint": "head"})
    weapon_side = _player_rig_side_for_hand(direction, "right")
    flashlight_side = _player_rig_side_for_hand(direction, "left")
    weapon_progress = _player_weapon_transition_progress(player_entity)
    offhand_motion_scale = 1.0 - weapon_progress * (
        1.0 - float(PLAYER_CUTOUT_ARM_DEFAULTS["far_arm_aim_motion_scale"])
    )
    far_arm = _build_player_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle,
        facing_left, is_far=True,
        motion_scale=(
            offhand_motion_scale if flashlight_side == "far" else 1.0
        ),
    )
    near_arm = _build_player_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle,
        facing_left, is_far=False,
        motion_scale=(
            offhand_motion_scale if flashlight_side == "near" else 1.0
        ),
    )
    arms_by_side = {"near": near_arm, "far": far_arm}
    for side, arm in arms_by_side.items():
        hand = "right" if side == weapon_side else "left"
        arm["upper_part"]["rig_hand"] = hand
        arm["lower_part"]["rig_hand"] = hand
    weapon_arm = arms_by_side[weapon_side]
    flashlight_arm = arms_by_side[flashlight_side]
    weapon_parts = _build_player_weapon_cutout_parts(
        player_entity, body_hip, torso_angle, facing_left, weapon_arm,
        animation_direction=direction,
        rig_side=weapon_side, rig_hand="right",
    )
    flashlight_parts = _build_player_flashlight_cutout_parts(
        player_entity, body_hip, torso_angle, facing_left, flashlight_arm,
        animation_direction=direction,
        rig_side=flashlight_side, rig_hand="left",
    )
    support_parts = None
    if player_entity.get("reload_state", "") == "reloading":
        weapon_parts = _build_player_side_reload_parts(
            player_entity, body_hip, torso_angle, facing_left, weapon_arm,
            rig_side=weapon_side, rig_hand="right",
        )
        support_parts = _build_player_side_reload_support_parts(
            player_entity, facing_left, flashlight_arm, weapon_parts[-1],
            rig_side=flashlight_side, rig_hand="left",
        )
    arm_parts_by_side = {
        "near": [near_arm["upper_part"], near_arm["lower_part"]],
        "far": [far_arm["lower_part"], far_arm["upper_part"]],
    }
    if weapon_parts:
        arm_parts_by_side[weapon_side] = weapon_parts
    if flashlight_parts:
        arm_parts_by_side[flashlight_side] = flashlight_parts
    elif support_parts:
        arm_parts_by_side[flashlight_side] = support_parts
    near_arm_parts = arm_parts_by_side["near"]
    far_arm_parts = arm_parts_by_side["far"]
    far_lower, far_upper = leg_parts[0]
    near_lower, near_upper = leg_parts[1]
    return [
        *far_arm_parts,
        far_lower, far_upper, torso, near_lower, near_upper,
        *near_arm_parts, head,
    ]


def _build_player_front_locomotion_arm_pose(
        arm_phase, run_blend, movement_blend, body_hip, torso_angle,
        direction, textures, is_far=False, motion_scale=1.0):
    rig_settings = PLAYER_FRONT_CUTOUT_RIG_DEFAULTS
    arm_settings = PLAYER_FRONT_CUTOUT_ARM_DEFAULTS
    bind_pose = arm_settings["bind_pose"]
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
    swing_scale = max(0.0, float(motion_scale)) * float(movement_blend)
    side = "far" if is_far else "near"
    direction_profiles = PLAYER_FRONT_CUTOUT_ARM_PROFILES[direction]
    body_bind_hip = rig_settings["body_hip"]
    attachment = arm_settings[
        "far_shoulder" if is_far else "shoulder"
    ]
    shoulder_offset = _rotate_rig_vector(
        float(attachment["x"]) - float(body_bind_hip["x"]),
        float(attachment["y"]) - float(body_bind_hip["y"]),
        torso_angle,
    )
    shoulder = {
        "x": float(body_hip["x"]) + shoulder_offset["x"],
        "y": float(body_hip["y"]) + shoulder_offset["y"],
    }

    # Walking retains the readable lateral arm sway.
    walk_pose = sample_player_cutout_gait_profile(
        direction_profiles["walk"], arm_phase,
    )
    walk_upper_angle = torso_angle + float(
        walk_pose.get(f"{side}_upper_arm_degrees", 0.0)
    ) * float(rig_settings["arm_angle_scale"]) * swing_scale
    walk_lower_angle = walk_upper_angle - float(
        walk_pose.get(f"{side}_elbow_bend_degrees", 0.0)
    ) * float(rig_settings["elbow_angle_scale"]) * swing_scale
    walk_elbow_offset = _rotate_rig_vector(
        upper_bind["x"], upper_bind["y"], walk_upper_angle,
    )
    walk_elbow = {
        "x": shoulder["x"] + walk_elbow_offset["x"],
        "y": shoulder["y"] + walk_elbow_offset["y"],
    }
    walk_hand_offset = _rotate_rig_vector(
        lower_bind["x"], lower_bind["y"], walk_lower_angle,
    )
    walk_hand = {
        "x": walk_elbow["x"] + walk_hand_offset["x"],
        "y": walk_elbow["y"] + walk_hand_offset["y"],
    }

    # Running uses vertical compression/extension to represent the arm moving
    # toward and away from the camera, rather than drawing a lateral arc.
    run_pose = sample_player_cutout_gait_profile(
        direction_profiles["run"], arm_phase,
    )
    neutral_elbow_offset = _rotate_rig_vector(
        upper_bind["x"], upper_bind["y"], torso_angle,
    )
    neutral_hand_offset = _rotate_rig_vector(
        upper_bind["x"] + lower_bind["x"],
        upper_bind["y"] + lower_bind["y"],
        torso_angle,
    )
    run_elbow = {
        "x": shoulder["x"] + neutral_elbow_offset["x"] + float(
            run_pose.get(f"{side}_elbow_x_pixels", 0.0)
        ) * swing_scale,
        "y": shoulder["y"] + neutral_elbow_offset["y"] + float(
            run_pose.get(f"{side}_elbow_y_pixels", 0.0)
        ) * swing_scale,
    }
    run_hand = {
        "x": shoulder["x"] + neutral_hand_offset["x"] + float(
            run_pose.get(f"{side}_hand_x_pixels", 0.0)
        ) * swing_scale,
        "y": shoulder["y"] + neutral_hand_offset["y"] + float(
            run_pose.get(f"{side}_hand_y_pixels", 0.0)
        ) * swing_scale,
    }
    profile_amount = max(0.0, min(1.0, float(run_blend)))
    elbow = {
        "x": walk_elbow["x"] + (run_elbow["x"] - walk_elbow["x"])
             * profile_amount,
        "y": walk_elbow["y"] + (run_elbow["y"] - walk_elbow["y"])
             * profile_amount,
    }
    hand = {
        "x": walk_hand["x"] + (run_hand["x"] - walk_hand["x"])
             * profile_amount,
        "y": walk_hand["y"] + (run_hand["y"] - walk_hand["y"])
             * profile_amount,
    }
    target_upper = {
        "x": elbow["x"] - shoulder["x"],
        "y": elbow["y"] - shoulder["y"],
    }
    target_lower = {
        "x": hand["x"] - elbow["x"],
        "y": hand["y"] - elbow["y"],
    }
    upper_angle = _rig_vector_angle_degrees(upper_bind, target_upper)
    lower_angle = _rig_vector_angle_degrees(lower_bind, target_lower)
    upper_scale = math.hypot(
        target_upper["x"], target_upper["y"],
    ) / max(0.0001, math.hypot(upper_bind["x"], upper_bind["y"]))
    lower_scale = math.hypot(
        target_lower["x"], target_lower["y"],
    ) / max(0.0001, math.hypot(lower_bind["x"], lower_bind["y"]))
    tint = PLAYER_CUTOUT_RIG_DEFAULTS["far_arm_tint"] if is_far else None
    upper_part = _make_player_cutout_part(
        textures["upper_arm"], source_shoulder, shoulder,
        upper_angle, is_far, tint, scale_y=upper_scale,
    )
    lower_part = _make_player_cutout_part(
        textures["lower_arm"], source_elbow, elbow,
        lower_angle, is_far, tint, scale_y=lower_scale,
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


def _build_player_front_cutout_rig_parts(player_entity, direction):
    settings = PLAYER_FRONT_CUTOUT_RIG_DEFAULTS
    textures = PLAYER_CUTOUT_DIRECTION_TEXTURES[direction]
    gait = player_entity.get("procedural_gait", {})
    try:
        phase = (
            float(gait.get("phase", 0.0))
            + math.radians(float(
                PLAYER_CUTOUT_RIG_DEFAULTS["footfall_phase_degrees"]
            ))
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

    leg_texture_direction = direction
    if (direction == "down"
            and settings.get("down_locomotion_uses_up_leg_art", True)
            and blend > float(settings["locomotion_leg_art_blend_threshold"])):
        leg_texture_direction = "up"
    leg_textures = PLAYER_CUTOUT_DIRECTION_TEXTURES[leg_texture_direction]

    body_pose = _blended_player_front_leg_pose(
        direction, phase, run_blend,
    )
    bob = float(body_pose.get("body_y_pixels", 0.0)) * blend
    torso_angle = (
        float(body_pose.get("torso_degrees", 0.0))
        * float(settings["torso_angle_scale"]) * blend
    )
    bind_body_hip = settings["body_hip"]
    body_hip = {
        "x": float(bind_body_hip["x"]),
        "y": float(bind_body_hip["y"]) + bob,
    }
    neck = settings["neck"]
    neck_from_hip = _rotate_rig_vector(
        float(neck["x"]) - float(bind_body_hip["x"]),
        float(neck["y"]) - float(bind_body_hip["y"]),
        torso_angle,
    )
    body_neck = {
        "x": body_hip["x"] + neck_from_hip["x"],
        "y": body_hip["y"] + neck_from_hip["y"],
    }

    leg_bind = settings["leg_bind_pose"]
    source_hip = leg_bind["hip"]
    # The down-facing authored upper leg includes one extra row at its foot.
    # Pivoting at y=26 keeps that row attached to the knee; up uses y=25.
    source_knee = dict(leg_bind["knee"])
    if leg_texture_direction == "down":
        source_knee["y"] = 26.0
    source_foot = dict(leg_bind["foot"])
    source_upper_vector = {
        "x": float(source_knee["x"]) - float(source_hip["x"]),
        "y": float(source_knee["y"]) - float(source_hip["y"]),
    }
    source_lower_vector = {
        "x": float(source_foot["x"]) - float(source_knee["x"]),
        "y": float(source_foot["y"]) - float(source_knee["y"]),
    }
    source_hip_to_foot = {
        "x": float(source_foot["x"]) - float(source_hip["x"]),
        "y": float(source_foot["y"]) - float(source_hip["y"]),
    }
    source_upper_length = max(
        0.0001, math.hypot(
            source_upper_vector["x"], source_upper_vector["y"],
        ),
    )
    source_lower_length = max(
        0.0001, math.hypot(
            source_lower_vector["x"], source_lower_vector["y"],
        ),
    )
    lateral_scale = float(settings["leg_lateral_scale"])
    lift_scale = float(settings["leg_lift_scale"])
    leg_parts = []
    for is_far in (True, False):
        side = "far" if is_far else "near"
        attachment = settings[f"{side}_hip"]
        attachment_offset = _rotate_rig_vector(
            float(attachment["x"]) - float(bind_body_hip["x"]),
            float(attachment["y"]) - float(bind_body_hip["y"]),
            torso_angle,
        )
        target_hip = {
            "x": body_hip["x"] + attachment_offset["x"],
            "y": body_hip["y"] + attachment_offset["y"],
        }
        target_knee = {
            "x": target_hip["x"] + source_upper_vector["x"] + float(
                body_pose.get(f"{side}_knee_x_pixels", 0.0)
            ) * lateral_scale * blend,
            "y": target_hip["y"] + source_upper_vector["y"] + float(
                body_pose.get(f"{side}_knee_y_pixels", 0.0)
            ) * lift_scale * blend,
        }
        target_foot = {
            "x": target_hip["x"] + source_hip_to_foot["x"] + float(
                body_pose.get(f"{side}_foot_x_pixels", 0.0)
            ) * lateral_scale * blend,
            "y": target_hip["y"] + source_hip_to_foot["y"] + float(
                body_pose.get(f"{side}_foot_y_pixels", 0.0)
            ) * lift_scale * blend,
        }
        target_upper_vector = {
            "x": target_knee["x"] - target_hip["x"],
            "y": target_knee["y"] - target_hip["y"],
        }
        target_lower_vector = {
            "x": target_foot["x"] - target_knee["x"],
            "y": target_foot["y"] - target_knee["y"],
        }
        upper_angle = _rig_vector_angle_degrees(
            source_upper_vector, target_upper_vector,
        )
        lower_angle = _rig_vector_angle_degrees(
            source_lower_vector, target_lower_vector,
        )
        upper_scale = math.hypot(
            target_upper_vector["x"], target_upper_vector["y"],
        ) / source_upper_length
        lower_scale = math.hypot(
            target_lower_vector["x"], target_lower_vector["y"],
        ) / source_lower_length
        tint = (
            PLAYER_CUTOUT_RIG_DEFAULTS["far_leg_tint"]
            if is_far else None
        )
        lower_part = _make_player_cutout_part(
            leg_textures["lower_leg"], source_knee, target_knee,
            lower_angle, is_far, tint, scale_y=lower_scale,
        )
        upper_part = _make_player_cutout_part(
            leg_textures["upper_leg"], source_hip, target_hip,
            upper_angle, is_far, tint, scale_y=upper_scale,
        )
        lower_part.update({"rig_side": side, "rig_joint": "lower_leg"})
        upper_part.update({"rig_side": side, "rig_joint": "upper_leg"})
        leg_parts.append((lower_part, upper_part))

    torso = _make_player_cutout_part(
        textures["torso"], bind_body_hip, body_hip, torso_angle,
    )
    torso.update({"rig_joint": "torso", "body_bob": bob})
    head = _make_player_cutout_part(
        textures["head"], neck, body_neck, 0.0,
    )
    head.update({"rig_joint": "head"})

    weapon_side = _player_rig_side_for_hand(direction, "right")
    flashlight_side = _player_rig_side_for_hand(direction, "left")
    weapon_progress = _player_weapon_transition_progress(player_entity)
    offhand_motion_scale = 1.0 - weapon_progress * (
        1.0 - float(
            PLAYER_FRONT_CUTOUT_ARM_DEFAULTS["far_arm_aim_motion_scale"]
        )
    )
    far_arm = _build_player_front_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle, direction, textures,
        is_far=True,
        motion_scale=(
            offhand_motion_scale if flashlight_side == "far" else 1.0
        ),
    )
    near_arm = _build_player_front_locomotion_arm_pose(
        phase, run_blend, blend, body_hip, torso_angle, direction, textures,
        is_far=False,
        motion_scale=(
            offhand_motion_scale if flashlight_side == "near" else 1.0
        ),
    )
    arms_by_side = {"near": near_arm, "far": far_arm}
    for side, arm in arms_by_side.items():
        hand = "right" if side == weapon_side else "left"
        arm["upper_part"]["rig_hand"] = hand
        arm["lower_part"]["rig_hand"] = hand
    weapon_arm = arms_by_side[weapon_side]
    flashlight_arm = arms_by_side[flashlight_side]
    weapon_parts = _build_player_weapon_cutout_parts(
        player_entity, body_hip, torso_angle, weapon_side == "far",
        weapon_arm,
        arm_settings=PLAYER_FRONT_CUTOUT_ARM_DEFAULTS,
        textures=textures,
        animation_direction=direction,
        rig_side=weapon_side, rig_hand="right",
    )
    flashlight_parts = _build_player_flashlight_cutout_parts(
        player_entity, body_hip, torso_angle, flashlight_side == "far",
        flashlight_arm,
        arm_settings=PLAYER_FRONT_CUTOUT_ARM_DEFAULTS,
        textures=textures, animation_direction=direction,
        rig_side=flashlight_side, rig_hand="left",
    )
    reload_parts = None
    if player_entity.get("reload_state", "") == "reloading":
        reload_parts = _build_player_front_reload_parts(
            player_entity, body_hip, torso_angle, direction, textures,
            weapon_arm, flashlight_arm, weapon_side, flashlight_side,
        )
    arm_parts_by_side = {
        "near": [near_arm["upper_part"], near_arm["lower_part"]],
        "far": [far_arm["lower_part"], far_arm["upper_part"]],
    }
    if reload_parts is not None:
        arm_parts_by_side.update(reload_parts)
        if flashlight_parts:
            arm_parts_by_side[flashlight_side] = flashlight_parts
    else:
        if weapon_parts:
            arm_parts_by_side[weapon_side] = weapon_parts
        if flashlight_parts:
            arm_parts_by_side[flashlight_side] = flashlight_parts
    far_arm_parts = arm_parts_by_side["far"]
    near_arm_parts = arm_parts_by_side["near"]
    far_lower, far_upper = leg_parts[0]
    near_lower, near_upper = leg_parts[1]
    far_parts = [
        *far_arm_parts,
        far_lower, far_upper,
    ]
    near_leg_parts = [near_lower, near_upper]
    if direction == "up":
        # Raised arms and the weapon travel behind the back-facing torso/head.
        return [
            *far_parts, *near_leg_parts, *near_arm_parts, torso, head,
        ]
    if weapon_side == "far" and (weapon_parts or reload_parts is not None):
        # Facing down, the anatomical right/weapon arm occupies the mirrored
        # far slot, but it still needs to draw in front of the torso. Near/far
        # selects the limb geometry here; it is not a universal depth order.
        return [
            far_lower, far_upper, torso, *near_leg_parts,
            *far_arm_parts, *near_arm_parts, head,
        ]
    return [
        *far_parts, torso, *near_leg_parts, *near_arm_parts, head,
    ]


def build_player_cutout_rig_parts(player_entity):
    """Build the procedural player cutout for any cardinal facing."""
    if not PLAYER_CUTOUT_RIG_DEFAULTS.get("enabled", True):
        return []
    direction = player_entity.get("animation_direction")
    if direction is None:
        frame_name = str(player_entity.get("animation_frame", ""))
        direction = next(
            (name for name in ("left", "right", "up", "down")
             if frame_name.startswith(name)),
            None,
        )
    if direction in {"left", "right"}:
        return _build_player_side_cutout_rig_parts(player_entity)
    if direction in {"up", "down"}:
        return _build_player_front_cutout_rig_parts(player_entity, direction)
    return []


def _blended_redhead_cutout_gait_pose(phase, run_blend):
    walk = sample_player_cutout_gait_profile(
        REDHEAD_CUTOUT_GAIT_PROFILES["walk"], phase,
    )
    run = sample_player_cutout_gait_profile(
        REDHEAD_CUTOUT_GAIT_PROFILES["run"], phase,
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
                               rotation, mirror=False, tint=None):
    canvas_size = float(REDHEAD_CUTOUT_RIG_DEFAULTS["canvas_size"])
    return _make_player_cutout_part(
        texture_name, source_pivot, target_pivot, rotation,
        facing_left=mirror, tint=tint,
        source_canvas_width=canvas_size,
        target_canvas_width=canvas_size,
    )


def build_redhead_cutout_rig_parts(entity):
    """Build the red head's cardinal, speed-blended procedural locomotion."""
    settings = REDHEAD_CUTOUT_RIG_DEFAULTS
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

    pose = _blended_redhead_cutout_gait_pose(phase, run_blend)
    front_facing = direction in {"up", "down"}
    rig = settings["front" if front_facing else "side"]
    texture_direction = direction if direction != "left" else "right"
    textures = REDHEAD_CUTOUT_TEXTURES[texture_direction]
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
        textures["torso"], bind_hip, body_hip, torso_angle, facing_left,
    )
    torso.update({
        "rig_joint": "torso", "body_bob": body_y,
        "body_sway": body_x,
    })
    head = _make_redhead_cutout_part(
        textures["head"], neck, body_neck, 0.0, facing_left,
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
            upper_leg_angle, mirror_part, tint,
        )
        lower_leg = _make_redhead_cutout_part(
            textures["lower_leg"], source_knee, target_knee,
            lower_leg_angle, mirror_part, tint,
        )
        upper_leg.update({"rig_side": side, "rig_joint": "upper_leg"})
        lower_leg.update({"rig_side": side, "rig_joint": "lower_leg"})
        legs[side] = [lower_leg, upper_leg]

        upper_arm_angle = torso_angle + float(
            pose.get(f"{side}_upper_arm_degrees", 0.0)
        ) * blend
        lower_arm_angle = upper_arm_angle + float(
            pose.get(f"{side}_elbow_bend_degrees", 0.0)
        ) * blend
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
            upper_arm_angle, mirror_part, tint,
        )
        lower_arm = _make_redhead_cutout_part(
            textures["lower_arm"], source_elbow, target_elbow,
            lower_arm_angle, mirror_part, tint,
        )
        upper_arm.update({"rig_side": side, "rig_joint": "upper_arm"})
        lower_arm.update({"rig_side": side, "rig_joint": "lower_arm"})
        arms[side] = [lower_arm, upper_arm]

    if direction == "up":
        return [
            *arms["far"], *legs["far"], *legs["near"],
            *arms["near"], torso, head,
        ]
    return [
        *arms["far"], *legs["far"], torso,
        *legs["near"], *arms["near"], head,
    ]


def player_cutout_gun_barrel_world(player_entity, tile_map):
    """Return the rendered gun-tip position and direction in world space."""
    parts = build_player_cutout_rig_parts(player_entity)
    gun = next((
        part for part in parts if part.get("rig_joint") == "gun"
    ), None)
    if gun is None:
        return None
    grip = gun.get("pivot_local", {})
    source_grip = PLAYER_CUTOUT_ARM_DEFAULTS["gun_grip"]
    source_muzzle = PLAYER_CUTOUT_ARM_DEFAULTS["gun_muzzle"]
    source_direction = PLAYER_CUTOUT_ARM_DEFAULTS["gun_barrel_direction"]
    muzzle_from_grip = {
        "x": float(source_muzzle["x"]) - float(source_grip["x"]),
        "y": float(source_muzzle["y"]) - float(source_grip["y"]),
    }
    if gun.get("flip_x", False):
        muzzle_from_grip["x"] = -muzzle_from_grip["x"]
        source_direction = {
            "x": -float(source_direction["x"]),
            "y": float(source_direction["y"]),
        }
    transformed_muzzle = _rotate_rig_vector(
        muzzle_from_grip["x"], muzzle_from_grip["y"],
        float(gun.get("rotation", 0.0)),
    )
    direction = _rotate_rig_vector(
        source_direction["x"], source_direction["y"],
        float(gun.get("rotation", 0.0)),
    )
    direction_length = math.hypot(direction["x"], direction["y"])
    if direction_length <= 0.000001:
        return None
    direction = {
        "x": direction["x"] / direction_length,
        "y": direction["y"] / direction_length,
    }
    player_world = position_to_world(player_entity.get("position", {}), tile_map)
    # Rig pivots are sprite-local, so their world origin must match the
    # destination rectangle used by build_player_render_item.  Player
    # position is the character anchor/flashlight origin, not the sprite's
    # top-left corner.
    render_anchor = player_entity.get("render_anchor_offset", {})
    top_left = {
        "x": player_world["x"] + float(render_anchor.get("x", -16.0)),
        "y": player_world["y"] + float(render_anchor.get("y", -16.0)),
    }
    grip_world = {
        "x": top_left["x"] + float(grip.get("x", 0.0)),
        "y": top_left["y"] + float(grip.get("y", 0.0)),
    }
    return {
        "position": {
            "x": grip_world["x"] + transformed_muzzle["x"],
            "y": grip_world["y"] + transformed_muzzle["y"],
        },
        "direction": direction,
        "grip_position": grip_world,
    }


def player_cutout_flashlight_world(player_entity, tile_map):
    """Return the deployed flashlight tip using the rendered spare-arm rig."""
    parts = build_player_cutout_rig_parts(player_entity)
    flashlight = next((
        part for part in parts if part.get("rig_joint") == "flashlight"
    ), None)
    if flashlight is None:
        return None
    direction = normalize_vector(player_entity.get("aim_direction", {}))
    if direction is None:
        return None
    player_world = position_to_world(player_entity.get("position", {}), tile_map)
    render_anchor = player_entity.get("render_anchor_offset", {})
    pivot = flashlight.get("pivot_local", {})
    grip = {
        "x": player_world["x"] + float(render_anchor.get("x", -16.0))
             + float(pivot.get("x", 0.0)),
        "y": player_world["y"] + float(render_anchor.get("y", -16.0))
             + float(pivot.get("y", 0.0)),
    }
    distance = max(
        0.0, float(flashlight.get("held_item_tip_distance", 5.0)),
    )
    return {
        "position": {
            "x": grip["x"] + direction["x"] * distance,
            "y": grip["y"] + direction["y"] * distance,
        },
        "grip_position": grip,
        "direction": direction,
    }


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
            if part.get("rig_joint") == "torso"
        ), None)
        if torso_part is not None:
            body_bob = float(torso_part.get("body_bob", 0.0))
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
        cutout_parts = build_redhead_cutout_rig_parts(entity)
        render_item = make_world_render_item(
            "entity", entity_type, f"brains:{object_id}", object_id,
            entity, world_position, 24.0, 24.0,
            make_texture_reference(
                "sprite_sheets", "red_head_texture_sheet", "sheet",
            ),
            {"x": float(frame_number) * 24.0, "y": 0.0,
             "width": 24.0, "height": 24.0},
            {"cutout_rig_parts": cutout_parts},
        )
        render_item["screen_snap"] = "relative_motion"
        return render_item
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
