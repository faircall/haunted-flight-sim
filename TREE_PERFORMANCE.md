# Painted-grid tree performance

Measured locally on 2026-09-20, Windows, RTX 3060 Ti, current Python/pyray runtime.
These are warmed CPU wall-clock timings for `g_tree_render.prepare`, including
mesh generation and submission of the color and directional-response textures.
They exclude the rest of the scene, lighting, cast shadows, and presentation.
Submission timings can also include driver stalls; they are not pure GPU timings.

| Animated trees | Previous scalar-call optimization, median ms | Cached/batched, median ms |
| --- | ---: | ---: |
| 1 | 8.98 | 2.71 |
| 5 | 42.99 | 11.15 |
| 10 | 85.55 | 21.55 |
| 25 | 225.91 | 53.10 |

Both paths were measured in this pass. Preparation is about 3.3-4.3 times faster.
At 60 FPS the entire frame has 16.7 ms: ten fully animated trees still exceed
that budget before the rest of the game. This is not yet a forest-scale renderer.

## Implementation

- Cache shared vertices, UVs, triangle indices, attachment weights, along-strand
  weights, and spatial phase offsets by bounds/pivot/mesh mode.
- Evaluate rotation sine/cosine once per part, and share its angle with lighting.
- Retain CPU deformation with the original arithmetic and unchanged artwork.
- Keep reusable indexed GPU meshes for the five parts (separate grids for strip
  comparison mode). Upload each part's positions once per tree; reuse that upload
  for both color and directional-response passes.
- Replace 14,272 scalar UV/vertex calls per tree with five buffer updates and ten
  mesh draws. The same 892 foliage quads are rendered with the same triangle split.
- Share mesh buffers across trees; unload their CPU/GPU allocations at renderer
  shutdown. Materials borrow existing textures/shaders without taking ownership.

The original immediate-mode mesh generation remains available for the standalone
experiments and as a benchmark reference. No new dependency was added. The
independent generated-strand implementation is unchanged.

## Reproduce and validate

```powershell
python benchmark_trees.py --verify --output artifacts/tree-wind/benchmark-batched.json
python benchmark_trees.py --reference --output artifacts/tree-wind/benchmark-reference.json
python -m unittest test_tree_animation test_tree_game test_entity_self_shadow
python .tree_game_smoke.py
```

Five warm-up frames and 20 measured frames per tree count. The benchmark also
records timings after synchronizing through texture readback; those include
transfer overhead and should not be treated as production frame times.

`--verify` compares reference and batched color/response textures byte-for-byte:
two trees with different seeds/positions, grid and strip modes, calm/default/
strong/regular wind, and three animation times. All comparisons passed. It also
checks shared mesh counts, tree removal, full unload, and resource recreation.
83 unit tests passed, including exact geometry/UV parity and cache keys following
changes to pivots/bounds. The real-game lighting/motion/cleanup check passed.

## Remaining opportunities (not implemented)

1. Reuse composed textures when pose inputs are unchanged (paused or calm).
   Invalidation must include asset/shader reloads and all wind/rig inputs.
2. Skip trees outside both visible and shadow-relevant regions. Simple camera
   culling alone can remove shadows from trees just outside the view.
3. Move deformation into a vertex shader if larger tree counts require it. The
   current batched version deliberately retains CPU calculations for exact parity.
4. Consider reduced update rates/distant detail only after the above. These can
   affect motion smoothness or appearance and need visual evaluation.

Each tree owns two 160x160 RGBA8 targets: 200 KiB of color data, plus render-target
storage/depth overhead. Cached GPU geometry is shared rather than per tree.
