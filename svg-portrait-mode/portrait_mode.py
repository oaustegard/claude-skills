"""
SVG Portrait Mode v0.5.0 — Foveated vectorization.

Four-zone selective detail: Focus Target → Focus Edge → Periphery → Background.
Combines Claude vision annotations, MediaPipe segmentation/landmarks,
and optional saliency for zone assignment.

Usage:
    from portrait_mode import portrait_mode

    # Agent-annotated (recommended):
    svg, stats = portrait_mode("photo.jpg",
        focus_targets=[{'bbox': (215, 125, 295, 195), 'label': 'face'}],
        focus_edges=[
            {'bbox': (214, 170, 310, 290), 'label': 'beard'},
            {'bbox': (210, 415, 300, 505), 'label': 'hands'},
        ])

    # Backward-compatible (MP-only, like v0.3.0):
    svg, stats = portrait_mode("photo.jpg")
"""

import sys
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import re
import subprocess

sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')

# Zone constants (back-to-front compositing order)
ZONE_BG = 0
ZONE_PERIPHERY = 1
ZONE_EDGE = 2
ZONE_TARGET = 3

ZONE_NAMES = {ZONE_BG: 'background', ZONE_PERIPHERY: 'periphery',
              ZONE_EDGE: 'edge', ZONE_TARGET: 'target'}

# MediaPipe face mesh landmark indices
_FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
              397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
              172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
_LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
_RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
_MOUTH = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]

# IM transforms for multi-pass segmentation
_MP_TRANSFORMS = [
    None,  # original
    ['-auto-level'],
    ['-equalize'],
    ['-contrast-stretch', '2%'],
    ['-brightness-contrast', '10x0'],
    ['-brightness-contrast', '-10x0'],
    ['-brightness-contrast', '0x15'],
    ['-brightness-contrast', '0x-15'],
    ['-modulate', '100,130,100'],
    ['-modulate', '100,70,100'],
    ['-colorspace', 'Gray', '-colorspace', 'sRGB'],
    ['-channel', 'R', '-separate', '-colorspace', 'sRGB'],
    ['-channel', 'G', '-separate', '-colorspace', 'sRGB'],
    ['-channel', 'B', '-separate', '-colorspace', 'sRGB'],
    ['-gamma', '1.3'],
    ['-gamma', '0.7'],
    ['-unsharp', '0x2+1+0'],
    ['-blur', '0x1'],
    ['-colorspace', 'LAB', '-channel', 'R', '-separate', '-colorspace', 'sRGB'],
    ['-brightness-contrast', '20x10'],
    ['-brightness-contrast', '-20x-10'],
    ['-modulate', '100,100,110'],
]


# ─── MediaPipe detection ───

