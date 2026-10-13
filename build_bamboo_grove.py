"""Blender-authored bamboo grove and secluded Chan room; reproducible GLB exports."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import math
import random
import json
from mathutils import Vector
from temple_interior_mesh import Mesh
from prepare_bamboo_textures import NAMES
from g_bamboo_grove import PATH,SHOTS,LIGHTS,COLUMNS,bamboo_layout,ground_height,path_distance

OUT=ROOT/'art'/'temple'/'bamboo'

def material(name,path):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(OUT/path));tex.image.pack()
    bsdf=mat.node_tree.nodes.get('Principled BSDF');mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);bsdf.inputs['Roughness'].default_value=.96
    return mat

def tube(m,a,b,r,tile='wood',sides=6,end=None):
    a,b=Vector(a),Vector(b);axis=(b-a).normalized();u=axis.cross(Vector((0,1,0)))
    if u.length<.01:u=axis.cross(Vector((1,0,0)))
    u.normalize();v=axis.cross(u);r2=end if end is not None else r*.72
    for i in range(sides):
        t=i*math.tau/sides;tt=(i+1)*math.tau/sides
        m.face((a+(u*math.cos(t)+v*math.sin(t))*r,a+(u*math.cos(tt)+v*math.sin(tt))*r,
                b+(u*math.cos(tt)+v*math.sin(tt))*r2,b+(u*math.cos(t)+v*math.sin(t))*r2),tile,smooth=True)

def leaf(m,p,angle,length,width,tile='leaf',dip=-.10):
    x,y,z=p;dx,dz=math.cos(angle),math.sin(angle);cx=x+dx*length*.44;cz=z+dz*length*.44
    m.face(((x,y,z),(cx-dz*width,y+.035,cz+dx*width),(x+dx*length,y+dip,z+dz*length),
            (cx+dz*width,y-.025,cz-dx*width)),tile)

def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mat=material('Moss, bamboo, limewash and weathered timber','materials.png');ink=material('Poem and quiet ink painting','scrolls.png')
    names=('grove_ground','grove_path','chan_shell','chan_timber','chan_roof','chan_props','grove_flowers','grove_understory','grove_lamps')
    meshes={n:Mesh(n,mat,NAMES) for n in names};scroll=Mesh('chan_scrolls',ink);meshes[scroll.name]=scroll
    ground,path,shell,timber,roof,props,flowers,under,lamps=[meshes[n] for n in names]
    rng=random.Random(7213)
    # A gently folded, continuous forest floor. The walk and mesh share heights.
    for x in range(-45,45,2):
        for z in range(-40,60,2):
            p=[(xx,ground_height(xx,zz),zz) for xx,zz in ((x,z),(x,z+2),(x+2,z+2),(x+2,z))]
            ground.face(p,'earth')
    # Narrow, slightly irregular slabs follow the bend; no cliff-like path sides.
    station=0.;last=PATH[0]
    for i,(a,b) in enumerate(zip(PATH,PATH[1:])):
        station+=math.dist(a,b)
        if station<.64:continue
        station=0.;dx,dz=b[0]-last[0],b[1]-last[1];length=math.hypot(dx,dz)
        if b[1]<-.25:break
        nx,nz=dz/max(.01,length),-dx/max(.01,length)
        for side in (-1,1):
            center=side*.39;corners=[]
            for t,w in ((0,center-.37),(1,center-.37),(1,center+.37),(0,center+.37)):
                xx=last[0]*(1-t)+b[0]*t+nx*w;zz=last[1]*(1-t)+b[1]*t+nz*w
                corners.append((xx,ground_height(xx,zz)+.041,zz))
            path.face(corners,'stone');path.face(corners[::-1],'stone')
        last=b
    # Irregular paving at the room is surrounded by moss and low flowering growth.
    for z in range(-15,4):
        for x in range(-7,7):
            if (-5.4<x<5.4 and z<-2) or (x*x/52+(z+5)**2/92)>1:continue
            if rng.random()<.11:continue
            xx=x+.5+rng.uniform(-.08,.08);zz=z+.5+rng.uniform(-.06,.06)
            path.box((xx,ground_height(xx,zz)+.014,zz),(.91,.048,.90),'stone')
    shell.box((0,.30,-8.1),(10.4,.65,11),'cap')
    for x in range(-5,5):
        for z in range(-13,-2):shell.box((x+.5,.602,z+.5),(.985,.05,.985),'stone' if z>=-5 else 'wood')
    shell.box((0,.6245,-9),(9.99,.003,7.99),'wood')
    for i in range(4):shell.box((0,.075+i*.08,-.3-(i+.5)*.59),(3.6,.15+i*.16,.59),'stone')
    for x in (-4.6,4.6):
        shell.box((x,2.32,-9),(.26,3.4,8.2),'plaster')
        shell.box((x,.87,-9),(.34,.50,8.4),'cap')
    # Round rear lattice window: a genuine opening through the plaster wall.
    for x in (-3.25,3.25):shell.box((x,2.3,-13),(2.7,3.4,.28),'plaster')
    shell.box((0,.98,-13),(3.8,.7,.28),'plaster');shell.box((0,3.76,-13),(3.8,.48,.28),'plaster')
    for j in range(32):
        a=j*math.tau/32;b=(j+1)*math.tau/32;radius=.90;cy=2.45
        def edge(t):
            c,s=math.cos(t),math.sin(t);f=min(1.9/max(.0001,abs(c)),1.12/max(.0001,abs(s)))
            return (c*f,cy+s*f,-12.84)
        p=((math.cos(a)*radius,cy+math.sin(a)*radius,-12.84),(math.cos(b)*radius,cy+math.sin(b)*radius,-12.84),edge(b),edge(a))
        # One planar mapping across the entire wall avoids radial texture seams.
        uv=[(.75+.0645+(xx+1.9)/3.8*.121,.5+.0645+(yy-1.33)/2.24*.121) for xx,yy,zz in p]
        shell.face(p[::-1],'plaster',uv=uv[::-1])
        shell.face([(xx,yy,zz-.30) for xx,yy,zz in p],'plaster',uv=uv)
        # A solid circular reveal bridges the inner and outer wall surfaces.
        ia,ib=p[0],p[1]
        shell.face((ia,(ia[0],ia[1],ia[2]-.30),(ib[0],ib[1],ib[2]-.30),ib),'wood')
        tube(timber,(math.cos(a)*.95,cy+math.sin(a)*.95,-12.80),(math.cos(b)*.95,cy+math.sin(b)*.95,-12.80),.055,'wood',6,end=.055)
    for x in (-.72,-.48,-.24,0,.24,.48,.72):
        height=math.sqrt(.89**2-x*x);timber.box((x,2.45,-12.81),(.028,height*2,.045),'wood')
    for y in (-.6,-.3,0,.3,.6):
        w=math.sqrt(.89**2-y*y);timber.box((0,2.45+y,-12.81),(w*2,.028,.045),'wood')
    # Front panels: open entrance, carved wooden lattice, aged lower aprons.
    for side in (-1,1):
        for x in (side*2.15,side*3.7):
            shell.box((x,1.15,-5),(1.45,1.05,.18),'wood')
            for xx in (x-.73,x+.73):timber.box((xx,2.3,-5),(.09,3.4,.25),'wood')
            for y in (1.7,3.35):timber.box((x,y,-5),(1.42,.08,.14),'wood')
            for j in range(7):timber.box((x-.63+j*.21,2.5,-5),(.027,1.55,.065),'wood')
            for y in (1.95,2.3,2.65,3.):timber.box((x,y,-5),(1.42,.027,.065),'wood')
            for j in range(3):
                xx=x-.47+j*.47
                for yy in (2.13,2.83):
                    for a,b in (((xx-.2,yy),(xx,yy+.27)),((xx,yy+.27),(xx+.2,yy)),((xx+.2,yy),(xx,yy-.27)),((xx,yy-.27),(xx-.2,yy))):
                        timber.beam((a[0],a[1],-4.96),(b[0],b[1],-4.96),.025,.027,'wood')
        # Open door leaves lie against the interior rather than blocking entry.
        shell.box((side*1.45,1.95,-5.6),(.12,2.65,1.1),'wood')
        for zz in (-5.13,-6.07):timber.box((side*1.52,1.95,zz),(.04,2.45,.055),'bronze')
    for x,z,r in COLUMNS:
        timber.lathe((x,.63,z),[(0,.22),(.14,.23),(.22,.15),(3.05,.13),(3.16,.21)],'wood',10)
        timber.lathe((x,.60,z),[(0,.24),(.15,.24),(.26,.19)],'cap',10)
        for s in (-1,1):timber.beam((x,3.25,z),(x+s*.58,3.90,z),.09,.13,'wood')
        for j in range(3):timber.box((x,3.75+j*.13,z),(.46+j*.23,.11,.22),'wood')
    for z in (-3,-5,-9,-13):timber.box((0,4.0,z),(10.2,.22,.26),'wood')
    for x in (-4.5,-1.5,1.5,4.5):
        timber.box((x,4.08,-8),(.22,.24,10.3),'wood')
    # Tile channels, ridge caps, curled eaves, and complete timber roof backs.
    def roofp(x,t,side):
        return (x,4.12+1.74*(1-t)**2+.27*t**8+.16*(abs(x)/5.7)**8*t**5,-8.5+side*6.5*t)
    for x in (-4.5,-1.5,1.5,4.5):
        for side in (-1,1):
            for j in range(8):
                a=roofp(x,j/8,side);b=roofp(x,(j+1)/8,side)
                timber.beam((a[0],a[1]-.24,a[2]),(b[0],b[1]-.24,b[2]),.17,.20,'wood')
    for side in (-1,1):
        for i in range(42):
            x=-5.75+i*11.5/42;xx=x+11.5/42
            for j in range(13):
                t=j/13;tt=(j+1)/13;p=[roofp(x,t,side),roofp(xx,t,side),roofp(xx,tt,side),roofp(x,tt,side)]
                roof.face(p if side<0 else p[::-1],'roof')
                underside=[(xx,yy-.09,zz) for xx,yy,zz in p]
                roof.face(underside[::-1] if side<0 else underside,'wood')
                # Raised curved channel ridges remain readable at close range.
                pa=roofp(x,t,side);pb=roofp(x,tt,side)
                tube(roof,(pa[0],pa[1]+.045,pa[2]),(pb[0],pb[1]+.045,pb[2]),.034,'roof',5,end=.034)
        for i in range(40):
            x=-5.75+i*11.5/40;pa=roofp(x,1,side);pb=roofp(x+11.5/40,1,side)
            tube(roof,pa,pb,.078,'roof',8,end=.078)
    roof.box((0,5.92,-8.5),(11.65,.19,.26),'roof')
    for side in (-1,1):
        for j in range(5):
            a=side*(5.2+j*.15);b=side*(5.35+j*.15)
            roof.beam((a,5.92+(j/5)**2*.43,-8.5),(b,5.92+((j+1)/5)**2*.43,-8.5),.13,.2,'roof')
        for j in range(16):
            z0=-13+j*.5;z1=z0+.5
            y0=roofp(side*4.73,abs(z0+8.5)/6.5,1)[1]-.09
            y1=roofp(side*4.73,abs(z1+8.5)/6.5,1)[1]-.09
            panel=[(side*4.73,4.02,z0),(side*4.73,4.02,z1),(side*4.73,y1,z1),(side*4.73,y0,z0)]
            if side>0:panel.reverse()
            shell.face(panel,'plaster')
            shell.face([(xx-side*.26,yy,zz) for xx,yy,zz in panel[::-1]],'plaster')
    # Exact poem on the entrance pillars and a restrained ink hanging inside.
    scroll.face(((-3.75,1.4,-12.80),(-1.8,1.4,-12.80),(-1.8,3.35,-12.80),(-3.75,3.35,-12.80)),0)
    for y in (1.37,3.38):props.box((-2.775,y,-12.73),(2.04,.055,.07),'wood')
    for side,tile in ((1,1),(-1,2)):
        x=side*1.5;scroll.face(((x-.175,1.05,-2.83),(x+.175,1.05,-2.83),(x+.175,3.29,-2.83),(x-.175,3.29,-2.83)),tile)
    scroll.face(((-1.28,3.42,-2.81),(1.28,3.42,-2.81),(1.28,4.02,-2.81),(-1.28,4.02,-2.81)),3)
    # Simple meditation furnishings; emptiness is the subject of this room.
    props.box((0,.67,-9.1),(1.8,.055,2.2),'cloth')
    props.lathe((0,.71,-9.25),[(0,.55),(.04,.59),(.17,.55),(.20,.43),(.21,.005)],'cloth',24)
    props.box((2.7,1.23,-11.4),(2.2,.15,.94),'wood')
    for x in (1.8,3.6):
        for z in (-11.75,-11.05):props.box((x,.9,z),(.09,.60,.09),'wood')
    for x,z in ((2.2,-11.35),(2.8,-11.6),(3.15,-11.24)):
        props.lathe((x,1.33,z),[(0,.075),(.03,.09),(.10,.11),(.13,.1),(.13,.08),(.055,.05)],'cap',12)
    props.lathe((2.65,1.3,-11.25),[(0,.16),(.08,.20),(.22,.16),(.26,.07),(.29,.025)],'bronze',16)
    tube(props,(2.75,1.41,-11.25),(2.99,1.56,-11.25),.055,'bronze',8,end=.029)
    props.box((-3.84,1.58,-9.5),(.42,1.9,2.5),'wood')
    for z in (-10.7,-9.5,-8.3):props.box((-3.6,1.57,z),(.48,1.8,.075),'wood')
    for y in (.82,1.33,1.92,2.46):props.box((-3.56,y,-9.5),(.5,.065,2.48),'wood')
    for j in range(16):
        z=-10.48+(j%8)*.265;y=.93+(j//8)*.58
        props.box((-3.54,y,z),(.30,.18,.21),'paper' if j%3 else 'cloth')
    props.lathe((.25,.63,-11.4),[(0,.28),(.08,.3),(.15,.16),(.65,.08),(.77,.3),(.85,.32),(.87,.26)],'bronze',16)
    for j in (-1,0,1):tube(props,(.25+j*.06,1.45,-11.4),(.25+j*.06,1.87,-11.4),.008,'wood',5,end=.006)
    # Mossy rain basin with real hollow lip, water plane added by the renderer.
    props.lathe((-6.5,.03,-1),[(0,.56),(.12,.70),(.62,.76),(.69,.72),(.69,.53),(.20,.46),(.20,.001)],'stone',24)
    for x,y,z in LIGHTS:
        if z<0:
            tube(props,(x,y+.42,z),(x,4.05,z),.025,'bronze',6,end=.025)
            lamps.lathe((x,y-.3,z),[(0,.09),(.07,.22),(.28,.28),(.48,.22),(.53,.08)],'paper',16)
            for j in range(8):
                a=j*math.tau/8;tube(props,(x+.11*math.cos(a),y-.29,z+.11*math.sin(a)),(x+.23*math.cos(a),y+.12,z+.23*math.sin(a)),.009,'wood',4,end=.009)
        else:
            h=ground_height(x,z);props.lathe((x,h,z),[(0,.25),(.1,.29),(.2,.17),(.60,.15),(.65,.30)],'stone',8)
            lamps.box((x,h+.80,z),(.27,.28,.27),'paper')
            for dx in (-.2,.2):
                for dz in (-.2,.2):props.box((x+dx,h+.80,z+dz),(.045,.37,.045),'stone')
            props.lathe((x,h+.98,z),[(0,.38),(.10,.40),(.23,.10),(.25,.005)],'roof',8)
    # Two gnarled camellias bury the eaves in white flowers and glossy leaf sprays.
    for cx,cz,seed in ((-7.4,-4,82),(6.8,-4.5,91)):
        rr=random.Random(seed);base=ground_height(cx,cz);tube(flowers,(cx,base,cz),(cx+.2,base+2.5,cz-.15),.18,'wood',9,end=.065)
        for branch in range(11):
            a=rr.random()*math.tau;y=base+1.6+rr.random()*1.9;length=rr.uniform(1.1,2.2)
            end=(cx+math.cos(a)*length,y,cz+math.sin(a)*length)
            tube(flowers,(cx+.1,base+1.3,cz),end,.052,'wood',6,end=.018)
            for k in range(9):
                p=(end[0]+rr.uniform(-.75,.75),end[1]+rr.uniform(-.38,.38),end[2]+rr.uniform(-.65,.65))
                for j in range(4):
                    aa=a+(j-1.5)*.75;leaf(flowers,(p[0]+rr.uniform(-.10,.10),p[1],p[2]+rr.uniform(-.10,.10)),aa,.36,.078,'leaf',rr.uniform(-.14,.12))
                if k%2:continue
                normal=Vector((math.cos(a),rr.uniform(.2,.9),math.sin(a))).normalized()
                u=normal.cross(Vector((0,1,0))).normalized();v=normal.cross(u);center=Vector(p)+normal*.065
                for j in range(5):
                    angle=j*math.tau/5;petalcenter=center+(u*math.cos(angle)+v*math.sin(angle))*.075
                    points=[petalcenter+(u*math.cos(k*math.tau/7)+v*math.sin(k*math.tau/7))*.066 for k in range(7)]
                    flowers.face(points,'flower')
                flowers.ellipsoid(center+normal*.008,(.025,.025,.025),'paper',6,3)
    # Low ferns, young bamboo and dead leaves break up the forest floor.
    for i in range(670):
        x=rng.uniform(-24,24);z=rng.uniform(-24,49)
        if abs(x)<5.8 and -15<z<2 or path_distance(x,z)<1.12:continue
        y=ground_height(x,z)
        for j in range(7):
            a=j*math.tau/7+rng.random()*.2;length=rng.uniform(.38,.85)
            for k in range(6):
                t=(k+1)/7;p=(x+math.cos(a)*length*t,y+math.sin(t*math.pi)*.4+.08,z+math.sin(a)*length*t)
                for side in (-1,1):leaf(under,p,a+side*.9,length*(1-t)*.45+.035,.035,'leaflight' if j%3==0 else 'leaf',-.045)
    # True mesh culms, nodal collars, branches and long, pointed bamboo leaves.
    layout=bamboo_layout()
    for chunk in range(6):
        culms=Mesh('bamboo_culms_'+str(chunk),mat,NAMES);leaves=Mesh('bamboo_leaves_'+str(chunk),mat,NAMES)
        meshes[culms.name]=culms;meshes[leaves.name]=leaves
        for index,(x,z,height,r,angle,far) in enumerate(layout):
            if index%6!=chunk:continue
            rr=random.Random(index+410);base=ground_height(x,z);count=10 if far else 20;sides=5 if far else 7
            leanx=math.cos(angle)*rr.uniform(.4,1.5);leanz=math.sin(angle)*rr.uniform(.4,1.5)
            def stem(t):return Vector((x+leanx*t*t,base+height*t,z+leanz*t*t))
            for j in range(count):
                a=j/count;b=(j+1)/count;radius=r*(1-a*.83)
                tube(culms,stem(a),stem(b-.003),radius,'bamboo',sides,end=r*(1-b*.83))
                tube(culms,stem(b-.003),stem(b+.001),r*(1-b*.83)*1.21,'node',sides,end=r*(1-b*.83)*1.19)
            for branch in range(4 if far else 7):
                t=.48+branch/(4 if far else 7)*.45;origin=stem(t);a=angle+branch*2.38;length=rr.uniform(1.6,3.)*(1-t*.4)
                end=origin+Vector((math.cos(a)*length,.25,math.sin(a)*length))
                tube(culms,origin,end,.023 if not far else .018,'bamboo',5,end=.008)
                for k in range(6 if far else 10):
                    q=(k+.5)/(6 if far else 10);anchor=origin.lerp(end,q)
                    for side in (-1,1):
                        aa=a+side*rr.uniform(.5,1.15);l=rr.uniform(.30,.67)
                        leaf(leaves,anchor,aa,l,.034 if far else .045,'leaflight' if k%4==0 else 'leaf',-.14)
                        if not far:
                            p=anchor+Vector((math.cos(aa)*.33,-.02,math.sin(aa)*.33));leaf(leaves,p,aa+.4*side,l*.85,.039,'leaf',-.18)
    counts={}
    for name,m in meshes.items():
        counts[name]=m.export(OUT);print(name,counts[name],flush=True)
    (OUT/'manifest.json').write_text(json.dumps(dict(separate_scene=True,bamboo_count=len(layout),models=counts,
        total_triangles=sum(v['triangles'] for v in counts.values()),textures=['materials.png','scrolls.png']),indent=2))
    bpy.ops.object.camera_add(location=(10,-8,3.3));cam=bpy.context.object;target=Vector((0,5,2));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=29;bpy.context.scene.camera=cam
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bamboo_grove.blend'),compress=True)

if __name__=='__main__':build()
