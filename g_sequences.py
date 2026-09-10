"""Serializable trigger, sequence and encounter state; procedural arena helpers."""
import copy
import math
import uuid
import zlib

import g_sequence_data as data
import g_puzzles as puzzles
import g_effects

MAX_PATH_SITES = 64
MAX_PATH_LIGHTS = 8
MAX_EVENTS_PER_FRAME = 64


def new_id(prefix):
    return prefix + ":" + uuid.uuid4().hex


def fire_seed(identity):
    """Stable across reloads/processes, within the fire shader's seed range."""
    seed = 1 + zlib.crc32(str(identity).encode("utf-8")) % 65520
    return 2208 if seed == 2207 else seed


def definition_id(arena, kind, name):
    definitions = arena["world_sequences"][kind]
    if name in definitions:
        return name
    matches = [identity for identity, value in definitions.items() if value.get("label") == name]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous " + kind + " name: " + str(name))
    return matches[0]


def ensure(arena):
    arena = puzzles.ensure_arena(arena)
    for identity, emitter in arena["entities"].get("emitters", {}).items():
        if emitter.get("sequence_torch") and not emitter.get("individual_fire_seed"):
            # Upgrade old torches once; retain seeds already tuned in the editor.
            if emitter.get("seed", 2207) == 2207:
                emitter["seed"] = fire_seed(identity)
            emitter["individual_fire_seed"] = True
    if "world_sequences" not in arena:
        arena = arena.set("world_sequences", {"sequences": {}, "triggers": {}, "encounters": {}})
    if "sequence_state" not in arena:
        arena = arena.set("sequence_state", {"time": 0., "sequences": {}, "encounters": {},
            "triggers": {}, "activation": {}, "events": [], "facts": {},
            "music": {"track": "silence", "fade": 1.}})
    if "sequence_runtime" not in arena:
        arena = arena.set("sequence_runtime", {"occupancy": {}, "log": [], "errors": [], "sounds": []})
    failed_events = arena["sequence_state"].setdefault("failed_events", arena["sequence_runtime"]["errors"])
    arena["sequence_runtime"]["errors"] = failed_events
    return arena


def log(arena, text):
    entries = arena["sequence_runtime"]["log"]
    entries.append(str(text))
    del entries[:-100]


def queue_event(arena, event_type, source, handler="none", **fields):
    arena["sequence_state"]["events"].append(dict(type=event_type, source=source, handler=handler, **fields))
    return arena


def dispatch_events(arena):
    for _ in range(MAX_EVENTS_PER_FRAME):
        events = arena["sequence_state"]["events"]
        if not events:
            break
        event = events.pop(0)
        name = event.get("handler", "none")
        log(arena, f"{event['type']} -> {name}")
        try:
            if name not in data.HANDLERS:
                raise ValueError("Unknown handler: " + name)
            handler = data.HANDLERS[name]
            if handler:
                arena = handler(arena, event)
        except Exception as error:
            log(arena, f"ERROR: {error}")
            arena["sequence_runtime"]["errors"].append({"event": event, "error": str(error)})
            del arena["sequence_runtime"]["errors"][:-30]
    return arena


def resolve(arena, reference):
    return arena["entities"].get(reference["collection"], {}).get(reference["id"])


def ref_key(reference):
    return reference["collection"] + ":" + str(reference["id"])


def world(obj, tile_map):
    return g_effects.position_to_world(obj["position"], tile_map)


def tile_position(point, tile_map):
    x, y = point["x"], point["y"]
    tx, ty = math.floor(x / tile_map["tile_width"]), math.floor(y / tile_map["tile_height"])
    return dict(tile_x=tx, tile_y=ty, x=x-tx*tile_map["tile_width"], y=y-ty*tile_map["tile_height"])


def create_torch(arena, point):
    identity = new_id("torch")
    torch = g_effects.make_default_fire_emitter(tile_position(point, arena["tile_map"]))
    torch.update(sequence_torch=True, seed=fire_seed(identity), individual_fire_seed=True,
                 initially_lit=False, size={"x": 9., "y": 17.},
                 area_size={"x": 5., "y": 3.})
    torch["light"].update(radius=58., intensity=0.8)
    arena["entities"].setdefault("emitters", {})[identity] = torch
    return {"collection": "emitters", "id": identity}


