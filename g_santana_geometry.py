"""Car-local anchors shared by Blender authoring and the rainy intro renderer."""
import math

AXLES=(-1.625,1.040)
REAR_BODY_END=1.840
TRUNK_START=1.294
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
WIPER_PIVOTS=(-.47,.235)
WIPER_Y=.995
WIPER_Z=-1.196
WIPER_LENGTH=.43

# Landmarks measured on the side view in Classic Santana Vehicle Reference Sheet.png.
# Ratios use the bumper-to-bumper span, rather than a seated actor's size.
REFERENCE_SIDE=dict(length_px=467,wheelbase_px=295,roof_px=164,glass_height_px=47,
                    car_height_px=168,wheel_diameter_px=70,center_post_px=700,
                    front_axle_px=532,rear_axle_px=827)


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
    panes=[([(-.744,1.009,-1.179),(.744,1.009,-1.179),(.626,1.417,-.730),(-.626,1.417,-.730)],True)]
    for sign in (-1,1):
        front=[(sign*.819,1.010,-1.164),(sign*.819,1.010,CENTER_POST_Z-.060),
               (sign*.722,1.429,CENTER_POST_Z-.058),(sign*.670,1.419,-.740)]
        rear=[(sign*.819,1.010,CENTER_POST_Z+.051),(sign*.819,1.010,.990),
              (sign*.680,1.409,.710),(sign*.722,1.429,CENTER_POST_Z+.056)]
        panes.extend(((front,False),(rear,False)))
    panes.append(([(.750,1.023,1.284),(-.750,1.023,1.284),(-.625,1.409,.860),(.625,1.409,.860)],False))
    return panes


def roof_height(x,z):
    # Crown falls away toward the gutters and gently turns down at either end.
    crown=max(0.,1-(x/.742)**2)
    return 1.451+.055*crown-.027*((z-.08)/.78)**2


def roof_rim(u,t):
    """Roof edge follows the extended glass planes, with a small pressed gutter."""
    width=.668+.016*t+.044*math.sin(math.pi*t)
    z=(-.678-.025*u*u)*(1-t)+(.815+.015*u*u)*t
    x=width*u
    return x,roof_height(x,z),z


def inside_cabin(eye):
    """Camera/editor classification follows the lowered roof and sloping glass."""
    x,y,z=eye
    width=.816-.097*max(0.,y-1.010)/.419
    front=-1.179+.449*max(0.,y-1.009)/.408
    rear=1.284-.424*max(0.,y-1.023)/.386
    return abs(x)<width and .215<y<roof_height(x,z)-.058 and front<z<rear


def wiper_pose(x,angle):
    tip=(x+WIPER_LENGTH*math.cos(angle),WIPER_Y+WIPER_LENGTH*math.sin(angle)*WIPER_UP[1],
         WIPER_Z+WIPER_LENGTH*math.sin(angle)*WIPER_UP[2])
    transverse=(-.13*math.sin(angle),.13*math.cos(angle)*WIPER_UP[1],.13*math.cos(angle)*WIPER_UP[2])
    return (x,WIPER_Y,WIPER_Z),tip,transverse
