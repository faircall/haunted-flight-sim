"""Independent, authored 3D fog regions for the canal reveal.

Everything here is deterministic and GPU independent. Regions describe actual
world space, rather than camera-facing screens. The renderer supplies animated
3D noise; these envelopes control where it may exist. Existing direction files
without a volumes section retain precisely their previous behavior.
"""
from dataclasses import dataclass, replace, asdict
import math
import re


MAX_VOLUMES = 24
QUALITIES = ('draft', 'balanced', 'high')
_DEFAULT_CUES = dict(zip(('start', 'build_end', 'blend_end', 'middle_start',
    'near_end', 'far_start', 'middle_end', 'far_end', 'end'),
    (0., 5., 6., 12., 14., 20., 22., 32., 46.)))


@dataclass(frozen=True, slots=True)
class VolumeRegion:
    id: str
    label: str
    enabled: bool
    shape: str
    center: tuple[float, float, float]
    half_extents: tuple[float, float, float]
    yaw: float
    density: float
    edge: float
    noise_size: float
    turbulence: float
    wind: tuple[float, float, float]
    hollow: float
    fade_in_start: float
    fade_in_end: float
    reveal_start: float
    reveal_end: float
    retreat: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class VolumeSettings:
    enabled: bool = False
    mix: float = 1.
    particle_mix: float = 1.
    quality: str = 'balanced'
    regions: tuple[VolumeRegion, ...] = ()

    def region(self, ident):
        for region in self.regions:
            if region.id == ident:return region
        raise KeyError(ident)


DEFAULT_VOLUME_SETTINGS = VolumeSettings()


def default_volume_document(cues=None):
    """Return an independent optional volumes section (not a direction file)."""
    return dict(enabled=False, mix=1., particle_mix=1., quality='balanced', regions={})


def default_region_document(cues=None, *, label='Fog volume', shape='box'):
    cues = _DEFAULT_CUES if cues is None else cues
    return dict(label=label, enabled=True, shape=shape, center=[0., 2., 12.],
        half_extents=[4., 3., 5.], yaw=0., density=.22, edge=.38,
        noise_size=3., turbulence=.7, wind=[.38, .04, -.24], hollow=0.,
        fade_in_start=0., fade_in_end=float(cues['build_end']),
        reveal_start=float(cues['blend_end']), reveal_end=float(cues['middle_end']),
        retreat=[0., .3, 4.])


def _remap_time(time, cues):
    names = tuple(_DEFAULT_CUES)
    for a, b in zip(names, names[1:]):
        if time <= _DEFAULT_CUES[b]:
            t=(time-_DEFAULT_CUES[a])/(_DEFAULT_CUES[b]-_DEFAULT_CUES[a])
            return cues[a] + t*(cues[b]-cues[a])
    return cues['end']


def demo_volume_document(cues=None):
    """Fitted house shells, low canal banks and an alley: no pavilion ring."""
    from g_huxin_canals_targets import target_groups
    cues = _DEFAULT_CUES if cues is None else cues
    targets = {target.id:target for target in target_groups()}
    result = default_volume_document(cues)
    result.update(enabled=True, particle_mix=.5)
    houses=('house-410', 'house-423', 'house-437', 'house-449',
            'house-110', 'house-211', 'house-121', 'house-224')
    for index, ident in enumerate(houses):
        target=targets[ident]
        value=default_region_document(cues, label=target.label+' / volume')
        value.update(center=list(target.center),
            half_extents=[size+1.4 for size in target.half_extents],
            density=.30, edge=.32, hollow=.58, noise_size=3.4,
            wind=[.32 if index%2 else -.38, .06, -.24],
            reveal_start=_remap_time(7.+index*1.3,cues),
            reveal_end=_remap_time(20.+index*1.4,cues),
            retreat=[-2. if target.center[0]<0 else 2., .6,
                     -3. if target.center[2]<0 else 3.])
        result['regions']['volume-'+ident]=value
    for index, ident in enumerate(('water-west-basin','water-east-basin',
                                  'water-reverse','water-approach','water-upper')):
        target=targets[ident]
        value=default_region_document(cues,label=target.label+' / low volume',shape='ellipsoid')
        value.update(center=[target.center[0],-.05,target.center[2]],
            half_extents=[target.half_extents[0]+.7,.9,target.half_extents[2]+1.5],
            density=.24, edge=.55, noise_size=2.3, turbulence=.8,
            wind=[.24,.025,-.43],
            reveal_start=_remap_time(8.+index*1.5,cues),
            reveal_end=_remap_time(23.+index*2.5,cues),
            retreat=[.8,.15,-3. if target.center[2]<0 else 4.])
        result['regions']['volume-'+ident]=value
    value=default_region_document(cues,label='West washing passage / drifting channel')
    value.update(center=[-17.,1.6,29.],half_extents=[2.4,2.5,12.],
        density=.19,edge=.55,noise_size=2.5,hollow=0.,wind=[.10,.03,.46],
        reveal_start=_remap_time(17.,cues),reveal_end=_remap_time(37.,cues),
        retreat=[0.,.4,8.])
    result['regions']['volume-west-passage']=value
    return validate_volume_document(result,cues)


