#version 330

in vec2 fragTexCoord;
in vec4 fragColor;

uniform sampler2D texture0;
uniform int shapeIndex;

out vec4 finalColor; // our result

bool isInsideShape(vec2 uv)
{
    if (shapeIndex ==0) {
        return true;
    }

    if (shapeIndex == 1) {
        // solid top left
        return uv.x + uv.y <= 1.0;
    }

    if (shapeIndex == 2) {
        // solid top right
        return uv.y <= uv.x;
    }

    if (shapeIndex == 3) {
        // solid bottom right
        return uv.x + uv.y >= 1.0;
    }

    if (shapeIndex == 4) {
        // solid bottom left
        return uv.y >= uv.x;
    }

    return true;
}

void main() {
    if (!isInsideShape(fragTexCoord)) {
        discard;
    }

    vec4 textureColor = texture(texture0, fragTexCoord);
    finalColor = textureColor * fragColor;
}