"""Build the deep-water Void Canals district: hollow homes and exposed quays.
Run: Blender --background --python build_huxin_canals.py.
"""
from pathlib import Path
import sys,math,json,random,struct
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from temple_interior_mesh import Mesh
from prepare_huxin_moon import TILES
from canals_housekit import build_house
from g_huxin_canals_layout import *
OUT=ROOT/'art'/'temple'/'huxin_canals'

def up(mesh,points,tile):
 p=list(points);n=(Vector(p[1])-Vector(p[0])).cross(Vector(p[2])-Vector(p[0]))
 if n.y<0:p.reverse()
 # Convex floor partitions may have >4 vertices. A fan avoids Blender's
 # triangulator introducing alternate diagonals across nearly collinear cuts.
 for i in range(1,len(p)-1):mesh.face((p[0],p[i],p[i+1]),tile)

def build():
 OUT.mkdir(parents=True,exist_ok=True)
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 mat=bpy.data.materials.new('Void Canals / weathered domestic surfaces');mat.use_nodes=True
 tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(OUT/'canal_materials.png'));tex.image.pack()
 mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
 mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.98
 names=('canal_ground','canal_masonry','canal_plaster','canal_timber','canal_windows','canal_roofs','canal_bridges','canal_details','canal_interiors','canal_shadow','canal_distant','canal_water','canal_annulus','canal_recess')
 meshes={n:Mesh(n,mat,TILES) for n in names}
 ground,masonry,plaster,timber,windows,roof,bridges,details,interiors,shadow,distant,water,annulus=[meshes[n] for n in names[:13]]
 rr=random.Random(28118)

 def pave(poly,mesh=ground,y=DECK,tile='stone',sides=True):
  p=ccw(poly);up(mesh,[(x,y,z) for x,z in p],tile)
  if sides:
   for a,b in zip(p,p[1:]+p[:1]):
    mesh.face(((a[0],BANK_BOTTOM,a[1]),(b[0],BANK_BOTTOM,b[1]),(b[0],y,b[1]),(a[0],y,a[1])),'wetstone')

 for p in floor_polygons():
  cx=sum(v[0] for v in p)/len(p);cz=sum(v[1] for v in p)/len(p)
  footbridge=(-16.5<cx<-11.5 and 35.5<cz<38.6) or (12.2<cx<14.2 and (33.6<cz<35.6 or 42.7<cz<45.1))
  pave(p,tile='wood' if footbridge else 'stone',sides=False)
  if footbridge:
   # Only outside timber edges are visible; partition boundaries need no beam.
   for a,b in boundary_segments((p,),tuple(q for q in floor_polygons() if q is not p)):
    timber.beam((a[0],DECK-.12,a[1]),(b[0],DECK-.12,b[1]),.22,.16,'wood')
 # Extruding every clipped floor partition used to duplicate coplanar internal
 # walls. Build only the exposed boundary of the complete paved union instead.
 ground_edges=boundary_segments(floor_polygons(),[house_polygon(s) for s in HOUSE_SPECS]+list(source_causeway_polygons()))
 for a,b in ground_edges:
  cx,cz=(a[0]+b[0])/2,(a[1]+b[1])/2
  if (-16.5<cx<-11.5 and 35.5<cz<38.6) or (12.2<cx<14.2 and (33.6<cz<35.6 or 42.7<cz<45.1)):continue
  ground.face(((a[0],BANK_BOTTOM,a[1]),(b[0],BANK_BOTTOM,b[1]),(b[0],DECK,b[1]),(a[0],DECK,a[1])),'wetstone')

 # Extend only BELOW the unchanged pavilion/causeway foundation. Their original
 # deck and upper masonry remain byte-identical; the new water is much lower.
 masonry.lathe((0,BANK_BOTTOM,0),[(0,7.2),(DECK-1.30-BANK_BOTTOM,7.2)],'wetstone',6)
 from g_huxin_canals import PATH,path_halfwidth
 source_edges=[]
 for i,(x,z) in enumerate(PATH):
  a=PATH[max(0,i-1)];b=PATH[min(len(PATH)-1,i+1)];dx,dz=b[0]-a[0],b[1]-a[1];ln=math.hypot(dx,dz);nx,nz=dz/ln,-dx/ln
  w=path_halfwidth(z)+.065+.025*math.sin(i*1.9)
  source_edges.append(((x-nx*w,z-nz*w),(x+nx*w,z+nz*w)))
 for i,(a,b) in enumerate(zip(source_edges,source_edges[1:])):
  if not (6.1<PATH[i+1][1]<12.8):continue
  for side in (0,1):
   pa,pb=a[side],b[side]
   if pa[1]>12. and pb[1]>12.:continue
   if pa[1]>12.:
    t=(12.-pb[1])/(pa[1]-pb[1]);pa=(pb[0]+(pa[0]-pb[0])*t,12.)
   if pb[1]>12.:
    t=(12.-pa[1])/(pb[1]-pa[1]);pb=(pa[0]+(pb[0]-pa[0])*t,12.)
   masonry.face(((pa[0],BANK_BOTTOM,pa[1]),(pb[0],BANK_BOTTOM,pb[1]),(pb[0],DECK-1.30,pb[1]),(pa[0],DECK-1.30,pa[1])),'wetstone')

 def quay_edges(points,side,offset=.95):
  for a,b in zip(points,points[1:]):
   dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);nx,nz=-dz/length,dx/length
   count=max(1,round(length/.75))
   for i in range(count):
    t=(i+.5)/count;x=a[0]+dx*t+nx*offset*side;z=a[1]+dz*t+nz*offset*side
    if z<12. or any(0.<step_local(st,x,z)[0]<st['steps']*st['tread'] and abs(step_local(st,x,z)[1])<st['width']/2+.16 for st in WASHING_STAIRS):continue
    lengthstone=length/count-.025;tx,tz=dx/length,dz/length
    blend=max(0.,min(1.,(z-12.)/5.));blend=blend*blend*(3.-2.*blend)
    inset=.105*(1.-blend);x-=nx*side*inset;z-=nz*side*inset
    # Individual rough coping stones follow the water, not a city-grid paving.
    aa=(x-tx*lengthstone/2,-.08,z-tz*lengthstone/2);bb=(x+tx*lengthstone/2,-.08,z+tz*lengthstone/2)
    for row in range(8):
     yy=DECK-.16-row*.30;shift=(.10 if row%2 else -.05)*lengthstone
     masonry.beam((aa[0]+tx*shift,yy,aa[2]+tz*shift),(bb[0]+tx*shift,yy,bb[2]+tz*shift),.275,.002+.198*blend,'wetstone')
    if i%4==2:masonry.beam((aa[0],DECK-.045,aa[2]),(bb[0],DECK-.045,bb[2]),.09+.11*blend,.006+.089*blend,'stone')
 quay_edges(LEFT_QUAY,-1);quay_edges(RIGHT_QUAY,1)

 metadata=[]
 for spec in HOUSE_SPECS:
  metadata.append(build_house(meshes,spec))
  print('NEAR HOUSE',spec['seed'],flush=True)

 def arch_bridge(b,mesh=bridges):
  x0,x1,z,width,n=b['x0'],b['x1'],b['z'],b['width'],b['steps'];center=(x0+x1)/2;half=(x1-x0)/2
  for i in range(n):
   xa=x0+(x1-x0)*i/n;xb=x0+(x1-x0)*(i+1)/n;y=bridge_height((xa+xb)/2,b)
   def underside(x):
    t=abs((x-center)/(half*.91));return DECK+b['rise']-.30-t*t*3.05
   ya,yb=min(y-.22,underside(xa)),min(y-.22,underside(xb))
   up(mesh,((xa,y,z-width/2),(xb,y,z-width/2),(xb,y,z+width/2),(xa,y,z+width/2)),'stone')
   for side in (-1,1):
    zz=z+side*width/2
    mesh.face(((xa,ya,zz),(xb,yb,zz),(xb,y,zz),(xa,y,zz)),'wetstone')
    mesh.beam((xa,ya+.08,zz),(xb,yb+.08,zz),.19,.20,'stone')
    # Low, weathered parapets; modest posts instead of monumental stone rails.
    mesh.box(((xa+xb)/2,y+.32,zz),(xb-xa+.012,.64,.16),'stone')
    mesh.box(((xa+xb)/2,y+.66,zz),(xb-xa+.018,.075,.21),'cap')
   mesh.face(((xa,ya,z-width/2),(xa,ya,z+width/2),(xb,yb,z+width/2),(xb,yb,z-width/2)),'wetstone')
   if i<n-1:
    yy=bridge_height(xb+.0001,b);mesh.face(((xb,y,z-width/2),(xb,y,z+width/2),(xb,yy,z+width/2),(xb,yy,z-width/2)),'stone')
  for x in (x0,x1):
   for side in (-1,1):mesh.box((x,DECK+.44,z+side*width/2),(.24,.88,.24),'stone')
 for b in BRIDGES:arch_bridge(b)

 # Reverse canal: visible through the original pavilion, with its own bridge
 # and deeply recessed frontages. It is scenery, not a second invisible route.
 reverse_left=((-8.8,-5.0),(-4.7,-10.),(-4.4,-18.),(-4.4,-26.),(-5.8,-37.))
 reverse_right=((8.8,-4.),(5.1,-10.),(4.8,-19.),(4.5,-28.),(4.4,-38.))
 scenery_raw=ribbon(reverse_left,1.15)+ribbon(reverse_right,1.15)+rear_polygons(False)
 arch_bridge(dict(x0=-4.6,x1=4.8,z=-21.5,width=1.55,rise=.83,steps=24),distant)

 # Substantial worn washing flights expose the tall quay masonry. Several
 # descend obliquely along the water rather than projecting straight across it.
 step_data=[]
 for st in WASHING_STAIRS:
  treads=[];w=st['width']
  phase=sum(map(ord,st['id']))*.013
  def tread_sides(edge):
   return (-w/2+.016+.012*math.sin(edge*1.31+phase),w/2-.016-.012*math.sin(edge*1.17+phase+.8))
  for i in range(st['steps']):
   ta=i*st['tread'];tb=(i+1)*st['tread'];yy=DECK-STEP_DROPS[i]
   la,ra=tread_sides(i);lb,rb=tread_sides(i+1)
   # Adjacent treads share one exact riser contour. Vary the worn side edges,
   # never move front/back edges apart and expose a slit through the stair.
   poly=ccw([step_point(st,t,u) for t,u in ((ta,la),(tb,lb),(tb,w*.08),(tb,rb),(ta,ra))])
   pave(poly,masonry,yy,'stone')
   x,z=step_point(st,(ta+tb)/2)
   treads.append(dict(center=[x,yy,z],width=w,depth=st['tread'],polygon=poly))
  landing=None
  if st['landing']:
   ta,tb,ua,ub=landing_rect(st);poly=ccw(step_polygon(st,ta,tb,ua,ub));yy=DECK-STEP_DROPS[9]
   pave(poly,masonry,yy,'stone');x,z=step_point(st,(ta+tb)/2,(ua+ub)/2)
   landing=dict(center=[x,yy,z],polygon=poly,walkable=True)
  rear_apron=None
  if st.get('side')=='rear':
   house_spec=next(s for s in HOUSE_SPECS if s['seed']==st['house_seed']);plan=house_ground_plan(house_spec)
   a,b,c,d=plan['rear_landing_bounds'];rear_apron=[transform(house_spec,u,v) for u,v in ((a,plan['rearwall']+.04),(c,plan['rearwall']+.04),(c,d),(a,d))]
  step_data.append({**st,'top':[st['top'][0],DECK,st['top'][1]],'treads':treads,'landing_geometry':landing,'rear_apron':rear_apron,'bank_bottom':BANK_BOTTOM})
 # Everyday remnants, sparse enough for the spaces between them to dominate.
 # The first home's jar sits alongside its solid outer corner, clear of every
 # door approach and the capsule-width space on either side of those approaches.
 jar_corner=transform(HOUSE_SPECS[0],HOUSE_SPECS[0]['width']/2+.40,-HOUSE_SPECS[0]['depth']/2+.55)
 for x,z in ((-13.9,30.3),(13.9,42.),jar_corner,(7.1,51.5)):
  details.lathe((x,DECK,z),[(0,.19),(.12,.27),(.41,.32),(.59,.23),(.63,.25),(.67,.18)],'earth',12)
 for x,z in ((-14.7,34.),(14.,36.6)):
  details.box((x,DECK+.21,z),(.44,.42,.95),'stone')
  details.box((x,DECK+.425,z),(.29,.018,.75),'water')

 # Additional quarters follow three uneven waterways. Widths, house depths and
 # offsets advance independently; they are not a rectangular apartment grid.
 far_specs=[]
 variants=('timber_gallery','plaster','shopfront','gable','corner','arcade')
 def channel(z0,z1,xbase,phase,spacing=9.5):
  sign=1 if z1>z0 else -1;z=z0;index=0
  while (z1-z)*sign>0:
   axis=xbase+2.2*math.sin(z*.035+phase)+.7*math.sin(z*.11+phase)
   slope=.077*math.cos(z*.035+phase)+.077*math.cos(z*.11+phase)
   for side in (-1,1):
    w=rr.uniform(5.2,8.2);d=rr.uniform(5.2,7.4);floors=1 if rr.random()<.38 else 2
    height=(rr.uniform(2.65,3.85) if floors==1 else rr.uniform(4.75,6.85))
    cx=axis+side*(3.3+1.05+d/2)+rr.uniform(-.18,.18);cz=z+rr.uniform(-.7,.7)
    yaw=(-side)*math.pi/2-math.atan(slope)+rr.uniform(-.035,.035)
    s=house(cx,cz,w,d,height,floors,yaw,variants[(index+side)%6],1000+len(far_specs)*17,porch=rr.uniform(.8,1.15))
    s['detail']=1 if math.hypot(cx,cz)<80 else 0
    s['frontage_group']=f'channel-{xbase}-{z0}-{side}'
    far_specs.append(s)
   index+=1;z+=sign*(spacing+rr.uniform(-1.1,1.0))
 channel(69.,195.,1.0,.4)
 channel(-43.,-154.,.0,1.3)
 channel(5.,114.,-34.,2.2,10.)
 channel(-2.,118.,34.,4.1,10.)
 # Lateral rear rows keep broad courtyard glimpses inhabited by structures.
 for side in (-1,1):
  for i in range(8):
   z=-37.+i*11.5;x=side*(53.+rr.uniform(-2.5,2.5));w=rr.uniform(5.9,8.2);d=rr.uniform(5.5,7.4)
   floors=1 if i%3==1 else 2
   s=house(x,z,w,d,rr.uniform(2.8,3.8) if floors==1 else rr.uniform(4.7,6.7),floors,-side*math.pi/2+rr.uniform(-.08,.08),variants[i%6],2200+len(far_specs),porch=1.);s['detail']=0;s['frontage_group']=f'outer-{side}';far_specs.append(s)
 for i,s in enumerate(far_specs):
  s.update(water_y=WATER_Y,foundation_bottom=BANK_BOTTOM,decay=('intact','neglected','ruin','neglected')[i%4])
  if s['floors']>1:s.update(upper_left=.35+.19*(i%4),upper_right=.30+.23*((i+1)%4),upper_front=.65+.23*(i%4),upper_back=.35+.18*((i+2)%3))
  metadata.append(build_house(meshes,s))
  if i%12==0:print('DISTANT HOUSE',i,'/',len(far_specs),flush=True)
 # Every farther frontage belongs to a continuous bank. A varied apron follows
 # each skewed facade, then a narrow causeway connects its neighbours. This is
 # actual geometry beneath the fog, rather than isolated ledges beside houses.
 all_specs=list(HOUSE_SPECS)+far_specs
 groups={}
 for i,s in enumerate(all_specs):
  if i<16:group='left-quay' if i<6 else 'right-quay' if i<12 else 'east-side-canal' if i==15 else 'west-side-canal'
  elif i<24:group='reverse-west' if i%2==0 else 'reverse-east'
  else:group=s['frontage_group']
  s['frontage_group']=group;groups.setdefault(group,[]).append(s)
  if i>=16:
   f=-s['depth']/2;w=s['width']/2
   scenery_raw.append(ccw([transform(s,x,z) for x,z in ((-w-.10,f-1.65),(w+.10,f-1.65),(w+.10,f),(-w-.10,f))]))
 for group,specs in groups.items():
  if group in ('left-quay','right-quay','east-side-canal','west-side-canal'):continue
  ordered=sorted(specs,key=lambda s:s['cz'])
  centers=[transform(s,0.,-s['depth']/2-.80) for s in ordered]
  if len(centers)>1:scenery_raw.extend(ribbon(centers,.84))
 # Preserve the small visible break beyond the playable quarter. The reverse
 # canal continues naturally into the rear village; the playable banks do not.
 for side in ('west','east'):
  a=min(groups['reverse-'+side],key=lambda s:s['cz'])
  key='channel-0.0--43.0-'+('-1' if side=='west' else '1')
  b=max(groups[key],key=lambda s:s['cz'])
  scenery_raw.extend(ribbon((transform(a,0.,-a['depth']/2-.80),transform(b,0.,-b['depth']/2-.80)),.84))
 scenery_polygons=[]
 cuts=[list(house_polygon(s,.025)) for s in all_specs]
 cuts += [ccw(step_polygon(st,0.,st['steps']*st['tread'],-st['width']/2,st['width']/2)) for st in WASHING_STAIRS]
 for i,p in enumerate(scenery_raw):
  pieces=[p]
  for clip in scenery_raw[:i]+cuts:pieces=[q for piece in pieces for q in subtract(piece,clip)]
  for piece in pieces:
   if abs(area(piece))>1e-6 and min(math.hypot(x,z) for x,z in piece)>7.4:
    scenery_polygons.append(piece);pave(piece,distant,sides=False)
 scenery_edges=boundary_segments(scenery_polygons,[house_polygon(s) for s in all_specs])
 for a,b in scenery_edges:
  distant.face(((a[0],BANK_BOTTOM,a[1]),(b[0],BANK_BOTTOM,b[1]),(b[0],DECK,b[1]),(a[0],DECK,a[1])),'wetstone')
 print('CONTINUOUS BANKS',len(scenery_polygons),flush=True)
 # Repeated silhouettes are glimpsed at different scales, never standing alone.
 for z in (87.,126.,165.,-56.,-94.,-131.):
  axis=(1.+2.2*math.sin(z*.035+.4)+.7*math.sin(z*.11+.4)) if z>0 else 2.2*math.sin(z*.035+1.3)+.7*math.sin(z*.11+1.3)
  arch_bridge(dict(x0=axis-4.5,x1=axis+4.5,z=z,width=1.35,rise=.86,steps=22),distant)
 # A humble upper-storey passage at an unreasonable distant elevation; anchored
 # in homes on either side, with no overt floating fantasy architecture.
 for z,y in ((109.,3.15),(-79.,4.1)):
  distant.box((0,y-.09,z),(16.,.18,1.5),'wood')
  for side in (-1,1):
   for x in (-7.7,-5,-2.5,0,2.5,5,7.7):
    distant.box((x,y+.92,z+side*.65),(.09,1.85,.09),'wood')
   distant.beam((-8,y+.8,z+side*.65),(8,y+.8,z+side*.65),.07,.08,'wood')
  up(distant,((-8.2,y+2.,z),(8.2,y+2.,z),(8.2,y+1.65,z-1.),(-8.2,y+1.65,z-1.)),'roof')
  up(distant,((-8.2,y+2.,z),(8.2,y+2.,z),(8.2,y+1.65,z+1.),(-8.2,y+1.65,z+1.)),'roof')

 # The lower water exposes full stone banks. Sheet boundaries remain well
 # beyond the composed views and disappear beneath the same colour mist.
 for xi in range(-7,7):
  for zi in range(-7,9):
   x,z=xi*32,zi*32;up(water,((x,WATER_Y,z),(x+32,WATER_Y,z),(x+32,WATER_Y,z+32),(x,WATER_Y,z+32)),'water')
 annulus.lathe((0,1.20,0),[(0,.22),(0,.56),(.025,.575),(.075,.56),(.075,.22),(0,.22)],'bronze',64)
 annulus.lathe((0,1.274,0),[(0,.45),(.014,.45),(.014,.48),(0,.48)],'wetstone',64)
 for i in range(16):
  a=i*math.tau/16;annulus.beam((math.cos(a)*.50,1.278,math.sin(a)*.50),(math.cos(a)*.56,1.278,math.sin(a)*.56),.008,.006,'cap')
 all_ground=list(floor_polygons())+scenery_polygons
 footprint_polys=[ccw(house_polygon(s)) for s in all_specs]
 masonry_bank_edges=[(a,b) for a,b in ground_edges if not
  (-16.5<(a[0]+b[0])/2<-11.5 and 35.5<(a[1]+b[1])/2<38.6) and not
  (12.2<(a[0]+b[0])/2<14.2 and (33.6<(a[1]+b[1])/2<35.6 or 42.7<(a[1]+b[1])/2<45.1))]+list(scenery_edges)
 def has_ground(x,z):return any(point_in_poly(p,x,z) for p in all_ground) or any(point_in_poly(p,x,z) for p in footprint_polys)
 for s,record in zip(all_specs,metadata):
  f=-s['depth']/2;w=s['width']/2;polygon=ccw([transform(s,x,z) for x,z in ((-w,f-1.65),(w,f-1.65),(w,f),(-w,f))])
  walk=transform(s,0.,f-.72);out=transform(s,0.,f-1.72);nx,nz=out[0]-walk[0],out[1]-walk[1];ln=math.hypot(nx,nz);nx,nz=nx/ln,nz/ln
  # Record the real outer boundary of the connected apron/quay union, not an
  # invented nominal shore immediately outside a doorway.
  waterprobe=None;edgecenter=None
  for j in range(1,71):
   distance=j*.12;x,z=walk[0]+nx*distance,walk[1]+nz*distance
   if not has_ground(x,z):
    edgecenter=(x-nx*.06,z-nz*.06);waterprobe=(x+nx*.30,z+nz*.30);break
  if edgecenter is None:edgecenter=out;waterprobe=(out[0]+nx,out[1]+nz)
  # Probe an actual masonry edge, never the intentionally open underside of a
  # timber crossing. Previously redundant internal walls concealed that error.
  candidates=[]
  for a,b in masonry_bank_edges:
   dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
   if length<.18:continue
   ex,ez=dz/length,-dx/length
   if ex*nx+ez*nz<.70:continue
   t=max(.15,min(.85,((walk[0]-a[0])*dx+(walk[1]-a[1])*dz)/(length*length)))
   q=(a[0]+dx*t,a[1]+dz*t);distance=math.dist(q,walk)
   hx,hz=q[0]-s['cx'],q[1]-s['cz'];hl=math.hypot(hx,hz)
   if distance>8. or hl<.1 or (hx*ex+hz*ez)/hl<.76:continue
   candidates.append((distance,q,ex,ez,dx/length,dz/length,min(.32,length*.12)))
  selected_edge=None
  if candidates:
   _,edgecenter,ex,ez,tx,tz,half=min(candidates,key=lambda c:c[0]);nx,nz=ex,ez
   selected_edge=[(edgecenter[0]-tx*half,edgecenter[1]-tz*half),(edgecenter[0]+tx*half,edgecenter[1]+tz*half)]
   waterprobe=(edgecenter[0]+nx*.35,edgecenter[1]+nz*.35)
  neighbours=sorted(groups[s['frontage_group']],key=lambda h:h['cz']);index=neighbours.index(s)
  record['frontage']=dict(polygon=polygon,walk_point=walk,water_edge=selected_edge or [(edgecenter[0]-nz*.42,edgecenter[1]+nx*.42),(edgecenter[0]+nz*.42,edgecenter[1]-nx*.42)],water_probe=waterprobe,normal=[nx,nz],walk_y=DECK,bank_bottom=BANK_BOTTOM,group=s['frontage_group'],connected_to=[h['seed'] for h in neighbours[max(0,index-1):index+2] if h is not s])
 blocked_ends=[]
 for name,path,left,right in (('west broken quay',LEFT_QUAY,2.65,.95),('east broken quay',RIGHT_QUAY,.95,2.7)):
  a,b=path[-2:];dx,dz=b[0]-a[0],b[1]-a[1];ln=math.hypot(dx,dz);dx,dz=dx/ln,dz/ln
  edge=((b[0]-dz*left,b[1]+dx*left),(b[0]+dz*right,b[1]-dx*right))
  blocked_ends.append(dict(name=name,approach=(b[0]-dx*.8,b[1]-dz*.8),beyond=(b[0]+dx*1.3,b[1]+dz*1.3),edge=edge))
  # Broken coping, sunken fragments and severed timber make the limit physical.
  for i in range(5):
   t=(i+.35)/5;x=edge[0][0]+(edge[1][0]-edge[0][0])*t;z=edge[0][1]+(edge[1][1]-edge[0][1])*t
   details.box((x,DECK-.19-i*.025,z-.08),(.26+.07*(i%2),.32,.30),'wetstone')
   masonry.box((x+dx*.65,WATER_Y-.08+(i%2)*.10,z+dz*.65),(.38,.42,.48),'wetstone')
  timber.beam((b[0],DECK-.25,b[1]-.10),(b[0]+dx*.70,DECK-.55,b[1]+dz*.70),.13,.11,'wood')
 manifest=dict(version=4,models={},houses=metadata,building_count=len(metadata),near_houses=len(HOUSE_SPECS),
   water=WATER_Y,deck=DECK,upper=UPPER,playable_bounds=[-20.,-7.2,21.,64.5],world_bounds=[-224.,-224.,224.,288.],
   floor_polygons=floor_polygons(),scenery_floor_polygons=scenery_polygons,ground_patches=[],washing_steps=step_data,blocked_ends=blocked_ends,
   door_routes=DOOR_ROUTES,washing_routes=WASHING_ROUTES,through_house_routes=THROUGH_HOUSE_ROUTES,
   bank_edges=ground_edges,scenery_bank_edges=scenery_edges,source_join_span=source_join_span(),
   walkable_models=['canal_ground','canal_bridges','canal_interiors','canal_shadow','canal_masonry'],
   camera_views=REVIEW_VIEWS,notes=['Original pavilion retained completely; no new floor within its hexagon.',
   'Canal water is 1.875 metres below the original deck; all banks and pavilion foundations reach below it.','Individually authored hollow homes: real apertures, deep porches, varied heights and reduced upper floors.',
   'Sixteen enterable houses; nine lead through real rear doors to private washing flights. Fifteen of twenty-four flights are behind homes.',
   'Paving walls follow the exposed polygon-union boundary, with the original causeway cross-section matched exactly at z12.'])
 for name,mesh in meshes.items():
  if not mesh.faces:continue
  result=mesh.export(OUT);coords=mesh.vertices;result['bounds']=[[min(p[j] for p in coords) for j in range(3)],[max(p[j] for p in coords) for j in range(3)]]
  raw=(OUT/(name+'.glb')).read_bytes();n=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+n]);actual=sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives'])
  result['authored_triangles']=result['triangles'];result['triangles']=actual
  manifest['models'][name]=result
 manifest['total_triangles']=sum(m['triangles'] for m in manifest['models'].values())
 (OUT/'canals_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'void_canals.blend'))
 print('VOID CANALS V4 COMPLETE',len(metadata),'houses',manifest['total_triangles'],'triangles',flush=True)
if __name__=='__main__':build()

