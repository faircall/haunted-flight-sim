"""Semantic names for *already ray-hit* generated scene geometry.

This does not pick bounding boxes, load graphics resources, or change assets.
The renderer supplies the closest actual surface. Where an existing manifest
unambiguously owns that surface we add an object ID and an authoring locator.
Otherwise an empty result preserves the caller's precise model/mesh/hit record.
"""
from functools import lru_cache
import importlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_IDENTITY = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
_HOUSE_MODELS = frozenset(('canal_masonry', 'canal_plaster', 'canal_timber',
    'canal_windows', 'canal_roofs', 'canal_details', 'canal_interiors',
    'canal_shadow', 'canal_recess'))
_LAKE_SCENES = frozenset(('huxin', 'huxin_moon', 'huxin_canals',
                         'huxin_canals_flooded'))


@lru_cache(maxsize=12)
def _read_json(path, modified, size):
    # The stat key invalidates a rebuilt manifest without retaining stale IDs.
    try:
        value = Path(path).read_text(encoding='utf-8')
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def _manifest(scene):
    path = ROOT / 'art' / 'temple' / scene / 'canals_manifest.json'
    try:
        stat = path.stat()
        return _read_json(str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}


@lru_cache(maxsize=8)
def _layout(name):
    return importlib.import_module(name)


def _bounds(points, bottom=None, margin=0.):
    low = [min(p[i] for p in points) - margin for i in range(3)]
    high = [max(p[i] for p in points) + margin for i in range(3)]
    if bottom is not None:
        low[1] = min(low[1], bottom)
    return {'min': low, 'max': high}


def _box(center, half):
    return {'min': [c-r for c, r in zip(center, half)],
            'max': [c+r for c, r in zip(center, half)]}


def _inside(poly, x, z, tolerance=.025):
    """Convex XZ polygon, with a distance tolerance on each edge."""
    if len(poly) < 3:
        return False
    cross = [(b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0])
             for a, b in zip(poly, poly[1:]+poly[:1])]
    eps = [tolerance*math.hypot(b[0]-a[0], b[1]-a[1])
           for a, b in zip(poly, poly[1:]+poly[:1])]
    return all(v >= -e for v, e in zip(cross, eps)) or all(v <= e for v, e in zip(cross, eps))


def _record(scene, hit, identity, label, kind, bounds, file, **fields):
    source = {'file': file, 'asset': hit.get('asset_path', '')}
    source.update(fields.pop('source', {}))
    return dict(id=scene+'/'+identity, label=label, kind=kind, bounds=bounds,
                source=source, selection_scope='object',
                resolution='authored_spatial_metadata', **fields)


def _stairs(scene, hit, manifest):
    model = hit['model_name']; x, y, z = hit['hit_position']
    if model not in ('canal_masonry', 'canal_ground', 'canal_distant'):
        return {}
    for index, stair in enumerate(manifest.get('washing_steps', ())):
        bottom = stair.get('bank_bottom', manifest.get('bank_bottom', -2.3))
        if not bottom-.035 <= y <= stair['top'][1]+.04:
            continue
        part = None; tread_index = None
        if model == 'canal_masonry':
            for i, tread in enumerate(stair['treads']):
                if y <= tread['center'][1]+.035 and _inside(tread['polygon'], x, z):
                    part = 'tread' if abs(y-tread['center'][1]) < .04 else 'riser or side'
                    tread_index = i
                    break
            landing = stair.get('landing_geometry')
            if not part and landing and y <= landing['center'][1]+.035 and _inside(landing['polygon'], x, z):
                part = 'washing landing'
        elif stair.get('rear_apron') and _inside(stair['rear_apron'], x, z):
            part = 'rear landing'
        if not part:
            continue
        points = [(p[0], t['center'][1], p[1]) for t in stair['treads'] for p in t['polygon']]
        landing = stair.get('landing_geometry')
        if landing:
            points += [(p[0], landing['center'][1], p[1]) for p in landing['polygon']]
        points += [(p[0], stair['top'][1], p[1]) for p in stair.get('rear_apron') or ()]
        seed = stair.get('house_seed')
        label = ('Rear washing stairs of house '+str(seed)) if seed is not None else ('Washing stairs '+stair['id'].removeprefix('washing-'))
        return _record(scene, hit, stair['id'], label, 'stairs',
            _bounds(points, bottom), 'build_huxin_canals.py',
            surface_part=part, tread_index=tread_index, house_seed=seed,
            source={'function': 'build.washing_flight', 'layout': 'g_huxin_canals_layout.py',
                    'manifest': 'art/temple/'+scene+'/canals_manifest.json',
                    'pointer': '/washing_steps/'+str(index), 'object_id': stair['id']})
    return {}


