"""Deterministic import of approved RetroDiffusion concepts; originals stay intact.

Chroma-key backgrounds, fit native pixels with nearest-neighbour sampling, and
keep material/emission data separate. Run once after updating source concepts.
"""
from pathlib import Path
from collections import deque
import json
import wave
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'artdev/concepts'
OUT = ROOT / 'art/temple'
SPECS = {
    'roof': ('roof/One_detached_roof_fo...-1501825482-0.png', (216,116)),
    'lantern_red': ('lanterns/Low_resolution_paint...-1357012072-0.png', (20,26)),
    'lantern_frame': ('lanterns/Low_resolution_paint...-336549837-0.png', (16,28)),
    'lantern_white': ('lanterns/One_tall_oval_Chines...-143842332-0 (1).png', (14,24)),
    'lily_flower': ('plants/Chinese_water_lillie...-1703315149-0.png', (23,19)),
    'lily_leaves': ('plants/Chinese_water_lillie...-1703315149-0 (1).png', (24,20)),
}


def cut_background(image):
    data=np.asarray(image.convert('RGBA')).copy();rgb=data[:,:,:3].astype(np.int16)
    corners=np.array([rgb[0,0],rgb[0,-1],rgb[-1,0],rgb[-1,-1]])
    background=np.median(corners,axis=0)
    if background[0]>background[1]+30 and background[2]>background[1]+20:
        # Magenta has no material role in these approved sprites. Clear enclosed
        # gaps too; a border-only flood would leave halos around suspension loops.
        keyed=(np.max(np.abs(rgb-background),axis=2)<46)
        keyed|=(rgb[:,:,0]>rgb[:,:,1]+50)&(rgb[:,:,2]>rgb[:,:,1]+30)&(np.abs(rgb[:,:,0]-rgb[:,:,2])<85)
    else:
        # White roof background: retain any isolated bright material highlights.
        possible=np.min(rgb,axis=2)>218
        keyed=np.zeros(possible.shape,dtype=bool);h,w=possible.shape
        queue=deque([(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]+
                    [(0,y) for y in range(h)]+[(w-1,y) for y in range(h)])
        while queue:
            x,y=queue.popleft()
            if not (0<=x<w and 0<=y<h) or keyed[y,x] or not possible[y,x]:continue
            keyed[y,x]=True;queue.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    data[keyed]=0
    result=Image.fromarray(data)
    bounds=result.getbbox()
    if not bounds:raise ValueError('No foreground in concept')
    return result.crop(bounds),bounds


def fit(image,size):
    scale=min(size[0]/image.width,size[1]/image.height)
    image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.NEAREST)
    out=Image.new('RGBA',size);out.paste(image,((size[0]-image.width)//2,size[1]-image.height))
    return out


def weather_audio():
    """Small seeded placeholder beds: periodic noise loops and delayed thunder.

    Audio assets are generated offline, never synthesized in the render loop.
    Replace these WAVs with recorded material later without changing gameplay.
    """
    rate=22050;rng=np.random.default_rng(733)
    def noise(seconds,cutoff):
        count=round(rate*seconds);frequencies=np.fft.rfftfreq(count,1/rate)
        spectrum=np.fft.rfft(rng.normal(size=count))
        spectrum/=np.sqrt(1.+(frequencies/cutoff)**4)
        result=np.fft.irfft(spectrum,n=count)
        return result/max(.001,np.max(np.abs(result)))
    def save(name,values):
        with wave.open(str(OUT/(name+'.wav')),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
            stream.writeframes(np.rint(values.clip(-1,1)*32767).astype('<i2').tobytes())
    save('rain_open',noise(6,4200)*.20)
    save('rain_roof',noise(6,1700)*.17)
    save('rain_muffled',noise(6,650)*.20)
    thunder=noise(5,210);t=np.arange(len(thunder))/rate
    envelope=(1.-np.exp(-t*28))*np.exp(-t*.78)*np.minimum(1.,(5.-t)*2.)
    envelope*=.73+.27*np.sin(t*7.1)**2
    save('thunder',thunder*envelope*.85)


def build():
    OUT.mkdir(parents=True,exist_ok=True);records={}
    for name,(source,size) in SPECS.items():
        with Image.open(SOURCE/source) as original:cut,bounds=cut_background(original)
        result=fit(cut,size);result.save(OUT/(name+'.png'))
        record=dict(source='artdev/concepts/'+source,crop=list(bounds),size=list(size))
        if name.startswith('lantern'):
            values=np.asarray(result);r,g,b=[values[:,:,i].astype(float) for i in range(3)]
            # Draft paper mask: leave dark ribs/caps unlit. White/amber paper
            # uses brightness; red paper uses its warm pigment.
            paper=((r>105)&(g>43)&(r>g*1.3)) if name=='lantern_red' else ((r>112)&(g>90)&(b<g*1.13))
            yy,xx=np.indices(paper.shape)
            paper&=(yy>size[1]*.16)&(yy<size[1]*.82)&(values[:,:,3]>0)
            emission=np.zeros_like(values);emission[:,:,:3]=(255,155,58);emission[:,:,3]=paper.astype('uint8')*255
            Image.fromarray(emission).save(OUT/(name+'_emission.png'))
            record['pivot']=[size[0]/2,0];record['paper_center']=[size[0]/2,size[1]*.48]
        records[name]=record
    # Native ground samples. Keep the original palette/texture, with only a
    # modest common timber tint on the much warmer vertical concept.
    for name,source in (
        ('planks_x','planks/Low_resolution_paint...-1232805536-0.png'),
        ('planks_y','planks/Matching_low_resolut...-1052733261-0.png')):
        with Image.open(SOURCE/source) as im:im=im.convert('RGB').resize((64,64),Image.Resampling.NEAREST)
        if name=='planks_y':
            p=np.asarray(im).astype(float);luma=p[:,:,0]*.3+p[:,:,1]*.59+p[:,:,2]*.11
            p=np.stack((luma*1.04+5,luma*.97+1,luma*.82),axis=2)
            im=Image.fromarray(np.rint(p).clip(0,255).astype('uint8'))
        im.save(OUT/(name+'.png'));records[name]=dict(source='artdev/concepts/'+source,size=[64,64])
    (OUT/'manifest.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
    weather_audio()
    # Inspection sheet only, not a runtime asset.
    sheet=Image.new('RGB',(864,420),(40,45,52));draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(records):
        im=Image.open(OUT/(name+'.png')).convert('RGBA')
        scale=min(3,260//im.width,170//im.height);scale=max(1,scale)
        im=im.resize((im.width*scale,im.height*scale),Image.Resampling.NEAREST)
        x=(i%3)*288;y=(i//3)*140
        draw.text((x+4,y+2),name,fill='white');sheet.paste(im,(x+4,y+20),im)
    preview=ROOT/'artifacts/temple-concepts';preview.mkdir(parents=True,exist_ok=True)
    sheet.save(preview/'prepared.png')
    print('Prepared',len(records),'temple assets in',OUT)


if __name__=='__main__':build()
