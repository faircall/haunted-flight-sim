"""Redhead draft editing and validated, conflict-aware data-module persistence."""
import ast
import copy
import difflib
import math
import os
from pathlib import Path
import pprint
import tempfile

import g_animation_redhead_data as data
import g_animation_player_data as player_data

NAMES = ("REDHEAD_CUTOUT_TEXTURES", "REDHEAD_CUTOUT_RIG_DEFAULTS",
         "REDHEAD_CUTOUT_GAIT_PROFILES", "REDHEAD_ANIMATION_DEBUG_POSE_NAMES")
HEADER = ("# Redhead animation data. Editable in Animation mode; Save to Code rewrites this file.\n"
          "# Schema, validation and help live in g_animation_authoring.py.\n\n")
# Keep structural calibration separate from freely editable pose values.
_SHAPE = copy.deepcopy({name: getattr(data, name) for name in NAMES})


PLAYER_NAMES = tuple(name for name in vars(player_data) if name.startswith("PLAYER_"))
_PLAYER_SHAPE = copy.deepcopy({name: getattr(player_data, name) for name in PLAYER_NAMES})


def character_for(document):
    return "player" if "PLAYER_CUTOUT_GAIT_PROFILES" in document else "redhead"


def module_for(character):
    return player_data if character == "player" else data


def data_path(character="redhead"):
    return Path(module_for(character).__file__).resolve()


def field_bounds(key):
    if key.endswith("degrees"):
        return -180.0, 180.0
    if key.endswith("pixels"):
        return -12.0, 12.0
    return 0.0, 2.0


def validate(document):
    def check(value, reference, path):
        if isinstance(reference, dict):
            if not isinstance(value, dict) or value.keys() != reference.keys():
                raise ValueError(f"Unexpected fields in {path}")
            for key in reference:
                check(value[key], reference[key], f"{path}.{key}")
        elif isinstance(reference, (list, tuple)):
            if not isinstance(value, type(reference)) or len(value) != len(reference):
                raise ValueError(f"Unexpected sequence in {path}")
            for index, item in enumerate(reference):
                check(value[index], item, f"{path}[{index}]")
        elif isinstance(reference, bool):
            if type(value) is not bool:
                raise ValueError(f"Expected boolean: {path}")
        elif isinstance(reference, (float, int)):
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError(f"Expected finite number: {path}")
            if "_PROFILES" in path:
                low, high = field_bounds(path.rsplit(".", 1)[-1])
            else:
                low, high = -360.0, 360.0
            if not low <= value <= high:
                raise ValueError(f"Out of range: {path} ({low:g} to {high:g})")
        elif not isinstance(value, str) or not value:
            raise ValueError(f"Expected text: {path}")
    character = character_for(document)
    check(document, _PLAYER_SHAPE if character == "player" else _SHAPE, "animation")
    if character == "player":
        if document["PLAYER_CUTOUT_RIG_DEFAULTS"]["canvas_size"] != 32.0:
            raise ValueError("Player art requires a 32 pixel canvas")
        return document
    rig = document["REDHEAD_CUTOUT_RIG_DEFAULTS"]
    if rig["canvas_size"] != 24.0:
        raise ValueError("Redhead art requires a 24 pixel canvas")
    if not 0 <= rig["run_blend_start_speed_fraction"] < rig["run_blend_full_speed_fraction"] <= 1:
        raise ValueError("Run blend requires 0 <= start < full <= 1")
    for key in ("movement_blend_response", "profile_blend_response"):
        if rig[key] < 0:
            raise ValueError(f"{key} must be nonnegative")
    if any(type(channel) is not int or not 0 <= channel <= 255 for channel in rig["far_limb_tint"]):
        raise ValueError("Limb tint channels must be integers from 0 to 255")
    return document


def parse_source(source, character="redhead"):
    names = PLAYER_NAMES if character == "player" else NAMES
    document = {}
    for node in ast.parse(source).body:
        if (not isinstance(node, ast.Assign) or len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)
                or node.targets[0].id not in names
                or node.targets[0].id in document):
            raise ValueError("Animation data must contain only its declared literal assignments")
        document[node.targets[0].id] = ast.literal_eval(node.value)
    if set(document) != set(names):
        raise ValueError("Missing animation data assignments")
    return validate(document)


def serialize(document):
    validate(document)
    character = character_for(document)
    names = PLAYER_NAMES if character == "player" else NAMES
    header = HEADER.replace("Redhead", "Player") if character == "player" else HEADER
    source = header + "\n\n".join(
        name + " = " + pprint.pformat(document[name], sort_dicts=False, width=100)
        for name in names
    ) + "\n"
    compile(source, str(data_path(character)), "exec")
    return source


