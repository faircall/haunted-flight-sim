"""Bounded cosmetic motes; cached texture alpha, no per-frame GPU readback."""
import math
import time
import zlib
import pyray as pr

MAX_PARTICLES = 512
MAX_PER_OBJECT = 48
MAX_TEXTURES = 64
MAX_TEXTURE_PIXELS = 262144


def edge_samples(alpha, width, height, rect):
    x0, y0, w, h = rect
    points = []
    def solid(x, y):
        return x0 <= x < x0+w and y0 <= y < y0+h and 0 <= x < width and 0 <= y < height and alpha[y*width+x] >= 128
    for y in range(max(0,y0), min(height,y0+h)):
        for x in range(max(0,x0), min(width,x0+w)):
            if not solid(x,y):
                continue
            empty = [(dx,dy) for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)) if not solid(x+dx,y+dy)]
            if empty:
                nx, ny = sum(p[0] for p in empty), sum(p[1] for p in empty)
                length = math.hypot(nx,ny)
                if length == 0:
                    nx,ny = empty[0]; length = 1.
                points.append((x-x0+.5,y-y0+.5,nx/length,ny/length))
    stride = max(1, math.ceil(len(points)/256))
    return points[::stride]


def texture_edges(runtime, texture, rect):
    cache = runtime.setdefault("textures", {})
    key = (texture.id, texture.width, texture.height)
    if key not in cache:
        if runtime["reads_left"] <= 0 or len(cache) >= MAX_TEXTURES or texture.width*texture.height > MAX_TEXTURE_PIXELS:
            return []
        runtime["reads_left"] -= 1
        image = pr.load_image_from_texture(texture)
        colors = pr.load_image_colors(image)
        try:
            alpha = bytes(colors[i].a for i in range(image.width*image.height))
        finally:
            pr.unload_image_colors(colors)
            pr.unload_image(image)
        cache[key] = (alpha, {})
        runtime["readbacks"] = runtime.get("readbacks", 0)+1
    alpha, frames = cache[key]
    if rect not in frames:
        if len(frames) >= 64:
            frames.pop(next(iter(frames)))
        frames[rect] = edge_samples(alpha, texture.width, texture.height, rect)
    return frames[rect]


def shapes(runtime, item, assets):
    import g_graphics as g
    dest = item["dest_rect"]
    result = []
    if item.get("placeholder_edges"):
        for i in range(16):
            t = (i+.5)/16.
            result.extend(((dest["x"]+t*dest["width"],dest["y"],0.,-1.),
                           (dest["x"]+t*dest["width"],dest["y"]+dest["height"],0.,1.),
                           (dest["x"],dest["y"]+t*dest["height"],-1.,0.),
                           (dest["x"]+dest["width"],dest["y"]+t*dest["height"],1.,0.)))
        return result
    parts = item.get("draw_data", {}).get("cutout_rig_parts", [])
    if parts:
        for part in parts:
            texture = assets.get("textures", {}).get(part.get("texture"))
            if texture is None:
                continue
            points = texture_edges(runtime, texture, (0,0,texture.width,texture.height))
            pivot, origin, scale = part["pivot_local"], part["origin"], part.get("scale", {})
            angle = math.radians(part.get("rotation", 0.))
            c,s = math.cos(angle), math.sin(angle)
            transformed = []
            for x,y,nx,ny in points:
                if part.get("flip_x"):
                    x = texture.width-x; nx = -nx
                x,y = (x-origin["x"])*scale.get("x",1.), (y-origin["y"])*scale.get("y",1.)
                transformed.append((dest["x"]+pivot["x"]+x*c-y*s, dest["y"]+pivot["y"]+x*s+y*c, nx*c-ny*s, nx*s+ny*c))
            result.extend(transformed)
    else:
        texture = g.resolve_render_item_texture(item, assets)
        if texture:
            rect = item["source_rect"]
            w,h = abs(int(rect["width"])), abs(int(rect["height"]))
            if w and h:
                points = texture_edges(runtime, texture, (int(rect["x"]),int(rect["y"]),w,h))
                result = [(dest["x"]+x*dest["width"]/w, dest["y"]+y*dest["height"]/h,nx,ny) for x,y,nx,ny in points]
    return result


def inside_rig(runtime, item, assets, x, y):
    """Reject component edges hidden inside the union of the evaluated rig."""
    dest = item["dest_rect"]
    for part in item.get("draw_data", {}).get("cutout_rig_parts", []):
        texture = assets.get("textures", {}).get(part.get("texture"))
        if texture is None:
            continue
        cached = runtime["textures"].get((texture.id,texture.width,texture.height))
        if cached is None:
            continue
        pivot, origin, scale = part["pivot_local"], part["origin"], part.get("scale",{})
        angle = math.radians(part.get("rotation",0.)); c,s = math.cos(angle), math.sin(angle)
        dx,dy = x-dest["x"]-pivot["x"], y-dest["y"]-pivot["y"]
        u = (dx*c+dy*s)/max(.0001,scale.get("x",1.))+origin["x"]
        v = (-dx*s+dy*c)/max(.0001,scale.get("y",1.))+origin["y"]
        if part.get("flip_x"):
            u = texture.width-u
        if 0 <= u < texture.width and 0 <= v < texture.height and cached[0][int(v)*texture.width+int(u)] >= 128:
            return True
    return False


