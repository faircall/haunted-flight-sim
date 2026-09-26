"""Moon shelter, aperture projection and facade collision semantics."""
import copy
import pickle
import unittest
from PIL import Image, ImageDraw
import g_night as night
import g_light_visibility as light
import g_update_and_render as game
from test_puzzles import make_arena, place


def exposed_map():
    tm=game.make_tile_map(12,12,16,16)
    for t in tm['tiles']:t['rain_exposure']=1.
    return tm


class NightTests(unittest.TestCase):
    def test_moon_has_no_radial_falloff_and_respects_roof_and_wall_shadow(self):
        tm=exposed_map();tm['tiles'][3*12+2]['index']=3
        tm['tiles'][4]['rain_exposure']=0.
        grid=light.build_light_collision_grid(tm,{3})
        moon=dict(night.MOON_DEFAULTS,azimuth=0.,elevation=45.,wall_height=16.)
        image=night.moon_field(tm,grid,moon)
        self.assertEqual(image.getpixel((8,8)),255)
        self.assertEqual(image.getpixel((180,180)),255)
        self.assertEqual(image.getpixel((72,8)),0)
        self.assertEqual(image.getpixel((54,56)),0)
        self.assertEqual(image.getpixel((80,56)),255)
        turned=night.moon_field(tm,grid,dict(moon,azimuth=90.))
        self.assertEqual(turned.getpixel((54,56)),255)
        self.assertEqual(turned.getpixel((40,70)),0)

    def test_aperture_bars_and_walls_clip_the_projected_light(self):
        tm=exposed_map();bounds=dict(x=64,y=32,width=32,height=32)
        holes=Image.new('L',(32,32));draw=ImageDraw.Draw(holes)
        draw.rectangle((4,8,27,24),fill=255);draw.rectangle((14,8,17,24),fill=0)
        source=dict(position={'x':80.,'y':48.},height=40.,enabled=True)
        image,origin=night.aperture_field({},holes,bounds,source,light.build_light_collision_grid(tm,{3}))
        sample=lambda im,x,y:im.getpixel((x-origin[0],y-origin[1]))
        self.assertEqual(sample(image,80,78),0,'mullion shadow lost')
        self.assertGreater(sample(image,68,78),0)
        self.assertGreater(max(image.crop((0,18,image.width,image.height)).getdata()),0)
        for x in range(12):tm['tiles'][5*12+x]['index']=3
        blocked,_=night.aperture_field({},holes,bounds,source,light.build_light_collision_grid(tm,{3}))
        self.assertEqual(max(blocked.crop((0,18,blocked.width,blocked.height)).getdata()),0)
        dark,_=night.aperture_field({},holes,bounds,dict(source,enabled=False),light.build_light_collision_grid(tm,{3}))
        self.assertEqual(dark.getextrema(),(0,0))

    def test_light_queries_use_the_same_field_as_rendering(self):
        record=dict(type='top_down',intensity=2.,_field=dict(origin=(20,30),width=2,height=2,values=bytes((0,255,128,0))))
        self.assertEqual(light.get_gameplay_light_strength_at_world_point(record,{'x':20.,'y':30.},{}),0.)
        self.assertEqual(light.get_gameplay_light_strength_at_world_point(record,{'x':21.,'y':30.},{}),2.)
        self.assertAlmostEqual(light.get_gameplay_light_strength_at_world_point(record,{'x':20.,'y':31.},{}),256/255)
        self.assertEqual(light.get_gameplay_light_strength_at_world_point(record,{'x':19.,'y':30.},{}),0.)
        record['affects_ai']=False
        self.assertEqual(light.get_gameplay_light_strength_at_world_point(record,{'x':21.,'y':30.},{}),0.)

    def test_window_holes_preserve_collision_and_removal_restores_floor(self):
        arena=make_arena();tm=arena['tile_map'];tile=tm['tiles'][3*30+4]
        tile.update(surface_material='grass',acoustic_zone_id=2,rain_exposure=.7)
        authored=copy.deepcopy(tile)
        obj=night.make_facade({'x':72.,'y':64.});obj['width']=16
        arena['entities']['facades']={'wall':obj};night.sync_collision(arena)
        self.assertTrue(game.tile_is_collidable(tile,tm))
        grid=light.build_light_collision_grid(tm,set())
        self.assertEqual(grid['shape_codes'][3*30+4],0)
        self.assertEqual({k:tile[k] for k in authored},authored)
        arena['entities']['facades'].clear();night.sync_collision(arena)
        self.assertFalse(game.tile_is_collidable(tile,tm))
        self.assertEqual({k:tile[k] for k in authored},authored)

    def test_linked_door_uses_existing_open_state_and_survives_save(self):
        arena=make_arena();door=place(arena,'lever door',4,3)
        obj=night.make_facade({'x':72.,'y':64.},'pierced_door');obj['door_id']=str(door['id'])
        arena['entities']['facades']={'door':obj}
        night.sync_collision(arena)
        state=game.g_puzzles.object_state(arena,door);state['unlocked']=True
        game.g_puzzles.set_door_open(arena,door,True);night.sync_collision(arena)
        self.assertTrue(night.is_open(obj,arena))
        self.assertFalse(game.tile_is_collidable(arena['tile_map']['tiles'][3*30+4],arena['tile_map']))
        restored=pickle.loads(pickle.dumps(arena))
        self.assertTrue(night.is_open(restored['entities']['facades']['door'],restored))

    def test_art_windows_and_door_holes_are_binary_and_open_door_is_wider(self):
        obj=night.make_facade({'x':0.,'y':0.},'pierced_door')
        panel,closed=night.facade_art(obj)
        _,opened=night.facade_art(obj,True)
        self.assertEqual(set(closed.getdata()),{0,255})
        self.assertGreater(sum(opened.getdata()),sum(closed.getdata())*3)
        self.assertEqual(panel.size,closed.size)

    def test_lamp_behind_partition_cannot_illuminate_window(self):
        tm=exposed_map();bounds=dict(x=64,y=64,width=32,height=32)
        obj=dict(source_light='lamp')
        entities={'lights':{'lamp':dict(type='point',position={'x':80.,'y':32.},radius=160.,intensity=2.,enabled=True)}}
        source=night.source_for(obj,entities,tm,bounds,light.build_light_collision_grid(tm,{3}))
        self.assertTrue(source['enabled'])
        for x in range(12):tm['tiles'][3*12+x]['index']=3
        source=night.source_for(obj,entities,tm,bounds,light.build_light_collision_grid(tm,{3}))
        self.assertFalse(source['enabled'])

    def test_small_panels_remain_valid(self):
        for kind in night.KINDS:
            obj=night.make_facade({'x':0.,'y':0.},kind)
            obj.update(width=8,height=16)
            panel,holes=night.facade_art(obj)
            self.assertEqual(panel.size,(8,16))
            self.assertEqual(holes.size,panel.size)


if __name__=='__main__':unittest.main()
