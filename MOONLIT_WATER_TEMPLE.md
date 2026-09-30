# Moonlit water temple

Run the new, independent scene:

```powershell
python moonlit_water_temple.py
```

The existing courtyard still launches with `python night_trial.py`. Its layout and authored lighting are unchanged.

## In the prototype

- A large dark lake with a rounded, crisp shoreline, a two-colour surface, sparse moonlit glimmers, lapping shore water and low mist.
- A raised timber boardwalk, railings and pilings leading to an open temple doorway. The route retains normal movement collision and wooden footstep sounds. Deep water blocks movement without acting as a wall for light rays.
- Six visible fire bowls, with procedural flames, embers, independently evolving firelight bands, and literal reflections of the flame pixels. The temple's window spill follows its indoor fire lamps. There are no authored electric point lamps in this scene.
- Lit sprite reflections of the temple, roof, supports, vegetation and player, projected from their ground anchors and distorted on the GPU. Dry surfaces and foreground objects mask them correctly.
- An imported RetroDiffusion roof, directional painted planks, three lantern styles and small lily clusters. The roof fades away indoors; the localized player reveal also works here. The shrine and rails retain their procedural art.
- GPU fireflies over the calm lake. Entering the temple triggers darker blue moonlight, outdoor rain, wet decking, lightning with delayed thunder, and stronger wind. See [Temple storm and imported assets](TEMPLE_STORM.md) for tuning and checks.

The reference guided the dark water, raised approach and cool architecture. Warm firelight gives this version an orange/blue contrast. Moonlight intensity defaults to `0.3` in this scene. The camera has a scene-specific look-ahead toward the temple.

## Tuning / limitations

### Irregular firelight bands

All fire emitters now use the GPU contour pattern, including fires in existing saved scenes. The brightness envelope stays steady while three scales of cached lattice noise evolve at different phases, changing the internal band boundaries locally. The dim outer footprint retains its static irregular shape. Coordinates stay fixed to native world pixels, and the existing final posterization keeps crisp lighting steps.

In the **Environment editor**, select a fire emitter and scroll to **linked light**. The former whole-light pulsing controls have been replaced with:

- **Band speed**: how quickly the internal bands evolve; default `4.0`. Zero freezes the pattern. Existing explicitly saved speeds are preserved.
- **Band motion**: how far the internal bands move; default `0.65`, range `0–1`. Zero also freezes the pattern.
- **Irregularity**: how broken-up the contours are; default `0.48`, range `0–0.85`. Zero gives smooth, steady lighting.
- **Band scale**: feature size in world pixels; default `28`. Larger values give broader shapes.

**Light radius** and **brightness** still set the overall reach and intensity; **flame speed** separately controls the flame sprite. Changes preview live and save with each emitter. Older scenes gain the new defaults without replacing their colours, radii, intensities or flame settings. Previously authored contour settings are preserved.

Authored values live in `light['contours']` as `speed`, `motion`, `strength` and `scale`, respectively. Each noise scale uses a different phase/rate, with a small contribution from flame activity. The old `light.flicker_*` and `flame_light_coupling` keys are retained internally solely to preserve existing flame animation; they no longer pulse the light.

Ground, sprite light fields, facade receivers and linked window spill use the same pattern and seed. Both rendered intensity and CPU gameplay light sampling use the steady authored intensity; explicit scripted fades still work. Shadow masks and cached visibility geometry remain intact; contour animation and edits to its four controls do not rebuild CPU irradiance textures. Reflections naturally inherit the resulting lit source colours.

The old pulsing mode and its Ctrl + backtick comparison shortcut have been retired. Plain backtick still toggles effect statistics; Shift + backtick switches the raw effect view. F12 capture shortcuts stay available.

Measure frame times with `python .tree_game_smoke.py --water-benchmark --profile-frames 0 --label contours`. Timings include GPU readback and its transfer overhead.

