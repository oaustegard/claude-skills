"""Text-prompted image zone detection using TIPSv2 B/14 (MaskCLIP values trick).

Returns bbox annotations in the shape expected by `svg-portrait-mode`'s
`portrait_mode()` — i.e. `focus_targets` and `focus_edges` lists of
`{'bbox': (x1, y1, x2, y2), 'label': str}`.
"""

import io
import math
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as TVT
from PIL import Image
from torch import Tensor, nn

PATCH_SIZE = 14
VOCAB_SIZE = 32000
MAX_SEQ_LEN = 64

B14_TEXT_CONFIG = {
    "hidden_size": 768,
    "mlp_dim": 3072,
    "num_heads": 12,
    "num_layers": 12,
}

# TCL-style prompt ensemble: averaging several phrasings stabilises the text
# embedding when the raw label is short.
_TCL_PROMPTS = [
    "itap of a {}.",
    "a bad photo of a {}.",
    "a origami {}.",
    "a photo of the large {}.",
    "a {} in a video game.",
    "art of the {}.",
    "a photo of the small {}.",
    "a photo of many {}.",
    "a photo of {}s.",
]


def _ensure_tips_on_path(tips_root):
    """Make `from tips.pytorch import ...` importable.

    The upstream google-deepmind/tips repo is not installed as a package; its
    `pytorch/` dir is a plain folder. Adding the parent to sys.path plus an
    empty `__init__.py` in `tips_root` is enough.
    """
    tips_root = os.path.abspath(tips_root)
    parent = os.path.dirname(tips_root)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    init = os.path.join(tips_root, "__init__.py")
    if not os.path.exists(init):
        with open(init, "w"):
            pass


def load_models(ckpt_dir, tips_root, device="cpu"):
    """Load B/14 vision + text encoders and the sentencepiece tokenizer.

    Args:
        ckpt_dir: directory containing `tips_v2_oss_b14_vision.npz`,
            `tips_v2_oss_b14_text.npz`, and `tokenizer.model`.
        tips_root: path to a local clone of google-deepmind/tips (the dir
            containing `pytorch/`).
        device: torch device string.

    Returns:
        (model_image, model_text, tokenizer)
    """
    _ensure_tips_on_path(tips_root)
    import tensorflow as tf
    import tensorflow_text  # noqa: F401 - registers sentencepiece op
    from tips.pytorch import image_encoder, text_encoder

    vision_path = os.path.join(ckpt_dir, "tips_v2_oss_b14_vision.npz")
    text_path = os.path.join(ckpt_dir, "tips_v2_oss_b14_text.npz")

    weights_image = {
        k: torch.tensor(v)
        for k, v in np.load(vision_path, allow_pickle=False).items()
    }
    model_image = image_encoder.vit_base(
        img_size=448,
        patch_size=PATCH_SIZE,
        ffn_layer="mlp",
        block_chunks=0,
        init_values=1.0,
        interpolate_antialias=True,
        interpolate_offset=0.0,
    )
    model_image.load_state_dict(weights_image)
    model_image = model_image.to(device).eval()

    with open(text_path, "rb") as f:
        np_weights_text = dict(np.load(io.BytesIO(f.read()), allow_pickle=False))
    weights_text = {k: torch.from_numpy(v) for k, v in np_weights_text.items()}
    weights_text.pop("temperature")

    model_text = text_encoder.TextEncoder(B14_TEXT_CONFIG, vocab_size=VOCAB_SIZE)
    model_text.load_state_dict(weights_text)
    model_text = model_text.to(device).eval()

    tokenizer_path = os.path.join(ckpt_dir, "tokenizer.model")
    with tf.io.gfile.GFile(tokenizer_path, "rb") as f:
        tokenizer = tensorflow_text.SentencepieceTokenizer(f.read())

    return model_image, model_text, tokenizer


def _get_all_blocks(model_image):
    if model_image.chunked_blocks:
        blocks = []
        for chunk in model_image.blocks:
            for blk in chunk:
                if not isinstance(blk, nn.Identity):
                    blocks.append(blk)
        return blocks
    return list(model_image.blocks)


