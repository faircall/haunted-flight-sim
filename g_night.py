"""Moonlight and elevated facade apertures for the existing 2D light renderer.

Authored data lives in lighting_profile / entities.facades. Textures and light
fields are derived caches only. Apertures project from a lamp through a vertical
front-facing panel onto the ground; solid tiles beyond the opening clip the spill.
"""
from pathlib import Path
import copy
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageChops
import pyray as pr
import g_effects
import g_light_visibility as visibility
import g_surfaces

ROOT = Path(__file__).resolve().parent
RUNTIME_GENERATION = globals().get('RUNTIME_GENERATION', 0) + 1
MOON_DEFAULTS = dict(enabled=False, color=[.48, .62, 1.], intensity=.70,
                     azimuth=55., elevation=38., wall_height=48., affects_ai=True)
KINDS = ('window_wall', 'pierced_door', 'wood_wall')


def moon_preset(profile):
    profile.update(name='moonlit', ambient_color=[.24, .30, .48], ambient_strength=.28,
                   shadow_color=[.006,.010,.025], black_point=.025, shadow_softness=.035,
                   shadow_detail=.65, contrast=1.05, light_posterize_enabled=True,
                   light_posterize_levels=24., light_dither_enabled=False)
    profile['moonlight'] = dict(copy.deepcopy(MOON_DEFAULTS), enabled=True)


def make_facade(position, kind='window_wall'):
    return dict(type=kind, position=copy.deepcopy(position), width=16 if kind=='pierced_door' else 48,
                height=44 if kind=='pierced_door' else 56, enabled=True, solid=True,
                source_light='builtin', door_id='none', open=False, seed=7,
                lamp_color=[1.,.48,.14], lamp_intensity=1.8, lamp_height=72.,
                lamp_depth=28., spill_length=180., transmission=.85)


def facade_bounds(obj, tm):
    p=g_effects.position_to_world(obj['position'],tm)
    w=max(8,min(192,round(obj.get('width',48))))
    h=max(16,min(192,round(obj.get('height',56))))
    return dict(x=round(p['x']-w/2),y=round(p['y']-h),width=w,height=h)


def is_open(obj, arena):
    if obj.get('type')!='pierced_door':return False
    link=str(obj.get('door_id','none'))
    for key,door in arena.get('entities',{}).get('puzzles',{}).items():
        if link in (str(key),str(door.get('persistent_id'))):
            import g_puzzles
            return bool(g_puzzles.object_state(arena,door).get('open',False))
    return bool(obj.get('open',False))


def sync_collision(arena):
    """Derived full-cell footprints, independent of visual holes and floor finish."""
    tm=arena['tile_map']; blocked=set()
    for obj in arena.get('entities',{}).get('facades',{}).values():
        if not obj.get('enabled',True) or not obj.get('solid',True) or is_open(obj,arena):continue
        b=facade_bounds(obj,tm);y=math.floor((b['y']+b['height']-1)/tm['tile_height'])
        for x in range(math.floor(b['x']/tm['tile_width']),math.ceil((b['x']+b['width'])/tm['tile_width'])):
            if 0<=x<tm['map_width'] and 0<=y<tm['map_height']:blocked.add(y*tm['map_width']+x)
    previous=set(tm.get('_facade_blocked_tiles',()))
    if blocked!=previous:
        for index in previous|blocked:
            if 0<=index<len(tm['tiles']):tm['tiles'][index]['facade_blocked']=index in blocked
        tm['_facade_blocked_tiles']=sorted(blocked)
        for name in ('geometry_revision','acoustic_revision'):tm[name]=tm.get(name,0)+1


