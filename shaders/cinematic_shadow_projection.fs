#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec3 shadowColor;
uniform float shadowOpacity;
uniform float alphaCutoff;

out vec4 finalColor;

void main()
{
    float sampledAlpha = texture(texture0, fragTexCoord).a;

    if (sampledAlpha <= alphaCutoff)
    {
        discard;
    }

    finalColor = vec4(shadowColor, sampledAlpha * shadowOpacity);
}
