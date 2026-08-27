#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform vec2 resolution;
uniform vec2 areaMin;
uniform vec2 areaMax;
uniform vec3 lightColor;
uniform float intensity;
uniform float edgeSoftness;

out vec4 finalColor;

float rectangleSignedDistance(vec2 point, vec2 centre, vec2 halfSize)
{
    vec2 offset = abs(point - centre) - halfSize;
    return length(max(offset, 0.0)) + min(max(offset.x, offset.y), 0.0);
}

void main()
{
    vec2 pixelPosition = vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y);
    vec2 areaCentre = (areaMin + areaMax) * 0.5;
    vec2 areaHalfSize = max((areaMax - areaMin) * 0.5, vec2(0.0));
    float signedDistance = rectangleSignedDistance(pixelPosition, areaCentre, areaHalfSize);
    float softness = max(edgeSoftness, 0.0001);
    float strength = 1.0 - smoothstep(-softness, 0.0, signedDistance);

    if (strength <= 0.0)
    {
        discard;
    }

    finalColor = vec4(lightColor * intensity * strength, 1.0);
}
