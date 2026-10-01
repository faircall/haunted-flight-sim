# Photo-derived water temple

**Newer comparison:** the full [Blender temple kit](temple3d/README.md) includes
normal/position lighting and a separate live 3D viewer. Run
`python moonlit_water_temple_blender.py` to review it. This page documents the
previous photo study, which remains independently available.

## Play and compare

From the repository root:

```powershell
python moonlit_water_temple_photo.py
```

The roof now uses a photo-textured Blender model, baked from a 30-degree
orthographic view. Try `--roof-angle 40` or `--roof-angle 50` to compare higher
views, or `--roof-angle photo` for the original photographic cutout.
See the [in-game angle comparison](review/roof-in-scene-comparison.png) and
[editable Blender project and rebuild notes](blender/README.md).

The previous art remains in `python moonlit_water_temple.py`. Both use the same
scene builder, walkable route, collision, sounds, lighting, reflection shaders,
roof fade, weather trigger and tree animation. The photo launcher changes art
references and surface styles. It also sets the wood/wall brush to the photo
style for continued painting during that session. This is a **Python review
scene**; the native C comparison has not been ported to these new assets.

Open [the review gallery](index.html), [the scene comparison](review/scene-comparison.png)
or [the runtime sheet](review/runtime-contact-sheet.png). The gallery has native/2x
pixel and dark/light background controls. Native captures are 480 x 270; the
comparison image enlarges them with nearest-neighbour sampling. The bright
inspection image deliberately changes ambient light; the first two comparison
images use matching moonlight, camera and animation time.

## What changed

| Scene component | Photo treatment |
| --- | --- |
| Roof | Curved hipped-roof geometry with photographic tiles, fascia and timber; three orthographic views, 216 x 116 each. Original intact photographic cutout retained as an alternative |
| Boardwalk and floor | Scanned timber grain cut into board strips, thin authored joints, horizontal/vertical atlases; 128 x 32 and 32 x 128 |
| Rails and supports | Actual dark red timber fragments applied to the existing simple rail geometry; perspective-corrected worn red pillar photograph |
| Walls | Timber scan with photographic painted fascia and pillars; temple brickwork for the wall footprints |
| Lilies | Two individually isolated pads and a white flower, combined into small clusters; purple flower included as an alternative |
| Lanterns | Tang-clan paper lantern at 20 x 30; a Qing porcelain lantern at 18 x 32, standing on a post |

There are **20 runtime assets**, including component parts and alternatives.
Tree art, grass, water, flames, the small procedural altar/statue, banners and
fire bowls remain the existing prototype assets. This batch targets the five
requested categories; it does not attempt the pasted brief's separate statue
collection. No existing PNGs in `art/` were overwritten.

### Art judgment / next refinements

- **Roof:** the original near-frontal, upward-looking photograph did not fit the
  scene's viewpoint. The new roof uses authored geometry and photo texture
  crops, so its camera angle can be changed before baking. The 30-degree view
  is the current starting fit; proportions and materials remain open to review.
  This simpler model does not reconstruct the source building's ornate finial.
- **Columns:** the perspective-corrected photographic pillars retain their
  irregular surface wear and shading.
- **Wood:** real material variation replaces the invented grain. Board layout
  remains code-defined so direction and joins stay consistent. The scan is
  fairly clean timber; rougher old deck photographs would be a useful next
  source pass. Current strips preserve photographic grain but cannot preserve
  every fine fibre at four pixels per board.
- **Lanterns:** promising objects, weaker small sprites. Lettering and porcelain
  scenes read well at 64/128 pixels and become colour clusters at 20–32 pixels.
  The porcelain is stationary, rather than swinging as if it were paper. The
  paper source is underexposed; a uniform linear exposure multiplier of 1.45
  is recorded in settings. No lettering was invented or redrawn.
- **Lilies:** genuine pad folds and reflections give irregular highlights. Some
  strong sunlight is baked into these photos; directional maps cannot remove
  it. Diffusely lit pads would relight more consistently. The white flower is
  the scene default; the more saturated purple cutout is an optional variant.
- **Historical fit:** these are identifiable real objects from different
  sources, including Tibetan-influenced Lama Temple architecture and a Qing
  porcelain lantern. They establish a visual test, not a period-accurate set.

## Rebuild

```powershell
python photo_asset_pipeline/download_sources.py
python photo_asset_pipeline/build.py
python photo_asset_pipeline/blender/rebuild.py
python -m unittest test_photo_assets
python photo_asset_smoke.py
python roof_angle_smoke.py
```

The first command verifies existing originals and restores missing **selected**
images from the recorded URLs, checking their hashes. It uses `requests` and
needs network access only for missing files. Ordinary builds need only Pillow,
NumPy and the locally preserved sources. The separate roof rebuild requires
Blender; a normal photo build preserves the registered Blender outputs. The GPU
checks use the normal game dependencies and write fresh scene captures.

