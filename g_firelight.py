"""Firelight contours, shared by radial and cached receiver shaders."""
from pathlib import Path
import numpy as np
from PIL import Image
import pyray as pr

ROOT = Path(__file__).resolve().parent


def parameters(emitter, activity, time_elapsed=0.):
    from g_effects import FIRELIGHT_CONTOUR_DEFAULTS
    settings = emitter.get('light', {}).get('contours', {})
    settings = FIRELIGHT_CONTOUR_DEFAULTS | settings
    seed = int(emitter.get('seed', 1))
    speed = max(0., float(settings['speed']))
    return dict(strength=max(0., min(.85, float(settings['strength']))),
                scale=max(4., float(settings['scale'])),
                offset=(float(seed * 37 % 128), float(seed * 73 % 128)),
                motion=max(0., min(1., float(settings['motion']))),
                phase=time_elapsed * speed + activity * .18 if speed else 0.)


def load_shader(path):
    source = Path(path).read_text(encoding='utf8')
    source = source.replace('// FIRELIGHT_COMMON', (ROOT/'shaders/firelight_contours.glsl').read_text(encoding='utf8'))
    shader = pr.load_shader_from_memory(pr.ffi.NULL, source)
    if shader.id == pr.rl.rlGetShaderIdDefault():
        raise RuntimeError('Firelight shader failed: ' + str(path))
    return shader


def register(shader):
    import g_surfaces
    # Cached lattice noise, not a colour texture. Smooth lookup is internal to
    # the light field; the usual final posterization still supplies crisp bands.
    values = np.random.default_rng(74119).integers(0, 256, (128, 128, 4), dtype=np.uint8)
    values[:, :, 3] = 255
    noise = g_surfaces.upload_image(Image.fromarray(values))
    pr.set_texture_filter(noise, pr.TextureFilter.TEXTURE_FILTER_BILINEAR)
    pr.set_texture_wrap(noise, pr.TextureWrap.TEXTURE_WRAP_REPEAT)
    return dict(shader=shader, noise=noise, locations={name: pr.get_shader_location(shader, name)
        for name in ('fireNoise', 'firePattern', 'fireWorld', 'fireMotion')})


def bind(info, light, camera, height):
    """Call inside shader mode, after flushing any preceding light's geometry."""
    if info is None:
        return
    import g_graphics as graphics
    shader = info['shader']; loc = info['locations']
    value = light.get('_fire_contours')
    if not value or value['strength'] <= 0.:
        graphics.set_shader_vec4(shader, loc['firePattern'], 0., 1., 0., 0.)
        return
    graphics.set_shader_vec4(shader, loc['firePattern'], value['strength'], 1./value['scale'], *value['offset'])
    graphics.set_shader_vec3(shader, loc['fireWorld'], round(camera.x), round(camera.y), height)
    graphics.set_shader_vec2(shader, loc['fireMotion'], value['motion'], value['phase'])
    graphics.set_shader_texture(shader, loc['fireNoise'], info['noise'])


def unload(info):
    if info and 'noise' in info:
        pr.unload_texture(info.pop('noise'))
