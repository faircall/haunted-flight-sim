"""Event-driven spatial audio policy and cyminiaudio runtime adapter.

Persistent game data enters this module as plain dictionaries. cyminiaudio
objects remain exclusively in the transient runtime owned by ``game_assets``.
"""

import copy
import math
import os
import random

import cyminiaudio as cma


AUDIO_SURFACES = (
    "grass", "dirt", "tile", "wood", "metal", "carpet", "stone", "generic",
)
BULLET_IMPACT_MATERIALS = ("wood", "stone", "metal")
AUDIO_SURFACE_SCHEMA_REVISION = 1
PLAYER_FOOTSTEP_VARIANT_COUNTS = {
    "carpet": 5,
    "wood": 5,
    "stone": 5,
    "grass": 5,
}
REDHEAD_FOOTSTEP_VARIANT_COUNTS = {
    "carpet": 5,
    "wood": 5,
    "stone": 5,
    "grass": 5,
}
SOUND_EMITTER_ASSETS = {
    "bells": ("sounds/ambience/bells/bell_loop.wav",),
}
SOUND_EMITTER_FAMILIES = tuple(SOUND_EMITTER_ASSETS)
FOOTSTEP_OVERLAYS = ("none", "puddle")
SUPPORTED_EVENT_TYPES = {
    "footstep", "gunshot", "reload_start", "reload_stop", "weapon_empty",
    "weapon_unholster", "weapon_holster", "sound_instance_stop",
    "bullet_wall_impact", "melee_whoosh", "stagger_impact", "death_impact",
    "pickup_ammo", "pickup_health", "ui_hover", "fire_crackle",
    "flashlight_click",
    "redhead_startle", "redhead_pursuit_hiss", "redhead_evade",
    "ambience_incidental",
    "sound_emitter_cadence",
}
CONTROL_EVENT_TYPES = {"reload_stop", "sound_instance_stop"}
OUTDOOR_ENVIRONMENTS = {"open_exterior", "covered_exterior"}
INTERIOR_ENVIRONMENTS = {
    "small_interior", "medium_interior", "large_interior", "stone_hall",
}
AUDIBILITY_EPSILON = 0.005


def _clamp(value, minimum, maximum):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = minimum
    return max(minimum, min(maximum, value))


def _clamp_int(value, minimum, maximum, fallback):
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        value = int(fallback)
    return max(minimum, min(maximum, value))


def make_audio_profile(profile_name="default"):
    """Return fresh, serialisable audio policy data."""
    return {
        "name": str(profile_name or "default"),
        "master_gain": 1.0,
        "sfx_gain": 1.0,
        "footstep_gain": 1.0,
        "weapon_gain": 1.0,
        "ambience_gain": 0.8,
        "weather_gain": 0.8,
        "ui_gain": 0.8,
        "minimum_distance": 12.0,
        "maximum_distance": 260.0,
        "pan_distance": 140.0,
        "maximum_pan": 0.85,
        "enemy_footstep_group_spacing": 0.055,
        "enemy_footstep_voice_limit": 4,
        "enemy_footsteps_per_frame": 1,
        "loop_attack_seconds": 0.45,
        "loop_release_seconds": 0.75,
        "pitch_variation": {
            "player_footstep": 0.035,
            "enemy_footstep": 0.045,
            "impact": 0.03,
        },
        "player_walk_stride": 13.0,
        "player_run_stride": 18.0,
        "enemy_stride": 15.0,
    }


def make_default_sound_emitter(position):
    """Return persistent authored data; the live Sound remains in audio_runtime."""
    return {
        "type": "sound",
        "position": copy.deepcopy(position),
        "enabled": True,
        "family": "bells",
        "playback_mode": "loop",
        "gain": 0.8,
        "minimum_distance": 12.0,
        "maximum_distance": 260.0,
        "pan_distance": 140.0,
        "maximum_pan": 0.85,
        "cadence_seconds": 50.0,
        "cadence_variation": 0.0,
        "seed": 4409,
    }


def normalize_sound_emitter(emitter):
    if not isinstance(emitter, dict):
        return emitter
    defaults = make_default_sound_emitter(emitter.get("position", {}))
    for key, value in defaults.items():
        emitter.setdefault(key, copy.deepcopy(value))
    emitter["type"] = "sound"
    emitter["enabled"] = bool(emitter.get("enabled", True))
    family = str(emitter.get("family", "bells"))
    emitter["family"] = family if family in SOUND_EMITTER_FAMILIES else "bells"
    mode = str(emitter.get("playback_mode", "loop"))
    emitter["playback_mode"] = mode if mode in {"loop", "cadence"} else "loop"
    emitter["gain"] = _clamp(emitter.get("gain", 0.8), 0.0, 2.0)
    emitter["minimum_distance"] = _clamp(
        emitter.get("minimum_distance", 12.0), 0.0, 10000.0,
    )
    emitter["maximum_distance"] = max(
        emitter["minimum_distance"] + 0.001,
        _clamp(emitter.get("maximum_distance", 260.0), 0.001, 10000.0),
    )
    emitter["pan_distance"] = _clamp(
        emitter.get("pan_distance", 140.0), 0.001, 10000.0,
    )
    emitter["maximum_pan"] = _clamp(emitter.get("maximum_pan", 0.85), 0.0, 1.0)
    emitter["cadence_seconds"] = _clamp(
        emitter.get("cadence_seconds", 50.0), 0.25, 3600.0,
    )
    emitter["cadence_variation"] = _clamp(
        emitter.get("cadence_variation", 0.0), 0.0,
        emitter["cadence_seconds"] * 0.95,
    )
    emitter["seed"] = _clamp_int(emitter.get("seed", 4409), 0, 2147483647, 4409)
    return emitter


def migrate_sound_emitters(sound_emitters):
    if not isinstance(sound_emitters, dict):
        return sound_emitters
    for emitter in sound_emitters.values():
        normalize_sound_emitter(emitter)
    return sound_emitters


def sound_emitter_spatial_policy(emitter):
    emitter = normalize_sound_emitter(emitter)
    return {
        "minimum_distance": emitter["minimum_distance"],
        "maximum_distance": emitter["maximum_distance"],
        "pan_distance": emitter["pan_distance"],
        "maximum_pan": emitter["maximum_pan"],
    }


def sound_emitter_cadence_interval(emitter, occurrence_index):
    emitter = normalize_sound_emitter(emitter)
    randomizer = random.Random(
        int(emitter["seed"]) + max(0, int(occurrence_index)) * 104729,
    )
    variation = emitter["cadence_variation"]
    return max(
        0.25,
        emitter["cadence_seconds"] + randomizer.uniform(-variation, variation),
    )


def normalize_audio_profile(profile):
    defaults = make_audio_profile(
        profile.get("name", "default") if isinstance(profile, dict) else "default"
    )
    if not isinstance(profile, dict):
        profile = defaults
    for key, value in defaults.items():
        if key == "pitch_variation":
            current = profile.setdefault(key, {})
            if not isinstance(current, dict):
                current = {}
                profile[key] = current
            for pitch_key, pitch_value in value.items():
                current.setdefault(pitch_key, pitch_value)
                current[pitch_key] = _clamp(current[pitch_key], 0.0, 0.25)
        else:
            profile.setdefault(key, copy.deepcopy(value))
    for key in (
        "master_gain", "sfx_gain", "footstep_gain", "weapon_gain",
        "ambience_gain", "weather_gain", "ui_gain",
    ):
        profile[key] = _clamp(profile[key], 0.0, 2.0)
    profile["minimum_distance"] = _clamp(profile["minimum_distance"], 0.0, 10000.0)
    profile["maximum_distance"] = max(
        profile["minimum_distance"] + 0.001,
        _clamp(profile["maximum_distance"], 0.001, 10000.0),
    )
    profile["pan_distance"] = _clamp(profile["pan_distance"], 0.001, 10000.0)
    profile["maximum_pan"] = _clamp(profile["maximum_pan"], 0.0, 1.0)
    profile["enemy_footstep_group_spacing"] = _clamp(
        profile["enemy_footstep_group_spacing"], 0.0, 1.0
    )
    profile["enemy_footstep_voice_limit"] = _clamp_int(
        profile["enemy_footstep_voice_limit"], 1, 32,
        defaults["enemy_footstep_voice_limit"],
    )
    profile["enemy_footsteps_per_frame"] = _clamp_int(
        profile["enemy_footsteps_per_frame"], 1, 16,
        defaults["enemy_footsteps_per_frame"],
    )
    profile["loop_attack_seconds"] = _clamp(profile["loop_attack_seconds"], 0.001, 10.0)
    profile["loop_release_seconds"] = _clamp(profile["loop_release_seconds"], 0.001, 10.0)
    for key in ("player_walk_stride", "player_run_stride", "enemy_stride"):
        profile[key] = _clamp(profile[key], 1.0, 100.0)
    return profile


def _family(variants=(), fallback=None, base_gain=1.0, pitch_variation=0.0,
            voice_count=4, spatial=True, bus="sfx", optional=False,
            muffled_variants=()):
    return {
        "variants": list(variants),
        "muffled_variants": list(muffled_variants),
        "fallback": fallback,
        "base_gain": float(base_gain),
        "pitch_variation": float(pitch_variation),
        "voice_count": int(voice_count),
        "spatial": bool(spatial),
        "bus": str(bus),
        "optional": bool(optional),
    }


