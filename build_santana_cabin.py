"""Padded upholstery and a lower, shaped dashboard for the revised Santana."""
import math
from mathutils import Vector
from g_santana_geometry import roof_height,cabin_point
from build_santana_body import rail


def cushion(car,center,width,depth,height,n=12,m=8,detailed=False):
    x,y,z=center;rows=[]
    for j in range(m+1):
        v=-1+2*j/m;row=[]
        for i in range(n+1):
            u=-1+2*i/n
            row.append((x+u*width/2*(1-.07*abs(v)**8),
                        y+height/2+.026*(1-u*u)*(1-v*v)+.017*u**6+
                        (.004*math.cos(math.tau*3*u)*(1-v*v)*(1-u*u) if detailed else 0),
                        z+v*depth/2*(1-.10*abs(u)**8)))
        rows.append(row)
    car.grid(rows,'cloth')
    edge=rows[0]+[r[-1] for r in rows[1:]]+list(reversed(rows[-1][:-1]))+[r[0] for r in reversed(rows[1:-1])]
    bottom=[(x+(xx-x)*.91,y-height/2,z+(zz-z)*.91) for xx,yy,zz in edge]
    middle=[(xx,y+height*.10,zz) for xx,yy,zz in edge]
    car.loft([bottom,middle,edge],'seat_side',smooth=True);car.face(bottom,'seat_side')


def backrest(car,x,width,low,high,z0,z1,n=10,m=5,detailed=False):
    # Horizontal superellipse sections give rounded shoulders and side bolsters.
    rows=[]
    for j in range(m+1):
        t=j/m;y=low+(high-low)*t;w=width*(1-.10*t)
        depth=.135*(.80+.20*math.sin(math.pi*t));z=z0+(z1-z0)*t
        row=[]
        count=16 if detailed else 12
        for i in range(count):
            angle=math.tau*i/count;c=math.cos(angle);s=math.sin(angle)
            row.append((x+w/2*math.copysign(abs(c)**.38,c),y,
                        z+depth/2*math.copysign(abs(s)**.60,s)))
        # Ring winds toward -Y, matching Mesh.loft's outward sides.
        rows.append(row)
    car.loft(rows,'seat_side',caps=True,smooth=True)
    for rear in (False,True):
        surface=[]
        for j in range(m+1):
            t=j/m;y=low+.027+(high-low-.054)*t
            w=width*(1-.10*t);z=z0+(z1-z0)*t;depth=.135*(.80+.20*math.sin(math.pi*t))
            row=[]
            for i in range(n+1):
                u=-1+2*i/n
                # Padded centre is slightly dished, with raised shoulder wings.
                padding=.016*math.sin(math.pi*t)**2*(1-u*u) if detailed else 0
                zz=z+(depth/2+.007+.012*u**4+padding)*(1 if rear else -1)
                row.append((x+u*w*.42,y,zz))
            surface.append(row)
        car.grid(surface,'cloth',reverse=rear)


