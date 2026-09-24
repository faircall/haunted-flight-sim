# Visual development plan: painterly pixels, materials, spaces and film

Research date: 24 September 2026. Planning only; no renderer or gameplay changes.

## Recommendation

Build one small courtyard/interior showcase using the current 480x270 renderer:
varied grass and dirt, a wooden room, ceramic entry, wall segments, one hinged door,
three steps, a pond and a projector. Establish an asset/material format usable by
both 2D and future 3D renderers. Develop a separate door-transition scene before
deciding whether gameplay should move to orthographic 3D.

Working art direction: a weathered Chinese courtyard house drawing on late-Qing /
early-Republic references. Region and architectural details should be chosen more
precisely before a large art batch. Keep foliage muted olive, wood warm brown,
stone cool grey, and strong color accents scarce. Ground texture should be lower
contrast than actors, interactables and trees. Preserve broad readable shapes,
quiet areas, consistent pixel density and restrained moving highlights.

## What the project already has

- `g_main.py`: 480x270 internal rendering with integer-scaled presentation.
- `g_update_and_render.py`: tile grid; artwork still partly selected by tile type.
- `test_tile_collision_override.py`: collision overrides already work independently
  of a tile's original art, including triangle shapes and pathfinding.
- `g_audio.py`: grass/dirt/tile/wood/etc. surfaces, puddle footstep overlays, acoustic
  zones and spatial-audio events. Zone transmission is currently coarse; explicit
  acoustic portals are a future policy, not an implemented feature.
- `g_puzzles.py`: door state, occupied-doorway checks and derived tile blockers;
  door changes invalidate geometry and acoustic revisions.
- `g_height.py`: actor render height/elevation and shadow projection. It is not a
  complete floor-height, stair-navigation or stacked-floor system.
- `g_sequences.py`: triggers, completion events, timed lighting and sound cues,
  music changes. It is not yet a general camera/video cutscene timeline.
- `g_render_order.py`: water-interaction metadata exists. That alone does not
  implement water, mirrors or reflections.

## A. RetroDiffusion workflow and prompts

### Verified capabilities and boundaries

The public catalog lists `rd_pro__painterly` at native dimensions up to 256px,
reference-image support, palette inputs and X/Y tiling controls. The separate
RD Tile family supplies tilesets and variations. Outpainting and seam repair are
also documented. I found no documented dedicated normal-map output. A 512px PNG
may be an enlarged export rather than a 512px native composition.

