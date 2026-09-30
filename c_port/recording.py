"""Export raylib work, never final frame images, for native renderer comparison.

Python is an offline scene/reference producer. The binary stores source assets,
mesh data, uniforms and drawing operations. C executes the actual shaders/FBOs.
Raylib's C API provides a useful deterministic boundary for an incremental port.
"""
import inspect
import json
from pathlib import Path
import struct
import pyray as pr

ROOT=Path(__file__).resolve().parent
ffi=pr.ffi
PACK=lambda fmt,*v:struct.pack('<'+fmt,*v)
SIMPLE='''BeginTextureMode EndTextureMode BeginShaderMode EndShaderMode
BeginBlendMode EndBlendMode ClearBackground BeginScissorMode EndScissorMode
DrawTexture DrawTextureRec DrawTexturePro DrawTextureEx DrawRectangle
DrawRectangleRec DrawRectanglePro DrawRectangleLines DrawRectangleLinesEx
DrawCircle DrawCircleV DrawCircleGradient DrawEllipse DrawLine DrawLineV DrawLineEx
DrawTriangle DrawPixel DrawPixelV DrawText DrawTextEx SetTextureFilter SetTextureWrap
rlBegin rlEnd rlColor4ub rlNormal3f rlTexCoord2f rlVertex2f rlVertex3f
rlPushMatrix rlPopMatrix rlTranslatef rlScalef rlRotatef
rlDisableBackfaceCulling rlEnableBackfaceCulling rlDrawRenderBatchActive
rlSetBlendFactors rlSetBlendFactorsSeparate'''.split()
SPECIAL='''LoadTexture LoadTextureFromImage LoadRenderTexture LoadShader LoadShaderFromMemory
GetShaderLocation SetShaderValue SetShaderValueV SetShaderValueTexture
UnloadTexture UnloadRenderTexture UnloadShader UpdateTexture
UploadMesh DrawMesh UnloadMesh UpdateMeshBuffer rlSetTexture DrawTriangleFan DrawTriangleStrip'''.split()
RESOURCE={'Texture','Texture2D','RenderTexture','RenderTexture2D','Shader','Font'}

def string(value):
    if value is None or value==ffi.NULL:return b''
    if isinstance(value,str):return value.encode('utf8')
    if isinstance(value,bytes):return value
    return ffi.string(value)

def blob(value):return PACK('I',len(value))+value