The water smoke also checks that the visible footprint and dim edge stay fixed across time while internal bands move in both directions, plus subpixel camera pans, receiver/radial agreement, sealed wall shadows, shader reload, editor numeric commits, and live contour edits reaching cached window spill. Isolated band comparisons, an editor capture and a real-time `bands-evolving.gif` are saved under `artifacts/firelight-review/`.

### Scene assets and limitations

Layout, lamp placement and lake defaults live in `moonlit_water_temple.py`. `lake_profile` controls the two surface colours, ripple placement, independent reflection treatment and camera offset. `g_water_temple_art.py` loads prepared PNG assets with procedural architecture as its fallback. Water is authored as tile metadata; a dedicated lake painting tool is not included yet. The scene data is compatible with the usual level saves.

These are 2D sprite reflections of visible rendered content, not a 3D mirror. Offscreen surfaces cannot contribute, and overlapping sprites retain the main view's occlusion. Flame reflections copy the rendered flame colours through a mask evaluated with the same flame shader, time, wind and occlusion. The shallow shoreline stencil can differ from its tile collision edge by a few pixels.

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

## Two-colour surface, independent reflections

The base surface has exactly two colours: `#02070d` water and `#0a1621` glimmers. Open-water ripples are sparse, straight, one-native-pixel strokes, up to 6–16 pixels long. Each grows briefly and shrinks away over roughly three seconds, with independently staggered quiet intervals and positions. Most of the water stays unbroken. Three sparse groups share a direction, toward the foreground by default, but travel at different positive speeds. Reflection distortion follows the mean current. Appearance/disappearance changes pixel coverage rather than blending colours: there are no gradient fringes, dither, fine colour noise, or 2x2 enlargement. Camera motion preserves the world-pixel alignment. Shore lapping has its own unchanged animation.

Shore waves form offshore, broaden into broken patches on arrival and dissolve at the bank. The actual water boundary washes a few pixels over the bank and retreats as the wave breaks up; a bright line does not slide back out into the lake. Nearby stretches have slightly different timing. Water keeps the same two colours and reveals the existing bank as it drains.

A signed distance field covers both sides of the resting shoreline. It is built only when the map changes and packed into the existing water-mask texture; the GPU animates the crisp shoreline threshold and wave patches. Base water and reflections obey the same moving edge. Raised decks and walls remain protected, and the lake bed beneath them does not create a false shore. Gameplay collision stays fixed.

The resting bank uses the same world-fixed fractal boundary displacement as the material painter's **Rounded joins**. Broad curves, smaller bays and fine scallops break up long horizontal/vertical runs. This is a cached shape change, with one crisp owner per pixel; it does not blend the water into the ground. Hard architectural edges stay straight. The shared implementation lives in `g_surfaces.boundary_samples` and `warp_boundary_field`.

The former shared 20-colour palette has been removed. Sprite and flame reflections composite separately; surface colours, density and spacing do not change reflected sprite colours. Fog and fire bloom remain later scene effects, so the complete scene naturally contains more than the two base colours.

Flashlights and lamps now illuminate the water through the existing shadowed
world-light texture. The two base colours gain three crisp brightness bands,
with a subdued response on flat water and brighter glimmers. Light hue is also
quantized; no filtered gradient is added. Reflected sprite pixels retain their
exact colours. Cached moon visibility occupies the water mask's unused alpha
channel so the authored moon ambience is not counted twice. This adds no render
pass, particle system or per-frame texture upload. `water-flashlight.png` under
`artifacts/moonlit-water-temple/` shows unlit, flashlight-lit and reflected cases.

Tuning fields in `lake_profile`:

