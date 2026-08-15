import math
import pickle
import os
import time

import random

import queue

import pyray as pr
from pyrsistent import m, pmap, v

import g_graphics
import g_audio
import g_effects
import g_editor
import g_render_order
import g_ui





from dataclasses import dataclass, field

INV_SQRT_2 = 1.0 / math.sqrt(2.0)

g_tile_shape_normals = {
    1: {
        "x": INV_SQRT_2,
        "y": INV_SQRT_2,
    },
    2: {
        "x": -INV_SQRT_2,
        "y": INV_SQRT_2,
    },
    3: {
        "x": -INV_SQRT_2,
        "y": -INV_SQRT_2,
    },
    4: {
        "x": INV_SQRT_2,
        "y": -INV_SQRT_2,
    },
}

g_sound_list_per_frame = []


g_last_interacted_ui_id = -1
g_interacted_ui_last_frame = False
g_interacted_ui_this_frame = False

g_default_entity_width = 16
g_default_entity_height = 16

g_test_see_through_walls = False

g_infinite_ammo = True

g_mute = False

g_editor_sounds = True

g_mouse_is_ui_captured = False

DEFAULT_AIM_HEADING_DEGREES = 0.0
DEFAULT_MOUSE_AIM_SENSITIVITY = 1.0
DEFAULT_AIM_CURSOR_DISTANCE = 72.0
MAX_AIM_CURSOR_DISTANCE = 120.0
AIM_INPUT_VERSION = 2
PLAYER_WEAPON_TRANSITION_INSTANCE_KEY = "player:pistol_transition"
PLAYER_WEAPON_TRANSITION_DEFAULTS = {
    # Match the authored clips initially; animation timing remains independently
    # tweakable without changing the normalized state model.
    "unholster_duration": 0.125,
    "holster_duration": 0.15,
    "minimum_reverse_sound_seconds": 0.07,
}
PLAYER_AIM_ACCURACY_DEFAULTS = {
    "minimum_fire_progress": 0.08,
    "turn_speed_deadzone": 35.0,
    "turn_speed_full_bloom": 360.0,
    "turn_acceleration_deadzone": 10000.0,
    "turn_acceleration_full_bloom": 4000.0,
    "turn_speed_filter_seconds": 0.04,
    "bloom_expand_seconds": 0.075,
    "bloom_motion_recovery": 0.15,
    "bloom_shot_recovery": 0.60,
    "recoil_bloom_per_shot": 0.35,
    "minimum_reticle_radius": 3.0,
    "motion_maximum_reticle_radius": 8.0,
    "transition_maximum_reticle_radius": 12.0,
    "motion_maximum_spread_degrees": 6.0,
    "transition_maximum_spread_degrees": 10.0,
}
DEFAULT_REDHEAD_COLLISION_CENTER_OFFSET = {"x": -12.0, "y": -8.0}
DEFAULT_REDHEAD_COLLISION_RADIUS_REDUCTION = 4.0
DEFAULT_REDHEAD_ATTACK_ENGAGE_DISTANCE = 28.0
# Initial knockback speed, decay window, and cap for combined rapid hits.
# With linear decay, 200 px/s over 0.10 s travels roughly 10 pixels.
DEFAULT_BULLET_IMPACT_SPEED = 200.0
DEFAULT_BULLET_IMPACT_DURATION = 0.10
DEFAULT_BULLET_COMBINED_IMPACT_CAP = 320.0
DEFAULT_REDHEAD_STAGGER_DURATION = 0.10
DEFAULT_REDHEAD_ACTOR_BLOCK_DELAY = 0.35
DEFAULT_REDHEAD_PASSTHROUGH_UNUSED_TIMEOUT = 1.0

# Redhead positions are the bottom-right anchor of their 24x24 render frame.
# Keep the gameplay hurtbox on the visible body rather than on that anchor tile.
DEFAULT_REDHEAD_BULLET_HURTBOX = {
    "offset": {"x": -20.0, "y": -22.0},
    "size": {"x": 16.0, "y": 22.0},
}

REDHEAD_EVADE_DEFAULTS = {
    "chance": 0.35,
    "aim_margin": 7.0,
    "aim_max_distance": 260.0,
    "reaction_time": 0.15,
    "failed_retry_delay": 0.50,
    "cooldown": 3.0,
    "duration_min": 1.0,
    "duration_max": 2.0,
    "search_radius_tiles": 4,
    "minimum_lateral_tiles": 1.25,
    # Half a tile allows grid paths to approximate a constant-radius arc while
    # still preventing a meaningful backwards/fleeing step.
    "maximum_retreat_tiles": 0.50,
    "heading_reversal_limit": -0.15,
    "top_candidate_count": 3,
    "lateral_score_weight": 2.0,
    "aim_clearance_score_weight": 2.5,
    "progress_score_weight": 1.0,
    "path_cost_score_weight": 0.35,
    "preferred_side_score": 0.40,
    "cover_score_weight": 0.0,
    "waypoint_arrival_radius": 4.0,
    "stuck_replan_delay": 0.35,
}

REDHEAD_FLEE_DEFAULTS = {
    "health_fraction": 0.34,
    "ally_search_radius_tiles": 12,
    "local_plan_radius_tiles": 8,
    "ally_arrival_distance": 28.0,
    "speed_multiplier": 1.6,
    "replan_interval": 0.75,
    "waypoint_arrival_radius": 4.0,
}

REDHEAD_MOVEMENT_DEFAULTS = {
    "max_speed": 70.0,
    "acceleration": 900.0,
    "deceleration": 1500.0,
    "reverse_acceleration": 2000.0,
    "arrival_radius": 3.0,
    "evade_speed_multiplier": 1.3,
}

REDHEAD_PERCEPTION_DEFAULTS = {
    # Visibility and direct-chase corridor rays are deliberately decoupled
    # from render/update frequency.
    "line_of_sight_checks_per_second": 4.0,
    "flashlight_checks_per_second": 20.0,
    "flashlight_notice_duration": 0.10,
    "flashlight_intensity_threshold": 0.15,
    "light_startle_duration": 0.10,
    # A committed chase can startle idle allies within this unobstructed
    # radius. This is deliberately radial; walls, rather than facing, gate it.
    "ally_alert_radius_tiles": 5.0,
}

REDHEAD_HEARING_DEFAULTS = {
    # AI audibility is authored independently from playback gain/muting.
    "gunshot_radius_tiles": 18.0,
    "walk_footstep_radius_tiles": 7.0,
    "run_footstep_radius_tiles": 10.0,
    "walk_footstep_contribution": 0.40,
    "run_footstep_contribution": 0.65,
    "startle_threshold": 1.0,
    "chase_threshold": 2.5,
    "silence_reset_seconds": 10.0,
}

g_tile_collision_shapes = [
    "full",
    "triangle_top_left",
    "triangle_top_right",
    "triangle_bottom_right",
    "triangle_bottom_left",
]

@dataclass(order=True)
class PriorityQueueEntry:
    priority: float
    tile: dict = field(compare=False)

def mouse_pos_world_from_lowres():
    internal_width = 480 # TODO move these into params
    internal_height = 270

    mouse_pos = pr.get_mouse_position()

    norm_pos_x = mouse_pos.x / pr.get_screen_width()
    norm_pos_y = mouse_pos.y / pr.get_screen_height()

    internal_x = internal_width * norm_pos_x
    internal_y = internal_height * norm_pos_y
    return {"x": internal_x, "y" : internal_y}




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

def point_inside_tile_shape(shape_index, local_x, local_y, tile_width, tile_height):
    if shape_index == 0:
        return True

    u = local_x / tile_width
    v = local_y / tile_height

    epsilon = 0.000001

    if shape_index == 1:
        # triangle top left
        return u + v < 1.0 - epsilon

    if shape_index == 2:
        # triangle top right
        return v < u - epsilon

    if shape_index == 3:
        # triangle bottom right
        return u + v > 1.0 + epsilon

    if shape_index == 4:
        # triangle bottom left
        return v > u + epsilon

    # fail safe
    return True


def tile_is_collidable(tile, tile_map):
    """Resolve physical/pathfinding collision for one placed tile instance."""
    if bool(tile.get("force_collidable", False)):
        return True
    tile_types = tile_map.get("tile_types", [])
    tile_index = int(tile.get("index", 0))
    if tile_index < 0 or tile_index >= len(tile_types):
        return False
    return tile_type_is_collidable(tile_types[tile_index].get("type", ""))


def should_tint_forced_collision_tile(tile, editor_mode):
    return editor_mode != "play" and bool(tile.get("force_collidable", False))

def get_tile_shape_collision(position, tile_map):
    tile_x = position.get("tile_x", 0)
    tile_y = position.get("tile_y", 0)

    if tile_not_in_bounds(tile_x, tile_y, tile_map):
        return {
            "collides": True,
            "shape_index": 0,
            "normal": None,
        }

    tile_index = (tile_y * tile_map["map_width"] + tile_x)

    tile = tile_map["tiles"][tile_index]
    if not tile_is_collidable(tile, tile_map):
        return {
            "collides": False,
            "shape_index": None,
            "normal": None,
        }

    shape_index = tile.get("shape_index", 0)

    collides = point_inside_tile_shape(shape_index, position.get("x", 0), position.get("y", 0), tile_map["tile_width"], tile_map["tile_height"])

    normal = g_tile_shape_normals.get(shape_index)

    return {
        "collides": collides,
        "shape_index": shape_index,
        "normal": normal,
        "tile": tile,
    }

def position_collides_within_tile_shape(position, tile_map):
    collision = get_tile_shape_collision(position, tile_map)

    return collision["collides"]


def make_tile_map(width, height, tile_width, tile_height):
    # to be able to serialize this we should change the types here
    result = {}
    result["map_width"] = width
    result["map_height"] = height
    result["tile_width"] = tile_width
    result["tile_height"] = tile_height    
    result["geometry_revision"] = 0
    result["rain_exposure_revision"] = 0
    result["acoustic_revision"] = 0
    result["audio_surface_schema_revision"] = g_audio.AUDIO_SURFACE_SCHEMA_REVISION
    result["acoustic_zones"] = g_audio.make_default_acoustic_zones()
    result["tile_types"] = [{"type" : "blank_tile", "color" : "BLACK", "audio_surface": "dirt"},
                            {"type" : "carpet", "color" : "BLUE", "audio_surface": "carpet"},
                            {"type" : "door", "color" : "RED", "audio_surface": "generic"},
                            {"type" : "wall", "color" : "PURPLE", "audio_surface": "generic"},
                            {"type" : "wood", "color" : "BROWN", "audio_surface": "wood"},
                            {"type" : "grass", "color" : "GREEN", "audio_surface": "grass"},
                            {"type" : "stone", "color" : "GREY", "audio_surface": "stone"}]
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

def mark_tile_map_geometry_dirty(tile_map):
    tile_map["geometry_revision"] = int(tile_map.get("geometry_revision", 0)) + 1
    return tile_map["geometry_revision"]


def flood_fill_rain_exposure(tile_map, start_x, start_y, target_exposure):
    return g_effects.flood_fill_rain_exposure(tile_map, start_x, start_y, target_exposure)

def apply_effect_events_to_world(events, tile_map):
    """Consume persistent outcomes from transient effects (currently decals)."""
    if not tile_map:
        return
    tile_width = max(1.0, float(tile_map.get("tile_width", 16.0)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16.0)))
    map_width = int(tile_map.get("map_width", 0))
    map_height = int(tile_map.get("map_height", 0))
    tiles = tile_map.get("tiles", [])
    for event in events:
        if event.get("type") != "blood_decal":
            continue
        world_x = float(event.get("x", 0.0))
        world_y = float(event.get("y", 0.0))
        tile_x = math.floor(world_x / tile_width)
        tile_y = math.floor(world_y / tile_height)
        if tile_x < 0 or tile_y < 0 or tile_x >= map_width or tile_y >= map_height:
            continue
        flat_index = tile_y * map_width + tile_x
        if flat_index < 0 or flat_index >= len(tiles):
            continue
        tile = tiles[flat_index]
        decals = tile.setdefault("decals", [])
        decal = {
            "type": "blood",
            "size": float(event.get("size", 3.0)),
            "offset_x": world_x - tile_x * tile_width,
            "offset_y": world_y - tile_y * tile_height,
        }
        maximum = 64
        if len(decals) < maximum:
            decals.append(decal)
        else:
            counter = int(tile.get("decal_counter", 0))
            decals[counter % maximum] = decal
            tile["decal_counter"] = counter + 1



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

def draw_tile_texture_from_type(game_assets, tile_type, x, y, shape_index=0, tint=None):
    textures = game_assets.get("textures",{})
    texture = None    
    if tile_type.get("type") == "wood":                
        texture = textures["wood_texture"]        
    elif tile_type.get("type") == "wall":                
        texture = textures["wall_texture"]        
    elif tile_type.get("type") == "stone":                
        texture = textures["grey_tile_texture"]        
    elif tile_type.get("type") == "carpet":  #change to other tile               
        texture = textures["orange_tile_texture"]
    if texture is not None:
        draw_masked_tile_texture(texture, pr.Vector2(x, y), shape_index, game_assets, tint=tint)
        
    
def do_flood_fill(current_tile_selection, x, y, tile_map, map_width, seen, mark_revision=True):
    initial_seen_count = len(seen)
    map_height = int(tile_map.get("map_height", 0))
    tiles = tile_map.get("tiles", [])
    pending = [(int(x), int(y))]
    while pending:
        current_x, current_y = pending.pop()
        if ((current_x, current_y) in seen or current_x < 0 or current_y < 0
                or current_x >= map_width or current_y >= map_height):
            continue
        index = current_y * map_width + current_x
        if index >= len(tiles) or tiles[index].get("index", 0) == current_tile_selection:
            continue
        seen[(current_x, current_y)] = True
        tiles[index]["index"] = current_tile_selection
        pending.extend((
            (current_x, current_y + 1), (current_x, current_y - 1),
            (current_x + 1, current_y), (current_x - 1, current_y),
        ))

    if mark_revision and len(seen) > initial_seen_count:
        mark_tile_map_geometry_dirty(tile_map)
    return len(seen) - initial_seen_count

def set_tile_force_collidable(tile, enabled):
    """Store only an enabled per-instance override; absence means use tile-type policy."""
    if enabled:
        tile["force_collidable"] = True
    else:
        tile.pop("force_collidable", None)


def do_flood_fill_replace(initial, current_tile_selection, x, y, tile_map, map_width, seen, mark_revision=True, force_collidable=False):
    initial_seen_count = len(seen)
    map_height = int(tile_map.get("map_height", 0))
    tiles = tile_map.get("tiles", [])
    if x < 0 or y < 0 or x >= map_width or y >= map_height:
        return 0
    start_index = int(y) * map_width + int(x)
    if start_index >= len(tiles):
        return 0
    if (initial == current_tile_selection
            and bool(tiles[start_index].get("force_collidable", False)) == bool(force_collidable)):
        return 0
    pending = [(int(x), int(y))]
    while pending:
        current_x, current_y = pending.pop()
        if ((current_x, current_y) in seen or current_x < 0 or current_y < 0
                or current_x >= map_width or current_y >= map_height):
            continue
        index = current_y * map_width + current_x
        if index >= len(tiles) or tiles[index].get("index", 0) != initial:
            continue
        edited_tile = tiles[index]
        seen[(current_x, current_y)] = True
        edited_tile["index"] = current_tile_selection
        set_tile_force_collidable(edited_tile, force_collidable)
        pending.extend((
            (current_x, current_y + 1), (current_x, current_y - 1),
            (current_x + 1, current_y), (current_x - 1, current_y),
        ))

    if mark_revision and len(seen) > initial_seen_count:
        mark_tile_map_geometry_dirty(tile_map)
    return len(seen) - initial_seen_count


def interpolate_tile_line(start, end):
    """Return an eight-connected integer tile path including both endpoints."""
    start_x, start_y = int(start[0]), int(start[1])
    end_x, end_y = int(end[0]), int(end[1])
    delta_x = end_x - start_x
    delta_y = end_y - start_y
    steps = max(abs(delta_x), abs(delta_y))
    if steps == 0:
        return [(start_x, start_y)]
    points = []
    for step in range(steps + 1):
        tile = (
            round(start_x + delta_x * step / steps),
            round(start_y + delta_y * step / steps),
        )
        if not points or points[-1] != tile:
            points.append(tile)
    return points


def paint_tile_editor_points(tile_map, points, tile_edit_mode,
                             tile_selection=0, shape_selection=0,
                             force_collidable=False, rain_exposure=1.0,
                             acoustic_zone=0, footstep_overlay="none"):
    width = int(tile_map.get("map_width", 0))
    height = int(tile_map.get("map_height", 0))
    tiles = tile_map.get("tiles", [])
    changed = 0
    visited = set()
    for tile_x, tile_y in points:
        tile_x, tile_y = int(tile_x), int(tile_y)
        if ((tile_x, tile_y) in visited or tile_x < 0 or tile_y < 0
                or tile_x >= width or tile_y >= height):
            continue
        visited.add((tile_x, tile_y))
        index = tile_y * width + tile_x
        if index >= len(tiles) or not isinstance(tiles[index], dict):
            continue
        tile = tiles[index]
        if tile_edit_mode == "rain_exposure":
            changed += int(g_effects.set_tile_rain_exposure(tile, rain_exposure))
        elif tile_edit_mode == "acoustic_zone":
            changed += int(g_audio.set_tile_acoustic_zone(tile, acoustic_zone))
        elif tile_edit_mode == "footstep_overlay":
            changed += int(g_audio.set_tile_footstep_overlay(tile, footstep_overlay))
        elif (tile.get("index", 0) != tile_selection
                or tile.get("shape_index", 0) != shape_selection
                or bool(tile.get("force_collidable", False)) != bool(force_collidable)):
            tile["index"] = tile_selection
            tile["shape_index"] = shape_selection
            set_tile_force_collidable(tile, force_collidable)
            changed += 1
    if changed:
        if tile_edit_mode == "rain_exposure":
            g_effects.mark_rain_exposure_dirty(tile_map)
        elif tile_edit_mode == "acoustic_zone":
            g_audio.mark_acoustic_dirty(tile_map)
        elif tile_edit_mode == "appearance":
            mark_tile_map_geometry_dirty(tile_map)
    return changed


def update_tile_editor_paint(editor_state, tile_map, mouse_tile_pos,
                             tile_selection, shape_selection, force_collidable,
                             rain_exposure, acoustic_zone, footstep_overlay):
    if not g_ui.interactive_mouse_left_down():
        editor_state["tile_paint_previous"] = None
        editor_state["tile_paint_mode"] = None
        return 0
    current = (int(mouse_tile_pos.x), int(mouse_tile_pos.y))
    mode = editor_state.get("tile_edit_mode", "appearance")
    previous = editor_state.get("tile_paint_previous")
    if editor_state.get("tile_paint_mode") != mode or not isinstance(previous, (list, tuple)):
        points = [current]
    else:
        points = interpolate_tile_line(previous, current)
    editor_state["tile_paint_previous"] = current
    editor_state["tile_paint_mode"] = mode
    return paint_tile_editor_points(
        tile_map, points, mode, tile_selection, shape_selection,
        force_collidable, rain_exposure, acoustic_zone, footstep_overlay,
    )

        
        

def get_tile_cost(tile, tile_map):
    return 999999999 if tile_is_collidable(tile, tile_map) else 1

def graph_cost(tile_a, tile_b, tile_map):
    map_width = tile_map["map_width"]
    a_tile = tile_map["tiles"][tile_a.get("tile_y") * map_width + tile_a.get("tile_x")]
    b_tile = tile_map["tiles"][tile_b.get("tile_y") * map_width + tile_b.get("tile_x")]
    a_cost = get_tile_cost(a_tile, tile_map)
    b_cost = get_tile_cost(b_tile, tile_map)
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
        for next_tile in filter_invalid_neighbours(current.get("neighbours"), tile_map):
        # for next_tile in current.get("neighbours").values():
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

def filter_invalid_neighbours(current_neighbours, tile_map):
    # provide a version that 'disallows' diagonal movement 
    # appropriately (no diagonals if they have tiles on 'sides'
    result = []


    #tileH tileA tileB
    #tileG tile  tileC
    #tileF tileE tileD

    # TODO zzz pickup here

    removal_pairs = [
        ("A", "H"),
        ("G", "H"),        
        ("A", "B"),
        ("C", "B"),
        ("G", "F"),
        ("E", "F"),
        ("C", "D"),
        ("E", "D")
    ]

    to_remove = set()

    for pair in removal_pairs:
        candidate = pair[0]
        problem_tile = pair[1]
        if candidate in current_neighbours:
            candidate_position = current_neighbours[candidate]
            candidate_tile = tile_map["tiles"][candidate_position["tile_y"] * tile_map["map_width"] + candidate_position["tile_x"]]
            if tile_is_collidable(candidate_tile, tile_map):
                to_remove.add(problem_tile)    

    for key, tile in current_neighbours.items():        
        if key not in to_remove:
            result.append(tile)
    return result
    
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


    

def tile_not_in_bounds(tile_x, tile_y, tile_map):
    return (tile_x < 0 or tile_y < 0 or tile_x >= tile_map["map_width"] or tile_y >= tile_map["map_height"])

def tile_in_bounds(tile_x, tile_y, tile_map):
    return not tile_not_in_bounds(tile_x, tile_y, tile_map)

def draw_masked_tile_texture(texture, render_pos, shape_index, game_assets, scale=1.0, tint=None):
    tile_mask = game_assets["shaders"]["tile_mask"]
    shader = tile_mask["shader"]
    shape_index_location = tile_mask["shape_index_location"]

    shape_index_ptr = pr.ffi.new("int *", shape_index)

    pr.set_shader_value(shader, shape_index_location, shape_index_ptr, pr.ShaderUniformDataType.SHADER_UNIFORM_INT)

    pr.begin_shader_mode(shader)
    pr.draw_texture_ex(texture, render_pos, 0.0, scale, tint or pr.WHITE)
    pr.end_shader_mode()


def draw_tile_shape_tint(render_pos, shape_index, tile_width, tile_height, color):
    x = float(render_pos.x)
    y = float(render_pos.y)
    width = float(tile_width)
    height = float(tile_height)
    if shape_index == 0:
        pr.draw_rectangle(int(x), int(y), int(width), int(height), color)
        return
    vertices = {
        1: ((x, y), (x + width, y), (x, y + height)),
        2: ((x, y), (x + width, y), (x + width, y + height)),
        3: ((x + width, y), (x + width, y + height), (x, y + height)),
        4: ((x, y), (x + width, y + height), (x, y + height)),
    }.get(shape_index)
    if vertices is not None:
        pr.draw_triangle(*(pr.Vector2(*vertex) for vertex in vertices), color)


def update_gameplay_entity_editor(entities, editor_state, game_camera, mouse_screen, tile_map):
    if g_mouse_is_ui_captured:
        return
    if pr.is_key_pressed(pr.KeyboardKey.KEY_DELETE):
        g_editor.delete_selected_gameplay_entity(entities, editor_state)
    if editor_state.get("tool", "select") != "select":
        return
    mouse_world = {
        "x": float(mouse_screen.x) + float(game_camera.x),
        "y": float(mouse_screen.y) + float(game_camera.y),
    }
    if pr.is_key_pressed(pr.KeyboardKey.KEY_ESCAPE):
        editor_state.update({
            "selected_kind": None, "selected_collection": None,
            "selected_id": None, "drag_kind": None,
        })
        return
    if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
        if g_editor.select_gameplay_entity_at(entities, editor_state, mouse_world, tile_map):
            g_editor.delete_selected_gameplay_entity(entities, editor_state)
        return
    if g_ui.interactive_mouse_left_pressed():
        selected_key = g_editor.select_gameplay_entity_at(
            entities, editor_state, mouse_world, tile_map,
        )
        if selected_key is not None:
            selected = g_editor.get_selected_gameplay_entity(entities, editor_state)
            selected_world = g_editor.tile_position_to_world(
                selected.get("position", {}), tile_map,
            )
            editor_state["drag_kind"] = "gameplay_entity_move"
            editor_state["drag_offset"] = {
                "x": selected_world["x"] - mouse_world["x"],
                "y": selected_world["y"] - mouse_world["y"],
            }
    if (editor_state.get("drag_kind") == "gameplay_entity_move"
            and pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT)):
        g_editor.move_selected_gameplay_entity(
            entities, editor_state, mouse_world, tile_map,
        )
    if pr.is_mouse_button_released(pr.MouseButton.MOUSE_BUTTON_LEFT):
        editor_state["drag_kind"] = None


def _render_world_scene_phase(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, ignore, player_entity, mode, debug_queue, draw_tiles, draw_entities):
    # Todo:
    # tiles are tiles,
    # items are items, they can sit on top of tiles
    game_camera_x = (game_camera.x)
    game_camera_y = (game_camera.y)
    player_pos = player_entity.get("position",{})
    if ignore:
        return

    # use logical 1920 x 1080 'screen'
    map_height = tile_map["map_height"]
    map_width = tile_map["map_width"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    editor_state = game_assets.get("editor_state", {})
    tile_edit_mode = editor_state.get("tile_edit_mode", "appearance")
    rain_exposure_value = float(editor_state.get("rain_exposure_value", 1.0))
    acoustic_zone_value = int(editor_state.get("acoustic_zone_value", 0))
    footstep_overlay_value = editor_state.get("footstep_overlay_value", "none")
    if mode == "entity" and draw_tiles:
        update_gameplay_entity_editor(
            entities, editor_state, game_camera, mouse_pos_world, tile_map,
        )
    
    # Every mode renders into the same internal 480x270 target. The editor used
    # to cull against a legacy 1920x1080 viewport, causing it to submit most of
    # a 100x100 map even though those tiles were outside the render target.
    visible_tiles_across = int(g_internal_width / tile_width)
    visible_tiles_down = int(g_internal_height / tile_height)

    mouse_tile_pos = pr.Vector2(
        math.floor((mouse_pos_world.x + game_camera_x) / tile_width),
        math.floor((mouse_pos_world.y + game_camera_y) / tile_height),
    )

    mouse_tile_pos_offset_x = (mouse_pos_world.x + game_camera_x) - mouse_tile_pos.x*tile_width
    mouse_tile_pos_offset_y = (mouse_pos_world.y + game_camera_y) - mouse_tile_pos.y*tile_height

    if draw_tiles:
        if mode == "tile":
            update_tile_editor_paint(
                editor_state, tile_map, mouse_tile_pos,
                current_tile_selection, current_shape_selection,
                current_tile_force_collidable, rain_exposure_value,
                acoustic_zone_value, footstep_overlay_value,
            )
        else:
            editor_state["tile_paint_previous"] = None
            editor_state["tile_paint_mode"] = None



    top_left_pos = pr.Vector2(int(game_camera_x/tile_width), int(game_camera_y/tile_height))    
    
    # let's try be slightly quicker about this!
    # we could think about where the camera *is*
    # and just draw the ones around that..?    

    tile_select_modes = {"tile", "entity", "environment"}
    tile_rows = range(int(top_left_pos.y), int(top_left_pos.y + visible_tiles_down+2)) if draw_tiles else ()

    for y in tile_rows:
        for x in range(int(top_left_pos.x), int(top_left_pos.x + visible_tiles_across+1)):

            if x < 0 or x >= map_width or y < 0 or y >= map_height:
                continue

            index = min(y*map_width + x, len(tile_map["tiles"])-1)
            tile_to_draw = tile_map["tiles"][index]
            is_highlight = False
            tile_index = tile_to_draw.get("index",0)
            shape_index = tile_to_draw.get("shape_index",0)
            shape_to_draw = g_tile_collision_shapes[shape_index]
            color_to_draw = tile_map["tile_types"][tile_index].get("color")
            tile_color = color_map(color_to_draw)
            editor_collision_tint = should_tint_forced_collision_tile(tile_to_draw, mode)
            
            tile_type = tile_map["tile_types"][tile_index]
            snapped_tile_position = g_render_order.world_to_screen_pixel(
                x * tile_width, y * tile_height, game_camera,
            )
            render_pos = pr.Vector2(
                snapped_tile_position["x"], snapped_tile_position["y"],
            )

            if mode in tile_select_modes and x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                is_highlight = True

            if mode == "tile":
                if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                    
                    # if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT):
                    #     # do a flood fill
                    #     seen = {}
                    #     do_flood_fill(current_tile_selection, x, y, tile_map, map_width, seen)

                    if tile_edit_mode == "rain_exposure":
                        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT) and not g_mouse_is_ui_captured:
                            flood_fill_rain_exposure(tile_map, x, y, rain_exposure_value)
                    elif tile_edit_mode == "acoustic_zone":
                        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT) and not g_mouse_is_ui_captured:
                            g_audio.flood_fill_acoustic_zone(tile_map, x, y, acoustic_zone_value)
                    elif tile_edit_mode == "footstep_overlay":
                        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT) and not g_mouse_is_ui_captured:
                            g_audio.flood_fill_footstep_overlay(tile_map, x, y, footstep_overlay_value)
                    else:
                        if pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_RIGHT) and not g_mouse_is_ui_captured:
                            # Appearance flood fill retains the existing tile/collision semantics.
                            initial = tile_map["tiles"][y*map_width + x]["index"]
                            seen = {}
                            initial_force_collidable = bool(tile_map["tiles"][y*map_width + x].get("force_collidable", False))
                            if initial != current_tile_selection or initial_force_collidable != bool(current_tile_force_collidable):
                                do_flood_fill_replace(initial, current_tile_selection, x, y, tile_map, map_width, seen, force_collidable=current_tile_force_collidable)

                pr.draw_rectangle(int(render_pos.x), int(render_pos.y), tile_width, tile_height, tile_color)

            if mode == "entity":
                if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                    if (editor_state.get("tool", "select") == "place"
                            and g_ui.interactive_mouse_left_pressed()):
                        new_entity = {}
                        entity_types = game_assets.get("entity_types", [])
                        if current_entity_selection < len(entity_types):
                            entity_type = entity_types[current_entity_selection]
                        new_entity["type"] = entity_type                                                

                        offset_x = mouse_tile_pos_offset_x
                        offset_y = mouse_tile_pos_offset_y                        

                        new_entity["position"] = {"x" : offset_x, "y" : offset_y, "tile_x" : x, "tile_y" : y}
                        new_entity["entity_width"] = g_default_entity_width 
                        new_entity["entity_height"] = g_default_entity_height 
                        

                        give_entity_stats_from_type(new_entity, entity_type)

                        collection_name = categorise_entity_type(entity_type)
                        collection = entities.setdefault(collection_name, {})
                        entity_id = g_editor.allocate_gameplay_entity_id(collection)
                        new_entity["id"] = entity_id
                        collection[entity_id] = new_entity
                        editor_state.update({
                            "selected_kind": "gameplay_entity",
                            "selected_collection": collection_name,
                            "selected_id": entity_id,
                        })

                    
                            
                pr.draw_rectangle(int(render_pos.x), int(render_pos.y), tile_width, tile_height, tile_color)

            if tile_type.get("type") == "wood":
                draw_masked_tile_texture(game_assets.get("textures",{}).get("wood_texture"), render_pos, shape_index, game_assets)
            elif tile_type.get("type") == "wall":
                draw_masked_tile_texture(game_assets.get("textures",{}).get("wall_texture"), render_pos, shape_index, game_assets)
            elif tile_type.get("type") == "stone":
                draw_masked_tile_texture(game_assets.get("textures",{}).get("grey_tile_texture"), render_pos, shape_index, game_assets)
            elif tile_type.get("type") == "carpet":  #change to other tile
                draw_masked_tile_texture(game_assets.get("textures",{}).get("orange_tile_texture"), render_pos, shape_index, game_assets)
            if editor_collision_tint:
                draw_tile_shape_tint(render_pos, shape_index, tile_width, tile_height, pr.Color(255, 70, 180, 128))
            if is_highlight:
                pr.draw_rectangle_lines(int(render_pos.x), int(render_pos.y), tile_width, tile_height, pr.WHITE)

            if "decals" in tile_to_draw:
                for decal in tile_to_draw["decals"]:
                    if decal["type"] == "blood":
                        render_pos_x = render_pos.x + decal["offset_x"]
                        render_pos_y = render_pos.y + decal["offset_y"]
                        pr.draw_circle(int(render_pos_x), int(render_pos_y), decal.get("size",5), pr.RED)


    if not draw_entities:
        return

    if "projectiles" not in entities:
        entities["projectiles"] = {}
    if "brains" not in entities:
        entities["brains"] = {}
    if "pickups" not in entities:
        entities["pickups"] = {}
    

    for entity in entities["projectiles"].values():        
        if entity.get("type","") == "bullet":
            render_x = entity["position"]["x"] - game_camera_x
            render_y = entity["position"]["y"] - game_camera_y
            pr.draw_rectangle(int(render_x), int(render_y), 1, 1, pr.BROWN)            
    for entity in entities["brains"].values():
        if entity.get("type","") == "buddha":
            continue
        elif entity.get("type","") == "red head":
            render_pos_x = int(tile_width * entity.get("position",{}).get("tile_x",0) + entity.get("position",{}).get("x",0) - game_camera_x)
            render_pos_y = int(tile_height * entity.get("position",{}).get("tile_y",0) + entity.get("position",{}).get("y",0) - game_camera_y)

            texture_x = render_pos_x - 24
            texture_y = render_pos_y - 24            
            debug_str = f"angle is {round(entity.get("sight_angle",0))}"
            if debug_queue is not None:
                debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : render_pos_x, "y" : render_pos_y-10},                                        
                    "font_size" : 8,
                    "text" : debug_str,
                    "color" : "WHITE",
                    "z_sort" : 0,                    
                    "debug_modes" : ["entity_states", "player_debug"]
                }
                debug_queue.append(debug_item)

            # also put some debut stuff here for the attack
            if debug_queue is not None:
                pr.draw_text(f"{entity.get("current_state","")}", texture_x, texture_y - 40, 10, pr.WHITE)
                pr.draw_text(f"{entity.get("attack_substate","")}", texture_x, texture_y - 60, 10, pr.WHITE)
            if entity.get("current_state","") == "angry and attacking":
                attack_point = entity.get("attack_point", {"x" : 0, "y" :0})
                attack_timer = round(entity["attack_timer"], 2)
                attack_cooldown = entity["attack_cooldown"]
                attack_windup = entity["attack_windup_duration"]
                if entity.get("attack_substate","") == "windup" or entity.get("attack_substate","") == "committed":
                    if debug_queue is not None:
                        pr.draw_text(f"{attack_timer}/{attack_windup} windup...", texture_x, texture_y - 20, 10, pr.WHITE)
                    pr.draw_circle(int(attack_point["x"] - game_camera_x), int(attack_point["y"] - game_camera_y), 10, pr.YELLOW)
                elif entity.get("attack_substate","") == "attacking":
                    
                    pr.draw_circle(int(attack_point["x"] - game_camera_x), int(attack_point["y"] - game_camera_y), 10, pr.RED)
                    if debug_queue is not None:
                        pr.draw_text(f"BAM {attack_timer}/{attack_cooldown}", texture_x, texture_y - 20, 10, pr.RED)


