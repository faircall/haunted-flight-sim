"""Reproducible, pixel-preserving draft tree extraction; edit SPECS to refine splits."""
from pathlib import Path
import json, math
from PIL import Image, ImageDraw, ImageFilter
ROOT = Path(__file__).resolve().parent
# Clump: name, pivot, ownership ellipse centre/radii. Branch paths guide wood extraction.
SPECS = {
 'a': ((64,123), [
 ('crown',(55,9),(54,27,19,26)),('upper_left',(29,25),(32,36,13,17)),
 ('upper_right',(85,22),(89,36,18,24)),('middle',(70,37),(72,55,14,23)),
 ('left_outer',(24,51),(22,69,14,25)),('left_inner',(44,59),(44,85,17,29)),
 ('right_tip',(105,66),(108,76,14,16))],
 [([(63,120),(62,110),(67,100),(78,90),(82,81),(81,77),(72,70),(65,63),(64,54),(70,46),(67,40),(56,37),(50,31),(50,21)],7),
 ([(65,56),(55,58),(49,55),(38,55),(33,51),(27,51)],3),
 ([(73,91),(67,86),(68,79),(63,75),(57,75),(53,66),(44,62)],3),
 ([(81,78),(90,71),(98,67),(106,67)],2), ([(71,46),(75,33),(79,26),(86,27)],2),
 ([(47,33),(40,32),(36,26),(31,25)],2)], [(45,123),(60,113),(71,116),(87,124)]),
 'b': ((83,123), [
 ('upper_left',(37,17),(32,32,20,21)),('crown',(74,10),(76,33,24,31)),
 ('left_outer',(20,58),(21,80,18,31)),('left_inner',(48,34),(46,60,19,30)),
 ('right_upper',(107,29),(109,48,14,23)),('right_lower',(107,65),(109,77,14,22))],
 [([(82,120),(84,111),(91,104),(89,97),(84,92),(72,88),(65,83),(62,76),(64,70),(68,65),(66,61),(66,53),(70,45),(73,27)],7),
 ([(84,91),(91,84),(94,79),(91,74),(94,65),(89,61),(83,63),(71,66)],3),
 ([(88,63),(92,56),(96,49),(102,43),(105,32)],3),
 ([(93,65),(103,66),(108,69)],2), ([(63,76),(58,73),(50,74),(48,71),(42,67)],3),
 ([(64,69),(55,60),(53,47),(47,33),(39,28)],2)], [(52,123),(77,113),(91,117),(100,124)]),
 'c': ((82,123), [
 ('upper_left',(44,18),(44,26,13,14)),('crown',(74,10),(74,24,14,20)),
 ('upper_right',(96,24),(98,38,13,20)),('middle',(59,31),(60,47,17,24)),
 ('left_middle',(32,33),(32,45,15,20)),('left_lower',(27,72),(25,88,17,29)),
 ('right_lower',(105,63),(111,79,15,24))],
 [([(82,121),(83,111),(91,103),(93,97),(89,91),(80,89),(74,89),(67,85),(65,79),(66,73),(71,67),(76,61),(77,57),(74,53),(69,50),(67,45),(71,39),(72,31),(70,20)],6),
 ([(66,77),(62,70),(58,65),(53,63),(46,63),(42,65),(38,69),(36,74)],3),
 ([(68,49),(61,46),(54,44),(49,39),(46,35),(41,34),(37,33)],2),
 ([(70,40),(78,37),(84,33),(90,33),(94,28)],2),
 ([(76,59),(84,53),(93,52),(99,56),(102,62),(111,65)],2),
 ([(59,29),(54,23),(51,19),(46,17)],2),
 ([(58,28),(52,29),(48,29)],2), ([(46,63),(42,61),(39,61),(35,65),(32,68),(28,68)],2)], [(53,123),(76,116),(88,116),(99,124)])}

