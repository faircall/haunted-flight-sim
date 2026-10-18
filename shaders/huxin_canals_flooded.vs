#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform float windStrength;
uniform float time;
out vec2 fragTexCoord;
out vec3 worldPosition;
out vec3 worldNormal;
void main(){
    vec3 p=vertexPosition;
    float h=max(p.y,0.);
    p.x+=windStrength*sin(time*.43+p.y*.7+matModel[3].x*.18)*min(h*h*.003,.12);
    fragTexCoord=vertexTexCoord;worldPosition=(matModel*vec4(p,1.)).xyz;
    worldNormal=normalize((matNormal*vec4(vertexNormal,0.)).xyz);
    gl_Position=mvp*vec4(p,1.);
}
