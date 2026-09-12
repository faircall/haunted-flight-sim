#version 330
in vec2 fragTexCoord;
in vec4 fragColor;
uniform sampler2D texture0;
uniform vec3 emissionColor;
uniform float emissionStrength;
uniform float edgeOnly;
uniform vec2 maskStep;
uniform float edgeWidth;
out vec4 finalColor;
float maskAlpha(vec2 uv) {
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return 0.0;
    return texture(texture0, uv).a;
}
void main() {
    float alpha = texture(texture0, fragTexCoord).a * fragColor.a;
    float edge = 1.0;
    if (edgeOnly > 0.5) {
        float inside = 1.0;
        for (int y=-1; y<=1; y++)
            for (int x=-1; x<=1; x++)
                inside = min(inside, maskAlpha(fragTexCoord + vec2(x,y)*maskStep));
        // Grow the silhouette outward instead of scaling the sprite about its centre.
        // Fractional coverage keeps the moving rim smooth at the native resolution.
        float radius = clamp(edgeWidth - 1.0, 0.0, 5.0);
        float expanded = alpha;
        int extent = int(ceil(radius));
        for (int y=-extent; y<=extent; y++) {
            for (int x=-extent; x<=extent; x++) {
                float coverage = clamp(radius + 1.0 - length(vec2(x,y)), 0.0, 1.0);
                if (coverage > 0.0)
                    expanded = max(expanded, maskAlpha(fragTexCoord + vec2(x,y)*maskStep) * coverage);
            }
        }
        edge = 1.0 - inside;
        alpha = expanded;
    }
    if (alpha < 0.01) discard;
    finalColor = vec4(emissionColor * emissionStrength * edge, alpha);
}
