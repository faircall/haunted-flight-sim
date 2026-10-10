#version 330
in vec2 fragTexCoord;
in vec3 worldPosition;
in vec3 worldNormal;
in vec4 fragColor;
uniform sampler2D texture0;
uniform float time;
uniform float windshield;
uniform vec2 wiperClock;
uniform vec2 wiperPivots;
uniform vec4 wiperPlane; // pivot YZ and normalized up vector YZ
uniform vec4 wiperRange; // blade inner/outer radius, parked angle, sweep
uniform vec3 carFrame;
uniform float dusk;
out vec4 finalColor;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float clean(vec2 point,float pivot) {
    vec2 d=point-vec2(pivot,0.);
    float r=length(d);float a=atan(d.y,d.x);
    float sector=step(wiperRange.z,a)*step(a,wiperRange.z+wiperRange.w);
    sector*=smoothstep(wiperRange.x-.008,wiperRange.x+.003,r)*(1.-smoothstep(wiperRange.y-.003,wiperRange.y+.008,r));
    // Time since the blade last crossed this point. Water gradually returns,
    // instead of the whole wiped fan popping on/off at each reversal.
    float phase=wiperClock.x;
    float outward=acos(clamp(1.-2.*(a-wiperRange.z)/wiperRange.w,-1.,1.))/6.2831853;
    float age=min(fract(phase-outward),fract(phase-(1.-outward)))*wiperClock.y;
    return sector*exp(-age*1.15);
}
void main() {
    vec2 uv=fragTexCoord;
    float speed=.45+hash(vec2(floor(uv.x*23.),2.))*.65;
    vec2 grid=vec2(uv.x*23.,uv.y*15.+time*speed);
    vec2 cell=floor(grid);vec2 q=fract(grid)-.5;
    q-=vec2(hash(cell)-.5,hash(cell+19.)-.5)*.6;
    float head=1.-smoothstep(.06,.15,length(q*vec2(1.4,1.)));
    float edge=1.-smoothstep(.014,.035,abs(length(q*vec2(1.4,1.))-.13));
    float tail=(1.-smoothstep(.012,.035,abs(q.x)))*smoothstep(.06,.14,q.y)*(1.-smoothstep(.25,.58,q.y));
    float column=floor(uv.x*11.);
    float rivuletX=fract(uv.x*11.)-(.25+hash(vec2(column,8.))*.5);
    rivuletX-=sin(uv.y*19.+hash(vec2(column,1.))*6.28)*.047;
    float flow=fract(uv.y*.75+time*(.028+hash(vec2(column,7.))*.025));
    float rivulet=(1.-smoothstep(.012,.030,abs(rivuletX)))*step(.54,hash(vec2(column,4.)));
    rivulet*=smoothstep(.05,.14,flow)*(1.-smoothstep(.68,.81,flow));
    float wet=1.;
    if(windshield>.5) {
        vec3 car=vec3(worldPosition.x,(worldPosition.y-carFrame.x)*carFrame.y+worldPosition.z*carFrame.z,
                     -(worldPosition.y-carFrame.x)*carFrame.z+worldPosition.z*carFrame.y);
        vec2 point=vec2(car.x,dot(car.yz-wiperPlane.xy,wiperPlane.zw));
        wet=1.-.94*max(clean(point,wiperPivots.x),clean(point,wiperPivots.y));
    }
    head*=wet;edge*=wet;tail*=wet;rivulet*=wet;
    vec2 screen=gl_FragCoord.xy/vec2(480.,270.);
    vec2 refract=vec2(q.x*.017,-.004)*head+vec2(rivulet*.0015,0.);
    vec3 scene=texture(texture0,clamp(screen+refract,vec2(.002),vec2(.998))).rgb;
    vec3 reflection=mix(vec3(.55,.61,.58),vec3(.24,.31,.35),dusk);
    vec3 colour=mix(scene,reflection,.16)+vec3(edge*.14+tail*.065+rivulet*.07);
    float alpha=.075+head*.48+edge*.22+tail*.15+rivulet*.19;
    finalColor=vec4(colour,min(.65,alpha));
}
