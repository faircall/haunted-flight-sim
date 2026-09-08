# Triggers, lighting sequences and encounters

Restart once to register the new hot-reload modules. Select **sequences** in the
mode dropdown, or use F8 to cycle to it. The mode has a separate toolbar and a
scrolling inspector. All authoring data is saved by the existing F5/F6 workflow.

## Try the complete example

1. Move the editor camera over a clear floor area, at least 180 by 180 world
   pixels, with room inside the map boundaries.
2. Select **sequences**, then **Place courtyard demo** in the inspector.
3. The tool adds six torches, a cyan entry area, two enemy spawn markers, and a
   locked exit. It does not repaint your level. Place the demo on floor, because
   its door does not remove an underlying wall and solid spawn points will wait.
4. Switch to play, begin outside the entry area, then walk into it. The torches
   ignite in order with placeholder start, ignition and completion sounds.
5. When the final torch finishes brightening, two redheads spawn. Defeat both:
   the exit unlocks and the temporary ritual bell music fades to silence.

The bell loop is an existing asset used as a music placeholder. Additional music
tracks are ordinary entries in `g_sequence_data.MUSIC`; no new soundtrack assets
are included. The example is opt-in and can be placed once per level. The existing
**Reset puzzle progress** button resets the whole chain, including sequence and
encounter progress, while retaining placed definitions. Keep actors off doors
when using that reset.

## Ordered placement

Choose a toolbar tool:

- **Pick existing:** click fire emitters or lights in order. Orange/blue handles
  show eligible objects, including inactive torches.
- **Place torches:** click each desired position. The draft shows numbered
  points and arrows. Torches are created only when you finish.
- **Circle:** click and drag from centre to radius. Adjust count, starting angle
  and direction in the inspector. Enable **Continuous fire path** to generate
  a closed fire path instead of separate torches.
- **Fire path:** click control points. Straight segments connect them.

**Finish / Enter** commits a draft. **Backspace** removes its latest entry.
**Cancel / Escape** discards it without creating torches. Changing tools or
leaving the mode also discards the unfinished draft.

Select a sequence in the inspector or click one of its objects. **Move member**
drags a torch/light or path point without changing its identity. **Insert member**
adds at the clicked connection (picking a nearby existing object or creating a
torch). **Append existing objects** builds an additional ordered draft.
The member number, **Remove member**, **Start at member**, and **Reverse** controls
edit order; the visible badges and arrows reflect playback order. On an object
sequence, reverse preserves the chosen first member and reverses the remaining
order. Open paths reverse end-to-end; closed paths also support a chosen start.

Torches bundle a fire emitter and its light. Their normal environmental fire
loop follows activation if matching fire-loop assets exist. Tune the fire/light
appearance in the existing environment inspector. **Initially lit** controls
the state before a sequence starts, including sequences made from existing lights.

## Timing, sound and preview

The sequence inspector controls delay, interval (objects) or speed/spacing
(paths), fade-in, hold, fade-out, direction and completion handler.

- **persistent:** each member stays lit after brightening.
- **pulse:** each member holds and fades independently, creating a travelling pulse.
- **fill:** the whole sequence fills, then holds and fades together.

Path timing uses distance along the path, independent of control-point spacing.
Generated paths are limited to **64 emission sites and 8 lights per path**;
spacing increases automatically for longer paths. Smooth spline curves and
scripted AI movement remain future work.

Choose start, activation and end sounds, plus an override for the selected
object member. **Pick sound origin** selects an object for start/end cues;
otherwise the triggering position is used (or the first member for a script
without a position). Activation sounds originate at their individual members.
`g_sequence_data.SOUNDS` maps the menu names to existing audio event types.

**Preview / pause**, **Stop preview**, and the time slider only affect a
temporary visual presentation. They never run callbacks, set gameplay facts,
or spawn enemies. Scrubbing is silent. **Audition sounds** enables sounds and
fire loops during actual preview playback. Changing timing values updates the
preview without changing a running gameplay sequence's saved definition snapshot.

## Trigger areas

**Trigger rectangle:** drag a region, then Finish. **Trigger paint:** paint an
irregular region, then Finish; hold Shift to erase. Select an existing trigger
and use **Edit painted area** to change its tiles while retaining its identity.

