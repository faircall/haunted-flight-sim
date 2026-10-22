#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
in vec3 fogPosition;
uniform sampler2D texture0,depthMap;
uniform vec2 resolution,clip,nearFade;
uniform vec3 fogColour;
uniform float reflectionPass,waterY,targetedFog;
out vec4 finalColor;
float linearDepth(float d){return 2.*clip.x*clip.y/(clip.y+clip.x-(d*2.-1.)*(clip.y-clip.x));}
void main(){
    vec4 texel=texture(texture0,fragTexCoord);
    float opacity=(fragColor.a*65280.+fragColor.r*255.)/65535.;
    float a=texel.a*opacity;
    if(a<=0.)discard;
    vec3 p=fogPosition;
    if(reflectionPass>.5)p.y=2.*waterY-p.y;
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
