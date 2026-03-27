"""
SVG Portrait Mode v0.4.1 - Layered vectorization with actual layer masking.

Key fix from v0.4.0: SVG clipPath per layer from MediaPipe masks.
Without clipping, the face layer (a full-image render) was covering everything.
Now each layer is clipped to its region — differentiation actually works.

Background: full canvas, blobby (downscaled input, K=6-8)
Body:       clipped to person mask, medium detail (K=40-48)
Face:       clipped to face bbox, high detail (K=80-96, no smoothing)
"""

import sys, cv2, numpy as np, re, os, tempfile
from PIL import Image

sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')

LAYER_DEFAULTS = {
    "photo":        {"face_K":96,  "face_smooth":None,         "face_mode":"photo",
                     "body_K":48,  "body_smooth":"kuwahara:3",  "body_mode":"painting",
                     "background_K":8, "background_smooth":"oilpaint:20","background_mode":"graphic","background_scale":0.25},
    "painting":     {"face_K":80,  "face_smooth":None,         "face_mode":"painting",
                     "body_K":40,  "body_smooth":"oilpaint:8",  "body_mode":"painting",
                     "background_K":6, "background_smooth":"oilpaint:24","background_mode":"graphic","background_scale":0.20},
    "illustration": {"face_K":64,  "face_smooth":None,         "face_mode":"illustration",
                     "body_K":32,  "body_smooth":"oilpaint:6",  "body_mode":"illustration",
                     "background_K":6, "background_smooth":"oilpaint:16","background_mode":"graphic","background_scale":0.25},
    "graphic":      {"face_K":48,  "face_smooth":None,         "face_mode":"graphic",
                     "body_K":24,  "body_smooth":None,          "body_mode":"graphic",
                     "background_K":6, "background_smooth":None,"background_mode":"graphic","background_scale":0.30},
}


def detect_image_type(image_path):
    import base64, json, urllib.request
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        env_path = "/mnt/project/claude.env"
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("API_KEY="):
                    api_key = line.strip().split("=", 1)[1]; break
    if not api_key:
        print("  detect_image_type: no key, defaulting to 'painting'"); return "painting"
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if w > 512: img = img.resize((512, int(512*h/w)), Image.LANCZOS)
        tmp = tempfile.mktemp(suffix=".jpg"); img.save(tmp, "JPEG", quality=85)
        data = base64.b64encode(open(tmp,"rb").read()).decode(); os.unlink(tmp)
        payload = json.dumps({"model":"claude-haiku-4-5-20251001","max_tokens":20,"messages":[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":data}},
            {"type":"text","text":"Classify: photo/painting/illustration/graphic. One word only."}
        ]}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        result = resp["content"][0]["text"].strip().lower()
        detected = result if result in LAYER_DEFAULTS else "painting"
        print(f"  detect_image_type: '{result}' → '{detected}'"); return detected
    except Exception as e:
        print(f"  detect_image_type: failed ({e}), defaulting to 'painting'"); return "painting"


def get_mediapipe_masks(image_path):
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    masks = {}
    try:
        seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path='/home/claude/selfie_segmenter.tflite'),
            output_category_mask=True))
        result = seg.segment(mp_img); mask = result.category_mask.numpy_view().squeeze(); seg.close()
        person = (mask == (255 if np.sum(mask==255) < mask.size*0.5 else 0)).astype(np.uint8) * 255
        masks['person'] = person; masks['background'] = 255 - person
    except Exception as e:
        print(f"  selfie segmentation failed: {e}")
        masks['person'] = np.ones((h,w),dtype=np.uint8)*255; masks['background'] = np.zeros((h,w),dtype=np.uint8)
    try:
        det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path='/home/claude/blaze_face_short_range.tflite'),
            min_detection_confidence=0.3))
        result = det.detect(mp_img); det.close()
        if result.detections:
            face_mask = np.zeros((h,w),dtype=np.uint8)
            for d in result.detections:
                b = d.bounding_box; pad = int(b.width*0.25)
                x1,y1 = max(0,b.origin_x-pad), max(0,b.origin_y-pad)
                x2,y2 = min(w,b.origin_x+b.width+pad), min(h,b.origin_y+b.height+int(b.height*0.15))
                face_mask[y1:y2, x1:x2] = 255
            masks['face'] = face_mask
    except Exception as e:
        print(f"  face detection failed: {e}")
    return masks


def _extract_region(image_path, mask, expand=0, scale=1.0):
    """Extract masked region to temp PNG, optionally downscaled."""
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    mask = cv2.resize(mask, (w,h), interpolation=cv2.INTER_NEAREST)
    if expand > 0:
        mask = cv2.dilate(mask, np.ones((expand,expand), np.uint8))
    rgba = np.zeros((h,w,4), dtype=np.uint8)
    rgba[:,:,:3] = img_rgb; rgba[:,:,3] = mask
    if scale != 1.0:
        new_w, new_h = max(64,int(w*scale)), max(64,int(h*scale))
        rgba = cv2.resize(rgba, (new_w,new_h), interpolation=cv2.INTER_AREA)
    tmp = tempfile.mktemp(suffix=".png"); Image.fromarray(rgba).save(tmp); return tmp


