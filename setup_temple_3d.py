"""Install the pinned 3D Raylib binding locally, reusing existing game dependencies."""
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
ENV = ROOT / 'artifacts' / 'temple3d-env'
VERSION = '5.5.0.4'


def python_path():
    return ENV / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def ensure_runtime():
    """Re-enter the isolated interpreter before importing any Raylib bindings."""
    if Path(sys.prefix).resolve() == ENV.resolve():
        from importlib.metadata import version
        if version('raylib') != VERSION:
            raise SystemExit('Run python setup_temple_3d.py to install the pinned Raylib binding.')
        return
    interpreter = python_path()
    if not interpreter.exists():
        raise SystemExit('Set up 3D once with: python setup_temple_3d.py')
    raise SystemExit(subprocess.call([str(interpreter), *sys.argv], cwd=ROOT))


def main():
    if not python_path().exists():
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(ENV)
    subprocess.run([str(python_path()), '-m', 'pip', 'install', '--only-binary=:all:',
                    '--disable-pip-version-check', f'raylib=={VERSION}'], check=True)
    print('3D environment ready. Launch: python moonlit_water_temple_3d.py')


if __name__ == '__main__':
    main()
