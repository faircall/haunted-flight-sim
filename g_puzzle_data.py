"""Hot-reloaded puzzle definitions and procedural example handlers."""

OBJECTS = {
    "key door": {"label": "Key door", "color": (184, 133, 49), "handler": "key_door"},
    "authored door": {"label": "Ritual door", "color": (154, 73, 178), "handler": "ritual_door"},
    "lever door": {"label": "Lever door", "color": (60, 159, 143)},
    "code door": {"label": "Code door", "color": (72, 126, 196)},
    "puzzle key": {"label": "Brass key", "color": (241, 203, 75)},
    "puzzle lever": {"label": "Lever", "color": (87, 193, 143)},
    "puzzle keypad": {"label": "Keypad", "color": (97, 178, 224), "code": "0451"},
    "puzzle spawn": {"label": "Ambush spawn", "color": (208, 83, 88)},
}


def key_door(arena, event):
    import g_puzzles as p
    door = p.get_object(arena, event["target"])
    if not p.has_key(arena, door):
        return p.message(arena, "Locked: find the brass key for this group.")
    return p.unlock_door(arena, door)


def ritual_door(arena, event):
    """Example: key AND pulled lever; unlock, spawn once, record a fact."""
    import g_puzzles as p
    door = p.get_object(arena, event["target"])
    if not p.has_key(arena, door):
        return p.message(arena, "Ritual door: a brass key is required.")
    levers = p.group_objects(arena, door, "puzzle lever")
    if not any(p.object_state(arena, lever).get("active") for lever in levers):
        return p.message(arena, "Ritual door: pull a lever in this group first.")
    markers = p.group_objects(arena, door, "puzzle spawn")
    if len(markers) != 1:
        return p.message(arena, "Ritual door needs exactly one spawn marker in its group.")
    # Validate before unlocking; a blocked marker leaves the puzzle retryable.
    if not p.spawn_is_clear(arena, markers[0]):
        return p.message(arena, "Ambush spawn is blocked. Clear the marked area.")
    arena = p.unlock_door(arena, door)
    arena = p.spawn_redhead(arena, markers[0], "unlock:" + door["persistent_id"])
    arena = p.set_fact(arena, "ritual_unlocked:" + door["persistent_id"], True)
    return p.message(arena, "The ritual lock releases. Something stirs nearby.")


def sequence_locked(arena, event):
    import g_puzzles as p
    return p.message(arena, "Defeat the courtyard guardians to release this lock.")


HANDLERS = {"key_door": key_door, "ritual_door": ritual_door, "sequence_locked": sequence_locked}
