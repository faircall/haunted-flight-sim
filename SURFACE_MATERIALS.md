# Procedural surface painting

## Try it

Run `python surface_trial.py` for a separate review map containing grass, dirt,
wood, carpet, ceramic and a short wooden wall. It uses the normal game and editor;
your saved levels are not replaced. Switch the top-left mode to `play` to walk
through the grass. F10 toggles the editor UI.

In any level, choose **tile → Tile edit: materials**:

- **Left drag:** paint continuously, including cells crossed between frames.
- **Brush 1 / 3 / 5:** paint single cells or stamp square sections.
- **Right click:** fill the connected material. On untouched tiles, the old tile
  type and forced-collision boundaries constrain the fill.
- **Detail:** grass coverage / frequency of dirt, grain and wear details.
- **Seed:** another stable arrangement, applied when painting.
- **Soft joins:** rounded, feathered material boundaries. Disable for crisp edges.
  Hard cells also keep their immediate boundary crisp, even beside a soft material.
- **Erase:** remove the procedural finish and restore the original appearance
  and footstep surface.
- **Ctrl+Z:** undo a paint stroke/fill. Normal level saving includes the material
  fields; loading regenerates identical details.

Adjacent painted cells form a continuous region. Adding a cell updates nearby
edges; established details away from those edges do not reshuffle. Triangle tile
shapes also participate. Visual smoothing does not change collision geometry.
Use the existing appearance/collision tools to create walls or change geometry.

## Art and rendering

`prepare_surface_assets.py` extracts 21 reusable details from the concepts:
four grass tufts, six dirt marks/pebbles, three wood grain details, four ceramic
cracks and four wall wear details. The PNG atlas, individual cutouts and provenance
(source path, crop rectangle and root) are in `art/surfaces`. The originals are
untouched. Carpet is procedural; doors remain separate assets for a later pass.

Ground colour uses smooth noise in world coordinates. Boards and ceramic grout
have regular structure, with irregular colour and wear. The detail placement is
seeded in world coordinates, not repeated tile images. Short grass uses static
GPU meshes: a vertex shader bends the tips in wind and away from the player.
Point sampling and the game's native resolution remain in use.

Grass has inexpensive projected contact silhouettes and receives existing floor
lighting. These are **not per-light directional grass shadows**. Grass is currently
short ground decoration, drawn below actors; tall vegetation would need a separate
occlusion/sorting pass. Footprints fade after 5 seconds on grass and 18 on dirt;
they are visual marks, not persistent flattened vegetation. Bullet impacts add
bounded, persistent decals to painted wood, wall and ceramic cells.

Collision, navigation, acoustic zones, rain exposure and puddle metadata remain
unchanged. Material-aware footsteps select the appropriate existing sound surface.

## Cost and checks

Bases and static details are cached in visible 4×4-cell chunks. Edits rebuild only
chunks whose two-cell neighborhood changed. Ordinary frames reuse the textures
and meshes; they do not regenerate sprites or deform vertices on the CPU. New
areas and large fills still incur a one-time generation/upload cost.

Runtime generation uses Pillow and NumPy (both available in this environment).
The review launcher does not require the original concepts; the extractor does.

Run:

```text
python -m unittest test_surfaces test_tile_editor test_tile_collision_override test_audio test_editor_history test_bullet_collision test_editor_ui test_camera_render_alignment -q
python .tree_game_smoke.py --surfaces
```

The hidden real-game check validates wind and proximity deformation separately,
cache reuse, local rebuilding, footprints, editor rendering and map cleanup.
Review captures are written under `artifacts/surfaces/`.
