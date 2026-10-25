"""Bake a reusable 3D distance field from the canal's actual rendered meshes.

This is an offline asset operation, not a runtime side effect. The field is an
unsigned distance to sampled roof, wall, doorway, stair and quay triangles;
open buildings remain open. It never creates or draws a surrogate ghost mesh.
Only NumPy is required. Distances are capped, allowing an exact separable
Euclidean transform of the rasterized surfaces without SciPy.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import struct
import time
from typing import NamedTuple

import numpy as np


ROOT=Path(__file__).resolve().parent
KIT=ROOT/'art/temple/huxin_canals'
DEFAULT_PATH=KIT/'surface_fog.npz'
VERSION=1
EXCLUDED_MODELS=('canal_water','canal_annulus')


class SurfaceSample(NamedTuple):
    distance: float
    owner: str | None
    occupied: bool


@dataclass(frozen=True)
class SurfaceField:
    origin: tuple[float,float,float]
    spacing: float
    shape: tuple[int,int,int]  # xyz; arrays are y,z,x for horizontal atlas slices
    distance_cap: float
    distance: np.ndarray      # uint8: distance_cap * byte / 255
    owner: np.ndarray         # uint8: zero generic, 1+ index into owners
    occupancy: np.ndarray    # bool: surface raster, before distance transform
    owners: tuple[str,...]
    source_digests: tuple[tuple[str,str],...]
    metadata: dict

    def sample(self,point):
        """Trilinear distance with nearest-voxel semantic owner, in metres."""
        if len(point)!=3 or not all(math.isfinite(v) for v in point):raise ValueError('Surface sample requires three finite coordinates.')
        q=(np.asarray(point)-np.asarray(self.origin))/self.spacing
        shape=np.asarray(self.shape)
        if np.any(q<0.) or np.any(q>shape-1):return SurfaceSample(self.distance_cap,None,False)
        low=np.floor(q).astype(int);high=np.minimum(low+1,shape-1);f=q-low
        distance=0.
        for x in (0,1):
            for y in (0,1):
                for z in (0,1):
                    ix,iy,iz=(high[i] if bit else low[i] for i,bit in enumerate((x,y,z)))
                    weight=(f[0] if x else 1.-f[0])*(f[1] if y else 1.-f[1])*(f[2] if z else 1.-f[2])
                    distance+=float(self.distance[iy,iz,ix])*weight*self.distance_cap/255.
        ix,iy,iz=np.rint(q).astype(int)
        index=int(self.owner[iy,iz,ix])
        return SurfaceSample(float(distance),self.owners[index-1] if index else None,bool(self.occupancy[iy,iz,ix]))

    def atlas(self,support=None):
        """RGBA bytes,width,height,columns,rows; each Y slice has XZ gutters.

        An optional transient support distance occupies spare alpha. It uses
        the same capped uint8 encoding as distance and never changes RGB or
        the cached surface field. Without it alpha remains exactly 255.
        """
        nx,ny,nz=self.shape
        if support is not None:
            support=np.asarray(support)
            if support.shape!=(ny,nz,nx):raise ValueError('Support distance must match the field y,z,x shape.')
            if support.dtype!=np.uint8:raise ValueError('Support distance must use capped uint8 distance bytes.')
        columns,rows=_atlas_layout(nx,ny,nz)
        tx,tz=nx+2,nz+2
        atlas=np.zeros((rows*tz,columns*tx,4),dtype=np.uint8)
        atlas[:,:,0]=255;atlas[:,:,3]=255
        for y in range(ny):
            tile=atlas[(y//columns)*tz:(y//columns+1)*tz,
                       (y%columns)*tx:(y%columns+1)*tx]
            tile[1:-1,1:-1,0]=self.distance[y]
            tile[1:-1,1:-1,1]=self.occupancy[y].astype(np.uint8)*255
            tile[1:-1,1:-1,2]=self.owner[y]
            if support is not None:tile[1:-1,1:-1,3]=support[y]
            tile[0,1:-1]=tile[1,1:-1];tile[-1,1:-1]=tile[-2,1:-1]
            tile[:,0]=tile[:,1];tile[:,-1]=tile[:,-2]
        return atlas.tobytes(),atlas.shape[1],atlas.shape[0],columns,rows


def _atlas_layout(nx,ny,nz,max_size=4096):
    candidates=[]
    for columns in range(1,ny+1):
        rows=math.ceil(ny/columns)
        width,height=columns*(nx+2),rows*(nz+2)
        if max(width,height)<=max_size:
            candidates.append((max(width,height),width*height,columns,rows))
    if not candidates:raise ValueError(f'Surface field does not fit a {max_size}px atlas; increase voxel spacing.')
    _,_,columns,rows=min(candidates)
    return columns,rows


def _source_paths(root):
    root=Path(root)
    manifest=json.loads((root/'canals_manifest.json').read_text(encoding='utf-8'))
    return (root/'canals_manifest.json',)+tuple(root/(name+'.glb')
        for name in manifest['models'] if name not in EXCLUDED_MODELS)


def geometry_digest(root=KIT):
    """Hash actual source bytes, including the manifest used to label houses."""
    return tuple((path.name,hashlib.sha256(path.read_bytes()).hexdigest())
                 for path in _source_paths(root))


def _glb(path):
    data=Path(path).read_bytes()
    if len(data)<20:raise ValueError(f'{path}: truncated GLB')
    magic,version,length=struct.unpack_from('<III',data)
    if magic!=0x46546c67 or version!=2 or length!=len(data):raise ValueError(f'{path}: expected a complete GLB 2 file')
    document=blob=None;offset=12
    while offset<len(data):
        size,kind=struct.unpack_from('<II',data,offset);offset+=8
        chunk=data[offset:offset+size];offset+=size
        if kind==0x4e4f534a:document=json.loads(chunk)
        elif kind==0x004e4942:blob=chunk
    if document is None or blob is None:raise ValueError(f'{path}: missing JSON or binary chunk')
    return document,blob


def _accessor(document,blob,index):
    entry=document['accessors'][index]
    if 'sparse' in entry:raise ValueError('Sparse GLB accessors need an explicit export before baking.')
    view=document['bufferViews'][entry['bufferView']]
    if view.get('buffer',0)!=0:raise ValueError('External GLB buffers are unsupported.')
    dtype={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}[entry['componentType']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[entry['type']]
    item=np.dtype(dtype).itemsize;stride=view.get('byteStride',width*item)
    start=view.get('byteOffset',0)+entry.get('byteOffset',0)
    return np.ndarray((entry['count'],width),dtype=dtype,buffer=blob,offset=start,strides=(stride,item))


def _node_matrix(node):
    if 'matrix' in node:return np.asarray(node['matrix'],dtype=np.float64).reshape(4,4).T
    x,y,z,w=node.get('rotation',(0.,0.,0.,1.))
    matrix=np.eye(4)
    matrix[:3,:3]=((1.-2.*(y*y+z*z),2.*(x*y-z*w),2.*(x*z+y*w)),
                  (2.*(x*y+z*w),1.-2.*(x*x+z*z),2.*(y*z-x*w)),
                  (2.*(x*z-y*w),2.*(y*z+x*w),1.-2.*(x*x+y*y)))
    matrix[:3,:3]*=np.asarray(node.get('scale',(1.,1.,1.)))[None,:]
    matrix[:3,3]=node.get('translation',(0.,0.,0.))
    return matrix


def glb_triangles(path):
    """Yield world-space float32 triangle batches, respecting GLB node TRS."""
    document,blob=_glb(path)
    nodes=document.get('nodes',[])
    roots=document.get('scenes',[{'nodes':list(range(len(nodes)))}])[document.get('scene',0)]['nodes']
    def visit(index,parent,ancestors):
        if index in ancestors:raise ValueError(f'{path}: cyclic GLB node tree')
        node=nodes[index];matrix=parent@_node_matrix(node)
        if 'mesh' in node:
            for primitive in document['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4)!=4:continue
                positions=_accessor(document,blob,primitive['attributes']['POSITION'])
                if positions.shape[1]!=3:raise ValueError(f'{path}: POSITION must be VEC3')
                positions=(positions@matrix[:3,:3].T+matrix[:3,3]).astype(np.float32)
                if not np.all(np.isfinite(positions)):raise ValueError(f'{path}: nonfinite geometry')
                indices=(_accessor(document,blob,primitive['indices']).ravel()
                         if 'indices' in primitive else np.arange(len(positions)))
                if len(indices)%3:raise ValueError(f'{path}: incomplete triangle indices')
                for start in range(0,len(indices),180000):
                    yield positions[indices[start:start+180000]].reshape(-1,3,3)
        for child in node.get('children',[]):yield from visit(child,matrix,ancestors|{index})
    for index in roots:yield from visit(index,np.eye(4),set())


def rasterize_triangles(occupancy,triangles,origin,spacing):
    """Sample each triangle on an adaptive barycentric grid <= .6 voxel."""
    longest=np.maximum.reduce((np.linalg.norm(triangles[:,0]-triangles[:,1],axis=1),
        np.linalg.norm(triangles[:,1]-triangles[:,2],axis=1),
        np.linalg.norm(triangles[:,2]-triangles[:,0],axis=1)))
    count=np.maximum(1,np.ceil(longest/(spacing*.6)).astype(np.int32))
    # Powers of two share sampling grids and permit efficient vector batches.
    levels=np.power(2,np.ceil(np.log2(count)).astype(np.int32))
    origin=np.asarray(origin,dtype=np.float32);samples=0
    ny,nz,nx=occupancy.shape
    for divisions in np.unique(levels):
        faces=triangles[levels==divisions]
        u,v=np.triu_indices(int(divisions)+1)
        weights=np.column_stack((u/divisions,(v-u)/divisions)).astype(np.float32)
        batch=max(1,1200000//len(weights))
        for start in range(0,len(faces),batch):
            face=faces[start:start+batch]
            points=(face[:,None,0,:]+weights[None,:,0,None]*(face[:,None,1,:]-face[:,None,0,:])+
                    weights[None,:,1,None]*(face[:,None,2,:]-face[:,None,0,:]))
            indices=np.rint((points.reshape(-1,3)-origin)/spacing).astype(np.int32)
            valid=(indices[:,0]>=0)&(indices[:,0]<nx)&(indices[:,1]>=0)&(indices[:,1]<ny)&(indices[:,2]>=0)&(indices[:,2]<nz)
            if not np.all(valid):raise ValueError('Geometry escaped the surface field bounds; regenerate bounds.')
            occupancy[indices[:,1],indices[:,2],indices[:,0]]=True
            samples+=len(indices)
    return samples


def truncated_distance_transform(occupancy,owners,spacing,cap):
    """Exact capped Euclidean voxel distance plus nearest occupied owner.

    Separability turns the truncated squared-distance transform into a small
    number of bulk shifted minima. Ties retain the earlier deterministic owner.
    """
    radius=math.ceil(cap/spacing)+1
    infinity=radius*radius+1
    if infinity+radius*radius>=65535:raise ValueError('Distance cap is too large for voxel spacing.')
    distance=np.where(occupancy,0,infinity).astype(np.uint16)
    owner=np.asarray(owners,dtype=np.uint8).copy()
    for axis in range(3):
        source=distance;labels=owner
        distance=source.copy();owner=labels.copy()
        for offset in range(1,min(radius,source.shape[axis]-1)+1):
            low=[slice(None)]*3;high=[slice(None)]*3
            low[axis]=slice(None,-offset);high[axis]=slice(offset,None)
            low,high=tuple(low),tuple(high)
            for dst,src in ((low,high),(high,low)):
                candidate=source[src]+offset*offset
                better=candidate<distance[dst]
                np.copyto(distance[dst],candidate,where=better)
                np.copyto(owner[dst],labels[src],where=better)
    # Distance to a sampled occupied voxel center is reduced conservatively
    # by its half-diagonal. The shader may safely skip truly empty space.
    metres=np.maximum(0.,np.sqrt(distance.astype(np.float32))*spacing-spacing*math.sqrt(3.)*.5)
    owner[metres>=cap]=0
    return np.rint(np.minimum(metres,cap)/cap*255.).astype(np.uint8),owner


def build_surface_support(field,base_y=0.,below=.6):
    """Return an in-memory fog distance that connects named roofs to water.

    Only columns with actual named architectural surface above the datum are
    filled. Roof setbacks, separated houses and open courtyards retain their
    projected shapes. This is temporary concealment density, not geometry or
    a replacement for the unsigned surface field; the source stays hollow.

    The result has the source y,z,x shape and conservative capped uint8 metre
    encoding. It can be packed in ``field.atlas(support=...)`` alpha. No bake,
    metadata, cached asset or material ownership is modified.
    """
    if not math.isfinite(base_y):raise ValueError('Support datum must be finite.')
    if not math.isfinite(below) or below<0.:raise ValueError('Support padding below the datum must be finite and nonnegative.')
    ny=field.shape[1]
    heights=field.origin[1]+np.arange(ny,dtype=np.float64)*field.spacing
    seed=(field.occupancy&(field.owner!=0)&
          (heights[:,None,None]>=float(base_y)-field.spacing*.5))
    if not np.any(seed):
        result=np.full(field.distance.shape,255,dtype=np.uint8)
        result.setflags(write=False)
        return result
    # Filling downward from each real upper surface bridges the room/floor
    # cavities that a thin unsigned shell correctly leaves empty. The lower
    # cutoff overlaps the low lake veil without following the changed water.
    filled=np.logical_or.accumulate(seed[::-1],axis=0)[::-1].copy()
    filled[heights<float(base_y)-float(below)-field.spacing*.5]=False
    labels=np.where(filled,field.owner,0).astype(np.uint8)
    result,_=truncated_distance_transform(filled,labels,field.spacing,field.distance_cap)
    result.setflags(write=False)
    return result


def _label_occupied(occupancy,origin,spacing,root):
    manifest=json.loads((Path(root)/'canals_manifest.json').read_text(encoding='utf-8'))
    houses=manifest['houses']
    # Duplicate seeds on opposite banks have distinct stable semantic IDs.
    counts={house['id']:sum(other['id']==house['id'] for other in houses) for house in houses}
    ids=[];bounds=[]
    for house in houses:
        corners=np.asarray(house['bounds_corners'],dtype=np.float32)
        low=corners.min(axis=0);high=corners.max(axis=0)
        low[1]=min(low[1],house.get('foundation_bottom',-2.3))
        center=(low+high)*.5
        ident=house['id']
        if counts[ident]>1:ident+=('-west' if center[0]<0 else '-east')
        ids.append(ident);bounds.append((low-.7,high+.7,center))
    if len(ids)>254:raise ValueError('Surface owner atlas supports at most 254 distinct buildings.')
    indices=np.column_stack(np.nonzero(occupancy))
    points=indices[:,(2,0,1)]*spacing+np.asarray(origin)
    labels=np.zeros(len(points),dtype=np.uint8);nearest=np.full(len(points),np.inf)
    for index,(low,high,center) in enumerate(bounds):
        inside=np.all((points>=low)&(points<=high),axis=1)
        squared=np.sum((points-center)**2,axis=1)
        choose=inside&(squared<nearest)
        nearest[choose]=squared[choose];labels[choose]=index+1
    output=np.zeros_like(occupancy,dtype=np.uint8)
    output[tuple(indices.T)]=labels
    return output,tuple(ids)


def bake_surface_field(root=KIT,spacing=.6,distance_cap=16.,padding=14.,progress=None):
    root=Path(root);start=time.perf_counter()
    if spacing<=0. or distance_cap<=0. or padding<spacing:raise ValueError('Surface spacing, cap and padding must be positive.')
    def report(message):
        if progress is not None:progress(message)
    sources=geometry_digest(root)
    manifest=json.loads((root/'canals_manifest.json').read_text(encoding='utf-8'))
    models={name:value for name,value in manifest['models'].items() if name not in EXCLUDED_MODELS}
    low=np.min([value['bounds'][0] for value in models.values()],axis=0)
    high=np.max([value['bounds'][1] for value in models.values()],axis=0)
    origin=np.floor((low-padding)/spacing)*spacing
    shape=np.ceil((high+padding-origin)/spacing).astype(int)+1
    _atlas_layout(*map(int,shape))  # Fail before expensive work if GPU cannot fit.
    occupancy=np.zeros((shape[1],shape[2],shape[0]),dtype=bool)
    report(f'Rasterizing {len(models)} GLBs into {tuple(shape)} xyz voxels ({occupancy.size/1e6:.2f}M).')
    triangles=samples=0
    for name in models:
        file_triangles=file_samples=0
        for faces in glb_triangles(root/(name+'.glb')):
            file_samples+=rasterize_triangles(occupancy,faces,origin,spacing);file_triangles+=len(faces)
        triangles+=file_triangles;samples+=file_samples
        report(f'{name}: {file_triangles:,} triangles / {file_samples:,} samples; {time.perf_counter()-start:.1f}s')
    owner,ids=_label_occupied(occupancy,origin,spacing,root)
    report(f'{np.count_nonzero(occupancy):,} surface cells; propagating distance and {len(ids)} building labels.')
    distance,owner=truncated_distance_transform(occupancy,owner,spacing,distance_cap)
    metadata=dict(version=VERSION,triangles=triangles,samples=samples,
        occupied_cells=int(np.count_nonzero(occupancy)),seconds=time.perf_counter()-start,
        padding=padding,source_bounds=[low.tolist(),high.tolist()],excluded=list(EXCLUDED_MODELS),
        distance_description='Capped distance to adaptive triangle raster, minus half voxel diagonal.',
        array_order='y,z,x',atlas_channels='R distance/cap; G surface occupancy; B owner index; A 255')
    for array in (distance,owner,occupancy):array.setflags(write=False)
    return SurfaceField(tuple(map(float,origin)),float(spacing),tuple(map(int,shape)),float(distance_cap),
        distance,owner,occupancy,ids,sources,metadata)


def save_surface_field(field,path=DEFAULT_PATH):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    columns,rows=_atlas_layout(*field.shape)
    nx,ny,nz=field.shape
    document=dict(field.metadata,origin=field.origin,spacing=field.spacing,shape=field.shape,
        distance_cap=field.distance_cap,owners=field.owners,source_digests=field.source_digests,
        atlas=dict(columns=columns,rows=rows,width=columns*(nx+2),height=rows*(nz+2),gutter=1,slice_axis='y'))
    encoded=json.dumps(document,ensure_ascii=False,sort_keys=True)
    with path.open('wb') as stream:
        np.savez_compressed(stream,distance=field.distance,owner=field.owner,
                            occupancy=field.occupancy,metadata=np.array(encoded))
    path.with_suffix('.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return path


def load_surface_field(path=DEFAULT_PATH,verify_sources=False):
    """Read only; missing/stale caches are reported, never silently rebaked."""
    path=Path(path)
    with np.load(path,allow_pickle=False) as data:
        metadata=json.loads(str(data['metadata']))
        if metadata.get('version')!=VERSION:raise ValueError('Unsupported surface fog cache version.')
        distance=data['distance'];owner=data['owner'];occupancy=data['occupancy']
    shape=tuple(metadata['shape']);array_shape=(shape[1],shape[2],shape[0])
    if any(array.shape!=array_shape for array in (distance,owner,occupancy)):
        raise ValueError('Surface fog cache dimensions do not match metadata.')
    if distance.dtype!=np.uint8 or owner.dtype!=np.uint8 or occupancy.dtype!=bool:
        raise ValueError('Surface fog cache has invalid array types.')
    sources=tuple(tuple(row) for row in metadata['source_digests'])
    if verify_sources and geometry_digest(path.parent)!=sources:raise ValueError('Surface fog cache is stale; rebuild it from current GLBs.')
    for array in (distance,owner,occupancy):array.setflags(write=False)
    return SurfaceField(tuple(metadata['origin']),float(metadata['spacing']),shape,float(metadata['distance_cap']),
        distance,owner,occupancy,tuple(metadata['owners']),sources,metadata)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=KIT)
    parser.add_argument('--output',type=Path,default=DEFAULT_PATH)
    parser.add_argument('--spacing',type=float,default=.6)
    parser.add_argument('--distance-cap',type=float,default=16.)
    parser.add_argument('--padding',type=float,default=14.)
    args=parser.parse_args()
    field=bake_surface_field(args.root,args.spacing,args.distance_cap,args.padding,print)
    save_surface_field(field,args.output)
    print(f'Saved {args.output}; {field.metadata["seconds"]:.1f}s; {field.shape} voxels.')
