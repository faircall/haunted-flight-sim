import math
import pickle
import os
import time

import random

import queue

import pyray as pr
from pyrsistent import m, pmap, v

import cyminiaudio as cma





from dataclasses import dataclass, field

g_default_entity_width = 16
g_default_entity_height = 16

g_test_see_through_walls = False

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

        
        

def get_tile_cost(tile_type):
    tile_costs = {
        "wall" : 999999999, 
    }
    

    return tile_costs.get(tile_type.get("type",""), 1)

def graph_cost(tile_a, tile_b, tile_map):
    a_type = get_tile_type_from_indices(tile_a.get("tile_x"), tile_a.get("tile_y"), tile_map)
    b_type = get_tile_type_from_indices(tile_b.get("tile_x"), tile_b.get("tile_y"), tile_map)
    a_cost = get_tile_cost(a_type)    
    b_cost = get_tile_cost(b_type)
    # do we want the sum....hrmm....
    # or could there be a special cost when transitioning beteen
    # special tiles even?
    return a_cost + b_cost    

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
            next_tile_from_map = tile_map.get("tiles")[tile_map.get("map_width")*next_tile.get("tile_y") + next_tile.get("tile_x") ]
            # if next_tile_from_map.get("neighbours") is None:
            #     print("hmmm")
            next_tile_id = get_tile_id_for_hash(next_tile)
            # if current_tile_id not in cost_so_far:
            #     print("argh")
            new_cost = cost_so_far.get(current_tile_id,0) + graph_cost(current, next_tile, tile_map)
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
    result.reverse()
    return result


    
    


def update_render_tile_map(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, game_assets, ignore, player_info, mode, debug_queue):
    # Todo:
    # tiles are tiles,
    # items are items, they can sit on top of tiles
    player_pos = player_info.get("position",{})
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

    mouse_tile_pos_offset_x = (mouse_pos_world.x + game_camera.x) - mouse_tile_pos.x*tile_width
    mouse_tile_pos_offset_y = (mouse_pos_world.y + game_camera.y) - mouse_tile_pos.y*tile_height



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
                        
                        # TODO : this is where we messed up!

                        offset_x = mouse_tile_pos_offset_x
                        offset_y = mouse_tile_pos_offset_y

                        # EXPLORE 
                        # opportunity to do interesting thing here
                        # where we store (and update!) entities on tiles
                        # which would allow us to do things like
                        # know about an explosion on a tile 
                        # and immediately damage all the entities on it 
                        # much faster for 'find the entities who are at location x/y/z'

                        new_entity["position"] = {"x" : offset_x, "y" : offset_y, "tile_x" : x, "tile_y" : y}

                        give_entity_stats_from_type(new_entity, entity_type)

                        if categorise_entity_type(entity_type) == "brains":
                            if "brains" not in entities:
                                entities["brains"] = {}
                            id = len(entities["brains"]) # this id system could use some improving!
                            new_entity["id"] = id                            
                            entities["brains"][id] = new_entity
                        elif categorise_entity_type(entity_type) == "pickups":
                            # in the C version we might want to 
                            # be slightly more clever about how we store ids 
                            # and whatnot
                            if "pickups" not in entities:
                                entities["pickups"] = {}
                            id = len(entities["pickups"]) # this id system could use some improving!
                            new_entity["id"] = id                            
                            entities["pickups"][id] = new_entity

                    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                        latest_id = max(len(entities) - 1,0)
                        if latest_id in entities:
                            del entities[latest_id]

                    
                            
                pr.draw_rectangle(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, tile_color)

            render_pos = pr.Vector2((x*tile_width - game_camera.x), (y*tile_height - game_camera.y))
            if tile_type.get("type") == "wood":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wood_texture"), render_pos, 0.0, 2, pr.WHITE)
            elif tile_type.get("type") == "wall":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("wall_texture"), render_pos, 0.0, 1, pr.WHITE)
            elif tile_type.get("type") == "stone":                
                pr.draw_texture_ex(game_assets.get("textures",{}).get("grey_tile_texture"), render_pos, 0.0, 1, pr.WHITE)
            elif tile_type.get("type") == "carpet":  #change to other tile               
                pr.draw_texture_ex(game_assets.get("textures",{}).get("orange_tile_texture"), render_pos, 0.0, 1, pr.WHITE)
            if is_highlight:
                pr.draw_rectangle_lines(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, pr.WHITE)

            if "decals" in tile_to_draw:
                for decal in tile_to_draw["decals"]:
                    if decal["type"] == "blood":
                        render_pos_x = render_pos.x + decal["offset_x"]
                        render_pos_y = render_pos.y + decal["offset_y"]
                        pr.draw_circle(int(render_pos_x), int(render_pos_y), decal.get("size",5), pr.RED)


    # draw the player also

    # make this a draw entity function
    player_render_pos = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - 20 - game_camera.x, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y - 16)    

    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - game_camera.x + 12, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y + 12)    
    
    if "aim_direction" not in player_info:
        player_info["aim_direction"] = {"x" : 0, "y" : 0}
    gun_pos = vec2_add_any(player_render_pos_center, player_info.get("aim_direction", {"x" : 0, "y" : 0}))
    if player_info.get("aim_direction", {"x" : 0, "y" : 0}).get("x") < 0:
        updated_gun_pos = vec2_add(vec2_scale(vec2_normalize(player_info.get("aim_direction")), 8), gun_pos)        
        gun_pos = pr.Vector2(gun_pos["x"], gun_pos["y"])
    else:
        gun_pos = pr.Vector2(gun_pos["x"], gun_pos["y"])

    gun_angle = angle_from_vector(player_info.get("aim_direction")) - 180 # some bs here

    #pr.draw_texture_ex(game_assets.get("textures",{}).get("blue_oxford_texture"), player_render_pos, 0.0, 2, pr.WHITE)    

    oxford_frame_key =  player_info.get("animation_frame", 0)   
    oxford_frame_number = game_assets.get("sprite_sheets",{}).get("blue_oxford_texture_sheet",{}).get(oxford_frame_key, 0)
    oxford_dest_rect = pr.Rectangle(int(player_render_pos.x), int(player_render_pos.y), 32*2, 32*2) # these 32s are in the thing actually
    oxford_source_rect = pr.Rectangle(oxford_frame_number*32, 0, 32, 32) # these 32s are in the thing actually
    pr.draw_texture_pro(game_assets.get("sprite_sheets",{}).get("blue_oxford_texture_sheet",{}).get("sheet"), oxford_source_rect, oxford_dest_rect, pr.Vector2(0,0), 0, pr.WHITE)
    pr.draw_line(int(player_render_pos_center.x), int(player_render_pos_center.y), int(gun_pos.x), int(gun_pos.y), pr.WHITE)
    
    
    if player_info.get("aim_direction").get("x") < 0:
        # zzz super slight bug here where it's drawing at the start and not accounting for the flip
        pr.draw_texture_ex(game_assets.get("textures",{}).get("pistol_texture_flipped"), updated_gun_pos, gun_angle + 180, 1, pr.WHITE)    
    else:
        pr.draw_texture_ex(game_assets.get("textures",{}).get("pistol_texture"), gun_pos, gun_angle, 1, pr.WHITE)    

    # HERE also draw reload status I think
    

    # and a dot at his center for debug purposes
    # entity_width_that_i_am_using = 16
    # entity_height_that_i_am_using = 16
    # pr.draw_circle(int(player_pos["x"] + entity_width_that_i_am_using  - game_camera.x), int(player_pos["y"] + entity_height_that_i_am_using - game_camera.y), 5, pr.RED)

    if "projectiles" not in entities:
        entities["projectiles"] = {}
    if "brains" not in entities:
        entities["brains"] = {}
    if "particle_systems" not in entities:
        entities["particle_systems"] = {}
    if "pickups" not in entities:
        entities["pickups"] = {}

    for key, particle_system in entities["particle_systems"].items():        
        if key == "taken":
            continue
        for particle in particle_system["particles"]:
            render_pos_x = tile_width * particle.get("position",{}).get("tile_x",0) + particle.get("position",{}).get("x",0) - game_camera.x
            render_pos_y = tile_height * particle.get("position",{}).get("tile_y",0) + particle.get("position",{}).get("y",0) - game_camera.y
            pr.draw_circle(int(render_pos_x), int(render_pos_y), particle.get("size",5), pr.RED)
    

    for entity in entities["projectiles"].values():        
        if entity.get("type","") == "bullet":
            render_x = entity["position"]["x"] - game_camera.x
            render_y = entity["position"]["y"] - game_camera.y
            pr.draw_rectangle(int(render_x), int(render_y), 4, 4, pr.BROWN)            
    for entity in entities["pickups"].values():        
        if entity.get("type","") == "pistol_ammo_pickup":
            texture_scale = 3
            texture_to_use = game_assets.get("textures",{}).get("pistol_ammo_pickup_texture")
            render_pos_x = tile_width * entity.get("position",{}).get("tile_x",0) + entity.get("position",{}).get("x",0) - game_camera.x
            render_pos_y = tile_height * entity.get("position",{}).get("tile_y",0) + entity.get("position",{}).get("y",0) - game_camera.y
            texture_x = (render_pos_x) - (texture_to_use.width*texture_scale) / 2
            texture_y = (render_pos_y) - (texture_to_use.height*texture_scale) / 2            
            pr.draw_texture_ex(texture_to_use, pr.Vector2(texture_x, texture_y), 0.0, texture_scale, pr.WHITE)
        elif entity.get("type","") == "health_pickup":
            texture_scale = 3
            texture_to_use = game_assets.get("textures",{}).get("health_pickup_texture")
            render_pos_x = tile_width * entity.get("position",{}).get("tile_x",0) + entity.get("position",{}).get("x",0) - game_camera.x
            render_pos_y = tile_height * entity.get("position",{}).get("tile_y",0) + entity.get("position",{}).get("y",0) - game_camera.y
            texture_x = (render_pos_x) - (texture_to_use.width*texture_scale) / 2
            texture_y = (render_pos_y) - (texture_to_use.height*texture_scale) / 2            
            pr.draw_texture_ex(texture_to_use, pr.Vector2(texture_x, texture_y), 0.0, texture_scale, pr.WHITE)            
    for entity in entities["brains"].values():        
        if entity.get("type","") == "buddha":
            texture_scale = 1
            texture_to_use = game_assets.get("textures",{}).get("buddha_texture")
            render_pos_x = tile_width * entity.get("position",{}).get("tile_x",0) + entity.get("position",{}).get("x",0) - game_camera.x
            render_pos_y = tile_height * entity.get("position",{}).get("tile_y",0) + entity.get("position",{}).get("y",0) - game_camera.y
            texture_x = (render_pos_x) - (texture_to_use.width*texture_scale) / 2
            texture_y = (render_pos_y) - (texture_to_use.height*texture_scale) / 2            
            pr.draw_texture_ex(texture_to_use, pr.Vector2(texture_x, texture_y), 0.0, texture_scale, pr.WHITE)
        elif entity.get("type","") == "red head":
            entity_frame_key =  entity.get("animation_frame", 0)   
            entity_frame_number = game_assets.get("sprite_sheets",{}).get("red_head_texture_sheet",{}).get(entity_frame_key, 0) 
            
            texture_to_use = game_assets.get("sprite_sheets",{}).get("red_head_texture_sheet",{}).get("sheet")
            texture_scale = 2
            render_pos_x = int(tile_width * entity.get("position",{}).get("tile_x",0) + entity.get("position",{}).get("x",0) - game_camera.x)
            render_pos_y = int(tile_height * entity.get("position",{}).get("tile_y",0) + entity.get("position",{}).get("y",0) - game_camera.y)

            texture_x = render_pos_x - 24
            texture_y = render_pos_y - 24            
            debug_str = f"angle is {entity.get("sight_angle",0)}"
            if debug_queue is not None:
                debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : render_pos_x, "y" : render_pos_y-10},                                        
                    "font_size" : 16,
                    "text" : debug_str,
                    "color" : "WHITE",
                    "z_sort" : 0,                    
                }
                debug_queue.append(debug_item)
            
            # texture_x = (render_pos_x) - (texture_to_use.width*texture_scale) / 2
            # texture_y = (render_pos_y) - (texture_to_use.height*texture_scale) / 2            
            

            # entity_dest_rect = pr.Rectangle(int(render_pos_x), int(render_pos_y), 24*2, 24*2) 
            entity_dest_rect = pr.Rectangle(int(texture_x), int(texture_y), 24*2, 24*2) 
            entity_source_rect = pr.Rectangle(entity_frame_number*24, 0, 24, 24) 
            pr.draw_texture_pro(game_assets.get("sprite_sheets",{}).get("red_head_texture_sheet",{}).get("sheet"), entity_source_rect, entity_dest_rect, pr.Vector2(0,0), 0, pr.WHITE)


