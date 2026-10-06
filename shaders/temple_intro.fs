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
uniform int surface;
out vec4 finalColor;
float noise(vec2 p) { return fract(sin(dot(floor(p),vec2(127.1,311.7)))*43758.5453); }
void main() {
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse*fragColor;
    if(tex.a<.1)discard;
    vec3 n=normalize(worldNormal);
    float diffuse=floor(max(dot(n,normalize(vec3(-.35,1.,.4))),0.)*4.+.5)/4.;
    vec3 light=mix(vec3(.56,.61,.56),vec3(.23,.29,.33),dusk)+diffuse*mix(.26,.15,dusk);
    if(interior>.5)light=mix(vec3(.69,.70,.64),vec3(.28,.34,.37),dusk)+diffuse*.14;
    vec3 colour=tex.rgb*light;
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
    if(interior<.5) {
        float distance=length(worldPosition-eyePosition);
        float fog=1.-exp(-pow(distance/max(1.,fogEnd),1.8)*2.4);
        colour=mix(colour,fogColour,fog);
    }
    // A restrained screen-space dither retains the limited-colour feel.
    float grain=(noise(gl_FragCoord.xy)-.5)/90.;
    finalColor=vec4(floor(clamp(colour+grain,0.,1.)*63.+.5)/63.,tex.a);
}
