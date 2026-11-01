"""Isolated movement for the optional Chorus figure demonstration.

The existing enemy AI, saves and scene files are not touched. The actor follows
an existing causeway centreline and advances its motion by actual distance.
"""
from dataclasses import dataclass
import math

from chorus_grasper_animation import GAITS,BRISK_WALK_SPEED
from g_huxin_moon import PLAYER_SCALE,walk_height
from g_huxin_moon_sequence import CAUSEWAY_LENGTH,causeway_point,causeway_progress


@dataclass
class FigureMotion:
    progress:float=.69
    yaw:float=0.
    phase:float=0.
    idle_phase:float=0.
    clip:str='enemy_idle'
    mode:str='follow'
    pace:str='idle'
    paused:bool=False

    @property
    def position(self):
        x,z=causeway_point(self.progress)
        return x,walk_height(x,z),z

    def tick(self,dt,player):
        dt=max(0.,min(.1,float(dt)))
        if self.paused:return
        if self.mode not in ('follow','idle','walk','brisk'):raise ValueError('Unknown figure mode')
        if self.mode!='follow':
            self.pace=self.mode
            self.clip='enemy_idle' if self.mode=='idle' else 'enemy_walk'
            if self.mode=='idle':self.idle_phase+=dt/2.5
            else:
                gait=GAITS[self.clip]
                speed=BRISK_WALK_SPEED if self.mode=='brisk' else gait['speed']
                self.phase+=dt*speed/(gait['stride']*PLAYER_SCALE)
            return
        target=causeway_progress(player.x,player.z)
        gap=(target-self.progress)*CAUSEWAY_LENGTH
        previous=self.position
        if abs(gap)<1.15:
            self.pace='idle';self.clip='enemy_idle';self.idle_phase+=dt/2.5
            return
        self.pace='brisk' if abs(gap)>2.5 else 'walk'
        self.clip='enemy_walk';gait=GAITS[self.clip]
        speed=BRISK_WALK_SPEED if self.pace=='brisk' else gait['speed']
        move=min(speed*dt,max(0.,abs(gap)-1.1))
        self.progress=max(0.,min(1.,self.progress+math.copysign(move/CAUSEWAY_LENGTH,gap)))
        x,_,z=self.position;distance=math.hypot(x-previous[0],z-previous[2])
        self.phase+=distance/(gait['stride']*PLAYER_SCALE)
        if distance>1.e-7:
            target_yaw=math.atan2(x-previous[0],-(z-previous[2]))
            delta=(target_yaw-self.yaw+math.pi)%math.tau-math.pi
            self.yaw+=delta*min(1.,dt*8.)

    @property
    def pose_phase(self):return self.idle_phase if self.clip=='enemy_idle' else self.phase
