"""Paired full-game runs, alternating order, then a separate native renderer run."""
import argparse
from pathlib import Path
import struct
import subprocess
import sys

PORT = Path(__file__).resolve().parent
REPO = PORT.parent


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--frames', type=int, default=240)
    args = parser.parse_args()
    if args.repeats < 1 or args.frames < 1:
        parser.error('repeats and frames must be positive')
    scene = PORT / 'data/water/scene.hfc'
    if not scene.exists():
        parser.error(f'First run python c_port/export_scene.py --frames {args.frames}')
    with scene.open('rb') as stream:
        header = stream.read(12)
    if header[:8] != b'HFCP0001' or struct.unpack_from('<I', header, 8)[0] != (args.frames+8)*3:
        parser.error(f'Re-export the reference route with --frames {args.frames}')
    for name in ('haunted_game.exe', 'haunted_native.exe'):
        if not (PORT / 'build' / name).exists():
            parser.error('Build both executables first; see c_port/README.md')
    output = PORT / 'output'
    output.mkdir(exist_ok=True)
    paths = dict(python=[], game=[])
    def execute(command, label):
        print(label, flush=True)
        with (output / (label+'.log')).open('w', encoding='utf8') as stream:
            subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT, check=True)
    for repeat in range(args.repeats):
        for kind in (('python', 'game') if repeat % 2 == 0 else ('game', 'python')):
            label = f'c-port-{kind}-repeat-{repeat+1}'
            command = ([sys.executable, '.tree_game_smoke.py'] if kind == 'python'
                       else [str(PORT/'build/haunted_game.exe')])
            execute(command + ['--water-benchmark', '--label', label, '--frames', str(args.frames),
                               '--profile-frames', '0'], label)
            paths[kind].append(f'artifacts/moonlit-water-temple/{label}-timings.json')
    native = f'c_port/output/native-{args.frames}.csv'
    execute([str(PORT/'build/haunted_native.exe'), '--benchmark', '--hidden', '--output', native],
            'c-port-native-final')
    subprocess.run([sys.executable, 'c_port/summarize.py', '--python', *paths['python'],
                    '--game', *paths['game'], '--native', native], cwd=REPO, check=True)


if __name__ == '__main__':
    run()
