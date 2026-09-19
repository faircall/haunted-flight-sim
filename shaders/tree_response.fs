#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform sampler2D trunkResponse;
uniform float foliage;
uniform float partSeed;
uniform float bendAngle;
out vec4 finalColor;

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7)) + partSeed * 19.19) * 43758.5453);
}

void main() {
    // Data alpha stores right-light response, so coverage must come from the art.
    if (texture(texture0, fragTexCoord).a <= 0.01) discard;
    if (foliage < 0.5) {
        finalColor = texture(trunkResponse, fragTexCoord);
        return;
    }
    // Stable small regions in original artwork coordinates, carried by the mesh.
    vec2 cell = floor(fragTexCoord * 128.0 / 3.0);
    float theta = hash21(cell) * 6.2831853 + bendAngle;
    vec2 normal = vec2(cos(theta), sin(theta));
    float base = mix(0.68, 0.79, hash21(cell + 41.0));
    // Broad two-sided fill approximates a thin, porous canopy, not emission.
    vec4 facing = vec4(normal.y, -normal.y, -normal.x, normal.x);
    finalColor = clamp(vec4(base) + 0.16 * facing + 0.05 * abs(facing), 0.55, 1.0);
}
