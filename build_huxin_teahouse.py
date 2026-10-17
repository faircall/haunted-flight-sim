"""Blender authoring for the independent Moon in the Water encounter.

Reuses the pavilion's painted atlas and stone core; no original assets are edited.
"""
from pathlib import Path
import sys, math, json, random
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from temple_interior_mesh import Mesh
from build_bamboo_grove import tube
from build_huxin_moon import material,face_up,OUT
from prepare_huxin_moon import TILES
from g_huxin_moon import DECK,inside_platform
from g_huxin_moon_sequence import UPPER,BASIN,MIRROR,MARK,TEA_LIGHTS,STAIR,STAIR_COUNT
from huxin_moon_floor import outside_core

def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mat=material('Moon teahouse: old lacquer, limestone and grey clay','materials.png')
    names=('moon_basin','moon_mirror','tea_foundation','tea_frame','tea_walls','tea_lattice',
           'tea_floors','tea_stairs','tea_roofs','tea_ceiling','tea_furniture','tea_lanterns','tea_ground','moon_fixture')
    meshes={n:Mesh(n,mat,TILES) for n in names}
    basin,mirror,stone,frame,walls,lattice,floors,stairs,roof,ceiling,props,lamps,ground,fixture=[meshes[n] for n in names]
    rr=random.Random(88231)
    # A hollow stone bowl with a shallow, dark pool, plus a plain worn circular
    # depression in its bottom. The reflected moon is rendered dynamically.
    basin.lathe((0,DECK,0),[(0,.55),(.10,.62),(.17,.53),(.57,.40),(.63,.79),(.77,.88),(.90,.85),(.91,.73),(.73,.63),(.71,.001)],'stone',40)
    basin.lathe((0,DECK+.13,0),[(0,.54),(.06,.56),(.10,.53)],'wetstone',32)
    for i in range(32):
        a=i*math.tau/32;b=(i+1)*math.tau/32
        face_up(basin,((0,BASIN[1]-.012,0),(.70*math.cos(a),BASIN[1]-.012,.70*math.sin(a)),(.70*math.cos(b),BASIN[1]-.012,.70*math.sin(b))),'water')
    basin.lathe((MARK[0],BASIN[1]-.008,MARK[2]),[(0,.115),(.004,.115),(.004,.094),(0,.094)],'wetstone',32)
    x,y,z=MIRROR
    fixture.lathe((x,DECK,z),[(0,.28),(.08,.30),(.15,.20),(.23,.13),(1.12,.09),(1.18,.14)],'bronze',20)
    for side in (-1,1):fixture.beam((x+side*.20,DECK+1.12,z),(x+side*.32,y,z),.055,.055,'bronze')
    # Mirror local +Z is its normal; viewer uses the same normal for its optics.
    N=48
    for i in range(N):
        a=i*math.tau/N;b=(i+1)*math.tau/N
        p=(.285*math.cos(a),.285*math.sin(a),.012);q=(.285*math.cos(b),.285*math.sin(b),.012)
        mirror.face(((0,0,.012),p,q),'bronze')
        mirror.face(((0,0,-.026),(q[0],q[1],-.026),(p[0],p[1],-.026)),'bronze')
        mirror.beam(p,q,.026,.032,'bronze')
    mirror.box((0,-.34,0),(.055,.17,.055),'bronze')
    # Under-water stone plinths and piers; additions rest lightly on the lake.
    for x,z,w,d in ((0,0,14,12.4),(9.7,0,5.4,6.6)):
        # Open-topped foundations: the actual floors above own the visible top.
        # Layering three almost coplanar cap faces under the paving caused speckle.
        for y,height,ww,dd,tile in ((DECK-.60,1.15,w,d,'wetstone'),(DECK-.08,.13,w+.12,d+.12,'stone')):
            start=len(stone.faces);stone.box((x,y,z),(ww,height,dd),tile)
            for j in range(len(stone.faces)-1,start-1,-1):
                if all(abs(stone.vertices[k][1]-(y+height/2))<1e-7 for k in stone.faces[j]):
                    del stone.faces[j];del stone.uv[j];del stone.smooth[j]
    # The balcony crosses the approach, but its supports must not. Split the
    # former central pile/post into an entrance bay: both stone shoes and timber
    # uprights sit outside the bending causeway, with a proper header above it.
    for x in (-6.7,-3.5,-1.9,1.9,3.5,6.7):
        stone.lathe((x,-1.7,7.9),[(0,.29),(1.9,.29),(2.0,.37)],'wetstone',10)
        frame.box((x,(UPPER+DECK)/2,7.9),(.17,UPPER-DECK,.17),'wood')
        frame.beam((x,UPPER-.18,7.9),(x,UPPER-1.0,5.9),.17,.18,'wood')
    frame.box((0,UPPER-.23,7.9),(3.97,.30,.24),'wood')
    # The surviving core has exactly one visible floor. New paving meets its
    # perimeter instead of extending another plane underneath it.
    for poly in outside_core([(-6.9,-6.05),(6.9,-6.05),(6.9,6.05),(-6.9,6.05)]):
        face_up(ground,[(x,DECK,z) for x,z in poly],'stone')
    def floor_piece(poly,y,thickness,tile):
        pieces=outside_core(poly) if y<1 else [poly]
        for part in pieces:
            top=[(x,y,z) for x,z in part];face_up(floors,top,tile)
            floors.face([(x,y-thickness,z) for x,z in part],tile)
            for a,b in zip(top,top[1:]+top[:1]):
                floors.face((a,b,(b[0],y-thickness,b[2]),(a[0],y-thickness,a[2])),tile)
    def boards(x0,x1,z0,z1,y):
        floor_piece([(x0,z0),(x1,z0),(x1,z1),(x0,z1)],y-.035,.06,'wood')
        count=math.ceil((x1-x0)/.28);w=(x1-x0)/count
        for i in range(count):
            for j in range(math.ceil((z1-z0)/1.5)):
                lo=z0+j*1.5;hi=min(z1,lo+1.5)
                a=x0+i*w+.004;b=x0+(i+1)*w-.004
                floor_piece([(a,lo+.004),(b,lo+.004),(b,hi-.004),(a,hi-.004)],y,.11,'wood')
    boards(7,12.2,-3.1,3.1,DECK+.01)
    boards(-4.4,6.8,-5.8,6.1,UPPER)
    boards(-6.8,-4.4,-5.8,-4.45,UPPER)
    boards(-6.8,-4.4,4.85,6.1,UPPER)
    boards(-6.8,6.8,6.1,8.2,UPPER)
    # Real joists under the upper floor, with a generous stairwell opening.
    for z in (-5.6,-4.4,-2.4,0,2.4,4.8,6.0):
        x0=-6.8 if z<-4.45 or z>4.85 else -4.4
        frame.box(((x0+6.8)/2,UPPER-.23,z),(6.8-x0,.28,.22),'wood')
    for x in (-6.85,-4.4,0,6.85):frame.box((x,UPPER-.25,0),(.24,.31,12),'wood')
    # Main structural grid, stone column shoes, restrained stacked dougong.
    for level in (DECK,UPPER):
        for x,z in tuple((x,z) for x in (-6.85,-3.45,0,3.45,6.85) for z in (-5.9,6.1))+((-6.85,-2),(-6.85,2),(6.85,-2),(6.85,2)):
            if x==0 and z>0:continue # The entrance and balcony door stay open.
            frame.lathe((x,level,z),[(0,.23),(.13,.25),(.25,.19)],'stone',10)
            frame.lathe((x,level+.20,z),[(0,.145),(3.25,.13),(3.40,.18)],'wood',12)
            for j in range(3):
                frame.box((x,level+3.25+j*.12,z),(.40+j*.20,.105,.20),'paint' if j==1 else 'wood')
                frame.box((x,level+3.30+j*.12,z),(.20,.10,.40+j*.20),'wood')
        for z in (-5.9,6.1):frame.box((0,level+3.45,z),(14.2,.26,.24),'paint')
        for x in (-6.85,6.85):frame.box((x,level+3.45,.1),(.24,.26,12.4),'wood')
    # Windows have true open lattice holes, a plaster lower dado, shutters and
    # deep timber reveals. Each is two-sided geometry, suitable for near cameras.
    def panel(a,b,y,window=True):
        ax,az=a;bx,bz=b;length=math.hypot(bx-ax,bz-az);dx,dz=(bx-ax)/length,(bz-az)/length
        def point(t,h,offset=0):return(ax+dx*t-dz*offset,y+h,az+dz*t+dx*offset)
        def bar(t0,h0,t1,h1,w=.045,d=.065,tile='wood',offset=0):lattice.beam(point(t0,h0,offset),point(t1,h1,offset),w,d,tile)
        if not window:
            walls.beam(point(0,1.58),point(length,1.58),.15,3.16,'plaster');return
        # beam's cross-section depends on axis; explicit boxes for the wall base
        walls.box(point(length/2,.42),((length if abs(dx)>.5 else .16),.84,(length if abs(dz)>.5 else .16)),'plaster')
        walls.box(point(length/2,.08),((length if abs(dx)>.5 else .19),.16,(length if abs(dz)>.5 else .19)),'wetstone')
        for h in (.88,1.02,2.87,3.12):bar(0,h,length,h,.105,.13)
        for t in (0,length/2,length):bar(t,.84,t,3.20,.10,.13)
        # Ice-ray inspired restrained geometric lattice; no opaque window texture.
        n=max(3,round(length/.36))
        for i in range(n+1):
            t=i*length/n;bar(t,1.03,t,2.86,.032,.055)
        for h in (1.36,1.74,2.12,2.50):bar(0,h,length,h,.033,.055)
        for i in range(n):
            t=(i+.5)*length/n;half=length/n*.45
            for h in (1.55,2.31):
                for p,q in (((t-half,h),(t,h+.17)),((t,h+.17),(t+half,h)),((t+half,h),(t,h-.17)),((t,h-.17),(t-half,h))):bar(*p,*q,.026,.04,'wood')
        # Solid folded shutters parked beside each bay.
        for t in (.12,length-.12):
            bar(t,1.06,t,2.85,.19,.07,'wood',.15)
            for h in (1.25,2.62):bar(t-.08,h,t+.08,h,.04,.08,'bronze',.20)
    for y in (DECK,UPPER):
        for z in (-5.9,6.1):
            spans=((-6.8,-3.5),(-3.5,-1.25),(1.25,3.5),(3.5,6.8)) if z>0 else ((-6.8,-3.4),(-3.4,0),(0,3.4),(3.4,6.8))
            for a,b in spans:panel((a,z),(b,z),y)
            if z>0:
                frame.box((0,y+2.85,z),(2.6,.25,.22),'wood')
                for x in (-1.25,1.25):frame.box((x,y+1.42,z),(.12,2.85,.22),'wood')
        for x in (-6.9,6.9):
            spans=((-5.9,-3.2),(-3.2,-1.2),(1.2,3.3),(3.3,6.1)) if x>0 and y==DECK else ((-5.9,-2),(-2,2),(2,6.1))
            for a,b in spans:panel((x,a),(x,b),y)
    for z in (-3.2,3.2):
        for a,b in ((7,9.6),(9.6,12.3)):panel((a,z),(b,z),DECK)
    for a,b in ((-3.2,0),(0,3.2)):panel((12.3,a),(12.3,b),DECK)
    for a,b in ((-5.9,-3.9),(-3.9,-1.9)):panel((2.3,a),(2.3,b),UPPER)
    panel((2.3,-1.9),(3.1,-1.9),UPPER);panel((4.5,-1.9),(6.9,-1.9),UPPER)
    frame.box((3.8,UPPER+2.85,-1.9),(1.5,.20,.15),'wood')
    # Stairs: comfortable rise, carved nosings, continuous stringers and rail.
    x0,x1,zt,zb=STAIR
    for i in range(STAIR_COUNT):
        lo=zb-(i+1)*(zb-zt)/STAIR_COUNT;hi=zb-i*(zb-zt)/STAIR_COUNT;y=DECK+(i+1)*3.8/STAIR_COUNT
        stairs.box(((x0+x1)/2,y-.08,(lo+hi)/2),(x1-x0,.16,hi-lo+.015),'wood')
        stairs.box(((x0+x1)/2,y-.025,hi-.01),(x1-x0+.06,.05,.065),'wood')
        if i<STAIR_COUNT-1:stairs.box(((x0+x1)/2,y+.006,lo), (x1-x0,.18,.04),'wood')
    for x in (x0,x1):
        stairs.beam((x,DECK-.12,zb),(x,UPPER-.12,zt),.16,.32,'wood')
        stairs.beam((x,DECK+.95,zb),(x,UPPER+.95,zt),.08,.09,'wood')
        for i in range(0,STAIR_COUNT+1,2):
            z=zb-i*(zb-zt)/STAIR_COUNT;y=DECK+i*3.8/STAIR_COUNT
            stairs.box((x,y+.46,z),(.065,.95,.065),'wood')
    def rail(a,b,y):
        length=math.dist(a,b);n=math.ceil(length/.42)
        for h in (.14,.70,1.0):frame.beam((a[0],y+h,a[1]),(b[0],y+h,b[1]),.085,.09,'wood')
        for i in range(n+1):
            t=i/n;x=a[0]*(1-t)+b[0]*t;z=a[1]*(1-t)+b[1]*t
            frame.box((x,y+.54,z),(.055,1.08,.055),'wood')
    for a,b in (((-6.8,8.2),(6.8,8.2)),((-6.8,6.1),(-6.8,8.2)),((6.8,6.1),(6.8,8.2)),((-4.5,-4.2),(-4.5,4.75)),((-6.8,4.75),(-4.5,4.75))):rail(a,b,UPPER)
    # Broad concave hipped roofs with individually modelled tile channels.
    def hip(cx,cz,rx,rz,y,rise,rows=12,cols=30,inner=0.):
        corners=((-rx,-rz),(rx,-rz),(rx,rz),(-rx,rz))
        def p(side,t,s):
            a=corners[side];b=corners[(side+1)%4];x=a[0]*(1-s)+b[0]*s;z=a[1]*(1-s)+b[1]*s
            return(cx+x*t,y+rise*(1-t)**2+.18*t**8+.60*abs(s*2-1)**7*t**6,cz+z*t)
        for side in range(4):
            for col in range(cols):
                s=col/cols;ss=(col+1)/cols
                for row in range(rows):
                    t=max(.008,inner+(1-inner)*row/rows);tt=inner+(1-inner)*(row+1)/rows
                    pts=[p(side,a,b) for a,b in ((t,s),(tt,s),(tt,ss),(t,ss))]
                    face_up(roof,pts,'roof');ceiling.face([(x,h-.14,z) for x,h,z in pts],'wood')
                    if row>0:
                        a=p(side,t,s);b=p(side,tt,s);tube(roof,(a[0],a[1]+.03,a[2]),(b[0],b[1]+.03,b[2]),.036,'roof',5,end=.035)
                    if col%3==0:ceiling.beam(tuple(v-(.23 if j==1 else 0) for j,v in enumerate(p(side,t,s))),tuple(v-(.23 if j==1 else 0) for j,v in enumerate(p(side,tt,s))),.07,.10,'wood')
                tube(roof,p(side,1,s),p(side,1,ss),.07,'roof',8,end=.07)
            for j in range(rows):
                a=p(side,inner+(1-inner)*j/rows,0);b=p(side,inner+(1-inner)*(j+1)/rows,0)
                tube(roof,(a[0],a[1]+.085,a[2]),(b[0],b[1]+.085,b[2]),.085,'roof',8,end=.085)
    hip(0,0,8.25,7.6,UPPER+3.48,2.50,14,34)
    # Lower skirt wraps the first floor without covering the upstairs rooms.
    hip(0,.55,8.1,7.8,UPPER-.25,1.5,6,30,.84)
    hip(9.75,0,3.7,4.25,DECK+3.32,1.45,10,20)
    # Familiar small hexagonal crown above the broad upper roof.
    for i in range(6):
        a=i*math.tau/6;b=(i+1)*math.tau/6
        frame.box((math.cos(a)*1.7,10.40,math.sin(a)*1.7),(.12,.9,.12),'wood')
        frame.beam((math.cos(a)*1.7,10.70,math.sin(a)*1.7),(math.cos(b)*1.7,10.70,math.sin(b)*1.7),.13,.16,'paint')
        for j in range(12):
            for k in range(9):
                def p(t,s):return ((math.cos(a)*(1-s)+math.cos(b)*s)*2.7*t,10.65+1.4*(1-t)**2+.2*t**8+.4*abs(s*2-1)**6*t**5,(math.sin(a)*(1-s)+math.sin(b)*s)*2.7*t)
                pts=[p(t,s) for t,s in ((max(.01,k/9),j/12),((k+1)/9,j/12),((k+1)/9,(j+1)/12),(max(.01,k/9),(j+1)/12))]
                face_up(roof,pts,'roof');ceiling.face([(x,h-.12,z) for x,h,z in pts],'wood')
                tube(roof,p(max(.01,k/9),j/12),p((k+1)/9,j/12),.032,'roof',5,end=.032)
    roof.lathe((0,12.05,0),[(0,.21),(.10,.29),(.24,.17),(.40,.21),(.56,.09),(.82,.015)],'bronze',16)
    # Chairs, tables and tea ware: useful silhouettes at the native 640x360.
    def table(x,z,y,w,d):
        props.box((x,y+.76,z),(w,.085,d),'wood');props.box((x,y+.66,z),(w-.10,.15,d-.10),'wood')
        for xx in (-w/2+.12,w/2-.12):
            for zz in (-d/2+.12,d/2-.12):props.beam((x+xx*1.04,y,z+zz*1.04),(x+xx,y+.70,z+zz),.09,.09,'wood')
        for zz in (-d/2+.12,d/2-.12):props.beam((x-w/2+.12,y+.25,z+zz),(x+w/2-.12,y+.25,z+zz),.05,.07,'wood')
    def chair(x,z,y,back=1):
        props.box((x,y+.44,z),(.64,.07,.60),'wood')
        for xx in (-.25,.25):
            for zz in (-.23,.23):props.box((x+xx,y+.22,z+zz),(.07,.44,.07),'wood')
            props.box((x+xx,y+.76,z+back*.25),(.055,.65,.055),'wood')
        props.box((x,y+1.03,z+back*.25),(.63,.09,.065),'wood')
        props.box((x,y+.79,z+back*.25),(.13,.40,.06),'wood')
    def cup(x,z,y):
        props.lathe((x,y,z),[(0,.06),(.015,.09),(.03,.07),(.12,.095),(.135,.095),(.135,.078),(.05,.05)],'plaster',16)
        props.lathe((x,y+.052,z),[(0,.05),(.001,.001)],'water',16)
    table(9.7,-.1,DECK,2.1,1.28);chair(9.7,1.25,DECK,1);chair(9.7,-1.45,DECK,-1);chair(11.25,-.1,DECK,1)
    for x,z in ((9.25,.25),(10.2,.25),(9.7,-.5)):cup(x,z,DECK+.81)
    props.lathe((9.7,DECK+.81,-.02),[(0,.13),(.08,.21),(.22,.19),(.27,.12),(.30,.15),(.32,.04),(.36,.04)],'cap',24)
    props.beam((9.82,DECK+.93,-.02),(10.01,DECK+1.09,-.02),.09,.08,'cap')
    for i in range(12):
        a=i*math.pi/12;b=(i+1)*math.pi/12
        props.beam((9.52-.12*math.sin(a),DECK+.97+.13*math.cos(a),-.02),(9.52-.12*math.sin(b),DECK+.97+.13*math.cos(b),-.02),.035,.035,'cap')
    table(-1.6,-4.65,DECK,2.4,.7);table(5.3,-4.6,UPPER,1.7,.84);chair(5.3,-3.45,UPPER,1)
    table(-1.9,-4.8,UPPER,2.2,.64);table(4,3.5,UPPER,1.3,1.3)
    for x in (3.,5.):chair(x,3.5,UPPER,1)
    cup(4,3.5,UPPER+.81)
    # Empty lacquer tray marks the future item location, without adding lore.
    props.box((5.3,UPPER+.82,-4.6),(.78,.025,.39),'bronze')
    for z in (-4.81,-4.39):props.box((5.3,UPPER+.85,z),(.84,.07,.035),'wood')
    for x in (4.88,5.72):props.box((x,UPPER+.85,-4.6),(.035,.07,.45),'wood')
    for x,y,z in TEA_LIGHTS:
        lamps.lathe((x,y-.25,z),[(0,.12),(.06,.23),(.18,.27),(.40,.25),(.51,.14)],'paper',16)
        for j in range(8):
            a=j*math.tau/8
            props.beam((x+.19*math.cos(a),y-.21,z+.19*math.sin(a)),(x+.21*math.cos(a),y+.20,z+.21*math.sin(a)),.012,.012,'wood')
        for h in (-.25,.26):props.lathe((x,y+h,z),[(0,.15),(.04,.15)],'wood',16)
        end=UPPER-.1 if y<UPPER else UPPER+3.5
        props.beam((x,y+.30,z),(x,end,z),.015,.015,'bronze')
    counts={n:m.export(OUT) for n,m in meshes.items()}
    (OUT/'teahouse_manifest.json').write_text(json.dumps(dict(models=counts,total_triangles=sum(c['triangles'] for c in counts.values()),upper_floor=UPPER,stair_count=STAIR_COUNT,item_location=(5.3,UPPER+.85,-4.6)),indent=2))
    bpy.ops.object.camera_add(location=(26,-34,17));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,5))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=42;bpy.context.scene.camera=cam
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'moon_teahouse.blend'),compress=True)
    print('TEAHOUSE COMPLETE',sum(c['triangles'] for c in counts.values()),flush=True)

if __name__=='__main__':build()
