#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in vec2 vertexTexCoord;
in vec2 vertexTexCoord2;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform float time;
uniform float windStrength;
out vec2 fragTexCoord;
out vec3 worldPosition;
out vec3 worldNormal;
out float plantSurface;
void main() {
    vec3 p=vertexPosition;
    vec3 anchor=(matModel*vec4(0.0,0.0,0.0,1.0)).xyz;
    float weight=abs(vertexTexCoord2.x);
    float phase=vertexTexCoord2.y*6.283185;
    float gust=0.55+0.30*sin(time*0.37+anchor.x*0.006)+0.20*sin(time*0.71-anchor.z*0.008);
    float sway=gust+0.60*sin(time*1.25+phase*0.7);
    vec3 bend=weight*windStrength*vec3(sway,0.07*sin(time*1.7+phase),0.26*sin(time*1.08+phase)+gust*0.3);
    // Unit-scale instances may rotate, but the prevailing wind stays world-aligned.
    p+=transpose(mat3(matModel))*bend;
    worldPosition=(matModel*vec4(p,1.0)).xyz;
    worldNormal=normalize(mat3(matNormal)*vertexNormal);
    fragTexCoord=vertexTexCoord;
    plantSurface=step(0.0,vertexTexCoord2.x);
    gl_Position=mvp*vec4(p,1.0);
}
