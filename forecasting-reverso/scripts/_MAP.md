# scripts/
*Files: 2*

## Files

### load_checkpoint.py
> Imports: `io, pickle, struct, zipfile`
- **TorchUnpickler** (C) :60
  - **__init__** (m) `(self, fp, zip_file: zipfile.ZipFile, archive_prefix: str)` :63
  - **find_class** (m) `(self, module: str, name: str)` :68
  - **persistent_load** (m) `(self, pid)` :102
  - **_infer_dtype** (m) `(self, storage_type_fn, raw_data: bytes, numel: int)` :114
- **load_checkpoint** (f) `(path: str)` :169

### reverso.py
> Imports: `os, urllib.request, dataclasses, typing, numba`...
- **sigmoid** (f) `(x: np.ndarray)` :80
- **silu** (f) `(x: np.ndarray)` :90
- **softmax** (f) `(x: np.ndarray, axis: int = -1)` :94
- **layer_norm** (f) `(
    x: np.ndarray, weight: np.ndarray, bias: Optional[np.ndarray], eps: float = 1e-5
)` :99
- **rms_norm** (f) `(x: np.ndarray, weight: np.ndarray, eps: float = 1e-6)` :112
- **l2_normalize** (f) `(x: np.ndarray, axis: int = -1, eps: float = 1e-12)` :118
- **simple_rms_norm** (f) `(x: np.ndarray, eps: float = 1e-6)` :123
- **depthwise_short_conv** (f) `(
    x: np.ndarray,
    weight: np.ndarray,
    bias: Optional[np.ndarray] = None,
)` :132
- **fft_long_conv** (f) `(x: np.ndarray, kernel: np.ndarray)` :155
- **CNNBlock** (C) :233
  - **__init__** (m) `(
        self,
        kernel: np.ndarray,
        gate_dw_w: np.ndarray,
        gate_dw_b: np.ndarray,
        gate_pw_w: np.ndarray,
        gate_pw_b: np.ndarray,
        norm_w: np.ndarray,
        norm_b: np.ndarray,
    )` :245
  - **__call__** (m) `(self, x: np.ndarray)` :264
- **MLPBlock** (C) :281
  - **__init__** (m) `(
        self,
        linear_w: np.ndarray,
        linear_b: np.ndarray,
        final_w: np.ndarray,
        final_b: np.ndarray,
        norm_w: np.ndarray,
        norm_b: np.ndarray,
        skip_w: Optional[np.ndarray] = None,
        skip_b: Optional[np.ndarray] = None,
    )` :284
  - **__call__** (m) `(self, x: np.ndarray)` :304
- **AttentionBlock** (C) :315
  - **__init__** (m) `(
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
    )` :330
  - **__call__** (m) `(self, x: np.ndarray)` :360
- **DecoderHead** (C) :417
  - **__init__** (m) `(
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
    )` :420
  - **__call__** (m) `(self, x: np.ndarray)` :444
- **ReversoModel** (C) :468
  - **__init__** (m) `(
        self,
        config: ReversoConfig,
        embedding_w: np.ndarray,
        layers: list,
        decoder: DecoderHead,
    )` :471
  - **embed** (m) `(self, x: np.ndarray)` :483
  - **forward** (m) `(self, x: np.ndarray)` :487
  - **forward_flip_equivariant** (m) `(self, x: np.ndarray)` :494
- **preprocess** (f) `(
    series: np.ndarray, seq_len: int = 2048
)` :513
- **postprocess** (f) `(predictions: np.ndarray, x_min: float, x_max: float)` :552
- **load_model** (f) `(weights: dict, config: ReversoConfig)` :592
- **download_weights** (f) `(url: str, cache_dir: str = "/tmp/reverso")` :710
- **forecast** (f) `(
    series: np.ndarray | list[float],
    prediction_length: int,
    weights: dict | str,
    model_size: str = "small",
    config: Optional[ReversoConfig] = None,
    flip_equivariant: bool = False,
)` :734
- **warmup_jit** (f) `()` :790

