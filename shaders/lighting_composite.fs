#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D lightTexture;

uniform vec3 ambientColor;
uniform vec3 shadowColor;

uniform float ambientStrength;
uniform float directLightStrength;
uniform float blackPoint;
uniform float shadowSoftness;
uniform float shadowDetail;
uniform float contrast;

out vec4 finalColor;

float maxChannel(vec3 value)
{
    return max(value.r, max(value.g, value.b));
}

vec3 applyContrast(vec3 color, float amount)
{
    return clamp((color - 0.5) * amount + 0.5, 0.0, 1.0);
}

void main()
{
    vec4 sceneSample = texture(texture0, fragTexCoord);
    vec3 directLight = texture(lightTexture, fragTexCoord).rgb * directLightStrength;
    // vec3 directLight = texture(lightTexture, vec2(fragTexCoord.x, 1.0 - fragTexCoord.y)).rgb * directLightStrength;

    vec3 ambientLight = ambientColor * ambientStrength;
    vec3 totalLight = ambientLight + directLight;

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