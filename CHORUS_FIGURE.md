# The Chorus figure study

The figure inspired by the far-left character in *The Chorus* is a separate
asset. The existing player and Redhead enemy have not been replaced.

## Compare the figure and player

Run `view_chorus_figure.cmd` to open the animation and proportion study. Choose
Idle, Walk, or Brisk walk; use the view and speed buttons to examine the
motion. Space pauses, the arrow keys step through frames, and the timeline can
be clicked to jump to a pose. Right-drag to orbit, use the mouse wheel to zoom,
and press P for a closer portrait. The light button switches between neutral
inspection lighting and moonlight.

## Try the figure in the lake scene

Run `play_chorus_figure.cmd` for a separate causeway study. Move the player with
W/S, turn with A/D, and hold Shift to run. The figure follows the player by
default; 1, 2, and 3 show idle, walk, and brisk walk in place, and 4 returns
to following. Space pauses the figure, R resets, right-drag orbits the camera,
and the wheel zooms. L changes the lighting, F4 switches player variants, and
H hides or shows the controls. This is an animation study: the figure does not
damage the player or change the existing enemy encounters.

The editable Blender file is `art/temple/chorus_grasper/chorus_grasper.blend`;
the animation actions are also kept in the separate
`art/temple/chorus_grasper/chorus_grasper_motion.blend` library. The build and
motion-loading code is in `build_chorus_grasper.py` and
`chorus_grasper_animation.py`. The unused earlier grasping-run action remains
in the motion library for possible future use. Both launchers are silent.
