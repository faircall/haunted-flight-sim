"""Deterministic timing reference for the fog's inward contraction.

The two standalone GPU shaders embed shaders/huxin_canals_condense.glsl so
Raylib's existing mesh/skin shader loading stays intact. Both use these same
per-building windows and stable world-space delays, including reflections.
"""
import math


def _ease(a,b,value):
    t=max(0.,min(1.,(value-a)/max(.0001,b-a)))
    return t*t*t*(10.+t*(-15.+6.*t))


def _fract(value):return value-math.floor(value)


def _hash(point):
    p=[_fract(v*.1031) for v in point]
    dot=sum(p[i]*(p[(i+1)%3]+33.33) for i in range(3))
    p=[v+dot for v in p]
    return _fract((p[0]+p[1])*p[2])


def _noise(point):
    cell=[math.floor(v) for v in point]
    f=[_fract(v) for v in point];f=[v*v*(3.-2.*v) for v in f]
    total=0.
    for x in (0,1):
        for y in (0,1):
            for z in (0,1):
                bits=(x,y,z)
                weight=math.prod(f[i] if bits[i] else 1.-f[i] for i in range(3))
                total+=weight*_hash([cell[i]+bits[i] for i in range(3)])
    return total


def condense_window(window,hold_fraction=.5,pull_duration=1.15):
    """Nominal pull start and effective duration, before the local noise delay.

    Long requested pulls may be shortened by their house's authored window.
    Exposing that duration lets authoring/QA verify the actual motion length
    instead of assuming the global duration is always attainable.
    """
    span=max(.1,window[1]-window[0])
    starts=window[0]+span*hold_fraction
    duration=max(.0001,min(pull_duration,span*(1.-hold_fraction)*.55))
    return starts,duration


def condense_phases(point,window,now,hold_fraction=.5,pull_duration=1.15,noise_size=2.8,pattern=.75):
    """Return tightening, inward pull, residual wisps, material emergence."""
    starts,duration=condense_window(window,hold_fraction,pull_duration)
    delay=_noise([v/max(.3,noise_size)+offset for v,offset in zip(point,(7.1,13.7,3.9))])*duration*.35*pattern
    starts+=delay;ends=starts+duration
    raw=max(0.,min(1.,(now-starts)/duration))
    patient=_ease(3.,6.,duration)
    pull=_ease(0.,1.,raw)*(1.-patient)+raw*raw*(3.-2.*raw)*patient
    material=_ease(.18,.84,raw)*(1.-patient)+_ease(.03,.97,raw)*patient
    return (_ease(window[0],starts,now),pull,
            1.-_ease(ends,window[1],now),material)
