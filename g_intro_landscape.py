"""The fictional temple's lakeside approach; bounded, road-fixed placement."""
import math

LAKE_HEIGHT=-1.35
LAKE_EDGE=4.4
TREE_MODELS=('chinese_pine_a','chinese_pine_b','chinese_pine_c')
RIDGE_MODELS=('ridge_a','ridge_b','ridge_c')
STAIR_COUNT=17
STAIR_RISE=.18


def road_x(station):
    return 7.5*math.sin(station/120)+2.1*math.sin(station/53)


def road_slope(station):
    return 7.5/120*math.cos(station/120)+2.1/53*math.cos(station/53)


def local_point(station,side,distance):
    yaw=-math.atan(road_slope(distance));dx=road_x(station)+side-road_x(distance);z=distance-station
    return dx*math.cos(yaw)-z*math.sin(yaw),dx*math.sin(yaw)+z*math.cos(yaw)


def road_yaw(station,distance):
    return math.degrees(-math.atan(road_slope(station))+math.atan(road_slope(distance)))


def scenery(distance):
    """Pines crowd the mountain bank; openings preserve views across the lake."""
    start=math.floor((distance-22)/8)
    for i in range(start,start+16):
        seed=(i*1836311903+2971215073)&0xffffffff
        for row in range(3):
            station=i*8+((seed>>(row*5))&15)/5
            # Sparse lakeside trees frame water instead of making a green wall.
            if row==2 and i%4:continue
            side=3.05 if row==2 else -(4.3+row*7+((seed>>7)&15)/8)
            x,z=local_point(station,side,distance)
            if -93<z<21:
                yield dict(x=x,z=z,y=(-.23 if row==2 else 3.6 if row==1 else 0),
                           station=station,side=side,
                           scale=.88+((seed>>(row*6+9))&15)/38,
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
                       yaw=0,layer=layer)


def last_electric_light(arrival_station):
    return arrival_station-210
