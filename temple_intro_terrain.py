"""Bounded curved terrain chunks, planted undergrowth and three stone bridges."""
import math
import random
import numpy as np
import pyray as pr
from g_intro_landscape import (CHUNK_LENGTH,BRIDGES,world_point,road_x,road_slope,
                               local_point,bank_height,bridge_distance,road_height,
                               POLE_SPACING,power_pole,power_wire,terrain_point,trees_between,
                               main_bank_height,main_road_height,main_road_x,main_coordinates,
                               trail_fraction,junction_station,shore_distance,river_station,
                               river_height,river_half_width,BRIDGE_HALF,DRAW_BEHIND,DRAW_AHEAD,main_side_on_section,
                               RIVER_UPSTREAM,RIVER_DOWNSTREAM,clearing_amount,temple_ground)


class Builder:
    def __init__(self):self.vertices=[];self.normals=[];self.uv=[];self.wind=[];self.colours=[]

    def face(self,points,colour=(255,255,255,255)):
        points=np.asarray(points,dtype=np.float32)
        triangles=points[np.asarray([(0,i,i+1) for i in range(1,len(points)-1)])]
        normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);length=np.linalg.norm(normals,axis=1)
        valid=length>1e-8
        if not valid.any():return
        vertices=triangles[valid].reshape(-1,3);normals=np.repeat(normals[valid]/length[valid,None],3,axis=0)
        order=range(len(vertices))
        self.vertices.append(vertices);self.normals.append(normals)
        self.uv.append(np.zeros((len(order),2),dtype=np.float32));self.wind.append(np.zeros((len(order),2),dtype=np.float32))
        self.colours.append(np.tile(np.asarray(colour,dtype=np.uint8),(len(order),1)))

    def instance(self,prototype,position,scale,yaw,colour):
        xyz,normals,uv,wind=prototype;c,s=math.cos(yaw),math.sin(yaw)
        rotation=np.array(((c,0,s),(0,1,0),(-s,0,c)),dtype=np.float32)
        self.vertices.append(xyz.dot(rotation.T)*scale+position);self.normals.append(normals.dot(rotation.T))
        self.uv.append(uv);self.wind.append(wind);self.colours.append(np.tile(np.array(colour,dtype=np.uint8),(len(xyz),1)))

    def tube(self,a,b,radius,colour,sides=5,end_radius=None):
        a,b=np.asarray(a),np.asarray(b);axis=b-a;axis/=np.linalg.norm(axis)
        across=np.cross(axis,(0,1,0) if abs(axis[1])<.95 else (1,0,0));across/=np.linalg.norm(across)
        up=np.cross(axis,across)
        ring=[radius*(across*math.cos(i*math.tau/sides)+up*math.sin(i*math.tau/sides)) for i in range(sides)]
        taper=1 if end_radius is None else end_radius/radius
        for i,r in enumerate(ring):
            q=ring[(i+1)%sides];self.face((a+r,a+q,b+q*taper,b+r*taper),colour)
        self.face([a+r for r in ring][::-1],colour);self.face([b+r*taper for r in ring],colour)

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
    def values(pointer,size):return np.frombuffer(pr.ffi.buffer(pointer,count*size*4),dtype='<f4').reshape(count,size).copy() if pointer else np.zeros((count,size),dtype=np.float32)
    order=np.frombuffer(pr.ffi.buffer(mesh.indices,mesh.triangleCount*6),dtype='<u2').copy() if mesh.indices else np.arange(count)
    return tuple(values(ptr,size)[order] for ptr,size in ((mesh.vertices,3),(mesh.normals,3),(mesh.texcoords,2),(mesh.texcoords2,2)))


