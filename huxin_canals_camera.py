"""Interior camera stations, kept in the room occupied by the player."""
from g_huxin_canals_sequence import UPPER,ease
from temple_interior_viewer import camera
import math
from functools import lru_cache
import pyray as pr
from canals_house_plan import house_ground_plan
from g_huxin_canals_layout import CAMERA_SHOTS,HOUSE_SPECS,in_house,local_point,transform,DECK,WASHING_STAIRS,step_local,step_point,step_height,landing_rect,floor_polygons,point_in_poly
_HOUSE_PLANS={s['seed']:house_ground_plan(s) for s in HOUSE_SPECS}


def _house_clear(eye,target):
    """Ground-storey sight lines use the same real apertures as navigation.

    Cameras inside an empty room are valid; crossing one of its opaque wall
    planes is not. This is deliberately separate from the street-camera box
    approximation, which cannot express a rear doorway.
    """
    for spec in HOUSE_SPECS:
        ax,az=local_point(spec,eye[0],eye[2]);bx,bz=local_point(spec,target[0],target[2])
        plan=_HOUSE_PLANS[spec['seed']];w=spec['width']/2;back=spec['depth']/2
        front=plan['front'];wall=plan['frontwall'];dy=target[1]-eye[1]
        ceiling=DECK+spec['height']/spec['floors']-.13
        if -w+.13<ax<w-.13 and wall+.18<az<back-.18 and eye[1]>ceiling:return False
        for axis,value,lo,hi,kind in ((0,-w,front,back,'side'),(0,w,front,back,'side'),
                                      (1,back,-w,w,'rear'),(1,wall,-w,w,'front')):
            a,b=(ax,bx) if axis==0 else (az,bz)
            if abs(b-a)<1e-8:continue
            t=(value-a)/(b-a)
            if not .001<t<.999:continue
            across=az+(bz-az)*t if axis==0 else ax+(bx-ax)*t
            yy=eye[1]+dy*t
            if not lo-.05<across<hi+.05 or not DECK-.03<yy<ceiling+.12:continue
            doors=plan['door_ranges'] if kind=='front' else plan['rear_door_ranges'] if kind=='rear' else ()
            if DECK+.04<yy<min(ceiling-.06,DECK+2.33) and any(a+.10<across<b-.10 for a,b in doors):continue
            return False
    return True


def _bank_clear(eye,target):
    # Lower stair cameras must see the actor across open water, rather than
    # looking down through the solid volume under a quay or its upper paving.
    if min(eye[1],target[1])>=DECK-.025:return True
    for i in range(1,28):
        t=i/28.;x,y,z=(eye[k]+(target[k]-eye[k])*t for k in range(3))
        if y<DECK-.025 and any(point_in_poly(p,x,z) for p in floor_polygons()):return False
    return True


def _body_clear(eye,x,y,z):
    return sum(_house_clear(eye,(x,y+h,z)) and _bank_clear(eye,(x,y+h,z)) for h in (.30,.95,1.60))


@lru_cache(maxsize=None)
def _rear_stair_station(index):
    stairs=WASHING_STAIRS[index];length=stairs['tread']*10
    candidates=[]
    for along in (length*.62,length+.9,-.50):
        for side in (1.7,-1.7,2.6,-2.6):
            x,z=step_point(stairs,along,side);eye=(x,DECK+1.75,z)
            # Keep candidate eyes out of the opaque part of every home.
            if any(in_house(h,x,z,.12) for h in HOUSE_SPECS):continue
            score=0
            for t in (.12,.80,1.60,min(2.65,length-.12)):
                xx,zz=step_point(stairs,t);score+=_body_clear(eye,xx,step_height(stairs,t),zz)
            ta,tb,ua,ub=landing_rect(stairs);xx,zz=step_point(stairs,(ta+tb)/2,(ua+ub)/2)
            score+=_body_clear(eye,xx,step_height(stairs,stairs['tread']*9+.01),zz)
            if score==15:return eye
            candidates.append((-score,abs(side-1.7)*.04+abs(along-length*.62)*.05,eye))
    if candidates:return min(candidates)[2]
    x,z=step_point(stairs,length+.9,1.7);return(x,DECK+1.75,z)


