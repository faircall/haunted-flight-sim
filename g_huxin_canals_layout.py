"""Irregular domestic water village. Geometry and navigation share these metre-scale surfaces."""
import math
from functools import lru_cache
from canals_house_plan import house_ground_plan
DECK=.325
WATER_Y=-1.55
BANK_BOTTOM=-2.30
UPPER=DECK+2.8
START=(1.65,DECK,1.65)
CAUSEWAY_END=12.
STAIRS=()
STAIR_COUNT=0
GALLERY_RECTS=()
GROUND_RECTS=()
LEFT_QUAY=((-1.80,11.5),(-2.,16.),(-2.2,22.),(-2.4,24.),(-3.5,30.),(-3.1,34.),(-2.4,37.),(-1.4,46.),(-2.,54.),(-2.8,58.),(-3.,64.5))
RIGHT_QUAY=((6.4,12.),(5.7,16.),(4.8,22.),(4.8,24.),(4.2,31.),(5.5,35.),(5.8,38.),(6.4,46.),(5.5,54.),(4.7,58.),(4.8,64.5))
COURT_PATH=((-3.2,27.8),(-8.,27.8),(-12.7,28.0),(-14.8,30.),(-14.8,35.7),(-12.3,38.2),(-7.6,38.),(-2.5,37.5))
EAST_ALLEY=((5.4,34.4),(10.,34.4),(13.8,35.),(14.4,38.3),(14.2,42.7),(11.7,44.3),(6.2,44.))
BRIDGES=(dict(name='The washing-house bridge',z=24.,x0=-2.4,x1=4.8,width=1.65,rise=.78,steps=24),dict(name='The other washing-house bridge',z=46.,x0=-1.4,x1=6.4,width=1.72,rise=.89,steps=26))
STEP_DROPS=(0.,.15,.31,.47,.64,.80,.97,1.13,1.30,1.47,1.64,1.80,1.97,2.14)
FRONT_WASHING_STAIRS=tuple(dict(id='washing-'+str(i),top=(x,z),angle=a,width=w,steps=len(STEP_DROPS),tread=.31,walkable=walk,landing=walk,side='front')
 for i,(x,z,a,w,walk) in enumerate((
 (-1.10,16.8,1.17,1.26,True),(3.40,29.4,2.00,1.20,True),(-.70,49.6,1.12,1.30,True),
 (4.15,55.0,2.12,1.16,False),(-1.35,36.9,1.10,1.14,False),
 (-4.0,-11.8,-1.11,1.35,False),(4.0,-25.0,-2.05,1.25,False),
 (-9.3,-3.4,-.55,1.35,False),(9.45,-1.8,2.58,1.22,False))))
REAR_FLIGHTS={110:(math.pi+.50,.29),133:(-1.62,.24),157:(math.pi+.40,.29),168:(math.pi-.35,.29),
 211:(.38,.29),224:(-.48,.29),237:(-.50,.29),261:(.30,.29),273:(-.30,.29),
 410:(-2.10,.29),437:(math.pi-.50,.29),449:(-.45,.29),473:(.45,.29),487:(math.pi+.40,.29),499:(-.40,.29)}
# Opposite domestic rear walls face the playable backwaters. Their washing
# stairs belong to the far houses rather than appearing as detached canal props.
SCENIC_REAR_FLIGHTS={1901:-.25,1935:.40,1969:-.45,2003:1.15,2037:.75,2071:.25,
 2326:math.pi+.35,2360:math.pi-.40,2394:math.pi-.80,
 2462:math.pi-.40,2496:math.pi+.45,2530:math.pi-.30}
def step_point(s,t,u=0.):
 dx,dz=math.cos(s['angle']),math.sin(s['angle']);x,z=s['top']
 return x+dx*t-dz*u,z+dz*t+dx*u
