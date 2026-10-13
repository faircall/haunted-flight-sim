"""Independent winding-path / Chan-room study. All dimensions are metres."""
import math
import random
from functools import lru_cache
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT

PLAYER_SCALE=1.73/25.65
SPAWN=(0.,40.)
CONTROL=((0,45),(0,40),(1.5,33),(-4.7,26),(-6.8,20),(-3.3,14),(3.5,8),(2.8,3),(0,-1),(0,-3.5))

def path_points():
    points=[];p=(CONTROL[0],)+CONTROL+(CONTROL[-1],)
    for i in range(1,len(p)-2):
        for j in range(16):
            t=j/16
            points.append(tuple(.5*((2*p[i][a])+(-p[i-1][a]+p[i+1][a])*t+
                (2*p[i-1][a]-5*p[i][a]+4*p[i+1][a]-p[i+2][a])*t*t+
                (-p[i-1][a]+3*p[i][a]-3*p[i+1][a]+p[i+2][a])*t*t*t) for a in (0,1)))
    return tuple(points)+(CONTROL[-1],)

PATH=path_points()
SEGMENTS=tuple((a,b,(b[0]-a[0])**2+(b[1]-a[1])**2) for a,b in zip(PATH,PATH[1:]))

def path_distance(x,z):
    closest=1e10
    for a,b,length in SEGMENTS:
        t=max(0,min(1,((x-a[0])*(b[0]-a[0])+(z-a[1])*(b[1]-a[1]))/max(1e-8,length)))
        closest=min(closest,(x-a[0]-t*(b[0]-a[0]))**2+(z-a[1]-t*(b[1]-a[1]))**2)
    return math.sqrt(closest)

def ground_height(x,z):
    # Flat courtyard blends into soft forest mounds, never sharp road banks.
    court=math.exp(-((x/13)**4+((z+5)/17)**4))
    base=-.22+.19*math.sin(z*.115)+.12*math.sin(x*.27+z*.13)
    return base*(1-court)+.035*court

def floor_height(x,z):
    if abs(x)<5.15 and -13.5<z<-2.65:return .63
    if abs(x)<1.85 and -2.65<=z<-.3:
        return .15+.16*min(3,int((-.3-z)/.59))
    return ground_height(x,z)+.045

LIGHTS=((-2.35,2.85,-2.9),(2.35,2.85,-2.9),(-.9,2.7,-11.8),(-7.8,1.1,19),(5.1,1.05,7.9),(2.2,1.0,35.5))
BLOCKS=((-4.55,-13.0,4.55,-12.65),(-4.7,-13.,-4.38,-4.9),(4.38,-13.,4.7,-4.9),
        (-4.6,-5.12,-1.30,-4.9),(1.30,-5.12,4.6,-4.9),
        (-3.9,-12.7,-2.4,-12.15),(1.6,-12.0,3.9,-10.8),(-4.1,-10.8,-3.6,-8.2))
COLUMNS=tuple((x,z,.15) for x in (-4.35,-1.5,1.5,4.35) for z in (-5.,-3.0))

SHOTS=(
    dict(name='Bamboo threshold',eye=(5.3,3.2,44),target=(-.3,1.45,34.2),fov=66),
    dict(name='The hidden bend',eye=(-11,3.2,28),target=(-4.5,1.65,21.5),fov=66),
    dict(name='A light between stems',eye=(6.4,3.0,19.0),target=(-2.,2.1,7.8),fov=69),
    dict(name='Flowers at the eaves',eye=(10.2,3.3,8.5),target=(-.7,2.25,-4.8),fov=66),
    dict(name='The quiet room',eye=(3.70,2.75,-5.65),target=(-.7,1.85,-10.3),fov=73),
    dict(name='Looking back',eye=(3.65,2.75,-12.0),target=(-.2,1.7,-3.5),fov=73),
    dict(name='Bamboo canopy',eye=(-5.9,1.6,22),target=(-4.,13.,17),fov=77),
    dict(name='The side garden',eye=(-11.8,3.0,-8.3),target=(-.7,2.25,-4.5),fov=70),
)

def camera_zone(x,z,current=0):
    if abs(x)<4.5 and z<-5.3:
        if z<-9.4 or current==5 and z<-8.8:return 5
        return 4
    if x<-7.1 and z<1:return 7
    for threshold,zone in ((31,0),(22,1),(11,2)):
        if z>threshold+(.6 if current>zone else -.6):return zone
    return 3

