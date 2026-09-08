# Puzzle prototype milestone

Restart the game once after installing these changes so the new Python modules
join the hot-reload watch list. Existing levels do not need conversion.

In **entity** editor mode, use **place** and the existing entity selection wheel
to choose the new types below. Use **select** to edit their **puzzle group**.
Objects in the same group are connected; the floating label shows the group.
Use separate groups for independent puzzles. Every placed object also receives
a persistent UUID, which survives moving and saving; a replacement gets a new ID.

| Example | Place in the same group | Play interaction |
| --- | --- | --- |
| Simple key lock | `key door`, `puzzle key` | E collects the key; E unlocks the door; E again opens it. |
| Authored ritual lock | `authored door`, `puzzle key`, `puzzle lever`, exactly one `puzzle spawn` | Collect the key, pull the lever, then E at the door. It unlocks and spawns one redhead. E again opens it. |
| Lever control | `lever door`, `puzzle lever` | E at the lever opens/closes all lever doors in its group. |
| Four-digit code | `code door`, `puzzle keypad` | E at the keypad; type **0451**, then Enter. Matching code doors unlock and open. |

The key is retained and can unlock multiple doors in its group. The ritual
lever also controls any lever doors in that group. Once unlocked, doors can be
opened/closed directly with E; the lever additionally provides remote control.
An occupied doorway cannot close on the player or a living enemy.

Keypad controls: number keys, Backspace, Enter, Escape. The code is stored as a
four-character string, preserving leading zeroes. Its inspector can change it.
Movement/combat and enemy updates pause while entering a code. There is no input
timeout. Leaving play mode or opening an editor/options modal cancels entry.

Doors occupy the **whole tile containing their position**. Place them on clear
floor in a doorway; opening a door does not remove an underlying authored wall.
Closed doors block movement, pathfinding, bullet traces and light. Opening,
moving or deleting a door refreshes the derived tile geometry. These first
placeholders are instant open/closed rectangles, with no swing animation.
Keys, controls and spawn markers can be moved freely. Spawn markers appear only
in editing modes; leave enough clear floor for the enemy's collision box.

Unlocking uses the existing reload sound; opening/closing uses unholster.
Floating labels and colors are placeholders. The key inventory is currently
puzzle-only; it has no inventory screen or item-combining interface yet.

## Authoring Python behavior

`g_puzzle_data.py` contains ordinary data and named functions. `ritual_door` is
the authored example. The door's `on_unlock` string selects a function from
`HANDLERS`; the inspector lists registered handlers. Add a function and registry
entry there, then select it on a door. No function objects are serialized.

```python
def custom_unlock(arena, event):
    import g_puzzles as p
    door = p.get_object(arena, event["target"])
    if not arena["puzzle_state"]["facts"].get("power_restored", False):
        return p.message(arena, "There is no power.")
    arena = p.unlock_door(arena, door)
    arena = p.set_fact(arena, "opened_the_way", True)
    return arena
```

Handlers have the full arena and must return it. Top-level fields use persistent
map replacement; nested entity and puzzle dictionaries follow the existing
mutable convention. These are not rollback transactions: validate prerequisites
before changing state, as the ritual handler does for its spawn marker.
The unlock handler runs on interaction while the door is locked, not every frame.

`g_puzzles.py` supplies procedural helpers for state, spawning, door geometry and
interaction selection. `g_puzzle_ui.py` contains the placeholder editor/input/UI.
These modules hot reload without resetting progress. UI and pending sound state
are transient and excluded from editor saves; inventory, door/lever state,
spawn records, enemies and custom facts survive the existing F5/F6 save/load.
Spawn records prevent the same ritual from spawning again after a kill or load.

**Reset puzzle progress** in any puzzle inspector resets every puzzle group,
restores collected keys, closes/relocks doors, and removes enemies spawned by
these puzzles. It preserves placed definitions and ordinary enemies. Move actors
off doorway tiles first. This is an explicit editor testing action.

Validation: `python -m unittest test_puzzles -q`; `.puzzle_smoke.py` runs a hidden
full game with all inspectors, keypad keyboard input and the authored spawn,
and writes preview images under `artifacts/puzzles/`.
