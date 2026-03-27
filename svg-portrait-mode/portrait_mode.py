"""
SVG Portrait Mode - Layered vectorization with selective detail.

Uses MediaPipe for segmentation and the image-to-svg pipeline for
per-layer processing with appropriate K and smoothing settings.

Usage:
    from portrait_mode import portrait_mode
    
    svg, stats = portrait_mode("photo.jpg")
    # or with custom settings:
    svg, stats = portrait_mode("photo.jpg", 
        face_K=96, body_K=48, background_K=16)
"""

import sys
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import re

# Use the image-to-svg pipeline
sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')


def get_mediapipe_masks(image_path):
    """Get person/face/background masks from MediaPipe.
    
    Returns:
        dict with 'person', 'background', 'face' (if detected) keys,
        each containing a numpy mask array
    """
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    
    masks = {}
    
    # Selfie segmentation for person/background
    try:
        seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path='/home/claude/selfie_segmenter.tflite'),
                output_category_mask=True))
        result = seg.segment(mp_img)
        mask = result.category_mask.numpy_view().squeeze()
        seg.close()
        
        # Determine which value is person
        if np.sum(mask == 255) < mask.size * 0.5:
            person = (mask == 255).astype(np.uint8) * 255
        else:
            person = (mask == 0).astype(np.uint8) * 255
            
        masks['person'] = person
        masks['background'] = 255 - person
    except Exception as e:
        print(f"Selfie segmentation failed: {e}")
        # Fallback: treat everything as foreground
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
        print(f"Face detection failed: {e}")
    
    return masks


def _extract_region(image_path, mask, expand=0):
    """Extract masked region to temp file with alpha channel."""
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    
    # Resize mask to match image
    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    
    if expand > 0:
        kernel = np.ones((expand, expand), np.uint8)
        mask = cv2.dilate(mask, kernel)
    
    # Create RGBA with alpha from mask
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:,:,:3] = img_rgb
    rgba[:,:,3] = mask
    
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


def portrait_mode(image_path, 
                  face_K=96, face_smooth=None,
                  body_K=48, body_smooth="kuwahara:3",
                  background_K=16, background_smooth="oilpaint:12",
                  svg_width=800):
    """
    Create portrait-mode SVG with layered detail levels.
    
    Uses MediaPipe for segmentation, then processes each layer
    through the image-to-svg pipeline with appropriate settings.
    
    Args:
        image_path: Path to source image
        face_K: Color clusters for face (default 96 - high detail)
        face_smooth: ImageMagick smoothing for face (default None)
        body_K: Color clusters for body (default 48)
        body_smooth: ImageMagick smoothing for body (default kuwahara:3)
        background_K: Color clusters for background (default 16 - flat)
        background_smooth: ImageMagick smoothing for background (default oilpaint:12)
        svg_width: Output SVG width
        
    Returns:
        (svg_string, stats_dict)
    """
    from pipeline import image_to_svg
    
    # Get segmentation masks
    print("[1] Segmentation")
    masks = get_mediapipe_masks(image_path)
    for name, m in masks.items():
        pct = 100 * np.sum(m > 128) / m.size
        print(f"    {name}: {pct:.1f}%")
    
    layers = {}
    stats = {}
    
    # Process each layer with appropriate settings
    print("\n[2] Processing layers")
    
    # Background layer (lowest detail)
    print(f"    Background: K={background_K}, smooth={background_smooth}")
    bg_tmp = _extract_region(image_path, masks['background'])
    try:
        bg_svg, _ = image_to_svg(bg_tmp, mode="graphic", K=background_K,
                                 smooth=background_smooth, svg_width=svg_width,
                                 pipeline="fill")
        layers['background'] = bg_svg
        stats['background'] = len(_extract_paths(bg_svg))
    finally:
        os.unlink(bg_tmp)
    
    # Body layer (person minus face)
    body_mask = masks['person'].copy()
    if 'face' in masks:
        body_mask[masks['face'] > 128] = 0
    
    print(f"    Body: K={body_K}, smooth={body_smooth}")
    body_tmp = _extract_region(image_path, body_mask, expand=5)
    try:
        body_svg, _ = image_to_svg(body_tmp, mode="painting", K=body_K,
                                   smooth=body_smooth, svg_width=svg_width,
                                   pipeline="fill")
        layers['body'] = body_svg
        stats['body'] = len(_extract_paths(body_svg))
    finally:
        os.unlink(body_tmp)
    
    # Face layer (highest detail)
    if 'face' in masks:
        print(f"    Face: K={face_K}, smooth={face_smooth}")
        face_tmp = _extract_region(image_path, masks['face'], expand=10)
        try:
            face_svg, _ = image_to_svg(face_tmp, mode="photo", K=face_K,
                                       smooth=face_smooth, svg_width=svg_width,
                                       pipeline="fill")
            layers['face'] = face_svg
            stats['face'] = len(_extract_paths(face_svg))
        finally:
            os.unlink(face_tmp)
    
    # Composite layers (back to front)
    print("\n[3] Compositing")
    vb = _extract_viewbox(layers.get('background', layers.get('body', '')))
    
    svg_parts = [f'<?xml version="1.0"?>',
                 f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">']
    
    for layer_name in ['background', 'body', 'face']:
        if layer_name in layers:
            paths = _extract_paths(layers[layer_name])
            svg_parts.append(f'  <g id="{layer_name}">')
            svg_parts.extend(f'    {p}' for p in paths)
            svg_parts.append('  </g>')
    
    svg_parts.append('</svg>')
    svg = '\n'.join(svg_parts)
    
    stats['total'] = sum(stats.values())
    print(f"    Total: {stats['total']} paths, {len(svg)//1024}KB")
    
    return svg, stats


# Convenience alias
def portrait_mode_auto(image_path, **kwargs):
    """Alias for portrait_mode() with default settings."""
    return portrait_mode(image_path, **kwargs)
