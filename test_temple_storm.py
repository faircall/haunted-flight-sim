"""Mission progression, shelter, native asset import and material continuity."""
import copy
import pickle
import unittest
from unittest import mock
from pathlib import Path
import numpy as np
from PIL import Image
import g_audio
import g_sequences
import g_surfaces
import g_weather
import g_water
import g_tree_animation as rig
import g_update_and_render as game
from moonlit_water_temple import review_arena
from test_puzzles import make_arena


class TempleStormTests(unittest.TestCase):
    def setUp(self):self.arena=review_arena(game,make_arena())

    def move(self,x,y):
        self.arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':x,'y':y},self.arena['tile_map'])

    def enter(self):
        self.arena=g_sequences.update(self.arena,.016)  # Establish outside occupancy.
        self.move(480.,240.)
        self.arena=g_sequences.update(self.arena,.016)
        return self.arena['sequence_state']['weather']

    def test_entry_once_survives_save_and_exit(self):
        self.assertNotIn('weather',self.arena['sequence_state'])
        state=self.enter();self.assertTrue(state['started'])
        self.assertTrue(self.arena['sequence_state']['facts']['temple_entered'])
        self.arena=g_weather.update(self.arena,5.)
        # Match real saves, which discard transient occupancy and sound queues.
        self.arena=g_sequences.ensure(pickle.loads(pickle.dumps(self.arena.remove('sequence_runtime'))))
        state=self.arena['sequence_state']['weather'];elapsed=state['elapsed']
        for y in (322.,240.):
            self.move(480.,y)
            self.arena=g_sequences.update(self.arena,.016)
        self.assertEqual(self.arena['sequence_state']['weather']['elapsed'],elapsed)
        self.assertTrue(self.arena['rain_profile']['enabled'])
        self.assertEqual(g_sequences.validate_world(self.arena),[])

    def test_transition_stays_bounded_and_flash_does_not_accumulate(self):
        self.enter();self.arena=g_weather.update(self.arena,2.8)
        state=self.arena['sequence_state']['weather'];self.assertAlmostEqual(state['flash'],1.)
        self.assertGreater(self.arena['lighting_profile']['moonlight']['intensity'],1.)
        frozen=copy.deepcopy(state)
        self.arena=g_weather.update(self.arena,0.)
        self.assertEqual(state,frozen)
        self.arena=g_weather.update(self.arena,1.)
        self.assertEqual(state['flash'],0.)
        self.assertAlmostEqual(self.arena['lighting_profile']['moonlight']['intensity'],.13)
        self.assertEqual(self.arena['wind_profile']['strength'],36.)
        self.assertEqual(self.arena['wind_profile']['gust_strength'],26.)
        rain=self.arena['rain_profile']
        self.assertEqual((rain['unlit_opacity'],rain['lit_opacity']),(0.,0.))
        self.assertTrue(rain['distortion_enabled'])
        self.assertEqual(rain['direction']['x'],0.)
        self.assertEqual(rain['distortion_density'],.75)
        self.assertEqual(self.arena['lake_profile']['rain_distortion'],3.)
        self.arena=g_weather.update(self.arena,40.)
        self.assertEqual(state['wetness'],1.)
        self.assertGreater(state['next_strike'],state['elapsed'])
        self.assertTrue(any(e['type']=='weather_thunder' for e in self.arena['sequence_runtime']['sounds']))

    def test_sheltered_interior_stays_dry_and_has_indoor_rain_mix(self):
        tm=self.arena['tile_map'];image=g_weather.terrain_image(tm)
        self.assertEqual(image.getpixel((30,14))[:3],(0,0,0))
        self.assertEqual(image.getpixel((20,20))[:3],(0,255,255))
        self.assertEqual(image.getpixel((20,18))[:3],(255,0,255))
        self.assertEqual(image.getpixel((20,20))[3],16,'deck receiving plane is raised above the lake')
        self.assertEqual(image.getpixel((20,18))[3],0,'lake receiving plane should be lower')
        self.assertEqual(self.arena['entities']['lake_props']['roof']['runoff_elevation'],16.)
        self.enter();self.arena=g_weather.update(self.arena,2.)
        state,_=g_audio.resolve_listener_rain_state({'x':480.,'y':240.},tm,self.arena['rain_profile'])
        self.assertEqual(state,'indoors')

    def test_plank_direction_preserves_collision_audio_and_chunk_continuity(self):
        tm=self.arena['tile_map']
        self.assertEqual(g_surfaces.cell(tm,20,20)['surface_axis'],'x')
        self.assertEqual(g_surfaces.cell(tm,30,18)['surface_axis'],'y')
        before=copy.deepcopy(g_surfaces.cell(tm,20,20));key=g_surfaces.signature(tm,5,5)
        g_surfaces.paint(tm,[(20,20)],'wood',plank_axis='y',style='temple',soft=False)
        self.assertNotEqual(key,g_surfaces.signature(tm,5,5))
        tile=g_surfaces.cell(tm,20,20)
        self.assertEqual(tile['index'],before['index'])
        self.assertEqual(g_audio.get_tile_audio_surface(tm,{'x':325.,'y':328.}),'wood')
        combined=g_surfaces.wood_layer(tm,288,288,128,64)
        left=g_surfaces.wood_layer(tm,288,288,64,64);right=g_surfaces.wood_layer(tm,352,288,64,64)
        joined=Image.new('RGBA',(128,64));joined.paste(left,(0,0));joined.paste(right,(64,0))
        self.assertEqual(combined.tobytes(),joined.tobytes())

    def test_imported_sprites_have_hard_alpha_and_no_magenta(self):
        root=Path(__file__).resolve().parent/'art/temple'
        for name in ('roof','lantern_red','lantern_white','lantern_frame','lily_flower','lily_leaves'):
            with Image.open(root/(name+'.png')) as im:p=np.asarray(im).astype(int)
            self.assertEqual(set(np.unique(p[:,:,3])),{0,255})
            opaque=p[p[:,:,3]>0]
            self.assertFalse(np.any((opaque[:,0]>opaque[:,1]+50)&(opaque[:,2]>opaque[:,1]+30)&(abs(opaque[:,0]-opaque[:,2])<85)),name)

    def test_delayed_thunder_reaches_the_audio_family(self):
        from test_audio import FakeSound,listener
        self.enter();self.arena=g_weather.update(self.arena,2.8)
        self.assertEqual(self.arena['sequence_runtime']['sounds'],[])
        self.arena=g_weather.update(self.arena,2.)
        event=self.arena['sequence_runtime']['sounds'][0]
        runtime=g_audio.make_audio_runtime(seed=733)
        self.assertTrue(g_audio.queue_audio_event(runtime,event))
        with mock.patch.object(g_audio.cma,'Sound',FakeSound):
            voices=g_audio._process_event(runtime,runtime['event_queue'].pop(),listener(480.,240.),
                self.arena['tile_map'],self.arena['entities'],g_audio.normalize_audio_profile(g_audio.make_audio_profile()))
        self.assertEqual(voices[0]['family'],'weather.thunder')
        self.assertEqual(Path(voices[0]['path']).name,'thunder.wav')

    def test_old_scenes_and_disabled_weather_are_unchanged(self):
        old=make_arena();self.assertIs(g_weather.update(old,2.),old)
        self.assertFalse(g_weather.enabled(self.arena.remove('lake_profile')))

    def test_roof_runoff_tracks_painted_eave(self):
        prop=self.arena['entities']['lake_props']['roof']
        edge=g_weather.eave_image(prop)
        with Image.open('art/temple/roof.png') as image:
            for x in range(image.width):
                bbox=image.getchannel('A').crop((x,0,x+1,image.height)).getbbox()
                if bbox:self.assertAlmostEqual(edge.getpixel((x,0))[0]/255*image.height,bbox[3],delta=.5)
                else:self.assertEqual(edge.getpixel((x,0))[1],0)

    def test_lantern_sway_is_continuous_and_uses_shared_gusts(self):
        prop=self.arena['entities']['lake_props']['lantern:0']
        self.enter();self.arena=g_weather.update(self.arena,5.)
        wind=self.arena['wind_profile']
        angles=[g_water.lantern_angle(prop,wind,t/60.) for t in range(1200)]
        self.assertGreater(max(angles)-min(angles),4.)
        self.assertLess(max(abs(b-a) for a,b in zip(angles,angles[1:])),.5)
        self.assertTrue(any(abs(a-round(a))>.1 for a in angles))
        self.assertEqual(g_water.lantern_angle(prop,dict(wind,strength=0.,gust_strength=0.,vertical_flutter=0.),4.),0.)
        self.assertEqual(rig.irregular_wind(dict(wind,tree_seed=1),(100,200),3.),rig.irregular_wind(dict(wind,tree_seed=9),(100,200),3.))

    def test_strong_tree_wind_remains_pinned_and_within_texture(self):
        self.enter();self.arena=g_weather.update(self.arena,5.)
        wind=dict(self.arena['wind_profile']);wind['strength']*=.6;wind['gust_strength']*=.6
        old=dict(wind,strength=22.*.6,gust_strength=14.*.6,tree_motion_gain=1.)
        movement=[];previous=[]
        for part in rig.PARTS:
            points,_,_=rig.mesh_topology(tuple(part['bounds']),tuple(part['pivot']))
            for t in range(40):
                positions,_=rig.mesh_pose(part,t*.5,wind,(138.,376.))
                before,_=rig.mesh_pose(part,t*.5,old,(138.,376.))
                self.assertEqual(positions[points.index(part['pivot'])],part['pivot'])
                self.assertTrue(all(-16.<x<144. and -16.<y<144. for x,y in positions))
                movement.append(positions[-1][0]);previous.append(before[-1][0])
        # Compare displacement from each part's own baseline, not tree spacing.
        current=np.asarray(movement).reshape(len(rig.PARTS),40).std(axis=1).mean()
        original=np.asarray(previous).reshape(len(rig.PARTS),40).std(axis=1).mean()
        self.assertGreater(current,original*1.4)


if __name__=='__main__':unittest.main()
