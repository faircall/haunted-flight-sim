import math
import random
import re

import pyray as pr
from pyrsistent import m, pmap, v

import g_audio
import g_update_and_render as game

UI_BACKGROUND = pr.Color(24, 22, 34, 238)
UI_PANEL = pr.Color(38, 35, 50, 245)
UI_NORMAL = pr.Color(68, 64, 82, 255)
UI_HOT = pr.Color(98, 91, 118, 255)
UI_ACTIVE = pr.Color(126, 111, 151, 255)
UI_TEXT = pr.Color(235, 232, 242, 255)
UI_MUTED = pr.Color(164, 158, 178, 255)
UI_ACCENT = pr.Color(226, 184, 94, 255)

def make_ui_state():
    return {
        "hot_id": None,
        "active_id": None,
        "focused_id": None,
        "open_dropdown_id": None,
        "text_buffers": {},
        "text_select_all": {},
        "numeric_edit_metadata": {},
        "pending_numeric_commits": {},
        "drag_start": None,
        "mouse_captured": False,
        "previous_hot_id": None,
        "dropdown_scroll": {},
        "audio_runtime": None,
        "panel_stack": []
    }

def ui_begin_frame(ui_state, audio_runtime):
    defaults = make_ui_state()

    for key, value in defaults.items():
        ui_state.setdefault(key, value)

    ui_state["previous_hot_id"] = ui_state.get("hot_id")
    ui_state["previous_hot_id_sound"] = ui_state.get("hot_id_sound")
    ui_state["hot_id"] = None
    ui_state["mouse_captured"] = ui_state.get("active_id") is not None or ui_state.get("focused_id") is not None or ui_state.get("open_dropdown_id") is not None
    ui_state["audio_runtime"] = audio_runtime
    ui_state["panel_stack"] = []
    return ui_state

def ui_end_frame(ui_state):
    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT) and ui_state.get("focused_id") is not None and ui_state.get("hot_id") != ui_state.get("focused_id"):
        ui_queue_focused_numeric_commit(ui_state)

    if pr.is_mouse_button_released(pr.MouseButton.MOUSE_BUTTON_LEFT):
        ui_state["active_id"] = None
        ui_state["drag_start"] = None

    if ui_state.get("open_dropdown_id") is not None or ui_state.get("focused_id") is not None:
        ui_state["mouse_captured"] = True

    return ui_state

def ui_capture_mouse(ui_state):
    ui_state["mouse_captured"] = True

def ui_release_mouse(ui_state, commit_focused=True):
    """End interactions belonging to UI that is no longer visible."""
    if commit_focused:
        ui_queue_focused_numeric_commit(ui_state)
    ui_state["active_id"] = None
    ui_state["focused_id"] = None
    ui_state["open_dropdown_id"] = None
    ui_state["drag_start"] = None
    ui_state["mouse_captured"] = False

def ui_point_in_rect(point, rect):
    return rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height

def ui_hover(ui_state, widget_id, rect, does_sound = True):
    hovered = ui_point_in_rect(get_mouse_position(), rect)

    if hovered:        
        ui_state["hot_id"] = widget_id
        if does_sound:
            ui_state["hot_id_sound"] = widget_id
        ui_capture_mouse(ui_state)

        if ui_state.get("previous_hot_id_sound") != widget_id and does_sound:
            audio_runtime = ui_state.get("audio_runtime")
            if audio_runtime is not None:
                g_audio.queue_audio_event(audio_runtime, {
                    "type": "ui_hover", "source_id": f"ui:{widget_id}",
                    "source_kind": "ui", "priority": 0.7,
                })

    return hovered

def ui_clamp(value, minimum=None, maximum=None):
    result = value

    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)

    return result

def ui_snap_value(value, step):
    if step is None or step <= 0:
        return value
    return round(value / step) * step

