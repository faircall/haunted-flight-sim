"""Plain-data puzzle state. Functions return the arena; nested dicts are mutable.

Definitions live on entities, progress under puzzle_state, transient UI/audio in
puzzle_runtime. No function objects or GPU resources are stored in the arena.
"""
import copy
import uuid

import g_puzzle_data as data

DOOR_TYPES = ("key door", "authored door", "lever door", "code door")


def init_object(entity, kind):
    definition = data.OBJECTS[kind]
    entity.update(persistent_id="puzzle:" + uuid.uuid4().hex,
                  puzzle_group=1, label=definition["label"],
                  entity_width=16, entity_height=16)
    if "handler" in definition:
        entity["on_unlock"] = definition["handler"]
    if "code" in definition:
        entity["code"] = definition["code"]
    return entity


def ensure_arena(arena):
    if "puzzle_state" not in arena:
        arena = arena.set("puzzle_state", {"objects": {}, "inventory": {}, "facts": {}, "spawns": {}})
    if "puzzle_runtime" not in arena:
        arena = arena.set("puzzle_runtime", {"message": "", "message_time": 0.0,
                                            "keypad": None, "digits": "", "sounds": []})
    return arena


def objects(arena):
    return arena.get("entities", {}).get("puzzles", {}).values()


def get_object(arena, persistent_id):
    return next((obj for obj in objects(arena) if obj["persistent_id"] == persistent_id), None)


def group_objects(arena, source, kind):
    return [obj for obj in objects(arena) if obj["type"] == kind
            and obj["puzzle_group"] == source["puzzle_group"]]


def object_state(arena, obj):
    return arena["puzzle_state"]["objects"].setdefault(obj["persistent_id"], {})


def set_fact(arena, name, value):
    arena["puzzle_state"]["facts"][name] = value
    return arena


def has_key(arena, obj):
    return arena["puzzle_state"]["inventory"].get(str(obj["puzzle_group"]), 0) > 0


def message(arena, text):
    arena["puzzle_runtime"].update(message=text, message_time=4.0)
    return arena


def world_position(obj, tile_map):
    pos = obj["position"]
    if obj["type"] in DOOR_TYPES:
        return {"x": (pos["tile_x"] + 0.5) * tile_map["tile_width"],
                "y": (pos["tile_y"] + 0.5) * tile_map["tile_height"]}
    return {"x": pos["tile_x"] * tile_map["tile_width"] + pos["x"],
            "y": pos["tile_y"] * tile_map["tile_height"] + pos["y"]}


def bounds(obj, tile_map):
    pos = world_position(obj, tile_map)
    width, height = ((tile_map["tile_width"], tile_map["tile_height"])
                     if obj["type"] in DOOR_TYPES else (8, 8))
    return dict(x=pos["x"] - width / 2, y=pos["y"] - height / 2, width=width, height=height)


def sound(arena, obj, event_type):
    arena["puzzle_runtime"]["sounds"].append({
        "type": event_type, "source_id": obj["persistent_id"], "source_kind": "puzzle",
        "world_position": world_position(obj, arena["tile_map"]),
        "data": {"instance_key": obj["persistent_id"] + ":" + event_type},
    })
    return arena


def unlock_door(arena, door):
    state = object_state(arena, door)
    if not state.get("unlocked"):
        state["unlocked"] = True
        sound(arena, door, "reload_start")
        message(arena, "Unlocked. Press E again to open.")
    return arena


def door_is_occupied(arena, door):
    import g_update_and_render as game
    box = bounds(door, arena["tile_map"])
    actors = [arena["player_info"]] + list(arena["entities"].get("brains", {}).values())
    return any(game.aabbs_overlap(box, game.get_entity_collision_box(actor, arena["tile_map"]))
               for actor in actors if actor.get("health", 1) > 0)


def set_door_open(arena, door, opened):
    state = object_state(arena, door)
    if opened and not state.get("unlocked"):
        return message(arena, "The door is locked.")
    if not opened and door_is_occupied(arena, door):
        return message(arena, "The doorway is occupied.")
    if bool(state.get("open")) != bool(opened):
        state["open"] = bool(opened)
        sound(arena, door, "weapon_unholster")
        sync_door_tiles(arena)
    return arena


def sync_door_tiles(arena):
    """Derived full-tile blockers; never change the authored floor tile."""
    tile_map = arena["tile_map"]
    blocked = set()
    for obj in objects(arena):
        if obj["type"] not in DOOR_TYPES or object_state(arena, obj).get("open"):
            continue
        pos = obj["position"]
        if 0 <= pos["tile_x"] < tile_map["map_width"] and 0 <= pos["tile_y"] < tile_map["map_height"]:
            blocked.add(pos["tile_y"] * tile_map["map_width"] + pos["tile_x"])
    previous = set(tile_map.get("_puzzle_blocked_tiles", ()))
    if previous != blocked:
        for index in previous | blocked:
            if 0 <= index < len(tile_map["tiles"]):
                tile_map["tiles"][index]["puzzle_blocked"] = index in blocked
        tile_map["_puzzle_blocked_tiles"] = sorted(blocked)
        tile_map["geometry_revision"] = tile_map.get("geometry_revision", 0) + 1
        tile_map["acoustic_revision"] = tile_map.get("acoustic_revision", 0) + 1
    return arena


def spawn_entity(arena, marker, identity):
    import g_update_and_render as game
    enemy = {"type": "red head", "id": identity,
             "position": copy.deepcopy(marker["position"]),
             "entity_width": game.g_default_entity_width,
             "entity_height": game.g_default_entity_height}
    game.give_entity_stats_from_type(enemy, "red head")
    return enemy


