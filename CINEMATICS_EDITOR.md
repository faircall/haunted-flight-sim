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

### Move fog spawn layouts

The **Fog placement** tab is the primary workspace. Choose **Nearby**, **Middle**
or **Distant**, then drag the coloured **X/Y/Z handles** in the image, type
coordinates, or use the 0.25-metre nudge buttons. These move the selected bank's
whole spawn layout; the particles keep their individual, staggered lifetimes.
**Spread / size** scales that layout and its clouds. **Opacity multiplier**
changes that bank's transparency. **Reset this bank** restores only its placement,
size and opacity, leaving the timeline intact. These controls edit banks, rather
than individual particle cards or the architecture.

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
puzzle launcher read the same file at startup or **Home** reset; no asset rebuild
is needed. **Ctrl+Z / Ctrl+Y** undo and redo; one drag is one undo step.
**Reload / Ctrl+O** reads the saved values and can itself be undone.
**Restore V17 defaults** restores the approved 5-second build, 1-second blend
and 40-second clearing timeline in the editor; saving makes it permanent.

**Return / exit**, F2 or Escape offers **Save and return**, **Discard and return**,
or **Keep editing** if changes are unsaved. When opened from play, returning resumes
at the chosen playhead without replaying sound cues or consuming another object.
The player's position is retained. F8 provides the existing Codex selection mode
and records the selected timeline point, time and fog bank with the selection.

Focused checks:

```powershell
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin_canals_direction test_huxin_canals_editor -q
artifacts/temple3d-env/Scripts/python.exe huxin_canals_editor_review.py
```

The native review is hidden and muted and saves screenshots and its report under
`artifacts/huxin-canals-editor/`. It edits an isolated temporary direction file,
leaving the actual game's saved direction unchanged.
The first editor pass passed 16 new CPU checks and the 50 existing focused
Canals checks. Native verification exercised 37 widget actions, seven repeated
forward/backward seeks and 18 direct/reflected fog passes. Repeated seeks were
pixel-identical; fog placement, saved gameplay, selection and embedded return
were verified with the actual renderer.
