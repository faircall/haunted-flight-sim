#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 eyePosition;
uniform float inspection;
uniform float time;
uniform float opacity;
uniform float emission;
uniform float waterPass;
uniform int lampCount;
uniform vec3 lamps[6];
out vec4 finalColor;

float hash(vec3 p){p=fract(p*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
float inside(vec3 p){return (1.-smoothstep(4.35,4.9,abs(p.x)))*(1.-smoothstep(-5.9,-5.,p.z))*smoothstep(-13.5,-12.8,p.z)*(1.-smoothstep(4.,5.5,p.y));}
float roomShadow(vec3 p,vec3 lamp){
    float d=lamp.z-p.z;
    if(abs(d)<.001)return 1.;
    float t=(-5.-p.z)/d;
    if(t>0.&&t<1.){vec3 hit=mix(p,lamp,t);if(abs(hit.x)>1.3&&abs(hit.x)<4.8&&hit.y<4.)return .12;}
    return 1.;
}
void main(){
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;if(tex.a<.25)discard;
    vec3 p=worldPosition,n=normalize(worldNormal);if(!gl_FrontFacing)n=-n;
    vec3 moon=normalize(vec3(-.52,.74,.25));float interior=inside(p);
    float canopy=.77+.23*sin(p.x*.79+p.z*.31+sin(time*.28+p.z*.13));
    vec3 light=mix(vec3(.38,.49,.43),vec3(.70,.78,.61),inspection);
    light*=.55+.45*smoothstep(-.1,5.,p.y);light*=1.-interior*.45;
    light+=mix(vec3(.22,.32,.35),vec3(.24,.27,.18),inspection)*max(0.,dot(n,moon))*canopy*(1.-interior*.88);
    // Sparse moving shafts pick out the path, leaving the bamboo depths unlit.
    float shafts=pow(max(0.,sin(p.x*.71+p.z*.23+sin(p.z*.32)*.6)),16.);
    light+=vec3(.12,.20,.16)*shafts*max(0.,n.y)*(1.-interior);
    for(int i=0;i<6;i++){
        if(i>=lampCount)break;
        vec3 delta=lamps[i]-p;float dist=length(delta);
        float fall=pow(max(0.,1.-dist/7.8),1.7)/(1.+dist*dist*.055);
        float flicker=.97+.018*sin(time*2.7+float(i)*3.)+.01*sin(time*7.);
        light+=vec3(1.48,.98,.48)*fall*(.28+.72*max(0.,dot(n,normalize(delta))))*flicker*roomShadow(p,lamps[i]);
    }
    // Ground colour drifts across tile boundaries instead of making a checkerboard.
    if(fragTexCoord.x<.5&&fragTexCoord.y>.5&&fragTexCoord.y<.75&&p.y<.3)
        tex.rgb=mix(tex.rgb,vec3(.14,.20,.10),noise(p*.58)*.38);
    vec3 colour=tex.rgb*light;
    if(waterPass>.5){
        float rings=sin(length(p.xz-vec2(-6.5,-1.))*32.-time*2.7);
        vec3 view=normalize(eyePosition-p);float fresnel=.08+.45*pow(1.-max(0.,dot(n,view)),3.);
        colour=mix(colour,vec3(.21,.35,.32),fresnel)+vec3(.035,.048,.038)*rings;
    }
    colour=mix(colour,tex.rgb*1.15+vec3(.10,.025,0),emission);
    // Integrate slowly drifting, height-dependent mist along the visible ray.
    vec3 ray=p-eyePosition;float distance=length(ray),density=0.;
    for(int i=0;i<6;i++){
        vec3 q=eyePosition+ray*(float(i)+.5)/6.;
        float bank=noise(q*vec3(.11,.19,.11)+vec3(time*.008,0,time*.003));
        float low=exp(-max(0.,q.y)*.48);
        density+=(.0038+low*(.005+.045*smoothstep(.30,.70,bank)))*(1.-inside(q)*.94);
    }
    float fog=1.-exp(-distance*density/6.);
    vec3 mist=mix(vec3(.14,.215,.195),vec3(.29,.37,.31),inspection);
    colour=mix(colour,mist,fog);
    finalColor=vec4(colour,tex.a*opacity);
}
