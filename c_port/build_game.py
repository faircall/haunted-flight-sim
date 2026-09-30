"""Compile the complete game into C extension modules, with a native C launcher.

Uses Cython for a semantics-preserving first C build. Existing Python source is
read-only. CPython containers and third-party runtime libraries remain; this is
not a claim that generated C has the ceiling of a packed-struct rewrite.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import time

PORT=Path(__file__).resolve().parent
REPO=PORT.parent
sys.path.insert(0,str(PORT/'build-tools'))
from Cython.Compiler.Main import compile as cython_compile,CompilationOptions,default_options

class PortableStrings(ast.NodeTransformer):
    """Avoid PEP 701 quote syntax while keeping format()/conversion behavior."""
    def visit_JoinedStr(self,node):
        pieces=[]
        for part in node.values:
            if isinstance(part,ast.Constant):pieces.append(part)
            else:
                value=self.visit(part.value)
                if part.conversion!=-1:
                    value=ast.Call(ast.Name({114:'repr',115:'str',97:'ascii'}[part.conversion],ast.Load()),[value],[])
                spec=self.visit(part.format_spec) if part.format_spec else ast.Constant('')
                pieces.append(ast.Call(ast.Name('format',ast.Load()),[value,spec],[]))
        return ast.copy_location(ast.Call(ast.Attribute(ast.Constant(''),'join',ast.Load()),[ast.List(pieces,ast.Load())],[]),node)

# Explicit types at the busiest container/numeric boundaries. Generated C then
# uses direct dictionary/list access and double arithmetic instead of generic
# Python method dispatch. Keep declarations narrow and validate output pixels.
TYPED_FUNCTIONS={
    'g_graphics':{
        'prepare_entity_self_shadows':(
            {'render_items':'list','prepared_lights':'list','major_occluders':'list','collision_grid':'dict'},
            ['dict summaries, item, policy, prepared, prepared_light, light, cache, summary, records, light_record, weights',
             'list diagnostics, sample_lists, positive, face_totals, per_light',
             'double strength, sampled_total, visible_total, omni_total',
             'bint bypass_occlusion, explicit_directional, is_omni']),
        'get_prepared_light_strength_for_render_item':(
            {'prepared_light':'dict','render_item':'dict','collision_grid':'dict'},
            ['dict light, cache, aggregate, point, bounds','list strengths','double intensity, strongest_sample, strength']),
        'get_render_item_light_sample_points':({'render_item':'dict'},[]),
        'prepare_entity_light_sample_caches':({'grid':'dict','assets':'dict'},['dict prepared, light, field, portal, entry']),
        'query_entity_light_occlusion':({'prepared_light':'dict','target_item':'dict'},[]),
        'calculate_center_directional_weights':({'render_item':'dict','light_position':'dict'},[]),
    },
    'g_light_visibility':{
        'get_unoccluded_light_strength_at_world_point':(
            {'light':'dict','world_point':'dict','collision_grid':'dict'},
            ['dict field, light_position, light_direction, size',
             'double offset_x, offset_y, distance, radius, radial_strength, cone_strength, near_strength, near_fade_distance, alignment, inner_angle, outer_angle, half_width, half_height']),
    },
}

def add_native_types(text,module):
    declarations=TYPED_FUNCTIONS.get(module,{})
    if not declarations:return text
    lines=text.splitlines()
    for node in reversed(ast.parse(text).body):
        if not isinstance(node,ast.FunctionDef) or node.name not in declarations:continue
        arguments,locals_=declarations[node.name]
        signature=lines[node.lineno-1]
        import re
        for name,kind in arguments.items():
            signature=re.sub(r'(?<=[(,])\s*'+re.escape(name)+r'(?=[,)=])', ' '+kind+' '+name,signature)
        lines[node.lineno-1]=signature
        lines[node.body[0].lineno-1:node.body[0].lineno-1]=['    cdef '+declaration for declaration in locals_]
    return '\n'.join(lines)+'\n'

NATIVE_RAYS='''
# The renderer/gameplay ray traversal uses typed native C, without ctypes.
cdef extern from "visibility.h":
    ctypedef struct HFGrid:
        int width
        int height
        double tile_width
        double tile_height
        const unsigned char *shapes
    ctypedef struct HFHit:
        double distance
        double normal_x
        double normal_y
        int hit
        int tile_x
        int tile_y
        int tile_index
        int shape
        int edge
        int steps
    HFHit hf_light_ray(const HFGrid *,double,double,double,double,double)

def dda_first_light_hit_values(double origin_x,double origin_y,double direction_x,
                               double direction_y,double max_distance,collision_grid):
    cdef const unsigned char[:] codes=collision_grid['shape_codes']
    cdef HFGrid grid
    grid.width=collision_grid['map_width']
    grid.height=collision_grid['map_height']
    grid.tile_width=collision_grid['tile_width']
    grid.tile_height=collision_grid['tile_height']
    grid.shapes=&codes[0]
    cdef HFHit hit=hf_light_ray(&grid,origin_x,origin_y,direction_x,direction_y,max_distance)
    if not hit.hit:
        return None,hit.steps
    return (hit.distance,hit.tile_x,hit.tile_y,hit.tile_index,hit.shape,hit.edge,hit.normal_x,hit.normal_y),hit.steps
'''

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args()
    build=PORT/'build';source_dir=build/'game_sources';generated=build/'generated';runtime=build/'runtime'
    for directory in (source_dir,generated,runtime):directory.mkdir(parents=True,exist_ok=True)
    gcc=Path('C:/raylib/w64devkit/bin/gcc.exe')
    env=os.environ.copy();env['PATH']=str(gcc.parent)+os.pathsep+env['PATH']
    include=sysconfig.get_paths()['include'];python_home=Path(sys.base_prefix)
    library=python_home/'libs'/f'python{sys.version_info.major}{sys.version_info.minor}.lib'
    suffix=sysconfig.get_config_var('EXT_SUFFIX')
    files=sorted(REPO.glob('g_*.py'))+[REPO/'moonlit_water_temple.py',REPO/'night_trial.py',PORT/'native_entry.py',PORT/'native_bindings.py',PORT/'native_geometry.pyx']
    manifest=[];jobs=[]
    for file in files:
        name=file.stem;text=file.read_text(encoding='utf8')
        if name=='g_main':
            text=text.replace('auto_reload = True','auto_reload = False')
            text=text.replace('if ((reload_timer >= reload_refresh_interval) and auto_reload) or pr.is_key_released(pr.KeyboardKey.KEY_F4):','if False: # Native build has no module/asset hot reload.')
        if name=='g_light_visibility':
            text=text.replace('def dda_first_light_hit_values(', 'def _python_dda_first_light_hit_values(',1)
        # Normalize Python 3.12's nested f-string quoting for Cython's parser.
        # AST round-tripping changes source spelling, not expression semantics.
        if file.suffix != '.pyx':
            text=ast.unparse(ast.fix_missing_locations(PortableStrings().visit(ast.parse(text))))+'\n'
            text=add_native_types(text,name)
        if name=='g_light_visibility':text+=NATIVE_RAYS
        # Source modules use __file__ for assets. The loader below sets it to
        # this read-only original path before Cython executes the module body.
        text=f'__file__ = {str(file)!r}\n'+text
        source=source_dir/(name+'.pyx');cfile=generated/(name+'.c');binary=runtime/(name+suffix)
        digest=hashlib.sha256((text+NATIVE_RAYS+sys.version).encode()).hexdigest()
        if name=='g_light_visibility':
            digest=hashlib.sha256(digest.encode()+(PORT/'src'/'visibility.c').read_bytes()+(PORT/'src'/'visibility.h').read_bytes()).hexdigest()
        if name=='native_geometry':
            digest=hashlib.sha256(digest.encode()+(PORT/'src'/'geometry.c').read_bytes()+(PORT/'src'/'geometry.h').read_bytes()).hexdigest()
        stamp=generated/(name+'.sha256')
        if not (binary.exists() and stamp.exists() and stamp.read_text()==digest):
            source.write_text(text,encoding='utf8')
            options=CompilationOptions(default_options,output_file=str(cfile),compiler_directives=dict(language_level=3,binding=True,infer_types=False,annotation_typing=False))
            result=cython_compile(str(source),options=options,full_module_name=name)
            if result.num_errors:raise RuntimeError('C generation failed: '+name)
            command=[str(gcc),'-shared','-O2','-DNDEBUG','-fwrapv','-ffp-contract=off','-Wno-unused-function',
                     '-Wno-unused-variable','-I'+include,'-I'+str(PORT/'src'),str(cfile)]
            if name=='g_light_visibility':command.append(str(PORT/'src'/'visibility.c'))
            if name=='native_geometry':command.append(str(PORT/'src'/'geometry.c'))
            command += [str(library),'-o',str(binary),'-static-libgcc']
            jobs.append((name,command,stamp,digest))
        manifest.append(dict(name=name,source=str(file.relative_to(REPO)),sha256=digest,binary=binary.name))
    def build_one(job):
        name,command,stamp,digest=job;start=time.perf_counter()
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        (generated/(name+'.build.log')).write_text(result.stdout+result.stderr,encoding='utf8')
        if result.returncode:raise RuntimeError(f'{name}:\n{result.stderr[-6000:]}')
        stamp.write_text(digest)
        print(f'Compiled {name} ({time.perf_counter()-start:.1f}s)',flush=True)
    with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as pool:
        list(pool.map(build_one,jobs))
    (runtime/'compiled_modules.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    # The launcher uses the installed dependency runtime, but all game modules
    # above resolve to compiled C extensions from build/runtime first.
    config=(f'#define HF_PYTHON_HOME {json.dumps(str(python_home))}\n'
            f'#define HF_REPO_ROOT {json.dumps(str(REPO))}\n'
            f'#define HF_RUNTIME_ROOT {json.dumps(str(runtime))}\n')
    (generated/'game_config.h').write_text(config,encoding='utf8')
    subprocess.run([str(gcc),'-O2','-I'+include,'-I'+str(generated),str(PORT/'src'/'game_main.c'),
                    str(library),'-o',str(build/'haunted_game.exe'),'-static-libgcc'],env=env,check=True)
    print(f'Built playable C game: {build/"haunted_game.exe"}; {len(manifest)} compiled game modules.',flush=True)

if __name__=='__main__':run()
