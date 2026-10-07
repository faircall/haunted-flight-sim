"""Curved Santana body panels, authored from the supplied side/front references."""
import math
from mathutils import Vector
from g_santana_geometry import (AXLES,WHEEL_Y,REAR_BODY_END,TRUNK_START,CENTER_POST_Z,
                                roof_height,roof_rim,window_panes)


def lerp_keys(value,keys):
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=value<=b:return x+(y-x)*(value-a)/(b-a)
    return keys[0][1] if value<keys[0][0] else keys[-1][1]


def top(z):
    return lerp_keys(z,[(-2.195,.881),(-1.20,1.005),(-.5,1.019),(.7,1.019),(TRUNK_START,1.012),(REAR_BODY_END,1.009)])


def deck_crown(z):
    return .012 if z>=TRUNK_START else .022


def side_x(y,z):
    width=lerp_keys(y,[(.29,.752),(.34,.791),(.43,.823),(.63,.842),(.83,.842),
                      (.878,.846),(.896,.838),(.95,.830),(1.015,.812),(1.05,.800)])
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


def pillar(mesh,a,b,widths,depth,patch):
    """Tapered, rolled sheet-metal pillars rather than straight chamfered bars."""
    a,b=Vector(a),Vector(b);direction=(b-a).normalized()
    right=direction.cross(Vector((0,0,1))).normalized();across=right.cross(direction)
    rows=[]
    for j in range(7):
        t=j/6;w=widths[0]+(widths[1]-widths[0])*t
        # The small bow follows the original glass plane without enlarging it.
        center=a+(b-a)*t+Vector((math.copysign(.004,a.x),0,0))*math.sin(math.pi*t)
        row=[]
        for i in range(12):
            angle=math.tau*i/12;c=math.cos(angle);s=math.sin(angle)
            row.append(center+right*w/2*math.copysign(abs(c)**.45,c)+
                       across*depth/2*math.copysign(abs(s)**.65,s))
        rows.append(row)
    mesh.loft(rows,patch,caps=True,smooth=True)


def glass_pillar(mesh,sign,rear=False,lining=False):
    """A/C pressed panels follow both glazing edges and bury their end returns."""
    panes=window_panes()
    wind=[Vector(p) for p in panes[-1 if rear else 0][0]]
    side=[Vector(p) for p in panes[(2 if rear else 1)+(2 if sign==1 else 0)][0]]
    def outward(points):
        normal=(points[1]-points[0]).cross(points[2]-points[0]).normalized()
        center=sum(points,Vector())/4
        if normal.dot(Vector((center.x,0,center.z)))<0:normal=-normal
        return normal
    wind_normal=outward(wind);side_normal=outward(side)
    # Windshield/back-light and side-light edges determine the actual wrap
    # width. A generic rectangular beam was wider than the space between them.
    wa,wb=(wind[0],wind[3]) if rear==(sign==1) else (wind[1],wind[2])
    sa,sb=(side[1],side[2]) if rear else (side[0],side[3])
    n,m=(3,4) if lining else (8,10);rows=[]
    for j in range(m+1):
        t=-.065+1.165*j/m
        a=wa.lerp(wb,t);b=sa.lerp(sb,t)
        # Small overlaps sit beneath the bevelled rubber window surrounds.
        a.x-=sign*.003;b.z+=-.004 if rear else .004
        outer=[];inner=[]
        for i in range(n+1):
            u=i/n;normal=wind_normal.lerp(side_normal,u).normalized()
            point=a.lerp(b,u)+normal*(.004+.009*math.sin(math.pi*u))
            if rear and t<.12:
                # Roll the quarter section into the deck/shoulder rather than
                # ending it as a separate strut on the beltline.
                weight=((.12-t)/.185)**2;body_y=top(point.z)
                width=side_x(body_y,point.z)
                deck_y=body_y+(deck_crown(point.z)*(1-(point.x/width)**2) if point.z>=TRUNK_START else 0)
                point.y+=(deck_y-.006-point.y)*weight
                root_x=abs(wa.x)+(width-abs(wa.x))*u
                point.x+=(sign*root_x-point.x)*weight
            # The upper return ends inside the roof, with no projecting cap.
            point.y=min(point.y,roof_height(point.x,point.z)-.009)
            if lining:point-=normal*.016
            outer.append(point);inner.append(point-normal*(.006 if lining else .014))
        ring=outer+list(reversed(inner))
        if (sign==1)==rear:ring.reverse()
        rows.append(ring)
    mesh.loft(rows,'liner' if lining else 'paint',caps=True,smooth=True)


