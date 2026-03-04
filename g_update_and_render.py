import math
import pickle
import os
import time

import random

import queue

import pyray as pr
from pyrsistent import m, pmap, v

from dataclasses import dataclass, field

@dataclass(order=True)
class PriorityQueueEntry:
    priority: float
    tile: dict = field(compare=False)



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
    result["tile_types"] = [{"type" : "blank_tile", "color" : "BLACK"}, 
                            {"type" : "carpet", "color" : "BLUE"}, 
                            {"type" : "door", "color" : "RED"}, 
                            {"type" : "wall", "color" : "PURPLE"}, 
                            {"type" : "wood", "color" : "BROWN"}, 
                            {"type" : "grass", "color" : "GREEN"}, 
                            {"type" : "stone", "color" : "GREY"}]
    result["tile_names"] = {}    
    result["tile_types_amount"] = len(result["tile_types"])
    tiles = []
    for y in range(height):
        for x in range(width):
            blank_tile = {}
            blank_tile["index"] = 0
            blank_tile["tile_x"] = x
            blank_tile["tile_y"] = y
            blank_tile["neighbours"] = get_neighbouring_tiles(blank_tile, result)
            # blank_tile["type"] = "blank_tile"
            # blank_tile["color"] = "BLACK"            
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
        "BROWN" : pr.BROWN,
        "BLUE" : pr.BLUE,
        "RED" : pr.RED,
        "GREEN" : pr.GREEN,
        "PURPLE" : pr.PURPLE,
        "GREY" : pr.GRAY,        
        "BLACK" : pr.BLACK,
        "PINK" : pr.PINK                
    }
    return lookup.get(color_enum, pr.WHITE)

def draw_tile_texture_from_type(game_assets, tile_type, x, y):
    if tile_type.get("type") == "wood":                
        pr.draw_texture_ex(game_assets.get("textures",{}).get("wood_texture"), pr.Vector2((x), (y)), 0.0, 2, pr.WHITE)
    elif tile_type.get("type") == "wall":                
        pr.draw_texture_ex(game_assets.get("textures",{}).get("wall_texture"), pr.Vector2((x), (y)), 0.0, 1, pr.WHITE)
    elif tile_type.get("type") == "stone":                
        pr.draw_texture_ex(game_assets.get("textures",{}).get("grey_tile_texture"), pr.Vector2((x), (y)), 0.0, 1, pr.WHITE)
    elif tile_type.get("type") == "carpet":  #change to other tile               
        pr.draw_texture_ex(game_assets.get("textures",{}).get("orange_tile_texture"), pr.Vector2((x), (y)), 0.0, 1, pr.WHITE)
    
def do_flood_fill(current_tile_selection, x, y, tile_map, map_width, seen):    
    if (x,y) in seen or x < 0 or y < 0 or x >= map_width or y >= tile_map.get("map_height",0) or (tile_map["tiles"][y*map_width + x]["index"] == current_tile_selection):
        return
    
    seen[(x,y)] = True
    tile_map["tiles"][y*map_width + x]["index"] = current_tile_selection
    do_flood_fill(current_tile_selection, x, y+1, tile_map, map_width, seen)    
    do_flood_fill(current_tile_selection, x, y-1, tile_map, map_width, seen)    
    do_flood_fill(current_tile_selection, x+1, y, tile_map, map_width, seen)        
    do_flood_fill(current_tile_selection, x-1, y, tile_map, map_width, seen)    

def do_flood_fill_replace(initial, current_tile_selection, x, y, tile_map, map_width, seen):    
    if x < 0 or y < 0 or x >= map_width or y >= tile_map.get("map_height",0) or (tile_map["tiles"][y*map_width + x]["index"] != initial) or (x,y) in seen:
        return
    seen[(x,y)] = True
    tile_map["tiles"][y*map_width + x]["index"] = current_tile_selection
    do_flood_fill_replace(initial, current_tile_selection, x, y+1, tile_map, map_width, seen)    
    do_flood_fill_replace(initial, current_tile_selection, x, y-1, tile_map, map_width, seen)    
    do_flood_fill_replace(initial, current_tile_selection, x+1, y, tile_map, map_width, seen)        
    do_flood_fill_replace(initial, current_tile_selection, x-1, y, tile_map, map_width, seen)    

        
        

def get_tile_cost(tile_index):
    pass

def graph_cost(tile_a, tile_b):
    return 1

def a_star_heuristic(target_tile, next_tile):
    return abs(target_tile.get("tile_x") - next_tile.get("tile_x")) + abs(target_tile.get("tile_y") - next_tile.get("tile_y"))

def get_tile_id_for_hash(tile):
    return f"{tile.get("tile_x")},{tile.get("tile_y")}"

def a_star_path(start_tile, target_tile, tile_map):
    frontier = queue.PriorityQueue()
    frontier.put(PriorityQueueEntry(0, start_tile))

    came_from = {}
    cost_so_far = {}

    tile_id = get_tile_id_for_hash(start_tile)
    came_from[tile_id] = None
    cost_so_far[tile_id] = 0

    while not frontier.empty():

        current_pair = frontier.get()

        current = current_pair.tile

        current_tile_id = get_tile_id_for_hash(current)
        if tiles_equal(current, target_tile):
            break

        if current.get("neighbours") is None:
            print("well damn")
        for next_tile in current.get("neighbours"):
            # need to deref via the tile map actually
            next_tile_from_map = tile_map.get("tiles")[tile_map.get("map_width")*next_tile.get("tile_y") + next_tile.get("tile_x")]
            if next_tile_from_map.get("neighbours") is None:
                print("hmmm")
            next_tile_id = get_tile_id_for_hash(next_tile)
            if current_tile_id not in cost_so_far:
                print("argh")
            new_cost = cost_so_far[current_tile_id] + graph_cost(current, next_tile)
            if next_tile_id not in cost_so_far or new_cost < cost_so_far[next_tile_id]:
                cost_so_far[next_tile_id] = new_cost
                priority = new_cost + a_star_heuristic(target_tile, next_tile)
                frontier.put(PriorityQueueEntry(priority, next_tile_from_map))
                came_from[next_tile_id] = current

    # i guess we want the reconstruct function
    return came_from

