"""Image-to-SVG pipeline using flowing DAG runner.

Usage:
    from pipeline import image_to_svg
    svg, flow = image_to_svg("photo.jpg", mode="painting")
"""
import cv2
import numpy as np
import sys
from collections import Counter
from pathlib import Path

# --- Skill paths (stable in container) ---
_SKILL_ROOT = Path(__file__).resolve().parent.parent  # image-to-svg/
_SKILLS_DIR = _SKILL_ROOT.parent                       # /mnt/skills/user/

sys.path.insert(0, str(_SKILLS_DIR / "flowing" / "scripts"))

from flowing import task, Flow

# --- Mode presets ---
MODES = {
    "graphic":      {"K": 28, "dark_lum": 55, "compactness_min": 0.04, "edge_density_min": 0.10, "isolation_filter": False, "min_area": 30},
    "illustration": {"K": 40, "dark_lum": 55, "compactness_min": 0.06, "edge_density_min": 0.12, "isolation_filter": True,  "min_area": 40},
    "painting":     {"K": 56, "dark_lum": 55, "compactness_min": 0.08, "edge_density_min": 0.15, "isolation_filter": True,  "min_area": 40},
    "photo":        {"K": 64, "dark_lum": 55, "compactness_min": 0.08, "edge_density_min": 0.15, "isolation_filter": True,  "min_area": 40},
}

# --- Palette presets (ordered darkest → lightest) ---
PALETTES = {
    "bw":       ["#000000", "#ffffff"],
    "mono3":    ["#000000", "#999999", "#ffffff"],
    "mono4":    ["#000000", "#555555", "#aaaaaa", "#ffffff"],
    "pop":      ["#141414", "#ff1493", "#ffd700", "#00bfff"],
    "pop2":     ["#1e1e1e", "#dc143c", "#32cd32", "#ffa500"],
    "neon":     ["#0d0d0d", "#ff00ff", "#00ff00", "#ffff00", "#00ffff"],
    "warhol4":  ["#1a1a1a", "#e4007c", "#f5a623", "#50e3c2"],
    "warhol6":  ["#0a0a0a", "#dc143c", "#ff69b4", "#ffd700", "#32cd32", "#00bfff"],
    "warhol8":  ["#0a0a0a", "#dc143c", "#ff69b4", "#ffd700", "#32cd32", "#00bfff", "#ff8c00", "#f5f5f5"],
    "sunset":   ["#1a0a2e", "#e74c3c", "#f39c12", "#f5e6cc"],
    "ocean":    ["#0c2340", "#1e6091", "#48c9b0", "#e8f4f8"],
}

# --- Pipeline config (module-level, set by configure()) ---
_cfg = {}


def _hex_luminance(hex_color):
    """Compute luminance from a hex color string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def configure(source_path, mode="painting", svg_width=1000, palette=None, bg_color=None, smooth=None, **overrides):
    """Set pipeline config. Called internally by image_to_svg().

    Any key in MODES presets can be overridden: K, dark_lum,
    compactness_min, edge_density_min, isolation_filter, min_area.

    palette: List of hex color strings or a preset name from PALETTES.
             Colors are mapped to shape clusters sorted by luminance
             (palette[0] = darkest cluster, palette[-1] = lightest).
    bg_color: Override background color (hex string). If None, uses
              detected background. With palette, defaults to lightest
              palette color.
    smooth:  ImageMagick preprocessing for texture removal before quantization.
             Reduces shape count 20-30% by smoothing noisy regions while
             preserving edges. Options:
             - None (default): pipeline's bilateral + Gaussian only
             - "oilpaint" or "oilpaint:N": IM -paint N (default N=8)
             - "kuwahara" or "kuwahara:N": IM -kuwahara N (default N=5)
             Runs before the bilateral filter, so both are complementary.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {list(MODES.keys())}")
    # Resolve palette preset name to list
    if isinstance(palette, str):
        if palette not in PALETTES:
            raise ValueError(f"Unknown palette '{palette}'. Choose from: {list(PALETTES.keys())}")
        palette = PALETTES[palette]
    _cfg.update({
        "source_path": str(source_path), "svg_width": svg_width,
        "palette": palette, "bg_color": bg_color, "smooth": smooth,
        **MODES[mode], **overrides,
    })



