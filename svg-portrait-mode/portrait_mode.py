"""
SVG Portrait Mode v0.6.1 — Selective simplification.

One pipeline pass at high K → zone-aware contour simplification → optional
per-zone style transforms. No clipPaths, no multi-pipeline compositing.

Usage:
    from portrait_mode import portrait_mode

    # Agent-annotated (recommended):
    svg, stats = portrait_mode("photo.jpg",
        focus_targets=[{'bbox': (215, 125, 295, 195), 'label': 'face'}],
        focus_edges=[
            {'bbox': (214, 170, 310, 290), 'label': 'beard'},
            {'bbox': (210, 415, 300, 505), 'label': 'hands'},
        ])

    # With style transforms (muted background):
    svg, stats = portrait_mode("photo.jpg",
        focus_targets=[{'bbox': (215, 125, 295, 195), 'label': 'face'}],
        style_transforms={'background': 'desaturate:0.7', 'periphery': 'desaturate:0.3'})

    # No annotations (MP fallback):
    svg, stats = portrait_mode("photo.jpg")
"""

import sys
import cv2
import numpy as np
import os
import time

# Pipeline imports
sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')

# Zone constants
ZONE_BG = 0
ZONE_PERIPHERY = 1
ZONE_EDGE = 2
ZONE_TARGET = 3

ZONE_NAMES = {
    ZONE_BG: 'background',
    ZONE_PERIPHERY: 'periphery',
    ZONE_EDGE: 'edge',
    ZONE_TARGET: 'target',
}

# Per-zone simplification defaults
# epsilon_mult: multiplier on base epsilon (0.002 * perimeter)
#   Unified at 1.0 across zones to prevent inter-zone tearing (issue #512).
#   Visual hierarchy is achieved via min_area (shape count) instead.
# min_area: minimum contour area in pixels²
ZONE_SIMPLIFICATION = {
    ZONE_TARGET:     {'epsilon_mult': 1.0,  'min_area': 15},
    ZONE_EDGE:       {'epsilon_mult': 1.0,  'min_area': 40},
    ZONE_PERIPHERY:  {'epsilon_mult': 1.0,  'min_area': 150},
    ZONE_BG:         {'epsilon_mult': 1.0,  'min_area': 400},
}

# MediaPipe face mesh landmark indices
_FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
              397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
              172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


# ─── MediaPipe helpers (optional) ───

def _ensure_models():
    """Download MP models if not present."""
    import urllib.request
    models = {
        'blaze_face_short_range.tflite':
            'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite',
        'face_landmarker.task':
            'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task',
    }
    for fname, url in models.items():
        path = f'/home/claude/{fname}'
        if not os.path.exists(path):
            print(f"    Downloading {fname}...")
            urllib.request.urlretrieve(url, path)


def _get_face_landmarks(image_path):
    """Get face mesh landmarks (478 points) if available.

    Returns list of (x, y) in pixel coords, or None.
    """
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision
    except ImportError:
        return None

    _ensure_models()

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    try:
        landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/face_landmarker.task'),
                num_faces=1))
        result = landmarker.detect(mp_img)
        landmarker.close()

        if result.face_landmarks:
            lm = result.face_landmarks[0]
            return [(int(p.x * w), int(p.y * h)) for p in lm]
    except Exception as e:
        print(f"    Landmark detection failed: {e}")

    return None


def _get_face_bbox(image_path):
    """Get face bounding box from MediaPipe face detector.

    Returns (x1, y1, x2, y2) or None.
    """
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import vision
    except ImportError:
        return None

    _ensure_models()

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    try:
        det = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/blaze_face_short_range.tflite'),
                min_detection_confidence=0.3))
        result = det.detect(mp_img)
        det.close()

        if result.detections:
            d = result.detections[0]
            bbox = d.bounding_box
            pad = int(bbox.width * 0.2)
            x1 = max(0, bbox.origin_x - pad)
            y1 = max(0, bbox.origin_y - pad)
            x2 = min(w, bbox.origin_x + bbox.width + pad)
            y2 = min(h, bbox.origin_y + bbox.height + int(bbox.height * 0.15))
            return (x1, y1, x2, y2)
    except Exception as e:
        print(f"    Face detection failed: {e}")

    return None