def update_render_tile_map_base(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, ignore, player_entity, mode, debug_queue):
    _render_world_scene_phase(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, ignore, player_entity, mode, debug_queue, True, False)

def draw_world_entities(game_camera, entities, tile_map, game_assets, ignore, player_entity, mode, debug_queue):
    _render_world_scene_phase(game_camera, entities, tile_map, pr.Vector2(0, 0), 0, 0, 0, False, game_assets, ignore, player_entity, mode, debug_queue, False, True)

def draw_sorted_world_debug(render_items, occluding_items, game_camera, outlined_items=None):
    occluding_ids = {item.get("source_id", item.get("id")) for item in occluding_items}
    outlined_ids = {entry["item"].get("source_id", entry["item"].get("id")) for entry in outlined_items or []}
    for item in render_items:
        bounds = g_render_order.world_bounds_to_screen(item["bounds_world"], game_camera)
        base = item["base_world"]
        base_x = int(base["x"] - game_camera.x)
        base_y = int(base["y"] - game_camera.y)
        source_id = item.get("source_id", item.get("id"))
        color = pr.YELLOW if source_id in occluding_ids else pr.MAGENTA if item.get("occludes_render_items") else pr.GREEN
        pr.draw_rectangle_lines(int(bounds["x"]), int(bounds["y"]), int(bounds["width"]), int(bounds["height"]), color)
        pr.draw_circle(base_x, base_y, 2, color)
        pr.draw_text(f"{item.get('source')} y={item.get('sort_y', 0.0):.1f}", base_x + 3, base_y - 5, 6, color)
        if source_id in outlined_ids:
            pr.draw_text(f"outline: {item.get('outline', {}).get('policy', 'never')}", base_x + 3, base_y + 2, 6, pr.GOLD)

def update_render_tile_map(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, ignore, player_entity, mode, debug_queue):
    _render_world_scene_phase(game_camera, entities, tile_map, mouse_pos_world, current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, ignore, player_entity, mode, debug_queue, True, True)


def transition_debug_state(current):
    # TODO is there any benefit to this approach over just...
    # incrementing a list counter? maybe not?
    state_transitions = {
        "clear" : "player_debug",
        "player_debug" : "entity_states",
        "entity_states" : "pathfinding",
        "pathfinding" : "collisions",
        "collisions" : "line_of_sight",
        "line_of_sight" : "slow_bullets",
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
        "play": "tile",
        "tile": "entity",
        "entity": "environment",
        "environment": "play"
    }
    return state_transitions.get(g_editor.migrate_editor_mode(current), "tile")

def transition_collision_state(current):
    state_transitions = {
        "normal" : "noclip",
        "noclip" : "normal",
    }
    return state_transitions.get(current)

def make_default_camera():
    game_camera = pr.Camera3D(pr.Vector3(0,0,10), pr.Vector3(0,1,0), pr.Vector3(0,1,0), 45.0, pr.CameraProjection.CAMERA_ORTHOGRAPHIC)    
    return game_camera



def make_projectile(responsible, spawn_pos, velocity, id, type,
                    impact_speed=DEFAULT_BULLET_IMPACT_SPEED,
                    impact_duration=DEFAULT_BULLET_IMPACT_DURATION,
                    combined_impact_cap=DEFAULT_BULLET_COMBINED_IMPACT_CAP):
    current_pos = {"x" : spawn_pos["x"], "y" : spawn_pos["y"]}
    bullet = {"entity_responsible" : "player",
                  "spawn_position" : spawn_pos,
                  "position" : current_pos,
                  "velocity" : velocity,
                  "id" : id,
                  "type" : type,
                  "timer" : 0,
                  # Gameplay impact is deliberately independent from travel
                  # speed so hitscan-fast bullets do not launch enemies.
                  "impact_speed": max(0.0, float(impact_speed)),
                  "impact_duration": max(0.001, float(impact_duration)),
                  "combined_impact_cap": max(
                      0.0, float(combined_impact_cap),
                  ),
                  }
    return bullet


def give_entity_stats_from_type(entity, entity_type):
    if entity_type == "red head":
        entity["health"] = 60
        entity["max_health"] = 60
        entity["attack_damage"] = 5
        entity["attack_timer"] = 0
        entity["attack_cooldown"] = 1
        entity["notice_duration"] = 1.0
        entity["attack_engage_distance"] = DEFAULT_REDHEAD_ATTACK_ENGAGE_DISTANCE
        entity["attack_exit_delay"] = 1.0
        entity["bullet_hurtbox"] = {
            "offset": dict(DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]),
            "size": dict(DEFAULT_REDHEAD_BULLET_HURTBOX["size"]),
        }
        entity["collision_center_offset"] = dict(
            DEFAULT_REDHEAD_COLLISION_CENTER_OFFSET
        )
        entity["collision_radius_reduction"] = (
            DEFAULT_REDHEAD_COLLISION_RADIUS_REDUCTION
        )
        entity["evade_settings"] = dict(REDHEAD_EVADE_DEFAULTS)
        entity["flee_settings"] = dict(REDHEAD_FLEE_DEFAULTS)
        entity["has_fled"] = False
        entity["movement_settings"] = dict(REDHEAD_MOVEMENT_DEFAULTS)
        entity["perception_settings"] = dict(REDHEAD_PERCEPTION_DEFAULTS)
        entity["hearing_settings"] = dict(REDHEAD_HEARING_DEFAULTS)
        entity["sound_awareness"] = {
            "accumulator": 0.0,
            "silence_timer": 0.0,
            "startle_triggered": False,
            "chase_triggered": False,
        }
        attack_windup_duration = 1
    
    
        entity["attack_windup_duration"] = attack_windup_duration
    elif entity_type == "buddha":
        entity["health"] = 600
    elif entity_type == "pistol_ammo_pickup":
        entity["value"] = 20
    elif entity_type == "health_pickup":
        entity["value"] = 25

    g_render_order.ensure_entity_render_metadata(entity, entity_type)


    

def update_camera(game_camera, camera_physics, mode, player_pos, dt):    
    camera_speed = 500
    up = 0
    across = 0

    # let's go for a bounded box camera

    free_nav_modes = {"tile", "entity", "environment"}
    
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
        game_camera.position.x = max(-100, game_camera.position.x)
        game_camera.position.y = max(-100, game_camera.position.y)
    else:
        camera_acceleration = get_or_invoke(camera_physics, "acceleration", vec2_new)
        camera_velocity = get_or_invoke(camera_physics, "velocity", vec2_new)

        # TODO focus region

        tile_width = 16
        tile_height = 16
        player_pos_abs = make_pos_abs(player_pos, tile_width, tile_height)
        desired_camera_x = max(-16, player_pos_abs["x"] - 240)
        desired_camera_y = max(-24, player_pos_abs["y"] - 135)

        error_x = desired_camera_x - game_camera.position.x
        error_y = desired_camera_y - game_camera.position.y

        if math.sqrt(error_x**2 + error_y**2) < 10:
            camera_velocity["x"] = 0
            camera_velocity["y"] = 0
            return game_camera

        

        

        stiffness_x = 25
        damping_x = 10

        stiffness_y = 25
        damping_y = 10

        accel_x = error_x * stiffness_x - damping_x * camera_velocity["x"]        
        accel_y = error_y * stiffness_y - damping_y * camera_velocity["y"]

        camera_velocity["x"] += accel_x * dt        
        camera_velocity["y"] += accel_y * dt        
        
        game_camera.position.x += camera_velocity["x"] * dt
        game_camera.position.y += camera_velocity["y"] * dt

        remaining_error_x = (desired_camera_x - game_camera.position.x )
        remaining_error_y = (desired_camera_y - game_camera.position.y)

        error_x_epsilon = 2
        error_y_epsilon = 2

        vel_x_epsilon = 4
        vel_y_epsilon = 4

     
        
        
    
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

    player["entity_width"] = 12 #drawing at double scale
    player["entity_height"] = 12

    player["position"] = pos

    player["id"] = "player"

    player["health"] = 100

    player["ammo"] = {}

    player["ammo"]["pistol"] = 20    
    player["ammo"]["spare_pistol"] = 20

    player["aim_heading"] = DEFAULT_AIM_HEADING_DEGREES
    player["aim_direction"] = {"x": 1.0, "y": 0.0}
    player["aim_cursor_offset"] = {"x": DEFAULT_AIM_CURSOR_DISTANCE, "y": 0.0}
    player["aim_requested"] = False
    player["aiming"] = False
    player["weapon_transition"] = {
        "progress": 0.0,
        "target": 0.0,
        "phase": "holstered",
    }
    player["aim_accuracy"] = {
        "motion_instability": 0.0,
        "shot_instability": 0.0,
        "filtered_angular_speed": 0.0,
        "previous_angular_speed": 0.0,
        "previous_heading": DEFAULT_AIM_HEADING_DEGREES,
    }
    player["mouse_aim_sensitivity"] = DEFAULT_MOUSE_AIM_SENSITIVITY
    player["aim_input_version"] = AIM_INPUT_VERSION

    g_render_order.ensure_entity_render_metadata(player, "player")
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
        print(f"issue loading state {e}")        

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
        find_unpickleable_values(arena)

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


def queue_gameplay_audio(audio_runtime, event_type, source_id, source_kind,
                         world_position=None, priority=1.0, gain=1.0, data=None):
    if isinstance(world_position, dict):
        position = dict(world_position)
    else:
        position = {
            "x": float(getattr(world_position, "x", 0.0)),
            "y": float(getattr(world_position, "y", 0.0)),
        }
    return g_audio.queue_audio_event(audio_runtime, {
        "type": event_type,
        "source_id": str(source_id),
        "source_kind": str(source_kind),
        "world_position": position,
        "priority": float(priority),
        "gain": float(gain),
        "data": dict(data or {}),
    })


















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

def load_shaders():
    result = {}

    tile_mask = pr.load_shader("", "shaders/tile_mask.fs")
    result["tile_mask"] = {
        "shader": tile_mask,
        "shape_index_location": pr.get_shader_location(tile_mask, "shapeIndex")
    }

    cinematic_shadow_projection = pr.load_shader("", "shaders/cinematic_shadow_projection.fs")
    result["cinematic_shadow_projection"] = {
        "shader": cinematic_shadow_projection,
        "shadow_color_location": pr.get_shader_location(cinematic_shadow_projection, "shadowColor"),
        "shadow_opacity_location": pr.get_shader_location(cinematic_shadow_projection, "shadowOpacity"),
        "alpha_cutoff_location": pr.get_shader_location(cinematic_shadow_projection, "alphaCutoff")
    }

    cinematic_shadow_composite = pr.load_shader("", "shaders/cinematic_shadow_composite.fs")
    result["cinematic_shadow_composite"] = {
        "shader": cinematic_shadow_composite,
        "shadow_texture_location": pr.get_shader_location(cinematic_shadow_composite, "shadowTexture"),
        "visibility_texture_location": pr.get_shader_location(cinematic_shadow_composite, "visibilityTexture")
    }

    render_item_outline = pr.load_shader("", "shaders/render_item_outline.fs")
    result["render_item_outline"] = {
        "shader": render_item_outline,
        "resolution_location": pr.get_shader_location(render_item_outline, "resolution"),
        "outline_color_location": pr.get_shader_location(render_item_outline, "outlineColor"),
        "outline_width_location": pr.get_shader_location(render_item_outline, "outlineWidth")
    }

    entity_self_shadow = pr.load_shader("", "shaders/entity_self_shadow.fs")
    result["entity_self_shadow"] = {
        "shader": entity_self_shadow,
        "entity_light_texture_location": pr.get_shader_location(entity_self_shadow, "entityLightTexture"),
        "entity_readability_light_texture_location": pr.get_shader_location(entity_self_shadow, "entityReadabilityLightTexture"),
        "directional_response_texture_location": pr.get_shader_location(entity_self_shadow, "directionalResponseTexture"),
        "resolution_location": pr.get_shader_location(entity_self_shadow, "resolution"),
        "source_uv_min_location": pr.get_shader_location(entity_self_shadow, "sourceUvMin"),
        "source_uv_max_location": pr.get_shader_location(entity_self_shadow, "sourceUvMax"),
        "face_exposure_location": pr.get_shader_location(entity_self_shadow, "faceExposure"),
        "omni_exposure_location": pr.get_shader_location(entity_self_shadow, "omniExposure"),
        "world_occlusion_scale_location": pr.get_shader_location(entity_self_shadow, "worldOcclusionScale"),
        "self_shadow_mode_location": pr.get_shader_location(entity_self_shadow, "selfShadowMode"),
        "self_shadow_strength_location": pr.get_shader_location(entity_self_shadow, "selfShadowStrength"),
        "self_shadow_softness_location": pr.get_shader_location(entity_self_shadow, "selfShadowSoftness"),
        "self_shadow_back_fill_location": pr.get_shader_location(entity_self_shadow, "selfShadowBackFill"),
        "self_shadow_minimum_direct_location": pr.get_shader_location(entity_self_shadow, "selfShadowMinimumDirect"),
        "profile_divider_enabled_location": pr.get_shader_location(entity_self_shadow, "profileDividerEnabled"),
        "profile_divider_top_location": pr.get_shader_location(entity_self_shadow, "profileDividerTop"),
        "profile_divider_bottom_location": pr.get_shader_location(entity_self_shadow, "profileDividerBottom"),
        "profile_light_origin_location": pr.get_shader_location(entity_self_shadow, "profileLightOrigin"),
        "self_shadow_debug_output_location": pr.get_shader_location(entity_self_shadow, "selfShadowDebugOutput"),
        "self_shadow_pass_location": pr.get_shader_location(entity_self_shadow, "selfShadowPass"),
        "ambient_color_location": pr.get_shader_location(entity_self_shadow, "ambientColor"),
        "shadow_color_location": pr.get_shader_location(entity_self_shadow, "shadowColor"),
        "ambient_strength_location": pr.get_shader_location(entity_self_shadow, "ambientStrength"),
        "direct_light_strength_location": pr.get_shader_location(entity_self_shadow, "directLightStrength"),
        "black_point_location": pr.get_shader_location(entity_self_shadow, "blackPoint"),
        "shadow_softness_location": pr.get_shader_location(entity_self_shadow, "shadowSoftness"),
        "shadow_detail_location": pr.get_shader_location(entity_self_shadow, "shadowDetail"),
        "contrast_location": pr.get_shader_location(entity_self_shadow, "contrast"),
        "light_posterize_enabled_location": pr.get_shader_location(entity_self_shadow, "lightPosterizeEnabled"),
        "light_posterize_levels_location": pr.get_shader_location(entity_self_shadow, "lightPosterizeLevels"),
        "light_dither_enabled_location": pr.get_shader_location(entity_self_shadow, "lightDitherEnabled"),
        "light_dither_strength_location": pr.get_shader_location(entity_self_shadow, "lightDitherStrength"),
        "posterize_ambient_location": pr.get_shader_location(entity_self_shadow, "posterizeAmbient")
    }

    light_accumulation = pr.load_shader("", "shaders/light_accumulation.fs")
    result["light_accumulation"] = {
        "shader": light_accumulation,
        "resolution_location": pr.get_shader_location(light_accumulation, "resolution"),
        "light_position_location": pr.get_shader_location(light_accumulation, "lightPosition"),
        "light_direction_location": pr.get_shader_location(light_accumulation, "lightDirection"),
        "light_color_location": pr.get_shader_location(light_accumulation, "lightColor"),
        "radius_location": pr.get_shader_location(light_accumulation, "radius"),
        "intensity_location": pr.get_shader_location(light_accumulation, "intensity"),
        "falloff_location": pr.get_shader_location(light_accumulation, "falloff"),
        "near_fade_distance_location": pr.get_shader_location(light_accumulation, "nearFadeDistance"),
        "inner_cone_cos_location": pr.get_shader_location(light_accumulation, "innerConeCos"),
        "outer_cone_cos_location": pr.get_shader_location(light_accumulation, "outerConeCos"),
        "light_type_location": pr.get_shader_location(light_accumulation, "lightType")
    }

    top_down_light = pr.load_shader("", "shaders/top_down_light.fs")
    result["top_down_light"] = {
        "shader": top_down_light,
        "resolution_location": pr.get_shader_location(top_down_light, "resolution"),
        "area_min_location": pr.get_shader_location(top_down_light, "areaMin"),
        "area_max_location": pr.get_shader_location(top_down_light, "areaMax"),
        "light_color_location": pr.get_shader_location(top_down_light, "lightColor"),
        "intensity_location": pr.get_shader_location(top_down_light, "intensity"),
        "edge_softness_location": pr.get_shader_location(top_down_light, "edgeSoftness")
    }

    fog_volume_mask = pr.load_shader("", "shaders/fog_volume_mask.fs")
    result["fog_volume_mask"] = {
        "shader": fog_volume_mask,
        "resolution_location": pr.get_shader_location(fog_volume_mask, "resolution"),
        "area_min_location": pr.get_shader_location(fog_volume_mask, "areaMin"),
        "area_max_location": pr.get_shader_location(fog_volume_mask, "areaMax"),
        "shape_type_location": pr.get_shader_location(fog_volume_mask, "shapeType"),
        "edge_softness_location": pr.get_shader_location(fog_volume_mask, "edgeSoftness"),
        "strength_location": pr.get_shader_location(fog_volume_mask, "strength")
    }

    lighting_composite = pr.load_shader("", "shaders/lighting_composite.fs")
    result["lighting_composite"] = {
        "shader": lighting_composite,
        "light_texture_location": pr.get_shader_location(lighting_composite, "lightTexture"),
        "readability_light_texture_location": pr.get_shader_location(lighting_composite, "readabilityLightTexture"),
        "ambient_color_location": pr.get_shader_location(lighting_composite, "ambientColor"),
        "shadow_color_location": pr.get_shader_location(lighting_composite, "shadowColor"),
        "ambient_strength_location": pr.get_shader_location(lighting_composite, "ambientStrength"),
        "direct_light_strength_location": pr.get_shader_location(lighting_composite, "directLightStrength"),
        "black_point_location": pr.get_shader_location(lighting_composite, "blackPoint"),
        "shadow_softness_location": pr.get_shader_location(lighting_composite, "shadowSoftness"),
        "shadow_detail_location": pr.get_shader_location(lighting_composite, "shadowDetail"),
        "contrast_location": pr.get_shader_location(lighting_composite, "contrast"),
        "light_posterize_enabled_location": pr.get_shader_location(lighting_composite, "lightPosterizeEnabled"),
        "light_posterize_levels_location": pr.get_shader_location(lighting_composite, "lightPosterizeLevels"),
        "light_dither_enabled_location": pr.get_shader_location(lighting_composite, "lightDitherEnabled"),
        "light_dither_strength_location": pr.get_shader_location(lighting_composite, "lightDitherStrength"),
        "posterize_ambient_location": pr.get_shader_location(lighting_composite, "posterizeAmbient")
    }

    illuminated_fog = pr.load_shader("", "shaders/illuminated_fog.fs")
    result["illuminated_fog"] = {
        "shader": illuminated_fog,
        "texture_location": pr.get_shader_location(illuminated_fog, "texture0"),
        "light_texture_location": pr.get_shader_location(illuminated_fog, "lightTexture"),
        "volume_texture_location": pr.get_shader_location(illuminated_fog, "volumeTexture"),
        "resolution_location": pr.get_shader_location(illuminated_fog, "resolution"),
        "camera_position_location": pr.get_shader_location(illuminated_fog, "cameraPosition"),
        "fog_drift_location": pr.get_shader_location(illuminated_fog, "fogDrift"),
        "detail_drift_location": pr.get_shader_location(illuminated_fog, "detailDrift"),
        "fog_color_location": pr.get_shader_location(illuminated_fog, "fogColor"),
        "time_location": pr.get_shader_location(illuminated_fog, "time"),
        "density_location": pr.get_shader_location(illuminated_fog, "density"),
        "opacity_location": pr.get_shader_location(illuminated_fog, "opacity"),
        "world_scale_location": pr.get_shader_location(illuminated_fog, "worldScale"),
        "detail_scale_location": pr.get_shader_location(illuminated_fog, "detailScale"),
        "cutoff_location": pr.get_shader_location(illuminated_fog, "cutoff"),
        "softness_location": pr.get_shader_location(illuminated_fog, "softness"),
        "light_strength_location": pr.get_shader_location(illuminated_fog, "lightStrength"),
        "ambient_strength_location": pr.get_shader_location(illuminated_fog, "ambientStrength"),
        "veil_strength_location": pr.get_shader_location(illuminated_fog, "veilStrength"),
        "evolution_speed_location": pr.get_shader_location(illuminated_fog, "evolutionSpeed"),
        "warp_scale_location": pr.get_shader_location(illuminated_fog, "warpScale"),
        "warp_strength_location": pr.get_shader_location(illuminated_fog, "warpStrength"),
        "detail_evolution_speed_location": pr.get_shader_location(illuminated_fog, "detailEvolutionSpeed"),
        "global_amount_location": pr.get_shader_location(illuminated_fog, "globalAmount"),
        "posterize_enabled_location": pr.get_shader_location(illuminated_fog, "posterizeEnabled"),
        "posterize_levels_location": pr.get_shader_location(illuminated_fog, "posterizeLevels"),
        "dither_enabled_location": pr.get_shader_location(illuminated_fog, "ditherEnabled"),
        "dither_strength_location": pr.get_shader_location(illuminated_fog, "ditherStrength")
    }

    g_graphics.load_effect_shaders(result)

    return result



def unload_shaders(shaders):
    if not shaders:
        return

    for shader_info in shaders.values():
        shader = shader_info.get("shader")
        if shader is not None:
            pr.unload_shader(shader)
    



def load_textures():
    result = {}    
    # we could make this easier to use if we monitored the files in the directory once
    # a second and then did a reload when a new one was in there!
    result["pistol_texture"] = pr.load_texture("art/pistol.png")
    result["pistol_texture_flipped"] = pr.load_texture("art/pistol_flipped.png")
    result["wood_texture"] = pr.load_texture("art/WoodDark.png")
    result["wall_texture_editor"] = pr.load_texture("art/WallDark.png")
    result["wall_texture"] = pr.load_texture("art/WallDarkChunky16x.png")
    result["red_head_texture"] = pr.load_texture("art/RedHead.png")
    result["blue_oxford_texture"] = pr.load_texture("art/blue_oxford.png")
    result["grey_tile_texture"] = pr.load_texture("art/grey_tile_16x.png")
    result["orange_tile_texture"] = pr.load_texture("art/orange_tile_16x.png")

    result["pistol_ammo_pickup_texture"] = pr.load_texture("art/pistol_ammo_pickup.png")
    result["health_pickup_texture"] = pr.load_texture("art/health_pickup.png")

    

    result["buddha_texture"] = pr.load_texture("art/buddha_128.png")
    if os.path.isfile("art/buddha_light_response.png"):
        result["buddha_light_response"] = pr.load_texture("art/buddha_light_response.png")
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

def get_tile_at_x_y(x, y, tile_map, debug_queue = None):
    tile_index = get_flat_tile_index(x, y, tile_map, debug_queue)
    tile_at_index = get_tile_at_index(tile_index)
    return tile_at_index

def get_flat_tile_index(x, y, tile_map, debug_queue = None):    
    return y*tile_map.get("map_width") + x

def get_tile_at_index(flat_index, tile_map):
    # bounds check
    if flat_index < 0 or flat_index >= len(tile_map["tiles"]):
        print("warning: bad tile index!")
        flat_index = 0
    tile_at_index = tile_map["tiles"][flat_index]
    return tile_at_index

def update_player_flashlight_toggle(player_entity, editor_mode, pause_state, audio_runtime):
    if "flashlight_enabled" not in player_entity:
        player_entity["flashlight_enabled"] = True

    if editor_mode == "play" and pause_state == "unpaused" and pr.is_key_pressed(pr.KeyboardKey.KEY_F):
        queue_gameplay_audio(audio_runtime, "ui_hover", "player:flashlight", "ui", priority=1.2)
        player_entity["flashlight_enabled"] = not player_entity["flashlight_enabled"]

    return player_entity["flashlight_enabled"]

def get_tile_index_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]        
    tile_x = math.floor((pos.get("x",0))/tile_width)
    tile_y = math.floor((pos.get("y",0))/tile_height)

    return {"tile_x" : tile_x, "tile_y" : tile_y}

def get_tile_index_and_offset_from_pos(pos, tile_map, debug_queue = None):    
    map_width = tile_map["map_width"]
    map_height = tile_map["map_height"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]    
    
    tile_x = math.floor((pos.get("x",0))/tile_width)
    tile_y = math.floor((pos.get("y",0))/tile_height)

    offset_x = pos["x"] - (tile_x * tile_width)
    offset_y = pos["y"] - (tile_y * tile_height)

    return {"tile_x" : tile_x, "tile_y" : tile_y, "x" : offset_x, "y" : offset_y}

def get_abs_pos_from_index(pos, tile_map, debug_queue = None):            
    abs_x = tile_map["tile_width"] * pos.get("tile_x",0) + pos.get("x",16)
    abs_y = tile_map["tile_height"] * pos.get("tile_y",0) + pos.get("y",16)
    
    return {"x" : abs_x, "y" : abs_y}

def get_abs_pos_from_index_given_offset(pos, offset, tile_map, debug_queue = None):            
    abs_x = tile_map["tile_width"] * pos.get("tile_x",0) + offset.get("x",16)
    abs_y = tile_map["tile_height"] * pos.get("tile_y",0) + offset.get("y",16)
    
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
        additional_x_tiles = math.floor(pos.get("x",0) / tile_width)        

    if pos["x"] < 0:
        additional_x_tiles = -math.floor((tile_width + abs(pos.get("x",0))) / tile_width)
        

    if pos["y"] < 0:
        additional_y_tiles = -math.floor((tile_height + abs(pos.get("y",0))) / tile_height)
        # I think this will do us?                

    if pos["y"] > tile_height:
        additional_y_tiles = math.floor(pos.get("y",0) / tile_height)        

    tile_x = pos.get("tile_x") + additional_x_tiles    
    tile_y = pos.get("tile_y") + additional_y_tiles


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
            "z_sort" : 1,
            "debug_modes" : ["player_debug"]

        }    
        debug_queue.append(debug_item)

    # if pos["tile_x"] < 0 or pos["tile_y"] < 0:
    #     return "wall"
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

def vec2_distance_tile(a, b, tile_map):
    # TODO (Cooper) : make this also use the tiles they're on!
    tile_abs_a = get_abs_pos_from_index(a, tile_map)
    tile_abs_b = get_abs_pos_from_index(b, tile_map)
    return vec2_distance(tile_abs_a, tile_abs_b)

def vec2_new(x=0, y=0):
    return {"x":x, "y":y}

def vec2_distance(a, b):    
    return math.sqrt((a["x"] - b["x"])**2 + (a["y"] - b["y"])**2)

def vec2_dot(a, b):
    # remember a dot b is |a||b|cos(theta)
    # therefore if we use normalized and b
    # it is just the cosine of the angle
    # and hence...
    # well there it is
    return a.get("x", 0) * b.get("x", 0) + a.get("y", 0) * b.get("y", 0)

def cos_flexible(angle, unit="degrees"):
    angle_in_radians = angle
    if unit == "degrees":
        angle_in_radians = deg_to_rad(angle)
    return math.cos(angle_in_radians)

def sin_flexible(angle, unit="degrees"):
    angle_in_radians = angle
    if unit == "degrees":
        angle_in_radians = deg_to_rad(angle)
    return math.sin(angle_in_radians)

def alice_can_see_bob_points(alice, bob_entity, tile_map, debug_queue):
    bob_position = bob_entity["position"]
    # The centre succeeds in the overwhelming majority of unobstructed cases.
    # Only try the four silhouette corners when the centre is occluded, which
    # keeps the useful "peeking around an edge" behaviour without tracing all
    # sixteen perimeter samples on every perception update.
    if alice_can_see_bob(alice, bob_position, tile_map, debug_queue):
        return True, bob_position

    bob_points = make_entity_boundary_points(
        bob_position, bob_entity["entity_width"], bob_entity["entity_height"],
        tile_map["tile_width"], tile_map["tile_height"], 1,
    )
    for position in bob_points.values():
        if alice_can_see_bob(alice, position, tile_map, debug_queue):
            return True, position
    return False, None

    
def alice_can_move_to_bob(alice, bob_position, tile_map, debug_queue):
    bob_abs = get_abs_pos_from_index(bob_position["position"], tile_map)
    alice_abs = get_abs_pos_from_index(alice["position"], tile_map)
    ray_to_bob = (vec2_subtract(bob_abs, alice_abs))
    ray_to_bob_normal = vec2_normalize(ray_to_bob)
    bob_beam = vec2_rotate_by(ray_to_bob_normal, 90)
    
    beam_width = 16 # might need to derive this

    scaled_beam = vec2_scale(bob_beam, beam_width / 2)

    bob_upper = vec2_add(bob_abs, scaled_beam)
    bob_upper_canonical = get_tile_index_and_offset_from_pos(bob_upper, tile_map, debug_queue)
    bob_lower = vec2_add(bob_abs, vec2_scale(scaled_beam, -1.0))
    bob_lower_canonical = get_tile_index_and_offset_from_pos(bob_lower, tile_map, debug_queue)

    alice_upper = vec2_add(alice_abs, scaled_beam)


    alice_upper_canonical = get_tile_index_and_offset_from_pos(alice_upper, tile_map, debug_queue)


    alice_lower = vec2_add(alice_abs, vec2_scale(scaled_beam, -1.0))
    alice_lower_canonical = get_tile_index_and_offset_from_pos(alice_lower, tile_map, debug_queue)

    move_range = 900 # matches sight range?
    can_move =  alice_can_raycast_to_bob(move_range, alice_upper_canonical, bob_upper_canonical, tile_map, debug_queue) and alice_can_raycast_to_bob(move_range, alice_lower_canonical, bob_lower_canonical, tile_map, debug_queue)

    if debug_queue is not None:                        
        debug_item = debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : alice_upper.get("x"), "y" : alice_upper.get("y")},                                        
                    "pos_end" : {"x" : bob_upper.get("x"), "y" : bob_upper.get("y")},                                        
                    "line_width" : 2,                    
                    "color" : "PINK",
                    "z_sort" : -1,                    
                    "debug_modes" : ["collisions"]                    
                }
        debug_queue.append(debug_item)
        debug_item = debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : alice_lower.get("x"), "y" : alice_lower.get("y")},                                        
                    "pos_end" : {"x" : bob_lower.get("x"), "y" : bob_lower.get("y")},                                        
                    "line_width" : 2,                    
                    "color" : "PINK",
                    "z_sort" : -1,                    
                    "debug_modes" : ["collisions"]                    
                }
        debug_queue.append(debug_item)

    return can_move


def alice_can_see_bob(alice, bob_position, tile_map, debug_queue):
    # we can actually super optimze this
    # first, see if bob is in the radius at all (distance)

    # then see if he's in the sight angle
    # (still don't do any raycasting yet)

    # then finally if he's both in-range and in-angle
    # THEN do like, a single raycast from bob to alice to see if there's walls hiding
    # (you could also do a very small amount to represent a radius)

    # a does need a direction
    # should have a size of object too obviously
    bob_abs = get_abs_pos_from_index(bob_position, tile_map)
    alice_abs = get_abs_pos_from_index(alice["position"], tile_map)
    ray_to_bob = (vec2_subtract(bob_abs, alice_abs))
    ray_to_bob_normal = vec2_normalize(ray_to_bob)
    # you could model bob as a sphere
    # then just trace down the line of sight?

    bob_tiles = bob_position

    
    alice_pos = alice.get("position")

    abs_alice = get_abs_pos_from_index(alice_pos, tile_map)
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
                    "debug_modes" : ["line_of_sight"]
                }
        debug_queue.append(debug_item)

    sight_range = alice.get("sight_range", 900)



    if vec2_distance_tile(alice_pos, bob_position, tile_map) > sight_range:
        return False

    

    bob_radius = 20

    alice_fov = 140

    

    angle_to_bob = vec2_dot(ray_to_bob_normal, main_direction)

    angle_start = vec2_scale(vector_from_angle(alice_sight_angle - int(alice_fov/2) ), 50)
    angle_end = vec2_scale(vector_from_angle(alice_sight_angle + int(alice_fov/2)), 50)

    if debug_queue is not None:
        debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : alice_abs.get("x",0), "y" : alice_abs.get("y",0) - 50},                                        
                    "font_size" : 16,
                    "text" : f"angle to bob: {angle_to_bob}",
                    "color" : "RED",
                    "z_sort" : 0,                    
                    "debug_modes" : ["line_of_sight"]
                }
        debug_queue.append(debug_item)
        debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : abs_alice.get("x"), "y" : abs_alice.get("y")},                                        
                    "pos_end" : {"x" : abs_alice.get("x") + angle_start.get("x"), "y" : abs_alice.get("y") + angle_start.get("y")},                                        
                    "line_width" : 1,                    
                    "color" : "PURPLE",
                    "z_sort" : -1,                    
                    "debug_modes" : ["line_of_sight"]
                }
        debug_queue.append(debug_item)

        debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : abs_alice.get("x"), "y" : abs_alice.get("y")},                                        
                    "pos_end" : {"x" : abs_alice.get("x") + angle_end.get("x"), "y" : abs_alice.get("y") + angle_end.get("y")},                                        
                    "line_width" : 1,                    
                    "color" : "PURPLE",
                    "z_sort" : -1,                    
                    "debug_modes" : ["line_of_sight"]
                }
        debug_queue.append(debug_item)

    
    
    if angle_to_bob < cos_flexible(alice_fov/2):
        return False

    step_size = 10

    # ideally what we do here
    # is have the lines follow a sort of radial fall off
    # so people can see far ahead
    # but less so in their peripheral
    # it might also be fun to play with the idea of 'motion' as a giveway
    
    
    alice_direction_of_sight_normalized = ray_to_bob_normal
    can_see = ray_along_tiles_hits_target_tile(alice_pos, bob_tiles, sight_range, int(bob_radius)/2, alice_direction_of_sight_normalized, tile_map, debug_queue)
    
    return can_see

