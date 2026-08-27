#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform vec2 resolution;
uniform vec2 areaMin;
uniform vec2 areaMax;
uniform int shapeType;
uniform float edgeSoftness;
uniform float strength;

out vec4 finalColor;

float rectangleSignedDistance(vec2 point, vec2 centre, vec2 halfSize)
{
    vec2 offset = abs(point - centre) - halfSize;
    return length(max(offset, 0.0)) + min(max(offset.x, offset.y), 0.0);
}

float ellipseSignedDistance(vec2 point, vec2 centre, vec2 halfSize)
{
    vec2 safeHalfSize = max(halfSize, vec2(0.0001));
    vec2 normalizedPoint = (point - centre) / safeHalfSize;
    return (length(normalizedPoint) - 1.0) * min(safeHalfSize.x, safeHalfSize.y);
}

void main()
{
    vec2 pixelPosition = vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y);
    vec2 areaCentre = (areaMin + areaMax) * 0.5;
    vec2 areaHalfSize = max((areaMax - areaMin) * 0.5, vec2(0.0));
    float signedDistance;

    if (shapeType == 1)
    {
        signedDistance = ellipseSignedDistance(pixelPosition, areaCentre, areaHalfSize);
    }
    else
    {
        signedDistance = rectangleSignedDistance(pixelPosition, areaCentre, areaHalfSize);
    }

    float maximumSoftness = max(min(areaHalfSize.x, areaHalfSize.y), 0.0001);
    float softness = max(min(edgeSoftness, maximumSoftness), 0.0001);
    float maskAmount = (1.0 - smoothstep(-softness, 0.0, signedDistance)) * max(strength, 0.0);

    if (maskAmount <= 0.0)
    {
        discard;
    }

    finalColor = vec4(vec3(maskAmount), 1.0);
}
