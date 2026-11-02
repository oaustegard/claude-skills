// raymarched SDF scene: structs, loops with break, mod repetition, mat2 rotation, normals
#define MAX_STEPS 96
#define EPS 0.001
struct Hit { float d; int id; };
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
Hit map(vec3 p) {
    Hit h = Hit(p.y + 1.0, 0);
    vec3 q = p; q.xz = mod(q.xz + 2.0, 4.0) - 2.0;
    q.xz *= rot(iTime * 0.5);
    float b = sdBox(q, vec3(0.6)) - 0.1;
    if (b < h.d) h = Hit(b, 1);
    float s = length(p - vec3(0.0, 0.3 + 0.2 * sin(iTime), 0.0)) - 0.5;
    if (s < h.d) h = Hit(s, 2);
    return h;
}
vec3 normal(vec3 p) {
    vec2 e = vec2(EPS, 0.0);
    return normalize(vec3(map(p + e.xyy).d - map(p - e.xyy).d, map(p + e.yxy).d - map(p - e.yxy).d, map(p + e.yyx).d - map(p - e.yyx).d));
}
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    vec3 ro = vec3(0.0, 1.0, -4.0), rd = normalize(vec3(uv, 1.5));
    float t = 0.0; Hit h = Hit(1e9, -1);
    for (int i = 0; i < MAX_STEPS; i++) {
        h = map(ro + rd * t);
        if (h.d < EPS || t > 40.0) break;
        t += h.d;
    }
    vec3 col = vec3(0.6, 0.75, 0.9) - rd.y * 0.3;
    if (t < 40.0) {
        vec3 p = ro + rd * t, n = normal(p);
        float dif = clamp(dot(n, normalize(vec3(0.6, 0.8, -0.4))), 0.0, 1.0);
        vec3 alb = h.id == 0 ? vec3(0.3 + 0.2 * mod(floor(p.x) + floor(p.z), 2.0)) : (h.id == 1 ? vec3(0.9, 0.4, 0.2) : vec3(0.2, 0.5, 0.9));
        col = alb * (0.2 + 0.8 * dif);
        col = mix(col, vec3(0.6, 0.75, 0.9), 1.0 - exp(-0.002 * t * t));
    }
    fragColor = vec4(pow(col, vec3(0.4545)), 1.0);
}
