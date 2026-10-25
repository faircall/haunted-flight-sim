// BEGIN CONDENSE
// Shared by the fog and material shaders. Keep this block identical in both:
// the wall texture must emerge exactly where the local inward pull arrives.
float condenseEase(float a,float b,float value){
    float t=clamp((value-a)/max(.0001,b-a),0.,1.);
    return t*t*t*(10.+t*(-15.+6.*t));
}
float condenseHash(vec3 p){
    p=fract(p*.1031);p+=dot(p,p.yzx+33.33);
    return fract((p.x+p.y)*p.z);
}
float condenseNoise(vec3 p){
    vec3 cell=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(mix(condenseHash(cell),condenseHash(cell+vec3(1,0,0)),f.x),
                   mix(condenseHash(cell+vec3(0,1,0)),condenseHash(cell+vec3(1,1,0)),f.x),f.y),
               mix(mix(condenseHash(cell+vec3(0,0,1)),condenseHash(cell+vec3(1,0,1)),f.x),
                   mix(condenseHash(cell+vec3(0,1,1)),condenseHash(cell+vec3(1,1,1)),f.x),f.y),f.z);
}
// x: tightening; y: physical inward pull; z: lingering wisps; w: real material.
vec4 condensePhases(vec3 anchor,vec2 window,float now,float holdFraction,
                    float seconds,float size,float pattern){
    float span=max(.1,window.y-window.x);
    float starts=window.x+span*holdFraction;
    float duration=min(seconds,span*(1.-holdFraction)*.55);
    duration=max(.0001,duration);
    // A fixed 3D pattern staggers small parts of the same facade. It never
    // scrolls back over a revealed surface, or changes when the camera moves.
    float delay=condenseNoise(anchor/max(.3,size)+vec3(7.1,13.7,3.9))*duration*.35*pattern;
    starts+=delay;
    float ends=starts+duration;
    float raw=clamp((now-starts)/duration,0.,1.);
    // Long pulls should use their full duration, rather than reserving most
    // visible material emergence for a short central burst.
    float patient=condenseEase(3.,6.,duration);
    float pull=mix(condenseEase(0.,1.,raw),raw*raw*(3.-2.*raw),patient);
    float material=mix(condenseEase(.18,.84,raw),condenseEase(.03,.97,raw),patient);
    return vec4(condenseEase(window.x,starts,now),pull,
                1.-condenseEase(ends,window.y,now),material);
}
// END CONDENSE