def make_audio_manifest():
    """Describe semantic families without pretending fallbacks are variants."""
    player_surface_variants = {
        surface: [
            f"sounds/footsteps/player/{surface}/player_{surface}_{index}.wav"
            for index in range(1, variant_count + 1)
        ]
        for surface, variant_count in PLAYER_FOOTSTEP_VARIANT_COUNTS.items()
    }
    player_surfaces = {
        surface: _family(variants=player_surface_variants.get(surface, ()),
                         fallback="sounds/player_footstep.wav", base_gain=0.75,
                         pitch_variation=0.035, voice_count=5, bus="footsteps")
        for surface in AUDIO_SURFACES
    }
    redhead_surface_variants = {
        surface: [
            f"sounds/footsteps/redhead/{surface}/redhead_{surface}_{index}.wav"
            for index in range(1, variant_count + 1)
        ]
        for surface, variant_count in REDHEAD_FOOTSTEP_VARIANT_COUNTS.items()
    }
    enemy_surfaces = {
        surface: _family(variants=redhead_surface_variants.get(surface, ()),
                         fallback="sounds/player_footstep.wav", base_gain=0.58,
                         pitch_variation=0.045, voice_count=5, bus="footsteps")
        for surface in AUDIO_SURFACES
    }
    return {
        "footstep_mix": {
            "none": {"base": 1.0, "overlay": 0.0},
            "puddle": {"base": 0.55, "overlay": 0.85},
            "corpse": {"base": 0.35, "overlay": 1.0},
        },
        "footsteps": {
            "player": player_surfaces,
            "enemy_contact": enemy_surfaces,
            "enemy_body": _family(optional=True, base_gain=0.35, bus="footsteps"),
        },
        "footstep_overlays": {
            "puddle": _family(optional=True, base_gain=1.0, bus="footsteps"),
            "corpse": _family(optional=True, base_gain=1.0, bus="footsteps"),
        },
        "barks": {
            "redhead": {
                "startle": _family(
                    variants=("sounds/barks/redhead/redhead_startle_1.wav",),
                    base_gain=0.8, pitch_variation=0.01,
                    voice_count=3, spatial=True, bus="sfx",
                ),
                "pursuit_hiss": _family(
                    variants=tuple(
                        f"sounds/barks/redhead/redhead_hiss_{index}.wav"
                        for index in range(1, 4)
                    ),
                    base_gain=0.8, pitch_variation=0.025,
                    voice_count=3, spatial=True, bus="sfx",
                ),
                "evade": _family(
                    variants=tuple(
                        f"sounds/barks/redhead/redhead_evade_{index}.wav"
                        for index in range(1, 3)
                    ),
                    base_gain=0.8, pitch_variation=0.02,
                    voice_count=3, spatial=True, bus="sfx",
                ),
            },
        },
        "weapons": {
            "pistol_shot": _family(fallback="sounds/pistol_shot_lofi.wav", base_gain=0.5,
                                     pitch_variation=0.015, voice_count=8, bus="weapons"),
            "pistol_mechanical": _family(optional=True, base_gain=0.25, voice_count=4, bus="weapons"),
            "pistol_reload": _family(fallback="sounds/pistol_reload.wav", base_gain=0.75,
                                      voice_count=2, bus="weapons"),
            "pistol_unholster": _family(
                fallback="sounds/unholster.wav", base_gain=0.75,
                voice_count=1, bus="weapons",
            ),
            "pistol_holster": _family(
                fallback="sounds/holster.wav", base_gain=0.75,
                voice_count=1, bus="weapons",
            ),
            "pistol_empty": _family(fallback="sounds/pistol_empty.wav", base_gain=0.5,
                                     pitch_variation=0.01, voice_count=3, bus="weapons"),
            "small_room_tail": _family(optional=True, base_gain=0.35, voice_count=3, bus="weapons"),
            "large_hall_tail": _family(optional=True, base_gain=0.5, voice_count=3, bus="weapons"),
        },
        "equipment": {
            # Temporary draw/holster endpoint sound. This family gives the
            # eventual dedicated flashlight audio a stable replacement point.
            "flashlight_click": _family(
                fallback="sounds/ui_hover.wav", base_gain=0.75,
                voice_count=1, bus="sfx",
            ),
        },
        "impacts": {
            "bullet_wall": _family(fallback="sounds/pistol_hit_wall.wav", base_gain=0.75,
                                    pitch_variation=0.03, voice_count=5),
            **{
                f"bullet_wall_{material}": _family(
                    # Material recordings can be dropped into this stable
                    # path later. Until then, pitch/gain treatment below keeps
                    # the existing wall recording usefully differentiated.
                    variants=(
                        f"sounds/impacts/pistol_hit_{material}.wav",
                    ) if os.path.isfile(
                        f"sounds/impacts/pistol_hit_{material}.wav"
                    ) else (),
                    fallback="sounds/pistol_hit_wall.wav",
                    base_gain={"wood": 0.68, "stone": 0.75, "metal": 0.82}[
                        material
                    ],
                    pitch_variation=0.03,
                    voice_count=5,
                )
                for material in BULLET_IMPACT_MATERIALS
            },
            "melee_whoosh": _family(fallback="sounds/whoosh.wav", base_gain=0.75,
                                     pitch_variation=0.03, voice_count=4),
            "stagger": _family(fallback="sounds/punch_1.wav", base_gain=0.75,
                                pitch_variation=0.03, voice_count=5),
            "death": _family(fallback="sounds/death_hit.wav", base_gain=0.5,
                              pitch_variation=0.02, voice_count=4),
        },
        "pickups": {
            "ammo": _family(fallback="sounds/ammo_pickup.wav", base_gain=0.75, voice_count=3),
            "health": _family(fallback="sounds/health_apply.wav", base_gain=0.75, voice_count=3),
        },
        "weather": {
            name: _family(optional=True, base_gain=1.0, voice_count=1,
                          spatial=False, bus="weather")
            for name in ("rain_open_body", "rain_open_detail", "rain_roof", "rain_muffled", "rain_drips")
        },
        "fire": {
            "fire_bed_small": _family(optional=True, voice_count=1, bus="ambience"),
            "fire_bed_large": _family(optional=True, voice_count=1, bus="ambience"),
            "fire_crackle": _family(optional=True, voice_count=5, bus="ambience"),
        },
        "ambience": {
            environment: {
                "base": _family(optional=True, voice_count=1, spatial=False, bus="ambience"),
                "wind": _family(optional=True, voice_count=1, spatial=False, bus="ambience"),
                "incidental": _family(optional=True, voice_count=3, spatial=False, bus="ambience"),
            }
            for environment in (
                "open_exterior", "covered_exterior", "small_interior",
                "medium_interior", "large_interior", "stone_hall",
            )
        },
        "sound_emitters": {
            family_name: _family(
                variants=asset_paths,
                fallback=None, base_gain=1.0, pitch_variation=0.0,
                voice_count=3, spatial=True, bus="ambience",
            )
            for family_name, asset_paths in SOUND_EMITTER_ASSETS.items()
        },
        "ui": {
            "hover": _family(fallback="sounds/ui_hover.wav", base_gain=0.75,
                              voice_count=3, spatial=False, bus="UI"),
        },
    }


def get_family_definition(manifest, family):
    current = manifest
    parts = family if isinstance(family, (tuple, list)) else str(family).split(".")
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, dict) and "variants" in current else None


def make_default_acoustic_zones():
    return {
        0: {"name": "outdoor", "environment": "open_exterior", "ambience_set": "open_exterior",
            "reverb_preset": "exterior", "wet_send": 0.05, "high_frequency_damping": 0.0},
        1: {"name": "small_room", "environment": "small_interior", "ambience_set": "small_interior",
            "reverb_preset": "small_room", "wet_send": 0.18, "high_frequency_damping": 0.08},
        2: {"name": "large_hall", "environment": "large_interior", "ambience_set": "large_hall",
            "reverb_preset": "large_hall", "wet_send": 0.42, "high_frequency_damping": 0.15},
        3: {"name": "covered_exterior", "environment": "covered_exterior", "ambience_set": "covered_exterior",
            "reverb_preset": "exterior", "wet_send": 0.08, "high_frequency_damping": 0.04},
        4: {"name": "medium_room", "environment": "medium_interior", "ambience_set": "medium_interior",
            "reverb_preset": "medium_room", "wet_send": 0.28, "high_frequency_damping": 0.11},
        5: {"name": "stone_hall", "environment": "stone_hall", "ambience_set": "stone_hall",
            "reverb_preset": "stone_hall", "wet_send": 0.48, "high_frequency_damping": 0.18},
    }


def detect_audio_capabilities():
    sound_attributes = set(dir(getattr(cma, "Sound", object)))
    return {
        "volume": "volume" in sound_attributes,
        "pitch": "pitch" in sound_attributes,
        "pan": "pan" in sound_attributes,
        "looping": "looping" in sound_attributes,
        "sound_3d_controls": all(name in sound_attributes for name in ("set_position", "spatialization_enabled")),
        "standalone_low_pass": hasattr(cma, "LowPassFilter"),
        "standalone_delay": hasattr(cma, "Delay"),
        "node_graph": hasattr(cma, "NodeGraph"),
        "delay_node": hasattr(cma, "DelayNode"),
        "practical_node_routing": False,
        "per_sound_filter_routing": False,
        "sound_groups": hasattr(cma, "SoundGroup"),
        "reverb": False,
        "auxiliary_sends": False,
        "custom_processing_nodes": hasattr(cma, "CustomNode"),
        "treatment_mode": "gain_fallback",
    }


