#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform sampler2D waterMask;
uniform sampler2D sceneTexture;
uniform sampler2D rainExposureTexture;
uniform sampler2D lightTexture;
uniform float lightResponse;
uniform vec3 skyColor;
uniform float rainAmount;
uniform float rainDistortion;
uniform vec2 resolution;
uniform vec2 mapSize;
uniform vec2 cameraPosition;
uniform vec3 surfaceColor;
uniform vec3 rippleColor;
uniform float rippleSpacing;
uniform float rippleDensity;
uniform float rippleWidth;
uniform float rippleSpeed;
uniform float rippleSpeedVariation;
uniform vec2 rippleDirection;
uniform float shoreWidth;
uniform float shoreSpeed;
uniform float shoreLap;
uniform float shoreDistanceRange;
uniform float time;
uniform float reflectionStrength;
uniform float rippleStrength;
uniform float reflectionSway;
uniform float reflectionPass;
out vec4 finalColor;

float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
}

float rippleLayer(vec2 p,float layer,float rate,float spacing) {
    p.y-=time*rippleSpeed*5.*rate+layer*17.31;
    vec2 cell=floor(p/vec2(40.,spacing));
    vec2 key=cell+vec2(layer*37.,layer*71.);
    float seed=hash(key);
    if(seed>=rippleDensity) return 0.;
    // Isolated glimmers, with varied positions and lifetimes. Most of the
    // surface is quiet; each stroke grows briefly, then shrinks away again.
    float center=(cell.x+.2+.6*hash(key+17.))*40.;
    float crest=(cell.y+.35+.3*hash(key+29.))*spacing;
    float age=fract(time*rippleSpeed*.18*mix(.8,1.2,seed)+hash(key+93.));
    float life=smoothstep(0.,.10,age)*(1.-smoothstep(.22,.36,age));
    float halfLength=mix(3.,8.,hash(key+41.))*life;
    float thickness=min(rippleWidth,spacing*.45);
    // Coverage changes in whole pixels, never intermediate palette colours.
    return step(.05,life)*step(abs(p.x-center),halfLength)*
           step(-thickness*.5,p.y-crest)*(1.-step(thickness*.5,p.y-crest));
}

float surfaceRipple(vec2 world) {
    if(rippleDensity<=0.) return 0.;
    vec2 p=vec2(dot(world,vec2(rippleDirection.y,-rippleDirection.x)),dot(world,rippleDirection));
    // Sparse glimmers share a direction with different forward speeds. Their
    // independent life cycles avoid permanent stripes or synchronized pulses.
    float a=rippleLayer(p,0.,1.-rippleSpeedVariation,rippleSpacing);
    float b=rippleLayer(p,1.,1.,rippleSpacing*1.31);
    float c=rippleLayer(p,2.,1.+rippleSpeedVariation,rippleSpacing*1.73);
    return max(a,max(b,c));
}

vec3 shoreCycle(vec2 world) {
    float cycle=time*shoreSpeed*.20+noise(world*.019)*.16;
    float age=fract(cycle);
    float reach=shoreLap*(.75+.25*noise(world*.09+vec2(31.,7.)));
    float wash=smoothstep(.30,.60,age)*(1.-smoothstep(.64,1.,age));
    return vec3(age,-reach*wash,reach);
}

float shoreRipple(vec2 world,float distanceToLand,vec3 cycle) {
    if(shoreWidth<=0. || distanceToLand>shoreWidth+3.) return 0.;
    // A wave is born offshore, spreads on arrival, then breaks into shrinking
    // patches. Its foam stays at the bank and dissolves as the water drains;
    // no bright line is translated back out into the lake.
    float age=cycle.x;
    float life=smoothstep(.02,.20,age)*(1.-smoothstep(.60,.95,age));
    float front=mix(shoreWidth,-cycle.z,smoothstep(.04,.60,age));
    float patch=noise(world*.22+vec2(7.,23.));
    float scallop=(noise(world*.10+vec2(19.,3.))-.5)*2.;
    float thickness=mix(.4,3.8,smoothstep(.04,.52,age));
    float body=1.-step(thickness,abs(distanceToLand-front-scallop));
    return body*step(mix(1.,.22,life),patch);
}

float waterPattern(vec2 world,float distanceToLand,vec3 cycle) {
    float openWater=surfaceRipple(world)*step(shoreWidth*.65,distanceToLand);
    return max(openWater,shoreRipple(world,distanceToLand,cycle));
}

