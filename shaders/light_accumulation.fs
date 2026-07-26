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
uniform float innerConeCos;
uniform float outerConeCos;

uniform int lightType;

out vec4 finalColor;

void main()
{
    // gl_FragCoord uses bottom-left as its origin.
    // The game uses top-left, so invert Y.
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

    // 0 = point light
    // 1 = spot light
    if (lightType == 1 && distanceFromLight > 0.0)
    {
        vec2 directionToPixel = fromLight / distanceFromLight;
        float alignment = dot(directionToPixel, normalize(lightDirection));

        coneStrength = smoothstep(outerConeCos, innerConeCos, alignment);
    }

    float strength = radialStrength * coneStrength * intensity;

    // Additive blending uses this RGB contribution.
    // Alpha stays at 1 so strength is not accidentally applied twice.
    finalColor = vec4(lightColor * strength, 1.0);
}