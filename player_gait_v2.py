"""Alternative human locomotion for the existing 15-bone player rig.

Coordinates for this module are lateral / forward / up in model units; Blender
is lateral / -forward / up. The game advances phases by actual travel, so the
stance foot uses exactly its existing distance per cycle. No original clip or
asset is modified: apply_actions() is called only in the candidate build.
"""
import math

THIGH=5.8
SHIN=5.8
ANKLE=.9
HEEL=-1.1
TOE=2.2
HIP_HALF_WIDTH=1.30
SHOULDER_HALF_WIDTH=2.6
SHOULDER_HEIGHT=19.45
TORSO=8.3
UPPER_ARM=4.5
FOREARM=3.8
HAND=1.5
PLAYER_HEIGHT=25.65
WALK_STRIDE=(4.6+5.4)/.56
RUN_STRIDE=(5.4+6.6)/.34
SETTINGS={
    'walk':dict(stance=.56,front=4.6,back=5.4,lift=1.05,heel=10.,toe=27.,stride=WALK_STRIDE),
    'walk_back':dict(stance=.56,front=4.6,back=5.4,lift=.85,heel=8.,toe=22.,stride=WALK_STRIDE),
    'run':dict(stance=.34,front=5.4,back=6.6,lift=2.5,heel=9.,toe=30.,stride=RUN_STRIDE),
}


def smooth(t):
    t=max(0.,min(1.,t))
    return t*t*(3.-2.*t)


def hermite(a,b,va,vb,t,span):
    return (a*(2*t**3-3*t*t+1)+va*span*(t**3-2*t*t+t)
            +b*(-2*t**3+3*t*t)+vb*span*(t**3-t*t))


def foot(clip,phase):
    """Independent planted heel/toe, smooth toe-off, recovery and landing."""
    if clip=='idle':return dict(forward=0.,height=ANKLE,pitch=0.,clearance=0.,stance=True)
    cfg=SETTINGS[clip];p=phase%1.;stance=cfg['stance'];reverse=clip=='walk_back'
    direction=-1. if reverse else 1.
    landing=math.radians(cfg['heel'])*direction
    takeoff=-math.radians(cfg['toe'])*direction
    if p<stance:
        t=p/stance
        pitch=landing*(1.-smooth(t/.22)) + takeoff*smooth((t-.68)/.32)
        anchor=direction*(cfg['front']-cfg['stride']*p)
        contact=HEEL if pitch>=0 else TOE
        forward=anchor+contact-(contact*math.cos(pitch)+ANKLE*math.sin(pitch))
        clearance=0.
    else:
        t=(p-stance)/(1.-stance)
        pitch=takeoff*(1.-smooth(t/.43))+landing*smooth((t-.72)/.28)
        # Match the ankle velocity at both takeoff and contact. This avoids the
        # hovering/reversal caused by an eased, stationary airborne endpoint.
        release_contact=HEEL if takeoff>=0 else TOE
        land_contact=HEEL if landing>=0 else TOE
        start=direction*(-cfg['back'])+release_contact-(release_contact*math.cos(takeoff)+ANKLE*math.sin(takeoff))
        end=direction*cfg['front']+land_contact-(land_contact*math.cos(landing)+ANKLE*math.sin(landing))
        forward=hermite(start,end,-direction*cfg['stride'],-direction*cfg['stride'],t,1.-stance)
        if clip=='run':
            # A quick but eased recovery prevents the trailing shoe dragging
            # the hips down. Keep the maximum much lower than the old high
            # heel kick, and ease gently back into the contact.
            envelope=min(smooth(t/.14),smooth((1.-t)/.14))
            clearance=cfg['lift']*envelope*(.65+.35*math.sin(math.pi*t))
        else:clearance=cfg['lift']*math.sin(math.pi*t)**2
    contact=HEEL if pitch>=0 else TOE
    height=clearance+ANKLE*math.cos(pitch)-contact*math.sin(pitch)
    return dict(forward=forward,height=height,pitch=pitch,clearance=clearance,stance=p<stance)


def foot_lateral(clip,sign,phase):
    if clip=='idle':return sign*HIP_HALF_WIDTH
    p=phase%1.;stance=SETTINGS[clip]['stance'];s=(p-stance)/(1.-stance) if p>=stance else 0.
    track=1.16 if clip=='run' else 1.30
    return sign*(track+(.07 if clip=='run' else .12)*math.sin(math.pi*s)**2)