def transition_debug_state(current):
    state_transitions = {
        "clear" : "player_debug",
        "player_debug" : "slow_bullets",
        "slow_bullets" : "clear",                
    }
    return state_transitions.get(current)

def transition_pause_state(current):
    state_transitions = {
        "paused" : "unpaused",
        "unpaused" : "paused",                
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


def make_projectile(responsible, spawn_pos, velocity, id, type):
    current_pos = {"x" : spawn_pos["x"], "y" : spawn_pos["y"]}
    bullet = {"entity_responsible" : "player",
                  "spawn_position" : spawn_pos,
                  "position" : current_pos,
                  "velocity" : velocity,
                  "id" : id,
                  "type" : type,
                  "timer" : 0
                  }
    return bullet


def give_entity_stats_from_type(entity, entity_type):
    if entity_type == "red head":
        entity["health"] = 60
        entity["attack_damage"] = 5
    elif entity_type == "buddha":
        entity["health"] = 600
    elif entity_type == "pistol_ammo_pickup":
        entity["value"] = 20
    elif entity_type == "health_pickup":
        entity["value"] = 25


    

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

    player["entity_width"] = 24 #drawing at double scale
    player["entity_height"] = 24

    player["position"] = pos

    player["health"] = 100

    player["ammo"] = {}

    player["ammo"]["pistol"] = 20    
    player["ammo"]["spare_pistol"] = 20

    return player

def get_reload_time(gun_type):
    times = {
        "pistol": 1.8 # this should be timed to the actual sound but it's roughly this
    }

    return times.get(gun_type, 0)

def get_clip_size(gun_type):
    sizes = {
        "pistol": 20
    }

    return sizes.get(gun_type, 0)

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
        "red head",
        "pistol_ammo_pickup",
        "health_pickup"
    ]
    return entity_types

def categorise_entity_type(entity_type):
    category_map =  {
        "buddha" : "brains",
        "red head" : "brains",
        "pistol_ammo_pickup" : "pickups",
        "health_pickup" : "pickups",
    }

    return category_map[entity_type]

def load_sound(engine, file_name, looping, volume, pitch, pan):
    sound = cma.Sound(engine, file_name)
    sound.looping = looping
    sound.volume = volume
    sound.pitch = pitch
    sound.pan = pan
    return sound

def load_pistol_pool(engine):
    variants = 10
    result = {"index" : 0, "pool" : []}
    for i in range(variants):        

        pistol_shot = load_sound(engine, "sounds/pistol_shot.wav", False, 0.5, 1 , 0)
        result["pool"].append(pistol_shot)
    return result

def load_sound_pool(engine, variants, base_file, base_volume, base_pitch, base_pan):    
    result = {"index" : 0, "pool" : []}
    for i in range(variants):        
        pool_sound = load_sound(engine, f"sounds/{base_file}", False, base_volume, base_pitch , base_pan)
        result["pool"].append(pool_sound)
    return result

def stop_pool_sounds(pool_name, sounds):
    if pool_name in sounds and sounds[pool_name] is not None:            
        for i in range(len(sounds[pool_name]["pool"])):
            sound_to_play = sounds[pool_name]["pool"][i]            
            sound_to_play.stop()
            sound_to_play.seek(0)        

def play_pool_sound(pool_name, sounds, rand_lower=-1, rand_upper=5, rand_base=25):
    if pool_name in sounds and sounds[pool_name] is not None:            
        sound_to_play_idx = sounds[pool_name]["index"]
        sound_to_play = sounds[pool_name]["pool"][sound_to_play_idx]
        sound_to_play.pitch = 1 + float(random.randint(rand_lower,rand_upper) / rand_base)
        sounds[pool_name]["index"] = (sounds[pool_name]["index"] + 1) % len(sounds[pool_name]["pool"])
        sound_to_play.stop()
        sound_to_play.seek(0)
        sound_to_play.start()

def load_sounds(engine):
    result = {}
    
    # player foot steps
    
    # enemy foot steps
    
    pistol_hit_wall = load_sound(engine, "sounds/pistol_hit_wall.wav", False, 0.75, 1, 0)

    pistol_reload = load_sound(engine, "sounds/pistol_reload.wav", False, 0.75, 1, 0)

    result["pistol_reload"] = pistol_reload

    result["player_footstep_pool"] = load_sound_pool(engine, 10, "player_footstep.wav", 0.75, 0.7, 0)
    result["pistol_pool"] = load_pistol_pool(engine)
    result["stagger_hit_pool"] = load_sound_pool(engine, 10, "pistol_hit_body.wav", 0.75, 0.7, 0)

    result["ammo_pickup_pool"] = load_sound_pool(engine, 10, "ammo_pickup.wav", 0.75, 0.7, 0)

    result["health_pickup_pool"] = load_sound_pool(engine, 10, "health_apply.wav", 0.75, 0.7, 0)

    result["death_hit_pool"] = load_sound_pool(engine, 10, "death_hit.wav", 0.5, 1, 0)

    result["pistol_empty_pool"] = load_sound_pool(engine, 10, "pistol_empty.wav", 0.5, 1, 0)
        
    result["pistol_hit_wall"] = pistol_hit_wall    


    return result
    

def load_sprite_sheets():
    result = {}    
    result["blue_oxford_texture_sheet"] =  {}
    result["blue_oxford_texture_sheet"]["sheet"] = pr.load_texture("art/blue_oxford_sheet.png")
    result["blue_oxford_texture_sheet"]["frame_width"] = 32 # kinda need to know these ahead of time currently
    result["blue_oxford_texture_sheet"]["frame_height"] = 32
    result["blue_oxford_texture_sheet"]["frames"] = result["blue_oxford_texture_sheet"]["sheet"].width / result["blue_oxford_texture_sheet"]["frame_width"]
    result["blue_oxford_texture_sheet"]["animation_frame"] = 0
    result["blue_oxford_texture_sheet"]["down_frame_start"] = 0
    result["blue_oxford_texture_sheet"]["up_frame_start"] = 7
    # this one would need to loop I think
    result["blue_oxford_texture_sheet"]["glance_frame_start"] = 2
    result["blue_oxford_texture_sheet"]["glance_frame_end"] = 4
    result["blue_oxford_texture_sheet"]["left_frame_start"] = 6
    result["blue_oxford_texture_sheet"]["right_frame_start"] = 5

    result["red_head_texture_sheet"] =  {}
    result["red_head_texture_sheet"]["sheet"] = pr.load_texture("art/redhead_sheet.png")
    result["red_head_texture_sheet"]["frame_width"] = 24
    result["red_head_texture_sheet"]["frame_height"] = 24

    result["red_head_texture_sheet"]["frames"] = result["red_head_texture_sheet"]["sheet"].width / result["red_head_texture_sheet"]["frame_width"]
    result["red_head_texture_sheet"]["animation_frame"] = 0
    result["red_head_texture_sheet"]["down_frame_start"] = 0
    result["red_head_texture_sheet"]["up_frame_start"] = 1    
    # result["red_head_texture_sheet"]["glance_frame_start"] = 2
    # result["red_head_texture_sheet"]["glance_frame_end"] = 4
    result["red_head_texture_sheet"]["left_frame_start"] = 3
    result["red_head_texture_sheet"]["right_frame_start"] = 2

    result["red_head_texture_sheet"]["death_frame_start"] = 19



    return result
    

    
