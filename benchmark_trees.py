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
    cases = ((0., True), (1., True), (3., True), (1., False))
    try:
        for mesh in ("grid", "strips"):
            for amount, irregular in cases:
                for tree in entities["brains"].values():
                    tree.update(tree_mesh=mesh, wind_response=amount, tree_irregular=irregular)
                for elapsed in (0., 3., 17.):
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
                    assert captures[0] == captures[1], (mesh, amount, irregular, elapsed,
                        [sum(a != b for a, b in zip(old, new)) for old, new in zip(*captures)])
        # GPU grids are shared by topology, not allocated for each tree/frame.
        assert len(assets["tree_runtime"]["meshes"]) == len(rig.PARTS) * 2
        trees.prepare(assets, {"brains": {}}, {}, profile, 0.)
        assert not assets["tree_runtime"]["targets"]
        assert not assets["tree_runtime"]["response_targets"]
        trees.unload(assets)
        assert not assets
        # The timed run below also exercises recreating everything after unload.
    finally:
        trees.update_mesh = optimized
    print("Pixel-identical color/response maps: two trees, grid/strips, calm/normal/strong/regular wind, three times")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--frames",type=int,default=20)
    parser.add_argument("--verify", action="store_true", help="Compare old and optimized rendering pixel-for-pixel first")
    parser.add_argument("--reference", action="store_true", help="Benchmark the previous immediate-mode renderer")
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
                    renderer="reference" if args.reference else "batched",
                    quads_per_tree=sum(len(list(rig.foliage_mesh(p,1.,profile))) for p in rig.PARTS))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(data,indent=2),encoding="utf-8")
    finally:
        trees.unload(assets)
        pr.close_window()


if __name__ == "__main__":
    main()
