import pyray as pr
import traceback
import sys
import os
import importlib
import time

g_screen_width = 1280
g_screen_height = 720


update_and_render_file = "g_update_and_render"
update_and_render_module = importlib.import_module(update_and_render_file)

g_reloadable_modules = [("g_update_and_render",update_and_render_module)]


def get_file_write_time(file_name):
    try:
        write_time = os.path.getmtime(file_name)
        result = write_time
    except Exception as e:
        print(f"error gettinf ile write time {e}")
        result = ""
    return result

def reload_modules_if_needed(module_write_times):
    for name_mod in g_reloadable_modules:
        name = name_mod[0]
        mod = name_mod[1]
        file_name = name + ".py"
        if name not in module_write_times:
            module_write_times[name] = get_file_write_time(file_name)
        if module_write_times[name] != get_file_write_time(file_name):
            try:
                mod = importlib.reload(mod)            
                render_error_message("reloaded module!")                
                module_write_times[name] = get_file_write_time(file_name)
            except (ImportError, SyntaxError) as e:
                render_error_message(f"An error occurred while reloading the viz module: {e}")                
            

def render_error_message(msg):
    pr.begin_drawing()
    pr.clear_background(pr.RED)
    pr.draw_text(msg, 20, 20, 20, pr.WHITE)
    pr.end_drawing()


def g_main():
    program_name = "Horror Flightsim"
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_RESIZABLE)
    
    pr.init_window(g_screen_width, g_screen_height, program_name)
    pr.rl_disable_backface_culling()
    pr.set_target_fps(60)

    main_arena = {}
    main_arena["screen_width"] = g_screen_width
    main_arena["screen_height"] = g_screen_height

    show_error_message = False
    skip_update = False

    module_write_times = {}

    reload_timer = 0.0
    reload_refresh_interval = 1.0

    update_timer = 0.0
    update_refresh_interval = 2.0
    
    update_error_message = ""

    auto_reload = True
    main_arena["auto_reload"] = auto_reload

    while not pr.window_should_close():                
        reload_timer += pr.get_frame_time()
        do_reload = False        

        if ((reload_timer >= reload_refresh_interval) and auto_reload) or pr.is_key_released(pr.KeyboardKey.KEY_F4):
            do_reload = True

        if do_reload:                                    
            skip_update = False
            update_timer = 0.0
            reload_timer = 0.0
            reload_modules_if_needed(module_write_times)
        if pr.is_key_released(pr.KeyboardKey.KEY_F5):                                    
            main_arena = {}
            main_arena["screen_width"] = g_screen_width
            main_arena["screen_height"] = g_screen_height                        
            # NOTE (Cooper) : I think we'd also want to do this, or at least there'd be times where you'd want to do both like this
            skip_update = False
            update_timer = 0.0
            reload_modules_if_needed(module_write_times)
        
        if not skip_update:
            try:
                update_and_render_module.update_and_render(main_arena)                        
                auto_reload = main_arena["auto_reload"]
            except Exception as e:
                skip_update = True
                error_type = type(e).__name__
                error_message = str(e)                
                tb_frames = traceback.extract_tb(e.__traceback__)                                
                relevant_line = None
                for frame in reversed(tb_frames):
                    if 'g_update_and_render' in frame.filename:
                        relevant_line = frame.lineno
                        break                                
                if relevant_line is None:
                    relevant_line = tb_frames[0].lineno if tb_frames else "unknown"                
                update_error_message = f"Issue with update and render: {error_type} at line {relevant_line}: {error_message}"                
        else:
            update_timer += max(pr.get_frame_time(), 0.016)
            if update_timer >= update_refresh_interval:
                skip_update = False
                update_timer = 0.0
            render_error_message(update_error_message)
            
        
        
        
    pr.close_window()

if __name__ == '__main__':
    g_main()