def _empty_stats():
    return {
        "queued_events": 0, "accepted_events": 0, "discarded_events": 0,
        "discard_reasons": {}, "active_one_shot_voices": 0, "active_loop_voices": 0,
        "voice_steals": 0, "enemy_footstep_suppressions": 0,
        "listener_zone": 0, "listener_rain_state": "dry",
        "listener_tile_surface": "generic", "last_footstep_base_surface": None,
        "last_footstep_overlay": None, "current_ambience_set": None,
        "rain_loop_targets": {}, "nearest_fire_loop_sources": [],
        "nearest_sound_emitter_sources": [],
        "requested_treatment": {}, "actual_treatment": "gain_fallback",
        "missing_asset_families": [], "missing_asset_paths": [],
    }


def make_audio_runtime(engine=None, seed=4409):
    return {
        "engine": engine,
        "event_queue": [],
        "manifest": make_audio_manifest(),
        "loaded_assets": {},
        "voice_pools": {},
        "active_voices": [],
        "loop_voices": {},
        "shuffle_bags": {},
        "recent_variants": {},
        "cooldowns": {},
        "source_state": {},
        "listener": {},
        "buses": {},
        "missing_asset_warnings": set(),
        "missing_asset_path_warnings": set(),
        "rng": random.Random(seed),
        "seed": int(seed),
        "time": 0.0,
        "frame": 0,
        "muted": False,
        "capabilities": detect_audio_capabilities(),
        "stats": _empty_stats(),
    }


def ensure_audio_runtime(game_assets, engine):
    runtime = game_assets.get("audio_runtime")
    if not isinstance(runtime, dict) or runtime.get("engine") is not engine:
        if isinstance(runtime, dict):
            shutdown_audio_runtime(game_assets)
        runtime = make_audio_runtime(engine)
        game_assets["audio_runtime"] = runtime
    return runtime


def _safe_stop(sound, rewind=True):
    if sound is None:
        return
    try:
        sound.stop()
        if rewind:
            sound.seek(0)
    except Exception:
        pass


def _safe_close(sound):
    if sound is None:
        return
    _safe_stop(sound)
    try:
        sound.close()
    except Exception:
        pass


def shutdown_audio_runtime(game_assets):
    runtime = game_assets.get("audio_runtime")
    if not isinstance(runtime, dict):
        return
    seen = set()
    for pool in runtime.get("voice_pools", {}).values():
        for voice in pool.get("voices", []):
            sound = voice.get("sound")
            if sound is not None and id(sound) not in seen:
                seen.add(id(sound))
                _safe_close(sound)
    for loop in runtime.get("loop_voices", {}).values():
        sound = loop.get("sound")
        if sound is not None and id(sound) not in seen:
            seen.add(id(sound))
            _safe_close(sound)
    runtime.get("event_queue", []).clear()
    runtime.get("active_voices", []).clear()
    runtime.get("loop_voices", {}).clear()
    runtime.get("voice_pools", {}).clear()


def clear_audio_runtime(game_assets):
    shutdown_audio_runtime(game_assets)
    game_assets.pop("audio_runtime", None)


def _is_plain_data(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_plain_data(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, (str, int)) and _is_plain_data(item) for key, item in value.items())
    return False


def queue_audio_event(audio_runtime, event):
    if not isinstance(audio_runtime, dict) or not isinstance(event, dict):
        return False
    event_type = event.get("type")
    if event_type not in SUPPORTED_EVENT_TYPES or not _is_plain_data(event):
        return False
    if "world_position" in event and not isinstance(event["world_position"], dict):
        return False
    if "data" in event and not isinstance(event["data"], dict):
        return False
    try:
        numeric_fields = {
            key: float(event.get(key, default))
            for key, default in (
                ("priority", 1.0), ("gain", 1.0), ("pitch", 1.0),
                ("timestamp", audio_runtime.get("time", 0.0)),
            )
        }
        world_position = event.get("world_position")
        if world_position is not None:
            world_position = {
                "x": float(world_position.get("x", 0.0)),
                "y": float(world_position.get("y", 0.0)),
            }
    except (TypeError, ValueError, OverflowError):
        return False
    queued = copy.deepcopy(event)
    queued.setdefault("source_id", "unknown")
    queued.setdefault("source_kind", "world")
    queued.update(numeric_fields)
    if world_position is not None:
        queued["world_position"] = world_position
    queued.setdefault("data", {})
    audio_runtime.setdefault("event_queue", []).append(queued)
    return True


def distance_attenuation(listener_position, source_position, minimum_distance, maximum_distance):
    listener_position = listener_position or {}
    source_position = source_position or {}
    dx = float(source_position.get("x", 0.0)) - float(listener_position.get("x", 0.0))
    dy = float(source_position.get("y", 0.0)) - float(listener_position.get("y", 0.0))
    distance = math.hypot(dx, dy)
    minimum = max(0.0, float(minimum_distance))
    maximum = max(minimum + 0.000001, float(maximum_distance))
    if distance <= minimum:
        return 1.0
    if distance >= maximum:
        return 0.0
    t = (distance - minimum) / (maximum - minimum)
    smooth = t * t * (3.0 - 2.0 * t)
    return 1.0 - smooth


def stereo_pan(listener_position, source_position, pan_distance, maximum_pan):
    listener_position = listener_position or {}
    source_position = source_position or {}
    distance = max(0.000001, float(pan_distance))
    maximum = _clamp(maximum_pan, 0.0, 1.0)
    delta_x = float(source_position.get("x", 0.0)) - float(listener_position.get("x", 0.0))
    return _clamp(delta_x / distance, -maximum, maximum)


def _event_spatial_policy(event, profile):
    overrides = event.get("data", {}).get("spatial_policy", {})
    if not isinstance(overrides, dict):
        overrides = {}
    minimum = _clamp(
        overrides.get("minimum_distance", profile["minimum_distance"]),
        0.0, 10000.0,
    )
    maximum = max(
        minimum + 0.001,
        _clamp(
            overrides.get("maximum_distance", profile["maximum_distance"]),
            0.001, 10000.0,
        ),
    )
    return {
        "minimum_distance": minimum,
        "maximum_distance": maximum,
        "pan_distance": _clamp(
            overrides.get("pan_distance", profile["pan_distance"]),
            0.001, 10000.0,
        ),
        "maximum_pan": _clamp(
            overrides.get("maximum_pan", profile["maximum_pan"]), 0.0, 1.0,
        ),
    }


def estimate_event_audibility(event, listener, acoustic_context, audio_profile):
    if not isinstance(event, dict):
        return 0.0
    profile = normalize_audio_profile(audio_profile)
    if event.get("source_kind") == "ui" or event.get("type") == "ui_hover":
        attenuation = 1.0
    else:
        spatial_policy = _event_spatial_policy(event, profile)
        attenuation = distance_attenuation(
            (listener or {}).get("world_position", listener or {}),
            event.get("world_position", {}),
            spatial_policy["minimum_distance"], spatial_policy["maximum_distance"],
        )
    treatment = acoustic_context or {}
    return max(0.0, float(event.get("gain", 1.0))) * attenuation * max(
        0.0, float(treatment.get("direct_gain", 1.0))
    )


def _tile_coordinates(tile_map, world_position):
    if not isinstance(tile_map, dict) or not isinstance(world_position, dict):
        return None
    try:
        width = float(tile_map.get("tile_width", 16.0))
        height = float(tile_map.get("tile_height", 16.0))
        if width <= 0 or height <= 0:
            return None
        tile_x = math.floor(float(world_position.get("x", 0.0)) / width)
        tile_y = math.floor(float(world_position.get("y", 0.0)) / height)
        map_width = int(tile_map.get("map_width", 0))
        map_height = int(tile_map.get("map_height", 0))
        if tile_x < 0 or tile_y < 0 or tile_x >= map_width or tile_y >= map_height:
            return None
        index = tile_y * map_width + tile_x
        tiles = tile_map.get("tiles", [])
        if index < 0 or index >= len(tiles):
            return None
        return int(tile_x), int(tile_y), index, tiles[index]
    except (TypeError, ValueError, OverflowError):
        return None


def default_audio_surface_for_tile_type(tile_type_name):
    return {
        "wood": "wood", "grass": "grass", "stone": "stone",
        "blank_tile": "dirt", "carpet": "carpet", "door": "generic",
        "wall": "generic",
    }.get(str(tile_type_name or "").lower(), "generic")


