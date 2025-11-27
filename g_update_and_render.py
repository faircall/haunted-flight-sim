import math
import pickle
import os
import time

import pyray as pr
from pyrsistent import m, pmap, v

from enum import Enum

MyColor = Enum('MyColor', ['RED','GREEN','BLUE','PURPLE','BROWN'])





def draw_variable_state(name, state, posx, posy, size, color):
    on_off = "off"
    if state:
        on_off = "on"        
    message = f"{name} is {on_off}"
    pr.draw_text(message, posx, posy, size, color)
    print(message)

def get_or_set(arena, variable_name, default_value):
    if variable_name in arena:
        return arena[variable_name]
    else:
        arena[variable_name] = default_value
        return default_value
    
def get_or_invoke(arena, variable_name, default_func):
    if variable_name in arena:
        return arena[variable_name]
    else:
        arena[variable_name] = default_func()
        return arena[variable_name]
    
def get_or_invoke_args(arena, variable_name, default_func, args):
    if variable_name in arena:
        return arena[variable_name]
    else:
        arena[variable_name] = default_func(*args)
        return arena[variable_name]


def normalized_sin(t):
    return 0.5 *math.sin(t) + 0.5

def make_tile_map(width, height, tile_width, tile_height):
    # to be able to serialize this we should change the types here
    result = {}
    result["map_width"] = width
    result["map_height"] = height
    result["tile_width"] = tile_width
    result["tile_height"] = tile_height    
    result["tile_types"] = [("blank_tile", MyColor.RED), ("carpet",MyColor.BLUE), ("bed", MyColor.GREEN), ("wall", MyColor.PURPLE), ("wood", MyColor.BROWN)]
    result["tile_names"] = {}
    for i, tup in enumerate(result["tile_types"]):
        result["tile_names"][i] = tup[0]

    result["tile_types_amount"] = len(result["tile_types"])
    tiles = []
    for y in range(height):
        for x in range(width):
            blank_tile = {}
            blank_tile["number"] = 0
            blank_tile["type"] = "blank_tile"
            blank_tile["color"] = MyColor.RED
            if x % 2 == 0 and y % 2 == 0:
                blank_tile["color"] = MyColor.GREEN
            if x % 2 == 0 and y % 2 != 0:
                blank_tile["color"] = MyColor.PURPLE
            tiles.append(blank_tile)
    result["tiles"] = tiles
    return result

def draw_screen_boundary_rect(rect, off_color, on_color, button_states, button_id, mouse_pos, dt, mouse_move_speed, max_mouse_speed):
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


def color_map(color_enum):
    lookup = {
        MyColor.BROWN : pr.BROWN,
        MyColor.BLUE : pr.BLUE,
        MyColor.RED : pr.RED,
        MyColor.GREEN : pr.GREEN,
        MyColor.PURPLE : pr.PURPLE
    }
    return lookup.get(color_enum, pr.WHITE)

def update_and_render_tile_map(game_camera, tile_map, mouse_pos_world, current_tile_selection, game_assets):
    # use logical 1920 x 1080 'screen'
    map_height = tile_map["map_height"]
    map_width = tile_map["map_width"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]

    map_tiles_across = map_width / tile_width
    map_tiles_down = map_height / tile_height

    visible_tiles_across = int(1920 / tile_width)
    visible_tiles_down = int(1080 / tile_width)

    mouse_tile_pos = pr.Vector2(int((mouse_pos_world.x + game_camera.x)/tile_width), int((mouse_pos_world.y + game_camera.y)/tile_height))

    top_left_pos = pr.Vector2(int(game_camera.x/tile_width), int(game_camera.y/tile_height))    
    
    # let's try be slightly quicker about this!
    # we could think about where the camera *is*
    # and just draw the ones around that..?    
    for y in range(int(top_left_pos.y), int(top_left_pos.y + visible_tiles_down)):
        for x in range(int(top_left_pos.x), int(top_left_pos.x + visible_tiles_across)):
            tile_to_draw = tile_map["tiles"][y*map_width + x]
            is_highlight = False
            tile_color = color_map(tile_to_draw["color"])
            if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                is_highlight = True
                if pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                    tile_map["tiles"][y*map_width + x]["number"] = (tile_map["tiles"][y*map_width + x]["number"] + 1) % tile_map["tile_types_amount"]
                    tile_map["tiles"][y*map_width + x]["type"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][0]
                    tile_map["tiles"][y*map_width + x]["color"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][1]            

                if pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT):
                    tile_map["tiles"][y*map_width + x]["number"] = current_tile_selection
                    tile_map["tiles"][y*map_width + x]["type"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][0]
                    tile_map["tiles"][y*map_width + x]["color"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][1]            


                

            pr.draw_rectangle(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, tile_color)
            if tile_to_draw.get("type") == "wood":
                #pr.draw_texture(game_assets.get("textures",{}).get("wood_texture"), int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), pr.WHITE)
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wood_texture"), pr.Vector2(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y)), 0.0, 2, pr.WHITE)
            elif tile_to_draw.get("type") == "wall":
                #pr.draw_texture(game_assets.get("textures",{}).get("wood_texture"), int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), pr.WHITE)
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wall_texture"), pr.Vector2(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y)), 0.0, 1, pr.WHITE)
            if is_highlight:
                pr.draw_rectangle_lines(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, pr.WHITE)

