#version 330
uniform vec3 forward,right,up,fogColour;
uniform vec4 lens; // tangent half-FOV, aspect, width, height
uniform vec4 worldFrame;
uniform float time,dusk;
out vec4 finalColor;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);}
float fbm(vec2 p){float v=0.,w=.54;for(int i=0;i<5;i++){v+=noise(p)*w;p=mat2(1.6,-1.2,1.2,1.6)*p+13.7;w*=.48;}return v;}
void main(){
    vec2 uv=gl_FragCoord.xy/lens.zw*2.-1.;
    vec3 ray=normalize(forward+right*uv.x*lens.x*lens.y+up*uv.y*lens.x);
    vec2 direction=vec2(ray.x*worldFrame.z-ray.z*worldFrame.w,ray.x*worldFrame.w+ray.z*worldFrame.z);
    vec2 p=direction/max(.065,ray.y)*1.3+vec2(worldFrame.x,-worldFrame.y)*.0006;
    p+=vec2(time*.004,-time*.002);
    float broad=fbm(p*.72),scud=fbm(p*2.8+vec2(time*.013,0));
    float billow=smoothstep(.18,.82,broad*.78+scud*.22);
    vec3 cloud=mix(vec3(.24,.29,.285),vec3(.61,.66,.625),billow);
    cloud-=vec3(.095,.10,.085)*smoothstep(.48,.70,scud)*(1.-billow*.4);
    cloud=mix(cloud,mix(vec3(.020,.029,.040),vec3(.075,.088,.103),billow),dusk);
    vec3 colour=mix(fogColour,cloud,smoothstep(-.01,.31,ray.y));
    float dither=(hash(gl_FragCoord.xy)-.5)/255.;
    finalColor=vec4(floor(clamp(colour+dither,0.,1.)*127.+.5)/127.,1);
}
