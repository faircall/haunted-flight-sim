# Independent generated-strand experiment

Run `python tree_strands_trial.py`.

The left panel is the current painted grid tree. The right panel retains the same
trunk but generates its foliage from curves and diamond-shaped leaves. Both are
shown enlarged and at native pixel size, with matching wind and directional-light
settings. The existing game, tree renderer and original PNGs are not changed.

## Controls

- **Space:** pause both trees.
- **R:** rest pose / animated pose.
- **W:** still air, breeze, wind, gusts.
- **L:** unlit artwork, then light from down, up, left or right.
- **D:** sparse / medium / dense foliage (regenerates only the experimental tree).
- **S:** new deterministic seed (regenerates only the experimental tree; updates shared wind seed).
- **V:** show/hide generated stems.
- **B:** background colour.
- **Esc:** close.

## What is implemented

- Original part alpha guides column-based strand coverage and hanging lengths.
- Leaf colours are sampled once from the original part at their rest locations.
- Roots stay fixed; strands sway with shared gusts and independent delayed motion.
- Each leaf has a stable orientation and transmission fill. These move smoothly
  with the strand and feed a separate GPU directional-response pass.
- The same authored trunk maps light both trees. Preview light intensity and
  ambient fill are deliberately simple and identical in both panels.

The generated tree is an approximation, not a pixel-identical reconstruction.
Its thinner hanging forms expose more trunk; density and crown fullness are
starting parameters to evaluate. Nearest-neighbour sampling can still shimmer.
The preview does not simulate world occlusion or cast shadows, and the generated
version has not been added to game placement. Its comparison controls are isolated
from saved levels and the existing standalone wind trial.

## Files

- `g_generated_tree.py`: deterministic generation and CPU curve/leaf poses.
- `tree_strands_trial.py`: comparison preview and rendering.
- `shaders/generated_tree_leaf.fs`: per-leaf response from stable orientations.
- `shaders/tree_compare.fs`: common directional-light display for both versions.

Capture a reproducible preview with:

`python tree_strands_trial.py --capture artifacts/tree-strands/comparison.png --time 3`

Optional flags: `--still`, `--seed 18`, `--density 1.8`, `--light up`.
