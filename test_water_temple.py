"""Playable route, separate scene data, fire sources and independent water mask."""
import pickle
import unittest
from collections import deque
import numpy as np
from PIL import Image
import g_update_and_render as game
import g_light_visibility as visibility
import g_audio
import g_night
import g_water
from moonlit_water_temple import review_arena
from test_puzzles import make_arena


class WaterTempleTests(unittest.TestCase):
    def setUp(self):
        self.arena=review_arena(game,make_arena());self.tm=self.arena['tile_map']
        g_night.sync_collision(self.arena)

    def test_separate_builder_does_not_mutate_existing_courtyard(self):
        from night_trial import review_arena as courtyard
        old=courtyard(game,make_arena());before=pickle.dumps(old)
        new=review_arena(game,old)
        self.assertEqual(pickle.dumps(old),before)
        self.assertNotIn('lake_profile',old)
        self.assertEqual(new['scene_name'],'moonlit_water_temple')

    def test_walkable_route_reaches_the_temple_and_has_wooden_footsteps(self):
        w=self.tm['map_width'];start=(14,21);goal=(30,14);seen={start};todo=deque([start])
        while todo:
            x,y=todo.popleft()
            for p in ((x+1,y),(x-1,y),(x,y-1),(x,y+1)):
                a,b=p
                if not (0<=a<w and 0<=b<self.tm['map_height']) or p in seen:continue
                if not game.tile_is_collidable(self.tm['tiles'][b*w+a],self.tm):seen.add(p);todo.append(p)
        self.assertIn(goal,seen)
        self.assertEqual(g_audio.get_tile_audio_surface(self.tm,{'x':232.,'y':336.}),'wood')
        self.assertTrue(all(game.tile_is_collidable(tile,self.tm) for tile in self.tm['tiles'] if tile.get('water')))
        player=self.arena['player_info']
        for _ in range(240):player['position']=game.move_entity_with_velocity(player,{'x':35.,'y':0.},self.tm,None,.05)
        pos=game.make_pos_abs(player['position'],16,16)
        self.assertLess(pos['x'],512.,'player walks off boardwalk into deep lake')
        self.assertGreater(pos['x'],490.,'route blocked by invisible architecture')

    def test_deep_water_blocks_movement_but_does_not_cast_wall_shadows(self):
        grid=visibility.build_light_collision_grid(self.tm,{3})
        for i,tile in enumerate(self.tm['tiles']):
            if tile.get('water'):self.assertEqual(grid['shape_codes'][i],visibility.EMPTY_SHAPE_CODE)
        mask=g_water.water_mask(self.tm)
        self.assertEqual(mask.getpixel((232,336)),0,'water paints over the boardwalk')
        self.assertEqual(mask.getpixel((336,240)),255,'lake mask missing')
        self.assertEqual(set(mask.getdata()),{0,255},'shore edge becomes a texture fade')

    def test_cached_shore_field_measures_land_and_ignores_raised_decks(self):
        bed=Image.new('L',(80,80),255)
        self.assertTrue(np.all(g_water.shore_distance(bed)==g_water.SHORE_DISTANCE))
        bed.putpixel((40,40),0)
        distance=g_water.shore_distance(bed)
        self.assertEqual(distance[40,40],0.)
        self.assertEqual(distance[44,43],5.)
        self.assertEqual(distance[36,37],5.)
        self.assertEqual(distance[0,0],g_water.SHORE_DISTANCE)
        packed=g_water.water_map_image(self.tm)
        self.assertEqual(packed.getchannel('R').tobytes(),g_water.water_mask(self.tm).tobytes())
        self.assertEqual(packed.getpixel((336,336))[:2],(0,255),'raised boardwalk creates a false shore')
        self.assertEqual(packed.getpixel((336,318))[:2],(255,255),'lapping surrounds a raised boardwalk')
        self.assertEqual(packed.getpixel((336,336))[2],0,'water can wash over a raised deck')
        dry=np.asarray(g_water.lake_bed_mask(self.tm))==0
        field=np.asarray(packed)
        self.assertTrue(np.all(field[:,:,1][dry]<128),'signed distance is missing on the landward side')
        self.assertTrue(np.any((field[:,:,0]==0)&(field[:,:,2]==255)&(field[:,:,1]>112)),
                        'shore stencil cannot extend onto nearby natural banks')

    def test_long_lake_boundaries_share_material_curvature(self):
        for vertical in (False,True):
            tm=game.make_tile_map(12,12,16,16)
            for y in range(12):
                for x in range(12):tm['tiles'][y*12+x]['lake_bed']=(x if vertical else y)>=6
            region=np.asarray(g_water.lake_bed_mask(tm))
            if vertical:region=region.T
            positions=np.argmax(region[64:128,16:176]>0,axis=0)
            self.assertGreaterEqual(np.ptp(positions),2,'lake still has a perfectly straight long bank')
            self.assertLessEqual(max(abs(positions-32)),4)

    def test_fire_lamps_supply_the_apertures_and_survive_save(self):
        self.assertFalse(self.arena['entities']['lights'])
        emitters=self.arena['entities']['emitters']
        self.assertEqual(sum(e['type']=='fire' for e in emitters.values()),6)
        obj=self.arena['entities']['facades']['left'];bounds=g_night.facade_bounds(obj,self.tm)
        source=g_night.source_for(obj,self.arena['entities'],self.tm,bounds)
        self.assertTrue(source['enabled']);self.assertGreater(source['intensity'],0.)
        emitters['altar-left']['enabled']=False
        self.assertFalse(g_night.source_for(obj,self.arena['entities'],self.tm,bounds)['enabled'])
        restored=pickle.loads(pickle.dumps(self.arena))
        self.assertEqual(restored['lake_profile'],self.arena['lake_profile'])
        self.assertEqual(restored['entities']['lake_props'],self.arena['entities']['lake_props'])

    def test_old_scenes_keep_their_camera_and_no_water_effect(self):
        old=make_arena();point={'tile_x':3,'tile_y':2,'x':1.,'y':2.}
        self.assertFalse(g_water.enabled(old));self.assertIs(g_water.camera_focus(old,point),point)
        self.assertEqual(g_water.render_items({},old['entities']),[])


if __name__=='__main__':unittest.main()
