# svg-portrait-mode/
*Files: 2*

## Files

### SKILL.md
- SVG Portrait Mode `h1` :8
- Quick Start `h2` :14
- How It Works `h2` :55
- Agent Workflow `h2` :78
- Four Zones `h2` :88
- Per-Zone Style Transforms `h2` :112
- Parameters `h2` :135
- Performance `h2` :159
- Requirements `h2` :165
- Verification Protocol `h2` :184
- What Changed from v0.5.0 `h2` :206

### portrait_mode.py
> Imports: `sys, cv2, os, time`
- **build_zone_map** (f) `(h, w, focus_targets=None, focus_edges=None,
                   landmarks=None, face_bbox=None)` :175
- **zone_extract_contours** (f) `(label_img, centers, sorted_clusters, h, w,
                          bg_clusters, edge_img, zone_map, svg_width,
                          dark_lum=55, base_epsilon=0.002)` :293
- **assemble_svg** (f) `(shapes, svg_w, svg_h, bg_hex, style_transforms=None)` :496
- **portrait_mode** (f) `(image_path,
                  # Zone annotations from calling agent
                  focus_targets=None,
                  focus_edges=None,

                  # Pipeline settings
                  K=96,
                  smooth=None,
                  svg_width=800,

                  # MediaPipe options
                  use_landmarks=True,

                  # Per-zone simplification overrides
                  zone_simplification=None,

                  # Per-zone style transforms
                  style_transforms=None,

                  # Pipeline passthrough
                  **overrides)` :570

