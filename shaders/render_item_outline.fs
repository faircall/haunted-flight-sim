#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;
uniform vec4 outlineColor;
uniform float outlineWidth;

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
    finalColor = vec4(outlineColor.rgb, outlineColor.a * edge) * fragColor;
}
