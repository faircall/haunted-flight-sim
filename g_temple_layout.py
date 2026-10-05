"""Plain-data blockout edits feeding the same surfaces, mesh and collision map.

Cells are internal 16-unit construction units. Authoring exposes rectangles,
material/height choices and stair flights, while the shipped scene stays intact.
"""
from copy import deepcopy
from dataclasses import asdict
import math
import uuid

import g_temple_structure as structure

CELL = 16
WIDTH, DEPTH = 56, 40
MATERIALS = ('wood', 'stone', 'grass', 'wall', 'water', 'restore')
AXES = ('x', 'z', '-x', '-z')


def default_layout():
    return dict(cells={}, stairs=[dict(asdict(s), bounds=list(s.bounds), id='stairs:'+s.name, authored=False)
                                 for s in structure.STAIRS], rails=True)


def validate(layout):
    if not isinstance(layout, dict) or not isinstance(layout.get('cells'), dict) or not isinstance(layout.get('stairs'), list) or not isinstance(layout.get('rails'), bool):
        raise ValueError('Invalid floor layout.')
    for key, cell in layout['cells'].items():
        try:
            x, z = map(int, key.split(','))
        except (ValueError, AttributeError):
            raise ValueError('Invalid floor cell address.') from None
        if key != f'{x},{z}' or not (0 <= x < WIDTH and 0 <= z < DEPTH):
            raise ValueError('Floor cells must be inside the map.')
        if not isinstance(cell, dict) or cell.get('material') not in MATERIALS[:-1] or cell.get('axis') not in ('x', 'y'):
            raise ValueError('Invalid floor material or grain direction.')
        h = cell.get('height')
        if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h) or not 0 <= h <= 48:
            raise ValueError('Floor heights must be between 0 and 48.')
        if cell['material'] == 'water' and h != 0:
            raise ValueError('Water stays at lake level.')
    identities = set()
    for stairs in layout['stairs']:
        if not isinstance(stairs, dict) or not isinstance(stairs.get('id'), str) or stairs['id'] in identities:
            raise ValueError('Stairs need unique IDs.')
        identities.add(stairs['id'])
        bounds = stairs.get('bounds')
        if not isinstance(bounds, (tuple, list)) or len(bounds) != 4 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds):
            raise ValueError('Invalid stair bounds.')
        x0, z0, x1, z1 = bounds
        if not (0 <= x0 < x1 <= WIDTH*CELL and 0 <= z0 < z1 <= DEPTH*CELL):
            raise ValueError('Stairs must be inside the map.')
        if stairs.get('axis') not in AXES or type(stairs.get('count')) is not int or not 1 <= stairs['count'] <= 24:
            raise ValueError('Invalid stair direction or tread count.')
        bottom, top = stairs.get('bottom'), stairs.get('top')
        if any(isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h) for h in (bottom, top)) or not 0 <= bottom < top <= 48:
            raise ValueError('Stairs need a higher upper landing.')
        if (top-bottom)/stairs['count'] > 4.001:
            raise ValueError('Stair risers must be at most four units high.')
        length=(x1-x0) if stairs['axis'].endswith('x') else (z1-z0)
        if length/stairs['count'] < 2:
            raise ValueError('This stair flight is too short. Draw a longer rectangle.')
        if not isinstance(stairs.get('authored'), bool) or not isinstance(stairs.get('name'), str):
            raise ValueError('Invalid stair definition.')
    for i, a in enumerate(layout['stairs']):
        for b in layout['stairs'][i+1:]:
            if overlaps(a['bounds'], b['bounds']):
                raise ValueError('Stair flights cannot overlap.')
    return layout


def cell_at(position):
    return tuple(max(0, min(limit-1, math.floor(v/CELL))) for v, limit in zip(position, (WIDTH, DEPTH)))


def rectangle(a, b):
    ax, az = cell_at(a)
    bx, bz = cell_at(b)
    return min(ax, bx)*CELL, min(az, bz)*CELL, (max(ax, bx)+1)*CELL, (max(az, bz)+1)*CELL


def cells_in(bounds):
    x0, z0, x1, z1 = bounds
    for z in range(math.floor(z0/CELL), math.ceil(z1/CELL)):
        for x in range(math.floor(x0/CELL), math.ceil(x1/CELL)):
            yield x, z


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def paint(scene, a, b, material, height=16, axis='x'):
    before = scene.checkpoint()
    layout = scene.document['layout']
    bounds = rectangle(a, b)
    layout['stairs'][:] = [s for s in layout['stairs'] if not overlaps(s['bounds'], bounds)]
    for x, z in cells_in(bounds):
        key = f'{x},{z}'
        if material == 'restore':
            layout['cells'].pop(key, None)
        else:
            layout['cells'][key] = dict(material=material, height=0 if material == 'water' else height, axis=axis)
    if material == 'restore':
        # Restore complete original flights touched by the restored region.
        for stairs in default_layout()['stairs']:
            if overlaps(stairs['bounds'], bounds) and not any(overlaps(stairs['bounds'], s['bounds']) for s in layout['stairs']):
                for x,z in cells_in(stairs['bounds']):layout['cells'].pop(f'{x},{z}',None)
                layout['stairs'].append(stairs)
    return scene.commit(before)


def add_stairs(scene, a, b, bottom, top, axis='x'):
    before = scene.checkpoint()
    layout = scene.document['layout']
    bounds = rectangle(a, b)
    layout['stairs'][:] = [s for s in layout['stairs'] if not overlaps(s['bounds'], bounds)]
    identity = 'stairs:' + uuid.uuid4().hex
    layout['stairs'].append(dict(id=identity, name=identity, bounds=list(bounds), axis=axis,
                                bottom=bottom, top=top, count=max(1, math.ceil((top-bottom)/3)), authored=True))
    scene.commit(before)
    return identity


