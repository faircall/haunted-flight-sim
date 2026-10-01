"""Palette colour, unit normals, position/height/depth/AO maps and provenance."""
from pathlib import Path
import sys,json,hashlib,math
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from build import pixels


def data_image(path,size):
    # Coverage-weighted numeric resize, explicitly avoiding the colour transfer.
    raw=np.asarray(Image.open(path).convert('RGBA')).astype(np.float32)/255
    alpha=raw[:,:,3];resize=lambda a:np.asarray(Image.fromarray(a).resize(size,Image.Resampling.LANCZOS))
    weight=resize(alpha)
    return np.stack([resize(raw[:,:,i]*alpha)/np.maximum(weight,1e-5) for i in range(3)],axis=2).clip(0,1)


def main():
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
    records=json.loads((ROOT/'bakes.json').read_text());sources=json.loads((ROOT/'sources.json').read_text())
    sheet=Image.new('RGB',(1200,230*((len(records)+3)//4)),(24,30,37));draw=ImageDraw.Draw(sheet)
    for index,(name,rec) in enumerate(records.items()):
        size=tuple(rec['size']);render=ROOT/'renders'
        color=pixels(Image.open(render/(name+'_color.png')).convert('RGBA'),size,64)
        arr=np.asarray(color).copy()
        if name in ('window','wall','door_open','door_closed'):
            holes=np.asarray(Image.open(ROOT/(name+'_holes.png')))>0
            # Exact portal/collision contract; the front plane fills all other pixels.
            missing=(arr[:,:,3]==0)&~holes
            fallback=np.asarray(Image.open(ROOT/'textures'/'wood.png').convert('RGBA').resize(size))
            arr[missing]=fallback[missing];arr[holes]=0
            color=pixels(Image.fromarray(arr),size,64);arr=np.asarray(color).copy()
        mask=arr[:,:,3]>0;color.save(runtime/(name+'.png'))
        normal=data_image(render/(name+'_normal.png'),size)*2-1
        length=np.linalg.norm(normal,axis=2,keepdims=True);normal/=np.maximum(length,1e-5)
        if name in ('window','wall','door_open','door_closed'):normal[missing]=[0,1,0]
        ao=data_image(render/(name+'_ao.png'),size)[:,:,0]
        rgb=np.rint((normal*.5+.5)*255).clip(0,255).astype('uint8')
        packed=np.dstack((rgb,np.rint(ao*255).astype('uint8')));packed[~mask]=0
        Image.fromarray(packed).save(runtime/(name+'_normal.png'))
        position=data_image(render/(name+'_position.png'),size)
        roughness=.35 if name=='lantern_porcelain' else .85 if name.startswith('lily') else .9
        packed=np.dstack((np.rint(position*255).astype('uint8'),np.full(mask.shape,round(roughness*255),dtype='uint8')));packed[~mask]=0
        Image.fromarray(packed).save(runtime/(name+'_position.png'))
        # Export human-readable scalar layers separately. Units and decode bounds
        # are recorded; the shader uses the position map to recover actual height.
        lo=np.asarray(rec['position_min']);hi=np.asarray(rec['position_max']);world=lo+position*(hi-lo)
        depth=world@np.array([0,-rec['depth_direction'][1],rec['depth_direction'][2]])
        dmin=float(depth[mask].min());dmax=float(depth[mask].max());rec['depth_range']=[dmin,dmax]
        height=(world[:,:,2]-lo[2])/max(.001,hi[2]-lo[2]);dep=(depth-dmin)/max(.001,dmax-dmin)
        for suffix,values in [('height',height),('depth',dep)]:
            values=np.where(mask,values,0);Image.fromarray(np.rint(values.clip(0,1)*65535).astype('uint16')).save(runtime/(name+'_'+suffix+'.png'))
        Image.fromarray(np.where(mask,np.rint(ao*255),0).astype('uint8')).save(runtime/(name+'_ao.png'))
        Image.fromarray(mask.astype('uint8')*255).save(runtime/(name+'_mask.png'))
        if name=='lantern_paper':
            # Genuine printed characters and caps stay dark; only paper glows.
            from build import emission
            emission(color).save(runtime/(name+'_emission.png'))
        rec['sha256']={suffix:hashlib.sha256((runtime/(name+suffix+'.png')).read_bytes()).hexdigest() for suffix in ('','_normal','_position','_height','_depth','_ao','_mask')}
        rec['normal_encoding']='RGB game-world unit normal (X right, Y down ground, Z up); A ambient occlusion'
        rec['position_encoding']='RGB normalized local game position between position_min/max; A roughness'
        x=index%4*300+8;y=index//4*230
        draw.text((x,y+7),name+' / colour + normals',fill='white')
        scale=max(1,min(3,210//size[0],130//size[1]));large=color.resize((size[0]*scale,size[1]*scale),Image.Resampling.NEAREST)
        sheet.paste(large,(x,y+30),large)
        preview=Image.fromarray(rgb).convert('RGBA');preview.putalpha(color.getchannel('A'));sheet.paste(preview,(x,y+175),preview)
    # Preserve world-registered two-axis floor placement.
    for suffix in ('','_mask','_ao','_height','_depth'):
        Image.open(runtime/('planks_x'+suffix+'.png')).transpose(Image.Transpose.ROTATE_90).save(runtime/('planks_y'+suffix+'.png'))
    normal=np.asarray(Image.open(runtime/'planks_x_normal.png')).copy();normal=np.rot90(normal).copy()
    old=normal[:,:,:2].copy();normal[:,:,0]=old[:,:,1];normal[:,:,1]=255-old[:,:,0]
    Image.fromarray(normal).save(runtime/'planks_y_normal.png')
    sheet.save(ROOT/'asset-review.png')
    (ROOT/'manifest.json').write_text(json.dumps(dict(version=1,assets=records,materials=sources),indent=2))
    print('Exported',len(records),'Blender assets with colour, normals, position, height, depth and AO.')


if __name__=='__main__':main()