def load_textures():
    result = {}    
    # we could make this easier to use if we monitored the files in the directory once
    # a second and then did a reload when a new one was in there!
    result["pistol_texture"] = pr.load_texture("art/pistol.png")
    result["pistol_texture_flipped"] = pr.load_texture("art/pistol_flipped.png")
    result["wood_texture"] = pr.load_texture("art/WoodTest.png")
    result["wall_texture"] = pr.load_texture("art/Wall.png")
    result["red_head_texture"] = pr.load_texture("art/RedHead.png")
    result["blue_oxford_texture"] = pr.load_texture("art/blue_oxford.png")
    result["grey_tile_texture"] = pr.load_texture("art/grey_tile_32x.png")
    result["orange_tile_texture"] = pr.load_texture("art/orange_tile_32x.png")

    result["pistol_ammo_pickup_texture"] = pr.load_texture("art/pistol_ammo_pickup.png")
    result["health_pickup_texture"] = pr.load_texture("art/health_pickup.png")

    

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

def get_flat_tile_index(x, y, tile_map, debug_queue = None):    
    return y*tile_map.get("map_width") + x

def get_tile_at_index(flat_index, tile_map):
    # bounds check
    if flat_index < 0 or flat_index >= len(tile_map["tiles"]):
        print("warning: bad tile index!")
        flat_index = 0
    tile_at_index = tile_map["tiles"][flat_index]
    return tile_at_index



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

def get_tile_index_and_offset_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]    
    tile_pos_x = int((pos.get("x",0))/tile_width)
    tile_pos_y =  int((pos.get("y",0))/tile_height)
    tile_x = tile_pos_x % map_width
    tile_y = tile_pos_y  % map_height

    offset_x = pos["x"] - (tile_x * tile_width)
    offset_y = pos["y"] - (tile_y * tile_height)

    return {"tile_x" : tile_x, "tile_y" : tile_y, "x" : offset_x, "y" : offset_y}

def get_abs_pos_from_index(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]    

    
    abs_x = tile_map["tile_width"] * pos.get("tile_x",0) + pos.get("x",16)
    abs_y = tile_map["tile_height"] * pos.get("tile_y",0) + pos.get("y",16)
    
    return {"x" : abs_x, "y" : abs_y}
                  


def get_tile_type_from_indices(tile_x, tile_y, tile_map):
    map_width = tile_map.get("map_width", 0)
    tile_index_to_test = tile_map["tiles"][tile_y*map_width + tile_x].get("index",0)
    tile_type = tile_map["tile_types"][tile_index_to_test]
    return tile_type


def get_tiles_from_pos(pos, tile_map, debug_queue = None):
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

    return {"tile_x" : tile_x, "tile_y" : tile_y}
    # if debug_queue is not None:
    #     debug_item = {
    #         "type" : "tile",
    #         "tile_x" : tile_x,
    #         "tile_y" : tile_y,
    #         "tile_width" : tile_width,
    #         "tile_height" : tile_height,
    #         "color" : "PINK",
    #         "drawing_function" : draw_debug_tile,
    #         "z_sort" : 1

    #     }    
    #     debug_queue.append(debug_item)

def get_tile_type_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tiles = get_tiles_from_pos(pos, tile_map, debug_queue = None)
    tile_x = tiles.get("tile_x")
    tile_y = tiles.get("tile_y")
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
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

def vec2_add_any(a, b):
    if not isinstance(a, dict):
        a = {"x" : a.x, "y" : a.y}

    if not isinstance(b, dict):
        a = {"x" : b.x, "y" : b.y}

    return vec2_add(a, b)

def vec2_add_just(a, b):
    # designed to take an A that might only be partially a vector (and also have other stuff)
    new_a = copy_entity_pos(a)
    vec2_mutation_add(new_a, b)
    return new_a

def vec2_mutation_add(a_to_mutate, b):
    a_to_mutate["x"] += b["x"]
    a_to_mutate["y"] += b["y"]

def vec2_add(a, b):
    return {"x": a.get("x",0) + b.get("x",0),
            "y": a.get("y",0) + b.get("y",0)}

def vec2_scale(v, s):
    return {"x": v.get("x",0) * s,
            "y": v.get("y",0) * s}

def vec2_subtract(a, b):
    return {"x": a.get("x",0) - b.get("x",0),
            "y": a.get("y",0) - b.get("y",0)}

def vec2_norm(vector):
    return math.sqrt(vector["x"]**2 + vector["y"]**2)

def vec2_set_new_length(vector, new_length):
    result = vec2_normalize(vector)
    result = vec2_scale(result, new_length)
    return result

def vec2_normalize(old_vector):
    vector = {"x" : old_vector.get("x",0), "y" : old_vector.get("y",0)}
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



def alice_can_see_bob(alice, bob_position, tile_map, debug_queue):
    # a does need a direction
    # should have a size of object too obviously
    line_to_bob = vec2_normalize(vec2_subtract(bob_position, alice))
    # you could model bob as a sphere
    # then just trace down the line of sight?

    bob_tiles = bob_position

    
    alice_pos = alice.get("position")

    abs_alice = get_abs_pos_from_index(alice_pos, tile_map, )
    alice_sight_angle = int(alice.get("sight_angle", 0)) #+ 180 #here?

    main_direction = vector_from_angle(alice_sight_angle) # I think we want to 180 this

    main_direction_scaled = vec2_scale(main_direction, 100)
    
    if debug_queue:
        debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : abs_alice.get("x"), "y" : abs_alice.get("y")},                                        
                    "pos_end" : {"x" : abs_alice.get("x") + main_direction_scaled.get("x"), "y" : abs_alice.get("y") + main_direction_scaled.get("y")},                                        
                    "line_width" : 1,                    
                    "color" : "PURPLE",
                    "z_sort" : -1,                    
                }
        debug_queue.append(debug_item)

    sight_range = 300
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



def tile_and_offset_to_absolute(tile_map, position):
    tile_width = tile_map.get("tile_width",0)
    tile_height = tile_map.get("tile_height",0)

    abs_x = tile_width * position.get("tile_x") + position.get("x")
    abs_y = tile_width * position.get("tile_y") + position.get("y")

    return {"x" : abs_x, "y": abs_y}

    
def ray_along_tiles_hits_target_tile(original_position, target_tile, end_range, step_size, normalized_ray_direction, tile_map, debug_queue = None):
    # original position is a tile/offset pair
    for i in range(0, end_range, int(step_size/2)):
        
        dist_to_push = i
        ray = vec2_scale(normalized_ray_direction, dist_to_push)        
        abs_pos = tile_and_offset_to_absolute(tile_map, original_position)
        pos_test = vec2_add(ray, abs_pos)
        

        test_tiles = get_tile_index_from_pos(pos_test, tile_map)

        

        found_tile = get_tile_type_from_indices(test_tiles.get("tile_x",0), test_tiles.get("tile_y",0), tile_map)


        if tile_type_is_collidable(found_tile.get("type","")):
            if g_test_see_through_walls:
                continue # to test see through walls
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

def ray_along_tiles_collides(original_position, end_range, step_size, normalized_ray_direction, tile_map, bullet_stamps, bullet_id, debug_queue = None):
    # original position is a tile/offset pair
    i = 0    
    while i < end_range:
        i += step_size
        dist_to_push = i
        ray = vec2_scale(normalized_ray_direction, dist_to_push)        
        abs_pos = tile_and_offset_to_absolute(tile_map, original_position)
        pos_test = vec2_add(ray, abs_pos)

        pos_pair = move_position_along_tiles(get_tile_index_and_offset_from_pos(pos_test, tile_map, None), tile_map.get("tile_width"), tile_map.get("tile_height"))

        pos_pair["id"] = bullet_id
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
            return True        
        else:
            
            bullet_key = f"{pos_pair.get("tile_x")},{pos_pair.get("tile_y")}"

            if bullet_key not in bullet_stamps:
                bullet_stamps[bullet_key] = {}
            if bullet_id not in bullet_stamps[bullet_key]:
                bullet_stamps[bullet_key][bullet_id] = []
            


            bullet_stamps[bullet_key][bullet_id].append(pos_pair)
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

                
    return False           


def tiles_equal(a, b):
    return a.get("tile_x",0) == b.get("tile_x",0) and a.get("tile_y",0) == b.get("tile_y",0)

def tiles_close(a, b, epsilon):
    if a.get("tile_x",0) == b.get("tile_x",0) and a.get("tile_y",0) == b.get("tile_y",0):
        if vec2_distance(a, {"x": 16, "y" : 16}):
            return True
    return False


