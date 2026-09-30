#version 330
uniform sampler2D texture0,coverageTexture;
uniform vec2 resolution,cameraPosition,tileSize,mapSize;
uniform float time,rainAmount,fireflyDensity;
out vec4 finalColor;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
void main() {
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=pixel+cameraPosition;
    vec2 cell=floor(world/vec2(44.,32.));float seed=hash(cell);
    if(seed>fireflyDensity*(1.-rainAmount*.85))discard;
    vec2 anchor=cell*vec2(44.,32.)+vec2(9.)+vec2(hash(cell+7.),hash(cell+11.))*vec2(26.,14.);
    ivec2 tile=ivec2(floor(anchor/tileSize));
    if(any(lessThan(tile,ivec2(0))) || any(greaterThanEqual(tile,ivec2(mapSize))))discard;
    if(texelFetch(texture0,tile,0).r<.5)discard;
    vec2 center=anchor+vec2(sin(time*.63+seed*49.)*4.+sin(time*.23+seed*91.)*2.,sin(time*.81+seed*27.)*3.);
    float glow=pow(max(0.,sin(time*(.6+seed*.4)+seed*73.)),3.);
    if(glow<.1)discard;
    vec2 delta=abs(world-floor(center)-.5);
    float distance=max(delta.x,delta.y);
    if(distance>2.)discard;
    if(texture(coverageTexture,gl_FragCoord.xy/resolution).a>.05)discard;
    float alpha=distance<.6?(.5+.5*glow):(distance<1.6?.13:.035)*glow;
    finalColor=vec4(distance<.6?vec3(.88,.96,.42):vec3(.53,.76,.20),alpha);
}
