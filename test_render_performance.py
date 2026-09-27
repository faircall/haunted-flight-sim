"""Equivalence checks for structural rendering optimizations (no GPU required)."""
import copy
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import g_entity_batch as batch
import g_graphics as graphics
import g_render_order as order
import test_entity_light_optimization as light_tests


class RenderPerformanceTests(unittest.TestCase):
    def test_vectorized_visibility_overlap_matches_scalar(self):
        import math
        rng = random.Random(103)
        polygon = [dict(x=math.cos(a)*r, y=math.sin(a)*r)
                   for a,r in ((i*math.tau/80,rng.uniform(20,100)) for i in range(80))]
        for _ in range(300):
            rect = dict(x=rng.uniform(-120,120),y=rng.uniform(-120,120),
                        width=rng.choice((0.,1.e-6,16.,64.)),height=rng.choice((0.,16.,64.)))
            self.assertEqual(graphics.polygon_intersects_rectangle(polygon,rect),
                             graphics._polygon_intersects_rectangle_scalar(polygon,rect))

    def test_spatial_occlusion_matches_all_pairs_including_boundary_contacts(self):
        rng = random.Random(704)
        items = [dict(source_id=str(i), sort_y=rng.randrange(20), occludes_render_items=i%4 != 0,
                      bounds_world=dict(x=rng.randrange(-200,700), y=rng.randrange(-100,400),
                                        width=rng.choice((0,16,64,96,300)),height=rng.choice((0,16,64,128))))
                 for i in range(200)]
        result = order.build_render_occlusion_groups(items)
        for item in items:
            self.assertEqual(result['targets'].get(item['source_id'], []), order.find_occluders_for_item(items,item))

    def test_culling_keeps_edge_pixels_and_articulated_equipment(self):
        def item(x,y,**extra):return dict(dest_rect=dict(x=x,y=y,width=20,height=20),**extra)
        items = [item(-20,0),item(481,0),item(483,0),item(1,272),
                 item(600,0,draw_data={'cutout_rig_parts':[{}]}),item(600,0,source='player')]
        kept = order.visible_sprite_items(items, SimpleNamespace(x=.4,y=.4),480,270)
        self.assertEqual(kept, [items[i] for i in (0,1,4,5)])
        self.assertEqual(len(items),6) # callers retain offscreen shadow/reflection casters

    def test_atlas_mask_ignores_blocked_missing_lights_and_supports_bit_31(self):
        lights = [dict(id=str(i)) for i in range(32)]
        item = dict(self_shadow_summary={'per_light':[dict(light_id='0'),dict(light_id='3',blocked=True),
                                                     dict(light_id='31'),dict(light_id='missing')]})
        self.assertEqual(batch.light_mask(item, lights), -2147483647)
        self.assertFalse(batch.eligible(dict(source='player')))
        self.assertFalse(batch.eligible(dict(source='lake_prop',opacity=.5)))
        self.assertFalse(batch.eligible(dict(source='lake_prop',self_shadow={'mode':'directional_profiles'})))

    def test_plain_light_records_match_reference_after_moves_edits_and_dimming(self):
        grid, prepared, items = light_tests.EntityLightOptimizationTests().fixtures()
        assets = {}
        for change in (lambda:None, lambda:prepared['light'].update(intensity=.4),
                       lambda:items[0]['base_world'].update(x=38.),
                       lambda:items[1].update(excluded_light_owners=['torch']),
                       lambda:prepared['light'].update(effect_owner='torch'),
                       lambda:grid.update(geometry_revision=3)):
            change()
            graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
            expected = copy.deepcopy(items)
            reference = dict(prepared); reference.pop('_entity_samples', None)
            graphics.prepare_entity_self_shadows(expected,[reference],[],grid)
            graphics.prepare_entity_self_shadows(items,[prepared],[],grid)
            # A second call exercises cached records.
            graphics.prepare_entity_self_shadows(items,[prepared],[],grid)
            for actual, original in zip(items,expected):
                self.assertEqual(actual['self_shadow_summary'], original['self_shadow_summary'])

    def test_zero_strength_facade_skips_visibility_rays(self):
        import g_night
        from test_light_visibility import make_grid
        item={'_facade':dict(bounds=dict(x=1000,y=20,width=32,height=32),receivers={})}
        light=dict(type='point',position={'x':20.,'y':80.},radius=40.,intensity=1.)
        prepared=dict(id='lamp',light=light,world_position=light['position'])
        with patch.object(g_night,'source_columns',side_effect=AssertionError('unreachable wall traced')):
            self.assertEqual(g_night.facade_receiver(prepared,item,make_grid())['strength'],0.)

    def test_cached_record_tracks_moving_occluder_world_footprint_and_height(self):
        grid, light, items = light_tests.EntityLightOptimizationTests().fixtures()
        blocker = dict(source_id='blocker',visual_height=100.,
                       ground_footprint_world=dict(shape='rectangle',center=dict(x=22.,y=22.),size=dict(x=2.,y=2.)))
        graphics.prepare_entity_light_sample_caches([light],grid,{})
        def check(blocked):
            graphics.prepare_entity_self_shadows(items,[light],[blocker],grid)
            self.assertEqual(items[0]['self_shadow_summary']['per_light'][0]['blocked'],blocked)
        check(True);check(True)
        blocker['visual_height']=0.;check(False)
        blocker['visual_height']=100.;check(True)
        blocker['ground_footprint_world']['center']['x']=300.;check(False)


if __name__ == '__main__':unittest.main()
