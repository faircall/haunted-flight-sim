#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform vec2 resolution;
out vec4 finalColor;
void main() {
    vec2 uv=fragTexCoord;vec3 c=texture(texture0,uv).rgb,bloom=vec3(0.);
    for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++) {
        vec3 sampleColour=texture(texture0,uv+vec2(x,y)*2./resolution).rgb;
        bloom+=max(sampleColour-vec3(.74),vec3(0.))/25.;
    }
    c+=bloom*.24;
    vec2 q=uv*2.-1.;float vignette=1.-.095*dot(q,q);
    c=pow(max(c,vec3(0.)),vec3(.94))*vignette;
    finalColor=vec4(c,1.);
}
