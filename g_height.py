"""Physical render profiles, in world units. Plain data, independent of sprite size."""
import g_height_data as data


def resolve(entity):
    name = entity.get("height_profile", "auto")
    if name == "auto":
        name = "fallen" if entity.get("current_state") == "dead" else "upright"
    profile = dict(data.PROFILES.get(name, data.PROFILES["upright"]))
    profile.update(entity.get("height_overrides", {}))
    body = max(0., float(profile.get("body_height", entity.get("visual_height", 0.))))
    elevation = max(0., float(entity.get("elevation", 0.)))
    return dict(profile=name, body_height=body, elevation=elevation,
                sample_height=elevation + max(0., float(profile.get("sample_height", entity.get("light_sample_height", body*.55)))),
                projection=profile.get("projection", entity.get("shadow", {}).get("mode", "none")))


def project(point, height, light, light_height, maximum):
    """Project a point onto z=0; cap rays at/below the light plane."""
    import math
    dx, dy = point["x"]-light["x"], point["y"]-light["y"]
    distance = math.hypot(dx, dy)
    if distance < .000001 or height <= 0.:
        return dict(point)
    displacement = maximum if light_height <= height else min(maximum, distance*height/(light_height-height))
    return {"x": point["x"]+dx*displacement/distance, "y": point["y"]+dy*displacement/distance}
