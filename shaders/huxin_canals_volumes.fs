#version 330
uniform sampler2D depthMap,noiseMap;
uniform vec2 resolution,lens,clip,rotation;
uniform vec3 eye,forward,right,up,fogColour,center,halfSize,wind;
uniform float clock,waterY,reflectedView,shape,density,edge,noiseSize,turbulence,hollow,stepCount;
out vec4 finalColor;

vec3 localVector(vec3 p){return vec3(rotation.x*p.x+rotation.y*p.z,p.y,-rotation.y*p.x+rotation.x*p.z);}
vec3 fieldNoise(vec3 p){
    // Periodic 32^3 lattice. XY gutters and explicit Z interpolation prevent
    // seams between slices; Hermite interpolation keeps flowing lobes smooth.
    p=mod(p,32.);vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    vec2 xy=cell.xy+f.xy+1.5;
    float a=cell.z,b=mod(a+1.,32.);
    vec2 uv0=(vec2(mod(a,8.),floor(a/8.))*34.+xy)/vec2(272.,136.);
    vec2 uv1=(vec2(mod(b,8.),floor(b/8.))*34.+xy)/vec2(272.,136.);
    return mix(texture(noiseMap,uv0).rgb,texture(noiseMap,uv1).rgb,f.z);
}
bool intersectBox(vec3 origin,vec3 ray,out float nearT,out float farT){
    nearT=0.;farT=1.e20;
    for(int axis=0;axis<3;axis++){
        if(abs(ray[axis])<.000001){if(abs(origin[axis])>halfSize[axis])return false;}
        else{
            float a=(-halfSize[axis]-origin[axis])/ray[axis];
            float b=(halfSize[axis]-origin[axis])/ray[axis];
            nearT=max(nearT,min(a,b));farT=min(farT,max(a,b));
        }
    }
    return farT>nearT;
}
float envelope(vec3 p){
    vec3 q=abs(localVector(p-center)/halfSize);
    float d=mix(max(q.x,max(q.y,q.z)),length(q),shape);
    float t=clamp((1.-d)/edge,0.,1.);
    float outer=t*t*t*(10.+t*(-15.+6.*t));
    t=clamp((d-hollow)/min(edge,.25),0.,1.);
    float inner=hollow>0.?t*t*t*(10.+t*(-15.+6.*t)):1.;
    return outer*inner;
}
void main(){
    vec2 uv=gl_FragCoord.xy/resolution,ndc=uv*2.-1.;
    vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float nearT,farT;
    if(!intersectBox(localVector(eye-center),localVector(ray),nearT,farT)){finalColor=vec4(0.);return;}
    float raw=texture(depthMap,uv).r;
    float distance=2.*clip.x*clip.y/(clip.y+clip.x-(raw*2.-1.)*(clip.y-clip.x));
    distance/=max(.001,dot(ray,forward));
    // Reflection geometry is already clipped at the water. Integrate the
    // same canonical fog only above that plane, using this endpoint's level.
    if(reflectedView>.5){
        if(abs(ray.y)<.00001){if(eye.y<waterY)farT=nearT;}
        else if(ray.y>0.)nearT=max(nearT,(waterY-eye.y)/ray.y);
        else farT=min(farT,(waterY-eye.y)/ray.y);
    }
    if(farT<=nearT||distance<=nearT){finalColor=vec4(0.);return;}
    // Anchor sample spacing to the volume, not the hidden geometry. Changing
    // the world behind a bank must not rearrange its noise at the handoff.
    float count=min(stepCount,max(8.,ceil((farT-nearT)/max(.10,noiseSize*.15))));
    float ds=(farT-nearT)/count;
    farT=min(farT,distance);
    float jitter=.22+.56*fract(52.9829189*fract(dot(floor(gl_FragCoord.xy),vec2(.06711056,.00583715))));
    float transmission=1.;vec3 scatter=vec3(0.);
    for(int i=0;i<64;i++){
        if(float(i)>=count)break;
        float lo=nearT+float(i)*ds,hi=min(farT,lo+ds);
        if(hi<=lo)break;
        vec3 p=eye+ray*(lo+jitter*(hi-lo));
        float bounds=envelope(p);
        if(bounds<.0001)continue;
        vec3 q=(p-wind*clock)/noiseSize;
        vec3 broad=fieldNoise(q);
        vec3 eddies=fieldNoise(q*2.13+(broad-.5)*.75+vec3(11.,3.,17.)+
                              vec3(-wind.z,.035,wind.x)*clock*.32/noiseSize);
        float cloud=smoothstep(.16,.84,broad.r*.73+eddies.g*.27);
        float sigma=density*bounds*mix(1.,.10+1.7*cloud,turbulence);
        float shade=fieldNoise(q+vec3(-.45,.82,.30)).r;
        float light=clamp(.52+(broad.r-shade)*1.75+(eddies.b-.5)*.22,0.,1.);
        // Coarse painted lighting, continuous extinction: no opacity bands.
        light=mix(light,floor(light*5.+.5)/5.,.55);
        vec3 colour=fogColour*(.52+.91*light);
        float alpha=1.-exp(-sigma*(hi-lo));
        scatter+=transmission*alpha*colour;
        transmission*=1.-alpha;
        if(transmission<.008)break;
    }
    finalColor=vec4(scatter,1.-transmission);
}