def make_player_points(player_info, tile_width, tile_height):
    # ZZZ
    # not taking into account that the tiles will be different when adding width/height
    player_pos = player_info.get("position",{}) # top left
    # true if we think in terms of offset
    player_pos_top_right = {"x" : player_pos.get("x",0) + player_info.get("entity_width",g_default_entity_width),
                            "y" : player_pos.get("y",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_top_right = move_position_along_tiles(player_pos_top_right, tile_width, tile_height)
    

    
    player_pos_bottom_right = {"x" : player_pos.get("x",0) + player_info.get("entity_width",g_default_entity_width),
                            "y" : player_pos.get("y",0) + player_info.get("entity_height",g_default_entity_height),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_right = move_position_along_tiles(player_pos_bottom_right, tile_width, tile_height)
    
    player_pos_bottom_left = {"x" : player_pos.get("x",0),
                            "y" : player_pos.get("y",0) + player_info.get("entity_height",g_default_entity_height),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_left = move_position_along_tiles(player_pos_bottom_left, tile_width, tile_height)

    player_points = {
        "top_left" : player_pos,
        "top_right" : player_pos_top_right,
        "bottom_left" : player_pos_bottom_left,
        "bottom_right" : player_pos_bottom_right,
    }        
    
    return player_points

def check_collisions_on_tilemap(player_points, new_pos_velocity, tile_map, debug_queue):
    # zzz use this for any entity
    collisions = { "x" : False, "y" : False}
    for potential_pos in player_points.values():    
        new_pos_x_direction = new_pos_from_old(potential_pos)
        new_pos_y_direction = new_pos_from_old(potential_pos)

        new_pos_x_direction['x'] += new_pos_velocity['x']

        new_pos_y_direction['y'] += new_pos_velocity['y']

        # these need to be adjusted!!!!
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



def move_entity_towards_target_abs(entity, target_position, tile_map, debug_queue, dt):
    # start with a straight line
    # returns an updated position, doesn't     
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    vec2_between = vec2_normalize(vec2_subtract(target_position, make_player_pos_abs(entity.get("position",{}), tile_width, tile_height)))

    # we can also set our heading here
    entity["sight_angle"] = angle_from_vector(vec2_between) 
    # obviously we should move to 'proper' velocity but it's just a tad harder
    default_speed = 50
    entity_speed = entity.get("speed", default_speed)
    new_entity_velocity = vec2_scale(vec2_between, entity_speed * dt)

    # TODO (Cooper) we also need to do our collision logic here    
    

    new_entity_position = vec2_add(entity.get("position",{}), new_entity_velocity)    
    new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)
    new_entity_position["tile_y"] = entity.get("position",{}).get("tile_y",0)    

    new_entity_position["source"] = "ai"
    
    new_entity_position = move_position_along_tiles(new_entity_position, tile_width, tile_height)

    # we should actually adjust velocity based on collision, 
    # rather than just killing it outright
    # then renormalize afterwards I think....
        
    

    
    

    entity_points = make_player_points(entity, tile_width, tile_height)

    for potential_pos in entity_points.values():
        if debug_queue is not None:
                debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle,
                    "pos" : potential_pos,                    
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "radius" : 2,
                    "color" : "BLUE",
                    "z_sort" : 0,
                    "tile_width" : tile_width,
                    "tile_height" : tile_height
                }
                debug_queue.append(debug_item)

    entity_collisions = check_collisions_on_tilemap(entity_points, new_entity_velocity, tile_map, debug_queue)
    if entity_collisions.get("x", False):
        new_entity_velocity['x'] = 0
        new_entity_velocity = vec2_normalize(new_entity_velocity)
        new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)
        # new_entity_position["x"] = entity.get("position",{}).get("x",0)    
        # new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)    
    if entity_collisions.get("y", False):
        new_entity_velocity['y'] = 0
        new_entity_velocity = vec2_normalize(new_entity_velocity)
        new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)

    new_entity_position = vec2_add(entity.get("position",{}), new_entity_velocity)    
    new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)
    new_entity_position["tile_y"] = entity.get("position",{}).get("tile_y",0)            
    new_entity_position = move_position_along_tiles(new_entity_position, tile_width, tile_height)

    if entity_collisions.get("x", False):
        # new_entity_velocity['x'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)
        new_entity_position["x"] = entity.get("position",{}).get("x",0)    
        new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)    
    if entity_collisions.get("y", False):
        new_entity_position["y"] = entity.get("position",{}).get("y",0)    
        new_entity_position["tile_y"] = entity.get("position",{}).get("tile_y",0)    
        # new_entity_velocity['y'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)

    motion_angle = angle_from_vector(new_entity_velocity)
    print(f"motion angle is {motion_angle}")
    #risky!    
    animation_direction = direction_from_angle(motion_angle) 
    entity["animation_frame"] = animation_frame_number_from_direction(animation_direction)
    

    return new_entity_position


def make_player_pos_abs(player_pos, tile_width, tile_height):
    player_pos_abs = { "x" : player_pos.get("x",0) + player_pos.get("tile_x",0) * tile_width,
                          "y" : player_pos.get("y",0) + player_pos.get("tile_y",0) * tile_height}
    
    return player_pos_abs

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
        # path to player needed here
        
        target_tile_from_tile_map = tile_map.get("tiles")[player_pos.get("tile_y")*tile_map.get("map_width") + player_pos.get("tile_x")]
        start_tile_from_tile_map = tile_map.get("tiles")[entity_pos.get("tile_y")*tile_map.get("map_width") + entity_pos.get("tile_x")]
        path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
        entity["path_to_player"] = path_to_player
        entity["path_to_player_current_index"] = 0
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)
    else:
        bored_timer += dt
        # zzz this is also update sight direction for now
        if bored_timer >= bored_threshold:
            bored_timer = 0
            new_angle = random.randint(0,360)
            new_angle = new_angle % 360            
            entity["sight_angle"] = new_angle                        
            
            # pick a new random direction...?
    entity["bored_timer"] = bored_timer

    animation_direction = direction_from_angle(entity.get("sight_angle",0)) 
    entity["animation_frame"] = animation_frame_number_from_direction(animation_direction)
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
    angle = deg_to_rad(angle_deg + 180)
    x = math.cos(angle)
    y = math.sin(angle)
    return {"x" : x, "y" : y}



def angle_from_vector(v):    
    x = v.get("x",0)
    y = v.get("y",0)
    # if x == 0:
    #     if y == 1:
    #         return 0        
    #     return 180
    # if y == 0:
    #     if x == 1:
    #         return 90
    #     return 270
    #tan_ratio = y / x
    angle = rad_to_deg(math.atan2(y, x))    
    # angle = rad_to_deg(math.atan(tan_ratio))    
    return angle + 180

def fast_distance_within_tiles(tile_and_offset_a, tile_and_offset_b, dist):
    collides = False
    if tile_and_offset_a.get("tile_x") == tile_and_offset_b.get("tile_x") and tile_and_offset_a.get("tile_y") == tile_and_offset_b.get("tile_y"):
        if vec2_distance(tile_and_offset_a, tile_and_offset_b) < dist:
            collides = True        
    return collides

def death_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    get_or_set(entity, "death_timer", 0)
    entity["death_timer"] += dt

    next_state = current_state

    bullet_decel = 10
    bullet_magnitude = entity["bullet_hit_magnitude"] 
    bullet_normalized = entity["bullet_normalized"] 

    if bullet_magnitude > 0:
        bullet_magnitude -= bullet_decel


    stop_epsilon = 20
    if bullet_magnitude < stop_epsilon:
        bullet_magnitude = 0

    entity["bullet_hit_magnitude"] = bullet_magnitude
    
    motion_scalar = 0.1

    # we could actually just reduce the magnitude over time

    bullet_friction_force = vec2_scale(bullet_normalized, -1.0* bullet_magnitude * motion_scalar)

    

    

    velocity = vec2_scale(bullet_normalized, bullet_magnitude * 0.07)

    


    if entity["death_timer"] < 0.15:    
        new_entity_velocity = vec2_scale(velocity, dt)
    else:
        new_entity_velocity = {"x" : 0, "y" : 0} # but maybe can be set for shooting dead bodies


    

    entity_points = make_player_points(entity, tile_map.get("tile_width"), tile_map.get("tile_height"))

    entity_collisions = check_collisions_on_tilemap(entity_points, new_entity_velocity, tile_map, debug_queue)

    

    if entity_collisions.get("x", False):
        new_entity_velocity['x'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)
        # new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)
        # new_entity_position["x"] = entity.get("position",{}).get("x",0)    
        # new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)    
    if entity_collisions.get("y", False):
        new_entity_velocity['y'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)
        # new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)


    new_pos = vec2_add_just(entity["position"], new_entity_velocity)
    new_entity_pos = move_position_along_tiles(new_pos, tile_map.get("tile_width"), tile_map.get("tile_height"))
    # zzz
    # need to check for collisions still...!

    entity["position"] = new_entity_pos

    
        

    return next_state

def stagger_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    entity["stagger_timer"] += dt
    
    
    next_state = current_state

    bullet_magnitude = entity["bullet_hit_magnitude"] 
    bullet_normalized = entity["bullet_normalized"] 

    # I think this isn't working very well
    # what 
    motion_scalar = 0.8

    bullet_friction_force = vec2_scale(bullet_normalized, -1.0* bullet_magnitude * motion_scalar)

    velocity = get_or_set(entity, "bullet_impulse", {"x" : 0, "y" : 0})

    velocity = vec2_add(velocity, vec2_scale(bullet_friction_force, dt))

    entity["bullet_impulse"] = velocity

    new_entity_velocity = vec2_scale(velocity, dt)

    

    entity_points = make_player_points(entity, tile_map.get("tile_width"), tile_map.get("tile_height"))

    entity_collisions = check_collisions_on_tilemap(entity_points, new_entity_velocity, tile_map, debug_queue)

    

    if entity_collisions.get("x", False):
        new_entity_velocity['x'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)
        # new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)
        # new_entity_position["x"] = entity.get("position",{}).get("x",0)    
        # new_entity_position["tile_x"] = entity.get("position",{}).get("tile_x",0)    
    if entity_collisions.get("y", False):
        new_entity_velocity['y'] = 0
        # new_entity_velocity = vec2_normalize(new_entity_velocity)
        # new_entity_velocity = vec2_scale(new_entity_velocity, entity_speed * dt)
        
    new_pos = vec2_add_just(entity["position"], new_entity_velocity)
    new_entity_pos = move_position_along_tiles(new_pos, tile_map.get("tile_width"), tile_map.get("tile_height"))
    # zzz
    # need to check for collisions still...!

    entity["position"] = new_entity_pos

    if entity["stagger_timer"] >= 0.1:
        entity["velocity"] = {"x" : 0, "y" : 0}
        next_state = entity.get("previous_state_on_stagger","idle") # go to whatever you had

    
    return next_state
    