def step_local(s,x,z):
 dx,dz=math.cos(s['angle']),math.sin(s['angle']);xx,zz=x-s['top'][0],z-s['top'][1]
 return xx*dx+zz*dz,-xx*dz+zz*dx
def step_polygon(s,t0,t1,u0,u1):return tuple(step_point(s,t,u) for t,u in ((t0,u0),(t1,u0),(t1,u1),(t0,u1)))
def step_height(s,t):return DECK-STEP_DROPS[max(0,min(s['steps']-1,int(t/s['tread'])))]
def landing_rect(s):return (s['tread']*8.25,s['tread']*10.20,s['width']/2-.04,s['width']/2+1.06)
def house(cx,cz,width,depth,height,floors,yaw,variant,seed,**extras):
 return dict(cx=cx,cz=cz,width=width,depth=depth,height=height,floors=floors,yaw=yaw,variant=variant,seed=seed,detail=2,base_y=DECK,**extras)
HOUSE_SPECS=(
 house(-7.3,16.1,7.3,6.5,5.35,2,math.pi/2-.035,'timber_gallery',110,porch=1.10,laundry=True),
 house(-7.,23.5,5.6,5.6,3.,1,math.pi/2+.025,'plaster',121,porch=.85),
 house(-8.6,32.7,6.2,6.4,5.45,2,math.pi/2-.03,'shopfront',133,porch=1.15,enterable=True),
 house(-6.8,41.4,5.9,6.5,3.15,1,math.pi/2+.06,'gable',144,porch=.85),
 house(-6.9,50.3,7.7,6.4,5.6,2,math.pi/2-.04,'arcade',157,porch=1.05,laundry=True),
 house(-7.6,59.2,6.2,6.6,4.85,2,math.pi/2+.02,'corner',168,porch=.95),
 house(9.7,15.3,7.4,5.6,3.05,1,-math.pi/2+.035,'plaster',211,porch=.9),
 house(9.5,23.4,6.4,6.7,5.25,2,-math.pi/2-.04,'timber_gallery',224,porch=1.2),
 house(9.5,30.4,5.6,7.,3.25,1,-math.pi/2+.055,'gable',237,porch=.8),
 house(9.9,39.,6.2,5.2,5.5,2,-math.pi/2-.025,'shopfront',249,porch=1.25,laundry=True,enterable=True),
 house(10.,49.2,7.5,5.8,5.05,2,-math.pi/2+.055,'corner',261,porch=1.),
 house(9.,58.,6.3,6.,3.1,1,-math.pi/2-.04,'plaster',273,porch=.9),
 house(-18.4,32.6,8.3,5.6,5.15,2,math.pi/2+.025,'arcade',310,porch=1.),
 house(-12.8,22.8,6.3,6.1,3.,1,math.pi-.06,'gable',323,porch=.8),
 house(-14.2,43.9,7.8,7.1,5.05,2,.025,'timber_gallery',337,porch=1.),
 house(18.1,39.1,7.5,5.,3.05,1,-math.pi/2+.025,'plaster',349,porch=.9),
 house(-13.6,-3.,7.2,6.4,5.35,2,math.pi/2-.04,'timber_gallery',410,porch=1.15,laundry=True),
 house(13.7,-2.1,7.1,6.1,3.15,1,-math.pi/2+.025,'gable',423,porch=.9),
 house(-8.7,-14.,6.1,5.7,5.35,2,math.pi/2+.035,'shopfront',437,porch=1.05),
 house(9.,-14.8,6.9,5.9,5.1,2,-math.pi/2-.045,'timber_gallery',449,porch=1.2),
 house(-8.6,-22.,6.,6.,3.1,1,math.pi/2-.03,'plaster',461,porch=.85),
 house(8.7,-23.6,6.8,5.9,3.2,1,-math.pi/2+.03,'gable',473,porch=.8),
 house(-9.6,-30.5,7.8,6.2,5.2,2,math.pi/2+.035,'arcade',487,porch=1.),
 house(8.5,-32.,7.5,6.4,5.3,2,-math.pi/2-.025,'corner',499,porch=1.,laundry=True))
