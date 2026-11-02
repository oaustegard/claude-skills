#version 300 es
uniform mat4 mvp;
uniform mat3 normalMatrix;
in vec3 position;
in vec3 normal;
in vec2 uv;
out vec3 vNormal;
out vec2 vUv;
void main() { vNormal = normalMatrix * normal; vUv = uv; gl_Position = mvp * vec4(position, 1.0); }
