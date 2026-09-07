#version 330
in vec2 fragTexCoord;
uniform sampler2D texture0;
out vec4 finalColor;
void main()
{
    if (texture(texture0, fragTexCoord).a <= 0.02) discard;
    // Opaque union: limb overlap and editor tint cannot darken the silhouette.
    finalColor = vec4(1.0);
}
