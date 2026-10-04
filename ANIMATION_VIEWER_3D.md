# Player animation viewer

Double-click [view_player_animations_3d.cmd](view_player_animations_3d.cmd), or run:

```powershell
python animation_viewer_3d.py
```

It uses the same player GLB, animation samples, GPU skinning shader and movement
cadence as the temple walkthrough. It opens on the walk cycle in a side view.
The smaller inset shows the character at approximately its in-game pixel size,
enlarged 2x. The ground grid moves at the matching travel speed to reveal skating.

After rebuilding the character, close and reopen the viewer and game to load
the new export. **Home** resets the view and playhead; it does not reload assets.

## Controls

| Control | Action |
| --- | --- |
| Idle / Walk / Run buttons, or **1 / 2 / 3** | Select a clip |
| Play / Pause, or **Space** | Toggle playback |
| Frame buttons, or **Left / Right** | Pause and step one exported sample |
| Click/drag the graph or timeline | Pause and scrub to a frame |
| **0.25x / 0.5x / 1x / 2x** | Playback speed |
| Camera buttons | Side, front, back or three-quarter view |
| **Right-drag** over the model | Orbit / tilt the camera |
| **Mouse wheel** over the model | Zoom |
| **B** | Skeleton overlay: green left, orange right |
| **T** | Ankle paths over a full cycle |
| Ground motion button, or **G** | Moving / stationary floor grid |
| Pixel view button, or **P** | Crisp enlarged pixels / higher-resolution geometry |
| **Home** | Reset camera, zoom and playhead |
| **F12** | Save the current view and pose notes |
| **Esc** | Close |

The graph shows **knee bend**: zero means straight. The elbow readout shows the
**inside angle**: a smaller angle means a tighter bend. Frame numbers are the
runtime's imported samples, so they differ from Blender's authoring frames.
The viewer shows each sample directly when scrubbing, without blending it with
the previous clip.

**AIRBORNE / GROUNDED** reports the rendered feet's clearance. The skeleton
overlay includes independent wrists and ankle joints; elbow angles use the
wrist position, so bending the hand does not change the elbow reading.
**Lean** measures the torso and **Pelvis** the pelvis pitch. The hip crossbar
in the skeleton overlay shows the bank and rotation during weight transfer.
Use **Front** to judge the running hand arcs and left/right weight shift;
use **Side** to judge foot recovery and landing.

F12 writes a PNG and matching JSON under `artifacts/animation-viewer-3d/`, including
clip, frame, camera, joint angles and positions. To describe a problem, the clip
and frame number (or that screenshot) are enough to identify the exact pose.

## Viewing in Blender

Open [player_animation_review.blend](photo_asset_pipeline/temple3d/living/player_animation_review.blend).
This separate review file has the player framed from the side, packed textures,
and three scenes: **Idle**, **Walk**, and **Run**. The tree is excluded.

1. Choose **Idle / Walk / Run** from the scene selector in Blender's top bar.
2. Click **Play** in the timeline, or press **Space** with the default keymap.
3. Drag the timeline playhead to inspect individual poses. Each scene already
   has the appropriate looping range and playback rate.
4. Use **Numpad 3** for side view, **Numpad 1** for front view, or middle-mouse
   orbit. **Home** frames the scene if the model gets out of view.

The armature is named `Player / walk` (or `run`, `idle`); selecting it lets you
inspect the bones. The complete source kit, including the willow, remains in
`photo_asset_pipeline/temple3d/living/living_kit.blend`.

Rebuilding the living assets regenerates both files. Use **Save As** under a
different name to keep manual Blender edits.

## Player design and motion

The player is a Chinese man in his early 30s wearing a blue long-sleeved
shirtjacket, white T-shirt, brown trousers and brown leather shoes. The compact
25.65-unit model has a 4.2-unit head, 2,930 authored triangles and a crisp 256x256
atlas. The supplied [face reference](photo_asset_pipeline/temple3d/living/references/face_reference.png)
is preserved and reprojected into a 64x64 front-face panel. The second
[side-angle reference](photo_asset_pipeline/temple3d/living/references/face_reference_2.png)
guides the rounder cranium, compact ears and matched profile skin. A narrower
head, substantial visible neck and lower back hairline follow the portrait silhouette.
A shorter 8.3-unit torso, narrower chest and slimmer shoulders balance the preserved legs. The broader
jaw, nose and full swept dark hair are shaped in 3D. The white tee shares the
torso surface with the jacket; collar undersides stay blue. Faceted surfaces keep the PS1
look while the clothing and blended joints maintain a readable silhouette.

