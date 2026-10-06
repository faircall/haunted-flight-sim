# Santana car asset

The rainy intro uses a charcoal civilian Santana based on `artdev/car_reference.png`,
`artdev/car_reference_2.png` and `artdev/Classic Santana Vehicle Reference Sheet.png`.
The roughly 12,000-triangle rebuild keeps nearest-filtered 256/128px textures
and the game's colour quantisation. Curved panels have smooth normals, with
geometry concentrated on body creases, rolled wheel arches, crowned roof/bonnet,
rounded bumpers, mirrors and padded upholstery. The body is proportioned from
the empty side view in `car_reference_2.png`, independently of the occupants:
the roof spans about 33% of the car length, the wheelbase about 63%, and side
glass is approximately 0.40m high. The earlier long roof and tall windows have
been replaced with a shorter cabin, thicker doors and longer bonnet/boot.

The cabin has grey stitched cloth seats/headrests, seatbelt webbing and buckles,
manual window cranks, grab handles, speaker grilles, stepped dashboard, analog
instruments, radio, heater controls, vents, gearshift, handbrake, visors and mirror.
All texture pixels are authored by the generator; reference images are not
required to rebuild or run the game.

| Part | Triangles in game |
| --- | ---: |
| Body and exterior trim | 5,920 |
| Cabin used in exterior shots | 4,950 |
| Lamp lenses | 8 |
| Four rounded tyres/domed wheel covers, 384 each | 1,536 |
| Steering wheel | 318 |
| Opaque car total | **12,732** |
| Six wet glass panes | 12 |

Characters, scenery, procedural moving wipers and headlight fog cones are outside
the opaque car count. The standalone Blender scene includes a held 48-triangle
wiper pose for inspection, so its car collection has 12,792 triangles with glass.
Its studio floor is separate from the asset collection.

Interior shots use an independent **14,880-triangle** cabin, within the requested
12,000–15,000 budget. It replaces the lighter cabin and steering wheel rather
than rendering both versions together. Window openings, actor placements and
rain/wiper anchors remain shared with the reference-proportioned exterior.

| First-person part | Triangles |
| --- | ---: |
| Curved upholstery, dashboard, door cards and lining | 8,374 |
| Belt guides/retractors/webbing, buckles, pockets and other fittings | 5,796 |
| Detailed steering wheel, column and stalk | 710 |
| Opaque interior total | **14,880** |

The fittings include hollow shoulder-belt guides, pillar adjusters, retractor
housings, thin textured webbing, metal tongues, red release buttons and flexible
buckle stalks. Seat backs have padded cloth pockets and sewn welts; seat bases
have slide rails, hinges and recline wheels. Door latches, lock pulls, window
cranks, lower pockets and grilles are modelled for close inspection. Dashboard
details include vent slats, rotary controls, hazard switch, shifter bellows and
rear ashtray. The lining has visor hinges, grab-handle mounts and a dome fitting.
Opaque counts exclude actors and procedural wipers; six glass panes add 12.
The interior Blender collection totals 14,940 with glass and held preview wipers.

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
packed textures and front-quarter, rear-quarter and dashboard cameras. Its
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
All inspection views hide actors; only the explicitly occupied view shows them.
It does not change cinematic or progress files. The
intro review additionally checks every cinematic cut, rainy glass, audio and
arrival. Export tests check complete assembled triangle counts, embedded texture
sizes/pixels, nearest filtering, UV bounds, non-degenerate triangles, silhouette
ratios, seated headroom, windshield/wiper alignment and camera classification.