def make_sequence():
    return {"label": "Lighting sequence", "mode": "objects", "targets": [], "points": [],
            "closed": False, "reverse": False, "start_index": 0, "spacing": 10., "speed": 35.,
            "delay": 0., "interval": .3, "fade_in": .6, "hold": 1., "fade_out": .6,
            "style": "persistent", "start_sound": "rumble", "item_sound": "ignite",
            "end_sound": "complete", "sound_overrides": {}, "sound_origin": None,
            "on_complete": "none", "data": {}}


def path_sites(points, spacing, closed=False):
    if len(points) < 2:
        return []
    edges = list(zip(points, points[1:] + (points[:1] if closed else [])))
    lengths = [math.hypot(b["x"]-a["x"], b["y"]-a["y"]) for a, b in edges]
    total = sum(lengths)
    if total <= .001:
        return []
    spacing = max(1., float(spacing), total / (MAX_PATH_SITES - (0 if closed else 1)))
    distances = [i * spacing for i in range(min(MAX_PATH_SITES, math.ceil(total / spacing)))]
    if not closed and (not distances or distances[-1] < total):
        distances.append(total)
    sites = []
    for distance in distances[:MAX_PATH_SITES]:
        offset = distance
        for (a, b), length in zip(edges, lengths):
            if offset <= length and length > 0:
                sites.append({"distance": distance, "point": {axis: a[axis]+(b[axis]-a[axis])*offset/length for axis in ("x", "y")}})
                break
            offset -= length
    return sites


def schedule(arena, definition):
    if definition["mode"] == "path":
        points = list(definition["points"])
        if definition.get("closed") and points:
            start = int(definition.get("start_index", 0)) % len(points)
            points = points[start:] + points[:start]
        if definition.get("reverse"):
            points = points[:1] + list(reversed(points[1:])) if definition.get("closed") else list(reversed(points))
        return [dict(site, at=definition["delay"] + site["distance"]/max(.1, definition["speed"]))
                for site in path_sites(points, definition["spacing"], definition["closed"])]
    refs = list(definition["targets"])
    if refs:
        start = int(definition.get("start_index", 0)) % len(refs)
        refs = refs[start:] + refs[:start]
    if definition.get("reverse"):
        refs = refs[:1] + list(reversed(refs[1:]))
    return [{"ref": reference, "at": definition["delay"] + index * definition["interval"]}
            for index, reference in enumerate(refs)]


def sequence_duration(definition, sites):
    if not sites:
        return 0.
    end = sites[-1]["at"] + max(0., definition["fade_in"])
    if definition["style"] != "persistent":
        end += max(0., definition["hold"]) + max(0., definition["fade_out"])
    return end


def site_weight(definition, sites, site, elapsed):
    age = elapsed - site["at"]
    if age < 0:
        return 0.
    fade = max(0., definition["fade_in"])
    value = min(1., age / max(.00001, fade)) if fade else 1.
    if definition["style"] != "persistent":
        start = (sites[-1]["at"] if definition["style"] == "fill" else site["at"]) + fade + max(0., definition["hold"])
        if elapsed >= start:
            out = max(0., definition["fade_out"])
            value = max(0., 1.-(elapsed-start)/out) if out else 0.
    return value


def sound(arena, cue, point):
    event_type = data.SOUNDS.get(cue)
    if event_type:
        arena["sequence_runtime"]["sounds"].append({"type": event_type, "source_id": "sequence",
            "source_kind": "sequence", "world_position": point or {"x": 0., "y": 0.}, "priority": 1.})