def build_cabin(car,detailed=False):
    def fit(start,dash=False):
        car.v[start:]=[Vector(cabin_point(p,dash)) for p in car.v[start:]]
    car.box((0,.190,.03),(1.55,.05,2.40),'carpet')
    rows=[]
    ceiling=10 if detailed else 8
    for j in range(ceiling+1):
        z=-.63+1.44*j/ceiling;width=.694+.040*math.sin(math.pi*j/ceiling)
        rows.append([(width*u,roof_height(width*u,z)-.052,z) for u in [-1+2*i/ceiling for i in range(ceiling+1)]])
    car.grid(rows,'liner',reverse=True)
    for sign in (-1,1):
        car.box((sign*.792,.691,.07),(.045,.610,2.32),'plastic')
        rail(car,(sign*.804,.996,-1.085),(sign*.804,.996,1.165),.040,.040,'rubber')
        rail(car,(sign*.805,1.004,-1.083),(sign*.690,1.425,-.625),.046,.043,'liner')
        rail(car,(sign*.807,1.011,.074),(sign*.748,1.425,.075),.073,.032,'liner')
        rail(car,(sign*.806,1.015,1.178),(sign*.695,1.408,.806),.080,.053,'liner')
        for z in (-.51,.65):
            x=sign*.765
            p=[(x,.966,z-.49),(x,.966,z+.49),(x,.401,z+.49),(x,.401,z-.49)]
            car.panel(list(reversed(p)) if sign==1 else p,'door')
            car.rounded_box((sign*.735,.733,z-.015),(.101,.054,.378),'plastic',.021,2 if detailed else 1)
            car.box((sign*.753,.859,z-.24),(.024,.064,.140),'rubber')
            car.box((sign*.735,.863,z-.24),(.018,.015,.100),'chrome')
            crank_lift=.090 if detailed and z>0 else 0
            crank_z=z-.26 if detailed and z>0 else z
            car.tube((sign*.745,.631+crank_lift,crank_z+.265),(sign*.723,.591+crank_lift,crank_z+.194),.012,'plastic',8)
            car.tube((sign*.757,.631+crank_lift,crank_z+.265),(sign*.735,.631+crank_lift,crank_z+.265),.022,'plastic',10)
            car.box((sign*.717,.587+crank_lift,crank_z+.188),(.036,.031,.044),'rubber')
        car.tube((sign*.701,1.396,.40),(sign*.701,1.396,.62),.013,'plastic',8)
        car.rounded_box((sign*.350,1.401,-.537),(.44,.024,.18),'liner',.010,2 if detailed else 1)
    start=len(car.v)
    sections=[(-1.382,.859,.884),(-1.265,.973,.871),(-1.10,.953,.852),(-1.02,.805,.833),(-1.10,.598,.792)]
    steps=3 if detailed else 2;across=14 if detailed else 10
    for (za,ya,wa),(zb,yb,wb) in zip(sections,sections[1:]):
        rows=[]
        for j in range(steps+1):
            t=j/steps;z=za+(zb-za)*t;y=ya+(yb-ya)*t;w=wa+(wb-wa)*t
            rows.append([(w*u,y+.012*(1-u*u),z) for u in [-1+2*i/across for i in range(across+1)]])
        car.grid(rows,'plastic')
    for sign in (-1,1):
        p=[(sign*w,y,z) for z,y,w in sections]
        car.face(list(reversed(p)) if sign==-1 else p,'plastic')
    car.rounded_box((-.45,.970,-1.16),(.590,.071,.233),'rubber',.027,2 if detailed else 1)
    car.panel([(-.733,.807,-1.010),(-.167,.807,-1.010),(-.167,.942,-1.010),(-.733,.942,-1.010)],'gauges')
    for x in (-.798,.27,.52,.786):
        width=.105 if abs(x)>.7 else .189
        car.panel([(x-width/2,.866,-1.010),(x+width/2,.866,-1.010),
                   (x+width/2,.922,-1.030),(x-width/2,.922,-1.030)],'vent')
    car.panel([(-.143,.716,-1.000),(.136,.716,-1.000),(.136,.850,-1.000),(-.143,.850,-1.000)],'radio')
    car.panel([(-.143,.622,-1.023),(.136,.622,-1.023),(.136,.709,-1.001),(-.143,.709,-1.001)],'console')
    car.panel([(.219,.641,-1.06),(.767,.641,-1.06),(.767,.841,-1.008),(.219,.841,-1.008)],'glovebox')
    car.box((.553,.727,-1.013),(.12,.015,.018),'chrome')
    fit(start,dash=True)
    start=len(car.v)
    car.rounded_box((0,.441,-.63),(.272,.25,.91),'plastic',.039,2 if detailed else 1)
    car.box((0,.580,-.44),(.256,.025,.295),'rubber')
    for y,r in ((.573,.088),(.596,.072),(.619,.055)):
        car.rounded_box((0,y,-.78),(r*2,.018,r*2),'rubber',.007,2 if detailed else 1)
    car.tube((0,.628,-.78),(0,.766,-.755),.011,'chrome',10)
    car.rounded_box((0,.772,-.755),(.065,.051,.062),'plastic',.020,2 if detailed else 1)
    car.tube((.052,.575,-.425),(.052,.618,-.258),.016,'rubber',10)
    fit(start)
    car.rounded_box((0,1.343,-.604),(.238,.075,.027),'plastic',.012,2 if detailed else 1)
    car.panel([(-.105,1.319,-.585),(.105,1.319,-.585),(.105,1.367,-.585),(-.105,1.367,-.585)],'mirror')
    car.tube((0,1.384,-.612),(0,1.435,-.577),.008,'rubber',8)
    car.box((0,1.438,.36),(.14,.020,.069),'light')
    car.box((0,.998,1.046),(1.47,.040,.235),'carpet')
    start=len(car.v)
    for x in (-.45,.45):
        cushion(car,(x,.503,-.40),.654,.70,.166,n=18 if detailed else 12,m=10 if detailed else 8,detailed=detailed)
        backrest(car,x,.640,.592,1.070,.020,.151,n=14 if detailed else 10,m=8 if detailed else 5,detailed=detailed)
        car.rounded_box((x,1.166,.157),(.357,.206,.151),'seat_side',.052,2 if detailed else 1)
        car.panel([(x-.145,1.090,.238),(x+.145,1.090,.238),(x+.145,1.242,.238),(x-.145,1.242,.238)],'cloth')
        for dx in (-.104,.104):car.tube((x+dx,1.041,.15),(x+dx,1.113,.15),.007,'chrome',8)
        if not detailed:car.box((x+math.copysign(.277,-x),.585,-.025),(.042,.055,.071),'buckle')
    cushion(car,(0,.535,.954),1.66,.625,.187,n=26 if detailed else 20,m=12 if detailed else 8,detailed=detailed)
    backrest(car,0,1.675,.611,1.158,1.23,1.419,n=22 if detailed else 18,m=8 if detailed else 5,detailed=detailed)
    if not detailed:
        for x in (-.54,0,.54):car.box((x,.659,.98),(.044,.033,.067),'buckle')
    for x in (-.54,.54):
        car.rounded_box((x,1.286,1.439),(.346,.178,.145),'seat_side',.045,2 if detailed else 1)
        car.panel([(x-.147,1.351,1.358),(x+.147,1.351,1.358),
                   (x+.147,1.216,1.358),(x-.147,1.216,1.358)],'cloth')
    if not detailed:
        for sign in (-1,1):car.beam((sign*.813,1.385,1.18),(sign*.49,.659,1.15),.031,.010,'rubber')
    fit(start)
