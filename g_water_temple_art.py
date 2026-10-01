"""Replaceable procedural architecture for the water-temple prototype."""
from PIL import Image,ImageDraw
from pathlib import Path
import g_surfaces
RUNTIME_GENERATION=globals().get('RUNTIME_GENERATION',0)+1


def roof():
    im=Image.new('RGBA',(216,116));d=ImageDraw.Draw(im)
    silhouette=[(1,84),(13,96),(34,86),(64,19),(77,15),(145,15),(155,21),(183,86),(204,96),(214,84),(209,104),(190,110),(24,110),(6,104)]
    d.polygon(silhouette,fill=(32,44,54,255))
    mask=im.getchannel('A')
    tiles=Image.new('RGBA',im.size);t=ImageDraw.Draw(tiles)
    for y in range(23,108,5):
        for x in range(-8,224,7):
            xx=x+(y//5%2)*3
            grain=g_surfaces.noise(xx,y,201)
            c=int(54+grain*18)
            t.rectangle((xx,y,xx+5,y+3),fill=(c-12,c,c+8,255))
            t.line((xx,y+3,xx+5,y+3),fill=(25,35,45,255))
            t.point((xx+1,y),fill=(104,126,132,255))
    im.paste(tiles,(0,0),mask);d=ImageDraw.Draw(im)
    for off,c in ((0,(130,150,149,255)),(2,(50,66,73,255)),(4,(90,112,121,255))):
        d.line([(4,87+off),(13,98+off),(34,94+off),(64,93+off),(151,93+off),(183,94+off),(204,98+off),(212,87+off)],fill=c,width=2)
    d.rectangle((67,15,151,20),fill=(95,112,118,255))
    d.line((67,14,151,14),fill=(162,168,151,255))
    for x in (61,155):
        d.polygon([(x,20),(x-4,7),(x+3,11),(x+6,20)],fill=(100,126,136,255))
    d.rectangle((20,105,194,111),fill=(49,33,29,255))
    for x in range(24,192,8):d.rectangle((x,104,x+2,109),fill=(102,79,54,255))
    return im


def image(kind,width=16,height=24,asset=None):
    if asset:
        root=Path(__file__).resolve().parent
        path=(root/'photo_asset_pipeline'/'temple3d'/'runtime'/(asset[6:]+'.png') if asset.startswith('baked:') else
              root/'photo_asset_pipeline'/'runtime'/(asset[6:]+'.png') if asset.startswith('photo:')
              else root/'art'/'temple'/(asset+'.png'))
        with Image.open(path) as source:
            return source.convert('RGBA').resize((width,height),Image.Resampling.NEAREST)
    if kind=='roof':return roof()
    im=Image.new('RGBA',(width,height));d=ImageDraw.Draw(im)
    if kind=='column':
        d.rectangle((2,3,width-3,height-5),fill=(77,39,28,255))
        d.line((3,4,3,height-6),fill=(151,101,60,255),width=2)
        for y in (0,4,height-7,height-3):d.rectangle((0,y,width-1,y+2),fill=(101,98,82,255))
    elif kind=='rail':
        for y in (3,8):
            d.rectangle((0,y,width-1,y+2),fill=(74,58,45,255))
            d.line((0,y,width-1,y),fill=(125,128,110,255))
        for x in range(0,width,16):
            d.rectangle((x,0,x+3,height-1),fill=(50,45,40,255))
            d.line((x,0,x,height-1),fill=(117,120,105,255))
    elif kind=='pile':
        d.rectangle((1,2,width-2,height-1),fill=(32,28,25,255))
        d.line((1,2,1,height-4),fill=(97,104,90,255))
        for y in range(3,height,7):d.line((2,y,width-2,y+1),fill=(56,51,38,255))
    elif kind=='brazier':
        cx=width//2
        d.rectangle((cx-2,7,cx+2,height-4),fill=(47,51,48,255))
        d.rectangle((cx-4,height-4,cx+4,height-2),fill=(90,89,70,255))
        d.polygon([(1,2),(width-2,2),(width-4,8),(3,8)],fill=(73,58,36,255))
        d.line((1,2,width-2,2),fill=(189,117,43,255))
        d.line((3,3,width-4,3),fill=(224,93,20,255))
    elif kind=='altar':
        cx=width//2
        d.rectangle((2,height-13,width-3,height-4),fill=(105,43,26,255))
        d.rectangle((0,height-14,width-1,height-12),fill=(187,133,70,255))
        for x in (4,width-7):d.rectangle((x,height-4,x+2,height-1),fill=(64,28,20,255))
        d.ellipse((cx-5,2,cx+5,12),fill=(158,129,66,255))
        d.polygon([(cx-6,12),(cx+6,12),(cx+9,28),(cx+13,height-15),(cx-13,height-15),(cx-8,27)],fill=(143,94,48,255))
        d.line((cx-3,5,cx-3,10),fill=(207,180,111,255))
        for y in range(17,29,4):d.line((cx-6,y,cx+5,y+3),fill=(191,146,76,255))
        d.rectangle((cx-14,height-17,cx+14,height-15),fill=(85,67,36,255))
    elif kind=='banner':
        d.polygon([(2,0),(width-3,0),(width-2,height-4),(width//2,height-8),(2,height)],fill=(105,36,26,255))
        for y in range(5,height-7,6):d.line((width//2-2,y,width//2+2,y+2),fill=(159,118,62,255))
        d.line((1,1,width-2,1),fill=(163,136,91,255))
    return im