def alice_can_raycast_to_bob(sight_range, alice_position, bob_position, tile_map, debug_queue):
    # should have a size of object too obviously
    bob_abs = get_abs_pos_from_index(bob_position, tile_map)
    alice_abs = get_abs_pos_from_index(alice_position, tile_map)
    ray_to_bob = (vec2_subtract(bob_abs, alice_abs))
    ray_to_bob_normal = vec2_normalize(ray_to_bob)
    # you could model bob as a sphere
    # then just trace down the line of sight?
    
    bob_radius = 16

    can_see = ray_along_tiles_hits_target_tile(alice_position, bob_position, sight_range, int(bob_radius)/2, ray_to_bob_normal, tile_map, debug_queue)
    
    return can_see

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
    

    adjacent_tiles = {
    "A" : {"tile_x" : tile_x,  "tile_y" : tile_y - 1}, #A
    "B" : {"tile_x" : tile_x+1,  "tile_y" : tile_y - 1}, #B
    "C" : {"tile_x" : tile_x+1,  "tile_y" : tile_y}, #C
    "D" : {"tile_x" : tile_x+1,  "tile_y" : tile_y+1}, #D
    "E" : {"tile_x" : tile_x,  "tile_y" : tile_y+1}, #E
    "F" : {"tile_x" : tile_x-1,  "tile_y" : tile_y+1}, #F
    "G" : {"tile_x" : tile_x-1,  "tile_y" : tile_y}, #G
    "H" : {"tile_x" : tile_x-1,  "tile_y" : tile_y-1} #H
    }
    
    filtered = {}

    for key, new_tile in adjacent_tiles.items():
        if new_tile.get("tile_x") < 0 or new_tile.get("tile_x") >= tile_map.get("map_width") or new_tile.get("tile_y") < 0 or new_tile.get("tile_y") >= tile_map.get("map_height"):
            continue
        filtered[key] = new_tile

    return filtered



def tile_and_offset_to_absolute(tile_map, position):
    tile_width = tile_map.get("tile_width",0)
    tile_height = tile_map.get("tile_height",0)

    abs_x = tile_width * position.get("tile_x") + position.get("x")
    abs_y = tile_height * position.get("tile_y") + position.get("y")

    return {"x" : abs_x, "y": abs_y}

    
def ray_along_tiles_hits_target_tile(original_position, target_tile, end_range, step_size, normalized_ray_direction, tile_map, debug_queue = None):
    origin_x = int(original_position.get("tile_x", -1))
    origin_y = int(original_position.get("tile_y", -1))
    target_x = int(target_tile.get("tile_x", -1))
    target_y = int(target_tile.get("tile_y", -1))
    if (tile_not_in_bounds(origin_x, origin_y, tile_map)
            or tile_not_in_bounds(target_x, target_y, tile_map)):
        return False

    absolute_origin = tile_and_offset_to_absolute(tile_map, original_position)
    absolute_target = tile_and_offset_to_absolute(tile_map, target_tile)
    target_delta = vec2_subtract(absolute_target, absolute_origin)
    target_distance = vec2_norm(target_delta)
    if target_distance > max(0.0, float(end_range)) + 0.000001:
        return False

    tile_width = max(0.000001, float(tile_map.get("tile_width", 16)))
    tile_height = max(0.000001, float(tile_map.get("tile_height", 16)))
    delta_x = float(target_delta.get("x", 0.0))
    delta_y = float(target_delta.get("y", 0.0))
    step_x = 1 if delta_x > 0.0 else (-1 if delta_x < 0.0 else 0)
    step_y = 1 if delta_y > 0.0 else (-1 if delta_y < 0.0 else 0)
    tile_x = origin_x
    tile_y = origin_y

    if step_x:
        next_x = (tile_x + (1 if step_x > 0 else 0)) * tile_width
        t_max_x = (next_x - absolute_origin["x"]) / delta_x
        t_delta_x = tile_width / abs(delta_x)
    else:
        t_max_x = math.inf
        t_delta_x = math.inf
    if step_y:
        next_y = (tile_y + (1 if step_y > 0 else 0)) * tile_height
        t_max_y = (next_y - absolute_origin["y"]) / delta_y
        t_delta_y = tile_height / abs(delta_y)
    else:
        t_max_y = math.inf
        t_delta_y = math.inf

    # Grid DDA visits each crossed tile exactly once. The old fixed-distance
    # marcher revisited the same tile several times on every ray.
    while not tile_not_in_bounds(tile_x, tile_y, tile_map):
        test_tiles = {"tile_x": tile_x, "tile_y": tile_y}
        found_tile = tile_map["tiles"][tile_y * tile_map["map_width"] + tile_x]
        collidable = tile_is_collidable(found_tile, tile_map)

        if debug_queue is not None:
            debug_queue.append({
                "type": "tile",
                "tile_x": tile_x,
                "tile_y": tile_y,
                "tile_width": tile_map.get("tile_width", 5),
                "tile_height": tile_map.get("tile_height", 5),
                "color": "PINK" if collidable else "RED",
                "drawing_function": draw_debug_tile,
                "z_sort": 1,
                "debug_modes": ["line_of_sight"],
            })
        if collidable and not g_test_see_through_walls:
            return False
        if tile_x == target_x and tile_y == target_y:
            return True
        if t_max_x < t_max_y:
            tile_x += step_x
            t_max_x += t_delta_x
        elif t_max_y < t_max_x:
            tile_y += step_y
            t_max_y += t_delta_y
        else:
            tile_x += step_x
            tile_y += step_y
            t_max_x += t_delta_x
            t_max_y += t_delta_y
    return False

def _segment_aabb_fraction_values(start_x, start_y, delta_x, delta_y,
                                  left, top, right, bottom):
    entry_fraction = 0.0
    exit_fraction = 1.0
    for origin, delta, minimum, maximum in (
            (start_x, delta_x, left, right),
            (start_y, delta_y, top, bottom)):
        if abs(delta) <= 0.0000001:
            if origin < minimum or origin > maximum:
                return None
            continue
        first = (minimum - origin) / delta
        second = (maximum - origin) / delta
        if first > second:
            first, second = second, first
        entry_fraction = max(entry_fraction, first)
        exit_fraction = min(exit_fraction, second)
        if entry_fraction > exit_fraction:
            return None
    if exit_fraction < 0.0 or entry_fraction > 1.0:
        return None
    return max(0.0, min(1.0, entry_fraction))


def segment_aabb_intersection_fraction(start, end, rectangle):
    """Return the first [0, 1] fraction where a segment enters an AABB."""
    try:
        start_x, start_y = float(start["x"]), float(start["y"])
        delta_x = float(end["x"]) - start_x
        delta_y = float(end["y"]) - start_y
        left = float(rectangle["x"])
        top = float(rectangle["y"])
        right = left + float(rectangle["width"])
        bottom = top + float(rectangle["height"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if (not all(math.isfinite(value) for value in (
            start_x, start_y, delta_x, delta_y, left, top, right, bottom))
            or right < left or bottom < top):
        return None
    return _segment_aabb_fraction_values(
        start_x, start_y, delta_x, delta_y, left, top, right, bottom,
    )


def point_along_segment(start, end, fraction):
    fraction = max(0.0, min(1.0, float(fraction)))
    return {
        "x": float(start["x"]) + (float(end["x"]) - float(start["x"])) * fraction,
        "y": float(start["y"]) + (float(end["y"]) - float(start["y"])) * fraction,
    }


def get_redhead_bullet_hurtbox(entity, tile_map):
    """Build the authored body hurtbox in absolute world coordinates."""
    world_position = make_pos_abs(
        entity.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    authored = entity.get("bullet_hurtbox", {})
    if not isinstance(authored, dict):
        authored = {}
    offset = authored.get("offset", DEFAULT_REDHEAD_BULLET_HURTBOX["offset"])
    size = authored.get("size", DEFAULT_REDHEAD_BULLET_HURTBOX["size"])
    if not isinstance(offset, dict):
        offset = DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]
    if not isinstance(size, dict):
        size = DEFAULT_REDHEAD_BULLET_HURTBOX["size"]
    try:
        offset_x = float(offset.get("x", DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]["x"]))
        offset_y = float(offset.get("y", DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]["y"]))
        width = max(0.0, float(size.get("x", DEFAULT_REDHEAD_BULLET_HURTBOX["size"]["x"])))
        height = max(0.0, float(size.get("y", DEFAULT_REDHEAD_BULLET_HURTBOX["size"]["y"])))
    except (AttributeError, TypeError, ValueError, OverflowError):
        offset_x = DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]["x"]
        offset_y = DEFAULT_REDHEAD_BULLET_HURTBOX["offset"]["y"]
        width = DEFAULT_REDHEAD_BULLET_HURTBOX["size"]["x"]
        height = DEFAULT_REDHEAD_BULLET_HURTBOX["size"]["y"]
    return {
        "x": world_position["x"] + offset_x,
        "y": world_position["y"] + offset_y,
        "width": width,
        "height": height,
    }


def make_redhead_hurtbox_debug_item(entity, tile_map):
    """Describe the exact gameplay bullet hurtbox for debug rendering."""
    hurtbox = get_redhead_bullet_hurtbox(entity, tile_map)
    return {
        "type": "rectangle_outline",
        "drawing_function": draw_debug_rect_outline,
        "x": hurtbox["x"], "y": hurtbox["y"],
        "width": hurtbox["width"], "height": hurtbox["height"],
        "color": "YELLOW", "z_sort": 0,
        "debug_modes": ["collisions"],
    }


def get_entity_collision_center_offset(entity):
    authored = entity.get("collision_center_offset")
    if not isinstance(authored, dict):
        authored = (
            DEFAULT_REDHEAD_COLLISION_CENTER_OFFSET
            if entity.get("type") == "red head" else {"x": 0.0, "y": 0.0}
        )
    try:
        return {
            "x": float(authored.get("x", 0.0)),
            "y": float(authored.get("y", 0.0)),
        }
    except (AttributeError, TypeError, ValueError, OverflowError):
        return {"x": 0.0, "y": 0.0}


def offset_entity_position_for_collision(position, entity, tile_map):
    offset = get_entity_collision_center_offset(entity)
    result = new_pos_from_old(position)
    result["x"] += offset["x"]
    result["y"] += offset["y"]
    return move_position_along_tiles(
        result, tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )


def get_entity_collision_dimensions(entity):
    width = max(0.0, float(entity.get("entity_width", 0.0)))
    height = max(0.0, float(entity.get("entity_height", 0.0)))
    if entity.get("type") != "red head":
        return width, height
    try:
        radius_reduction = float(entity.get(
            "collision_radius_reduction",
            DEFAULT_REDHEAD_COLLISION_RADIUS_REDUCTION,
        ))
    except (TypeError, ValueError, OverflowError):
        radius_reduction = DEFAULT_REDHEAD_COLLISION_RADIUS_REDUCTION
    if not math.isfinite(radius_reduction):
        radius_reduction = DEFAULT_REDHEAD_COLLISION_RADIUS_REDUCTION
    radius_reduction = max(0.0, radius_reduction)
    return (
        max(0.0, width - radius_reduction * 2.0),
        max(0.0, height - radius_reduction * 2.0),
    )


def get_entity_collision_world_position(entity, tile_map, position=None):
    collision_position = offset_entity_position_for_collision(
        position if position is not None else entity.get("position", {}),
        entity, tile_map,
    )
    return make_pos_abs(
        collision_position,
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )


def get_redhead_attack_engage_distance(entity):
    """Return a threshold that remains inside the authored melee hit reach."""
    try:
        authored = float(entity.get(
            "attack_engage_distance", DEFAULT_REDHEAD_ATTACK_ENGAGE_DISTANCE,
        ))
    except (TypeError, ValueError, OverflowError):
        authored = DEFAULT_REDHEAD_ATTACK_ENGAGE_DISTANCE
    if not math.isfinite(authored):
        authored = DEFAULT_REDHEAD_ATTACK_ENGAGE_DISTANCE
    # The old authored value was 40 px, beyond the point where the current
    # swing test can connect. Scale the cap with the body size so custom-sized
    # redheads still enter attack only inside their real melee reach.
    maximum_hit_reach = max(
        0.0, float(entity.get("entity_width", 16.0)) + 12.0,
    )
    return min(max(0.0, authored), maximum_hit_reach)