# The first sixteen homes all open onto the playable connected quay network.
# Vary whole-building mass, not just a repeated upper-window arrangement.
_heights=(6.35,2.80,6.85,3.65,5.10,5.75,3.55,6.15,2.85,5.45,6.65,3.20,5.85,3.45,6.05,3.05,6.45,3.70,5.15,6.10,2.80,3.65,6.35,5.25)
for _i,_s in enumerate(HOUSE_SPECS):
 _s.update(height=_heights[_i],water_y=WATER_Y,foundation_bottom=BANK_BOTTOM,
           decay=('neglected','ruin','intact','neglected','ruin')[_i%5])
 if _i<16:_s['enterable']=True
 if _s['seed'] in REAR_FLIGHTS:_s.update(rear_access=True,rear_landing_depth=1.25,rear_landing_width=2.25,rear_door_width=1.65)
 if _s['seed']==133:_s.update(rear_landing_depth=2.0,rear_landing_width=3.0)
 if _s['floors']>1:
  _s.update(upper_left=.30+.17*(_i%4),upper_right=.35+.21*((_i+2)%4),upper_front=.65+.24*(_i%4),upper_back=.35+.16*((_i+1)%3))
def transform(s,x,z):
 x,z=x+.14*z/s['depth'],z+.12*x/s['width']
 c,a=math.cos(s['yaw']),math.sin(s['yaw']);return s['cx']+c*x-a*z,s['cz']+a*x+c*z

REAR_WASHING_STAIRS=tuple(dict(id='rear-washing-'+str(s['seed']),house_seed=s['seed'],side='rear',
 top=transform(s,.60 if s['seed']==133 else 0.,s['depth']/2+s['rear_landing_depth']-.12),angle=REAR_FLIGHTS[s['seed']][0],
 width=1.12 if s['seed']==133 else 1.22,steps=len(STEP_DROPS),tread=REAR_FLIGHTS[s['seed']][1],
 walkable=bool(s.get('enterable')),landing=bool(s.get('enterable'))) for s in HOUSE_SPECS if s.get('rear_access'))
WASHING_STAIRS=FRONT_WASHING_STAIRS+REAR_WASHING_STAIRS
REAR_QUAY_GROUPS=((157,168),(211,224,237),(261,273),(410,437,487),(449,473,499))

def rear_polygons(playable):
 out=[];by_seed={s['seed']:s for s in HOUSE_SPECS}
 for s in HOUSE_SPECS:
  if not s.get('rear_access') or bool(s.get('enterable'))!=playable:continue
  p=house_ground_plan(s);a,b,c,d=p['rear_landing_bounds'];b=p['rearwall']+.04
  out.append(ccw([transform(s,x,z) for x,z in ((a,b),(c,b),(c,d),(a,d))]))
 for group in REAR_QUAY_GROUPS:
  selected=[by_seed[seed] for seed in group if bool(by_seed[seed].get('enterable'))==playable]
  if len(selected)<2:continue
  pts=[transform(s,0.,s['depth']/2+.65) for s in selected]
  out.extend(ribbon(pts,.59))
 return out
def local_point(s,x,z):
 c,a=math.cos(s['yaw']),math.sin(s['yaw']);dx,dz=x-s['cx'],z-s['cz'];u,v=c*dx+a*dz,-a*dx+c*dz
 aa,bb=.14/s['depth'],.12/s['width'];det=1.-aa*bb
 return (u-aa*v)/det,(v-bb*u)/det
def house_polygon(s,margin=0.):
 w,d=s['width']/2+margin,s['depth']/2+margin
 return tuple(transform(s,x,z) for x,z in ((-w,-d),(w,-d),(w,d),(-w,d)))
