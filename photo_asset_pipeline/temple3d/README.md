# Photo-textured Blender temple kit

This is an independent art and lighting pass over the water-temple scene.
The earlier painted scene and first photo/roof study remain available.

## Review

```powershell
python moonlit_water_temple_blender.py
python moonlit_water_temple_blender.py --lighting flat
python temple_3d_viewer.py
```

The first command is the **playable 2D game**, with baked sprites and per-pixel
normal lighting. It preserves the scene's trees, grass, gameplay, material
painting, collision, footsteps, roof fade, storm trigger, rain and reflections.
The second command shows the same new art with unshaped direct light for a
lighting comparison. `python moonlit_water_temple_photo.py` retains the preceding
photo study and four-direction roof response.
These changes are in the Python renderer; the native C comparison is unchanged.

The third command is a **live 3D art viewer**, using the actual exported meshes
and the same scene placement/tile collision data. It renders at 480 x 270 and
enlarges with nearest filtering. It has real raised decking, depth testing,
orthographic camera orbit, normal lighting and automatic roof cutaway. It is
not a gameplay port: its player is a marker, its water and lighting are simpler,
and it does not yet reproduce the game's reflections, shadows, storm, audio,
animated grass or tree deformation. Existing trees are static billboards there.

Viewer controls: **WASD** walk; **Q/E** orbit; **up/down** change camera elevation;
**mouse wheel** zoom; **R** roof cutaway; **L** inspection light; **Home** reset
camera; **F12** screenshot; **Esc** quit. Movement follows world axes.

- [Playable scene comparison](review/comparison.png)
- [Actual normal/height lighting sweep](review/normal-lighting-study.png)
- [Live 3D: front](review/live-3d-0.png) / [orbit](review/live-3d-1.png) / [inspection](review/live-3d-2.png)
- [Native asset and normal review](asset-review.png)
- [Photographic material crops](materials.png)
- [Editable, packed Blender kit](water_temple_kit.blend)

## Converted assets

Twenty bake definitions cover the roof, columns, two railing lengths, three
support/post sizes, fire bowls, paper and porcelain lanterns, altar, decorative
hanging panels, lily clusters, leaves, window wall, solid wall, open and closed
doorway, deck boards and masonry. A rotated floor atlas supports the boardwalk's
second grain direction. All lake props in the new scene select these assets.

Architecture, rails, lanterns, bowls and decking use authored 3D geometry.
Colour, grain and wear come from the preserved photographs. These are models
built from references, not photogrammetric scans or historically exact replicas.
The fire bowls currently use a temple masonry photo for a stone finish.
The decorative hanging panels use photographed painted motifs as a material
study; a genuine textile reference would improve them.

The **Buddha remains the user's existing photograph**, on a card above a modelled
altar. A single front photograph cannot supply its back. Lily pads use cupped
geometry with photo masks; the flower is a shallow relief of the intact photo,
not a reconstruction of every petal. These limits matter when orbiting in 3D.

All new material crops and operations are recorded in [sources.json](sources.json),
with hashes. The underlying source/rights records are in [../SOURCES.md](../SOURCES.md).
No original photographs or previous art assets were overwritten. No new image
generation, online source collection or external software installation is used.

## Lighting and geometric data

The previous roof combined four baked directional responses. The new shader
instead recovers a surface normal and local 3D position for each sprite pixel,
then evaluates that pixel against the current light's position **and height**.
This supports continuously changing light directions and different responses
on the roof hips, eaves, cylindrical posts, bowls and lanterns. Six response
bands, the existing light palette, binary silhouettes and nearest sampling keep
the image crisp. Paper has a small back-light response; porcelain has a restrained,
banded highlight. These settings are in `g_baked_assets.policy()`.

| Map | Meaning / current use |
| --- | --- |
| colour | At most 64 visible colours per asset; alpha is 0/255 |
| normal | RGB encodes a unit vector in game coordinates: X right, Y along ground, Z up; alpha contains ambient occlusion |
| position | RGB encodes local position between the manifest bounds; alpha contains authored roughness |
| height | Vertical component, normalized over the recorded bounds, saved separately for inspection/future use |
| depth | Distance along the baking camera's direction, with the range recorded in the manifest |
| AO | Ambient occlusion from the actual model, retained as a separate layer |
| mask | Sprite coverage, independent of the data maps' alpha channels |

Normals and positions are registered to the **same pixel centres** as colour.
Numeric maps bypass the photographic sRGB transform. The runtime maps have
8-bit channels; Blender's supersampled numeric masters are retained as 16-bit
PNGs. The separate scalar height/depth PNGs use 16-bit storage, but their current
export derives from the 8-bit decoded position channels; do not assume full
16-bit measurement precision. The manifest records scale, pivot and bounds.

