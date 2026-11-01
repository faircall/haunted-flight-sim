"""Relaxed jogging at the player's normal 3.15 m/s movement speed.

All coordinates are lateral / forward / up in the shared rig's author units.
The short contact arc is locked to travelled distance; swing uses a folded
heel recovery and moderate knee drive rather than the sprint's high front pose.
"""
import math

from photo_asset_pipeline.temple3d.living import gait as base

JOG_STRIDE = 33.5
JOG_SPEED = 3.15
STANCE = .35
JOG_STANCE = STANCE
FRONT = 5.2
BACK = JOG_STRIDE*STANCE-FRONT
THIGH = base.THIGH
SHIN = base.SHIN
ANKLE = base.ANKLE
HEEL = base.HEEL
TOE = base.TOE
HIP_HALF_WIDTH = base.HIP_HALF_WIDTH


def pelvis(phase):
    a=math.tau*phase
    lateral=-.30*math.cos(a-.85)
    roll=math.radians(1.25)*lateral/.30
    pitch=math.radians(2.)
    yaw=-math.radians(2.8)*math.cos(a)
    up=(math.sin(roll),math.sin(pitch)*math.cos(roll),math.cos(pitch)*math.cos(roll))
    x,y,z=up
    right=(1-x*x/(1+z),-x*y/(1+z),-x)
    forward=(-x*y/(1+z),1-y*y/(1+z),-y)
    right=tuple(a*math.cos(yaw)+b*math.sin(yaw) for a,b in zip(right,forward))
    return dict(lateral=lateral,forward=.55+.035*math.sin(2*a),up=up,right=right,yaw=yaw)


def foot_lateral(sign,phase):
    p=phase%1.
    swing=max(0.,(p-STANCE)/(1-STANCE))
    return sign*(1.13-.055*math.sin(math.pi*swing)**2)


def support_foot(phase):
    """Exact heel/toe pivot contact throughout the planted interval."""
    p=phase%1.
    heel=10.*max(0.,1-p/.052)**2
    toe=35.*max(0.,(p-.235)/(STANCE-.235))**2
    pitch=math.radians(heel-toe)
    contact=HEEL if pitch>=0 else TOE
    forward=FRONT-JOG_STRIDE*p+contact-(contact*math.cos(pitch)+ANKLE*math.sin(pitch))
    height=ANKLE*math.cos(pitch)-contact*math.sin(pitch)
    return dict(forward=forward,height=height,pitch=pitch,clearance=0.,stance=True)


def _contact_height():
    f=support_foot(0.)
    m=pelvis(0.)
    off=tuple(-HIP_HALF_WIDTH*x for x in m['right'])
    dx=foot_lateral(-1,0.)-m['lateral']-off[0]
    df=f['forward']-m['forward']-off[1]
    reach2=THIGH*THIGH+SHIN*SHIN+2*THIGH*SHIN*math.cos(math.radians(18.))
    return f['height']-off[2]+math.sqrt(reach2-dx*dx-df*df)


def hip_height(phase):
    p=phase%.5;contact=_contact_height()
    if p<.12:preferred=base.hermite(contact,12.34,0.,0.,p/.12,.12)
    elif p<STANCE:preferred=base.hermite(12.34,11.75,0.,0.,(p-.12)/(STANCE-.12),STANCE-.12)
    elif p<.425:preferred=base.hermite(11.75,12.48,0.,0.,(p-STANCE)/(.425-STANCE),.425-STANCE)
    else:preferred=base.hermite(12.48,contact,0.,0.,(p-.425)/(.5-.425),.5-.425)
    m=pelvis(phase)
    for side,sign in ((0.,-1),(.5,1)):
        if (phase+side)%1.>=STANCE:continue
        f=support_foot(phase+side)
        off=tuple(sign*HIP_HALF_WIDTH*x for x in m['right'])
        dx=foot_lateral(sign,phase+side)-m['lateral']-off[0]
        df=f['forward']-m['forward']-off[1]
        reach=THIGH+SHIN-.025
        ceiling=f['height']-off[2]+math.sqrt(max(.001,reach*reach-dx*dx-df*df))
        preferred=base.soft_min(preferred,ceiling,.012)
    return preferred


def reference_hip(phase):
    m=pelvis(phase)
    center=(m['lateral'],m['forward'],hip_height(phase))
    return tuple(a-HIP_HALF_WIDTH*b for a,b in zip(center,m['right']))


def contact_angles(phase):
    f=support_foot(phase);hip=reference_hip(phase)
    delta=(foot_lateral(-1,phase)-hip[0],f['forward']-hip[1],f['height']-hip[2])
    distance=math.sqrt(sum(v*v for v in delta))
    flex=math.acos(max(-1.,min(1.,(distance*distance-THIGH*THIGH-SHIN*SHIN)/(2*THIGH*SHIN))))
    thigh=math.atan2(delta[1],-delta[2])+flex/2
    return thigh,flex