def ui_queue_focused_numeric_commit(ui_state, except_id=None):
    focused_id = ui_state.get("focused_id")

    if focused_id is None or focused_id == except_id:
        return

    metadata = ui_state.get("numeric_edit_metadata", {}).get(focused_id)

    if metadata is not None:
        parsed = parse_numeric_input(ui_state["text_buffers"].get(focused_id, ""), metadata["integer"])
        committed = metadata["original_value"] if parsed is None else ui_clamp(parsed, metadata["minimum"], metadata["maximum"])
        committed = int(committed) if metadata["integer"] else float(committed)
        ui_state["pending_numeric_commits"][focused_id] = committed
        ui_state["text_buffers"][focused_id] = str(committed)

    ui_state["focused_id"] = None

def parse_numeric_input(text, integer=False):
    candidate = text.strip()

    if not candidate or candidate in {"-", "+", ".", "-.", "+."}:
        return None

    pattern = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

    if re.fullmatch(pattern, candidate) is None:
        return None

    try:
        parsed = float(candidate)

        if integer:
            return int(parsed) if parsed.is_integer() else None

        return parsed
    except ValueError:
        return None

def ui_current_panel(ui_state):
    panels = ui_state.get("panel_stack", [])
    return panels[-1] if panels else None

def ui_next_rect(ui_state, height=14, width=None):
    panel = ui_current_panel(ui_state)

    if panel is None:
        return pr.Rectangle(0, 0, width or 100, height)

    rect = pr.Rectangle(panel["x"] + panel["padding"], panel["cursor_y"], width or panel["width"] - panel["padding"] * 2, height)
    panel["cursor_y"] += height + panel["spacing"]
    return rect

def ui_begin_panel(ui_state, widget_id, rect, title=None, scroll=0.0):
    hovered = ui_hover(ui_state, widget_id, rect, False)
    pr.draw_rectangle_rec(rect, UI_PANEL)
    pr.draw_rectangle_lines_ex(rect, 1.0, UI_NORMAL)
    pr.begin_scissor_mode(int(rect.x), int(rect.y), int(rect.width), int(rect.height))
    cursor_y = rect.y + 5 - scroll

    if title:
        pr.draw_text(title, int(rect.x + 5), int(cursor_y), 10, UI_TEXT)
        cursor_y += 14

    ui_state["panel_stack"].append({"id": widget_id, "x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height, "padding": 5, "spacing": 2, "cursor_y": cursor_y, "hovered": hovered})
    return hovered

def ui_end_panel(ui_state):
    panels = ui_state.get("panel_stack", [])
    panel = panels.pop() if panels else None

    if panel is not None:
        pr.end_scissor_mode()

    return panel

def ui_label(ui_state, widget_id, text, rect=None, color=None, font_size=9):
    rect = rect or ui_next_rect(ui_state, font_size + 3)
    pr.draw_text(str(text), int(rect.x), int(rect.y + 1), font_size, color or UI_TEXT)
    return rect

def ui_separator(ui_state, widget_id, rect=None):
    rect = rect or ui_next_rect(ui_state, 3)
    pr.draw_line(int(rect.x), int(rect.y + 1), int(rect.x + rect.width), int(rect.y + 1), UI_NORMAL)
    return rect

def ui_button(ui_state, widget_id, text, rect=None, selected=False):
    rect = rect or ui_next_rect(ui_state, 15)
    hovered = ui_hover(ui_state, widget_id, rect)
    pressed = hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT)

    if pressed:
        ui_queue_focused_numeric_commit(ui_state)
        ui_state["active_id"] = widget_id

    color = (
        UI_ACTIVE
        if selected or ui_state.get("active_id") == widget_id
        else UI_HOT if hovered else UI_NORMAL
    )
    pr.draw_rectangle_rec(rect, color)
    pr.draw_rectangle_lines_ex(rect, 1.0, UI_ACCENT if selected else UI_BACKGROUND)
    pr.draw_text(text, int(rect.x + 4), int(rect.y + 3), 9, UI_TEXT)
    return pressed

def ui_checkbox(ui_state, widget_id, label, value, rect=None):
    rect = rect or ui_next_rect(ui_state, 14)
    hovered = ui_hover(ui_state, widget_id, rect)
    changed = hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT)

    if changed:
        ui_queue_focused_numeric_commit(ui_state)
        value = not value
        ui_state["active_id"] = widget_id

    box = pr.Rectangle(rect.x, rect.y + 1, 11, 11)
    pr.draw_rectangle_rec(box, UI_HOT if hovered else UI_NORMAL)
    pr.draw_rectangle_lines_ex(box, 1.0, UI_MUTED)

    if value:
        pr.draw_line(int(box.x + 2), int(box.y + 6), int(box.x + 5), int(box.y + 9), UI_ACCENT)
        pr.draw_line(int(box.x + 5), int(box.y + 9), int(box.x + 10), int(box.y + 2), UI_ACCENT)

    pr.draw_text(label, int(rect.x + 15), int(rect.y + 2), 9, UI_TEXT)
    return value, changed

