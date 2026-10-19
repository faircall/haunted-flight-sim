# Temple: 3D exploration and level editing

```powershell
python moonlit_water_temple_3d.py
```

Or double-click `play_temple_3d.cmd`. The launcher selects the local **Raylib
5.5.0.4** environment before importing the renderer. On a new checkout, run
`python setup_temple_3d.py` once. This environment overrides Raylib locally and
reuses the already-installed Python game dependencies; the original global
Raylib 5.0 installation and native C comparison are unchanged.

## Separate lake pavilion / The Still Lake

Double-click [play_huxin.cmd](play_huxin.cmd), or run:

```powershell
python moonlit_water_temple_3d.py --huxin
```

This separate, enemy-free scene takes its mood from **湖心亭看雪** and the
supplied pavilion photograph: an open, double-eaved pavilion reached by a
narrow stone causeway. There is no snow. Evening cloud, low drifting lake mist,
dark Chinese pines and layered distant mountains surround the small pools of
lantern light. The temple is deliberately absent at this stage.

The pavilion has six timber columns, curved grey tiled roofs, bracket sets,
continuous wooden roof undersides, a painted ceiling and a **湖心亭** plaque.
Two peripheral benches leave the middle open. The causeway bends gently over
the water and continues directly into a gently rising shore path. A matching
pair of stone lamps frames the entrance. Staggered, chipped paving settles
into soil and moss, with reeds and low plants softening the bank. The deck
sits 0.325m above the lake, with its stone foundation mostly submerged.

**W/S** walk forwards/backwards, **A/D** turn, **Shift** runs. **1–9** select
authored shots; **0** restores automatic fixed-camera selection. **F** toggles
free camera (mouse + WASD, Q/E height). **L** toggles inspection daylight,
**Tab** hides the player, **H** hides the HUD, **Home** resets, **F12** captures.

**F3** displays the reserved assembly areas: a **4.5m diameter** clear floor
for the future puzzle and an **18–52m radius** ring of open water for the
surrounding structure. Only the approach crosses that ring. These dimensions
are editable in [g_huxin.py](g_huxin.py); the machine-readable layout is
[assembly_space.json](art/temple/huxin/assembly_space.json). Neither the puzzle
nor surrounding structure has been implemented. There is no scene handoff yet.

The live renderer uses 640×360 output, small painted material tiles, seven-sample
height fog and a planar geometry reflection with gentle ripple distortion.
Sky, vegetation, architecture and the moving player reflect in the lake.
Foliage alpha thresholds compensate for distant mipmaps so the trees retain
their silhouettes. Reflections, lighting and weather are runtime effects;
the Blender file contains the editable environment geometry and packed textures.

- [Packed Blender source](art/temple/huxin/huxin_pavilion.blend)
- [Geometry builder](build_huxin.py), [texture packer](prepare_huxin.py)
- [Playable scene](huxin_viewer.py), [layout and collision](g_huxin.py)
- [Review contact sheet](artifacts/huxin/lake-review.png)
- [Accelerated walkthrough](artifacts/huxin/lake-walkthrough.gif)

Built-in ImageGen supplied the new [wood, roof, stone and paint source sheet](art/temple/huxin/materials_source.png).
The [exact prompt](art/temple/huxin/materials_prompt.txt) and
[runtime material atlas](art/temple/huxin/materials.png) are saved with the asset.
Remaining material colours reuse the bamboo palette; the pine models reuse the
intro's Chinese pines. Chinese lettering is rendered from a local font.

```powershell
python prepare_huxin.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_huxin.py
python moonlit_water_temple_3d.py --huxin-review
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin -v
```

The scene and review open no audio device. Nine tests cover bidirectional
traversal, water and prop collision, actual exported floor support, roof
undersides, terrain-aware camera sightlines, grounded paired lamps, reserved
space and embedded asset portability.
The native review captures all nine shots, the roof from above and below, an
assembly overview, four close shore views and an 89-frame walkthrough through
seven camera zones.
Captures and measured timings are written under `artifacts/huxin/`.

## Separate rockery maze / The Hollow Garden

Double-click [play_rockery.cmd](play_rockery.cmd), or run:

```powershell
python moonlit_water_temple_3d.py --rockery
```

**The Hollow Garden / 叠石迷园** is an independent, empty survival-horror
prototype inspired by the rockery of **狮子林**. Narrow, roofed limestone
passages connect looping paths, a concealed grotto, a blind viewing aperture
and broader courts. A staircase leads onto a second route that actually
crosses above the lower passages. Beyond the last constriction, the space
opens around a hexagonal pavilion, a dark lily pond and a covered garden
gallery. It does not read or write gameplay saves or connect to the intro.

