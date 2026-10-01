"""Run INSIDE Blender: --background --factory-startup --python build_roof.py.

Creates a real curved hipped roof, packed .blend, three orthographic views and
four shadowed directional response renders. No live 3D is added to the game.
"""
from pathlib import Path
import json,math,sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'roof_settings.json').read_text())
OUT=ROOT/'renders';OUT.mkdir(exist_ok=True)
HALF=CFG['half_width'];DEPTH=CFG['half_depth'];RIDGE=CFG['ridge_half_width']
STEPS=[0.,.12,.25,.40,.55,.68,.79,.88,.95,1.]
MESHES=[];MATERIALS={};BINDINGS={}


def surface_material(name,file):
    material=bpy.data.materials.new(name);material.use_nodes=True
    nodes=material.node_tree.nodes;nodes.clear();links=material.node_tree.links
    out=nodes.new('ShaderNodeOutputMaterial');out.location=(500,0)
    shader=nodes.new('ShaderNodeEmission');shader.location=(280,0)
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'textures'/file));tex.image.pack()
    tex.interpolation='Linear';tex.extension='EXTEND';tex.location=(-480,20)
    # Mild geometry AO retains crease depth without baking a strong sun into RGB.
    ao=nodes.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=8.;ao.samples=16;ao.location=(-480,-200)
    remap=nodes.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.72;remap.inputs['To Max'].default_value=1.;remap.location=(-230,-150)
    links.new(ao.outputs['AO'],remap.inputs['Value'])
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1.;mix.location=(20,0)
    links.new(tex.outputs['Color'],mix.inputs[1]);links.new(remap.outputs['Result'],mix.inputs[2]);links.new(mix.outputs[0],shader.inputs['Color'])
    links.new(shader.outputs[0],out.inputs['Surface'])
    MATERIALS[name]=material;return material


def mesh(name,vertices,faces,uvs,material):
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.data.materials.append(material)
    layer=data.uv_layers.new(name='Photo UV')
    for polygon,coords in zip(data.polygons,uvs):
        for index,uv in zip(polygon.loop_indices,coords):layer.data[index].uv=uv
    MESHES.append(obj);return obj


def height(s,t):
    kick=CFG['eave_lift']*max(0.,(s-.72)/.28)**2
    return CFG['rise']*(1.-s)**1.65+kick+CFG['corner_lift']*abs(t)**8*s**3


def point(face,t,s):
    width=RIDGE+(HALF-RIDGE)*s
    if face in ('front','back'):return (t*width,(-1 if face=='front' else 1)*DEPTH*s,height(s,t))
    return ((-1 if face=='left' else 1)*width,t*DEPTH*s,height(s,t))


def roof_surface(face):
    ts=[-1.+i/16*2 for i in range(17)];verts=[point(face,t,s) for s in STEPS for t in ts];faces=[];uvs=[]
    for j in range(len(STEPS)-1):
        for i in range(len(ts)-1):
            indices=[j*len(ts)+i,j*len(ts)+i+1,(j+1)*len(ts)+i+1,(j+1)*len(ts)+i]
            # Planar course spacing: clip parallel rows at hips, rather than
            # stretching an entire photograph into every trapezoid/triangle.
            coordinates=[]
            for k,s in zip(indices,(STEPS[j],STEPS[j],STEPS[j+1],STEPS[j+1])):
                p=verts[k];u=(p[0]/HALF+1)/2 if face in ('front','back') else (p[1]/DEPTH+1)/2
                coordinates.append((u,1.-s))
            a,b,c=(Vector(verts[k]) for k in indices[:3])
            normal=(b-a).cross(c-a)
            if normal.length<1e-7:
                a,b,c=(Vector(verts[k]) for k in indices[1:]);normal=(b-a).cross(c-a)
            if normal.z<0:indices.reverse();coordinates.reverse()
            faces.append(indices);uvs.append(coordinates)
    mesh('Roof slope / '+face,verts,faces,uvs,MATERIALS['Photographed tiles'])


def ribbon(name,points,depth,material):
    verts=[];faces=[];uvs=[]
    for p in points:verts.extend([tuple(p),tuple(Vector(p)-Vector((0,0,depth)))])
    for i in range(len(points)-1):
        faces.append([2*i,2*i+2,2*i+3,2*i+1]);u=i/(len(points)-1);v=(i+1)/(len(points)-1)
        uvs.append([(u,1),(v,1),(v,0),(u,0)])
    return mesh(name,verts,faces,uvs,material)


