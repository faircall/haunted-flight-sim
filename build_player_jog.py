"""Bake the independent relaxed jog on the compatible player skeleton."""
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import player_jog as jog
from photo_asset_pipeline.temple3d.living import gait

OUT=ROOT/'art'/'temple'/'player_jog'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art'/'temple'/'combat'/'combat_kit.blend'))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene;scene.render.fps=60
rig=bpy.data.objects['Player'];body=bpy.data.objects['Player / PS1 shirtjacket character']
for obj in list(bpy.data.objects):
    if obj not in (rig,body):bpy.data.objects.remove(obj,do_unlink=True)
rig.animation_data_clear()
for action in list(bpy.data.actions):bpy.data.actions.remove(action,do_unlink=True)
rig.animation_data_create()
action=bpy.data.actions.new('run');action.use_fake_user=True;rig.animation_data.action=action


def world(point):return Vector((point[0],-point[1],point[2]))


def posed_bone(name,head,tail,poses,twist=0.):
    bone=rig.pose.bones[name];rest=bone.bone.matrix_local
    direction=(Vector(tail)-Vector(head)).normalized()
    rest_direction=(bone.bone.tail_local-bone.bone.head_local).normalized()
    rotation=Quaternion(direction,twist) @ rest_direction.rotation_difference(direction) @ rest.to_quaternion()
    desired=Matrix.LocRotScale(Vector(head),rotation,Vector((1,1,1)))
    basis=rest.inverted()
    if bone.parent:basis=basis @ bone.parent.bone.matrix_local @ poses[bone.parent.name].inverted()
    bone.rotation_mode='QUATERNION';bone.matrix_basis=basis @ desired;poses[name]=desired


previous={}
for frame in range(61):
    phase=frame/60
    motion=jog.pelvis(phase)
    hip=world((motion['lateral'],motion['forward'],jog.hip_height(phase)))
    poses={};posed_bone('root',hip,hip+2*world(motion['up']),poses,-motion['yaw'])
    lean=jog.torso_lean(phase);bank=jog.torso_bank(phase)
    neck=hip+gait.TORSO*Vector((math.sin(bank),-math.sin(lean)*math.cos(bank),math.cos(lean)*math.cos(bank)))
    posed_bone('spine',hip,neck,poses,jog.torso_twist(phase))
    head_height=25.65-(1+gait.THIGH+gait.SHIN+gait.TORSO)
    posed_bone('head',neck,neck+Vector((0,0,head_height)),poses)
    transform=poses['spine'] @ rig.data.bones['spine'].matrix_local.inverted()
    for side,suffix,sign in ((0.,'L',-1),(.5,'R',1)):
        path=jog.leg(phase,side)
        h,k,ankle=(world(path[key]) for key in ('hip','knee','ankle'))
        posed_bone('thigh.'+suffix,h,k,poses);posed_bone('shin.'+suffix,k,ankle,poses)
        tip=ankle+Vector((0,-1.5*math.cos(path['pitch']),1.5*math.sin(path['pitch'])))
        posed_bone('foot.'+suffix,ankle,tip,poses)
        upper,lower,palm=jog.arm_vectors(phase+side,sign)
        shoulder=transform @ Vector((sign*gait.SHOULDER_HALF_WIDTH,0,gait.SHOULDER_HEIGHT))
        elbow=shoulder+gait.UPPER_ARM*world(upper);wrist=elbow+gait.FOREARM*world(lower)
        posed_bone('arm.'+suffix,shoulder,elbow,poses)
        posed_bone('forearm.'+suffix,elbow,wrist,poses)
        posed_bone('hand.'+suffix,wrist,wrist+gait.HAND*world(palm),poses,sign*math.radians(65.))
    for bone in rig.pose.bones:
        q=bone.rotation_quaternion
        if bone.name in previous and q.dot(previous[bone.name])<0:q.negate()
        previous[bone.name]=q.copy()
        bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone.name)
        bone.keyframe_insert('location',frame=frame,group=bone.name)

scene.frame_set(0);scene.frame_end=60
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'player_jog.blend'))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'jog.glb'),export_format='GLB',
    use_selection=True,export_yup=True,export_animations=True,export_force_sampling=True,
    export_animation_mode='ACTIONS',export_optimize_animation_size=False,
    export_frame_range=False,export_skins=True)
manifest={'player':{'clips':{'run':1.},'stride':jog.JOG_STRIDE,'world_speed':jog.JOG_SPEED,
    'stance':jog.STANCE,'description':'Relaxed normal jogging; sprint preserved separately.'}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('PLAYER JOG',json.dumps(manifest))
