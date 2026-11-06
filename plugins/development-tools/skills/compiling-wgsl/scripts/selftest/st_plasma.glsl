// plasma: trig, iTime, iResolution, swizzles
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
    float v = sin(uv.x * 3.0 + iTime) + sin(uv.y * 4.0 - iTime * 1.3) + sin(length(uv) * 6.0 - iTime * 2.0);
    vec3 col = 0.5 + 0.5 * cos(v + vec3(0.0, 2.1, 4.2));
    fragColor = vec4(col, 1.0);
}
