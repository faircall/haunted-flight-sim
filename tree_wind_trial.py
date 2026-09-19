"""Run: python tree_wind_trial.py. Uses original split_tree PNGs without changing them."""
import argparse
from pathlib import Path

import pyray as pr

import g_effects
import g_tree_animation as rig


ROOT = Path(__file__).resolve().parent
PRESETS = (("Still", 0., 0.), ("Breeze", 4., 2.), ("Wind", 8., 5.), ("Gusts", 14., 9.))
BACKGROUNDS = ((34, 43, 41, 255), (82, 89, 76, 255), (238, 224, 185, 255))


def draw_tree(textures, elapsed, profile, mode, pivots=False):
    pr.draw_texture(textures["trunk"], 16, 20, pr.WHITE)
    for part in rig.PARTS:
        texture = textures[part["name"]]
        pr.rl_set_texture(texture.id)
        pr.rl_begin(pr.RL_QUADS)
        pr.rl_color4ub(255, 255, 255, 255)
        pr.rl_normal3f(0, 0, 1)
        for quad in rig.foliage_mesh(part, elapsed, profile, mode=mode):
            for x, y, u, v in quad:
                pr.rl_tex_coord2f(u, v)
                pr.rl_vertex2f(x + 16, y + 20)
        pr.rl_end()
        pr.rl_set_texture(0)
    if pivots:
        for part in rig.PARTS:
            x, y = part["pivot"]
            pr.draw_line(x + 14, y + 20, x + 18, y + 20, pr.MAGENTA)
            pr.draw_line(x + 16, y + 18, x + 16, y + 22, pr.MAGENTA)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="Render one hidden preview frame to PNG and exit")
    parser.add_argument("--time", type=float, default=3.0, help="Animation time for a captured frame")
    parser.add_argument("--mode", choices=("still", "rigid", "hybrid"), default="hybrid")
    parser.add_argument("--regular", action="store_true", help="Use the original periodic wind")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--mesh", choices=("grid", "strips"), default="grid")
    args = parser.parse_args()
    if args.capture:
        pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.init_window(1000, 650, "Willow wind trial")
    pr.set_target_fps(60)
    textures, targets = {}, []
    try:
        for name in ("reference", "trunk", *(part["name"] for part in rig.PARTS)):
            path = ROOT / "art" / "split_tree" / ("willow_tree_" + name + ".png")
            texture = pr.load_texture(str(path))
            if not texture.id:
                raise RuntimeError("Could not load " + str(path))
            textures[name] = texture
            pr.set_texture_filter(texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
        targets = [pr.load_render_texture(160, 160) for _ in range(2)]
        capture_target = pr.load_render_texture(1000, 650) if args.capture else None
        if capture_target:
            targets.append(capture_target)
        for target in targets:
            pr.set_texture_filter(target.texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
        elapsed, paused, pivots, preset, background, reverse = 0., False, False, 2, 0, False
        mode = args.mode
        irregular, seed = not args.regular, args.seed
        mesh = args.mesh
        while not pr.window_should_close():
            pressed = lambda key: pr.is_key_pressed(getattr(pr.KeyboardKey, "KEY_" + key))
            if pressed("SPACE"):
                paused = not paused
            if pressed("P"):
                pivots = not pivots
            if pressed("B"):
                background = (background + 1) % len(BACKGROUNDS)
            if pressed("W"):
                preset = (preset + 1) % len(PRESETS)
            if pressed("R"):
                reverse = not reverse
            if pressed("G"):
                mesh = "strips" if mesh == "grid" else "grid"
            if pressed("N"):
                irregular = not irregular
            if pressed("S"):
                seed += 1
            for key, value in (("ONE", "still"), ("TWO", "rigid"), ("THREE", "hybrid")):
                if pressed(key):
                    mode = value
            if not paused:
                elapsed += pr.get_frame_time()
            if args.capture:
                elapsed = args.time
            name, strength, gust = PRESETS[preset]
            profile = g_effects.make_wind_profile()
            profile.update(strength=strength, gust_strength=gust, direction={"x": -1. if reverse else 1., "y": 0.})
            profile.update(tree_irregular=irregular, tree_seed=seed, tree_mesh=mesh)
            for index, target in enumerate(targets[:2]):
                pr.begin_texture_mode(target)
                pr.clear_background(pr.Color(*BACKGROUNDS[background]))
                if index == 0:
                    pr.draw_texture(textures["reference"], 16, 20, pr.WHITE)
                else:
                    draw_tree(textures, elapsed, profile, mode, pivots)
                pr.end_texture_mode()
            pr.begin_drawing()
            if capture_target:
                pr.begin_texture_mode(capture_target)
            pr.clear_background(pr.Color(20, 25, 28, 255))
            pr.draw_text("WILLOW / WIND STUDY", 20, 16, 24, pr.RAYWHITE)
            pr.draw_text("Reference", 20, 54, 18, pr.LIGHTGRAY)
            pr.draw_text("Animated / " + mode + " / " + mesh, 360, 54, 18, pr.LIGHTGRAY)
            for target, x, scale in ((targets[0], 20, 2), (targets[1], 360, 3)):
                pr.draw_texture_pro(target.texture, pr.Rectangle(0, 0, 160, -160),
                    pr.Rectangle(x, 80, 160 * scale, 160 * scale), pr.Vector2(0, 0), 0, pr.WHITE)
            pr.draw_text("Native pixels", 20, 416, 18, pr.LIGHTGRAY)
            pr.draw_texture_pro(targets[1].texture, pr.Rectangle(0, 0, 160, -160),
                pr.Rectangle(160, 400, 160, 160), pr.Vector2(0, 0), 0, pr.WHITE)
            pr.draw_text("Wind: " + name + ("  <" if reverse else "  >") +
                ("  Irregular / seed " + str(seed) if irregular else "  Original periodic") +
                ("  PAUSED" if paused else ""), 20, 578, 18, pr.RAYWHITE)
            pr.draw_text("1 Still pose   2 Rigid sway   3 Sway + bend   W Wind   R Reverse", 20, 605, 17, pr.LIGHTGRAY)
            pr.draw_text("G Grid/strips   N Wind style   S Seed   Space Pause   P Pivots   B Background", 20, 627, 17, pr.LIGHTGRAY)
            if capture_target:
                pr.end_texture_mode()
            pr.end_drawing()
            if args.capture:
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                image = pr.load_image_from_texture(capture_target.texture)
                try:
                    pr.image_flip_vertical(image)
                    if not pr.export_image(image, str(args.capture.resolve())):
                        raise RuntimeError("Could not export " + str(args.capture))
                finally:
                    pr.unload_image(image)
                break
    finally:
        for target in targets:
            pr.unload_render_texture(target)
        for texture in textures.values():
            pr.unload_texture(texture)
        pr.close_window()


if __name__ == "__main__":
    main()
