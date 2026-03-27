"""
SVG Portrait Mode v0.4.0 - Layered vectorization with selective detail.

Changes from v0.3.0:
- Auto image type detection via Claude API (photo/painting/graphic/illustration)
- Background downscaling for large blobby shapes (background_scale param)
- Type-appropriate layer defaults

Usage:
    from portrait_mode import portrait_mode
    
    svg, stats = portrait_mode("photo.jpg")
    # auto-detects image type, applies appropriate settings
    
    svg, stats = portrait_mode("painting.jpg", image_type="painting")
    # explicit type override
"""

import sys
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import re

sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')


# --- Layer defaults by image type ---

LAYER_DEFAULTS = {
    "photo": {
        "face_K": 96, "face_smooth": None, "face_mode": "photo",
        "body_K": 48, "body_smooth": "kuwahara:3", "body_mode": "painting",
        "background_K": 8, "background_smooth": "oilpaint:20", "background_mode": "graphic",
        "background_scale": 0.25,
    },
    "painting": {
        "face_K": 80, "face_smooth": None, "face_mode": "painting",
        "body_K": 40, "body_smooth": "oilpaint:8", "body_mode": "painting",
        "background_K": 6, "background_smooth": "oilpaint:24", "background_mode": "graphic",
        "background_scale": 0.20,
    },
    "illustration": {
        "face_K": 64, "face_smooth": None, "face_mode": "illustration",
        "body_K": 32, "body_smooth": "oilpaint:6", "body_mode": "illustration",
        "background_K": 6, "background_smooth": "oilpaint:16", "background_mode": "graphic",
        "background_scale": 0.25,
    },
    "graphic": {
        "face_K": 48, "face_smooth": None, "face_mode": "graphic",
        "body_K": 24, "body_smooth": None, "body_mode": "graphic",
        "background_K": 6, "background_smooth": None, "background_mode": "graphic",
        "background_scale": 0.30,
    },
}


def detect_image_type(image_path):
    """Classify image as photo/painting/graphic/illustration using Claude API.
    
    Returns one of: 'photo', 'painting', 'illustration', 'graphic'
    Falls back to 'painting' on any error.
    """
    import base64
    import json
    import urllib.request

    # Load API key
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        # Try loading from claude.env
        env_path = "/mnt/project/claude.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
    if not api_key:
        print("  detect_image_type: no API key, defaulting to 'painting'")
        return "painting"

    # Read and encode image (use a resized version for speed)
    try:
        img = Image.open(image_path)
        # Resize to at most 512px wide for cheap classification
        w, h = img.size
        if w > 512:
            img = img.resize((512, int(512 * h / w)), Image.LANCZOS)
        # Convert to RGB if needed
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        
        tmp = tempfile.mktemp(suffix=".jpg")
        img.save(tmp, "JPEG", quality=85)
        with open(tmp, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        os.unlink(tmp)
        media_type = "image/jpeg"
    except Exception as e:
        print(f"  detect_image_type: image prep failed ({e}), defaulting to 'painting'")
        return "painting"

    prompt = (
        "Classify this image. Reply with exactly one word from this list: "
        "photo, painting, illustration, graphic. "
        "photo=real photograph, painting=fine art painting/artwork, "
        "illustration=digital art/drawing/cartoon, graphic=vector/logo/flat design."
    )
    
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 20,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                {"type": "text", "text": prompt}
            ]
        }]
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        result = data["content"][0]["text"].strip().lower()
        valid = {"photo", "painting", "illustration", "graphic"}
        detected = result if result in valid else "painting"
        print(f"  detect_image_type: '{result}' → '{detected}'")
        return detected
    except Exception as e:
        print(f"  detect_image_type: API call failed ({e}), defaulting to 'painting'")
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
        print(f"  selfie segmentation failed: {e}")
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
        print(f"  face detection failed: {e}")

    return masks