def _mask_to_clip_path(mask, img_w, img_h, svg_w, svg_h, clip_id, simplify=4):
    """Convert numpy mask to SVG <clipPath> element."""
    mask_resized = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
    contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    sx, sy = svg_w / img_w, svg_h / img_h
    polys = []
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:  # top 5 by area
        if cv2.contourArea(c) < img_w * img_h * 0.001: continue  # skip tiny
        approx = cv2.approxPolyDP(c, simplify, closed=True)
        if len(approx) < 3: continue
        pts = " ".join(f"{p[0][0]*sx:.1f},{p[0][1]*sy:.1f}" for p in approx)
        polys.append(f'<polygon points="{pts}"/>')
    if not polys: return None
    return f'<clipPath id="{clip_id}">\n    ' + '\n    '.join(polys) + '\n  </clipPath>'


def _extract_svg_elements(svg_content):
    """Extract rect + path elements from SVG."""
    rects = re.findall(r'<rect[^>]*/>', svg_content)
    paths = re.findall(r'<path[^>]*/>', svg_content)
    return rects + paths


def _extract_viewbox(svg_content):
    m = re.search(r'viewBox="([^"]+)"', svg_content)
    return m.group(1) if m else "0 0 800 800"


def portrait_mode(image_path, image_type=None,
                  face_K=None, face_smooth=None, face_mode=None,
                  body_K=None, body_smooth=None, body_mode=None,
                  background_K=None, background_smooth=None, background_mode=None,
                  background_scale=None, svg_width=800):
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
    face_K            = face_K            or d["face_K"]
    face_smooth       = face_smooth       or d["face_smooth"]
    face_mode         = face_mode         or d["face_mode"]
    body_K            = body_K            or d["body_K"]
    body_smooth       = body_smooth       or d["body_smooth"]
    body_mode         = body_mode         or d["body_mode"]
    background_K      = background_K      or d["background_K"]
    background_smooth = background_smooth or d["background_smooth"]
    background_mode   = background_mode   or d["background_mode"]
    background_scale  = background_scale  if background_scale is not None else d["background_scale"]

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
        body_mask[masks['face'] > 128] = 0  # subtract face from body

    # --- Layer processing ---
    print("\n[2] Processing layers")
    layers = {}; stats = {"image_type": image_type}

    # Background — downscaled, full canvas (bottom layer, no clip needed)
    print(f"    Background: K={background_K}, smooth={background_smooth}, scale={background_scale}")
    bg_tmp = _extract_region(image_path, masks['background'], scale=background_scale)
    try:
        bg_svg, _ = image_to_svg(bg_tmp, mode=background_mode, K=background_K,
                                  smooth=background_smooth, svg_width=svg_width, pipeline="fill")
        layers['background'] = bg_svg
        stats['background'] = len(re.findall(r'<path', bg_svg))
    finally:
        os.unlink(bg_tmp)

    # Body — full resolution, clipped to person-minus-face
    print(f"    Body: K={body_K}, smooth={body_smooth}")
    body_tmp = _extract_region(image_path, body_mask, expand=5)
    try:
        body_svg, _ = image_to_svg(body_tmp, mode=body_mode, K=body_K,
                                    smooth=body_smooth, svg_width=svg_width, pipeline="fill")
        layers['body'] = body_svg
        stats['body'] = len(re.findall(r'<path', body_svg))
    finally:
        os.unlink(body_tmp)

    # Face — full resolution, clipped to face bbox
    if 'face' in masks:
        print(f"    Face: K={face_K}, smooth={face_smooth}")
        face_tmp = _extract_region(image_path, masks['face'], expand=10)
        try:
            face_svg, _ = image_to_svg(face_tmp, mode=face_mode, K=face_K,
                                        smooth=face_smooth, svg_width=svg_width, pipeline="fill")
            layers['face'] = face_svg
            stats['face'] = len(re.findall(r'<path', face_svg))
        finally:
            os.unlink(face_tmp)

    # --- Compositing with clipPaths ---
    print("\n[3] Compositing")
    # Use face (or body) for the reference coordinate system
    ref_svg = layers.get('face') or layers.get('body') or layers.get('background')
    vb = _extract_viewbox(ref_svg)
    vb_parts = [float(x) for x in vb.split()]
    svg_w_out, svg_h_out = vb_parts[2], vb_parts[3]

    # Build clipPaths from masks
    clips = {}
    for lname, mask in [('body', body_mask), ('face', masks.get('face'))]:
        if mask is not None and lname in layers:
            clip = _mask_to_clip_path(mask, img_w, img_h, svg_w_out, svg_h_out, f"clip_{lname}")
            if clip:
                clips[lname] = clip

    # Assemble SVG
    lines = ['<?xml version="1.0"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">']

    if clips:
        lines.append('  <defs>')
        for clip in clips.values():
            lines.append(f'    {clip}')
        lines.append('  </defs>')

    for lname in ['background', 'body', 'face']:
        if lname not in layers: continue
        elements = _extract_svg_elements(layers[lname])
        layer_vb = _extract_viewbox(layers[lname])

        if lname == 'background' and layer_vb != vb:
            # Scale from downscaled coordinate space to full
            bg_parts = [float(x) for x in layer_vb.split()]
            sx = svg_w_out / bg_parts[2]; sy = svg_h_out / bg_parts[3]
            lines.append(f'  <g id="background" transform="scale({sx:.6f},{sy:.6f})">')
        elif lname in clips:
            lines.append(f'  <g id="{lname}" clip-path="url(#clip_{lname})">')
        else:
            lines.append(f'  <g id="{lname}">')

        lines.extend(f'    {el}' for el in elements)
        lines.append('  </g>')

    lines.append('</svg>')
    svg = '\n'.join(lines)
    stats['total'] = sum(v for k,v in stats.items() if k != 'image_type')
    print(f"    Total: {stats['total']} paths, {len(svg)//1024}KB")
    return svg, stats