class Terrain:
    def __init__(self,models,shader):
        self.chunks={};self.shader=shader;self.active=set();self.preloaded=set()
        self.prototypes={name:prototype(models[name]) for name in ('shrub','fern')}
        self.trees={name:[prototype(models[name],i) for i in range(models[name].meshCount)] for name in ('chinese_pine_a','chinese_pine_b','chinese_pine_c')}
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
        start=index*CHUNK_LENGTH;origin=road_x(start,arrival);bank=Builder();road=Builder();dirt=Builder();plants=Builder();bridge=Builder();utilities=Builder();clearing=Builder();river=Builder();snags=Builder()
        forest={name:Builder() for name,_,_ in self.forest}
        def p(station,side,y):
            x,z=terrain_point(station,side,arrival);return (x-origin,y,z+start)
        def pm(station,side,y):
            x,z=world_point(station,side,main=True);return (x-origin,y,z+start)
        cross=(-180,-140,-110,-84,-62,-48,-38,-28,-21,-16,-12,-9,-7,-5,-4,-2,2,3,4.5,6,8,10,13,16,20,24,30,40,54,70,90,115,140,180,220)
        sections={s:sorted(list(cross)+[main_side_on_section(s,side,arrival) for side in (-8,-4,-2,0,2,4,8,shore_distance(s))])
                  for s in range(start,start+CHUNK_LENGTH+1,2)}
        for station in range(start,start+CHUNK_LENGTH,2):
            end=station+2
            left,right=sections[station],sections[end]
            for i in range(len(left)-1):
                a,b=left[i:i+2];aa,bb=right[i:i+2]
                bank.face([p(station,a,bank_height(station,a,arrival)),p(end,aa,bank_height(end,aa,arrival)),
                           p(end,bb,bank_height(end,bb,arrival)),p(station,b,bank_height(station,b,arrival))][::-1])
            # Road cross-sections follow the normal, so width is constant on bends.
            if station<junction_station(arrival)+2:
                ya=road_height(station,arrival)+.007;yb=road_height(end,arrival)+.007
                if bridge_distance(station+1)>BRIDGE_HALF:
                    road.face([p(station,-1.92,ya),p(station,1.92,ya),p(end,1.92,yb),p(end,-1.92,yb)],(79,86,78,255))
            else:
                ya=road_height(station,arrival)+.012;yb=road_height(end,arrival)+.012
                width=1.68+1.45*(1-trail_fraction(station,arrival))
                # Several strips supply reliable along/across UVs for ruts and grass.
                for a,b in zip((-width,-1.05,-.57,.57,1.05),(-1.05,-.57,.57,1.05,width)):
                    if station>=arrival-20:continue
                    dirt.face([p(station,a,ya),p(station,b,ya),p(end,b,yb),p(end,a,yb)],(156,149,114,255))
                    dirt.uv[-1]=np.array(((a,station),(b,station),(b,end),(a,station),(b,end),(a,end)),dtype=np.float32)
                # The public road keeps following the lake after our turnoff.
                road.face([pm(station,-1.92,main_road_height(station)+.014),pm(station,1.92,main_road_height(station)+.014),
                           pm(end,1.92,main_road_height(end)+.014),pm(end,-1.92,main_road_height(end)+.014)],(79,86,78,255))
            if arrival-46<station<arrival+7:
                for a in range(-20,20,2):
                    b=a+2
                    if clearing_amount(station+1,a+1,arrival)<=0:continue
                    clearing.face([p(station,a,bank_height(station,a,arrival)+.028),p(station,b,bank_height(station,b,arrival)+.028),
                                   p(end,b,bank_height(end,b,arrival)+.028),p(end,a,bank_height(end,a,arrival)+.028)])
                    clearing.uv[-1]=np.array(((a,station-arrival+20),(b,station-arrival+20),(b,end-arrival+20),
                                             (a,station-arrival+20),(b,end-arrival+20),(a,end-arrival+20)),dtype=np.float32)
        def block(station,side,y,width,height,length,colour):
            a,b=station-length/2,station+length/2;l,r=side-width/2,side+width/2;lo,hi=y-height/2,y+height/2
            vertices=[p(s,x,yy+road_height(s,arrival)) for s in (a,b) for x,yy in ((l,lo),(r,lo),(r,hi),(l,hi))]
            for face in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(1,5,6,2),(0,3,7,4)):
                bridge.face([vertices[i] for i in face],colour)
        stone=(154,169,145,255);cap=(183,193,172,255)
        for center in BRIDGES:
            for offset in range(-BRIDGE_HALF,BRIDGE_HALF):
                station=center+offset+.5
                if not start<=station<start+CHUNK_LENGTH:continue
                block(station,0,-.105,4.55,.20,1.,stone)
                for sign in (-1,1):
                    block(station,sign*2.13,.735,.25,.15,1.02,cap)
                    a=center+offset;b=a+1
                    ya=-.26-1.7*(abs(offset)/BRIDGE_HALF)**2;yb=-.26-1.7*(abs(offset+1)/BRIDGE_HALF)**2
                    vertices=[p(a,sign*2.24,ya+road_height(a,arrival)),p(b,sign*2.24,yb+road_height(b,arrival)),
                              p(b,sign*2.24,-.12+road_height(b,arrival)),p(a,sign*2.24,-.12+road_height(a,arrival))]
                    bridge.face(vertices if sign==1 else vertices[::-1],stone)
                if offset%2==0:
                    for side in (-2.13,2.13):block(station,side,.4,.23,.92,.25,cap)
            for offset in (-BRIDGE_HALF-.1,BRIDGE_HALF+.1):
                station=center+offset
                if start<=station<start+CHUNK_LENGTH:
                    for side in (-2.13,2.13):block(station,side,.37,.46,1.0,.48,stone)
            if start<=center<start+CHUNK_LENGTH:
                for side in range(RIVER_UPSTREAM,RIVER_DOWNSTREAM,2):
                    next_side=side+2
                    a=river_station(center,side);b=river_station(center,next_side)
                    wa=river_half_width(side)+.35;wb=river_half_width(next_side)+.35
                    river.face([pm(a-wa,side,river_height(side)),pm(a+wa,side,river_height(side)),
                                pm(b+wb,next_side,river_height(next_side)),pm(b-wb,next_side,river_height(next_side))][::-1])
                    river.uv[-1]=np.array(((0,next_side),(1,next_side),(1,side),(0,next_side),(1,side),(0,side)),dtype=np.float32)
                    if side< -142:
                        # Carry the channel and both banks well beyond the scene
                        # fade; do not terminate water at the terrain-strip edge.
                        for sign in (-1,1):
                            inner_a=a+sign*wa;inner_b=b+sign*wb
                            points=[pm(inner_a,side,river_height(side)-.15),pm(inner_b,next_side,river_height(next_side)-.15),
                                    pm(inner_b+sign*27,next_side,river_height(next_side)+7),pm(inner_a+sign*27,side,river_height(side)+7)]
                            bank.face(points if sign==1 else points[::-1])
        rng=random.Random(index*9127+625)
        for i in range(190):
            station=start+rng.random()*CHUNK_LENGTH
            trail=trail_fraction(station,arrival)>.5
            side=(-3.8-rng.random()**1.65*42) if (i%3 if trail else i%10) else (3.6+rng.random()*18 if trail else 4+rng.random()*12)
            if bridge_distance(station)<BRIDGE_HALF+5 or temple_ground(station,side,arrival):continue
            y=bank_height(station,side,arrival)
            if y<-.45:continue
            species='fern' if i%3 else 'shrub';size=rng.uniform(.65,1.28) if species=='fern' else rng.uniform(1.0,2.1)
            if side>0:size*=.55
            position=np.asarray(p(station,side,y-.035),dtype=np.float32)
            green=rng.randrange(205,256)
            plants.instance(self.prototypes[species],position,size,rng.random()*math.tau,(green,255,green-15,255))
        # Near pines are part of persistent batches too: looking back never
        # crosses a separate 25m tree culling plane or hundreds of Python draws.
        for tree in trees_between(start,start+CHUNK_LENGTH,arrival):
            station,side=tree['station'],tree['side'];position=np.asarray(p(station,side,tree['y']))
            colour=(161,185,158,255) if trail_fraction(station,arrival)>.5 else (233,251,231,255)
            for data in self.trees[tree['kind']]:
                name='forest_leaf' if data[3][:,0].max()>.1 else 'forest_wood'
                forest[name].instance(data,position,tree['scale'],math.radians(tree['yaw']),colour)
        for i in range(9):
            station=start+rng.random()*CHUNK_LENGTH;side=-34-rng.random()*29
            if bridge_distance(station)<BRIDGE_HALF+5 or temple_ground(station,side,arrival):continue
            position=np.asarray(p(station,side,bank_height(station,side,arrival)),dtype=np.float32)
            scale=rng.uniform(1.1,1.7);yaw=rng.random()*math.tau
            for name,data,_ in self.forest:forest[name].instance(data,position,scale,yaw,(227,250,225,255))
        # Irregular low thickets follow the public shoreline past the turnoff.
        for i in range(150):
            station=start+rng.random()*CHUNK_LENGTH
            if rng.random()>.60+.25*math.sin(station/17)+.14*math.sin(station/5):continue
            side=4.4+rng.random()*(shore_distance(station)-4.5);y=main_bank_height(station,side)
            if y< -1.13:continue
            plants.instance(self.prototypes['shrub' if i%4 else 'fern'],np.asarray(pm(station,side,y-.03)),
                            rng.uniform(.55,1.22),rng.random()*math.tau,(rng.randrange(175,225),235,180,255))
        # Crooked bare limbs and exposed roots silhouette the private mountain track.
        for i in range(6):
            station=start+rng.random()*CHUNK_LENGTH
            if station<junction_station(arrival)+25 or temple_ground(station,0,arrival):continue
            side=(-1 if i%2 else 1)*rng.uniform(4.3,8.5);base=np.asarray(p(station,side,bank_height(station,side,arrival)))
            lean=-math.copysign(1,side);h=rng.uniform(5.3,8.1)
            points=[base+np.array((lean*(t*t*1.7+.24*math.sin(t*8)),h*t,.5*math.sin(t*5+i))) for t in (0,.22,.48,.72,1)]
            for k,(a,b) in enumerate(zip(points,points[1:])):snags.tube(a,b,.24-k*.043,(62,71,59,255),7,end_radius=.20-k*.043)
            for k in range(2,5):
                a=points[k];b=a+(lean*rng.uniform(.9,2.4),rng.uniform(.2,.8),rng.uniform(-1.7,1.7));c=b+(lean*.7,1.2,.3)
                snags.tube(a,b,.082,(66,76,63,255),5,end_radius=.042);snags.tube(b,c,.042,(66,76,63,255),5,end_radius=.008)
            for angle in range(0,360,60):
                q=base+np.array((math.cos(math.radians(angle))*.85,.02,math.sin(math.radians(angle))*.85))
                snags.tube(base+(0,.25,0),q,.17,(62,71,59,255),5,end_radius=.04)
        # Entire spans are owned by their starting pole's chunk. Adjacent chunks
        # share endpoints, so the three uphill conductors never terminate on a cut.
        def chunk_point(point):return np.asarray((point[0]-origin,point[1],point[2]+start),dtype=float)
        for station in range(math.ceil(start/POLE_SPACING)*POLE_SPACING,start+CHUNK_LENGTH,POLE_SPACING):
            base=np.asarray(power_pole(station,arrival));top=base+(0,6.,0)
            utilities.tube(chunk_point(base),chunk_point(top),.095,(114,122,112,255),7)
            utilities.tube(chunk_point(top+(-.72,-.12,0)),chunk_point(top+(.72,-.12,0)),.055,(67,76,71,255),4)
            for conductor in (-1,0,1):
                peg=base+(conductor*.48,5.86,0)
                utilities.tube(chunk_point(peg),chunk_point(peg+(0,.25,0)),.072,(154,173,159,255),6)
                wire=power_wire(station,conductor,arrival)
                for a,b in zip(wire,wire[1:]):utilities.tube(chunk_point(a),chunk_point(b),.017,(39,49,46,255),4)
        result=dict(bank=bank.model(self.shader),road=road.model(self.shader),dirt=dirt.model(self.shader),plants=plants.model(self.shader,self.texture),
                    bridge=bridge.model(self.shader),river=river.model(self.shader),clearing=clearing.model(self.shader),snags=snags.model(self.shader),utilities=utilities.model(self.shader))
        result.update({name:forest[name].model(self.shader,texture) for name,_,texture in self.forest})
        return result

    def warm_route(self,arrival):
        # Build this short cinematic's bounded route before playback. No Python
        # mesh generation/upload stalls when the moving car crosses a chunk seam.
        self.route_arrival=arrival
        self.preloaded=set(range(-math.ceil(DRAW_BEHIND/CHUNK_LENGTH)-1,min(80,math.ceil(arrival/CHUNK_LENGTH)+math.ceil(DRAW_AHEAD/CHUNK_LENGTH)+2)))
        for index in sorted(self.preloaded):self.chunks[index]=self.build(index,arrival)

    def update(self,distance,arrival):
        if self.preloaded and abs(arrival-self.route_arrival)>.01:
            self.close();self.warm_route(arrival)
        first=math.floor((distance-DRAW_BEHIND)/CHUNK_LENGTH);last=math.ceil((distance+DRAW_AHEAD)/CHUNK_LENGTH)
        wanted=set(range(first,last+1))
        for index in list(self.chunks):
            if index not in wanted and index not in self.preloaded:
                for model in self.chunks.pop(index).values():
                    if model is not None:pr.unload_model(model)
        for index in sorted(wanted):
            if index not in self.chunks:self.chunks[index]=self.build(index,arrival)
        self.active=wanted

    def draw(self,kind,distance):
        count=0;yaw=math.degrees(math.atan(road_slope(distance,self.route_arrival)))
        for index in sorted(self.active):
            models=self.chunks[index]
            model=models[kind]
            if model is None:continue
            x,z=local_point(index*CHUNK_LENGTH,0,distance,self.route_arrival)
            pr.draw_model_ex(model,pr.Vector3(x,0,z),pr.Vector3(0,1,0),yaw,pr.Vector3(1,1,1),pr.WHITE);count+=1
        return count

    def close(self):
        for models in self.chunks.values():
            for model in models.values():
                if model is not None:pr.unload_model(model)
        self.chunks.clear()
