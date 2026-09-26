"""Fixed tree shadow axes and aperture casters on both sides of a doorway."""
import math
from types import SimpleNamespace
import unittest

import g_graphics as graphics
import g_light_visibility as visibility
import g_night as night
import g_render_order as order
import g_tree_assets as packs
import g_update_and_render as game


class TreeShadowVolumeTests(unittest.TestCase):
    def test_physical_height_overrides_keep_their_projection(self):
        tree=dict(id=3,type='willow tree',position={'x':200.,'y':200.})
        assets={'tree_textures':{'3':SimpleNamespace(width=160,height=160)}}
        item=order.build_brain_render_item(3,tree,dict(tile_width=16,tile_height=16),assets)
        info=graphics.get_render_item_shadow_sprite_info(item,assets)
        for overrides in ({'mode':'grounded','cast_height':3.},{'elevation':12.}):
            quad=graphics.build_cinematic_shadow_quad(info,dict(item['shadow'],**overrides),{'x':160.,'y':200.},72.)
            self.assertNotIn('cards',quad)

    def test_all_tree_roots_and_world_axes_survive_a_full_light_orbit(self):
        for kind in packs.TREE_TYPES:
            for animated in (False, True):
                tree=dict(id=3,type=kind,position={'x':200.,'y':200.})
                texture=SimpleNamespace(width=160 if animated else 128,height=160 if animated else 128)
                assets={'tree_textures':{'3':texture}} if animated else {'textures':{packs.reference_name(kind):texture}}
                item=order.build_brain_render_item(3,tree,dict(tile_width=16,tile_height=16),assets)
                info=graphics.get_render_item_shadow_sprite_info(item,assets)
                for angle in range(0,360,15):
                    lamp={'x':200+80*math.cos(math.radians(angle)),'y':200+80*math.sin(math.radians(angle))}
                    quad=graphics.build_cinematic_shadow_quad(info,item['shadow'],lamp,22.)
                    self.assertAlmostEqual(sum(c['weight'] for c in quad['cards']),1.)
                    u,v=info['root_local']['x']/info['sprite_width'],info['root_local']['y']/info['sprite_height']
                    for card in quad['cards']:
                        # The artwork's root, not the centre of its canvas, stays fixed.
                        for axis in ('x','y'):
                            actual=(card['far_left'][axis]+u*(card['far_right'][axis]-card['far_left'][axis])
                                    +v*(card['near_left'][axis]-card['far_left'][axis]))
                            self.assertAlmostEqual(actual,200.,msg=(kind,animated,angle,axis))
                        dx=card['far_right']['x']-card['far_left']['x']
                        dy=card['far_right']['y']-card['far_left']['y']
                        self.assertTrue(abs(dx)<1e-6 or abs(dy)<1e-6,'shadow card rotates with light')
                self.assertNotIn('projection',tree['shadow'],'runtime default mutated authored data')


class ApertureShadowTests(unittest.TestCase):
    def setUp(self):
        self.tm=game.make_tile_map(20,20,16,16)
        self.grid=visibility.build_light_collision_grid(self.tm,{3})
        self.obj=night.make_facade({'x':104.,'y':96.},'pierced_door')
        self.bounds=night.facade_bounds(self.obj,self.tm)
        self.source=dict(position={'x':104.,'y':68.},height=72.,intensity=1.,enabled=True)
        _,holes=night.facade_art(self.obj,True)
        image,origin=night.aperture_field(self.obj,holes,self.bounds,self.source,self.grid)
        self.light=dict(type='top_down',intensity=1.,_field=dict(origin=origin,width=image.width,height=image.height,values=image.tobytes()),
                        _aperture_caster=night.aperture_caster(self.obj,self.bounds,self.source,self.grid))

    def test_caster_crosses_threshold_without_lighting_the_indoor_floor_field(self):
        values=[]
        for y in (98.,97.,96.,95.,94.,90.):
            point={'x':104.,'y':y}
            strength=night.shadow_caster_strength(self.light,point)
            self.assertGreater(strength,.8)
            values.append(strength)
            if y<96.:
                self.assertEqual(visibility.get_unoccluded_light_strength_at_world_point(self.light,point,self.grid),0.)
        self.assertLess(max(abs(a-b) for a,b in zip(values,values[1:])),.02)

    def test_interior_partition_blocks_the_extended_caster(self):
        for x in range(20):self.tm['tiles'][5*20+x]['index']=3
        grid=visibility.build_light_collision_grid(self.tm,{3})
        self.light['_aperture_caster']=night.aperture_caster(self.obj,self.bounds,self.source,grid)
        self.assertEqual(night.shadow_caster_strength(self.light,{'x':104.,'y':94.}),0.)

    def test_disabled_lamp_cannot_cast_from_inside(self):
        self.light['_aperture_caster']['source']['enabled']=False
        self.assertEqual(night.shadow_caster_strength(self.light,{'x':104.,'y':94.}),0.)


if __name__=='__main__':unittest.main()