def _landmarks_to_mask(landmarks, indices, h, w, dilate=0):
    """Convert landmark indices to a filled polygon mask."""
    pts = np.array([landmarks[i] for i in indices], dtype=np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    if dilate > 0:
        kernel = np.ones((dilate, dilate), np.uint8)
        mask = cv2.dilate(mask, kernel)
    return mask


# ─── Zone map construction ───

# @lat: [[visual-pipeline#Foveated Vectorization]]
def build_zone_map(h, w, focus_targets=None, focus_edges=None,
                   landmarks=None, face_bbox=None):
    """Build pixel-level zone map from agent annotations and optional MP data.

    Without agent annotations, falls back to MP face detection.
    Without either, everything is background (no foveation).

    Args:
        h, w: Image dimensions
        focus_targets: Agent-provided [{'bbox': (x1,y1,x2,y2), 'label': str}]
        focus_edges: Agent-provided [{'bbox': (x1,y1,x2,y2), 'label': str}]
        landmarks: MP face mesh landmarks [(x,y), ...]
        face_bbox: MP face detector bbox (x1,y1,x2,y2)

    Returns:
        zone_map: uint8 array with ZONE_* values per pixel
    """
    zone_map = np.full((h, w), ZONE_BG, dtype=np.uint8)

    # Focus edges: agent-identified compositionally important areas
    if focus_edges:
        for fe in focus_edges:
            x1, y1, x2, y2 = fe['bbox']
            # Pad 15%
            bw, bh = x2 - x1, y2 - y1
            px, py = int(bw * 0.15), int(bh * 0.15)
            x1p, y1p = max(0, x1 - px), max(0, y1 - py)
            x2p, y2p = min(w, x2 + px), min(h, y2 + py)
            zone_map[y1p:y2p, x1p:x2p] = np.maximum(
                zone_map[y1p:y2p, x1p:x2p], ZONE_EDGE)

    # Focus targets: where the eye goes first
    if focus_targets:
        for ft in focus_targets:
            label = ft.get('label', 'target')
            if label == 'face' and landmarks is not None:
                face_mask = _landmarks_to_mask(landmarks, _FACE_OVAL, h, w, dilate=12)
                zone_map[face_mask > 128] = ZONE_TARGET
            else:
                x1, y1, x2, y2 = ft['bbox']
                bw, bh = x2 - x1, y2 - y1
                px, py = int(bw * 0.10), int(bh * 0.10)
                x1p, y1p = max(0, x1 - px), max(0, y1 - py)
                x2p, y2p = min(w, x2 + px), min(h, y2 + py)
                zone_map[y1p:y2p, x1p:x2p] = ZONE_TARGET
    elif face_bbox is not None:
        # Backward compat: no annotations, use MP face detection
        if landmarks is not None:
            face_mask = _landmarks_to_mask(landmarks, _FACE_OVAL, h, w, dilate=12)
            zone_map[face_mask > 128] = ZONE_TARGET
        else:
            x1, y1, x2, y2 = face_bbox
            zone_map[y1:y2, x1:x2] = ZONE_TARGET

    # Periphery: anything "between" target/edge and background.
    # Strategy: dilate the target+edge union to create a periphery buffer.
    fg_mask = (zone_map >= ZONE_EDGE).astype(np.uint8)
    if fg_mask.any():
        # Periphery = dilated foreground minus foreground itself
        peri_size = max(h, w) // 8  # ~12% of image dimension
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (peri_size, peri_size))
        dilated = cv2.dilate(fg_mask, kernel)
        periphery = (dilated > 0) & (zone_map == ZONE_BG)
        zone_map[periphery] = ZONE_PERIPHERY

    # Report
    total = h * w
    for zv, zn in ZONE_NAMES.items():
        pct = 100 * np.sum(zone_map == zv) / total
        if pct > 0:
            print(f"    {zn}: {pct:.1f}%")

    return zone_map


# ─── Zone-aware contour extraction ───

def _assign_zone(contour, zone_map, h, w):
    """Assign a contour to the highest zone covering >30% of its area.

    Falls back to centroid zone if no zone covers >30%.
    """
    # Fast path: check centroid first
    M = cv2.moments(contour)
    if M["m00"] > 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        cx = min(max(cx, 0), w - 1)
        cy = min(max(cy, 0), h - 1)
        centroid_zone = zone_map[cy, cx]
    else:
        centroid_zone = ZONE_BG

    # For small contours, centroid is sufficient
    area = cv2.contourArea(contour)
    if area < 500:
        return centroid_zone

    # For larger contours, check zone coverage to prevent
    # focal shapes from being simplified
    contour_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(contour_mask, [contour], -1, 255, -1)
    total_px = contour_mask.sum() // 255

    if total_px == 0:
        return centroid_zone

    best_zone = centroid_zone
    for zone_val in [ZONE_TARGET, ZONE_EDGE, ZONE_PERIPHERY]:
        zone_pixels = np.sum((contour_mask > 0) & (zone_map == zone_val))
        if zone_pixels / total_px > 0.30:
            best_zone = max(best_zone, zone_val)
            break  # highest zone found

    return best_zone


