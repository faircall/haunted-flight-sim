#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
in vec2 sourcePixel;
uniform sampler2D texture0;
uniform sampler2D litScene;
uniform vec2 resolution;
out vec4 finalColor;
void main() {
    float mask=texture(texture0,fragTexCoord).a*fragColor.a;
    vec2 source=floor(sourcePixel)+.5;
    vec2 uv=vec2(source.x/resolution.x,1.0-source.y/resolution.y);
    if(mask<.01 || any(lessThan(uv,vec2(0.))) || any(greaterThan(uv,vec2(1.)))) discard;
    // Copy a single lit source pixel. Distance must not invent darker shades.
    vec3 color=texelFetch(litScene,ivec2(source.x,resolution.y-source.y),0).rgb;
    finalColor=vec4(color,mask);
}
