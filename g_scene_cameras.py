"""Pure camera validation, composition and spatial activation.

Movement controls the eye, aim controls the target, and lens controls field of
view. None of these routines opens a window or evaluates authored code.
"""
from copy import deepcopy
import math
import re

MOVEMENTS=('locked','path','follow')
AIMS=('fixed','pan','player','keep_visible')
LENSES=('fixed','zoom')
EASINGS=('linear','smooth')
TRIGGERS=('reveal','focus','lake','room','zone')


class CameraValidationError(ValueError):pass


def _number(value,path,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise CameraValidationError(f'{path}: expected a finite number')
    try:value=float(value)
    except (OverflowError,ValueError):raise CameraValidationError(f'{path}: expected a finite number') from None
    if not math.isfinite(value) or not low<=value<=high:
        raise CameraValidationError(f'{path}: must be between {low:g} and {high:g}')
    return value


def _vector(value,path):
    if not isinstance(value,(list,tuple)) or len(value)!=3:
        raise CameraValidationError(f'{path}: expected three coordinates')
    return [_number(v,f'{path}[{i}]',-10000.,10000.) for i,v in enumerate(value)]


def _object(value,path,required,optional=()):
    if not isinstance(value,dict):raise CameraValidationError(f'{path}: expected an object')
    missing=set(required)-value.keys();extra=value.keys()-set(required)-set(optional)
    if missing:raise CameraValidationError(f'{path}: missing '+', '.join(sorted(missing)))
    if extra:raise CameraValidationError(f'{path}: unknown fields '+', '.join(sorted(map(str,extra))))


def _text(value,path,limit=100):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):
        raise CameraValidationError(f'{path}: expected nonempty text, at most {limit} characters')
    return value


def _pose(value,path):
    _object(value,path,('eye','target','fov'))
    result=dict(eye=_vector(value['eye'],path+'.eye'),target=_vector(value['target'],path+'.target'),
                fov=_number(value['fov'],path+'.fov',10.,140.))
    if math.dist(result['eye'],result['target'])<.05:
        raise CameraValidationError(path+': eye and target must be at least .05m apart')
    return result


def actor_position(actor):
    """Accept the gameplay Explorer, an XYZ dict, or an authored XYZ list."""
    if isinstance(actor,(list,tuple)):return _vector(actor,'actor')
    if isinstance(actor,dict):
        if 'actor' in actor:return _vector(actor['actor'],'actor')
        return _vector((actor.get('x'),actor.get('y',actor.get('height')),actor.get('z')),'actor')
    return _vector((getattr(actor,'x',None),getattr(actor,'height',getattr(actor,'y',None)),getattr(actor,'z',None)),'actor')


def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _sub(a,b):return [x-y for x,y in zip(a,b)]
def _add(a,b):return [x+y for x,y in zip(a,b)]
def _mix(a,b,t):return [x+(y-x)*t for x,y in zip(a,b)]
def _cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _unit(value):
    length=math.sqrt(_dot(value,value))
    return [v/length for v in value] if length>1.e-9 else [0.,0.,-1.]


def validate_document(document):
    """Return a normalized deep copy; reject unknown, singular or unsafe data."""
    _object(document,'cameras',('version','scene','shots'))
    if type(document['version']) is not int or document['version']!=1:
        raise CameraValidationError('version: expected camera document version 1')
    scene=_text(document['scene'],'scene',64)
    if not isinstance(document['shots'],list) or not 1<=len(document['shots'])<=256:
        raise CameraValidationError('shots: expected between 1 and 256 shots')
    result={'version':1,'scene':scene,'shots':[]};ids=set()
    for i,shot in enumerate(document['shots']):
        path=f'shots[{i}]'
        _object(shot,path,('id','label','enabled','activation','movement','aim','lens','easing','duration','start','end','preview'),('aim_offset',))
        identity=_text(shot['id'],path+'.id',80)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',identity):
            raise CameraValidationError(path+'.id: use letters, numbers, hyphens and underscores')
        if identity in ids:raise CameraValidationError(path+'.id: duplicate shot id '+identity)
        ids.add(identity)
        if type(shot['enabled']) is not bool:raise CameraValidationError(path+'.enabled: expected true or false')
        clean=dict(id=identity,label=_text(shot['label'],path+'.label'),enabled=shot['enabled'])
        for field,allowed in (('movement',MOVEMENTS),('aim',AIMS),('lens',LENSES),('easing',EASINGS)):
            if shot[field] not in allowed:raise CameraValidationError(path+'.'+field+': expected '+', '.join(allowed))
            clean[field]=shot[field]
        clean['duration']=_number(shot['duration'],path+'.duration',.1,300.)
        clean['start']=_pose(shot['start'],path+'.start');clean['end']=_pose(shot['end'],path+'.end')
        preview=shot['preview'];_object(preview,path+'.preview',('phase','actor','yaw'))
        if preview['phase'] not in ('lake','teahouse','reveal'):raise CameraValidationError(path+'.preview.phase: unknown phase')
        clean['preview']=dict(phase=preview['phase'],actor=_vector(preview['actor'],path+'.preview.actor'),
                              yaw=_number(preview['yaw'],path+'.preview.yaw',-10000.,10000.))
        clean['aim_offset']=_vector(shot.get('aim_offset',(0.,.95,0.)),path+'.aim_offset')
        activation=shot['activation'];_object(activation,path+'.activation',('type',),('index','priority','bounds','phase'))
        kind=activation['type']
        if kind not in TRIGGERS:raise CameraValidationError(path+'.activation.type: unknown trigger')
        priority=activation.get('priority',0)
        if type(priority) is not int or not -1000<=priority<=1000:raise CameraValidationError(path+'.activation.priority: expected integer -1000..1000')
        active={'type':kind,'priority':priority}
        if kind in ('lake','room'):
            index=activation.get('index')
            if type(index) is not int or not 0<=index<=4095:raise CameraValidationError(path+'.activation.index: expected integer 0..4095')
            active['index']=index
            if 'bounds' in activation or 'phase' in activation:raise CameraValidationError(path+'.activation: indexed shot cannot have zone fields')
        elif kind=='zone':
            if 'index' in activation:raise CameraValidationError(path+'.activation: zone cannot have an index')
            phase=activation.get('phase','any')
            if phase not in ('any','lake','teahouse'):raise CameraValidationError(path+'.activation.phase: unknown zone phase')
            bounds=activation.get('bounds');_object(bounds,path+'.activation.bounds',('min','max'))
            low=_vector(bounds['min'],path+'.activation.bounds.min');high=_vector(bounds['max'],path+'.activation.bounds.max')
            if any(b-a<.01 for a,b in zip(low,high)):raise CameraValidationError(path+'.activation.bounds: each maximum must exceed minimum by at least .01m')
            active.update(phase=phase,bounds={'min':low,'max':high})
        elif any(key in activation for key in ('index','bounds','phase')):
            raise CameraValidationError(path+'.activation: this trigger has no spatial fields')
        clean['activation']=active
        # Known authored trajectories must not interpolate through a zero
        # viewing direction. Dynamic actor crossings are guarded at sampling.
        eye0=clean['start']['eye'];eye1=clean['end']['eye'] if clean['movement']=='path' else eye0
        target0=clean['start']['target'];target1=clean['end']['target'] if clean['aim']=='pan' else target0
        if clean['aim']=='player':target0=target1=_add(clean['preview']['actor'],clean['aim_offset'])
        a=_sub(target0,eye0);b=_sub(_sub(target1,eye1),a);denom=_dot(b,b)
        t=max(0.,min(1.,-_dot(a,b)/denom)) if denom>1.e-12 else 0.
        if clean['aim']!='keep_visible' and math.sqrt(_dot(_add(a,[t*v for v in b]),_add(a,[t*v for v in b])))<.05:
            raise CameraValidationError(path+': authored camera path crosses its aim target')
        result['shots'].append(clean)
    return result


