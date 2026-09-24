"""Bounded editor transactions. History is transient; only authored fields rewind."""
import copy
import time
import pyray as pr

LIMIT = 100
PROFILE_KEYS = ("lighting_profile", "fog_profile", "wind_profile", "rain_profile", "audio_profile")
TILE_FIELDS = ("index", "shape_index", "force_collidable", "rain_exposure", "acoustic_zone_id", "footstep_overlay",
               "surface_material", "surface_density", "surface_seed", "surface_soft")
ACTOR_FIELDS = ("position", "glow", "height", "description_id", "movement_settings",
    "perception_settings", "evade_settings", "flee_settings", "render_anchor_offset",
    "render_base_offset", "visual_height", "light_sample_height", "ground_footprint",
    "self_shadow", "entity_light_occluder", "shadow", "outline", "contact_shadow",
    "render_style", "occludes_render_items", "occludes_player", "outline_player_when_behind",
    "fog_interaction", "water_interaction", "entity_width", "entity_height", "value",
    "wind_response", "tree_seed", "tree_irregular", "tree_mesh")


def state(assets):
    return assets.setdefault("editor_history", {"undo": [], "pending": {}, "before": None,
        "group": None, "mode": None, "message": "", "until": 0.0})


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return copy.deepcopy(value)


def snapshot(arena, editor, mode):
    result = {("selection",): tuple(editor.get(k) for k in ("selected_kind", "selected_collection", "selected_id"))}
    tile_map = arena.get("tile_map") or {}
    if mode in ("tile", "sequences"):
        # Tile authoring values are scalars. Compact rows avoid copying runtime
        # neighbours/collision lists or allocating a dictionary per cell.
        result[("tiles",)] = tuple(tuple(tile.get(k) for k in TILE_FIELDS) for tile in tile_map.get("tiles", []))
        for k in ("tile_types", "acoustic_zones"):
            if k in tile_map:
                result[("map", k)] = clean(tile_map[k])
    for collection, objects in (arena.get("entities") or {}).items():
        if collection == "projectiles" or not isinstance(objects, dict):
            continue
        for identity, obj in objects.items():
            if not isinstance(obj, dict):
                continue
            authored = ({k: clean(obj[k]) for k in ACTOR_FIELDS if k in obj}
                        if collection in ("brains", "pickups") else clean(obj))
            result[("entity", collection, identity)] = (authored, clean(obj))
    for k in PROFILE_KEYS + ("world_sequences",):
        if k in arena:
            result[("arena", k)] = clean(arena[k])
    if mode == "sequences":
        result[("draft",)] = clean(editor.get("sequence_editor", {}).get("draft"))
    return result


def differences(before, after):
    patches = {}
    selection_changed = before.get(("selection",)) != after.get(("selection",))
    for path in before.keys() | after.keys():
        if path[0] == "selection":
            continue
        old_exists, new_exists = path in before, path in after
        old, new = before.get(path), after.get(path)
        if path[0] == "tiles":
            for i, (old_row, new_row) in enumerate(zip(old or (), new or ())):
                if old_row != new_row:
                    for field, a, b in zip(TILE_FIELDS, old_row, new_row):
                        if a != b:
                            patches[("tile", i, field)] = (a is not None, a, b is not None, b)
            continue
        if path[0] == "entity" and old_exists and new_exists:
            old, new = old[0], new[0]
        elif path[0] == "entity":
            old = old[1] if old_exists else None
            new = new[1] if new_exists else None
        if old_exists == new_exists and old == new:
            continue
        if old_exists and new_exists and isinstance(old, dict) and isinstance(new, dict):
            for field in old.keys() | new.keys():
                # Opening an actor inspector fills previously implicit defaults.
                # That is not an edit; position changes during a drag still count.
                if (selection_changed and path[0] == "entity" and path[1] in ("brains", "pickups")
                        and field != "position" and not old.get(field)):
                    continue
                if (field in old) != (field in new) or old.get(field) != new.get(field):
                    patches[path + (field,)] = (field in old, copy.deepcopy(old.get(field)), field in new, copy.deepcopy(new.get(field)))
        elif old_exists != new_exists or old != new:
            patches[path] = (old_exists, copy.deepcopy(old), new_exists, copy.deepcopy(new))
    return patches


def flush(history):
    pending = {p: v for p, v in history["pending"].items() if v[:2] != v[2:]}
    if pending:
        history["undo"].append(pending)
        del history["undo"][:-LIMIT]
    history["pending"] = {}
    history["group"] = None


def record(history, before, after, group=None):
    if history["group"] != group:
        flush(history)
    history["group"] = group
    for path, change in differences(before, after).items():
        previous = history["pending"].get(path)
        history["pending"][path] = (previous[:2] if previous else change[:2]) + change[2:]
    if group is None:
        flush(history)


def apply(arena, editor, patches):
    for path in sorted(patches, key=len):
        exists, old, _, _ = patches[path]
        kind = path[0]
        if kind == "entity":
            container = arena["entities"].setdefault(path[1], {})
            key = path[2]
            if len(path) == 4:
                if key not in container:
                    continue
                container, key = container[key], path[3]
        elif kind == "tile":
            container, key = arena["tile_map"]["tiles"][path[1]], path[2]
        elif kind == "map":
            container, key = arena["tile_map"], path[1]
            if len(path) == 3:
                container, key = container[key], path[2]
        elif kind == "arena":
            if len(path) == 2:
                arena = arena.set(path[1], copy.deepcopy(old)) if exists else arena.remove(path[1])
                continue
            container, key = arena[path[1]], path[2]
        elif kind == "draft":
            container, key = editor.setdefault("sequence_editor", {}), "draft"
            if len(path) == 2:
                container, key = container.setdefault("draft", {}), path[1]
        else:
            continue
        if exists:
            container[key] = copy.deepcopy(old)
        else:
            container.pop(key, None)
    return arena