def reconstruct_path(came_from, target, origin):
    next = target
    result = []
    result.append(target)
    while not tiles_equal(next, origin):
        next_id = get_tile_id_for_hash(next)
        next = came_from[next_id]
        result.append(next)
    return result


    
    


def do_tile_map(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, game_assets, ignore, player_pos, mode):
    # Todo:
    # tiles are tiles,
    # items are items, they can sit on top of tiles
    if ignore:
        return

    # use logical 1920 x 1080 'screen'
    map_height = tile_map["map_height"]
    map_width = tile_map["map_width"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    

    visible_tiles_across = int(1920 / tile_width)
    visible_tiles_down = int(1080 / tile_width)

    mouse_tile_pos = pr.Vector2(int((mouse_pos_world.x + game_camera.x)/tile_width), int((mouse_pos_world.y + game_camera.y)/tile_height))

    top_left_pos = pr.Vector2(int(game_camera.x/tile_width), int(game_camera.y/tile_height))    
    
    # let's try be slightly quicker about this!
    # we could think about where the camera *is*
    # and just draw the ones around that..?    

    tile_select_modes = {"editing", "entity_placing"}

    for y in range(int(top_left_pos.y), int(top_left_pos.y + visible_tiles_down+2)):
        for x in range(int(top_left_pos.x), int(top_left_pos.x + visible_tiles_across+1)):

            index = min(y*map_width + x, len(tile_map["tiles"])-1)
            tile_to_draw = tile_map["tiles"][index]
            is_highlight = False
            tile_index = tile_to_draw.get("index",0)
            color_to_draw = tile_map["tile_types"][tile_index].get("color")
            tile_color = color_map(color_to_draw)
            
            tile_type = tile_map["tile_types"][tile_index]

            if mode == "editing":
                if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                    is_highlight = True
                    # if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                    #     # do a flood fill
                    #     seen = {}
                    #     do_flood_fill(current_tile_selection, x, y, tile_map, map_width, seen)

                    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                        # do a flood fill
                        # get the initial tile
                        initial = tile_map["tiles"][y*map_width + x]["index"]
                        seen = {}
                        do_flood_fill_replace(initial, current_tile_selection, x, y, tile_map, map_width, seen)

                    if pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT):
                        tile_map["tiles"][y*map_width + x]["index"] = current_tile_selection                    
                            
                pr.draw_rectangle(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, tile_color)

            if mode == "entity_placing":
                if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                    is_highlight = True
                    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
                        new_entity = {}
                        entity_types = game_assets.get("entity_types", [])
                        if current_entity_selection < len(entity_types):
                            entity_type = entity_types[current_entity_selection]
                        new_entity["type"] = entity_type
                        new_entity["position"] = {"x" : mouse_pos_world.x + game_camera.x, "y" : mouse_pos_world.y + game_camera.y}
                        id = len(entities)
                        new_entity["id"] = id
                        entities[id] = new_entity

                    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                        latest_id = max(len(entities) - 1,0)
                        if latest_id in entities:
                            del entities[latest_id]

                    
                            
                pr.draw_rectangle(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, tile_color)
            if tile_type.get("type") == "wood":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wood_texture"), pr.Vector2((x*tile_width - game_camera.x), (y*tile_height - game_camera.y)), 0.0, 2, pr.WHITE)
            elif tile_type.get("type") == "wall":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wall_texture"), pr.Vector2((x*tile_width - game_camera.x), (y*tile_height - game_camera.y)), 0.0, 1, pr.WHITE)
            elif tile_type.get("type") == "stone":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("grey_tile_texture"), pr.Vector2((x*tile_width - game_camera.x), (y*tile_height - game_camera.y)), 0.0, 1, pr.WHITE)
            elif tile_type.get("type") == "carpet":  #change to other tile               
                pr.draw_texture_ex(game_assets.get("textures",{}).get("orange_tile_texture"), pr.Vector2((x*tile_width - game_camera.x), (y*tile_height - game_camera.y)), 0.0, 1, pr.WHITE)
            if is_highlight:
                pr.draw_rectangle_lines(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, pr.WHITE)

    # draw the player also
    player_render_pos = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - 20 - game_camera.x, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y - 16)    
    pr.draw_texture_ex(game_assets.get("textures",{}).get("blue_oxford_texture"), player_render_pos, 0.0, 2, pr.WHITE)    
    # and a dot at his center for debug purposes
    # player_width_that_i_am_using = 16
    # player_height_that_i_am_using = 16
    # pr.draw_circle(int(player_pos["x"] + player_width_that_i_am_using  - game_camera.x), int(player_pos["y"] + player_height_that_i_am_using - game_camera.y), 5, pr.RED)

    for entity in entities.values():
        if entity.get("type","") == "buddha":
            pr.draw_texture_ex(game_assets.get("textures",{}).get("buddha_texture"), pr.Vector2((entity.get("position",{}).get("x",0) - game_camera.x), (entity.get("position",{}).get("y",0) - game_camera.y)), 0.0, 1.5, pr.WHITE)
        elif entity.get("type","") == "red head":
            texture_to_use = game_assets.get("textures",{}).get("red_head_texture")
            texture_scale = 2
            texture_x = (entity.get("position",{}).get("x",0) - game_camera.x) - (texture_to_use.width*texture_scale) / 2
            texture_y = (entity.get("position",{}).get("y",0) - game_camera.y) - (texture_to_use.height*texture_scale) / 2            

            pr.draw_texture_ex(texture_to_use, pr.Vector2(texture_x, texture_y), 0.0, texture_scale, pr.WHITE)


def transition_debug_state(current):
    state_transitions = {
        "clear" : "player_debug",
        "player_debug" : "clear",                
    }
    return state_transitions.get(current)


def transition_editor_state(current):
    state_transitions = {
        "play" : "editing",
        "editing" : "entity_placing",        
        "entity_placing" : "play",
    }
    return state_transitions.get(current)