def zone_extract_contours(label_img, centers, sorted_clusters, h, w,
                          bg_clusters, edge_img, zone_map, svg_width,
                          dark_lum=55, base_epsilon=0.002):
    """Extract contours with zone-aware simplification.

    Like pipeline.extract_contours but applies different epsilon and min_area
    per zone. Returns shapes tagged with their zone.

    Args:
        label_img, centers, sorted_clusters, h, w: From quantize step
        bg_clusters: Set of background cluster IDs
        edge_img: Sobel edge map
        zone_map: Per-pixel zone assignment (h x w, values ZONE_*)
        svg_width: Target SVG width
        dark_lum: Dark shape luminance threshold
        base_epsilon: Base epsilon factor (multiplied by zone epsilon_mult)

    Returns:
        dict with 'shapes' (list of {path, color, area, zone}),
        'svg_w', 'svg_h', 'zone_counts'
    """
    SVG_W = svg_width
    SVG_H = int(SVG_W * h / w)
    scale_x, scale_y = SVG_W / w, SVG_H / h

    # Dark territory mask (for dark shape gating)
    dark_territory = np.zeros((h, w), dtype=np.uint8)
    for cid, cnt in sorted_clusters:
        if cid in bg_clusters:
            continue
        c = centers[cid]
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        if lum < dark_lum:
            dark_territory[label_img == cid] = 255

    k_morph = np.ones((3, 3), np.uint8)
    k_dilate = np.ones((3, 3), np.uint8)
    shapes = []
    zone_counts = {zn: 0 for zn in ZONE_NAMES.values()}

    for cid, cnt in sorted_clusters:
        if cid in bg_clusters:
            continue

        c = centers[cid]
        lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        is_dark = lum < dark_lum
        color_hex = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"

        mask = (label_img == cid).astype(np.uint8) * 255
        mask = cv2.dilate(mask, k_dilate, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_morph, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k_morph, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)

            # Assign zone BEFORE filtering — zone determines thresholds
            zone = _assign_zone(contour, zone_map, h, w)
            zone_cfg = ZONE_SIMPLIFICATION[zone]

            if area < zone_cfg['min_area']:
                continue

            peri = cv2.arcLength(contour, True)
            compactness = (4 * 3.14159 * area / (peri * peri)) if peri > 0 else 1

            # Dark shape gating (same as pipeline, but with zone-adjusted thresholds)
            # Target/edge zones use looser gating to preserve detail
            if is_dark:
                compact_min = 0.04 if zone >= ZONE_EDGE else 0.08
                edge_dens_min = 0.10 if zone >= ZONE_EDGE else 0.15

                contour_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(contour_mask, [contour], -1, 255, -1)
                edge_overlap = cv2.bitwise_and(edge_img, contour_mask)
                edge_density = edge_overlap.sum() / max(contour_mask.sum(), 1)

                if not (compactness > compact_min or edge_density > edge_dens_min
                        or area > (h * w * 0.01)):
                    continue

                # Isolation filter for background/periphery only
                if zone <= ZONE_PERIPHERY and area < 500:
                    border = cv2.dilate(contour_mask, np.ones((11, 11), np.uint8), 1) & ~contour_mask
                    border_dark = cv2.bitwise_and(dark_territory, border)
                    if border_dark.sum() / max(border.sum(), 1) < 0.3:
                        continue

            # Zone-aware simplification
            eps = base_epsilon * peri * zone_cfg['epsilon_mult']
            approx = cv2.approxPolyDP(contour, eps, True)
            pts = approx.reshape(-1, 2).astype(float)
            pts[:, 0] *= scale_x
            pts[:, 1] *= scale_y

            path_d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
            for p in pts[1:]:
                path_d += f" L {p[0]:.1f},{p[1]:.1f}"
            path_d += " Z"

            zone_name = ZONE_NAMES[zone]
            shapes.append({
                "path": path_d,
                "color": color_hex,
                "area": area,
                "zone": zone_name,
            })
            zone_counts[zone_name] += 1

    # Painter's algorithm: largest shapes first
    shapes.sort(key=lambda x: -x["area"])

    print(f"  zone_extract: {len(shapes)} shapes")
    for zn, zc in zone_counts.items():
        if zc > 0:
            print(f"    {zn}: {zc}")

    return {"shapes": shapes, "svg_w": SVG_W, "svg_h": SVG_H,
            "zone_counts": zone_counts}


# ─── Per-zone style transforms ───