def center_pillar(mesh,sign,lining=False):
    """Two complete door-window edges flank a recessed B-post, down into doors."""
    panes=window_panes();front=[Vector(p) for p in panes[1+(2 if sign==1 else 0)][0]]
    rear=[Vector(p) for p in panes[2+(2 if sign==1 else 0)][0]]
    parts=((0,1,'liner'),) if lining else ((0,1,'rubber'),(0,.43,'paint'),(.62,1,'paint'))
    for low,high,patch in parts:
        rows=[];sections=[];m=3 if lining else 4
        for j in range(m+1):
            t=-.070+1.115*j/m;a=front[1].lerp(front[2],t);b=rear[0].lerp(rear[3],t)
            outer=[];inner=[]
            for u0 in (0,.18,.82,1):
                u=low+(high-low)*u0;point=a.lerp(b,u)
                point.x+=sign*(.004+.004*math.sin(math.pi*u0))
                if not lining and patch=='rubber':point.x-=sign*.008
                if point.y<1.015:point.x=sign*(side_x(point.y,point.z)+.002)
                point.y=min(point.y,roof_height(point.x,point.z)-.009)
                if lining:point.x-=sign*.023
                outer.append(point);inner.append(point-Vector((sign*(.008 if lining else .020),0,0)))
            ring=outer+list(reversed(inner))
            if sign==-1:ring.reverse()
            rows.append(ring);sections.append((outer,inner))
        mesh.loft(rows,patch,smooth=True)
        # Quad end returns avoid skinny ear-clipped triangles on straight edges.
        for index,direction in ((0,-1),(-1,1)):
            outer,inner=sections[index]
            for i in range(3):
                points=[outer[i],inner[i],inner[i+1],outer[i+1]]
                if (points[1]-points[0]).cross(points[2]-points[0]).y*direction<0:points.reverse()
                mesh.face(points,patch)


def window_seal(mesh,points):
    """Continuous bevelled rubber surround, overlapping each glazing perimeter."""
    points=[Vector(p) for p in points]
    normal=(points[1]-points[0]).cross(points[2]-points[0]).normalized()
    center=sum(points,Vector())/len(points)
    if normal.dot(Vector((center.x,0,center.z)))<0:
        points.reverse();normal=-normal
    def offset(distance,lift):
        corners=[]
        for i,p in enumerate(points):
            a=(points[i-1]-p).normalized();b=(points[(i+1)%4]-p).normalized()
            corners.append(p-(a+b).normalized()*distance/math.sqrt((1-a.dot(b))/2)+normal*lift)
        return [corners[i].lerp(corners[(i+1)%4],j/2) for i in range(4) for j in range(2)]
    rows=[offset(distance,lift) for distance,lift in ((-.010,.002),(.002,.008),(.014,.002))]
    for a,b in zip(rows,rows[1:]):
        for i in range(len(a)):
            points=[a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]]
            if (points[1]-points[0]).cross(points[2]-points[0]).dot(normal)<0:points.reverse()
            mesh.face(points,'rubber',smooth=True)


