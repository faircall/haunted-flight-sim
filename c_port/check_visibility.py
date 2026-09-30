"""Compare the actual C kernel against the Python reference, including seams."""
import math
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import g_light_visibility as reference
from native_visibility import ray

def run():
    rng=random.Random(728311)
    shapes=bytearray(rng.choice((255,255,255,255,0,1,2,3,4)) for _ in range(35*27))
    grid=dict(map_width=35,map_height=27,tile_width=16,tile_height=16,shape_codes=shapes,
              shape_clip_planes=tuple(reference.tile_shape_clip_planes(i,16,16) for i in range(5)))
    queries=[]
    for index in range(16000):
        ox,oy=rng.uniform(-32,600),rng.uniform(-32,480)
        angle=rng.uniform(-math.pi,math.pi)
        if index%4==0:
            ox,oy=rng.randint(-1,36)*16.,rng.randint(-1,28)*16.
            angle=(index%8)*math.pi/4
        queries.append((ox,oy,math.cos(angle),math.sin(angle),rng.uniform(0,600),grid))
    start=time.perf_counter();expected=[reference.dda_first_light_hit_values(*q) for q in queries]
    python_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();actual=[ray(*q) for q in queries];native_ms=(time.perf_counter()-start)*1000
    for index,(a,b) in enumerate(zip(expected,actual)):
        assert (a[0] is None)==(b[0] is None) and a[1]==b[1],(index,queries[index][:5],a,b)
        if a[0] is not None:
            assert a[0][1:6]==b[0][1:6],(index,a,b)
            assert all(abs(a[0][i]-b[0][i])<1e-10 for i in (0,6,7)),(index,a,b)
    print(f'{len(queries)} C/Python ray comparisons passed; Python {python_ms:.2f} ms, C through ctypes {native_ms:.2f} ms.')

if __name__=='__main__':run()
