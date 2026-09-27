#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
uniform sampler2D stateTexture;
uniform vec2 resolution;
uniform vec4 playerRect;
uniform float transparency;
uniform float maskPass;
uniform float premultiplied;
out vec4 finalColor;
void main() {
    vec4 sprite=texture(texture0,fragTexCoord)*fragColor;
    if (sprite.a<=0.001) discard;
    vec2 pixel=floor(vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y))+0.5;
    vec2 center=playerRect.xy+playerRect.zw*0.5;
    vec2 radius=playerRect.zw*0.5+vec2(4.0,7.0);
    float patch=1.0-smoothstep(0.55,1.0,length((pixel-center)/radius));
    float strength=texture(stateTexture,vec2(0.5)).r;
    strength=strength*strength*(3.0-2.0*strength);
    vec3 color=maskPass>0.5?vec3(0.0):sprite.rgb;
    if (premultiplied>0.5) color/=max(sprite.a,0.001);
    finalColor=vec4(color,sprite.a*(1.0-transparency*strength*patch));
}
