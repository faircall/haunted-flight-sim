"""Serializable storm progression plus bounded, world-registered lake effects.

Weather state is saved with sequence progress. GPU resources live in assets;
rain impact/puddle/firefly patterns are evaluated on the GPU, not CPU particles.
"""
import copy
from pathlib import Path
from PIL import Image
import pyray as pr
import g_effects
import g_surfaces

ROOT=Path(__file__).resolve().parent
RUNTIME_GENERATION=globals().get('RUNTIME_GENERATION',0)+1


def enabled(arena):
    return bool(arena.get('weather_profile',{}).get('enabled',False) and arena.get('lake_profile',{}).get('enabled',False))


def start_storm(arena,event=None):
    if not enabled(arena):return arena
    state=arena['sequence_state'].setdefault('weather',{})
    if state.get('started'):return arena
    state.update(started=True,elapsed=0.,wetness=0.,flash=0.,strike=0,next_strike=2.8,last_strike=-100.,
                 baseline={key:copy.deepcopy(arena.get(key,{})) for key in ('lighting_profile','wind_profile','rain_profile','lake_profile')})
    arena['sequence_state']['facts']['temple_entered']=True
    return arena


def flash_at(age):
    # Two brief, irregular-looking pulses, then a soft tail; no white screen overlay.
    if not 0.<=age<.42:return 0.
    if age<.07:return 1.-age/.1
    if age<.16:return .10
    if age<.23:return .75*(1.-(age-.16)/.10)
    return .24*(1.-(age-.23)/.19)


def update(arena,dt):
    if not enabled(arena):return arena
    state=arena['sequence_state'].get('weather',{})
    if not state.get('started'):return arena
    settings=arena['weather_profile'];dt=max(0.,float(dt));state['elapsed']+=dt
    elapsed=state['elapsed'];amount=min(1.,elapsed/max(.01,settings.get('onset_seconds',1.4)))
    amount=amount*amount*(3.-2.*amount)
    state['wetness']=min(1.,state['wetness']+dt*settings.get('wetting_rate',.026)*amount)
    while elapsed>=state['next_strike']:
        state['last_strike']=state['next_strike'];state['strike']+=1
        state.setdefault('thunder_due',[]).append(state['last_strike']+.7+g_surfaces.noise(state['strike'],8,733)*1.2)
        wait=6.+g_surfaces.noise(state['strike'],17,settings.get('seed',733))*8.
        state['next_strike']+=wait
    due=state.setdefault('thunder_due',[])
    for when in due:
        if when<=elapsed:
            arena['sequence_runtime']['sounds'].append(dict(type='weather_thunder',source_id='temple:storm',
                source_kind='weather',priority=1.5,gain=.9,pitch=.94+g_surfaces.noise(int(when*100),9,733)*.12))
    due[:]=[when for when in due if when>elapsed]
    flash=flash_at(elapsed-state['last_strike']);state['flash']=flash
    base=state['baseline']
    light=copy.deepcopy(base['lighting_profile']);moon=light.setdefault('moonlight',{})
    initial=base['lighting_profile'].get('moonlight',{})
    target=settings.get('moon_color',[.14,.32,.83])
    moon['color']=[initial.get('color',[.29,.55,.87])[i]*(1.-amount)+target[i]*amount for i in range(3)]
    moon['intensity']=initial.get('intensity',.3)*(1.-amount)+settings.get('moon_intensity',.13)*amount+flash*1.25
    # A little scattered sky light catches trees/architecture, while indoor
    # warmth survives. The directional flash still respects the moon shadow map.
    light['ambient_strength']=base['lighting_profile'].get('ambient_strength',.32)*(1.-.30*amount)+flash*.16
    light['ambient_color']=[a*(1.-amount)+b*amount for a,b in zip(base['lighting_profile'].get('ambient_color',[.16,.25,.36]),[.10,.18,.36])]
    wind=copy.deepcopy(base['wind_profile']) or g_effects.make_wind_profile()
    wind['strength']=wind.get('strength',8.)*(1.-amount)+settings.get('wind_strength',36.)*amount
    wind['gust_strength']=wind.get('gust_strength',5.)*(1.-amount)+settings.get('gust_strength',26.)*amount
    wind['tree_motion_gain']=1.+(settings.get('tree_motion_gain',1.65)-1.)*amount
    wind['gust_speed']=wind.get('gust_speed',.35)*(1.-amount)+.62*amount
    wind['vertical_flutter']=.6*amount
    rain=copy.deepcopy(base['rain_profile']) or g_effects.make_rain_profile()
    # Use the original painted rain-exposure compositor as subtle refraction.
    # No visible drop colour, and no diagonal curtain scrolling over the scene.
    rain.update(enabled=elapsed>.18,density=settings.get('rain_density',.72)*amount,speed=1.,
                direction={'x':0.,'y':1.},streak_length=4.,cell_size={'x':7.,'y':11.},unlit_opacity=0.,lit_opacity=0.,
                distortion_enabled=True,distortion_strength=1.,distortion_density=settings.get('rain_refraction_density',.75))
    lake=copy.deepcopy(base['lake_profile'])
    lake['rain_distortion']=settings.get('rain_reflection_distortion',3.)
    for key in ('surface_color','ripple_color'):
        start=base['lake_profile'].get(key,[.01,.03,.05])
        lake[key]=[min(1.,c*(1.-.22*amount)+flash*f) for c,f in zip(start,(.04,.065,.10))]
    return arena.set('lighting_profile',light).set('wind_profile',wind).set('rain_profile',rain).set('lake_profile',lake)


