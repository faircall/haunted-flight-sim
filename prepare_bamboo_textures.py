"""Pack the original painted grove surfaces into mip-safe 128px material tiles."""
from pathlib import Path
import math
import random

ROOT=Path(__file__).parent;OUT=ROOT/'art'/'temple'/'bamboo'
NAMES=('bamboo','node','leaf','leaflight','earth','moss','stone','plaster','wood','roof','flower','bronze','paper','cloth','cap','water')

def build():
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont,ImageEnhance
    source=Image.open(OUT/'materials_source.png').convert('RGB');w,h=source.size
    panels=[source.crop((i%2*w//2,i//2*h//2,(i%2+1)*w//2,(i//2+1)*h//2)) for i in range(4)]
    old=Image.open(ROOT/'art'/'temple'/'interior'/'architecture.png').convert('RGB')
    oldtile=lambda n:old.crop((n%4*256+64,n//4*256+64,n%4*256+192,n//4*256+192))
    rng=random.Random(120);atlas=Image.new('RGB',(1024,1024))
    for i,name in enumerate(NAMES):
        base={'node':(122,139,83),'leaf':(55,88,47),'leaflight':(102,126,57),'earth':(54,59,39),'moss':(61,79,43),
              'flower':(216,209,175),'paper':(229,195,126),'water':(47,74,66)}.get(name,(80,85,62))
        tile=Image.new('RGB',(128,128));d=ImageDraw.Draw(tile)
        for y in range(128):
            for x in range(128):
                noise=rng.uniform(-5,5)+4*math.sin(x*.08)*math.sin(y*.09)
                if name in ('leaf','leaflight'):noise+=14*(1-abs(x-64)/64)
                if name=='node':noise+=6*math.sin(y*.1)
                tile.putpixel((x,y),tuple(max(0,min(255,round(v+noise))) for v in base))
        if name in ('earth','moss'):
            for j in range(130):
                x,y=rng.randrange(128),rng.randrange(128);length=rng.randrange(3,15)
                d.line((x,y,x+rng.randrange(-6,7),y+length),fill=rng.choice(((74,72,40),(93,86,52),(40,49,30),(76,85,44))),width=1)
        if name in ('leaf','leaflight'):
            d.line((64,0,64,128),fill=(124,141,66),width=1)
            for y in range(8,128,11):
                for sign in (-1,1):d.line((64,y,64+sign*45,y+12),fill=(73,104,51),width=1)
        if name in ('stone','plaster','bamboo'):tile=panels[{'stone':0,'plaster':1,'bamboo':2}[name]].resize((128,128),Image.Resampling.LANCZOS)
        if name in ('wood','roof','bronze','cloth','cap'):
            tile=oldtile({'wood':2,'roof':11,'bronze':8,'cloth':12,'cap':3}[name])
            if name=='wood':tile=ImageEnhance.Brightness(tile).enhance(1.3)
        padded=Image.fromarray(np.pad(np.asarray(tile),((64,64),(64,64),(0,0)),mode='edge'))
        atlas.paste(padded,(i%4*256,i//4*256))
    atlas.save(OUT/'materials.png')
    art=Image.new('RGB',(1024,1024),(186,169,131));art.paste(panels[3].resize((512,512),Image.Resampling.LANCZOS),(0,0))
    # Exact poem typography is rendered from the local Chinese font, not invented.
    fontpath=next(p for p in (Path('C:/Windows/Fonts/simkai.ttf'),Path('C:/Windows/Fonts/simsun.ttc'),Path('C:/Windows/Fonts/msyh.ttc')) if p.exists())
    for index,line in ((1,'曲径通幽处'),(2,'禅房花木深')):
        panel=Image.new('RGB',(160,1024),(152,131,92));draw=ImageDraw.Draw(panel);font=ImageFont.truetype(str(fontpath),132)
        draw.rectangle((5,5,154,1018),outline=(87,67,44),width=4)
        for j,char in enumerate(line):draw.text((14,80+j*170),char,font=font,fill=(37,43,33),stroke_width=0)
        art.paste(panel.resize((512,512),Image.Resampling.LANCZOS),(index%2*512,index//2*512))
    plaque=Image.new('RGB',(640,180),(34,44,37));d=ImageDraw.Draw(plaque);font=ImageFont.truetype(str(fontpath),132)
    d.rectangle((5,5,634,174),outline=(129,124,88),width=6);d.text((53,18),'竹隐禅房',font=font,fill=(191,180,123))
    art.paste(plaque.resize((512,512),Image.Resampling.LANCZOS),(512,512));art.save(OUT/'scrolls.png')

if __name__=='__main__':build()
