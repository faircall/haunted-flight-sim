#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D lightTexture;

uniform vec2 resolution;
uniform vec2 cameraPosition;
uniform vec2 fogDrift;
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

out vec4 finalColor;

float hash21(vec2 point)
{
    point = fract(point * vec2(123.34, 456.21));
    point += dot(point, point + 45.32);
    return fract(point.x * point.y);
}

float valueNoise(vec2 point)
{
    vec2 cell = floor(point);
    vec2 local = fract(point);
    vec2 blend = local * local * (3.0 - 2.0 * local);

    float bottomLeft = hash21(cell);
    float bottomRight = hash21(cell + vec2(1.0, 0.0));
    float topLeft = hash21(cell + vec2(0.0, 1.0));
    float topRight = hash21(cell + vec2(1.0, 1.0));

    return mix(mix(bottomLeft, bottomRight, blend.x), mix(topLeft, topRight, blend.x), blend.y);
}

float fbm(vec2 point)
{
    float result = 0.0;
    float amplitude = 0.5;
    mat2 rotation = mat2(0.80, 0.60, -0.60, 0.80);

    for (int octave = 0; octave < 4; octave++)
    {
        result += valueNoise(point) * amplitude;
        point = rotation * point * 2.03 + vec2(17.13, 9.71);
        amplitude *= 0.5;
    }

    return result;
}

void main()
{
    vec4 sceneSample = texture(texture0, fragTexCoord);
    vec3 directLight = texture(lightTexture, fragTexCoord).rgb;
    vec2 screenPosition = vec2(gl_FragCoord.x, resolution.y - gl_FragCoord.y);
    vec2 worldPosition = cameraPosition + screenPosition;
    vec2 fogCoordinate = (worldPosition + fogDrift * time) * worldScale;

    float broadNoise = fbm(fogCoordinate);
    float detailNoise = fbm(fogCoordinate * detailScale + vec2(31.7, -18.4));
    float combinedNoise = mix(broadNoise, detailNoise, 0.32);
    float bankSoftness = max(softness, 0.0001);
    float shapedFog = smoothstep(cutoff - bankSoftness, cutoff + bankSoftness, combinedNoise);
    float fogAmount = clamp(shapedFog * density, 0.0, 1.0) * opacity;

    vec3 directFog = directLight * fogColor * fogAmount * lightStrength;
    vec3 ambientFog = fogColor * fogAmount * ambientStrength;
    vec3 veiledScene = sceneSample.rgb * (1.0 - clamp(fogAmount * veilStrength, 0.0, 1.0));
    vec3 result = veiledScene + directFog + ambientFog;

    finalColor = vec4(result, sceneSample.a);
}
