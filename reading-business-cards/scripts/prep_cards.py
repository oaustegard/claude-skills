#!/usr/bin/env python3
"""
prep_cards.py — turn sheet photos of many business cards into legible,
de-glared per-card crops plus numbered montages a vision model can read.

Why this exists: Claude downscales any input image to ~1568px on the long
edge before the model sees it. A photo of 60 cards leaves each card at
~200px wide — too mushy for Sonnet, so you're forced onto Opus. Cropping
each card and re-tiling a handful per montage gives every card 350px+ of
real resolution, which is usually what flips Sonnet from failing to working.
De-glare (illumination flattening + CLAHE + optional highlight inpaint) is
the second layer on top.

Usage:
    python3 prep_cards.py INPUT --out WORKDIR [options]

    INPUT        a single image, or a directory of sheet images
    --out        output directory (default: ./cards_work)
    --rows R --cols C   slice each sheet on a fixed RxC grid (most reliable
                        when the cards are laid out regularly, e.g. a binder
                        page). Omit to auto-detect cards by contour.
    --per-montage N     cards per montage tile (default 6; lower = sharper)
    --cell PX           target cell width in px for montage (default 420)
    --binarize          add a clean black-on-white pass (text-only cards)
    --no-inpaint        skip specular-highlight inpainting
    --min-area-frac F   contour mode: min card area as frac of sheet (default 0.003)
    --max-area-frac F   contour mode: max card area as frac of sheet (default 0.25)

Outputs under WORKDIR:
    cards/      individual de-glared crops, named <sheet>__<NNN>.png
    montages/   numbered grids the reader views, montage_000.png ...
    manifest.json   maps every global card index -> sheet, crop path, montage
"""
import argparse, json, os, sys, glob, math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CARD_ASPECT_RANGE = (1.3, 2.4)   # US card ~1.75, EU ~1.6; allow rotation slack

# ---------- card detection ----------

