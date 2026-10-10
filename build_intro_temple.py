"""Blender-authored terraced arrival complex. Standalone rebuild preserves the car.

Blender --background --factory-startup --python build_intro_temple.py
The playable water courtyard remains independent of this cinematic approach.
"""
from pathlib import Path
import json
import math
import random
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from g_intro_landscape import STAIR_COUNT,STAIR_RISE,STAIR_TREAD,STAIR_FLIGHT,STAIR_LANDING,stair_z


def build(out,models):
    palette=dict(stone=(.39,.42,.36),cap=(.52,.54,.46),red=(.37,.105,.066),plaster=(.56,.51,.38),
                 roof=(.20,.27,.24),ridge=(.28,.34,.27),wood=(.18,.115,.075),dark=(.033,.041,.035),
                 green=(.15,.25,.19),gold=(.46,.34,.14),lamp=(.65,.36,.12),moss=(.24,.31,.17))
    names=list(palette);rng=random.Random(913);pixels=[]
    for y in range(256):
        for x in range(256):
            index=(y//64)*4+x//64;name=names[index] if index<len(names) else 'stone'
            c=palette[name];u=x%64;v=y%64;noise=rng.uniform(-.018,.018)
            if name in ('stone','cap'):
                row=v//16;edge=(u+(row%2)*16)%32
                noise+=-.095 if v%16<2 or edge<2 else .025*math.sin(row*6+u//32)
                noise-=.025*math.sin(u*.19+v*.13)
            if name in ('roof','ridge'):
                noise+=.045*math.cos(u*math.tau/16)-(.055 if v%16<2 else 0)
            if name=='red':
                noise+=-.035*math.sin(u*.15+v*.03)
                if v<8 and rng.random()<.3:c=palette['plaster']
            if name in ('wood','green'):noise+=.028*math.sin(u*.4+math.sin(v*.13))
            pixels.extend((*[max(.005,min(.95,a+noise)) for a in c],1))
    atlas=bpy.data.images.new('Temple / weathered 256px atlas',width=256,height=256)
    atlas.pixels=pixels;atlas.filepath_raw=str(out/'temple_approach.png');atlas.file_format='PNG';atlas.save();atlas.pack()
    material=bpy.data.materials.new('Temple / painted stone, red timber and grey tiles');material.use_nodes=True
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;node.interpolation='Closest'
    bsdf=material.node_tree.nodes.get('Principled BSDF');material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value=.94

    class Mesh:
        def __init__(self,name):self.name=name;self.v=[];self.f=[];self.uv=[]
        def face(self,p,tile):
            if len(p)==4 and tile in ('stone','cap','plaster'):
                a,b,c,d=map(Vector,p);u=max((b-a).length,(c-d).length);v=max((d-a).length,(c-b).length)
                if max(u,v)>5:
                    nx=max(1,math.ceil(u/4));ny=max(1,math.ceil(v/3))
                    def point(x,y):return a.lerp(b,x).lerp(d.lerp(c,x),y)
                    for j in range(ny):
                        for i in range(nx):self.face([point(i/nx,j/ny),point((i+1)/nx,j/ny),point((i+1)/nx,(j+1)/ny),point(i/nx,(j+1)/ny)],tile)
                    return
            start=len(self.v);self.v.extend(p);self.f.append(list(range(start,start+len(p))))
            index=names.index(tile);x=index%4/4;y=index//4/4;lo=(x+1/256,y+1/256);hi=(x+63/256,y+63/256)
            self.uv.append([lo,(hi[0],lo[1]),hi,(lo[0],hi[1])] if len(p)==4 else
                           [(x+.125+.115*math.cos(i*math.tau/len(p)),y+.125+.115*math.sin(i*math.tau/len(p))) for i in range(len(p))])
        def box(self,c,size,tile):
            x,y,z=c;w,h,d=[v/2 for v in size]
            p=[(x+a*w,y+b*h,z+c*d) for a,b,c in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
            for ids in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([p[i] for i in ids],tile)
        def beam(self,a,b,width,depth,tile):
            a,b=Vector(a),Vector(b);axis=(b-a).normalized();right=axis.cross(Vector((0,0,1)))
            if right.length<.01:right=axis.cross(Vector((1,0,0)))
            right.normalize();across=axis.cross(right);center=(a+b)/2
            points=[p+right*r*width/2+across*d*depth/2 for p in (a,b) for r,d in ((-1,-1),(1,-1),(1,1),(-1,1))]
            for ids in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                face=[points[i] for i in ids];normal=(face[1]-face[0]).cross(face[2]-face[0])
                if normal.dot(sum(face,Vector())/4-center)<0:face.reverse()
                self.face(face,tile)
        def column(self,x,y,z,radius,height,tile):
            for i in range(10):
                a=i*math.tau/10;b=(i+1)*math.tau/10
                self.face([(x+radius*math.cos(a),y,z+radius*math.sin(a)),(x+radius*math.cos(a),y+height,z+radius*math.sin(a)),
                           (x+radius*math.cos(b),y+height,z+radius*math.sin(b)),(x+radius*math.cos(b),y,z+radius*math.sin(b))],tile)
        def export(self):
            # Raylib's mesh indices are uint16; keep every exported primitive
            # below that limit even before glTF merges duplicate vertices.
            groups=[];group=[];count=0
            for face,uv in zip(self.f,self.uv):
                if count+len(face)>45000:groups.append(group);group=[];count=0
                group.append((face,uv));count+=len(face)
            if group:groups.append(group)
            objects=[]
            for part,group in enumerate(groups):
                vertices=[];faces=[];coords=[]
                for ids,uv in group:
                    start=len(vertices);vertices.extend([(self.v[i][0],-self.v[i][2],self.v[i][1]) for i in ids])
                    faces.append(list(range(start,len(vertices))));coords.append(uv)
                mesh=bpy.data.meshes.new(self.name+str(part));mesh.from_pydata(vertices,[],faces);mesh.update()
                obj=bpy.data.objects.new(self.name+str(part),mesh);bpy.context.scene.collection.objects.link(obj);mesh.materials.append(material)
                layer=mesh.uv_layers.new(name='Painted atlas')
                for poly,uv in zip(mesh.polygons,coords):
                    for i,p in zip(poly.loop_indices,uv):layer.data[i].uv=p
                objects.append(obj)
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:obj.select_set(True)
            bpy.context.view_layer.objects.active=objects[0]
            bpy.ops.export_scene.gltf(filepath=str(out/(self.name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
            models[self.name]=dict(vertices=len(self.v),triangles=sum(len(f)-2 for f in self.f),texture=[256,256])

    front=Mesh('temple_facade');rear=Mesh('temple_halls');lamps=Mesh('temple_lamps')

    def roof(m,x,y,z,width,depth,rise,double=False):
        # Curved hipped planes with swept corners, closed fascia and tile ribs.
        w=width/2;d=depth/2;ridge=max(.35,w-d*.40)
        for sign in (-1,1):
            rows=[]
            for j in range(9):
                t=j/8;half=w*(1-t)+ridge*t
                rows.append([(x+(-1+2*i/24)*half,y+rise*t*t+.44*(1-t)**4+.36*(abs(-1+2*i/24)**8)*(1-t),z+sign*d*(1-t)) for i in range(25)])
            for a,b in zip(rows,rows[1:]):
                for i in range(24):
                    p=[a[i],a[i+1],b[i+1],b[i]];m.face(p if sign==1 else p[::-1],'roof')
            for i in range(25):
                for j in range(0,8,2):m.beam(rows[j][i],rows[j+2][i],.06,.065,'ridge')
            for a,b in zip(rows[0],rows[0][1:]):m.beam(a,b,.17,.24,'ridge')
        for sign in (-1,1):
            tip=(x+sign*ridge,y+rise,z)
            for j in range(10):
                a=-1+2*j/10;b=-1+2*(j+1)/10
                pa=(x+sign*w,y+.44+.36*abs(a)**8,z+a*d);pb=(x+sign*w,y+.44+.36*abs(b)**8,z+b*d)
                m.face([pa,pb,tip] if sign==1 else [pb,pa,tip],'roof');m.beam(pa,pb,.17,.24,'ridge')
            for zsign in (-1,1):m.beam((x+sign*w,y+.8,z+zsign*d),tip,.14,.15,'ridge')
            # Finials suggest ridge guardians without dense sculpted geometry.
            m.beam((x+sign*(ridge-.2),y+rise,z),(x+sign*(ridge+.12),y+rise+.65,z),.18,.22,'ridge')
            m.box((x+sign*(ridge+.18),y+rise+.65,z),(.45,.18,.26),'ridge')
        m.box((x,y+rise+.05,z),(ridge*2,.24,.32),'ridge')
        m.box((x,y+.12,z),(width-.6,.18,depth-.6),'wood')

    def rail(m,x1,z1,x2,z2,y):
        length=math.hypot(x2-x1,z2-z1);count=max(1,round(length/2))
        for i in range(count+1):
            t=i/count;x=x1+(x2-x1)*t;z=z1+(z2-z1)*t
            m.box((x,y+.59,z),(.29,1.18,.29),'cap');m.box((x,y+1.22,z),(.39,.16,.39),'cap')
        m.beam((x1,y+.90,z1),(x2,y+.90,z2),.16,.18,'cap')
        m.beam((x1,y+.30,z1),(x2,y+.30,z2),.13,.16,'stone')

    def hall(m,x,base,z,width,depth,height,bays=5,double=False,open_gate=False):
        m.box((x,base-.28,z),(width+1.2,.56,depth+1.1),'stone')
        # Repeated panels preserve texel density; shadowed porch is real depth.
        bay=width/bays;front_z=z+depth/2
        for i in range(bays):
            xx=x-width/2+bay*(i+.5)
            if open_gate and i==bays//2:
                m.box((xx,base+height*.84,front_z-.9),(bay,height*.32,.50),'red')
                m.box((xx,base+height*.45,z-depth/2),(bay,height*.9,.25),'dark')
            else:
                m.box((xx,base+height/2,front_z-.90),(bay-.12,height,.50),'red')
                m.box((xx,base+height*.52,front_z-.62),(bay*.69,height*.62,.10),'dark')
                for k in range(7):
                    m.box((xx-bay*.32+k*bay*.106,base+height*.52,front_z-.54),(.055,height*.62,.06),'wood')
                for yy in (.24,.39,.54,.69,.81):m.box((xx,base+height*yy,front_z-.53),(bay*.70,.07,.06),'wood')
            for zz in (z-depth/2,):m.box((xx,base+height/2,zz),(bay,height,.40),'red')
        for side in (-1,1):m.box((x+side*width/2,base+height/2,z),(.48,height,depth),'red')
        for i in range(bays+1):
            xx=x-width/2+i*bay
            m.box((xx,base+.15,front_z),(.68,.3,.68),'cap');m.column(xx,base+.3,front_z,.23,height-.3,'red')
            for level in range(3):
                m.box((xx,base+height-.28+level*.22,front_z+.10*level),(.55+.28*level,.15,.68+.26*level),'green')
            m.beam((xx-.42,base+height-.45,front_z),(xx+.42,base+height-.05,front_z),.12,.15,'gold')
        m.box((x,base+height-.14,front_z),(width+.6,.35,.32),'green')
        m.box((x,base+height*.83,front_z+.05),(min(3.2,width*.22),.77,.16),'wood')
        m.box((x,base+height*.84,front_z+.15),(min(2.85,width*.19),.045,.03),'gold')
        roof(m,x,base+height+.3,z,width+3,depth+2.4,2.9 if width>20 else 2.0)
        if double:
            m.box((x,base+height+2.65,z),(width*.60,1.5,depth*.42),'red')
            for side in (-1,1):
                m.box((x,base+height+2.9,z+side*depth*.215),(width*.55,.65,.08),'dark')
                for i in range(9):m.box((x-width*.27+i*width*.0675,base+height+2.9,z+side*depth*.222),(.07,.70,.08),'green')
            roof(m,x,base+height+3.4,z,width*.76,depth*.67,2.6)

    # Fifty-four human-scale steps, split by generous resting platforms.
    for step in range(STAIR_COUNT):
        h=(step+1)*STAIR_RISE;z=stair_z(step)
        front.box((0,h/2,z),(10.8,h,STAIR_TREAD+.015),'stone')
        front.box((0,h-.025,z+.18),(10.9,.055,.09),'cap')
        if step%STAIR_FLIGHT==STAIR_FLIGHT-1 and step<STAIR_COUNT-1:
            front.box((0,h/2,z-STAIR_LANDING/2-.20),(11.6,h,STAIR_LANDING+.1),'stone')
    base=STAIR_COUNT*STAIR_RISE
    for flight in range(3):
        a=flight*STAIR_FLIGHT;b=a+STAIR_FLIGHT-1
        for side in (-1,1):
            x=side*5.8;za=stair_z(a)+.3;zb=stair_z(b)-.3
            front.beam((x,a*STAIR_RISE+.35,za),(x,(b+1)*STAIR_RISE+.35,zb),.65,.7,'stone')
            front.beam((x,a*STAIR_RISE+1.1,za),(x,(b+1)*STAIR_RISE+1.1,zb),.21,.22,'cap')
            for j in range(0,19,3):
                t=j/18;front.box((x,a*STAIR_RISE+(b+1-a)*STAIR_RISE*t+.7,za+(zb-za)*t),(.3,1.1,.3),'cap')
    # Broad stepped retaining terraces, with a lower wall framing the stairway.
    for side in (-1,1):
        for j in range(5):
            y=(j+1)*2.0;z=5.5-j*5.3
            front.box((side*16,y/2,z-2.7),(19.2,y,5.8),'stone')
            front.box((side*16,y+.06,z),(19.5,.22,.64),'cap')
        front.box((side*18,base/2,-26),(25,base,12),'stone')
        front.box((side*19,base+1.4,-22),(22,2.8,.85),'red')
        roof(front,side*19,base+2.8,-22,23,1.6,.65)
        rail(front,side*6,-19.7,side*30,-19.7,base)
    front.box((0,base/2,-27),(12,base,12),'stone')
    hall(front,0,base,-26,19,8,5.1,3,open_gate=True)
    for side in (-1,1):
        hall(front,side*27,base,-30,10,9,5.6,3,double=True)
        # Steles in roofed niches beside the lower stair; scale cues at the foot.
        front.box((side*9,1.0,6),(1.1,2.,.4),'stone')
        front.box((side*9,1.15,6.23),(.73,1.25,.035),'dark')
        roof(front,side*9,2.2,6,2.3,1.4,.6)
    # Successive courtyards ascend behind the entrance. Multiple roof silhouettes
    # are visible from the clearing instead of one enlarged facade rectangle.
    rear.box((0,base/2,-46),(66,base,29),'stone')
    for side in (-1,1):
        hall(rear,side*26,base+.25,-44,12,20,4.5,3)
        rear.box((side*35,base+1.5,-54),(.8,3.,66),'red')
        rear.box((side*35,base+3.1,-54),(1.2,.26,67),'roof')
        rear.box((side*35,base+3.27,-54),(.3,.15,67),'ridge')
    upper=base+10.8
    rear.box((0,upper/2,-76),(64,upper,29),'stone')
    for i in range(54):
        h=base+(i+1)*.2;rear.box((0,(h+base)/2,-44-i*.32),(12,h-base+.02,.34),'stone')
    hall(rear,0,upper,-73,33,15,7.0,7,double=True)
    for side in (-1,1):
        rail(rear,side*7,-61.5,side*31,-61.5,upper)
        hall(rear,side*25,upper,-80,13,13,5.2,3)
    summit=upper+10.8
    rear.box((0,summit/2,-117),(53,summit,26),'stone')
    for i in range(54):
        h=upper+(i+1)*.2;rear.box((0,(h+upper)/2,-86.5-i*.32),(10,h-upper+.02,.34),'stone')
    hall(rear,0,summit,-117,28,15,7.2,5,double=True)
    for side in (-1,1):
        hall(rear,side*20,summit,-116,8,12,4.6,3)
        rail(rear,side*5.5,-104,side*25,-104,summit)
    # Two modest pools of warm light leave the temple mostly dark and empty.
    for x,z,y in ((-6.3,-20.7,base+3.6),(6.3,-20.7,base+3.6),(-14,-64.5,upper+4.8),(14,-64.5,upper+4.8)):
        front.beam((x,y+.6,z),(x,y+.25,z),.04,.04,'wood')
        lamps.box((x,y,z),(.35,.48,.35),'lamp')
        front.box((x,y+.27,z),(.44,.08,.44),'wood');front.box((x,y-.27,z),(.40,.09,.40),'wood')
        for sign in (-1,1):front.box((x+sign*.16,y,z+.19),(.035,.49,.04),'wood')
    for mesh in (front,rear,lamps):mesh.export()
    report=dict(temple_stairs=STAIR_COUNT,temple_rise=base,temple_width=72,temple_depth=139,
                temple_role='Terraced mountain complex above an arrival clearing; separate from playable water courtyard',
                temple_texture=[256,256],temple_halls=11,temple_reference='Fahai atmosphere; fictional terraced composition')
    return report


if __name__=='__main__':
    out=ROOT/'art'/'temple'/'intro';bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.context.preferences.filepaths.save_version=0
    document=json.loads((out/'manifest.json').read_text());document['landscape'].update(build(out,document['models']))
    (out/'manifest.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8',newline='\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'temple_approach.blend'))
    print(json.dumps(document['landscape']),flush=True)
