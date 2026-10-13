"""Visibility-aware selection among fixed camera positions in the rockery."""
from pathlib import Path
import json
import math
import struct
import numpy as np
from PIL import Image
from g_rockery import SHOTS,LIGHTS,PAVILION


class StairOccluders:
    """The exported, baked stair mesh includes chipped lips and irregular edges."""
    def __init__(self,path):
        raw=Path(path).read_bytes();size=struct.unpack_from('<I',raw,12)[0]
        doc=json.loads(raw[20:20+size]);binary=raw[28+size:];triangles=[]
        def values(index):
            a=doc['accessors'][index];view=doc['bufferViews'][a['bufferView']]
            dtype=np.dtype({5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']])
            count=3 if a['type']=='VEC3' else 1
            return np.ndarray((a['count'],count),dtype=dtype,buffer=binary,
                offset=view.get('byteOffset',0)+a.get('byteOffset',0),
                strides=(view.get('byteStride',dtype.itemsize*count),dtype.itemsize))
        for mesh in doc['meshes']:
            for primitive in mesh['primitives']:
                xyz=values(primitive['attributes']['POSITION']);indices=values(primitive['indices']).reshape(-1)
                triangles.append(xyz[indices].reshape(-1,3,3))
        tri=np.concatenate(triangles);self.low=tri.min(axis=1);self.high=tri.max(axis=1)
        self.a=tri[:,0];self.ab=tri[:,1]-self.a;self.ac=tri[:,2]-self.a

    def blocked(self,eye,target):
        selected=np.all(self.high>=np.minimum(eye,target),axis=1)&np.all(self.low<=np.maximum(eye,target),axis=1)
        if not np.any(selected):return False
        a,ab,ac=self.a[selected],self.ab[selected],self.ac[selected];direction=target-eye
        h=np.cross(direction,ac);det=np.einsum('ij,ij->i',ab,h)
        inv=np.divide(1.,det,out=np.zeros_like(det),where=np.abs(det)>1e-9)
        s=eye-a;u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,ab)
        v=np.einsum('j,ij->i',direction,q)*inv;t=np.einsum('ij,ij->i',ac,q)*inv
        length=np.linalg.norm(direction)
        return bool(np.any((abs(det)>1e-9)&(u>=-1e-5)&(v>=-1e-5)&(u+v<=1.00001)&(t>.10/length)&(t<1-.12/length)))

class RockField:
    def __init__(self,folder):
        info=json.loads((Path(folder)/'field.json').read_text());self.origin=np.array(info['origin']);self.step=info['step'];self.size=np.array(info['size'])
        a=np.array(Image.open(Path(folder)/'rock_field.png'))[:,:,0].astype(np.float32)/255*3-1.5;nx,ny,nz=self.size
        self.volume=np.stack([a[i//8*nz:(i//8+1)*nz,i%8*nx:(i%8+1)*nx].T for i in range(ny)],axis=1)
        self.stairs=StairOccluders(Path(folder)/'high_walk.glb')
    def sample(self,points):
        p=(np.asarray(points)-self.origin)/self.step;outside=np.any((p<0)|(p>self.size-1),axis=-1);p=np.clip(p,0,self.size-1.00001)
        base=np.floor(p).astype(int);f=p-base;result=np.zeros(len(p))
        for x in (0,1):
            for y in (0,1):
                for z in (0,1):
                    weight=(f[:,0] if x else 1-f[:,0])*(f[:,1] if y else 1-f[:,1])*(f[:,2] if z else 1-f[:,2])
                    result+=self.volume[base[:,0]+x,base[:,1]+y,base[:,2]+z]*weight
        result[outside]=1.5;return result
    def sightline(self,eye,target):
        eye=np.asarray(eye);target=np.asarray(target);distance=np.linalg.norm(target-eye)
        t=np.linspace(.10/max(.1,distance),1-.12/max(.2,distance),max(3,int(distance/.10)))
        points=eye[None,:]+(target-eye)[None,:]*t[:,None]
        if np.count_nonzero(self.sample(points)<-.065)>1:return False
        # Test the actual chipped stair decks and low rock shoulders separately.
        if self.stairs.blocked(eye,target):return False
        x,y,z=points.T
        for cx,cy,cz in LIGHTS:
            if np.any(((x-cx)**2+(z-cz)**2<.22**2)&(y>.08)&(y<cy+.2)):return False
        for i in range(6):
            cx=PAVILION[0]+math.cos(i*math.tau/6)*PAVILION[2];cz=PAVILION[1]+math.sin(i*math.tau/6)*PAVILION[2]
            if np.any(((x-cx)**2+(z-cz)**2<.16**2)&(y>.08)&(y<3.5)):return False
        return True

class Director:
    def __init__(self,field):self.field=field;self.current=0;self.uncovered=0;self.pans=0;self.last_clear=True
    def select(self,e):
        body=np.array((e.x,e.height+.93,e.z));candidates=[]
        for i,shot in enumerate(SHOTS):
            eye=np.array(shot['eye']);distance=np.linalg.norm(body-eye)
            if distance<1.25 or distance>17:continue
            # Upper cameras should preserve the player's current vertical level.
            if e.floor<.3 and eye[1]>4.7:continue
            if e.floor>2.5 and eye[1]<3.4:continue
            target=np.array(shot['target']);forward=target-eye;forward/=np.linalg.norm(forward)
            right=np.cross(forward,(0,1,0));right/=np.linalg.norm(right);up=np.cross(right,forward)
            d=body-eye;depth=np.dot(d,forward);tan=math.tan(math.radians(shot['fov'])/2)
            framing=10.
            if depth>.2:framing=max(abs(np.dot(d,right)/(depth*tan*16/9)),(abs(np.dot(d,up))+.82)/(depth*tan))
            # Check actual carved geometry, not just which room contains the player.
            if not self.field.sightline(eye,body):continue
            score=abs(distance-5.5)*.10+min(framing,3.)*.4
            if framing<.89:score-=2.
            if i==self.current and framing<.89:score-=1.25
            candidates.append((score,i,framing))
        if not candidates:
            self.uncovered+=1;self.last_clear=False
            shot=SHOTS[self.current];return self.current,shot['eye'],tuple(body),shot['fov']
        _,i,framing=min(candidates);self.current=i;self.last_clear=True;shot=SHOTS[i]
        target=shot['target']
        if framing>=.89:
            # Keep the position fixed; a restrained pan handles the edge of a turn.
            target=tuple(body);self.pans+=1
        return i,shot['eye'],target,shot['fov']
