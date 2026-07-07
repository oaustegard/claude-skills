"""
Reverso Time Series Foundation Model — NumPy/Numba Inference Implementation.

CPU-only, dependency-minimal inference for the Reverso model family
(arXiv:2602.17634). Supports all published model sizes via config-driven
layer stacking.

Dependencies: numpy, scipy (fft), numba
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

import numpy as np
from numba import njit
from scipy.fft import irfft, rfft

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ReversoConfig:
    """Model configuration for a Reverso variant.

    Built from the ``args.json`` shipped alongside each checkpoint.
    """

    d_model: int
    module_list: list[str]
    seq_len: int = 2048
    output_token_len: int = 48
    d_intermediate: int = 256
    n_heads: int = 4
    gating_kernel_size: int = 3
    attn_conv_size: int = 4

    @property
    def d_head(self) -> int:
        return self.d_model // self.n_heads

    @property
    def n_modules(self) -> int:
        return len(self.module_list)

    @classmethod
    def from_args(cls, args: dict) -> "ReversoConfig":
        """Create config from a loaded ``args.json`` dictionary."""
        module_list = [m.strip() for m in args["main_module"].split(",")]
        return cls(
            d_model=args["d_model"],
            module_list=module_list,
            seq_len=args.get("seq_len", 2048),
            output_token_len=args.get("output_token_len", 48),
            d_intermediate=args.get("d_intermediate", 256),
            n_heads=4,
            gating_kernel_size=args.get("gating_kernel_size", 3),
            attn_conv_size=4,
        )


# Pre-built configs for known model sizes
CONFIGS: dict[str, ReversoConfig] = {
    "nano": ReversoConfig(d_model=32, module_list=["conv", "attn", "conv", "attn"]),
    "small": ReversoConfig(d_model=64, module_list=["conv", "attn", "conv", "attn"]),
    "full": ReversoConfig(d_model=128, module_list=["conv", "attn"] * 8),
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    pos = x >= 0
    z = np.empty_like(x)
    z[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    z[~pos] = exp_x / (1.0 + exp_x)
    return z


def silu(x: np.ndarray) -> np.ndarray:
    return x * sigmoid(x)


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)


def layer_norm(
    x: np.ndarray, weight: np.ndarray, bias: Optional[np.ndarray], eps: float = 1e-5
) -> np.ndarray:
    """Layer normalization over the last dimension."""
    mean = x.mean(axis=-1, keepdims=True)
    var = x.var(axis=-1, keepdims=True)
    normed = (x - mean) / np.sqrt(var + eps)
    out = normed * weight
    if bias is not None:
        out = out + bias
    return out


def rms_norm(x: np.ndarray, weight: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Root-mean-square normalization (no bias, no mean centering)."""
    rms = np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)
    return (x / rms) * weight


def l2_normalize(x: np.ndarray, axis: int = -1, eps: float = 1e-12) -> np.ndarray:
    norm = np.sqrt(np.sum(x * x, axis=axis, keepdims=True) + eps)
    return x / norm


def simple_rms_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Parameter-free RMSNorm: ``x / sqrt(mean(x²))``.

    Produces vectors with L2 norm ≈ sqrt(dim), NOT unit vectors.
    Used by fla's DeltaNet for q/k normalization.
    """
    return x / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)


def depthwise_short_conv(
    x: np.ndarray,
    weight: np.ndarray,
    bias: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Causal depthwise 1-D convolution (correlation, matching PyTorch Conv1d).

    :param x: Input of shape ``(L, d)``.
    :param weight: Per-channel kernels, shape ``(d, kernel_size)``.
    :param bias: Optional, shape ``(d,)``.
    :returns: Output of shape ``(L, d)``.
    """
    L, d = x.shape
    ks = weight.shape[1]
    padded = np.pad(x, ((ks - 1, 0), (0, 0)), mode="constant")
    out = np.empty((L, d), dtype=x.dtype)
    for c in range(d):
        out[:, c] = np.correlate(padded[:, c], weight[c], mode="valid")
    if bias is not None:
        out += bias
    return out


