#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
uniform sampler2D depthMap;
uniform vec3 eye,forward,right,up,lens,fogColour;
uniform vec2 clip;
uniform vec4 worldFrame;
uniform vec3 carFrame;
uniform float dusk,headlights,clock,enabled;
out vec4 finalColor;
float hash(vec3 p) { return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453); }
float noise(vec3 p) {
    vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
float beam(vec3 p,float side) {
    vec3 v=p-vec3(side*.615,.701,-2.245);
    float len=length(v);
    float cone=smoothstep(.963,.995,dot(v/max(.001,len),normalize(vec3(0,-.025,-1))));
    return cone*(1.-smoothstep(16.,39.,len))*min(1.,9./max(1.,len));
}
void main() {
    vec3 scene=texture(texture0,fragTexCoord).rgb;
    if(enabled<.5) {finalColor=vec4(scene,1);return;}
    vec2 ndc=fragTexCoord*2.-1.;
    vec3 offset=right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x;
    vec3 origin=eye,ray=normalize(forward+offset);
    float depth=texture(depthMap,fragTexCoord).r;
    float distance=2.*clip.x*clip.y/(clip.y+clip.x-(depth*2.-1.)*(clip.y-clip.x));
    if(lens.z>.5) {origin+=offset;ray=forward;distance=mix(clip.x,clip.y,depth);}
    else distance/=max(.01,dot(ray,forward));
    distance=min(distance,650.);
    float transmission=1.;vec3 scattering=vec3(0);
    // Quadratic steps retain resolution near the headlights while covering the lake.
    const int STEPS=56;
    float jitter=hash(vec3(floor(gl_FragCoord.xy),0));
    for(int i=0;i<STEPS;i++) {
        float a=float(i)/float(STEPS),b=float(i+1)/float(STEPS);
        float lengthStep=(b*b-a*a)*distance;
        float t=mix(a*a,b*b,.3+.4*jitter)*distance;
        vec3 p=origin+ray*t;
        vec3 car=vec3(p.x,(p.y-carFrame.x)*carFrame.y+p.z*carFrame.z,-(p.y-carFrame.x)*carFrame.z+p.z*carFrame.y);
        // No weather inside the cabin; this also covers exterior close portraits.
        if(abs(car.x)<.89 && car.y>.10 && car.y<1.56 && car.z>-1.35 && car.z<1.5)continue;
        vec3 field=vec3(p.x*worldFrame.z-p.z*worldFrame.w+worldFrame.x,
                        p.y,p.x*worldFrame.w+p.z*worldFrame.z-worldFrame.y);
        float n=noise(field*vec3(.052,.14,.044)+vec3(clock*.026,0,clock*.010));
        float low=exp(-max(0.,p.y+1.35)*.18);
        float density=.0024*exp(-max(0.,p.y-18.)*.035)+.014*low*(.28+1.4*smoothstep(.26,.77,n));
        density+=.008*exp(-pow((p.y-9.-4.*sin(field.z*.008))/9.,2.))*n;
        float coast=22.*sin(-field.z/90.)+11.*sin(-field.z/43.+.5);
        float lake=smoothstep(6.,21.,field.x-coast);
        vec3 rolling=field*vec3(.044,.34,.035)+vec3(clock*.072,-clock*.06,clock*.039);
        float billow=noise(rolling)+.32*noise(rolling*2.2+vec3(0,clock*.06,0));
        float rollHeight=-.45+2.9*noise(vec3(field.x*.032+clock*.024,0,field.z*.038-clock*.018));
        rollHeight+=.80*sin(field.z*.068+field.x*.043+clock*.23);
        float bank=exp(-pow((p.y-rollHeight)/1.18,2.));
        float lakeMist=lake*.26*bank*smoothstep(.60,.98,billow);
        density+=lakeMist;
        float stepT=exp(-density*lengthStep);
        vec3 illumination=fogColour*(.84+.16*n);
        illumination+=vec3(.075,.083,.070)*lake*(1.-dusk)*smoothstep(.1,2.5,p.y);
        // Stronger when looking toward the lamps; restrained backscatter from
        // the driver's seat keeps the road and temple visible through the glass.
        vec3 incoming=normalize(car-vec3(0,.701,-2.245));
        vec3 carRay=vec3(ray.x,ray.y*carFrame.y+ray.z*carFrame.z,-ray.y*carFrame.z+ray.z*carFrame.y);
        float phase=.18+.82*pow(.5+.5*dot(incoming,-carRay),3.);
        illumination+=vec3(1.,.86,.57)*(beam(car,-1.)+beam(car,1.))*headlights*1.8*phase;
        scattering+=transmission*(1.-stepT)*illumination;
        transmission*=stepT;
        if(transmission<.015)break;
    }
    finalColor=vec4(scene*transmission+scattering,1.);
}
