# Render height and grounded shadows

Entities may author `elevation` (world units above the floor), `height_profile`
(`auto`, `upright`, `fallen`), and `height_overrides` (body_height, sample_height,
projection). These plain fields save with the entity. Auto selects fallen for
the dead state; standing entities retain their existing authored dimensions.
`g_height_data.py` contains shared hot-reloadable profile defaults.

Elevation shifts the sprite upward without moving its ground position or sort
anchor. Lighting sample height rises with it. Shadow rays use elevation plus
body height; lights below a projected point use the existing maximum distance.
Grounded silhouettes retain their floor orientation instead of being flattened
from an upright billboard. Their thickness determines displacement.

Animation editor: select the **height** group. Elevation and profile are preview
overrides, cleared by **Reset elevation preview**. Fallen height/light controls
adjust the shared profile live; **Save heights to code** writes g_height_data.py.
The fixed specimen preview shows sprite lift against its baseline; inspect a
level entity under the flashlight to see the projected shadow. The existing
cinematic shadow debug overlay shows elevation, body height and footprint.
Restart once to register the new modules with the reload watcher.

This is a floor projection approximation: the corpse uses one low plane and a
conservative sprite-sized footprint, not per-pixel thickness. Existing upright
shadow styling remains available. This does not add jumping input, airborne
collisions, shadow receivers on walls, or shadows from additional lights.
Foot contact shadows remain disabled by their existing master toggle.