def ui_dropdown(ui_state, widget_id, label, value, options, rect=None, max_visible=8):
    rect = rect or ui_next_rect(ui_state, 16)
    hovered = ui_hover(ui_state, widget_id, rect)
    changed = False

    if hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        ui_queue_focused_numeric_commit(ui_state)
        ui_state["open_dropdown_id"] = None if ui_state.get("open_dropdown_id") == widget_id else widget_id

    pr.draw_rectangle_rec(rect, UI_HOT if hovered else UI_NORMAL)
    pr.draw_rectangle_lines_ex(rect, 1.0, UI_BACKGROUND)
    display = f"{label}: {value}" if label else str(value)
    pr.draw_text(display, int(rect.x + 4), int(rect.y + 4), 8, UI_TEXT)
    pr.draw_text("v", int(rect.x + rect.width - 10), int(rect.y + 4), 8, UI_ACCENT)

    if ui_state.get("open_dropdown_id") != widget_id:
        return value, changed

    ui_capture_mouse(ui_state)
    visible_count = min(max_visible, len(options))
    popup = pr.Rectangle(rect.x, rect.y + rect.height, rect.width, visible_count * 15)
    panel = ui_current_panel(ui_state)

    if panel is not None:
        panel["cursor_y"] += popup.height
    popup_hovered = ui_point_in_rect(get_mouse_position(), popup)

    if popup_hovered:
        wheel = pr.get_mouse_wheel_move()
        maximum_scroll = max(0, len(options) - visible_count)
        current_scroll = ui_state["dropdown_scroll"].get(widget_id, 0)
        ui_state["dropdown_scroll"][widget_id] = int(ui_clamp(current_scroll - wheel, 0, maximum_scroll))

    scroll = ui_state["dropdown_scroll"].get(widget_id, 0)
    pr.draw_rectangle_rec(popup, UI_BACKGROUND)
    pr.draw_rectangle_lines_ex(popup, 1.0, UI_ACCENT)

    for visible_index, option in enumerate(options[scroll:scroll + visible_count]):
        option_id = f"{widget_id}:option:{option}"
        option_rect = pr.Rectangle(popup.x, popup.y + visible_index * 15, popup.width, 15)
        option_hovered = ui_hover(ui_state, option_id, option_rect)
        pr.draw_rectangle_rec(option_rect, UI_HOT if option_hovered else UI_BACKGROUND)
        pr.draw_text(str(option), int(option_rect.x + 4), int(option_rect.y + 3), 9, UI_TEXT)

        if option_hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
            changed = option != value
            value = option
            ui_state["open_dropdown_id"] = None

    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT) and not hovered and not popup_hovered:
        ui_state["open_dropdown_id"] = None

    return value, changed

