#version 330
uniform sampler2D depthMap,noiseMap,fieldMap,timingMap;
uniform vec2 resolution,lens,clip,atlasSize,causeway[6];
uniform vec3 eye,forward,right,up,fogColour,fieldOrigin,fieldShape,wind;
uniform float spacing,distanceCap,atlasColumns,clock,elapsed,waterY,reflectedView;
uniform float amount,density,thickness,edge,noiseSize,patternAmount,buildStart,buildEnd,stepCount;
uniform float riseResolve,initialScale,settleFraction,baseY;
uniform float condenseMode,pullDuration,wispAmount,textureGrit,wispyFormation,pixelGrain;
uniform float footCurve,lakeBaseY,lakeOwnsCurve,progressiveLake;
out vec4 finalColor;

// BEGIN CONDENSE
// Shared by the fog and material shaders. Keep this block identical in both:
// the wall texture must emerge exactly where the local inward pull arrives.
float condenseEase(float a,float b,float value){
    float t=clamp((value-a)/max(.0001,b-a),0.,1.);
    return t*t*t*(10.+t*(-15.+6.*t));
}
float condenseHash(vec3 p){
    p=fract(p*.1031);p+=dot(p,p.yzx+33.33);
    return fract((p.x+p.y)*p.z);
}
float condenseNoise(vec3 p){
    vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(condenseHash(cell),condenseHash(cell+vec3(1,0,0)),f.x),
                   mix(condenseHash(cell+vec3(0,1,0)),condenseHash(cell+vec3(1,1,0)),f.x),f.y),
               mix(mix(condenseHash(cell+vec3(0,0,1)),condenseHash(cell+vec3(1,0,1)),f.x),
                   mix(condenseHash(cell+vec3(0,1,1)),condenseHash(cell+vec3(1,1,1)),f.x),f.y),f.z);
}
// x: tightening; y: physical inward pull; z: lingering wisps; w: real material.
vec4 condensePhases(vec3 anchor,vec2 window,float now,float holdFraction,
                    float seconds,float size,float pattern){
    float span=max(.1,window.y-window.x);
    float starts=window.x+span*holdFraction;
    float duration=min(seconds,span*(1.-holdFraction)*.55);
    duration=max(.0001,duration);
    // A fixed 3D pattern staggers small parts of the same facade. It never
    // scrolls back over a revealed surface, or changes when the camera moves.
    float delay=condenseNoise(anchor/max(.3,size)+vec3(7.1,13.7,3.9))*duration*.35*pattern;
    starts+=delay;
    float ends=starts+duration;
    float raw=clamp((now-starts)/duration,0.,1.);
    // Long pulls should use their full duration, rather than reserving most
    // visible material emergence for a short central burst.
    float patient=condenseEase(3.,6.,duration);
    float pull=mix(condenseEase(0.,1.,raw),raw*raw*(3.-2.*raw),patient);
    float material=mix(condenseEase(.18,.84,raw),condenseEase(.03,.97,raw),patient);
    return vec4(condenseEase(window.x,starts,now),pull,
                1.-condenseEase(ends,window.y,now),material);
}
// END CONDENSE