`research.py` and `collect_*.py` preserve the broader source-discovery work.
They are optional research helpers, not dependencies of a normal rebuild.

### Processing order

1. Preserve the downloaded JPEG / scan archive and image-specific rights record.
2. Trace masks in `settings.json`. Coordinates refer to the stated review-image
   dimensions and are expanded to the full source resolution. Separate polygons
   cut the porcelain crown/base holes. A one-source-pixel erosion excludes mixed
   background pixels. Roof sky and purple-flower filters are limited to their
   manually bounded regions; no generative fill or reconstruction is used.
3. Keep full-resolution transparent crops in `masters/` and separate masks in
   `masks/`. Fragment assemblies and perspective transforms are explicit in
   `build.py`; actual source colour, wear and photographic shading remain.
4. Resize in linear light with premultiplied alpha, then reduce to a palette.
   Palette selection uses visible pixels only. Dithering is disabled. Runtime
   alpha is thresholded to 0/255, with zero RGB outside the silhouette.
5. Export 128px/32-colour, 128px/64-colour and 64px/32-colour variants for each
   component. Architectural components also get 256px/64-colour versions.
   Runtime sprites are baked directly from masters at their game dimensions,
   with up to 64 colours; they are not upscaled copies of the 128px preview.
6. Bake conservative lighting responses and the paper lantern emission mask.
   Runtime loads ordinary cached nearest-filtered textures. None of the photo
   processing or segmentation runs per frame.

The Blender roof adds a separate offline geometry/render stage before the same
pixel reduction. Its light responses come from shadowed renders of a white
material, and its normal maps come from the mesh. See [the roof pipeline](blender/README.md).

`manifest.json` records source dependencies, runtime dimensions, selected
silhouette crop, pivots, notes and output hashes. `sources/*/source.json` records
original URLs, download date, rights URL, credit and SHA-256. See [SOURCES.md](SOURCES.md).

### Editing masks and directional light response

Change the polygons / runtime sizes in `settings.json`, then rebuild. Architecture
fragment crops and board geometry are in `architecture()` in `build.py`.

`responses/<asset>/` contains four generated greyscale draft layers:

| Layer | Light arrives from | Packed channel |
| --- | --- | --- |
| down | +Y / below the sprite | R |
| up | -Y / above the sprite | G |
| left | -X | B |
| right | +X | A |

White admits direct light; black rejects it. These maps describe a coarse rounded
lantern, sloping roof or timber surface. **They are not normals inferred from the
photo**, and do not erase baked shadows. The Blender variants instead derive
their response from the authored mesh; their geometry is not recovered from the
photograph either. Their gentle response is intentional.
The scene connects the roof, columns and lantern responses at 0.65 strength with
a 0.25 minimum direct contribution. Rails/piles retain ordinary lighting; their
draft maps are included for later experimentation. Facades retain the existing
planar aperture lighting. Lily drafts use broad response and are not connected to
the upright-sprite lighting path.

To paint an override, copy all four layers to
`response_edits/<asset>/{down,up,left,right}.png`, keeping the exact runtime size.
The next build packs these instead of the draft. This directory is never written
by the build. The `A` channel of a packed response is **right-light response**, not
opacity: do not run a background-removal tool on that file. Sprite alpha lives in
the colour image. Restart the review scene after rebaking textures.

## Validation

124 targeted unit/regression tests passed, including source hashes, palette and
alpha constraints, background-free resampling, original-scene isolation, matching
facade apertures, tile/footstep metadata, plank continuity, roof alignment across
camera angles, lighting-map orientation and normalized mesh normals. An existing pixel
snapping test had an obsolete mock for the high-level Raylib wrapper; it now
mocks the current direct Raylib entry point without changing its assertions.

`photo_asset_smoke.py` passed in the real renderer: texture and response upload,
response reuse across frames, stationary porcelain, window holes, roof fade on
entry/exit, the existing storm trigger, rain and full scene-resource cleanup.
The original water-temple regression suite also passes. This is not a new FPS
benchmark or a claim that photographed colour is fully relightable.

`roof_angle_smoke.py` also renders all three roof angles and the original cutout
with identical camera, time and lighting, under moonlight and bright inspection
light. The saved Blender project contains all four packed photo textures.

## 3D-assisted assets and possible next steps

The roof experiment is now implemented as an **offline Blender bake**, with
three orthographic camera views, colour sprites, normal maps and directional
responses. The game continues using its existing 2D sprite renderer. The
editable mesh and reproducible pipeline are in [blender/](blender/README.md).

A future live mesh could use the same anchor, height, depth ordering and roof-fade
policy as this sprite. It would need deliberate integration with reflections,
occlusion and lighting; it is not just a free camera switch. One photo does not
provide hidden sides or clean albedo: use additional photos, keep the camera
constrained, or accept explicit simple geometry. Live 3D rendering is a separate
experiment; this roof bake does not require it.
