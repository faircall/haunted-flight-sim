"""Curved Santana body panels, authored from the supplied side/front references."""
import math
from mathutils import Vector
from g_santana_geometry import AXLES,WHEEL_Y,roof_height


def lerp_keys(value,keys):
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=value<=b:return x+(y-x)*(value-a)/(b-a)
    return keys[0][1] if value<keys[0][0] else keys[-1][1]


def top(z):
    return lerp_keys(z,[(-2.195,.881),(-1.10,1.005),(-.5,1.019),(.7,1.019),(1.19,1.012),(2.09,.914)])


def side_x(y,z):
    width=lerp_keys(y,[(.29,.752),(.34,.791),(.43,.823),(.63,.842),(.83,.842),(.95,.832),(1.015,.812),(1.05,.800)])
    flare=sum(.032*math.exp(-((z-axle)/.44)**2)*math.exp(-((y-.62)/.24)**2) for axle in AXLES)
    taper=.020*max(0,abs(z+.05)-1.90)/.35
    return width+flare-taper


def rail(mesh,a,b,width,depth,patch):
    a,b=Vector(a),Vector(b);direction=(b-a).normalized();right=direction.cross(Vector((0,0,1)))
    if right.length<.01:right=direction.cross(Vector((1,0,0)))
    right.normalize();across=right.cross(direction)
    ring=[(-.35,-.5),(.35,-.5),(.5,-.35),(.5,.35),(.35,.5),(-.35,.5),(-.5,.35),(-.5,-.35)]
    rows=[[a+(b-a)*t+(right*x*width+across*z*depth)*scale for x,z in ring]
          for t,scale in ((0,.88),(.045,1),(.955,1),(1,.88))]
    mesh.loft(rows,patch,caps=True,smooth=True)


