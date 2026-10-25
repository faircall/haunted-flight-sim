#version 330
uniform sampler2D depthMap,noiseMap,fieldMap,timingMap;
uniform vec2 resolution,lens,clip,causeway[6];
uniform vec3 eye,forward,right,up,fogColour;
uniform float clock,waterY,reflectedView,baseY,strength,textureGrit,wispyFormation;
uniform float formationBaseY,depthHold;
uniform vec3 fieldOrigin,fieldShape;
uniform vec2 atlasSize;
uniform float fieldSpacing,fieldDistanceCap,atlasColumns;
uniform float curveRadius,curveBuild,curveDescent,curveInitialScale,curveThickness;
out vec4 finalColor;

vec3 noise3(vec3 p){
    p=mod(p,32.);vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    vec2 xy=cell.xy+f.xy+1.5;float a=cell.z,b=mod(a+1.,32.);
    vec2 uv0=(vec2(mod(a,8.),floor(a/8.))*34.+xy)/vec2(272.,136.);
    vec2 uv1=(vec2(mod(b,8.),floor(b/8.))*34.+xy)/vec2(272.,136.);
    return mix(texture(noiseMap,uv0).rgb,texture(noiseMap,uv1).rgb,f.z);
}
float paintedGrain(vec3 flow,vec3 warp){
    // The original coarse fog-card artwork is packed in spare alpha. Its
    // broad painted tones roll through two world-space planes, not the screen.
    vec2 a=abs(fract((flow.xz+warp.xz*.55)*.29)*2.-1.);
    vec2 b=abs(fract((flow.zy+warp.zy*.34)*.37+vec2(.27,.51))*2.-1.);
    return clamp((texture(noiseMap,a).a*.64+texture(noiseMap,b).a*.36-.35)/.61,0.,1.);
}
float shoreRadius(float angle){
    float d=atan(sin(angle-1.5707963),cos(angle-1.5707963));float south=exp(-pow(d/.54,2.));
    float entry=atan(77.,-12.);float delta=atan(sin(angle-entry),cos(angle-entry));
    return 126.-51.*south+(1.-south)*(10.*sin(angle*3.+.2)+6.*sin(angle*7.-.6))-3.*exp(-pow(delta/.14,2.));
}
float waterFootprint(vec2 p){
    float shore=shoreRadius(atan(p.y,p.x));
    float water=1.-smoothstep(shore-1.2,shore+1.2,length(p));
    float hex=-100.;
    for(int i=0;i<6;i++){
        float angle=(float(i)+.5)*1.04719755;
        hex=max(hex,dot(p,vec2(cos(angle),sin(angle))));
    }
    // The unchanged deck has an exact hexagonal footprint. Its dense lower
    // fog lies below the paving; the interior remains completely clear.
    water*=smoothstep(6.0353829,6.2353829,hex);
    float path=100.;
    for(int i=0;i<5;i++){
        vec2 a=causeway[i],d=causeway[i+1]-a;
        float t=clamp(dot(p-a,d)/max(.001,dot(d,d)),0.,1.);
        path=min(path,length(p-a-t*d));
    }
    float shared=(1.-smoothstep(.90,1.04,path))*(1.-smoothstep(11.7,12.,p.y));
    return water*(1.-shared);
}
vec2 fieldUV(vec2 xz,float y){
    vec2 tile=vec2(mod(y,atlasColumns),floor(y/atlasColumns));
    return (tile*(fieldShape.xz+2.)+xz+1.5)/atlasSize;
}
float projectedSupport(vec2 xz){
    vec3 q=(vec3(xz.x,formationBaseY+.30,xz.y)-fieldOrigin)/fieldSpacing;
    if(any(lessThan(q,vec3(0.)))||any(greaterThan(q,fieldShape-1.)))return fieldDistanceCap;
    float y=floor(q.y),nextY=min(y+1.,fieldShape.y-1.);
    return mix(texture(fieldMap,fieldUV(q.xz,y)).a,
               texture(fieldMap,fieldUV(q.xz,nextY)).a,fract(q.y))*fieldDistanceCap;
}
vec2 lakeCurve(vec2 xz){
    // Bend the visible lake layer itself into the rising architectural mist.
    // The same real roof projection and growing per-house center keep this
    // continuous with the building banks, rather than an opaque flat lid.
    vec3 fieldPoint=(vec3(xz.x,formationBaseY+.30,xz.y)-fieldOrigin)/fieldSpacing;
    if(any(lessThan(fieldPoint,vec3(0.)))||any(greaterThan(fieldPoint,fieldShape-1.)))return vec2(0.);
    vec3 cell=clamp(floor(fieldPoint+.5),vec3(0.),fieldShape-1.);
    float owner=floor(texture(fieldMap,fieldUV(cell.xz,cell.y)).b*255.+.5);
    vec4 bounds=texelFetch(timingMap,ivec2(int(owner),1),0);
    vec2 halfSize=texelFetch(timingMap,ivec2(int(owner),2),0).rg;
    float scale=(owner>.5&&min(halfSize.x,halfSize.y)>0.)?mix(curveInitialScale,1.,curveBuild):1.;
    vec2 q=bounds.xz+(xz-bounds.xz)/scale;
    float d=max(0.,projectedSupport(q)*scale-curveThickness*.65);
    float width=max(.1,curveRadius*scale);
    // Quadratic Bezier from vertical wall to horizontal water:
    // x=W*t^2, h=H*(1-t)^2. Its outer tangent is exactly horizontal.
    float t=sqrt(clamp(d/width,0.,1.));
    float height=curveRadius*.65*curveBuild*(1.-.85*curveDescent);
    float slope=height*(1.-t)/(width*max(.06,t));
    return vec2(height*(1.-t)*(1.-t),slope);
}
void main(){
    vec2 uv=gl_FragCoord.xy/resolution,ndc=uv*2.-1.;
    vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float raw=texture(depthMap,uv).r;
    float depth=2.*clip.x*clip.y/(clip.y+clip.x-(raw*2.-1.)*(clip.y-clip.x))/max(.001,dot(ray,forward));
    float start=0.,finish=min(depth,260.);
    // Incoming walls and quay edges must not suddenly shorten the low fog's
    // optical path. Keep integrating through their still-concealed surfaces;
    // the veil's gradual strength envelope reveals them later. The unchanged
    // pavilion/eaves and the exact curved causeway retain normal depth tests,
    // as do both water levels. This is a transient medium, never a depth write.
    vec3 hit=eye+ray*depth;
    float pathHold=0.;
    if(wispyFormation>.5 && length(hit.xz)>9. && hit.y>formationBaseY+.07 && waterFootprint(hit.xz)>.5)
        pathHold=clamp(depthHold,0.,1.);
    if(pathHold>0.)
        finish=260.;
    // The shared timeline holds this slab at the ORIGINAL lake through the
    // whole handoff, then slowly lowers it toward the canal water afterwards.
    float maximumLift=curveRadius*.65*curveBuild*(1.-.85*curveDescent);
    float low=baseY+.025,high=baseY+1.45+maximumLift+(curveRadius>0.?.5:0.);
    if(abs(ray.y)<.000001){
        if(eye.y<low||eye.y>high){finalColor=vec4(0.);return;}
    }else{
        float a=(low-eye.y)/ray.y,b=(high-eye.y)/ray.y;
        start=max(start,min(a,b));finish=min(finish,max(a,b));
    }
    if(reflectedView>.5){
        if(abs(ray.y)<.000001){if(eye.y<waterY)finish=start;}
        else if(ray.y>0.)start=max(start,(waterY-eye.y)/ray.y);
        else finish=min(finish,(waterY-eye.y)/ray.y);
    }
    if(finish<=start||strength<=0.){finalColor=vec4(0.);return;}
    float transmission=1.;vec3 scatter=vec3(0.);
    // Slab entry and fixed increments define sampling, never background
    // depth. Thus a water-height change cannot redraw the fog's pattern.
    float stepLength=clamp(.028/max(.005,abs(ray.y)),.028,1.);
    float jitter=fract(52.9829189*fract(dot(floor(gl_FragCoord.xy),vec2(.06711056,.00583715))));
    float travel=start;
    for(int i=0;i<384;i++){
        if(curveRadius<=0.&&i>=96)break;
        float lo=curveRadius>0.?travel:start+float(i)*stepLength;
        if(lo>=finish||transmission<.0004)break;
        if(curveRadius>0.){
            // A vertical sample interval alone aliases the steep side of a
            // curved bank into contour ribs. Resolve its quadratic slope in
            // world space; only the thin cap needs these finer samples.
            vec3 probe=eye+ray*lo;
            vec2 section=lakeCurve(probe.xz);
            float relative=probe.y-baseY-section.x;
            float rate=max(.008,abs(ray.y)+section.y*length(ray.xz)+smoothstep(.02,.5,section.x)*.45);
            float empty=max(relative-1.95,.20-relative);
            stepLength=clamp(max(.036,empty*.6)/rate,.018,1.25);
        }
        travel=lo+stepLength;
        float lengthHere=min(stepLength,finish-lo);
        // Fade only the optical contribution behind actual geometry. Keep
        // slab-anchored samples fixed instead of sliding the ray endpoint
        // through its noise pattern as normal depth occlusion is restored.
        if(pathHold>0.)
            lengthHere=mix(clamp(depth-lo,0.,lengthHere),lengthHere,pathHold);
        if(lengthHere<=0.)continue;
        vec3 p=eye+ray*(lo+stepLength*(.3+.4*jitter));
        float footprint=waterFootprint(p.xz);
        if(footprint<.0001)continue;
        float lift=curveRadius>0.?lakeCurve(p.xz).x:0.;
        vec3 flowPoint=p;
        // Keep three-dimensional clouds independent of the profile. Draping
        // their coordinates over the cap makes it resemble a solid surface.
        if(curveRadius>0.)flowPoint.y-=baseY;
        vec3 flow=flowPoint*vec3(.30,.86,.30)+vec3(-clock*.035,clock*.011,clock*.026);
        vec3 broad=noise3(flow);
        vec3 detail=noise3(flow*2.11+vec3(11,7,23)+(broad-.5)*.7);
        float height=p.y-baseY;
        float curvedWeight=smoothstep(.05,.65,lift);
        float capNoise=curvedWeight*((broad.g-.5)*.65+(detail.r-.5)*.20);
        float curvedHeight=height-lift-capNoise;
        float bottom=smoothstep(.025,.065,height);
        // The minimum top of the dense core is above the new quay's .325m
        // paving. Its appearance therefore cannot shorten the opaque part of
        // a water ray. Modulated tops and tall sparse lobes avoid a flat sheet.
        float coreTop=.44+.10*broad.g;
        float core=bottom*(1.-smoothstep(coreTop,coreTop+.22,curvedHeight));
        float upper=1.03+.25*broad.r+.10*detail.g;
        float fringe=bottom*(1.-smoothstep(.44,upper,curvedHeight));
        fringe*=smoothstep(.22,.75,.72*broad.g+.28*detail.r);
        float filaments=exp(-((broad.g-.49)*(broad.g-.49)+(detail.b-.51)*(detail.b-.51))*64.);
        float wisps=bottom*(1.-smoothstep(.55,upper+.06,curvedHeight))*filaments;
        // A guaranteed low core masks glints and the level drop. Sparse
        // rolling lobes above it connect to the existing lake mist.
        float coreDensity=30.*core*(.94+.12*broad.b);
        float fringeDensity=3.5*fringe;
        if(curveRadius>0.){
            // Preserve the proven low water mask, but make the raised part a
            // porous cloud rather than extruding that opaque core into hills.
            float lowCore=bottom*(1.-smoothstep(coreTop,coreTop+.22,height));
            float pores=smoothstep(.25,.72,broad.r*.58+detail.g*.42);
            float extension=max(0.,core-lowCore);
            coreDensity=30.*lowCore*(.94+.12*broad.b)+5.5*extension*(.08+.92*pores);
            fringeDensity*=mix(1.,.42,curvedWeight);
        }
        float sigma=strength*footprint*(coreDensity+fringeDensity+1.4*wisps);
        float alpha=1.-exp(-sigma*lengthHere);
        float grain=paintedGrain(flow,broad-.5);
        float shaded=noise3(flow+vec3(-.45,.8,.3)).r;
        float light=clamp(.5+(broad.r-shaded)*1.2+(detail.b-.5)*.16+(grain-.5)*textureGrit*.7,0.,1.);
        light=mix(light,floor(light*6.+.5)/6.,textureGrit*.7);
        vec3 colour=fogColour*(.85+.30*light);
        scatter+=transmission*alpha*colour;transmission*=1.-alpha;
    }
    finalColor=vec4(scatter,1.-transmission);
}