def facade_art(obj, opened=False):
    w=max(8,min(192,round(obj.get('width',48))));h=max(16,min(192,round(obj.get('height',56))))
    seed=int(obj.get('seed',7))
    panel=g_surfaces.base_patch('wall',seed*12,0,w,h).copy()
    holes=Image.new('L',(w,h));cut=ImageDraw.Draw(holes);draw=ImageDraw.Draw(panel)
    # Grain, frame rails, pegs: geometry is regular, wear is stable and varied.
    for x in range(4,w-3,3):
        y=4+int(g_surfaces.noise(x,seed)*max(1,h-20))
        draw.line((x,y,x,y+9),fill=(64,54,41,255))
    for y in (1,5,h-7,h-3):draw.line((1,y,w-2,y),fill=(118,94,63,255) if y%2 else (50,40,32,255),width=2)
    draw.rectangle((0,0,w-1,h-1),outline=(38,33,31,255),width=2)
    draw.line((3,2,3,h-3),fill=(139,110,71,255))
    draw.line((w-4,2,w-4,h-3),fill=(42,36,31,255),width=2)
    kind=obj.get('type')
    if kind=='window_wall':
        left=max(3,min(7,w//4));right=w-left-1
        top=max(4,min(12,h//4));bottom=h-max(4,min(17,h//3))
        draw.rectangle((left-3,top-3,right+3,bottom+3),fill=(45,34,26,255),outline=(143,112,66,255),width=2)
        cut.rectangle((left,top,right,bottom),fill=255)
        for x in range(left+6,right,8):cut.rectangle((x,top,x+1,bottom),fill=0)
        cut.rectangle((left,(top+bottom)//2,right,(top+bottom)//2+1),fill=0)
    elif kind=='pierced_door':
        if opened:
            cut.rectangle((4,3,w-3,h-3),fill=255)
            draw.rectangle((4,3,w-3,h-3),fill=(22,15,11,255))
        else:
            for x,y,hh in ((5,11,7),(w-6,20,6),(w//2,30,4)):
                cut.polygon(((x,y),(x+1,y-1),(x+2,y+hh),(x,y+hh+2)),fill=255)
            draw.rectangle((w-5,h//2,w-4,h//2+3),fill=(179,138,57,255))
    panel.paste((28,19,12,255),(0,0,w,h),holes)
    return panel,holes


def moon_field(tm, grid, moon):
    """Parallel wall shadows and sky exposure; no radial distance falloff."""
    w=tm['map_width']*tm['tile_width'];h=tm['map_height']*tm['tile_height']
    exposure=Image.new('L',(tm['map_width'],tm['map_height']))
    exposure.putdata([round(255*g_effects.get_tile_rain_exposure(t)) for t in tm['tiles']])
    exposure=exposure.resize((w,h),Image.Resampling.NEAREST)
    shade=Image.new('L',(w,h),255);draw=ImageDraw.Draw(shade)
    angle=math.radians(float(moon['azimuth']))
    distance=min(256.,float(moon['wall_height'])/max(.1,math.tan(math.radians(float(moon['elevation'])))))
    dx,dy=math.cos(angle)*distance,math.sin(angle)*distance
    for polygon in grid['receiver_polygons']:
        if not polygon:continue
        points=[(p['x'],p['y']) for p in polygon]
        for i,a in enumerate(points):
            b=points[(i+1)%len(points)]
            draw.polygon((a,b,(b[0]+dx,b[1]+dy),(a[0]+dx,a[1]+dy)),fill=0)
        draw.polygon(points,fill=0)
    return ImageChops.multiply(exposure,shade)


def source_for(obj, entities, tm, bounds, grid=None):
    identity=str(obj.get('source_light','builtin'))
    if identity=='builtin':
        return dict(position={'x':bounds['x']+bounds['width']/2,'y':bounds['y']+bounds['height']-float(obj.get('lamp_depth',28))},
                    color=obj.get('lamp_color',[1.,.48,.14]),intensity=float(obj.get('lamp_intensity',1.8)),
                    height=float(obj.get('lamp_height',72)),enabled=True)
    source=next((v for k,v in entities.get('lights',{}).items() if str(k)==identity),None)
    if source is None:return dict(enabled=False,position={'x':0.,'y':0.},height=72.,color=[1.,.48,.14],intensity=0.)
    result=dict(source);result['position']=g_effects.position_to_world(source.get('position',{}),tm)
    if source.get('type','point')!='point' or result['position']['y']>=bounds['y']+bounds['height']:
        result['enabled']=False
    inside={'x':bounds['x']+bounds['width']/2,'y':bounds['y']+bounds['height']-tm['tile_height']-.5}
    if grid is not None and not visibility.light_ray_reaches_world_point(result['position'],inside,grid):
        result['enabled']=False
    distance=math.hypot(bounds['x']+bounds['width']/2-result['position']['x'],bounds['y']+bounds['height']-result['position']['y'])
    radius=max(1.,float(source.get('radius',120.)))
    result['intensity']=float(source.get('intensity',1.))*max(0.,1-distance/radius)**float(source.get('falloff',1.6))
    return result


def aperture_field(obj, holes, bounds, source, grid):
    """Project each open pixel through the vertical panel onto a ground patch."""
    reach=max(16,min(320,int(obj.get('spill_length',180))))
    base=bounds['y']+bounds['height'];origin=(bounds['x']-reach,base)
    size=(bounds['width']+reach*2,reach+1)
    field=Image.new('L',size)
    sx,sy=source['position']['x'],source['position']['y'];height=float(source.get('height',72.))
    if not source.get('enabled',True) or sy>=base or height<=0:return field,origin
    draw=ImageDraw.Draw(field)
    for y in range(holes.height):
        for x in range(holes.width):
            if not holes.getpixel((x,y)):continue
            polygon=[]
            for u,v in ((x,y),(x+1,y),(x+1,y+1),(x,y+1)):
                altitude=holes.height-v
                if altitude>=height-.5:break
                scale=height/(height-altitude)
                polygon.append((sx+(bounds['x']+u-sx)*scale-origin[0],sy+(base-sy)*scale-origin[1]))
            if len(polygon)==4:draw.polygon(polygon,fill=255)
    # Rays begin outside the wall footprint, so openings do not require removing
    # gameplay collision. Each aperture still respects other walls in front.
    portal={'x':bounds['x']+bounds['width']/2,'y':base+.5}
    rays=visibility.build_light_visibility_polygon_dda({'type':'point','radius':reach*2.,'shadow_bias':0.,'ray_count':128},portal,grid)
    clip=Image.new('L',size)
    polygon=[(p['x']-origin[0],p['y']-origin[1]) for p in rays['unbiased_polygon']]
    if len(polygon)>=3:ImageDraw.Draw(clip).polygon(polygon,fill=255)
    values=np.asarray(ImageChops.multiply(field,clip),dtype=np.float32)
    yy,xx=np.mgrid[0:size[1],0:size[0]]
    distance=np.hypot(xx+origin[0]-sx,yy+origin[1]-sy)
    falloff=np.clip(1-distance/(reach+abs(base-sy)),0,1)**.65
    return Image.fromarray((values*falloff).round().astype('uint8')),origin


def field_record(image, origin, source, identity, assets):
    """GPU and gameplay sample the same world-aligned light field."""
    rgba=Image.merge('RGBA',(image,image,image,Image.new('L',image.size,255)))
    texture=g_surfaces.upload_image(rgba)
    light=dict(type='top_down',position=dict(source['position']),size={'x':200000.,'y':200000.},
               color=list(source['color']),intensity=max(0.,float(source['intensity'])),height=source.get('height',72.),
               enabled=True,affects_world=source.get('affects_world',True),affects_entities=source.get('affects_entities',True),
               affects_fog=source.get('affects_fog',True),affects_ai=source.get('affects_ai',True),
               casts_wall_shadows=False,casts_cinematic_shadows=False,entity_lighting_mode='directional',
               _field=dict(origin=origin,width=image.width,height=image.height,values=image.tobytes(),texture=texture))
    return {'id':identity,'light':light}


def drop_entry(entry):
    for key in ('panel','emission'):
        if key in entry:pr.unload_texture(entry[key])
    if 'record' in entry:pr.unload_texture(entry['record']['light']['_field']['texture'])


def prepare(assets, arena, grid, camera=None):
    tm=arena['tile_map'];entities=arena['entities']
    editor=assets.setdefault('editor_state',{})
    editor['night_light_ids']=['builtin']+[str(k) for k,v in entities.get('lights',{}).items() if v.get('type','point')=='point']
    editor['night_door_ids']=['none']+[str(k) for k,v in entities.get('puzzles',{}).items() if 'door' in v.get('type','')]
    rt=assets.setdefault('night_runtime',{'entries':{}})
    if rt.get('map') is not tm or rt.get('generation') != RUNTIME_GENERATION:
        for entry in rt['entries'].values():drop_entry(entry)
        rt.update(map=tm,entries={},generation=RUNTIME_GENERATION)
    wanted=set();records=[];textures={};items=[]
    geometry=(tm.get('geometry_revision',0),grid.get('runtime_generation',0))
    moon=dict(MOON_DEFAULTS,**arena.get('lighting_profile',{}).get('moonlight',{}))
    if moon['enabled']:
        key='moon';wanted.add(key)
        stamp=json.dumps((moon,geometry,tm.get('rain_exposure_revision',0)),sort_keys=True)
        entry=rt['entries'].get(key)
        if entry is None or entry['stamp']!=stamp:
            if entry:drop_entry(entry)
            image=moon_field(tm,grid,moon)
            angle=math.radians(moon['azimuth']);distance=50000.
            source=dict(position={'x':-math.cos(angle)*distance,'y':-math.sin(angle)*distance},
                        color=moon['color'],intensity=moon['intensity'],height=distance*math.tan(math.radians(moon['elevation'])),
                        affects_ai=moon['affects_ai'])
            entry={'stamp':stamp,'record':field_record(image,(0,0),source,'night:moon',assets)}
            entry['record']['light']['_moon']=True
            rt['entries'][key]=entry
        records.append(entry['record'])
    for identity,obj in entities.get('facades',{}).items():
        if not obj.get('enabled',True):continue
        bounds=facade_bounds(obj,tm)
        reach=max(16,min(320,int(obj.get('spill_length',180))))
        if camera is not None and (bounds['x']+bounds['width']+reach<camera.x or bounds['x']-reach>camera.x+480
                or bounds['y']+bounds['height']+reach<camera.y or bounds['y']>camera.y+270):continue
        key='facade:'+str(identity);wanted.add(key)
        opened=is_open(obj,arena);source=source_for(obj,entities,tm,bounds,grid)
        stamp=json.dumps((obj,bounds,opened,source,geometry),sort_keys=True)
        entry=rt['entries'].get(key)
        if entry is None or entry['stamp']!=stamp:
            if entry:drop_entry(entry)
            panel,holes=facade_art(obj,opened)
            entry=dict(stamp=stamp,panel=g_surfaces.upload_image(panel),bounds=bounds)
            rt['entries'][key]=entry
            if holes.getbbox() is None:
                textures[str(identity)]=entry['panel'];items.append((str(identity),obj,entry))
                continue
            field,origin=aperture_field(obj,holes,bounds,source,grid)
            source=dict(source,intensity=source.get('intensity',0)*float(obj.get('transmission',.85)))
            active=source.get('enabled',True) and source['intensity']>0
            emission=Image.new('RGBA',panel.size)
            pixels=emission.load()
            color=source['color']
            for y in range(holes.height):
                for x in range(holes.width):
                    if holes.getpixel((x,y)) and active:
                        strength=min(1.,source['intensity']*.95)*(.82+.18*g_surfaces.noise(x//3,y//4,5))
                        pixels[x,y]=tuple(round(255*max(0,min(1,c*strength))) for c in color)+(255,)
            entry.update(emission=g_surfaces.upload_image(emission),
                         record=field_record(field,origin,source,'night:'+str(identity),assets))
        if 'record' in entry:records.append(entry['record'])
        textures[str(identity)]=entry['panel']
        items.append((str(identity),obj,entry))
    for key in list(rt['entries']):
        if key not in wanted:drop_entry(rt['entries'].pop(key))
    assets['architectural_lights']=records;assets['facade_textures']=textures;rt['items']=items


def render_items(assets,tm):
    import g_render_order as order
    result=[]
    for identity,obj,entry in assets.get('night_runtime',{}).get('items',[]):
        b=entry['bounds'];base={'x':b['x']+b['width']/2,'y':b['y']+b['height']}
        entity=dict(render_anchor_offset={'x':-b['width']/2,'y':-b['height']},render_base_offset={'x':0,'y':0},
                    visual_height=b['height'],light_sample_height=b['height']/2,
                    self_shadow={'mode':'upright_box','strength':.65},occludes_render_items=True,
                    ground_footprint={'shape':'rectangle','size':{'x':b['width'],'y':8}},outline={'policy':'never'})
        item=order.make_world_render_item('facade','facade','facade:'+identity,identity,entity,base,b['width'],b['height'],
                     order.make_texture_reference('facade_textures',identity),{'x':0,'y':0,'width':b['width'],'height':b['height']})
        if 'emission' in entry:item['_emission']=entry['emission']
        result.append(item)
    return result


def draw_field(prepared,camera,target,assets,unmasked=False):
    import g_graphics as graphics
    light=prepared['light'];field=light['_field'];rt=assets['night_runtime']
    if 'field_shader' not in rt:
        shader=pr.load_shader('',str(ROOT/'shaders'/'field_light.fs'))
        rt['field_shader']=shader
        rt['field_locations']={n:pr.get_shader_location(shader,n) for n in ('lightColor','intensity','unmasked')}
        if min(rt['field_locations'].values())<0:raise RuntimeError('Light field shader failed')
    shader=rt['field_shader'];loc=rt['field_locations']
    graphics.set_shader_vec3(shader,loc['lightColor'],*light['color'])
    graphics.set_shader_float(shader,loc['intensity'],light['intensity'])
    entire=unmasked and light.get('_moon',False)
    graphics.set_shader_float(shader,loc['unmasked'],1. if entire else 0.)
    pr.begin_shader_mode(shader)
    if entire:pr.draw_rectangle(0,0,target.texture.width,target.texture.height,pr.WHITE)
    else:pr.draw_texture(field['texture'],round(field['origin'][0])-round(camera.x),round(field['origin'][1])-round(camera.y),pr.WHITE)
    pr.end_shader_mode()


def draw_emission(scene,items,camera,assets):
    if not any('_emission' in item for item in items):return
    import g_graphics as graphics
    rt=assets['night_runtime']
    if 'mask_shader' not in rt:
        rt['mask_shader']=pr.load_shader('',str(ROOT/'shaders'/'emission_occlusion.fs'))
        if rt['mask_shader'].id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Emission occlusion shader failed')
    target=graphics.get_or_create_render_target(assets,'facade_emission',scene.texture.width,scene.texture.height)
    pr.begin_texture_mode(target);pr.clear_background(pr.BLANK)
    for item in items:
        texture=graphics.resolve_render_item_texture(item,assets)
        if texture is None:continue
        pr.begin_shader_mode(rt['mask_shader']);graphics._draw_render_item_main_shape(item,texture,camera,assets);pr.end_shader_mode()
        if '_emission' in item:graphics._draw_render_item_main_shape(item,item['_emission'],camera,assets)
    pr.end_texture_mode()
    pr.begin_texture_mode(scene);pr.begin_blend_mode(pr.BlendMode.BLEND_ADDITIVE)
    pr.draw_texture_rec(target.texture,pr.Rectangle(0,0,target.texture.width,-target.texture.height),pr.Vector2(0,0),pr.WHITE)
    pr.end_blend_mode();pr.end_texture_mode()


def unload(assets):
    rt=assets.pop('night_runtime',{})
    for entry in rt.get('entries',{}).values():drop_entry(entry)
    for name in ('field_shader','mask_shader'):
        if name in rt:pr.unload_shader(rt[name])
    assets.pop('architectural_lights',None);assets.pop('facade_textures',None)


def inspect_moon(ui,editor,profile):
    import g_editor,g_ui
    if not g_editor.section_button(ui,editor,'moonlight','Moonlight'):return
    if g_ui.ui_button(ui,'moon:preset','Moonlit night preset'):moon_preset(profile)
    moon=profile.setdefault('moonlight',copy.deepcopy(MOON_DEFAULTS))
    moon['enabled'],_=g_ui.ui_checkbox(ui,'moon:enabled','enabled',moon.get('enabled',False))
    moon['color'],_=g_ui.ui_color3_editor(ui,'moon:color','moon colour',moon.get('color',MOON_DEFAULTS['color']))
    for name,lo,hi in (('intensity',0.,2.),('azimuth',0.,360.),('elevation',10.,85.),('wall_height',8.,128.)):
        moon[name],_=g_ui.ui_number_input_float(ui,'moon:'+name,name.replace('_',' '),moon.get(name,MOON_DEFAULTS[name]),lo,hi)
    moon['affects_ai'],_=g_ui.ui_checkbox(ui,'moon:ai','affects AI',moon.get('affects_ai',True))
    g_ui.ui_label(ui,'moon:roof','Paint rain Exposed outdoors',font_size=8)


def inspect_facade(ui,editor,identity,obj,tm):
    import g_ui,g_editor
    prefix='facade:'+str(identity)
    obj['enabled'],_=g_ui.ui_checkbox(ui,prefix+':on','enabled',obj.get('enabled',True))
    obj['position']=g_editor.edit_world_position(ui,prefix+':pos',obj['position'],tm)
    for name,lo,hi,default in (('width',8,192,48),('height',16,192,56),('seed',0,9999,7)):
        obj[name],_=g_ui.ui_number_input_int(ui,prefix+name,name,obj.get(name,default),lo,hi)
    obj['solid'],_=g_ui.ui_checkbox(ui,prefix+':solid','blocks movement',obj.get('solid',True))
    obj['source_light'],_=g_ui.ui_dropdown(ui,prefix+':source','lamp',obj.get('source_light','builtin'),editor.get('night_light_ids',['builtin']))
    if obj.get('type')=='pierced_door':
        obj['open'],_=g_ui.ui_checkbox(ui,prefix+':open','preview open',obj.get('open',False))
        obj['door_id'],_=g_ui.ui_dropdown(ui,prefix+':door','door',obj.get('door_id','none'),editor.get('night_door_ids',['none']))
    obj['lamp_color'],_=g_ui.ui_color3_editor(ui,prefix+':color','lamp colour',obj.get('lamp_color',[1.,.48,.14]))
    for name,lo,hi,default in (('lamp_intensity',0.,5.,1.8),('lamp_height',16.,160.,72.),('lamp_depth',4.,120.,28.),('spill_length',16.,320.,180.),('transmission',0.,1.,.85)):
        obj[name],_=g_ui.ui_number_input_float(ui,prefix+name,name.replace('_',' '),obj.get(name,default),lo,hi)


def hit_test(point,obj,tm):
    b=facade_bounds(obj,tm)
    return b['x']<=point['x']<=b['x']+b['width'] and b['y']<=point['y']<=b['y']+b['height']


def handles(identity,obj,camera,tm,selected):
    b=facade_bounds(obj,tm);color=pr.SKYBLUE if selected else pr.Color(180,130,80,180)
    pr.draw_rectangle_lines(b['x']-round(camera.x),b['y']-round(camera.y),b['width'],b['height'],color)
    pr.draw_circle(b['x']+b['width']//2-round(camera.x),b['y']+b['height']-round(camera.y),3,color)