def pelvis(clip,phase):
    if clip=='idle':return dict(lateral=.025*math.sin(math.tau*phase),forward=0.,yaw=0.,roll=0.,pitch=0.)
    angle=math.tau*phase
    amplitude=.24 if clip=='run' else .28
    return dict(lateral=-amplitude*math.cos(angle-.70),forward=0.,
                yaw=math.radians(-3.0 if clip=='run' else -2.2)*math.cos(angle),
                roll=math.radians(-1.1)*math.cos(angle-.70),
                pitch=math.radians(1.5 if clip=='run' else .5))


def _hip_offset(motion,sign):
    # Pelvis rotates gently without forcing the shoes to slide sideways.
    x,y,z=motion['roll'],motion['pitch'],motion['yaw']
    return (sign*HIP_HALF_WIDTH*math.cos(z)*math.cos(x),
            sign*HIP_HALF_WIDTH*math.sin(z),
            sign*HIP_HALF_WIDTH*math.sin(x))


def hip_height(clip,phase):
    if clip=='idle':return 12.26+.035*math.sin(math.tau*phase)
    motion=pelvis(clip,phase)
    if clip=='run':preferred=11.88-.24*math.cos(math.tau*2*phase)
    else:preferred=12.12-.17*math.cos(math.tau*2*phase)
    ceilings=[]
    for side,sign in ((0.,-1),(.5,1)):
        f=foot(clip,phase+side);offset=_hip_offset(motion,sign)
        dx=foot_lateral(clip,sign,phase+side)-motion['lateral']-offset[0]
        df=f['forward']-motion['forward']-offset[1]
        reach=THIGH+SHIN-.12
        radial=max(.01,reach*reach-dx*dx-df*df)
        ceilings.append(f['height']-offset[2]+math.sqrt(radial))
    # A smooth minimum prevents a seam as support transfers to the other leg.
    def soft(a,b,width=.08):
        q=max(0.,width-abs(a-b))/width
        return min(a,b)-width*q*q*.25
    return soft(preferred,soft(*ceilings))


def leg(clip,phase,side=0.):
    motion=pelvis(clip,phase);sign=-1 if side==0. else 1
    target=foot(clip,phase+side);offset=_hip_offset(motion,sign)
    hip=(motion['lateral']+offset[0],motion['forward']+offset[1],hip_height(clip,phase)+offset[2])
    ankle=(foot_lateral(clip,sign,phase+side),target['forward'],target['height'])
    delta=tuple(a-b for a,b in zip(ankle,hip));distance=math.sqrt(sum(v*v for v in delta))
    if not abs(THIGH-SHIN)<distance<THIGH+SHIN:
        raise ValueError(f'Ankle out of reach: {clip} phase={phase:.5f} side={side} distance={distance:.5f}')
    axis=tuple(v/distance for v in delta);pole=(sign*.025,1.,0.)
    dot=sum(a*b for a,b in zip(pole,axis));bend=tuple(a-dot*b for a,b in zip(pole,axis))
    length=math.sqrt(sum(v*v for v in bend));bend=tuple(v/length for v in bend)
    along=(THIGH*THIGH-SHIN*SHIN+distance*distance)/(2*distance)
    lift=math.sqrt(max(0.,THIGH*THIGH-along*along))
    knee=tuple(a+along*b+lift*c for a,b,c in zip(hip,axis,bend))
    return dict(hip=hip,knee=knee,ankle=ankle,**target)


def arms(clip,phase,sign):
    """Relaxed counter-swing with a consistently bent, pumping running elbow."""
    wave=math.cos(math.tau*phase)
    if clip=='idle':swing=-2.+1.0*math.sin(math.tau*phase);elbow=11.;abduction=4.
    elif clip=='run':
        swing=-3.-36.*wave
        # The elbow opens behind the hip, folds as the arm comes forward,
        # and stays folded longer on the return. A small phase lag makes the
        # two passing arms different rather than matching flat at the waist.
        elbow=70.-38.*math.cos(math.tau*(phase-.10))
        abduction=8.5+1.5*wave
    else:
        swing=-2.-16.*wave
        if clip=='walk_back':swing=-2.+13.*wave
        elbow=20.-4.*wave;abduction=6.
    shoulder,elbow,abduction=map(math.radians,(swing,elbow,abduction))
    upper=(sign*math.sin(abduction),math.sin(shoulder)*math.cos(abduction),-math.cos(shoulder)*math.cos(abduction))
    # Bend the forearm principally forward, with mild lateral clearance.
    pole=(sign*.06,1.,0.);dot=sum(a*b for a,b in zip(pole,upper))
    plane=tuple(a-dot*b for a,b in zip(pole,upper));length=math.sqrt(sum(v*v for v in plane));plane=tuple(v/length for v in plane)
    lower=tuple(a*math.cos(elbow)+b*math.sin(elbow) for a,b in zip(upper,plane))
    wrist=math.radians((8. if clip=='run' else 0.)+3.*math.sin(math.tau*phase-.5))
    palm=tuple(a*math.cos(elbow+wrist)+b*math.sin(elbow+wrist) for a,b in zip(upper,plane))
    return upper,lower,palm


