"""CPU contracts for independent cloud births, local drift and gradual death."""
import dataclasses
from hashlib import sha256
import math
import json
import unittest
from unittest.mock import patch

import numpy as np

from g_huxin_canals_particles import (
    ARRIVAL_DURATION, CLEAR_START, CLEAR_DURATION, DURATION, ALPHA_CUTOFF,
    NEAR_CLEAR_START, NEAR_CLEAR_END, MIDDLE_CLEAR_START, MIDDLE_CLEAR_END,
    FAR_CLEAR_START, FAR_CLEAR_END,
    ATLAS_VARIANTS, CloudParticle, atlas_rect, build_particle_atlas,
    particle_schedule, particles_at, _arrival_clock, _arrival_time,
    building_frame_at,
)
from g_huxin_canals_direction import building_document,profile_from_document,DEFAULT_DIRECTION
from g_huxin_canals_targets import target_groups,target_group,coverage_bounds


class ParticleFieldTests(unittest.TestCase):
    def test_activation_is_empty_and_births_fade_in_gently(self):
        self.assertEqual(particles_at(0., 100.), ())
        self.assertEqual(particles_at(-1., 100.), ())
        peak_alpha = sum(p.alpha for p in particles_at(ARRIVAL_DURATION,100.))
        self.assertLess(sum(p.alpha for p in particles_at(.01,100.))/peak_alpha,1e-5)
        schedule = particle_schedule()
        self.assertEqual({s.wave for s in schedule}, set(range(6)))
        self.assertGreater(max(s.birth for s in schedule), 3.7)
        for s in schedule:
            self.assertGreater(s.opaque_at - s.birth,.5)
            self.assertLessEqual(s.opaque_at - s.birth,ARRIVAL_DURATION)
            self.assertLessEqual(s.opaque_at, ARRIVAL_DURATION)
        counts = [len(particles_at(t, 30.)) for t in (0., 1./3., 2./3., 4./3., 2., 8./3., ARRIVAL_DURATION)]
        self.assertTrue(all(a < b for a, b in zip(counts[:5], counts[1:6])))
        self.assertEqual(counts[-1], len(schedule))
        for wave in range(6):
            s = next(s for s in schedule if s.wave == wave)
            first = {p.id:p for p in particles_at(s.birth + .001, 30.)}.get(s.id)
            self.assertTrue(first is None or first.alpha < .00011)

    def test_arrival_keeps_adding_clouds_until_the_end_without_alpha_reversals(self):
        previous={}
        totals=[]
        for frame in range(1,round(ARRIVAL_DURATION*60)+1):
            current={p.id:p.alpha for p in particles_at(frame/60.,87.)}
            self.assertTrue(set(previous)<=set(current))
            for ident,alpha in previous.items():self.assertGreaterEqual(current[ident],alpha)
            totals.append(sum(current.values()))
            previous=current
        # Test the actual packet population; native coverage checks separately
        # guard against overlapping clouds visually saturating too early.
        self.assertLess(totals[59]/totals[-1],.03)
        self.assertLess(totals[119]/totals[-1],.12)
        self.assertLess(totals[179]/totals[-1],.3)
        self.assertGreater(len(particles_at(3.9,87.)),len(particles_at(3.,87.)))

    def test_arrival_clock_is_monotone_with_bounded_speed_and_smooth_crest(self):
        step = .0005
        times = np.arange(0., ARRIVAL_DURATION + step*.5, step)
        values = np.array([_arrival_clock(t) for t in times])
        rates = np.diff(values) / step
        self.assertEqual(values[0], 0.)
        self.assertEqual(values[-1], 4.)
        self.assertTrue(np.all(rates >= 0.))
        self.assertLess(float(rates.max()), 2.25)
        self.assertLess(float(rates[0]), .002)
        self.assertLess(float(rates[-1]), .002)
        # The old exponential remap accelerated to 99 raw seconds/second
        # before abruptly switching clocks. Both sides of every Hermite join
        # now have matching finite velocity, including the stationary crest.
        h = 1e-5
        for t in (1., 2., 3., 4., ARRIVAL_DURATION):
            before = (_arrival_clock(t)-_arrival_clock(t-h))/h
            after = (_arrival_clock(t+h)-_arrival_clock(t))/h
            self.assertLess(abs(before-after), .0001)
        for clock in np.linspace(0., 4., 81):
            self.assertAlmostEqual(_arrival_clock(_arrival_time(clock)), clock, places=11)

    def test_actual_cloud_alpha_rates_ease_into_an_exact_handoff_plateau(self):
        schedule = {s.id:s for s in particle_schedule()}
        previous = {}
        maximum_rate = crest_rate = 0.
        for frame in range(1,round(ARRIVAL_DURATION*120)+1):
            t = frame/120.
            current = {p.id:p.alpha for p in particles_at(t,87.)}
            for ident,alpha in current.items():
                rate = (alpha-previous.get(ident,0.))*120./schedule[ident].max_alpha
                self.assertGreaterEqual(rate, 0.)
                maximum_rate = max(maximum_rate,rate)
                if t >= ARRIVAL_DURATION-.25:crest_rate = max(crest_rate,rate)
            previous = current
        # A real card can no longer materialize almost completely in a few
        # frames, even if the scalar arrival clock itself looks continuous.
        self.assertLess(maximum_rate, 4.)
        self.assertLess(crest_rate, .025)
        peak = particles_at(ARRIVAL_DURATION,87.)
        for t in (ARRIVAL_DURATION,5.25,5.5,5.75,CLEAR_START):
            self.assertEqual(particles_at(t,87.),peak)
        before = {p.id:p.alpha for p in particles_at(CLEAR_START-.001,87.)}
        after = {p.id:p.alpha for p in particles_at(CLEAR_START+.001,87.)}
        self.assertEqual(set(before),set(after))
        self.assertLess(max(abs(after[i]-a) for i,a in before.items()),1e-5)

    def test_layout_is_deterministic_cached_and_immutable(self):
        a = particles_at(ARRIVAL_DURATION, 73.5)
        self.assertIs(a, particles_at(ARRIVAL_DURATION, 73.5))
        self.assertEqual(particles_at.cache_info().maxsize, 4)
        self.assertTrue(all(isinstance(p, CloudParticle) for p in a))
        self.assertEqual(len(a), len({p.id for p in a}))
        with self.assertRaises(dataclasses.FrozenInstanceError):a[0].alpha = 0.
        with self.assertRaises(dataclasses.FrozenInstanceError):particle_schedule()[0].birth = 100.

    def test_every_cloud_has_reached_its_authored_alpha_before_handoff(self):
        schedule = {s.id:s for s in particle_schedule()}
        a, b = particles_at(ARRIVAL_DURATION, 60.), particles_at(CLEAR_START, 60.)
        self.assertEqual(a, b)
        self.assertEqual(len(a), len(schedule))
        for p in a:self.assertAlmostEqual(p.alpha, schedule[p.id].max_alpha, places=12)
        self.assertEqual(DURATION, CLEAR_START + CLEAR_DURATION)
        self.assertEqual(DURATION, 46.)

    def test_birth_waves_are_interleaved_at_all_depths_not_concentric_fronts(self):
        schedule = {s.id:s for s in particle_schedule()}
        particles = particles_at(ARRIVAL_DURATION, 60.)
        for lo, hi in ((0., 10.), (10., 16.), (16., 32.), (32., 200.)):
            waves = {schedule[p.id].wave for p in particles if lo <= math.hypot(p.center[0],p.center[2]) < hi}
            self.assertEqual(waves, set(range(6)))
        self.assertGreaterEqual(min(s.clear_start for s in schedule.values()), CLEAR_START)
        self.assertLessEqual(max(s.clear_start for s in schedule.values()), FAR_CLEAR_START + .52)

    def test_depth_windows_finish_clearing_their_actual_particle_population(self):
        schedule = {s.id:s for s in particle_schedule()}
        windows = {'near':(NEAR_CLEAR_START,NEAR_CLEAR_END),
                   'middle':(MIDDLE_CLEAR_START,MIDDLE_CLEAR_END),
                   'far':(FAR_CLEAR_START,FAR_CLEAR_END)}
        self.assertEqual(windows,{'near':(6.,14.),'middle':(12.,22.),'far':(20.,32.)})
        for band,(start,end) in windows.items():
            members=[s for s in schedule.values() if s.band==band]
            self.assertTrue(members)
            for s in members:
                self.assertGreaterEqual(s.clear_start,start)
                self.assertLessEqual(s.clear_start,start+.52)
                self.assertEqual(s.clear_end,end)
                self.assertEqual(s.end,46.)
                expected='near' if s.radius<14. else 'middle' if s.radius<35. else 'far'
                self.assertEqual(s.band,expected)
            at_start={p.id:p.alpha for p in particles_at(start,60.)}
            at_end={p.id:p.alpha for p in particles_at(end,60.)}
            for s in members:
                self.assertAlmostEqual(at_start[s.id],s.max_alpha,places=12)
                self.assertLessEqual(at_end.get(s.id,0.)/s.max_alpha,.01)
            self.assertGreater(max(s.clear_start for s in members)-min(s.clear_start for s in members),.30)
        # Whole-scene populations retain near-first ordering, including the
        # two-second overlaps between neighbouring dominant clearing windows.
        for elapsed in (10.,14.,18.,22.,28.,32.,38.):
            actual={p.id:p.alpha for p in particles_at(elapsed,60.)}
            ratios=[sum(actual.get(s.id,0.)/s.max_alpha for s in schedule.values() if s.band==band)
                    /sum(s.band==band for s in schedule.values()) for band in windows]
            self.assertTrue(all(a<=b for a,b in zip(ratios,ratios[1:])),(elapsed,ratios))

    def test_complete_clearing_is_exactly_twice_as_long_as_the_approved_phases(self):
        # Golden alpha packets captured from V16, sampled with the same cloud
        # clock. Retiming t -> 6+2*(t-4) must preserve every particle, not only
        # stage endpoints: this catches unscaled onset, stagger or faint tail.
        goldens = (
            (6.2,2097,'05fda9e802fb455f04ea09564679add8192f870f126175af19b8671960aed1a3'),
            (7.,2097,'3f4d4ac7b921a3dc7bce7bfcd0628b9c6408bf27658546aee25fbda34b1f0491'),
            (10.,2097,'b11aa457a06a8533422b30f063b2470415f44f4ff2a87ef498e0fdc50d493423'),
            (14.,2097,'7ad30731c801ca254940fb474776dfe0f67ff2433d638bb44cb51c7e68d9a8ff'),
            (18.,2097,'5ad55bcd375d9c881396e1ab408b0407126ed45fa4b6b757da12545097fc255e'),
            (22.,2097,'08be051f428ef5c977600ba39f926e4f9b9cf3d7e501a960444c518ab9c7cef2'),
            (32.,2097,'9e8f735d0622676fa9c1f67a6d23600cf07ab44681e27e599d6bac42bb110068'),
            (38.,2038,'dde9df454c56c16cf18e5aade980905398c7c15d050d5c870fcbdc7e36d6930c'),
            (44.,221,'9c44321f94aa64f044f0b9b3adee47979f043147ed8374c45db03ebeb8d0613c'),
            (46.,0,'4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'),
        )
        for elapsed,count,digest in goldens:
            with self.subTest(elapsed=elapsed):
                packets=particles_at(elapsed,37.5)
                signature=json.dumps([(p.id,round(p.alpha,9)) for p in packets],separators=(',',':')).encode()
                self.assertEqual(len(packets),count)
                self.assertEqual(sha256(signature).hexdigest(),digest)

    def test_approved_peak_layout_and_density_are_byte_identical(self):
        packets=[dataclasses.asdict(p) for p in particles_at(ARRIVAL_DURATION,37.5)]
        encoded=json.dumps(packets,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(len(packets),2097)
        self.assertEqual(sha256(encoded).hexdigest(),
                         '35bc461cffd6c2c690dd8284271da77062369f931137f5419185f5f8f89acee4')

    def test_clouds_spawn_in_place_and_only_drift_locally(self):
        peak = {p.id:p for p in particles_at(ARRIVAL_DURATION, 60.)}
        for p in particles_at(ARRIVAL_DURATION/3., 60.):
            self.assertEqual(p.center, peak[p.id].center)
            self.assertEqual((p.width,p.height), (peak[p.id].width,peak[p.id].height))
        later = {p.id:p for p in particles_at(ARRIVAL_DURATION, 120.)}
        distances = [math.dist(a.center,later[a.id].center) for a in peak.values()]
        self.assertGreater(max(distances), .5)
        self.assertLess(max(distances), 2.2)
        for p in peak.values():
            if math.hypot(p.center[0],p.center[2]) < 16. and p.width <= 6.:
                self.assertLess(math.dist(p.center,later[p.id].center), .9)
            self.assertEqual((p.width,p.height), (later[p.id].width,later[p.id].height))

    def test_near_clouds_are_small_with_a_translucent_foreground(self):
        particles = particles_at(ARRIVAL_DURATION, 0.)
        self.assertGreater(len(particles), 1800);self.assertLess(len(particles), 2300)
        self.assertEqual({p.layer for p in particles}, {'wisp','bank','low','far'})
        wisps = [p for p in particles if p.layer == 'wisp']
        self.assertGreater(len(wisps), 100)
        for p in wisps:
            self.assertGreaterEqual(p.width,1.2);self.assertLessEqual(p.width,3.5)
            self.assertGreaterEqual(p.alpha,.12);self.assertLessEqual(p.alpha,.30)
            self.assertLess(p.variant,4)
        near = [p for p in particles if p.layer == 'bank' and math.hypot(p.center[0],p.center[2]) < 15.]
        self.assertGreater(len(near),1200)
        for p in near:
            self.assertGreaterEqual(p.width,4.);self.assertLessEqual(p.width,6.)
            self.assertGreaterEqual(p.height,4.);self.assertLessEqual(p.height,6.)
            self.assertLessEqual(p.alpha,.74);self.assertGreaterEqual(p.variant,4)
        self.assertGreater(max(p.center[1]+p.height/2 for p in near),15.)

    def test_small_low_banks_overlap_above_and_below_the_water(self):
        low = [p for p in particles_at(ARRIVAL_DURATION,31.) if p.layer == 'low']
        self.assertGreaterEqual(sum(p.center[1]-.5*p.height < -1.55 for p in low),96)
        self.assertGreaterEqual(sum(p.center[1] > .45 for p in low),96)
        for p in low:
            self.assertLessEqual(p.width,6.);self.assertLessEqual(p.height,6.)
            self.assertGreater(p.center[1]+p.height/2,.8)
        edge = [p for p in low if p.width <= 4.5 and p.height <= 3.4
                and math.hypot(p.center[0],p.center[2]) < 7.3 and p.center[1] > .5]
        self.assertGreaterEqual(len(edge),96)
        for i in range(64):
            angle=math.tau*i/64;overlaps=0
            for p in low:
                a=math.atan2(p.center[2],p.center[0])
                delta=math.atan2(math.sin(a-angle),math.cos(a-angle))
                if abs(delta)<math.atan2(p.width/2,math.hypot(p.center[0],p.center[2])):overlaps+=1
            self.assertGreaterEqual(overlaps,10)

    def test_fade_has_a_gentle_onset_and_a_progressively_slower_tail(self):
        chosen=[next(s for s in particle_schedule() if s.layer==kind) for kind in ('wisp','bank','low','far')]
        for s in chosen:
            span=s.clear_end-s.clear_start
            alphas=[]
            for age in (0.,.001,span*.25,span*.5,span*.75,span):
                packet={p.id:p for p in particles_at(s.clear_start+age,40.)}
                alphas.append(packet[s.id].alpha)
            self.assertAlmostEqual(alphas[0],s.max_alpha,places=12)
            self.assertLess((alphas[0]-alphas[1])/s.max_alpha,.00001)
            self.assertTrue(all(a>b for a,b in zip(alphas,alphas[1:])))
            self.assertGreater(alphas[2]-alphas[3],alphas[3]-alphas[4])
            self.assertGreater(alphas[3]-alphas[4],alphas[4]-alphas[5])
            self.assertLessEqual(alphas[-1]/s.max_alpha,.01)
        # The entire tail is doubled too. Very faint cards remain two seconds
        # before the endpoint, without a final visible truncation.
        traces=particles_at(DURATION-2.,76.)
        self.assertTrue(traces)
        self.assertLess(max(p.alpha for p in traces),.00025)
        self.assertEqual(particles_at(DURATION,20.),())
        self.assertEqual(particles_at(DURATION+100.,20.),())

    def test_particles_are_removed_only_at_negligible_alpha(self):
        previous={p.id:p for p in particles_at(ARRIVAL_DURATION,40.)}
        self.assertTrue(previous)
        removed=0
        for tick in range(int(ARRIVAL_DURATION*4)+1,int(DURATION*4)+1):
            current={p.id:p for p in particles_at(tick*.25,40.)}
            self.assertTrue(set(current)<=set(previous))
            for ident,p in current.items():
                self.assertGreater(p.alpha,ALPHA_CUTOFF)
                self.assertLessEqual(p.alpha,previous[ident].alpha)
            for ident in set(previous)-set(current):
                # Even a quarter second before removal, a card contributes
                # less than one sixteenth of an eight-bit alpha step. Later
                # horizon starts must still finish without a visible pop.
                self.assertLess(previous[ident].alpha,1./4096.)
                removed+=1
            previous=current
        self.assertFalse(previous);self.assertEqual(removed,len(particle_schedule()))

    def test_sampling_is_independent_of_frame_rate_and_player_history(self):
        expected=particles_at(9.75,101.25)
        for t in (0.,.1,3.,30.,600.,1.):particles_at(t,t*2.)
        self.assertEqual(expected,particles_at(9.75,101.25))
        for elapsed in (.1,5.,6.,14.,22.,32.,44.):
            for p in particles_at(elapsed,212.):
                self.assertTrue(all(math.isfinite(v) for v in (*p.center,p.width,p.height,p.rotation,p.alpha)))
                self.assertGreater(p.width,0.);self.assertGreater(p.height,0.)
                self.assertGreater(p.alpha,ALPHA_CUTOFF);self.assertLessEqual(p.alpha,1.)
                self.assertIn(p.variant,range(ATLAS_VARIANTS))
        for elapsed,clock in ((math.nan,0.),(0.,math.inf),(math.inf,1.)):
            with self.assertRaises(ValueError):particles_at(elapsed,clock)


class ParticleAtlasTests(unittest.TestCase):
    def test_atlas_has_eight_distinct_original_tiles_and_zero_alpha_borders(self):
        data, width, height = build_particle_atlas()
        self.assertEqual((width, height), (256, 128))
        self.assertEqual(sha256(data).hexdigest(), '4a89bd1bc8e9a3ad23c16043183466de6fa1443e32f064da7aa3437fd3ac83a4')
        self.assertEqual(len(data), width * height * 4)
        atlas = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
        signatures = set()
        means = []
        for variant in range(8):
            x, y, w, h = atlas_rect(variant)
            tile = atlas[y:y + h, x:x + w]
            alpha = tile[:, :, 3]
            self.assertEqual(int(alpha[:2].max()), 0)
            self.assertEqual(int(alpha[-2:].max()), 0)
            self.assertEqual(int(alpha[:, :2].max()), 0)
            self.assertEqual(int(alpha[:, -2:].max()), 0)
            self.assertGreater(np.count_nonzero(alpha), 1200)
            self.assertGreater(len(np.unique(alpha)), 80)
            self.assertTrue(np.array_equal(tile[:, :, 0], tile[:, :, 1]))
            self.assertTrue(np.array_equal(tile[:, :, 1], tile[:, :, 2]))
            self.assertEqual(int(tile[:, :, 0].min()), 90)
            self.assertLessEqual(int(tile[:, :, 0].max()), 245)
            self.assertGreaterEqual(int(tile[:, :, 0].max())-int(tile[:, :, 0].min()), 124)
            self.assertLessEqual(len(np.unique(tile[:, :, 0])), 6)
            signatures.add(tile.tobytes());means.append(float(alpha.mean()))
        self.assertEqual(len(signatures), 8)
        self.assertGreater(np.mean(means[4:]), np.mean(means[:4]) * 1.6)

    def test_atlas_is_repeatable_and_supports_other_low_res_tile_sizes(self):
        first = build_particle_atlas()
        build_particle_atlas.cache_clear()
        self.assertEqual(first, build_particle_atlas())
        data, width, height = build_particle_atlas(32)
        self.assertEqual((width, height), (128, 64))
        self.assertEqual(len(data), width * height * 4)
        for tile_size in (True, 0, 15, 64.5):
            with self.assertRaises(ValueError):build_particle_atlas(tile_size)
        for variant in (True, -1, 8, .5):
            with self.assertRaises(ValueError):atlas_rect(variant)


class BuildingParticleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=building_document()
        cls.direction=profile_from_document(cls.document)

    def test_every_target_has_unique_stable_world_packets_and_an_exact_crest(self):
        a=particles_at(5.,37.5,self.direction)
        self.assertGreater(len(a),4000);self.assertLess(len(a),8000)
        self.assertIs(a,particles_at(5.,37.5,self.direction))
        self.assertEqual(a,particles_at(6.,37.5,self.direction))
        self.assertEqual({p.group_id for p in a},{target.id for target in target_groups()})
        self.assertEqual(len({p.id for p in a}),len(a))
        self.assertEqual(len(particle_schedule(self.direction)),len(a))
        expected=a
        particles_at(2.,89.,self.direction);particles_at(30.,3.,self.direction)
        self.assertEqual(expected,particles_at(5.,37.5,self.direction))
        # All packets, including IDs and positions, serialize without a
        # runtime-specific object, camera reference or GPU dependency.
        json.dumps([p._asdict() for p in a])
        with self.assertRaises(AttributeError):a[0].alpha=0.
        self.assertEqual(particles_at(0.,37.5,self.direction),())
        self.assertEqual(particles_at(46.,37.5,self.direction),())
        self.assertEqual(particles_at(100.,37.5,self.direction),())

    def test_a_single_group_placement_edit_changes_only_that_group(self):
        ident='house-410';doc=building_document()
        doc['fog']['groups'][ident].update(offset=[1.25,-.5,2.],scale=1.4,opacity=.5)
        edited=profile_from_document(doc)
        before={p.id:p for p in particles_at(5.,71.,self.direction)}
        after={p.id:p for p in particles_at(5.,71.,edited)}
        self.assertEqual(set(before),set(after))
        center=target_group(ident).center
        for pid,a in before.items():
            b=after[pid]
            if a.group_id!=ident:self.assertEqual(a,b);continue
            expected=tuple(c+(v-c)*1.4+o for c,v,o in zip(center,a.center,(1.25,-.5,2.)))
            for x,y in zip(expected,b.center):self.assertAlmostEqual(x,y,places=11)
            self.assertAlmostEqual(b.width,a.width*1.4)
            self.assertAlmostEqual(b.height,a.height*1.4)
            self.assertAlmostEqual(b.alpha,a.alpha*.5)

    def test_a_single_reveal_edit_does_not_clear_other_houses(self):
        ident='house-410';doc=building_document()
        doc['fog']['groups'][ident].update(reveal_start=22.,reveal_end=32.)
        edited=profile_from_document(doc)
        before={p.id:p for p in particles_at(16.,71.,self.direction)}
        after={p.id:p for p in particles_at(16.,71.,edited)}
        self.assertEqual(set(before),set(after))
        changed=0
        for pid,a in before.items():
            if a.group_id!=ident:self.assertEqual(a,after[pid])
            else:
                self.assertGreater(after[pid].alpha,a.alpha*10.)
                changed+=1
        self.assertGreater(changed,50)

    def test_group_lifetimes_keep_handoff_covered_and_finish_with_a_faint_tail(self):
        schedule=particle_schedule(self.direction)
        self.assertTrue(all(s.clear_start>=6. for s in schedule))
        self.assertTrue(all(s.opaque_at<=5. for s in schedule))
        by_id={p.id:p for p in particles_at(5.,31.,self.direction)}
        # Sample representative houses on both arms and every non-house type.
        ids=('house-110','house-410','house-423','house-449','house-1000',
             'water-approach','quay-west-near','bridge-reverse','backdrop-east','foreground-wisps')
        for ident in ids:
            group=self.direction.group(ident)
            remaining={p.id:p for p in particles_at(group.reveal_end,31.,self.direction)}
            members=[p for p in by_id.values() if p.group_id==ident]
            self.assertTrue(members)
            self.assertLess(max(remaining[p.id].alpha/p.alpha if p.id in remaining else 0. for p in members),.01)
        final=particles_at(45.99,31.,self.direction)
        self.assertTrue(all(p.alpha<.0002 for p in final))

    def test_envelopes_are_outside_every_house_and_within_editor_bounds(self):
        packets=particles_at(5.,31.,self.direction)
        grouped={target.id:[] for target in target_groups()}
        for p in packets:grouped[p.group_id].append(p)
        for target in target_groups():
            bounds=coverage_bounds(target,self.direction.group(target.id))
            for p in grouped[target.id]:
                radius=.5*math.hypot(p.width,p.height)
                for axis in range(3):
                    self.assertGreaterEqual(p.center[axis]-radius,bounds[0][axis])
                    self.assertLessEqual(p.center[axis]+radius,bounds[1][axis])
            if target.kind!='house':continue
            cx,cy,cz=target.center;hx,hy,hz=target.half_extents
            members=grouped[target.id]
            self.assertTrue(any(p.center[0]<cx-hx for p in members))
            self.assertTrue(any(p.center[0]>cx+hx for p in members))
            self.assertTrue(any(p.center[2]<cz-hz for p in members))
            self.assertTrue(any(p.center[2]>cz+hz for p in members))
            self.assertTrue(any(p.center[1]>cy+hy for p in members))
        wisps=grouped['foreground-wisps']
        self.assertLess(len(wisps),60)
        self.assertTrue(all(p.alpha<=.2 and p.width<=3.5 for p in wisps))

    def test_retained_group_settings_cannot_change_legacy_bank_mode(self):
        doc=building_document();doc['fog']['mode']='banks'
        doc['fog']['groups']['house-110']['offset']=[2.,3.,4.]
        legacy=profile_from_document(doc)
        for t in (0.,2.,5.,6.,12.,22.,32.,45.,46.):
            self.assertEqual(particles_at(t,71.),particles_at(t,71.,legacy))

    def test_birth_and_crest_continuity_use_actual_per_card_alpha(self):
        schedule={s.id:s for s in particle_schedule(self.direction)}
        previous={};maximum=0.;late=0.
        for frame in range(1,151):
            t=frame/30.
            current={p.id:p.alpha for p in particles_at(t,77.,self.direction)}
            self.assertTrue(set(previous)<=set(current))
            for ident,alpha in current.items():
                rate=(alpha-previous.get(ident,0.))*30./schedule[ident].max_alpha
                self.assertGreaterEqual(rate,0.)
                maximum=max(maximum,rate)
                if t>=4.8:late=max(late,rate)
            previous=current
        self.assertLess(maximum,4.2)
        self.assertLess(late,.025)

    def test_array_frames_match_packets_and_share_each_time_sample(self):
        for elapsed in (0.,2.,5.,16.,32.,46.):
            frame=building_frame_at(elapsed,71.5,self.direction)
            packets=particles_at(elapsed,71.5,self.direction)
            self.assertIs(frame,building_frame_at(elapsed,71.5,self.direction))
            self.assertEqual(len(frame),len(packets))
            self.assertEqual(frame.centers.shape,(len(packets),3))
            self.assertEqual(frame.ids.dtype,np.dtype(np.int64))
            self.assertEqual(frame.group_ids.dtype,np.dtype(object))
            self.assertEqual(frame.layers.dtype,np.dtype(object))
            for field,attribute in (('ids','id'),('centers','center'),('widths','width'),
                                    ('heights','height'),('rotations','rotation'),('alphas','alpha'),
                                    ('variants','variant'),('group_ids','group_id'),('layers','layer')):
                actual=getattr(frame,field).tolist()
                expected=[getattr(p,attribute) for p in packets]
                if field=='centers':expected=[list(center) for center in expected]
                self.assertEqual(actual,expected)
        self.assertLessEqual(building_frame_at.cache_info().currsize,4)

    def test_array_frames_are_readonly_finite_and_do_not_construct_packets(self):
        with patch('g_huxin_canals_particles.BuildingCloudParticle',side_effect=AssertionError('packet allocation')):
            frame=building_frame_at(5.023,63.719,self.direction)
        self.assertGreater(len(frame),7000)
        for field in dataclasses.fields(frame):
            array=getattr(frame,field.name)
            self.assertFalse(array.flags.writeable)
            if array.dtype!=object:self.assertTrue(np.isfinite(array).all())
            with self.assertRaises(ValueError):array[0]=array[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):frame.ids=np.empty(0)
        self.assertTrue((frame.alphas>ALPHA_CUTOFF).all())
        self.assertTrue((frame.alphas<=1.).all())
        self.assertTrue((frame.widths>0.).all() and (frame.heights>0.).all())
        saved=frame.centers.copy()
        building_frame_at(6.1,100.,self.direction)
        np.testing.assert_array_equal(saved,frame.centers)

    def test_array_frame_empty_lifecycle_and_invalid_inputs(self):
        for elapsed in (-1.,0.,46.,200.):
            frame=building_frame_at(elapsed,17.,self.direction)
            self.assertEqual(len(frame),0)
            self.assertEqual(frame.centers.shape,(0,3))
            self.assertTrue(all(not getattr(frame,field.name).flags.writeable for field in dataclasses.fields(frame)))
        for elapsed,clock in ((float('nan'),1.),(1.,float('inf'))):
            with self.assertRaisesRegex(ValueError,'finite'):
                building_frame_at(elapsed,clock,self.direction)
        with self.assertRaisesRegex(ValueError,'buildings'):
            building_frame_at(5.,17.,DEFAULT_DIRECTION)


if __name__ == '__main__':unittest.main()
