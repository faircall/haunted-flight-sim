"""Shared modal descriptions, choices and inventory; callbacks take arena/event."""
import pyray as pr
import g_inventory as inventory
import g_interaction_data as data
import g_narrative_text as text
import g_puzzles as puzzles

DIALOGUE_FADE_IN_SECONDS = 0.45
DIALOGUE_FADE_OUT_SECONDS = 0.3
PAGE_FADE_SECONDS = 0.18
PROMPT_FADE_SECONDS = 0.25


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def tint(color, opacity):
    if isinstance(color, tuple):
        color = pr.Color(*color)
    return pr.Color(color.r, color.g, color.b, round(color.a * opacity))


def update_prompt(runtime, candidate, dt):
    prompt = runtime.setdefault("prompt", {"identity": None, "label": "", "amount": 0.0})
    identity = candidate[:2] if candidate else None
    same = identity is not None and identity == prompt["identity"]
    prompt["amount"] = max(0.0, min(1.0,
        prompt["amount"] + (1 if same else -1) * dt / PROMPT_FADE_SECONDS))
    if prompt["amount"] == 0.0:
        prompt["identity"] = identity
        prompt["label"] = candidate[2].get("label", candidate[2]["type"]) if candidate else ""


def finish_dialogue(arena, modal):
    arena["interaction_runtime"]["modal"] = None
    if modal.get("cancelled"):
        return arena
    choices = modal["choices"]
    choice = choices[modal["choice"]] if choices else {}
    handler = choice.get("handler") if choices else modal.get("on_complete")
    if handler == "pickup":
        return take(arena, modal["target"])
    if handler:
        callback = data.HANDLERS.get(handler)
        if callback is None:
            return open_dialogue(arena, ["Unknown dialogue handler: " + handler])
        return callback(arena, {"target": modal["target"], "choice": modal["choice"]})
    return arena


def ensure(arena):
    arena = inventory.ensure(arena)
    if "interaction_runtime" not in arena:
        arena = arena.set("interaction_runtime", {"modal": None, "selected": 0})
    return arena


def open_dialogue(arena, pages, choices=None, target=None, on_complete=None, speaker=None):
    arena = ensure(arena)
    arena["interaction_runtime"]["modal"] = dict(kind="dialogue", pages=list(pages) or [""],
        page=0, scroll=0, choices=choices or [], choice=max(0, len(choices or []) - 1), target=target,
        on_complete=on_complete, speaker=speaker, fade_elapsed=0.0)
    return arena


def nearest(arena):
    import g_update_and_render as game
    tile_map = arena["tile_map"]
    pos = game.tile_and_offset_to_absolute(tile_map, arena["player_info"]["position"])
    candidates = []
    puzzle = puzzles.nearest_interactable(arena)
    for collection in ("pickups", "brains", "puzzles"):
        for key, obj in arena["entities"].get(collection, {}).items():
            if collection == "puzzles":
                if obj is not puzzle:
                    continue
            elif collection == "brains" and not obj.get("description_id"):
                continue
            destination = puzzles.world_position(obj, tile_map)
            distance = sum((pos[a] - destination[a]) ** 2 for a in ("x", "y"))
            if distance > 28 ** 2:
                continue
            if collection != "puzzles":
                steps = max(1, int(distance ** .5 / 2))
                if any(game.position_collides_within_tile_shape(
                    game.get_tile_index_and_offset_from_pos({a: pos[a] + (destination[a] - pos[a]) * i / steps
                                                            for a in ("x", "y")}, tile_map), tile_map)
                       for i in range(1, steps)):
                    continue
            candidates.append((distance, collection, str(key), key, obj))
    if not candidates:
        return None
    _, collection, _, key, obj = min(candidates, key=lambda c: c[:3])
    return collection, key, obj


def pickup_item(obj):
    if obj["type"] == "puzzle key":
        return {"kind": "key", "group": str(obj["puzzle_group"]), "count": 1}
    if obj["type"] == "health_pickup":
        return {"kind": "health", "value": obj.get("value", 25), "count": 1}
    return {"kind": "ammo", "count": obj.get("value", 20)}


def take(arena, target):
    collection, key = target
    obj = arena["entities"].get(collection, {}).get(key)
    if obj is None or (collection == "puzzles" and puzzles.object_state(arena, obj).get("collected")):
        return open_dialogue(arena, ["This item is no longer here."])
    if not inventory.add(arena["player_info"]["inventory"], pickup_item(obj)):
        return open_dialogue(arena, ["full"])
    if collection == "puzzles":
        puzzles.object_state(arena, obj)["collected"] = True
    else:
        arena["entities"][collection].pop(key)
    inventory.sync_ammo(arena["player_info"])
    arena["puzzle_runtime"]["sounds"].append({"type": "pickup_health" if obj["type"] == "health_pickup" else "pickup_ammo",
        "source_id": "player", "source_kind": "player", "world_position": puzzles.world_position(obj, arena["tile_map"])})
    return arena