# --- Compiled nearest-neighbor acceleration ---

_NN_SRC = Path(__file__).resolve().parent / "nn_assign.c"
_NN_BIN = Path(__file__).resolve().parent / "nn_assign"


def _ensure_nn_binary():
    """Compile nn_assign.c if binary is missing or stale."""
    if _NN_BIN.exists() and _NN_BIN.stat().st_mtime >= _NN_SRC.stat().st_mtime:
        return True
    import subprocess, shutil
    gcc = shutil.which("gcc")
    if not gcc:
        return False
    try:
        subprocess.run(
            [gcc, "-O3", "-march=native", "-o", str(_NN_BIN), str(_NN_SRC), "-lm"],
            capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _nn_assign_fast(pixels_u8, centers_u8, K):
    """Assign each pixel to nearest center. Uses compiled C (27x faster) with numpy fallback."""
    import subprocess, tempfile, os

    if _ensure_nn_binary():
        px_f = tempfile.mktemp(suffix=".bin")
        ct_f = tempfile.mktemp(suffix=".bin")
        try:
            pixels_u8.tofile(px_f)
            centers_u8.tofile(ct_f)
            result = subprocess.run(
                [str(_NN_BIN), px_f, ct_f, str(K)],
                capture_output=True, check=True,
            )
            return np.frombuffer(result.stdout, dtype=np.int32).copy()
        finally:
            for f in (px_f, ct_f):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    # Fallback: numpy batched assignment
    full_px_f = pixels_u8.astype(np.float32)
    centers_f = centers_u8.astype(np.float32)
    batch_size = 50000
    full_labels = np.empty(len(full_px_f), dtype=np.int32)
    for i in range(0, len(full_px_f), batch_size):
        chunk = full_px_f[i:i + batch_size]
        dists = np.linalg.norm(
            chunk[:, None, :] - centers_f[None, :, :], axis=2
        )
        full_labels[i:i + batch_size] = np.argmin(dists, axis=1)
    return full_labels

# --- ImageMagick preprocessing ---

def _im_smooth(source_path, smooth_spec):
    """Apply ImageMagick smoothing filter. Returns path to smoothed image.

    Args:
        source_path: Path to source image
        smooth_spec: "oilpaint", "oilpaint:N", "kuwahara", or "kuwahara:N"

    Returns:
        Path to preprocessed temp file, or source_path if smooth is None/unavailable.
    """
    import subprocess, shutil, tempfile

    if not smooth_spec:
        return source_path

    convert = shutil.which("convert") or shutil.which("magick")
    if not convert:
        print("  smooth: ImageMagick not found, skipping")
        return source_path

    # Parse "filter:strength" or just "filter"
    parts = smooth_spec.split(":", 1)
    filter_name = parts[0].lower()
    defaults = {"oilpaint": 8, "kuwahara": 5}
    if filter_name not in defaults:
        raise ValueError(f"Unknown smooth filter '{filter_name}'. Choose from: oilpaint, kuwahara")
    strength = int(parts[1]) if len(parts) > 1 else defaults[filter_name]

    im_flags = {"oilpaint": "-paint", "kuwahara": "-kuwahara"}
    flag = im_flags[filter_name]

    out = tempfile.mktemp(suffix=".jpg")
    try:
        subprocess.run(
            [convert, source_path, flag, str(strength), out],
            capture_output=True, check=True,
        )
        print(f"  smooth: {filter_name} strength={strength}")
        return out
    except subprocess.CalledProcessError as e:
        print(f"  smooth: ImageMagick failed ({e}), skipping")
        return source_path


# --- Pipeline steps ---

@task
def preprocess():
    # Apply optional ImageMagick smoothing before OpenCV processing
    source = _im_smooth(_cfg["source_path"], _cfg.get("smooth"))
    img = cv2.imread(source)
    if img is None:
        raise FileNotFoundError(f"Cannot read: {source}")
    # Clean up temp file if smoothing was applied
    if source != _cfg["source_path"]:
        import os
        try:
            os.unlink(source)
        except OSError:
            pass
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    blurred = cv2.bilateralFilter(rgb, 9, 50, 50)
    blurred = cv2.GaussianBlur(blurred, (3, 3), 0)
    h, w = blurred.shape[:2]
    print(f"  preprocess: {w}x{h}")
    return {"blurred": blurred, "h": h, "w": w}


@task(depends_on=[preprocess])
def quantize(preprocess):
    blurred, h, w = preprocess["blurred"], preprocess["h"], preprocess["w"]
    K = _cfg["K"]

    small = cv2.resize(blurred, (600, int(600 * h / w)))
    pixels = small.reshape(-1, 3).astype(np.float32)
    from sklearn.cluster import MiniBatchKMeans
    mbk = MiniBatchKMeans(n_clusters=K, batch_size=4096, max_iter=30,
                          n_init=2, random_state=42)
    mbk.fit(pixels)
    centers = mbk.cluster_centers_.astype(np.uint8)

    # Map centers to full resolution
    full_px = blurred.reshape(-1, 3).astype(np.uint8)
    full_labels = _nn_assign_fast(full_px, centers, K)

    label_img = full_labels.reshape(h, w)
    sorted_clusters = sorted(Counter(full_labels).items(), key=lambda x: -x[1])

    print(f"  quantize: K={K}, {len(sorted_clusters)} clusters")
    return {
        "label_img": label_img, "centers": centers, "full_labels": full_labels,
        "sorted_clusters": sorted_clusters, "h": h, "w": w,
    }


@task(depends_on=[quantize])
def detect_background(quantize):
    label_img = quantize["label_img"]
    centers = quantize["centers"]
    full_labels = quantize["full_labels"]
    sorted_clusters = quantize["sorted_clusters"]
    h, w = quantize["h"], quantize["w"]

    bg_clusters = set()
    for cid, cnt in sorted_clusters:
        pct = cnt / len(full_labels) * 100
        mask = label_img == cid
        edge_px = mask[0, :].sum() + mask[-1, :].sum() + mask[:, 0].sum() + mask[:, -1].sum()
        edge_ratio = edge_px / (2 * (h + w))
        if edge_ratio > 0.15 and pct > 3.0:
            bg_clusters.add(cid)

    # Weighted average background color
    bg_total = sum(cnt for cid, cnt in sorted_clusters if cid in bg_clusters)
    bg_color = np.zeros(3, dtype=np.float64)
    for cid, cnt in sorted_clusters:
        if cid in bg_clusters:
            bg_color += centers[cid].astype(np.float64) * cnt
    bg_color = (bg_color / bg_total).astype(np.uint8) if bg_total > 0 else np.array([0, 0, 0], dtype=np.uint8)
    bg_hex = f"#{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x}"

    print(f"  detect_background: {len(bg_clusters)} clusters, {bg_hex}")
    return {"bg_clusters": bg_clusters, "bg_hex": bg_hex}


@task(depends_on=[quantize])
def edge_map(quantize):
    """Sobel edge detection using cv2 (85x faster than Python pixel loop)."""
    h, w = quantize["h"], quantize["w"]
    img = cv2.imread(_cfg["source_path"])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (w, h))
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    edge_img = np.clip(mag, 0, 255).astype(np.uint8)
    edge_img[edge_img <= 50] = 0
    print(f"  edge_map: {edge_img.shape}")
    return {"edge_img": edge_img}


