"""Compose animated willow sprites once per frame for all world rendering passes."""
from pathlib import Path
import math
from PIL import Image

import pyray as pr

import g_effects
import g_tree_animation as rig

SIZE = 160
PADDING = 16
ROOT_PIXEL = (84, 123)
ART = Path(__file__).resolve().parent / "art" / "split_tree"
RESPONSE_DIRECTIONS = ("down", "up", "left", "right")


def ensure_gpu_resources(runtime):
    directory = ART.parent.parent / "shaders"
    vertex = directory / "tree_deform.vs"
    for name, fragment in (("color", "tree_color.fs"), ("response", "tree_response.fs")):
        path = directory / fragment
        stamp = (vertex.stat().st_mtime_ns, path.stat().st_mtime_ns)
        key = "gpu_" + name
        if runtime.get(key + "_stamp") == stamp:
            continue
        shader = pr.load_shader(str(vertex), str(path))
        uniforms = ("deformation",) + (("trunkResponse", "foliage", "partSeed", "bendAngle") if name == "response" else ())
        locations = {u: pr.get_shader_location(shader, u) for u in uniforms}
        if shader.id == pr.rl.rlGetShaderIdDefault() or any(loc < 0 for loc in locations.values()):
            if shader.id != pr.rl.rlGetShaderIdDefault():
                pr.unload_shader(shader)
            raise RuntimeError("Tree GPU " + name + " shader failed to compile")
        if key in runtime:
            pr.unload_shader(runtime[key])
        runtime.update({key: shader, key + "_locations": locations, key + "_stamp": stamp})


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
    # These hot-path calls accept only numeric scalars. Calling the underlying
    # CFFI binding avoids pyray's generic argument-conversion wrapper per vertex.
    tex_coord = pr.rl.rlTexCoord2f
    vertex = pr.rl.rlVertex2f
    for quad in quads:
        for x, y, u, v in quad:
            tex_coord(u, v)
            vertex(x + PADDING, y + PADDING)
    pr.rl_end()
    pr.rl_set_texture(0)


def cached_mesh(runtime, part, profile, gpu=False):
    """GPU and CPU comparison paths have separate buffers; topology is shared."""
    key = (tuple(part["bounds"]), tuple(part["pivot"]), profile.get("tree_mesh", "grid") == "strips")
    cached = runtime.setdefault("gpu_meshes" if gpu else "meshes", {})
    if key not in cached:
        points, weights, indices = rig.mesh_topology(*key)
        mesh = pr.ffi.new("Mesh *")
        mesh.vertexCount = len(points)
        mesh.triangleCount = len(indices) // 3
        # Raylib owns these allocations: UnloadMesh releases CPU and GPU buffers.
        mesh.vertices = pr.ffi.cast("float *", pr.rl.MemAlloc(len(points) * 3 * 4))
        mesh.texcoords = pr.ffi.cast("float *", pr.rl.MemAlloc(len(points) * 2 * 4))
        mesh.indices = pr.ffi.cast("unsigned short *", pr.rl.MemAlloc(len(indices) * 2))
        if gpu:
            mesh.normals = pr.ffi.cast("float *", pr.rl.MemAlloc(len(points) * 3 * 4))
        for i, (x, y) in enumerate(points):
            mesh.vertices[i*3:i*3+3] = (x + PADDING, y + PADDING, 0.)
            mesh.texcoords[i*2:i*2+2] = (x / 128., y / 128.)
            if gpu:
                mesh.normals[i*3:i*3+3] = weights[i]
        mesh.indices[0:len(indices)] = indices
        pr.rl.UploadMesh(mesh, not gpu)
        cached[key] = mesh
    return cached[key]


def update_cpu_mesh(runtime, part, profile, elapsed, position):
    """Previous batched CPU path retained for benchmarking and comparisons."""
    mesh = cached_mesh(runtime, part, profile)
    positions, angle = rig.mesh_pose(part, elapsed, profile, position)
    for i, (x, y) in enumerate(positions):
        mesh.vertices[i*3] = x + PADDING
        mesh.vertices[i*3+1] = y + PADDING
    pr.rl.UpdateMeshBuffer(mesh[0], 0, mesh.vertices, mesh.vertexCount * 3 * 4, 0)
    return mesh, angle


