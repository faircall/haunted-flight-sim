"""Cloned lake approach and the same tank-control explorer for the Void Canals."""
import math
import random
from functools import lru_cache
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT

PLAYER_SCALE=1.73/25.65
DECK=.325
WATER=0.
PLATFORM_RADIUS=7.2
PUZZLE_RADIUS=2.25
FUTURE_RING=(18.,52.)
SPAWN=(-12.45,82.)
CONTROL=((-13.3,92),(-13.0,87),(-12.35,81),(-12,76),(-12,72),(-11,63),(-8,54),(-8,39),(-4,28),(-3,16),(0,7),(0,4))
COLUMNS=tuple((math.cos(i*math.tau/6)*4.65,math.sin(i*math.tau/6)*4.65,.19) for i in range(6))
SHORE_LAMPS=((-14.05,76.6),(-9.95,76.6))
BENCHES=((-3.65,-1.8,.32,1.1),(3.65,-1.8,.32,1.1))

def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)

def path_halfwidth(z):return 1.+.30*smooth(75,82,z)-.10*smooth(86,92,z)

def walk_height(x,z):return DECK+.065*max(0.,z-76)

def path_points():
    p=(CONTROL[0],)+CONTROL+(CONTROL[-1],);result=[]
    for i in range(1,len(p)-2):
        for j in range(20):
            t=j/20
            result.append(tuple(.5*(2*p[i][a]+(-p[i-1][a]+p[i+1][a])*t+
                (2*p[i-1][a]-5*p[i][a]+4*p[i+1][a]-p[i+2][a])*t*t+
                (-p[i-1][a]+3*p[i][a]-3*p[i+1][a]+p[i+2][a])*t**3) for a in (0,1)))
    return tuple(result)+(CONTROL[-1],)

PATH=path_points()
SEGMENTS=tuple((a,b,(b[0]-a[0])**2+(b[1]-a[1])**2) for a,b in zip(PATH,PATH[1:]))

def path_distance(x,z):
    best=1e10
    for a,b,length in SEGMENTS:
        t=max(0.,min(1.,((x-a[0])*(b[0]-a[0])+(z-a[1])*(b[1]-a[1]))/max(length,1e-8)))
        best=min(best,(x-a[0]-(b[0]-a[0])*t)**2+(z-a[1]-(b[1]-a[1])*t)**2)
    return math.sqrt(best)

def inside_platform(x,z,radius=0.):
    apothem=PLATFORM_RADIUS*math.cos(math.pi/6)-radius
    return all(x*math.cos((i+.5)*math.tau/6)+z*math.sin((i+.5)*math.tau/6)<apothem for i in range(6))

def can_walk(x,z,radius=.24):
    if not (inside_platform(x,z,radius) or path_distance(x,z)<path_halfwidth(z)-radius):return False
    for cx,cz,r in COLUMNS:
        if math.hypot(x-cx,z-cz)<r+radius:return False
    for cx,cz,rx,rz in BENCHES:
        if abs(x-cx)<rx+radius and abs(z-cz)<rz+radius:return False
    for cx,cz in SHORE_LAMPS:
        if math.hypot(x-cx,z-cz)<.27+radius:return False
    return True

def shore_radius(angle):
    d=math.atan2(math.sin(angle-math.pi/2),math.cos(angle-math.pi/2));south=math.exp(-(d/.54)**2)
    entry=math.atan2(77,-12);delta=math.atan2(math.sin(angle-entry),math.cos(angle-entry))
    return 126-51*south+(1-south)*(10*math.sin(angle*3+.2)+6*math.sin(angle*7-.6))-3*math.exp(-(delta/.14)**2)

def shore_height(x,z):
    radius=math.hypot(x,z);angle=math.atan2(z,x);d=radius-shore_radius(angle)
    h=-.28+max(0,d)*.17+max(0,d-6)*.07
    h+=max(0,min(1,d/10))*(1.8+.9*math.sin(x*.17+z*.12))
    # A shallow, elongated approach merges into the hillside; no circular pad.
    center=-12-.08*max(0.,z-76)
    clearing=math.exp(-((x-center)/6.1)**4)*smooth(71,76,z)*(1-smooth(93,102,z))
    return h*(1-clearing)+(walk_height(x,z)-.035)*clearing

