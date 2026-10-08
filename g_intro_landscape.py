"""The fictional temple's lakeside approach; bounded, road-fixed placement."""
import math

LAKE_HEIGHT=-1.35
LAKE_EDGE=4.4
TREE_MODELS=('chinese_pine_a','chinese_pine_b','chinese_pine_c')
RIDGE_MODELS=('ridge_a','ridge_b','ridge_c')
STAIR_COUNT=17
STAIR_RISE=.18
BRIDGES=(315.,748.,1120.)
CHUNK_LENGTH=48


def road_x(station):
    return 22*math.sin(station/90)+11*math.sin(station/43+.5)


def road_slope(station):
    return 22/90*math.cos(station/90)+11/43*math.cos(station/43+.5)


def road_curve(station):
    return -22/90**2*math.sin(station/90)-11/43**2*math.sin(station/43+.5)


def world_point(station,side):
    slope=road_slope(station);normal=math.sqrt(1+slope*slope)
    return road_x(station)+side/normal,-station+side*slope/normal


def local_point(station,side,distance):
    yaw=-math.atan(road_slope(distance));x,z=world_point(station,side);dx=x-road_x(distance);z+=distance
    return dx*math.cos(yaw)-z*math.sin(yaw),dx*math.sin(yaw)+z*math.cos(yaw)


def road_yaw(station,distance):
    return math.degrees(-math.atan(road_slope(station))+math.atan(road_slope(distance)))


def scenery(distance):
    """Pines crowd the mountain bank; openings preserve views across the lake."""
    start=math.floor((distance-24)/8)
    for i in range(start,start+22):
        seed=(i*1836311903+2971215073)&0xffffffff
        for row in range(4):
            station=i*8+((seed>>(row*5))&15)/5
            # Sparse lakeside trees frame water instead of making a green wall.
            if row==3 and i%5:continue
            side=3.15 if row==3 else -(5.0+row*10+((seed>>7)&15)/5)
            if bridge_distance(station)<12:continue
            x,z=local_point(station,side,distance)
            if -150<z<25:
                yield dict(x=x,z=z,y=bank_height(station,side),
                           station=station,side=side,
                           scale=.88+((seed>>(row*6+9))&15)/30,
                           kind=TREE_MODELS[(seed+row)%3],yaw=(seed+row*77)%360,seed=seed)


def ridges(distance):
    """Three broad overlapping mountain ranges across the water and left bank."""
    for layer,(side,height,width,span) in enumerate(((-68,72,65,150),(180,96,105,200),(340,176,150,260))):
        first=math.floor(distance/span)-2
        for i in range(first,first+6):
            station=i*span
            x,z=local_point(station,side,distance)
            yield dict(kind=RIDGE_MODELS[(i+layer)%3],position=(x,LAKE_HEIGHT-3,z),
                       scale=(width,height*(.8+.15*((i+2*layer)%3)),span*.63),
                       yaw=math.degrees(math.atan(road_slope(distance))),layer=layer)


def last_electric_light(arrival_station):
    return arrival_station-210


def bridge_distance(station):return min(abs(station-b) for b in BRIDGES)


def bank_height(station,side):
    cross=((-96,31),(-62,24),(-40,15),(-22,8),(-12,3.7),(-7,1.1),(-4,.04),(-2,-.035),(2,-.035),(2.6,-.10),(3.4,-.48),(4.6,-1.65),(10,-2.4))
    for (a,y),(b,v) in zip(cross,cross[1:]):
        if side<=b:
            height=y+(v-y)*(side-a)/(b-a);break
    else:height=-2.4
    if side<-4:
        height+=min(1.,(-side-4)/10)*(.85*math.sin(station*.12+side*.2)+.4*math.cos(station*.29-side*.12))
    # Three tributary cuts descend from the hillside and open into the lake.
    t=max(0.,min(1.,(bridge_distance(station)-4.8)/2.4))
    stream=1-t*t*(3-2*t)
    if -35<side<10:
        weight=min(1.,(side+35)/15)
        height=height*(1-stream*weight)+(-1.72)*stream*weight
    return height
