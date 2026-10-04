# Temple: 3D exploration and level editing

```powershell
python moonlit_water_temple_3d.py
```

Or double-click `play_temple_3d.cmd`. The launcher selects the local **Raylib
5.5.0.4** environment before importing the renderer. On a new checkout, run
`python setup_temple_3d.py` once. This environment overrides Raylib locally and
reuses the already-installed Python game dependencies; the original global
Raylib 5.0 installation and native C comparison are unchanged.

The first gameplay milestone now runs here: collect the brass key on the
boardwalk, unlock the temple entrance, open it with a second interaction, and
inspect the inscription in front of the altar. Medicine near the starting point
can be collected and used from the inventory when health is below 100.

Walk along the boardwalk, turn toward the entrance, enter the temple, and return.
Three composed orthographic views cut automatically: across the lake, the temple
landing, and the altar room. The image remains 480 x 270, enlarged with nearest
filtering. This uses the photo-textured Blender meshes from the live art viewer.

## Controls

| Key | Action |
| --- | --- |
| WASD | Move relative to the current shot |
| Shift | Run |
| Release all movement keys | Adopt the new shot's movement directions |
| E | Inspect, collect, unlock/open or close the nearby door |
| Tab | Inventory; arrows select, E/Enter uses an item |
| E / Enter | Continue dialogue; left/right selects a choice |
| F5 / F6 | Save / reload exploration progress |
| F2 | Enter / leave the placement editor |
| Home | Return to the authored spawn, retaining progress |
| H | Hide/show the help and shot title |
| R | Toggle roof cutaway for inspection |
| L | Toggle neutral inspection lighting |
| F12 | Save `artifacts/temple-camera-trial/fixed-camera-user.png` |
| Esc | Cancel a dialogue, close inventory, or quit during exploration |

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

- [Saved scene](art/temple/exploration.scene.json): decorative object transforms,
  stable exploration IDs, spawn and design markup. Load a separate scene with
  `python moonlit_water_temple_3d.py --scene path/to/scene.json`.
- [Exploration controller](g_temple_gameplay.py): synchronizes the original
  player state with camera-relative movement and uses the shared inventory,
  descriptions, choices and puzzle handlers. Movement, footsteps, animation
  and the gameplay clock pause for modal UI and scene editing. Opening and
  closing a modal also consume their input frames.
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

## Level blockout, placement and design markup

Press **F2** to pause exploration and open the editor. **C** switches between
an overhead view and the actual game camera. The complete camera composition is
shown beside the tool panel. In the overhead view, WASD pans and the wheel zooms.

| Control | Action |
| --- | --- |
| 1 / Select | Click an object or mark, then drag it; arrows nudge |
| 2 / Place | Choose an object in the palette and click the scene |
| Q / E | Rotate the selected object in 15-degree increments |
| G | Toggle four-unit snapping; Shift enables one-unit placement/nudges |
| Ctrl+D / Delete | Duplicate / remove the selected object or mark |
| 3 / Note | Click, type a design note, Enter commits, Esc cancels text |
| 4 / Arrow | Click the start and end, then type an optional note |
| 5 / Area | Click opposite corners, then type an optional note |
| 6 / Floor | Choose a material and drag a rectangle to build floors or walkways |
| 7 / Stairs | Click the lower corner, then the opposite upper corner |
| 8 / Spawn | Click a clear walkable spot for the starting position |
| [ / ] | Lower / raise the chosen floor or stair landing height by four units |
| V | Change wood grain direction or stair ascent direction |
| Right drag (Floor) | Erase a floor rectangle into water |
| Alt+click (Floor) | Sample an existing floor's material, height and grain |
| Right click (Stairs) | Remove the stair flight under the cursor |
| J | Toggle automatic edge rails |
| K | Choose yellow, blue or red markup |
| Enter | Edit the selected mark's text |
| Ctrl+Z / Ctrl+Y | Undo / redo; a complete drag is one operation |
| Ctrl+S / Ctrl+O | Save / reload the scene; reload is undoable |
| F2 | Return to exploration, applying unsaved edits in the current session |

Scene edits persist only after **Ctrl+S**. Closing the editor keeps unsaved edits
in memory. Save files preserve UTF-8 notes, arrows, areas and object IDs, so you
can mark a location and describe the intended change directly in the game.
Decorative props, keys, medicine and inscriptions can be placed; moving a fire
bowl also moves its emitter and collision. Collected items retain their progress
through layout edits; duplicates receive new IDs. If an edited prop overlaps the
player, returning to play moves him to a nearby clear position.

