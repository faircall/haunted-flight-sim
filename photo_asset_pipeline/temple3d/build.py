"""Blender-only temple kit: photo textures, real geometry, colour/data bakes."""
from pathlib import Path
import sys,json,math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'renders';OUT.mkdir(exist_ok=True)
MODELS=ROOT/'models';MODELS.mkdir(exist_ok=True)
MATERIALS={};SETS={};CURRENT=[]
ANGLE=math.radians(30)


def texture_node(nodes,name):
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.get(name)
    if tex.image is None:tex.image=bpy.data.images.load(str(ROOT/'textures'/(name+'.png')));tex.image.name=name;tex.image.pack()
    tex.interpolation='Linear';tex.extension='REPEAT'
    return tex


def material(name,alpha=False):
    if name in MATERIALS:return MATERIALS[name]
    mat=bpy.data.materials.new(name);mat.use_nodes=True;mat['photo']=name;mat['alpha_cutout']=alpha
    nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    out=nodes.new('ShaderNodeOutputMaterial');emit=nodes.new('ShaderNodeEmission');tex=texture_node(nodes,name)
    ao=nodes.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=5.;ao.samples=8
    remap=nodes.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.74
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1.
    links.new(ao.outputs['AO'],remap.inputs[0]);links.new(tex.outputs['Color'],mix.inputs[1]);links.new(remap.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],emit.inputs[0])
    output=emit.outputs[0]
    if alpha:
        transparent=nodes.new('ShaderNodeBsdfTransparent');blend=nodes.new('ShaderNodeMixShader')
        links.new(tex.outputs['Alpha'],blend.inputs[0]);links.new(transparent.outputs[0],blend.inputs[1]);links.new(output,blend.inputs[2]);output=blend.outputs[0]
    links.new(output,out.inputs[0]);MATERIALS[name]=mat;return mat


def mesh(name,verts,faces,mat,uvs=None,smooth=False):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    layer=data.uv_layers.new(name='Photo UV')
    for i,p in enumerate(data.polygons):
        p.use_smooth=smooth
        coords=uvs[i] if uvs else [(0,0),(1,0),(1,1),(0,1)]
        for index,uv in zip(p.loop_indices,coords):layer.data[index].uv=uv
    CURRENT.append(obj);return obj


def box(name,center,size,mat,bevel=.18,uv_offset=0.):
    x,y,z=center;a,b,c=[v/2 for v in size]
    verts=[(x+dx*a,y+dy*b,z+dz*c) for dx,dy,dz in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    faces=[[0,3,2,1],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]]
    coords=[[(uv_offset,0),(uv_offset+1,0),(uv_offset+1,1),(uv_offset,1)] for _ in faces]
    obj=mesh(name,verts,faces,mat,coords)
    if bevel:
        mod=obj.modifiers.new('Worn edge','BEVEL');mod.width=min(bevel,min(size)*.2);mod.segments=1
        bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);obj.select_set(False)
    return obj


def lathe(name,profile,mat,segments=20,center=(0,0,0),smooth=True,front_uv=False):
    verts=[];faces=[];uvs=[];cx,cy,cz=center;low=min(p[1] for p in profile);high=max(p[1] for p in profile);radius=max(p[0] for p in profile)
    for r,z in profile:
        for i in range(segments):
            a=2*math.pi*i/segments;verts.append((cx+r*math.sin(a),cy-r*math.cos(a),cz+z))
    for j in range(len(profile)-1):
        for i in range(segments):
            f=[j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i];faces.append(f)
            if front_uv:uvs.append([((verts[k][0]-cx)/(radius*2)+.5,(verts[k][2]-cz-low)/max(.01,high-low)) for k in f])
            else:uvs.append([(i/segments,j/(len(profile)-1)),((i+1)/segments,j/(len(profile)-1)),((i+1)/segments,(j+1)/(len(profile)-1)),(i/segments,(j+1)/(len(profile)-1))])
    return mesh(name,verts,faces,mat,uvs,smooth)