float ease(float a,float b,float x){float t=clamp((x-a)/max(.001,b-a),0.,1.);return t*t*t*(10.+t*(-15.+6.*t));}
vec3 noise3(vec3 p){
    p=mod(p,32.);vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    vec2 xy=cell.xy+f.xy+1.5;float a=cell.z,b=mod(a+1.,32.);
    vec2 uv0=(vec2(mod(a,8.),floor(a/8.))*34.+xy)/vec2(272.,136.);
    vec2 uv1=(vec2(mod(b,8.),floor(b/8.))*34.+xy)/vec2(272.,136.);
    return mix(texture(noiseMap,uv0).rgb,texture(noiseMap,uv1).rgb,f.z);
}
float paintedGrain(vec3 flow,vec3 warp){
    // Original 64px cloud artwork, mirrored through two world-space planes.
    // RGB of this texture is still the independent 32-cubed noise lattice.
    vec2 a=abs(fract((flow.xy+warp.xy*.45)*.29)*2.-1.);
    vec2 b=abs(fract((flow.zy+warp.zy*.31)*.37+vec2(.27,.51))*2.-1.);
    float grain=texture(noiseMap,a).a*.58+texture(noiseMap,b).a*.42;
    if(pixelGrain>0.){
        // Nearest 32px painted cells deliberately retain the old card fog's
        // crunchy marks. Only artwork is coarse; depth stays full resolution.
        vec2 ca=(floor(a*32.)+.5)/32.,cb=(floor(b*32.)+.5)/32.;
        float coarse=texelFetch(noiseMap,ivec2(ca*vec2(272,136)),0).a*.58+
                     texelFetch(noiseMap,ivec2(cb*vec2(272,136)),0).a*.42;
        grain=mix(grain,coarse,pixelGrain);
    }
    return clamp((grain-.35)/.61,0.,1.);
}
vec4 pixelFog(vec4 fog){
    if(pixelGrain<=0.||fog.a<.00001)return fog;
    // An intentional two-pixel ordered grain, restricted to partial coverage.
    // Opaque concealment stays opaque and the native depth silhouette is never
    // downsampled. A stationary pattern avoids temporal sparkle when paused.
    ivec2 p=ivec2(floor(gl_FragCoord.xy*.5));
    int bayer[16]=int[16](0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5);
    float threshold=(float(bayer[(p.y%4)*4+p.x%4])+.5)/16.;
    float quantized=floor(fog.a*7.+threshold)/7.;
    float weight=pixelGrain*(1.-smoothstep(.94,.995,fog.a));
    float alpha=mix(fog.a,quantized,weight);
    return vec4(fog.rgb*(alpha/fog.a),alpha);
}
vec2 fieldUV(vec2 xz,float y){
    vec2 tile=vec2(mod(y,atlasColumns),floor(y/atlasColumns));
    return (tile*(fieldShape.xz+2.)+xz+1.5)/atlasSize;
}
float distanceField(vec3 p){
    vec3 q=(p-fieldOrigin)/spacing;
    if(any(lessThan(q,vec3(0.)))||any(greaterThan(q,fieldShape-1.)))return distanceCap;
    float y=floor(q.y),nextY=min(y+1.,fieldShape.y-1.);
    return mix(texture(fieldMap,fieldUV(q.xz,y)).r,
               texture(fieldMap,fieldUV(q.xz,nextY)).r,fract(q.y))*distanceCap;
}
float supportField(vec3 p){
    vec3 q=(p-fieldOrigin)/spacing;
    if(any(lessThan(q,vec3(0.)))||any(greaterThan(q,fieldShape-1.)))return distanceCap;
    float y=floor(q.y),nextY=min(y+1.,fieldShape.y-1.);
    return mix(texture(fieldMap,fieldUV(q.xz,y)).a,
               texture(fieldMap,fieldUV(q.xz,nextY)).a,fract(q.y))*distanceCap;
}
float footWaterSpace(vec2 p){
    // The same exact hexagonal pavilion and curved shared path as the low
    // veil. The new fillet belongs to water beside them, not their paving.
    float hex=-100.;
    for(int i=0;i<6;i++){
        float a=(float(i)+.5)*1.04719755;
        hex=max(hex,dot(p,vec2(cos(a),sin(a))));
    }
    float water=smoothstep(6.0353829,6.2353829,hex);
    float path=100.;
    for(int i=0;i<5;i++){
        vec2 a=causeway[i],d=causeway[i+1]-a;
        float t=clamp(dot(p-a,d)/max(.001,dot(d,d)),0.,1.);
        path=min(path,length(p-a-t*d));
    }
    float shared=(1.-smoothstep(.90,1.04,path))*(1.-smoothstep(11.7,12.,p.y));
    return water*(1.-shared);
}
float fogDistance(vec3 p,float support){
    float surface=distanceField(p);
    if(support>.0001)surface=min(surface,supportField(p)+(1.-support)*(thickness+1.8));
    return surface;
}
float ownerAt(vec3 p){
    vec3 q=clamp(floor((p-fieldOrigin)/spacing+.5),vec3(0.),fieldShape-1.);
    return floor(texture(fieldMap,fieldUV(q.xz,q.y)).b*255.+.5);
}
bool interval(vec3 origin,vec3 ray,out float nearT,out float farT){
    nearT=0.;farT=1.e20;
    vec3 hi=fieldOrigin+(fieldShape-1.)*spacing;
    for(int axis=0;axis<3;axis++){
        if(abs(ray[axis])<.000001){if(origin[axis]<fieldOrigin[axis]||origin[axis]>hi[axis])return false;}
        else{float a=(fieldOrigin[axis]-origin[axis])/ray[axis],b=(hi[axis]-origin[axis])/ray[axis];nearT=max(nearT,min(a,b));farT=min(farT,max(a,b));}
    }
    return farT>nearT;
}
float traceGate(float progress,float pattern){
    float phase=mix(.5,.2+.6*pattern,patternAmount);
    return smoothstep(phase-.15,phase+.15,progress);
}
// Inverse-map the real architecture into its growing, water-rooted envelope.
// Metadata is per house: neighbouring roofs never shrink about the district's
// origin. Generic quays remain in place and emerge through a low rising front.
vec3 growingPoint(vec3 p,float owner,float build,out float scaleXZ,out float scaleY,out float top){
    vec4 bounds=texelFetch(timingMap,ivec2(int(owner),1),0);
    vec2 halfSize=texelFetch(timingMap,ivec2(int(owner),2),0).rg;
    bool named=owner>.5&&min(halfSize.x,halfSize.y)>0.;
    scaleXZ=named?mix(initialScale,1.,build):1.;
    scaleY=mix(.035,1.,build);
    top=bounds.y+bounds.w*scaleY;
    if(!named){scaleY=1.;return p;}
    return vec3(bounds.x+(p.x-bounds.x)/scaleXZ,
                bounds.y+(p.y-bounds.y)/scaleY,
                bounds.z+(p.z-bounds.z)/scaleXZ);
}
// The unsigned field's gradient points away from the closest real surface.
// Four tetrahedral samples are stable at the baked voxel scale, including
// concave roofs and door recesses. Flat occupied cells use a gentle fallback.
vec3 surfaceOutward(vec3 p,float owner){
    vec3 a=vec3(1,-1,-1),b=vec3(-1,-1,1),c=vec3(-1,1,-1),d=vec3(1,1,1);
    float h=max(.35,spacing*.9);
    vec3 gradient=a*distanceField(p+a*h)+b*distanceField(p+b*h)+
                  c*distanceField(p+c*h)+d*distanceField(p+d*h);
    if(dot(gradient,gradient)>.0001)return normalize(gradient);
    vec4 bounds=texelFetch(timingMap,ivec2(int(owner),1),0);
    vec3 fallback=p-vec3(bounds.x,bounds.y+bounds.w*.45,bounds.z);
    if(owner<.5||dot(fallback,fallback)<.001)return vec3(0,1,0);
    return normalize(fallback);
}
vec4 riseFog(vec3 ray,float start,float finish,float build,float jitter,float sceneDepth,float behindFog){
    float transmission=1.,travel=start;vec3 scatter=vec3(0.);
    float buildTime=clamp((elapsed-buildStart)/max(.1,buildEnd-buildStart),0.,1.);
    float forming=ease(0.,.38,buildTime);
    if(condenseMode>.5)forming=mix(forming,pow(ease(0.,1.,buildTime),1.35),ease(0.,.5,textureGrit));
    bool waterRooted=condenseMode>.5&&wispyFormation>.5;
    if(waterRooted)forming=pow(ease(0.,1.,buildTime),.85);
    if(forming<.00001)return vec4(0.);
    for(int i=0;i<256;i++){
        if(float(i)>=stepCount||travel>=finish||transmission<.0015)break;
        vec3 p=eye+ray*travel;
        float owner=ownerAt(p),scaleXZ,scaleY,top;
        vec3 q=growingPoint(p,owner,build,scaleXZ,scaleY,top);
        vec2 timing=texelFetch(timingMap,ivec2(int(owner),0),0).rg;
        float progress=clamp((elapsed-timing.x)/max(.1,timing.y-timing.x),0.,1.);
        float settled=ease(0.,settleFraction,progress);
        float irregular=(1.-settled)*patternAmount;
        float reach=mix(thickness*mix(.20,1.,build),.085,settled);
        bool condensing=condenseMode>.5&&progress>0.;
        vec4 phases=vec4(0,0,1,0);
        if(condensing){
            phases=condensePhases(p,timing,elapsed,settleFraction,pullDuration,noiseSize,patternAmount);
            settled=.45*phases.x+.55*phases.y;
            irregular=patternAmount*(1.-.45*phases.x)*(1.-phases.y);
            reach=mix(thickness*(1.-.25*phases.x),.065,phases.y);
        }
        float support=waterRooted?1.-ease(.05,.92,phases.y):0.;
        float roughness=textureGrit*(condenseMode>.5?1.:0.);
        float marchReach=condensing?max(reach,mix(reach,thickness*.85+.6,phases.x)):reach;
        marchReach+=roughness*.8*(1.-phases.y);
        float rawDistance=fogDistance(q,support),surface=rawDistance*scaleXZ;
        // The descending lake veil now owns the visible curved bank. Keeping
        // a second per-house fillet here would leave a late mound underneath
        // it, collapsing abruptly when that house reaches its inward pull.
        bool curvedFoot=waterRooted&&footCurve>0.&&lakeOwnsCurve<.5;
        float footRadius=footCurve*scaleXZ;
        float footSkip=distanceCap;
        // Follow the transformed field even inside the original hollow walls.
        // Original-surface skipping would jump past the compressed seed.
        float stepLength=rawDistance*min(scaleXZ,scaleY)-marchReach-.75;
        if(scaleY<1.){
            vec4 bounds=texelFetch(timingMap,ivec2(int(owner),1),0);
            vec2 halfSize=texelFetch(timingMap,ivec2(int(owner),2),0).rg;
            float low=baseY-.25-4.*build;
            vec3 center=vec3(bounds.x,(top+low)*.5,bounds.z);
            vec3 halfBounds=vec3(halfSize.x*scaleXZ,(top-low)*.5,halfSize.y*scaleXZ)+marchReach+1.4;
            // A conservative transformed-field distance protects thin early
            // roofs. Outside the padded growing bounds we can still advance.
            stepLength=max(stepLength,length(max(abs(p-center)-halfBounds,vec3(0.))));
        }
        if(curvedFoot){
            // Project the real roofed footprint to its original lake datum.
            // This broadens only the foot of each bank, never the whole wall.
            float projected=supportField(vec3(q.x,baseY+.30,q.z))*scaleXZ;
            footSkip=max(projected-footRadius-thickness-1.2,
                max(p.y-lakeBaseY-.65-footCurve*.65*build-.8,lakeBaseY-.4-p.y));
            stepLength=min(stepLength,footSkip);
        }
        stepLength=clamp(stepLength,.22,6.);
        if((surface<marchReach+.75||(curvedFoot&&footSkip<1.))&&stepLength<1.)stepLength=.22+min(travel*.002,.22);
        stepLength=min(stepLength,finish-travel);
        p+=ray*stepLength*(.25+.5*jitter);travel+=stepLength;
        if(surface>marchReach+1.4&&(!curvedFoot||footSkip>1.4))continue;
        q=growingPoint(p,owner,build,scaleXZ,scaleY,top);
        float ownership=(scaleXZ<1.&&abs(ownerAt(q)-owner)>.5)?ease(.94,1.,build):1.;
        vec3 flow=(p-wind*clock)/noiseSize;
        vec3 normal=vec3(0,1,0);
        if(condensing){
            normal=surfaceOutward(q,owner);
            vec3 anchor=q-normal*distanceField(q);
            phases=condensePhases(anchor,timing,elapsed,settleFraction,pullDuration,noiseSize,patternAmount);
            settled=.45*phases.x+.55*phases.y;
            irregular=patternAmount*(1.-.45*phases.x)*(1.-phases.y);
            reach=mix(thickness*(1.-.25*phases.x),.065,phases.y);
            // Backtrace the density along an inward velocity. Billows travel
            // into the architecture; this is more than changing their alpha.
            flow=(p+normal*(.22*phases.x+1.65*phases.y)-wind*clock)/noiseSize;
        }
        vec3 broad=noise3(flow);
        vec3 detail=noise3(flow*2.17+vec3(11.,7.,23.)+(broad-.5)*.8);
        vec3 warp=(broad-.5)*1.15*irregular;
        warp+=(detail-.5)*.8*irregular*roughness;
        float warped=fogDistance(q+warp/max(.25,scaleXZ),support)*scaleXZ;
        reach=max(.065,reach+(.72*broad.r+.28*detail.g-.5)*.55*irregular);
        reach=max(.065,reach+(detail.r-.5)*.65*irregular*roughness);
        float body=(1.-smoothstep(reach*(1.-edge),reach,warped))*ownership;
        float grain=.5,frayed=0.;
        if(roughness>0.){
            grain=paintedGrain(flow,broad-.5);
            // Porous, textured outer billows surround a denser interior close
            // to the real surface. Two 3D level sets make branching filaments.
            float edgeBand=smoothstep(reach*.12,reach*.85,warped);
            float pores=smoothstep(.20,.72,broad.b*.42+detail.r*.33+grain*.25);
            body*=mix(1.,.10+.90*pores,roughness*edgeBand);
            vec3 crossing=noise3(flow.zxy*1.43+vec3(19,3,11)+(detail-.5)*.7);
            float a=detail.g-.5,b=crossing.b-.5;
            float threads=exp(-(a*a+b*b)*96.);
            float outside=1.-smoothstep(reach*.4,reach+.85*roughness,warped);
            frayed=outside*threads*(.20+.8*grain)*roughness*.30*(1.-phases.y);
        }
        if(waterRooted){
            // Formation uses the same drifting filaments as the trailing
            // wisps. It becomes a concealing body only as the last high wisps
            // reach roof height. There is no early translucent solid house.
            float fullHeight=ease(.87,.9995,build);
            vec3 curls=noise3(flow*vec3(1.35,.8,1.35)+(broad-.5)*.65+vec3(4,17,9));
            float fragments=smoothstep(.49,.76,curls.r+.22*(detail.g-.5));
            fragments*=smoothstep(.32,.59,curls.b);
            float veins=exp(-pow((detail.g-.5)*7.,2.))*smoothstep(.30,.68,broad.b);
            float airy=(fragments*.30+veins*.10)*(.30+1.1*grain);
            if(curvedFoot){
                // Quadratic Bezier section: (0,H), (0,0), (W,0).
                // x=W*t*t, y=H*(1-t)^2: vertical at the wall and horizontal
                // at the lake. Drifting noise frays this volumetric boundary.
                vec3 projected=vec3(q.x+warp.x/max(.25,scaleXZ),baseY+.30,
                                    q.z+warp.z/max(.25,scaleXZ));
                float d=max(0.,supportField(projected)*scaleXZ-reach*.65);
                float width=max(.1,footRadius*(1.-.55*phases.y));
                float t=sqrt(clamp(d/width,0.,1.));
                float lift=footCurve*.65*build*(1.-.8*phases.y)*(1.-t)*(1.-t);
                float cap=lakeBaseY+.64+lift+(.7*broad.g+.3*detail.r-.5)*.45*irregular;
                float fillet=(1.-smoothstep(cap-.30,cap+.48,p.y));
                fillet*=smoothstep(lakeBaseY-.25,lakeBaseY+.08,p.y);
                fillet*=1.-smoothstep(width*.82,width+.35,d);
                fillet*=.65+.35*smoothstep(.20,.72,broad.b*.42+detail.r*.33+grain*.25);
                body=max(body,fillet*ownership*footWaterSpace(p.xz));
            }
            body*=mix(airy,1.,fullHeight);
            frayed*=mix(1.6,1.,fullHeight);
            // Full-height roots hold a deep optical path through open ground
            // floors and under eaves. Their inner density is temporary; it
            // contracts into the real walls during the existing slow pull.
            float rooted=1.-smoothstep(.05,thickness*.85,supportField(q));
            float hold=fullHeight*support*(1.-phases.y);
            if(progressiveLake>.5)hold*=1.-.8*phases.x;
            body*=1.+rooted*hold*2.2;
        }
        // Feathery leading wisps rise from the same fixed lake datum in both
        // worlds and in reflections. No mid-air opacity switch or moving plane.
        float front=top+(.7*broad.g+.3*detail.r-.5)*(.65+roughness*1.7*build)*irregular;
        if(waterRooted)front+=ease(.87,.9995,build)*(thickness+.65*roughness+.3);
        float heightMask=1.-smoothstep(front-.12,front+.22+.35*build,p.y);
        float bottom=baseY-mix(.20,3.8,build);
        float spatial=heightMask*smoothstep(bottom-.18,bottom+.15,p.y);
        if(!condensing)body=(body+frayed)*spatial;
        float quiet=max(abs(p.x)/5.3,abs(p.z-.4)/5.3);
        spatial*=smoothstep(.86,1.15,quiet);
        if(!condensing)body*=smoothstep(.86,1.15,quiet);
        // Turbulence collapses first. The exact mesh then supplies the quiet
        // fog-coloured silhouette; its textures are the final reveal stage.
        float remaining=1.-ease(settleFraction*.72,min(.98,settleFraction+.16),progress);
        float variation=mix(1.,.72+.55*broad.g+.22*detail.b,1.-settled);
        float sigma;
        if(condensing){
            // Keep substance during the pull; shrinking its occupied space
            // does the clearing. Residual fragments keep flowing afterwards.
            remaining=1.-ease(mix(.72,.10,roughness),1.,phases.y);
            // Use the smooth envelope, not the noise-modulated reach: the
            // first instant of tightening must retain exactly unit density.
            float compression=min(mix(3.,1.5,roughness),thickness/max(.20,mix(thickness*(1.-.25*phases.x),.065,phases.y)));
            // Once the descending-lake version begins tightening, stop
            // compensating for every reduction in occupied fog volume. The
            // hidden crest retains its original density; the long pull then
            // produces visible progress instead of a late saturation break.
            if(progressiveLake>.5)compression=mix(compression,1.,phases.x);
            float core=(body+frayed)*remaining*variation*compression;
            if(progressiveLake>.5&&phases.x>0.){
                // Begin admitting faint architectural silhouettes while the
                // bank tightens. Calibrating a thick core's transmission avoids
                // ten seconds of saturated opacity followed by a short collapse.
                // No relief is applied at the concealed geometry handoff.
                float earlyClear=.22*phases.x;
                core*=-log(earlyClear+(1.-earlyClear)*exp(-8.))/8.;
            }
            float wisps=0.;
            if(wispAmount>0.&&phases.y>.08&&phases.z>0.){
                vec3 tailFlow=flow+normal*((1.-phases.z)*.65/noiseSize);
                vec3 curls=noise3(tailFlow*vec3(1.35,.8,1.35)+(broad-.5)*.65+vec3(4,17,9));
                float fragments=smoothstep(mix(.52,.44,roughness),.77,curls.r+.18*(detail.g-.5));
                fragments*=smoothstep(.30,.58,curls.b);
                float shell=1.-smoothstep(.12,thickness*.85+.55,distanceField(q+(curls-.5)*.24));
                float wall=1.-.55*max(0.,normal.y);
                wisps=fragments*shell*wall*wispAmount*.75*ease(.08,.65,phases.y)*phases.z;
            }
            sigma=density*amount*forming*spatial*(core+wisps);
        }else sigma=density*amount*body*forming*remaining*variation;
        // A newly inserted wall must not cut an already-established fog ray
        // short. Continue through its hidden negative spaces until the same
        // local phase that reveals its material restores ordinary occlusion.
        if(waterRooted&&travel>sceneDepth)sigma*=behindFog;
        if(sigma<.0001)continue;
        float shaded=noise3(flow+vec3(-.48,.85,.32)).r;
        float light=clamp(.49+(broad.r-shaded)*1.65+(detail.b-.5)*.24,0.,1.);
        light=mix(light,floor(light*5.+.5)/5.,.5);
        float colourSettled=condensing?settled*(1.-.3*ease(.6,1.,phases.y)):settled;
        vec3 colour=fogColour*mix(.84+.32*light,1.,colourSettled);
        if(roughness>0.)colour*=mix(1.,.80+.40*grain,roughness*(1.-.35*phases.y));
        if(pixelGrain>0.)colour*=mix(1.,.74+.52*(floor(grain*5.+.5)/5.),pixelGrain*.65);
        float alpha=1.-exp(-sigma*stepLength);
        scatter+=transmission*alpha*colour;transmission*=1.-alpha;
    }
    return vec4(scatter,1.-transmission);
}
void main(){
    vec2 uv=gl_FragCoord.xy/resolution,ndc=uv*2.-1.;
    vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float start,finish;
    if(!interval(eye,ray,start,finish)){finalColor=vec4(0.);return;}
    float raw=texture(depthMap,uv).r;
    float depth=2.*clip.x*clip.y/(clip.y+clip.x-(raw*2.-1.)*(clip.y-clip.x))/max(.001,dot(ray,forward));
    float behindFog=0.;
    if(condenseMode>.5&&wispyFormation>.5){
        vec3 hit=eye+ray*depth;
        // The shared pavilion, its occupants and low causeway retain normal
        // depth. Only temporary incoming architecture can be transparent to
        // fog integration; the visible geometry itself remains unchanged.
        if(length(hit.xz)>9.&&hit.y>baseY+.65&&distanceField(hit)<max(1.2,spacing*2.)){
            float owner=ownerAt(hit);
            vec2 timing=texelFetch(timingMap,ivec2(int(owner),0),0).rg;
            behindFog=1.-condensePhases(hit,timing,elapsed,settleFraction,pullDuration,noiseSize,patternAmount).w;
        }
    }
    if(behindFog<.0001)finish=min(finish,depth);
    if(reflectedView>.5){
        if(abs(ray.y)<.00001){if(eye.y<waterY)finish=start;}
        else if(ray.y>0.)start=max(start,(waterY-eye.y)/ray.y);
        else finish=min(finish,(waterY-eye.y)/ray.y);
    }
    if(finish<=start){finalColor=vec4(0.);return;}
    float build=ease(buildStart,buildEnd,elapsed);
    float transmission=1.,travel=start;vec3 scatter=vec3(0.);
    // Geometry, not the changing background depth, anchors the ray samples.
    // Empty-space skipping follows the actual surface field, including holes.
    float jitter=fract(52.9829189*fract(dot(floor(gl_FragCoord.xy),vec2(.06711056,.00583715))));
    if(riseResolve>.5){finalColor=pixelFog(riseFog(ray,start,finish,build,jitter,depth,behindFog));return;}
    for(int i=0;i<256;i++){
        if(float(i)>=stepCount||travel>=finish||transmission<.0015)break;
        vec3 p=eye+ray*travel;float surface=distanceField(p);
        float stepLength=clamp(surface-thickness-1.7,.34,7.);
        if(surface<thickness+1.7)stepLength=.34+min(travel*.006,.55);
        stepLength=min(stepLength,finish-travel);
        p+=ray*stepLength*(.25+.5*jitter);travel+=stepLength;
        if(surface>thickness+2.5)continue;
        vec3 flow=(p-wind*clock)/noiseSize;
        vec3 broad=noise3(flow);
        vec3 warp=(broad-.5)*1.7;
        // Noise changes the 3D boundary itself, rather than painting streaks
        // over an expanded copy of a wall. A dense interior hides its surface.
        float warped=distanceField(p+warp);
        vec3 detail=noise3(flow*2.17+vec3(11.,7.,23.)+(broad-.5)*.8);
        float reach=max(.15,thickness+(.72*broad.r+.28*detail.g-.5)*1.8);
        float body=1.-smoothstep(reach*(1.-edge),reach,warped);
        // Keep only the shared pavilion's inner refuge clear. No new ring is
        // generated: outside this pocket the actual architecture owns density.
        float quiet=max(abs(p.x)/5.3,abs(p.z-.4)/5.3);
        body*=smoothstep(.86,1.15,quiet);
        if(body<.0001)continue;
        float owner=ownerAt(p);vec4 timing=texelFetch(timingMap,ivec2(int(owner),0),0);
        float clear=ease(timing.r,timing.g,elapsed);
        // Slow, world-anchored tracing is distinct from the billows' wind.
        vec3 pattern=noise3(p/(noiseSize*1.55)+vec3(11.7,3.1,27.4));
        float trace=clamp(pattern.r*.72+(.5+.5*sin(p.y*.34+p.x*.045-p.z*.039))*.28,0.,1.);
        float forming=traceGate(build,trace),remaining=1.-traceGate(clear,1.-trace);
        float sigma=density*amount*body*forming*remaining*(.72+.55*broad.g+.22*detail.b);
        if(sigma<.0001)continue;
        float shaded=noise3(flow+vec3(-.48,.85,.32)).r;
        float light=clamp(.49+(broad.r-shaded)*1.65+(detail.b-.5)*.24,0.,1.);
        light=mix(light,floor(light*5.+.5)/5.,.5);
        vec3 colour=fogColour*(.59+.79*light);
        float alpha=1.-exp(-sigma*stepLength);
        scatter+=transmission*alpha*colour;transmission*=1.-alpha;
    }
    finalColor=vec4(scatter,1.-transmission);
}
