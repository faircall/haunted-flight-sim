#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0,previousFrame;
uniform float worldBlend;
out vec4 finalColor;
void main(){
    // Each endpoint already contains its own water reflection and depth-aware
    // mist. The common opaque pavilion keeps identical coverage in both images.
    vec3 before=texture(previousFrame,fragTexCoord).rgb;
    vec3 after=texture(texture0,fragTexCoord).rgb;
    finalColor=vec4(mix(before,after,worldBlend),1.);
}
