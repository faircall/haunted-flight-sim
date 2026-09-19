# Willow wind trial

Run `python tree_wind_trial.py` from the project directory.

The preview uses the untouched PNGs in `art/split_tree`, showing the reference,
an enlarged animated tree, and the same animation at native pixel size.

## Controls

- **1 / 2 / 3:** still pose / rigid cluster sway / sway with frond bending.
- **W:** cycle still air, breeze, wind, and gusts.
- **R:** reverse wind.
- **N:** compare irregular wind (default) against the original periodic wind.
- **S:** change the deterministic wind seed.
- **G:** compare the new 2D grid against the previous horizontal strips.
- **Space:** pause animation.
- **P:** show attachment pivots.
- **B:** cycle dark, medium, and original beige backgrounds.
- **Esc:** close.

## Rig

`g_tree_animation.py` contains the five pivot positions inferred from the magenta
crosses in `willow_tree_pivotst.png`. All positions use the original 128px canvas:

| Part | Pivot x, y |
| --- | --- |
| top_left | 56, 19 |
| top_right | 77, 12 |
| left_outer | 32, 31 |
| left_inner | 46, 45 |
| right_outer | 102, 43 |

The trunk stays still. Foliage is rendered in the order listed, over the trunk;
this is an initial overlap interpretation to review with the artist.
Slow rotation follows the game's existing wind sampler. Connected textured
strips add increasing sideways bend below each pivot. This is procedural mesh
deformation evaluated on the CPU, not a new shader or a physics simulation.
The existing assets are not modified, and zero wind restores the original pose.

Irregular wind adds smooth random gusts and longer lulls. All clusters share that
wind, with individually tuned exposure, lag, response smoothing, and tip motion.
The inner curtain is more sheltered; outer curtains are freer to bend. Randomness
is seeded and continuous, never a new random displacement every frame. This is
confined to the tree trial and does not change the game's global wind sampler.
Use `--regular` or `--seed 18` for reproducible comparisons. Pixel shimmer from
nearest-neighbour sampling during rotation remains a rendering limitation; this
change reduces fast detail motion but does not add anti-aliasing.

Review the motion at native size, including attachment seams, exposed branches,
and pixel stepping during gusts. The split-layer assembly may differ from the
painted reference because of reconstructed overlapping content.

## In the game

In **Entity** mode, select **willow tree** and place it with the cursor at the
trunk's base. Switch to **Play** to see it in the scene. Select a placed tree to
adjust **Wind response** (0 freezes it in its rest pose) and **Wind seed**.
**Foliage motion** switches between `grid` (default, also for existing trees)
and `strips` for comparison. The grid adds smoothly varying lateral and slight
vertical motion across each foliage cluster. It retains pinned pivots and shared
vertices; it does not change texture filtering or eliminate pixel quantisation.
Global direction, strength, and gust settings come from the existing environment
wind controls. Placement and per-tree settings are saved with the level and
participate in editor undo/redo.

`g_tree_render.py` composes the animated layers to a reusable 160px texture per
tree, including padding for sway. Sorting stays anchored to the trunk, and the
same animated texture feeds scene lighting, occlusion, and cinematic shadows.
Deleted trees release their render targets. The placement ghost uses the static
reference image. Trees currently act as scenery, without physical trunk collision.

## Lighting response

The four `willow_tree_trunk_response_{down,up,left,right}.png` files are read as
luminance and packed at runtime in RGBA order. Their alpha is not coverage: the
original trunk sprite supplies coverage. Changes to these maps reload automatically.

A second animated texture stores directional response in exactly the same pose
as the visible tree. Trunk response comes from the authored maps; foliage uses
stable small regions with a broad two-sided response (minimum 55% direct-light
survival) and mild directional variation. This is a stylised transmission
approximation, not a physical scattering simulation. No wood masks are required
for this first pass; the small woody areas inside foliage layers get leaf shading.

Ambient light and world occlusion retain their existing behaviour. Cast-shadow
transmission/density is a separate future change. The planned generated-strand
alternative is described in `TREE_GENERATED_STRANDS_PLAN.md`.

For a reproducible hidden render:

`python tree_wind_trial.py --capture artifacts/tree-wind/trial.png --time 3`

Add `--mode still` or `--mode rigid` to compare approaches at the same time.
Use `--mesh strips` to capture the previous deformation at that same time.