def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _desaturate(hex_color, amount):
    """Desaturate a color by amount (0=none, 1=full grayscale)."""
    r, g, b = _hex_to_rgb(hex_color)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    r2 = r + (gray - r) * amount
    g2 = g + (gray - g) * amount
    b2 = b + (gray - b) * amount
    return _rgb_to_hex(r2, g2, b2)


def _mute(hex_color, amount):
    """Mute a color toward mid-gray by amount (0=none, 1=full gray)."""
    r, g, b = _hex_to_rgb(hex_color)
    r2 = r + (128 - r) * amount
    g2 = g + (128 - g) * amount
    b2 = b + (128 - b) * amount
    return _rgb_to_hex(r2, g2, b2)


def _warm(hex_color, amount):
    """Shift color temperature warmer (positive) or cooler (negative)."""
    r, g, b = _hex_to_rgb(hex_color)
    shift = amount * 20  # subtle
    r2 = min(255, max(0, r + shift))
    b2 = min(255, max(0, b - shift))
    return _rgb_to_hex(r2, g, b2)


def _opacity(amount):
    """Return opacity value (for the style attribute)."""
    return max(0.0, min(1.0, amount))


def _apply_color_transform(hex_color, transform_spec):
    """Apply a style transform to a single color.

    Specs:
        'desaturate:0.7' — desaturate by 70%
        'mute:0.3' — mute toward gray by 30%
        'warm:0.5' / 'cool:0.5' — temperature shift
        'grayscale' — full grayscale

    Returns transformed hex color.
    """
    if ':' in transform_spec:
        name, val = transform_spec.split(':', 1)
        val = float(val)
    else:
        name = transform_spec
        val = 1.0

    if name == 'desaturate':
        return _desaturate(hex_color, val)
    elif name == 'grayscale':
        return _desaturate(hex_color, 1.0)
    elif name == 'mute':
        return _mute(hex_color, val)
    elif name == 'warm':
        return _warm(hex_color, val)
    elif name == 'cool':
        return _warm(hex_color, -val)
    else:
        return hex_color  # unknown transform, passthrough


# ─── SVG assembly ───