def transition_collision_state(current):
    state_transitions = {
        "normal" : "noclip",
        "noclip" : "normal",
    }
    return state_transitions.get(current)

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

def update_projectiles(main_arena):
    # this should be something like
    # for each projectile
    # test against the environment (easy, since it's a tilemap)
    # test against the entities (couple hundred at most?)
    # resolve collision to environment or entity
    # or advance along the velocity line
    # bullet drop is just a time limit, in a sense
    # could also get bullets to collide with themselves?
    # note that collisions need to be checked between frames,
    # via raycasting/line intersection
    # is a point on a line or not should just resolve to
    # same direction vector with smaller magnitude?



    # tile map collision
    
    # entity collision

    # bullet-to-bullet collision

    # then there is a question about which came first

    # list of projectiles seems to make sense

    projectile_list = []

    for projectile in projectile_list:
        velocity = projectile.get("velocity") # direction and speed
        velocity = projectile.get("velocity")

    pass

def spawn_projectile(main_arena, origin, bullet_speed):
    projectile_list = []




def update_camera(game_camera, mode, player_pos, dt):    
    camera_speed = 500
    up = 0
    across = 0

    # let's go for a bounded box camera

    free_nav_modes = {"editing", "entity_placing"}
    
    if mode in free_nav_modes:
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
    else:
        game_camera.position.x = player_pos["x"] - pr.get_screen_width()/2
        game_camera.position.x = max(0, game_camera.position.x)
        game_camera.position.y = player_pos["y"] - pr.get_screen_height()/2
        game_camera.position.y = max(0, game_camera.position.y)
        
    
    return game_camera

def make_default_position(x,y,z):
    return pr.Vector3(x,y,z)

def make_default_player(x,y,z):
    player = {}
    pos = {}

    pos["x"] = x
    pos["y"] = y
    pos["z"] = z
    # should do the offset thing too, just store tile coord and an offset
    pos["tile_x"] = 0
    pos["tile_y"] = 0

    player["player_width"] = 24 #drawing at double scale
    player["player_height"] = 24

    player["position"] = pos

    return player

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
        if do_button(pr.Vector2(dropdown_x, dropdown_y + drawn*height), width, height, f"{saved_file}"):
            selected_file = i
        drawn += 1    

    do_load = False
    if do_button(pr.Vector2(dropdown_x + 200, dropdown_y), 100, 40, f"load {saved_files[selected_file]}"):
        do_load = True
    return selected_file, do_load


    

    

g_save_directory = "saved_editor_states"

def load_state(file_name):
    directory = g_save_directory           
    file_path = os.path.join(directory, file_name)        
    try:
        with open(file_path, "rb") as f:
            new_arena = pickle.load(f)
        pr.draw_text(f"loaded editor state {file_path}", 400, 40, 30, pr.WHITE)        
        return new_arena
        print(f"saved editor state")
    except Exception as e:
        print(f"issue saving state {e}")        

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

def load_entity_types():
    entity_types = [
        "buddha",
        "red head"
    ]

    return entity_types
    
def load_textures():
    result = {}    
    result["wood_texture"] = pr.load_texture("art/WoodTest.png")
    result["wall_texture"] = pr.load_texture("art/Wall.png")
    result["red_head_texture"] = pr.load_texture("art/RedHead.png")
    result["blue_oxford_texture"] = pr.load_texture("art/blue_oxford.png")
    result["grey_tile_texture"] = pr.load_texture("art/grey_tile_32x.png")
    result["orange_tile_texture"] = pr.load_texture("art/orange_tile_32x.png")

    result["buddha_texture"] = pr.load_texture("art/buddha_128.png")
    return result

def new_pos_from_old(old):
    new_pos = {
        "x" : old.get("x",0),
        "y" : old.get("y",0),
        "z" : old.get("z",0),
        "tile_x" : old.get("tile_x", 0),
        "tile_y" : old.get("tile_y", 0)
    }
    return new_pos

def get_tile_index_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]    
    tile_pos_x = int((pos.get("x",0))/tile_width)
    tile_pos_y =  int((pos.get("y",0))/tile_height)
    tile_x = tile_pos_x % map_width
    tile_y = tile_pos_y  % map_height

    return {"tile_x" : tile_x, "tile_y" : tile_y}

def get_abs_pos_from_index(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]    

    abs_x = tile_map["tile_width"] * pos.get("tile_x",0) + pos.get("x",0)
    abs_y = tile_map["tile_height"] * pos.get("tile_y",0) + pos.get("y",0)
    
    return {"x" : abs_x, "y" : abs_y}
                  


def get_tile_type_from_indices(tile_x, tile_y, tile_map):
    map_width = tile_map.get("map_width", 0)
    tile_index_to_test = tile_map["tiles"][tile_y*map_width + tile_x].get("index",0)
    tile_type = tile_map["tile_types"][tile_index_to_test]
    return tile_type

def get_tile_type_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]

    additional_x_tiles = 0
    additional_y_tiles = 0
    if pos["x"] > tile_width:
        additional_x_tiles = int(pos.get("x",0) / tile_width)        

    if pos["x"] < 0:
        additional_x_tiles = -int((tile_width + abs(pos.get("x",0))) / tile_width)
        

    if pos["y"] < 0:
        additional_y_tiles = -int((tile_height + abs(pos.get("y",0))) / tile_height)
        # I think this will do us?                

    if pos["y"] > tile_height:
        additional_y_tiles = int(pos.get("y",0) / tile_height)        

    tile_x = pos.get("tile_x") + additional_x_tiles
    tile_x = tile_x % map_width
    tile_y = pos.get("tile_y") + additional_y_tiles
    tile_y = tile_y  % map_height
    if debug_queue is not None:
        debug_item = {
            "type" : "tile",
            "tile_x" : tile_x,
            "tile_y" : tile_y,
            "tile_width" : tile_width,
            "tile_height" : tile_height,
            "color" : "PINK",
            "drawing_function" : draw_debug_tile,
            "z_sort" : 1

        }    
        debug_queue.append(debug_item)

    tile_index_to_test = tile_map["tiles"][tile_y*map_width + tile_x].get("index",0)
    tile_type = tile_map["tile_types"][tile_index_to_test]
    return tile_type.get("type","blank")

