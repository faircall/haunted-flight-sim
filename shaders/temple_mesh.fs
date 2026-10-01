#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 eyePosition;
uniform vec3 moonDirection;
uniform float inspection;
uniform float opacity;
uniform float time;
uniform int waterPass;
uniform int lampCount;
uniform vec3 lamps[6];
out vec4 finalColor;
float band(float v) { return floor(clamp(v,0.0,1.0)*5.0+0.5)/5.0; }
void main() {
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;
    if(tex.a<0.5)discard;
    if(waterPass==1) {
        vec2 p=floor(worldPosition.xz);
        float wave=sin(p.y*.36-time*.45+sin(p.x*.012)*.45);
        float patch=sin(p.x*.055+sin(p.y*.014))*cos(p.y*.09-time*.12);
        vec3 colour=(wave>.97 && patch>.68) ? vec3(.055,.105,.16):vec3(.012,.031,.052);
        finalColor=vec4(colour,1.0);return;
    }
    vec3 n=normalize(worldNormal);
    vec3 light=vec3(.08,.11,.16)+vec3(.2,.35,.62)*band(max(dot(n,normalize(moonDirection)),0.0))*.65;
    for(int i=0;i<6;i++) {
        if(i>=lampCount)break;
        vec3 delta=lamps[i]-worldPosition;float distance=length(delta);
        float falloff=pow(max(0.,1.-distance/125.),1.5);
        float diffuse=band(max(dot(n,normalize(delta)),0.0));
        float flicker=.94+.035*sin(time*3.5+float(i)*1.7);
        light+=vec3(1.,.43,.13)*falloff*(.12+diffuse*1.8)*flicker;
    }
    light=mix(light,vec3(.80)+vec3(.17)*band(max(dot(n,normalize(vec3(-.4,1.,.7))),0.)),inspection);
    finalColor=vec4(tex.rgb*light,opacity);
}
