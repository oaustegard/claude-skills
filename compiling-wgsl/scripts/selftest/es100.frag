precision mediump float;
uniform vec2 resolution;
uniform float time;
varying vec2 vUv;
uniform sampler2D tex;
void main() {
    vec2 uv = gl_FragCoord.xy / resolution;
    vec4 t = texture2D(tex, vUv);
    gl_FragColor = vec4(uv, 0.5 + 0.5 * sin(time), 1.0) * t;
}