def tile_type_is_collidable(tile_type):
    collision_map = {
        "blank_tile" : False,
        "carpet" : False,
        "wall" : True
    }
    return collision_map.get(tile_type, False)

def vec2_add(a, b):
    return {"x": a.get("x",0) + b.get("x",0),
            "y": a.get("y",0) + b.get("y",0)}

def vec2_scale(v, s):
    return {"x": v.get("x",0) * s,
            "y": v.get("y",0) * s}

def vec2_subtract(a, b):
    return {"x": a.get("x",0) - b.get("x",0),
            "y": a.get("y",0) - b.get("y",0)}

def vec2_normalize(vector):
    mag = math.sqrt(vector["x"]**2 + vector["y"]**2)
    if mag > 0:
        vector["x"] /= mag
        vector["y"] /= mag
    return vector
    

def get_or_set(map, key, val):
    if key in map:
        return map[key]
    map[key] = val
    return val

def vec2_distance_tile(a, b):
    # TODO (Cooper) : make this also use the tiles they're on!
    return math.sqrt((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2)

def vec2_distance(a, b):    
    return math.sqrt((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2)


def vec2_dot(a, b):
    # remember a dot b is |a||b|cos(theta)
    # therefore if we use normalized and b
    # it is just the cosine of the angle
    # and hence...
    # well there it is
    return a.get("x", 0) * b.get("x", 0) + a.get("y", 0) * b.get("y", 0)

#def point_in_circle_of_radius_at_x_y(pos, circle):


def update_sight_direction(entity, player_pos, tile_map, new_direction):
    # zzz todo
    # we probably want to do something like
    # if we hear something, take a look
    # if something is in our peripheral vision, take a look
    # if we're bored, look at something interesting...? i.e not a wall
    # in which case, look opposite direction of something boring...?

    pass


def alice_can_see_bob(alice, bob_position, tile_map, debug_queue):
    # a does need a direction
    # should have a size of object too obviously
    line_to_bob = vec2_normalize(vec2_subtract(bob_position, alice))
    # you could model bob as a sphere
    # then just trace down the line of sight?

    bob_tiles = bob_position

    
    alice_pos = alice.get("position")
    alice_sight_angle = int(alice.get("sight_angle", 0))

    main_direction = vector_from_angle(alice_sight_angle)

    main_direction_scaled = vec2_scale(main_direction, 100)
    if debug_queue:
        debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : alice_pos.get("x"), "y" : alice_pos.get("y")},                                        
                    "pos_end" : {"x" : alice_pos.get("x") + main_direction_scaled.get("x"), "y" : alice_pos.get("y") + main_direction_scaled.get("y")},                                        
                    "line_width" : 1,                    
                    "color" : "PURPLE",
                    "z_sort" : -1,                    
                }
        debug_queue.append(debug_item)

    sight_range = 200
    bob_radius = 20

    alice_fov = 180

    angle_start = alice_sight_angle - int(alice_fov/2)
    angle_end = alice_sight_angle + int(alice_fov/2)

    step_size = 10

    # ideally what we do here
    # is have the lines follow a sort of radial fall off
    # so people can see far ahead
    # but less so in their peripheral
    # it might also be fun to play with the idea of 'motion' as a giveway
    for angle in range(angle_start, angle_end, step_size):        
        alice_direction_of_sight_normalized = vector_from_angle(angle)
        can_see = ray_along_tiles_hits_target_tile(alice_pos, bob_tiles, sight_range, int(bob_radius)/2, alice_direction_of_sight_normalized, tile_map, debug_queue)
        if can_see:
            return True        
    result = False

    return result

def get_neighbouring_tiles(tile, tile_map):
    # the idea here is we return the neighbouring tiles
    # which is like our 'adjacency matrix', I suppose
    # we could in fact generate them when the tilemap is initially made?
    # we want the i,j form    
    tile_x = tile.get("tile_x")
    tile_y = tile.get("tile_y")
    

    # our max case is eight

    # easy to add all then remove the ones we don't want...?    
    #tileH tileA tileB
    #tileG tile  tileC
    #tileF tileE tileD       
    

    adjacent_tiles = [
    {"tile_x" : tile_x,  "tile_y" : tile_y - 1}, #A
    {"tile_x" : tile_x+1,  "tile_y" : tile_y - 1}, #B
    {"tile_x" : tile_x+1,  "tile_y" : tile_y}, #C
    {"tile_x" : tile_x+1,  "tile_y" : tile_y+1}, #D
    {"tile_x" : tile_x,  "tile_y" : tile_y+1}, #E
    {"tile_x" : tile_x-1,  "tile_y" : tile_y+1}, #F
    {"tile_x" : tile_x-1,  "tile_y" : tile_y}, #G
    {"tile_x" : tile_x-1,  "tile_y" : tile_y-1}] #H

    for new_tile in adjacent_tiles:
        if new_tile.get("tile_x") < 0 or new_tile.get("tile_x") >= tile_map.get("map_width") or new_tile.get("tile_y") < 0 or new_tile.get("tile_y") >= tile_map.get("map_height"):
            adjacent_tiles.remove(new_tile)

    return adjacent_tiles

    
    
