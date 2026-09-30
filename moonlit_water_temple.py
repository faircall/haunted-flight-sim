"""Independent playable lake prototype: python moonlit_water_temple.py."""
import math
import g_night
import g_surfaces
import g_effects
import g_sequences


def review_arena(game,arena):
    tm=game.make_tile_map(56,40,16,16)
    water=[];shore=[]
    for y in range(40):
        for x in range(56):
            # An irregular shoreline; all gameplay still uses ordinary cells.
            dx=(x-28)/25.;dy=(y-19)/17.
            lake=dx*dx+dy*dy < 1.+.055*math.sin(x*.65+y*.43)
            if x<12 and 18<=y<=26:lake=False
            tile=tm['tiles'][y*56+x];tile['rain_exposure']=1.
            if lake:
                tile.update(water=True,lake_bed=True,force_collidable=True)
                water.append((x,y))
            else:shore.append((x,y))
    g_surfaces.paint(tm,shore,'grass',density=.26)
    # Raised timber path, turn, forecourt and covered temple floor.
    deck=set((x,y) for x in range(11,32) for y in range(20,22))
    deck.update((x,y) for x in range(29,32) for y in range(17,22))
    deck.update((x,y) for x in range(24,36) for y in range(11,19))
    g_surfaces.paint(tm,deck,'wood',soft=False,density=.25,seed=93,plank_axis='x',style='temple')
    # The perpendicular run has its own grain. A crosswise header at the elbow
    # provides a clean construction joint rather than bending/fading the boards.
    g_surfaces.paint(tm,[(x,y) for x in range(29,32) for y in range(18,20)],'wood',soft=False,
                     density=.25,seed=93,plank_axis='y',style='temple')
    for x,y in deck:
        tile=tm['tiles'][y*56+x];tile.pop('water',None);tile.pop('force_collidable',None)
        tile['index']=4
        tile['surface_elevation']=16.
    footprint=dict(x=400,y=176,width=160,height=96)
    for y in range(11,17):
        for x in range(25,35):tm['tiles'][y*56+x].update(rain_exposure=0.,acoustic_zone_id=4)
    for x,y in ([(x,11) for x in range(25,35)]+[(x,y) for x in (25,34) for y in range(12,16)]):
        tm['tiles'][y*56+x]['index']=3
        g_surfaces.paint(tm,[(x,y)],'wall',soft=False)
    entities=dict(facades={},lights={},emitters={},brains={},puzzles={},lake_props={},environment_examples_seeded=True)
    props=entities['lake_props']
    def prop(name,kind,x,y,w,h,**extra):
        props[name]=dict(kind=kind,position=dict(x=float(x),y=float(y)),width=w,height=h,**extra)
    prop('roof','roof',480,272,216,116,anchor_y=-156,cutaway=footprint,asset='roof',roof_runoff=True,runoff_elevation=16.)
    prop('altar','altar',480,218,40,46)
    for x in (402,454,506,558):prop(f'column:{x}','column',x,272,10,58)
    for x in (414,540):prop(f'banner:{x}','banner',x,260,10,30)
    for i,(x,y,asset,w,h) in enumerate(((422,272,'lantern_red',20,26),(538,272,'lantern_white',14,24),
                                       (272,354,'lantern_frame',16,28),(406,306,'lantern_red',20,26))):
        if i>=2:prop(f'lantern-post:{i}','pile',x,y,4,54)
        prop(f'lantern:{i}','lantern',x,y,w,h,asset=asset,emission=asset+'_emission',anchor_y=-58,
             phase=i*1.7,player_reveal_enabled=False,occludes_render_items=False)
    # Sparse clusters stay clear of the boardwalk, so they do not resemble
    # walkable stepping stones. Source sprites remain at native pixel scale.
    for i,(x,y) in enumerate(((172,297),(194,285),(239,287),(365,383),(388,390),(596,315),(619,331),(578,355))):
        variant='lily_flower' if i%3==0 else 'lily_leaves'
        prop(f'lily:{i}','lily',x,y,23 if i%3==0 else 24,19 if i%3==0 else 20,
             asset=variant,anchor_y=-10,phase=i*1.3,player_reveal_enabled=False,occludes_render_items=False)
    # Walkway rails and supports, broken into short sections for correct depth.
    for x in range(192,480,32):
        for y in (320,354):prop(f'rail:{x}:{y}','rail',x+16,y,32,17)
        for y in (324,366):prop(f'pile:{x}:{y}','pile',x+2,y,5,28)
    for x in range(384,576,24):
        if 456<=x<504:continue
        prop(f'porch:{x}','rail',x+12,306,24,17)
        prop(f'porch-pile:{x}','pile',x+3,320,5,29)
    lamps=[('approach',222,326),('crossing',334,350),('landing',458,302),('landing-r',550,302),
           ('altar-left',440,223),('altar-right',520,223)]
    for i,(name,x,y) in enumerate(lamps):
        prop('bowl:'+name,'brazier',x,y+13,14,18)
        fire=g_effects.make_default_fire_emitter(dict(x=float(x),y=float(y)))
        fire.update(seed=3101+i*977,size={'x':9.,'y':17.},area_size={'x':5.,'y':2.},
                    ember_density=.055,ember_height=12.,wind_response=.18)
        fire['light'].update(radius=112. if i<4 else 122.,intensity=1.8 if i<4 else 2.5,
                             height=42.,color=[1.,.42,.105],flicker_strength=.24,flicker_speed=4.3+i*.37)
        entities['emitters'][name]=fire
    for name,x,y in (('west',332,264),('east',638,350)):
        mist=g_effects.make_default_smoke_emitter(dict(x=float(x),y=float(y)))
        mist.update(size={'x':200.,'y':18.},area_size={'x':150.,'y':5.},speed=.09,evolution_speed=.16,
                    density=.38,opacity=.16,wind_response=.16,color=[.16,.29,.39,1.],seed=int(x))
        entities['emitters']['lake-mist:'+name]=mist
    for key,kind,x,width,fire in (
        ('left','window_wall',424,48,'altar-left'),('post-left','wood_wall',456,16,'altar-left'),
        ('door','pierced_door',480,32,'altar-left'),('post-right','wood_wall',504,16,'altar-right'),
        ('right','window_wall',536,48,'altar-right')):
        panel=g_night.make_facade(dict(x=float(x),y=272.),kind)
        panel.update(width=width,source_light='fire:'+fire,seed=int(x),spill_length=110)
        if key=='door':panel.update(open=True,height=56)
        entities['facades'][key]=panel
    for name,x in (('willow:west',138),('willow:east',686)):
        tree=dict(type='willow tree',id=name,position={'x':float(x),'y':376.})
        game.give_entity_stats_from_type(tree,'willow tree');tree.update(wind_response=.6,tree_seed=x)
        entities['brains'][name]=tree
    light=game.g_graphics.make_lighting_profile();g_night.moon_preset(light)
    light.update(ambient_color=[.16,.25,.36],ambient_strength=.32,shadow_color=[.003,.006,.013],black_point=.008,contrast=1.)
    light['moonlight'].update(color=[.29,.55,.87],intensity=.3,azimuth=50.,elevation=46.)
    fog=game.g_graphics.make_fog_profile();fog.update(global_amount=.035,opacity=.20,density=.26,veil_strength=.018)
    profile=dict(enabled=True,seed=771,reflection_strength=.72,reflection_stretch=1.,ripple_strength=1.25,reflection_sway=2.,
                 surface_color=[2/255.,7/255.,13/255.],ripple_color=[10/255.,22/255.,33/255.],
                 ripple_spacing=20.,ripple_density=.28,ripple_width=1.,ripple_speed=.65,ripple_speed_variation=.28,
                 ripple_direction={'x':0.,'y':1.},shore_width=12.,shore_speed=.65,shore_lap=3.,reflections_enabled=True,
                 fire_reflections_enabled=True,camera_offset={'x':120.,'y':-76.})
    player=game.make_default_player(232.,322.,0.)
    player.update(aim_heading=0.,aim_direction={'x':1.,'y':0.})
    for key in ('puzzle_state','puzzle_runtime','sequence_state','sequence_runtime','world_sequences'):
        if key in arena:arena=arena.remove(key)
    arena=(arena.set('scene_name','moonlit_water_temple').set('tile_map',tm).set('entities',entities)
           .set('lake_profile',profile).set('player_info',player).set('lighting_profile',light).set('fog_profile',fog)
           .set('editor_mode','play'))
    arena=arena.set('wind_profile',dict(g_effects.make_wind_profile(),gust_seed=733)).set('rain_profile',g_effects.make_rain_profile())
    arena=arena.set('weather_profile',dict(enabled=True,fireflies=True,firefly_density=.45,seed=733,
        onset_seconds=1.4,moon_intensity=.13,moon_color=[.14,.32,.83],rain_density=.72,
        wind_strength=36.,gust_strength=26.,tree_motion_gain=1.65,wetting_rate=.026,
        rain_refraction_density=.75,rain_reflection_distortion=3.))
    arena=g_sequences.ensure(arena)
    trigger=g_sequences.make_trigger([(x,y) for y in range(12,16) for x in range(26,34)])
    trigger.update(label='Temple threshold — storm',on_enter='temple_storm',on_exit='none',repeat='once')
    arena['world_sequences']['triggers']['temple:storm']=trigger
    return arena


def run():
    import g_main
    game=g_main.update_and_render_module;original=game.update_and_render;started=False
    def initialize(render,lighting,arena,assets,engine):
        nonlocal started
        if not started:
            arena=review_arena(game,arena)
            assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
            camera=assets.setdefault('camera_3d',game.make_default_camera())
            camera.position.x=112.;camera.position.y=111.
            started=True
        return original(render,lighting,arena,assets,engine)
    game.update_and_render=initialize;g_main.g_main()


if __name__=='__main__':run()