def ui_slider_float(ui_state, widget_id, label, value, minimum, maximum, step=0.01, rect=None):
    rect = rect or ui_next_rect(ui_state, 18)
    label_width = min(62, rect.width * 0.45)
    track = pr.Rectangle(rect.x + label_width, rect.y + 4, rect.width - label_width, 10)
    hovered = ui_hover(ui_state, widget_id, rect)
    changed = False

    if hovered and pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        ui_queue_focused_numeric_commit(ui_state)
        ui_state["active_id"] = widget_id
        ui_state["drag_start"] = {"id": widget_id, "mouse_x": get_mouse_position().x, "value": float(value)}

    if ui_state.get("active_id") == widget_id and pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT):
        ui_capture_mouse(ui_state)
        mouse = get_mouse_position()
        drag_start = ui_state.get("drag_start") or {"mouse_x": mouse.x, "value": float(value)}
        range_size = maximum - minimum
        fine = 0.1 if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT) or pr.is_key_down(pr.KeyboardKey.KEY_RIGHT_SHIFT) else 1.0
        candidate = drag_start["value"] + (mouse.x - drag_start["mouse_x"]) / max(track.width, 1.0) * range_size * fine
        candidate = ui_clamp(ui_snap_value(candidate, step * fine), minimum, maximum)

        if candidate != value:
            value = candidate
            changed = True

    ratio = (float(value) - minimum) / max(maximum - minimum, 0.000001)
    pr.draw_text(f"{label} {float(value):.3g}", int(rect.x), int(rect.y + 4), 8, UI_TEXT)
    pr.draw_rectangle_rec(track, UI_NORMAL)
    pr.draw_rectangle(int(track.x), int(track.y), int(track.width * ui_clamp(ratio, 0.0, 1.0)), int(track.height), UI_ACCENT)
    pr.draw_circle(int(track.x + track.width * ui_clamp(ratio, 0.0, 1.0)), int(track.y + track.height * 0.5), 3, UI_TEXT)
    return value, changed

def ui_commit_numeric_buffer(ui_state, widget_id, value, integer, minimum, maximum):
    parsed = parse_numeric_input(ui_state["text_buffers"].get(widget_id, str(value)), integer)

    if parsed is None:
        ui_state["text_buffers"][widget_id] = str(value)
        return value, False

    parsed = ui_clamp(parsed, minimum, maximum)
    parsed = int(parsed) if integer else float(parsed)
    ui_state["text_buffers"][widget_id] = str(parsed)
    return parsed, parsed != value

def ui_number_input(ui_state, widget_id, label, value, integer=False, minimum=None, maximum=None, rect=None):
    pending_value = ui_state["pending_numeric_commits"].pop(widget_id, None)
    pending_changed = pending_value is not None and pending_value != value

    if pending_value is not None:
        value = pending_value

    rect = rect or ui_next_rect(ui_state, 16)
    label_width = min(68, rect.width * 0.5)
    input_rect = pr.Rectangle(rect.x + label_width, rect.y, rect.width - label_width, rect.height)
    hovered = ui_hover(ui_state, widget_id, rect)
    focused = ui_state.get("focused_id") == widget_id
    changed = pending_changed

    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        if ui_point_in_rect(get_mouse_position(), input_rect):
            if not focused:
                ui_queue_focused_numeric_commit(ui_state, widget_id)
                ui_state["text_buffers"][widget_id] = str(value)
                ui_state["text_select_all"][widget_id] = True
                ui_state["numeric_edit_metadata"][widget_id] = {"original_value": value, "integer": integer, "minimum": minimum, "maximum": maximum}
            ui_state["focused_id"] = widget_id
            ui_state["open_dropdown_id"] = None
            focused = True
        elif focused:
            value, changed = ui_commit_numeric_buffer(ui_state, widget_id, value, integer, minimum, maximum)
            ui_state["focused_id"] = None
            focused = False

    if focused:
        ui_capture_mouse(ui_state)
        buffer = ui_state["text_buffers"].setdefault(widget_id, str(value))
        character = pr.get_char_pressed()

        while character > 0:
            typed = chr(character)

            if typed in "0123456789+-.eE":
                if ui_state["text_select_all"].get(widget_id, False):
                    buffer = ""
                    ui_state["text_select_all"][widget_id] = False
                buffer += typed

            character = pr.get_char_pressed()

        if pr.is_key_pressed(pr.KeyboardKey.KEY_BACKSPACE):
            if ui_state["text_select_all"].get(widget_id, False):
                buffer = ""
                ui_state["text_select_all"][widget_id] = False
            else:
                buffer = buffer[:-1]

        ui_state["text_buffers"][widget_id] = buffer

        if pr.is_key_pressed(pr.KeyboardKey.KEY_ENTER):
            value, changed = ui_commit_numeric_buffer(ui_state, widget_id, value, integer, minimum, maximum)
            ui_state["focused_id"] = None
            focused = False
        elif pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE):
            ui_state["text_buffers"][widget_id] = str(value)
            ui_state["focused_id"] = None
            focused = False

    pr.draw_text(label, int(rect.x), int(rect.y + 4), 8, UI_TEXT)
    pr.draw_rectangle_rec(input_rect, UI_ACTIVE if focused else UI_HOT if hovered else UI_NORMAL)
    pr.draw_rectangle_lines_ex(input_rect, 1.0, UI_ACCENT if focused else UI_BACKGROUND)
    display = ui_state["text_buffers"].get(widget_id, str(value)) if focused else f"{value:g}"
    pr.draw_text(display, int(input_rect.x + 3), int(input_rect.y + 4), 8, UI_TEXT)
    return value, changed