def ray_along_tiles_hits_target_tile(original_position, target_tile, end_range, step_size, normalized_ray_direction, tile_map, debug_queue = None):

    for i in range(0, end_range, int(step_size/2)):
        
        dist_to_push = i
        ray = vec2_scale(normalized_ray_direction, dist_to_push)
        pos_test = vec2_add(ray, original_position)
        

        test_tiles = get_tile_index_from_pos(pos_test, tile_map)

        

        found_tile = get_tile_type_from_indices(test_tiles.get("tile_x",0), test_tiles.get("tile_y",0), tile_map)


        if tile_type_is_collidable(found_tile.get("type","")):
            if debug_queue is not None:
                debug_item = {
                    "type" : "tile",
                    "tile_x" : test_tiles.get("tile_x",0),
                    "tile_y" : test_tiles.get("tile_y",0),
                    "tile_width" : tile_map.get("tile_width",5),
                    "tile_height" : tile_map.get("tile_height",5),
                    "color" : "PINK",
                    "drawing_function" : draw_debug_tile,
                    "z_sort" : 1

                }    
                debug_queue.append(debug_item)
            return False        
        else:
            if debug_queue is not None:
                debug_item = {
                    "type" : "tile",
                    "tile_x" : test_tiles.get("tile_x",0),
                    "tile_y" : test_tiles.get("tile_y",0),
                    "tile_width" : tile_map.get("tile_width",5),
                    "tile_height" : tile_map.get("tile_height",5),
                    "color" : "RED",
                    "drawing_function" : draw_debug_tile,
                    "z_sort" : 1

                }    
                debug_queue.append(debug_item)

        
        if tiles_equal(test_tiles, target_tile):
            return True
    return False           

def tiles_equal(a, b):
    return a.get("tile_x",0) == b.get("tile_x",0) and a.get("tile_y",0) == b.get("tile_y",0)
        










    # draw a
    pass

def make_player_points(player_info):
    player_pos = player_info.get("position",{}) # top left
    # true if we think in terms of offset
    player_pos_top_right = {"x" : player_pos.get("x",0) + player_info.get("player_width",0),
                            "y" : player_pos.get("y",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_bottom_right = {"x" : player_pos.get("x",0) + player_info.get("player_width",0),
                            "y" : player_pos.get("y",0) + player_info.get("player_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_left = {"x" : player_pos.get("x",0),
                            "y" : player_pos.get("y",0) + player_info.get("player_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }

    player_points = {
        "top_left" : player_pos,
        "top_right" : player_pos_top_right,
        "bottom_left" : player_pos_bottom_left,
        "bottom_right" : player_pos_bottom_right,
    }        
    
    return player_points

def check_collisions_on_tilemap(player_points, tile_map, debug_queue):
    # zzz use this for any entity
    collisions = { "x" : False, "y" : False}
    for potential_pos in player_points.values():    
        new_pos_x_direction = new_pos_from_old(potential_pos)
        new_pos_y_direction = new_pos_from_old(potential_pos)
        tile_at_pos_x = get_tile_type_from_pos(new_pos_x_direction, tile_map, debug_queue)
        tile_at_pos_y = get_tile_type_from_pos(new_pos_y_direction, tile_map, debug_queue)
        if tile_type_is_collidable(tile_at_pos_x):
            collisions["x"] = True
        if tile_type_is_collidable(tile_at_pos_y):
            collisions["y"] = True
    return collisions

def copy_entity_pos(existing):
    return {
        "x" : existing.get("x",0),
        "y" : existing.get("y",0),
        "z" : existing.get("z",0),
        "tile_x" : existing.get("tile_x",0),
        "tile_y" : existing.get("tile_y",0),
    }

def move_entity_towards_target_abs(entity, target_position, dt):
    # start with a straight line
    # returns an updated position, doesn't     
    vec2_between = vec2_normalize(vec2_subtract(target_position, entity.get("position",{})))

    # we can also set our heading here
    entity["sight_angle"] = angle_from_vector(vec2_between)
    # obviously we should move to 'proper' velocity but it's just a tad harder
    default_speed = 30
    entity_speed = entity.get("speed", default_speed)
    new_entity_velocity = vec2_scale(vec2_between, entity_speed * dt)

    # TODO (Cooper) we also need to do our collision logic here

    new_entity_position = vec2_add(entity.get("position",{}), new_entity_velocity)
    return new_entity_position



def idle_redhead_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    entity_pos = entity.get("position",{})        
    next_state = current_state
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    entity_pos = entity.get("position",{})
    player_pos_abs = { "x" : player_pos.get("x",0) + player_pos.get("tile_x",0) * tile_width,
                          "y" : player_pos.get("y",0) + player_pos.get("tile_y",0) * tile_height}
    
    entity_collide_distance = 5
    bored_timer = entity.get("bored_timer", 0)

    bored_threshold = 5
        
    if vec2_distance(entity_pos, player_pos_abs) < entity_collide_distance:
        next_state = "angry and attacking"
    elif alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        next_state = "angry chase"
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)
    else:
        bored_timer += dt
        if bored_timer >= bored_threshold:
            bored_timer = 0
            new_angle = random.randint(0,360)
            new_angle = new_angle % 360
            new_vec = vector_from_angle(new_angle)
            entity["sight_angle"] = new_angle            
            # pick a new random direction...?
    entity["bored_timer"] = bored_timer

    return next_state

def deg_to_rad(deg):
    if not deg:
        deg = 0
    return math.pi * (deg / 180.0)

def rad_to_deg(rad):
    if not rad:
        rad = 0
    return (rad * 180.0) / math.pi 

def vector_from_angle(angle_deg):
    angle = deg_to_rad(angle_deg)
    x = math.cos(angle)
    y = math.sin(angle)
    return {"x" : x, "y" : y}



def angle_from_vector(v):
    x = v.get("x",0)
    y = v.get("y",0)
    if x == 0:
        if y == 1:
            return 0        
        return 180
    if y == 0:
        if x == 1:
            return 90
        return 270
    tan_ratio = y / x
    angle = rad_to_deg(math.atan2(y, x))
    # TODO angle from Vector...    
    return angle

def angry_chase_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    next_state = current_state
    can_see = True
    if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)
    else:
        can_see = False
    entity_collide_distance = 5
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    entity_pos = entity.get("position",{})
    player_pos_abs = { "x" : player_pos.get("x",0) + player_pos.get("tile_x",0) * tile_width,
                          "y" : player_pos.get("y",0) + player_pos.get("tile_y",0) * tile_height}
        
        
    target_pos = get_abs_pos_from_index(entity.get("last_seen_player_pos"), tile_map, debug_queue)
    new_position = move_entity_towards_target_abs(entity, target_pos, dt)
    
    entity.get("position",{})["x"] = new_position.get("x", 0)
    entity.get("position",{})["y"] = new_position.get("y", 0)        

    if vec2_distance(new_position, player_pos_abs) < entity_collide_distance:
        next_state = "angry and attacking"

    dest_threshold = 5
    give_up_threshold = 3
    if not can_see and vec2_distance(new_position, target_pos) < dest_threshold:
        get_or_set(entity, "give_up_time", 0)
        entity["give_up_time"] += dt
        if entity["give_up_time"] > give_up_threshold:
            next_state = "idle"
    return next_state


    

def transition_entity_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    # TODO in addition to line of sight
    # need like a line of sound / within earshot function
    next_state = current_state
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)    

    if current_state == "idle":
        next_state = idle_redhead_state(entity, current_state, player_pos, tile_map, debug_queue, dt)        
    elif current_state == "angry chase":        
        # this is essentially a 'go to last position' state
        # with maybe a different animation and / or speed
        next_state = angry_chase_state(entity, current_state, player_pos, tile_map, debug_queue, dt)
    elif current_state == "angry and attacking":        
        if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
            # keep attacking
            pass
        else:
            next_state = "idle"            

    return next_state

    

def update_entities(entities, tile_map, player_info, editor_mode, collision_mode, dt, debug_queue = None):
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    if editor_mode != "play":
        return
    
    player_pos = player_info.get("position",{}) # top left

    for entity in entities.values():        
        # TODO (Cooper) : move this stuff into an update function later
        if entity.get("type","") == "red head":
            # he needs to know about the environment (the tilemap)
            # he needs to know about potentially other entities...
            # he definitely needs to know about the player
            # the 'other entities' is interesting because it opens up
            # bioshock like interactions where one monster could do something with another
            # I kind of like that potential
            
            current_state = get_or_set(entity, "current state", "idle")
            next_state = transition_entity_state(entity, current_state, player_pos, tile_map, debug_queue, dt)
            entity["current state"] = next_state
            if debug_queue is not None:
                debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : entity.get("position",{}).get("x"), "y" : entity.get("position",{}).get("y")},                                        
                    "font_size" : 16,
                    "text" : f"{entity["current state"]}",
                    "color" : "WHITE",
                    "z_sort" : 0,                    
                }
                debug_queue.append(debug_item)