def remove_stairs(scene, position):
    before = scene.checkpoint()
    x, z = position
    scene.document['layout']['stairs'][:] = [s for s in scene.document['layout']['stairs']
        if not (s['bounds'][0] <= x < s['bounds'][2] and s['bounds'][1] <= z < s['bounds'][3])]
    return scene.commit(before)


def stair_records(layout):
    original_order={'stairs:shore':0,'stairs:threshold':1}
    stairs=sorted(layout['stairs'],key=lambda s:(original_order.get(s['id'],2),s['id']))
    return tuple(structure.Stairs(s['name'], tuple(s['bounds']), s['axis'], s['bottom'], s['top'], s['count'])
                 for s in stairs)


def authored(layout):
    return bool(layout['cells']) or {s['id']:s for s in layout['stairs']} != {s['id']:s for s in default_layout()['stairs']}


def apply(base, layout, revision=0):
    validate(layout)
    tm = deepcopy(base)
    for key, record in layout['cells'].items():
        x, z = map(int, key.split(','))
        material = record['material']
        tile = dict(index=0, shape_index=0, surface_material=material,
                    surface_elevation=record['height'], surface_axis=record['axis'],
                    audio_surface='stone' if material == 'wall' else 'generic' if material == 'water' else material,
                    force_collidable=material in ('water', 'wall'), rain_exposure=1., structure='blockout')
        if material == 'water':
            tile.update(water=True, lake_bed=True)
        if base['tiles'][z*WIDTH+x].get('acoustic_zone_id'):
            tile['acoustic_zone_id']=base['tiles'][z*WIDTH+x]['acoustic_zone_id']
        tm['tiles'][z*WIDTH+x] = tile
    for stairs in layout['stairs']:
        if not stairs['authored']:
            continue
        for x, z in cells_in(stairs['bounds']):
            tm['tiles'][z*WIDTH+x] = dict(index=0, shape_index=0, surface_material='wood',
                surface_elevation=stairs['top'], surface_axis='y' if stairs['axis'].endswith('z') else 'x',
                audio_surface='wood', rain_exposure=1., structure='blockout')
            if base['tiles'][z*WIDTH+x].get('acoustic_zone_id'):
                tm['tiles'][z*WIDTH+x]['acoustic_zone_id']=base['tiles'][z*WIDTH+x]['acoustic_zone_id']
    tm['temple3d_stairs'] = stair_records(layout)
    # Shared AI/pathfinding uses cell addresses and neighbour topology in
    # addition to surface fields. Painting must preserve that derived graph.
    for i,tile in enumerate(tm['tiles']):
        original=base['tiles'][i]
        for key in ('tile_x','tile_y','neighbours'):
            if key in original:tile[key]=deepcopy(original[key])
        tile.pop('current_entities',None)
    tm['temple3d_levels']=tuple(sorted({0., *(t.get('surface_elevation',0.) for t in tm['tiles']),
        *(height for stairs in tm['temple3d_stairs'] for _,height in stairs.treads())}))
    tm['temple3d_edited_cells'] = {z*WIDTH+x for key in layout['cells'] for x, z in [map(int, key.split(','))]}
    tm['temple3d_authored_geometry'] = authored(layout)
    tm['temple3d_custom_temple'] = any(25 <= x < 35 and 11 <= z < 18 for key in layout['cells'] for x, z in [map(int, key.split(','))]) or any(
        s['authored'] and overlaps(s['bounds'],structure.TEMPLE_BOUNDS) for s in layout['stairs'])
    tm['blockout_revision'] = revision
    tm['surface_revision'] = base.get('surface_revision', 0)+revision+1
    tm['geometry_revision'] = base.get('geometry_revision', 0)+revision+1
    tm['acoustic_revision'] = base.get('acoustic_revision', 0)+revision+1
    return tm


def generated_rails(tm):
    """Rails only on exposed wood edges; internal edges and stair entries stay open."""
    rails = {}
    def tile(x, z):
        return tm['tiles'][z*WIDTH+x] if 0 <= x < WIDTH and 0 <= z < DEPTH else {'water': True}
    stairs = structure.stairs_for(tm)
    for z in range(DEPTH):
        for x in range(WIDTH):
            cell = tile(x, z)
            if cell.get('surface_material') != 'wood' or cell.get('surface_elevation', 0) <= 0:
                continue
            bounds = x*CELL, z*CELL, (x+1)*CELL, (z+1)*CELL
            if any(overlaps(bounds, s.bounds) for s in stairs):
                continue
            if 25 <= x < 35 and 11 <= z < 18 and not tm.get('temple3d_custom_temple'):
                continue
            for side, dx, dz in (('left', -1, 0), ('right', 1, 0), ('back', 0, -1), ('front', 0, 1)):
                neighbour = tile(x+dx, z+dz)
                if neighbour.get('surface_material') == 'wall':
                    continue
                px, pz = (x+.5)*CELL+dx*CELL/2, (z+.5)*CELL+dz*CELL/2
                inside = structure.floor_height(tm, px-dx*.1, pz-dz*.1)
                outside = structure.floor_height(tm, px+dx*.1, pz+dz*.1)
                if not neighbour.get('water') and not neighbour.get('force_collidable') and abs(inside-outside) <= 4:
                    continue
                rails[f'edge:{x},{z}:{side}'] = dict(kind='rail', asset='baked:rail32',
                    position=dict(x=px-dx*1.5, y=pz-dz*1.5), base_height=inside,
                    geometry_offset=(0, 0, 0), rotation_y=90 if dx else 0, scale=(.5, 1, 1))
    return rails