def attack_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    
    next_state = current_state
    can_see = True    
    if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        # on some interval we should also update the path to the player here...I think
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)
    else:
        can_see = False
        # this should be on a timer tho
        next_state = "idle" # also probably should be a 'searching' state
    entity_collide_distance = 5
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    # TODO: mismatch here between player position which is offset, turned into abs
    # and entity positions, which are currenty only abs
    entity_pos = entity.get("position",{})

    player_pos_abs = get_abs_pos_from_index(player_pos, tile_map)                              
    entity_pos_abs = get_abs_pos_from_index(entity_pos, tile_map)




                     
        
    
    # check if our distance to the player allows us to do our attack
    # if not we need to chase again to last known position
    attack_substate = get_or_set(entity, "attack_substate", "windup")
    attack_direction = get_or_set(entity, "attack_direction")
    attack_windup_duration = 1 
    attack_coold = 1 
    attack_timer = get_or_set(entity, "attack_timer", 0)
    attack_timer += dt
    attack_range = 10
    windup_direction_window = 0.3

    if attack_timer < windup_direction_window:
        # set direction
        attack_direction = vec2_normalize(vec2_subtract(player_pos_abs, entity_pos_abs))
        entity["attack_direction"] = attack_direction

    if attack_timer >= attack_windup_duration:
        attack_substate = "attacking"
        attack_point = vec2_add(entity_pos_abs, vec2_scale(attack_direction, attack_range))
        # just straightup check if player is in the line of sight?
        # zzzz pickup here 16/5/26 important
        # do the attack!
        # make a point





    # this should be on a per entity basis?
    # though I don't really mind implementing a function for each
    # enemy either
    





    

    # fundamentally two types of attack:
    # melee and projectile
    # -melee is like a punch: windup 
    # --(whilst maintaining a vector on the player for at least some of that, though it feels cheap if it's the whole thing because you can't dodge)
    # -projectile is shooting bullets/some exotic thing
    # --and could also even be spawning some kinda heat seeking mini-monster/missile thing,
    # ---basically a smart projectile

    # melee attacks need to be done in close range
    # since the 'attack' will basically instantly spawn a 
    # region slightly in front of the entity for a frame that will damage the player
    # whereas projectiles obviously, will travel 
    # you could also imagine a hit-scanning attack based on
    # line of sight, these can be less fun but
    # there could be an angle that is ok (like a psychic attack that you need to just
    # break the line of sight by getting behind something?)

    # one other type would be a sort of magic attack
    # which is kinda a hybrid where you maybe spawn in a 
    # region of fire for a short duration, not really 
    # a projectile, but unlike a melee it would last longer
    # than one frame
    waypoint_pos = entity["path_to_player"][min(entity["path_to_player_current_index"], len(entity["path_to_player"])-1)]
    # if our last position here doesn't match tiles on the last_seen_player_position we should recalculate?
    # OR if enough time has elapsed
    # really depends how slow this thing is

    if debug_queue is not None:
        for tile in entity["path_to_player"]:
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

    if tiles_close(entity_pos, waypoint_pos, 1) and entity["path_to_player_current_index"] < len(entity["path_to_player"]):
        entity["path_to_player_current_index"] += 1
    target_pos = get_abs_pos_from_index(waypoint_pos, tile_map, debug_queue)

    
    new_position = move_entity_towards_target_abs(entity, target_pos, tile_map, debug_queue, dt)
    # we could do a raycast along positions to check if we 'hit' the target on the way maybe

    entity["position"] = new_position
    
    # entity.get("position",{})["x"] = new_position.get("x", 0)
    # entity.get("position",{})["y"] = new_position.get("y", 0)        

    dest_threshold = 5
    give_up_threshold = 3

    if not fast_distance_within_tiles(new_position, player_pos, dest_threshold):
        next_state = "angry chase"

    
    if not can_see and entity["path_to_player_current_index"] == len(entity["path_to_player"]):
        get_or_set(entity, "give_up_time", 0)
        entity["give_up_time"] += dt
        if entity["give_up_time"] > give_up_threshold:
            next_state = "idle"

    
    if can_see and not tiles_equal(entity["path_to_player"][-1], entity["last_seen_player_pos"]):
        target_tile_from_tile_map = tile_map.get("tiles")[entity["last_seen_player_pos"]["tile_y"]*tile_map.get("map_width") + entity["last_seen_player_pos"]["tile_x"]]
        start_tile_from_tile_map = tile_map.get("tiles")[entity["position"].get("tile_y")*tile_map.get("map_width") + entity["position"].get("tile_x")]
        path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
        entity["path_to_player"] = path_to_player
        entity["path_to_player_current_index"] = 0        
    return next_state


def angry_chase_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    # We need a 'transition into 
    # portion of these state functions because there's some book keeping
    # that will need to be done only once
    # zzzz do that here
    
    next_state = current_state
    can_see = True    
    if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        # on some interval we should also update the path to the player here...I think
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)
    else:
        can_see = False
    entity_collide_distance = 5
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    # TODO: mismatch here between player position which is offset, turned into abs
    # and entity positions, which are currenty only abs
    entity_pos = entity.get("position",{})
    player_pos_abs = { "x" : player_pos.get("x",0) + player_pos.get("tile_x",0) * tile_width,
                          "y" : player_pos.get("y",0) + player_pos.get("tile_y",0) * tile_height}
        
    
    waypoint_pos = entity["path_to_player"][min(entity["path_to_player_current_index"], len(entity["path_to_player"])-1)]
    # if our last position here doesn't match tiles on the last_seen_player_position we should recalculate?
    # OR if enough time has elapsed
    # really depends how slow this thing is

    if debug_queue is not None:
        for tile in entity["path_to_player"]:
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

    if tiles_close(entity_pos, waypoint_pos, 1) and entity["path_to_player_current_index"] < len(entity["path_to_player"]):
        entity["path_to_player_current_index"] += 1
    target_pos = get_abs_pos_from_index(waypoint_pos, tile_map, debug_queue)

    
    new_position = move_entity_towards_target_abs(entity, target_pos, tile_map, debug_queue, dt)
    # we could do a raycast along positions to check if we 'hit' the target on the way maybe

    entity["position"] = new_position
    
    # entity.get("position",{})["x"] = new_position.get("x", 0)
    # entity.get("position",{})["y"] = new_position.get("y", 0)        

    dest_threshold = 5
    give_up_threshold = 3

    if fast_distance_within_tiles(new_position, player_pos, dest_threshold):
        next_state = "angry and attacking"

    
    if not can_see and entity["path_to_player_current_index"] == len(entity["path_to_player"]):
        get_or_set(entity, "give_up_time", 0)
        entity["give_up_time"] += dt
        if entity["give_up_time"] > give_up_threshold:
            next_state = "idle"

    
    if can_see and not tiles_equal(entity["path_to_player"][-1], entity["last_seen_player_pos"]):
        target_tile_from_tile_map = tile_map.get("tiles")[entity["last_seen_player_pos"]["tile_y"]*tile_map.get("map_width") + entity["last_seen_player_pos"]["tile_x"]]
        start_tile_from_tile_map = tile_map.get("tiles")[entity["position"].get("tile_y")*tile_map.get("map_width") + entity["position"].get("tile_x")]
        path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
        entity["path_to_player"] = path_to_player
        entity["path_to_player_current_index"] = 0        
    return next_state



def apply_force(entity, force):
    # force is acceleration really
    # f = ma, force has a direction and a magnitude
    # a = f/m 

    # velocity is a function of acceleration
    # no friction means no slow down

    # so if we go the 
    pass
    

def transition_entity_state(entity, current_state, player_pos, tile_map, debug_queue, dt):
    # TODO in addition to line of sight
    # need like a line of sound / within earshot function
    if entity.get("previous_state") != current_state:
        entity["entered_new_state"] = True
    
    next_state = current_state
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)    

    if current_state == "idle":
        next_state = idle_redhead_state(entity, current_state, player_pos, tile_map, debug_queue, dt)        
    elif current_state == "angry chase":        
        # this is essentially a 'go to last position' state
        # with maybe a different animation and / or speed
        next_state = angry_chase_state(entity, current_state, player_pos, tile_map, debug_queue, dt)
    elif current_state == "stagger":        
        next_state = stagger_state(entity, current_state, player_pos, tile_map, debug_queue, dt)
    elif current_state == "dead":        
        next_state = death_state(entity, current_state, player_pos, tile_map, debug_queue, dt)        
    elif current_state == "angry and attacking":        
        next_state = attack_state(entity, current_state, player_pos, tile_map, debug_queue, dt)        
        # if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        #     # keep try attacking if close enough
        #     pass
        # else:
        #     next_state = "idle"            
    entity["previous_state"] = current_state
    entity["entered_new_state"] = False

    return next_state

    



