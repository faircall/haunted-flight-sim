"""Physics-facing checks for the opt-in player animation, with no GPU/audio."""
import math
import unittest

from photo_asset_pipeline.temple3d.living import gait as original
import player_gait_v2 as gait


class CandidateGaitTests(unittest.TestCase):
    def test_existing_game_stride_and_planted_velocity_agree(self):
        for clip in ('walk','walk_back','run'):
            cfg=gait.SETTINGS[clip]
            self.assertAlmostEqual(cfg['stride'],original.SETTINGS['run' if clip=='run' else 'walk']['stride'])
            direction=-1 if clip=='walk_back' else 1
            world_contacts=[]
            for n in range(1,140):
                phase=cfg['stance']*n/140
                foot=gait.foot(clip,phase);pitch=foot['pitch']
                contact=gait.HEEL if pitch>=0 else gait.TOE
                anchored=foot['forward']+contact*math.cos(pitch)+gait.ANKLE*math.sin(pitch)-contact
                world_contacts.append(anchored+direction*cfg['stride']*phase)
                self.assertAlmostEqual(foot['height']-gait.ANKLE*math.cos(pitch)+contact*math.sin(pitch),0.,places=8)
            self.assertLess(max(world_contacts)-min(world_contacts),1e-7,clip)

    def test_exact_links_reach_floor_and_keep_clearance_nonnegative(self):
        for clip in ('idle','walk','walk_back','run'):
            clearance=[]
            for n in range(600):
                for side in (0.,.5):
                    pose=gait.leg(clip,n/600,side)
                    self.assertAlmostEqual(math.dist(pose['hip'],pose['knee']),gait.THIGH,places=7)
                    self.assertAlmostEqual(math.dist(pose['knee'],pose['ankle']),gait.SHIN,places=7)
                    pitch=pose['pitch'];contact=gait.HEEL if pitch>=0 else gait.TOE
                    sole=pose['height']-gait.ANKLE*math.cos(pitch)+contact*math.sin(pitch)
                    self.assertGreaterEqual(sole,-1e-9,(clip,n,side))
                    clearance.append(sole)
            if clip!='idle':self.assertGreater(max(clearance),.5,clip)
            if clip=='run':self.assertLess(max(clearance),3.0,'Avoid the former exaggerated high kick')

    def test_position_and_velocity_cross_takeoff_landing_and_loop_smoothly(self):
        def values(clip,p):
            pose=gait.leg(clip,p,0.)
            return (*pose['hip'],*pose['knee'],*pose['ankle'],pose['pitch'])
        step=1e-5
        for clip in ('walk','walk_back','run'):
            for phase in (0.,.5,gait.SETTINGS[clip]['stance'],(gait.SETTINGS[clip]['stance']+.5)%1.):
                a,b,c=(values(clip,phase+shift) for shift in (-step,0.,step))
                for index in range(len(b)):
                    self.assertLess(abs(a[index]-c[index]),.003,(clip,phase,index))
                    velocity_jump=abs((b[index]-a[index])/step-(c[index]-b[index])/step)
                    self.assertLess(velocity_jump,.12,(clip,phase,index))

    def test_weight_transfer_and_airborne_swing_are_asymmetric_through_cycle(self):
        for clip in ('walk','walk_back','run'):
            lateral=[gait.pelvis(clip,n/100.)['lateral'] for n in range(100)]
            self.assertLess(min(lateral),-.15);self.assertGreater(max(lateral),.15)
            difference=[abs(gait.foot(clip,n/100)['forward']-gait.foot(clip,n/100+.5)['forward']) for n in range(100)]
            self.assertGreater(max(difference),6.)
            for n in range(100):
                for side in (0.,.5):
                    pose=gait.leg(clip,n/100,side)
                    self.assertLess(abs(pose['knee'][0]-pose['hip'][0]),.65,clip)
        flight=[min(gait.foot('run',p)['clearance'],gait.foot('run',p+.5)['clearance']) for p in (n/200 for n in range(200))]
        self.assertGreater(max(flight),.5)
        self.assertLess(max(flight),2.6)
        self.assertTrue(any(gait.foot('run',n/100)['stance'] for n in range(100)))

    def test_running_arms_stay_bent_and_counter_swing(self):
        shoulders=[];bends=[]
        for p in (n/100 for n in range(100)):
            upper,lower,_=gait.arms('run',p,-1)
            shoulders.append(math.degrees(math.atan2(upper[1],-upper[2])))
            bends.append(math.degrees(math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(upper,lower)))))))
        self.assertLess(min(shoulders),-25.);self.assertGreater(max(shoulders),25.)
        self.assertGreater(min(bends),30.);self.assertLess(max(bends),110.)
        front=gait.arms('run',.5,-1);back=gait.arms('run',0.,-1)
        self.assertGreater(front[1][2],back[1][2])
        advancing=gait.arms('run',.25,-1);retreating=gait.arms('run',.75,1)
        def bend(pair):return math.degrees(math.acos(sum(a*b for a,b in zip(pair[0],pair[1]))))
        self.assertGreater(bend(retreating)-bend(advancing),35.)

    def test_turning_planted_foot_counters_actual_game_heading(self):
        for direction in (-1,1):
            for n in range(49):
                phase=n/100.;angle,lift=gait.turn_foot(phase,direction)
                self.assertEqual(lift,0.)
                self.assertAlmostEqual(angle-direction*1.8*phase,
                                       -direction*1.8*.25,places=10)
            self.assertGreater(gait.turn_foot(.75,direction)[1],.5)


if __name__=='__main__':unittest.main()

