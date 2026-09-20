#version 330
in vec2 fragTexCoord; // angle and transmission fill, constant over each leaf
in vec4 fragColor;
uniform float responsePass;
out vec4 finalColor;
void main() {
    if (responsePass < 0.5) { finalColor = fragColor; return; }
    vec2 normal = vec2(cos(fragTexCoord.x), sin(fragTexCoord.x));
    vec4 facing = vec4(normal.y, -normal.y, -normal.x, normal.x);
    finalColor = clamp(vec4(fragTexCoord.y) + .16*facing + .05*abs(facing), .55, 1.0);
}
