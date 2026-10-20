"""A brief pause within a slow fog arrival; exploration discovers the canals."""
import math
from g_interaction_data import SLOT_COUNT
from g_huxin_canals import DECK, can_walk, walk_height, COLUMNS, BENCHES, smooth, shore_radius, PATH
from g_exploration_fog import ExplorationFog
from g_canals_fog_grid import CanalFogGrid

ENTRY_SWAP=5.
ENTRY_DURATION=5.
FOG_ARRIVAL_DURATION=30.
REVEAL_START_RADIUS=4.5
REVEAL_END_RADIUS=9.5
ENTRY_CLEAR=ENTRY_DURATION # Player discovery can start while the fog is still arriving.
def ease(a,b,x):
    """Quintic easing: velocity and acceleration meet without a visible corner."""
    t=max(0.,min(1.,(x-a)/(b-a)))
    return max(0.,min(1.,t*t*t*(t*(t*6.-15.)+10.)))

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
DISC_ITEM={'kind':'key','group':'void_disc','name':'Stone annulus','count':1}


def support(x,z,previous,revealed,r=.19):
    if revealed:
        from g_huxin_canals_layout import support as canal_support
        h=canal_support(x,z,previous,r)
    else:
        h=walk_height(x,z) if can_walk(x,z,r) else None
    if h is not None and abs(h-DECK)<.1:
        if math.hypot(x,z)<.88+r or math.hypot(x-MIRROR[0],z-MIRROR[2])<.22+r:return None
    return h


class CanalSequence:
    def __init__(self):
        from g_inventory import add
        self.state='ordinary';self.revealed=False;self.elapsed=0.;self.approach=0.
        self.focus=False;self.yaw,self.pitch=SOLUTION;self.held=0.;self.disc_placed=False
        self.entry_veil=.72;self.entry_arrival=.93;self.locked_camera=None;self.locked_pose=None;self.locked_shot=None
        # This short departure gate controls only the hidden world handoff.
        # Fog itself remembers visited cells, never distance from the basin.
        self.exploration=ExplorationFog(inner_distance=3.5,outer_distance=58.,origin=(0.,DECK,0.))
        self.fog_grid=CanalFogGrid()
        self.inventory=[None]*SLOT_COUNT;add(self.inventory,DISC_ITEM)
        self.events=[];self.swaps=[];self.bells=0;self.world_time=0.;self.next_creak=39.

    @property
    def world(self):return 'canals' if self.revealed else 'lake'
    @property
    def transitioning(self):return self.state=='entering'
    @property
    def movement_locked(self):return self.transitioning
    @property
    def world_blend(self):
        """Time alone never exposes the village, even after the fog settles."""
        if self.state!='canals':return 0.
        return ease(REVEAL_START_RADIUS,REVEAL_END_RADIUS,self.exploration.furthest_distance)
    @property
    def veil(self):
        if self.state=='ordinary':return .72*ease(0.,1.,self.approach)
        if self.state in ('entering','canals'):return self.entry_veil
        return 0.
    @property
    def fog_arrival(self):
        if self.state=='ordinary':return .93*ease(0.,1.,self.approach)
        if self.state in ('entering','canals'):
            return self.entry_arrival+(1.-self.entry_arrival)*ease(0.,FOG_ARRIVAL_DURATION,self.elapsed)
        return 0.
    @property
    def fog_source_arrival(self):
        """The leading fog keeps its activation density as its front moves."""
        return self.fog_arrival if self.state=='ordinary' else self.entry_arrival
    @property
    def fog_depth(self):
        """Additional, spatially trailing fog; never an opacity change to the lead."""
        if self.state in ('entering','canals'):return ease(3.,FOG_ARRIVAL_DURATION,self.elapsed)
        return 0.
    @property
    def fog_clear(self):
        """Explored area for colour grading only; the shader clears per cell."""
        return self.fog_grid.clear_fraction if self.state=='canals' else 0.
    @property
    def camera_stage(self):return 'continuous' if self.transitioning else None
    @property
    def warmth(self):return 0.
    @property
    def void_tone(self):return self.fog_clear
    @property
    def normal(self):return (math.sin(self.yaw)*math.cos(self.pitch),math.sin(self.pitch),math.cos(self.yaw)*math.cos(self.pitch))

    def hit(self):
        n=self.normal;d=sum(MOON[i]*n[i] for i in range(3));ray=tuple(-MOON[i]+2*d*n[i] for i in range(3))
        if ray[1]>=-.0001:return None
        t=(BASIN[1]-MIRROR[1])/ray[1];p=tuple(MIRROR[i]+ray[i]*t for i in range(3))
        return p if t>0 and math.hypot(p[0],p[2])<.69 else None

    def activate(self,e):
        if self.state!='ordinary' or self.disc_placed or math.hypot(e.x-MIRROR[0],e.z-MIRROR[2])>=2.1:return False
        slot=next((i for i,s in enumerate(self.inventory) if s and s.get('kind')=='key' and s.get('group')==DISC_ITEM['group'] and s.get('count',0)>0),None)
        if slot is None:return False
        self.inventory[slot]['count']-=1
        if not self.inventory[slot]['count']:self.inventory[slot]=None
        self.disc_placed=True;self.entry_veil=self.veil;self.entry_arrival=self.fog_arrival
        self.state='entering';self.elapsed=0.;self.focus=False;self.events.append('bell');self.bells+=1
        return True

    def tick(self,dt,e):
        self.approach=causeway_progress(e.x,e.z)
        if self.state in ('entering','canals'):
            # The cloud has its own long clock. Releasing control neither
            # completes nor resets it, and it never drives the world reveal.
            self.elapsed=min(FOG_ARRIVAL_DURATION,self.elapsed+dt)
        if self.state=='entering':
            if self.elapsed>=ENTRY_SWAP and not self.revealed:
                self.revealed=True;self.swaps.append(('entering',self.veil))
            if self.elapsed>=ENTRY_DURATION:
                self.state='canals';self.world_time=0.
        elif self.state=='canals':
            self.exploration.update(e.x,e.height,e.z)
            self.fog_grid.update(e.x,e.height,e.z,strength=self.world_blend)
            self.world_time+=dt
            # Sparse, low-level timber movement, separated by long silences.
            if self.world_time>=self.next_creak:
                self.events.append('timber');self.next_creak+=47.+17.*math.sin(self.next_creak*.13)**2

    def prompt(self,e):
        if self.transitioning:return ''
        if self.state=='ordinary' and math.hypot(e.x-MIRROR[0],e.z-MIRROR[2])<2.1:
            available=any(s and s.get('group')==DISC_ITEM['group'] for s in self.inventory)
            return 'E  Place the stone annulus on the basin' if available else 'A circular recess in the basin.'
        return ''
