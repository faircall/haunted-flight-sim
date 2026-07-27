import math
import random

import pyray as pr
from pyrsistent import m, pmap, v

import g_update_and_render as game

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

def do_button(sounds, pos, width = 50, height = 20, name = "some buttons"):
    game.g_button_id += 1
    font_width = 6
    width = len(name) * font_width
    base_rect = pr.Rectangle(int(pos.x), int(pos.y), width, height)
    rect_col = pr.WHITE
    
    result = False
    if pr.check_collision_point_rec(get_mouse_position(), base_rect):
        game.g_interacted_ui_this_frame += 1
        if game.g_last_interacted_ui_id != game.g_button_id:
            game.g_last_interacted_ui_id = game.g_button_id
            game.play_sound(sounds["ui_hover"])
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
        if do_button(assets.get("sounds"), pr.Vector2(dropdown_x, dropdown_y + drawn*height), width, height, f"{saved_file}"):
            selected_file = i
        drawn += 1    

    do_load = False
    if do_button(assets.get("sounds"), pr.Vector2(dropdown_x + 200, dropdown_y), 100, 40, f"load {saved_files[selected_file]}"):
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
