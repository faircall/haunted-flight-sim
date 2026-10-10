"""Painted pine boughs, layered ridges and an elevated fictional temple façade."""
import math
import random
import bpy
from mathutils import Vector
from g_intro_landscape import STAIR_COUNT,STAIR_RISE


def build(out,models,Mesh):
    from build_intro_undergrowth import build as build_undergrowth
    build_undergrowth(out,models)
    leaf=bpy.data.materials.new('Chinese pine / painted needle cutouts');leaf.use_nodes=True
    image=bpy.data.images.load(str(out/'pine_foliage.png'));image.pack()
    node=leaf.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;node.interpolation='Closest'
    bsdf=leaf.node_tree.nodes.get('Principled BSDF')
    leaf.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
    leaf.node_tree.links.new(node.outputs['Alpha'],bsdf.inputs['Alpha'])
    leaf.surface_render_method='DITHERED';leaf.alpha_threshold=.45;leaf.use_backface_culling=False
    bsdf.inputs['Roughness'].default_value=.95
    bark=bpy.data.materials.new('Chinese pine / fissured painted bark');bark.use_nodes=True
    image=bpy.data.images.new('pine_bark',width=32,height=64);pixels=[];rng=random.Random(72)
    for y in range(64):
        for x in range(32):
            crack=math.sin(x*1.1+math.sin(y*.32)*.9)
            shade=(.055 if crack>.5 else -.045 if crack<-.6 else 0)+rng.uniform(-.016,.016)
            pixels.extend((.25+shade,.205+shade,.145+shade,1.))
    image.pixels=pixels;image.filepath_raw=str(out/'pine_bark.png');image.file_format='PNG';image.save();image.pack()
    node=bark.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;node.interpolation='Closest'
    bark.node_tree.links.new(node.outputs['Color'],bark.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    bark.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.95

    def export_tree(name,seed):
        rng=random.Random(seed);parts=[];counts=[]
        def object_(label,verts,faces,uv,wind,material):
            mesh=bpy.data.meshes.new(label)
            mesh.from_pydata([(x,-z,y) for x,y,z in verts],[],faces);mesh.update()
            obj=bpy.data.objects.new(label,mesh);bpy.context.scene.collection.objects.link(obj);mesh.materials.append(material)
            colour=mesh.uv_layers.new(name='Painted bough atlas');motion=mesh.uv_layers.new(name='Wind weight and phase')
            for poly,coords in zip(mesh.polygons,uv):
                for i,coord in zip(poly.loop_indices,coords):
                    colour.data[i].uv=coord;motion.data[i].uv=wind[mesh.loops[i].vertex_index]
            parts.append(obj);counts.append((len(verts),sum(len(f)-2 for f in faces)))
        wood=[];wf=[];wu=[];ww=[];foliage=[];ff=[];fu=[];fw=[]
        def branch(points,radii,sides=6):
            start=len(wood)
            for row,(p,r) in enumerate(zip(points,radii)):
                tangent=Vector(points[min(row+1,len(points)-1)])-Vector(points[max(row-1,0)])
                tangent.normalize();right=tangent.cross(Vector((0,0,1)))
                if right.length<.01:right=tangent.cross(Vector((1,0,0)))
                right.normalize();across=tangent.cross(right)
                for i in range(sides):
                    a=math.tau*i/sides;v=Vector(p)+r*(right*math.cos(a)+across*math.sin(a))
                    wood.append(tuple(v));ww.append((-.008*(v.y/6)**2,.13))
            for j in range(len(points)-1):
                for i in range(sides):
                    wf.append([start+j*sides+i,start+j*sides+(i+1)%sides,start+(j+1)*sides+(i+1)%sides,start+(j+1)*sides+i])
                    wu.append([(i/sides,j*.4),((i+1)/sides,j*.4),((i+1)/sides,(j+1)*.4),(i/sides,(j+1)*.4)])
        lean=rng.uniform(-.35,.35)
        branch([(0,0,0),(.12,1.5,0),(-.12,3.1,.12),(lean,4.7,.25),(lean+.36,6.1,.18)],(.24,.19,.15,.095,.023),8)
        for i in range(5):
            a=math.tau*i/5
            branch([(math.cos(a)*.8,.02,math.sin(a)*.7),(math.cos(a)*.25,.26,math.sin(a)*.23),(0,.8,0)],(.035,.15,.15),5)
        for i in range(12):
            angle=i*2.39996+rng.uniform(-.25,.25);height=2.5+i*.285
            radius=(2.7-.07*i)*rng.uniform(.78,1.2)
            outward=Vector((math.cos(angle),0,math.sin(angle)));root=Vector((lean*.5,height,.12))
            tip=root+outward*radius+Vector((0,.40,0))
            elbow=root.lerp(tip,.55)+Vector((0,-.19,0))
            branch([root,elbow,tip],(.105-.004*i,.055,.018),6)
            for j in range(5):
                a=angle+rng.uniform(-.95,.95);v=Vector((math.cos(a),0,math.sin(a)))
                center=root.lerp(tip,.62+.12*j)+v*rng.uniform(.05,.55)+Vector((0,rng.uniform(.02,.42),0))
                branch([elbow,center],(.025,.007),4)
                for tilt in (rng.uniform(.25,.55),rng.uniform(.90,1.25)):
                    right=Vector((-math.sin(a),0,math.cos(a)))
                    up=Vector((0,math.sin(tilt),0))+v*math.cos(tilt)
                    width=rng.uniform(1.3,2.05);height_=rng.uniform(.85,1.35);tile=(i+j)%4
                    first=len(foliage);phase=rng.random()
                    for row in range(3):
                        y=-.5+row*.5
                        for col in range(3):
                            x=-.5+col*.5;p=center+right*x*width+up*y*height_+v*(.10*(1-4*x*x)*(1-4*y*y))
                            foliage.append(tuple(p));fw.append((.35+.5*(y+.5),phase))
                    for row in range(2):
                        for col in range(2):
                            ids=[first+row*3+col,first+row*3+col+1,first+(row+1)*3+col+1,first+(row+1)*3+col]
                            ff.append(ids);u=tile%2*.5;vv=(1-tile//2)*.5
                            fu.append([(u+col*.25,vv+row*.25),(u+(col+1)*.25,vv+row*.25),
                                       (u+(col+1)*.25,vv+(row+1)*.25),(u+col*.25,vv+(row+1)*.25)])
        object_(name+' / crooked wood',wood,wf,wu,ww,bark)
        object_(name+' / painted boughs',foliage,ff,fu,fw,leaf)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:obj.select_set(True)
        bpy.context.view_layer.objects.active=parts[0]
        bpy.ops.export_scene.gltf(filepath=str(out/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[name]=dict(vertices=sum(v for v,t in counts),triangles=sum(t for v,t in counts),
                          species='Pinus tabuliformis / Chinese pine / 油松',foliage_cards=120,wind_uv=True)
    for i,name in enumerate(('chinese_pine_a','chinese_pine_b','chinese_pine_c')):export_tree(name,719+i*41)

    for seed,name in enumerate(('ridge_a','ridge_b','ridge_c')):
        mesh=Mesh(name);mesh.smooth=True;rows=[];rng=random.Random(91+seed)
        peaks=[(rng.uniform(-.8,.8),rng.uniform(.2,.45),rng.uniform(.35,.65)) for _ in range(5)]
        for j in range(31):
            z=-1+2*j/30;crest=sum(h*math.exp(-((z-c)/w)**2) for c,w,h in peaks)*(.48+.09*seed)
            end=min(1.,(1-abs(z))/.30);end=end*end*(3-2*end)
            row=[]
            for i in range(23):
                x=-1+2*i/22;shift=.18*math.sin(z*5+seed)
                # Every rim reaches the submerged base, including the shifted
                # cross-section. Otherwise the open side reads as a huge arch.
                fraction=abs(x-shift)/(1-shift if x>=shift else 1+shift)
                profile=max(0.,math.cos(min(1.,fraction)*math.pi/2))**(1.25+.4*math.sin(z*3+seed))
                y=(crest*profile+.037*math.sin(x*16+z*12+seed)*profile)*end
                row.append((x,y,z))
            rows.append(row)
        for a,b in zip(rows,rows[1:]):
            for i in range(22):mesh.face([a[i],b[i],b[i+1],a[i+1]],'stone')
        mesh.export()
    bank=Mesh('lakeside_bank')
    cross=((-78,23),(-40,15),(-22,8),(-12,3.7),(-7,1.1),(-4,.04),(-2,-.02),(2,-.02),(2.6,-.10),(3.4,-.48),(4.6,-1.6),(8,-2.3))
    rows=[[(x,y+(math.sin(math.pi*j/4)*.2 if x<-7 else 0),-3.4+6.8*j/4) for x,y in cross] for j in range(5)]
    for a,b in zip(rows,rows[1:]):
        for i in range(len(cross)-1):bank.face([a[i],b[i],b[i+1],a[i+1]],'stone' if i<4 or i>8 else 'olive')
    bank.export()

    from build_intro_temple import build as build_temple
    temple_report=build_temple(out,models)
    return dict(trees=['chinese_pine_a','chinese_pine_b','chinese_pine_c'],tree_species='Pinus tabuliformis',
                foliage_texture=[256,256],bark_texture=[32,64],lake_height=-1.35,
                **temple_report,
                reference='Fahai Temple atmosphere/entrance; Santana video lakeside drive',volumetric_fog=True)