The playable scene uses geometric height for the new **surface light direction**.
It retains existing light coverage/falloff and shadow visibility. Normal maps
do not create arbitrary self-cast shadows, recover hidden surfaces, or remove
lighting baked into a source photo. Ground atlases include geometric maps, but
the existing 2D ground renderer currently uses their colour/AO bake and ordinary
ground lighting; the live viewer lights the actual ground geometry. Full pixel
depth compositing and new stair/multilevel gameplay are future steps.

## Rebuild and edit

Verified with Blender 5.2.2 LTS:

```powershell
python photo_asset_pipeline/temple3d/rebuild.py
```

`--blender <executable>` selects another installation. `--export-only` repeats
the palette and data conversion without rerendering. The builder runs in the
background with factory settings; it does not install add-ons or save user
preferences. Rebuilding regenerates the `.blend`, so save hand-edited variations
under a separate filename.

1. `prepare.py`: extract materials, retain provenance, copy the game's aperture masks.
2. `build.py`: model the kit, apply photo UVs, bake colour/normal/position/AO, export
   triangulated OBJ meshes and a packed Blender file with the kit laid out in rows.
3. `export.py`: palette reduction and binary coverage; unit-vector normalization;
   registered position/height/depth maps; manifest and review sheets.

The same 30-degree camera is used for upright objects; floor atlases use an
explicit top-down camera to retain existing world-aligned tile painting.
Window and door stencils remain exact, including the closed door's holes.
`temple_mesh_loader.py` loads the exported triangle groups into GPU buffers once.
The installed Raylib OBJ loader stalled on this export, so the viewer uses this
small parser for our documented v/vt/vn triangle format instead.

## Performance and checks

Runtime colour/geometry textures are cached. Normal/position maps are shared
among instances. Normal lighting uses the existing per-light sprite pass, with
one packed uniform upload for geometric/material parameters and reusable CPU
light-eligibility tests. No Blender or photo processing occurs during gameplay.

A short local uncapped benchmark, including GPU readback, gave these median
completion times (24 measured frames per case, after warmup):

| Scene | Approach | Walking | Interior |
| --- | ---: | ---: | ---: |
| Previous photo scene | 35.5 ms | 48.9 ms | 36.6 ms |
| Initial normal implementation | 53.4 ms | 64.9 ms | 53.4 ms |
| Packed parameters + cached eligibility | 42.8 ms | 53.7 ms | 43.3 ms |

This is a local regression check with other activity on the machine, not a
moderate-machine or 60 FPS certification. The richer lighting still has a cost.
Logs are under `artifacts/moonlit-water-temple/` with labels
`photo-before-blender-kit`, `blender-kit-normals` and `blender-kit-final`.
The larger structural opportunity is a shared material-data buffer and light
pass instead of repeated sprite-material setup; profile before attempting it.

```powershell
python -m unittest test_blender_assets test_photo_assets test_water_temple test_temple_storm test_surfaces test_night test_entity_self_shadow test_render_performance test_flashlight_origin test_light_visibility test_entity_light_optimization -q
python normal_lighting_smoke.py
python blender_temple_smoke.py
python temple_3d_viewer.py --smoke
python benchmark_water.py --art blender --calm --label blender-review
```

160 targeted checks passed. They include independent camera reprojection of
position maps, normalized normals, palettes/hashes, map mismatch fallback,
per-light height, unchanged collision/sequence/tree data, exact apertures and
floor continuity. GPU checks cover six light directions, actual roof lighting,
texture sharing, roof entry/exit, rain/storm, closed door and resource cleanup.
The saved Blender kit was reopened and verified to contain all 20 editable
model collections and 17 packed photographic image resources.

## Suggested direction

Make photo-textured Blender models the source assets and retain both sprite and
mesh exports. First improve the curated materials (aged decking, diffuse-lit
paper, actual cloth and stone/metal detail). Then test one controlled live-3D
room or doorway with a fixed orthographic camera, real shadowing and planar
water reflections before considering a full rendering migration. The shared
tile logic already survives the viewer experiment; gameplay height, stairs,
AI sight and multi-floor navigation still need explicit designs.

Blender's standard [render passes](https://docs.blender.org/manual/en/latest/render/layers/passes.html)
also provide geometric depth/position/normal information. These exported maps
contain only the visible surfaces from their baking camera; retaining the mesh
is what preserves the hidden geometry for other views.
