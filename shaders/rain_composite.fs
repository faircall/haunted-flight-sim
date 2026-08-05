#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D lightTexture;
uniform sampler2D rainExposureTexture;

uniform vec2 resolution;
uniform vec2 cameraPosition;
uniform vec2 tileSize;
uniform vec2 mapSize;
uniform float time;
uniform float seed;
uniform float density;
uniform float speed;
uniform vec2 direction;
uniform vec2 cellSize;
uniform float streakLength;
uniform float unlitOpacity;
uniform float litOpacity;
uniform float lightThreshold;
uniform float lightResponse;
uniform float lightColorInfluence;
uniform vec3 ambientRainColor;
uniform float opacityLevels;
uniform float distortionEnabled;
uniform float distortionStrength;
uniform float distortionDensity;
uniform int debugMode;
uniform float showExposureOverlay;
uniform float disableStreakColor;
uniform float disableDistortion;

out vec4 finalColor;

float hashCell(ivec2 cell, uint salt)
{
    uint value = uint(cell.x) * 374761393u + uint(cell.y) * 668265263u;
    value += uint(seed) * 69069u + salt * 2246822519u;
    value = (value ^ (value >> 13u)) * 1274126177u;
    value ^= value >> 16u;
    return float(value) / 4294967295.0;
}

float exposureAtWorld(vec2 worldPosition)
{
    ivec2 tile = ivec2(floor(worldPosition / max(tileSize, vec2(1.0))));
    ivec2 dimensions = ivec2(mapSize);
    if (tile.x < 0 || tile.y < 0 || tile.x >= dimensions.x || tile.y >= dimensions.y)
        return 0.0;
    // Exact authored boundaries: one nearest texel, with no interpolation.
    return texelFetch(rainExposureTexture, tile, 0).r;
}

float streakField(vec2 worldPosition, vec2 rainDirection, out float geometryMask,
                  out float distortionSelection, out float offsetSign)
{
    vec2 perpendicular = vec2(-rainDirection.y, rainDirection.x);
    float loopTime = mod(time * speed, 4096.0);
    vec2 movingWorld = worldPosition - rainDirection * loopTime * 54.0;
    vec2 basisPosition = vec2(dot(movingWorld, perpendicular), dot(movingWorld, rainDirection));
    vec2 safeCellSize = max(cellSize, vec2(2.0));
    ivec2 cell = ivec2(floor(basisPosition / safeCellSize));
    vec2 local = basisPosition - vec2(cell) * safeCellSize;
    float active = hashCell(cell, 1u) < clamp(density, 0.0, 1.0) ? 1.0 : 0.0;
    float life = fract(loopTime * 0.18 + hashCell(cell, 2u));
    active *= life < 0.84 ? 1.0 : 0.0;
    float variedLength = clamp(streakLength * mix(0.58, 1.22, hashCell(cell, 3u)), 1.0, 8.0);
    float availableY = max(0.0, safeCellSize.y - variedLength - 1.0);
    vec2 anchor = vec2(
        0.5 + hashCell(cell, 4u) * max(0.0, safeCellSize.x - 1.0),
        0.5 + hashCell(cell, 5u) * availableY
    );
    float onePixelWide = abs(local.x - anchor.x) < 0.45 ? 1.0 : 0.0;
    float withinLength = local.y >= anchor.y && local.y < anchor.y + variedLength ? 1.0 : 0.0;
    float opacityVariation = mix(0.74, 1.0, hashCell(cell, 6u));
    geometryMask = active * onePixelWide * withinLength;
    // Refraction can select a subset, but it always uses this exact streak.
    distortionSelection = hashCell(cell, 7u) < clamp(distortionDensity, 0.0, 1.0) ? 1.0 : 0.0;
    offsetSign = hashCell(cell, 8u) < 0.5 ? -1.0 : 1.0;
    return geometryMask * opacityVariation;
}

void main()
{
    // gl_FragCoord is bottom-up; authored world/tile coordinates are top-down.
    vec2 screenPixel = floor(vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y));
    vec2 worldPosition = cameraPosition + screenPixel;
    vec2 rainDirection = normalize(length(direction) > 0.000001 ? direction : vec2(0.0, 1.0));
    float exposure = exposureAtWorld(worldPosition);
    vec3 directLight = texture(lightTexture, fragTexCoord).rgb;
    float luminance = dot(directLight, vec3(0.2126, 0.7152, 0.0722));
    float lightAmount = clamp((luminance - lightThreshold) * lightResponse, 0.0, 1.0);

    float streakGeometry = 0.0;
    float distortionSelection = 0.0;
    float offsetSign = 1.0;
    float streakMask = streakField(
        worldPosition, rainDirection, streakGeometry, distortionSelection, offsetSign
    ) * exposure;
    float distortionMask = streakGeometry * distortionSelection * exposure;
    float distortionAmount = distortionMask * clamp(distortionStrength, 0.0, 1.0);
    float offsetPixels = offsetSign * floor(distortionAmount + 0.5);
    if (distortionEnabled < 0.5 || disableDistortion > 0.5)
        offsetPixels = 0.0;
    // Contract: X is exactly zero and Y is an integer in {-1, 0, +1}.
    offsetPixels = clamp(offsetPixels, -1.0, 1.0);
    vec2 displacedUv = fragTexCoord + vec2(0.0, offsetPixels / resolution.y);
    vec2 halfTexel = 0.5 / resolution;
    displacedUv = clamp(displacedUv, halfTexel, vec2(1.0) - halfTexel);
    vec4 sceneSample = texture(texture0, displacedUv);

    float streakAlpha = streakMask * mix(unlitOpacity, litOpacity, lightAmount);
    float levels = max(floor(opacityLevels + 0.5), 2.0);
    streakAlpha = floor(clamp(streakAlpha, 0.0, 1.0) * levels + 0.5) / levels;
    if (streakMask <= 0.0)
        streakAlpha = 0.0;
    vec3 normalisedLight = directLight / max(max(directLight.r, max(directLight.g, directLight.b)), 0.0001);
    vec3 rainColor = mix(ambientRainColor, normalisedLight, clamp(lightColorInfluence * lightAmount, 0.0, 1.0));
    if (disableStreakColor > 0.5)
        streakAlpha = 0.0;
    vec3 result = mix(sceneSample.rgb, rainColor, streakAlpha);

    if (showExposureOverlay > 0.5 && exposure > 0.0)
        result = mix(result, vec3(0.12, 0.72, 0.92), exposure * 0.35);
    if (debugMode == 2)
        result = vec3(streakMask);
    else if (debugMode == 3)
        result = vec3(distortionMask);
    else if (debugMode == 4)
        result = vec3(lightAmount);
    else if (debugMode == 5)
        result = texture(rainExposureTexture, screenPixel / resolution).rrr;

    finalColor = vec4(result, sceneSample.a);
}
