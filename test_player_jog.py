"""Grounding, continuity and runtime compatibility of the relaxed jog."""
import math
from pathlib import Path
import unittest

import numpy as np

import player_jog as jog
from photo_asset_pipeline.temple3d.living import gait as sprint
from test_player_refined_assets import animation_channel,glb,joints
from test_temple_living import accessor

ROOT=Path(__file__).resolve().parent


class PlayerJogTests(unittest.TestCase):
    def test_contact_matches_world_travel_and_leg_links_reach(self):
        anchors=[]
        for i in range(1000):
            phase=i/1000
            for side in (0.,.5):
                l=jog.leg(phase,side)
                self.assertAlmostEqual(math.dist(l['hip'],l['knee']),jog.THIGH,places=7)
                self.assertAlmostEqual(math.dist(l['knee'],l['ankle']),jog.SHIN,places=7)
                self.assertGreaterEqual(l['clearance'],-1e-6,(phase,side))
            if phase<jog.STANCE:
                f=jog.foot(phase);pitch=f['pitch'];contact=jog.HEEL if pitch>=0 else jog.TOE
                anchors.append(f['forward']+contact*math.cos(pitch)+jog.ANKLE*math.sin(pitch)-contact+jog.JOG_STRIDE*phase)
        self.assertLess(max(anchors)-min(anchors),1e-7)

    def test_ground_contact_recovery_and_loop_have_no_velocity_jumps(self):
        def pose(p):
            l=jog.leg(p)
            return (*l['hip'],*l['knee'],*l['ankle'],l['pitch'])
        h=1e-6
        for p in (0.,.052,.12,.235,jog.STANCE,.425,.43,.5,.53,.70,.79,.86,1.):
            a,b,c=(pose(p+s) for s in (-h,0.,h))
            for x,y,z in zip(a,b,c):
                self.assertLess(abs(z-x),.001,p)
                self.assertLess(abs((z-y)/h-(y-x)/h),.02,p)

    def test_jog_is_less_strained_at_its_real_game_cadence(self):
        cycle=jog.JOG_STRIDE*(1.73/25.65)/jog.JOG_SPEED
        steps_per_minute=120/cycle
        self.assertTrue(155<steps_per_minute<180)
        thigh=[math.degrees(jog.swing_angles(jog.STANCE+(1-jog.STANCE)*i/600)[0]) for i in range(601)]
        self.assertTrue(35<max(thigh)<55)
        self.assertLess(max(thigh),math.degrees(sprint._run_swing_angles(.83)[0])*.7)
        for i in range(100):
            p=i/100
            self.assertLess(math.degrees(jog.torso_lean(p)),3.)
            u,l,_=jog.arm_vectors(p,-1)
            flex=math.degrees(math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(u,l))))))
            self.assertTrue(50<flex<100)
        rear=jog.arm_vectors(0.,-1);front=jog.arm_vectors(.5,-1)
        def wrist_forward(v):return sprint.UPPER_ARM*v[0][1]+sprint.FOREARM*v[1][1]
        self.assertLess(wrist_forward(rear),-1.5,'Rear hand should pass behind the hip')
        self.assertGreater(wrist_forward(front),3.5,'Front hand should pump freely')
        # There is a genuine flight phase, rather than a sped-up walking cycle.
        self.assertTrue(any(not jog.foot(i/100)['stance'] and not jog.foot(i/100+.5)['stance'] for i in range(100)))

    def test_export_has_compatible_rest_rig_and_seamless_loop(self):
        old,old_data=glb(ROOT/'art'/'temple'/'combat'/'player.glb')
        new,data=glb(ROOT/'art'/'temple'/'player_jog'/'jog.glb')
        self.assertEqual(joints(old),joints(new))
        np.testing.assert_allclose(accessor(old,old_data,old['skins'][0]['inverseBindMatrices']),
                                   accessor(new,data,new['skins'][0]['inverseBindMatrices']),atol=1e-5)
        self.assertEqual([a['name'] for a in new['animations']],['run'])
        for bone in joints(new):
            for path in ('rotation','translation'):
                times,values=animation_channel(new,data,'run',bone,path)
                self.assertAlmostEqual(float(times[-1,0]),1.,places=5)
                if path=='rotation':self.assertAlmostEqual(abs(float(np.dot(values[0],values[-1]))),1.,places=4)
                else:np.testing.assert_allclose(values[0],values[-1],atol=1e-5)


if __name__=='__main__':unittest.main()
