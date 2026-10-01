"""Small loader for our triangulated OBJ exports, using explicit Raylib buffers.

The installed Raylib OBJ loader stalls on these exports. This bounded parser
supports our v/vt/vn triangles and groups by material once at startup.
"""
from array import array
from pathlib import Path
import pyray as pr


def load(path,shader,textures):
    path=Path(path);vertices=[];uvs=[];normals=[];groups={};current=None;materials={}
    for line in path.read_text().splitlines():
        pieces=line.split()
        if not pieces:continue
        key=pieces[0]
        if key=='mtllib':
            mtl=path.parent/' '.join(pieces[1:]);name=None
            for row in mtl.read_text().splitlines():
                head,_,rest=row.partition(' ')
                if head=='newmtl':name=rest.strip()
                if head=='map_Kd':materials[name]=(mtl.parent/rest.strip()).resolve()
        elif key=='v':vertices.append(tuple(map(float,pieces[1:4])))
        elif key=='vt':uvs.append(tuple(map(float,pieces[1:3])))
        elif key=='vn':normals.append(tuple(map(float,pieces[1:4])))
        elif key=='usemtl':current=' '.join(pieces[1:])
        elif key=='f':
            if len(pieces)!=4:raise ValueError('Expected triangulated OBJ: '+str(path))
            values=groups.setdefault(current,[[],[],[]])
            for item in pieces[1:]:
                vi,ti,ni=map(int,item.split('/'))
                values[0].extend(vertices[vi-1]);values[1].extend((uvs[ti-1][0],1-uvs[ti-1][1]));values[2].extend(normals[ni-1])
    models=[]
    for material,values in groups.items():
        mesh=pr.ffi.new('Mesh *');mesh.vertexCount=len(values[0])//3;mesh.triangleCount=mesh.vertexCount//3
        for field,items in zip(('vertices','texcoords','normals'),values):
            packed=array('f',items).tobytes();memory=pr.rl.MemAlloc(len(packed));pr.ffi.memmove(memory,packed,len(packed));setattr(mesh,field,pr.ffi.cast('float *',memory))
        pr.rl.UploadMesh(mesh,False);model=pr.rl.LoadModelFromMesh(mesh[0]);model.materials[0].shader=shader
        image=materials[material]
        if image not in textures:
            textures[image]=pr.load_texture(str(image));pr.set_texture_filter(textures[image],pr.TEXTURE_FILTER_POINT);pr.set_texture_wrap(textures[image],pr.TEXTURE_WRAP_REPEAT)
        model.materials[0].maps[pr.MATERIAL_MAP_DIFFUSE].texture=textures[image];models.append(model)
    return models
