"""Selective emission and bloom. Plain saved settings; GPU resources live in assets."""
import pyray as pr
import math
import zlib

SPREADS = ("small", "medium", "wide")
RADII = (1.0, 2.0, 4.0)
PULSES = ("none", "periodic", "random seeded")


def pulse_multiplier(authored, now):
    """Smooth modulation below the authored peak; evaluated directly from time."""
    mode = authored.get("pulse", "none")
    speed = max(0., float(authored.get("pulse_speed", .5)))
    depth = max(0., min(1., float(authored.get("pulse_depth", .65))))
    if mode == "none" or speed == 0. or depth == 0.:
        return 1.
    position = float(now) * speed
    if mode == "periodic":
        wave = .5 + .5 * math.cos(position * math.tau)
    elif mode == "random seeded":
        import g_effects
        seed = int(authored.get("pulse_seed", 1))
        cell = math.floor(position)
        t = position - cell
        t = t*t*t*(t*(t*6.-15.)+10.)
        a = g_effects.procedural_hash(cell, 97, seed)
        b = g_effects.procedural_hash(cell+1, 97, seed)
        wave = a + (b-a)*t
    else:
        return 1.
    return 1. - depth + depth*wave


def settings(obj, now=0.0, effect=False, apply_pulse=True):
    authored = obj.get("glow", {})
    default = effect and obj.get("type") in ("fire", "ember", "spark")
    strength = max(0., min(1., float(authored.get("strength", .25 if default else .5))))
    strength *= bool(authored.get("enabled", default))
    transition = obj.get("glow_transition")
    if transition:
        t = max(0., min(1., (now-transition["start"])/max(.0001, transition["duration"])))
        t = t*t*(3.-2.*t)
        strength = transition["from"]+(strength-transition["from"])*t
    if apply_pulse:
        strength *= pulse_multiplier(authored, now)
    pulsing = authored.get("pulse", "none") != "none"
    maximum_width = max(1., min(6., float(authored.get("edge_width", 3. if pulsing else 1.))))
    width_depth = max(0., min(1., float(authored.get("edge_pulse", 1.))))
    wave = pulse_multiplier(dict(authored, pulse_depth=1.), now)
    edge_width = 1. + (maximum_width-1.)*(1.-width_depth+width_depth*wave)
    return dict(strength=strength, color=[max(0., min(1., float(c))) for c in authored.get("color", [0.3, .7, 1.])[:3]],
                spread=authored.get("spread", "medium"), mode=authored.get("mode", "whole"), edge_width=edge_width)


def set_glow(arena, identity, enabled=True, color=None, strength=None, spread=None, fade=0.0, mode=None,
             pulse=None, pulse_speed=None, pulse_depth=None, pulse_seed=None, edge_width=None, edge_pulse=None):
    """Address player, collection:id, or a persistent_id; return the arena."""
    matches = []
    player = arena.get("player_info", {})
    if identity == "player":
        matches.append(player)
    for collection, objects in arena.get("entities", {}).items():
        if not isinstance(objects, dict):
            continue
        for key, obj in objects.items():
            if isinstance(obj, dict) and (identity == f"{collection}:{key}" or identity == obj.get("persistent_id")):
                matches.append(obj)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous glow target: " + str(identity))
    if spread is not None and spread not in SPREADS:
        raise ValueError("Unknown glow spread: " + str(spread))
    if mode is not None and mode not in ("whole", "edge"):
        raise ValueError("Unknown glow mode: " + str(mode))
    if pulse is not None and pulse not in PULSES:
        raise ValueError("Unknown glow pulse: " + str(pulse))
    obj = matches[0]
    now = float(arena.get("time_elapsed", 0.))
    previous = settings(obj, now, obj.get("type") in ("fire", "ember", "spark"), apply_pulse=False)["strength"]
    value = dict(obj.get("glow", {}), enabled=bool(enabled))
    if color is not None:
        if len(color) != 3:
            raise ValueError("Glow color needs three RGB components")
        value["color"] = [max(0., min(1., float(c))) for c in color]
    if strength is not None:
        value["strength"] = max(0., min(1., float(strength)))
    if spread is not None:
        value["spread"] = spread
    if mode is not None:
        value["mode"] = mode
    if pulse is not None:
        value["pulse"] = pulse
        value.setdefault("pulse_seed", 1 + zlib.crc32(str(identity).encode("utf-8")) % 2147483646)
    if pulse_speed is not None:
        value["pulse_speed"] = max(0., float(pulse_speed))
    if pulse_depth is not None:
        value["pulse_depth"] = max(0., min(1., float(pulse_depth)))
    if pulse_seed is not None:
        value["pulse_seed"] = int(pulse_seed)
    if edge_width is not None:
        value["edge_width"] = max(1., min(6., float(edge_width)))
    if edge_pulse is not None:
        value["edge_pulse"] = max(0., min(1., float(edge_pulse)))
    obj["glow"] = value
    obj.pop("glow_transition", None)
    if fade > 0.:
        obj["glow_transition"] = dict(start=now, duration=float(fade), **{"from": previous})
    return arena


