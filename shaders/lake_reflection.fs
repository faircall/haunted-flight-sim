#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
in vec2 sourcePixel;
in float reflectedDistance;
uniform sampler2D texture0;
uniform sampler2D litScene;
uniform vec2 resolution;
out vec4 finalColor;
void main() {
    float mask=texture(texture0,fragTexCoord).a*fragColor.a;
    vec2 uv=vec2(sourcePixel.x/resolution.x,1.0-sourcePixel.y/resolution.y);
    if(mask<.01 || any(lessThan(uv,vec2(0.))) || any(greaterThan(uv,vec2(1.)))) discard;
    vec3 color=texture(litScene,uv).rgb;
    finalColor=vec4(color,mask*exp(-reflectedDistance*.005));
}
