"""Offline photo cutouts and sprite baking. No generative models or runtime work.

Run from any directory: python photo_asset_pipeline/build.py
Polygons are editable in settings.json, measured on the stated reference size.
RGBA response maps encode down/up/left/right, NOT colour or transparency.
"""
from pathlib import Path
import json, hashlib, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parent
SETTINGS=json.loads((ROOT/'settings.json').read_text(encoding='utf8'))


def original(name):
    record=json.loads((ROOT/'sources'/name/'source.json').read_text(encoding='utf8'))
    return Image.open(ROOT/record['original_file']).convert('RGB')


def linear(rgb):
    rgb=np.asarray(rgb,dtype=np.float32)/255.
    return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)


def srgb(rgb):
    rgb=np.clip(rgb,0,1)
    return np.rint(np.where(rgb<=.0031308,rgb*12.92,1.055*rgb**(1/2.4)-.055)*255).astype('uint8')


def resize_rgba(im,size):
    """Linear-light, premultiplied-alpha resize: no black/grey matte fringe."""
    if im.size==tuple(size):return im.copy()
    data=np.asarray(im.convert('RGBA'));alpha=data[:,:,3].astype(np.float32)/255.
    channels=[linear(data[:,:,:3])[:,:,i]*alpha for i in range(3)]+[alpha]
    values=[np.asarray(Image.fromarray(c).resize(size,Image.Resampling.LANCZOS)).clip(0,1) for c in channels]
    a=values[3];rgb=np.stack(values[:3],axis=-1)/np.maximum(a[:,:,None],1.e-7)
    return Image.fromarray(np.dstack((srgb(rgb),np.rint(a*255).astype('uint8'))))


