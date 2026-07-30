#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D lightTexture;
uniform sampler2D readabilityLightTexture;

uniform vec3 ambientColor;
uniform vec3 shadowColor;

uniform float ambientStrength;
uniform float directLightStrength;
uniform float blackPoint;
uniform float shadowSoftness;
uniform float shadowDetail;
uniform float contrast;
uniform float lightPosterizeEnabled;
uniform float lightPosterizeLevels;
uniform float lightDitherEnabled;
uniform float lightDitherStrength;
uniform float posterizeAmbient;

out vec4 finalColor;

float maxChannel(vec3 value)
{
    return max(value.r, max(value.g, value.b));
}

vec3 applyContrast(vec3 color, float amount)
{
    return clamp((color - 0.5) * amount + 0.5, 0.0, 1.0);
}

float posterizeScalar(float value, float levels)
{
    float levelCount = max(floor(levels + 0.5), 2.0);
    float stepCount = levelCount - 1.0;
    return floor(clamp(value, 0.0, 1.0) * stepCount + 0.5) / stepCount;
}

vec3 posterizeVec3(vec3 color, float levels)
{
    return vec3(
        posterizeScalar(color.r, levels),
        posterizeScalar(color.g, levels),
        posterizeScalar(color.b, levels)
    );
}

float bayer4x4(vec2 screenPosition)
{
    const float matrix[16] = float[16](
         0.0,  8.0,  2.0, 10.0,
        12.0,  4.0, 14.0,  6.0,
         3.0, 11.0,  1.0,  9.0,
        15.0,  7.0, 13.0,  5.0
    );
    ivec2 pixel = ivec2(mod(floor(screenPosition), 4.0));
    return (matrix[pixel.y * 4 + pixel.x] + 0.5) / 16.0;
}

float posterizeScalarDithered(float value, float levels, vec2 screenPosition, float strength)
{
    float levelCount = max(floor(levels + 0.5), 2.0);
    float stepCount = levelCount - 1.0;
    float thresholdOffset = (bayer4x4(screenPosition) - 0.5) * max(strength, 0.0) / stepCount;
    return posterizeScalar(value + thresholdOffset, levelCount);
}

vec3 posterizeVec3Dithered(vec3 color, float levels, vec2 screenPosition, float strength)
{
    return vec3(
        posterizeScalarDithered(color.r, levels, screenPosition, strength),
        posterizeScalarDithered(color.g, levels, screenPosition, strength),
        posterizeScalarDithered(color.b, levels, screenPosition, strength)
    );
}

vec3 posterizeLighting(vec3 color)
{
    if (lightDitherEnabled > 0.5)
    {
        return posterizeVec3Dithered(color, lightPosterizeLevels, gl_FragCoord.xy, lightDitherStrength);
    }

    return posterizeVec3(color, lightPosterizeLevels);
}

void main()
{
    vec4 sceneSample = texture(texture0, fragTexCoord);
    vec3 worldDirectLight = texture(lightTexture, fragTexCoord).rgb * directLightStrength;
    vec3 readabilityLight = texture(readabilityLightTexture, fragTexCoord).rgb * directLightStrength;
    // vec3 directLight = texture(lightTexture, vec2(fragTexCoord.x, 1.0 - fragTexCoord.y)).rgb * directLightStrength;

    vec3 ambientLight = ambientColor * ambientStrength;
    vec3 totalLight;

    if (lightPosterizeEnabled > 0.5)
    {
        if (posterizeAmbient > 0.5)
        {
            totalLight = posterizeLighting(ambientLight + worldDirectLight) + readabilityLight;
        }
        else
        {
            worldDirectLight = posterizeLighting(worldDirectLight);
            totalLight = ambientLight + worldDirectLight + readabilityLight;
        }
    }
    else
    {
        totalLight = ambientLight + worldDirectLight + readabilityLight;
    }

    vec3 litScene = sceneSample.rgb * totalLight;
    litScene = applyContrast(litScene, contrast);

    float lightAmount = maxChannel(totalLight);
    float softness = max(shadowSoftness, 0.000001);
    float visibility = smoothstep(blackPoint, blackPoint + softness, lightAmount);

    // shadowDetail = 0:
    //     completely flat, solid darkness
    //
    // shadowDetail = 1:
    //     retain some scene texture inside darkness
    vec3 detailedShadow = sceneSample.rgb * shadowColor;
    vec3 darkness = mix(shadowColor, detailedShadow, shadowDetail);

    vec3 result = mix(darkness, litScene, visibility);

    finalColor = vec4(result, sceneSample.a);
}
