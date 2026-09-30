"""Native pixel checks for quiet refractive rain; called by temple_storm_smoke."""
from pathlib import Path
import copy
import numpy as np
from PIL import Image
import pyray as pr
import g_effects
import g_graphics as graphics
import g_render_order as order
import g_surfaces
import g_water
import g_weather
from night_lighting_smoke import pixels,assert_camera_locked


def check(game,assets):
    from moonlit_water_temple import review_arena
    from test_puzzles import make_arena
    storm=g_weather.update(g_weather.start_storm(review_arena(game,make_arena())),5.)
    rain=copy.deepcopy(storm['rain_profile'])
    tm=game.make_tile_map(15,15,16,16)
    for i,tile in enumerate(tm['tiles']):tile.update(water=True,lake_bed=True,rain_exposure=float(i%15<8))
    arena=dict(tile_map=tm,player_info=game.make_default_player(20.,20.,0.),entities={'lake_props':{}},
        lake_profile=dict(enabled=True,ripple_strength=0.,ripple_density=0.,ripple_speed=0.,reflection_strength=1.,rain_distortion=3.),
        weather_profile={'enabled':True},rain_profile=rain)
    local={'shaders':{'rain_composite':assets['shaders']['rain_composite']}}
    target=pr.load_render_texture(240,240);light=pr.load_render_texture(240,240)
    yy,xx=np.mgrid[:56,:208];colors=np.array(((190,105,45,255),(70,90,130,255),(32,41,64,255)),dtype=np.uint8)
    texture=g_surfaces.upload_image(Image.fromarray(colors[(xx//2+yy//2)%3]));local['test']={'panel':texture}
    item=order.make_world_render_item('test','test','panel',0,dict(render_anchor_offset={'x':-104.,'y':-56.}),
        {'x':120.,'y':96.},208,56,order.make_texture_reference('test','panel'),dict(x=0,y=0,width=208,height=56))
    camera=pr.Vector2(0,0);out=Path('artifacts/temple-storm');out.mkdir(parents=True,exist_ok=True)
    try:
        pr.begin_texture_mode(light);pr.clear_background(pr.WHITE);pr.end_texture_mode()
        g_water.prepare(local,arena,0.,'play');g_weather.prepare(local,arena)
        def lake(pan=camera,now=31.2,reflection=True):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLACK);pr.end_texture_mode()
            g_water.draw(target,None,local,arena,[item],pan,now,False)
            if reflection:
                graphics.draw_sorted_world_render_items([item],target,pan,local,{})
                g_water.draw(target,None,local,arena,[item],pan,now,True)
            return pixels(target)
        rain['enabled']=False;dry=lake()
        rain['enabled']=True;wet=lake()
        arena['lake_profile']['rain_distortion']=1.;subtle=lake();arena['lake_profile']['rain_distortion']=3.
        area=(slice(104,150),slice(16,120))
        assert np.count_nonzero(np.any(wet[area]!=dry[area],axis=2))>np.count_nonzero(np.any(subtle[area]!=dry[area],axis=2))*1.3,'stronger rain is not disturbing more reflection texels'
        assert np.array_equal(dry[:,128:],wet[:,128:]),'rain changes sheltered water'
        assert np.count_nonzero(np.any(dry[104:150,16:120]!=wet[104:150,16:120],axis=2))>8,'no refractive lake impacts'
        palette={tuple(c[:3]) for c in colors}|{g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR}
        assert {tuple(c) for c in wet[:,:,:3].reshape(-1,3)}<=palette,'rain interpolates reflected colours'
        # Stronger rain still copies exact texels within a bounded neighbourhood.
        wet_patch=wet[104:150,16:120]
        nearby=np.zeros(wet_patch.shape[:2],dtype=bool)
        for dy in range(-3,4):
            for dx in range(-3,4):nearby|=np.all(wet_patch==dry[104+dy:150+dy,16+dx:120+dx],axis=2)
        assert nearby.all(),'rain displacement exceeds authored three-pixel limit'
        assert_camera_locked(target,lambda pan:lake(pan),'rain dimples')
        plain=lake(reflection=False);glints=np.all(plain[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
        assert 0<glints[:,:128].mean()<.0015,'lake rain paints dense splash symbols'
        assert not (glints[:-1]&glints[1:]).any(),'rain contacts form multi-row splash outlines'
        Image.fromarray(np.concatenate((dry,wet),axis=1)).save(out/'rain-refraction-pixels.png')
        frames=[Image.fromarray(lake(now=31.+i/24.)) for i in range(48)]
        frames[0].save(out/'rain-dimples.gif',save_all=True,append_images=frames[1:],duration=42,loop=0)
        exposure=graphics.ensure_rain_exposure_texture(local,tm)
        def refract():
            graphics.apply_rain_composite(target,light,exposure,rain,local,camera,tm,31.2)
            return pixels(target)
        pr.begin_texture_mode(target);pr.clear_background(pr.Color(24,32,48,255));pr.end_texture_mode()
        flat=pixels(target)
        assert np.array_equal(flat,refract()),'rain adds visible streak colours to a flat surface'
        # On detailed scenery the original rain compositor copies exact vertical
        # neighbours, with no X displacement or changes under covered tiles.
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
        for y in range(240):pr.draw_line(0,y,239,y,pr.Color(y,255-y,(y*17)%256,255))
        pr.end_texture_mode();before=pixels(target);after=refract()
        assert np.array_equal(before[:,128:],after[:,128:]),'rain refracts shelter'
        assert np.any(before!=after),'legacy scene refraction disabled'
        changed=np.any(before[:,:128]!=after[:,:128],axis=2).mean()
        assert changed>.008,('exposed rain tiles too quiet',changed)
        choices=np.zeros((238,240),dtype=bool)
        for dy in (-1,0,1):choices|=np.all(after[1:239]==before[1+dy:239+dy],axis=2)
        assert choices.all(),'rain compositor changes palette or displaces more than one pixel'
        # Ground contacts use exposure on grass/dirt too, not only wood.
        for i,tile in enumerate(tm['tiles']):tile.update(water=False,surface_material='grass' if i//15<7 else 'dirt')
        tm['surface_revision']=tm.get('surface_revision',0)+1;g_weather.prepare(local,arena)
        pr.begin_texture_mode(target);pr.clear_background(pr.Color(24,32,48,255));pr.end_texture_mode()
        ground=pixels(target)
        g_weather.draw(target,light,local,arena,camera,31.2,'ground');contacts=pixels(target)
        changed=np.any(ground!=contacts,axis=2)
        assert changed[:112,:128].any() and changed[112:,:128].any(),'rain tile contacts missing on grass or dirt'
        assert not changed[:,128:].any(),'ground rain contacts enter shelter'
        # Runoff is local to the roof, follows its cutaway, and keeps its landing
        # contacts outside shelter. No CPU particle buffers are involved.
        arena['entities']['lake_props']['roof']=dict(kind='roof',width=72,height=38,asset='roof',
            position={'x':120.,'y':96.},anchor_y=-70,roof_runoff=True)
        g_water.prepare(local,arena,0.,'play');g_weather.prepare(local,arena)
        def runoff(pan=camera):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLANK);pr.end_texture_mode()
            g_weather.draw_runoff(target,light,local,arena,[],pan,31.2)
        runoff();edge=pixels(target)
        assert edge[50:99,80:160,3].any(),'roof edge has no runoff'
        assert not edge[:,:75,3].any() and not edge[:,165:,3].any(),'runoff leaks away from roof'
        assert_camera_locked(target,runoff,'roof runoff')
        local['water_runtime']['cutaways']['roof']=0.;runoff();cutaway=pixels(target)
        assert not cutaway[:97,:,3].any(),'roof runoff floats in the cutaway room'
        assert not cutaway[:,128:,3].any(),'roof runoff contacts inside shelter'
        Image.fromarray(edge).save(out/'eave-runoff-pixels.png')
        # Raised timber and lake share an awning but receive rain at different
        # projected heights. Hidden-roof contacts isolate the landing points.
        for i,tile in enumerate(tm['tiles']):
            tile.update(surface_elevation=16. if i%15<7 else 0.,water=i%15>=7,
                        rain_exposure=float(i%15<9))
        tm['surface_revision']+=1
        arena['entities']['lake_props']['roof']['runoff_elevation']=16.
        g_weather.prepare(local,arena)
        landings=np.zeros((240,240),dtype=bool);falls=landings.copy()
        for i in range(36):
            now=31.+i/24.
            for opacity,combined in ((0.,landings),(1.,falls)):
                local['water_runtime']['cutaways']['roof']=opacity
                pr.begin_texture_mode(target);pr.clear_background(pr.BLANK);pr.end_texture_mode()
                g_weather.draw_runoff(target,light,local,arena,[],camera,now)
                combined|=pixels(target)[:,:,3]>0
        assert landings[98:100,84:112].any(),'timber has no deck-height runoff contacts'
        assert landings[114:116,112:144].any(),'lake has no lower runoff contacts'
        assert not landings[:114,112:144].any(),'lake runoff collides in mid-air at deck height'
        assert not landings[100:,84:112].any(),'runoff falls through the timber deck'
        assert falls[100:114,112:144].any(),'drops never continue down toward the lake'
        assert not landings[:,144:].any(),'lower lake landing ignores rain shelter'
        print('Rain GPU pixels: denser exposed-tile refraction, stronger palette-preserving reflection warp, shelter, camera alignment and roof runoff passed.')
    finally:
        g_water.unload(local);g_weather.unload(local);graphics.clear_rain_runtime_assets(local)
        pr.unload_texture(texture);pr.unload_render_texture(target);pr.unload_render_texture(light)