class Recorder:
    def __init__(self):
        self.real=pr.rl;self.original={};self.spec={};self.commands=bytearray()
        names=SIMPLE+SPECIAL+['HFTexture','HFTarget','HFShader','HFLocation','HFUniform','HFSampler','HFFont','HFGrid','HFRay',
                             'HFSceneGeometry','HFVisibility','HFVisibilityFan','HFTreeDefinition','HFTreePose','HFTreeUniform','HFTreeAngle']
        self.ops={name:index+1 for index,name in enumerate(names)}
        self.maps={name:{} for name in ('texture','target','shader','mesh','font')}
        self.next={name:2 for name in self.maps};self.active=False;self.suspended=False
        self.frame_counts={};self.all_counts={};self.frames=[]
        self.map_texture_default=None;self.shader_default=None
        self.grid_ids={}
        self.native_scene=None

    def emit(self,name,data):
        if self.suspended:return
        if name not in self.ops:self.ops[name]=len(self.ops)+1
        self.commands+=PACK('II',self.ops[name],len(data))+data
        self.all_counts[name]=self.all_counts.get(name,0)+1
        if self.active:self.frame_counts[name]=self.frame_counts.get(name,0)+1

    def new(self,kind,old):
        value=self.next[kind];self.next[kind]+=1;self.maps[kind][int(old)]=value;return value

    def ref(self,kind,old):
        old=int(old)
        if not old:return 0
        if kind=='shader' and old==int(self.real.rlGetShaderIdDefault()):return 1
        if kind=='texture' and old==int(self.real.rlGetTextureIdDefault()):return 1
        return self.maps[kind][old]

    def texture(self,value):
        if not int(value.id):return 0
        try:return self.ref('texture',value.id)
        except KeyError:
            # Font atlas/default assets created internally by raylib.
            image=self.real.LoadImageFromTexture(value)
            identity=self.new('texture',value.id)
            self.emit('HFTexture',PACK('I',identity)+self.image(image))
            self.real.UnloadImage(image)
            return identity

    def image(self,value):
        size=self.real.GetPixelDataSize(value.width,value.height,value.format)
        if value.mipmaps!=1:raise ValueError('Export expects base-level source images')
        return PACK('iii',value.width,value.height,value.format)+blob(bytes(ffi.buffer(value.data,size)))

    def font(self,value):
        old=int(value.texture.id)
        if old in self.maps['font']:return self.maps['font'][old]
        identity=self.new('font',old);texture=self.texture(value.texture)
        data=PACK('IiiiI',identity,value.baseSize,value.glyphCount,value.glyphPadding,texture)
        for i in range(value.glyphCount):
            r=value.recs[i];g=value.glyphs[i]
            data+=PACK('ffffiiii',r.x,r.y,r.width,r.height,g.value,g.offsetX,g.offsetY,g.advanceX)
        self.emit('HFFont',data);return identity

    def encode(self,t,value):
        name=t.cname.removeprefix('struct ')
        if name in ('Texture','Texture2D'):return PACK('I',self.texture(value))
        if name in ('RenderTexture','RenderTexture2D'):return PACK('I',self.ref('target',value.id))
        if name=='Shader':return PACK('I',self.ref('shader',value.id))
        if name=='Font':return PACK('I',self.font(value))
        if t.kind=='struct':
            if isinstance(value,(tuple,list)):value=ffi.new(t.cname+' *',value)[0]
            return b''.join(self.encode(f.type,getattr(value,k)) for k,f in t.fields)
        if t.kind=='pointer' and t.item.cname=='char':return blob(string(value)+b'\0')
        if name=='float':return PACK('f',float(value))
        if name=='double':return PACK('d',float(value))
        if t.kind in ('primitive','enum'):return PACK('i',int(value))
        raise ValueError((name,value))

    def invoke(self,name,function,args):
        if self.suspended:return function(*args)
        if self.native_scene is not None and self.native_scene.invoke(name,args):
            return function(*args)
        if name in SIMPLE:
            if self.active or name.startswith('Set'):
                # Original pyray wrappers do conversions, so callers here always
                # provide native argument values at the C boundary.
                self.emit(name,b''.join(self.encode(t,a) for t,a in zip(self.spec[name],args)))
            return function(*args)
        if name in ('LoadTexture','LoadTextureFromImage'):
            result=function(*args);identity=self.new('texture',result.id)
            im=args[0] if name=='LoadTextureFromImage' else self.real.LoadImageFromTexture(result)
            self.emit('HFTexture',PACK('I',identity)+self.image(im))
            if name=='LoadTexture':self.real.UnloadImage(im)
            return result
        if name=='LoadRenderTexture':
            result=function(*args);identity=self.new('target',result.id);tex=self.new('texture',result.texture.id)
            self.emit('HFTarget',PACK('IIii',identity,tex,*args));return result
        if name in ('LoadShader','LoadShaderFromMemory'):
            source=[string(v) for v in args]
            if name=='LoadShader':source=[Path(v.decode()).read_bytes() if v else b'' for v in source]
            result=function(*args)
            if result.id==self.real.rlGetShaderIdDefault():raise RuntimeError('Shader compilation failed')
            identity=self.new('shader',result.id)
            self.emit('HFShader',PACK('I',identity)+b''.join(blob(v+b'\0') for v in source));return result
        if name=='GetShaderLocation':
            result=function(*args)
            self.emit('HFLocation',PACK('Ii',self.ref('shader',args[0].id),result)+blob(string(args[1])+b'\0'))
            return result
        if name in ('SetShaderValue','SetShaderValueV'):
            shader,loc,values,kind=args[:4];count=int(args[4]) if len(args)>4 else 1
            width=(1,2,3,4,1,2,3,4,1)[int(kind)]
            self.emit('HFUniform',PACK('Iiii',self.ref('shader',shader.id),loc,kind,count)+blob(bytes(ffi.buffer(values,count*width*4))))
        elif name=='SetShaderValueTexture':
            shader,loc,tex=args
            self.emit('HFSampler',PACK('IiI',self.ref('shader',shader.id),loc,self.texture(tex)))
        elif name=='rlSetTexture':
            if self.active:self.emit(name,PACK('I',self.ref('texture',args[0])))
        elif name in ('UnloadTexture','UnloadRenderTexture','UnloadShader'):
            kind={'UnloadTexture':'texture','UnloadRenderTexture':'target','UnloadShader':'shader'}[name]
            self.emit(name,PACK('I',self.ref(kind,args[0].id)))
        elif name=='UpdateTexture':
            tex,data=args;size=self.real.GetPixelDataSize(tex.width,tex.height,tex.format)
            self.emit(name,PACK('I',self.texture(tex))+blob(bytes(ffi.buffer(data,size))))
        elif name=='UploadMesh':
            result=function(*args);m=args[0][0];identity=self.new('mesh',m.vaoId)
            data=PACK('Iiii',identity,m.vertexCount,m.triangleCount,int(args[1]))
            for pointer,size in ((m.vertices,m.vertexCount*12),(m.texcoords,m.vertexCount*8),
                                  (m.normals,m.vertexCount*12),(m.indices,m.triangleCount*6),
                                  (m.colors,m.vertexCount*4),(m.texcoords2,m.vertexCount*8),(m.tangents,m.vertexCount*16)):
                data+=blob(bytes(ffi.buffer(pointer,size)) if pointer!=ffi.NULL else b'')
            self.emit(name,data);return result
        elif name=='DrawMesh':
            m,mat,matrix=args;data=PACK('II',self.ref('mesh',m.vaoId),self.ref('shader',mat.shader.id))
            for index in range(12):
                slot=mat.maps[index];color=slot.color
                data+=PACK('I4Bfi',self.texture(slot.texture),color.r,color.g,color.b,color.a,slot.value,
                           mat.shader.locs[int(pr.ShaderLocationIndex.SHADER_LOC_MAP_ALBEDO)+index])
            data+=bytes(ffi.buffer(ffi.addressof(matrix),ffi.sizeof('Matrix')))
            self.emit(name,data)
        elif name=='UnloadMesh':self.emit(name,PACK('I',self.ref('mesh',args[0].vaoId)))
        elif name=='UpdateMeshBuffer':
            m,index,data,size,offset=args
            self.emit(name,PACK('Iii',self.ref('mesh',m.vaoId),index,offset)+blob(bytes(ffi.buffer(data,size))))
        elif name in ('DrawTriangleFan','DrawTriangleStrip'):
            points,count,color=args
            if self.active:self.emit(name,PACK('i',count)+bytes(ffi.buffer(points,count*8))+self.encode(ffi.typeof('Color'),color))
        else:raise ValueError(name)
        return function(*args)

    def install(self):
        recorder=self
        class Proxy:
            def __getattr__(self,name):
                if name in recorder.original:return recorder.original[name]
                return getattr(recorder.real,name)
        for name in SIMPLE+SPECIAL:
            function=getattr(self.real,name);self.spec[name]=ffi.typeof(function).args
            def invoke(*args,_name=name,_function=function):return self.invoke(_name,_function,args)
            self.original[name]=invoke
            uname=pr._underscore(name).replace('3_d','_3d').replace('2_d','_2d')
            # Reuse pyray's argument coercion around the intercepted C function.
            wrapped=pr._wrap_function(function)
            closure=dict(zip(wrapped.__code__.co_freevars,wrapped.__closure__))
            closure['original_func'].cell_contents=invoke
            setattr(pr,uname,wrapped)
        pr.rl=Proxy()

    def start_frame(self):
        result=bytes(self.commands);self.commands.clear();self.frame_counts={};self.active=True
        return result

    def end_frame(self):
        self.active=False;result=bytes(self.commands);self.commands.clear();return result

    def generate_dispatch(self):
        # Primitive arguments are read into locals in order: C argument
        # evaluation order must never choose the binary-stream read order.
        structs={}
        def reader(t):
            n=t.cname.removeprefix('struct ')
            if n in ('Texture','Texture2D'):return 'textures[rd_id(r)]'
            if n in ('RenderTexture','RenderTexture2D'):return 'targets[rd_id(r)]'
            if n=='Shader':return 'shaders[rd_id(r)]'
            if n=='Font':return 'fonts[rd_id(r)]'
            if t.kind=='pointer' and t.item.cname=='char':return '(const char *)rd_blob(r,NULL)'
            if t.kind=='struct':
                if n not in structs:
                    body=''.join(f'v.{key}={reader(f.type)};' for key,f in t.fields)
                    structs[n]=f'static {n} rd_{n}(Reader *r) {{ {n} v;{body}return v; }}'
                return f'rd_{n}(r)'
            return {'float':'rd_float(r)','double':'rd_double(r)'}.get(n,'rd_i32(r)')
        cases=[]
        for name,op in self.ops.items():
            if name not in SIMPLE:continue
            types=self.spec[name];declarations=[]
            for i,t in enumerate(types):
                typename='const char *' if t.kind=='pointer' and t.item.cname=='char' else t.cname
                declarations.append(f'{typename} a{i}={reader(t)};')
            cases.append(f'case OP_{name}: {{ '+''.join(declarations)+name+'('+','.join(f'a{i}' for i in range(len(types)))+');break; }')
        text='/* Generated from raylib C signatures by recording.py; do not edit. */\n'
        text+='enum { '+', '.join(f'OP_{n}={v}' for n,v in self.ops.items())+' };\n'
        text+='\n'.join(structs.values())+'\n'
        text+='#define HF_SIMPLE_CASES '+(' \\\n'.join(cases))+'\n'
        (ROOT/'src'/'dispatch.h').write_text(text,encoding='utf8')

if __name__=='__main__':
    recorder=Recorder();recorder.install();recorder.generate_dispatch()
