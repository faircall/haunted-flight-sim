# Santana car asset

The rainy intro uses a charcoal civilian Santana based on `artdev/car_reference.png`,
`artdev/car_reference_2.png` and `artdev/Classic Santana Vehicle Reference Sheet.png`.
The **21,996-triangle exterior car** keeps nearest-filtered 256/128px textures
and the game's colour quantisation.
The exterior allowance is 18,000–22,000 triangles. The latest fit pass adds 416
triangles for continuous bumper returns, enclosed sills and glazing joins.
The [supplied Santana video](https://www.youtube.com/watch?v=k1agHhirYR4) was inspected
frame by frame, particularly the exterior details around 00:29–00:43, the rear
quarter around 13:44–13:48 and the front bumper around 18:02. Silent reference
frame sheets are retained locally in `artifacts/santana-video/`.
Curved panels have smooth normals, with
geometry concentrated on body creases, rolled wheel arches, crowned roof/bonnet,
wrapped bumpers, mirrors and padded upholstery. The roof is a single closed
shell: crown, thin gutters, front/rear headers and inner skin share their
boundary vertices. Header stations follow the exact window corners, and the rear
roof corners taper into the C-pillars. Bevelled rubber surrounds overlap all six
glazing edges, including at oblique viewing angles.
The lower roof gutter recesses behind the door-window rubber, with extra relief
along the rear doors so their full upper black border stays visible. This fit
correction does not add triangles or change the window openings.
The front A-pillars follow the windshield and side-window edges. Broader rear
C-pillar sections roll into the body shoulder and nearly level trunk deck. The
rear glass has a longer rake into that deck; its side windows include the narrow
fixed quarter-light dividers. The narrower roof has a rounded crown and a longer
front slope. Its rim follows the window frames without a projecting slab.
Painted door-window frames meet the beltline around a recessed black center
post, closing the gaps between the B-pillars and doors. The post sits farther
forward to match the reference's front/rear door proportions. Matching interior
linings, door cards and belt guides follow these openings.
Finer wheel arches, more curved mirror housings, bumper corners
and 32-sided tyres with rolled wheel-cover rims improve close exterior views.
The body is proportioned from
the empty side view in `Classic Santana Vehicle Reference Sheet.png`, independently
of the occupants. Wheelbase is about 64% of overall length; side glass is
approximately 0.42m high. The wheels are 0.63m in diameter, with wider pressed arch
lips. Higher bumpers, rear lamps and lower valances follow the reference's panel
divisions. The rear wheel center sits 0.085m behind the side window's lower end.
The body is approximately 4.15m bumper to bumper, with a 0.48m trunk deck whose
longitudinal height varies by only 3mm, plus a shallow transverse crown.
Side-window openings are approximately 4–6% shorter than the preceding pass.
Both bumpers are closed U-shaped skins with rolled corners and tapered returns
toward the wheel arches; their texture bands follow the wrap continuously.
The narrower carpet floor sits above a sealed pan and behind the sill returns.
Sloping carpet returns now bridge the floor to the door cards, with front and
rear bulkheads closing the footwells from inside as well as outside. The headliner
and visors use worn charcoal-grey cloth. The unoccupied rear belts hang retracted
beside their C-pillar guides. Front belts are authored once, with the actors,
following the chest/pelvis surface and lap before meeting the buckles; the cabin
supplies their matching pillar guides and retractors.

The cabin has grey stitched cloth seats/headrests, seatbelt webbing and buckles,
manual window cranks, grab handles, speaker grilles, stepped dashboard, analog
instruments, radio, heater controls, vents, gearshift, handbrake, visors and mirror.
All texture pixels are authored by the generator; reference images are not
required to rebuild or run the game.

| Part | Triangles in game |
| --- | ---: |
| Body and exterior trim | 13,540 |
| Cabin used in exterior shots | 5,058 |
| Lamp lenses | 8 |
| Four rounded tyres/domed wheel covers, 768 each | 3,072 |
| Steering wheel | 318 |
| Opaque car total | **21,996** |
| Six wet glass panes | 12 |

Characters, scenery, procedural moving wipers and volumetric headlights are outside
the opaque car count. The standalone Blender scene includes a held 48-triangle
wiper pose for inspection, so its car collection has 22,056 triangles with glass.
Its studio floor is separate from the asset collection.

Interior shots use an independent **14,736-triangle** cabin, within the requested
12,000–15,000 budget. It replaces the lighter cabin and steering wheel rather
than rendering both versions together. Window openings, actor placements and
rain/wiper anchors remain shared with the reference-proportioned exterior.

| First-person part | Triangles |
| --- | ---: |
| Curved upholstery, dashboard, door cards and lining | 8,482 |
| Belt guides/retractors/webbing, buckles, pockets and other fittings | 5,544 |
| Detailed steering wheel, column and stalk | 710 |
| Opaque interior total | **14,736** |

The fittings include hollow shoulder-belt guides, pillar adjusters, retractor
housings, thin textured webbing, metal tongues, red release buttons and flexible
buckle stalks. Seat backs have padded cloth pockets and sewn welts; seat bases
have slide rails, hinges and recline wheels. Door latches, lock pulls, window
cranks, lower pockets and grilles are modelled for close inspection. Dashboard
details include vent slats, rotary controls, hazard switch, shifter bellows and
rear ashtray. The lining has visor hinges, grab-handle mounts and a dome fitting.
Opaque counts exclude actors and procedural wipers; six glass panes add 12.
The interior Blender collection totals 14,796 with glass and held preview wipers.

| Texture sheet | Size |
| --- | --- |
| `art/temple/intro/santana_exterior.png` | 256x256 |
| `art/temple/intro/santana_interior.png` | 256x256 |
| `art/temple/intro/santana_wheels.png` | 128x128 |
| `art/temple/intro/santana_cabin.png` (first person) | 256x256 |
| `art/temple/intro/santana_cabin_details.png` (first-person fittings) | 256x256 |

All eight car GLBs embed their PNGs and have no external texture dependencies.
The renderer retains the animated rain/refraction, wiper clearing arcs,
wheel rotation, steering and headlight transition. Glass, wheels and wipers use
the same anchors in Blender and the game, defined in `g_santana_geometry.py`.
Seated actors use a uniform 0.88 scale and separate front/rear seat translations
to fit the finished shell; their accepted source meshes and gameplay proportions
are unchanged. The stock portrait and back-seat camera poses follow the smaller
cabin. Camera/timeline data remains editable; custom camera keys are preserved.

Open [santana.blend](art/temple/intro/santana.blend) for an assembled car with
packed textures and front-quarter, rear-quarter, roof-seam, wheel/mirror and dashboard cameras. Its
`CAR / textured parts` collection is the asset; `STUDIO / cameras and lighting`
contains the inspection setup. The other scene holds the five export prototypes.
Open [santana_interior.blend](art/temple/intro/santana_interior.blend) for the
separate close-view cabin, with packed textures and back-seat, seat-back, rear
bench, belt-guide and dashboard cameras. Its `CABIN / textured parts` collection
contains the three first-person exports; the studio collection is preview-only.
The broader [intro kit](art/temple/intro/intro_kit.blend) also contains colleagues,
the accepted seated player and countryside props.

Edit [build_santana_car.py](build_santana_car.py) for atlases and reusable mesh
helpers, [build_santana_body.py](build_santana_body.py) for the silhouette,
[build_santana_cabin.py](build_santana_cabin.py) for upholstery/interior, and
[build_santana_fittings.py](build_santana_fittings.py) for close-view belt hardware,
seat pockets/welts, fittings and steering. Use
[g_santana_geometry.py](g_santana_geometry.py) for shared placement anchors.
Regenerate through the existing intro builder:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --python-exit-code 1 --python build_temple_intro_assets.py
```

Edits made directly in Blender are useful for exploration; regeneration replaces
the generated Blender files and exports. Copy a hand-edited scene before rebuilding.

```powershell
python temple_car_review.py
python moonlit_water_temple_3d.py --intro-review
python moonlit_water_temple_3d.py --cinematics-editor-review
python moonlit_water_temple_3d.py --intro-handoff-smoke
python moonlit_water_temple_3d.py --combat-smoke
python -m unittest test_santana_car test_temple_intro -q
```

`temple_car_review.py` uses the actual 480x270 intro renderer and writes
empty exterior/night views, orthographic side/front/top views, an occupied
back-seat view and an inspection contact sheet to `artifacts/santana-car/`.
`interior-review.png` collects the detailed cabin inspection views, including
belts, buckles, pockets, seat controls and night occupancy. Each native view
asserts that the appropriate exterior or first-person model is actually drawn.
`exterior-review.png` collects front/rear/night views and close-ups of both roof
headers, gutters, wheels and mirrors. Export tests weld the roof's texture/normal
seams and verify that its connected shell has no boundary edges, consistent
winding and positive enclosed volume.
Pillar tests also check that opaque roof corners remain below the roof profile
and inside its gutter width, and that both rear quarters and center door joints
remain opaque across their full height. `roof-quarter-review.png` collects close
views of both roof headers, the rear quarter, both center door joints and the side
profile. `pillar-comparison.png` reproduces the camera poses
from `screenshot000.png`, `screenshot001.png` and `screenshot002.png`, with their
original preview crops beside the updated in-game render. These temporary
inspection cameras never alter the saved cinematic shots.
General inspection views hide actors; occupied and screenshot-matching views show them.
`reference-comparison.png` crops both side profiles to their actual vehicle bounds;
`classic-shape-review.png` compares this shape pass with the previous native
profile at the same camera and scale. Export checks verify rear axle/window
alignment, overhang, wheel size, center-post placement, a nearly level trunk lid
and the exported arch crown's alignment with the runtime wheel anchor.
`body-fit-review.png` collects close-ups of both bumper returns, the lower sill,
rear window header, rear quarter and side silhouette. The native review now
captures 33 views. `rear-door-trim-comparison.png` matches the camera in the latest
`screenshot000.png`; a mirrored camera checks the opposite rear door. Visibility
rays check that the first surface along the upper rear-window border is black
rubber, rather than painted roof, across the screenshot and nearby viewing angles.
Export checks also verify that the bumper skins are closed
and outward-facing, their returns extend around both corners, floor corners are
occluded from outside, and angled rays cannot pass through the glazing/header join.
It does not change cinematic or progress files. The
intro review additionally checks every cinematic cut, rainy glass, audio and
arrival. Export tests check complete assembled triangle counts, embedded texture
sizes/pixels, nearest filtering, UV bounds, non-degenerate triangles, silhouette
ratios, seated headroom, windshield/wiper alignment and camera classification.