def in_house(s,x,z,margin=0.):
 u,v=local_point(s,x,z)
 return abs(u)<s['width']/2+margin and abs(v)<s['depth']/2+margin
def interior_point(s,x,z):
 if not s.get('enterable'):return False
 u,v=local_point(s,x,z);p=house_ground_plan(s);a,b,c,d=p['room_bounds'];front,wall=p['front'],p['frontwall']
 if p.get('rear_access') and p['rearwall']-.35<v<p['rearwall']+.055:
  return any(lo+.075<u<hi-.075 for lo,hi in p['rear_door_ranges'])
 if not (a<u<c and front-.04<v<d):return False
 for px,pz,r in p['posts']:
  if math.hypot(u-px,v-pz)<r:return False
 if wall-.075<v<wall+p['wall_thickness']+.075:
  return any(lo+.075<u<hi-.075 for lo,hi in p['door_ranges'])
 return True
BUILDINGS=tuple((min(p[0] for p in house_polygon(s)),min(p[1] for p in house_polygon(s)),max(p[0] for p in house_polygon(s)),max(p[1] for p in house_polygon(s)),DECK+s['height'],s['floors'],'z') for s in HOUSE_SPECS)
def rect_contains(q,x,z):return q[0]-1e-7<=x<=q[2]+1e-7 and q[1]-1e-7<=z<=q[3]+1e-7
def point_in_poly(p,x,z):return all((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0])>=-1e-7 for a,b in zip(p,p[1:]+p[:1]))
def area(p):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))*.5
def ccw(p):return list(p) if area(p)>0 else list(reversed(p))
def split(p,n,k):
 inside=[];outside=[]
 for a,b in zip(p,p[1:]+p[:1]):
  da=a[0]*n[0]+a[1]*n[1]-k;db=b[0]*n[0]+b[1]*n[1]-k
  if abs(da)<=1e-9:inside.append(a);outside.append(a)
  elif da<0:inside.append(a)
  else:outside.append(a)
  if da*db<-1e-12:
   t=da/(da-db);v=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t);inside.append(v);outside.append(v)
 return inside,outside
def subtract(p,clip):
 if max(v[0] for v in p)<min(v[0] for v in clip) or min(v[0] for v in p)>max(v[0] for v in clip) or max(v[1] for v in p)<min(v[1] for v in clip) or min(v[1] for v in p)>max(v[1] for v in clip):return [p]
 remaining=list(p);out=[]
 for a,b in zip(clip,clip[1:]+clip[:1]):
  if len(remaining)<3:break
  n=(b[1]-a[1],a[0]-b[0]);remaining,outer=split(remaining,n,a[0]*n[0]+a[1]*n[1])
  if len(outer)>=3 and abs(area(outer))>1e-7:out.append(ccw(outer))
 return out
def ribbon(points,left,right=None):
 right=left if right is None else right;edges=[]
 for i,p in enumerate(points):
  a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)];dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);nx,nz=-dz/length,dx/length
  edges.append(((p[0]+nx*left,p[1]+nz*left),(p[0]-nx*right,p[1]-nz*right)))
 return [ccw((a[0],a[1],b[1],b[0])) for a,b in zip(edges,edges[1:])]

@lru_cache(maxsize=1)
def source_causeway_polygons():
 from g_huxin_canals import PATH,path_halfwidth
 edges=[]
 for i,(x,z) in enumerate(PATH):
  a=PATH[max(0,i-1)];b=PATH[min(len(PATH)-1,i+1)];dx,dz=b[0]-a[0],b[1]-a[1];ln=math.hypot(dx,dz)
  nx,nz=dz/ln,-dx/ln;w=path_halfwidth(z)+.065+.025*math.sin(i*1.9)
  edges.append(((x-nx*w,z-nz*w),(x+nx*w,z+nz*w)))
 out=[]
 for a,b in zip(edges,edges[1:]):
  poly=ccw((a[0],b[0],b[1],a[1]));poly,_=split(poly,(0.,1.),CAUSEWAY_END)
  if len(poly)>2 and max(p[1] for p in poly)>6.1:out.append(ccw(poly))
 return tuple(out)

