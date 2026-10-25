"""Shared, seekable descent of the lake fog after the concealed world change.

The original formation datum never follows the rendered water height: old and
new worlds must see precisely the same fog throughout their hidden blend.
Only this later authored descent moves the lake layer toward the canal water.
"""
from dataclasses import dataclass

from g_huxin_canals_layout import WATER_Y
from g_huxin_canals_surface_settings import DEFAULT_SURFACE_SETTINGS,surface_blend_window


def shared_causeway_points():
    """Six points on the unchanged path, shared by both fog exclusions."""
    from g_huxin_canals import PATH
    result=[]
    for z in (4.,5.6,7.2,8.8,10.4,12.):
        for a,b in zip(PATH,PATH[1:]):
            if min(a[1],b[1])<=z<=max(a[1],b[1]) and abs(a[1]-b[1])>1.e-8:
                t=(z-a[1])/(b[1]-a[1])
                result.append((a[0]+(b[0]-a[0])*t,z));break
        else:raise ValueError(f'Shared causeway has no point at z={z:g}.')
    return tuple(result)


def _ease(value):
    t=max(0.,min(1.,float(value)))
    return max(0.,min(1.,t*t*t*(10.+t*(-15.+6.*t))))


def descent_progress(value):
    """Steady lowering with brief, smoothly accelerated endpoint ramps.

    A full-duration quintic hides most early movement and concentrates the
    visible level change in its middle. Integrating a smoothstep velocity over
    each 12% end ramp gives continuous velocity/acceleration without that hold.
    """
    t=max(0.,min(1.,float(value)))
    ramp=.12
    if t>=1.:return 1.
    if t>.5:return 1.-descent_progress(1.-t)
    if t<ramp:
        u=t/ramp
        return ramp*(u*u*u-.5*u*u*u*u)/(1.-ramp)
    return (t-ramp*.5)/(1.-ramp)


@dataclass(frozen=True,slots=True)
class LakeFogFrame:
    base_y: float
    descent: float
    depth_hold: float


def lake_fog_frame(profile,elapsed,state='canals'):
    """Return the lake datum, descent fraction, and hidden-depth allowance.

    A late handoff shifts the complete descent window, retaining its duration.
    The optical-path allowance vanishes during the first 65% of the descent,
    restoring ordinary step/bridge occlusion as the dense core drops below it.
    No rendered-world endpoint or accumulated frame time is an input.
    """
    settings=getattr(profile,'surface_fog',DEFAULT_SURFACE_SETTINGS)
    original=float(getattr(settings,'base_y',0.))
    if not (settings.enabled and settings.amount>0. and getattr(settings,'water_settle',False)
            and state in ('entering','canals')):
        return LakeFogFrame(original,0.,1.)
    authored_start=float(getattr(settings,'water_settle_start',35.))
    duration=max(.1,float(getattr(settings,'water_settle_end',47.))-authored_start)
    start=max(authored_start,surface_blend_window(profile)[1])
    descent=descent_progress((float(elapsed)-start)/duration)
    base=original if descent==0. else WATER_Y if descent==1. else original+(WATER_Y-original)*descent
    return LakeFogFrame(base,descent,
                        1.-_ease(descent/.65))


def render_water_height(profile,elapsed,state='canals',revealed=True):
    """Move the physical canal water with the optional descending lake veil.

    Both worlds meet at the original lake height during the hidden handoff.
    The canal mesh, reflection plane and waterline then use this same height.
    A custom fog formation datum changes the mist, never the starting water.
    Profiles without the descending surface mask retain their original water.
    """
    if not revealed:return 0.
    settings=getattr(profile,'surface_fog',DEFAULT_SURFACE_SETTINGS)
    if not (settings.enabled and settings.amount>0.
            and getattr(settings,'water_mask',False)
            and getattr(settings,'water_settle',False)
            and state in ('entering','canals')):
        return WATER_Y
    return WATER_Y*lake_fog_frame(profile,elapsed,state).descent
