"""
see.py — Augmented vision tools for Claude
Compensates for measured visual blindspots using programmatic image analysis.
All image-producing functions save to /home/claude/see_*.png and return the path.
Dependencies: Pillow (pre-installed), numpy (via pip if needed)
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from collections import Counter

OUT_DIR = "/home/claude"

def _out(name):
    return os.path.join(OUT_DIR, f"see_{name}.png")

def _load(path):
    return Image.open(path).convert('RGB')

def _font(size=11):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

def _crop_region(img, region):
    """region = (x, y, w, h) → PIL crop box"""
    x, y, w, h = region
    return img.crop((x, y, x + w, y + h))


# ============================================================
# GRID — systematic spatial decomposition
# ============================================================
# @lat: [[visual-pipeline#Augmented Vision]]
def grid(path, rows=3, cols=3, labels=True):
    """Split image into labeled grid cells. Returns path to composite."""
    img = _load(path)
    W, H = img.size
    cell_w, cell_h = W // cols, H // rows
    
    # Create composite with borders and labels
    pad = 4
    comp_w = cols * (cell_w + pad) + pad
    comp_h = rows * (cell_h + pad + (18 if labels else 0)) + pad
    comp = Image.new('RGB', (comp_w, comp_h), (60, 60, 60))
    draw = ImageDraw.Draw(comp)
    font = _font(10)
    
    for r in range(rows):
        for c in range(cols):
            x0 = c * cell_w
            y0 = r * cell_h
            cell = img.crop((x0, y0, min(x0 + cell_w, W), min(y0 + cell_h, H)))
            
            cx = pad + c * (cell_w + pad)
            cy = pad + r * (cell_h + pad + (18 if labels else 0))
            comp.paste(cell, (cx, cy + (18 if labels else 0)))
            
            if labels:
                label = f"{chr(65+r)}{c+1} ({x0},{y0})"
                draw.text((cx + 2, cy), label, fill=(200, 200, 200), font=font)
    
    out = _out("grid")
    comp.save(out, quality=95)
    return out


# ============================================================
# SAMPLE — exact RGB at coordinates
# ============================================================
def sample(path, points, radius=3):
    """Get exact RGB values at pixel coordinates. Returns list of dicts.
    points: list of (x,y) tuples
    radius: averaging radius to handle noise (0 = single pixel)
    """
    img = _load(path)
    W, H = img.size
    results = []
    
    for px, py in points:
        if radius == 0:
            r, g, b = img.getpixel((px, py))
        else:
            pixels = []
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < W and 0 <= ny < H:
                        pixels.append(img.getpixel((nx, ny)))
            if pixels:
                r = sum(p[0] for p in pixels) // len(pixels)
                g = sum(p[1] for p in pixels) // len(pixels)
                b = sum(p[2] for p in pixels) // len(pixels)
            else:
                r, g, b = 0, 0, 0
        
        results.append({
            'x': px, 'y': py,
            'rgb': (r, g, b),
            'hex': f'#{r:02x}{g:02x}{b:02x}',
            'luminance': int(0.299 * r + 0.587 * g + 0.114 * b)
        })
    
    # Also create a visual showing sample points
    vis = img.copy()
    vd = ImageDraw.Draw(vis)
    font = _font(9)
    for i, res in enumerate(results):
        x, y = res['x'], res['y']
        r, g, b = res['rgb']
        # Crosshair
        vd.line([(x-8, y), (x+8, y)], fill=(255, 255, 0), width=1)
        vd.line([(x, y-8), (x, y+8)], fill=(255, 255, 0), width=1)
        # Swatch + label
        lx, ly = x + 12, y - 8
        vd.rectangle([lx, ly, lx+30, ly+16], fill=(r, g, b), outline=(255, 255, 0))
        vd.text((lx+34, ly), f"({r},{g},{b})", fill=(255, 255, 0), font=font)
    
    out = _out("sample")
    vis.save(out, quality=95)
    
    # Print results for immediate use
    for res in results:
        print(f"  ({res['x']},{res['y']}): RGB{res['rgb']} {res['hex']} L={res['luminance']}")
    
    return results


# ============================================================
# HISTOGRAM — color distribution analysis
# ============================================================
def histogram(path, region=None, channel='all'):
    """Analyze color distribution. Returns path to histogram visualization.
    channel: 'all', 'r', 'g', 'b', 'luminance'
    """
    img = _load(path)
    if region:
        img = _crop_region(img, region)
    W, H = img.size
    
    # Compute histograms
    r_hist = [0] * 256
    g_hist = [0] * 256
    b_hist = [0] * 256
    l_hist = [0] * 256
    
    for y in range(H):
        for x in range(W):
            r, g, b = img.getpixel((x, y))
            r_hist[r] += 1
            g_hist[g] += 1
            b_hist[b] += 1
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            l_hist[lum] += 1
    
    # Draw histogram
    hist_w, hist_h = 520, 200
    vis = Image.new('RGB', (hist_w, hist_h + 30), (30, 30, 30))
    vd = ImageDraw.Draw(vis)
    font = _font(9)
    
    channels = {'r': (r_hist, (220,60,60)), 'g': (g_hist, (60,180,60)),
                'b': (b_hist, (60,60,220)), 'luminance': (l_hist, (200,200,200))}
    
    if channel == 'all':
        draw_channels = ['r', 'g', 'b']
    else:
        draw_channels = [channel]
    
    max_val = max(max(h) for h, _ in [channels[c] for c in draw_channels])
    if max_val == 0:
        max_val = 1
    
    for ch_name in draw_channels:
        hist_data, color = channels[ch_name]
        for i in range(256):
            bar_h = int((hist_data[i] / max_val) * (hist_h - 10))
            x = 10 + i * 2
            if x < hist_w - 10:
                vd.line([(x, hist_h - bar_h), (x, hist_h)], fill=color, width=1)
    
    # Axis labels
    for v in [0, 64, 128, 192, 255]:
        x = 10 + v * 2
        vd.text((x - 5, hist_h + 5), str(v), fill=(150, 150, 150), font=font)
    
    # Stats
    total = W * H
    mean_r = sum(i * r_hist[i] for i in range(256)) // total
    mean_g = sum(i * g_hist[i] for i in range(256)) // total
    mean_b = sum(i * b_hist[i] for i in range(256)) // total
    vd.text((10, hist_h + 18), f"Mean RGB: ({mean_r},{mean_g},{mean_b})  Pixels: {total}",
            fill=(180, 180, 180), font=font)
    
    out = _out("histogram")
    vis.save(out, quality=95)
    print(f"  Mean RGB: ({mean_r},{mean_g},{mean_b}), {total} pixels")
    return out


# ============================================================
# ENHANCE — contrast/brightness boosting
# ============================================================
def enhance(path, region=None, factor=2.0, mode='contrast'):
    """Boost contrast/brightness/color/sharpness. Saves enhanced version.
    mode: 'contrast', 'brightness', 'color', 'sharpness', 'auto'
    auto: applies CLAHE-like local contrast enhancement
    """
    img = _load(path)
    
    if region:
        crop = _crop_region(img, region)
    else:
        crop = img
    
    if mode == 'contrast':
        enhanced = ImageEnhance.Contrast(crop).enhance(factor)
    elif mode == 'brightness':
        enhanced = ImageEnhance.Brightness(crop).enhance(factor)
    elif mode == 'color':
        enhanced = ImageEnhance.Color(crop).enhance(factor)
    elif mode == 'sharpness':
        enhanced = ImageEnhance.Sharpness(crop).enhance(factor)
    elif mode == 'auto':
        # Stretch histogram to full range (simple auto-levels)
        pixels = list(crop.getdata())
        r_vals = [p[0] for p in pixels]
        g_vals = [p[1] for p in pixels]
        b_vals = [p[2] for p in pixels]
        
        def stretch(vals):
            lo, hi = min(vals), max(vals)
            if hi == lo:
                return vals
            return [int(255 * (v - lo) / (hi - lo)) for v in vals]
        
        r_s, g_s, b_s = stretch(r_vals), stretch(g_vals), stretch(b_vals)
        enhanced = Image.new('RGB', crop.size)
        enhanced.putdata(list(zip(r_s, g_s, b_s)))
    else:
        enhanced = crop
    
    if region:
        # Side-by-side: original region + enhanced
        w, h = crop.size
        comp = Image.new('RGB', (w * 2 + 10, h), (60, 60, 60))
        comp.paste(crop, (0, 0))
        comp.paste(enhanced, (w + 10, 0))
        out = _out("enhance")
        comp.save(out, quality=95)
    else:
        out = _out("enhance")
        enhanced.save(out, quality=95)
    
    return out


# ============================================================
# EDGES — boundary detection
# ============================================================
def edges(path, threshold=50, region=None):
    """Sobel edge detection. Returns edge map (white on black)."""
    img = _load(path)
    if region:
        img = _crop_region(img, region)
    
    # Convert to grayscale
    gray = img.convert('L')
    W, H = gray.size
    
    edge_img = Image.new('L', (W, H), 0)
    
    # Sobel kernels
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            # 3x3 neighborhood
            p = [[gray.getpixel((x+dx-1, y+dy-1)) for dx in range(3)] for dy in range(3)]
            
            gx = (-p[0][0] + p[0][2] - 2*p[1][0] + 2*p[1][2] - p[2][0] + p[2][2])
            gy = (-p[0][0] - 2*p[0][1] - p[0][2] + p[2][0] + 2*p[2][1] + p[2][2])
            
            mag = min(255, int(math.sqrt(gx*gx + gy*gy)))
            if mag > threshold:
                edge_img.putpixel((x, y), mag)
    
    out = _out("edges")
    edge_img.save(out)
    return out


# ============================================================
# GRADIENT MAP — local gradient magnitude
# ============================================================
def gradient_map(path, region=None):
    """Compute and visualize local gradient magnitude. Reveals hidden gradients."""
    img = _load(path)
    if region:
        img = _crop_region(img, region)
    
    gray = img.convert('L')
    W, H = gray.size
    
    grad = Image.new('L', (W, H), 0)
    
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            dx = abs(gray.getpixel((x+1, y)) - gray.getpixel((x-1, y)))
            dy = abs(gray.getpixel((x, y+1)) - gray.getpixel((x, y-1)))
            mag = min(255, (dx + dy) * 4)  # amplified
            grad.putpixel((x, y), mag)
    
    out = _out("gradient_map")
    grad.save(out)
    return out


# ============================================================
# ISOLATE — decontextualize a region
# ============================================================
def isolate(path, region, padding=20, bg=(128, 128, 128)):
    """Extract region onto neutral background. Removes context-dependent color bias."""
    img = _load(path)
    crop = _crop_region(img, region)
    w, h = crop.size
    
    canvas = Image.new('RGB', (w + 2*padding, h + 2*padding), bg)
    canvas.paste(crop, (padding, padding))
    
    out = _out("isolate")
    canvas.save(out, quality=95)
    return out


# ============================================================
# COMPARE — side-by-side with diff
# ============================================================
def compare(path, r1, r2, amplify=10):
    """Compare two regions with amplified diff overlay.
    r1, r2: (x, y, w, h) tuples
    amplify: difference amplification factor
    """
    img = _load(path)
    c1 = _crop_region(img, r1)
    c2 = _crop_region(img, r2)
    
    # Resize to match
    w = min(c1.size[0], c2.size[0])
    h = min(c1.size[1], c2.size[1])
    c1 = c1.resize((w, h))
    c2 = c2.resize((w, h))
    
    # Compute diff
    diff = Image.new('RGB', (w, h))
    for y in range(h):
        for x in range(w):
            p1 = c1.getpixel((x, y))
            p2 = c2.getpixel((x, y))
            dr = min(255, abs(p1[0] - p2[0]) * amplify)
            dg = min(255, abs(p1[1] - p2[1]) * amplify)
            db = min(255, abs(p1[2] - p2[2]) * amplify)
            diff.putpixel((x, y), (dr, dg, db))
    
    # Composite: r1 | r2 | diff
    gap = 6
    comp = Image.new('RGB', (w * 3 + gap * 2, h + 20), (60, 60, 60))
    comp.paste(c1, (0, 0))
    comp.paste(c2, (w + gap, 0))
    comp.paste(diff, (2 * (w + gap), 0))
    
    cd = ImageDraw.Draw(comp)
    font = _font(9)
    cd.text((w//2 - 10, h + 3), "R1", fill=(200, 200, 200), font=font)
    cd.text((w + gap + w//2 - 10, h + 3), "R2", fill=(200, 200, 200), font=font)
    cd.text((2*(w+gap) + w//2 - 15, h + 3), f"Diff x{amplify}", fill=(200, 200, 200), font=font)
    
    # Compute stats
    total_diff = 0
    max_diff = 0
    for y in range(h):
        for x in range(w):
            p1 = c1.getpixel((x, y))
            p2 = c2.getpixel((x, y))
            d = sum(abs(a-b) for a, b in zip(p1, p2))
            total_diff += d
            max_diff = max(max_diff, d)
    
    avg_diff = total_diff / (w * h * 3) if w * h > 0 else 0
    print(f"  Avg channel diff: {avg_diff:.1f}, Max: {max_diff}, Size: {w}x{h}")
    
    out = _out("compare")
    comp.save(out, quality=95)
    return out


# ============================================================
# COUNT ELEMENTS — connected component analysis
# ============================================================
def count_elements(path, region=None, color_range=None, min_size=3):
    """Count distinct colored elements using flood fill.
    color_range: ((r_min,g_min,b_min), (r_max,g_max,b_max)) or None for auto
    min_size: minimum pixel area to count as an element
    Returns count and centroids.
    """
    img = _load(path)
    if region:
        img = _crop_region(img, region)
    W, H = img.size
    
    # Build binary mask
    mask = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            r, g, b = img.getpixel((x, y))
            if color_range:
                lo, hi = color_range
                if lo[0] <= r <= hi[0] and lo[1] <= g <= hi[1] and lo[2] <= b <= hi[2]:
                    mask[y][x] = True
            else:
                # Auto: non-background (anything not within 20 of image corner color)
                corner = img.getpixel((0, 0))
                if any(abs(a - b) > 20 for a, b in zip((r, g, b), corner)):
                    mask[y][x] = True
    
    # Connected components (4-connected flood fill)
    visited = [[False] * W for _ in range(H)]
    components = []
    
    for y in range(H):
        for x in range(W):
            if mask[y][x] and not visited[y][x]:
                # BFS
                queue = [(x, y)]
                visited[y][x] = True
                pixels = []
                while queue:
                    cx, cy = queue.pop(0)
                    pixels.append((cx, cy))
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = cx+dx, cy+dy
                        if 0<=nx<W and 0<=ny<H and mask[ny][nx] and not visited[ny][nx]:
                            visited[ny][nx] = True
                            queue.append((nx, ny))
                
                if len(pixels) >= min_size:
                    cx_avg = sum(p[0] for p in pixels) / len(pixels)
                    cy_avg = sum(p[1] for p in pixels) / len(pixels)
                    components.append({
                        'centroid': (int(cx_avg), int(cy_avg)),
                        'size': len(pixels),
                        'color': img.getpixel((int(cx_avg), int(cy_avg)))
                    })
    
    # Visualize
    vis = img.copy()
    vd = ImageDraw.Draw(vis)
    font = _font(9)
    for i, comp in enumerate(components):
        cx, cy = comp['centroid']
        vd.ellipse([cx-6, cy-6, cx+6, cy+6], outline=(255, 255, 0), width=2)
        vd.text((cx+8, cy-5), str(i+1), fill=(255, 255, 0), font=font)
    
    out = _out("count")
    vis.save(out, quality=95)
    
    print(f"  Found {len(components)} elements (min_size={min_size})")
    for i, c in enumerate(components[:20]):
        print(f"    #{i+1}: centroid={c['centroid']}, size={c['size']}px, color=RGB{c['color']}")
    
    return components


# ============================================================
# DENOISE — median filter for noise reduction
# ============================================================
def denoise(path, region=None, strength=3):
    """Apply median filter to reduce noise and reveal subtle features."""
    img = _load(path)
    if region:
        crop = _crop_region(img, region)
        denoised = crop.filter(ImageFilter.MedianFilter(size=strength if strength % 2 == 1 else strength + 1))
        # Side-by-side
        w, h = crop.size
        comp = Image.new('RGB', (w * 2 + 10, h), (60, 60, 60))
        comp.paste(crop, (0, 0))
        comp.paste(denoised, (w + 10, 0))
        out = _out("denoise")
        comp.save(out, quality=95)
    else:
        denoised = img.filter(ImageFilter.MedianFilter(size=strength if strength % 2 == 1 else strength + 1))
        out = _out("denoise")
        denoised.save(out, quality=95)
    return out


# ============================================================
# PALETTE — dominant color extraction
# ============================================================
# @lat: [[visual-pipeline#Augmented Vision]]
def palette(path, n=8, region=None):
    """Extract n dominant colors using quantization. Returns colors + proportions."""
    img = _load(path)
    if region:
        img = _crop_region(img, region)
    
    # Quantize to n colors
    quantized = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()[:n*3]
    
    # Count pixels per color
    pixels = list(quantized.getdata())
    counts = Counter(pixels)
    total = len(pixels)
    
    # Build results
    colors = []
    for i in range(n):
        r, g, b = palette_data[i*3], palette_data[i*3+1], palette_data[i*3+2]
        count = counts.get(i, 0)
        pct = (count / total) * 100 if total > 0 else 0
        colors.append({'rgb': (r, g, b), 'hex': f'#{r:02x}{g:02x}{b:02x}', 'pct': round(pct, 1)})
    
    colors.sort(key=lambda c: c['pct'], reverse=True)
    
    # Visualize palette
    swatch_w, swatch_h = 60, 40
    vis_w = n * (swatch_w + 4) + 4
    vis = Image.new('RGB', (vis_w, swatch_h + 20), (60, 60, 60))
    vd = ImageDraw.Draw(vis)
    font = _font(8)
    
    for i, c in enumerate(colors):
        x = 4 + i * (swatch_w + 4)
        vd.rectangle([x, 0, x + swatch_w, swatch_h], fill=c['rgb'])
        vd.text((x + 2, swatch_h + 2), f"{c['pct']}%", fill=(200, 200, 200), font=font)
    
    out = _out("palette")
    vis.save(out, quality=95)
    
    for c in colors:
        print(f"  RGB{c['rgb']} {c['hex']}: {c['pct']}%")
    
    return colors


# ============================================================
# CROP — simple crop + zoom helper
# ============================================================
def crop(path, region, zoom=1):
    """Crop region and optionally zoom (nearest-neighbor for pixel-level inspection)."""
    img = _load(path)
    cropped = _crop_region(img, region)
    
    if zoom > 1:
        w, h = cropped.size
        cropped = cropped.resize((w * zoom, h * zoom), Image.NEAREST)
    
    out = _out("crop")
    cropped.save(out, quality=95)
    return out
