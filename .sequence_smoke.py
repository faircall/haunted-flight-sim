"""Hidden GPU/audio smoke: sequence editor, path preview and full courtyard chain."""
from pathlib import Path
from unittest.mock import patch
import pyray as pr
import g_main
import g_update_and_render as game
import g_sequences as s
import g_sequence_editor as editor
import g_ui
from test_puzzles import make_arena

pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
output = Path("artifacts/sequences")
output.mkdir(parents=True, exist_ok=True)
fixture = s.ensure(make_arena())
for tile in fixture["tile_map"]["tiles"]:
    tile["index"] = 6  # stone floor
fixture["player_info"]["position"] = dict(tile_x=9,tile_y=15,x=1.,y=8.)
fixture = editor.create_courtyard(fixture,{"x":145.,"y":140.})
demo = fixture["world_sequences"]["demo"]
sequence = fixture["world_sequences"]["sequences"][demo["sequence"]]
sequence.update(interval=.05,fade_in=.1)
path = s.make_sequence()
path.update(mode="path",points=[{"x":30.,"y":100.},{"x":110.,"y":100.},{"x":110.,"y":170.}],style="pulse",hold=.3,fade_in=.15,fade_out=.4,speed=45.)
fixture["world_sequences"]["sequences"]["smoke_path"] = path
original = game.update_and_render
frame = 0
errors = []


def checked(render,lighting,arena,assets,engine):
    global frame
    try:
        if frame == 0:
            for key,value in fixture.items():
                arena=arena.set(key,value)
        ed=game.g_editor.get_or_create_editor_state(assets)
        st=editor.state(ed)
        assets.setdefault("ui_state",g_ui.make_ui_state())["show_editor"]=frame<4 or frame>=24
        arena=arena.set("editor_mode","sequences" if frame<4 or frame>=24 else "play").set("auto_reload",False)
        if frame == 0:
            st.update(kind="sequences",selected=demo["sequence"])
            st["preview"]=editor.make_preview(arena,demo["sequence"],sequence)
            st["preview"]["elapsed"]=.22
        if frame == 1:
            st.update(kind="triggers",selected=demo["trigger"],preview=None)
        if frame == 2:
            st.update(kind="encounters",selected=demo["encounter"])
        if frame == 3:
            st.update(kind="sequences",selected="smoke_path")
            st["preview"]=editor.make_preview(arena,"smoke_path",path)
            st["preview"]["elapsed"]=1.5
        if frame == 5:
            arena["player_info"]["position"]=dict(tile_x=9,tile_y=12,x=1.,y=8.)
        if frame == 17:
            assert len(arena["entities"]["brains"]) == 2, "Encounter was not spawned"
            for enemy in arena["entities"]["brains"].values():
                enemy["health"]=0
        if frame == 24:
            st.update(kind="event log",selected="",preview=None)
        with patch.object(pr,"is_key_pressed",return_value=False), patch.object(pr,"get_char_pressed",return_value=0):
            arena=original(render,lighting,arena,assets,engine)
        if frame in (0,1,2,3,11,17,24):
            im=pr.load_image_from_texture(render.texture)
            pr.image_flip_vertical(im)
            pr.export_image(im,str(output/f"frame-{frame}.png"))
            pr.unload_image(im)
        if frame == 18:
            assert arena["puzzle_state"]["facts"].get("courtyard_guardians_defeated"), "Completion callback failed"
            assert arena["sequence_state"]["music"]["track"] == "silence"
            assert not arena["sequence_runtime"]["errors"], arena["sequence_runtime"]["errors"]
        frame+=1
        return arena
    except Exception as error:
        errors.append(error)
        raise


game.update_and_render=checked
remaining=iter([False]*26+[True])
pr.window_should_close=lambda: next(remaining)
pr.get_frame_time=lambda: .05
g_main.g_main()
assert not errors, errors
assert frame == 26, frame
print("Sequence smoke passed: torch and path previews, trigger/encounter inspectors, courtyard entry -> ignition -> two enemies -> music/door completion.")
