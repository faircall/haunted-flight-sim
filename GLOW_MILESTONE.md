# Selective glow

## Linked light

Enable **Glow light** in the entity inspector to illuminate nearby surfaces,
entities and fog. Radius and intensity are independent controls; colour, pulse
and scripted brightness fades follow the glow. Light intensity multiplies the
evaluated glow strength. The source follows the centre of the displayed entity;
height follows half its body height plus elevation. It skips its own entity as
an occluder and respects other occluders and tile walls. It does not affect AI
visibility or add cinematic projected shadows. Zero brightness removes the
runtime light, and disabling preview removes these generated lights too.

Example: `set_glow(arena, door_id, light={"enabled": True, "radius": 80,
"intensity": 1.5})`. The same call accepts the glow colour and pulse settings.
Generated lights live only in runtime assets and use stable owner-based IDs.

## Edge motes

Enable **Edge particles** in the object's Glow inspector. Adjust motes/sec,
lifetime, drift, colour, and **Pulse emission**. Start at 12/sec and 1.5 seconds.
Particles float outward/upward and fade, contributing to the existing bloom.
They use the actual texture alpha boundary (or the evaluated rig's component
boundaries, rejecting covered seams). Puzzle placeholder objects use their
rectangular boundary. Foreground sprites obstruct motes through the shared mask.

Scripts can pass `particles={"enabled": True, "rate": 12, "lifetime": 1.5,
"drift": 7, "pulse_link": True}` to `set_glow`. An optional RGB `color` overrides
the glow colour. Turn emission off to let existing motes finish fading.

Limits: 512 live motes globally, 48 per object, 40/sec per object. Off-screen
objects stop spawning; elapsed-time jumps do not create catch-up bursts.
Texture alpha is read back only on a cache miss (at most one new texture/frame),
then shared across instances. There are at most 64 cached textures, each at most
262144 pixels; unsupported/oversized textures skip emission. PNG reload clears
the cache. Particle pools and caches live in game assets, not saved levels.

The hidden GPU stress test with eight statues, 30/sec and 380 live motes measured
5.614 ms without motes versus 7.814 ms with motes (median CPU submission time on
this machine, not a GPU timing guarantee). It verified one shared texture
readback. See `artifacts/glow/edge-motes.png`. Restart once for the new module and
shader reload registration.

Restart once to register `g_glow` and the two shaders with the hot-reload watcher.

Select an entity (including puzzle doors, keys, levers and keypads) in the
gameplay entity inspector. Enable **Glow**, choose RGB colour, strength (0–1),
and spread (small / medium / wide). These settings save with the level.
**Glow mode** distinguishes **whole** (the filled silhouette) from **edge**
(a one-world-pixel rim plus bloom). Existing objects retain whole mode; choose
edge for a statue aura that preserves its interior shading. Edge extraction
uses the complete evaluated silhouette, avoiding seams between rig parts.

**Glow pulse** offers **none**, **periodic**, and **random seeded**. Pulse speed
is cycles per second for periodic, or random target changes per second for
seeded variation. Depth controls how far brightness dips below the authored
strength (0 = steady, 1 = can fade completely). Random values interpolate
smoothly and retain their saved seed. Try edge + periodic, speed 0.5, depth 0.65
for a two-second breathing aura. Existing objects default to none.
Both rim emission and bloom follow the same pulse. Scripted fades multiply this
pulse rather than restarting it. `set_glow` accepts `pulse`, `pulse_speed`,
`pulse_depth`, and `pulse_seed` as optional arguments.

Edge mode also has **max rim width** (1–6 native pixels) and **rim expansion**
(0–1). The rim grows outward along the evaluated silhouette rather than scaling
the sprite. Expansion follows the selected periodic or seeded pulse, independently
of brightness depth: set pulse depth to zero for a steady-brightness moving rim.
Set rim expansion to zero for fixed width. Existing pulsing rims without an
authored width now breathe between 1 and 3 pixels. Non-pulsing rims retain 1 pixel.
Scripts can set `edge_width` and `edge_pulse` through `set_glow`.
**Min rim width** (`edge_min_width` in code) sets the contracted width, including
zero for no rim. Values below one pixel fade coverage smoothly to zero. The
minimum is clamped to the maximum width. Rim width and brightness are independent
controls sharing the pulse timing: brightness minimum is strength × (1 − pulse
depth), so depth 1 allows completely off. Use rim expansion 1 to reach the chosen
minimum width. Seeded random pulses approach their range endpoints rather than
guaranteeing a fully-off moment each cycle. Existing motes finish their lifetimes
even if the rim disappears.
The fire emitter inspector also has glow strength and spread; fire inherits its
animated core colour. Fire, embers and sparks have restrained glow by default.
Other objects opt in. Ember/spark glow can also be configured through their
ordinary `glow` dictionary.

Conditional effects use a procedural function returning the arena:

```python
import g_glow

# In a door-unlock or sequence-completion callback:
arena = g_glow.set_glow(arena, door["persistent_id"],
    color=[0.1, 0.8, 0.45], strength=0.6, spread="medium", mode="edge", fade=0.8)

# Later, fade it out:
arena = g_glow.set_glow(arena, door["persistent_id"], enabled=False, fade=1.0)
```

Targets can be persistent puzzle IDs, `collection:id` addresses, or `player`.
Missing/ambiguous targets raise an error rather than silently affecting another
object. Fades use arena `time_elapsed`, save their start/value/duration, and can
be retargeted without a brightness jump. Colours change immediately; strength
fades. Editor changes replace any active fade. Runtime changes live on the
object, so authored reset callbacks should explicitly disable glow if needed.

The emission layer draws actual sprite alpha and evaluated cutout poses, plus
the current puzzle placeholder shapes. Foreground sorted sprite silhouettes
mask object emission. A separable shader blur spreads only this emission; it
does not bloom the entire screen or the UI. Composition precedes rain/fog.
Three reusable render targets serve all spread groups. Groups without sources
are skipped. Existing emissive effect cores are captured separately for the
halo without adding their sharp core a second time.
An additional reusable silhouette target supports edge mode. Fire bodies,
hot cores, embers and fire bloom consult a shared per-pixel foreground depth
mask based on sprite ground sorting, so a foreground statue hides a rear fire.
Glow shader uniforms are explicitly separated between batched objects.

This is screen-space bloom, not an extra world light: it does not change AI
visibility or cast shadows, and its halo may bleed softly across nearby edges.
Individual rig-component emission masks, HDR exposure and physical scattering
are outside this milestone. No particle sequences or reflections are added yet.

Validation: `python -m unittest discover -q`, `python .glow_smoke.py`, and
`python .sequence_smoke.py`. The GPU check verifies halo pixels, orientation,
foreground masking, disabling, and resource reuse; its image is written to
`artifacts/glow/blue-glow.png`.
