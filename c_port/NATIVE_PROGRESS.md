# Native C: arenas and scene preparation

## Status

This pass extends the **handwritten, Python-free C executable**. Full light
visibility construction and tree wind/pose evaluation now run in C and feed
the actual GPU rendering passes. They are no longer supplied as finished
results by Python. Expected Python results remain in the fixture only for
validation.

**The complete playable native game is still unfinished.** Other render-item
preparation, character poses, gameplay, editor and audio are still produced
offline for this executable. `play.cmd` remains the earlier playable Cython
comparison, with its CPython dependency. The original Python game source is
unchanged by this work.

Launch **[run_native_scene.cmd](run_native_scene.cmd)** to inspect the native
stages. Space pauses, Right advances one frame, and F1 toggles the viewer text.
This is still a recorded route, not player-controlled gameplay.

## Memory ownership

The executable makes one OS allocation at startup, split into three arenas:

| Arena | Lifetime and contents |
| --- | --- |
| Persistent | Runtime state, cached light polygons, frame index and reusable GPU readback buffer. |
| Assets | Immutable source data, packed wall geometry and spatial buckets, mesh attributes and font tables. |
| Frame | Temporary ray candidates, sorting scratch and triangle-fan vertices. Reset every frame; nested work uses marks and rewinds. |

The current harness reserves 128 / 384 / 16 MiB respectively. These are explicit
capacity limits, not allocation targets. Windows commits the reservation;
physical pages are backed as touched. The largest used allocation is the
**recorded command fixture**, which would not exist in a live native game.
These sizes are therefore not a prediction of the eventual game's memory use.

- Arrays are contiguous typed C records, connected by integer resource IDs.
  Nearby wall corners are queried through flat bucket ranges and index arrays,
  without per-frame dictionaries, linked lists or allocation-heavy sorting.
- Checked allocation handles alignment, multiplication overflow and exhaustion.
  Exhaustion fails explicitly; it never silently grows an arena or falls back
  to the heap. Reset generations reject stale temporary marks.
- Textures, render targets, shaders, fonts, meshes and cached polygon capacities
  are prepared before playback. No GPU resource creation is deferred to a frame.
- CPU mesh/font storage belongs to the arena. Raylib-owned GPU handles and
  metadata are released separately, preventing `UnloadMesh` from freeing
  borrowed arena memory.
- GPU validation reads pixels into a reusable buffer. Capture image flipping
  uses frame scratch instead of raylib's allocating/replacing image operation.
- Rewinding restores modified textures into their existing GPU allocations.
  The same arenas and GPU resources survive repeated route playback.

The renderer checks that persistent and asset cursors do not grow during frames.
GNU linker wrappers count `malloc`, `calloc`, `realloc` and `free` calls in the
executable and statically linked raylib. Rendering/readback and presentation are
audited separately. File logging, PNG exports, initialization, and allocations
inside external OS/GPU DLLs are outside that audit.

## Work now performed in C

### Visibility and shadows

`native_scene.c` builds the complete visibility polygon from the packed wall
grid: baseline rays, nearby corner candidates, angular separation, extra rays
around corners, deterministic sorting, DDA traversal, bias and unbiased points.
Native points generate the actual light-mask triangle fans used by the renderer.
Light results have preallocated cache storage; temporary construction never
changes persistent memory ownership.

### Tree animation

Native code evaluates regular/irregular wind, smooth noise, delayed branch
response, sway, bend and all 16 GPU deformation parameters. The resulting
uniforms drive the existing vertex shaders, including lighting-response passes.
The GPU still performs the mesh deformation. Source art and shaders are shared
with the Python reference.

Floating-point contraction is disabled and fast-math is not used. Doubles are
retained for reference calculations; conversion to float occurs at the same
shader boundary. Seed arithmetic avoids signed integer overflow.

## Validation and measurements