def get_entity_collision_box(entity, tile_map, position=None):
    """Return the AABB used by wall and dynamic-entity collision."""
    collision_position = offset_entity_position_for_collision(
        position if position is not None else entity.get("position", {}),
        entity, tile_map,
    )
    center = make_pos_abs(
        collision_position,
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    width, height = get_entity_collision_dimensions(entity)
    return {
        "x": center["x"] - width * 0.5,
        "y": center["y"] - height * 0.5,
        "width": width,
        "height": height,
    }


def make_entity_collision_points(position, entity, tile_map):
    collision_position = offset_entity_position_for_collision(
        position, entity, tile_map,
    )
    width, height = get_entity_collision_dimensions(entity)
    return make_player_points(
        collision_position, width, height,
        tile_map["tile_width"], tile_map["tile_height"],
    )


def get_redhead_collision_box(entity, tile_map):
    return get_entity_collision_box(entity, tile_map)


def make_redhead_collision_debug_item(entity, tile_map):
    collision_box = get_entity_collision_box(entity, tile_map)
    return {
        "type": "rectangle_outline",
        "drawing_function": draw_debug_rect_outline,
        "x": collision_box["x"], "y": collision_box["y"],
        "width": collision_box["width"], "height": collision_box["height"],
        "color": "GREEN", "z_sort": 0,
        "debug_modes": ["player_debug"],
    }


def make_player_collision_debug_item(entity, tile_map):
    """Describe the player's authoritative movement collision AABB."""
    collision_box = get_entity_collision_box(entity, tile_map)
    return {
        "type": "rectangle_outline",
        "drawing_function": draw_debug_rect_outline,
        "x": collision_box["x"], "y": collision_box["y"],
        "width": collision_box["width"], "height": collision_box["height"],
        "color": "BLUE", "z_sort": 0,
        "debug_modes": ["player_debug"],
    }


def build_redhead_bullet_targets(brains, tile_map):
    targets = []
    for entity_id, entity in (brains or {}).items():
        if not isinstance(entity, dict) or entity.get("type") != "red head":
            continue
        hurtbox = get_redhead_bullet_hurtbox(entity, tile_map)
        targets.append({
            "entity_id": entity_id,
            "entity": entity,
            "hurtbox": hurtbox,
            "left": hurtbox["x"],
            "top": hurtbox["y"],
            "right": hurtbox["x"] + hurtbox["width"],
            "bottom": hurtbox["y"] + hurtbox["height"],
        })
    return targets


def find_first_redhead_bullet_hit(start, end, brains, tile_map,
                                  maximum_fraction=None,
                                  prepared_targets=None):
    """Return the nearest exact body hit strictly before a blocking wall."""
    closest = None
    limit = None if maximum_fraction is None else max(
        0.0, min(1.0, float(maximum_fraction)),
    )
    start_x, start_y = float(start["x"]), float(start["y"])
    delta_x = float(end["x"]) - start_x
    delta_y = float(end["y"]) - start_y
    segment_left = min(start_x, start_x + delta_x)
    segment_right = max(start_x, start_x + delta_x)
    segment_top = min(start_y, start_y + delta_y)
    segment_bottom = max(start_y, start_y + delta_y)
    targets = prepared_targets
    if targets is None:
        targets = build_redhead_bullet_targets(brains, tile_map)
    for target in targets:
        if (target["right"] < segment_left or target["left"] > segment_right
                or target["bottom"] < segment_top
                or target["top"] > segment_bottom):
            continue
        fraction = _segment_aabb_fraction_values(
            start_x, start_y, delta_x, delta_y,
            target["left"], target["top"], target["right"], target["bottom"],
        )
        if fraction is None or (limit is not None and fraction >= limit):
            continue
        entity_id = target["entity_id"]
        candidate_key = (fraction, str(entity_id))
        if closest is None or candidate_key < closest["sort_key"]:
            closest = {
                "sort_key": candidate_key,
                "fraction": fraction,
                "position": point_along_segment(start, end, fraction),
                "entity_id": entity_id,
                "entity": target["entity"],
                "hurtbox": target["hurtbox"],
            }
    if closest is not None:
        closest.pop("sort_key", None)
    return closest


def first_solid_tile_hit_on_segment(start, end, tile_map, step_size=2.0,
                                    debug_queue=None):
    """Return the first sampled physical-tile hit along a bullet segment."""
    start_tile = get_tile_index_and_offset_from_pos(start, tile_map)
    start_in_bounds = not tile_not_in_bounds(
        start_tile["tile_x"], start_tile["tile_y"], tile_map,
    )
    if start_in_bounds and position_collides_within_tile_shape(start_tile, tile_map):
        return {
            "fraction": 0.0,
            "position": dict(start),
            "tile_x": start_tile["tile_x"],
            "tile_y": start_tile["tile_y"],
        }
    delta = vec2_subtract(end, start)
    distance = vec2_norm(delta)
    if distance <= 0.0000001:
        return None
    direction = vec2_scale(delta, 1.0 / distance)
    step_size = max(0.25, float(step_size))
    sample_distance = min(step_size, distance)
    while sample_distance <= distance + 0.0000001:
        position = vec2_add(start, vec2_scale(direction, sample_distance))
        tile_position = get_tile_index_and_offset_from_pos(position, tile_map)
        in_bounds = not tile_not_in_bounds(
            tile_position["tile_x"], tile_position["tile_y"], tile_map,
        )
        collides = in_bounds and position_collides_within_tile_shape(
            tile_position, tile_map,
        )
        if debug_queue is not None and in_bounds:
            debug_queue.append({
                "type": "tile",
                "tile_x": tile_position["tile_x"],
                "tile_y": tile_position["tile_y"],
                "tile_width": tile_map.get("tile_width", 5),
                "tile_height": tile_map.get("tile_height", 5),
                "color": "PINK" if collides else "RED",
                "drawing_function": draw_debug_tile,
                "z_sort": 1,
                "debug_modes": ["line_of_sight"],
            })
        if collides:
            fraction = min(1.0, sample_distance / distance)
            return {
                "fraction": fraction,
                "position": point_along_segment(start, end, fraction),
                "tile_x": tile_position["tile_x"],
                "tile_y": tile_position["tile_y"],
            }
        if sample_distance >= distance:
            break
        sample_distance = min(distance, sample_distance + step_size)
    return None


def allocate_projectile_id(projectiles):
    numeric_ids = [key for key in (projectiles or {}) if isinstance(key, int)]
    return max(numeric_ids, default=-1) + 1


def tiles_equal(a, b):
    return a.get("tile_x",0) == b.get("tile_x",0) and a.get("tile_y",0) == b.get("tile_y",0)

def tiles_close(entity_position, waypoint_tile, target_offset, epsilon):
    if not tiles_equal(entity_position,  waypoint_tile):
        return False

    entity_local_position = {"x": entity_position.get("x", 0), "y": entity_position.get("y", 0)}

    return vec2_distance(entity_local_position, target_offset) < epsilon

def get_current_ai_waypoint_target_abs(entity, tile_map, arrival_epsilon=8.0):
    path = entity.get("path_to_player", [])

    if not path:
        collision_position = offset_entity_position_for_collision(
            entity["position"], entity, tile_map,
        )
        return (None, make_pos_abs(
            collision_position, tile_map["tile_width"], tile_map["tile_height"],
        ))

    path_index = entity.get("path_to_player_current_index", 0)

    # Keep len(path) as the existing "finished path"
    # sentinel, but use the final element as the actual target.
    waypoint_index = min(path_index, len(path) - 1)

    waypoint = path[waypoint_index]

    tile_target_offset = entity.get("current_tile_target_offset")

    if tile_target_offset is None:
        tile_target_offset = {"x": tile_map["tile_width"] / 2, "y": tile_map["tile_height"] / 2}
        entity["current_tile_target_offset"] = (tile_target_offset)

    collision_position = offset_entity_position_for_collision(
        entity["position"], entity, tile_map,
    )
    reached_waypoint = tiles_close(
        collision_position, waypoint, tile_target_offset, arrival_epsilon,
    )

    if reached_waypoint and path_index < len(path):
        path_index += 1

        entity["path_to_player_current_index"] = path_index

        waypoint_index = min(path_index, len(path) - 1)

        waypoint = path[waypoint_index]

    target_position_abs = (get_abs_pos_from_index_given_offset(waypoint, tile_target_offset, tile_map))

    return waypoint, target_position_abs


def make_entity_boundary_points(entity_pos, entity_width, entity_height, tile_width, tile_height, sub_divisions):
    subdivisions = max(1, int(sub_divisions))
    half_width = max(0.0, float(entity_width)) * 0.5
    half_height = max(0.0, float(entity_height)) * 0.5
    width = half_width * 2.0
    height = half_height * 2.0
    entity_points = {}

    def canonical(local_x, local_y):
        return move_position_along_tiles({
            "x": entity_pos.get("x", 0) + local_x,
            "y": entity_pos.get("y", 0) + local_y,
            "tile_x": entity_pos.get("tile_x", 0),
            "tile_y": entity_pos.get("tile_y", 0),
        }, tile_width, tile_height)

    for subdivision in range(subdivisions):
        progress = subdivision / subdivisions
        entity_points[f"top_{subdivision}"] = canonical(
            -half_width + width * progress, -half_height,
        )
        entity_points[f"right_{subdivision}"] = canonical(
            half_width, -half_height + height * progress,
        )
        entity_points[f"bottom_{subdivision}"] = canonical(
            half_width - width * progress, half_height,
        )
        entity_points[f"left_{subdivision}"] = canonical(
            -half_width, half_height - height * progress,
        )
    return entity_points

def make_player_points(player_pos, entity_width, entity_height, tile_width, tile_height):
    # TODO
    # not taking into account that the tiles will be different when adding width/height    
    # true if we think in terms of offset
    player_pos_top_left = {"x" : player_pos.get("x",0) - entity_width/2,
                            "y" : player_pos.get("y",0) - entity_height/2,
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_top_left = move_position_along_tiles(player_pos_top_left, tile_width, tile_height)

    player_pos_top_right = {"x" : player_pos.get("x",0) + entity_width/2,
                            "y" : player_pos.get("y",0) - entity_height/2,
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0)  
                            }
    
    player_pos_top_right = move_position_along_tiles(player_pos_top_right, tile_width, tile_height)
    

    
    player_pos_bottom_right = {"x" : player_pos.get("x",0) + entity_width/2,
                            "y" : player_pos.get("y",0) + entity_height/2,
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_right = move_position_along_tiles(player_pos_bottom_right, tile_width, tile_height)
    
    player_pos_bottom_left = {"x" : player_pos.get("x",0) - entity_width/2,
                            "y" : player_pos.get("y",0) + entity_height/2,
                            "tile_x" : player_pos.get("tile_x", 0),
                            "tile_y" : player_pos.get("tile_y", 0) 
                            }
    
    player_pos_bottom_left = move_position_along_tiles(player_pos_bottom_left, tile_width, tile_height)

    player_points = {
        "top_left" : player_pos_top_left,
        "top_right" : player_pos_top_right,
        "bottom_left" : player_pos_bottom_left,
        "bottom_right" : player_pos_bottom_right,
    }        
    
    return player_points

def remove_velocity_into_surface(velocity, normal):
    velocity_into_surface = vec2_dot(velocity, normal)

    
    if velocity_into_surface >= 0:
        return velocity

    return vec2_subtract(velocity, vec2_scale(normal, velocity_into_surface))

def check_collisions_on_tilemap(entity_id, player_points, new_pos_velocity, tile_map, dt, debug_queue=None):
    collisions = {
        "x": False,
        "y": False,
        "slope_normals": [],
    }

    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]

    for potential_pos in player_points.values():        
        candidate_x = new_pos_from_old(
            potential_pos
        )

        candidate_x["x"] += (
            new_pos_velocity["x"] * dt
        )

        candidate_x = move_position_along_tiles(
            candidate_x,
            tile_width,
            tile_height,
        )

        candidate_y = new_pos_from_old(
            potential_pos
        )

        candidate_y["y"] += (
            new_pos_velocity["y"] * dt
        )

        candidate_y = move_position_along_tiles(
            candidate_y,
            tile_width,
            tile_height,
        )

        
        # hitting something horizontally does not automatically
        # prevent vertical movement, and vice versa.
        if position_collides_within_tile_shape(
            candidate_x,
            tile_map,
        ):
            collisions["x"] = True

        if position_collides_within_tile_shape(
            candidate_y,
            tile_map,
        ):
            collisions["y"] = True

        
        # Combined movement for diagonal slope detection        

        candidate_combined = new_pos_from_old(
            potential_pos
        )

        candidate_combined["x"] += (
            new_pos_velocity["x"] * dt
        )

        candidate_combined["y"] += (
            new_pos_velocity["y"] * dt
        )

        candidate_combined = move_position_along_tiles(candidate_combined, tile_width, tile_height)

        combined_collision = get_tile_shape_collision(candidate_combined, tile_map)

        if not combined_collision["collides"]:
            continue

        shape_index = combined_collision["shape_index"]
        normal = combined_collision["normal"]

        if shape_index == 0 or normal is None:
            continue

        # The diagonal normal is appropriate when the point was
        # already in this tile's empty half and is now attempting
        # to cross the diagonal into its solid half.
        #
        # Entering a triangular tile through one of its outer
        # horizontal/vertical edges remains an ordinary X/Y hit.
        stayed_in_same_tile = (candidate_combined["tile_x"] == potential_pos["tile_x"] and candidate_combined["tile_y"] == potential_pos["tile_y"])

        started_colliding = (position_collides_within_tile_shape(potential_pos, tile_map))

        moving_into_diagonal = (vec2_dot(new_pos_velocity, normal) < 0)

        if (
            stayed_in_same_tile
            and not started_colliding
            and moving_into_diagonal
            and normal not in collisions["slope_normals"]
        ):
            collisions["slope_normals"].append(normal)

    return collisions

def is_legal_position_on_tilemap(player_points, tile_map, debug_queue = None):        
    for potential_pos in player_points.values():                    
        if position_collides_within_tile_shape(potential_pos, tile_map):
            return False        
    return True

def move_position_by_velocity(start_pos, velocity, dt, tile_width, tile_height):
    result = new_pos_from_old(start_pos)

    result["x"] += velocity["x"] * dt
    result["y"] += velocity["y"] * dt
    result["source"] = "ai"

    return move_position_along_tiles(result, tile_width, tile_height)

def vec2_move_towards(current, target, max_delta):
    delta = vec2_subtract(target, current)
    distance = vec2_norm(delta)

    if distance == 0 or distance <= max_delta:
        return {
            "x": target["x"],
            "y": target["y"],
        }

    movement = vec2_scale(delta, max_delta / distance)

    return vec2_add(current, movement)

def entity_position_is_legal(position, entity, tile_map, debug_queue=None,
                             collision_details=None):
    entity_points = make_entity_collision_points(position, entity, tile_map)

    if not is_legal_position_on_tilemap(entity_points, tile_map, debug_queue):
        if isinstance(collision_details, dict):
            collision_details["kind"] = "tile"
        return False

    collides_with_entity, actor_details = collides_within_tile_at_position(
        position, entity, tile_map, debug_queue,
    )
    if collides_with_entity and isinstance(collision_details, dict):
        collision_details.update(actor_details or {})
        collision_details["kind"] = "actor"

    return not collides_with_entity


def check_collision_on_tilemap(entity_id, potential_pos, new_pos_velocity, tile_map, dt, debug_queue = None):
    # TODO use this for any entity but only for walls
    collisions = { "x" : False, "y" : False}
    
    new_pos_x_direction = new_pos_from_old(potential_pos)
    new_pos_y_direction = new_pos_from_old(potential_pos)

    new_pos_x_direction['x'] += new_pos_velocity['x'] * dt

    new_pos_y_direction['y'] += new_pos_velocity['y'] * dt

    # these need to be adjusted!!!!
    collision_x = get_tile_shape_collision(new_pos_x_direction, tile_map)
    collision_y = get_tile_shape_collision(new_pos_y_direction, tile_map)


    if collision_x["collides"]:
        collisions["x"] = True
    if collision_y["collides"]:
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



def collides_within_tile(new_entity_pos, entity_id, tile_map, debug_queue = None):    
    new_tile_index = get_flat_tile_index(new_entity_pos["tile_x"], new_entity_pos["tile_y"], tile_map, debug_queue)
    new_tile = tile_map["tiles"][new_tile_index]
    if "current_entities" not in new_tile:
        new_tile["current_entities"] = {}
        return False
    
    entity_radius_for_now = 10
    
    for entity_key, entity_val in new_tile["current_entities"].items():
        if entity_key != entity_id:            
            
            minkowski_rect = {
                "x" : entity_val["x"] - 24,
                "y" : entity_val["y"] - 24,
                "width" : 48, # TODO tweak this, test idea first
                "height" : 48
            }

            if point_in_rect(new_entity_pos, minkowski_rect):
                return True
    return False

def aabbs_overlap(first, second):
    return (
        first["x"] < second["x"] + second["width"]
        and first["x"] + first["width"] > second["x"]
        and first["y"] < second["y"] + second["height"]
        and first["y"] + first["height"] > second["y"]
    )


def actor_passthrough_pair_key(first_id, second_id):
    if first_id == second_id:
        return None
    return tuple(sorted(
        (first_id, second_id),
        key=lambda value: (type(value).__name__, str(value)),
    ))


def get_actor_passthrough_runtime(tile_map):
    runtime = tile_map.get("_actor_passthrough_runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        tile_map["_actor_passthrough_runtime"] = runtime
    if not isinstance(runtime.get("pending"), dict):
        runtime["pending"] = {}
    if not isinstance(runtime.get("pairs"), dict):
        runtime["pairs"] = {}
    return runtime


def actor_passthrough_pair_record(tile_map, first_id, second_id):
    pair_key = actor_passthrough_pair_key(first_id, second_id)
    if pair_key is None:
        return None
    return get_actor_passthrough_runtime(tile_map)["pairs"].get(pair_key)


def actor_passthrough_pair_is_active(tile_map, first_id, second_id):
    return actor_passthrough_pair_record(
        tile_map, first_id, second_id,
    ) is not None


def begin_actor_passthrough_pair(entity, blocker_details, tile_map):
    entity_id = entity.get("id")
    other_id = blocker_details.get("entity_id")
    pair_key = actor_passthrough_pair_key(entity_id, other_id)
    if pair_key is None:
        return
    boxes = {
        entity_id: get_entity_collision_box(entity, tile_map),
        other_id: dict(blocker_details.get("collision_box", {})),
    }
    get_actor_passthrough_runtime(tile_map)["pairs"][pair_key] = {
        "ids": pair_key,
        "boxes": boxes,
        "crossing_started": False,
        "unused_timer": 0.0,
    }


def note_redhead_actor_block(entity, blocker_details, tile_map, dt):
    runtime = get_actor_passthrough_runtime(tile_map)
    entity_id = entity.get("id")
    blocker_id = (
        blocker_details.get("entity_id")
        if isinstance(blocker_details, dict) else None
    )
    if (entity.get("type") != "red head"
            or not isinstance(blocker_details, dict)
            or blocker_details.get("entity_type") != "red head"
            or entity_id is None or blocker_id is None
            or blocker_id == entity_id):
        runtime["pending"].pop(entity_id, None)
        return

    other_id = blocker_id
    pending = runtime["pending"].get(entity_id)
    if not isinstance(pending, dict) or pending.get("other_id") != other_id:
        pending = {"other_id": other_id, "duration": 0.0}
        runtime["pending"][entity_id] = pending
    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0
    pending["duration"] = max(
        0.0, float(pending.get("duration", 0.0)),
    ) + frame_dt
    if pending["duration"] >= DEFAULT_REDHEAD_ACTOR_BLOCK_DELAY:
        begin_actor_passthrough_pair(entity, blocker_details, tile_map)
        runtime["pending"].pop(entity_id, None)


def clear_redhead_actor_block(entity, tile_map):
    get_actor_passthrough_runtime(tile_map)["pending"].pop(
        entity.get("id"), None,
    )


def mark_actor_passthrough_crossing(tile_map, first_id, second_id):
    pair = actor_passthrough_pair_record(tile_map, first_id, second_id)
    if pair is not None:
        pair["crossing_started"] = True
        pair["unused_timer"] = 0.0


def update_actor_passthrough_box(tile_map, entity_id, collision_box):
    runtime = get_actor_passthrough_runtime(tile_map)
    for pair_key, pair in list(runtime["pairs"].items()):
        if entity_id not in pair.get("ids", ()):
            continue
        if collision_box is None:
            runtime["pairs"].pop(pair_key, None)
            continue
        pair.setdefault("boxes", {})[entity_id] = dict(collision_box)
        first_id, second_id = pair["ids"]
        first_box = pair["boxes"].get(first_id)
        second_box = pair["boxes"].get(second_id)
        if (pair.get("crossing_started")
                and isinstance(first_box, dict)
                and isinstance(second_box, dict)
                and not aabbs_overlap(first_box, second_box)):
            runtime["pairs"].pop(pair_key, None)


def update_actor_passthrough_runtime(tile_map, live_redhead_ids, dt):
    runtime = get_actor_passthrough_runtime(tile_map)
    live_ids = set(live_redhead_ids)
    for entity_id in list(runtime["pending"]):
        pending = runtime["pending"].get(entity_id, {})
        if (entity_id not in live_ids
                or pending.get("other_id") not in live_ids):
            runtime["pending"].pop(entity_id, None)
    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0
    for pair_key, pair in list(runtime["pairs"].items()):
        if any(entity_id not in live_ids for entity_id in pair.get("ids", ())):
            runtime["pairs"].pop(pair_key, None)
            continue
        if not pair.get("crossing_started"):
            pair["unused_timer"] = max(
                0.0, float(pair.get("unused_timer", 0.0)),
            ) + frame_dt
            if pair["unused_timer"] >= DEFAULT_REDHEAD_PASSTHROUGH_UNUSED_TIMEOUT:
                runtime["pairs"].pop(pair_key, None)


def make_entity_collision_record(entity, tile_map, position=None):
    position = position if position is not None else entity.get("position", {})
    record = copy_position_dict(position)
    record["entity_type"] = entity.get("type", "player" if entity.get("id") == "player" else "")
    record["entity_width"] = float(entity.get("entity_width", 0.0))
    record["entity_height"] = float(entity.get("entity_height", 0.0))
    record["collision_center_offset"] = get_entity_collision_center_offset(entity)
    record["collision_box"] = get_entity_collision_box(
        entity, tile_map, position=position,
    )
    return record


def collision_box_from_record(record, other_entity_id, tile_map):
    collision_box = record.get("collision_box")
    if isinstance(collision_box, dict):
        return collision_box
    # Compatibility for stale/saved spatial-index records. The index is
    # rebuilt with complete records at the start of the next gameplay frame.
    fallback = {
        "id": other_entity_id,
        "type": record.get("entity_type", ""),
        "position": record,
        "entity_width": record.get(
            "entity_width", 12.0 if other_entity_id == "player" else 16.0,
        ),
        "entity_height": record.get(
            "entity_height", 12.0 if other_entity_id == "player" else 16.0,
        ),
    }
    if isinstance(record.get("collision_center_offset"), dict):
        fallback["collision_center_offset"] = record["collision_center_offset"]
    elif other_entity_id != "player":
        fallback["type"] = "red head"
    return get_entity_collision_box(fallback, tile_map)


def collides_within_tile_at_position(new_entity_pos, entity, tile_map,
                                     debug_queue=None):
    collision_position = offset_entity_position_for_collision(
        new_entity_pos, entity, tile_map,
    )
    tile_x = collision_position["tile_x"]
    tile_y = collision_position["tile_y"]

    if tile_not_in_bounds(tile_x, tile_y, tile_map):
        return True, None

    entity_id = entity.get("id")
    moving_box = get_entity_collision_box(
        entity, tile_map, position=new_entity_pos,
    )

    tile_index = get_flat_tile_index(tile_x, tile_y, tile_map, debug_queue)

    current_tile = tile_map["tiles"][tile_index]

    tiles_to_check = [current_tile]

    for neighbour in current_tile["neighbours"].values():
        neighbour_index = get_flat_tile_index(neighbour["tile_x"], neighbour["tile_y"], tile_map, debug_queue)

        tiles_to_check.append(tile_map["tiles"][neighbour_index])

    for tile in tiles_to_check:
        for (other_entity_id, other_entity_record) in tile.get("current_entities", {}).items():

            if other_entity_id == entity_id:
                continue

            other_box = collision_box_from_record(
                other_entity_record, other_entity_id, tile_map,
            )
            if aabbs_overlap(moving_box, other_box):
                if actor_passthrough_pair_is_active(
                        tile_map, entity_id, other_entity_id):
                    mark_actor_passthrough_crossing(
                        tile_map, entity_id, other_entity_id,
                    )
                    continue
                return (True, {
                    "entity_id": other_entity_id,
                    "entity_type": other_entity_record.get(
                        "entity_type", "",
                    ),
                    "collision_box": other_box,
                })

    return False, None




def collides_within_tiles_at_position_circle(new_entity_pos, entity_id, tile_map, debug_queue = None):    
    new_tile_index = get_flat_tile_index(new_entity_pos["tile_x"], new_entity_pos["tile_y"], tile_map, debug_queue)
    new_tile = tile_map["tiles"][new_tile_index]
    if "current_entities" not in new_tile:
        new_tile["current_entities"] = {}
        return False, None
    
    entity_radius_for_now = 60

    # the actual issue here is we're only checking a single tile so
    # we never hit the ones on the border

    

    new_pos_abs = tile_and_offset_to_absolute(tile_map, new_entity_pos)
    
    for entity_key, entity_val in new_tile["current_entities"].items():
        if entity_key != entity_id:            
            
            entity_pos_abs = tile_and_offset_to_absolute(tile_map, entity_val)

            minkowski_circle = {
                "x" : entity_pos_abs["x"],
                "y" : entity_pos_abs["y"],
                "radius" : entity_radius_for_now, # TODO tweak this, test idea first                
            }

            if point_in_circle(new_pos_abs, minkowski_circle):
                return True,  entity_pos_abs
    
    for neighbour in new_tile["neighbours"].values():
        neighbour_tile_index = get_flat_tile_index(neighbour["tile_x"], neighbour["tile_y"], tile_map, debug_queue)
        neighbour_tile = tile_map["tiles"][neighbour_tile_index]
        for entity_key, entity_val in neighbour_tile.get("current_entities",{}).items():
            if entity_key != entity_id:     
                entity_pos_abs = tile_and_offset_to_absolute(tile_map, entity_val)

                minkowski_circle = {
                    "x" : entity_pos_abs["x"],
                    "y" : entity_pos_abs["y"],
                    "radius" : entity_radius_for_now, # TODO tweak this, test idea first                
                }

                if point_in_circle(new_pos_abs, minkowski_circle):
                    return True, entity_pos_abs                                       


    return False, None


def point_in_circle(point, circle):
    return (point["x"] - circle["x"]) ** 2 + (point["y"] - circle["y"]) ** 2  <= circle["radius"]**2


def update_tile_manager(old_entity_pos, new_entity_pos, entity_id, tile_map,
                        debug_queue=None, remove_only=False, entity=None):
    old_index_position = (
        offset_entity_position_for_collision(old_entity_pos, entity, tile_map)
        if entity is not None else old_entity_pos
    )
    new_index_position = (
        offset_entity_position_for_collision(new_entity_pos, entity, tile_map)
        if entity is not None else new_entity_pos
    )
    old_x = old_index_position["tile_x"]
    old_y = old_index_position["tile_y"]
    if not tile_not_in_bounds(old_x, old_y, tile_map):
        old_tile_index = get_flat_tile_index(
            old_x, old_y, tile_map, debug_queue,
        )
        old_entities = tile_map["tiles"][old_tile_index].get(
            "current_entities", {},
        )
        old_entities.pop(entity_id, None)

    new_x = new_index_position["tile_x"]
    new_y = new_index_position["tile_y"]
    if tile_not_in_bounds(new_x, new_y, tile_map):
        update_actor_passthrough_box(tile_map, entity_id, None)
        return

    new_tile_index = get_flat_tile_index(
        new_x, new_y, tile_map, debug_queue,
    )
    new_entities = tile_map["tiles"][new_tile_index].setdefault(
        "current_entities", {},
    )
    if remove_only:
        new_entities.pop(entity_id, None)
        update_actor_passthrough_box(tile_map, entity_id, None)
        return
    collision_record = (
        make_entity_collision_record(entity, tile_map, new_entity_pos)
        if entity is not None else copy_position_dict(new_entity_pos)
    )
    new_entities[entity_id] = collision_record
    update_actor_passthrough_box(
        tile_map, entity_id, collision_record.get("collision_box"),
    )


def rebuild_actor_collision_index(tile_map, player_info, entities):
    """Rebuild derived actor AABBs so stationary and loaded actors collide."""
    for tile in tile_map.get("tiles", []):
        tile.pop("current_entities", None)
    actors = []
    if isinstance(player_info, dict):
        actors.append(player_info)
    for actor in (entities or {}).get("brains", {}).values():
        if (isinstance(actor, dict) and actor.get("type") == "red head"
                and actor.get("current_state") != "dead"):
            actors.append(actor)
    for actor in actors:
        position = actor.get("position", {})
        index_position = offset_entity_position_for_collision(
            position, actor, tile_map,
        )
        if tile_not_in_bounds(
                index_position["tile_x"], index_position["tile_y"], tile_map):
            continue
        tile_index = get_flat_tile_index(
            index_position["tile_x"], index_position["tile_y"], tile_map,
        )
        tile_map["tiles"][tile_index].setdefault("current_entities", {})[
            actor.get("id")
        ] = make_entity_collision_record(actor, tile_map, position)
        update_actor_passthrough_box(
            tile_map, actor.get("id"),
            get_entity_collision_box(actor, tile_map, position),
        )


def actor_collision_index_signature(tile_map, player_info, entities):
    """Identify changes that require a full actor-index rebuild.

    Normal movement maintains the index incrementally. Only a new world/player,
    or a change to the live redhead set, requires scanning the entire tile map.
    """
    live_redheads = tuple(sorted(
        (str(entity_id), id(entity))
        for entity_id, entity in (entities or {}).get("brains", {}).items()
        if (isinstance(entity, dict) and entity.get("type") == "red head"
            and entity.get("current_state") != "dead")
    ))
    return (
        id(tile_map), id(player_info), id(entities), live_redheads,
    )

    
def vec2_rotate_by(vec, amount): #in degrees
    angle = angle_from_vector(vec)
    result = vector_from_angle(angle + amount)
    return result

def move_redhead_with_locomotion(entity, desired_direction, tile_map,
                                  debug_queue, dt, desired_speed=None,
                                  speed_multiplier=1.0):
    """Move a redhead using its shared, persistent locomotion velocity."""
    settings = get_redhead_movement_settings(entity)
    try:
        speed_multiplier = float(speed_multiplier)
    except (TypeError, ValueError, OverflowError):
        speed_multiplier = 1.0
    if not math.isfinite(speed_multiplier):
        speed_multiplier = 1.0
    maximum_speed = settings["max_speed"] * max(0.0, speed_multiplier)

    direction = vec2_normalize(desired_direction)
    if vec2_norm(direction) <= 0.000001 or maximum_speed <= 0.0:
        target_velocity = {"x": 0.0, "y": 0.0}
    else:
        if desired_speed is None:
            target_speed = maximum_speed
        else:
            try:
                target_speed = float(desired_speed)
            except (TypeError, ValueError, OverflowError):
                target_speed = maximum_speed
            if not math.isfinite(target_speed):
                target_speed = maximum_speed
            target_speed = max(0.0, min(maximum_speed, target_speed))
        target_velocity = vec2_scale(direction, target_speed)

    authored_velocity = entity.get("ai_velocity", {})
    if not isinstance(authored_velocity, dict):
        authored_velocity = {}

    def velocity_component(name):
        try:
            component = float(authored_velocity.get(name, 0.0))
        except (TypeError, ValueError, OverflowError):
            component = 0.0
        return component if math.isfinite(component) else 0.0

    ai_velocity = {
        "x": velocity_component("x"),
        "y": velocity_component("y"),
    }
    current_speed = vec2_norm(ai_velocity)
    target_speed = vec2_norm(target_velocity)
    if target_speed <= 0.000001:
        acceleration = settings["deceleration"]
    elif (current_speed > 0.000001
            and vec2_dot(ai_velocity, target_velocity) < 0.0):
        acceleration = settings["reverse_acceleration"]
    elif target_speed < current_speed:
        acceleration = settings["deceleration"]
    else:
        acceleration = settings["acceleration"]

    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0
    ai_velocity = vec2_move_towards(
        ai_velocity, target_velocity, acceleration * frame_dt,
    )

    # Collision resolution mutates this velocity so blocked components stay
    # removed from the persistent locomotion state on the next frame.
    new_entity_position = move_entity_with_velocity(
        entity, ai_velocity, tile_map, debug_queue, frame_dt,
    )
    entity["ai_velocity"] = ai_velocity
    return new_entity_position


def move_entity_towards_target_abs(entity, target_position, tile_map,
                                   debug_queue, dt, arrival_radius=None,
                                   speed_multiplier=1.0):
    """Target adapter for the shared redhead locomotion implementation."""
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    settings = get_redhead_movement_settings(entity)
    if arrival_radius is None:
        arrival_radius = settings["arrival_radius"]
    else:
        try:
            arrival_radius = max(0.0, float(arrival_radius))
        except (TypeError, ValueError, OverflowError):
            arrival_radius = settings["arrival_radius"]

    collision_position = offset_entity_position_for_collision(
        entity["position"], entity, tile_map,
    )
    entity_position_abs = make_pos_abs(
        collision_position, tile_width, tile_height,
    )
    vector_to_target = vec2_subtract(target_position, entity_position_abs)
    distance_to_target = vec2_norm(vector_to_target)
    remaining_distance = max(0.0, distance_to_target - arrival_radius)
    direction = (
        vec2_normalize(vector_to_target)
        if remaining_distance > 0.000001
        else {"x": 0.0, "y": 0.0}
    )

    maximum_speed = settings["max_speed"] * max(0.0, speed_multiplier)
    if settings["deceleration"] > 0.0:
        # v^2 = 2as: begin slowing early enough to arrive without oscillating.
        arrival_speed = math.sqrt(
            2.0 * settings["deceleration"] * remaining_distance,
        )
        desired_speed = min(maximum_speed, arrival_speed)
    else:
        desired_speed = maximum_speed if remaining_distance > 0.0 else 0.0

    return move_redhead_with_locomotion(
        entity, direction, tile_map, debug_queue, dt,
        desired_speed=desired_speed, speed_multiplier=speed_multiplier,
    )


def move_entity_with_velocity(entity, new_entity_velocity, tile_map, debug_queue, dt):
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]

    start_pos = new_pos_from_old(entity["position"])

    if vec2_norm(new_entity_velocity) > 0:
        entity["sight_angle"] = angle_from_vector(vec2_normalize(new_entity_velocity))

    # Record the starting position for the tile manager.
    if "old_tile" not in entity:
        entity["old_tile"] = {}

    entity["old_tile"]["tile_x"] = start_pos["tile_x"]
    entity["old_tile"]["tile_y"] = start_pos["tile_y"]
    entity["old_tile"]["x"] = start_pos["x"]
    entity["old_tile"]["y"] = start_pos["y"]

    # Work on a local copy. At the end we copy the resolved
    # components back into the supplied velocity dictionary.
    resolved_velocity = {
        "x": new_entity_velocity["x"],
        "y": new_entity_velocity["y"],
    }
    actor_blockers = {}

    def remember_actor_block(collision_details, blocked_weight):
        if (not isinstance(collision_details, dict)
                or collision_details.get("kind") != "actor"):
            return
        blocker_id = collision_details.get("entity_id")
        if blocker_id is None:
            return
        current = actor_blockers.get(blocker_id)
        if current is None or blocked_weight > current[0]:
            actor_blockers[blocker_id] = (
                blocked_weight, dict(collision_details),
            )

    start_points = make_entity_collision_points(start_pos, entity, tile_map)

    initial_collisions = check_collisions_on_tilemap(entity.get("id"), start_points, resolved_velocity, tile_map, dt, debug_queue)

    # Remove only the parts of velocity directed into
    # diagonal slope faces.
    for slope_normal in initial_collisions["slope_normals"]:
        resolved_velocity = (remove_velocity_into_surface(resolved_velocity, slope_normal))
    
    combined_candidate = move_position_by_velocity(
        start_pos,
        resolved_velocity,
        dt,
        tile_width,
        tile_height,
    )

    if entity_position_is_legal(combined_candidate, entity, tile_map, debug_queue):
        new_entity_position = combined_candidate
    else:
        # Fall back to ordinary axis-separated movement. 

        new_entity_position = new_pos_from_old(start_pos)
        
        x_velocity = {
            "x": resolved_velocity["x"],
            "y": 0,
        }

        x_candidate = move_position_by_velocity(new_entity_position, x_velocity, dt, tile_width, tile_height)

        x_collision = {}
        if entity_position_is_legal(
                x_candidate, entity, tile_map, debug_queue, x_collision):
            new_entity_position = x_candidate
        else:
            remember_actor_block(x_collision, abs(resolved_velocity["x"]))
            resolved_velocity["x"] = 0
        
        y_velocity = {
            "x": 0,
            "y": resolved_velocity["y"],
        }

        y_candidate = move_position_by_velocity(new_entity_position, y_velocity, dt, tile_width, tile_height)

        y_collision = {}
        if entity_position_is_legal(
                y_candidate, entity, tile_map, debug_queue, y_collision):
            new_entity_position = y_candidate
        else:
            remember_actor_block(y_collision, abs(resolved_velocity["y"]))
            resolved_velocity["y"] = 0

    if actor_blockers:
        _weight, blocker_details = max(
            actor_blockers.values(), key=lambda item: item[0],
        )
        note_redhead_actor_block(entity, blocker_details, tile_map, dt)
    else:
        clear_redhead_actor_block(entity, tile_map)

    
    # Last-resort invariant check    

    final_points = make_entity_collision_points(
        new_entity_position, entity, tile_map,
    )

    if not is_legal_position_on_tilemap(final_points, tile_map, debug_queue):
        print("doing super safe fallback rejection!")

        new_entity_position = new_pos_from_old(
            start_pos
        )

        resolved_velocity["x"] = 0
        resolved_velocity["y"] = 0
    
    # Mutating it stops the next frame from immediately pushing
    # back into the blocked wall.
    new_entity_velocity["x"] = resolved_velocity["x"]
    new_entity_velocity["y"] = resolved_velocity["y"]

    update_tile_manager(
        entity["old_tile"], new_entity_position, entity["id"], tile_map,
        entity=entity,
    )

    entity["current_speed"] = vec2_norm(resolved_velocity)

    if entity["current_speed"] > 0:
        motion_angle = angle_from_vector(resolved_velocity)

        animation_direction = direction_from_angle(motion_angle)

        entity["animation_frame"] = (animation_frame_number_from_direction(animation_direction))

    return new_entity_position




def make_pos_abs(pos, tile_width, tile_height):
    pos_abs = { "x" : pos.get("x",0) + pos.get("tile_x",0) * tile_width,
                          "y" : pos.get("y",0) + pos.get("tile_y",0) * tile_height}
    
    return pos_abs


def reset_redhead_attack_cycle(entity):
    entity["attack_timer"] = 0.0
    entity["attack_substate"] = "windup"
    entity["attack_out_of_range_timer"] = 0.0


def get_redhead_movement_settings(entity):
    """Return safe locomotion values without mutating authored entity data."""
    authored = entity.get("movement_settings", {})
    if not isinstance(authored, dict):
        authored = {}

    legacy_fields = {
        "max_speed": "speed",
        "acceleration": "acceleration",
        "reverse_acceleration": "reverse_acceleration",
        "arrival_radius": "arrival_radius",
    }

    def value(name):
        if name in authored:
            raw_value = authored[name]
        elif name in legacy_fields and legacy_fields[name] in entity:
            raw_value = entity[legacy_fields[name]]
        elif name == "evade_speed_multiplier":
            evade_settings = entity.get("evade_settings", {})
            raw_value = (
                evade_settings.get("speed_multiplier")
                if isinstance(evade_settings, dict)
                and "speed_multiplier" in evade_settings
                else REDHEAD_MOVEMENT_DEFAULTS[name]
            )
        else:
            raw_value = REDHEAD_MOVEMENT_DEFAULTS[name]
        try:
            result = float(raw_value)
        except (TypeError, ValueError, OverflowError):
            result = float(REDHEAD_MOVEMENT_DEFAULTS[name])
        if not math.isfinite(result):
            result = float(REDHEAD_MOVEMENT_DEFAULTS[name])
        return result

    return {
        "max_speed": max(0.0, value("max_speed")),
        "acceleration": max(0.0, value("acceleration")),
        "deceleration": max(0.0, value("deceleration")),
        "reverse_acceleration": max(0.0, value("reverse_acceleration")),
        "arrival_radius": max(0.0, value("arrival_radius")),
        "evade_speed_multiplier": max(
            0.0, value("evade_speed_multiplier"),
        ),
    }


def ensure_redhead_movement_settings(entity):
    """Migrate legacy locomotion fields to the serialisable authored profile."""
    settings = get_redhead_movement_settings(entity)
    entity["movement_settings"] = settings
    return settings


def get_redhead_perception_settings(entity):
    """Return safe authored perception timing without mutating the entity."""
    authored = entity.get("perception_settings", {})
    if not isinstance(authored, dict):
        authored = {}
    def value(name):
        try:
            result = float(authored.get(name, REDHEAD_PERCEPTION_DEFAULTS[name]))
        except (TypeError, ValueError, OverflowError):
            result = float(REDHEAD_PERCEPTION_DEFAULTS[name])
        if not math.isfinite(result):
            result = float(REDHEAD_PERCEPTION_DEFAULTS[name])
        return result

    return {
        "line_of_sight_checks_per_second": max(
            0.25, min(60.0, value("line_of_sight_checks_per_second")),
        ),
        "flashlight_checks_per_second": max(
            1.0, min(60.0, value("flashlight_checks_per_second")),
        ),
        "flashlight_notice_duration": max(
            0.0, min(5.0, value("flashlight_notice_duration")),
        ),
        "flashlight_intensity_threshold": max(
            0.0, min(10.0, value("flashlight_intensity_threshold")),
        ),
        "light_startle_duration": max(
            0.0, min(2.0, value("light_startle_duration")),
        ),
        "ally_alert_radius_tiles": max(
            0.0, min(16.0, value("ally_alert_radius_tiles")),
        ),
    }


def ensure_redhead_perception_settings(entity):
    settings = get_redhead_perception_settings(entity)
    entity["perception_settings"] = settings
    return settings


def get_redhead_hearing_settings(entity):
    """Return safe, independently authored AI hearing values."""
    authored = entity.get("hearing_settings", {})
    if not isinstance(authored, dict):
        authored = {}

    def value(name):
        try:
            result = float(authored.get(name, REDHEAD_HEARING_DEFAULTS[name]))
        except (TypeError, ValueError, OverflowError):
            result = float(REDHEAD_HEARING_DEFAULTS[name])
        if not math.isfinite(result):
            result = float(REDHEAD_HEARING_DEFAULTS[name])
        return result

    startle_threshold = max(0.0, value("startle_threshold"))
    chase_threshold = max(
        startle_threshold, value("chase_threshold"),
    )
    return {
        "gunshot_radius_tiles": max(
            0.0, min(64.0, value("gunshot_radius_tiles")),
        ),
        "walk_footstep_radius_tiles": max(
            0.0, min(32.0, value("walk_footstep_radius_tiles")),
        ),
        "run_footstep_radius_tiles": max(
            0.0, min(32.0, value("run_footstep_radius_tiles")),
        ),
        "walk_footstep_contribution": max(
            0.0, min(10.0, value("walk_footstep_contribution")),
        ),
        "run_footstep_contribution": max(
            0.0, min(10.0, value("run_footstep_contribution")),
        ),
        "startle_threshold": startle_threshold,
        "chase_threshold": chase_threshold,
        "silence_reset_seconds": max(
            0.0, min(120.0, value("silence_reset_seconds")),
        ),
    }


def ensure_redhead_hearing_settings(entity):
    settings = get_redhead_hearing_settings(entity)
    entity["hearing_settings"] = settings
    return settings


def _redhead_perception_phase(entity):
    """Return a stable 0..1 phase used to spread checks between enemies."""
    identifier = str(entity.get("id", "0"))
    phase_hash = 2166136261
    for character in identifier:
        phase_hash ^= ord(character)
        phase_hash = (phase_hash * 16777619) & 0xFFFFFFFF
    # Avalanche adjacent integer-like IDs across the full interval.
    phase_hash ^= phase_hash >> 16
    phase_hash = (phase_hash * 0x7FEB352D) & 0xFFFFFFFF
    phase_hash ^= phase_hash >> 15
    phase_hash = (phase_hash * 0x846CA68B) & 0xFFFFFFFF
    phase_hash ^= phase_hash >> 16
    return phase_hash / 4294967296.0


def sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt,
        include_direct_movement=False, force=False):
    """Return cached LOS data, refreshing expensive rays at the authored rate.

    The direct-movement corridor query shares the same cadence as LOS while in
    chase. A forced sample is reserved for moments that require a fresh answer,
    such as the end of the noticing/startle period.
    """
    settings = get_redhead_perception_settings(entity)
    interval = 1.0 / settings["line_of_sight_checks_per_second"]
    cache = entity.get("perception_runtime")
    if not isinstance(cache, dict):
        cache = {}
        entity["perception_runtime"] = cache

    try:
        elapsed = float(cache.get("elapsed", 0.0))
    except (TypeError, ValueError, OverflowError):
        elapsed = 0.0
    if not math.isfinite(elapsed):
        elapsed = 0.0
    elapsed += max(0.0, dt)
    geometry_revision = int(tile_map.get("geometry_revision", 0))
    source_identity = id(tile_map)
    source_changed = (
        cache.get("tile_map_identity") != source_identity
        or int(cache.get("geometry_revision", -1)) != geometry_revision
    )
    first_sample = not bool(cache.get("valid", False))
    sample_due = (
        force or first_sample or source_changed
        or elapsed + 0.000001 >= interval
    )

    if sample_due:
        can_see, seen_position = alice_can_see_bob_points(
            entity, player_info, tile_map, debug_queue,
        )
        cached_seen_position = (
            copy_entity_pos(seen_position)
            if can_see and isinstance(seen_position, dict)
            else None
        )
        cache.update({
            "valid": True,
            "can_see": bool(can_see),
            "seen_position": cached_seen_position,
            "direct_movement_valid": False,
            "can_move_directly": False,
            "tile_map_identity": source_identity,
            "geometry_revision": geometry_revision,
            "sample_count": int(cache.get("sample_count", 0)) + 1,
        })
        if first_sample and not force:
            # The initial answer is immediate; subsequent samples are phased so
            # a crowd does not keep producing one synchronized 250 ms spike.
            cache["elapsed"] = -interval * _redhead_perception_phase(entity)
        elif force:
            cache["elapsed"] = 0.0
        else:
            # The epsilon in the due test handles floating-point frame sums;
            # do not preserve a just-under-interval remainder or it would
            # trigger a duplicate sample on the following frame.
            cache["elapsed"] = (
                elapsed % interval if elapsed >= interval else 0.0
            )
    else:
        cache["elapsed"] = elapsed

    if include_direct_movement and not cache.get(
            "direct_movement_valid", False):
        cache["can_move_directly"] = bool(
            cache.get("can_see", False)
            and alice_can_move_to_bob(
                entity, player_info, tile_map, debug_queue,
            )
        )
        cache["direct_movement_valid"] = True

    seen_position = cache.get("seen_position")
    return (
        bool(cache.get("can_see", False)),
        copy_entity_pos(seen_position)
        if isinstance(seen_position, dict) else None,
        bool(cache.get("can_move_directly", False))
        if include_direct_movement else False,
    )


def face_redhead_towards_world_position(entity, world_position, tile_map):
    entity_world = make_pos_abs(
        entity.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    direction = vec2_normalize(vec2_subtract(world_position, entity_world))
    if vec2_norm(direction) <= 0.000001:
        return False
    entity["sight_angle"] = angle_from_vector(direction) % 360.0
    animation_direction = direction_from_angle(entity["sight_angle"])
    entity["animation_frame"] = animation_frame_number_from_direction(
        animation_direction,
    )
    return True


def queue_redhead_awareness_stimulus(
        entity, stimulus_type, source_world_position, tile_map, strength=1.0):
    """Queue one generic awareness event for idle-state consumption.

    Sound can use this same entry point later; state-machine code does not need
    to care whether the thing that made the redhead turn was light or audio.
    """
    if not isinstance(source_world_position, dict):
        return False
    source = {
        "x": float(source_world_position.get("x", 0.0)),
        "y": float(source_world_position.get("y", 0.0)),
    }
    face_redhead_towards_world_position(entity, source, tile_map)
    entity["pending_awareness_stimulus"] = {
        "type": str(stimulus_type),
        "source_world_position": source,
        "strength": max(0.0, float(strength)),
    }
    return True


def get_redhead_sound_awareness(entity):
    state = entity.get("sound_awareness")
    if not isinstance(state, dict):
        state = {}
        entity["sound_awareness"] = state
    try:
        accumulator = max(0.0, float(state.get("accumulator", 0.0)))
        silence_timer = max(0.0, float(state.get("silence_timer", 0.0)))
    except (TypeError, ValueError, OverflowError):
        accumulator = 0.0
        silence_timer = 0.0
    if not math.isfinite(accumulator):
        accumulator = 0.0
    if not math.isfinite(silence_timer):
        silence_timer = 0.0
    state.update({
        "accumulator": accumulator,
        "silence_timer": silence_timer,
        "startle_triggered": bool(state.get("startle_triggered", False)),
        "chase_triggered": bool(state.get("chase_triggered", False)),
    })
    return state


def reset_redhead_sound_awareness(entity):
    state = get_redhead_sound_awareness(entity)
    state.update({
        "accumulator": 0.0,
        "silence_timer": 0.0,
        "startle_triggered": False,
        "chase_triggered": False,
    })
    return state


def propagate_ai_sound_distances(source_world_position, tile_map,
                                 radius_tiles):
    """Return bounded four-connected sound distances; solid tiles block."""
    if not isinstance(source_world_position, dict):
        return {}
    map_width = int(tile_map.get("map_width", 0))
    map_height = int(tile_map.get("map_height", 0))
    tile_width = max(1.0, float(tile_map.get("tile_width", 16)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16)))
    radius = max(0, int(math.ceil(max(0.0, float(radius_tiles)))))
    source_x = int(math.floor(
        float(source_world_position.get("x", 0.0)) / tile_width,
    ))
    source_y = int(math.floor(
        float(source_world_position.get("y", 0.0)) / tile_height,
    ))
    if (source_x < 0 or source_y < 0
            or source_x >= map_width or source_y >= map_height):
        return {}

    distances = {(source_x, source_y): 0}
    frontier = [(source_x, source_y)]
    frontier_index = 0
    tiles = tile_map.get("tiles", [])
    while frontier_index < len(frontier):
        tile_x, tile_y = frontier[frontier_index]
        frontier_index += 1
        next_distance = distances[(tile_x, tile_y)] + 1
        if next_distance > radius:
            continue
        for next_x, next_y in (
                (tile_x - 1, tile_y), (tile_x + 1, tile_y),
                (tile_x, tile_y - 1), (tile_x, tile_y + 1)):
            key = (next_x, next_y)
            if (key in distances or next_x < 0 or next_y < 0
                    or next_x >= map_width or next_y >= map_height):
                continue
            tile_index = next_y * map_width + next_x
            if tile_index >= len(tiles) or tile_is_collidable(
                    tiles[tile_index], tile_map):
                continue
            distances[key] = next_distance
            frontier.append(key)
    return distances


def coalesce_player_ai_sound_events(events, tile_map):
    """Group same-frame player sounds that share a source tile and profile."""
    tile_width = max(1.0, float(tile_map.get("tile_width", 16)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16)))
    grouped = {}
    for event in events or ():
        if (not isinstance(event, dict)
                or event.get("source_kind") != "player"
                or str(event.get("source_id", "")) != "player"
                or event.get("type") not in {"gunshot", "footstep"}
                or not isinstance(event.get("world_position"), dict)):
            continue
        world_position = event["world_position"]
        event_type = event["type"]
        gait = (
            str(event.get("data", {}).get("gait", "walk"))
            if event_type == "footstep" else ""
        )
        tile_x = int(math.floor(
            float(world_position.get("x", 0.0)) / tile_width,
        ))
        tile_y = int(math.floor(
            float(world_position.get("y", 0.0)) / tile_height,
        ))
        key = (event_type, gait, tile_x, tile_y)
        group = grouped.setdefault(key, {
            "type": event_type,
            "gait": gait,
            "world_position": {
                "x": float(world_position.get("x", 0.0)),
                "y": float(world_position.get("y", 0.0)),
            },
            "count": 0,
        })
        group["count"] += 1
        group["world_position"] = {
            "x": float(world_position.get("x", 0.0)),
            "y": float(world_position.get("y", 0.0)),
        }
    return list(grouped.values())


def queue_redhead_sound_chase(entity, source_world_position, tile_map,
                               from_cumulative_startle=False):
    existing = entity.get("pending_player_sound_chase")
    if (isinstance(existing, dict)
            and not existing.get("from_cumulative_startle", False)
            and from_cumulative_startle):
        # An immediate sound is the stronger request. Do not let a footstep
        # group later in the same frame downgrade it to cumulative behavior.
        return False
    source_position = get_tile_index_and_offset_from_pos(
        source_world_position, tile_map,
    )
    entity["last_heard_player_pos"] = copy_entity_pos(source_position)
    entity["pending_player_sound_chase"] = {
        "position": copy_entity_pos(source_position),
        "from_cumulative_startle": bool(from_cumulative_startle),
    }
    return True


def update_redhead_sound_awareness(entities, tile_map, audio_events, dt):
    """Propagate this frame's player sounds and update per-enemy alertness."""
    brains = entities.get("brains", {}) if isinstance(entities, dict) else {}
    listeners = []
    for entity_id, entity in brains.items():
        if (not isinstance(entity, dict) or entity.get("type") != "red head"
                or entity.get("current_state") == "dead"
                or float(entity.get("health", 0.0)) <= 0.0):
            continue
        listeners.append((entity_id, entity, get_redhead_hearing_settings(entity)))

    groups = coalesce_player_ai_sound_events(audio_events, tile_map)
    cumulative_heard = set()
    stats = {"sound_groups": len(groups), "floods": 0, "visited_tiles": 0}
    for group in groups:
        is_gunshot = group["type"] == "gunshot"
        gait = "run" if group.get("gait") == "run" else "walk"
        radius_key = (
            "gunshot_radius_tiles" if is_gunshot
            else f"{gait}_footstep_radius_tiles"
        )
        maximum_radius = max(
            (settings[radius_key] for _id, _entity, settings in listeners),
            default=0.0,
        )
        if maximum_radius <= 0.0:
            continue
        distances = propagate_ai_sound_distances(
            group["world_position"], tile_map, maximum_radius,
        )
        stats["floods"] += 1
        stats["visited_tiles"] += len(distances)
        for entity_id, entity, settings in listeners:
            current_state = entity.get("current_state", "idle")
            if current_state in {"angry chase", "angry and attacking", "evade"}:
                continue
            collision_position = offset_entity_position_for_collision(
                entity.get("position", {}), entity, tile_map,
            )
            distance = distances.get((
                int(collision_position.get("tile_x", -1)),
                int(collision_position.get("tile_y", -1)),
            ))
            radius = settings[radius_key]
            if distance is None or distance > radius:
                continue
            audibility = max(0.0, 1.0 - distance / (radius + 1.0))
            if audibility <= 0.0:
                continue
            if is_gunshot:
                reset_redhead_sound_awareness(entity)
                queue_redhead_sound_chase(
                    entity, group["world_position"], tile_map,
                    from_cumulative_startle=False,
                )
                continue

            cumulative_heard.add(entity_id)
            state = get_redhead_sound_awareness(entity)
            state["silence_timer"] = 0.0
            contribution = (
                settings[f"{gait}_footstep_contribution"]
                * max(1, int(group.get("count", 1))) * audibility
            )
            state["accumulator"] += contribution
            source_position = get_tile_index_and_offset_from_pos(
                group["world_position"], tile_map,
            )
            entity["last_heard_player_pos"] = copy_entity_pos(source_position)
            if (not state["startle_triggered"]
                    and state["accumulator"] >= settings["startle_threshold"]):
                state["startle_triggered"] = True
                if (current_state == "idle"
                        and not isinstance(
                            entity.get("pending_awareness_stimulus"), dict,
                        )):
                    queue_redhead_awareness_stimulus(
                        entity, "sound", group["world_position"], tile_map,
                        strength=audibility,
                    )
            if (not state["chase_triggered"]
                    and state["accumulator"] >= settings["chase_threshold"]):
                state["chase_triggered"] = True
                queue_redhead_sound_chase(
                    entity, group["world_position"], tile_map,
                    from_cumulative_startle=state["startle_triggered"],
                )

    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0
    for entity_id, entity, settings in listeners:
        if entity_id in cumulative_heard:
            continue
        state = get_redhead_sound_awareness(entity)
        if state["accumulator"] <= 0.0 and not state["startle_triggered"]:
            continue
        state["silence_timer"] += frame_dt
        if state["silence_timer"] + 0.000001 >= settings["silence_reset_seconds"]:
            reset_redhead_sound_awareness(entity)
    return stats


def get_redhead_flashlight_sample_points(entity, tile_map):
    hurtbox = get_redhead_bullet_hurtbox(entity, tile_map)
    left = float(hurtbox["x"])
    top = float(hurtbox["y"])
    width = float(hurtbox["width"])
    height = float(hurtbox["height"])
    center_x = left + width * 0.5
    center_y = top + height * 0.5
    return (
        {"x": center_x, "y": center_y},
        {"x": center_x, "y": top + height * 0.20},
        {"x": center_x, "y": top + height * 0.80},
        {"x": left + width * 0.20, "y": center_y},
        {"x": left + width * 0.80, "y": center_y},
    )


