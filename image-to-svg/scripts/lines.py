"""Line extraction for graphic/line-art inputs.

Implements Pass 1 of the compositional pipeline:
thin feature isolation -> skeletonize -> Hough -> merge -> measure -> emit SVG strokes.

Usage:
    from lines import classify_input, extract_lines, suppress_line_regions

    classification = classify_input(img_rgb)
    if classification["is_graphic"]:
        lines, thin_mask = extract_lines(img_rgb, scale_x, scale_y)
        img_for_fills = suppress_line_regions(img_rgb, thin_mask)
"""
import cv2
import numpy as np


# @lat: [[visual-pipeline#Line Art Extraction]]
def classify_input(img_rgb):
    """Detect whether image is graphic-style (lines, strokes, geometric) vs photographic.

    Returns dict with:
        is_graphic: bool
        edge_density: fraction of edge pixels (higher = more graphic)
        bimodality: luminance bimodality coefficient (higher = more bimodal)
        line_density: Hough lines per 10k pixels
        n_lines: raw line count
    """
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # Edge density via Canny
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / edges.size

    # Luminance bimodality
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist_norm = hist / hist.sum()
    mean_lum = np.sum(np.arange(256) * hist_norm)
    var_lum = np.sum(((np.arange(256) - mean_lum) ** 2) * hist_norm)
    std_lum = np.sqrt(var_lum) if var_lum > 0 else 1.0
    skewness = np.sum(((np.arange(256) - mean_lum) ** 3) * hist_norm) / (std_lum ** 3)
    kurtosis = np.sum(((np.arange(256) - mean_lum) ** 4) * hist_norm) / (std_lum ** 4)
    bimodality = (skewness ** 2 + 1) / kurtosis if kurtosis > 0 else 0

    # Straight line density via Hough
    min_len = max(20, int(min(h, w) * 0.03))
    hough_lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50,
                                  minLineLength=min_len, maxLineGap=10)
    n_lines = len(hough_lines) if hough_lines is not None else 0
    line_density = n_lines / max(1, (h * w) / 10000)

    is_graphic = (edge_density > 0.05 and bimodality > 0.35) or line_density > 3.0

    return {
        "is_graphic": is_graphic,
        "edge_density": round(edge_density, 4),
        "bimodality": round(bimodality, 4),
        "line_density": round(line_density, 2),
        "n_lines": n_lines,
    }