def build_roof(shell):
    """One closed crown/header/gutter shell with shared edges at every join."""
    n,m=20,24;top=[];bottom=[]
    edge_x=[(-.737,.676),(CENTER_POST_Z-.058,.728),(CENTER_POST_Z+.056,.728),(.710,.686),(.866,.680)]
    edge_y=[(-.737,1.411),(CENTER_POST_Z-.058,1.423),(CENTER_POST_Z+.056,1.423),(.710,1.403),(.866,1.403)]
    # Lower edge is outside the upper rim: the frame slopes naturally into the
    # glass instead of leaving a projecting, thick roof slab above the pillars.
    for j in range(m+1):
        t=j/m;z0=-.737+1.603*t
        x0=lerp_keys(z0,edge_x);y0=lerp_keys(z0,edge_y)
        top.append([roof_rim(-1+2*i/n,t) for i in range(n+1)])
        header_blend=min(1.,t/.10,(1-t)/.10)
        bottom.append([(x0*u,y0+(roof_height(0,z0)-.014-y0)*(1-u*u)*header_blend,z0)
                       for u in [-1+2*i/n for i in range(n+1)]])
    shell.grid(top,'roof')
    def skirt(a,b):
        rows=[]
        for t in (0,.20,.64,1):
            row=[]
            for pa,pb in zip(a,b):
                x,y,z=Vector(pa).lerp(Vector(pb),t)
                y-=.003*math.sin(math.pi*t)
                row.append((x,y,z))
            rows.append(row)
        return rows
    for sign,index in ((-1,0),(1,-1)):
        shell.grid(skirt([r[index] for r in top],[r[index] for r in bottom]),
                   'paint',reverse=sign==1)
    for index,reverse in ((0,True),(-1,False)):
        shell.grid(skirt(top[index],bottom[index]),'paint',reverse=reverse)
    # The invisible inner sheet closes the volume. Its perimeter is exactly the
    # skirt's bottom edge; the independently detailed cabin supplies the lining.
    perimeter=bottom[0]+[r[-1] for r in bottom[1:]]+list(reversed(bottom[-1][:-1]))+\
              [r[0] for r in reversed(bottom[1:-1])]
    center=Vector((0,roof_height(0,.08)-.014,.08))
    for i,p in enumerate(perimeter):
        shell.face([center,p,perimeter[(i+1)%len(perimeter)]],'paint',smooth=True)


