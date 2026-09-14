# Inventory and descriptions

Restart once to register the new hot-reload modules. Thereafter edit
`g_interaction_data.py` while the game runs.

## Trying it

* In play mode, **Tab** opens the eight-slot inventory. Arrow keys select a slot;
  **E/Enter** uses medicine. **Escape/Tab** closes it. Hide editor panels with
  **F10** if the pointer is over a panel and gameplay interaction is captured.
* Place the existing health pickup, pistol ammo pickup, or puzzle key in entity
  mode. Approach it and press **E**. **Left/Right** selects Yes/No; **E/Enter**
  confirms. No is initially selected. Escape cancels. Full inventory leaves the
  object in place, including when a whole ammo pickup cannot fit.
* Ammo stacks to 60 rounds per slot. Medicine and keys occupy one slot each.
  Medicine restores its authored `value`, capped at player maximum health (100
  by default); it is not consumed at full health. Ammo is consumed from inventory
  by reloading. Loaded rounds and the currently equipped pistol are outside the
  grid for this milestone. `g_infinite_ammo` is now False; it remains a debug flag.
* Keys retain their puzzle group and automatically satisfy the existing door
  handlers. They are retained after unlocking, because several doors can share
  a key. There is no discard or storage-box system in this milestone.
* Place **inspectable** in entity mode. Its inspector offers a description ID.
  `old_inscription` demonstrates two pages and a Yes/No button. Saying Yes records
  `inscription_button:<persistent_id>` in puzzle facts and opens a follow-up page.
* A selected Buddha also has a **description** dropdown: choose `statue` or any
  authored description, or `none` to remove its interaction.

Inventory/dialogue/keypad input pauses movement, combat and sequence progression.
The opening and closing frames also consume gameplay input. These UI states are
transient; saves keep inventory and world facts but reopen with no modal.

## Authoring

`g_interaction_data.py` holds item stack limits, localization strings, description
definitions and named handlers. Keep description and callback IDs stable.

```python
DESCRIPTIONS["shrine"] = {
    "speaker": {"en": "Inscription", "zh_hans": "铭文"},
    "pages": [{"en": "Light the incense?", "zh_hans": "点燃香吗？"}],
    "choices": [
        {"label": "yes", "handler": "light_incense"},
        {"label": "no"},
    ],
}

def light_incense(arena, event):
    import g_puzzles
    # Can also call sequence/spawn/door functions here.
    return g_puzzles.set_fact(arena, "incense_lit", True)

HANDLERS["light_incense"] = light_incense
```

Handlers take `(arena, event)` and return the arena. Events contain `target` and
`choice`. A handler may call `g_interactions.open_dialogue(...)` for another page
or choice. For a description without choices, `on_complete` names a callback that
runs after its final page is acknowledged; Escape does not invoke it. No callable
objects or suspended Python execution are stored in saves. Camera choreography,
voiced dialogue and scripted AI remain future cutscene work.

## Chinese text

Set `LANGUAGE` to `en`, `zh_hans`, or `zh_hant` in `g_interaction_data.py`.
The new inventory/description UI uses the matching Fusion Pixel 12px proportional
font from `fonts/`. English uses the Simplified variant, which includes Latin.
String dictionaries fall back to English. The sample descriptions, item labels,
item explanations and main controls include both Chinese variants. Existing
editor, door/keypad and debug text remain in their existing English renderer.

Text measurement and wrapping share the loaded font. Chinese wraps between
characters with basic punctuation handling; English prefers word boundaries.
Long pages paginate in four-line chunks rather than drawing outside the panel.
The atlas loads authored codepoints, expands for new text, and reloads after a
font-file change. It uses point filtering. Keep the font license files in builds.

## Persistence and older saves

Slots live in `player_info['inventory']`; ammo's old reserve field is a derived
compatibility value. Older saves migrate reserve rounds and group-key counts
once. Excess legacy items are retained in `inventory_overflow`; **R** in inventory
claims those stacks when space permits. This prevents silently deleting older
save contents. Reset puzzle progress clears keys (including legacy overflow),
allowing the corresponding world keys to be collected again.

## Verification

`python -m unittest discover -q`

`python .inventory_smoke.py` renders both Chinese variants and English, checks
sample glyphs and exports panels under `artifacts/inventory/`.

`python .inventory_game_smoke.py` exercises inventory and key confirmation through
the real hidden game loop. Neither script modifies authored levels.
