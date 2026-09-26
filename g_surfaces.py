"""Paintable material regions: deterministic cached ground and GPU grass details."""
from pathlib import Path
from functools import lru_cache
import json
import math
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import pyray as pr
import numpy as np
import g_effects
ART = Path(__file__).resolve().parent / 'art' / 'surfaces'
MATERIALS = ('erase', 'grass', 'dirt', 'wood', 'carpet', 'ceramic', 'wall')
COLORS = {'grass': (85, 91, 48), 'dirt': (135, 117, 90), 'wood': (137, 109, 82), 'carpet': (93, 60, 53), 'ceramic': (130, 146, 135), 'wall': (86, 75, 60)}
CHUNK = 4
MASK_VERSION = 3
GRASS_SHADER_VERSION = 2

def brush_settings(editor):
    return dict(density=editor.get('surface_density', 0.65), seed=editor.get('surface_seed', 17), soft=editor.get('surface_soft', True))

def draw_controls(ui, editor):
    """The material popup is last so it can cover the controls below it."""
    import g_ui
    pr.draw_rectangle(328, 59, 149, 161, g_ui.UI_BACKGROUND)
    editor['surface_density'], _ = g_ui.ui_slider_float(ui, 'surface:density', 'detail', editor.get('surface_density', 0.65), 0.0, 1.0, 0.05, pr.Rectangle(332, 88, 138, 17))
    pr.draw_text('Brush', 332, 113, 8, pr.WHITE)
    for i, size in enumerate((1, 3, 5)):
        if g_ui.ui_button(ui, f'surface:brush:{size}', str(size), pr.Rectangle(379 + i * 30, 109, 28, 16), selected=editor.get('surface_brush', 1) == size):
            editor['surface_brush'] = size
    editor['surface_soft'], _ = g_ui.ui_checkbox(ui, 'surface:soft', 'Rounded joins', editor.get('surface_soft', True), pr.Rectangle(332, 130, 138, 15))
    editor['surface_seed'], _ = g_ui.ui_number_input_int(ui, 'surface:seed', 'Seed', editor.get('surface_seed', 17), 0, 99999, pr.Rectangle(332, 151, 138, 17))
    pr.draw_text('LMB paint / RMB fill', 332, 178, 8, g_ui.UI_MUTED)
    pr.draw_text('Ctrl+Z undo', 332, 190, 8, g_ui.UI_MUTED)
    pr.draw_text('Finish + footstep sound', 332, 202, 7, g_ui.UI_MUTED)
    pr.draw_text('Keeps tile collision', 332, 211, 7, g_ui.UI_MUTED)
    editor['surface_material'], _ = g_ui.ui_dropdown(ui, 'surface:material', '', editor.get('surface_material', 'grass'), MATERIALS, pr.Rectangle(332, 65, 138, 17), 7)

def noise(x, y, seed=0):
    n = int(x) * 374761393 + int(y) * 668265263 + int(seed) * 1442695041 & 4294967295
    n = (n ^ n >> 13) * 1274126177 & 4294967295
    return ((n ^ n >> 16) & 65535) / 65535.0

def cell(tm, x, y):
    if 0 <= x < tm['map_width'] and 0 <= y < tm['map_height']:
        return tm['tiles'][y * tm['map_width'] + x]
    return {}

def material_at(tm, x, y):
    return cell(tm, math.floor(x / tm['tile_width']), math.floor(y / tm['tile_height'])).get('surface_material', 'erase')

