# scripts/
*Files: 2*

## Files

### lines.py
> Imports: `cv2`
- **classify_input** (f) `(img_rgb)` :19
- **isolate_thin_features** (f) `(img_rgb, dark_threshold=None)` :64
- **merge_collinear** (f) `(segments, angle_tol=0.12, dist_tol=6.0, gap_tol=15.0)` :133
- **merge_segments_to_curves** (f) `(lines, merge_distance=10, merge_angle=30)` :226
- **measure_stroke_width** (f) `(mask, x1, y1, x2, y2, n_samples=5)` :399
- **sample_line_color** (f) `(img_rgb, mask, x1, y1, x2, y2, n_samples=10)` :431
- **extract_lines** (f) `(img_rgb, scale_x=1.0, scale_y=1.0, min_line_length=20,
                  stroke_width_cap=4.5, stroke_width_scale=0.65)` :452
- **suppress_line_regions** (f) `(img_rgb, thin_mask)` :506
- **lines_to_svg_elements** (f) `(lines, opacity=1.0)` :533

### pipeline.py
> Imports: `cv2, sys, collections, pathlib, flowing`
- **configure** (f) `(source_path, mode="painting", svg_width=1000, palette=None, bg_color=None, smooth=None, bg_clusters=None, pipeline="auto",
              stroke_width_cap=4.5, stroke_width_scale=0.65, stroke_opacity=1.0,
              stroke_merge=None, stroke_merge_distance=10, stroke_merge_angle=30,
              stroke_blur=0, stroke_dasharray=None, **overrides)` :75
- **image_to_svg** (f) `(source_path, mode="painting", svg_width=1000, palette=None,
                 bg_color=None, smooth=None, bg_clusters=None, pipeline="auto",
                 stroke_width_cap=4.5, stroke_width_scale=0.65, stroke_opacity=1.0,
                 stroke_merge=None, stroke_merge_distance=10, stroke_merge_angle=30,
                 stroke_blur=0, stroke_dasharray=None,
                 **overrides)` :728
- **image_to_svg_batch** (f) `(source_path, variants, svg_width=1000)` :801