The second milestone adds saved floor footprints. Wood produces suspended
boards, beams and piers; stone and grass produce solid platforms. Walls stand
48 units above their selected base height and block movement. Water removes
walkable floor. **Restore original** restores the shipped surface and any
original stair flight touched by the rectangle. Each complete floor drag is
one undo operation. Rectangle boundaries use 16-unit construction increments.

Heights range from 0 to 48; the original bridge is at 16 and the temple at 24.
Stair flights rise in any of four map directions, with automatically sized
risers. Set the upper landing height before placing stairs; their lower height
comes from the first clicked location. Draw a longer rectangle if the tool
reports that the flight is too short. Floor painting across stairs replaces
the whole flight. The player can climb short risers and cannot step directly
up or down a tall ledge. Individual foot IK remains future animation work.

Floor commits, undo/redo and scene reload rebuild the visible meshes from the
same data that drives collision, floor height and surface footsteps. Boundary
rails follow exposed raised wood edges and disappear across newly connected
floor. New walkable areas outside the original footprint get a local camera
view so the player remains visible; the original authored shots are retained
on the original route. Leaving the editor relocates the player if a floor or
prop edit makes the current position invalid. A completely erased layout stays
in the editor until it has a walkable starting point again.

The scene file stores edits to the original layout rather than duplicating
all exported geometry. Older placement scenes load with the original floor and
stairs automatically. The decorated temple shell, its entrance and original
camera regions remain anchored; new walls are blockout masonry. There is one
walkable surface at each map position, so overlapping floors are later work.

## Exploration saves

**F5** writes `saved_editor_states/temple3d-progress.json`; **F6** reloads it.
The save contains player position, heading, health, ammunition, inventory,
collected items, door state and puzzle facts. It contains no graphics, audio
voices, modal dialogue or editor history. Startup begins a fresh exploration;
press F6 to continue a saved one. Invalid saves are rejected before changing
progress. Layout and player progress are separate files, so a playthrough cannot
overwrite level design. F5/F6 are available during exploration, outside modals.

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

## Current scope and verification

The existing tile collision and authored camera cuts work with a revised 3D
footprint and explicit floor heights. This is useful for judging composition,
spatial readability and controls before committing to a rendering migration.

The actor is now a low-poly, GPU-skinned player based on the existing directional
sprites, with idle/walk/run clips and short pose blends. Both willows now use a
3D trunk, branches and hanging painted foliage with GPU wind. See the
[editable living asset kit](photo_asset_pipeline/temple3d/living/README.md).
The [3D animation viewer](ANIMATION_VIEWER_3D.md) provides slow motion, frame
scrubbing, skeleton overlays and a Blender review file for refining the gait.

Interactions, pickups, inventory, healing, linked entrance collision, inspection
callbacks, progress saves and distance-driven footsteps now run in 3D. Footsteps
use the existing surface-aware spatial audio runtime and sound files; optional
ambient/fire families fall back to silence when their recordings are absent.
Enemies, combat, storm scripting, richer water/reflections, cast shadows and
animated grass remain later migration work. The Buddha remains part of the
existing altar asset.
The separate 2D game launchers remain available. `--classic-assets` restores
the capsule and tree billboards for comparison. The orbital viewer keeps those
older assets by default; to orbit the new models, run
`artifacts/temple3d-env/Scripts/python.exe temple_3d_viewer.py --living-assets`.

```powershell
python -m unittest test_temple_layout test_temple_exploration test_inventory test_puzzles test_temple_cameras test_audio test_temple_gait_deck
python moonlit_water_temple_3d.py --gameplay-smoke
python moonlit_water_temple_3d.py --player-review
```

The gameplay smoke test drives movement and actual shared modal input in a hidden
Raylib 5.5 window. It checks pickups, healing, modal pause, both door leaves,
camera cuts, an inscription callback, a progress round trip, scene undo/redo,
duplicate IDs, moved fire emitters and UTF-8 markup. Captures and its JSON report
are written to `artifacts/temple-exploration/`; all smoke saves use that directory
and leave the shipped scene and user progress untouched. The original art,
structure and animation review modes remain available.

The same review now injects a mouse drag through the actual editor/camera picking
path, builds an extended walkway, stone landing, stair flight and upper terrace,
and walks the player over them. It verifies material footsteps, framing, wall
collision, progress reload, geometry undo/restore and an empty-mesh rebuild.
The editable demo is saved as `artifacts/temple-exploration/blockout.scene.json`;
try it with `python moonlit_water_temple_3d.py --scene artifacts/temple-exploration/blockout.scene.json`.

The next gameplay migration work is enemies, combat and the temple storm.
Shadows and water reflections can be evaluated at the intended low resolution
alongside those systems, with frame-time profiling to guide the rendering work.
More general terrain/foot IK can build on the separate ground positions and
render heights used by the stairs.

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
