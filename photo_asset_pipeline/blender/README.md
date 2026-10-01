# Blender roof / photo texture experiment

Built and verified with **Blender 5.2.2 LTS**. The installed executable is:

`C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`

Open [water_temple_roof.blend](water_temple_roof.blend) to inspect the model. All
four photographic textures are packed into it. It opens with the 30-degree
orthographic camera and the colour materials. There are three named cameras.

## What this fixes

The original cutout photographed the roof from below. Its underside and shallow
view of the tiles could not be corrected by scaling the sprite. This experiment
uses **actual roof slopes, hips, curved eaves, ridge caps and fascia geometry**.
Separate tile, edge and timber photo crops are mapped onto those surfaces.

The mesh has 2,462 triangles across 18 objects. It is a deliberately simple,
authored hipped-roof approximation, not a photogrammetric recovery of the
photographed building. The surface colour and wear come from the preserved
photographs. No generative image fill is involved.

The 30-degree view is the current visual choice for the existing facades. The
game has stylized 2D ground coordinates, so this is a starting art calibration,
not a claim to recover an exact physical camera for all existing sprites.
The higher views expose more of the rear roof and have a squarer silhouette.

## Review in the game

From the repository root:

```powershell
python moonlit_water_temple_photo.py
python moonlit_water_temple_photo.py --roof-angle 40
python moonlit_water_temple_photo.py --roof-angle 50
python moonlit_water_temple_photo.py --roof-angle photo
```

Default is 30 degrees. `photo` retains the rejected front-photo cutout for
comparison; `moonlit_water_temple.py` retains the earlier painted scene.

- [Same-camera in-game comparison](../review/roof-in-scene-comparison.png)
- [Native pixels and exact 2x enlargement](../review/roof-angle-comparison.png)
- [Photo texture crops](textures-review.png)

All three variants have a 216 x 116 canvas, with individual anchor offsets
calculated from the projected **front fascia**, keeping it at world Y=232.
We do not independently stretch a roof render to force it into the frame.
The camera stays orthographic and fits the mesh into the canvas with a margin.

The game loads ordinary cached PNGs. Blender does not run during gameplay;
the 3D mesh adds no runtime triangles. Existing roof fade, reflection, rain-edge
extraction and gameplay use the same paths as the earlier sprite.

## Rebuild and edit

```powershell
python photo_asset_pipeline/blender/rebuild.py
```

An alternate Blender executable can be supplied with `--blender`. This command
extracts photo textures, runs Blender in the background, and exports reduced
sprites and maps. It writes a local `bake.log`. It does not install add-ons or
change the user's saved Blender preferences (`--factory-startup`).

`roof_settings.json` controls dimensions, ridge height, eave/corner lift, candidate
camera elevations and selected `.blend` camera. The game launcher's default and
supported angle list are in `moonlit_water_temple_photo.py`. The model builder is
`build_roof.py`; photo crop quadrilaterals are in `prepare_textures.py` and recorded
in `texture_sources.json`. Colours/textures are prepared offline, and the packed
scene is entirely editable in Blender. A rebuild regenerates that scene, so save
hand-edited alternatives under a different `.blend` filename.

### Outputs

- `water_temple_roof.blend`: colour model, packed textures, three cameras.
- `renders/roof_{angle}.png`: transparent 864 x 464 colour masters.
- `../runtime/roof_blender_{angle}.png`: 216 x 116, <=64 colours, binary alpha.
- `../variants/roof_blender_{angle}/`: 64/128/256-pixel palette comparisons.
- `renders/normal_{angle}.png`: world-space normal data rendered with Raw colour
  management; a unit-vector native-resolution version is also retained.
- `renders/response_{angle}_{direction}.png`: white-material direct-light renders
  with geometry shadows, from four horizontal directions at 40-degree elevation.
- `../responses/roof_blender_{angle}/`: editable greyscale directional layers.
- `../runtime/roof_blender_{angle}_response.png`: packed down/up/left/right in RGBA.
- `render_metadata.json`: Blender version, camera scale, fascia projection and mesh
  count; `baked_assets.json`: pipeline registration, source dependencies and hashes.

Response data is resized as linear numeric data, without the sRGB transform used
for photographed colour. A-channel response remains right-hand lighting, not
opacity. The existing `response_edits/<asset>/` override convention is supported.

Colour renders use photographic texture with mild geometry ambient occlusion.
The source photos still contain their original lighting. The response bake adds
geometric directional behaviour but does not recover clean albedo. The game still
approximates lighting with four directions rather than using the normal map live.

## Validation

`test_photo_assets.py` checks all palettes/masks and source hashes, matching eave
alignment across views, lighting-map left/right orientation, normalized normals,
and unchanged gameplay data. `roof_angle_smoke.py` renders all views in the real
game with identical camera, time and lighting. `photo_asset_smoke.py` checks the
selected roof's fade, reflections, storm/rain, aperture lighting and cleanup.

The saved `.blend` was also reopened and rendered successfully, with all four
textures packed. To repeat this check in PowerShell:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background photo_asset_pipeline/blender/water_temple_roof.blend --python-exit-code 1 --python photo_asset_pipeline/blender/verify_scene.py
```
