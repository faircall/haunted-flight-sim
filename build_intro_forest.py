"""Blender-authored mature Chinese arborvitae and Fahai-inspired lacebark pines."""
from pathlib import Path
import json
import math
import random
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent

def build(out,models):
    def material(name,image,alpha=False):
        m=bpy.data.materials.new(name);m.use_nodes=True
        n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=image;n.interpolation='Closest'
        b=m.node_tree.nodes.get('Principled BSDF');m.node_tree.links.new(n.outputs['Color'],b.inputs['Base Color'])
        b.inputs['Roughness'].default_value=.98
        if alpha:
            m.node_tree.links.new(n.outputs['Alpha'],b.inputs['Alpha']);m.surface_render_method='DITHERED'
            m.alpha_threshold=.42;m.use_backface_culling=False
        return m
    image=bpy.data.images.load(str(out/'mountain_foliage.png'));image.pack()
    leaf=material('Mountain forest / cypress fans and lacebark needles',image,True)
    image=bpy.data.images.new('Mountain forest bark',width=64,height=64);pixels=[];rng=random.Random(144)
    spots=[(rng.random()*32,rng.random()*64,rng.uniform(2,6),rng.choice((-.16,-.08,.045))) for _ in range(65)]
    for y in range(64):
        for x in range(64):
            if x<32:
                shade=.035*math.sin(x*1.3+math.sin(y*.22))-.07*max(0,math.sin(x*.7+y*.04))
                c=(.28+shade,.25+shade,.19+shade)
            else:
                shade=0
                for xx,yy,r,v in spots:
                    if ((x-32-xx)/r)**2+((y-yy)/(r*1.6))**2<1:shade=v
                c=(.66+shade,.68+shade,.58+shade)
            pixels.extend((*[v+rng.uniform(-.015,.015) for v in c],1))
    image.pixels=pixels;image.filepath_raw=str(out/'mountain_bark.png');image.file_format='PNG';image.save();image.pack()
    bark=material('Mountain forest / flaking cypress and mottled white pine bark',image)

    def tree(name,seed,pine=False):
        rng=random.Random(seed);wood=[];wf=[];wu=[];ww=[];leaves=[];lf=[];lu=[];lw=[]
        height=27 if pine else 21;phase=rng.random()
        def branch(points,radii,sides=6):
            start=len(wood)
            for row,(point,radius) in enumerate(zip(points,radii)):
                axis=(Vector(points[min(row+1,len(points)-1)])-Vector(points[max(row-1,0)])).normalized()
                right=axis.cross(Vector((0,0,1))).normalized();across=axis.cross(right)
                for i in range(sides):
                    a=i*math.tau/sides;v=Vector(point)+radius*(right*math.cos(a)+across*math.sin(a))
                    wood.append(v);ww.append((-.002*(v.y/height)**2,phase))
            for row in range(len(points)-1):
                for i in range(sides):
                    wf.append([start+row*sides+i,start+row*sides+(i+1)%sides,start+(row+1)*sides+(i+1)%sides,start+(row+1)*sides+i])
                    u=.5 if pine else 0;a=u+.012+i/sides*.475;b=u+.012+(i+1)/sides*.475
                    wu.append([(a,row*.29),(b,row*.29),(b,(row+1)*.29),(a,(row+1)*.29)])
        lean=rng.uniform(-1.1,1.1)
        branch([(0,-.28,0),(.22,3.6,.1),(-.14,8,.35),(lean,13,.1),(lean+.55,18,.45),(lean+.6,height,.2)],(.65,.48,.35,.25,.16,.025),9)
        for i in range(7):
            a=i*math.tau/7;branch([(math.cos(a)*1.9,-.08,math.sin(a)*1.9),(math.cos(a)*.7,.22,math.sin(a)*.7),(0,1.8,0)],(.04,.31,.38),5)
        for i in range(20):
            angle=i*2.39996+rng.uniform(-.35,.35)
            h=(12+i*.61 if pine else 5+i*.72);h=min(height-1,h)
            radius=(6.2 if pine else 3.9)*rng.uniform(.70,1.18)*(1-.40*max(0,(h/height-.7)/.3))
            direction=Vector((math.cos(angle),0,math.sin(angle)));root=Vector((lean*h/height,h,.2))
            elbow=root+direction*radius*.52+Vector((0,-.5 if pine else .4,0))
            tip=root+direction*radius+Vector((0,.8 if pine else 2.3,0))
            branch([root,elbow,tip],(.17*(1-i/28),.09,.014),6)
            for j in range(5):
                a=angle+rng.uniform(-1.0,1.0);outward=Vector((math.cos(a),0,math.sin(a)))
                center=root.lerp(tip,.55+j*.12)+outward*rng.uniform(.05,1.25)+Vector((0,rng.uniform(-.3,1.1),0))
                branch([elbow,center],(.043,.008),4)
                for k in range(2):
                    right=Vector((-math.sin(a),0,math.cos(a)));tilt=rng.uniform(.15,1.25) if pine else rng.uniform(.65,1.55)
                    up=Vector((0,math.sin(tilt),0))+outward*math.cos(tilt)
                    width=rng.uniform(2.5,3.7) if pine else rng.uniform(2.0,3.2);length=rng.uniform(1.5,2.4) if pine else rng.uniform(2.2,3.4)
                    tile=2+rng.randrange(2) if pine else rng.randrange(2);u=tile%2*.5;v=(1-tile//2)*.5
                    start=len(leaves)
                    for xx,yy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)):
                        leaves.append(center+right*xx*width+up*yy*length);lw.append((.22+.48*(yy+.5),phase+j*.12))
                    lf.append([start,start+1,start+2,start+3]);lu.append([(u+.005,v+.005),(u+.495,v+.005),(u+.495,v+.495),(u+.005,v+.495)])
        objects=[]
        for label,verts,faces,uv,wind,mat in (('wood',wood,wf,wu,ww,bark),('foliage',leaves,lf,lu,lw,leaf)):
            mesh=bpy.data.meshes.new(name+' '+label);mesh.from_pydata([(x,-z,y) for x,y,z in verts],[],faces);mesh.update()
            obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(mat)
            atlas=mesh.uv_layers.new(name='Painted atlas');motion=mesh.uv_layers.new(name='Wind')
            for poly,coords in zip(mesh.polygons,uv):
                poly.use_smooth=label=='wood'
                for i,coord in zip(poly.loop_indices,coords):atlas.data[i].uv=coord;motion.data[i].uv=wind[mesh.loops[i].vertex_index]
            objects.append(obj)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.export_scene.gltf(filepath=str(out/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[name]=dict(vertices=len(wood)+len(leaves),triangles=sum(len(f)-2 for f in wf+lf),height=height,
                          species='Pinus bungeana' if pine else 'Platycladus orientalis',texture=[256,256],wind_uv=True)
    tree('temple_cypress_a',972);tree('temple_cypress_b',617);tree('lacebark_pine',162,True)

if __name__=='__main__':
    out=ROOT/'art'/'temple'/'intro';bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    document=json.loads((out/'manifest.json').read_text());build(out,document['models'])
    (out/'manifest.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(out/'mountain_forest.blend'))