def inspect(ui, obj, key="glow", effect=False):
    import g_ui
    value = dict(obj.get("glow", {}))
    default = effect and obj.get("type") in ("fire", "ember", "spark")
    enabled, changed = g_ui.ui_checkbox(ui, key+":enabled", "Glow", value.get("enabled", default))
    value["enabled"] = enabled
    if enabled:
        value["strength"], edit = g_ui.ui_number_input_float(ui, key+":strength", "glow strength", value.get("strength", .25 if default else .5), 0., 1.)
        changed |= edit
        value["spread"], edit = g_ui.ui_dropdown(ui, key+":spread", "glow spread", value.get("spread", "medium"), SPREADS)
        changed |= edit
        if not effect:
            value["mode"], edit = g_ui.ui_dropdown(ui, key+":mode", "glow mode", value.get("mode", "whole"), ("whole", "edge"))
            changed |= edit
        value["pulse"], edit = g_ui.ui_dropdown(ui, key+":pulse", "glow pulse", value.get("pulse", "none"), PULSES)
        changed |= edit
        if value["pulse"] != "none":
            value["pulse_speed"], edit = g_ui.ui_number_input_float(ui, key+":pulse_speed", "pulse speed Hz", value.get("pulse_speed", .5), 0., 5.)
            changed |= edit
            value["pulse_depth"], edit = g_ui.ui_number_input_float(ui, key+":pulse_depth", "pulse depth", value.get("pulse_depth", .65), 0., 1.)
            changed |= edit
            if value["pulse"] == "random seeded":
                seed = 1 + zlib.crc32(str(obj.get("persistent_id", obj.get("id", key))).encode("utf-8")) % 2147483646
                value["pulse_seed"], edit = g_ui.ui_number_input_int(ui, key+":pulse_seed", "pulse seed", value.get("pulse_seed", seed), 1, 2147483647)
                changed |= edit
        if not effect and value.get("mode", "whole") == "edge":
            value["edge_width"], edit = g_ui.ui_number_input_float(ui, key+":edge_width", "max rim width", value.get("edge_width", 3. if value["pulse"] != "none" else 1.), 1., 6.)
            changed |= edit
            value["edge_pulse"], edit = g_ui.ui_number_input_float(ui, key+":edge_pulse", "rim expansion", value.get("edge_pulse", 1.), 0., 1.)
            changed |= edit
        if not effect:
            value["color"], edit = g_ui.ui_color3_editor(ui, key+":color", "glow color", value.get("color", [.3, .7, 1.]))
            changed |= edit
    if changed:
        obj["glow"] = value
        obj.pop("glow_transition", None)