def update_entities(entities, tile_map, player_info, editor_mode, collision_mode, dt, sounds, debug_queue = None):
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    if editor_mode != "play":
        return
    
    player_pos = player_info.get("position",{}) # top left

    deletions = []

    bullet_tiles = {}
    # TODO make a 'reverse particle' system style weapon that
    # sucks up ammo from a corpse
    # like in Tenent
    # at the cost of reviving the corpse!
    

    
    if "pickups" not in entities:
        entities["pickups"] = {}
    for key, pickup in entities["pickups"].items():             
        # we might want to handle this in player interactions,
        # in which case we could have an 'e to pickup'
        # system
        
        # to use minkowsky sum approach
        # currently it feels awful
        pickup_rad = 10

        # bad test actually but still not working

        pickup_pos_abs = tile_and_offset_to_absolute(tile_map, pickup.get("position",{}))
        player_pos_abs = tile_and_offset_to_absolute(tile_map, player_pos)
        player_pos_abs["x"] += 12
        player_pos_abs["y"] += 12
        # player_pos_abs["x"] += player_info["entity_width"]/2
        # player_pos_abs["y"] += player_info["entity_height"]/2
        
        minkowski_rect = {
            "x" : pickup_pos_abs["x"] - player_info["entity_width"] - 12,
            "y" : pickup_pos_abs["y"] - player_info["entity_height"] - 12,
            "width" : 24 + player_info["entity_width"] + 12,
            "height": 24 + player_info["entity_height"] + 12
        }

        if debug_queue is not None:
                minkowski_debug_item = {
                    "type" : "rectangle",
                    "drawing_function" : draw_debug_rect,
                    "x" : minkowski_rect["x"],                    
                    "y" : minkowski_rect["y"],                    
                    "width" : minkowski_rect["width"],                    
                    "height" : minkowski_rect["height"],                    
                    "color" : "GREEN",
                    "z_sort" : 0,                    
                }
                debug_queue.append(minkowski_debug_item)

                debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle_abs,
                    "pos" : player_pos_abs,                                        
                    "radius" : 8,
                    "color" : "RED",
                    "z_sort" : 0,                    
                }
                debug_queue.append(debug_item)

        if point_in_rect(player_pos_abs, minkowski_rect):#vec2_distance(player_pos, pickup["position"]) < pickup_rad:
            deletions.append({"subdict": "pickups", "id" : pickup["id"]})            
            if pickup.get("type") == "pistol_ammo_pickup":
                print("got ammo")
                # zzz TODO play a nice ammo sound
                player_info["ammo"]["spare_pistol"] += pickup.get("value", 0)                    
                play_pool_sound("ammo_pickup_pool", sounds, -1, 1)
            elif pickup.get("type") == "health_pickup":                                        
                print("got health")
                player_info["health"] += pickup.get("value", 0)
                play_pool_sound("health_pickup_pool", sounds, -1, 1)
        

    if "particle_systems" not in entities:
        entities["particle_systems"] = {}

    for key, particle_system in entities["particle_systems"].items():        
        if key == "taken":
            continue
        place_decal = False
        if particle_system["timer"] >= particle_system["duration"]:
            # mark for deletion
            deletions.append({"subdict": "particle_systems", "id" : particle_system["id"]})            
            place_decal = True
        for particle in particle_system["particles"]:
            next_particle_pos_offset = vec2_add(particle["position"], vec2_scale(particle["velocity"], dt))            
            next_pos = copy_entity_pos(particle["position"])
            next_pos["x"] = next_particle_pos_offset["x"]
            next_pos["y"] = next_particle_pos_offset["y"]
            
            particle["position"] = move_position_along_tiles(next_pos, tile_map.get("tile_width"), tile_map.get("tile_height"))
            tile_x = particle["position"]["tile_x"]
            tile_y = particle["position"]["tile_y"]
            flat_index = get_flat_tile_index(tile_x, tile_y, tile_map)
            tile_at_index = get_tile_at_index(flat_index, tile_map)

            if tile_type_is_collidable(tile_map["tile_types"][tile_at_index["index"]]["type"]):
                particle["velocity"] = {"x" : 0, "y" : 0}
            # BUG we currently allow particles to travel through walls which is wrong obviously
            if place_decal:
                # and maybe just place decal randomly?
                
                offset_x = particle["position"]["x"]
                offset_y = particle["position"]["y"]
                ground_particle_size = particle["size"] + 1
                                                
                if "decals" not in tile_at_index:
                    tile_at_index["decals"] = []
                    tile_at_index["decal_counter"] = 0
                

                 
                # TODO (optimisation) : preallocate a certain amount of decals on each tile up front
                # zzz AND we already know the type of tile that it's landing on so we can properly like
                # have different decals for different tile types!!
                decal = {
                    "type" : "blood",
                    "size" : ground_particle_size,
                    "offset_x" : offset_x,
                    "offset_y" : offset_y,
                }

                # enforce max length on decals per tile?
                max_decals_for_now = 64
                if len(tile_at_index["decals"]) >= max_decals_for_now:
                    counter = tile_at_index.get("decal_counter", 0)
                    tile_at_index["decals"][counter % max_decals_for_now]
                    tile_at_index["decal_counter"] = counter + 1
                else:
                    tile_at_index["decals"].append(decal)   

                
                

                print("already have our tile indices, good on me")


        particle_system["timer"] += dt                    
            


    if "projectiles" not in entities:
        entities["projectiles"] = {}
    for entity in entities["projectiles"].values():        
        # TODO (Cooper) : move this stuff into an update function later
        if entity.get("type","") == "bullet":        
            # TODO zzz 
            # make 'dynamite bullets' 
            # that take a few seconds before exploding
            # kinda like the flare gun from Blood

            # we should actually apply our 'move along tile' thing to the 
            # bullet too...I think?
            # maybe later though let's leave it for now since
            # I want to keep some momentum to get
            # enemy hits in
            next_bullet_pos = vec2_add(entity["position"], vec2_scale(entity["velocity"], dt))            
            current_tile_and_offset = get_tile_index_and_offset_from_pos(entity["position"], tile_map, None)

            target_tile_next = get_tile_index_from_pos(next_bullet_pos, tile_map, None)
            end_range = (vec2_norm(vec2_subtract(next_bullet_pos, entity["position"])))
            direction = vec2_normalize(vec2_subtract(next_bullet_pos, entity["position"]))
            step_size = 2
            collides = ray_along_tiles_collides(current_tile_and_offset, end_range, step_size, direction, tile_map, bullet_tiles, entity["id"], debug_queue)
            if collides:
                play_sound(sounds["pistol_hit_wall"])
                deletions.append({"subdict": "projectiles", "id" : entity["id"]})            
            entity["position"] = next_bullet_pos
            entity["timer"] += dt
            max_bullet_time_for_now = 0.6
            if entity["timer"] >= max_bullet_time_for_now:
                deletions.append({"subdict": "projectiles", "id" : entity["id"]})            

            
            

            # interp the tiles between this and next 
    for entity in entities.get("brains",{}).values():                        
        if entity.get("type","") == "red head":
            # he needs to know about the environment (the tilemap)
            # he needs to know about potentially other entities...
            # he definitely needs to know about the player
            # the 'other entities' is interesting because it opens up
            # bioshock like interactions where one monster could do something with another
            # I kind of like that potential
            
            current_state = get_or_set(entity, "current_state", "idle")
            # there's a lot of logic happening in these states!
            next_state = transition_entity_state(entity, current_state, player_pos, tile_map, debug_queue, dt)
            entity["current_state"] = next_state
            pos_abs = tile_and_offset_to_absolute(tile_map, entity.get("position",{}))
            bullet_key = f"{entity.get("position",{}).get("tile_x")},{entity.get("position",{}).get("tile_y")}"
            if bullet_key in bullet_tiles:
                # possible collision!
                # but we're allowing one bullet in multiple times somehow
                print(f"we're saying there's {len(bullet_tiles[bullet_key])} in this square")
                for bullet_id in bullet_tiles[bullet_key].keys():
                    bullet_list = bullet_tiles[bullet_key][bullet_id]
                    for bullet in bullet_list:
                        bullet_dist = vec2_distance(bullet, entity.get("position")) 
                        # this is where our radius might be small
                        # and should technically check on the enemy as
                        # like, a body, not a point
                        if bullet_dist < 30:                        
                            # apply damage!
                            # subtract health

                            if entity["current_state"] != "dead":
                                entity["current_state"] = "stagger"
                                entity["stagger_timer"] = 0
                            else:
                                entity["death_timer"] = 0

                            
                            if current_state != "stagger":
                                entity["previous_state_on_stagger"] = current_state
                            
                            
                            # spawn particle
                            start_color = {"r" : 100, "g" : "20", "b" : 20}
                            end_color = {"r" : 100, "g" : "20", "b" : 20}
                            # want to know the velocity of the bullet that hit us
                            bullet_hitting_us = entities["projectiles"][bullet["id"]]

                            deletions.append({"subdict": "projectiles", "id" : bullet_hitting_us["id"]})            
                            bullet_magnitude = vec2_norm(bullet_hitting_us.get("velocity"))    



                            bullet_normalized = vec2_normalize(bullet_hitting_us.get("velocity")) 
                            entity["bullet_hit_magnitude"] = bullet_magnitude
                            entity["bullet_normalized"] = bullet_normalized
                            entity["bullet_impulse"] = vec2_scale(bullet_normalized, bullet_magnitude*0.2)

                            

                            base_bullet_damage = 20

                            entity["health"] -= base_bullet_damage

                            if entity["health"] > 0:
                                particle_system = make_blood_spatter(5, start_color,  end_color, 0.3, 0.1, 100, bullet_hitting_us, entity.get("position"))
                                play_pool_sound("stagger_hit_pool", sounds)                                
                            else:
                                # kill them here
                                if entity["current_state"] != "dead":
                                    play_pool_sound("death_hit_pool", sounds)                                
                                    particle_system = make_blood_spatter(20, start_color,  end_color, 0.7, 0.1, 100, bullet_hitting_us, entity.get("position"))
                                else:
                                    play_pool_sound("stagger_hit_pool", sounds)                                
                                    particle_system = make_blood_spatter(5, start_color,  end_color, 0.1, 0.01, 100, bullet_hitting_us, entity.get("position"))
                                entity["current_state"] = "dead"

                                entity["animation_frame"] = "death_frame_start" # zzz TODO make this directional
                                
                                
                            
                            particle_system_id = len(entities["particle_systems"]) 
                            particle_system["id"] = particle_system_id

                            if "taken" not in entities["particle_systems"]:
                                entities["particle_systems"]["taken"] = {}

                            if not entities["particle_systems"].get("taken", False):
                                entities["particle_systems"]["taken"][particle_system_id] = True
                            else:
                                found_free = False
                                while not found_free:
                                    particle_system_id += 1
                                    if not entities["particle_systems"]["taken"].get(particle_system_id, False):
                                        found_free = True             
                                        particle_system["id"] = particle_system_id                   
                                        entities["particle_systems"]["taken"][particle_system_id] = True
                                        break

                            entities["particle_systems"][particle_system_id] = particle_system
                            if debug_queue is not None:
                                debug_item = {
                                    "type" : "circle",
                                    "drawing_function" : draw_debug_circle,
                                    "pos" : entity.get("position"),                                        
                                    "font_size" : 16,
                                    "radius" : 60,
                                    "color" : "BLUE",
                                    "z_sort" : -2,                    
                                    "tile_width" : tile_width,
                                    "tile_height" : tile_height
                                }
                                debug_queue.append(debug_item)
                            break


            
            if debug_queue is not None:
                debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : pos_abs.get("x",0), "y" : pos_abs.get("y",0)},                                        
                    "font_size" : 16,
                    "text" : f"{entity["current_state"]}",
                    "color" : "WHITE",
                    "z_sort" : 0,                    
                }
                debug_queue.append(debug_item)
    for deletion in deletions:
        sublist = deletion.get("subdict")
        id = deletion.get("id")
        if id in entities[sublist]:
            del entities[sublist][id]
            if sublist == "particle_systems":
                entities["particle_systems"]["taken"][id] = False

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


