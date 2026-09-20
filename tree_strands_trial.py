"""Independent comparison: python tree_strands_trial.py. Existing game trees are untouched."""
import argparse
from pathlib import Path

import pyray as pr
import g_effects
import g_generated_tree as generated
import g_tree_render as painted
from tree_wind_trial import PRESETS, BACKGROUNDS

ROOT = Path(__file__).resolve().parent


def scalar(shader, name, value):
    pr.set_shader_value(shader, pr.get_shader_location(shader,name), pr.ffi.new("float *",float(value)),
                        pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT)


def render_generated(target, runtime, geometry, leaf_shader, response=False, show_stems=True):
    stems,leaves = geometry
    pr.begin_texture_mode(target)
    pr.clear_background(pr.WHITE if response else pr.BLANK)
    pr.rl_push_matrix()
    pr.rl_translatef(0,160,0)
    pr.rl_scalef(1,-1,1)
    pr.rl_disable_backface_culling()
    if response:
        pr.rl_set_blend_factors(pr.RL_ONE,pr.RL_ZERO,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM)
        shader = runtime["response_shader"]
        pr.begin_shader_mode(shader)
        scalar(shader,"foliage",0)
        pr.set_shader_value_texture(shader,runtime["response_locations"]["trunkResponse"],runtime["trunk_response"])
    painted.draw_layer(runtime["textures"]["trunk"])
    if response:
        pr.end_shader_mode()
    if show_stems:
        ink = pr.Color(175,175,175,175) if response else pr.Color(74,70,40,170)
        for a,b in stems:
            pr.draw_line_ex(pr.Vector2(a[0]+16,a[1]+16),pr.Vector2(b[0]+16,b[1]+16),.45,ink)
    pr.begin_shader_mode(leaf_shader)
    scalar(leaf_shader,"responsePass",float(response))
    pr.rl_set_texture(0)
    pr.rl_begin(pr.RL_TRIANGLES)
    for quad,color,normal,fill in leaves:
        pr.rl_color4ub(*color,255)
        for index in (0,1,2,0,2,3):
            x,y = quad[index]
            pr.rl_tex_coord2f(normal,fill)
            pr.rl_vertex2f(x+16,y+16)
    pr.rl_end()
    pr.end_shader_mode()
    if response:
        pr.end_blend_mode()
    pr.rl_pop_matrix()
    pr.rl_draw_render_batch_active()
    pr.rl_enable_backface_culling()
    pr.end_texture_mode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",type=Path)
    parser.add_argument("--time",type=float,default=3.)
    parser.add_argument("--seed",type=int,default=17)
    parser.add_argument("--density",type=float,default=1.3)
    parser.add_argument("--still",action="store_true")
    parser.add_argument("--light",choices=("off","down","up","left","right"),default="off")
    args = parser.parse_args()
    if args.capture:
        pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.init_window(1040,830,"Willow: painted grid vs generated strands")
    pr.set_target_fps(60)
    assets,targets,shaders = {},[],[]
    try:
        leaf_shader = pr.load_shader("",str(ROOT/"shaders/generated_tree_leaf.fs")); shaders.append(leaf_shader)
        display_shader = pr.load_shader("",str(ROOT/"shaders/tree_compare.fs")); shaders.append(display_shader)
        assert pr.get_shader_location(leaf_shader,"responsePass") >= 0
        assert pr.get_shader_location(display_shader,"responseTexture") >= 0
        targets = [pr.load_render_texture(160,160) for _ in range(2)]
        capture = pr.load_render_texture(1040,830) if args.capture else None
        if capture:
            targets.append(capture)
        for target in targets:
            pr.set_texture_filter(target.texture,pr.TextureFilter.TEXTURE_FILTER_POINT)
        tree = dict(type="willow tree",position=dict(tile_x=0,tile_y=0,x=0.,y=0.))
        entities = {"brains":{1:tree}}
        tile_map = dict(tile_width=16,tile_height=16)
        seed,density,elapsed = args.seed,args.density,0.
        strands = generated.build(seed,density)
        paused,still,stems,wind_index,background = False,args.still,True,2,0
        lights = ("off","down","up","left","right")
        light_index = lights.index(args.light)
        while not pr.window_should_close():
            pressed = lambda key: pr.is_key_pressed(getattr(pr.KeyboardKey,"KEY_"+key))
            if pressed("SPACE"): paused = not paused
            if pressed("R"): still = not still
            if pressed("W"): wind_index = (wind_index+1)%len(PRESETS)
            if pressed("B"): background = (background+1)%len(BACKGROUNDS)
            if pressed("L"): light_index = (light_index+1)%len(lights)
            if pressed("V"): stems = not stems
            rebuild = False
            if pressed("S"):
                seed += 1
                rebuild = True
            if pressed("D"):
                density = .8 if density >= 1.8 else 1.8 if density >= 1.3 else 1.3
                rebuild = True
            if rebuild: strands = generated.build(seed,density)
            if not paused: elapsed += pr.get_frame_time()
            if args.capture: elapsed = args.time
            wind_name,strength,gust = PRESETS[wind_index]
            profile = dict(g_effects.make_wind_profile(),strength=0. if still else strength,
                           gust_strength=0. if still else gust,tree_seed=seed)
            tree["tree_seed"] = seed
            painted.prepare(assets,entities,tile_map,profile,elapsed)
            geometry = generated.pose(strands,elapsed,profile,still)
            for index,target in enumerate(targets[:2]):
                render_generated(target,assets["tree_runtime"],geometry,leaf_shader,index==1,stems)
            pr.begin_drawing()
            if capture: pr.begin_texture_mode(capture)
            pr.clear_background(pr.Color(20,25,28,255))
            pr.draw_text("WILLOW / GENERATED STRANDS COMPARISON",20,15,24,pr.RAYWHITE)
            for column,(title,texture,response) in enumerate((
                    ("Painted grid (existing)",assets["tree_textures"]["1"],assets["tree_responses"]["1"]),
                    ("Generated strands (experiment)",targets[0].texture,targets[1].texture))):
                x = 20+column*520
                pr.draw_text(title,x,53,19,pr.LIGHTGRAY)
                for y,scale,dx in ((80,3,0),(579,1,160)):
                    pr.draw_rectangle(x+dx,y,160*scale,160*scale,pr.Color(*BACKGROUNDS[background]))
                    pr.begin_shader_mode(display_shader)
                    scalar(display_shader,"lit",float(light_index!=0))
                    weights = [float(light_index==i+1) for i in range(4)]
                    pr.set_shader_value(display_shader,pr.get_shader_location(display_shader,"lightWeights"),
                        pr.ffi.new("float[]",weights),pr.ShaderUniformDataType.SHADER_UNIFORM_VEC4)
                    pr.set_shader_value_texture(display_shader,pr.get_shader_location(display_shader,"responseTexture"),response)
                    pr.draw_texture_pro(texture,pr.Rectangle(0,0,160,160),pr.Rectangle(x+dx,y,160*scale,160*scale),pr.Vector2(0,0),0,pr.WHITE)
                    pr.end_shader_mode()
                pr.draw_text("Native pixels",x,594,16,pr.GRAY)
            status = f"Wind: {wind_name}   Light: {lights[light_index]}   Density: {density:.1f}   Seed: {seed}"
            pr.draw_text(status,20,754,18,pr.RAYWHITE)
            pr.draw_text(f"{len(strands)} strands / {len(geometry[1])} leaves" + ("   REST POSE" if still else "") + ("   PAUSED" if paused else ""),20,777,17,pr.LIGHTGRAY)
            pr.draw_text("Space Pause   R Rest/motion   W Wind   L Light   D Density   S Seed   V Stems   B Background",20,804,16,pr.LIGHTGRAY)
            if capture: pr.end_texture_mode()
            pr.end_drawing()
            if args.capture:
                args.capture.parent.mkdir(parents=True,exist_ok=True)
                image = pr.load_image_from_texture(capture.texture)
                try:
                    pr.image_flip_vertical(image)
                    assert pr.export_image(image,str(args.capture.resolve()))
                finally: pr.unload_image(image)
                break
    finally:
        painted.unload(assets)
        for target in targets: pr.unload_render_texture(target)
        for shader in shaders: pr.unload_shader(shader)
        pr.close_window()


if __name__ == "__main__":
    main()
