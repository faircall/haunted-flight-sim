from pathlib import Path
from unittest.mock import patch
import copy
import pyray as pr
import g_update_and_render as game
import g_editor
import g_ui
import g_placement_preview as preview
from test_puzzles import make_arena

pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
pr.init_window(480,270,"Placement ghost validation")
assets = dict(textures=game.load_textures(),sprite_sheets=game.load_sprite_sheets(),shaders=game.load_shaders(),entity_types=game.load_entity_types())
scene = pr.load_render_texture(480,270)
arena = make_arena()
before = copy.deepcopy(arena)
state = g_editor.make_editor_state()
state["tool"] = "place"
Path("artifacts/placement").mkdir(parents=True,exist_ok=True)
try:
    cases = [("entity",i,kind) for i,kind in enumerate(assets["entity_types"])]
    cases += [("environment",0,kind) for kind in g_editor.ENVIRONMENT_OBJECT_REGISTRY]
    cases += [("tile",0,"tile")]
    for mode,index,kind in cases:
        state["placement_type"] = kind
        pr.begin_texture_mode(scene);pr.clear_background(pr.BLANK);pr.end_texture_mode()
        with patch.object(g_ui,"get_mouse_position",return_value=pr.Vector2(145.,140.)):
            preview.draw(scene,pr.Vector2(0,0),assets,arena["tile_map"],state,mode,6,0,index,1.)
        image = pr.load_image_from_texture(scene.texture)
        colors = pr.load_image_colors(image)
        alpha = [colors[i].a for i in range(480*270)]
        assert max(alpha)>0,kind
        assert max(alpha)<255,kind
        pr.unload_image_colors(colors)
        pr.image_flip_vertical(image)
        if kind in ("buddha","red head","fire_emitter","tile","puzzle lever"):
            pr.export_image(image,"artifacts/placement/"+kind.replace(" ","_")+".png")
        pr.unload_image(image)
    assert arena == before,"preview mutated level data"
    print(f"Placement GPU checks passed for {len(cases)} types: visible, translucent, no level mutation")
finally:
    game.unload_image_asset_collections(assets["textures"],assets["sprite_sheets"])
    for info in assets["shaders"].values():pr.unload_shader(info["shader"])
    for target in assets.get("render_targets",{}).values():pr.unload_render_texture(target)
    pr.unload_render_texture(scene)
    pr.close_window()
