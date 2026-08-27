#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D lightTexture;
uniform sampler2D volumeTexture;

uniform vec2 resolution;
uniform vec2 cameraPosition;
uniform vec2 fogDrift;
uniform vec2 detailDrift;
uniform vec3 fogColor;

uniform float time;
uniform float density;
uniform float opacity;
uniform float worldScale;
uniform float detailScale;
uniform float cutoff;
uniform float softness;
uniform float lightStrength;
uniform float ambientStrength;
uniform float veilStrength;
uniform float evolutionSpeed;
uniform float warpScale;
uniform float warpStrength;
uniform float detailEvolutionSpeed;
uniform float globalAmount;
uniform float posterizeEnabled;
uniform float posterizeLevels;
uniform float ditherEnabled;
uniform float ditherStrength;

out vec4 finalColor;

float hash31(vec3 point)
{
    point = fract(point * vec3(0.1031, 0.1030, 0.0973));
    point += dot(point, point.yxz + 33.33);
    return fract((point.x + point.y) * point.z);
}

float valueNoise3D(vec3 point)
{
    vec3 cell = floor(point);
    vec3 local = fract(point);
    vec3 blend = local * local * (3.0 - 2.0 * local);

    float x00 = mix(hash31(cell + vec3(0.0, 0.0, 0.0)), hash31(cell + vec3(1.0, 0.0, 0.0)), blend.x);
    float x10 = mix(hash31(cell + vec3(0.0, 1.0, 0.0)), hash31(cell + vec3(1.0, 1.0, 0.0)), blend.x);
    float x01 = mix(hash31(cell + vec3(0.0, 0.0, 1.0)), hash31(cell + vec3(1.0, 0.0, 1.0)), blend.x);
    float x11 = mix(hash31(cell + vec3(0.0, 1.0, 1.0)), hash31(cell + vec3(1.0, 1.0, 1.0)), blend.x);
    float y0 = mix(x00, x10, blend.y);
    float y1 = mix(x01, x11, blend.y);
    return mix(y0, y1, blend.z);
}

float fbm3D(vec3 point)
{
    float result = 0.0;
    float amplitude = 0.5;

    for (int octave = 0; octave < 4; octave++)
    {
        result += valueNoise3D(point) * amplitude;
        point = point * 2.03 + vec3(17.13, 9.71, 5.47);
        amplitude *= 0.5;
    }

    return result;
}

float warpFbm3D(vec3 point)
{
    float result = 0.0;
    float amplitude = 0.5;

    for (int octave = 0; octave < 3; octave++)
    {
        result += valueNoise3D(point) * amplitude;
        point = point * 2.01 + vec3(7.17, 13.91, 3.73);
        amplitude *= 0.5;
    }

    return result / 0.875;
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

void main()
{
    vec4 sceneSample = texture(texture0, fragTexCoord);
    vec3 directLight = texture(lightTexture, fragTexCoord).rgb;
    float localAmount = texture(volumeTexture, fragTexCoord).r;
    float regionAmount = clamp(globalAmount + localAmount, 0.0, 1.0);
    vec2 screenPosition = vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y);
    vec2 worldPosition = cameraPosition + screenPosition;
    vec2 broadCoordinate = (worldPosition + fogDrift * time) * worldScale;
    float warpTime = time * evolutionSpeed * 0.7;
    float warpX = warpFbm3D(vec3(broadCoordinate * warpScale + vec2(19.7, -8.3), warpTime));
    float warpY = warpFbm3D(vec3(broadCoordinate * warpScale + vec2(-14.2, 27.1), warpTime + 11.7));
    vec2 warp = vec2(warpX, warpY) * 2.0 - 1.0;
    vec2 warpedCoordinate = broadCoordinate + warp * warpStrength;

    float broadNoise = fbm3D(vec3(warpedCoordinate, time * evolutionSpeed));
    vec2 detailCoordinate = (worldPosition + detailDrift * time) * worldScale * detailScale;
    detailCoordinate += warp * warpStrength * 0.35 + vec2(31.7, -18.4);
    float detailNoise = fbm3D(vec3(detailCoordinate, time * detailEvolutionSpeed + 23.9));
    float combinedNoise = mix(broadNoise, detailNoise, 0.32);
    float bankSoftness = max(softness, 0.0001);
    float shapedFog = smoothstep(cutoff - bankSoftness, cutoff + bankSoftness, combinedNoise);
    float fogAmount = clamp(shapedFog * density, 0.0, 1.0) * opacity * regionAmount;

    vec3 directFog = directLight * fogColor * fogAmount * lightStrength;
    vec3 ambientFog = fogColor * fogAmount * ambientStrength;
    float veilAmount = clamp(fogAmount * veilStrength, 0.0, 1.0);
    vec3 fogContribution = directFog + ambientFog;

    if (posterizeEnabled > 0.5)
    {
        vec3 fogIllumination = directLight * fogColor * lightStrength + fogColor * ambientStrength;
        float stylizedFogAlpha = fogAmount;

        if (ditherEnabled > 0.5)
        {
            stylizedFogAlpha = posterizeScalarDithered(stylizedFogAlpha, posterizeLevels, gl_FragCoord.xy, ditherStrength);
            fogContribution = posterizeVec3Dithered(fogIllumination * stylizedFogAlpha, posterizeLevels, gl_FragCoord.xy, ditherStrength);
        }
        else
        {
            stylizedFogAlpha = posterizeScalar(stylizedFogAlpha, posterizeLevels);
            fogContribution = posterizeVec3(fogIllumination * stylizedFogAlpha, posterizeLevels);
        }

        veilAmount = clamp(stylizedFogAlpha * veilStrength, 0.0, 1.0);
    }

    vec3 veiledScene = sceneSample.rgb * (1.0 - veilAmount);
    vec3 result = veiledScene + fogContribution;

    finalColor = vec4(result, sceneSample.a);
}
