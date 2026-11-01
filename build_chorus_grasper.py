"""Build an independent, hand-painted Chorus figure and its skinned clips.

Run Blender in background with ``--python build_chorus_grasper.py``. The source
rig is read from the existing combat kit, but neither that file nor its
exports are written. ``--draft`` builds a static preview under artifacts.
"""
from pathlib import Path
import json
import math
import random
import sys

import bpy

ROOT=Path(__file__).resolve().parent
DRAFT='--draft' in sys.argv
OUT=(ROOT/'artifacts'/'chorus-model'/'draft' if DRAFT else ROOT/'art'/'temple'/'chorus_grasper')
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art'/'temple'/'combat'/'combat_kit.blend'))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene;scene.render.fps=60
rig=bpy.data.objects['Player'];rig.name='Chorus / original rest rig'
rig.animation_data_clear()
for obj in list(bpy.data.objects):
    if obj!=rig:bpy.data.objects.remove(obj,do_unlink=True)
for action in list(bpy.data.actions):bpy.data.actions.remove(action,do_unlink=True)

# A small, deliberately imperfect painted atlas: pale mask, ink-dark marks,
# weathered monochrome cloth and hair. This is drawn from the figure's visual
# vocabulary, not a photograph projected onto the model.
randomiser=random.Random(19465);size=256;pixels=[]
for y in range(size):
    for x in range(size):
        r=randomiser.random()-.5
        if x<64:
            grain=.014*math.sin(x*.37+y*.025)+.008*math.sin(x*.14-y*.19)+r*.018
            if (x*7+y//3)%71<2:grain+=.023
            colour=(.075+grain,.092+grain,.073+grain)
        elif x<160:
            u=(x-64)/96;v=(y-20)/216
            grain=r*.016+.004*math.sin(x*.31+y*.11)
            colour=(.935+grain,.945+grain,.922+grain)
            ink=False;white=False
            for index,cx in enumerate((.292,.708)):
                eye_height=(.682,.700)[index]
                dx=(u-cx)/(.127 if index==0 else .132);dy=(v-eye_height)/.075
                ink|=dx*dx+dy*dy<1.+.10*math.sin(x*.93+y*.47)+.035*math.sin(y*2.2)
                white|=((u-cx)/.072)**2+((v-eye_height-.011)/.029)**2<1.
                ink|=(abs(u-cx)<.14 and abs(v-(eye_height+.105-.16*abs(u-cx)))<.014)
                # Hand-cut, tapered cheek-darkness from the eye down to jaw.
                low=(.205 if index==0 else .17)+.07*abs((u-cx)/.12)
                high=(.565 if index==0 else .555)+.014*math.sin(x*.47+index)
                # Uneven strokes and small gaps, like ink caught by paper,
                # instead of two immaculate geometric cheek rectangles.
                width=(.060 if index==0 else .054)+.011*math.sin(y*.16+cx*8)+.004*math.sin(y*.48)
                shift=.008*math.sin(y*.075+index*1.7)
                ink|=(abs(u-cx-shift)<width and low<v<high)
            # An ivory central nose ridge is surrounded by two broken strokes.
            ink|=(.462<u<.477 and .28<v<.89 and (y//7)%7!=3)
            ink|=(.525<u<.539 and .31<v<.84 and (y//5)%9!=4)
            # Uneven open mouth, closer to a vertical ink cut than a dot.
            ink|=(.479+.006*math.sin(y*.23)<u<.527+.004*math.sin(y*.31) and .115<v<.283)
            if ink:
                brush=r*.018+.008*math.sin(x*.9+y*.16)
                colour=(.029+brush,.039+brush,.029+brush)
                # Broken, narrow highlights keep the print's worn texture
                # without filling the sockets or softening the silhouette.
                if (x*29+y//3*17)%193<3 and .19<v<.57:
                    colour=(.61+r*.07,.63+r*.07,.59+r*.07)
            if white:colour=(.94,.947,.925)
            for cx,eye_height in ((.292,.682),(.708,.700)):
                if ((u-cx)/.023)**2+((v-eye_height-.014)/.027)**2<1:colour=(.025,.032,.025)
            if (x*13+y*17)%313==0 and .1<v<.9:colour=tuple(max(0,c-.08) for c in colour)
        elif x<208:
            grain=r*.01+.006*math.sin(x*.2+y*.11)
            colour=(.92+grain,.935+grain,.91+grain)
        else:
            grain=.008*math.sin(x*.31+y*.13)+r*.012
            colour=(.026+grain,.034+grain,.026+grain)
        pixels.extend((*[min(1.,max(0.,c)) for c in colour],1.))
atlas=bpy.data.images.new('Chorus / 256px hand-painted atlas',width=size,height=size)
atlas.pixels=pixels;atlas.filepath_raw=str(OUT/'chorus_grasper_atlas.png');atlas.file_format='PNG';atlas.save();atlas.pack()
material=bpy.data.materials.new('Chorus / ink and chalk');material.use_nodes=True
shader=material.node_tree.nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.88
tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas;tex.interpolation='Closest'
material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])

vertices=[];faces=[];uvs=[];weights=[];smooth_faces=[]
def vertex(point,weight):
    vertices.append(point);weights.append(weight(point) if callable(weight) else dict(weight));return len(vertices)-1


def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3.-2.*t)


def mix_weights(a,b,t):
    t=smooth(t);return {a:1.-t,b:t}


def cloth_uv(j,row,rows,sides):
    return ((5.+j/sides*54.)/256.,(.06+row/max(1,rows-1)*.88))


def rings(rows,weight,panel='cloth',sides=16,caps=True,face=False):
    """Cross sections (centre-x, centre-y, z, radius-x, radius-y)."""
    start=len(vertices)
    for cx,cy,z,rx,ry in rows:
        for j in range(sides):
            a=math.tau*j/sides
            vertex((cx+math.cos(a)*rx,cy+math.sin(a)*ry,z),weight)
    for row in range(len(rows)-1):
        for j in range(sides):
            face_indices=[start+row*sides+j,start+row*sides+(j+1)%sides,
                          start+(row+1)*sides+(j+1)%sides,start+(row+1)*sides+j]
            faces.append(face_indices);smooth_faces.append(True)
            if face and sides//2<=j<sides-1:
                uvs.append([((66.+max(0.,min(1.,.5+vertices[k][0]/6.85))*92.)/256.,
                             (20.+max(0.,min(1.,(vertices[k][2]-20.35)/6.75))*216.)/256.) for k in face_indices])
            elif panel=='cloth':
                uvs.append([cloth_uv(j,row,len(rows),sides),cloth_uv(j+1,row,len(rows),sides),
                            cloth_uv(j+1,row+1,len(rows),sides),cloth_uv(j,row+1,len(rows),sides)])
            else:
                u=(184. if panel=='skin' else 232.)/256.
                uvs.append([(u,.15),(u,.15),(u,.82),(u,.82)])
    if caps:
        for row,reverse in ((0,True),(len(rows)-1,False)):
            face_indices=[start+row*sides+j for j in range(sides)]
            if reverse:face_indices.reverse()
            faces.append(face_indices);smooth_faces.append(False)
            u=(25. if panel=='cloth' else 184. if panel=='skin' else 232.)/256.
            uvs.append([(u,.5)]*sides)


def coat_weight(p):
    z=p[2]
    return {'root':1.} if z<11.8 else mix_weights('root','spine',(z-11.8)/2.7) if z<14.5 else {'spine':1.}


def limbs_weight(side,part):
    def assign(p):
        z=p[2]
        if part=='arm':
            if z>15.5:return {'arm.'+side:1.}
            if z>14.4:return mix_weights('forearm.'+side,'arm.'+side,(z-14.4)/1.1)
            if z>11.7:return {'forearm.'+side:1.}
            if z>10.65:return mix_weights('hand.'+side,'forearm.'+side,(z-10.65)/1.05)
            return {'hand.'+side:1.}
        if z>7.45:return {'thigh.'+side:1.}
        if z>6.15:return mix_weights('shin.'+side,'thigh.'+side,(z-6.15)/1.3)
        return {'shin.'+side:1.}
    return assign


# Long, dark close-fitting tunic, sloping shoulders and slightly uneven hem.
rings([(0,.05,9.55,2.35,1.32),(0,.05,10.9,2.37,1.36),(0,.05,12.6,2.21,1.30),
       (0,.05,14.1,2.15,1.30),(0,.04,16.2,2.26,1.35),(0,.02,18.5,2.59,1.40),
       (0,.02,19.35,2.32,1.34),(0,.04,20.05,1.54,1.12),(0,.04,20.6,1.09,.94)],coat_weight,sides=20)

# Short dark collar nests directly below the broad jaw.
rings([(0,.04,19.95,1.12,.94),(0,.04,20.40,1.06,.92),(0,.03,20.68,.93,.84)],{'head':1.},sides=16)
rings([(0,.02,20.38,.90,.80),(0,.02,20.72,1.08,.90)],{'head':1.},'skin',sides=18)

# The face is an oval mask, distinctly larger than the player's, with a
# shallow jaw and a human profile. Front-only UVs carry the etched features.
rings([(0,.02,20.54,1.16,.92),(0,-.12,21.18,1.80,1.28),(0,-.20,21.95,2.33,1.60),
       (0,-.20,23.05,2.75,1.89),(0,-.12,24.30,3.02,2.08),(0,.0,25.45,3.15,2.14),
       (0,.10,26.33,2.87,1.98),(0,.17,26.89,2.15,1.59),(0,.17,27.10,.60,.56)],
      {'head':1.},'skin',sides=24,face=True)
# Low-relief nose, kept ivory so the profile remains visible against darkness.
rings([(0,-1.84,23.05,.20,.18),(0,-2.08,23.46,.26,.26),(0,-2.13,24.02,.19,.19),
       (0,-2.07,24.96,.12,.11)],{'head':1.},'skin',sides=8)

# Cap silhouette: broad at the sides, rising above the forehead, falling down
# around the back. Irregular edge avoids a mechanical helmet or floating disc.
start=len(vertices);sides=24
for row in range(5):
    for j in range(sides):
        a=math.tau*j/sides;front=max(0.,-math.sin(a))
        if row==0:
            z=22.75+3.28*front**1.5+.07*math.sin(a*5.)
            rx,ry=2.82+.25*front,1.98+.24*front
        else:
            z,rx,ry=((26.15,3.36,2.28),(26.68,2.97,2.04),(27.03,2.03,1.53),(27.32,.45,.42))[row-1]
        vertex((math.cos(a)*rx,.11+math.sin(a)*ry,z),{'head':1.})
for row in range(4):
    for j in range(sides):
        faces.append([start+row*sides+j,start+row*sides+(j+1)%sides,
                      start+(row+1)*sides+(j+1)%sides,start+(row+1)*sides+j])
        uvs.append([(232/256,.10),(232/256,.10),(232/256,.90),(232/256,.90)]);smooth_faces.append(True)
faces.append([start+4*sides+j for j in range(sides)]);uvs.append([(232/256,.5)]*sides);smooth_faces.append(False)

for sign,side in ((-1,'L'),(1,'R')):
    x=sign*1.30
    rings([(x,.06,1.0,.70,.69),(x,.05,3.5,.73,.72),(x,.04,6.8,.86,.82),
           (x,.02,9.4,.98,.90),(x,.02,12.55,1.03,.96)],limbs_weight(side,'leg'),sides=16)
    # Low broad feet, separated visibly for planted stepping.
    rings([(x,-.54,.10,.74,1.33),(x,-.54,.35,.85,1.42),(x,-.48,.91,.80,1.30),
           (x,-.15,1.37,.69,.84)],{'foot.'+side:1.},sides=14)
    sx=sign*2.6
    rings([(sx+sign*.31,0.,10.82,.44,.39),(sx+sign*.29,0.,11.28,.48,.43),
           (sx+sign*.25,0.,13.2,.56,.50),(sx+sign*.18,0.,14.9,.68,.60),
           (sx+sign*.08,.03,17.4,.82,.71),(sx,.04,18.75,.88,.78),
           (sx-sign*.20,.05,19.30,.68,.65),(sx-sign*.50,.05,19.66,.45,.46)],limbs_weight(side,'arm'),sides=16)
    # Pale exposed palm with a clear thumb; the four fingertips are short,
    # rounded and joined at the palm, not separate sticks.
    hx=sx+sign*.31
    rings([(hx,-.02,9.91,.38,.29),(hx,-.02,10.25,.46,.34),(hx,-.01,10.85,.43,.35),
           (hx,.0,11.15,.36,.31)],{'hand.'+side:1.},'skin',sides=14)
    for index,off in enumerate((-.27,-.09,.09,.27)):
        top=10.08;length=(.50,.62,.60,.48)[index];px=hx+off
        rings([(px,-.035,top-length,.072,.105),(px,-.035,top-length*.78,.105,.14),
               (px,-.035,top,.115,.15)],{'hand.'+side:1.},'skin',sides=8)
    # Thumb angles inward against the other fingers.
    rings([(hx-sign*.52,-.10,10.06,.11,.13),(hx-sign*.42,-.08,10.40,.16,.16),
           (hx-sign*.31,-.04,10.72,.16,.16)],{'hand.'+side:1.},'skin',sides=8)

mesh=bpy.data.meshes.new('Chorus / single weighted figure');mesh.from_pydata(vertices,[],faces);mesh.update()
body=bpy.data.objects.new('Chorus / grasper',mesh);scene.collection.objects.link(body);mesh.materials.append(material)
uv=mesh.uv_layers.new(name='Chorus atlas')
for poly,coords,soft in zip(mesh.polygons,uvs,smooth_faces):
    poly.use_smooth=soft
    for index,coord in zip(poly.loop_indices,coords):uv.data[index].uv=coord
for bone in rig.data.bones:
    group=body.vertex_groups.new(name=bone.name)
    for index,weight in enumerate(weights):
        if weight.get(bone.name,0.)>0:group.add([index],weight[bone.name],'REPLACE')
body.parent=rig;body.modifiers.new('Chorus skin','ARMATURE').object=rig

if DRAFT:
    action=bpy.data.actions.new('enemy_idle');action.use_fake_user=True
    rig.animation_data_create();rig.animation_data.action=action
    for bone in rig.pose.bones:
        bone.rotation_mode='QUATERNION'
        for frame in (0,120):
            bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone.name)
            bone.keyframe_insert('location',frame=frame,group=bone.name)
    clips={'enemy_idle':2.}
else:
    from chorus_grasper_animation import apply_actions
    clips=apply_actions(rig)
rig.animation_data.action=bpy.data.actions['enemy_idle'];scene.frame_set(0);scene.frame_end=150
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'chorus_grasper.blend'))
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);body.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'chorus_grasper.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_animations=True,export_force_sampling=True,export_animation_mode='ACTIONS',
    export_optimize_animation_size=False,export_frame_range=False,export_skins=True)
manifest={'chorus_grasper':{'clips':clips,'vertices':len(vertices),'triangles':sum(len(f)-2 for f in faces),
          'bones':len(rig.data.bones),'height':27.32,'atlas':'chorus_grasper_atlas.png',
          'reference':'Far-left figure, The Chorus; artdev/ChorusReference.jpg',
          'description':'Pale large-faced ink-dark figure, slightly taller than the player.'}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('CHORUS GRASPER',json.dumps(manifest))
