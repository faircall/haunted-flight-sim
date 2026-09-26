#version 330
uniform vec2 resolution, camera, lightPosition, lightDirection;
uniform vec3 lightColor;
uniform float radius, intensity, falloff, nearFadeDistance, innerConeCos, outerConeCos, lightHeight;
uniform vec4 panel;
uniform sampler2D holesTexture, columnTexture;
out vec4 finalColor;
void main() {
    vec2 world=vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y)+camera;
    vec2 ray=world-lightPosition;
    if(abs(ray.y)<.001)discard;
    float amount=(panel.y-lightPosition.y)/ray.y;
    if(amount<=0.0 || amount>=1.0)discard;
    vec2 hole=vec2(lightPosition.x+ray.x*amount-panel.x, panel.w-lightHeight*(1.0-amount));
    if(hole.x<0.0 || hole.y<0.0 || hole.x>=panel.z || hole.y>=panel.w)discard;
    vec2 uv=(floor(hole)+.5)/panel.zw;
    if(texture(holesTexture,uv).r<.5 || texture(columnTexture,vec2(uv.x,.5)).r<.5)discard;
    float distance=length(ray);
    float cone=smoothstep(outerConeCos,innerConeCos,dot(ray/max(.001,distance),normalize(lightDirection)));
    float near=nearFadeDistance>0.0?smoothstep(0.0,nearFadeDistance,distance):1.0;
    float strength=pow(clamp(1.0-distance/radius,0.0,1.0),falloff)*cone*near*intensity;
    finalColor=vec4(lightColor*strength,1.0);
}
