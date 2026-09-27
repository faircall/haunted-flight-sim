"""One light field per frame; one lighting draw per ordinary opaque sprite.

Binary-alpha scenery can be lit directly in painter order. Response-mapped trees,
layered actors and facade receivers retain their specialized lighting passes.
"""
from pathlib import Path
import pyray as pr
import g_graphics as graphics


def eligible(item):
    # These generated assets have binary alpha. Fractional-alpha source art must
    # keep the survival compositor (cutaway opacity is applied afterwards).
    return (item.get('source') == 'lake_prop'
            and item.get('self_shadow', {}).get('mode', 'none') == 'none'
            and item.get('opacity', 1.) == 1.)


def light_mask(item, lights):
    records = {r['light_id'] for r in item.get('self_shadow_summary', {}).get('per_light', ())
               if not r.get('blocked', False)}
    mask = sum(1 << i for i, light in enumerate(lights) if light.get('id') in records)
    return mask if mask < 1 << 31 else mask - (1 << 32)


def atlas(assets, lights, camera, w, h):
    frame = assets.get('entity_light_atlas_frame')
    stamp = (tuple(id(light) for light in lights), round(camera.x), round(camera.y), w, h)
    if frame is not None and frame['stamp'] == stamp:
        return frame
    active = [p for p in lights if p['light'].get('enabled', True)
              and p.get('affects_entities', p['light'].get('affects_entities', False))
              and p['light'].get('render_style', 'world') == 'world']
    rows = max(1, (len(active)+3)//4)
    target = graphics.get_or_create_render_target(assets, 'entity_light_atlas', w*4, h*rows)
    scratch = graphics.get_or_create_render_target(assets, 'entity_atlas_scratch', w, h)
    pr.begin_texture_mode(target)
    pr.clear_background(pr.BLACK)
    pr.end_texture_mode()
    for i, light in enumerate(active):
        graphics._render_single_prepared_entity_light(light, camera, scratch, assets)
        pr.begin_texture_mode(target)
        pr.draw_texture_rec(scratch.texture, pr.Rectangle(0,0,w,-h), pr.Vector2(i%4*w,i//4*h), pr.WHITE)
        pr.end_texture_mode()
    frame = dict(stamp=stamp, target=target, lights=active, rows=rows)
    assets['entity_light_atlas_frame'] = frame
    return frame


def shader(assets):
    shaders = assets['shaders']
    if 'entity_atlas' not in shaders:
        # Share tone mapping verbatim with the reference compositor. Only the
        # source fetches differ; this also keeps palette/dither edits in sync.
        source = Path('shaders/lighting_composite.fs').read_text()
        source = source.replace('uniform sampler2D lightTexture;', '''uniform sampler2D lightTexture;
uniform vec2 resolution;
uniform int atlasRows;
uniform int lightCount;
uniform int lightMask;
vec3 atlasLight() {
    vec3 total = vec3(0.0);
    for (int i = 0; i < lightCount; ++i) {
        if ((uint(lightMask) & (1u << uint(i))) == 0u) continue;
        // Render-target texel coordinates are bottom-up; atlas tiles were
        // copied in top-down painter coordinates.
        ivec2 pixel = ivec2(gl_FragCoord.xy);
        pixel += ivec2((i % 4)*int(resolution.x), (atlasRows-1-i/4)*int(resolution.y));
        total += texelFetch(lightTexture, pixel, 0).rgb;
    }
    return min(total, vec3(1.0));
}''')
        source = source.replace('texture(texture0, fragTexCoord);', 'texture(texture0, fragTexCoord) * fragColor;\n    if (sceneSample.a < 0.001) discard;')
        source = source.replace('texture(lightTexture, fragTexCoord).rgb', 'atlasLight()')
        source = source.replace('texture(readabilityLightTexture, fragTexCoord)', 'texture(readabilityLightTexture, gl_FragCoord.xy / resolution)')
        compiled = pr.load_shader_from_memory(pr.ffi.NULL, source)
        if compiled.id == pr.rl.rlGetShaderIdDefault():
            raise RuntimeError('Entity light atlas shader failed')
        names = ('resolution','atlasRows','lightCount','lightMask','lightTexture','readabilityLightTexture',
                 'ambientColor','shadowColor','ambientStrength','directLightStrength','blackPoint','shadowSoftness',
                 'shadowDetail','contrast','lightPosterizeEnabled','lightPosterizeLevels',
                 'lightDitherEnabled','lightDitherStrength','posterizeAmbient')
        shaders['entity_atlas'] = dict(shader=compiled, locations={n:pr.get_shader_location(compiled,n) for n in names})
    return shaders['entity_atlas']


def draw_plain(items, scene, camera, assets, profile, frame, readability):
    info = shader(assets); sh = info['shader']; loc = info['locations']
    graphics.set_shader_vec2(sh, loc['resolution'], scene.texture.width, scene.texture.height)
    graphics.set_shader_int(sh, loc['atlasRows'], frame['rows'])
    graphics.set_shader_int(sh, loc['lightCount'], len(frame['lights']))
    graphics.set_shader_vec3(sh, loc['ambientColor'], *graphics.normalize_light_color(profile.get('ambient_color',[.2,.2,.3])))
    graphics.set_shader_vec3(sh, loc['shadowColor'], *graphics.normalize_light_color(profile.get('shadow_color',[0,0,0])))
    for name, key, default in (('ambientStrength','ambient_strength',.3),('directLightStrength','direct_light_strength',1.),
            ('blackPoint','black_point',.1),('shadowSoftness','shadow_softness',.03),('shadowDetail','shadow_detail',0.),
            ('contrast','contrast',1.),('lightPosterizeEnabled','light_posterize_enabled',True),
            ('lightPosterizeLevels','light_posterize_levels',8.),('lightDitherEnabled','light_dither_enabled',False),
            ('lightDitherStrength','light_dither_strength',.5),('posterizeAmbient','posterize_ambient',False)):
        graphics.set_shader_float(sh,loc[name],float(profile.get(key,default)))
    pr.begin_texture_mode(scene)
    active_mask = None
    for item in items:
        texture = graphics.resolve_render_item_texture(item, assets)
        if texture is None:continue
        mask = light_mask(item,frame['lights'])
        if mask != active_mask:
            if active_mask is not None:pr.end_shader_mode()
            graphics.set_shader_int(sh,loc['lightMask'],mask)
            pr.begin_shader_mode(sh)
            graphics.set_shader_texture(sh,loc['lightTexture'],frame['target'].texture)
            graphics.set_shader_texture(sh,loc['readabilityLightTexture'],readability.texture)
            active_mask = mask
        graphics._draw_render_item_main_shape(item,texture,camera,assets)
    if active_mask is not None:pr.end_shader_mode()
    pr.end_texture_mode()


def draw_batches(items, scene, camera, assets, profile, lights, readability, player):
    existed = assets.get('entity_light_atlas_frame')
    frame = atlas(assets, lights, camera, scene.texture.width, scene.texture.height)
    result = dict(scratch_light_draws=0 if frame is existed else len(frame['lights']), survival_draws=0)
    start = 0
    while start < len(items):
        fast = eligible(items[start]); end = start+1
        while end < len(items) and eligible(items[end]) == fast:end += 1
        batch = items[start:end]
        if fast:
            draw_plain(batch,scene,camera,assets,profile,frame,readability)
            result['survival_draws'] += len(batch)
        else:
            drawn = graphics.draw_sorted_world_render_items(batch,scene,camera,assets,profile,lights,readability,player,_legacy=True)
            for key,value in drawn.items():
                result[key] = result.get(key,0)+value if key in ('scratch_light_draws','survival_draws') else value
        start = end
    return result
