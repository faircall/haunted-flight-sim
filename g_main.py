import pyray as pr
import traceback
import sys
import os
import importlib
import time
from pyrsistent import m, pmap, v

import cyminiaudio as cma

g_screen_width = 1920
g_screen_height = 1080 


update_and_render_file = "g_update_and_render"
update_and_render_module = importlib.import_module(update_and_render_file)

g_reloadable_modules = [
    ("g_audio", update_and_render_module.g_audio),
    ("g_light_visibility", update_and_render_module.g_graphics.light_visibility),
    ("g_effects", update_and_render_module.g_effects),
    ("g_graphics", update_and_render_module.g_graphics),
    ("g_ui", update_and_render_module.g_ui),
    ("g_editor", update_and_render_module.g_editor),
    ("g_render_order", update_and_render_module.g_render_order),
    ("g_update_and_render", update_and_render_module),
]

g_shader_source_files = (
    "shaders/tile_mask.fs",
    "shaders/cinematic_shadow_projection.fs",
    "shaders/cinematic_shadow_composite.fs",
    "shaders/render_item_outline.fs",
    "shaders/entity_self_shadow.fs",
    "shaders/light_accumulation.fs",
    "shaders/top_down_light.fs",
    "shaders/fog_volume_mask.fs",
    "shaders/lighting_composite.fs",
    "shaders/illuminated_fog.fs",
    "shaders/rain_composite.fs",
    "shaders/effect_fire.fs",
    "shaders/effect_smoke.fs"
)

g_module_persistent_reload_specs = {
    "g_audio": {
        # The current serialisable profile remains in main_arena. The transient
        # runtime is stopped before the module object is reloaded.
        "arena_factories": (),
        "game_asset_keys_to_clear": (),
    },
    "g_effects": {
        "arena_factories": (
            ("wind_profile", "make_wind_profile", "default"),
            ("rain_profile", "make_rain_profile", "default"),
        ),
        "game_asset_keys_to_clear": (
            "effects_runtime",
            "effects_entities_identity",
        )
    },
    "g_graphics": {
        "arena_factories": (
            ("lighting_profile", "make_lighting_profile", "inky"),
            ("fog_profile", "make_fog_profile", "misty")
        ),
        "game_asset_keys_to_clear": (
            "light_collision_grid",
            "light_visibility_cache",
            "lighting_frame_stats"
        )
    },
    "g_ui": {
        "arena_factories": (),
        "game_asset_keys_to_clear": ("ui_state",)
    },
    "g_editor": {
        "arena_factories": (),
        "game_asset_keys_to_clear": ("ui_state",)
    }
}


def get_file_write_time(file_name):
    try:
        write_time = os.path.getmtime(file_name)
        result = write_time
    except Exception as e:
        print(f"error getting file write time {e}")
        result = ""
    return result


def get_png_asset_snapshot(asset_root="art"):
    """Return a recursive, high-resolution snapshot of authored PNG assets."""
    snapshot = {}
    if not os.path.isdir(asset_root):
        return snapshot
    for directory, _subdirectories, file_names in os.walk(asset_root):
        for file_name in file_names:
            if not file_name.lower().endswith(".png"):
                continue
            path = os.path.normpath(os.path.join(directory, file_name))
            try:
                stat = os.stat(path)
            except OSError:
                # An editor may briefly replace a file atomically. If it is
                # still absent at the next poll, deletion will be detected.
                continue
            snapshot[path] = (int(stat.st_mtime_ns), int(stat.st_size))
    return snapshot


def changed_snapshot_files(previous_snapshot, current_snapshot):
    paths = set(previous_snapshot) | set(current_snapshot)
    return sorted(
        path for path in paths
        if previous_snapshot.get(path) != current_snapshot.get(path)
    )


def reload_png_assets_if_needed(asset_snapshot, game_assets):
    current_snapshot = get_png_asset_snapshot()
    changed_files = changed_snapshot_files(asset_snapshot, current_snapshot)
    if not changed_files:
        return []
    try:
        update_and_render_module.reload_image_assets(game_assets)
    except Exception as error:
        # Keep the old snapshot so a half-written or temporarily unavailable
        # asset is retried on the next poll instead of being silently accepted.
        render_error_message(f"Unable to reload PNG assets: {error}")
        return []
    asset_snapshot.clear()
    asset_snapshot.update(current_snapshot)
    print(f"reloaded PNG assets after changes to: {', '.join(changed_files)}")
    return changed_files

