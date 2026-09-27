#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform sampler2D waterMask;
uniform sampler2D foregroundMask;
uniform sampler2D lightTexture;
uniform vec2 resolution;
uniform vec2 mapSize;
uniform vec2 cameraPosition;
uniform vec2 moonPosition;
uniform vec3 moonColor;
uniform float time;
uniform float reflectionStrength;
uniform float rippleStrength;
uniform float reflectionPass;
uniform vec4 firePositions[8];
uniform vec4 fireColors[8];
out vec4 finalColor;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
}
void main() {
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+.5;
    vec2 world=pixel+cameraPosition;
    vec2 mapUv=world/mapSize;
    if(any(lessThan(mapUv,vec2(0))) || any(greaterThanEqual(mapUv,vec2(1)))) discard;
    if(texture(waterMask,mapUv).r<.5) discard;
    vec2 uv=gl_FragCoord.xy/resolution;
    float foreground=reflectionPass>.5?texture(foregroundMask,uv).a:0.;
    if(foreground>.999) discard;
    float swell=sin(world.x*.033+world.y*.061-time*.57)+.45*sin(world.x*.089-world.y*.041+time*.36);
    float grain=noise(world*vec2(.11,.29)+vec2(time*.028,0));
    float ripple=sin(world.y*.39+world.x*.026+swell*.6-time*.73);
    vec2 warp=vec2(swell*.85+sin(world.x*.067-world.y*.078+time*.62)*.35,ripple*.32)*rippleStrength;
    vec2 reflectionUv=(vec2(pixel.x,resolution.y-pixel.y)+vec2(round(warp.x),round(warp.y)))/resolution;
    vec4 reflected=texture(texture0,clamp(reflectionUv,vec2(.001),vec2(.999)));
    float breakup=.30+.70*smoothstep(-.2,.85,ripple+grain*.65);
    vec3 direct=texture(lightTexture,uv).rgb;
    vec3 base=vec3(.004,.011,.019)+vec3(.006,.014,.022)*(grain*.7+swell*.08+.2);
    base+=direct*vec3(.019,.027,.034);
    vec2 delta=world-moonPosition;
    float moonWidth=17.+max(0.,delta.y)*.22;
    float moonLane=exp(-pow((delta.x+swell*6.)/moonWidth,2.))*exp(-abs(delta.y)/310.);
    float glints=pow(max(0.,ripple),12.)*smoothstep(.35,.73,grain);
    base+=moonColor*moonLane*glints*.25;
    vec3 color=base;
    for(int i=0;i<8;i++) {
        vec4 fire=firePositions[i];
        float dy=world.y-fire.y;
        float width=2.4+max(0.,dy)*.075;
        float line=exp(-pow((world.x-fire.x+swell*1.5)/width,2.))*exp(-max(0.,dy)/48.);
        float fragments=.22+.78*pow(max(0.,sin(world.y*.72+world.x*.06+swell-time*.95)),3.);
        color+=fireColors[i].rgb*fire.z*line*fragments*.27*step(0.,dy)*step(dy,150.);
    }
    // Quantise light, never blur the painted sprites or move a whole pixel row.
    if(reflectionPass>.5) color=reflected.rgb*reflectionStrength*breakup*(1.-foreground);
    color=floor(max(color,vec3(0))*96.+.5)/96.;
    finalColor=vec4(color,1.);
}