def _world(point):
    from mathutils import Vector
    return Vector((point[0],-point[1],point[2]))


def _posed_bone(rig,name,head,tail,poses,twist=0.):
    """Convert absolute joint targets to the armature's existing local basis."""
    from mathutils import Matrix,Quaternion,Vector
    bone=rig.pose.bones[name];rest=bone.bone.matrix_local
    direction=(Vector(tail)-Vector(head)).normalized()
    rest_direction=(bone.bone.tail_local-bone.bone.head_local).normalized()
    rotation=Quaternion(direction,twist) @ rest_direction.rotation_difference(direction) @ rest.to_quaternion()
    desired=Matrix.LocRotScale(Vector(head),rotation,Vector((1,1,1)))
    basis=rest.inverted()
    if bone.parent:basis=basis @ bone.parent.bone.matrix_local @ poses[bone.parent.name].inverted()
    bone.rotation_mode='QUATERNION';bone.matrix_basis=basis @ desired
    poses[name]=desired


def _body(rig,clip,phase):
    from mathutils import Vector
    m=pelvis(clip,phase);hip=_world((m['lateral'],m['forward'],hip_height(clip,phase)))
    up=Vector((-math.sin(m['roll']),-math.sin(m['pitch']),math.cos(m['pitch'])*math.cos(m['roll'])))
    poses={};_posed_bone(rig,'root',hip,hip+2*up,poses,-m['yaw'])
    lean=math.radians((3.5 if clip=='run' else .8 if clip in ('walk','walk_back') else .2))
    if clip=='idle':lean*=math.sin(math.tau*phase)
    bank=math.radians((.8 if clip=='run' else .55 if clip!='idle' else .12)*math.cos(math.tau*phase-.7))
    neck=hip+TORSO*Vector((math.sin(bank),-math.sin(lean)*math.cos(bank),math.cos(lean)*math.cos(bank)))
    twist=-math.radians(2.7 if clip=='run' else 1.8 if clip!='idle' else .3)*math.cos(math.tau*phase)
    _posed_bone(rig,'spine',hip,neck,poses,twist)
    _posed_bone(rig,'head',neck,neck+Vector((0,0,PLAYER_HEIGHT-(1+THIGH+SHIN+TORSO))),poses)
    spine_transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    return hip,poses,spine_transform


def _locomotion(rig,clip,phase):
    from mathutils import Vector
    hip,poses,transform=_body(rig,clip,phase)
    for side,suffix,sign in ((0.,'L',-1),(.5,'R',1)):
        target=leg(clip,phase,side)
        h,k,a=(_world(target[key]) for key in ('hip','knee','ankle'))
        _posed_bone(rig,'thigh.'+suffix,h,k,poses)
        _posed_bone(rig,'shin.'+suffix,k,a,poses)
        toe=a+Vector((0,-1.5*math.cos(target['pitch']),1.5*math.sin(target['pitch'])))
        _posed_bone(rig,'foot.'+suffix,a,toe,poses)
        upper,lower,palm=arms(clip,phase+side,sign)
        shoulder=transform @ Vector((sign*SHOULDER_HALF_WIDTH,0,SHOULDER_HEIGHT))
        elbow=shoulder+UPPER_ARM*_world(upper);wrist=elbow+FOREARM*_world(lower)
        fingers=wrist+HAND*_world(palm)
        _posed_bone(rig,'arm.'+suffix,shoulder,elbow,poses)
        _posed_bone(rig,'forearm.'+suffix,elbow,wrist,poses)
        _posed_bone(rig,'hand.'+suffix,wrist,fingers,poses)


