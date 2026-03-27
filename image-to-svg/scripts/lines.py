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


def lines_to_svg_elements(lines):
    """Convert extracted lines to SVG <line> element strings."""
    elements = []
    for ln in lines:
        elements.append(
            f'    <line x1="{ln["x1"]}" y1="{ln["y1"]}" '
            f'x2="{ln["x2"]}" y2="{ln["y2"]}" '
            f'stroke="{ln["color"]}" stroke-width="{ln["stroke_width"]}" '
            f'stroke-linecap="round"/>'
        )
    return elements
