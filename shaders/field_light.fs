#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform vec3 lightColor;
uniform float intensity;
uniform float unmasked;
out vec4 finalColor;
void main() {
    float strength = unmasked > .5 ? 1.0 : texture(texture0, fragTexCoord).r;
    finalColor = vec4(lightColor * intensity * strength, 1.0);
}