def load_shaders(result):
    for name, uniforms in (("glow_source", ("emissionColor", "emissionStrength", "edgeOnly", "maskStep", "edgeWidth")), ("glow_blur", ("blurStep",)), ("effect_occlusion", ("groundDepth",))):
        shader = pr.load_shader("", "shaders/"+name+".fs")
        result[name] = dict(shader=shader, **{key: pr.get_shader_location(shader, key) for key in uniforms})


def prepare_effect_occlusion(scene, camera, assets, items):
    """One screen-space ground-depth mask shared by fire body/core/bloom."""
    import g_graphics as g
    if "effect_occlusion" not in assets["shaders"]:
        load_shaders(assets["shaders"])
    target = g.get_or_create_render_target(assets, "effect_occlusion", scene.texture.width, scene.texture.height)
    info = assets["shaders"]["effect_occlusion"]
    pr.begin_texture_mode(target)
    pr.clear_background(pr.BLANK)
    pr.begin_shader_mode(info["shader"])
    for item in items:
        texture = g.resolve_render_item_texture(item, assets)
        if texture is None and not item.get("draw_data", {}).get("cutout_rig_parts"):
            continue
        pr.rl_draw_render_batch_active()
        g.set_shader_float(info["shader"], info["groundDepth"], item.get("sort_y", item.get("base_world", {}).get("y", 0.))-camera.y)
        g._draw_render_item_main_shape(item, texture, camera, assets)
    pr.end_shader_mode()
    pr.end_texture_mode()


