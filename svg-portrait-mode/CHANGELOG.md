# Changelog

## 0.6.0

Changed from 0.5.0:

### Deleted
- Per-zone image-to-svg calls (4 pipeline runs)
- Per-zone smoothing (kuwahara, oilpaint per zone)
- ClipPath compositing
- Opaque crop + translate trick
- Multi-pass segmentation (21 IM transforms × MP segmenter)
- MediaPipe selfie segmenter dependency

### Kept
- Agent annotation API (focus_targets, focus_edges with bboxes)
- MediaPipe face landmarks for precise face ovals
- Four-zone concept (target / edge / periphery / background)

### Added
- Single-pass pipeline with unified palette
- Zone-aware contour simplification (epsilon + min_area per zone)
- Per-zone style transforms (desaturate, mute, warm/cool, opacity)
- Automatic periphery generation (dilated foreground buffer)
- Zone-tagged shapes in SVG output (<g> groups)
