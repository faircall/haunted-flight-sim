#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec4 vertexColor;
uniform mat4 mvp;
out vec2 fragTexCoord;
out vec4 fragColor;
out vec3 fogPosition;
void main(){
    fragTexCoord=vertexTexCoord;
    fragColor=vertexColor;
    fogPosition=vertexPosition;
    gl_Position=mvp*vec4(vertexPosition,1.);
}
