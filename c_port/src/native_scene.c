#include "native_scene.h"
#include <math.h>
#include <string.h>
#define HF_PI 3.14159265358979323846
#define HF_TAU (2.0*HF_PI)
#define HF_EPS .000001
static double clamp(double v,double lo,double hi) { return v<lo?lo:v>hi?hi:v; }
static double modulo(double a,double b) { double r=fmod(a,b);return r<0?r+b:r; }
static double angle_signed(double a) { return modulo(a+HF_PI,HF_TAU)-HF_PI; }
double hf_round_even(double v) {
    double lo=floor(v),f=v-lo;
    if (f>.5 || (f==.5 && fmod(lo,2.)!=0.)) return lo+1.;
    return lo;
}
static double hash_noise(int64_t x,int64_t y,int64_t seed) {
    uint32_t v=(uint32_t)x*374761393u+(uint32_t)y*668265263u+(uint32_t)seed*69069u;
    v=(v^(v>>13))*1274126177u;v^=v>>16;
    return v/4294967295.;
}
static double noise(double value,int64_t seed) {
    double cell=floor(value),f=value-cell;
    double blend=pow(f,3.)*(f*(f*6.-15.)+10.);
    double a=hash_noise((int64_t)cell,seed,7919)*2.-1.;
    double b=hash_noise((int64_t)cell+1,seed,7919)*2.-1.;
    return a+(b-a)*blend;
}
HFPoint hf_sample_wind(const HFWind *w,HFPoint p,double t) {
    double dx=w->direction.x,dy=w->direction.y,length=hypot(dx,dy);
    if (length<=HF_EPS) { dx=1.;dy=0.;length=1.; }
    dx/=length;dy/=length;
    double phase=(p.x*.73+p.y*1.19)*w->spatial_scale;
    double gust=sin(t*w->gust_speed*HF_TAU+phase);
    double cross=sin(t*.41+phase*1.7)*w->vertical_flutter;
    double magnitude=w->strength+gust*w->gust_strength;
    return (HFPoint){dx*magnitude-dy*cross,dy*magnitude+dx*cross};
}
static HFPoint irregular_wind(const HFWind *w,HFPoint p,double elapsed) {
    double phase=(p.x*.73+p.y*1.19)*w->spatial_scale;
    double t=elapsed*fmax(0.,w->gust_speed)+phase;
    double gust=.75*noise(t,w->seed)+.25*noise(t*2.7,(int64_t)w->seed+1);
    double lull=.75+.25*noise(t*.27,(int64_t)w->seed+2);
    HFWind local=*w;local.strength=(w->strength+w->gust_strength*gust)*lull;local.gust_strength=0.;
    return hf_sample_wind(&local,p,elapsed);
}
void hf_tree_pose(const HFTreePart *p,const HFWind *w,HFPoint world,double elapsed,
                  int strips,HFTreePose *out) {
    double angle,bend,t=elapsed-p->lag;
    if (w->irregular) {
        double wx=0.,wy=0.;
        for (int i=0;i<3;i++) {
            HFPoint s=irregular_wind(w,world,t-p->response*(i*.5));
            wx+=s.x;wy+=s.y;
        }
        wx/=3.;wy/=3.;
        double force=(wx+.2*wy)/13.*p->exposure;
        double strength=fmin(2.,hypot(wx,wy)/13.)*p->exposure;
        int64_t seed=(int64_t)w->seed+(int64_t)(p->phase*100);
        double spatial=world.x*.019+world.y*.013;
        double sway=noise(t*.4+spatial,seed),flutter=noise(t*p->flutter+spatial,seed+1);
        angle=-p->stiffness*(2.6*force+.6*strength*sway);
        bend=p->bend_gain*(1.6*force+.85*strength*flutter);
    } else {
        HFPoint current=hf_sample_wind(w,world,elapsed),delayed=hf_sample_wind(w,world,elapsed-.18*p->phase);
        double force=(.8*current.x+.2*delayed.x+.2*current.y)/13.;
        double strength=fmin(2.,hypot(current.x,current.y)/13.);
        double phase=p->phase+world.x*.019+world.y*.013;
        angle=-p->stiffness*(2.6*force+.45*strength*sin(elapsed*1.7+phase));
        bend=p->stiffness*(1.5*force+strength*(.7*sin(elapsed*2.3+phase)+.25*sin(elapsed*4.1+phase*1.6)));
    }
    out->angle=clamp(angle,-7.,7.)*(HF_PI/180.);out->bend=clamp(bend,-5.,5.);
    HFPoint wind=w->irregular?irregular_wind(w,world,elapsed):hf_sample_wind(w,world,elapsed);
    double strength=fmin(1.5,hypot(wind.x,wind.y)/8.)*p->exposure;
    double phase=p->phase+world.x*.019+world.y*.013+w->seed*.37;
    double values[16]={cos(out->angle),sin(out->angle),out->bend,strength,
        p->pivot.x,p->pivot.y,fmax(1.,p->bottom-p->pivot.y),p->bend_gain,
        modulo(t*1.35+phase,HF_TAU),modulo(t*2.05+phase*.3,HF_TAU),
        modulo(t*1.6+phase+.8,HF_TAU),modulo(phase,HF_TAU),!strips,0,0,0};
    for (int i=0;i<16;i++) out->deformation[i]=(float)values[i];
}

