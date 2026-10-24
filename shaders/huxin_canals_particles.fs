#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
in vec3 fogPosition;
uniform sampler2D texture0,depthMap;
uniform vec2 resolution,clip,nearFade;
uniform vec3 fogColour;
uniform float reflectionPass,waterY,targetedFog,flowTime;
// Displacement multiplier: 1.0 is the original animated-flow strength.
// On a 64px cloud tile, 1.5 permits up to 12px per-axis displacement before
// edge feathering/clamping. Flow speed and shading contrast are independent.
const float FLOW_STRENGTH=1.5;
out vec4 finalColor;
float linearDepth(float d){return 2.*clip.x*clip.y/(clip.y+clip.x-(d*2.-1.)*(clip.y-clip.x));}
vec2 flowHash(vec2 p){
    vec3 q=fract(vec3(p.xyx)*vec3(.1031,.1030,.0973));
    q+=dot(q,q.yzx+33.33);
    return fract((q.xx+q.yz)*q.zy);
}
vec2 flowNoise(vec2 p){
    vec2 cell=floor(p),f=fract(p);
    f=f*f*(3.-2.*f);
    return mix(mix(flowHash(cell),flowHash(cell+vec2(1.,0.)),f.x),
               mix(flowHash(cell+vec2(0.,1.)),flowHash(cell+vec2(1.,1.)),f.x),f.y);
}
void main(){
    vec4 texel=texture(texture0,fragTexCoord);
    vec3 p=fogPosition;
    if(reflectionPass>.5)p.y=2.*waterY-p.y;
    if(targetedFog>.5){
        // Two currents roll THROUGH the fragments at different scales and
        // directions. Use canonical world space so the reflected pass samples
        // the same field; no camera-space scrolling or whole-bank pulsing.
        vec2 field=vec2(p.x+.37*p.y,p.z+.21*p.y);
        vec2 broad=flowNoise(field*.48-vec2(.048,.016)*flowTime);
        vec2 detail=flowNoise(field*.83+vec2(.032,-.041)*flowTime+vec2(13.7,4.2));
        vec2 grid=vec2(4.,2.);
        vec2 cell=min(floor(fragTexCoord*grid),grid-1.);
        vec2 uv=fragTexCoord*grid-cell;
        vec2 edge=min(uv,1.-uv);
        float feather=smoothstep(0.,.12,min(edge.x,edge.y));
        vec2 warp=((broad-.5)*.18+(detail-.5)*.07)*feather*FLOW_STRENGTH;
        vec2 inset=.5*grid/vec2(textureSize(texture0,0));
        // Never sample another atlas cell or pull colour across its gutter.
        vec2 flowed=(cell+clamp(uv+warp,inset,1.-inset))/grid;
        vec4 rolling=texture(texture0,flowed);
        // Preserve most of the silhouette/dense core coverage. The visible
        // roll is primarily internal shading, with softer contour changes.
        texel.a=mix(texel.a,rolling.a,.35);
        texel.rgb=mix(texel.rgb,rolling.rgb,.90)*
                  (.80+.40*(broad.x*.65+detail.y*.35));
    }
    float opacity=(fragColor.a*65280.+fragColor.r*255.)/65535.;
    float a=texel.a*opacity;
    if(a<=0.)discard;
    // Broad, irregular feathering protects the small puzzle centre; there
    // is no moving player bubble and no hard circular fog boundary.
    vec2 q=p.xz*vec2(.96,1.04)+vec2(.35,-.25);
    float edge=length(q)+.52*sin(p.x*.49+p.z*.27)+.44*sin(p.z*.65-p.x*.16)+.18*sin(p.y*.7);
    // Low mist reaches a little further beneath the outer paving. Both water
    // datums must be hidden there, while the upper pocket stays airy/readable.
    float lowPocket=smoothstep(3.0,5.6,edge);
    float upperPocket=smoothstep(3.8,7.5,edge);
    // Targeted clouds are positioned around architecture, including its roof
    // and washing steps. They need no circular exclusion around the pavilion.
    // Retain the saved bank version's feathering for comparison playback.
    a*=mix(mix(lowPocket,upperPocket,smoothstep(.6,1.5,p.y)),1.,targetedFog);
    // Soft particles intersect timber, stairs, water and the actor without
    // rectangles or hard seams. Depth belongs to the opaque scene, never fog.
    float scene=linearDepth(texture(depthMap,gl_FragCoord.xy/resolution).r);
    float particle=linearDepth(gl_FragCoord.z);
    a*=smoothstep(0.,1.25,scene-particle);
    a*=smoothstep(nearFade.x,nearFade.y,particle);
    if(reflectionPass>.5)a*=smoothstep(waterY-.18,waterY+.18,p.y);
    // Coarse atlas tones stay visible through overlapping cards. Do not
    // quantize opacity: that would turn their soft edges into a hard curtain.
    vec3 colour=fogColour*(.40+1.10*texel.r);
    finalColor=vec4(colour,a);
}
