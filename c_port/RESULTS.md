# C build: results and scope

This report preserves the initial Cython and renderer measurements. Subsequent
handwritten C work is documented in **[NATIVE_PROGRESS.md](NATIVE_PROGRESS.md)**
with a separate benchmark. Do not mix the two sets of timings: the newer build
includes additional native preparation and explicit release optimization flags.

## What is ready

Open **[play.cmd](play.cmd)** for the playable water temple. Add `--courtyard`
or `--original-level` for the other entry points. Python game sources and art
remain unchanged; hot reload is disabled in this build.

The playable build compiles the game through Cython into C, adds handwritten C
visibility and polygon kernels, and uses a native executable to launch it.
There are 48 compiled modules, including the two native bridge modules.
Selected hot functions use native numeric/container types; raylib calls that
need no conversion bypass the generic Python adapters.

**It still requires CPython and the existing third-party packages. A complete
interpreter-free game rewrite is not finished.** Dictionaries, object allocation,
and much of the rendering interface retain the original runtime architecture.
Compiling that architecture helps, but does not achieve the requested large
speedup or stable 60 FPS yet.

There is also an independent, interpreter-free **[C renderer](run.cmd)**. It
re-executes exported rendering commands and visibility queries using real source
textures, meshes and shaders. It is a trace viewer, not an interactive game.
Most scene preparation, animation evaluation, gameplay, editor and audio costs
are excluded. Its timing shows rendering headroom, not completed-port FPS.

## Measured performance

Measured on 28 September 2026: AMD Ryzen 5 3600, NVIDIA RTX 3060 Ti, Windows,
raylib 5.0, OpenGL 3.3 / NVIDIA 610.47. Internal resolution is 480 x 270.

The complete-game comparison uses three paired runs with alternating order:
Python/C, C/Python, Python/C. Each run has eight warmup frames and 240 measured
frames per view, with a fixed 1/60 s simulation step and uncapped rendering.
There are **720 measured frames per view per implementation**. No build or other
test was run concurrently with these benchmarks.

### Playable game

Median frame completion time, including the GPU readback used by the benchmark:

| View | Original Python | C-compiled game | Frame-time reduction |
| --- | ---: | ---: | ---: |
| Approach | 27.58 ms | 21.73 ms | 21.2% |
| Walking / moving flashlight | 40.28 ms | 28.79 ms | 28.5% |
| Interior | 30.06 ms | 24.91 ms | 17.1% |

The improvement also holds at the 95th percentile:

| View | Python p95 | C-compiled p95 |
| --- | ---: | ---: |
| Approach | 35.83 ms | 25.36 ms |
| Walking / moving flashlight | 45.83 ms | 31.74 ms |
| Interior | 34.66 ms | 27.11 ms |

All measured complete-game frames still exceed the **16.67 ms** budget for 60 FPS.
Even without the final GPU readback, C-game median submission times are
17.89 / 22.74 / 19.81 ms. This is an improvement, not a stable-60 result.

### Independent C renderer

This separate run uses 240 measured frames per view and the same visual work.
It executes the rendering API calls and native rays, with other CPU preparation
performed offline by Python.

| View | CPU submission median | Completion + readback median | Completion p95 | GPU elapsed median |
| --- | ---: | ---: | ---: | ---: |
| Approach | 2.05 ms | 8.57 ms | 9.87 ms | 4.98 ms |
| Walking | 2.11 ms | 8.49 ms | 9.06 ms | 4.86 ms |
| Interior | 2.03 ms | 8.59 ms | 8.91 ms | 5.18 ms |

None of its 720 measured frames exceeds 16.67 ms; the worst is 13.28 ms.
That demonstrates useful renderer headroom at the existing visual quality.
**It does not establish the performance of a future fully native game.** Live
preparation must be added back, and its cost depends on the native data layout.