def detect_cards_contour(bgr, min_area_frac, max_area_frac):
    """Find card-shaped rectangles by contour. Returns list of upright crops."""
    h, w = bgr.shape[:2]
    sheet_area = h * w
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # flatten lighting first so a single global threshold can separate cards
    # (bright, contiguous) from the gaps/background between them
    bg = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), max(h, w) / 12.0)
    flat = np.clip(gray.astype(np.float32) / (bg + 1e-3) * float(bg.mean()), 0, 255).astype(np.uint8)
    flat = cv2.GaussianBlur(flat, (5, 5), 0)
    _, th = cv2.threshold(flat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # close text holes inside each card into one solid blob, then open to
    # break thin bridges between neighbours
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area_frac * sheet_area or area > max_area_frac * sheet_area:
            continue
        rect = cv2.minAreaRect(c)            # ((cx,cy),(w,h),angle)
        (cx, cy), (rw, rh), ang = rect
        if rw < 1 or rh < 1:
            continue
        long_, short_ = max(rw, rh), min(rw, rh)
        aspect = long_ / short_
        if not (CARD_ASPECT_RANGE[0] <= aspect <= CARD_ASPECT_RANGE[1]):
            continue
        boxes.append(rect)
    # sort top-to-bottom, then left-to-right (reading order)
    boxes.sort(key=lambda r: (round(r[0][1] / (0.5 * min(r[1]) + 1)), r[0][0]))
    return [warp_upright(bgr, b) for b in boxes]

def warp_upright(bgr, rect):
    box = cv2.boxPoints(rect).astype("float32")
    (rw, rh) = rect[1]
    W, H = int(max(rw, rh)), int(min(rw, rh))   # force landscape
    # order box points to match a landscape destination
    s = box.sum(1); d = np.diff(box, axis=1).ravel()
    tl = box[np.argmin(s)]; br = box[np.argmax(s)]
    tr = box[np.argmin(d)]; bl = box[np.argmax(d)]
    src = np.array([tl, tr, br, bl], dtype="float32")
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(bgr, M, (W, H))

def slice_grid(bgr, rows, cols):
    h, w = bgr.shape[:2]
    ch, cw = h // rows, w // cols
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append(bgr[r*ch:(r+1)*ch, c*cw:(c+1)*cw].copy())
    return out

def slice_tiles(bgr, rows, cols, overlap):
    """Cut the sheet into rows x cols overlapping tiles, ignoring card
    boundaries. Robust for scattered, rotated, or glare-covered cards where
    per-card detection fails: each tile holds a few cards at near-full
    resolution, and the overlap means a card split by one tile edge is whole
    in its neighbour. Returns list of (tile_bgr, (x0, y0))."""
    h, w = bgr.shape[:2]
    th, tw = h / rows, w / cols
    ox, oy = int(tw * overlap), int(th * overlap)
    tiles = []
    for r in range(rows):
        for c in range(cols):
            x0 = max(0, int(c*tw) - ox); x1 = min(w, int((c+1)*tw) + ox)
            y0 = max(0, int(r*th) - oy); y1 = min(h, int((r+1)*th) + oy)
            tiles.append((bgr[y0:y1, x0:x1].copy(), (x0, y0)))
    return tiles

# ---------- de-glare ----------

def flatten_illumination(bgr):
    """Divide out smooth lighting/glare gradients via a large-kernel background
    estimate. Operates on the LAB L channel so color is preserved."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0].astype(np.float32)
    k = max(31, (min(bgr.shape[:2]) // 3) | 1)   # odd, ~1/3 of the short side
    bg = cv2.GaussianBlur(L, (k, k), 0)
    norm = (L / (bg + 1e-3)) * float(np.mean(bg))
    lab[:, :, 0] = np.clip(norm, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def inpaint_specular(bgr):
    """Fill only small, fully-blown specular spots (e.g. a lamination glint)
    from surrounding pixels. Restricted to tiny compact components because on
    a flat card most of the paper is bright + low-saturation; masking all of
    it and inpainting would smear text. Opt-in via --inpaint."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    mask = ((v >= 252) & (s < 25)).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    max_spot = 0.01 * bgr.shape[0] * bgr.shape[1]   # ignore anything >1% of card
    keep = np.zeros_like(mask)
    for k in range(1, n):
        if stats[k, cv2.CC_STAT_AREA] <= max_spot:
            keep[lbl == k] = 255
    if keep.sum() == 0:
        return bgr
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.inpaint(bgr, keep, 3, cv2.INPAINT_TELEA)

def apply_clahe(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def binarize(bgr):
    from skimage.filters import threshold_sauvola
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    win = max(15, (min(gray.shape) // 8) | 1)
    t = threshold_sauvola(gray, window_size=win, k=0.2)
    bw = (gray > t).astype(np.uint8) * 255
    return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

def deglare(bgr, do_inpaint=True, do_binarize=False):
    out = flatten_illumination(bgr)
    if do_inpaint:
        out = inpaint_specular(out)
    out = apply_clahe(out)
    if do_binarize:
        out = binarize(out)
    return out

# ---------- montage ----------

def build_montage(crop_paths, indices, cell_w, out_path):
    """Tile crops into one image, each cell labelled with its global index so
    the reader can map a cell back to a manifest record."""
    n = len(crop_paths)
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    cells = []
    cell_h = 0
    for p in crop_paths:
        im = Image.open(p).convert("RGB")
        scale = cell_w / im.width
        im = im.resize((cell_w, max(1, int(im.height * scale))))
        cells.append(im)
        cell_h = max(cell_h, im.height)
    pad, label_h = 12, 34
    cw, chh = cell_w + 2*pad, cell_h + label_h + pad
    sheet = Image.new("RGB", (cols*cw, rows*chh), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    for i, (im, idx) in enumerate(zip(cells, indices)):
        r, c = divmod(i, cols)
        x, y = c*cw + pad, r*chh + label_h
        draw.text((x, r*chh + 4), f"#{idx}", fill="red", font=font)
        sheet.paste(im, (x, y))
    sheet.save(out_path)

# ---------- driver ----------

def auto_grid(h, w, overlap, target=1500):
    """Derive rows x cols from the image's own dimensions so each tile's long
    edge (including overlap) stays at or below `target` px — just under the
    model's ~1568 downscale cap, so tiles keep full resolution and cards stay
    legible. No human tuning needed; adapts per image and orientation."""
    factor = 1.0 + 2.0 * overlap
    rows = max(1, math.ceil(h * factor / target))
    cols = max(1, math.ceil(w * factor / target))
    return rows, cols


def gather_inputs(path):
    if os.path.isdir(path):
        files = []
        for ext in ("*.jpg","*.jpeg","*.png","*.webp","*.tif","*.tiff","*.bmp",
                    "*.JPG","*.JPEG","*.PNG","*.HEIC","*.heic"):
            files += glob.glob(os.path.join(path, ext))
        return sorted(files)
    return [path]

def main():
    ap = argparse.ArgumentParser(description="Segment + de-glare business-card sheets.")
    ap.add_argument("input")
    ap.add_argument("--out", default="cards_work")
    ap.add_argument("--tiles", default="",
                    help="ROWSxCOLS override, e.g. 5x4. Omit to auto-derive the "
                         "grid from each image's size (the default).")
    ap.add_argument("--target-px", type=int, default=1500,
                    help="max tile long edge for auto-grid (default 1500, just "
                         "under the model's downscale cap)")
    ap.add_argument("--overlap", type=float, default=0.12,
                    help="tile overlap fraction (default 0.12)")
    ap.add_argument("--detect", action="store_true",
                    help="opt in to per-card contour detection instead of tiling "
                         "(only for cleanly separated, non-rotated cards)")
    ap.add_argument("--rows", type=int, default=0)
    ap.add_argument("--cols", type=int, default=0)
    ap.add_argument("--per-montage", type=int, default=6)
    ap.add_argument("--cell", type=int, default=420)
    ap.add_argument("--binarize", action="store_true")
    ap.add_argument("--no-deglare", action="store_true",
                    help="skip the flatten+CLAHE de-glare pass")
    ap.add_argument("--inpaint", action="store_true",
                    help="fill small fully-blown specular spots (off by default; "
                         "can smear text if cards are glossy/uniform)")
    ap.add_argument("--min-area-frac", type=float, default=0.003)
    ap.add_argument("--max-area-frac", type=float, default=0.25)
    args = ap.parse_args()

    inputs = gather_inputs(args.input)
    if not inputs:
        sys.exit(f"No images found at {args.input}")

    # ---- TILE MODE (DEFAULT): tiles are the read units. Grid is auto-derived
    # per image unless --tiles overrides. Falls through to grid-slice/contour
    # only when --rows/--cols or --detect are explicitly requested. ----
    explicit_grid = bool(args.rows and args.cols)
    tile_mode = bool(args.tiles) or (not explicit_grid and not args.detect)
    if tile_mode:
        tiles_dir = os.path.join(args.out, "tiles")
        os.makedirs(tiles_dir, exist_ok=True)
        manifest = []
        for sheet_path in inputs:
            bgr = cv2.imread(sheet_path)
            if bgr is None:
                print(f"  ! could not read {sheet_path}, skipping", file=sys.stderr)
                continue
            sheet_name = os.path.splitext(os.path.basename(sheet_path))[0]
            h, w = bgr.shape[:2]
            if args.tiles:
                try:
                    tr, tc = (int(x) for x in args.tiles.lower().split("x"))
                except Exception:
                    sys.exit("--tiles must look like ROWSxCOLS, e.g. 5x4")
                how = f"{tr}x{tc} override"
            else:
                tr, tc = auto_grid(h, w, args.overlap, args.target_px)
                how = f"auto {tr}x{tc} from {w}x{h}"
            tiles = slice_tiles(bgr, tr, tc, args.overlap)
            for k, (tile, (x0, y0)) in enumerate(tiles):
                if not args.no_deglare:
                    tile = deglare(tile, do_inpaint=args.inpaint, do_binarize=args.binarize)
                r, c = divmod(k, tc)
                fname = f"{sheet_name}__r{r}_c{c}.png"
                fpath = os.path.join(tiles_dir, fname)
                cv2.imwrite(fpath, tile)
                manifest.append({"sheet": sheet_name, "row": r, "col": c,
                                 "offset_xy": [x0, y0], "tile": fpath})
            print(f"{sheet_name}: {len(tiles)} tiles ({how}, overlap {args.overlap})")
        with open(os.path.join(args.out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nTotal tiles: {len(manifest)} -> {tiles_dir}")
        print(f"Manifest: {os.path.join(args.out, 'manifest.json')}")
        return

    cards_dir = os.path.join(args.out, "cards")
    mont_dir = os.path.join(args.out, "montages")
    os.makedirs(cards_dir, exist_ok=True)
    os.makedirs(mont_dir, exist_ok=True)

    manifest, gidx = [], 0
    for sheet_path in inputs:
        bgr = cv2.imread(sheet_path)
        if bgr is None:
            print(f"  ! could not read {sheet_path}, skipping", file=sys.stderr)
            continue
        sheet_name = os.path.splitext(os.path.basename(sheet_path))[0]
        if args.rows and args.cols:
            crops = slice_grid(bgr, args.rows, args.cols)
            mode = f"grid {args.rows}x{args.cols}"
        else:
            crops = detect_cards_contour(bgr, args.min_area_frac, args.max_area_frac)
            mode = "contour-detect"
        print(f"{sheet_name}: {len(crops)} cards ({mode})")
        for j, crop in enumerate(crops):
            clean = deglare(crop, do_inpaint=args.inpaint, do_binarize=args.binarize)
            fname = f"{sheet_name}__{gidx:03d}.png"
            fpath = os.path.join(cards_dir, fname)
            cv2.imwrite(fpath, clean)
            manifest.append({"index": gidx, "sheet": sheet_name,
                             "position_in_sheet": j, "crop": fpath, "montage": None})
            gidx += 1

    # montages over all crops, in index order
    per = max(1, args.per_montage)
    for m, start in enumerate(range(0, len(manifest), per)):
        chunk = manifest[start:start+per]
        out_path = os.path.join(mont_dir, f"montage_{m:03d}.png")
        build_montage([c["crop"] for c in chunk], [c["index"] for c in chunk],
                      args.cell, out_path)
        for c in chunk:
            c["montage"] = out_path

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nTotal cards: {len(manifest)} | montages: {math.ceil(len(manifest)/per)}")
    print(f"Manifest: {os.path.join(args.out, 'manifest.json')}")

if __name__ == "__main__":
    main()