def update_redhead_flashlight_awareness(
        entities, player_info, tile_map, lighting_frame, dt):
    """Accumulate wall-occluded flashlight exposure and queue awareness."""
    prepared_by_id = (
        lighting_frame.get("prepared_by_id", {})
        if isinstance(lighting_frame, dict) else {}
    )
    flashlight = prepared_by_id.get("runtime:player_flashlight")
    collision_grid = (
        lighting_frame.get("collision_grid")
        if isinstance(lighting_frame, dict) else None
    )
    player_world = make_pos_abs(
        player_info.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )

    for entity in entities.get("brains", {}).values():
        if entity.get("type") != "red head":
            continue
        runtime = entity.setdefault("awareness_runtime", {})
        if not isinstance(runtime, dict):
            runtime = {}
            entity["awareness_runtime"] = runtime
        if entity.get("current_state", "idle") != "idle":
            runtime["flashlight_exposure"] = 0.0
            runtime["flashlight_latched"] = False
            runtime["last_flashlight_strength"] = 0.0
            continue

        settings = get_redhead_perception_settings(entity)
        sample_interval = 1.0 / settings["flashlight_checks_per_second"]
        sample_elapsed = max(
            0.0, float(runtime.get("flashlight_sample_elapsed", 0.0)),
        ) + max(0.0, dt)
        sample_due = (
            not runtime.get("flashlight_sample_valid", False)
            or runtime.get("flashlight_latched", False)
            or sample_elapsed + 0.000001 >= sample_interval
        )
        if not sample_due:
            runtime["flashlight_sample_elapsed"] = sample_elapsed
            continue

        strength = 0.0
        if flashlight is not None and collision_grid is not None:
            sample_points = get_redhead_flashlight_sample_points(entity, tile_map)
            strength = (
                g_graphics.get_prepared_gameplay_light_strength_at_world_point(
                    flashlight, sample_points[0], collision_grid,
                )
            )
            if strength < settings["flashlight_intensity_threshold"]:
                for point in sample_points[1:]:
                    strength = max(
                        strength,
                        g_graphics.get_prepared_gameplay_light_strength_at_world_point(
                            flashlight, point, collision_grid,
                        ),
                    )
        runtime["last_flashlight_strength"] = strength
        runtime["flashlight_sample_valid"] = True
        runtime["flashlight_sample_elapsed"] = 0.0
        illuminated = (
            strength > 0.0
            and strength >= settings["flashlight_intensity_threshold"]
        )
        if not illuminated:
            runtime["flashlight_exposure"] = 0.0
            runtime["flashlight_latched"] = False
            continue

        exposure = max(
            0.0, float(runtime.get("flashlight_exposure", 0.0)),
        ) + sample_elapsed
        runtime["flashlight_exposure"] = exposure
        if (exposure >= settings["flashlight_notice_duration"]
                and not runtime.get("flashlight_latched", False)):
            queue_redhead_awareness_stimulus(
                entity, "light", player_world, tile_map, strength,
            )
            runtime["flashlight_latched"] = True


def get_redhead_evade_settings(entity):
    authored = entity.get("evade_settings", {})
    if not isinstance(authored, dict):
        authored = {}

    def value(name):
        try:
            result = float(authored.get(name, REDHEAD_EVADE_DEFAULTS[name]))
        except (TypeError, ValueError, OverflowError):
            result = float(REDHEAD_EVADE_DEFAULTS[name])
        return result if math.isfinite(result) else float(REDHEAD_EVADE_DEFAULTS[name])

    duration_min = max(0.05, value("duration_min"))
    duration_max = max(duration_min, value("duration_max"))
    return {
        "chance": max(0.0, min(1.0, value("chance"))),
        "aim_margin": max(0.0, value("aim_margin")),
        "aim_max_distance": max(1.0, value("aim_max_distance")),
        "reaction_time": max(0.0, value("reaction_time")),
        "failed_retry_delay": max(0.0, value("failed_retry_delay")),
        "cooldown": max(0.0, value("cooldown")),
        "duration_min": duration_min,
        "duration_max": duration_max,
        "search_radius_tiles": max(1, int(round(value("search_radius_tiles")))),
        "minimum_lateral_tiles": max(0.0, value("minimum_lateral_tiles")),
        "maximum_retreat_tiles": max(0.0, value("maximum_retreat_tiles")),
        "heading_reversal_limit": max(
            -1.0, min(1.0, value("heading_reversal_limit")),
        ),
        "top_candidate_count": max(1, int(round(value("top_candidate_count")))),
        "lateral_score_weight": max(0.0, value("lateral_score_weight")),
        "aim_clearance_score_weight": max(
            0.0, value("aim_clearance_score_weight"),
        ),
        "progress_score_weight": max(0.0, value("progress_score_weight")),
        "path_cost_score_weight": max(0.0, value("path_cost_score_weight")),
        "preferred_side_score": max(0.0, value("preferred_side_score")),
        "cover_score_weight": max(0.0, value("cover_score_weight")),
        "waypoint_arrival_radius": max(
            0.0, value("waypoint_arrival_radius"),
        ),
        "stuck_replan_delay": max(0.05, value("stuck_replan_delay")),
    }


def get_redhead_flee_settings(entity):
    authored = entity.get("flee_settings", {})
    if not isinstance(authored, dict):
        authored = {}

    def value(name):
        try:
            result = float(authored.get(name, REDHEAD_FLEE_DEFAULTS[name]))
        except (TypeError, ValueError, OverflowError):
            result = float(REDHEAD_FLEE_DEFAULTS[name])
        return result if math.isfinite(result) else float(REDHEAD_FLEE_DEFAULTS[name])

    return {
        "health_fraction": max(0.0, min(1.0, value("health_fraction"))),
        "ally_search_radius_tiles": max(
            1, min(32, int(round(value("ally_search_radius_tiles")))),
        ),
        "local_plan_radius_tiles": max(
            1, min(16, int(round(value("local_plan_radius_tiles")))),
        ),
        "ally_arrival_distance": max(0.0, value("ally_arrival_distance")),
        "speed_multiplier": max(0.0, value("speed_multiplier")),
        "replan_interval": max(0.10, value("replan_interval")),
        "waypoint_arrival_radius": max(
            0.0, value("waypoint_arrival_radius"),
        ),
    }


def redhead_has_live_ally_nearby(entity, entities, tile_map):
    if not isinstance(entities, dict) or not isinstance(tile_map, dict):
        return False
    settings = get_redhead_flee_settings(entity)
    tile_scale = max(
        1.0, (float(tile_map.get("tile_width", 16))
              + float(tile_map.get("tile_height", 16))) * 0.5,
    )
    radius_squared = (
        settings["ally_search_radius_tiles"] * tile_scale
    ) ** 2
    entity_world = get_entity_collision_world_position(entity, tile_map)
    for ally in entities.get("brains", {}).values():
        if (not isinstance(ally, dict) or ally is entity
                or ally.get("type") != "red head"
                or ally.get("current_state") == "dead"
                or float(ally.get("health", 0.0)) <= 0.0):
            continue
        ally_world = get_entity_collision_world_position(ally, tile_map)
        delta_x = ally_world["x"] - entity_world["x"]
        delta_y = ally_world["y"] - entity_world["y"]
        if delta_x * delta_x + delta_y * delta_y <= radius_squared:
            return True
    return False


def redhead_should_flee(entity, entities=None, tile_map=None):
    if bool(entity.get("has_fled", False)):
        return False
    settings = get_redhead_flee_settings(entity)
    maximum_health = max(
        1.0, float(entity.get("max_health", 60.0)),
    )
    low_health = 0.0 < float(entity.get("health", 0.0)) <= (
        maximum_health * settings["health_fraction"]
    )
    return low_health and redhead_has_live_ally_nearby(
        entity, entities, tile_map,
    )


def alert_visible_redhead_allies(entity, entities, tile_map,
                                  debug_queue=None):
    """Startle nearby idle allies after this redhead commits to pursuit."""
    if not isinstance(entities, dict) or not isinstance(tile_map, dict):
        return 0
    settings = get_redhead_perception_settings(entity)
    tile_scale = max(
        1.0, (float(tile_map.get("tile_width", 16))
              + float(tile_map.get("tile_height", 16))) * 0.5,
    )
    alert_radius = settings["ally_alert_radius_tiles"] * tile_scale
    if alert_radius <= 0.0:
        return 0
    source_position = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    source_world = make_pos_abs(
        source_position,
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    alerted = 0
    for ally in entities.get("brains", {}).values():
        if (not isinstance(ally, dict) or ally is entity
                or ally.get("type") != "red head"
                or ally.get("current_state") != "idle"
                or float(ally.get("health", 0.0)) <= 0.0
                or isinstance(
                    ally.get("pending_awareness_stimulus"), dict,
                )):
            continue
        ally_position = offset_entity_position_for_collision(
            ally.get("position", {}), ally, tile_map,
        )
        ally_world = make_pos_abs(
            ally_position,
            tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
        )
        if vec2_distance(source_world, ally_world) > alert_radius:
            continue
        if not alice_can_raycast_to_bob(
                alert_radius, source_position, ally_position,
                tile_map, debug_queue):
            continue
        if queue_redhead_awareness_stimulus(
                ally, "ally_alert", source_world, tile_map):
            alerted += 1
    return alerted


def player_is_aiming_near_redhead(player_info, entity, tile_map):
    settings = get_redhead_evade_settings(entity)
    aim_direction = vec2_normalize(player_info.get("aim_direction", {}))
    if vec2_norm(aim_direction) <= 0.000001:
        return False
    player_world = make_pos_abs(
        player_info.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    aim_end = vec2_add(
        player_world,
        vec2_scale(aim_direction, settings["aim_max_distance"]),
    )
    hurtbox = get_redhead_bullet_hurtbox(entity, tile_map)
    margin = settings["aim_margin"]
    threat_box = {
        "x": hurtbox["x"] - margin,
        "y": hurtbox["y"] - margin,
        "width": hurtbox["width"] + margin * 2.0,
        "height": hurtbox["height"] + margin * 2.0,
    }
    return segment_aabb_intersection_fraction(
        player_world, aim_end, threat_box,
    ) is not None


def update_redhead_evade_trigger(entity, player_info, tile_map, can_see, dt):
    settings = get_redhead_evade_settings(entity)
    available = (
        can_see
        and float(entity.get("evade_cooldown_timer", 0.0)) <= 0.0
        and float(entity.get("evade_retry_timer", 0.0)) <= 0.0
    )
    aimed_near = available and player_is_aiming_near_redhead(
        player_info, entity, tile_map,
    )
    if not aimed_near:
        entity["evade_reaction_timer"] = 0.0
        return False
    reaction_timer = max(
        0.0, float(entity.get("evade_reaction_timer", 0.0)),
    ) + max(0.0, dt)
    entity["evade_reaction_timer"] = reaction_timer
    if reaction_timer < settings["reaction_time"]:
        return False
    entity["evade_reaction_timer"] = 0.0
    if random.random() < settings["chance"]:
        return True
    entity["evade_retry_timer"] = settings["failed_retry_delay"]
    return False


def prepare_redhead_pursuit_path(entity, seen_pos, tile_map):
    if not isinstance(seen_pos, dict):
        return False
    map_width = int(tile_map.get("map_width", 0))
    map_height = int(tile_map.get("map_height", 0))
    target_x = int(seen_pos.get("tile_x", -1))
    target_y = int(seen_pos.get("tile_y", -1))
    entity_pos = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    start_x = int(entity_pos.get("tile_x", -1))
    start_y = int(entity_pos.get("tile_y", -1))
    if (target_x < 0 or target_y < 0 or start_x < 0 or start_y < 0
            or target_x >= map_width or target_y >= map_height
            or start_x >= map_width or start_y >= map_height):
        return False
    tiles = tile_map.get("tiles", [])
    target_index = target_y * map_width + target_x
    start_index = start_y * map_width + start_x
    if target_index >= len(tiles) or start_index >= len(tiles):
        return False
    target_tile = tiles[target_index]
    start_tile = tiles[start_index]
    came_from = a_star_path(start_tile, target_tile, tile_map)
    if get_tile_id_for_hash(target_tile) not in came_from:
        return False
    entity["path_to_player"] = reconstruct_path(
        came_from, target_tile, start_tile,
    )
    entity["path_to_player_current_index"] = 0
    entity["last_seen_player_pos"] = copy_entity_pos(seen_pos)
    entity["give_up_time"] = 0.0
    entity["breadcrumb_timer"] = 0.0
    return True


def on_redhead_state_enter(entity, state, entered_from, tile_map, audio_runtime):
    entity["state_entered_from"] = entered_from
    resumed_after_stagger = (
        entered_from == "stagger"
        and entity.get("previous_state_on_stagger") == state
    )
    if resumed_after_stagger:
        return
    world_position = make_pos_abs(
        entity.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    source_id = f"enemy:{entity.get('id', 'unknown')}"
    if state in ("noticing", "light startle"):
        if state == "noticing":
            entity["notice_timer"] = 0.0
        else:
            entity["light_startle_timer"] = 0.0
        entity["pursuit_bark_pending"] = False
        queue_gameplay_audio(
            audio_runtime, "redhead_startle", source_id, "enemy",
            world_position, priority=0.95,
        )
    elif state == "evade":
        settings = get_redhead_evade_settings(entity)
        entity["evade_elapsed"] = 0.0
        entity["evade_duration"] = random.uniform(
            settings["duration_min"], settings["duration_max"],
        )
        entity["evade_cooldown_timer"] = settings["cooldown"]
        entity["evade_reaction_timer"] = 0.0
        entity["evade_retry_timer"] = 0.0
        entity["evade_stuck_timer"] = 0.0
        queue_gameplay_audio(
            audio_runtime, "redhead_evade", source_id, "enemy",
            world_position, priority=1.0,
        )
    elif state == "flee":
        # Flee is a one-shot survival reaction. Once entered, subsequent
        # low-health staggers resume combat rather than restarting retreat.
        entity["has_fled"] = True
        clear_redhead_evade_navigation(entity)
        clear_redhead_flee_navigation(entity)
        entity["flee_plan_retry_timer"] = 0.0
    elif state == "angry chase" and entity.pop("pursuit_bark_pending", False):
        queue_gameplay_audio(
            audio_runtime, "redhead_pursuit_hiss", source_id, "enemy",
            world_position, priority=1.0,
        )
    elif state == "angry and attacking":
        reset_redhead_attack_cycle(entity)

def idle_redhead_state(entity, current_state, player_info, tile_map, debug_queue, dt):
    next_state = current_state
    bored_timer = entity.get("bored_timer", 0)

    awareness_stimulus = entity.pop("pending_awareness_stimulus", None)
    if isinstance(awareness_stimulus, dict):
        source = awareness_stimulus.get("source_world_position")
        if isinstance(source, dict):
            face_redhead_towards_world_position(entity, source, tile_map)
        entity["last_awareness_stimulus"] = awareness_stimulus
        entity["bored_timer"] = bored_timer
        if awareness_stimulus.get("type") == "light":
            entity["last_seen_player_pos"] = copy_entity_pos(
                player_info.get("position", {}),
            )
            entity["breadcrumb_timer"] = 0.0
            return "light startle"
        return "noticing"

    bored_threshold = 1
    can_see, seen_pos, _can_move = sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt,
    )
        
    if can_see:
        next_state = "noticing"
    else:
        bored_timer += dt
        # TODO
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


def noticing_redhead_state(entity, current_state, player_info, tile_map,
                           debug_queue, dt):
    notice_timer = max(0.0, float(entity.get("notice_timer", 0.0))) + dt
    entity["notice_timer"] = notice_timer
    notice_duration = max(0.0, float(entity.get("notice_duration", 1.0)))
    if notice_timer < notice_duration:
        return current_state
    can_see, seen_pos, _can_move = sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt, force=True,
    )
    entity["notice_timer"] = 0.0
    if can_see and prepare_redhead_pursuit_path(entity, seen_pos, tile_map):
        entity["pursuit_bark_pending"] = True
        return "angry chase"
    entity["pursuit_bark_pending"] = False
    return "idle"


def light_startle_redhead_state(entity, current_state, player_info, tile_map,
                                 debug_queue, dt):
    entity["light_startle_timer"] = max(
        0.0, float(entity.get("light_startle_timer", 0.0)),
    ) + max(0.0, dt)
    duration = get_redhead_perception_settings(entity)["light_startle_duration"]
    if entity["light_startle_timer"] < duration:
        return current_state
    seen_position = entity.get("last_seen_player_pos")
    if not isinstance(seen_position, dict):
        seen_position = player_info.get("position", {})
    if prepare_redhead_pursuit_path(entity, seen_position, tile_map):
        entity["pursuit_bark_pending"] = True
        return "angry chase"
    return "idle"

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


def normalize_aim_heading(angle_degrees):
    return float(angle_degrees) % 360.0


def aim_direction_from_heading(angle_degrees):
    radians = math.radians(normalize_aim_heading(angle_degrees))
    return {"x": math.cos(radians), "y": math.sin(radians)}


def aim_heading_from_direction(direction, fallback=DEFAULT_AIM_HEADING_DEGREES):
    direction = direction or {}
    x = float(direction.get("x", 0.0))
    y = float(direction.get("y", 0.0))
    if math.hypot(x, y) <= 0.000001:
        return normalize_aim_heading(fallback)
    return normalize_aim_heading(math.degrees(math.atan2(y, x)))


def ensure_player_aim_state(player):
    """Migrate old aim data and maintain the player-relative virtual cursor."""
    migrated = int(player.get("aim_input_version", 0)) != AIM_INPUT_VERSION
    if "aim_heading" not in player:
        player["aim_heading"] = aim_heading_from_direction(player.get("aim_direction"))
    player["aim_heading"] = normalize_aim_heading(player.get("aim_heading", DEFAULT_AIM_HEADING_DEGREES))
    direction = aim_direction_from_heading(player["aim_heading"])
    cursor = player.get("aim_cursor_offset")
    if migrated or not isinstance(cursor, dict):
        cursor = vec2_scale(direction, DEFAULT_AIM_CURSOR_DISTANCE)
        player["mouse_aim_sensitivity"] = DEFAULT_MOUSE_AIM_SENSITIVITY
    else:
        cursor = {"x": float(cursor.get("x", 0.0)), "y": float(cursor.get("y", 0.0))}
        cursor_length = math.hypot(cursor["x"], cursor["y"])
        if cursor_length > 0.000001:
            player["aim_heading"] = aim_heading_from_direction(cursor, player["aim_heading"])
            direction = aim_direction_from_heading(player["aim_heading"])
    player["aim_cursor_offset"] = cursor
    player["aim_direction"] = direction
    player.setdefault("mouse_aim_sensitivity", DEFAULT_MOUSE_AIM_SENSITIVITY)
    player["aim_input_version"] = AIM_INPUT_VERSION
    return player["aim_direction"]


def apply_player_aim_turn(player, turn_degrees):
    """Apply device-independent relative turn input to persistent aim state."""
    ensure_player_aim_state(player)
    cursor = player["aim_cursor_offset"]
    cursor_distance = math.hypot(cursor["x"], cursor["y"])
    if cursor_distance <= 0.000001:
        cursor_distance = DEFAULT_AIM_CURSOR_DISTANCE
    player["aim_heading"] = normalize_aim_heading(player["aim_heading"] + float(turn_degrees))
    player["aim_direction"] = aim_direction_from_heading(player["aim_heading"])
    player["aim_cursor_offset"] = vec2_scale(player["aim_direction"], cursor_distance)
    return player["aim_direction"]


def apply_player_aim_cursor_delta(player, delta_x, delta_y):
    """Move the virtual cursor relative to its current player-local position."""
    previous_direction = ensure_player_aim_state(player)
    cursor = player["aim_cursor_offset"]
    candidate = {
        "x": cursor["x"] + float(delta_x),
        "y": cursor["y"] + float(delta_y),
    }
    candidate_length = math.hypot(candidate["x"], candidate["y"])
    if candidate_length > MAX_AIM_CURSOR_DISTANCE:
        candidate = vec2_scale(candidate, MAX_AIM_CURSOR_DISTANCE / candidate_length)
        candidate_length = MAX_AIM_CURSOR_DISTANCE
    player["aim_cursor_offset"] = candidate
    if candidate_length > 0.000001:
        player["aim_heading"] = aim_heading_from_direction(candidate, player["aim_heading"])
        player["aim_direction"] = aim_direction_from_heading(player["aim_heading"])
    else:
        player["aim_direction"] = dict(previous_direction)
    return player["aim_direction"]


def apply_player_mouse_aim_delta(player, mouse_delta_x, mouse_delta_y):
    sensitivity = max(0.0, float(player.get("mouse_aim_sensitivity", DEFAULT_MOUSE_AIM_SENSITIVITY)))
    return apply_player_aim_cursor_delta(
        player, float(mouse_delta_x) * sensitivity,
        float(mouse_delta_y) * sensitivity,
    )


def scale_mouse_delta_to_internal(mouse_delta_x, mouse_delta_y, screen_width, screen_height):
    """Convert window-pixel motion into the fixed internal scene coordinate space."""
    width = max(1.0, float(screen_width))
    height = max(1.0, float(screen_height))
    return {
        "x": float(mouse_delta_x) * float(g_internal_width) / width,
        "y": float(mouse_delta_y) * float(g_internal_height) / height,
    }


def get_player_aim_cursor_screen_position(player, tile_map, game_camera):
    ensure_player_aim_state(player)
    cursor = player["aim_cursor_offset"]
    world_position = make_pos_abs(
        player.get("position", {}), tile_map.get("tile_width", 16),
        tile_map.get("tile_height", 16),
    )
    return pr.Vector2(
        world_position["x"] - game_camera.x + cursor["x"],
        world_position["y"] - game_camera.y + cursor["y"],
    )


def get_player_weapon_transition_settings(player):
    # Defaults stay module-owned so code hot reloads immediately affect live
    # players. Only explicitly authored overrides belong in persistent state.
    authored = player.get("weapon_transition_overrides", {})
    if not isinstance(authored, dict):
        authored = {}

    def value(name):
        try:
            result = float(authored.get(
                name, PLAYER_WEAPON_TRANSITION_DEFAULTS[name],
            ))
        except (TypeError, ValueError, OverflowError):
            result = float(PLAYER_WEAPON_TRANSITION_DEFAULTS[name])
        if not math.isfinite(result):
            result = float(PLAYER_WEAPON_TRANSITION_DEFAULTS[name])
        return result

    return {
        "unholster_duration": max(0.01, value("unholster_duration")),
        "holster_duration": max(0.01, value("holster_duration")),
        "minimum_reverse_sound_seconds": max(
            0.0, value("minimum_reverse_sound_seconds"),
        ),
    }


def player_weapon_transition_phase(progress, target):
    if progress <= 0.000001 and target <= 0.0:
        return "holstered"
    if progress >= 0.999999 and target >= 1.0:
        return "unholstered"
    return "unholstering" if target >= 1.0 else "holstering"


def player_weapon_is_ready(player, aim_requested=None):
    state = ensure_player_weapon_transition_state(player)
    if aim_requested is None:
        aim_requested = player.get("aim_requested", player.get("aiming", False))
    return bool(
        aim_requested
        and state["target"] >= 1.0
        and state["progress"] >= 0.999999
    )


def get_player_aim_accuracy_settings(player):
    # Like transition timing, accuracy policy stays module-owned for immediate
    # hot tuning. Persistent data contains only explicit overrides.
    authored = player.get("aim_accuracy_overrides", {})
    if not isinstance(authored, dict):
        authored = {}

    def value(name):
        try:
            result = float(authored.get(name, PLAYER_AIM_ACCURACY_DEFAULTS[name]))
        except (TypeError, ValueError, OverflowError):
            result = float(PLAYER_AIM_ACCURACY_DEFAULTS[name])
        if not math.isfinite(result):
            result = float(PLAYER_AIM_ACCURACY_DEFAULTS[name])
        return result

    speed_deadzone = max(0.0, value("turn_speed_deadzone"))
    acceleration_deadzone = max(0.0, value("turn_acceleration_deadzone"))
    minimum_radius = max(0.0, value("minimum_reticle_radius"))
    return {
        "minimum_fire_progress": max(
            0.0, min(1.0, value("minimum_fire_progress")),
        ),
        "turn_speed_deadzone": speed_deadzone,
        "turn_speed_full_bloom": max(
            speed_deadzone + 0.000001, value("turn_speed_full_bloom"),
        ),
        "turn_acceleration_deadzone": acceleration_deadzone,
        "turn_acceleration_full_bloom": max(
            acceleration_deadzone + 0.000001,
            value("turn_acceleration_full_bloom"),
        ),
        "turn_speed_filter_seconds": max(
            0.001, value("turn_speed_filter_seconds"),
        ),
        "bloom_expand_seconds": max(0.001, value("bloom_expand_seconds")),
        "bloom_motion_recovery": max(
            0.001, value("bloom_motion_recovery"),
        ),
        "bloom_shot_recovery": max(
            0.001, value("bloom_shot_recovery"),
        ),
        "recoil_bloom_per_shot": max(
            0.0, min(1.0, value("recoil_bloom_per_shot")),
        ),
        "minimum_reticle_radius": minimum_radius,
        "motion_maximum_reticle_radius": max(
            minimum_radius, value("motion_maximum_reticle_radius"),
        ),
        "transition_maximum_reticle_radius": max(
            minimum_radius, value("transition_maximum_reticle_radius"),
        ),
        "motion_maximum_spread_degrees": max(
            0.0, value("motion_maximum_spread_degrees"),
        ),
        "transition_maximum_spread_degrees": max(
            0.0, value("transition_maximum_spread_degrees"),
        ),
    }


def smoothstep_unit(value):
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def smoothstep_range(value, minimum, maximum):
    if maximum <= minimum:
        return 1.0 if value >= maximum else 0.0
    return smoothstep_unit((float(value) - minimum) / (maximum - minimum))


def shortest_angle_delta_degrees(current, previous):
    return (float(current) - float(previous) + 180.0) % 360.0 - 180.0


def ensure_player_aim_accuracy_state(player):
    state = player.get("aim_accuracy")
    if not isinstance(state, dict):
        state = {}
        player["aim_accuracy"] = state

    def finite_nonnegative(name, fallback=0.0):
        try:
            result = max(0.0, float(state.get(name, fallback)))
        except (TypeError, ValueError, OverflowError):
            result = fallback
        return result if math.isfinite(result) else fallback

    try:
        previous_heading = float(state.get(
            "previous_heading", player.get("aim_heading", 0.0),
        )) % 360.0
    except (TypeError, ValueError, OverflowError):
        previous_heading = float(player.get("aim_heading", 0.0)) % 360.0
    state.update({
        "motion_instability": min(
            1.0, finite_nonnegative("motion_instability"),
        ),
        "shot_instability": min(
            1.0, finite_nonnegative("shot_instability"),
        ),
        "filtered_angular_speed": finite_nonnegative(
            "filtered_angular_speed",
        ),
        "previous_angular_speed": finite_nonnegative(
            "previous_angular_speed",
        ),
        "previous_heading": previous_heading,
    })
    return state


def update_player_aim_accuracy(player, aim_requested, dt):
    """Update motion bloom from angular speed and positive acceleration."""
    ensure_player_aim_state(player)
    state = ensure_player_aim_accuracy_state(player)
    settings = get_player_aim_accuracy_settings(player)
    try:
        frame_dt = max(0.0, min(0.1, float(dt)))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0

    heading = float(player.get("aim_heading", 0.0)) % 360.0
    previous_heading = state["previous_heading"]
    angular_speed = 0.0
    target_instability = 0.0
    if frame_dt > 0.0 and aim_requested:
        angular_speed = abs(shortest_angle_delta_degrees(
            heading, previous_heading,
        )) / frame_dt
        filter_alpha = 1.0 - math.exp(
            -frame_dt / settings["turn_speed_filter_seconds"],
        )
        filtered_speed = state["filtered_angular_speed"] + (
            angular_speed - state["filtered_angular_speed"]
        ) * filter_alpha
        positive_acceleration = max(
            0.0,
            (angular_speed - state["previous_angular_speed"]) / frame_dt,
        )
        speed_instability = smoothstep_range(
            filtered_speed,
            settings["turn_speed_deadzone"],
            settings["turn_speed_full_bloom"],
        )
        acceleration_instability = smoothstep_range(
            positive_acceleration,
            settings["turn_acceleration_deadzone"],
            settings["turn_acceleration_full_bloom"],
        )
        target_instability = 1.0 - (
            (1.0 - speed_instability) * (1.0 - acceleration_instability)
        )
        state["filtered_angular_speed"] = filtered_speed
        state["previous_angular_speed"] = angular_speed
    else:
        state["filtered_angular_speed"] = 0.0
        state["previous_angular_speed"] = 0.0

    instability = state["motion_instability"]
    duration = (
        settings["bloom_expand_seconds"]
        if target_instability > instability
        else settings["bloom_motion_recovery"]
    )
    maximum_change = frame_dt / duration if duration > 0.0 else 1.0
    if target_instability > instability:
        instability = min(target_instability, instability + maximum_change)
    else:
        instability = max(target_instability, instability - maximum_change)
    state.update({
        "motion_instability": max(0.0, min(1.0, instability)),
        "previous_heading": heading,
        "angular_speed": angular_speed,
        "target_instability": target_instability,
    })
    state["shot_instability"] = max(
        0.0,
        state["shot_instability"]
        - frame_dt / settings["bloom_shot_recovery"],
    )
    return state


def get_player_transition_instability(player):
    progress = ensure_player_weapon_transition_state(player)["progress"]
    return 1.0 - smoothstep_unit(progress)


def get_player_dynamic_aim_instability(player):
    state = ensure_player_aim_accuracy_state(player)
    motion = state["motion_instability"]
    shot = state["shot_instability"]
    return 1.0 - (1.0 - motion) * (1.0 - shot)


def get_player_total_aim_instability(player):
    dynamic = get_player_dynamic_aim_instability(player)
    transition = get_player_transition_instability(player)
    return max(0.0, min(1.0, 1.0 - (1.0 - dynamic) * (1.0 - transition)))


def player_weapon_can_fire(player, aim_requested=None):
    state = ensure_player_weapon_transition_state(player)
    if aim_requested is None:
        aim_requested = player.get("aim_requested", player.get("aiming", False))
    minimum_progress = get_player_aim_accuracy_settings(player)[
        "minimum_fire_progress"
    ]
    return bool(
        aim_requested
        and state["target"] >= 1.0
        and state["progress"] + 0.000001 >= minimum_progress
    )


def get_player_accuracy_reticle_radius(player):
    settings = get_player_aim_accuracy_settings(player)
    dynamic = get_player_dynamic_aim_instability(player)
    transition = get_player_transition_instability(player)
    minimum = settings["minimum_reticle_radius"]
    transition_penalty = (
        settings["transition_maximum_reticle_radius"] - minimum
    ) * transition
    dynamic_penalty = (
        settings["motion_maximum_reticle_radius"] - minimum
    ) * dynamic * (1.0 - transition)
    return minimum + transition_penalty + dynamic_penalty


def get_player_maximum_shot_deviation(player):
    settings = get_player_aim_accuracy_settings(player)
    dynamic = get_player_dynamic_aim_instability(player)
    transition = get_player_transition_instability(player)
    return (
        settings["transition_maximum_spread_degrees"] * transition
        + settings["motion_maximum_spread_degrees"]
        * dynamic * (1.0 - transition)
    )


def apply_player_shot_recoil_bloom(player):
    state = ensure_player_aim_accuracy_state(player)
    recoil = get_player_aim_accuracy_settings(player)["recoil_bloom_per_shot"]
    state["shot_instability"] = min(
        1.0, state["shot_instability"] + recoil,
    )
    return state["shot_instability"]


def sample_player_shot_direction(player, aim_direction, rng=None):
    maximum_deviation = get_player_maximum_shot_deviation(player)
    if maximum_deviation <= 0.000001:
        return dict(aim_direction)
    random_source = rng or random
    deviation = random_source.triangular(
        -maximum_deviation, maximum_deviation, 0.0,
    )
    shot_angle = aim_heading_from_direction(aim_direction) + deviation
    return aim_direction_from_heading(shot_angle)


def ensure_player_weapon_transition_state(player):
    settings = get_player_weapon_transition_settings(player)
    # Retire the old copied-default representation. Keeping it would pin live
    # players to whichever values existed when they were constructed.
    player.pop("weapon_transition_settings", None)
    state = player.get("weapon_transition")
    if not isinstance(state, dict):
        initial = 1.0 if player.get("aiming", False) else 0.0
        state = {"progress": initial, "target": initial}
        player["weapon_transition"] = state
    try:
        progress = max(0.0, min(1.0, float(state.get("progress", 0.0))))
        target = 1.0 if float(state.get("target", progress)) >= 0.5 else 0.0
    except (TypeError, ValueError, OverflowError):
        progress = 0.0
        target = 0.0
    state.update({
        "progress": progress,
        "target": target,
        "phase": player_weapon_transition_phase(progress, target),
    })
    return state


def update_player_weapon_transition(player, aim_requested, dt, audio_runtime,
                                    world_position):
    """Move the pistol between normalized endpoints and manage reversal audio."""
    state = ensure_player_weapon_transition_state(player)
    settings = get_player_weapon_transition_settings(player)
    progress = state["progress"]
    target = 1.0 if aim_requested else 0.0
    previous_target = state["target"]

    if target != previous_target:
        state["target"] = target
        queue_gameplay_audio(
            audio_runtime, "sound_instance_stop", "player", "player",
            world_position, priority=2.0,
            data={"instance_key": PLAYER_WEAPON_TRANSITION_INSTANCE_KEY},
        )
        if target >= 1.0:
            event_type = "weapon_unholster"
            start_fraction = progress
            remaining_seconds = (
                (1.0 - progress) * settings["unholster_duration"]
            )
        else:
            event_type = "weapon_holster"
            start_fraction = 1.0 - progress
            remaining_seconds = progress * settings["holster_duration"]
        if (remaining_seconds + 0.000001
                >= settings["minimum_reverse_sound_seconds"]):
            queue_gameplay_audio(
                audio_runtime, event_type, "player", "player",
                world_position, priority=1.6,
                data={
                    "instance_key": PLAYER_WEAPON_TRANSITION_INSTANCE_KEY,
                    "start_fraction": start_fraction,
                },
            )

    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt):
        frame_dt = 0.0
    if target > progress:
        progress = min(
            target, progress + frame_dt / settings["unholster_duration"],
        )
    elif target < progress:
        progress = max(
            target, progress - frame_dt / settings["holster_duration"],
        )
    state.update({
        "progress": progress,
        "target": target,
        "phase": player_weapon_transition_phase(progress, target),
    })
    return state


def draw_player_aim_cursor(player, tile_map, game_camera):
    aim_cursor = get_player_aim_cursor_screen_position(
        player, tile_map, game_camera,
    )
    cursor_x = int(round(aim_cursor.x))
    cursor_y = int(round(aim_cursor.y))
    if player_weapon_can_fire(player):
        pr.draw_circle_lines(
            cursor_x, cursor_y,
            get_player_accuracy_reticle_radius(player), pr.WHITE,
        )
    pr.draw_circle(cursor_x, cursor_y, 1.0, pr.WHITE)


