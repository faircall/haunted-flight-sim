/* Native render-pass comparison harness. No Python runtime or final-frame video.
 * Source textures/meshes, uniforms and raylib commands come from export_scene.py.
 * Visibility construction and tree poses run in C. Remaining preparation and
 * gameplay still come from offline traces; see NATIVE_PROGRESS.md. */
#include "raylib.h"
#include "rlgl.h"
#include "raymath.h"
#include "visibility.h"
#include "native_scene.h"
#include "allocation_audit.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>

#define RESOURCES 8192
#define LOCATIONS 512
typedef struct { const unsigned char *p,*end; } Reader;
typedef struct { uint32_t scene,index,measured;uint64_t expected;Reader commands; } Frame;
static Texture2D textures[RESOURCES];
static RenderTexture2D targets[RESOURCES];
static Shader shaders[RESOURCES];
static Mesh meshes[RESOURCES];
static Font fonts[RESOURCES];
static HFGrid grids[128];
static int locations[RESOURCES][LOCATIONS];
static uint64_t ray_count,ray_errors;
static float vector_scratch[131072];
static int source_frame=-1;
static HFMemory memory;
static bool resources_ready;
static bool texture_owned[RESOURCES];
static const void *texture_initial_pixels[RESOURCES];
static bool texture_dirty[RESOURCES];
#if defined(_WIN32)
#define GL_CALL __stdcall
#else
#define GL_CALL
#endif
typedef void (*GLProc)(void);
extern GLProc glfwGetProcAddress(const char *name);
typedef struct {
    void (GL_CALL *gen)(int,unsigned *);
    void (GL_CALL *begin)(unsigned,unsigned);
    void (GL_CALL *end)(unsigned);
    void (GL_CALL *result)(unsigned,unsigned,uint64_t *);
    void (GL_CALL *destroy)(int,const unsigned *);
    unsigned id;
    bool enabled;
} GPUTimer;
static GPUTimer gpu_timer(void) {
    GPUTimer t={0};GLProc proc;
#define LOAD(member,name) proc=glfwGetProcAddress(name);memcpy(&t.member,&proc,sizeof(proc))
    LOAD(gen,"glGenQueries");LOAD(begin,"glBeginQuery");LOAD(end,"glEndQuery");
    LOAD(result,"glGetQueryObjectui64v");LOAD(destroy,"glDeleteQueries");
#undef LOAD
    t.enabled=t.gen&&t.begin&&t.end&&t.result&&t.destroy;
    if(t.enabled)t.gen(1,&t.id);
    return t;
}
typedef struct {
    void (GL_CALL *bind)(unsigned,unsigned);
    void (GL_CALL *pack)(unsigned,int);
    void (GL_CALL *read)(unsigned,int,unsigned,unsigned,void *);
} GPUReadback;
static GPUReadback gpu_readback(void) {
    GPUReadback value={0};GLProc proc;
#define READ_PROC(member,name) proc=glfwGetProcAddress(name);memcpy(&value.member,&proc,sizeof(proc))
    READ_PROC(bind,"glBindTexture");READ_PROC(pack,"glPixelStorei");READ_PROC(read,"glGetTexImage");
#undef READ_PROC
    return value;
}
static void fail(const char *message) { fprintf(stderr,"Native error (frame %d): %s\n",source_frame,message);exit(1); }
static const unsigned char *rd_bytes(Reader *r,size_t n) {
    if(n>(size_t)(r->end-r->p)) fail("truncated command data");
    const unsigned char *p=r->p;r->p+=n;return p;
}
static uint32_t rd_u32(Reader *r) { uint32_t v;memcpy(&v,rd_bytes(r,4),4);return v; }
static int32_t rd_i32(Reader *r) { return (int32_t)rd_u32(r); }
static uint64_t rd_u64(Reader *r) { uint64_t v;memcpy(&v,rd_bytes(r,8),8);return v; }
static uint32_t rd_id(Reader *r) { uint32_t id=rd_u32(r);if(id>=RESOURCES) fail("resource index out of range");return id; }
static float rd_float(Reader *r) { float v;memcpy(&v,rd_bytes(r,4),4);return v; }
static double rd_double(Reader *r) { double v;memcpy(&v,rd_bytes(r,8),8);return v; }
static const unsigned char *rd_blob(Reader *r,uint32_t *size) { uint32_t n=rd_u32(r);if(size)*size=n;return rd_bytes(r,n); }
static void *copy_blob(Reader *r) { uint32_t n;const void *p=rd_blob(r,&n);if(!n)return NULL;void *v=hf_arena_push(&memory.assets,n,1,64,0);if(!v)fail("asset arena exhausted");memcpy(v,p,n);return v; }
static int location(uint32_t shader,int old) {
    if(old<0)return -1;
    if(old>=LOCATIONS)fail("uniform location out of range");
    return locations[shader][old];
}
#include "dispatch.h"
#include "scene_commands.h"
static bool creates_resource(uint32_t op) {
    return op==OP_HFTexture || op==OP_HFTarget || op==OP_HFShader || op==OP_HFLocation ||
           op==OP_HFFont || op==OP_UploadMesh;
}
static void unload_arena_mesh(Mesh mesh) {
    /* CPU attribute storage is borrowed from our arena. Raylib owns vboId. */
    mesh.vertices=NULL;mesh.texcoords=NULL;mesh.texcoords2=NULL;mesh.normals=NULL;
    mesh.tangents=NULL;mesh.colors=NULL;mesh.indices=NULL;mesh.animVertices=NULL;
    mesh.animNormals=NULL;mesh.boneIds=NULL;mesh.boneWeights=NULL;
    UnloadMesh(mesh);
}

