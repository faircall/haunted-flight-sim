"""Blender background authoring: accepted player plus combat clips and redhead.

Run Blender --background --factory-startup --python build_temple_combat_assets.py.
The original living kit is read as source and its exports are never overwritten.
"""
from pathlib import Path
import json
import math
import random
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
KIT=ROOT/'photo_asset_pipeline'/'temple3d'/'living'
OUT=ROOT/'art'/'temple'/'combat'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(KIT))
# Reuse the existing geometry, weights, skeleton and accepted locomotion baker.
# Stop before the willow section; route all exports to this separate asset kit.
source=(KIT/'build.py').read_text().split('# Willow:')[0]
source=source.replace("OUT = Path(__file__).resolve().parent", "OUT = KIT")
source=source.replace("MODELS = OUT / 'models'", "MODELS = COMBAT_OUT")
namespace=dict(__file__=str(KIT/'build.py'),KIT=KIT,COMBAT_OUT=OUT)
exec(compile(source,str(KIT/'build.py'),'exec'),namespace)
rig=namespace['rig'];body=namespace['body'];gait=namespace['gait']
posed_bone=namespace['posed_bone'];export=namespace['export'];mesh=namespace['mesh']
clips=dict(namespace['clips'])
scene=bpy.context.scene


def keyframes(action,frames,pose):
    rig.animation_data.action=action
    for frame in range(frames+1):
        phase=frame/frames
        pose(phase)
        for bone in rig.pose.bones:
            bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone.name)
            bone.keyframe_insert('location',frame=frame,group=bone.name)


def arm_ik(shoulder,wrist,length1,length2,outside):
    v=wrist-shoulder;distance=min(v.length,length1+length2-.01);direction=v.normalized()
    across=Vector(outside)-direction*Vector(outside).dot(direction);across.normalize()
    along=(length1*length1-length2*length2+distance*distance)/(2*distance)
    return shoulder+direction*along+across*math.sqrt(max(0,length1*length1-along*along))


