#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
out vec4 finalColor;
void main() {
    finalColor = vec4(0.0, 0.0, 0.0, texture(texture0, fragTexCoord).a);
}
