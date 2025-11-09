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

def make_default_camera():
    game_camera = pr.Camera3D(pr.Vector3(0,0,10), pr.Vector3(0,1,0), pr.Vector3(0,1,0), 45.0, pr.CameraProjection.CAMERA_PERSPECTIVE)    
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

def update_camera(player_position, player_heading, camera, dt):
    game_camera = camera.get("camera_3d")    
    camera_speed = 10

    # print(f"player heading: {player_heading.x},  {player_heading.y}")

    # move to a forward and up system

    rotate_speed = 3    

    if pr.is_key_down(pr.KeyboardKey.KEY_UP):
        player_heading.y += dt * rotate_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_DOWN):
        player_heading.y -= dt * rotate_speed
    
    if pr.is_key_down(pr.KeyboardKey.KEY_LEFT):
        player_heading.x -= dt * rotate_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_RIGHT):
        player_heading.x += dt * rotate_speed

    slide_heading = pr.vector3_normalize(pr.Vector3(math.cos(player_heading.x + math.pi/2.0), 0, math.sin((player_heading.x + math.pi/2.0))))

    spherical_cos = math.cos(player_heading.y)
    heading_xyz = pr.Vector3(math.cos(player_heading.x)*spherical_cos, math.sin(player_heading.y),math.sin(player_heading.x)*spherical_cos)
    heading_xyz = pr.vector3_normalize(heading_xyz)    
    
    
    
    if pr.is_key_down(pr.KeyboardKey.KEY_SPACE):
        player_position.y += dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_A):
        #player_position.x -= dt*camera_speed
        player_position = pr.vector3_add(player_position, pr.vector3_scale(slide_heading, dt*camera_speed)) # yeah nice
    if pr.is_key_down(pr.KeyboardKey.KEY_LEFT_CONTROL):
        player_position.y -= dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_D):
        player_position = pr.vector3_add(player_position, pr.vector3_scale(slide_heading, -dt*camera_speed)) # yeah niec
        #player_position.x += dt*camera_speed

    if pr.is_key_down(pr.KeyboardKey.KEY_W):
        player_position = pr.vector3_add(player_position, pr.vector3_scale(heading_xyz, dt*camera_speed)) # yeah nice
        # player_position.z -= dt*camera_speed
    if pr.is_key_down(pr.KeyboardKey.KEY_S):
        player_position = pr.vector3_add(player_position, pr.vector3_scale(heading_xyz, -dt*camera_speed)) # yeah nice
        #player_position.z += dt*camera_speed
    
    target_position = pr.vector3_add(player_position, heading_xyz)
    print(f"target heading is {target_position.x} {target_position.y} {target_position.z}")
        
    game_camera.position = player_position
    game_camera.target = target_position
    
    return player_position, player_heading

def make_default_position(x,y,z):
    return pr.Vector3(x,y,z)


def update_and_render(main_arena):
    # arena initialisation
    dt = pr.get_frame_time()
    mouse_pos = pr.get_mouse_position()
    time_elapsed = get_or_set(main_arena, "time_elapsed", 0.0)
    ui_button_states = get_or_set(main_arena, "ui_button_states", {})
    use_mouse_screen_navigation =  get_or_set(ui_button_states, "use_mouse_screen_navigation", True)
    camera_3d = get_or_invoke(main_arena, "camera_3d", make_default_camera)        
    player_camera = get_or_set(main_arena, "player_camera", {"camera_3d" : camera_3d})        
    player_position = get_or_invoke_args(main_arena, "player_position", make_default_position, (0,0,0))        
    player_heading = get_or_invoke_args(main_arena, "player_heading", make_default_position, (0,0,1))        

    screen_width = main_arena["screen_width"]
    screen_height = main_arena["screen_height"]    
    tile_size = 32
        

    #input handling
    player_position , player_heading = update_camera(player_position, player_heading, player_camera, dt)
    
    
    # print(f"game camera is at x:{game_camera.position.x}, y: {game_camera.position.y}, z: {game_camera.position.z}")
    if pr.is_key_pressed(pr.KeyboardKey.KEY_F1):
        main_arena["auto_reload"] = not main_arena["auto_reload"]
        draw_variable_state("auto reload", main_arena["auto_reload"], 10, 10, 20, pr.WHITE)            
                

    # rendering code
    # this seems to be about the shade of the sky
    color_to_draw = pr.Color(60, 160, 250, 255)    
    pr.begin_drawing()
    pr.clear_background(color_to_draw)    
    

    if do_button(pr.Vector2(10, 10), name="reset cameras"):
        camera_3d = make_default_camera()   
        player_heading = make_default_position(0,0,1)
        player_position = make_default_position(0,0,0)
        player_camera["camera_3d"] = camera_3d

    pr.begin_mode_3d(camera_3d)
    pr.draw_plane(pr.Vector3(0,0,0), pr.Vector2(100,100), pr.BROWN)
    pr.draw_cube(pr.Vector3(10,50,0), 100, 10, 10, pr.RED)

    pr.draw_triangle_3d(pr.Vector3(1,1,1), pr.Vector3(0,0,1), pr.Vector3(2,0,1), pr.GREEN)
    pr.end_mode_3d()
    pr.end_drawing()

    # update persistent variables here
    main_arena["player_heading"] = player_heading
    main_arena["player_position"] = player_position
    main_arena["time_elapsed"] = time_elapsed
    main_arena["camera_3d"] = camera_3d
    main_arena["ui_button_states"] = ui_button_states
