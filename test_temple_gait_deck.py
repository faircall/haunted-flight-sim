"""Contact/stride invariants and suspended structure/collision compatibility."""
import copy
import math
import unittest

from photo_asset_pipeline.temple3d.living import gait
import g_temple_deck as deck
import g_temple_structure as structure
import test_temple_cameras as camera_tests


class GaitTests(unittest.TestCase):
    @staticmethod
    def knee_flex(pose):
        h,k,a=(pose[key] for key in ('hip','knee','ankle'))
        u=tuple(hh-kk for hh,kk in zip(h,k));v=tuple(aa-kk for aa,kk in zip(a,k))
        dot=sum(x*y for x,y in zip(u,v))/(math.sqrt(sum(x*x for x in u))*math.sqrt(sum(y*y for y in v)))
        return 180-math.degrees(math.acos(max(-1.,min(1.,dot))))

    @staticmethod
    def hand_offset(clip,phase,sign):
        vectors=gait.arm_vectors(clip,phase,sign)
        return tuple(sum(length*vector[axis] for length,vector in zip(
            (gait.UPPER_ARM,gait.FOREARM,gait.HAND),vectors)) for axis in range(3))

    @classmethod
    def hand_from_hip(cls,clip,phase,sign):
        """Resolve the tilted shoulder anchor as the Blender builder does."""
        lean=gait.torso_lean(clip,phase);bank=gait.torso_bank(clip,phase)
        x,y,z=math.sin(bank),-math.sin(lean)*math.cos(bank),math.cos(lean)*math.cos(bank)
        right=(1-x*x/(1+z),-x*y/(1+z),-x)
        forward=(-x*y/(1+z),1-y*y/(1+z),-y)
        twist=gait.torso_twist(clip,phase)
        right=tuple(a*math.cos(twist)+b*math.sin(twist) for a,b in zip(right,forward))
        reach=gait.SHOULDER_HEIGHT-(gait.THIGH+gait.SHIN+1.)
        shoulder=(sign*gait.SHOULDER_HALF_WIDTH*right[0]+reach*x,
                  -sign*gait.SHOULDER_HALF_WIDTH*right[1]-reach*y,
                  sign*gait.SHOULDER_HALF_WIDTH*right[2]+reach*z)
        return tuple(a+b for a,b in zip(shoulder,cls.hand_offset(clip,phase,sign)))

    def test_legs_keep_adult_proportions_and_bend_forward_without_stretching(self):
        self.assertAlmostEqual(gait.THIGH+gait.SHIN,11.6)
        self.assertTrue(.9<gait.THIGH/gait.SHIN<1.1)
        for clip in ('idle','walk','run'):
            for frame in range(240):
                for side in (0.,.5):
                    pose=gait.leg_3d(clip,frame/240,side)
                    h,k,a=(pose[key] for key in ('hip','knee','ankle'))
                    self.assertTrue(all(math.isfinite(v) for point in (h,k,a) for v in point))
                    self.assertAlmostEqual(math.dist(h,k),gait.THIGH)
                    self.assertAlmostEqual(math.dist(k,a),gait.SHIN)
                    cross=(a[1]-h[1])*(k[2]-h[2])-(a[2]-h[2])*(k[1]-h[1])
                    self.assertGreater(cross,0.,clip)

    def test_stance_contact_is_grounded_and_does_not_slide(self):
        for clip,settings in gait.SETTINGS.items():
            for frame in range(101):
                phase=settings['stance']*frame/101
                f=gait.foot(clip,phase);pitch=f['pitch']
                contact=gait.HEEL if pitch>=0 else gait.TOE
                height=f['height']+contact*math.sin(pitch)-gait.ANKLE*math.cos(pitch)
                self.assertAlmostEqual(height,0.,places=6)
                position=f['forward']+contact*math.cos(pitch)+gait.ANKLE*math.sin(pitch)
                world_position=position+settings['stride']*phase
                self.assertAlmostEqual(world_position,settings['front']+contact,places=6)
                for side,sign in ((0.,-1),(.5,1)):
                    pose=gait.leg_3d(clip,phase-side,side)
                    self.assertAlmostEqual(pose['ankle'][0],gait.foot_lateral(clip,sign))

    def test_walking_is_a_low_recovery_arc_with_soft_support_and_extended_landing(self):
        samples=[];support=[]
        for i in range(1000):
            phase=i/1000;pose=gait.leg_3d('walk',phase)
            flex=self.knee_flex(pose)
            samples.append((flex,phase,pose['ankle'][1]-pose['hip'][1]))
            if .05<phase<.34:support.append(flex)
        flex,phase,forward=max(samples)
        self.assertTrue(.64<phase<.76)
        self.assertLess(forward,-2.5)
        self.assertTrue(45<flex<65)
        self.assertLess(max(s[0] for s in samples if s[1]>.90),15.)
        self.assertTrue(5<min(support)<15)
        self.assertLess(max(support),22.)
        clearance=max(gait.foot('walk',i/1000)['clearance'] for i in range(1000))
        self.assertTrue(1.2<clearance<1.9)
        self.assertLess(min(s[0] for s in samples),10.)

    def test_walking_toeoff_flows_directly_into_forward_heel_recovery(self):
        stance=gait.SETTINGS['walk']['stance'];early_speeds=[];later_speeds=[]
        for frame in range(121):
            phase=stance+.0005*frame;eps=1e-5
            a=gait.leg_3d('walk',phase-eps);b=gait.leg_3d('walk',phase+eps)
            ankle=tuple((bb-aa)/(2*eps) for aa,bb in zip(a['ankle'],b['ankle']))
            knee=tuple((bb-aa)/(2*eps) for aa,bb in zip(a['knee'],b['knee']))
            # The lifted heel starts advancing at once. The knee must not
            # continue backward, hover, then reverse again several frames later.
            self.assertGreater(ankle[1],0.)
            self.assertGreater(ankle[2],0.)
            self.assertGreater(knee[1],0.)
            speed=math.sqrt(sum(v*v for v in knee))
            (early_speeds if phase<stance+.025 else later_speeds).append(speed)
        self.assertGreater(min(early_speeds),.5*sum(later_speeds)/len(later_speeds))

    def test_running_recovers_the_heel_and_loads_after_softly_extended_contact(self):
        flex=[];knees=[];hips=[];lateral=[]
        for i in range(500):
            phase=i/500;motion=gait.pelvis_motion('run',phase)
            lateral.append(motion['lateral']);hips.append(gait.hip_height('run',phase))
            self.assertTrue(1.<motion['forward']<1.4)
            self.assertTrue(.08<motion['up'][1]<.13)
            for side in (0.,.5):
                pose=gait.leg_3d('run',phase,side)
                flex.append(self.knee_flex(pose))
                if pose['stance']:knees.append(pose['knee'][1]-pose['hip'][1])
                if (phase+side)%1<.025:
                    self.assertTrue(5<flex[-1]<20)
                    self.assertLess(pose['ankle'][1]-pose['hip'][1],gait.THIGH*.85)
        self.assertTrue(85<max(flex)<100)
        self.assertLess(min(flex),10.)
        self.assertLess(min(knees),-gait.THIGH*.35)
        self.assertTrue(1.<max(lateral)-min(lateral)<1.5)
        self.assertTrue(.7<max(hips)-min(hips)<1.2)

    def test_running_lifts_both_feet_and_body_between_supports(self):
        apex=(gait.SETTINGS['run']['stance']+.5)/2
        for phase in (apex,apex+.5):
            feet=[gait.foot('run',phase+side) for side in (0.,.5)]
            self.assertTrue(all(not f['stance'] for f in feet))
            self.assertGreater(min(f['clearance'] for f in feet),.6)
            rise=gait.hip_height('run',phase)-gait.hip_height('run',0.)
            self.assertTrue(.3<rise<.65)

    def test_arm_articulation_preserves_lengths_and_jacket_clearance(self):
        for clip in ('walk','run'):
            elbows=[];hands=[]
            for i in range(240):
                phase=i/240;u,l,p=gait.arm_vectors(clip,phase,1)
                for vector in (u,l,p):self.assertAlmostEqual(sum(v*v for v in vector),1.)
                flex=math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(u,l)))))
                self.assertAlmostEqual(flex,gait.arm(clip,phase)[1])
                elbows.append(180-math.degrees(flex));hands.append(self.hand_offset(clip,phase,1)[1])
            self.assertLess(min(hands),-2.)
            self.assertGreater(max(hands),4.)
            if clip=='run':
                self.assertTrue(60<min(elbows)<75)
                self.assertTrue(150<max(elbows)<165)
                self.assertGreater(max(elbows)-min(elbows),80.)
            else:self.assertTrue(all(160<angle<175 for angle in elbows))
        for sign in (-1,1):
            for phase in (.25,.75):
                offset=self.hand_offset('walk',phase,sign)
                ends=min(sign*self.hand_offset('walk',p,sign)[0] for p in (0.,.5))
                self.assertLess(sign*offset[0],ends-.1)
                self.assertGreater(gait.SHOULDER_HALF_WIDTH+sign*offset[0],2.8)
            front=self.hand_offset('run',.5,sign)
            # The higher pump brings the hand inward; keep it on its own side
            # of the chest while native checks verify actual surface clearance.
            self.assertTrue(.5<gait.SHOULDER_HALF_WIDTH+sign*front[0]<2.5)

    def test_running_elbow_stays_open_through_rear_reversal_and_return_to_hip(self):
        for sign in (-1,1):
            crossing=None;previous=self.hand_from_hip('run',0.,sign)
            for i in range(1,251):
                phase=i/500
                hand=self.hand_from_hip('run',phase,sign)
                inside=180-math.degrees(gait.arm('run',phase)[1])
                if hand[1]<-.25 and hand[1]>previous[1]:self.assertGreater(inside,145.)
                if previous[1]<0<=hand[1] and crossing is None:
                    crossing=(phase,inside)
                previous=hand
            self.assertIsNotNone(crossing)
            self.assertTrue(.18<crossing[0]<.3)
            self.assertTrue(145<crossing[1]<165)
        for phase in (0.,.1,.9):
            self.assertTrue(150<180-math.degrees(gait.arm('run',phase)[1])<165)
        self.assertTrue(60<180-math.degrees(gait.arm('run',.5)[1])<75)

    def test_running_abducts_arms_and_keeps_passing_hands_outside_thighs(self):
        for sign,side in ((-1,0.),(1,.5)):
            for i in range(100):
                phase=.15+.13*i/99
                hand=self.hand_from_hip('run',phase,sign)
                upper=gait.arm_vectors('run',phase,sign)[0]
                self.assertTrue(.1<sign*upper[0]<.18)
                if abs(hand[1])<2.:
                    self.assertGreater(sign*hand[0],3.)
                    leg=gait.leg_3d('run',phase,side)
                    centre=gait.pelvis_motion('run',phase)['lateral']
                    thigh_lateral=sign*(leg['hip'][0]-centre)
                    self.assertGreater(sign*hand[0]-thigh_lateral,1.5)

    def test_narrower_shoulders_keep_relaxed_hands_beside_the_trousers(self):
        for clip in ('idle','walk'):
            for sign in (-1,1):
                for frame in range(120):
                    phase=frame/120
                    hand=self.hand_from_hip(clip,phase,sign)
                    self.assertTrue(2.7<sign*hand[0]<3.9)
                    for vector in gait.arm_vectors(clip,phase,sign):
                        self.assertAlmostEqual(sum(v*v for v in vector),1.)

    def test_running_front_pump_folds_the_forearm_up_with_a_tight_elbow(self):
        for sign in (-1,1):
            for frame in range(31):
                phase=.44+.12*frame/30
                inside=180-math.degrees(gait.arm('run',phase)[1])
                hand=self.hand_from_hip('run',phase,sign)
                self.assertTrue(60<inside<75)
                self.assertGreater(gait.arm_vectors('run',phase,sign)[1][2],.6)
                self.assertGreater(hand[2],gait.TORSO*.6)
                vectors=gait.arm_vectors('run',phase,sign)
                # Raise the upper arm as well as the hand: simply tightening
                # the elbow would leave the elbow near the jacket's waist.
                self.assertGreater(vectors[0][1],.60)
                self.assertGreater(vectors[0][2],-.78)
                hand_height=sum(length*vector[2] for length,vector in zip(
                    (gait.UPPER_ARM,gait.FOREARM,gait.HAND),vectors))
                self.assertGreater(hand_height,.40)
            # The peak stays high, but neither side of it holds a fixed bend.
            self.assertGreater(self.hand_offset('run',.5,sign)[2],1.1)
        bends=[gait.arm('run',phase)[1] for phase in (.42,.46,.49,.5,.51,.54,.58)]
        self.assertTrue(all(a<b for a,b in zip(bends[:4],bends[1:4])))
        self.assertTrue(all(a>b for a,b in zip(bends[3:],bends[4:])))
        # Less time near the upper-arm peak prevents a whole-pose pause even
        # though angular velocity must pass through zero at each reversal.
        shoulder_near_peak=sum(math.degrees(gait.arm('run',i/1000)[0])>40. for i in range(1000))
        self.assertLess(shoulder_near_peak,120)

    def test_running_pairs_under_body_recovery_with_late_forward_knee_drive(self):
        stance=gait.SETTINGS['run']['stance'];poses=[]
        def thigh(pose):
            h,k=pose['hip'],pose['knee']
            return math.degrees(math.atan2(k[1]-h[1],h[2]-k[2]))
        def support_axis(pose):
            h,a=pose['hip'],pose['ankle']
            return math.degrees(math.atan2(a[1]-h[1],h[2]-a[2]))
        for i in range(340):
            phase=stance*i/340;support=gait.leg_3d('run',phase)
            poses.append((phase,support,gait.leg_3d('run',phase,.5)))
        # Find the physical support landmarks instead of fixing a phase to
        # the current front/back contact distances. The folded swing thigh
        # stays near vertical while the other ankle passes under its hip.
        phase,support,swing=min(poses,key=lambda row:abs(support_axis(row[1])))
        self.assertLess(abs(support_axis(support)),1.)
        self.assertLess(self.knee_flex(support),25.)
        self.assertLess(abs(thigh(swing)),15.)
        self.assertTrue(80<self.knee_flex(swing)<100)
        self.assertLess(swing['ankle'][1]-swing['hip'][1],-gait.SHIN*.75)
        # At rear support the opposite thigh drives forward while the shin
        # remains folded. This is the paired pose in the 46–48 s reference.
        rear=min((row for row in poses if row[0]>stance*.65),key=lambda row:thigh(row[1]))
        self.assertLess(support_axis(rear[1]),-30.)
        self.assertLess(self.knee_flex(rear[1]),15.)
        self.assertTrue(70<thigh(rear[2])<90)
        self.assertTrue(80<self.knee_flex(rear[2])<100)
        # Recovery and under-body alignment are passing poses, so the knee
        # must keep moving relative to the pelvis at both landmarks.
        for phase in (.38,.43,.48,.62):
            eps=1e-5
            before,after=[gait.leg_3d('run',phase+d) for d in (-eps,eps)]
            relative=[tuple(k-h for k,h in zip(pose['knee'],pose['hip'])) for pose in (before,after)]
            self.assertGreater(math.dist(*relative)/(2*eps),4.)

    def test_running_opens_the_shin_progressively_into_soft_touchdown(self):
        phases=(.90,.95,.98,.999)
        poses=[gait.leg_3d('run',phase) for phase in phases]
        flex=[self.knee_flex(pose) for pose in poses]
        self.assertTrue(45<flex[0]<80)
        self.assertTrue(25<flex[1]<45)
        self.assertTrue(15<flex[2]<25)
        self.assertTrue(all(a>b for a,b in zip(flex,flex[1:])))
        # The shin is still opening as the sole descends in the final few
        # frames; there is no near-straight airborne plateau before contact.
        self.assertGreater(flex[2]-flex[3],2.)
        self.assertGreater(poses[1]['clearance'],poses[2]['clearance'])
        self.assertGreater(poses[2]['clearance'],poses[3]['clearance'])
        landing=gait.leg_3d('run',0.)
        self.assertTrue(12<self.knee_flex(landing)<18)
        self.assertAlmostEqual(landing['clearance'],0.)
        self.assertTrue(gait.THIGH*.55<landing['ankle'][1]-landing['hip'][1]<gait.THIGH*.85)

    def test_running_long_stride_measures_ground_travel_not_only_swing_reach(self):
        first,last=.04,.30
        contacts=[]
        for phase in (first,last):
            foot=gait.foot('run',phase);pitch=foot['pitch']
            pivot=gait.HEEL if pitch>=0 else gait.TOE
            contacts.append(foot['forward']+pivot*math.cos(pitch)+gait.ANKLE*math.sin(pitch)-pivot)
        travelled=(contacts[0]-contacts[1])/(last-first)
        self.assertAlmostEqual(travelled,gait.SETTINGS['run']['stride'])
        self.assertTrue(32.<travelled<36.)
        self.assertGreater(travelled,gait.SETTINGS['walk']['stride']*1.8)
        # Increasing the travelling distance at fixed speed must lengthen the
        # cycle too; otherwise the floor motion and planted foot would diverge.
        cycle=travelled/gait.SETTINGS['run']['speed']
        self.assertTrue(.75<cycle<.90)

    def test_running_has_one_smooth_recovery_and_no_rebend_before_contact(self):
        stance=gait.SETTINGS['run']['stance']
        curve=[self.knee_flex(gait.leg_3d('run',stance+(1-stance)*i/500)) for i in range(501)]
        peak=max(range(len(curve)),key=curve.__getitem__)
        self.assertTrue(100<peak<350)
        self.assertTrue(all(b>=a-.01 for a,b in zip(curve[:peak],curve[1:peak+1])))
        self.assertTrue(all(b<=a+.01 for a,b in zip(curve[peak:],curve[peak+1:])))
        self.assertGreater(curve[-20]-curve[-1],2.)
        self.assertLess(self.knee_flex(gait.leg_3d('run',.10)),25.)
        for i in range(500):
            pose=gait.leg_3d('run',i/500)
            self.assertLess(-(pose['knee'][0]-pose['hip'][0]),gait.THIGH*.12)

    def test_running_rear_foot_advances_continuously_out_of_folded_recovery(self):
        period=gait.SETTINGS['run']['stride']/gait.SETTINGS['run']['speed']
        for side in (0.,.5):
            for i in range(141):
                local=.48+.001*i;phase=local-side;eps=1e-5
                before,after=[gait.leg_3d('run',phase+d,side) for d in (-eps,eps)]
                relative=[pose['ankle'][1]-pose['hip'][1] for pose in (before,after)]
                speed=(relative[1]-relative[0])/(2*eps*period)
                # A moving knee can still leave the folded shoe almost still.
                # Check sustained forward shoe travel through the entire rear
                # recovery interval, relative to its moving hip.
                self.assertGreater(speed,.30*gait.SETTINGS['run']['speed'])

    def test_swing_foot_arcs_sideways_then_tracks_in_for_a_stable_landing(self):
        for clip,minimum_arc in (('walk',.12),('run',.07)):
            stance=gait.SETTINGS[clip]['stance']
            for sign in (-1,1):
                track=gait.foot_lateral(clip,sign,0.)
                for i in range(50):
                    self.assertAlmostEqual(gait.foot_lateral(clip,sign,stance*i/50),track)
                lateral=[sign*(gait.foot_lateral(clip,sign,stance+(1-stance)*i/100)-track) for i in range(101)]
                self.assertGreater(max(abs(v) for v in lateral),minimum_arc)
                if clip=='run':self.assertLessEqual(max(lateral),1e-8)
                self.assertAlmostEqual(lateral[0],0.)
                self.assertAlmostEqual(lateral[-1],0.)
                eps=1e-6
                for phase in (0.,stance):
                    a,b,c=[gait.foot_lateral(clip,sign,phase+d) for d in (-eps,0.,eps)]
                    self.assertAlmostEqual((b-a)/eps,(c-b)/eps,delta=.005)

    def test_walk_and_run_transfer_weight_and_counter_rotate_shoulders(self):
        for clip in ('walk','run'):
            lateral=[]
            for i in range(240):
                phase=i/240;motion=gait.pelvis_motion(clip,phase)
                lateral.append(motion['lateral'])
                self.assertAlmostEqual(sum(v*v for v in motion['up']),1.)
                self.assertAlmostEqual(sum(v*v for v in motion['right']),1.)
                self.assertAlmostEqual(sum(a*b for a,b in zip(motion['up'],motion['right'])),0.)
                # The builder's root uses -yaw; the spine twist uses +yaw.
                self.assertGreaterEqual(motion['yaw']*gait.torso_twist(clip,phase),0.)
            self.assertGreater(max(lateral)-min(lateral),.4)
            self.assertLess(gait.pelvis_motion(clip,.15)['lateral'],-.2)
            self.assertGreater(gait.pelvis_motion(clip,.65)['lateral'],.2)
        self.assertTrue(3<math.degrees(gait.torso_lean('run',0))<5)
        self.assertTrue(0<math.degrees(gait.torso_lean('walk',0))<3)

    def test_running_torso_banks_into_weight_transfer_and_rocks_with_loading(self):
        banks=[];leans=[]
        for frame in range(240):
            phase=frame/240
            bank=gait.torso_bank('run',phase);lean=gait.torso_lean('run',phase)
            banks.append(math.degrees(bank));leans.append(math.degrees(lean))
            tilt=math.degrees(math.acos(math.cos(lean)*math.cos(bank)))
            self.assertLessEqual(tilt,5.)
            motion=gait.pelvis_motion('run',phase)
            offset=gait.torso_side_offset('run',phase)
            self.assertGreaterEqual(offset*motion['lateral'],0.)
            self.assertLess(abs(offset),.35)
            self.assertLess(abs(math.degrees(gait.torso_bank('walk',phase))),.3)
        self.assertTrue(3.5<max(banks)-min(banks)<5.)
        self.assertTrue(.8<max(leans)-min(leans)<1.)
        self.assertTrue(all(3.<lean<4.5 for lean in leans))
        eps=1e-6
        for function in (gait.torso_bank,gait.torso_side_offset,gait.torso_lean):
            for phase in (0.,.5):
                a,b,c=[function('run',phase+d) for d in (-eps,0.,eps)]
                self.assertAlmostEqual((b-a)/eps,(c-b)/eps,delta=.005)

    def test_half_cycle_mirrors_body_motion_without_dragging_the_support_foot(self):
        for clip in ('walk','run'):
            for frame in range(120):
                phase=frame/120
                a=gait.leg_3d(clip,phase,0.)
                b=gait.leg_3d(clip,phase+.5,.5)
                for key in ('hip','knee','ankle'):
                    self.assertAlmostEqual(a[key][0],-b[key][0])
                    self.assertAlmostEqual(a[key][1],b[key][1])
                    self.assertAlmostEqual(a[key][2],b[key][2])

    def test_contact_paths_and_body_motion_close_with_continuous_velocity(self):
        for clip in gait.SETTINGS:
            phases=(0.,gait.SETTINGS[clip]['stance'])
            if clip=='run':phases+=(.38,.48,.565,.62,gait.SETTINGS['run']['recovery_peak'],gait.SETTINGS['run']['knee_drive'])
            for phase in phases:
                eps=1e-5
                a,b,c=[gait.foot(clip,phase+d) for d in (-eps,0,eps)]
                for key in ('forward','height','pitch'):
                    left=(b[key]-a[key])/eps;right=(c[key]-b[key])/eps
                    self.assertAlmostEqual(left,right,delta=.18,msg=f'{clip}/{key}/{phase}')
            for phase in (0.,.15,.45):
                eps=1e-6
                samples=[gait.arm_vectors(clip,phase+d,1) for d in (-eps,0.,eps)]
                for segment in range(3):
                    for axis in range(3):
                        a,b,c=(v[segment][axis] for v in samples)
                        self.assertAlmostEqual((b-a)/eps,(c-b)/eps,delta=.005)
                a,b,c=[gait.hip_height(clip,phase+d) for d in (-eps,0.,eps)]
                self.assertAlmostEqual((b-a)/eps,(c-b)/eps,delta=.005)

    def test_game_travel_speeds_keep_human_cadence(self):
        for clip,speed in (('walk',20.),('run',42.)):
            settings=gait.SETTINGS[clip]
            self.assertEqual(settings['speed'],speed)
            period=settings['stride']/settings['speed']
            if clip=='walk':
                self.assertTrue(.8<period<1.05)
                self.assertTrue(.53<settings['stance']<.62)
            else:
                self.assertTrue(.75<period<.90)
                self.assertTrue(.3<settings['stance']<.4)


class RaisedDeckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        camera_tests.TempleWalkabilityTests.setUpClass()
        cls.tm=camera_tests.TempleWalkabilityTests.tile_map
        cls.parts=deck.layout(cls.tm)

    def test_construction_preserves_logical_floor_and_collision_data(self):
        before=copy.deepcopy(self.tm)
        self.assertEqual(self.parts,deck.layout(self.tm))
        self.assertEqual(before,self.tm)
        self.assertTrue(any(p.kind=='board' for p in self.parts))
        for part in self.parts:
            self.assertTrue(all(a<b for a,b in zip(part.low,part.high)))
            if part.kind=='board':
                self.assertEqual(part.high[1],24. if part.owner=='temple' else 16.)
                self.assertAlmostEqual(part.high[1]-part.low[1],deck.BOARD_THICKNESS)
                self.assertGreater(part.low[1],13.)

    def test_piers_are_under_joists_inside_the_deck_and_below_water(self):
        cells=deck.floor_cells(self.tm)
        for part in self.parts:
            if part.kind!='pier':continue
            x=(part.low[0]+part.high[0])/2;z=(part.low[2]+part.high[2])/2
            if part.owner=='temple':
                self.assertTrue(400<=x<560 and 176<=z<280)
            else:self.assertIn((int(x)//16,int(z)//16),cells)
            self.assertLess(part.low[1],0)
            self.assertGreater(part.high[1],0)
            self.assertTrue(any(j.kind=='joist' and j.low[0]<=x<=j.high[0] and j.low[2]<=z<=j.high[2]
                                and abs(j.low[1]-part.high[1])<.001 for j in self.parts))

    def test_temple_and_bridge_both_have_open_space_under_boards(self):
        for x,z in ((300,334),(482,310),(483,230)):
            boards=[p for p in self.parts if p.kind=='board' and p.low[0]<=x<=p.high[0] and p.low[2]<=z<=p.high[2]]
            self.assertTrue(boards,(x,z))
            self.assertTrue(all(p.low[1]>13 for p in boards))

    def test_temple_and_walkway_have_distinct_footprints_and_supports(self):
        for part in self.parts:
            if part.owner=='temple':
                self.assertGreaterEqual(part.low[0],398.)
                self.assertLessEqual(part.high[0],562.)
                self.assertLessEqual(part.high[2],280.)
            elif part.owner=='bridge':
                self.assertLessEqual(part.high[1],16.)
                self.assertGreaterEqual(part.low[2],296.)
        # No leftover boards or invisible walkable forecourt beside the door.
        for x,z in ((392,240),(568,240),(432,292),(536,292),(504,312)):
            self.assertFalse(camera_tests.can_walk(self.tm,x,z))
            self.assertFalse(any(p.kind in ('board','tread') and p.low[0]<=x<p.high[0]
                                 and p.low[2]<=z<p.high[2] for p in self.parts))

    def test_stair_geometry_matches_height_and_both_routes_are_walkable(self):
        for stairs in structure.STAIRS:
            heights=[stairs.bottom]
            for bounds,top in stairs.treads():
                x0,z0,x1,z1=bounds;x=(x0+x1)/2;z=(z0+z1)/2
                self.assertTrue(camera_tests.can_walk(self.tm,x,z))
                self.assertAlmostEqual(structure.floor_height(self.tm,x,z),top)
                self.assertTrue(any(p.kind=='tread' and p.low[0]<=x<=p.high[0]
                                    and p.low[2]<=z<=p.high[2] and abs(p.high[1]-top)<1e-6 for p in self.parts))
                heights.append(top)
            self.assertAlmostEqual(heights[-1],stairs.top)
            self.assertTrue(all(0<b-a<=3 for a,b in zip(heights,heights[1:])))

    def test_preparing_3d_layout_does_not_change_original_2d_arena(self):
        source=camera_tests.TempleWalkabilityTests.source_arena
        before=copy.deepcopy(source)
        structure.prepare(source)
        self.assertEqual(source,before)


if __name__=='__main__':unittest.main()
