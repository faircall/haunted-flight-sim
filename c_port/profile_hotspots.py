"""Instrument compiled entry points; use separately from frame benchmarks."""
import collections
import functools
import json
from pathlib import Path
import sys
import time


def run():
    import benchmark_water
    import g_graphics
    import g_light_visibility
    import g_night

    totals = collections.defaultdict(lambda: [0, 0.0])
    originals = []
    names = {
        g_graphics: (
            'prepare_entity_self_shadows', 'get_prepared_light_strength_for_render_item',
            'get_render_item_light_sample_points', 'points_in_polygon',
            'query_entity_light_occlusion', 'spot_light_conservatively_intersects_render_item',
            'polygon_intersects_rectangle', 'calculate_render_item_light_direction_bundle',
            'calculate_center_directional_weights', 'prepare_entity_light_sample_caches',
        ),
        g_light_visibility: ('get_unoccluded_light_strength_at_world_point',),
        g_night: ('facade_receiver', 'portal_strength'),
    }
    for module, functions in names.items():
        for name in functions:
            original = getattr(module, name)
            key = module.__name__ + '.' + name
            @functools.wraps(original)
            def measured(*args, _method=original, _key=key, **kwargs):
                start = time.perf_counter()
                try:
                    return _method(*args, **kwargs)
                finally:
                    entry = totals[_key]
                    entry[0] += 1
                    entry[1] += time.perf_counter() - start
            originals.append((module, name, original))
            setattr(module, name, measured)
    argv = sys.argv[:]
    sys.argv = [argv[0], '--water-benchmark', '--label', 'c-port-instrumented',
                '--frames', '40', '--profile-frames', '0']
    try:
        benchmark_water.run()
    finally:
        sys.argv = argv
        for module, name, original in originals:
            setattr(module, name, original)
    output = {key: dict(calls=value[0], total_ms=round(value[1]*1000, 3))
              for key, value in sorted(totals.items(), key=lambda pair: -pair[1][1])}
    Path('c_port/output/instrumented.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