typedef struct { double distance,angle;uint32_t index; } Candidate;
/* Stable, allocation-free merge sort. No libc qsort scratch allocation and no
 * pointer chasing: all candidate fields are contiguous. */
static void sort_candidates(Candidate *a,Candidate *temp,uint32_t count) {
    for (uint32_t width=1;width<count;width*=2) {
        for (uint32_t first=0;first<count;first+=width*2) {
            uint32_t middle=first+width<count?first+width:count;
            uint32_t end=first+width*2<count?first+width*2:count;
            uint32_t left=first,right=middle;
            for (uint32_t out=first;out<end;out++) {
                int use_left=right==end || (left<middle &&
                    (a[left].distance<a[right].distance ||
                     (a[left].distance==a[right].distance && a[left].index<a[right].index)));
                temp[out]=a[use_left?left++:right++];
            }
        }
        memcpy(a,temp,count*sizeof(*a));
    }
}
static int add_angle(double value,double *angles,int64_t *keys,uint32_t *count,uint32_t capacity) {
    value=modulo(value,HF_TAU);
    int64_t key=(int64_t)hf_round_even(value*1.e8);
    for (uint32_t i=0;i<*count;i++) if (keys[i]==key) return 0;
    if (*count>=capacity) return 0;
    keys[*count]=key;angles[(*count)++]=value;return 1;
}
int hf_build_visibility(const HFSceneGeometry *s,const HFVisibilityLight *l,
                        HFArena *frame,HFVisibilityResult *out) {
    *out=(HFVisibilityResult){0};
    uint32_t maximum=l->max_rays,limit=l->corner_limit;
    if (!maximum || maximum>HF_MAX_RAYS || limit>HF_MAX_CORNERS) return 0;
    HFArenaMark start=hf_arena_mark(frame);
    out->angles=HF_PUSH(frame,double,maximum);
    out->polygon=HF_PUSH(frame,HFPoint,maximum);
    out->unbiased=HF_PUSH(frame,HFPoint,maximum);
    out->hit_tiles=HF_PUSH(frame,int32_t,maximum);
    if (!out->angles || !out->polygon || !out->unbiased || !out->hit_tiles) goto exhausted;
    HFArenaMark scratch=hf_arena_mark(frame);
    int64_t *keys=HF_PUSH(frame,int64_t,maximum);
    /* Query packed spatial buckets first. A small lamp must not scan or reserve
     * scratch for every wall corner in a large level. Each vertex belongs to
     * exactly one bucket; candidate sorting restores authored-ID tie order. */
    int min_x=0,min_y=0,max_x=-1,max_y=-1;
    uint32_t candidate_capacity=0;
    if (l->corner_rays && limit && s->buckets_x && s->buckets_y) {
        min_x=(int)clamp(floor((l->position.x-l->radius)/s->bucket_width),0,s->buckets_x);
        min_y=(int)clamp(floor((l->position.y-l->radius)/s->bucket_height),0,s->buckets_y);
        max_x=(int)clamp(floor((l->position.x+l->radius)/s->bucket_width),-1,s->buckets_x-1);
        max_y=(int)clamp(floor((l->position.y+l->radius)/s->bucket_height),-1,s->buckets_y-1);
        for (int y=min_y;y<=max_y;y++) for (int x=min_x;x<=max_x;x++)
            candidate_capacity+=s->buckets[y*s->buckets_x+x].count;
    }
    Candidate *candidates=HF_PUSH(frame,Candidate,candidate_capacity);
    Candidate *sort_temp=HF_PUSH(frame,Candidate,candidate_capacity);
    double *accepted=HF_PUSH(frame,double,limit);
    if (!keys || !candidates || !sort_temp || !accepted) goto exhausted;
    double length=hypot(l->direction.x,l->direction.y);
    double center=l->spot && length>HF_EPS?atan2(l->direction.y/length,l->direction.x/length):0.;
    double outer=l->spot?l->outer_angle*(HF_PI/180.):HF_PI;
    uint32_t baseline=l->ray_count<maximum?l->ray_count:maximum;
    for (uint32_t i=0;i<baseline;i++) {
        double angle=l->spot?(baseline==1?center:center-outer+(double)i/(baseline-1)*outer*2.):
                                      (double)i/baseline*HF_PI*2.;
        add_angle(angle,out->angles,keys,&out->count,maximum);
    }
    out->baseline_count=out->count;
    uint32_t candidate_count=0;
    if (l->corner_rays && limit && out->count<maximum) {
        for (int y=min_y;y<=max_y;y++) for (int x=min_x;x<=max_x;x++) {
            HFRange bucket=s->buckets[y*s->buckets_x+x];
            for (uint32_t j=0;j<bucket.count;j++) {
                uint32_t i=s->bucket_vertices[bucket.first+j];
                HFPoint p=s->vertices[i];double dx=p.x-l->position.x,dy=p.y-l->position.y;
                double distance=hypot(dx,dy);
                if (distance<=l->radius+HF_EPS)
                    candidates[candidate_count++]=(Candidate){distance,atan2(dy,dx),i};
            }
        }
    }
    sort_candidates(candidates,sort_temp,candidate_count);
    double separation=(outer*2./fmax(1.,limit))*.35;
    for (uint32_t i=0;i<candidate_count && out->corner_count<limit;i++) {
        double angle=candidates[i].angle;
        if (l->spot && fabs(angle_signed(angle-center))>outer+HF_EPS) continue;
        int duplicate=0;
        double key=hf_round_even(modulo(angle,HF_TAU)*1.e6);
        for (uint32_t j=0;j<out->corner_count;j++) {
            if (key==hf_round_even(modulo(accepted[j],HF_TAU)*1.e6) ||
                fabs(angle_signed(angle-accepted[j]))<separation) { duplicate=1;break; }
        }
        if (!duplicate) accepted[out->corner_count++]=angle;
    }
    for (uint32_t i=0;i<out->corner_count && out->count<maximum;i++) {
        for (int side=-1;side<=1 && out->count<maximum;side++) {
            double angle=accepted[i]+l->corner_epsilon*side;
            if (!l->spot || fabs(angle_signed(angle-center))<=outer+HF_EPS)
                add_angle(angle,out->angles,keys,&out->count,maximum);
        }
    }
    /* Small bounded ray arrays: stable insertion sort avoids allocator/library
     * state. Baseline rays are already sorted except a single angle wrap. */
    for (uint32_t i=1;i<out->count;i++) {
        double angle=out->angles[i],key=l->spot?angle_signed(angle-center):angle;
        uint32_t j=i;
        while (j && (l->spot?angle_signed(out->angles[j-1]-center):out->angles[j-1])>key) {
            out->angles[j]=out->angles[j-1];j--;
        }
        out->angles[j]=angle;
    }
    out->adaptive_count=out->count-out->baseline_count;
    for (uint32_t i=0;i<out->count;i++) {
        double dx=cos(out->angles[i]),dy=sin(out->angles[i]);
        HFHit hit=hf_light_ray(&s->grid,l->position.x,l->position.y,dx,dy,l->radius);
        out->tile_steps+=(uint32_t)hit.steps;
        if ((uint32_t)hit.steps>out->max_tile_steps) out->max_tile_steps=(uint32_t)hit.steps;
        double distance=hit.hit?hit.distance:l->radius;
        double biased=hit.hit?fmax(0.,distance-l->shadow_bias):distance;
        out->polygon[i]=(HFPoint){l->position.x+dx*biased,l->position.y+dy*biased};
        out->unbiased[i]=(HFPoint){l->position.x+dx*distance,l->position.y+dy*distance};
        if (hit.hit) {
            uint32_t j=0;for (;j<out->hit_count;j++) if (out->hit_tiles[j]==hit.tile_index) break;
            if (j==out->hit_count) out->hit_tiles[out->hit_count++]=hit.tile_index;
        }
    }
    hf_arena_rewind(scratch);
    return 1;
exhausted:
    hf_arena_rewind(start);*out=(HFVisibilityResult){0};return 0;
}
