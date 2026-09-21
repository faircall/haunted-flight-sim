"""Run via python .tree_game_smoke.py --variants for hidden in-game validation."""
from pathlib import Path
from PIL import Image
import pyray as pr
import g_main
import g_tree_assets as packs

def run():
 game=g_main.update_and_render_module;original=game.update_and_render
 state={'frame':0};poses={};out=Path('artifacts/tree-assets');out.mkdir(parents=True,exist_ok=True)
 pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
 pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.get_frame_time=lambda:.016
 def checked(render,lighting,arena,assets,engine):
  f=state['frame']
  if f==0:
   entities={'brains':{}}
   for i,kind in enumerate(packs.VARIANTS):
    entity=dict(id=i+1,type=kind,position=dict(x=100.+i*135.,y=210.))
    game.give_entity_stats_from_type(entity,kind);entity['wind_response']=0.;entities['brains'][i+1]=entity
   lamp=game.g_editor.make_default_point_light(dict(tile_x=14,tile_y=14,x=0.,y=0.))
   lamp.update(radius=450.,intensity=1.5,casts_cinematic_shadows=True);entities['lights']={'lamp':lamp}
   arena=arena.set('entities',entities).set('tile_map',game.make_tile_map(40,30,16,16)).set('player_info',game.make_default_player(235,230,0))
  for e in arena['entities']['brains'].values():e['wind_response']=0. if f==0 else 1.
  if f==7:arena['entities']['brains'].clear()
  assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
  result=original(render,lighting,arena.set('editor_mode','play').set('time_elapsed',f*1.7),assets,engine)
  if f==7:
   assert not assets['tree_textures'];assert not assets['tree_responses'];assert not assets['tree_variants']
  else:
   for i,kind in enumerate(packs.VARIANTS):
    texture=assets['tree_textures'][str(i+1)];image=pr.load_image_from_texture(texture)
    pose=Image.frombytes('RGBA',(image.width,image.height),bytes(pr.ffi.buffer(image.data,image.width*image.height*4)));pr.unload_image(image)
    if f==0:
     expected=Image.new('RGBA',(160,160));expected.paste(Image.open(packs.definition(kind)['directory']/'willow_tree_reference.png'),(16,16))
     assert pose.getchannel('A').tobytes()==expected.getchannel('A').tobytes(),kind
     assert all(a==b for a,b in zip(pose.getdata(),expected.getdata()) if b[3]),kind
    poses.setdefault(kind,[]).append(pose)
   image=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(image)
   pr.export_image(image,str(out/f'game-review-{f}.png'));pr.unload_image(image)
  state['frame']+=1
  return result
 def safe(*args):
  try:return checked(*args)
  except Exception:
   import traceback;traceback.print_exc();raise SystemExit(1)
 game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=8
 g_main.g_main()
 for kind,frames in poses.items():assert frames[0].tobytes()!=frames[1].tobytes(),kind
 print('Three willow variants: exact calm reconstruction, animated GPU poses, real-game rendering and removal passed.')
