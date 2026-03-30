# Visual Pipeline

Three skills form a deep pipeline for image analysis and vectorization. seeing-images provides ground truth, image-to-svg converts raster to vector, and svg-portrait-mode adds foveated selective detail.

## Augmented Vision

Tools that give Claude precise visual information beyond native vision capabilities.

[[seeing-images/scripts/see.py#grid]] overlays a labeled grid for spatial reference. [[seeing-images/scripts/see.py#sample]] reads pixel colors at specified coordinates. [[seeing-images/scripts/see.py#histogram]] analyzes color distributions. [[seeing-images/scripts/see.py#edges]] runs Canny edge detection.

[[seeing-images/scripts/see.py#palette]] extracts dominant colors via k-means clustering. [[seeing-images/scripts/see.py#compare]] amplifies differences between two image regions. [[seeing-images/scripts/see.py#count_elements]] uses connected component analysis to count discrete objects in a region.

## Raster-to-Vector Pipeline

[[image-to-svg/scripts/pipeline.py#configure]] sets up the pipeline parameters. [[image-to-svg/scripts/pipeline.py#image_to_svg]] is the main entry point, orchestrating quantization, contour extraction, and SVG assembly. The pipeline uses the flowing skill ([[orchestration#DAG Workflow Runner]]) for parallel stage execution.

[[image-to-svg/scripts/pipeline.py#image_to_svg_batch]] generates multiple SVG variants from a single source image with different parameters — useful for A/B comparison of palette sizes, smoothing levels, or stroke treatments.

## Line Art Extraction

[[image-to-svg/scripts/lines.py#classify_input]] determines whether an image is photographic or line-art, routing to the appropriate pipeline. [[image-to-svg/scripts/lines.py#isolate_thin_features]] uses morphological operations to separate thin lines from filled regions.

[[image-to-svg/scripts/lines.py#extract_lines]] runs probabilistic Hough line detection. [[image-to-svg/scripts/lines.py#merge_collinear]] joins nearly-collinear segments, and [[image-to-svg/scripts/lines.py#merge_segments_to_curves]] groups segments into smooth polylines.

Per-line properties are measured by [[image-to-svg/scripts/lines.py#measure_stroke_width]] (cross-section sampling) and [[image-to-svg/scripts/lines.py#sample_line_color]] (color averaging along the stroke). [[image-to-svg/scripts/lines.py#lines_to_svg_elements]] converts the final line set to SVG path elements.

## Foveated Vectorization

[[svg-portrait-mode/portrait_mode.py#portrait_mode]] is the main entry point. It implements a 4-zone detail allocation inspired by phone portrait mode: foreground gets maximum detail, near-ground gets moderate, far-ground gets reduced, and background gets minimal.

[[svg-portrait-mode/portrait_mode.py#build_zone_map]] constructs the zone assignment from focus targets, edge maps, and optional MediaPipe face landmarks. [[svg-portrait-mode/portrait_mode.py#zone_extract_contours]] runs contour extraction per zone with zone-appropriate epsilon values — tighter for foreground, looser for background.

[[svg-portrait-mode/portrait_mode.py#assemble_svg]] combines all zone outputs into the final SVG with optional per-zone style transforms (opacity, blur, saturation shifts).