def build_body(shell):
    radius=.407;segments=16
    intervals=[(-2.195,AXLES[0]-radius),(AXLES[0]+radius,AXLES[1]-radius),(AXLES[1]+radius,2.09)]
    stations=sorted(set([-2.195+i*4.285/24 for i in range(25)]+
                         [a+radius*math.cos(math.pi*i/segments) for a in AXLES for i in range(segments+1)]))
    for sign in (-1,1):
        def p(y,z):return (sign*side_x(y,z),y,z)
        # Upper shoulder rolls continuously into the hood and trunk.
        rows=[[p(.78+(top(z)-.78)*v/4,z) for v in range(5)] for z in stations]
        shell.grid(rows,'doors',reverse=sign==1)
        for za,zb in intervals:
            count=max(5,round((zb-za)*8))
            rows=[[p(y,za+(zb-za)*j/count) for y in (.29,.34,.44,.58,.70,.78)] for j in range(count+1)]
            shell.grid(rows,'doors',reverse=sign==1)
            # Narrow rubbing strip follows the curved panel instead of floating.
            rows=[[(sign*(side_x(y,za+(zb-za)*j/count)+.004),y,za+(zb-za)*j/count)
                   for y in (.578,.613)] for j in range(count+1)]
            shell.grid(rows,'bumper',reverse=sign==1)
        for axle in AXLES:
            rows=[]
            for i in range(segments+1):
                a=math.pi*i/segments;z=axle+radius*math.cos(a);y=WHEEL_Y+radius*math.sin(a)
                rows.append([p(y+(.78-y)*t/3,z) for t in range(4)])
            shell.grid(rows,'paint',reverse=sign==-1)
            # Rolled painted lip, with the outer curve swelling over the tyre.
            rows=[]
            for i in range(segments+1):
                a=math.pi*i/segments;row=[]
                for j,r in enumerate((.383,.391,.400,.407)):
                    y=WHEEL_Y+r*math.sin(a);z=axle+r*math.cos(a)
                    row.append((sign*(side_x(y,z)+(.005,.014,.010,0)[j]),y,z))
                rows.append(row)
            shell.grid(rows,'paint',reverse=sign==-1)
            for i in range(segments):
                a=math.pi*i/segments;b=math.pi*(i+1)/segments
                pa=p(WHEEL_Y+.383*math.sin(a),axle+.383*math.cos(a))
                pb=p(WHEEL_Y+.383*math.sin(b),axle+.383*math.cos(b))
                qa=(sign*.647,pa[1],pa[2]);qb=(sign*.647,pb[1],pb[2])
                points=[pa,qa,qb,pb]
                shell.face(points if sign==1 else list(reversed(points)),'rubber')
                points=[(sign*.642,WHEEL_Y,axle),qa,qb]
                shell.face(list(reversed(points)) if sign==1 else points,'rubber')
        # Door outlines include the sloping front edge and rear arch sweep.
        for track in ([(-.92,.31),(-.96,.48),(-1.02,.74),(-1.10,1.006)],
                      [(.075,.30),(.075,.60),(.075,1.019)],
                      [(.826,.39),(.91,.62),(1.03,.85),(1.16,1.013)]):
            for (za,ya),(zb,yb) in zip(track,track[1:]):
                points=[(sign*(side_x(y,z)+.002),y,z+d) for y,z,d in
                        ((ya,za,-.003),(yb,zb,-.003),(yb,zb,.003),(ya,za,.003))]
                shell.face(points if sign==1 else list(reversed(points)),'rubber')
        for z in (-.12,.70):
            x=side_x(.918,z)
            shell.rounded_box((sign*(x+.012),.918,z),(.028,.045,.181),'rubber',.013,1)
            shell.box((sign*(x+.028),.920,z),(.010,.012,.129),'chrome')
        # Sloping, chamfered pillars and a much shorter greenhouse.
        rail(shell,(sign*.837,1.014,-1.099),(sign*.708,1.436,-.626),.066,.059,'paint')
        rail(shell,(sign*.837,1.022,.073),(sign*.772,1.440,.075),.086,.041,'rubber')
        rail(shell,(sign*.830,1.029,1.196),(sign*.717,1.422,.812),.161,.065,'paint')
        for za,zb in ((-1.083,.022),(.126,1.166)):
            rail(shell,(sign*.829,1.012,za),(sign*.829,1.012,zb),.025,.023,'chrome')
        roof_band=[]
        for j in range(13):
            z=-.650+1.488*j/12;width=.718+.056*math.sin(math.pi*j/12)
            y=roof_height(width,z)
            roof_band.append([(sign*width,y-.053,z),(sign*(width+.009),y-.022,z),(sign*width,y,z)])
        shell.grid(roof_band,'paint',reverse=sign==1)
        rail(shell,(sign*.833,1.043,-1.013),(sign*.895,1.058,-1.011),.040,.030,'rubber')
        shell.rounded_box((sign*.910,1.070,-1.01),(.162,.109,.209),'paint',.034,2)
        shell.rounded_box((sign*.910,1.070,-.897),(.126,.075,.012),'glass',.005,1)
        shell.box((sign*(side_x(.761,-1.99)+.007),.761,-1.99),(.010,.034,.074),'amber')
    # Bonnet and boot crowns turn down gently into shaped fenders.
    for za,zb,count,patch in ((-2.195,-1.100,16,'hood'),(1.194,2.09,10,'trunk')):
        rows=[]
        for j in range(count+1):
            z=za+(zb-za)*j/count;edge=top(z);width=side_x(edge,z)
            rows.append([(width*u,edge+.030*(1-u*u),z) for u in [-1+2*i/10 for i in range(11)]])
        shell.grid(rows,patch)
        for sign in (-1,1):
            rows=[]
            for j in range(count+1):
                z=za+(zb-za)*j/count;edge=top(z);width=side_x(edge,z)
                rows.append([(sign*width*u,edge+.030*(1-u*u)+.0015,z) for u in (.929,.934)])
            shell.grid(rows,'rubber',reverse=sign==-1)
    # The bonnet/boot crowns turn down over the fascia. These rolled returns
    # close the daylight seams that otherwise show up in the studio preview.
    for z0,z1,z2,low,patch,reverse in ((-2.195,-2.217,-2.235,.818,'hood',True),
                                     (2.09,2.113,2.135,.845,'trunk',False)):
        edge=top(z0);width=side_x(edge,z0);rows=[]
        for t,z in ((0,z0),(.38,z1),(1,z2)):
            rows.append([(width*u*(1-.025*t),edge+(low-edge)*t+.030*(1-u*u)*(1-t),z)
                         for u in [-1+2*i/10 for i in range(11)]])
        shell.grid(rows,patch,reverse=reverse)
        # Close each rolled corner down to the fascia. Without these faces,
        # the studio background shows through the curved bumper-side join.
        for sign,index in ((-1,0),(1,-1)):
            points=[r[index] for r in rows]+[(sign*.819,.70,z2),(sign*side_x(.70,z0),.70,z0)]
            shell.face(list(reversed(points)) if (sign==1)==reverse else points,patch,smooth=True)
    roof=[]
    for j in range(17):
        z=-.663+1.508*j/16;width=.718+.056*math.sin(math.pi*j/16)
        roof.append([(width*u,roof_height(width*u,z),z) for u in [-1+2*i/12 for i in range(13)]])
    shell.grid(roof,'roof')
    for z,y,w in ((-.618,1.443,.705),(.807,1.431,.711)):
        rail(shell,(-w,y,z),(w,y,z),.066,.049,'paint')
    for z,y,w in ((-1.093,1.010,.800),(1.196,1.027,.799)):
        rail(shell,(-w,y,z),(w,y,z),.035,.039,'paint')
    shell.box((0,.236,-.20),(1.40,.095,2.86),'rubber')
    # Wrapped fascia and bumper corners, instead of squared stacked blocks.
    shell.rounded_box((0,.688,-2.192),(1.654,.322,.080),'paint',.031,2)
    shell.rounded_box((0,.434,-2.214),(1.754,.188,.179),'bumper',.056,2)
    shell.rounded_box((0,.683,2.091),(1.656,.369,.081),'trunk',.032,2)
    shell.rounded_box((0,.421,2.101),(1.749,.175,.184),'bumper',.053,2)
    shell.panel([(-.41,.789,-2.237),(.41,.789,-2.237),(.41,.603,-2.237),(-.41,.603,-2.237)],'grille')
    shell.panel([(-.200,.517,-2.307),(.200,.517,-2.307),(.200,.403,-2.307),(-.200,.403,-2.307)],'plate')
    shell.panel([(.213,.792,2.140),(-.213,.792,2.140),(-.213,.650,2.140),(.213,.650,2.140)],'plate')
    for sign in (-1,1):
        x=sign*.615
        shell.rounded_box((x,.701,-2.226),(.399,.210,.031),'rubber',.014,1)
        shell.rounded_box((sign*.587,.443,-2.306),(.208,.060,.020),'amber',.008,1)
        x=sign*.629
        shell.panel([(x+.189,.843,2.143),(x-.189,.843,2.143),(x-.189,.659,2.143),(x+.189,.659,2.143)],'taillight')
    shell.panel([(side_x(.872,1.74)+.003,.872,1.74),(side_x(.872,1.94)+.003,.872,1.94),
                 (side_x(.748,1.94)+.003,.748,1.94),(side_x(.748,1.74)+.003,.748,1.74)],'details')
    shell.tube((-.45,.247,1.94),(-.45,.238,2.14),.026,'rubber',10)


def build_lamps(lamps):
    for sign in (-1,1):
        x=sign*.615
        lamps.panel([(x-.187,.793,-2.245),(x+.187,.793,-2.245),
                     (x+.187,.610,-2.245),(x-.187,.610,-2.245)],'headlight')
        p=[(sign*.824,.765,-2.183),(sign*.837,.765,-2.025),(sign*.837,.643,-2.025),(sign*.824,.643,-2.183)]
        lamps.panel(p if sign==1 else list(reversed(p)),'amber')