Submission timings stop after flushing raylib's batches. Completion timings
also synchronize through texture readback and include its transfer cost. GPU
elapsed time comes from an OpenGL timer query, rather than a CPU stopwatch.
All figures exclude final window presentation. Initialization, asset loading,
first-frame costs and pixel hashing are excluded from steady-state timings.
Earlier exploratory runs varied noticeably in absolute time; the tables above
use only the final paired batch. They should not be compared directly with older
reports produced under different conditions.

## Accuracy and checks

- **744 / 744 RGB frames exactly match Python** in the playable build, covering
  the approach, moving flashlight and interior routes at native resolution.
- **744 / 744 frames also match** in the independent C renderer.
- Native renderer recomputed **82,582 visibility rays**, with zero mismatches.
- Independent native-ray checks passed **16,000** seeded and boundary cases.
- Native polygon tests matched **44,210 points and 8,000 rectangles**, including
  degenerate edges, vertex hits and both reference polygon algorithms.
- Focused behavior suite: **447 passed, five explicitly skipped**.
- Final GPU smoke checks passed for the water temple, courtyard and material
  scene: reflections, firelight bands, shores, camera alignment, window/door
  transmission, roof/reveal fades, tree/player shadows, grass, footprints,
  editor controls and resource cleanup.

Pixel parity is measured on these routes and this graphics stack; it is not an
exhaustive comparison of every possible authored scene or GPU driver.

The five exclusions are visible in [verify_game.py](verify_game.py): two tests
inspect Python function source, one mocks a builtin `print` cached by Cython,
and two also fail in the original Python checkout. Those last two use an old
draw-call mock and a reference image that predates the cleaned tree artwork.
They are documented skips, not counted as passes.

## Where the remaining headroom is

The expensive work still crosses Python object boundaries many times per frame.
The moving-flashlight case is particularly sensitive to entity-light eligibility,
cached sample keys and per-light records. In the final third run, that preparation
stage alone takes a median **5.17 ms** in the C-compiled build.

A full native port should proceed through these concrete boundaries:

1. **Pack render items, lights and footprints into C arrays.** Convert authored
   data at load/edit boundaries instead of rebuilding nested dictionaries and
   tuples for each light/object pair every frame. Use explicit generation numbers
   for cache invalidation.
2. **Move live lighting preparation behind one C call.** Reuse the existing
   native ray and polygon kernels, and produce eligibility, response weights,
   wall receivers and shadow geometry in native buffers.
3. **Generate and submit rendering work directly in C.** Keep the same shaders,
   render targets, pixel snapping and order. Replace the trace's offline producer
   with live native preparation, including tree/character poses and batching.
4. **Export authored scene/resource data and port the remaining simulation.**
   Collision, AI, interactions, sequences and audio state then need native
   ownership to remove the interpreter entirely. The trace format is a test
   fixture, not an authored level format.

The reference exporter and pixel checks provide a usable comparison boundary for
each step. Keeping Python for authoring and experimentation remains compatible
with that route; a production C build would consume exported scene data/assets.

## Reproduce and inspect

Build and launch instructions are in [README.md](README.md). With both binaries
and the exported reference ready:

```powershell
python c_port/benchmark_all.py --repeats 3 --frames 240
```

The script alternates full-game run order, measures the renderer separately and
writes `output/comparison.json`. The included [benchmark_results.json](benchmark_results.json)
preserves the reported distributions, frame counts, source paths and provenance.
Raw per-frame JSON, CSV and logs remain in the local ignored output/artifact
directories. Builds and the roughly 173 MiB exported trace are ignored too.

Reference source revision: `d266eca608903ab102cc0f063d0b65bf379e256d`.
Reference trace SHA-256:
`e3967838cdc3ff43460d1ae48058c531ea8c7cedd14531ca4f591c1f8b494112`.
Toolchain: Python 3.12, Cython 3.1.8, GCC 13.2; native C compilation disables
floating-point contraction and does not use fast-math.