def combat_pose(phase,clip):
    moving=clip in ('aim_walk','aim_back','aim_left','aim_right')
    base='walk' if moving else 'idle'
    motion=gait.pelvis_motion(base,phase if moving else 0.)
    hip_height=gait.hip_height(base,phase if moving else 0.)
    hip=Vector((motion['lateral'] if moving else 0,0,hip_height))
    recoil=(math.sin(math.pi*min(1,phase*3))* .7 if phase<1/3 else 0) if clip=='recoil' else 0.
    falling=clip=='death'
    fall=min(1,phase*1.45) if falling else 0.
    if falling:hip.z-=10.8*fall;hip.y+=2.5*fall
    poses={};up=Vector((0,math.sin(fall*math.pi/2),math.cos(fall*math.pi/2)))
    posed_bone('root',hip,hip+up*2,poses)
    if clip=='hurt':up=Vector((0,math.sin(.22*math.sin(math.pi*phase)),math.cos(.22*math.sin(math.pi*phase))))
    neck=hip+up*gait.TORSO
    posed_bone('spine',hip,neck,poses)
    posed_bone('head',neck,neck+up*(25.65-(1+gait.THIGH+gait.SHIN+gait.TORSO)),poses)
    transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    for side,suffix,sign in ((0.,'L',-1),(.5,'R',1)):
        path=gait.leg_3d(base,phase if moving else 0.,side)
        points=[Vector((path[k][0],-path[k][1],path[k][2])) for k in ('hip','knee','ankle')]
        if moving:
            angle={'aim_walk':0,'aim_back':math.pi,'aim_left':-math.pi/2,'aim_right':math.pi/2}[clip]
            origin=points[0].copy()
            for point in points[1:]:
                delta=point-origin
                point.x=origin.x+delta.x*math.cos(angle)-delta.y*math.sin(angle)
                point.y=origin.y+delta.x*math.sin(angle)+delta.y*math.cos(angle)
        if falling:
            points[0]=hip+Vector((sign*gait.HIP_HALF_WIDTH,0,0))
            points[2]=Vector((sign*1.5,-3+fall*1.5,1.))
            points[1]=arm_ik(points[0],points[2],gait.THIGH,gait.SHIN,(0,-1,1))
        h,k,a=points
        posed_bone('thigh.'+suffix,h,k,poses);posed_bone('shin.'+suffix,k,a,poses)
        posed_bone('foot.'+suffix,a,a+Vector((0,-1.5,0)),poses)
        shoulder=transform @ Vector((sign*gait.SHOULDER_HALF_WIDTH,0,gait.SHOULDER_HEIGHT))
        if falling:
            wrist=shoulder+Vector((sign*(2+fall*3),1+fall*2,-5*(1-fall)))
            elbow=arm_ik(shoulder,wrist,gait.UPPER_ARM,gait.FOREARM,(sign,1,0))
            finger=wrist+Vector((sign*gait.HAND*fall,0,-gait.HAND*(1-fall)))
        else:
            wrist=Vector((.6 if sign==1 else -.3,-6.7+recoil,18.5+recoil*1.8))
            if clip=='reload':
                pulse=math.sin(math.pi*phase)**2
                wrist.y+=pulse*(3 if sign==1 else 3.4)
                wrist.z-=pulse*(2 if sign==1 else 2.8)
                if sign==-1:wrist.z+=math.sin(math.tau*phase*2)*pulse*.5
            if clip=='hurt':wrist.y+=math.sin(math.pi*phase)*2;wrist.z-=math.sin(math.pi*phase)*2
            if moving:wrist+=Vector((motion['lateral'],0,hip_height-12.6))
            elbow=arm_ik(shoulder,wrist,gait.UPPER_ARM,gait.FOREARM,(sign,0,-.5))
            finger=wrist+Vector((0,-gait.HAND,.08+recoil*.15))
        posed_bone('arm.'+suffix,shoulder,elbow,poses)
        posed_bone('forearm.'+suffix,elbow,wrist,poses)
        posed_bone('hand.'+suffix,wrist,finger,poses)


def backward_pose(phase):
    # Sample the accepted walk in reverse, leaving its original curves intact.
    destination=rig.animation_data.action
    rig.animation_data.action=bpy.data.actions['walk']
    scene.frame_set(round((1-phase)*60))
    samples={b.name:(b.location.copy(),b.rotation_quaternion.copy()) for b in rig.pose.bones}
    rig.animation_data.action=destination
    for b in rig.pose.bones:b.location,b.rotation_quaternion=samples[b.name]


def turn_pose(phase,direction):
    """Alternate planted pivot steps for 120 degrees of rotation per cycle."""
    bob=.10*math.sin(math.tau*phase*2)
    hip=Vector((0,0,12.6+bob));poses={}
    posed_bone('root',hip,hip+Vector((0,0,2)),poses)
    neck=hip+Vector((0,0,gait.TORSO))
    posed_bone('spine',hip,neck,poses,direction*.035)
    posed_bone('head',neck,neck+Vector((0,0,25.65-neck.z)),poses,direction*.09)
    transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    for side,suffix,sign in ((0.,'L',-1),(.5,'R',1)):
        p=(phase+side)%1
        angle=math.radians(direction*(30-p*120)) if p<.5 else math.radians(direction*(-30+(p-.5)*120))
        lift=0 if p<.5 else .85*math.sin(math.pi*(p-.5)*2)
        x=sign*(gait.HIP_HALF_WIDTH+.35)
        ankle=Vector((x*math.cos(angle),x*math.sin(angle),1+lift))
        h=hip+Vector((sign*gait.HIP_HALF_WIDTH,0,0))
        knee=arm_ik(h,ankle,gait.THIGH,gait.SHIN,(0,-1,0))
        posed_bone('thigh.'+suffix,h,knee,poses);posed_bone('shin.'+suffix,knee,ankle,poses)
        posed_bone('foot.'+suffix,ankle,ankle+Vector((1.5*math.sin(angle),-1.5*math.cos(angle),0)),poses)
        shoulder=transform @ Vector((sign*gait.SHOULDER_HALF_WIDTH,0,gait.SHOULDER_HEIGHT))
        upper,lower,palm=gait.arm_vectors('idle',phase+side,sign)
        world=lambda v:Vector((v[0],-v[1],v[2]))
        elbow=shoulder+gait.UPPER_ARM*world(upper)
        wrist=elbow+gait.FOREARM*world(lower)
        posed_bone('arm.'+suffix,shoulder,elbow,poses)
        posed_bone('forearm.'+suffix,elbow,wrist,poses)
        posed_bone('hand.'+suffix,wrist,wrist+gait.HAND*world(palm),poses)