@task(depends_on=[quantize, detect_background, edge_map])
def extract_contours(quantize, detect_background, edge_map):
    label_img = quantize["label_img"]
    centers = quantize["centers"]
    sorted_clusters = quantize["sorted_clusters"]
    h, w = quantize["h"], quantize["w"]
    bg_clusters = detect_background["bg_clusters"]
    edge_img = edge_map["edge_img"]

    DARK_LUM = _cfg["dark_lum"]
    COMPACT_MIN = _cfg["compactness_min"]
    EDGE_DENS_MIN = _cfg["edge_density_min"]
    USE_ISOLATION = _cfg["isolation_filter"]
    MIN_AREA = _cfg["min_area"]

    SVG_W = _cfg["svg_width"]
    SVG_H = int(SVG_W * h / w)
    scale_x, scale_y = SVG_W / w, SVG_H / h

    # Dark territory mask (used for dark shape gating below)
    dark_territory = np.zeros((h, w), dtype=np.uint8)
    for cid, cnt in sorted_clusters:
        if cid in bg_clusters:
            continue
        c = centers[cid]
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        if lum < DARK_LUM:
            dark_territory[label_img == cid] = 255

    k_morph = np.ones((3, 3), np.uint8)
    k_dilate = np.ones((3, 3), np.uint8)
    shapes = []

    for cid, cnt in sorted_clusters:
        if cid in bg_clusters:
            continue

        c = centers[cid]
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        is_dark = lum < DARK_LUM
        color_hex = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"

        mask = (label_img == cid).astype(np.uint8) * 255

        # Light dilation for morphological cleanup only.
        # Gap coverage is handled by stroke=fill in assemble_svg.
        mask = cv2.dilate(mask, k_dilate, iterations=1)

        # Morphological cleanup
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_morph, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_morph, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < MIN_AREA:
                continue

            peri = cv2.arcLength(contour, True)
            compactness = (4 * 3.14159 * area / (peri * peri)) if peri > 0 else 1

            # Dark shape gating
            if is_dark:
                contour_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(contour_mask, [contour], -1, 255, -1)
                edge_overlap = cv2.bitwise_and(edge_img, contour_mask)
                edge_density = edge_overlap.sum() / max(contour_mask.sum(), 1)

                if not (compactness > COMPACT_MIN or edge_density > EDGE_DENS_MIN
                        or area > (h * w * 0.01)):
                    continue

                # Isolation filter: small dark shapes surrounded by non-dark = artifacts
                if USE_ISOLATION and area < 500:
                    border = cv2.dilate(contour_mask, np.ones((11, 11), np.uint8), 1) & ~contour_mask
                    border_dark = cv2.bitwise_and(dark_territory, border)
                    if border_dark.sum() / max(border.sum(), 1) < 0.3:
                        continue

            # Simplify and convert to SVG path
            eps = 0.002 * peri
            approx = cv2.approxPolyDP(contour, eps, True)
            pts = approx.reshape(-1, 2).astype(float)
            pts[:, 0] *= scale_x
            pts[:, 1] *= scale_y

            path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
            for p in pts[1:]:
                path_d += f" L {p[0]:.1f},{p[1]:.1f}"
            path_d += " Z"

            shapes.append({"path": path_d, "color": color_hex, "area": area})

    # Painter's algorithm: largest shapes first (behind)
    shapes.sort(key=lambda x: -x["area"])
    print(f"  extract_contours: {len(shapes)} shapes")
    return {"shapes": shapes, "svg_w": SVG_W, "svg_h": SVG_H}


