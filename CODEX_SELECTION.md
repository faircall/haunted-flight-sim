# Point out a 3D object to Codex

Press **F8** in a supported 3D scene or editor, then click the object you want
to discuss. The scene, editor controls and scene audio pause while selection is
active. Selection identifies objects; it does not move them or edit the scene.

- **Click:** select one object.
- **Shift + click:** add an object, or remove one already selected.
- **Backspace:** clear the selection.
- **F8 or Esc:** resume. The last selection remains available to Codex.

The overlay shows the selected object and its label. Editor sidebars and the
selection controls are excluded from picking. An object made from several
rendered components retains its authored identity.

Selections are saved atomically to **`codex_selection.json` in the repository
root**. Nothing is written until selection mode is enabled. This is a transient
local handoff file, separate from scene documents and saved game progress. A
later selection replaces the handoff; resuming keeps the last selected records.

The file includes the scene and source file, object ID and asset path, hit point
and normal, displayed transform/bounds, camera and viewport, and available
authored object data and scene context. In the placement editor, context also
identifies the scene document and its current revision, including unsaved edits.

After pointing, tell Codex what to change. Codex can read the root JSON file
directly, or print it with:

```powershell
python codex_selection.py
```

Supported views are the main 3D temple game and placement editor, car intro and
cinematics editor, temple interior, bamboo grove, rockery, and the current
`huxin_canals` scene. The preserved original lake/Moon files and frozen flooded
canals version are unchanged and have not been newly integrated.

Static objects use the actual rendered mesh triangles and transforms. Animated
GPU characters use explicitly labelled approximate standing bounds; wind-bent
willows identify their resting mesh approximation. Merged geometry resolves to
an authored object where metadata exists, otherwise it reports the specific
surface hit rather than claiming the entire landscape is one editable object.
Transparent car glass is passed through so the occupants and interior can be
selected. Render-only reflections and discarded geometry are excluded.
During the canal transformation, selection records the more visible environment
and includes the blend amount in the saved context.

Automated integration reviews use hidden windows and muted audio. The temple
review exercises play, selection, the editor, sidebar rejection and resuming
play while checking that selection clicks cannot fire, interact, save, drag or
delete. Run its CPU checks or optional native review with:

```powershell
$env:HAUNTED_MUTE_AUDIO = '1'
python -m unittest test_temple_selection_integration -v
python test_temple_selection_integration.py --native
```

Use the project's Raylib environment (`artifacts/temple3d-env/Scripts/python.exe`)
if the active Python does not contain the game dependencies. Native review
images and reports are written under `artifacts/codex_selection/`.
