#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform vec2 resolution;
uniform vec2 lightPosition;
uniform vec2 lightDirection;
uniform vec3 lightColor;

uniform float radius;
uniform float intensity;
uniform float falloff;
uniform float nearFadeDistance;
uniform float innerConeCos;
uniform float outerConeCos;

uniform int lightType;

out vec4 finalColor;

void main()
{
    vec2 pixelPosition = vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y);
    vec2 fromLight = pixelPosition - lightPosition;

    float distanceFromLight = length(fromLight);

    if (distanceFromLight >= radius)
    {
        discard;
    }

    float radialStrength = 1.0 - distanceFromLight / radius;
    radialStrength = pow(clamp(radialStrength, 0.0, 1.0), max(falloff, 0.0001));

    float coneStrength = 1.0;

    if (lightType == 1 && distanceFromLight > 0.0)
    {
        vec2 directionToPixel = fromLight / distanceFromLight;
        float alignment = dot(directionToPixel, normalize(lightDirection));
        coneStrength = smoothstep(outerConeCos, innerConeCos, alignment);
    }

    float nearStrength = 1.0;

    if (nearFadeDistance > 0.0)
    {
        nearStrength = smoothstep(0.0, nearFadeDistance, distanceFromLight);
    }

    float strength = radialStrength * coneStrength * nearStrength * intensity;

    finalColor = vec4(lightColor * strength, 1.0);
}