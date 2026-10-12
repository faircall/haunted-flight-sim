"""The separate Hall of Returning Rain art-study scene, in metres."""
import math
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT

SPAWN=(0.,10.1)
PLAYER_SCALE=1.73/25.65
COLUMNS=tuple((x,z,.29) for x in (-6.,6.) for z in (-7.8,-1.,5.8))+((-9.,5.8,.29),(9.,5.8,.29))
BLOCKS=((-5.0,-8.5,5.0,-3.6),(-2.75,-3.45,2.75,-2.45),(-9.7,-8.3,-8.3,-6.7),(8.3,-8.3,9.7,-6.7),
        (-2.70,7.9,-2.50,10.1),(2.50,7.9,2.70,10.1),(-8.65,4.2,-7.35,5.6),(7.35,4.2,8.65,5.6))
SHOTS=(
    dict(name='The threshold',eye=(7.8,3.7,7.3),target=(-1.,2.3,-3.8),fov=66),
    dict(name='The painted assembly',eye=(8.7,3.3,3.8),target=(-3.,2.4,-4.5),fov=70),
    dict(name='Western procession',eye=(-7.6,2.9,-7.8),target=(-4.0,2.5,2.4),fov=73),
    dict(name='Behind the shrine',eye=(8.9,2.8,-8.9),target=(-2.4,2.8,-7.8),fov=70),
    dict(name='Eastern aisle',eye=(8.1,3.3,-7.7),target=(3.5,2.6,3.0),fov=72),
    dict(name='Rain at the door',eye=(-5.8,3.0,1.5),target=(1.1,2.4,10.5),fov=72),
    dict(name='Mandala ceiling',eye=(2.5,1.7,2.4),target=(0.,7.3,-2.),fov=82),
)
LIGHTS=((-4.5,2.3,-3.2),(4.5,2.3,-3.2),(-8.7,2.6,1.0),(8.7,2.6,1.),(-3.6,2.5,-9.),(3.6,2.5,-9.))

def can_walk(x,z,radius=.24):
    if not(-9.55+radius<x<9.55-radius and -9.6+radius<z<23-radius):return False
    if 7.65-radius<z<8.45+radius and abs(x)>2.35-radius:return False
    for cx,cz,r in COLUMNS:
        if math.hypot(x-cx,z-cz)<r+radius:return False
    for left,back,right,front in BLOCKS:
        if left-radius<x<right+radius and back-radius<z<front+radius:return False
    return True

def camera_zone(x,z,current=0):
    # Dead bands hold the shot at boundaries while the player turns.
    if z<-8.6:return 3
    if current==3 and z<-8.25:return 3
    if z>7.8:return 0
    if x<-4.95:return 2
    if current==2 and x<-4.55:return 2
    if x>4.95:return 4
    if current==4 and x>4.55:return 4
    return 1

class Explorer:
    def __init__(self):self.x,self.z=SPAWN;self.yaw=0.;self.phase=0.;self.shot=0;self.clip='idle'
    def tick(self,dt,forward=0.,turn=0.,run=False):
        dt=max(0.,min(.1,dt));self.yaw+=turn*dt*1.8
        speed=(3.4 if run and forward>0 else 1.55)*forward
        dx=math.sin(self.yaw)*speed*dt;dz=-math.cos(self.yaw)*speed*dt
        old=(self.x,self.z)
        # Substeps and sliding allow controlled movement beside columns.
        steps=max(1,math.ceil(math.hypot(dx,dz)/.06))
        for _ in range(steps):
            if can_walk(self.x+dx/steps,self.z):self.x+=dx/steps
            if can_walk(self.x,self.z+dz/steps):self.z+=dz/steps
        distance=math.hypot(self.x-old[0],self.z-old[1]);self.phase+=distance/(GAIT['run' if run else 'walk']['stride']*PLAYER_SCALE)
        self.clip=('walk_back' if forward<0 else 'run' if run else 'walk') if distance>.0001 else ('turn_right' if turn>0 else 'turn_left') if turn else 'idle'
        self.shot=camera_zone(self.x,self.z,self.shot)
        return distance
