#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;
uniform vec4 outlineColor;
uniform float outlineWidth;
uniform float darknessEnabled;
uniform sampler2D sceneTexture;
uniform vec4 sampleRect;
uniform vec2 darknessRange;

out vec4 finalColor;

void main()
{
    vec2 texel = outlineWidth / resolution;
    float center = texture(texture0, fragTexCoord).a;
    float expanded = 0.0;
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(texel.x, 0.0)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(-texel.x, 0.0)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(0.0, texel.y)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(0.0, -texel.y)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(texel.x, texel.y)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(-texel.x, texel.y)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(texel.x, -texel.y)).a);
    expanded = max(expanded, texture(texture0, fragTexCoord + vec2(-texel.x, -texel.y)).a);
    float edge = max(expanded - center, 0.0);
    if (edge <= 0.0) discard;
    if (darknessEnabled > .5) {
        // Read actual rendered player brightness, including colored lights/fog.
        // A fixed small grid is evaluated only at outline fragments; no CPU readback.
        float sum = 0.0;
        float weight = 0.0;
        for (int y=0;y<8;y++) for (int x=0;x<8;x++) {
            vec2 pixel = sampleRect.xy + (vec2(x,y)+.5)/8.0*sampleRect.zw;
            vec2 uv = vec2(pixel.x/resolution.x,1.0-pixel.y/resolution.y);
            if (any(lessThan(uv,vec2(0.))) || any(greaterThan(uv,vec2(1.)))) continue;
            float a = texture(texture0,uv).a;
            sum += dot(texture(sceneTexture,uv).rgb,vec3(.2126,.7152,.0722))*a;
            weight += a;
        }
        float brightness = sum/max(weight,.0001);
        edge *= 1.0-smoothstep(darknessRange.x,darknessRange.y,brightness);
    }
    finalColor = vec4(outlineColor.rgb, outlineColor.a * edge) * fragColor;
}