def validate_volume_document(document, cues=None, error_type=ValueError):
    cues=_DEFAULT_CUES if cues is None else cues
    def fail(path,message):raise error_type(f'{path}: {message}')
    def obj(value,path,fields):
        if not isinstance(value,dict):fail(path,'expected an object')
        missing=set(fields)-value.keys();unknown=value.keys()-set(fields)
        if missing:fail(path,'missing '+', '.join(sorted(missing)))
        if unknown:fail(path,'unknown field '+', '.join(sorted(map(str,unknown))))
    def number(value,path,low,high):
        if isinstance(value,bool) or not isinstance(value,(int,float)):
            fail(path,'expected a finite number')
        try:value=float(value)
        except (ValueError,OverflowError):fail(path,'expected a finite number')
        if not math.isfinite(value):fail(path,'expected a finite number')
        if not low<=value<=high:fail(path,f'must be between {low:g} and {high:g}')
        return value
    def vec(value,path,low=-1000.,high=1000.):
        if not isinstance(value,(tuple,list)) or len(value)!=3:fail(path,'expected three coordinates [x, y, z]')
        return [number(v,f'{path}[{i}]',low,high) for i,v in enumerate(value)]
    obj(document,'volumes',('enabled','mix','particle_mix','quality','regions'))
    if not isinstance(document['enabled'],bool):fail('volumes.enabled','expected true or false')
    if document['quality'] not in QUALITIES:fail('volumes.quality','expected draft, balanced or high')
    if not isinstance(document['regions'],dict):fail('volumes.regions','expected an object keyed by stable region IDs')
    if len(document['regions'])>MAX_VOLUMES:fail('volumes.regions',f'at most {MAX_VOLUMES} regions are supported')
    result=dict(enabled=document['enabled'],mix=number(document['mix'],'volumes.mix',0.,2.),
        particle_mix=number(document['particle_mix'],'volumes.particle_mix',0.,2.),
        quality=document['quality'],regions={})
    fields=tuple(VolumeRegion.__dataclass_fields__)[1:]
    for ident,value in document['regions'].items():
        path=f'volumes.regions.{ident}'
        if not isinstance(ident,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',ident):
            fail('volumes.regions','IDs must use 1–64 lower-case letters, digits, underscores or hyphens')
        obj(value,path,fields)
        if not isinstance(value['label'],str) or not value['label'].strip() or len(value['label'])>96:
            fail(path+'.label','expected a nonempty label of at most 96 characters')
        if not isinstance(value['enabled'],bool):fail(path+'.enabled','expected true or false')
        if value['shape'] not in ('box','ellipsoid'):fail(path+'.shape','expected box or ellipsoid')
        normalized=dict(label=value['label'],enabled=value['enabled'],shape=value['shape'])
        for key,low,high in (('center',-1000.,1000.),('half_extents',.1,500.),
                             ('wind',-20.,20.),('retreat',-500.,500.)):
            normalized[key]=vec(value[key],path+'.'+key,low,high)
        for key,low,high in (('yaw',-360.,360.),('density',0.,8.),('edge',.02,1.),
            ('noise_size',.1,100.),('turbulence',0.,1.),('hollow',0.,.95),
            ('fade_in_start',0.,cues['end']),('fade_in_end',0.,cues['end']),
            ('reveal_start',cues['blend_end'],cues['end']),
            ('reveal_end',cues['blend_end'],cues['end'])):
            normalized[key]=number(value[key],path+'.'+key,low,high)
        if normalized['fade_in_end']-normalized['fade_in_start']<.1-1e-9:
            fail(path+'.fade_in_end','must be at least .1s after fade_in_start')
        if normalized['reveal_start']<normalized['fade_in_end']:
            fail(path+'.reveal_start','must be at or after fade_in_end')
        if normalized['reveal_end']-normalized['reveal_start']<.1-1e-9:
            fail(path+'.reveal_end','must be at least .1s after reveal_start')
        result['regions'][ident]=normalized
    return result


def settings_from_document(document):
    if document is None:return DEFAULT_VOLUME_SETTINGS
    values={key:document[key] for key in ('enabled','mix','particle_mix','quality')}
    regions=[]
    for ident,value in document['regions'].items():
        value=dict(value)
        for key in ('center','half_extents','wind','retreat'):value[key]=tuple(value[key])
        regions.append(VolumeRegion(id=ident,**value))
    return VolumeSettings(**values,regions=tuple(regions))


def document_from_settings(settings):
    result={key:getattr(settings,key) for key in ('enabled','mix','particle_mix','quality')}
    result['regions']={}
    for region in settings.regions:
        value=asdict(region);value.pop('id')
        for key in ('center','half_extents','wind','retreat'):value[key]=list(value[key])
        result['regions'][region.id]=value
    return result


def _smooth(t):
    t=max(0.,min(1.,t))
    return t*t*t*(10.+t*(-15.+6.*t))


def volume_frame_at(elapsed, clock, settings):
    """Sample envelopes without accumulated state; noise uses clock in GLSL.

    Each bank begins retreating a quarter of its clearing interval before its
    density decreases. A gently bowed path avoids a mechanical linear shove.
    Frames retain named fields so inspection and reflection share one source.
    """
    if not math.isfinite(elapsed) or not math.isfinite(clock):raise ValueError('Volume sample times must be finite.')
    if not settings.enabled or settings.mix<=0.:return ()
    output=[]
    for region in settings.regions:
        if not region.enabled or region.density<=0.:continue
        arrival=_smooth((elapsed-region.fade_in_start)/(region.fade_in_end-region.fade_in_start))
        t=max(0.,min(1.,(elapsed-region.reveal_start)/(region.reveal_end-region.reveal_start)))
        density=region.density*settings.mix*arrival*(1.-_smooth((t-.25)/.75))
        if density<=1e-7:continue
        move=_smooth(t)
        distance=math.hypot(region.retreat[0],region.retreat[2])
        bow=math.sin(math.pi*move)*min(distance*.12,1.4)
        center=tuple(c+d*move+(bow if i==1 else 0.) for i,(c,d) in enumerate(zip(region.center,region.retreat)))
        output.append(replace(region,center=center,density=density))
    return tuple(output)


def local_point(point, region):
    x,y,z=(p-c for p,c in zip(point,region.center))
    angle=math.radians(region.yaw);c,s=math.cos(angle),math.sin(angle)
    return (c*x+s*z,y,-s*x+c*z)


def envelope_density(point, region):
    """Noise-free world-space extinction; useful for gizmos and spatial QA."""
    q=tuple(abs(v)/h for v,h in zip(local_point(point,region),region.half_extents))
    radius=math.sqrt(sum(v*v for v in q)) if region.shape=='ellipsoid' else max(q)
    outer=_smooth((1.-radius)/region.edge)
    # A hollow box leaves a building's interior clear while wrapping all sides.
    inner=1. if not region.hollow else _smooth((radius-region.hollow)/min(region.edge,.25))
    return max(0.,region.density*outer*inner) if region.enabled else 0.


def ray_interval(origin, direction, region):
    """Positive world-ray interval through an oriented box or ellipsoid."""
    if not all(math.isfinite(v) for v in (*origin,*direction)):raise ValueError('Ray must be finite.')
    p=local_point(origin,region)
    end=local_point(tuple(o+d for o,d in zip(origin,direction)),region)
    d=tuple(e-v for e,v in zip(end,p))
    if sum(v*v for v in d)<1e-18:return None
    if region.shape=='ellipsoid':
        p=tuple(v/h for v,h in zip(p,region.half_extents));d=tuple(v/h for v,h in zip(d,region.half_extents))
        a=sum(v*v for v in d);b=sum(u*v for u,v in zip(p,d));c=sum(v*v for v in p)-1.
        disc=b*b-a*c
        if disc<0.:return None
        root=math.sqrt(disc);lo,hi=(-b-root)/a,(-b+root)/a
    else:
        lo,hi=-math.inf,math.inf
        for value,delta,extent in zip(p,d,region.half_extents):
            if abs(delta)<1e-12:
                if abs(value)>extent:return None
            else:
                a,b=(-extent-value)/delta,(extent-value)/delta
                lo=max(lo,min(a,b));hi=min(hi,max(a,b))
    lo=max(0.,lo)
    return (lo,hi) if hi>=lo else None