def source_join_span():
 xs=[x for p in source_causeway_polygons() for x,z in p if abs(z-CAUSEWAY_END)<1e-6]
 return min(xs),max(xs)

def boundary_segments(polygons,occluders=()):
 """Only genuine outside edges; split T-junctions before rejecting shared walls."""
 shapes=[ccw(p) for p in polygons];cover=shapes+[ccw(p) for p in occluders]
 bounds=[(min(x for x,z in p),min(z for x,z in p),max(x for x,z in p),max(z for x,z in p),p) for p in cover]
 cells={}
 for p in cover:
  for x,z in p:cells.setdefault((math.floor(x/2),math.floor(z/2)),set()).add((x,z))
 result=[]
 for p in shapes:
  for a,b in zip(p,p[1:]+p[:1]):
   dx,dz=b[0]-a[0],b[1]-a[1];ln=math.hypot(dx,dz)
   if ln<1e-6:continue
   times={0.,1.};near=set()
   for ix in range(math.floor((min(a[0],b[0])-1e-4)/2),math.floor((max(a[0],b[0])+1e-4)/2)+1):
    for iz in range(math.floor((min(a[1],b[1])-1e-4)/2),math.floor((max(a[1],b[1])+1e-4)/2)+1):near.update(cells.get((ix,iz),()))
   for x,z in near:
    t=((x-a[0])*dx+(z-a[1])*dz)/(ln*ln)
    if 1e-7<t<1.-1e-7 and abs(dx*(z-a[1])-dz*(x-a[0]))<ln*2e-5:times.add(round(t,8))
   ordered=sorted(times)
   for ta,tb in zip(ordered,ordered[1:]):
    if (tb-ta)*ln<1e-5:continue
    t=(ta+tb)/2;x=a[0]+dx*t+dz/ln*.002;z=a[1]+dz*t-dx/ln*.002
    if any(x0-1e-7<=x<=x1+1e-7 and z0-1e-7<=z<=z1+1e-7 and point_in_poly(q,x,z) for x0,z0,x1,z1,q in bounds):continue
    result.append(((a[0]+dx*ta,a[1]+dz*ta),(a[0]+dx*tb,a[1]+dz*tb)))
 return tuple(result)
def raw_ground():
 out=ribbon(LEFT_QUAY,2.65,.95)+ribbon(RIGHT_QUAY,.95,2.7)+ribbon(COURT_PATH,.72)+ribbon(EAST_ALLEY,.70)
 out.extend(rear_polygons(True))
 # Match the exact retained causeway cross-section instead of ending the new
 # strip a few centimetres short along its curved, irregular stone margin.
 lo,hi=source_join_span()
 out.append(ccw(((lo,CAUSEWAY_END),(hi,CAUSEWAY_END),(-.95,14.),(-4.55,14.))))
 # Every reachable home has an actual doorstep apron attached to its quay.
 for s in HOUSE_SPECS[:16]:
  f=-s['depth']/2;w=s['width']/2
  out.append(ccw([transform(s,x,z) for x,z in ((-w,f-1.65),(w,f-1.65),(w,f),(-w,f))]))
 for route in DOOR_ROUTES:
  a,b=route['points'][:2]
  if math.dist(a,b)>.05:out.extend(ribbon((a,b),.68))
 for st in WASHING_STAIRS:
  if st['walkable']:out.append(ccw(step_polygon(st,-1.05,0.,-st['width']/2-.12,st['width']/2+.12)))
 clipped=[]
 for p in out:
  p,_=split(p,(0.,-1.),-CAUSEWAY_END)
  if len(p)>=3:clipped.append(ccw(p))
 return clipped
