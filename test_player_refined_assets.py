"""Compatibility of the independent player export with the game's rig and gun."""
from io import BytesIO
import json
from pathlib import Path
import struct
import unittest

import numpy as np
from PIL import Image
from test_temple_living import accessor

ROOT=Path(__file__).resolve().parent


def glb(path):
    raw=path.read_bytes();magic,version,size=struct.unpack_from('<III',raw)
    if (magic,version,size)!=(0x46546c67,2,len(raw)):raise ValueError('Invalid GLB')
    n,kind=struct.unpack_from('<II',raw,12)
    if kind!=0x4e4f534a:raise ValueError('Missing GLB JSON')
    doc=json.loads(raw[20:20+n]);length,kind=struct.unpack_from('<II',raw,20+n)
    if kind!=0x004e4942:raise ValueError('Missing GLB binary')
    return doc,raw[28+n:28+n+length]


def joints(document):return [document['nodes'][i]['name'] for i in document['skins'][0]['joints']]


def animation_channel(doc,binary,clip,bone,path):
    animation=next(a for a in doc['animations'] if a['name']==clip)
    channel=next(c for c in animation['channels'] if doc['nodes'][c['target']['node']]['name']==bone and c['target']['path']==path)
    sampler=animation['samplers'][channel['sampler']]
    return accessor(doc,binary,sampler['input']),accessor(doc,binary,sampler['output'])


class RefinedPlayerAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.old_data=glb(ROOT/'art'/'temple'/'combat'/'player.glb')
        cls.gun,cls.gun_data=glb(ROOT/'art'/'temple'/'combat'/'pistol.glb')
        cls.new,cls.new_data=glb(ROOT/'art'/'temple'/'player_refined'/'player.glb')

    def test_combat_hierarchy_keeps_only_the_intended_arm_proportion_changes(self):
        self.assertEqual(joints(self.old),joints(self.new));self.assertEqual(joints(self.gun),joints(self.new))
        self.assertEqual(len(joints(self.new)),15)
        original=accessor(self.old,self.old_data,self.old['skins'][0]['inverseBindMatrices'])
        pistol=accessor(self.gun,self.gun_data,self.gun['skins'][0]['inverseBindMatrices'])
        actual=accessor(self.new,self.new_data,self.new['skins'][0]['inverseBindMatrices'])
        np.testing.assert_allclose(original,pistol,atol=1e-5)
        names=joints(self.new)
        rest={}
        old_rest={}
        for i,name in enumerate(names):
            if name not in ('forearm.L','forearm.R','hand.L','hand.R'):
                np.testing.assert_allclose(actual[i],original[i],atol=1e-5)
            old_rest[name]=np.linalg.inv(original[i].reshape(4,4,order='F'))
            rest[name]=np.linalg.inv(actual[i].reshape(4,4,order='F'))
            np.testing.assert_allclose(rest[name][:3,:3],old_rest[name][:3,:3],atol=1e-5)
        for side in ('L','R'):
            for a,b in (('arm','forearm'),('forearm','hand')):
                old_length=np.linalg.norm(old_rest[a+'.'+side][:3,3]-old_rest[b+'.'+side][:3,3])
                new_length=np.linalg.norm(rest[a+'.'+side][:3,3]-rest[b+'.'+side][:3,3])
                self.assertAlmostEqual(float(new_length/old_length),.91,places=5)
        old_clips={a['name'] for a in self.old['animations']}
        self.assertEqual({a['name'] for a in self.new['animations']},old_clips)
        manifest=json.loads((ROOT/'art'/'temple'/'player_refined'/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['player']['clips']),old_clips)

    def test_refined_skin_is_weighted_and_texture_remains_era_appropriate(self):
        total=0
        for mesh in self.new['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes'];weights=accessor(self.new,self.new_data,attrs['WEIGHTS_0'])
                indices=accessor(self.new,self.new_data,attrs['JOINTS_0'])
                np.testing.assert_allclose(weights.sum(axis=1),1.,atol=1e-5)
                self.assertLess(int(indices.max()),15);self.assertTrue(np.all(weights>=0))
                total+=len(accessor(self.new,self.new_data,primitive['indices']))//3
        self.assertGreater(total,2930);self.assertLess(total,15000)
        image=self.new['images'][0];view=self.new['bufferViews'][image['bufferView']]
        start=view.get('byteOffset',0)
        with Image.open(BytesIO(self.new_data[start:start+view['byteLength']])) as atlas:
            self.assertEqual(atlas.size,(256,256))

    def test_accepted_locomotion_is_preserved_on_refined_model(self):
        for clip in ('idle','walk','run','walk_back','turn_left','turn_right'):
            animation=next(a for a in self.old['animations'] if a['name']==clip)
            for channel in animation['channels']:
                bone=self.old['nodes'][channel['target']['node']]['name']
                path=channel['target']['path']
                old_t,old=animation_channel(self.old,self.old_data,clip,bone,path)
                new_t,new=animation_channel(self.new,self.new_data,clip,bone,path)
                np.testing.assert_allclose(old_t,new_t,atol=1e-5)
                if path=='rotation':
                    # Quaternions q and -q represent the same pose.
                    similarity=np.abs(np.sum(old*new,axis=1)/(np.linalg.norm(old,axis=1)*np.linalg.norm(new,axis=1)))
                    np.testing.assert_allclose(similarity,1.,atol=1e-5,err_msg=clip+' '+bone)
                else:
                    offset=np.zeros(old.shape[1])
                    if path=='translation' and bone.startswith(('forearm.','hand.')):
                        old_node=next(n for n in self.old['nodes'] if n.get('name')==bone)
                        new_node=next(n for n in self.new['nodes'] if n.get('name')==bone)
                        offset=np.array(new_node.get('translation',[0,0,0]))-np.array(old_node.get('translation',[0,0,0]))
                    np.testing.assert_allclose(new,old+offset,atol=1e-5,err_msg=clip+' '+bone)

    def test_trousers_have_one_connected_seat_and_both_legs(self):
        # glTF splits vertices at UV/normal seams. Rejoin coincident positions
        # before asking whether the two legs share a continuous cloth surface.
        locations={};parents=[];influences=[]
        def root(i):
            while parents[i]!=i:
                parents[i]=parents[parents[i]];i=parents[i]
            return i
        names=joints(self.new)
        for mesh in self.new['meshes']:
            for primitive in mesh['primitives']:
                attrs=primitive['attributes']
                positions=accessor(self.new,self.new_data,attrs['POSITION'])
                bones=accessor(self.new,self.new_data,attrs['JOINTS_0'])
                weights=accessor(self.new,self.new_data,attrs['WEIGHTS_0'])
                ids=[]
                for position,js,ws in zip(positions,bones,weights):
                    key=tuple(np.rint(position*10000).astype(int))
                    if key not in locations:
                        locations[key]=len(parents);parents.append(len(parents));influences.append(set())
                    i=locations[key];ids.append(i)
                    influences[i].update(names[int(j)] for j,w in zip(js,ws) if w>.75)
                triangles=accessor(self.new,self.new_data,primitive['indices']).reshape(-1,3)
                for a,b,c in triangles:
                    first=root(ids[a]);parents[root(ids[b])]=first;parents[root(ids[c])]=first
        components={}
        for i,bones in enumerate(influences):components.setdefault(root(i),set()).update(bones)
        required={'thigh.L','thigh.R','shin.L','shin.R'}
        self.assertTrue(any(required<=bones for bones in components.values()),
                        'The trouser seat and both legs must share one surface')

    def test_weapon_aim_and_recoil_are_preserved(self):
        for clip,bone in (('aim','arm.R'),('aim','hand.R'),('recoil','forearm.R')):
            old_t,old=animation_channel(self.old,self.old_data,clip,bone,'rotation')
            new_t,new=animation_channel(self.new,self.new_data,clip,bone,'rotation')
            np.testing.assert_allclose(old_t,new_t,atol=1e-5)
            dot=np.abs(np.sum(old*new,axis=1)/(np.linalg.norm(old,axis=1)*np.linalg.norm(new,axis=1)))
            np.testing.assert_allclose(dot,1.,atol=1e-5)


if __name__=='__main__':unittest.main()
