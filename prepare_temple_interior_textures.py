"""Deterministic 128px material tiles and painted architectural ornament."""
from pathlib import Path
import math
import random
import numpy as np
from PIL import Image,ImageDraw

OUT=Path(__file__).parent/'art'/'temple'/'interior'
NAMES=('stone','red','wood','cap','coffer','blue','green','scroll','bronze','robe','hair','roof','cloth','plaster','lamp','lotus')
BASE=((84,87,81),(116,37,29),(44,29,24),(123,119,103),(31,69,63),(26,43,65),(29,71,59),(126,43,29),
      (151,112,51),(166,91,42),(30,32,32),(64,77,72),(103,32,26),(131,111,82),(245,165,63),(71,91,77))

def paint():
    OUT.mkdir(parents=True,exist_ok=True);atlas=Image.new('RGB',(1024,1024));rng=random.Random(871)
    ornament=Image.open(OUT/'ornament_source.png').convert('RGB').resize((256,256),Image.Resampling.LANCZOS)
    ornament.save(OUT/'ornament.png')
    for index,name in enumerate(NAMES):
        tile=Image.new('RGB',(128,128));pixels=tile.load();base=BASE[index]
        for y in range(128):
            for x in range(128):
                shade=rng.uniform(-5,5)
                if name in ('wood','red'):shade+=5*math.sin(x*.27+math.sin(y*.036)*2)+3*math.sin(x*.96)
                if name=='stone':
                    shade+=4*math.sin(x*.08+y*.04)+3*math.cos(x*.14-y*.07)
                    if y%64<2 or (x+(y//64%2)*32)%64<2:shade-=23
                if name=='cap':shade+=5*math.sin(x*.09+y*.05)
                if name=='roof':shade+=10*math.cos(x*math.tau/16)-(12 if y%32<2 else 0)
                if name in ('bronze','robe'):shade+=8*math.sin(x*.13+y*.018)+3*math.sin(y*.3)
                if name=='plaster':shade+=7*math.sin(x*.13)*math.sin(y*.095)
                pixels[x,y]=tuple(max(0,min(255,round(c+shade))) for c in base)
        d=ImageDraw.Draw(tile)
        gold=(175,142,89);cream=(186,176,135);red=(155,54,37);teal=(51,108,89);blue=(52,72,104);dark=(29,34,33)
        if name in ('coffer','lotus'):
            d.rectangle((3,3,124,124),outline=gold,width=2);d.rectangle((7,7,120,120),outline=dark,width=3)
            d.rectangle((11,11,116,116),outline=red,width=2)
            for radius,c in ((52,red),(48,dark),(45,gold),(42,teal)):
                d.ellipse((64-radius,64-radius,64+radius,64+radius),fill=c)
            for i in range(12):
                a=i*math.tau/12
                points=[]
                for r,angle in ((14,a-.14),(30,a-.25),(42,a),(30,a+.25),(14,a+.14)):
                    points.append((64+r*math.cos(angle),64+r*math.sin(angle)))
                d.polygon(points,fill=red,outline=gold)
            d.ellipse((50,50,78,78),fill=dark,outline=gold,width=2)
            d.polygon([(64,54),(70,64),(64,74),(58,64)],fill=gold)
            for x,y in ((20,20),(108,20),(20,108),(108,108)):
                d.ellipse((x-6,y-6,x+6,y+6),outline=cream,width=1)
        if name in ('blue','green','scroll'):
            for y in (5,10,117,122):d.line((0,y,127,y),fill=gold if y%2 else cream,width=2)
            for cx in (0,64,128):
                for radius,c in ((28,gold),(24,dark),(20,teal),(15,red),(8,gold)):
                    points=[(cx+math.cos(a)*radius,64+math.sin(a)*radius*.95) for a in [i*math.tau/8 for i in range(8)]]
                    d.polygon(points,fill=c)
                for sign in (-1,1):
                    for off in (0,8):
                        pts=[(cx+sign*(14+i*2),64+20*math.sin(i*.2)+off) for i in range(20)]
                        d.line(pts,fill=cream if off else gold,width=2)
        if name=='cloth':
            for x in range(0,128,16):d.line((x,0,x,128),fill=(119,45,30),width=2)
            for y in (4,9,116,123):d.line((0,y,128,y),fill=gold,width=2)
        if name=='robe':
            for y in range(0,128,24):
                for x in range(0,128,24):d.arc((x,y,x+20,y+20),10,300,fill=gold,width=1)
        if name in ('coffer','blue','scroll','lotus'):
            q={'coffer':0,'blue':1,'scroll':2,'lotus':3}[name]
            tile=ornament.crop((q%2*128,q//2*128,q%2*128+128,q//2*128+128))
        # 64px edge extrusion around each 128px tile prevents neighbour colours
        # bleeding into distant beams and statues through the mip pyramid.
        padded=Image.fromarray(np.pad(np.asarray(tile),((64,64),(64,64),(0,0)),mode='edge'))
        atlas.paste(padded,(index%4*256,index//4*256))
    atlas.save(OUT/'architecture.png')

if __name__=='__main__':paint()