def undo(arena, assets):
    import g_editor
    import g_puzzles
    import g_effects
    import g_graphics
    import g_update_and_render as game
    history = state(assets)
    flush(history)
    if not history["undo"]:
        history.update(message="Nothing to undo", until=time.monotonic() + 2)
        return arena
    editor = g_editor.get_or_create_editor_state(assets)
    arena = apply(arena, editor, history["undo"].pop())
    editor.update(drag_kind=None, tile_paint_previous=None, tile_paint_mode=None)
    sequence = editor.get("sequence_editor", {})
    sequence.update(preview=None, drag=None)
    for key in ("finish", "command", "demo", "append_to"):
        sequence.pop(key, None)
    tile_map = arena["tile_map"]
    for revision in ("geometry_revision", "rain_exposure_revision", "acoustic_revision"):
        tile_map[revision] = tile_map.get(revision, 0) + 1
    g_puzzles.sync_door_tiles(arena)
    game.rebuild_actor_collision_index(tile_map, arena["player_info"], arena["entities"])
    assets.pop("actor_collision_index_signature", None)
    g_effects.clear_effects_runtime(assets)
    g_graphics.clear_rain_runtime_assets(assets)
    assets.pop("effects_entities_identity", None)
    g_editor.validate_selection(arena["entities"], editor)
    history.update(message="Undid editor change", until=time.monotonic() + 2)
    return arena


def begin(arena, assets):
    """Called before editor mutations, never snapshots simulation frames."""
    import g_ui
    history = state(assets)
    mode = arena.get("editor_mode", "tile")
    if mode == "play" or arena.get("do_load_level") or not arena.get("tile_map"):
        assets.pop("editor_history", None)
        return arena
    if history["mode"] != mode:
        finish_stroke(arena, assets)
        flush(history)
        history["mode"] = mode
    ui = assets.get("ui_state", {})
    editor = assets.get("editor_state", {})
    held_mouse = pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT) or pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_RIGHT)
    if not held_mouse:
        history["suppress_mouse"] = False
    ctrl = pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KeyboardKey.KEY_RIGHT_CONTROL)
    if ctrl and pr.is_key_pressed(pr.KeyboardKey.KEY_Z):
        finish_stroke(arena, assets)
        history["suppress_mouse"] = bool(held_mouse)
        history["before"] = None
        if ui.get("focused_id"):
            # Cancel the text edit first; don't also undo an unrelated world edit.
            g_ui.ui_release_mouse(ui, commit_focused=False)
            ui["text_buffers"] = {}
            ui["pending_numeric_commits"] = {}
            return arena
        if mode == "animation":
            import g_animation_authoring
            character = editor.get("animation_debug", {}).get("authoring_character", "redhead")
            draft = editor.get(character + "_animation_draft")
            if draft:
                g_animation_authoring.history(draft)
            return arena
        g_ui.ui_release_mouse(ui, commit_focused=False)
        ui["pending_numeric_commits"] = {}
        ui["text_buffers"] = {}
        return undo(arena, assets)
    if mode == "animation":
        history["before"] = None
        return arena
    mouse = any(pr.is_mouse_button_down(button) or pr.is_mouse_button_released(button)
                for button in (pr.MouseButton.MOUSE_BUTTON_LEFT, pr.MouseButton.MOUSE_BUTTON_RIGHT))
    keys = any(pr.is_key_pressed(key) for key in (pr.KeyboardKey.KEY_DELETE, pr.KeyboardKey.KEY_BACKSPACE,
        pr.KeyboardKey.KEY_ENTER, pr.KeyboardKey.KEY_ESCAPE, pr.KeyboardKey.KEY_D))
    sequence = editor.get("sequence_editor", {})
    active = not history.get("suppress_mouse") and (mouse or keys or pr.get_mouse_wheel_move() != 0 or ui.get("focused_id") or ui.get("pending_numeric_commits") or any(sequence.get(k) for k in ("finish", "command", "demo")))
    history["before"] = snapshot(arena, editor, mode) if active and not history.get("stroke") else None
    if not active:
        flush(history)
    return arena


def finish_stroke(arena, assets):
    history = state(assets)
    stroke = history.pop("stroke", None)
    if stroke:
        before, mode = stroke
        record(history, before, snapshot(arena, assets.get("editor_state", {}), mode))


def end(arena, assets, reset=False):
    history = state(assets)
    if reset or arena.get("editor_mode") == "play":
        assets.pop("editor_history", None)
        return
    before = history.pop("before", None)
    history["before"] = None
    mode = history["mode"]
    editor = assets.get("editor_state", {})
    held = pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT) or pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_RIGHT)
    if held:
        if before is not None:
            history.setdefault("stroke", (before, mode))
        return
    if history.get("stroke"):
        finish_stroke(arena, assets)
    elif before is not None:
        record(history, before, snapshot(arena, editor, mode))


def draw(assets):
    history = assets.get("editor_history", {})
    if time.monotonic() < history.get("until", 0):
        pr.draw_rectangle(8, 250, 200, 16, pr.Color(20, 20, 30, 230))
        pr.draw_text(history["message"], 12, 254, 8, pr.WHITE)
