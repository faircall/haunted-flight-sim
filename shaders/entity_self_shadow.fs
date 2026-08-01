#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D entityLightTexture;
uniform sampler2D entityReadabilityLightTexture;
uniform sampler2D directionalResponseTexture;
uniform vec2 resolution;
uniform vec2 sourceUvMin;
uniform vec2 sourceUvMax;
uniform vec4 faceExposure;
uniform float omniExposure;
uniform float worldOcclusionScale;
uniform int selfShadowMode;
uniform float selfShadowStrength;
uniform float selfShadowSoftness;
uniform float selfShadowBackFill;
uniform float selfShadowMinimumDirect;
uniform int profileDividerEnabled;
uniform vec2 profileDividerTop;
uniform vec2 profileDividerBottom;
uniform vec2 profileLightOrigin;
uniform int selfShadowDebugOutput;
uniform int selfShadowPass;
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

float posterizeScalar(float value, float levels)
{
    float levelCount = max(floor(levels + 0.5), 2.0);
    float stepCount = levelCount - 1.0;
    return floor(clamp(value, 0.0, 1.0) * stepCount + 0.5) / stepCount;
}

float bayer4x4(vec2 screenPosition)
{
    const float matrix[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
    ivec2 pixel = ivec2(mod(floor(screenPosition), 4.0));
    return (matrix[pixel.y * 4 + pixel.x] + 0.5) / 16.0;
}

vec3 posterizeLighting(vec3 color)
{
    float levels = max(floor(lightPosterizeLevels + 0.5), 2.0);
    float stepCount = levels - 1.0;
    float offset = lightDitherEnabled > 0.5 ? (bayer4x4(gl_FragCoord.xy) - 0.5) * max(lightDitherStrength, 0.0) / stepCount : 0.0;
    return vec3(posterizeScalar(color.r + offset, levels), posterizeScalar(color.g + offset, levels), posterizeScalar(color.b + offset, levels));
}

float calculateUprightBoxSelfShadow(vec2 localUv)
{
    float softness = clamp(selfShadowSoftness, 0.001, 0.49);
    float rightMask = smoothstep(0.5 - softness, 0.5 + softness, localUv.x);
    float leftMask = 1.0 - rightMask;
    float front = faceExposure.x;
    float back = faceExposure.y * clamp(selfShadowBackFill, 0.0, 1.0);
    float sides = faceExposure.z * leftMask + faceExposure.w * rightMask;
    float shapedExposure = clamp(omniExposure + front + back + sides, 0.0, 1.0);
    return mix(1.0, shapedExposure, clamp(selfShadowStrength, 0.0, 1.0));
}

float cross2d(vec2 first, vec2 second)
{
    return first.x * second.y - first.y * second.x;
}

float calculateProfileDividerVisibility(vec2 localUv)
{
    if (profileDividerEnabled == 0)
    {
        return 1.0;
    }

    vec2 lightRay = localUv - profileLightOrigin;
    vec2 divider = profileDividerBottom - profileDividerTop;
    float denominator = cross2d(lightRay, divider);

    if (abs(denominator) <= 0.000001)
    {
        return 1.0;
    }

    vec2 offset = profileDividerTop - profileLightOrigin;
    float rayFraction = cross2d(offset, divider) / denominator;
    float dividerFraction = cross2d(offset, lightRay) / denominator;
    bool crossesDivider = rayFraction > 0.0001 && rayFraction < 0.9999 && dividerFraction >= 0.0 && dividerFraction <= 1.0;
    return crossesDivider ? 0.0 : 1.0;
}

float calculateSelfShadow(vec2 localUv, out vec4 response)
{
    response = vec4(1.0);

    if (selfShadowMode == 1)
    {
        return calculateUprightBoxSelfShadow(localUv);
    }

    if (selfShadowMode == 2)
    {
        // RGBA is direct-light survival (not emission or sprite colour): down (+Y), up (-Y), left (-X), right (+X).
        response = texture(directionalResponseTexture, fragTexCoord);
        // This profile attenuates only the currently isolated direct-light contribution.
        float dividerVisibility = calculateProfileDividerVisibility(localUv);
        float authoredExposure =
            response.r * faceExposure.x +
            response.g * faceExposure.y * dividerVisibility +
            response.b * faceExposure.z +
            response.a * faceExposure.w;
        float shapedExposure = clamp(omniExposure + authoredExposure, selfShadowMinimumDirect, 1.0);
        return mix(1.0, shapedExposure, clamp(selfShadowStrength, 0.0, 1.0));
    }

    return 1.0;
}

void main()
{
    vec4 sprite = texture(texture0, fragTexCoord) * fragColor;

    if (sprite.a <= 0.001)
    {
        discard;
    }

    if (selfShadowPass == 2)
    {
        finalColor = vec4(0.0, 0.0, 0.0, sprite.a);
        return;
    }

    vec2 sourceSize = max(sourceUvMax - sourceUvMin, vec2(0.000001));
    vec2 localUv = clamp((fragTexCoord - sourceUvMin) / sourceSize, 0.0, 1.0);
    vec2 screenUv = gl_FragCoord.xy / max(resolution, vec2(1.0));
    vec3 ambientLight = ambientColor * ambientStrength;
    vec3 sampledDirectLight = texture(entityLightTexture, screenUv).rgb;
    vec3 worldDirectLight = sampledDirectLight * directLightStrength;
    vec3 readabilityLight = texture(entityReadabilityLightTexture, screenUv).rgb * directLightStrength;
    vec4 directionalResponse;
    float selfShadowAttenuation = calculateSelfShadow(localUv, directionalResponse);
    float finalDirectAttenuation = clamp(worldOcclusionScale, 0.0, 1.0) * selfShadowAttenuation;
    worldDirectLight *= finalDirectAttenuation;

    if (selfShadowPass == 1)
    {
        finalColor = vec4(sampledDirectLight * finalDirectAttenuation, sprite.a);
        return;
    }

    if (selfShadowDebugOutput == 1 && selfShadowMode == 2)
    {
        finalColor = vec4(directionalResponse.rgb, sprite.a);
        return;
    }

    if (selfShadowDebugOutput == 2)
    {
        finalColor = vec4(vec3(finalDirectAttenuation), sprite.a);
        return;
    }

    vec3 totalLight;

    if (lightPosterizeEnabled > 0.5)
    {
        totalLight = posterizeAmbient > 0.5 ? posterizeLighting(ambientLight + worldDirectLight) + readabilityLight : ambientLight + posterizeLighting(worldDirectLight) + readabilityLight;
    }
    else
    {
        totalLight = ambientLight + worldDirectLight + readabilityLight;
    }

    vec3 litSprite = clamp((sprite.rgb * totalLight - 0.5) * contrast + 0.5, 0.0, 1.0);
    float visibility = smoothstep(blackPoint, blackPoint + max(shadowSoftness, 0.000001), maxChannel(totalLight));
    vec3 darkness = mix(shadowColor, sprite.rgb * shadowColor, shadowDetail);
    vec3 result = mix(darkness, litSprite, visibility);
    finalColor = vec4(result, sprite.a);
}