@task(depends_on=[extract_contours, detect_background])
def assemble_svg(extract_contours, detect_background):
    shapes = extract_contours["shapes"]
    SVG_W = extract_contours["svg_w"]
    SVG_H = extract_contours["svg_h"]
    bg_hex = detect_background["bg_hex"]

    palette = _cfg.get("palette")
    bg_override = _cfg.get("bg_color")

    # --- Palette remapping ---
    if palette:
        # Collect unique shape colors, sort by luminance
        unique_colors = sorted(set(s["color"] for s in shapes), key=_hex_luminance)
        n_colors = len(unique_colors)
        n_palette = len(palette)

        # Build mapping: divide unique colors into n_palette bands by luminance rank
        color_map = {}
        for i, color in enumerate(unique_colors):
            # Map color index to palette index proportionally
            palette_idx = min(int(i * n_palette / n_colors), n_palette - 1)
            color_map[color] = palette[palette_idx]

        # Remap shapes
        for s in shapes:
            s["color"] = color_map[s["color"]]

        # Background: explicit override > lightest palette entry > detected
        if bg_override:
            bg_hex = bg_override
        else:
            bg_hex = palette[-1]  # lightest palette color for bg

        print(f"  palette: {n_colors} colors → {n_palette} palette entries")
    elif bg_override:
        bg_hex = bg_override

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}">',
        f'  <rect width="{SVG_W}" height="{SVG_H}" fill="{bg_hex}"/>',
    ]
    for s in shapes:
        lines.append(f'  <path d="{s["path"]}" fill="{s["color"]}" stroke="{s["color"]}" stroke-width="4" stroke-linejoin="round"/>')
    lines.append("</svg>")

    svg_content = "\n".join(lines)
    print(f"  assemble_svg: {len(svg_content)} bytes, {len(shapes)} paths")
    return {"svg": svg_content, "shape_count": len(shapes)}


