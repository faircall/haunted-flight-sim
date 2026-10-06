"""Blender background authoring for the rainy back-seat intro.

Boxy silver sedan inspired by artdev/car_reference.png. Original procedural
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
        data.from_pydata([(p[0],-p[2],p[1]) for p in self.v],[],self.f);data.update()
        obj=bpy.data.objects.new(self.name,data);bpy.context.scene.collection.objects.link(obj);data.materials.append(mat)
        uv=data.uv_layers.new(name='Colour atlas')
        for polygon,coords in zip(data.polygons,self.uv):
            for index,value in zip(polygon.loop_indices,coords):uv.data[index].uv=value
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.gltf(filepath=str(OUT/(self.name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[self.name]=dict(vertices=len(self.v),triangles=sum(len(f)-2 for f in self.f))
        return obj


car=Mesh('sedan')
car.box((0,.36,-.04),(1.93,.12,2.75),'plastic')
car.box((0,1.63,-.02),(1.90,.065,2.38),'liner')
car.box((0,1.675,-.02),(2.02,.025,2.48),'silver')
for sign in (-1,1):
    x=sign*.99
    car.box((x,.67,-.02),(.12,.5,2.80),'plastic')
    car.box((x,.90,-.02),(.16,.07,2.70),'rubber')
    car.box((sign*.92,1.58,-.025),(.08,.08,2.35),'liner')
    car.beam((sign*.97,.94,-1.62),(sign*.85,1.59,-1.17),.09,.09,'liner')
    car.box((sign*.975,1.26,.12),(.12,.65,.11),'liner')
    car.beam((sign*.98,.96,1.47),(sign*.86,1.59,1.13),.12,.12,'liner')
    for z in (-.5,.76):
        car.box((sign*.93,.70,z),(.07,.13,.65),'fabric')
        car.box((sign*.87,.78,z),(.13,.055,.36),'plastic')
        car.box((sign*.877,.845,z-.14),(.04,.025,.13),'chrome')
        car.box((sign*.91,.81,z+.17),(.07,.06,.035),'plastic')
    car.box((sign*.82,1.51,.69),(.025,.025,.25),'plastic')
    car.box((sign*.44,1.54,-1.04),(.57,.07,.29),'liner')
car.box((0,.89,-1.40),(1.76,.25,.48),'plastic')
car.box((-.45,.963,-1.149),(.53,.235,.035),'gauges')
car.box((.03,.81,-1.142),(.29,.13,.035),'radio')
car.box((.44,.78,-1.15),(.47,.15,.035),'plastic')
car.box((.44,.795,-1.125),(.15,.016,.016),'chrome')
for x in (-.15,.18,.40,.66):
    car.box((x,.975,-1.168),(.13,.045,.023),'rubber')
    for dx in (-.035,0,.035):car.box((x+dx,.976,-1.150),(.008,.035,.003),'chrome')
car.box((0,.57,-.72),(.30,.30,.70),'plastic')
car.beam((0,.67,-.71),(0,.82,-.69),.025,.025,'rubber')
car.ellipsoid((0,.83,-.69),(.037,.035,.043),'plastic',8,3)
car.box((0,.65,-.40),(.28,.035,.26),'fabric')
car.box((0,1.405,-1.095),(.265,.079,.055),'plastic')
car.box((0,1.406,-1.064),(.235,.05,.009),'chrome')
car.beam((0,1.41,-1.11),(0,1.57,-1.20),.018,.018,'rubber')
car.box((0,1.585,.51),(.17,.022,.085),'light')
car.box((0,.89,-2.13),(1.85,.10,1.08),'silver')
car.box((0,.87,1.91),(1.93,.17,.93),'silver')
car.box((0,1.03,1.26),(1.80,.075,.29),'fabric')
for x in (-.45,.45):
    car.box((x,.58,-.38),(.68,.19,.66),'fabric')
    car.beam((x,.68,-.015),(x,1.14,.09),.67,.155,'fabric')
    car.box((x,1.22,.09),(.37,.21,.13),'fabric')
    for dx in (-.09,.09):car.beam((x+dx,1.10,.09),(x+dx,1.15,.09),.015,.015,'chrome')
car.box((0,.60,.93),(1.66,.22,.58),'fabric')
car.beam((0,.66,1.19),(0,1.17,1.36),1.68,.19,'fabric')
car.export()

# Closed bodywork with actual wheel arches and open window apertures. It is a
# separate mesh so the interior keeps its existing, uncluttered first-person view.
shell=Mesh('sedan_exterior')
shell.box((0,.32,-.12),(1.84,.14,4.88),'rubber')
for sign in (-1,1):
    x=sign*1.035
    shell.box((x,.86,-.13),(.045,.16,4.91),'silver')
    for lo,hi in ((-2.59,-2.08),(-1.22,1.09),(1.95,2.36)):
        shell.box((x,.565,(lo+hi)/2),(.055,.49,hi-lo),'silver')
    for axle in (-1.65,1.52):
        for i in range(10):
            a=math.pi*i/10;b=math.pi*(i+1)/10
            za,zb=axle+.43*math.cos(a),axle+.43*math.cos(b)
            ya,yb=.34+.43*math.sin(a),.34+.43*math.sin(b)
            points=[(x,ya,za),(x,yb,zb),(x,.80,zb),(x,.80,za)]
            shell.face(points if sign==1 else list(reversed(points)),'silver')
    shell.box((x+sign*.01,.58,-.10),(.025,.045,4.92),'rubber')
    shell.box((x,.35,-.06),(.055,.08,2.17),'silver')
    for z in (-.58,.74):
        shell.box((x+sign*.04,.847,z),(.03,.04,.20),'rubber')
        shell.box((x+sign*.06,.855,z),(.03,.018,.16),'chrome')
    for z in (-1.18,.12,1.09):shell.box((x+sign*.03,.61,z),(.008,.41,.012),'plastic')
    shell.beam((sign*.986,.945,-1.625),(sign*.865,1.622,-1.16),.055,.06,'silver')
    shell.box((sign*.999,1.27,.12),(.045,.66,.13),'rubber')
    shell.beam((sign*1.00,.98,1.475),(sign*.88,1.625,1.115),.11,.09,'silver')
    shell.box((sign*.95,1.61,-.02),(.08,.025,2.39),'silver')
    shell.beam((sign*.98,1.015,-1.19),(sign*1.15,1.015,-1.16),.06,.05,'rubber')
    shell.box((sign*1.17,1.055,-1.16),(.16,.12,.20),'silver')
    shell.box((sign*1.17,1.055,-1.05),(.12,.075,.012),'chrome')
shell.box((0,.68,-2.62),(2.03,.33,.10),'silver')
shell.box((0,.52,-2.68),(2.11,.14,.11),'rubber')
shell.box((0,.685,-2.678),(.86,.17,.024),'rubber')
for x in (-.31,-.19,-.07,.07,.19,.31):shell.box((x,.688,-2.698),(.008,.13,.006),'chrome')
shell.box((0,.64,2.365),(2.035,.40,.08),'silver')
shell.box((0,.45,2.43),(2.12,.14,.12),'rubber')
for x in (-.79,.79):
    shell.box((x,.72,2.414),(.39,.19,.035),'red')
    shell.box((x,.778,2.435),(.35,.044,.018),'light')
for z in (-2.743,2.439):
    shell.box((0,.535 if z<0 else .67,z),(.42,.11,.016),'blue')
    for x in (-.145,-.087,-.029,.029,.087,.145):shell.box((x,.535 if z<0 else .67,z+(-.011 if z<0 else .011)),(.022,.065,.006),'liner')
shell.export()

lights=Mesh('headlamps')
for x in (-.72,.72):
    lights.box((x,.733,-2.687),(.43,.17,.035),'liner')
    # Corner lenses wrap onto the front fenders and remain visible side-on.
    lights.box((math.copysign(1.067,x),.738,-2.49),(.026,.12,.22),'light')
lights.export()

# Wheel axis is X. Twelve sides retain the chunky PS1 silhouette while the
# inset wheel covers, rims and rubber sidewalls survive the wider camera cuts.
tyre=Mesh('tyre')
for i in range(12):
    a=math.tau*i/12;b=math.tau*(i+1)/12
    for xa,xb,ra,rb,tile in ((-.13,.13,.32,.32,'rubber'),(.13,.145,.32,.245,'rubber'),(-.145,-.13,.245,.32,'rubber')):
        tyre.face([(xa,math.sin(a)*ra,math.cos(a)*ra),(xb,math.sin(a)*rb,math.cos(a)*rb),
                   (xb,math.sin(b)*rb,math.cos(b)*rb),(xa,math.sin(b)*ra,math.cos(b)*ra)],tile)
    for sign in (-1,1):
        points=[(sign*.146,0,0),(sign*.146,math.sin(a)*.242,math.cos(a)*.242),(sign*.146,math.sin(b)*.242,math.cos(b)*.242)]
        tyre.face(points if sign==-1 else list(reversed(points)),'chrome')
        # Small dark slots break up the broad wheel cover without extra textures.
        c=(a+b)/2;tyre.box((sign*.15,math.sin(c)*.173,math.cos(c)*.173),(.008,.035,.035),'plastic')
tyre.export()


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
    person.beam((x-.17,1.20,-.485),(x+.13,.78,-.525),.032,.014,'rubber')
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

wheel=Mesh('steering')
up=Vector((0,.74,-.673));right=Vector((1,0,0));normal=right.cross(up)
rows=[]
for i in range(16):
    direction=right*math.cos(math.tau*i/16)+up*math.sin(math.tau*i/16)
    rows.append([direction*(.205+.017*math.cos(math.tau*j/5))+normal*.017*math.sin(math.tau*j/5) for j in range(5)])
for i in range(16):
    for j in range(5):wheel.face([rows[i][j],rows[(i+1)%16][j],rows[(i+1)%16][(j+1)%5],rows[i][(j+1)%5]],'rubber')
wheel.box((0,0,0),(.10,.07,.07),'plastic')
for sign in (-1,1):wheel.beam((0,0,0),(sign*.19,0,0),.032,.026,'rubber')
wheel.export()

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
(OUT/'manifest.json').write_text(json.dumps(dict(models=models,reference='artdev/car_reference.png',
    cabin_camera=[.02,1.34,.65],texture=[256,256],audio='Original synthesized placeholder rain, engine and wiper'),indent=2)+'\n',newline='\n')
print('Intro assets exported to',OUT)