def make_default_camera():
    game_camera = pr.Camera3D(pr.Vector3(0,0,10), pr.Vector3(0,1,0), pr.Vector3(0,1,0), 45.0, pr.CameraProjection.CAMERA_ORTHOGRAPHIC)    
    return game_camera

def do_button(pos, width = 50, height = 20, name = "some buttons"):
    font_width = 6
    width = len(name) * font_width
    base_rect = pr.Rectangle(int(pos.x), int(pos.y), width, height)
    rect_col = pr.WHITE
    
    result = False
    if pr.check_collision_point_rec(pr.get_mouse_position(), base_rect):
        rect_col = pr.YELLOW
        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
            result = True
    pr.draw_rectangle(int(pos.x), int(pos.y), width, height, rect_col)
    pr.draw_text(name, int(pos.x), int(pos.y), int(height/10), pr.BLACK)
    return result



def update_camera(game_camera, dt):    
    camera_speed = 500
    up = 0
    across = 0
        
    if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT):
        camera_speed *= 3
    # if pr.is_key_down(pr.KeyboardKey.KEY_A):
    #     #player_position.x -= dt*camera_speed
    #     player_position = pr.vector3_add(player_position, pr.vector3_scale(slide_heading, -dt*camera_speed)) # yeah nice
    # if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL):
    #     player_position.y -= dt*camera_speed
    camera_direction = pr.Vector3(0.0, 0.0, 0.0)
    if pr.is_key_down(pr.KeyboardKey.KEY_A):
        camera_direction.x = -1         
    if pr.is_key_down(pr.KeyboardKey.KEY_D):
        camera_direction.x = 1                
    if pr.is_key_down(pr.KeyboardKey.KEY_W):
        camera_direction.y = -1                        
    if pr.is_key_down(pr.KeyboardKey.KEY_S):
        camera_direction.y = 1                        
    
    
        
    game_camera.position = pr.vector3_add(game_camera.position, pr.vector3_scale(camera_direction, camera_speed * dt))    
    game_camera.position.x = max(0, game_camera.position.x)
    game_camera.position.y = max(0, game_camera.position.y)
    
    return game_camera

def make_default_position(x,y,z):
    return pr.Vector3(x,y,z)

def update_tile_selection(current_tile_selection, tile_types_amount):
    mouse_wheel =  pr.get_mouse_wheel_move()
    if mouse_wheel < 0:
        current_tile_selection = (current_tile_selection - 1) % tile_types_amount
    elif mouse_wheel > 0:
        current_tile_selection = (current_tile_selection + 1) % tile_types_amount
    return current_tile_selection        
    

g_save_directory = "saved_editor_states"
def save_state(arena):
    directory = g_save_directory   
    os.makedirs(directory, exist_ok=True)
    file_name = f"editor_state_{int(time.time())}.pkl"
    file_path = os.path.join(directory, file_name)        
    try:
        with open(file_path, "wb") as f:
            pickle.dump(arena, f)
        pr.draw_text(f"saved editor state {file_path}", 400, 40, 30, pr.WHITE)        
        print(f"saved editor state")
    except Exception as e:
        print(f"issue saving state {e}")        

