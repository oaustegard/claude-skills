# Reimplementing a Neural Network Without PyTorch: Building Reverso as a Claude Skill

*A development log of porting a time series foundation model to run in an ephemeral, CPU-only container using nothing but NumPy, SciPy, and Numba — and the four bugs that had to die along the way.*

---

## The premise

[Reverso](https://github.com/shinfxh/reverso) is a family of tiny time series foundation models published in February 2026 ([arXiv:2602.17634](https://arxiv.org/html/2602.17634v1)). "Tiny" means 200K–2.6M parameters — roughly 1000x smaller than typical transformer-based forecasters — yet competitive on zero-shot benchmarks. The architecture interleaves long FFT convolutions with DeltaNet linear attention layers, making it both efficient and architecturally interesting.

The question was: could this run as a Claude skill? Skills execute in ephemeral Linux containers with no GPU and no persistent state. PyTorch alone is a 190MB install. The model weights are 2.2MB. There's a certain absurdity to needing 100x the framework to run 1x the model. (tl;dr: [yes](../forecasting-reverso/SKILL.md))

## Phase 1: Feasibility (with Sonnet)

The initial exploration happened in a conversation with Claude Sonnet, focused on whether this was even worth attempting. The key findings:

**The dependency landscape.** PyTorch CPU: 190MB, 3–5 minutes to install — a non-starter for per-conversation ephemeral use. JAX: similar story. ONNX Runtime: lightweight (12MB) but can't express DeltaNet's sequential recurrence cleanly. NumPy + Numba: 5MB total, installs in 1.6 seconds via `uv`, and Numba's JIT compiler handles the one performance-critical loop (the DeltaNet state update). Winner by elimination.

**The architecture decomposition.** Reverso's components map cleanly to NumPy primitives. FFT convolutions use `scipy.fft`. Matrix multiplications are `x @ W`. Layer normalization, softmax, SiLU — all one-liners. The only piece that needs compilation is the DeltaNet recurrence: a sequential loop over 2048 timesteps updating a small state matrix. Pure Python would take 50–150ms; Numba JIT gets it under 3ms.

**State weaving — the "open question."** The paper describes a mechanism where the last position's representation gets added to the first position before each intermediate DeltaNet layer. Initial concern: does this create cross-step recurrence that complicates inference? Answer after careful reading: no. It's a within-forward-pass operation. One line of code: `x[0] += x[-1]`.

Sonnet produced a detailed implementation outline covering all model components, weight name mappings, and a phased build plan. The actual coding moved to Opus.

## Phase 2: Initial implementation (with Opus)

The first implementation was built from the outline, the paper's architecture description, and assumptions about the fla (flash-linear-attention) library's DeltaNet implementation. Without access to PyTorch or the actual fla source code, several details had to be inferred from the weight shapes in the checkpoint.

A custom PyTorch checkpoint loader was written that unpickles `.pth` files without torch installed — reimplementing just enough of the pickle protocol to extract numpy arrays from the zip-structured checkpoint format. This avoided the 190MB PyTorch install entirely.

The first end-to-end run produced output with no NaN, no Inf, and numbers in a plausible range. The model appeared to work.

It did not work.

## Phase 3: The four bugs

### Bug 1: Linear vs. circular convolution

**Symptom:** Forecasts were structurally wrong — a clear sine wave input produced what looked like a random walk.

**Root cause:** The implementation used `rfft(x, n=2*L)` for zero-padded linear convolution. FlashFFTConv, which was used during training, computes **circular** convolution with `rfft(x, n=L)`. The learned kernels encode circular wraparound relationships. Using linear convolution changed every single CNN block output by an average of 660%.

**The fix:** Change `n=2*L` to `n=L`. One character.

**The lesson:** When reimplementing a trained model, you must match the training-time computation exactly, even when the "textbook" version differs. Circular convolution is technically "wrong" (it aliases) but the model's learned kernels compensate for that aliasing. Removing it doesn't clean the output — it destroys it.

This was the last bug found but by far the most impactful.

### Bug 2: Per-head L2 normalization dimension

**Symptom:** NaN values exploding from the first attention block.

**Root cause:** The DeltaNet layer normalizes query and key vectors to unit length. The initial implementation did this across the full `d_model=64` dimension *before* reshaping to multi-head layout `(L, 4, 16)`. The correct order is reshape first, then normalize per head across `d_head=16`.

With the wrong order, individual attention heads could have key vectors with `||k|| ≈ 3.2`. The DeltaNet state update has a stability condition requiring `beta * ||k||² ≤ 2`. With `||k||=3.2` and `beta=0.46`, the spectral radius hits -3.8 — exponential divergence within 20 timesteps of a 2048-step sequence.

**The debugging process:** Layer-by-layer tracing showed NaN appearing at Layer 2 (first AttentionBlock). Manual recurrence simulation for each of the 4 heads revealed head 0 was stable (`||k||≈1.0`) while head 1 diverged at step 53 (`||k||≈3.2`). The fix was reordering two lines.

### Bug 3: Flip equivariance formula

**Symptom:** Forecast mean was biased ~20 points low.

**Root cause:** The paper describes a flip equivariance trick averaging `f(x)` and `f(-x)`. But Reverso's input is min-max normalized to [0,1]. The vertical flip of [0,1] data is `1-x`, not `-x`. Feeding `-x` (values in [-1,0]) to a model trained on [0,1] data produces garbage — the model has never seen negative inputs.

**The correct formula:** `(f(x) + 1 - f(1-x)) / 2`

### Bug 4: Flip equivariance in autoregressive rollout

**Symptom:** 192-step forecasts of sine waves were flat despite correct single-step predictions.

**Root cause:** Averaging two forward passes at each autoregressive step cumulatively dampens amplitude. Each chunk's prediction is slightly compressed toward the mean, and that compressed prediction becomes context for the next chunk. Over 4 chunks, a 40-point amplitude oscillation shrinks to noise.

**The fix:** Default to raw `f(x)` for multi-step rollout; offer flip equivariance as an opt-in for single-step use.

## Phase 4: Validation theater vs. actual testing

A recurring theme in this development was premature declaration of success. After each fix, there was a temptation to look at summary statistics — "no NaN, mean is centered, range is plausible" — and conclude the model worked.

It didn't work until the *plots* looked right.

The turning point was the user's blunt assessment of the initial "fixed" output: *"In what universe would someone see the historical noisy sine curve and predict what looks like a random walk of a stockmarket performance during a bearmarket?"* This forced a shift from statistical validation (RMSE improved!) to visual validation (does this look like a forecast a human would recognize?).

The multi-pattern test suite — pure sines at different periods, damped oscillation, AM modulation, superposed frequencies, trend+seasonality, random walk — proved essential. A model producing junk on a pure sine wave has a bug. A model that handles sines but struggles with step functions might just have a training distribution gap. This distinction only becomes visible when you test diverse patterns and look at the plots.

## Phase 5: The final skill

[The forecasting-reverso skill](../forecasting-reverso/) consists of:

- **SKILL.md** (112 lines): Setup instructions, weight acquisition (HuggingFace download or user upload), forecast API, visualization template
- **scripts/reverso.py** (797 lines): Complete inference engine — all model components, preprocessing, autoregressive rollout
- **scripts/load_checkpoint.py** (229 lines): PyTorch-free `.pth` loader using custom pickle unpickling
- **references/architecture.md** (136 lines): Weight mapping, implementation pitfalls, debugging guidance

Total cold-start time: ~4 seconds (1.6s numba install + 2s JIT warmup). A 96-step forecast runs in ~160ms after warmup.

## Phase 6: Benchmark validation

Visual testing on synthetic data proves the architecture works. It doesn't prove it matches the published numbers. The paper claims Reverso Small achieves MASE 0.726 on GIFT-Eval, a standard benchmark with 23 datasets and 97 forecasting tasks.

Running the full benchmark in the container was impractical — GIFT-Eval has 144,000 time series and requires `gluonts` for standardized data loading. But two targeted tests on real benchmark datasets proved informative.

**M4 Yearly (22,974 very short series, 31 points each):** Our MASE of 3.95 versus the paper's 3.43 (full 2.6M model). These series are padded to 2048 with 98.5% constant fill — the worst case for an architecture built around long convolutions. Every foundation model struggles here; even Chronos-2 only manages 3.24 on this dataset.

**SZ Taxi (156 series, 2,976 points each, 15-minute frequency):** Our MASE of **0.5619** versus the paper's 0.5441 (full 2.6M model). This is a 3.3% gap between our Small (0.6M) implementation and the paper's Full (2.6M) — entirely expected from the model size difference. For context, the naive baseline scores 0.79 and Chronos-2 scores 0.54 on this dataset.

The SZ Taxi result is the convincing one. With proper context length (2,976 points fitting cleanly into the 2,048 window), our reimplementation matches models 50–200x larger and sits within a few percent of the full Reverso model's published score.

A practical discovery from benchmarking: at ~65ms per forward pass, large-scale evaluation in the container requires budget awareness. The SZ Taxi evaluation (936 forecast windows) took 61 seconds. M4 Yearly's 22,974 windows would take 25 minutes. The skill now includes cost estimation and rejects batch requests that would timeout.

## What I'd do differently

**Start with the convolution.** The circular vs. linear distinction was the biggest bug but the last one found. If I'd verified a single CNN block's output against a known reference before building the rest of the model, the other three bugs would have been found in a cleaner context.

**Build a reference trace first.** The right workflow is: run the PyTorch model, save activations at every layer boundary, then match each layer independently. Instead, the implementation was built bottom-up and tested end-to-end, which made it impossible to localize errors until I resorted to manual layer-by-layer tracing.

**Trust the plots, not the numbers.** RMSE improved from 14.14 (naive) to 12.87 (broken model) to 4.93 (working model). The difference between 12.87 and 4.93 is the difference between junk and a real forecast. Summary statistics can't tell you that — only visual inspection can.

---

*The Reverso paper is by Xinghong Fu, Yanhong Li, Georgios Papaioannou, and Yoon Kim. The skill implementation uses their published checkpoint for Reverso Small. The flash-linear-attention library by Songlin Yang and Yu Zhang provides the DeltaNet layer implementation that the weight structure is based on.*
