"""Semantic ownership after an exact mesh ray hit; no window or audio needed."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import codex_scene_objects as objects


def hit(model, position, **fields):
    return dict(model_name=model,asset_path='art/temple/huxin_canals/'+model+'.glb',
        instance_id=model,hit_position=list(position),hit_normal=[0,1,0],
        bounds={'min':[-100,-3,-100],'max':[100,20,200]},
        transform=list(objects._IDENTITY),metadata={},mesh_index=0,**fields)


class SemanticObjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=objects._manifest('huxin_canals')
        cls.houses={h['seed']:h for h in cls.manifest['houses']}

    def resolve(self, model, point):
        return objects.resolve_hit('huxin_canals',hit(model,point))

    def test_near_and_distant_houses_have_stable_authored_locators(self):
        for seed in (110,133,249,1901,2530):
            house=self.houses[seed]
            point=[house['center'][0],house['center'][1]+1.4,house['center'][2]]
            value=self.resolve('canal_interiors',point)
            self.assertEqual(value['id'],'huxin_canals/house-'+str(seed))
            self.assertEqual(value['source']['seed'],seed)
            self.assertEqual(value['source']['file'],'g_huxin_canals_layout.py' if seed<1000 else 'build_huxin_canals.py')
            self.assertIn('canals_housekit',value['source']['generator'])
            self.assertLessEqual(value['bounds']['min'][1],house['foundation_bottom'])
            self.assertGreater(value['bounds']['max'][1],house['center'][1]+house['height'])

    def test_water_ground_and_below_foundation_do_not_become_houses(self):
        house=self.houses[110];x,_,z=house['center']
        for model,point in (('canal_water',(x,-1.55,z)),('canal_ground',(x,.325,z)),
                            ('canal_masonry',(x,-3.0,z)),('canal_masonry',(x,-1.0,z))):
            self.assertEqual(self.resolve(model,point),{})
        # A real foundation perimeter is part of its house, unlike the empty
        # volume below the room. Use the same ground shear as the builder.
        from g_huxin_canals_layout import HOUSE_SPECS,transform
        spec=next(s for s in HOUSE_SPECS if s['seed']==110)
        px,pz=transform(spec,spec['width']/2,0.)
        self.assertEqual(self.resolve('canal_masonry',(px,-1.,pz))['house_seed'],110)

    def test_all_front_and_rear_flights_resolve_their_actual_treads(self):
        for stair in self.manifest['washing_steps']:
            for i in (0,len(stair['treads'])-1):
                tread=stair['treads'][i]
                value=self.resolve('canal_masonry',tread['center'])
                self.assertEqual(value['id'],'huxin_canals/'+stair['id'])
                self.assertEqual(value['kind'],'stairs')
                self.assertEqual(value['tread_index'],i)
                self.assertEqual(value['surface_part'],'tread')
                self.assertEqual(value['house_seed'],stair.get('house_seed'))
            point=list(stair['treads'][0]['center']);point[1]=stair['bank_bottom']-.10
            self.assertNotEqual(self.resolve('canal_masonry',point).get('kind'),'stairs')

    def test_rear_apron_and_washing_landing_are_named_without_house_guessing(self):
        stair=next(s for s in self.manifest['washing_steps'] if s['id']=='rear-washing-133')
        polygon=stair['rear_apron'];center=(sum(p[0] for p in polygon)/len(polygon),.325,sum(p[1] for p in polygon)/len(polygon))
        value=self.resolve('canal_ground',center)
        self.assertEqual(value['id'],'huxin_canals/rear-washing-133')
        self.assertEqual(value['surface_part'],'rear landing')
        value=self.resolve('canal_masonry',stair['landing_geometry']['center'])
        self.assertEqual(value['id'],'huxin_canals/rear-washing-133')
        self.assertEqual(value['surface_part'],'washing landing')

    def test_stair_volume_does_not_capture_unrelated_batches(self):
        point=self.manifest['washing_steps'][0]['treads'][0]['center']
        self.assertEqual(self.resolve('canal_water',point),{})
        self.assertEqual(self.resolve('canal_roofs',point),{})

    def test_two_playable_and_seven_scenic_bridges(self):
        from g_huxin_canals_layout import BRIDGES,DECK
        for bridge in BRIDGES:
            point=((bridge['x0']+bridge['x1'])/2,DECK+bridge['rise'],bridge['z'])
            value=self.resolve('canal_bridges',point)
            self.assertEqual(value['kind'],'bridge')
            self.assertEqual(value['source']['definition'],'BRIDGES')
        for z in (-21.5,87.,126.,165.,-56.,-94.,-131.):
            value=self.resolve('canal_distant',(0.,.9,z))
            self.assertEqual(value['kind'],'bridge')
            self.assertEqual(value['source']['station_z'],z)
        self.assertEqual(self.resolve('canal_ground',(0.,.9,24.)),{})

    def test_individual_jars_and_troughs_precede_building_envelopes(self):
        from g_huxin_canals_layout import HOUSE_SPECS,transform
        house=next(s for s in HOUSE_SPECS if s['seed']==110)
        corner=transform(house,house['width']/2+.40,-house['depth']/2+.55)
        for i,(x,z) in enumerate(((-13.9,30.3),(13.9,42.),corner,(7.1,51.5))):
            value=self.resolve('canal_details',(x,.65,z))
            self.assertEqual(value['id'],'huxin_canals/rain-jar-'+str(i))
            self.assertEqual(value['kind'],'prop')
        self.assertEqual(self.resolve('canal_details',(-14.7,.65,34.))['id'],'huxin_canals/stone-trough-0')

    def test_pavilion_posts_lamps_and_causeway_keep_authored_ids(self):
        from g_huxin_canals import COLUMNS,LIGHTS
        for i,(x,z,r) in enumerate(COLUMNS):
            self.assertEqual(self.resolve('pavilion_posts',(x,2.,z))['id'],'huxin_canals/post-'+str(i))
        for i,(x,y,z) in enumerate(LIGHTS):
            self.assertEqual(self.resolve('lake_lamps',(x,y,z))['id'],'huxin_canals/lamp-'+str(i))
        self.assertEqual(self.resolve('pavilion_roofs',(2.,5.5,0.))['id'],'huxin_canals/pavilion')
        self.assertEqual(self.resolve('causeway',(-2.,.325,11.))['id'],'huxin_canals/causeway')
        self.assertEqual(self.resolve('pavilion_details',(90.,2.,90.)),{})
        self.assertEqual(objects.resolve_hit('huxin_moon',hit('pavilion_roofs',(2.,5.5,0.)))['id'],'huxin_moon/pavilion')

    def test_exact_hit_is_immutable_and_json_record_does_not_invent_triangle_id(self):
        source=hit('canal_interiors',self.houses[133]['center']);before=copy.deepcopy(source)
        value=objects.resolve_hit('huxin_canals',source)
        self.assertEqual(source,before)
        self.assertNotIn('triangle_index',value)
        self.assertNotIn('hit_position',value)
        json.dumps({**source,**value},allow_nan=False)

    def test_unknown_nonidentity_and_invalid_records_keep_precise_fallback(self):
        source=hit('canal_interiors',self.houses[133]['center'])
        self.assertEqual(objects.resolve_hit('bamboo',source),{})
        source['transform'][12]=10.
        self.assertEqual(objects.resolve_hit('huxin_canals',source),{})
        for point in ((math.nan,0,0),(0,math.inf,0),(0,0)):
            source=hit('canal_interiors',point)
            self.assertEqual(objects.resolve_hit('huxin_canals',source),{})
        source=hit('canal_interiors',self.houses[133]['center']);source['transform'][0]+=1e-7
        self.assertEqual(objects.resolve_hit('huxin_canals',source)['house_seed'],133)

    def test_manifest_cache_reads_lazily_and_invalidates_after_file_change(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(objects,'ROOT',Path(directory)):
            self.assertEqual(objects._manifest('huxin_canals'),{})
            file=Path(directory)/'art/temple/huxin_canals/canals_manifest.json'
            file.parent.mkdir(parents=True);file.write_text('{"version":5}',encoding='utf8')
            first=objects._manifest('huxin_canals')
            self.assertIs(first,objects._manifest('huxin_canals'))
            file.write_text('{"version":6,"updated":true}',encoding='utf8')
            self.assertEqual(objects._manifest('huxin_canals')['version'],6)


if __name__=='__main__':
    unittest.main()