def get_saved_files():    
    directory = g_save_directory   
    saved_files = []
    all_files = os.listdir(directory)
    saved_files = [f for f in all_files if f.endswith(".pkl")]
    saved_files.sort(reverse=True)
    return saved_files
    
def load_textures():
    result = {}    
    result["wood_texture"] = pr.load_texture("art/WoodTest.png")
    result["wall_texture"] = pr.load_texture("art/Wall.png")
    return result

def update_and_render(main_arena, game_assets):
    # maybe we think of assets as things that can't be serialized, or are expensive to do so...
    # arena initialisation
    dt = pr.get_frame_time()
    mouse_pos = pr.get_mouse_position()
    time_elapsed = main_arena.get("time_elapsed", 0.0) 
    save_interval = 200
    save_elapsed = main_arena.get("save_elapsed", 0.0) 
    save_elapsed += dt
    saved_files = main_arena.get("saved_files") 
    if not saved_files:
        saved_files = get_saved_files()

    textures = game_assets.get("textures")
    if not textures:
        textures = load_textures()
        game_assets["textures"] = textures

    if save_elapsed >= save_interval or pr.is_key_pressed(pr.KeyboardKey.KEY_F5):
        save_state(main_arena)
        save_elapsed = 0.0
        saved_files = get_saved_files()

    ui_button_states = main_arena.get("ui_button_states")
    if not ui_button_states:
        ui_button_states = pmap()

        tile_map = game_assets.get("tile_map")
    if not tile_map:
        tile_map = make_tile_map(1000, 1000, 32, 32)
        game_assets["tile_map"] = tile_map
    

    use_mouse_screen_navigation =  ui_button_states.get("use_mouse_screen_navigation", True)
    current_tile_selection = main_arena.get("current_tile_selection")


    if not current_tile_selection:
        current_tile_selection = 0

    # this is 'mutable' or at least expensive since it's a raylib/opengl call I think, don't want to spam it
    camera_3d = get_or_invoke(game_assets, "camera_3d", make_default_camera)        
    
    
    

    screen_width = main_arena.get("screen_width")
    screen_height = main_arena.get("screen_height")
    tile_size = 32
        

    #input handling
    camera_3d = update_camera(camera_3d, dt)
    
    auto_reload = main_arena.get("auto_reload", True)
    # print(f"game camera is at x:{game_camera.position.x}, y: {game_camera.position.y}, z: {game_camera.position.z}")
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F1):
        auto_reload = not auto_reload    
        draw_variable_state("auto reload", auto_reload, 10, 10, 20, pr.WHITE)            
                

    # rendering code
    # this seems to be about the shade of the sky
    color_to_draw = pr.Color(60, 160, 250, 255)    
    pr.begin_drawing()
    pr.clear_background(color_to_draw)    
    

    

    update_and_render_tile_map(camera_3d.position, tile_map, pr.get_mouse_position(), current_tile_selection, game_assets)

    if do_button(pr.Vector2(10, 10), name="reset all"):        
        game_assets["tile_map"] = None
        game_assets["textures"] = None

    if do_button(pr.Vector2(10, 30), name=f"sel:{tile_map.get("tile_names",{}).get(current_tile_selection, "")}"):
        current_tile_selection = (current_tile_selection + 1) % tile_map.get("tile_types_amount", 1)

    current_tile_selection = (update_tile_selection(current_tile_selection, tile_map.get("tile_types_amount", 1))) % tile_map.get("tile_types_amount", 1)

    

    
    pr.end_drawing()

    # update persistent variables here
    changes = main_arena.evolver()

    changes["time_elapsed"] = time_elapsed + dt
    changes["current_tile_selection"] = current_tile_selection
    changes["auto_reload"] = auto_reload    
    changes["ui_button_states"] = ui_button_states
    changes["save_elapsed"] = save_elapsed
    changes["saved_files"] = saved_files

    result = changes.persistent()    
    game_assets["camera_3d"] = camera_3d

    return result
    
