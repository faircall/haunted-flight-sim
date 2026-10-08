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
uniform vec4 worldFrame;
uniform sampler2D reflectionMap;
uniform mat4 reflectionVP;
uniform float reflectionPass;
uniform int surface;
out vec4 finalColor;
float noise(vec2 p) { return fract(sin(dot(floor(p),vec2(127.1,311.7)))*43758.5453); }
float softNoise(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(noise(i),noise(i+vec2(1,0)),f.x),mix(noise(i+vec2(0,1)),noise(i+1.),f.x),f.y);
}
void main() {
    if(reflectionPass>.5 && worldPosition.y< -1.34)discard;
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse*fragColor;
    if(tex.a<(surface==3?.45:.1))discard;
    vec3 n=normalize(worldNormal);
    vec3 sun=normalize(vec3(-.35,1.,.4));
    float diffuse=max(dot(n,sun),0.);
    vec3 light=mix(vec3(.77,.84,.76),vec3(.23,.29,.33),dusk)+diffuse*mix(.34,.15,dusk);
    if(interior>.5) {
        float bounce=.69+.31*smoothstep(.20,1.04,worldPosition.y);
        light=(mix(vec3(.64,.69,.65),vec3(.28,.34,.37),dusk)+diffuse*.20)*bounce;
    }
    vec3 colour=tex.rgb*light;
    if(surface==5 || surface==6) {
        vec2 p=vec2(worldPosition.x*worldFrame.z-worldPosition.z*worldFrame.w+worldFrame.x,
                    worldPosition.x*worldFrame.w+worldPosition.z*worldFrame.z-worldFrame.y);
        float patches=.7*softNoise(p*.071)+.3*softNoise(p*.19+8.);
        float grit=noise(p*5.);
        vec3 moss=mix(vec3(.17,.30,.12),vec3(.32,.46,.21),patches);
        vec3 rock=mix(vec3(.29,.34,.27),vec3(.42,.46,.34),patches);
        float slope=1.-abs(n.y);
        colour=mix(moss,rock,smoothstep(.32,.70,slope))*(.90+grit*.10)*light;
        if(surface==6)colour=mix(colour,vec3(.27,.38,.29)*light,.18);
    }
    if(surface==7) {
        vec2 global=vec2(worldPosition.x*worldFrame.z-worldPosition.z*worldFrame.w+worldFrame.x,
                    worldPosition.x*worldFrame.w+worldPosition.z*worldFrame.z-worldFrame.y);
        vec2 p=abs(n.y)>.6?global:vec2(global.y,worldPosition.y);
        vec2 blocks=p*vec2(2.1,4.5);blocks.x+=mod(floor(blocks.y),2.)*.5;
        vec2 f=fract(blocks);float edge=min(min(f.x,1.-f.x),min(f.y,1.-f.y));
        float joint=smoothstep(.016,.048,edge);
        vec3 stone=mix(vec3(.28,.33,.27),vec3(.47,.49,.39),noise(blocks));
        stone=mix(vec3(.17,.22,.15),stone,joint);
        float moss=(1.-smoothstep(-.3,.6,worldPosition.y))*(.3+.5*softNoise(global*3.));
        colour=mix(stone,vec3(.17,.25,.10),moss)*light;
    }
    if(surface==3)colour=tex.rgb*(mix(vec3(.76,.88,.68),vec3(.26,.33,.35),dusk)+abs(dot(n,sun))*.22);
    if(surface==1) {
        vec2 p=vec2(worldPosition.x*worldFrame.z-worldPosition.z*worldFrame.w+worldFrame.x,
                    worldPosition.x*worldFrame.w+worldPosition.z*worldFrame.z-worldFrame.y);
        float puddle=step(.60,noise(p*1.2))*.28+step(.83,noise(p*5.))*.20;
        colour=mix(colour,fogColour*.57,puddle);
        float contact=1.-smoothstep(.66,1.15,length(worldPosition.xz/vec2(1.04,2.65)));
        colour*=1.-contact*.38;
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
        vec2 p=vec2(worldPosition.x*worldFrame.z-worldPosition.z*worldFrame.w+worldFrame.x,
                    worldPosition.x*worldFrame.w+worldPosition.z*worldFrame.z-worldFrame.y);
        vec3 view=normalize(eyePosition-worldPosition);
        vec2 wave=vec2(sin(p.x*.91+p.y*.73+time*.72)+.40*sin(p.y*3.7-time*1.16),
                       cos(p.y*1.1-p.x*.32-time*.5)+.32*sin(p.x*4.3+time*.95));
        vec3 waterNormal=normalize(vec3(wave.x*.055,1.,wave.y*.038));
        float fresnel=.12+.82*pow(1.-max(0.,dot(view,waterNormal)),3.);
        vec4 reflected=reflectionVP*vec4(worldPosition,1.);
        vec2 uv=reflected.xy/reflected.w*.5+.5;
        vec3 reflection=texture(reflectionMap,clamp(uv+wave*.0028,vec2(.003),vec2(.997))).rgb;
        float coast=22.*sin(-p.y/90.)+11.*sin(-p.y/43.+.5);
        float shallow=1.-smoothstep(5.,20.,p.x-coast);
        vec3 water=mix(vec3(.065,.21,.175),vec3(.15,.29,.19),shallow);
        water=mix(water,vec3(.026,.061,.075),dusk);
        colour=mix(water,reflection,fresnel);
        vec3 halfVector=normalize(view+sun);
        float glint=pow(max(0.,dot(waterNormal,halfVector)),80.);
        colour+=mix(vec3(.31,.34,.26),vec3(.028,.041,.048),dusk)*glint;
        // Expanding rain rings, broken into small irregular patches.
        vec2 cell=floor(p*2.4);vec2 q=fract(p*2.4)-.5;
        float age=fract(time*.9+noise(cell));
        float ring=(1.-smoothstep(.018,.040,abs(length(q)-age*.44)))*(1.-age)*step(.75,noise(cell+17.));
        colour+=ring*mix(.045,.012,dusk);
        colour+=sin(p.x*5.1+p.y*1.9+time)*.004;
    }
    if(surface==0 && interior<.5)colour+=vec3(.16,.19,.18)*pow(max(0.,dot(n,normalize(sun+normalize(eyePosition-worldPosition)))),40.)*(1.-dusk);
    if(interior<.5 && fogEnd>0.) {
        float distance=length(worldPosition-eyePosition);
        float fog=1.-exp(-pow(distance/max(1.,fogEnd),1.8)*2.4);
        colour=mix(colour,fogColour,fog);
    }
    // A restrained screen-space dither retains the limited-colour feel.
    float grain=(noise(gl_FragCoord.xy)-.5)/180.;
    finalColor=vec4(floor(clamp(colour+grain,0.,1.)*127.+.5)/127.,surface==3?1.:tex.a);
}
