# Intro cinematics editor

For the Void Canals fog reveal, use `edit_huxin_canals.cmd` or **F2** in the
Canals scene. Its timeline and fog-placement controls are described below.

Double-click `edit_intro_cinematics.cmd`, or run:

```powershell
python moonlit_water_temple_3d.py --cinematics-editor
```

You can also press **F2 during the drive**, including while paused. F2 or Escape
returns to the ride at the editor's playhead; your previous mouse-look direction
and pause state are restored. The editor uses the same car, characters, rain,
glass, countryside, headlights and subtitles as the game.

## Compose a shot

1. Select a shot from the list. Choose **START** or **END** on the right.
2. Hold **right mouse** over the image and move the mouse to turn the camera.
   **WASD** moves it; **Q/E** moves down/up. Shift moves faster, Ctrl slower.
   While flying, the mouse wheel changes movement speed.
3. **Middle mouse** orbits around the look-at point. Shift + middle mouse pans.
   **Aim at car** and **Aim at player** make framing easier.
4. Scroll over the image to change the lens. Click any coordinate or lens value
   to type an exact number, then Enter to apply. Escape cancels that value edit.
5. Set both camera keys for a move, or use **Match other key** for a held shot.
   Choose eased movement or constant speed. **Reset camera** restores that shot
   type's original framing.

Coordinates are in metres relative to the travelling car: X is sideways, Y is
height, and negative Z points toward the front of the car. The camera stays with
the car while the countryside passes. Numeric look-at values specify a point;
the middle-mouse orbit turns around that point.
Road height and uphill/downhill pitch are applied automatically to the preview
and game. Camera coordinates remain relative to the car, including when scrubbing
the final climb; existing shot keys do not need to be raised by hand.

**Mouse look** controls whether the player can look around during that shot.
**View: Interior/Exterior** controls first-person body visibility. Moving a camera
out of the cabin through flight or position fields selects the exterior view and
a fixed camera automatically; these buttons remain available for explicit choices.

## Preview and edit the timeline

The current 2:56 sequence includes **turn-off-the-main-road** (1:58-2:17),
**climb-through-the-pines** (2:17-2:43) and **arrival** (2:43-2:56).
These are ordinary editable shots. The arrival shot frames the clearing,
54 entrance steps and upper temple roofs.

**Space** plays or pauses the sequence. **Loop shot** repeats the selected shot.
**Audio** enables the rain, engine and wipers while playing. The image can show
subtitles and thirds guides independently.

Click or drag the timeline to scrub. Drag a white cut boundary to change both
adjacent shots together; Shift enables finer timing. Dialogue remains at its
authored time and is shown by the grey bars underneath. Left/right arrows step
1/30 second; Shift + arrow steps one second. Home jumps to the beginning.

**Split at cursor** creates a cut with camera poses that meet at that instant.
**Remove shot** lets an adjacent shot cover its time. The night-transition shot
is retained because it controls the lighting change; its camera and cut boundaries
are fully editable. Its headlight timing scales with its duration. Start and end
of the complete ride stay fixed so the arrival and gameplay handoff stay aligned.

## Save and undo

**Save to game / Ctrl+S** writes the camera keys and cuts into
[dialogue.json](art/temple/intro/dialogue.json). Normal game playback reads those
same values. Saves validate the full document and replace it atomically.

**Ctrl+Z / Ctrl+Y** undo and redo. A camera gesture or cut drag is one undo step.
**Reload / Ctrl+O** reads the saved shots and is itself undoable. A star and
“Unsaved changes” show edits that still need saving. When opening the editor
through F2, unsaved changes apply to the current ride; save to keep them for future
sessions. In the standalone editor, use Save before exiting to keep changes.

## Verification

### Mountainside arrival assets

The arrival now spans 194 metres across 17 halls. Shallow court slabs and
retaining bands sit in a continuous hillside; six asymmetric wings climb out
to the sides. The 54 entrance steps and central sightline stay open, while
385 trees and irregular undergrowth patches obscure the outer limits.

