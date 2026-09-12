#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform vec2 blurStep;
out vec4 finalColor;
void main() {
    vec3 color = texture(texture0, fragTexCoord).rgb * 0.227027;
    color += texture(texture0, fragTexCoord + blurStep * 1.384615).rgb * 0.316216;
    color += texture(texture0, fragTexCoord - blurStep * 1.384615).rgb * 0.316216;
    color += texture(texture0, fragTexCoord + blurStep * 3.230769).rgb * 0.070270;
    color += texture(texture0, fragTexCoord - blurStep * 3.230769).rgb * 0.070270;
    finalColor = vec4(color, 1.0);
}
