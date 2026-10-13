#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D texture0;
uniform sampler2D rockField;
uniform vec4 colDiffuse;
uniform vec3 eyePosition;
uniform vec3 fieldOrigin;
uniform vec3 fieldSize;
uniform vec3 fieldAtlas;
uniform float inspection;
uniform float time;
uniform float opacity;
uniform float emission;
uniform float surfaceKind;
uniform int lampCount;
uniform vec3 lamps[6];
out vec4 finalColor;

float rockSDF(vec3 p){
    vec3 q=(p-fieldOrigin)/fieldAtlas.z;
    if(any(lessThan(q,vec3(0.)))||any(greaterThan(q,fieldSize-vec3(1.))))return 1.5;
    float sy=floor(q.y),ny=min(sy+1.,fieldSize.y-1.);
    vec2 a=vec2(mod(sy,8.)*fieldSize.x+q.x+.5,floor(sy/8.)*fieldSize.z+q.z+.5)/fieldAtlas.xy;
    vec2 b=vec2(mod(ny,8.)*fieldSize.x+q.x+.5,floor(ny/8.)*fieldSize.z+q.z+.5)/fieldAtlas.xy;
    return (mix(texture(rockField,a).r,texture(rockField,b).r,fract(q.y))-.5)*3.;
}
float noise(vec3 p){return .5+.25*sin(p.x*1.7+sin(p.z*1.1))*cos(p.y*2.3+p.z*.9)+.25*sin(p.z*3.1+p.x*.7)*cos(p.y*3.3);}
vec3 tile(vec2 uv,float index){
    // glTF's texture coordinates have already converted Blender's vertical axis.
    vec2 base=vec2(mod(index,4.)*.25+.0645,floor(index/4.)*.25+.0645);
    return texture(texture0,base+abs(fract(uv*.5)*2.-1.)*.121).rgb;
}
vec3 rockColour(vec3 p,vec3 n){
    vec3 weight=pow(abs(n),vec3(5.));weight/=max(.001,weight.x+weight.y+weight.z);
    float index=0.;
    vec3 a=tile(p.zy*.57,index),b=tile(p.xz*.57,index),c=tile(p.xy*.57,index);
    vec3 colour=a*weight.x+b*weight.y+c*weight.z;
    vec3 moss=tile(p.zy*.57,2.)*weight.x+tile(p.xz*.57,2.)*weight.y+tile(p.xy*.57,2.)*weight.z;
    float growth=clamp((1.-smoothstep(.15,1.5,p.y))*.6+smoothstep(.58,.82,noise(p*.43))*.75,0.,1.);
    colour=mix(colour,moss,growth);
    colour*=.84+.23*noise(p*.62);return colour;
}
float visibility(vec3 p,vec3 light){
    vec3 d=light-p;float distance=length(d);vec3 dir=d/max(distance,.001);float visibility=1.;
    // Eight field samples supply real occlusion through arches and rock windows.
    for(int j=0;j<8;j++){
        float t=(float(j)+.7)/8.;float sd=rockSDF(p+dir*distance*t);
        visibility*=smoothstep(-.035,.14,sd);
    }
    return .06+.94*visibility;
}
void main(){
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;if(tex.a<.25)discard;
    vec3 p=worldPosition,n=normalize(worldNormal);if(!gl_FrontFacing)n=-n;
    if(surfaceKind>.5&&surfaceKind<1.5)tex.rgb=rockColour(p,n)*colDiffuse.rgb;
    if(surfaceKind>2.5&&surfaceKind<3.5)tex.rgb=tile(p.xz*.32,3.);
    if(surfaceKind>3.5){
        // Cut from the surrounding limestone, with finer wear on horizontal treads.
        vec3 stone=rockColour(p,n);
        vec3 worn=tile(p.xz*1.15,0.)*(.88+.12*noise(p*.7));
        tex.rgb=mix(stone,worn,smoothstep(.65,.95,n.y)*.58);
    }
    vec3 samplePoint=p+n*.12;float sky=1.;
    for(int j=0;j<4;j++)sky*=smoothstep(-.02,.18,rockSDF(samplePoint+vec3(-.2,1.,.1)*(float(j)*1.2+.3)));
    float ao=smoothstep(-.12,.45,rockSDF(p+n*.31));
    vec3 light=mix(vec3(.25,.29,.29),vec3(.60,.64,.60),inspection)*(.67+.33*ao);
    vec3 moon=normalize(vec3(-.42,.78,.3));
    light+=mix(vec3(.22,.31,.36),vec3(.30,.33,.27),inspection)*(.22+.78*max(0.,dot(n,moon)))*sky;
    for(int i=0;i<6;i++){
        if(i>=lampCount)break;vec3 delta=lamps[i]-p;float d=length(delta);if(d>8.)continue;
        float fall=pow(max(0.,1.-d/8.),1.4)/(1.+d*d*.06);
        float flicker=.97+.017*sin(time*3.2+float(i)*2.1)+.01*sin(time*7.3);
        light+=vec3(1.85,1.20,.58)*fall*(.3+.7*max(0.,dot(n,normalize(delta))))*visibility(samplePoint,lamps[i])*flicker;
    }
    vec3 colour=tex.rgb*light;
    if(surfaceKind>1.5&&surfaceKind<2.5){
        vec3 v=normalize(eyePosition-p);float f=.08+.60*pow(1.-max(0.,dot(n,v)),3.);
        float ripple=sin(p.x*6.+time*.3)*sin(p.z*7.3-time*.5);
        vec3 reflected=vec3(.105,.16,.17)+vec3(.04)*ripple;
        // Broken vertical silhouettes imply the surrounding pillars in the still pool.
        reflected*=.70+.30*smoothstep(.2,.38,abs(sin(p.x*1.7+p.z*.13)));
        colour=mix(vec3(.045,.075,.068),reflected,f);
    }
    colour=mix(colour,tex.rgb*1.18+vec3(.1,.025,0),emission);
    float distance=length(p-eyePosition);float bank=.75+.25*sin(p.x*.15+p.z*.18-time*.11);
    float fog=1.-exp(-distance*(.010+.013*exp(-max(p.y,0.)*.65)*bank));
    colour=mix(colour,mix(vec3(.11,.15,.16),vec3(.27,.32,.31),inspection),fog);
    finalColor=vec4(colour,tex.a*opacity);
}
