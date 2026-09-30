#ifndef HF_NATIVE_SCENE_H
#define HF_NATIVE_SCENE_H
#include "arena.h"
#include "visibility.h"
#include "geometry.h"
#include <stdint.h>

enum { HF_MAX_RAYS=4096, HF_MAX_CORNERS=512 };
typedef struct { uint32_t first, count; } HFRange;
/* Cold authored data and hot runtime arrays are separate. Integer indices,
 * never strings/dictionaries, connect objects to their resources. */
typedef struct {
    HFGrid grid;
    HFPoint *vertices;
    uint32_t vertex_count;
    HFRange *buckets;
    uint32_t *bucket_vertices;
    uint32_t buckets_x,buckets_y;
    double bucket_width,bucket_height;
} HFSceneGeometry;
typedef struct {
    HFPoint position,direction;
    double radius,outer_angle,shadow_bias,corner_epsilon;
    uint32_t spot,ray_count,max_rays,corner_rays,corner_limit;
} HFVisibilityLight;
typedef struct {
    double *angles;
    HFPoint *polygon,*unbiased;
    int32_t *hit_tiles;
    uint32_t count,hit_count,baseline_count,corner_count,adaptive_count;
    uint32_t tile_steps,max_tile_steps;
} HFVisibilityResult;
typedef struct {
    HFPoint direction;
    double strength,gust_strength,gust_speed,spatial_scale,vertical_flutter;
    int32_t seed;
    uint32_t irregular;
} HFWind;
typedef struct {
    HFPoint pivot;
    double bottom,stiffness,phase,exposure,lag,response,flutter,bend_gain;
} HFTreePart;
typedef struct { double angle,bend; float deformation[16]; } HFTreePose;

HF_EXPORT int hf_build_visibility(const HFSceneGeometry *scene,const HFVisibilityLight *light,
                        HFArena *frame,HFVisibilityResult *result);
HF_EXPORT HFPoint hf_sample_wind(const HFWind *wind,HFPoint world,double time);
HF_EXPORT void hf_tree_pose(const HFTreePart *part,const HFWind *wind,HFPoint world,
                  double time,int strips,HFTreePose *result);
/* Exact Python-style rounding used at the CPU -> pixel boundary. */
HF_EXPORT double hf_round_even(double value);
#endif