@lru_cache(maxsize=1)
def floor_polygons():
 raw=raw_ground();out=[]
 for i,p in enumerate(raw):
  pending=[p]
  for earlier in raw[:i]:pending=[piece for q in pending for piece in subtract(q,earlier)]
  for s in HOUSE_SPECS:pending=[piece for q in pending for piece in subtract(q,list(house_polygon(s,.025)))]
  for st in WASHING_STAIRS:
   cut=ccw(step_polygon(st,0.,st['steps']*st['tread'],-st['width']/2,st['width']/2))
   pending=[piece for q in pending for piece in subtract(q,cut)]
  out.extend(tuple(p) for p in pending if abs(area(p))>1e-6)
 return tuple(out)
def bridge_height(x,b):
 t=max(0.,min(1.,(x-b['x0'])/(b['x1']-b['x0'])));i=min(b['steps']-1,max(0,int(t*b['steps'])))
 return DECK+b['rise']*math.sin(math.pi*(i+.5)/b['steps'])**1.08
def stair_height(z):return DECK
def supported_by(rects,x,z,r):
 return all(any(rect_contains(q,x+dx*r,z+dz*r) for q in rects) for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)))
def support(x,z,previous,r=.19):
 from g_huxin_canals import can_walk
 if z<=CAUSEWAY_END and can_walk(x,z,r) and abs(previous-DECK)<.235:return DECK
 for st in WASHING_STAIRS:
  if not st['walkable']:continue
  t,u=step_local(st,x,z);half=st['width']/2
  if st['landing']:
   ta,tb,ua,ub=landing_rect(st)
   if ta+r<t<tb-r and ua-r<u<ub-r:
    h=DECK-STEP_DROPS[9]
    if abs(h-previous)<.235:return h
  if -r-.025<t<st['tread']*11.-r and abs(u)<half+r:
   if abs(u)>half-r:return None
   h=step_height(st,t);return h if abs(previous-h)<.235 else None
 for b in BRIDGES:
  if b['x0']<x<b['x1'] and abs(z-b['z'])<b['width']/2+r:
   if abs(z-b['z'])>b['width']/2-r:return None
   h=bridge_height(x,b);return h if abs(previous-h)<.235 else None
 if abs(previous-DECK)>=.235:return None
 for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(.707,.707),(-.707,.707),(.707,-.707),(-.707,-.707)):
  xx,zz=x+dx*r,z+dz*r
  if zz<=CAUSEWAY_END and can_walk(xx,zz,0.):continue
  if not any(point_in_poly(p,xx,zz) for p in floor_polygons()) and not any(interior_point(s,xx,zz) for s in HOUSE_SPECS):return None
 return DECK
REVIEW_ROUTE=((1.65,1.65),(1.2,3.),(0.,5.8),(0.,7.),(-1.84,12.),(-2.,16.),(-2.85,22.),(-2.85,24.),(1.,24.),(5.25,24.),(4.8,22.),(5.7,16.),(6.34,12.4),(5.7,16.),(4.8,22.),(5.25,24.),(5.25,26.2),(4.2,31.),(5.4,34.4),(5.8,38.),(6.32,43.4),(5.8,38.),(5.4,34.4),(10.,34.4),(13.8,35.),(14.4,38.3),(14.2,42.7),(11.7,44.3),(6.85,44.),(6.85,46.),(6.4,49.),(5.5,54.),(4.7,58.),(4.8,63.3),(4.7,58.),(5.5,54.),(6.4,49.),(6.85,46.),(2.4,46.),(-1.85,46.),(-2.,54.),(-2.8,58.),(-3.,63.3),(-2.8,58.),(-2.,54.),(-1.85,46.),(-2.4,37.),(-3.1,34.),(-3.5,30.),(-3.2,27.8),(-3.5,30.),(-3.1,34.),(-2.4,37.),(-7.6,38.),(-12.3,38.2),(-14.8,35.7),(-14.8,30.),(-12.7,28.0),(-8.,27.8),(-3.2,27.8),(-2.85,24.),(-2.85,22.),(-2.,16.),(-1.84,12.),(0.,7.),(0.,5.8),(1.2,3.),(1.65,1.65))
WATER_PROBES=((1.4,18.),(1.,33.),(1.6,42.),(0.,-12.),(17.,8.))
WALL_PROBES=tuple((s['cx'],s['cz']) for s in HOUSE_SPECS[16:21])
def closest_on_path(path,p):
 best=None
 for a,b in zip(path,path[1:]):
  dx,dz=b[0]-a[0],b[1]-a[1];t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/(dx*dx+dz*dz)))
  q=(a[0]+dx*t,a[1]+dz*t);d=math.dist(q,p)
  if best is None or d<best[0]:best=(d,q)
 return best[1]