for clip,pose in (('walk_back',backward_pose),('turn_left',lambda p:turn_pose(p,-1)),('turn_right',lambda p:turn_pose(p,1))):
    action=bpy.data.actions.new(clip);action.use_fake_user=True
    keyframes(action,60,pose);clips[clip]=1.


for clip,seconds in (('aim',1.),('aim_walk',clips['walk']),('aim_back',clips['walk']),('aim_left',clips['walk']),('aim_right',clips['walk']),('recoil',.24),('reload',1.15),('hurt',.3),('death',.9)):
    action=bpy.data.actions.new(clip);action.use_fake_user=True
    keyframes(action,round(seconds*60),lambda p,c=clip:combat_pose(p,c))
    clips[clip]=round(seconds*60)/60
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(0)
export('player',[rig,body],True)

# Low-poly pistol, rigidly weighted to the right hand; only drawn while armed.
gun_vertices=[];gun_faces=[]
def box(center,size):
    start=len(gun_vertices);x,y,z=center;w,d,h=[v/2 for v in size]
    gun_vertices.extend((x+a*w,y+b*d,z+c*h) for a,b,c in
        ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)))
    gun_faces.extend([start+i for i in face] for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)))
wrist=rig.data.bones['hand.R'].head_local
box(wrist+Vector((0,0,-1.65)),(.8,.85,2.7));box(wrist+Vector((0,.65,-.65)),(.65,1.4,.75))
gun_mat=bpy.data.materials.new('Pistol / blued steel');gun_mat.diffuse_color=(.16,.18,.2,1)
gun=mesh('Pistol',gun_vertices,gun_faces,gun_mat,[[(0,0)]*4 for f in gun_faces])
group=gun.vertex_groups.new(name='hand.R');group.add(list(range(len(gun_vertices))),1,'REPLACE')
gun.parent=rig;gun.modifiers.new('Hand attachment','ARMATURE').object=rig
export('pistol',[rig,gun],True)
gun.hide_set(True)

# Pale chorus figure: a large porcelain head over a short, ink-dark body.
# "redhead" remains the asset/AI identifier for compatibility with old scenes.
# A small deterministic atlas replaces a per-face material/draw-call explosion.
image=bpy.data.images.new('Chorus / 128px monochrome atlas',width=128,height=128)
rng=random.Random(381);pixels=[]
for y in range(128):
    for x in range(128):
        region=x//32
        colors=((.095,.11,.09),(.96,.96,.94),(.96,.96,.94),(.018,.025,.018))
        base=colors[region];noise=rng.choice((-.04,-.015,0,.015,.025))
        if region==0 and x%9 in (0,1):noise+=.035
        if region in (1,2):noise*=.3
        if region==1:
            # A small, original mask texture follows the print's vocabulary:
            # outlined eyes, long nose, angular cheek stains and an open mouth.
            u=(x-32)/31;v=(y-6)/80
            ink=False;eye_white=False
            for cx in (.25,.75):
                eye=((u-cx)/.145)**2+((v-.65)/.085)**2
                ink|=eye<1
                eye_white|=((u-cx)/.080)**2+((v-.65)/.045)**2<1
                ink|=abs(u-cx)<.14 and abs(v-(.765-.20*abs(u-cx)))<.025
            ink|=(.19<u<.29 and .32+.07*math.sin(u*95)<v<.565)
            ink|=(.70<u<.79 and .37+.04*math.sin(u*83)<v<.56)
            ink|=(.445<u<.485 and .30<v<.93)
            ink|=(.535<u<.57 and .31<v<.84)
            ink|=(.46<u<.59 and .29<v<.335)
            ink|=(.45<u<.59 and .09<v<.235 and u>.46+.025*math.sin(v*70))
            ink|=(.12<u<.155 and .18<v<.49) or (.855<u<.885 and .23<v<.53)
            if ink:base=colors[3];noise*=.25
            if eye_white:base=colors[2]
            if any(((u-cx)/.025)**2+((v-.67)/.026)**2<1 for cx in (.25,.75)):base=colors[3]
        pixels.extend((*[max(0,min(1,c+noise)) for c in base],1))