def reload_modules_if_needed(module_write_times, game_assets=None):
    reloaded_module_names = set()

    for name_mod in g_reloadable_modules:
        name = name_mod[0]
        mod = name_mod[1]
        file_name = name + ".py"
        if name not in module_write_times:
            module_write_times[name] = get_file_write_time(file_name)
        if module_write_times[name] != get_file_write_time(file_name):
            try:
                if name == "g_audio" and game_assets is not None:
                    mod.shutdown_audio_runtime(game_assets)
                    game_assets.pop("audio_runtime", None)
                mod = importlib.reload(mod)
                render_error_message("reloaded module!")
                module_write_times[name] = get_file_write_time(file_name)
                reloaded_module_names.add(name)
            except (ImportError, SyntaxError) as e:
                render_error_message(f"An error occurred while reloading the file: {e}")

    return reloaded_module_names

def refresh_persistent_data_after_module_reloads(main_arena, game_assets, reloaded_module_names):
    reloadable_modules = dict(g_reloadable_modules)

    for module_name in reloaded_module_names:
        reload_spec = g_module_persistent_reload_specs.get(module_name)

        if reload_spec is None:
            continue

        module = reloadable_modules[module_name]
        refreshed_names = []

        for arena_name, factory_name, default_profile_name in reload_spec["arena_factories"]:
            current_value = main_arena.get(arena_name)
            profile_name = current_value.get("name", default_profile_name) if current_value else default_profile_name
            main_arena = main_arena.set(arena_name, getattr(module, factory_name)(profile_name))
            refreshed_names.append(arena_name)

        for game_asset_key in reload_spec["game_asset_keys_to_clear"]:
            game_assets.pop(game_asset_key, None)

        if refreshed_names:
            print(f"refreshed {module_name} persistent data: {', '.join(refreshed_names)}")

    return main_arena

def reload_shaders_if_needed(shader_write_times, game_assets):
    changed_files = []

    for file_name in g_shader_source_files:
        write_time = get_file_write_time(file_name)

        if file_name not in shader_write_times:
            shader_write_times[file_name] = write_time
        elif shader_write_times[file_name] != write_time:
            shader_write_times[file_name] = write_time
            changed_files.append(file_name)

    if not changed_files:
        return

    shaders = game_assets.get("shaders")

    if shaders:
        update_and_render_module.unload_shaders(shaders)

    game_assets["shaders"] = update_and_render_module.load_shaders()
    print(f"reloaded shaders after changes to: {', '.join(changed_files)}")

def render_error_message(msg):
    print(msg)
    pr.begin_drawing()
    pr.clear_background(pr.RED)
    pr.draw_text(msg, 20, 20, 20, pr.WHITE)
    pr.end_drawing()

def format_update_error(error):
    tb_frames = traceback.extract_tb(error.__traceback__)
    reloadable_module_names = {name.lower() for name, module in g_reloadable_modules}
    relevant_frame = None

    for frame in reversed(tb_frames):
        module_name = os.path.splitext(os.path.basename(frame.filename))[0].lower()

        if module_name in reloadable_module_names:
            relevant_frame = frame
            break

    if relevant_frame is None and tb_frames:
        relevant_frame = tb_frames[-1]

    if relevant_frame is None:
        location = "unknown location"
    else:
        module_file = os.path.basename(relevant_frame.filename)
        location = f"{module_file}:{relevant_frame.lineno} in {relevant_frame.name}()"

    error_type = type(error).__name__
    return f"Issue in {location}: {error_type}: {error}"