def update(assets, objects, camera, width, height, now):
    import g_effects
    import g_glow
    started = time.perf_counter()
    runtime = assets.setdefault("glow_particles", {"particles": [], "sources": {}, "textures": {}, "last": now})
    elapsed = now-runtime["last"]
    runtime["last"] = now
    dt = max(0., min(.1, elapsed))
    if elapsed < 0 or elapsed > 1.:
        runtime["particles"].clear()
        runtime["sources"].clear()
    runtime["reads_left"] = 1
    particles = runtime["particles"]
    particles[:] = [p for p in particles if p["age"]+dt < p["life"]]
    for p in particles:
        p["age"] += dt
        p["x"] += p["vx"]*dt
        p["y"] += p["vy"]*dt
    counts = {}
    for p in particles:
        counts[p["owner"]] = counts.get(p["owner"],0)+1
    active = set()
    for item, value in objects:
        policy = item.get("glow", {}).get("particles", {})
        if not policy.get("enabled", False) or value["strength"] <= 0.:
            continue
        dest = item["dest_rect"]
        if dest["x"]+dest["width"] < camera.x or dest["x"] > camera.x+width or dest["y"]+dest["height"] < camera.y or dest["y"] > camera.y+height:
            continue
        owner = item.get("source_id", str(item.get("id", "object")))
        active.add(owner)
        state = runtime["sources"].setdefault(owner, {"credit": 0., "serial": 0})
        rate = max(0.,min(40.,float(policy.get("rate",12.))))
        if policy.get("pulse_link", True):
            rate *= g_glow.pulse_multiplier(item.get("glow", {}), now)
        state["credit"] = min(4.,state["credit"]+rate*dt)
        count = min(int(state["credit"]),MAX_PER_OBJECT-counts.get(owner,0),MAX_PARTICLES-len(particles))
        if count <= 0:
            continue
        points = shapes(runtime,item,assets)
        if not points:
            continue
        seed = zlib.crc32(owner.encode("utf-8"))
        for _ in range(count):
            serial = state["serial"]; state["serial"] += 1
            state["credit"] -= 1.
            random = lambda channel: g_effects.procedural_hash(serial,channel,seed)
            x,y,nx,ny = points[min(len(points)-1,int(random(1)*len(points)))]
            if inside_rig(runtime,item,assets,x+nx,y+ny):
                continue
            drift = max(0.,min(30.,float(policy.get("drift",7.))))*(.6+random(2)*.8)
            life = max(.1,min(4.,float(policy.get("lifetime",1.5))))*(.7+random(3)*.3)
            offset = max(0.,value["edge_width"]-1.)
            particles.append(dict(owner=owner,x=x+nx*offset,y=y+ny*offset,vx=nx*drift,vy=ny*drift-3.,age=0.,life=life,
                color=policy.get("color",value["color"]),strength=value["strength"],spread=value["spread"],depth=item.get("sort_y",0.)))
    runtime["sources"] = {key:value for key,value in runtime["sources"].items() if key in active}
    runtime["update_ms"] = (time.perf_counter()-started)*1000.
    return particles


def draw(assets, camera, spread, width, height):
    import g_graphics as g
    info = assets["shaders"]["glow_particles"]
    mask = assets.get("render_targets", {}).get("effect_occlusion")
    pr.begin_shader_mode(info["shader"])
    g.set_shader_vec2(info["shader"],info["resolution"],width,height)
    g.set_shader_float(info["shader"],info["maskEnabled"],1. if mask else 0.)
    groups = {}
    for p in assets.get("glow_particles", {}).get("particles", []):
        if p["spread"] == spread:
            groups.setdefault(p["owner"], []).append(p)
    for particles in groups.values():
        pr.rl_draw_render_batch_active()
        g.set_shader_float(info["shader"],info["groundDepth"],particles[0]["depth"]-camera.y)
        if mask:
            g.set_shader_texture(info["shader"],info["occlusionTexture"],mask.texture)
        for p in particles:
            fade = min(1.,p["age"]/.1)*(1.-p["age"]/p["life"])
            color = pr.Color(*(int(max(0.,min(1.,c))*255) for c in p["color"]), int(255*fade*p["strength"]))
            pr.draw_rectangle(round(p["x"]-camera.x),round(p["y"]-camera.y),1,1,color)
    pr.end_shader_mode()
