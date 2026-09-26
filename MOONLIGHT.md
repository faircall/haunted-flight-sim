# Moonlit exteriors and warm openings

## Review scene

Run `python night_trial.py` for a separate courtyard scene. Walk towards the
building, then use **E** at the centre door. It uses the existing puzzle-door
interaction and collision system. **F10** reveals the editor. The launcher does
not replace a saved level.

The window lattice and door holes project patterned light onto the ground. The
scene includes a willow, procedural grass, cool moonlight, warm interior lamps,
and a small amount of illuminated haze.

## Add moonlight to a level

1. In **tile → rain_exposure**, paint **Exposed** over outdoor areas. Mark roofed
   rooms **Covered**. Moonlight uses the same sky-exposure data as rain. Untouched
   maps default to covered, so enabling moonlight alone does not expose them.
2. In **environment → World → Moonlight**, choose **Moonlit night preset**.
3. Adjust colour, intensity, azimuth and elevation. Azimuth is the direction the
   light travels/shadows extend: 0° right, 90° down. Lower elevation lengthens
   shadows. Wall height is the shared shadow-casting height for tile walls.

Moonlight has no radial falloff. It uses a cached world light map containing
parallel wall shadows and sky exposure. It contributes to ground, entity response
maps, fog and optional gameplay exposure. Existing point/spot lights still work.

## Add windows and pierced doors

In **environment → place**, choose **Window Wall**, **Pierced Door**, or
**Wood Wall**. These are front-facing upright panels, anchored at the centre of
their bottom edge. Place them on a 16-pixel grid so their collision cells line up.
They add derived collision footprints without replacing painted floor materials.

The object inspector provides:

- Width, height, grain seed and movement-blocking toggle.
- **Lamp:** `builtin` gives the opening its own warm interior source. Choose an
  existing point-light ID to follow that lamp's position, height, colour,
  intensity, radius and enabled state.
- Built-in lamp colour, intensity, height and depth behind the wall.
- Spill length and transmission.
- For a pierced door: **preview open**, or **door** to link an existing puzzle
  door. A linked door's actual state takes precedence over the preview checkbox.

Place the source **behind the panel** (smaller world Y), with enough height to
shine down through the opening. Apertures above the lamp do not project onto the
floor. The built-in lamp lights the opening/spill; a linked point light also
provides the room's normal interior illumination.

Window bars and door holes affect light without creating holes in movement
collision. Obstacles beyond an opening clip its spill. Opening a linked door
expands its aperture and removes the panel's collider; normal puzzle checks still
prevent closing on an actor. Avoid painting a permanently solid wall tile under
a doorway, since that independent wall collider would remain.

## Scope of this pass

This is an authored 2.5D aperture projection, not full volumetric ray tracing.
Panels currently face screen-down; alternate wall orientations and animated door
hinges can build on this system. Window emission follows world depth order so
actors in front cover it. The mask is a glowing pane/interior treatment rather
than a fully rendered view through glass.

Moon shadows currently use tile/facade footprints with a shared wall height.
Trees receive directional moonlight through their existing response maps; tree
silhouette shadows from the moon are not added in this pass. The spill clip uses
one visibility origin per opening, an approximation for very wide apertures.

Light fields and facade textures regenerate on relevant edits, lamp changes or
door changes and are reused on ordinary frames. Facade resources are limited to
the view plus their spill reach. The moon field covers the authored map, so very
large maps may eventually need chunked storage. The original art is untouched;
panel frames and grain are procedural and share the existing surface palette.

Saving and undo preserve authored profiles and panels. Derived GPU resources
are held outside saved game state and are released on removal/map changes.

## Validation

```text
python -m unittest test_night test_light_visibility test_editor_ui test_editor_history test_puzzles test_entity_self_shadow test_tile_collision_override test_gameplay_line_of_sight test_surfaces -q
python .tree_game_smoke.py --night
```

Review images are written to `artifacts/night/`.