def tube(name,points,radius,material,segments=6):
    verts=[];faces=[];uvs=[]
    for i,p in enumerate(points):
        p=Vector(p);a=Vector(points[max(0,i-1)]);b=Vector(points[min(len(points)-1,i+1)])
        tangent=(b-a).normalized();side=tangent.cross(Vector((0,0,1))).normalized();up=side.cross(tangent).normalized()
        for n in range(segments):
            angle=2*math.pi*n/segments;verts.append(tuple(p+radius*(side*math.cos(angle)+up*math.sin(angle))))
    for i in range(len(points)-1):
        for n in range(segments):
            faces.append([i*segments+n,i*segments+(n+1)%segments,(i+1)*segments+(n+1)%segments,(i+1)*segments+n])
            uvs.append([(i/(len(points)-1),n/segments),(i/(len(points)-1),(n+1)/segments),((i+1)/(len(points)-1),(n+1)/segments),((i+1)/(len(points)-1),n/segments)])
    # Close the trim's exposed ends.
    faces.extend([list(reversed(range(segments))),list(range((len(points)-1)*segments,len(points)*segments))])
    uvs.extend([[(.5+.48*math.cos(n*2*math.pi/segments),.5+.48*math.sin(n*2*math.pi/segments)) for n in range(segments)] for _ in range(2)])
    return mesh(name,verts,faces,uvs,material)


def geometry():
    for face in ('front','back','left','right'):
        roof_surface(face)
        edge=[point(face,-1.+2*i/24,1.) for i in range(25)]
        ribbon('Painted fascia / '+face,[Vector(p)-Vector((0,0,1.)) for p in edge],CFG['fascia_height'],MATERIALS['Painted fascia'])
        ribbon('Tile end course / '+face,[Vector(p)+Vector((0,0,.25)) for p in edge],2.6,MATERIALS['Tile ends'])
    # Four shaped hip ridges define geometry even when the photo details are small.
    for sign in (-1,1):
        for t in (-1,1):
            pts=[Vector(point('front' if sign<0 else 'back',t,s))+Vector((0,0,1.2)) for s in STEPS]
            tube('Glazed hip ridge '+str((sign,t)),pts,1.8,MATERIALS['Photographed tiles'])
    spine=[(x,0,CFG['rise']+1.9+7.*(abs(x)/(RIDGE+4))**12) for x in range(-int(RIDGE)-4,int(RIDGE)+5,4)]
    tube('Raised central ridge',spine,2.7,MATERIALS['Photographed tiles'],8)
    # Open-air timber underside, visible only where the higher camera permits it.
    mesh('Roof underside',[(-HALF,-DEPTH,-1),(HALF,-DEPTH,-1),(HALF,DEPTH,-1),(-HALF,DEPTH,-1)],
         [[3,2,1,0]],[[(0,0),(1,0),(1,1),(0,1)]],MATERIALS['Old timber'])
    for obj in MESHES:BINDINGS[obj.name]=obj.data.materials[0]


def camera_for(angle):
    scene=bpy.context.scene
    camera=bpy.data.objects.new('Orthographic '+str(angle)+' degrees',bpy.data.cameras.new('Camera '+str(angle)))
    scene.collection.objects.link(camera);camera.data.type='ORTHO';camera.data.lens=50
    theta=math.radians(angle);out=Vector((0,-math.cos(theta),math.sin(theta)))
    up=Vector((0,math.sin(theta),math.cos(theta)));right=Vector((1,0,0))
    points=[obj.matrix_world @ v.co for obj in MESHES for v in obj.data.vertices]
    us=[p.dot(right) for p in points];vs=[p.dot(up) for p in points]
    center=right*((max(us)+min(us))/2)+up*((max(vs)+min(vs))/2)
    camera.location=center+out*600;camera.rotation_euler=(-out).to_track_quat('-Z','Y').to_euler()
    aspect=CFG['runtime_size'][0]/CFG['runtime_size'][1]
    camera.data.ortho_scale=max(max(us)-min(us)+5,(max(vs)-min(vs)+5)*aspect)
    camera.data.clip_end=1200;scene.camera=camera;bpy.context.view_layer.update()
    eave=world_to_camera_view(scene,camera,Vector((0,-DEPTH,CFG['eave_lift']-1.-CFG['fascia_height'])))
    eave_pixel=(1.-eave.y)*CFG['runtime_size'][1]
    # Attach the bottom of the actual front fascia to the existing wall top.
    anchor=round(CFG['front_fascia_world_y']-CFG['scene_base_y']-eave_pixel)
    return camera,dict(elevation=angle,azimuth=0,projection='ORTHO',ortho_scale=camera.data.ortho_scale,
                       front_fascia_pixel=eave_pixel,anchor_y=anchor)