def isolate_thin_features(img_rgb, dark_threshold=None):
    """Isolate thin linear features via morphological erosion.

    Logic: thick shapes survive heavy erosion, thin lines don't.
    thin_mask = dark_mask AND NOT erode(dark_mask, large_kernel)

    Returns:
        thin_mask: uint8 mask of thin features (255 = thin)
        dark_mask: uint8 mask of all dark features
    """
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    if dark_threshold is None:
        dark_threshold, _ = cv2.threshold(gray, 0, 255,
                                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        dark_threshold = min(dark_threshold, 160)

    dark_mask = (gray < dark_threshold).astype(np.uint8) * 255

    # Heavy erosion: only thick features survive
    k_size = max(7, int(min(img_rgb.shape[:2]) * 0.02) | 1)  # ~2% of min dim, odd
    k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    eroded = cv2.erode(dark_mask, k_large, iterations=1)

    # Thin features = dark but didn't survive erosion
    thin_mask = cv2.bitwise_and(dark_mask, cv2.bitwise_not(eroded))

    # Clean up noise
    k_small = np.ones((3, 3), np.uint8)
    thin_mask = cv2.morphologyEx(thin_mask, cv2.MORPH_OPEN, k_small, iterations=1)

    return thin_mask, dark_mask


def _skeletonize_mask(mask):
    """Skeletonize a binary mask to 1px centerlines."""
    from skimage.morphology import skeletonize as sk_skel
    return (sk_skel(mask > 0).astype(np.uint8) * 255)


def _detect_hough_lines(skeleton, min_line_length=20, max_line_gap=8):
    """Detect straight line segments via probabilistic Hough transform."""
    lines = cv2.HoughLinesP(skeleton, rho=1, theta=np.pi / 180,
                            threshold=15, minLineLength=min_line_length,
                            maxLineGap=max_line_gap)
    if lines is None:
        return []
    return [tuple(line[0]) for line in lines]


def _line_angle(x1, y1, x2, y2):
    """Angle in radians [0, pi)."""
    return np.arctan2(y2 - y1, x2 - x1) % np.pi


def _line_length(x1, y1, x2, y2):
    """Euclidean length."""
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _perp_dist(px, py, x1, y1, x2, y2):
    """Perpendicular distance from point to line."""
    dx, dy = x2 - x1, y2 - y1
    length = np.sqrt(dx * dx + dy * dy)
    if length < 1e-6:
        return np.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    return abs(dy * px - dx * py + x2 * y1 - y2 * x1) / length


def merge_collinear(segments, angle_tol=0.12, dist_tol=6.0, gap_tol=15.0):
    """Merge collinear line segments.

    Segments with matching angle (within angle_tol radians), small
    perpendicular distance, and close endpoints are merged.

    Args:
        segments: list of (x1, y1, x2, y2) tuples
        angle_tol: max angle difference in radians (~7 degrees)
        dist_tol: max perpendicular distance between midpoints
        gap_tol: max endpoint gap for merging
    """
    if not segments:
        return []

    props = []
    for seg in segments:
        x1, y1, x2, y2 = seg
        props.append({
            "seg": seg,
            "angle": _line_angle(x1, y1, x2, y2),
            "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
            "length": _line_length(x1, y1, x2, y2),
        })

    merged = []
    used = [False] * len(props)

    for i in range(len(props)):
        if used[i]:
            continue

        group = [props[i]]
        used[i] = True

        for j in range(i + 1, len(props)):
            if used[j]:
                continue

            # Angle check (handle wraparound at pi)
            da = abs(props[i]["angle"] - props[j]["angle"])
            da = min(da, np.pi - da)
            if da > angle_tol:
                continue

            # Perpendicular distance: midpoint of j to line of i
            x1, y1, x2, y2 = props[i]["seg"]
            perp = _perp_dist(props[j]["mx"], props[j]["my"], x1, y1, x2, y2)
            if perp > dist_tol:
                continue

            # Endpoint gap check
            pts_i = [(x1, y1), (x2, y2)]
            x1j, y1j, x2j, y2j = props[j]["seg"]
            pts_j = [(x1j, y1j), (x2j, y2j)]
            min_gap = min(
                np.sqrt((pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2)
                for pi in pts_i for pj in pts_j
            )
            max_len = max(props[i]["length"], props[j]["length"])
            if min_gap > gap_tol + max_len * 0.5:
                continue

            group.append(props[j])
            used[j] = True

        if len(group) == 1:
            merged.append(group[0]["seg"])
        else:
            # Project all endpoints onto dominant direction, take extremes
            all_pts = []
            for g in group:
                gx1, gy1, gx2, gy2 = g["seg"]
                all_pts.extend([(gx1, gy1), (gx2, gy2)])

            longest = max(group, key=lambda g: g["length"])
            lx1, ly1, lx2, ly2 = longest["seg"]
            dx, dy = lx2 - lx1, ly2 - ly1
            norm = np.sqrt(dx * dx + dy * dy)
            if norm < 1e-6:
                merged.append(group[0]["seg"])
                continue
            ux, uy = dx / norm, dy / norm

            projections = sorted((ux * px + uy * py, px, py)
                                 for px, py in all_pts)
            _, sx, sy = projections[0]
            _, ex, ey = projections[-1]
            merged.append((int(sx), int(sy), int(ex), int(ey)))

    return merged


def merge_segments_to_curves(lines, merge_distance=10, merge_angle=30):
    """Merge nearby collinear line segments into bezier curves.

    Clusters extracted line segments by endpoint proximity and angular
    continuity, then fits smooth bezier curves to each chain.

    Args:
        lines: list of dicts with {x1, y1, x2, y2, color, stroke_width}
        merge_distance: max endpoint distance for chaining (in SVG units)
        merge_angle: max angular deviation in degrees for chaining

    Returns:
        list of dicts — either:
          {"path_d": str, "color": hex, "stroke_width": float}  (merged curves)
          {"x1", "y1", "x2", "y2", "color", "stroke_width"}    (isolated segments)
    """
    if not lines:
        return []

    angle_tol_rad = merge_angle * np.pi / 180

    def seg_angle(seg):
        return np.arctan2(seg["y2"] - seg["y1"], seg["x2"] - seg["x1"]) % np.pi

    def endpoint_dist(seg_a, seg_b):
        """Min distance between any pair of endpoints."""
        pts_a = [(seg_a["x1"], seg_a["y1"]), (seg_a["x2"], seg_a["y2"])]
        pts_b = [(seg_b["x1"], seg_b["y1"]), (seg_b["x2"], seg_b["y2"])]
        return min(
            np.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
            for a in pts_a for b in pts_b
        )

    # Build chains via greedy nearest-neighbor with angle + distance constraints
    used = [False] * len(lines)
    chains = []

    for i in range(len(lines)):
        if used[i]:
            continue
        chain = [i]
        used[i] = True

        # Extend chain in both directions
        changed = True
        while changed:
            changed = False
            head = chain[0]
            tail = chain[-1]

            best_head = (-1, float("inf"))
            best_tail = (-1, float("inf"))

            for j in range(len(lines)):
                if used[j]:
                    continue

                # Angle check against the neighbor in the chain
                da_head = abs(seg_angle(lines[head]) - seg_angle(lines[j]))
                da_head = min(da_head, np.pi - da_head)
                da_tail = abs(seg_angle(lines[tail]) - seg_angle(lines[j]))
                da_tail = min(da_tail, np.pi - da_tail)

                d_head = endpoint_dist(lines[head], lines[j])
                d_tail = endpoint_dist(lines[tail], lines[j])

                if da_head <= angle_tol_rad and d_head <= merge_distance:
                    if d_head < best_head[1]:
                        best_head = (j, d_head)
                if da_tail <= angle_tol_rad and d_tail <= merge_distance:
                    if d_tail < best_tail[1]:
                        best_tail = (j, d_tail)

            if best_tail[0] >= 0:
                chain.append(best_tail[0])
                used[best_tail[0]] = True
                changed = True
            if best_head[0] >= 0 and best_head[0] != best_tail[0]:
                chain.insert(0, best_head[0])
                used[best_head[0]] = True
                changed = True

        chains.append(chain)

    # Convert chains to output
    result = []
    for chain in chains:
        if len(chain) == 1:
            # Isolated segment — pass through unchanged
            result.append(dict(lines[chain[0]]))
            continue

        # Order chain endpoints into a polyline
        # Use median color and stroke width from chain members
        chain_segs = [lines[idx] for idx in chain]
        colors = [s["color"] for s in chain_segs]
        widths = [s["stroke_width"] for s in chain_segs]
        # Most common color
        from collections import Counter
        color = Counter(colors).most_common(1)[0][0]
        stroke_width = round(float(np.median(widths)), 1)

        # Build ordered point sequence by walking closest endpoints
        ordered_pts = [(chain_segs[0]["x1"], chain_segs[0]["y1"]),
                       (chain_segs[0]["x2"], chain_segs[0]["y2"])]
        remaining = list(range(1, len(chain_segs)))

        while remaining:
            last_pt = ordered_pts[-1]
            best_idx = -1
            best_dist = float("inf")
            best_flip = False

            for ri in remaining:
                seg = chain_segs[ri]
                d1 = np.sqrt((last_pt[0] - seg["x1"]) ** 2 + (last_pt[1] - seg["y1"]) ** 2)
                d2 = np.sqrt((last_pt[0] - seg["x2"]) ** 2 + (last_pt[1] - seg["y2"]) ** 2)
                if d1 < best_dist:
                    best_dist, best_idx, best_flip = d1, ri, False
                if d2 < best_dist:
                    best_dist, best_idx, best_flip = d2, ri, True

            seg = chain_segs[best_idx]
            if best_flip:
                ordered_pts.append((seg["x2"], seg["y2"]))
                ordered_pts.append((seg["x1"], seg["y1"]))
            else:
                ordered_pts.append((seg["x1"], seg["y1"]))
                ordered_pts.append((seg["x2"], seg["y2"]))
            remaining.remove(best_idx)

        # Deduplicate consecutive near-identical points
        deduped = [ordered_pts[0]]
        for pt in ordered_pts[1:]:
            if np.sqrt((pt[0] - deduped[-1][0]) ** 2 + (pt[1] - deduped[-1][1]) ** 2) > 0.5:
                deduped.append(pt)

        # Fit bezier curve
        if len(deduped) == 2:
            # Two points — just a line, emit as segment
            result.append({
                "x1": deduped[0][0], "y1": deduped[0][1],
                "x2": deduped[1][0], "y2": deduped[1][1],
                "color": color, "stroke_width": stroke_width,
            })
        elif len(deduped) == 3:
            # Quadratic bezier through 3 points
            p0, p1, p2 = deduped
            path_d = (f"M {p0[0]:.1f},{p0[1]:.1f} "
                      f"Q {p1[0]:.1f},{p1[1]:.1f} "
                      f"{p2[0]:.1f},{p2[1]:.1f}")
            result.append({"path_d": path_d, "color": color, "stroke_width": stroke_width})
        else:
            # 4+ points — chain of quadratic beziers through midpoints
            parts = [f"M {deduped[0][0]:.1f},{deduped[0][1]:.1f}"]
            for k in range(1, len(deduped) - 1):
                # Control point is the actual point, endpoint is midpoint to next
                cx, cy = deduped[k]
                if k < len(deduped) - 2:
                    ex = (deduped[k][0] + deduped[k + 1][0]) / 2
                    ey = (deduped[k][1] + deduped[k + 1][1]) / 2
                else:
                    ex, ey = deduped[-1]
                parts.append(f"Q {cx:.1f},{cy:.1f} {ex:.1f},{ey:.1f}")
            path_d = " ".join(parts)
            result.append({"path_d": path_d, "color": color, "stroke_width": stroke_width})

    n_curves = sum(1 for r in result if "path_d" in r)
    n_lines = sum(1 for r in result if "x1" in r)
    print(f"  merge_to_curves: {n_curves} curves + {n_lines} lines from {len(lines)} segments")
    return result


def measure_stroke_width(mask, x1, y1, x2, y2, n_samples=5):
    """Measure stroke width perpendicular to a line segment.

    Returns median stroke width in pixels.
    """
    h, w = mask.shape[:2]
    dx, dy = x2 - x1, y2 - y1
    length = np.sqrt(dx * dx + dy * dy)
    if length < 1:
        return 2.0

    # Unit perpendicular vector
    px, py = -dy / length, dx / length

    widths = []
    for t in np.linspace(0.2, 0.8, n_samples):
        cx, cy = x1 + t * dx, y1 + t * dy
        width = 0
        for direction in [1, -1]:
            for step in range(1, 50):
                sx = int(cx + direction * step * px)
                sy = int(cy + direction * step * py)
                if sx < 0 or sx >= w or sy < 0 or sy >= h:
                    break
                if mask[sy, sx] == 0:
                    break
                width += 1
        widths.append(max(width, 1))

    return float(np.median(widths)) if widths else 2.0


def sample_line_color(img_rgb, mask, x1, y1, x2, y2, n_samples=10):
    """Sample the dominant color along a line from the original image.

    Returns hex color string.
    """
    h, w = img_rgb.shape[:2]
    colors = []

    for t in np.linspace(0.1, 0.9, n_samples):
        cx, cy = int(x1 + t * (x2 - x1)), int(y1 + t * (y2 - y1))
        if 0 <= cx < w and 0 <= cy < h and mask[cy, cx] > 0:
            colors.append(img_rgb[cy, cx])

    if not colors:
        return "#000000"

    median_color = np.median(colors, axis=0).astype(np.uint8)
    return f"#{median_color[0]:02x}{median_color[1]:02x}{median_color[2]:02x}"


# @lat: [[visual-pipeline#Line Art Extraction]]
def extract_lines(img_rgb, scale_x=1.0, scale_y=1.0, min_line_length=20,
                  stroke_width_cap=4.5, stroke_width_scale=0.65):
    """Extract line features from a graphic-style image.

    Full line extraction pass:
    1. Isolate thin features via morphological erosion
    2. Skeletonize to 1px centerlines
    3. Hough line detection for straight segments
    4. Merge collinear fragments
    5. Measure stroke width perpendicular to each line
    6. Sample color from masked pixels along the line

    Args:
        img_rgb: RGB image array
        scale_x, scale_y: coordinate scaling (image -> SVG)
        min_line_length: minimum line segment length in pixels
        stroke_width_cap: maximum SVG stroke width
        stroke_width_scale: multiply measured width by this (prevents bloat)

    Returns:
        (lines, thin_mask) where lines is list of dicts:
            {x1, y1, x2, y2, color, stroke_width}
    """
    thin_mask, _ = isolate_thin_features(img_rgb)

    skeleton = _skeletonize_mask(thin_mask)

    segments = _detect_hough_lines(skeleton, min_line_length=min_line_length)
    if not segments:
        return [], thin_mask

    merged = merge_collinear(segments)

    lines = []
    for x1, y1, x2, y2 in merged:
        width = measure_stroke_width(thin_mask, x1, y1, x2, y2)
        color = sample_line_color(img_rgb, thin_mask, x1, y1, x2, y2)

        svg_width = min(width * stroke_width_scale, stroke_width_cap)
        svg_width = max(svg_width, 1.0)

        lines.append({
            "x1": round(x1 * scale_x, 1),
            "y1": round(y1 * scale_y, 1),
            "x2": round(x2 * scale_x, 1),
            "y2": round(y2 * scale_y, 1),
            "color": color,
            "stroke_width": round(svg_width, 1),
        })

    print(f"  extract_lines: {len(lines)} strokes from {len(segments)} raw segments")
    return lines, thin_mask


def suppress_line_regions(img_rgb, thin_mask):
    """Remove line regions from image before fill quantization.

    Replaces thin feature pixels with local background estimate (median blur).
    Prevents lines from fragmenting K-means color clusters.

    Args:
        img_rgb: RGB image array
        thin_mask: uint8 mask from isolate_thin_features

    Returns:
        img_suppressed: RGB image with line regions replaced by background estimate
    """
    # Dilate mask to cover anti-aliased edges
    k = np.ones((5, 5), np.uint8)
    mask_dilated = cv2.dilate(thin_mask, k, iterations=1)

    # Background estimate via median blur (preserves edges, fills lines)
    bg_estimate = cv2.medianBlur(img_rgb, 15)

    result = img_rgb.copy()
    mask_bool = mask_dilated > 0
    result[mask_bool] = bg_estimate[mask_bool]

    return result


def lines_to_svg_elements(lines, opacity=1.0):
    """Convert extracted lines/curves to SVG element strings.

    Handles two item formats:
      - {"path_d": str, "color": hex, "stroke_width": float} → <path> element
      - {"x1", "y1", "x2", "y2", "color", "stroke_width"} → <line> element

    Args:
        lines: list of line/curve dicts
        opacity: per-element stroke-opacity (0.0–1.0). Only emitted if < 1.0.

    Returns:
        list of SVG element strings
    """
    opacity_attr = f' stroke-opacity="{opacity}"' if opacity < 1.0 else ''
    elements = []
    for ln in lines:
        if "path_d" in ln:
            elements.append(
                f'    <path d="{ln["path_d"]}" '
                f'stroke="{ln["color"]}" stroke-width="{ln["stroke_width"]}" '
                f'stroke-linecap="round" fill="none"{opacity_attr}/>'
            )
        else:
            elements.append(
                f'    <line x1="{ln["x1"]}" y1="{ln["y1"]}" '
                f'x2="{ln["x2"]}" y2="{ln["y2"]}" '
                f'stroke="{ln["color"]}" stroke-width="{ln["stroke_width"]}" '
                f'stroke-linecap="round"{opacity_attr}/>'
            )
    return elements