def migrate_tile_audio_data(tile_map):
    if not isinstance(tile_map, dict):
        return tile_map
    tile_map.setdefault("acoustic_revision", 0)
    zones = tile_map.setdefault("acoustic_zones", make_default_acoustic_zones())
    if not isinstance(zones, dict):
        tile_map["acoustic_zones"] = make_default_acoustic_zones()
    else:
        defaults = make_default_acoustic_zones()
        for zone_id, definition in defaults.items():
            zones.setdefault(zone_id, copy.deepcopy(definition))
    try:
        surface_schema_revision = int(tile_map.get("audio_surface_schema_revision", 0))
    except (TypeError, ValueError, OverflowError):
        surface_schema_revision = 0
    for tile_type in tile_map.get("tile_types", []):
        if not isinstance(tile_type, dict):
            continue
        tile_type_name = str(tile_type.get("type", "")).lower()
        surface = tile_type.get("audio_surface")
        if surface_schema_revision < 1:
            legacy_surface = {"carpet": "generic", "stone": "tile"}.get(tile_type_name)
            if surface == legacy_surface:
                surface = default_audio_surface_for_tile_type(tile_type_name)
                tile_type["audio_surface"] = surface
        if surface not in AUDIO_SURFACES:
            tile_type["audio_surface"] = default_audio_surface_for_tile_type(tile_type_name)
    tile_map["audio_surface_schema_revision"] = AUDIO_SURFACE_SCHEMA_REVISION
    return tile_map


def get_tile_audio_surface(tile_map, world_position):
    tile_info = _tile_coordinates(tile_map, world_position)
    if tile_info is None:
        return "generic"
    tile = tile_info[3]
    if not isinstance(tile, dict):
        return "generic"
    try:
        tile_type = tile_map.get("tile_types", [])[int(tile.get("index", 0))]
    except (IndexError, TypeError, ValueError):
        return "generic"
    if not isinstance(tile_type, dict):
        return "generic"
    surface = tile_type.get("audio_surface")
    if surface in AUDIO_SURFACES:
        return surface
    fallback = default_audio_surface_for_tile_type(tile_type.get("type"))
    return fallback if fallback in AUDIO_SURFACES else "generic"


def get_acoustic_zone_at_world_position(tile_map, world_position):
    tile_info = _tile_coordinates(tile_map, world_position)
    if tile_info is None or not isinstance(tile_info[3], dict):
        return 0
    try:
        zone_id = max(0, int(tile_info[3].get("acoustic_zone_id", 0)))
    except (TypeError, ValueError):
        return 0
    zones = tile_map.get("acoustic_zones", {})
    if not isinstance(zones, dict) or (
        zone_id not in zones and str(zone_id) not in zones
    ):
        return 0
    return zone_id


def get_acoustic_zone_definition(tile_map, zone_id):
    defaults = make_default_acoustic_zones()
    zones = tile_map.get("acoustic_zones", {}) if isinstance(tile_map, dict) else {}
    try:
        zone_id = max(0, int(zone_id))
    except (TypeError, ValueError):
        zone_id = 0
    resolved_id = zone_id
    definition = zones.get(zone_id, zones.get(str(zone_id))) if isinstance(zones, dict) else None
    if not isinstance(definition, dict):
        resolved_id = 0
        definition = zones.get(0, zones.get("0")) if isinstance(zones, dict) else None
    if not isinstance(definition, dict):
        resolved_id = 0
        definition = defaults[0]
    result = copy.deepcopy(defaults.get(resolved_id, defaults[0]))
    result.update(copy.deepcopy(definition))
    result["id"] = resolved_id
    return result


def resolve_source_listener_acoustic_context(source_position, listener_position, tile_map):
    source_zone_id = get_acoustic_zone_at_world_position(tile_map, source_position)
    listener_zone_id = get_acoustic_zone_at_world_position(tile_map, listener_position)
    source_zone = get_acoustic_zone_definition(tile_map, source_zone_id)
    listener_zone = get_acoustic_zone_definition(tile_map, listener_zone_id)
    same_zone = source_zone_id == listener_zone_id
    source_environment = source_zone.get("environment", "open_exterior")
    listener_environment = listener_zone.get("environment", "open_exterior")
    direct_gain = 1.0 if same_zone else 0.62
    low_pass_hz = None if same_zone else 3200.0
    transmission = "clear" if same_zone else "different_zone"
    if source_environment in OUTDOOR_ENVIRONMENTS and listener_environment in INTERIOR_ENVIRONMENTS:
        direct_gain = 0.48
        low_pass_hz = 1900.0
        transmission = "outdoor_to_indoor"
    elif source_environment in INTERIOR_ENVIRONMENTS and listener_environment in OUTDOOR_ENVIRONMENTS:
        direct_gain = 0.58
        low_pass_hz = 2600.0
        transmission = "indoor_to_outdoor"
    return {
        "source_zone_id": source_zone_id,
        "listener_zone_id": listener_zone_id,
        "source_zone": source_zone,
        "listener_zone": listener_zone,
        "same_zone": same_zone,
        "transmission": transmission,
        "direct_gain": direct_gain,
        "low_pass_hz": low_pass_hz,
        "wet_send": _clamp(listener_zone.get("wet_send", 0.0), 0.0, 1.0),
        "reverb_preset": listener_zone.get("reverb_preset", "exterior"),
        "tail_family": None if same_zone else listener_zone.get("ambience_set"),
        "muffled_weather": listener_environment in INTERIOR_ENVIRONMENTS,
        "portal_policy": "future_explicit_portals",
    }


def set_tile_acoustic_zone(tile, zone_id):
    if not isinstance(tile, dict):
        return False
    try:
        zone_id = max(0, int(zone_id))
    except (TypeError, ValueError):
        zone_id = 0
    old = get_tile_acoustic_zone(tile)
    if old == zone_id and (zone_id != 0 or "acoustic_zone_id" not in tile):
        return False
    if zone_id == 0:
        tile.pop("acoustic_zone_id", None)
    else:
        tile["acoustic_zone_id"] = zone_id
    return True


def get_tile_acoustic_zone(tile):
    if not isinstance(tile, dict):
        return 0
    try:
        return max(0, int(tile.get("acoustic_zone_id", 0)))
    except (TypeError, ValueError):
        return 0


def mark_acoustic_dirty(tile_map):
    tile_map["acoustic_revision"] = int(tile_map.get("acoustic_revision", 0)) + 1
    return tile_map["acoustic_revision"]


def set_tile_footstep_overlay(tile, overlay):
    if not isinstance(tile, dict):
        return False
    overlay = str(overlay or "none").lower()
    overlay = overlay if overlay in FOOTSTEP_OVERLAYS else "none"
    old = str(tile.get("footstep_overlay", "none")).lower()
    old = old if old in FOOTSTEP_OVERLAYS else "none"
    if old == overlay and (overlay != "none" or "footstep_overlay" not in tile):
        return False
    if overlay == "none":
        tile.pop("footstep_overlay", None)
    else:
        tile["footstep_overlay"] = overlay
    return True


