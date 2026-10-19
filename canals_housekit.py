"""Hollow Jiangnan houses for the second Void Canals art pass.

The front of a house is local -Z. No surface is placed behind a window to fake
darkness: apertures open into full-depth rooms, with separate interior/soffit
meshes so the renderer can give sheltered surfaces their appropriate exposure.
"""
import math
import random
from temple_interior_mesh import Mesh
from canals_house_plan import house_ground_plan

KEYS=('canal_masonry','canal_plaster','canal_timber','canal_windows',
      'canal_roofs','canal_details','canal_interiors','canal_shadow','canal_recess')


def build_house(meshes,spec):
    """Append one independently seeded house; return world-space opening probes.

    Required spec: cx, cz, width, depth. Optional yaw, floors, height (eave above
    base), seed, variant, detail, base_y, porch, laundry. A positive yaw turns
    local -Z towards world +X, so west-bank houses face the canal at +pi/2.
    """
    seed=int(spec.get('seed',0));rr=random.Random(seed)
    w=float(spec['width']);d=float(spec['depth']);cx=float(spec['cx']);cz=float(spec['cz'])
    base=float(spec.get('base_y',.325));yaw=float(spec.get('yaw',0.))
    levels=max(1,min(2,int(spec.get('floors',2))));height=float(spec.get('height',2.8*levels))
    detail=int(spec.get('detail',2));variant=spec.get('variant','plaster')
    variants=('plaster','timber_gallery','shopfront','gable','arcade','corner')
    if variant not in variants:variant=variants[seed%len(variants)]
    ground_plan=house_ground_plan(dict(spec,variant=variant))
    porch=ground_plan['porch']
    floor_h=height/levels;front=-d/2;back=d/2;thick=.25
    copies={k:Mesh('house_work_'+k,meshes[k].material,meshes[k].tiles) for k in KEYS}
    stone,wall,wood,lattice,roofs,props,inside,shade,recess_mesh=[copies[k] for k in KEYS]
    opening_probes=[];floor_bounds=[];porch_posts=[];gable_probes=[];wall_top_edges=[];porous_panels=0;folded_leaves=0;missing_tiles=0;door_portals=[];rear_portals=[]
    enterable=bool(spec.get('enterable',False))
    decay=spec.get('decay',('intact','neglected','ruin')[seed%3])
    decay={'intact':0,'neglected':1,'ruin':2}.get(decay,decay)
    decay=max(0,min(2,int(decay)))
    water_y=float(spec.get('water_y',-1.55))
    foundation_bottom=min(float(spec.get('foundation_bottom',-2.2)),water_y-.70)
    upper_setback=float(spec.get('upper_front',spec.get('upper_setback',.65+.15*(seed%3))))
    upper_left=float(spec.get('upper_left',w*(.10+.025*(seed%3))))
    upper_right=float(spec.get('upper_right',w*(.10+.025*((seed+1)%3))))
    upper_back=float(spec.get('upper_back',.35+.15*(seed%3)))
    # The second floor is an independently smaller occupied volume. Its walls,
    # floor, ceiling, gables and roof share these actual bounds; the shoulders
    # left on the lower storey receive low weathered lean-to roofs.
    upper=(-w/2+upper_left,w/2-upper_right,front+upper_setback,back-upper_back)
    if upper[1]-upper[0]<2.3 or upper[3]-upper[2]<2.3:
        upper=(-w*.32,w*.32,front+min(.65,d*.15),back-min(.35,d*.08))
    top_bounds=upper if levels>1 else (-w/2,w/2,front,back)
    sy,cy=math.sin(yaw),math.cos(yaw)

    def warp(p):
        x,y,z=p;t=max(0.,min(1.,y/max(1.,height)))
        return (x+.14*z/d+.15*math.sin(seed*.8)*t+.035*math.sin(y*.9)*t,
                y+(.024*math.sin(x*.86+z*.61+seed) if y>.4 else 0.),
                z+.12*x/w+.12*math.cos(seed*.6)*t+.025*math.sin(y*.61)*t)
    def world(p):
        x,y,z=warp(p);return(cx+cy*x-sy*z,base+y,cz+sy*x+cy*z)
    def normal(n):
        # Inverse-transpose of the coherent ground shear, then yaw. Navigation
        # probes use this exact outward direction rather than an unwarped axis.
        xx=n[0]-.12/w*n[2];zz=n[2]-.14/d*n[0]
        length=math.sqrt(xx*xx+n[1]*n[1]+zz*zz)
        return((cy*xx-sy*zz)/length,n[1]/length,(sy*xx+cy*zz)/length)
    def face_up(mesh,pts,tile):
        p=list(pts)
        # Signed y component of cross product.
        a,b,c=p[:3]
        ny=(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2])
        if ny<0:p.reverse()
        mesh.face(p,tile)
    def slab(mesh,x0,x1,z0,z1,y,tile='wood',thickness=.13):
        mesh.box(((x0+x1)/2,y-thickness/2,(z0+z1)/2),(x1-x0,thickness,z1-z0),tile)
    def bent_beam(mesh,a,b,width,depth,tile='wood'):
        mesh.beam(a,b,width,depth,tile)
    def stone_block(center,size,tile='stone',rough=.018):
        x,y,z=center;sx,sy_,sz=[v/2 for v in size]
        verts=[]
        for a,b,c in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
            verts.append((x+a*sx+rr.uniform(-rough,rough),y+b*sy_+rr.uniform(-rough*.6,rough*.6),z+c*sz+rr.uniform(-rough,rough)))
        for ids in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            stone.face([verts[i] for i in ids],tile)

    # The foundation is a continuous perimeter, not a filled house. Independently
    # laid stones cover it in short, irregular courses rather than a tiled cube.
    perimeter=((-w/2,front),(w/2,front),(w/2,back),(-w/2,back))
    for a,b in zip(perimeter,perimeter[1:]+perimeter[:1]):
        bottom=foundation_bottom-base
        # X/Z perimeter is counter-clockwise: its exterior lies to the right
        # of each edge. Top-first winding points the backing out towards the
        # water; bottom-first faces were culled between the individual stones.
        stone.face(((a[0],.025,a[1]),(b[0],.025,b[1]),(b[0],bottom,b[1]),(a[0],bottom,a[1])),'wetstone')
        if detail<1:continue
        dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);dx/=length;dz/=length
        # Wet, broad lowest courses transition into smaller hand-laid dry
        # stones. The irregular joints are backed by the continuous perimeter.
        course_count=max(5,math.ceil((-bottom+.025)/.30))
        course_height=(-bottom+.025)/course_count
        for row in range(course_count):
            lo=bottom+row*course_height;start=-.25 if row%2 else 0.
            while start<length:
                end=min(length,start+rr.uniform(.50,1.00));aa=max(0.,start);bb=end
                if bb-aa>.08:
                    t=(aa+bb)/2;x=a[0]+dx*t;z=a[1]+dz*t
                    wet=base+lo+course_height*.5<water_y+.36
                    blockdepth=rr.uniform(.22,.37)
                    stone_block((x,lo+course_height*.5,z),((bb-aa-.025) if abs(dx)>.5 else blockdepth,course_height-.018,(bb-aa-.025) if abs(dz)>.5 else blockdepth),'wetstone' if wet else 'stone',.028)
                start=end

    def wall_with_openings(a,b,y0,y1,holes,tile='plaster',sheltered=False):
        """A thick wall cut into actual cells around apertures; no backing card."""
        surface_mesh=recess_mesh if sheltered else wall
        ax,az=a;bx,bz=b;length=math.hypot(bx-ax,bz-az);dx,dz=(bx-ax)/length,(bz-az)/length
        nx,nz=-dz,dx
        def p(t,y,depth=0):return(ax+dx*t+nx*depth,y,az+dz*t+nz*depth)
        us=sorted(set([0.,length]+[max(0.,min(length,h[k])) for h in holes for k in ('u0','u1')]))
        ys=sorted(set([y0,y1]+[max(y0,min(y1,h[k])) for h in holes for k in ('y0','y1')]))
        if detail>0 and decay and tile=='plaster':
            # Coherent courses permit broad flaking patches with irregular
            # edges. They never cut a random hole through a solid room wall.
            us=sorted(set(us+[length*i/max(1,math.ceil(length/.70)) for i in range(1,max(1,math.ceil(length/.70)))]))
            ys=sorted(set(ys+[y0+(y1-y0)*i/max(1,math.ceil((y1-y0)/.38)) for i in range(1,max(1,math.ceil((y1-y0)/.38)))]))
        if abs(y1-height)<1e-7:wall_top_edges.append([p(u,y1) for u in us])
        for u0,u1 in zip(us,us[1:]):
            for ya,yb in zip(ys,ys[1:]):
                if u1-u0<.005 or yb-ya<.005:continue
                u=(u0+u1)/2;y=(ya+yb)/2
                if any(h['u0']<u<h['u1'] and h['y0']<y<h['y1'] for h in holes):continue
                pts=(p(u0,ya),p(u1,ya),p(u1,yb),p(u0,yb))
                # Small plaster subdivisions hold the irregular, hand-finished
                # silhouette while coherent warp keeps adjoining panels closed.
                weather=math.sin(u*.92+seed*.7)+.63*math.cos(y*1.71+seed*.27)+.42*math.sin(u*1.8+y*1.1)
                chipped=tile=='plaster' and decay and (weather>(1.05 if decay==1 else .45) or (y-y0<.34 and weather>-.1))
                surface_mesh.face(pts,'wetstone' if chipped else tile)
                if chipped and detail>0:
                    # Broken surviving plaster has a shallow raised edge over
                    # visible masonry; no decal lies on the same depth plane.
                    if weather<1.5:
                        du=u1-u0;dy=yb-ya
                        surface_mesh.face((p(u0+.02,ya+.02,.014),p(u1-.025,ya+.035,.014),p(u1-.06,yb-dy*.26,.014),p(u0+du*.54,yb-dy*.12,.014),p(u0+.035,yb-dy*.38,.014)),'plaster')
                    if yb-ya>.12 and u1-u0>.20:
                        for jy in range(max(1,int((yb-ya)/.14))):
                            yy=ya+.035+jy*.14
                            if yy>=yb-.03:continue
                            stone.beam(p(u0+.02,yy,.024),p(u1-.02,yy,.024),.014,.016,'stone')
                inside.face((p(u1,ya,-thick),p(u0,ya,-thick),p(u0,yb,-thick),p(u1,yb,-thick)),'wood' if tile=='wood' else 'plaster')
        # Outer wall ends and true masonry thickness in every opening.
        for u in (0.,length):surface_mesh.face((p(u,y0),p(u,y1),p(u,y1,-thick),p(u,y0,-thick)),tile)
        surface_mesh.face((p(0,y1),p(length,y1),p(length,y1,-thick),p(0,y1,-thick)),tile)
        for h in holes:
            u0,u1=h['u0'],h['u1'];ya,yb=h['y0'],h['y1']
            for u in (u0,u1):shade.face((p(u,ya),p(u,yb),p(u,yb,-thick),p(u,ya,-thick)),'wood')
            shade.face((p(u0,yb),p(u1,yb),p(u1,yb,-thick),p(u0,yb,-thick)),'wood')
            face_up(stone if h.get('kind')=='door' else wood,(p(u0,ya),p(u1,ya),p(u1,ya,-thick),p(u0,ya,-thick)),'stone' if h.get('kind')=='door' else 'wood')
            for u in (u0,u1):wood.beam(p(u,ya,.012),p(u,yb,.012),.085,.115,'wood')
            wood.beam(p(u0,yb,.015),p(u1,yb,.015),.12,.15,'wood')
            if h.get('kind')!='door':wood.beam(p(u0,ya,.018),p(u1,ya,.018),.11,.14,'wood')
            center=p((u0+u1)/2,(ya+yb)/2)
            opening_probes.append(dict(center=world(center),normal=normal((nx,0,nz)),clear_width=u1-u0,clear_height=yb-ya,wall_thickness=thick,room_depth=h.get('room_depth',d-porch-thick),kind=h.get('kind','window'),covered=h.get('covered',False),room_floor=base+h.get('floor',0.),room_ceiling=base+h.get('ceiling',floor_h),local_center=center))
        return p

    def rail(x0,x1,z,y,height=.78,pattern=0):
        for yy in (.13,height):wood.beam((x0,y+yy,z),(x1,y+yy,z),.07,.08,'wood')
        count=max(2,math.ceil((x1-x0)/.58))
        for i in range(count+1):
            x=x0+(x1-x0)*i/count;wood.beam((x,y+.08,z),(x+.015*math.sin(i),y+height,z),.045,.055,'wood')
        if pattern:
            for i in range(count):
                xa=x0+(x1-x0)*i/count;xb=x0+(x1-x0)*(i+1)/count
                wood.beam((xa,y+.16,z),(xb,y+height-.08,z),.032,.045,'wood')
                wood.beam((xa,y+height-.08,z),(xb,y+.16,z),.032,.045,'wood')

    def porous_screen(x0,x1,z,y0,y1,mode=0,hinge_angle=0.,hinge_right=False):
        """An open wooden screen: thin bars surround empty polygonal cells."""
        nonlocal porous_panels
        porous_panels+=1
        pivot=x1 if hinge_right else x0;ca,sa=math.cos(hinge_angle),math.sin(hinge_angle)
        def p(x,y):return(pivot+(x-pivot)*ca,y,z+(x-pivot)*sa)
        def bar(a,b,ww=.025):lattice.beam(p(*a),p(*b),ww,.038,'wood')
        for x in (x0,x1):bar((x,y0),(x,y1),.045)
        for y in (y0,y1):bar((x0,y),(x1,y),.05)
        cols=max(2,round((x1-x0)/.30));rows=max(3,round((y1-y0)/.35))
        if mode%3==0:
            # Loose rectangular meander: alternating interrupted grids leave
            # large voids and intentional asymmetry, not a modern window grid.
            for i in range(cols):
                xa=x0+(x1-x0)*(i+.13)/cols;xb=x0+(x1-x0)*(i+.87)/cols
                for j in range(rows):
                    ya=y0+(y1-y0)*(j+.13)/rows;yb=y0+(y1-y0)*(j+.87)/rows
                    if (i+j+seed)%11==0:continue
                    for a,b in (((xa,ya),(xb,ya)),((xb,ya),(xb,yb)),((xb,yb),(xa,yb)),((xa,yb),(xa,ya))):bar(a,b)
                    if j<rows-1:bar((xa if (i+j)%2 else xb,yb),(xa if (i+j)%2 else xb,y0+(y1-y0)*(j+1.13)/rows))
            for i in range(1,cols):bar((x0+(x1-x0)*i/cols,y0),(x0+(x1-x0)*i/cols,y1),.021)
        elif mode%3==1:
            # Diamond lattice with clipped boundary intersections.
            step=(x1-x0)/cols
            for slope in (-1,1):
                start=x0-(y1-y0) if slope==1 else x0
                end=x1 if slope==1 else x1+(y1-y0)
                for j in range(math.ceil((end-start)/step)+1):
                    x=start+j*step
                    candidates=[]
                    for yy in (y0,y1):
                        xx=x+slope*(yy-y0)
                        if x0-1e-6<=xx<=x1+1e-6:candidates.append((xx,yy))
                    for xx in (x0,x1):
                        yy=y0+(xx-x)/slope
                        if y0-1e-6<=yy<=y1+1e-6:candidates.append((xx,yy))
                    if len(candidates)>=2 and math.dist(candidates[0],candidates[-1])>.02:bar(candidates[0],candidates[-1],.021)
        else:
            for i in range(1,cols*2):
                if i%7==seed%7:continue
                x=x0+(x1-x0)*i/(cols*2);bar((x,y0),(x,y1),.025)
            for y in (y0+.26,y1-.25):bar((x0,y),(x1,y),.035)

    def shutter(x,z,y0,y1,width,angle,broken=False,screen=False):
        """A folded leaf in real space; the opening behind it remains empty."""
        nonlocal folded_leaves
        folded_leaves+=1;ca,sa=math.cos(angle),math.sin(angle)
        def p(t,y,offset=0):return(x+ca*t-sa*offset,y,z+sa*t+ca*offset)
        if screen:
            porous_screen(min(x,x+width),max(x,x+width),z,y0,y1,seed%3,angle,width<0);return
        n=max(3,round(abs(width)/.16))
        for i in range(n):
            if broken and i==n//2:continue
            a=width*i/n;b=width*(i+1)/n
            low=y0+(.35 if broken and i==n//2+1 else 0)
            lattice.face((p(a+.004,low),p(b-.004,low),p(b-.004,y1),p(a+.004,y1)),'wood')
            lattice.face((p(a+.004,y1,-.035),p(b-.004,y1,-.035),p(b-.004,low,-.035),p(a+.004,low,-.035)),'wood')
        for yy in (y0+.25,y1-.25):wood.beam(p(.015,yy,-.03),p(width-.015,yy,-.03),.055,.07,'wood')
        for t in (0,width):wood.beam(p(t,y0),p(t,y1),.045,.07,'wood')

    # Wide asymmetrical doors, porch bays, and continuous upper galleries replace
    # the rejected equally spaced grid of little square windows.
    for level in range(levels):
        y=level*floor_h;ceil=y+floor_h-.18
        left,right,outer_front,room_back=upper if level else (-w/2,w/2,front,back)
        bw=right-left;bd=room_back-outer_front;mid=(left+right)/2
        recess=porch if level==0 else min(.75,porch*.65)
        z=outer_front+recess
        # Separate shells at each storey: no full-height lower sidewall remains
        # to make the smaller upper room look like a recess inside a large box.
        rearholes=[]
        if level==0 and ground_plan['rear_access']:
            for x0,x1 in ground_plan['rear_door_ranges']:
                ya=ground_plan['threshold'];yb=min(ceil,2.37)
                rearholes.append(dict(u0=x0-left,u1=x1-left,y0=ya,y1=yb,kind='door',covered=False,room_depth=room_back-z-thick,floor=y,ceiling=ceil))
                # The kit owns only the doorway throat. The district owns the
                # full rear landing, so it can union its paving with an angled
                # stair flight and the back quay without coplanar intersections.
                slab(shade,x0,x1,room_back-.23,room_back+.04,y,'wetstone',.14)
                nt=normal((0,0,1));tangent=(-nt[2],0,nt[0]);xx=(x0+x1)/2
                rear_portals.append(dict(side='rear',center=world((xx,(ya+yb)/2,room_back)),normal=nt,tangent=tangent,local_range=[x0,x1],local_z=room_back,clear_width=x1-x0,clear_height=yb-ya,floor=base+y,floor_y=base+y,threshold=base+ya,enterable=enterable,accessible=enterable,approach=world((xx,y,room_back+.60)),inside=world((xx,y,room_back-.80)),landing_bounds=ground_plan['rear_landing_bounds']))
        elif detail>0 and (seed+level)%3==0:
            rearholes=[dict(u0=bw*.32,u1=bw*.32+.58,y0=y+.95,y1=min(ceil,y+1.74),kind='window',covered=False,room_depth=bd-recess, floor=y,ceiling=ceil)]
        wall_with_openings((left,room_back),(right,room_back),y,y+floor_h,rearholes)
        for side,x in ((-1,left),(1,right)):
            a=(x,outer_front);b=(x,room_back)
            if side>0:a,b=b,a
            sideholes=[]
            if variant in ('plaster','corner','gable'):
                u=bd*.60 if side<0 else bd*.24
                sideholes.append(dict(u0=u,u1=min(bd-.2,u+.64),y0=y+.95,y1=min(ceil,y+1.95),kind='window',covered=False,room_depth=bw-.5,floor=y,ceiling=ceil))
            wall_with_openings(a,b,y,y+floor_h,sideholes)
        floor_bounds.append(dict(y=base+y,ceiling=base+ceil,local=[left+.28,z+thick,right-.28,room_back-thick],world_corners=[world((xx,y,zz)) for xx,zz in ((left+.28,z+thick),(right-.28,z+thick),(right-.28,room_back-thick),(left+.28,room_back-thick))],porch_local=[left+.28,outer_front+.16,right-.28,z],porch_world=[world((xx,y,zz)) for xx,zz in ((left+.28,outer_front+.16),(right-.28,outer_front+.16),(right-.28,z),(left+.28,z))]))
        # A small overlap with the .25m inner wall closes the old .01m light
        # slit. The slab remains .23m from the exterior face, so its dark edge
        # cannot protrude through the plaster as the earliest full-width slabs
        # did. The rear doorway throat starts at this same back edge.
        # The district clips its quay against a .025m expanded house footprint.
        # Extend only the open ground porch to that same boundary; otherwise a
        # walkable 25mm crack exposes the foundation instead of a floor surface.
        porch_floor_front=outer_front-.025 if level==0 else outer_front
        slab(shade,left+.23,right-.23,porch_floor_front,z,y,'wood' if level else 'wetstone',.14)
        slab(inside,left+.23,right-.23,z,room_back-.23,y,'wood' if level else 'wetstone',.14)
        # Whole-room ceiling is well behind the visible facade. The open porch
        # has a separately dark soffit whose edge follows the actual roof.
        shade.box((mid,ceil+.06,(z+room_back-.23)/2),(bw-.46,.12,room_back-z-.23),'wood')
        if level==0:
            holes=[dict(u0=right-x1,u1=right-x0,y0=ground_plan['threshold'],y1=min(ceil,y+2.37),kind='door',covered=False,floor=y,ceiling=ceil,room_depth=room_back-z-thick) for x0,x1 in ground_plan['door_ranges']]
            panelmaterial='wood' if variant=='timber_gallery' else 'plaster'
            if len(holes)==1:
                # The small unglazed squint sits in the largest remaining pier.
                dx0,dx1=ground_plan['door_ranges'][0]
                candidates=((left+.25,dx0-.22),(dx1+.22,right-.25))
                a,b=max(candidates,key=lambda q:q[1]-q[0])
                if b-a>.58:
                    wx=(a+b)/2;ww=min(.85,b-a-.08)
                    holes.append(dict(u0=right-wx-ww/2,u1=right-wx+ww/2,y0=y+1.0,y1=min(ceil-.08,y+1.98),kind='window',covered=False,floor=y,ceiling=ceil,room_depth=room_back-z-thick))
        else:
            if variant in ('timber_gallery','shopfront','arcade','corner'):
                holes=[dict(u0=.24,u1=bw-.24,y0=y+.62,y1=ceil-.08,kind='gallery',covered=True,floor=y,ceiling=ceil,room_depth=room_back-z-thick)]
                panelmaterial='wood'
            else:
                holes=[dict(u0=bw*.13,u1=bw*.86,y0=y+.67,y1=ceil-.12,kind='window',covered=True,floor=y,ceiling=ceil,room_depth=room_back-z-thick)]
                panelmaterial='plaster'
        p=wall_with_openings((right,z),(left,z),y,ceil+.12,holes,panelmaterial,True)
        for h in holes:
            # Wall u runs right-to-left, unlike the convenient front x coordinate.
            x0=right-h['u1'];x1=right-h['u0'];hh=h['y1']-h['y0'];ww=x1-x0
            if h['kind']=='door':
                nt=normal((0,0,-1));tangent=(-nt[2],0,nt[0])
                door_portals.append(dict(side='front',center=world(((x0+x1)/2,(h['y0']+h['y1'])/2,z)),normal=nt,tangent=tangent,local_range=[x0,x1],local_z=z,clear_width=ww,clear_height=hh,floor=base+y,floor_y=base+y,threshold=base+h['y0'],enterable=enterable,accessible=enterable,approach=world(((x0+x1)/2,y,front-.6)),inside=world(((x0+x1)/2,y,z+.8))))
                if enterable:
                    # Missing leaves are visible on every navigable doorway.
                    # A few detached planks sit beside the end pier, never in a
                    # door or straight approach corridor.
                    if decay and x0==min(a for a,b in ground_plan['door_ranges']):
                        wood.beam((left+.07,.02,z+.30),(left+.13,1.35,z+.38),.10,.045,'wood')
                elif ww>1.25:
                    shutter(x0+.02,z-.025,h['y0']+.02,h['y1']-.03,min(.62,ww*.40),-1.35,broken=seed%3==0)
                    if (seed+level)%2:shutter(x1-.02,z-.025,h['y0']+.03,h['y1']-.02,-min(.53,ww*.36),1.28,broken=True)
                elif seed%2:shutter(x0+.02,z-.03,h['y0']+.02,h['y1']-.02,ww*.76,-1.46,broken=variant=='plaster')
            elif h['kind']=='gallery' or (level and ww>1.6):
                count=max(3,round(ww/.85));step=ww/count
                for j in range(count):
                    xa=x0+j*step;xb=xa+step
                    # Every third leaf is physically folded open; several others
                    # are only lower lattice, revealing the unlit upper room.
                    if j%3==1 and not (decay==2 and j%2):
                        shutter(xa+.025,z-.035,h['y0']+.03,h['y1']-.03,step*.90,-1.28-.08*decay,screen=True)
                    elif j%3==0 and (decay<2 or j%2==0):
                        porous_screen(xa+.025,xb-.025,z-.03,h['y0']+.03,h['y1']-.03,seed+j)
                    if j<count-1:wood.beam((xb,h['y0']-.05,z-.02),(xb,h['y1']+.04,z-.02),.07,.09,'wood')
            else:
                # Both leaves open; their geometric patterns are silhouetted
                # against a genuinely hollow room, not painted onto black panels.
                shutter(x0,z-.02,h['y0'],h['y1'],ww*.49,-1.05,screen=True)
                shutter(x1,z-.02,h['y0'],h['y1'],-ww*.49,1.30,screen=True)
        # Posts do not form a uniform window grid: one main offset pier and two
        # perimeter uprights carry the porch/upper beam.
        if recess>.45:
            postlist=ground_plan['posts'] if level==0 else [(left+.14,outer_front+.12,.18),(right-.14,outer_front+.12,.18)]
            for x,pz,pr in postlist:
                stone_block((x,y+.10,pz),(.30,.20,.32),'stone',.012)
                porch_posts.append(dict(center=world((x,y,pz)),radius=pr,floor=base+y))
                wood.beam((x,y+.19,pz),(x+.018*math.sin(seed+x),ceil+.01,pz-.02),.14,.17,'wood')
                wood.beam((x,ceil-.56,outer_front+.12),(x,ceil-.08,z-.02),.085,.105,'wood')
            wood.beam((left+.08,ceil-.04,outer_front+.11),(right-.08,ceil-.04,outer_front+.11),.18,.23,'wood')
            shade.box((mid,ceil+.025,(outer_front+z)/2),(bw-.46,.10,z-outer_front+.02),'wood')
            if level:
                rail(left+.14,right-.14,outer_front+.15,y,.73,1 if seed%2 else 0)
        # Sparse interior structure and domestic remnants provide parallax when
        # looking through the door. Keep the centre ray unobstructed for probes.
        if not enterable:inside.box((left+bw*.20,y+.37,room_back-.58),(bw*.23,.08,.55),'wood')
        for xx in (() if enterable else (left+bw*.10,left+bw*.26)):inside.box((xx,y+.17,room_back-.58),(.065,.34,.43),'wood')
        if level==0 and detail>1 and not enterable:
            props.lathe((right-.55,y,room_back-.65),[(0,.18),(.12,.24),(.40,.28),(.56,.20),(.59,.22),(.64,.17)],'earth',12)

    # Rough plaster repairs and exposed brick courses are actual relief clustered
    # around wet corners, not a repeated stain stamped onto every storey.
    if detail>0:
        # Slightly bowed timber outside the clear opening, with irregular lower
        # board ends. This creates an old, repaired silhouette instead of boxes.
        if variant in ('timber_gallery','corner') and levels>1:
            ul,ur,uf,ub=upper;uw=ur-ul
            for i in range(max(4,round(uw/.20))):
                x=ul+(i+.5)*uw/max(4,round(uw/.20))
                top=floor_h+.54;bottom=floor_h+rr.uniform(.04,.12)
                wood.box((x,(bottom+top)/2,uf+min(.75,porch*.65)-.035),(.185,top-bottom,.055),'wood')

    def tiled_slope(x0,x1,z0,z1,y0,y1,rowscale=1.,tilemesh=roofs,gable_bounds=None):
        """Individually lapped, curved pan tiles with uneven eave silhouettes."""
        nonlocal missing_tiles
        cols=max(3,round((x1-x0)/(.21 if detail>1 else .36 if detail else 1.4)))
        rows=max(2,round(abs(z1-z0)/(.32*rowscale if detail>1 else .55 if detail else 1.4)))
        width=(x1-x0)/cols
        def surface(x,z):
            t=max(0.,min(1.,(z-z0)/(z1-z0)))
            # Curved settling: steeper at the ridge, relaxed and a little lifted
            # at the eave. No ceremonial upturned temple corners.
            y=y0+(y1-y0)*(1-(1-t)**1.28)
            y+=.025*math.sin(x*1.9+seed)+.018*math.sin(z*2.1+seed*.2)
            # The failing section settles as one construction patch, especially
            # at awnings. It does not become random noisy tile displacement.
            settle=(.035+.055*decay)*math.sin(math.pi*max(0.,min(1.,(x-x0)/(x1-x0))))**2
            y-=settle*math.sin(math.pi*t*.80)**2
            return y
        if detail==0:
            for j in range(rows):
                za=z0+(z1-z0)*j/rows;zb=z0+(z1-z0)*(j+1)/rows
                face_up(tilemesh,((x0,surface(x0,za),za),(x1,surface(x1,za),za),(x1,surface(x1,zb),zb),(x0,surface(x0,zb),zb)),'roof')
        else:
            for i in range(cols):
                xa=x0+i*width;xb=xa+width
                for j in range(rows):
                    za=z0+(z1-z0)*j/rows;zb=z0+(z1-z0)*(j+1)/rows
                    damaged=decay and ((i/cols-(.25+.08*(seed%5)))**2/(.12 if decay==2 else .065)**2+(j/rows-(.60+.08*(seed%3)))**2/(.32 if decay==2 else .16)**2<1.)
                    if damaged:
                        missing_tiles+=1
                        # The outer tile coat has fallen away, exposing dark
                        # uneven boards. A retained under-roof prevents sky
                        # pinholes and lets the damage read as actual depth.
                        face_up(inside,((xa,surface(xa,za)-.10,za),(xb,surface(xb,za)-.10,za),(xb,surface(xb,zb)-.10,zb),(xa,surface(xa,zb)-.10,zb)),'wood')
                        if (i+j)%3==0:wood.beam((xa,surface(xa,za)-.06,za),(xa,surface(xa,zb)-.06,zb),.045,.06,'wood')
                        continue
                    # Eave tiles have independently chipped ends; the dark
                    # continuous under-roof prevents unwanted sky pinholes.
                    if j==rows-1:zb+=rr.uniform(-.055,.040)
                    lip=.017+rr.random()*.014;segments=4 if detail>1 else 2
                    for k in range(segments):
                        ta=k/segments;tb=(k+1)/segments
                        aa=xa+width*ta;bb=xa+width*tb
                        ha=.045*(2*ta-1)**2;hb=.045*(2*tb-1)**2
                        face_up(tilemesh,((aa,surface(aa,za)+ha+lip,za),(bb,surface(bb,za)+hb+lip,za),
                                          (bb,surface(bb,zb)+hb,zb),(aa,surface(aa,zb)+ha,zb)),'roof')
                    # Narrow convex cover at the shared edge creates the
                    # characteristic linked half-round tile mouths in reference.
                    for k in range(3 if detail>1 else 2):
                        a=math.pi*k/(3 if detail>1 else 2);b=math.pi*(k+1)/(3 if detail>1 else 2)
                        ra=.046;pa=xa+math.cos(a)*ra;pb=xa+math.cos(b)*ra
                        face_up(tilemesh,((pa,surface(pa,za)+.05+math.sin(a)*ra+lip,za),(pb,surface(pb,za)+.05+math.sin(b)*ra+lip,za),
                                          (pb,surface(pb,zb)+.05+math.sin(b)*ra,zb),(pa,surface(pa,zb)+.05+math.sin(a)*ra,zb)),'roof')
                    if j==rows-1:
                        tilemesh.face(((xa,surface(xa,zb),zb),(xb,surface(xb,zb),zb),(xb,surface(xb,zb)-.06,zb),(xa,surface(xa,zb)-.06,zb)),'roof')
        # Clip the soffit at the actual thick gable walls. A single dark plane
        # spanning the full roof used to cut through the plaster and appear as
        # a black diagonal scar. Retain separate strips under exterior overhangs.
        low,high=gable_bounds if gable_bounds is not None else (-w/2,w/2)
        strips=((x0,min(x1,low-.09)),(max(x0,low+thick+.07),min(x1,high-thick-.07)),(max(x0,high+.09),x1))
        for left,right in strips:
            if right-left<.015:continue
            for j in range(max(2,rows)):
                za=z0+(z1-z0)*j/max(2,rows);zb=z0+(z1-z0)*(j+1)/max(2,rows)
                underside=[(left,surface(left,za)-.14,za),(right,surface(right,za)-.14,za),
                           (right,surface(right,zb)-.14,zb),(left,surface(left,zb)-.14,zb)]
                if z1<z0:underside.reverse()
                shade.face(underside,'wood')
        wood.beam((x0,y1-.09,z1),(x1,y1-.09,z1),.11,.16,'wood')
        if detail>0:
            for i in range(max(3,round((x1-x0)/.48))):
                x=x0+(i+.5)*(x1-x0)/max(3,round((x1-x0)/.48))
                wood.beam((x,y0-.15,z0),(x,y1-.13,z1+.065*math.copysign(1,z1-z0)),.065,.09,'wood')

    def gable_shell(points,outward):
        # Opposite building ends require opposite outward winding. Interior
        # material also needs its own inset surface: a reversed coplanar face
        # was winning the depth test and turning entire front gables black.
        pts=list(points)
        # Match the exact boundary vertices of the wall below. Coherent settling
        # still leaves a seam if a long gable edge skips the wall's window cuts.
        for edge in wall_top_edges:
            if math.dist(edge[0],pts[0])<1e-6 and math.dist(edge[-1],pts[1])<1e-6:
                pts=edge+[pts[2]];break
            if math.dist(edge[-1],pts[0])<1e-6 and math.dist(edge[0],pts[1])<1e-6:
                pts=edge[::-1]+[pts[2]];break
        # Newell normal handles the now-collinear intermediate base vertices.
        n=[0.,0.,0.]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            n[0]+=(a[1]-b[1])*(a[2]+b[2]);n[1]+=(a[2]-b[2])*(a[0]+b[0]);n[2]+=(a[0]-b[0])*(a[1]+b[1])
        if sum(n[i]*outward[i] for i in range(3))<0:pts.reverse()
        inner=[tuple(p[i]-outward[i]*thick for i in range(3)) for p in pts]
        wall.face(pts,'plaster');inside.face(inner[::-1],'plaster')
        for i in range(len(pts)):
            j=(i+1)%len(pts)
            wall.face((pts[i],pts[j],inner[j],inner[i]),'plaster')
        center=tuple(sum(p[i] for p in pts)/len(pts) for i in range(3))
        gable_probes.append(dict(center=world(center),normal=normal(outward),thickness=thick,outer=[world(p) for p in pts],inner=[world(p) for p in inner]))

    # Broad, modest domestic roof; blank gable ends remain heavy white masonry.
    # Gable bases meet height exactly: eave is .04m higher for tile clearance,
    # and using eave for masonry left a visible daylight slit above the wall.
    tl,tr,tf,tb=top_bounds;tw=tr-tl;td=tb-tf;tcx=(tl+tr)/2;tcz=(tf+tb)/2
    roofrise=min(1.65,(tw if variant=='gable' else td)*(.20+.02*(seed%4)))
    eave=height+.04;ridge=eave+roofrise
    roof_front=tf-.44;roof_back=tb+.35;roof_ridge_z=tcz
    if variant=='gable':
        # Author a normal roof and rotate only these components through 90deg;
        # the world-facing front gable changes the district silhouette.
        starts={k:len(copies[k].vertices) for k in ('canal_roofs','canal_shadow','canal_timber','canal_interiors')}
        tiled_slope(-td/2-.30,td/2+.30,0,-tw/2-.42,ridge,eave,gable_bounds=(-td/2,td/2))
        tiled_slope(-td/2-.30,td/2+.30,0,tw/2+.35,ridge,eave,gable_bounds=(-td/2,td/2))
        for k,start in starts.items():
            m=copies[k]
            for i in range(start,len(m.vertices)):
                x,y,z=m.vertices[i];m.vertices[i]=(tcx-z,y,tcz+x)
        for z,sign in ((tf,-1),(tb,1)):
            gable_shell(((tl,height,z),(tr,height,z),(tcx,ridge,z)),(0,0,sign))
        wood.beam((tcx,ridge+.04,tf-.32),(tcx,ridge+.04,tb+.32),.16,.18,'roof')
    else:
        tiled_slope(tl-.35,tr+.35,roof_ridge_z,roof_front,ridge,eave,gable_bounds=(tl,tr))
        tiled_slope(tl-.35,tr+.35,roof_ridge_z,roof_back,ridge,eave,gable_bounds=(tl,tr))
        for x,sign in ((tl,-1),(tr,1)):
            gable_shell(((x,height,tf),(x,height,tb),(x,ridge,roof_ridge_z)),(sign,0,0))
        roofs.beam((tl-.39,ridge+.07,roof_ridge_z),(tr+.39,ridge+.07,roof_ridge_z),.17,.20,'cap')
    # Low porch awnings overlap the frontage irregularly. Their dense shadows
    # and tile mouths are far more characteristic than decorative balconies.
    if levels>1 or variant in ('shopfront','arcade'):
        awtop=min(height-.5,floor_h+.11);awfront=front-.40
        # The front lean-to reaches the actual reduced upper mass, while the
        # lower porch remains as broad as the foundation beneath it.
        awback=max(front+porch+.12,tf+.10) if levels>1 else front+porch+.12
        tiled_slope(-w/2-.16,w/2+.17,awback,awfront,awtop+.08,awtop-.35,1.15)
    if levels>1:
        # Side shoulders are separately roofed, visibly exposing the narrower
        # upper floor instead of leaving a flat modern terrace around it.
        def side_lean(inner_x,outer_x,z0,z1):
            starts={k:len(copies[k].vertices) for k in ('canal_roofs','canal_shadow','canal_timber','canal_interiors')}
            # Work in rotated coordinates then map (-z,x) back into X/Z.
            tiled_slope(z0,z1,-inner_x,-outer_x,floor_h+.18,floor_h-.22,1.10,gable_bounds=(z0+.16,z1-.16))
            for key,start in starts.items():
                m=copies[key]
                for i in range(start,len(m.vertices)):
                    x,y,z=m.vertices[i];m.vertices[i]=(-z,y,x)
        if tl-(-w/2)>.28:side_lean(tl+.07,-w/2-.28,max(front+porch+.10,tf),back+.22)
        if w/2-tr>.28:side_lean(tr-.07,w/2+.28,max(front+porch+.10,tf),back+.22)
        if back-tb>.22:
            tiled_slope(tl-.12,tr+.12,tb-.06,back+.28,floor_h+.18,floor_h-.22,1.12,gable_bounds=(tl,tr))

    if bool(spec.get('laundry',seed%5==0)) and detail>0:
        # Reachable doorways must remain clear at head and shoulder height.
        # Full-sized garments belong on the real upper porch in those houses;
        # non-enterable homes retain low lines like the photographic reference.
        laundry_left,laundry_right=-w*.35,w*.35
        z=front+.06;y=min(floor_h-.35,2.25)
        if enterable and levels>1:
            laundry_left,laundry_right=upper[0]+.14,upper[1]-.14
            z=upper[2]+.08;y=floor_h+min(floor_h-.35,2.25)
        elif enterable:
            y=floor_h-.26
        laundry_span=laundry_right-laundry_left
        count=8
        for i in range(count):
            xa=laundry_left+laundry_span*i/count;xb=laundry_left+laundry_span*(i+1)/count
            ya=y-.13*math.sin(math.pi*i/count);yb=y-.13*math.sin(math.pi*(i+1)/count)
            props.beam((xa,ya,z),(xb,yb,z),.009,.009,'wood')
        for i in range(3+seed%3):
            x=laundry_left+laundry_span*.10+i*laundry_span*.80/max(1,2+seed%3);ww=rr.uniform(.29,.44);hh=rr.uniform(.48,.72)
            if enterable and levels==1:hh=min(hh,.38)
            yy=y-.13*math.sin(math.pi*((x-laundry_left)/laundry_span))
            def cloth_point(u,v):return(x+(u-.5)*ww,yy-v*hh,z+.045*math.sin(u*8+v*3+i))
            tile='cloth' if i%3==0 else 'paper'
            if i%3==0:
                # Two leg silhouettes and a real crotch opening distinguish
                # trousers from a strip of paper at the native game resolution.
                outline=((.06,0),(.94,0),(1.,.96),(.59,1.),(.51,.44),(.41,1.),(0.,.96))
                pts=[cloth_point(u,v) for u,v in outline]
                props.face(pts,tile);props.face(pts[::-1],tile)
            elif i%3==1:
                # Shoulder, short sleeves and a small scooped neckline. These
                # are unanimated household garments, not human-shaped figures.
                outline=((.18,0),(.41,0),(.44,.08),(.56,.08),(.59,0),(.82,0),
                         (1.,.20),(.86,.34),(.76,.25),(.77,1.),(.23,1.),(.24,.25),(.14,.34),(0.,.20))
                pts=[cloth_point(u,v) for u,v in outline]
                props.face(pts,tile);props.face(pts[::-1],tile)
            else:
                for row in range(4):
                    for col in range(3):
                        pts=(cloth_point(col/3,row/4),cloth_point((col+1)/3,row/4),cloth_point((col+1)/3,(row+1)/4),cloth_point(col/3,(row+1)/4))
                        props.face(pts,tile);props.face(pts[::-1],tile)
            for xx in (x-ww*.35,x+ww*.35):props.box((xx,yy+.015,z),(.022,.06,.026),'wood')

    # Copy authored local geometry once, applying a coherent tiny lean/settling
    # field to every component so openings still align with their jambs.
    counts={}
    for key,source in copies.items():
        target=meshes[key];offset=len(target.vertices)
        target.vertices.extend(world(p) for p in source.vertices)
        target.faces.extend([[offset+j for j in f] for f in source.faces])
        target.uv.extend(source.uv);target.smooth.extend(source.smooth)
        counts[key]=sum(max(0,len(f)-2) for f in source.faces)
    return dict(id=spec.get('id',f'house-{seed}'),seed=seed,variant=variant,
                center=[cx,base,cz],yaw=yaw,width=w,depth=d,height=height,
                bounds_corners=[world((x,y,z)) for x in (-w/2,w/2) for y in (0,height+roofrise) for z in (front,back)],
                openings=opening_probes,rooms=floor_bounds,porch_posts=porch_posts,gables=gable_probes,enterable=enterable,upper_setback=upper_setback,
                ground_plan=ground_plan,door_portals=door_portals+rear_portals,rear_portals=rear_portals,
                upper_bounds=list(upper) if levels>1 else None,
                upper_footprint_ratio=((upper[1]-upper[0])*(upper[3]-upper[2])/(w*d)) if levels>1 else None,
                water_y=water_y,foundation_bottom=foundation_bottom,
                decay=('intact','neglected','ruin')[decay],missing_roof_tiles=missing_tiles,
                porous_panels=porous_panels,folded_leaves=folded_leaves,
                authored_triangles=sum(counts.values()),models=counts)
