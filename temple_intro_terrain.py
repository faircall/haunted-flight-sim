"""Bounded curved terrain chunks, planted undergrowth and three stone bridges."""
import math
import random
import numpy as np
import pyray as pr
from g_intro_landscape import (CHUNK_LENGTH,BRIDGES,world_point,road_x,road_slope,
                               local_point,bank_height,bridge_distance)


class Builder:
    def __init__(self):self.vertices=[];self.normals=[];self.uv=[];self.wind=[];self.colours=[]

    def face(self,points,colour=(255,255,255,255)):
        points=np.asarray(points,dtype=np.float32)
        normal=np.cross(points[1]-points[0],points[2]-points[0]);normal/=max(.00001,np.linalg.norm(normal))
        order=[v for i in range(1,len(points)-1) for v in (0,i,i+1)]
        self.vertices.append(points[order]);self.normals.append(np.tile(normal,(len(order),1)))
        self.uv.append(np.zeros((len(order),2),dtype=np.float32));self.wind.append(np.zeros((len(order),2),dtype=np.float32))
        self.colours.append(np.tile(np.asarray(colour,dtype=np.uint8),(len(order),1)))

    def instance(self,prototype,position,scale,yaw,colour):
        xyz,normals,uv,wind=prototype;c,s=math.cos(yaw),math.sin(yaw)
        rotation=np.array(((c,0,s),(0,1,0),(-s,0,c)),dtype=np.float32)
        self.vertices.append(xyz.dot(rotation.T)*scale+position);self.normals.append(normals.dot(rotation.T))
        self.uv.append(uv);self.wind.append(wind);self.colours.append(np.tile(np.array(colour,dtype=np.uint8),(len(xyz),1)))

    def model(self,shader,texture=None):
        if not self.vertices:return None
        mesh=pr.ffi.new('Mesh *');mesh.vertexCount=sum(len(v) for v in self.vertices);mesh.triangleCount=mesh.vertexCount//3
        for name,values,dtype,ctype in (('vertices',self.vertices,'<f4','float *'),('normals',self.normals,'<f4','float *'),
                    ('texcoords',self.uv,'<f4','float *'),('texcoords2',self.wind,'<f4','float *'),('colors',self.colours,'u1','unsigned char *')):
            data=np.concatenate(values).astype(dtype).tobytes();memory=pr.rl.MemAlloc(len(data));pr.ffi.memmove(memory,data,len(data))
            setattr(mesh,name,pr.ffi.cast(ctype,memory))
        pr.rl.UploadMesh(mesh,False);model=pr.rl.LoadModelFromMesh(mesh[0]);model.materials[0].shader=shader
        if texture is not None:model.materials[0].maps[pr.MATERIAL_MAP_DIFFUSE].texture=texture
        return model


def prototype(model,index=0):
    mesh=model.meshes[index];count=mesh.vertexCount
    def values(pointer,size):return np.frombuffer(pr.ffi.buffer(pointer,count*size*4),dtype='<f4').reshape(count,size).copy()
    order=np.frombuffer(pr.ffi.buffer(mesh.indices,mesh.triangleCount*6),dtype='<u2').copy() if mesh.indices else np.arange(count)
    return tuple(values(ptr,size)[order] for ptr,size in ((mesh.vertices,3),(mesh.normals,3),(mesh.texcoords,2),(mesh.texcoords2,2)))


