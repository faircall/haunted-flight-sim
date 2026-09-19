"""Compose animated willow sprites once per frame for all world rendering passes."""
from pathlib import Path

import pyray as pr

import g_effects
import g_tree_animation as rig

SIZE = 160
PADDING = 16
ROOT_PIXEL = (84, 123)
ART = Path(__file__).resolve().parent / "art" / "split_tree"


def prepare(assets, entities, tile_map, wind, elapsed):
    trees = {key: entity for key, entity in entities.get("brains", {}).items()
             if entity.get("type") == "willow tree"}
    runtime = assets.setdefault("tree_runtime", {"textures": {}, "targets": {}})
    outputs = assets.setdefault("tree_textures", {})
    # Asset references require string names; editor entity IDs are integers.
    # Rebuild this cheap lookup to discard keys from older hot-reloaded versions.
    outputs.clear()
    for key in list(runtime["targets"]):
        if key not in trees:
            pr.unload_render_texture(runtime["targets"].pop(key))
    if not trees:
        return
    textures = runtime["textures"]
    for name in ("trunk", *(part["name"] for part in rig.PARTS)):
        if name not in textures:
            textures[name] = pr.load_texture(str(ART / ("willow_tree_" + name + ".png")))
            pr.set_texture_filter(textures[name], pr.TextureFilter.TEXTURE_FILTER_POINT)
    for key, entity in trees.items():
        if key not in runtime["targets"]:
            target = pr.load_render_texture(SIZE, SIZE)
            pr.set_texture_filter(target.texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
            runtime["targets"][key] = target
        target = runtime["targets"][key]
        world = g_effects.position_to_world(entity["position"], tile_map)
        profile = dict(wind, tree_irregular=entity.get("tree_irregular", True),
                       tree_seed=int(entity.get("tree_seed", 17)), tree_mesh=entity.get("tree_mesh", "grid"))
        amount = max(0., float(entity.get("wind_response", 1.)))
        profile["strength"] = profile.get("strength", 8.) * amount
        profile["gust_strength"] = profile.get("gust_strength", 5.) * amount
        pr.begin_texture_mode(target)
        pr.clear_background(pr.BLANK)
        # Store an upright texture so lighting/shadow shaders use ordinary positive UVs.
        pr.rl_push_matrix()
        pr.rl_translatef(0, SIZE, 0)
        pr.rl_scalef(1, -1, 1)
        pr.rl_disable_backface_culling()
        pr.draw_texture(textures["trunk"], PADDING, PADDING, pr.WHITE)
        for part in rig.PARTS:
            pr.rl_set_texture(textures[part["name"]].id)
            pr.rl_begin(pr.RL_QUADS)
            pr.rl_color4ub(255, 255, 255, 255)
            pr.rl_normal3f(0, 0, 1)
            for quad in rig.foliage_mesh(part, elapsed, profile, (world["x"], world["y"])):
                for x, y, u, v in quad:
                    pr.rl_tex_coord2f(u, v)
                    pr.rl_vertex2f(x + PADDING, y + PADDING)
            pr.rl_end()
            pr.rl_set_texture(0)
        pr.rl_pop_matrix()
        pr.rl_draw_render_batch_active()
        pr.rl_enable_backface_culling()
        pr.end_texture_mode()
        outputs[str(key)] = target.texture


def unload(assets):
    runtime = assets.pop("tree_runtime", {})
    for target in runtime.get("targets", {}).values():
        pr.unload_render_texture(target)
    for texture in runtime.get("textures", {}).values():
        pr.unload_texture(texture)
    assets.pop("tree_textures", None)
