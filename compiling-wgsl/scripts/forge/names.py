"""Names a renamed identifier must never take: WGSL keywords, reserved words and
predeclared names (types, aliases, builtin functions, enumerants)."""
from .wgsl import KEYWORDS

RESERVED = set("""
NULL Self abstract active alignas alignof as asm asm_fragment async attribute auto await
become cast catch class co_await co_return co_yield coherent column_major common compile
compile_fragment concept const_cast consteval constexpr constinit crate debugger decltype
delete demote demote_to_helper do dynamic_cast enum explicit export extends extern external
fallthrough filter final finally friend from fxgroup get goto groupshared highp impl
implements import inline instanceof interface layout lowp macro macro_rules match mediump
meta mod module move mut mutable namespace new nil noexcept noinline nointerpolation
non_coherent noncoherent noperspective null nullptr of operator package packoffset partition
pass patch pixelfragment precise precision premerge priv protected pub public readonly ref
regardless register reinterpret_cast require resource restrict self set shared sizeof smooth
snorm static static_assert static_cast std subroutine super target template this
thread_local throw trait try type typedef typeid typename typeof union unless unorm unsafe
unsized use using varying virtual volatile wgsl where with writeonly yield
in is or and not
""".split())

TYPES = set("""
bool f16 f32 i32 u32 i64 u64 vec2 vec3 vec4 mat2x2 mat2x3 mat2x4 mat3x2 mat3x3 mat3x4 mat4x2
mat4x3 mat4x4 array atomic ptr sampler sampler_comparison texture_1d texture_2d
texture_2d_array texture_3d texture_cube texture_cube_array texture_multisampled_2d
texture_depth_multisampled_2d texture_external texture_storage_1d texture_storage_2d
texture_storage_2d_array texture_storage_3d texture_depth_2d texture_depth_2d_array
texture_depth_cube texture_depth_cube_array binding_array ray_query acceleration_structure
""".split())
TYPES |= {f"vec{n}{s}" for n in (2, 3, 4) for s in "iufh"}
TYPES |= {f"mat{c}x{r}{s}" for c in (2, 3, 4) for r in (2, 3, 4) for s in "fh"}

BUILTIN_FNS = set("""
abs acos acosh all any arrayLength asin asinh atan atanh atan2 bitcast ceil clamp cos cosh
countLeadingZeros countOneBits countTrailingZeros cross degrees determinant distance dot
dot4U8Packed dot4I8Packed exp exp2 extractBits faceForward firstLeadingBit firstTrailingBit
floor fma fract frexp insertBits inverseSqrt ldexp length log log2 max min mix modf normalize
pow quantizeToF16 radians reflect refract reverseBits round saturate select sign sin sinh
smoothstep sqrt step tan tanh transpose trunc
pack4x8snorm pack4x8unorm pack4xI8 pack4xU8 pack4xI8Clamp pack4xU8Clamp pack2x16snorm
pack2x16unorm pack2x16float unpack4x8snorm unpack4x8unorm unpack4xI8 unpack4xU8
unpack2x16snorm unpack2x16unorm unpack2x16float
storageBarrier textureBarrier workgroupBarrier workgroupUniformLoad
dpdx dpdxCoarse dpdxFine dpdy dpdyCoarse dpdyFine fwidth fwidthCoarse fwidthFine
textureDimensions textureGather textureGatherCompare textureLoad textureNumLayers
textureNumLevels textureNumSamples textureSample textureSampleBias textureSampleCompare
textureSampleCompareLevel textureSampleGrad textureSampleLevel textureSampleBaseClampToEdge
textureStore
atomicLoad atomicStore atomicAdd atomicSub atomicMax atomicMin atomicAnd atomicOr atomicXor
atomicExchange atomicCompareExchangeWeak
subgroupAdd subgroupAll subgroupAnd subgroupAny subgroupBallot subgroupBroadcast
subgroupBroadcastFirst subgroupElect subgroupExclusiveAdd subgroupExclusiveMul
subgroupInclusiveAdd subgroupInclusiveMul subgroupMax subgroupMin subgroupMul subgroupOr
subgroupShuffle subgroupShuffleDown subgroupShuffleUp subgroupShuffleXor subgroupXor
quadBroadcast quadSwapDiagonal quadSwapX quadSwapY
rayQueryInitialize rayQueryProceed rayQueryGetCommittedIntersection
rayQueryGetCandidateIntersection
""".split())

ENUMERANTS = set("""
function private workgroup uniform storage handle read write read_write immediate
perspective linear flat center centroid sample first either
error warning info off
position vertex_index instance_index front_facing frag_depth sample_index sample_mask
local_invocation_id local_invocation_index global_invocation_id workgroup_id num_workgroups
subgroup_invocation_id subgroup_size clip_distances primitive_index
rgba8unorm rgba8snorm rgba8uint rgba8sint rgba16uint rgba16sint rgba16float r32uint r32sint
r32float rg32uint rg32sint rg32float rgba32uint rgba32sint rgba32float bgra8unorm r8unorm
r8snorm r8uint r8sint rg8unorm rg8snorm rg8uint rg8sint r16uint r16sint r16float rg16uint
rg16sint rg16float rgb10a2uint rgb10a2unorm rg11b10ufloat r16unorm r16snorm rg16unorm
rg16snorm rgba16unorm rgba16snorm
""".split())

# members of builtin result structs (frexp, modf, atomicCompareExchangeWeak)
BUILTIN_MEMBERS = {"fract", "exp", "whole", "old_value", "exchanged"}

FORBIDDEN = KEYWORDS | RESERVED | TYPES | BUILTIN_FNS | ENUMERANTS | {"_", "true", "false"}

_SWZ = set("xyzw"), set("rgba")


def is_swizzle(name: str) -> bool:
    return 1 <= len(name) <= 4 and (set(name) <= _SWZ[0] or set(name) <= _SWZ[1])


_FIRST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_REST = _FIRST + "0123456789"


def name_stream():
    """Every identifier in length-then-lexicographic order, minus forbidden names."""
    for c in _FIRST:
        if c not in FORBIDDEN:
            yield c
    length = 2
    while True:
        def gen(prefix, k):
            if k == 0:
                yield prefix
                return
            for c in _REST:
                yield from gen(prefix + c, k - 1)
        for c in _FIRST:
            for n in gen(c, length - 1):
                if n not in FORBIDDEN and not n.startswith("__"):
                    yield n
        length += 1
