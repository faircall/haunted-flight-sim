"""The one-time moon encounter. Metres, seconds and actual reflected-ray optics."""
import math
from g_interaction_data import SLOT_COUNT
from g_huxin_moon import DECK, can_walk, walk_height, COLUMNS, BENCHES, smooth, shore_radius, PATH

ENTRY_SWAP=8.
ENTRY_CLEAR=10.
ENTRY_DURATION=24.
RETURN_SWAP=.50
RETURN_CLEAR=.50
FOG_STOP_RADIUS=4.65 # At the six original columns; the centre stays open.

def ease(a,b,x):
    """Quintic easing: velocity and acceleration meet without a visible corner."""
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*t*(t*(t*6.-15.)+10.)

_PATH_STATIONS=[0.]
for a,b in zip(PATH,PATH[1:]):_PATH_STATIONS.append(_PATH_STATIONS[-1]+math.dist(a,b))

def _station(x,z):
    best=(math.inf,0.)
    for i,(a,b) in enumerate(zip(PATH,PATH[1:])):
        dx,dz=b[0]-a[0],b[1]-a[1];length=dx*dx+dz*dz
        t=max(0.,min(1.,((x-a[0])*dx+(z-a[1])*dz)/max(1e-8,length)))
        d=(x-a[0]-dx*t)**2+(z-a[1]-dz*t)**2
        if d<best[0]:best=(d,_PATH_STATIONS[i]+math.sqrt(length)*t)
    return best[1]

_SHORE_STATION=_station(-12.,76.)
_PAVILION_STATION=_station(0.,7.)
CAUSEWAY_LENGTH=_PAVILION_STATION-_SHORE_STATION

def causeway_progress(x,z):
    """Position on the path, not distance walked: backtracking unwinds the mist."""
    return max(0.,min(1.,(_station(x,z)-_SHORE_STATION)/CAUSEWAY_LENGTH))

def causeway_point(progress):
    s=_SHORE_STATION+max(0.,min(1.,progress))*CAUSEWAY_LENGTH
    for i,(a,b) in enumerate(zip(PATH,PATH[1:])):
        if _PATH_STATIONS[i+1]>=s:
            t=(s-_PATH_STATIONS[i])/(_PATH_STATIONS[i+1]-_PATH_STATIONS[i])
            return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
    return PATH[-1]

UPPER=DECK+3.80
BASIN=(0.,DECK+.82,0.)
MIRROR=(1.35,DECK+1.55,-.15)
MARK=(-.22,BASIN[1],.18)
def unit(v):
    length=math.sqrt(sum(x*x for x in v));return tuple(x/length for x in v)
MOON=unit((.62,.25,-.74))
outgoing=unit(tuple(MARK[i]-MIRROR[i] for i in range(3)))
NORMAL=unit(tuple(MOON[i]+outgoing[i] for i in range(3)))
SOLUTION=(math.atan2(NORMAL[0],NORMAL[2]),math.asin(NORMAL[1]))
TEA_LIGHTS=((-3,DECK+2.9,2.8),(3,DECK+2.9,2.8),(0,DECK+2.95,-3.7),
            (9.65,DECK+2.55,0),(-2,UPPER+2.35,-3.7),(3.8,UPPER+2.45,2.5),
            (4.8,UPPER+2.25,-3.8),(-4.7,UPPER+2.8,5.8),(4.7,UPPER+2.8,5.8))
# Solid walls are shared by authoring, navigation and camera checks. Doorways
# are actual gaps. The upper floor has a real stairwell, not a teleport zone.
GROUND_WALLS=((-7,-6,7,-5.8),(-7,-6,-6.8,6.2),(6.8,-6,7,-1.2),(6.8,1.2,7,6.2),
              (-7,6, -1.25,6.2),(1.25,6,7,6.2),
              (7,-3.3,12.4,-3.1),(7,3.1,12.4,3.3),(12.2,-3.3,12.4,3.3))
UPPER_WALLS=((-7,-6,7,-5.8),(-7,-6,-6.8,6.2),(6.8,-6,7,6.2),
             (-7,6,-1.25,6.2),(1.25,6,7,6.2),
             (2.2,-6,2.4,-1.8),(2.2,-2,3.1,-1.8),(4.5,-2,7,-1.8),
             (-7,8.1,7,8.3),(-7,6,-6.8,8.3),(6.8,6,7,8.3),
             (-4.6,-4.2,-4.4,4.8),(-6.8,4.65,-4.4,4.85))