def _ensure_models():
    """Download MP models if not present."""
    import urllib.request
    models = {
        'selfie_segmenter.tflite':
            'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite',
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


def get_mp_masks(image_path, multi_pass=True):
    """MediaPipe segmentation, optionally multi-pass for soft boundaries.

    Returns:
        dict with:
          'person': uint8 mask (0 or 255)
          'background': uint8 mask (0 or 255)
          'agreement': float32 0-1 (multi-pass agreement, only if multi_pass=True)
          'face_bbox': (x1, y1, x2, y2) or None
    """
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    _ensure_models()

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    def _segment_once(img_array):
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_array)
        seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/selfie_segmenter.tflite'),
                output_category_mask=True))
        result = seg.segment(mp_img)
        mask = result.category_mask.numpy_view().squeeze().copy()
        seg.close()
        return mask

    if multi_pass:
        # Run segmentation with multiple IM transforms for soft boundaries
        agreement = np.zeros((h, w), dtype=np.float32)
        n_valid = 0

        for i, transform in enumerate(_MP_TRANSFORMS):
            try:
                if transform is None:
                    transformed = img_rgb
                else:
                    tmp_in = tempfile.mktemp(suffix='.png')
                    tmp_out = tempfile.mktemp(suffix='.png')
                    cv2.imwrite(tmp_in, img)
                    cmd = ['convert', tmp_in] + transform + [tmp_out]
                    subprocess.run(cmd, check=True, capture_output=True, timeout=5)
                    t_img = cv2.imread(tmp_out)
                    transformed = cv2.cvtColor(t_img, cv2.COLOR_BGR2RGB)
                    os.unlink(tmp_in)
                    os.unlink(tmp_out)

                mask = _segment_once(transformed)
                # Resize if needed
                if mask.shape[:2] != (h, w):
                    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

                # Determine person value (minority = person)
                is_person = (mask == 255) if np.sum(mask == 255) < mask.size * 0.5 else (mask == 0)
                agreement += is_person.astype(np.float32)
                n_valid += 1
            except Exception:
                continue

        if n_valid > 0:
            agreement /= n_valid
        else:
            agreement[:] = 0.5

        person = (agreement >= 0.5).astype(np.uint8) * 255
    else:
        mask = _segment_once(img_rgb)
        if mask.shape[:2] != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        if np.sum(mask == 255) < mask.size * 0.5:
            person = (mask == 255).astype(np.uint8) * 255
        else:
            person = (mask == 0).astype(np.uint8) * 255
        agreement = (person / 255.0).astype(np.float32)

    masks = {
        'person': person,
        'background': 255 - person,
        'agreement': agreement,
        'face_bbox': None,
    }

    # Face detection
    try:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        det = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/blaze_face_short_range.tflite'),
                min_detection_confidence=0.3))
        result = det.detect(mp_img)
        det.close()

        if result.detections:
            d = result.detections[0]  # primary face
            bbox = d.bounding_box
            pad = int(bbox.width * 0.2)
            x1 = max(0, bbox.origin_x - pad)
            y1 = max(0, bbox.origin_y - pad)
            x2 = min(w, bbox.origin_x + bbox.width + pad)
            y2 = min(h, bbox.origin_y + bbox.height + int(bbox.height * 0.15))
            masks['face_bbox'] = (x1, y1, x2, y2)
    except Exception as e:
        print(f"    Face detection failed: {e}")

    return masks


def get_mp_landmarks(image_path):
    """Get face mesh landmarks (478 points) if available.

    Returns:
        list of (x, y) in pixel coords, or None if detection fails.
    """
    import mediapipe as mp
    from mediapipe.tasks.python import vision

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

