"""Reference checks for complete native visibility construction and wind poses."""
import math
from pathlib import Path
import random
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import g_light_visibility as lv
import g_tree_animation as rig
import g_effects
from c_port.scene_reference import Kernels,PackedGeometry,light_data,wind_data,part_data

def run():
    rng=random.Random(408315);native=Kernels();rays=0;poses=0
    try:
        for scene in range(10):
            tm=dict(map_width=24,map_height=18,tile_width=16,tile_height=16,
                    tiles=[dict(index=int(rng.random()<.14),shape_index=rng.randrange(5)) for _ in range(24*18)])
            grid=lv.build_light_collision_grid(tm,{1});packed=PackedGeometry(grid)
            for sample in range(30):
                position=dict(x=rng.uniform(-16,400),y=rng.uniform(-16,300))
                if sample%5==0:position=dict(x=sample*16.,y=128.)
                angle=rng.uniform(-math.pi,math.pi)
                light=dict(type='spot' if sample%2 else 'point',radius=rng.uniform(1,320),
                           direction=dict(x=math.cos(angle),y=math.sin(angle)),outer_angle=rng.uniform(1,80),
                           visibility_ray_count=rng.choice((1,16,64,128)),visibility_max_rays=512)
                if sample==0:light.update(outer_angle=0.,type='spot',visibility_ray_count=512)
                if sample==1:light.update(radius=0.)
                expected=lv.build_light_visibility_polygon_dda(light,position,grid)
                actual=native.visibility(packed,light_data(light,position))
                for key,field in (('ray_count','count'),('baseline_ray_count','baseline_count'),
                                  ('corner_candidate_count','corner_count'),('adaptive_rays_added','adaptive_count'),
                                  ('dda_tile_steps','tile_steps'),('max_dda_tile_steps_for_one_ray','max_tile_steps')):
                    assert expected[key]==getattr(actual,field),(scene,sample,key,expected[key],getattr(actual,field))
                assert set(expected['hit_tile_ids'])==set(actual.hit_tiles[:actual.hit_count]),(scene,sample,'hit tiles')
                for key,points in (('polygon',actual.polygon),('unbiased_polygon',actual.unbiased)):
                    for i,p in enumerate(expected[key]):
                        assert abs(p['x']-points[i].x)<1.e-8 and abs(p['y']-points[i].y)<1.e-8,(scene,sample,key,i,p,(points[i].x,points[i].y))
                rays+=actual.count
        for sample in range(2500):
            w=g_effects.make_wind_profile();w.update(tree_seed=rng.randrange(-800,800),tree_irregular=bool(sample%3),
                strength=rng.uniform(0,20),gust_strength=rng.uniform(0,10),vertical_flutter=rng.uniform(0,2))
            if sample%100==0:w['tree_seed']=2147483647
            if sample%100==1:w['tree_seed']=-2147483648
            w['direction']=dict(x=rng.uniform(-1,1),y=rng.uniform(-1,1))
            world=(rng.uniform(-1000,1000),rng.uniform(-1000,1000));time=rng.uniform(-1000,10000)
            p=rig.PARTS[sample%len(rig.PARTS)];angle,bend=rig.motion(p,time,w,world)
            actual=native.pose(part_data(p),wind_data(w),world,time,strips=bool(sample%2))
            assert abs(actual.angle-angle)<1.e-11 and abs(actual.bend-bend)<1.e-9,(sample,'motion',actual.angle,angle)
            wind=rig.irregular_wind(w,world,time) if w['tree_irregular'] else g_effects.sample_wind(w,*world,time)
            strength=min(1.5,math.hypot(wind['x'],wind['y'])/8.)*p['exposure']
            phase=p['phase']+world[0]*.019+world[1]*.013+w['tree_seed']*.37;t=time-p['lag']
            expected=(math.cos(angle),math.sin(angle),bend,strength,*p['pivot'],max(1.,p['bounds'][3]-p['pivot'][1]),p['bend_gain'],
                (t*1.35+phase)%math.tau,(t*2.05+phase*.3)%math.tau,(t*1.6+phase+.8)%math.tau,phase%math.tau,
                float(not sample%2),0.,0.,0.)
            assert bytes(actual.deformation)==struct.pack('<16f',*expected),(sample,'GPU deformation')
            poses+=1
        assert not native.memory.frame.failures
        print(f'Native scene: 300 complete visibility polygons / {rays} rays and {poses} tree poses passed.')
        print(f'Frame arena peak: {native.memory.frame.peak} bytes; capacity failures: 0.')
    finally:native.close()

if __name__=='__main__':run()