Walk uses 56% contact / 44% recovery at about 0.89 seconds per cycle. The foot
keeps rotating smoothly about the toe through lift-off, then the heel rises
and advances directly into recovery. The ankle path matches its release
velocity instead of sweeping backward in the air. Peak knee bend is about
63 degrees behind the hips, followed by a softly extended landing. Support-knee
flexion, 0.68 units of lateral weight transfer and shoulder counterrotation keep
the step relaxed. Gentle shoulder abduction clears the trousers while keeping
a small inward hand drift beside the jacket.

Select **Walk**, **Side** and **0.25x** to inspect the release in the live viewer;
the moving floor remains synchronized at the slower playback speed. The native
[quarter-speed GIF](artifacts/temple3d-living/walk-side-slow.gif),
[dense toe-off sheet](artifacts/temple3d-living/walk-toeoff-contact.png) and
[speed plot](artifacts/temple3d-living/walk-toeoff-speed.png) show the same
59 imported samples. Early recovery keeps the knee moving above 20.5 game
units/sec and the ankle advancing above 6.8 units/sec.

Run covers 35.29 units per full cycle at 42 units/sec, with a 0.84-second cycle
and broad front-to-back planted travel. When the support ankle passes beneath
its hip, the opposite thigh stays nearly vertical with its heel behind and
about 90 degrees of knee bend. During terminal rear support, that thigh drives
forward to about 80 degrees from down while the knee remains folded. The rear
support leg reaches about 34 degrees without stretching. The shin then opens
through the final descent: native samples progress through roughly 70, 40, 20
and 16 degrees toward the soft 15-degree authored touchdown. Imported contact
samples read 15-16 degrees because the two events fall between different frames.
There is no straight airborne hold. The pelvis vaults over the support foot
with about 17 degrees of knee softness.
The pelvis pitches 6 degrees, the torso leans 3.45-4.35 degrees, and the body
shifts about 1.3 units side to side. The chest banks about 2.24 degrees each way
while the head remains upright. Combined chest tilt, including side bank,
stays below 5 degrees.

The supplied [running reference](https://www.youtube.com/watch?v=jRtlU2QOVQo)
guides the timing at 46-48 seconds. Side frames around 47.581, 47.648 and
47.781 seconds show under-body heel recovery, forward knee drive during rear
support and shin opening right into contact.

The elbow stays near 158 degrees through the backsweep, rear reversal and early
return. It remains above 145 degrees while the returning hand is behind the
hip, then folds to about 68 degrees at the front pump. Slight shoulder abduction
and an outward rear elbow plane keep the hands clear of the thighs. Front hands
move inward at chest height.

Compare the [quarter-speed run](artifacts/temple3d-living/run-side-slow.gif),
[paired-pose sheet](artifacts/temple3d-living/run-paired-contact.png),
[native stride proof](artifacts/temple3d-living/run-stride-proof.png) and
[before/after curves](artifacts/run-v9/source-before-after.png). The imported
frames show the paired leg timing and progressive landing extension; left/right event
phases differ slightly because the runtime uses discrete samples.

Walking feet trace a 0.24-unit lateral swing arc; running recovery uses a smaller
0.10-unit inward arc with little outward knee movement. Contact feet retain
fixed tracks and smooth heel/toe roll. Running lifts both feet between supports,
with about 2.52 units of simultaneous sole clearance and 0.42 units of pelvis
rise. Use **Back / Front** to inspect knee tracking and hand/thigh clearance,
and **Side** for heel recovery, stride length, shin extension and elbow timing.

The moving grid uses the game's 20 / 42 units/sec walk/run speeds. Higher
resolution shows joint deformation and facial detail; the pixel inset shows
the final in-game silhouette.

For a full-game check on the actual 480x270 route, run:

```powershell
python moonlit_water_temple_3d.py --player-review
```

This captures night walking, night running and costume inspection lighting under
`artifacts/temple-camera-trial/`: `player-walk-night-N.png`,
`player-run-night-N.png` and `player-costume-light-N.png`.

## Verification

```powershell
python -m unittest test_animation_viewer_3d test_temple_gait_deck test_temple_living -q
python animation_viewer_3d.py --smoke
python temple_living_smoke.py
```

The viewer smoke renders every clip, overlays, both preview resolutions, the
graph and scale inset. The living-asset check verifies GPU deformation, export
timing, joint lengths, soft walking support, continuous toe-off/early recovery
and locked foot contacts. It also checks one continuous running recovery,
paired support/swing poses, actual travelling stride, progressive contact extension, front elbow
contraction and held elbow extension during the forward return. Actual skinned hand/cuff
surfaces are checked against the trouser geometry in all three clips: minimum
gaps are 0.10 units in idle, 0.14 in walk and 0.30 in run, with no penetration.
The [native measurements](artifacts/temple3d-living/gpu-check.json) keep stance
height error below 0.011 units, sliding below 0.0075 and lateral drift below
0.0015. The 480x270 full-game review verifies walking, running, night lighting
and costume inspection passes.
