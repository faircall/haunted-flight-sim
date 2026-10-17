#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0,depthMap;
uniform vec2 resolution;
uniform float veil,time,arrival,clearing,returning,crest,travelling,reflectedView;
uniform vec3 eye,forward,right,up,playerCenter,fogColour;
uniform vec2 lens,clip;
out vec4 finalColor;

// The 2D illuminated fog's warped, evolving noise and stepped illumination,
// sampled in world space here so its lobes have depth, parallax and occlusion.
float hash(vec3 p){p=fract(p*vec3(.1031,.1030,.0973));p+=dot(p,p.yxz+33.33);return fract((p.x+p.y)*p.z);}
float noise(vec3 p){
    vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
float shoreRadius(float angle){
    float d=atan(sin(angle-1.5707963),cos(angle-1.5707963));float south=exp(-pow(d/.54,2.));
    float entry=atan(77.,-12.);float delta=atan(sin(angle-entry),cos(angle-entry));
    return 126.-51.*south+(1.-south)*(10.*sin(angle*3.+.2)+6.*sin(angle*7.-.6))-3.*exp(-pow(delta/.14,2.));
}
float billow(vec3 p){
    vec3 flow=p*vec3(.115,.21,.115)+vec3(time*.010,-time*.013,time*.008);
    vec3 warp=vec3(noise(flow*.57+17.),noise(flow*.57+43.),noise(flow*.57-11.))-.5;
    flow+=warp*1.4;
    return noise(flow)*.72+noise(flow*2.03+vec3(17.13,9.71,time*.008))*.28;
}
float band(float v,float steps){
    // Antialias the edges of the contour, not the broad painted tonal bands.
    float x=clamp(v,0.,1.)*steps;
    return (floor(x)+smoothstep(.46,.54,fract(x)))/steps;
}
vec3 rollingMist(vec3 scene,vec2 uv){
    if(veil<.001)return scene;
    vec2 ndc=uv*2.-1.;vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float depth=texture(depthMap,uv).r;
    float distance=2.*clip.x*clip.y/(clip.y+clip.x-(depth*2.-1.)*(clip.y-clip.x));
    distance=min(240.,distance/max(.01,dot(ray,forward)));
    // Reflected geometry was drawn upside down. Unfold its view ray into the
    // actual world so the water sees the very same moving cloud, not a copy
    // below the lake. Only integrate beyond the water: the main pass already
    // accounts for the real camera-to-water segment.
    vec3 origin=eye;
    if(reflectedView>.5){origin.y=-origin.y;ray.y=-ray.y;}
    // Restrict integration to the cloud's vertical bounds. Quadratic steps
    // preserve near detail without wasting samples above the bank or below water.
    float start=0.,finish=distance;
    if(abs(ray.y)>.0001){
        float bottom=reflectedView>.5?0.:-.12;
        float lo=(bottom-origin.y)/ray.y,hi=(16.-origin.y)/ray.y;
        start=max(0.,min(lo,hi));finish=min(distance,max(lo,hi));
    }
    if(finish<=start)return scene;
    float transmission=1.;vec3 scatter=vec3(0.);
    const int STEPS=88;
    for(int i=0;i<STEPS;i++){
        // Sample locations cannot depend on the geometry behind the cloud:
        // otherwise its silhouette changes the quadrature and prints into fog.
        float a=float(i),b=float(i+1);
        float lo=start+a*.085+a*a*.033,hi=min(finish,start+b*.085+b*b*.033);
        if(lo>=finish)break;
        float stepLength=hi-lo;vec3 p=origin+ray*(lo+hi)*.5;
        float r=length(p.xz),shore=shoreRadius(atan(p.z,p.x));
        float frontRadius=mix(shore-6.,4.65,arrival);
        if(r<frontRadius-18.||r>shore+20.)continue;
        float cloud=billow(p);
        float lobes=(cloud-.5)*mix(15.,3.6,arrival);
        frontRadius+=max(0.,p.y)*.8*(1.-smoothstep(.78,1.,arrival));
        float edge=mix(12.,2.6,arrival);
        float front=smoothstep(-edge,edge,r-frontRadius+lobes);
        float pocket=smoothstep(3.95,4.5,r);
        float top=mix(2.5,11.,arrival)+(cloud-.5)*5.;
        float height=(1.-smoothstep(top-3.,top+2.,p.y))*exp(-max(0.,p.y)*.055);
        float outer=1.-smoothstep(shore+5.,shore+20.,r);
        // Clearing eats holes in the bank, rather than reversing its journey.
        float erosion=smoothstep(clearing*.95-.08,clearing*.95+.20,cloud);
        float shape=smoothstep(.20,.72,cloud);
        // The same low, drifting field as the scene's everyday mist, enriched
        // with slowly turning 3D billows rather than a second bright cloud layer.
        float flow=.55+.22*sin(p.x*.065+p.z*.073-time*.07)+.17*sin(p.z*.16-p.x*.09+time*.035);
        float density=front*pocket*height*outer*erosion*veil*mix(.24,1.,shape)*(.72+flow*.42);
        // At the outbound midpoint the bank thickens around the building.
        // Foreground mist stays navigable from the ordinary fixed cameras.
        float pavilionBank=(1.-smoothstep(18.,34.,r))*pow(arrival,4.);
        density*=mix(.035+.26*pow(arrival,3.)+5.8*crest,.04+.16*pow(arrival,3.)+.85*pavilionBank,returning);
        // Keep the immediate space around the walking actor readable.
        if(travelling>.5)density*=smoothstep(1.25,2.2,length((p-playerCenter)*vec3(1.,.8,1.)));
        if(density<.0001)continue;
        float shaded=noise(p*vec3(.115,.21,.115)+vec3(.7,1.3,-.5)+vec3(0,-time*.013,0));
        float light=clamp(.5+(cloud-shaded)*.9,0.,1.);
        light=mix(light,band(light,8.),.24);
        vec3 colour=fogColour*(.82+.36*light);
        float stepT=exp(-density*stepLength);
        scatter+=transmission*(1.-stepT)*colour;transmission*=stepT;
        if(transmission<.001)break;
    }
    float alpha=1.-transmission;
    vec3 colour=scatter/max(.0001,alpha);
    // Continuous transmission prevents six-percent opacity jumps as the player
    // advances. Only the low-contrast illumination carries painted tonal bands.
    return mix(scene,colour,alpha);
}
void main(){
    vec2 uv=fragTexCoord;vec3 c=texture(texture0,uv).rgb,bloom=vec3(0.);
    // Reflections feed the water material in scene colour space. Bloom, gamma
    // and vignette are applied once, after the complete scene is assembled.
    if(reflectedView>.5){finalColor=vec4(rollingMist(c,uv),1.);return;}
    for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++)bloom+=max(texture(texture0,uv+vec2(x,y)*2./resolution).rgb-vec3(.74),vec3(0.))/25.;
    c=rollingMist(c,uv);
    c=pow(max(c+bloom*.24,vec3(0.)),vec3(.94))*(1.-.095*dot(uv*2.-1.,uv*2.-1.));
    finalColor=vec4(c,1.);
}