def paint(tm, points, material, density=0.65, seed=17, soft=True):
    """Write authored scalar fields only; geometry and sound zones stay intact."""
    if material not in MATERIALS:
        raise ValueError(material)
    changed = 0
    for x, y in set(points):
        tile = cell(tm, x, y)
        if not tile:
            continue
        before = tuple((tile.get(k) for k in ('surface_material', 'surface_density', 'surface_seed', 'surface_soft')))
        if material == 'erase':
            for k in ('surface_material', 'surface_density', 'surface_seed', 'surface_soft'):
                tile.pop(k, None)
        else:
            tile.update(surface_material=material, surface_density=max(0.0, min(1.0, float(density))), surface_seed=int(seed), surface_soft=bool(soft))
        changed += before != tuple((tile.get(k) for k in ('surface_material', 'surface_density', 'surface_seed', 'surface_soft')))
    if changed:
        tm['acoustic_revision'] = tm.get('acoustic_revision', 0) + 1
        tm['surface_revision'] = tm.get('surface_revision', 0) + 1
    return changed

def flood(tm, x, y, material, **settings):
    """Fill connected material; legacy tile/collision boundaries bound unpainted fills."""
    def region_key(tile):
        kind = tile.get('surface_material', 'erase')
        return (kind, tile.get('index', 0), bool(tile.get('force_collidable'))) if kind == 'erase' else kind
    initial = region_key(cell(tm, x, y))
    seen = set()
    todo = [(x, y)]
    points = []
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        t = cell(tm, *p)
        if not t or region_key(t) != initial:
            continue
        points.append(p)
        a, b = p
        todo.extend(((a - 1, b), (a + 1, b), (a, b - 1), (a, b + 1)))
    return paint(tm, points, material, **settings)

def signature(tm, cx, cy):
    """A two-cell halo invalidates adjacent masks and overlapping detail cutouts."""
    return tuple(((t.get('surface_material'), t.get('surface_density'), t.get('surface_seed'), t.get('surface_soft'), t.get('shape_index', 0), vegetation_blocked(tm, t)) for y in range(cy * CHUNK - 2, (cy + 1) * CHUNK + 2) for x in range(cx * CHUNK - 2, (cx + 1) * CHUNK + 2) for t in (cell(tm, x, y),)))

@lru_cache(maxsize=1)
def detail_data():
    records = json.loads((ART / 'details.json').read_text())
    with Image.open(ART / 'details.png') as im:
        atlas = im.convert('RGBA')
    return (records, atlas)

def masks(tm, cx, cy):
    """Round region contours, then assign each pixel to exactly one material.

    Blurred fields define the contour only; the returned stencils are binary.
    Include unpainted space in the competition to round outer corners too.
    The saved surface_soft flag now means rounded joins, preserving old maps.
    """
    tw, th = (tm['tile_width'], tm['tile_height'])
    pad = max(tw, th) * 2
    width, height = (tw * CHUNK, th * CHUNK)
    ox, oy = (cx * width - pad, cy * height - pad)
    size = (width + pad * 2, height + pad * 2)
    hard = Image.new('L', size)
    hd = ImageDraw.Draw(hard)
    result = {}
    for y in range(cy * CHUNK - 2, (cy + 1) * CHUNK + 2):
        for x in range(cx * CHUNK - 2, (cx + 1) * CHUNK + 2):
            tile = cell(tm, x, y)
            kind = tile.get('surface_material')
            if kind not in COLORS:
                continue
            image = result.setdefault(kind, Image.new('L', size))
            d = ImageDraw.Draw(image)
            a, b = (x * tw - ox, y * th - oy)
            c, e = (a + tw - 1, b + th - 1)
            shape = tile.get('shape_index', 0)
            polygon = {1: [(a, b), (c, b), (a, e)], 2: [(a, b), (c, b), (c, e)], 3: [(c, b), (c, e), (a, e)], 4: [(a, b), (c, e), (a, e)]}.get(shape)
            if polygon:
                d.polygon(polygon, fill=255)
            else:
                d.rectangle((a, b, c, e), fill=255)
            if not tile.get('surface_soft', True):
                hd.rectangle((a, b, c, e), fill=255)
    crop = (pad, pad, pad + width, pad + height)
    hard = hard.filter(ImageFilter.MaxFilter(7))
    union = Image.new('L', size)
    for raw in result.values():
        union = ImageChops.lighter(union, raw)
    # Stable ordering and original-owner tie breaks make shared borders exact
    # across chunks, including junctions of three or more materials.
    kinds = [kind for kind in COLORS if kind in result] + ['_unpainted']
    result['_unpainted'] = ImageChops.invert(union)
    scores = []
    for kind in kinds:
        raw = result[kind]
        curved = raw.filter(ImageFilter.GaussianBlur(max(1.0, min(tw, th) * 0.30)))
        field = np.asarray(Image.composite(raw, curved, hard), dtype=np.uint16)
        scores.append(field * 2 + (np.asarray(raw) > 0))
    owner = np.argmax(np.stack(scores), axis=0)
    result = {kind: Image.fromarray(np.where(owner == index, 255, 0).astype('uint8'))
              for index, kind in enumerate(kinds[:-1])}
    result['_coverage'] = Image.fromarray(np.where(owner != len(kinds)-1, 255, 0).astype('uint8'))
    return (result, crop, (ox, oy))