The mountain forest uses mature **Chinese arborvitae / Platycladus orientalis**
and **lacebark pine / Pinus bungeana**, with 21-metre and 27-metre prototypes.
The private climb now has three irregular near-tree rows on each side, deeper
forest behind both verges and balanced undergrowth. The continuing public road
has its own planting and shrub batches in public-road coordinates, so those
trees keep following the lakeside road after the car turns away. Planting clears
both carriageways. `python temple_intro_forest_review.py` captures both routes
and checks the uploaded road geometry with audio muted.
Each is 1,910 triangles with wind weights, a 256px foliage atlas and a shared
64px bark atlas. The smaller lakeside Chinese pines remain along the public road.
Fahai's actual ancient white-barked pines and cypresses informed the choice:
[Beijing's Fahai account](https://www.beijing.gov.cn/renwen/sy/whkb/201912/t20191226_1867617.html).
Mature arborvitae's irregular crown and flattened leaf sprays follow
[Flora of China](https://www.iplant.cn/foc/pdf/Platycladus.pdf).

Edit [g_intro_temple_layout.py](g_intro_temple_layout.py) for building pads,
mountain contours, grove clearances and wing locations. The runtime terrain and
Blender architecture share those coordinates. The terrain uses parallel
world-space sections and smooth heightfield normals to avoid folded mountain
passes. Roads keep their own constant-width geometry.

Rebuild the assets independently of the car:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_intro_forest.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_intro_temple.py
python temple_intro_mountainside_review.py
```

Blender sources: [mountain_forest.blend](art/temple/intro/mountain_forest.blend)
and [temple_approach.blend](art/temple/intro/temple_approach.blend).
The new foliage was generated with built-in ImageGen and reduced with alpha
preserved: [source](art/temple/intro/mountain_foliage_source.png),
[256px runtime atlas](art/temple/intro/mountain_foliage.png),
[exact generation prompt](art/temple/intro/mountain_foliage_prompt.txt).

The muted mountainside review captures the pass, cabin, lateral wings, upper
courts and night arrival, plus an animated approach. It checks uploaded terrain
at 1,386 lane-centre and wheel-track positions. Latest local measurement: about
25 seconds to preload, 11.5ms median frame including readback at 480x270 in the
sampled approach; this excludes window presentation. Results are under
`artifacts/intro-mountainside/`.

### Editor and gameplay checks

```powershell
python -m unittest test_cinematics_editor test_temple_intro -q
python moonlit_water_temple_3d.py --cinematics-editor-review
python moonlit_water_temple_3d.py --intro-handoff-smoke --combat-smoke
```

The native editor review exercises the real input handler and widgets, camera
flight/orbit/pan, typed lens values, invalid-value rejection, cut dragging,
scrubbing, splitting/removing, undo/redo, save/reload, looping and the F2 round
trip. It uses an isolated, reproducible timeline and confirms that game playback
reads the saved camera. It leaves the actual cinematic file untouched. Screenshots
and a report go to `artifacts/cinematics-editor/`.

## Void Canals fog editor

Double-click **`edit_huxin_canals.cmd`**, run `python huxin_canals_viewer.py --editor`,
or press **F2** during ordinary Canals play or the puzzle test. The standalone
editor opens at full fog strength so placement changes are immediately visible.
It uses the actual game renderer, including the water reflections, with sound muted.

The left list contains nine jump points, from puzzle activation through the
hidden world blend, the overlapping near/middle/distant clearing phases, and
the last traces. Click a point to jump there. Drag its marker along the bottom
timeline, or click **Point time** to type an exact value. The phase order is
preserved; markers stop short of their neighbours. Activation stays at zero.
Click or drag the tracks to scrub freely, including backward through the blend.

**Space** plays or pauses. **Loop interval** repeats the section from the
selected point to the next. Left/right arrows step one frame; Shift + arrow
steps one second. Shift while dragging a marker gives finer timing adjustments.

### Give each building its own fog

The **Fog placement** tab opens in **Buildings / groups** mode for the current
scene. Click a building in the preview, or use the searchable target list on the
left. The list includes every house individually, plus water, quays, bridges,
foreground wisps and distant backdrop groups. Search by house number, ID, name
or type; scroll over the list or use its page buttons. This selection uses the
building catalog, so the scene's batched model exports do not merge the houses
into one selectable object. Broad foreground/backdrop groups are selected from
the list. F8 remains the separate Codex object-selection tool.

Use **Frame selected target** to inspect it, then drag the coloured **X/Y/Z
handles**, type an offset, or use the 0.25-metre nudge buttons. Offsets are world
metres. **Spread / size** scales the selected fog locally about that target's
centre. **Opacity multiplier** adjusts only that group's transparency. The
solid outline marks the target bounds; the dashed outline is a conservative
fog envelope including the billows' reach. It is not the exact noisy edge.

**Reveal starts** and **Mostly clear** set that target's independent clearing
interval in seconds after puzzle activation. The selected target also has an
**S / E** timeline bar; click a handle to jump to its exact time, or drag it to
change that time. Clearing cannot
start before the hidden world blend ends, and its end must remain within the
whole sequence. The faint tail finishes at the final sequence point. A click
without dragging does not round or change a time.

In building mode, **Reveal starts** begins a curved retreat of that target's
clouds. Opacity holds briefly while they move (up to 1.4 seconds, shortened for
small intervals), then fades to **Mostly clear**. Continuous rolling motion
runs through the five-second density crest and the world blend. The dashed
envelope includes the retreat path; scaling or moving a group also transforms
that path. Pausing the timeline freezes motion, and scrubbing reproduces it.

The near/middle/distant reference points on the left remain useful jump points
and camera keys; in building mode they do not drive individual clearing times.
Changing a global blend/end point preserves the groups' absolute times unless
they no longer fit, in which case affected intervals are clamped in the same
undo step. **Reset selected fog** restores just that target's settings using
the current global timing.

**Legacy banks** switches to the earlier Nearby / Middle / Distant layout for
comparison. Both configurations are retained when switching modes. Its handles,
size, opacity and **Reset this bank** still affect a whole bank; the original
near/middle/distant cue timing applies in that mode.

**Reverse view** and **Overhead** help inspect the layout. On the Fog tab,
hold right mouse and use WASD / Q / E to fly around, or middle mouse to orbit.
Shift + middle mouse pans; the wheel changes the lens. These inspection moves
do not change the saved camera path. **Authored view** returns to it. **Guides**
toggles the placement handles; they hide during playback.

The optional **Camera** tab provides a camera key at each timeline point.
Editing its position, target or lens, or flying/orbiting while that tab is open,
enables the camera path for game playback. **Hold this view at all points**
copies the selected framing throughout. The path is initially disabled, preserving
the existing game cameras. Once enabled it plays during the reveal until the
player moves after control returns.

### Save and return to play

**Save to game / Ctrl+S** atomically writes
[`direction.json`](art/temple/huxin_canals/direction.json). Normal gameplay and the
puzzle launcher watch the same file while running, so a save updates the current
scene without a restart or **Home** reset. **Ctrl+Z / Ctrl+Y** undo and redo;
one drag is one undo step.
**Reload / Ctrl+O** reads the saved values and can itself be undone.
**Restore defaults** restores the current mode's initial placement and the
5-second build, 1-second blend and 40-second clearing timeline in the editor;
saving makes it permanent. Undo restores the preceding configuration.

**Return / exit**, F2 or Escape offers **Save and return**, **Discard and return**,
or **Keep editing** if changes are unsaved. When opened from play, returning resumes
at the chosen playhead without replaying sound cues or consuming another object.
The player's position is retained. F8 provides the existing Codex selection mode
and records the selected timeline point, time, fog mode and target with the
selection. The editor uses at least 1360 x 900 pixels so its target list,
placement fields and independent timeline controls remain readable.

### Edit the direction file while the editor stays open

Leave **Live ON** enabled and keep the editor open while changing
[`direction.json`](art/temple/huxin_canals/direction.json) in a text editor or
asking Codex to change it. Complete, valid saves appear after a brief settling
delay. The preview keeps its playhead, selected house, inspection camera and
F8 object selection. Live updates also work while the preview is paused.
In normal play, the player keeps their position and elapsed sequence time;
updating the file does not restart the puzzle or replay its sounds.
Once the village has been revealed, moving the blend time later does not turn
the running game back into the lake. Scrub in the editor or reset with **Home**
to replay that transition with the new timing.

Fog placement, size, opacity, independent reveal times, global timing and camera
keys are live data. Edited camera keys affect the authored camera view; a free
inspection view stays where you placed it. Python code, shaders, model exports
and texture assets still require restarting the running scene.

Unsaved editor changes and external changes to different fields merge. If both
edit the same field, or their combined timings would be invalid, the editor
holds the current preview and shows a conflict. **Use file** loads the complete
file version, discarding unsaved editor changes; **Keep mine** explicitly saves
the current editor version over the file. An ordinary save refuses to overwrite
an unresolved conflict. **Live OFF** pauses automatic updates, but saves still
check for external changes.

A missing, incomplete or invalid file leaves the last good scene running and
shows an error. Correcting and saving the file resumes live updates. During a
drag, numeric entry or the exit dialog, valid external changes wait until that
interaction finishes. **Home** remains an explicit game reset, rather than a
requirement for seeing a direction edit.

Focused checks:

```powershell
$env:HAUNTED_MUTE_AUDIO='1'
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin_canals_direction test_huxin_canals_targets test_huxin_canals_editor test_huxin_canals_building_runtime -q
artifacts/temple3d-env/Scripts/python.exe huxin_canals_building_review.py --label editor-check
artifacts/temple3d-env/Scripts/python.exe huxin_canals_live_review.py
```

The building review is hidden and muted and saves screenshots and its report
under `artifacts/huxin-canals-buildings/editor-check/`. It exercises the actual
target picker, transform gizmo, reveal handles, fields, undo/save/reload and
fresh-game playback, alongside direct/reflected fog and performance checks.
It edits an isolated temporary direction file, leaving the game's saved
direction unchanged. Add `--quick` for a shorter native pass.

The live review uses a temporary direction file and a temporary F8 selection
file. It verifies rendered updates in the open editor and normal play,
last-good recovery, independent merging and conflict protection. Its hidden,
muted screenshots and report are under `artifacts/huxin-canals-live/`.

The earlier bank-mode editor review remains available with
`artifacts/temple3d-env/Scripts/python.exe huxin_canals_editor_review.py`; its
screenshots and report go under `artifacts/huxin-canals-editor/`.

### Authored volumetric fog alongside the quad layers

The **Volumes** tab edits a separate, bounded three-dimensional fog layer.
Existing direction files keep the previous appearance until volumes are added
or enabled. **Quads only**, **Volumes only** and **Hybrid** compare the techniques
without discarding either setup. The independent **Volume amount** and **Quad
amount** fields control the mix; **Quality** cycles Draft, Balanced and High.
The ordinary ambient lake mist remains in all three modes.

The new layer integrates animated three-dimensional density between each
volume's boundaries and the visible scene surface. It supports entering a
volume, depth occlusion and the same world-space fog in water reflections.
Broad rolling noise, smaller moving eddies and stepped shading retain the
painted appearance. Balanced renders at half resolution with depth-aware
upsampling; High uses full resolution and more samples. Up to 24 independently
authored regions are supported.

Use **+ Box volume** for a room, lane or sheet over the water, or **+ Ellipsoid
volume** for a softer cloud bank. Click a building in the preview, then choose
**+ Fit selected building** to make a shell around it. F8 semantic building
selections also transfer to this target when leaving selection mode. New volumes
enable the volumetric layer automatically. The region list supports paging and
the mouse wheel; **Duplicate**, **Remove** and **Frame selected volume** act on
the selected region. Click its name at the top of the properties to rename it.

The three property pages keep the controls grouped:

- **Shape**: centre, half-size, rotation and hollow core. Half-size is the distance
  from the centre to each side, in metres. The gold wireframe shows the authored
  volume bounds; the blue inner frame shows the hollow core. Drag XYZ handles to
  move it. Right mouse + WASD / Q / E inspects without altering the game camera.
- **Flow**: density, edge softness, noise size, turbulence and XYZ wind speed.
  Wind moves the internal noise; it does not move the bounds.
- **Timing**: build start/full density, clearing start/gone, and a total retreat
  displacement. The two additional timeline tracks provide draggable handles
  for build and clearing. Retreat moves the region while it clears.

Volume controls share the same Save, Undo, Redo, Reload, Live and conflict handling
as the quad controls. F8 records the current volume ID and editor tab as well as
the selected scene objects. To work on an independent experiment rather than the
main direction file, use **`edit_huxin_canals_volumetric.cmd`**. Its companion
**`play_huxin_canals_volumetric_test.cmd`** starts at the puzzle. Both are muted
and use the separate, live-reloaded
[`direction-volumetric.json`](art/temple/huxin_canals/direction-volumetric.json),
leaving the existing saved quad setup intact. The equivalent editor command is:

```powershell
artifacts/temple3d-env/Scripts/python.exe huxin_canals_editor.py --direction art/temple/huxin_canals/direction-volumetric.json
```

The included experiment starts in Hybrid, with fourteen regions around houses,
over the canals and along a passage. It leaves the pavilion centre clear. The
quad layer still supplies distant-building coverage; Volumes only is useful
for inspecting and shaping the new layer independently.

That editor saves and watches the specified file. Embedded editing returns to
the same direction path that its game session is using. Data edits hot-reload;
the first installation of the new renderer still requires restarting the game.

The headless UI checks exercise actual controls, one-step drag undo, timing
constraints, fit-to-building, layer comparison, custom-file saving and F8-paused
live updates:

```powershell
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin_canals_volume_ui -q
```
