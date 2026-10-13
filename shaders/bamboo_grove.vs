#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform float time;
uniform float windStrength;
out vec2 fragTexCoord;
out vec3 worldPosition;
out vec3 worldNormal;
void main() {
    vec3 p=vertexPosition;
    // Static architecture has zero wind. Culms flex gradually from fixed roots.
    float h=max(0.,p.y-.8)/14.;
    float gust=sin(time*.67+p.x*.11+p.z*.087)+.32*sin(time*1.21+p.z*.23);
    p.x+=windStrength*h*h*gust*.29;
    p.z+=windStrength*h*h*sin(time*.53+p.x*.13)*.16;
    fragTexCoord=vertexTexCoord;
    worldPosition=(matModel*vec4(p,1.)).xyz;
    worldNormal=normalize((matNormal*vec4(vertexNormal,0.)).xyz);
    gl_Position=mvp*vec4(p,1.);
}