image.pixels=pixels;image.filepath_raw=str(OUT/'redhead.png');image.file_format='PNG';image.save();image.pack()
mat=bpy.data.materials.new('Chorus / white skin and charcoal cloth');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Closest'
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
verts=[];faces=[];uvs=[];weights=[]
def rings(rows,weight,panel=0,sides=10,caps=True,face_mask=False):
    start=len(verts)
    for cx,cy,z,rx,ry in rows:
        for j in range(sides):
            a=math.tau*j/sides
            vertex=(cx+math.cos(a)*rx,cy+math.sin(a)*ry,z)
            verts.append(vertex);weights.append(weight(vertex) if callable(weight) else weight if isinstance(weight,dict) else {weight:1.})
    for row in range(len(rows)-1):
        for j in range(sides):
            faces.append([start+row*sides+j,start+row*sides+(j+1)%sides,start+(row+1)*sides+(j+1)%sides,start+(row+1)*sides+j])
            u0=(panel*32+2+j/sides*28)/128;u1=(panel*32+2+(j+1)/sides*28)/128
            v0=.05+row/(len(rows)-1)*.9;v1=.05+(row+1)/(len(rows)-1)*.9
            coords=[(u0,v0),(u1,v0),(u1,v1),(u0,v1)]
            if face_mask and sides/2+1<=j<sides-1:
                coords=[((34+max(0,min(1,.5+verts[i][0]/7.0))*28)/128,
                         (6+max(0,min(1,(verts[i][2]-22.4)/6))*80)/128) for i in faces[-1]]
            uvs.append(coords)
    for row,reverse in (((0,True),(len(rows)-1,False)) if caps else ()):
        face=[start+row*sides+j for j in range(sides)]
        if reverse:face.reverse()
        faces.append(face);uvs.append([((panel*32+16)/128,.5)]*sides)
def coat_weight(vertex):
    x,y,z=vertex
    if z>=14.3:return {'spine':1.}
    if z>=11.7:
        spine=(z-11.7)/(14.3-11.7)
        return {'spine':spine,'root':1-spine}
    leg='thigh.'+('R' if x>=0 else 'L')
    amount=min(.45,(11.7-z)/11)
    return {'root':1-amount,leg:amount}


# A knee-length coat makes the exposed legs short, as in the leftmost figure.
# The lower hem follows the pelvis and thighs rather than the leaning chest.
rings([(0,0,6.9,2.8,1.65),(0,0,9.8,2.8,1.7),(0,0,11.7,2.7,1.6),
       (0,.3,14.3,2.4,1.5),(0,.4,18,3.0,1.8),(0,.4,20.6,2.5,1.5)],coat_weight,0,16,False)
rings([(0,0,20.5,1.05,1.),(0,0,22.,1.1,1.)],'head',2,10)
rings([(0,-.1,21.7,1.1,1.),(0,-.25,23.1,2.25,1.6),(0,-.2,25.,3.1,2.1),
       (0,0,27.5,3.3,2.2),(0,.15,29.2,2.5,1.8),(0,.2,29.85,.65,.6)],'head',2,16,True,True)
