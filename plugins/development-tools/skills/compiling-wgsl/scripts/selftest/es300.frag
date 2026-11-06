#version 300 es
precision highp float;
uniform Lights { vec4 dir; vec4 color; };
uniform sampler2D albedo;
uniform samplerCube env;
in vec3 vNormal;
in vec2 vUv;
out vec4 outColor;
void main() {
    vec3 n = normalize(vNormal);
    float d = max(dot(n, dir.xyz), 0.0);
    vec3 base = texture(albedo, vUv).rgb;
    vec3 refl = texture(env, reflect(-dir.xyz, n)).rgb;
    outColor = vec4(base * d * color.rgb + 0.1 * refl, 1.0);
}