static void execute(Reader commands) {
    while(commands.p<commands.end) {
        uint32_t op=rd_u32(&commands),size=rd_u32(&commands);
        const unsigned char *bytes=rd_bytes(&commands,size);Reader reader={bytes,bytes+size},*r=&reader;
        if(resources_ready && (creates_resource(op) || op==OP_UnloadTexture || op==OP_UnloadRenderTexture ||
                               op==OP_UnloadShader || op==OP_UnloadMesh))continue;
        if(execute_native(op,r)) {
            if(r->p!=r->end)fail("native command length mismatch");
            continue;
        }
        switch(op) {
        HF_SIMPLE_CASES
        case OP_HFTexture: {
            uint32_t id=rd_id(r);int w=rd_i32(r),h=rd_i32(r),format=rd_i32(r);uint32_t n;
            const void *pixels=rd_blob(r,&n);
            if(w<=0 || h<=0 || n!=(uint32_t)GetPixelDataSize(w,h,format))fail("invalid texture data");
            if(textures[id].id)UnloadTexture(textures[id]);
            textures[id]=LoadTextureFromImage((Image){(void*)pixels,w,h,1,format});texture_owned[id]=true;
            texture_initial_pixels[id]=pixels;break;
        }
        case OP_HFTarget: {
            uint32_t id=rd_id(r),tex=rd_id(r);int w=rd_i32(r),h=rd_i32(r);
            if(targets[id].id)UnloadRenderTexture(targets[id]);
            targets[id]=LoadRenderTexture(w,h);textures[tex]=targets[id].texture;break;
        }
        case OP_HFShader: {
            uint32_t id=rd_id(r);const char *vs=(const char*)rd_blob(r,NULL),*fs=(const char*)rd_blob(r,NULL);
            if(shaders[id].id)UnloadShader(shaders[id]);
            shaders[id]=LoadShaderFromMemory(*vs?vs:NULL,*fs?fs:NULL);
            if(shaders[id].id==rlGetShaderIdDefault())fail("shader failed to compile");
            for(int i=0;i<LOCATIONS;i++)locations[id][i]=-1;
            break;
        }
        case OP_HFLocation: {
            uint32_t id=rd_id(r);int old=rd_i32(r);const char *name=(const char*)rd_blob(r,NULL);
            if(old>=LOCATIONS)fail("uniform index too large");
            if(old>=0) { locations[id][old]=GetShaderLocation(shaders[id],name);if(locations[id][old]<0)fail(name); }
            break;
        }
        case OP_HFUniform: {
            uint32_t id=rd_id(r);int loc=rd_i32(r),type=rd_i32(r),count=rd_i32(r);uint32_t n;
            const void *data=rd_blob(r,&n);if(n>sizeof(vector_scratch))fail("uniform overflow");memcpy(vector_scratch,data,n);
            SetShaderValueV(shaders[id],location(id,loc),vector_scratch,type,count);break;
        }
        case OP_HFSampler: {
            uint32_t id=rd_id(r);int loc=rd_i32(r);uint32_t tex=rd_id(r);
            SetShaderValueTexture(shaders[id],location(id,loc),textures[tex]);break;
        }
        case OP_HFFont: {
            uint32_t id=rd_id(r);Font f={0};f.baseSize=rd_i32(r);f.glyphCount=rd_i32(r);f.glyphPadding=rd_i32(r);f.texture=textures[rd_id(r)];
            if(f.glyphCount<1 || f.glyphCount>65536)fail("font size invalid");
            if(fonts[id].recs)fail("duplicate font definition");
            f.recs=HF_PUSH(&memory.assets,Rectangle,f.glyphCount);f.glyphs=HF_PUSH_ZERO(&memory.assets,GlyphInfo,f.glyphCount);
            if(!f.recs || !f.glyphs)fail("font arena exhausted");
            for(int i=0;i<f.glyphCount;i++) {
                f.recs[i]=rd_Rectangle(r);f.glyphs[i].value=rd_i32(r);f.glyphs[i].offsetX=rd_i32(r);
                f.glyphs[i].offsetY=rd_i32(r);f.glyphs[i].advanceX=rd_i32(r);
            }
            fonts[id]=f;break;
        }
        case OP_UnloadTexture: { uint32_t id=rd_id(r);if(textures[id].id)UnloadTexture(textures[id]);textures[id]=(Texture2D){0};break; }
        case OP_UnloadRenderTexture: { uint32_t id=rd_id(r);if(targets[id].id)UnloadRenderTexture(targets[id]);targets[id]=(RenderTexture2D){0};break; }
        case OP_UnloadShader: { uint32_t id=rd_id(r);if(shaders[id].id)UnloadShader(shaders[id]);shaders[id]=(Shader){0};break; }
        case OP_UpdateTexture: { uint32_t id=rd_id(r);const void *data=rd_blob(r,NULL);UpdateTexture(textures[id],data);texture_dirty[id]=true;break; }
        case OP_rlSetTexture: { uint32_t id=rd_id(r);rlSetTexture(textures[id].id);break; }
        case OP_UploadMesh: {
            uint32_t id=rd_id(r);Mesh m={0};m.vertexCount=rd_i32(r);m.triangleCount=rd_i32(r);int dynamic=rd_i32(r);
            m.vertices=copy_blob(r);m.texcoords=copy_blob(r);m.normals=copy_blob(r);m.indices=copy_blob(r);
            m.colors=copy_blob(r);m.texcoords2=copy_blob(r);m.tangents=copy_blob(r);
            if(meshes[id].vaoId)unload_arena_mesh(meshes[id]);
            UploadMesh(&m,dynamic);meshes[id]=m;break;
        }
        case OP_DrawMesh: {
            uint32_t mesh=rd_id(r),shader=rd_id(r);
            MaterialMap maps[12]={0};int old[12];
            for(int i=0;i<12;i++) {
                maps[i].texture=textures[rd_id(r)];memcpy(&maps[i].color,rd_bytes(r,4),4);
                maps[i].value=rd_float(r);int loc=rd_i32(r);
                old[i]=shaders[shader].locs[SHADER_LOC_MAP_ALBEDO+i];
                if(maps[i].texture.id && location(shader,loc)>=0)shaders[shader].locs[SHADER_LOC_MAP_ALBEDO+i]=location(shader,loc);
            }
            Matrix matrix;memcpy(&matrix,rd_bytes(r,sizeof(Matrix)),sizeof(Matrix));
            Material mat={0};mat.shader=shaders[shader];mat.maps=maps;
            DrawMesh(meshes[mesh],mat,matrix);
            for(int i=0;i<12;i++)shaders[shader].locs[SHADER_LOC_MAP_ALBEDO+i]=old[i];
            break;
        }
        case OP_UnloadMesh: { uint32_t id=rd_id(r);if(meshes[id].vaoId)unload_arena_mesh(meshes[id]);meshes[id]=(Mesh){0};break; }
        case OP_UpdateMeshBuffer: {
            uint32_t id=rd_id(r);int index=rd_i32(r),offset=rd_i32(r);uint32_t n;const void *data=rd_blob(r,&n);
            UpdateMeshBuffer(meshes[id],index,data,n,offset);break;
        }
        case OP_DrawTriangleFan: case OP_DrawTriangleStrip: {
            int count=rd_i32(r);if(count<0 || (size_t)count*8>sizeof(vector_scratch))fail("vertex overflow");
            memcpy(vector_scratch,rd_bytes(r,count*8),count*8);Color color=rd_Color(r);
            if(op==OP_DrawTriangleFan)DrawTriangleFan((Vector2*)vector_scratch,count,color);
            else DrawTriangleStrip((Vector2*)vector_scratch,count,color);
            break;
        }
        case OP_HFGrid: {
            uint32_t id=rd_u32(r);if(id>=128)fail("too many collision grids");
            int w=rd_i32(r),h=rd_i32(r);double tw=rd_double(r),th=rd_double(r);uint32_t n;const uint8_t *p=rd_blob(r,&n);
            if(w<=0 || h<=0 || n!=(uint32_t)(w*h))fail("invalid collision grid");
            grids[id]=(HFGrid){w,h,tw,th,p};break;
        }
        case OP_HFRay: {
            uint32_t id=rd_u32(r);if(id>=128)fail("invalid collision grid id");
            double ox=rd_double(r),oy=rd_double(r),dx=rd_double(r),dy=rd_double(r),distance=rd_double(r);
            HFHit expected={0};expected.distance=rd_double(r);expected.normal_x=rd_double(r);expected.normal_y=rd_double(r);
            expected.hit=rd_i32(r);expected.tile_x=rd_i32(r);expected.tile_y=rd_i32(r);expected.tile_index=rd_i32(r);
            expected.shape=rd_i32(r);expected.edge=rd_i32(r);expected.steps=rd_i32(r);
            HFHit actual=hf_light_ray(&grids[id],ox,oy,dx,dy,distance);ray_count++;
            if(actual.hit!=expected.hit || actual.steps!=expected.steps || (actual.hit &&
                (actual.tile_x!=expected.tile_x || actual.tile_y!=expected.tile_y || actual.shape!=expected.shape || actual.edge!=expected.edge ||
                 fabs(actual.distance-expected.distance)>1e-9 || fabs(actual.normal_x-expected.normal_x)>1e-9 || fabs(actual.normal_y-expected.normal_y)>1e-9)))ray_errors++;
            break;
        }
        default:fprintf(stderr,"Unknown opcode %u\n",op);fail("unsupported command");
        }
        if(r->p!=r->end)fail("command length mismatch");
    }
}
static void preload_gpu(Reader commands) {
    while(commands.p<commands.end) {
        const unsigned char *start=commands.p;
        uint32_t op=rd_u32(&commands),size=rd_u32(&commands);rd_bytes(&commands,size);
        if(creates_resource(op))execute((Reader){start,commands.p});
    }
}
static void unload_gpu(void) {
    for(unsigned i=2;i<RESOURCES;i++) {
        if(meshes[i].vaoId)unload_arena_mesh(meshes[i]);
        if(targets[i].id)UnloadRenderTexture(targets[i]);
        if(texture_owned[i] && textures[i].id)UnloadTexture(textures[i]);
        if(shaders[i].id)UnloadShader(shaders[i]);
    }
}

