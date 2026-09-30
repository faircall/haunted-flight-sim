"""Offline compiler of native scene inputs, alongside renderer parity fixtures.

The C renderer receives authored geometry and wind definitions, not pre-evaluated
foliage vertices or visibility polygons for these stages. Python output is kept
only as expected values for the validation harness.
"""
import struct
from c_port.recording import PACK,blob,ffi
from c_port.scene_reference import PackedGeometry,light_data,wind_data,part_data

class NativeSceneRecorder:
    def __init__(self,recorder):
        self.rec=recorder;recorder.native_scene=self
        self.grids={};self.polygons={};self.jobs={};self.prepared={};self.locations={}
        self.trees={};self.buffers={};self.tree_values={};self.compose_jobs=[];self.active_part=-1
        self.fan=None;self.building_visibility=False
        self.fan_count=self.pose_count=self.visibility_count=0

    def grid_id(self,grid):
        identity=id(grid)
        if identity not in self.rec.grid_ids:
            index=len(self.rec.grid_ids);self.rec.grid_ids[identity]=(index,grid)
            self.rec.emit('HFGrid',PACK('Iii dd',index,grid['map_width'],grid['map_height'],grid['tile_width'],grid['tile_height'])+
                          blob(bytes(grid['shape_codes'])))
        index=self.rec.grid_ids[identity][0]
        if identity not in self.grids:
            packed=PackedGeometry(grid);g=packed.value
            self.rec.emit('HFSceneGeometry',PACK('I5I2d',index,len(packed.vertices),len(packed.buckets),len(packed.indices),
                g.buckets_x,g.buckets_y,g.bucket_width,g.bucket_height)+blob(bytes(packed.vertices))+
                blob(bytes(packed.buckets))+blob(bytes(packed.indices)))
            self.grids[identity]=packed
        return index

    def register_polygon(self,light,position,grid,config,result):
        gid=self.grid_id(grid);spec=light_data(light,position,config)
        owner=light.get('owner_id') or light.get('effect_owner')
        key=(gid,owner,bytes(spec)[16:] if owner else bytes(spec))
        if key not in self.jobs:self.jobs[key]=len(self.jobs)
        jid=self.jobs[key]
        # Strong references prevent Python id reuse while exporting cached fans.
        record=(jid,gid,spec,result)
        self.polygons[id(result['polygon'])]=(result['polygon'],record,False)
        self.polygons[id(result['unbiased_polygon'])]=(result['unbiased_polygon'],record,True)
        return result

    def ensure_visibility(self,record):
        jid,gid,spec,result=record;signature=(gid,bytes(spec))
        if self.prepared.get(jid)==signature:return
        self.prepared[jid]=signature
        expected=PACK('6I',*(result[key] for key in ('ray_count','baseline_ray_count','corner_candidate_count',
                         'adaptive_rays_added','dda_tile_steps','max_dda_tile_steps_for_one_ray')))
        expected+=blob(b''.join(PACK('2d',p['x'],p['y']) for p in result['polygon']))
        self.rec.emit('HFVisibility',PACK('II',jid,gid)+blob(bytes(spec))+expected)
        self.visibility_count+=1

    def install(self):
        import g_light_visibility as lv
        import g_graphics as graphics
        import g_render_order as order
        import g_tree_render as tree
        original_visibility=lv.build_light_visibility_polygon_dda
        def visibility(light,position,grid,visibility_config=None):
            previous=self.building_visibility;self.building_visibility=True
            try:result=original_visibility(light,position,grid,visibility_config)
            finally:self.building_visibility=previous
            return self.register_polygon(light,position,grid,visibility_config,result)
        lv.build_light_visibility_polygon_dda=visibility
        original_fan=graphics.draw_light_visibility_polygon
        def fan(light,position,polygon,camera):
            found=self.polygons.get(id(polygon));previous=self.fan
            if found and self.rec.active:
                _,record,unbiased=found;self.ensure_visibility(record)
                self.fan=(record[0],unbiased,order.world_camera_offset(camera),position,lv.visibility_type(light)=='point')
            try:return original_fan(light,position,polygon,camera)
            finally:self.fan=previous
        graphics.draw_light_visibility_polygon=fan

        original_mesh=tree.update_mesh
        def mesh(runtime,part,profile,elapsed,position):
            result,angle=original_mesh(runtime,part,profile,elapsed,position)
            if isinstance(result,dict):
                p=part_data(part);w=wind_data(profile)
                key=(bytes(p),bytes(w),tuple(position),profile.get('tree_mesh')=='strips')
                if key not in self.trees:
                    self.trees[key]=len(self.trees);index=self.trees[key]
                    self.rec.emit('HFTreeDefinition',PACK('I',index)+blob(bytes(p))+blob(bytes(w))+
                                  PACK('2dI',*position,int(key[-1])))
                index=self.trees[key];values=bytes(ffi.buffer(result['deformation'],64))
                self.rec.emit('HFTreePose',PACK('Idd',index,elapsed,angle)+values)
                pointer=int(ffi.cast('uintptr_t',result['deformation']))
                self.buffers[pointer]=(result['deformation'],index)
                self.tree_values[index]=(elapsed,angle,values)
                self.pose_count+=1
            return result,angle
        tree.update_mesh=mesh
        original_compose=tree.compose
        def compose(target,textures,meshes,runtime,angles,response=False,parts=tree.rig.PARTS):
            previous=(self.compose_jobs,self.active_part)
            self.compose_jobs=[-1]+[self.buffers[int(ffi.cast('uintptr_t',meshes[p['name']]['deformation']))][1]
                                    if isinstance(meshes.get(p['name']),dict) else -1 for p in parts]
            self.active_part=-1
            try:return original_compose(target,textures,meshes,runtime,angles,response,parts)
            finally:self.compose_jobs,self.active_part=previous
        tree.compose=compose

        # The underlying recorder sees the return value, so collect uniform names
        # in the normal API wrapper without changing the reference game's result.
        import pyray as pr
        old_get=pr.get_shader_location
        def get_location(shader,name):
            loc=old_get(shader,name)
            self.locations[(int(shader.id),loc)]=name.decode() if isinstance(name,bytes) else name
            return loc
        pr.get_shader_location=get_location

    def invoke(self,name,args):
        if name=='DrawTriangleFan' and self.fan is not None and self.rec.active:
            jid,unbiased,camera,origin,closed=self.fan
            self.rec.emit('HFVisibilityFan',PACK('III4d',jid,int(unbiased),int(closed),*camera,origin['x'],origin['y'])+
                          self.rec.encode(ffi.typeof('Color'),args[2]))
            self.fan_count+=1
            return True
        if name=='SetShaderValueV' and int(args[3])==3 and int(args[4])==4:
            pointer=int(ffi.cast('uintptr_t',args[2]));found=self.buffers.get(pointer)
            if found:
                self.rec.emit('HFTreeUniform',PACK('IIi',found[1],self.rec.ref('shader',args[0].id),args[1]))
                return True
        if name=='SetShaderValue' and self.compose_jobs:
            uniform=self.locations.get((int(args[0].id),int(args[1])))
            if uniform=='partSeed':
                index=int(struct.unpack('<f',bytes(ffi.buffer(args[2],4)))[0])
                self.active_part=self.compose_jobs[index] if index<len(self.compose_jobs) else -1
            elif uniform=='bendAngle' and self.active_part>=0:
                self.rec.emit('HFTreeAngle',PACK('IIi',self.active_part,self.rec.ref('shader',args[0].id),args[1]))
                return True
        return False

    def end_frame(self):
        self.buffers.clear()