def render(scene, camera, assets, items, arena, emitters, wind, now, preview=False):
    import g_graphics as g
    import g_puzzles as p
    width, height = scene.texture.width, scene.texture.height
    objects = [(item, settings(item, now)) for item in items]
    puzzles = [(obj, settings(obj, now)) for obj in p.objects(arena)
               if not p.object_state(arena, obj).get("collected") and obj.get("type") != "puzzle spawn"]
    effects = [(key, obj, settings(obj, now, True)) for key, obj in emitters.items()
               if obj.get("enabled", True) and (not preview or obj.get("preview_enabled", True))]
    active = {value["spread"] for _, value in objects+puzzles if value["strength"] > 0.}
    active.update(value["spread"] for _, _, value in effects if value["strength"] > 0.)
    if not active:
        return
    if "glow_source" not in assets["shaders"]:
        load_shaders(assets["shaders"])
    source = g.get_or_create_render_target(assets, "glow_source", width, height)
    scratch = g.get_or_create_render_target(assets, "glow_scratch", width, height)
    blurred = g.get_or_create_render_target(assets, "glow_blurred", width, height)
    silhouette = g.get_or_create_render_target(assets, "glow_silhouette", width, height)
    for target in (source, scratch, blurred):
        pr.set_texture_filter(target.texture, pr.TextureFilter.TEXTURE_FILTER_BILINEAR)
        pr.set_texture_wrap(target.texture, pr.TextureWrap.TEXTURE_WRAP_CLAMP)
    source_info, blur_info = (assets["shaders"][name] for name in ("glow_source", "glow_blur"))
    src = pr.Rectangle(0, 0, width, -height)
    dst = pr.Rectangle(0, 0, width, height)
    for spread, radius in zip(SPREADS, RADII):
        if spread not in active:
            continue
        pr.begin_texture_mode(source)
        pr.clear_background(pr.BLACK)
        pr.begin_shader_mode(source_info["shader"])
        def bind(value):
            # Uniform changes do not flush raylib's queued sprite vertices.
            pr.rl_draw_render_batch_active()
            g.set_shader_vec3(source_info["shader"], source_info["emissionColor"], *value["color"])
            g.set_shader_float(source_info["shader"], source_info["emissionStrength"], value["strength"] if value["spread"] == spread else 0.)
            g.set_shader_float(source_info["shader"], source_info["edgeOnly"], 0.)
        # Puzzle placeholders are drawn before the sorted sprites, like the scene.
        for obj, value in puzzles:
            bind(value)
            box = p.bounds(obj, arena["tile_map"])
            rect = pr.Rectangle(round(box["x"]-camera.x), round(box["y"]-camera.y), box["width"], box["height"])
            if p.object_state(arena, obj).get("open"):
                pr.draw_rectangle_lines_ex(rect, 1., pr.WHITE)
            else:
                pr.draw_rectangle_rec(rect, pr.WHITE)
        # Black non-emitting silhouettes mask sources behind foreground sprites.
        for item, value in objects:
            texture = g.resolve_render_item_texture(item, assets)
            if texture is None and not item.get("draw_data", {}).get("cutout_rig_parts"):
                continue
            bind(value)
            if value["mode"] == "edge" and value["strength"] > 0. and value["spread"] == spread:
                # Build the whole evaluated silhouette first: no seams between limbs.
                pr.end_shader_mode()
                pr.end_texture_mode()
                pr.begin_texture_mode(silhouette)
                pr.clear_background(pr.BLANK)
                g._draw_render_item_main_shape(item, texture, camera, assets)
                pr.end_texture_mode()
                pr.begin_texture_mode(source)
                pr.begin_shader_mode(source_info["shader"])
                bind(value)
                g.set_shader_float(source_info["shader"], source_info["edgeOnly"], 1.)
                g.set_shader_float(source_info["shader"], source_info["edgeWidth"], value["edge_width"])
                g.set_shader_vec2(source_info["shader"], source_info["maskStep"], 1./width, 1./height)
                pr.draw_texture_pro(silhouette.texture, src, dst, pr.Vector2(0, 0), 0., pr.WHITE)
            else:
                g._draw_render_item_main_shape(item, texture, camera, assets)
        pr.end_shader_mode()
        pr.end_texture_mode()
        # Sharp object emission remains visible even in an unlit room.
        pr.begin_texture_mode(scene)
        pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
        pr.draw_texture_pro(source.texture, src, dst, pr.Vector2(0, 0), 0., pr.WHITE)
        pr.end_blend_mode()
        pr.end_texture_mode()
        pr.begin_texture_mode(source)
        pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
        for key, obj, value in effects:
            if value["spread"] != spread or value["strength"] <= 0.:
                continue
            group = "emissive" if obj.get("type") == "fire" else obj.get("render_group", "emissive")
            submission = g._procedural_effect_submission(obj, group)
            if not submission or submission["material"] != "emissive_additive":
                continue
            bounds = g._effect_screen_bounds(obj, arena["tile_map"], camera, width, height)
            if bounds is None:
                continue
            emitter = dict(obj, opacity=float(obj.get("opacity", 1.))*value["strength"])
            info = assets["shaders"][submission["shader"]]
            g._bind_effect_uniforms(info, emitter, bounds, camera, arena["tile_map"], wind, now, submission["pass_mode"], width, height, assets)
            pr.begin_shader_mode(info["shader"])
            g.bind_effect_occlusion_texture(info, assets)
            pr.draw_rectangle_rec(bounds["clip"], pr.WHITE)
            pr.end_shader_mode()
        pr.end_blend_mode()
        pr.end_texture_mode()
        for target, texture, step in ((scratch, source.texture, (radius/width, 0.)), (blurred, scratch.texture, (0., radius/height))):
            pr.begin_texture_mode(target)
            pr.clear_background(pr.BLACK)
            pr.begin_shader_mode(blur_info["shader"])
            g.set_shader_vec2(blur_info["shader"], blur_info["blurStep"], *step)
            pr.draw_texture_pro(texture, src, dst, pr.Vector2(0, 0), 0., pr.WHITE)
            pr.end_shader_mode()
            pr.end_texture_mode()
        pr.begin_texture_mode(scene)
        pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
        pr.draw_texture_pro(blurred.texture, src, dst, pr.Vector2(0, 0), 0., pr.WHITE)
        pr.end_blend_mode()
        pr.end_texture_mode()
