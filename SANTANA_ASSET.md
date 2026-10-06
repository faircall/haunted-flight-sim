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
| Cabin | 4,950 |
| Lamp lenses | 8 |
| Four rounded tyres/domed wheel covers, 384 each | 1,536 |
| Steering wheel | 318 |
| Opaque car total | **12,732** |
| Six wet glass panes | 12 |

Characters, scenery, procedural moving wipers and headlight fog cones are outside
the opaque car count. The standalone Blender scene includes a held 48-triangle
wiper pose for inspection, so its car collection has 12,792 triangles with glass.
Its studio floor is separate from the asset collection.

| Texture sheet | Size |
| --- | --- |
| `art/temple/intro/santana_exterior.png` | 256x256 |
| `art/temple/intro/santana_interior.png` | 256x256 |
| `art/temple/intro/santana_wheels.png` | 128x128 |

The five GLBs embed their PNGs and have no external texture dependencies.
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
The broader [intro kit](art/temple/intro/intro_kit.blend) also contains colleagues,
the accepted seated player and countryside props.

Edit [build_santana_car.py](build_santana_car.py) for atlases and reusable mesh
helpers, [build_santana_body.py](build_santana_body.py) for the silhouette,
[build_santana_cabin.py](build_santana_cabin.py) for upholstery/interior, and
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
All inspection views hide actors; only the explicitly occupied view shows them.
It does not change cinematic or progress files. The
intro review additionally checks every cinematic cut, rainy glass, audio and
arrival. Export tests check complete assembled triangle counts, embedded texture
sizes/pixels, nearest filtering, UV bounds, non-degenerate triangles, silhouette
ratios, seated headroom, windshield/wiper alignment and camera classification.
