"""Lighting optimization equivalence and invalidation without a GPU context."""
import random
import unittest
from unittest.mock import patch
import g_graphics as graphics
import g_night as night
import g_light_visibility as visibility
from test_light_visibility import make_grid


class EntityLightOptimizationTests(unittest.TestCase):
    def test_batched_polygon_matches_scalar_edges_concavity_and_chunk_boundary(self):
        rng=random.Random(54)
        polygons=[[],[{'x':0.,'y':0.}],
                  [dict(x=x,y=y) for x,y in ((0,0),(30,0),(30,10),(10,10),(10,30),(0,30))],
                  [dict(x=x,y=y) for x,y in ((-2,-3),(20,15),(-15,24))]]
        points=[(rng.uniform(-40,40),rng.uniform(-40,40)) for _ in range(600)]
        points += [(0,0),(10,10),(30,5),(30.000001,5),(29.999999,5),(0,30)]
        for polygon in polygons:
            for shape in (polygon,list(reversed(polygon))):
                expected=[graphics.point_in_polygon(dict(x=x,y=y),shape) for x,y in points]
                self.assertEqual(graphics.points_in_polygon(points,shape).tolist(),expected)

    def fixtures(self):
        grid=make_grid([(3,2,0)],width=10,height=10)
        light=dict(type='point',enabled=True,position={'x':20.,'y':20.},radius=90.,falloff=1.5,intensity=2.)
        polygon=visibility.build_light_visibility_polygon_dda(light,light['position'],grid)['polygon']
        prepared=dict(id='lamp',light=light,world_position=light['position'],visibility_polygon=polygon,
                      casts_wall_shadows=True,affects_entities=True)
        items=[dict(source_id=str(i),base_world={'x':x,'y':y},bounds_world={'x':x-3,'y':y-8,'width':6.,'height':8.},
                    self_shadow={'mode':'none'}) for i,(x,y) in enumerate(((25.,25.),(42.,26.),(65.,48.)))]
        return grid,prepared,items

    def test_cached_flickering_light_matches_uncached_and_retains_geometry(self):
        grid,prepared,items=self.fixtures();assets={}
        graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
        graphics.prepare_entity_self_shadows(items,[prepared],[],grid)
        entry=prepared['_entity_samples'];points=entry['points'].copy()
        for intensity in (0.,.01,.4,2.,4.):
            prepared['light']['intensity']=intensity
            graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
            self.assertIs(prepared['_entity_samples'],entry)
            reference=dict(prepared);reference.pop('_entity_samples')
            for item in items:
                expected=graphics.get_prepared_light_strength_for_render_item(reference,item,grid)
                with patch.object(graphics,'prepared_light_reaches_point',side_effect=AssertionError('retested cached visibility')):
                    actual=graphics.get_prepared_light_strength_for_render_item(prepared,item,grid)
                self.assertAlmostEqual(actual,expected)
        self.assertEqual(entry['points'],points)

    def test_geometry_and_field_changes_invalidate_but_colour_does_not(self):
        grid,prepared,items=self.fixtures();assets={}
        def refresh():
            graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
            return prepared['_entity_samples']
        entry=refresh();prepared['light']['color']=[.1,.4,.9]
        self.assertIs(refresh(),entry)
        for change in (lambda:prepared['light'].update(radius=50.),
                       lambda:prepared['light'].update(render_position={'x':21.,'y':18.}),
                       lambda:prepared['light'].update(enabled=False),
                       lambda:grid.update(geometry_revision=grid.get('geometry_revision',0)+1),
                       lambda:prepared.update(visibility_polygon=list(prepared['visibility_polygon']))):
            entry=refresh();change();self.assertIsNot(refresh(),entry)
        graphics.prepare_entity_light_sample_caches([],grid,assets)
        self.assertFalse(assets['entity_light_sample_cache'])

    def test_moving_spot_keeps_conservative_overlap_live(self):
        grid,prepared,items=self.fixtures()
        prepared['light'].update(type='spot',direction={'x':1.,'y':0.},inner_angle=10.,outer_angle=20.)
        prepared['casts_wall_shadows']=False
        item=dict(bounds_world=dict(x=40.,y=18.,width=5.,height=4.))
        self.assertTrue(graphics.spot_light_conservatively_intersects_render_item(prepared,item))
        prepared['light']['direction']={'x':-1.,'y':0.}
        self.assertFalse(graphics.spot_light_conservatively_intersects_render_item(prepared,item))
        self.assertFalse(graphics.spot_light_conservatively_intersects_render_item(prepared,{}))

    def test_field_replacement_and_point_budget_do_not_leave_stale_samples(self):
        grid,prepared,items=self.fixtures();assets={}
        prepared['light'].update(type='top_down',_field=dict(origin=(0,0),width=100,height=100,values=bytes([255])*10000))
        prepared['casts_wall_shadows']=False
        graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
        entry=prepared['_entity_samples']
        self.assertEqual(graphics.get_prepared_light_strength_for_render_item(prepared,items[0],grid),2.)
        prepared['light']['_field']['values']=bytes(10000)
        graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
        self.assertIsNot(prepared['_entity_samples'],entry)
        self.assertEqual(graphics.get_prepared_light_strength_for_render_item(prepared,items[0],grid),0.)
        entry=prepared['_entity_samples'];entry['points']={i:0. for i in range(5000)}
        graphics.prepare_entity_light_sample_caches([prepared],grid,assets)
        self.assertFalse(entry['points'])

    def test_facade_irradiance_survives_flicker_and_rebuilds_on_motion(self):
        grid=make_grid(width=12,height=12)
        entry=dict(bounds=dict(x=40,y=20,width=24,height=32),receivers={})
        light=dict(type='point',position={'x':52.,'y':72.},height=25.,radius=100.,intensity=1.5,falloff=1.)
        prepared=dict(id='fire',light=light,world_position=light['position'])
        item={'_facade':entry};first=night.facade_receiver(prepared,item,grid);original=first['strength']
        pixels=first['image'].tobytes()
        for intensity in (0.,.3,3.):
            light['intensity']=intensity
            result=night.facade_receiver(prepared,item,grid)
            self.assertIs(result,first)
            self.assertEqual(result['image'].tobytes(),pixels)
            self.assertAlmostEqual(result['strength'],original*intensity/1.5)
        light['position']['x']+=12.
        self.assertIsNot(night.facade_receiver(prepared,item,grid),first)

    def test_only_overlapping_preceding_shapes_need_light_masks(self):
        def item(x,y,w=10,h=10):return dict(bounds_world=dict(x=x,y=y,width=w,height=h))
        items=[item(0,0),item(40,0),item(5,5),item(80,0)]
        self.assertEqual(graphics.entity_light_overlap_masks(items),[0,0,1,0])
        items[1].update(source='player',draw_data={'weapon_visible':True})
        masks=graphics.entity_light_overlap_masks(items)
        self.assertEqual(masks[1],1)
        self.assertTrue(masks[3] & 2)


if __name__=='__main__':unittest.main()
