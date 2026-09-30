"""Compiled C game entry: same assets/gameplay, with hot reload disabled."""
import importlib
import json
from pathlib import Path
import sys

def run():
    runtime=Path(sys.executable).parent/'runtime'
    manifest=json.loads((runtime/'compiled_modules.json').read_text(encoding='utf8'))
    # Fail loudly instead of quietly benchmarking original Python modules.
    for record in manifest:
        module=importlib.import_module(record['name'])
        origin=Path(module.__spec__.origin)
        if origin.parent!=runtime or origin.suffix!='.pyd':
            raise RuntimeError('Game module was not compiled: '+record['name'])
    import g_main
    import native_bindings
    import native_geometry
    native_bindings.install()
    native_geometry.install()
    g_main.g_reloadable_modules=[]
    g_main.g_shader_source_files=()
    if '--profile-native' in sys.argv:
        from c_port.profile_hotspots import run as profile
        profile()
    elif '--parity' in sys.argv:
        from c_port.check_game import run as check
        check()
    elif '--water-benchmark' in sys.argv:
        import benchmark_water
        benchmark_water.run()
    elif '--smoke' in sys.argv:
        kind=sys.argv[sys.argv.index('--smoke')+1]
        if kind=='water':
            import water_temple_smoke
            water_temple_smoke.run()
        elif kind=='night':
            import night_smoke
            night_smoke.run()
        elif kind=='surfaces':
            import surface_smoke
            surface_smoke.run()
        else:raise ValueError('Unknown smoke scene: '+kind)
    elif '--tests' in sys.argv:
        import unittest
        names=sys.argv[sys.argv.index('--tests')+1:]
        result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
        if not result.wasSuccessful():raise RuntimeError('Compiled C game tests failed')
    elif '--courtyard' in sys.argv:
        import night_trial
        night_trial.run()
    elif '--original-level' in sys.argv:g_main.g_main()
    else:
        import moonlit_water_temple
        moonlit_water_temple.run()