static uint64_t hash_rgb(Image image) {
    if(image.format!=PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)fail("unexpected render-target readback format");
    const unsigned char *p=image.data;uint64_t h=UINT64_C(14695981039346656037);
    for(int i=0;i<image.width*image.height;i++)for(int j=0;j<3;j++)h=(h^p[i*4+j])*UINT64_C(1099511628211);
    return h;
}
static void flip_readback(Image image) {
    /* ImageFlipVertical may free/replace Image.data. This image borrows arena
       storage, so flip rows in place using bounded frame scratch instead. */
    HFArenaMark mark=hf_arena_mark(&memory.frame);
    size_t row=(size_t)image.width*4;
    unsigned char *temp=HF_PUSH(&memory.frame,unsigned char,row);
    if(!temp)fail("capture row scratch exhausted");
    unsigned char *pixels=image.data;
    for(int y=0;y<image.height/2;y++) {
        unsigned char *a=pixels+y*row,*b=pixels+(image.height-1-y)*row;
        memcpy(temp,a,row);memcpy(a,b,row);memcpy(b,temp,row);
    }
    hf_arena_rewind(mark);
}
static unsigned char *read_file(const char *path,size_t *size) {
    FILE *f=fopen(path,"rb");if(!f)fail("cannot open scene file");
    fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<24)fail("invalid scene file");
    unsigned char *p=HF_PUSH(&memory.assets,unsigned char,(size_t)n);if(!p || fread(p,1,n,f)!=(size_t)n)fail("cannot read scene file into asset arena");
    fclose(f);*size=n;return p;
}
static void present(Texture2D texture,int width,int height,bool overlay,unsigned frame,unsigned count) {
    BeginDrawing();ClearBackground(BLACK);
    float scale=fminf((float)GetScreenWidth()/width,(float)GetScreenHeight()/height);
    scale=fmaxf(1,floorf(scale));
    DrawTexturePro(texture,(Rectangle){0,0,(float)width,(float)-height},
                   (Rectangle){(GetScreenWidth()-width*scale)*.5f,(GetScreenHeight()-height*scale)*.5f,width*scale,height*scale},(Vector2){0,0},0,WHITE);
    if(overlay)DrawText(TextFormat("C renderer comparison | frame %u/%u | SPACE pause | RIGHT step | F1 text",frame+1,count),8,8,16,WHITE);
    EndDrawing();
}
static uint64_t audit_present(Texture2D texture,int width,int height,bool overlay,unsigned frame,unsigned count) {
    hf_allocation_begin();
    present(texture,width,height,overlay,frame,count);
    HFAllocationCounts allocations=hf_allocation_end();
    return allocations.mallocs+allocations.callocs+allocations.reallocs;
}
int main(int argc,char **argv) {
    const char *path="c_port/data/water/scene.hfc",*output="c_port/output/native.csv";
    bool benchmark=false,hidden=false,overlay=true;const char *capture_dir=NULL;
    unsigned loops=1,iteration=0;
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--scene") && i+1<argc)path=argv[++i];
        else if(!strcmp(argv[i],"--output") && i+1<argc)output=argv[++i];
        else if(!strcmp(argv[i],"--captures") && i+1<argc)capture_dir=argv[++i];
        else if(!strcmp(argv[i],"--benchmark"))benchmark=true;
        else if(!strcmp(argv[i],"--hidden"))hidden=true;
        else if(!strcmp(argv[i],"--loops") && i+1<argc) {
            char *end;long value=strtol(argv[++i],&end,10);
            if(*end || value<1 || value>10000)fail("loops must be between 1 and 10000");
            loops=(unsigned)value;
        }
        else { fprintf(stderr,"Usage: haunted_native [--scene file.hfc] [--benchmark] [--hidden] [--output csv] [--captures directory] [--loops n]\n");return 2; }
    }
    if(!hf_memory_init(&memory,HF_MIB(128),HF_MIB(384),HF_MIB(16)))fail("cannot reserve native memory arenas");
    native_scene=HF_PUSH_ZERO(&memory.persistent,NativeSceneState,1);if(!native_scene)fail("scene state allocation failed");
    size_t length;unsigned char *data=read_file(path,&length);Reader file={data,data+length};
    if(memcmp(rd_bytes(&file,8),"HFCP0001",8))fail("unsupported scene version");
    uint32_t count=rd_u32(&file),width=rd_u32(&file),height=rd_u32(&file),render=rd_id(&file),size;
    const unsigned char *init=rd_blob(&file,&size);Reader initial={init,init+size};
    if(!count || count>100000 || !width || !height || width>8192 || height>8192)fail("invalid scene header");
    Frame *frames=HF_PUSH_ZERO(&memory.persistent,Frame,count);if(!frames)fail("frame table capacity exceeded");
    for(uint32_t i=0;i<count;i++) {
        Frame *f=&frames[i];f->scene=rd_u32(&file);f->index=rd_u32(&file);f->measured=rd_u32(&file);f->expected=rd_u64(&file);
        const unsigned char *p=rd_blob(&file,&size);f->commands=(Reader){p,p+size};
    }
    if(file.p!=file.end)fail("trailing scene data");
    preload_native(initial);
    for(uint32_t i=0;i<count;i++)preload_native(frames[i].commands);
    allocate_native_results();
    SetTraceLogLevel(LOG_WARNING);SetConfigFlags((hidden?FLAG_WINDOW_HIDDEN:0)|FLAG_WINDOW_RESIZABLE);
    InitWindow(width*2,height*2,"Haunted Flight - native C renderer comparison");SetTargetFPS(benchmark?0:60);
    Material material=LoadMaterialDefault();shaders[1]=material.shader;MemFree(material.maps);
    textures[1]=(Texture2D){rlGetTextureIdDefault(),1,1,1,PIXELFORMAT_UNCOMPRESSED_R8G8B8A8};
    preload_gpu(initial);
    for(uint32_t i=0;i<count;i++)preload_gpu(frames[i].commands);
    resources_ready=true;
    unsigned char *pixels=HF_PUSH(&memory.persistent,unsigned char,(size_t)width*height*4);
    if(!pixels)fail("readback arena exhausted");
    size_t persistent_used=memory.persistent.used,assets_used=memory.assets.used;
    execute(initial);rlDrawRenderBatchActive();
    FILE *csv=benchmark?fopen(output,"wb"):NULL;if(benchmark && !csv)fail("cannot create timing output (create its directory first)");
    GPUTimer timer=gpu_timer();
    GPUReadback readback=gpu_readback();
    if(benchmark && (!readback.bind || !readback.pack || !readback.read))fail("OpenGL texture readback unavailable");
    if(csv)fprintf(csv,"case,index,measured,submit_ms,complete_readback_ms,gpu_elapsed_ms,pixel_match,expected,actual,rays,ray_errors,heap_allocations,heap_bytes\n");
    uint64_t mismatches=0,heap_allocations=0,heap_bytes=0,presentation_allocations=0,processed=0;
    bool paused=false,has_frame=false;unsigned frame=0;
    while(!WindowShouldClose()) {
        if(IsKeyPressed(KEY_F1))overlay=!overlay;
        if(IsKeyPressed(KEY_SPACE))paused=!paused;
        bool step=IsKeyPressed(KEY_RIGHT);
        if(!benchmark && paused && has_frame && !step) {
            presentation_allocations+=audit_present(textures[render],width,height,overlay,frame,count);
            continue;
        }
        if(has_frame)frame=(frame+1)%count;
        hf_arena_reset(&memory.frame);
        Frame *f=&frames[frame];source_frame=(int)frame;
        uint64_t rays_before=ray_count,errors_before=ray_errors;
        if(benchmark && timer.enabled)timer.begin(0x88BF,timer.id); /* GL_TIME_ELAPSED */
        hf_allocation_begin();
        double start=GetTime();
        /* Restore initialization uniforms/state when rewinding the fixture.
         * Resource creation is still skipped: all storage remains resident. */
        if(frame==0 && has_frame) {
            for(unsigned i=2;i<RESOURCES;i++)if(texture_dirty[i] && texture_initial_pixels[i]) {
                UpdateTexture(textures[i],texture_initial_pixels[i]);texture_dirty[i]=false;
            }
            execute(initial);
        }
        execute(f->commands);rlDrawRenderBatchActive();double submitted=GetTime();
        if(memory.persistent.used!=persistent_used || memory.assets.used!=assets_used)fail("persistent arena grew during a frame");
        if(benchmark && timer.enabled)timer.end(0x88BF);
        if(benchmark) {
            /* Same GL readback as raylib, into one persistent buffer. */
            readback.bind(0x0DE1,textures[render].id);readback.pack(0x0D05,1);
            readback.read(0x0DE1,0,0x1908,0x1401,pixels);readback.bind(0x0DE1,0);
            Image image={pixels,(int)width,(int)height,1,PIXELFORMAT_UNCOMPRESSED_R8G8B8A8};double complete=GetTime();
            HFAllocationCounts allocations=hf_allocation_end();
            uint64_t allocs=allocations.mallocs+allocations.callocs+allocations.reallocs;
            heap_allocations+=allocs;heap_bytes+=allocations.requested_bytes;
            uint64_t gpu_ns=0;if(timer.enabled)timer.result(timer.id,0x8866,&gpu_ns); /* GL_QUERY_RESULT */
            uint64_t actual=hash_rgb(image);bool match=actual==f->expected;if(!match)mismatches++;
            fprintf(csv,"%u,%u,%u,%.6f,%.6f,%.6f,%d,%016" PRIx64 ",%016" PRIx64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%zu\n",
                f->scene,f->index,f->measured,(submitted-start)*1000,(complete-start)*1000,gpu_ns/1e6,match,f->expected,actual,ray_count-rays_before,ray_errors-errors_before,allocs,allocations.requested_bytes);
            if(capture_dir && (!match || f->index==0 || f->index==8 || frame==count-1 || frames[(frame+1)%count].scene!=f->scene)) {
                flip_readback(image);ExportImage(image,TextFormat("%s/native-%u-%u.png",capture_dir,f->scene,f->index));
            }
        } else {
            HFAllocationCounts allocations=hf_allocation_end();
            heap_allocations+=allocations.mallocs+allocations.callocs+allocations.reallocs;
            heap_bytes+=allocations.requested_bytes;
        }
        presentation_allocations+=audit_present(textures[render],width,height,!benchmark&&overlay,frame,count);
        processed++;
        if(benchmark && frame+1==count && ++iteration>=loops)break;
        has_frame=true;
    }
    if(csv)fclose(csv);
    printf("Native: %" PRIu64 " recorded frames; pixel mismatches=%" PRIu64 "; C visibility rays=%" PRIu64 ", errors=%" PRIu64 "\n",processed,mismatches,ray_count,ray_errors);
    printf("Native preparation: polygons=%" PRIu64 ", fans=%" PRIu64 ", tree poses=%" PRIu64 ", errors=%" PRIu64 "\n",
           native_scene->visibility_builds,native_scene->fans,native_scene->tree_poses,native_scene->errors);
    printf("Arenas: persistent=%zu, assets=%zu, frame peak=%zu bytes; failures=%" PRIu64 "; no persistent growth during frames\n",
           memory.persistent.used,memory.assets.used,memory.frame.peak,memory.frame.failures);
    printf("Frame heap audit (executable + raylib, excludes OS/GPU DLLs): allocations=%" PRIu64 ", requested bytes=%" PRIu64 "\n",heap_allocations,heap_bytes);
    printf("Presentation heap audit: allocations=%" PRIu64 "\n",presentation_allocations);
    /* Context destruction releases GPU resources, including temporary targets
       whose texture aliases are intentionally shared in the trace. */
    if(timer.enabled)timer.destroy(1,&timer.id);
    int result=mismatches || ray_errors || native_scene->errors || heap_allocations || presentation_allocations?1:0;
    unload_gpu();CloseWindow();hf_memory_destroy(&memory);return result;
}