def _flood_fill_property(tile_map, start_x, start_y, getter, setter, target, mark_dirty=None):
    width = int(tile_map.get("map_width", 0))
    height = int(tile_map.get("map_height", 0))
    if start_x < 0 or start_y < 0 or start_x >= width or start_y >= height:
        return 0
    tiles = tile_map.get("tiles", [])
    start_index = start_y * width + start_x
    if start_index >= len(tiles):
        return 0
    initial = getter(tiles[start_index])
    if initial == target:
        return 0
    changed = 0
    stack = [(start_x, start_y)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or x < 0 or y < 0 or x >= width or y >= height:
            continue
        seen.add((x, y))
        index = y * width + x
        if index >= len(tiles) or getter(tiles[index]) != initial:
            continue
        if setter(tiles[index], target):
            changed += 1
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    if changed and mark_dirty is not None:
        mark_dirty(tile_map)
    return changed


def flood_fill_acoustic_zone(tile_map, start_x, start_y, target_zone_id):
    try:
        target_zone_id = max(0, int(target_zone_id))
    except (TypeError, ValueError):
        target_zone_id = 0
    return _flood_fill_property(
        tile_map, start_x, start_y, get_tile_acoustic_zone,
        set_tile_acoustic_zone, target_zone_id, mark_acoustic_dirty,
    )


def _get_tile_overlay(tile):
    overlay = str(tile.get("footstep_overlay", "none")).lower() if isinstance(tile, dict) else "none"
    return overlay if overlay in FOOTSTEP_OVERLAYS else "none"


def flood_fill_footstep_overlay(tile_map, start_x, start_y, target_overlay):
    target_overlay = str(target_overlay or "none").lower()
    target_overlay = target_overlay if target_overlay in FOOTSTEP_OVERLAYS else "none"
    return _flood_fill_property(
        tile_map, start_x, start_y, _get_tile_overlay,
        set_tile_footstep_overlay, target_overlay, None,
    )


def _entity_world_position(entity, tile_map):
    position = entity.get("position", {}) if isinstance(entity, dict) else {}
    return {
        "x": float(position.get("tile_x", 0)) * float(tile_map.get("tile_width", 16.0)) + float(position.get("x", 0.0)),
        "y": float(position.get("tile_y", 0)) * float(tile_map.get("tile_height", 16.0)) + float(position.get("y", 0.0)),
    }


def get_corpse_contact_footprint(entity, tile_map):
    entity_type = str(entity.get("type", "")).lower().replace("_", " ")
    if entity_type != "red head":
        return None
    if not (entity.get("dead") is True or str(entity.get("current_state", "")).lower() == "dead"):
        return None
    centre = _entity_world_position(entity, tile_map)
    footprint = entity.get("audio_contact_footprint") or entity.get("ground_footprint") or {}
    offset = footprint.get("offset", {}) if isinstance(footprint, dict) else {}
    size = footprint.get("size", {}) if isinstance(footprint, dict) else {}
    centre_x = centre["x"] + float(offset.get("x", 0.0))
    centre_y = centre["y"] + float(offset.get("y", 0.0))
    width = max(1.0, float(size.get("x", 14.0)))
    height = max(1.0, float(size.get("y", 8.0)))
    return {"x": centre_x, "y": centre_y, "width": width, "height": height}


def _point_in_corpse_contact(world_position, entity, tile_map):
    footprint = get_corpse_contact_footprint(entity, tile_map)
    if footprint is None:
        return False
    return (
        abs(float(world_position.get("x", 0.0)) - footprint["x"]) <= footprint["width"] * 0.5
        and abs(float(world_position.get("y", 0.0)) - footprint["y"]) <= footprint["height"] * 0.5
    )


def resolve_footstep_contact(world_position, tile_map, entities):
    base_surface = get_tile_audio_surface(tile_map, world_position)
    overlay = None
    overlay_source_id = None
    tile_info = _tile_coordinates(tile_map, world_position)
    if tile_info is not None and isinstance(tile_info[3], dict):
        tile = tile_info[3]
        if _get_tile_overlay(tile) == "puddle" or any(
            isinstance(decal, dict) and decal.get("type") == "puddle"
            for decal in tile.get("decals", [])
        ):
            overlay = "puddle"
    brains = entities.get("brains", {}) if isinstance(entities, dict) else {}
    for entity_id, entity in brains.items():
        if isinstance(entity, dict) and _point_in_corpse_contact(world_position, entity, tile_map):
            overlay = "corpse"
            overlay_source_id = str(entity_id)
            break
    strength = {None: 0.0, "puddle": 0.8, "corpse": 1.0}[overlay]
    return {
        "base_surface": base_surface,
        "overlay": overlay,
        "overlay_strength": strength,
        "overlay_source_id": overlay_source_id,
    }


def update_actor_footstep_travel(actor, current_world_position, stride_distance,
                                 source_id, source_kind, audio_runtime=None,
                                 priority=1.0, gait="walk"):
    """Accumulate collision-resolved travel and return newly crossed step events."""
    state = actor.setdefault("audio_step_state", {})
    stride = max(1.0, float(stride_distance))
    previous_stride = max(1.0, float(state.get("stride_distance", stride)))
    if abs(previous_stride - stride) > 0.000001:
        # Preserve progress through the current step when changing gait. This
        # keeps the procedural pose continuous across walk/run transitions.
        state["distance"] = (
            max(0.0, float(state.get("distance", 0.0)))
            * stride / previous_stride
        )
    state["stride_distance"] = stride
    current = {"x": float(current_world_position.get("x", 0.0)),
               "y": float(current_world_position.get("y", 0.0))}
    previous = state.get("previous_world_position")
    state["previous_world_position"] = current
    if not isinstance(previous, dict):
        state.setdefault("distance", 0.0)
        state.setdefault("stride_index", 0)
        return []
    travelled = math.hypot(current["x"] - float(previous.get("x", current["x"])),
                           current["y"] - float(previous.get("y", current["y"])))
    accumulated = max(0.0, float(state.get("distance", 0.0))) + travelled
    events = []
    while accumulated >= stride and len(events) < 3:
        accumulated -= stride
        stride_index = int(state.get("stride_index", 0)) + 1
        state["stride_index"] = stride_index
        event = {
            "type": "footstep", "source_id": str(source_id),
            "source_kind": str(source_kind), "world_position": dict(current),
            "priority": float(priority), "gain": 1.0,
            "data": {"gait": str(gait), "stride_index": stride_index,
                     "speed": travelled},
        }
        events.append(event)
        if audio_runtime is not None:
            queue_audio_event(audio_runtime, event)
    state["distance"] = accumulated
    return events


def select_shuffle_bag_variant(state, family, variants, rng=None):
    variants = list(dict.fromkeys(variants))
    if not variants:
        return None
    rng = rng or random
    bags = state.setdefault("shuffle_bags", {})
    recent = state.setdefault("recent_variants", {})
    bag = bags.get(family, [])
    if not bag:
        bag = list(variants)
        rng.shuffle(bag)
        previous = recent.get(family)
        if len(bag) > 1 and bag[-1] == previous:
            bag[0], bag[-1] = bag[-1], bag[0]
        bags[family] = bag
    selected = bag.pop()
    recent[family] = selected
    return selected


def _resolve_family_path_set(runtime, family, variant_field, fallback_field=None):
    cache = runtime.setdefault("loaded_assets", {})
    cache_key = family if variant_field == "variants" else f"{family}:{variant_field}"
    if cache_key in cache:
        return list(cache[cache_key].get("paths", []))
    definition = get_family_definition(runtime.get("manifest", {}), family)
    if definition is None:
        cache[cache_key] = {"paths": [], "missing": True}
        return []
    variants = [path for path in definition.get(variant_field, []) if path]
    paths = [path for path in variants if os.path.isfile(path)]
    missing_paths = runtime.setdefault("missing_asset_path_warnings", set())
    for path in variants:
        if not os.path.isfile(path) and path not in missing_paths:
            missing_paths.add(path)
            print(f"audio variant unavailable: {path} ({family})")
    fallback = definition.get(fallback_field) if fallback_field else None
    if not paths and fallback and os.path.isfile(fallback):
        paths = [fallback]
    missing = not paths
    cache[cache_key] = {"paths": list(paths), "missing": missing}
    if missing and variant_field == "variants":
        warnings = runtime.setdefault("missing_asset_warnings", set())
        if family not in warnings:
            warnings.add(family)
            if not definition.get("optional", False):
                print(f"audio family unavailable: {family}")
    return paths


def resolve_available_family_paths(runtime, family):
    return _resolve_family_path_set(runtime, family, "variants", "fallback")


def resolve_available_muffled_family_paths(runtime, family):
    """Return prepared muffled variants only; a dry fallback is never relabelled."""
    return _resolve_family_path_set(runtime, family, "muffled_variants")


def choose_voice_to_steal(active_voices, incoming):
    incoming_priority = float(incoming.get("priority", 0.0))
    incoming_type = incoming.get("event_type")
    candidates = []
    for index, voice in enumerate(active_voices):
        if voice.get("looping", False):
            continue
        existing_type = voice.get("event_type")
        existing_kind = voice.get("source_kind")
        if existing_kind == "ui" and incoming_kind_is_low_priority(incoming):
            continue
        if existing_type == "gunshot" and voice.get("source_kind") == "player" and incoming_type == "footstep":
            continue
        existing_priority = float(voice.get("priority", 0.0))
        if incoming_priority <= existing_priority:
            continue
        score = existing_priority * 2.0 + float(voice.get("estimated_gain", 0.0))
        candidates.append((score, float(voice.get("started_at", 0.0)), index))
    return min(candidates)[2] if candidates else None


def incoming_kind_is_low_priority(incoming):
    return incoming.get("event_type") in {"footstep", "fire_crackle"} or float(incoming.get("priority", 0.0)) < 1.0


def _sound_is_playing(sound):
    try:
        return bool(sound.is_playing)
    except Exception:
        try:
            return not bool(sound.at_end)
        except Exception:
            return False


def _make_sound(engine, path, looping=False):
    sound = cma.Sound(engine, path)
    sound.looping = bool(looping)
    try:
        sound.spatialization_enabled = False
    except Exception:
        pass
    return sound


def _retire_finished_voices(runtime):
    active = []
    seen = set()
    for metadata in runtime.get("active_voices", []):
        sound = metadata.get("sound")
        if id(metadata) in seen:
            continue
        seen.add(id(metadata))
        if sound is not None and _sound_is_playing(sound):
            active.append(metadata)
        else:
            metadata["active"] = False
    runtime["active_voices"] = active


def _allocate_one_shot(runtime, family, path, incoming, definition):
    pool = runtime.setdefault("voice_pools", {}).setdefault(
        family, {"family": family, "voice_count": max(1, int(definition.get("voice_count", 4))), "voices": []}
    )
    voices = pool["voices"]
    selected = None
    for voice in voices:
        if not voice.get("active", False) or not _sound_is_playing(voice.get("sound")):
            selected = voice
            break
    if selected is None and len(voices) < pool["voice_count"]:
        selected = {"sound": None, "path": None, "active": False}
        voices.append(selected)
    if selected is None:
        steal_index = choose_voice_to_steal(voices, incoming)
        if steal_index is None:
            return None
        selected = voices[steal_index]
        _safe_stop(selected.get("sound"))
        runtime["stats"]["voice_steals"] += 1
    # A pooled metadata dictionary can be reused more than once in one frame.
    # Remove its prior active registration before the caller appends the newly
    # configured playback, otherwise voice counts and retirement see duplicates.
    runtime["active_voices"] = [
        voice for voice in runtime.get("active_voices", []) if voice is not selected
    ]
    if selected.get("path") != path or selected.get("sound") is None:
        _safe_close(selected.get("sound"))
        try:
            selected["sound"] = _make_sound(runtime.get("engine"), path, False)
            selected["path"] = path
        except Exception:
            selected["sound"] = None
            return None
    selected.update(incoming)
    selected["family"] = family
    selected["path"] = path
    selected["active"] = True
    selected["looping"] = False
    selected["sound"] = selected["sound"]
    return selected


def _bus_gain(profile, bus):
    mapping = {
        "footsteps": "footstep_gain", "weapons": "weapon_gain",
        "ambience": "ambience_gain", "weather": "weather_gain", "UI": "ui_gain",
        "sfx": "sfx_gain",
    }
    return float(profile.get(mapping.get(bus, "sfx_gain"), 1.0))


def _event_pitch_variation(profile, event, definition):
    policy = profile.get("pitch_variation", {})
    if event.get("type") == "footstep":
        key = "enemy_footstep" if event.get("source_kind") == "enemy" else "player_footstep"
        return float(policy.get(key, definition.get("pitch_variation", 0.0)))
    if event.get("type") in {
        "bullet_wall_impact", "melee_whoosh", "stagger_impact", "death_impact",
    }:
        return float(policy.get("impact", definition.get("pitch_variation", 0.0)))
    return float(definition.get("pitch_variation", 0.0))


def _play_family_layer(runtime, family, event, listener, context, profile, layer_gain=1.0,
                       used_paths=None, instance_key=None):
    definition = get_family_definition(runtime.get("manifest", {}), family)
    if definition is None:
        return None
    requested_low_pass = context.get("low_pass_hz")
    muffled_paths = (
        resolve_available_muffled_family_paths(runtime, family)
        if requested_low_pass is not None else []
    )
    use_prepared_muffled = bool(muffled_paths)
    paths = muffled_paths or resolve_available_family_paths(runtime, family)
    if not paths:
        return None
    selection_family = f"{family}:muffled" if use_prepared_muffled else family
    path = select_shuffle_bag_variant(runtime, selection_family, paths, runtime.get("rng"))
    if used_paths is not None and path in used_paths:
        return None
    if used_paths is not None:
        used_paths.add(path)
    spatial = bool(definition.get("spatial", True)) and event.get("source_kind") != "ui"
    attenuation = 1.0
    pan = 0.0
    if spatial:
        spatial_policy = _event_spatial_policy(event, profile)
        attenuation = distance_attenuation(
            listener.get("world_position", {}), event.get("world_position", {}),
            spatial_policy["minimum_distance"], spatial_policy["maximum_distance"],
        )
        pan = stereo_pan(
            listener.get("world_position", {}), event.get("world_position", {}),
            spatial_policy["pan_distance"], spatial_policy["maximum_pan"],
        )
        if event.get("source_kind") == "player":
            pan *= 0.35
    direct_gain = float(context.get("direct_gain", 1.0))
    if (requested_low_pass is not None and not use_prepared_muffled
            and not runtime["capabilities"].get("per_sound_filter_routing", False)):
        direct_gain *= 0.82
    gain = (
        float(event.get("gain", 1.0)) * float(layer_gain)
        * float(definition.get("base_gain", 1.0)) * attenuation * direct_gain
        * profile["master_gain"] * _bus_gain(profile, definition.get("bus", "sfx"))
    )
    if runtime.get("muted", False):
        gain = 0.0
    variation = _event_pitch_variation(profile, event, definition)
    pitch = max(0.1, float(event.get("pitch", 1.0)) * (1.0 + runtime["rng"].uniform(-variation, variation)))
    incoming = {
        "source_id": event.get("source_id"), "source_kind": event.get("source_kind"),
        "event_type": event.get("type"), "priority": float(event.get("priority", 1.0)),
        "estimated_gain": gain, "started_at": runtime["time"],
        "instance_key": instance_key,
        "world_position": copy.deepcopy(event.get("world_position")),
    }
    voice = _allocate_one_shot(runtime, family, path, incoming, definition)
    if voice is None:
        return None
    sound = voice["sound"]
    try:
        sound.volume = max(0.0, gain)
        sound.pitch = pitch
        sound.pan = _clamp(pan, -1.0, 1.0)
        sound.looping = False
        sound.stop()
        try:
            sample_frames = max(0, int(getattr(sound, "length", 0)))
        except (TypeError, ValueError, OverflowError):
            sample_frames = 0
        start_fraction = _clamp(
            event.get("data", {}).get("start_fraction", 0.0), 0.0, 1.0,
        )
        seek_frame = 0
        if sample_frames > 0:
            seek_frame = min(
                sample_frames - 1,
                int(round(start_fraction * sample_frames)),
            )
        sound.seek(seek_frame)
        sound.start()
    except Exception:
        voice["active"] = False
        return None
    runtime.setdefault("active_voices", []).append(voice)
    voice["start_fraction"] = start_fraction
    voice["seek_frame"] = seek_frame
    runtime["stats"]["requested_treatment"] = {
        "low_pass_hz": context.get("low_pass_hz"),
        "wet_send": context.get("wet_send"),
        "reverb_preset": context.get("reverb_preset"),
    }
    return voice


def _discard(stats, reason, count=1):
    stats["discarded_events"] += count
    reasons = stats.setdefault("discard_reasons", {})
    reasons[reason] = reasons.get(reason, 0) + count


def arbitrate_enemy_footsteps(events, runtime, listener, tile_map, profile):
    if not events:
        return []
    stats = runtime["stats"]
    last = float(runtime.setdefault("cooldowns", {}).get("enemy_footstep_group", -1000000.0))
    if runtime["time"] - last < profile["enemy_footstep_group_spacing"]:
        _discard(stats, "enemy_group_spacing", len(events))
        stats["enemy_footstep_suppressions"] += len(events)
        return []
    active_sources = {
        voice.get("source_id") for voice in runtime.get("active_voices", [])
        if voice.get("event_type") == "footstep" and voice.get("source_kind") == "enemy"
    }
    capacity = max(0, profile["enemy_footstep_voice_limit"] - len(active_sources))
    if capacity <= 0:
        _discard(stats, "enemy_voice_limit", len(events))
        stats["enemy_footstep_suppressions"] += len(events)
        return []
    scored = []
    for event in events:
        context = resolve_source_listener_acoustic_context(
            event.get("world_position", {}), listener.get("world_position", {}), tile_map
        )
        audible = estimate_event_audibility(event, listener, context, profile)
        threat = float(event.get("data", {}).get("threat", 1.0))
        score = audible * max(0.0, float(event.get("priority", 1.0))) * max(0.1, threat)
        if audible < AUDIBILITY_EPSILON:
            _discard(stats, "inaudible_enemy_footstep")
            stats["enemy_footstep_suppressions"] += 1
        else:
            scored.append((score, str(event.get("source_id", "")), event))
    scored.sort(key=lambda item: (-item[0], item[1]))
    limit = min(capacity, profile["enemy_footsteps_per_frame"])
    accepted = [item[2] for item in scored[:limit]]
    rejected = max(0, len(scored) - len(accepted))
    if rejected:
        _discard(stats, "enemy_per_frame_limit", rejected)
        stats["enemy_footstep_suppressions"] += rejected
    if accepted:
        runtime["cooldowns"]["enemy_footstep_group"] = runtime["time"]
    return accepted


def _process_footstep(runtime, event, listener, tile_map, entities, profile):
    contact = resolve_footstep_contact(event.get("world_position", {}), tile_map, entities)
    event["data"] = dict(event.get("data", {}))
    event["data"]["contact"] = contact
    runtime["stats"]["last_footstep_base_surface"] = contact["base_surface"]
    runtime["stats"]["last_footstep_overlay"] = contact["overlay"]
    context = resolve_source_listener_acoustic_context(
        event.get("world_position", {}), listener.get("world_position", {}), tile_map
    )
    source_kind = "enemy_contact" if event.get("source_kind") == "enemy" else "player"
    family = f"footsteps.{source_kind}.{contact['base_surface']}"
    mix_name = contact["overlay"] or "none"
    mix = runtime.get("manifest", {}).get("footstep_mix", {}).get(
        mix_name, {"base": 1.0, "overlay": 0.0},
    )
    base_gain = float(mix.get("base", 1.0))
    used_paths = set()
    voices = []
    voice = _play_family_layer(runtime, family, event, listener, context, profile, base_gain, used_paths)
    if voice is not None:
        voices.append(voice)
    if event.get("source_kind") == "enemy":
        identity = _play_family_layer(
            runtime, "footsteps.enemy_body", event, listener, context, profile, 1.0, used_paths
        )
        if identity is not None:
            voices.append(identity)
    if contact["overlay"]:
        overlay = _play_family_layer(
            runtime, f"footstep_overlays.{contact['overlay']}", event,
            listener, context, profile, float(mix.get("overlay", 0.0)), used_paths,
        )
        if overlay is not None:
            voices.append(overlay)
    return voices


def _stop_instance(runtime, instance_key):
    stopped = 0
    for voice in runtime.get("active_voices", []):
        if voice.get("instance_key") == instance_key:
            _safe_stop(voice.get("sound"))
            voice["active"] = False
            stopped += 1
    runtime["active_voices"] = [voice for voice in runtime.get("active_voices", []) if voice.get("active", False)]
    return stopped


def _process_event(runtime, event, listener, tile_map, entities, profile):
    context = resolve_source_listener_acoustic_context(
        event.get("world_position", listener.get("world_position", {})),
        listener.get("world_position", {}), tile_map,
    )
    audible = estimate_event_audibility(event, listener, context, profile)
    if event.get("type") not in CONTROL_EVENT_TYPES and audible < AUDIBILITY_EPSILON:
        _discard(runtime["stats"], "inaudible")
        return []
    event_type = event.get("type")
    if event_type == "footstep":
        return _process_footstep(runtime, event, listener, tile_map, entities, profile)
    if event_type in CONTROL_EVENT_TYPES:
        default_key = "player:pistol_reload" if event_type == "reload_stop" else ""
        _stop_instance(
            runtime, event.get("data", {}).get("instance_key", default_key),
        )
        return []
    family_map = {
        "reload_start": "weapons.pistol_reload", "weapon_empty": "weapons.pistol_empty",
        "weapon_unholster": "weapons.pistol_unholster",
        "weapon_holster": "weapons.pistol_holster",
        "flashlight_click": "equipment.flashlight_click",
        "bullet_wall_impact": "impacts.bullet_wall", "melee_whoosh": "impacts.melee_whoosh",
        "stagger_impact": "impacts.stagger", "death_impact": "impacts.death",
        "pickup_ammo": "pickups.ammo", "pickup_health": "pickups.health",
        "ui_hover": "ui.hover", "fire_crackle": "fire.fire_crackle",
        "redhead_startle": "barks.redhead.startle",
        "redhead_pursuit_hiss": "barks.redhead.pursuit_hiss",
        "redhead_evade": "barks.redhead.evade",
    }
    if event_type == "bullet_wall_impact":
        material = str(
            event.get("data", {}).get("material", "stone")
        ).lower()
        if material not in BULLET_IMPACT_MATERIALS:
            material = "stone"
        family_map[event_type] = f"impacts.bullet_wall_{material}"
        event = dict(event)
        event["pitch"] = float(event.get("pitch", 1.0)) * {
            "wood": 0.90,
            "stone": 1.0,
            "metal": 1.14,
        }[material]
    if event_type == "ambience_incidental":
        environment = str(event.get("data", {}).get("environment", "open_exterior"))
        family_map[event_type] = f"ambience.{environment}.incidental"
    if event_type == "sound_emitter_cadence":
        emitter_family = str(event.get("data", {}).get("family", "bells"))
        if emitter_family in SOUND_EMITTER_FAMILIES:
            family_map[event_type] = f"sound_emitters.{emitter_family}"
    if event_type == "gunshot":
        used_paths = set()
        voices = []
        dry = _play_family_layer(runtime, "weapons.pistol_shot", event, listener, context, profile, 1.0, used_paths)
        if dry is not None:
            voices.append(dry)
        mechanical = _play_family_layer(runtime, "weapons.pistol_mechanical", event, listener, context, profile, 1.0, used_paths)
        if mechanical is not None:
            voices.append(mechanical)
        environment = context["listener_zone"].get("environment", "open_exterior")
        tail_family = "weapons.large_hall_tail" if environment in {"large_interior", "stone_hall"} else "weapons.small_room_tail" if environment in {"small_interior", "medium_interior"} else None
        if tail_family:
            tail = _play_family_layer(runtime, tail_family, event, listener, context, profile, context["wet_send"], used_paths)
            if tail is not None:
                voices.append(tail)
        return voices
    family = family_map.get(event_type)
    if family is None:
        return []
    instance_key = event.get("data", {}).get("instance_key")
    if instance_key:
        _stop_instance(runtime, instance_key)
    voice = _play_family_layer(runtime, family, event, listener, context, profile, 1.0, set(), instance_key)
    return [voice] if voice is not None else []


def request_loop(runtime, key, family, target_gain, world_position=None, spatial=False,
                 treatment=None, spatial_policy=None):
    loops = runtime.setdefault("loop_voices", {})
    loop = loops.get(key)
    if loop is None and float(target_gain) <= 0.0:
        return None
    if loop is None:
        loop = {
            "key": key, "family": family, "sound": None, "path": None,
            "current_gain": 0.0, "target_gain": 0.0, "world_position": None,
            "spatial": bool(spatial), "treatment": {}, "spatial_policy": {},
            "last_requested_frame": -1,
            "start_count": 0,
        }
        loops[key] = loop
    loop["family"] = family
    loop["target_gain"] = max(0.0, float(target_gain))
    loop["world_position"] = copy.deepcopy(world_position) if world_position is not None else None
    loop["spatial"] = bool(spatial)
    loop["treatment"] = copy.deepcopy(treatment or {})
    loop["spatial_policy"] = copy.deepcopy(spatial_policy or {})
    loop["last_requested_frame"] = runtime.get("frame", 0)
    return loop


def _approach(current, target, dt, seconds):
    if current == target:
        return target
    step = max(0.0, float(dt)) / max(0.001, float(seconds))
    if current < target:
        return min(target, current + step)
    return max(target, current - step)


def update_loop_voices(runtime, dt, listener, profile):
    remove = []
    for key, loop in list(runtime.setdefault("loop_voices", {}).items()):
        if loop.get("last_requested_frame") != runtime.get("frame"):
            loop["target_gain"] = 0.0
        duration = profile["loop_attack_seconds"] if loop["target_gain"] > loop["current_gain"] else profile["loop_release_seconds"]
        loop["current_gain"] = _approach(loop["current_gain"], loop["target_gain"], dt, duration)
        treatment = loop.get("treatment", {})
        muffled_paths = (
            resolve_available_muffled_family_paths(runtime, loop["family"])
            if treatment.get("low_pass_hz") is not None else []
        )
        paths = muffled_paths or resolve_available_family_paths(runtime, loop["family"])
        if loop["sound"] is None and paths and loop["current_gain"] > AUDIBILITY_EPSILON:
            path = paths[0]
            try:
                loop["sound"] = _make_sound(runtime.get("engine"), path, True)
                loop["path"] = path
                loop["sound"].start()
                loop["start_count"] += 1
            except Exception:
                loop["sound"] = None
        sound = loop.get("sound")
        if sound is not None:
            gain = loop["current_gain"] * profile["master_gain"]
            definition = get_family_definition(runtime["manifest"], loop["family"]) or {}
            gain *= float(definition.get("base_gain", 1.0))
            gain *= _bus_gain(profile, definition.get("bus", "ambience"))
            pan = 0.0
            if loop.get("spatial") and loop.get("world_position"):
                spatial_policy = loop.get("spatial_policy", {})
                minimum_distance = spatial_policy.get(
                    "minimum_distance", profile["minimum_distance"],
                )
                maximum_distance = spatial_policy.get(
                    "maximum_distance", profile["maximum_distance"],
                )
                gain *= distance_attenuation(
                    listener.get("world_position", {}), loop["world_position"],
                    minimum_distance, maximum_distance,
                )
                pan = stereo_pan(
                    listener.get("world_position", {}), loop["world_position"],
                    spatial_policy.get("pan_distance", profile["pan_distance"]),
                    spatial_policy.get("maximum_pan", profile["maximum_pan"]),
                )
                gain *= max(0.0, float(treatment.get("direct_gain", 1.0)))
                if (treatment.get("low_pass_hz") is not None
                        and not muffled_paths
                        and not runtime["capabilities"].get("per_sound_filter_routing", False)):
                    gain *= 0.82
            if runtime.get("muted", False):
                gain = 0.0
            try:
                sound.volume = max(0.0, gain)
                sound.pan = pan
            except Exception:
                pass
        if loop["target_gain"] <= 0.0 and loop["current_gain"] <= AUDIBILITY_EPSILON:
            _safe_close(loop.get("sound"))
            remove.append(key)
    for key in remove:
        runtime["loop_voices"].pop(key, None)


def resolve_listener_rain_state(listener_position, tile_map, rain_profile):
    if not isinstance(rain_profile, dict) or not rain_profile.get("enabled", False):
        return "dry", {"rain_open_body": 0.0, "rain_open_detail": 0.0, "rain_roof": 0.0, "rain_muffled": 0.0}
    tile_info = _tile_coordinates(tile_map, listener_position)
    exposure = 0.0
    if tile_info is not None and isinstance(tile_info[3], dict):
        try:
            exposure = _clamp(tile_info[3].get("rain_exposure", 0.0), 0.0, 1.0)
        except (TypeError, ValueError):
            exposure = 0.0
    zone_id = get_acoustic_zone_at_world_position(tile_map, listener_position)
    environment = get_acoustic_zone_definition(tile_map, zone_id).get("environment", "open_exterior")
    if exposure > 0.01 and environment in OUTDOOR_ENVIRONMENTS:
        return "exposed_outdoor", {"rain_open_body": exposure, "rain_open_detail": 0.55 * exposure, "rain_roof": 0.05, "rain_muffled": 0.0}
    if environment in INTERIOR_ENVIRONMENTS:
        return "indoors", {"rain_open_body": 0.10, "rain_open_detail": 0.0, "rain_roof": 0.20, "rain_muffled": 0.85}
    return "covered_exterior", {"rain_open_body": 0.35, "rain_open_detail": 0.08, "rain_roof": 0.85, "rain_muffled": 0.18}


def _request_sound_emitters(runtime, listener_position, tile_map, entities):
    sound_emitters = entities.get("sound_emitters", {}) if isinstance(entities, dict) else {}
    migrate_sound_emitters(sound_emitters)
    sources = []
    for emitter_id, emitter in sound_emitters.items():
        if not isinstance(emitter, dict) or not emitter.get("enabled", True):
            continue
        position = _entity_world_position(emitter, tile_map)
        context = resolve_source_listener_acoustic_context(
            position, listener_position, tile_map,
        )
        spatial_policy = sound_emitter_spatial_policy(emitter)
        family_name = emitter["family"]
        source_key = f"sound_emitter:{emitter_id}"
        distance = math.hypot(
            position["x"] - float(listener_position.get("x", 0.0)),
            position["y"] - float(listener_position.get("y", 0.0)),
        )
        sources.append({
            "id": str(emitter_id), "family": family_name,
            "mode": emitter["playback_mode"], "distance": distance,
            "position": position,
        })
        if emitter["playback_mode"] == "loop":
            request_loop(
                runtime, f"{source_key}:loop", f"sound_emitters.{family_name}",
                emitter["gain"], position, True, context, spatial_policy,
            )
            continue
        state = runtime.setdefault("source_state", {}).setdefault(source_key, {})
        next_play_at = float(state.get("next_play_at", runtime["time"]))
        occurrence = max(0, int(state.get("occurrence", 0)))
        if runtime["time"] >= next_play_at:
            queue_audio_event(runtime, {
                "type": "sound_emitter_cadence", "source_id": source_key,
                "source_kind": "sound_emitter", "world_position": position,
                "priority": 0.45, "gain": emitter["gain"],
                "data": {
                    "family": family_name,
                    "spatial_policy": spatial_policy,
                    "emitter_id": str(emitter_id),
                },
            })
            occurrence += 1
            next_play_at = runtime["time"] + sound_emitter_cadence_interval(
                emitter, occurrence,
            )
        state["next_play_at"] = next_play_at
        state["occurrence"] = occurrence
    sources.sort(key=lambda item: item["distance"])
    runtime["stats"]["nearest_sound_emitter_sources"] = sources[:8]


def _request_environment_loops(runtime, listener, tile_map, entities, rain_profile, emitters, profile):
    listener_position = listener.get("world_position", {})
    _request_sound_emitters(runtime, listener_position, tile_map, entities)
    rain_state, rain_targets = resolve_listener_rain_state(listener_position, tile_map, rain_profile)
    runtime["stats"]["listener_rain_state"] = rain_state
    runtime["stats"]["rain_loop_targets"] = dict(rain_targets)
    for family_name, target in rain_targets.items():
        request_loop(runtime, f"weather:{family_name}", f"weather.{family_name}", target, spatial=False)
    zone_id = get_acoustic_zone_at_world_position(tile_map, listener_position)
    zone = get_acoustic_zone_definition(tile_map, zone_id)
    ambience_set = zone.get("ambience_set", zone.get("environment", "open_exterior"))
    runtime["stats"]["current_ambience_set"] = ambience_set
    environment = zone.get("environment", "open_exterior")
    ambience_state = runtime.setdefault("source_state", {}).setdefault("ambience", {})
    previous_zone = ambience_state.get("listener_zone")
    if previous_zone is not None and previous_zone != zone_id:
        keep_prefixes = (f"ambience:{zone_id}:", f"ambience:{previous_zone}:")
        for key in list(runtime.setdefault("loop_voices", {})):
            if key.startswith("ambience:") and not key.startswith(keep_prefixes):
                _safe_close(runtime["loop_voices"][key].get("sound"))
                runtime["loop_voices"].pop(key, None)
    ambience_state["listener_zone"] = zone_id
    request_loop(runtime, f"ambience:{zone_id}:base", f"ambience.{environment}.base", 1.0, spatial=False)
    request_loop(runtime, f"ambience:{zone_id}:wind", f"ambience.{environment}.wind", 0.45, spatial=False)
    next_incidental = float(ambience_state.get(
        "next_incidental", runtime["time"] + 9.0 + (zone_id * 17 % 11) * 0.7,
    ))
    if runtime["time"] >= next_incidental:
        queue_audio_event(runtime, {
            "type": "ambience_incidental", "source_id": f"ambience:{zone_id}",
            "source_kind": "ambience", "world_position": dict(listener_position),
            "priority": 0.1, "gain": 0.55,
            "data": {"environment": environment},
        })
        next_incidental += 13.0 + (zone_id * 29 % 9) * 0.8
    ambience_state["next_incidental"] = next_incidental
    fire_sources = []
    for emitter_id, emitter in (emitters or {}).items():
        if not isinstance(emitter, dict) or emitter.get("type") != "fire" or not emitter.get("enabled", True):
            continue
        position = _entity_world_position(emitter, tile_map)
        size = emitter.get("size", emitter.get("area_size", {}))
        scale = _clamp((float(size.get("x", 16.0)) + float(size.get("y", 16.0))) / 64.0, 0.25, 1.5)
        context = resolve_source_listener_acoustic_context(position, listener_position, tile_map)
        family = "fire.fire_bed_large" if scale > 0.85 else "fire.fire_bed_small"
        request_loop(runtime, f"fire:{emitter_id}:bed", family, 0.55 * scale,
                     position, True, context)
        distance = math.hypot(position["x"] - float(listener_position.get("x", 0.0)),
                              position["y"] - float(listener_position.get("y", 0.0)))
        fire_sources.append({"id": str(emitter_id), "distance": distance, "position": position})
        source_state = runtime.setdefault("source_state", {}).setdefault(f"fire:{emitter_id}", {})
        next_crackle = float(source_state.get("next_crackle", runtime["time"] + 1.0 + (int(emitter.get("seed", 1)) % 17) * 0.11))
        if runtime["time"] >= next_crackle:
            queue_audio_event(runtime, {"type": "fire_crackle", "source_id": f"fire:{emitter_id}",
                                        "source_kind": "fire", "world_position": position,
                                        "priority": 0.25, "gain": 0.5})
            next_crackle += 2.5 + (int(emitter.get("seed", 1)) % 13) * 0.17
        source_state["next_crackle"] = next_crackle
    fire_sources.sort(key=lambda item: item["distance"])
    runtime["stats"]["nearest_fire_loop_sources"] = fire_sources[:4]


def update_audio(audio_runtime, engine, dt, listener, tile_map, entities,
                 rain_profile, emitters, audio_profile):
    """Process deferred events, then update persistent environmental loops."""
    if not isinstance(audio_runtime, dict):
        return None
    profile = normalize_audio_profile(audio_profile)
    audio_runtime["engine"] = engine
    audio_runtime["time"] = float(audio_runtime.get("time", 0.0)) + max(0.0, float(dt))
    audio_runtime["frame"] = int(audio_runtime.get("frame", 0)) + 1
    audio_runtime["listener"] = copy.deepcopy(listener or {})
    audio_runtime["listener"].setdefault("world_position", {"x": 0.0, "y": 0.0})
    listener = audio_runtime["listener"]
    migrate_tile_audio_data(tile_map)
    _retire_finished_voices(audio_runtime)
    previous_stats = audio_runtime.get("stats", {})
    stats = _empty_stats()
    stats["voice_steals"] = int(previous_stats.get("voice_steals", 0))
    audio_runtime["stats"] = stats
    event_queue = audio_runtime.setdefault("event_queue", [])
    queued = list(event_queue)
    stats["queued_events"] = len(queued)
    listener_position = listener.get("world_position", {})
    listener_zone = get_acoustic_zone_at_world_position(tile_map, listener_position)
    stats["listener_zone"] = listener_zone
    stats["listener_tile_surface"] = get_tile_audio_surface(tile_map, listener_position)
    enemy_steps = [event for event in queued if event.get("type") == "footstep" and event.get("source_kind") == "enemy"]
    ordinary = [event for event in queued if event not in enemy_steps]
    accepted_enemy = arbitrate_enemy_footsteps(enemy_steps, audio_runtime, listener, tile_map, profile)
    accepted = ordinary + accepted_enemy
    for event in accepted:
        voices = _process_event(audio_runtime, event, listener, tile_map, entities or {}, profile)
        if voices or event.get("type") in CONTROL_EVENT_TYPES:
            stats["accepted_events"] += 1
        elif event.get("type") not in CONTROL_EVENT_TYPES:
            _discard(stats, "missing_asset_family")
    _request_environment_loops(
        audio_runtime, listener, tile_map, entities or {}, rain_profile or {},
        emitters or {}, profile,
    )
    # Crackles requested above are intentionally deferred to the next frame so
    # all event arbitration still happens at one stable processing boundary.
    update_loop_voices(audio_runtime, dt, listener, profile)
    _retire_finished_voices(audio_runtime)
    # Remove exactly the frame-start batch. Environment schedulers above may
    # have appended crackles/incidental ambience for the next processing pass.
    del event_queue[:len(queued)]
    stats["active_one_shot_voices"] = len(audio_runtime.get("active_voices", []))
    stats["active_loop_voices"] = sum(1 for loop in audio_runtime.get("loop_voices", {}).values() if loop.get("sound") is not None)
    if not stats["requested_treatment"]:
        context = resolve_source_listener_acoustic_context(listener_position, listener_position, tile_map)
        stats["requested_treatment"] = {
            "low_pass_hz": context.get("low_pass_hz"), "wet_send": context.get("wet_send"),
            "reverb_preset": context.get("reverb_preset"),
        }
    stats["actual_treatment"] = audio_runtime.get("capabilities", {}).get("treatment_mode", "gain_fallback")
    stats["missing_asset_families"] = sorted(audio_runtime.get("missing_asset_warnings", set()))
    stats["missing_asset_paths"] = sorted(audio_runtime.get("missing_asset_path_warnings", set()))
    return stats
