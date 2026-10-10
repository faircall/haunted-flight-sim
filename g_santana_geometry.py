"""Car-local anchors shared by Blender authoring and the rainy intro renderer."""
import math

AXLES=(-1.625,1.040)
REAR_BODY_END=1.755
TRUNK_START=1.274
CENTER_POST_Z=-.095
DOOR_CENTERS=(-.595,.565)
WHEEL_X=.764
WHEEL_Y=.320
TYRE_RADIUS=.315
ACTOR_SCALE=.88
FRONT_ACTOR_POSITION=(0,-.062,.060)
REAR_ACTOR_POSITION=(0,-.0312,-.100)
STEERING=(-.396,.849,-.776)
CABIN_EYE=(.02,1.235,.53)
WIPER_UP=(0,.6725,.7401)
WIPER_PIVOTS=(-.505,.155)
WIPER_Y=.995
WIPER_Z=-1.196
WIPER_INNER=.155
WIPER_OUTER=.56
WIPER_LENGTH=(WIPER_INNER+WIPER_OUTER)/2
WIPER_PARK=math.radians(5)
WIPER_SWEEP=math.radians(93)

# Landmarks measured on the side view in Classic Santana Vehicle Reference Sheet.png.
# Ratios use the bumper-to-bumper span, rather than a seated actor's size.
REFERENCE_SIDE=dict(length_px=467,wheelbase_px=295,roof_px=164,glass_height_px=47,
                    car_height_px=168,wheel_diameter_px=70,center_post_px=700,
                    front_axle_px=532,rear_axle_px=827)


def actor_point(point,rear=False):
    offset=REAR_ACTOR_POSITION if rear else FRONT_ACTOR_POSITION
    return tuple(v*ACTOR_SCALE+d for v,d in zip(point,offset))


def front_belt_path(sign):
    """One shoulder belt fitted outside the two ellipsoids of the seated actor."""
    def unfit(p):return tuple((v-d)/ACTOR_SCALE for v,d in zip(p,FRONT_ACTOR_POSITION))
    path=[unfit((sign*.692,1.218,CENTER_POST_Z-.005))]
    for i in range(10):
        t=i/9;x=sign*(.61-.30*t);y=1.245-.475*t;front=-.40
        for cy,cz,rx,ry,rz in ((1.04,-.35,.225,.29,.145),(.76,-.39,.225,.15,.18)):
            q=1-((x-sign*.45)/rx)**2-((y-cy)/ry)**2
            if q>=0:front=min(front,cz-rz*math.sqrt(q))
        path.append((x,y,front-.022))
    path.append(unfit((sign*.161,.613,-.348)))
    return path


def rear_belt_path(sign):
    """Unlatched shoulder webbing hangs on the visible face of the outer bolster."""
    return [(sign*x,y,z) for x,y,z in ((.664,1.170,.854),(.620,1.025,.791),
                                     (.611,.880,.750),(.635,.700,.691),(.667,.531,.663))]


def cabin_point(point,dash=False):
    """Fit existing trim into the independently proportioned body shell."""
    x,y,z=point
    keys=((-1.4,-1.12),(0.,.06),(.8,.58),(1.44,.86),(1.68,1.18))
    for (a,u),(b,v) in zip(keys,keys[1:]):
        if z<=b:
            z=u+(v-u)*(z-a)/(b-a);break
    else:z=1.18+(z-1.68)*.88
    return x*.88,y*.88+.026+(.10 if dash else 0),z


def window_panes():
    """Six real openings. Both .blend glazing and game rain use these points."""
    panes=[([(-.744,1.009,-1.179),(.744,1.009,-1.179),(.626,1.417,-.730),(-.626,1.417,-.730)],True)]
    for sign in (-1,1):
        front=[(sign*.819,1.010,-1.134),(sign*.819,1.010,CENTER_POST_Z-.072),
               (sign*.722,1.429,CENTER_POST_Z-.070),(sign*.670,1.419,-.710)]
        rear=[(sign*.819,1.010,CENTER_POST_Z+.062),(sign*.819,1.010,.955),
              (sign*.680,1.409,.665),(sign*.722,1.429,CENTER_POST_Z+.067)]
        panes.extend(((front,False),(rear,False)))
    panes.append(([(.750,1.023,1.264),(-.750,1.023,1.264),(-.625,1.409,.815),(.625,1.409,.815)],False))
    return panes


def roof_height(x,z):
    # Crown falls away toward the gutters and gently turns down at either end.
    crown=max(0.,1-(x/.742)**2)
    return 1.451+.055*crown-.027*((z-.08)/.78)**2


def roof_rim(u,t):
    """Roof edge follows the extended glass planes, with a small pressed gutter."""
    width=.668+.016*t+.044*math.sin(math.pi*t)-.032*t**8
    z=(-.678-.025*u*u)*(1-t)+(.770+.015*u*u)*t
    x=width*u
    return x,roof_height(x,z),z


def inside_cabin(eye):
    """Camera/editor classification follows the lowered roof and sloping glass."""
    x,y,z=eye
    width=.816-.097*max(0.,y-1.010)/.419
    front=-1.179+.449*max(0.,y-1.009)/.408
    rear=1.264-.449*max(0.,y-1.023)/.386
    return abs(x)<width and .215<y<roof_height(x,z)-.058 and front<z<rear


def wiper_pose(x,angle):
    tip=(x+WIPER_LENGTH*math.cos(angle),WIPER_Y+WIPER_LENGTH*math.sin(angle)*WIPER_UP[1],
         WIPER_Z+WIPER_LENGTH*math.sin(angle)*WIPER_UP[2])
    # Blade runs along the arm, not across it like a window-cleaning squeegee.
    half=(WIPER_OUTER-WIPER_INNER)/2
    transverse=(half*math.cos(angle),half*math.sin(angle)*WIPER_UP[1],half*math.sin(angle)*WIPER_UP[2])
    return (x,WIPER_Y,WIPER_Z),tip,transverse


def wiper_segments(x,angle):
    """Shared parked/swept assembly for Blender and both runtime car variants."""
    def p(radius,lift=0.,lateral=0.):
        return (x+radius*math.cos(angle)-lateral*math.sin(angle),
                WIPER_Y+(radius*math.sin(angle)+lateral*math.cos(angle))*WIPER_UP[1]+lift*WIPER_UP[2],
                WIPER_Z+(radius*math.sin(angle)+lateral*math.cos(angle))*WIPER_UP[2]-lift*WIPER_UP[1])
    return [(p(0,.015),p(.055,.015),.025,.018,'arm'),
            (p(.045,.023),p(.255,.023,-.021),.013,.009,'arm'),
            (p(.255,.023,-.021),p(WIPER_LENGTH,.017),.011,.008,'arm'),
            (p(WIPER_INNER,.004),p(WIPER_OUTER,.004),.012,.008,'rubber'),
            (p(.215,.015),p(.31,.024),.010,.009,'arm'),
            (p(.31,.024),p(.405,.024),.012,.012,'arm'),
            (p(.405,.024),p(.50,.015),.010,.009,'arm')]
