# New willow assets: review pass

In the game's **entity editor**, choose **willow a**, **willow b**, or **willow c**
and place them like the existing **willow tree**. Wind response, seed and grid/strip
motion controls work for each. They use the existing GPU deformation, lighting,
sorting and shadow pipelines. The original willow and generated-strand trial
remain separate. Existing saved levels are not modified.

## Prepared packs

- `art/trees/willow_a/`: 7 moving sections, root (64,123).
- `art/trees/willow_b/`: 6 moving sections, root (83,123).
- `art/trees/willow_c/`: 7 moving sections, root (82,123).

Each pack contains a transparent reference, stationary trunk/branches, transparent
foliage layers on aligned 128x128 canvases, a magenta pivot overlay, per-layer wood
masks, a combined wood mask, four draft directional wood-response maps, and
`tree.json` with pivots, bounds and per-section movement settings.

Willow A's source was actually 512x512; it was reduced to 128x128 using nearest
sampling. The beige background was removed by a small color-distance threshold,
including enclosed spaces between branches. Foreground colors are retained.
Recompositing the prepared layers exactly reproduces each cleaned reference.

## Draft decisions to review

Wood extraction uses hand-sketched branch paths plus palette classification.
Identified wood stays on the trunk layer, so the foliage wood masks are currently
black by construction. These masks are authoring outputs; the runtime uses the
wood/foliage layer separation, rather than sampling mixed-material masks.

Small inferred branch backing is added only under existing opaque foliage to
reduce gaps in motion. Hidden branches cannot be recovered exactly from a flat
image. Watch for detached tips, isolated stationary pixels, and split boundaries
that become visible at strong wind settings. Wind amplitudes start conservatively.

Lighting maps approximate rounded wood using the wood silhouette, not recovered
3D normals. They are deliberately drafts. Leaves retain the existing stable
random orientation and two-sided light response. Check exposed trunk lighting
from all four sides, especially branch junctions.

## Refining and reproducing

Edit each `tree.json` for movement: `pivot`, `bounds`, `stiffness`, `exposure`,
`lag`, `response`, `flutter`, and `bend_gain`. Movement definitions reload while
running. Restart after editing layer PNGs or root anchors. The four response maps
retain the existing automatic reload behavior.

`prepare_tree_assets.py` stores the initial split guides and response-map recipe.
Run `python prepare_tree_assets.py` to rebuild from `artdev/unprocessed_trees/`.
**Rebuilding overwrites these generated packs**, including hand-edited JSON/maps;
preserve refinements or update the recipe first. Source images are never modified.

Review artifacts:

- `artifacts/tree-assets/prepared.png`: transparent artwork and isolated wood.
- `artifacts/tree-assets/game-review-1.png`: all three rendered in-game.

Validation:

```powershell
python -m unittest test_tree_assets test_tree_game test_tree_animation test_entity_self_shadow
python .tree_game_smoke.py --variants
```

Checks cover asset reconstruction, mask sizes, pivot/bounds validity, editor types,
root alignment, exact calm GPU output, wind movement, and removing all variants.
The original willow's GPU comparison benchmark also passes unchanged.