def doorway_routes():
 records=[]
 for i,s in enumerate(HOUSE_SPECS):
  if not s.get('enterable'):continue
  p=house_ground_plan(s);path=LEFT_QUAY if i<6 else RIGHT_QUAY if i<12 else EAST_ALLEY if i==15 else COURT_PATH
  for bay,(lo,hi) in enumerate(p['door_ranges']):
   u=(lo+hi)/2;approach_depth=.80 if s['seed']==310 else 1.25
   outside=transform(s,u,p['front']-approach_depth);station=closest_on_path(path,outside)
   points=(station,outside,transform(s,u,p['front']-.12),transform(s,u,p['frontwall']+.60),transform(s,u,min(.65,p['room_bounds'][3]-.7)))
   records.append(dict(seed=s['seed'],bay=bay,clear_range=[lo,hi],points=points+tuple(reversed(points[:-1]))))
 return tuple(records)
DOOR_ROUTES=doorway_routes()
ROOM_ROUTES=tuple(r['points'] for r in DOOR_ROUTES)
def washing_route(st):
 path=LEFT_QUAY if st['top'][0]<1. else RIGHT_QUAY;entry=step_point(st,-.42);station=closest_on_path(path,entry)
 ta,tb,ua,ub=landing_rect(st)
 pts=(station,entry,step_point(st,.12),step_point(st,st['tread']*3.5),step_point(st,st['tread']*6.7),step_point(st,st['tread']*9.3),step_point(st,(ta+tb)/2,(ua+ub)/2))
 return pts+tuple(reversed(pts[:-1]))
WASHING_ROUTES=tuple(washing_route(st) for st in FRONT_WASHING_STAIRS if st['walkable'])

