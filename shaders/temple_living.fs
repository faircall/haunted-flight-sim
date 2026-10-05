#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
in float plantSurface;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 moonDirection;
uniform float inspection;
uniform float time;
uniform float opacity;
uniform int lampCount;
uniform vec3 lamps[6];
out vec4 finalColor;
float band(float value) { return floor(clamp(value,0.0,1.0)*5.0+0.5)/5.0; }
float response(vec3 normal,vec3 direction) {
    float facing=dot(normal,direction);
    return mix(max(0.0,facing),0.3+0.7*abs(facing),plantSurface);
}
void main() {
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;
    if(tex.a<0.5)discard;
    vec3 normal=normalize(worldNormal);
    vec3 light=vec3(.08,.11,.16)+vec3(.2,.35,.62)*band(response(normal,normalize(moonDirection)))*.65;
    for(int i=0;i<6;i++) {
        if(i>=lampCount)break;
        vec3 delta=lamps[i]-worldPosition;
        float falloff=pow(max(0.,1.-length(delta)/125.),1.5);
        float diffuse=band(response(normal,normalize(delta)));
        float flicker=.94+.035*sin(time*3.5+float(i)*1.7);
        light+=vec3(1.,.43,.13)*falloff*(.12+diffuse*1.8)*flicker;
    }
    vec3 neutral=vec3(.80)+vec3(.17)*band(response(normal,normalize(vec3(-.4,1.,.7))));
    light=mix(light,neutral,inspection);
    finalColor=vec4(tex.rgb*light,opacity);
}