def sample_shot(shot,elapsed,actor=None,aspect=16/9):
    """Compose independent eye motion, target motion and lens interpolation."""
    elapsed=_number(elapsed,'elapsed',-1.e9,1.e9);aspect=_number(aspect,'aspect',.1,10.)
    duration=_number(shot['duration'],'duration',.1,300.)
    t=max(0.,min(1.,elapsed/duration))
    if shot['easing']=='smooth':t=t*t*t*(10.+t*(-15.+6.*t))
    a,b=shot['start'],shot['end'];position=actor_position(shot['preview']['actor'] if actor is None else actor)
    eye=list(a['eye'])
    if shot['movement']=='path':eye=_mix(a['eye'],b['eye'],t)
    elif shot['movement']=='follow':eye=_add(a['eye'],_sub(position,shot['preview']['actor']))
    fov=float(a['fov']) if shot['lens']=='fixed' else float(a['fov'])+(float(b['fov'])-float(a['fov']))*t
    target=list(a['target']);body=_add(position,shot.get('aim_offset',(0.,.95,0.)))
    if shot['aim']=='pan':target=_mix(a['target'],b['target'],t)
    elif shot['aim']=='player':target=body
    elif shot['aim']=='keep_visible':
        forward=_unit(_sub(target,eye));right=_cross(forward,[0.,1.,0.])
        if _dot(right,right)<1.e-8:right=_cross(forward,[0.,0.,1.])
        right=_unit(right);up=_cross(right,forward);delta=_sub(body,eye)
        depth=_dot(delta,forward);tan=math.tan(math.radians(fov)*.5)
        visible=depth>1. and abs(_dot(delta,right))<depth*tan*aspect*.82 and abs(_dot(delta,up))+.88<depth*tan*.84
        if not visible:target=body
    if math.dist(eye,target)<.05:
        direction=_unit(_sub(a['target'],a['eye']));target=_add(eye,[v*.25 for v in direction])
    return {'eye':list(map(float,eye)),'target':list(map(float,target)),'fov':float(fov)}


def resolve_shot(document,trigger,actor,state):
    """Choose the highest-priority enabled match; document order breaks ties.

    Spatial zones override ordinary gameplay stations only. They can never
    steal the mirror focus or the held reveal choreography.
    """
    if not isinstance(trigger,dict) or trigger.get('type') not in ('reveal','focus','lake','room'):
        raise CameraValidationError('trigger: expected reveal, focus, lake or room')
    kind=trigger['type'];position=actor_position(actor);phase=str(state)
    matches=[]
    for i,shot in enumerate(document['shots']):
        if not shot['enabled']:continue
        active=shot['activation'];mode=active['type'];match=False
        if mode==kind:match=mode in ('reveal','focus') or active['index']==trigger.get('index')
        elif mode=='zone' and kind in ('lake','room'):
            bounds=active['bounds']
            match=active['phase'] in ('any',phase) and all(a<=v<=b for a,v,b in zip(bounds['min'],position,bounds['max']))
        if match:matches.append((active.get('priority',0),-i,shot))
    return max(matches,key=lambda value:value[:2])[2] if matches else None
