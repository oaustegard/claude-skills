struct Params { offset: u32, stride: u32, count: u32, _pad: u32 }
@group(0) @binding(0) var<uniform> P: Params;
@group(0) @binding(1) var<storage, read> src: array<u32>;
@group(0) @binding(2) var<storage, read_write> dst: array<u32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= P.count) { return; }
  if (P.offset + P.count * P.stride > arrayLength(&src)) { return; }  // bug: u32 wraps
  dst[i] = src[P.offset + i * P.stride];
}