LIGHTS=tuple((x,y+DECK-.65,z) for x,y,z in ((-2.30,4.0,3.75),(2.30,4.0,3.75),(0,4.15,-3.9)))+tuple((x,shore_height(x,z)+1.28,z) for x,z in SHORE_LAMPS)

@lru_cache(maxsize=1)
def trees():
    rr=random.Random(62103);result=[]
    for i in range(620):
        a=rr.random()*math.tau;r=shore_radius(a)+rr.uniform(4,48);x,z=math.cos(a)*r,math.sin(a)*r
        if z>70 and path_distance(x,z)<4.5:continue
        result.append((x,shore_height(x,z)-.05,z,rr.uniform(1.2,2.25),rr.random()*360,i%3))
    return tuple(result)

SHOTS=(
 dict(name='A pavilion in the mist',eye=(-8.2,4.0,86),target=(-11,1.9,66),fov=66),
 dict(name='Leaving the pines',eye=(-18,3.2,67),target=(-9,2.2,49),fov=69),
 dict(name='Water on every side',eye=(1,3.3,49),target=(-7,2.5,33),fov=70),
 dict(name='The long approach',eye=(-12,2.85,28),target=(0,3.8,3),fov=71),
 dict(name='Under the flying eaves',eye=(9.5,3.5,14),target=(0,3.9,.5),fov=75),
 dict(name='The empty centre',eye=(4.05,3.2,3.05),target=(-.7,1.5,-1.2),fov=78),
 dict(name='Only the path home',eye=(3.5,3.1,-3.5),target=(-1,2.1,7),fov=78),
 dict(name='The far shore fades',eye=(-11,3.2,-12),target=(0,4.4,0),fov=65),
 dict(name='Reflected in the lake',eye=(20,2.0,23),target=(0,4.,0),fov=56),
)

def camera_zone(x,z,current=0):
    if z<1.0:return 6
    if z<5.5:return 5
    if z<14:return 4
    if z<31:return 3
    if z<54:return 2
    if z<71:return 1
    return 0

class Explorer:
    def __init__(self):self.x,self.z=SPAWN;self.height=walk_height(self.x,self.z);self.yaw=0.;self.phase=0.;self.clip='idle';self.shot=0;self.encounter=None
    def tick(self,dt,forward=0.,turn=0.,run=False):
        dt=max(0.,min(.1,dt));self.yaw+=turn*dt*1.8;speed=(3.15 if run and forward>0 else 1.55)*forward
        dx=math.sin(self.yaw)*speed*dt;dz=-math.cos(self.yaw)*speed*dt;old=(self.x,self.z)
        n=max(1,math.ceil(math.hypot(dx,dz)/.045))
        for _ in range(n):
            if self.encounter is None:
                if can_walk(self.x+dx/n,self.z):self.x+=dx/n
                if can_walk(self.x,self.z+dz/n):self.z+=dz/n
            else:
                from g_huxin_canals_sequence import support
                h=support(self.x+dx/n,self.z,self.height,self.encounter.revealed)
                if h is not None:self.x+=dx/n;self.height=h
                h=support(self.x,self.z+dz/n,self.height,self.encounter.revealed)
                if h is not None:self.z+=dz/n;self.height=h
        distance=math.hypot(self.x-old[0],self.z-old[1]);self.phase+=distance/(GAIT['run' if run else 'walk']['stride']*PLAYER_SCALE)
        self.clip=('walk_back' if forward<0 else 'run' if run else 'walk') if distance>.0001 else ('turn_right' if turn>0 else 'turn_left') if turn else 'idle'
        if self.encounter is None:self.height=walk_height(self.x,self.z)
        self.shot=camera_zone(self.x,self.z,self.shot);return distance

REVIEW_ROUTE=tuple(p for p in PATH[::4] if p[1]<SPAWN[1])+((0,2),(0,0),(1.8,-1),(1.6,-3),(-1.5,-3),(-1.8,0),(0,3))
