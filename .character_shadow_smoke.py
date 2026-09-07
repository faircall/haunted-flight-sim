from pathlib import Path
from PIL import Image
import math
import pyray as pr
import g_graphics as g
import g_render_order as r
import g_update_and_render as game

def main():
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.init_window(480,270,'character shadow GPU validation')
    textures={name:pr.load_texture(path) for name,path in {**game.PLAYER_CUTOUT_TEXTURE_PATHS,**game.REDHEAD_CUTOUT_TEXTURE_PATHS}.items()}
    mask=pr.load_shader('', 'shaders/character_shadow_mask.fs')
    projection=pr.load_shader('', 'shaders/cinematic_shadow_projection.fs')
    composite=pr.load_shader('', 'shaders/cinematic_shadow_composite.fs')
    assert all(s.id>0 for s in (mask,projection,composite))
    assets={'textures':textures,'sprite_sheets':{},'shaders':{
        'character_shadow_mask':{'shader':mask},
        'cinematic_shadow_projection':{'shader':projection,**{key+'_location':pr.get_shader_location(projection,name) for key,name in (('shadow_color','shadowColor'),('shadow_opacity','shadowOpacity'),('alpha_cutoff','alphaCutoff'))}},
        'cinematic_shadow_composite':{'shader':composite,'shadow_texture_location':pr.get_shader_location(composite,'shadowTexture'),'visibility_texture_location':pr.get_shader_location(composite,'visibilityTexture')}}}
    scene=pr.load_render_texture(480,270);frames=[];atlas_ids=[]
    light={'type':'point','position':{'x':240,'y':280},'height':70,'radius':600,'intensity':1.0,'falloff':1.0}
    prepared={'light':light,'world_position':{'x':240,'y':280},'casts_cinematic_shadows':True,'visibility_polygon':[{'x':-1000,'y':-1000},{'x':1000,'y':-1000},{'x':1000,'y':1000},{'x':-1000,'y':1000}]}
    out=Path('artifacts/character-shadows');out.mkdir(parents=True,exist_ok=True)
    try:
        for frame in range(24):
            items=[]
            for row,player in enumerate((False,True)):
                for col,facing in enumerate(('right','left','up','down')):
                    rootx,rooty=70+110*col,110+125*row
                    entity={'id':'player' if player else row*4+col,'type':'red head','animation_direction':facing,
                            'position':{'x':rootx if player else rootx+12,'y':rooty-14 if player else rooty+3},
                            'procedural_gait':{'phase':frame*math.tau/24,'blend':1,'run_blend':0}}
                    item=r.build_player_render_item(entity,{'tile_width':16,'tile_height':16},assets) if player else r.build_brain_render_item(col,entity,{'tile_width':16,'tile_height':16},assets)
                    item['shadow']=dict(item['shadow'],mode='upright',cast_height=32 if player else 24,max_light_distance=600,maximum_length=65,opacity=.6)
                    items.append(item)
            pr.begin_texture_mode(scene);pr.clear_background(pr.Color(109,114,102,255))
            for y in range(0,270,16):pr.draw_line(0,y,480,y,pr.Color(100,105,94,255))
            pr.end_texture_mode()
            g.draw_character_contact_shadows(scene,pr.Vector2(0,0),items)
            g.render_and_apply_cinematic_entity_shadows(scene,pr.Vector2(0,0),items,assets,prepared)
            assert len(g.build_cinematic_shadow_frame_data(items,assets,prepared)['shadows'])==8
            atlas_ids.append(assets['render_targets']['character_shadow_atlas'].id)
            pr.begin_texture_mode(scene)
            for item in items:g._draw_cutout_rig(item,pr.Vector2(0,0),assets)
            pr.end_texture_mode()
            image=pr.load_image_from_texture(scene.texture);pr.image_flip_vertical(image)
            frames.append(Image.frombytes('RGBA',(image.width,image.height),bytes(pr.ffi.buffer(image.data,image.width*image.height*4))).convert('RGB'))
            pr.unload_image(image)
        frames[0].resize((1440,810),Image.Resampling.NEAREST).save(out/'posed-shadows.png')
        frames[0].save(out/'posed-shadows.gif',save_all=True,append_images=frames[1:],duration=50,loop=0)
        atlas=assets['render_targets']['character_shadow_atlas'];image=pr.load_image_from_texture(atlas.texture);pr.image_flip_vertical(image)
        pixels=Image.frombytes('RGBA',(image.width,image.height),bytes(pr.ffi.buffer(image.data,image.width*image.height*4)))
        assert set(pixels.getchannel('A').getdata())=={0,255},'mask must be a binary union'
        pixels.save(out/'pose-atlas.png');pr.unload_image(image)
        assert len(set(atlas_ids))<=3,'atlas should reuse capacity after initial growth'
        print('8 animated casters, all facings, 24 frames; binary masks and atlas reuse passed')
    finally:
        for target in assets.get('render_targets',{}).values():pr.unload_render_texture(target)
        for texture in textures.values():pr.unload_texture(texture)
        for shader in (mask,projection,composite):pr.unload_shader(shader)
        pr.unload_render_texture(scene);pr.close_window()
if __name__=='__main__':main()