def reload_data(path=None, character="redhead"):
    # Parse before touching the module. A bad hand edit keeps all live values.
    document = parse_source((Path(path) if path else data_path(character)).read_text(encoding="utf-8"), character)
    module_for(character).__dict__.update(copy.deepcopy(document))


def new_draft(path=None, character="redhead"):
    source = (Path(path) if path else data_path(character)).read_bytes()
    document = parse_source(source.decode("utf-8"), character)
    return {"document": document, "baseline": copy.deepcopy(document),
            "source": source, "undo": [], "redo": [], "clipboard": None,
            "preview": True, "review": None, "message": "Draft ready"}


def dirty(draft):
    return draft["document"] != draft["baseline"]


def commit(draft, document):
    validate(document)
    if document == draft["document"]:
        return
    draft["undo"].append(copy.deepcopy(draft["document"]))
    draft["undo"] = draft["undo"][-100:]
    draft["redo"].clear()
    draft["document"] = copy.deepcopy(document)
    draft["review"] = None


def edit_pose(draft, track, index, key, value, linked=False, profile_path=None):
    document = copy.deepcopy(draft["document"])
    poses = get_path(document, profile_path or ("REDHEAD_CUTOUT_GAIT_PROFILES", track))
    poses[index][key] = value
    if linked and key.startswith(("near_", "far_")):
        opposite = ("far_" if key.startswith("near_") else "near_") + key.split("_", 1)[1]
        poses[(index + 2) % len(poses)][opposite] = value
    commit(draft, document)


def history(draft, redo=False):
    source, target = ("redo", "undo") if redo else ("undo", "redo")
    if draft[source]:
        draft[target].append(copy.deepcopy(draft["document"]))
        draft["document"] = draft[source].pop()
        draft["review"] = None


def reset_pose(draft, track, index, profile_path=None):
    document = copy.deepcopy(draft["document"])
    path = profile_path or ("REDHEAD_CUTOUT_GAIT_PROFILES", track)
    get_path(document, path)[index] = copy.deepcopy(get_path(draft["baseline"], path)[index])
    commit(draft, document)


def copy_pose(draft, track, index, profile_path=None):
    draft["clipboard"] = copy.deepcopy(get_path(draft["document"], profile_path or ("REDHEAD_CUTOUT_GAIT_PROFILES", track))[index])


def paste_pose(draft, track, index, profile_path=None):
    if draft["clipboard"] is not None:
        document = copy.deepcopy(draft["document"])
        poses = get_path(document, profile_path or ("REDHEAD_CUTOUT_GAIT_PROFILES", track))
        if poses[index].keys() != draft["clipboard"].keys():
            raise ValueError("This pose uses different fields. Copy from a compatible track.")
        poses[index] = copy.deepcopy(draft["clipboard"])
        commit(draft, document)


def prepare_save(draft):
    source = serialize(draft["document"])
    draft["review"] = {"source": source,
                       "diff": list(difflib.unified_diff(
                           draft["source"].decode("utf-8").splitlines(), source.splitlines(),
                           fromfile="saved", tofile="draft", lineterm=""))}
    return draft["review"]


def save(draft, path=None):
    character = character_for(draft["document"])
    path = Path(path) if path else data_path(character)
    source = serialize(draft["document"])
    if not draft["review"] or draft["review"]["source"] != source:
        raise ValueError("Review the current changes before saving")
    if path.read_bytes() != draft["source"]:
        raise ValueError("Source changed externally. Revert/reload before saving.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != draft["source"]:
            raise ValueError("Source changed externally. Draft retained.")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    draft["source"] = source.encode("utf-8")
    draft["baseline"] = copy.deepcopy(draft["document"])
    draft["review"] = None
    draft["message"] = "Saved to code"
    if path.resolve() == data_path(character):
        module_for(character).__dict__.update(copy.deepcopy(draft["document"]))


def get_path(document, path):
    for key in path:
        document = document[key]
    return document


def pose_path(character, facing, group, track):
    if character == "redhead":
        return ("REDHEAD_CUTOUT_GAIT_PROFILES", track)
    if facing in ("up", "down"):
        name = "PLAYER_FRONT_CUTOUT_ARM_PROFILES" if group == "arms" else "PLAYER_FRONT_CUTOUT_LEG_PROFILES"
        return (name, facing, track)
    return ("PLAYER_CUTOUT_GAIT_PROFILES", track)
