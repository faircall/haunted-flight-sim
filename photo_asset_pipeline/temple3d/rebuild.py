"""Rebuild the independently selectable photo/Blender temple kit."""
from pathlib import Path
import argparse,subprocess,sys

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blender',default='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
    p.add_argument('--export-only',action='store_true');args=p.parse_args()
    if not args.export_only:
        subprocess.run([sys.executable,str(ROOT/'prepare.py')],check=True)
        with (ROOT/'bake.log').open('w') as log:
            result=subprocess.run([args.blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'build.py')],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            print((ROOT/'bake.log').read_text());raise SystemExit(result.returncode)
    subprocess.run([sys.executable,str(ROOT/'export.py')],check=True)


if __name__=='__main__':main()
