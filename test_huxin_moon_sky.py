"""Sky rays must align with native scene projections, including mirrored water.

These checks use raylib's vector/projection maths but never create a window,
load a shader, initialise audio, or issue a GPU call.
"""
from contextlib import ExitStack
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyray as pr

from g_huxin_moon_sequence import MOON
from huxin_moon_sky import MoonSky


WIDTH, HEIGHT = 640, 360


def xyz(vector):
    return vector.x, vector.y, vector.z


def reflect_y(vector):
    return vector[0], -vector[1], vector[2]


def camera_cases():
    """Ordinary pans, pitched views, and authorable rolled/vertical cameras."""
    for yaw in (-135., -40., 0., 63., 170.):
        for pitch in (-62., -17., 23.):
            heading, elevation = math.radians(yaw), math.radians(pitch)
            forward = (math.sin(heading)*math.cos(elevation), math.sin(elevation),
                       -math.cos(heading)*math.cos(elevation))
            eye = (13., 7., 23.)
            target = tuple(a+10.*b for a, b in zip(eye, forward))
            yield f'yaw={yaw}, pitch={pitch}', pr.Camera3D(
                pr.Vector3(*eye), pr.Vector3(*target), pr.Vector3(0, 1, 0),
                61., pr.CAMERA_PERSPECTIVE)
    yield 'rolled', pr.Camera3D(pr.Vector3(8, 5, 12), pr.Vector3(-3, 1, -7),
                               pr.Vector3(.55, .81, -.20), 79., pr.CAMERA_PERSPECTIVE)
    yield 'vertical down', pr.Camera3D(pr.Vector3(2, 20, 3), pr.Vector3(2, 0, 3),
                                      pr.Vector3(0, 0, -1), 48., pr.CAMERA_PERSPECTIVE)
    yield 'vertical up', pr.Camera3D(pr.Vector3(2, 4, 3), pr.Vector3(2, 20, 3),
                                    pr.Vector3(0, 0, -1), 48., pr.CAMERA_PERSPECTIVE)


def capture_uniforms(camera, reflected=False):
    sky = object.__new__(MoonSky)
    sky.shader = object()
    names = ('forward', 'right', 'up', 'fogColour', 'lens', 'time', 'dusk', 'moonDirection')
    sky.locations = {name: index for index, name in enumerate(names)}
    captured = {}
    sizes = {pr.SHADER_UNIFORM_FLOAT: 1, pr.SHADER_UNIFORM_VEC3: 3, pr.SHADER_UNIFORM_VEC4: 4}

    def record(shader, location, values, kind):
        captured[names[location]] = tuple(float(values[i]) for i in range(sizes[kind]))

    with ExitStack() as stack:
        stack.enter_context(patch.object(pr, 'set_shader_value', side_effect=record))
        for name in ('begin_shader_mode', 'draw_rectangle', 'end_shader_mode'):
            stack.enter_context(patch.object(pr, name))
        # Keep construction/render calls honest if the implementation changes.
        for name in ('init_window', 'init_audio_device', 'load_shader'):
            stack.enter_context(patch.object(pr, name, side_effect=AssertionError('CPU-only sky test')))
        sky.draw(camera, SimpleNamespace(elapsed=17.25, dusk=.7),
                 pr.Color(45, 60, 63, 255), WIDTH, HEIGHT, reflected=reflected)
    return captured


def shader_ray(uniforms, u, v):
    tangent, aspect = uniforms['lens'][:2]
    ray = tuple(uniforms['forward'][i] + uniforms['right'][i]*u*tangent*aspect
                + uniforms['up'][i]*v*tangent for i in range(3))
    length = math.sqrt(sum(component*component for component in ray))
    return tuple(component/length for component in ray)


class MoonSkyTests(unittest.TestCase):
    def assert_vector_close(self, actual, expected, places=6):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=places)

    def test_reflection_rays_follow_mirrored_geometry_for_pan_pitch_roll_and_vertical_views(self):
        # get_world_to_screen_ex uses raylib's own view/projection matrices.
        # Project a distant sky landmark after the same Y mirror as the scene
        # geometry. It must land on the pixel that emitted the shader ray.
        # In particular, this fails if cross products silently reverse right.
        for label, camera in camera_cases():
            uniforms = capture_uniforms(camera, reflected=True)
            reflected_eye = reflect_y(xyz(camera.position))
            for u, v in ((-.72, -.57), (.61, -.24), (-.31, .68), (.83, .42), (0., 0.)):
                with self.subTest(camera=label, uv=(u, v)):
                    ray = shader_ray(uniforms, u, v)
                    landmark = tuple(a+180.*b for a, b in zip(reflected_eye, ray))
                    mirrored_geometry = pr.Vector3(*reflect_y(landmark))
                    screen = pr.get_world_to_screen_ex(mirrored_geometry, camera, WIDTH, HEIGHT)
                    self.assertAlmostEqual(screen.x, (u+1.)*.5*WIDTH, delta=.001)
                    self.assertAlmostEqual(screen.y, (1.-v)*.5*HEIGHT, delta=.001)

    def test_direct_sky_rays_keep_the_original_scene_projection(self):
        for label, camera in camera_cases():
            uniforms = capture_uniforms(camera)
            for u, v in ((-.72, -.57), (.61, -.24), (-.31, .68), (.83, .42)):
                with self.subTest(camera=label, uv=(u, v)):
                    ray = shader_ray(uniforms, u, v)
                    landmark = pr.Vector3(*(a+180.*b for a, b in zip(xyz(camera.position), ray)))
                    screen = pr.get_world_to_screen_ex(landmark, camera, WIDTH, HEIGHT)
                    self.assertAlmostEqual(screen.x, (u+1.)*.5*WIDTH, delta=.001)
                    self.assertAlmostEqual(screen.y, (1.-v)*.5*HEIGHT, delta=.001)

    def test_reflection_changes_only_world_y_and_preserves_weather_and_lens(self):
        for label, camera in camera_cases():
            with self.subTest(camera=label):
                direct = capture_uniforms(camera)
                reflected = capture_uniforms(camera, reflected=True)
                for name in ('forward', 'right', 'up'):
                    self.assert_vector_close(reflected[name], reflect_y(direct[name]))
                for name in ('fogColour', 'lens', 'time', 'dusk', 'moonDirection'):
                    self.assertEqual(reflected[name], direct[name])
                self.assert_vector_close(direct['moonDirection'], MOON)
                self.assertEqual(direct['time'], (17.25,))
                for u, v in ((-.8, .7), (.65, -.4)):
                    self.assert_vector_close(shader_ray(reflected, u, v),
                                             reflect_y(shader_ray(direct, u, v)))


if __name__ == '__main__':
    unittest.main()
