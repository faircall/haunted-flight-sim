#version 330
uniform sampler2D texture0,exposureTexture,coverageTexture,lightTexture;
uniform vec2 resolution,cameraPosition,mapSize;
uniform vec4 roofRect,playerRect;
uniform float time,rainAmount,flash,eaveFloor,roofOpacity,windShift,runoffElevation;
out vec4 finalColor;
float hash(float n) { return fract(sin(n*127.1+311.7)*43758.5453); }
void main() {
    vec2 screen=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=screen+cameraPosition;
    float height=max(8.,eaveFloor-roofRect.y-roofRect.w);
    float drift=windShift*clamp((world.y-roofRect.y-roofRect.w)/height,0.,1.);
    float cell=floor((world.x-roofRect.x-drift)/4.);
    float origin=cell*4.+.5+hash(cell+19.)*3.;
    if(origin<0. || origin>=roofRect.z)discard;
    vec2 edge=texelFetch(texture0,ivec2(int(origin),0),0).rg;
    if(edge.g<.1)discard;
    float top=roofRect.y+round(edge.r*roofRect.w);
    vec2 ground=vec2(roofRect.x+origin+windShift,eaveFloor);
    if(any(lessThan(ground,vec2(0.))) || any(greaterThanEqual(ground,mapSize)))discard;
    vec4 receiver=texture(exposureTexture,ground/mapSize);
    // Eave floor is projected at the supporting deck's elevation. Continue
    // below that plane where there is only lake/low ground underneath.
    ground.y+=runoffElevation-round(receiver.a*255.);
    float landing=max(top+1.,ground.y);
    height=max(1.,landing-top);
    float clock=time*(1.1+hash(cell+37.)*.7)+hash(cell+73.)*31.;
    float age=fract(clock);
    if(hash(cell+floor(clock)*83.)>rainAmount*edge.g)discard;
    // Reach the receiving surface BEFORE the contact flash begins.
    float flight=min(1.,age/.87);
    float travel=flight*flight*height;
    float dx=world.x-roofRect.x-origin-windShift*clamp((world.y-top)/height,0.,1.);
    float fall=step(abs(dx),.65)*step(top+travel,world.y)*(1.-step(top+travel+2.+age*3.,world.y));
    fall*=step(top,world.y)*(1.-step(landing,world.y))*(1.-step(.87,age))*roofOpacity;
    float contact=step(.87,age)*step(abs(world.x-ground.x),1.6)*step(abs(world.y-ground.y),.6)*receiver.b;
    vec4 contactReceiver=texture(exposureTexture,vec2(world.x,eaveFloor)/mapSize);
    contact*=contactReceiver.b*(1.-step(.5,abs(contactReceiver.a-receiver.a)*255.));
    if(max(fall,contact)<.01)discard;
    if(all(greaterThanEqual(world,playerRect.xy)) && all(lessThan(world,playerRect.xy+playerRect.zw)) &&
       texture(coverageTexture,gl_FragCoord.xy/resolution).a>.05)discard;
    vec3 light=texture(lightTexture,gl_FragCoord.xy/resolution).rgb;
    float lit=clamp(max(light.r,max(light.g,light.b)),0.,1.);
    vec3 color=vec3(.12,.20,.30)+min(light,vec3(.8))*.35+flash*vec3(.25,.32,.42);
    color=floor(color*24.+.5)/24.;
    float alpha=max(fall*(.22+.22*lit+.18*flash),contact*(.28+.18*lit));
    alpha=floor(alpha*8.+.5)/8.;
    finalColor=vec4(color,alpha);
}
