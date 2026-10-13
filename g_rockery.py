"""The independent Hollow Garden: shared walk surfaces, routes and encounter notes."""
import math
import random
from functools import lru_cache
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT

PLAYER_SCALE=1.73/25.65
SPAWN=(0.,26.)
# X, height, Z. Elevated routes genuinely cross above the grotto passages.
NODES={
 'gate':(0,.08,26),'mouth':(0,.08,20),'throat':(-3.8,.08,16),'fork':(-3.8,.08,10),
 'reveal':(0,.08,3),'west':(-10,.08,9),'fern':(-13,.08,3),'blind':(-11,.08,-4),
 'turn':(-6,.08,-2),'grotto':(-8,.08,-11),'north':(-2,.08,-14),'court':(0,.08,-22),
 'east':(9,.08,1),'east_bend':(13,.08,-5),'riddle':(7,.08,-10),
 'window':(-.5,.08,-8),'window_turn':(-1,.08,-4),
 'stair_east':(15,1.68,1),'high_east':(10,3.28,7),'bridge_east':(5,3.28,8),
 'bridge_mid':(0,3.28,9),'bridge_west':(-6,3.28,8),'stair_west':(-15,1.68,7),
}
# Radius, roofed passage. Widths include some clearance beyond the collision body.
EDGES=(
 ('gate','mouth',.92,True),('mouth','throat',.79,True),('throat','fork',.82,True),
 ('fork','reveal',1.03,False),('fork','west',.92,True),('west','fern',.85,False),
 ('fern','blind',.88,True),('blind','turn',.84,True),('turn','reveal',.88,False),
 ('blind','grotto',.95,True),('grotto','north',.86,True),('north','court',1.0,True),
 ('reveal','east',.98,False),('east','east_bend',.93,True),('east_bend','riddle',.85,True),
 ('riddle','north',.90,False),('reveal','window_turn',.78,True),('window_turn','window',.74,True),
 ('east_bend','stair_east',.91,False),('stair_east','high_east',.91,False),
 ('high_east','bridge_east',.92,False),('bridge_east','bridge_mid',.92,False),
 ('bridge_mid','bridge_west',.92,False),('bridge_west','stair_west',.91,False),('stair_west','fern',.91,False),
)
UPPER_ROUTE=('east_bend','stair_east','high_east','bridge_east','bridge_mid','bridge_west','stair_west','fern')
ROOMS=(('entrance',0,26,3.5,3.8,.08,False),('echo',0,3,5.2,4.4,.08,False),
       ('blind_grotto',-8,-11,3.1,2.65,.08,True),('open_court',0,-22,6.3,4.9,.08,False))
POND=(-3.65,-22,1.75,2.65)
PAVILION=(1.6,-23.2,2.75)
OBSTACLES=((2.2,3.,.77,0),)+tuple((PAVILION[0]+math.cos(i*math.tau/6)*PAVILION[2],PAVILION[1]+math.sin(i*math.tau/6)*PAVILION[2],.14,0) for i in range(6))
LIGHTS=((1.15,1.9,23),(-4.65,1.75,13.6),(-3.6,2.1,3.4),(-8.8,1.9,-10.8),(10.8,1.9,-5.8),(1.4,2.8,-22.7))
OBSTACLES=OBSTACLES+tuple((x,z,.23,0) for x,y,z in LIGHTS)

ENCOUNTERS=(
 dict(id='echo_court',name='Echo court',center=(-.8,.08,3),radius=2.5,spawns=[(-2,.08,4),(1,.08,0)],
      exits=['fork','turn','east','window_turn'],notes='Four exits; perforated central stone breaks sightlines. Open maneuvering before the next constriction.'),
 dict(id='blind_grotto',name='Blind grotto',center=(-8,.08,-11),radius=1.9,spawns=[(-9.3,.08,-11.5),(-7.4,.08,-12)],
      exits=['blind','north'],notes='Lower roof and two retreat routes; concealed approach around the west bend.'),
 dict(id='last_court',name='Open court',center=(1.7,.08,-21.4),radius=2.0,spawns=[(2,.08,-21),(3,.08,-23)],
      exits=['north'],notes='Wider confrontation space; pond constrains the left flank, pavilion columns provide partial cover.'),
 dict(id='throat',name='Single-file throat',center=(-3.8,.08,13.5),radius=.46,spawns=[(-3.8,.08,13.5)],
      exits=['throat','fork'],notes='About 1.6 m wide. Deliberate retreat pressure; no enemy is activated in this prototype.'),
)

