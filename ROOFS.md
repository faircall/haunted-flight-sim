# Roofs and transparent openings

Window gaps, holes in closed doors, and open doorways now show the real scene behind them: floor textures, characters, and their lighting. Warm aperture glow is restricted to the solid frame edges. Linked puzzle doors keep their interaction and collision behavior; their old placeholder rectangle is hidden during play when a facade supplies the art.

## Painting roofs

1. Open the **Tile** editor and change **Tile edit** to **roofs**.
2. Select **Black roof**. Left-drag to cover the building's ground footprint, including its boundary wall cells. The existing floor, collision, and footstep settings stay underneath.
3. Right-click to fill a matching floor region. Add boundary cells with the brush as needed. Once a roof exists, right-click operates on that connected roof instead.
4. Use **Erase** with the same brush/fill controls to remove coverage.
5. **Height** raises the drawn roof above its footprint. The default is 44 pixels, matching the courtyard doorway; use the same height throughout a building.
6. The cyan grid shows coverage while editing. **Preview exterior** displays the black roof, even if the player is inside.

Four-neighbor connected roof tiles form one cutaway. The roof fades out when the player's feet enter its footprint, and fades back in on exit. Each fade takes 0.3 seconds with eased endpoints; turning around midway reverses it smoothly. The duration is `FADE_SECONDS` in `g_roofs.py`. Separate buildings stay covered. To make independently revealed rooms, leave a gap between their roof footprints; touching roofs currently reveal together.

Roof fields save with the level and participate in normal editor undo (Ctrl+Z). Roofs shelter against rain and direct moonlight even while hidden to show the interior. Removing a roof restores the tile's previously authored rain exposure; an explicitly marked covered floor stays covered.

## Review scene

Run `python night_trial.py` for the courtyard with its roof already painted. Existing saved levels keep their authored data; add roofs using the tile editor. The current black material is a placeholder for future roof sprites. Roofs use the existing 2D draw order and crisp pixel grid.

## Checks

- `python -m unittest test_roofs test_night test_tile_editor test_editor_history test_render_order test_rain -q`
- `python .tree_game_smoke.py --night`

The native check verifies actual scene pixels through apertures, frame glow, roof entry/exit, camera alignment, editor controls, and texture cleanup. Captures are written under `artifacts/night/` and `artifacts/roof-interior/`.
