# Temple assets and entry storm

Launch `python moonlit_water_temple.py`. Follow the boardwalk right, then turn
toward the open temple entrance. Crossing into the room starts the storm once.
It stays active after leaving and saves with mission progress. Restarting the
scene gives a fresh calm approach.

## Imported art

Prepared runtime PNGs live in `art/temple/`; `manifest.json` records the source
concepts, crop rectangles and dimensions. Originals in `artdev/concepts` are
unchanged. Regenerate the imports with `python prepare_temple_assets.py`.

- **Roof:** broad, front-facing grey-tile concept, fitted to the existing roof
  footprint and cutaway. Other camera angles remain available in the concepts.
- **Lanterns:** round red, pale oval and timber cage variants. Separate paper
  emission masks keep ribs/caps dark. Continuous rotation around the hanging point
  follows the trees' shared gust field, with a delayed response. Lighting,
  coverage and reflections use the same rotated sprite. Existing fire bowls remain.
- **Planks:** horizontal and vertical concepts, brought into a common timber
  palette. The long bridge and perpendicular run have separate grain directions,
  meeting at a straight construction joint. Samples are registered to the world,
  with stable strip offsets, rather than restarted at each cell.
- **Lilies:** two small cutouts in sparse groups, with gentle whole-pixel bobbing.
  They receive near-water-height lighting and mask reflections underneath them.

In the material painter, select **wood**, then **Grain AUTO / X / Y**. AUTO
inherits a consistent adjacent direction or uses the painted region's long axis;
a single isolated tile defaults to X. Use X/Y explicitly at turns. Existing
neighbours retain their authored directions. These fields change the finish;
tile collision and wood footstep sounds remain intact. Existing saved wood
keeps its old appearance until repainted with the new style.

## Weather and mission controls

The ordinary sequence trigger `temple:storm` invokes the reusable handler
`temple_storm`. It also sets the mission fact `temple_entered`. This provides a
place to add later encounter/dialogue/progression logic without coupling it to
the renderer.

Settings are in the scene's `weather_profile` in `moonlit_water_temple.py`:

| Field | Default | Effect |
| --- | ---: | --- |
| `onset_seconds` | 1.4 | Time to reach full storm conditions |
| `moon_intensity` | 0.13 | Storm moonlight, down from the calm 0.3 |
| `moon_color` | [0.14, 0.32, 0.83] | Normalized RGB storm tint |
| `rain_density` | 0.72 | Refractive rain and surface-impact density |
| `rain_refraction_density` | 0.75 | Fraction of rain drops that shift scenery on exposed tiles |
| `rain_reflection_distortion` | 3 | Maximum extra lake reflection displacement, in native pixels per axis |
| `wind_strength` | 36 | Mean wind, up from 8 |
| `gust_strength` | 26 | Gust amplitude, up from 5 |
| `tree_motion_gain` | 1.65 | Extra storm bending and foliage motion, with bounded deformation |
| `wetting_rate` | 0.026 | Wetness gained per second at full rain |
| `firefly_density` | 0.45 | Fraction of candidate lake cells with fireflies |
| `fireflies` | true | Enables the firefly pass |
| `seed` | 733 | Repeatable lightning timing |

The first flash follows entry by 2.8 seconds; subsequent intervals vary between
6 and 14 seconds. A short double pulse changes existing directional and ambient
lighting, with thunder delayed by roughly 0.7–1.9 seconds. Brightness and colour
changes reuse the moon's cached shadow field. The storm state freezes when the
game pauses; ordinary scene animation retains its existing pause behavior.

Rain exposure uses the original painted-tile compositor from the `rain v1`
implementation. The storm sets both streak opacities to zero and uses denser
one-pixel vertical refraction, without a diagonal scrolling drop colour.
The template rain settings in other scenes remain available. Rain and scenery
now use the same rounded camera origin.