def _refine_bbox_mask(img_bgr, rough_bbox, person_mask, label="", image_type="auto"):
    """Refine rough bounding box to actual object boundary using thresholding.

    For grayscale/BW images: uses luminance bands.
    For color images: uses LAB color space thresholding.
    Constrained by person_mask.
    """
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = rough_bbox

    # Pad the bbox by 20%
    bw, bh = x2 - x1, y2 - y1
    pad_x, pad_y = int(bw * 0.2), int(bh * 0.2)
    x1p = max(0, x1 - pad_x)
    y1p = max(0, y1 - pad_y)
    x2p = min(w, x2 + pad_x)
    y2p = min(h, y2 + pad_y)

    # Crop region
    crop = img_bgr[y1p:y2p, x1p:x2p]
    crop_person = person_mask[y1p:y2p, x1p:x2p]

    # Detect if grayscale
    if image_type == "auto":
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mean_sat = np.mean(hsv[:, :, 1])
        is_gray = mean_sat < 25
    else:
        is_gray = image_type in ("bw", "grayscale")

    if is_gray:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Use Otsu to find natural threshold in the region
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Pick the value that overlaps more with the rough bbox center
        ch, cw = crop.shape[:2]
        center_mask = np.zeros((ch, cw), dtype=np.uint8)
        margin_x, margin_y = max(1, cw // 4), max(1, ch // 4)
        center_mask[margin_y:ch - margin_y, margin_x:cw - margin_x] = 255
        white_in_center = np.sum((thresh == 255) & (center_mask == 255))
        black_in_center = np.sum((thresh == 0) & (center_mask == 255))
        if white_in_center > black_in_center:
            region_mask = thresh
        else:
            region_mask = 255 - thresh
    else:
        # LAB: use A and B channels for skin/non-skin separation
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        # Adaptive threshold on L channel within region
        _, region_mask = cv2.threshold(l_ch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Same center-overlap test
        ch, cw = crop.shape[:2]
        center_mask = np.zeros((ch, cw), dtype=np.uint8)
        margin_x, margin_y = max(1, cw // 4), max(1, ch // 4)
        center_mask[margin_y:ch - margin_y, margin_x:cw - margin_x] = 255
        white_in_center = np.sum((region_mask == 255) & (center_mask == 255))
        black_in_center = np.sum((region_mask == 0) & (center_mask == 255))
        if black_in_center > white_in_center:
            region_mask = 255 - region_mask

    # Constrain by person mask
    region_mask = region_mask & crop_person

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    region_mask = cv2.morphologyEx(region_mask, cv2.MORPH_OPEN, kernel)
    region_mask = cv2.morphologyEx(region_mask, cv2.MORPH_CLOSE, kernel)

    # Keep largest connected component
    n_labels, labels, label_stats, _ = cv2.connectedComponentsWithStats(region_mask, connectivity=8)
    if n_labels > 1:
        # Skip background label 0
        largest = 1 + np.argmax(label_stats[1:, cv2.CC_STAT_AREA])
        region_mask = ((labels == largest) * 255).astype(np.uint8)

    # Place back into full-size mask
    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[y1p:y2p, x1p:x2p] = region_mask

    return full_mask


def compute_saliency(image_path):
    """Cheap edge-based saliency map (0-1 float32).

    Uses IM edge detection + color saliency, combined.
    """
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    # Edge saliency
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3) ** 2 + \
            cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3) ** 2
    edges = np.sqrt(edges)
    edges = (edges / (edges.max() + 1e-8)).astype(np.float32)

    # Color saliency (difference from mean)
    blur = cv2.GaussianBlur(img, (31, 31), 15)
    diff = cv2.absdiff(img, blur)
    color_sal = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY).astype(np.float32)
    color_sal = color_sal / (color_sal.max() + 1e-8)

    # Combined
    saliency = np.clip(edges * 0.5 + color_sal * 0.5, 0, 1)
    # Smooth
    saliency = cv2.GaussianBlur(saliency, (15, 15), 5)
    saliency = saliency / (saliency.max() + 1e-8)

    return saliency


def build_zone_map(image_path, focus_targets, focus_edges, masks, landmarks,
                   use_saliency=False, image_type="auto"):
    """Build pixel-level zone map from all detection sources.

    Returns:
        zone_map: uint8 array with ZONE_BG/PERIPHERY/EDGE/TARGET values
        zone_masks: dict mapping zone name → binary uint8 mask
    """
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    # Start: everything is background
    zone_map = np.full((h, w), ZONE_BG, dtype=np.uint8)

    # Person region → periphery
    person = masks['person']
    if person.shape[:2] != (h, w):
        person = cv2.resize(person, (w, h), interpolation=cv2.INTER_NEAREST)
    zone_map[person > 128] = ZONE_PERIPHERY

    # Focus edges (from agent annotations)
    edge_masks = {}
    if focus_edges:
        for fe in focus_edges:
            bbox = fe['bbox']
            label = fe.get('label', 'edge')
            refined = _refine_bbox_mask(img, bbox, person, label=label,
                                        image_type=image_type)
            edge_masks[label] = refined
            zone_map[refined > 128] = ZONE_EDGE

    # Focus targets (from agent annotations or MP landmarks)
    target_masks = {}
    if focus_targets:
        for ft in focus_targets:
            bbox = ft['bbox']
            label = ft.get('label', 'target')
            if label == 'face' and landmarks is not None:
                # Use landmark-derived face oval instead of bbox thresholding
                face_mask = _landmarks_to_mask(landmarks, _FACE_OVAL, h, w, dilate=8)
                target_masks[label] = face_mask
            else:
                refined = _refine_bbox_mask(img, bbox, person, label=label,
                                            image_type=image_type)
                target_masks[label] = refined
            zone_map[target_masks[label] > 128] = ZONE_TARGET
    elif masks.get('face_bbox') is not None:
        # Backward compat: no annotations, use MP face bbox
        if landmarks is not None:
            face_mask = _landmarks_to_mask(landmarks, _FACE_OVAL, h, w, dilate=8)
        else:
            x1, y1, x2, y2 = masks['face_bbox']
            face_mask = np.zeros((h, w), dtype=np.uint8)
            face_mask[y1:y2, x1:x2] = 255
            face_mask = face_mask & person
        target_masks['face'] = face_mask
        zone_map[face_mask > 128] = ZONE_TARGET

    # Saliency promotion: periphery → edge where saliency is high
    if use_saliency:
        saliency = compute_saliency(image_path)
        promote = (zone_map == ZONE_PERIPHERY) & (saliency > 0.5) & (person > 128)
        zone_map[promote] = ZONE_EDGE

    # Build per-zone binary masks
    zone_masks = {}
    for zone_val, zone_name in ZONE_NAMES.items():
        zone_masks[zone_name] = (zone_map == zone_val).astype(np.uint8) * 255

    # Report
    total = h * w
    for zone_name, zmask in zone_masks.items():
        pct = 100 * np.sum(zmask > 128) / total
        print(f"    {zone_name}: {pct:.1f}%")

    return zone_map, zone_masks