def noise_grid(x, y, seed=0):
    n = x.astype(np.int64) * 374761393 + y.astype(np.int64) * 668265263 + seed * 1442695041 & 4294967295
    n = (n ^ n >> 13) * 1274126177 & 4294967295
    return ((n ^ n >> 16) & 65535) / 65535.0

def smooth_noise(x, y, sx, sy):
    """World-space value noise; smooth color fields hide the generation lattice."""
    gx, gy = (x // sx, y // sy)
    u = x % sx / sx
    v = y % sy / sy
    u = u * u * (3 - 2 * u)
    v = v * v * (3 - 2 * v)
    return (noise_grid(gx, gy) * (1 - u) + noise_grid(gx + 1, gy) * u) * (1 - v) + (noise_grid(gx, gy + 1) * (1 - u) + noise_grid(gx + 1, gy + 1) * u) * v

@lru_cache(maxsize=256)
def base_patch(kind, ox, oy, w, h):
    y, x = np.mgrid[oy:oy + h, ox:ox + w]
    fine = (noise_grid(x, y, 5) - 0.5) * 3
    value = (smooth_noise(x, y, 29, 23) - 0.5) * 10 + (smooth_noise(x, y, 7, 9) - 0.5) * 4 + fine
    if kind in ('wood', 'wall'):
        board = x // 12
        value += (noise_grid(board, np.zeros_like(y), 3) - 0.5) * 16
        joint = (x % 12 == 0) | ((y + (noise_grid(board, np.zeros_like(y)) * 40).astype(int)) % 56 == 0)
        value += np.where(joint, -24, np.where(x % 12 == 1, 8, 0))
        value += (smooth_noise(x, y, 2, 14) - 0.5) * 10
    elif kind == 'ceramic':
        value = (noise_grid(x // 16, y // 16, 9) - 0.5) * 23 + fine
        value = np.where((x % 16 == 0) | (y % 16 == 0), -28, value + np.where((x % 16 == 1) | (y % 16 == 1), 10, 0))
    elif kind == 'carpet':
        value = (noise_grid(x // 2, y // 2, 3) - 0.5) * 10 + (x + y) % 2 * 2
    rgb = np.asarray(COLORS[kind])[None, None, :] + value[:, :, None]
    return Image.fromarray(rgb.round().clip(0, 255).astype('uint8')).convert('RGBA')

def vegetation_blocked(tm, tile):
    # A material is a finish, so an old grass finish must not grow through a wall.
    import g_update_and_render as game
    return game.tile_is_collidable(tile, tm)

def candidates(tm, ox, oy, width, height):
    """Anchor identity depends on world position and seed, never paint order."""
    records, _ = detail_data()
    for gy in range(math.floor((oy - 24) / 8), math.ceil((oy + height + 24) / 8)):
        for gx in range(math.floor((ox - 24) / 8), math.ceil((ox + width + 24) / 8)):
            x = gx * 8 + 1 + noise(gx, gy, 3) * 6
            y = gy * 8 + 1 + noise(gx, gy, 7) * 6
            tile = cell(tm, math.floor(x / tm['tile_width']), math.floor(y / tm['tile_height']))
            kind = tile.get('surface_material')
            if kind == 'grass' and vegetation_blocked(tm, tile):
                continue
            seed = tile.get('surface_seed', 17)
            probability = tile.get('surface_density', 0.65) * (0.46 if kind == 'grass' else 0.16)
            if kind not in COLORS or noise(gx, gy, seed) > probability:
                continue
            pool = [(i, r) for i, r in enumerate(records) if r['material'] == ('tiles' if kind == 'ceramic' else kind)]
            if not pool:
                continue
            idx, record = pool[min(len(pool) - 1, int(noise(gx, gy, seed + 1) * len(pool)))]
            scale = 0.3 + noise(gx, gy, seed + 2) * 0.24 if kind == 'grass' else 0.45 + noise(gx, gy, seed + 2) * 0.3
            yield (kind, x, y, record, scale, noise(gx, gy, seed + 4) > 0.5)

def bake_chunk(tm, cx, cy):
    """Cut complete material layers against mutually exclusive pixel stencils."""
    tw, th = (tm['tile_width'], tm['tile_height'])
    w, h = (tw * CHUNK, th * CHUNK)
    wx, wy = (cx * w, cy * h)
    fields, crop, origin = masks(tm, cx, cy)
    _, atlas = detail_data()
    grass = []
    ground = Image.new('RGBA', (w, h))
    nearby = list(candidates(tm, wx, wy, w, h))
    for kind in COLORS:
        if kind not in fields:
            continue
        mask = fields[kind].crop(crop)
        layer = base_patch(kind, wx, wy, w, h).copy()
        for k, x, y, record, scale, flip in nearby:
            if k != kind:
                continue
            mx, my = (round(x - origin[0]), round(y - origin[1]))
            if not (0 <= mx < fields[k].width and 0 <= my < fields[k].height) or fields[k].getpixel((mx, my)) < 180:
                continue
            if k == 'grass':
                if wx <= x < wx + w and wy <= y < wy + h:
                    grass.append((x, y, record, scale, flip))
                continue
            ax, ay, aw, ah = record['rect']
            sprite = atlas.crop((ax, ay, ax + aw, ay + ah))
            sprite = sprite.resize((max(1, round(aw * scale)), max(1, round(ah * scale))), Image.Resampling.NEAREST)
            if flip:
                sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            sprite.putalpha(sprite.getchannel('A').point(lambda a: round(a * 0.72)))
            layer.alpha_composite(sprite, (round(x - wx - sprite.width / 2), round(y - wy - sprite.height / 2)))
        ground.paste(layer, (0, 0), mask)
    return (ground, grass)

def upload_image(im):
    raw = bytearray(im.tobytes())
    native = pr.Image(raw, im.width, im.height, 1, int(pr.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
    tex = pr.load_texture_from_image(native)
    pr.set_texture_filter(tex, pr.TextureFilter.TEXTURE_FILTER_POINT)
    return tex

def build_grass_mesh(items):
    """Static quads carry root and bend weight in normals for GPU deformation."""
    if not items:
        return None
    m = pr.ffi.new('Mesh *')
    m.vertexCount = len(items) * 6
    m.triangleCount = len(items) * 2
    for name, count in (('vertices', 3), ('normals', 3), ('texcoords', 2)):
        setattr(m, name, pr.ffi.cast('float *', pr.rl.MemAlloc(m.vertexCount * count * 4)))
    for i, (x, y, record, scale, flip) in enumerate(items):
        ax, ay, w, h = record['rect']
        root_x, root_y = record['root']
        corners = [(-root_x, -root_y, 0, 0, 1), (-root_x, h-root_y, 0, 1, 0),
                   (w-root_x, h-root_y, 1, 1, 0), (w-root_x, -root_y, 1, 0, 1)]
        for j, k in enumerate((0, 1, 2, 0, 2, 3)):
            dx, dy, u, v, tip = corners[k]
            n = i * 6 + j
            if flip:
                u = 1 - u
            m.vertices[n * 3:n * 3 + 3] = (x + dx * scale, y + dy * scale, 0.0)
            m.normals[n * 3:n * 3 + 3] = (x, y, tip)
            m.texcoords[n * 2:n * 2 + 2] = ((ax + u * w) / 256.0, (ay + v * h) / 128.0)
    pr.rl.UploadMesh(m, False)
    return m

def free_chunk(chunk):
    pr.unload_texture(chunk['texture'])
    if chunk['mesh'] is not None:
        pr.rl.UnloadMesh(chunk['mesh'][0])

def prepare(assets, tm, camera):
    """Cache visible chunks; compare neighborhood signatures only after editing."""
    rt = assets.setdefault('surface_runtime', {'chunks': {}, 'footprints': []})
    if (rt.get('map') is not tm or rt.get('mask_version') != MASK_VERSION
            or rt.get('dimensions') != (tm['tile_width'], tm['tile_height'], tm['map_width'], tm['map_height'])):
        for c in rt['chunks'].values():
            free_chunk(c)
        rt.update(chunks={}, map=tm, mask_version=MASK_VERSION, dimensions=(tm['tile_width'], tm['tile_height'], tm['map_width'], tm['map_height']), footprints=[], last_player=None, empty=set(), revision=None)
    revision = (tm.get('surface_revision', 0), tm.get('geometry_revision', 0))
    dirty = rt.get('revision') != revision
    if dirty:
        rt['empty'] = set()
    w, h = (tm['tile_width'] * CHUNK, tm['tile_height'] * CHUNK)
    visible = []
    for cy in range(max(0, math.floor(camera.y / h) - 1), min(math.ceil(tm['map_height'] / CHUNK), math.ceil((camera.y + 270) / h) + 1)):
        for cx in range(max(0, math.floor(camera.x / w) - 1), min(math.ceil(tm['map_width'] / CHUNK), math.ceil((camera.x + 480) / w) + 1)):
            key = (cx, cy)
            existing = rt['chunks'].get(key)
            if key in rt['empty']:
                continue
            if existing is not None and (not dirty):
                visible.append(key)
                continue
            sig = signature(tm, cx, cy)
            if not any((t[0] for t in sig)):
                rt['empty'].add(key)
                continue
            visible.append(key)
            if existing is None or existing['signature'] != sig:
                if existing:
                    free_chunk(existing)
                im, grass = bake_chunk(tm, cx, cy)
                rt['chunks'][key] = dict(signature=sig, texture=upload_image(im), mesh=build_grass_mesh(grass))
    for key in list(rt['chunks']):
        if key not in visible:
            free_chunk(rt['chunks'].pop(key))
    rt['visible'] = visible
    blocker_revision = (id(tm), tm.get('geometry_revision', 0), MASK_VERSION, rt['dimensions'])
    if (rt.get('blocker_revision') != blocker_revision
            and any(rt['chunks'][key]['mesh'] is not None for key in visible)):
        prepare_grass_blockers(rt, tm)
        rt['blocker_revision'] = blocker_revision
    rt['revision'] = revision
    return rt

def draw_cell(assets, tm, x, y, screen):
    rt = assets.get('surface_runtime', {})
    chunk = rt.get('chunks', {}).get((x // CHUNK, y // CHUNK))
    if chunk:
        tw, th = (tm['tile_width'], tm['tile_height'])
        pr.draw_texture_rec(chunk['texture'], pr.Rectangle(x % CHUNK * tw, y % CHUNK * th, tw, th), screen, pr.WHITE)

def prepare_grass_blockers(rt, tm):
    import g_light_visibility as visibility
    tw, th = tm['tile_width'], tm['tile_height']
    mask = Image.new('RGBA', (tm['map_width']*tw, tm['map_height']*th), (0,0,0,255))
    draw = ImageDraw.Draw(mask)
    for index, tile in enumerate(tm['tiles']):
        if not vegetation_blocked(tm, tile):continue
        x,y = index % tm['map_width'], index // tm['map_width']
        shape = 0 if tile.get('facade_blocked') or tile.get('puzzle_blocked') else tile.get('shape_index',0)
        if shape == 0:
            draw.rectangle((x*tw,y*th,(x+1)*tw-1,(y+1)*th-1),fill=(255,255,255,255))
        else:
            points = visibility.tile_shape_world_vertices(x,y,shape,tw,th)
            draw.polygon([(p['x'],p['y']) for p in points],fill=(255,255,255,255))
    if 'blocker_texture' in rt:pr.unload_texture(rt['blocker_texture'])
    rt['blocker_texture'] = upload_image(mask)

def ensure_grass(rt):
    if 'shader' in rt and rt.get('shader_version') == GRASS_SHADER_VERSION:
        return
    if 'material' in rt:
        pr.unload_texture(rt['material'].maps[0].texture)
        pr.rl.MemFree(rt['material'].maps)
    if 'shader' in rt:pr.unload_shader(rt['shader'])
    path = ART.parent.parent / 'shaders'
    shader = pr.load_shader(str(path / 'surface_grass.vs'), str(path / 'surface_grass.fs'))
    names = ('camera', 'player', 'wind', 'elapsed', 'shadow', 'blockerTexture', 'worldSize')
    locations = {n: pr.get_shader_location(shader, n) for n in names}
    if shader.id == pr.rl.rlGetShaderIdDefault() or min(locations.values()) < 0:
        raise RuntimeError('Grass shader failed')
    material = pr.load_material_default()
    material.shader = shader
    material.shader.locs[int(pr.ShaderLocationIndex.SHADER_LOC_MAP_NORMAL)] = locations['blockerTexture']
    material.maps[0].texture = pr.load_texture(str(ART / 'details.png'))
    pr.set_texture_filter(material.maps[0].texture, pr.TextureFilter.TEXTURE_FILTER_POINT)
    rt.update(shader=shader, shader_version=GRASS_SHADER_VERSION, locations=locations, material=material, identity=pr.matrix_identity())

def update_footprints(rt, tm, pos, elapsed, playing):
    previous = rt.get('last_player') if playing else None
    if playing and previous:
        distance = math.hypot(pos['x']-previous[0], pos['y']-previous[1])
        if distance > 10:
            if distance < 40 and material_at(tm, pos['x'], pos['y']) == 'dirt':
                dx, dy = (pos['x']-previous[0])/distance, (pos['y']-previous[1])/distance
                side = 1 if rt.get('step_index', 0) % 2 else -1
                rt['step_index'] = rt.get('step_index', 0) + 1
                rt['footprints'].append((pos['x']-dy*side*2, pos['y']+dx*side*2, elapsed, dx, dy))
            rt['last_player'] = (pos['x'], pos['y'])
    else:
        rt['last_player'] = (pos['x'], pos['y']) if playing else None
    rt['footprints'] = [p for p in rt['footprints'][-96:] if len(p) == 5 and 0 <= elapsed-p[2] < 18]

def footprint_pixels(dx, dy):
    # Broad toe, narrow heel; direction remains the travel direction at contact.
    return {(x,y) for y in range(-3,4) for x in range(-3,4)
            if -1.5 <= x*dx+y*dy <= 2.0
            and abs(-x*dy+y*dx) <= (1.0 if x*dx+y*dy >= 0 else .55)}

def draw_details(assets, tm, camera, player, wind, elapsed, playing):
    rt = assets.get('surface_runtime')
    if not rt or not rt.get('visible'):
        return
    pos = g_effects.position_to_world(player.get('position', {}), tm)
    # Gameplay positions sit at the torso; vegetation reacts at the feet.
    base_offset = player.get('render_base_offset', {'x': 0., 'y': 14.})
    pos['x'] += float(base_offset.get('x', 0.))
    pos['y'] += float(base_offset.get('y', 0.))
    update_footprints(rt, tm, pos, elapsed, playing)
    for x, y, t, dx, dy in rt['footprints']:
        if material_at(tm, x, y) != 'dirt':
            continue
        alpha = int(85 * (1 - (elapsed - t) / 18))
        # Rasterise the stored sole orientation at native pixels, without filtering.
        for px, py in footprint_pixels(dx, dy):
            pr.draw_pixel(round(x) - round(camera.x) + px, round(y) - round(camera.y) + py,
                          pr.Color(45, 38, 27, alpha))
    if not any((rt['chunks'][key]['mesh'] is not None for key in rt['visible'])):
        return
    ensure_grass(rt)
    shader = rt['shader']
    loc = rt['locations']
    rt['material'].maps[2].texture = rt['blocker_texture']
    pr.set_shader_value(shader, loc['worldSize'], pr.ffi.new('float[]', (rt['blocker_texture'].width, rt['blocker_texture'].height)), pr.ShaderUniformDataType.SHADER_UNIFORM_VEC2)
    wind = g_effects.sample_wind(wind, pos['x'], pos['y'], elapsed)
    for name, value in (('camera', (round(camera.x), round(camera.y))), ('player', (pos['x'], pos['y'])), ('wind', (wind['x'], wind['y']))):
        pr.rl.SetShaderValue(shader, loc[name], pr.ffi.new('float[]', value), int(pr.ShaderUniformDataType.SHADER_UNIFORM_VEC2))
    pr.rl.SetShaderValue(shader, loc['elapsed'], pr.ffi.new('float *', elapsed), int(pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT))
    pr.rl_draw_render_batch_active()
    pr.rl_disable_backface_culling()
    for shadow in (1.0, 0.0):
        pr.rl.SetShaderValue(shader, loc['shadow'], pr.ffi.new('float *', shadow), int(pr.ShaderUniformDataType.SHADER_UNIFORM_FLOAT))
        for key in rt['visible']:
            mesh = rt['chunks'][key]['mesh']
            if mesh is not None:
                pr.rl.DrawMesh(mesh[0], rt['material'], rt['identity'])
    pr.rl_enable_backface_culling()

def add_impact(tm, position, velocity):
    dx, dy = (velocity.get('x', 0), velocity.get('y', 0))
    length = max(1.0, math.hypot(dx, dy))
    x, y = (position['x'] + dx / length, position['y'] + dy / length)
    tile = cell(tm, math.floor(x / tm['tile_width']), math.floor(y / tm['tile_height']))
    if tile.get('surface_material') not in ('wall', 'wood', 'ceramic'):
        return
    decals = tile.setdefault('decals', [])
    if sum((d.get('type') == 'surface_bullet' for d in decals)) >= 12:
        return
    decals.append(dict(type='surface_bullet', offset_x=x % tm['tile_width'], offset_y=y % tm['tile_height'], size=1))

def unload(assets):
    rt = assets.pop('surface_runtime', {})
    for chunk in rt.get('chunks', {}).values():
        free_chunk(chunk)
    if 'blocker_texture' in rt:pr.unload_texture(rt['blocker_texture'])
    if 'material' in rt:
        pr.unload_texture(rt['material'].maps[0].texture)
        pr.rl.MemFree(rt['material'].maps)
    if 'shader' in rt:
        pr.unload_shader(rt['shader'])
