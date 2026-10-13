"""Build the Hollow Garden in Blender, including a walkable upper/lower rock maze."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
import bmesh
import math
import random
import json
import numpy as np
from mathutils import Vector
from temple_interior_mesh import Mesh
from build_bamboo_grove import tube,leaf
from prepare_rockery import TILES
from g_rockery import (NODES,EDGES,ROOMS,SHOTS,LIGHTS,POND,PAVILION,OBSTACLES,
                      edge_height,stair_profile,stair_boundaries,edge_frame,cut_radius,UPPER_ROUTE)

OUT=ROOT/'art'/'temple'/'rockery'

def material(name,path):
    m=bpy.data.materials.new(name);m.use_nodes=True;tex=m.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(OUT/path));tex.image.pack();bs=m.node_tree.nodes.get('Principled BSDF')
    m.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.95
    return m

def uv_planar(points,tile,scale=.45):
    index=TILES.index(tile);u=index%4/4+.0645;v=1-(index//4+1)/4+.0645
    return [(u+(p[0]*scale%1)*.121,v+(p[2]*scale%1)*.121) for p in points]

def plank(mesh,a,b,width,top,thickness,tile):
    a,b=Vector(a),Vector(b);delta=b-a;normal=Vector((delta.z,0,-delta.x)).normalized()*width/2
    p=[a-normal,b-normal,b+normal,a+normal]
    p=[(v.x,top,v.z) for v in p];q=[(x,top-thickness,z) for x,y,z in p]
    mesh.face(p,tile);mesh.face(q[::-1],tile)
    for i in range(4):mesh.face((p[i],q[i],q[(i+1)%4],p[(i+1)%4]),tile)

def hewn_slab(mesh,outline,height,seed):
    """A level walking face with a chipped lip and rough, buried limestone sides."""
    rr=random.Random(seed);center=sum((Vector(p) for p in outline),Vector())/len(outline)
    top=[];lip=[];base=[]
    for p in outline:
        p=Vector(p);radial=p-center;radial.y=0;radial.normalize()
        top.append((p.x,height,p.z))
        q=p+radial*rr.uniform(.018,.038)
        lip.append((q.x,height-rr.uniform(.010,.022),q.z))
        q=p+radial*rr.uniform(.015,.065)
        base.append((q.x,height-.24,q.z))
    mesh.face(top,'limestone');mesh.face(base[::-1],'limestone')
    for i in range(len(top)):
        j=(i+1)%len(top)
        mesh.face((top[i],lip[i],lip[j],top[j]),'limestone')
        mesh.face((lip[i],base[i],base[j],lip[j]),'limestone')


def carved_tread(mesh,na,nb,radius,index,breaks,heights):
    a,b=NODES[na],NODES[nb];sloping=abs(a[1]-b[1])>.1;h=heights[index]
    lo,hi=breaks[index:index+2];grid=[]
    for v in (0,.24,.64,1):
        row=[]
        for s in (-1,-.75,-.5,-.25,0,.25,.5,.75,1):
            mid,_=edge_frame(na,nb,(lo+hi)/2);lateral=cut_radius(mid[0],mid[2],radius)*s
            boundaries=stair_boundaries(a,b,lateral) if sloping else breaks
            t=boundaries[index]*(1-v)+boundaries[index+1]*v
            p,d=edge_frame(na,nb,t);width=cut_radius(p[0],p[2],radius)
            x,z=p[0]+d[1]*width*s,p[2]-d[0]*width*s
            wear=.014*(1-s*s)*math.sin(v*math.pi)
            chips=.052*abs(s)**6*(.55+.45*math.sin(x*7.9+z*5.3))
            y=h+.005*math.sin(x*5.1+z*3.9)-wear-chips
            # Irregular lowered noses and a shallow dish, not a planar slab top.
            if v==0:y-=.009*(.6+.4*math.sin(x*11+z*8))
            row.append((x,y,z))
        grid.append(row)
    for row in range(len(grid)-1):
        for col in range(len(grid[0])-1):
            mesh.face((grid[row][col],grid[row+1][col],grid[row+1][col+1],grid[row][col+1]),'limestone')
    outline=[row[0] for row in grid]+grid[-1][1:]+[row[-1] for row in grid[-2::-1]]+grid[0][-2:0:-1]
    base=[(x,h-.24,z) for x,y,z in outline]
    mesh.face(base[::-1],'limestone')
    for i in range(len(outline)):
        j=(i+1)%len(outline);mesh.face((outline[i],base[i],base[j],outline[j]),'limestone')


def rock_shoulder(mesh,center,direction,seed):
    """Low, irregular rock left beside the cut, without a balustrade silhouette."""
    rr=random.Random(seed);cx,h,cz=center;dx,dz=direction;nx,nz=dz,-dx
    profile=((-.20,1.02),(.07,1.0),(rr.uniform(.20,.35),.67))
    points=[];radii=[rr.uniform(.85,1.13) for _ in range(7)]
    for y,scale in profile:
        points.append([(cx+(dx*math.cos(i*math.tau/7)*.48+nx*math.sin(i*math.tau/7)*.17)*radii[i]*scale,
                        h+y,cz+(dz*math.cos(i*math.tau/7)*.48+nz*math.sin(i*math.tau/7)*.17)*radii[i]*scale) for i in range(7)])
    mesh.face(points[-1],'limestone')
    for row in range(2):
        for i in range(7):
            j=(i+1)%7;mesh.face((points[row][i],points[row][j],points[row+1][j],points[row+1][i]),'limestone')


def rock_path_edges(mesh):
    """Stone remnants follow the same gently curved path as the cut treads."""
    for side in (-1,1):
        for i,(na,nb) in enumerate(zip(UPPER_ROUTE,UPPER_ROUTE[1:])):
            a,b=NODES[na],NODES[nb];length=math.hypot(b[0]-a[0],b[2]-a[2]);count=max(1,round(length/.84))
            for j in range(count):
                t=(j+.5+.17*math.sin(j*7.1+i*2.3))/count;p,d=edge_frame(na,nb,t)
                offset=(cut_radius(p[0],p[2],.92)+.19)*side;h=edge_height(a,b,t,offset)
                rock_shoulder(mesh,(p[0]+d[1]*offset,h,p[2]-d[0]*offset),d,5141+i*137+j*19+side*11)


def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mat=material('Porous limestone, moss, timber and grey tiles','materials.png');letter=material('Carved garden inscriptions','inscriptions.png')
    names=('garden_floor','stone_paths','high_walk','garden_walls','garden_roofs','pavilion','garden_props','garden_plants','garden_lamps','garden_water')
    meshes={n:Mesh(n,mat,TILES) for n in names};inscriptions=Mesh('garden_inscriptions',letter);meshes[inscriptions.name]=inscriptions
    floor,paths,high,walls,roofs,pavilion,props,plants,lamps,water=[meshes[n] for n in names];rng=random.Random(13987)
    for x in range(-27,27,2):
        for z in range(-35,37,2):floor.face(((x,-.018,z),(x,-.018,z+2),(x+2,-.018,z+2),(x+2,-.018,z)),'earth')
    for edge_index,(na,nb,r,roofed) in enumerate(EDGES):
        a,b=NODES[na],NODES[nb];length=math.hypot(b[0]-a[0],b[2]-a[2]);elevated=max(a[1],b[1])>.2
        m=high if elevated else paths
        if abs(a[1]-b[1])>.1:
            breaks,heights=stair_profile(a,b)
            spans=list(zip(breaks,breaks[1:]))
        else:
            n=max(1,math.ceil(length/.65));breaks=tuple(j/n for j in range(n+1));heights=(a[1],)*n
            spans=list(zip(breaks,breaks[1:]))
        for step_index,(lo,hi) in enumerate(spans):
            t=(lo+hi)/2;h=edge_height(a,b,t)
            p=tuple(a[i]+(b[i]-a[i])*lo for i in range(3));q=tuple(a[i]+(b[i]-a[i])*hi for i in range(3))
            if elevated:carved_tread(m,na,nb,r,step_index,breaks,heights)
            else:plank(m,p,q,r*2+.06,h,.10,'pebble')
    rock_path_edges(high)
    for name,(x,h,z) in NODES.items():
        if h>.2:
            circle=[(x+math.cos(-i*math.tau/16)*.98,h,z+math.sin(-i*math.tau/16)*.98) for i in range(16)]
            hewn_slab(high,circle,h,1159+list(NODES).index(name)*59)
            continue
        m=paths;m.lathe((x,h-.20,z),[(0,.96),(.20,.96)],'pebble',20)
        # Close each junction disk with an upward facing surface.
        circle=[(x+math.cos(i*math.tau/24)*.95,h,z+math.sin(i*math.tau/24)*.95) for i in range(24)]
        m.face(circle[::-1],'cap' if h>.2 else 'pebble')
    for name,cx,cz,rx,rz,h,roofed in ROOMS:
        for i in range(64):
            a=i*math.tau/64;b=(i+1)*math.tau/64
            p=((cx,h,cz),(cx+math.cos(b)*rx,h,cz+math.sin(b)*rz),(cx+math.cos(a)*rx,h,cz+math.sin(a)*rz))
            paths.face(p,'pebble',uv=uv_planar(p,'pebble',.22))
    # Quiet perimeter architecture keeps this legibly a Chinese garden.
    for side in (-1,1):
        walls.box((side*22,1.65,0),(.38,3.3,61),'plaster')
        walls.box((side*21.75,.32,0),(.18,.64,61),'cap')
        for z in range(-30,31):
            roofs.box((side*22,3.36,z),(.68,.15,1.03),'roof')
            if z%3==0:props.box((side*21.68,1.9,z),(.12,1.3,1.2),'wood')
    # Front moon gate, with a physically open circular doorway.
    for side in (-1,1):walls.box((side*12.0,1.9,30.5),(19.8,3.8,.4),'plaster')
    radius=1.65;cy=1.65
    for i in range(48):
        a=i*math.tau/48;b=(i+1)*math.tau/48
        def edge(t):
            c,s=math.cos(t),math.sin(t);f=min(2.1/max(abs(c),.001),(2.15 if s>0 else 1.65)/max(abs(s),.001))
            return (c*f,cy+s*f,30.3)
        p=[(radius*math.cos(a),cy+radius*math.sin(a),30.3),(radius*math.cos(b),cy+radius*math.sin(b),30.3),edge(b),edge(a)]
        walls.face(p,'plaster');walls.face([(x,y,z+.4) for x,y,z in p[::-1]],'plaster')
        tube(props,(math.cos(a)*1.70,cy+math.sin(a)*1.70,30.22),(math.cos(b)*1.70,cy+math.sin(b)*1.70,30.22),.095,'cap',8,end=.095)
    for x in range(-22,23):roofs.box((x,3.87,30.5),(1.04,.18,.75),'roof')
    inscriptions.face(((-1.1,3.35,30.20),(-1.1,3.78,30.20),(1.1,3.78,30.20),(1.1,3.35,30.20)),0)
    # Rear covered gallery; lattice bays and tiled eaves frame the open sky court.
    walls.box((0,1.75,-28.9),(44,3.5,.38),'plaster');walls.box((0,.3,-28.6),(44,.6,.25),'cap')
    for x in range(-21,22,3):
        props.lathe((x,.08,-27.4),[(0,.18),(.2,.18),(3.2,.12),(3.35,.17)],'wood',10)
        props.box((x,3.32,-27.4),(3.1,.22,.22),'wood')
        if abs(x)>4:
            props.box((x,1.95,-28.65),(1.6,1.7,.08),'wood')
            for dx in (-.6,-.3,0,.3,.6):props.box((x+dx,1.95,-28.53),(.045,1.5,.08),'cap')
            for y in (1.35,1.65,1.95,2.25,2.55):props.box((x,y,-28.53),(1.4,.035,.08),'cap')
    for x in range(-23,23):
        for j in range(6):
            za=-30+j*.62;zb=za+.62;ya=4.1-.22*j+.06*max(0,j-3)**2;yb=4.1-.22*(j+1)+.06*max(0,j-2)**2
            p=[(x,ya,za),(x+1,ya,za),(x+1,yb,zb),(x,yb,zb)]
            roofs.face(p[::-1],'roof');roofs.face([(xx,yy-.09,zz) for xx,yy,zz in p],'wood')
    # A six-sided pavilion, open on every side, appears beyond the final slit.
    cx,cz,r=PAVILION
    pavilion.lathe((cx,-.05,cz),[(0,3.08),(.13,3.08)],'cap',6)
    for i in range(6):
        a=i*math.tau/6;b=(i+1)*math.tau/6;x=cx+math.cos(a)*r;z=cz+math.sin(a)*r
        pavilion.lathe((x,.08,z),[(0,.20),(.15,.21),(.30,.14),(3.25,.115),(3.42,.18)],'wood',12)
        bx=cx+math.cos(b)*r;bz=cz+math.sin(b)*r;pavilion.beam((x,3.42,z),(bx,3.42,bz),.2,.25,'wood')
        for j in range(4):pavilion.box((x,3.35+j*.11,z),(.3+j*.1,.10,.31+j*.1),'wood')
        # Roof sector is tessellated into curved tile rows, with complete undersides.
        def point(t,s):
            xx=math.cos(a)*(1-s)+math.cos(b)*s;zz=math.sin(a)*(1-s)+math.sin(b)*s
            return (cx+xx*3.65*t,3.82+1.88*(1-t)**2+.32*t**8,cz+zz*3.65*t)
        for row in range(12):
            for col in range(10):
                t=row/12;tt=(row+1)/12;s=col/10;ss=(col+1)/10
                p=[point(t,s),point(tt,s),point(tt,ss),point(t,ss)]
                roofs.face(p[::-1],'roof');roofs.face([(xx,yy-.08,zz) for xx,yy,zz in p],'wood')
        for j in range(12):
            p=point(j/12,0);q=point((j+1)/12,0);tube(roofs,p,q,.055,'roof',6,end=.055)
    roofs.lathe((cx,5.67,cz),[(0,.23),(.15,.26),(.35,.12),(.50,.16),(.64,.001)],'bronze',12)
    # A dark pond and low, folded banks occupy one side of the wider final court.
    px,pz,rx,rz=POND
    for i in range(64):
        a=i*math.tau/64;b=(i+1)*math.tau/64
        water.face(((px,.102,pz),(px+math.cos(b)*rx,.102,pz+math.sin(b)*rz),(px+math.cos(a)*rx,.102,pz+math.sin(a)*rz)),'wetstone')
        p=(px+math.cos(a)*(rx+.04),.16,pz+math.sin(a)*(rz+.04));q=(px+math.cos(b)*(rx+.04),.16,pz+math.sin(b)*(rz+.04))
        tube(props,p,q,.115,'mossrock',7,end=.12)
    for i in range(12):
        a=rng.random()*math.tau;rngrad=rng.uniform(.2,.85);x=px+math.cos(a)*rx*rngrad;z=pz+math.sin(a)*rz*rngrad
        petals=[(x+math.cos(j*math.tau/12)*.19,.114,z+math.sin(j*math.tau/12)*.19) for j in range(12)];plants.face(petals[::-1],'leaf')
    # Warm lantern niches identify turns without making every cave bright.
    for i,(x,y,z) in enumerate(LIGHTS):
        props.lathe((x,.08,z),[(0,.25),(.10,.28),(.22,.15),(y-.34,.10),(y-.25,.23)],'cap',10)
        lamps.lathe((x,y-.24,z),[(0,.09),(.05,.16),(.28,.19),(.38,.12),(.42,.05)],'paper',12)
        props.lathe((x,y+.18,z),[(0,.23),(.07,.25),(.17,.07),(.2,.001)],'roof',8)
    # Ferns in cavities, roots and restrained peach blossom at the open court.
    for na,nb,r,roofed in EDGES:
        a,b=NODES[na],NODES[nb];length=math.hypot(b[0]-a[0],b[2]-a[2]);dx=(b[0]-a[0])/length;dz=(b[2]-a[2])/length
        if max(a[1],b[1])>.2:continue
        for j in range(max(1,int(length/2.2))):
            t=(j+.5)/max(1,int(length/2.2));side=1 if j%2 else -1
            x=a[0]+(b[0]-a[0])*t+dz*(r+.055)*side;z=a[2]+(b[2]-a[2])*t-dx*(r+.055)*side
            facing=math.atan2(dx*side,-dz*side)
            for k in range(6):
                angle=facing+(k-2.5)*.34
                for q in range(6):
                    f=(q+1)/7;p=(x+math.cos(angle)*f*.6,.1+math.sin(f*math.pi)*.45,z+math.sin(angle)*f*.6)
                    for sign in (-1,1):leaf(plants,p,angle+sign*.8,.19*(1-f)+.025,.027,'leaflight',-.035)
    for i in range(240):
        x=rng.uniform(-19,19);z=rng.uniform(-25,24)
        from g_rockery import surfaces
        if surfaces(x,z,.0):continue
        for branch in range(5):
            a=rng.random()*math.tau
            for j in range(5):
                t=(j+1)/6;p=(x+math.cos(a)*t*.6,.09+math.sin(t*math.pi)*.36,z+math.sin(a)*t*.6)
                for side in (-1,1):leaf(plants,p,a+side,.22*(1-t)+.05,.028,'leaflight',-.035)
    for x,z,seed in ((-9,-24,47),(8,-25,91),(-17,13,31),(17,10,77)):
        rr=random.Random(seed);tube(plants,(x,-.01,z),(x+.45,4.2,z+.25),.25,'wood',9,end=.11)
        for branch in range(8):
            a=rr.random()*math.tau;length=rr.uniform(1.8,3.6);end=(x+math.cos(a)*length,rr.uniform(3.5,6.),z+math.sin(a)*length)
            tube(plants,(x+.2,2.5,z),end,.085,'wood',7,end=.019)
            for k in range(12):
                p=(end[0]+rr.uniform(-.7,.7),end[1]+rr.uniform(-.4,.4),end[2]+rr.uniform(-.7,.7))
                for j in range(4):leaf(plants,p,a+(j-1.5),.40,.08,'leaf',-.08)
                if z<-20 and k%3==0:
                    for j in range(5):
                        a2=j*math.tau/5;plants.ellipsoid((p[0]+math.cos(a2)*.055,p[1],p[2]+math.sin(a2)*.055),(.064,.047,.063),'flower',5,3)
    # The carved mesh is split into spatial pieces for portable GLB index buffers.
    triangles=np.load(OUT/'rockery_geometry.npz')['triangles'];centers=triangles.mean(axis=1)
    for n in range(6):
        selected=((centers[:,0]>=0).astype(int)+2*np.clip(((centers[:,2]+28)/18).astype(int),0,2))==n
        rock=Mesh('taihu_rockery_'+str(n),mat,TILES);meshes[rock.name]=rock
        for tri in triangles[selected]:rock.face(tri,'limestone',smooth=True)
    counts={}
    for name,m in meshes.items():
        counts[name]=m.export(OUT);print(name,counts[name],flush=True)
    (OUT/'manifest.json').write_text(json.dumps(dict(separate_scene=True,models=counts,total_triangles=sum(v['triangles'] for v in counts.values()),
        enemy_count=0,encounter_areas='encounters.json',rockery_layers=2),indent=2))
    bpy.ops.object.camera_add(location=(17,19,15));cam=bpy.context.object;target=Vector((0,-2,1.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=35;bpy.context.scene.camera=cam
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'hollow_garden.blend'),compress=True)

if __name__=='__main__':build()
