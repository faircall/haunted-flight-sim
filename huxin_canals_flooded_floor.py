"""Convex floor pieces around the unchanged hexagonal pavilion platform."""
import math
from g_huxin_canals_flooded import PLATFORM_RADIUS

def split_polygon(poly,normal,offset):
    inside=[];outside=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=sum(a[i]*normal[i] for i in range(2))-offset
        db=sum(b[i]*normal[i] for i in range(2))-offset
        (inside if da<=0 else outside).append(a)
        if (da<0<db) or (db<0<da):
            t=da/(da-db);p=tuple(a[i]+(b[i]-a[i])*t for i in range(2))
            inside.append(p);outside.append(p)
    return inside,outside

def outside_core(poly):
    """Partition a convex polygon minus the hexagon into non-overlapping pieces."""
    remaining=list(poly);pieces=[]
    for i in range(6):
        if len(remaining)<3:break
        angle=(i+.5)*math.tau/6
        remaining,outer=split_polygon(remaining,(math.cos(angle),math.sin(angle)),PLATFORM_RADIUS*math.cos(math.pi/6))
        if len(outer)>=3:pieces.append(outer)
    return pieces
