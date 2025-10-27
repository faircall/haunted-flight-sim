import math

import pyray as pr

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
    
def get_or_invoke(arena, variable_name, default_func, default_vals):
    if variable_name in arena:
        return arena[variable_name]
    else:
        arena[variable_name] = default_func(default_vals)
        return arena[variable_name]


def normalized_sin(t):
    return 0.5 *math.sin(t) + 0.5

def make_tile_map(width, height, tile_width, tile_height):
    result = {}
    result["map_width"] = width
    result["map_height"] = height
    result["tile_width"] = tile_width
    result["tile_height"] = tile_height    
    result["tile_types"] = [("blank_tile", pr.RED), ("carpet",pr.BLUE), ("bed", pr.GREEN), ("wall", pr.PURPLE)]
    result["tile_types_amount"] = len(result["tile_types"])
    tiles = []
    for y in range(height):
        for x in range(width):
            blank_tile = {}
            blank_tile["number"] = 0
            blank_tile["type"] = "blank_tile"
            blank_tile["color"] = pr.BLUE
            if x % 2 == 0 and y % 2 == 0:
                blank_tile["color"] = pr.GREEN
            if x % 2 == 0 and y % 2 != 0:
                blank_tile["color"] = pr.PURPLE
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


def update_and_render_tile_map(game_camera, tile_map, mouse_pos_world):
    map_height = tile_map["map_height"]
    map_width = tile_map["map_width"]
    tile_width = tile_map["tile_width"]
    tile_height = tile_map["tile_height"]
    mouse_tile_pos = pr.Vector2(int(mouse_pos_world.x/tile_width), int(mouse_pos_world.y/tile_height))
    for y in range(map_height):
        for x in range(map_width):
            tile_to_draw = tile_map["tiles"][y*map_width + x]
            if x == mouse_tile_pos.x and y == mouse_tile_pos.y:
                tile_color = pr.RED
                if pr.is_mouse_button_down(pr.MouseButton.MOUSE_BUTTON_LEFT):
                    tile_map["tiles"][y*map_width + x]["number"] = (tile_map["tiles"][y*map_width + x]["number"] + 1) % tile_map["tile_types_amount"]
                    tile_map["tiles"][y*map_width + x]["type"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][0]
                    tile_map["tiles"][y*map_width + x]["color"] = tile_map["tile_types"][tile_map["tiles"][y*map_width + x]["number"]][1]
            else:
                tile_color = tile_to_draw["color"]

            pr.draw_rectangle(int(x*tile_width - game_camera.x), int(y*tile_height - game_camera.y), tile_width, tile_height, tile_color)

def update_and_render(main_arena):
    # arena initialisation
    dt = pr.get_frame_time()
    mouse_pos = pr.get_mouse_position()
    time_elapsed = get_or_set(main_arena, "time_elapsed", 0.0)
    ui_button_states = get_or_set(main_arena, "ui_button_states", {})
    use_mouse_screen_navigation =  get_or_set(ui_button_states, "use_mouse_screen_navigation", True)
    #game_camera = get_or_invoke(main_arena, "camera_3d", pr.Camera3D, (pr.Vector3(0,0,0), pr.Vector3(0,1,0), pr.Vector3(0,1,0), 45.0, pr.CameraProjection.CAMERA_PERSPECTIVE))    
    if "camera_3d" in main_arena:
        game_camera = main_arena["camera_3d"]
    else:
        game_camera = pr.Camera3D(pr.Vector3(0,0,0), pr.Vector3(0,1,0), pr.Vector3(0,1,0), 45.0, pr.CameraProjection.CAMERA_PERSPECTIVE)
        main_arena["camera_3d"] = game_camera
    screen_width = main_arena["screen_width"]
    screen_height = main_arena["screen_height"]
    tile_size = 32
        

    #input handling
    camera_speed = 10
    if pr.is_key_down(pr.KeyboardKey.KEY_W):
        game_camera.position.y -= dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_A):
        game_camera.position.x -= dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_S):
        game_camera.position.y += dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_D):
        game_camera.position.x += dt*camera_speed

    if pr.is_key_down(pr.KeyboardKey.KEY_SPACE):
        game_camera.position.z += dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL):
        game_camera.position.z -= dt*camera_speed

    print(f"game camera is at x:{game_camera.position.x}, y: {game_camera.position.y}, z: {game_camera.position.z}")
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F1):
        main_arena["auto_reload"] = not main_arena["auto_reload"]
        draw_variable_state("auto reload", main_arena["auto_reload"], 10, 10, 20, pr.WHITE)            
                

    # rendering code
    # this seems to be about the shade of the sky
    color_to_draw = pr.Color(20, 120, 250, 255)    
    pr.begin_drawing()
    pr.clear_background(color_to_draw)    
    pr.begin_mode_3d(game_camera)
    pr.draw_triangle_3d(pr.Vector3(1,1,1), pr.Vector3(0,0,1), pr.Vector3(2,0,1), pr.GREEN)
    pr.end_mode_3d()
    pr.end_drawing()

    # update persistent variables here
    main_arena["time_elapsed"] = time_elapsed
    main_arena["camera_3d"] = game_camera
    main_arena["ui_button_states"] = ui_button_states