def turn_foot(phase,direction):
    """Relative foot heading and lift for the game's 1.8 rad/sec turn."""
    p=phase%1.;speed=math.degrees(1.8);quarter=speed*.25
    if p<.5:return direction*math.radians(-quarter+speed*p),0.
    t=(p-.5)/.5
    angle=direction*math.radians(hermite(quarter,-quarter,speed,speed,t,.5))
    return angle,.56*math.sin(math.pi*t)**2


def _turn(rig,phase,direction):
    """Alternate small planted pivot steps for approximately 104 degrees/sec."""
    from mathutils import Vector
    hip=Vector((.12*math.sin(math.tau*phase),0,12.30+.08*math.cos(math.tau*2*phase)))
    poses={};_posed_bone(rig,'root',hip,hip+Vector((0,0,2)),poses)
    neck=hip+Vector((0,0,TORSO));_posed_bone(rig,'spine',hip,neck,poses,direction*.018)
    _posed_bone(rig,'head',neck,neck+Vector((0,0,PLAYER_HEIGHT-(1+THIGH+SHIN+TORSO))),poses,direction*.04)
    transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    for side,suffix,sign in ((0.,'L',-1),(.5,'R',1)):
        angle,lift=turn_foot(phase+side,direction)
        x=sign*1.48
        ankle=Vector((x*math.cos(angle),x*math.sin(angle),ANKLE+lift))
        h=hip+Vector((sign*HIP_HALF_WIDTH,0,0))
        delta=ankle-h;dist=delta.length
        if dist>=THIGH+SHIN:raise ValueError('Turn ankle is out of reach')
        axis=delta.normalized();pole=Vector((sign*.025,-1,0));pole=(pole-axis*pole.dot(axis)).normalized()
        along=(THIGH*THIGH-SHIN*SHIN+dist*dist)/(2*dist)
        knee=h+axis*along+pole*math.sqrt(max(0.,THIGH*THIGH-along*along))
        _posed_bone(rig,'thigh.'+suffix,h,knee,poses);_posed_bone(rig,'shin.'+suffix,knee,ankle,poses)
        toe=ankle+Vector((1.5*math.sin(angle),-1.5*math.cos(angle),0))
        _posed_bone(rig,'foot.'+suffix,ankle,toe,poses)
        shoulder=transform @ Vector((sign*SHOULDER_HALF_WIDTH,0,SHOULDER_HEIGHT))
        upper,lower,palm=arms('idle',phase+side,sign)
        elbow=shoulder+UPPER_ARM*_world(upper);wrist=elbow+FOREARM*_world(lower)
        _posed_bone(rig,'arm.'+suffix,shoulder,elbow,poses)
        _posed_bone(rig,'forearm.'+suffix,elbow,wrist,poses)
        _posed_bone(rig,'hand.'+suffix,wrist,wrist+HAND*_world(palm),poses)


def apply_actions(rig):
    """Bake candidate cycles while keeping the original combat actions intact.

    Call on a fresh copy of combat_kit.blend's Player armature. Existing rest
    bones, skin weights, weapon attachment and the nine combat/aim clips are
    left untouched. Export all actions at 60fps with sampling enabled.
    """
    import bpy
    clips=('idle','walk','run','walk_back','turn_left','turn_right')
    if rig.type!='ARMATURE':raise TypeError('Expected Player armature')
    required={'root','spine','head'}|{name+'.'+side for side in ('L','R') for name in ('thigh','shin','foot','arm','forearm','hand')}
    if not required.issubset(rig.pose.bones.keys()):raise ValueError('Player rig is missing expected bones')
    rig.animation_data_create();rig.animation_data.action=None
    for name in clips:
        old=bpy.data.actions.get(name)
        if old is not None:bpy.data.actions.remove(old,do_unlink=True)
    scene=bpy.context.scene;scene.render.fps=60
    for name in clips:
        action=bpy.data.actions.new(name);action.use_fake_user=True
        rig.animation_data.action=action
        frames=120 if name=='idle' else 60
        previous={}
        for frame in range(frames+1):
            phase=frame/frames
            if name=='turn_left':_turn(rig,phase,-1)
            elif name=='turn_right':_turn(rig,phase,1)
            else:_locomotion(rig,name,phase)
            for bone in rig.pose.bones:
                q=bone.rotation_quaternion
                if bone.name in previous and q.dot(previous[bone.name])<0:q.negate()
                previous[bone.name]=q.copy()
                bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone.name)
                bone.keyframe_insert('location',frame=frame,group=bone.name)
    rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(0)
    return {name:(2. if name=='idle' else 1.) for name in clips}