Reproduce with the commands in [README.md](README.md). The separate
[native_scene_results.json](native_scene_results.json) preserves per-view
distributions, fixture/source/executable hashes, memory counts and validation.
Raw frame CSVs and logs are in the ignored `output/` directory.

- Reference kernel checks: **300 complete visibility polygons** across random
  and boundary cases, plus **2,500 tree poses**. All deformation float bytes
  agree with Python; polygon coordinates agree within 1e-8 pixels.
- Arena checks exercise alignment, overflow, exhaustion, mark/reset lifetimes
  and **100,000 resets**. The allocation-audit test first detects deliberate
  heap traffic, then verifies 10,000 arena-backed frames allocate no heap.
- Full GPU comparisons cover the water temple and courtyard, each looped three
  times in one process: **3,384 / 3,384 frames match exactly**, with zero native
  calculation errors, zero frame/presentation heap allocations, zero capacity
  failures and no persistent/asset growth. This tests retained resource state
  as well as pixels.

On the local Ryzen 5 3600 / RTX 3060 Ti, at 480 x 270 internal resolution:

| Scene/view | Submission median | Completion + readback median | Completion p95 |
| --- | ---: | ---: | ---: |
| Water / approach | 1.82 ms | 8.38 ms | 8.80 ms |
| Water / walking | 1.86 ms | 8.37 ms | 9.47 ms |
| Water / interior | 1.82 ms | 8.43 ms | 8.85 ms |
| Courtyard / approach | 0.58 ms | 2.93 ms | 3.31 ms |
| Courtyard / walking | 0.63 ms | 3.02 ms | 3.41 ms |
| Courtyard / interior | 0.62 ms | 3.12 ms | 3.48 ms |

Water uses 3,406,176 persistent bytes and 29,344 bytes of peak frame scratch.
Courtyard uses 3,256,608 persistent bytes and 30,928 bytes of peak frame scratch.
The asset arenas use 161,769,168 and 32,789,384 bytes respectively, overwhelmingly
the resident command fixtures. GPU/driver memory and C static storage are not
included in these arena counters.

These are partial-pipeline performance measurements. They include native
visibility/tree preparation, rendering and GPU readback, but exclude the
remaining offline preparation and live simulation. Eight warmup frames per
view per loop are excluded from timing statistics; they are still checked for
pixel equality and allocations. Window presentation is outside the timing.

The newer CMake build explicitly adds `-O2 -DNDEBUG`: the prior local Release
configuration had empty release flags. Timing changes must not be attributed
solely to arenas or data layout. The historical complete-game Cython results in
[RESULTS.md](RESULTS.md) remain separate.

## Remaining path to a playable native game

1. Port entity/light eligibility, response sampling and shadow preparation into
   arena-owned arrays, replacing the remaining expensive Python preparation.
2. Build sorted render items and all rendering passes directly from native
   scene state, using the same shaders, pixel snapping and blending order.
3. Replace the command fixture with an authored level/resource export; move
   player movement, collision, character poses, interactions and other
   simulation state into the native runtime.
4. Bring over the needed gameplay/audio features and benchmark the complete
   playable build against Python using identical input routes.

The new arena and native scene modules are reusable for that runtime; the
trace reader and expected-result comparisons remain a validation harness.
Pixel parity in these scenes does not yet establish parity for every authored
level or the performance of a full native game.

## Main implementation files

- [src/arena.h](src/arena.h), [src/arena.c](src/arena.c): memory lifetimes and checked allocation.
- [src/native_scene.h](src/native_scene.h), [src/native_scene.c](src/native_scene.c): packed scene data and CPU kernels.
- [src/scene_commands.h](src/scene_commands.h): native results connected to rendering and reference checks.
- [src/main.c](src/main.c): resource preloading, render loop, readback and lifecycle.
- [src/allocation_audit.c](src/allocation_audit.c): executable/raylib heap instrumentation.
- [record_native_scene.py](record_native_scene.py): offline reference export; not part of the C runtime.
- [benchmark_native_scene.py](benchmark_native_scene.py): repeatable validation and timing.