def activate(arena, candidate):
    collection, key, obj = candidate
    if collection == "pickups" or obj["type"] == "puzzle key":
        return open_dialogue(arena, [text.localize(data.ITEMS[pickup_item(obj)["kind"]]["name"]) + "\n" + text.localize("take")],
                             [{"label": "yes", "handler": "pickup"}, {"label": "no"}], [collection, key])
    identity = obj.get("description_id", "old_inscription" if obj["type"] == "inspectable" else None)
    if identity:
        definition = data.DESCRIPTIONS.get(identity)
        if definition is None:
            return open_dialogue(arena, ["Unknown description: " + identity])
        return open_dialogue(arena, definition["pages"], definition.get("choices"), obj.get("persistent_id", str(key)),
                             definition.get("on_complete"), definition.get("speaker"))
    return puzzles.interact(arena, obj["persistent_id"])


def update(arena, enabled, assets):
    arena = ensure(arena)
    runtime = arena["interaction_runtime"]
    modal = runtime["modal"]
    if not enabled:
        runtime["modal"] = None
        runtime.pop("prompt", None)
        return arena, bool(modal)
    dt = max(0.0, pr.get_frame_time())
    candidate = nearest(arena) if not modal and not arena["puzzle_runtime"].get("keypad") else None
    update_prompt(runtime, candidate, dt)
    pressed = lambda name: pr.is_key_pressed(getattr(pr.KeyboardKey, "KEY_" + name))
    if modal:
        if "closing_elapsed" in modal:
            modal["closing_elapsed"] += dt
            if modal["closing_elapsed"] >= DIALOGUE_FADE_OUT_SECONDS:
                arena = finish_dialogue(arena, modal)
            return arena, True
        if pressed("ESCAPE") or (modal["kind"] == "inventory" and pressed("TAB")):
            if modal["kind"] == "inventory":
                runtime["modal"] = None
            else:
                modal.update(closing_elapsed=0.0, cancelled=True)
            return arena, True
        if modal["kind"] == "inventory":
            slots = arena["player_info"]["inventory"]
            delta = int(pressed("RIGHT")) - int(pressed("LEFT")) + 4 * (int(pressed("DOWN")) - int(pressed("UP")))
            runtime["selected"] = (runtime["selected"] + delta) % len(slots)
            if pressed("ENTER") or pressed("E"):
                modal["message"] = inventory.use(arena["player_info"], runtime["selected"]) if slots[runtime["selected"]] else ""
            if pressed("R"):
                overflow = arena["player_info"].get("inventory_overflow", [])
                arena["player_info"]["inventory_overflow"] = [item for item in overflow if not inventory.add(slots, item)]
                inventory.sync_ammo(arena["player_info"])
            return arena, True
        modal["fade_elapsed"] = min(DIALOGUE_FADE_IN_SECONDS,
            modal.get("fade_elapsed", DIALOGUE_FADE_IN_SECONDS) + dt)
        if "page_elapsed" in modal:
            modal["page_elapsed"] += dt
            if modal["page_elapsed"] >= PAGE_FADE_SECONDS and "next_page" in modal:
                modal["page"], modal["scroll"] = modal.pop("next_page")
            if modal["page_elapsed"] >= 2 * PAGE_FADE_SECONDS:
                del modal["page_elapsed"]
            return arena, True
        choices = modal["choices"]
        if choices and (pressed("LEFT") or pressed("RIGHT")):
            modal["choice"] = (modal["choice"] + (1 if pressed("RIGHT") else -1)) % len(choices)
        if pressed("E") or pressed("ENTER"):
            lines = text.wrap(assets, modal["pages"][modal["page"]], 416)
            if modal["scroll"] + 4 < len(lines):
                modal.update(page_elapsed=0.0, next_page=(modal["page"], modal["scroll"] + 4))
            elif modal["page"] + 1 < len(modal["pages"]):
                modal.update(page_elapsed=0.0, next_page=(modal["page"] + 1, 0))
            else:
                modal["closing_elapsed"] = 0.0
        return arena, True
    if arena["puzzle_runtime"].get("keypad"):
        return arena, False
    if pressed("TAB"):
        runtime["modal"] = {"kind": "inventory", "message": ""}
        return arena, True
    if candidate and pressed("E"):
        return activate(arena, candidate), True
    return arena, False


