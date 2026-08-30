#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform vec2 resolution;
uniform vec2 boundsMin;
uniform vec2 boundsSize;
uniform vec2 anchorInBounds;
uniform vec2 effectSize;
uniform vec2 effectDirection;
uniform float seed;
uniform float density;
uniform float opacity;
uniform float burstProgress;
uniform vec4 sparkColor;

out vec4 finalColor;

float hash12(vec2 p)
{
    ivec2 cell = ivec2(floor(p));
    uint value = uint(cell.x) * 374761393u
               + uint(cell.y) * 668265263u
               + uint(seed) * 69069u;
    value = (value ^ (value >> 13u)) * 1274126177u;
    value ^= value >> 16u;
    return float(value) / 4294967295.0;
}

float distanceToSegment(vec2 point, vec2 start, vec2 end)
{
    vec2 segment = end - start;
    float lengthSquared = max(0.000001, dot(segment, segment));
    float amount = clamp(dot(point - start, segment) / lengthSquared, 0.0, 1.0);
    return length(point - (start + segment * amount));
}

void main()
{
    vec2 screenPixel = floor(vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y));
    vec2 pixel = screenPixel - boundsMin;
    if (pixel.x < 0.0 || pixel.y < 0.0
            || pixel.x >= boundsSize.x || pixel.y >= boundsSize.y)
        discard;

    vec2 direction = effectDirection;
    if (dot(direction, direction) < 0.000001)
        direction = vec2(1.0, 0.0);
    direction = normalize(direction);
    vec2 perpendicular = vec2(-direction.y, direction.x);
    vec2 samplePoint = pixel + vec2(0.5);
    float brightness = 0.0;
    float activeCount = clamp(density, 0.0, 1.0) * 12.0;

    for (int index = 0; index < 12; index++)
    {
        float id = float(index);
        float countJitter = hash12(vec2(id * 3.11, seed + 1.7));
        if (id >= activeCount + countJitter)
            continue;
        float spreadRandom = hash12(vec2(id * 7.13, seed + 8.9));
        float speedRandom = hash12(vec2(id * 5.37, seed + 17.1));
        float delay = hash12(vec2(id * 9.71, seed + 23.3)) * 0.16;
        float age = clamp(
            (burstProgress - delay) / max(0.001, 1.0 - delay), 0.0, 1.0
        );
        if (age <= 0.0)
            continue;

        vec2 ray = normalize(
            direction + perpendicular * mix(-0.78, 0.78, spreadRandom)
        );
        float travel = effectSize.y * age * mix(0.58, 1.0, speedRandom);
        vec2 gravity = vec2(0.0, effectSize.x * 0.28 * age * age);
        vec2 head = anchorInBounds + ray * travel + gravity;
        float trailLength = mix(1.7, 0.55, age) * mix(0.75, 1.25, speedRandom);
        vec2 tail = head - ray * trailLength;
        float distanceFromSpark = distanceToSegment(samplePoint, tail, head);
        float spark = 1.0 - smoothstep(0.18, 0.82, distanceFromSpark);
        spark *= (1.0 - age * 0.62) * mix(0.72, 1.0, countJitter);
        brightness = max(brightness, spark);
    }

    brightness *= opacity;
    if (brightness <= 0.001)
        discard;
    finalColor = vec4(
        sparkColor.rgb * brightness,
        brightness * sparkColor.a
    );
}
