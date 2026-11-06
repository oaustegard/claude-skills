// out/inout params, switch, ternary, integer division and modulo, mat3, atan2, macros with arguments
#define SQ(x) ((x) * (x))
#define PI 3.14159265
void polar(in vec2 p, out float r, out float a) { r = length(p); a = atan(p.y, p.x); }
void bump(inout vec3 c, float k) { c += k * vec3(0.1, 0.05, 0.0); }
vec3 palette(int i) {
    switch (i % 4) {
        case 0: return vec3(0.9, 0.3, 0.3);
        case 1: return vec3(0.3, 0.9, 0.4);
        case 2: return vec3(0.3, 0.4, 0.9);
        default: return vec3(0.9, 0.8, 0.3);
    }
}
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 p = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    float r, a; polar(p, r, a);
    int sector = int(floor((a + PI) / (2.0 * PI) * 12.0));
    int ring = int(r * 10.0) / 2;
    vec3 c = palette(sector + ring * 3);
    mat3 m = mat3(0.9, 0.1, 0.0, 0.0, 0.8, 0.2, 0.1, 0.0, 0.9);
    c = m * c;
    bump(c, SQ(sin(iTime + r * 8.0)));
    c *= r < 0.45 ? 1.0 : 0.35;
    fragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
