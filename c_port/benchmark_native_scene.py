"""Validate and measure the arena-backed C stages; this is not full-game timing."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from c_port.summarize import stats, CASES

PORT = Path(__file__).resolve().parent
REPO = PORT.parent


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loops', type=int, default=3)
    parser.add_argument('--scenes', nargs='+', choices=('water', 'courtyard'),
                        default=['water', 'courtyard'])
    args = parser.parse_args()
    if not 1 <= args.loops <= 10000:
        parser.error('--loops must be between 1 and 10000')
    output = PORT / 'output'
    output.mkdir(exist_ok=True)
    report = dict(scope='C renderer plus native visibility construction and tree poses; '
                        'remaining preparation and gameplay are still produced offline.',
                  loops_in_one_process=args.loops, scenes={},
                  notes=[
                      'No Python interpreter is used by haunted_native.exe.',
                      'All measured frames exclude eight warmup frames per view and loop.',
                      'CPU submission and completion/readback exclude presentation, hashing and capture export.',
                      'Allocator audit covers executable and statically linked raylib; excludes external OS/GPU DLLs.',
                      'Presentation is audited separately; arenas and GPU resources are reused across loops.',
                      'Release uses explicit -O2, -DNDEBUG and -ffp-contract=off; no fast-math.',
                      'Do not compare these partial-pipeline timings directly against historical full-game results.',
                  ])
    for name in args.scenes:
        folder = PORT / 'data' / (name+'-native')
        fixture = folder / 'scene.hfc'
        manifest_path = folder / 'manifest.json'
        if not manifest_path.exists():
            parser.error(f'First export: python c_port/export_scene.py --native-scene --scene {name} --frames 240')
        manifest = json.loads(manifest_path.read_text(encoding='utf8'))
        if not manifest.get('native_scene'):
            parser.error(f'{folder} does not contain native preparation inputs')
        csv_path = output / f'arena-native-{name}.csv'
        log_path = output / f'arena-native-{name}.log'
        command = [str(PORT/'build/haunted_native.exe'), '--scene', str(fixture),
                   '--benchmark', '--hidden', '--loops', str(args.loops), '--output', str(csv_path)]
        with log_path.open('w', encoding='utf8') as log:
            result = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'Native validation failed; inspect {log_path}')
        with csv_path.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        expected_count = (manifest['frames']+manifest['warmup'])*3*args.loops
        if len(rows) != expected_count:
            raise RuntimeError(f'Incomplete route: {len(rows)} / {expected_count} frames')
        log = log_path.read_text(encoding='utf8')
        memory = re.search(r'Arenas: persistent=(\d+), assets=(\d+), frame peak=(\d+) bytes; failures=(\d+)', log)
        prepared = re.search(r'Native preparation: polygons=(\d+), fans=(\d+), tree poses=(\d+), errors=(\d+)', log)
        presentation = re.search(r'Presentation heap audit: allocations=(\d+)', log)
        if not all((memory, prepared, presentation)):
            raise RuntimeError('Native executable is outdated; rebuild with c_port/build.cmd')
        checked = dict(frames=len(rows), pixel_mismatches=sum(row['pixel_match']!='1' for row in rows),
                       ray_errors=sum(int(row['ray_errors']) for row in rows),
                       heap_allocations=sum(int(row['heap_allocations']) for row in rows),
                       requested_heap_bytes=sum(int(row['heap_bytes']) for row in rows),
                       presentation_heap_allocations=int(presentation[1]),
                       preparation=dict(zip(('polygons','fans','tree_poses','errors'), map(int, prepared.groups()))))
        entry = dict(validation=checked,
                     memory_bytes=dict(zip(('persistent_used','assets_used','frame_peak','capacity_failures'), map(int, memory.groups()))),
                     timings={case:{metric:stats([float(row[metric]) for row in rows
                                        if int(row['case'])==index and row['measured']=='1'])
                                    for metric in ('submit_ms','complete_readback_ms','gpu_elapsed_ms')}
                              for index, case in enumerate(CASES)},
                     fixture_sha256=sha256(fixture), fixture_bytes=fixture.stat().st_size,
                     fixture_manifest=manifest['native_scene'],
                     csv=str(csv_path.relative_to(REPO)), log=str(log_path.relative_to(REPO)))
        report['scenes'][name]=entry
        print(f'{name}: {len(rows)} frames; mismatches={checked["pixel_mismatches"]}; '
              f'heap allocations={checked["heap_allocations"]}', flush=True)
        for case in CASES:
            t=entry['timings'][case]
            print(f'  {case}: submit {t["submit_ms"]["median"]:.3f} ms; '
                  f'complete {t["complete_readback_ms"]["median"]:.3f} ms; '
                  f'p95 {t["complete_readback_ms"]["p95"]:.3f} ms', flush=True)
    paths=[PORT/'CMakeLists.txt', *sorted((PORT/'src').glob('*.c')), *sorted((PORT/'src').glob('*.h'))]
    report['source_sha256']={str(path.relative_to(PORT)):sha256(path) for path in paths}
    report['executable_sha256']=sha256(PORT/'build/haunted_native.exe')
    (PORT/'native_scene_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    run()
