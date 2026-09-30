/* Native scene stages wired into the parity renderer. Included after Reader
 * and dispatch declarations; the reusable CPU kernels live in native_scene.c. */
typedef struct { HFVisibilityResult result;uint32_t capacity; } VisibilitySlot;
typedef struct { HFTreePart part;HFWind wind;HFPoint world;uint32_t strips,loaded;HFTreePose pose; } TreeSlot;
typedef struct {
    HFSceneGeometry geometry[128];
    VisibilitySlot lights[RESOURCES];
    TreeSlot trees[RESOURCES];
    uint64_t visibility_builds,tree_poses,fans,errors;
} NativeSceneState;
static NativeSceneState *native_scene;

static void read_struct(Reader *r,void *out,size_t size) {
    uint32_t length;const void *p=rd_blob(r,&length);
    if(length!=size)fail("native struct ABI mismatch; re-export with this build");
    memcpy(out,p,size);
}
static void *read_array(Reader *r,size_t count,size_t element,size_t alignment) {
    uint32_t size;const void *p=rd_blob(r,&size);
    if(count>SIZE_MAX/element || count*element!=size)fail("native array length mismatch");
    void *result=hf_arena_push(&memory.assets,count,element,alignment,0);
    if(!result)fail("asset arena capacity exceeded");
    memcpy(result,p,size);return result;
}
static void preload_native(Reader commands) {
    while(commands.p<commands.end) {
        uint32_t op=rd_u32(&commands),size=rd_u32(&commands);
        const unsigned char *bytes=rd_bytes(&commands,size);Reader value={bytes,bytes+size},*r=&value;
        if(op==OP_HFGrid) {
            uint32_t id=rd_u32(r);if(id>=128)fail("too many collision grids");
            int w=rd_i32(r),h=rd_i32(r);double tw=rd_double(r),th=rd_double(r);
            uint32_t n;const uint8_t *p=rd_blob(r,&n);
            if(w<=0 || h<=0 || (size_t)w*(size_t)h!=n || tw<=0 || th<=0)fail("invalid collision grid");
            grids[id]=(HFGrid){w,h,tw,th,p};
        } else if(op==OP_HFSceneGeometry) {
            uint32_t id=rd_u32(r);if(id>=128)fail("invalid native grid id");
            HFSceneGeometry *g=&native_scene->geometry[id];g->grid=grids[id];
            g->vertex_count=rd_u32(r);uint32_t buckets=rd_u32(r),indices=rd_u32(r);
            g->buckets_x=rd_u32(r);g->buckets_y=rd_u32(r);
            g->bucket_width=rd_double(r);g->bucket_height=rd_double(r);
            if(g->vertex_count>1000000 || !g->grid.shapes || (uint64_t)g->buckets_x*g->buckets_y!=buckets ||
               !g->buckets_x || !g->buckets_y || !isfinite(g->bucket_width) || !isfinite(g->bucket_height) ||
               g->bucket_width<=0 || g->bucket_height<=0)
                fail("invalid native scene geometry");
            g->vertices=read_array(r,g->vertex_count,sizeof(HFPoint),_Alignof(HFPoint));
            g->buckets=read_array(r,buckets,sizeof(HFRange),_Alignof(HFRange));
            g->bucket_vertices=read_array(r,indices,sizeof(uint32_t),_Alignof(uint32_t));
            for(uint32_t i=0;i<buckets;i++)
                if(g->buckets[i].first>indices || g->buckets[i].count>indices-g->buckets[i].first)
                    fail("invalid bucket range");
            for(uint32_t i=0;i<indices;i++)if(g->bucket_vertices[i]>=g->vertex_count)fail("invalid boundary vertex id");
        } else if(op==OP_HFVisibility) {
            uint32_t id=rd_id(r);(void)rd_u32(r);HFVisibilityLight light;read_struct(r,&light,sizeof(light));
            if(!light.max_rays || light.max_rays>HF_MAX_RAYS)fail("native ray capacity invalid");
            if(native_scene->lights[id].capacity<light.max_rays)native_scene->lights[id].capacity=light.max_rays;
        } else if(op==OP_HFTreeDefinition) {
            uint32_t id=rd_id(r);TreeSlot *tree=&native_scene->trees[id];
            read_struct(r,&tree->part,sizeof(tree->part));read_struct(r,&tree->wind,sizeof(tree->wind));
            tree->world.x=rd_double(r);tree->world.y=rd_double(r);tree->strips=rd_u32(r);tree->loaded=1;
        }
    }
}
static void allocate_native_results(void) {
    for(unsigned i=0;i<RESOURCES;i++) {
        VisibilitySlot *slot=&native_scene->lights[i];if(!slot->capacity)continue;
        HFVisibilityResult *r=&slot->result;
        r->angles=HF_PUSH(&memory.persistent,double,slot->capacity);
        r->polygon=HF_PUSH(&memory.persistent,HFPoint,slot->capacity);
        r->unbiased=HF_PUSH(&memory.persistent,HFPoint,slot->capacity);
        r->hit_tiles=HF_PUSH(&memory.persistent,int32_t,slot->capacity);
        if(!r->angles || !r->polygon || !r->unbiased || !r->hit_tiles)fail("native result arena exhausted");
    }
}
static bool execute_native(uint32_t op,Reader *r) {
    switch(op) {
    case OP_HFSceneGeometry:case OP_HFTreeDefinition:r->p=r->end;return true;
    case OP_HFVisibility: {
        uint32_t id=rd_id(r),gid=rd_u32(r);if(gid>=128)fail("invalid native grid");
        HFVisibilityLight light;read_struct(r,&light,sizeof(light));
        VisibilitySlot *slot=&native_scene->lights[id];
        if(light.max_rays>slot->capacity)fail("visibility capacity was not preallocated");
        HFArenaMark scratch=hf_arena_mark(&memory.frame);HFVisibilityResult output;
        if(!hf_build_visibility(&native_scene->geometry[gid],&light,&memory.frame,&output))fail("frame arena exhausted by visibility");
        uint32_t expected[6];for(int i=0;i<6;i++)expected[i]=rd_u32(r);
        if(output.count!=expected[0] || output.baseline_count!=expected[1] || output.corner_count!=expected[2] ||
           output.adaptive_count!=expected[3] || output.tile_steps!=expected[4] || output.max_tile_steps!=expected[5]) {
            native_scene->errors++;
            if(native_scene->errors<8)fprintf(stderr,"Native visibility stats differ at frame %d, light %u\n",source_frame,id);
        }
        uint32_t bytes;const unsigned char *p=rd_blob(r,&bytes);
        if(bytes!=(size_t)expected[0]*sizeof(HFPoint))fail("invalid polygon reference");
        Reader points={p,p+bytes};
        for(uint32_t i=0;i<expected[0];i++) {
            double x=rd_double(&points),y=rd_double(&points);
            if(i>=output.count || fabs(x-output.polygon[i].x)>1.e-8 || fabs(y-output.polygon[i].y)>1.e-8)native_scene->errors++;
        }
        HFVisibilityResult saved=slot->result;
        memcpy(saved.angles,output.angles,output.count*sizeof(double));
        memcpy(saved.polygon,output.polygon,output.count*sizeof(HFPoint));
        memcpy(saved.unbiased,output.unbiased,output.count*sizeof(HFPoint));
        memcpy(saved.hit_tiles,output.hit_tiles,output.hit_count*sizeof(int32_t));
        slot->result=output;slot->result.angles=saved.angles;slot->result.polygon=saved.polygon;
        slot->result.unbiased=saved.unbiased;slot->result.hit_tiles=saved.hit_tiles;
        hf_arena_rewind(scratch);native_scene->visibility_builds++;
        ray_count+=output.count;return true;
    }
    case OP_HFVisibilityFan: {
        uint32_t id=rd_id(r),unbiased=rd_u32(r),closed=rd_u32(r);
        double cx=rd_double(r),cy=rd_double(r),ox=rd_double(r),oy=rd_double(r);Color color=rd_Color(r);
        HFVisibilityResult *v=&native_scene->lights[id].result;
        if(!v->count)fail("visibility fan used before native preparation");
        HFArenaMark mark=hf_arena_mark(&memory.frame);
        Vector2 *vertices=HF_PUSH(&memory.frame,Vector2,v->count+2);if(!vertices)fail("fan scratch exhausted");
        vertices[0]=(Vector2){(float)(ox-cx),(float)(oy-cy)};
        HFPoint *points=unbiased?v->unbiased:v->polygon;
        for(uint32_t i=0;i<v->count;i++)vertices[i+1]=(Vector2){(float)(points[v->count-1-i].x-cx),(float)(points[v->count-1-i].y-cy)};
        uint32_t count=v->count+1;
        if(closed && v->count>=3)vertices[count++]=vertices[1];
        DrawTriangleFan(vertices,(int)count,color);hf_arena_rewind(mark);native_scene->fans++;return true;
    }
    case OP_HFTreePose: {
        uint32_t id=rd_id(r);double time=rd_double(r),angle=rd_double(r);
        const void *expected=rd_bytes(r,64);TreeSlot *tree=&native_scene->trees[id];
        if(!tree->loaded)fail("native tree used before definition");
        hf_tree_pose(&tree->part,&tree->wind,tree->world,time,tree->strips,&tree->pose);
        if(fabs(angle-tree->pose.angle)>1.e-11 || memcmp(expected,tree->pose.deformation,64))native_scene->errors++;
        native_scene->tree_poses++;return true;
    }
    case OP_HFTreeUniform:case OP_HFTreeAngle: {
        uint32_t tree=rd_id(r),shader=rd_id(r);int loc=rd_i32(r);
        if(op==OP_HFTreeUniform)SetShaderValueV(shaders[shader],location(shader,loc),native_scene->trees[tree].pose.deformation,SHADER_UNIFORM_VEC4,4);
        else { float angle=(float)native_scene->trees[tree].pose.angle;SetShaderValue(shaders[shader],location(shader,loc),&angle,SHADER_UNIFORM_FLOAT); }
        return true;
    }
    default:return false;
    }
}