def through_house_routes():
 records=[];specs={s['seed']:s for s in HOUSE_SPECS}
 for st in REAR_WASHING_STAIRS:
  if not st['walkable']:continue
  s=specs[st['house_seed']];p=house_ground_plan(s);front_routes=[r for r in DOOR_ROUTES if r['seed']==s['seed']]
  front=front_routes[len(front_routes)//2]['points'][:5]
  lo,hi=p['rear_door_ranges'][0];u=(lo+hi)/2;back=p['rearwall'];ta,tb,ua,ub=landing_rect(st)
  approach=(transform(s,u,back-.80),transform(s,u,back+.28),transform(s,u,back+.65))
  if s['seed']==133:approach+=(step_point(st,-.62,.85),)
  pts=front+approach+(step_point(st,-.42),step_point(st,.12),step_point(st,st['tread']*3.5),step_point(st,st['tread']*6.7),step_point(st,st['tread']*9.3),step_point(st,(ta+tb)/2,(ua+ub)/2))
  records.append(dict(seed=s['seed'],rear_bay=0,stair_id=st['id'],washing_index=len(WASHING_ROUTES)+len(records),points=pts+tuple(reversed(pts[:-1]))))
 return tuple(records)
THROUGH_HOUSE_ROUTES=through_house_routes()
WASHING_ROUTES=WASHING_ROUTES+tuple(r['points'] for r in THROUGH_HOUSE_ROUTES)
CAMERA_SHOTS=(
 dict(name='A house where the shore was',eye=(5.2,3.4,9.3),target=(-2.,1.7,17.),fov=69,zone=(-5.,9.,9.,19.)),
 dict(name='The low white house',eye=(1.8,3.6,17.),target=(-2.,1.7,25.),fov=71,zone=(-5.,17.,0.,28.)),
 dict(name='A small stone crossing',eye=(1.5,3.8,29.),target=(1.,1.6,23.),fov=70,zone=(-4.,22.,6.,26.)),
 dict(name='The shuttered shop',eye=(1.2,3.5,33.7),target=(-3.,1.7,31.),fov=69,zone=(-6.,27.,0.,39.)),
 dict(name='The crooked courtyard entry',eye=(-11.8,3.1,27.5),target=(-4.5,1.5,27.9),fov=76,zone=(-13.,26.,-3.,30.)),
 dict(name='The dry well court',eye=(-12.1,4.8,37.6),target=(-14.,1.5,31.),fov=74,zone=(-17.,28.,-11.,39.)),
 dict(name='A passage behind the house',eye=(-11.6,3.2,38.5),target=(-3.1,1.5,37.),fov=74,zone=(-12.,36.,-2.,41.)),
 dict(name='Laundry over black water',eye=(2.6,3.5,41.),target=(-1.6,1.6,48.),fov=69,zone=(-5.,38.,1.,58.)),
 dict(name='The bridge repeats',eye=(2.,3.8,51.5),target=(2.,1.6,45.),fov=70,zone=(-3.,44.,8.,49.)),
 dict(name='An empty porch',eye=(1.7,3.25,29.),target=(5.,1.6,32.5),fov=72,zone=(3.,25.,8.,35.)),
 dict(name='The covered side alley',eye=(14.,3.1,34.9),target=(13.9,1.5,41.5),fov=74,zone=(10.,33.,16.,44.)),
 dict(name='Past the rain jars',eye=(12.1,3.4,44.3),target=(5.8,1.5,43.5),fov=74,zone=(5.,41.,13.,46.)),
 dict(name='The distant bend',eye=(1.8,3.2,40.),target=(6.,1.6,49.),fov=71,zone=(4.,35.,9.,58.)),
 dict(name='Porches face the other bank',eye=(.5,3.4,13.),target=(5.7,1.6,19.),fov=72,zone=(3.,11.,9.,25.)))
REVIEW_VIEWS=(
 dict(name='behind-the-tall-house',eye=(-15.5,.65,19.4),target=(-10.8,1.3,16.),fov=70),
 dict(name='the-private-washing-channel',eye=(-14.1,1.45,29.8),target=(-12.15,1.1,33.4),fov=72),
 dict(name='back-doors-on-the-east-canal',eye=(18.5,.85,26.3),target=(13.5,1.35,26.),fov=74),
 dict(name='long-washing-flight',eye=(2.4,.30,21.8),target=(-1.15,-.25,18.8),fov=67),
 dict(name='high-quay-and-low-water',eye=(.2,-.10,28.),target=(4.1,.65,31.),fov=68),
 dict(name='pavilion-still-here',eye=(6.,2.9,10.5),target=(-1.2,2.8,-4.),fov=68),
 dict(name='low-canal-houses',eye=(1.2,1.8,19.8),target=(-1.,2.7,42.),fov=66),
 dict(name='the-hollow-shop',eye=(.4,2.,31.),target=(-7.7,2.,32.7),fov=63),
 dict(name='porch-and-watersteps',eye=(1.5,1.6,-9.5),target=(-7.6,2.5,-15.),fov=69),
 dict(name='the-domestic-court',eye=(-13.8,3.5,38.),target=(-14.5,1.8,30.),fov=71),
 dict(name='village-beyond-the-bend',eye=(1.8,5.2,42.),target=(2.2,3.,100.),fov=63))