def validate_sequence(arena, definition):
    errors = []
    if not schedule(arena, definition):
        errors.append("Add targets or at least two path points")
    keys = []
    for ref in definition["targets"]:
        keys.append(ref_key(ref))
        obj = resolve(arena, ref)
        if obj is None:
            errors.append("Missing member: " + ref_key(ref))
        elif ref["collection"] not in {"emitters", "lights"} or (ref["collection"] == "emitters" and obj.get("type") != "fire"):
            errors.append("Members must be lights or fire emitters")
    if len(keys) != len(set(keys)):
        errors.append("Duplicate sequence member")
    if definition["on_complete"] not in data.HANDLERS:
        errors.append("Unknown completion handler")
    if definition["on_complete"] == "spawn_linked_encounter" and definition["data"].get("encounter") not in arena["world_sequences"]["encounters"]:
        errors.append("Select a completion encounter")
    origin = definition.get("sound_origin")
    if origin and resolve(arena, origin) is None:
        errors.append("Missing sound origin")
    for cue in [definition["start_sound"], definition["item_sound"], definition["end_sound"], *definition["sound_overrides"].values()]:
        if cue not in data.SOUNDS:
            errors.append("Unknown sound: " + str(cue))
    return errors


def start_sequence(arena, identity, restart=False, origin=None):
    identity = definition_id(arena, "sequences", identity)
    definition = arena["world_sequences"]["sequences"].get(identity)
    if definition is None:
        raise ValueError("Missing sequence: " + str(identity))
    if identity in arena["sequence_state"]["sequences"] and not restart:
        return arena
    errors = validate_sequence(arena, definition)
    if errors:
        raise ValueError("; ".join(errors))
    definition = copy.deepcopy(definition)
    sites = schedule(arena, definition)
    for site in sites:
        if "ref" in site:
            arena["sequence_state"].get("manual_activation", {}).pop(ref_key(site["ref"]), None)
            arena["sequence_state"].setdefault("owners", {})[ref_key(site["ref"])] = identity
            arena["sequence_state"]["activation"][ref_key(site["ref"])] = False
    if definition.get("sound_origin"):
        origin = world(resolve(arena, definition["sound_origin"]), arena["tile_map"])
    if origin is None:
        origin = sites[0].get("point") or world(resolve(arena, sites[0]["ref"]), arena["tile_map"])
    arena["sequence_state"]["sequences"][identity] = dict(definition=definition, sites=sites,
        elapsed=0., next=0, status="running", origin=origin, start_played=False)
    log(arena, "Started " + definition.get("label", identity))
    return arena


def update_sequences(arena, dt):
    state = arena["sequence_state"]
    for identity, record in list(state["sequences"].items()):
        if record["status"] != "running":
            continue
        record["blocked"] = ["Missing member: "+ref_key(site["ref"]) for site in record["sites"] if "ref" in site and resolve(arena,site["ref"]) is None]
        if record["blocked"]:
            continue
        record["elapsed"] += dt
        definition, sites, elapsed = record["definition"], record["sites"], record["elapsed"]
        if elapsed >= definition["delay"] and not record["start_played"]:
            sound(arena, definition["start_sound"], record["origin"])
            record["start_played"] = True
        while record["next"] < len(sites) and sites[record["next"]]["at"] <= elapsed:
            index = record["next"]
            site = sites[index]
            obj = resolve(arena, site["ref"]) if "ref" in site else None
            position = world(obj, arena["tile_map"]) if obj else site.get("point", record["origin"])
            cue = definition["sound_overrides"].get(ref_key(site["ref"]) if "ref" in site else str(index), definition["item_sound"])
            sound(arena, cue, position)
            if "ref" in site and state.get("owners", {}).get(ref_key(site["ref"]), identity) == identity:
                state["activation"][ref_key(site["ref"])] = True
            record["next"] += 1
        if definition["style"] != "persistent":
            for site in sites:
                end = (sites[-1]["at"] if definition["style"] == "fill" else site["at"]) + definition["fade_in"] + max(0., definition["hold"]) + definition["fade_out"]
                if "ref" in site and elapsed >= end and state.get("owners", {}).get(ref_key(site["ref"]), identity) == identity:
                    state["activation"][ref_key(site["ref"])] = False
        if elapsed >= sequence_duration(definition, sites):
            record["status"] = "completed"
            state["facts"]["sequence_completed:" + identity] = True
            sound(arena, definition["end_sound"], record["origin"])
            queue_event(arena, "sequence_completed", identity, definition["on_complete"], data=definition["data"])
    return arena


def set_trigger_enabled(arena, identity, enabled):
    identity = definition_id(arena, "triggers", identity)
    arena["sequence_state"]["triggers"].setdefault(identity, {})["enabled"] = bool(enabled)
    return arena


