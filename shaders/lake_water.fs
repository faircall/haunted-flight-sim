#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform sampler2D waterMask;
uniform sampler2D sceneTexture;
uniform vec2 resolution;
uniform vec2 mapSize;
uniform vec2 cameraPosition;
uniform vec3 surfaceColor;
uniform vec3 rippleColor;
uniform float rippleSpacing;
uniform float rippleDensity;
uniform float time;
uniform float reflectionStrength;
uniform float rippleStrength;
uniform float reflectionPass;
out vec4 finalColor;

float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
}

float surfaceRipple(vec2 world) {
    // One native-pixel stroke, broken into varying lengths. The wave changes
    // placement only: its colour/opacity has no smooth or antialiased fringe.
    float band=floor(world.y/rippleSpacing);
    float phase=hash(vec2(band,19.))*6.283185;
    float bend=sin(world.x*.025-time*.48+phase);
    float crest=floor(band*rippleSpacing+rippleSpacing*(.5+.20*bend));
    float dash=noise(vec2(world.x*.045+time*.10,band*2.71));
    float stroke=1.-step(.5,abs(floor(world.y)-crest));
    return stroke*step(1.-rippleDensity,dash);
}

void main() {
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=pixel+cameraPosition;
    vec2 mapUv=world/mapSize;
    if(any(lessThan(mapUv,vec2(0))) || any(greaterThanEqual(mapUv,vec2(1)))) discard;
    if(texture(waterMask,mapUv).r<.5) discard;

    if(reflectionPass<.5) {
        // Exactly two RGB colours. Lights, reflections and their distortion do
        // not participate in the base surface's colour or ripple mask.
        finalColor=vec4(mix(surfaceColor,rippleColor,surfaceRipple(world)),1.);
        return;
    }

    vec2 uv=gl_FragCoord.xy/resolution;
    vec4 scene=texture(sceneTexture,uv);
    float foreground=scene.a;
    if(foreground>.999) discard;

    // Reflection treatment is independent from the two-colour surface.
    float swell=sin(world.x*.033+world.y*.061-time*.57)+.45*sin(world.x*.089-world.y*.041+time*.36);
    float grain=noise(world*vec2(.11,.29)+vec2(time*.028,0));
    float ripple=sin(world.y*.39+world.x*.026+swell*.6-time*.73);
    vec2 warp=round(vec2(swell*.85+sin(world.x*.067-world.y*.078+time*.62)*.35,ripple*.32)*rippleStrength);
    ivec2 samplePixel=ivec2(vec2(pixel.x,resolution.y-pixel.y)+warp);
    if(any(lessThan(samplePixel,ivec2(0))) || any(greaterThanEqual(samplePixel,ivec2(resolution)))) discard;
    vec4 reflected=texelFetch(texture0,samplePixel,0);
    // Strength controls gaps, never brightness. Entire native pixels survive
    // or disappear in coherent ripple bands; no colour ramp or soft fire glow.
    float wave=clamp((ripple+grain*.65+1.)/2.65,0.,1.);
    if(reflectionStrength<=0. || wave<1.-clamp(reflectionStrength,0.,1.) || reflected.a<=0.) discard;
    vec3 base=mix(surfaceColor,rippleColor,surfaceRipple(world));
    // The scene already contains foreground over base water. Replace only the
    // exposed base contribution. Opaque reflected texels keep their exact RGB;
    // alpha blending is reserved for deliberately fading objects/foregrounds.
    finalColor=vec4(clamp(scene.rgb+(reflected.rgb-base*reflected.a)*(1.-foreground),0.,1.),1.);
}
