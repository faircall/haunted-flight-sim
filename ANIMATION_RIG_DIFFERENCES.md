# Player and redhead rig differences

Both rigs sample four equally spaced poses per walk/run cycle, blend between
walk and run, and derive gameplay phase from the shared footstep clock. Left
mirrors right. They use the same basic transform and interpolation helpers.

| Feature | Player | Redhead |
|---|---|---|
| Authored canvas | 32 x 32 pixels | 24 x 24 pixels |
| Side legs/arms | Upper-limb and knee/elbow angles | Upper-limb and knee/elbow angles |
| Front/back legs | Independent knee X/Y and foot X/Y offsets | Whole straight-leg vertical lift |
| Front/back walking arms | Shoulder/elbow angles | Side gait angles with front-view scale factors |
| Front/back running arms | Elbow X/Y and hand X/Y offsets | Side gait angles with front-view scale factors |
| Body controls | Vertical bob and torso angle | Horizontal/vertical translation, side/front torso angles |
| Directional data | Separate up/down leg and arm tracks | Shared gait with front-view controls |
| Held items | Aim, gun, flashlight and reload poses | No held-item pose system |

The offset fields represent different geometry, not merely extra tuning knobs.
The player's front/back evaluator constructs joint positions, then derives
segment angles and lengths/scales from the resulting vectors. This allows
foreshortening: a leg can appear shorter as it moves in depth. Its side view
mainly rotates fixed-length segments. Knee-bend signs also differ between the
two side evaluators, so copying an angle table verbatim is not equivalent.

The redhead uses a smaller cutout rig. Its front/back legs deliberately remain
straight and move vertically in fixed lanes. Applying its side rotations in
those views previously caused lateral scissoring and inward-pointing knees.
Whole-leg lift removed those artifacts, but provides less control than the
player's individual knee/foot targets. Its arm artwork also has different bind
vectors: the front/back arm pieces are diagonal rather than the player's
vertical bind pieces.

The player editor now exposes its existing directional offsets; its motion
values were preserved during the migration. Redhead feature parity would need
an additional target-position/foreshortening path in its evaluator, with zero
offset defaults that preserve the current appearance. Prefer vertical knee,
foot, elbow and hand controls first, making lateral offsets optional. Merely
adding similarly named constants would not change how its limbs are built.

## Redhead cycle correction

The inspected redhead had no transform discontinuity at the loop boundary, and
its near/far render order stayed constant. Its recovery poses were assigned to
the wrong half-cycle: the forward contact leg lifted immediately instead of
supporting the body. This made the apparent foot path resemble a backward step.
The walk torso also alternated between forward and backward lean.

The corrected sequence is near contact, far recovery, far contact, near
recovery. The walk holds a small forward torso lean and removes horizontal body
shuttling; the run's recovery knee bend is reduced to avoid its former extreme
lower-leg excursion. Geometry tests check support/recovery timing, limb identity,
small adjacent changes, and continuity around every keyframe and the loop wrap.