def card(name,w,h,z,mat,y=0,relief=0.):
    # Camera-facing UV projection on a shallow relief. Used only where a single
    # photograph cannot justify a recovered statue or individual flower petals.
    verts=[];faces=[];uvs=[];n=16
    for j in range(n+1):
        for i in range(n+1):
            u=i/n;v=j/n;depth=relief*math.sin(u*math.pi)*math.sin(v*math.pi)
            verts.append(((u-.5)*w,y-depth,v*h+z))
    for j in range(n):
        for i in range(n):
            f=[j*(n+1)+i,j*(n+1)+i+1,(j+1)*(n+1)+i+1,(j+1)*(n+1)+i];faces.append(f)
            uvs.append([((k%(n+1))/n,(k//(n+1))/n) for k in f])
    return mesh(name,verts,faces,mat,uvs,True)


def foliage(flower):
    for index,(cx,cy,r) in enumerate(((-5,-2,6.7),(4,2,7.6))):
        verts=[(cx,cy,.6)];uv=[(.5,.5)]
        for j in range(1,7):
            for i in range(48):
                a=2*math.pi*i/48;rr=r*j/6;z=.55+1.1*(j/6)**3+.16*math.sin(a*5)*j/6
                verts.append((cx+rr*math.cos(a),cy+rr*math.sin(a),z));uv.append((.5+.5*j/6*math.cos(a),.5+.5*j/6*math.sin(a)))
        faces=[[0,1+i,1+(i+1)%48] for i in range(48)]
        for j in range(5):
            for i in range(48):faces.append([1+j*48+i,1+j*48+(i+1)%48,1+(j+1)*48+(i+1)%48,1+(j+1)*48+i])
        mesh('Photo pad '+str(index),verts,faces,material('pad' if index else 'pad_small',True),[[uv[k] for k in f] for f in faces],True)
    if flower:
        # A cupped low relief with the intact flower photograph projected above.
        verts=[];uv=[];faces=[];n=20
        for j in range(n+1):
            for i in range(n+1):
                u=i/n;v=j/n;dx=(u-.5)*7;dy=(v-.5)*7;r=math.hypot(dx,dy)
                z=2.+2.8*max(0.,1-r/5.)+.4*math.sin(math.atan2(dy,dx)*9)*min(1,r/2.)
                verts.append((dx+2,dy,z));uv.append((u,v))
        for j in range(n):
            for i in range(n):faces.append([j*(n+1)+i,j*(n+1)+i+1,(j+1)*(n+1)+i+1,(j+1)*(n+1)+i])
        mesh('Flower photo relief',verts,faces,material('flower',True),[[uv[k] for k in f] for f in faces],True)


def facade(kind,w,h):
    # Front face coordinates retain the game's exact opening rectangle. Extra
    # depth projects behind that face and is clipped to the same aperture mask.
    # Blender ships no Pillow: preparation also supplies aperture rows in JSON.
    holes=json.loads((ROOT/'aperture_pixels.json').read_text())[kind]
    active={}
    for row in range(h+1):
        spans=[];start=None
        for x in range(w+1):
            solid=row<h and x<w and not holes[row][x]
            if solid and start is None:start=x
            if not solid and start is not None:spans.append((start,x));start=None
        for span,first in list(active.items()):
            if span not in spans:
                a,b=span;top=first;bottom=row
                # Actual boards and edges, instead of a single flat wood slab.
                cuts=[a]+[x for x in range(6,w,6) if a<x<b]+[b]
                for left,right in zip(cuts,cuts[1:]):
                    obj=box('Facade joinery',((left+right)/2-w/2,2.,(h-(top+bottom)/2)/math.cos(ANGLE)),
                        (right-left,4.,(bottom-top)/math.cos(ANGLE)),material('column' if b-a<=4 else 'wood'),.14)
                    if b-a>4:
                        uv=obj.data.uv_layers.active.data
                        for polygon in obj.data.polygons:
                            for k in polygon.loop_indices:
                                p=obj.data.vertices[obj.data.loops[k].vertex_index].co
                                uv[k].uv=((p.x+w/2)/48.,p.z/70.)
                del active[span]
        for span in spans:active.setdefault(span,row)
    # Apply decorative photo frieze to the lintel, visible on its actual face.
    box('Painted lintel',(0,-.3,(h-3)/math.cos(ANGLE)),(w,1.,5./math.cos(ANGLE)),material('painted'),.12)


def geometry(kind,w,h):
    if kind.startswith('rail'):
        for x in (-w/2+1.7,w/2-1.7):
            box('Rail post',(x,0,7.),(3.,3.,14.),material('column'),.25)
            box('Post cap',(x,0,14.4),(3.8,3.8,1.4),material('timber'),.25)
        for z in (5.,10.5):box('Rail crossbeam',(0,0,z),(w,2.6,2.),material('timber'),.25)
        for x in (-w*.22,w*.22):box('Rail spindle',(x,0,7.8),(1.2,1.7,4.),material('column'),.1)
    elif kind.startswith('pile'):
        box('Foundation pile',(0,0,h*.52),(w*.78,w*.78,h),material('wood'),.3)
        box('Pile cap',(0,0,h),(w,w,1.),material('timber'),.15)
    elif kind=='column':
        lathe('Red timber column',[(2.4,3),(2.65,7),(2.25,57)],material('column'),16)
        for z in (1.5,58):box('Stone collar',(0,0,z),(7.,7.,3.),material('stone'),.45)
        box('Carved capital',(0,0,61),(9.,7.,3.),material('painted'),.2)
    elif kind=='brazier':
        lathe('Stone lamp plinth',[(0,0),(4,0),(4,1.5),(2.2,3),(1.5,11)],material('stone'),16)
        lathe('Open fire bowl',[(1.5,10),(4.4,11),(6.8,15),(6.8,16),(5.6,16),(3.4,12),(0,12)],material('stone'),24)
    elif kind in ('lantern_paper','lantern_porcelain'):
        porcelain=kind.endswith('porcelain');hh=26 if porcelain else 25;r=7 if porcelain else 7.5
        lathe('Lantern body',[(r*.72,5),(r,8),(r,hh-5),(r*.73,hh)],material('ceramic' if porcelain else 'paper'),24,front_uv=True)
        for z in (4.,hh):lathe('Lantern cap',[(0,z-.7),(r*.8,z-.7),(r*.92,z),(r*.8,z+1),(0,z+1)],material('ceramic' if porcelain else 'painted'),24)
        if porcelain:lathe('Porcelain foot',[(0,0),(r*.8,0),(r*.85,1),(r*.42,3),(r*.55,5)],material('ceramic'),12)
        else:
            box('Suspension',(0,0,hh+3),(.5,.5,5.),material('timber'),0)
            lathe('Tassel',[(1.,0),(1.3,1),(1.,4)],material('column'),8)
    elif kind=='altar':
        box('Altar apron',(0,0,7),(34,11,8),material('column'),.4)
        box('Altar top',(0,0,12),(40,15,2.4),material('painted'),.4)
        for x in (-14,14):
            for y in (-4,4):box('Altar leg',(x,y,3),(3,3,6),material('column'),.25)
        box('Statue plinth',(0,2,14),(26,10,2),material('stone'),.3)
        card('Photographic Buddha',26,32,15,material('buddha',True),y=1.5,relief=0.)
    elif kind=='banner':
        obj=card('Hanging decorative panel',8,28,0,material('banner'),relief=.7)
        box('Hanging crossbar',(0,0,28.5),(10,1.2,1),material('timber'),.1)
    elif kind in ('lily_cluster','lily_leaves'):foliage(kind=='lily_cluster')
    elif kind in ('window','wall','door_open','door_closed'):facade(kind,w,h)
    elif kind=='planks_x':
        box('Dark timber substrate',(0,0,-1.5),(128,32,1),material('timber'),0)
        for row in range(8):
            joint=(-48+row*19)%120-60
            for a,b in ((-64,joint),(joint,64)):
                obj=box('Deck board',((a+b)/2,-14+row*4,-.55),(b-a-.45,3.6,1.5),material('wood'),.2)
                # Wood058's fibres run vertically in the photograph; rotate UVs
                # so they run along the length of each modelled horizontal board.
                uv=obj.data.uv_layers.active.data
                for polygon in obj.data.polygons:
                    for k in polygon.loop_indices:
                        p=obj.data.vertices[obj.data.loops[k].vertex_index].co
                        uv[k].uv=((p.y+16)/32.,(p.x+64)/128.)
    elif kind=='wall_ground':
        box('Mortar',(0,0,-1),(48,32,1),material('stone'),0)
        for row in range(4):
            for x in range(-36+(row%2)*8,32,16):box('Stone foundation',(x, -12+row*8,0),(15.2,7.2,2),material('brick'),.3,(row%3)*.2)


def configure_camera(size,ground=False,facade=False):
    scene=bpy.context.scene;w,h=size;angle=math.pi/2 if ground else ANGLE
    out=Vector((0,-math.cos(angle),math.sin(angle)));up=Vector((0,math.sin(angle),math.cos(angle)))
    points=[o.matrix_world@v.co for o in CURRENT for v in o.data.vertices]
    us=[p.x for p in points];vs=[p.dot(up) for p in points]
    if ground or facade:
        scale=w;center=Vector((0,0,0)) if ground else up*(h/2)
    else:
        scale=max(max(us)-min(us)+1.5,(max(vs)-min(vs)+1.5)*w/h)
        center=Vector(((max(us)+min(us))/2,0,0))+up*((max(vs)+min(vs))/2)
    camera=scene.camera;camera.location=center+out*600;camera.rotation_euler=(-out).to_track_quat('-Z','Y').to_euler()
    if ground:camera.rotation_euler=(0.,0.,0.) # explicit roll at the zenith
    # Blender's AUTO sensor fit uses the longer image axis, including portrait
    # props. Metadata scale remains pixels per unit in either orientation.
    camera.data.ortho_scale=scale*max(1.,h/w)
    scene.render.resolution_x=w*4;scene.render.resolution_y=h*4;bpy.context.view_layer.update()
    origin=world_to_camera_view(scene,camera,Vector((0,0,0)))
    s=w/scale
    minimum=[min(p.x for p in points),min(-p.y for p in points),min(p.z for p in points)]
    maximum=[max(p.x for p in points),max(-p.y for p in points),max(p.z for p in points)]
    for i in range(3):
        if maximum[i]-minimum[i]<.01:maximum[i]=minimum[i]+.01
    return dict(size=size,scale=s,elevation=math.degrees(angle),pivot=[origin.x*w,(1-origin.y)*h],
                position_min=[v*s for v in minimum],position_max=[v*s for v in maximum],
                raw_min=minimum,raw_max=maximum,depth_direction=list(out))


def data_material(original,mode,record):
    mat=bpy.data.materials.new(mode);mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    out=nodes.new('ShaderNodeOutputMaterial');emit=nodes.new('ShaderNodeEmission');geo=nodes.new('ShaderNodeNewGeometry')
    if mode=='ao':
        ao=nodes.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=5.;ao.samples=8;links.new(ao.outputs['AO'],emit.inputs[0])
    else:
        flip=nodes.new('ShaderNodeVectorMath');flip.operation='MULTIPLY';flip.inputs[1].default_value=(1,-1,1)
        links.new(geo.outputs['Normal' if mode=='normal' else 'Position'],flip.inputs[0])
        sub=nodes.new('ShaderNodeVectorMath');sub.operation='SUBTRACT'
        sub.inputs[1].default_value=(-1,-1,-1) if mode=='normal' else record['raw_min'];links.new(flip.outputs[0],sub.inputs[0])
        divide=nodes.new('ShaderNodeVectorMath');divide.operation='DIVIDE';divide.inputs[1].default_value=(2,2,2) if mode=='normal' else tuple(b-a for a,b in zip(record['raw_min'],record['raw_max']))
        links.new(sub.outputs[0],divide.inputs[0]);links.new(divide.outputs[0],emit.inputs[0])
    result=emit.outputs[0]
    if original.get('alpha_cutout'):
        tex=texture_node(nodes,original['photo']);transparent=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader')
        links.new(tex.outputs['Alpha'],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1]);links.new(result,mix.inputs[2]);result=mix.outputs[0]
    links.new(result,out.inputs[0]);return mat


def export_obj(name,record):
    # A simple interoperable mesh export also feeds the independent live viewer.
    # Coordinates become game X, height, ground Y; keep model units in pixels.
    lines=['mtllib materials.mtl'];offset=0;scale=record['scale']
    for obj in CURRENT:
        data=obj.data;data.calc_loop_triangles();uv=data.uv_layers.active.data
        lines.extend(['o '+obj.name.replace(' ','_'),'usemtl '+obj.data.materials[0].name])
        for tri in data.loop_triangles:
            for k in tri.loops:
                loop=data.loops[k];p=obj.matrix_world@data.vertices[loop.vertex_index].co;n=loop.normal
                lines.append('v %.6f %.6f %.6f'%(p.x*scale,p.z*scale,-p.y*scale));lines.append('vt %.6f %.6f'%tuple(uv[k].uv));lines.append('vn %.6f %.6f %.6f'%(n.x,n.z,-n.y))
            lines.append('f '+' '.join(f'{j}/{j}/{j}' for j in range(offset+1,offset+4)));offset+=3
    (MODELS/(name+'.obj')).write_text('\n'.join(lines))


def render(name):
    bpy.context.scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)


def setup():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.max_bounces=2;scene.cycles.transparent_max_bounces=8;scene.cycles.use_denoising=False
    scene.render.film_transparent=True;scene.render.dither_intensity=0.;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
    world=bpy.data.worlds.new('Black background');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[1].default_value=0.;scene.world=world
    camera=bpy.data.objects.new('Orthographic sprite camera',bpy.data.cameras.new('Bake camera'));scene.collection.objects.link(camera);camera.data.type='ORTHO';camera.data.clip_end=1200;scene.camera=camera
    bpy.context.preferences.filepaths.save_version=0
    preview=bpy.context.preferences.filepaths.bl_rna.properties.get('file_preview_type')
    if preview and 'NONE' in preview.enum_items.keys():bpy.context.preferences.filepaths.file_preview_type='NONE'


def main():
    setup();scene=bpy.context.scene;records={}
    specs=[('column',10,58),('rail32',32,17),('rail24',24,17),('pile28',5,28),('pile29',5,29),('pile54',4,54),
           ('brazier',14,18),('lantern_paper',20,30),('lantern_porcelain',18,32),('altar',40,46),('banner',10,30),
           ('lily_cluster',26,20),('lily_leaves',26,20),('window',48,56),('wall',16,56),('door_open',32,56),('door_closed',32,56),
           ('planks_x',128,32),('wall_ground',48,32)]
    for name,w,h in specs:
        CURRENT.clear();geometry(name,w,h);bpy.context.view_layer.update()
        record=configure_camera((w,h),name in ('planks_x','wall_ground'),name in ('window','wall','door_open','door_closed'));records[name]=record
        record['triangles']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in CURRENT)
        bindings={o.name:o.data.materials[0] for o in CURRENT};export_obj(name,record)
        scene.view_settings.view_transform='Standard';scene.render.image_settings.color_depth='8';render(name+'_color')
        scene.view_settings.view_transform='Raw';scene.render.image_settings.color_depth='16'
        for mode in ('normal','position','ao'):
            cached={}
            for obj in CURRENT:
                original=bindings[obj.name]
                if original.name not in cached:cached[original.name]=data_material(original,mode,record)
                obj.data.materials[0]=cached[original.name]
            render(name+'_'+mode)
        for obj in CURRENT:obj.data.materials[0]=bindings[obj.name];obj.hide_render=True
        SETS[name]=list(CURRENT)
        print('KIT_BAKED '+name,flush=True)
    # Include the approved roof geometry, with its same camera and anchor.
    CURRENT.clear()
    with bpy.data.libraries.load(str(ROOT.parent/'blender'/'water_temple_roof.blend')) as (src,dst):dst.objects=[n for n in src.objects if not n.startswith('Orthographic')]
    for obj in dst.objects:
        if obj.type=='MESH':scene.collection.objects.link(obj);obj.hide_render=False;CURRENT.append(obj)
    record=configure_camera((216,116));record['pivot'][1]+=0 # kept in metadata; scene uses existing front-eave attachment
    records['roof']=record;record['triangles']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in CURRENT)
    # Roof textures have already been packed by the earlier pipeline.
    for obj in CURRENT:
        mat=obj.data.materials[0]
        if 'photo' not in mat:
            tex=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE');name='roof_'+tex.image.name.split('.')[0]
            tex.image.filepath_raw=str(ROOT/'textures'/(name+'.png'));tex.image.save();mat['photo']=name
            MATERIALS[mat.name]=mat
    export_obj('roof',record);bindings={o.name:o.data.materials[0] for o in CURRENT}
    scene.view_settings.view_transform='Standard';scene.render.image_settings.color_depth='8';render('roof_color')
    scene.view_settings.view_transform='Raw';scene.render.image_settings.color_depth='16'
    for mode in ('normal','position','ao'):
        cached={}
        for obj in CURRENT:
            mat=bindings[obj.name]
            if mat.name not in cached:cached[mat.name]=data_material(mat,mode,record)
            obj.data.materials[0]=cached[mat.name]
        render('roof_'+mode)
    for obj in CURRENT:obj.data.materials[0]=bindings[obj.name]
    SETS['roof']=list(CURRENT)
    mtl=[]
    for name,mat in MATERIALS.items():
        mtl.extend(['newmtl '+mat.name,'Kd 1 1 1','Ka 0 0 0','Ks 0 0 0','d 1','map_Kd ../textures/'+mat['photo']+'.png',''])
    (MODELS/'materials.mtl').write_text('\n'.join(mtl))
    (ROOT/'bakes.json').write_text(json.dumps(records,indent=2))
    # Editable kit laid out in rows. The canonical model OBJ files remain local.
    for index,(name,objects) in enumerate(SETS.items()):
        collection=bpy.data.collections.new(name);scene.collection.children.link(collection)
        for obj in objects:
            for old in list(obj.users_collection):old.objects.unlink(obj)
            collection.objects.link(obj);obj.hide_render=False;obj.location.x+=(index%5)*170;obj.location.y+=(index//5)*150
    scene.view_settings.view_transform='Standard';scene.render.image_settings.color_depth='8'
    scene.camera.location=(400,-660,700);target=Vector((400,225,0));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=940;scene.camera.data.clip_end=5000
    scene.render.resolution_x=1280;scene.render.resolution_y=900
    scene['kit_spacing']=[170,150]
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'water_temple_kit.blend'))
    render('kit_overview')
    print('TEMPLE_KIT_COMPLETE',flush=True)


if __name__=='__main__':main()
