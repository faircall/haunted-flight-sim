"""Opt-in lake rendering and replaceable water-temple props.

Water stays a ground mask, independently of movement collision. Reflections
project actual lit sprites about their ground anchors, then ripple on the GPU.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter
import pyray as pr
import g_effects
import g_surfaces
import g_render_order as order
import g_water_temple_art as art

ROOT=Path(__file__).resolve().parent
RUNTIME_GENERATION=globals().get('RUNTIME_GENERATION',0)+1
DEFAULT_SURFACE_COLOR=(2,7,13)
DEFAULT_RIPPLE_COLOR=(10,22,33)


def enabled(arena):return bool(arena.get('lake_profile',{}).get('enabled',False))


def camera_focus(arena,position):
    if not enabled(arena):return position
    point=g_effects.position_to_world(position,arena['tile_map'])
    offset=arena['lake_profile'].get('camera_offset',{})
    return dict(x=point['x']+offset.get('x',0),y=point['y']+offset.get('y',0))


def water_mask(tm):
    w,h=tm['map_width'],tm['map_height'];tw,th=tm['tile_width'],tm['tile_height']
    mask=Image.new('L',(w,h));mask.putdata([255 if tile.get('lake_bed',tile.get('water',False)) else 0 for tile in tm['tiles']])
    mask=mask.resize((w*tw,h*th),Image.Resampling.NEAREST).filter(ImageFilter.GaussianBlur(5)).point(lambda value:255 if value>=128 else 0)
    draw=ImageDraw.Draw(mask)
    for i,tile in enumerate(tm['tiles']):
        if not tile.get('water') and tile.get('surface_material') in ('wood','wall'):
            x,y=i%w*tw,i//w*th;draw.rectangle((x,y,x+tw-1,y+th-1),fill=0)
    return mask


def prepare(assets,arena,dt,mode):
    if not enabled(arena):unload(assets);return
    tm=arena['tile_map'];rt=assets.get('water_runtime')
    stamp=(id(tm),tm.get('geometry_revision',0),tm.get('water_revision',0),RUNTIME_GENERATION,art.RUNTIME_GENERATION)
    if rt is None or rt['stamp']!=stamp:
        previous=rt.get('cutaways',{}) if rt and rt.get('map') is tm else {}
        unload(assets)
        rt=dict(stamp=stamp,map=tm,cutaways=previous,props={},targets={},shaders={},mode=mode)
        assets['water_runtime']=rt;assets['water_prop_textures']={}
        rt['mask']=g_surfaces.upload_image(water_mask(tm).convert('RGBA'))
    wanted=set()
    feet=g_effects.position_to_world(arena['player_info']['position'],tm)
    offset=arena['player_info'].get('render_base_offset',{'y':14.})
    feet={axis:feet[axis]+offset.get(axis,0.) for axis in ('x','y')}
    for name,prop in arena['entities'].get('lake_props',{}).items():
        if not prop.get('enabled',True):continue
        wanted.add(name);signature=(prop['kind'],prop['width'],prop['height'])
        if rt['props'].get(name)!=signature:
            if name in assets['water_prop_textures']:pr.unload_texture(assets['water_prop_textures'][name])
            assets['water_prop_textures'][name]=g_surfaces.upload_image(art.image(*signature))
            rt['props'][name]=signature
        region=prop.get('cutaway')
        if region:
            inside=region['x']<=feet['x']<region['x']+region['width'] and region['y']<=feet['y']<region['y']+region['height']
            target=float(not inside) if mode=='play' else float(assets.get('editor_state',{}).get('roof_preview',False))
            old=rt['cutaways'].get(name,target)
            step=max(0.,dt)/.3
            rt['cutaways'][name]=target if mode!='play' or rt['mode']!=mode else max(target,old-step) if target<old else min(target,old+step)
    for name in set(rt['props'])-wanted:
        pr.unload_texture(assets['water_prop_textures'].pop(name));rt['props'].pop(name);rt['cutaways'].pop(name,None)
        rt.get('metadata',{}).pop(name,None)
    rt['mode']=mode


def render_items(assets,entities):
    if 'water_runtime' not in assets:return []
    rt=assets['water_runtime'];result=[]
    metadata=rt.setdefault('metadata',{})
    for name,prop in entities.get('lake_props',{}).items():
        if name not in assets['water_prop_textures']:continue
        progress=rt['cutaways'].get(name,1.);opacity=progress*progress*(3-2*progress)
        if opacity<=0.:continue
        w,h=prop['width'],prop['height'];base=prop['position']
        signature=(w,h,prop.get('anchor_y',-h))
        cached=metadata.get(name)
        if cached is None or cached[0]!=signature:
            entity=dict(render_anchor_offset={'x':-w/2,'y':signature[2]},visual_height=h,
                        self_shadow={'mode':'none'},shadow={'mode':'none'},occludes_render_items=True,
                        outline={'policy':'never'})
            metadata[name]=(signature,entity)
        else:entity=cached[1]
        item=order.make_world_render_item('lake_prop','lake_prop','lake:'+name,name,entity,base,w,h,
            order.make_texture_reference('water_prop_textures',name),dict(x=0,y=0,width=w,height=h))
        if prop.get('cutaway'):item['sort_y']-=.5
        if prop['kind']=='roof':item['excluded_light_owners']=['altar-left','altar-right']
        if opacity<1.:item['composite_opacity']=opacity
        result.append(item)
    return result


def _target(rt,name,w,h):
    target=rt['targets'].get(name)
    if target is None or (target.texture.width,target.texture.height)!=(w,h):
        if target:pr.unload_render_texture(target)
        target=pr.load_render_texture(w,h);rt['targets'][name]=target
        pr.set_texture_filter(target.texture,pr.TextureFilter.TEXTURE_FILTER_POINT)
    return target


def _shader(rt,name):
    if name in rt['shaders']:return rt['shaders'][name]
    vertex=str(ROOT/'shaders'/'lake_reflection.vs') if name=='reflection' else ''
    shader=pr.load_shader(vertex,str(ROOT/'shaders'/('lake_reflection.fs' if name=='reflection' else 'lake_water.fs')))
    if shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake shader failed: '+name)
    uniforms=('mirrorY','stretch','litScene','resolution') if name=='reflection' else (
        'waterMask','sceneTexture','resolution','mapSize','cameraPosition',
        'time','reflectionStrength','rippleStrength','reflectionPass',
        'surfaceColor','rippleColor','rippleSpacing','rippleDensity')
    value=(shader,{key:pr.get_shader_location(shader,key) for key in uniforms});rt['shaders'][name]=value
    return value


def _reflect_fires(rt,assets,arena,emitters,camera,wind,now,respect_preview):
    """Mirror the visible flame pixels, using the flame shader only for shape."""
    import g_graphics as graphics
    info=assets.get('shaders',{}).get('effect_fire')
    if info is None:return
    source=rt['targets']['source'];coverage=rt['targets']['coverage'];reflections=rt['targets']['reflections']
    w,h=source.texture.width,source.texture.height;full=pr.Rectangle(0,0,w,-h)
    shader,loc=_shader(rt,'reflection')
    camera=pr.Vector2(round(camera.x),round(camera.y))
    for emitter in emitters.values():
        if emitter.get('type')!='fire' or not emitter.get('enabled',True):continue
        if respect_preview and not emitter.get('preview_enabled',True):continue
        bounds=graphics._effect_screen_bounds(emitter,arena['tile_map'],camera,w,h)
        if bounds is None:continue
        mask=_target(rt,'fire_mask',w,h)
        graphics._bind_effect_uniforms(info,emitter,bounds,camera,arena['tile_map'],wind,now,3,w,h,assets)
        pr.begin_texture_mode(mask);pr.clear_background(pr.BLANK)
        pr.begin_shader_mode(info['shader']);graphics.bind_effect_occlusion_texture(info,assets)
        pr.draw_rectangle_rec(bounds['clip'],pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode()
        # Protect the visible flames wherever they overlap water.
        pr.begin_texture_mode(coverage)
        pr.draw_texture_rec(mask.texture,full,pr.Vector2(0,0),pr.WHITE)
        pr.end_texture_mode()
        if not arena['lake_profile'].get('fire_reflections_enabled',True):continue
        position=g_effects.position_to_world(emitter.get('position',{}),arena['tile_map'])
        base=position['y']+float(emitter.get('reflection_base_offset',14.))
        graphics.set_shader_float(shader,loc['mirrorY'],round(base)-round(camera.y))
        pr.begin_texture_mode(reflections);pr.rl_disable_backface_culling()
        pr.begin_shader_mode(shader);graphics.set_shader_texture(shader,loc['litScene'],source.texture)
        pr.draw_texture_rec(mask.texture,full,pr.Vector2(0,0),pr.WHITE)
        pr.end_shader_mode();pr.rl_enable_backface_culling();pr.end_texture_mode()


def draw(scene,lighting,assets,arena,items,camera,now,reflections_only=True,
         effect_emitters=None,wind_profile=None,respect_preview_enabled=False):
    if not enabled(arena) or 'water_runtime' not in assets:return
    import g_graphics as graphics
    rt=assets['water_runtime'];profile=arena['lake_profile'];tm=arena['tile_map']
    if reflections_only and not profile.get('reflections_enabled',True):return
    w,h=scene.texture.width,scene.texture.height
    source=_target(rt,'source',w,h);reflections=_target(rt,'reflections',w,h);coverage=_target(rt,'coverage',w,h)
    full=pr.Rectangle(0,0,w,-h)
    if reflections_only:
        import g_player_reveal
        pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ZERO,pr.RL_ONE,pr.RL_ZERO,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_texture_mode(source);pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
        pr.draw_texture_rec(scene.texture,full,pr.Vector2(0,0),pr.WHITE)
        pr.end_blend_mode();pr.end_texture_mode()
        pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_texture_mode(coverage);pr.clear_background(pr.BLANK);pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
        for item in items:
            tex=graphics.resolve_render_item_texture(item,assets)
            if tex is None:continue
            masked=dict(item,opacity=item.get('opacity',1.)*item.get('composite_opacity',1.))
            if '_player_reveal' in item:g_player_reveal.begin_patch(assets,item,mask=True)
            graphics._draw_render_item_main_shape(masked,tex,camera,assets)
            if '_player_reveal' in item:pr.end_shader_mode()
        pr.end_blend_mode();pr.end_texture_mode()
        shader,loc=_shader(rt,'reflection')
        graphics.set_shader_vec2(shader,loc['resolution'],w,h)
        graphics.set_shader_float(shader,loc['stretch'],profile.get('reflection_stretch',1.))
        pr.begin_texture_mode(reflections);pr.clear_background(pr.BLANK)
        # Premultiplied RGB and ordinary coverage alpha, including roof fades.
        pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
        pr.rl_disable_backface_culling()
        for item in items:
            tex=graphics.resolve_render_item_texture(item,assets)
            if tex is None:continue
            base=item.get('base_world',{}).get('y',item['sort_y'])
            graphics.set_shader_float(shader,loc['mirrorY'],round(base)-round(camera.y))
            pr.begin_shader_mode(shader);graphics.set_shader_texture(shader,loc['litScene'],source.texture)
            reflected_item=dict(item,opacity=item.get('opacity',1.)*item.get('composite_opacity',1.))
            graphics._draw_render_item_main_shape(reflected_item,tex,camera,assets);pr.end_shader_mode()
        pr.rl_enable_backface_culling();pr.end_blend_mode();pr.end_texture_mode()
        _reflect_fires(rt,assets,arena,effect_emitters or {},camera,
            wind_profile or arena.get('wind_profile') or g_effects.make_wind_profile(),now,respect_preview_enabled)
        # Store foreground coverage (including visible flames) in source alpha
        # without changing the lit RGB sampled by the reflected geometry.
        pr.rl_set_blend_factors_separate(pr.RL_ZERO,pr.RL_ONE,pr.RL_ONE,pr.RL_ZERO,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_texture_mode(source);pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
        pr.draw_texture_rec(coverage.texture,full,pr.Vector2(0,0),pr.WHITE)
        pr.end_blend_mode();pr.end_texture_mode()
    else:
        for target in (reflections,coverage):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLANK);pr.end_texture_mode()
    shader,loc=_shader(rt,'water')
    graphics.set_shader_vec2(shader,loc['resolution'],w,h)
    graphics.set_shader_vec2(shader,loc['mapSize'],tm['map_width']*tm['tile_width'],tm['map_height']*tm['tile_height'])
    graphics.set_shader_vec2(shader,loc['cameraPosition'],round(camera.x),round(camera.y))
    graphics.set_shader_vec3(shader,loc['surfaceColor'],*profile.get('surface_color',[v/255. for v in DEFAULT_SURFACE_COLOR]))
    graphics.set_shader_vec3(shader,loc['rippleColor'],*profile.get('ripple_color',[v/255. for v in DEFAULT_RIPPLE_COLOR]))
    graphics.set_shader_float(shader,loc['rippleSpacing'],max(4.,profile.get('ripple_spacing',10.)))
    graphics.set_shader_float(shader,loc['rippleDensity'],max(0.,min(1.,profile.get('ripple_density',.45))))
    graphics.set_shader_float(shader,loc['time'],now)
    graphics.set_shader_float(shader,loc['reflectionStrength'],profile.get('reflection_strength',.72))
    graphics.set_shader_float(shader,loc['rippleStrength'],profile.get('ripple_strength',1.25))
    graphics.set_shader_float(shader,loc['reflectionPass'],float(reflections_only))
    pr.begin_texture_mode(scene)
    pr.begin_shader_mode(shader)
    graphics.set_shader_texture(shader,loc['waterMask'],rt['mask'])
    graphics.set_shader_texture(shader,loc['sceneTexture'],source.texture)
    pr.draw_texture_rec(reflections.texture,full,pr.Vector2(0,0),pr.WHITE)
    pr.end_shader_mode()
    pr.end_texture_mode()


def unload(assets):
    rt=assets.pop('water_runtime',{})
    if 'mask' in rt:pr.unload_texture(rt['mask'])
    if 'palette' in rt:pr.unload_texture(rt['palette'])
    for target in rt.get('targets',{}).values():pr.unload_render_texture(target)
    for shader,_ in rt.get('shaders',{}).values():pr.unload_shader(shader)
    for texture in assets.pop('water_prop_textures',{}).values():pr.unload_texture(texture)
