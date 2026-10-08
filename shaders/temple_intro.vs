#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec2 vertexTexCoord2;
in vec3 vertexNormal;
in vec4 vertexColor;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform float time;
uniform int surface;
out vec2 fragTexCoord;
out vec3 worldPosition;
out vec3 worldNormal;
out vec4 fragColor;
void main() {
    fragTexCoord=vertexTexCoord;
    vec3 position=vertexPosition;
    if(surface==3) {
        float weight=abs(vertexTexCoord2.x);
        float phase=vertexTexCoord2.y*6.283;
        position.x+=sin(time*1.3+phase+position.y*.24)*weight*.075;
        position.z+=sin(time*.91+phase)*weight*.055;
    }
    worldPosition=(matModel*vec4(position,1.0)).xyz;
    worldNormal=(matNormal*vec4(vertexNormal,0.0)).xyz;
    fragColor=vertexColor;
    gl_Position=mvp*vec4(position,1.0);
}