def fft_long_conv(x: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Depthwise long circular convolution via FFT.

    Matches FlashFFTConv behaviour used during training: circular convolution
    with ``n_fft = L`` (no zero-padding).

    :param x: Shape ``(L, d)`` — sequence-first layout.
    :param kernel: Shape ``(d, L)`` — one length-L kernel per channel.
    :returns: Shape ``(L, d)``.
    """
    L, d = x.shape
    xt = x.T  # (d, L)
    xf = rfft(xt, n=L, axis=-1)
    kf = rfft(kernel, n=L, axis=-1)
    conv = irfft(xf * kf, n=L, axis=-1)
    return conv.T  # (L, d)


# ---------------------------------------------------------------------------
# Numba-accelerated DeltaNet recurrence
# ---------------------------------------------------------------------------


@njit(cache=True)
def _deltanet_recurrence(
    q: np.ndarray,
    k: np.ndarray,
    v: np.ndarray,
    beta: np.ndarray,
) -> np.ndarray:
    """DeltaNet linear-attention recurrence (all heads).

    :param q: ``(L, n_heads, d_h)``
    :param k: ``(L, n_heads, d_h)``
    :param v: ``(L, n_heads, d_h)``
    :param beta: ``(L, n_heads)``
    :returns: ``(L, n_heads, d_h)``
    """
    L, n_heads, d_h = q.shape
    out = np.empty_like(q)

    for h in range(n_heads):
        S = np.zeros((d_h, d_h), dtype=q.dtype)
        for i in range(L):
            ki = k[i, h]
            vi = v[i, h]
            bi = beta[i, h]

            # Sk = S @ ki
            Sk = np.empty(d_h, dtype=q.dtype)
            for a in range(d_h):
                acc = 0.0
                for b in range(d_h):
                    acc += S[a, b] * ki[b]
                Sk[a] = acc

            # S += bi * outer(vi - Sk, ki)
            for a in range(d_h):
                diff = bi * (vi[a] - Sk[a])
                for b in range(d_h):
                    S[a, b] += diff * ki[b]

            # out[i, h] = S @ qi
            qi = q[i, h]
            for a in range(d_h):
                acc = 0.0
                for b in range(d_h):
                    acc += S[a, b] * qi[b]
                out[i, h, a] = acc

    return out


# ---------------------------------------------------------------------------
# Model blocks
# ---------------------------------------------------------------------------


class CNNBlock:
    """Long depthwise FFT convolution with gating.

    The gating sub-network is::

        gate = sigmoid(pointwise_conv(silu(depthwise_conv(x))))

    where ``depthwise_conv`` has ``kernel_size=gating_kernel_size`` (3) and
    ``pointwise_conv`` has ``kernel_size=1`` (equivalent to a per-position
    linear projection).
    """

    def __init__(
        self,
        kernel: np.ndarray,
        gate_dw_w: np.ndarray,
        gate_dw_b: np.ndarray,
        gate_pw_w: np.ndarray,
        gate_pw_b: np.ndarray,
        norm_w: np.ndarray,
        norm_b: np.ndarray,
    ):
        self.kernel = kernel            # (d, L)
        self.gate_dw_w = gate_dw_w      # (d, ks) — depthwise conv
        self.gate_dw_b = gate_dw_b      # (d,)
        # Pointwise conv weight stored as (d_out, d_in, 1) → squeeze to (d_out, d_in)
        self.gate_pw_w = gate_pw_w.squeeze(-1) if gate_pw_w.ndim == 3 else gate_pw_w
        self.gate_pw_b = gate_pw_b      # (d,)
        self.norm_w = norm_w
        self.norm_b = norm_b

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """x: (L, d) → (L, d)."""
        residual = x
        # Gating
        g = depthwise_short_conv(x, self.gate_dw_w, self.gate_dw_b)
        g = silu(g)
        # Pointwise conv (kernel_size=1) = per-position linear: (L, d_in) @ (d_in, d_out).T
        g = g @ self.gate_pw_w.T + self.gate_pw_b
        g = sigmoid(g)
        gated = x * g
        # Long convolution
        out = fft_long_conv(gated, self.kernel)
        out = np.maximum(out, 0.0)  # ReLU
        out = layer_norm(out, self.norm_w, self.norm_b) + residual
        return out


class MLPBlock:
    """Two-layer MLP with optional skip projection."""

    def __init__(
        self,
        linear_w: np.ndarray,
        linear_b: np.ndarray,
        final_w: np.ndarray,
        final_b: np.ndarray,
        norm_w: np.ndarray,
        norm_b: np.ndarray,
        skip_w: Optional[np.ndarray] = None,
        skip_b: Optional[np.ndarray] = None,
    ):
        self.linear_w = linear_w
        self.linear_b = linear_b
        self.final_w = final_w
        self.final_b = final_b
        self.norm_w = norm_w
        self.norm_b = norm_b
        self.skip_w = skip_w
        self.skip_b = skip_b

    def __call__(self, x: np.ndarray) -> np.ndarray:
        if self.skip_w is not None:
            residual = x @ self.skip_w + self.skip_b
        else:
            residual = x
        y = np.maximum(x @ self.linear_w + self.linear_b, 0.0)  # ReLU
        y = y @ self.final_w + self.final_b
        y = layer_norm(y, self.norm_w, self.norm_b) + residual
        return y


class AttentionBlock:
    """DeltaNet linear attention with short convolutions.

    Matches the ``fla.layers.DeltaNet`` structure from the checkpoint:

    - Linear projections for q, k, v (no bias)
    - Causal depthwise short convolutions on q, k, v (no bias)
    - SiLU activation + L2 normalization on q and k
    - Beta gate via linear projection (no bias) + sigmoid
    - DeltaNet recurrence
    - Per-head RMS normalization (``o_norm``)
    - Output projection (no bias)
    - LayerNorm + residual
    """

    def __init__(
        self,
        q_proj_w: np.ndarray,
        k_proj_w: np.ndarray,
        v_proj_w: np.ndarray,
        o_proj_w: np.ndarray,
        beta_w: np.ndarray,
        q_conv_w: np.ndarray,
        k_conv_w: np.ndarray,
        v_conv_w: np.ndarray,
        o_norm_w: np.ndarray,
        norm_w: np.ndarray,
        norm_b: np.ndarray,
        n_heads: int,
        state_weaving: bool = False,
    ):
        self.q_proj_w = q_proj_w
        self.k_proj_w = k_proj_w
        self.v_proj_w = v_proj_w
        self.o_proj_w = o_proj_w
        self.beta_w = beta_w
        self.q_conv_w = q_conv_w
        self.k_conv_w = k_conv_w
        self.v_conv_w = v_conv_w
        self.o_norm_w = o_norm_w    # (d_head,) — per-head RMSNorm
        self.norm_w = norm_w
        self.norm_b = norm_b
        self.n_heads = n_heads
        self.state_weaving = state_weaving

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """x: (L, d_model) → (L, d_model)."""
        residual = x

        # State weaving: feed end-of-sequence info to start
        if self.state_weaving:
            x = x.copy()
            x[0] += x[-1]

        L, d = x.shape
        d_h = d // self.n_heads

        # Linear projections (no bias)
        q = x @ self.q_proj_w      # (L, d)
        k = x @ self.k_proj_w
        v = x @ self.v_proj_w

        # Short convolutions (causal, depthwise, no bias)
        q = depthwise_short_conv(q, self.q_conv_w)
        k = depthwise_short_conv(k, self.k_conv_w)
        v = depthwise_short_conv(v, self.v_conv_w)

        # Reshape to multi-head FIRST: (L, d) → (L, n_heads, d_h)
        q = q.reshape(L, self.n_heads, d_h)
        k = k.reshape(L, self.n_heads, d_h)
        v = v.reshape(L, self.n_heads, d_h)

        # Activations + per-head L2 normalization (q and k only)
        q = l2_normalize(silu(q), axis=-1)
        k = l2_normalize(silu(k), axis=-1)
        # v: no activation, no normalization

        # Beta gate (no bias)
        beta = sigmoid(x @ self.beta_w)  # (L, n_heads)

        # Ensure contiguous float64 for Numba
        q = np.ascontiguousarray(q, dtype=np.float64)
        k = np.ascontiguousarray(k, dtype=np.float64)
        v = np.ascontiguousarray(v, dtype=np.float64)
        beta = np.ascontiguousarray(beta, dtype=np.float64)

        # DeltaNet recurrence
        out = _deltanet_recurrence(q, k, v, beta)  # (L, n_heads, d_h)
        out = out.astype(np.float32)

        # Per-head RMS normalization
        for h in range(self.n_heads):
            out[:, h, :] = rms_norm(out[:, h, :], self.o_norm_w)

        # Reshape back and output projection (no bias)
        out = out.reshape(L, d)
        out = out @ self.o_proj_w

        out = layer_norm(out, self.norm_w, self.norm_b) + residual
        return out


class DecoderHead:
    """Attention-based decoder producing output_token_len predictions."""

    def __init__(
        self,
        head_w: np.ndarray,
        head_b: np.ndarray,
        q_proj_w: np.ndarray,
        q_proj_b: np.ndarray,
        k_proj_w: np.ndarray,
        k_proj_b: np.ndarray,
        v_proj_w: np.ndarray,
        v_proj_b: np.ndarray,
        out_proj_w: np.ndarray,
        out_proj_b: np.ndarray,
    ):
        self.head_w = head_w
        self.head_b = head_b
        self.q_proj_w = q_proj_w
        self.q_proj_b = q_proj_b
        self.k_proj_w = k_proj_w
        self.k_proj_b = k_proj_b
        self.v_proj_w = v_proj_w
        self.v_proj_b = v_proj_b
        self.out_proj_w = out_proj_w
        self.out_proj_b = out_proj_b

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """x: (L, d) → (p,) forecast values."""
        L, d = x.shape
        # Position mixing: (p, L) @ (L, d) → (p, d)
        z = self.head_w[:, :L] @ x + self.head_b[:, None]

        # Cross-attention
        q = z @ self.q_proj_w + self.q_proj_b
        k = x @ self.k_proj_w + self.k_proj_b
        v = x @ self.v_proj_w + self.v_proj_b

        scale = 1.0 / np.sqrt(d)
        attn_weights = softmax(q @ k.T * scale, axis=-1)
        attn_out = attn_weights @ v

        out = (attn_out @ self.out_proj_w + self.out_proj_b).squeeze(-1)
        return out


# ---------------------------------------------------------------------------
# Full model
# ---------------------------------------------------------------------------


class ReversoModel:
    """Assembled Reverso model for inference."""

    def __init__(
        self,
        config: ReversoConfig,
        embedding_w: np.ndarray,
        layers: list,
        decoder: DecoderHead,
    ):
        self.config = config
        self.embedding_w = embedding_w  # (d_model, 1)
        self.layers = layers
        self.decoder = decoder

    def embed(self, x: np.ndarray) -> np.ndarray:
        """x: (L,) → (L, d_model)."""
        return x[:, None] @ self.embedding_w.T

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Single forward pass: normalized input (L,) → (p,) predictions."""
        h = self.embed(x)
        for layer_fn in self.layers:
            h = layer_fn(h)
        return self.decoder(h)

    def forward_flip_equivariant(self, x: np.ndarray) -> np.ndarray:
        """Forward with flip equivariance for [0,1]-normalized input.

        For min-max normalized data in [0,1], the vertical flip is ``1 - x``
        (not ``-x``).  If the model is equivariant, ``f(1-x) ≈ 1 - f(x)``.
        Averaging enforces this symmetry:

            ``f_eq(x) = (f(x) + 1 - f(1 - x)) / 2``
        """
        f_pos = self.forward(x)
        f_flip = self.forward(1.0 - x)
        return (f_pos + 1.0 - f_flip) / 2.0


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def preprocess(
    series: np.ndarray, seq_len: int = 2048
) -> tuple[np.ndarray, float, float]:
    """Prepare raw series for model input.

    Handles NaN interpolation, padding, truncation, and min-max normalization.

    :returns: ``(normalized_series, x_min, x_max)``
    """
    x = np.asarray(series, dtype=np.float32).copy()

    # Interpolate NaNs
    nans = np.isnan(x)
    if nans.any():
        if nans.all():
            raise ValueError("Series is entirely NaN")
        valid = ~nans
        indices = np.arange(len(x))
        x[nans] = np.interp(indices[nans], indices[valid], x[valid])

    # Pad short series by back-filling with leftmost value
    if len(x) < seq_len:
        pad_len = seq_len - len(x)
        x = np.concatenate([np.full(pad_len, x[0], dtype=np.float32), x])

    # Truncate to last seq_len values
    x = x[-seq_len:]

    # Min-max normalization to [0, 1]
    x_min, x_max = float(x.min()), float(x.max())
    denom = x_max - x_min
    if denom < 1e-10:
        x_norm = np.full_like(x, 0.5)
    else:
        x_norm = (x - x_min) / denom

    return x_norm, x_min, x_max


def postprocess(predictions: np.ndarray, x_min: float, x_max: float) -> np.ndarray:
    """Unnormalize predictions back to original scale."""
    return predictions * (x_max - x_min) + x_min


# ---------------------------------------------------------------------------
# Weight loading
# ---------------------------------------------------------------------------


def _get(weights: dict, key: str) -> np.ndarray:
    """Retrieve a weight, raising a clear error if missing."""
    if key not in weights:
        available = [k for k in sorted(weights.keys()) if not k.startswith("__")]
        raise KeyError(
            f"Weight '{key}' not found. Available ({len(available)}): "
            + ", ".join(available[:20])
            + ("..." if len(available) > 20 else "")
        )
    return weights[key].astype(np.float32)


def _get_optional(weights: dict, key: str) -> Optional[np.ndarray]:
    if key in weights:
        return weights[key].astype(np.float32)
    return None


def _T(w: np.ndarray) -> np.ndarray:
    """Transpose PyTorch linear weight from (out, in) to (in, out) for x @ W."""
    return w.T.copy()


def _squeeze_conv(w: np.ndarray) -> np.ndarray:
    """Squeeze depthwise conv weight from (d, 1, ks) to (d, ks)."""
    if w.ndim == 3 and w.shape[1] == 1:
        return w.squeeze(1)
    return w


def load_model(weights: dict, config: ReversoConfig) -> ReversoModel:
    """Construct a ReversoModel from a weight dictionary and config.

    :param weights: Dict of ``name → np.ndarray``, from checkpoint or ``.npz``.
    :param config: Model configuration.
    """
    embedding_w = _get(weights, "embedding.weight")  # (d_model, 1)

    layers = []
    layer_idx = 0

    n_attn = 0
    total_attn = sum(1 for m in config.module_list if m == "attn")

    for mod_type in config.module_list:
        if mod_type == "conv":
            cnn = _build_cnn_block(weights, layer_idx, config)
            layers.append(cnn)
            layer_idx += 1

            mlp = _build_mlp_block(weights, layer_idx, config)
            layers.append(mlp)
            layer_idx += 1

        elif mod_type == "attn":
            is_intermediate = n_attn < (total_attn - 1)
            attn = _build_attn_block(
                weights, layer_idx, config, state_weaving=is_intermediate
            )
            layers.append(attn)
            layer_idx += 1
            n_attn += 1

            mlp = _build_mlp_block(weights, layer_idx, config)
            layers.append(mlp)
            layer_idx += 1
        else:
            raise ValueError(f"Unknown module type: {mod_type}")

    decoder = _build_decoder(weights, config)
    return ReversoModel(config, embedding_w, layers, decoder)


def _build_cnn_block(weights: dict, idx: int, cfg: ReversoConfig) -> CNNBlock:
    pfx = f"layers.{idx}"
    return CNNBlock(
        kernel=_get(weights, f"{pfx}.k"),
        gate_dw_w=_squeeze_conv(_get(weights, f"{pfx}.pregate.net.0.weight")),
        gate_dw_b=_get(weights, f"{pfx}.pregate.net.0.bias"),
        gate_pw_w=_get(weights, f"{pfx}.pregate.net.2.weight"),
        gate_pw_b=_get(weights, f"{pfx}.pregate.net.2.bias"),
        norm_w=_get(weights, f"{pfx}.norm.weight"),
        norm_b=_get(weights, f"{pfx}.norm.bias"),
    )


def _build_mlp_block(weights: dict, idx: int, cfg: ReversoConfig) -> MLPBlock:
    pfx = f"layers.{idx}"
    skip_w = _get_optional(weights, f"{pfx}.skip_linear.weight")
    skip_b = _get_optional(weights, f"{pfx}.skip_linear.bias")
    if skip_w is not None:
        skip_w = _T(skip_w)
    return MLPBlock(
        linear_w=_T(_get(weights, f"{pfx}.linear.weight")),
        linear_b=_get(weights, f"{pfx}.linear.bias"),
        final_w=_T(_get(weights, f"{pfx}.linear_final.weight")),
        final_b=_get(weights, f"{pfx}.linear_final.bias"),
        norm_w=_get(weights, f"{pfx}.norm.weight"),
        norm_b=_get(weights, f"{pfx}.norm.bias"),
        skip_w=skip_w,
        skip_b=skip_b,
    )


def _build_attn_block(
    weights: dict, idx: int, cfg: ReversoConfig, state_weaving: bool
) -> AttentionBlock:
    pfx = f"layers.{idx}"
    ap = f"{pfx}.attention"
    return AttentionBlock(
        q_proj_w=_T(_get(weights, f"{ap}.q_proj.weight")),
        k_proj_w=_T(_get(weights, f"{ap}.k_proj.weight")),
        v_proj_w=_T(_get(weights, f"{ap}.v_proj.weight")),
        o_proj_w=_T(_get(weights, f"{ap}.o_proj.weight")),
        beta_w=_T(_get(weights, f"{ap}.b_proj.weight")),
        q_conv_w=_squeeze_conv(_get(weights, f"{ap}.q_conv1d.weight")),
        k_conv_w=_squeeze_conv(_get(weights, f"{ap}.k_conv1d.weight")),
        v_conv_w=_squeeze_conv(_get(weights, f"{ap}.v_conv1d.weight")),
        o_norm_w=_get(weights, f"{ap}.o_norm.weight"),
        norm_w=_get(weights, f"{pfx}.norm.weight"),
        norm_b=_get(weights, f"{pfx}.norm.bias"),
        n_heads=cfg.n_heads,
        state_weaving=state_weaving,
    )


def _build_decoder(weights: dict, cfg: ReversoConfig) -> DecoderHead:
    return DecoderHead(
        head_w=_get(weights, "head.weight"),
        head_b=_get(weights, "head.bias"),
        q_proj_w=_T(_get(weights, "simple_q_proj.weight")),
        q_proj_b=_get(weights, "simple_q_proj.bias"),
        k_proj_w=_T(_get(weights, "key_proj.weight")),
        k_proj_b=_get(weights, "key_proj.bias"),
        v_proj_w=_T(_get(weights, "value_proj.weight")),
        v_proj_b=_get(weights, "value_proj.bias"),
        out_proj_w=_T(_get(weights, "out_proj.weight")),
        out_proj_b=_get(weights, "out_proj.bias"),
    )


# ---------------------------------------------------------------------------
# Weight download
# ---------------------------------------------------------------------------

_WEIGHT_CACHE: dict[str, dict] = {}


def download_weights(url: str, cache_dir: str = "/tmp/reverso") -> dict:
    """Download .npz weights from URL, caching in *cache_dir*."""
    if url in _WEIGHT_CACHE:
        return _WEIGHT_CACHE[url]

    os.makedirs(cache_dir, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    local_path = os.path.join(cache_dir, filename)

    if not os.path.exists(local_path):
        print(f"Downloading weights from {url} ...")
        urllib.request.urlretrieve(url, local_path)
        print(f"Saved to {local_path}")

    data = dict(np.load(local_path, allow_pickle=False))
    _WEIGHT_CACHE[url] = data
    return data


# ---------------------------------------------------------------------------
# Autoregressive forecast
# ---------------------------------------------------------------------------


def forecast(
    series: np.ndarray | list[float],
    prediction_length: int,
    weights: dict | str,
    model_size: str = "small",
    config: Optional[ReversoConfig] = None,
    flip_equivariant: bool = False,
) -> np.ndarray:
    """Zero-shot time series forecast using Reverso.

    :param series: Historical observations (1-D).
    :param prediction_length: Number of future steps to predict.
    :param weights: Either a weight dict or a URL string to .npz.
    :param model_size: One of ``'nano'``, ``'small'``, ``'full'`` (ignored if *config* given).
    :param config: Optional explicit config (overrides *model_size*).
    :param flip_equivariant: Use flip-equivariant averaging.  Helps for
        single-step prediction but can dampen amplitude during multi-step
        autoregressive rollout.  Default ``False``.
    :returns: Array of *prediction_length* forecasted values.
    """
    if config is None:
        config = CONFIGS[model_size]

    if isinstance(weights, str):
        weight_data = download_weights(weights)
    else:
        weight_data = weights

    model = load_model(weight_data, config)

    series = np.asarray(series, dtype=np.float32)
    x_norm, x_min, x_max = preprocess(series, config.seq_len)

    forward_fn = model.forward_flip_equivariant if flip_equivariant else model.forward

    context = x_norm.copy()
    predictions = []
    remaining = prediction_length

    while remaining > 0:
        ctx = context[-config.seq_len :]
        chunk = forward_fn(ctx)
        take = min(config.output_token_len, remaining)
        predictions.append(chunk[:take])
        remaining -= take
        context = np.concatenate([context, chunk])

    result_norm = np.concatenate(predictions)[:prediction_length]
    return postprocess(result_norm, x_min, x_max)


# ---------------------------------------------------------------------------
# Warm-up: trigger Numba JIT compilation
# ---------------------------------------------------------------------------


def warmup_jit():
    """Pre-compile the Numba DeltaNet kernel with a tiny dummy input."""
    L, nh, dh = 4, 2, 2
    q = np.zeros((L, nh, dh), dtype=np.float64)
    k = np.zeros((L, nh, dh), dtype=np.float64)
    v = np.zeros((L, nh, dh), dtype=np.float64)
    beta = np.zeros((L, nh), dtype=np.float64)
    _deltanet_recurrence(q, k, v, beta)
