#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
uniform float groundDepth;
out vec4 finalColor;
void main() {
    if (texture(texture0, fragTexCoord).a * fragColor.a < 0.5) discard;
    float encoded = floor(clamp((groundDepth + 2048.0)*16.0, 0.0, 65535.0));
    finalColor = vec4(floor(encoded/256.0)/255.0, mod(encoded,256.0)/255.0, 0.0, 1.0);
}