def ui_number_input_float(ui_state, widget_id, label, value, minimum=None, maximum=None, rect=None):
    return ui_number_input(ui_state, widget_id, label, float(value), False, minimum, maximum, rect)

def ui_number_input_int(ui_state, widget_id, label, value, minimum=None, maximum=None, rect=None):
    return ui_number_input(ui_state, widget_id, label, int(value), True, minimum, maximum, rect)

def ui_vec2_input(ui_state, widget_id, label, value, minimum=None, maximum=None):
    ui_label(ui_state, f"{widget_id}:label", label, font_size=8)
    x_value, x_changed = ui_number_input_float(ui_state, f"{widget_id}:x", "x", value.get("x", 0.0), minimum, maximum)
    y_value, y_changed = ui_number_input_float(ui_state, f"{widget_id}:y", "y", value.get("y", 0.0), minimum, maximum)

    if x_changed or y_changed:
        value = {"x": x_value, "y": y_value}

    return value, x_changed or y_changed

def ui_color3_editor(ui_state, widget_id, label, value):
    color = list(value[:3]) if value else [1.0, 1.0, 1.0]
    ui_label(ui_state, f"{widget_id}:label", label, font_size=8)
    changed = False

    for index, channel in enumerate(("r", "g", "b")):
        color[index], channel_changed = ui_slider_float(ui_state, f"{widget_id}:{channel}:slider", channel, float(color[index]), 0.0, 1.0, 0.01)
        color[index], number_changed = ui_number_input_float(ui_state, f"{widget_id}:{channel}:number", channel, color[index], 0.0, 1.0)
        changed = changed or channel_changed or number_changed

    panel = ui_current_panel(ui_state)
    swatch = ui_next_rect(ui_state, 12)
    preview = pr.Color(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255), 255)
    pr.draw_rectangle_rec(swatch, preview)
    pr.draw_rectangle_lines_ex(swatch, 1.0, UI_TEXT)
    return color, changed

def draw_variable_state(name, state, posx, posy, size, color):
    on_off = "off"
    if state:
        on_off = "on"        
    message = f"{name} is {on_off}"
    pr.draw_text(message, posx, posy, size, color)
    print(message)

def draw_screen_boundary_rect(rect, off_color, on_color, button_states, button_id, mouse_pos, dt, mouse_move_speed, max_mouse_speed):
    # this thing lets you move around the screen by having your cursor on the edge
    if not button_states.get("use_mouse_screen_navigation"):
        return

    color_to_draw = off_color
    
    mouse_collides = False
    if button_id not in button_states:
        button_states[button_id] = {}        
        button_states[button_id]["velocity"] = pr.Vector2(0, 0)
        button_states[button_id]["state"] = "off"
    
    if pr.check_collision_point_rec(mouse_pos, rect):
        button_states[button_id]["state"] = "on"
        mouse_collides = True
        color_to_draw = on_color
        button_states[button_id]["state"] = "on"
        if button_id == "upper":
            button_states[button_id]["velocity"].y -= dt * mouse_move_speed
        elif button_id == "lower":
            button_states[button_id]["velocity"].y += dt * mouse_move_speed
        if button_id == "left":
            button_states[button_id]["velocity"].x -= dt * mouse_move_speed
        if button_id == "right":
            button_states[button_id]["velocity"].x += dt * mouse_move_speed
        
        button_states[button_id]["velocity"].x = min(button_states[button_id]["velocity"].x, max_mouse_speed)
        button_states[button_id]["velocity"].y = min(button_states[button_id]["velocity"].y, max_mouse_speed)
    else:
        button_states[button_id]["velocity"].x = 0
        button_states[button_id]["velocity"].y = 0

    pr.draw_rectangle_rec(rect, color_to_draw)
    return mouse_collides

