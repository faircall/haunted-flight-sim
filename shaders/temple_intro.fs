#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
in vec4 fragColor;
uniform sampler2D texture0;
uniform vec4 colDiffuse;
uniform vec3 eyePosition;
uniform vec3 fogColour;
uniform float fogEnd;
uniform float dusk;
uniform float headlights;
uniform float interior;
uniform float travel;
uniform float time;
uniform int surface;
out vec4 finalColor;
float noise(vec2 p) { return fract(sin(dot(floor(p),vec2(127.1,311.7)))*43758.5453); }
void main() {
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse*fragColor;
    if(tex.a<(surface==3?.45:.1))discard;
    vec3 n=normalize(worldNormal);
    float diffuse=floor(max(dot(n,normalize(vec3(-.35,1.,.4))),0.)*4.+.5)/4.;
    vec3 light=mix(vec3(.56,.61,.56),vec3(.23,.29,.33),dusk)+diffuse*mix(.26,.15,dusk);
    if(interior>.5)light=mix(vec3(.69,.70,.64),vec3(.28,.34,.37),dusk)+diffuse*.14;
    vec3 colour=tex.rgb*light;
    if(surface==5 || surface==6) {
        vec2 p=worldPosition.xz+vec2(0,-travel);
        float patches=.5+.5*sin(p.x*.31+sin(p.y*.12)*2.)*sin(p.y*.19+p.x*.08);
        float grit=noise(p*5.);
        vec3 moss=mix(vec3(.25,.31,.23),vec3(.36,.41,.31),patches);
        vec3 rock=mix(vec3(.37,.41,.38),vec3(.46,.47,.41),patches);
        float slope=1.-abs(n.y);
        colour=mix(moss,rock,smoothstep(.14,.5,slope))*(.93+grit*.07)*light;
        if(surface==6)colour=mix(colour,vec3(.35,.43,.41)*light,.3);
    }
    if(surface==3)colour=tex.rgb*(mix(vec3(.65,.70,.62),vec3(.26,.33,.35),dusk)+abs(dot(n,normalize(vec3(-.35,1.,.4))))*.17);
    if(surface==1) {
        vec2 p=worldPosition.xz+vec2(0,-travel);
        float puddle=step(.60,noise(p*1.2))*.28+step(.83,noise(p*5.))*.20;
        colour=mix(colour,fogColour*.44,puddle);
        float ahead=-worldPosition.z;
        float cone=smoothstep(2.,7.,ahead)*(1.-smoothstep(18.,35.,ahead));
        cone*=1.-smoothstep(.4+ahead*.05,1.0+ahead*.15,abs(worldPosition.x));
        colour+=vec3(.30,.26,.16)*cone*headlights;
    }
    if(surface==2)colour=mix(colour,vec3(1.,.91,.67),headlights);
    if(interior<.5 && surface!=2 && surface!=4) {
        float ahead=-worldPosition.z;
        float beam=smoothstep(1.8,5.,ahead)*(1.-smoothstep(21.,37.,ahead));
        beam*=1.-smoothstep(.4+ahead*.06,.9+ahead*.18,abs(worldPosition.x));
        beam*=1.-smoothstep(.8,2.6,worldPosition.y);
        colour+=tex.rgb*vec3(.35,.29,.17)*beam*headlights;
    }
    if(surface==4) {
        vec2 p=worldPosition.xz+vec2(0,-travel);
        vec3 view=normalize(eyePosition-worldPosition);
        float fresnel=pow(1.-abs(view.y),3.);
        float ripple=sin(p.y*7.3+sin(p.x*.53)+time*1.3)*sin(p.x*.71-p.y*3.1-time*.7);
        float bands=.5+.5*sin(p.y*.11+sin(p.x*.017)*2.);
        vec3 water=mix(vec3(.13,.22,.21),vec3(.033,.067,.09),dusk);
        colour=mix(water,fogColour*.68,fresnel*.72);
        colour*=.85+.15*bands;
        colour+=ripple*mix(.022,.007,dusk)*(.25+.75*fresnel);
        float rain=step(.982,noise(p*13.+floor(time*9.)));
        colour+=rain*.021;
    }
    if(interior<.5 && fogEnd>0.) {
        float distance=length(worldPosition-eyePosition);
        float fog=1.-exp(-pow(distance/max(1.,fogEnd),1.8)*2.4);
        colour=mix(colour,fogColour,fog);
    }
    // A restrained screen-space dither retains the limited-colour feel.
    float grain=(noise(gl_FragCoord.xy)-.5)/90.;
    finalColor=vec4(floor(clamp(colour+grain,0.,1.)*63.+.5)/63.,tex.a);
}
