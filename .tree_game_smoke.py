"""Hidden real-game rendering check for animated willow placement and lighting."""
from pathlib import Path
import sys

if "--variants" in sys.argv:
    from tree_assets_smoke import run
    run()
    raise SystemExit(0)

import pyray as pr
from PIL import Image, ImageChops
import g_main

game = g_main.update_and_render_module
original = game.update_and_render
TREE_ID = game.g_editor.allocate_gameplay_entity_id({})
frame = 0
poses = []
lighting_names = ("down", "up", "left", "right")
out = Path("artifacts/tree-wind")
out.mkdir(parents=True, exist_ok=True)
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
pr.is_key_pressed = lambda key: False
pr.is_key_down = lambda key: False
pr.get_frame_time = lambda: .016


def checked(render, lighting, arena, assets, engine):
    global frame
    if frame == 6:
        arena["entities"]["brains"].pop(TREE_ID)
        arena = original(render, lighting, arena, assets, engine)
        assert not assets["tree_textures"]
        assert not assets["tree_runtime"]["targets"]
        assert not assets["tree_responses"]
        assert not assets["tree_runtime"]["response_targets"]
        frame += 1
        return arena
    if frame == 0:
        tree = dict(id=TREE_ID, type="willow tree",
                    position=dict(tile_x=18, tile_y=13, x=0., y=0.))
        game.give_entity_stats_from_type(tree, "willow tree")
        entities = {"brains": {TREE_ID: tree}}
        lamp = game.g_editor.make_default_point_light(dict(tile_x=14, tile_y=14, x=0., y=0.))
        lamp.update(radius=300., intensity=1.5, casts_cinematic_shadows=True)
        entities["lights"] = {"tree-lamp": lamp}
        arena = arena.set("entities", entities).set("tile_map", game.make_tile_map(40, 30, 16, 16))
        arena = arena.set("player_info", game.make_default_player(235, 220, 0))
    if 2 <= frame < 6:
        arena["entities"]["brains"][TREE_ID]["wind_response"] = 0.
        dx, dy = ((0, 80), (0, -80), (-80, 0), (80, 0))[frame-2]
        arena["entities"]["lights"]["tree-lamp"]["position"] = game.g_editor.world_to_tile_position(
            {"x": 288.+dx, "y": 208.+dy}, arena["tile_map"])
    assets.setdefault("ui_state", game.g_ui.make_ui_state())["show_editor"] = False
    game.g_mouse_is_ui_captured = False
    arena = original(render, lighting, arena.set("editor_mode", "play").set("time_elapsed", frame * 3.), assets, engine)
    texture = assets["tree_textures"][str(TREE_ID)]
    item = game.g_render_order.build_brain_render_item(TREE_ID, arena["entities"]["brains"][TREE_ID], arena["tile_map"], assets)
    assert game.g_graphics.resolve_render_item_texture(item, assets) is texture
    resources = game.g_graphics.resolve_entity_self_shadow_resources(item, texture, assets)
    assert resources["active_mode"] == "directional_profiles" and not resources["fallback_used"]
    image = pr.load_image_from_texture(texture)
    pose = Image.frombytes("RGBA", (image.width, image.height), bytes(pr.ffi.buffer(image.data, image.width * image.height * 4)))
    poses.append(pose.copy())
    pose.save(out / f"game-tree-pose-{frame}.png")
    pr.unload_image(image)
    image = pr.load_image_from_texture(assets["tree_responses"][str(TREE_ID)])
    response = Image.frombytes("RGBA", (image.width, image.height), bytes(pr.ffi.buffer(image.data, image.width*image.height*4)))
    pr.unload_image(image)
    if frame == 2:
        # Exposed lower trunk is fixed and must retain all four authored channels,
        # including alpha as data rather than transparency/blend weight.
        channels = [Image.open(game.g_tree_render.ART / f"willow_tree_trunk_response_{d}.png").convert("L") for d in lighting_names]
        trunk = Image.open(game.g_tree_render.ART / "willow_tree_trunk.png").convert("RGBA")
        foliage_masks = [Image.open(game.g_tree_render.ART / f"willow_tree_{part['name']}.png").getchannel("A")
                         for part in game.g_tree_render.rig.PARTS]
        checked_pixels = 0
        for y in range(110, 123):
            for x in range(128):
                if trunk.getpixel((x,y))[3] == 255 and not any(mask.getpixel((x,y)) for mask in foliage_masks):
                    expected = tuple(c.getpixel((x,y)) for c in channels)
                    actual = response.getpixel((x+16,y+16))
                    assert max(abs(a-b) for a,b in zip(expected,actual)) <= 1, (x,y,expected,actual)
                    checked_pixels += 1
        assert checked_pixels > 10
        leaf_values = [response.getpixel((x,y)) for y in range(25,80) for x in range(160)
                       if pose.getpixel((x,y))[3] == 255 and min(response.getpixel((x,y))) >= 140
                       and max(response.getpixel((x,y))) < 255]
        assert len(leaf_values) > 100
        assert len(set(leaf_values)) > 10
        for index, name in enumerate(lighting_names):
            response.getchannel(index).save(out / f"response-{name}.png")
    image = pr.load_image_from_texture(render.texture)
    pr.image_flip_vertical(image)
    pr.export_image(image, str(out / f"game-tree-{frame}.png"))
    if 2 <= frame < 6:
        pr.export_image(image, str(out / f"lighting-{lighting_names[frame-2]}.png"))
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
pr.window_should_close = lambda: frame >= 7
g_main.g_main()
assert frame == 7
assert poses[0].getchannel("A").getbbox() is not None
assert ImageChops.difference(poses[0], poses[1]).convert("RGB").getbbox() is not None
print("Willow: animated poses, four light directions, exact trunk channels, two-sided foliage, resource cleanup passed")
