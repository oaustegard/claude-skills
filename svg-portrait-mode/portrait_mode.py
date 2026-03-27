"""
SVG Portrait Mode v0.4.0 - Layered vectorization with selective detail.

Hybrid approach:
- Background: alpha-masked bg region at full resolution (like v0.3.0)
- Body: full person mask (face NOT subtracted), dilated, high K
- Face: OPAQUE CROP of face bbox, highest K, no smooth
- Fixed mask polarity detection (face bbox overlap, not global pixel count)
- Face detection filtering (center_y < 0.55, conf > 0.6)

Usage:
    from portrait_mode import portrait_mode
    svg, stats = portrait_mode("photo.jpg")
"""

import sys
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import re

sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')


def get_mediapipe_masks(image_path):
    """Get person and face masks from MediaPipe."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    result = {}

    # Face detection FIRST (needed for mask polarity)
    face_bbox = None
    try:
        det = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/blaze_face_short_range.tflite'),
                min_detection_confidence=0.3))
        detections = det.detect(mp_img)
        det.close()

        valid = []
        for d in detections.detections:
            bbox = d.bounding_box
            center_y = (bbox.origin_y + bbox.height / 2) / h
            conf = d.categories[0].score if d.categories else 0
            if center_y < 0.55 and conf > 0.6:
                valid.append(d)

        if valid:
            d = max(valid, key=lambda x: x.categories[0].score)
            bbox = d.bounding_box
            pad_x = int(bbox.width * 0.3)
            pad_top = int(bbox.height * 0.35)
            pad_bot = int(bbox.height * 0.2)
            x1 = max(0, bbox.origin_x - pad_x)
            y1 = max(0, bbox.origin_y - pad_top)
            x2 = min(w, bbox.origin_x + bbox.width + pad_x)
            y2 = min(h, bbox.origin_y + bbox.height + pad_bot)
            face_bbox = (x1, y1, x2, y2)
            result['face_bbox'] = face_bbox
            print(f"    Face detected: ({x1},{y1})-({x2},{y2}), conf={d.categories[0].score:.2f}")
    except Exception as e:
        print(f"    Face detection failed: {e}")

    # Selfie segmentation
    try:
        seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/selfie_segmenter.tflite'),
                output_category_mask=True))
        seg_result = seg.segment(mp_img)
        mask = seg_result.category_mask.numpy_view().squeeze()
        seg.close()

        mask_255 = (mask == 255).astype(np.uint8) * 255
        mask_0 = (mask == 0).astype(np.uint8) * 255

        if face_bbox is not None:
            fx1, fy1, fx2, fy2 = face_bbox
            face_region_255 = np.sum(mask_255[fy1:fy2, fx1:fx2] > 128)
            face_region_0 = np.sum(mask_0[fy1:fy2, fx1:fx2] > 128)
            if face_region_255 > face_region_0:
                person = mask_255
            else:
                person = mask_0
            print(f"    Mask polarity: face-overlap method (255={face_region_255}, 0={face_region_0})")
        else:
            if np.sum(mask == 255) < mask.size * 0.5:
                person = mask_255
            else:
                person = mask_0
            print(f"    Mask polarity: minority heuristic (no face)")

        result['person'] = person
        result['background'] = 255 - person
    except Exception as e:
        print(f"    Selfie segmentation failed: {e}")
        result['person'] = np.ones((h, w), dtype=np.uint8) * 255
        result['background'] = np.zeros((h, w), dtype=np.uint8)

    pct = 100 * np.sum(result['person'] > 128) / result['person'].size
    print(f"    Person coverage: {pct:.1f}%")
    return result


def _extract_region(image_path, mask, expand=0):
    """Extract masked region to temp file with alpha channel."""
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
    tmp = tempfile.mktemp(suffix=".png")
    Image.fromarray(rgba).save(tmp)
    return tmp


def _extract_paths(svg_content):
    return re.findall(r'<path[^>]*/?>', svg_content)


def _extract_viewbox(svg_content):
    match = re.search(r'viewBox="([^"]+)"', svg_content)
    return match.group(1) if match else "0 0 800 800"


def portrait_mode(image_path,
                  face_K=192, face_smooth=None,
                  body_K=96, body_smooth=None,
                  body_mask_dilate=15,
                  bg_K=16, bg_smooth="oilpaint:12",
                  svg_width=800,
                  image_type="painting"):
    """
    Create portrait-mode SVG with layered detail levels.

    Three layers composited back-to-front:
    1. Background: alpha-masked bg region at full resolution
    2. Body: full person mask (including face region), dilated, high K
    3. Face: opaque crop of face bbox, highest K, no smooth

    Face layer paints OVER body — no subtraction, no gaps.
    """
    from pipeline import image_to_svg

    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    print("[1] Segmentation")
    masks = get_mediapipe_masks(image_path)

    layers = {}
    stats = {}

    # [2] Background — alpha-masked bg region at full resolution
    print(f"\n[2] Background: K={bg_K}, smooth={bg_smooth}")
    bg_tmp = _extract_region(image_path, masks['background'])
    try:
        bg_svg, _ = image_to_svg(bg_tmp, mode="graphic", K=bg_K,
                                  smooth=bg_smooth, svg_width=svg_width,
                                  pipeline="fill")
        layers['background'] = bg_svg
        stats['background'] = len(_extract_paths(bg_svg))
        print(f"    -> {stats['background']} paths")
    finally:
        os.unlink(bg_tmp)

    # [3] Body — full person mask (face NOT subtracted), dilated
    body_mask = masks['person'].copy()
    if body_mask_dilate > 0:
        kernel = np.ones((body_mask_dilate, body_mask_dilate), np.uint8)
        body_mask = cv2.dilate(body_mask, kernel)

    print(f"\n[3] Body: K={body_K}, smooth={body_smooth}, dilate={body_mask_dilate}")
    body_tmp = _extract_region(image_path, body_mask)
    try:
        mode = "painting" if image_type == "painting" else "photo"
        body_svg, _ = image_to_svg(body_tmp, mode=mode, K=body_K,
                                    smooth=body_smooth, svg_width=svg_width,
                                    pipeline="fill")
        layers['body'] = body_svg
        stats['body'] = len(_extract_paths(body_svg))
        print(f"    -> {stats['body']} paths")
    finally:
        os.unlink(body_tmp)

    # [4] Face — opaque crop of face bbox
    if 'face_bbox' in masks:
        fx1, fy1, fx2, fy2 = masks['face_bbox']
        print(f"\n[4] Face crop: ({fx1},{fy1})-({fx2},{fy2}), K={face_K}, smooth={face_smooth}")

        face_crop = img[fy1:fy2, fx1:fx2].copy()
        face_crop_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        face_tmp = tempfile.mktemp(suffix=".png")
        Image.fromarray(face_crop_rgb).save(face_tmp)

        crop_h, crop_w = face_crop.shape[:2]
        try:
            face_svg, _ = image_to_svg(face_tmp, mode="photo", K=face_K,
                                        smooth=face_smooth, svg_width=crop_w,
                                        bg_clusters=0, pipeline="fill")
            layers['face'] = face_svg
            stats['face'] = len(_extract_paths(face_svg))
            print(f"    -> {stats['face']} paths ({crop_w}x{crop_h}px crop)")
        finally:
            os.unlink(face_tmp)
    else:
        print("\n[4] No face detected -- skipping face layer")

    # [5] Composite
    print("\n[5] Compositing")
    vb = _extract_viewbox(layers.get('background', layers.get('body', '')))

    svg_parts = [
        '<?xml version="1.0"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">'
    ]

    # Background — paths already at svg_width scale
    if 'background' in layers:
        bg_paths = _extract_paths(layers['background'])
        svg_parts.append('  <g id="background">')
        svg_parts.extend(f'    {p}' for p in bg_paths)
        svg_parts.append('  </g>')

    # Body — paths already at svg_width scale
    if 'body' in layers:
        body_paths = _extract_paths(layers['body'])
        svg_parts.append('  <g id="body">')
        svg_parts.extend(f'    {p}' for p in body_paths)
        svg_parts.append('  </g>')

    # Face — translate crop paths to face bbox position
    if 'face' in layers and 'face_bbox' in masks:
        fx1, fy1, fx2, fy2 = masks['face_bbox']
        face_paths = _extract_paths(layers['face'])

        vb_parts = [float(x) for x in vb.split()]
        vb_w = vb_parts[2] if len(vb_parts) >= 3 else svg_width
        vb_h = vb_parts[3] if len(vb_parts) >= 4 else int(svg_width * h / w)

        # Map face crop pixel coords -> SVG viewbox coords
        sx = vb_w / w
        sy = vb_h / h
        tx = fx1 * sx
        ty = fy1 * sy

        svg_parts.append(
            f'  <g id="face" transform="translate({tx:.2f},{ty:.2f}) scale({sx:.4f},{sy:.4f})">')
        svg_parts.extend(f'    {p}' for p in face_paths)
        svg_parts.append('  </g>')

    svg_parts.append('</svg>')
    svg = '\n'.join(svg_parts)

    stats['total'] = sum(stats.values())
    print(f"\n    Total: {stats['total']} paths, {len(svg) // 1024}KB")

    return svg, stats