class Terrain:
    def __init__(self,models,shader):
        self.chunks={};self.shader=shader;self.active=set();self.preloaded=set()
        self.prototypes={name:prototype(models[name]) for name in ('shrub','fern')}
        pine=models['chinese_pine_b'];self.forest=[]
        for i in range(pine.meshCount):
            data=prototype(pine,i);material=pine.materials[pine.meshMaterial[i]]
            texture=pr.ffi.new('Texture2D *',material.maps[pr.MATERIAL_MAP_DIFFUSE].texture)[0]
            name='forest_leaf' if data[3][:,0].max()>.1 else 'forest_wood'
            self.forest.append((name,data,texture))
        self.texture=pr.ffi.new('Texture2D *',models['shrub'].materials[0].maps[pr.MATERIAL_MAP_DIFFUSE].texture)[0]
        # The glTF loader may include a default material before the painted one.
        for i in range(models['shrub'].materialCount):
            candidate=models['shrub'].materials[i].maps[pr.MATERIAL_MAP_DIFFUSE].texture
            if candidate.id!=pr.rl.rlGetTextureIdDefault() and candidate.id:self.texture=pr.ffi.new('Texture2D *',candidate)[0]

    def build(self,index,arrival):
        start=index*CHUNK_LENGTH;origin=road_x(start);bank=Builder();road=Builder();plants=Builder();bridge=Builder()
        forest={name:Builder() for name,_,_ in self.forest}
        def p(station,side,y):
            x,z=world_point(station,side);return (x-origin,y,z+start)
        cross=(-96,-72,-52,-38,-28,-21,-16,-12,-9,-7,-5,-4,-2,2,2.6,3.4,4.6,7,10)
        for station in range(start,start+CHUNK_LENGTH,2):
            end=station+2
            for a,b in zip(cross,cross[1:]):
                bank.face([p(station,a,bank_height(station,a)),p(end,a,bank_height(end,a)),
                           p(end,b,bank_height(end,b)),p(station,b,bank_height(station,b))][::-1])
            # Road cross-sections follow the normal, so width is constant on bends.
            road.face([p(station,-1.92,.007),p(station,1.92,.007),p(end,1.92,.007),p(end,-1.92,.007)],(79,91,83,255))
        def block(station,side,y,width,height,length,colour):
            a,b=station-length/2,station+length/2;l,r=side-width/2,side+width/2;lo,hi=y-height/2,y+height/2
            vertices=[p(s,x,yy) for s in (a,b) for x,yy in ((l,lo),(r,lo),(r,hi),(l,hi))]
            for face in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(1,5,6,2),(0,3,7,4)):
                bridge.face([vertices[i] for i in face],colour)
        stone=(154,169,145,255);cap=(183,193,172,255)
        for center in BRIDGES:
            for offset in range(-7,7):
                station=center+offset+.5
                if not start<=station<start+CHUNK_LENGTH:continue
                block(station,0,-.105,4.55,.20,1.,stone)
                for sign in (-1,1):
                    block(station,sign*2.13,.735,.25,.15,1.02,cap)
                    a=center+offset;b=a+1
                    ya=-.26-1.3*(abs(offset)/7)**2;yb=-.26-1.3*(abs(offset+1)/7)**2
                    vertices=[p(a,sign*2.24,ya),p(b,sign*2.24,yb),p(b,sign*2.24,-.12),p(a,sign*2.24,-.12)]
                    bridge.face(vertices if sign==1 else vertices[::-1],stone)
                if offset%2==0:
                    for side in (-2.13,2.13):block(station,side,.4,.23,.92,.25,cap)
            for offset in (-7.1,7.1):
                station=center+offset
                if start<=station<start+CHUNK_LENGTH:
                    for side in (-2.13,2.13):block(station,side,.37,.46,1.0,.48,stone)
        rng=random.Random(index*9127+625)
        for i in range(190):
            station=start+rng.random()*CHUNK_LENGTH
            side=-3.8-rng.random()**1.65*42 if i%10 else 2.8+rng.random()*.7
            if bridge_distance(station)<10 or abs(station-arrival)<12 and side>-10:continue
            y=bank_height(station,side)
            if y<-.45:continue
            species='fern' if i%3 else 'shrub';size=rng.uniform(.65,1.28) if species=='fern' else rng.uniform(1.0,2.1)
            if side>0:size*=.55
            position=np.asarray(p(station,side,y-.035),dtype=np.float32)
            green=rng.randrange(205,256)
            plants.instance(self.prototypes[species],position,size,rng.random()*math.tau,(green,255,green-15,255))
        for i in range(13):
            station=start+rng.random()*CHUNK_LENGTH;side=-34-rng.random()*29
            if bridge_distance(station)<11:continue
            position=np.asarray(p(station,side,bank_height(station,side)),dtype=np.float32)
            scale=rng.uniform(1.1,1.7);yaw=rng.random()*math.tau
            for name,data,_ in self.forest:forest[name].instance(data,position,scale,yaw,(227,250,225,255))
        result=dict(bank=bank.model(self.shader),road=road.model(self.shader),plants=plants.model(self.shader,self.texture),bridge=bridge.model(self.shader))
        result.update({name:forest[name].model(self.shader,texture) for name,_,texture in self.forest})
        return result

    def warm_route(self,arrival):
        # Build this short cinematic's bounded route before playback. No Python
        # mesh generation/upload stalls when the moving car crosses a chunk seam.
        self.route_arrival=arrival
        self.preloaded=set(range(-2,min(64,math.ceil(arrival/CHUNK_LENGTH)+5)))
        for index in sorted(self.preloaded):self.chunks[index]=self.build(index,arrival)

    def update(self,distance,arrival):
        if self.preloaded and abs(arrival-self.route_arrival)>.01:
            self.close();self.warm_route(arrival)
        first=math.floor((distance-32)/CHUNK_LENGTH);wanted=set(range(first,first+5))
        for index in list(self.chunks):
            if index not in wanted and index not in self.preloaded:
                for model in self.chunks.pop(index).values():
                    if model is not None:pr.unload_model(model)
        for index in sorted(wanted):
            if index not in self.chunks:self.chunks[index]=self.build(index,arrival)
        self.active=wanted

    def draw(self,kind,distance):
        count=0;yaw=math.degrees(math.atan(road_slope(distance)))
        for index in sorted(self.active):
            models=self.chunks[index]
            model=models[kind]
            if model is None:continue
            x,z=local_point(index*CHUNK_LENGTH,0,distance)
            pr.draw_model_ex(model,pr.Vector3(x,0,z),pr.Vector3(0,1,0),yaw,pr.Vector3(1,1,1),pr.WHITE);count+=1
        return count

    def close(self):
        for models in self.chunks.values():
            for model in models.values():
                if model is not None:pr.unload_model(model)
        self.chunks.clear()