def draw(arena, assets):
    background_opacity = (max(0.0, min(1.0, data.NARRATIVE_BACKGROUND_OPACITY))
        if data.SHOW_NARRATIVE_BACKGROUNDS else 0.0)
    runtime = arena.get("interaction_runtime", {})
    modal = runtime.get("modal")
    prompt = runtime.get("prompt", {})
    prompt_opacity = ease(prompt.get("amount", 0.0))
    if prompt_opacity:
        if background_opacity:
            pr.draw_rectangle(16, 238, 448, 20, tint(pr.Color(12, 14, 23, 240), prompt_opacity * background_opacity))
        text.draw(assets, "[E] " + prompt["label"] + "    [Tab] Inventory", 24, 242, tint(pr.WHITE, prompt_opacity))
    if not modal:
        return
    progress = max(0.0, min(1.0, modal.get("fade_elapsed", DIALOGUE_FADE_IN_SECONDS) / DIALOGUE_FADE_IN_SECONDS))
    opacity = ease(progress) * (1.0 - ease(modal.get("closing_elapsed", 0.0) / DIALOGUE_FADE_OUT_SECONDS))
    page_elapsed = modal.get("page_elapsed")
    text_opacity = opacity
    if page_elapsed is not None:
        text_opacity *= ease(abs(page_elapsed / PAGE_FADE_SECONDS - 1.0))
    def faded(color):
        return tint(color, opacity)

    if modal["kind"] == "inventory":
        pr.draw_rectangle(0, 0, 480, 270, faded(pr.Color(0, 0, 0, 120)))
        pr.draw_rectangle(16, 12, 448, 246, pr.Color(14, 18, 27, 255))
        text.draw(assets, "inventory", 28, 22)
        slots = arena["player_info"]["inventory"]
        for i, item in enumerate(slots):
            x, y = 28 + i % 4 * 106, 44 + i // 4 * 49
            pr.draw_rectangle_lines(x, y, 100, 46, pr.YELLOW if i == runtime["selected"] else pr.GRAY)
            label = (text.localize(data.ITEMS[item["kind"]]["name"]) if item else text.localize("empty"))
            for n, line in enumerate(text.wrap(assets, label, 92)[:2]):
                text.draw(assets, line, x + 4, y + 3 + n * 14)
            if item:
                text.draw(assets, str(item["count"]) + (" / " + item["group"] if item["kind"] == "key" else ""), x + 4, y + 31)
        item = slots[runtime["selected"]]
        description = modal.get("message") or (data.ITEMS[item["kind"]]["description"] if item else "")
        for i, line in enumerate(text.wrap(assets, description, 416)[:4]):
            text.draw(assets, line, 28, 146 + i * 15)
        text.draw(assets, "inventory_controls", 28, 220)
        if arena["player_info"].get("inventory_overflow"):
            text.draw(assets, "R: claim items retained from an older save", 28, 240, pr.YELLOW)
    else:
        if background_opacity:
            pr.draw_rectangle(0, 0, 480, 270, tint(pr.Color(0, 0, 0, 120), opacity * background_opacity))
        if modal.get("speaker"):
            if background_opacity:
                pr.draw_rectangle(16, 124, 448, 20, tint(pr.Color(14, 18, 27, 255), opacity * background_opacity))
            text.draw(assets, modal["speaker"], 28, 128, faded(pr.YELLOW))
        if background_opacity:
            pr.draw_rectangle(16, 144, 448, 114, tint(pr.Color(14, 18, 27, 255), opacity * background_opacity))
        lines = text.wrap(assets, modal["pages"][modal["page"]], 416)
        for i, line in enumerate(lines[modal["scroll"]:modal["scroll"] + 4]):
            text.draw(assets, line, 28, 154 + i * 15, tint(pr.WHITE, text_opacity))
        final = modal["page"] == len(modal["pages"]) - 1 and modal["scroll"] + 4 >= len(lines)
        if final and modal["choices"]:
            x = 28
            marker_width = text.width(assets, "> ")
            for i, choice in enumerate(modal["choices"]):
                label = text.localize(choice["label"])
                if i == modal["choice"]:
                    text.draw(assets, ">", x, 220, tint(pr.YELLOW, text_opacity))
                text.draw(assets, label, x + marker_width, 220, tint(pr.YELLOW if i == modal["choice"] else pr.WHITE, text_opacity))
                x += marker_width + text.width(assets, label) + 20
        text.draw(assets, "dialogue_controls", 28, 242, faded(pr.WHITE))