GROUND_PROPS=((9.7,-.1,1.05,.64),(9.7,1.25,.40,.38),(9.7,-1.45,.40,.38),
              (11.25,-.1,.38,.4),(-1.6,-4.65,1.2,.35))
UPPER_PROPS=((5.3,-4.6,.85,.42),(5.3,-3.45,.36,.36),(-1.9,-4.8,1.1,.32),
             (4.,3.5,.65,.65),(3.,3.5,.32,.32),(5.,3.5,.32,.32))
STAIR=(-6.65,-4.65,-4.45,4.55) # xmin,xmax,top z,bottom z
STAIR_COUNT=22

def rect_hit(x,z,rect,r):
    a,b,c,d=rect;return a-r<x<c+r and b-r<z<d+r

def furniture_hit(x,z,props,r):
    return any(abs(x-a)<rx+r and abs(z-b)<rz+r for a,b,rx,rz in props)

def support(x,z,previous,revealed,r=.24):
    if not revealed:
        if not can_walk(x,z,r):return None
        if math.hypot(x,z)<.88+r or math.hypot(x-MIRROR[0],z-MIRROR[2])<.22+r:return None
        return walk_height(x,z)
    upper=previous>UPPER-.23
    # The whole stair is climbable from either landing, but only within one riser.
    if STAIR[0]+r<x<STAIR[1]-r and STAIR[2]-.2<z<STAIR[3]+.25:
        f=max(0.,min(1.,(STAIR[3]-z)/(STAIR[3]-STAIR[2])))
        h=DECK+min(STAIR_COUNT,math.ceil(f*STAIR_COUNT))*3.8/STAIR_COUNT
        if abs(h-previous)<.24:return h
    walls=UPPER_WALLS if upper else GROUND_WALLS
    if any(rect_hit(x,z,q,r) for q in walls):return None
    if upper:
        if not (-7+r<x<7-r and -6+r<z<8.3-r):return None
        if -6.85-r<x<-4.4+r and -4.45<z<4.85+r:return None
        if furniture_hit(x,z,UPPER_PROPS,r):return None
        return UPPER
    # No access underneath the stair flight.
    if -6.85-r<x<-4.4+r and -4.65-r<z<4.55:return None
    inside=(-7+r<x<7-r and -6+r<z<6.2) or (6.6<x<12.4-r and -3.3+r<z<3.3-r)
    if not inside and not can_walk(x,z,r):return None
    if math.hypot(x,z)<.88+r or math.hypot(x-MIRROR[0],z-MIRROR[2])<.22+r:return None
    if any(math.hypot(x-a,z-b)<rad+r for a,b,rad in COLUMNS):return None
    if furniture_hit(x,z,BENCHES+GROUND_PROPS,r):return None
    return walk_height(x,z)