# --- Assembly (pure function, no global state) ---

def _assemble_pure(shapes, svg_w, svg_h, bg_hex, palette=None, bg_color=None):
    """Assemble SVG from shapes. Does NOT mutate input shapes.

    Args:
        shapes: List of {"path": str, "color": hex, "area": float}
        svg_w, svg_h: ViewBox dimensions
        bg_hex: Detected background color
        palette: Optional list of hex colors (darkest→lightest) or preset name
        bg_color: Optional background color override

    Returns:
        SVG string
    """
    if isinstance(palette, str):
        if palette not in PALETTES:
            raise ValueError(f"Unknown palette '{palette}'. Choose from: {list(PALETTES.keys())}")
        palette = PALETTES[palette]

    # Work on copies to avoid mutating shared shapes
    if palette:
        unique_colors = sorted(set(s["color"] for s in shapes), key=_hex_luminance)
        n_colors, n_palette = len(unique_colors), len(palette)
        color_map = {}
        for i, color in enumerate(unique_colors):
            palette_idx = min(int(i * n_palette / n_colors), n_palette - 1)
            color_map[color] = palette[palette_idx]

        bg_hex = bg_color if bg_color else palette[-1]
    elif bg_color:
        bg_hex = bg_color

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}">',
        f'  <rect width="{svg_w}" height="{svg_h}" fill="{bg_hex}"/>',
    ]
    for s in shapes:
        c = color_map[s["color"]] if palette and s["color"] in color_map else s["color"]
        lines.append(f'  <path d="{s["path"]}" fill="{c}" stroke="{c}" stroke-width="4" stroke-linejoin="round"/>')
    lines.append("</svg>")
    return "\n".join(lines)


# --- Public API ---

def image_to_svg(source_path, mode="painting", svg_width=1000, palette=None, bg_color=None, smooth=None, **overrides):
    """Convert a raster image to SVG.

    Args:
        source_path: Path to source image (jpg, png, etc.)
        mode: One of "graphic", "illustration", "painting", "photo"
        svg_width: SVG viewBox width (height computed from aspect ratio)
        palette: List of hex colors or preset name ("pop", "warhol4", "mono4", etc.)
                 Maps to clusters by luminance: palette[0]=darkest, [-1]=lightest.
        bg_color: Override background color (hex). With palette, defaults to lightest entry.
        smooth: ImageMagick preprocessing ("oilpaint", "oilpaint:N", "kuwahara", "kuwahara:N").
                Reduces shape count/SVG size 20-30%. Requires ImageMagick on PATH.
        **overrides: Override any mode preset (K, dark_lum, compactness_min,
                     edge_density_min, isolation_filter, min_area)

    Returns:
        (svg_string, flow) — the SVG content and the Flow object for inspection
    """
    configure(source_path, mode=mode, svg_width=svg_width, palette=palette, bg_color=bg_color, smooth=smooth, **overrides)
    flow = Flow(assemble_svg)
    flow.run()
    result = flow.value(assemble_svg)
    return result["svg"], flow


