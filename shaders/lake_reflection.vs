#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec4 vertexColor;
uniform mat4 mvp;
uniform float mirrorY;
uniform float stretch;
out vec2 fragTexCoord;
out vec4 fragColor;
out vec2 sourcePixel;
void main() {
    sourcePixel=vertexPosition.xy;
    vec3 position=vertexPosition;
    position.y=mirrorY+(mirrorY-position.y)*stretch;
    gl_Position=mvp*vec4(position,1.0);
    fragTexCoord=vertexTexCoord;
    fragColor=vertexColor;
}
