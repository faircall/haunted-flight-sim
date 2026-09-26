"""A separate moonlit courtyard: python night_trial.py."""
import g_night as night
import g_surfaces as surfaces


def review_arena(game,arena):
    tm=game.make_tile_map(36,24,16,16)
    for tile in tm['tiles']:tile['rain_exposure']=1.
    surfaces.paint(tm,[(x,y) for y in range(24) for x in range(36)],'grass',density=.5)
    surfaces.paint(tm,[(x,y) for y in range(10,24) for x in range(16,22)],'dirt',density=.55)
    surfaces.paint(tm,[(x,y) for y in range(2,10) for x in range(11,27)],'wood',soft=False)
    for y in range(2,10):
        for x in range(11,27):surfaces.cell(tm,x,y)['rain_exposure']=0.
    for x,y in ([(x,2) for x in range(11,27)]+[(x,y) for x in (11,26) for y in range(2,9)]):
        surfaces.cell(tm,x,y)['index']=3
        surfaces.paint(tm,[(x,y)],'wall',soft=False)
    entities={'facades':{},'lights':{},'brains':{},'puzzles':{},'environment_examples_seeded':True}
    for name,x in (('lamp:left',224),('lamp:right',384)):
        lamp=game.g_editor.make_default_point_light({'x':float(x),'y':112.})
        lamp.update(color=[1.,.43,.11],intensity=2.1,radius=155.,height=76.,falloff=1.35)
        entities['lights'][name]=lamp
    specs=[('left','window_wall',200,48,'lamp:left'),('middle','window_wall',248,48,'lamp:left'),
           ('post','wood_wall',280,16,'builtin'),('door','pierced_door',296,16,'builtin'),
           ('wall','wood_wall',336,64,'builtin'),('right','window_wall',392,48,'lamp:right')]
    for key,kind,x,w,lamp in specs:
        obj=night.make_facade({'x':float(x),'y':160.},kind)
        obj.update(width=w,source_light=lamp,seed=x//8)
        entities['facades'][key]=obj
    for key,x,w in (('rear-left',240,128),('rear-right',360,112)):
        obj=night.make_facade({'x':float(x),'y':48.},'wood_wall')
        obj.update(width=w,height=16)
        entities['facades'][key]=obj
    door=dict(id=1,type='lever door',label='Old door',position={'tile_x':18,'tile_y':9,'x':8.,'y':8.})
    game.give_entity_stats_from_type(door,'lever door');entities['puzzles'][1]=door
    entities['facades']['door']['door_id']='1'
    tree=dict(id=3,type='willow tree',position={'x':104.,'y':210.})
    game.give_entity_stats_from_type(tree,'willow tree');entities['brains'][3]=tree
    profile=game.g_graphics.make_lighting_profile();night.moon_preset(profile)
    profile['moonlight'].update(azimuth=60.,intensity=.9)
    fog=game.g_graphics.make_fog_profile();fog.update(global_amount=.07,opacity=.32,density=.35,veil_strength=.035)
    arena=(arena.set('entities',entities).set('tile_map',tm).set('lighting_profile',profile)
           .set('fog_profile',fog).set('player_info',game.make_default_player(270,226,0)))
    arena=game.g_puzzles.ensure_arena(arena)
    game.g_puzzles.object_state(arena,door)['unlocked']=True
    return arena


def run():
    import g_main
    game=g_main.update_and_render_module;original=game.update_and_render;started=False
    def initialize(render,lighting,arena,assets,engine):
        nonlocal started
        if not started:
            arena=review_arena(game,arena).set('editor_mode','play')
            assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
            started=True
        return original(render,lighting,arena,assets,engine)
    game.update_and_render=initialize;g_main.g_main()


if __name__=='__main__':run()