def g_main():
    
    
    program_name = "Chinese Horror Story"
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_RESIZABLE)
    
    pr.init_window(g_screen_width, g_screen_height, program_name)
    pr.rl_disable_backface_culling()
    pr.set_target_fps(60)

    pr.hide_cursor()

    internal_width = 480
    internal_height = 270

    big_width = 1920
    big_height = 1080

    render_target = pr.load_render_texture(internal_width, internal_height)
    lighting_target = pr.load_render_texture(internal_width, internal_height)

    render_target_regular = pr.load_render_texture(big_width, big_height)
    lighting_target_regular = pr.load_render_texture(big_width, big_height)

    game_assets = {}

    main_arena = m(screen_width = g_screen_width, screen_height = g_screen_height)    
    backup_arena = pmap()
    show_error_message = False
    skip_update = False

    module_write_times = {name: get_file_write_time(name + ".py") for name, module in g_reloadable_modules}
    shader_write_times = {file_name: get_file_write_time(file_name) for file_name in g_shader_source_files}
    png_asset_snapshot = get_png_asset_snapshot()

    reload_timer = 0.0
    reload_refresh_interval = 1.0

    update_timer = 0.0
    update_refresh_interval = 2.0
    
    update_error_message = ""

    auto_reload = True
    main_arena = main_arena.set("auto_reload", auto_reload)

    cma_engine = cma.Engine()
    

    while not pr.window_should_close():                
        reload_timer += pr.get_frame_time()
        do_reload = False        

        if ((reload_timer >= reload_refresh_interval) and auto_reload) or pr.is_key_released(pr.KeyboardKey.KEY_F4):
            do_reload = True

        if do_reload:                                    
            skip_update = False
            update_timer = 0.0
            reload_timer = 0.0
            reloaded_module_names = reload_modules_if_needed(module_write_times, game_assets)
            main_arena = refresh_persistent_data_after_module_reloads(main_arena, game_assets, reloaded_module_names)
            reload_shaders_if_needed(shader_write_times, game_assets)
            reload_png_assets_if_needed(png_asset_snapshot, game_assets)
        # if pr.is_key_released(pr.KeyboardKey.KEY_F5):                                    
        #     main_arena = pmap()
        #     main_arena = main_arena.set("screen_width", g_screen_width)
        #     main_arena = main_arena.set("screen_height",  g_screen_height)                        
        #     # NOTE (Cooper) : I think we'd also want to do this, or at least there'd be times where you'd want to do both like this
        #     skip_update = False
        #     update_timer = 0.0
        #     reload_modules_if_needed(module_write_times)
        
        if not skip_update:
            try:
                backup_arena = main_arena
                editor_mode = main_arena.get("editor_mode", "")

                # if editor_mode == "play":
                main_arena = update_and_render_module.update_and_render(render_target, lighting_target, main_arena, game_assets, cma_engine)      
                # else:
                #     main_arena = update_and_render_module.update_and_render(render_target_regular, lighting_target_regular, main_arena, game_assets, cma_engine)      
                
                pr.begin_drawing()
                pr.clear_background(pr.BLACK)
                screen_width = pr.get_screen_width()
                screen_height = pr.get_screen_height()

                scale = max(1, min(screen_width // internal_width, screen_height // internal_height))
                dest_width = internal_width * scale
                dest_height = internal_height * scale

                offset_x = (screen_width - dest_width) // 2
                offset_y = (screen_height - dest_height)

                editor_mode = main_arena.get("editor_mode")

                
                source = pr.Rectangle(0, 0, internal_width, -internal_height)

                destination = pr.Rectangle(offset_x, offset_y, dest_width, dest_height)
                
                pr.draw_texture_pro(render_target.texture, source, destination, pr.Vector2(0,0), 0, pr.WHITE)                                        

                # if editor_mode == "play":
                #     scale = max(1, min(screen_width // internal_width, screen_height // internal_height))
                #     dest_width = internal_width * scale
                #     dest_height = internal_height * scale

                #     offset_x = (screen_width - dest_width) // 2
                #     offset_y = (screen_height - dest_height)

                #     editor_mode = main_arena.get("editor_mode")

                    
                #     source = pr.Rectangle(0, 0, internal_width, -internal_height)

                #     destination = pr.Rectangle(offset_x, offset_y, dest_width, dest_height)
                    
                #     pr.draw_texture_pro(render_target.texture, source, destination, pr.Vector2(0,0), 0, pr.WHITE)                                        
                # else:
                #     scale = max(1, min(screen_width // big_width, screen_height // big_height))
                #     dest_width = big_width * scale
                #     dest_height = big_height * scale

                #     offset_x = (screen_width - dest_width) // 2
                #     offset_y = (screen_height - dest_height)

                    

                    
                #     source = pr.Rectangle(0, 0, big_width, -big_height)

                #     destination = pr.Rectangle(offset_x, offset_y, dest_width, dest_height)

                #     pr.draw_texture_pro(render_target_regular.texture, source, destination, pr.Vector2(0,0), 0, pr.WHITE)

                
                
                pr.end_drawing()
                
                auto_reload = main_arena.get("auto_reload", True)
            except Exception as e:
                skip_update = True
                update_error_message = format_update_error(e)
                traceback.print_exception(type(e), e, e.__traceback__)
                main_arena = backup_arena
        else:
            update_timer += max(pr.get_frame_time(), 0.016)
            if update_timer >= update_refresh_interval:
                skip_update = False
                update_timer = 0.0
            render_error_message(update_error_message)
            
        
        
        
    update_and_render_module.g_audio.shutdown_audio_runtime(game_assets)
    try:
        cma_engine.close()
    except Exception:
        pass
    pr.close_window()

if __name__ == '__main__':
    g_main()
