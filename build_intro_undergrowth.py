"""Compact curved foliage sprays, exported with per-vertex wind weights."""
import math
import random
import bpy
from mathutils import Vector


def build(out,models):
    mat=bpy.data.materials.new('Undergrowth / jade foliage');mat.use_nodes=True
    image=bpy.data.images.load(str(out/'undergrowth.png'));image.pack()
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Closest'
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    mat.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
    mat.surface_render_method='DITHERED';mat.alpha_threshold=.45;mat.use_backface_culling=False
    for variant,name in enumerate(('shrub','fern')):
        rng=random.Random(923+variant);verts=[];faces=[];uvs=[];weights=[]
        for i in range(16 if variant==0 else 10):
            a=i*2.39996;right=Vector((math.cos(a),0,math.sin(a)))
            outward=Vector((-math.sin(a),0,math.cos(a)))
            center=outward*rng.uniform(.12,.45)+Vector((0,rng.uniform(.3,.78) if variant==0 else .27,0))
            width=rng.uniform(.78,1.4) if variant==0 else rng.uniform(.45,.78)
            height=rng.uniform(.6,1.0) if variant==0 else rng.uniform(.5,.95)
            tile=i%2+variant*2;start=len(verts)
            for row in range(3):
                v=row/2
                for col in range(2):
                    u=col;point=center+right*(u-.5)*width+Vector((0,(v-.5)*height,0))+outward*(v*v*.42)
                    verts.append((point.x,-point.z,point.y));weights.append((v*.5+.06,rng.random()))
            for row in range(2):
                faces.append((start+row*2,start+row*2+1,start+row*2+3,start+row*2+2))
                x=tile%2*.5;y=(1-tile//2)*.5
                uvs.append(((x,y+row*.25),(x+.5,y+row*.25),(x+.5,y+(row+1)*.25),(x,y+(row+1)*.25)))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        uv=mesh.uv_layers.new(name='Painted foliage');wind=mesh.uv_layers.new(name='Wind')
        for poly,coords in zip(mesh.polygons,uvs):
            for index,coord in zip(poly.loop_indices,coords):
                uv.data[index].uv=coord;wind.data[index].uv=weights[mesh.loops[index].vertex_index]
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj);mesh.materials.append(mat)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.gltf(filepath=str(out/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[name]=dict(triangles=len(faces)*2,vertices=len(verts),wind_uv=True,atlas='undergrowth')
