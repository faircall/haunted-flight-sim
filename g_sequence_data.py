"""Reloadable callbacks and audio choices for world sequences."""
SOUNDS = {"none": None, "ignite": "weapon_unholster", "rumble": "reload_start", "complete": "pickup_health"}
MUSIC = {
    "silence": None,
    "ritual_bells": {"path": "sounds/ambience/bells/bell_loop.wav", "gain": 0.35},
}


def start_linked_sequence(arena, event):
    import g_sequences as s
    trigger = arena["world_sequences"]["triggers"][event["source"]]
    restart = trigger.get("restart_sequence", False)
    if "demo" in arena["world_sequences"] and trigger["sequence"] == arena["world_sequences"]["demo"]["sequence"] and (restart or trigger["sequence"] not in arena["sequence_state"]["sequences"]):
        arena = s.change_music(arena, "ritual_bells", 2.)
    return s.start_sequence(arena, trigger["sequence"], restart=restart, origin=event.get("position"))


def spawn_linked_encounter(arena, event):
    import g_sequences as s
    return s.spawn_encounter(arena, event["data"]["encounter"])


def courtyard_completed(arena, event):
    import g_sequences as s
    import g_puzzles as p
    arena = s.change_music(arena, "silence", 3.0)
    arena = p.set_fact(arena, "courtyard_guardians_defeated", True)
    door = p.get_object(arena, event["data"]["door"])
    if door is None:
        raise ValueError("Courtyard exit was deleted")
    return p.unlock_door(arena, door)


HANDLERS = {"none": None, "start_linked_sequence": start_linked_sequence,
            "spawn_linked_encounter": spawn_linked_encounter,
            "courtyard_completed": courtyard_completed}