def update_play_mouse_capture(game_assets, should_capture):
    """Use unbounded relative mouse input during unobstructed play."""
    should_capture = bool(should_capture)
    was_captured = bool(game_assets.get("play_mouse_captured", False))
    if should_capture == was_captured:
        return was_captured
    if should_capture:
        pr.disable_cursor()
    else:
        pr.enable_cursor()
        pr.hide_cursor()
    game_assets["play_mouse_captured"] = should_capture
    game_assets["suppress_aim_mouse_delta_once"] = True
    return should_capture


def fast_distance_within_tiles(tile_and_offset_a, tile_and_offset_b, dist):
    collides = False
    if tile_and_offset_a.get("tile_x") == tile_and_offset_b.get("tile_x") and tile_and_offset_a.get("tile_y") == tile_and_offset_b.get("tile_y"):
        if vec2_distance(tile_and_offset_a, tile_and_offset_b) < dist:
            collides = True        
    return collides

def advance_redhead_bullet_impulse(entity, tile_map, debug_queue, dt):
    """Apply collision-safe knockback while decaying speed toward zero."""
    try:
        frame_dt = max(0.0, float(dt))
    except (TypeError, ValueError, OverflowError):
        frame_dt = 0.0
    if not math.isfinite(frame_dt) or frame_dt <= 0.0:
        return entity.get("position", {})

    impulse = entity.get("bullet_impulse", {})
    if not isinstance(impulse, dict):
        impulse = {}
    current_speed = vec2_norm(impulse)
    duration = max(
        0.001, float(entity.get(
            "bullet_impact_duration", DEFAULT_BULLET_IMPACT_DURATION,
        )),
    )
    elapsed = max(0.0, float(entity.get("bullet_impact_elapsed", 0.0)))
    active_dt = min(frame_dt, max(0.0, duration - elapsed))
    if current_speed <= 0.000001 or active_dt <= 0.0:
        entity["bullet_impulse"] = {"x": 0.0, "y": 0.0}
        entity["bullet_impact_elapsed"] = min(duration, elapsed + frame_dt)
        return entity.get("position", {})

    deceleration = max(
        0.0, float(entity.get(
            "bullet_impact_deceleration", current_speed / duration,
        )),
    )
    collision_width, collision_height = get_entity_collision_dimensions(entity)
    maximum_step_distance = max(1.0, min(
        float(tile_map.get("tile_width", 16)),
        float(tile_map.get("tile_height", 16)),
        collision_width if collision_width > 0.0 else math.inf,
        collision_height if collision_height > 0.0 else math.inf,
    ) * 0.45)
    step_count = max(
        1, min(16, int(math.ceil(
            current_speed * active_dt / maximum_step_distance,
        ))),
    )
    step_dt = active_dt / step_count

    preserved_animation_frame = (
        entity.get("animation_frame")
        if entity.get("current_state") == "dead" else None
    )
    for _step in range(step_count):
        current_speed = vec2_norm(impulse)
        if current_speed <= 0.000001:
            impulse = {"x": 0.0, "y": 0.0}
            break
        direction = vec2_scale(impulse, 1.0 / current_speed)
        next_speed = max(0.0, current_speed - deceleration * step_dt)
        average_speed = (current_speed + next_speed) * 0.5
        movement_velocity = vec2_scale(direction, average_speed)
        entity["position"] = move_entity_with_velocity(
            entity, movement_velocity, tile_map, debug_queue, step_dt,
        )

        # Collision resolution mutates movement_velocity. Carry its surviving
        # direction forward, but retain the scalar decay calculated above.
        resolved_speed = vec2_norm(movement_velocity)
        if resolved_speed <= 0.000001 or next_speed <= 0.000001:
            impulse = {"x": 0.0, "y": 0.0}
        else:
            surviving_fraction = min(1.0, resolved_speed / average_speed)
            impulse = vec2_scale(
                vec2_scale(movement_velocity, 1.0 / resolved_speed),
                next_speed * surviving_fraction,
            )

    # Movement updates directional locomotion frames. A corpse must retain its
    # death pose while it is displaced by the same impact solver.
    if preserved_animation_frame is not None:
        entity["animation_frame"] = preserved_animation_frame

    elapsed += active_dt
    if elapsed + 0.000001 >= duration:
        impulse = {"x": 0.0, "y": 0.0}
    entity["bullet_impulse"] = impulse
    entity["bullet_impact_elapsed"] = min(duration, elapsed)
    return entity.get("position", {})


def death_state(entity, current_state, player_info, tile_map, debug_queue, dt):
    entity["death_timer"] = max(
        0.0, float(entity.get("death_timer", 0.0)),
    ) + max(0.0, dt)
    advance_redhead_bullet_impulse(entity, tile_map, debug_queue, dt)
    # Corpses move against walls during impact but do not remain dynamic actor
    # blockers once their position has been resolved.
    update_tile_manager(
        entity["position"], entity["position"], entity["id"], tile_map,
        debug_queue, True, entity=entity,
    )
    return current_state
def stagger_state(entity, current_state, player_info, tile_map, debug_queue, dt,
                  behavior_context=None):
    entity["stagger_timer"] += dt


    next_state = current_state
    advance_redhead_bullet_impulse(entity, tile_map, debug_queue, dt)

    stagger_duration = max(
        0.0,
        float(entity.get(
            "stagger_duration", DEFAULT_REDHEAD_STAGGER_DURATION,
        )),
        float(entity.get(
            "bullet_impact_duration", DEFAULT_BULLET_IMPACT_DURATION,
        )),
    )
    if entity["stagger_timer"] >= stagger_duration:
        entity["bullet_impulse"] = {"x": 0.0, "y": 0.0}
        entity["ai_velocity"] = {"x": 0.0, "y": 0.0}
        entities = (
            behavior_context.get("entities", {})
            if isinstance(behavior_context, dict) else {}
        )
        if redhead_should_flee(entity, entities, tile_map):
            next_state = "flee"
        else:
            previous_state = entity.get("previous_state_on_stagger", "idle")
            if previous_state in (
                    "angry chase", "angry and attacking", "evade"):
                next_state = previous_state
            else:
                seen_position = entity.get("last_seen_player_pos")
                if not isinstance(seen_position, dict):
                    seen_position = player_info.get("position", {})
                next_state = (
                    "angry chase"
                    if prepare_redhead_pursuit_path(
                        entity, seen_position, tile_map,
                    ) else "idle"
                )

    
    return next_state
    


def attack_state(entity, current_state, player_info, tile_map, debug_queue, audio_runtime, dt):
    player_pos = player_info.get("position",{}) # top left
    next_state = current_state
    attack_substate = get_or_set(entity, "attack_substate", "windup")
    can_see, seen_pos, _can_move = sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt,
    )
    if can_see:
        # on some interval we should also update the path to the player here...I think
        entity["last_seen_player_pos"] = copy_entity_pos(seen_pos)
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    # TODO: mismatch here between player position which is offset, turned into abs
    # and entity positions, which are currenty only abs
    player_pos_abs = get_abs_pos_from_index(player_pos, tile_map)
    entity_pos_abs = get_entity_collision_world_position(entity, tile_map)

    if not can_see and attack_substate != "committed":
        reset_redhead_attack_cycle(entity)
        return "idle"  # A searching state can replace this later.

    attack_engage_distance = get_redhead_attack_engage_distance(entity)
    attack_exit_delay = max(0.0, float(entity.get("attack_exit_delay", 1.0)))
    distance_to_player = vec2_distance(entity_pos_abs, player_pos_abs)
    if distance_to_player > attack_engage_distance:
        out_of_range_timer = max(
            0.0, float(entity.get("attack_out_of_range_timer", 0.0)),
        ) + dt
    else:
        out_of_range_timer = 0.0
    entity["attack_out_of_range_timer"] = out_of_range_timer
    if out_of_range_timer >= attack_exit_delay:
        reset_redhead_attack_cycle(entity)
        return "angry chase"
    
    # check if our distance to the player allows us to do our attack
    # if not we need to chase again to last known position
    attack_direction = get_or_set(entity, "attack_direction", {"x" : 0, "y" : 0})
    attack_windup_duration = max(
        0.0, float(entity.get("attack_windup_duration", 1.0)),
    )
    attack_timer = entity["attack_timer"]
    attack_timer += dt
    attack_range = 10
    windup_direction_window = 0.3

    if attack_timer < windup_direction_window and attack_substate == "windup":
        # set direction
        attack_direction = vec2_normalize(vec2_subtract(player_pos_abs, entity_pos_abs))
        entity["attack_direction"] = attack_direction
    
    attack_point = vec2_add(entity_pos_abs, vec2_scale(attack_direction, attack_range))
    entity["attack_point"] = attack_point

    if attack_timer >= entity["attack_cooldown"] and attack_substate == "attacking":
        attack_timer = 0
        attack_substate = "windup"

    if attack_timer > windup_direction_window and attack_substate == "windup":
        attack_substate = "committed"

    if attack_timer >= attack_windup_duration and attack_substate == "committed":
        attack_timer = 0
        attack_substate = "attacking"
        attack_point = vec2_add(entity_pos_abs, vec2_scale(attack_direction, attack_range))

        entity["attack_point"] = attack_point

        minkowski_rect = {
            "x" : player_pos_abs["x"] - player_info["entity_width"] - 12,
            "y" : player_pos_abs["y"] - player_info["entity_height"] - 12,
            "width" : 24 + player_info["entity_width"] + 12,
            "height": 24 + player_info["entity_height"] + 12
        }
        

        
        if point_in_rect(attack_point, minkowski_rect):#vec2_distance(player_pos, pickup["position"]) < pickup_rad:
            # now we do damage
            damage_per_hit = 20
            player_info["health"] -= damage_per_hit
            queue_gameplay_audio(
                audio_runtime, "stagger_impact", "player", "player",
                player_pos_abs, priority=1.4,
            )
        else:
            queue_gameplay_audio(
                audio_runtime, "melee_whoosh", f"enemy:{entity.get('id', 'unknown')}",
                "enemy", attack_point, priority=0.8,
            )
            # TODO play the miss ound

    

        


    entity["attack_timer"] = attack_timer
    entity["attack_substate"] = attack_substate

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
    # if "path_to_player" not in entity:
    #     target_tile_from_tile_map = tile_map.get("tiles")[player_pos.get("tile_y")*tile_map.get("map_width") + player_pos.get("tile_x")]
    #     start_tile_from_tile_map = tile_map.get("tiles")[entity_pos.get("tile_y")*tile_map.get("map_width") + entity_pos.get("tile_x")]
    #     path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
    #     entity["path_to_player"] = path_to_player
    #     entity["path_to_player_current_index"] = 0
    #     entity["last_seen_player_pos"] = copy_entity_pos(player_pos)        
    # waypoint_pos = entity["path_to_player"][min(entity["path_to_player_current_index"], len(entity["path_to_player"])-1)]
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
                "z_sort" : 1,
                "debug_modes" : ["pathfinding"]

            }    
            debug_queue.append(debug_item)

    # if tiles_close(entity_pos, waypoint_pos, 1) and entity["path_to_player_current_index"] < len(entity["path_to_player"]):
    #     entity["path_to_player_current_index"] += 1
    # this should be adjusted if it's the last tile and we don't wanna crowd
    # target_pos = get_abs_pos_from_index(waypoint_pos, tile_map, debug_queue)

    
    # new_position = move_entity_towards_target_abs(entity, target_pos, tile_map, debug_queue, dt)
    # we could do a raycast along positions to check if we 'hit' the target on the way maybe

    # entity["position"] = new_position
    
    # entity.get("position",{})["x"] = new_position.get("x", 0)
    # entity.get("position",{})["y"] = new_position.get("y", 0)        

    # if can_see and not tiles_equal(entity["path_to_player"][-1], entity["last_seen_player_pos"]):
    #     target_tile_from_tile_map = tile_map.get("tiles")[entity["last_seen_player_pos"]["tile_y"]*tile_map.get("map_width") + entity["last_seen_player_pos"]["tile_x"]]
    #     start_tile_from_tile_map = tile_map.get("tiles")[entity["position"].get("tile_y")*tile_map.get("map_width") + entity["position"].get("tile_x")]
    #     path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
    #     entity["path_to_player"] = path_to_player
    #     entity["path_to_player_current_index"] = 0        
    return next_state


def get_redhead_chase_target_abs(entity, player_info, tile_map, can_move):
    tile_width = tile_map.get("tile_width", 16)
    tile_height = tile_map.get("tile_height", 16)
    if can_move:
        return make_pos_abs(player_info.get("position", {}), tile_width, tile_height)
    if entity.get("path_to_player"):
        _, target = get_current_ai_waypoint_target_abs(
            entity, tile_map, arrival_epsilon=8.0,
        )
        return target
    last_seen = entity.get("last_seen_player_pos")
    if isinstance(last_seen, dict):
        return make_pos_abs(last_seen, tile_width, tile_height)
    collision_position = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    return make_pos_abs(collision_position, tile_width, tile_height)


def tactical_tile_center_position(tile_x, tile_y, tile_map):
    return {
        "tile_x": int(tile_x),
        "tile_y": int(tile_y),
        "x": tile_map.get("tile_width", 16) * 0.5,
        "y": tile_map.get("tile_height", 16) * 0.5,
    }


def entity_position_for_collision_tile_center(entity, tile_x, tile_y, tile_map):
    """Return the render-anchor position whose collision center is on a tile."""
    offset = get_entity_collision_center_offset(entity)
    return move_position_along_tiles({
        "tile_x": int(tile_x),
        "tile_y": int(tile_y),
        "x": tile_map.get("tile_width", 16) * 0.5 - offset["x"],
        "y": tile_map.get("tile_height", 16) * 0.5 - offset["y"],
    }, tile_map.get("tile_width", 16), tile_map.get("tile_height", 16))


def redhead_can_occupy_tactical_tile(entity, tile_x, tile_y, tile_map):
    if tile_not_in_bounds(tile_x, tile_y, tile_map):
        return False
    index = tile_y * tile_map["map_width"] + tile_x
    tiles = tile_map.get("tiles", [])
    if index < 0 or index >= len(tiles) or tile_is_collidable(
            tiles[index], tile_map):
        return False
    tile_width = max(1.0, float(tile_map.get("tile_width", 16)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16)))
    candidate_position = entity_position_for_collision_tile_center(
        entity, tile_x, tile_y, tile_map,
    )
    collision_box = get_entity_collision_box(
        entity, tile_map, position=candidate_position,
    )
    map_pixel_width = tile_map.get("map_width", 0) * tile_width
    map_pixel_height = tile_map.get("map_height", 0) * tile_height
    if (collision_box["x"] < 0.0 or collision_box["y"] < 0.0
            or collision_box["x"] + collision_box["width"] >= map_pixel_width
            or collision_box["y"] + collision_box["height"] >= map_pixel_height):
        return False
    footprint = make_entity_collision_points(
        candidate_position, entity, tile_map,
    )
    return is_legal_position_on_tilemap(footprint, tile_map)


def build_redhead_tactical_reachability(entity, tile_map, radius_tiles):
    """Perform one bounded local search and retain paths to every result."""
    start = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    start_key = (
        int(start.get("tile_x", -1)), int(start.get("tile_y", -1)),
    )
    if tile_not_in_bounds(start_key[0], start_key[1], tile_map):
        return {"start": start_key, "came_from": {}, "cost": {}, "depth": {}}

    radius_tiles = max(1, int(radius_tiles))
    frontier = [start_key]
    frontier_index = 0
    came_from = {start_key: None}
    cost = {start_key: 0.0}
    depth = {start_key: 0}
    occupancy_cache = {}
    tiles = tile_map.get("tiles", [])
    map_width = tile_map.get("map_width", 0)

    def can_occupy(tile_key):
        if tile_key not in occupancy_cache:
            occupancy_cache[tile_key] = redhead_can_occupy_tactical_tile(
                entity, tile_key[0], tile_key[1], tile_map,
            )
        return occupancy_cache[tile_key]

    while frontier_index < len(frontier):
        current_key = frontier[frontier_index]
        frontier_index += 1
        current_depth = depth[current_key]
        if current_depth >= radius_tiles:
            continue
        current_index = current_key[1] * map_width + current_key[0]
        if current_index < 0 or current_index >= len(tiles):
            continue
        current_tile = tiles[current_index]
        neighbours = current_tile.get("neighbours")
        if not isinstance(neighbours, dict):
            neighbours = get_neighbouring_tiles(current_tile, tile_map)
        for neighbour in filter_invalid_neighbours(neighbours, tile_map):
            next_key = (
                int(neighbour.get("tile_x", -1)),
                int(neighbour.get("tile_y", -1)),
            )
            if next_key in came_from or not can_occupy(next_key):
                continue
            diagonal = (
                next_key[0] != current_key[0]
                and next_key[1] != current_key[1]
            )
            if diagonal and (
                    not can_occupy((next_key[0], current_key[1]))
                    or not can_occupy((current_key[0], next_key[1]))):
                continue
            came_from[next_key] = current_key
            depth[next_key] = current_depth + 1
            cost[next_key] = cost[current_key] + (
                math.sqrt(2.0) if diagonal else 1.0
            )
            frontier.append(next_key)
    return {
        "start": start_key,
        "came_from": came_from,
        "cost": cost,
        "depth": depth,
    }


def reconstruct_tactical_tile_path(reachability, goal_key):
    came_from = reachability.get("came_from", {})
    if goal_key not in came_from:
        return []
    path = []
    current = goal_key
    while current is not None:
        path.append({"tile_x": current[0], "tile_y": current[1]})
        current = came_from[current]
    path.reverse()
    return path


def redhead_evade_cover_score(entity, candidate_tile, player_info, tile_map):
    """Extension seam for later authored or geometric cover evaluation."""
    return 0.0


def make_redhead_evade_scoring_context(entity, player_info, chase_target,
                                        tile_map, settings=None):
    if settings is None:
        settings = get_redhead_evade_settings(entity)
    tile_width = max(1.0, float(tile_map.get("tile_width", 16)))
    tile_height = max(1.0, float(tile_map.get("tile_height", 16)))
    tile_scale = max(1.0, (tile_width + tile_height) * 0.5)
    collision_position = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    entity_world = make_pos_abs(
        collision_position, tile_width, tile_height,
    )
    player_world = make_pos_abs(
        player_info.get("position", {}), tile_width, tile_height,
    )
    aim_direction = vec2_normalize(player_info.get("aim_direction", {}))
    if vec2_norm(aim_direction) <= 0.000001:
        aim_direction = vec2_normalize(
            vec2_subtract(entity_world, player_world),
        )
    forward = vec2_normalize(vec2_subtract(chase_target, entity_world))
    if vec2_norm(forward) <= 0.000001:
        forward = vec2_scale(aim_direction, -1.0)
    current_heading = vec2_normalize(entity.get("ai_velocity", {}))
    return {
        "settings": settings,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "tile_scale": tile_scale,
        "entity_world": entity_world,
        "player_world": player_world,
        "aim_direction": aim_direction,
        "lateral_axis": {"x": -forward["y"], "y": forward["x"]},
        "current_heading": current_heading,
        "current_distance": vec2_distance(entity_world, chase_target),
    }


def score_redhead_evade_candidate(entity, candidate_key, path_cost,
                                  player_info, chase_target, tile_map,
                                  preferred_side, settings=None,
                                  scoring_context=None):
    if scoring_context is None:
        scoring_context = make_redhead_evade_scoring_context(
            entity, player_info, chase_target, tile_map, settings,
        )
    settings = scoring_context["settings"]
    tile_width = scoring_context["tile_width"]
    tile_height = scoring_context["tile_height"]
    tile_scale = scoring_context["tile_scale"]
    entity_world = scoring_context["entity_world"]
    candidate_position = tactical_tile_center_position(
        candidate_key[0], candidate_key[1], tile_map,
    )
    candidate_world = make_pos_abs(
        candidate_position, tile_width, tile_height,
    )
    candidate_delta = vec2_subtract(candidate_world, entity_world)

    player_world = scoring_context["player_world"]
    aim_direction = scoring_context["aim_direction"]
    lateral_axis = scoring_context["lateral_axis"]
    signed_lateral = vec2_dot(candidate_delta, lateral_axis) / tile_scale
    lateral_tiles = abs(signed_lateral)

    current_distance = scoring_context["current_distance"]
    candidate_distance = vec2_distance(candidate_world, chase_target)
    progress_tiles = (current_distance - candidate_distance) / tile_scale
    if progress_tiles < -settings["maximum_retreat_tiles"]:
        return None
    if lateral_tiles < settings["minimum_lateral_tiles"]:
        return None
    candidate_direction = vec2_normalize(candidate_delta)
    current_heading = scoring_context["current_heading"]
    heading_alignment = (
        vec2_dot(candidate_direction, current_heading)
        if vec2_norm(current_heading) > 0.000001 else 1.0
    )
    if heading_alignment < settings["heading_reversal_limit"]:
        return None

    player_to_candidate = vec2_subtract(candidate_world, player_world)
    aim_distance = vec2_dot(player_to_candidate, aim_direction)
    aim_distance = max(0.0, min(settings["aim_max_distance"], aim_distance))
    nearest_aim_point = vec2_add(
        player_world, vec2_scale(aim_direction, aim_distance),
    )
    aim_clearance_tiles = (
        vec2_distance(candidate_world, nearest_aim_point) / tile_scale
    )
    side_bonus = (
        1.0 if signed_lateral * preferred_side > 0.0 else 0.0
    )
    cover_score = redhead_evade_cover_score(
        entity, candidate_position, player_info, tile_map,
    )
    components = {
        "signed_lateral_tiles": signed_lateral,
        "lateral_tiles": lateral_tiles,
        "aim_clearance_tiles": aim_clearance_tiles,
        "progress_tiles": progress_tiles,
        "path_cost": path_cost,
        "preferred_side": side_bonus,
        "cover": cover_score,
        "heading_alignment": heading_alignment,
    }
    score = (
        lateral_tiles * settings["lateral_score_weight"]
        + aim_clearance_tiles * settings["aim_clearance_score_weight"]
        + progress_tiles * settings["progress_score_weight"]
        - path_cost * settings["path_cost_score_weight"]
        + side_bonus * settings["preferred_side_score"]
        + cover_score * settings["cover_score_weight"]
    )
    return {
        "tile_x": candidate_key[0],
        "tile_y": candidate_key[1],
        "score": score,
        "components": components,
    }


def choose_redhead_evade_navigation(entity, player_info, chase_target,
                                     tile_map, preferred_side=None):
    settings = get_redhead_evade_settings(entity)
    scoring_context = make_redhead_evade_scoring_context(
        entity, player_info, chase_target, tile_map, settings,
    )
    if preferred_side is None:
        lateral_velocity = vec2_dot(
            entity.get("ai_velocity", {}), scoring_context["lateral_axis"],
        )
        if abs(lateral_velocity) > 0.01:
            preferred_side = -1.0 if lateral_velocity < 0.0 else 1.0
        else:
            preferred_side = (
                -1.0 if _redhead_perception_phase(entity) < 0.5 else 1.0
            )
    preferred_side = -1.0 if float(preferred_side) < 0.0 else 1.0
    reachability = build_redhead_tactical_reachability(
        entity, tile_map, settings["search_radius_tiles"],
    )
    candidates = []
    start_key = reachability["start"]
    for candidate_key, path_cost in reachability["cost"].items():
        if candidate_key == start_key:
            continue
        candidate = score_redhead_evade_candidate(
            entity, candidate_key, path_cost, player_info, chase_target,
            tile_map, preferred_side, settings, scoring_context,
        )
        if candidate is not None:
            candidates.append(candidate)
    candidates.sort(
        key=lambda candidate: (
            -candidate["score"], candidate["tile_y"], candidate["tile_x"],
        ),
    )
    if not candidates:
        return None
    checked_candidates = 0
    for candidate in candidates:
        candidate_position = entity_position_for_collision_tile_center(
            entity, candidate["tile_x"], candidate["tile_y"], tile_map,
        )
        if not entity_position_is_legal(candidate_position, entity, tile_map):
            continue
        checked_candidates += 1
        goal_key = (candidate["tile_x"], candidate["tile_y"])
        path = reconstruct_tactical_tile_path(reachability, goal_key)
        if len(path) < 2:
            continue
        path_is_natural = True
        previous_world = scoring_context["entity_world"]
        previous_segment = None
        selected_lateral = candidate["components"]["signed_lateral_tiles"]
        for path_index, path_tile in enumerate(path[1:], start=1):
            path_world = make_pos_abs(
                tactical_tile_center_position(
                    path_tile["tile_x"], path_tile["tile_y"], tile_map,
                ), scoring_context["tile_width"], scoring_context["tile_height"],
            )
            if vec2_distance(path_world, chase_target) > (
                    scoring_context["current_distance"]
                    + settings["maximum_retreat_tiles"]
                    * scoring_context["tile_scale"] + 0.0001):
                path_is_natural = False
                break
            path_delta = vec2_subtract(
                path_world, scoring_context["entity_world"],
            )
            path_lateral = vec2_dot(
                path_delta, scoring_context["lateral_axis"],
            )
            if path_lateral * selected_lateral < -0.0001:
                path_is_natural = False
                break
            segment = vec2_normalize(vec2_subtract(path_world, previous_world))
            if (previous_segment is not None
                    and vec2_dot(segment, previous_segment)
                    < settings["heading_reversal_limit"]):
                path_is_natural = False
                break
            if path_index == 1 and vec2_norm(
                    scoring_context["current_heading"]) > 0.000001:
                if vec2_dot(
                        segment, scoring_context["current_heading"],
                ) < settings["heading_reversal_limit"]:
                    path_is_natural = False
                    break
            previous_segment = segment
            previous_world = path_world
        if path_is_natural:
            selected_side = (
                -1.0
                if candidate["components"]["signed_lateral_tiles"] < 0.0
                else 1.0
            )
            return {
                "intent": "evade",
                "goal_tile": {"tile_x": goal_key[0], "tile_y": goal_key[1]},
                "path": path,
                "waypoint_index": 1,
                "geometry_revision": int(tile_map.get("geometry_revision", 0)),
                "preferred_side": selected_side,
                "requested_side": preferred_side,
                "score": candidate["score"],
                "score_components": dict(candidate["components"]),
            }
        if checked_candidates >= settings["top_candidate_count"]:
            break
    return None


def prepare_redhead_evade_navigation(entity, player_info, chase_target,
                                      tile_map, preferred_side=None):
    navigation = choose_redhead_evade_navigation(
        entity, player_info, chase_target, tile_map, preferred_side,
    )
    if navigation is None:
        return False
    entity["navigation"] = navigation
    entity["evade_side"] = navigation["preferred_side"]
    entity["evade_stuck_timer"] = 0.0
    return True


def get_redhead_evade_waypoint(entity, tile_map, arrival_epsilon=6.0):
    navigation = entity.get("navigation", {})
    if not isinstance(navigation, dict) or navigation.get("intent") != "evade":
        return None, None
    path = navigation.get("path", [])
    if not isinstance(path, list) or not path:
        return None, None
    waypoint_index = max(1, int(navigation.get("waypoint_index", 1)))
    tile_offset = {
        "x": tile_map.get("tile_width", 16) * 0.5,
        "y": tile_map.get("tile_height", 16) * 0.5,
    }
    collision_position = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    while waypoint_index < len(path) and tiles_close(
            collision_position, path[waypoint_index], tile_offset,
            arrival_epsilon):
        waypoint_index += 1
    navigation["waypoint_index"] = waypoint_index
    if waypoint_index >= len(path):
        return None, None
    waypoint = path[waypoint_index]
    return waypoint, get_abs_pos_from_index_given_offset(
        waypoint, tile_offset, tile_map,
    )


def move_redhead_in_direction(entity, direction, tile_map, debug_queue, dt,
                              speed_multiplier=1.0):
    return move_redhead_with_locomotion(
        entity, direction, tile_map, debug_queue, dt,
        speed_multiplier=speed_multiplier,
    )


def clear_redhead_evade_navigation(entity):
    navigation = entity.get("navigation")
    if isinstance(navigation, dict) and navigation.get("intent") == "evade":
        entity.pop("navigation", None)
    entity["evade_stuck_timer"] = 0.0


def clear_redhead_flee_navigation(entity):
    navigation = entity.get("navigation")
    if isinstance(navigation, dict) and navigation.get("intent") == "flee":
        entity.pop("navigation", None)


def hold_redhead_near_flee_ally(entity):
    """Stop locomotion while a wounded redhead shelters with an ally."""
    entity["ai_velocity"] = {"x": 0.0, "y": 0.0}


def get_redhead_flee_allies(entity, entities, tile_map, radius_tiles):
    tile_scale = max(
        1.0, (float(tile_map.get("tile_width", 16))
              + float(tile_map.get("tile_height", 16))) * 0.5,
    )
    radius = max(1, int(radius_tiles)) * tile_scale
    entity_world = get_entity_collision_world_position(entity, tile_map)
    allies = []
    for ally_id, ally in (entities or {}).get("brains", {}).items():
        if (not isinstance(ally, dict) or ally is entity
                or ally.get("type") != "red head"
                or ally.get("current_state") == "dead"
                or float(ally.get("health", 0.0)) <= 0.0):
            continue
        ally_world = get_entity_collision_world_position(ally, tile_map)
        distance = vec2_distance(entity_world, ally_world)
        if distance <= radius:
            allies.append((distance, str(ally_id), ally_id, ally, ally_world))
    allies.sort(key=lambda item: (item[0], item[1]))
    return allies


def choose_redhead_flee_navigation(entity, player_info, tile_map, entities):
    """Plan one bounded local retreat toward a nearby living ally."""
    settings = get_redhead_flee_settings(entity)
    allies = get_redhead_flee_allies(
        entity, entities, tile_map, settings["ally_search_radius_tiles"],
    )
    if not allies:
        return None
    reachability = build_redhead_tactical_reachability(
        entity, tile_map, settings["local_plan_radius_tiles"],
    )
    start_key = reachability["start"]
    reachable_keys = [
        key for key in reachability["cost"] if key != start_key
    ]
    if not reachable_keys:
        return None

    tile_width = float(tile_map.get("tile_width", 16))
    tile_height = float(tile_map.get("tile_height", 16))
    player_world = make_pos_abs(
        player_info.get("position", {}), tile_width, tile_height,
    )
    entity_world = get_entity_collision_world_position(entity, tile_map)
    away_direction = vec2_normalize(
        vec2_subtract(entity_world, player_world),
    )
    # Prefer a nearby ally that also lies along the retreating hemisphere.
    _, _, target_ally_id, _ally, target_ally_world = min(
        allies,
        key=lambda item: (
            item[0] - max(0.0, vec2_dot(
                vec2_subtract(item[4], entity_world), away_direction,
            )) * 0.5,
            item[1],
        ),
    )

    def candidate_world(key):
        return make_pos_abs(
            tactical_tile_center_position(key[0], key[1], tile_map),
            tile_width, tile_height,
        )

    current_ally_distance = vec2_distance(entity_world, target_ally_world)
    improving = [
        key for key in reachable_keys
        if vec2_distance(candidate_world(key), target_ally_world)
        < current_ally_distance - 0.001
    ]
    if not improving:
        return None
    goal_key = min(
        improving,
        key=lambda key: (
            vec2_distance(candidate_world(key), target_ally_world)
            - 0.20 * vec2_distance(candidate_world(key), player_world),
            reachability["cost"][key], key[1], key[0],
        ),
    )

    path = reconstruct_tactical_tile_path(reachability, goal_key)
    if len(path) < 2:
        return None
    return {
        "intent": "flee",
        "goal_tile": {"tile_x": goal_key[0], "tile_y": goal_key[1]},
        "path": path,
        "waypoint_index": 1,
        "geometry_revision": int(tile_map.get("geometry_revision", 0)),
        "target_ally_id": target_ally_id,
        "replan_timer": 0.0,
    }


def get_redhead_flee_waypoint(entity, tile_map):
    navigation = entity.get("navigation", {})
    if not isinstance(navigation, dict) or navigation.get("intent") != "flee":
        return None, None
    path = navigation.get("path", [])
    if not isinstance(path, list) or not path:
        return None, None
    waypoint_index = max(1, int(navigation.get("waypoint_index", 1)))
    tile_offset = {
        "x": tile_map.get("tile_width", 16) * 0.5,
        "y": tile_map.get("tile_height", 16) * 0.5,
    }
    collision_position = offset_entity_position_for_collision(
        entity.get("position", {}), entity, tile_map,
    )
    while waypoint_index < len(path) and tiles_close(
            collision_position, path[waypoint_index], tile_offset, 6.0):
        waypoint_index += 1
    navigation["waypoint_index"] = waypoint_index
    if waypoint_index >= len(path):
        return None, None
    waypoint = path[waypoint_index]
    return waypoint, get_abs_pos_from_index_given_offset(
        waypoint, tile_offset, tile_map,
    )


def flee_redhead_state(entity, current_state, player_info, tile_map,
                        debug_queue, dt, behavior_context=None):
    # Also cover old/saved entities that were already in flee when loaded and
    # therefore do not receive a fresh state-entry callback.
    entity["has_fled"] = True
    settings = get_redhead_flee_settings(entity)
    entities = (
        behavior_context.get("entities", {})
        if isinstance(behavior_context, dict) else {}
    )
    nearby_allies = get_redhead_flee_allies(
        entity, entities, tile_map, settings["ally_search_radius_tiles"],
    )
    if not nearby_allies:
        clear_redhead_flee_navigation(entity)
        entity["flee_plan_retry_timer"] = 0.0
        return "angry chase"

    # Arrival completes the one-shot retreat. Idle perception is then free to
    # notice the player and begin a new chase, but the flee gate stays spent.
    if nearby_allies[0][0] <= settings["ally_arrival_distance"]:
        clear_redhead_flee_navigation(entity)
        entity["flee_plan_retry_timer"] = 0.0
        hold_redhead_near_flee_ally(entity)
        entity.pop("perception_runtime", None)
        return "idle"

    navigation = entity.get("navigation", {})
    retry_timer = max(
        0.0, float(entity.get("flee_plan_retry_timer", 0.0))
        - max(0.0, dt),
    )
    entity["flee_plan_retry_timer"] = retry_timer
    navigation_valid = (
        isinstance(navigation, dict)
        and navigation.get("intent") == "flee"
        and int(navigation.get("geometry_revision", -1))
        == int(tile_map.get("geometry_revision", 0))
    )
    if navigation_valid:
        navigation["replan_timer"] = max(
            0.0, float(navigation.get("replan_timer", 0.0)),
        ) + max(0.0, dt)
        target_id = navigation.get("target_ally_id")
        target = entities.get("brains", {}).get(target_id)
        target_invalid = target_id is not None and (
            not isinstance(target, dict)
            or target.get("current_state") == "dead"
            or float(target.get("health", 0.0)) <= 0.0
        )
        if (target_invalid
                or navigation["replan_timer"] >= settings["replan_interval"]):
            navigation_valid = False

    if not navigation_valid:
        if retry_timer > 0.0:
            hold_redhead_near_flee_ally(entity)
            return current_state
        if isinstance(behavior_context, dict):
            remaining_plans = int(
                behavior_context.get("flee_plans_remaining", 1),
            )
            if remaining_plans <= 0:
                return current_state
            behavior_context["flee_plans_remaining"] = remaining_plans - 1
        navigation = choose_redhead_flee_navigation(
            entity, player_info, tile_map, entities,
        )
        if navigation is None:
            clear_redhead_flee_navigation(entity)
            entity["flee_plan_retry_timer"] = settings["replan_interval"]
            hold_redhead_near_flee_ally(entity)
            return current_state
        entity["flee_plan_retry_timer"] = 0.0
        entity["navigation"] = navigation

    waypoint, waypoint_target = get_redhead_flee_waypoint(entity, tile_map)
    if waypoint is None:
        clear_redhead_flee_navigation(entity)
        hold_redhead_near_flee_ally(entity)
        return current_state
    entity["position"] = move_entity_towards_target_abs(
        entity, waypoint_target, tile_map, debug_queue, dt,
        arrival_radius=settings["waypoint_arrival_radius"],
        speed_multiplier=settings["speed_multiplier"],
    )
    return current_state


