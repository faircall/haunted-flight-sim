"""Combat exports preserve accepted art and carry real, weighted motion clips."""
import json
from pathlib import Path
import struct
import unittest
import numpy as np
from test_temple_living import glb,accessor

ROOT=Path(__file__).resolve().parent


def combat_glb(name):
    data=(ROOT/'art'/'temple'/'combat'/(name+'.glb')).read_bytes()
    size,kind=struct.unpack_from('<II',data,12)
    assert kind==0x4E4F534A
    doc=json.loads(data[20:20+size]);start=20+size
    length,kind=struct.unpack_from('<II',data,start)
    assert kind==0x004E4942
    return doc,data[start+8:start+8+length]


class CombatAssetTests(unittest.TestCase):
    def test_player_mesh_and_accepted_locomotion_are_preserved(self):
        old,old_data=glb('player');new,new_data=combat_glb('player')
        a=old['meshes'][0]['primitives'][0];b=new['meshes'][0]['primitives'][0]
        for attribute in ('POSITION','NORMAL','TEXCOORD_0','JOINTS_0','WEIGHTS_0'):
            np.testing.assert_allclose(accessor(old,old_data,a['attributes'][attribute]),accessor(new,new_data,b['attributes'][attribute]),atol=1e-6)
        def channels(doc,binary,clip):
            animation=next(a for a in doc['animations'] if a['name']==clip)
            result={}
            for channel in animation['channels']:
                sampler=animation['samplers'][channel['sampler']]
                key=doc['nodes'][channel['target']['node']]['name'],channel['target']['path']
                result[key]=(accessor(doc,binary,sampler['input']),accessor(doc,binary,sampler['output']))
            return result
        for clip in ('idle','walk','run'):
            previous,current=channels(old,old_data,clip),channels(new,new_data,clip)
            self.assertEqual(previous.keys(),current.keys())
            for key in previous:
                for left,right in zip(previous[key],current[key]):np.testing.assert_allclose(left,right,atol=1e-5)

    def test_combat_assets_have_weights_compatible_skeletons_and_required_clips(self):
        player,_=combat_glb('player');pistol,_=combat_glb('pistol');enemy,data=combat_glb('redhead')
        def bones(document):return [document['nodes'][i]['name'] for i in document['skins'][0]['joints']]
        self.assertEqual(bones(player),bones(pistol));self.assertEqual(bones(player),bones(enemy))
        self.assertEqual(len(bones(enemy)),15)
        self.assertTrue({'turn_left','turn_right','walk_back','aim','aim_walk','aim_left','aim_right','aim_back','recoil','reload','hurt','death'}<={a['name'] for a in player['animations']})
        self.assertTrue({'enemy_idle','enemy_walk','enemy_attack','enemy_stagger','enemy_death'}<={a['name'] for a in enemy['animations']})
        primitive=enemy['meshes'][0]['primitives'][0]
        weights=accessor(enemy,data,primitive['attributes']['WEIGHTS_0'])
        np.testing.assert_allclose(weights.sum(axis=1),1,atol=1e-6)
        triangles=len(accessor(enemy,data,primitive['indices']))//3
        self.assertTrue(500<=triangles<=2000,triangles)
        positions=accessor(enemy,data,primitive['attributes']['POSITION'])
        self.assertAlmostEqual(positions[:,1].max(),21.6,places=4)
        self.assertLess(positions[:,1].max(),25.65)

    def test_turns_move_both_feet_without_root_translation_and_loop_cleanly(self):
        doc,data=combat_glb('player')
        for clip in ('turn_left','turn_right','walk_back'):
            animation=next(a for a in doc['animations'] if a['name']==clip)
            moving_feet=set()
            for channel in animation['channels']:
                name=doc['nodes'][channel['target']['node']]['name'];path=channel['target']['path']
                values=accessor(doc,data,animation['samplers'][channel['sampler']]['output'])
                np.testing.assert_allclose(values[0],values[-1],atol=1e-5)
                if clip.startswith('turn') and name=='root' and path=='translation':
                    np.testing.assert_allclose(values[:,(0,2)],0,atol=1e-5)
                if name.startswith('foot.') and path=='rotation' and np.max(np.ptp(values,axis=0))>.05:moving_feet.add(name)
            self.assertEqual(moving_feet,{'foot.L','foot.R'})


if __name__=='__main__':unittest.main()