The spatial rhythm follows **初极狭，才通人。复行数十步，豁然开朗。**:
constriction, uncertain turns, glimpses of places that cannot be reached
directly, then an unexpected opening. The porous Taihu limestone has real
holes and cave roofs. Ferns, muted white blossoms, occluded warm lamps and
cool drifting height fog keep the garden inhabited-looking but empty.
The layout is an interpretation, not a reconstruction of Lion Grove.
Reference: [Suzhou Gardens' account of the Lion Grove rockery](https://ylj.suzhou.gov.cn/szsylj/sjyc/201905/767dcf47765b40549969f1a6989c689c.shtml).

| Control | Action |
| --- | --- |
| W / S, A / D | Walk forward/back; turn left/right |
| Shift | Run |
| 1–9 / [ / ] | Select the first nine cameras / cycle all 23 |
| 0 | Restore automatic fixed camera selection |
| F | Free camera: mouse, WASD, Q/E for height |
| L | Toggle daylight |
| M | Show the layout plan; jade lower paths, ochre upper route |
| F3 | Show potential encounter areas and spawn markers |
| Tab / H | Toggle player / controls overlay |
| Home / F12 / Esc | Reset / capture / exit |

There are **no enemies**. Four disabled encounter studies in
[encounters.json](art/temple/rockery/encounters.json) describe possible spawn
positions, exits and fighting space: the four-exit echo court, the two-exit
grotto, the final pavilion court and a single-file throat. The narrowest
passages are roughly 1.5–1.6 m across; the courts provide room to maneuver.
The markers are design notes, not an active encounter system.

The 640×360 rendering and 128px painted material tiles retain the established
Dreamcast-inspired treatment. Roughly 1.1 million triangles across the whole
garden preserve the folded silhouettes and genuine perforations; this is a
modern density budget rather than a hardware-accurate console limit. Mirrored
triplanar stone textures avoid UV seams. A baked distance field from the same
carved geometry supplies lamp occlusion and visibility checks for 23 fixed
camera positions. A camera can pan from its fixed position at a bend. The
pond uses stylized ripples and reflected colour, not a second scene render.

The stairs and upper path use hand-cut limestone treads with varied rises and
runs, crooked noses, chipped corners and shallow worn hollows. Low rock
shoulders replace the balusters. Their colour and texture scale match the
rockery. The upper route curves through its joins, and the corridor walls
flare and fold away from the floor instead of forming square vertical slots.
Navigation, carved rock and exported floors share the same centerlines and
stair profiles; the mild surface wear does not shake the player camera.
Camera visibility also ray-tests the exported stair mesh and its rough edges.

Source files:

- [Packed Blender scene](art/temple/rockery/hollow_garden.blend)
- [Blender geometry builder](build_rockery.py)
- [Rock carving and texture packing](prepare_rockery.py)
- [Navigation, layout, cameras and encounter notes](g_rockery.py)
- [Camera visibility director](rockery_camera.py)
- [Playable viewer](rockery_viewer.py)

Built-in ImageGen supplied the original [limestone and pebble material sheet](art/temple/rockery/materials_source.png).
Its [exact prompt](art/temple/rockery/materials_prompt.txt) is saved alongside
the [runtime atlas](art/temple/rockery/materials.png). Timber, roof tile and
plant colours reuse the bamboo scene's palette. Chinese inscriptions are
rendered with a local Chinese font by the texture packer.

```powershell
python prepare_rockery.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_rockery.py
python moonlit_water_temple_3d.py --rockery-review
python -m unittest test_rockery
```

The silent native review saves sixteen compositions, a six-view stair/corridor study,
an encounter/layout study, an animated walkthrough and a timing report under
`artifacts/rockery/`.
It traverses all five route groups with the actual player controller. Tests
also walk every route in reverse, check the baked cave clearance and camera
sightlines, compare collision heights against the exported stair/floor
triangles, verify the genuine over/under crossing and check that encounter
spawns are clear. The scene opens no audio device, including during reviews.

## Separate bamboo grove and Chan room

Double-click [play_bamboo_grove.cmd](play_bamboo_grove.cmd), or run:

```powershell
python moonlit_water_temple_3d.py --bamboo
```

The **Bamboo Hermitage / 竹隐禅房** is a separate, playable art prototype. A
winding stone path passes between tall bamboo, then opens onto a small Chan
meditation room concealed among white camellias. The room includes a veranda,
open wooden latticework, a round rear window, an ink scroll, tea table, books,
incense and an empty meditation cushion. It has its own collision and camera
layout and does not read or write the gameplay save or connect to the intro.

The art direction follows Chang Jian's **曲径通幽处，禅房花木深**: reveal the
destination gradually through the path and planting. Warm lamps in an empty
room, slowly moving bamboo and drifting ground mist supply the unease.
Reference notes: [the poem and commentary from Lingyin Temple](https://www.lingyinsi.org/detail_17990.html),
and [moso bamboo at Kew](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:415998-1)
for the grove's tall, jointed culm silhouettes.

| Control | Action |
| --- | --- |
| W / S, A / D | Walk forward/back; turn left/right |
| Shift | Run |
| 1–8 / 0 | Select a camera / restore automatic cameras |
| F | Free camera: mouse, WASD, Q/E for height |
| L | Toggle daylight |
| Tab / H | Toggle player / controls overlay |
| Home / F12 / Esc | Reset / capture / exit |

The 640×360 renderer uses 128px material tiles with mip gutters, a separate
scroll/poem atlas, batched bamboo meshes, GPU wind and six-sample height fog
integrated along the view ray. The complete forest has 1,464 culms and roughly
one million triangles, most belonging to the surrounding foliage. This keeps
the old-console material and silhouette treatment while using modern hardware
for the density. The scene opens no audio device, including during reviews.

Source files:

- [Blender scene](art/temple/bamboo/bamboo_grove.blend)
- [Geometry builder](build_bamboo_grove.py)
- [Layout, collision and cameras](g_bamboo_grove.py)
- [Playable viewer](bamboo_grove_viewer.py)
- [Texture packing](prepare_bamboo_textures.py)

Built-in ImageGen supplied the original [painted material sheet](art/temple/bamboo/materials_source.png),
including the ink painting. Its [exact prompt](art/temple/bamboo/materials_prompt.txt)
is saved alongside the [material atlas](art/temple/bamboo/materials.png) and
[scroll/poem atlas](art/temple/bamboo/scrolls.png). Chinese lettering is rendered
from a local Chinese font by the texture packer. Other timber and tile colours
reuse the previous hall's material palette.

```powershell
python prepare_bamboo_textures.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_bamboo_grove.py
python moonlit_water_temple_3d.py --bamboo-review
python -m unittest test_bamboo_grove
```

The silent native review walks the actual controller from the starting path,
around the bends, up the steps and into the room. It saves twelve compositions,
an animated walkthrough and a timing report under `artifacts/bamboo-grove/`.
Tests also check exported mesh indices, access around furniture, camera
sightlines, step heights, the round window and the roof from below.

## Separate painted temple interior

Double-click [play_temple_interior.cmd](play_temple_interior.cmd), or run:

```powershell
python moonlit_water_temple_3d.py --interior
```

This is a separate, playable art study of a main hall, both mural aisles, the
passage behind the shrine and a rainy porch. It uses the accepted player rig
and tank controls, with automatic fixed-camera cuts. It does not connect to
the intro's arrival or read/write the water-courtyard gameplay save.

| Control | Action |
| --- | --- |
| W / S, A / D | Walk forward/back; turn left/right |
| Shift | Run |
| 1–7 / 0 | Select an inspection composition / restore automatic cameras |
| F | Free camera; mouse to look, WASD to move, Q/E for height |
| L | Toggle the daylight colour study |
| Tab / H | Toggle player / controls overlay |
| Home / F12 / Esc | Reset / capture / exit |

The hall has three seated figures, layered lotus pedestals, offering vessels,
incense, painted bracket sets, three recessed mandala ceilings and full roof
undersides. Warm lamps contrast with cool lattice light and the rainy exterior.
The original generated paintings draw on the procession murals and Water-Moon
Guanyin shown in the [first reference clip](https://www.youtube.com/watch?v=W07UAbYXJuc)
and the [Fahai walkthrough](https://www.youtube.com/watch?v=ZKio-KcdQKU).
This is a fictional hall for the game, not a measured reconstruction.

Asset source: [temple_interior.blend](art/temple/interior/temple_interior.blend).
Geometry is authored by [build_temple_interior.py](build_temple_interior.py);
collision, lighting positions and camera compositions live in
[g_temple_interior.py](g_temple_interior.py). The scene is about 75,000 triangles,
rendered at 640×360. Materials use 128px tiles with generous mip gutters in a
1024px atlas; wall paintings use four 512px panels in a 1024px atlas.

Built-in ImageGen produced the original
[murals](art/temple/interior/murals_source.png) and
[painted ornament](art/temple/interior/ornament_source.png).
Exact prompts: [murals](art/temple/interior/murals_prompt.txt),
[ornament](art/temple/interior/ornament_prompt.txt).
The runtime sheets are [murals.png](art/temple/interior/murals.png),
[ornament.png](art/temple/interior/ornament.png), and the packed
[architecture.png](art/temple/interior/architecture.png).

```powershell
python prepare_temple_interior_textures.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python build_temple_interior.py
python moonlit_water_temple_3d.py --interior-review
python -m unittest test_temple_interior test_intro_landscape
```

The native review opens no audio device. It captures twelve views and an animated
walk, checks passage access and samples the actual game renderer. Geometry tests
ray-check the floor, ceiling and roof undersides, including oblique views into
the caissons. Previews and timing results are in `artifacts/temple-interior/`.

## Back-seat introduction

Press **F2 during the drive** to open the camera/timeline editor, or double-click
`edit_intro_cinematics.cmd`. It supports camera flight/orbit/pan, start/end camera
keys, lenses, cut timing, shot splitting, looping, save/reload and undo/redo.
See [CINEMATICS_EDITOR.md](CINEMATICS_EDITOR.md) for the controls. Saved framing
and camera moves are used by normal game playback.

The game now opens with a **2 minute 56 second** rainy drive, then fades into the
temple in the same native window. You are in the rear seat of a charcoal Santana;
two anonymous colleagues sit up front in plain clothes. Their heads are deliberately
featureless until the character references arrive. The player lap keeps the blue
shirtjacket, brown trousers and shoes. The car follows a narrow, gently bending
rural road between a mountain bank and a lake, with painted Chinese pines and
layered mountain ranges across the water. The last houses and electric lights
fall away before the final approach.
The sequence alternates composed exterior shots with interactive first-person
dialogue. Travel, rain, wipers, audio and conversation continue across every cut.

| Time | Shot |
| --- | --- |
| 0:00–0:07 | Outside the rear side window, framing the seated player |
| 0:07–0:44 | Interactive interior: dispatch conversation |
| 0:44–0:56 | Overhead tracking view of the car and rural road |
| 0:56–1:35 | Interactive interior: caretaker and temple stories |
| 1:35–1:54 | Side-on tracking: afternoon becomes night, headlights switch on |
| 1:54-1:58 | Interactive interior: the turn is called out |
| 1:58-2:17 | Exterior view of the slow left turn off the continuing public road |
| 2:17-2:43 | Interactive interior: the wooded climb and temple reveal |
| 2:43-2:56 | Pull into the clearing; camera rises toward the terraced temple, then gameplay |

The held side-on shot adds short exposure trails to the passing countryside,
with the car drawn crisply over them. Its time-lapse lighting change reaches full
night before the next interior cut; the headlamp lenses, volumetric beams and wet-road
spill come on together. Shot boundaries are editable in `dialogue.json` alongside
the dialogue timings.

During interior shots, mouse movement looks around the entire cabin, including the side/rear windows,
dashboard, headliner and your lap. **Home** looks forward. **Esc** pauses the ride
and releases the mouse; Esc resumes, Enter skips to the temple, and Q quits from
that menu. Enter also skips during the ride. F12 saves the current view under
`artifacts/temple-intro/`. Exterior cameras are authored; returning inside preserves
your previous look direction. The cursor is restored for temple mouse aiming.

Six real window planes carry refracting drops and winding water trails. Two
windshield wipers sweep continuously and clear their arcs in the glass shader.
Quiet original rain/engine loops and a wiper swish are included. The conversation
is currently subtitled with no recorded voices. Draft dialogue introduces the
caretaker's call, the small-station colleagues and a local bell story; edit the
speaker labels, text and timings in [dialogue.json](art/temple/intro/dialogue.json).

```powershell
python moonlit_water_temple_3d.py --intro-only
python moonlit_water_temple_3d.py --skip-intro
python moonlit_water_temple_3d.py --intro-review
python moonlit_water_temple_3d.py --intro-handoff-smoke
python -m unittest test_temple_intro -q
```

The review writes native 480x270 views of each cut, interior window views, the
day/night tracking progression, arrival, pause and a `cinematic-preview.gif`
montage to `artifacts/temple-intro/`.
The handoff smoke continues through the existing exploration/editor checks in
the same window. Other gameplay/art smoke modes bypass the intro automatically.
Neither the ride nor its reviews write progress or alter level designs.

### Lakeside landscape and mist

The lakeside passage near the end of the supplied
[Santana footage](https://www.youtube.com/watch?v=k1agHhirYR4) guides this fictional
shanshui approach. Chinese pine, 油松 (*Pinus tabuliformis*), is appropriate to the
Beijing mountain setting; see the
[Beijing Forestry account](https://yllhj.beijing.gov.cn/English/Resources/202107/t20210720_2445104.html).
Three Blender-built variants use crooked modeled branches and double-sided painted
needle sprays, with UV-weighted GPU wind like the existing willow foliage. Each
tree has 1,892 triangles, a 256x256 foliage sheet and 32x64 bark. The original sheet
was generated with built-in image generation; its
[source](art/temple/intro/pine_foliage_source.png),
[runtime atlas](art/temple/intro/pine_foliage.png) and
[exact prompt/provenance](art/temple/intro/pine_foliage_prompt.txt) are retained.

The route now has pronounced linked bends, with the car aligned to the road's
tangent and the steering wheel responding to curvature. Rolling rises and dips
lead into a sustained final climb to a 21m-high forecourt. Bridge decks stay
level, with broad eased approaches. The car samples the road at its two axles;
the body, occupants, glass, wipers, headlights and car-relative cameras all pitch
together. The lake and its reflection plane stay horizontal at their original
height. The gateway has a wider level landing supporting its stairs and walls.
The large mountain ranges are world-aligned outside the entire winding road
envelope, rather than offset from individual bends where their bases could
cross the lane. A continuous three-conductor powerline runs 19m up the hillside,
with sagging spans, crossarms and insulators; poles avoid the tributary channels.
The powerline stays beside the public lakeside road. About 255 route metres before
arrival, the car turns left onto a narrower dirt track. The main road visibly
continues beside the lake. Muddy wheel ruts, a grassy centre, darker pines, crooked
bare trunks, branches and exposed roots distinguish the private climb. Terrain
cross-sections explicitly include both roads so the hillside cannot cover the
continuing asphalt. The departure elevation matches both height and grade through
the bend; the final landing remains level.

Terrain and foliage extend 288 route metres both ahead and behind, with a distant
fog fade. Near trees now share persistent terrain batches instead of disappearing
at a separate short rear culling plane. The complete short route is preloaded to
avoid mesh-generation hitches during playback. Three 24m weathered stone bridges
cross visible meandering rivers at stations 315, 748 and 1120 metres. Road pavement
stops at the bridge decks. Separate river ribbons descend from the gullies, with
moving broken ripples and bank foam, then blend into the lake. Wider banks soften
the river valleys. The lakeshore has variable-width grassy shelves, small bays,
irregular ground contours and low, varied shrub thickets. The shoreline boulder scatter
has been removed. Each river continues 520m upstream with supporting banks, beyond
the 275m scene fade, and blends into the lake downstream. The hillsides have
additional pine groves and batched shrubs/ferns, planted at the terrain height.
Foliage uses mipmaps and trilinear filtering to reduce distant shimmer; car and
cloth atlases retain their crisp filtering. Mountain silhouettes have smoother
normals and denser contours. Daylight has a brighter overcast sky, directional
shading, green bounce and wet highlights, while the night transition is retained.
The sky is a cheap world-oriented procedural cloud layer: a dense grey ceiling,
drifting low scud and a hazy horizon, also visible in reflections. High-altitude
mist thins enough to retain cloud shapes. Car paint has a low, broad highlight
and darker diffuse response; the previous hard metallic glint is removed.

Rear-view mirrors use one 128x64 rear scenery capture shared by the two door
mirrors, refreshed at most 10 times per cinematic second. A second small target
adds the actual rear cabin and seated player for the interior mirror. Its narrow
glass crops the image rather than stretching faces. Door-mirror housings are
reused from the exterior mesh in first-person shots. This is an inexpensive shared
view, not three independent physically accurate reflection cameras; there is no
recursive rendering or additional volumetric pass for mirrors.

The 256x256 undergrowth atlas was generated with built-in image generation:
[runtime sheet](art/temple/intro/undergrowth.png),
[original](art/temple/intro/undergrowth_source.png),
[exact prompt](art/temple/intro/undergrowth_prompt.txt). The Blender shrub and fern
prototypes have 64 and 40 triangles; runtime terrain chunks combine their geometry
so hundreds of plants do not become hundreds of separate draw calls.

The 480x270 scene has a sampleable depth texture. A 56-step ray march integrates
height-dependent, drifting 3D mist and warm headlight scattering up to opaque
scene depth. It supports perspective and orthographic editor cameras. Fog is
composited before the cabin/glass, with a cabin exclusion volume, then participates
in the tracking shot's exposure trails. Lake mist has its own drifting, rising
billows, distinct from the thinner roadside haze. A mirrored scene pass reflects
mountains, shore vegetation and bridges in the lake. Fresnel blending, small wave
distortion, shallow-water tint, highlights and expanding rain rings animate the
surface. Headlight backscatter is restrained from inside the car; the volumes do
not yet cast light-space tree shadows.

The arrival is now a broad dirt clearing beneath a fictional terraced temple
complex, retaining the [Fahai-inspired atmosphere](https://english.visitbeijing.com.cn/article/47ONhwzBFdS).
Fifty-four entrance steps rise 10.8m in three flights with resting landings and
stone balustrades. A red three-bay gateway, flanking towers, enclosing walls,
latticework, bracket sets and curved tiled roofs lead into successive higher
courtyards and halls. The complex spans about 72m across and 139m deep; its eleven
halls/towers use a dedicated original 256x256 weathered-material atlas. Upper
roof silhouettes rise above the gate from the arrival camera. Terrace pines,
roofed steles and four restrained lanterns add scale and framing.

The car brakes before the signed left turn, travels slowly through the bend,
then accelerates up the wooded track and stops 20 route metres before the temple
origin, about 12m short of the first stair. The public asphalt remains separate;
the private track ends in a roughly 36m by 48m gravel-and-earth clearing. The new
turning shot and longer climb are editable in the existing cinematics editor.
The turn dialogue now refers to the clearing below the steps.

This remains the cinematic approach. The existing playable water courtyard is a
separate part of the temple, and gameplay still hands off there; the complete
playable temple layout awaits the proposed sketch.

Placement, bends, elevations and bridge stations live in `g_intro_landscape.py`;
continuous terrain/bridge/vegetation/powerline batches live in
`temple_intro_terrain.py`. Tree, ridge and undergrowth prototypes are built by
`build_intro_landscape.py` and `build_intro_undergrowth.py`. The regular intro
Blender build also calls `build_intro_temple.py`; that script can run independently
to rebuild only the approach temple and its manifest entries, preserving the car
assets. The editable source is `art/temple/intro/temple_approach.blend`. All GLBs
embed their textures; the larger temple uses uint16-safe mesh batches for Raylib.

```powershell
python -m unittest test_intro_landscape test_temple_intro test_cinematics_editor -q
python temple_landscape_review.py
python temple_intro_polish_review.py
python temple_intro_route_review.py
python temple_intro_atmosphere_review.py
python temple_intro_arrival_review.py
```

The muted native landscape review writes lake/mountain, pine, headlight and arrival
views to `artifacts/intro-landscape/landscape-review.png`, plus a JSON report. The
GPU checks verify that an opaque near wall stops the mist, that a farther wall
admits the intervening volume, and that foliage moves without changing CPU mesh
buffers. An isolated fog test freezes both the opaque scene and road position to
verify that the volume itself moves. The polish review adds occupied belt views,
empty rear belts, both footwells, headliner, all three bridges and a stationary
lake-mist animation under `artifacts/intro-polish/`. It also verifies that driving
across chunk boundaries reuses uploaded geometry. The normal cinematics editor
previews exactly this landscape and volume pass.

The muted route review renders 280 samples along the drive and a complete
60-frame wiper cycle from inside and outside. It writes `route-review.png`,
`full-route-contact-sheet.png`, `wiper-poses.png`, `wipers-inside-out.gif` and
timing data under `artifacts/intro-route/`. Geometry tests check whole mountain
footprints against the road envelope, tyre contact through crests, uninterrupted
wire spans, the ascending approach and level forecourt, rear belt visibility,
and wiper clearance from the pillars/roof and from each other.

The atmosphere review adds mirror close-ups and refresh checks, a rear-window
driving GIF, the main-road turnoff, daylight inspection of the dirt climb, rivers,
clouds and subdued paint under `artifacts/intro-atmosphere/`. It ray-checks the
uploaded terrain along both the driven route and continuing public road.
The arrival review adds upstream river views, shoreline planting, daylight and
night temple inspections, plus `turnoff.gif` and `temple-reveal.gif` under
`artifacts/intro-arrival/`. Its latest run passed 467 road-clearance ray checks,
with terrain at least 2cm below the sampled road centres. The reviewed frames
peaked at 411 counted scene submissions, including reflections; full-route
preload took about 17 seconds. These are review measurements, not a guarantee
of total game frame rate.

The car now follows the additional Santana exterior and interior references.
Its curved body, cloth seat bolsters/headrests, moulded door cards, window cranks,
analog dashboard, radio, vents and steel wheel covers use two 256x256 sheets and
one 128x128 wheel sheet. The complete opaque exterior car is **21,988 triangles**, including
all four wheel instances and the steering wheel; six rain-glass panes add 12.
The narrower crowned roof, thin gutters and headers form one closed shell.
The Classic Santana reference guides a nearly flat trunk, longer rear-glass rake,
forward center pillars, quarter-light dividers, smaller wheels and higher bumper
and rear-lamp placement. Painted door-window frames meet the beltline; rear quarter
sections flow into the shorter, 0.48m trunk deck. The video-reference pass slightly
shortens the side windows, seals their header joins and replaces the end bars with
continuous bumpers wrapping toward the wheel arches. A fitted floorpan and sill
returns enclose the cabin carpet. The complete exterior stays below 22,000 triangles.
Finer arches, bevelled window seals and rounded mirrors improve exterior close-ups.
Matching inner pillar linings follow the shared glass openings in both cabin variants.
The moving wipers remain procedural.
See [SANTANA_ASSET.md](SANTANA_ASSET.md).
First-person shots select a separate **14,720-triangle** interior, including a
more detailed steering wheel and 5,544 triangles of belt hardware, buckles,
seat-back pockets/welts, seat controls, door fittings and dashboard details.
Unused rear belts retract beside the C-pillars. Each front passenger has one belt
fitted over the chest and lap in the actor mesh, with matching pillar hardware.
Sloping carpet returns and front/rear bulkheads close both footwells, and the
headliner/visors use a darker worn grey fabric. Floor ray checks include the side
edges, from inside the car, with upward-facing geometry.
It has two dedicated 256x256 sheets. Exterior shots retain the lighter cabin;
both versions use the same window openings and actor placements. Inspect the
[first-person Blender scene](art/temple/intro/santana_interior.blend) or run
`python temple_car_review.py` for detailed native close-ups and variant checks.
Its `artifacts/santana-car/roof-quarter-review.png` shows the revised roof,
rear quarter, both center door joints and side profile without occupants.
The [assembled car Blender scene](art/temple/intro/santana.blend) opens with the
vehicle assembled, packed textures, studio lighting and five inspection cameras,
including roof seams and a wheel/mirror close-up.

The [editable intro Blender kit](art/temple/intro/intro_kit.blend) contains the cabin,
colleagues, steering wheel, player lap, countryside props and approach gateway,
plus exterior bodywork, rotating wheels, headlamps and the accepted player model
in a seated pose with its existing face atlas. The original locomotion assets
remain the source for that character.
Rebuild the models, texture sheets, Blender scenes and synthesized audio with:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python-exit-code 1 --python build_temple_intro_assets.py
```

The [ride controller](g_temple_intro.py) integrates travel independently of frame
rate; nearby scenery stays bounded as it scrolls past the stationary car. The
[intro renderer](temple_intro_viewer.py) owns and releases its models, frame
buffers, exposure history, fonts, shaders and audio before handing off. The car
uses the three supplied `artdev` car references, with a lower/shorter roof,
revised wheelbase, rounded panels and shared cabin/glass/wiper placement anchors.
Its generated assets do not depend on those untracked
reference images at runtime.

The first gameplay milestone now runs here: collect the brass key on the
boardwalk, unlock the temple entrance, open it with a second interaction, and
inspect the inscription in front of the altar. Medicine near the starting point
can be collected and used from the inventory when health is below 100.

The third milestone adds a complete encounter on the timber terrace beyond the
boardwalk's right-hand end. Walk onto the terrace to wake a pale chorus figure; retreat to
the bridge or fight it. Defeating it unlocks the slatted gate. Open the gate with
E and collect the ammunition beyond it. Medicine sits at the terrace's near edge.

Walk along the boardwalk, turn toward the entrance, enter the temple, and return.
Three composed orthographic views cut automatically: across the lake, the temple
landing, and the altar room. The image remains 480 x 270, enlarged with nearest
filtering. This uses the photo-textured Blender meshes from the live art viewer.

## Controls

| Key | Action |
| --- | --- |
| W / S | Move forward / step backward along the player's heading |
| A / D | Turn left / right, with pivot steps when standing still |
| Shift + W | Run forward |
| Hold right mouse | Mouse controls facing; W/S moves forward/back and A/D slowly strafes |
| Left mouse while aiming | Fire the pistol |
| T | Reload from inventory ammunition; stand still during the 1.15-second reload |
| Enter after death | Restart fresh progress using the current authored spawn |
| E | Inspect, collect, unlock/open or close the nearby door |
| Tab | Inventory; arrows select, E/Enter uses an item |
| E / Enter | Continue dialogue; left/right selects a choice |
| F5 / F6 | Save / reload exploration progress |
| F2 | Enter / leave the level editor |
| Home | Return to the authored spawn, retaining progress |
| H | Hide/show the help and shot title |
| R | Toggle roof cutaway for inspection |
| L | Toggle neutral inspection lighting |
| F12 | Save `artifacts/temple-camera-trial/fixed-camera-user.png` |
| Esc | Cancel a dialogue, close inventory, or quit during exploration |

Gameplay uses tank controls: camera cuts and key releases preserve the player's
heading. Turning can be combined with forward/backward movement. Rotation runs
at 120 degrees/second, backward steps at 13 units/second, and aimed strafing at
7 units/second (aimed forward movement is 12). Shift affects forward running.
Movement slides along blocked tile edges, including the sides of the boardwalk.
The independent `--fixed-cameras` art review retains its camera-relative controls.

Each shot has a smaller entry region and a larger retention region. These
overlapping regions keep a player near a boundary from repeatedly switching
views. Returning along the route restores the earlier shots.

The existing roof fade remains. The interior shot also hides the front facade
to keep the room readable; the columns, lanterns and collision remain. This is
a deliberate shot-specific cutaway, not a change to the original scene.

## Authoring and implementation

- [Saved scene](art/temple/exploration.scene.json): decorative object transforms,
  stable exploration IDs, spawn and design markup. Load a separate scene with
  `python moonlit_water_temple_3d.py --scene path/to/scene.json`.
- [Exploration controller](g_temple_gameplay.py): synchronizes the original
  player state with tank movement and uses the shared inventory,
  descriptions, choices and puzzle handlers. Movement, footsteps, animation
  and the gameplay clock pause for modal UI and scene editing. Opening and
  closing a modal also consume their input frames.
- [Camera definitions](art/temple/camera_shots.json): eye, target, vertical
  orthographic span, region priority, `enter`/`hold` rectangles, and optional
  `hide_front_facade`. That option covers this scene's front facade entities.
- [Camera and movement logic](g_temple_cameras.py): independent of Raylib.
- [Shared live renderer](temple_3d_viewer.py): `--fixed-cameras` selects this mode;
  running without it retains the orbital art viewer and its world-axis controls.

Camera vectors use `(X, height, ground Y)`. Region rectangles use
`[min X, min ground Y, max X, max ground Y]`. Higher priority wins on entry;
the current shot otherwise persists until the player leaves its `hold` rectangle.
Terrain generation writes into the ignored artifact cache, rather than changing
the exported model files.

## Level blockout, placement and design markup

Press **F2** to pause exploration and open the editor. **C** switches between
an overhead view and the actual game camera. The complete camera composition is
shown beside the tool panel. In the overhead view, WASD pans and the wheel zooms.

| Control | Action |
| --- | --- |
| 1 / Select | Click an object or mark, then drag it; arrows nudge |
| 2 / Place | Choose an object in the palette and click the scene |
| Q / E | Rotate the selected object by 15 degrees; gates use 90-degree turns |
| G | Toggle four-unit snapping; Shift enables one-unit placement/nudges |
| Ctrl+D / Delete | Duplicate / remove the selected object or mark |
| 3 / Note | Click, type a design note, Enter commits, Esc cancels text |
| 4 / Arrow | Click the start and end, then type an optional note |
| 5 / Area | Click opposite corners, then type an optional note |
| 6 / Floor | Choose a material and drag a rectangle to build floors or walkways |
| 7 / Stairs | Click the lower corner, then the opposite upper corner |
| 8 / Spawn | Click a clear walkable spot for the starting position |
| 9 / Encounter | Click opposite trigger corners, then enter an encounter group |
| [ / ] | Lower / raise the chosen floor or stair landing height by four units |
| V | Change wood grain direction or stair ascent direction |
| Right drag (Floor) | Erase a floor rectangle into water |
| Alt+click (Floor) | Sample an existing floor's material, height and grain |
| Right click (Stairs) | Remove the stair flight under the cursor |
| J | Toggle automatic edge rails |
| K | Choose yellow, blue or red markup |
| Enter | Edit markup text or the selected encounter object's group |
| F4 (editor) | Reset encounters and gates; restore health and a full pistol |
| Wheel over object palette | Scroll additional props, spawns, gates and ammunition |
| Ctrl+Z / Ctrl+Y | Undo / redo; a complete drag is one operation |
| Ctrl+S / Ctrl+O | Save / reload the scene; reload is undoable |
| F2 | Return to exploration, applying unsaved edits in the current session |

Scene edits persist only after **Ctrl+S**. Closing the editor keeps unsaved edits
in memory. Save files preserve UTF-8 notes, arrows, areas and object IDs, so you
can mark a location and describe the intended change directly in the game.
Decorative props, keys, medicine and inscriptions can be placed; moving a fire
bowl also moves its emitter and collision. Collected items retain their progress
through layout edits; duplicates receive new IDs. If an edited prop overlaps the
player, returning to play moves him to a nearby clear position.

The second milestone adds saved floor footprints. Wood produces suspended
boards, beams and piers; stone and grass produce solid platforms. Walls stand
48 units above their selected base height and block movement. Water removes
walkable floor. **Restore original** restores the shipped surface and any
original stair flight touched by the rectangle. Each complete floor drag is
one undo operation. Rectangle boundaries use 16-unit construction increments.

Heights range from 0 to 48; the original bridge is at 16 and the temple at 24.
Stair flights rise in any of four map directions, with automatically sized
risers. Set the upper landing height before placing stairs; their lower height
comes from the first clicked location. Draw a longer rectangle if the tool
reports that the flight is too short. Floor painting across stairs replaces
the whole flight. The player can climb short risers and cannot step directly
up or down a tall ledge. Individual foot IK remains future animation work.

Floor commits, undo/redo and scene reload rebuild the visible meshes from the
same data that drives collision, floor height and surface footsteps. Boundary
rails follow exposed raised wood edges and disappear across newly connected
floor. New walkable areas outside the original footprint get a local camera
view so the player remains visible; the original authored shots are retained
on the original route. Leaving the editor relocates the player if a floor or
prop edit makes the current position invalid. A completely erased layout stays
in the editor until it has a walkable starting point again.

The scene file stores edits to the original layout rather than duplicating
all exported geometry. Older placement scenes load with the original floor and
stairs automatically. The decorated temple shell, its entrance and original
camera regions remain anchored; new walls are blockout masonry. There is one
walkable surface at each map position, so overlapping floors are later work.

## Combat and encounter authoring

The pistol has a 20-round magazine and a 0.24-second shot cooldown. Body hits
use the existing 20-point bullet damage against the redhead's 60 health. Mouse
aiming follows the current orthographic camera; nearby projected bodies provide
a small aim target. The actual bullet trace checks height, walls, doors and solid
props, so a target behind a gate cannot be hit through it. Shots can cross open
water. The redhead reuses the original noticing, hearing, pursuit, windup,
committed attack, stagger, evasion, fleeing and death behaviours at speeds tuned
for the 3D player's scale. Movement respects live bodies, painted floors, props,
stairs and tall ledges; melee cannot damage the player across a large height gap.

In **Place**, choose **Redhead spawn** or **Encounter gate**. Tool **9** creates
a rectangular encounter trigger. Select a trigger, spawn or gate and press
**Enter** to change its group. Matching groups connect the objects: entering any
trigger in a group activates its spawns; defeating all of them unlocks the group's
gates. Groups with no spawns do not complete. Blocked spawn points wait until clear.
Gates occupy two adjacent 16-unit cells and can be rotated with Q/E. Duplicate,
move, delete, save and undo use the same stable-ID scene workflow as other props.

The authored terrace has a west-side camera and two fire bowls so the fight stays
readable. Additional fire lights are chosen by proximity to the current view.
A nearby foreground willow fades during the new layout views to keep the player
visible. Optional trigger fields `camera_offset` and `camera_span` allow camera
composition to be adjusted in the scene JSON; the original route keeps its shots.

Use **F4 while editing** to test the encounter again without discarding the layout,
pickups or unrelated puzzle progress. It resets enemy/encounter state, reseals
encounter gates and restores health and a loaded pistol. It does not save progress
or alter scene history. F5 saves the resulting progress after returning to play.

The separate [Blender combat kit](art/temple/combat/combat_kit.blend) contains the
accepted player geometry and locomotion plus left/right pivot turns, backward
steps, aim, forward/backward/sideways aimed walking, recoil, reload, hurt and death
clips. The pale chorus figure uses a 128px monochrome atlas, fifteen bones and
idle/walk/attack/stagger/death clips. Its 21.6-unit stature is shorter than the
25.65-unit player, with an oversized pale mask, dark rounded hair, outlined eyes,
long nose, angular cheek marks and a knee-length charcoal coat. The short leftmost
figure in Margaret Breindel's *The Chorus* is the visual reference, inspected from
[the supplied local image](artdev/ChorusReference.jpg). The
legacy `redhead` asset and AI identifiers keep old scenes/progress compatible. Both deform
on the GPU. The pistol is weighted to the player's right hand. Rebuild with:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python-exit-code 1 --python build_temple_combat_assets.py
```

This writes only the combat kit; the original living exports and animation review
files remain intact. More advanced aim overlays and individual stair-foot IK are
future animation refinements.

## Exploration saves

**F5** writes `saved_editor_states/temple3d-progress.json`; **F6** reloads it.
The save contains player position, heading, health, ammunition, inventory,
collected items, door state and puzzle facts. It contains no graphics, audio
voices, modal dialogue or editor history. Startup begins a fresh exploration;
press F6 to continue a saved one. Invalid saves are rejected before changing
progress. Layout and player progress are separate files, so a playthrough cannot
overwrite level design. F5/F6 are available during exploration, outside modals.

Combat progress also records activated/completed groups, enemy health/position/
behaviour timing and pending reload time. Restoring a defeated enemy retains its
corpse and completion state. Saves without combat data load with unstarted
encounters. Combat and compound-door data are validated before changing progress.

## Raised bridge and temple floor

`g_temple_deck.py` replaces solid wood tile extrusions with individual boards,
transverse beams and piers extending below the waterline. `g_temple_structure.py`
prepares a separate 3D layout: the surrounding forecourt/skirt is removed, the
temple stands on its own heavier bearer beams and twelve piers, and a narrow
walkway connects directly to the entrance. Temple floor height is 24; bridge
height is 16. Roof, walls, lamps and furnishings follow the raised building.

Six low shore steps rise from the grass to the bridge; four shorter risers
connect the bridge to the temple sill. Walking uses the actual tread heights
with smoothed root elevation. Independent foot alignment to individual steps
is not implemented yet. The normal spawn remains on the bridge; walk back toward
the grass to try the shore steps.

The layout operates on a copy of the original arena. Removed platform cells
become collidable water, while the existing doorway and movement code remain
in use. Rails and former forecourt props move onto the supported footprints.
Board gaps remain visual. The geometry has 170 boards, 27 beams, 38 piers and
10 stair treads plus risers/stringers: 3,300 triangles combined into three
material batches at load time. There is no per-board update or draw loop.
`python moonlit_water_temple_3d.py --structure-review` saves three views under
`artifacts/temple-camera-trial/`: `structure-0.png` (bridge), `structure-1.png`
(temple foundation), and `structure-2.png` (shore stairs).

## Current scope and verification

The existing tile collision and authored camera cuts work with a revised 3D
footprint and explicit floor heights. This is useful for judging composition,
spatial readability and controls before committing to a rendering migration.

The actor is now a low-poly, GPU-skinned player based on the existing directional
sprites, with idle/walk/run clips and short pose blends. Both willows now use a
3D trunk, branches and hanging painted foliage with GPU wind. See the
[editable living asset kit](photo_asset_pipeline/temple3d/living/README.md).
The [3D animation viewer](ANIMATION_VIEWER_3D.md) provides slow motion, frame
scrubbing, skeleton overlays and a Blender review file for refining the gait.

Interactions, pickups, inventory, healing, linked entrance collision, inspection
callbacks, progress saves and distance-driven footsteps now run in 3D. Footsteps
use the existing surface-aware spatial audio runtime and sound files; optional
ambient/fire families fall back to silence when their recordings are absent.
Storm scripting, richer water/reflections, cast shadows and
animated grass remain later migration work. The Buddha remains part of the
existing altar asset.
The separate 2D game launchers remain available. `--classic-assets` restores
the capsule and tree billboards for comparison. The orbital viewer keeps those
older assets by default; to orbit the new models, run
`artifacts/temple3d-env/Scripts/python.exe temple_3d_viewer.py --living-assets`.

```powershell
python -m unittest test_temple_layout test_temple_exploration test_inventory test_puzzles test_temple_cameras test_audio test_temple_gait_deck
python moonlit_water_temple_3d.py --gameplay-smoke
python -m unittest test_temple_combat test_temple_combat_assets -q
python moonlit_water_temple_3d.py --combat-smoke
python moonlit_water_temple_3d.py --player-review
```

The gameplay smoke test drives movement and actual shared modal input in a hidden
Raylib 5.5 window. It checks pickups, healing, modal pause, both door leaves,
camera cuts, an inscription callback, a progress round trip, scene undo/redo,
duplicate IDs, moved fire emitters and UTF-8 markup. Captures and its JSON report
are written to `artifacts/temple-exploration/`; all smoke saves use that directory
and leave the shipped scene and user progress untouched. The original art,
structure and animation review modes remain available.

The same review now injects a mouse drag through the actual editor/camera picking
path, builds an extended walkway, stone landing, stair flight and upper terrace,
and walks the player over them. It verifies material footsteps, framing, wall
collision, progress reload, geometry undo/restore and an empty-mesh rebuild.
The editable demo is saved as `artifacts/temple-exploration/blockout.scene.json`;
try it with `python moonlit_water_temple_3d.py --scene artifacts/temple-exploration/blockout.scene.json`.

The earlier gameplay review uses a calm fixture of the original temple so its
blockout route is independent of enemy encounters. The separate combat review
uses the shipped terrace in a hidden native window. It checks pursuit and melee,
real camera/mouse aiming, recoil/reload/hurt/death GPU clips, modal pause, healing,
gate traversal, ammunition pickup, active and completed progress round trips,
native trigger placement/undo, tank turns, backward steps and restart. Front/side
enemy inspections and pivot-step captures are included. The control regressions
in `test_temple_tank_controls.py` check facing across cuts, mouse-owned yaw,
slow strafe speed, collision, modal pause and stationary-facing save/load.
Captures and reports are written to
`artifacts/temple-combat/`; the test never saves over the shipped scene or user
progress. Export tests compare the accepted mesh and all original locomotion
channels against the combat export.

The next gameplay migration work is the temple storm.
Shadows and water reflections can be evaluated at the intended low resolution
alongside those systems, with frame-time profiling to guide the rendering work.
More general terrain/foot IK can build on the separate ground positions and
render heights used by the stairs.

## Verification

The independent **The Moon in the Water** encounter is available through
`play_huxin_moon.cmd` (or `python huxin_moon_viewer.py`). The original lake scene
remains available through `play_huxin.cmd`; its 29 original files are recorded
and checked against `art/temple/huxin_moon/origin_snapshot.json`.

Walk along the causeway with W/S, turn with A/D, and hold Shift to run. At the
basin, press E to examine the bronze mirror. Arrow keys rotate and tilt it;
bring the pale moon image into the small worn circle in the water and hold it
there briefly. E steps away. Mist accumulates throughout the approach, using
projected distance along the curved causeway and quintic easing. It shares the
existing scene fog's blue-green colour, with slowly evolving three-dimensional
billows and restrained stepped lighting adapted from `illuminated_fog.fs`.
Opacity remains continuous, preventing visible jumps between tonal bands.
The first alignment plays one distant bell and adds a six-second crescendo
to the already thick bank. The hidden swap happens at eight seconds, then the
mist dissipates through the rest of a 24-second sequence. The basin, original
columns and central floor remain visible as the larger room emerges. The basin
shot tightens during the swap to keep the new overhead lantern out of frame;
the later pullback reveals it with the room.

Explore the tea room, timber stairs, upper chamber and balcony. On the return
causeway, fog builds with outbound distance and reaches its peak halfway along
the route. A denser bank around the pavilion conceals the one-time swap at that
midpoint. Fog then eases away throughout the second half, revealing the original
pavilion by the shore. Normal gameplay cameras remain in use throughout, with
no transition close-up. Walking, running, turning and stopping remain available.
Walking the causeway takes about 46 seconds; running reaches the same fog stages
at the same places. Backtracking reverses the fog before the swap, and never
reconstructs the house after it. Neither swap changes position or inventory.

The water reflection has its own depth-aware pass through the same moving fog
field. Its rays run from the water toward the reflected scenery; the main view
then adds the camera-to-water fog. Both views conceal the building change, while
colour grading and bloom are applied once to the assembled scene.

The previous cinematic fog version is preserved in
`artdev/scene_backups/huxin_moon_cinematic_fog_20261015.zip`, including its source,
assets and preview GIFs. Its `BACKUP_MANIFEST.json` records hashes and restoration
instructions. The current teahouse has paired supports beside the entrance and
an overhead lintel, leaving the causeway clear underneath the balcony.

The extended floor joins the
original platform at its boundary, without overlapping floor caps underneath.
At game resolution, the central paving uses filtered joints on its continuous
surface instead of rendering the millimetre-high decorative slab edges.
Home restarts the encounter. H hides the controls, 1–9 select inspection
cameras, 0 restores automatic cameras, F enables free look, L toggles daylight,
and F12 captures the view. In free look, mouse/WASD move and Q/E change height.

This remains a separate art/gameplay prototype, with no new story item or
dialogue. The empty tray upstairs is reserved for a future interaction. The
encounter uses the existing inventory slot format and retains its contents
through both swaps. A restart deliberately clears the prototype session.

The editable Blender file is `art/temple/huxin_moon/moon_teahouse.blend`.
Rebuild its GLBs with Blender's background Python runner and
`build_huxin_teahouse.py`; the builder reuses the pavilion's 128px painted
material tiles. Navigation, mirror optics and transition timing live in
`g_huxin_moon_sequence.py`; interior camera stations are in
`huxin_moon_camera.py`. The layered roof, lattice windows and waterside rooms
take their architectural cues from the historical Huxinting Teahouse
([Shanghai tourism reference](https://www.meet-in-shanghai.net/en/news/hai-streets-the-ancient-and-little-known-history-of-yuyuan-garden-575580/)).

```powershell
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin_moon test_huxin_moon_encounter test_huxin_moon_clearance -v
python huxin_moon_viewer.py --review
artifacts/temple3d-env/Scripts/python.exe huxin_moon_fog_review.py
```

The muted native review walks the approach, aligns the mirror through its
adjustment controls, watches both complete fog transitions, visits both floors,
and checks that no camera cut coincides with a swap, along with player continuity
and inventory retention. Captures, a full
walkthrough GIF and the JSON report are in `artifacts/huxin_moon/`. Unit checks
also compare navigation against exported stair/floor surfaces and cast camera
rays through the actual architectural meshes. No audio device opens for this
review. The original bell cue is verified from its WAV samples.
The dedicated fog review compares both architecture states at the same instant
to check concealment while the central pocket remains visible. It also measures
frame-to-frame fog changes, verifies player visibility through the volume and
walks the entire return without interrupting movement, checking midpoint
concealment from the normal gameplay camera. Its captures,
`mist-roll-in.gif` and `mist-causeway-return.gif` are also written to
`artifacts/huxin_moon/`. Pass `--quick` to skip encoding the two animated previews.
The concealment checks include the worst changed pixel, separate reflection
captures, and several cloud phases, so small lamp or reflection flashes cannot
be hidden by a low whole-frame average.

Automated unit tests, smoke tests and native review modes mute the audio engine's
master output by default. Sound loading, voice timing, pause/resume and audio-event
checks still run normally. Interactive gameplay and previews retain sound.
Use `HAUNTED_MUTE_AUDIO=1` for ad-hoc automation launched via stdin or `runpy`.

## Void Canals — 幽冥水乡

Launch `play_huxin_canals.cmd` for the independent third pavilion scene. It starts
on the same lake approach, with the established position-driven fog. The existing
lake and Moon scenes remain unchanged; 89 source/asset hashes are recorded in
`art/temple/huxin_canals/origin_snapshot.json` and checked by the new tests.
The previous high-water version is a separate frozen scene, launched with
`play_huxin_canals_flooded.cmd`. Its 81 source and asset hashes are recorded in
`art/temple/huxin_canals_flooded/frozen_snapshot.json`; rebuilding the current
district does not overwrite that version.

The prototype begins with the previously collected stone annulus in inventory.
At the bronze mirror, press **E** to place it on the basin. This consumes only
the matching object, preserves other inventory and starts a 48-second
fog sequence. After the concealed change, the dense bank retreats outward for
38 seconds: nearby houses emerge first, then successive layers of the village,
while the distant canals remain obscured. Coarse, softly posterized fog banks
gather around the actual house footprints. Nearby water and paving receive
lighter, broken wisps, while denser layers cover the changing streets farther
out. The two environments blend gradually from seconds 5 to 12, each with its
own depth-aware fog and correct water reflection. The shared pavilion and player
stay aligned throughout. Three-dimensional noise bends the broad billows and
branching wisps; the player and basin remain readable during the crescendo.
Uneven layers release different parts of the village at different
moments. The camera stays exactly where it was before the interaction,
through the gathering mist, the concealed world change and the clearing fog.
It remains there until the player moves. The complete original pavilion is its
own twin in the other world: deck, roof, posts, brackets, ceiling, inscriptions,
basin and lamps remain in place. The ordinary lake remains at y=0; the blend
reveals canal water at y=-1.55, while the pavilion and quays
stay at y=.325. Exposed foundations, bank walls and washing stairs establish
that difference in height. Reflections use the current water plane and pass
through the same world-space fog as the direct view.

The district is built around the newer book references in
`artdev/concepts/canalsv2`. An irregular network of waterside quays, two stone
bridges, a small courtyard and covered passages replaces the first block layout.
Vacant homes along the playable quays can be entered through their actual
ground-floor door bays and explored. Door apertures, porch posts and navigation
share `canals_house_plan.py`, including the outer bays of wide shopfronts.
The current district contains 142 houses and sixteen accessible homes. Thirty
front door bays lead into real rooms, and nine homes also have open rear doors
leading to back quays and washing stairs. Thirty-six washing flights are
distributed around the village, twenty-seven behind houses; twelve have playable
landings just above the lower water. Reaching the rear landings requires walking
through the rooms and returning through them. Twelve additional rear flights
belong to the scenery houses opposite the pavilion. Continuous bank paths also connect the distant houses; the
playable northern quays end at visible breaks with submerged fragments.
The nearby houses have hollow rooms, inset upper storeys, open windows, porous
timber screens, folded or broken doors and deep awnings. Black interiors have
actual floors, ceilings and back walls rather than flat dark panels pasted onto
solid boxes. Hand-laid paving, water stairs, irregular tiled roofs and occasional
laundry provide domestic scale. The original causeway blends into the new paving
over a shared strip, with continuous stone beneath the join. The desaturated material atlas remains deliberately
low resolution. Current exported budgets and house metadata are recorded in
`art/temple/huxin_canals/canals_manifest.json`.

After entry, walking back never restores the lake. **Home** resets the standalone
prototype for testing. `play_huxin_canals.cmd --canals` starts directly inside the
new world. W/S move, A/D turn, Shift runs; 1–9 inspect camera stations, 0 restores
automatic cameras, F enables free look, H hides controls and F12 captures an image.
There are no inhabitants or combat encounters. Long silences are interrupted only
by occasional quiet timber movement; the eventual exit remains open for design.

Edit the district in `g_huxin_canals_layout.py` and `build_huxin_canals.py`, and
the hollow house components in `canals_housekit.py`;
`art/temple/huxin_canals/void_canals.blend` is the editable Blender scene.
The layout is shared by geometry, collision and camera stations. Rebuild the GLBs
with Blender's background runner and `build_huxin_canals.py`. Repack materials with
`prepare_huxin_canals_materials.py`. The new sequence, renderer, cameras, sky, audio
and shaders all have their own `huxin_canals` files.

```powershell
$env:HAUNTED_MUTE_AUDIO='1'
artifacts/temple3d-env/Scripts/python.exe -m unittest test_huxin test_huxin_moon test_huxin_moon_encounter test_huxin_moon_clearance test_huxin_canals -q
artifacts/temple3d-env/Scripts/python.exe huxin_canals_review.py
artifacts/temple3d-env/Scripts/python.exe huxin_canals_review.py --flooded-smoke
```

The muted native review walks the lake approach, places the object, checks the
stationary camera and hidden swap in both the image and the water reflection,
then walks the complete canal loop using the real controller.
It verifies player visibility from every route camera and saves the reveal,
a condensed walkthrough, a contact sheet and a JSON report under
`artifacts/huxin_canals_v5/`. Earlier review images remain under
`artifacts/huxin_canals_v4/`, `artifacts/huxin_canals_v3/`, `artifacts/huxin_canals_v2/` and
`artifacts/huxin_canals/`. `--quick` skips GIF
encoding. The flooded smoke loads the preserved scene independently, checks
its stationary reveal and high water, then walks its own quay route without
writing any frozen files. CPU checks cover walking
and running in both directions, exported walking surfaces, real opening depth,
camera continuity, retained pavilion geometry, inventory continuity and preservation
of the earlier scenes and the flooded backup. Natural doorway tests use the
exported apertures to drive straight approaches at the center and both sides
of every accessible bay, walking and running, and check actual geometry at
both sides of the player's capsule. Rear routes are checked against the actual
exported room boundaries before reaching their stairs; the causeway join is
checked across its usable width against the exported floor meshes. The native
review also compares the last clearing frame with the completed state to catch
a final fog pop. Rays immediately inside the room walls check that their floors
meet the plaster without thin light leaks. Automated reviews never open an audio device.
V5 adds front-facing rays for bank walls, house foundations, washing risers,
stair flanks and caps; ordinary two-sided floor intersections cannot detect a
face that disappears under back-face culling. The tread shoulders now close
the full-width quay cuts while retaining worn edges. The separate V5 curtain
probe checks both held cameras, centre actor/basin contrast during the crescendo,
the distance-driven approach, reflected world change and final clearing.
The optional V5 CPU runner caches controller trajectories using fingerprints of
the controller/navigation sources and exported doorway data, allowing geometry
repairs to reuse verified routes without concealing a changed movement model.

The final V5 export passed 21 focused CPU checks in 232.94 seconds, covering
outward-facing bank walls and undersides, closed tread mouths, all 39 accessible
front/rear doorway bays, actual walked floors, sequence behavior and protected
scene hashes. All 936 probes placed 1mm on either side of tread boundaries
passed. The district contains 142 houses and 1,322,743 exported triangles, with
36 washing flights: 27 behind houses, including 12 on the opposite scenery banks.
The architecture review captured 37 native views of the corrected shells and
opposite stairs. The original 89 files and flooded backup's 81 files remain unchanged.

The final V5 curtain review held both pavilion cameras throughout the 48-second
sequence. Eight same-clock world/water swaps changed the final image by at most
three RGB levels out of 255; both final clearing transitions changed no pixels.
The actor and puzzle basin retained essentially all direct image contrast at
2, 4, 6 and 10 seconds, while the perimeter fog concealed the surroundings.
The distance-driven approach and both full retreat animations are saved as
`approach-sheet.jpg`, `curtain-retreat-5.gif` and `curtain-retreat-6.gif` under
`artifacts/huxin_canals_v5/`. A separate 100-frame sample at 640x360, including
GPU completion/readback, measured 8.19ms median and 17.69ms p95 on the review
machine; the thick-curtain phase measured 4.68ms median. All automated windows
were hidden and no audio device opened. `validation-summary.json` records the
exact scope: these are focused V5 checks, with the prior complete V4 traversal
retained below rather than repeated for shell winding and scenery changes.

The V6 fog revision replaces the sharp pavilion-shaped curtain and stretched
wisps with soft, asymmetric banks, warped three-dimensional billows and branching
filaments. Translucent foreground curls overlap a denser bank farther out;
uneven low mist conceals the changing water edge without covering the actor.
Direct and reflected views sample the same world-space cloud. Its illumination
has gentle tonal steps, while transparency changes continuously.

The muted V6 native review captured the complete 48-second sequence from both
pavilion views and two exterior diagnostic views. Sixteen same-clock swaps
(four views at four different clocks) changed the final image by at most one
RGB level out of 255, including the separate reflection-only comparisons.
All four clearing endpoints matched exactly. The player retained at least
75.8% of unfogged contrast and the puzzle basin at least 96.2% in the two
pavilion views. Frozen-clock camera sweeps check depth and parallax; isolated
60Hz fog-motion samples at four phases changed by at most one RGB level per
frame. Across the 170-frame capture in each pavilion view, render and readback
times were 12.23/12.35ms median and 16.62/15.21ms p95 at 640x360 on the review
machine. These are diagnostic timings, not a full gameplay benchmark.
The three reflection/uniform tests and ten sequence tests pass; all 170
protected original and flooded-backup files remain unchanged. Captures, GIFs,
source hashes and reports are under `artifacts/huxin-canals-fog-v6/after/` and
`artifacts/huxin-canals-fog-v6/after-motion/`.

V7 moves the heavy fog away from the pavilion and into the village. A 128x128
world-space coverage field is generated once from the exported house footprints,
with a four-metre feather and three-dimensional warping in the fog shader.
Open water receives only a lighter background haze and porous foreground wisps.
Broader noise octaves and five softly blended illumination bands give the banks
a coarser texture; opacity remains continuous. The logical encounter commits
once at eight seconds, while a separate quintic visual blend runs from five to
twelve seconds. Both endpoint worlds render their own depth, water plane and
fogged reflection before composition. Only those seven seconds require two
complete renders; the common player pose and held camera are evaluated once.

The V7 native review compares the two fog fields with identical world weights,
lighting and cameras. Mean retained outer-paving contrast rises from 5.7% to
83.6%; player and basin contrast remains above 99% in both pavilion views.
Four views at four clocks show no more than one RGB level of change across
the blend start, logical commit, blend end and final clearing boundaries.
The actual composite agrees with its weighted endpoint images to within one
RGB level. The prior V6 images, shader, viewer and sequence are preserved under
`artifacts/huxin-canals-fog-v7/before/`; V7 captures and reports are stored beside
that backup. All native reviews are hidden and muted.

The final V7 field uses 96 fixed ray intervals, with 30cm foreground steps;
the softer distant banks no longer require the former 128-sample curtain.
In warmed 90-frame samples with synchronized readback at 640x360, the two
pavilion views measured 24.7/25.6ms median during the seven-second blend,
with 27.5/30.6ms p95. Rendering returns to one endpoint afterward. The 19
focused CPU tests cover fog uniforms, sequence behavior and selection during
the blend; coverage-map invariants also pass. Final native captures are in
`artifacts/huxin-canals-fog-v7/final96/` and `final96-motion/`.
Both complete 48-second captures and the frozen-volume motion/parallax checks
pass with the production shader. All 89 original and 81 flooded-backup file
hashes remain unchanged.

The preceding V4 release passed all 64 CPU checks across the original scene suites, the canal suite and the
15-check final geometry recheck. The checks found a narrow gap between a porch
and its quay; the porch now meets the exact cut edge. Adjacent washing treads
also share their riser boundaries, verified with 624 exported-mesh rays placed
1mm to either side of those boundaries. The final floor scan uses all real
controller trajectories and excludes the hidden original causeway beyond z12.
The V4 native review completed 12,356 controller steps and all 42 excursions,
including nine routes through houses to their rear water stairs. All 580 player
visibility checks passed. The 48-second reveal kept the camera stationary,
measured at most one RGB level of change at the concealed swap, and zero change
at the end of the radial clearing. With the reflection plane held fixed, fog
reduced the hidden-world image difference by 77.3%. The final assets contain
1,311,004 exported triangles. The frozen flooded scene also passed its independent
muted launch, reveal and movement smoke check.
The preceding V3 release passed all 59 CPU checks across the existing scene suites and the final focused
recheck. The mesh checks caught low laundry and a jar intersecting doorway
approaches; both were moved before the final export, with all aperture and
capsule checks passing afterward.
The V3 native check walked 9,330 controller steps and measured a maximum
one-level RGB change at the concealed swap across the complete visible image,
with no camera movement. All 344 player-visibility samples passed. A focused
recheck after the northern camera adjustment passed all 165 doorway/stair
stations and 68 route stations. The assets contain 1,312,013 exported triangles.
The water-plane change legitimately alters the intermediate reflection's
projection. A separate comparison holding the reflection plane fixed measured
76.0% attenuation from fog. That buffer holds only the water-to-object optical
path; the complete image adds the camera-to-water segment and is the decisive
visible-reflection concealment check.
Only for a deliberate listening check that cannot be verified from the WAV or
runtime state, set `HAUNTED_TEST_AUDIO=1` for that test process; an explicit
`HAUNTED_MUTE_AUDIO=1` takes precedence. No system volume settings are changed.

```powershell
artifacts/temple3d-env/Scripts/python.exe -m unittest test_temple_living test_temple_cameras test_temple_gait_deck test_blender_assets -q
python temple_living_smoke.py
python moonlit_water_temple_3d.py --smoke
python temple_3d_viewer.py --smoke
python moonlit_water_temple_3d.py --structure-review
```

Tests cover input continuity across cuts, release/reorientation, boundary
overlap, diagonal speed, collision sliding, preventing tunnelling, and traversal
of the entire route through the real scene's collision data. The GPU smoke saves
thirteen route frames in both directions and checks the selected shot, walkability
and actor framing. Review images are in `artifacts/temple-camera-trial/`.
Living-asset captures, animation GIFs and the GPU verification report are in
`artifacts/temple3d-living/`. The check confirms changing GPU output while CPU
vertex buffers remain unchanged, and checks continuity at animation transitions.
The gait/deck checks cover planted contact, knee extension and flexion, rearward
arm/leg travel, continuous foot paths, supported boards and piers, stair height
agreement, collision around the separate structures, and preservation of the
original 2D arena.