def spawn_is_clear(arena, marker):
    import g_update_and_render as game
    enemy = spawn_entity(arena, marker, "puzzle:preview")
    box = game.get_entity_collision_box(enemy, arena["tile_map"])
    tile_map = arena["tile_map"]
    # Check all tiles touched by the enemy, not just its centre.
    import math
    for ty in range(math.floor(box["y"] / tile_map["tile_height"]),
                    math.floor((box["y"] + box["height"]) / tile_map["tile_height"]) + 1):
        for tx in range(math.floor(box["x"] / tile_map["tile_width"]),
                        math.floor((box["x"] + box["width"]) / tile_map["tile_width"]) + 1):
            if game.tile_not_in_bounds(tx, ty, tile_map):
                return False
            if game.tile_is_collidable(tile_map["tiles"][ty * tile_map["map_width"] + tx], tile_map):
                return False
    actors = [arena["player_info"]] + list(arena["entities"].get("brains", {}).values())
    return not any(game.aabbs_overlap(box, game.get_entity_collision_box(actor, tile_map))
                   for actor in actors if actor.get("health", 1) > 0)


def spawn_redhead(arena, marker, spawn_id):
    import g_update_and_render as game
    spawned = arena["puzzle_state"]["spawns"]
    if spawn_id in spawned:
        return arena
    identity = "puzzle_enemy:" + spawn_id
    enemy = spawn_entity(arena, marker, identity)
    arena["entities"].setdefault("brains", {})[identity] = enemy
    game.update_tile_manager(enemy["position"], enemy["position"], identity,
                             arena["tile_map"], entity=enemy)
    spawned[spawn_id] = identity
    return arena


def interact(arena, target, code=None):
    obj = get_object(arena, target)
    if obj is None:
        return message(arena, "This object no longer exists.")
    state = object_state(arena, obj)
    kind = obj["type"]
    if kind == "puzzle key":
        if not state.get("collected"):
            state["collected"] = True
            inventory = arena["puzzle_state"]["inventory"]
            key = str(obj["puzzle_group"])
            inventory[key] = inventory.get(key, 0) + 1
            return message(arena, "Collected brass key (group " + key + ").")
    elif kind in DOOR_TYPES:
        if not state.get("unlocked"):
            handler_name = obj.get("on_unlock")
            if handler_name:
                handler = data.HANDLERS.get(handler_name)
                if handler is None:
                    return message(arena, "Unknown puzzle handler: " + handler_name)
                arena = handler(arena, {"type": "interact", "target": target})
                state = object_state(arena, obj)
                if state.get("unlocked"):
                    # Separate unlock/open lets the placeholder reload sound finish.
                    return arena
                return arena
            return message(arena, "Use the matching " + ("lever." if kind == "lever door" else "keypad."))
        return set_door_open(arena, obj, not state.get("open", False))
    elif kind == "puzzle lever":
        doors = group_objects(arena, obj, "lever door")
        opened = not state.get("active", False)
        if not opened and any(door_is_occupied(arena, door) for door in doors):
            return message(arena, "The doorway is occupied.")
        state["active"] = opened
        for door in doors:
            arena = unlock_door(arena, door)
            arena = set_door_open(arena, door, opened)
        return message(arena, "Lever " + ("on." if opened else "off."))
    elif kind == "puzzle keypad":
        if code is None:
            arena["puzzle_runtime"].update(keypad=target, digits="")
            return arena
        if len(code) != 4 or not code.isascii() or not code.isdigit() or code != obj.get("code", "0451"):
            return message(arena, "Incorrect code.")
        doors = group_objects(arena, obj, "code door")
        if not doors:
            return message(arena, "No code door in this puzzle group.")
        for door in doors:
            arena = unlock_door(arena, door)
            arena = set_door_open(arena, door, True)
        arena["puzzle_runtime"].update(keypad=None, digits="")
        return message(arena, "Code accepted.")
    return arena


def nearest_interactable(arena, radius=26.0):
    import g_update_and_render as game
    player = game.tile_and_offset_to_absolute(arena["tile_map"], arena["player_info"]["position"])
    candidates = []
    for obj in objects(arena):
        if obj["type"] == "puzzle spawn" or object_state(arena, obj).get("collected"):
            continue
        pos = world_position(obj, arena["tile_map"])
        distance = (player["x"] - pos["x"]) ** 2 + (player["y"] - pos["y"]) ** 2
        if distance > radius * radius:
            continue
        # Check the approach segment; exclude the target door's own blocking tile.
        steps = max(1, int(distance ** 0.5 / 2))
        visible = True
        for step in range(1, steps):
            point = {axis: player[axis] + (pos[axis] - player[axis]) * step / steps for axis in ("x", "y")}
            tile_pos = game.get_tile_index_and_offset_from_pos(point, arena["tile_map"])
            if obj["type"] in DOOR_TYPES and all(tile_pos[k] == obj["position"][k] for k in ("tile_x", "tile_y")):
                continue
            if game.position_collides_within_tile_shape(tile_pos, arena["tile_map"]):
                visible = False
                break
        if visible:
            candidates.append((distance, obj["persistent_id"], obj))
    return min(candidates, key=lambda entry: entry[:2])[2] if candidates else None


def reset_progress(arena):
    for identity in arena["puzzle_state"]["spawns"].values():
        arena["entities"].get("brains", {}).pop(identity, None)
    arena = arena.remove("puzzle_state").remove("puzzle_runtime")
    had_sequences = "sequence_state" in arena
    for key in ("sequence_state", "sequence_runtime"):
        if key in arena:
            arena = arena.remove(key)
    arena = ensure_arena(arena)
    if had_sequences:
        import g_sequences
        arena = g_sequences.ensure(arena)
    sync_door_tiles(arena)
    return arena