def evade_redhead_state(entity, current_state, player_info, tile_map,
                         debug_queue, dt):
    settings = get_redhead_evade_settings(entity)
    can_see, seen_pos, _can_move = sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt,
    )
    if can_see:
        entity["last_seen_player_pos"] = copy_entity_pos(
            seen_pos if isinstance(seen_pos, dict) else player_info["position"],
        )
        entity["breadcrumb_timer"] = 0.0
    else:
        entity["breadcrumb_timer"] = max(
            0.0, float(entity.get("breadcrumb_timer", 0.0)),
        ) + max(0.0, dt)

    tile_width = tile_map.get("tile_width", 16)
    tile_height = tile_map.get("tile_height", 16)
    chase_target = make_pos_abs(
        player_info.get("position", {}), tile_width, tile_height,
    )
    navigation = entity.get("navigation", {})
    navigation_valid = (
        isinstance(navigation, dict)
        and navigation.get("intent") == "evade"
        and int(navigation.get("geometry_revision", -1))
        == int(tile_map.get("geometry_revision", 0))
    )
    if not navigation_valid:
        preferred_side = (
            navigation.get("preferred_side")
            if isinstance(navigation, dict) else None
        )
        if not prepare_redhead_evade_navigation(
                entity, player_info, chase_target, tile_map, preferred_side):
            clear_redhead_evade_navigation(entity)
            return "angry chase"
        navigation = entity["navigation"]

    waypoint, waypoint_target = get_redhead_evade_waypoint(
        entity, tile_map,
    )
    if waypoint is None:
        clear_redhead_evade_navigation(entity)
        return "angry chase"

    before_world = make_pos_abs(
        entity.get("position", {}), tile_width, tile_height,
    )
    movement_settings = get_redhead_movement_settings(entity)
    entity["position"] = move_entity_towards_target_abs(
        entity, waypoint_target, tile_map, debug_queue, dt,
        arrival_radius=settings["waypoint_arrival_radius"],
        speed_multiplier=movement_settings["evade_speed_multiplier"],
    )
    after_world = make_pos_abs(
        entity.get("position", {}), tile_width, tile_height,
    )
    moved_distance = vec2_distance(before_world, after_world)
    ai_velocity = entity.get("ai_velocity", {})
    ai_speed = math.hypot(
        float(ai_velocity.get("x", 0.0)) if isinstance(ai_velocity, dict) else 0.0,
        float(ai_velocity.get("y", 0.0)) if isinstance(ai_velocity, dict) else 0.0,
    )
    if moved_distance <= 0.01 and ai_speed <= 1.0:
        entity["evade_stuck_timer"] = max(
            0.0, float(entity.get("evade_stuck_timer", 0.0)),
        ) + max(0.0, dt)
    else:
        entity["evade_stuck_timer"] = 0.0
    if entity["evade_stuck_timer"] >= settings["stuck_replan_delay"]:
        preserved_side = float(navigation.get("preferred_side", 1.0))
        if not prepare_redhead_evade_navigation(
                entity, player_info, chase_target, tile_map, preserved_side):
            clear_redhead_evade_navigation(entity)
            return "angry chase"

    entity["evade_elapsed"] = max(
        0.0, float(entity.get("evade_elapsed", 0.0)),
    ) + max(0.0, dt)

    if debug_queue is not None:
        active_navigation = entity.get("navigation", navigation)
        active_path = active_navigation.get("path", [])
        active_index = int(active_navigation.get("waypoint_index", 1))
        for path_index, path_tile in enumerate(active_path):
            debug_queue.append({
                "type": "tile",
                "tile_x": path_tile.get("tile_x", 0),
                "tile_y": path_tile.get("tile_y", 0),
                "tile_width": tile_width,
                "tile_height": tile_height,
                "color": "PURPLE" if path_index >= active_index else "PINK",
                "drawing_function": draw_debug_tile,
                "z_sort": 1,
                "debug_modes": ["pathfinding"],
            })

    player_world = make_pos_abs(
        player_info.get("position", {}), tile_width, tile_height,
    )
    entity_world = get_entity_collision_world_position(entity, tile_map)
    if vec2_distance(entity_world, player_world) <= (
            get_redhead_attack_engage_distance(entity)):
        clear_redhead_evade_navigation(entity)
        return "angry and attacking"
    if entity["evade_elapsed"] >= float(entity.get(
            "evade_duration", settings["duration_max"])):
        clear_redhead_evade_navigation(entity)
        return "angry chase"
    return current_state


def angry_chase_state(entity, current_state, player_info, tile_map, debug_queue, audio_runtime, dt):

    player_pos = player_info["position"]
    # this state exists for 
    # entities to get into position to attack the player

    # for enemies with a ranged attack
    # that means a line of sight usually

    # for melee enemies, that means close enough 
    # to a point around the edge of the player

    #

    # We need a 'transition into 
    # portion of these state functions because there's some book keeping
    # that will need to be done only once
    # TODO do that here
    
    next_state = current_state
    can_see, seen_pos, can_move = sample_redhead_player_perception(
        entity, player_info, tile_map, debug_queue, dt,
        include_direct_movement=True,
    )
    breadcrumb_timer = get_or_set(entity, "breadcrumb_timer", 0)
    breadcrumb_interval = 3
    knows_of_player = False
    if can_see or (breadcrumb_timer < breadcrumb_interval): 
        knows_of_player = True
        # on some interval we should also update the path to the player here...I think
        entity["last_seen_player_pos"] = copy_entity_pos(player_pos)                    
    else:
        can_see = False
    

    # print(f"does {knows_of_player} of player")
    if can_see:
        breadcrumb_timer = 0
    else:
        breadcrumb_timer += dt

    entity["breadcrumb_timer"] = breadcrumb_timer

    entity_collide_distance = 5
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)
    # TODO: mismatch here between player position which is offset, turned into abs
    # and entity positions, which are currenty only abs
    entity_pos = entity.get("position",{})
    player_pos_abs = { "x" : player_pos.get("x",0) + player_pos.get("tile_x",0) * tile_width,
                          "y" : player_pos.get("y",0) + player_pos.get("tile_y",0) * tile_height}
        
    waypoint_pos, target_pos = (get_current_ai_waypoint_target_abs(entity, tile_map, arrival_epsilon=8.0))
    
    if can_move: 
        # print("can move here apparently")
        player_abs = make_pos_abs(player_pos, tile_width, tile_height)
        target_pos = player_abs

    if debug_queue is not None:        
        entity_abs = make_pos_abs(entity["position"], tile_width, tile_height)
        debug_item = debug_item = {
                    "type" : "line",
                    "drawing_function" : draw_debug_line,
                    "pos_start" : {"x" : entity_abs.get("x"), "y" : entity_abs.get("y")},                                        
                    "pos_end" : {"x" : target_pos.get("x"), "y" : target_pos.get("y")},                                        
                    "line_width" : 2,                    
                    "color" : "RED",
                    "z_sort" : -1,                    
                    "debug_modes" : ["collisions"]                    
                }
        debug_queue.append(debug_item)


    direct_arrival_radius = (
        get_redhead_attack_engage_distance(entity)
        if can_move else None
    )
    new_position = move_entity_towards_target_abs(
        entity, target_pos, tile_map, debug_queue, dt,
        arrival_radius=direct_arrival_radius,
    )
    # we could do a raycast along positions to check if we 'hit' the target on the way maybe

    entity["position"] = new_position
    
    # entity.get("position",{})["x"] = new_position.get("x", 0)
    # entity.get("position",{})["y"] = new_position.get("y", 0)        

    dest_threshold = get_redhead_attack_engage_distance(entity)
    give_up_threshold = 10

    

    

    new_collision_position = offset_entity_position_for_collision(
        new_position, entity, tile_map,
    )
    if vec2_distance(get_abs_pos_from_index(new_collision_position, tile_map), get_abs_pos_from_index(player_pos, tile_map)) <= dest_threshold:
        next_state = "angry and attacking"

    
    if not knows_of_player and entity["path_to_player_current_index"] == len(entity["path_to_player"]):
        # so here....you could either
        # go into a "start looking around in all directions" state
        # OR
        # maybe simulate a 'guess' by picking a random
        # valid tile 'nearish' the player?
        # OR
        # 
        get_or_set(entity, "give_up_time", 0)
        entity["give_up_time"] += dt
        if entity["give_up_time"] > give_up_threshold:
            next_state = "idle"

    
    if knows_of_player and not tiles_equal(entity["path_to_player"][-1], entity["last_seen_player_pos"]) and not can_move:
        target_tile_from_tile_map = tile_map.get("tiles")[entity["last_seen_player_pos"]["tile_y"]*tile_map.get("map_width") + entity["last_seen_player_pos"]["tile_x"]]
        collision_position = offset_entity_position_for_collision(
            entity["position"], entity, tile_map,
        )
        start_tile_from_tile_map = tile_map.get("tiles")[collision_position.get("tile_y")*tile_map.get("map_width") + collision_position.get("tile_x")]
        path_to_player = reconstruct_path(a_star_path(start_tile_from_tile_map, target_tile_from_tile_map, tile_map), target_tile_from_tile_map, start_tile_from_tile_map)
        entity["path_to_player"] = path_to_player
        entity["path_to_player_current_index"] = min(1, len(path_to_player) -1)
    if (next_state == current_state
            and update_redhead_evade_trigger(
                entity, player_info, tile_map, can_see, dt,
            )):
        if prepare_redhead_evade_navigation(
                entity, player_info, player_pos_abs, tile_map):
            next_state = "evade"
        else:
            entity["evade_retry_timer"] = get_redhead_evade_settings(
                entity,
            )["failed_retry_delay"]
    return next_state



def apply_force(entity, force):
    # force is acceleration really
    # f = ma, force has a direction and a magnitude
    # a = f/m 

    # velocity is a function of acceleration
    # no friction means no slow down

    # so if we go the 
    pass
    

def consume_redhead_pending_sound_chase(entity, current_state, tile_map):
    """Resolve a heard-player chase request at the normal AI update boundary."""
    pending = entity.get("pending_player_sound_chase")
    if not isinstance(pending, dict):
        return None, False
    heard_position = pending.get("position")
    if not isinstance(heard_position, dict):
        entity.pop("pending_player_sound_chase", None)
        return None, False
    entity["last_heard_player_pos"] = copy_entity_pos(heard_position)
    entity["last_seen_player_pos"] = copy_entity_pos(heard_position)
    entity["breadcrumb_timer"] = 0.0
    if current_state == "dead":
        entity.pop("pending_player_sound_chase", None)
        return None, False
    if current_state in {"flee", "stagger"}:
        # Physical survival reactions finish first; the chase request remains
        # queued and is consumed after their next state transition.
        return None, False
    if current_state in {"angry chase", "angry and attacking", "evade"}:
        entity.pop("pending_player_sound_chase", None)
        return None, False

    from_cumulative = bool(pending.get("from_cumulative_startle", False))
    entity.pop("pending_player_sound_chase", None)
    if prepare_redhead_pursuit_path(entity, heard_position, tile_map):
        entity.pop("pending_awareness_stimulus", None)
        entity["pursuit_bark_pending"] = True
        return "angry chase", from_cumulative

    # Propagation and pathfinding use the same wall topology, so this is an
    # unusual footprint/path failure. Preserve a visible reaction rather than
    # retrying an expensive path search every frame.
    if current_state == "idle":
        heard_world = make_pos_abs(
            heard_position,
            tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
        )
        queue_redhead_awareness_stimulus(
            entity, "sound", heard_world, tile_map,
        )
    return None, False


def transition_entity_state(entity, current_state, player_info, tile_map,
                            debug_queue, audio_runtime, dt,
                            behavior_context=None):
    player_pos = player_info.get("position",{}) # top left
    # TODO in addition to line of sight
    # need like a line of sound / within earshot function
    timer_dt = max(0.0, dt)
    for timer_name in ("evade_cooldown_timer", "evade_retry_timer"):
        entity[timer_name] = max(
            0.0, float(entity.get(timer_name, 0.0)) - timer_dt,
        )
    if current_state != "angry chase":
        entity["evade_reaction_timer"] = 0.0

    entered_from = entity.get("previous_state")
    entered_new_state = entered_from != current_state
    entity["entered_new_state"] = entered_new_state
    if entered_new_state:
        on_redhead_state_enter(
            entity, current_state, entered_from, tile_map, audio_runtime,
        )
    
    next_state = current_state
    forced_state, sound_startle_committed = (
        consume_redhead_pending_sound_chase(
            entity, current_state, tile_map,
        )
    )
    tile_width = tile_map.get("tile_width", 0)
    tile_height = tile_map.get("tile_height", 0)    

    if forced_state is not None:
        next_state = forced_state
    elif current_state == "idle":
        next_state = idle_redhead_state(entity, current_state, player_info, tile_map, debug_queue, dt)
    elif current_state == "noticing":
        next_state = noticing_redhead_state(
            entity, current_state, player_info, tile_map, debug_queue, dt,
        )
    elif current_state == "light startle":
        next_state = light_startle_redhead_state(
            entity, current_state, player_info, tile_map, debug_queue, dt,
        )
    elif current_state == "angry chase":
        # this is essentially a 'go to last position' state
        # with maybe a different animation and / or speed
        next_state = angry_chase_state(entity, current_state, player_info, tile_map, debug_queue, audio_runtime, dt)
    elif current_state == "evade":
        next_state = evade_redhead_state(
            entity, current_state, player_info, tile_map, debug_queue, dt,
        )
    elif current_state == "flee":
        next_state = flee_redhead_state(
            entity, current_state, player_info, tile_map, debug_queue, dt,
            behavior_context,
        )
    elif current_state == "stagger":        
        next_state = stagger_state(
            entity, current_state, player_info, tile_map, debug_queue, dt,
            behavior_context,
        )
    elif current_state == "dead":        
        next_state = death_state(entity, current_state, player_info, tile_map, debug_queue, dt)        
    elif current_state == "angry and attacking":
        next_state = attack_state(entity, current_state, player_info, tile_map, debug_queue, audio_runtime, dt)
        # if alice_can_see_bob(entity, player_pos, tile_map, debug_queue):
        #     # keep try attacking if close enough
        #     pass
        # else:
        #     next_state = "idle"
    if ((current_state in ("noticing", "light startle")
            or sound_startle_committed)
            and next_state == "angry chase"):
        nearby_entities = (
            behavior_context.get("entities", {})
            if isinstance(behavior_context, dict) else {}
        )
        alert_visible_redhead_allies(
            entity, nearby_entities, tile_map, debug_queue,
        )
    entity["previous_state"] = current_state
    entity["entered_new_state"] = False

    return next_state

    



def apply_bullet_hit_to_redhead(entity, entity_id, bullet, state_before_update,
                                tile_map, audio_runtime, effects_runtime=None,
                                debug_queue=None, player_info=None,
                                impact_dt=0.0):
    was_dead = entity.get("current_state") == "dead"
    was_staggering = entity.get("current_state") == "stagger"
    if was_dead:
        entity["death_timer"] = 0.0
    else:
        entity["current_state"] = "stagger"
        entity["stagger_timer"] = 0.0
    if state_before_update != "stagger":
        entity["previous_state_on_stagger"] = state_before_update
    if isinstance(player_info, dict):
        entity["last_seen_player_pos"] = copy_entity_pos(
            player_info.get("position", {}),
        )
        entity["breadcrumb_timer"] = 0.0

    bullet_velocity = bullet.get("velocity", {})
    bullet_normalized = vec2_normalize(bullet_velocity)
    try:
        impact_speed = max(0.0, float(bullet.get(
            "impact_speed", DEFAULT_BULLET_IMPACT_SPEED,
        )))
        impact_duration = max(0.001, float(bullet.get(
            "impact_duration", DEFAULT_BULLET_IMPACT_DURATION,
        )))
        impact_cap = max(0.0, float(bullet.get(
            "combined_impact_cap", DEFAULT_BULLET_COMBINED_IMPACT_CAP,
        )))
    except (TypeError, ValueError, OverflowError):
        impact_speed = DEFAULT_BULLET_IMPACT_SPEED
        impact_duration = DEFAULT_BULLET_IMPACT_DURATION
        impact_cap = DEFAULT_BULLET_COMBINED_IMPACT_CAP
    incoming_impulse = vec2_scale(bullet_normalized, impact_speed)
    existing_impulse = entity.get("bullet_impulse", {})
    if not isinstance(existing_impulse, dict) or not (
            was_dead or was_staggering or state_before_update == "stagger"):
        existing_impulse = {"x": 0.0, "y": 0.0}
    combined_impulse = vec2_add(existing_impulse, incoming_impulse)
    combined_speed = vec2_norm(combined_impulse)
    if impact_cap > 0.0 and combined_speed > impact_cap:
        combined_impulse = vec2_scale(
            combined_impulse, impact_cap / combined_speed,
        )
        combined_speed = impact_cap
    entity["bullet_impulse"] = combined_impulse
    entity["bullet_impact_duration"] = impact_duration
    entity["bullet_impact_deceleration"] = (
        combined_speed / impact_duration if impact_duration > 0.0 else 0.0
    )
    entity["bullet_impact_elapsed"] = 0.0
    # Knockback owns movement briefly; stale chase momentum should not resume
    # immediately after the hit response.
    entity["ai_velocity"] = {"x": 0.0, "y": 0.0}
    entity["health"] = entity.get("health", 0) - 20
    world_position = make_pos_abs(
        entity.get("position", {}),
        tile_map.get("tile_width", 16), tile_map.get("tile_height", 16),
    )
    impact_position = copy_entity_pos(entity.get("position", {}))
    if entity["health"] > 0:
        blood_amount, blood_duration = 5, 0.3
        queue_gameplay_audio(
            audio_runtime, "stagger_impact", f"enemy:{entity_id}",
            "enemy", world_position, priority=1.0,
        )
    else:
        if was_dead:
            queue_gameplay_audio(
                audio_runtime, "stagger_impact", f"enemy:{entity_id}",
                "enemy", world_position, priority=0.8,
            )
            blood_amount, blood_duration = 5, 0.1
        else:
            queue_gameplay_audio(
                audio_runtime, "death_impact", f"enemy:{entity_id}",
                "enemy", world_position, priority=1.25,
            )
            blood_amount, blood_duration = 20, 0.7
        entity["current_state"] = "dead"
        entity["animation_frame"] = "death_frame_start"

    if effects_runtime is not None:
        g_effects.spawn_blood_spatter(
            effects_runtime, blood_amount, blood_duration, bullet_velocity,
            impact_position, tile_map,
        )
    if debug_queue is not None:
        debug_queue.append({
            "type": "circle",
            "drawing_function": draw_debug_circle,
            "pos": impact_position,
            "font_size": 16,
            "radius": 60,
            "color": "BLUE",
            "z_sort": -2,
            "tile_width": tile_map.get("tile_width", 16),
            "tile_height": tile_map.get("tile_height", 16),
            "debug_modes": ["damage"],
        })

    immediate_dt = max(0.0, min(float(impact_dt), impact_duration))
    if immediate_dt > 0.0:
        advance_redhead_bullet_impulse(
            entity, tile_map, debug_queue, immediate_dt,
        )
        if was_dead or entity.get("current_state") == "dead":
            update_tile_manager(
                entity["position"], entity["position"], entity["id"],
                tile_map, debug_queue, True, entity=entity,
            )
            entity["death_timer"] = immediate_dt
        else:
            entity["stagger_timer"] = immediate_dt


def update_entities(entities, tile_map, player_info, editor_mode, collision_mode, dt,
                    audio_runtime, audio_profile, debug_queue=None, effects_runtime=None):
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    if editor_mode != "play":
        return

    player_pos = player_info.get("position",{}) # top left
    live_redhead_ids = {
        entity_id
        for entity_id, actor in entities.get("brains", {}).items()
        if (isinstance(actor, dict) and actor.get("type") == "red head"
            and actor.get("current_state") != "dead"
            and float(actor.get("health", 0.0)) > 0.0)
    }
    update_actor_passthrough_runtime(tile_map, live_redhead_ids, dt)

    deletions = []

    bullet_traces = []
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
                    "debug_modes" : ["collisions"]                 
                }
                debug_queue.append(minkowski_debug_item)

                debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle_abs,
                    "pos" : player_pos_abs,                                        
                    "radius" : 8,
                    "color" : "RED",
                    "z_sort" : 0,                    
                    "debug_modes" : ["collisions"]                 
                }
                debug_queue.append(debug_item)

        if point_in_rect(player_pos_abs, minkowski_rect):#vec2_distance(player_pos, pickup["position"]) < pickup_rad:
            deletions.append({"subdict": "pickups", "id" : pickup["id"]})            
            if pickup.get("type") == "pistol_ammo_pickup":
                print("got ammo")
                player_info["ammo"]["spare_pistol"] += pickup.get("value", 0)
                queue_gameplay_audio(audio_runtime, "pickup_ammo", "player", "player", player_pos_abs, 1.1)
            elif pickup.get("type") == "health_pickup":
                print("got health")
                player_info["health"] += pickup.get("value", 0)
                queue_gameplay_audio(audio_runtime, "pickup_health", "player", "player", player_pos_abs, 1.1)
        

    if "projectiles" not in entities:
        entities["projectiles"] = {}
    for projectile in entities["projectiles"].values():
        if projectile.get("type", "") != "bullet":
            continue
        segment_start = dict(projectile["position"])
        segment_end = vec2_add(
            segment_start, vec2_scale(projectile["velocity"], dt),
        )
        wall_hit = first_solid_tile_hit_on_segment(
            segment_start, segment_end, tile_map, 2.0, debug_queue,
        )
        bullet_traces.append({
            "projectile": projectile,
            "start": segment_start,
            "end": segment_end,
            "wall_hit": wall_hit,
        })
        projectile["position"] = segment_end
        projectile["timer"] += dt
        if projectile["timer"] >= 0.6:
            deletions.append({
                "subdict": "projectiles", "id": projectile["id"],
            })
    redhead_states_before_update = {}
    enemy_stride = g_audio.normalize_audio_profile(audio_profile)["enemy_stride"]
    behavior_context = {
        "entities": entities,
        # Bound local flood fills so several wounded enemies cannot all create
        # the same-frame spike. Waiting redheads remain in flee and plan on the
        # following frames.
        "flee_plans_remaining": 1,
    }

    for entity_id, entity in entities.get("brains",{}).items():
        if entity.get("type","") == "red head":
            ensure_redhead_movement_settings(entity)
            ensure_redhead_perception_settings(entity)
            ensure_redhead_hearing_settings(entity)
            previous_audio_position = make_pos_abs(entity.get("position", {}), tile_width, tile_height)
            # he needs to know about the environment (the tilemap)
            # he needs to know about potentially other entities...
            # he definitely needs to know about the player
            # the 'other entities' is interesting because it opens up
            # bioshock like interactions where one monster could do something with another
            # I kind of like that potential
            if "old_tile" not in entity:        
                entity["old_tile"] = {}
            
            current_state = get_or_set(entity, "current_state", "idle")
            redhead_states_before_update[entity_id] = current_state
            # there's a lot of logic happening in these states!
            next_state = transition_entity_state(
                entity, current_state, player_info, tile_map, debug_queue,
                audio_runtime, dt, behavior_context,
            )
            # next_state = "idle"
            # update_tile_manager(entity["old_tile"], entity["position"], entity["id"], tile_map)
            entity["current_state"] = next_state
            pos_abs = tile_and_offset_to_absolute(tile_map, entity.get("position",{}))
            current_audio_position = make_pos_abs(entity.get("position", {}), tile_width, tile_height)
            # Seed from the actual pre-update position so the first moving frame
            # contributes collision-resolved distance without a synthetic step.
            step_state = entity.setdefault("audio_step_state", {})
            step_state.setdefault("previous_world_position", previous_audio_position)
            g_audio.update_actor_footstep_travel(
                entity, current_audio_position,
                enemy_stride,
                f"enemy:{entity_id}", "enemy", audio_runtime,
                priority=0.75, gait="walk",
            )
            if debug_queue is not None:
                debug_queue.append(
                    make_redhead_hurtbox_debug_item(entity, tile_map)
                )
                debug_queue.append(
                    make_redhead_collision_debug_item(entity, tile_map)
                )
                debug_item = {
                    "type" : "text",
                    "drawing_function" : draw_debug_text,
                    "pos" : {"x" : pos_abs.get("x",0), "y" : pos_abs.get("y",0)},                                        
                    "font_size" : 16,
                    "text" : f"{entity["current_state"]}",
                    "color" : "WHITE",
                    "z_sort" : 0,                    
                    "debug_modes" : ["entity_states"]                 
                }
                debug_queue.append(debug_item)

    bullet_targets = build_redhead_bullet_targets(
        entities.get("brains", {}), tile_map,
    )
    for trace in bullet_traces:
        projectile = trace["projectile"]
        wall_hit = trace["wall_hit"]
        enemy_hit = find_first_redhead_bullet_hit(
            trace["start"], trace["end"], entities.get("brains", {}),
            tile_map,
            wall_hit["fraction"] if wall_hit is not None else None,
            bullet_targets,
        )
        if enemy_hit is not None:
            projectile["position"] = enemy_hit["position"]
            apply_bullet_hit_to_redhead(
                enemy_hit["entity"], enemy_hit["entity_id"], projectile,
                redhead_states_before_update.get(
                    enemy_hit["entity_id"],
                    enemy_hit["entity"].get("current_state", "idle"),
                ),
                tile_map, audio_runtime, effects_runtime, debug_queue,
                player_info,
                impact_dt=dt * max(
                    0.0, 1.0 - float(enemy_hit.get("fraction", 1.0)),
                ),
            )
            deletions.append({
                "subdict": "projectiles", "id": projectile["id"],
            })
        elif wall_hit is not None:
            projectile["position"] = wall_hit["position"]
            queue_gameplay_audio(
                audio_runtime, "bullet_wall_impact",
                f"projectile:{projectile['id']}", "world",
                wall_hit["position"], priority=0.9,
            )
            deletions.append({
                "subdict": "projectiles", "id": projectile["id"],
            })

    for deletion in deletions:
        sublist = deletion.get("subdict")
        id = deletion.get("id")
        if id in entities[sublist]:
            del entities[sublist][id]

def make_tile_x_y(x, y):
    return {"tile_x" : x, "tile_y" : y}

def pathfind_test_on_player(player_info, tile_map, game_camera, debug_queue = None):
    if "path" not in player_info:
        player_info["test_path"] = []
    mouse_pos_world = g_ui.get_mouse_position()
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
                "z_sort" : 1,
                "debug_modes" : ["pathfinding"]                 

            }    
            debug_queue.append(debug_item)


def point_in_rect(point_position, rectangle):
    rect_left = rectangle["x"]
    rect_right = rectangle["x"] + rectangle["width"]
    rect_top = rectangle["y"]
    rect_bottom = rectangle["y"] + rectangle["height"]
    return point_position["x"] >= rect_left and point_position["x"] <= rect_right and point_position["y"] >= rect_top and point_position["y"] <= rect_bottom 
    

def update_player_position(tile_map, entity, editor_mode, collision_mode, dt,
                           audio_runtime, audio_profile, debug_queue=None):
    if editor_mode != "play":
        return entity.get("position", {})

    player_velocity = get_or_set(entity, "player_velocity", {"x": 0.0, "y": 0.0})

    player_speed_max = 35.0

    aiming = entity.get("aiming", False)
    running = pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT)
    if running:
        player_speed_max = 65.0

    if aiming:
        player_speed_max = 20.0

    player_accel = 1500.0
    player_reverse_accel = 3000.0
    player_decel = 1500.0

    direction_vector = {
        "x": 0.0,
        "y": 0.0,
    }

    if pr.is_key_down(pr.KeyboardKey.KEY_A):
        direction_vector["x"] -= 1.0

    if pr.is_key_down(pr.KeyboardKey.KEY_D):
        direction_vector["x"] += 1.0

    if pr.is_key_down(pr.KeyboardKey.KEY_W):
        direction_vector["y"] -= 1.0

    if pr.is_key_down(pr.KeyboardKey.KEY_S):
        direction_vector["y"] += 1.0

    has_movement_input = vec2_norm(direction_vector) > 0

    if has_movement_input:
        direction_vector = vec2_normalize(direction_vector)

        target_velocity = vec2_scale(direction_vector, player_speed_max)

        acceleration = player_accel

        # Accelerate more strongly when changing to a genuinely
        # opposing direction.
        if vec2_dot(player_velocity, target_velocity) < 0:
            acceleration = player_reverse_accel

        player_velocity = vec2_move_towards(player_velocity, target_velocity, acceleration * dt)

    else:
        # No input: approach a complete stop.
        player_velocity = vec2_move_towards(player_velocity, {"x": 0.0, "y": 0.0}, player_decel * dt)

    # move_entity_with_velocity mutates this velocity to contain
    # the collision-resolved velocity. 
    new_pos = move_entity_with_velocity(entity, player_velocity, tile_map, debug_queue, dt)

    entity["player_velocity"] = player_velocity
    old_world = make_pos_abs(entity.get("position", {}), tile_map["tile_width"], tile_map["tile_height"])
    new_world = make_pos_abs(new_pos, tile_map["tile_width"], tile_map["tile_height"])
    step_state = entity.setdefault("audio_step_state", {})
    step_state.setdefault("previous_world_position", old_world)
    profile = g_audio.normalize_audio_profile(audio_profile)
    stride = profile["player_run_stride"] if running else profile["player_walk_stride"]
    g_audio.update_actor_footstep_travel(
        entity, new_world, stride, "player", "player", audio_runtime,
        priority=1.5, gait="run" if running else "walk",
    )

    return new_pos



def get_player_center_screen_space(tile_width, tile_height, player_pos, game_camera):
    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] - game_camera.x + 12, tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y + 12)    

def get_player_center_world_space(tile_width, tile_height, player_pos, game_camera):
    player_render_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"] + 12, tile_height * player_pos["tile_y"] + player_pos["y"] + 12)    

def apply_force():
    # A = F / m
    pass

def update_player_interaction(tile_map, entity, game_camera, entities, audio_runtime, dt, debug_state, debug_queue,
                              aim_input_enabled=True, mouse_delta=None):
    player_pos = entity["position"]
    tile_height = tile_map["tile_height"]
    tile_width = tile_map["tile_width"]
    # really need to have a 'player center' position
    player_render_pos = {"x" : tile_width * player_pos["tile_x"] + player_pos["x"] - game_camera.x, "y" : tile_height * player_pos["tile_y"] + player_pos["y"] - game_camera.y}
    

    player_pos_center = pr.Vector2(tile_width * player_pos["tile_x"] + player_pos["x"], tile_height * player_pos["tile_y"] + player_pos["y"])    

    arm_length = 20

    ensure_player_weapon_transition_state(entity)
    aim_requested = pr.is_mouse_button_down(
        pr.MouseButton.MOUSE_BUTTON_RIGHT,
    )
    entity["aim_requested"] = aim_requested
    update_player_weapon_transition(
        entity, aim_requested, dt, audio_runtime, player_pos_center,
    )
    # Aiming intent slows movement immediately; readiness and firing use their
    # own transition-aware gates below.
    entity["aiming"] = aim_requested

    if mouse_delta is None:
        mouse_delta = pr.get_mouse_delta()
    if aim_input_enabled:
        internal_mouse_delta = scale_mouse_delta_to_internal(
            mouse_delta.x, mouse_delta.y, pr.get_screen_width(), pr.get_screen_height(),
        )
        aim_heading_normal = apply_player_mouse_aim_delta(
            entity, internal_mouse_delta["x"], internal_mouse_delta["y"],
        )
    else:
        aim_heading_normal = ensure_player_aim_state(entity)
    update_player_aim_accuracy(entity, aim_requested, dt)
    weapon_can_fire = player_weapon_can_fire(entity, aim_requested)
    entity["weapon_can_fire"] = weapon_can_fire
    transition_progress = ensure_player_weapon_transition_state(entity)[
        "progress"
    ]
    spawn_pos = g_render_order.player_weapon_bezier_world_position(
        {"x": player_pos_center.x, "y": player_pos_center.y},
        aim_heading_normal, arm_length, transition_progress,
    )

    if debug_queue is not None:
        debug_queue.append(make_player_collision_debug_item(entity, tile_map))
        debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle,
                    "pos" : spawn_pos,                    
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "radius" : 2,
                    "color" : "RED",
                    "z_sort" : 0,
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "debug_modes" : ["all"]
                }
        debug_queue.append(debug_item)

        debug_item = {
                    "type" : "circle",
                    "drawing_function" : draw_debug_circle,
                    "pos" : player_render_pos,                    
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "radius" : 2,
                    "color" : "PINK",
                    "z_sort" : 0,
                    "tile_width" : tile_width,
                    "tile_height" : tile_height,
                    "debug_modes" : ["all"]
                }
        debug_queue.append(debug_item)

    #pr.draw_circle(int(spawn_pos["x"] - game_camera.x), int(spawn_pos["y"] - game_camera.y), 300, pr.WHITE)

    # resulting_sounds = []

    # set direciton based on aim? or running?
    player_angle_current = angle_from_vector(aim_heading_normal)
    #player_angle_current += 180
    animation_direction = direction_from_angle(player_angle_current)
    gunshot_timer = entity.get("gunshot_timer", 0)
    entity["animation_direction"] = animation_direction
    entity["animation_frame"] = animation_frame_number_from_direction(animation_direction)

    pr.draw_text(f"player angle is {int(player_angle_current)}", 20, 30, 10, pr.RED)

    pr.draw_text(f"player health is {int(entity["health"])}", 80, 40, 10, pr.RED)

    pr.draw_text(f"player ammo is {int(entity["ammo"]["pistol"])} / {int(entity["ammo"]["spare_pistol"])}", 80, 50, 10, pr.RED)

    current_gun = "pistol" # TODO make more types of guns and make them selectable

    if entity.get("reload_state","") == "reloading":
        reload_timer = entity.get("reload_timer",0)
        reload_timer += dt
        entity["reload_timer"] = reload_timer
        if reload_timer >= get_reload_time(current_gun):
            entity["reload_timer"] = 0
            entity["reload_state"] = "reloaded"
            # reload!
            current_bullets = entity["ammo"][f"{current_gun}"]
            spare_bullets = entity["ammo"][f"spare_{current_gun}"]
            clip_size = get_clip_size(current_gun)

            bullets_we_have_room_for = clip_size - current_bullets

            
            clip_to_load = min(bullets_we_have_room_for, spare_bullets)            

            entity["ammo"][current_gun] += clip_to_load # this would allow it to go over
            #entity["ammo"][f"{current_gun}"] = max(spare_bullets, 0)
            spare_bullets -= clip_to_load                        
            entity["ammo"][f"spare_{current_gun}"] = max(spare_bullets, 0)


        # should also be able to interrupt this

    if pr.is_key_pressed(pr.KeyboardKey.KEY_R):
        if entity.get("reload_state","") != "reloading":
            queue_gameplay_audio(
                audio_runtime, "reload_start", "player", "player",
                player_pos_center, priority=1.4,
                data={"instance_key": "player:pistol_reload"},
            )
            entity["reload_state"] = "reloading"


    if (pr.is_mouse_button_pressed(pr.MouseButton.MOUSE_BUTTON_LEFT)
            and not g_mouse_is_ui_captured and weapon_can_fire):
        
        current_ammo = entity["ammo"][current_gun]
        if entity.get("reload_state","") == "reloading":
            queue_gameplay_audio(
                audio_runtime, "reload_stop", "player", "player",
                player_pos_center, priority=2.0,
                data={"instance_key": "player:pistol_reload"},
            )
            entity["reload_timer"] = 0
            entity["reload_state"] = "interrupted" # could do something with this


        if current_ammo <= 0:
            print("no bullets")
            queue_gameplay_audio(
                audio_runtime, "weapon_empty", "player", "player",
                player_pos_center, priority=1.3,
            )
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
            bullet_id = allocate_projectile_id(entities["projectiles"])
            shot_direction = sample_player_shot_direction(
                entity, aim_heading_normal,
            )
            bullet = make_projectile(
                "player", bullet_pos,
                vec2_scale(shot_direction, bullet_speed), bullet_id, "bullet",
            )
            apply_player_shot_recoil_bloom(entity)
            
            gunshot_timer = 0.07
            queue_gameplay_audio(
                audio_runtime, "gunshot", "player", "player",
                current_pos, priority=2.0,
                data={"weapon": "pistol"},
            )

            entities["projectiles"][bullet_id] = bullet

            
            current_ammo -= 1

            if g_infinite_ammo:
                current_ammo += 1

            entity["ammo"][current_gun] = current_ammo

            # spawn a bullet with our name on it
            # try playing a gunshot sound directly here
        
    
    entity["aim_direction"] = dict(aim_heading_normal)
    
    entity["gunshot_timer"] = max(0, gunshot_timer - dt)


