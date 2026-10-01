"""Extract photo fragments for actual roof surfaces, not a front-photo billboard."""
from pathlib import Path
import sys,json,hashlib
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from build import original,texture_crop


def main():
    folder=ROOT/'textures';folder.mkdir(exist_ok=True)
    source=original('temple_pavilion');sx=source.width/1000;sy=source.height/667
    # An unobscured lower-roof patch: repeated tile courses, without the roof's
    # sky/finial/silhouette. The quadrilateral is rectified to surface UV space.
    quad=[(451,243),(442,280),(693,281),(683,240)]
    tiles=source.transform((1024,256),Image.Transform.QUAD,
        tuple(v for x,y in quad for v in (x*sx,y*sy)),Image.Resampling.BICUBIC)
    tiles.save(folder/'tiles.png')
    caps=texture_crop('temple_pavilion',(447,280,687,295),(1000,667)).convert('RGB')
    caps.save(folder/'tile_ends.png')
    trim=texture_crop('temple_pavilion',(651,334,968,367),(1000,667)).convert('RGB')
    trim.save(folder/'fascia.png')
    wood=texture_crop('tang_lantern',(210,741,528,765),(893,1000)).convert('RGB')
    wood.save(folder/'timber.png')
    manifest={
        'tiles':dict(source='temple_pavilion',reference_size=[1000,667],quad_tl_bl_br_tr=quad,operation='four-corner perspective rectification'),
        'tile_ends':dict(source='temple_pavilion',reference_size=[1000,667],crop=[447,280,687,295]),
        'fascia':dict(source='temple_pavilion',reference_size=[1000,667],crop=[651,334,968,367]),
        'timber':dict(source='tang_lantern',reference_size=[893,1000],crop=[210,741,528,765])}
    for name,data in manifest.items():data['sha256']=hashlib.sha256((folder/(name+'.png')).read_bytes()).hexdigest()
    (ROOT/'texture_sources.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    sheet=Image.new('RGB',(1024,650),(25,30,36));draw=ImageDraw.Draw(sheet)
    y=0
    for name,im in [('Rectified roof tile courses',tiles),('Photographed tile ends',caps),('Painted wooden fascia',trim),('Old timber',wood)]:
        draw.text((8,y+4),name,fill='white');y+=24
        im.thumbnail((1000,180));sheet.paste(im,(8,y));y+=im.height+12
    sheet.save(ROOT/'textures-review.png')
    print('Prepared four traceable photographic roof textures.')


if __name__=='__main__':main()
