"""Compare like-for-like warm frames, keeping renderer-only figures separate."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent
CASES=('approach','walking','interior')

def stats(values):
    values=sorted(values)
    return dict(median=round(statistics.median(values),3),p95=round(values[math.ceil(.95*len(values))-1],3),
                p99=round(values[math.ceil(.99*len(values))-1],3),maximum=round(max(values),3),
                over_16_67_ms=sum(v>1000/60 for v in values),frames=len(values))

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',nargs='+',default=['artifacts/moonlit-water-temple/c-port-python-timings.json'])
    parser.add_argument('--game',nargs='+',default=['artifacts/moonlit-water-temple/c-port-game-timings.json'])
    parser.add_argument('--native',default='c_port/output/native-240.csv')
    args=parser.parse_args()
    result={}
    for key,files in (('python_game',args.python),('compiled_c_game',args.game)):
        frames=[row for file in files for row in json.loads(Path(file).read_text(encoding='utf8'))['frames']]
        result[key]={case:{metric:stats([row[metric] for row in frames if row['case']==case])
                          for metric in ('submit_ms','complete_ms')} for case in CASES}
    rows=list(csv.DictReader(Path(args.native).open()))
    result['native_renderer_only']={case:{metric:stats([float(row[metric]) for row in rows if int(row['case'])==index and row['measured']=='1'])
        for metric in ('submit_ms','complete_readback_ms','gpu_elapsed_ms')} for index,case in enumerate(CASES)}
    result['renderer_validation']=dict(frames=len(rows),pixel_mismatches=sum(row['pixel_match']!='1' for row in rows),
        native_rays=sum(int(row['rays']) for row in rows),native_ray_mismatches=sum(int(row['ray_errors']) for row in rows))
    parity=ROOT/'output'/'game-parity.json'
    if parity.exists():result['game_validation']=json.loads(parity.read_text())
    result['inputs']=dict(python=args.python,compiled_game=args.game,native_renderer=args.native)
    result['notes']=[
        'Complete game uses generated C for game modules, native C visibility/geometry, and the existing CPython/third-party runtime.',
        'Native renderer-only replays prepared rendering commands and recomputes visibility rays; excludes other scene preparation and gameplay.',
        'Complete timings include GPU readback cost; all figures exclude window presentation.',
        'Eight warmup frames per view in each run; fixed 1/60 simulation step; no FPS cap. Frame counts are in each distribution.',
        'GPU elapsed is a GL_TIME_ELAPSED query around native command execution; not a CPU submission timer.'
    ]
    (ROOT/'output'/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('| View | Python complete | C-compiled complete | Native renderer only |')
    print('| --- | ---: | ---: | ---: |')
    for case in CASES:
        a=result['python_game'][case]['complete_ms']['median']
        b=result['compiled_c_game'][case]['complete_ms']['median']
        c=result['native_renderer_only'][case]['complete_readback_ms']['median']
        print(f'| {case} | {a:.2f} ms | {b:.2f} ms | {c:.2f} ms |')
    print(json.dumps(result['renderer_validation']))

if __name__=='__main__':run()
