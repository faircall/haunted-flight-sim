"""Blender-authored open, double-eaved lake pavilion and narrow stone causeway."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
import math
import random
import json
from mathutils import Vector
from temple_interior_mesh import Mesh
from build_bamboo_grove import tube,leaf
from prepare_huxin_moon import TILES
from g_huxin_moon import PATH,DECK,PLATFORM_RADIUS,COLUMNS,LIGHTS,BENCHES,shore_radius,shore_height,inside_platform,path_distance,path_halfwidth,walk_height

OUT=ROOT/'art'/'temple'/'huxin_moon'

def elevation(y):
    """Keep the authored structure together when changing deck freeboard."""
    return y+DECK-.65

def material(name,path):
    m=bpy.data.materials.new(name);m.use_nodes=True;t=m.node_tree.nodes.new('ShaderNodeTexImage')
    t.image=bpy.data.images.load(str(OUT/path));t.image.pack();m.node_tree.links.new(t.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.96;return m

def face_up(mesh,points,tile):
    points=list(points);normal=(Vector(points[1])-Vector(points[0])).cross(Vector(points[2])-Vector(points[0]))
    if normal.y<0:points.reverse()
    mesh.face(points,tile)

def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mat=material('Old timber, unglazed tiles and damp limestone','materials.png');ink=material('Lake pavilion plaques','inscriptions.png')
    names=('lake_bank','lake_mountains','causeway','pavilion_base','pavilion_posts','pavilion_brackets','pavilion_roofs','pavilion_ceiling','pavilion_details','lake_plants','lake_lamps','lake_surface')
    meshes={n:Mesh(n,mat,TILES) for n in names};meshes['pavilion_inscriptions']=Mesh('pavilion_inscriptions',ink)
    bank,mountains,path,base,posts,brackets,roofs,ceiling,details,plants,lamps,water=[meshes[n] for n in names];rr=random.Random(49371)
    # Continuous shoreline stays well outside the later surrounding-structure envelope.
    rings=(-5,-3,-1,0,.75,1.5,2.5,4,6,8)+tuple(range(10,33))+(36,40,48,72,110)
    entry=math.atan2(77,-12)
    angles=sorted(set([i*math.tau/180 for i in range(181)]+[entry-.34+i*.004 for i in range(171)]))
    for a,b in zip(angles,angles[1:]):
        for lo,hi in zip(rings,rings[1:]):
            pts=[]
            for angle,d in ((a,lo),(a,hi),(b,hi),(b,lo)):
                r=shore_radius(angle)+d;x,z=math.cos(angle)*r,math.sin(angle)*r;pts.append((x,shore_height(x,z),z))
            face_up(bank,pts,'earth' if hi>5 else 'moss')
    # Layered subdued mountain silhouettes, all beyond the open-water assembly space.
    for layer in range(3):
        radius=230+layer*65;segments=120
        for i in range(segments):
            a=i*math.tau/segments;b=(i+1)*math.tau/segments
            def peak(t):return 19+layer*9+17*math.sin(t*3+.8+layer)**2+13*math.sin(t*7-layer*.7)**4
            pts=[(math.cos(a)*radius,-3,math.sin(a)*radius),(math.cos(b)*radius,-3,math.sin(b)*radius),
                 (math.cos(b)*radius,peak(b),math.sin(b)*radius),(math.cos(a)*radius,peak(a),math.sin(a)*radius)]
            mountains.face(pts,'cap');mountains.face(pts[::-1],'cap')
    # A continuous foundation under lightly chipped, individually readable slabs.
    # Shared cross-sections keep bends watertight across the full walking width.
    edges=[]
    for i,(x,z) in enumerate(PATH):
        before=PATH[max(0,i-1)];after=PATH[min(len(PATH)-1,i+1)]
        dx,dz=after[0]-before[0],after[1]-before[1];length=math.hypot(dx,dz);nx,nz=dz/length,-dx/length
        width=path_halfwidth(z)+.065+.025*math.sin(i*1.9)
        edges.append(tuple((x+side*nx*width,walk_height(x+side*nx*width,z+side*nz*width),z+side*nz*width) for side in (-1,1)))
    for i,(a,b) in enumerate(zip(PATH,PATH[1:])):
        dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);nx,nz=dz/length,-dx/length
        p=[edges[i][0],edges[i+1][0],edges[i+1][1],edges[i][1]]
        if b[1]>6.1:
            if b[1]<76:
                face_up(path,p,'stone')
                for j in (0,2):
                    q=p[(j+1)%4];v=p[j];path.face((v,(v[0],DECK-1.30,v[2]),(q[0],DECK-1.30,q[2]),q),'wetstone')
            # Low moss-darkened stone margins, without a visual guardrail.
            if i%3==0 and b[1]<76:
                for side in (-1,1):
                    x=(a[0]+b[0])/2+nx*1.045*side;z=(a[1]+b[1])/2+nz*1.045*side
                    details.ellipsoid((x,DECK+.022,z),(.10,.055,.18),'moss',6,3)
    # Worn, staggered slabs settle into the earth on shore. Their edges vary
    # independently; the soil beneath supports the shallow seams and missing chips.
    paving=random.Random(8107)
    for row in range(24):
        z=75.85+row*.70;center=-12-.08*max(0,z-76);width=path_halfwidth(z)
        for col in (-1,1):
            x=center+col*width*.48;half=width*.48+paving.uniform(-.06,.035)
            zz=z+paving.uniform(-.065,.065)+col*.06*(row%3-1);dz=.33+paving.uniform(-.035,.025)
            outline=[(x-half,zz-dz+.035),(x+half-.08,zz-dz),(x+half,zz-dz+.08),
                     (x+half-.025,zz+dz-.055),(x+half-.10,zz+dz),(x-half+.04,zz+dz-.025)]
            top=[(xx,walk_height(xx,zv)-paving.uniform(.002,.009),zv) for xx,zv in outline]
            face_up(path,top,'stone')
            for a,b in zip(top,top[1:]+top[:1]):
                path.face((a,(a[0],a[1]-.055,a[2]),(b[0],b[1]-.055,b[2]),b),'wetstone')
            if row>4 and row%3==0:
                side=col;xx=center+side*(width+.02);yy=shore_height(xx,zz)
                details.ellipsoid((xx,yy+.018,zz),(.16,.035,.23),'moss',7,4)
    base.lathe((0,DECK-1.30,0),[(0,7.20),(.55,7.20),(.62,7.29),(1.22,7.29),(1.3,7.2)],'wetstone',6)
    # A complete floor, including the reserved central area, with shallow paving seams.
    vertices=[(math.cos(i*math.tau/6)*PLATFORM_RADIUS,DECK,math.sin(i*math.tau/6)*PLATFORM_RADIUS) for i in range(6)]
    base.face(vertices[::-1],'stone')
    for x in range(-7,8):
        for z in range(-7,8):
            if all(inside_platform(xx,zz,.04) for xx in (x-.47,x+.47) for zz in (z-.47,z+.47)):
                base.box((x,DECK+.001,z),(.976,.008,.977),'stone')
    # The approach threshold is left completely open between the front columns.
    for x,z,r in COLUMNS:
        posts.lathe((x,DECK,z),[(0,.31),(.12,.33),(.20,.28),(.33,.22)],'stone',12)
        posts.lathe((x,DECK+.24,z),[(0,.205),(.24,.195),(3.48,.165),(3.70,.225)],'wood',12)
        for j in range(4):
            y=elevation(4.42)+j*.15;width=.42+j*.22
            brackets.box((x,y,z),(width,.13,.24),'paint' if j%2 else 'wood')
            brackets.box((x,y+.035,z),(.24,.11,width),'wood')
    for i in range(6):
        a=i*math.tau/6;b=(i+1)*math.tau/6
        p=(math.cos(a)*4.65,elevation(4.72),math.sin(a)*4.65);q=(math.cos(b)*4.65,elevation(4.72),math.sin(b)*4.65)
        brackets.beam(p,q,.27,.32,'paint')
        # Open curved struts supply detail overhead without walls between the posts.
        for t in (.12,.88):
            x=p[0]*(1-t)+q[0]*t;z=p[2]*(1-t)+q[2]*t
            near=p if t<.5 else q;brackets.beam((near[0],elevation(4.02),near[2]),(x,elevation(4.70),z),.13,.17,'wood')
    def roof_point(sector,t,s,radius,eave,rise):
        a=sector*math.tau/6;b=(sector+1)*math.tau/6
        x=math.cos(a)*(1-s)+math.cos(b)*s;z=math.sin(a)*(1-s)+math.sin(b)*s
        y=elevation(eave)+rise*(1-t)**2+.27*t**8+.52*abs(s*2-1)**6*t**5
        return (x*radius*t,y,z*radius*t)
    for radius,eave,rise,columns,rows in ((6.55,4.86,2.20,18,13),(4.28,7.30,2.07,14,11)):
        for sector in range(6):
            for col in range(columns):
                s=col/columns;ss=(col+1)/columns
                for row in range(rows):
                    t=max(.012,row/rows);tt=(row+1)/rows
                    p=[roof_point(sector,v,u,radius,eave,rise) for v,u in ((t,s),(tt,s),(tt,ss),(t,ss))]
                    face_up(roofs,p,'roof')
                    # One downward-facing soffit. Coincident reversed faces get
                    # merged by the exporter and can leave the underside culled.
                    ceiling.face([(x,y-.13,z) for x,y,z in p],'wood')
                    # Raised half-round tile channels follow the concave slope.
                    if row>1:
                        a=roof_point(sector,t,s,radius,eave,rise);b=roof_point(sector,tt,s,radius,eave,rise)
                        tube(roofs,(a[0],a[1]+.028,a[2]),(b[0],b[1]+.028,b[2]),.034,'roof',5,end=.033)
                a=roof_point(sector,1,s,radius,eave,rise);b=roof_point(sector,1,ss,radius,eave,rise)
                tube(roofs,a,b,.068,'roof',8,end=.068)
                # Visible timber rafters are radial and tucked under the tiled eave.
                if col%2==0:
                    for j in range(7):
                        a=roof_point(sector,.36+j*.65/7,s,radius,eave,rise);b=roof_point(sector,.36+(j+1)*.65/7,s,radius,eave,rise)
                        ceiling.beam((a[0],a[1]-.22,a[2]),(b[0],b[1]-.22,b[2]),.085,.11,'wood')
            for j in range(15):
                a=roof_point(sector,j/15,0,radius,eave,rise);b=roof_point(sector,(j+1)/15,0,radius,eave,rise)
                tube(roofs,(a[0],a[1]+.08,a[2]),(b[0],b[1]+.08,b[2]),.085,'roof',8,end=.08)
    # Small open upper lantern storey; no opaque box beneath the second roof.
    for i in range(6):
        a=i*math.tau/6;b=(i+1)*math.tau/6;p=(math.cos(a)*2.48,elevation(6.05),math.sin(a)*2.48);q=(math.cos(b)*2.48,elevation(6.05),math.sin(b)*2.48)
        posts.lathe(p,[(0,.10),(1.34,.10),(1.49,.16)],'wood',10)
        for y in (6.26,7.47):brackets.beam((p[0],elevation(y),p[2]),(q[0],elevation(y),q[2]),.13,.18,'paint')
        for j in range(1,8):
            t=j/8;x=p[0]*(1-t)+q[0]*t;z=p[2]*(1-t)+q[2]*t
            brackets.box((x,elevation(6.50),z),(.035,.46,.035),'wood')
    roofs.lathe((0,elevation(9.38),0),[(0,.29),(.12,.34),(.24,.28),(.4,.16),(.56,.23),(.76,.13),(.90,.11),(1.12,.025)],'bronze',16)
    # A decorated hexagonal ceiling canopy remains visible from close cameras.
    ceiling.face([(math.cos(i*math.tau/6)*2.62,elevation(5.52),math.sin(i*math.tau/6)*2.62) for i in range(6)],'paint')
    for i in range(6):
        a=i*math.tau/6;ceiling.beam((0,elevation(5.50),0),(math.cos(a)*4.8,elevation(5.13),math.sin(a)*4.8),.12,.17,'wood')
    # Only peripheral benches; the central 4.5m diameter remains entirely clear.
    for x,z,rx,rz in BENCHES:
        details.box((x,elevation(1.13),z),(rx*2,.12,rz*2),'wood')
        for dz in (-.82,.82):details.box((x,elevation(.85),z+dz),(.32,.42,.23),'stone')
    inscription=meshes['pavilion_inscriptions']
    details.box((0,elevation(4.67),4.21),(2.28,.64,.06),'wood')
    inscription.face(((-1.08,elevation(4.40),4.248),(1.08,elevation(4.40),4.248),(1.08,elevation(4.94),4.248),(-1.08,elevation(4.94),4.248)),0,
        uv=((.002,.502),(.498,.502),(.498,.998),(.002,.998)))
    for x,y,z in LIGHTS:
        if z<10:
            tube(details,(x,y+.29,z),(x,elevation(4.90),z),.018,'bronze',6,end=.018)
            lamps.lathe((x,y-.27,z),[(0,.095),(.07,.20),(.32,.24),(.48,.16),(.53,.07)],'paper',12)
            for j in range(6):
                a=j*math.tau/6;tube(details,(x+.13*math.cos(a),y-.25,z+.13*math.sin(a)),(x+.18*math.cos(a),y+.17,z+.18*math.sin(a)),.012,'wood',4,end=.012)
        else:
            bottom=shore_height(x,z)-.035
            details.lathe((x,bottom,z),[(0,.24),(.08,.26),(.16,.18),(.28,.12),(y-bottom-.43,.115),(y-bottom-.32,.22)],'stone',10)
            lamps.lathe((x,y-.3,z),[(0,.18),(.4,.20)],'paper',10)
            for side in range(4):
                angle=(side+.5)*math.tau/4
                tube(details,(x+.17*math.cos(angle),y-.30,z+.17*math.sin(angle)),(x+.19*math.cos(angle),y+.10,z+.19*math.sin(angle)),.018,'wood',5,end=.018)
            details.lathe((x,y+.1,z),[(0,.29),(.08,.32),(.26,.01)],'roof',8)
    # Sparse reeds, low shrubs and stones are confined to the shore, not the lake centre.
    for i in range(350):
        a=rr.random()*math.tau;r=shore_radius(a)+rr.uniform(.4,8);x,z=math.cos(a)*r,math.sin(a)*r;y=shore_height(x,z)
        if z>70 and path_distance(x,z)<2.1:continue
        for j in range(4):
            angle=rr.random()*math.tau;height=rr.uniform(.35,1.25)
            leaf(plants,(x,y,z),angle,.25+height*.32,.023,'leaf',height)
            tube(plants,(x,y,z),(x+.12*math.cos(angle),y+height,z+.12*math.sin(angle)),.012,'leaflight',4,end=.004)
        if i%4==0:details.ellipsoid((x,y-.12,z),(.45,.25,.35),'wetstone',8,5)
    # Local sedges and ferny understory soften the causeway abutment and follow
    # the actual bank height, leaving the central walk and both lamps clear.
    for i in range(140):
        z=rr.uniform(73,96);center=-12-.08*max(0,z-76);x=center+rr.choice((-1,1))*rr.uniform(1.65,7)
        y=shore_height(x,z)
        if y<.02 or any(math.hypot(x-lx,z-lz)<.65 for lx,ly,lz in LIGHTS):continue
        for j in range(rr.randint(5,9)):
            angle=rr.random()*math.tau;length=rr.uniform(.22,.65)
            leaf(plants,(x,y+.025,z),angle,length,.035,'leaf',rr.uniform(.15,.55))
            tube(plants,(x,y,z),(x+.15*math.cos(angle),y+rr.uniform(.25,.65),z+.15*math.sin(angle)),.011,'leaflight',4,end=.003)
    water.face(((-700,0,-700),(-700,0,700),(700,0,700),(700,0,-700)),'water')
    counts={}
    for name,m in meshes.items():counts[name]=m.export(OUT);print(name,counts[name],flush=True)
    (OUT/'manifest.json').write_text(json.dumps(dict(separate_scene=True,models=counts,total_triangles=sum(x['triangles'] for x in counts.values()),
        enemy_count=0,water_height=0,assembly_space='assembly_space.json',open_sided=True),indent=2))
    bpy.ops.object.camera_add(location=(18,-25,9));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,4))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=42;bpy.context.scene.camera=cam
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'huxin_pavilion.blend'),compress=True)

if __name__=='__main__':build()
