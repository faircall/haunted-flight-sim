"""Verify linked glow lights enter the real editor lighting pass."""
from pathlib import Path
import pyray as pr
import g_main
import g_glow
game = g_main.update_and_render_module
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
original = game.update_and_render
frame = 0
def checked(render,lighting,arena,assets,engine):
    global frame
    if frame == 0:
        obj = dict(type="buddha",id="glow_statue",position=dict(tile_x=5,tile_y=5,x=8.,y=8.))
        game.give_entity_stats_from_type(obj,"buddha")
        arena = arena.set("entities",{"brains":{"glow_statue":obj}})
        arena = g_glow.set_glow(arena,"brains:glow_statue",strength=.8,color=[.1,.8,.4],
            mode="edge",light=dict(enabled=True,radius=100.,intensity=2.))
    arena = original(render,lighting,arena.set("editor_mode","entity"),assets,engine)
    assert "effect:glow:brains:glow_statue" in assets["runtime_lights"]
    if frame == 2:
        Path("artifacts/glow").mkdir(parents=True,exist_ok=True)
        image = pr.load_image_from_texture(render.texture);pr.image_flip_vertical(image)
        pr.export_image(image,"artifacts/glow/linked-light.png");pr.unload_image(image)
    frame += 1
    return arena
game.update_and_render = checked
frames = iter((False,False,False,True))
pr.window_should_close = lambda: next(frames)
g_main.g_main()
assert frame == 3
print("Entity editor linked glow light rendering passed")