def render(name):
    scene=bpy.context.scene;scene.render.filepath=str(OUT/(name+'.png'))
    print('ROOF_RENDER '+name,flush=True);bpy.ops.render.render(write_still=True)


def override_material(material):
    for obj in MESHES:obj.data.materials[0]=material if material else BINDINGS[obj.name]


def data_material(name,mode):
    m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes;nodes.clear();links=m.node_tree.links
    out=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission')
    if mode=='normal':
        geo=nodes.new('ShaderNodeNewGeometry');scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=.5
        add=nodes.new('ShaderNodeVectorMath');add.operation='ADD';add.inputs[1].default_value=(.5,.5,.5)
        links.new(geo.outputs['Normal'],scale.inputs[0]);links.new(scale.outputs['Vector'],add.inputs[0]);links.new(add.outputs['Vector'],emission.inputs[0])
        links.new(emission.outputs[0],out.inputs['Surface'])
    else:
        emission.inputs[0].default_value=(.12,.12,.12,1.)
        diffuse=nodes.new('ShaderNodeBsdfDiffuse');diffuse.inputs['Color'].default_value=(.88,.88,.88,1.)
        add=nodes.new('ShaderNodeAddShader');links.new(emission.outputs[0],add.inputs[0]);links.new(diffuse.outputs[0],add.inputs[1]);links.new(add.outputs[0],out.inputs['Surface'])
    return m


def setup():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16
    bpy.context.preferences.filepaths.save_version=0
    preview=bpy.context.preferences.filepaths.bl_rna.properties.get('file_preview_type')
    if preview and 'NONE' in preview.enum_items.keys():bpy.context.preferences.filepaths.file_preview_type='NONE'
    scene.cycles.use_denoising=False;scene.cycles.max_bounces=1;scene.cycles.diffuse_bounces=0
    scene.render.resolution_x=CFG['runtime_size'][0]*CFG['supersample'];scene.render.resolution_y=CFG['runtime_size'][1]*CFG['supersample']
    scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.dither_intensity=0.
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0.;scene.view_settings.gamma=1.
    world=bpy.data.worlds.new('Transparent black world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[1].default_value=0.;scene.world=world
    for name,file in [('Photographed tiles','tiles.png'),('Tile ends','tile_ends.png'),('Painted fascia','fascia.png'),('Old timber','timber.png')]:surface_material(name,file)


def main():
    setup();geometry();metadata=dict(blender=bpy.app.version_string,settings=CFG,views={})
    scene=bpy.context.scene
    for angle in CFG['angles']:
        camera,record=camera_for(angle);metadata['views'][str(angle)]=record
        render('roof_'+str(angle))
    selected=bpy.data.objects['Orthographic '+str(CFG['selected_angle'])+' degrees'];scene.camera=selected
    metadata['mesh_objects']=len(MESHES);metadata['triangles']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in MESHES)
    scene['asset_description']='Photographic tiles and timber on a curved hipped roof. Orthographic sprite-baking study.'
    scene['runtime_size']=CFG['runtime_size'];scene['selected_angle']=CFG['selected_angle']
    # A packed scene opens with the selected camera and the colour materials.
    for area in bpy.context.screen.areas if bpy.context.screen else ():
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'water_temple_roof.blend'))
    if '--previews-only' not in sys.argv:
        scene.view_settings.view_transform='Raw'
        normal_material=data_material('World normal data','normal')
        response_material=data_material('White light response','response')
        light=bpy.data.lights.new('Response sun','SUN');light.energy=math.pi;light.angle=math.radians(3.)
        obj=bpy.data.objects.new('Response sun',light);scene.collection.objects.link(obj)
        elevation=math.radians(CFG['light_elevation']);z=math.sin(elevation);c=math.cos(elevation)
        for angle in CFG['angles']:
            scene.camera=bpy.data.objects['Orthographic '+str(angle)+' degrees']
            override_material(normal_material);render('normal_'+str(angle))
            override_material(response_material)
            for name,direction in [('down',(0,-c,z)),('up',(0,c,z)),('left',(-c,0,z)),('right',(c,0,z))]:
                obj.rotation_euler=(-Vector(direction)).to_track_quat('-Z','Y').to_euler();render('response_'+str(angle)+'_'+name)
        override_material(None);bpy.data.objects.remove(obj,do_unlink=True);scene.view_settings.view_transform='Standard'
    (ROOT/'render_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
    print('ROOF_COMPLETE '+str(metadata['triangles'])+' triangles',flush=True)


if __name__=='__main__':main()
