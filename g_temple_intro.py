"""Deterministic, slightly interactive car ride; no rendering or game saves."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
from g_temple_cinematics import default_camera,validate_camera
from g_intro_landscape import road_x,road_slope,local_point,scenery

ROOT=Path(__file__).resolve().parent
SCRIPT=ROOT/'art'/'temple'/'intro'/'dialogue.json'
WIPER_PERIOD=1.85


def load_script(path=SCRIPT):
    document=json.loads(Path(path).read_text(encoding='utf-8'))
    validate_script(document)
    return document


def validate_script(document):
    duration=document['duration']
    if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<30:
        raise ValueError('Invalid intro duration.')
    end=0.
    for line in document['lines']:
        if not 0<=line['start']<line['end']<=duration or line['start']<end:
            raise ValueError('Dialogue lines must be ordered and not overlap.')
        if not line['speaker'] or not line['text']:raise ValueError('Empty dialogue.')
        end=line['end']
    end=0.;identities=set()
    for shot in document['shots']:
        if not shot.get('id') or shot['id'] in identities:raise ValueError('Shots need unique names.')
        identities.add(shot['id'])
        if shot['start']!=end or not shot['start']<shot['end']<=duration:
            raise ValueError('Shots must cover the entire ride without gaps or overlaps.')
        if shot['kind'] not in ('opening','interior','drone','tracking','arrival','exterior'):
            raise ValueError('Unknown intro shot.')
        if 'camera' in shot:validate_camera(shot['camera'])
        end=shot['end']
    if end!=duration:raise ValueError('Shots must end at arrival.')
    if sum(s['kind']=='tracking' for s in document['shots'])!=1:
        raise ValueError('The ride needs one day-to-night tracking shot.')
    return document


def smooth(value):
    value=max(0.,min(1.,value));return value*value*(3-2*value)


def wiper_angle(elapsed):
    # Smooth at the reversals, without holding at either end of the sweep.
    phase=elapsed/WIPER_PERIOD
    return math.radians(8+94*(.5-.5*math.cos(math.tau*phase)))


@dataclass
class Intro:
    document:dict
    elapsed:float=0.
    yaw:float=0.
    pitch:float=-8.
    paused:bool=False
    skipped:bool=False

    @property
    def duration(self):return self.document['duration']

    @property
    def finished(self):return self.skipped or self.elapsed>=self.duration

    @property
    def progress(self):return min(1.,self.elapsed/self.duration)

    @property
    def shot(self):
        return next((s for s in self.document['shots'] if s['start']<=self.elapsed<s['end']),self.document['shots'][-1])

    @property
    def interactive(self):return (self.shot.get('camera') or default_camera(self.shot['kind']))['mode']=='interactive'

    @property
    def shot_progress(self):return smooth((self.elapsed-self.shot['start'])/(self.shot['end']-self.shot['start']))

    @property
    def night_shot(self):return next(s for s in self.document['shots'] if s['kind']=='tracking')

    @property
    def dusk(self):
        # Late afternoon barely cools before the side-on time-lapse. All of
        # the substantial light change happens while that camera holds the car.
        shot=self.night_shot
        return .18*smooth(self.elapsed/max(.001,shot['start']))+.82*smooth((self.elapsed-shot['start'])/(shot['end']-shot['start']))

    @property
    def headlights(self):
        shot=self.night_shot
        phase=(self.elapsed-shot['start'])/(shot['end']-shot['start'])
        return smooth((phase-5/19)/(2.5/19))

    @property
    def distance(self):
        # Cruise, then ease to a stop during the final eleven seconds. Integral
        # of the speed curve, independent of render FPS and camera interaction.
        cruise=self.duration-15
        if self.elapsed<=cruise:return 10.5*self.elapsed
        t=min(11.,self.elapsed-cruise);u=t/11
        return 10.5*cruise+10.5*11*(u-u**3+.5*u**4)

    @property
    def speed(self):return 10.5*(1-smooth((self.elapsed-(self.duration-15))/11))

    @property
    def arrival_station(self):return 10.5*(self.duration-15)+10.5*11*.5+20

    @property
    def line(self):
        return next((line for line in self.document['lines'] if line['start']<=self.elapsed<line['end']),None)

    @property
    def fade(self):
        return max(1-smooth(self.elapsed/2.5),smooth((self.elapsed-(self.duration-3))/3))

    def tick(self,dt,mouse=(0.,0.),pause=False,skip=False,reset=False):
        if pause:self.paused=not self.paused
        if skip:self.skipped=True
        if reset and self.interactive:self.yaw,self.pitch=0.,-8.
        if not self.paused and not self.finished:
            if self.interactive:
                self.yaw=(self.yaw+mouse[0]*.14+180)%360-180
                self.pitch=max(-65.,min(62.,self.pitch-mouse[1]*.12))
            self.elapsed=min(self.duration,self.elapsed+max(0.,min(.1,dt)))