def image_to_svg_batch(source_path, variants, svg_width=1000):
    """Convert one image to multiple SVG variants, sharing computation.

    Runs preprocess, quantize, edge_map, detect_background, and extract_contours
    ONCE per unique K value. Only assembly (palette remapping) fans out per variant.

    Args:
        source_path: Path to source image
        variants: List of dicts, each with:
            - name (str): Key for results dict
            - mode (str): "graphic", "illustration", "painting", "photo"
            - palette (optional): Hex list or preset name
            - bg_color (optional): Background override
            - K, dark_lum, etc. (optional): Override mode defaults
        svg_width: SVG viewBox width (shared across all variants)

    Returns:
        Dict of {name: svg_string}

    Example:
        results = image_to_svg_batch("photo.jpg", [
            {"name": "natural",  "mode": "poster"},
            {"name": "warhol",   "mode": "graphic", "K": 12, "palette": "warhol4"},
            {"name": "neon",     "mode": "graphic", "K": 12, "palette": "neon"},
            {"name": "sunset",   "mode": "graphic", "K": 12, "palette": "sunset"},
        ])
    """
    import time
    t0 = time.time()

    # Resolve each variant's effective config
    resolved = []
    for v in variants:
        name = v["name"]
        mode = v.get("mode", "painting")
        if mode not in MODES:
            raise ValueError(f"Unknown mode '{mode}' in variant '{name}'")
        cfg = {**MODES[mode], **{k: v[k] for k in v if k not in ("name", "mode", "palette", "bg_color", "smooth")}}
        cfg["palette"] = v.get("palette")
        cfg["bg_color"] = v.get("bg_color")
        cfg["smooth"] = v.get("smooth")
        cfg["name"] = name
        resolved.append(cfg)

    # Group by K (and dark-shape gating params that affect contour extraction)
    from collections import defaultdict
    groups = defaultdict(list)
    for cfg in resolved:
        groups[cfg["K"]].append(cfg)

    results = {}

    for K, group_variants in groups.items():
        tg = time.time()
        # Use loosest dark-shape gating for shared extraction
        # (most permissive = smallest thresholds = keeps all plausible shapes)
        loosest_compact = min(v["compactness_min"] for v in group_variants)
        loosest_edge = min(v["edge_density_min"] for v in group_variants)
        use_isolation = any(v.get("isolation_filter", True) for v in group_variants)
        min_area = min(v["min_area"] for v in group_variants)

        # Configure for this K group
        configure(source_path, svg_width=svg_width,
                  smooth=group_variants[0].get("smooth"),
                  K=K, dark_lum=group_variants[0]["dark_lum"],
                  compactness_min=loosest_compact,
                  edge_density_min=loosest_edge,
                  isolation_filter=use_isolation,
                  min_area=min_area)

        # Run full pipeline through extract_contours (once per K)
        flow = Flow(assemble_svg)
        flow.run()

        # Extract shared intermediate results
        contour_result = flow.value(extract_contours)
        bg_result = flow.value(detect_background)
        shapes = contour_result["shapes"]
        svg_w = contour_result["svg_w"]
        svg_h = contour_result["svg_h"]
        bg_hex = bg_result["bg_hex"]

        print(f"  batch K={K}: pipeline {time.time()-tg:.1f}s, {len(shapes)} shapes, {len(group_variants)} variants")

        # Fan out: assemble each variant (fast — just string ops)
        for cfg in group_variants:
            palette = cfg["palette"]
            if isinstance(palette, str):
                palette = PALETTES.get(palette, palette)
            svg = _assemble_pure(shapes, svg_w, svg_h, bg_hex,
                                 palette=palette, bg_color=cfg["bg_color"])
            results[cfg["name"]] = svg
            print(f"    {cfg['name']}: {len(svg)//1024}KB")

    print(f"  batch total: {time.time()-t0:.1f}s, {len(results)} variants")
    return results
