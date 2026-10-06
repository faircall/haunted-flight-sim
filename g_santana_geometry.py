"""Car-local anchors shared by Blender authoring and the rainy intro renderer."""
import math

AXLES=(-1.625,1.220)
WHEEL_X=.764
WHEEL_Y=.355
TYRE_RADIUS=.35
ACTOR_SCALE=.88
FRONT_ACTOR_POSITION=(0,-.062,.060)
REAR_ACTOR_POSITION=(0,-.0312,-.100)
STEERING=(-.396,.849,-.776)
CABIN_EYE=(.02,1.235,.53)
WIPER_UP=(0,.6295,.7770)
WIPER_PIVOTS=(-.47,.235)
WIPER_Y=.995
WIPER_Z=-1.096
WIPER_LENGTH=.43

# Landmarks measured on the large side view in car_reference_2.png.
# Ratios use the bumper-to-bumper span, rather than a seated actor's size.
REFERENCE_SIDE=dict(length_px=682,wheelbase_px=434,roof_px=218,glass_height_px=70,
                    car_height_px=236)


def actor_point(point,rear=False):
    offset=REAR_ACTOR_POSITION if rear else FRONT_ACTOR_POSITION
    return tuple(v*ACTOR_SCALE+d for v,d in zip(point,offset))


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
    panes=[([(-.744,1.009,-1.079),(.744,1.009,-1.079),(.645,1.405,-.590),(-.645,1.405,-.590)],True)]
    for sign in (-1,1):
        front=[(sign*.819,1.010,-1.064),(sign*.819,1.010,.015),
               (sign*.754,1.409,.017),(sign*.691,1.399,-.604)]
        rear=[(sign*.819,1.010,.126),(sign*.819,1.010,1.127),
              (sign*.699,1.389,.751),(sign*.754,1.409,.131)]
        panes.extend(((front,False),(rear,False)))
    panes.append(([(.750,1.023,1.184),(-.750,1.023,1.184),(-.645,1.388,.781),(.645,1.388,.781)],False))
    return panes


def roof_height(x,z):
    # Crown falls away toward the gutters and gently turns down at either end.
    crown=max(0.,1-(x/.775)**2)
    return 1.447+.047*crown-.020*((z-.08)/.78)**2


def inside_cabin(eye):
    """Camera/editor classification follows the lowered roof and sloping glass."""
    x,y,z=eye
    width=.816-.065*max(0.,y-1.010)/.399
    front=-1.079+.489*max(0.,y-1.009)/.396
    rear=1.184-.403*max(0.,y-1.023)/.365
    return abs(x)<width and .215<y<roof_height(x,z)-.058 and front<z<rear


def wiper_pose(x,angle):
    tip=(x+WIPER_LENGTH*math.cos(angle),WIPER_Y+WIPER_LENGTH*math.sin(angle)*WIPER_UP[1],
         WIPER_Z+WIPER_LENGTH*math.sin(angle)*WIPER_UP[2])
    transverse=(-.13*math.sin(angle),.13*math.cos(angle)*WIPER_UP[1],.13*math.cos(angle)*WIPER_UP[2])
    return (x,WIPER_Y,WIPER_Z),tip,transverse
