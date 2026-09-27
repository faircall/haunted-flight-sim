"""Localized, pixel-tested transparency for objects hiding the player.

Coverage and transition state stay on the GPU. The colour pass fades a lit
object over the already-lit scene, so it never redraws or brightens the player.
"""
from pathlib import Path
import pyray as pr
import g_render_order as order

ROOT=Path(__file__).resolve().parent
RUNTIME_GENERATION=globals().get('RUNTIME_GENERATION',0)+1
ENABLED=True
TRANSPARENCY=.65
FADE_IN_SECONDS=.16
FADE_OUT_SECONDS=.22
MIN_COVERAGE=.04
FULL_COVERAGE=.45


def candidates(items):
    player=order.get_player_render_item(items)
    if player is None:return None,[]
    # Respect the actual painter order, including equal-depth tie breakers.
    after=items[items.index(player)+1:]
    return player,[item for item in after
                   if item.get('occludes_render_items',False) and item.get('opacity',1.)>0.
                   and order.bounds_overlap(player['bounds_world'],item['bounds_world'])]


def screen_region(player,camera):
    b=player['dest_rect']
    snap=order.moving_world_to_screen_pixel if player.get('screen_snap')=='relative_motion' else order.world_to_screen_pixel
    p=snap(b['x'],b['y'],camera)
    return (p['x'],p['y'],b['width'],b['height'])


def _target(width,height):
    target=pr.load_render_texture(width,height)
    pr.set_texture_filter(target.texture,pr.TextureFilter.TEXTURE_FILTER_POINT)
    pr.begin_texture_mode(target);pr.clear_background(pr.BLANK);pr.end_texture_mode()
    return target


def _draw_mask(target,item,texture,camera,assets):
    import g_graphics as graphics
    pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
    pr.begin_texture_mode(target);pr.clear_background(pr.BLANK)
    pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
    if texture is not None:graphics._draw_render_item_main_shape(item,texture,camera,assets)
    pr.end_blend_mode();pr.end_texture_mode()


def _runtime(assets,width,height,scene_key):
    stamp=(width,height,scene_key,RUNTIME_GENERATION)
    rt=assets.get('player_reveal_runtime')
    if rt is not None and rt['stamp']==stamp:return rt
    unload(assets)
    rt=dict(stamp=stamp,states={},shaders={},targets={})
    assets['player_reveal_runtime']=rt
    for name,uniforms in (
        ('coverage',('playerMask','previousState','resolution','playerRect','frameDelta','fadeTimes','coverageRange')),
        ('patch',('stateTexture','resolution','playerRect','transparency','maskPass','premultiplied'))):
        shader=pr.load_shader('',str(ROOT/'shaders'/f'player_reveal_{name}.fs'))
        if shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Player reveal shader failed: '+name)
        rt['shaders'][name]=(shader,{key:pr.get_shader_location(shader,key) for key in uniforms})
    for name in ('player','occluder','layer'):rt['targets'][name]=_target(width,height)
    return rt


def prepare(assets,items,scene,camera,dt,scene_key=None):
    import g_graphics as graphics
    rt=assets.get('player_reveal_runtime')
    if rt and (rt['stamp'][2]!=scene_key or not ENABLED):unload(assets)
    for item in items:item.pop('_player_reveal',None)
    player,blockers=candidates(items) if ENABLED else (None,[])
    if not blockers:
        rt=assets.get('player_reveal_runtime')
        if rt:
            for pair in rt['states'].values():
                for target in pair:pr.unload_render_texture(target)
            rt['states'].clear()
        return
    width,height=scene.texture.width,scene.texture.height
    rt=_runtime(assets,width,height,scene_key)
    region=screen_region(player,camera)
    mask=rt['targets']['player'];texture=graphics.resolve_render_item_texture(player,assets)
    _draw_mask(mask,player,texture,camera,assets)
    active=set()
    for item in blockers:
        texture=graphics.resolve_render_item_texture(item,assets)
        if texture is None:continue
        identity=item['source_id'];active.add(identity)
        if identity not in rt['states']:rt['states'][identity]=[_target(1,1),_target(1,1)]
        previous,current=rt['states'][identity]
        occluder=rt['targets']['occluder']
        _draw_mask(occluder,item,texture,camera,assets)
        shader,loc=rt['shaders']['coverage']
        graphics.set_shader_vec2(shader,loc['resolution'],width,height)
        graphics.set_shader_vec4(shader,loc['playerRect'],*region)
        graphics.set_shader_float(shader,loc['frameDelta'],max(0.,float(dt)))
        graphics.set_shader_vec2(shader,loc['fadeTimes'],FADE_IN_SECONDS,FADE_OUT_SECONDS)
        graphics.set_shader_vec2(shader,loc['coverageRange'],MIN_COVERAGE,FULL_COVERAGE)
        pr.begin_texture_mode(current);pr.begin_shader_mode(shader)
        graphics.set_shader_texture(shader,loc['playerMask'],mask.texture)
        graphics.set_shader_texture(shader,loc['previousState'],previous.texture)
        pr.draw_texture_pro(occluder.texture,pr.Rectangle(0,0,width,-height),pr.Rectangle(0,0,1,1),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode()
        rt['states'][identity]=[current,previous]
        item['_player_reveal']=dict(state=current.texture,region=region)
    for identity in set(rt['states'])-active:
        for target in rt['states'].pop(identity):pr.unload_render_texture(target)


def begin_patch(assets,item,mask=False,premultiplied=False):
    import g_graphics as graphics
    rt=assets['player_reveal_runtime'];shader,loc=rt['shaders']['patch']
    reveal=item['_player_reveal'];width,height=rt['stamp'][:2]
    graphics.set_shader_vec2(shader,loc['resolution'],width,height)
    graphics.set_shader_vec4(shader,loc['playerRect'],*reveal['region'])
    graphics.set_shader_float(shader,loc['transparency'],TRANSPARENCY)
    graphics.set_shader_float(shader,loc['maskPass'],float(mask))
    graphics.set_shader_float(shader,loc['premultiplied'],float(premultiplied))
    pr.begin_shader_mode(shader)
    graphics.set_shader_texture(shader,loc['stateTexture'],reveal['state'])


def draw_item(item,scene,camera,assets,profile,lights,readability,player):
    import g_graphics as graphics
    rt=assets['player_reveal_runtime'];layer=rt['targets']['layer']
    pr.begin_texture_mode(layer);pr.clear_background(pr.BLANK);pr.end_texture_mode()
    plain=dict(item);plain.pop('_player_reveal',None)
    result=graphics.draw_sorted_world_render_items([plain],layer,camera,assets,profile,lights,readability,player)
    pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
    pr.begin_texture_mode(scene);pr.begin_blend_mode(pr.BlendMode.BLEND_CUSTOM_SEPARATE)
    begin_patch(assets,item,premultiplied=True)
    pr.draw_texture_rec(layer.texture,pr.Rectangle(0,0,layer.texture.width,-layer.texture.height),pr.Vector2(0,0),pr.WHITE)
    pr.end_shader_mode();pr.end_blend_mode();pr.end_texture_mode()
    return result


def unload(assets):
    rt=assets.pop('player_reveal_runtime',{})
    for pair in rt.get('states',{}).values():
        for target in pair:pr.unload_render_texture(target)
    for target in rt.get('targets',{}).values():pr.unload_render_texture(target)
    for shader,_ in rt.get('shaders',{}).values():pr.unload_shader(shader)
