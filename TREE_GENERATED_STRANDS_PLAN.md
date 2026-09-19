# Generated willow strands — separate experiment

Status: plan only. Preserve all authored PNGs and the working grid/strip renderer.

## Target

Retain the painted trunk. Generate hanging foliage whose identity, colours, and
lighting stay attached to each strand as it moves. Keep a per-tree choice between
painted foliage and generated foliage, with identical roots, wind, lighting, and
ground sorting. Do not overwrite or automatically migrate existing trees.

## Representation

- Reuse the five authored branch pivots and their layer order.
- Create a modest initial set of curves per cluster (roughly 6–12 to prototype;
  density is an artistic parameter, not a requirement or measured budget).
- Each curve has a stable ID, attachment offset, length, rest curvature, stiffness,
  seed, and depth/layer. Optional artist-drawn guide curves override generated ones.
- Place small leaf shapes or leaf clusters along each curve using seeded spacing,
  size and orientation. Their rest-space sample coordinates never change.
- Start with generated geometry and a small leaf texture/shader. A fullscreen
  fragment shader searching all curves at every pixel is possible but is not the
  first implementation: it makes cost, overlap and debugging harder to control.

## Using the original art

Use each part's alpha as a density/silhouette reference. Estimate strand lengths
from occupied areas; avoid treating every disconnected bright pixel as a leaf.
Attach generated curves near the existing pivots, then fan out to cover that part.
This is an approximation: the flattened artwork cannot reveal hidden structure.

For colour, compare two static options:

1. Sample the original part at each leaf's rest-space location. Resolve empty
   samples to a nearby opaque texel during generation, not every frame.
2. Extract a small local palette and choose stable colours per leaf, preserving
   broad dark/light regions without copying every painted highlight.

The original art contains baked shading. Excessive extra directional contrast can
double-shade it; evaluate this explicitly before adding detailed leaf normals.
No colour lookup should slide across the image as a leaf moves.

## Animation

- Use the existing spatially varying wind and seed controls.
- Bend each curve with a fixed root, broad shared sway, and progressively delayed
  tip movement. Begin with analytic, frame-rate-independent motion.
- Leaves inherit position and orientation from the local curve tangent. Add a
  small seeded turning motion; avoid independently jittering every leaf.
- Use the same evaluated geometry for visible pixels, response data and shadows.
- Consider spring dynamics only if the analytic version cannot produce suitable
  settling or interaction. No spring simulation is needed for the first trial.

## Lighting

- Keep the authored four-channel trunk response maps.
- Give each generated leaf a stable orientation and transmission/thickness value.
  Derive directional response from its current orientation, with a generous
  two-sided fill. Reuse the animated response-texture path introduced for grid trees.
- Add canopy density attenuation for sheltered inner foliage, without bypassing
  world occlusion or turning backlighting into emission.
- Later distinguish solid trunk shadows from attenuated foliage shadows. The
  current cinematic shadow path projects the visible silhouette; transmission
  through the canopy requires a separate caster treatment, not just bright leaves.

## Milestones and comparisons

1. **Static generation:** standalone side-by-side view of reference, grid tree at
   rest, and generated tree. Review silhouette, density, branch concealment and
   palette at native pixels before animation.
2. **Motion:** apply identical breeze/gust presets. Compare row-like artifacts,
   coherent strand movement, idle activity and attachment stability. Retain an
   easy switch back to painted foliage.
3. **Lighting:** evaluate four cardinal directions, moving light, overlapping
   lights and a wall blocking the source. Look for stable leaf shading, readable
   backlighting and no sparkle from regenerated random values.
4. **Game experiment:** expose a separate foliage-renderer choice, preserve
   save/load and undo/redo, release GPU resources when switching/deleting.
5. **Cost and scale:** measure CPU generation/update, GPU draw cost and texture
   memory with 1, 10 and 50 visible trees. Cull offscreen work and simplify distant
   trees only after those measurements identify the bottleneck.

## Inputs needed

Current split art and pivots are enough for the first static experiment. Wood
masks are optional. If generated curves fail to match the willow's structure,
the next useful art input is a handful of root-to-tip guide strokes per part,
on aligned 128x128 reference layers. No individual leaf cutouts are required yet.
