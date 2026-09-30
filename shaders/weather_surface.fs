#version 330
uniform sampler2D texture0;
uniform sampler2D lightTexture;
uniform vec2 resolution,cameraPosition,tileSize,mapSize;
uniform float time,rainAmount,wetness,flash;
out vec4 finalColor;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
}
void main() {
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=pixel+cameraPosition;
    ivec2 tile=ivec2(floor(world/tileSize));
    if(any(lessThan(tile,ivec2(0))) || any(greaterThanEqual(tile,ivec2(mapSize))))discard;
    vec3 terrain=texelFetch(texture0,tile,0).rgb;
    float exposed=terrain.b*(1.-terrain.r);
    if(exposed<.5)discard;
    vec2 cell=floor(world/13.);
    float cycle=time*(1.4+hash(cell+91.)*.5)+hash(cell+17.);
    float serial=floor(cycle),age=fract(cycle);
    float selected=step(hash(cell+serial*7.),rainAmount*.65);
    vec2 center=cell*13.+vec2(5.)+vec2(hash(cell+serial),hash(cell+serial+83.))*3.;
    vec2 delta=world-floor(center)-.5;
    // Wet planks darken first. Later shallow irregular patches catch sky
    // and nearby lantern/fire light. Crisp thresholds keep pixel edges.
    float wood=terrain.g;
    float puddle=wood*step(1.-wetness*.56,noise(world*vec2(.047,.105)));
    vec3 direct=texture(lightTexture,gl_FragCoord.xy/resolution).rgb;
    float glint=puddle*step(.50+.12*sin(time*.8),noise(world*vec2(.031,.35)));
    vec3 color=mix(vec3(.012,.021,.034),vec3(.09,.15,.24)+min(direct,vec3(.65))*.55+flash*.35,glint);
    // A brief pinprick catches light at contact; no animated splash glyph.
    float drop=selected*(1.-step(.15,age))*step(abs(delta.x),.85)*step(abs(delta.y),.55);
    color=mix(color,vec3(.09,.14,.20)+min(direct,vec3(.5))*.35+flash*.2,drop);
    float alpha=max(wood*wetness*.16,max(glint*wetness*.35,drop*.35));
    if(alpha<.005)discard;
    finalColor=vec4(color,alpha);
}
