"""Prepare traceable photographic materials and the existing aperture contract."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
import build as photos
import g_night


def main():
    folder=HERE/'textures';folder.mkdir(parents=True,exist_ok=True);records={}
    def save(name,im,sources,operation):
        im.save(folder/(name+'.png'))
        records[name]=dict(sources=sources,operation=operation,sha256=hashlib.sha256((folder/(name+'.png')).read_bytes()).hexdigest())
    # The scans contain the detail; Blender supplies joints, edges and volume.
    save('wood',photos.original('Wood058').resize((1024,1024)),['Wood058'],'Whole preserved scan, 1024px texture')
    for name,source,box,size in (
        ('timber','tang_lantern',(210,741,528,765),(893,1000)),
        ('brick','tang_lantern',(8,565,185,688),(893,1000)),
        ('paper','tang_lantern',(294,221,529,512),(893,1000)),
        ('painted','temple_pavilion',(651,334,968,367),(1000,667)),
        ('ceramic','walters_lantern',(254,318,560,730),(809,1000))):
        im=photos.texture_crop(source,box,size)
        if name=='paper':im=Image.fromarray(photos.srgb(photos.linear(im.convert('RGB'))*1.45))
        save(name,im,[source],dict(crop=box,reference_size=size,linear_exposure=1.45 if name=='paper' else 1.))
    architecture=photos.architecture()
    save('column',architecture['column'][0],['pavilion'],'Perspective-rectified pillar, same source quad as photo pipeline')
    # Stone grain is a desaturated close crop of the actual temple brick face.
    brick=photos.texture_crop('tang_lantern',(25,605,76,625),(893,1000)).convert('RGB')
    save('stone',brick,['tang_lantern'],'Brick face crop [25,605,76,625] at reference 893x1000; used for stone bowls and plinths')
    for name,source in (('pad','lily_pad'),('pad_small','lily_pad_small'),('flower','lily_flower')):
        master=Image.open(ROOT/'masters'/(source+'.png')).convert('RGBA')
        save(name,master.resize((512,512),Image.Resampling.LANCZOS),photos.SETTINGS[source]['source'].split(),
             'Existing photo mask and crop, rectified to square UV domain; shallow relief geometry, not a recovered scan')
    save('buddha',Image.open(ROOT.parent/'art'/'buddha_128.png').convert('RGBA'),['user_buddha'],
         'Existing user photograph sprite on an altar photo-card; no invented back of statue')
    # Hanging textile uses genuine decorative paint, without invented writing.
    save('banner',photos.texture_crop('temple_pavilion',(651,334,714,367),(1000,667)),['temple_pavilion'],
         'Decorative painted motif on a hanging panel; material study, not an authenticated textile')
    apertures={};aperture_pixels={}
    for name,kind,w,opened in [('window','window_wall',48,False),('wall','wood_wall',16,False),
                              ('door_open','pierced_door',32,True),('door_closed','pierced_door',32,False)]:
        _,holes=g_night.facade_art(dict(type=kind,width=w,height=56,seed=7),opened)
        holes.save(HERE/(name+'_holes.png'));apertures[name]=dict(width=w,height=56,kind=kind,opened=opened)
        aperture_pixels[name]=np.asarray(holes).tolist()
    (HERE/'apertures.json').write_text(json.dumps(apertures,indent=2))
    (HERE/'aperture_pixels.json').write_text(json.dumps(aperture_pixels))
    (HERE/'sources.json').write_text(json.dumps(records,indent=2))
    sheet=Image.new('RGB',(960,240*((len(records)+3)//4)),(23,29,36));d=ImageDraw.Draw(sheet)
    for i,name in enumerate(records):
        im=Image.open(folder/(name+'.png')).convert('RGBA');im.thumbnail((224,205))
        x=(i%4)*240+8;y=(i//4)*240;d.text((x,y+8),name,fill='white');sheet.paste(im,(x,y+28),im)
    sheet.save(HERE/'materials.png')
    print('Prepared photo materials and matching window/door apertures.')


if __name__=='__main__':main()
