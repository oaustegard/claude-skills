"""
SVG Portrait Mode v0.4.0 - Layered vectorization with selective detail.

Changes from v0.3.0:
- Auto image type detection (photo/painting/illustration/graphic) via Anthropic API
- Background downscaling: process at ~20% resolution for naturally large blobby paths
- Per-type layer defaults (K, smoothing, modes)
- Background scale-up compositing (transform to match master viewBox)

Architecture: Same as v0.3.0 — alpha-channel masking per layer, no clipPaths.
The background downscale trick means fewer pixels → bigger K-means clusters →
bigger SVG paths when rendered at full width. Combined with low K and heavy
oilpaint, this produces the flat/blobby pop-art effect.
"""

import sys, cv2, numpy as np, re, os, tempfile, base64, json, urllib.request
from PIL import Image

sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')

# Sentinel to distinguish "not specified" from "explicitly None"
_UNSET = object()

# Per-type defaults: tuned for the portrait-mode aesthetic
# Background is intentionally crushed: low K + heavy oilpaint + small image = big blobs
LAYER_DEFAULTS = {
    "photo": {
        "face_K": 96,  "face_smooth": None,          "face_mode": "photo",
        "body_K": 48,  "body_smooth": "kuwahara:3",   "body_mode": "painting",
        "bg_K":   6,   "bg_smooth":   "oilpaint:24",  "bg_mode":   "graphic",  "bg_scale": 0.20,
    },
    "painting": {
        "face_K": 80,  "face_smooth": None,          "face_mode": "painting",
        "body_K": 48,  "body_smooth": "oilpaint:8",   "body_mode": "painting",
        "bg_K":   6,   "bg_smooth":   "oilpaint:28",  "bg_mode":   "graphic",  "bg_scale": 0.18,
    },
    "illustration": {
        "face_K": 64,  "face_smooth": None,          "face_mode": "illustration",
        "body_K": 32,  "body_smooth": "oilpaint:6",   "body_mode": "illustration",
        "bg_K":   6,   "bg_smooth":   "oilpaint:20",  "bg_mode":   "graphic",  "bg_scale": 0.22,
    },
    "graphic": {
        "face_K": 48,  "face_smooth": None,          "face_mode": "graphic",
        "body_K": 24,  "body_smooth": None,           "body_mode": "graphic",
        "bg_K":   8,   "bg_smooth":   None,           "bg_mode":   "graphic",  "bg_scale": 0.25,
    },
}


def detect_image_type(image_path):
    """Classify image as photo/painting/illustration/graphic via Anthropic API."""
    api_key = None
    for env_var in ("ANTHROPIC_API_KEY", "API_KEY"):
        api_key = os.environ.get(env_var)
        if api_key:
            break
    if not api_key:
        env_path = "/mnt/project/claude.env"
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
    if not api_key:
        print("  detect_image_type: no API key, defaulting to 'painting'")
        return "painting"

    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if w > 512:
            img = img.resize((512, int(512 * h / w)), Image.LANCZOS)
        tmp = tempfile.mktemp(suffix=".jpg")
        img.save(tmp, "JPEG", quality=80)
        data = base64.b64encode(open(tmp, "rb").read()).decode()
        os.unlink(tmp)

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 20,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
                    {"type": "text", "text": "Classify this image into exactly one category: photo, painting, illustration, or graphic. Reply with that single word only."}
                ]
            }]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            }
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        result = resp["content"][0]["text"].strip().lower()
        detected = result if result in LAYER_DEFAULTS else "painting"
        print(f"  detect_image_type: '{result}' → '{detected}'")
        return detected
    except Exception as e:
        print(f"  detect_image_type: failed ({e}), defaulting to 'painting'")
        return "painting"