# A long narrow nose gives the pale mask a human profile.
rings([(0,-2.02,24.2,.27,.30),(0,-2.28,24.7,.38,.48),
       (0,-2.14,26.8,.23,.25),(0,-1.98,27.3,.16,.12)],'head',2,6)
# Dark rounded hair wraps down the sides/back, with an uneven high fringe.
start=len(verts);hair_sides=16
for row in range(4):
    for j in range(hair_sides):
        a=math.tau*j/hair_sides
        if row==0:
            front=max(0,-math.sin(a))
            z=23.5+4.4*front**1.5+.12*math.cos(a*3)
            rx=3.5;ry=2.35+.12*front
        else:z,rx,ry=((28.4,3.55,2.48),(29.4,2.65,1.98),(30.,.75,.65))[row-1]
        verts.append((math.cos(a)*rx,.17+math.sin(a)*ry,z));weights.append({'head':1.})
for row in range(3):
    for j in range(hair_sides):
        faces.append([start+row*hair_sides+j,start+row*hair_sides+(j+1)%hair_sides,
                      start+(row+1)*hair_sides+(j+1)%hair_sides,start+(row+1)*hair_sides+j])
        uvs.append([(100/128,.1),(122/128,.1),(122/128,.9),(100/128,.9)])
faces.append([start+3*hair_sides+j for j in range(hair_sides)])
uvs.append([(112/128,.5)]*hair_sides)
for sign,suffix in ((-1,'L'),(1,'R')):
    x=sign*gait.HIP_HALF_WIDTH
    rings([(x,0,12.5,1.2,1.1),(x,0,8.7,.85,.85),(x,0,6.8,.75,.7)],'thigh.'+suffix,0,8)
    rings([(x,0,6.8,.75,.7),(x,0,3.5,.6,.65),(x,0,1.,.6,.6)],'shin.'+suffix,0,8)
    rings([(x,-.65,.15,.9,1.4),(x,-.65,1.2,.85,1.4)],'foot.'+suffix,0,8)
    shoulder=sign*gait.SHOULDER_HALF_WIDTH
    elbow=gait.SHOULDER_HEIGHT-gait.UPPER_ARM;wrist_z=elbow-gait.FOREARM
    rings([(shoulder,0,gait.SHOULDER_HEIGHT,1,.95),(shoulder,0,elbow+.3,.65,.6),(shoulder,0,elbow,.6,.6)],'arm.'+suffix,0,8)
    rings([(shoulder,0,elbow,.6,.6),(shoulder,0,wrist_z,.45,.45)],'forearm.'+suffix,0,8)
    rings([(shoulder,0,wrist_z,.55,.45),(shoulder,0,wrist_z-1.8,.4,.35)],'hand.'+suffix,2,8)
enemy=mesh('Chorus / pale oversized head and dark coat',verts,faces,mat,uvs)
for name in rig.data.bones:
    group=enemy.vertex_groups.new(name=name.name)
    for i,weight in enumerate(weights):
        if name.name in weight:group.add([i],weight[name.name],'REPLACE')
enemy.parent=rig;enemy.modifiers.new('GPU skin','ARMATURE').object=rig

