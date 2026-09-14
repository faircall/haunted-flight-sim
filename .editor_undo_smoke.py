"""Hidden real editor regression: one stroke, Ctrl+Z while held, release."""
import pyray as pr
import g_main
import g_editor_history as history

game = g_main.update_and_render_module
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
frame = 0
pr.get_frame_time = lambda: .016
pr.is_key_pressed = lambda key: frame == 2 and key == pr.KeyboardKey.KEY_Z
pr.is_key_down = lambda key: frame == 2 and key == pr.KeyboardKey.KEY_LEFT_CONTROL
pr.is_mouse_button_down = lambda button: button == pr.MouseButton.MOUSE_BUTTON_LEFT and frame < 4
pr.is_mouse_button_pressed = lambda button: button == pr.MouseButton.MOUSE_BUTTON_LEFT and frame == 0
pr.is_mouse_button_released = lambda button: button == pr.MouseButton.MOUSE_BUTTON_LEFT and frame == 4
pr.get_mouse_wheel_move = lambda: 0
game.g_ui.get_mouse_position = lambda: pr.Vector2(160 + frame * 16, 160)
original = game.update_and_render

def checked(render, lighting, arena, assets, engine):
    global frame
    if frame == 0:
        arena = arena.set("tile_map", game.make_tile_map(30, 20, 16, 16)).set("entities", {})
        arena = arena.set("player_info", game.make_default_player(24, 24, 0))
        assets.setdefault("ui_state", game.g_ui.make_ui_state())["show_editor"] = False
    arena = original(render, lighting, arena.set("editor_mode", "tile").set("current_tile_selection", 1), assets, engine)
    changed = sum(t["index"] != 0 for t in arena["tile_map"]["tiles"])
    if frame == 0:
        assert changed == 1, changed
    if frame == 1:
        assert changed >= 2, changed
    if frame >= 2:
        assert changed == 0, (frame, changed)
        assert not history.state(assets)["undo"]
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
pr.window_should_close = lambda: frame >= 5
g_main.g_main()
assert frame == 5
print("Real editor stroke undo and held-mouse suppression passed")
