"""Irregular domestic water village. Geometry and navigation share these metre-scale surfaces."""
import math
from functools import lru_cache
DECK=.325
WATER_Y=0.
UPPER=DECK+2.8
START=(1.65,DECK,1.65)
CAUSEWAY_END=12.
STAIRS=()
STAIR_COUNT=0
GALLERY_RECTS=()
GROUND_RECTS=()
LEFT_QUAY=((-1.80,11.5),(-2.,16.),(-2.2,22.),(-2.4,24.),(-3.5,30.),(-3.1,34.),(-2.4,37.),(-1.4,46.),(-2.,54.),(-2.8,58.))
RIGHT_QUAY=((6.4,12.),(5.7,16.),(4.8,22.),(4.8,24.),(4.2,31.),(5.5,35.),(5.8,38.),(6.4,46.),(5.5,54.),(4.7,58.))
COURT_PATH=((-3.2,27.8),(-8.,27.8),(-12.7,28.4),(-14.,30.),(-14.,35.7),(-12.3,38.2),(-7.6,38.),(-2.5,37.5))
EAST_ALLEY=((5.4,34.4),(10.,34.4),(13.8,35.),(14.4,38.3),(14.2,42.7),(11.7,44.3),(6.2,44.))
BRIDGES=(dict(name='The washing-house bridge',z=24.,x0=-2.4,x1=4.8,width=1.65,rise=.78,steps=24),dict(name='The other washing-house bridge',z=46.,x0=-1.4,x1=6.4,width=1.72,rise=.89,steps=26))
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
 house(-12.8,43.9,7.8,7.1,5.05,2,.025,'timber_gallery',337,porch=1.),
 house(18.1,39.1,7.5,5.,3.05,1,-math.pi/2+.025,'plaster',349,porch=.9),
 house(-13.6,-3.,7.2,6.4,5.35,2,math.pi/2-.04,'timber_gallery',410,porch=1.15,laundry=True),
 house(13.7,-2.1,7.1,6.1,3.15,1,-math.pi/2+.025,'gable',423,porch=.9),
 house(-8.7,-14.,6.1,5.7,5.35,2,math.pi/2+.035,'shopfront',437,porch=1.05),
 house(9.,-14.8,6.9,5.9,5.1,2,-math.pi/2-.045,'timber_gallery',449,porch=1.2),
 house(-8.6,-22.,6.,6.,3.1,1,math.pi/2-.03,'plaster',461,porch=.85),
 house(8.7,-23.6,6.8,5.9,3.2,1,-math.pi/2+.03,'gable',473,porch=.8),
 house(-9.6,-30.5,7.8,6.2,5.2,2,math.pi/2+.035,'arcade',487,porch=1.),
 house(8.5,-32.,7.5,6.4,5.3,2,-math.pi/2-.025,'corner',499,porch=1.,laundry=True))
def transform(s,x,z):
 x,z=x+.14*z/s['depth'],z+.12*x/s['width']
 c,a=math.cos(s['yaw']),math.sin(s['yaw']);return s['cx']+c*x-a*z,s['cz']+a*x+c*z
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
 u,v=local_point(s,x,z);w,d=s['width'],s['depth'];front=-d/2;wall=front+s['porch']
 if not (-w/2+.28<u<w/2-.28 and front-.04<v<d/2-.30):return False
 for px in (-w/2+.15,w*.06,w/2-.16):
  if math.hypot(u-px,v-(front+.12))<.19:return False
 if wall-.12<v<wall+.34:
  return .5*w-.64*w+.25<u<.5*w-.29*w-.25
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
def raw_ground():
 out=ribbon(LEFT_QUAY,2.65,.95)+ribbon(RIGHT_QUAY,.95,2.7)+ribbon(COURT_PATH,1.)+ribbon(EAST_ALLEY,1.)
 out.append(ccw(((-15.3,29.5),(-12.,29.5),(-12.,36.),(-15.3,36.))))
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
REVIEW_ROUTE=((1.65,1.65),(1.2,3.),(0.,5.8),(0.,7.),(-1.84,12.),(-2.,16.),(-2.85,22.),(-2.85,24.),(1.,24.),(5.25,24.),(5.25,26.2),(4.2,31.),(5.4,34.4),(10.,34.4),(13.8,35.),(14.4,38.3),(14.2,42.7),(11.7,44.3),(6.85,44.),(6.85,46.),(2.4,46.),(-1.85,46.),(-2.4,37.),(-7.6,38.),(-12.3,38.2),(-14.,35.7),(-14.,30.),(-12.7,28.4),(-8.,27.8),(-3.2,27.8),(-2.85,24.),(-2.85,22.),(-2.,16.),(-1.84,12.),(0.,7.),(0.,5.8),(1.2,3.),(1.65,1.65))
WATER_PROBES=((1.4,18.),(1.,33.),(1.6,42.),(0.,-12.),(17.,8.))
WALL_PROBES=tuple((s['cx'],s['cz']) for s in HOUSE_SPECS[:8] if not s.get('enterable'))
def room_route(seed,station):
 s=next(h for h in HOUSE_SPECS if h['seed']==seed);front=-s['depth']/2;wall=front+s['porch']
 points=(station,transform(s,-.3,front-.65),transform(s,-.3,front+.55),transform(s,.12,wall+.65),transform(s,.12,.65))
 return points+tuple(reversed(points[:-1]))
ROOM_ROUTES=(room_route(133,(-3.5,30.)),room_route(249,(5.8,38.)))
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
 dict(name='pavilion-still-here',eye=(6.,2.9,10.5),target=(-1.2,2.8,-4.),fov=68),
 dict(name='low-canal-houses',eye=(1.2,1.8,19.8),target=(-1.,2.7,42.),fov=66),
 dict(name='the-hollow-shop',eye=(.4,2.,31.),target=(-7.7,2.,32.7),fov=63),
 dict(name='porch-and-watersteps',eye=(1.5,1.6,-9.5),target=(-7.6,2.5,-15.),fov=69),
 dict(name='the-domestic-court',eye=(-13.8,3.5,38.),target=(-14.5,1.8,30.),fov=71),
 dict(name='village-beyond-the-bend',eye=(1.8,5.2,42.),target=(2.2,3.,100.),fov=63))

