"""Car intro timing, frame-independent scrolling, input and portable assets."""
from pathlib import Path
import json
import math
import struct
import unittest
import wave
import numpy as np
from g_temple_intro import Intro,load_script,local_point,road_x,road_slope,scenery,wiper_angle,WIPER_PERIOD
from test_temple_living import accessor

ROOT=Path(__file__).resolve().parent
KIT=ROOT/'art'/'temple'/'intro'


def controller_fixture():
    from test_cinematics_editor import fixture_document
    document=load_script();document['duration']=142;document['shots']=fixture_document()['shots']
    return document


class IntroTests(unittest.TestCase):
    def test_script_is_bounded_ordered_and_covers_dispatch_lore_and_arrival(self):
        document=load_script();self.assertTrue(90<=document['duration']<=180)
        words=' '.join(line['text'] for line in document['lines'])
        for word in ('caretaker','temple','bell','together'):self.assertIn(word,words)
        self.assertEqual({line['speaker'] for line in document['lines']},{'DRIVER','FRONT PASSENGER','YOU'})
        state=Intro(document);state.elapsed=document['lines'][0]['start'];self.assertIsNotNone(state.line)
        state.elapsed=document['lines'][0]['end'];self.assertIsNone(state.line)

    def test_full_ride_integral_is_independent_of_frame_rate_and_stops(self):
        document=controller_fixture();states=[]
        for dt in (.02,.05,.10):
            state=Intro(document)
            while not state.finished:state.tick(dt)
            states.append(state)
        self.assertEqual({s.distance for s in states},{states[0].distance})
        self.assertEqual(states[0].speed,0)
        self.assertAlmostEqual(states[0].arrival_station-states[0].distance,20.)
        self.assertEqual(states[0].fade,1.)

    def test_pause_freezes_camera_scrolling_weather_and_subtitle_clock(self):
        state=Intro(controller_fixture());state.elapsed=20.;frozen=state.elapsed,state.distance,state.yaw,state.pitch
        state.tick(.05,pause=True)
        for _ in range(12):state.tick(.05,(100,-100))
        self.assertEqual((state.elapsed,state.distance,state.yaw,state.pitch),frozen)
        state.tick(.05,pause=True);self.assertGreater(state.elapsed,20)
        state.tick(.05,skip=True);self.assertTrue(state.finished)

    def test_look_can_turn_to_all_windows_and_clamps_vertical_limits(self):
        state=Intro(controller_fixture(),elapsed=17.);distance=state.distance
        state.tick(0,(700,-900));self.assertEqual(state.pitch,62)
        self.assertAlmostEqual(state.yaw,98)
        state.tick(0,(800,1800));self.assertLess(state.yaw,0);self.assertEqual(state.pitch,-65)
        self.assertEqual(state.distance,distance)
        state.tick(0,reset=True);self.assertEqual((state.yaw,state.pitch),(0,-8))

    def test_cuts_cover_the_ride_and_preserve_interior_look(self):
        state=Intro(controller_fixture());shots=state.document['shots']
        self.assertEqual([s['kind'] for s in shots],['opening','interior','drone','interior','tracking','interior','arrival'])
        for shot in shots:
            state.elapsed=shot['start'];self.assertEqual(state.shot,shot)
            state.yaw,state.pitch=31.,-12.;state.tick(0,(100,100))
            if shot['kind']=='interior':self.assertNotEqual((state.yaw,state.pitch),(31.,-12.))
            else:
                self.assertEqual((state.yaw,state.pitch),(31.,-12.))
                state.tick(0,reset=True);self.assertEqual((state.yaw,state.pitch),(31.,-12.))
        state.elapsed=43.99;state.yaw,state.pitch=56.,-9.;state.tick(.02)
        self.assertEqual(state.shot['kind'],'drone')
        state.elapsed=55.99;state.tick(.02,(120,-140))
        self.assertTrue(state.interactive);self.assertEqual((state.yaw,state.pitch),(56.,-9.))

    def test_night_and_headlights_transition_in_the_side_tracking_shot(self):
        state=Intro(controller_fixture());shot=state.night_shot
        state.elapsed=shot['start'];self.assertAlmostEqual(state.dusk,.18);self.assertEqual(state.headlights,0)
        state.elapsed=shot['start']+6;self.assertTrue(0<state.headlights<1)
        state.elapsed=shot['end'];self.assertEqual(state.dusk,1);self.assertEqual(state.headlights,1)
        state.elapsed=135;self.assertEqual(state.dusk,1);self.assertEqual(state.headlights,1)

    def test_world_is_bounded_and_follows_road_tangent_at_the_car(self):
        for distance in (0,17,999,1e6):
            self.assertEqual(local_point(distance,0,distance),(0.,0.))
            x,z=local_point(distance+.001,0,distance)
            self.assertLess(abs(x),1e-7);self.assertLess(z,0)
            items=list(scenery(distance));self.assertLessEqual(len(items),76)
            self.assertTrue(all(-93<t['z']<21 and math.isfinite(t['x']) for t in items))
            self.assertEqual(items,list(scenery(distance)))

    def test_wipers_sweep_continuously_and_reverse_at_periodic_extremes(self):
        self.assertAlmostEqual(wiper_angle(0),math.radians(8))
        self.assertAlmostEqual(wiper_angle(WIPER_PERIOD/2),math.radians(102))
        self.assertAlmostEqual(wiper_angle(WIPER_PERIOD),wiper_angle(0))
        angles=[wiper_angle(i*WIPER_PERIOD/200) for i in range(101)]
        self.assertTrue(all(b>a for a,b in zip(angles,angles[1:])))

    def test_dusk_and_braking_are_smooth_and_monotonic(self):
        state=Intro(controller_fixture());last=0;last_dusk=0
        for i in range(state.duration*10+1):
            state.elapsed=i/10
            self.assertGreaterEqual(state.distance,last);self.assertGreaterEqual(state.dusk,last_dusk)
            last,last_dusk=state.distance,state.dusk
        state.elapsed=state.duration-10;self.assertTrue(0<state.speed<10.5)

    def test_assets_are_embedded_compact_and_audio_has_valid_loop_beds(self):
        manifest=json.loads((KIT/'manifest.json').read_text())
        self.assertTrue({'sedan_exterior','headlamps','tyre','player_seated'}<=manifest['models'].keys())
        self.assertEqual(manifest['models']['player_seated']['triangles'],2930)
        self.assertLess(manifest['models']['sedan']['triangles'],6500)
        for name in manifest['models']:
            raw=(KIT/(name+'.glb')).read_bytes();size,kind=struct.unpack_from('<II',raw,12)
            doc=json.loads(raw[20:20+size]);offset=20+size;length,_=struct.unpack_from('<II',raw,offset)
            binary=raw[offset+8:offset+8+length]
            self.assertTrue(doc['meshes']);self.assertTrue(all('uri' not in image for image in doc['images']))
            for mesh in doc['meshes']:
                for p in mesh['primitives']:
                    positions=accessor(doc,binary,p['attributes']['POSITION'])
                    self.assertTrue(np.isfinite(positions).all())
        for name in ('rain_cabin','engine','wiper'):
            with wave.open(str(KIT/(name+'.wav'))) as sound:
                self.assertEqual(sound.getnchannels(),1);self.assertEqual(sound.getsampwidth(),2)
                self.assertEqual(sound.getframerate(),22050);self.assertGreater(sound.getnframes(),6000)


if __name__=='__main__':unittest.main()
