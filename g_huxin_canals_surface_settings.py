"""Optional, validated authoring data for geometry-shaped fog.

The distance field and renderer live separately. Merely loading an older
direction file never adds this section or enables a new rendering path.
"""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True, slots=True)
class SurfaceFogSettings:
    enabled: bool = False
    amount: float = 1.
    density: float = 2.2
    thickness: float = 3.4
    edge: float = .6
    noise_size: float = 2.8
    pattern_amount: float = .75
    wind: tuple[float, float, float] = (.26,.05,-.31)
    build_start: float = 0.
    build_end: float = 5.
    reveal_start: float = 8.
    reveal_end: float = 32.
    use_building_timing: bool = True
    evolution: str = 'erode'
    initial_scale: float = .4
    settle_fraction: float = .65
    base_y: float = 0.
    pull_duration: float = 1.15
    wisp_amount: float = .35
    texture_grit: float = 0.
    water_mask: bool = False
    wispy_formation: bool = False
    pixel_grain: float = 0.


DEFAULT_SURFACE_SETTINGS=SurfaceFogSettings()
TIME_KEYS=('build_start','build_end','reveal_start','reveal_end')
SURFACE_OPTIONAL_FIELDS=('evolution','initial_scale','settle_fraction','base_y','pull_duration','wisp_amount','texture_grit','water_mask','wispy_formation','pixel_grain')


def default_surface_document(cues=None):
    result=document_from_surface_settings(DEFAULT_SURFACE_SETTINGS)
    if cues is not None:
        result.update(build_start=0.,build_end=float(cues['build_end']),
            reveal_start=max(float(cues['blend_end']),min(float(cues['end'])-.1,float(cues['blend_end'])+2.)),
            reveal_end=max(float(cues['blend_end'])+2.1,min(float(cues['end']),float(cues['far_end']))))
        # Compact authored timelines need the same valid ordering as long ones.
        fit_surface_times(result,cues)
    return result


def fit_surface_times(value,cues):
    high=cues['end'];blend=cues['blend_end']
    span=blend-cues['build_end'];last_build=high-span-.1
    start=max(0.,min(last_build-.1,value['build_start']))
    end=max(start+.1,min(last_build,value['build_end']))
    effective_end=max(cues['build_end'],end)+span
    reveal=max(effective_end,min(high-.1,value['reveal_start']))
    clear=max(reveal+.1,min(high,value['reveal_end']))
    value.update(build_start=start,build_end=end,reveal_start=reveal,reveal_end=clear)
    return value


def surface_blend_window(profile):
    """Keep the whole geometry handoff behind fully formed surface fog.

    Normal files validate enough room for the original blend span and a final
    clearing interval. The tiny end cap also protects direct runtime callers
    from floating point overshoot at the last authored cue.
    """
    start,end=profile.cue('build_end'),profile.cue('blend_end')
    surface=getattr(profile,'surface_fog',DEFAULT_SURFACE_SETTINGS)
    if not surface.enabled or surface.amount<=0.:return start,end
    span=end-start;start=max(start,surface.build_end)
    end=min(profile.cue('end')-.0001,start+span)
    if end<=start:raise ValueError('Surface fog build leaves no time for the geometry handoff.')
    return start,end


def validate_surface_document(document,cues,error_type=ValueError):
    def fail(path,message):raise error_type('surface_fog.'+path+': '+message)
    if not isinstance(document,dict):fail('','expected an object')
    fields=set(SurfaceFogSettings.__dataclass_fields__)
    required=fields-set(SURFACE_OPTIONAL_FIELDS)
    if required-document.keys():fail('','missing '+', '.join(sorted(required-document.keys())))
    if document.keys()-fields:fail('','unknown field '+', '.join(sorted(map(str,document.keys()-fields))))
    def number(key,low,high,value=None):
        value=document[key] if value is None else value
        if isinstance(value,bool) or not isinstance(value,(float,int)):fail(key,'expected a finite number')
        try:value=float(value)
        except (OverflowError,ValueError):fail(key,'expected a finite number')
        if not math.isfinite(value) or not low<=value<=high:fail(key,f'must be between {low:g} and {high:g}')
        return value
    normalized={}
    for key in ('enabled','use_building_timing'):
        if not isinstance(document[key],bool):fail(key,'expected true or false')
        normalized[key]=document[key]
    for key in ('water_mask','wispy_formation'):
        if key in document:
            if not isinstance(document[key],bool):fail(key,'expected true or false')
            normalized[key]=document[key]
    for key,low,high in (('amount',0.,2.),('density',.05,8.),('thickness',.5,12.),
        ('edge',.1,.95),('noise_size',.3,12.),('pattern_amount',0.,1.),
        ('build_start',0.,cues['end']),('build_end',0.,cues['end']),
        ('reveal_start',cues['blend_end'],cues['end']),('reveal_end',cues['blend_end'],cues['end'])):
        normalized[key]=number(key,low,high)
    if not isinstance(document['wind'],(tuple,list)) or len(document['wind'])!=3:fail('wind','expected [x, y, z]')
    normalized['wind']=[number('wind',-20.,20.,value) for value in document['wind']]
    if 'evolution' in document:
        if document['evolution'] not in ('erode','rise_resolve','condense'):fail('evolution','expected erode, rise_resolve or condense')
        normalized['evolution']=document['evolution']
    for key,low,high in (('initial_scale',.15,1.),('settle_fraction',.2,.9),('base_y',-1000.,1000.),
                         ('pull_duration',.1,15.),('wisp_amount',0.,1.),('texture_grit',0.,1.),('pixel_grain',0.,1.)):
        if key in document:normalized[key]=number(key,low,high)
    if normalized['build_end']-normalized['build_start']<.1-1e-9:fail('build_end','must be at least .1s after build_start')
    span=cues['blend_end']-cues['build_end']
    if normalized['build_end']>cues['end']-span-.1+1e-9:fail('build_end','must leave room for the geometry blend and final clearing')
    earliest_clear=max(cues['build_end'],normalized['build_end'])+span
    if normalized['reveal_start']<earliest_clear-1e-9:fail('reveal_start',f'must be at or after the hidden blend at {earliest_clear:g}s')
    if normalized['reveal_end']-normalized['reveal_start']<.1-1e-9:fail('reveal_end','must be at least .1s after reveal_start')
    return normalized


def surface_settings_from_document(document):
    if document is None:return DEFAULT_SURFACE_SETTINGS
    values=dict(document);values['wind']=tuple(values['wind'])
    return SurfaceFogSettings(**values)


def document_from_surface_settings(settings,authored_fields=()):
    result=asdict(settings);result['wind']=list(settings.wind)
    # Old saved sections stay byte-for-byte equivalent after normalization:
    # optional evolution controls are implicit until authored or changed.
    for key in SURFACE_OPTIONAL_FIELDS:
        if key not in authored_fields and getattr(settings,key)==getattr(DEFAULT_SURFACE_SETTINGS,key):result.pop(key)
    return result
