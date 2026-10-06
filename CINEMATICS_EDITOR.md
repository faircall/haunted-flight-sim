# Intro cinematics editor

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

**Mouse look** controls whether the player can look around during that shot.
**View: Interior/Exterior** controls first-person body visibility. Moving a camera
out of the cabin through flight or position fields selects the exterior view and
a fixed camera automatically; these buttons remain available for explicit choices.

## Preview and edit the timeline

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
