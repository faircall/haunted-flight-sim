"""Immediate-mode sequence authoring. Drafts and previews never touch progress."""
import copy
import math

import pyray as pr
import g_ui
import g_sequences as s
import g_puzzles as p

TOOLS = ("Select", "Pick existing", "Place torches", "Circle", "Fire path", "Trigger rectangle", "Trigger paint", "Move member", "Insert member", "Sound origin")


def state(editor):
    return editor.setdefault("sequence_editor", {"tool": "Select", "kind": "sequences", "selected": "",
        "draft": None, "scroll": 0., "member": 0, "preview": None, "audition": False,
        "circle_count": 6, "circle_angle": 0., "circle_reverse": False, "circle_fire": False, "error": ""})


def toolbar(ui, editor):
    st = state(editor)
    old = st["tool"]
    st["tool"], changed = g_ui.ui_dropdown(ui, "sequence:tool", "", old, TOOLS, pr.Rectangle(82, 2, 128, 16), 8)
    if changed:
        st["draft"] = None
        st.pop("append_to", None)
    if g_ui.ui_button(ui, "sequence:finish", "Finish", pr.Rectangle(218, 2, 58, 16)):
        st["finish"] = True
    if g_ui.ui_button(ui, "sequence:cancel", "Cancel", pr.Rectangle(282, 2, 58, 16)):
        st["draft"] = None
        st["tool"] = "Select"
        st.pop("append_to", None)
    if ui.get("open_dropdown_id") not in {"toolbar:mode", "sequence:tool"}:
        pr.draw_text("Enter finish | Backspace undo | Esc cancel", 4, 23, 8, g_ui.UI_MUTED)


def pick(arena, point, collections=("emitters", "lights")):
    candidates = []
    for collection in collections:
        for identity, obj in arena["entities"].get(collection, {}).items():
            if collection == "emitters" and obj.get("type") != "fire":
                continue
            pos = s.world(obj, arena["tile_map"])
            distance = math.hypot(pos["x"]-point["x"], pos["y"]-point["y"])
            if distance < 12:
                candidates.append((distance, str(identity), {"collection": collection, "id": identity}))
    return min(candidates, key=lambda item: item[:2])[2] if candidates else None


def circle_points(centre, edge, count, angle=0., reverse=False):
    radius = math.hypot(edge["x"]-centre["x"], edge["y"]-centre["y"])
    count = max(2, min(64, int(count)))
    return [{"x": centre["x"]+radius*math.cos(math.radians(angle)+( -1 if reverse else 1)*i*math.tau/count),
             "y": centre["y"]+radius*math.sin(math.radians(angle)+( -1 if reverse else 1)*i*math.tau/count)} for i in range(count)]


def begin_draft(st):
    st["draft"] = {"tool": st["tool"], "entries": [], "points": [], "cells": [], "centre": None, "edge": None}
    return st["draft"]


def finish_draft(arena, st):
    draft = st.get("draft")
    if not draft:
        return arena
    tool = draft["tool"]
    if tool.startswith("Trigger"):
        if not draft["cells"]:
            return arena
        identity = draft.get("replace") or s.new_id("trigger")
        definition = copy.deepcopy(arena["world_sequences"]["triggers"].get(identity)) or s.make_trigger(draft["cells"])
        definition["cells"] = copy.deepcopy(draft["cells"])
        available = arena["world_sequences"]["sequences"]
        if not draft.get("replace"):
            definition["sequence"] = st["selected"] if st["selected"] in available else next(iter(available), "")
        arena["world_sequences"]["triggers"][identity] = definition
        st.update(kind="triggers", selected=identity)
    else:
        definition = s.make_sequence()
        if tool == "Fire path":
            if len(draft["points"]) < 2:
                st["error"] = "A path needs two points."
                return arena
            definition.update(mode="path", points=copy.deepcopy(draft["points"]), label="Fire path")
        else:
            entries = draft["entries"]
            if tool == "Circle":
                if not draft["centre"] or not draft["edge"]:
                    return arena
                entries = [{"point": point} for point in circle_points(draft["centre"], draft["edge"], st["circle_count"], st["circle_angle"], st["circle_reverse"])]
                definition["closed"] = True
            if not entries:
                return arena
            if tool == "Circle" and st.get("circle_fire"):
                definition.update(mode="path", points=[entry["point"] for entry in entries], label="Fire circle")
            else:
                refs = [entry["ref"] if "ref" in entry else s.create_torch(arena, entry["point"]) for entry in entries]
                definition["targets"] = refs
        if st.get("append_to") and st["append_to"] in arena["world_sequences"]["sequences"]:
            identity = st.pop("append_to")
            arena["world_sequences"]["sequences"][identity]["targets"].extend(definition["targets"])
        else:
            identity = s.new_id("sequence")
            arena["world_sequences"]["sequences"][identity] = definition
        st.update(kind="sequences", selected=identity)
    st.update(draft=None, tool="Select", scroll=0., error="")
    return arena


