# Temple: fixed-camera walkthrough

```powershell
python moonlit_water_temple_3d.py
```

Or double-click `play_temple_3d.cmd`. The launcher selects the local **Raylib
5.5.0.4** environment before importing the renderer. On a new checkout, run
`python setup_temple_3d.py` once. This environment overrides Raylib locally and
reuses the already-installed Python game dependencies; the original global
Raylib 5.0 installation and native C comparison are unchanged.

Walk along the boardwalk, turn toward the open door, enter the temple, and return.
Three composed orthographic views cut automatically: across the lake, the temple
landing, and the altar room. The image remains 480 x 270, enlarged with nearest
filtering. This uses the photo-textured Blender meshes from the live art viewer.

## Controls

| Key | Action |
| --- | --- |
| WASD | Move relative to the current shot |
| Shift | Run |
| Release all movement keys | Adopt the new shot's movement directions |
| Home | Return to the starting point and first shot |
| H | Hide/show the help and shot title |
| R | Toggle roof cutaway for inspection |
| L | Toggle neutral inspection lighting |
| F12 | Save `artifacts/temple-camera-trial/fixed-camera-user.png` |
| Esc | Quit |

Holding a direction through a cut preserves its world direction. Adding another
movement key retains that same basis until all movement keys are released. This
prevents an abrupt reversal when the new camera looks from the opposite side.
Movement slides along blocked tile edges, including the sides of the boardwalk.

Each shot has a smaller entry region and a larger retention region. These
overlapping regions keep a player near a boundary from repeatedly switching
views. Returning along the route restores the earlier shots.

The existing roof fade remains. The interior shot also hides the front facade
to keep the room readable; the columns, lanterns and collision remain. This is
a deliberate shot-specific cutaway, not a change to the original scene.

## Authoring and implementation

- [Camera definitions](art/temple/camera_shots.json): eye, target, vertical
  orthographic span, region priority, `enter`/`hold` rectangles, and optional
  `hide_front_facade`. That option covers this scene's front facade entities.
- [Camera and movement logic](g_temple_cameras.py): independent of Raylib.
- [Shared live renderer](temple_3d_viewer.py): `--fixed-cameras` selects this mode;
  running without it retains the orbital art viewer and its world-axis controls.

Camera vectors use `(X, height, ground Y)`. Region rectangles use
`[min X, min ground Y, max X, max ground Y]`. Higher priority wins on entry;
the current shot otherwise persists until the player leaves its `hold` rectangle.
Terrain generation writes into the ignored artifact cache, rather than changing
the exported model files.

## Raised bridge and temple floor

`g_temple_deck.py` replaces solid wood tile extrusions with individual boards,
transverse beams and piers extending below the waterline. `g_temple_structure.py`
prepares a separate 3D layout: the surrounding forecourt/skirt is removed, the
temple stands on its own heavier bearer beams and twelve piers, and a narrow
walkway connects directly to the entrance. Temple floor height is 24; bridge
height is 16. Roof, walls, lamps and furnishings follow the raised building.

Six low shore steps rise from the grass to the bridge; four shorter risers
connect the bridge to the temple sill. Walking uses the actual tread heights
with smoothed root elevation. Independent foot alignment to individual steps
is not implemented yet. The normal spawn remains on the bridge; walk back toward
the grass to try the shore steps.

The layout operates on a copy of the original arena. Removed platform cells
become collidable water, while the existing doorway and movement code remain
in use. Rails and former forecourt props move onto the supported footprints.
Board gaps remain visual. The geometry has 170 boards, 27 beams, 38 piers and
10 stair treads plus risers/stringers: 3,300 triangles combined into three
material batches at load time. There is no per-board update or draw loop.
`python moonlit_water_temple_3d.py --structure-review` saves three views under
`artifacts/temple-camera-trial/`: `structure-0.png` (bridge), `structure-1.png`
(temple foundation), and `structure-2.png` (shore stairs).

## What this experiment establishes

The existing tile collision and authored camera cuts work with a revised 3D
footprint and explicit floor heights. This is useful for judging composition,
spatial readability and controls before committing to a rendering migration.

The actor is now a low-poly, GPU-skinned player based on the existing directional
sprites, with idle/walk/run clips and short pose blends. Both willows now use a
3D trunk, branches and hanging painted foliage with GPU wind. See the
[editable living asset kit](photo_asset_pipeline/temple3d/living/README.md).
The [3D animation viewer](ANIMATION_VIEWER_3D.md) provides slow motion, frame
scrubbing, skeleton overlays and a Blender review file for refining the gait.

This is not yet the main game running in 3D: interactions, enemies, storm
scripting, audio, the richer water/reflections, cast shadows and animated grass
have not been connected. The Buddha remains the original photographic card.
The separate 2D game launchers remain available. `--classic-assets` restores
the capsule and tree billboards for comparison. The orbital viewer keeps those
older assets by default; to orbit the new models, run
`artifacts/temple3d-env/Scripts/python.exe temple_3d_viewer.py --living-assets`.

The next useful milestone is connecting the existing interaction and character
gameplay logic, followed by 3D shadows, water reflections and the temple
storm. Evaluate those together at the intended low resolution and profile the
frame time before deciding on a full migration. More general terrain/foot IK
can build on the separate ground positions and render heights used by the stairs.

## Verification

```powershell
artifacts/temple3d-env/Scripts/python.exe -m unittest test_temple_living test_temple_cameras test_temple_gait_deck test_blender_assets -q
python temple_living_smoke.py
python moonlit_water_temple_3d.py --smoke
python temple_3d_viewer.py --smoke
python moonlit_water_temple_3d.py --structure-review
```

Tests cover input continuity across cuts, release/reorientation, boundary
overlap, diagonal speed, collision sliding, preventing tunnelling, and traversal
of the entire route through the real scene's collision data. The GPU smoke saves
thirteen route frames in both directions and checks the selected shot, walkability
and actor framing. Review images are in `artifacts/temple-camera-trial/`.
Living-asset captures, animation GIFs and the GPU verification report are in
`artifacts/temple3d-living/`. The check confirms changing GPU output while CPU
vertex buffers remain unchanged, and checks continuity at animation transitions.
The gait/deck checks cover planted contact, knee extension and flexion, rearward
arm/leg travel, continuous foot paths, supported boards and piers, stair height
agreement, collision around the separate structures, and preservation of the
original 2D arena.
