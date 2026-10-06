"""Portable camera poses shared by intro playback and the cinematics editor."""
from copy import deepcopy
import math
from g_santana_geometry import inside_cabin,CABIN_EYE


def pose(eye,target,fov):return dict(eye=list(eye),target=list(target),fov=float(fov))


def default_camera(kind):
    if kind=='opening':
        start=pose((1.61,1.29,.63),(0,1.22,.62),48);end=pose((1.72,1.29,.53),(0,1.22,.62),48)
    elif kind=='drone':
        start=pose((5,20,7),(0,.1,-3),48);end=pose((6.5,20,3),(0,.1,-3),48)
    elif kind=='tracking':
        start=end=pose((3.55,1.55,.06),(0,.87,-.12),62)
    elif kind=='arrival':
        start=pose((0,4.6,8),(0,1.1,-10),58);end=pose((0,4.9,7),(0,1.1,-10),58)
    elif kind=='interior':
        a=math.radians(-8)
        x,y,z=CABIN_EYE
        start=end=pose(CABIN_EYE,(x,y+math.sin(a),z-math.cos(a)),62)
    else:start=end=pose((6,3,6),(0,1,0),58)
    return dict(mode='interactive' if kind=='interior' else 'fixed',
                view='interior' if kind=='interior' else 'exterior',ease='smooth',
                start=deepcopy(start),end=deepcopy(end))


def validate_camera(camera):
    if camera.get('mode') not in ('interactive','fixed') or camera.get('view') not in ('interior','exterior'):
        raise ValueError('Camera mode or scene view is invalid.')
    if camera.get('ease') not in ('linear','smooth'):raise ValueError('Camera easing is invalid.')
    for name in ('start','end'):
        frame=camera[name]
        for key in ('eye','target'):
            values=frame[key]
            if len(values)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):
                raise ValueError('Camera coordinates must be three finite numbers.')
            if any(abs(v)>10000 for v in values):raise ValueError('Camera coordinates must be within 10000 metres of the car.')
        if math.dist(frame['eye'],frame['target'])<.05:raise ValueError('Camera must look at a point at least 5 cm away.')
        if not isinstance(frame['fov'],(int,float)) or not math.isfinite(frame['fov']) or not 15<=frame['fov']<=110:
            raise ValueError('Lens must be between 15 and 110 degrees.')


def sample_camera(shot,elapsed):
    camera=shot.get('camera') or default_camera(shot['kind'])
    u=max(0.,min(1.,(elapsed-shot['start'])/(shot['end']-shot['start'])))
    if camera['ease']=='smooth':u=u*u*(3-2*u)
    a,b=camera['start'],camera['end']
    result={key:[x+(y-x)*u for x,y in zip(a[key],b[key])] for key in ('eye','target')}
    result['fov']=a['fov']+(b['fov']-a['fov'])*u
    # Crossing a look-at point must not produce a singular camera matrix.
    if math.dist(result['eye'],result['target'])<.05:
        delta=[y-x for x,y in zip(a['eye'],a['target'])];length=math.sqrt(sum(v*v for v in delta))
        result['target']=[x+.05*d/length for x,d in zip(result['eye'],delta)]
    return result


def fly_pose(frame,mouse=(0,0),movement=(0,0,0),dt=0,speed=2):
    """Right/forward/up motion plus mouse rotation, independent of render FPS."""
    eye=list(frame['eye']);delta=[b-a for a,b in zip(eye,frame['target'])]
    distance=math.sqrt(sum(v*v for v in delta))
    yaw=math.atan2(delta[0],-delta[2])+math.radians(mouse[0]*.16)
    pitch=max(math.radians(-87),min(math.radians(87),math.asin(delta[1]/distance)-math.radians(mouse[1]*.16)))
    forward=(math.sin(yaw)*math.cos(pitch),math.sin(pitch),-math.cos(yaw)*math.cos(pitch))
    right=(math.cos(yaw),0,math.sin(yaw))
    x,z,y=movement;length=max(1,math.sqrt(x*x+y*y+z*z));step=max(0,min(.1,dt))*speed/length
    eye=[v+step*(right[i]*x+forward[i]*z+(y if i==1 else 0)) for i,v in enumerate(eye)]
    return pose(eye,[v+distance*forward[i] for i,v in enumerate(eye)],frame['fov'])


def orbit_pose(frame,mouse=(0,0),pan=False):
    eye,target=frame['eye'],frame['target'];delta=[a-b for a,b in zip(eye,target)]
    distance=math.sqrt(sum(v*v for v in delta));yaw=math.atan2(delta[0],delta[2]);pitch=math.asin(delta[1]/distance)
    if pan:
        right=(math.cos(yaw),0,-math.sin(yaw));up=(-math.sin(yaw)*math.sin(pitch),math.cos(pitch),-math.cos(yaw)*math.sin(pitch))
        shift=[(-right[i]*mouse[0]+up[i]*mouse[1])*distance*.002 for i in range(3)]
        return pose([eye[i]+shift[i] for i in range(3)],[target[i]+shift[i] for i in range(3)],frame['fov'])
    yaw-=math.radians(mouse[0]*.22);pitch=max(math.radians(-87),min(math.radians(87),pitch+math.radians(mouse[1]*.22)))
    eye=[target[0]+distance*math.sin(yaw)*math.cos(pitch),target[1]+distance*math.sin(pitch),target[2]+distance*math.cos(yaw)*math.cos(pitch)]
    return pose(eye,target,frame['fov'])
