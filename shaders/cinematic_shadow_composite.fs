#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform sampler2D shadowTexture;
uniform sampler2D visibilityTexture;

out vec4 finalColor;

void main()
{
    vec4 sceneSample = texture(texture0, fragTexCoord);
    vec4 rawShadow = texture(shadowTexture, fragTexCoord);
    float visibilityMask = texture(visibilityTexture, fragTexCoord).r;
    float shadowAlpha = rawShadow.a * visibilityMask;
    vec3 result = sceneSample.rgb * (1.0 - shadowAlpha) + rawShadow.rgb * visibilityMask;

    finalColor = vec4(result, sceneSample.a);
}
