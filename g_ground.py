"""Bounded static ground batches. Prepare outside a render target, draw once/chunk.

The editable tile path remains the reference. Cache signatures include decals,
texture identities and neighbouring material chunks, so edits and reloads cannot
leave stale paint behind. Simulation, collision and sound still use the tile map.
"""
import math
import pyray as pr
import g_surfaces
import g_render_order

CHUNK = g_surfaces.CHUNK
LIMIT = 256
TEXTURES = {'wood': 'wood_texture', 'wall': 'wall_texture',
            'stone': 'grey_tile_texture', 'carpet': 'orange_tile_texture'}


def unload(assets):
    for entry in assets.pop('ground_runtime', {}).get('chunks', {}).values():
        pr.unload_render_texture(entry['target'])


def prepare(assets, tm, camera, draw_tile):
    # Small levels fit entirely in the bounded terrain cache. Pay their Pillow
    # generation cost on scene entry rather than at camera chunk boundaries.
    surfaces = g_surfaces.prepare(assets, tm, camera, prewarm=True)
    rt = assets.setdefault('ground_runtime', {'chunks': {}, 'map': tm})
    if rt['map'] is not tm:
        unload(assets)
        rt = assets.setdefault('ground_runtime', {'chunks': {}, 'map': tm})
    tw, th = tm['tile_width'], tm['tile_height']
    mw, mh = tm['map_width'], tm['map_height']
    cw, ch = tw * CHUNK, th * CHUNK
    textures = assets.get('textures', {})
    texture_refs = tuple(textures.get(name) for name in TEXTURES.values())
    texture_key = (assets['shaders']['tile_mask']['shader'].id,
                   tuple((id(texture), getattr(texture, 'id', 0)) for texture in texture_refs))
    types = tuple(t.get('type') for t in tm['tile_types'])
    rt['fallback'] = False
    visible = []
    cols, rows = math.ceil(mw/CHUNK), math.ceil(mh/CHUNK)
    view_cols = range(max(0,math.floor(camera.x/cw)), min(cols,math.ceil((camera.x+480)/cw)))
    view_rows = range(max(0,math.floor(camera.y/ch)), min(rows,math.ceil((camera.y+270)/ch)))
    preload = not rt.get('prewarmed') and cols*rows <= LIMIT
    for cy in range(rows) if preload else view_rows:
        for cx in range(cols) if preload else view_cols:
            key = cx, cy
            # Include neighbours to reproduce decals crossing chunk boundaries.
            cells = [(x, y, tm['tiles'][y*mw+x])
                     for y in range(max(0, cy*CHUNK-1), min(mh, (cy+1)*CHUNK+1))
                     for x in range(max(0, cx*CHUNK-1), min(mw, (cx+1)*CHUNK+1))]
            if any(d.get('size', 5) > min(tw, th) or not (0 <= d.get('offset_x', 0) <= tw and 0 <= d.get('offset_y', 0) <= th)
                   for _, _, tile in cells for d in tile.get('decals', ())):
                # Arbitrarily large authored decals can span more than the
                # cache gutter. Keep exact painter ordering via the reference.
                rt['fallback'] = True
                return
            signature = (tw, th, types, texture_key,
                         tuple((t.get('index', 0), t.get('shape_index', 0), repr(t.get('decals', ()))) for _, _, t in cells),
                         tuple((k, surfaces['chunks'][k]['texture'].id, surfaces['chunks'][k]['signature']) for k in
                               ((xx, yy) for yy in range(cy-1, cy+2) for xx in range(cx-1, cx+2))
                               if k in surfaces['chunks']))
            entry = rt['chunks'].pop(key, None)
            if entry is None or entry['signature'] != signature:
                target = entry['target'] if entry and entry['size'] == (cw, ch) else None
                if entry and target is None:
                    pr.unload_render_texture(entry['target'])
                target = target or pr.load_render_texture(cw, ch)
                pr.begin_texture_mode(target)
                pr.clear_background(pr.BLANK)
                pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
                pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
                for x, y, tile in cells:
                    pos = pr.Vector2(x*tw-cx*cw, y*th-cy*ch)
                    name = TEXTURES.get(types[tile.get('index', 0)])
                    if name:
                        draw_tile(textures[name], pos, tile.get('shape_index', 0), assets)
                    g_surfaces.draw_cell(assets, tm, x, y, pos)
                    for decal in tile.get('decals', ()):
                        px, py = int(pos.x+decal['offset_x']), int(pos.y+decal['offset_y'])
                        if decal['type'] == 'blood':
                            pr.draw_circle(px, py, decal.get('size', 5), pr.RED)
                        elif decal['type'] == 'surface_bullet':
                            pr.draw_pixel(px+1, py+1, pr.Color(170,145,107,255))
                            pr.draw_circle(px, py, 1., pr.Color(30,25,21,255))
                pr.end_blend_mode()
                pr.end_texture_mode()
                # Retain handles as well as IDs: GL can reuse a deleted texture
                # name, and Python can reuse an unreferenced wrapper's address.
                entry = dict(target=target, signature=signature, size=(cw, ch), texture_refs=texture_refs)
            rt['chunks'][key] = entry
            if cx in view_cols and cy in view_rows:visible.append(key)
    while len(rt['chunks']) > max(LIMIT, len(visible)):
        pr.unload_render_texture(rt['chunks'].pop(next(iter(rt['chunks'])))['target'])
    rt.update(visible=visible, size=(cw,ch))
    if preload:rt['prewarmed'] = True


def draw(assets, camera):
    rt = assets['ground_runtime']
    cw, ch = rt['size']
    x, y = g_render_order.world_camera_offset(camera)
    source = pr.Rectangle(0, 0, cw, -ch)
    # The cached layer has premultiplied RGB, including any translucent art.
    pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
    pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
    for cx, cy in rt['visible']:
        pr.draw_texture_rec(rt['chunks'][cx,cy]['target'].texture, source,
                            pr.Vector2(cx*cw-x, cy*ch-y), pr.WHITE)
    pr.end_blend_mode()
