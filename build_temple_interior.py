"""Blender-authored separate temple hall: murals, painted brackets and caissons.

Run prepare_temple_interior_textures.py first, then this with Blender background.
"""
from pathlib import Path
import sys
import math
import json
import random
import bpy
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from temple_interior_mesh import Mesh
from g_temple_interior import COLUMNS,LIGHTS
NAMES=('stone','red','wood','cap','coffer','blue','green','scroll','bronze','robe','hair','roof','cloth','plaster','lamp','lotus')
OUT=ROOT/'art'/'temple'/'interior'

def material(name,file):
    m=bpy.data.materials.new(name);m.use_nodes=True
    image=bpy.data.images.load(str(OUT/file));image.pack()
    node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;node.interpolation='Closest'
    b=m.node_tree.nodes.get('Principled BSDF');m.node_tree.links.new(node.outputs['Color'],b.inputs['Base Color'])
    b.inputs['Roughness'].default_value=.9
    return m

def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    architecture=material('Weathered painted timber, stone and bronze','architecture.png')
    painting=material('Original Ming-inspired mineral pigment murals','murals.png')
    meshes={n:Mesh(n,architecture,NAMES) for n in ('hall_shell','hall_timber','hall_ceiling','hall_roof','hall_altar','hall_statues','hall_props','hall_courtyard','hall_lamps')}
    murals=Mesh('hall_murals',painting);meshes['hall_murals']=murals
    shell,timber,ceiling,roof,altar,statues,props,court,lamps=[meshes[n] for n in ('hall_shell','hall_timber','hall_ceiling','hall_roof','hall_altar','hall_statues','hall_props','hall_courtyard','hall_lamps')]
    rng=random.Random(7871)
    # Stone paving has shallow bevel-like shoulders and small real mortar joints.
    shell.box((0,-.18,1),(20.4,.30,24),'wood')
    for z in range(-10,12):
        for x in range(-10,10):
            y=rng.uniform(-.006,.006)
            shell.box((x+.5,y-.025,z+.5),(.992,.055,.992),'stone')
    for side in (-1,1):
        shell.box((side*10,2.85,-1),(.5,5.7,18.5),'plaster')
        shell.box((side*9.7,.45,-1),(.25,.9,18),'stone')
        for z in range(-9,9,2):shell.box((side*9.62,.9,z),(.35,.13,2),'cap')
    shell.box((0,2.85,-10),(20.5,5.7,.5),'plaster')
    shell.box((0,.45,-9.72),(20,.9,.28),'stone')
    # Front wall: the open centre doorway and deep lattice side panels are real.
    for side in (-1,1):
        for j in range(4):
            x=side*(3.35+j*1.83)
            shell.box((x,.6,8.0),(1.77,1.2,.24),'red')
            shell.box((x,4.9,8.0),(1.77,1.3,.24),'red')
            for xx in (x-.88,x+.88):timber.box((xx,2.8,8),(.11,5.6,.28),'red')
            for k in range(10):timber.box((x-.80+k*.177,2.75,8),(.035,3.1,.08),'wood')
            for yy in (1.3,1.85,2.40,2.95,3.50,4.05,4.28):timber.box((x,yy,8),(1.7,.035,.08),'wood')
            # Small diagonal lattice diamonds, visible in close camera views.
            for k in range(5):
                xx=x-.72+k*.35
                for yy in (1.6,2.7,3.8):
                    for sign in (-1,1):timber.beam((xx-.14,yy,7.94),(xx,yy+sign*.22,7.94),.025,.025,'green')
        timber.box((side*2.4,2.8,8),(.25,5.6,.4),'red')
        # Heavy open doors sit against the porch returns, with iron ring handles.
        shell.box((side*2.60,2.5,9.0),(.18,5.,2.1),'red')
        for yy in (.38,2.15,4.6):timber.box((side*2.71,yy,9.0),(.065,.13,1.9),'wood')
        for z in (8.2,9.8):timber.box((side*2.72,2.5,z),(.06,4.5,.07),'bronze')
    timber.box((0,5.1,8),(5.,.9,.35),'scroll')
    shell.box((0,.06,8),(4.7,.12,.38),'cap')

    def bracket(m,x,y,z,axis=0):
        for j in range(4):
            w=.62+j*.27;depth=.58+j*.27
            m.box((x,y+j*.19,z),((.28 if axis else w),.17,(w if axis else .28)),'blue')
            m.box((x,y+j*.19+.08,z+.10*j),(.22,.11,depth),'green')
            for sign in (-1,1):
                xx=x+sign*w*.42 if not axis else x
                zz=z+sign*w*.42 if axis else z
                m.box((xx,y+j*.19+.12,zz),(.21,.20,.22),'scroll')
    for x,z,r in COLUMNS:
        timber.lathe((x,0,z),[(0,.46),(.15,.47),(.25,.36),(.42,.31),(5.65,.26),(5.9,.34)],'red',16)
        timber.lathe((x,0,z),[(0,.48),(.10,.49),(.25,.39),(.30,.34)],'cap',16)
        bracket(timber,x,5.3,z)
        for side in (-1,1):timber.beam((x,4.8,z),(x+side*.92,5.62,z),.16,.19,'green')
    for z in (-8,-1,5.8,10.4):
        for x in (-6,0,6):timber.box((x,5.95,z),(6.0,.40,.38),'blue')
        for x in range(-9,10,2):bracket(timber,x,5.7,z)
    for x in (-9.65,-6,0,6,9.65):
        if abs(x)<7:
            for z,d in ((-7.95,5.1),(5.1,11.4)):timber.box((x,6.35,z),(.32,.36,d),'green')
        else:timber.box((x,6.35,.3),(.32,.36,21.3),'green')
    # Elaborate painted bands above the full-height side wall paintings.
    for side in (-1,1):
        for z in (-7,-3,1,5):
            timber.box((side*9.57,5.1,z),(.24,.35,4.0),'scroll')
            timber.box((side*9.53,5.52,z),(.30,.43,4.0),'blue')
            for zz in (z-1.5,z-.5,z+.5,z+1.5):bracket(timber,side*9.2,5.55,zz,1)

    # Four different paintings are mapped without stretching across corners.
    for side in (-1,1):
        for i,z in enumerate((-7.15,-2.7,1.75,5.85)):
            w=4.12 if i<3 else 3.35;x=side*9.73
            points=[(x,.98,z-side*w/2),(x,.98,z+side*w/2),(x,4.88,z+side*w/2),(x,4.88,z-side*w/2)]
            murals.face(points,(1,2,3,1)[i] if side<0 else (2,1,3,2)[i])
            for yy in (.96,4.9):timber.box((side*9.68,yy,z),(.08,.045,w+.05),'bronze')
    for x,tile in ((-7,2),(0,0),(7,1)):
        w=5.8 if x else 5.6
        murals.face([(x-w/2,.98,-9.72),(x+w/2,.98,-9.72),(x+w/2,5.18,-9.72),(x-w/2,5.18,-9.72)],tile)

    # Flat coffers give way to three deep octagonal mandala caissons.
    centers=(-6.,0.,6.)
    for x in range(-10,10,2):
        for z in range(-10,10,2):
            cx=x+1;cz=z+1
            if any(abs(cx-a)<2.01 and abs(cz+3)<2.01 for a in centers):continue
            ceiling.face([(x,6.7,z),(x+2,6.7,z),(x+2,6.7,z+2),(x,6.7,z+2)],'coffer')
            ceiling.box((cx,6.64,z),(2,.12,.13),'green');ceiling.box((x,6.64,cz),(.13,.12,2),'green')
    for cx in centers:
        cz=-3
        for j in range(6):
            radius=2.2-j*.155;y=6.65+j*.20
            for i in range(8):
                a=i*math.tau/8+math.pi/8;b=(i+1)*math.tau/8+math.pi/8
                pa=(cx+math.cos(a)*radius,y,cz+math.sin(a)*radius);pb=(cx+math.cos(b)*radius,y,cz+math.sin(b)*radius)
                ceiling.beam(pa,pb,.18,.20,'blue' if j%2 else 'scroll')
                for k in (.2,.5,.8):
                    xx=pa[0]*(1-k)+pb[0]*k;zz=pa[2]*(1-k)+pb[2]*k
                    ceiling.box((xx,y+.06,zz),(.16,.28,.25),'green')
        y=7.85;r=1.40
        points=[(cx+math.cos(i*math.tau/32)*r,y,cz+math.sin(i*math.tau/32)*r) for i in range(32)]
        # Use circular UVs inside the lotus tile for the mandala disk.
        tile=NAMES.index('lotus');u=tile%4/4;v=1-(tile//4+1)/4
        uv=[(u+.125+math.cos(i*math.tau/32)*.061,v+.125+math.sin(i*math.tau/32)*.061) for i in range(32)]
        ceiling.face(points,'lotus',uv=uv)
        # Close the spandrels above the octagon: no accidental sky holes.
        for x,z in ((-1,-1),(-1,1),(1,-1),(1,1)):
            ceiling.face([(cx+x*2.5,7.95,cz+z*2.5),(cx-x*2.5,7.95,cz+z*2.5),
                          (cx-x*2.5,7.95,cz-z*2.5),(cx+x*2.5,7.95,cz-z*2.5)],'wood')
            break
    # Heavy roof timbers and grey glazed tiles, including the visible porch soffit.
    for x in range(-11,12):
        for sign in (-1,1):
            roof.beam((x,8.8,-1),(x,6.6,-1+sign*12.3),.10,.17,'wood')
    for sign in (-1,1):
        for i in range(44):
            x=-11.6+i*23.2/44
            for j in range(12):
                t=j/12;tt=(j+1)/12
                def p(xx,a):return (xx,6.8+2.65*(1-a)**2+.50*a**8,-1+sign*12.4*a)
                points=[p(x,t),p(x+23.2/44,t),p(x+23.2/44,tt),p(x,tt)]
                roof.face(points if sign<0 else points[::-1],'roof')
                roof.face(points[::-1] if sign<0 else points,'wood')
        roof.beam((-11.7,7.28,-1+sign*12.4),(11.7,7.28,-1+sign*12.4),.20,.25,'green')
    roof.box((0,9.53,-1),(23.7,.28,.40),'roof')
    for side in (-1,1):
        end=[(side*11.6,6.65,-13.4),(side*11.6,9.46,-1),(side*11.6,6.65,11.4)]
        roof.face(end,'wood');roof.face(end[::-1],'wood')
        for sign in (-1,1):roof.beam((side*11.4,9.5,-1),(side*11.8,10.25,-1+sign*.1),.18,.20,'bronze')
    # Shrine dais and low carved offering table leave a full circuit behind it.
    altar.box((0,.19,-6.1),(9.6,.38,4.4),'stone')
    altar.box((0,.43,-6.1),(9.25,.14,4.15),'cap')
    altar.box((0,.68,-6.1),(8.9,.40,3.9),'red')
    for x in (-4,-2,0,2,4):altar.box((x,.69,-4.12),(1.7,.31,.07),'scroll')
    altar.box((0,2.93,-6.96),(9.4,4.85,.18),'red')
    murals.face([(2.55,1.02,-7.075),(-2.55,1.02,-7.075),(-2.55,5.12,-7.075),(2.55,5.12,-7.075)],0)
    for side in (-1,1):
        murals.face([(side*3.55+.9,1.02,-7.08),(side*3.55-.9,1.02,-7.08),(side*3.55-.9,5.12,-7.08),(side*3.55+.9,5.12,-7.08)],1 if side<0 else 2)
    altar.box((0,5.37,-6.96),(9.7,.18,.4),'scroll')
    altar.box((0,1.12,-2.95),(5.35,.20,.91),'red')
    altar.box((0,.87,-2.95),(5.1,.30,.68),'scroll')
    for x in (-2.35,2.35):
        for z in (-3.25,-2.65):altar.box((x,.49,z),(.19,.93,.19),'wood')
    altar.box((0,.60,-2.46),(2.05,1.0,.05),'cloth')

    def buddha(x,y,z,size):
        def e(c,r,t='bronze',seg=16,rings=10):statues.ellipsoid((x+c[0]*size,y+c[1]*size,z+c[2]*size),tuple(v*size for v in r),t,seg,rings)
        def lat(c,prof,t='bronze',scale=(1,1,1)):statues.lathe((x+c[0]*size,y+c[1]*size,z+c[2]*size),[(h*size,r*size) for h,r in prof],t,24,scale)
        lat((0,0,0),[(0,.75),(.12,.89),(.22,.84),(.32,.72)],'bronze',scale=(1,1,.75))
        for i in range(16):
            a=i*math.tau/16;e((math.cos(a)*.73,.26,math.sin(a)*.54),(.17,.20,.13),'robe',10,6)
        e((0,.53,0),(1.03,.35,.64),'robe');e((0,1.05,-.05),(.60,.70,.38),'robe')
        e((0,1.75,.03),(.29,.41,.28));e((0,1.99,-.015),(.30,.24,.28),'hair')
        e((0,2.2,-.02),(.11,.13,.11),'hair',12,7)
        for side in (-1,1):
            e((side*.30,1.68,.03),(.085,.22,.09));e((side*.57,1.08,.04),(.21,.50,.22),'robe')
            e((side*.40,.78,.37),(.28,.17,.18));e((side*.14,.75,.50),(.19,.075,.12))
            # Closed eyes, raised brows and elongated earlobes remain readable.
            e((side*.105,1.79,.264),(.078,.013,.015),'hair',10,5)
            e((side*.11,1.845,.252),(.083,.018,.024),'bronze',10,5)
        e((0,1.73,.295),(.048,.088,.050));e((0,1.63,.283),(.074,.014,.018),'robe',10,5)
        for i in range(9):
            a=(i-4)*.17
            statues.beam((x+a*size,y+.42*size,z+.55*size),(x+a*.6*size,y+1.44*size,z+.32*size),.018*size,.022*size,'bronze')
        # Raised gold nimbus on the painted backboard.
        for i in range(48):
            a=i*math.tau/48;b=(i+1)*math.tau/48
            statues.beam((x+math.cos(a)*.70*size,y+(1.74+math.sin(a)*.70)*size,z-.35*size),
                         (x+math.cos(b)*.70*size,y+(1.74+math.sin(b)*.70)*size,z-.35*size),.035*size,.04*size,'bronze')
    buddha(0,.91,-5.95,1.68)
    for x in (-3.05,3.05):buddha(x,.91,-5.86,1.35)

    def vessel(x,y,z,r,h,tile='bronze'):
        props.lathe((x,y,z),[(0,r*.65),(.06*h,r*.67),(.15*h,r*.52),(.30*h,r),(.68*h,r*1.05),(.86*h,r*.65),(.94*h,r*.57),(h,r*.72)],tile,18)
    for x in (-1.9,1.9):vessel(x,1.23,-2.95,.17,.48)
    vessel(0,1.23,-2.95,.24,.25)
    for x in (-.1,0,.1):props.beam((x,1.42,-2.95),(x+.018,1.9,-2.95),.012,.012,'wood')
    for side in (-1,1):
        vessel(side*8.9,0,-7.5,.38,1.04)
        for i in range(5):
            x=side*8.9+rng.uniform(-.19,.19);props.beam((x,.97,-7.5),(x,1.75,-7.5),.012,.012,'wood')
        vessel(side*1.06,1.22,-2.96,.34,.045)
        for i in range(5):props.ellipsoid((side*1.06+(i%3-1)*.17,1.34+(i//3)*.13,-2.98+(i//3)*.15),(.095,.095,.095),'robe',10,6)
        # Gong and drum on timber trestles in the shadowed entrance corners.
        for z in (4.4,5.4):
            props.beam((side*8-.6,0,z),(side*8-.4,1.9,z),.16,.16,'red');props.beam((side*8+.6,0,z),(side*8+.4,1.9,z),.16,.16,'red')
        props.box((side*8,1.75,4.9),(1.2,.15,1.25),'wood')
        props.ellipsoid((side*8,1.56,4.95),(.58,.67,.24),'bronze' if side<0 else 'robe',20,12)
    for x,z in ((-2.3,-.95),(0,-.95),(2.3,-.95)):
        props.lathe((x,0,z),[(0,.44),(.05,.50),(.14,.50),(.2,.43)],'cloth',24,scale=(1,1,.8))
    for x,y,z in LIGHTS:
        props.lathe((x,0,z),[(0,.22),(.1,.26),(.2,.12),(y-.35,.055),(y-.23,.20),(y-.16,.21)],'bronze',12)
        props.lathe((x,y-.16,z),[(0,.15),(.12,.13),(.26,.18),(.29,.20)],'bronze',12)
        lamps.ellipsoid((x,y+.15,z),(.045,.15,.045),'lamp',10,6)
        props.lathe((x,y+.35,z),[(0,.24),(.035,.27),(.12,.12),(.15,.04)],'bronze',12)

    # Courtyard, side parapets, rooflines and trees complete views through doors.
    court.box((0,-.25,22),(50,.45,23),'stone')
    for x in range(-17,18,2):
        for z in range(12,30,2):court.box((x,-.02,z),(1.985,.10,1.985),'cap')
    for side in (-1,1):
        court.box((side*17,.8,22),(.7,1.6,23),'plaster')
        court.box((side*17,1.68,22),(.95,.20,23),'roof')
        court.box((side*22,2.2,22),(8,4.4,18),'red')
        for sign in (-1,1):
            court.face([(side*22,6.1,12),(side*22+sign*5,4.6,12),(side*22+sign*5,4.6,32),(side*22,6.1,32)],'roof')
    for x in (-8,-4,0,4,8):
        for z in (9.8,):court.face([(x-2,6.55,z-1.6),(x+2,6.55,z-1.6),(x+2,6.55,z+1.6),(x-2,6.55,z+1.6)],'coffer')
    manifest=dict(scene='temple_interior',units='metres',separate_from_intro=True,models={},mural_atlas=[1024,1024],architecture_atlas=[1024,1024],architecture_tile_size=128,architecture_gutter=64,
                  references=['https://www.youtube.com/watch?v=W07UAbYXJuc','https://www.youtube.com/watch?v=ZKio-KcdQKU'])
    for name,m in meshes.items():manifest['models'][name]=m.export(OUT)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    # Useful modelling camera: see all of the central hall from the doorway.
    bpy.ops.object.camera_add(location=(8,-7,3.7));camera=bpy.context.object
    from mathutils import Vector
    camera.rotation_euler=(Vector((0,4,2.8))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=21
    bpy.context.scene.camera=camera;bpy.context.scene.world.color=(.22,.22,.22)
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'temple_interior.blend'))
    print('Interior triangles:',sum(m['triangles'] for m in manifest['models'].values()),flush=True)

if __name__=='__main__':build()
