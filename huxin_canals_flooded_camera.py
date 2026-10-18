"""Interior camera stations, kept in the room occupied by the player."""
from g_huxin_canals_flooded_sequence import UPPER,ease
from temple_interior_viewer import camera
import math
import pyray as pr
from g_huxin_canals_flooded_layout import CAMERA_SHOTS,HOUSE_SPECS,in_house,local_point,transform,DECK


def canal_camera(e):
    """Fixed domestic-scale stations, with real walls between camera and player."""
    if e.z<=5.3:
        from huxin_canals_flooded_viewer import auto_camera,clear_view
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
        from huxin_canals_flooded_viewer import auto_camera
        q.locked_shot,q.locked_camera=auto_camera(e)
    return q.locked_shot,q.locked_camera
