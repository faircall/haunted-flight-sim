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
uniform float windResponse;
uniform float opacity;
uniform float posterizeLevels;
uniform float emberDensity;
uniform float emberHeight;
uniform int passMode; // 0 = lit flame body, 1 = emissive core + fire embers, 2 = standalone embers
uniform vec4 colorCore;
uniform vec4 colorHot;
uniform vec4 colorMid;
uniform vec4 colorOuter;

out vec4 finalColor;

float hash12(vec2 p)
{
    ivec2 cell = ivec2(floor(p));
    uint value = uint(cell.x) * 374761393u + uint(cell.y) * 668265263u + uint(seed) * 69069u;
    value = (value ^ (value >> 13u)) * 1274126177u;
    value ^= value >> 16u;
    return float(value) / 4294967295.0;
}

float noise2(vec2 p)
{
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
               mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0)), u.x), u.y);
}

float fbm(vec2 p)
{
    float value = 0.0;
    float amplitude = 0.55;
    for (int octave = 0; octave < 3; octave++)
    {
        value += noise2(p) * amplitude;
        p = p * 2.03 + vec2(11.7, 7.9);
        amplitude *= 0.48;
    }
    return value / 0.957;
}

float quantize(float value, float levels)
{
    float steps = max(2.0, floor(levels + 0.5)) - 1.0;
    return floor(clamp(value, 0.0, 1.0) * steps + 0.5) / steps;
}

vec3 quantizeColor(vec3 value, float levels)
{
    return vec3(quantize(value.r, levels), quantize(value.g, levels), quantize(value.b, levels));
}

bool emberAtPixel(vec2 pixel, float fieldHeight, int maximumCount, float fieldDensity)
{
    ivec2 target = ivec2(floor(pixel));
    float activeCount = clamp(fieldDensity, 0.0, 1.0) * float(maximumCount);
    for (int index = 0; index < 16; index++)
    {
        if (index >= maximumCount || float(index) >= activeCount + hash12(vec2(float(index), seed)))
            continue;
        float id = float(index);
        float r0 = hash12(vec2(id * 3.17, seed + 4.1));
        float r1 = hash12(vec2(id * 7.31, seed + 9.7));
        float phase = fract(time * speed * mix(0.16, 0.29, r1) + r0);
        float rise = phase * fieldHeight;
        float drift = (r1 - 0.5) * effectSize.x + wind.x * windResponse * phase * phase * 0.32;
        float wobble = sin(phase * 18.0 + r0 * 31.0) * turbulence * 2.0;
        vec2 ember = anchorInBounds + vec2(drift + wobble, -rise);
        if (all(equal(target, ivec2(floor(ember)))))
            return true;
    }
    return false;
}

void main()
{
    vec2 screenPixel = floor(vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y));
    vec2 pixel = screenPixel - boundsMin;
    if (pixel.x < 0.0 || pixel.y < 0.0 || pixel.x >= boundsSize.x || pixel.y >= boundsSize.y)
        discard;

    float flameHeight = max(1.0, effectSize.y);
    float flameWidth = max(1.0, effectSize.x);
    vec2 fromBase = vec2(pixel.x - anchorInBounds.x, anchorInBounds.y - pixel.y);
    float y = fromBase.y / flameHeight;

    if (passMode == 2)
    {
        if (!emberAtPixel(pixel, max(1.0, effectSize.y), 16, density))
            discard;
        vec3 emberColor = quantizeColor(colorHot.rgb, posterizeLevels);
        finalColor = vec4(emberColor * opacity, opacity);
        return;
    }

    if (passMode == 1 && emberAtPixel(pixel, max(1.0, emberHeight), 12, emberDensity))
    {
        vec3 emberColor = quantizeColor(colorHot.rgb, posterizeLevels);
        finalColor = vec4(emberColor * opacity, opacity);
        return;
    }

    if (y < 0.0 || y > 1.0)
        discard;

    float advect = time * speed;
    float bend = wind.x * windResponse * y * y * 0.018;
    float warp = (fbm(vec2(y * 3.2 - advect * 1.7, seed * 0.013 + y * 1.1)) - 0.5) * turbulence;
    float x = (fromBase.x - bend - warp * flameWidth * 0.24) / flameWidth;
    float silhouetteNoise = fbm(vec2(x * 3.1 + seed * 0.007, y * 5.4 - advect * 2.2));
    float edgeBreakup = mix(0.62, 1.30, silhouetteNoise);
    // Converge to an almost point-sized apex.  The previous 0.12 minimum
    // width left a visibly flat cap after pixel quantisation.
    float halfWidth = (0.015 + 0.50 * pow(max(0.0, 1.0 - y), 0.72)) * edgeBreakup;
    float edge = 1.0 - abs(x) / max(0.01, halfWidth);
    float body = clamp(edge * 2.0 + silhouetteNoise * 0.48 - y * 0.18, 0.0, 1.0);

    // Two shorter, independently moving tongues prevent the flame from
    // collapsing into a single geometric wedge while retaining a stable base.
    float sideNoise = fbm(vec2(y * 4.7 + seed * 0.021, -advect * 1.9));
    float sideHeight = mix(0.42, 0.74, sideNoise);
    float sideY = y / max(0.01, sideHeight);
    float sideCentre = mix(-0.24, 0.24, step(0.5, hash12(vec2(seed, floor(advect * 0.55)))))
                     + (sideNoise - 0.5) * 0.16;
    float sideWidth = 0.19 * pow(max(0.0, 1.0 - sideY), 0.55);
    float sideTongue = clamp((1.0 - abs(x - sideCentre) / max(0.01, sideWidth)) * 1.8, 0.0, 1.0);
    sideTongue *= step(sideY, 1.0) * smoothstep(0.0, 0.12, sideY);
    body = max(body, sideTongue * mix(0.72, 1.0, sideNoise));
    body *= (1.0 - smoothstep(0.90, 1.0, y)) * density;
    body = quantize(body, posterizeLevels);
    if (body <= 0.0)
        discard;

    if (passMode == 0)
    {
        float band = quantize(clamp(y * 0.65 + (1.0 - body) * 0.45, 0.0, 1.0), posterizeLevels);
        vec3 color = mix(colorMid.rgb, colorOuter.rgb, band);
        float alpha = body * opacity * 0.82;
        finalColor = vec4(quantizeColor(color, posterizeLevels), alpha);
    }
    else
    {
        float core = quantize(clamp(body * 1.18 - abs(x) * 1.25 - y * 0.18, 0.0, 1.0), posterizeLevels);
        if (core <= 0.0)
            discard;
        vec3 color = mix(colorHot.rgb, colorCore.rgb, core);
        float alpha = core * opacity;
        finalColor = vec4(quantizeColor(color, posterizeLevels) * alpha, alpha);
    }
}