def _house_local(house, point):
    """Undo the housekit's coherent lean and shear, including upper floors."""
    x, y, z = point; cx, base, cz = house['center']; yaw = house['yaw']
    c, s = math.cos(yaw), math.sin(yaw)
    u, v = c*(x-cx)+s*(z-cz), -s*(x-cx)+c*(z-cz)
    level = y-base; t = max(0., min(1., level/max(1., house['height'])))
    u -= .15*math.sin(house['seed']*.8)*t+.035*math.sin(level*.9)*t
    v -= .12*math.cos(house['seed']*.6)*t+.025*math.sin(level*.61)*t
    a, b = .14/house['depth'], .12/house['width']; determinant = 1-a*b
    return (u-a*v)/determinant, (v-b*u)/determinant


def _house(scene, hit, manifest):
    model = hit['model_name']
    if model not in _HOUSE_MODELS:
        return {}
    y = hit['hit_position'][1]; candidates = []
    # Roof eaves and folded shutters project beyond the wall. Masonry below the
    # floor must lie on the actual perimeter, never an entire infinite column.
    margin = .70 if model == 'canal_roofs' else .55 if model == 'canal_windows' else .26
    for index, house in enumerate(manifest.get('houses', ())):
        if not house.get('models', {}).get(model):
            continue
        bounds = _bounds(house['bounds_corners'], house.get('foundation_bottom', -2.3), .25)
        if not bounds['min'][1]-.04 <= y <= bounds['max'][1]+.25:
            continue
        u, v = _house_local(house, hit['hit_position'])
        ox, oz = abs(u)-house['width']/2, abs(v)-house['depth']/2
        if max(ox, oz) > margin:
            continue
        if y < house['center'][1]-.08:
            if model != 'canal_masonry' or min(abs(ox), abs(oz)) > .24:
                continue
        # Prefer a containing wall footprint over a neighbouring eave envelope.
        score = max(0., ox)**2+max(0., oz)**2
        candidates.append((score, index, house, bounds))
    if not candidates:
        return {}
    candidates.sort(key=lambda v: v[0])
    if len(candidates)>1 and abs(candidates[0][0]-candidates[1][0]) < .0001:
        return {}  # Shared/overlapping envelopes: keep the precise mesh fallback.
    _, index, house, bounds = candidates[0]
    # Include the known projecting eaves in the highlight's conservative bounds.
    for axis in (0, 2):
        bounds['min'][axis] -= .55; bounds['max'][axis] += .55
    near = index < manifest.get('near_houses', 24)
    identity = house['id']
    duplicate = sum(other['id']==identity for other in manifest.get('houses', ())) > 1
    side = 'west' if house['center'][0]<0 else 'east'
    if duplicate:identity += '-'+side
    label = 'House '+str(house['seed'])+(' '+side if duplicate else '')+' ('+house['variant'].replace('_', ' ')+')'
    return _record(scene, hit, identity, label,
        'building', bounds, 'g_huxin_canals_layout.py' if near else 'build_huxin_canals.py',
        house_seed=house['seed'], fog_target=identity, surface_part=model.removeprefix('canal_'),
        source={'builder': 'build_huxin_canals.py', 'generator': 'canals_housekit.py:build_house',
                'definition': 'HOUSE_SPECS' if near else 'build:far_specs',
                'seed': house['seed'], 'manifest': 'art/temple/'+scene+'/canals_manifest.json',
                'pointer': '/houses/'+str(index), 'object_id': house['id']})