def swing_angles(phase):
    p=phase;eps=1e-6
    start=contact_angles(STANCE);prior=contact_angles(STANCE-eps)
    start_rate=tuple((a-b)/eps for a,b in zip(start,prior))
    end=contact_angles(0.);after=contact_angles(eps)
    end_rate=tuple((a-b)/eps for a,b in zip(after,end))
    # Angles in degrees at expressive landmarks. Every passing landmark has
    # through-velocity; only the actual anatomical reversals turn around.
    keys=[(STANCE,start,start_rate),
          (.43,tuple(map(math.radians,(-14.,78.))),tuple(map(math.radians,(170.,500.)))),
          (.53,tuple(map(math.radians,(3.,105.))),tuple(map(math.radians,(180.,0.)))),
          (.70,tuple(map(math.radians,(35.,93.))),tuple(map(math.radians,(160.,-140.)))),
          (.79,tuple(map(math.radians,(45.,75.))),tuple(map(math.radians,(0.,-260.)))),
          (1.,end,end_rate)]
    for (a,values,rates),(b,next_values,next_rates) in zip(keys,keys[1:]):
        if p<=b:
            return tuple(base.hermite(x,y,v,w,(p-a)/(b-a),b-a) for x,y,v,w in zip(values,next_values,rates,next_rates))
    return end


def foot(phase):
    p=phase%1.
    if p<=STANCE:return support_foot(phase)
    thigh,flex=swing_angles(p);hip=reference_hip(p)
    # The foot folds after toe-off, then relaxes into a low heel contact.
    if p<.43:pitch=base.hermite(-35.,-48.,-70./(STANCE-.235),0.,(p-STANCE)/(.43-STANCE),.43-STANCE)
    elif p<.86:pitch=base.hermite(-48.,15.,0.,0.,(p-.43)/.43,.43)
    else:pitch=base.hermite(15.,10.,0.,-20./.052,(p-.86)/.14,.14)
    pitch=math.radians(pitch)
    distance=math.sqrt(THIGH*THIGH+SHIN*SHIN+2*THIGH*SHIN*math.cos(flex))
    dx=foot_lateral(-1,p)-hip[0];scale=math.sqrt(max(.001,1-dx*dx/(distance*distance)))
    forward=hip[1]+scale*(THIGH*math.sin(thigh)+SHIN*math.sin(thigh-flex))
    height=hip[2]-scale*(THIGH*math.cos(thigh)+SHIN*math.cos(thigh-flex))
    contact=HEEL if pitch>=0 else TOE
    sole=ANKLE*math.cos(pitch)-contact*math.sin(pitch)
    return dict(forward=forward,height=height,pitch=pitch,clearance=height-sole,stance=False)


def leg(phase,side=0.):
    m=pelvis(phase);sign=-1 if side==0. else 1
    target=foot(phase+side)
    center=(m['lateral'],m['forward'],hip_height(phase))
    hip=tuple(a+sign*HIP_HALF_WIDTH*b for a,b in zip(center,m['right']))
    ankle=(foot_lateral(sign,phase+side),target['forward'],target['height'])
    delta=tuple(a-b for a,b in zip(ankle,hip));distance=math.sqrt(sum(v*v for v in delta))
    if not abs(THIGH-SHIN)<distance<THIGH+SHIN:raise ValueError(('Unreachable jog ankle',phase,side,distance))
    axis=tuple(v/distance for v in delta)
    pole=(sign*.015,1.,0.);dot=sum(a*b for a,b in zip(pole,axis))
    pole=tuple(a-dot*b for a,b in zip(pole,axis));length=math.sqrt(sum(v*v for v in pole));pole=tuple(v/length for v in pole)
    along=(THIGH*THIGH-SHIN*SHIN+distance*distance)/(2*distance)
    bend=math.sqrt(max(0.,THIGH*THIGH-along*along))
    knee=tuple(a+along*b+bend*c for a,b,c in zip(hip,axis,pole))
    return dict(hip=hip,knee=knee,ankle=ankle,**target)


def arm_vectors(phase,sign):
    wave=math.cos(math.tau*phase)
    shoulder=math.radians(-13.-31.*wave)
    # Let the rear hand travel behind the hip. Keeping both elbows near a
    # right angle through the rear sweep leaves the palms hovering in front.
    flex=math.radians(74.-18.*math.cos(math.tau*(phase-.08)))
    abduction=math.radians(7.)
    upper=(sign*math.sin(abduction),math.sin(shoulder)*math.cos(abduction),-math.cos(shoulder)*math.cos(abduction))
    pole=(-sign*.10,1.,0.);dot=sum(a*b for a,b in zip(pole,upper))
    bend=tuple(a-dot*b for a,b in zip(pole,upper));length=math.sqrt(sum(v*v for v in bend));bend=tuple(v/length for v in bend)
    def direction(angle):return tuple(a*math.cos(angle)+b*math.sin(angle) for a,b in zip(upper,bend))
    wrist=math.radians(1.5+2.*math.sin(math.tau*phase-.5))
    return upper,direction(flex),direction(flex+wrist)


def torso_lean(phase):return math.radians(2.3+.20*math.sin(math.tau*2*phase-.3))
def torso_bank(phase):return math.radians(.65)*math.cos(math.tau*phase-.85)
def torso_twist(phase):return -math.radians(2.4)*math.cos(math.tau*phase)