def pixels(im,size,colours=64,threshold=128):
    """Resize FIRST, then quantize visible pixels only, with no dithering."""
    arr=np.asarray(resize_rgba(im,size)).copy();visible=arr[:,:,3]>=threshold
    if visible.any():
        samples=Image.fromarray(arr[:,:,:3][visible].reshape((-1,1,3)))
        palette=samples.quantize(colors=colours,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        quantized=Image.fromarray(arr[:,:,:3]).quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
        arr[:,:,:3]=np.asarray(quantized)
    arr[:,:,3]=visible.astype('uint8')*255;arr[~visible]=0
    return Image.fromarray(arr)


def contain(im,size):
    scale=min(size[0]/im.width,size[1]/im.height)
    fitted=resize_rgba(im,(max(1,round(im.width*scale)),max(1,round(im.height*scale))))
    out=Image.new('RGBA',size);out.paste(fitted,((size[0]-fitted.width)//2,size[1]-fitted.height))
    return out


def cutout(cfg):
    source=original(cfg['source']);sx=source.width/cfg['reference_size'][0];sy=source.height/cfg['reference_size'][1]
    coords=lambda pts:[(round(x*sx),round(y*sy)) for x,y in pts]
    mask=Image.new('L',source.size);d=ImageDraw.Draw(mask)
    d.polygon(coords(cfg['polygon']),fill=255)
    for hole in cfg.get('holes',[]):d.polygon(coords(hole),fill=0)
    rgb=np.asarray(source).astype(np.int16);mode=cfg.get('remove')
    if mode=='sky':
        sky=(rgb.min(axis=2)>184)&(rgb.max(axis=2)-rgb.min(axis=2)<32)
        mask=Image.fromarray(np.where(sky,0,np.asarray(mask)).astype('uint8'))
    elif mode=='purple':
        flower=((rgb[:,:,0]-rgb[:,:,1]>13)&(rgb[:,:,2]-rgb[:,:,1]>18))|((rgb[:,:,0]>165)&(rgb[:,:,1]>135)&(rgb[:,:,0]>rgb[:,:,2]))
        mask=Image.fromarray(np.where(flower,np.asarray(mask),0).astype('uint8'))
    if cfg.get('exposure',1)!=1:source=Image.fromarray(srgb(linear(source)*cfg['exposure']))
    source=source.convert('RGBA');source.putalpha(mask)
    # One source-pixel erosion removes mixed background/foreground boundary pixels.
    mask=mask.filter(ImageFilter.MinFilter(3));source.putalpha(mask)
    bounds=mask.getbbox();crop=source.crop(bounds)
    arr=np.asarray(crop).copy();arr[arr[:,:,3]==0]=0
    return Image.fromarray(arr),bounds


def response(im,shape):
    """Conservative authored geometry, not alleged normals recovered from RGB.

    Photo shading remains in the colour image. Gentle response reduces double
    shading; replace the four greyscale layers if a painted map is available.
    """
    h,w=im.height,im.width;y,x=np.mgrid[:h,:w];u=(x+.5)/w;v=(y+.5)/h
    if shape=='round':
        side=np.clip((u-.5)*2,-1,1)
        values=(np.full((h,w),.9),np.full((h,w),.40),.72-.24*side,.72+.24*side)
    elif shape=='roof':
        slope=np.clip((v-.2)*1.4,0,1)
        values=(.76+.12*slope,.62-.12*slope,.76-.14*(u-.5),.76+.14*(u-.5))
    elif shape=='leaf':
        values=(np.full((h,w),.92),np.full((h,w),.85),np.full((h,w),.88),np.full((h,w),.88))
    else:
        values=(np.full((h,w),.9),np.full((h,w),.52),np.full((h,w),.76),np.full((h,w),.76))
    arr=np.rint(np.stack(values,axis=-1)*255).astype('uint8')
    arr[np.asarray(im)[:,:,3]==0]=0
    return Image.fromarray(arr,'RGBA')


def save_response(name,im,shape):
    packed=response(im,shape)
    dest=ROOT/'responses'/name;dest.mkdir(parents=True,exist_ok=True)
    for channel,label in zip(packed.split(),('down','up','left','right')):channel.save(dest/(label+'.png'))
    authored=ROOT/'response_edits'/name
    if authored.exists():
        channels=[]
        for label in ('down','up','left','right'):
            with Image.open(authored/(label+'.png')) as channel:
                if channel.size!=im.size:raise ValueError(f'{authored}/{label}.png must be {im.size}')
                channels.append(channel.convert('L'))
        packed=Image.merge('RGBA',channels)
    packed.save(ROOT/'runtime'/(name+'_response.png'))


def emission(im):
    a=np.asarray(im).copy();rgb=a[:,:,:3].astype(float);h,w=a.shape[:2];yy,xx=np.mgrid[:h,:w]
    # Preserve the dark lettering/caps. Only warm paper leaks a little light.
    paper=(yy>h*.14)&(yy<h*.77)&(a[:,:,3]>0)&(rgb.min(axis=2)>34)
    brightness=np.clip(rgb.min(axis=2)/120.,0,.48)*paper
    a[:,:,:3]=np.rint(brightness[:,:,None]*np.array([125,68,25])).astype('uint8')
    a[:,:,3]=np.where(paper,255,0);a[a[:,:,3]==0]=0
    return Image.fromarray(a)


def texture_crop(name,box,reference_size):
    im=original(name);sx=im.width/reference_size[0];sy=im.height/reference_size[1]
    return im.crop(tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))).convert('RGBA')


def architecture():
    """Photo fragments on simple cut geometry. All grain/wear comes from photos."""
    timber=original('Wood058').convert('RGBA')
    # Master board atlas, including narrow physical joints; never random grain.
    floor=Image.new('RGBA',(1024,256));horizontal=timber.transpose(Image.Transpose.ROTATE_90)
    for row in range(8):
        strip=horizontal.crop((0,row*240,2048,row*240+224))
        strip=resize_rgba(strip,(1024,32));floor.paste(strip,(0,row*32))
    d=ImageDraw.Draw(floor)
    for row in range(8):
        d.rectangle((0,row*32,1023,row*32+3),fill=(51,43,35,255))
        joint=(row*317+123)%1024
        d.rectangle((joint,row*32+4,joint+3,row*32+31),fill=(62,51,42,255))
    # Beams have photographed red-brown wood; blocks below retain wear from it.
    beam=texture_crop('tang_lantern',(210,741,528,765),(893,1000))
    post=texture_crop('tang_lantern',(210,770,243,810),(893,1000))
    rail=Image.new('RGBA',(256,136))
    for y in (24,64):rail.paste(resize_rgba(beam,(256,24)),(0,y))
    for x in (0,128):rail.paste(resize_rgba(post,(32,136)),(x,0))
    col_source=original('pavilion');sx=col_source.width/1000;sy=col_source.height/750
    quad=[(734,362),(768,740),(823,740),(776,359)]  # TL, BL, BR, TR
    column=col_source.transform((160,1216),Image.Transform.QUAD,
        tuple(v for x,y in quad for v in (x*sx,y*sy)),Image.Resampling.BICUBIC).convert('RGBA')
    # Actual painted eave fascia from the unobscured right-hand bay.
    frieze=texture_crop('temple_pavilion',(651,334,968,367),(1000,667))
    brick=texture_crop('tang_lantern',(8,565,185,688),(893,1000))
    wall=resize_rgba(timber,(384,448));wd=ImageDraw.Draw(wall)
    for x in range(0,384,48):wd.rectangle((x,0,x+3,447),fill=(53,42,33,255))
    wall.paste(resize_rgba(frieze,(384,56)),(0,0))
    for x in (0,352):wall.paste(resize_rgba(column,(32,448)),(x,0))
    wall.paste(resize_rgba(beam,(384,24)),(0,412))
    return {
        'planks_x':(floor,(128,32),['Wood058'],'Photographic scan, rotated grain and perspective-compressed board strips; thin authored joints.'),
        'planks_y':(floor.transpose(Image.Transpose.ROTATE_90),(32,128),['Wood058'],'Same board atlas rotated 90 degrees.'),
        'rail':(rail,(32,17),['tang_lantern'],'Actual timber photo fragments placed on the existing open rail geometry.'),
        'column':(column,(10,58),['pavilion'],'Photographed worn red pillar; a four-corner perspective correction straightens the camera convergence.'),
        'pile':(timber.crop((580,0,880,2048)),(5,28),['Wood058'],'Narrow vertical timber scan crop.'),
        'wall':(wall,(48,56),['Wood058','temple_pavilion','tang_lantern','pavilion'],'Timber scan, actual painted fascia and red post crops; aperture geometry stays in the renderer.'),
        'wall_ground':(brick,(48,32),['tang_lantern'],'Actual grey temple brickwork crop for wall footprints.'),
        'frieze':(frieze,(128,14),['temple_pavilion'],'Painted beam fragment, available as a reusable architectural trim.')}


def variants(name,master,architecture=False):
    dest=ROOT/'variants'/name;dest.mkdir(parents=True,exist_ok=True)
    for edge,count in [(128,32),(128,64),(64,32)]+([(256,64)] if architecture else []):
        scale=edge/max(master.size);size=tuple(max(1,round(n*scale)) for n in master.size)
        pixels(master,size,count).save(dest/f'{edge}px_{count}col.png')


def checker(size,dark=True):
    base=(24,29,36) if dark else (221,220,207);other=(34,40,47) if dark else (238,237,225)
    im=Image.new('RGBA',size,base+(255,));d=ImageDraw.Draw(im)
    for y in range(0,size[1],12):
        for x in range(0,size[0],12):
            if (x//12+y//12)%2:d.rectangle((x,y,x+11,y+11),fill=other+(255,))
    return im


def review(name,master,record):
    out=Image.new('RGB',(1450,470),(31,36,43));d=ImageDraw.Draw(out)
    d.text((16,10),name+' | source / cutout / 128px 32 / 128px 64 / 64px 32 / game size',fill=(230,220,192))
    source=original(record['sources'][0]);source.thumbnail((190,190))
    out.paste(source,((200-source.width)//2,35))
    thumbs=[master]+[Image.open(ROOT/'variants'/name/fn) for fn in ('128px_32col.png','128px_64col.png','64px_32col.png')]+[Image.open(ROOT/'runtime'/(name+'.png'))]
    for i,im in enumerate(thumbs,1):
        for dark,y in ((True,35),(False,245)):
            bg=checker((192,195),dark);factor=min(184/im.width,181/im.height)
            if i>1:factor=max(1,int(factor))
            thumb=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.NEAREST if i>1 else Image.Resampling.LANCZOS)
            if thumb.width>192 or thumb.height>195:thumb.thumbnail((184,181),Image.Resampling.NEAREST)
            bg.alpha_composite(thumb,((192-thumb.width)//2,(195-thumb.height)//2));out.paste(bg.convert('RGB'),(i*200+4,y))
    runtime=thumbs[-1];out.paste(runtime,(1210,270),runtime)
    d.text((1208,244),'Native pixels',fill='white')
    d.text((8,450),'All enlarged sprite previews use nearest-neighbour; alpha is binary at runtime.',fill=(177,184,191))
    out.save(ROOT/'review'/(name+'.png'))


def main():
    for directory in ('masters','masks','runtime','responses','variants','review'):(ROOT/directory).mkdir(exist_ok=True)
    records={};masters={}
    for name,cfg in SETTINGS.items():
        master,bounds=cutout(cfg);masters[name]=master
        master.save(ROOT/'masters'/(name+'.png'));master.getchannel('A').save(ROOT/'masks'/(name+'.png'))
        variants(name,master,cfg.get('architecture',False))
        native=pixels(contain(master,tuple(cfg['runtime'])),tuple(cfg['runtime']),64)
        native.save(ROOT/'runtime'/(name+'.png'));save_response(name,native,cfg['response'])
        if cfg.get('emission'):emission(native).save(ROOT/'runtime'/(name+'_emission.png'))
        records[name]=dict(sources=[cfg['source']],source_crop=bounds,runtime_size=native.size,
            palette=64,note=cfg['note'],response='Conservative geometry draft: RGBA=down/up/left/right',pivot=[native.width/2,0] if 'lantern' in name else [native.width/2,native.height])
    for name,(master,size,sources,note) in architecture().items():
        masters[name]=master;master.save(ROOT/'masters'/(name+'.png'));master.getchannel('A').save(ROOT/'masks'/(name+'.png'))
        variants(name,master,True);native=pixels(master,size,64);native.save(ROOT/'runtime'/(name+'.png'))
        save_response(name,native,'wood')
        records[name]=dict(sources=sources,runtime_size=size,palette=64,note=note,response='Conservative wood geometry draft: RGBA=down/up/left/right',pivot=[size[0]/2,size[1]])
    # Actual-size composition, all assembled from already-isolated photos.
    for name,flower in [('lily_cluster',True),('lily_leaves',False)]:
        im=Image.new('RGBA',(26,20));im.alpha_composite(Image.open(ROOT/'runtime'/'lily_pad_small.png'),(0,1))
        im.alpha_composite(Image.open(ROOT/'runtime'/'lily_pad.png'),(2,3))
        if flower:im.alpha_composite(Image.open(ROOT/'runtime'/'lily_flower.png'),(7,0))
        im=pixels(im,im.size,64);im.save(ROOT/'runtime'/(name+'.png'));save_response(name,im,'leaf')
        records[name]=dict(sources=['pads_pond','white_lily'] if flower else ['pads_pond'],runtime_size=im.size,palette=64,note='Composite of intact photo cutouts; no invented foliage.')
    for name,rec in records.items():
        fn=ROOT/'runtime'/(name+'.png');rec['sha256']=hashlib.sha256(fn.read_bytes()).hexdigest()
        if name in masters:review(name,masters[name],rec)
    # Separate Blender baking owns these files. A photo-only rebuild preserves
    # the chosen roof renders and does not regenerate their geometric responses.
    baked=ROOT/'blender'/'baked_assets.json'
    if baked.exists():records.update(json.loads(baked.read_text(encoding='utf8')))
    (ROOT/'manifest.json').write_text(json.dumps(dict(version=1,assets=records),indent=2),encoding='utf8')
    # Compact runtime board, native and 3x, so tiny assets are not judged at 128px.
    board=checker((1000,220*math.ceil(len(records)/4)));d=ImageDraw.Draw(board)
    for i,name in enumerate(records):
        col=i%4;row=i//4;x=col*250;y=row*220
        im=Image.open(ROOT/'runtime'/(name+'.png'));scale=max(1,min(3,190//im.height,234//im.width))
        d.text((x+8,y+8),f'{name} ({im.width}x{im.height}, {scale}x)',fill='white')
        big=im.resize((im.width*scale,im.height*scale),Image.Resampling.NEAREST)
        board.alpha_composite(big,(x+8,y+26))
    board.convert('RGB').save(ROOT/'review'/'runtime-contact-sheet.png')
    make_gallery(records)
    print(f'Built {len(records)} photo-derived assets, masters, masks, variants, draft responses and review sheets.')


def make_gallery(records):
    import html
    cards=[]
    for name,rec in records.items():
        w,h=rec['runtime_size']
        links=' '.join(f'<a href="sources/{s}/source.json">{s}</a>' for s in rec['sources'])
        review_link=f'<a href="review/{name}.png">Variants and mask review</a>' if (ROOT/'review'/(name+'.png')).exists() else ''
        cards.append(f'<article><h3>{name.replace("_"," ")}</h3><div class="well"><img class="sprite" width="{w}" height="{h}" src="runtime/{name}.png" alt="{name}"></div><small>{w} x {h} native pixels; up to 64 colours</small><p>{html.escape(rec["note"])}</p>{review_link}<p class="sources">Sources: {links}</p></article>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Water temple / photographic art study</title><style>
:root{color-scheme:dark;font-family:system-ui;background:#141a20;color:#d8d4c8}body{max-width:1250px;margin:40px auto;padding:0 24px}h1{font-family:Georgia;font-weight:normal;font-size:42px;margin-bottom:8px}h2{font-weight:500}a{color:#debf83}p{line-height:1.55}header p{max-width:780px;color:#aeb8bf}.toolbar{position:sticky;top:0;background:#141a20ee;padding:16px 0;z-index:1;display:flex;gap:20px}button{background:#303c44;color:inherit;border:1px solid #64717a;padding:9px 14px;cursor:pointer}.scenes{display:grid;grid-template-columns:1fr 1fr;gap:16px}.scenes img{width:100%;image-rendering:pixelated}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}article{border:1px solid #38434a;padding:18px}h3{margin-top:0;text-transform:capitalize}.well{height:244px;display:flex;align-items:center;justify-content:center;background:#202932;overflow:hidden}.sprite{image-rendering:pixelated;object-fit:contain;max-width:100%;transform-origin:center}body.enlarged .sprite{zoom:2}body.light .well{background:#dedbcf}small,.sources{color:#aeb8bf;font-size:12px}article p{font-size:14px}.tag{color:#dcad69;letter-spacing:.16em;font-size:11px}footer{margin-top:40px;border-top:1px solid #38434a;padding-top:20px;color:#aeb8bf}@media(max-width:700px){.scenes{grid-template-columns:1fr}h1{font-size:30px}}
</style><header><div class="tag">PHOTOGRAPHIC ART STUDY / FIRST PASS</div><h1>Moonlit water temple</h1>
<p>Photographs reduced to crisp pixels, preserving their shading and material wear. The roof uses photographic crops on a curved Blender mesh, baked to a sprite. The original scene stays available; this study uses the same 2D renderer and gameplay.</p>
<p>Play: <code>python moonlit_water_temple_photo.py</code> &nbsp; <a href="README.md">Pipeline and review notes</a> / <a href="SOURCES.md">Source ledger</a></p></header>
<p><strong>Newer comparison:</strong> <a href="temple3d/README.md">Full Blender temple kit, normal lighting and live 3D viewer</a> / <a href="temple3d/review/comparison.png">Scene screenshots</a></p>
<h2>Same camera, same moonlight</h2><div class="scenes"><figure><figcaption>Previous assets</figcaption><a href="review/painted-moon.png"><img src="review/painted-moon.png" alt="Painted comparison"></a></figure><figure><figcaption>Photo-derived assets</figcaption><a href="review/photo-moon.png"><img src="review/photo-moon.png" alt="Photo comparison"></a></figure></div>
<p><a href="review/photo-ambient.png">Brighter colour inspection</a> / <a href="review/photo-inside.png">Inside / roof hidden</a> / <a href="review/photo-storm.png">Storm</a> / <a href="review/photo-lightning.png">Lightning</a></p>
<p><a href="review/roof-in-scene-comparison.png">Roof camera angles in the game</a> / <a href="review/roof-angle-comparison.png">Roof native pixels and 2x review</a> / <a href="blender/README.md">Editable Blender model and rebuild instructions</a></p>
<h2>Runtime assets</h2><div class="toolbar"><button onclick="document.body.classList.toggle('enlarged')">Native / 2x pixels</button><button onclick="document.body.classList.toggle('light')">Dark / light background</button></div><div class="grid">'''+''.join(cards)+'''</div><footer>All baking happens offline. Runtime colours have no dithering; transparency is binary. Directional response maps are geometry-based drafts, not recovered 3D normals. Photos, masks and larger masters are preserved.</footer></html>'''
    (ROOT/'index.html').write_text(page,encoding='utf8')


if __name__=='__main__':main()