def point_in_rect(point_position, rectangle):
    rect_left = rectangle["x"]
    rect_right = rectangle["x"] + rectangle["width"]
    rect_top = rectangle["y"]
    rect_bottom = rectangle["y"] + rectangle["height"]
    return point_position["x"] >= rect_left and point_position["x"] <= rect_right and point_position["y"] >= rect_top and point_position["y"] <= rect_bottom 
    

def update_player_position(tile_map, player_info, editor_mode, collision_mode, dt, sounds, debug_queue = None):
    # i think the offset should be relative to _actual_ tile width
    # and so our world position is always a sum of the tile start pos + offset

    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]

    if editor_mode != "play":
        return player_info.get("position",{})
    
    player_pos = player_info.get("position",{}) # top left
    # true if we think in terms of offset
    player_pos_top_right = {"x" : player_pos.get("x",0) + player_info.get("entity_width",0),
                            "y" : player_pos.get("y",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_bottom_right = {"x" : player_pos.get("x",0) + player_info.get("entity_width",0),
                            "y" : player_pos.get("y",0) + player_info.get("entity_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_left = {"x" : player_pos.get("x",0),
                            "y" : player_pos.get("y",0) + player_info.get("entity_height",0),
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }

    # player_points = {
    #     "top_left" : player_pos,
    #     "top_right" : player_pos_top_right,
    #     "bottom_left" : player_pos_bottom_left,
    #     "bottom_right" : player_pos_bottom_right,
    # }

    player_points = make_player_points(player_info, tile_width, tile_height)

    collisions = { "x" : False, "y" : False}

    

    #need to test 4 corners I believe
        

    player_velocity = get_or_set(player_info, "player_velocity", {"x" : 0, "y" : 0})

    player_footstep_timer = get_or_set(player_info, "player_footstep_timer", 0)

    player_footstep_timer_base_gap = 0.3

    player_accel = 3000

    player_speed_max = 500

    
    

    
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

    # if run_multiplier:
    #     player_speed *= run_multiplier

    direction_vector = vec2_normalize(direction_vector)    

    if (player_velocity["x"]*direction_vector["x"] < 0) or (player_velocity["y"]*direction_vector["y"] < 0):
        player_accel *= 2

    player_velocity = vec2_add(player_velocity, vec2_scale(direction_vector, dt * player_accel))
    # correct in the case that we're diagonal but not full speed?
    
    
    if vec2_norm(player_velocity) >= player_speed_max:
        # this will need to be adjusted for sprinting -> walking transition
        player_velocity = vec2_set_new_length(player_velocity, player_speed_max)


    min_speed = 10
    current_speed = vec2_norm(player_velocity)

    if current_speed > 0: # make this distance based rather than speed based, better accumulator
        player_footstep_timer += dt * 0.003 * current_speed #although I guess this *is* a distance in disguise kinda
    # else:
    #     player_footstep_timer = 0

    if player_footstep_timer >= player_footstep_timer_base_gap:
        player_footstep_timer = 0
        play_pool_sound("player_footstep_pool", sounds, -3, 3, 40)
        # print("playing pool sound")

    player_info["player_footstep_timer"] = player_footstep_timer

    if vec2_norm(direction_vector) < 0.1 and vec2_norm(player_velocity) > min_speed:
        player_decel = 10
        # no buttons are pressed in this case, so subtract speed
        friction_vector = vec2_scale(player_velocity, -1)        
        player_velocity = vec2_add(player_velocity, vec2_scale(friction_vector, dt * player_decel))
    elif vec2_norm(direction_vector) < 0.1 and current_speed > 0 and current_speed <= min_speed:
        # print("killing velocity")
        player_velocity = {"x" : 0, "y" : 0}
    
    player_info["player_velocity"] = player_velocity
    new_pos["x"] += player_velocity["x"] * dt 
    new_pos["y"] += player_velocity["y"] * dt 
        


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
            
            new_pos_x_direction["x"] += player_velocity["x"]*dt
            
            new_pos_y_direction["y"] += player_velocity["y"]*dt

            
            
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
    
    
    
    new_pos = move_position_along_tiles(new_pos, tile_width, tile_height)

    # need the screen space of the player to get the mouse screen space to make a direction vector
    

    # if new_pos["x"] > tile_width:
    #     additional_x_tiles = int(new_pos.get("x",0) / tile_width)
    #     new_pos["tile_x"] += additional_x_tiles
    #     new_pos["x"] = new_pos["x"] % tile_width

    # if new_pos["x"] < 0:
    #     additional_x_tiles = int((tile_width + abs(new_pos.get("x",0))) / tile_width)
    #     new_pos["tile_x"] -= additional_x_tiles

    #     new_pos["x"] = tile_width + new_pos["x"]

    # if new_pos["y"] < 0:
    #     additional_y_tiles = int((tile_height + abs(new_pos.get("y",0))) / tile_height)
    #     # I think this will do us?
        
    #     new_pos["tile_y"] -= additional_y_tiles    
    #     new_pos["y"] = new_pos["y"] + tile_height

    # if new_pos["y"] > tile_height:
    #     additional_y_tiles = int(new_pos.get("y",0) / tile_height)
    #     # I think this will do us?
        
    #     new_pos["tile_y"] += additional_y_tiles    

    #     new_pos["y"] = new_pos["y"] % tile_height

    

    
    
    

    
    return new_pos

def get_player_center_screen_space(tile_width, tile_height, player_pos, game_camera):
    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - game_camera.x + 12, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y + 12)    

def get_player_center_world_space(tile_width, tile_height, player_pos, game_camera):
    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] + 12, tile_height * player_pos["tile_y"] + player_pos["y"] + 12)    

def apply_force():
    # A = F / m
    pass

