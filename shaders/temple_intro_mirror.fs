#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform float mirrorSide;
out vec4 finalColor;
void main(){
    vec2 uv=fragTexCoord;
    vec2 corner=max(abs(uv-.5)-vec2(.45,.40),0.);
    if(length(corner/vec2(.055,.11))>1.)discard;
    vec2 sampleUV=vec2(1.-uv.x,uv.y);
    // The narrow interior glass crops a rear panorama instead of stretching faces.
    if(abs(mirrorSide)<.5)sampleUV.y=sampleUV.y*.442+.29;
    sampleUV.x=clamp(sampleUV.x*.78+.11+mirrorSide*.09,.003,.997);
    vec3 reflection=texture(texture0,sampleUV).rgb;
    float edge=smoothstep(0.,.045,min(min(uv.x,1.-uv.x),min(uv.y,1.-uv.y)));
    reflection=reflection*vec3(.79,.84,.79)+vec3(.017,.022,.018);
    finalColor=vec4(mix(vec3(.09,.115,.10),reflection,edge),1.);
}
