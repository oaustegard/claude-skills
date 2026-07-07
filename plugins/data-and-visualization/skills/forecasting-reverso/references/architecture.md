# Reverso Architecture Reference

## Model Structure

Reverso Small: `conv,attn,conv,attn` with d_model=64, producing this layer stack:

```
Layer 0: CNNBlock       (FFT long conv + gating)
Layer 1: MLPBlock       (d=64 → 256 → 64)
Layer 2: AttentionBlock (DeltaNet, state_weaving=True)
Layer 3: MLPBlock
Layer 4: CNNBlock
Layer 5: MLPBlock
Layer 6: AttentionBlock (DeltaNet, state_weaving=False)
Layer 7: MLPBlock
→ DecoderHead          (cross-attention, 48 output positions)
```

State weaving applies to all attention blocks except the last: `is_intermediate = n_attn < (total_attn - 1)`.

## Weight Name Mapping

From the actual checkpoint (86 tensors total, 71 after filtering FlashFFTConv twiddle factors):

### CNNBlock (layers 0, 4)
- `layers.{i}.k` — (64, 2048) long conv kernel
- `layers.{i}.pregate.net.0.weight` — (64, 1, 3) depthwise gate conv
- `layers.{i}.pregate.net.0.bias` — (64,)
- `layers.{i}.pregate.net.2.weight` — (64, 64, 1) **pointwise** gate conv (NOT depthwise)
- `layers.{i}.pregate.net.2.bias` — (64,)
- `layers.{i}.norm.weight/bias` — (64,) LayerNorm

### AttentionBlock (layers 2, 6)
All projections are **bias-free** except LayerNorm:
- `layers.{i}.attention.q_proj.weight` — (64, 64)
- `layers.{i}.attention.k_proj.weight` — (64, 64)
- `layers.{i}.attention.v_proj.weight` — (64, 64)
- `layers.{i}.attention.o_proj.weight` — (64, 64)
- `layers.{i}.attention.b_proj.weight` — (4, 64) beta gate
- `layers.{i}.attention.q_conv1d.weight` — (64, 1, 4) causal depthwise, no bias
- `layers.{i}.attention.k_conv1d.weight` — (64, 1, 4)
- `layers.{i}.attention.v_conv1d.weight` — (64, 1, 4)
- `layers.{i}.attention.o_norm.weight` — (16,) per-head RMSNorm
- `layers.{i}.norm.weight/bias` — (64,) LayerNorm

### MLPBlock (layers 1, 3, 5, 7)
- `layers.{i}.linear.weight` — (256, 64)
- `layers.{i}.linear.bias` — (256,)
- `layers.{i}.linear_final.weight` — (64, 256)
- `layers.{i}.linear_final.bias` — (64,)
- `layers.{i}.norm.weight/bias` — (64,)

### Decoder
- `head.weight` — (48, 2048) position mixing
- `head.bias` — (48,)
- `simple_q_proj.weight/bias` — (64, 64) / (64,)
- `key_proj.weight/bias` — (64, 64) / (64,)
- `value_proj.weight/bias` — (64, 64) / (64,)
- `out_proj.weight` — (1, 64)
- `out_proj.bias` — (1,)

### Ignored weights
`layers.{i}.flashfftconv.*` and `shared_flashfftconv.*` are CUDA-specific precomputed twiddle factors. Skip during loading — scipy.fft handles FFT natively.

## Critical Implementation Details

These are lessons from debugging — each caused incorrect output when wrong.

### 1. Circular FFT convolution (n_fft = L, not 2L)

FlashFFTConv computes **circular** convolution. The model was trained with wraparound aliasing, so the learned kernels depend on it.

```python
# CORRECT — circular conv matching training
xf = rfft(x, n=L, axis=-1)
kf = rfft(kernel, n=L, axis=-1)
result = irfft(xf * kf, n=L, axis=-1)

# WRONG — linear conv (zero-padded), 660% error
xf = rfft(x, n=2*L, axis=-1)  # DO NOT DO THIS
```

### 2. Per-head L2 normalization (reshape BEFORE normalizing)

The fla DeltaNet flow is: linear proj → short conv → reshape to (L, n_heads, d_h) → SiLU → L2 normalize per head.

```python
# CORRECT — normalize across d_h=16 per head
q = q.reshape(L, n_heads, d_h)
q = l2_normalize(silu(q), axis=-1)  # ||q|| = 1 per head

# WRONG — normalize across d_model=64 before reshape
q = l2_normalize(silu(q), axis=-1)  # ||q|| = 1 across all heads
q = q.reshape(L, n_heads, d_h)      # individual heads can have ||k|| >> 1
```

Wrong order causes DeltaNet state divergence. With ||k||=3.2 and beta=0.46, eigenvalue = 1 - beta*||k||² = -3.8, causing exponential blowup within ~20 steps.

### 3. Flip equivariance for [0,1]-normalized data

Input is min-max normalized to [0,1]. Vertical flip is `1-x`, not `-x`:

```python
# CORRECT
f_flip = model.forward(1.0 - x)
result = (f_pos + 1.0 - f_flip) / 2.0

# WRONG — feeds negative values the model never saw in training
f_neg = model.forward(-x)
result = (f_pos - f_neg) / 2.0
```

### 4. Pointwise gate convolution

`pregate.net.2` has shape (64, 64, 1) — a full pointwise (1x1) convolution, NOT depthwise. Squeeze the trailing dim and apply as a matrix multiply per position:

```python
g = g @ gate_pw_w.squeeze(-1).T + gate_pw_b  # (L, d) @ (d, d) per position
```

### 5. Per-head RMSNorm on attention output

The checkpoint contains `o_norm.weight` of shape (d_head,) = (16,). Applied per-head after the DeltaNet recurrence, before the output projection:

```python
for h in range(n_heads):
    out[:, h, :] = rms_norm(out[:, h, :], o_norm_weight)
```

### 6. PyTorch weight transposition

PyTorch stores Linear weights as (out_features, in_features). For `x @ W` computation, transpose to (in_features, out_features):

```python
W_numpy = checkpoint_weight.T.copy()
```
