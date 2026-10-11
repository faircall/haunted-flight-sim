"""The fictional temple's lakeside approach; bounded, road-fixed placement."""
import math
from functools import lru_cache
from g_intro_temple_layout import mountain_height,mountain_weight

LAKE_HEIGHT=-1.35
LAKE_EDGE=4.4
TREE_MODELS=('chinese_pine_a','chinese_pine_b','chinese_pine_c')
MOUNTAIN_TREES=('temple_cypress_a','temple_cypress_b','lacebark_pine')
RIDGE_MODELS=('ridge_a','ridge_b','ridge_c')
STAIR_COUNT=54
STAIR_RISE=.20
STAIR_TREAD=.42
STAIR_START=8.2
STAIR_FLIGHT=18
STAIR_LANDING=2.4
BRIDGES=(315.,748.,1120.)
CHUNK_LENGTH=48
DEFAULT_ARRIVAL=1485.75
POLE_SPACING=36
POLE_SIDE=-19.
DRAW_BEHIND=288
DRAW_AHEAD=288
BRIDGE_HALF=12
RIVER_UPSTREAM=-520
RIVER_DOWNSTREAM=80


def junction_station(arrival=DEFAULT_ARRIVAL):return arrival-255


def stair_z(step):return STAIR_START-step*STAIR_TREAD-(step//STAIR_FLIGHT)*STAIR_LANDING


def clearing_amount(station,side,arrival=DEFAULT_ARRIVAL):
    # Broad oval turning court below the first stair; no tarmac runs into the gate.
    radius=math.sqrt(((station-(arrival-20))/24)**2+(side/18)**2)
    return 1-smooth((radius-.78)/.30)


def temple_ground(station,side,arrival=DEFAULT_ARRIVAL):
    x,z=local_world_point(*world_point(station,side,arrival),arrival,arrival)
    return (-205<z<38 and abs(x)<142) or clearing_amount(station,side,arrival)>.02


def trail_fraction(station,arrival=DEFAULT_ARRIVAL):return smooth((station-junction_station(arrival))/28)


def main_road_x(station):return 22*math.sin(station/90)+11*math.sin(station/43+.5)


def main_road_slope(station):return 22/90*math.cos(station/90)+11/43*math.cos(station/43+.5)


def main_road_height(station):
    rolling=2.5+1.55*math.sin(station/83-.8)+.85*math.sin(station/39+.4)
    return .55+(rolling-.55)*smooth((bridge_distance(station)-BRIDGE_HALF-2)/65)


def branch_offset(station,arrival=DEFAULT_ARRIVAL,derivative=0):
    t=max(0.,min(1.,(station-junction_station(arrival))/110))
    if derivative==1:return -150*30*t*t*(1-t)**2/110
    if derivative==2:return -150*60*t*(1-t)*(1-2*t)/110**2
    return -150*t**3*(10-15*t+6*t*t)


def smooth(value):
    t=max(0.,min(1.,value));return t*t*(3-2*t)


def _raw_road_height(station,arrival=DEFAULT_ARRIVAL):
    """Low lakeside crests, level bridge decks, then a sustained temple climb."""
    rolling=main_road_height(station);junction=junction_station(arrival)
    offset=-branch_offset(station,arrival);entry=main_road_height(junction)
    # Stay level through the turn, then climb through the forest in a long grade.
    progress=smooth((station-(junction+36))/180)
    trail=entry+(21-entry)*progress
    departure=smooth((offset-3)/8)
    return rolling*(1-departure)+trail*departure


@lru_cache(maxsize=8)
def departure_profile(arrival):
    a=junction_station(arrival)+4;b=a+76
    slope=lambda s:(_raw_road_height(s+.1,arrival)-_raw_road_height(s-.1,arrival))/.2
    return _raw_road_height(a,arrival),_raw_road_height(b,arrival),slope(a),slope(b)


def road_height(station,arrival=DEFAULT_ARRIVAL):
    """Match value and grade over the fork's vertical transition, with no kicker."""
    t=(station-junction_station(arrival)-4)/76
    if not 0<t<1:return _raw_road_height(station,arrival)
    a,b,ma,mb=departure_profile(arrival)
    return a*(2*t**3-3*t*t+1)+76*ma*(t**3-2*t*t+t)+b*(-2*t**3+3*t*t)+76*mb*(t**3-t*t)


def car_pose(distance,arrival=DEFAULT_ARRIVAL):
    # The wheelbase samples the road, so all four tyres stay planted on crests.
    metric=math.sqrt(1+road_slope(distance,arrival)**2)
    front=road_height(distance+1.625/metric,arrival)
    rear=road_height(distance-1.040/metric,arrival)
    pitch=math.atan2(front-rear,2.665)
    height=(front*1.040+rear*1.625)/2.665
    return height,pitch


def car_point(point,height,pitch,vector=False):
    x,y,z=point;c,s=math.cos(pitch),math.sin(pitch)
    return x,y*c-z*s+(0 if vector else height),y*s+z*c


def road_x(station,arrival=DEFAULT_ARRIVAL):
    return main_road_x(station)+branch_offset(station,arrival)


def road_slope(station,arrival=DEFAULT_ARRIVAL):
    return main_road_slope(station)+branch_offset(station,arrival,1)


def road_curve(station,arrival=DEFAULT_ARRIVAL):
    return -22/90**2*math.sin(station/90)-11/43**2*math.sin(station/43+.5)+branch_offset(station,arrival,2)


def world_point(station,side,arrival=DEFAULT_ARRIVAL,main=False):
    slope=main_road_slope(station) if main else road_slope(station,arrival);normal=math.sqrt(1+slope*slope)
    x=main_road_x(station) if main else road_x(station,arrival)
    return x+side/normal,-station+side*slope/normal


def local_point(station,side,distance,arrival=DEFAULT_ARRIVAL):
    return local_world_point(*world_point(station,side,arrival),distance,arrival)


def terrain_point(station,side,arrival=DEFAULT_ARRIVAL):
    # Parallel world-space sections cannot fold at an inside road bend. The road
    # itself still uses normals for constant width; the ground is a heightfield.
    return road_x(station,arrival)+side,-station


def local_world_point(x,z,distance,arrival=DEFAULT_ARRIVAL):
    yaw=-math.atan(road_slope(distance,arrival));dx=x-road_x(distance,arrival);z+=distance
    return dx*math.cos(yaw)-z*math.sin(yaw),dx*math.sin(yaw)+z*math.cos(yaw)


def road_yaw(station,distance,arrival=DEFAULT_ARRIVAL):
    return math.degrees(-math.atan(road_slope(station,arrival))+math.atan(road_slope(distance,arrival)))


def scenery(distance,arrival=DEFAULT_ARRIVAL):
    """Pines crowd the mountain bank; openings preserve views across the lake."""
    for item in trees_between(distance-DRAW_BEHIND,distance+DRAW_AHEAD,arrival):
        x,z=local_point(item['station'],item['side'],distance,arrival)
        if -DRAW_AHEAD-60<z<DRAW_BEHIND+60:yield dict(item,x=x,z=z)


def trees_between(start,end,arrival=DEFAULT_ARRIVAL):
    for i in range(math.floor(start/8)-1,math.ceil(end/8)+1):
        seed=(i*1836311903+2971215073)&0xffffffff
        for row in range(4):
            station=i*8+((seed>>(row*5))&15)/5
            if not start<=station<end:continue
            # Sparse lakeside trees frame water instead of making a green wall.
            trail=trail_fraction(station,arrival)>.5
            if row==3 and i%5 and not trail:continue
            side=(4.8+(seed%17)/6 if trail else 3.15) if row==3 else -(5.0+row*10+((seed>>7)&15)/5)
            if bridge_distance(station)<BRIDGE_HALF+5 or temple_ground(station,side,arrival):continue
            yield dict(y=ground_height(*world_point(station,side,arrival),arrival),
                           station=station,side=side,
                           scale=.88+((seed>>(row*6+9))&15)/30,
                           kind=(MOUNTAIN_TREES if trail else TREE_MODELS)[(seed+row)%3],yaw=(seed+row*77)%360,seed=seed)


def ridges(distance,arrival=DEFAULT_ARRIVAL):
    """Three broad overlapping mountain ranges across the water and left bank."""
    # World-aligned ranges clear the entire +/-33m winding-road envelope.
    # Offsetting just one road normal lets long ridge bases cross other bends.
    for layer,(side,height,width,span) in enumerate(((-330,154,85,150),(180,96,105,200),(340,176,150,260))):
        first=math.floor(distance/span)-2
        for i in range(first,first+6):
            station=i*span
            x,z=local_world_point(side,-station,distance,arrival)
            yield dict(kind=RIDGE_MODELS[(i+layer)%3],position=(x,LAKE_HEIGHT-3,z),
                       scale=(width,height*(.8+.15*((i+2*layer)%3)),span*.63),
                       yaw=math.degrees(math.atan(road_slope(distance,arrival))),layer=layer)


def last_electric_light(arrival_station):
    return arrival_station-210


def bridge_distance(station):return min(abs(station-b) for b in BRIDGES)


def shore_distance(station):return 16+4*math.sin(station/53)+3*math.sin(station/21+.8)+2*math.cos(station/107)


def river_station(bridge,side):return bridge+3*math.sin(side/19)+.028*side


def river_height(side):return LAKE_HEIGHT+.025+max(0.,-side-4)*.036


def river_half_width(side):return 7.4+1.3*math.sin(side/27+.3)


def main_coordinates(x,z):
    # Newton projection is reliable close to the road, but can jump to a remote
    # bend when a hillside lies hundreds of metres away. Use a smooth vertical
    # projection out there; only the nearby carriageway needs exact normals.
    seed=-z;station=seed;horizontal=x-main_road_x(seed)
    far_side=horizontal/math.sqrt(1+main_road_slope(seed)**2)
    blend=smooth((abs(horizontal)-24)/24)
    if blend==1:return seed,far_side
    for _ in range(7):
        slope=main_road_slope(station);curve=-22/90**2*math.sin(station/90)-11/43**2*math.sin(station/43+.5)
        step=(slope*(main_road_x(station)-x)+station+z)/max(.25,1+slope*slope+curve*(main_road_x(station)-x))
        station-=max(-8.,min(8.,step))
    slope=main_road_slope(station)
    side=((x-main_road_x(station))+slope*(z+station))/math.sqrt(1+slope*slope)
    return station*(1-blend)+seed*blend,side*(1-blend)+far_side*blend


def main_bank_height(station,side):
    road=main_road_height(station);edge=shore_distance(station)
    if side>=2:
        t=smooth((side-3)/(edge-3))
        height=(road-.035)*(1-t)+LAKE_HEIGHT*t
        height-=.8*smooth((side-edge)/8)
        height+=.20*math.sin(station*.16+side*.8)*math.sin(station*.061-side*.4)*smooth((side-4)/4)*(1-smooth((side-edge+1)/3))
    else:
        cross=((-200,48),(-110,27),(-62,15.5),(-40,10.5),(-22,6),(-12,3.1),(-7,1.1),(-4,.04),(-2,-.035),(2,-.035))
        for (a,y),(b,v) in zip(cross,cross[1:]):
            if side<=b:height=road+y+(v-y)*(side-a)/(b-a);break
        if side<-4:height+=min(1.,(-side-4)/10)*(.85*math.sin(station*.12+side*.2)+.4*math.cos(station*.29-side*.12))
    # A meandering, visibly broad river bed connects mountain gullies to the lake.
    for bridge in BRIDGES:
        channel=1-smooth((abs(station-river_station(bridge,side))-river_half_width(side))/(3.4+max(0.,-side-6)*.28))
        if channel:height=height*(1-channel)+(river_height(side)-.65)*channel
    return height


def route_coordinates(x,z,arrival=DEFAULT_ARRIVAL):
    station=-z
    for _ in range(9):
        slope=road_slope(station,arrival);dx=road_x(station,arrival)-x
        step=(slope*dx+station+z)/max(.7,1+slope*slope+road_curve(station,arrival)*dx)
        station-=max(-7.,min(7.,step))
    slope=road_slope(station,arrival)
    return station,((x-road_x(station,arrival))+slope*(z+station))/math.sqrt(1+slope*slope)


@lru_cache(maxsize=240000)
def ground_height(x,z,arrival=DEFAULT_ARRIVAL):
    main_s,main_side=main_coordinates(x,z)
    height=main_bank_height(main_s,main_side)
    # The rivers are world-space ribbons. Far from the road the approximate
    # valley projection must not shift their carved bed away from that ribbon.
    for bridge in BRIDGES:
        if abs(main_s-bridge)>80:continue
        _,cz=world_point(river_station(bridge,main_side),main_side,main=True)
        channel=1-smooth((abs(z-cz)-river_half_width(main_side))/(3.4+max(0.,-main_side-6)*.28))
        if channel:height=min(height,height*(1-channel)+(river_height(main_side)-.65)*channel)
    if -z>junction_station(arrival)-12:
        tx,tz=local_world_point(x,z,arrival,arrival)
        mountain=mountain_weight(tx,tz)*smooth((abs(main_side)-4)/25)
        if mountain:height=height*(1-mountain)+(21+mountain_height(tx,tz))*mountain
        # Broad, varying verges ease into rounded banks. Restrict projection to
        # the road's vicinity; distant ground never projects onto another bend.
        horizontal=abs(x-road_x(-z,arrival))
        if horizontal<110 and -z<arrival+5:
            station,side=route_coordinates(x,z,arrival)
            width=(44 if side<0 else 80)+7*math.sin(station*.046)+4*math.cos(station*.091)
            cut=1-smooth((abs(side)-3.2)/width)
            cut*=smooth((abs(main_side)-2.2)/1.2)*(1-smooth((station-arrival+28)/28))
            verge=max(0.,abs(side)-3.2)
            contour=verge*(.12 if side<0 else -.045)+.55*math.sin(station*.12+side*.08)*smooth(verge/9)
            height=height*(1-cut)+(road_height(station,arrival)-.09+contour)*cut
        clearing=(1-smooth((abs(tx)-14)/12))*smooth((tz-8)/8)*(1-smooth((tz-43)/14))
        height=height*(1-clearing)+(21-.035)*clearing
    return height


def bank_height(station,side,arrival=DEFAULT_ARRIVAL):
    return ground_height(*terrain_point(station,side,arrival),arrival)


def main_side_on_section(station,side,arrival=DEFAULT_ARRIVAL):
    """Locate the continuing public road within a dirt-route terrain cross-section."""
    result=side-branch_offset(station,arrival)
    for _ in range(6):
        value=main_coordinates(*terrain_point(station,result,arrival))[1]
        derivative=(main_coordinates(*terrain_point(station,result+.02,arrival))[1]-value)/.02
        result-=(value-side)/max(.25,derivative)
    return result


def power_station(station):
    for bridge in BRIDGES:
        center=river_station(bridge,POLE_SIDE);clear=river_half_width(POLE_SIDE)+3.4+max(0.,-POLE_SIDE-6)*.28+2
        if abs(station-center)<clear:return center+math.copysign(clear,station-center)
    return station


def power_pole(station,arrival=DEFAULT_ARRIVAL):
    station=power_station(station)
    x,z=world_point(station,POLE_SIDE,main=True)
    return x,main_bank_height(station,POLE_SIDE),z


def power_wire(station,conductor,arrival=DEFAULT_ARRIVAL):
    a=power_pole(station,arrival);b=power_pole(station+POLE_SPACING,arrival)
    points=[]
    for i in range(13):
        t=i/12
        points.append((a[0]*(1-t)+b[0]*t+conductor*.48,
                       a[1]*(1-t)+b[1]*t+6.1-4*.65*t*(1-t),a[2]*(1-t)+b[2]*t))
    return points