def update_mesh(runtime, part, profile, elapsed, position):
    """Send only per-section wind parameters; vertices stay resident on the GPU."""
    mesh = cached_mesh(runtime, part, profile, gpu=True)
    angle, bend = rig.motion(part, elapsed, profile, position)
    wind = (rig.irregular_wind(profile, position, elapsed) if profile.get("tree_irregular", True)
            else g_effects.sample_wind(profile, *position, elapsed))
    strength = min(1.5, math.hypot(wind["x"], wind["y"]) / 8.) * part["exposure"]
    phase = part["phase"] + position[0] * .019 + position[1] * .013 + int(profile.get("tree_seed", 17)) * .37
    t = elapsed - part["lag"]
    # Reduce phases in double precision before float upload to avoid losing motion
    # resolution after long sessions or with large world coordinates/seeds.
    phases = [(t * 1.35 + phase) % math.tau, (t * 2.05 + phase * .3) % math.tau,
              (t * 1.6 + phase + .8) % math.tau, phase % math.tau]
    values = (math.cos(angle), math.sin(angle), bend, strength,
              *part["pivot"], max(1., part["bounds"][3] - part["pivot"][1]), part["bend_gain"],
              *phases, float(profile.get("tree_mesh", "grid") != "strips"), 0., 0., 0.)
    return {"mesh": mesh, "deformation": pr.ffi.new("float[]", values)}, angle


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
        mesh = meshes.get(name)
        gpu = isinstance(mesh, dict)
        if response:
            shader = runtime["gpu_response"] if gpu else runtime["response_shader"]
            locations = runtime["gpu_response_locations"] if gpu else runtime["response_locations"]
        if response:
            pr.rl_draw_render_batch_active()
            for uniform, value in (("foliage", float(index != 0)), ("partSeed", float(index)),
                                   ("bendAngle", angles.get(name, 0.))):
                pr.set_shader_value(shader, locations[uniform], pr.ffi.new("float *", value),
                                    pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT)
            # A batch flush releases auxiliary texture bindings.
            pr.set_shader_value_texture(shader, locations["trunkResponse"], runtime["trunk_response"])
        if mesh is not None and not isinstance(mesh, list):
            # Flush the trunk/preceding immediate geometry before a direct draw.
            pr.rl_draw_render_batch_active()
            material = runtime.get("mesh_material")
            if material is None:
                material = runtime["mesh_material"] = pr.load_material_default()
                runtime["mesh_default_shader"] = pr.ffi.new("Shader *", material.shader)
                runtime["mesh_identity"] = pr.matrix_identity()
            if gpu:
                material.shader = shader if response else runtime["gpu_color"]
            else:
                material.shader = runtime["response_shader"] if response else runtime["mesh_default_shader"][0]
            material.maps[0].texture = textures[name]
            if response:
                material.shader.locs[int(pr.ShaderLocationIndex.SHADER_LOC_MAP_METALNESS)] = locations["trunkResponse"]
                material.maps[1].texture = runtime["trunk_response"]
            else:
                material.maps[1].texture.id = 0
            if gpu:
                loc = runtime["gpu_response_locations" if response else "gpu_color_locations"]["deformation"]
                pr.rl.SetShaderValueV(material.shader, loc, mesh["deformation"], int(pr.ShaderUniformDataType.SHADER_UNIFORM_VEC4), 4)
                mesh = mesh["mesh"]
            pr.rl.DrawMesh(mesh[0], material, runtime["mesh_identity"])
        else:
            draw_layer(textures[name], mesh)
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
    ensure_gpu_resources(runtime)
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
        meshes, angles = {}, {}
        for part in rig.PARTS:
            meshes[part["name"]], angles[part["name"]] = update_mesh(runtime, part, profile, elapsed, position)
        compose(target, textures, meshes, runtime, angles)
        compose(response_targets[key], textures, meshes, runtime, angles, response=True)
        outputs[str(key)] = target.texture
        responses[str(key)] = response_targets[key].texture


def unload(assets):
    runtime = assets.pop("tree_runtime", {})
    for mesh in runtime.get("meshes", {}).values():
        pr.rl.UnloadMesh(mesh[0])
    for mesh in runtime.get("gpu_meshes", {}).values():
        pr.rl.UnloadMesh(mesh[0])
    for name in ("gpu_color", "gpu_response"):
        if name in runtime:
            pr.unload_shader(runtime[name])
    if runtime.get("mesh_material") is not None:
        # Material textures/shaders are borrowed and released by their owners below.
        pr.rl.MemFree(runtime["mesh_material"].maps)
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
