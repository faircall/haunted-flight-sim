"""Data-driven tree packs; original authored willow remains a separate type."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = ("willow a", "willow b", "willow c")
TREE_TYPES = ("willow tree", *VARIANTS)
_cache = {}


def definition(entity_type):
    path = ROOT / "art" / "trees" / entity_type.replace(" ", "_") / "tree.json"
    stamp = path.stat().st_mtime_ns
    if entity_type not in _cache or _cache[entity_type][0] != stamp:
        data = json.loads(path.read_text())
        data["directory"] = path.parent
        _cache[entity_type] = (stamp, data)
    return _cache[entity_type][1]


def reference_name(entity_type):
    return "willow_tree_reference" if entity_type == "willow tree" else entity_type.replace(" ", "_") + "_reference"
