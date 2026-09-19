"""Compose animated willow sprites once per frame for all world rendering passes."""
from pathlib import Path
from PIL import Image

import pyray as pr

import g_effects
import g_tree_animation as rig

SIZE = 160
PADDING = 16
ROOT_PIXEL = (84, 123)
ART = Path(__file__).resolve().parent / "art" / "split_tree"
RESPONSE_DIRECTIONS = ("down", "up", "left", "right")


def response_pixels():
    """Pack authored luminance without confusing source transparency with data alpha."""
    channels = []
    for direction in RESPONSE_DIRECTIONS:
        path = ART / f"willow_tree_trunk_response_{direction}.png"
        with Image.open(path) as source:
            if source.size != (128, 128):
                raise ValueError(f"{path.name} must use the aligned 128x128 canvas")
            channels.append(source.convert("L"))
    return Image.merge("RGBA", channels).tobytes()


def ensure_response_resources(runtime):
    shader_path = ART.parent.parent / "shaders" / "tree_response.fs"
    stamp = tuple((ART / f"willow_tree_trunk_response_{d}.png").stat().st_mtime_ns
                  for d in RESPONSE_DIRECTIONS)
    if runtime.get("response_stamp") != stamp:
        pixels = bytearray(response_pixels())
        image = pr.Image(pixels, 128, 128, 1, int(pr.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
        texture = pr.load_texture_from_image(image)
        pr.set_texture_filter(texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
        if runtime.get("trunk_response") is not None:
            pr.unload_texture(runtime["trunk_response"])
        runtime.update(trunk_response=texture, response_stamp=stamp)
    stamp = shader_path.stat().st_mtime_ns
    if runtime.get("response_shader_stamp") != stamp:
        shader = pr.load_shader("", str(shader_path))
        locations = {name: pr.get_shader_location(shader, name)
                     for name in ("trunkResponse", "foliage", "partSeed", "bendAngle")}
        if not shader.id or any(value < 0 for value in locations.values()):
            raise RuntimeError("Tree response shader failed to compile")
        if runtime.get("response_shader") is not None:
            pr.unload_shader(runtime["response_shader"])
        runtime.update(response_shader=shader, response_locations=locations, response_shader_stamp=stamp)


def draw_layer(texture, quads=None):
    if quads is None:
        pr.draw_texture(texture, PADDING, PADDING, pr.WHITE)
        return
    pr.rl_set_texture(texture.id)
    pr.rl_begin(pr.RL_QUADS)
    pr.rl_color4ub(255, 255, 255, 255)
    pr.rl_normal3f(0, 0, 1)
    for quad in quads:
        for x, y, u, v in quad:
            pr.rl_tex_coord2f(u, v)
            pr.rl_vertex2f(x + PADDING, y + PADDING)
    pr.rl_end()
    pr.rl_set_texture(0)


def compose(target, textures, meshes, runtime, angles, response=False):
    pr.begin_texture_mode(target)
    pr.clear_background(pr.WHITE if response else pr.BLANK)
    pr.rl_push_matrix()
    pr.rl_translatef(0, SIZE, 0)
    pr.rl_scalef(1, -1, 1)
    pr.rl_disable_backface_culling()
    if response:
        shader = runtime["response_shader"]
        locations = runtime["response_locations"]
        pr.begin_shader_mode(shader)
        pr.set_shader_value_texture(shader, locations["trunkResponse"], runtime["trunk_response"])
        # All four channels are data. Never blend using the right-light channel.
        pr.rl_set_blend_factors(pr.RL_ONE, pr.RL_ZERO, pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM)
    for index, name in enumerate(("trunk", *(part["name"] for part in rig.PARTS))):
        if response:
            pr.rl_draw_render_batch_active()
            for uniform, value in (("foliage", float(index != 0)), ("partSeed", float(index)),
                                   ("bendAngle", angles.get(name, 0.))):
                pr.set_shader_value(shader, locations[uniform], pr.ffi.new("float *", value),
                                    pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT)
            # A batch flush releases auxiliary texture bindings.
            pr.set_shader_value_texture(shader, locations["trunkResponse"], runtime["trunk_response"])
        draw_layer(textures[name], meshes.get(name))
    pr.rl_draw_render_batch_active()
    if response:
        pr.end_blend_mode()
        pr.end_shader_mode()
    pr.rl_pop_matrix()
    pr.rl_enable_backface_culling()
    pr.end_texture_mode()


def prepare(assets, entities, tile_map, wind, elapsed):
    trees = {key: entity for key, entity in entities.get("brains", {}).items()
             if entity.get("type") == "willow tree"}
    runtime = assets.setdefault("tree_runtime", {"textures": {}, "targets": {}})
    outputs = assets.setdefault("tree_textures", {})
    responses = assets.setdefault("tree_responses", {})
    response_targets = runtime.setdefault("response_targets", {})
    # Asset references require string names; editor entity IDs are integers.
    # Rebuild this cheap lookup to discard keys from older hot-reloaded versions.
    outputs.clear()
    responses.clear()
    for key in list(runtime["targets"]):
        if key not in trees:
            pr.unload_render_texture(runtime["targets"].pop(key))
            if key in response_targets:
                pr.unload_render_texture(response_targets.pop(key))
    if not trees:
        return
    ensure_response_resources(runtime)
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
        if key not in response_targets:
            response_targets[key] = pr.load_render_texture(SIZE, SIZE)
            pr.set_texture_filter(response_targets[key].texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
        world = g_effects.position_to_world(entity["position"], tile_map)
        profile = dict(wind, tree_irregular=entity.get("tree_irregular", True),
                       tree_seed=int(entity.get("tree_seed", 17)), tree_mesh=entity.get("tree_mesh", "grid"))
        amount = max(0., float(entity.get("wind_response", 1.)))
        profile["strength"] = profile.get("strength", 8.) * amount
        profile["gust_strength"] = profile.get("gust_strength", 5.) * amount
        position = (world["x"], world["y"])
        meshes = {part["name"]: list(rig.foliage_mesh(part, elapsed, profile, position)) for part in rig.PARTS}
        angles = {part["name"]: rig.motion(part, elapsed, profile, position)[0] for part in rig.PARTS}
        compose(target, textures, meshes, runtime, angles)
        compose(response_targets[key], textures, meshes, runtime, angles, response=True)
        outputs[str(key)] = target.texture
        responses[str(key)] = response_targets[key].texture


def unload(assets):
    runtime = assets.pop("tree_runtime", {})
    for target in runtime.get("targets", {}).values():
        pr.unload_render_texture(target)
    for target in runtime.get("response_targets", {}).values():
        pr.unload_render_texture(target)
    for texture in runtime.get("textures", {}).values():
        pr.unload_texture(texture)
    assets.pop("tree_textures", None)
    assets.pop("tree_responses", None)
    if runtime.get("trunk_response") is not None:
        pr.unload_texture(runtime["trunk_response"])
    if runtime.get("response_shader") is not None:
        pr.unload_shader(runtime["response_shader"])