def get_mediapipe_masks(image_path):
    """Get person/face/background masks from MediaPipe."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    masks = {}

    # Selfie segmentation
    try:
        seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/selfie_segmenter.tflite'),
                output_category_mask=True))
        result = seg.segment(mp_img)
        mask = result.category_mask.numpy_view().squeeze()
        seg.close()

        if np.sum(mask == 255) < mask.size * 0.5:
            person = (mask == 255).astype(np.uint8) * 255
        else:
            person = (mask == 0).astype(np.uint8) * 255

        masks['person'] = person
        masks['background'] = 255 - person
    except Exception as e:
        print(f"  Selfie segmentation failed: {e}")
        masks['person'] = np.ones((h, w), dtype=np.uint8) * 255
        masks['background'] = np.zeros((h, w), dtype=np.uint8)

    # Face detection
    try:
        det = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/blaze_face_short_range.tflite'),
                min_detection_confidence=0.3))
        result = det.detect(mp_img)
        det.close()

        if result.detections:
            face_mask = np.zeros((h, w), dtype=np.uint8)
            for d in result.detections:
                bbox = d.bounding_box
                pad = int(bbox.width * 0.25)
                x1 = max(0, bbox.origin_x - pad)
                y1 = max(0, bbox.origin_y - pad)
                x2 = min(w, bbox.origin_x + bbox.width + pad)
                y2 = min(h, bbox.origin_y + bbox.height + int(bbox.height * 0.15))
                face_mask[y1:y2, x1:x2] = 255
            masks['face'] = face_mask
    except Exception as e:
        print(f"  Face detection failed: {e}")

    return masks


def _extract_region(image_path, mask, expand=0, scale=1.0):
    """Extract masked region to temp PNG, optionally downscaled.
    
    The scale parameter is the key to the background blob effect:
    smaller image → fewer pixels → bigger K-means clusters → bigger paths.
    """
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    if expand > 0:
        kernel = np.ones((expand, expand), np.uint8)
        mask = cv2.dilate(mask, kernel)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = img_rgb
    rgba[:, :, 3] = mask

    if scale != 1.0 and scale > 0:
        new_w = max(32, int(w * scale))
        new_h = max(32, int(h * scale))
        rgba = cv2.resize(rgba, (new_w, new_h), interpolation=cv2.INTER_AREA)

    tmp = tempfile.mktemp(suffix=".png")
    Image.fromarray(rgba).save(tmp)
    return tmp


def _extract_paths_and_rects(svg_content):
    """Extract rect + path elements from SVG string."""
    rects = re.findall(r'<rect[^>]*/>', svg_content)
    paths = re.findall(r'<path[^>]*/?>', svg_content)
    return rects + paths


def _extract_viewbox(svg_content):
    """Extract viewBox from SVG string."""
    match = re.search(r'viewBox="([^"]+)"', svg_content)
    return match.group(1) if match else "0 0 800 800"


def _parse_viewbox(vb_str):
    """Parse viewBox string to (x, y, w, h) floats."""
    return [float(x) for x in vb_str.split()]


def portrait_mode(image_path, image_type=None,
                  face_K=None, face_smooth=_UNSET, face_mode=None,
                  body_K=None, body_smooth=_UNSET, body_mode=None,
                  background_K=None, background_smooth=_UNSET, background_mode=None,
                  background_scale=None, svg_width=800):
    """
    Create portrait-mode SVG with layered detail levels.
    
    Key improvement over v0.3.0: background is processed from a downscaled
    image, producing naturally large blobby shapes when rendered at full size.
    
    Args:
        image_path: Path to source image
        image_type: One of photo/painting/illustration/graphic (auto-detected if None)
        face_K, face_smooth, face_mode: Face layer overrides
        body_K, body_smooth, body_mode: Body layer overrides
        background_K, background_smooth, background_mode: Background layer overrides
        background_scale: Downscale factor for background (0.15-0.30, lower = blobbier)
        svg_width: Output SVG width
        
    Returns:
        (svg_string, stats_dict)
    """
    from pipeline import image_to_svg

    # --- Type detection ---
    print("[0] Image type detection")
    if image_type is None:
        image_type = detect_image_type(image_path)
    else:
        print(f"  image_type: '{image_type}' (explicit)")
    if image_type not in LAYER_DEFAULTS:
        image_type = "painting"

    d = LAYER_DEFAULTS[image_type]
    # Apply type defaults. Callers use _UNSET sentinel (module-level) to 
    # distinguish "not specified" from "explicitly None (no smoothing)".
    face_K            = d["face_K"]        if face_K is None else face_K
    face_smooth       = d["face_smooth"]   if face_smooth is _UNSET else face_smooth
    face_mode         = d["face_mode"]     if face_mode is None else face_mode
    body_K            = d["body_K"]        if body_K is None else body_K
    body_smooth       = d["body_smooth"]   if body_smooth is _UNSET else body_smooth
    body_mode         = d["body_mode"]     if body_mode is None else body_mode
    background_K      = d["bg_K"]          if background_K is None else background_K
    background_smooth = d["bg_smooth"]     if background_smooth is _UNSET else background_smooth
    background_mode   = d["bg_mode"]       if background_mode is None else background_mode
    background_scale  = d["bg_scale"]      if background_scale is None else background_scale

    # --- Segmentation ---
    print("\n[1] Segmentation")
    masks = get_mediapipe_masks(image_path)
    img = cv2.imread(image_path)
    img_h, img_w = img.shape[:2]
    for name, m in masks.items():
        pct = 100 * np.sum(m > 128) / m.size
        print(f"    {name}: {pct:.1f}%")

    body_mask = masks['person'].copy()
    if 'face' in masks:
        body_mask[masks['face'] > 128] = 0

    layers = {}
    stats = {"image_type": image_type}

    # --- Layer processing ---
    print("\n[2] Processing layers")

    # Background — FULL IMAGE, DOWNSCALED for big blobby shapes
    # No mask: background is the base layer, body+face paint over it
    print(f"    Background: K={background_K}, smooth={background_smooth}, scale={background_scale}")
    bg_tmp = _extract_region(image_path, np.ones((img_h, img_w), dtype=np.uint8) * 255, scale=background_scale)
    try:
        bg_svg, _ = image_to_svg(bg_tmp, mode=background_mode, K=background_K,
                                 smooth=background_smooth, svg_width=svg_width,
                                 pipeline="fill")
        layers['background'] = bg_svg
        stats['background'] = len(re.findall(r'<path', bg_svg))
    finally:
        os.unlink(bg_tmp)

    # Body — full resolution, medium detail
    print(f"    Body: K={body_K}, smooth={body_smooth}")
    body_tmp = _extract_region(image_path, body_mask, expand=5)
    try:
        body_svg, _ = image_to_svg(body_tmp, mode=body_mode, K=body_K,
                                   smooth=body_smooth, svg_width=svg_width,
                                   pipeline="fill")
        layers['body'] = body_svg
        stats['body'] = len(re.findall(r'<path', body_svg))
    finally:
        os.unlink(body_tmp)

    # Face — full resolution, maximum detail
    if 'face' in masks:
        print(f"    Face: K={face_K}, smooth={face_smooth}")
        face_tmp = _extract_region(image_path, masks['face'], expand=10)
        try:
            face_svg, _ = image_to_svg(face_tmp, mode=face_mode, K=face_K,
                                       smooth=face_smooth, svg_width=svg_width,
                                       pipeline="fill")
            layers['face'] = face_svg
            stats['face'] = len(re.findall(r'<path', face_svg))
        finally:
            os.unlink(face_tmp)

    # --- Compositing ---
    print("\n[3] Compositing")
    
    # Master viewBox from full-resolution layer (face or body)
    master_svg = layers.get('face') or layers.get('body') or layers['background']
    master_vb = _extract_viewbox(master_svg)
    master_parts = _parse_viewbox(master_vb)
    
    svg_parts = ['<?xml version="1.0"?>',
                 f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{master_vb}">']

    for layer_name in ['background', 'body', 'face']:
        if layer_name not in layers:
            continue

        if layer_name == 'background':
            # Background: include everything (rect + paths) — it's the base layer
            elements = _extract_paths_and_rects(layers[layer_name])
            bg_vb = _extract_viewbox(layers['background'])
            bg_parts = _parse_viewbox(bg_vb)
            
            # Scale from background's coordinate space to master's
            sx = master_parts[2] / bg_parts[2] if bg_parts[2] > 0 else 1.0
            sy = master_parts[3] / bg_parts[3] if bg_parts[3] > 0 else 1.0
            
            if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
                svg_parts.append(f'  <g id="background" transform="scale({sx:.6f},{sy:.6f})">')
            else:
                svg_parts.append('  <g id="background">')
        else:
            # Body/face: PATHS ONLY — skip the pipeline's bg rect (#000000 full-canvas)
            # which would paint over the background layer
            elements = re.findall(r'<path[^>]*/?>', layers[layer_name])
            svg_parts.append(f'  <g id="{layer_name}">')

        svg_parts.extend(f'    {el}' for el in elements)
        svg_parts.append('  </g>')

    svg_parts.append('</svg>')
    svg = '\n'.join(svg_parts)

    stats['total'] = sum(v for k, v in stats.items() if isinstance(v, int))
    print(f"    Total: {stats['total']} paths, {len(svg)//1024}KB")

    return svg, stats
