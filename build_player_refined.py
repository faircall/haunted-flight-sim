"""Build the proportioned player candidate on the accepted 15-bone rig.

The original kit is read only. The rebuilt clothing has a shared pelvis and
crotch topology, softer shoulders and more readable hands. Accepted animation
actions and weapon attachment remain compatible. Run in background Blender.
"""
from pathlib import Path
import json
import math
import shutil
import sys

import bpy

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'art'/'temple'/'combat'/'combat_kit.blend'
OUT=ROOT/'art'/'temple'/'player_refined'
LIVING=ROOT/'photo_asset_pipeline'/'temple3d'/'living'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(LIVING));sys.path.insert(0,str(ROOT))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene;scene.render.fps=60
rig=bpy.data.objects['Player']
old=bpy.data.objects['Player / PS1 shirtjacket character']
material=old.data.materials[0]
for obj in list(bpy.data.objects):
    if obj!=rig:bpy.data.objects.remove(obj,do_unlink=True)
for action in list(bpy.data.actions):
    if action.name.startswith('enemy_'):bpy.data.actions.remove(action)

# Shorten the actual rest chain as well as the sleeve/hand surface. Keeping
# the shoulder anchor and local action rotations gives a natural proportion
# change throughout the existing animation set, without changing its timing.
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for side in ('L','R'):
    arm=rig.data.edit_bones['arm.'+side]
    forearm=rig.data.edit_bones['forearm.'+side]
    hand=rig.data.edit_bones['hand.'+side]
    shoulder=arm.head.copy()
    direction=(arm.tail-arm.head).normalized()
    arm.tail=shoulder+direction*4.095
    forearm.head=arm.tail
    forearm.tail=forearm.head+direction*3.458
    hand.head=forearm.tail
    hand.tail=hand.head+direction*1.5
bpy.ops.object.mode_set(mode='OBJECT')

# Retain the front/profile likeness and compact original colour atlas.
atlas=OUT/'player_atlas.png'
shutil.copyfile(LIVING/'textures'/'player.png',atlas)
for node in material.node_tree.nodes:
    if node.type=='TEX_IMAGE' and node.image:
        node.image=bpy.data.images.load(str(atlas),check_existing=False)
        image=node.image;pixels=list(image.pixels[:])
        for py in range(53,64):
            blend=.42*((py-53)/10.)**2
            for px in range(1,63):
                k=((255-py)*256+px)*4
                for c,target in enumerate((176/255,145/255,124/255)):
                    pixels[k+c]=pixels[k+c]*(1.-blend)+target*blend
        # Quiet woven trouser cloth. The old pocket drawing stretched into
        # oversized ochre shapes when carried over the connected saddle.
        for py in range(64,192):
            t=(py-64)/127
            for px in range(64):
                u=px/63
                grain=2.6*math.sin(px*2.31+py*1.74)+1.5*math.cos(px*.63-py*.47)
                fold=0.
                for y0 in (.51,.59,.88,.94):
                    line=t-y0-.013*math.sin(u*math.pi*2)
                    fold-=6.*math.exp(-(line/.009)**2)
                    fold+=3.*math.exp(-((line-.014)/.009)**2)
                seam=-4.*math.exp(-((u-.12)/.014)**2)
                value=grain+fold+seam
                k=((255-py)*256+px)*4
                for c,base in enumerate((109,78,51)):
                    pixels[k+c]=max(0.,min(1.,(base+value)/255))
        image.pixels[:]=pixels;image.filepath_raw=str(atlas)
        image.file_format='PNG';image.save();image.pack()
        node.interpolation='Closest'

from player_refined_geometry import geometry
points,faces,coords,weights,softened=geometry()

def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)

for i,((x,y,z),w) in enumerate(zip(points,weights)):
    arm=sum(v for name,v in w.items() if name.startswith(('arm.','forearm.')))
    if w.get('head',0)<.02 and arm<.3 and w.get('spine',0)>.15 and 12.7<z<20.3:
        # Chest projects subtly over a softer abdomen and natural waist.
        chest=math.exp(-((z-18.0)/1.5)**2)
        waist=math.exp(-((z-13.2)/.7)**2)
        y*=1+.10*chest-.025*waist
    if w.get('head',0)<.02 and w.get('spine',0)+arm>.1 and z>16:
        side=smooth((abs(x)-1.2)/1.5)
        upper=smooth((z-17)/1.8)*smooth((20.9-z)/.55)
        z-=.27*side*upper
        x*=1-.018*side*upper
        if arm>.75 and 12.<z<18.3:
            fold=.012*math.sin(z*3.1+y*2.4+abs(x)*1.8)
            x+=(1 if x>0 else -1)*fold;y+=fold*math.sin(z*1.7)
    # Keep a readable palm width without extending the fingertips further
    # down the thigh after shortening the upper and lower arm.
    if w.get('hand.L',0)+w.get('hand.R',0)>.8 and z<11.1:
        center=2.6 if x>0 else -2.6
        x=center+(x-center)*1.17
        y*=1.06
    points[i]=(x,y,z)

mesh=bpy.data.meshes.new('Player / connected cloth topology')
mesh.from_pydata(points,[],faces);mesh.update()
body=bpy.data.objects.new('Player / refined candidate',mesh)
scene.collection.objects.link(body);body.parent=rig
mesh.materials.append(material)
uv=mesh.uv_layers.new(name='Colour atlas')
for poly,face_uv,soft in zip(mesh.polygons,coords,softened):
    poly.use_smooth=soft
    for loop,point in zip(poly.loop_indices,face_uv):uv.data[loop].uv=point
for bone in rig.data.bones:
    group=body.vertex_groups.new(name=bone.name)
    for i,w in enumerate(weights):
        if w.get(bone.name,0):group.add([i],w[bone.name],'REPLACE')
modifier=body.modifiers.new('GPU skeletal deformation','ARMATURE');modifier.object=rig

procedural='--procedural-gait' in sys.argv
if procedural:
    from player_gait_v2 import apply_actions
    apply_actions(rig)
rig.animation_data.action=bpy.data.actions['idle']
scene.frame_set(0);scene.frame_end=120
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'player_refined.blend'))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'player.glb'),export_format='GLB',
    use_selection=True,export_yup=True,export_animations=True,
    export_force_sampling=True,export_animation_mode='ACTIONS',
    export_optimize_animation_size=False,export_frame_range=False,export_skins=True)
clips=json.loads((ROOT/'art'/'temple'/'combat'/'manifest.json').read_text())['player']['clips']
manifest={'player':{'clips':clips,'vertices':len(mesh.vertices),
    'triangles':sum(len(p.vertices)-2 for p in mesh.polygons),'bones':len(rig.data.bones),
    'height':25.65,'atlas':'player_atlas.png',
    'arm_proportions':{'upper_arm':4.095,'forearm':3.458,'hand':1.5},
    'description':'Rebuilt adult player with connected trousers, shorter articulated arms and readable hands.'}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('REFINED PLAYER',json.dumps(manifest))