Sources: [official API examples](https://github.com/Retro-Diffusion/api-examples),
[style catalog](https://raw.githubusercontent.com/Retro-Diffusion/api-examples/main/llms.txt),
[edit tools](https://github.com/Retro-Diffusion/api-examples/blob/main/EDIT_TOOLS.md).
Verify current controls before ordering a batch. These are documented abilities,
not tests of generated tile quality performed during this research pass.

Start with 128x128 patches. On a 16px grid that is an 8x8-cell patch. A 256px patch
is 16x16 cells and nearly the height of our viewport: use it for larger authored
areas once texture density is approved. Dimensions refer to native pixels.

Choose Painterly in the style selector. Use an approved tree as a palette/style
reference, explicitly requesting only the surface material in the output. Use a
shared palette reference where available. Match camera/projection separately:
ground is a straight-on texture; wall/door art is a flat front elevation. Do not
bake a perspective ground plane into a texture that will later be projected again.

For reusable ground patches enable X and Y tiling. For wall strips, horizontal
tiling only. For authored distinctive patches, disable tiling and prepare a
transition collar. A patch that tiles with itself is not guaranteed to join a
different generated patch. Prompts cannot enforce exact seams or construction
dimensions: inspect and repair these after generation.

### Shared surface prompt suffix

Append this to each floor prompt:

> Surface material fills the complete image edge to edge, seen directly from
> above. Small painterly pixel clusters, restrained local contrast, readable broad
> patches, muted natural colors. Soft neutral diffuse illumination with minimal
> directional shading; material color and texture are the focus. Flat texture
> study, without scenery, objects, borders, lettering or perspective convergence.

### 1. Grass — 128x128, X/Y tiling

> An irregular carpet of short grass in an old Chinese courtyard garden. Muted
> olive, moss green and dry straw colors, small groups of bent blades, subtle dark
> earth visible between patches. Uneven growth forms broad soft clusters, with
> sparse quiet areas between denser tufts. Worn and natural, delicate rather than
> spiky, consistent fine blade scale throughout.

Derive variations from an approved base: thin/worn grass; dry verge; damp shaded
grass. Keep large recognizable stones, flowers and tall tufts in separate decals
or sprites, rather than repeating them inside the base texture. Animate only
selected taller tufts with shared world wind; avoid making the entire floor swim.

### 2. Dirt — 128x128, X/Y tiling

> Compacted courtyard earth, warm grey-brown clay with subtle ochre undertones.
> Shallow irregular depressions, tiny embedded stones and faint broken cracks.
> Broad smooth areas crossed by restrained granular patches, naturally uneven
> wear, sparse detail and low contrast, fine ground texture at consistent scale.

Variants: dry compact earth; damp dark earth; gravelly margin. Generate paths as
masked authored patches over the base, rather than baking a path across every
repeated tile. Footprints and leaves are separate decals.

### 3. Wooden floor — 128x128, X/Y tiling

> Worn timber floor in an old Chinese courtyard house, parallel narrow planks
> running vertically through the image. Warm desaturated walnut and ash-brown
> wood, staggered board joints, dark fine seams, subtle longitudinal grain, a few
> restrained knots and gently worn edges. Broad matte plank faces with quiet
> variation; the grain is fine and the board widths remain consistent.

Variants: worn pale boards; smoke-darkened boards. Request an approximately
16px board width, then validate/correct it against the grid. Wetness/polish should
come from a material mask, not bright painted reflections.

### 4. Ceramic floor — 128x128, X/Y tiling

> A floor of square muted celadon-grey ceramic tiles in a restrained regular
> grid. Narrow dark grout, slight differences between neighboring tiles, delicate
> glaze crazing and occasional small chips at edges. Quiet cloudy glaze in each
> tile, subdued moss-grey and blue-grey colors, careful square geometry, aged
> craftsmanship, broad unbroken tile faces.

Variant: subdued terracotta. Target a 16px ceramic unit for the initial test.
If generated grout wanders, use a code-defined grid and keep the generated paint
inside each face; exact joints matter more than preserving every generated seam.

### 5. Wooden wall — 128x64, horizontal tiling

> Front elevation of a weathered timber wall from an old Chinese courtyard house.
> Vertical dark wooden panels between plain structural posts, a restrained upper
> crossbeam and low worn sill. Desaturated brown wood, subtle longitudinal grain,
> slight chips and rain staining near the base. Straight vertical posts and level
> horizontal beams, consistent construction scale. Flat front-facing material
> study, soft neutral illumination, fine painterly pixel clusters, minimal baked
> shadows. Wall surface fills the image; no ground, roof, doors, lettering or
> perspective convergence.

Separate outputs: post/end cap; narrow sill; plain infill. Use these to construct
corners and openings deterministically. Keep the footprint and visible wall face
distinct; do not use the whole painted face as a collision rectangle.

### 6. Door leaf — 32x64 initially, no tiling

> One closed rectangular wooden door leaf from an old Chinese courtyard house,
> seen exactly from the front. Aged dark timber, two recessed rectangular panels,
> simple horizontal rails and one small dark iron ring handle toward the right
> edge. Plain straight left edge for a hinge attachment. Warm muted brown and
> restrained iron-grey detail, soft neutral illumination, crisp painterly pixel
> clusters. Entire leaf visible with a small margin, isolated on a uniform bright
> magenta background. No frame, floor, text, perspective or cast shadow.

Use the background-removal control and verify real alpha. Test this size beside
the player before generating the final family; exact leaf dimensions can be
adjusted without changing the asset strategy.

### 7. Matching door frame — 64x80 initially, no tiling

> A simple freestanding timber doorway frame matching the supplied wooden door
> reference. Exact front elevation, two straight posts and one worn horizontal
> lintel, an empty rectangular opening, simple narrow threshold. Same aged dark
> timber, muted palette and painterly pixel detail. Entire frame visible on a
> uniform bright magenta background; the empty opening also shows this background.
> Soft neutral illumination, no door leaf, ground, text or cast shadow.

Generate separately, then fit the opening deterministically to the approved leaf.
Request a matching reverse side via an edit/reference pass only if the camera can
see it. Small side-edge texture strips can be derived from the approved wood.

### 8. Door animation concept — optional motion reference

> Locked camera. The existing door leaf slowly rotates inward about its fixed
> left vertical hinge. It begins shut, sticks briefly, then creaks open to a dark
> opening. Preserve the frame, hinge location, rectangular proportions, wood grain
> and handle exactly. Only the door leaf moves.

Treat generated animation as a timing reference. Final production animation should
rotate the same texture/geometry, or use frames rendered from that same setup;
independent generated frames will not guarantee stable grain or hinges.

### First batch and acceptance checks

Generate two candidates each for the six main material categories, select one
direction, then derive variations and frame pieces. First approve a 3x3 repeated
preview and a 128px patch beside the player, tree and flashlight. Check native
pixel scale, seam continuity, quiet ground contrast and silhouette readability.
Keep all accepted surfaces under the same neutral and four-direction light tests.

## B. Large sections with unchanged grid semantics

Use **stamps**: an authored image plus its placement metadata. An image spanning
8x8 cells can be placed in one editor action. It can reference atlas subrectangles
per cell, or render as one ground patch while the underlying cells remain intact.
The player still walks on those cells; the image need not look like a grid.

Separate records:

```
Visual: atlas, source rectangle, local offset, layer, material, stable variant seed
Gameplay cell: collision shape, surface, acoustic zone, height/level (when added)
Stamp: dimensions, visual references, optional explicit gameplay metadata, version
```

Default to visual-only placement. Offer an explicit geometry/material stamp mode
with a collision/audio overlay preview. Preserve authored collision overrides,
doorway state and acoustic zones unless the author chooses to replace them.

Implementation sequence:

1. Add an optional visual asset/source rectangle while keeping legacy tile-type
   rendering as fallback. Painting art must not silently select a new blocker type.
2. Add rectangular stamp brush, preview, undo/redo as one transaction, serialization
   and deterministic seeds. Retain individual cell editing after placement.
3. Assign per-cell surface IDs: grass, dirt, wood, tile. Puddles add the existing
   footstep overlay without discarding the underlying surface.
4. Use a small seamless base set, several authored patches, and sparse decals.
   Preserve patch interiors; only edges need compatible transition masks/tiles.
5. Mark edge families or use a shared neutral edge collar for multi-patch joining.
   Never shuffle every sliced tile independently: that destroys authored structure.
6. Batch static floor geometry or cache chunks. Retain enough subdivisions for
   existing per-tile lighting/occlusion; do not flatten a whole room into one
   uniformly lit billboard.

For walls, stamps place base footprints plus segmented visible faces/caps; they
must still sort/occlude correctly against actors. Door openings remain interactive
objects with explicit links, not merely empty pixels in a large wall painting.

Tests: old levels load unchanged; visual-only placement leaves collision/audio
identical; surfaces sound correct; doors still invalidate visibility/acoustics;
undo/save/load reproduce the stamp; variation is stable across runs; seams survive
camera movement and moving light.

## Material maps and lighting

A normal map records the direction a surface faces at each pixel; it does not
create geometry. Ground and walls can benefit without moving the game to 3D.
I would not depend on prompting an image model to paint a technically correct RGB
normal map. Its colors and alignment need to encode measurements, not aesthetics.

Preferred workflow:

1. Approve the painted color image.
2. Define material IDs, seam masks and a restrained height field: depressed grout,
   slightly rounded plank edges, shallow ground clumps. Painted bright colors are
   not automatically high points, so do not simply turn luminance into height.
3. Derive normals from that field, or bake from a simple Blender proxy. Blender
   supports normal and roughness baking: [official baking documentation](https://docs.blender.org/manual/id/3.3/render/cycles/baking.html).
4. Store roughness/reflection masks separately. Matte wood, glazed tile and wet
   earth can share a color palette but respond differently to moving light.
5. Keep maps aligned at native resolution; treat them as linear data, document
   tangent axes/green-channel convention, and transform normals when art rotates.
6. Use weak, broad normal response first. Strong per-pixel highlights can create
   shimmer or make painted grass resemble crumpled metal. Retain the trees' existing
   two-sided foliage response and authored wood-response approach.

For later 3D use, a flat normal is relative to the surface tangent frame: floor
normals point up in world space, wall normals sideways. Do not reuse the same
world normal convention blindly for both.

## C and D. Conservative rendering versus actual 3D

| Area | Extend current 2D | Orthographic 3D cards/surfaces |
| --- | --- | --- |
| Painted pixel composition | Direct control | Needs projection/texel-density calibration |
| Floors/walls | Layered faces, caps, explicit height data | Horizontal floor surfaces and vertical wall planes |
| Occlusion | Segment sorting, masks or a custom depth buffer | Depth buffer helps opaque/cutout geometry |
| Door hinge | Project a leaf quad or use baked frames | Direct 3D hinge with thin edge/back faces |
| Steps | Art + height interpolation + occlusion | Treads/risers are easy geometry; navigation still needs height rules |
| Reflections | Convincing controlled approximations | More coherent reflected-camera view, extra render cost |
| Camera freedom | Keep fixed view | More freedom, but cards expose missing side/back art |
| Migration | Incremental | Rendering, picking, lighting, fog and editor integration work |

### Conservative path

Model a wall as a ground footprint, visible vertical face, top cap and optional
foreground trim. Split long walls into sortable segments; use masks or depth
metadata where a single sort key cannot express an overlap. Add foot/contact
shadows, top-edge highlights and subtle material normals.

For doors, separate frame, leaf, reverse, thin edge and hinge coordinate. Project
the four corners of a rotating leaf into the fixed 2D view, or bake 8-12 consistent
frames in Blender. Keep one authoritative opening progress. A first implementation
can retain a fixed doorway blocker until the leaf is sufficiently clear; use the
same threshold for collision, visibility and sound revision changes. Preserve the
occupied-doorway close guard. A physically swinging collision leaf is a separate
feature; it is not required for the visual improvement.

For walkable stairs, retain XY navigation and introduce a surface-height query
over a ramp footprint. Render actors at the corresponding elevation, with drawn
treads and a step-aware foot/contact shadow. Logical floor levels gate adjacency,
line of sight and bullet interactions where necessary. The current render-height
field alone is insufficient. Start without overlapping floors or walking under
stairs; those require multiple walkable layers and broader gameplay changes.

### Bounded 3D experiment

An orthographic camera plus ground-parallel and upright quads is entirely viable.
Walls should be oriented in world space; actors can be camera-facing or vertical
axis billboards. A thin door needs edge/back faces when opened. Existing art often
contains its own projection: pasting it onto a tilted card can foreshorten it twice.
Orthographic projection preserves size with distance, but does not automatically
align texture pixels or remove diagonal shimmer. See [Blender camera documentation](https://docs.blender.org/manual/nl/5.2/render/cameras.html).

Make a standalone scene using the same textures and logical grid: floor, L-shaped
wall, door, three steps, pond, one tree and one actor. Match the current camera and
480x270 target. Start with fixed yaw/pitch, stable nearest sampling and calibrated
world-unit/pixel density. Test slow camera movement and diagonal silhouettes.

Keep the gameplay-to-render boundary explicit: XY positions, collider footprints,
surface/zone IDs and door states feed either renderer. Screen picking must invert
the new projection; visibility, shadows, transparency, lights and fog need audited
adapters. Existing movement/pathfinding can survive a single-ground-plane test,
but true overlapping storeys or height-dependent combat are not render-only work.

Adopt gameplay 3D only if the comparison preserves the look, shows a clear benefit
for depth/stairs/reflections, and stays within a measured frame budget. Otherwise
retain the 2D renderer and reuse the 3D work for cutscenes and offline sprite bakes.

## E. Water, puddles, polished floors and reflective walls

Start with a shallow pond and puddles, then glazed ceramic, then one wall mirror.

### Current-renderer prototype

- Give each reflective region a mask, plane height/orientation, roughness and tint.
- Render selected world items into a separate reflection target using their ground
  anchors and approximate height. A fixed-camera ground reflection can mirror
  upright sprites below their contact points; clip the result to water polygons.
- Reflect the world before UI and screen effects. Background terrain, occlusion,
  submerged objects and alternate sprite views need explicit handling; a flipped
  final screen is not a general solution.
- Share one reflection target among coplanar puddles. Pool different planes;
  avoid one full-scene render per puddle or recursive mirrors.
- Add low-amplitude coherent distortion, dark tint, view-dependent weighting and
  roughness filtering. Retain the final low-resolution pixel grid. Glazed floors
  should mostly show soft light streaks; still water can reveal clear silhouettes.
- Add shore contact shading, restrained ripple rings at footsteps, and pond depth
  color. Gameplay declares whether water is shallow/walkable or blocks movement.
  The existing puddle audio overlay supplies the sound hook.

A 2D wall mirror requires reflection across its wall line and correct drawing
order, not a universal horizontal flip. Start with one camera-aligned orientation;
missing reverse-facing character art may need alternate sprites or a deliberately
soft reflection. This is harder than a puddle.

### 3D experiment

Reflect the camera across the water/wall plane and render a clipped view into a
texture. Use roughness and distortion to integrate it with the art. This gives
more coherent geometry, but still needs billboard-facing rules, clipping, alpha
handling and a render budget. A normal map alone cannot provide reflected scenery.

## Cutscenes and the door transition

Use three complementary forms:

1. In-engine choreography for continuity: camera, actor poses, lights, dialogue,
   sound cues and temporary input control.
2. Python-authored Blender scenes for controlled cinematic shots, rendered to the
   game's target resolution/palette or slightly supersampled then deliberately
   reduced. Keep the `.blend`, script, camera transform and export settings.
3. Archival/altered film played as an in-world projector texture or a narrative cut.

Generative video is useful for storyboard motion, atmosphere and rough timing.
Rebuilding in Blender is a guided reconstruction, not an automatic reliable
video-to-scene conversion. Choose an approved keyframe, camera position and a few
key poses; recreate the minimum geometry and animate it deterministically. This
allows exact reshoots and changes to timing/resolution without video-model drift.

### First cinematic: a 4-6-second door transition

- Fixed front-facing shot; frame and leaf use the approved game texture family.
- Brief handle movement, resistance, then a slow hinge rotation.
- A thin strip of moving light reveals the edge; darkness remains beyond.
- Creak and latch cues follow hinge motion; transition completes into the next room.
- Bake the clip first. Optional real-time 3D playback can follow if variants matter.

This delivers the Resident Evil-style effect without migrating gameplay rendering.
The cinematic camera can use a little perspective even if gameplay stays fixed 2D.

Add a small cutscene timeline above the current sequence events: camera/pose/light/
audio/video tracks, skip handling, input ownership, restoration and one completion
transaction. Skipping must apply the final door/room state exactly once and stop
temporary audio. Test skipping, replaying and saving/loading at allowed checkpoints.
For longer footage use streamed decoding and a clock tied to playback; short door
clips can be packed frame sequences. Avoid holding entire long films in VRAM.

## Historical footage and music

Moving-image candidates will come from the late nineteenth/early twentieth century,
not ancient China. For earlier nineteenth-century imagery, use verified photographs
or prints and label any animated reconstruction appropriately.

### Concrete starting points

| Candidate | Why it fits | What is established |
| --- | --- | --- |
| [Nankin Road, Shanghai, c.1900-1901 — BFI](https://www.youtube.com/watch?v=Z9ls4mV51Yk) | Crowds, shopfronts, street movement for a short projector loop | Authentic archival candidate; commercial reuse of this supplied copy not verified |
| [China on Film — BFI](https://replay.bfi.org.uk/collection/412) | Beijing 1910, Hangzhou canals 1925 and other travelogue/home-movie leads | Excellent catalog; viewing access is not a reuse grant |
| [Shanghai canal stereograph, 1901 — LOC](https://www.loc.gov/item/2019634396/) | Boats/water scene for a lantern slide or controlled parallax reconstruction | Item states no known publication restrictions; this is a photograph, not film |
| [Nankin Road bazaars, 1901 — LOC](https://www.loc.gov/item/2019634519/) | A second still for slide changes and architectural reference | Item states no known publication restrictions |
| [Chinese recording, part 6, 1903 — LOC](https://www.loc.gov/item/jukebox-312589/) | Vocal/instrumental ensemble with period recording character | Cataloged 7 August 1903; recording location listed as Philadelphia, unconfirmed |
| [LOC's early Chinese-recording discussion](https://blogs.loc.gov/folklife/2017/01/music-chinese-new-year/) | More 1902/1903 listening leads and performance context | Period Chinese music, not necessarily recordings made in China |

The BFI upload calls Nankin Road 1901, while its Replay entry dates it August 1900;
retain that uncertainty in asset metadata. I have not established an unrestricted
commercial download for the film candidates in this pass.

Prefer pre-1923 published recordings as a US-rights starting pool: their recording
protection ended under the Music Modernization Act, but composition/lyrics and
other territories still need item-level checks. Do not assume 1930s records are
free because ordinary films or photographs of similar age might be. The US rule
for recordings first published in 1923-1946 is generally 100 years from publication.
Sources: [US Copyright Office](https://www.copyright.gov/music-modernization/faq.html),
[LOC Jukebox rights](https://www.loc.gov/collections/national-jukebox/about-this-collection/rights-and-access/).

Track the source work, exact recording/scan, dates, creator, rights statement,
territories, credit and modifications separately. A new soundtrack, translation
or creative restoration may have separate rights; archive supply terms also
matter. Australia's NFSA explains the distinction between archive custody, rights
and access, including fees for supplying public-domain material:
[NFSA rights and usage](https://www.nfsa.gov.au/industry/rights-usage).

### Sound and projector treatment

Keep original recordings and creative processed versions separate. Make dry music,
surface noise, motor hum and room sound separate controllable layers. Start with
recognizable period music, then introduce slight speed drift, a repeated groove,
a missing phrase or a room-dependent reverb tail. Retain enough fidelity to hear
the performance; avoid burying it under generic noise. If a desired 1930s recording
cannot be cleared, commission an original period-inspired piece and own that master.

For the projector: a low-resolution video texture on the wall, subtle gate weave,
limited shutter modulation, dust and a soft beam in the existing fog treatment.
Use the image's average brightness to drive a restrained local light. Character
silhouettes can interrupt the beam or screen image. Offer reduced flicker.

Horror idea: a normal street loop repeats, but one shutter opens only on the third
pass; later the projected doorway matches the room's actual doorway. Build the
alteration as a controlled separate layer or short generated insert. Preserve the
untouched source, match grain and frame cadence, and credit the result as altered
historical material rather than presenting invented events as documentary footage.

## Order of work and decision gates

1. **Art proof:** six material families at native size, one shared palette, repeated
   previews and player/tree comparisons. Approve visual density before mass generation.
2. **Stamp/editor support:** visuals separated from collision/sound semantics;
   rectangular placement, undo, save/load and edge handling.
3. **Materials and construction:** mild normals/roughness, segmented wall kit,
   deterministic hinged door, one walkable stair with single-layer height rules.
4. **Reflections:** one pond and ceramic floor patch; profile render cost and inspect
   occlusion. Add one controlled wall mirror after the ground reflection works.
5. **Cinematic slice:** scripted/baked door transition plus a skippable timeline.
   In parallel as a workstream, shortlist and verify one archival clip and recording.
6. **Optional gameplay 3D comparison:** use the same small scene and textures;
   retain only if quality, interaction alignment and measured costs justify it.

The default destination is richer 2D with clear materials and authored spaces.
Blender and small 3D scenes remain useful even if the gameplay renderer never changes.