def build_body(shell):
    radius=.407;segments=24;rear_end=REAR_BODY_END
    intervals=[(-2.195,AXLES[0]-radius),(AXLES[0]+radius,AXLES[1]-radius),(AXLES[1]+radius,rear_end)]
    stations=sorted(set([-2.195+i*(rear_end+2.195)/28 for i in range(29)]+
                         [a+radius*math.cos(math.pi*i/segments) for a in AXLES for i in range(segments+1)]))
    for sign in (-1,1):
        def p(y,z):return (sign*side_x(y,z),y,z)
        # Upper shoulder rolls continuously into the hood and trunk.
        rows=[[p(.78+(top(z)-.78)*v,z) for v in (0,.22,.435,.50,.70,.86,1)] for z in stations]
        shell.grid(rows,'doors',reverse=sign==1)
        for za,zb in intervals:
            count=max(5,round((zb-za)*10))
            rows=[[p(y,za+(zb-za)*j/count) for y in (.29,.34,.42,.50,.58,.70,.78)] for j in range(count+1)]
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
                for j,r in enumerate((.355,.361,.374,.390,.402,.407)):
                    y=WHEEL_Y+r*math.sin(a);z=axle+r*math.cos(a)
                    row.append((sign*(side_x(y,z)+(.005,.011,.014,.012,.006,0)[j]),y,z))
                rows.append(row)
            shell.grid(rows,'paint',reverse=sign==-1)
            for i in range(segments):
                a=math.pi*i/segments;b=math.pi*(i+1)/segments
                pa=p(WHEEL_Y+.355*math.sin(a),axle+.355*math.cos(a))
                pb=p(WHEEL_Y+.355*math.sin(b),axle+.355*math.cos(b))
                qa=(sign*.647,pa[1],pa[2]);qb=(sign*.647,pb[1],pb[2])
                points=[pa,qa,qb,pb]
                shell.face(points if sign==1 else list(reversed(points)),'rubber')
                points=[(sign*.642,WHEEL_Y,axle),qa,qb]
                shell.face(list(reversed(points)) if sign==1 else points,'rubber')
        # Door outlines include the sloping front edge and rear arch sweep.
        for track in ([(-1.12,.31),(-1.16,.50),(-1.19,.78),(-1.20,1.006)],
                      [(CENTER_POST_Z,.30),(CENTER_POST_Z,.60),(CENTER_POST_Z,1.019)],
                      [(.617,.39),(.711,.62),(.95,.85),(1.11,1.013)]):
            for (za,ya),(zb,yb) in zip(track,track[1:]):
                points=[(sign*(side_x(y,z)+.002),y,z+d) for y,z,d in
                        ((ya,za,-.003),(yb,zb,-.003),(yb,zb,.003),(ya,za,.003))]
                shell.face(points if sign==1 else list(reversed(points)),'rubber')
        for z in (-.29,.80):
            x=side_x(.918,z)
            shell.rounded_box((sign*(x+.012),.918,z),(.028,.045,.181),'rubber',.013,2)
            shell.rounded_box((sign*(x+.028),.920,z),(.010,.012,.129),'chrome',.004,1)
            shell.tube((sign*(x+.024),.892,z+.059),(sign*(x+.030),.892,z+.059),.010,'chrome',8)
        # Sloping, chamfered pillars and a much shorter greenhouse.
        glass_pillar(shell,sign)
        center_pillar(shell,sign)
        glass_pillar(shell,sign,rear=True)
        for za,zb in ((-1.183,CENTER_POST_Z-.053),(CENTER_POST_Z+.051,1.266)):
            rail(shell,(sign*.829,1.012,za),(sign*.829,1.012,zb),.025,.023,'chrome')
        # Narrow fixed quarter-light divider visible in the reference rear door.
        rear=window_panes()[2+(2 if sign==1 else 0)][0]
        t=(.565-rear[3][2])/(rear[2][2]-rear[3][2])
        upper=Vector(rear[3]).lerp(Vector(rear[2]),t)
        upper.x+=sign*.006
        rail(shell,(sign*.825,1.010,.565),upper,.022,.022,'rubber')
        rail(shell,(sign*.833,1.043,-1.103),(sign*.895,1.058,-1.101),.040,.030,'rubber')
        shell.rounded_box((sign*.910,1.070,-1.10),(.162,.109,.209),'paint',.040,3)
        shell.rounded_box((sign*.910,1.070,-.998),(.141,.088,.020),'rubber',.009,1)
        shell.rounded_box((sign*.910,1.070,-.987),(.126,.075,.012),'glass',.005,2)
        shell.box((sign*(side_x(.761,-1.99)+.007),.761,-1.99),(.010,.034,.074),'amber')
    # Bonnet and boot crowns turn down gently into shaped fenders.
    for za,zb,count,patch in ((-2.195,-1.200,20,'hood'),(TRUNK_START,rear_end,14,'trunk')):
        rows=[]
        for j in range(count+1):
            z=za+(zb-za)*j/count;edge=top(z);width=side_x(edge,z)
            rows.append([(width*u,edge+deck_crown(z)*(1-u*u),z) for u in [-1+2*i/14 for i in range(15)]])
        shell.grid(rows,patch)
        for sign in (-1,1):
            rows=[]
            for j in range(count+1):
                z=za+(zb-za)*j/count;edge=top(z);width=side_x(edge,z)
                rows.append([(sign*width*u,edge+deck_crown(z)*(1-u*u)+.0015,z) for u in (.929,.934)])
            shell.grid(rows,'rubber',reverse=sign==-1)
    # The bonnet/boot crowns turn down over the fascia. These rolled returns
    # close the daylight seams that otherwise show up in the studio preview.
    for z0,z1,z2,low,patch,reverse in ((-2.195,-2.217,-2.235,.818,'hood',True),
                                     (rear_end,rear_end+.023,rear_end+.045,.965,'trunk',False)):
        edge=top(z0);width=side_x(edge,z0);rows=[]
        for t,z in ((0,z0),(.38,z1),(1,z2)):
            rows.append([(width*u*(1-.025*t),edge+(low-edge)*t+deck_crown(z0)*(1-u*u)*(1-t),z)
                         for u in [-1+2*i/14 for i in range(15)]])
        shell.grid(rows,patch,reverse=reverse)
        # Close each rolled corner down to the fascia. Without these faces,
        # the studio background shows through the curved bumper-side join.
        for sign,index in ((-1,0),(1,-1)):
            points=[r[index] for r in rows]+[(sign*.819,.70,z2),(sign*side_x(.70,z0),.70,z0)]
            shell.face(list(reversed(points)) if (sign==1)==reverse else points,patch,smooth=True)
    build_roof(shell)
    for points,_ in window_panes():window_seal(shell,points)
    for z,y,w in ((-1.193,1.010,.800),(TRUNK_START+.002,1.027,.799)):
        rail(shell,(-w,y,z),(w,y,z),.035,.039,'paint')
    shell.box((0,.236,-.20),(1.40,.095,2.86),'rubber')
    # Wrapped fascia and bumper corners, instead of squared stacked blocks.
    shell.rounded_box((0,.688,-2.192),(1.654,.322,.080),'paint',.031,3)
    shell.rounded_box((0,.492,-2.214),(1.754,.200,.179),'bumper',.056,3)
    shell.rounded_box((0,.795,rear_end+.001),(1.656,.357,.081),'trunk',.032,3)
    shell.rounded_box((0,.523,rear_end+.011),(1.749,.210,.184),'bumper',.053,3)
    shell.rounded_box((0,.340,-2.180),(1.625,.130,.080),'paint',.025,2)
    shell.rounded_box((0,.377,rear_end-.025),(1.602,.104,.080),'paint',.025,2)
    shell.panel([(-.41,.789,-2.237),(.41,.789,-2.237),(.41,.603,-2.237),(-.41,.603,-2.237)],'grille')
    shell.panel([(-.200,.562,-2.307),(.200,.562,-2.307),(.200,.448,-2.307),(-.200,.448,-2.307)],'plate')
    shell.panel([(.213,.865,rear_end+.050),(-.213,.865,rear_end+.050),
                 (-.213,.715,rear_end+.050),(.213,.715,rear_end+.050)],'plate')
    for sign in (-1,1):
        x=sign*.615
        shell.rounded_box((x,.701,-2.226),(.399,.210,.031),'rubber',.014,2)
        shell.rounded_box((sign*.587,.495,-2.306),(.208,.060,.020),'amber',.008,2)
        x=sign*.629
        shell.panel([(x+.189,.953,rear_end+.053),(x-.189,.953,rear_end+.053),
                     (x-.189,.749,rear_end+.053),(x+.189,.749,rear_end+.053)],'taillight')
    za,zb=rear_end-.35,rear_end-.15
    shell.panel([(side_x(.872,za)+.003,.872,za),(side_x(.872,zb)+.003,.872,zb),
                 (side_x(.748,zb)+.003,.748,zb),(side_x(.748,za)+.003,.748,za)],'details')
    shell.tube((-.45,.247,rear_end-.15),(-.45,.238,rear_end+.05),.026,'rubber',10)


def build_lamps(lamps):
    for sign in (-1,1):
        x=sign*.615
        lamps.panel([(x-.187,.793,-2.245),(x+.187,.793,-2.245),
                     (x+.187,.610,-2.245),(x-.187,.610,-2.245)],'headlight')
        p=[(sign*.824,.765,-2.183),(sign*.837,.765,-2.025),(sign*.837,.643,-2.025),(sign*.824,.643,-2.183)]
        lamps.panel(p if sign==1 else list(reversed(p)),'amber')