def _bridges(scene, hit):
    model = hit['model_name']
    if model not in ('canal_bridges', 'canal_distant'):
        return {}
    layout = _layout('g_huxin_canals_layout'); x, y, z = hit['hit_position']
    records = list(layout.BRIDGES) if model == 'canal_bridges' else [dict(x0=-4.6, x1=4.8, z=-21.5, width=1.55, rise=.83)]
    if model == 'canal_distant':
        for station in (87., 126., 165., -56., -94., -131.):
            axis = 1.+2.2*math.sin(station*.035+.4)+.7*math.sin(station*.11+.4) if station>0 else 2.2*math.sin(station*.035+1.3)+.7*math.sin(station*.11+1.3)
            records.append(dict(x0=axis-4.5, x1=axis+4.5, z=station, width=1.35, rise=.86))
    for index, bridge in enumerate(records):
        low = layout.DECK+bridge['rise']-.30-3.05/(.91*.91)-.12
        high = layout.DECK+bridge['rise']+.72
        if bridge['x0']-.13<=x<=bridge['x1']+.13 and abs(z-bridge['z'])<=bridge['width']/2+.13 and low<=y<=high:
            identity = 'bridge-z-'+format(bridge['z'], 'g')
            return _record(scene, hit, identity, bridge.get('name', 'Canal bridge at '+format(bridge['z'], 'g')),
                'bridge', {'min':[bridge['x0']-.13,low,bridge['z']-bridge['width']/2-.13],
                           'max':[bridge['x1']+.13,high,bridge['z']+bridge['width']/2+.13]},
                'g_huxin_canals_layout.py' if model=='canal_bridges' else 'build_huxin_canals.py',
                source={'builder':'build_huxin_canals.py', 'function':'build.arch_bridge',
                        'definition':'BRIDGES' if model=='canal_bridges' else 'scenery bridge stations',
                        'station_z':bridge['z'], 'index':index})
    return {}


def _props(scene, hit):
    if hit['model_name'] != 'canal_details':
        return {}
    layout = _layout('g_huxin_canals_layout'); x, y, z = hit['hit_position']
    first = next(h for h in layout.HOUSE_SPECS if h['seed']==110)
    corner = layout.transform(first, first['width']/2+.40, -first['depth']/2+.55)
    for i, (cx, cz) in enumerate(((-13.9,30.3),(13.9,42.),corner,(7.1,51.5))):
        if math.hypot(x-cx,z-cz)<=.335 and layout.DECK-.01<=y<=layout.DECK+.68:
            return _record(scene,hit,'rain-jar-'+str(i),'Rain jar '+str(i+1),'prop',
                _box((cx,layout.DECK+.335,cz),(.335,.345,.335)),'build_huxin_canals.py',
                source={'function':'build', 'definition':'standalone rain jars', 'index':i})
    for i, (cx, cz) in enumerate(((-14.7,34.),(14.,36.6))):
        if abs(x-cx)<=.225 and abs(z-cz)<=.48 and layout.DECK-.01<=y<=layout.DECK+.44:
            return _record(scene,hit,'stone-trough-'+str(i),'Stone trough '+str(i+1),'prop',
                _box((cx,layout.DECK+.215,cz),(.225,.225,.48)),'build_huxin_canals.py',
                source={'function':'build', 'definition':'standalone stone troughs', 'index':i})
    return {}


