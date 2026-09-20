"""Warm painted-tree preparation timings; excludes scene lighting/shadows/presentation."""
import argparse
import json
import statistics
import time
from pathlib import Path

import pyray as pr
import g_effects
import g_tree_animation as rig
import g_tree_render as trees


def reference_mesh(runtime, part, profile, elapsed, position):
    """Previous immediate-mode path, retained only for comparisons."""
    return (list(rig.foliage_mesh(part, elapsed, profile, position)),
            rig.motion(part, elapsed, profile, position)[0])


def verify_pixels(assets, profile):
    entities = {"brains": {
        0: dict(type="willow tree", position=dict(x=37., y=13.)),
        1: dict(type="willow tree", position=dict(x=-137., y=43.), tree_seed=93),
    }}
    optimized = trees.update_mesh
    worst_pixels = 0
    total_pixels = 0
    compared_pixels = 0
    cases = ((0., True), (1., True), (3., True), (1., False))
    try:
        for mesh in ("grid", "strips"):
            for amount, irregular in cases:
                for tree in entities["brains"].values():
                    tree.update(tree_mesh=mesh, wind_response=amount, tree_irregular=irregular)
                for elapsed in (0., 3., 17., 123.456, 1000000.):
                    captures = []
                    for update in (reference_mesh, optimized):
                        trees.update_mesh = update
                        trees.prepare(assets, entities, dict(tile_width=16, tile_height=16), profile, elapsed)
                        pixels = []
                        for key in ("tree_textures", "tree_responses"):
                            for tree_id in ("0", "1"):
                                image = pr.load_image_from_texture(assets[key][tree_id])
                                try:
                                    assert image.format == pr.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8
                                    pixels.append(bytes(pr.ffi.buffer(image.data, image.width * image.height * 4)))
                                finally:
                                    pr.unload_image(image)
                        captures.append(pixels)
                    differences = [sum(old[i:i+4] != new[i:i+4] for i in range(0, len(old), 4))
                                   for old, new in zip(*captures)]
                    worst_pixels = max(worst_pixels, *differences)
                    total_pixels += sum(differences)
                    compared_pixels += len(captures[0]) * trees.SIZE * trees.SIZE
                    # Float GPU arithmetic can cross a nearest-sampled texel edge.
                    # Allow at most 8 pixels (0.032% of a target); calm must be exact.
                    assert max(differences) <= (0 if amount == 0 else 8), (mesh, amount, irregular, elapsed, differences)
        # GPU grids are shared by topology, not allocated for each tree/frame.
        assert len(assets["tree_runtime"]["gpu_meshes"]) == len(rig.PARTS) * 2
        # Shader hot reload must recreate both GPU programs without losing meshes.
        runtime = assets["tree_runtime"]
        old_shader = runtime["gpu_color"].id
        runtime["gpu_color_stamp"] = None
        runtime["gpu_response_stamp"] = None
        trees.ensure_gpu_resources(runtime)
        assert runtime["gpu_color"].id != old_shader
        trees.prepare(assets, entities, dict(tile_width=16, tile_height=16), profile, 3.)
        trees.prepare(assets, {"brains": {}}, {}, profile, 0.)
        assert not assets["tree_runtime"]["targets"]
        assert not assets["tree_runtime"]["response_targets"]
        trees.unload(assets)
        assert not assets
        # The timed run below also exercises recreating everything after unload.
    finally:
        trees.update_mesh = optimized
    print(f"GPU comparison: at most {worst_pixels} changed pixels per 160x160 texture; {total_pixels}/{compared_pixels} overall; calm exact")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--frames",type=int,default=20)
    parser.add_argument("--verify", action="store_true", help="Compare GPU output with CPU reference within pixel-error bounds")
    renderer = parser.add_mutually_exclusive_group()
    renderer.add_argument("--reference", action="store_true", help="Benchmark the previous immediate-mode renderer")
    renderer.add_argument("--cpu", action="store_true", help="Benchmark the previous batched CPU deformation")
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.init_window(160,160,"Tree preparation benchmark")
    results = []
    profile = g_effects.make_wind_profile()
    assets = {}
    try:
        if args.verify:
            verify_pixels(assets, profile)
        if args.reference:
            trees.update_mesh = reference_mesh
        elif args.cpu:
            trees.update_mesh = trees.update_cpu_mesh
        for count in (1,5,10,25):
            entities = {"brains": {i:dict(type="willow tree",position=dict(x=i*37.,y=i*13.)) for i in range(count)}}
            submit,complete = [],[]
            for frame in range(args.frames+5):
                pr.begin_drawing()
                start = time.perf_counter()
                trees.prepare(assets,entities,dict(tile_width=16,tile_height=16),profile,frame/60.)
                submitted = time.perf_counter()
                # Readback waits for queued rendering, but includes transfer overhead.
                image = pr.load_image_from_texture(assets["tree_responses"][str(count-1)])
                pr.unload_image(image)
                finished = time.perf_counter()
                pr.end_drawing()
                if frame >= 5:
                    submit.append((submitted-start)*1000)
                    complete.append((finished-start)*1000)
            row = dict(trees=count,submit_median_ms=round(statistics.median(submit),3),
                       completed_with_readback_median_ms=round(statistics.median(complete),3),
                       submit_p95_ms=round(sorted(submit)[int((len(submit)-1)*.95)],3))
            results.append(row)
            print(row)
        data = dict(scope=__doc__,frames=args.frames,results=results,
                    renderer="reference" if args.reference else "cpu" if args.cpu else "gpu",
                    quads_per_tree=sum(len(list(rig.foliage_mesh(p,1.,profile))) for p in rig.PARTS))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2),encoding="utf-8")
    finally:
        trees.unload(assets)
        pr.close_window()


if __name__ == "__main__":
    main()
