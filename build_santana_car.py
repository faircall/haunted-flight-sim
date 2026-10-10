"""Blender authoring: a reference-proportioned Santana, around 21,000 triangles.

Dedicated 256px exterior/interior and 128px wheel atlases. The empty body follows
the reference silhouette; actors fit it afterwards. Wet window anchors are
shared with the renderer. All texture pixels are
authored here; the supplied reference sheets guide shape, trim and upholstery.
"""
from pathlib import Path
import math
import random
import bpy
from mathutils import Vector
from g_santana_geometry import (AXLES,WHEEL_X,WHEEL_Y,TYRE_RADIUS,STEERING,window_panes,
                                roof_height,wiper_segments,WIPER_PIVOTS)


class Atlas:
    def __init__(self,name,size):
        self.name=name;self.size=size;self.pixels=[(35,39,41,255)]*(size*size);self.regions={}

    def pixel(self,x,y,c):
        if 0<=x<self.size and 0<=y<self.size:self.pixels[y*self.size+x]=tuple(c)+(255,) if len(c)==3 else tuple(c)

    def rect(self,x,y,w,h,c):
        for yy in range(y,y+h):
            for xx in range(x,x+w):self.pixel(xx,yy,c)

    def line(self,a,b,c,width=1):
        steps=max(abs(b[0]-a[0]),abs(b[1]-a[1]),1)
        for i in range(steps+1):
            x=round(a[0]+(b[0]-a[0])*i/steps);y=round(a[1]+(b[1]-a[1])*i/steps)
            self.rect(x-width//2,y-width//2,width,width,c)

    def circle(self,x,y,r,c,fill=False):
        for yy in range(y-r-1,y+r+2):
            for xx in range(x-r-1,x+r+2):
                d=math.hypot(xx-x,yy-y)
                if d<=r if fill else abs(d-r)<.7:self.pixel(xx,yy,c)

    def patch(self,name,rect,base,style='plain'):
        self.regions[name]=rect;x,y,w,h=rect;rng=random.Random(name)
        for v in range(h):
            for u in range(w):
                n=rng.choice((-2,-1,0,0,1,2));fade=0
                if style=='paint':fade=14*math.exp(-((v/h-.24)/.13)**2)-9*v/h
                if style=='cloth':n+=5 if (u-v)%5==0 else -3 if (u+2*v)%7==0 else 0
                if style=='carpet':n=rng.choice((-4,-2,0,2,4))
                if style=='liner':n//=2
                c=[max(0,min(255,round(b+n+fade))) for b in base]
                self.pixel(x+u,y+v,c)
        return rect

    def material(self,out):
        image=bpy.data.images.new(self.name,width=self.size,height=self.size,alpha=True)
        image.pixels=[v/255 for row in reversed(range(self.size)) for pixel in self.pixels[row*self.size:(row+1)*self.size] for v in pixel]
        image.filepath_raw=str(out/(self.name+'.png'));image.file_format='PNG';image.save();image.pack()
        material=bpy.data.materials.new(self.name);material.use_nodes=True
        material.use_backface_culling=True
        node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;node.interpolation='Closest'
        material.node_tree.links.new(node.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.72
        return material


def exterior_atlas():
    a=Atlas('santana_exterior',256)
    for name,rect,colour,style in (
        ('paint',(0,0,128,64),(65,73,78),'plain'),('hood',(128,0,128,64),(65,73,78),'plain'),
        ('doors',(0,64,128,64),(63,71,76),'plain'),('roof',(128,64,128,64),(65,73,78),'plain'),
        ('grille',(0,128,96,32),(21,25,27),'plain'),('headlight',(96,128,48,32),(171,177,168),'plain'),
        ('taillight',(144,128,48,32),(114,28,24),'plain'),('plate',(192,128,64,32),(30,56,88),'plain'),
        ('bumper',(0,160,96,32),(39,44,46),'plain'),('chrome',(96,160,48,32),(135,146,151),'plain'),
        ('glass',(144,160,48,32),(69,88,96),'paint'),('amber',(192,160,32,32),(157,90,27),'plain'),
        ('rubber',(224,160,32,32),(20,24,26),'plain'),('trunk',(0,192,128,64),(65,73,78),'plain'),
        ('details',(128,192,128,64),(63,71,76),'plain')):a.patch(name,rect,colour,style)
    for y in (132,138,144,150,156):
        a.line((3,y),(92,y),(68,77,78));a.line((3,y+1),(92,y+1),(12,17,18))
    # Small manufacturer badge and the broad rectangular sealed-beam reflector.
    a.circle(48,144,9,(156,166,168));a.line((43,139),(48,150),(164,174,176));a.line((48,150),(53,139),(164,174,176))
    a.line((42,143),(45,149),(164,174,176));a.line((45,149),(48,144),(164,174,176));a.line((48,144),(51,149),(164,174,176));a.line((51,149),(54,143),(164,174,176))
    for cx in (108,132):
        a.circle(cx,144,10,(209,210,191),True);a.circle(cx,144,8,(135,148,147));a.circle(cx-2,142,5,(192,198,184))
    for xx in range(98,143,4):a.line((xx,130),(xx,157),(150,160,151))
    a.line((97,130),(142,130),(227,228,211));a.line((97,157),(142,157),(69,78,77))
    for v in range(131,158,4):a.line((146,v),(189,v),(150,45,30))
    for x in (148,162,176):a.line((x,130),(x,158),(59,17,18))
    a.rect(147,131,12,7,(179,104,33));a.rect(177,149,11,8,(140,140,120))
    a.rect(195,132,58,24,(199,205,190));a.rect(196,133,56,22,(26,49,79))
    # Fictional plate: tiny bitmap characters rather than a copied registration.
    glyphs=('01110/10001/11111/10001/10001','11110/00001/01110/00001/11110',
            '00100/01100/00100/00100/01110','11111/00010/00100/01000/01000',
            '01110/10001/01110/10001/01110')
    for i,glyph in enumerate(glyphs):
        for row,bits in enumerate(glyph.split('/')):
            for col,bit in enumerate(bits):
                if bit=='1':a.rect(210+i*8+col,139+row*2,1,2,(220,224,202))
    a.line((201,140),(201,150),(220,224,202));a.line((204,138),(204,151),(220,224,202));a.line((207,140),(207,150),(220,224,202))
    for yy in (166,170):a.line((2,yy),(93,yy),(62,69,70))
    a.line((1,185),(94,185),(21,26,28));a.line((98,166),(141,166),(201,210,205))
    for yy in range(164,189,3):a.line((194,yy),(221,yy),(197,136,54))
    # Restrained paint variation. Panel gaps/highlights now follow the geometry;
    # repeating bright borders on every face made the old body read as blocks.
    for p,q in (((131,195),(252,195)),((252,195),(252,252)),
                ((252,252),(131,252)),((131,252),(131,195))):a.line(p,q,(22,29,32))
    a.rect(130,221,3,9,(20,26,29))
    return a


def interior_atlas():
    a=Atlas('santana_interior',256)
    for name,rect,c,style in (
        ('cloth',(0,0,96,96),(108,111,108),'cloth'),('seat_side',(96,0,64,96),(72,77,77),'cloth'),
        ('plastic',(160,0,64,64),(52,59,60),'plain'),('rubber',(224,0,32,64),(23,28,29),'plain'),
        ('gauges',(160,64,96,48),(29,34,34),'plain'),('door',(0,96,96,64),(56,62,62),'plain'),
        ('radio',(96,96,64,64),(26,31,31),'plain'),('console',(160,112,64,48),(31,36,36),'plain'),
        ('chrome',(224,112,32,48),(138,147,145),'plain'),('liner',(0,160,96,64),(54,59,55),'liner'),
        ('carpet',(96,160,64,64),(48,53,52),'carpet'),('vent',(160,160,64,32),(23,29,30),'plain'),
        ('mirror',(224,160,32,32),(98,127,136),'plain'),('steering',(160,192,64,32),(41,47,47),'plain'),
        ('buckle',(224,192,32,32),(129,35,28),'plain'),('seams',(0,224,128,32),(96,101,101),'cloth'),
        ('glovebox',(128,224,96,32),(42,49,50),'plain'),('light',(224,224,32,32),(157,157,128),'plain')):a.patch(name,rect,c,style)
    # Cloth insert stripes and stitches are shaded into the sheet, not tiny boxes.
    for x in (4,7,88,91):a.line((x,3),(x,92),(62,69,68))
    for x in (5,90):
        for y in range(5,92,4):a.pixel(x,y,(153,155,145))
    for cx,r in ((181,17),(216,17),(243,9)):
        a.circle(cx,88,r,(141,151,140));a.circle(cx,88,r-2,(19,24,24),True)
        for i in range(12):
            ang=math.radians(135+i*24)
            p=(round(cx+math.cos(ang)*(r-4)),round(88+math.sin(ang)*(r-4)))
            a.pixel(*p,(173,184,160))
        a.line((cx,88),(cx+6,78),(193,111,67))
    a.rect(196,100,34,5,(89,107,70));a.rect(201,101,21,3,(161,175,124))
    a.rect(2,98,92,60,(49,55,55));a.line((3,100),(92,100),(109,114,109))
    a.rect(8,112,41,19,(73,79,76));a.line((10,112),(45,112),(112,116,109))
    a.rect(10,143,74,10,(28,35,35))
    for x in range(59,92,3):
        for y in range(119,140,3):a.pixel(x,y,(20,28,29))
    a.rect(101,104,54,12,(43,59,43));a.rect(106,107,29,6,(91,122,73))
    for x in range(109,133,5):a.line((x,108),(x,111),(154,172,109))
    a.circle(105,128,5,(88,96,90),True);a.circle(150,128,5,(88,96,90),True)
    a.rect(114,124,27,3,(13,18,19))
    for x in range(110,150,6):a.rect(x,137,4,3,(109,116,106))
    a.line((101,150),(155,150),(127,128,110))
    for cx in (176,197,216):
        a.circle(cx,132,7,(67,74,71),True);a.line((cx,132),(cx+3,127),(175,182,154))
    a.rect(170,149,42,3,(91,103,89))
    for y in (165,171,177,183):
        a.line((164,y),(220,y),(98,106,103));a.line((164,y+2),(220,y+2),(15,21,22))
    a.circle(192,207,10,(121,131,127));a.line((186,202),(192,213),(156,161,149));a.line((192,213),(198,202),(156,161,149))
    a.line((132,226),(219,226),(94,103,99));a.rect(190,231,22,5,(17,25,26))
    for y in range(226,253,3):a.line((228,y),(252,y),(198,196,168))
    return a


def wheel_atlas():
    a=Atlas('santana_wheels',128)
    a.patch('tyre',(0,0,64,64),(29,32,32));a.patch('hub',(64,0,64,64),(134,143,142))
    a.patch('tread',(0,64,64,64),(31,35,34));a.patch('metal',(64,64,64,64),(88,99,104))
    for r in (28,25,21):a.circle(96,32,r,(173,181,173))
    a.circle(96,32,20,(137,146,143),True)
    for i in range(10):
        angle=math.tau*i/10;x=round(96+math.cos(angle)*22);y=round(32+math.sin(angle)*22)
        a.circle(x,y,3,(34,43,43),True);a.pixel(x-1,y-2,(203,205,190))
    a.circle(96,32,7,(78,91,93),True);a.circle(96,32,7,(192,198,184))
    a.line((92,28),(96,36),(177,187,178));a.line((96,36),(100,28),(177,187,178))
    for y in range(2,62,6):
        a.line((3,y),(60,y+3),(44,48,47));a.line((4,67+y),(60,70+y),(13,20,21))
    for r in (27,23,18):a.circle(32,32,r,(49,53,52))
    return a


class Mesh:
    def __init__(self,name,atlas,material):self.name=name;self.atlas=atlas;self.material=material;self.v=[];self.f=[];self.uv=[];self.smooth=[]

    def face(self,points,patch,uv=None,smooth=False):
        start=len(self.v);self.v.extend(points);self.f.append(list(range(start,start+len(points))))
        x,y,w,h=self.atlas.regions[patch];s=self.atlas.size
        if uv is None:
            uv=[(0,1),(1,1),(1,0),(0,0)] if len(points)==4 else [(.5+.48*math.cos(math.tau*i/len(points)),.5+.48*math.sin(math.tau*i/len(points))) for i in range(len(points))]
        self.uv.append([((x+1+u*(w-2))/s,1-(y+1+v*(h-2))/s) for u,v in uv])
        self.smooth.append(smooth)

    def grid(self,rows,patch,reverse=False,smooth=True):
        """Connected curved surface with one continuous atlas patch, not tiled quads."""
        for j in range(len(rows)-1):
            for i in range(len(rows[j])-1):
                p=[rows[j][i],rows[j+1][i],rows[j+1][i+1],rows[j][i+1]]
                uv=[(i/(len(rows[j])-1),j/(len(rows)-1)),(i/(len(rows[j])-1),(j+1)/(len(rows)-1)),
                    ((i+1)/(len(rows[j])-1),(j+1)/(len(rows)-1)),((i+1)/(len(rows[j])-1),j/(len(rows)-1))]
                if reverse:p.reverse();uv.reverse()
                self.face(p,patch,uv,smooth)

    def rounded_box(self,center,size,patch,radius=.025,segments=2,smooth=True):
        """Compact rounded cuboid: flat face centres, curved edges and corners."""
        center=Vector(center);half=[d/2 for d in size];radius=min(radius,min(half)*.85)
        core=[h-radius for h in half]
        def emit(points):
            normal=(points[1]-points[0]).cross(points[2]-points[0])
            if normal.dot(sum(points,Vector())/len(points)-center)<0:points=list(reversed(points))
            self.face(points,patch,smooth=smooth)
        for axis in range(3):
            a,b=[i for i in range(3) if i!=axis]
            for sign in (-1,1):
                points=[]
                for u,v in ((-1,-1),(1,-1),(1,1),(-1,1)):
                    p=Vector();p[axis]=sign*half[axis];p[a]=u*core[a];p[b]=v*core[b]
                    points.append(center+p)
                emit(points)
        for a,b in ((0,1),(0,2),(1,2)):
            axis=3-a-b
            for sa in (-1,1):
                for sb in (-1,1):
                    rows=[]
                    for i in range(segments+1):
                        angle=math.pi/2*i/segments;row=[]
                        for sign in (-1,1):
                            p=Vector();p[a]=sa*(core[a]+radius*math.cos(angle));p[b]=sb*(core[b]+radius*math.sin(angle));p[axis]=sign*core[axis]
                            row.append(center+p)
                        rows.append(row)
                    for i in range(segments):emit([rows[i][0],rows[i][1],rows[i+1][1],rows[i+1][0]])
        for sx in (-1,1):
            for sy in (-1,1):
                for sz in (-1,1):
                    base=Vector((sx*core[0],sy*core[1],sz*core[2]))+center
                    pole=base+Vector((0,sy*radius,0));previous=None
                    for j in range(1,segments+1):
                        phi=math.pi/2*j/segments
                        row=[base+Vector((sx*radius*math.sin(phi)*math.cos(math.pi/2*i/segments),sy*radius*math.cos(phi),
                                          sz*radius*math.sin(phi)*math.sin(math.pi/2*i/segments))) for i in range(segments+1)]
                        for i in range(segments):
                            emit([pole,row[i],row[i+1]] if previous is None else [previous[i],row[i],row[i+1],previous[i+1]])
                        previous=row

    def tube(self,a,b,radius,patch,count=12):
        a,b=Vector(a),Vector(b);direction=(b-a).normalized();right=direction.cross(Vector((0,0,1)))
        if right.length<.01:right=direction.cross(Vector((1,0,0)))
        right.normalize();up=direction.cross(right)
        rings=[[p+radius*(right*math.cos(math.tau*i/count)+up*math.sin(math.tau*i/count)) for i in range(count)] for p in (a,b)]
        for i in range(count):self.face([rings[0][i],rings[0][(i+1)%count],rings[1][(i+1)%count],rings[1][i]],patch,smooth=True)
        self.face(list(reversed(rings[0])),patch);self.face(rings[1],patch)

    def box(self,c,size,patch,bevel=0):
        if bevel:
            x,y,z=c;w,h,d=size
            ring=[(-w/2+bevel,-d/2),(w/2-bevel,-d/2),(w/2,-d/2+bevel),(w/2,d/2-bevel),
                  (w/2-bevel,d/2),(-w/2+bevel,d/2),(-w/2,d/2-bevel),(-w/2,-d/2+bevel)]
            rows=[[(x+xx*scale,y+yy,z+zz*scale) for xx,zz in ring] for yy,scale in ((-h/2,.94),(-h/2+min(bevel,h/3),1),(h/2-min(bevel,h/3),1),(h/2,.94))]
            self.loft(rows,patch,caps=True);return
        x,y,z=c;w,h,d=[s/2 for s in size]
        p=[(x+a*w,y+b*h,z+c*d) for a,b,c in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
        for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([p[i] for i in f],patch)

    def loft(self,rows,patch,caps=False,smooth=False):
        # Rows run along +Y and their X/Z perimeter winds counter-clockwise.
        for a,b in zip(rows,rows[1:]):
            for i in range(len(a)):self.face([a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]],patch,smooth=smooth)
        if caps:self.face(rows[0],patch);self.face(list(reversed(rows[-1])),patch)

    def beam(self,a,b,width,depth,patch):
        a,b=Vector(a),Vector(b);direction=(b-a).normalized();right=direction.cross(Vector((0,0,1)))
        if right.length<.01:right=direction.cross(Vector((1,0,0)))
        right.normalize();across=right.cross(direction).normalized()
        p=[point+right*r*width/2+across*d*depth/2 for point in (a,b) for r,d in ((-1,-1),(1,-1),(1,1),(-1,1))]
        for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([p[i] for i in reversed(f)],patch)

    def panel(self,points,patch,axis=None):
        # Decals stay upright and readable from their outward-facing side.
        if axis is None:
            n=(Vector(points[1])-Vector(points[0])).cross(Vector(points[2])-Vector(points[0]))
            if abs(n.z)>=max(abs(n.x),abs(n.y)):
                coords=[(p[0]*(1 if n.z>0 else -1),-p[1]) for p in points]
            elif abs(n.x)>=abs(n.y):
                coords=[(p[2]*(-1 if n.x>0 else 1),-p[1]) for p in points]
            else:coords=[(p[0],p[2]) for p in points]
        else:coords=[(p[axis[0]],p[axis[1]]) for p in points]
        xs,ys=zip(*coords)
        uv=[((x-min(xs))/(max(xs)-min(xs) or 1),(y-min(ys))/(max(ys)-min(ys) or 1)) for x,y in coords]
        self.face(points,patch,uv)

    def export(self,out,models):
        # Weld position seams so the added curved surfaces have useful normals.
        vertices=[];lookup={};remap=[]
        for p in self.v:
            key=tuple(round(float(v),7) for v in p)
            if key not in lookup:lookup[key]=len(vertices);vertices.append((p[0],-p[2],p[1]))
            remap.append(lookup[key])
        data=bpy.data.meshes.new(self.name);data.from_pydata(vertices,[],[[remap[i] for i in f] for f in self.f]);data.update()
        obj=bpy.data.objects.new(self.name,data);bpy.context.scene.collection.objects.link(obj);data.materials.append(self.material)
        layer=data.uv_layers.new(name='PS1 atlas')
        for polygon,uv,smooth in zip(data.polygons,self.uv,self.smooth):
            polygon.use_smooth=smooth
            for index,value in zip(polygon.loop_indices,uv):layer.data[index].uv=value
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.export_scene.gltf(filepath=str(out/(self.name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
        models[self.name]=dict(vertices=len(data.vertices),triangles=sum(len(f)-2 for f in self.f),atlas=self.atlas.name)
        return obj


def save_car_blend(out,exterior,material,interior=False):
    """A portable, assembled editing scene, separate from the crowded intro kit."""
    scene=bpy.data.scenes.new('Santana / first-person cabin' if interior else 'Santana / assembled vehicle')
    asset=bpy.data.collections.new('CABIN / textured parts' if interior else 'CAR / textured parts');scene.collection.children.link(asset)
    studio=bpy.data.collections.new('STUDIO / cameras and lighting');scene.collection.children.link(studio)
    parts=('sedan_interior','cabin_fittings','steering_interior') if interior else ('sedan_exterior','sedan','headlamps','steering')
    for name in parts:
        obj=bpy.data.objects[name].copy();asset.objects.link(obj)
        if name.startswith('steering'):obj.location=(STEERING[0],-STEERING[2],STEERING[1])
        obj['Game export']=name+'.glb'
    for x in (() if interior else (-WHEEL_X,WHEEL_X)):
        for z in AXLES:
            obj=bpy.data.objects['tyre'].copy();obj.name=f'Wheel {x:+.3f} {z:+.2f}'
            obj.location=(x,-z,WHEEL_Y);asset.objects.link(obj);obj['Game export']='tyre.glb (four instances)'
    glass=bpy.data.materials.new('Preview / lightly tinted glass');glass.use_nodes=True
    shader=glass.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(.17,.23,.25,1)
    shader.inputs['Roughness'].default_value=.3;shader.inputs['Alpha'].default_value=.16
    glass.surface_render_method='DITHERED';glass.use_transparency_overlap=False
    panes=[points for points,_ in window_panes()]
    vertices=[(x,-z,y) for pane in panes for x,y,z in pane]
    data=bpy.data.meshes.new('Six glazing planes');data.from_pydata(vertices,[],[(i,i+1,i+2,i+3) for i in range(0,24,4)])
    obj=bpy.data.objects.new('Glass / game uses animated rain shader',data);asset.objects.link(obj);data.materials.append(glass)
    # A held wiper pose helps inspection. Runtime sweeps remain procedural.
    wipers=Mesh('Preview wipers',exterior,material);angle=math.radians(35)
    for x in WIPER_PIVOTS:
        for a,b,width,depth,part in wiper_segments(x,angle):wipers.beam(a,b,width,depth,'rubber')
    data=bpy.data.meshes.new('Held wiper pose');data.from_pydata([(p[0],-p[2],p[1]) for p in wipers.v],[],wipers.f)
    obj=bpy.data.objects.new('Wipers / preview pose only',data);asset.objects.link(obj);data.materials.append(material)
    layer=data.uv_layers.new(name='PS1 atlas')
    for polygon,uv in zip(data.polygons,wipers.uv):
        for index,value in zip(polygon.loop_indices,uv):layer.data[index].uv=value
    cameras=(
        ('Camera / back seat',(.02,1.235,.53),(.02,1.05,-.88),28),
        ('Camera / front seat backs',(0,1.31,.76),(0,.69,-.28),22),
        ('Camera / rear bench',(0,1.31,.18),(0,.79,.81),20),
        ('Camera / belt guide',(.08,1.20,.48),(.745,1.12,.08),32),
        ('Camera / dashboard',(0,1.22,-.22),(0,.81,-.88),24)) if interior else (
        ('Camera / front quarter',(3.7,1.70,-5.4),(0,.76,-.15),40),
        ('Camera / rear quarter',(-3.7,1.70,5.4),(0,.78,-.12),40),
        ('Camera / roof seams',(2.5,2.6,2.1),(0,1.40,.08),50),
        ('Camera / wheel and mirror',(2.7,1.12,-2.75),(.76,.75,-1.30),55),
        ('Camera / dashboard',(0,1.22,-.22),(0,.81,-.88),24))
    for name,eye,target,lens in cameras:
        data=bpy.data.cameras.new(name);data.lens=lens;data.clip_start=.025
        obj=bpy.data.objects.new(name,data);studio.objects.link(obj);obj.location=(eye[0],-eye[2],eye[1])
        destination=Vector((target[0],-target[2],target[1]))
        obj.rotation_euler=(destination-obj.location).to_track_quat('-Z','Y').to_euler()
        if scene.camera is None:scene.camera=obj
    for name,position,power,size in (('Soft key',(3,4,6),250,5),('Fill',(-4,2,4),200,4),('Roof rim',(1,-5,5),300,3)):
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new(name,data);studio.objects.link(obj);obj.location=position
        obj.rotation_euler=(Vector((0,0,.7))-obj.location).to_track_quat('-Z','Y').to_euler()
    if interior:
        for name,position,power in (('Cabin soft fill',(0,-.28,1.32),5),('Dashboard bounce',(0,.75,1.25),4)):
            data=bpy.data.lights.new(name,'AREA');data.energy=power;data.size=.70
            obj=bpy.data.objects.new(name,data);studio.objects.link(obj);obj.location=position
            obj.rotation_euler=(Vector((0,-.1,.65))-obj.location).to_track_quat('-Z','Y').to_euler()
    world=bpy.data.worlds.new('Studio charcoal');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.08,.10,.12,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55;scene.world=world
    floor=bpy.data.meshes.new('Studio ground');floor.from_pydata([(-200,-200,.012),(200,-200,.012),(200,200,.012),(-200,200,.012)],[],[(0,1,2,3)])
    obj=bpy.data.objects.new('Studio ground / not part of asset',floor);studio.objects.link(obj)
    mat=bpy.data.materials.new('Studio matte');mat.diffuse_color=(.13,.16,.17,1);floor.materials.append(mat)
    scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
    scene['Opaque cabin triangles' if interior else 'Opaque car triangles']=sum(sum(len(p.vertices)-2 for p in obj.data.polygons)
        for obj in asset.objects if obj.type=='MESH' and obj.get('Game export'))
    scene['Glazing triangles']=12;scene['Preview wiper triangles']=sum(len(face)-2 for face in wipers.f)
    scene['Authoring']='build_santana_car.py; regenerate with build_temple_intro_assets.py. Textures packed; game cameras stay in dialogue.json.'
    # Write a normal .blend with its UI/camera, so opening it shows the assembled
    # car immediately. The other scene contains only the five export prototypes.
    previous=bpy.context.window.scene;bpy.context.window.scene=scene;viewports=[]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;region=space.region_3d
                viewports.append((space,space.shading.type,region.view_perspective,space.overlay.show_overlays))
                space.shading.type='MATERIAL';region.view_perspective='CAMERA';space.overlay.show_overlays=False
    for layer in scene.view_layers:layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/('santana_interior.blend' if interior else 'santana.blend')),copy=True)
    bpy.context.window.scene=previous
    for space,shading,perspective,overlays in viewports:
        space.shading.type=shading;space.region_3d.view_perspective=perspective;space.overlay.show_overlays=overlays
    bpy.data.scenes.remove(scene)


def build(out,models):
    out=Path(out);ext=exterior_atlas();inner=interior_atlas();wheels=wheel_atlas()
    em=ext.material(out);im=inner.material(out);wm=wheels.material(out)
    shell=Mesh('sedan_exterior',ext,em);car=Mesh('sedan',inner,im)
    from build_santana_body import build_body,build_lamps
    from build_santana_cabin import build_cabin
    build_body(shell);shell.export(out,models)

    build_cabin(car);car.export(out,models)

    lamps=Mesh('headlamps',ext,em)
    build_lamps(lamps)
    lamps.export(out,models)

    tyre=Mesh('tyre',wheels,wm);count=32
    bands=((- .112,.268),(-.116,.294),(-.105,.322),(-.079,.35),
           (.079,.35),(.105,.322),(.116,.294),(.112,.268))
    for i in range(count):
        a=math.tau*i/count;b=math.tau*(i+1)/count
        for j,((xa,ra),(xb,rb)) in enumerate(zip(bands,bands[1:])):
            tyre.face([(xa,math.sin(a)*ra,math.cos(a)*ra),(xb,math.sin(a)*rb,math.cos(a)*rb),
                       (xb,math.sin(b)*rb,math.cos(b)*rb),(xa,math.sin(b)*ra,math.cos(b)*ra)],
                      'tread' if xa<0<xb else 'tyre',
                      [(i/count,j/7),(i/count,(j+1)/7),((i+1)/count,(j+1)/7),((i+1)/count,j/7)],smooth=True)
        for sign in (-1,1):
            def point(r,x,angle):return (sign*x,math.sin(angle)*r,math.cos(angle)*r)
            def uv(r,angle):return (.5+.49*r/.282*math.cos(angle),.5+.49*r/.282*math.sin(angle))
            p=[point(.267,.120,a),point(.14,.136,a),point(.14,.136,b),point(.267,.120,b)]
            coords=[uv(.267,a),uv(.14,a),uv(.14,b),uv(.267,b)]
            if sign==-1:p.reverse();coords.reverse()
            tyre.face(p,'hub',coords,smooth=True)
            # A rolled steel outer rim reads as a rounded lip at grazing angles.
            p=[point(.267,.120,a),point(.282,.114,a),point(.282,.114,b),point(.267,.120,b)]
            coords=[uv(.267,a),uv(.282,a),uv(.282,b),uv(.267,b)]
            if sign==1:p.reverse();coords.reverse()
            tyre.face(p,'hub',coords,smooth=True)
            p=[(sign*.141,0,0),point(.14,.136,a),point(.14,.136,b)]
            coords=[(.5,.5),uv(.14,a),uv(.14,b)]
            if sign==1:p.reverse();coords.reverse()
            tyre.face(p,'hub',coords,smooth=True)
    tyre.v=[Vector((p[0]*.80,p[1]*TYRE_RADIUS/.35,p[2]*TYRE_RADIUS/.35)) for p in tyre.v]
    tyre.export(out,models)

    wheel=Mesh('steering',inner,im);up=Vector((0,.74,-.673));right=Vector((1,0,0));normal=right.cross(up);rows=[]
    for i in range(28):
        direction=right*math.cos(math.tau*i/28)+up*math.sin(math.tau*i/28)
        rows.append([direction*(.205+.018*math.cos(math.tau*j/4))+normal*.018*math.sin(math.tau*j/4) for j in range(4)])
    for i in range(28):
        for j in range(4):wheel.face([rows[i][j],rows[(i+1)%28][j],rows[(i+1)%28][(j+1)%4],rows[i][(j+1)%4]],'rubber')
    for sign in (-1,1):
        wheel.beam((sign*.04,.02,-.02),(sign*.19,.03,-.027),.044,.035,'plastic')
        wheel.beam((sign*.04,-.01,.01),tuple(up*(-.16)+right*sign*.10),.038,.032,'plastic')
    start=len(wheel.v);wheel.rounded_box((0,0,0),(.145,.088,.08),'plastic',.024,1)
    wheel.v[start:]=[right*p[0]+up*p[1]+normal*p[2] for p in wheel.v[start:]]
    wheel.panel([right*x+up*y+normal*.047 for x,y in ((-.057,-.033),(.057,-.033),(.057,.033),(-.057,.033))],'steering')
    wheel.v=[p*.88 for p in wheel.v]
    wheel.export(out,models)
    total=sum(models[n]['triangles']*copies for n,copies in (('sedan_exterior',1),('sedan',1),('headlamps',1),('tyre',4),('steering',1)))
    save_car_blend(out,ext,em)

    # Close-view cabin has its own budget; exterior shots retain the accepted kit.
    from build_santana_fittings import fittings_atlas,build_fittings,build_steering
    close=interior_atlas();close.name='santana_cabin'
    close.patch('cloth',(0,0,96,96),(122,126,122),'cloth')
    for x in (3,92):
        close.line((x,2),(x,93),(82,89,86))
        for y in range(4,93,4):close.pixel(x,y,(163,165,154))
    cm=close.material(out);fittings=fittings_atlas(Atlas);fm=fittings.material(out)
    cabin=Mesh('sedan_interior',close,cm);build_cabin(cabin,detailed=True);cabin.export(out,models)
    detail=Mesh('cabin_fittings',fittings,fm);features=build_fittings(detail);detail.export(out,models)
    steering=Mesh('steering_interior',close,cm);build_steering(steering);steering.export(out,models)
    interior_models=('sedan_interior','cabin_fittings','steering_interior')
    interior_total=sum(models[name]['triangles'] for name in interior_models)
    save_car_blend(out,ext,em,interior=True)
    return dict(triangles=total,budget=[18000,22000],glass_triangles=12,wheel_instances=4,
                editable_source='santana.blend',
                interior=dict(triangles=interior_total,budget=[12000,15000],models=list(interior_models),
                              editable_source='santana_interior.blend',features=features,
                              atlases={'santana_cabin':[256,256],'santana_cabin_details':[256,256]}),
                atlases={'santana_exterior':[256,256],'santana_interior':[256,256],'santana_wheels':[128,128]},
                references=['artdev/car_reference.png','artdev/car_reference_2.png','artdev/Classic Santana Vehicle Reference Sheet.png'],
                description='Charcoal civilian Santana; shaped body, cloth seats, manual cranks, textured dashboard and steel wheel covers')
