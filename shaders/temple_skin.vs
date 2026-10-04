#version 330
in vec3 vertexPosition;
in vec3 vertexNormal;
in vec2 vertexTexCoord;
in vec4 vertexBoneIds;
in vec4 vertexBoneWeights;
uniform mat4 mvp;
uniform mat4 matModel;
uniform mat4 matNormal;
uniform mat4 boneMatrices[128];
uniform mat4 previousPose[32];
uniform float poseBlend;
out vec2 fragTexCoord;
out vec3 worldPosition;
out vec3 worldNormal;
out float plantSurface;
void main() {
    mat4 pose=mat4(0.0);
    for(int joint=0;joint<4;joint++) {
        int bone=int(vertexBoneIds[joint]);
        pose+=(previousPose[bone]*(1.0-poseBlend)+boneMatrices[bone]*poseBlend)*vertexBoneWeights[joint];
    }
    vec4 position=pose*vec4(vertexPosition,1.0);
    worldPosition=(matModel*position).xyz;
    worldNormal=normalize(mat3(matNormal)*mat3(pose)*vertexNormal);
    fragTexCoord=vertexTexCoord;
    plantSurface=0.0;
    gl_Position=mvp*position;
}
