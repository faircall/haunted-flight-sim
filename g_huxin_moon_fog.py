"""Local teahouse concealment, sampled without a renderer or accumulated time.

The old pavilion, lake and causeway retain their own assets. These small banks
cover only changed architecture: walls, roof, stair, annex and hanging details.
Bounds are fitted to the exported moon GLBs, in the game's world coordinates.
"""
from dataclasses import dataclass,replace
import math


ENTRY_CONCEAL_END=8.5
RETURN_CONCEAL_END=.53


@dataclass(frozen=True,slots=True)
class MoonFogRegion:
    id: str
    center: tuple[float,float,float]
    half_extents: tuple[float,float,float]
    density: float
    edge: float
    noise_size: float
    wind: tuple[float,float,float]
    clear_start: float
    clear_end: float
    role: str
    build_start: float = 0.
    build_end: float = 7.2


def _region(identity,center,half,density,clears,role,edge=.55,noise=1.45,build_start=0.):
    return MoonFogRegion(identity,center,half,density,edge,noise,
                         (.065,.024,-.055),*clears,role,build_start)


_ARCHITECTURE=(
    _region('west-wall',(-6.9,3.85,.1),(1.25,4.2,6.95),3.4,(10.2,19.2),'wall'),
    _region('north-wall',(0.,3.85,-5.95),(7.75,4.2,1.25),3.3,(9.8,18.5),'wall'),
    _region('east-wall',(6.9,3.85,.1),(1.25,4.2,6.95),3.3,(10.6,19.5),'wall'),
    # Deeper front banks include the six balcony supports at z=8, with a
    # deliberate opening between them along the causeway's centre.
    _region('entry-west',(-4.2,3.85,6.45),(3.45,4.2,1.65),3.3,(8.6,17.),'wall'),
    _region('entry-east',(4.2,3.85,6.45),(3.45,4.2,1.65),3.3,(9.2,17.8),'wall'),
    _region('timber-stair',(-5.65,2.65,.05),(1.55,2.9,5.25),2.8,(10.8,19.5),'stair'),
    _region('east-annex',(10.05,1.9,0.),(3.6,2.3,3.95),2.5,(9.6,19.4),'annex'),
    _region('annex-roof',(10.05,4.75,0.),(4.,1.55,4.35),2.,(11.2,21.),'roof',noise=1.7),
    _region('upper-balcony',(0.,6.25,7.25),(7.85,2.25,1.65),2.4,(11.6,22.),'balcony'),
    # Both existing entry cameras are at y=3.6. Even the soft extension of
    # this sheet begins above their lenses, rather than enveloping the view.
    _region('upper-floor',(0.,4.65,.15),(7.5,.75,6.6),3.4,(10.4,20.5),'ceiling',edge=.22),
    _region('main-roof',(0.,9.25,.35),(8.95,4.35,8.7),1.8,(12.4,24.),'roof',edge=.7,noise=1.9),
)
_COLUMN_HEADS=tuple(
    _region(f'column-head-{i}',(4.65*math.cos(i*math.tau/6),4.32,4.65*math.sin(i*math.tau/6)),
            (.95,.52,.95),3.,(10.+i*.18,20.+i*.22),'bracket',edge=.19,noise=1.1)
    for i in range(6))
_LANTERNS=tuple(
    _region(f'ground-lantern-{i}',(x,y,z),(.62,.63,.62),3.1,
            (10.5+i*.4,19.+i*.7),'lantern',edge=.25,noise=.85,build_start=4.3)
    for i,(x,y,z) in enumerate(((-3.,3.225,2.8),(3.,3.225,2.8),(0.,3.275,-3.7))))
_FOOTINGS=tuple(
    _region(f'footing-{i}',(x,.05,z),(1.65,.55,1.65),2.6,
            (9.2+i*.25,18.+i*.35),'footing',edge=.4,noise=1.2)
    for i,(x,z) in enumerate(((-5.7,-4.7),(5.7,-4.7),(-5.7,4.7),(5.7,4.7))))
MOON_FOG_REGIONS=_ARCHITECTURE+_COLUMN_HEADS+_LANTERNS+_FOOTINGS


def _ease(a,b,value):
    t=max(0.,min(1.,(value-a)/max(1.e-9,b-a)))
    return max(0.,min(1.,t*t*t*(10.+t*(-15.+6.*t))))


def _finite(value):
    value=float(value)
    if not math.isfinite(value):raise ValueError('Moon fog progress must be finite.')
    return value


def _optical_remaining(clear):
    # Against an eight-unit optical path, visible opacity follows 1-clear.
    # An ordinary density multiplier would remain saturated until its tail.
    return max(0.,min(1.,-math.log(clear+(1.-clear)*math.exp(-8.))/8.))


@dataclass(frozen=True,slots=True)
class MoonFogFrame:
    strength: float
    build: float
    clearing: float
    depth_hold: float
    regions: tuple[MoonFogRegion,...]

    @property
    def active(self):return self.strength>1.e-7


def moon_fog_frame(sequence):
    """Final per-bank extinction; the renderer must not multiply it again.

    Region count/order and bounds stay fixed, even when all densities are zero.
    Entry uses the existing 24-second clock; departure uses path position, so
    walking, stopping and reversing remain interactive. Neither logical world
    endpoint nor camera position changes the field at the hidden handoff.
    """
    state=sequence.state
    if state=='entering':
        t=_finite(sequence.elapsed)
        build=_ease(0.,7.2,t)
        clearing=_ease(ENTRY_CONCEAL_END,24.,t)
        hold=build*(1.-_ease(ENTRY_CONCEAL_END,19.5,t))
        weights=[_optical_remaining(1.-_ease(region.build_start,region.build_end,t))*
                 _optical_remaining(_ease(region.clear_start,region.clear_end,t))
                 for region in MOON_FOG_REGIONS]
    elif state=='leaving':
        t=_finite(sequence.return_progress)
        build=_ease(.025,.43,t)
        clearing=_ease(.54,.98,t)
        hold=build*(1.-_ease(RETURN_CONCEAL_END,.82,t))
        weights=[]
        for region in MOON_FOG_REGIONS:
            start=.54+.11*(region.clear_start-8.6)/(12.4-8.6)
            end=.83+.15*(region.clear_end-17.)/(24.-17.)
            weights.append(_optical_remaining(1.-build)*_optical_remaining(_ease(start,end,t)))
    else:
        build=clearing=hold=0.
        weights=[0.]*len(MOON_FOG_REGIONS)
    regions=tuple(replace(region,density=region.density*weight)
                  for region,weight in zip(MOON_FOG_REGIONS,weights))
    return MoonFogFrame(max(weights,default=0.),build,clearing,hold,regions)