SHOTS=(
 dict(name='The stone threshold',eye=(2.6,2.9,28.8),target=(0,1.55,21),fov=66),
 dict(name='Only room for one',eye=(-3.8,2.1,17.5),target=(-3.8,1.3,12.0),fov=76),
 dict(name='The blind fork',eye=(-3.8,2.8,12.1),target=(-3.7,1.3,7.0),fov=76),
 dict(name='A court within the stone',eye=(-3.0,3.0,5.6),target=(1.3,1.4,1.5),fov=75),
 dict(name='The fern passage',eye=(-12.1,2.25,5.0),target=(-13.0,1.25,1.3),fov=73),
 dict(name='The listening grotto',eye=(-9.7,2.30,-9.5),target=(-6.9,1.35,-12.1),fov=77),
 dict(name='Another way around',eye=(13.1,2.35,-4.4),target=(7.6,1.35,-9.6),fov=76),
 dict(name='Across the hollow',eye=(10.8,5.6,7.1),target=(-2,3.9,8.8),fov=75),
 dict(name='Suddenly the sky',eye=(-1.25,2.5,-17.4),target=(.5,1.7,-23),fov=75),
 dict(name='Eastern stair',eye=(14.5,5.8,1.2),target=(13.8,1.3,-2.1),fov=76),
 dict(name='Western descent',eye=(-15.2,4.5,7.4),target=(-13.0,1.1,3.0),fov=76),
 dict(name='The northern fissure',eye=(4.0,2.6,-11.3),target=(-1,1.4,-14.0),fov=77),
 dict(name='The stone eye',eye=(-.75,2.2,-5.5),target=(-.5,1.4,-8.5),fov=76),
 dict(name='Bending inward',eye=(0,2.2,21.2),target=(-3.8,1.4,16),fov=78),
 dict(name='The western fork',eye=(-4.1,2.4,10),target=(-10,1.3,9),fov=78),
 dict(name='The shaded return',eye=(-13,2.2,3.5),target=(-11,1.4,-3.8),fov=78),
 dict(name='The hidden return',eye=(-6.8,2.5,-2.7),target=(-.5,1.4,2.5),fov=78),
 dict(name='The low approach',eye=(-11,2.2,-4.8),target=(-8,1.3,-11),fov=78),
 dict(name='The eastern slot',eye=(8.7,2.3,1.8),target=(13,1.4,-5),fov=78),
 dict(name='The riddle turn',eye=(7.6,2.2,-9.1),target=(-2,1.4,-14),fov=78),
 dict(name='Last narrow opening',eye=(-2.4,2.15,-13.4),target=(0,1.3,-21.5),fov=78),
 dict(name='Climbing to daylight',eye=(10.2,5.7,7.4),target=(14.6,1.4,.8),fov=78),
 dict(name='The western landing',eye=(-5.7,5.6,8.3),target=(-14.5,2.6,7),fov=78),
)

def segment_position(x,z,a,b):
    dx,dz=b[0]-a[0],b[2]-a[2];length=dx*dx+dz*dz
    t=max(0.,min(1.,((x-a[0])*dx+(z-a[2])*dz)/max(length,1e-9)))
    return math.hypot(x-a[0]-dx*t,z-a[2]-dz*t),t

def stair_limits(a,b):
    """One metre flat landings keep the junction disks clear of the risers."""
    pad=min(.35,1.0/math.hypot(b[0]-a[0],b[2]-a[2]))
    return pad,1-pad

