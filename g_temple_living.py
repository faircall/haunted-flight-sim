"""Persistent 3D willow/player resources. Bone and wind deformation stay on GPU."""
from pathlib import Path
import math
import json

import pyray as pr
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT_SETTINGS

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'photo_asset_pipeline' / 'temple3d' / 'living'
# Raylib 5.5 LoadModelAnimationsGLTF uses GLTF_ANIMDELAY=17 milliseconds.
# https://github.com/raysan5/raylib/blob/5.5/src/rmodels.c
ANIMATION_SAMPLE_SECONDS = .017


class LivingScene:
    def __init__(self, include_willow=True):
        if not hasattr(pr, 'update_model_animation_bones'):
            raise RuntimeError('3D characters require Raylib 5.5. Run play_temple_3d.cmd.')
        self.shaders = []
        self.locations = {}
        self.models = []
        self.textures = {}
        self.animations = None
        self.animation_count = 0
        self.clock = 0.
        self.phase = 0.
        self.yaw = 90.
        self.clip = 'idle'
        self.animation_frame = 0
        self.pose_blend = 1.
        try:
            self.skin = self.load_shader('temple_skin')
            self.wind = self.load_shader('temple_willow') if include_willow else None
            self.player = self.load_model('player', self.skin)
            self.willow = self.load_model('willow', self.wind) if include_willow else None
            count = pr.ffi.new('int *')
            self.animations = pr.load_model_animations(str(ASSETS/'models'/'player.glb'), count)
            self.animation_count = count[0]
            self.clips = {pr.ffi.string(self.animations[i].name).decode(): i for i in range(count[0])}
            self.clip_seconds = json.loads((ASSETS/'manifest.json').read_text())['player']['clips']
            if not {'idle','walk','run'} <= self.clips.keys():
                raise RuntimeError('Player export is missing animation clips')
            for mesh in self.player.meshes[0:self.player.meshCount]:
                if mesh.boneCount != self.player.boneCount or not mesh.vboId[7] or not mesh.vboId[8]:
                    raise RuntimeError('GPU joint attributes were not uploaded')
            if self.player.boneCount > 32:
                raise RuntimeError('This character shader supports at most 32 bones')
            self.previous_pose = pr.ffi.new('Matrix[]',self.player.boneCount)
            self.previous_location = pr.get_shader_location(self.skin,'previousPose')
            self.blend_location = pr.get_shader_location(self.skin,'poseBlend')
            self.pose('idle', 0.)
        except Exception:
            self.close()
            raise

    def load_shader(self, name):
        shader = pr.load_shader(str(ROOT/'shaders'/(name+'.vs')),str(ROOT/'shaders'/'temple_living.fs'))
        if shader.id == pr.rl.rlGetShaderIdDefault():
            raise RuntimeError('Shader did not compile: '+name)
        self.shaders.append(shader)
        shader.locs[pr.SHADER_LOC_MATRIX_MODEL] = pr.get_shader_location(shader,'matModel')
        shader.locs[pr.SHADER_LOC_MATRIX_NORMAL] = pr.get_shader_location(shader,'matNormal')
        if name == 'temple_skin':
            shader.locs[pr.SHADER_LOC_BONE_MATRICES] = pr.get_shader_location(shader,'boneMatrices')
            if shader.locs[pr.SHADER_LOC_BONE_MATRICES] < 0:
                raise RuntimeError('Bone uniform not active')
        self.locations[shader.id] = {key: pr.get_shader_location(shader,key) for key in
                                     ('time','inspection','windStrength','moonDirection','lampCount','lamps')}
        return shader

    def load_model(self, name, shader):
        model = pr.load_model(str(ASSETS/'models'/(name+'.glb')))
        self.models.append(model)
        if not model.meshCount:
            raise RuntimeError('Empty model: '+name)
        for index in range(model.materialCount):
            material = model.materials[index]
            material.shader = shader
            texture = material.maps[pr.MATERIAL_MAP_DIFFUSE].texture
            if texture.id != pr.rl.rlGetTextureIdDefault() and texture.id:
                self.textures[texture.id] = texture
                pr.set_texture_filter(texture,pr.TEXTURE_FILTER_POINT)
                pr.set_texture_wrap(texture,pr.TEXTURE_WRAP_REPEAT)
        return model

    def environment(self, now, inspection, lights, wind=4.):
        self.clock = now
        # Small fixed uniform sets; no rebuilding meshes or traversing vertices.
        for shader in self.shaders:
            locations = self.locations[shader.id]
            for name, value in (('time',now),('inspection',float(inspection)),('windStrength',wind)):
                if locations[name] >= 0:
                    pr.set_shader_value(shader,locations[name],pr.ffi.new('float[]',[value]),pr.SHADER_UNIFORM_FLOAT)
            pr.set_shader_value(shader,locations['moonDirection'],pr.ffi.new('float[]',[-.45,.75,-.52]),pr.SHADER_UNIFORM_VEC3)
            pr.set_shader_value(shader,locations['lampCount'],pr.ffi.new('int[]',[len(lights)//3]),pr.SHADER_UNIFORM_INT)
            if lights:
                pr.set_shader_value_v(shader,locations['lamps'],pr.ffi.new('float[]',lights),pr.SHADER_UNIFORM_VEC3,len(lights)//3)

    def pose(self, clip, phase, dt=None):
        if dt is None:
            self.pose_blend = 1.
        elif clip != self.clip:
            # Freeze the currently displayed pose, including an interrupted fade.
            # This tiny bone array is touched only when the animation clip changes.
            old = pr.ffi.cast('float *',self.previous_pose)
            current = pr.ffi.cast('float *',self.player.meshes[0].boneMatrices)
            for i in range(self.player.boneCount*16):
                old[i] = old[i]*(1-self.pose_blend)+current[i]*self.pose_blend
            pr.rl.rlEnableShader(self.skin.id)
            pr.rl.rlSetUniformMatrices(self.previous_location,self.previous_pose,self.player.boneCount)
            pr.rl.rlDisableShader()
            self.pose_blend = 0.
        else:
            self.pose_blend = min(1.,self.pose_blend+max(0.,dt)/.14)
        animation = self.animations[self.clips[clip]]
        frame = min(animation.frameCount-1, int((phase % 1.)*self.clip_seconds[clip]/ANIMATION_SAMPLE_SECONDS))
        pr.update_model_animation_bones(self.player,animation,frame)
        pr.set_shader_value(self.skin,self.blend_location,pr.ffi.new('float[]',[self.pose_blend]),pr.SHADER_UNIFORM_FLOAT)
        self.clip, self.animation_frame = clip, frame

    def update(self, dt, moving, heading, travelled, running=False):
        if moving:
            goal = math.degrees(math.atan2(heading[0],heading[1]))
            delta = (goal-self.yaw+180)%360-180
            self.yaw += delta*min(1.,dt*12.)
            self.phase += travelled/GAIT_SETTINGS['run' if running else 'walk']['stride']
            self.pose('run' if running else 'walk',self.phase,dt)
        else:
            self.pose('idle',self.clock/2.,dt)

    def draw_player(self, x, floor, z):
        pr.draw_model_ex(self.player,pr.Vector3(x,floor,z),pr.Vector3(0,1,0),self.yaw,pr.Vector3(1,1,1),pr.WHITE)

    def draw_willow(self, x, z, angle=0.):
        # Alpha-tested leaves write depth normally; both sides of each ribbon show.
        pr.rl.rlDisableBackfaceCulling()
        pr.draw_model_ex(self.willow,pr.Vector3(x,0,z),pr.Vector3(0,1,0),angle,pr.Vector3(1,1,1),pr.WHITE)
        pr.rl.rlEnableBackfaceCulling()

    def close(self):
        if self.animations is not None:
            pr.unload_model_animations(self.animations,self.animation_count)
            self.animations = None
        for model in self.models:
            pr.unload_model(model)
        for texture in self.textures.values():
            pr.unload_texture(texture)
        for shader in self.shaders:
            pr.unload_shader(shader)
        self.models.clear()
        self.textures.clear()
        self.shaders.clear()