def _lake_objects(scene, hit):
    model=hit['model_name']; x,y,z=hit['hit_position']
    if not (model.startswith('pavilion_') or model in ('causeway','lake_lamps')):
        return {}
    layout=_layout('g_'+scene)
    builder='build_huxin.py' if scene=='huxin' else 'build_huxin_moon.py'
    source={'layout':'g_'+scene+'.py'}
    if model=='causeway':
        return _record(scene,hit,'causeway','Stone causeway','walkway',hit.get('bounds'),builder,
            source={**source,'definition':'PATH'},surface_part='causeway surface')
    if model in ('lake_lamps','pavilion_details'):
        for i,(cx,cy,cz) in enumerate(layout.LIGHTS):
            radius=.34
            if math.hypot(x-cx,z-cz)<radius and cy-.35<=y<=cy+.40:
                return _record(scene,hit,'lamp-'+str(i),'Pavilion lamp '+str(i+1) if i<3 else 'Shore lamp '+str(i-2),
                    'lamp',_box((cx,cy,cz),(radius,.40,radius)),builder,
                    source={**source,'definition':'LIGHTS','index':i})
        if model=='lake_lamps':
            return {}
    if model=='pavilion_posts':
        for tier,(radius,bottom,top,half) in enumerate(((4.65,layout.DECK,layout.DECK+3.94,.34),(2.48,layout.DECK+5.4,layout.DECK+6.89,.17))):
            for i in range(6):
                cx,cz=math.cos(i*math.tau/6)*radius,math.sin(i*math.tau/6)*radius
                if math.hypot(x-cx,z-cz)<half+.025 and bottom-.02<=y<=top+.02:
                    return _record(scene,hit,('upper-post-' if tier else 'post-')+str(i),
                        ('Upper pavilion post ' if tier else 'Pavilion post ')+str(i+1),'column',
                        _box((cx,(bottom+top)/2,cz),(half,(top-bottom)/2,half)),builder,
                        source={**source,'definition':'COLUMNS' if not tier else 'upper lantern storey','index':i})
    # The details batch also contains shoreline rocks and moss: it is not all
    # pavilion furniture. Only the central pavilion envelope is safe to name.
    if math.hypot(x,z)<=7.5 and layout.DECK-1.31<=y<=layout.DECK+9.86:
        return _record(scene,hit,'pavilion','Lake pavilion','building',
            {'min':[-7.4,layout.DECK-1.30,-7.4],'max':[7.4,layout.DECK+9.86,7.4]},
            builder,source=source,surface_part=model.removeprefix('pavilion_'))
    return {}


def resolve_hit(scene_id, hit):
    """Return semantic fields to merge into an exact ray-hit record, or {}.

    A nonidentity instance is deliberately left to the caller's exact model
    fallback: manifests use authored world coordinates. No triangle identity is
    inferred from material batches. ``hit`` is never modified.
    """
    if not isinstance(scene_id,str) or not isinstance(hit,dict):
        return {}
    scene=scene_id.replace('-','_')
    # The editor keeps its own session/context identity while displaying the
    # same authored canal geometry as gameplay. Resolve against that manifest.
    if scene=='huxin_canals_editor':scene='huxin_canals'
    if scene not in _LAKE_SCENES or not isinstance(hit.get('model_name'),str):
        return {}
    p=hit.get('hit_position')
    if not isinstance(p,(list,tuple)) or len(p)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p):
        return {}
    transform=hit.get('transform',_IDENTITY)
    if not isinstance(transform,(list,tuple)) or len(transform)!=16 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v-i)>1e-4 for v,i in zip(transform,_IDENTITY)):
        return {}
    if scene=='huxin_canals':
        manifest=_manifest(scene)
        for resolver in (_stairs,_house):
            # Small standalone objects take precedence over a building envelope.
            if resolver is _house:
                result=_props(scene,hit)
                if result:return result
            result=resolver(scene,hit,manifest)
            if result:return result
        result=_bridges(scene,hit)
        if result:return result
    return _lake_objects(scene,hit)
