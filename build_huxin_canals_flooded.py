"""Build the second Void Canals district: small hollow homes and crooked waterways.
Run: Blender --background --python build_huxin_canals_flooded.py.
"""
from pathlib import Path
import sys,math,json,random,struct
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from temple_interior_mesh import Mesh
from prepare_huxin_moon import TILES
from canals_flooded_housekit import build_house
from g_huxin_canals_flooded_layout import *
OUT=ROOT/'art'/'temple'/'huxin_canals_flooded'

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

 def pave(poly,mesh=ground,y=DECK,tile='stone'):
  p=ccw(poly);up(mesh,[(x,y,z) for x,z in p],tile)
  for a,b in zip(p,p[1:]+p[:1]):
   mesh.face(((a[0],-.9,a[1]),(b[0],-.9,b[1]),(b[0],y,b[1]),(a[0],y,a[1])),'wetstone')

 for p in floor_polygons():pave(p)

 def quay_edges(points,side,offset=.95):
  for a,b in zip(points,points[1:]):
   dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);nx,nz=-dz/length,dx/length
   count=max(1,round(length/.75))
   for i in range(count):
    t=(i+.5)/count;x=a[0]+dx*t+nx*offset*side;z=a[1]+dz*t+nz*offset*side
    lengthstone=length/count-.025;tx,tz=dx/length,dz/length
    # Individual rough coping stones follow the water, not a city-grid paving.
    aa=(x-tx*lengthstone/2,-.08,z-tz*lengthstone/2);bb=(x+tx*lengthstone/2,-.08,z+tz*lengthstone/2)
    masonry.beam(aa,bb,.24,.34,'wetstone')
    if i%4==2:masonry.beam((aa[0],DECK-.045,aa[2]),(bb[0],DECK-.045,bb[2]),.20,.095,'stone')
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
    t=abs((x-center)/(half*.91));return DECK+b['rise']-.30-t*t*1.65
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
 for points in (reverse_left,reverse_right):
  for p in ribbon(points,1.15):
   pieces=[p]
   for s in HOUSE_SPECS:pieces=[q for t in pieces for q in subtract(t,list(house_polygon(s,.04)))]
   for piece in pieces:
    if min(math.hypot(x,z) for x,z in piece)>7.6:pave(piece,distant)
 arch_bridge(dict(x0=-4.6,x1=4.8,z=-21.5,width=1.55,rise=.83,steps=24),distant)

 # Worn washing stairs descend obliquely into the same water as the lake.
 # No large square contemporary platforms; every run follows its own frontage.
 step_data=[]
 for x,z,angle,width in ((-4.0,-14.,-.52,1.25),(4.35,-28.5,math.pi+.32,1.15),
                         (-1.0,17.8,-.42,1.15),(3.6,31.0,math.pi+.3,1.1),
                         (-.8,51.,-.25,1.25)):
  dx,dz=math.cos(angle),math.sin(angle);nx,nz=-dz,dx
  for i in range(7):
   cx,cz=x+dx*(i*.30),z+dz*(i*.30);y=DECK-i*.12
   a=(cx-nx*width/2,y-.075,cz-nz*width/2);b=(cx+nx*width/2,y-.075,cz+nz*width/2)
   masonry.beam(a,b,.15,.33,'wetstone')
  step_data.append(dict(top=[x,DECK,z],angle=angle,width=width,steps=7))
 # Everyday remnants, sparse enough for the spaces between them to dominate.
 for x,z in ((-13.9,30.3),(13.9,42.),(-3.7,19.),(7.1,51.5)):
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
    height=(rr.uniform(2.7,3.3) if floors==1 else rr.uniform(4.8,5.7))
    cx=axis+side*(3.3+1.05+d/2)+rr.uniform(-.18,.18);cz=z+rr.uniform(-.7,.7)
    yaw=(-side)*math.pi/2-math.atan(slope)+rr.uniform(-.035,.035)
    s=house(cx,cz,w,d,height,floors,yaw,variants[(index+side)%6],1000+len(far_specs)*17,porch=rr.uniform(.8,1.15))
    s['detail']=1 if math.hypot(cx,cz)<80 else 0
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
   s=house(x,z,w,d,rr.uniform(4.8,5.6),2,-side*math.pi/2+rr.uniform(-.08,.08),variants[i%6],2200+len(far_specs),porch=1.);s['detail']=0;far_specs.append(s)
 for i,s in enumerate(far_specs):
  metadata.append(build_house(meshes,s))
  # Long, irregular quay ledges bind neighbouring houses to their waterway.
  front=-s['depth']/2;corners=[transform(s,x,z) for x,z in ((-s['width']/2-.5,front-1.3),(s['width']/2+.5,front-1.3),(s['width']/2+.5,front),(-s['width']/2-.5,front))]
  pave(corners,distant)
  if i%12==0:print('DISTANT HOUSE',i,'/',len(far_specs),flush=True)
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

 # New world and retained lake share a single water datum. Sheet boundaries
 # are far beyond all composed views and fade beneath the same colour fog.
 for xi in range(-7,7):
  for zi in range(-7,9):
   x,z=xi*32,zi*32;up(water,((x,0,z),(x+32,0,z),(x+32,0,z+32),(x,0,z+32)),'water')
 annulus.lathe((0,1.20,0),[(0,.22),(0,.56),(.025,.575),(.075,.56),(.075,.22),(0,.22)],'bronze',64)
 annulus.lathe((0,1.274,0),[(0,.45),(.014,.45),(.014,.48),(0,.48)],'wetstone',64)
 for i in range(16):
  a=i*math.tau/16;annulus.beam((math.cos(a)*.50,1.278,math.sin(a)*.50),(math.cos(a)*.56,1.278,math.sin(a)*.56),.008,.006,'cap')
 manifest=dict(version=2,models={},houses=metadata,building_count=len(metadata),near_houses=len(HOUSE_SPECS),
   water=WATER_Y,deck=DECK,upper=UPPER,playable_bounds=[-16.,-7.2,16.,58.],world_bounds=[-224.,-224.,224.,288.],
   floor_polygons=floor_polygons(),ground_patches=[],washing_steps=step_data,
   walkable_models=['canal_ground','canal_bridges','canal_interiors','canal_shadow'],
   camera_views=REVIEW_VIEWS,notes=['Original pavilion retained completely; no new floor within its hexagon.',
   'Water datum is 0, exactly the unchanged lake.','Individually authored hollow homes: real apertures, deep porches, curved tile roofs.',
   'Compact crooked quay loop, two walkable bridges and two modest enterable vacant shops.'])
 for name,mesh in meshes.items():
  if not mesh.faces:continue
  result=mesh.export(OUT);coords=mesh.vertices;result['bounds']=[[min(p[j] for p in coords) for j in range(3)],[max(p[j] for p in coords) for j in range(3)]]
  raw=(OUT/(name+'.glb')).read_bytes();n=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+n]);actual=sum(doc['accessors'][p['indices']]['count']//3 for m in doc['meshes'] for p in m['primitives'])
  result['authored_triangles']=result['triangles'];result['triangles']=actual
  manifest['models'][name]=result
 manifest['total_triangles']=sum(m['triangles'] for m in manifest['models'].values())
 (OUT/'canals_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'void_canals.blend'))
 print('VOID CANALS V2 COMPLETE',len(metadata),'houses',manifest['total_triangles'],'triangles',flush=True)
if __name__=='__main__':build()