def update_triggers(arena):
    import g_update_and_render as game
    runtime, state = arena["sequence_runtime"], arena["sequence_state"]
    for identity, area in arena["world_sequences"]["triggers"].items():
        progress = state["triggers"].setdefault(identity, {"fired": [], "last": {}})
        progress.setdefault("fired", [])
        progress.setdefault("last", {})
        actors = []
        if area["actors"] in ("player", "all"):
            actors.append(("player", arena["player_info"]))
        if area["actors"] in ("enemy", "all"):
            actors.extend((str(key), obj) for key, obj in arena["entities"].get("brains", {}).items() if obj.get("health", 1) > 0)
        cells = {tuple(cell) for cell in area["cells"]}
        inside = set()
        positions = {}
        enabled = progress.get("enabled", area.get("enabled", True))
        for actor_id, actor in actors:
            position = game.tile_and_offset_to_absolute(arena["tile_map"], actor["position"])
            positions[actor_id] = position
            cell = (math.floor(position["x"]/arena["tile_map"]["tile_width"]), math.floor(position["y"]/arena["tile_map"]["tile_height"]))
            if enabled and cell in cells:
                inside.add(actor_id)
        if identity not in runtime["occupancy"]:
            runtime["occupancy"][identity] = inside
            continue
        previous = runtime["occupancy"][identity]
        if enabled:
            for event_type, changed, handler in (("trigger_enter", inside-previous, area["on_enter"]),
                                                  ("trigger_exit", previous-inside, area["on_exit"])):
                for actor_id in sorted(changed):
                    if actor_id not in positions:  # Despawn/unload is not an exit.
                        continue
                    key = event_type + ":" + actor_id
                    if area["repeat"] == "once" and event_type in progress["fired"]:
                        continue
                    if area["repeat"] == "cooldown" and state["time"]-progress["last"].get(key, -1e9) < area["cooldown"]:
                        continue
                    queue_event(arena, event_type, identity, handler, actor=actor_id, position=positions[actor_id])
                    if event_type not in progress["fired"]:
                        progress["fired"].append(event_type)
                    progress["last"][key] = state["time"]
        runtime["occupancy"][identity] = inside
    return arena


def make_trigger(cells):
    return dict(label="Trigger area", cells=[list(cell) for cell in cells], enabled=True,
                actors="player", repeat="once", cooldown=3., on_enter="start_linked_sequence",
                on_exit="none", sequence="", restart_sequence=False)


def spawn_encounter(arena, identity, restart=False):
    identity = definition_id(arena, "encounters", identity)
    definition = arena["world_sequences"]["encounters"].get(identity)
    if definition is None or not definition.get("spawns"):
        raise ValueError("Missing or empty encounter: " + str(identity))
    old = arena["sequence_state"]["encounters"].get(identity)
    if old and (not restart or old["status"] == "running"):
        return arena
    for entry in definition["spawns"]:
        marker = puzzles.get_object(arena, entry["marker"])
        if entry.get("type", "red head") != "red head" or marker is None or marker.get("type") != "puzzle spawn":
            raise ValueError("Invalid encounter spawn: " + str(entry))
    if definition.get("on_complete", "none") not in data.HANDLERS:
        raise ValueError("Unknown encounter completion handler")
    arena["sequence_state"]["encounters"][identity] = dict(definition=copy.deepcopy(definition),
        generation=old["generation"]+1 if old else 1, elapsed=0., status="running", members={}, spawned=[])
    return arena


def record_defeat(arena, enemy_id):
    for record in arena["sequence_state"]["encounters"].values():
        if enemy_id in record["members"]:
            record["members"][enemy_id] = "defeated"
    return arena