def sample_rectangle(a, b, tm):
    ax, ay = int(a["x"]//tm["tile_width"]), int(a["y"]//tm["tile_height"])
    bx, by = int(b["x"]//tm["tile_width"]), int(b["y"]//tm["tile_height"])
    return [[x, y] for y in range(max(0,min(ay,by)), min(tm["map_height"]-1,max(ay,by))+1)
            for x in range(max(0,min(ax,bx)), min(tm["map_width"]-1,max(ax,bx))+1)]


def update_editor(arena, editor, ui, camera, active, dt):
    st = state(editor)
    if not active:
        st.update(draft=None, preview=None, drag=None)
        st.pop("append_to", None)
        return arena
    if st.pop("demo", False):
        try:
            arena = create_courtyard(arena, {"x": camera.x+145, "y": camera.y+140})
            st.update(kind="sequences", selected=arena["world_sequences"]["demo"]["sequence"], error="Demo placed near camera.")
        except ValueError as error:
            st["error"] = str(error)
    if st.pop("finish", False):
        arena = finish_draft(arena, st)
    command = st.pop("command", None)
    if command:
        kind, identity = st["kind"], st["selected"]
        try:
            if command == "reset":
                if kind == "sequences":
                    arena = s.reset_sequence(arena, identity)
                elif kind == "encounters":
                    arena = s.reset_encounter(arena, identity)
                else:
                    arena = s.reset_trigger(arena, identity)
            elif command == "test":
                if kind == "sequences":
                    arena = s.start_sequence(arena, identity)
                elif kind == "encounters":
                    arena = s.spawn_encounter(arena, identity)
            elif command == "retry" and arena["sequence_runtime"]["errors"]:
                event = arena["sequence_runtime"]["errors"].pop()["event"]
                arena["sequence_state"]["events"].append(event)
        except Exception as error:
            st["error"] = str(error)
    if ui.get("focused_id") is not None or ui.get("open_dropdown_id"):
        return arena
    if pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE):
        st.update(draft=None, tool="Select", preview=None, drag=None)
        st.pop("append_to", None)
        return arena
    draft = st.get("draft")
    if pr.is_key_pressed(pr.KeyboardKey.KEY_BACKSPACE) and draft:
        key = "points" if draft["tool"] == "Fire path" else "cells" if draft["tool"].startswith("Trigger") else "entries"
        if draft[key]:
            draft[key].pop()
    if pr.is_key_pressed(pr.KeyboardKey.KEY_ENTER):
        arena = finish_draft(arena, st)
    mouse = g_ui.get_mouse_position()
    point = {"x": mouse.x+camera.x, "y": mouse.y+camera.y}
    can_world = not ui.get("mouse_captured") and mouse.y >= 38 and mouse.x < 306
    pressed = can_world and g_ui.interactive_mouse_left_pressed()
    held = can_world and g_ui.interactive_mouse_left_down()
    released = pr.is_mouse_button_released(pr.MouseButton.MOUSE_BUTTON_LEFT)
    tool = st["tool"]
    if pressed and tool in ("Pick existing", "Place torches", "Circle", "Fire path", "Trigger rectangle", "Trigger paint"):
        draft = st["draft"] or begin_draft(st)
        if tool == "Pick existing":
            ref = pick(arena, point)
            if ref and not any(entry.get("ref") == ref for entry in draft["entries"]):
                draft["entries"].append({"ref": ref})
        elif tool == "Place torches":
            draft["entries"].append({"point": point})
        elif tool == "Fire path":
            draft["points"].append(point)
        elif tool in ("Circle", "Trigger rectangle"):
            draft.update(centre=point, edge=point, dragging=True)
    if draft and draft["tool"] in ("Circle", "Trigger rectangle") and draft.get("dragging"):
        if held:
            draft["edge"] = point
        if draft["tool"] == "Trigger rectangle":
            draft["cells"] = sample_rectangle(draft["centre"], draft["edge"], arena["tile_map"])
        if released:
            draft["dragging"] = False
    if tool == "Trigger paint" and held:
        draft = st["draft"] or begin_draft(st)
        current = [int(point["x"]//arena["tile_map"]["tile_width"]), int(point["y"]//arena["tile_map"]["tile_height"])]
        previous = draft.get("paint_previous") or current
        steps = max(1, abs(current[0]-previous[0]), abs(current[1]-previous[1]))
        for step in range(steps+1):
            cell = [round(previous[axis]+(current[axis]-previous[axis])*step/steps) for axis in (0,1)]
            if 0 <= cell[0] < arena["tile_map"]["map_width"] and 0 <= cell[1] < arena["tile_map"]["map_height"]:
                if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT):
                    if cell in draft["cells"]:
                        draft["cells"].remove(cell)
                elif cell not in draft["cells"]:
                    draft["cells"].append(cell)
        draft["paint_previous"] = current
    elif draft:
        draft.pop("paint_previous", None)
    definition = arena["world_sequences"].get(st["kind"], {}).get(st["selected"])
    if pressed and tool == "Select":
        ref = pick(arena, point)
        if ref:
            for identity, sequence in arena["world_sequences"]["sequences"].items():
                if ref in sequence["targets"]:
                    st.update(kind="sequences", selected=identity, member=sequence["targets"].index(ref), scroll=0.)
                    break
        else:
            cell = [int(point["x"]//arena["tile_map"]["tile_width"]), int(point["y"]//arena["tile_map"]["tile_height"])]
            for identity, area in arena["world_sequences"]["triggers"].items():
                if cell in area["cells"]:
                    st.update(kind="triggers", selected=identity, scroll=0.)
                    break
    if definition and st["kind"] == "sequences":
        if pressed and tool == "Sound origin":
            definition["sound_origin"] = pick(arena, point, ("emitters", "lights", "puzzles"))
            st["tool"] = "Select"
        if tool == "Move member":
            points = definition["points"]
            if pressed:
                if definition["mode"] == "path" and points:
                    index = min(range(len(points)), key=lambda i: math.hypot(points[i]["x"]-point["x"], points[i]["y"]-point["y"]))
                    if math.hypot(points[index]["x"]-point["x"], points[index]["y"]-point["y"]) < 12:
                        st["drag"] = {"point": index}
                else:
                    ref = pick(arena, point)
                    if ref in definition["targets"]:
                        st["drag"] = {"ref": ref}
            if st.get("drag") and held:
                if "point" in st["drag"]:
                    definition["points"][st["drag"]["point"]] = point
                else:
                    resolve = s.resolve(arena, st["drag"]["ref"])
                    if resolve:
                        resolve["position"] = s.tile_position(point, arena["tile_map"])
            if released:
                st["drag"] = None
        if pressed and tool == "Insert member":
            points = definition_points(arena, definition)
            if len(points) > 1:
                index = min(range(len(points) if definition.get("closed") else len(points)-1), key=lambda i: segment_distance(point, points[i], points[(i+1)%len(points)]))
                if definition["mode"] == "path":
                    definition["points"].insert(index+1, point)
                else:
                    ref = pick(arena, point) or s.create_torch(arena, point)
                    if ref not in definition["targets"]:
                        definition["targets"].insert(index+1, ref)
                st["tool"] = "Select"
    preview = st.get("preview")
    if preview and preview["id"] in arena["world_sequences"]["sequences"]:
        current = arena["world_sequences"]["sequences"][preview["id"]]
        if current != preview["definition"]:
            preview.update(definition=copy.deepcopy(current), sites=s.schedule(arena, current))
    if preview and preview.get("playing"):
        before = preview["elapsed"]
        preview["elapsed"] = min(sequence_end(preview), before+dt)
        if st["audition"]:
            audition(arena, preview, before, preview["elapsed"])
        if preview["elapsed"] >= sequence_end(preview):
            preview["playing"] = False
    return arena


def segment_distance(point, a, b):
    dx, dy = b["x"]-a["x"], b["y"]-a["y"]
    t = max(0., min(1., ((point["x"]-a["x"])*dx+(point["y"]-a["y"])*dy)/max(.0001,dx*dx+dy*dy)))
    return math.hypot(point["x"]-a["x"]-t*dx, point["y"]-a["y"]-t*dy)


def definition_points(arena, definition):
    if definition["mode"] == "path":
        return definition["points"]
    return [s.world(s.resolve(arena, ref), arena["tile_map"]) for ref in definition["targets"] if s.resolve(arena, ref)]


def member_order(definition):
    members = definition["points"] if definition["mode"] == "path" else definition["targets"]
    indices = list(range(len(members)))
    rotates = definition["mode"] == "objects" or definition["closed"]
    if indices and rotates:
        start = int(definition["start_index"]) % len(indices)
        indices = indices[start:]+indices[:start]
    if definition["reverse"]:
        indices = indices[:1]+list(reversed(indices[1:])) if rotates else list(reversed(indices))
    return indices


def sequence_end(preview):
    return max(.01, s.sequence_duration(preview["definition"], preview["sites"]))


def make_preview(arena, identity, definition):
    return dict(id=identity, definition=copy.deepcopy(definition), sites=s.schedule(arena, definition), elapsed=0., playing=False)


def audition(arena, preview, before, after):
    definition = preview["definition"]
    sites = preview["sites"]
    if not sites:
        return
    first = sites[0]
    obj = s.resolve(arena, first["ref"]) if "ref" in first else None
    origin = s.world(obj, arena["tile_map"]) if obj else first.get("point", {"x": 0., "y": 0.})
    if definition.get("sound_origin") and s.resolve(arena,definition["sound_origin"]):
        origin = s.world(s.resolve(arena,definition["sound_origin"]),arena["tile_map"])
    for index, site in enumerate(sites):
        if before < site["at"] <= after or before == 0 == site["at"]:
            obj = s.resolve(arena, site["ref"]) if "ref" in site else None
            cue = definition["sound_overrides"].get(s.ref_key(site["ref"]) if "ref" in site else str(index),definition["item_sound"])
            s.sound(arena, cue, s.world(obj, arena["tile_map"]) if obj else site.get("point", origin))
    if before < definition["delay"] <= after or before == definition["delay"] == 0:
        s.sound(arena, definition["start_sound"], origin)
    if before < sequence_end(preview) <= after:
        s.sound(arena, definition["end_sound"], origin)


def short_labels(collection):
    return {f"{obj.get('label', identity.split(':')[0])} {identity[-5:]}": identity for identity, obj in collection.items()}


def choose(ui, widget, label, value, collection):
    labels = short_labels(collection)
    selected = next((name for name, identity in labels.items() if identity == value), "none")
    name, changed = g_ui.ui_dropdown(ui, widget, label, selected, ["none", *labels], max_visible=5)
    return labels.get(name, ""), changed


def wrapped(ui, key, text):
    line = ""
    words = []
    for word in str(text).split():
        while pr.measure_text(word,8) > 145:
            end = len(word)-1
            while pr.measure_text(word[:end],8) > 145:
                end -= 1
            words.append(word[:end])
            word = word[end:]
        words.append(word)
    for word in words:
        if pr.measure_text((line+" "+word).strip(), 8) > 145:
            g_ui.ui_label(ui, key, line, font_size=8)
            line = word
        else:
            line = (line+" "+word).strip()
    if line:
        g_ui.ui_label(ui, key, line, font_size=8)


def edit_name(ui, st, definition):
    key = "seq:name:" + st["selected"]
    g_ui.ui_label(ui, "seq:name_label", "Name (Enter to save)", font_size=8)
    rect = g_ui.ui_next_rect(ui, 16)
    hovered = g_ui.ui_hover(ui, key, rect)
    if hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        g_ui.ui_queue_focused_numeric_commit(ui)
        ui["focused_id"] = key
        st["name_buffer"] = definition["label"]
    focused = ui.get("focused_id") == key
    if focused:
        buffer = st.get("name_buffer", definition["label"])
        character = pr.get_char_pressed()
        while character:
            if character >= 32 and len(buffer) < 64:
                buffer += chr(character)
            character = pr.get_char_pressed()
        if pr.is_key_pressed(pr.KeyboardKey.KEY_BACKSPACE):
            buffer = buffer[:-1]
        st["name_buffer"] = buffer
        if pr.is_key_pressed(pr.KeyboardKey.KEY_ENTER):
            definition["label"] = buffer.strip() or definition["label"]
            ui["focused_id"] = None
        elif pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE):
            ui["focused_id"] = None
    text = st.get("name_buffer", "") if focused else definition["label"]
    while text and pr.measure_text(text,8) > rect.width-8:
        text = text[1:]
    pr.draw_rectangle_rec(rect,g_ui.UI_ACTIVE if focused else g_ui.UI_NORMAL)
    pr.draw_text(text,int(rect.x+3),int(rect.y+4),8,g_ui.UI_TEXT)
    if g_ui.ui_button(ui,"seq:copy_id","Copy persistent ID"):
        pr.set_clipboard_text(st["selected"])


def inspector(arena, editor, ui):
    st = state(editor)
    rect = pr.Rectangle(310, 38, 170, 232)
    if g_ui.ui_point_in_rect(g_ui.get_mouse_position(), rect) and not ui.get("open_dropdown_id"):
        st["scroll"] = max(0., st["scroll"]-pr.get_mouse_wheel_move()*18.)
    g_ui.ui_begin_panel(ui, "seq:panel", rect, "Sequences", st["scroll"])
    st["kind"], kind_changed = g_ui.ui_dropdown(ui, "seq:kind", "", st["kind"], ("sequences", "triggers", "encounters", "event log"))
    if kind_changed:
        st.update(selected="", preview=None, member=0)
    if st["kind"] == "event log":
        if g_ui.ui_button(ui, "seq:retry", "Retry last failed event"):
            st["command"] = "retry"
        for entry in reversed(arena["sequence_runtime"]["log"][-30:]):
            wrapped(ui, "seq:log", entry)
        g_ui.ui_end_panel(ui)
        return
    collection = arena["world_sequences"][st["kind"]]
    st["selected"], changed = choose(ui, "seq:selected", "", st["selected"], collection)
    if changed:
        st.update(member=0, preview=None)
    if g_ui.ui_button(ui, "seq:demo", "Place courtyard demo"):
        st["demo"] = True
    if g_ui.ui_button(ui, "seq:validate", "Validate world links"):
        errors = s.validate_world(arena)
        st["error"] = errors[0] if errors else "World links valid."
        for error in errors:
            s.log(arena, error)
    if st["kind"] == "encounters" and g_ui.ui_button(ui, "seq:new_encounter", "New encounter"):
        identity = s.new_id("encounter")
        collection[identity] = {"label": "Encounter", "spawns": [], "on_complete": "none", "data": {}}
        st["selected"] = identity
    if st["tool"] == "Circle":
        for field, label, low, high in (("circle_count", "count", 2, 64), ("circle_angle", "start angle", 0, 360)):
            widget = g_ui.ui_number_input_int if field == "circle_count" else g_ui.ui_number_input_float
            st[field], _ = widget(ui, "seq:"+field, label, st[field], low, high)
        st["circle_reverse"], _ = g_ui.ui_checkbox(ui, "seq:circledir", "anticlockwise", st["circle_reverse"])
        st["circle_fire"], _ = g_ui.ui_checkbox(ui, "seq:circlefire", "Continuous fire path", st.get("circle_fire", False))
    definition = collection.get(st["selected"])
    if definition:
        edit_name(ui, st, definition)
        if st["kind"] == "sequences":
            sequence_inspector(arena, st, ui, definition)
        elif st["kind"] == "triggers":
            definition["sequence"], _ = choose(ui, "seq:triggerseq", "", definition["sequence"], arena["world_sequences"]["sequences"])
            for field, options in (("actors", ("player", "enemy", "all")), ("repeat", ("once", "every entry", "cooldown"))):
                definition[field], _ = g_ui.ui_dropdown(ui, "seq:"+field, field, definition[field], options)
            definition["enabled"], _ = g_ui.ui_checkbox(ui, "seq:enabled", "Initially enabled", definition["enabled"])
            definition["restart_sequence"], _ = g_ui.ui_checkbox(ui, "seq:restart", "Restart linked sequence", definition.get("restart_sequence", False))
            definition["cooldown"], _ = g_ui.ui_number_input_float(ui, "seq:cooldown", "cooldown", definition["cooldown"], 0, 600)
            for field in ("on_enter", "on_exit"):
                g_ui.ui_label(ui, "seq:"+field+":label", field, font_size=8)
                definition[field], _ = g_ui.ui_dropdown(ui, "seq:"+field, "", definition[field], list(s.data.HANDLERS))
            wrapped(ui, "seq:area", f"{len(definition['cells'])} tiles. Shift paints erase.")
            if g_ui.ui_button(ui, "seq:editarea", "Edit painted area"):
                st["tool"] = "Trigger paint"
                begin_draft(st)["cells"] = copy.deepcopy(definition["cells"])
                st["draft"]["replace"] = st["selected"]
        else:
            definition["on_complete"], _ = g_ui.ui_dropdown(ui, "seq:enc_handler", "", definition.get("on_complete", "none"), list(s.data.HANDLERS))
            markers = {obj["persistent_id"]: obj for obj in p.objects(arena) if obj["type"] == "puzzle spawn"}
            st["spawn_marker"], _ = choose(ui, "seq:add_marker", "", st.get("spawn_marker", ""), markers)
            if st["spawn_marker"] and g_ui.ui_button(ui, "seq:add_spawn", "Add spawn marker"):
                definition["spawns"].append({"marker": st["spawn_marker"], "type": "red head", "at": 0.})
            if definition["spawns"] and g_ui.ui_button(ui, "seq:remove_spawn", "Remove last spawn"):
                definition["spawns"].pop()
            if definition["on_complete"] == "courtyard_completed":
                doors = {obj["persistent_id"]: obj for obj in p.objects(arena) if obj["type"] in p.DOOR_TYPES}
                definition["data"]["door"], _ = choose(ui, "seq:exit_door", "", definition["data"].get("door", ""), doors)
            wrapped(ui, "seq:enc", f"{len(definition['spawns'])} spawn entries")
            for i, entry in enumerate(definition["spawns"]):
                wrapped(ui, "seq:spawn", f"{i+1}: {entry['type']} {entry['marker'][-6:]}")
                entry["at"], _ = g_ui.ui_number_input_float(ui, f"seq:spawn:{i}", "delay", entry.get("at", 0), 0, 600)
        if g_ui.ui_button(ui, "seq:reset", "Reset selected progress"):
            st["command"] = "reset"
        if st["kind"] != "triggers" and g_ui.ui_button(ui, "seq:test", "Start in gameplay"):
            st["command"] = "test"
        progress = arena["sequence_state"].get(st["kind"], {}).get(st["selected"], {})
        wrapped(ui, "seq:status", "State: "+progress.get("status", "not started"))
        for blocked in progress.get("blocked", []):
            wrapped(ui, "seq:blocked", blocked)
        if g_ui.ui_button(ui, "seq:delete", "Delete definition"):
            if progress:
                st["error"] = "Reset selected progress before deleting."
            else:
                del collection[st["selected"]]
                st.update(selected="", preview=None)
    if st["error"]:
        wrapped(ui, "seq:error", st["error"])
    panel = g_ui.ui_end_panel(ui)
    # Avoid scrolling past the last control into an empty inspector.
    content_height = panel["cursor_y"] + st["scroll"] - rect.y
    st["scroll"] = min(st["scroll"], max(0., content_height-rect.height+8))


def sequence_inspector(arena, st, ui, definition):
    identity = st["selected"]
    if g_ui.ui_button(ui, "seq:preview", "Preview / pause"):
        preview = st.get("preview")
        if preview is None or preview["id"] != identity or preview["definition"] != definition or preview["elapsed"] >= sequence_end(preview):
            preview = make_preview(arena, identity, definition)
            st["preview"] = preview
        preview["playing"] = not preview["playing"]
    if g_ui.ui_button(ui, "seq:stop", "Stop preview"):
        st["preview"] = None
    st["audition"], _ = g_ui.ui_checkbox(ui, "seq:audition", "Audition sounds", st["audition"])
    preview = st.get("preview") or make_preview(arena, identity, definition)
    elapsed, changed = g_ui.ui_slider_float(ui, "seq:scrub", "time", preview["elapsed"], 0, sequence_end(preview), .01)
    if changed:
        preview.update(elapsed=elapsed, playing=False)
        st["preview"] = preview
    fields = [("delay", "start delay", 0, 60), ("fade_in", "fade in", 0, 20),
              ("hold", "hold", 0, 60), ("fade_out", "fade out", 0, 20)]
    fields += [("speed", "speed", .1, 300), ("spacing", "spacing", 2, 100)] if definition["mode"] == "path" else [("interval", "interval", 0, 30)]
    for field, label, low, high in fields:
        definition[field], _ = g_ui.ui_number_input_float(ui, "seq:"+field, label, definition[field], low, high)
    definition["style"], _ = g_ui.ui_dropdown(ui, "seq:style", "", definition["style"], ("persistent", "pulse", "fill"))
    definition["reverse"], _ = g_ui.ui_checkbox(ui, "seq:reverse", "Reverse", definition["reverse"])
    definition["closed"], _ = g_ui.ui_checkbox(ui, "seq:closed", "Closed loop", definition["closed"])
    members = definition["points"] if definition["mode"] == "path" else definition["targets"]
    st["member"] = max(0, min(st["member"], len(members)-1))
    indices = member_order(definition)
    shown_member = indices.index(st["member"])+1 if indices else 1
    shown_member, _ = g_ui.ui_number_input_int(ui, "seq:member", "member", shown_member, 1, max(1,len(members)))
    st["member"] = indices[max(0,min(shown_member-1,len(indices)-1))] if indices else 0
    index = max(0, min(st["member"], len(members)-1))
    if members:
        if (definition["mode"] == "objects" or definition["closed"]) and g_ui.ui_button(ui, "seq:start_here", "Start at member"):
            definition["start_index"] = index
        if g_ui.ui_button(ui, "seq:remove", "Remove member"):
            members.pop(index)
        if definition["mode"] == "objects" and index < len(members):
            key = s.ref_key(members[index])
            g_ui.ui_label(ui, "seq:override_label", "Member sound override", font_size=8)
            cue, changed = g_ui.ui_dropdown(ui, "seq:override", "", definition["sound_overrides"].get(key, "default"), ["default", *s.data.SOUNDS])
            if changed:
                if cue == "default":
                    definition["sound_overrides"].pop(key, None)
                else:
                    definition["sound_overrides"][key] = cue
            obj = s.resolve(arena, members[index])
            if obj:
                obj["initially_lit"], _ = g_ui.ui_checkbox(ui, "seq:initial", "Initially lit", obj.get("initially_lit", obj.get("enabled", True)))
    if definition["mode"] == "objects" and g_ui.ui_button(ui, "seq:append", "Append existing objects"):
        st.update(tool="Pick existing", append_to=identity)
        begin_draft(st)
    for field, label in (("start_sound", "Start sound"), ("item_sound", "Activation sound"), ("end_sound", "End sound")):
        g_ui.ui_label(ui, "seq:"+field+":label", label, font_size=8)
        definition[field], _ = g_ui.ui_dropdown(ui, "seq:"+field, "", definition[field], list(s.data.SOUNDS))
    if g_ui.ui_button(ui, "seq:origin", "Pick sound origin"):
        st["tool"] = "Sound origin"
    if g_ui.ui_button(ui, "seq:origin_clear", "Use trigger sound origin"):
        definition["sound_origin"] = None
    g_ui.ui_label(ui, "seq:callback_label", "Completion handler", font_size=8)
    definition["on_complete"], _ = g_ui.ui_dropdown(ui, "seq:callback", "", definition["on_complete"], list(s.data.HANDLERS))
    if definition["on_complete"] == "spawn_linked_encounter":
        definition["data"]["encounter"], _ = choose(ui, "seq:encounter", "", definition["data"].get("encounter", ""), arena["world_sequences"]["encounters"])
    for error in s.validate_sequence(arena, definition):
        wrapped(ui, "seq:validation", error)


def draw_world(arena, editor, camera):
    st = state(editor)
    tm = arena["tile_map"]
    selected = arena["world_sequences"].get(st["kind"], {}).get(st["selected"])
    for collection in ("emitters", "lights"):
        for obj in arena["entities"].get(collection, {}).values():
            if collection == "emitters" and obj.get("type") != "fire":
                continue
            pos = s.world(obj, tm)
            x, y = round(pos["x"]-camera.x), round(pos["y"]-camera.y)
            pr.draw_circle_lines(x,y,4,pr.ORANGE if collection == "emitters" else pr.SKYBLUE)
    for identity, area in arena["world_sequences"]["triggers"].items():
        draw_cells(area["cells"], tm, camera, pr.Color(70,190,210,90 if identity == st["selected"] else 40))
    if selected and st["kind"] == "sequences":
        if selected["mode"] == "objects":
            points = [s.world(s.resolve(arena, site["ref"]),tm) for site in s.schedule(arena,selected) if s.resolve(arena,site["ref"])]
        else:
            points = list(selected["points"])
            if points and selected["closed"]:
                start = int(selected["start_index"]) % len(points)
                points = points[start:]+points[:start]
            if selected["reverse"]:
                points = points[:1]+list(reversed(points[1:])) if selected["closed"] else list(reversed(points))
        draw_chain(points, camera, selected.get("closed", False), pr.YELLOW)
    draft = st.get("draft")
    if draft:
        if draft["tool"].startswith("Trigger"):
            draw_cells(draft["cells"], tm, camera, pr.Color(70,240,150,100))
        else:
            points = draft["points"] or [entry.get("point") or s.world(s.resolve(arena, entry["ref"]), tm) for entry in draft["entries"] if "point" in entry or s.resolve(arena, entry["ref"])]
            if draft["tool"] == "Circle" and draft["centre"] and draft["edge"]:
                points = circle_points(draft["centre"], draft["edge"], st["circle_count"], st["circle_angle"], st["circle_reverse"])
            draw_chain(points, camera, draft["tool"] == "Circle", pr.GREEN)


def draw_cells(cells, tm, camera, color):
    for tx, ty in cells:
        x, y = round(tx*tm["tile_width"]-camera.x), round(ty*tm["tile_height"]-camera.y)
        pr.draw_rectangle(x, y, tm["tile_width"], tm["tile_height"], color)
        pr.draw_rectangle_lines(x, y, tm["tile_width"], tm["tile_height"], pr.Color(color.r,color.g,color.b,150))


def draw_chain(points, camera, closed, color):
    for a, b in zip(points, points[1:] + (points[:1] if closed else [])):
        ax, ay, bx, by = a["x"]-camera.x,a["y"]-camera.y,b["x"]-camera.x,b["y"]-camera.y
        pr.draw_line(int(ax),int(ay),int(bx),int(by),color)
        angle = math.atan2(by-ay,bx-ax)
        mx, my = (ax+bx)/2, (ay+by)/2
        for sign in (-1,1):
            pr.draw_line(int(mx),int(my),int(mx-5*math.cos(angle+sign*.5)),int(my-5*math.sin(angle+sign*.5)),color)
    for index, point in enumerate(points):
        x, y = int(point["x"]-camera.x), int(point["y"]-camera.y)
        pr.draw_circle(x,y,6,pr.BLACK)
        pr.draw_text(str(index+1),x-3,y-4,8,color)


def draw_torches(arena, camera):
    for obj in arena["entities"].get("emitters", {}).values():
        if obj.get("sequence_torch"):
            point = s.world(obj, arena["tile_map"])
            pr.draw_rectangle(round(point["x"]-camera.x-2),round(point["y"]-camera.y-4),4,7,pr.BROWN)


def create_courtyard(arena, centre):
    """Opt-in demo; adds objects without repainting or replacing the user's map."""
    if "demo" in arena["world_sequences"]:
        raise ValueError("Courtyard demo already exists; reset its progress to replay")
    tm = arena["tile_map"]
    if centre["x"] < 90 or centre["y"] < 90 or centre["x"]+90 >= tm["map_width"]*tm["tile_width"] or centre["y"]+90 >= tm["map_height"]*tm["tile_height"]:
        raise ValueError("Move the camera to leave a 180px clear area inside the map")
    import g_update_and_render as game
    import g_editor
    identity = s.new_id("courtyard")
    definition = s.make_sequence()
    definition.update(label="Courtyard ignition", on_complete="spawn_linked_encounter")
    definition["targets"] = [s.create_torch(arena, point) for point in circle_points(centre, {"x": centre["x"]+64,"y":centre["y"]},6)]
    arena["world_sequences"]["sequences"][identity] = definition
    objects = arena["entities"].setdefault("puzzles", {})
    demo_group = max((obj.get("puzzle_group", 0) for obj in objects.values()), default=0)+1
    created = []
    for kind, dx, dy in (("authored door",0,-88),("puzzle spawn",-35,0),("puzzle spawn",35,0)):
        obj = {"type":kind, "position":s.tile_position({"x":centre["x"]+dx,"y":centre["y"]+dy},arena["tile_map"])}
        game.give_entity_stats_from_type(obj,kind)
        obj["puzzle_group"] = demo_group
        obj["id"] = g_editor.allocate_gameplay_entity_id(objects)
        if kind == "authored door":
            obj.update(on_unlock="sequence_locked", label="Guardian exit")
        else:
            obj["label"] = "Spawn A" if dx < 0 else "Spawn B"
        objects[obj["id"]] = obj
        created.append(obj)
    encounter_id = s.new_id("guardians")
    arena["world_sequences"]["encounters"][encounter_id] = dict(label="Courtyard guardians",
        spawns=[{"marker": obj["persistent_id"], "type":"red head", "at":0.} for obj in created[1:]],
        on_complete="courtyard_completed", data={"door":created[0]["persistent_id"]})
    definition["data"] = {"encounter":encounter_id}
    cells = sample_rectangle({"x":centre["x"]-24,"y":centre["y"]+52},{"x":centre["x"]+24,"y":centre["y"]+68},arena["tile_map"])
    trigger_id = s.new_id("courtyard_entry")
    area = s.make_trigger(cells)
    area.update(label="Courtyard entrance",sequence=identity)
    arena["world_sequences"]["triggers"][trigger_id] = area
    arena["world_sequences"]["demo"] = {"sequence":identity,"encounter":encounter_id,"trigger":trigger_id}
    return arena


def audio_emitters(entities, preview, audition_enabled):
    emitters = entities.get("emitters", {})
    if not preview or (audition_enabled and preview.get("playing")):
        return emitters
    muted = {site["ref"]["id"] for site in preview["sites"] if "ref" in site and site["ref"]["collection"] == "emitters"}
    prefix = "sequence_path:"+preview["id"]+":"
    return {key: obj for key,obj in emitters.items() if key not in muted and not str(key).startswith(prefix)}