def camera_clear(x,z):
    # An unobtrusive corridor behind each camera avoids a stalk filling the lens.
    for shot in SHOTS:
        a=shot['eye'];b=shot['target'];dx=b[0]-a[0];dz=b[2]-a[2];length=math.hypot(dx,dz)
        if length<1:continue
        t=((x-a[0])*dx+(z-a[2])*dz)/(length*length)
        if -.1<t<min(1.,4.0/length) and abs((x-a[0])*dz-(z-a[2])*dx)/length<.75:return False
    return True

@lru_cache(maxsize=1)
def bamboo_layout():
    rng=random.Random(10613);plants=[]
    for iz in range(49):
        for ix in range(43):
            x=-39+ix*1.85+rng.uniform(-.68,.68);z=-34+iz*1.85+rng.uniform(-.68,.68)
            clear=(x/11.6)**2+((z+7)/14.2)**2
            if clear<1. or path_distance(x,z)<2.05 or not camera_clear(x,z):continue
            if rng.random()<.24:continue
            # Higher density and sharper silhouettes near the explored path.
            far=path_distance(x,z)>15 and clear>2.3
            plants.append((round(x,3),round(z,3),rng.uniform(10.5,17.5),rng.uniform(.075,.135),rng.random()*math.tau,far))
    return tuple(plants)

@lru_cache(maxsize=1)
def bamboo_grid():
    cells={}
    for x,z,_,r,_,_ in bamboo_layout():cells.setdefault((math.floor(x/2),math.floor(z/2)),[]).append((x,z,r))
    return cells

def can_walk(x,z,radius=.24):
    if not(-17+radius<x<17-radius and -19+radius<z<42-radius):return False
    clearing=(x/10.9)**2+((z+5)/13.5)**2<1
    if not clearing and path_distance(x,z)>1.80-radius:return False
    # The raised veranda is reached by the low front steps, not through its sides.
    if -13.6<z<-2.75 and 4.95-radius<abs(x)<5.4+radius:return False
    if -2.85-radius<z<-2.55+radius and 1.8-radius<abs(x)<5.3:return False
    for a,b,c,d in BLOCKS:
        if a-radius<x<c+radius and b-radius<z<d+radius:return False
    for cx,cz,r in COLUMNS:
        if math.hypot(x-cx,z-cz)<r+radius:return False
    # Basin and trunk of the flowering trees.
    for cx,cz,r in ((-6.5,-1.0,.75),(-7.4,-4,.24),(6.8,-4.5,.24),(0,-9.25,.6),(.25,-11.4,.31)):
        if math.hypot(x-cx,z-cz)<r+radius:return False
    for cx,_,cz in LIGHTS:
        if cz>0 and math.hypot(x-cx,z-cz)<.32+radius:return False
    gx,gz=math.floor(x/2),math.floor(z/2)
    for xx in range(gx-1,gx+2):
        for zz in range(gz-1,gz+2):
            for cx,cz,r in bamboo_grid().get((xx,zz),()):
                if math.hypot(x-cx,z-cz)<r+radius:return False
    return True

class Explorer:
    def __init__(self):self.x,self.z=SPAWN;self.yaw=0.;self.phase=0.;self.shot=0;self.clip='idle';self.height=floor_height(*SPAWN)
    def tick(self,dt,forward=0.,turn=0.,run=False):
        dt=max(0.,min(.1,dt));self.yaw+=turn*dt*1.8
        speed=(3.4 if run and forward>0 else 1.55)*forward
        dx=math.sin(self.yaw)*speed*dt;dz=-math.cos(self.yaw)*speed*dt;old=(self.x,self.z)
        steps=max(1,math.ceil(math.hypot(dx,dz)/.055))
        for _ in range(steps):
            if can_walk(self.x+dx/steps,self.z):self.x+=dx/steps
            if can_walk(self.x,self.z+dz/steps):self.z+=dz/steps
        distance=math.hypot(self.x-old[0],self.z-old[1]);self.phase+=distance/(GAIT['run' if run else 'walk']['stride']*PLAYER_SCALE)
        self.clip=('walk_back' if forward<0 else 'run' if run else 'walk') if distance>.0001 else ('turn_right' if turn>0 else 'turn_left') if turn else 'idle'
        self.shot=camera_zone(self.x,self.z,self.shot)
        self.height+=(floor_height(self.x,self.z)-self.height)*(1-math.exp(-dt*24.))
        return distance
