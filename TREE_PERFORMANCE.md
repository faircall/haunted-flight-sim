# Painted-grid tree performance

Measured locally on 2026-09-20, Windows, RTX 3060 Ti, current Python/pyray runtime.
These are warmed CPU wall-clock timings for `g_tree_render.prepare`, including
mesh generation and submission of the color and directional-response textures.
They exclude the rest of the scene, lighting, cast shadows, and presentation.
Submission timings can also include driver stalls; they are not pure GPU timings.

| Animated trees | Batched CPU deformation, median ms | GPU deformation, median ms |
| --- | ---: | ---: |
| 1 | 2.87 | 0.97 |
| 5 | 11.75 | 2.41 |
| 10 | 22.63 | 4.44 |
| 25 | 54.45 | 10.21 |

Both paths were measured in this pass. For 5-25 trees, preparation is about
4.9-5.3 times faster. At 60 FPS the entire frame has 16.7 ms: the remaining scene
cost still matters even when tree preparation fits within that budget.

## Implementation

The cached grid, UVs, triangle indices and deformation weights are uploaded once.
Shared static GPU meshes carry along-strand weights, attachment weights and
spatial phase offsets in the normal attribute. A custom vertex shader interprets
that attribute as deformation data rather than lighting normals.

Python evaluates the small set of per-section wind values (angle, bend, strength
and phase). Each part gets four vec4 uniforms. `shaders/tree_deform.vs` evaluates
all vertex displacement and rotation; there are no per-frame position-buffer
uploads or Python per-vertex calculations. The same shader deforms the color and
lighting-response passes, preserving their alignment and the fixed UVs. Temporal
phases are reduced in CPU double precision before upload to retain smoothness
in long sessions and at large world offsets. The trunk remains static.

Color and response GPU programs reload when their source timestamps change.
Renderer unload releases the shared mesh buffers and shaders. The original
immediate path and the batched CPU path remain available for comparisons. The
independent generated-strand experiment is unchanged. No dependency was added.

## Reproduce and validate

```powershell
python benchmark_trees.py --verify --output artifacts/tree-wind/benchmark-gpu.json
python benchmark_trees.py --cpu --output artifacts/tree-wind/benchmark-cpu.json
python -m unittest test_tree_animation test_tree_game test_entity_self_shadow
python .tree_game_smoke.py
```

Five warm-up frames and 20 measured frames per tree count. The benchmark also
records timings after synchronizing through texture readback; those include
transfer overhead and should not be treated as production frame times.

`--verify` compares CPU-reference and GPU color/response textures: two trees
with different seeds/positions, grid and strip modes, calm/default/strong/regular
wind, and five times including 1,000,000 seconds. Calm poses were pixel-identical.
Across 4,096,000 compared pixels, only two differed (one color pixel and its
response pixel); no texture differed by more than one pixel. This is consistent
with floating-point rounding crossing a nearest-sampled texel boundary. The
comparison permits up to eight differing pixels per 160x160 target in motion,
and zero in calm poses, to detect substantive regressions.

The check also covers shared mesh counts, GPU shader reloads, tree removal,
unload, and resource recreation. All 83 tree/lighting unit tests and the real-game
lighting/motion/cleanup check passed. GPU comparison is tested on this machine's
OpenGL driver; exact rounding differences can vary across GPUs.

## Remaining opportunities (not implemented)

1. Reuse composed textures when pose inputs are unchanged (paused or calm).
   Invalidation must include asset/shader reloads and all wind/rig inputs.
2. Skip trees outside both visible and shadow-relevant regions. Simple camera
   culling alone can remove shadows from trees just outside the view.
3. Consider reduced update rates/distant detail only after the above. These can
   affect motion smoothness or appearance and need visual evaluation.

Each tree owns two 160x160 RGBA8 targets: 200 KiB of color data, plus render-target
storage/depth overhead. Cached GPU geometry is shared rather than per tree.