def terrain_image(tm):
    """RGB = exposed lake/wood/sky; A = surface elevation in native pixels."""
    pixels=[]
    for tile in tm['tiles']:
        exposure=round(255*g_effects.get_tile_rain_exposure(tile))
        water=bool(tile.get('water'))
        wood=tile.get('surface_material')=='wood' and not tile.get('facade_blocked')
        elevation=round(max(0.,min(255.,tile.get('surface_elevation',0.))))
        pixels.append((exposure if water else 0,exposure if wood and not water else 0,exposure,elevation))
    image=Image.new('RGBA',(tm['map_width'],tm['map_height']));image.putdata(pixels)
    return image


def eave_image(prop):
    """One cached texel per roof column; runoff follows the actual painted edge."""
    import g_water_temple_art as art
    image=art.image(prop['kind'],prop['width'],prop['height'],prop.get('asset'))
    alpha=image.getchannel('A');pixels=[]
    for x in range(image.width):
        column=alpha.crop((x,0,x+1,image.height)).getbbox()
        if not column:pixels.append((0,0,0,255));continue
        end=min(x,image.width-1-x)/max(1.,image.width*.14)
        pixels.append((round(column[3]/image.height*255),round((.65+.35*max(0.,1.-end))*255),0,255))
    edge=Image.new('RGBA',(image.width,1));edge.putdata(pixels)
    return edge


def prepare(assets,arena):
    if not enabled(arena):unload(assets);return
    tm=arena['tile_map'];rt=assets.get('weather_runtime')
    if rt and rt.get('generation')!=RUNTIME_GENERATION:
        unload(assets);rt=None
    stamp=(id(tm),tm.get('geometry_revision',0),tm.get('surface_revision',0),tm.get('rain_exposure_revision',0),RUNTIME_GENERATION)
    if rt is None:
        rt={'shaders':{},'generation':RUNTIME_GENERATION};assets['weather_runtime']=rt
    if rt.get('stamp')!=stamp:
        if 'terrain' in rt:pr.unload_texture(rt['terrain'])
        rt['terrain']=g_surfaces.upload_image(terrain_image(tm));rt['stamp']=stamp
    runoff=rt.setdefault('runoff',{});wanted=set()
    for name,prop in arena['entities'].get('lake_props',{}).items():
        if not prop.get('enabled',True) or not prop.get('roof_runoff',False):continue
        wanted.add(name)
        stamp=(prop['width'],prop['height'],prop.get('asset'),id(assets.get('water_runtime')))
        if name not in runoff or runoff[name]['stamp']!=stamp:
            if name in runoff:pr.unload_texture(runoff[name]['edge'])
            runoff[name]=dict(stamp=stamp,edge=g_surfaces.upload_image(eave_image(prop)))
    for name in set(runoff)-wanted:pr.unload_texture(runoff.pop(name)['edge'])


def shader(rt,name):
    if name not in rt['shaders']:
        value=pr.load_shader('',str(ROOT/'shaders'/('weather_'+name+'.fs')))
        if value.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Weather shader failed: '+name)
        names=('resolution','cameraPosition','tileSize','mapSize','time','rainAmount','wetness','flash','coverageTexture','lightTexture','fireflyDensity',
               'roofRect','eaveFloor','roofOpacity','windShift','playerRect','exposureTexture','runoffElevation')
        rt['shaders'][name]=(value,{k:pr.get_shader_location(value,k) for k in names})
    return rt['shaders'][name]


