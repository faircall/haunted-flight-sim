"""Shared hillside, building pads and grove clearances for the arrival temple.

Coordinates are metres relative to the foot of the main stair. The architecture
rests on this relief; its courts are excavated into the hill, not tall boxes.
"""
import math
import random

# x, z, floor, width, depth, wall height, bays, double roof
WINGS = ((-48,-28,13.4,18,11,4.5,5,False),
         (-70,-45,19.0,17,12,5.2,3,True),
         (-89,-69,25.0,13,12,4.5,3,False),
         (47,-39,15.5,22,12,4.6,5,False),
         (71,-59,22.0,16,13,5.2,3,True),
         (89,-88,29.0,13,11,4.5,3,False))
GALLERIES=((-38,-29,12.0,13),(-59,-41,16.1,9),(38,-41,13.0,13),(61,-56,19.0,11))
# Broad courts are deliberately limited to the central axis. Outer buildings
# have individual pads surrounded by earth and trees.
PADS = ((0,-27,10.8,62,12),(0,-43,10.8,66,22),
        (0,-76,21.6,64,29),(0,-117,32.4,53,26)) + tuple(
        (x,z,y,w+3,d+3) for x,z,y,w,d,*_ in WINGS)+tuple(
        (x,z,y,w,3.2) for x,z,y,w in GALLERIES)

def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)

def axis_height(z):
    # Follow the three stair flights, including their level resting landings.
    points=((15,-.035),(8.41,-.06),(1.06,3.35),(-1.34,3.35),
            (-8.9,6.95),(-11.3,6.95),(-19.2,10.55),(-44,10.55),
            (-62,21.35),(-86.5,21.35),(-104,32.15),(-132,32.15),(-195,55))
    if z>=points[0][0]:return points[0][1]
    for (a,h),(b,k) in zip(points,points[1:]):
        if z>=b:return h+(k-h)*(a-z)/(a-b)
    return 55+(abs(z)-195)*.13

def mountain_height(x,z):
    """Uneven wooded shoulders wrap around shallow, cut-in building terraces."""
    forward=smooth((25-z)/35)
    shoulder=4.5+3.2*math.sin(x*.043+z*.032)+1.6*math.sin(z*.081-x*.037)
    shoulder+=7*math.exp(-((x+72)/38)**2-((z+64)/67)**2)
    shoulder+=5*math.exp(-((x-87)/42)**2-((z+92)/80)**2)
    raw=axis_height(z)+shoulder*smooth((abs(x)-7)/22)*forward
    for px,pz,y,w,d in PADS:
        distance=max(abs(x-px)-w/2,abs(z-pz)-d/2)
        amount=1-smooth((distance+.3)/7)
        raw=raw*(1-amount)+(y-.18)*amount
    inside=[y-.18 for px,pz,y,w,d in PADS if abs(x-px)<=w/2 and abs(z-pz)<=d/2]
    if inside:raw=inside[0]
    if abs(x)<6.1:raw=min(raw,axis_height(z))
    # A generous flat clearing and the first tread stay at the road datum.
    landing=(1-smooth((abs(x)-13)/13))*smooth((z-8)/7)
    return raw*(1-landing)-.035*landing

def mountain_weight(x,z):
    return smooth((z+225)/55)*(1-smooth((z-10)/35))*(1-smooth((abs(x)-98)/55))

def occupied(x,z,margin=3):
    if abs(x)<9+margin and -135<z<23:return True
    return any(abs(x-px)<w/2+margin and abs(z-pz)<d/2+margin for px,pz,y,w,d in PADS)

def grove():
    """Irregular groves leave the stair axis and architecture readable."""
    rng=random.Random(73419);points=[]
    for z in range(-192,34,9):
        for x in range(-133,134,9):
            xx=x+rng.uniform(-3.7,3.7);zz=z+rng.uniform(-3.7,3.7)
            if occupied(xx,zz,4.0) or (zz>8 and abs(xx)<24):continue
            if rng.random()<.20:continue
            if any(math.hypot(xx-a,zz-b)<6.5 for a,b,*_ in points):continue
            kind='lacebark_pine' if rng.random()<.16 else ('temple_cypress_a' if rng.random()<.5 else 'temple_cypress_b')
            points.append((xx,zz,kind,rng.uniform(.76,1.16),rng.random()*math.tau))
    # Old white-barked sentinels above the entrance, as at Fahai.
    points.extend((x,z,'lacebark_pine',1.12,1.1+x) for x,z in ((-37,-18),(36,-17)))
    return points
