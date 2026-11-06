// value-noise fbm: hash, floor/fract, int loop, uint bit ops, const arrays
const float W[5] = float[5](0.5, 0.25, 0.125, 0.0625, 0.03125);
float hash(vec2 p) { uvec2 q = uvec2(ivec2(floor(p))) * uvec2(1597334673u, 3812015801u); uint n = (q.x ^ q.y) * 1597334673u; return float(n) * (1.0 / 4294967295.0); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float s = 0.0; for (int k = 0; k < 5; k++) { s += W[k] * noise(p); p = p * 2.03 + vec2(1.7, 9.2); } return s; }
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 p = fragCoord / iResolution.y * 4.0;
    float f = fbm(p + fbm(p + iTime * 0.2));
    fragColor = vec4(mix(vec3(0.1, 0.2, 0.4), vec3(1.0, 0.9, 0.7), f), 1.0);
}
