"""Pack the lake pavilion's painted 128px materials and exact Chinese plaque."""
from pathlib import Path
import json
import numpy as np
from g_huxin import DECK,PUZZLE_RADIUS,FUTURE_RING

ROOT=Path(__file__).parent;OUT=ROOT/'art'/'temple'/'huxin'
TILES=('wood','roof','stone','paint','earth','moss','leaf','leaflight','cap','bronze','paper','cloth','plaster','wetstone','bark','water')

def prepare():
    from PIL import Image,ImageDraw,ImageFont
    OUT.mkdir(parents=True,exist_ok=True);src=Image.open(OUT/'materials_source.png').convert('RGB');w,h=src.size
    old=Image.open(ROOT/'art'/'temple'/'bamboo'/'materials.png').convert('RGB')
    oldnames=('bamboo','node','leaf','leaflight','earth','moss','stone','plaster','wood','roof','flower','bronze','paper','cloth','cap','water')
    atlas=Image.new('RGB',(1024,1024))
    for i,name in enumerate(TILES):
        if i<4:tile=src.crop((i%2*w//2,i//2*h//2,(i%2+1)*w//2,(i//2+1)*h//2)).resize((128,128),Image.Resampling.LANCZOS)
        else:
            n=oldnames.index({'wetstone':'stone','bark':'wood'}.get(name,name));tile=old.crop((n%4*256+64,n//4*256+64,n%4*256+192,n//4*256+192))
        atlas.paste(Image.fromarray(np.pad(np.array(tile),((64,64),(64,64),(0,0)),mode='edge')),(i%4*256,i//4*256))
    atlas.save(OUT/'materials.png')
    plaque=Image.new('RGB',(1024,1024),(34,43,39));fontpath='C:/Windows/Fonts/simkai.ttf'
    for i,text in enumerate(('湖心亭','天与云与山与水','湖上无声','山水之间')):
        im=Image.new('RGB',(768,256),(32,43,40));d=ImageDraw.Draw(im);font=ImageFont.truetype(fontpath,100 if i==1 else 150)
        b=d.textbbox((0,0),text,font=font);d.text(((768-(b[2]-b[0]))/2,36),text,font=font,fill=(153,143,104))
        d.rectangle((10,10,757,245),outline=(97,92,67),width=5);plaque.paste(im.resize((512,512),Image.Resampling.LANCZOS),(i%2*512,i//2*512))
    plaque.save(OUT/'inscriptions.png')
    (OUT/'assembly_space.json').write_text(json.dumps(dict(puzzle=dict(center=[0,DECK,0],clear_radius=PUZZLE_RADIUS,implemented=False),
        surrounding_structure=dict(center=[0,0,0],inner_radius=FUTURE_RING[0],outer_radius=FUTURE_RING[1],implemented=False,
            notes='Open water reserved for a later surrounding structure. The south causeway crosses this envelope.'),
        enemies=0,temple_backdrop=False),indent=2))

if __name__=='__main__':prepare()
