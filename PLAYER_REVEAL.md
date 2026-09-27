# Seeing the player behind objects

Occlusion outlines are replaced with a small oval of partial transparency in objects that cover the player. The centre can become 65% transparent, with a feathered edge; the rest of each object stays opaque. The player retains their real sprite colours and lighting. No extra light or silhouette is painted over the scene.

The renderer checks the actual animated alpha masks on the GPU, rather than treating overlapping bounding boxes as proof of obstruction. Leaves, window openings and doorways retain their gaps. The response grows with the amount of the player covered, fades in over about 0.16 seconds and restores opacity over about 0.22 seconds. Several blockers can respond independently. Foreground objects, collision, shadows and physical light blocking keep their normal behavior.

The effect works with the roof cutaway fade. Only potentially blocking objects need an isolated colour pass; coverage is computed in a one-pixel GPU target with no CPU readback. Leaving an object frees its transition targets, and level changes/cleanup release the caches.

Settings are near the top of `g_player_reveal.py`: `TRANSPARENCY`, `FADE_IN_SECONDS`, `FADE_OUT_SECONDS`, `MIN_COVERAGE`, `FULL_COVERAGE`, and the master `ENABLED` switch. The oval size and edge are in `shaders/player_reveal_patch.fs`.

Objects can opt out with `player_reveal_enabled: False`. The **Fade to show player** checkbox is in the Entity inspector and the Environment inspector for walls/doors. The flag is saved with the object and supports editor undo; lake props also honor it in scene data. All willow variants default to off, including trees loaded from older saves. Individual trees can opt back in. This only controls the local transparency effect; collision, shadows and light blocking retain their existing settings.

The separate darkness outline remains disabled by default. If explicitly re-enabled via `PLAYER_DARKNESS_OUTLINE_ENABLED` in `g_graphics.py`, its threshold is now restricted to near-black pixels. Transparency alone does not make an unlit player glow.

Validation: `python -m unittest test_player_reveal test_render_order test_roofs test_night -q` and `python .tree_game_smoke.py --night`. Native comparison captures are in `artifacts/player-reveal/`.
