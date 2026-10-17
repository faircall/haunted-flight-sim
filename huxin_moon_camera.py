"""Interior camera stations, kept in the room occupied by the player."""
from g_huxin_moon_sequence import UPPER,ease
from temple_interior_viewer import camera

FOCUS_EYE=(2.85,3.60,2.4)
FOCUS_TARGET=(.35,1.16,-.05)

def mist_camera(q,e):
    """Frame the basin crescendo. Departure keeps the ordinary gameplay cameras."""
    stage=q.camera_stage
    if stage=='basin':
        if q.elapsed<4.:return 22,camera(FOCUS_EYE,FOCUS_TARGET,57)
        # Look back toward the causeway, leaving the new stair behind the lens.
        # The shared basin, posts and player remain in the clear central space.
        close=ease(4,6,q.elapsed)*(1.-ease(12,24,q.elapsed))
        # Keep the new hanging lantern and its cage above the frame at the swap.
        # The later pullback can then reveal them naturally with the room.
        return 22,camera((-2.6,3.6,-2.8),(.7,.9-.35*close,1.3),57.-close*12.)
    raise ValueError(stage)

TEA_SHOTS=(
    dict(name='The room within the pavilion',eye=(5.9,3.35,5.35),target=(0,1.5,0),fov=73),
    dict(name='Three empty chairs',eye=(11.7,3.15,2.65),target=(9.5,1.1,-.3),fov=74),
    dict(name='The timber stair',eye=(-5.65,7.1,-5.4),target=(-5.65,2.8,1.8),fov=72),
    dict(name='Upper gallery',eye=(-3.85,6.95,5.4),target=(1.2,5.2,-1.5),fov=76),
    dict(name='The empty tray',eye=(6.35,6.65,-2.55),target=(4.7,5.1,-4.5),fov=80),
    dict(name='Water beyond the balcony',eye=(5.9,6.5,7.7),target=(0,5.1,7.3),fov=75),
    dict(name='A house upon the water',eye=(25,10,28),target=(1,5,0),fov=60),
    dict(name='The narrow landing',eye=(-3.1,6.85,-5.25),target=(-5.4,5.1,-4.7),fov=75),
    dict(name='The other side of the hall',eye=(-3.95,3.45,-4.7),target=(.8,1.5,1),fov=76),
    dict(name='The open doorway',eye=(.15,3.30,4.4),target=(0,1.2,7),fov=76),
    dict(name='The eastern gallery',eye=(6.25,6.9,5.2),target=(3,5.1,1),fov=76),
)

def interior_camera(e):
    if e.height>UPPER-.23:
        if e.x<-4.1 and e.z<-4.3:i=7
        elif e.z>6.3:i=5
        elif e.x>2.45 and e.z<-2.05:i=4
        elif e.x>4.8 and e.z>2:i=10
        else:i=3
    elif e.x<-4.6:i=8 if e.z<-4.7 and e.height<.45 else 2
    elif e.x>6.7:i=1
    elif e.z>5.1:i=9
    elif e.z<-1.0:i=8
    else:i=0
    s=TEA_SHOTS[i];body=(e.x,e.height+.92,e.z)
    return i,camera(s['eye'],body,s['fov'])
