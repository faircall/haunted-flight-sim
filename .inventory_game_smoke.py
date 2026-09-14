"""Exercise modal opening/closing in the real update/render loop."""
import copy
from pathlib import Path
import pyray as pr
import g_main
import g_interactions as ui
from test_puzzles import place

game = g_main.update_and_render_module
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
original = game.update_and_render
frame = 0
keys = ["TAB", None, "ESCAPE", "E", "LEFT", "ENTER", None]
pr.is_key_pressed = lambda key: frame < len(keys) and keys[frame] is not None and key == getattr(pr.KeyboardKey, "KEY_" + keys[frame])
pr.is_key_down = lambda key: False
pr.get_frame_time = lambda: .016

def checked(render, lighting, arena, assets, engine):
    global frame
    if frame == 0:
        arena = arena.set("entities", {}).set("tile_map", game.make_tile_map(30, 20, 16, 16))
        arena = arena.set("player_info", game.make_default_player(24, 24, 0))
        arena = game.g_puzzles.ensure_arena(arena)
        place(arena, "puzzle key", x=1, y=1)
    game.g_mouse_is_ui_captured = False
    assets.setdefault("ui_state", game.g_ui.make_ui_state())["show_editor"] = False
    before = game.tile_and_offset_to_absolute(arena["tile_map"], arena["player_info"]["position"])
    arena = original(render, lighting, arena.set("editor_mode", "play"), assets, engine)
    assert before == game.tile_and_offset_to_absolute(arena["tile_map"], arena["player_info"]["position"])
    modal = arena["interaction_runtime"]["modal"]
    if frame in (0, 1):
        assert modal and modal["kind"] == "inventory"
    if frame == 2:
        assert modal is None
    if frame in (3, 4):
        assert modal and modal["kind"] == "dialogue"
    if frame == 5:
        assert modal is None
        assert ui.inventory.count(arena["player_info"]["inventory"], "key") == 1
    if frame == 3:
        image = pr.load_image_from_texture(render.texture)
        pr.image_flip_vertical(image)
        pr.export_image(image, "artifacts/inventory/game-pickup.png")
        pr.unload_image(image)
    frame += 1
    return arena

def fail_fast(*args):
    try:
        return checked(*args)
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)

game.update_and_render = fail_fast
pr.window_should_close = lambda: frame >= len(keys)
g_main.g_main()
assert frame == len(keys)
print("Real game inventory open, close, pickup prompt and confirmed transfer passed")
