#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
// Fixed along-strand weight, attachment weight, and spatial phase offset.
in vec3 vertexNormal;
uniform mat4 mvp;
uniform vec4 deformation[4];
out vec2 fragTexCoord;
void main() {
    vec4 motion = deformation[0]; // cos(angle), sin(angle), bend, strength
    vec4 shape = deformation[1];  // pivot x/y, hanging length, bend gain
    vec4 phase = deformation[2];  // three temporal phases, strand phase
    vec2 point = vertexPosition.xy - vec2(16.0);
    float localBend = motion.z;
    if (deformation[3].x > 0.5) {
        float along = vertexNormal.x;
        float weight = vertexNormal.y;
        float offset = vertexNormal.z;
        float wave = sin(phase.x - along * 0.405 + offset)
                   + 0.35 * sin(phase.y - along * 0.615 - offset * 0.7);
        point.x += motion.w * shape.w * weight * 1.35 * wave;
        point.y += motion.w * weight * 0.3 * sin(phase.z - along * 0.48 + offset);
        localBend *= 0.8 + 0.2 * sin(offset + phase.w);
    }
    point -= shape.xy;
    float bendWeight = clamp(point.y / shape.z, 0.0, 1.0);
    point.x += localBend * bendWeight * bendWeight;
    point = shape.xy + vec2(point.x * motion.x - point.y * motion.y,
                           point.x * motion.y + point.y * motion.x);
    gl_Position = mvp * vec4(point + vec2(16.0), vertexPosition.z, 1.0);
    fragTexCoord = vertexTexCoord;
}