def update_encounters(arena, dt):
    for identity, record in arena["sequence_state"]["encounters"].items():
        if record["status"] != "running":
            continue
        record["elapsed"] += dt
        definition = record["definition"]
        record["blocked"] = []
        for index, entry in enumerate(definition["spawns"]):
            if index in record["spawned"] or record["elapsed"] < entry.get("at", 0):
                continue
            marker = puzzles.get_object(arena, entry["marker"])
            if marker is None or not puzzles.spawn_is_clear(arena, marker):
                record["blocked"].append(f"Spawn {index+1}: " + ("missing marker" if marker is None else "occupied/solid floor"))
                continue  # Retry blocked spawn; do not prematurely complete a wave.
            spawn_id = f"encounter:{identity}:{record['generation']}:{index}"
            arena = puzzles.spawn_redhead(arena, marker, spawn_id)
            enemy_id = arena["puzzle_state"]["spawns"][spawn_id]
            record["members"][enemy_id] = "alive"
            record["spawned"].append(index)
        for enemy_id in record["members"]:
            enemy = arena["entities"].get("brains", {}).get(enemy_id)
            if enemy is not None and enemy.get("health", 1) <= 0:
                record["members"][enemy_id] = "defeated"
        if len(record["spawned"]) == len(definition["spawns"]) and all(value == "defeated" for value in record["members"].values()):
            record["status"] = "completed"
            arena["sequence_state"]["facts"]["encounter_completed:"+identity] = True
            queue_event(arena, "encounter_completed", identity, definition.get("on_complete", "none"),
                        data=definition.get("data", {}), generation=record["generation"])
    return arena


def change_music(arena, track, fade_seconds=2.):
    if track not in data.MUSIC:
        raise ValueError("Unknown music track: " + track)
    arena["sequence_state"]["music"] = {"track": track, "fade": max(0., fade_seconds)}
    return arena


def set_torch_lit(arena, reference, lit):
    if resolve(arena, reference) is None:
        raise ValueError("Missing torch: " + ref_key(reference))
    arena["sequence_state"].setdefault("manual_activation", {})[ref_key(reference)] = 1. if lit else 0.
    arena["sequence_state"]["activation"][ref_key(reference)] = bool(lit)
    return arena


def torch_is_active(arena, reference):
    obj = resolve(arena, reference) or {}
    return arena["sequence_state"]["activation"].get(ref_key(reference), bool(obj.get("initially_lit", obj.get("enabled", False))))


def update(arena, dt):
    arena["sequence_state"]["time"] += max(0., dt)
    arena = update_triggers(arena)
    arena = update_sequences(arena, max(0., dt))
    arena = update_encounters(arena, max(0., dt))
    return dispatch_events(arena)


def presentation_entities(arena, preview=None):
    """Frame-local copies: authored brightness/emission never become progress."""
    entities = dict(arena["entities"])
    entities["emitters"] = dict(entities.get("emitters", {}))
    entities["lights"] = dict(entities.get("lights", {}))
    weights = {}
    for key, obj in entities["emitters"].items():
        if obj.get("sequence_torch"):
            weights["emitters:"+str(key)] = 1. if obj.get("initially_lit") else 0.
    for definition in arena["world_sequences"]["sequences"].values():
        for reference in definition["targets"]:
            obj = resolve(arena, reference)
            if obj is not None:
                weights.setdefault(ref_key(reference), float(bool(obj.get("initially_lit", obj.get("enabled", True)))))
    records = dict(arena["sequence_state"]["sequences"])
    if preview:
        records[preview["id"]] = preview
    controlled = {}
    for record_id, record in records.items():
        definition, sites = record["definition"], record["sites"]
        for index, site in enumerate(sites):
            weight = site_weight(definition, sites, site, record["elapsed"])
            if "ref" in site:
                key = ref_key(site["ref"])
                if arena["sequence_state"].get("owners", {}).get(key, record_id) == record_id or (preview and record_id == preview["id"]):
                    controlled[key] = weight
            elif weight > 0:
                key = f"sequence_path:{record_id}:{index}"
                emitter = g_effects.make_default_fire_emitter(tile_position(site["point"], arena["tile_map"]))
                emitter.update(seed=fire_seed(key), size={"x": 8., "y": 14.},
                               area_size={"x": 4., "y": 2.}, opacity=.94*weight)
                emitter["light"].update(enabled=index % max(1, math.ceil(len(sites)/MAX_PATH_LIGHTS)) == 0,
                                        intensity=.5*weight, radius=45.)
                entities["emitters"][key] = emitter
    weights.update(controlled)
    weights.update(arena["sequence_state"].get("manual_activation", {}))
    if preview:
        # Preview must reflect authored timing even when gameplay has a manual override.
        for site in preview["sites"]:
            if "ref" in site:
                weights[ref_key(site["ref"])] = site_weight(preview["definition"], preview["sites"], site, preview["elapsed"])
    for key, weight in weights.items():
        collection, object_id = key.split(":", 1)
        obj = entities.get(collection, {}).get(object_id)
        if obj is None or collection not in {"lights", "emitters"} or (collection == "emitters" and obj.get("type") != "fire"):
            continue
        obj = copy.deepcopy(obj)
        obj["enabled"] = weight > .0001
        if collection == "lights":
            obj["intensity"] = obj.get("intensity", 1.) * weight
            obj["gameplay_intensity"] = obj.get("gameplay_intensity", 1.) * weight
        else:
            obj["opacity"] = obj.get("opacity", 1.) * weight
            obj["activation_gain"] = weight
            if "light" in obj:
                obj["light"]["intensity"] = obj["light"].get("intensity", .8) * weight
        entities[collection][object_id] = obj
    return entities


