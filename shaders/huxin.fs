#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 eyePosition;
uniform float time;
uniform float inspection;
uniform float opacity;
uniform float emission;
uniform float surfaceKind;
uniform float reflectionPass;
uniform float deckHeight;
uniform int lampCount;
uniform vec3 lamps[5];
out vec4 finalColor;
float mist(vec3 p){
    float flow=.55+.22*sin(p.x*.065+p.z*.073-time*.07)+.17*sin(p.z*.16-p.x*.09+time*.035);
    return .0055+.052*exp(-max(0.,p.y)*.46)*max(.16,flow);
}
vec3 fogColour(){return mix(vec3(.175,.235,.248),vec3(.39,.455,.45),inspection);}
float fogAmount(vec3 a,vec3 b){
    float density=0.;
    for(int i=0;i<7;i++)density+=mist(mix(a,b,(float(i)+.5)/7.));
    return 1.-exp(-length(a-b)*density/7.);
}
vec3 tile(vec2 uv,float index){
    vec2 base=vec2(mod(index,4.)*.25+.0645,floor(index/4.)*.25+.0645);
    return texture(texture0,base+abs(fract(uv*.5)*2.-1.)*.121).rgb;
}
void main(){
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;
    float alphaCut=surfaceKind>2.5?mix(.32,.11,smoothstep(18.,90.,length(worldPosition-eyePosition))):.36;
    if(tex.a<alphaCut)discard;
    vec3 p=worldPosition,n=normalize(worldNormal);if(reflectionPass<.5&&!gl_FrontFacing)n=-n;
    if(reflectionPass>.5){if(p.y>.02)discard;p.y=-p.y;n.y=-n.y;}
    if(surfaceKind>.5&&surfaceKind<1.5){
        vec3 w=pow(abs(n),vec3(4.));w/=max(.001,w.x+w.y+w.z);
        tex.rgb=tile(p.zy*.7,2.)*w.x+tile(p.xz*.7,2.)*w.y+tile(p.xy*.7,2.)*w.z;
        tex.rgb*=.82+.18*smoothstep(-.15,.75,p.y);
        float damp=1.-smoothstep(-.03,.30,p.y);tex.rgb=mix(tex.rgb,tex.rgb*vec3(.56,.69,.54),damp*.7);
    }
    if(surfaceKind>1.5&&surfaceKind<2.5)tex.rgb=mix(vec3(.075,.10,.085),vec3(.20,.235,.19),max(0.,n.y));
    if(surfaceKind>3.5){
        float patch=.5+.24*sin(p.x*.81+p.z*.35)+.17*sin(p.x*1.9-p.z*.73);
        vec3 earth=tile(p.xz*.42,4.)*vec3(.69,.60,.49),moss=tile(p.xz*.36,5.)*vec3(.63,.78,.57);
        tex.rgb=mix(earth,moss,smoothstep(.25,.75,patch));
        tex.rgb*=mix(.58,1.,smoothstep(-.05,.42,p.y));
    }
    float underRoof=(length(p.xz)<5.45&&p.y<deckHeight+4.85)? .2:1.;
    vec3 light=mix(vec3(.37,.41,.42),vec3(.70,.73,.66),inspection);
    light+=mix(vec3(.26,.34,.39),vec3(.27,.30,.24),inspection)*max(0.,dot(n,normalize(vec3(-.5,.72,.3))))*underRoof;
    for(int i=0;i<5;i++){
        if(i>=lampCount)break;vec3 d=lamps[i]-p;float dist=length(d);
        float fall=pow(max(0.,1.-dist/9.),1.4)/(1.+dist*dist*.13);
        light+=vec3(2.25,1.55,.72)*fall*(.27+.73*max(0.,dot(n,normalize(d))));
    }
    vec3 colour=tex.rgb*light;
    colour=mix(colour,tex.rgb*1.15+vec3(.16,.05,.002),emission);
    vec3 eye=eyePosition;if(reflectionPass>.5)eye.y=-eye.y;
    float fog=fogAmount(eye,p);if(reflectionPass>.5)fog*=.77;
    colour=mix(colour,fogColour(),fog);
    finalColor=vec4(colour,(surfaceKind>2.5?1.:tex.a)*opacity);
}
