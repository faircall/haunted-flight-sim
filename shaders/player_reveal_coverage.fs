#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
uniform sampler2D playerMask;
uniform sampler2D previousState;
uniform vec2 resolution;
uniform vec4 playerRect;
uniform float frameDelta;
uniform vec2 fadeTimes;
uniform vec2 coverageRange;
out vec4 finalColor;
void main() {
    float covered=0.0, total=0.0;
    // One fragment per blocker, no CPU readback. The grid resolves the native
    // 32px animated player, including alpha holes in leaves and window panels.
    for (int y=0;y<32;y++) for (int x=0;x<32;x++) {
        vec2 pixel=playerRect.xy+(vec2(x,y)+0.5)/32.0*playerRect.zw;
        vec2 uv=vec2(pixel.x/resolution.x,1.0-pixel.y/resolution.y);
        if (any(lessThan(uv,vec2(0.0))) || any(greaterThanEqual(uv,vec2(1.0)))) continue;
        float body=texture(playerMask,uv).a;
        total+=body;
        covered+=body*texture(texture0,uv).a;
    }
    float coverage=covered/max(total,0.00001);
    float target=smoothstep(coverageRange.x,coverageRange.y,coverage);
    float previous=texture(previousState,vec2(0.5)).r;
    float step=frameDelta/max(target>previous?fadeTimes.x:fadeTimes.y,0.001);
    float value=target>previous?min(target,previous+step):max(target,previous-step);
    finalColor=vec4(value,coverage,target,1.0);
}
