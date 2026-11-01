"""Persistent 3D willow/player resources. Bone and wind deformation stay on GPU."""
from pathlib import Path
import math
import json
import os

import pyray as pr
from g_player_locomotion import stride_for
from g_player_proportions import arm_positions
from photo_asset_pipeline.temple3d.living.gait import UPPER_ARM, FOREARM

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'photo_asset_pipeline' / 'temple3d' / 'living'
# Raylib 5.5 LoadModelAnimationsGLTF uses GLTF_ANIMDELAY=17 milliseconds.
# https://github.com/raysan5/raylib/blob/5.5/src/rmodels.c
ANIMATION_SAMPLE_SECONDS = .017
SMOOTH_PLAYER_CLIPS = frozenset(('idle','walk','run','walk_back','turn_left','turn_right'))
SMOOTH_CHORUS_CLIPS = frozenset(('enemy_idle','enemy_walk','enemy_run'))


def animation_samples(phase,seconds,frame_count):
    """Adjacent looping samples and their weight, including the short tail."""
    time=(phase%1.)*seconds
    frame=min(frame_count-1,int(time/ANIMATION_SAMPLE_SECONDS))
    if frame_count<=1:return frame,frame,0.
    start=frame*ANIMATION_SAMPLE_SECONDS
    end=seconds if frame==frame_count-1 else (frame+1)*ANIMATION_SAMPLE_SECONDS
    weight=max(0.,min(1.,(time-start)/max(1.e-9,end-start)))
    return frame,(frame+1)%frame_count,weight