def copy_position_dict(original):
    return {"x" : original.get("x",0), "y" : original.get("y",0), 
            "tile_x" : original.get("tile_x",0), "tile_y" : original.get("tile_y",0)}

def move_position_along_tiles(new_pos, tile_width, tile_height):

    additional_x_tiles = math.floor(new_pos["x"] / tile_width)

    additional_y_tiles = math.floor(new_pos["y"] / tile_height)

    new_pos["tile_x"] += additional_x_tiles
    new_pos["tile_y"] += additional_y_tiles

    new_pos["x"] -= additional_x_tiles * tile_width
    new_pos["y"] -= additional_y_tiles * tile_height
    
    if new_pos["tile_x"] < 0:
        new_pos["tile_x"] = 0
        new_pos["x"] = 0

    if new_pos["tile_y"] < 0:
        new_pos["tile_y"] = 0
        new_pos["y"] = 0

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


def draw_debug_rect_outline(debug_item, camera):
    width = debug_item.get("width", 0)
    height = debug_item.get("height", 0)
    color = color_map(debug_item.get("color", "PINK"))
    draw_x = int(debug_item.get("x", 0) - camera.position.x)
    draw_y = int(debug_item.get("y", 0) - camera.position.y)
    pr.draw_rectangle_lines(
        draw_x, draw_y, int(round(width)), int(round(height)), color,
    )

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
    

def draw_debug_item(debug_state, debug_item, camera):
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
    if debug_state in debug_item["debug_modes"] or "all" in debug_item["debug_modes"]:
        debug_item.get("drawing_function", lambda x, y : x)(debug_item, camera)

def find_unpickleable_values(value, path="arena", seen=None):
    if seen is None:
        seen = set()

    value_id = id(value)

    if value_id in seen:
        return

    seen.add(value_id)

    try:
        pickle.dumps(value)
        return
    except Exception:
        # don't want to handle it yet
        pass

    if isinstance(value, dict):
        for key, child in value.items():
            find_unpickleable_values(child, f"{path}[{key!r}]", seen)
        return

    if hasattr(value, "items"):
        for key, child in value.items():
            find_unpickleable_values(child, f"{path}[{key!r}]")
        return

    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            find_unpickleable_values(child, f"{path}[{index}]", seen)
        return

    print("Can't be pickled:", path, type(value), repr(value))

    


def draw_audio_stats_debug(audio_runtime):
    stats = (audio_runtime or {}).get("stats", {})
    rain_targets = stats.get("rain_loop_targets", {})
    target_summary = " ".join(
        f"{name.removeprefix('rain_')}={gain:.2f}"
        for name, gain in rain_targets.items() if gain > 0.0
    ) or "none"
    treatment = stats.get("requested_treatment", {})
    lines = (
        f"audio queued {stats.get('queued_events', 0)} accepted {stats.get('accepted_events', 0)} discarded {stats.get('discarded_events', 0)}",
        f"voices {stats.get('active_one_shot_voices', 0)} loops {stats.get('active_loop_voices', 0)} steals {stats.get('voice_steals', 0)} enemy suppress {stats.get('enemy_footstep_suppressions', 0)}",
        f"zone {stats.get('listener_zone', 0)} rain {stats.get('listener_rain_state', 'dry')} surface {stats.get('listener_tile_surface', 'generic')}",
        f"step {stats.get('last_footstep_base_surface')} + {stats.get('last_footstep_overlay')} DSP {stats.get('actual_treatment', 'gain_fallback')}",
        f"discard {stats.get('discard_reasons', {})}",
        f"ambience {stats.get('current_ambience_set')} rain targets {target_summary}",
        f"treatment LPF {treatment.get('low_pass_hz')} wet {treatment.get('wet_send', 0.0):.2f} {treatment.get('reverb_preset')}",
        f"nearest fires {[item.get('id') for item in stats.get('nearest_fire_loop_sources', [])]}",
        f"missing families {stats.get('missing_asset_families', [])}",
    )
    for index, line in enumerate(lines):
        pr.draw_text(line, 4, 151 + index * 9, 8, pr.LIME)


def draw_audio_world_debug(audio_runtime, game_camera, audio_profile, entities=None, tile_map=None):
    listener = (audio_runtime or {}).get("listener", {}).get("world_position", {})
    listener_screen = g_render_order.world_to_screen_pixel(
        listener.get("x", 0.0), listener.get("y", 0.0), game_camera,
    )
    pr.draw_circle_lines(listener_screen["x"], listener_screen["y"], 4.0, pr.LIME)
    pr.draw_circle_lines(
        listener_screen["x"], listener_screen["y"],
        float(audio_profile.get("maximum_distance", 260.0)), pr.Color(80, 220, 130, 90),
    )
    sources = []
    sources.extend((audio_runtime or {}).get("active_voices", []))
    sources.extend((audio_runtime or {}).get("loop_voices", {}).values())
    for source in sources:
        position = source.get("world_position")
        if not isinstance(position, dict):
            continue
        screen = g_render_order.world_to_screen_pixel(
            position.get("x", 0.0), position.get("y", 0.0), game_camera,
        )
        pr.draw_circle(screen["x"], screen["y"], 2.0, pr.ORANGE)
    for entity in (entities or {}).get("brains", {}).values():
        footprint = g_audio.get_corpse_contact_footprint(entity, tile_map or {})
        if footprint is None:
            continue
        screen = g_render_order.world_to_screen_pixel(
            footprint["x"] - footprint["width"] * 0.5,
            footprint["y"] - footprint["height"] * 0.5,
            game_camera,
        )
        pr.draw_rectangle_lines(
            screen["x"], screen["y"],
            int(round(footprint["width"])), int(round(footprint["height"])),
            pr.Color(205, 75, 115, 210),
        )


g_internal_width = 480
g_internal_height = 270



def update_and_render(render_target, lighting_target, main_arena, game_assets, cma_engine):
    global g_mouse_is_ui_captured
    global g_interacted_ui_this_frame 
    global g_last_interacted_ui_id
    g_interacted_ui_this_frame = 0
    # maybe we think of assets as things that can't be serialized, or are expensive to do so...
    # arena initialisation
    
    dt = pr.get_frame_time()
    # issue here when debugging, people will accumulate insane time
    dt = min(dt, 0.05)
    mouse_pos = g_ui.get_mouse_position()
    time_elapsed = main_arena.get("time_elapsed", 0.0) 
    save_interval = 200
    save_elapsed = main_arena.get("save_elapsed", 0.0) 
    player_info = main_arena.get("player_info") # really more info
    debug_state = main_arena.get("debug_state", "clear") 
    pause_state = main_arena.get("pause_state", "unpaused")     

    lighting_profile = main_arena.get("lighting_profile")

    if lighting_profile is None:
        lighting_profile = g_graphics.make_lighting_profile("inky")

    fog_profile = main_arena.get("fog_profile")

    if fog_profile is None:
        fog_profile = g_graphics.make_fog_profile("misty")

    audio_profile = g_audio.normalize_audio_profile(
        main_arena.get("audio_profile") or g_audio.make_audio_profile()
    )

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

    show_options = main_arena.get("show_options", False) 
    
    do_load_level = main_arena.get("do_load_level", False) 
    editor_mode = g_editor.migrate_editor_mode(main_arena.get("editor_mode", "tile"))
    collision_mode = main_arena.get("collision_mode", "regular")

    global g_mute   

    if pr.is_key_pressed(pr.KeyboardKey.KEY_O):
        show_options = not show_options
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F11):
        g_mute = not g_mute

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F6):
        do_load_level = not do_load_level

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F8):
        editor_mode = transition_editor_state(editor_mode)
    
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F7):
        debug_state = transition_debug_state(debug_state)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F9):
        collision_mode = transition_collision_state(collision_mode)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F2):
        game_assets["show_entity_direction_basis_debug"] = not game_assets.get("show_entity_direction_basis_debug", False)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F3):
        game_assets["show_entity_lighting_debug"] = not game_assets.get("show_entity_lighting_debug", False)
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F12):
        if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT) or pr.is_key_down(pr.KeyboardKey.KEY_RIGHT_SHIFT):
            game_assets["effect_debug_output"] = "raw" if game_assets.get("effect_debug_output", "final") == "final" else "final"
            game_assets["show_effect_stats"] = True
        else:
            game_assets["show_effect_stats"] = not game_assets.get("show_effect_stats", False)
    
    

    if not saved_files:
        saved_files = get_saved_files()

    audio_runtime = g_audio.ensure_audio_runtime(game_assets, cma_engine)
    audio_runtime["muted"] = bool(g_mute)
    textures = game_assets.get("textures")
    if not textures:
        textures = load_textures()        
        game_assets["textures"] = textures

    sprite_sheets = game_assets.get("sprite_sheets")
    if not sprite_sheets:
        sprite_sheets = load_sprite_sheets()
        game_assets["sprite_sheets"] = sprite_sheets

    shaders = game_assets.get("shaders")
    lighting_composite_shader = shaders.get("lighting_composite", {}) if shaders else {}
    entity_self_shadow_shader = shaders.get("entity_self_shadow", {}) if shaders else {}
    effect_shaders_valid = shaders and all(
        name in shaders and shaders[name].get("shader") is not None
        for name in ("effect_fire", "effect_smoke")
    )
    if not shaders or "cinematic_shadow_projection" not in shaders or "cinematic_shadow_composite" not in shaders or "render_item_outline" not in shaders or "entity_self_shadow" not in shaders or "light_posterize_enabled_location" not in lighting_composite_shader or "readability_light_texture_location" not in lighting_composite_shader or "self_shadow_mode_location" not in entity_self_shadow_shader or "self_shadow_pass_location" not in entity_self_shadow_shader or not effect_shaders_valid:
        if shaders:
            unload_shaders(shaders)
        shaders = load_shaders()
        game_assets["shaders"] = shaders

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
        tile_map = make_tile_map(100, 100, 16, 16)
    tile_map.setdefault("rain_exposure_revision", 0)
    g_audio.migrate_tile_audio_data(tile_map)

    if not entities:
        entities = {}

    g_editor.migrate_environment_data(entities)
    g_effects.discard_legacy_particle_systems(entities)
    collision_index_signature = actor_collision_index_signature(
        tile_map, player_info, entities,
    )
    if (editor_mode != "play"
            or game_assets.get("actor_collision_index_signature")
            != collision_index_signature):
        rebuild_actor_collision_index(tile_map, player_info, entities)
        game_assets["actor_collision_index_signature"] = collision_index_signature
    wind_profile = main_arena.get("wind_profile") or g_effects.make_wind_profile()
    rain_profile = g_effects.normalize_rain_profile(main_arena.get("rain_profile") or g_effects.make_rain_profile())
    if game_assets.get("effects_entities_identity") != id(entities):
        g_effects.clear_effects_runtime(game_assets)
        game_assets["effects_entities_identity"] = id(entities)
    effects_runtime = g_effects.ensure_effects_runtime(game_assets)
    ui_state = game_assets.get("ui_state")

    if ui_state is None:
        ui_state = g_ui.make_ui_state()
        game_assets["ui_state"] = ui_state

    show_editor = ui_state.get("show_editor", True)

    if pr.is_key_pressed(pr.KeyboardKey.KEY_F10):
        show_editor = not show_editor
    aim_controls_active = (
        editor_mode == "play"
        and pause_state == "unpaused"
        and not show_options
        and not do_load_level
    )
    # F10-visible editor UI keeps an absolute pointer available. Hiding it
    # captures the mouse for unbounded relative turning during normal play.
    update_play_mouse_capture(game_assets, aim_controls_active and not show_editor)
    editor_state = g_editor.get_or_create_editor_state(game_assets)
    game_assets["rain_debug"] = editor_state.get("rain_debug", {})
    g_ui.ui_begin_frame(ui_state, audio_runtime)
    g_editor.capture_editor_ui_regions(
        ui_state, editor_state, editor_mode, show_editor=show_editor,
    )

    if show_options and g_ui.ui_point_in_rect(g_ui.get_mouse_position(), pr.Rectangle(0, 0, 170, 180)):
        g_ui.ui_capture_mouse(ui_state)

    if do_load_level and g_ui.ui_point_in_rect(g_ui.get_mouse_position(), pr.Rectangle(90, 30, 340, 230)):
        g_ui.ui_capture_mouse(ui_state)

    if editor_mode == "tile" and g_ui.ui_point_in_rect(g_ui.get_mouse_position(), pr.Rectangle(330, 30, 142, 110)):
        g_ui.ui_capture_mouse(ui_state)

    g_mouse_is_ui_captured = ui_state.get("mouse_captured", False)

    

    
    

    use_mouse_screen_navigation =  ui_button_states.get("use_mouse_screen_navigation", True)
    current_tile_selection = main_arena.get("current_tile_selection", 0)
    current_shape_selection = main_arena.get("current_shape_selection", 0)
    current_tile_force_collidable = bool(main_arena.get("current_tile_force_collidable", False))


    current_entity_selection = main_arena.get("current_entity_selection", 0)

    

    

    # this is 'mutable' or at least expensive since it's a raylib/opengl call I think, don't want to spam it
    camera_3d = get_or_invoke(game_assets, "camera_3d", make_default_camera)        

    camera_physics = get_or_set(game_assets, "camera_physics", {})        
    
    
    

    screen_width = main_arena.get("screen_width")
    screen_height = main_arena.get("screen_height")
    tile_size = 32
        
    #input handling

    if pause_state != "paused":
        player_info["position"] = update_player_position(
            entity=player_info, editor_mode=editor_mode, collision_mode=collision_mode,
            dt=dt, audio_runtime=audio_runtime, audio_profile=audio_profile,
            tile_map=tile_map, debug_queue=debug_queue,
        )
        update_player_flashlight_toggle(player_info, editor_mode, pause_state, audio_runtime)
    
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
        update_entities(
            entities=entities, player_info=player_info, editor_mode=editor_mode,
            collision_mode=collision_mode, dt=dt, tile_map=tile_map,
            audio_runtime=audio_runtime, audio_profile=audio_profile,
            debug_queue=debug_queue, effects_runtime=effects_runtime,
        )
    
    if ui_state.get("focused_id") is None and editor_state.get("drag_kind") is None:
        camera_3d = update_camera(camera_3d, camera_physics=camera_physics, mode=editor_mode, player_pos=player_info.get("position",{}), dt=dt)

    if editor_mode == "play":
        aim_mouse_delta = pr.get_mouse_delta()
        if game_assets.pop("suppress_aim_mouse_delta_once", False):
            aim_mouse_delta = pr.Vector2(0.0, 0.0)
        update_player_interaction(
            tile_map, player_info, camera_3d.position, entities, audio_runtime,
            dt, debug_state, debug_queue,
            aim_input_enabled=aim_controls_active and not g_mouse_is_ui_captured,
            mouse_delta=aim_mouse_delta,
        )
        if pause_state != "paused":
            update_redhead_sound_awareness(
                entities, tile_map,
                audio_runtime.get("event_queue", []), dt,
            )
    # pathfind_test_on_player(player_info=player_info, tile_map=tile_map, game_camera=camera_3d.position, debug_queue=debug_queue)
    
    auto_reload = main_arena.get("auto_reload", True)
    # print(f"game camera is at x:{game_camera.position.x}, y: {game_camera.position.y}, z: {game_camera.position.z}")


    if pr.is_key_pressed(pr.KeyboardKey.KEY_F1):
        auto_reload = not auto_reload    
        g_ui.draw_variable_state("auto reload", auto_reload, 10, 10, 20, pr.WHITE)            
    
    if tile_map and editor_mode == "tile" and not ui_state.get("mouse_captured"):
        if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_SHIFT):
            current_shape_selection = g_ui.update_mousewheel_selection(current_shape_selection, len(g_tile_collision_shapes))
        else:
            current_tile_selection = g_ui.update_mousewheel_selection(current_tile_selection, tile_map.get("tile_types_amount", 1))

    if tile_map and editor_mode == "entity" and not ui_state.get("mouse_captured"):
        current_entity_selection = g_ui.update_mousewheel_selection(current_entity_selection, len(entity_types))

    preview_environment = editor_mode == "environment" and editor_state.get("preview_effects", True)
    render_environment_effects = editor_mode == "play" or preview_environment
    g_effects.update_effects(
        effects_runtime,
        entities.get("emitters", {}),
        wind_profile,
        time_elapsed,
        0.0 if pause_state == "paused" else dt,
        tile_map,
        update_authored=render_environment_effects,
        update_bursts=editor_mode == "play",
        respect_preview_enabled=editor_mode == "environment",
    )
    apply_effect_events_to_world(g_effects.drain_effect_events(effects_runtime), tile_map)
    fire_light_emitters = entities.get("emitters", {})
    if editor_mode == "environment":
        fire_light_emitters = {key: value for key, value in fire_light_emitters.items() if value.get("preview_enabled", True)}
    fire_lights = g_effects.build_fire_runtime_lights(fire_light_emitters, tile_map, time_elapsed) if render_environment_effects else {}
    game_assets["runtime_lights"] = g_effects.replace_fire_runtime_lights(game_assets.get("runtime_lights", {}), fire_lights)
    lighting_frame = g_graphics.prepare_lighting_frame(camera_3d.position, entities, player_info, tile_map, render_target, game_assets)
    if editor_mode == "play" and pause_state != "paused":
        update_redhead_flashlight_awareness(
            entities, player_info, tile_map, lighting_frame, dt,
        )
    prepared_flashlight = lighting_frame["prepared_by_id"].get("runtime:player_flashlight")
    sorted_world_items = [] if do_load_level else g_render_order.build_sorted_world_render_items(entities, player_info, tile_map, game_assets)
    major_entity_light_occluders = g_render_order.build_major_entity_light_occluders(sorted_world_items)
    entity_lighting_started = time.perf_counter()
    entity_self_shadow_frame = g_graphics.prepare_entity_self_shadows(sorted_world_items, lighting_frame["prepared_lights"], major_entity_light_occluders, lighting_frame["collision_grid"], game_assets.get("show_entity_lighting_debug", False))
    lighting_frame["stats"]["entity_prepare_time_ms"] = (time.perf_counter() - entity_lighting_started) * 1000.0
    render_occlusion_groups = g_render_order.build_render_occlusion_groups(sorted_world_items)
    outlined_items = g_render_order.find_items_requiring_outline(sorted_world_items, render_occlusion_groups)
    player_occluders = render_occlusion_groups.get("targets", {}).get("player", [])

    color_to_draw = pr.Color(33, 25, 68, 255)
    pr.begin_texture_mode(render_target)
    pr.clear_background(color_to_draw)
    update_render_tile_map_base(camera_3d.position, entities, tile_map, g_ui.get_mouse_position(), current_tile_selection, current_entity_selection, current_shape_selection, current_tile_force_collidable, game_assets, do_load_level, player_info, editor_mode, debug_queue=debug_queue)
    draw_world_entities(camera_3d.position, entities, tile_map, game_assets, do_load_level, player_info, editor_mode, debug_queue)
    pr.end_texture_mode()

    if render_environment_effects and not do_load_level:
        g_graphics.render_effect_group(
            render_target, camera_3d.position, game_assets, lighting_profile, None,
            "floor_lit", False, entities.get("emitters", {}), tile_map,
            wind_profile, time_elapsed, editor_mode == "environment",
        )

    if render_environment_effects and not do_load_level:
        g_graphics.render_and_apply_cinematic_entity_shadows(render_target, camera_3d.position, sorted_world_items, game_assets, prepared_flashlight)

    entity_light_target = None
    entity_readability_light_target = None

    if render_environment_effects:
        fog_light_target, readability_light_target, entity_light_target, entity_readability_light_target = g_graphics.render_prepared_lighting(lighting_frame, camera_3d.position, lighting_target, game_assets)
        g_graphics.apply_lighting(render_target, lighting_target, readability_light_target, game_assets, lighting_profile)
        g_graphics.render_effect_group(
            render_target, camera_3d.position, game_assets, lighting_profile,
            lighting_target, "world_behind", True, entities.get("emitters", {}),
            tile_map, wind_profile, time_elapsed, editor_mode == "environment",
        )

    entity_render_started = time.perf_counter()
    entity_render_frame = g_graphics.draw_sorted_world_render_items(sorted_world_items, render_target, camera_3d.position, game_assets, lighting_profile, lighting_frame["prepared_lights"] if render_environment_effects else [], entity_readability_light_target, player_info)
    lighting_frame["stats"]["entity_draw_time_ms"] = lighting_frame["stats"].get("entity_draw_time_ms", 0.0) + (time.perf_counter() - entity_render_started) * 1000.0
    lighting_frame["stats"]["entity_scratch_light_draws"] = entity_render_frame.get("scratch_light_draws", 0)
    lighting_frame["stats"]["entity_survival_draws"] = entity_render_frame.get("survival_draws", 0)
    entity_light_target = entity_render_frame.get("entity_direct_light")

    if render_environment_effects:
        g_graphics.render_effect_group(
            render_target, camera_3d.position, game_assets, lighting_profile,
            lighting_target, "world_front", True, entities.get("emitters", {}),
            tile_map, wind_profile, time_elapsed, editor_mode == "environment",
        )
        g_graphics.render_effect_group(
            render_target, camera_3d.position, game_assets, lighting_profile,
            lighting_target, "emissive", False, entities.get("emitters", {}),
            tile_map, wind_profile, time_elapsed, editor_mode == "environment",
        )
        rain_exposure_texture = g_graphics.ensure_rain_exposure_texture(game_assets, tile_map)
        g_graphics.apply_rain_composite(
            render_target, lighting_target, rain_exposure_texture, rain_profile,
            game_assets, camera_3d.position, tile_map, time_elapsed,
        )
        fog_volume_mask = g_graphics.render_fog_volume_mask(camera_3d.position, entities, tile_map, render_target, game_assets)
        g_graphics.apply_illuminated_fog(render_target, fog_light_target, fog_volume_mask, game_assets, fog_profile, camera_3d.position, time_elapsed)

    g_graphics.draw_render_item_occlusion_outlines(render_target, outlined_items, camera_3d.position, game_assets)

    pr.begin_texture_mode(render_target)

    if debug_queue:
        debug_queue = sorted(debug_queue, key=lambda x: x.get("z_sort", 0), reverse=True)
        for debug_item in debug_queue:
            draw_debug_item(debug_state, debug_item, camera=camera_3d)

    if game_assets.get("show_lighting_stats", False) and render_environment_effects:
        g_graphics.draw_lighting_stats_debug(lighting_frame["stats"])
    if game_assets.get("show_effect_stats", False) and render_environment_effects:
        g_graphics.draw_effect_stats_debug(effects_runtime)
    if editor_state.get("rain_debug", {}).get("show_stats", False) and render_environment_effects:
        g_graphics.draw_rain_stats_debug(game_assets)

    if editor_mode != "play" and game_assets.get("show_cinematic_shadow_debug", False):
        g_graphics.draw_cinematic_shadow_debug(camera_3d.position, sorted_world_items, game_assets, prepared_flashlight)

    if editor_mode != "play" and game_assets.get("show_render_order_debug", False):
        draw_sorted_world_debug(sorted_world_items, player_occluders, camera_3d.position, outlined_items)

    if editor_mode != "play" and game_assets.get("show_entity_lighting_debug", False):
        g_graphics.draw_entity_self_shadow_debug(sorted_world_items, major_entity_light_occluders, entity_self_shadow_frame, camera_3d.position, game_assets, lighting_profile, entity_light_target, entity_readability_light_target)

    full_entity_lighting_debug = editor_mode != "play" and game_assets.get("show_entity_lighting_debug", False)
    if game_assets.get("show_entity_direction_basis_debug", False) and not full_entity_lighting_debug:
        g_graphics.draw_entity_direction_basis_debug(sorted_world_items, camera_3d.position, lighting_frame["prepared_lights"])

    audio_debug = editor_state.get("audio_debug", {})
    if audio_debug.get("show_stats", False):
        draw_audio_stats_debug(audio_runtime)
    if audio_debug.get("show_world", False):
        draw_audio_world_debug(
            audio_runtime, camera_3d.position, audio_profile, entities, tile_map,
        )
    if (audio_debug.get("show_world", False)
            or audio_debug.get("show_acoustic_zones", False)
            or audio_debug.get("show_contact_overlays", False)):
        g_editor.draw_audio_tile_overlays(
            {
                "tile_edit_mode": "appearance",
                "show_acoustic_zone_overlay": audio_debug.get("show_acoustic_zones", False),
                "show_footstep_overlay": (
                    audio_debug.get("show_world", False)
                    or audio_debug.get("show_contact_overlays", False)
                ),
            },
            "audio_debug", camera_3d.position, tile_map,
        )

    g_editor.draw_rain_exposure_overlay(editor_state, editor_mode, camera_3d.position, tile_map)
    g_editor.draw_audio_tile_overlays(editor_state, editor_mode, camera_3d.position, tile_map)
    if editor_mode == "entity":
        g_editor.draw_gameplay_entity_selection(
            editor_state, entities, camera_3d.position, tile_map,
        )
    editor_mode = g_editor.draw_editor_overlay(
        ui_state, editor_state, editor_mode, entities, lighting_profile,
        fog_profile, wind_profile, camera_3d.position, tile_map, show_editor,
        rain_profile=rain_profile, audio_profile=audio_profile,
        audio_runtime=audio_runtime,
        redhead_movement_defaults=REDHEAD_MOVEMENT_DEFAULTS,
        redhead_evade_defaults=REDHEAD_EVADE_DEFAULTS,
        redhead_perception_defaults=REDHEAD_PERCEPTION_DEFAULTS,
        redhead_flee_defaults=REDHEAD_FLEE_DEFAULTS,
    )
    if editor_mode == "tile":
        g_editor.draw_tile_edit_controls(ui_state, editor_state, tile_map)
        if editor_state.get("tile_edit_mode", "appearance") == "appearance":
            tile_type = tile_map["tile_types"][current_tile_selection]
            draw_tile_texture_from_type(game_assets, tile_type, 275, 42, current_shape_selection, pr.PINK if current_tile_force_collidable else pr.WHITE)
            pr.draw_text(tile_type.get("type", ""), 275, 32, 8, pr.WHITE)
            pr.draw_text(g_tile_collision_shapes[current_shape_selection], 275, 60, 8, pr.WHITE)
            current_tile_force_collidable, _ = g_ui.ui_checkbox(
                ui_state,
                "tile:force_collidable",
                "force solid",
                current_tile_force_collidable,
                pr.Rectangle(332, 61, 92, 14),
            )
            tile_type["audio_surface"], _ = g_ui.ui_dropdown(
                ui_state, "tile:audio_surface", "sound", tile_type.get("audio_surface", "generic"),
                g_audio.AUDIO_SURFACES, pr.Rectangle(332, 78, 138, 15), 6,
            )
    elif editor_mode == "entity":
        pr.draw_text(entity_types[current_entity_selection], 275, 42, 8, pr.WHITE)

    if show_options:
        if g_ui.do_button(audio_runtime, pr.Vector2(10, 100), name="reload assets"):
            unload_shaders(game_assets["shaders"])
            game_assets["textures"] = None
            game_assets["sprite_sheets"] = None
            game_assets["shaders"] = None
            g_audio.clear_audio_runtime(game_assets)
            audio_runtime = g_audio.ensure_audio_runtime(game_assets, cma_engine)

        if g_ui.do_button(audio_runtime, pr.Vector2(10, 140), name="reset player"):
            player_info = None

    reset_all = False

    if show_options and g_ui.do_button(audio_runtime, pr.Vector2(10, 42), name="reset all"):
        player_info = None
        tile_map = None
        game_assets["textures"] = None
        entities = None
        reset_all = True
        fog_profile = None
        lighting_profile = None
        wind_profile = g_effects.make_wind_profile()
        rain_profile = g_effects.make_rain_profile()
        audio_profile = g_audio.make_audio_profile()
        g_effects.clear_effects_runtime(game_assets)
        game_assets.pop("effects_entities_identity", None)
        g_graphics.clear_rain_runtime_assets(game_assets)
        g_audio.clear_audio_runtime(game_assets)
        audio_runtime = g_audio.ensure_audio_runtime(game_assets, cma_engine)

    selected_save_index, load_saved_data = g_ui.draw_load_level(main_arena, game_assets)

    if load_saved_data:
        main_arena = load_state(saved_files[selected_save_index])
        tile_map = main_arena.get("tile_map")
        loaded_entities = main_arena.get("entities")
        lighting_profile = main_arena.get("lighting_profile") or g_graphics.make_lighting_profile("inky")
        fog_profile = main_arena.get("fog_profile") or g_graphics.make_fog_profile("misty")
        wind_profile = main_arena.get("wind_profile") or g_effects.make_wind_profile()
        rain_profile = g_effects.normalize_rain_profile(main_arena.get("rain_profile") or g_effects.make_rain_profile())
        audio_profile = g_audio.normalize_audio_profile(main_arena.get("audio_profile") or g_audio.make_audio_profile())
        editor_mode = g_editor.migrate_editor_mode(main_arena.get("editor_mode", editor_mode))
        g_effects.clear_effects_runtime(game_assets)
        game_assets.pop("effects_entities_identity", None)
        g_graphics.clear_rain_runtime_assets(game_assets)
        g_audio.clear_audio_runtime(game_assets)
        audio_runtime = g_audio.ensure_audio_runtime(game_assets, cma_engine)
        if tile_map is not None:
            tile_map.setdefault("rain_exposure_revision", 0)
            g_audio.migrate_tile_audio_data(tile_map)

        if loaded_entities is not None:
            entities = loaded_entities
            g_editor.migrate_environment_data(entities)
            g_effects.discard_legacy_particle_systems(entities)
            g_editor.validate_selection(entities, editor_state)

    if g_mute:
        pr.draw_text("sound muted", 400, 42, 8, pr.WHITE)
    if debug_state != "clear":
        pr.draw_text(debug_state, 400, 52, 8, pr.WHITE)
    if pause_state == "paused":
        pr.draw_text("PAUSED", 220, 130, 12, pr.WHITE)

    if editor_mode == "play" and player_info is not None and tile_map is not None:
        draw_player_aim_cursor(player_info, tile_map, camera_3d.position)
    if editor_mode != "play" or not game_assets.get("play_mouse_captured", False):
        mp = g_ui.get_mouse_position()
        pr.draw_circle(int(mp.x), int(mp.y), 4 if editor_mode != "play" else 1, pr.WHITE)
    pr.end_texture_mode()
    g_ui.ui_end_frame(ui_state)
    ui_state["show_editor"] = show_editor
    g_mouse_is_ui_captured = ui_state.get("mouse_captured", False)

    listener_position = make_pos_abs(
        (player_info or {}).get("position", {}),
        (tile_map or {}).get("tile_width", 16),
        (tile_map or {}).get("tile_height", 16),
    )
    g_audio.update_audio(
        audio_runtime, cma_engine, dt,
        {"source_id": "player", "world_position": listener_position},
        tile_map or {}, entities or {}, rain_profile,
        (entities or {}).get("emitters", {}), audio_profile,
    )


    # update persistent variables here
    changes = main_arena.evolver()
    changes["show_options"] = show_options
    changes["pause_state"] = pause_state
    changes["debug_state"] = debug_state
    changes["collision_mode"] = collision_mode
    changes["editor_mode"] = editor_mode
    changes["do_load_level"] = do_load_level
    changes["time_elapsed"] = time_elapsed + dt
    changes["current_tile_selection"] = current_tile_selection
    changes["current_shape_selection"] = current_shape_selection
    changes["current_tile_force_collidable"] = current_tile_force_collidable
    changes["current_entity_selection"] = current_entity_selection
    changes["auto_reload"] = auto_reload    
    changes["ui_button_states"] = ui_button_states
    changes["save_elapsed"] = save_elapsed
    changes["saved_files"] = saved_files
    changes["tile_map"] = tile_map
    changes["entities"] = entities
    changes["player_info"] = player_info
    changes["selected_save_index"] = selected_save_index
    changes["lighting_profile"] = lighting_profile
    changes["fog_profile"] = fog_profile
    changes["wind_profile"] = wind_profile
    changes["rain_profile"] = rain_profile
    changes["audio_profile"] = audio_profile

    result = changes.persistent()    
    
    game_assets["camera_3d"] = camera_3d
    if reset_all:
        del game_assets["camera_3d"]

    if g_interacted_ui_this_frame == 0:
        g_last_interacted_ui_id = -1
    

    return result


