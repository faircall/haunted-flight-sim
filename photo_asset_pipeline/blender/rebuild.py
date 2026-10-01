"""Complete offline Blender roof build; accepts --blender /path/to/blender.exe."""
from pathlib import Path
import argparse,subprocess,sys

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender',type=Path,default=Path('C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'))
    args=parser.parse_args()
    if not args.blender.is_file():parser.error('Blender not found. Supply its executable path with --blender.')
    subprocess.run([sys.executable,str(ROOT/'prepare_textures.py')],check=True)
    with (ROOT/'bake.log').open('w',encoding='utf8') as log:
        completed=subprocess.run([str(args.blender),'--background','--factory-startup','--python-exit-code','1',
                                  '--python',str(ROOT/'build_roof.py')],stdout=log,stderr=subprocess.STDOUT)
    if completed.returncode:
        print((ROOT/'bake.log').read_text(encoding='utf8'));raise SystemExit(completed.returncode)
    subprocess.run([sys.executable,str(ROOT/'export_roof.py')],check=True)
    print('Roof rebuilt. Editable scene: '+str(ROOT/'water_temple_roof.blend'))


if __name__=='__main__':main()