def _extract_region(image_path, mask, expand=0, scale=1.0):
    """Extract masked region to temp PNG, optionally downscaled.
    
    Args:
        scale: Downscale factor (e.g. 0.25 = quarter size). Used for
               background to get large blobby shapes when processed at
               full svg_width (pipeline scales paths back up).
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

    if scale != 1.0:
        new_w = max(64, int(w * scale))
        new_h = max(64, int(h * scale))
        rgba = cv2.resize(rgba, (new_w, new_h), interpolation=cv2.INTER_AREA)

    tmp = tempfile.mktemp(suffix=".png")
    Image.fromarray(rgba).save(tmp)
    return tmp


def _extract_paths(svg_content):
    return re.findall(r'<path[^>]*/?>', svg_content)


def _extract_viewbox(svg_content):
    match = re.search(r'viewBox="([^"]+)"', svg_content)
    return match.group(1) if match else "0 0 800 800"


def portrait_mode(image_path,
                  image_type=None,
                  face_K=None, face_smooth=None, face_mode=None,
                  body_K=None, body_smooth=None, body_mode=None,
                  background_K=None, background_smooth=None, background_mode=None,
                  background_scale=None,
                  svg_width=800):
    """
    Create portrait-mode SVG with layered detail levels.

    Args:
        image_path: Path to source image
        image_type: One of 'photo', 'painting', 'illustration', 'graphic'.
                    If None, auto-detected via Claude API.
        face_K, body_K, background_K: Color cluster counts per layer
        face_smooth, body_smooth, background_smooth: ImageMagick smoothing specs
        face_mode, body_mode, background_mode: pipeline modes per layer
        background_scale: Downscale factor for background before vectorization.
                          Lower = larger/blobber shapes. Default: 0.25
        svg_width: Output SVG width

    Returns:
        (svg_string, stats_dict) where stats includes 'image_type'
    """
    from pipeline import image_to_svg

    # Auto-detect image type
    print("[0] Image type detection")
    if image_type is None:
        image_type = detect_image_type(image_path)
    else:
        print(f"  image_type: '{image_type}' (explicit)")

    if image_type not in LAYER_DEFAULTS:
        print(f"  unknown type '{image_type}', using 'painting'")
        image_type = "painting"

    # Get defaults for this image type, allow per-call overrides
    d = LAYER_DEFAULTS[image_type]
    face_K         = face_K         or d["face_K"]
    face_smooth    = face_smooth    or d["face_smooth"]
    face_mode      = face_mode      or d["face_mode"]
    body_K         = body_K         or d["body_K"]
    body_smooth    = body_smooth    or d["body_smooth"]
    body_mode      = body_mode      or d["body_mode"]
    background_K   = background_K   or d["background_K"]
    background_smooth = background_smooth or d["background_smooth"]
    background_mode   = background_mode   or d["background_mode"]
    background_scale  = background_scale  if background_scale is not None else d["background_scale"]

    # Segmentation
    print("\n[1] Segmentation")
    masks = get_mediapipe_masks(image_path)
    for name, m in masks.items():
        pct = 100 * np.sum(m > 128) / m.size
        print(f"    {name}: {pct:.1f}%")

    layers = {}
    stats = {"image_type": image_type}

    print("\n[2] Processing layers")

    # Background (downscaled for blobby shapes)
    print(f"    Background: K={background_K}, smooth={background_smooth}, scale={background_scale}")
    bg_tmp = _extract_region(image_path, masks['background'], scale=background_scale)
    try:
        bg_svg, _ = image_to_svg(bg_tmp, mode=background_mode, K=background_K,
                                  smooth=background_smooth, svg_width=svg_width,
                                  pipeline="fill")
        layers['background'] = bg_svg
        stats['background'] = len(_extract_paths(bg_svg))
    finally:
        os.unlink(bg_tmp)

    # Body (person minus face)
    body_mask = masks['person'].copy()
    if 'face' in masks:
        body_mask[masks['face'] > 128] = 0

    print(f"    Body: K={body_K}, smooth={body_smooth}")
    body_tmp = _extract_region(image_path, body_mask, expand=5)
    try:
        body_svg, _ = image_to_svg(body_tmp, mode=body_mode, K=body_K,
                                    smooth=body_smooth, svg_width=svg_width,
                                    pipeline="fill")
        layers['body'] = body_svg
        stats['body'] = len(_extract_paths(body_svg))
    finally:
        os.unlink(body_tmp)

    # Face (highest detail, no downscaling)
    if 'face' in masks:
        print(f"    Face: K={face_K}, smooth={face_smooth}")
        face_tmp = _extract_region(image_path, masks['face'], expand=10)
        try:
            face_svg, _ = image_to_svg(face_tmp, mode=face_mode, K=face_K,
                                        smooth=face_smooth, svg_width=svg_width,
                                        pipeline="fill")
            layers['face'] = face_svg
            stats['face'] = len(_extract_paths(face_svg))
        finally:
            os.unlink(face_tmp)

    # Composite (back to front)
    print("\n[3] Compositing")
    # Use face/body viewbox for coordinate system (background scale changes its viewbox)
    ref_svg = layers.get('face') or layers.get('body') or layers.get('background')
    vb = _extract_viewbox(ref_svg)

    svg_parts = [
        '<?xml version="1.0"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">',
    ]
    for layer_name in ['background', 'body', 'face']:
        if layer_name not in layers:
            continue
        paths = _extract_paths(layers[layer_name])
        layer_vb = _extract_viewbox(layers[layer_name])
        # Background may have different viewbox due to downscaling; wrap in transform group
        if layer_name == 'background' and layer_vb != vb:
            vb_parts = [float(x) for x in vb.split()]
            bg_vb_parts = [float(x) for x in layer_vb.split()]
            sx = vb_parts[2] / bg_vb_parts[2]
            sy = vb_parts[3] / bg_vb_parts[3]
            svg_parts.append(f'  <g id="background" transform="scale({sx:.6f},{sy:.6f})">')
        else:
            svg_parts.append(f'  <g id="{layer_name}">')
        svg_parts.extend(f'    {p}' for p in paths)
        svg_parts.append('  </g>')

    svg_parts.append('</svg>')
    svg = '\n'.join(svg_parts)

    stats['total'] = sum(v for k, v in stats.items() if k not in ('image_type',))
    print(f"    Total: {stats['total']} paths, {len(svg) // 1024}KB")

    return svg, stats
