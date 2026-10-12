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
uniform int lampCount;
uniform vec3 lamps[6];
uniform vec3 columns[8];
out vec4 finalColor;

float shadow(vec3 p,vec3 light) {
    vec2 ray=light.xz-p.xz;float len=dot(ray,ray);float visible=1.;
    for(int j=0;j<8;j++) {
        vec3 column=columns[j];float t=clamp(dot(column.xy-p.xz,ray)/max(.001,len),0.,1.);
        float h=mix(p.y,light.y,t);float d=length(p.xz+ray*t-column.xy);
        if(t>.025&&t<.975&&h<5.7&&h>0.)visible*=smoothstep(column.z-.035,column.z+.09,d);
    }
    // The shrine's broad screen separates its front and rear light pools.
    float t=(-6.96-p.z)/(light.z-p.z);
    if(t>.01&&t<.99) {
        vec3 hit=mix(p,light,t);
        if(abs(hit.x)<4.7&&hit.y>.6&&hit.y<5.4)visible*=.12;
    }
    return .18+.82*visible;
}
void main() {
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;if(tex.a<.4)discard;
    vec3 p=worldPosition,n=normalize(worldNormal);
    vec3 light=vec3(.24,.27,.30);
    light*=.79+.21*smoothstep(0.,2.5,p.y);
    float outside=smoothstep(7.4,10.4,p.z);
    vec3 moon=normalize(vec3(-.45,.76,.52));
    light+=vec3(.10,.17,.24)*max(0.,dot(n,moon))*(.3+.7*outside);
    // Broken, cool lattice light rakes the worn floor near the entrance.
    if(p.y<.08&&p.z>2.&&p.z<10.) {
        float lattice=step(.15,fract((p.x+p.z*.4)*2.3))*step(.17,fract(p.z*2.));
        float entry=1.-smoothstep(4.0,8.,abs(p.x));
        light+=vec3(.11,.18,.22)*lattice*entry*smoothstep(2.,7.,p.z);
    }
    for(int i=0;i<6;i++) {
        if(i>=lampCount)break;
        vec3 delta=lamps[i]-p;float distance=length(delta);
        float falloff=pow(max(0.,1.-distance/13.),1.5)/(1.+distance*distance*.045);
        float flicker=.965+.018*sin(time*3.3+float(i)*2.)+.014*sin(time*7.1+float(i));
        float diffuse=.22+.78*max(0.,dot(n,normalize(delta)));
        light+=vec3(1.48,1.10,.65)*falloff*diffuse*shadow(p,lamps[i])*flicker;
    }
    // Tight grounding under columns, rather than a uniformly glossy floor.
    if(p.y<.09)for(int j=0;j<8;j++)light*=.65+.35*smoothstep(columns[j].z,columns[j].z+.65,length(p.xz-columns[j].xy));
    vec3 neutral=vec3(.78,.77,.70)+vec3(.13)*max(0.,dot(n,moon));
    light=mix(light,neutral,inspection*.88);
    vec3 colour=tex.rgb*light;
    if(p.y<.08&&p.z>8.) {
        vec3 view=normalize(eyePosition-p),halfway=normalize(view+moon);
        colour+=vec3(.09,.13,.14)*pow(max(0.,dot(n,halfway)),48.)*.25;
    }
    colour=mix(colour,tex.rgb*1.7+vec3(.2,.07,.005),emission);
    vec3 fog=mix(vec3(.055,.084,.105),vec3(.30,.36,.35),inspection);
    float distance=length(p-eyePosition);
    colour=mix(colour,fog,smoothstep(35.,95.,distance)*outside*.8);
    finalColor=vec4(colour,tex.a*opacity);
}
