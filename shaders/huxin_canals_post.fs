#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0,depthMap,buildingCoverage;
uniform vec2 resolution;
uniform vec4 coverageBounds;
uniform float veil,time,arrival,clearing,retreatRadius,returning,crest,reflectedView,voidWorld,waterY;
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
    vec3 flow=p*vec3(.14,.20,.14)+vec3(time*.010,-time*.013,time*.008);
    vec3 warp=vec3(noise(flow*.57+17.),noise(flow*.57+43.),noise(flow*.57-11.))-.5;
    flow+=warp*1.1;
    vec3 turned=vec3(flow.z*.8-flow.y*.6,flow.x*.8+flow.y*.48+flow.z*.36,
                     -flow.x*.6+flow.y*.64+flow.z*.48);
    // Two broad octaves give the banks a coarse, painted grain. Small
    // filaments supply depth without smoothing every lobe into milky smoke.
    return noise(flow)*.72+noise(turned*2.03+vec3(17.13,9.71,time*.008))*.28;
}
vec3 driftSpace(vec3 p){
    // Advection bends in all three dimensions. Similar spatial scales keep
    // the eddies round in depth instead of stretching them into texture bands.
    vec3 q=p+vec3(-time*.075,0.,time*.052);
    q.x+=2.2*sin(p.z*.12+p.y*.18-time*.041);
    q.z+=1.7*sin(p.x*.15-p.y*.21+time*.033);
    q.y+=.65*sin(p.x*.17+p.z*.13-time*.052)
          +.24*sin(p.z*.39-p.x*.23+time*.071);
    return q;
}
float wisps(vec3 q){
    // Intersections of two warped 3D level sets form branching filaments,
    // with finite thickness in BOTH transverse directions, not flat ribbons.
    vec3 v=q*vec3(.29,.34,.29);
    float a=noise(v+vec3(11.,4.,29.))-.50;
    vec3 rotated=vec3(v.z*.8-v.y*.6,v.x*.8+v.y*.48+v.z*.36,
                      -v.x*.6+v.y*.64+v.z*.48);
    float b=noise(rotated*1.17+vec3(37.,17.,3.))-.51;
    return exp(-(a*a+b*b)*112.);
}
float buildingBank(vec3 p,vec3 drift){
    // A coarse, feathered map of the actual house footprints places the
    // heaviest banks in the streets, leaving irregular gaps over open water.
    // Bend the map through height as well as horizontally: this is a volume,
    // not a vertical extrusion of the walls or an annulus around the pavilion.
    vec2 bend=vec2(noise(drift*.12+19.),noise(drift.yzx*.12-7.))-.5;
    vec2 xz=p.xz+bend*4.5;
    vec2 uv=(xz-coverageBounds.xy)/(coverageBounds.zw-coverageBounds.xy);
    float mapped=texture(buildingCoverage,clamp(uv,vec2(.001),vec2(.999))).r;
    return mix(mapped,1.,smoothstep(76.,94.,max(abs(xz.x),abs(xz.y))));
}
float band(float v,float steps){
    // Antialias the edges of the contour, not the broad painted tonal bands.
    float x=clamp(v,0.,1.)*steps;
    return (floor(x)+smoothstep(.46,.54,fract(x)))/steps;
}
vec3 rollingMist(vec3 scene,vec2 uv){
    if(veil<.001&&voidWorld<.001)return scene;
    vec2 ndc=uv*2.-1.;vec3 ray=normalize(forward+right*ndc.x*lens.x*lens.y+up*ndc.y*lens.x);
    float depth=texture(depthMap,uv).r;
    float distance=2.*clip.x*clip.y/(clip.y+clip.x-(depth*2.-1.)*(clip.y-clip.x));
    distance=min(240.,distance/max(.01,dot(ray,forward)));
    // Reflected geometry was drawn upside down. Unfold its view ray into the
    // actual world so the water sees the very same moving cloud, not a copy
    // below the lake. Only integrate beyond the water: the main pass already
    // accounts for the real camera-to-water segment.
    vec3 origin=eye;
    if(reflectedView>.5){origin.y=2.*waterY-origin.y;ray.y=-ray.y;}
    // Restrict integration to the cloud's vertical bounds. Quadratic steps
    // preserve near detail without wasting samples above the bank or below water.
    float start=0.,finish=distance;
    if(abs(ray.y)>.0001){
        float bottom=reflectedView>.5?waterY:waterY-.12;
        float lo=(bottom-origin.y)/ray.y,hi=(16.-origin.y)/ray.y;
        start=max(0.,min(lo,hi));finish=min(distance,max(lo,hi));
    }
    if(finish<=start)return scene;
    float transmission=1.;vec3 scatter=vec3(0.);
    const int STEPS=96;
    for(int i=0;i<STEPS;i++){
        // Sample locations cannot depend on the geometry behind the cloud:
        // otherwise its silhouette changes the quadrature and prints into fog.
        float a=float(i),b=float(i+1),qa=max(0.,a-40.),qb=max(0.,b-40.);
        // The soft foreground needs thirty-centimetre samples; the old sharp
        // deck skirt needed much finer steps. Keep fixed world intervals so
        // hidden geometry cannot change the fog pattern during the dissolve.
        float lo=start+min(a,40.)*.30+qa*.45+qa*qa*.065;
        float fullHi=start+min(b,40.)*.30+qb*.45+qb*qb*.065;
        float hi=min(finish,fullHi);
        if(lo>=finish)break;
        float stepLength=hi-lo;vec3 p=origin+ray*(lo+fullHi)*.5;
        float r=length(p.xz),shore=shoreRadius(atan(p.z,p.x));
        float frontRadius=max(mix(shore-6.,mix(4.65,10.50,crest),arrival),retreatRadius);
        // At the crescendo the far bank fills outward as well. Reflected rays
        // can meet the water beyond the former shore; their remaining light
        // path still needs fog, including the distant replacement rooftops.
        float outerReach=shore+20.+390.*crest;
        if(voidWorld<.001&&(r<frontRadius-18.||r>outerReach))continue;
        float cloud=billow(p);
        vec3 drift=driftSpace(p);
        float filament=wisps(drift);
        float retreating=smoothstep(0.,.16,clearing);
        // Different layers and channels release at different times. The
        // retreat travels through a warped volume, with no circular outline.
        float bank=noise(drift*vec3(.083,.12,.073));
        float folds=noise(drift.zxy*vec3(.22,.20,.25)+17.);
        float stretch=1.+retreating*(.27*sin(atan(p.z,p.x)*3.+.8)+.19*cos(atan(p.z,p.x)*5.-.6));
        float travel=r*stretch;
        float foldsWidth=mix(4.,min(58.,8.+retreatRadius*.35),retreating);
        float lobes=(cloud-.5)*mix(15.,7.5,arrival);
        lobes+=crest*((bank-.5)*5.0+(folds-.5)*2.0);
        lobes+=retreating*((bank-.5)*foldsWidth*2.2+(folds-.5)*12.+p.y*1.1);
        frontRadius+=max(0.,p.y)*.8*(1.-smoothstep(.78,1.,arrival));
        float edge=mix(mix(12.,4.5,arrival),min(25.,7.+retreatRadius*.09),retreating);
        float front=smoothstep(-edge,edge,travel-frontRadius+lobes);
        // Frayed ribbons remain behind the bulk of the cloud. Their crests
        // drift sideways across successive silhouettes, instead of dissolving.
        float tailDistance=min(42.,8.+retreatRadius*.28);
        float wake=smoothstep(-tailDistance-edge,-tailDistance*.35,travel-frontRadius+lobes)
                  *(1.-smoothstep(-edge*.35,edge*1.1,travel-frontRadius+lobes));
        // There is no platform-shaped wall of fog. The quiet centre feathers
        // into asymmetric, height-varying lobes over several metres. Fine
        // wisps may cross the outer paving while the actor remains readable.
        vec2 quietXZ=p.xz*vec2(.94,1.08)+vec2(.45,-.25);
        float quietDistance=length(quietXZ)+(bank-.5)*3.6+(folds-.5)*1.35
                           +.42*sin(p.y*.8+p.x*.31);
        float pocket=smoothstep(5.8,10.8,quietDistance);
        float top=mix(2.5,11.,arrival)+(cloud-.5)*5.;
        float height=(1.-smoothstep(top-3.,top+2.,p.y))*exp(-max(0.,p.y)*.055);
        float outer=1.-smoothstep(outerReach-15.,outerReach,r);
        float shape=smoothstep(.23,.73,cloud);
        shape=mix(shape,band(shape,5.),.32);
        // The same low, drifting field as the scene's everyday mist, enriched
        // with slowly turning 3D billows rather than a second bright cloud layer.
        float flow=.55+.22*sin(p.x*.065+p.z*.073-time*.07)+.17*sin(p.z*.16-p.x*.09+time*.035);
        // Keep the distant bank dense. Its irregular inner edge travels out
        // through the streets; there is no screen-wide opacity/erosion fade.
        float porous=pow(shape,1.35)*(.38+.62*filament);
        float body=mix(mix(.24,1.,shape),.025+1.05*porous,crest);
        float density=front*pocket*height*outer*veil*body*(.72+flow*.42);
        // At the outbound midpoint the bank thickens around the building.
        // Foreground mist stays navigable from the ordinary fixed cameras.
        float pavilionBank=(1.-smoothstep(18.,34.,r))*pow(arrival,4.);
        density*=mix(.035+.10*pow(arrival,3.)+.30*crest,.04+.16*pow(arrival,3.)+.85*pavilionBank,returning);
        // The denser overlapping bank sits BEHIND the translucent fringe.
        // Its coverage comes from optical depth, not an opaque surface mask.
        float backing=smoothstep(6.8,11.2,quietDistance)
                     *smoothstep(-6.,4.,travel-frontRadius+lobes);
        float houses=buildingBank(p,drift);
        density+=backing*height*outer*veil*crest*(.10+houses*(.8+1.4*cloud));
        // A separate, porous foreground travels ahead of the main bank. These
        // finite 3D curls cross the outer posts and paving at different depths.
        float fringe=smoothstep(-12.,-2.,travel-frontRadius+lobes)
                    *(1.-smoothstep(1.,8.,travel-frontRadius+lobes));
        float curl=smoothstep(.30,.65,cloud*.58+folds*.42)*(.18+.82*filament);
        float fringePocket=smoothstep(3.0,7.2,quietDistance);
        float skirtDensity=fringe*fringePocket*height*outer*veil*crest*curl*.20;
        density+=skirtDensity;
        // A trace of low mist crosses the water and stone edges. The worlds
        // dissolve gradually, so this no longer has to hide the water datum
        // behind an opaque skirt right beside the player.
        float lowTop=1.10+(cloud-.5)*.55+(folds-.5)*.25;
        float underDeck=(1.-smoothstep(.05,lowTop,p.y))*smoothstep(5.,9.,quietDistance);
        float lowFront=smoothstep(-8.,1.,travel-frontRadius+lobes*.35);
        density+=underDeck*lowFront*outer*veil*crest*(.06+.16*filament);
        density+=wake*retreating*pocket*height*outer*veil*filament*.16;
        // Low, persistent banks over the canals outlive the transition cloud.
        density+=voidWorld*(1.-front*veil)*(.0018+.024*exp(-max(0.,p.y-waterY)*.72))*filament;
        float thinScatter=clamp(skirtDensity/max(.001,density),0.,1.);
        // Keep the immediate space around the walking actor readable.
        density*=smoothstep(1.05,2.10,length((p-playerCenter)*vec3(1.,.72,1.)));
        // Use the real camera here in both optical paths, so a reflection does
        // not carve a second, contradictory hole in the same cloud.
        density*=smoothstep(.75,1.65,length(p-eye));
        if(density<.0001)continue;
        // A sample towards the dim sky gives each 3D lobe a lit edge and a
        // shaded body. Smaller eddies add soft detail instead of bright lines.
        float shaded=billow(p+vec3(-1.1,1.8,.65));
        float detail=noise(drift*vec3(.45,.48,.44)+vec3(7.,21.,13.));
        float light=clamp(.50+(cloud-shaded)*2.8+(folds-.5)*.85+(detail-.5)*.12,0.,1.);
        light=mix(light,band(light,5.),.65);
        vec3 colour=fogColour*(.63+.72*light+thinScatter*.12);
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
