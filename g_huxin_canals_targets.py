"""Small, stable fog target catalog; the multi-megabyte mesh manifest is offline.

Run this module to rebuild fog_targets.json after exporting changed buildings.
Runtime reads only the compact catalog, once. Bounds include foundations,
warped roof corners and extra eave padding, not just nominal storey heights.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json
import math
from collections import Counter

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / 'art/temple/huxin_canals/fog_targets.json'
MANIFEST_PATH = ROOT / 'art/temple/huxin_canals/canals_manifest.json'


@dataclass(frozen=True, slots=True)
class TargetGroup:
    id: str
    label: str
    kind: str
    center: tuple[float, float, float]
    half_extents: tuple[float, float, float]
    band: str


# These low volumes follow actual canal arms and quays, leaving the original
# central pavilion untouched. They do not form a circular curtain.
_EXTRAS = (
    ('water-west-basin','West basin water','water',(-8.7,-.4,0.),(2.,1.4,6.),'near'),
    ('water-east-basin','East basin water','water',(8.7,-.4,0.),(2.,1.4,6.),'near'),
    ('water-reverse-mouth','Reverse canal mouth','water',(0.,-.4,-9.2),(5.5,1.4,2.),'near'),
    ('water-approach','Main canal near bridge','water',(1.,-.4,20.),(3.8,1.4,11.),'near'),
    ('water-reverse','Reverse canal water','water',(0.,-.4,-25.),(4.8,1.4,14.),'middle'),
    ('water-upper','Main canal upper water','water',(1.,-.4,48.),(4.8,1.4,19.),'middle'),
    ('water-back-west','West washing channel','water',(-17.,-.4,32.),(3.2,1.4,22.),'middle'),
    ('water-back-east','East washing channel','water',(17.,-.4,32.),(3.2,1.4,24.),'middle'),
    ('quay-west-near','West near quay','quay',(-3.,-.4,23.),(1.8,1.8,11.),'near'),
    ('quay-east-near','East near quay','quay',(5.4,-.4,23.),(1.8,1.8,11.),'near'),
    ('quay-west-upper','West upper quay','quay',(-3.,-.4,49.),(2.,1.8,15.),'middle'),
    ('quay-east-upper','East upper quay','quay',(5.5,-.4,49.),(2.,1.8,15.),'middle'),
    ('quay-reverse-west','West reverse quay','quay',(-5.,-.4,-23.),(1.7,1.8,15.),'middle'),
    ('quay-reverse-east','East reverse quay','quay',(5.2,-.4,-23.),(1.7,1.8,15.),'middle'),
    ('bridge-washing','First washing-house bridge','bridge',(1.2,.4,24.),(4.3,2.4,1.7),'near'),
    ('bridge-upper','Upper washing-house bridge','bridge',(2.5,.4,46.),(4.4,2.5,1.8),'middle'),
    ('bridge-reverse','Reverse canal bridge','bridge',(.1,.4,-21.5),(5.2,2.4,1.7),'near'),
    ('backdrop-west','Far west district and hills','backdrop',(-96.,10.,15.),(24.,18.,170.),'far'),
    ('backdrop-east','Far east district and hills','backdrop',(96.,10.,15.),(24.,18.,170.),'far'),
    ('backdrop-north','Far reverse canal horizon','backdrop',(0.,10.,-178.),(100.,18.,26.),'far'),
    ('backdrop-south','Far main canal horizon','backdrop',(0.,10.,218.),(100.,18.,30.),'far'),
    ('foreground-wisps','Thin foreground fragments','foreground',(0.,1.,2.),(15.,2.,18.),'near'),
)


def catalog_from_manifest(manifest):
    """Offline rebuild helper, also useful to verify catalog coverage in tests."""
    rows = []
    counts = Counter(house['id'] for house in manifest['houses'])
    for house in manifest['houses']:
        corners = house['bounds_corners']
        low = [min(p[i] for p in corners) for i in range(3)]
        high = [max(p[i] for p in corners) for i in range(3)]
        low[1] = min(low[1], house.get('foundation_bottom', -2.3))
        for axis in (0,2):low[axis] -= 1.05; high[axis] += 1.05
        high[1] += .7
        center = tuple((a+b)*.5 for a,b in zip(low,high))
        half = tuple((b-a)*.5 for a,b in zip(low,high))
        distance = math.hypot(center[0],center[2])
        band = 'near' if distance < 26. else 'middle' if distance < 70. else 'far'
        side = 'west' if center[0]<0 else 'east'
        arm = 'reverse' if center[2]<0 else 'main'
        ident = house['id'] if counts[house['id']]==1 else f"{house['id']}-{side}"
        rows.append({'id':ident, 'label':f"House {house['seed']} / {side} {arm} canal",
                     'kind':'house', 'center':center, 'half_extents':half, 'band':band})
    for ident,label,kind,center,half,band in _EXTRAS:
        rows.append(dict(id=ident,label=label,kind=kind,center=center,half_extents=half,band=band))
    for edge in range(6):
        a=(7.2*math.cos(edge*math.tau/6),7.2*math.sin(edge*math.tau/6))
        b=(7.2*math.cos((edge+1)*math.tau/6),7.2*math.sin((edge+1)*math.tau/6))
        rows.append(dict(id=f'waterline-{edge+1}',label=f'Pavilion waterline / edge {edge+1}',kind='water',
                         center=((a[0]+b[0])*.5,-.55,(a[1]+b[1])*.5),
                         half_extents=(abs(a[0]-b[0])*.5+.5,1.6,abs(a[1]-b[1])*.5+.5),band='near'))
    return {'version':1,'source':'art/temple/huxin_canals/canals_manifest.json','groups':rows}


@lru_cache(maxsize=1)
def target_groups():
    data = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    if data.get('version') != 1:raise ValueError('Unsupported canals fog target catalog')
    groups = tuple(TargetGroup(row['id'],row['label'],row['kind'],tuple(row['center']),
                               tuple(row['half_extents']),row['band']) for row in data['groups'])
    if len({g.id for g in groups}) != len(groups):raise ValueError('Duplicate fog target IDs')
    for group in groups:
        if len(group.center)!=3 or len(group.half_extents)!=3 or group.band not in ('near','middle','far'):
            raise ValueError(f'Invalid fog target: {group.id}')
        if not all(math.isfinite(v) for v in (*group.center,*group.half_extents)) or min(group.half_extents)<=0:
            raise ValueError(f'Invalid fog target bounds: {group.id}')
    return groups


@lru_cache(maxsize=1)
def _by_id():return {group.id:group for group in target_groups()}


def target_group(ident):return _by_id()[ident]


def coverage_bounds(target, settings):
    """Editor envelope including rolling lobes and the full retreat path."""
    padding = 14. if target.band=='near' else 17. if target.band=='middle' else 26.
    if target.id in ('house-410','house-423','house-437','house-449'):padding+=1.5
    if target.kind=='backdrop':padding=40.
    if target.kind in ('water','quay','bridge','foreground'):padding=9.
    center = tuple(a+b for a,b in zip(target.center,settings.offset))
    extent = tuple((half+padding)*settings.scale for half in target.half_extents)
    return (tuple(c-e for c,e in zip(center,extent)),tuple(c+e for c,e in zip(center,extent)))


if __name__ == '__main__':
    result = catalog_from_manifest(json.loads(MANIFEST_PATH.read_text(encoding='utf-8')))
    CATALOG_PATH.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f"Wrote {len(result['groups'])} fog target groups to {CATALOG_PATH}")
