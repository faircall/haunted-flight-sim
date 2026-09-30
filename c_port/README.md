# C performance build

**Latest native C work: [arena design, native scene stages and validation](NATIVE_PROGRESS.md).**
`run_native_scene.cmd` runs the independent C renderer with C-generated tree
poses and complete light visibility polygons. The rest of its frame preparation
still comes from a reference trace; it is not yet a standalone playable C game.

This folder contains two distinct comparisons. The Python prototype and its
assets stay in their original locations and are not edited by the build.

**[Measured results, limitations and next steps](RESULTS.md)** describe what this
build actually achieves. The playable build is C-compiled but retains CPython;
the independent interpreter-free executable is a renderer benchmark.

## 1. Playable game compiled to C

Double-click **`play.cmd`** to start the water temple. Controls, simulation,
collision, animation, lighting, reflections, UI and sound use the existing game
logic. `play.cmd --courtyard` starts the courtyard; `--original-level` starts the
ordinary game. Hot reload, including F4, is disabled.

The game modules are compiled to C using Cython, then built as native modules
with GCC and loaded by `build/haunted_game.exe`, a small C launcher. Visibility
ray traversal and polygon coverage tests use handwritten C implementations.
Raylib calls that need no conversion bypass pyray's generic Python adapters.
The launcher refuses to silently fall back to original Python game modules.

**This retains CPython's containers and the installed third-party Python
runtime.** It is a complete playable C-compiled build, not a completed rewrite
into native structs with no Python dependency. It measures what compiling the
existing architecture buys us while preserving behavior. Further savings need
changes to data representation and the Python-to-raylib call boundary.

### Build

From the repository root, using the existing Python 3.12 installation:

```powershell
python -m pip install --target c_port/build-tools Cython==3.1.8
python c_port/build_game.py --jobs 2
```

The build uses `C:/raylib/w64devkit/bin/gcc.exe`, the installed Python headers
and import library, and the game's existing dependencies. It writes only under
`c_port/`. Generated C is in `build/generated/`; adapted input sources are in
`build/game_sources/`; native modules and source hashes are in `build/runtime/`.
Unchanged modules are reused on later builds. Rebuild after changing Python
logic. Shaders and art are loaded from the shared assets when the game starts.

The executable is tied to this checkout and Python installation; this is a local
performance build, not a distributable release. Cython is only needed to build.
The small source adaptation normalizes Python 3.12 f-string syntax for Cython,
adds native types to selected hot functions and replaces ray traversal with
a typed C call. Game modules keep
their original asset paths. Original source files are never overwritten.

## 2. Independent C renderer headroom benchmark

**`run.cmd`** opens `build/haunted_native.exe`. This has no Python interpreter.
It executes recorded raylib operations using the same source textures, meshes,
shaders, uniforms and render targets, and recomputes recorded visibility queries
in C. It renders trees, foliage, light masks, player silhouettes, reflections,
lapping water, fire, fog and compositing at the same native resolution.

It is a **rendering trace viewer**, not the playable game. It does not play a
movie or display finished reference screenshots. Python produces the render
work offline; the native program reruns that work on the GPU. It excludes most
scene preparation, AI, collision, pose evaluation, editor and audio costs.
Use it to estimate rendering headroom, never as a claim about full-game FPS.

Controls: Space pauses; right steps through the paused route; F1 toggles
the viewer's text. The game image keeps nearest-neighbor integer scaling.

```powershell
cmd /c c_port\build.cmd
python c_port/export_scene.py --frames 240
c_port/build/haunted_native.exe --benchmark --hidden --output c_port/output/native-240.csv --captures c_port/output
```

Raylib 5.0 comes from `C:/raylib/raylib/src/libraylib.a`, matching the Python
binding's renderer version. CMake can take another `RAYLIB_ROOT`. The exported
scene is local build data in `data/water/`, not an authored level format. Re-export
after changing game visuals. The executable needs only that file and system
graphics libraries once built. Exported frames contain assets and commands,
not the reference frame images; only RGB checksums are stored for validation.

## Verification and measurement

```powershell
python c_port/check_visibility.py
python c_port/check_geometry.py
c_port/build/haunted_game.exe --parity
c_port/build/haunted_game.exe --smoke water
c_port/build/haunted_game.exe --smoke night
c_port/build/haunted_game.exe --smoke surfaces
c_port/build/haunted_game.exe --tests c_port.verify_game
python c_port/benchmark_all.py --repeats 3 --frames 240
```

For the new arena-backed native stages, use:

```powershell
cmd /c c_port\build.cmd
ctest --test-dir c_port/build --output-on-failure
python c_port/check_native_scene.py
python c_port/export_scene.py --native-scene --frames 240
python c_port/export_scene.py --native-scene --scene courtyard --frames 120
python c_port/benchmark_native_scene.py
```

That benchmark checks three complete loops per scene in the same process,
pixel equality, native calculation results, arena growth and heap allocations.
It writes [native_scene_results.json](native_scene_results.json). Its timings
cover rendering plus the ported preparation stages, not the complete game.

The paired benchmark alternates Python/C run order, then measures the independent
C renderer. Avoid other benchmarks/builds competing for the CPU/GPU. There are
eight warmup frames followed by 240 measured frames for each
of approach, walking flashlight and interior views. Simulation uses 1/60 s steps;
rendering is uncapped. Pixel comparison checks every exported frame's RGB.

`submit_ms` measures update/submission; `complete_ms` also waits for GPU readback
and includes its transfer cost. Neither includes final window presentation.
The independent renderer also reports a GPU elapsed query. Its C ray checks are
included in the timing; reading files, initializing assets and hashing captured
pixels are outside warm-frame timings. JSON/CSV include p95/p99 and counts above
16.67 ms. Startup and first-frame allocation/shader costs must not be mistaken
for steady-state rendering cost.

`--tests c_port.verify_game` explicitly lists five exclusions: two source-inspection
checks, one builtin-print mock, and two tests that also fail in the original
Python checkout. See [verify_game.py](verify_game.py) and the measured report.

For separate, instrumented investigation, run
`c_port/build/haunted_game.exe --profile-native`. This wraps individual compiled
entry points and writes `output/instrumented.json`; its timings include profiling
overhead and are not used in the paired performance results.

Builds, local assets and captures are ignored by Git. The source, build scripts,
comparison tools and measured report remain reviewable here.
