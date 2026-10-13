"""Bake limestone surfaces and a porous, carved rockery field using only NumPy."""
from pathlib import Path
import json
import math
import random
import numpy as np
from g_rockery import NODES,EDGES,ROOMS,SHOTS,ENCOUNTERS,stair_limits,edge_path

ROOT=Path(__file__).parent;OUT=ROOT/'art'/'temple'/'rockery'
TILES=('limestone','wetstone','mossrock','pebble','wood','roof','plaster','cap','leaf','leaflight','bronze','paper','earth','moss','flower','cloth')

def textures():
    from PIL import Image,ImageDraw,ImageFont
    src=Image.open(OUT/'materials_source.png').convert('RGB');w,h=src.size
    panels=[src.crop((i%2*w//2,i//2*h//2,(i%2+1)*w//2,(i//2+1)*h//2)).resize((128,128),Image.Resampling.LANCZOS) for i in range(4)]
    old=Image.open(ROOT/'art'/'temple'/'bamboo'/'materials.png').convert('RGB');oldnames=('bamboo','node','leaf','leaflight','earth','moss','stone','plaster','wood','roof','flower','bronze','paper','cloth','cap','water')
    atlas=Image.new('RGB',(1024,1024))
    for i,name in enumerate(TILES):
        if i<4:tile=panels[i]
        else:
            n=oldnames.index(name);tile=old.crop((n%4*256+64,n//4*256+64,n%4*256+192,n//4*256+192))
        atlas.paste(Image.fromarray(np.pad(np.asarray(tile),((64,64),(64,64),(0,0)),mode='edge')),(i%4*256,i//4*256))
    atlas.save(OUT/'materials.png')
    # Exact text is a carved plaque, supplied as a separate square atlas tile.
    fontpath=next(p for p in (Path('C:/Windows/Fonts/simkai.ttf'),Path('C:/Windows/Fonts/simsun.ttc')) if p.exists())
    atlas=Image.new('RGB',(1024,1024),(70,76,68))
    for i,text in enumerate(('叠石迷园','初极狭 才通人','豁然开朗','别有洞天')):
        im=Image.new('RGB',(768,256),(65,75,68));d=ImageDraw.Draw(im);font=ImageFont.truetype(str(fontpath),106 if i==1 else 140)
        box=d.textbbox((0,0),text,font=font);d.text(((768-(box[2]-box[0]))/2,52),text,font=font,fill=(172,169,135))
        d.rectangle((9,9,758,246),outline=(119,124,106),width=6)
        atlas.paste(im.resize((512,512),Image.Resampling.LANCZOS),(i%2*512,i//2*512))
    atlas.save(OUT/'inscriptions.png')
    (OUT/'encounters.json').write_text(json.dumps(dict(enabled=False,areas=ENCOUNTERS),indent=2),encoding='utf-8')

def field():
    step=.24
    xs=np.arange(-20,20.001,step,dtype=np.float32);ys=np.arange(-.45,10.2,step,dtype=np.float32);zs=np.arange(-28,24.01,step,dtype=np.float32)
    x,y,z=np.meshgrid(xs,ys,zs,indexing='ij');shape=x.shape;rock=np.full(shape,100,dtype=np.float32)
    rng=random.Random(13105)
    # Stacked limestone lobes make separate pinnacles and folded bases, not cliffs.
    for gx in range(-16,18,3):
        for gz in range(-18,23,3):
            if (gx/18)**2+((gz-1)/24)**2>1.2:continue
            xx=gx+rng.uniform(-.6,.6);zz=gz+rng.uniform(-.7,.7);height=rng.uniform(3.7,7.0)
            if -8<gx<9 and 5<gz<15:height+=1.3
            for j in range(2):
                yy=height*(.24 if not j else .68);rx=rng.uniform(1.6,2.8)*(1 if not j else .74)
                ry=height*(.43 if not j else .36);rz=rng.uniform(1.8,2.9)*(1 if not j else .77)
                value=(np.sqrt(((x-xx)/rx)**2+((y-yy)/ry)**2+((z-zz)/rz)**2)-1)*min(rx,ry,rz)
                rock=np.minimum(rock,value)
    # Scale-separated wrinkles produce the thin, folded Taihu silhouettes.
    wrinkle=.14*np.sin(x*3.7+np.sin(z*2.0))*np.sin(y*4.4+z*1.8)
    wrinkle+=.11*np.sin(z*5.2+x*1.8)*np.cos(y*3.8+x*1.9)
    rock+=wrinkle
    # Erosion hollows connect through the stacks, leaving genuine perforations.
    for i in range(225):
        xx=rng.uniform(-17,17);zz=rng.uniform(-20,22);yy=rng.uniform(.8,7.2)
        rx=rng.uniform(.30,.70);ry=rng.uniform(.27,.62);rz=rng.uniform(.30,.65)
        if i%3==0:rx*=rng.uniform(2.8,5.)
        elif i%3==1:rz*=rng.uniform(2.8,5.)
        cavity=(np.sqrt(((x-xx)/rx)**2+((y-yy)/ry)**2+((z-zz)/rz)**2)-1)*min(rx,ry,rz)
        cavity+=.055*np.sin(x*5+y*4)*np.cos(z*5)
        rock=np.maximum(rock,-cavity)
    # The exact navigation shapes carve passages; clearance never depends on rocks.
    for na,nb,r,roofed in EDGES:
        a,b=NODES[na],NODES[nb];dx=b[0]-a[0];dz=b[2]-a[2];length=dx*dx+dz*dz
        elevated=max(a[1],b[1])>.2
        if elevated:
            # Work in X/Z while finding the curved centerline, then broadcast upward.
            xx,zz=x[:,0,:],z[:,0,:];nearest=np.full(xx.shape,np.inf);global_t=np.zeros(xx.shape)
            path=edge_path(na,nb)
            for (ta,p),(tb,q) in zip(path,path[1:]):
                vx,vz=q[0]-p[0],q[2]-p[2];tt=np.clip(((xx-p[0])*vx+(zz-p[2])*vz)/(vx*vx+vz*vz),0,1)
                dd=(xx-p[0]-vx*tt)**2+(zz-p[2]-vz*tt)**2;closer=dd<nearest
                global_t=np.where(closer,ta+(tb-ta)*tt,global_t);nearest=np.minimum(nearest,dd)
            t=global_t[:,None,:];dist=np.sqrt(nearest)[:,None,:]
        else:
            t=np.clip(((x-a[0])*dx+(z-a[2])*dz)/length,0,1)
            dist=np.sqrt((x-a[0]-dx*t)**2+(z-a[2]-dz*t)**2)
        ht=t
        if abs(a[1]-b[1])>.1:
            lo,hi=stair_limits(a,b);ht=np.clip((t-lo)/(hi-lo),0,1)
        h=a[1]+(b[1]-a[1])*ht
        # A little extra clearance accommodates the low-poly surface approximation.
        if elevated:
            # Round the rock away from the floor instead of cutting a vertical slot.
            up=np.maximum(0,y-h)
            flare=.30*(1-np.exp(-up/.52))
            width=r+.18+.08*np.sin(x*1.31+z*.83)+.03*np.sin(z*4.7-x*2.1)
            folds=(.06+.10*np.minimum(up,1))*np.sin(z*1.7+x*2.2+np.sin(y*2.1))
            horizontal=dist-width-flare-folds
        else:horizontal=dist-r-.13-.035*np.sin(z*2+x*1.8)
        height=h+(2.26+.48*np.sqrt(np.maximum(0,1-(dist/(r+.2))**2))) if roofed else np.full(shape,20.)
        void=np.maximum(horizontal,np.maximum(h-.24-y,y-height))
        rock=np.maximum(rock,-void)
    for name,cx,cz,rx,rz,h,roofed in ROOMS:
        d=(np.sqrt(((x-cx)/rx)**2+((z-cz)/rz)**2)-1)*min(rx,rz)
        ceiling=3.1+.25*np.cos(x*.6+z*.3) if roofed else np.full(shape,20.)
        void=np.maximum(d-.16,np.maximum(h-.24-y,y-ceiling))
        rock=np.maximum(rock,-void)
    # Cameras sit in small recesses where necessary; holes are part of the rockery.
    for shot in SHOTS:
        cx,cy,cz=shot['eye'];cut=np.sqrt((x-cx)**2+(y-cy)**2+(z-cz)**2)-.43
        rock=np.maximum(rock,-cut)
    # A small eye at the blind passage offers a view through to another route.
    eye=(np.sqrt(((x+.5)/.47)**2+((y-1.58)/.45)**2+((z+10.5)/3.3)**2)-1)*.45
    rock=np.maximum(rock,-eye)
    # This ceremonial scholar stone stands in the reveal court, also perforated.
    hero=(np.sqrt(((x-2.2)/.78)**2+((y-1.72)/1.7)**2+((z-3.)/.64)**2)-1)*.7
    for yy in (1.,2.3):
        hole=(np.sqrt(((x-2.2)/1.3)**2+((y-yy)/.29)**2+((z-3.)/.25)**2)-1)*.25
        hero=np.maximum(hero,-hole)
    rock=np.minimum(rock,hero+wrinkle*.4)
    # Trim subterranean waste; all walking surfaces are authored separately.
    rock=np.maximum(rock,-.20-y)
    return xs,ys,zs,rock,step

def polygonise(xs,ys,zs,values,step):
    # Marching tetrahedra: two triangles at most per crossing tetrahedron.
    corners=np.array(((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)))
    tetra=((0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6))
    edges=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3));triangles=[]
    # Process slabs to bound temporary memory; orient polygons toward positive SDF.
    for start in range(0,len(xs)-1,12):
        stop=min(start+12,len(xs)-1)
        cube=np.stack([values[start+c[0]:stop+c[0],c[1]:len(ys)-1+c[1],c[2]:len(zs)-1+c[2]] for c in corners],axis=-1)
        mask=(cube.min(axis=-1)<0)&(cube.max(axis=-1)>=0);indices=np.argwhere(mask)
        if not len(indices):continue
        base=np.column_stack((xs[indices[:,0]+start],ys[indices[:,1]],zs[indices[:,2]]));cube=cube[mask]
        for tet in tetra:
            v=cube[:,tet];sign=(v<0).astype(np.int8);case=sign.dot(np.array((1,2,4,8)))
            for c in range(1,15):
                selected=np.flatnonzero(case==c)
                if not len(selected):continue
                crossings=[e for e in edges if bool(c&(1<<e[0]))!=bool(c&(1<<e[1]))]
                points=[]
                for a,b in crossings:
                    va=v[selected,a];vb=v[selected,b];t=va/(va-vb)
                    points.append(base[selected]+(corners[tet[a]][None,:]*(1-t[:,None])+corners[tet[b]][None,:]*t[:,None])*step)
                p=np.stack(points,axis=1)
                # Four intersections must follow the perimeter, not crossing diagonals.
                if len(crossings)==4:
                    connected=[0];remaining=[1,2,3]
                    while remaining:
                        previous=crossings[connected[-1]];n=next(i for i in remaining if len(set(previous)&set(crossings[i]))==1)
                        connected.append(n);remaining.remove(n)
                    p=p[:,connected]
                inward=np.mean(corners[np.array(tet)[[bool(c&(1<<j)) for j in range(4)]]],axis=0)
                outward=np.mean(corners[np.array(tet)[[not bool(c&(1<<j)) for j in range(4)]]],axis=0)-inward
                for ids in ((0,1,2),) if p.shape[1]==3 else ((0,1,2),(0,2,3)):
                    tri=p[:,ids].copy();normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);flip=normal.dot(outward)<0
                    tri[flip]=tri[flip][:,[0,2,1]];triangles.append(tri.astype(np.float32))
    return np.concatenate(triangles)

if __name__=='__main__':
    from PIL import Image
    OUT.mkdir(parents=True,exist_ok=True);textures();print('Texture atlas and encounter notes saved.',flush=True)
    x,y,z,v,step=field();print('Porous rock field carved.',flush=True)
    atlas=np.full((math.ceil(len(y)/8)*len(z),8*len(x)),255,dtype=np.uint8)
    for i in range(len(y)):
        atlas[i//8*len(z):(i//8+1)*len(z),i%8*len(x):(i%8+1)*len(x)]=np.clip((v[:,i,:].T/3+.5)*255,0,255).astype(np.uint8)
    Image.fromarray(atlas).convert('RGB').save(OUT/'rock_field.png')
    (OUT/'field.json').write_text(json.dumps(dict(origin=[float(x[0]),float(y[0]),float(z[0])],size=[len(x),len(y),len(z)],step=step,columns=8,atlas=[atlas.shape[1],atlas.shape[0]]),indent=2))
    triangles=polygonise(x,y,z,v,step)
    np.savez_compressed(OUT/'rockery_geometry.npz',triangles=triangles)
    print('Rock surface:',len(triangles),'triangles',flush=True)
