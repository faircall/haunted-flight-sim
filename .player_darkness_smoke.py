"""GPU regression: darkness adds only a rim; bright light removes it."""
from pathlib import Path
import pyray as pr
import g_graphics as g
import g_update_and_render as game
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
pr.init_window(64,64,"Darkness outline check")
scene = pr.load_render_texture(64,64)
image = pr.gen_image_color(8,8,pr.WHITE)
texture = pr.load_texture_from_image(image);pr.unload_image(image)
assets = {"shaders":game.load_shaders(),"textures":{"test":texture}}
item = dict(source_id="player",texture={"collection":"textures","name":"test"},
            source_rect=dict(x=0,y=0,width=8,height=8),dest_rect=dict(x=20,y=16,width=16,height=24))
try:
    for bright in (False,True):
        pr.begin_texture_mode(scene);pr.clear_background(pr.WHITE if bright else pr.BLACK);pr.end_texture_mode()
        g.draw_player_darkness_outline(scene,[item],[],pr.Vector2(0,0),assets)
        image = pr.load_image_from_texture(scene.texture);pr.image_flip_vertical(image)
        rim = pr.get_image_color(image,19,28)
        inside = pr.get_image_color(image,28,28)
        if bright:
            assert rim.r == 255 and inside.r == 255,"outline remained in bright light"
        else:
            assert rim.b > 20 and inside.b == 0,"darkness outline filled the body or failed to appear"
            Path("artifacts/glow").mkdir(parents=True,exist_ok=True)
            pr.export_image(image,"artifacts/glow/player-darkness-outline.png")
        pr.unload_image(image)
    print("Player darkness GPU check passed: dark rim, unlit interior, bright-light suppression")
finally:
    for info in assets["shaders"].values():pr.unload_shader(info["shader"])
    for target in assets.get("render_targets",{}).values():pr.unload_render_texture(target)
    pr.unload_texture(texture);pr.unload_render_texture(scene);pr.close_window()