- `surface_color` and `ripple_color`: normalized RGB triples for the two colours.
- `light_response`: direct light sensitivity, default `1`; `0` restores the entirely unlit two-colour surface.
- `ripple_spacing`: spacing between potential glimmer rows, `20` world pixels by default; individual strokes have varied positions within each row.
- `ripple_density`: fraction of potential glimmers that participate, `0.28` by default; their brief lifetimes further reduce visible coverage. Zero hides open-water glimmers.
- `ripple_width`: stroke thickness in native pixels, `1` by default (range `1–8`).
- `ripple_speed`: mean current rate, `0.65` by default; each unit is five world pixels per second. Zero freezes surface and reflection ripple motion.
- `ripple_speed_variation`: speed difference between the three wave trains, `0.28` by default (range `0–0.65`). The default gives rates of 72%, 100% and 128% of the mean; zero makes them travel together. All rates stay forward.
- `ripple_direction`: `{x, y}` travel direction, normalized by the renderer; default `{x: 0, y: 1}` moves toward the foreground. This controls travel, not the camera.
- `shore_width`: how far lapping reaches into the lake, `12` world pixels by default (range `0–28`); zero disables lapping.
- `shore_speed`: lapping rate, `0.65` by default; zero freezes it. Independent of reflection distortion.
- `shore_lap`: maximum distance the water can wash onto the bank, `3` native pixels by default (range `0–8`). Zero keeps the silhouette fixed while shore wave patches can still form and dissolve.
- `reflections_enabled`: set false to review the base surface independently.
- `fire_reflections_enabled`: controls literal flame reflections separately.
- `reflection_strength`: coverage, from 0 (hidden) to 1 (unbroken). Ripples remove pixels in coherent bands instead of multiplying their brightness.
- `reflection_stretch`, `ripple_strength`: vertical scale and whole-pixel distortion amount. These do not affect surface ripple styling.
- `reflection_sway`: additional horizontal displacement multiplier, now `2` (range `0–4`); zero disables sideways displacement. At the temple's `ripple_strength=1.25`, the former multiplier of 1 gave at most about two native pixels sideways; 2 gives up to about four. Vertical distortion and exact source-colour sampling are unaffected.
- Per-fire `reflection_base_offset`: water-plane pivot below the flame anchor, default 14 pixels for the prototype's braziers.

GPU checks verify sparse single-pixel strokes, glimmer formation/dissipation, exactly two base colours, shared direction (including an authored diagonal), differing positive glimmer speeds, visible horizontal reflection displacement, forming/dissolving shore patches, a moving water/land boundary, reflection clipping at that boundary, cached shore data, deck protection, zero-speed motion, exact source-colour preservation in both sprite and flame reflections, native pixel detail, strength changing coverage instead of RGB, transparent foregrounds, lamp extinction and camera alignment. Review captures include `water-glimmers.gif`, `water-wavelets.png`, `shore-lapping-phases.png` and `shore-lapping.gif` under `artifacts/moonlit-water-temple/`.

### How reflections currently work

1. Render the sprites and visible flames, then capture their lit colours before bloom and mist.
2. Draw each sprite's geometry again into a reflection target. A vertex shader mirrors it around its ground anchor; stretch defaults to 1.0. Sample a single source texel using the original sprite alpha for shape. Flame masks come from the same procedural flame shader, including its embers and depth occlusion.
3. A fragment shader shifts samples in whole native pixels using explicit texel fetches, then cuts gaps along ripple bands. Surviving opaque pixels retain their source RGB exactly. There is no reflection distance fade, brightness ramp, additive colour boost, or synthetic fire-light streak. Intentional object fades and translucent foregrounds still use alpha blending.

An independent reflected strip/grid mesh remains an option for changing the deformation shape and overcoming main-view occlusion. Palette preservation does not require it: fragment shaders can move exact texels just as well, provided their sampling and compositing do not interpolate colours.

## Structural optimization pass

Implemented ground chunk batches, a shared GPU light atlas for ordinary scenery,
shared character shadow silhouettes, bounded terrain retention/prewarming, sprite
culling and a spatial broad phase for occlusion. Water/reflections remain at native
resolution with their existing colours and animation.

See [RENDER_PERFORMANCE.md](RENDER_PERFORMANCE.md) for measured frame times,
reproduction commands, cache limits, validation, and the remaining work toward
60 FPS. The current Python build still exceeds the 16.7 ms frame budget; the C
port is expected to help CPU work but has not been used to claim a speedup.