@lru_cache(maxsize=None)
def stair_profile(a,b):
    """Varied hand-cut rises and runs, shared by collision and exported geometry."""
    if a[1]>b[1]:
        breaks,heights=stair_profile(b,a)
        return tuple(1-t for t in breaks[::-1]),heights[::-1]
    n=round((b[1]-a[1])/.16);lo,hi=stair_limits(a,b)
    rr=random.Random(round(a[0]*713+a[2]*431+b[0]*197+b[2]*83))
    breaks=(0.,)+tuple(lo+(j+.5+rr.uniform(-.18,.18))/n*(hi-lo) for j in range(n))+(1.,)
    heights=tuple(a[1]+(b[1]-a[1])*j/n+(rr.uniform(-.014,.014) if 0<j<n else 0.) for j in range(n+1))
    return breaks,heights

def stair_boundaries(a,b,lateral=0.):
    if a[1]>b[1]:return tuple(1-t for t in stair_boundaries(b,a,-lateral)[::-1])
    breaks,_=stair_profile(tuple(a),tuple(b));length=math.hypot(b[0]-a[0],b[2]-a[2])
    phase=a[0]*.67+b[2]*.31
    def wobble(j):
        p=phase+j*2.17
        return (.065*lateral*math.sin(p)+.05*(math.sin(lateral*4+p)-math.sin(p)))/length
    return tuple(t+(wobble(j) if 0<j<len(breaks)-1 else 0.) for j,t in enumerate(breaks))

def edge_height(a,b,t,lateral=0.):
    if abs(a[1]-b[1])<.1:return a[1]
    boundaries=stair_boundaries(a,b,lateral);_,heights=stair_profile(tuple(a),tuple(b))
    return heights[min(len(heights)-1,sum(t>=v for v in boundaries[1:-1]))]

def edge_point(na,nb,t):
    """Cubic centerline: adjoining upper passages share the same tangent."""
    a,b=NODES[na],NODES[nb]
    if max(a[1],b[1])<.2:return tuple(a[i]+(b[i]-a[i])*t for i in range(3))
    def tangent(name):
        i=UPPER_ROUTE.index(name);p=NODES[UPPER_ROUTE[max(0,i-1)]];q=NODES[UPPER_ROUTE[min(len(UPPER_ROUTE)-1,i+1)]]
        dx,dz=q[0]-p[0],q[2]-p[2];length=math.hypot(dx,dz)
        sign=1 if UPPER_ROUTE.index(nb)>UPPER_ROUTE.index(na) else -1
        return dx/length*sign,dz/length*sign
    ma,mb=tangent(na),tangent(nb);length=math.hypot(b[0]-a[0],b[2]-a[2])
    h00=2*t**3-3*t*t+1;h10=t**3-2*t*t+t;h01=-2*t**3+3*t*t;h11=t**3-t*t
    return (h00*a[0]+h10*ma[0]*length+h01*b[0]+h11*mb[0]*length,
            a[1]+(b[1]-a[1])*t,
            h00*a[2]+h10*ma[1]*length+h01*b[2]+h11*mb[1]*length)

def edge_frame(na,nb,t):
    p=edge_point(na,nb,t);a=edge_point(na,nb,max(0,t-.001));b=edge_point(na,nb,min(1,t+.001))
    dx,dz=b[0]-a[0],b[2]-a[2];length=math.hypot(dx,dz)
    return p,(dx/length,dz/length)

@lru_cache(maxsize=None)
def edge_path(na,nb):
    a,b=NODES[na],NODES[nb]
    n=max(1,math.ceil(math.hypot(b[0]-a[0],b[2]-a[2])/.40)) if max(a[1],b[1])>.2 else 1
    return tuple((j/n,edge_point(na,nb,j/n)) for j in range(n+1))

def path_projection(x,z,na,nb):
    best=(math.inf,0.,0.)
    path=edge_path(na,nb)
    for (ta,a),(tb,b) in zip(path,path[1:]):
        distance,t=segment_position(x,z,a,b)
        if distance<best[0]:
            dx,dz=b[0]-a[0],b[2]-a[2];length=math.hypot(dx,dz)
            lateral=((x-a[0])*dz-(z-a[2])*dx)/length
            best=(distance,ta+(tb-ta)*t,lateral)
    return best

def cut_radius(x,z,radius):
    return radius+.16+.065*math.sin(x*1.31+z*.83)+.025*math.sin(z*4.7-x*2.1)

