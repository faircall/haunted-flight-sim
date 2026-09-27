// Shared scalar modulation BEFORE lighting posterization. Never offset the
// visibility/shadow sample, or add illumination where the field is zero.
uniform sampler2D fireNoise;
uniform vec4 firePattern; // strength, inverse scale, seeded noise offset xy
uniform vec3 fireWorld;   // snapped camera xy, target height
uniform vec2 fireMotion; // amount, evolution phase

vec3 fireLattice(vec2 p) {
    vec2 f=fract(p);
    f=f*f*(3.-2.*f);
    return texture(fireNoise,(floor(p)+f+.5)/128.).rgb*2.-1.;
}

float fireContourStrength(float strength) {
    if(firePattern.x<=0. || strength<=0.) return strength;
    vec2 pixel=floor(vec2(gl_FragCoord.x,fireWorld.z-gl_FragCoord.y))+.5;
    vec2 p=(pixel+fireWorld.xy)*firePattern.y;
    vec3 a=fireLattice(p+firePattern.zw);
    vec3 b=fireLattice(p*2.23+firePattern.zw+vec2(17.,39.));
    vec3 c=fireLattice(p*5.17+firePattern.zw+vec2(71.,13.));
    float shape=.58*a.r+.28*b.r+.14*c.r;
    float steady=strength*max(0.,1.+firePattern.x*shape);
    // Different spatial fields and phases at each scale morph the inner band
    // boundaries. No common brightness pulse, expansion, or scrolling texture.
    vec3 phase=fireMotion.y*vec3(.71,1.03,1.43)+firePattern.z*.21+vec3(0.,2.1,4.2);
    float evolving=.7071068*dot(vec3(.58,.28,.14),
        vec3(a.g,b.g,c.g)*cos(phase)+vec3(a.b,b.b,c.b)*sin(phase));
    // Preserve the dim outer footprint, including its static irregular shape.
    // Animated pixels cannot cross this floor into the unlit band. This works
    // on irradiance rather than distance, so cached wall/window fields agree.
    const float edgeFloor=.10;
    float interior=smoothstep(edgeFloor,.32,steady);
    float amplitude=min(max(0.,steady-edgeFloor),strength*firePattern.x*fireMotion.x);
    return steady+interior*amplitude*evolving;
}