def make_tile_x_y(x, y):
    return {"tile_x" : x, "tile_y" : y}

def pathfind_test_on_player(player_info, tile_map, game_camera, debug_queue = None):
    if "path" not in player_info:
        player_info["test_path"] = []
    mouse_pos_world = pr.get_mouse_position()
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
        mouse_tile_pos = make_tile_x_y(int((mouse_pos_world.x + game_camera.x)/tile_width), int((mouse_pos_world.y + game_camera.y)/tile_height))
        player_pos = player_info.get("position",{})
        target_tile_from_tile_map = tile_map.get("tiles")[mouse_tile_pos.get("tile_y")*tile_map.get("map_width") + mouse_tile_pos.get("tile_x")]
        start_tile_from_tile_map = tile_map.get("tiles")[player_pos.get("tile_y")*tile_map.get("map_width") + player_pos.get("tile_x")]

        player_info["test_path"] = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)

    if debug_queue is not None:
        for tile in player_info["test_path"]:
            debug_item = {
                "type" : "tile",
                "tile_x" : tile.get("tile_x"),
                "tile_y" : tile.get("tile_y"),
                "tile_width" : tile_width,
                "tile_height" : tile_height,
                "color" : "GREEN",
                "drawing_function" : draw_debug_tile,
                "z_sort" : 1

            }    
            debug_queue.append(debug_item)
    

