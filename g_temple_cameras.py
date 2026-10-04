"""Fixed-camera walkthrough logic, independent of Raylib and rendering.

Coordinates: X/right, Z/ground-map Y. A movement chord keeps its camera basis
until all movement keys are released, preventing direction flips at a cut.
"""
from dataclasses import dataclass,field
from pathlib import Path
import json,math

SHOT_FILE=Path(__file__).resolve().parent/'art'/'temple'/'camera_shots.json'


def load_shots(path=SHOT_FILE):
    shots=json.loads(Path(path).read_text())
    for name,shot in shots.items():
        if len(shot['eye'])!=3 or len(shot['target'])!=3 or shot['span']<=0:raise ValueError('Invalid camera: '+name)
        if math.hypot(shot['eye'][0]-shot['target'][0],shot['eye'][2]-shot['target'][2])<1e-6:
            raise ValueError('A vertical camera needs an explicit movement basis: '+name)
        for box in ('enter','hold'):
            x0,y0,x1,y1=shot[box]
            if x1<=x0 or y1<=y0:raise ValueError('Invalid camera region: '+name)
    return shots


def contains(bounds,x,y):
    x0,y0,x1,y1=bounds
    return x0<=x<x1 and y0<=y<y1


def movement_basis(shot):
    # Screen up moves away from the camera along the walkable ground plane.
    dx=shot['target'][0]-shot['eye'][0];dy=shot['target'][2]-shot['eye'][2]
    length=math.hypot(dx,dy);forward=(dx/length,dy/length)
    return (-forward[1],forward[0]),forward


@dataclass
class CameraDirector:
    shots:dict=field(default_factory=load_shots)
    active:str='approach'
    cut_count:int=0

    @property
    def shot(self):return self.shots[self.active]

    def update(self,x,y):
        candidates=[name for name,s in self.shots.items() if contains(s['enter'],x,y)]
        candidate=max(candidates,key=lambda n:self.shots[n]['priority'],default=self.active)
        if self.shots[candidate]['priority']>self.shot['priority'] or not contains(self.shot['hold'],x,y):
            if candidate!=self.active:self.active=candidate;self.cut_count+=1;return True
        return False


@dataclass
class MovementIntent:
    basis:tuple|None=None
    source_camera:str|None=None

    def direction(self,keys,director):
        keys=set(keys)&{'w','a','s','d'}
        if not keys:
            self.basis=None;self.source_camera=None;return (0.,0.)
        horizontal=int('d' in keys)-int('a' in keys)
        vertical=int('w' in keys)-int('s' in keys)
        if self.basis is None and (horizontal or vertical):
            self.basis=movement_basis(director.shot);self.source_camera=director.active
        if self.basis is None:return (0.,0.)
        right,forward=self.basis
        dx=right[0]*horizontal+forward[0]*vertical;dy=right[1]*horizontal+forward[1]*vertical
        length=math.hypot(dx,dy)
        return (dx/length,dy/length) if length else (0.,0.)


def move_with_collision(x,y,dx,dy,distance,can_walk):
    # Small swept steps retain the existing tile-shape collision at low FPS.
    steps=max(1,math.ceil(abs(distance)/2.))
    for _ in range(steps):
        nx=x+dx*distance/steps
        if can_walk(nx,y):x=nx
        ny=y+dy*distance/steps
        if can_walk(x,ny):y=ny
    return x,y


@dataclass
class Walkthrough:
    x:float=256.
    y:float=334.
    director:CameraDirector=field(default_factory=CameraDirector)
    intent:MovementIntent=field(default_factory=MovementIntent)
    distance:float=0.
    heading:tuple=(1.,0.)
    moving:bool=False

    def step(self,keys,dt,can_walk,speed=65.):
        dx,dy=self.intent.direction(keys,self.director);old=(self.x,self.y)
        self.x,self.y=move_with_collision(self.x,self.y,dx,dy,speed*max(0.,dt),can_walk)
        travel=math.hypot(self.x-old[0],self.y-old[1]);self.distance+=travel;self.moving=travel>1e-5
        if self.moving:self.heading=((self.x-old[0])/travel,(self.y-old[1])/travel)
        return self.director.update(self.x,self.y)


REVIEW_ROUTE=((128.,334.),(152.,334.),(176.,334.),(256.,334.),(402.,334.),(480.,334.),
              (480.,292.),(480.,258.),(480.,231.),(480.,294.),(480.,334.),(320.,334.),(128.,334.))
REVIEW_SHOTS=('approach','approach','approach','approach','landing','landing',
              'landing','sanctum','sanctum','landing','landing','approach','approach')
