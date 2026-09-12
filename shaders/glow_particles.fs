#version 330
in vec4 fragColor;
uniform sampler2D occlusionTexture;
uniform vec2 resolution;
uniform float groundDepth;
uniform float maskEnabled;
out vec4 finalColor;
void main() {
    if (maskEnabled > 0.5) {
        vec4 blocker = texture(occlusionTexture,gl_FragCoord.xy/resolution);
        float depth = (round(blocker.r*255.0)*256.0+round(blocker.g*255.0))/16.0-2048.0;
        if (blocker.a > .5 && depth > groundDepth+.0625) discard;
    }
    finalColor = fragColor;
}