def reset_sequence(arena, identity):
    record = arena["sequence_state"]["sequences"].pop(identity, None)
    if record:
        for site in record["sites"]:
            if "ref" in site and arena["sequence_state"].get("owners", {}).get(ref_key(site["ref"]), identity) == identity:
                arena["sequence_state"]["activation"].pop(ref_key(site["ref"]), None)
                arena["sequence_state"].setdefault("owners", {})[ref_key(site["ref"])] = None
                arena["sequence_state"].get("manual_activation", {}).pop(ref_key(site["ref"]), None)
    arena["sequence_state"]["facts"].pop("sequence_completed:"+identity, None)
    arena["sequence_state"]["events"][:] = [event for event in arena["sequence_state"]["events"] if event["source"] != identity]
    return arena


def reset_trigger(arena, identity):
    arena["sequence_state"]["triggers"].pop(identity, None)
    arena["sequence_runtime"]["occupancy"].pop(identity, None)
    arena["sequence_state"]["events"][:] = [event for event in arena["sequence_state"]["events"] if event["source"] != identity]
    return arena


def reset_encounter(arena, identity):
    record = arena["sequence_state"]["encounters"].pop(identity, None)
    if record:
        for enemy_id in record["members"]:
            arena["entities"].get("brains", {}).pop(enemy_id, None)
        prefix = f"encounter:{identity}:"
        spawns = arena["puzzle_state"]["spawns"]
        for key in list(spawns):
            if key.startswith(prefix):
                arena["entities"].get("brains", {}).pop(spawns[key], None)
                del spawns[key]
    arena["sequence_state"]["facts"].pop("encounter_completed:"+identity, None)
    arena["sequence_state"]["events"][:] = [event for event in arena["sequence_state"]["events"] if event["source"] != identity]
    import g_update_and_render as game
    game.rebuild_actor_collision_index(arena["tile_map"], arena["player_info"], arena["entities"])
    return arena


def validate_world(arena):
    result = []
    definitions = arena["world_sequences"]
    for identity, definition in definitions["sequences"].items():
        result.extend(definition["label"]+": "+error for error in validate_sequence(arena, definition))
    for identity, area in definitions["triggers"].items():
        if not area["cells"]:
            result.append(area["label"]+": empty area")
        for field in ("on_enter", "on_exit"):
            if area[field] not in data.HANDLERS:
                result.append(area["label"]+": unknown "+field)
            if area[field] == "start_linked_sequence" and area["sequence"] not in definitions["sequences"]:
                result.append(area["label"]+": missing linked sequence")
    for identity, encounter in definitions["encounters"].items():
        label = encounter.get("label", identity)
        if not encounter["spawns"]:
            result.append(label+": no spawn entries")
        for entry in encounter["spawns"]:
            obj = puzzles.get_object(arena, entry["marker"])
            if obj is None or obj["type"] != "puzzle spawn":
                result.append(label+": missing spawn marker")
            if entry.get("type") != "red head":
                result.append(label+": unsupported enemy type")
        if encounter.get("on_complete", "none") not in data.HANDLERS:
            result.append(label+": unknown completion handler")
        if encounter.get("on_complete") == "courtyard_completed" and puzzles.get_object(arena, encounter.get("data", {}).get("door")) is None:
            result.append(label+": missing exit door")
    return result