class MoonSequence:
    def __init__(self):
        self.state='ordinary';self.revealed=False;self.elapsed=0.;self.focus=False
        self.yaw=SOLUTION[0]+.075;self.pitch=SOLUTION[1]+.045
        self.held=0.;self.events=[];self.inventory=[None]*SLOT_COUNT;self.bells=0;self.swaps=[]
        self.locked_camera=None;self.locked_pose=None
        self.approach=0.;self.return_progress=0.
        self.entry_veil=.72;self.entry_arrival=.93
    @property
    def transitioning(self):return self.state in ('entering','leaving')
    @property
    def veil(self):
        if self.state=='ordinary':return .72*ease(0.,1.,self.approach)
        if self.state=='entering':return (self.entry_veil+(1.-self.entry_veil)*ease(0.,6.,self.elapsed))*(1.-self.fog_clear)
        if self.state=='leaving':return ease(0.,RETURN_SWAP,self.return_progress)*(1.-self.fog_clear)
        return 0.
    @property
    def fog_arrival(self):
        if self.state=='ordinary':return .93*ease(0.,1.,self.approach)
        if self.state=='entering':return self.entry_arrival+(1.-self.entry_arrival)*ease(0.,6.,self.elapsed)
        if self.state=='leaving':return ease(0.,RETURN_SWAP,self.return_progress)
        return 0.
    @property
    def fog_clear(self):
        if self.state=='entering':return ease(ENTRY_CLEAR,ENTRY_DURATION,self.elapsed)
        if self.state=='leaving':return ease(RETURN_CLEAR,1.,self.return_progress)
        return 0.
    def fog_front(self,x,z):
        shore=shore_radius(math.atan2(z,x))-6.
        return shore+(FOG_STOP_RADIUS-shore)*self.fog_arrival
    @property
    def movement_locked(self):
        return self.state=='entering'
    @property
    def swap_time(self):
        return ENTRY_SWAP if self.state=='entering' else math.inf
    @property
    def duration(self):
        return ENTRY_DURATION if self.state=='entering' else math.inf
    @property
    def camera_stage(self):
        if self.state=='entering':
            return 'basin'
        if self.state=='leaving':return 'walking'
        return None
    @property
    def warmth(self):
        if self.state=='entering':return ease(ENTRY_SWAP,ENTRY_DURATION-2.,self.elapsed)
        if self.state=='leaving':return 1.-ease(RETURN_SWAP,.94,self.return_progress)
        return float(self.revealed)
    @property
    def normal(self):return (math.sin(self.yaw)*math.cos(self.pitch),math.sin(self.pitch),math.cos(self.yaw)*math.cos(self.pitch))
    def hit(self):
        n=self.normal;dot=sum(MOON[i]*n[i] for i in range(3));ray=tuple(-MOON[i]+2*dot*n[i] for i in range(3))
        if ray[1]>=-.0001:return None
        t=(BASIN[1]-MIRROR[1])/ray[1]
        p=tuple(MIRROR[i]+t*ray[i] for i in range(3))
        return p if t>0 and math.hypot(p[0],p[2])<.69 else None
    def adjust(self,dt,horizontal,vertical):
        if self.focus and self.state=='ordinary':
            self.yaw=max(SOLUTION[0]-.22,min(SOLUTION[0]+.22,self.yaw+horizontal*dt*.085))
            self.pitch=max(SOLUTION[1]-.18,min(SOLUTION[1]+.18,self.pitch+vertical*dt*.085))
    def tick(self,dt,explorer):
        self.approach=causeway_progress(explorer.x,explorer.z)
        self.return_progress=1.-self.approach
        if self.state=='ordinary' and self.focus:
            hit=self.hit();aligned=hit is not None and math.dist(hit,MARK)<.065
            self.held=self.held+dt if aligned else 0.
            if self.held>=1.1:
                self.entry_veil=self.veil;self.entry_arrival=self.fog_arrival
                self.state='entering';self.elapsed=0.;self.focus=False;self.events.append('bell');self.bells+=1
        elif self.state=='revealed' and self.return_progress>.025 and explorer.height<1:
            self.state='leaving';self.elapsed=0.;self.locked_camera=None;self.locked_pose=None
        elif self.state=='ordinary':self.held=0.
        if self.state=='entering':
            self.elapsed+=dt
            if self.elapsed>=ENTRY_SWAP and not self.revealed:
                self.revealed=True;self.swaps.append(('entering',self.veil));self.events.append('timber')
            if self.elapsed>=ENTRY_DURATION:self.state='revealed';self.elapsed=0.
        elif self.state=='leaving':
            self.elapsed+=dt
            safe=explorer.height<1 and support(explorer.x,explorer.z,explorer.height,False) is not None
            if self.return_progress>=RETURN_SWAP and self.revealed and safe:
                self.revealed=False;self.swaps.append(('leaving',self.veil));self.events.append('timber')
            # No timers drive departure: stopping, turning or running retain
            # movement and animation, and fog is normal again at either endpoint.
            if self.return_progress>=.999 or self.return_progress<=.01:
                self.state='revealed' if self.revealed else 'returned';self.elapsed=0.
                self.locked_camera=None;self.locked_pose=None
    def prompt(self,e):
        if self.transitioning:return ''
        if self.focus:return 'Arrow keys: turn / tilt the bronze mirror     E: step away'
        if self.state=='ordinary' and math.hypot(e.x-MIRROR[0],e.z-MIRROR[2])<2.1:return 'E  Examine the bronze mirror'
        if self.revealed and e.height>UPPER-.2 and math.hypot(e.x-5.3,e.z+4.6)<2:return 'An empty tray, carefully set beside the window.'
        if self.revealed and e.x>8:return 'Three cups. The chairs are empty.'
        return ''
