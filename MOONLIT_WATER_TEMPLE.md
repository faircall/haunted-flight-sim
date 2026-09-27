# Moonlit water temple

Run the new, independent scene:

```powershell
python moonlit_water_temple.py
```

The existing courtyard still launches with `python night_trial.py`. Its layout and authored lighting are unchanged.

## In the prototype

- A large dark lake with a rounded, crisp shoreline, animated ripples, broken blue moon glints and low mist.
- A raised timber boardwalk, railings and pilings leading to an open temple doorway. The route retains normal movement collision and wooden footstep sounds. Deep water blocks movement without acting as a wall for light rays.
- Six visible fire bowls, with procedural flames, embers, independently flickering light, and warm reflected streaks. The temple's window spill follows its indoor fire lamps. There are no authored electric point lamps in this scene.
- Lit sprite reflections of the temple, roof, supports, vegetation and player, projected from their ground anchors and distorted on the GPU. Dry surfaces and foreground objects mask them correctly.
- A temporary tiled roof and shrine. The roof fades away indoors; the localized player reveal also works here.

The reference guided the dark water, raised approach and cool architecture. Warm firelight gives this version an orange/blue contrast. The camera has a scene-specific look-ahead toward the temple.

## Tuning / limitations

Layout, lamp placement and lake defaults live in `moonlit_water_temple.py`. `lake_profile` controls reflection strength, ripple strength, moon glint position/colour and camera offset. `g_water_temple_art.py` provides replaceable procedural architecture. Water is authored as tile metadata; a dedicated lake painting tool is not included yet. The scene data is compatible with the usual level saves.

These are 2D sprite reflections of visible rendered content, not a 3D mirror. Offscreen surfaces cannot contribute, and overlapping sprites retain the main view's occlusion. Flame reflections use flickering, rippled light streaks rather than a second full flame simulation. The shallow shoreline stencil can differ from its tile collision edge by a few pixels.

## RetroDiffusion asset prompts

Use the **painterly pixel art** style, hard native pixel edges, our existing slightly elevated orthographic view, neutral material lighting, and transparent backgrounds for isolated objects. Avoid baked moonlight, glow, shadows on the ground, water reflections, text and antialiasing: the renderer supplies those.

### 1. Temple roof — highest priority

> Isolated weathered Chinese lakeside temple roof, front-facing with a slightly elevated orthographic game view, broad dark blue-grey ceramic roof tiles, graceful upturned eaves, carved ridge ornaments, aged timber brackets beneath the eaves, restrained moss and chipped tile details. Painterly low-resolution pixel art, carefully grouped pixel clusters, readable silhouette, subdued natural material colours, neutral diffuse lighting. Entire roof visible, centered on a transparent 256 by 128 canvas, roughly 216 pixels wide, no walls, no sky, no ground, no cast shadow, no glow, no text.

Provide the whole roof as one layer first. We can split eaves/ridge later if needed.

### 2. Entrance guardians

> A single ancient Chinese stone guardian lion for a haunted temple entrance, three-quarter front view from a slightly elevated orthographic game camera, squat seated pose on a square carved plinth, eroded expressive face, curling mane, cracked grey stone with restrained moss in crevices. Painterly pixel art, dense but readable sculptural texture, hard pixel clusters, neutral material lighting. Entire statue and base visible on a transparent 64 by 80 canvas. No scenery, no ground shadow, no moonlight, no glow, no text.

A second facing variant would help flank the entrance. Include the plinth so its bottom centre can serve as the ground pivot.

### 3. Bronze fire bowl / lamp stand

> Isolated old Chinese bronze temple brazier on a short narrow pedestal, front-facing slightly elevated orthographic view, shallow open bowl with a clearly visible rim, aged dark bronze with small verdigris accents and rubbed warm metal highlights, sturdy foot. Painterly low-resolution pixel art, hard pixel edges, readable at native size, neutral lighting. Transparent 32 by 48 canvas, entire object visible. Empty bowl, no flame, no smoke, no sparks, no glow, no cast shadow, no text.

The empty bowl is intentional: the live fire shader supplies the flame at its centre.

### 4. Carved lattice wall / open entrance

> A modular front-facing wall bay of an old Chinese water temple, slightly elevated orthographic game view, dark aged red-brown timber frame, intricate but readable wooden lattice, chipped lacquer, carved beam ends, painterly pixel clusters and restrained wear. Transparent 64 by 64 canvas. The spaces between lattice bars are completely transparent; no paper, no glass, no background room, no painted light. Neutral material lighting, hard native pixel edges, no shadow, no glow, no text.

For the doorway variant, replace the lattice with a fully open central doorway and retain only the timber frame. Keep the bottom edge and beam height consistent between bays.

### 5. Optional shore details

> A small isolated clump of sparse lake reeds and sedges, old Chinese lakeshore, slightly elevated orthographic game view, asymmetrical curved stems and a few dry seed heads, subdued olive and straw colours, painterly pixel art with clear separated leaf clusters and hard edges. Transparent 48 by 48 canvas, whole plant visible, neutral lighting. No water, no ground patch, no reflection, no shadow, no glow, no text.

We can split the reeds for wind response; the lake itself benefits more from code than a painted water tile.

## Checks and previews

`python -m unittest test_water_temple -q`

`python .tree_game_smoke.py --water`

The native check captures the approach, temple interior and extinguished lamps under `artifacts/moonlit-water-temple/`, and checks reflection alignment, dry masks, lighting links, roof transitions and cleanup when returning to the original courtyard.

## Performance pass

The original bottleneck was CPU object lighting: repeating visibility tests and dozens of shader uniform updates for each object/light pair. The water, reflection distortion, fire and tree deformation already run on the GPU.

The renderer now caches geometric light samples independently of fire intensity, batches new visibility samples with native array operations, reuses facade irradiance textures through flicker, avoids empty masking draws, and combines mask/light draws for ordinary sprites. Layered character rigs keep their original accumulation. Static prop metadata and native sprite draw geometry are reused too. Light movement, wall edits and field replacement invalidate the relevant caches.

Measured on this workspace's machine, using 24 warm timed frames per view, uncapped and without the CPU profiler:

| View | Before | After | Speedup |
| --- | ---: | ---: | ---: |
| Approach | 231 ms | 61 ms | 3.8x |
| Walking | 250 ms | 64 ms | 3.9x |
| Interior | 240 ms | 51 ms | 4.7x |

These timings include waiting for GPU completion through a readback, which adds transfer overhead; they exclude window presentation. They are not a claim of 60 FPS. All three fixed-time comparison captures match the original pixels exactly, with fires, reflections and detail retained. Remaining costs are distributed across object lighting submissions, moving-light visibility, tile rendering and other scene passes. Further gains call for broader batching of the renderer.

Reproduce timings and a separate CPU profile with:

```powershell
python .tree_game_smoke.py --water-benchmark --label current
```

Results and comparison captures are written under `artifacts/moonlit-water-temple/`. Unit coverage for cache invalidation, moving lights, batched polygon edges and overlap masks lives in `test_entity_light_optimization.py`.
