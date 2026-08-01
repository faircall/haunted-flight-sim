# Haunted Flight Sim renderer roadmap

The renderer uses serialisable authored dictionaries, transient flat render-item/light arrays, and GPU resources owned only by `game_assets`. `base_world`, `visual_height`, `light_sample_height`, `ground_footprint`, and the render-item policy dictionaries are the shared 2.5D description for lighting, shadows, outlines, future fog height, and future water interaction.

## 1. Entity rendering foundation — implemented

- Explicit world/entity/fog light destinations with one shared prepared wall-visibility result.
- Y-sorted render items for player, hostile entities, tall props currently represented by Buddha, and pickups.
- Directional upright entity lighting, omni/readability lighting, alpha-derived backlight rims, and world-style posterisation.
- Selective height-aware entity-to-entity direct-light blocking, separate from tile-wall DDA visibility.
- Height-aware upright shadows, grounded contact-shadow policy, and `none` policy.
- Policy-driven post-fog occlusion outlines with shared-player-occluder grouping.

Entities without a dedicated corpse type can adopt the grounded policy by merging the fresh dictionary returned by `g_render_order.make_grounded_entity_render_metadata()` into their authored render metadata.

## 2. Emitters and wind — next

Add serialisable emitter definitions and transient flat particle arrays. Particles must select an existing semantic pass (`floor`, `ground_projected`, `sorted_world`, `atmospheric`, or `readability`) and reuse render-item sorting when appropriate. Do not place GPU state in emitters.

## 3. Fog height

Consume render-item `base_world`, `visual_height`, `light_sample_height`, and `fog_interaction`. Do not introduce a second height convention or alter entity-light occlusion.

## 4. Liquids

Keep puddles and blood in the floor pass. Treat large water as an environment surface. Partial immersion must reuse render-item base/height and `water_interaction` metadata.

## 5. Optional refinement

Wall-projected shadows, baked sprite normal maps, reflections, advanced weather interaction, local wind zones, and soft smoke lighting remain deliberately deferred until milestones 2–4 are stable.

## Stable pass contract

1. Prepare shared lighting and transient render items.
2. Draw floor/base world and ground effects.
3. Draw ground/contact/cinematic shadows.
4. Apply world lighting to the base world only.
5. Draw sorted entities with prepared per-item lighting.
6. Compose atmosphere.
7. Draw readability outlines and gameplay markers.
8. Draw editor/debug/UI overlays.
