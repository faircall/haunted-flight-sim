"""Editor controls and placeholder presentation for the puzzle milestone."""
import pyray as pr

import g_puzzles as p
import g_ui


def update_input(arena, enabled, dt):
    runtime = arena["puzzle_runtime"]
    runtime["message_time"] = max(0.0, runtime["message_time"] - dt)
    if not enabled:
        runtime.update(keypad=None, digits="")
        return arena
    target = p.nearest_interactable(arena)
    if runtime.get("keypad"):
        keypad = p.get_object(arena, runtime["keypad"])
        if keypad is None or target is None or target["persistent_id"] != keypad["persistent_id"]:
            runtime.update(keypad=None, digits="")
            return arena
        if pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE):
            runtime.update(keypad=None, digits="")
            return arena
        value = pr.get_char_pressed()
        while value:
            if 48 <= value <= 57 and len(runtime["digits"]) < 4:
                runtime["digits"] += chr(value)
            value = pr.get_char_pressed()
        if pr.is_key_pressed(pr.KeyboardKey.KEY_BACKSPACE):
            runtime["digits"] = runtime["digits"][:-1]
        if pr.is_key_pressed(pr.KeyboardKey.KEY_ENTER) or pr.is_key_pressed(pr.KeyboardKey.KEY_KP_ENTER):
            arena = p.interact(arena, keypad["persistent_id"], runtime["digits"])
            runtime["digits"] = ""
        return arena
    if target is not None and pr.is_key_pressed(pr.KeyboardKey.KEY_E):
        # Discard text typed before opening the keypad.
        while pr.get_char_pressed():
            pass
        arena = p.interact(arena, target["persistent_id"])
    return arena


def draw_world(arena, camera, editor=False):
    for obj in p.objects(arena):
        state = p.object_state(arena, obj)
        if state.get("collected") and not editor:
            continue
        if obj["type"] == "puzzle spawn" and not editor:
            continue
        box = p.bounds(obj, arena["tile_map"])
        rect = pr.Rectangle(round(box["x"] - camera.x), round(box["y"] - camera.y), box["width"], box["height"])
        color = pr.Color(*p.data.OBJECTS[obj["type"]]["color"], 255)
        if state.get("open") or state.get("collected"):
            pr.draw_rectangle_lines_ex(rect, 1, color)
        else:
            pr.draw_rectangle_rec(rect, color)
        if obj["type"] == "puzzle lever":
            pr.draw_line(int(rect.x + 4), int(rect.y + 7),
                         int(rect.x + (7 if state.get("active") else 1)), int(rect.y), pr.WHITE)
        elif obj["type"] == "puzzle keypad":
            for x in (2, 5):
                for y in (2, 5):
                    pr.draw_rectangle(int(rect.x + x), int(rect.y + y), 1, 1, pr.WHITE)


def draw_overlay(arena, camera, playing):
    target = p.nearest_interactable(arena) if playing else None
    for obj in p.objects(arena):
        state = p.object_state(arena, obj)
        if playing and (state.get("collected") or obj["type"] == "puzzle spawn"):
            continue
        box = p.bounds(obj, arena["tile_map"])
        status = ""
        if obj["type"] in p.DOOR_TYPES:
            status = "open" if state.get("open") else "unlocked" if state.get("unlocked") else "locked"
        elif obj["type"] == "puzzle lever":
            status = "on" if state.get("active") else "off"
        labels = [f"{obj['label']} [{obj['puzzle_group']}]"]
        if status or target is obj:
            labels.append(("[E] " if target is obj else "") + (status or "use"))
        for index, label in enumerate(labels):
            x = round(box["x"] + box["width"] / 2 - camera.x - pr.measure_text(label, 8) / 2)
            y = round(box["y"] - camera.y - 11 * (len(labels) - index))
            if -20 < y < 270 and -pr.measure_text(label, 8) < x < 480:
                pr.draw_text(label, x + 1, y + 1, 8, pr.BLACK)
                pr.draw_text(label, x, y, 8, pr.YELLOW if target is obj else pr.WHITE)
    runtime = arena["puzzle_runtime"]
    if playing and runtime.get("keypad"):
        pr.draw_rectangle(115, 80, 250, 95, pr.Color(16, 19, 30, 255))
        pr.draw_rectangle_lines(115, 80, 250, 95, pr.SKYBLUE)
        pr.draw_text("KEYPAD", 130, 90, 10, pr.WHITE)
        digits = runtime["digits"].ljust(4, "_")
        pr.draw_text("  ".join(digits), 175, 111, 20, pr.SKYBLUE)
        pr.draw_text("0-9: type   Enter: submit", 130, 143, 8, pr.WHITE)
        pr.draw_text("Backspace: erase   Esc: cancel", 130, 157, 8, pr.WHITE)
    if playing and runtime["message_time"] > 0:
        # The internal screen is 480px wide; wrap longer authoring diagnostics.
        words, lines, line = runtime["message"].split(), [], ""
        for word in words:
            candidate = (line + " " + word).strip()
            if pr.measure_text(candidate, 8) > 450:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        for i, text in enumerate(lines):
            y = 249 - (len(lines) - 1 - i) * 10
            pr.draw_rectangle(10, y - 1, 460, 10, pr.Color(10, 10, 18, 220))
            pr.draw_text(text, 14, y, 8, pr.WHITE)


def inspect(ui_state, editor_state, obj):
    obj["puzzle_group"], _ = g_ui.ui_number_input_int(
        ui_state, "puzzle:group", "puzzle group", obj["puzzle_group"], 1, 999)
    g_ui.ui_label(ui_state, "puzzle:link", "Same group = connected", font_size=8)
    g_ui.ui_label(ui_state, "puzzle:id", obj["persistent_id"][-12:], font_size=8)
    if obj["type"] in ("key door", "authored door"):
        obj["on_unlock"], _ = g_ui.ui_dropdown(
            ui_state, "puzzle:handler", "handler", obj["on_unlock"], list(p.data.HANDLERS))
    if obj["type"] == "puzzle keypad":
        code, changed = g_ui.ui_number_input_int(ui_state, "puzzle:code", "code", int(obj.get("code", "0451")), 0, 9999)
        if changed:
            obj["code"] = f"{code:04d}"
        g_ui.ui_label(ui_state, "puzzle:digits", "Code: " + obj.get("code", "0451"), font_size=8)
    hints = {
        "authored door": ("Needs key + pulled lever", "and one spawn marker.", "Edit g_puzzle_data.py"),
        "key door": ("Needs key in same group.", "E: unlock, then E: open."),
        "lever door": ("Lever opens/closes it.", "E also works once unlocked."),
        "code door": ("Use keypad in same group.",),
        "puzzle spawn": ("Ritual enemy spawn point.", "Place on clear floor."),
        "puzzle key": ("E to collect; key is kept.",),
        "puzzle lever": ("E: toggle all lever doors", "in this puzzle group."),
        "puzzle keypad": ("E: enter four digits.",),
    }
    for index, hint in enumerate(hints.get(obj["type"], ())):
        g_ui.ui_label(ui_state, f"puzzle:hint:{index}", hint, font_size=8)
    if g_ui.ui_button(ui_state, "puzzle:reset", "Reset puzzle progress"):
        editor_state["reset_puzzles_requested"] = True
    g_ui.ui_label(ui_state, "puzzle:reset_scope", "Resets ALL groups.", font_size=8)
    if editor_state.get("puzzle_reset_blocked"):
        g_ui.ui_label(ui_state, "puzzle:reset_blocked", "Move actors off doors.", font_size=8)