def draw(scene,lighting,assets,arena,camera,now,mode):
    rt=assets.get('weather_runtime')
    if not rt or not enabled(arena):return
    import g_graphics as graphics
    state=arena.get('sequence_state',{}).get('weather',{})
    wet=state.get('wetness',0.);rain=arena.get('rain_profile',{})
    density=rain.get('density',0.) if rain.get('enabled') else 0.
    if mode=='ground' and wet<=0. and density<=0.:return
    if mode=='fireflies' and not arena['weather_profile'].get('fireflies',True):return
    value,loc=shader(rt,'fireflies' if mode=='fireflies' else 'surface')
    tm=arena['tile_map'];width,height=scene.texture.width,scene.texture.height
    graphics.set_shader_vec2(value,loc['resolution'],width,height)
    graphics.set_shader_vec2(value,loc['cameraPosition'],round(camera.x),round(camera.y))
    graphics.set_shader_vec2(value,loc['tileSize'],tm['tile_width'],tm['tile_height'])
    graphics.set_shader_vec2(value,loc['mapSize'],tm['map_width'],tm['map_height'])
    graphics.set_shader_float(value,loc['time'],now)
    graphics.set_shader_float(value,loc['rainAmount'],density)
    graphics.set_shader_float(value,loc['wetness'],wet)
    graphics.set_shader_float(value,loc['flash'],state.get('flash',0.))
    graphics.set_shader_float(value,loc['fireflyDensity'],arena['weather_profile'].get('firefly_density',.45))
    pr.begin_texture_mode(scene);pr.begin_shader_mode(value)
    if mode=='fireflies':
        coverage=assets.get('water_runtime',{}).get('targets',{}).get('coverage')
        if coverage:graphics.set_shader_texture(value,loc['coverageTexture'],coverage.texture)
    if lighting:graphics.set_shader_texture(value,loc['lightTexture'],lighting.texture)
    # texture0 is the tiny material/exposure map. No scene readback or copy.
    pr.draw_texture_pro(rt['terrain'],pr.Rectangle(0,0,tm['map_width'],tm['map_height']),
                        pr.Rectangle(0,0,width,height),pr.Vector2(0,0),0,pr.WHITE)
    pr.end_shader_mode();pr.end_texture_mode()


def draw_runoff(scene,lighting,assets,arena,items,camera,now):
    rt=assets.get('weather_runtime',{});rain=arena.get('rain_profile',{})
    if not enabled(arena) or not rain.get('enabled') or rain.get('density',0.)<=0. or not rt.get('runoff'):return
    import g_graphics as graphics
    import g_tree_animation as wind_rig
    value,loc=shader(rt,'runoff');tm=arena['tile_map']
    graphics.set_shader_vec2(value,loc['resolution'],scene.texture.width,scene.texture.height)
    graphics.set_shader_vec2(value,loc['cameraPosition'],round(camera.x),round(camera.y))
    graphics.set_shader_vec2(value,loc['mapSize'],tm['map_width']*tm['tile_width'],tm['map_height']*tm['tile_height'])
    graphics.set_shader_float(value,loc['time'],now)
    graphics.set_shader_float(value,loc['rainAmount'],rain['density'])
    graphics.set_shader_float(value,loc['flash'],arena.get('sequence_state',{}).get('weather',{}).get('flash',0.))
    player=next((i for i in items if i.get('source')=='player'),None)
    water=assets.get('water_runtime',{})
    for name,cached in rt['runoff'].items():
        prop=arena['entities']['lake_props'].get(name)
        if not prop:continue
        w,h=prop['width'],prop['height'];base=prop['position']
        x=round(base['x']-w/2);y=round(base['y']+prop.get('anchor_y',-h));floor=round(base['y']+3)
        elevation=max(0.,min(255.,prop.get('runoff_elevation',0.)))
        progress=water.get('cutaways',{}).get(name,1.);opacity=progress*progress*(3.-2.*progress)
        wind=wind_rig.irregular_wind(arena.get('wind_profile',{}),(base['x'],base['y']),now)
        graphics.set_shader_vec4(value,loc['roofRect'],x,y,w,h)
        graphics.set_shader_float(value,loc['eaveFloor'],floor)
        graphics.set_shader_float(value,loc['runoffElevation'],elevation)
        graphics.set_shader_float(value,loc['roofOpacity'],opacity)
        graphics.set_shader_float(value,loc['windShift'],max(-3.,min(3.,wind['x']*.08)))
        b=player['bounds_world'] if player and player.get('sort_y',0.)>=base['y'] else dict(x=-10000.,y=-10000.,width=0.,height=0.)
        graphics.set_shader_vec4(value,loc['playerRect'],b['x'],b['y'],b['width'],b['height'])
        pr.begin_texture_mode(scene);pr.begin_shader_mode(value)
        graphics.set_shader_texture(value,loc['exposureTexture'],rt['terrain'])
        if lighting:graphics.set_shader_texture(value,loc['lightTexture'],lighting.texture)
        coverage=water.get('targets',{}).get('coverage')
        if coverage:graphics.set_shader_texture(value,loc['coverageTexture'],coverage.texture)
        pr.draw_texture_pro(cached['edge'],pr.Rectangle(0,0,w,1),
            pr.Rectangle(x-4-round(camera.x),y-round(camera.y),w+8,floor+elevation-y+4),pr.Vector2(0,0),0,pr.WHITE)
        pr.end_shader_mode();pr.end_texture_mode()


def unload(assets):
    rt=assets.pop('weather_runtime',{})
    if 'terrain' in rt:pr.unload_texture(rt['terrain'])
    for record in rt.get('runoff',{}).values():pr.unload_texture(record['edge'])
    for value,_ in rt.get('shaders',{}).values():pr.unload_shader(value)