def assemble_svg(shapes, svg_w, svg_h, bg_hex, style_transforms=None):
    """Assemble single SVG with zone-labeled <g> groups.

    Args:
        shapes: List of {path, color, area, zone}
        svg_w, svg_h: ViewBox dimensions
        bg_hex: Background color
        style_transforms: Optional dict of {zone_name: transform_spec}
            e.g. {'background': 'desaturate:0.7', 'periphery': 'mute:0.3'}

    Returns:
        SVG string
    """
    # Group shapes by zone, preserving painter's algorithm order within each
    zone_shapes = {zn: [] for zn in ZONE_NAMES.values()}
    for s in shapes:
        zone_shapes[s['zone']].append(s)

    # Apply style transforms if specified
    if style_transforms:
        for zone_name, spec in style_transforms.items():
            if zone_name in zone_shapes:
                for s in zone_shapes[zone_name]:
                    s = dict(s)  # don't mutate originals... actually we do need to
                    # We'll apply transforms during rendering below

    # Background color transform
    bg_color = bg_hex
    if style_transforms and 'background' in style_transforms:
        bg_color = _apply_color_transform(bg_hex, style_transforms['background'])

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}">',
        f'  <rect width="{svg_w}" height="{svg_h}" fill="{bg_color}"/>',
    ]

    # Render zones back-to-front
    zone_order = ['background', 'periphery', 'edge', 'target']
    for zone_name in zone_order:
        zshapes = zone_shapes.get(zone_name, [])
        if not zshapes:
            continue

        transform_spec = (style_transforms or {}).get(zone_name)

        # Check if zone needs opacity
        opacity_val = None
        if transform_spec and transform_spec.startswith('opacity:'):
            opacity_val = _opacity(float(transform_spec.split(':')[1]))

        group_attrs = f'id="{zone_name}"'
        if opacity_val is not None:
            group_attrs += f' opacity="{opacity_val:.2f}"'

        lines.append(f'  <g {group_attrs}>')

        for s in zshapes:
            color = s['color']
            if transform_spec and not transform_spec.startswith('opacity:'):
                color = _apply_color_transform(color, transform_spec)
            lines.append(
                f'    <path d="{s["path"]}" fill="{color}" '
                f'stroke="{color}" stroke-width="4" stroke-linejoin="round"/>'
            )

        lines.append('  </g>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ─── Main entry point ───

# @lat: [[visual-pipeline#Foveated Vectorization]]
def portrait_mode(image_path,
                  # Zone annotations from calling agent
                  focus_targets=None,
                  focus_edges=None,

                  # Pipeline settings
                  K=96,
                  smooth=None,
                  svg_width=800,

                  # MediaPipe options
                  use_landmarks=True,

                  # Per-zone simplification overrides
                  zone_simplification=None,

                  # Per-zone style transforms
                  style_transforms=None,

                  # Pipeline passthrough
                  **overrides):
    """Create portrait-mode SVG with selective simplification.

    Single pipeline pass at high K → zone-aware contour simplification →
    optional per-zone style transforms → single SVG.

    Args:
        image_path: Path to source image
        focus_targets: [{'bbox': (x1,y1,x2,y2), 'label': str}] — highest detail
        focus_edges: [{'bbox': (x1,y1,x2,y2), 'label': str}] — important areas
        K: Color clusters (default 96, higher = more tonal detail)
        smooth: ImageMagick preprocessing ("oilpaint", "kuwahara:N")
        svg_width: Output SVG width
        use_landmarks: Try MP face landmarks for precise face geometry
        zone_simplification: Override ZONE_SIMPLIFICATION defaults.
            Dict of {ZONE_*: {'epsilon_mult': float, 'min_area': int}}
        style_transforms: Per-zone color transforms.
            Dict of {zone_name: transform_spec}.
            Specs: 'desaturate:0.7', 'mute:0.3', 'grayscale', 'warm:0.5',
                   'cool:0.5', 'opacity:0.8'
        **overrides: Passed to pipeline configure() (dark_lum, etc.)

    Returns:
        (svg_string, stats_dict)
    """
    from pipeline import configure, preprocess, quantize, detect_background, edge_map
    from flowing import task as flow_task, Flow

    t0 = time.time()

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    img_h, img_w = img.shape[:2]

    # Apply zone simplification overrides
    if zone_simplification:
        for zone_val, cfg in zone_simplification.items():
            ZONE_SIMPLIFICATION[zone_val].update(cfg)

    # Gate task: depends on both detect_background and edge_map so the Flow
    # builds a DAG that runs preprocess → quantize → [detect_bg, edge_map]
    @flow_task(depends_on=[detect_background, edge_map])
    def _portrait_gate(detect_background, edge_map):
        return {"bg": detect_background, "edges": edge_map}

    # ─── Step 1: Run pipeline through quantize + edge detection ───
    print(f"[1/4] Pipeline (K={K})")
    configure(image_path, mode="photo", svg_width=svg_width, K=K,
              smooth=smooth, pipeline="fill", **overrides)

    flow = Flow(_portrait_gate)
    flow.run()

    quant = flow.value(quantize)
    bg = flow.value(detect_background)
    edges = flow.value(edge_map)

    t_pipeline = time.time() - t0
    print(f"    Pipeline: {t_pipeline:.1f}s, {len(quant['sorted_clusters'])} clusters")

    # ─── Step 2: Zone detection ───
    print("[2/4] Zone detection")
    h, w = quant['h'], quant['w']

    landmarks = None
    face_bbox = None
    if use_landmarks:
        landmarks = _get_face_landmarks(image_path)
        if landmarks:
            print(f"    Landmarks: 478 points")
        else:
            print(f"    Landmarks: not detected")

    if not focus_targets and landmarks is None:
        face_bbox = _get_face_bbox(image_path)
        if face_bbox:
            print(f"    Face bbox: {face_bbox}")

    zone_map = build_zone_map(h, w, focus_targets, focus_edges,
                               landmarks, face_bbox)

    # ─── Step 3: Zone-aware contour extraction ───
    print("[3/4] Zone-aware extraction")
    result = zone_extract_contours(
        quant['label_img'], quant['centers'], quant['sorted_clusters'],
        h, w, bg['bg_clusters'], edges['edge_img'], zone_map, svg_width,
        dark_lum=overrides.get('dark_lum', 55),
    )

    # ─── Step 4: Assemble SVG ───
    print("[4/4] Assembly")
    svg = assemble_svg(result['shapes'], result['svg_w'], result['svg_h'],
                       bg['bg_hex'], style_transforms=style_transforms)

    t_total = time.time() - t0

    stats = {
        'total': len(result['shapes']),
        'time': t_total,
        'K': K,
        'svg_bytes': len(svg),
        **result['zone_counts'],
    }

    print(f"\n    Total: {stats['total']} paths ({len(svg)//1024}KB) in {t_total:.1f}s")
    for zn in ['target', 'edge', 'periphery', 'background']:
        if result['zone_counts'].get(zn, 0) > 0:
            print(f"      {zn}: {result['zone_counts'][zn]}")

    return svg, stats
