#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
uniform sampler2D texture0,otherStone;
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
uniform vec3 lamps[16];
uniform float veil;
uniform float enclosed;
uniform float warmth;
uniform float flatPaving;
uniform float voidWorld,worldMaterial,waterY,preservePlatform,shadowAmount,twinPart,joiningStone;
out vec4 finalColor;
float mist(vec3 p){
    float flow=.55+.22*sin(p.x*.065+p.z*.073-time*.07)+.17*sin(p.z*.16-p.x*.09+time*.035);
    return mix(.0055+.052*exp(-max(0.,p.y)*.46)*max(.16,flow),.0095+.012*exp(-max(0.,p.y-waterY)*.40)*max(.16,flow),voidWorld);
}
vec3 fogColour(){return mix(mix(vec3(.175,.235,.248),vec3(.39,.455,.45),inspection),vec3(.165,.180,.180),voidWorld);}
float fogAmount(vec3 a,vec3 b){
    float density=0.;
    for(int i=0;i<7;i++)density+=mist(mix(a,b,(float(i)+.5)/7.));
    return 1.-exp(-length(a-b)*density/7.);
}
vec3 tile(vec2 uv,float index){
    vec2 base=vec2(mod(index,4.)*.25+.0645,floor(index/4.)*.25+.0645);
    // Stable mip selection across mirrored-repeat seams.
    return textureGrad(texture0,base+abs(fract(uv*.5)*2.-1.)*.121,dFdx(uv)*.121,dFdy(uv)*.121).rgb;
}
vec3 stoneTile(sampler2D atlas,vec2 uv,float index){
    vec2 base=vec2(mod(index,4.)*.25+.0645,floor(index/4.)*.25+.0645);
    return textureGrad(atlas,base+abs(fract(uv*.5)*2.-1.)*.121,dFdx(uv)*.121,dFdy(uv)*.121).rgb;
}
vec3 stoneSurface(sampler2D atlas,vec3 p,vec3 n,float index,float scale){
    vec3 w=pow(abs(n),vec3(4.));w/=max(.001,w.x+w.y+w.z);
    return stoneTile(atlas,p.zy*scale,index)*w.x+stoneTile(atlas,p.xz*scale,index)*w.y+stoneTile(atlas,p.xy*scale,index)*w.z;
}
void main(){
    vec4 tex=texture(texture0,fragTexCoord)*colDiffuse;
    float alphaCut=surfaceKind>2.5?mix(.32,.11,smoothstep(18.,90.,length(worldPosition-eyePosition))):.36;
    if(tex.a<alphaCut)discard;
    vec3 p=worldPosition,n=normalize(worldNormal);if(reflectionPass<.5&&!gl_FrontFacing)n=-n;
    if(reflectionPass>.5){if(p.y>waterY+.02)discard;p.y=2.*waterY-p.y;n.y=-n.y;}
    // The pavilion, its lamps and first twelve metres of path are an exact
    // twin. The remote shore and the rest of the old causeway leave together.
    if(twinPart>.5&&enclosed>.5&&p.z>12.)discard;
    if(twinPart>.5&&surfaceKind>.5&&surfaceKind<1.5){
        // The original causeway slightly overlaps the pavilion's hexagon.
        // Give the shared deck one owner instead of two coplanar surfaces.
        float hex=-100.;
        for(int i=0;i<6;i++){float a=(float(i)+.5)*1.04719755;hex=max(hex,dot(p.xz,vec2(cos(a),sin(a))));}
        if(hex<6.2353829)discard;
    }
    if(worldMaterial>.5){
        // Repeat the authored 128px material at a physical scale, independent
        // of how large a modular wall or pavement face happens to be.
        vec2 cell=floor(fragTexCoord*4.)/4.;float index=floor(fragTexCoord.x*4.)+floor(fragTexCoord.y*4.)*4.;
        float scale=index>11.5&&index<12.5?.19:(index<.5||index>13.5&&index<14.5?.48:.68);
        vec3 w=pow(abs(n),vec3(6.));w/=max(.001,w.x+w.y+w.z);
        vec2 a=abs(fract(p.zy*scale*.5)*2.-1.),b=abs(fract(p.xz*scale*.5)*2.-1.),c=abs(fract(p.xy*scale*.5)*2.-1.);
        tex.rgb=textureGrad(texture0,cell+.0645+a*.121,dFdx(p.zy)*scale*.121,dFdy(p.zy)*scale*.121).rgb*w.x+
                textureGrad(texture0,cell+.0645+b*.121,dFdx(p.xz)*scale*.121,dFdy(p.xz)*scale*.121).rgb*w.y+
                textureGrad(texture0,cell+.0645+c*.121,dFdx(p.xy)*scale*.121,dFdy(p.xy)*scale*.121).rgb*w.z;
        float damp=1.-smoothstep(waterY-.1,waterY+1.1+.24*sin(p.x*.9+p.z*.5),p.y);
        tex.rgb*=1.-damp*.48;
    }
    // Millimetre-high decorative slab lips become subpixel black/white dashes
    // at game resolution. Use the continuous floor beneath, with filtered joints.
    if(flatPaving>.5&&p.y>deckHeight+.00001)discard;
    if(surfaceKind>5.5&&surfaceKind<6.5&&p.z<10.&&p.y>deckHeight+3.55)discard;
    if(surfaceKind>.5&&surfaceKind<1.5){
        vec3 w=pow(abs(n),vec3(4.));w/=max(.001,w.x+w.y+w.z);
        tex.rgb=tile(p.zy*.7,2.)*w.x+tile(p.xz*.7,2.)*w.y+tile(p.xy*.7,2.)*w.z;
        tex.rgb*=.82+.18*smoothstep(-.15,.75,p.y);
        float damp=1.-smoothstep(-.03,.30,p.y);tex.rgb=mix(tex.rgb,tex.rgb*vec3(.56,.69,.54),damp*.7);
        if(flatPaving>.5&&n.y>.8&&abs(p.y-deckHeight)<.002){
            vec2 cell=fract(p.xz+.5),edge=min(cell,1.-cell);
            float width=max(.001,max(fwidth(p.x),fwidth(p.z)));
            float joint=1.-smoothstep(.010-width*.5,.014+width*.5,min(edge.x,edge.y));
            tex.rgb*=1.-.23*joint*min(1.,.024/width);
        }
    }
    if(surfaceKind>1.5&&surfaceKind<2.5)tex.rgb=mix(vec3(.075,.10,.085),vec3(.20,.235,.19),max(0.,n.y));
    if(surfaceKind>3.5&&surfaceKind<4.5){
        float patch=.5+.24*sin(p.x*.81+p.z*.35)+.17*sin(p.x*1.9-p.z*.73);
        vec3 earth=tile(p.xz*.42,4.)*vec3(.69,.60,.49),moss=tile(p.xz*.36,5.)*vec3(.63,.78,.57);
        tex.rgb=mix(earth,moss,smoothstep(.25,.75,patch));
        tex.rgb*=mix(.58,1.,smoothstep(-.05,.42,p.y));
    }
    if(joiningStone>.5&&enclosed>.5&&p.z>7.5&&p.z<19.&&abs(p.x)<5.){
        // One physical mapping on both sides of the mesh join. The pale lake
        // stone gradually acquires the canal's worn joints and darker masonry.
        vec3 oldStone=joiningStone>1.5?stoneSurface(texture0,p,n,2.,.7):stoneSurface(otherStone,p,n,2.,.7);
        oldStone*=.82+.18*smoothstep(-.15,.75,p.y);
        oldStone=mix(oldStone,oldStone*vec3(.56,.69,.54),(1.-smoothstep(-.03,.30,p.y))*.7);
        float index=abs(n.y)>.7?2.:13.;
        vec3 newStone=joiningStone>1.5?stoneSurface(otherStone,p,n,index,.68):stoneSurface(texture0,p,n,index,.68);
        float damp=1.-smoothstep(waterY-.1,waterY+1.1+.24*sin(p.x*.9+p.z*.5),p.y);
        newStone*=1.-damp*.48;
        float wear=.24*sin(p.x*2.1+p.z*.65)+.16*sin(p.x*.7-p.z*1.8);
        float blend=smoothstep(8.,17.,p.z+wear);
        float boundary=(1.-smoothstep(3.5,5.,abs(p.x)))*smoothstep(7.5,8.,p.z)*(1.-smoothstep(18.,19.,p.z));
        tex.rgb=mix(tex.rgb,mix(oldStone,newStone,blend),boundary);
    }
    float underRoof=(length(p.xz)<5.45&&p.y<deckHeight+4.85)? .2:1.;
    vec3 light=mix(vec3(.37,.41,.42),vec3(.70,.73,.66),inspection);
    light=mix(light,vec3(.49,.515,.50)+max(0.,dot(n,normalize(vec3(-.7,.8,.25))))*vec3(.24,.25,.24),voidWorld);
    if(surfaceKind>4.5&&surfaceKind<5.5){
        vec3 v=normalize(eyePosition-worldPosition);float polish=pow(max(0.,dot(reflect(-normalize(vec3(.62,.25,-.74)),n),v)),22.);
        tex.rgb=vec3(.34,.38,.32)+vec3(.19,.22,.20)*max(0.,n.y)+polish*.32;
    }
    if(surfaceKind>7.5){float patina=.5+.5*sin(p.y*22.+p.x*9.)*sin(p.z*35.+p.y*6.);tex.rgb=tex.rgb*.38+vec3(.025,.075,.055)*patina;}
    float inside=(abs(p.x)<12.4&&abs(p.z)<6.2&&p.y>deckHeight-.10&&p.y<8.0)?warmth:0.;
    light=mix(light,mix(vec3(.22,.24,.23),vec3(.42,.43,.37),inspection),inside);
    underRoof=mix(underRoof,.14,inside);
    light+=mix(vec3(.26,.34,.39),vec3(.27,.30,.24),inspection)*max(0.,dot(n,normalize(vec3(-.5,.72,.3))))*underRoof*(1.-voidWorld);
    for(int i=0;i<16;i++){
        if(i>=lampCount)break;vec3 d=lamps[i]-p;float dist=length(d);
        float fall=pow(max(0.,1.-dist/9.),1.4)/(1.+dist*dist*.13);
        if((p.y<4.11&&lamps[i].y>4.5)||(p.y>4.14&&lamps[i].y<4.1))fall*=mix(1.,.05,warmth);
        fall*=i<3?1.-warmth:(i>=5?warmth:1.);
        if(surfaceKind>6.5&&surfaceKind<7.5)fall*=.035;
        light+=vec3(2.25,1.55,.72)*fall*(.27+.73*max(0.,dot(n,normalize(d))));
    }
    // Rooms and deep awning soffits are separate, genuinely hollow geometry.
    // Their occluded skylight is deliberately almost absent; open shutters
    // silhouette against that depth, rather than a painted black window tile.
    if(worldMaterial>.5)light=mix(light,vec3(.018,.021,.023),shadowAmount);
    vec3 colour=tex.rgb*light;
    colour=mix(colour,tex.rgb*1.15+vec3(.16,.05,.002),emission);
    colour=mix(colour,vec3(dot(colour,vec3(.299,.587,.114))),voidWorld*.65);
    vec3 eye=eyePosition;if(reflectionPass>.5)eye.y=2.*waterY-eye.y;
    float fog=fogAmount(eye,p);if(reflectionPass>.5)fog*=.77;
    colour=mix(colour,fogColour(),fog);
    // Surviving paper-lamp texels are opaque. Fractional atlas alpha otherwise
    // blends hidden background into a foreground depth sample at the swap.
    finalColor=vec4(colour,(surfaceKind>2.5||emission>.5?1.:tex.a)*opacity);
}
