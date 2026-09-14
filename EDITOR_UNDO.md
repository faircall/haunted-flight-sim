# Editor undo

Press **Ctrl+Z** in tile, entity, environment or sequences mode. Each held mouse
stroke/drag is one step, including slider drags. Discrete edits such as placement,
deletion, dropdown choices, numeric commits and sequence commands are separate
steps. Undo shows a short status message at the bottom of the screen.

Covered data:

* Tile appearance/shape/forced collision, rain exposure, acoustic zones and
  footstep overlays; tile-type settings.
* Entity placement, deletion, movement, glow and authored behaviour settings.
* Lights, fog volumes, emitters, sound emitters and environment profiles.
* Sequence definitions, trigger areas and unfinished sequence drafts.

Animation mode routes Ctrl+Z to the selected character's existing animation draft
history. It does not undo files already written by Save to Code, or direct edits
to Python files/global constants (including the height-profile controls).

If a numeric text field is focused, Ctrl+Z first cancels that uncommitted text
edit. Press it again to undo a committed editor operation. Holding the mouse
after undo cannot immediately paint the change back; release before resuming.

History keeps up to 100 transactions in `game_assets['editor_history']`. It is
not saved with a level. Loading/resetting a level or entering play clears history,
so undo cannot accidentally rewind gameplay progress. Switching between level
editor modes retains history. Camera movement and selection alone are not edits.

Implementation: `g_editor_history.py` captures authored values at transaction
boundaries and stores only changed values in history. Long mouse gestures avoid
copying the map every frame. Entity restoration retains IDs, and undo refreshes
door blockers, actor collision indexing, and lighting/rain/effect derived data.

Validation: `python -m unittest test_editor_history -q` and
`python .editor_undo_smoke.py` (hidden real editor paint/undo check).