def do_button(audio_runtime, pos, width = 50, height = 20, name = "some buttons"):
    widget_id = f"legacy:{name}:{int(pos.x)}:{int(pos.y)}"
    font_width = 6
    width = len(name) * font_width
    base_rect = pr.Rectangle(int(pos.x), int(pos.y), width, height)
    rect_col = pr.WHITE
    
    result = False
    if pr.check_collision_point_rec(get_mouse_position(), base_rect):
        game.g_interacted_ui_this_frame += 1
        if game.g_last_interacted_ui_id != widget_id:
            game.g_last_interacted_ui_id = widget_id
            if audio_runtime is not None:
                g_audio.queue_audio_event(audio_runtime, {
                    "type": "ui_hover", "source_id": f"ui:{widget_id}",
                    "source_kind": "ui", "priority": 0.7,
                })
            # play a  sound here

        game.g_mouse_is_ui_captured = True
        rect_col = pr.YELLOW
        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
            result = True
            
    pr.draw_rectangle(int(pos.x), int(pos.y), width, height, rect_col)
    pr.draw_text(name, int(pos.x) + 4, int(pos.y + height/3), int(height/10), pr.BLACK)
    return result

def update_tile_selection(current_tile_selection, tile_types_amount):
    mouse_wheel =  pr.get_mouse_wheel_move()
    if mouse_wheel < 0:
        current_tile_selection = (current_tile_selection - 1) % tile_types_amount
    elif mouse_wheel > 0:
        current_tile_selection = (current_tile_selection + 1) % tile_types_amount
    return current_tile_selection

def update_mousewheel_selection(current_selection, types_amount):
    mouse_wheel =  pr.get_mouse_wheel_move()
    if mouse_wheel < 0:
        current_selection = (current_selection - 1) % types_amount
    elif mouse_wheel > 0:
        current_selection = (current_selection + 1) % types_amount
    return current_selection

def draw_load_level(arena, assets):    
    if not arena.get("do_load_level", False):
        return -1, arena.get("do_load_level", False)
        
    saved_files = arena.get("saved_files")
    if not saved_files:
        return -1, arena.get("do_load_level", False)
    
    items_per_page = 20
    start_index = arena.get("load_level_index_start", 0)
    end_index = arena.get("load_level_end_start", 20)

    selected_file = arena.get("selected_save_index", -1)

    start_index = max(0, start_index)
    end_index = min(len(saved_files), end_index)

    

    dropdown_x = 100
    dropdown_y = 40
    height = 20
    drawn = 0
    width = 120
    for i in range(start_index, end_index):
        saved_file = saved_files[i]
        if do_button(assets.get("audio_runtime"), pr.Vector2(dropdown_x, dropdown_y + drawn*height), width, height, f"{saved_file}"):
            selected_file = i
        drawn += 1    

    do_load = False
    if do_button(assets.get("audio_runtime"), pr.Vector2(dropdown_x + 200, dropdown_y), 100, 40, f"load {saved_files[selected_file]}"):
        do_load = True
    return selected_file, do_load

def get_mouse_position():
    mouse_pos = pr.get_mouse_position()

    normalized_x = mouse_pos.x / max(1,pr.get_screen_width())
    normalized_y = mouse_pos.y / max(1,pr.get_screen_height())

    logical_x = normalized_x * game.g_internal_width
    logical_y = normalized_y * game.g_internal_height
    return pr.Vector2(logical_x, logical_y)

def interactive_mouse_left_pressed():
    return pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT) and not game.g_mouse_is_ui_captured

def interactive_mouse_left_down():
    return pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT) and not game.g_mouse_is_ui_captured
