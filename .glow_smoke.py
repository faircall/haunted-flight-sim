"""Hidden GPU check for selective bloom, masking, and render-target reuse."""
from pathlib import Path
import pyray as pr
import g_glow
import g_effects
from test_puzzles import make_arena

pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
pr.init_window(128, 96, "Glow validation")
assets = {"shaders": {}, "textures": {}}
scene = pr.load_render_texture(128, 96)
image = pr.gen_image_color(8, 8, pr.WHITE)
texture = pr.load_texture_from_image(image)
pr.unload_image(image)
assets["textures"]["square"] = texture
try:
    g_glow.load_shaders(assets["shaders"])
    assert all(info["shader"].id > 0 for info in assets["shaders"].values())
    assert assets["shaders"]["glow_blur"]["blurStep"] >= 0
    item = dict(texture={"collection": "textures", "name": "square"},
                source_rect=dict(x=0, y=0, width=8, height=8),
                dest_rect=dict(x=40, y=32, width=16, height=16),
                glow=dict(enabled=True, strength=.6, color=[.1, .7, 1.], spread="wide"))
    def draw(items, now=0.):
        pr.begin_texture_mode(scene)
        pr.clear_background(pr.BLACK)
        pr.end_texture_mode()
        g_glow.render(scene, pr.Vector2(0, 0), assets, items, make_arena(), {}, g_effects.make_wind_profile(), now)
        image = pr.load_image_from_texture(scene.texture)
        pr.image_flip_vertical(image)
        return image
    image = draw([item])
    assert pr.get_image_color(image, 48, 40).b > 100
    assert pr.get_image_color(image, 37, 40).b > 0, "halo must extend outside silhouette"
    assert pr.get_image_color(image, 48, 75).b == 0, "no vertical inversion"
    Path("artifacts/glow").mkdir(parents=True, exist_ok=True)
    pr.export_image(image, "artifacts/glow/blue-glow.png")
    pr.unload_image(image)
    ids = {key: target.id for key, target in assets["render_targets"].items()}
    image = draw([item, dict(item, glow={})])
    assert pr.get_image_color(image, 48, 40).b == 0, "foreground silhouette must mask emission"
    pr.unload_image(image)
    assert ids == {key: target.id for key, target in assets["render_targets"].items()}
    # Different textures/draws must not inherit another object's last uniform.
    other = dict(item, dest_rect=dict(x=90, y=32, width=8, height=16), glow={})
    for objects in ([item, other], [other, item]):
        image = draw(objects)
        assert pr.get_image_color(image, 94, 40).b == 0, "unselected sprite acquired glow"
        assert pr.get_image_color(image, 48, 40).b > 100
        pr.unload_image(image)
    edge = dict(item, dest_rect=dict(x=32, y=24, width=40, height=40),
                glow=dict(item["glow"], mode="edge", spread="small"))
    image = draw([edge])
    assert pr.get_image_color(image, 52, 44).b == 0, "edge mode filled the interior"
    assert pr.get_image_color(image, 32, 44).b > 50
    pr.export_image(image, "artifacts/glow/edge-glow.png")
    pr.unload_image(image)
    pulsing = dict(edge, glow=dict(edge["glow"], pulse="periodic", pulse_depth=1., pulse_speed=.5))
    expanding = dict(edge, glow=dict(edge["glow"], pulse="periodic", pulse_depth=0., pulse_speed=.5, edge_width=5.))
    zero_rim = dict(expanding, glow=dict(expanding["glow"], edge_min_width=0.))
    image = draw([zero_rim], 1.)
    assert pr.get_image_color(image, 32, 44).b == 0, "zero-width rim still emits"
    assert pr.get_image_color(image, 30, 44).b == 0, "zero-width rim still blooms"
    pr.unload_image(image)
    image = draw([expanding], 0.)
    wide_rim = pr.get_image_color(image, 29, 44).b
    assert pr.get_image_color(image, 52, 44).b == 0
    pr.unload_image(image)
    image = draw([expanding], 1.)
    assert wide_rim > pr.get_image_color(image, 29, 44).b + 40, "rim failed to expand outward"
    assert pr.get_image_color(image, 52, 44).b == 0
    pr.unload_image(image)
    for now, bright in ((0., True), (1., False), (2., True)):
        image = draw([pulsing], now)
        assert (pr.get_image_color(image, 32, 44).b > 50) == bright
        assert (pr.get_image_color(image, 30, 44).b > 0) == bright
        pr.unload_image(image)
    image = draw([dict(item, glow={})])
    assert pr.get_image_color(image, 48, 40).b == 0, "disabled glow must not retain old pixels"
    pr.unload_image(image)
    import g_graphics as g
    g.load_effect_shaders(assets["shaders"])
    fire = g_effects.make_default_fire_emitter({"x": 64., "y": 80.})
    fire["ember_density"] = 0.
    wind = g_effects.make_wind_profile()
    camera = pr.Vector2(0, 0)
    blocker = dict(item, dest_rect=dict(x=0, y=0, width=128, height=96), glow={})
    for depth, hidden in ((100., True), (0., False)):
        blocker["sort_y"] = depth
        g_glow.prepare_effect_occlusion(scene, camera, assets, [blocker])
        for pass_mode in (0, 1):
            bounds = g._effect_screen_bounds(fire, {}, camera, 128, 96)
            info = assets["shaders"]["effect_fire"]
            pr.begin_texture_mode(scene)
            pr.clear_background(pr.BLACK)
            g._bind_effect_uniforms(info, fire, bounds, camera, {}, wind, 1., pass_mode, 128, 96, assets)
            pr.begin_shader_mode(info["shader"])
            g.bind_effect_occlusion_texture(info, assets)
            pr.draw_rectangle_rec(bounds["clip"], pr.WHITE)
            pr.end_shader_mode()
            pr.end_texture_mode()
            image = pr.load_image_from_texture(scene.texture)
            colors = pr.load_image_colors(image)
            lit = sum(colors[i].r > 0 for i in range(128*96))
            pr.unload_image_colors(colors)
            pr.unload_image(image)
            assert (lit == 0) if hidden else (lit > 0), (depth, pass_mode, lit)
    print("Glow GPU check passed: halo, orientation, foreground mask, disabled state, target reuse")
    import time
    import statistics
    pr.unload_render_texture(scene)
    scene = pr.load_render_texture(480,270)
    buddha = pr.load_texture("art/buddha_128.png")
    assets["textures"]["benchmark_buddha"] = buddha
    try:
        statues = [dict(item, source_id=f"statue:{i}", sort_y=120.+(i//4)*110,
            texture={"collection":"textures","name":"benchmark_buddha"},
            source_rect=dict(x=0,y=0,width=128,height=128),
            dest_rect=dict(x=25+(i%4)*110,y=10+(i//4)*120,width=64,height=96),
            glow=dict(enabled=True,strength=.7,mode="edge",spread="small",edge_width=2.,color=[.2,.7,1.],
                      particles=dict(enabled=False,rate=30.,lifetime=2.))) for i in range(8)]
        samples = {}
        clock = 5.
        for enabled in (False,True):
            for statue in statues:
                statue["glow"]["particles"]["enabled"] = enabled
            timings = []
            for frame in range(150):
                clock += 1./60.
                started = time.perf_counter()
                pr.begin_texture_mode(scene); pr.clear_background(pr.BLACK); pr.end_texture_mode()
                g_glow.prepare_effect_occlusion(scene,camera,assets,statues)
                g_glow.render(scene,camera,assets,statues,make_arena(),{},wind,clock)
                pr.rl_draw_render_batch_active()
                if frame >= 30:
                    timings.append((time.perf_counter()-started)*1000.)
            samples[enabled] = statistics.median(timings)
        runtime = assets["glow_particles"]
        assert runtime["readbacks"] == 1, "eight statues should share one texture readback"
        assert 100 < len(runtime["particles"]) <= 8*48
        image = pr.load_image_from_texture(scene.texture); pr.image_flip_vertical(image)
        pr.export_image(image,"artifacts/glow/edge-motes.png"); pr.unload_image(image)
        print(f"Eight statues CPU submission median: off={samples[False]:.3f}ms on={samples[True]:.3f}ms; motes={len(runtime['particles'])}; readbacks={runtime['readbacks']}")
    finally:
        pr.unload_texture(buddha)
finally:
    for info in assets["shaders"].values():
        pr.unload_shader(info["shader"])
    for target in assets.get("render_targets", {}).values():
        pr.unload_render_texture(target)
    pr.unload_texture(texture)
    pr.unload_render_texture(scene)
    pr.close_window()
