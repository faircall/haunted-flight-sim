/* Double-precision port of g_light_visibility.dda_first_light_hit_values.
 * Keep edge conventions, epsilon and corner-seam sealing identical to Python.
 * No allocation, interpreter, graphics dependency or global mutable state. */
#include "visibility.h"
#include <math.h>
#include <string.h>
#define EPS 0.000001
static double max2(double a,double b) { return a>b?a:b; }
static double min2(double a,double b) { return a<b?a:b; }
static int planes(int shape,double w,double h,double p[4][3]) {
    const double all[5][4][3]={
        {{1,0,0},{0,1,0},{-1,0,w},{0,-1,h}},
        {{1,0,0},{0,1,0},{-1/w,-1/h,1}},
        {{-1,0,w},{0,1,0},{1/w,-1/h,0}},
        {{-1,0,w},{0,-1,h},{1/w,1/h,-1}},
        {{1,0,0},{0,-1,h},{-1/w,1/h,0}}
    };
    if(shape<0 || shape>4) return 0;
    memcpy(p,all[shape],sizeof(all[shape]));
    return shape==0?4:3;
}
static int corner(const HFGrid *g,int x,int y,double wx,double wy) {
    if(x<0 || y<0 || x>=g->width || y>=g->height) return 0;
    int s=g->shapes[y*g->width+x];
    if(s==255) return 0;
    if(s==0) return 1;
    double p[4][3];int n=planes(s,g->tile_width,g->tile_height,p);
    wx-=x*g->tile_width;wy-=y*g->tile_height;
    for(int i=0;i<n;i++) if(p[i][0]*wx+p[i][1]*wy+p[i][2]<-EPS) return 0;
    return n>0;
}
static int shape_hit(const HFGrid *g,int x,int y,int s,double ox,double oy,
                     double dx,double dy,double enter,double leave,HFHit *out) {
    double p[4][3],lo=-INFINITY,hi=INFINITY,nx=-dx,ny=-dy;
    int n=planes(s,g->tile_width,g->tile_height,p),edge=-1;
    ox-=x*g->tile_width;oy-=y*g->tile_height;
    for(int i=0;i<n;i++) {
        double offset=p[i][0]*ox+p[i][1]*oy+p[i][2];
        double rate=p[i][0]*dx+p[i][1]*dy;
        if(fabs(rate)<=EPS) { if(offset<-EPS) return 0;continue; }
        double t=-offset/rate;
        if(rate>0 && t>lo) {
            lo=t;edge=i;double length=hypot(p[i][0],p[i][1]);
            nx=-p[i][0]/length;ny=-p[i][1]/length;
        } else if(rate<0 && t<hi) hi=t;
        if(hi<lo-EPS) return 0;
    }
    double start=max2(max2(enter,lo),0),end=min2(leave,hi);
    if(end-start<=EPS) return 0;
    if(lo<enter-EPS || edge<0) { edge=-1;nx=-dx;ny=-dy; }
    out->distance=max2(0,start);out->edge=edge;out->normal_x=nx;out->normal_y=ny;
    return 1;
}
HFHit hf_light_ray(const HFGrid *g,double ox,double oy,double dx,double dy,double distance) {
    HFHit r={0};
    double start=0,end=distance,w=g->tile_width,h=g->tile_height;
    if(g->width<=0 || g->height<=0 || w<=0 || h<=0 || !g->shapes) return r;
    double origins[2]={ox,oy},dirs[2]={dx,dy},sizes[2]={g->width*w,g->height*h};
    for(int i=0;i<2;i++) {
        if(fabs(dirs[i])<=EPS) { if(origins[i]<0 || origins[i]>sizes[i]) return r;continue; }
        double a=-origins[i]/dirs[i],b=(sizes[i]-origins[i])/dirs[i];
        start=max2(start,min2(a,b));end=min2(end,max2(a,b));
        if(end<start) return r;
    }
    if(end<0 || start>distance) return r;
    start=max2(0,start);end=min2(distance,end);
    double sample=min2(end,start+EPS);
    int x=(int)floor((ox+dx*sample)/w),y=(int)floor((oy+dy*sample)/h);
    x=x<0?0:x>=g->width?g->width-1:x;y=y<0?0:y>=g->height?g->height-1:y;
    int sx=dx>EPS?1:dx<-EPS?-1:0,sy=dy>EPS?1:dy<-EPS?-1:0;
    double delta_x=sx?w/fabs(dx):INFINITY,delta_y=sy?h/fabs(dy):INFINITY;
    double mx=sx?((x+(sx>0))*w-ox)/dx:INFINITY;
    double my=sy?((y+(sy>0))*h-oy)/dy:INFINITY;
    double t=start;
    while(x>=0 && y>=0 && x<g->width && y<g->height && t<=end+EPS) {
        r.steps++;
        double leave=min2(min2(mx,my),end);
        int index=y*g->width+x,s=g->shapes[index],hit=0;
        if(s!=255) {
            if(s==0 && leave-t>EPS) {
                double hx=ox+dx*t-x*w,hy=oy+dy*t-y*h;
                r.edge=-1;r.normal_x=-dx;r.normal_y=-dy;r.distance=max2(0,t);
                if(t>EPS) {
                    if(fabs(hx)<=EPS*4) { r.edge=3;r.normal_x=-1;r.normal_y=0; }
                    else if(fabs(hx-w)<=EPS*4) { r.edge=1;r.normal_x=1;r.normal_y=0; }
                    else if(fabs(hy)<=EPS*4) { r.edge=0;r.normal_x=0;r.normal_y=-1; }
                    else if(fabs(hy-h)<=EPS*4) { r.edge=2;r.normal_x=0;r.normal_y=1; }
                }
                hit=1;
            } else hit=shape_hit(g,x,y,s,ox,oy,dx,dy,t,leave,&r);
            if(hit && r.distance<=end+EPS) {
                r.hit=1;r.tile_x=x;r.tile_y=y;r.tile_index=index;r.shape=s;return r;
            }
        }
        if(leave>=end-EPS) break;
        if(mx<my-EPS) { t=mx;mx+=delta_x;x+=sx; }
        else if(my<mx-EPS) { t=my;my+=delta_y;y+=sy; }
        else {
            t=min2(mx,my);double cx=ox+dx*t,cy=oy+dy*t;
            if(corner(g,x+sx,y,cx,cy) && corner(g,x,y+sy,cx,cy)) {
                r.hit=1;r.distance=t;r.tile_x=x+sx;r.tile_y=y;r.tile_index=y*g->width+x+sx;
                r.shape=g->shapes[r.tile_index];r.edge=-1;r.normal_x=-dx;r.normal_y=-dy;return r;
            }
            mx+=delta_x;my+=delta_y;x+=sx;y+=sy;
        }
    }
    return r;
}
