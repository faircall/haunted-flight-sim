"""Raised board-and-pier geometry; the tile map remains the walkable surface.

Built once at load, grouped into three materials. Narrow visual board gaps do
not create collision holes. Coordinates here are X / height / ground Y.
"""
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path

from PIL import Image
import g_temple_structure as structure

BOARD_THICKNESS=2.25
GAP=.45


@dataclass(frozen=True)
class Part:
    kind:str
    low:tuple
    high:tuple
    axis:str
    owner:str='bridge'


def runs(values):
    values=sorted(set(values))
    if not values:return
    start=previous=values[0]
    for value in values[1:]:
        if value!=previous+1:
            yield start,previous+1
            start=value
        previous=value
    yield start,previous+1


def floor_cells(tm):
    result={}
    for index,tile in enumerate(tm['tiles']):
        if tile.get('surface_material') not in ('wood','wall'):continue
        height=float(tile.get('surface_elevation',0.))
        if height<=0:continue
        axis=tile.get('surface_axis','x') if tile.get('surface_material')=='wood' else 'x'
        result[index%tm['map_width'],index//tm['map_width']]=(height,axis)
    return result


def layout(tm):
    cells=floor_cells(tm)
    bands=defaultdict(list)
    columns=defaultdict(list)
    for (x,y),(height,axis) in cells.items():
        long,across=(x,y) if axis=='x' else (y,x)
        bands[height,axis,across].append(long)
        columns[height,axis,long].append(across)
    parts=[]

    def add(kind,axis,a0,a1,b0,b1,h0,h1):
        x0,z0,x1,z1=(a0,b0,a1,b1) if axis=='x' else (b0,a0,b1,a1)
        owner='temple' if tm.get('temple3d_layout') and height==structure.TEMPLE_HEIGHT else 'bridge'
        parts.append(Part(kind,(x0,h0,z0),(x1,h1,z1),axis,owner))

    for (height,axis,across),longs in sorted(bands.items()):
        for first,end in runs(longs):
            for strip in range(4):
                b0=across*16+strip*4+GAP/2
                b1=b0+4-GAP
                a=first*16
                offset=((across*4+strip)%3)*16
                while a<end*16:
                    b=min(end*16,(math.floor((a-offset)/48)+1)*48+offset)
                    add('board',axis,a+GAP/2,b-GAP/2,b0,b1,height-BOARD_THICKNESS,height)
                    a=b
    # Transverse joists carry the boards. End stations prevent cantilevered
    # tile boundaries at the shore, corners and changes in plank direction.
    piers=set()
    for (height,axis,long),across_values in sorted(columns.items()):
        stations=[]
        if long%2==0:stations.append(long*16+2.)
        for direction in (-1,1):
            if (height,axis,long+direction) not in columns:
                stations.append(long*16+(2. if direction<0 else 14.))
        for station in sorted(set(stations)):
            for first,end in runs(across_values):
                lo,hi=first*16,end*16
                top=height-BOARD_THICKNESS
                temple=tm.get('temple3d_layout') and height==structure.TEMPLE_HEIGHT
                depth=4.
                half_width=2.5 if temple else 1.75
                add('joist',axis,station-half_width,station+half_width,lo+.5,hi-.5,top-depth,top)
                # Piers sit directly below the joist, including intermediate
                # supports under the broad temple floor. They extend below water.
                spans=max(1,math.ceil((hi-lo-6)/48))
                for step in range(spans+1):
                    if temple:continue  # building has its own aligned bearer/pier grid below
                    across=lo+3+(hi-lo-6)*step/spans
                    x,z=(station,across) if axis=='x' else (across,station)
                    key=(round(x,4),round(z,4),height)
                    if key not in piers:
                        piers.add(key)
                        radius=3.5 if temple else 2.
                        parts.append(Part('pier',(x-radius,-20.,z-radius),(x+radius,top-depth,z+radius),'vertical','temple' if temple else 'bridge'))
    if tm.get('temple3d_layout'):parts=finish_structures(parts)
    return parts


def subtract(part,bounds):
    """Clip boards around stair openings, preserving their thickness and owner."""
    x0,h0,z0=part.low;x1,h1,z1=part.high
    a0,b0,a1,b1=bounds
    a0,a1=max(x0,a0),min(x1,a1);b0,b1=max(z0,b0),min(z1,b1)
    if a0>=a1 or b0>=b1:return [part]
    boxes=((x0,z0,a0,z1),(a1,z0,x1,z1),(a0,z0,a1,b0),(a0,b1,a1,z1))
    return [Part(part.kind,(a,h0,b),(c,h1,d),part.axis,part.owner) for a,b,c,d in boxes if a<c and b<d]


def finish_structures(parts):
    result=[]
    for part in parts:
        if part.owner=='bridge' and part.kind!='board' and part.high[2]<=296:continue
        chunks=[part]
        if part.kind=='board':
            for bounds in [s.bounds for s in structure.STAIRS]+[(400,272,560,280)]:
                chunks=[piece for chunk in chunks for piece in subtract(chunk,bounds)]
        result.extend(chunks)
    # A narrow front sill belongs to the building, with its own perimeter beams
    # and column supports. There is no wraparound forecourt underneath it.
    for x in range(400,560,32):
        result.append(Part('board',(x+GAP/2,21.75,272),(x+32-GAP/2,24,280),'x','temple'))
    for low,high,axis in (((400,14.75,274),(560,21.75,280),'x'),
                          ((400,14.75,176),(404,21.75,274),'y'),
                          ((556,14.75,176),(560,21.75,274),'y'),
                          ((400,14.75,176),(560,21.75,180),'x')):
        result.append(Part('joist',low,high,axis,'temple'))
    for z in (180,224,276):
        result.append(Part('joist',(400,10.75,z-3),(560,17.75,z+3),'x','temple'))
        for x in (404,454,506,556):
            result.append(Part('pier',(x-3.5,-20,z-3.5),(x+3.5,10.75,z+3.5),'vertical','temple'))
    for stairs in structure.STAIRS:
        previous=stairs.bottom
        for (x0,z0,x1,z1),top in stairs.treads():
            owner='stairs:'+stairs.name
            axis='y' if stairs.axis=='x' else 'x'
            result.append(Part('tread',(x0,top-2,z0),(x1,top,z1),axis,owner))
            # Closed risers and stepped side stringers support each tread.
            if stairs.axis=='x':
                result.append(Part('riser',(x0,previous,z0),(x0+.8,top,z1),'y',owner))
                for z in (z0,z1-2):result.append(Part('stringer',(x0,stairs.bottom-4,z),(x1,top-1,z+2),'x',owner))
            else:
                result.append(Part('riser',(x0,previous,z1-.8),(x1,top,z1),'x',owner))
                for x in (x0,x1-2):result.append(Part('stringer',(x,stairs.bottom-4,z0),(x+2,top-1,z1),'y',owner))
            previous=top
    return result


def quads(part):
    x0,y0,z0=part.low;x1,y1,z1=part.high
    return (
        ([(x0,y1,z0),(x0,y1,z1),(x1,y1,z1),(x1,y1,z0)],(0,1,0)),
        ([(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],(0,-1,0)),
        ([(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0)],(-1,0,0)),
        ([(x1,y0,z1),(x1,y0,z0),(x1,y1,z0),(x1,y1,z1)],(1,0,0)),
        ([(x1,y0,z0),(x0,y0,z0),(x0,y1,z0),(x1,y1,z0)],(0,0,-1)),
        ([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],(0,0,1)))


def write(tm,folder,art):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    parts=layout(tm)
    lines=['mtllib raised_deck.mtl'];index=0
    for material in ('boards_x','boards_y','timber'):
        lines+=['o '+material,'usemtl '+material]
        for part in parts:
            group='boards_'+part.axis if part.kind in ('board','tread') else 'timber'
            if group!=material:continue
            for vertices,normal in quads(part):
                for corner in (0,1,2,0,2,3):
                    x,h,z=vertices[corner]
                    if part.kind in ('board','tread'):
                        u,v=(x/128,z/32) if part.axis=='x' else (x/32,z/128)
                        if not normal[1]:v+=(part.high[1]-h)/32
                    else:
                        if part.axis=='vertical':u,v=h/32,(x+z)/16
                        elif part.axis=='x':u,v=z/32,(x if normal[1] else h)/16
                        else:u,v=x/32,(z if normal[1] else h)/16
                    lines+=['v %g %g %g'%(x,h,z),'vt %g %g'%(u,-v),'vn %g %g %g'%normal]
                for start in (0,3):
                    lines.append('f '+' '.join(f'{v}/{v}/{v}' for v in range(index+start+1,index+start+4)))
                index+=6
    target=folder/'raised_deck.obj'
    target.write_text('\n'.join(lines),newline='\n')
    timber=folder/'deck_timber.png'
    Image.open(art/'textures'/'wood.png').convert('RGB').resize((64,64)).quantize(32).convert('RGBA').save(timber)
    paths={'boards_x':art/'runtime'/'planks_x.png','boards_y':art/'runtime'/'planks_y.png','timber':timber}
    (folder/'raised_deck.mtl').write_text('\n'.join(f'newmtl {name}\nKd 1 1 1\nmap_Kd {path.as_posix()}\n' for name,path in paths.items()),newline='\n')
    counts={kind:sum(part.kind==kind for part in parts) for kind in sorted({p.kind for p in parts})}
    (folder/'raised_deck.json').write_text(json.dumps(dict(counts=counts,triangles=len(parts)*12,materials=3,bridge_height=16,temple_height=24 if tm.get('temple3d_layout') else 16,board_thickness=BOARD_THICKNESS,gap=GAP),indent=2)+'\n',newline='\n')
    return target
