"""Reduce Blender renders to the game's crisp sprite/response texture contract."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
import build as pipeline


def data_resize(im,size,alpha):
    """Response/normal channels are linear data, with no sRGB colour transform."""
    arr=np.asarray(im.convert('RGBA'),dtype=np.float32)/255.;a=arr[:,:,3]
    resize=lambda v:np.asarray(Image.fromarray(v).resize(size,Image.Resampling.LANCZOS))
    coverage=resize(a);rgb=np.stack([resize(arr[:,:,i]*a) for i in range(3)],axis=-1)/np.maximum(coverage[:,:,None],1e-5)
    rgb=np.rint(rgb.clip(0,1)*255).astype('uint8');rgb[np.asarray(alpha)==0]=0
    return rgb


def export():
    metadata=json.loads((ROOT/'render_metadata.json').read_text());cfg=metadata['settings'];size=tuple(cfg['runtime_size']);records={}
    runtime=ROOT.parent/'runtime';runtime.mkdir(exist_ok=True)
    comparison=Image.new('RGB',(1368,720),(23,29,36));draw=ImageDraw.Draw(comparison)
    for i,angle in enumerate(cfg['angles']):
        name='roof_blender_'+str(angle)
        master=Image.open(ROOT/'renders'/('roof_'+str(angle)+'.png')).convert('RGBA')
        native=pipeline.pixels(master,size,cfg['palette']);native.save(runtime/(name+'.png'))
        master.save(ROOT.parent/'masters'/(name+'.png'));master.getchannel('A').save(ROOT.parent/'masks'/(name+'.png'))
        pipeline.variants(name,master,True)
        dest=ROOT.parent/'responses'/name;dest.mkdir(parents=True,exist_ok=True);channels=[]
        for label in ('down','up','left','right'):
            rgb=data_resize(Image.open(ROOT/'renders'/f'response_{angle}_{label}.png'),size,native.getchannel('A'))
            layer=Image.fromarray(rgb[:,:,0]);layer.save(dest/(label+'.png'));channels.append(layer)
        override=ROOT.parent/'response_edits'/name
        if override.exists():
            channels=[]
            for label in ('down','up','left','right'):
                with Image.open(override/(label+'.png')) as im:
                    if im.size!=size:raise ValueError(f'{override}/{label}.png must be {size}')
                    channels.append(im.convert('L'))
        Image.merge('RGBA',channels).save(runtime/(name+'_response.png'))
        raw=data_resize(Image.open(ROOT/'renders'/f'normal_{angle}.png'),size,native.getchannel('A'))
        normals=raw.astype(float)/127.5-1.;normals/=np.maximum(np.linalg.norm(normals,axis=2,keepdims=True),1e-5)
        normal_image=Image.fromarray(np.rint((normals+1.)*127.5).clip(0,255).astype('uint8')).convert('RGBA');normal_image.putalpha(native.getchannel('A'))
        normal_image.save(ROOT/'renders'/f'normal_{angle}_native.png')
        camera=metadata['views'][str(angle)]
        records[name]=dict(sources=['temple_pavilion','tang_lantern'],runtime_size=size,palette=cfg['palette'],
            note=f'Photographic tile/wood fragments on a real curved hipped roof; orthographic elevation {angle} degrees. Authored geometry, not a recovered 3D scan.',
            response='Blender shadowed white-material directional renders; RGBA down/up/left/right.',
            camera=camera,pivot=[size[0]/2,size[1]],sha256=hashlib.sha256((runtime/(name+'.png')).read_bytes()).hexdigest())
        pipeline.review(name,master,records[name])
        x=i*456+8;draw.text((x,12),f'{angle} degrees / native pixels',fill='white')
        comparison.paste(native,(x,42),native)
        large=native.resize((432,232),Image.Resampling.NEAREST);comparison.paste(large,(x,180),large)
        draw.text((x,424),'2x nearest / dark and light',fill=(188,192,192))
        panel=Image.new('RGBA',(432,248),(224,222,209,255));panel.alpha_composite(large,(0,8));comparison.paste(panel.convert('RGB'),(x,446))
    comparison.save(ROOT.parent/'review'/'roof-angle-comparison.png')
    (ROOT/'baked_assets.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    target=ROOT.parent/'manifest.json';manifest=json.loads(target.read_text());manifest['assets'].update(records)
    target.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    pipeline.make_gallery(manifest['assets'])
    print('Exported three roof angles, matching directional profiles, normals, masks and palette variants.')


if __name__=='__main__':export()