An area overlays tiles rather than replacing floor materials. Configure its
linked sequence, enter/exit handlers, actor category (player, enemy, all), initial
enabled state, and repeat policy (once, every entry, cooldown). Moving between
tiles inside the same area does not emit another entry event. Once applies once
per event type for the area; cooldown is tracked per actor and event type.

On load, occupancy is seeded from the actors' current positions without creating
synthetic entry events. Actor removal does not count as exiting. Enabling an area
around an actor can produce an entry on the next update. By default, starting a
sequence again is a no-op; **Restart linked sequence** makes repeated trigger
entries restart its timing explicitly.

## Encounters and chaining

Place **puzzle spawn** markers using entity mode. In sequences mode, choose the
**encounters** inspector category, create an encounter, and add markers. Each
entry has a spawn delay; different delays can form waves. This milestone supports
the existing redhead enemy. Additional types can be added to the spawn helper.

Select **spawn_linked_encounter** as a sequence's completion handler and choose
the encounter below it. Encounters expose their own completion handler. The
provided **courtyard_completed** handler lets you choose an exit door and uses
the bell-to-silence placeholder; custom reactions belong in Python.

An encounter records each spawned enemy's identity. It completes only after all
scheduled spawning has succeeded and every member has been defeated. A missing
or obstructed marker waits and appears as a diagnostic in the inspector. Deleting
or unloading a live enemy does not count as a kill. Repeated encounters use
explicit new generations, so previous kills do not satisfy a later encounter.

## Procedural API

All functions receive the arena and return it. Definitions live in
`arena['world_sequences']`; progress lives in `arena['sequence_state']`.
Neither contains function objects or audio/GPU handles.

```python
import g_sequences as sequences

def after_puzzle(arena, event):
    arena = sequences.start_sequence(arena, "my_sequence_id")
    return arena

def after_lights(arena, event):
    return sequences.spawn_encounter(arena, "my_encounter_id")

def after_fight(arena, event):
    return sequences.change_music(arena, "my_calm_track", fade_seconds=3.0)
```

Register callbacks in `g_sequence_data.HANDLERS`; their names then appear in the
editor. Callback events carry `type`, `source` and relevant fields: triggers have
`actor` and `position`; completions have authored `data`; encounter completions
also have `generation`. The full arena is available for custom puzzle state.

The inspector's name field commits with Enter. Start functions accept either the
persistent ID or a unique readable name; ambiguous names are rejected. **Copy
persistent ID** supplies a stable code reference even if the display name changes.

Other helpers include `set_trigger_enabled`, `set_torch_lit`, `torch_is_active`,
`record_defeat`, `reset_sequence`, `reset_trigger`, `reset_encounter`, and `queue_event`.
`start_sequence(..., restart=True)` explicitly restarts a sequence.
`spawn_encounter(..., restart=True)` creates a new generation after completion;
it does not duplicate a running encounter.

Sequence completion and encounter completion set persistent facts named
`sequence_completed:<id>` and `encounter_completed:<id>` under sequence state.
Logical torch activation is separate from visual brightness. The most recently
started sequence owns a shared target; explicit `set_torch_lit` overrides it until
another sequence starts. Authored brightness and emission values remain unchanged.

## Persistence and diagnostics

Sequence elapsed time, crossed activation events, encounter members, pending
callbacks, trigger progress and desired music are saved. Loading does not replay
one-shot sounds or create another enemy group. Music resumes the desired track
with a fade; it does not seek to a sample-exact playback position.

The event queue has a bounded per-frame dispatch budget, preventing recursive
callback chains from monopolizing a frame. Errors appear in the **event log**;
failed callbacks survive saves, and **Retry last failed event** is explicit.
Handlers are procedural, not rollback
transactions: validate prerequisites before side effects, and make custom retryable
handlers idempotent. The supplied example follows this pattern where relevant.

**Validate world links** checks references and handler names. The inspector also
flags missing sequence members. **Reset selected progress** resets just that
sequence, trigger or encounter; encounter reset removes enemies it spawned but
preserves unrelated enemies. Reset progress before deleting an active definition.

Validation commands:

```text
python -m unittest discover -q
python .sequence_smoke.py
```

The hidden full-game smoke covers torch/path rendering, all three inspectors,
triggered ignition, enemy spawning, defeat completion, music state and unlocking.
Preview images are written to `artifacts/sequences/`.
