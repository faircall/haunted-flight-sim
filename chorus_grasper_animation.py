"""Editable animation library for the figure inspired by The Chorus.

The six skinned actions are kept in a separate Blender library so artists can
edit their curves independently of the generated character mesh. The build
script appends them onto the shared 15-bone rest rig before exporting glTF.
All distances are in the rig's author units; the game scales them to metres.
"""
from pathlib import Path

MOTION_LIBRARY = (Path(__file__).resolve().parent / 'art' / 'temple' /
                  'chorus_grasper' / 'chorus_grasper_motion.blend')

GAITS = {
    'enemy_walk': dict(stance=.62, front=4.4, back=4.4, lift=.8,
                       heel=7., toe=19., speed=1.),
    'enemy_run': dict(stance=.40, front=4.8, back=5.6, lift=1.7,
                      heel=9., toe=25., speed=2.4),
}
for gait in GAITS.values():
    gait['stride'] = (gait['front'] + gait['back']) / gait['stance']

WALK_STRIDE = GAITS['enemy_walk']['stride']
RUN_STRIDE = GAITS['enemy_run']['stride']
WALK_SPEED = GAITS['enemy_walk']['speed']
RUN_SPEED = GAITS['enemy_run']['speed']
# The active fast movement is a brisk walk, using the same footfall and arm
# pose as the walk. The original run action stays in the editable library for
# future experiments, but is not used by the character study.
BRISK_WALK_SPEED = 1.4

CLIP_SECONDS = {
    'enemy_idle': 2.5,
    'enemy_walk': 1.,
    'enemy_run': 1.,
    'enemy_attack': 1.,
    'enemy_stagger': .35,
    'enemy_death': .9,
}


def apply_actions(rig):
    """Append the authored actions to *rig*; return the export durations.

    Blender's exporter collects actions by name, so first remove actions with
    conflicting names left in the source combat kit. They are not used by this
    independent build, whose objects have already been removed.
    """
    import bpy

    for name in CLIP_SECONDS:
        old = bpy.data.actions.get(name)
        if old is not None:
            bpy.data.actions.remove(old)
    with bpy.data.libraries.load(str(MOTION_LIBRARY), link=False) as (source, dest):
        missing = set(CLIP_SECONDS) - set(source.actions)
        if missing:
            raise RuntimeError(f'Chorus motion library is missing actions: {sorted(missing)}')
        dest.actions = list(CLIP_SECONDS)
    for action in dest.actions:
        if action is None:
            raise RuntimeError('Failed to load a Chorus action')
        action.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = bpy.data.actions['enemy_idle']
    return dict(CLIP_SECONDS)
