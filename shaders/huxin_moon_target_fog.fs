#version 330
uniform sampler2D depthMap,noiseMap;
uniform vec2 resolution,lens,clip;
uniform vec3 eye,forward,right,up,fogColour,playerCenter,boundsLow,boundsHigh;
uniform float clock,reflectedView,build,depthHold;
uniform int regionCount;
uniform vec4 regionCenters[24],regionHalves[24],regionFlow[24],regionBanks[24];
out vec4 finalColor;

vec3 noise3(vec3 p){
    p=mod(p,32.);vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    vec2 xy=cell.xy+f.xy+1.5;float a=cell.z,b=mod(a+1.,32.);
    vec2 uv0=(vec2(mod(a,8.),floor(a/8.))*34.+xy)/vec2(272.,136.);
    vec2 uv1=(vec2(mod(b,8.),floor(b/8.))*34.+xy)/vec2(272.,136.);
    return mix(texture(noiseMap,uv0).rgb,texture(noiseMap,uv1).rgb,f.z);
}
float boxDistance(vec3 p,vec3 halfSize){
    vec3 d=abs(p)-halfSize;
    return length(max(d,vec3(0.)))+min(max(d.x,max(d.y,d.z)),0.);
}
float bankDistance(int index,vec3 p){
    float distance=boxDistance(p-regionCenters[index].xyz,regionHalves[index].xyz);
    float shape=regionBanks[index].w;
    if(shape>.5&&shape<1.5){
        // Cover the actual concave hip plus its small hexagonal crown. A
        // thirteen-metre-high rectangular box creates a floating fog wall.
        float t=clamp(max(abs(p.x)/8.25,abs(p.z)/7.6),0.,1.);
        float hip=8.65+2.*(1.-t)*(1.-t);
        float crown=13.4-.25*dot(p.xz,p.xz);
        distance=max(distance,p.y-max(hip,crown));
    }else if(shape>1.5){
        float t=clamp(max(abs(p.x-9.75)/3.7,abs(p.z)/4.25),0.,1.);
        distance=max(distance,p.y-(4.8+(1.-t)*(1.-t)));
    }
    return distance;
}
float quietSpace(vec3 p){
    // These are feathered clear spaces, not a curtain around the pavilion.
    // The central room below the new upper floor remains readable, while
    // clouds above it can conceal the changed ceiling and hanging lanterns.
    float low=1.-smoothstep(2.15,3.05,p.y);
    float refuge=1.-low*(1.-smoothstep(2.6,4.1,length(p.xz)));
    float actor=smoothstep(.72,1.55,length((p-playerCenter)/vec3(.75,1.25,.75)));
    return refuge*actor;
}
bool interval(vec3 origin,vec3 ray,out float nearT,out float farT){
    nearT=0.;farT=240.;
    for(int axis=0;axis<3;axis++){
        if(abs(ray[axis])<.000001){if(origin[axis]<boundsLow[axis]||origin[axis]>boundsHigh[axis])return false;}
        else{
            float a=(boundsLow[axis]-origin[axis])/ray[axis],b=(boundsHigh[axis]-origin[axis])/ray[axis];
            nearT=max(nearT,min(a,b));farT=min(farT,max(a,b));
        }
    }
    return farT>nearT;
}
float nearestRegion(vec3 p){
    float distance=240.;
    for(int i=0;i<24;i++){
        if(i>=regionCount)break;
        // Include zero-density regions: fading a target never moves samples.
        float pad=max(regionHalves[i].w*2.5,regionBanks[i].x*2.3+regionHalves[i].w);
        distance=min(distance,boxDistance(p-regionCenters[i].xyz,regionHalves[i].xyz)-pad);
    }
    return distance;
}
bool coveredHit(vec3 p){
    if(quietSpace(p)<.97)return false;
    // These six lower columns survive the change. A cloud behind a shared
    // post must never replace its depth and erase its readable silhouette.
    if(p.y>.18&&p.y<3.85){
        for(int column=0;column<6;column++){
            float angle=float(column)*1.04719755;
            if(length(p.xz-4.65*vec2(cos(angle),sin(angle)))<.28)return false;
        }
    }
    for(int i=0;i<24;i++){
        if(i>=regionCount)break;
        if(regionCenters[i].w<=.00001)continue;
        if(bankDistance(i,p)<regionHalves[i].w*1.75)return true;
    }
    return false;
}
vec4 densityAt(vec3 p){
    float sigma=0.,weight=0.;vec3 colour=vec3(0.);
    for(int i=0;i<24;i++){
        if(i>=regionCount)break;
        float extinction=regionCenters[i].w,edge=max(.08,regionHalves[i].w);
        if(extinction<=.00001)continue;
        float width=regionBanks[i].x;
        float guard=smoothstep(regionBanks[i].y,regionBanks[i].y+regionBanks[i].z,p.y);
        if(guard<.0001)continue;
        float raw=bankDistance(i,p);
        if(raw>max(edge*2.4,width*2.3+edge))continue;
        float size=max(.3,regionFlow[i].w);
        vec3 base=(p-regionFlow[i].xyz*clock)/size;
        vec3 tilted=vec3(.81*base.x+.58*base.z,-.21*base.x+.93*base.y+.30*base.z,
                         -.54*base.x-.37*base.y+.76*base.z);
        vec3 macro=noise3(tilted*.43+vec3(17,5,11));
        vec3 flow=tilted+(macro-.5)*2.3;
        vec3 broad=noise3(flow);
        vec3 detail=noise3(flow*2.07+vec3(13,7,21)+(broad-.5)*.7);
        vec3 warp=(broad-.5)*edge*1.1+(detail-.5)*edge*.35;
        float warped=bankDistance(i,p+warp);
        float core=1.-smoothstep(-edge*.55,edge*.45,warped);
        float inner=1.-smoothstep(-edge*.65,-edge*.12,raw);
        float pores=smoothstep(.20,.75,broad.r*.55+detail.g*.45);
        float body=core*mix(.25+.75*pores,1.,inner*build);
        float fringe=1.-smoothstep(edge*.15,edge*1.75,warped);
        if(width>0.){
            // A dense quiet interior does the concealment; broad wandering
            // lobes outside it break up the silhouette without another slab.
            float outside=bankDistance(i,p+warp+(macro-.5)*width*1.25);
            float outer=1.-smoothstep(-edge*.35,width,outside);
            float protectedCore=1.-smoothstep(-edge*.5,0.,raw);
            vec2 center=regionCenters[i].xz;
            float outward=length(center)<1.?1.:smoothstep(-.3,.9,dot(p.xz-center,normalize(center)));
            // Large outward clouds should not fill the original room until
            // its emergency refuge becomes a visible circular floor cutout.
            // Keep the room-facing edge as tight as the original local mask.
            body=mix(body,max(protectedCore*build,outer*(.18+.67*pores)),outward);
            fringe=mix(fringe,1.-smoothstep(width*.35,width*1.5,outside),outward);
        }
        float threads=exp(-((detail.g-.48)*(detail.g-.48)+(broad.b-.51)*(broad.b-.51))*74.);
        float local=extinction*(body+fringe*threads*.14)*guard;
        float shade=noise3(flow+vec3(-.55,.8,.35)).r;
        float light=clamp(.5+(broad.r-shade)*1.25+(detail.b-.5)*.17,0.,1.);
        light=mix(light,floor(light*6.+.5)/6.,.35);
        colour+=local*fogColour*(.94+.12*light);weight+=local;
        // Meeting banks should merge without creating a doubled opaque slab.
        sigma=max(sigma,local);
    }
    sigma*=quietSpace(p);
    return vec4(colour/max(.00001,weight),sigma);
}
void main(){
    vec2 uv=gl_FragCoord.xy/resolution,ndc=uv*2.-1.;
    vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float start,farBound;
    if(!interval(eye,ray,start,farBound)){finalColor=vec4(0.);return;}
    // A budget floor based solely on static volume bounds guarantees that
    // grazing rays reach the far side instead of ending at a sampling plane.
    float minimumStep=max(.18,(farBound-start)/144.);
    float raw=texture(depthMap,uv).r;
    float depth=2.*clip.x*clip.y/(clip.y+clip.x-(raw*2.-1.)*(clip.y-clip.x))/max(.001,dot(ray,forward));
    float preserve=depthHold>.00001&&coveredHit(eye+ray*depth)?clamp(depthHold,0.,1.):0.;
    float finish=preserve>0.?farBound:min(farBound,depth);
    // The reflected ray is already unfolded into the same canonical world.
    // Integrate only beyond the water; main sight covers camera-to-water fog.
    if(reflectedView>.5){
        if(abs(ray.y)<.000001){if(eye.y<0.)finish=start;}
        else if(ray.y>0.)start=max(start,-eye.y/ray.y);
        else finish=min(finish,-eye.y/ray.y);
    }
    if(finish<=start){finalColor=vec4(0.);return;}
    float transmission=1.,travel=start;vec3 scatter=vec3(0.);
    float jitter=fract(52.9829189*fract(dot(floor(gl_FragCoord.xy),vec2(.06711056,.00583715))));
    for(int i=0;i<160;i++){
        if(travel>=finish||transmission<.00025)break;
        float stepLength=clamp(nearestRegion(eye+ray*travel)*.65,minimumStep,1.25);
        float lo=travel,hi=min(finish,lo+stepLength);travel+=stepLength;
        float lengthHere=hi-lo;
        if(preserve>0.)lengthHere=mix(clamp(depth-lo,0.,lengthHere),lengthHere,preserve);
        if(lengthHere<=0.)continue;
        vec3 p=eye+ray*(lo+stepLength*(.30+.40*jitter));
        vec4 medium=densityAt(p);
        if(medium.a<.00001)continue;
        float alpha=1.-exp(-medium.a*lengthHere);
        scatter+=transmission*alpha*medium.rgb;transmission*=1.-alpha;
    }
    finalColor=vec4(scatter,1.-transmission);
}