def surface_samples(x,z,radius=.24):
    result=[]
    for name,cx,cz,rx,rz,h,covered in ROOMS:
        if ((x-cx)/(rx-radius))**2+((z-cz)/(rz-radius))**2<1:result.append((h,0.))
    for na,nb,w,roof in EDGES:
        a,b=NODES[na],NODES[nb];distance,t,lateral=path_projection(x,z,na,nb)
        if distance<w-radius:result.append((edge_height(a,b,t,lateral),distance))
    return result

def surfaces(x,z,radius=.24):return [h for h,d in surface_samples(x,z,radius)]

def support_height(x,z,previous=.08,radius=.24):
    candidates=[(h,d) for h,d in surface_samples(x,z,radius) if abs(h-previous)<.245]
    if not candidates:return None
    height,_=min(candidates,key=lambda p:(round(p[1],5),abs(p[0]-previous)))
    if height<.3:
        px,pz,rx,rz=POND
        if ((x-px)/(rx+radius))**2+((z-pz)/(rz+radius))**2<1:return None
        for cx,cz,r,h in OBSTACLES:
            if math.hypot(x-cx,z-cz)<r+radius:return None
    return height

def can_walk(x,z,height=.08,radius=.24):return support_height(x,z,height,radius) is not None

def camera_zone(x,z,height,current=0):
    if height>.3 and x>11.7:return 9
    if height>.3 and x<-7.4:return 10
    if height>1.85:return 7
    if z<-16.3 or current==8 and z<-15.7:return 8
    if x<-5.2 and z<-6.4:return 5
    if z<-9.0:return 11
    if z<-5.8 and -2.5<x<2:return 12
    if x>6.2 and z<4.5:return 6
    if x<-8.1 and z<10:return 4
    if z>21.3:return 0
    if z>14.6 or current==1 and z>14.1:return 1
    if z>7.7:return 2
    return 3

class Explorer:
    def __init__(self):self.x,self.z=SPAWN;self.floor=.08;self.height=.08;self.yaw=0.;self.phase=0.;self.clip='idle';self.shot=0
    def tick(self,dt,forward=0.,turn=0.,run=False):
        dt=max(0.,min(.1,dt));self.yaw+=turn*dt*1.8;speed=(3.15 if run and forward>0 else 1.5)*forward
        dx=math.sin(self.yaw)*speed*dt;dz=-math.cos(self.yaw)*speed*dt;old=(self.x,self.z)
        steps=max(1,math.ceil(math.hypot(dx,dz)/.045))
        for _ in range(steps):
            h=support_height(self.x+dx/steps,self.z,self.floor)
            if h is not None:self.x+=dx/steps;self.floor=h
            h=support_height(self.x,self.z+dz/steps,self.floor)
            if h is not None:self.z+=dz/steps;self.floor=h
        distance=math.hypot(self.x-old[0],self.z-old[1]);self.phase+=distance/(GAIT['run' if run else 'walk']['stride']*PLAYER_SCALE)
        self.clip=('walk_back' if forward<0 else 'run' if run else 'walk') if distance>.0001 else ('turn_right' if turn>0 else 'turn_left') if turn else 'idle'
        self.height+=(self.floor-self.height)*(1-math.exp(-dt*24));self.shot=camera_zone(self.x,self.z,self.floor,self.shot)
        return distance

REVIEW_ROUTES=(
 ('main',('gate','mouth','throat','fork','reveal','east','east_bend','riddle','north','court')),
 ('west_loop',('fork','west','fern','blind','turn','reveal','fork')),
 ('grotto',('blind','grotto','north')),
 ('upper_crossing',('east_bend','stair_east','high_east','bridge_east','bridge_mid','bridge_west','stair_west','fern')),
 ('blind_window',('reveal','window_turn','window')),
)

def review_points(route):
    """Walk around the court's scholar stone rather than steering into its cover."""
    result=[NODES[route[0]]]
    for a,b in zip(route,route[1:]):
        if {a,b}=={'reveal','east'}:
            detour=((0,.08,.7),(3.8,.08,1.8))
            result.extend(detour if a=='reveal' else detour[::-1])
        result.append(NODES[b])
    return result