class LivingScene:
    def __init__(self, include_willow=True, combat=False, actor='player',fragment_shader='temple_living.fs',variant=None):
        if not hasattr(pr, 'update_model_animation_bones'):
            raise RuntimeError('3D characters require Raylib 5.5. Run play_temple_3d.cmd.')
        self.shaders = []
        self.locations = {}
        self.models = []
        self.textures = {}
        self.animations = None
        self.animation_count = 0
        self.run_timing_animations = None
        self.run_timing_count = 0
        self.run_timing_index = None
        self.use_improved_run = True
        self.run_style = 'jog'
        self.jog_animations = None
        self.jog_count = 0
        self.jog_index = None
        self._sample_buffers = {}
        self.clock = 0.
        self.phase = 0.
        self.yaw = 90.
        self.clip = 'idle'
        self.animation_frame = 0
        self.pose_blend = 1.
        self.actor=actor
        self.fragment_shader=fragment_shader
        requested=(variant if variant is not None else os.environ.get('HAUNTED_PLAYER_VARIANT','original')) if actor=='player' else 'original'
        if requested not in ('original','refined'):raise ValueError('Player variant must be original or refined')
        self.variant=requested
        self.asset_root=(ROOT/'art'/'temple'/'chorus_grasper' if actor=='chorus_grasper' else
                         ROOT/'art'/'temple'/'player_refined' if requested=='refined' else
                         ROOT/'art'/'temple'/'combat' if combat or actor=='redhead' else ASSETS/'models')
        self.pistol=None
        try:
            self.skin = self.load_shader('temple_skin')
            self.wind = self.load_shader('temple_willow') if include_willow else None
            self.player = self.load_model(actor, self.skin)
            if combat and actor=='player':
                self.pistol=self.load_model('pistol',self.skin)
                self.align_pistol_bind_pose()
            self.willow = self.load_model('willow', self.wind) if include_willow else None
            count = pr.ffi.new('int *')
            self.animations = pr.load_model_animations(str(self.asset_root/(actor+'.glb')), count)
            self.animation_count = count[0]
            self.clips = {pr.ffi.string(self.animations[i].name).decode(): i for i in range(count[0])}
            manifest=(self.asset_root/'manifest.json' if requested=='refined' or actor=='chorus_grasper' else
                      ROOT/'art'/'temple'/'combat'/'manifest.json' if combat or actor=='redhead' else ASSETS/'manifest.json')
            self.clip_seconds = json.loads(manifest.read_text())[actor]['clips']
            required=({'idle','walk','run'} if actor=='player' else
                      {'enemy_idle','enemy_walk','enemy_run','enemy_attack','enemy_stagger','enemy_death'} if actor=='chorus_grasper' else
                      {'enemy_idle','enemy_walk','enemy_attack','enemy_stagger','enemy_death'})
            if not required <= self.clips.keys():
                raise RuntimeError('Player export is missing animation clips')
            # The run timing is an independent animation on the same rest rig.
            # Preserve the original assets and apply this to either player model.
            run_asset=ROOT/'art'/'temple'/'player_run_timing'/'run.glb'
            if actor=='player' and run_asset.is_file():
                run_count=pr.ffi.new('int *')
                self.run_timing_animations=pr.load_model_animations(str(run_asset),run_count)
                self.run_timing_count=run_count[0]
                names={pr.ffi.string(self.run_timing_animations[i].name).decode():i for i in range(run_count[0])}
                if 'run' not in names or not pr.is_model_animation_valid(self.player,self.run_timing_animations[names['run']]):
                    raise RuntimeError('Improved run animation is missing or incompatible with the player')
                self.run_timing_index=names['run']
                self.retarget_arm_animation(self.run_timing_animations[self.run_timing_index])
            jog_asset=ROOT/'art'/'temple'/'player_jog'/'jog.glb'
            if actor=='player' and jog_asset.is_file():
                jog_count=pr.ffi.new('int *')
                self.jog_animations=pr.load_model_animations(str(jog_asset),jog_count)
                self.jog_count=jog_count[0]
                names={pr.ffi.string(self.jog_animations[i].name).decode():i for i in range(jog_count[0])}
                if 'run' not in names or not pr.is_model_animation_valid(self.player,self.jog_animations[names['run']]):
                    raise RuntimeError('Jog animation is missing or incompatible with the player')
                self.jog_index=names['run']
                self.retarget_arm_animation(self.jog_animations[self.jog_index])
            for mesh in self.player.meshes[0:self.player.meshCount]:
                if mesh.boneCount != self.player.boneCount or not mesh.vboId[7] or not mesh.vboId[8]:
                    raise RuntimeError('GPU joint attributes were not uploaded')
            if self.player.boneCount > 32:
                raise RuntimeError('This character shader supports at most 32 bones')
            self.previous_pose = pr.ffi.new('Matrix[]',self.player.boneCount)
            self.previous_location = pr.get_shader_location(self.skin,'previousPose')
            self.blend_location = pr.get_shader_location(self.skin,'poseBlend')
            self.pose('idle' if actor=='player' else 'enemy_idle', 0.)
        except Exception:
            self.close()
            raise

    def load_shader(self, name):
        shader = pr.load_shader(str(ROOT/'shaders'/(name+'.vs')),str(ROOT/'shaders'/self.fragment_shader))
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
                                     ('time','inspection','windStrength','moonDirection','lampCount','lamps','opacity')}
        pr.set_shader_value(shader,self.locations[shader.id]['opacity'],pr.ffi.new('float[]',[1.]),pr.SHADER_UNIFORM_FLOAT)
        return shader

    def align_pistol_bind_pose(self):
        """Keep the rigid gun attached to the refined model's shorter wrist.

        Rebind only the in-memory copy. Sharing the player's rest rig also
        keeps the existing pose crossfade valid for both skinned meshes.
        """
        ids={pr.ffi.string(self.player.bones[i].name).decode():i for i in range(self.player.boneCount)}
        pistol_ids={pr.ffi.string(self.pistol.bones[i].name).decode():i for i in range(self.pistol.boneCount)}
        hand=ids['hand.R'];gun_hand=pistol_ids['hand.R']
        target=self.player.bindPose[hand].translation;source=self.pistol.bindPose[gun_hand].translation
        delta=(target.x-source.x,target.y-source.y,target.z-source.z)
        if max(abs(v) for v in delta)<1.e-5:return
        if ids!=pistol_ids:raise RuntimeError('Pistol and player joint order differs')
        for mesh in self.pistol.meshes[0:self.pistol.meshCount]:
            for i in range(mesh.vertexCount):
                for k in range(4):
                    if mesh.boneWeights[4*i+k]>.00001 and mesh.boneIds[4*i+k]!=gun_hand:
                        raise RuntimeError('Pistol proportion adjustment requires a rigid hand attachment')
                for axis,offset in enumerate(delta):mesh.vertices[3*i+axis]+=offset
            pr.update_mesh_buffer(mesh,0,mesh.vertices,mesh.vertexCount*3*pr.ffi.sizeof('float'),0)
        pr.ffi.memmove(self.pistol.bindPose,self.player.bindPose,self.player.boneCount*pr.ffi.sizeof('Transform'))

    def retarget_arm_animation(self,animation):
        """Shared overlays store global joint poses on the original arm rig."""
        ids={pr.ffi.string(self.player.bones[i].name).decode():i for i in range(self.player.boneCount)}
        def point(v):return v.x,v.y,v.z
        for side in ('L','R'):
            arm,forearm,hand=(ids[name+'.'+side] for name in ('arm','forearm','hand'))
            upper_scale=math.dist(point(self.player.bindPose[arm].translation),point(self.player.bindPose[forearm].translation))/UPPER_ARM
            forearm_scale=math.dist(point(self.player.bindPose[forearm].translation),point(self.player.bindPose[hand].translation))/FOREARM
            if abs(upper_scale-1.)<1.e-5 and abs(forearm_scale-1.)<1.e-5:continue
            for frame in range(animation.frameCount):
                poses=animation.framePoses[frame]
                elbow,wrist=arm_positions(point(poses[arm].translation),point(poses[forearm].translation),
                                          point(poses[hand].translation),upper_scale,forearm_scale)
                poses[forearm].translation=pr.Vector3(*elbow)
                poses[hand].translation=pr.Vector3(*wrist)

    def load_model(self, name, shader):
        folder=(ASSETS/'models' if name=='willow' else ROOT/'art'/'temple'/'combat' if name=='pistol' else self.asset_root)
        model = pr.load_model(str(folder/(name+'.glb')))
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
            self.pose_blend = min(1.,max(0.,dt)/.035) if clip=='recoil' else 0.
        else:
            self.pose_blend = min(1.,self.pose_blend+max(0.,dt)/(.035 if clip=='recoil' else .14))
        improved=(self.actor=='player' and clip=='run' and self.use_improved_run and self.run_timing_index is not None)
        jogging=(self.actor=='player' and clip=='run' and self.use_improved_run and self.run_style=='jog' and self.jog_index is not None)
        animation = (self.jog_animations[self.jog_index] if jogging else
                     self.run_timing_animations[self.run_timing_index] if improved else self.animations[self.clips[clip]])
        frame,next_frame,weight=animation_samples(phase,self.clip_seconds[clip],animation.frameCount)
        if (jogging or improved or (self.actor=='player' and self.variant=='refined' and clip in SMOOTH_PLAYER_CLIPS) or
            (self.actor=='chorus_grasper' and clip in SMOOTH_CHORUS_CLIPS)):
            self.interpolate_bones(self.player,'player',animation,frame,next_frame,weight)
            if self.pistol:self.interpolate_bones(self.pistol,'pistol',animation,frame,next_frame,weight)
        else:
            pr.update_model_animation_bones(self.player,animation,frame)
            if self.pistol:pr.update_model_animation_bones(self.pistol,animation,frame)
        pr.set_shader_value(self.skin,self.blend_location,pr.ffi.new('float[]',[self.pose_blend]),pr.SHADER_UNIFORM_FLOAT)
        self.clip, self.animation_frame = clip, frame

    def interpolate_bones(self,model,identity,animation,frame,next_frame,weight):
        """Smooth adjacent cyclic samples without disturbing clip crossfades."""
        pr.update_model_animation_bones(model,animation,frame)
        if weight<=1.e-8 or next_frame==frame:return
        length=model.boneCount*16
        for i in range(model.meshCount):
            key=(identity,i);saved=self._sample_buffers.get(key)
            if saved is None:
                saved=pr.ffi.new('float[]',length);self._sample_buffers[key]=saved
            pr.ffi.memmove(saved,model.meshes[i].boneMatrices,length*pr.ffi.sizeof('float'))
        pr.update_model_animation_bones(model,animation,next_frame)
        for i in range(model.meshCount):
            saved=self._sample_buffers[(identity,i)]
            current=pr.ffi.cast('float *',model.meshes[i].boneMatrices)
            for j in range(length):current[j]=saved[j]+(current[j]-saved[j])*weight

    def update(self, dt, moving, heading, travelled, running=False):
        if moving:
            goal = math.degrees(math.atan2(heading[0],heading[1]))
            delta = (goal-self.yaw+180)%360-180
            self.yaw += delta*min(1.,dt*12.)
            self.phase += travelled/stride_for('run' if running else 'walk',self.run_style if self.use_improved_run else 'legacy')
            self.pose('run' if running else 'walk',self.phase,dt)
        else:
            self.pose('idle',self.clock/2.,dt)

    def draw_player(self, x, floor, z):
        pr.draw_model_ex(self.player,pr.Vector3(x,floor,z),pr.Vector3(0,1,0),self.yaw,pr.Vector3(1,1,1),pr.WHITE)

    def draw_pistol(self,x,floor,z):
        if self.pistol:pr.draw_model_ex(self.pistol,pr.Vector3(x,floor,z),pr.Vector3(0,1,0),self.yaw,pr.Vector3(1,1,1),pr.WHITE)

    def draw_willow(self, x, z, angle=0.,opacity=1.):
        # Alpha-tested leaves write depth normally; both sides of each ribbon show.
        pr.rl.rlDisableBackfaceCulling()
        pr.set_shader_value(self.wind,self.locations[self.wind.id]['opacity'],pr.ffi.new('float[]',[opacity]),pr.SHADER_UNIFORM_FLOAT)
        if opacity<.999:pr.rl.rlDisableDepthMask()
        pr.draw_model_ex(self.willow,pr.Vector3(x,0,z),pr.Vector3(0,1,0),angle,pr.Vector3(1,1,1),pr.WHITE)
        if opacity<.999:pr.rl.rlEnableDepthMask()
        pr.set_shader_value(self.wind,self.locations[self.wind.id]['opacity'],pr.ffi.new('float[]',[1.]),pr.SHADER_UNIFORM_FLOAT)
        pr.rl.rlEnableBackfaceCulling()

    def close(self):
        if self.jog_animations is not None:
            pr.unload_model_animations(self.jog_animations,self.jog_count)
            self.jog_animations = None
        if self.run_timing_animations is not None:
            pr.unload_model_animations(self.run_timing_animations,self.run_timing_count)
            self.run_timing_animations = None
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
        self._sample_buffers.clear()