def _rear_door_camera(spec,index,body):
    plan=_HOUSE_PLANS[spec['seed']];lo,hi=plan['rear_door_ranges'][0];center=(lo+hi)/2
    # This camera looks straight through the full rear aperture during the
    # crossing, before the door jamb can hide the player's shoulders or feet.
    choices=[]
    for distance in (2.25,1.75,1.30):
        x,z=transform(spec,center,plan['rearwall']+distance);eye=(x,DECK+1.95,z)
        if any(in_house(h,x,z,.10) for h in HOUSE_SPECS):continue
        choices.append((-_body_clear(eye,body[0],body[1]-.92,body[2]),-distance,eye))
    if choices:eye=min(choices)[2]
    else:
        x,z=transform(spec,center,plan['rearwall']+1.30);eye=(x,DECK+1.95,z)
    return 160+index,camera(eye,body,78)


def canal_camera(e):
    """Fixed domestic-scale stations, with real walls between camera and player."""
    if e.z<=5.3:
        from huxin_canals_viewer import auto_camera,clear_view
        shot,view=auto_camera(e)
        if shot in (5,6):return shot,view
        # The former lake-shore fallback cameras now sit inside houses. Keep
        # fallback positions in the unchanged pavilion's clear central space.
        body=(e.x,e.height+.92,e.z)
        stations=((4.05,3.2,3.05),(3.5,3.1,-3.5),(-3.5,3.2,3.2),(-3.4,3.2,-3.4))
        eligible=[(abs(math.dist(eye,body)-6.),i,eye) for i,eye in enumerate(stations)
                  if math.dist(eye,body)>2.3 and clear_view(eye,body)]
        _,i,eye=min(eligible or [(0.,0,stations[0])])
        return 25+i,camera(eye,body,76)
    if e.z<=12.:
        # The old approach camera at (9.5,3.5,14) now occupies a real house.
        # This water-side station keeps the unchanged pavilion and its short
        # causeway visible without seeing through that new home's walls.
        return 29,camera((4.8,3.4,10.5),(e.x,e.height+.9,e.z),74)
    body=(e.x,e.height+.92,e.z)
    for house_index,spec in enumerate(HOUSE_SPECS):
        if not spec.get('enterable') or not spec.get('rear_access'):continue
        u,v=local_point(spec,e.x,e.z);plan=_HOUSE_PLANS[spec['seed']];back=plan['rearwall']
        if abs(u)>spec['width']/2-.22:continue
        if back-1.45<v<back-.55 and in_house(spec,e.x,e.z):
            # Looking towards the rear from within the room avoids the former
            # camera being trapped between the actor, back wall and ceiling.
            x,z=transform(spec,-spec['width']/2+.65,plan['frontwall']+.65)
            eye=(x,DECK+min(2.05,spec['height']/spec['floors']-.45),z)
            return 140+house_index,camera(eye,body,75)
        if back-.55<=v<back+.50 and any(a-.24<u<b+.24 for a,b in plan['rear_door_ranges']):
            return _rear_door_camera(spec,house_index,body)
    # A high street camera can look through the quay to a person standing on
    # the low washing ledge. Use fixed stations over the open channel, looking
    # back across the stair flight and the exposed masonry behind the actor.
    for index,stairs in enumerate(WASHING_STAIRS):
        if not stairs['walkable']:continue
        t,u=step_local(stairs,e.x,e.z)
        if stairs.get('side')=='rear':
            half=stairs['width']/2;ta,tb,ua,ub=landing_rect(stairs)
            on_flight=-.25<t<stairs['tread']*11+.10 and abs(u)<half+.12
            on_low_ledge=ta-.12<t<tb+.12 and ua-.12<u<ub+.12 and e.height<DECK-.50
            # A broad rectangular trigger used to catch the upper landing
            # beside a parallel flight, cutting away and back during its turn.
            if on_flight or on_low_ledge:return 100+index,camera(_rear_stair_station(index),body,72)
        elif -.32<t<3.8 and -stairs['width']/2-.12<u<stairs['width']/2+1.14:
            water_side=-3.4 if stairs['top'][0]<1. else 3.4
            x,z=step_point(stairs,3.8,water_side)
            return 100+index,camera((x,1.60,z),body,66)
    rear_candidates=[]
    for house_index,spec in enumerate(HOUSE_SPECS):
        if not spec.get('enterable') or not spec.get('rear_access'):continue
        u,v=local_point(spec,e.x,e.z);back=spec['depth']/2
        if abs(u)<spec['width']/2+.65 and back+.10<v<back+2.15:
            rear_candidates.append((abs(u)+abs(v-back-.65),house_index,spec))
    if rear_candidates:
        _,house_index,spec=min(rear_candidates,key=lambda row:row[:2])
        shot,view=_rear_door_camera(spec,house_index,body)
        return 200+house_index,view
    # Enterable shops have a fixed camera within their actual empty ground room.
    # It looks out through the open door; there is no view through opaque walls.
    for house_index,spec in enumerate(HOUSE_SPECS):
        if not spec.get('enterable') or not in_house(spec,e.x,e.z):continue
        u,v=local_point(spec,e.x,e.z)
        if v>-spec['depth']/2+spec['porch']-.45:
            x,z=transform(spec,spec['width']/2-.65,spec['depth']/2-.65)
            return 60+house_index,camera((x,DECK+2.1,z),body,73)
        x,z=transform(spec,-.60,-spec['depth']/2-2.4)
        return 80+house_index,camera((x,DECK+1.9,z),body,72)
    if e.z>54.:
        # The final doorways and broken quay ends lie well beyond the old
        # bridge camera. Keep the actor readable instead of a tiny silhouette
        # seventeen metres away, with the unreachable continuation behind.
        left=e.x<1.
        eye=(2.4,3.25,61.2) if left else (.5,3.2,55.)
        return 120 if left else 121,camera(eye,body,70)
    candidates=[]
    for i,s in enumerate(CAMERA_SHOTS):
        eye=s['eye'];distance=math.dist(eye,body)
        if distance<2.2 or distance>30.:continue
        blocked=False
        for sample in range(50):
            t=sample/50.;x,y,z=(eye[k]+(body[k]-eye[k])*t for k in range(3))
            for h in HOUSE_SPECS:
                # Open front porches do not act as solid facade planes.
                if h.get('enterable') and in_house(h,e.x,e.z):continue
                if in_house(h,x,z,.12) and .1<y<DECK+h['height']+1.55:
                    blocked=True;break
            if blocked:break
        if blocked:continue
        a,b,c,d=s['zone'];inside=a<=e.x<=c and b<=e.z<=d
        score=(0 if inside else 24)+abs(distance-7.5)*.11
        if getattr(e,'_canal_camera',None)==i:score-=.28
        candidates.append((score,i))
    i=min(candidates)[1] if candidates else min(range(len(CAMERA_SHOTS)),key=lambda j:math.dist(CAMERA_SHOTS[j]['eye'],body))
    e._canal_camera=i;s=CAMERA_SHOTS[i]
    eye=pr.Vector3(*s['eye']);target=pr.Vector3(*s['target'])
    forward=pr.vector3_normalize(pr.vector3_subtract(target,eye));right=pr.vector3_normalize(pr.vector3_cross_product(forward,pr.Vector3(0,1,0)));up=pr.vector3_cross_product(right,forward)
    delta=pr.vector3_subtract(pr.Vector3(*body),eye);depth=pr.vector3_dot_product(delta,forward);tan=math.tan(math.radians(s['fov'])/2)
    visible=depth>1 and abs(pr.vector3_dot_product(delta,right))<depth*tan*16/9*.80 and abs(pr.vector3_dot_product(delta,up))+.9<depth*tan*.82
    return 30+i,camera(s['eye'],s['target'] if visible else body,s['fov'])

FOCUS_EYE=(2.85,3.60,2.4)
FOCUS_TARGET=(.35,1.16,-.05)

def mist_camera(q,e):
    """The previously rendered view is held for the entire continuous reveal."""
    if q.locked_camera is None:
        # Headless callers can select an ordinary lake camera without taking
        # ownership of the interactive viewer's current/manual camera.
        from huxin_canals_viewer import auto_camera
        q.locked_shot,q.locked_camera=auto_camera(e)
    return q.locked_shot,q.locked_camera