# ─── SVG compositing ───

def _mask_to_clippath_points(mask, svg_width, img_w, img_h):
    """Convert binary mask to SVG polygon point strings for clipPath.

    Returns list of polygon point strings (one per contour).
    """
    # Scale factor
    scale = svg_width / img_w
    svg_height = int(img_h * scale)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 50:  # skip tiny contours
            continue
        # Simplify
        epsilon = 0.002 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 3:
            continue
        # Scale to SVG coords
        pts = approx.squeeze()
        if pts.ndim == 1:
            continue
        scaled = pts.astype(np.float64)
        scaled[:, 0] *= scale
        scaled[:, 1] *= scale
        point_str = ' '.join(f'{x:.1f},{y:.1f}' for x, y in scaled)
        polygons.append(point_str)

    return polygons


def _extract_region_opaque(image_path, mask, expand=0):
    """Extract masked region as opaque crop (fills masked-out area with dominant color).

    This concentrates K-means clusters on the actual content pixels.
    Returns (temp_file_path, bbox_of_crop_in_original).
    """
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    if expand > 0:
        kernel = np.ones((expand, expand), np.uint8)
        mask = cv2.dilate(mask, kernel)

    # Find bounding box of mask
    ys, xs = np.where(mask > 128)
    if len(ys) == 0:
        # Empty mask — return full image
        tmp = tempfile.mktemp(suffix=".png")
        Image.fromarray(img_rgb).save(tmp)
        return tmp, (0, 0, w, h)

    x1, y1 = xs.min(), ys.min()
    x2, y2 = xs.max() + 1, ys.max() + 1

    # Pad
    pad = max(5, int(0.02 * max(x2 - x1, y2 - y1)))
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)

    crop = img_rgb[y1:y2, x1:x2].copy()
    crop_mask = mask[y1:y2, x1:x2]

    # Fill non-mask pixels with mean of mask pixels (so K-means doesn't waste on bg)
    fg_pixels = crop[crop_mask > 128]
    if len(fg_pixels) > 0:
        mean_color = fg_pixels.mean(axis=0).astype(np.uint8)
        crop[crop_mask <= 128] = mean_color

    tmp = tempfile.mktemp(suffix=".png")
    Image.fromarray(crop).save(tmp)
    return tmp, (x1, y1, x2, y2)


def _extract_region_alpha(image_path, mask, expand=0):
    """Extract masked region with alpha channel (for full-canvas layers)."""
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    if expand > 0:
        kernel = np.ones((expand, expand), np.uint8)
        mask = cv2.dilate(mask, kernel)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = img_rgb
    rgba[:, :, 3] = mask

    tmp = tempfile.mktemp(suffix=".png")
    Image.fromarray(rgba).save(tmp)
    return tmp


def _extract_paths(svg_content):
    """Extract path elements from SVG string."""
    return re.findall(r'<path[^>]*/?>', svg_content)


def _extract_viewbox(svg_content):
    """Extract viewBox from SVG string."""
    match = re.search(r'viewBox="([^"]+)"', svg_content)
    return match.group(1) if match else "0 0 800 800"