def build(letter, spec):
 root, clumps, paths, roots = spec
 folder=ROOT/'art'/'trees'/('willow_'+letter); folder.mkdir(parents=True,exist_ok=True)
 source=Image.open(ROOT/'artdev'/'unprocessed_trees'/f'willow_{letter}_128.png').convert('RGBA')
 source=source.resize((128,128),Image.Resampling.NEAREST)
 bg=source.getpixel((0,0))[:3]
 clean=Image.new('RGBA',(128,128)); px=clean.load()
 for y in range(128):
  for x in range(128):
   r,g,b,a=source.getpixel((x,y))
   if max(abs(v-w) for v,w in zip((r,g,b),bg))>12: px[x,y]=(r,g,b,255)
 skeleton=Image.new('L',(128,128)); draw=ImageDraw.Draw(skeleton)
 for points,width in paths: draw.line(points,fill=255,width=width,joint='curve')
 draw.polygon(roots,fill=255)
 wood=Image.new('L',(128,128)); wp=wood.load()
 for y in range(128):
  for x in range(128):
   r,g,b,a=px[x,y]
   if a and ((skeleton.getpixel((x,y)) and r>=g-3) or y>=114): wp[x,y]=255
 layers={n:Image.new('RGBA',(128,128)) for n in ['trunk']+[c[0] for c in clumps]}
 for y in range(128):
  for x in range(128):
   if not px[x,y][3]: continue
   if wp[x,y]: owner='trunk'
   else:
    owner=min(clumps,key=lambda c:((x-c[2][0])/c[2][2])**2+((y-c[2][1])/c[2][3])**2)[0]
   layers[owner].putpixel((x,y),px[x,y])
 # Hidden branch backing only beneath existing opaque foliage: no rest-pose change.
 bark=(100,90,60,255)
 for y in range(128):
  for x in range(128):
   if px[x,y][3] and skeleton.getpixel((x,y)) and not wp[x,y]:
    layers['trunk'].putpixel((x,y),bark)
 wood=layers['trunk'].getchannel('A')
 wood.save(folder/'willow_tree_wood_mask.png')
 clean.save(folder/'willow_tree_reference.png')
 parts=[]
 for i,(name,pivot,ellipse) in enumerate(clumps):
  box=layers[name].getbbox()
  # Bounds contain the actual attachment and every painted texel.
  bounds=[min(box[0],pivot[0]),min(box[1],pivot[1]),max(box[2],pivot[0]+1),max(box[3],pivot[1]+1)]
  parts.append(dict(name=name,pivot=pivot,bounds=bounds,stiffness=.55+i*.045,phase=.8+i*1.13,
                    exposure=.7+(i%3)*.12,lag=.2+(i%3)*.13,response=.65+(i%2)*.2,
                    flutter=.45+(i%3)*.1,bend_gain=.65+(i%3)*.15))
 for name,layer in layers.items():
  layer.save(folder/f'willow_tree_{name}.png')
  (wood if name=='trunk' else Image.new('L',(128,128))).save(folder/f'willow_tree_{name}_wood_mask.png')
 # Draft cylinder-like response from the smoothed wood silhouette, not baked color.
 blurred=wood.filter(ImageFilter.GaussianBlur(2.0))
 for direction,(lx,ly) in {'down':(0,1),'up':(0,-1),'left':(-1,0),'right':(1,0)}.items():
  response=Image.new('L',(128,128),180)
  for y in range(128):
   for x in range(128):
    gx=(blurred.getpixel((max(0,x-1),y))-blurred.getpixel((min(127,x+1),y)))/100.
    gy=(blurred.getpixel((x,max(0,y-1)))-blurred.getpixel((x,min(127,y+1))))/100.
    normal=max(1.,math.hypot(gx,gy))
    response.putpixel((x,y),round(255*max(.2,min(1.,.62+.38*(lx*gx+ly*gy)/normal))))
  response.save(folder/f'willow_tree_trunk_response_{direction}.png')
 pivots=Image.new('RGBA',(128,128)); d=ImageDraw.Draw(pivots)
 for part in parts:
  x,y=part['pivot'];d.line((x-2,y,x+2,y),fill=(255,0,255));d.line((x,y-2,x,y+2),fill=(255,0,255))
 pivots.save(folder/'willow_tree_pivots.png')
 data=dict(type='willow '+letter,root=root,parts=parts,source=f'artdev/unprocessed_trees/willow_{letter}_128.png',
           notes='Draft: wood follows hand-sketched branch paths and palette classification; lighting approximates rounded wood. Hidden backing is inferred. Refine this JSON for pivots/movement.')
 (folder/'tree.json').write_text(json.dumps(data,indent=2)+'\n')
 rebuilt=layers['trunk'].copy()
 for p in parts:rebuilt.alpha_composite(layers[p['name']])
 assert rebuilt.tobytes()==clean.tobytes(),letter
 return clean,layers,parts

if __name__=='__main__':
 sheet=Image.new('RGB',(1152,768),(37,44,52));d=ImageDraw.Draw(sheet)
 for i,(letter,spec) in enumerate(SPECS.items()):
  clean,layers,parts=build(letter,spec)
  for row,im in enumerate((clean,layers['trunk'])):
   im=im.resize((384,384),Image.Resampling.NEAREST);sheet.paste(im,(384*i,384*row),im)
  d.text((384*i+8,8),'Willow '+letter.upper(),fill='white')
 out=ROOT/'artifacts'/'tree-assets';out.mkdir(parents=True,exist_ok=True);sheet.save(out/'prepared.png')
 print('Built 3 tree packs; exact rest-pose reconstruction verified.')
