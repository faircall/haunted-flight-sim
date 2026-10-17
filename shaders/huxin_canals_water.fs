#version 330
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D reflectionTexture;
uniform vec3 eyePosition;
uniform float time;
uniform float inspection;
uniform vec2 resolution;
uniform float veil;
uniform float voidWorld;
out vec4 finalColor;
float mist(vec3 p){
    float flow=.55+.22*sin(p.x*.065+p.z*.073-time*.07)+.17*sin(p.z*.16-p.x*.09+time*.035);
    return mix(.0055+.052*exp(-max(0.,p.y)*.46)*max(.16,flow),.0095+.010*exp(-max(0.,p.y)*.5)*max(.16,flow),voidWorld);
}
void main(){
    vec3 p=worldPosition;float distance=length(p-eyePosition);
    float speed=mix(1.,.22,voidWorld);
    float a=sin(p.x*1.30+p.z*1.7-time*.40*speed),b=sin(p.x*2.9-p.z*.8+time*.21*speed);
    vec3 n=normalize(vec3(a*.025,1.,b*.019));vec3 v=normalize(eyePosition-p);
    float fresnel=.30+.63*pow(1.-max(0.,dot(n,v)),3.);
    vec2 uv=gl_FragCoord.xy/resolution;
    vec2 warp=vec2(a+.35*b,b*.34)*mix(.0025,.0008,voidWorld)*min(1.,18./max(2.,distance));
    vec3 reflection=texture(reflectionTexture,clamp(uv+warp,vec2(.001),vec2(.999))).rgb;
    vec3 deep=mix(vec3(.035,.075,.076),vec3(.11,.18,.17),inspection);
    deep=mix(deep,vec3(.011,.018,.018),voidWorld);
    vec3 colour=mix(deep,reflection,fresnel);
    float glimmer=pow(max(0.,sin(p.z*5.1+p.x*.14+time*.26)*sin(p.x*.64-p.z*.19)),22.);
    colour+=vec3(.02,.03,.032)*glimmer*min(1.,24./max(1.,distance));
    float density=0.;for(int i=0;i<7;i++)density+=mist(mix(eyePosition,p,(float(i)+.5)/7.));
    float fog=1.-exp(-distance*density/7.);
    vec3 fogColour=mix(vec3(.175,.235,.248),vec3(.39,.455,.45),inspection);
    fogColour=mix(fogColour,vec3(.165,.180,.180),voidWorld);
    colour=mix(colour,fogColour,fog*.88);
    finalColor=vec4(colour,1.);
}