vec3 rainDimple(vec2 world,float layer,float amount) {
    // Stationary impacts disturb a tiny surface normal, rather than drawing
    // expanding outlines. Two staggered fields avoid a repeated splash grid.
    vec2 p=world+vec2(layer*73.1,layer*47.7);
    vec2 size=vec2(22.,14.)+layer*vec2(5.,3.);
    vec2 cell=floor(p/size);
    float seed=hash(cell+layer*31.);
    float clock=time*(1.1+seed*.5)+seed*71.;
    float serial=floor(clock),age=fract(clock);
    vec2 key=cell+serial*vec2(17.,53.)+layer*11.;
    if(hash(key+9.)>amount*.88 || age>.92)return vec3(0.);
    vec2 center=floor(cell*size+vec2(6.,3.)+
        vec2(hash(key+7.),hash(key+19.))*(size-vec2(12.,6.)))+.5;
    vec2 delta=p-center;
    vec2 q=delta*vec2(1.,2.2);float radius=length(q);
    float life=smoothstep(.02,.12,age)*(1.-smoothstep(.35,.85,age));
    float wave=radius-(.6+age*6.5);
    float slope=sin(wave*2.4)*exp(-wave*wave*.65)*life*(1.-smoothstep(3.5,5.5,radius));
    vec2 normal=q/max(.5,radius)*slope;
    // Only the short initial contact catches sky light: one or two native
    // pixels in the existing ripple colour, with no bright ring or gradient.
    float glint=step(.025,age)*(1.-step(.09,age))*
        step(abs(delta.x),.9)*step(abs(delta.y),.5);
    return vec3(normal,glint);
}

void main() {
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=pixel+cameraPosition;
    vec2 mapUv=world/mapSize;
    if(any(lessThan(mapUv,vec2(0))) || any(greaterThanEqual(mapUv,vec2(1)))) discard;
    vec4 mask=texture(waterMask,mapUv);
    if(mask.b<.5) discard;
    float shoreDistance=(mask.g*255.-128.)*(shoreDistanceRange/127.);
    vec3 cycle=vec3(0.);
    if(shoreWidth>0.) {
        if(shoreDistance< -shoreLap) discard;
        if(shoreDistance<shoreWidth+3.) cycle=shoreCycle(world);
        // The water silhouette itself washes over the bank, in native pixels.
        // Both render passes use this same boundary, including reflections.
        if(shoreDistance<cycle.y) discard;
    } else if(mask.r<.5) discard;

    vec3 impact=vec3(0.);
    if(rainAmount>0.) {
        float exposure=texture(rainExposureTexture,mapUv).r;
        if(exposure>.0 && shoreDistance>2.)
            impact=rainDimple(world,0.,rainAmount*exposure)+rainDimple(world,1.,rainAmount*exposure);
    }
    float pattern=max(waterPattern(world,shoreDistance,cycle),min(1.,impact.z));
    vec3 base=mix(surfaceColor,rippleColor,pattern);
    if(lightResponse>0.) {
        // Reuse the shadowed world light field (including the actual flashlight
        // cone). Sky colour already lives in the two authored water colours.
        vec3 light=max(vec3(0.),texelFetch(lightTexture,ivec2(gl_FragCoord.xy),0).rgb-skyColor*mask.a);
        float strength=max(light.r,max(light.g,light.b));
        float bands=(step(.10,strength*lightResponse)+step(.30,strength*lightResponse)+step(.60,strength*lightResponse))/3.;
        // A small stepped palette, no smooth colour gradients or filtering.
        vec3 hue=floor(light/max(.001,strength)*2.+.5)/2.;
        base+=hue*bands*mix(.055,.14,pattern);
    }

    if(reflectionPass<.5) {
        // Unlit water keeps its two colours; direct light adds three bands.
        finalColor=vec4(base,1.);
        return;
    }

    vec2 uv=gl_FragCoord.xy/resolution;
    vec4 scene=texture(sceneTexture,uv);
    float foreground=scene.a;
    if(foreground>.999) discard;

    // Reflection strength/colour remain independent, but the distortion field
    // travels with the same current as the surface wavelets.
    vec2 flow=world-rippleDirection*(time*rippleSpeed*5.);
    float swell=sin(flow.x*.033+flow.y*.061)+.45*sin(flow.x*.089-flow.y*.041);
    float grain=noise(flow*vec2(.11,.29));
    float ripple=sin(flow.y*.39+flow.x*.026+swell*.6);
    vec2 warp=round(vec2((swell*.85+sin(flow.x*.067-flow.y*.078)*.35)*reflectionSway,ripple*.32)*rippleStrength);
    // Move exact reflected texels within the authored rain displacement limit.
    // The disturbance primarily reads in lantern/temple reflections, not as
    // light-blue symbols painted across otherwise dark water.
    warp+=round(clamp(impact.xy*2.2*rainDistortion,vec2(-rainDistortion),vec2(rainDistortion)));
    ivec2 samplePixel=ivec2(vec2(pixel.x,resolution.y-pixel.y)+warp);
    if(any(lessThan(samplePixel,ivec2(0))) || any(greaterThanEqual(samplePixel,ivec2(resolution)))) discard;
    vec4 reflected=texelFetch(texture0,samplePixel,0);
    // Strength controls gaps, never brightness. Entire native pixels survive
    // or disappear in coherent ripple bands; no colour ramp or soft fire glow.
    float wave=clamp((ripple+grain*.65+1.)/2.65,0.,1.);
    if(reflectionStrength<=0. || wave<1.-clamp(reflectionStrength,0.,1.) || reflected.a<=0.) discard;
    // The scene already contains foreground over base water. Replace only the
    // exposed base contribution. Opaque reflected texels keep their exact RGB;
    // alpha blending is reserved for deliberately fading objects/foregrounds.
    finalColor=vec4(clamp(scene.rgb+(reflected.rgb-base*reflected.a)*(1.-foreground),0.,1.),1.);
}
