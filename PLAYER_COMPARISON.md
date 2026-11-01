# Player candidate comparison

The original player and the new candidate have separate exported assets. The
original remains the default. To compare them in the Moon scene, open
`play_huxin_moon.cmd` and press **F4**. It switches the displayed player in
place, keeping the current movement phase, player position, and scene state.
The first switch loads the other character; subsequent switches reuse it.

Open `compare_player_3d.cmd` for synchronized side-by-side motion review. The
buttons select idle, walk, jog, backwards walking, turning and aim. Space pauses,
the arrow keys step through the animation, and the timeline can be clicked.
Right-drag to orbit both views; the mouse wheel zooms. View presets, playback
speed and the moving-ground grid are shared, so both characters are inspected
at the same phase and game cadence. The right-hand figure is the rebuilt player.
The review opens no audio device.

For jogging, press T or choose **Jog / sprint** to compare the retained sprint
on the original model at left with the relaxed jog on the rebuilt player at
right. Both travel at the normal game's speed, with a separate cadence for
each stride length. Press T again to compare both models jogging.

The candidate can also be selected for other 3D prototypes by setting
`HAUNTED_PLAYER_VARIANT=refined` before launching the desired scene. For example,
`play_huxin_canals_refined.cmd` starts the Canals scene with the candidate. The
normal launchers continue to use the original unless that variable is set.

The rebuilt player has connected trousers with a shared pelvis and crotch,
reshaped body contours and improved hands. Both player models use the relaxed
jog for normal running. The jog has a 33.5-unit stride (about 2.26 metres),
giving a 0.717-second cycle at the Moon/Canals speed of 3.15 m/s. Its editable
Blender source is `art/temple/player_refined/player_refined.blend`, and
`build_player_refined.py` rebuilds it. For cyclic clips the candidate also
interpolates between animation samples; the updated run is interpolated on
both models.

The jog is authored in `player_jog.py`, built by `build_player_jog.py`, and
stored in `art/temple/player_jog/`, including its own editable Blender file.
The runtime stride settings are in `g_player_locomotion.py`. The previous
sprint and its timing revision remain in `art/temple/player_run_timing/`.

The prior refined model is backed up in `art/temple/player_refined_previous/`.
The rebuilt player's upper arms and forearms are 9% shorter than the original
rig, with adjusted elbow/wrist joints and no extra fingertip extension. Shared
jog and sprint motion is retargeted to those lengths when loaded; the rigid
pistol copy is rebound to the same wrist so aiming and clip crossfades stay
aligned. The longer-arm rebuild is kept in `art/temple/player_refined_long_arms/`.

The earlier procedural locomotion experiment is preserved in
`art/temple/player_refined_procedural/` and `player_gait_v2.py`. Passing
`--procedural-gait` to the Blender build opts into that experiment; the normal
build keeps the accepted original actions.
