---
name: detecting-tips-zones
description: Text-prompted image zone detection using TIPSv2 B/14 on CPU. Produces `focus_targets` / `focus_edges` bbox lists from natural-language labels, ready to feed into `svg-portrait-mode`. Use when you want automatic foreground/background separation from prompts like "dog face" + "wooden floor" instead of hand-annotating bboxes.
metadata:
  version: 0.1.0
---

# Detecting TIPS Zones

Zero-shot zone detection: text prompts → patch-grid cosine heatmaps → bboxes.
Companion to `svg-portrait-mode` — replaces manual `focus_targets` / `focus_edges`
annotation with a TIPSv2 B/14 forward pass.

## Quick Start

```python
from tips_zones import detect_zones
from portrait_mode import portrait_mode

focus_targets, focus_edges = detect_zones(
    "photo.jpg",
    targets=["dog face"],
    edges=["dog paws", "dog ears", "dog body"],
    distractors=["wooden floor", "carpet rug", "shoes", "wall"],
    ckpt_dir="/path/to/tips/checkpoints",
    tips_root="/path/to/tips",
)

svg, stats = portrait_mode(
    "photo.jpg",
    focus_targets=focus_targets,
    focus_edges=focus_edges,
    style_transforms={"background": "desaturate:0.7"},
)
```

Amortise model load across multiple images:

```python
from tips_zones import load_models, detect_zones

models = load_models(ckpt_dir, tips_root, device="cpu")
for img in images:
    ft, fe = detect_zones(img, targets=[...], edges=[...], distractors=[...],
                          ckpt_dir=ckpt_dir, tips_root=tips_root, models=models)
    ...
```

## How It Works

```
image → B/14 vision encoder (MaskCLIP values trick on last block)
     → (32×32 patch grid at 448, or 64×64 at 896) × 768-d patch features
text labels → prompt ensemble (9 TCL templates) → B/14 text encoder
     → per-label mean feature → L2-normalise
per-label heatmap = cos(patch feature, label feature)  # raw, no softmax
bbox = top-k% patches → largest connected component → scaled + padded to image coords
```

### Why no softmax over labels

Naïve softmax assumes labels are mutually exclusive. `dog face`, `dog ears`,
and `dog body` are all true of the same pixels, so softmax collapses to
near-uniform and every heatmap covers the whole subject. Raw cosines +
per-label top-k threshold works much better — at the cost of requiring
**distractor labels** to anchor the relative scale. Always pass some
distractors (floor, wall, props — whatever is in the scene but not the
subject).

## Parameters

```python
detect_zones(
    image,                     # path | PIL Image
    targets,                   # ["main subject label", ...]
    edges=(),                  # ["sub-region label", ...]
    distractors=(),            # scene elements to anchor against — pass these!
    *,
    ckpt_dir,                  # has tips_v2_oss_b14_{vision,text}.npz + tokenizer.model
    tips_root,                 # local clone of google-deepmind/tips
    input_size=448,            # 448 → 32×32 grid, 896 → 64×64 (~12× slower on CPU)
    target_top_frac=0.04,      # fraction of patches kept per target label
    edge_top_frac=0.06,        # fraction of patches kept per edge label
    pad_frac=0.02,             # bbox padding as fraction of image dim
    device="cpu",
    models=None,               # optional pre-loaded (img_model, text_model, tokenizer)
)
```

Returns `(focus_targets, focus_edges)` — both lists of `{'bbox': (x1,y1,x2,y2), 'label': str}`.

## Performance (CPU, 16 cores)

| Step | Time |
|------|------|
| `load_models` (warm) | ~3.5s |
| `load_models` (cold, over 9p) | ~50s |
| Text encoding (9 templates × N labels) | ~0.1s |
| Vision forward @ 448 | 0.3–0.6s |
| Vision forward @ 896 | ~6–7s |

Inference is negligible next to `portrait_mode()` on large images.

## Capability Notes

**Subject / background split: strong.** B/14 separates subject from scene
reliably — typical split ~30/70 subject:background on single-subject photos.

**Sub-part discrimination: weak at B/14 + 448.** "dog face" vs "dog paws" vs
"dog ears" tend to fire on the same region. The 32×32 patch grid is not the
bottleneck (64×64 at 896 barely helps); B/14's patch features just don't
encode fine sub-part semantics strongly. If you need per-part zones:

1. Sharpen prompts — "close-up of dog's furry face" > "dog face" (try first)
2. L/14 or SO/14 model (richer features, larger download)
3. Sliding-window inference (tile crops, stitch heatmaps)

For coarse target/edge zoning (the `portrait_mode` use case), B/14 at 448 is
enough.

## Requirements

Python deps:

```bash
pip install torch torchvision tensorflow tensorflow-text scipy pillow numpy --break-system-packages -q
```

Upstream TIPS repo (for the `tips.pytorch` image/text encoder modules):

```bash
git clone https://github.com/google-deepmind/tips /path/to/tips
```

B/14 checkpoints (~500MB total) go in a directory passed as `ckpt_dir`:

- `tips_v2_oss_b14_vision.npz`
- `tips_v2_oss_b14_text.npz`
- `tokenizer.model`

Download links are in the TIPS repo README.

## Prompt Engineering Tips

- **Always include distractors.** Without them, top-k thresholding has no
  relative scale. 3–7 distractors covering scene elements (floor, wall,
  background objects) is the sweet spot.
- **Use concrete nouns over abstract ones.** "carpet rug" > "textured floor".
- **Top_frac tuning.** If a target bbox is too small, raise `target_top_frac`
  (0.04 → 0.08). Too big / bleeds into scene: lower it.
- **Pad modestly.** `pad_frac=0.02` works for most photos; raise to 0.05 for
  subjects near frame edges.

## EXIF Caveat

`portrait_mode` (via OpenCV) honours EXIF rotation. PIL (this skill's
preprocessing) does not. For correctly-oriented source images they agree; for
EXIF-rotated phone photos the detected bboxes will be in the *raw pixel*
orientation. Either:

- Re-save the source with EXIF baked in: `Image.open(p).rotate(0, expand=True).save(p)`
- Or call `ImageOps.exif_transpose(pil)` before passing to `detect_zones`.
