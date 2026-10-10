"""Close-view cabin hardware: real belt slots, webbing, buckles and upholstery."""
import math
from mathutils import Vector
from g_santana_geometry import actor_point,cabin_point,CENTER_POST_Z,DOOR_CENTERS,rear_belt_path


def fittings_atlas(Atlas):
    a=Atlas('santana_cabin_details',256)
    names=(('cloth',(105,111,110),'cloth'),('seat_side',(78,84,85),'cloth'),
           ('webbing',(36,41,43),'plain'),('plastic',(61,68,69),'plain'),
           ('rubber',(23,28,30),'plain'),('chrome',(151,158,151),'plain'),
           ('button',(180,49,38),'plain'),('slot',(12,18,19),'plain'),
           ('seams',(128,135,129),'cloth'),('screw',(141,149,146),'plain'),
           ('switch',(78,86,81),'plain'),('boot',(42,49,50),'plain'),
           ('vent',(27,34,35),'plain'),('light',(177,176,145),'plain'),
           ('gauge',(27,34,32),'plain'),('label',(183,184,168),'plain'))
    for i,(name,c,style) in enumerate(names):a.patch(name,((i%4)*64,(i//4)*64,64,64),c,style)
    for x in (131,133,186,188):
        a.line((x,1),(x,62),(78,85,81))
    for y in range(2,62,3):
        a.line((135,y),(184,y),(43,49,48))
        a.pixel(132,y,(124,132,121));a.pixel(187,y,(124,132,121))
    a.line((132,68),(185,68),(224,100,73));a.line((132,122),(185,122),(106,25,21))
    for x in (139,148,157,166,175):a.line((x,91),(x+4,91),(229,200,175),2)
    for p,q in (((71,134),(120,183)),((71,183),(120,134))):a.line(p,q,(51,60,61),3)
    for y in range(196,252,7):
        a.line((4,y),(59,y),(109,117,111));a.line((4,y+3),(59,y+3),(14,21,23))
    for y in range(194,253,5):a.line((67,y),(123,y),(217,216,178))
    for y in range(131,190,5):a.line((195,y),(252,y),(62,70,69))
    return a


def ribbon(mesh,points,width=.036,normal=(0,0,-1),steps=3,patch='webbing'):
    """Thin solid webbing with continuous UVs and visible edges, not a tube."""
    control=[Vector(p) for p in points];path=[]
    for a,b in zip(control,control[1:]):
        path.extend(a.lerp(b,i/steps) for i in range(steps))
    path.append(control[-1]);normal=Vector(normal).normalized();rows=[]
    for i,p in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(0,i-1)]).normalized()
        across=normal.cross(tangent)
        if across.length<.001:across=Vector((1,0,0))
        across.normalize();across*=width/2
        rows.append([p-across+normal*.002,p+across+normal*.002,
                     p+across-normal*.002,p-across-normal*.002])
    for i,(a,b) in enumerate(zip(rows,rows[1:])):
        for j in range(4):
            pts=[a[j],b[j],b[(j+1)%4],a[(j+1)%4]]
            outward=sum(pts,Vector())/4-(path[i]+path[i+1])/2
            uv=[(0,i/(len(path)-1)),(0,(i+1)/(len(path)-1)),
                (1,(i+1)/(len(path)-1)),(1,i/(len(path)-1))]
            if (pts[1]-pts[0]).cross(pts[2]-pts[0]).dot(outward)<0:
                pts.reverse();uv.reverse()
            mesh.face(pts,patch if j in (0,2) else 'rubber',uv,smooth=False)
    mesh.face(list(reversed(rows[0])),patch);mesh.face(rows[-1],patch)


def slot_frame(mesh,center,width,height,depth,axis='x',patch='chrome'):
    """Rounded hollow guide: the belt can visibly thread through its opening."""
    center=Vector(center)
    right=Vector((0,0,1)) if axis=='x' else Vector((1,0,0))
    up=Vector((0,1,0));normal=right.cross(up);rings=[]
    for scale,z in ((1,-depth/2),(1,depth/2),(.64,depth/2),(.64,-depth/2)):
        row=[];w=width*scale/2;h=height*scale/2;r=min(w,h)*.35
        for cx,cy,start in ((w-r,h-r,0),(-w+r,h-r,90),(-w+r,-h+r,180),(w-r,-h+r,270)):
            for j in range(3):
                a=math.radians(start+j*45)
                row.append(center+right*(cx+r*math.cos(a))+up*(cy+r*math.sin(a))+normal*z)
        rings.append(row)
    for a,b in zip(rings,rings[1:]+rings[:1]):
        for i in range(len(a)):
            points=[a[i],a[(i+1)%len(a)],b[(i+1)%len(a)],b[i]]
            mesh.face(points,patch,smooth=True)


def screw(mesh,center,axis='x',radius=.008):
    p=Vector(center);normal=Vector((1,0,0)) if axis=='x' else Vector((0,0,1))
    mesh.tube(p-normal*.003,p+normal*.003,radius,'screw',8)


def buckle(mesh,x,y,z,front=False):
    # A flexible stalk, metal tongue and recessed black receiving mouth.
    mesh.beam((x,y-.085,z+.014),(x,y-.027,z),.025,.022,'webbing')
    mesh.rounded_box((x,y,z),(.069,.087,.070),'rubber',.013,1)
    mesh.box((x,y+.037,z-.011),(.047,.008,.048),'slot')
    mesh.rounded_box((x,y+.037,z+.015),(.050,.017,.025),'button',.006,1)
    if front:mesh.box((x,y+.048,z-.022),(.035,.017,.006),'chrome')
    screw(mesh,(x,y-.075,z+.027),'z',.010)


def seat_seam(x,y,rear=False):
    """Use the padded cloth surface itself to place a sewn welt without gaps."""
    low,high,z0,z1,width=(.611,1.158,1.23,1.419,1.675) if rear else (.592,1.070,.020,.151,.640)
    old_y=(y-.026)/.88
    t=max(0,min(1,(old_y-low-.027)/(high-low-.054)))
    w=width*(1-.10*t)
    u=x/(w*.42*.88) if rear else math.copysign(.96,x)
    depth=.135*(.80+.20*math.sin(math.pi*t))
    pad=.016*math.sin(math.pi*t)**2*(1-u*u)
    z=z0+(z1-z0)*t+(depth/2+.007+.012*u**4+pad)*(-1 if rear else 1)
    xx=x if rear else w*.42*.88*u
    return (xx,y,cabin_point((0,old_y,z))[2]+(-.004 if rear else .004))


def build_fittings(mesh):
    features={}
    def mark(name,start):features[name]=sum(len(f)-2 for f in mesh.f[start:])
    start=len(mesh.f)
    for sign in (-1,1):
        # Sliding B-pillar carrier, open steel guide and capped fixing bolts.
        hardware_start=len(mesh.v)
        mesh.rounded_box((sign*.741,1.235,.075),(.030,.177,.109),'plastic',.012,1)
        mesh.box((sign*.720,1.235,.075),(.013,.096,.049),'rubber')
        slot_frame(mesh,(sign*.713,1.218,.075),.105,.071,.012)
        for y in (1.179,1.294):screw(mesh,(sign*.721,y,.075))
        # Retractor enclosure and the upward return behind the occupied seat.
        mesh.rounded_box((sign*.729,.371,.070),(.093,.139,.098),'plastic',.016,1)
        mesh.box((sign*.710,.431,.070),(.027,.017,.069),'slot')
        screw(mesh,(sign*.676,.364,.072))
        ribbon(mesh,[(sign*.709,.430,.071),(sign*.714,.85,.075),(sign*.710,1.212,.075)],normal=(-sign,0,0))
        mesh.v[hardware_start:]=[Vector((p[0]-sign*.018,p[1],p[2]+CENTER_POST_Z-.075))
                                for p in mesh.v[hardware_start:]]
        # Occupied front webbing belongs to the actor mesh, fitted to its chest.
        # Rear outboard belts have their own guides on the C-pillar trim.
        mesh.rounded_box((sign*.683,1.178,.876),(.050,.120,.089),'plastic',.012,1)
        slot_frame(mesh,(sign*.664,1.170,.851),.065,.057,.012,axis='z')
        screw(mesh,(sign*.674,1.212,.835),'z')
        ribbon(mesh,rear_belt_path(sign),width=.046,steps=2)
        # Sliding tongue remains free on the hanging belt, above an empty socket.
        slot_frame(mesh,(sign*.629,.748,.699),.058,.058,.010,axis='z')
    mark('belt_guides_retractors_and_webbing',start)

    start=len(mesh.f)
    for sign in (-1,1):
        buckle(mesh,sign*.161,.571,-.326,front=True)
        buckle(mesh,sign*.236,.586,.574)
    buckle(mesh,.02,.587,.708)
    mark('five_buckle_housings_buttons_and_stalks',start)

    start=len(mesh.f)
    for sign in (-1,1):
        x=sign*.396
        # Padded seat-back pouch, with a shadowed opening and rolled top lip.
        rows=[]
        for j in range(7):
            t=j/6;y=.615+.191*t;z=.135+.045*t
            rows.append([(x+.191*u*(1-.065*(1-t)),y,
                          z+.013+.020*math.sin(math.pi*t)*(1-u*u)) for u in [-1+2*i/12 for i in range(13)]])
        mesh.grid(rows,'seat_side',reverse=True)
        for edge in (0,-1):
            for a,b in zip(rows,rows[1:]):
                p,q=a[edge],b[edge]
                mesh.face([p,q,(q[0],q[1],q[2]-.027),(p[0],p[1],p[2]-.027)],'cloth')
        mesh.rounded_box((x,.807,.190),(.380,.022,.026),'rubber',.008,1)
        ribbon(mesh,[(x-.178,.802,.206),(x,.790,.206),(x+.178,.802,.206)],.007,normal=(0,0,1),patch='seams',steps=2)
        # Profile seams follow the rounded back and cushion, rather than squares.
        for side in (-1,1):
            points=[seat_seam(side,y) for y in (.585,.710,.860,.936)]
            ribbon(mesh,[(x+dx,y,z) for dx,y,z in points],.006,normal=(0,0,1),patch='seams',steps=2)
        # Seat slide rails, a large recline wheel and visible hinge bracket.
        for dx in (-.205,.205):
            mesh.beam((x+dx,.267,-.543),(x+dx,.267,.100),.030,.025,'chrome')
            mesh.box((x+dx,.294,-.34),(.051,.049,.122),'rubber')
        mesh.rounded_box((sign*.654,.427,.069),(.066,.117,.155),'plastic',.017,1)
        mesh.tube((sign*.653,.457,.074),(sign*.692,.457,.074),.051,'rubber',12)
        screw(mesh,(sign*.694,.457,.074),radius=.016)
        for dx in (-.092,.092):
            mesh.rounded_box((x+dx,.967,.177),(.040,.028,.041),'plastic',.008,1)
    # Split bench seams and a welt across the leading cushion edge.
    for x in (-.242,.242):
        ribbon(mesh,[seat_seam(x,y,rear=True) for y in (.594,.796,1.012)],.007,patch='seams',steps=3)
    ribbon(mesh,[(-.65,.591,.493),(-.32,.584,.480),(0,.582,.477),(.32,.584,.480),(.65,.591,.493)],
           .005,normal=(0,1,0),patch='seams',steps=2)
    mark('seat_pockets_seams_rails_and_recline_hardware',start)

    start=len(mesh.f)
    for sign in (-1,1):
        for z in DOOR_CENTERS:
            # Recessed latch surround, inner chrome lever and lock pull.
            mesh.rounded_box((sign*.749,.860,z-.240),(.035,.079,.174),'plastic',.012,1)
            mesh.box((sign*.730,.860,z-.240),(.003,.051,.134),'slot')
            mesh.box((sign*.719,.868,z-.250),(.013,.014,.102),'chrome')
            mesh.box((sign*.744,1.008,z+.345),(.031,.015,.054),'rubber')
            mesh.tube((sign*.744,1.006,z+.345),(sign*.744,1.050,z+.345),.009,'switch',8)
            # Rounded window-crank knob and a recessed lower door pocket.
            crank_y=.677 if z>0 else .587
            crank_z=z-.26 if z>0 else z
            mesh.tube((sign*.719,crank_y,crank_z+.188),(sign*.686,crank_y,crank_z+.188),.023,'rubber',10)
            mesh.box((sign*.751,.502,z-.030),(.025,.071,.470),'slot')
            mesh.rounded_box((sign*.737,.493,z-.030),(.060,.065,.471),'plastic',.016,1)
            # Three broad grille slats remain readable at 480x270.
            for y in (.446,.463,.480):
                mesh.box((sign*.755,y,z+.328),(.014,.006,.158),'vent')
    mark('door_latches_locks_cranks_pockets_and_speakers',start)

    start=len(mesh.f)
    for x in (-.702,.239,.459,.692):
        width=.071 if abs(x)>.6 else .141
        for y in (.895,.907,.919):
            mesh.box((x,y,-.792),(width,.005,.025),'plastic')
    for x in (-.098,.033,.164):
        p=cabin_point((x,.650,-1.016),dash=True)
        mesh.tube((p[0],p[1],p[2]+.003),(p[0],p[1],p[2]+.018),.023,'switch',10)
    mesh.rounded_box((.147,.964,-.804),(.051,.037,.018),'rubber',.008,1)
    mesh.box((.147,.964,-.792),(.018,.020,.005),'button')
    mesh.rounded_box((.487,.766,-.790),(.104,.023,.025),'plastic',.008,1)
    mesh.box((.487,.774,-.776),(.070,.006,.012),'chrome')
    # More legible bellows around the shifter, plus a tucked rear ashtray.
    for y,w in ((.547,.150),(.560,.133),(.573,.115),(.586,.095)):
        mesh.rounded_box((0,y,-.598),(w,.012,w),'boot',.009,1)
    mesh.rounded_box((0,.365,.137),(.127,.087,.049),'plastic',.013,1)
    mesh.box((0,.371,.165),(.090,.048,.012),'slot')
    for x in (-.396,.396):
        for z,depth in ((-.50,.74),(.31,.39)):
            mesh.rounded_box((x,.219,z),(.49,.009,depth),'boot',.003,1)
    mark('dashboard_controls_vents_shifter_and_ashtray',start)

    start=len(mesh.f)
    for sign in (-1,1):
        for z in (.40,.62):
            mesh.rounded_box((sign*.682,1.396,z),(.049,.038,.056),'plastic',.010,1)
        for x in (sign*.166,sign*.535):
            mesh.tube((x,1.400,-.555),(x,1.400,-.523),.011,'plastic',8)
    mesh.rounded_box((0,1.432,.359),(.165,.028,.094),'plastic',.010,1)
    mesh.box((0,1.414,.345),(.119,.005,.055),'light')
    mesh.box((.063,1.411,.363),(.017,.011,.030),'switch')
    mark('grab_mounts_visor_hinges_and_dome_light',start)
    return features


def build_steering(mesh):
    up=Vector((0,.74,-.673));right=Vector((1,0,0));normal=right.cross(up)
    rows=[];count=40;sides=6
    for i in range(count):
        direction=right*math.cos(math.tau*i/count)+up*math.sin(math.tau*i/count)
        rows.append([direction*(.180+.017*math.cos(math.tau*j/sides))+normal*.017*math.sin(math.tau*j/sides) for j in range(sides)])
    for i in range(count):
        for j in range(sides):
            mesh.face([rows[i][j],rows[(i+1)%count][j],rows[(i+1)%count][(j+1)%sides],rows[i][(j+1)%sides]],'rubber',smooth=True)
    for sign in (-1,1):
        mesh.beam(right*(sign*.033),right*(sign*.17)+up*.030,.040,.029,'plastic')
        mesh.beam(right*(sign*.035)-up*.012,up*(-.145)+right*sign*.088,.034,.028,'plastic')
    start=len(mesh.v)
    mesh.rounded_box((0,0,0),(.138,.083,.063),'plastic',.020,2)
    mesh.v[start:]=[right*p[0]+up*p[1]+normal*p[2] for p in mesh.v[start:]]
    mesh.face([right*x+up*y+normal*.037 for x,y in ((-.031,-.026),(.031,-.026),(.031,.026),(-.031,.026))],'steering')
    mesh.tube(-normal*.125,-normal*.046,.035,'plastic',12)
    mesh.tube(right*(-.035)-normal*.081,right*(-.172)+up*.008-normal*.099,.009,'rubber',8)
