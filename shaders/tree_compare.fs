#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
uniform sampler2D responseTexture;
uniform vec4 lightWeights;
uniform float lit;
out vec4 finalColor;
void main() {
    vec4 art = texture(texture0, fragTexCoord) * fragColor;
    float response = dot(texture(responseTexture, fragTexCoord), lightWeights);
    finalColor = vec4(art.rgb * mix(1.0, .18 + .85*response, lit), art.a);
}
