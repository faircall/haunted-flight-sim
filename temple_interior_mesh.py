"""Small Blender mesh authoring helper; all inputs are game X/up/Z metres."""
import math
import bpy
import bmesh
from mathutils import Vector

class Mesh:
    def __init__(self,name,material,tiles=None):
        self.name=name;self.material=material;self.tiles=tiles;self.vertices=[];self.faces=[];self.uv=[];self.smooth=[]
    def face(self,points,tile=0,uv=None,smooth=False):
        first=len(self.vertices);self.vertices.extend(tuple(p) for p in points);self.faces.append(list(range(first,len(self.vertices))));self.smooth.append(smooth)
        if uv is None:
            tile=self.tiles.index(tile) if isinstance(tile,str) else tile
            n=4 if self.tiles else 2;u=tile%n/n;v=1-(tile//n+1)/n;pad=.0645 if self.tiles else .002
            uv=[(u+pad,v+pad),(u+1/n-pad,v+pad),(u+1/n-pad,v+1/n-pad),(u+pad,v+1/n-pad)]
            if len(points)!=4:
                radius=.0605 if self.tiles else .47/n
                uv=[(u+.5/n+math.cos(i*math.tau/len(points))*radius,v+.5/n+math.sin(i*math.tau/len(points))*radius) for i in range(len(points))]
        self.uv.append(uv)
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
            face=[points[i] for i in ids]
            if (face[1]-face[0]).cross(face[2]-face[0]).dot(sum(face,Vector())/4-center)<0:face.reverse()
            self.face(face,tile)
    def lathe(self,c,profile,tile,sides=16,scale=(1,1,1)):
        x,y,z=c
        tile_index=self.tiles.index(tile) if isinstance(tile,str) else tile
        tu=tile_index%4/4;tv=1-(tile_index//4+1)/4
        for row,((ya,ra),(yb,rb)) in enumerate(zip(profile,profile[1:])):
            for i in range(sides):
                a=i*math.tau/sides;b=(i+1)*math.tau/sides
                self.face([(x+ra*math.cos(a)*scale[0],y+ya*scale[1],z+ra*math.sin(a)*scale[2]),
                           (x+rb*math.cos(a)*scale[0],y+yb*scale[1],z+rb*math.sin(a)*scale[2]),
                           (x+rb*math.cos(b)*scale[0],y+yb*scale[1],z+rb*math.sin(b)*scale[2]),
                           (x+ra*math.cos(b)*scale[0],y+ya*scale[1],z+ra*math.sin(b)*scale[2])],tile,
                          uv=[(tu+.0645+i/sides*.121,tv+.0645+row/(len(profile)-1)*.121),
                              (tu+.0645+i/sides*.121,tv+.0645+(row+1)/(len(profile)-1)*.121),
                              (tu+.0645+(i+1)/sides*.121,tv+.0645+(row+1)/(len(profile)-1)*.121),
                              (tu+.0645+(i+1)/sides*.121,tv+.0645+row/(len(profile)-1)*.121)],smooth=True)
    def ellipsoid(self,c,size,tile,segments=16,rings=10):
        profile=[(math.cos(math.pi*j/rings),max(.00001,math.sin(math.pi*j/rings))) for j in range(rings,-1,-1)]
        self.lathe(c,profile,tile,segments,size)
    def export(self,out):
        groups=[];current=[];count=0
        for face,uv,smooth in zip(self.faces,self.uv,self.smooth):
            if count+len(face)>45000:groups.append(current);current=[];count=0
            current.append((face,uv,smooth));count+=len(face)
        if current:groups.append(current)
        objects=[]
        for i,group in enumerate(groups):
            verts=[];faces=[];coords=[];shades=[]
            for ids,uv,smooth in group:
                start=len(verts);verts.extend((self.vertices[j][0],-self.vertices[j][2],self.vertices[j][1]) for j in ids)
                faces.append(list(range(start,len(verts))));coords.append(uv);shades.append(smooth)
            mesh=bpy.data.meshes.new(self.name+str(i));mesh.from_pydata(verts,[],faces);mesh.update()
            obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);mesh.materials.append(self.material)
            layer=mesh.uv_layers.new(name='Painted colour')
            for poly,uv,smooth in zip(mesh.polygons,coords,shades):
                poly.use_smooth=smooth
                for loop,coord in zip(poly.loop_indices,uv):layer.data[loop].uv=coord
            # Share positions for smooth carved surfaces while retaining each
            # loop's UVs and flat normals on the architectural faces.
            bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000005)
            bm.to_mesh(mesh);bm.free();mesh.update()
            objects.append(obj)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.export_scene.gltf(filepath=str(out/(self.name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        return dict(triangles=sum(len(f)-2 for f in self.faces),vertices=len(self.vertices),primitives=len(objects))
