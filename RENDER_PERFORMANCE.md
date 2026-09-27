# Rendering performance: lake temple

## Implemented

- **Static ground batches:** tile textures, shape masks, painted materials and
  ordinary decals bake into 4x4-cell render targets. Play mode draws one quad per
  visible chunk. Grass deformation and footsteps remain live. The editor keeps
  its direct tile path. Oversized decals use that path to preserve painter order.
- **Bounded retention and loading:** terrain and ground caches retain up to 256
  chunks each (or the visible set if larger). Small maps fitting that budget,
  including this lake's 140 chunks, prepare at scene entry. This moves first-visit
  terrain generation out of walking frames. Larger maps retain recent chunks;
  they still need asynchronous streaming for hitch-free first visits.
- **Shared light atlas:** each entity light field is rasterized once per frame
  for the ordinary scenery path. Its shader sums selected atlas texels and uses
  the existing lighting compositor's exact tone mapping. Consecutive props with
  the same light set share a shader batch. Binary-alpha lake props use this path;
  response-mapped trees, layered characters and facade receivers keep their
  specialized passes. Cutaways still composite the completed lit object once.
- **Shared pose work:** character draw commands are reused across passes. Each
  animated shadow silhouette is packed once per frame and shared by all lamps.
- **Visibility work:** a spatial grid reduces object overlap tests, direct sprite
  work is culled conservatively, large polygon overlap tests use native arrays,
  and plain-object light records/aggregate samples are cached with invalidation.
  Unreachable facade columns skip visibility rays. Moving actors, lights,
  blockers, doors and edited geometry remain live. Shadow casters and reflected
  objects keep the full world list, independently of direct sprite culling.
- Known-type shader uploads and sprite commands call raylib's C interface
  directly. This avoids repeated Python argument conversion; unlike batching,
  this particular saving will naturally disappear into the future C port.

The GPU atlas is limited to 32 lights, with the reference renderer as fallback.
Lighting debug previews also use the reference renderer. The 12-light lake atlas
is 1920x810; ground colour storage is at most 4 MiB at 16-pixel tiles, plus render
target depth attachments. Source texture replacement, material edits, map
replacement, shader reload and module reload invalidate the appropriate data.

## Measurement

The test machine reports an NVIDIA GeForce RTX 3060 Ti through raylib. These are
local measurements, not certification across moderate machines.

The original 60-frame-per-view baseline submitted frames in roughly 50–60 ms.
After the structural changes, the longer 240-frame-per-view run submitted them
in roughly 23–33 ms. The ordinary entity render stage fell from approximately
14–15 ms to approximately 3 ms. These separate runs varied with machine load;
use the repeatable comparison below when evaluating another machine.

Final warm run (`perf-prewarmed`, 240 frames per view):

| View | Submission median | p95 | p99 | Completion + readback median |
| --- | ---: | ---: | ---: | ---: |
| Approach | 22.6 ms | 23.5 ms | 32.3 ms | 27.5 ms |
| Walking | 32.9 ms | 35.1 ms | 45.4 ms | 40.3 ms |
| Interior | 24.5 ms | 25.8 ms | 36.0 ms | 29.9 ms |

All 720 submitted frames exceeded 16.7 ms. Prewarming reduced the worst ground
preparation frame from 56.2 ms to 2.85 ms on this route; the worst complete game
submission fell from 87.5 ms to 46.8 ms. This fixes the observed first-visit terrain
hitch, while leaving the broader frame-budget work explicit.

The retained reference switch disables ground batches, the scenery atlas and
sprite culling; it **retains the shared CPU/pose optimizations**. It therefore
isolates those three changes, rather than recreating the entire original build.
Its submission medians were 32.0, 42.2 and 32.5 ms respectively, so the three
switchable structural changes alone save approximately 22–29% in that comparison.
Both runs use uncapped rendering, fixed simulation steps, hidden editor UI and
the same approach, walking and interior views. Profiling is run separately from
the timed frames. JSON includes medians, p95, p99, maximum and the count exceeding
16.7 ms, plus individual frame/stage timings.

`submit_ms` measures the game update and render submission. `complete_ms` also
waits for GPU readback **and pays its transfer cost**; it is not a GPU timer. Both
exclude final window presentation. Startup/prewarming is outside the warm-frame
numbers. Do not translate these into a promised displayed frame rate.

```powershell
python .tree_game_smoke.py --water-benchmark --label optimized --frames 240 --profile-frames 0
python .tree_game_smoke.py --water-benchmark --reference --label reference --frames 240 --profile-frames 0
python .tree_game_smoke.py --water-benchmark --label cpu --frames 60 --profile-frames 8 --profile-case walking
```

Artifacts go to `artifacts/moonlit-water-temple/`. Reference and optimized captures
must be compared with identical frame counts/settings. Profiling walks through
the middle of the route as well, rather than profiling only its final position.

## Validation

All three fixed-view RGB captures matched the original baseline. The long
reference/optimized comparison also matched exactly. Native render checks cover
water colour/texel preservation, roof transitions, lamp extinction, windows,
the courtyard and the surface editor. Ground-specific checks compare against
tile drawing after offscreen edits, cache revisits, decal movement, oversized
marks, texture replacement (including recycled GPU IDs) and translucent art.

Unit checks cover overlap equivalence, culling edges, light masks, cache
invalidation, moving/height-changing occluders and unreachable facade rejection.
Run `test_render_performance` alongside `test_entity_light_optimization`,
`test_render_order`, `test_night`, `test_surfaces` and the editor/asset reload tests.
The final focused run passed 197 unit tests; native lake, courtyard and surface
smokes also passed.

## Remaining budget and C port

**Stable 60 FPS has not been reached.** The budget is 16.7 ms including presentation,
not just a good average. The moving flashlight still spends substantial CPU time
on visibility geometry, per-object light eligibility and facade transmission.
In the long run, lighting preparation together was roughly 13.5 ms while walking,
versus about 3.6 ms at the stationary approach view. The water draw stages were
about 1.5 ms combined; reducing water resolution is not the next useful tradeoff.

For the C port, retain the atlas, painter-order grouping, bounded chunks,
prewarming, spatial grid and shared pose atlas. Port moving-light visibility and
receiver selection first into packed arrays; these still do many Python loops,
dictionary lookups and allocations. Measure the resulting speedup rather than
assuming it will meet the target. A later renderer pass can extend atlas lighting
to response-mapped sprites/facades and reduce their remaining passes.

Before claiming the target, measure GPU time with timer queries and run sustained
gameplay on the chosen minimum-spec CPU/GPU, including room transitions, moving
flashlights, terrain streaming and more actors. This pass establishes cheaper
rendering and a repeatable benchmark; it does not certify the final frame budget.