def _offset_paths(paths, dx, dy):
    """Translate SVG path elements by (dx, dy) via transform attribute."""
    if dx == 0 and dy == 0:
        return paths
    offset = []
    for p in paths:
        # Insert transform before the closing />
        if '/>' in p:
            p = p.replace('/>', f' transform="translate({dx:.1f},{dy:.1f})"/>')
        offset.append(p)
    return offset


# ─── Main entry point ───

def portrait_mode(image_path,
                  # Zone annotations from calling agent
                  focus_targets=None,   # list of {'bbox': (x1,y1,x2,y2), 'label': str}
                  focus_edges=None,     # list of {'bbox': (x1,y1,x2,y2), 'label': str}

                  # Per-zone K and smoothing
                  target_K=128, target_smooth=None,
                  edge_K=64, edge_smooth="kuwahara:2",
                  periphery_K=32, periphery_smooth="kuwahara:3",
                  bg_K=16, bg_smooth="oilpaint:12",

                  # Detail hints for focus target zones (loosen pipeline extraction)
                  target_detail=True,

                  # Options
                  use_landmarks=True,
                  use_saliency=False,
                  multi_pass=True,
                  svg_width=800,
                  image_type="auto"):
    """
    Create portrait-mode SVG with foveated detail levels.

    Four zones from highest to lowest detail:
      - Focus Target (face, eyes) → K=128, no smoothing
      - Focus Edge (beard, hands, hat) → K=64, light kuwahara
      - Periphery (torso, clothing) → K=32, kuwahara
      - Background (sky, walls) → K=16, oilpaint

    Args:
        image_path: Path to source image
        focus_targets: Agent-identified focal regions with rough bboxes
        focus_edges: Agent-identified compositionally important regions
        target_K, edge_K, periphery_K, bg_K: Color clusters per zone
        target_smooth, edge_smooth, periphery_smooth, bg_smooth: IM smoothing
        target_detail: Loosen pipeline extraction for target zones (more paths)
        use_landmarks: Try MP face landmarks for precise face geometry
        use_saliency: Promote high-saliency periphery to edge zone
        multi_pass: Multi-pass MP segmentation for soft boundaries
        svg_width: Output SVG width
        image_type: "auto", "photo", "painting", "bw", "grayscale", "graphic"

    Returns:
        (svg_string, stats_dict)
    """
    from pipeline import image_to_svg

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    img_h, img_w = img.shape[:2]
    scale = svg_width / img_w
    svg_height = int(img_h * scale)

    # ─── Step 1: MediaPipe segmentation ───
    print("[1/4] Segmentation" + (" (multi-pass)" if multi_pass else ""))
    masks = get_mp_masks(image_path, multi_pass=multi_pass)

    landmarks = None
    if use_landmarks:
        landmarks = get_mp_landmarks(image_path)
        if landmarks:
            print(f"    Landmarks: 478 points detected")
        else:
            print(f"    Landmarks: not detected (falling back to bbox)")

    # ─── Step 2: Build zone map ───
    print("[2/4] Zone detection")
    zone_map, zone_masks = build_zone_map(
        image_path, focus_targets, focus_edges, masks, landmarks,
        use_saliency=use_saliency, image_type=image_type)

    # ─── Step 3: Process each zone ───
    print("[3/4] Per-zone vectorization")

    zone_config = {
        'background': {'K': bg_K, 'smooth': bg_smooth, 'mode': 'graphic',
                        'overrides': {}},
        'periphery':  {'K': periphery_K, 'smooth': periphery_smooth, 'mode': 'painting',
                        'overrides': {}},
        'edge':       {'K': edge_K, 'smooth': edge_smooth, 'mode': 'painting',
                        'overrides': {}},
        'target':     {'K': target_K, 'smooth': target_smooth, 'mode': 'photo',
                        'overrides': {}},
    }

    # Loosen extraction for target zone to get more paths
    if target_detail:
        zone_config['target']['overrides'] = {
            'compactness_min': 0.04,
            'edge_density_min': 0.10,
            'isolation_filter': False,
            'min_area': 20,
        }

    layers = {}
    stats = {}

    for zone_name in ['background', 'periphery', 'edge', 'target']:
        zmask = zone_masks[zone_name]
        if np.sum(zmask > 128) == 0:
            print(f"    {zone_name}: empty, skipping")
            continue

        cfg = zone_config[zone_name]
        print(f"    {zone_name}: K={cfg['K']}, smooth={cfg['smooth']}")

        # For target/edge zones: use opaque crop to concentrate K-means
        if zone_name in ('target', 'edge'):
            tmp_path, crop_bbox = _extract_region_opaque(image_path, zmask, expand=3)
            cx1, cy1, cx2, cy2 = crop_bbox

            try:
                layer_svg, _ = image_to_svg(
                    tmp_path, mode=cfg['mode'], K=cfg['K'],
                    smooth=cfg['smooth'], svg_width=svg_width,
                    pipeline="fill", **cfg['overrides'])
            finally:
                os.unlink(tmp_path)

            # Extract paths and translate to correct position in composite
            paths = _extract_paths(layer_svg)
            # The cropped image was processed at svg_width scale,
            # but it covers only a portion of the full image.
            # We need to rescale: crop was (cx2-cx1) wide, rendered at svg_width.
            # In the composite, this crop occupies (cx2-cx1)*scale pixels.
            crop_w = cx2 - cx1
            crop_h = cy2 - cy1
            crop_svg_w = crop_w * scale
            crop_svg_h = crop_h * scale
            # The layer_svg was rendered at full svg_width — need to rescale
            inner_scale = crop_svg_w / svg_width
            dx = cx1 * scale
            dy = cy1 * scale

            # Wrap in a group that scales from svg_width space to crop space
            layers[zone_name] = {
                'paths': paths,
                'transform': f'translate({dx:.1f},{dy:.1f}) scale({inner_scale:.4f})',
            }
            stats[zone_name] = len(paths)
        else:
            # Background/periphery: full-canvas with alpha
            tmp_path = _extract_region_alpha(image_path, zmask, expand=3)
            try:
                layer_svg, _ = image_to_svg(
                    tmp_path, mode=cfg['mode'], K=cfg['K'],
                    smooth=cfg['smooth'], svg_width=svg_width,
                    pipeline="fill", **cfg['overrides'])
            finally:
                os.unlink(tmp_path)

            paths = _extract_paths(layer_svg)
            layers[zone_name] = {'paths': paths, 'transform': None}
            stats[zone_name] = len(paths)

    # ─── Step 4: Composite with clipPaths ───
    print("[4/4] Compositing")

    vb = f"0 0 {svg_width} {svg_height}"
    svg_parts = [
        '<?xml version="1.0"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">',
        '  <defs>',
    ]

    # Generate clipPaths for each zone (except background which is full canvas)
    for zone_name in ['periphery', 'edge', 'target']:
        zmask = zone_masks.get(zone_name)
        if zmask is None or np.sum(zmask > 128) == 0:
            continue
        polygons = _mask_to_clippath_points(zmask, svg_width, img_w, img_h)
        if polygons:
            svg_parts.append(f'    <clipPath id="clip_{zone_name}">')
            for poly_pts in polygons:
                svg_parts.append(f'      <polygon points="{poly_pts}"/>')
            svg_parts.append(f'    </clipPath>')

    svg_parts.append('  </defs>')

    # Layers: back to front
    for zone_name in ['background', 'periphery', 'edge', 'target']:
        if zone_name not in layers:
            continue

        layer = layers[zone_name]
        paths = layer['paths']
        transform = layer.get('transform')

        if zone_name == 'background':
            svg_parts.append(f'  <g id="{zone_name}">')
        else:
            clip_attr = f' clip-path="url(#clip_{zone_name})"'
            svg_parts.append(f'  <g id="{zone_name}"{clip_attr}>')

        if transform:
            svg_parts.append(f'    <g transform="{transform}">')
            svg_parts.extend(f'      {p}' for p in paths)
            svg_parts.append('    </g>')
        else:
            svg_parts.extend(f'    {p}' for p in paths)

        svg_parts.append('  </g>')

    svg_parts.append('</svg>')
    svg = '\n'.join(svg_parts)

    stats['total'] = sum(stats.values())
    print(f"\n    Total: {stats['total']} paths ({len(svg) // 1024}KB)")
    for zn, cnt in sorted(stats.items()):
        if zn != 'total':
            print(f"      {zn}: {cnt}")

    return svg, stats
