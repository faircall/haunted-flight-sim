"""Blender background authoring for the rainy back-seat intro.

Charcoal Santana inspired by the three artdev car references. Original procedural
textures, anonymous seated colleagues, roadside trees and a temple approach gate.
Run with Blender --background --factory-startup --python this_file.py.
"""
from pathlib import Path
import math
import json
import random
import wave
from array import array
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'art'/'temple'/'intro'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.preferences.filepaths.save_version=0

# One 256px atlas; each material patch is an original 32px texture.
palette=dict(fabric=(.18,.20,.19),plastic=(.095,.105,.10),liner=(.40,.39,.34),
    silver=(.36,.40,.39),rubber=(.027,.035,.032),chrome=(.38,.43,.43),
    olive=(.16,.19,.13),brown=(.22,.16,.115),skin=(.60,.46,.33),hair=(.035,.031,.023),
    leaf=(.12,.18,.10),bark=(.17,.12,.08),stone=(.23,.27,.24),red=(.35,.055,.035),
    wood=(.15,.095,.065),light=(.61,.43,.16),gauges=(.023,.036,.03),radio=(.045,.065,.042),blue=(.06,.135,.20))
tiles={name:(i%8,i//8) for i,name in enumerate(palette)}
atlas=bpy.data.images.new('Sedan / original 256px atlas',width=256,height=256)
pixels=[];rng=random.Random(1403);names=list(palette)
for y in range(256):
    for x in range(256):
        i=y//32*8+x//32;name=names[i] if i<len(names) else 'plastic'
        base=palette[name];u=x%32;v=y%32
        noise=rng.choice((-.015,-.007,0,.007,.015))
        if name=='fabric':noise+=.016 if (u+v)%3==0 else -.005
        if name in ('wood','bark'):noise+=.02*math.sin(u*.7+math.sin(v*.14))
        if name=='liner':noise*=.3
        if name=='gauges':
            for cx in (9,23):
                r=math.hypot(u-cx,v-16)
                if 5.5<r<7 or (abs(u-cx)<1 and 13<v<20):base=(.61,.69,.59)
                if abs(u-cx-(v-16)*.6)<.8 and 16<v<22:base=(.7,.34,.12)
        if name=='radio' and (8<v<13 and 4<u<27):base=(.31,.43,.22) if u%4 else (.08,.11,.065)
        pixels.extend((*[max(0,min(1,c+noise)) for c in base],1))
atlas.pixels=pixels;atlas.filepath_raw=str(OUT/'sedan.png');atlas.file_format='PNG';atlas.save();atlas.pack()
mat=bpy.data.materials.new('Sedan / crisp cloth and worn plastic');mat.use_nodes=True
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;node.interpolation='Closest'
mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.9
models={}


class Mesh:
    def __init__(self,name):self.name=name;self.v=[];self.f=[];self.uv=[]

    def face(self,points,tile):
        start=len(self.v);self.v.extend(points);self.f.append(list(range(start,start+len(points))))
        tx,ty=tiles[tile];lo=((tx*32+1)/256,(ty*32+1)/256);hi=((tx*32+31)/256,(ty*32+31)/256)
        uv=[lo,(hi[0],lo[1]),hi,(lo[0],hi[1])]
        self.uv.append(uv if len(points)==4 else [(lo[0]+(hi[0]-lo[0])*(.5+.45*math.cos(math.tau*i/len(points))),
                                                    lo[1]+(hi[1]-lo[1])*(.5+.45*math.sin(math.tau*i/len(points)))) for i in range(len(points))])

    def box(self,c,size,tile):
        x,y,z=c;w,h,d=[s/2 for s in size]
        p=[(x+a*w,y+b*h,z+c*d) for a,b,c in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
        for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([p[i] for i in face],tile)

    def beam(self,a,b,width,depth,tile):
        a,b=Vector(a),Vector(b);up=(b-a).normalized()
        right=up.cross(Vector((0,0,1)))
        if right.length<.01:right=up.cross(Vector((1,0,0)))
        right.normalize();across=right.cross(up).normalized()
        p=[point+right*r*width/2+across*d*depth/2 for point in (a,b) for r,d in ((-1,-1),(1,-1),(1,1),(-1,1))]
        for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([p[i] for i in reversed(face)],tile)

    def ellipsoid(self,c,size,tile,sides=10,rings=5):
        cx,cy,cz=c;rx,ry,rz=size
        rows=[]
        for i in range(rings+1):
            a=-math.pi/2+math.pi*i/rings
            rows.append([(cx+rx*math.cos(a)*math.cos(math.tau*j/sides),cy+ry*math.sin(a),cz+rz*math.cos(a)*math.sin(math.tau*j/sides)) for j in range(sides)])
        for i in range(rings):
            for j in range(sides):self.face([rows[i][j],rows[i+1][j],rows[i+1][(j+1)%sides],rows[i][(j+1)%sides]],tile)

    def cone(self,c,radius,height,tile,sides=8):
        cx,cy,cz=c;ring=[(cx+radius*math.cos(math.tau*j/sides),cy,cz+radius*math.sin(math.tau*j/sides)) for j in range(sides)]
        for j in range(sides):self.face([ring[j],(cx,cy+height,cz),ring[(j+1)%sides]],tile)
        self.face(ring,tile)

    def export(self):
        data=bpy.data.meshes.new(self.name)
        # Builder coordinates are the game's X/up/Z; Blender is X/Y/up.
        if getattr(self,'smooth',False):
            vertices=[];lookup={};remap=[]
            for p in self.v:
                key=tuple(round(float(v),6) for v in p)
                if key not in lookup:lookup[key]=len(vertices);vertices.append((p[0],-p[2],p[1]))
                remap.append(lookup[key])
            data.from_pydata(vertices,[],[[remap[i] for i in f] for f in self.f])
            for polygon in data.polygons:polygon.use_smooth=True
        else:data.from_pydata([(p[0],-p[2],p[1]) for p in self.v],[],self.f)
        data.update()
        obj=bpy.data.objects.new(self.name,data);bpy.context.scene.collection.objects.link(obj);data.materials.append(mat)
        uv=data.uv_layers.new(name='Colour atlas')
        for polygon,coords in zip(data.polygons,self.uv):
            for index,value in zip(polygon.loop_indices,coords):uv.data[index].uv=value
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.gltf(filepath=str(OUT/(self.name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[self.name]=dict(vertices=len(self.v),triangles=sum(len(f)-2 for f in self.f))
        return obj


import sys
sys.path.insert(0,str(ROOT))
from build_santana_car import build as build_car
car_report=build_car(OUT,models)


for name,x,shirt in (('driver',-.45,'olive'),('colleague',.45,'brown')):
    person=Mesh(name)
    person.ellipsoid((x,.76,-.39),(.225,.15,.18),'plastic',10,4)
    person.ellipsoid((x,1.04,-.35),(.225,.29,.145),shirt,10,5)
    for sign in (-1,1):
        hip=(x+sign*.115,.74,-.39);knee=(x+sign*.13,.67,-.92);ankle=(x+sign*.13,.38,-1.12)
        person.beam(hip,knee,.17,.19,'plastic');person.beam(knee,ankle,.14,.15,'plastic')
        person.box((x+sign*.13,.365,-1.18),(.15,.10,.29),'rubber')
        shoulder=(x+sign*.20,1.19,-.34)
        elbow=(x+sign*.235,.985,-.57)
        hand=(x+sign*.19,1.025,-.95) if name=='driver' else (x+sign*.12,.77,-.69)
        person.beam(shoulder,elbow,.13,.14,shirt);person.beam(elbow,hand,.115,.12,shirt)
        person.ellipsoid(hand,(.052,.05,.078),'skin',8,3)
    from g_santana_geometry import front_belt_path,FRONT_ACTOR_POSITION,ACTOR_SCALE,CENTER_POST_Z
    sign=-1 if x<0 else 1
    path=front_belt_path(sign)
    for a,b in zip(path,path[1:]):person.beam(a,b,.041,.009,'rubber')
    def unfit(p):return tuple((v-d)/ACTOR_SCALE for v,d in zip(p,FRONT_ACTOR_POSITION))
    lap=[path[-1],(x-sign*.10,.80,-.575),(x+sign*.09,.80,-.575),
         (x+sign*.22,.75,-.48),unfit((sign*.706,.399,CENTER_POST_Z-.032))]
    for a,b in zip(lap,lap[1:]):person.beam(a,b,.041,.009,'rubber')
    person.export()
    # Heads are separate rigid objects for subtle glances; intentionally blank.
    head=Mesh(name+'_head')
    head.ellipsoid((0,0,0),(.135,.19,.145),'skin',10,6)
    head.ellipsoid((0,.06,.018),(.138,.145,.144),'hair',10,5)
    head.box((0,-.19,0),(.10,.11,.095),'skin');head.export()

lap=Mesh('player_lap')
for sign in (-1,1):
    lap.beam((sign*.15,.69,.71),(sign*.18,.65,.18),.20,.22,'brown')
    lap.beam((sign*.18,.65,.18),(sign*.19,.39,-.03),.14,.16,'brown')
    lap.box((sign*.19,.365,-.085),(.16,.10,.28),'brown')
    lap.beam((sign*.22,.84,.60),(sign*.19,.72,.36),.14,.16,'blue')
    lap.ellipsoid((sign*.17,.745,.34),(.055,.035,.09),'skin',8,3)
lap.export()

# Reuse the accepted player mesh, face atlas and skeleton, authored into a
# seated pose here. No player source geometry or locomotion clips are modified.
source=ROOT/'photo_asset_pipeline'/'temple3d'/'living'/'build.py'
prefix=source.read_text().split('\nfor clip, frames in ')[0]
prefix=prefix.replace("bpy.ops.object.select_all(action='SELECT')\nbpy.ops.object.delete(use_global=False)", '')
namespace={'__file__':str(source),'__name__':'intro_seated_player'}
exec(compile(prefix,str(source),'exec'),namespace)
rig=namespace['rig'];body=namespace['body'];posed=namespace['posed_bone'];gait=namespace['gait']
scale=.07
def seat_point(x,y,z):return Vector((x,-z,y))/scale
hip=seat_point(0,.70,.82);neck=hip+Vector((0,0,gait.TORSO))
poses={}
posed('root',hip,hip+Vector((0,0,2)),poses,math.pi)
posed('spine',hip,neck,poses,math.pi)
# A relaxed seated neck settles slightly into the shirt collar.
head_base=neck-Vector((0,0,.035/scale))
posed('head',head_base,head_base+Vector((0,0,namespace['PLAYER_HEIGHT']-namespace['neck_z'])),poses,math.pi-math.radians(65))
for sign,suffix in ((-1,'L'),(1,'R')):
    x=-sign*gait.HIP_HALF_WIDTH*scale
    h=seat_point(x,.70,.82);k=seat_point(-sign*.15,.68,.414);a=seat_point(-sign*.15,.36,.164)
    posed('thigh.'+suffix,h,k,poses,math.pi)
    posed('shin.'+suffix,k,a,poses,math.pi)
    posed('foot.'+suffix,a,a+Vector((0,1.5,0)),poses,math.pi)
    shoulder=seat_point(-sign*gait.SHOULDER_HALF_WIDTH*scale,.70+(gait.SHOULDER_HEIGHT-namespace['hip_z'])*scale,.82)
    elbow=seat_point(-sign*.235,.905,.65);wrist=seat_point(-sign*.15,.76,.43)
    posed('arm.'+suffix,shoulder,elbow,poses,math.pi)
    posed('forearm.'+suffix,elbow,wrist,poses,math.pi)
    posed('hand.'+suffix,wrist,seat_point(-sign*.15,.75,.33),poses,math.pi)
bpy.context.view_layer.update()
evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
data=bpy.data.meshes.new_from_object(evaluated)
for vertex in data.vertices:vertex.co*=scale
seated=bpy.data.objects.new('Player / seated rear-window portrait',data)
bpy.context.scene.collection.objects.link(seated)
bpy.ops.object.select_all(action='DESELECT');seated.select_set(True);bpy.context.view_layer.objects.active=seated
bpy.ops.export_scene.gltf(filepath=str(OUT/'player_seated.glb'),export_format='GLB',use_selection=True,export_animations=False)
models['player_seated']=dict(vertices=len(data.vertices),triangles=sum(len(p.vertices)-2 for p in data.polygons),source='Accepted player mesh and face atlas')
# Keep the seated rig in the editable kit, outside the exported stationary car.
rig.scale=(scale,scale,scale)
rig['Intro editing']='Unhide this rig and its skinned body to edit the seated pose; hide the baked portrait mesh while editing.'
rig.hide_render=True;rig.hide_viewport=True;body.hide_render=True;body.hide_viewport=True

pine=Mesh('pine');pine.beam((0,0,0),(0,5.7,0),.28,.26,'bark')
for y,r,h in ((1.3,1.55,3.2),(2.5,1.3,3.),(3.8,.95,2.6),(5.0,.53,1.8)):pine.cone((0,y,0),r,h,'leaf',9)
pine.export()
tree=Mesh('broadleaf');tree.beam((0,0,0),(.25,4.4,0),.32,.28,'bark')
for c,size in (((.1,4.6,0),(1.65,1.8,1.5)),((-.8,3.5,.2),(1.3,1.4,1.2)),((1.0,3.8,-.3),(1.3,1.5,1.1))):tree.ellipsoid(c,size,'leaf',7,4)
tree.export()
rock=Mesh('rock');rock.ellipsoid((0,.35,0),(.8,.7,.75),'stone',7,3);rock.export()

mountain=Mesh('mountain');mr=random.Random(28)
rows=[]
for y,r in ((0,1.),(.22,.85),(.50,.58),(.76,.33),(1.,.025)):
    rows.append([(math.cos(math.tau*j/11)*r*(1+mr.random()*.18),y+mr.random()*.045,math.sin(math.tau*j/11)*r) for j in range(11)])
for i in range(4):
    for j in range(11):mountain.face([rows[i][j],rows[i+1][j],rows[i+1][(j+1)%11],rows[i][(j+1)%11]],'stone')
mountain.export()

house=Mesh('house');house.box((0,1.7,0),(4.2,3.4,3.4),'liner')
for sign in (-1,1):
    points=[(-2.4,3.35,sign*1.9),(2.4,3.35,sign*1.9),(2.4,4.6,0),(-2.4,4.6,0)]
    house.face(points if sign==1 else list(reversed(points)),'plastic')
house.box((0,1.0,1.715),(.8,2.0,.04),'wood')
for x in (-1.35,1.25):house.box((x,1.9,1.72),(.75,.8,.035),'rubber')
house.export()
gate=Mesh('gate')
for x in (-2.5,2.5):
    gate.box((x,1.6,0),(.35,3.2,.35),'wood');gate.box((x,.15,0),(.6,.3,.6),'stone')
gate.box((0,3.0,0),(5.7,.28,.5),'wood')
for sign in (-1,1):
    points=[(-3.25,3.18,sign*.9),(3.25,3.18,sign*.9),(2.9,3.80,0),(-2.9,3.80,0)]
    gate.face(points if sign==1 else list(reversed(points)),'plastic')
    for x in (-3.,3.):gate.beam((x,3.2,sign*.9),(x+math.copysign(.25,x),3.42,sign*1.1),.13,.15,'plastic')
for x in (-1.9,1.9):
    gate.beam((x,3.,0),(x,2.6,0),.024,.024,'rubber')
    gate.ellipsoid((x,2.36,0),(.22,.30,.22),'red',8,4)
gate.box((0,2.65,.29),(1.85,.48,.065),'wood');gate.export()

from build_intro_landscape import build as build_landscape
landscape_report=build_landscape(OUT,models,Mesh)

# Seamless, quiet placeholder beds and a separate wiper swish. Generated here
# so this intro doesn't depend on the untracked development sound collection.
def wav(name,samples,rate=22050):
    packed=array('h',(int(max(-1,min(1,s)) * 32767) for s in samples))
    with wave.open(str(OUT/(name+'.wav')),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate);stream.writeframes(packed.tobytes())

rate=22050;seconds=8;n=rate*seconds;ar=random.Random(433);low=0.;rain=[];engine=[]
for i in range(n):
    t=i/rate;noise=ar.uniform(-1,1);low=.92*low+.08*noise
    rain.append((low*.65+noise*.065)*(1+.12*math.sin(math.tau*t/8)))
    engine.append(.13*math.sin(math.tau*52*t)+.045*math.sin(math.tau*104*t)+.018*math.sin(math.tau*156*t)+low*.14)
for samples in (rain,engine):
    # Correct the small seam offset smoothly; preserve the motor's periodic
    # harmonics instead of splicing a differently phased chunk over the tail.
    count=400;difference=samples[-1]-samples[0]
    for i in range(count):
        a=i/(count-1);samples[n-count+i]-=difference*a*a*(3-2*a)
wav('rain_cabin',rain);wav('engine',engine)
swish=[];ar=random.Random(7);low=0
for i in range(int(rate*.32)):
    t=i/(rate*.32);noise=ar.uniform(-1,1);low=.6*low+.4*noise
    swish.append((low*.16+.035*math.sin(i/rate*math.tau*410))*math.sin(math.pi*t)**2)
wav('wiper',swish)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'intro_kit.blend'))
from g_santana_geometry import CABIN_EYE
(OUT/'manifest.json').write_text(json.dumps(dict(models=models,car=car_report,landscape=landscape_report,reference='artdev/car_reference.png',
    cabin_camera=list(CABIN_EYE),texture=[256,256],audio='Original synthesized placeholder rain, engine and wiper'),indent=2)+'\n',newline='\n')
print('Intro assets exported to',OUT)