def update_player_position(tile_map, player_info, editor_mode, collision_mode, dt, debug_queue = None):
    # i think the offset should be relative to _actual_ tile width
    # and so our world position is always a sum of the tile start pos + offset

    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]

    if editor_mode != "play":
        return player_info.get("position",{})
    
    player_pos = player_info.get("position",{}) # top left
    # true if we think in terms of offset
    player_pos_top_right = {"x" : player_pos.get("x",0) + player_info.get("player_width",0),
                            "y" : player_pos.get("y",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_bottom_right = {"x" : player_pos.get("x",0) + player_info.get("player_width",0),
                            "y" : player_pos.get("y",0) + player_info.get("player_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_left = {"x" : player_pos.get("x",0),
                            "y" : player_pos.get("y",0) + player_info.get("player_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }

    player_points = {
        "top_left" : player_pos,
        "top_right" : player_pos_top_right,
        "bottom_left" : player_pos_bottom_left,
        "bottom_right" : player_pos_bottom_right,
    }

    collisions = { "x" : False, "y" : False}

    

    #need to test 4 corners I believe
    player_speed = 200
    

    
    # I think what we should do is resolve the vector into two components
    # that are perpendicular
    # and check each of those for collisions
    # return either 0 or motion vectors,
    # then sum thhem
    new_pos = new_pos_from_old(player_pos)


    # assume we CAN move

    # need a direction vector to first normalize...

    direction_vector = {"x" : 0.0, "y" : 0.0}


    if pr.is_key_down(pr.KeyboardKey.KEY_A):
        direction_vector["x"] = -1.0        
    if pr.is_key_down(pr.KeyboardKey.KEY_D):
        direction_vector["x"] = 1.0        
    if pr.is_key_down(pr.KeyboardKey.KEY_W):
        direction_vector["y"] = -1.0        
    if pr.is_key_down(pr.KeyboardKey.KEY_S):
        direction_vector["y"] = 1.0        

    run_multiplier = 0
    if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT):
        run_multiplier = 4

    if run_multiplier:
        player_speed *= run_multiplier

    direction_vector = vec2_normalize(direction_vector)    

    new_pos["x"] += direction_vector["x"] * dt * player_speed
    new_pos["y"] += direction_vector["y"] * dt * player_speed
        


    if collision_mode != "noclip":
        # apply collision detection if needed
        for potential_pos in player_points.values():    
            if debug_queue is not None:
                debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle,
                    "pos" : potential_pos,                    
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "radius" : 2,
                    "color" : "RED",
                    "z_sort" : 0,
                    "tile_width" : tile_width,
                    "tile_height" : tile_height
                }
                debug_queue.append(debug_item)
            new_pos_x_direction = new_pos_from_old(potential_pos)
            new_pos_y_direction = new_pos_from_old(potential_pos)
            
            # we should probably address rebindable keys somewhat early on        
            if pr.is_key_down(pr.KeyboardKey.KEY_A):
                new_pos_x_direction["x"] -= dt*player_speed
            if pr.is_key_down(pr.KeyboardKey.KEY_D):
                new_pos_x_direction["x"] += dt*player_speed
            if pr.is_key_down(pr.KeyboardKey.KEY_W):
                new_pos_y_direction["y"] -= dt*player_speed
            if pr.is_key_down(pr.KeyboardKey.KEY_S):
                new_pos_y_direction["y"] += dt*player_speed
            
            # now check for collision
            
            
            tile_at_pos_x = get_tile_type_from_pos(new_pos_x_direction, tile_map, debug_queue)
            tile_at_pos_y = get_tile_type_from_pos(new_pos_y_direction, tile_map, debug_queue)
            if tile_type_is_collidable(tile_at_pos_x):
                collisions["x"] = True
            if tile_type_is_collidable(tile_at_pos_y):
                collisions["y"] = True

    
    if collisions["x"]:
        new_pos["x"] = player_pos["x"]
    if collisions["y"]:
        new_pos["y"] = player_pos["y"]    
    
    
    
    

    if new_pos["x"] > tile_width:
        additional_x_tiles = int(new_pos.get("x",0) / tile_width)
        new_pos["tile_x"] += additional_x_tiles
        new_pos["x"] = new_pos["x"] % tile_width

    if new_pos["x"] < 0:
        additional_x_tiles = int((tile_width + abs(new_pos.get("x",0))) / tile_width)
        new_pos["tile_x"] -= additional_x_tiles

        new_pos["x"] = tile_width + new_pos["x"]

    if new_pos["y"] < 0:
        additional_y_tiles = int((tile_height + abs(new_pos.get("y",0))) / tile_height)
        # I think this will do us?
        
        new_pos["tile_y"] -= additional_y_tiles    
        new_pos["y"] = new_pos["y"] + tile_height

    if new_pos["y"] > tile_height:
        additional_y_tiles = int(new_pos.get("y",0) / tile_height)
        # I think this will do us?
        
        new_pos["tile_y"] += additional_y_tiles    

        new_pos["y"] = new_pos["y"] % tile_height

    

    
    
    

    
    return new_pos

def draw_debug_circle(debug_item, camera):
    x = debug_item.get("pos", {}).get("x") + debug_item.get("pos",{}).get("tile_x", 0) * debug_item.get("tile_width")
    y = debug_item.get("pos", {}).get("y") + debug_item.get("pos",{}).get("tile_y", 0) * debug_item.get("tile_height")    
    cx = int(x - camera.position.x)
    cy = int(y - camera.position.y)
    rad = debug_item.get("radius", 0)
    color = color_map(debug_item.get("color", ""))
    pr.draw_circle(cx, cy, rad, color)

def draw_debug_tile(debug_item, camera):
    tile_width = debug_item.get("tile_width", 0)
    tile_height = debug_item.get("tile_height", 0)
    color = color_map(debug_item.get("color", "PINK"))
    x = debug_item.get("tile_x", 0) * tile_width
    y = debug_item.get("tile_y", 0) * tile_height
    camera_x = camera.position.x
    camera_y = camera.position.y
    draw_x = int(x - camera_x)
    draw_y = int(y - camera_y)

    pr.draw_rectangle(draw_x, draw_y, tile_width, tile_height, color)

def draw_debug_line(debug_item, camera):
    color = color_map(debug_item.get("color", "PINK"))

    start_x = debug_item.get("pos_start").get("x") - camera.position.x
    start_y = debug_item.get("pos_start").get("y") - camera.position.y

    end_x = debug_item.get("pos_end").get("x") - camera.position.x
    end_y = debug_item.get("pos_end").get("y") - camera.position.y
    

    pr.draw_line_ex(pr.Vector2(start_x, start_y), pr.Vector2(end_x, end_y), debug_item.get("line_width"), color)


def draw_debug_text(debug_item, camera):
    x = debug_item.get("pos", {}).get("x") 
    y = debug_item.get("pos", {}).get("y") 
    text_to_draw = debug_item.get("text", "")
    font_size = debug_item.get("font_size", "")
    cx = int(x - camera.position.x)
    cy = int(y - camera.position.y)
    
    color = color_map(debug_item.get("color", ""))
    pr.draw_text(text_to_draw, cx, cy, font_size, color)
    

def draw_debug_item(debug_item, camera):
    # two ways we could do this
    # have a map of types to functions
    # or, add the drawing function on the argument
    # I kind of feel like it's ok to make a function that does the thing,
    # and attach it as a field in the map...
    # just make sure the function takes all required fields rather than 'self'

    # drawing_functions = {
    #     "tile" : draw_debug_tile
    # }

    # drawing_functions.get(debug_item.get("type",""), lambda x : x)(debug_item)
    # OR
    debug_item.get("drawing_function", lambda x, y : x)(debug_item, camera)
    
    

def update_and_render(main_arena, game_assets):
    # maybe we think of assets as things that can't be serialized, or are expensive to do so...
    # arena initialisation
    dt = pr.get_frame_time()
    mouse_pos = pr.get_mouse_position()
    time_elapsed = main_arena.get("time_elapsed", 0.0) 
    save_interval = 200
    save_elapsed = main_arena.get("save_elapsed", 0.0) 
    player_info = main_arena.get("player_info") # really more info
    debug_state = main_arena.get("debug_state", "clear") 

    

    


    if debug_state == "clear":
        debug_queue = None
    else:
        debug_queue = [] # queue.Queue()
    

    if not player_info:
        player_info = make_default_player(0,0,0)
                                     
    frame_arena = {} # this will be useful, to have a mutable per frame arena

    save_elapsed += dt
    saved_files = main_arena.get("saved_files") 
    
    do_load_level = main_arena.get("do_load_level", False) 
    editor_mode = main_arena.get("editor_mode", "editing")
    collision_mode = main_arena.get("collision_mode", "regular")

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F6):
        do_load_level = not do_load_level

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F8):
        editor_mode = transition_editor_state(editor_mode)
    
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F7):
        debug_state = transition_debug_state(debug_state)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F9):
        collision_mode = transition_collision_state(collision_mode)
    
    

    if not saved_files:
        saved_files = get_saved_files()

    textures = game_assets.get("textures")
    if not textures:
        textures = load_textures()
        game_assets["textures"] = textures

    entity_types = game_assets.get("entity_types")
    if not entity_types:
        entity_types = load_entity_types()
        game_assets["entity_types"] = entity_types

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F5): # save_elapsed >= save_interval or 
        save_state(main_arena)
        save_elapsed = 0.0
        saved_files = get_saved_files()

    ui_button_states = main_arena.get("ui_button_states")
    if not ui_button_states:
        ui_button_states = pmap()

    tile_map = main_arena.get("tile_map")

    entities = main_arena.get("entities")

    if not tile_map:
        tile_map = make_tile_map(1000, 1000, 32, 32)        

    if not entities:
        entities = {}

    
    

    use_mouse_screen_navigation =  ui_button_states.get("use_mouse_screen_navigation", True)
    current_tile_selection = main_arena.get("current_tile_selection", 0)

    current_entity_selection = main_arena.get("current_entity_selection", 0)

    

    

    # this is 'mutable' or at least expensive since it's a raylib/opengl call I think, don't want to spam it
    camera_3d = get_or_invoke(game_assets, "camera_3d", make_default_camera)        
    
    
    

    screen_width = main_arena.get("screen_width")
    screen_height = main_arena.get("screen_height")
    tile_size = 32
        
    #input handling
    player_info["position"] = update_player_position(player_info=player_info, editor_mode=editor_mode, collision_mode=collision_mode ,dt=dt, tile_map=tile_map, debug_queue=debug_queue)
    
    update_entities(entities=entities,player_info=player_info, editor_mode=editor_mode, collision_mode=collision_mode ,dt=dt, tile_map=tile_map, debug_queue=debug_queue)
    camera_3d = update_camera(camera_3d, mode=editor_mode, player_pos=player_info.get("position",{}), dt=dt)
    pathfind_test_on_player(player_info=player_info, tile_map=tile_map, game_camera=camera_3d.position, debug_queue=debug_queue)
    
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
    

    

    do_tile_map(camera_3d.position, entities, tile_map, pr.get_mouse_position(), current_tile_selection, current_entity_selection, game_assets, do_load_level, player_info.get("position",{}), editor_mode)

    pr.draw_text(editor_mode, 1700, 30, 20, pr.WHITE)

    if debug_state != "clear":
        pr.draw_text(debug_state, 1700, 50, 20, pr.WHITE)

    if editor_mode == "editing":
        tile_type = tile_map["tile_types"][current_tile_selection]
        tile_width = tile_map["tile_width"]
        tile_height = tile_map["tile_height"]
        draw_tile_texture_from_type(game_assets, tile_type, 1700, 100)
        pr.draw_text(tile_type.get("type",""), 1700, 50, 20, pr.WHITE)

    if editor_mode == "entity_placing":
        pr.draw_text(entity_types[current_entity_selection], 1700, 50, 20, pr.WHITE)

    

    if do_button(pr.Vector2(10, 100), name="reload assets"):        
        game_assets["textures"] = None

    if do_button(pr.Vector2(10, 140), name="reset player"):        
        player_info = None

    reset_all = False
    if do_button(pr.Vector2(10, 10), name="reset all"):        
        player_info = None
        tile_map = None
        game_assets["textures"] = None
        entities = None
        reset_all = True
        
    if tile_map and editor_mode == "editing":
        if do_button(pr.Vector2(10, 30), name=f"sel:{tile_map.get("tile_names",{}).get(current_tile_selection, "")}"):
            current_tile_selection = (current_tile_selection + 1) % tile_map.get("tile_types_amount", 1)
        current_tile_selection = (update_tile_selection(current_tile_selection, tile_map.get("tile_types_amount", 1))) % tile_map.get("tile_types_amount", 1)

    if tile_map and editor_mode == "entity_placing":        
        current_entity_selection = update_mousewheel_selection(current_entity_selection, len(entity_types))

    
    selected_save_index, load_saved_data = draw_load_level(main_arena, game_assets)
    if load_saved_data:
        main_arena = load_state(saved_files[selected_save_index])
        tile_map = main_arena.get("tile_map")

    
    #if debug_queue:
        
    if debug_queue:
        debug_queue = sorted(debug_queue, key=lambda x : x.get("z_sort", 0), reverse=True)
        for debug_item in debug_queue:
            draw_debug_item(debug_item, camera=camera_3d)

    pr.end_drawing()

    # update persistent variables here
    changes = main_arena.evolver()
    changes["debug_state"] = debug_state
    changes["collision_mode"] = collision_mode
    changes["editor_mode"] = editor_mode
    changes["do_load_level"] = do_load_level
    changes["time_elapsed"] = time_elapsed + dt
    changes["current_tile_selection"] = current_tile_selection
    changes["current_entity_selection"] = current_entity_selection
    changes["auto_reload"] = auto_reload    
    changes["ui_button_states"] = ui_button_states
    changes["save_elapsed"] = save_elapsed
    changes["saved_files"] = saved_files
    changes["tile_map"] = tile_map
    changes["entities"] = entities
    changes["player_info"] = player_info
    changes["selected_save_index"] = selected_save_index

    result = changes.persistent()    
    
    game_assets["camera_3d"] = camera_3d
    if reset_all:
        del game_assets["camera_3d"]

    return result
    
