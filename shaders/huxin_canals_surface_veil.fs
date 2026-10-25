#version 330
uniform sampler2D depthMap,noiseMap;
uniform vec2 resolution,lens,clip,causeway[6];
uniform vec3 eye,forward,right,up,fogColour;
uniform float clock,waterY,reflectedView,baseY,strength,textureGrit,wispyFormation;
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
    if(wispyFormation>.5 && length(hit.xz)>9. && hit.y>baseY+.07 && waterFootprint(hit.xz)>.5)
        finish=260.;
    // Every density sample is above the ORIGINAL lake. Both old and lowered
    // water therefore sit behind exactly the same complete optical path.
    float low=baseY+.025,high=baseY+1.45;
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
    for(int i=0;i<96;i++){
        float lo=start+float(i)*stepLength;
        if(lo>=finish||transmission<.0004)break;
        float lengthHere=min(stepLength,finish-lo);
        vec3 p=eye+ray*(lo+stepLength*(.3+.4*jitter));
        float footprint=waterFootprint(p.xz);
        if(footprint<.0001)continue;
        vec3 flow=p*vec3(.30,.86,.30)+vec3(-clock*.035,clock*.011,clock*.026);
        vec3 broad=noise3(flow);
        vec3 detail=noise3(flow*2.11+vec3(11,7,23)+(broad-.5)*.7);
        float height=p.y-baseY;
        float bottom=smoothstep(.025,.065,height);
        // The minimum top of the dense core is above the new quay's .325m
        // paving. Its appearance therefore cannot shorten the opaque part of
        // a water ray. Modulated tops and tall sparse lobes avoid a flat sheet.
        float coreTop=.44+.10*broad.g;
        float core=bottom*(1.-smoothstep(coreTop,coreTop+.22,height));
        float upper=1.03+.25*broad.r+.10*detail.g;
        float fringe=bottom*(1.-smoothstep(.44,upper,height));
        fringe*=smoothstep(.22,.75,.72*broad.g+.28*detail.r);
        float filaments=exp(-((broad.g-.49)*(broad.g-.49)+(detail.b-.51)*(detail.b-.51))*64.);
        float wisps=bottom*(1.-smoothstep(.55,upper+.06,height))*filaments;
        // A guaranteed low core masks glints and the level drop. Sparse
        // rolling lobes above it connect to the existing lake mist.
        float sigma=strength*footprint*(30.*core*(.94+.12*broad.b)+3.5*fringe+1.4*wisps);
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