def encode_image_value_attention(model_image, img: Tensor) -> Tensor:
    """MaskCLIP 'values' trick on the last attention block.

    Replaces the last block's attention output with its value projection,
    which aligns better with the text encoder than final patch tokens.
    Returns a (B, h, w, C) tensor.
    """
    B, _, H, W = img.shape
    P = model_image.patch_size
    new_H = math.ceil(H / P) * P
    new_W = math.ceil(W / P) * P
    if (H, W) != (new_H, new_W):
        img = F.interpolate(img, size=(new_H, new_W), mode="bicubic", align_corners=False)
    _, _, h_i, w_i = img.shape

    x = model_image.prepare_tokens_with_masks(img)
    num_register = model_image.num_register_tokens
    all_blocks = _get_all_blocks(model_image)
    for i, blk in enumerate(all_blocks):
        if i < len(all_blocks) - 1:
            x = blk(x)
        else:
            x_normed = blk.norm1(x)
            b_dim, n_dim, c_dim = x_normed.shape
            qkv = (
                blk.attn.qkv(x_normed)
                .reshape(b_dim, n_dim, 3, blk.attn.num_heads, c_dim // blk.attn.num_heads)
                .permute(2, 0, 3, 1, 4)
            )
            v = qkv[2]
            v_out = v.transpose(1, 2).reshape(b_dim, n_dim, c_dim)
            v_out = blk.attn.proj(v_out)
            v_out = blk.ls1(v_out)
            x_val = v_out + x
            y_val = blk.norm2(x_val)
            y_val = blk.ls2(blk.mlp(y_val))
            x_val = x_val + y_val

    x_val = model_image.norm(x_val)
    patch_tokens = x_val[:, 1 + num_register:, :]
    return patch_tokens.reshape(B, h_i // P, w_i // P, -1).contiguous()


def tokenize_prompts(tokenizer, labels, templates=_TCL_PROMPTS):
    texts = []
    spans = []
    for lab in labels:
        start = len(texts)
        for t in templates:
            texts.append(t.format(lab))
        spans.append((start, len(texts)))
    tokens = tokenizer.tokenize(texts).to_list()
    max_l = min(max(len(ids) for ids in tokens), MAX_SEQ_LEN)
    num = len(tokens)
    token_ids = np.zeros((num, max_l), dtype=np.int64)
    paddings = np.ones((num, max_l), dtype=np.float32)
    for i, ids in enumerate(tokens):
        length = min(len(ids), max_l)
        token_ids[i, :length] = ids[:length]
        paddings[i, :length] = 0.0
    return torch.from_numpy(token_ids), torch.from_numpy(paddings), spans


def text_features_for_labels(model_text, tokenizer, labels, device="cpu"):
    ids, pads, spans = tokenize_prompts(tokenizer, labels)
    ids, pads = ids.to(device), pads.to(device)
    with torch.no_grad():
        feats = model_text(ids, pads)
        feats = F.normalize(feats, p=2, dim=-1)
    out = []
    for a, b in spans:
        f = feats[a:b].mean(dim=0)
        out.append(F.normalize(f, p=2, dim=-1))
    return torch.stack(out)  # (L, D)


def preprocess_image(pil_image, size=448):
    transform = TVT.Compose([
        TVT.Resize((size, size), interpolation=TVT.InterpolationMode.BICUBIC),
        TVT.ToTensor(),
        TVT.Normalize(mean=[0.0, 0.0, 0.0], std=[1.0, 1.0, 1.0]),
    ])
    return transform(pil_image.convert("RGB"))


def heatmaps(model_image, img_tensor, text_feats, softmax_over_labels=False):
    """Per-label patch-grid heatmaps via cosine similarity.

    softmax_over_labels=True forces one dominant label per patch (fails when
    labels aren't mutually exclusive, e.g. "dog face" / "dog ears" / "dog body"
    are all true of the same region). Default False: raw cosines, thresholded
    per-label downstream.
    """
    img = img_tensor.unsqueeze(0)
    with torch.no_grad():
        feats = encode_image_value_attention(model_image, img).squeeze(0)  # (h, w, C)
    feats = F.normalize(feats, p=2, dim=-1)
    cos = torch.einsum("cd,hwd->chw", text_feats, feats)  # (L, h, w)
    if softmax_over_labels:
        cos = cos.softmax(dim=0)
    return cos.cpu().numpy()


def bbox_from_heatmap(hm, image_size, top_frac=0.08, pad_frac=0.02):
    """Top-k% patches → largest connected component → bbox at image scale."""
    from scipy import ndimage
    H, W = image_size
    h, w = hm.shape
    n_keep = max(1, int(round(h * w * top_frac)))
    flat = hm.flatten()
    thr = np.partition(flat, -n_keep)[-n_keep]
    mask = hm >= thr
    if mask.sum() == 0:
        return None
    lbl, n = ndimage.label(mask)
    sizes = ndimage.sum(mask, lbl, range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    ys, xs = np.where(lbl == biggest)
    y1, y2 = ys.min(), ys.max() + 1
    x1, x2 = xs.min(), xs.max() + 1
    sy, sx = H / h, W / w
    X1, Y1, X2, Y2 = int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)
    pad_x = int(W * pad_frac)
    pad_y = int(H * pad_frac)
    X1 = max(0, X1 - pad_x); Y1 = max(0, Y1 - pad_y)
    X2 = min(W, X2 + pad_x); Y2 = min(H, Y2 + pad_y)
    return (X1, Y1, X2, Y2)


def detect_zones(
    image,
    targets,
    edges=(),
    distractors=(),
    *,
    ckpt_dir,
    tips_root,
    input_size=448,
    target_top_frac=0.04,
    edge_top_frac=0.06,
    pad_frac=0.02,
    device="cpu",
    models=None,
):
    """End-to-end: image + text prompts → (focus_targets, focus_edges) for portrait_mode.

    Args:
        image: path, PIL Image, or anything Image.open can handle.
        targets: list of label strings for the main subject (e.g. ["dog face"]).
        edges: list of label strings for compositionally important sub-regions.
        distractors: list of label strings for scene elements to suppress —
            critical for relative ranking when softmax is disabled.
        ckpt_dir, tips_root: as in `load_models`.
        input_size: 448 (32x32 patch grid) or 896 (64x64, ~12x slower on CPU,
            marginal gains for sub-part discrimination on small models).
        target_top_frac, edge_top_frac, pad_frac: bbox extraction knobs.
        device: torch device.
        models: pre-loaded (model_image, model_text, tokenizer) tuple, to amortise
            load cost across multiple images.

    Returns:
        (focus_targets, focus_edges): lists of {'bbox': (x1,y1,x2,y2), 'label': str}
        ready to pass as `portrait_mode(..., focus_targets=..., focus_edges=...)`.
    """
    if models is None:
        models = load_models(ckpt_dir, tips_root, device=device)
    model_image, model_text, tokenizer = models

    if isinstance(image, (str, os.PathLike)):
        pil = Image.open(image).convert("RGB")
    else:
        pil = image.convert("RGB")
    W, H = pil.size

    img_t = preprocess_image(pil, size=input_size)
    all_labels = list(targets) + list(edges) + list(distractors)
    text_feats = text_features_for_labels(model_text, tokenizer, all_labels, device=device)
    hm = heatmaps(model_image, img_t, text_feats, softmax_over_labels=False)

    focus_targets = []
    for i, lab in enumerate(targets):
        bb = bbox_from_heatmap(hm[i], (H, W), top_frac=target_top_frac, pad_frac=pad_frac)
        if bb:
            focus_targets.append({"bbox": bb, "label": lab})
    focus_edges = []
    offset = len(targets)
    for j, lab in enumerate(edges):
        bb = bbox_from_heatmap(hm[offset + j], (H, W), top_frac=edge_top_frac, pad_frac=pad_frac)
        if bb:
            focus_edges.append({"bbox": bb, "label": lab})

    return focus_targets, focus_edges
