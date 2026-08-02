#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;
uniform vec2 boundsMin;
uniform vec2 boundsSize;
uniform vec2 anchorInBounds;
uniform vec2 effectSize;
uniform vec2 wind;
uniform float time;
uniform float seed;
uniform float density;
uniform float speed;
uniform float turbulence;
uniform float detailScale;
uniform float warpStrength;
uniform float evolutionSpeed;
uniform float windResponse;
uniform float opacity;
uniform float posterizeLevels;
uniform vec4 smokeColor;

out vec4 finalColor;

float hash13(vec3 p)
{
    ivec3 cell = ivec3(floor(p));
    uint value = uint(cell.x) * 374761393u
               + uint(cell.y) * 668265263u
               + uint(cell.z) * 2246822519u
               + uint(seed) * 69069u;
    value = (value ^ (value >> 13u)) * 1274126177u;
    value ^= value >> 16u;
    return float(value) / 4294967295.0;
}

float noise3(vec3 p)
{
    vec3 i = floor(p);
    vec3 f = fract(p);
    vec3 u = f * f * (3.0 - 2.0 * f);
    float z0 = mix(mix(hash13(i), hash13(i + vec3(1.0, 0.0, 0.0)), u.x),
                   mix(hash13(i + vec3(0.0, 1.0, 0.0)), hash13(i + vec3(1.0, 1.0, 0.0)), u.x), u.y);
    float z1 = mix(mix(hash13(i + vec3(0.0, 0.0, 1.0)), hash13(i + vec3(1.0, 0.0, 1.0)), u.x),
                   mix(hash13(i + vec3(0.0, 1.0, 1.0)), hash13(i + vec3(1.0)), u.x), u.y);
    return mix(z0, z1, u.z);
}

float fbm3(vec3 p)
{
    float value = 0.0;
    float amplitude = 0.54;
    for (int octave = 0; octave < 4; octave++)
    {
        value += noise3(p) * amplitude;
        p = p * 2.01 + vec3(13.7, 8.3, 5.9);
        amplitude *= 0.46;
    }
    return value / 0.927;
}

float quantize(float value, float levels)
{
    float steps = max(2.0, floor(levels + 0.5)) - 1.0;
    return floor(clamp(value, 0.0, 1.0) * steps + 0.5) / steps;
}

void main()
{
    vec2 screenPixel = floor(vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y));
    vec2 pixel = screenPixel - boundsMin;
    if (pixel.x < 0.0 || pixel.y < 0.0 || pixel.x >= boundsSize.x || pixel.y >= boundsSize.y)
        discard;

    vec2 fromBase = vec2(pixel.x - anchorInBounds.x, anchorInBounds.y - pixel.y);
    float height = max(1.0, effectSize.y);
    float width = max(1.0, effectSize.x);
    float y = fromBase.y / height;
    if (y < 0.0 || y > 1.0)
        discard;

    float advect = time * speed;
    // Advection moves smoke upward through the volume.  The independent Z
    // coordinate makes the volume itself continuously evolve rather than
    // merely translating a frozen two-dimensional noise texture.
    float evolution = time * evolutionSpeed;
    float windBend = wind.x * windResponse * y * y * 0.035;
    vec2 broad = vec2((fromBase.x - windBend) / width * 3.2, y * 4.0 - advect);
    float warpX = fbm3(vec3(broad * 0.72 + vec2(17.3, advect * -0.37), evolution * 0.71)) - 0.5;
    float warpY = fbm3(vec3(broad * 0.69 + vec2(-9.1, advect * -0.23), evolution * 0.83 + 11.0)) - 0.5;
    vec2 warped = broad + vec2(warpX, warpY) * warpStrength;
    float cloud = fbm3(vec3(warped * max(0.04, detailScale * 7.0) + vec2(0.0, -advect * 0.72), evolution));
    float lobes = fbm3(vec3(warped * 1.83 + vec2(seed * 0.011, -advect * 1.18), evolution * 1.21 + 23.0));
    float halfWidth = mix(0.18, 0.58, pow(y, 0.62));
    halfWidth *= mix(0.72, 1.28, lobes);
    float x = abs((fromBase.x - windBend) / width);
    float silhouette = 1.0 - smoothstep(halfWidth * 0.74, halfWidth, x);
    float densityField = silhouette * smoothstep(0.25, 0.64, cloud + turbulence * (lobes - 0.5) * 0.28);
    densityField *= smoothstep(0.0, 0.08, y) * (1.0 - smoothstep(0.72, 1.0, y)) * density;
    float alpha = quantize(densityField * opacity, posterizeLevels);
    if (alpha <= 0.0)
        discard;

    float shade = quantize(mix(0.72, 1.08, lobes), posterizeLevels);
    vec3 color = smokeColor.rgb * shade;
    finalColor = vec4(color, alpha);
}