def enemy_pose(phase,clip):
    base='walk' if clip=='walk' else 'idle'
    combat_pose(phase,'death' if clip=='death' else 'aim_walk' if clip=='walk' else 'aim')
    poses={}
    # Preserve the lower body from the accepted locomotion while leaning the
    # monster's chest and carrying its long hands forward, ready to strike.
    for bone in rig.pose.bones:poses[bone.name]=bone.matrix.copy()
    hip=Vector((0,0,gait.hip_height(base,phase)))
    lean=.25+(.18*math.sin(math.pi*phase) if clip=='attack' else 0)
    if clip=='death':return
    neck=hip+Vector((0,-math.sin(lean)*gait.TORSO,math.cos(lean)*gait.TORSO))
    posed_bone('root',hip,hip+Vector((0,0,2)),poses)
    posed_bone('spine',hip,neck,poses);posed_bone('head',neck,neck+Vector((0,-.1,4.5)),poses)
    transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    swing=math.sin(math.tau*phase)*.4 if clip=='walk' else 0
    strike=math.sin(math.pi*min(1,phase*1.7)) if clip=='attack' else 0
    stagger=math.sin(math.pi*phase)*1.5 if clip=='stagger' else 0
    for sign,suffix in ((-1,'L'),(1,'R')):
        shoulder=transform @ Vector((sign*gait.SHOULDER_HALF_WIDTH,0,gait.SHOULDER_HEIGHT))
        upper=Vector((sign*.2,-.2-strike*.75+stagger*.3,-.9+strike*.6));upper.normalize()
        lower=Vector((sign*.15,-.65-strike*.3,-.7+strike*.6));lower.normalize()
        elbow=shoulder+upper*gait.UPPER_ARM+Vector((0,sign*swing,0))
        wrist=elbow+lower*gait.FOREARM;tip=wrist+lower*gait.HAND
        posed_bone('arm.'+suffix,shoulder,elbow,poses);posed_bone('forearm.'+suffix,elbow,wrist,poses);posed_bone('hand.'+suffix,wrist,tip,poses)

# Export just the enemy actions by giving it a separate copy of the skeleton.
player_rig=rig;enemy_rig=bpy.data.objects.new('Redhead',rig.data.copy());scene.collection.objects.link(enemy_rig)
bpy.context.view_layer.update()
enemy.parent=enemy_rig;enemy.modifiers[0].object=enemy_rig;rig=enemy_rig
namespace['rig']=rig;rig.animation_data_create()
enemy_clips={}
for clip,seconds in (('idle',2.),('walk',.9),('attack',1.),('stagger',.35),('death',.9)):
    action=bpy.data.actions.new('redhead_'+clip);action.use_fake_user=True
    # GLB clip names are stripped below, with player actions temporarily untagged.
    keyframes(action,round(seconds*60),lambda p,c=clip:enemy_pose(p,c))
    action.name='enemy_'+clip;enemy_clips['enemy_'+clip]=round(seconds*60)/60
rig.animation_data.action=bpy.data.actions['enemy_idle'];scene.frame_set(0)
# Bake stature into vertices, rest joints and animated translations.
enemy_scale=.72
for vertex in enemy.data.vertices:vertex.co*=enemy_scale
namespace['select_only']([rig]);bpy.ops.object.mode_set(mode='EDIT')
for bone in rig.data.edit_bones:bone.head*=enemy_scale;bone.tail*=enemy_scale
bpy.ops.object.mode_set(mode='OBJECT')
for name in enemy_clips:
    action=bpy.data.actions[name]
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path.endswith('.location'):
                        for key in curve.keyframe_points:
                            key.co.y*=enemy_scale;key.handle_left.y*=enemy_scale;key.handle_right.y*=enemy_scale
scene.frame_set(0);bpy.context.view_layer.update()
export('redhead',[rig,enemy],True)
player_rig.animation_data.action=bpy.data.actions['idle']
enemy_rig.location.x=36
for name,objects in (('Player / accepted rig + combat',[player_rig,body,gun]),('Redhead / encounter enemy',[enemy_rig,enemy])):
    collection=bpy.data.collections.new(name);scene.collection.children.link(collection)
    for obj in objects:
        for existing in list(obj.users_collection):existing.objects.unlink(obj)
        collection.objects.link(obj)
scene.frame_set(0);scene.frame_end=120
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'combat_kit.blend'))
(OUT/'manifest.json').write_text(json.dumps(dict(player=dict(clips=clips),redhead=dict(clips=enemy_clips,
    vertices=len(verts),triangles=sum(len(f)-2 for f in faces),bones=15,height=21.6,aim_height=14.5,
    reference='Margaret Breindel, The Chorus; artdev/ChorusReference.jpg, short leftmost figure'),source='Accepted living kit; original exports preserved'),indent=2)+'\n',newline='\n')
print('Combat kit exported to',OUT)