def update_player_interaction(tile_map, player_info, game_camera, entities, sounds, audio_engine, dt, debug_state):
    player_pos = player_info["position"]
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    # really need to have a 'player center' position
    player_render_pos = {"x" : tile_width * player_pos["tile_x"] + player_pos["x"] - 20 - game_camera.x, "y" : tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y - 16}

    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - game_camera.x + 12, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y + 12)    

    player_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] + 12, tile_height * player_pos["tile_y"] + player_pos["y"] + 12)    

    mouse_pos = pr.get_mouse_position()
    
    mouse_pos_mine = {"x" : mouse_pos.x, "y" : mouse_pos.y}

    arm_length = 20

    aim_heading_normal = vec2_normalize(vec2_subtract(mouse_pos_mine, player_render_pos))
    aim_heading = vec2_scale(aim_heading_normal, arm_length)

    spawn_pos = vec2_add_any(player_pos_center, aim_heading)

    # resulting_sounds = []

    # set direciton based on aim? or running?
    player_angle_current = angle_from_vector(aim_heading_normal)
    #player_angle_current += 180
    animation_direction = direction_from_angle(player_angle_current)

    player_info["animation_frame"] = animation_frame_number_from_direction(animation_direction)

    pr.draw_text(f"player angle is {int(player_angle_current)}", 80, 30, 10, pr.RED)

    pr.draw_text(f"player health is {int(player_info["health"])}", 80, 40, 10, pr.RED)

    pr.draw_text(f"player ammo is {int(player_info["ammo"]["pistol"])} / {int(player_info["ammo"]["spare_pistol"])}", 80, 50, 10, pr.RED)

    current_gun = "pistol" # TODO make more types of guns and make them selectable

    if player_info.get("reload_state","") == "reloading":
        reload_timer = player_info.get("reload_timer",0)
        reload_timer += dt
        player_info["reload_timer"] = reload_timer
        if reload_timer >= get_reload_time(current_gun):
            player_info["reload_timer"] = 0
            player_info["reload_state"] = "reloaded"
            # reload!
            current_bullets = player_info["ammo"][f"{current_gun}"]
            spare_bullets = player_info["ammo"][f"spare_{current_gun}"]
            clip_size = get_clip_size(current_gun)

            bullets_we_have_room_for = clip_size - current_bullets

            
            clip_to_load = min(bullets_we_have_room_for, spare_bullets)            

            player_info["ammo"][current_gun] += clip_to_load # this would allow it to go over
            #player_info["ammo"][f"{current_gun}"] = max(spare_bullets, 0)
            spare_bullets -= clip_to_load                        
            player_info["ammo"][f"spare_{current_gun}"] = max(spare_bullets, 0)


        # should also be able to interrupt this

    if pr.is_key_pressed(pr.KeyboardKey.KEY_R):
        if player_info.get("reload_state","") != "reloading":                        
            play_sound(sounds["pistol_reload"])
            player_info["reload_state"] = "reloading"


    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT):
        
        current_ammo = player_info["ammo"][current_gun]
        if player_info.get("reload_state","") == "reloading":
            stop_sound(sounds["pistol_reload"])            
            player_info["reload_timer"] = 0
            player_info["reload_state"] = "interrupted" # could do something with this


        if current_ammo <= 0:
            print("no bullets")            
            play_pool_sound("pistol_empty_pool", sounds)
            # play reload sound
        else:
            bullet_pos = {"x" : spawn_pos["x"], "y" :spawn_pos["y"]} # world space I think
            current_pos = {"x" : spawn_pos["x"], "y" : spawn_pos["y"]}
            bullet_speed = 10000 # this will be kept constant effectively, since the bullet won't really slow down
            if debug_state == "slow_bullets":
                bullet_speed = 50
            # in the horizontal before it hits the ground
            if "projectiles" not in entities:
                entities["projectiles"] = {}
            bullet_id = len(entities["projectiles"])
            bullet = make_projectile("player", bullet_pos, vec2_scale(aim_heading_normal, bullet_speed), bullet_id, "bullet")
            
            # TODO! move this stuff to an audio manager, just need the sound info

            play_pool_sound("pistol_pool", sounds)        

            entities["projectiles"][bullet_id] = bullet

            current_ammo -= 1

            player_info["ammo"][current_gun] = current_ammo

            # spawn a bullet with our name on it
            # try playing a gunshot sound directly here
        
        
    player_info["aim_direction"] = aim_heading


def copy_position_dict(original):
    return {"x" : original.get("x",0), "y" : original.get("y",0), 
            "tile_x" : original.get("tile_x",0), "tile_y" : original.get("tile_y",0)}

def make_blood_spatter(particle_amount, start_color, end_color, total_duration, spawn_time, max_amount, bullet_hit_us, spawn_position):    
    # the better thing to do here would probably be
    # to pool it?
    bullet_magnitude = vec2_norm(bullet_hit_us.get("velocity"))
    
    bullet_normalized = vec2_normalize(bullet_hit_us.get("velocity"))

    blood_particles = [] # maybe slow
    print("spawning particle system")
    

    for i in range(particle_amount):
        current_angle = angle_from_vector(bullet_normalized)
        new_angle = current_angle + float(random.randint(-10, 10))
        speed_offset = float(random.randint(-2, 2))
        new_magnitude = bullet_magnitude / (speed_offset + 10)#(10 + speed_offset)
        blood_velocity = vec2_scale(vector_from_angle(new_angle), new_magnitude)
        spawn_pos = copy_entity_pos(spawn_position)
        base_size = 2
        size_offset = random.randint(-1,1)
        random_offset_x = random.randint(-7,7)
        random_offset_y = random.randint(-7,7)
        spawn_pos["x"] += random_offset_x
        spawn_pos["y"] += random_offset_y
        particle = {
            "velocity" : blood_velocity,
            "size" : base_size + size_offset,
            "timer" : 0.0,
            "position" : spawn_pos,
            
        }
        # TODO color them 'uniquely'
        blood_particles.append(particle)
        
    particle_system = {}
    particle_system["particles"] = blood_particles
    particle_system["timer"] = 0.0
    particle_system["duration"] = total_duration
    particle_system["start_color"] = start_color
    particle_system["end_color"] = end_color
    
    return particle_system

def make_particle_system(particle_amount, start_color, end_color, total_duration, spawn_time, max_amount, direction):
    particle_system = {}    
    return particle_system


def play_sound(sound):
    sound.stop()
    sound.seek(0)
    sound.start()

def stop_sound(sound):
    sound.stop()
    sound.seek(0)


    

def move_position_along_tiles(new_pos, tile_width, tile_height):        

    # draw_debug = (new_pos.get("source","") == "ai")
    draw_debug = False
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

    if draw_debug:
        pr.draw_text(f"tile x: {new_pos.get("tile_x","")}", 80, 30, 10, pr.WHITE)
        print(f"tile x: {new_pos.get("tile_x","")}")
        print(f"tile y: {new_pos.get("tile_y","")}")

    return new_pos

def in_the_range(x, start, end):
    return x >= start and x <= end

def direction_from_angle(angle):
    rough_direction = "down"
    if in_the_range(angle, 150,  185):
        rough_direction = "right"    
    elif in_the_range(angle, 45,  149):
        rough_direction = "up"
    elif in_the_range(angle, 0, 44) or in_the_range(angle, 320, 360):
        rough_direction = "left"
    return rough_direction

def animation_frame_number_from_direction(direction):
    frame_number_name = f"{direction}_frame_start"
    return frame_number_name # lol this isn't a number


def draw_debug_circle_abs(debug_item, camera):
    x = debug_item.get("pos", {}).get("x") 
    y = debug_item.get("pos", {}).get("y") 
    cx = int(x - camera.position.x)
    cy = int(y - camera.position.y)
    rad = debug_item.get("radius", 0)
    color = color_map(debug_item.get("color", ""))
    pr.draw_circle(cx, cy, rad, color)


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


def draw_debug_rect(debug_item, camera):
    width = debug_item.get("width", 0)
    height = debug_item.get("height", 0)
    color = color_map(debug_item.get("color", "PINK"))
    x = debug_item.get("x", 0) 
    y = debug_item.get("y", 0) 
    camera_x = camera.position.x
    camera_y = camera.position.y
    draw_x = int(x - camera_x)
    draw_y = int(y - camera_y)

    pr.draw_rectangle(draw_x, draw_y, width, height, color)

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
    
    

def update_and_render(main_arena, game_assets, cma_engine):
    # maybe we think of assets as things that can't be serialized, or are expensive to do so...
    # arena initialisation
    
    dt = pr.get_frame_time()
    # if dt > 0:
    #     print(f"fps is {1/dt}")
    # issue here when debugging, people will accumulate insane time
    dt = min(dt, 0.016)
    mouse_pos = pr.get_mouse_position()
    time_elapsed = main_arena.get("time_elapsed", 0.0) 
    save_interval = 200
    save_elapsed = main_arena.get("save_elapsed", 0.0) 
    player_info = main_arena.get("player_info") # really more info
    debug_state = main_arena.get("debug_state", "clear") 
    pause_state = main_arena.get("pause_state", "unpaused") 

    # could handle a pause event here...?
    if pr.is_key_pressed(pr.KeyboardKey.KEY_PAUSE):
        pause_state = transition_pause_state(pause_state)    
    

    


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

    sounds = game_assets.get("sounds")
    if not sounds:
        sounds = load_sounds(cma_engine)
        game_assets["sounds"] = sounds
    textures = game_assets.get("textures")
    if not textures:
        textures = load_textures()
        sprite_sheets = load_sprite_sheets()
        game_assets["textures"] = textures
        game_assets["sprite_sheets"] = sprite_sheets

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

    if pause_state != "paused":
        player_info["position"] = update_player_position(player_info=player_info, editor_mode=editor_mode, collision_mode=collision_mode ,dt=dt, sounds=sounds, tile_map=tile_map, debug_queue=debug_queue)
    
    if pause_state != "paused":
        # I think we want to have the current 'hot spots' in terms of bullets cached
        # then when we check an entity, we can just check
        # IF that region has an active bullet we need to do a check on
        # that would be super efficient I think
        # because you don't need to loop over all bullets and all entities
        # instead, each bullet gets updated (this is obviously necessary)
        # and then each enemy gets updated, and only needs to check in the table if 
        # there is a bullet in their current (not next! I think) 
        # square, so we avoid the quadratic thing
        # and then if there is a bullet(s) in the square,
        # we check against only those (there may be more than one I suppose)
        update_entities(entities=entities,player_info=player_info, editor_mode=editor_mode, collision_mode=collision_mode ,dt=dt, tile_map=tile_map, sounds =sounds, debug_queue=debug_queue)
    camera_3d = update_camera(camera_3d, mode=editor_mode, player_pos=player_info.get("position",{}), dt=dt)

    if editor_mode == "play":
        update_player_interaction(tile_map, player_info, camera_3d.position, entities, sounds, cma_engine, dt, debug_state)
    # pathfind_test_on_player(player_info=player_info, tile_map=tile_map, game_camera=camera_3d.position, debug_queue=debug_queue)
    
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
    

    

    update_render_tile_map(camera_3d.position, entities, tile_map, pr.get_mouse_position(), current_tile_selection, current_entity_selection, game_assets, do_load_level, player_info, editor_mode, debug_queue=debug_queue)

    pr.draw_text(editor_mode, 1700, 30, 20, pr.WHITE)

    if debug_state != "clear":
        pr.draw_text(debug_state, 1700, 50, 20, pr.WHITE)

    if pause_state == "paused":
        pr.draw_text("PAUSED", 1700, 50, 20, pr.WHITE)

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
        game_assets["sounds"] = None

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
    changes["pause_state"] = pause_state
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
    