The temple interior has zero exposure and an indoor acoustic zone. Exposed wood
darkens, then develops irregular shallow wet patches and light glints over about
40 seconds. Exposed wood, grass and dirt show brief contact pinpricks. On the lake,
two staggered fields of stationary dimples perturb reflected texels by at most three extra pixels
per axis. Sparse one/two-pixel contacts use the existing ripple colour. There
are no outlined splash rings, translucent blue overlays or interpolated
reflection colours. Impacts respect rain exposure, the shoreline and foreground
coverage; the existing shore-lapping animation remains separate.

The roof prop has `roof_runoff=True`. A cached one-row texture records the actual
painted eave silhouette. A localized shader draws accelerated drops from that
edge, with heavier flow near the tips and contacts below. Falling drops fade
with the roof cutaway; landing contacts remain on exposed ground. Runoff catches
nearby lamps and lightning. It does not allocate CPU particles.

Runoff now uses a receiving height: `surface_elevation` on tiles and
`runoff_elevation` on the roof, both in native pixels. The temple deck is 16
pixels above the lake's zero plane. Drops beyond the timber continue down to
the lake; deck contacts stay higher. The contact phase starts only after the
fall reaches that surface, and contacts cannot straddle a height or shelter
boundary. These are rendering heights; movement collision is unchanged.

The scene's wind profile uses a shared `gust_seed=733` for trees and lanterns,
including before the storm. Trees retain their own local flutter. Storm gain
increases part rotation, bending and grid deformation while keeping branch roots
pinned and the silhouette within its padded render texture.

Wet wood currently uses sky/nearby-light glints, not full object reflections.
Rain/thunder audio uses small procedural placeholder WAVs generated offline by
the import script; these can be replaced with recordings. The existing audio
system blends outdoor, roof and muffled rain. Fireflies dim and become sparser
as rain develops; they are shader pixels with no per-insect CPU simulation or
point lights.

## Verification and performance

`python -m unittest test_temple_storm test_water_temple test_surfaces test_sequences test_night test_rain test_audio -q`

`python temple_storm_smoke.py`

`python temple_storm_smoke.py --motion` also records a three-second storm preview
at `artifacts/temple-storm/storm-motion.gif`.

The GPU smoke captures calm, entry, rain, lightning, wet decking, shelter and
return to the courtyard under `artifacts/temple-storm/`. It checks the actual
shaders, entry state, roof cutaway, stable moon/terrain caches and resource cleanup.
`rain_surface_smoke.py` also checks actual GPU pixels for colour preservation,
stronger reflection displacement, exposed grass/dirt contacts, roof runoff and
cutaway, different lake/deck landing heights, shelter and subpixel camera alignment.
Its isolated motion preview is `artifacts/temple-storm/rain-dimples.gif`.

Compare the same scene with and without the storm:

```powershell
python benchmark_water.py --calm --label temple-calm --frames 90 --profile-frames 0
python benchmark_water.py --storm --label temple-storm-runoff --frames 90 --profile-frames 0
```

Local storm measurements with runoff and continuous lantern rotation, before
the receiving-height and water-lighting refinements, 90 warm timed frames
per view (milliseconds):

| View | Submission median | Completion/readback median |
| --- | ---: | ---: |
| Approach | 28.90 | 34.82 |
| Walking | 40.71 | 48.81 |
| Interior | 32.65 | 40.19 |

These are local timings including readback overhead, not isolated GPU timings
or a claimed speedup over the prior run. All measured frames exceed the 16.7 ms
60 FPS budget in this Python build. Weather update takes roughly 0.10 ms; the
ground/firefly submissions take roughly 0.06 ms combined, and roof runoff takes
roughly 0.07 ms, excluding deferred GPU execution. Fireflies
use one draw pass when calm. Full rain adds the ground-contact/wet-wood pass, one
small runoff quad per roof, and the original rain compositor. Lake dimples run inside the existing water/reflection passes,
removing the previous full-screen splash pass. Surface masks are cached; effects
require no per-frame texture uploads, CPU particle arrays or GPU-to-CPU readbacks.
The original rain compositor still uses its normal GPU scene copy. The native C
comparison remains separate.
