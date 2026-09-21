import unittest
from PIL import Image
import g_tree_assets as packs
import g_update_and_render as game
import g_render_order as render

class TreeAssetTests(unittest.TestCase):
 def test_packs_reconstruct_and_masks_align(self):
  for kind in packs.VARIANTS:
   spec=packs.definition(kind);folder=spec['directory']
   reference=Image.open(folder/'willow_tree_reference.png').convert('RGBA')
   composite=Image.open(folder/'willow_tree_trunk.png').convert('RGBA')
   self.assertEqual(reference.size,(128,128));self.assertEqual(reference.getpixel((0,0))[3],0)
   for part in spec['parts']:
    layer=Image.open(folder/f"willow_tree_{part['name']}.png").convert('RGBA')
    mask=Image.open(folder/f"willow_tree_{part['name']}_wood_mask.png").convert("L")
    self.assertEqual(mask.size,reference.size)
    left,top,right,bottom=part['bounds'];x,y=part['pivot'];box=layer.getbbox()
    self.assertTrue(left<=x<right and top<=y<bottom)
    self.assertTrue(left<=box[0] and top<=box[1] and right>=box[2] and bottom>=box[3])
    composite.alpha_composite(layer)
   self.assertEqual(reference.tobytes(),composite.tobytes())
   maps=[Image.open(folder/f'willow_tree_trunk_response_{d}.png').tobytes() for d in ('down','up','left','right')]
   self.assertEqual(len(set(maps)),4)
 def test_placement_and_reference_roots(self):
  for kind in packs.VARIANTS:
   self.assertIn(kind,game.load_entity_types());self.assertEqual(game.categorise_entity_type(kind),'brains')
   entity=dict(type=kind,id=1,position=dict(x=200.,y=200.));game.give_entity_stats_from_type(entity,kind)
   root=packs.definition(kind)['root']
   self.assertEqual(entity['render_anchor_offset'],dict(x=-root[0]-16.,y=-root[1]-16.))
   ghost=render.build_brain_render_item(1,entity,dict(tile_width=16,tile_height=16),{})
   self.assertEqual(ghost['texture']['name'],packs.reference_name(kind))
   self.assertEqual(ghost['dest_rect']['x']+root[0],200.)

if __name__=='__main__':unittest.main()
