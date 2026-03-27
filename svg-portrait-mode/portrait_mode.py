"""
Semantic Compositor: Claude interprets user intent and generates foveated SVG.

This module provides the execution layer. Claude provides:
1. Region definitions (from visual analysis)
2. Treatment mappings (from user intent)

The key insight: Claude IS the semantic segmentation layer.
"""

import numpy as np
import cv2
from PIL import Image
from sklearn.cluster import KMeans
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import json

@dataclass
class RegionSpec:
    """Specification for a region - Claude generates these"""
    name: str
    method: str  # "position", "color", "mask_file", "remainder", "bbox"
    params: Dict[str, Any]
    treatment: str  # flat, simplified, detailed, textured, outline
    treatment_overrides: Dict[str, Any] = field(default_factory=dict)
    z_order: int = 0

# Treatment presets with human-friendly names
TREATMENT_PRESETS = {
    # Background treatments
    "flat": {"K": 2, "blur": 21, "simplify": 3.0, "min_area": 100},
    "solid": {"K": 1, "blur": 25, "simplify": 5.0, "min_area": 200},
    
    # Midground treatments  
    "simplified": {"K": 5, "blur": 15, "simplify": 2.0, "min_area": 50},
    "stylized": {"K": 8, "blur": 11, "simplify": 1.5, "min_area": 40},
    
    # Foreground treatments
    "standard": {"K": 12, "blur": 9, "simplify": 1.0, "min_area": 30},
    "detailed": {"K": 24, "blur": 5, "simplify": 0.5, "min_area": 15},
    "textured": {"K": 32, "blur": 3, "simplify": 0.3, "min_area": 10},
    "hyperdetail": {"K": 48, "blur": 1, "simplify": 0.2, "min_area": 5},
    
    # Special treatments
    "outline": {"K": 1, "blur": 5, "simplify": 1.0, "min_area": 20, "mode": "outline"},
    "bold_outline": {"K": 1, "blur": 3, "simplify": 0.5, "min_area": 10, "mode": "outline", "stroke_width": 3},
}

class SemanticCompositor:
    def __init__(self, image_path: str, max_dim: int = 800):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load {image_path}")
        self.original = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        h, w = self.original.shape[:2]
        self.scale = max_dim / max(h, w) if max(h, w) > max_dim else 1.0
        self.image = cv2.resize(self.original, (int(w*self.scale), int(h*self.scale)))
        self.h, self.w = self.image.shape[:2]
        
    def create_mask(self, spec: RegionSpec) -> np.ndarray:
        """Create binary mask from region specification"""
        mask = np.zeros((self.h, self.w), dtype=np.uint8)
        
        if spec.method == "position":
            # Vertical slice: {"y": [0.0, 0.3]} or {"x": [0.2, 0.8]}
            y = spec.params.get("y", [0, 1])
            x = spec.params.get("x", [0, 1])
            y1, y2 = int(y[0] * self.h), int(y[1] * self.h)
            x1, x2 = int(x[0] * self.w), int(x[1] * self.w)
            mask[y1:y2, x1:x2] = 255
            
        elif spec.method == "color":
            # HSV color range: {"hsv_ranges": [([h1,s1,v1], [h2,s2,v2]), ...]}
            hsv = cv2.cvtColor(self.image, cv2.COLOR_RGB2HSV)
            for lower, upper in spec.params.get("hsv_ranges", []):
                mask |= cv2.inRange(hsv, np.array(lower), np.array(upper))
                
        elif spec.method == "saturation":
            # By saturation level: {"min": 0, "max": 30} for grays
            hsv = cv2.cvtColor(self.image, cv2.COLOR_RGB2HSV)
            s_min = spec.params.get("min", 0)
            s_max = spec.params.get("max", 255)
            mask = cv2.inRange(hsv[:,:,1], s_min, s_max)
            
        elif spec.method == "luminance":
            # By brightness: {"min": 200, "max": 255} for bright areas
            gray = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)
            l_min = spec.params.get("min", 0)
            l_max = spec.params.get("max", 255)
            mask = cv2.inRange(gray, l_min, l_max)
            
        elif spec.method == "bbox":
            # Bounding box: {"x1": 0.2, "y1": 0.3, "x2": 0.6, "y2": 0.8}
            x1 = int(spec.params.get("x1", 0) * self.w)
            y1 = int(spec.params.get("y1", 0) * self.h)
            x2 = int(spec.params.get("x2", 1) * self.w)
            y2 = int(spec.params.get("y2", 1) * self.h)
            mask[y1:y2, x1:x2] = 255
            
        elif spec.method == "mask_file":
            # Load from file
            m = np.array(Image.open(spec.params["path"]).convert("L"))
            mask = cv2.resize(m, (self.w, self.h), interpolation=cv2.INTER_NEAREST)
            if spec.params.get("invert", False):
                mask = 255 - mask
                
        # Apply morphological cleanup if requested
        if spec.params.get("cleanup", False):
            kernel = np.ones((5,5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
        # Expand/contract
        if "expand" in spec.params:
            kernel = np.ones((spec.params["expand"], spec.params["expand"]), np.uint8)
            mask = cv2.dilate(mask, kernel)
        if "contract" in spec.params:
            kernel = np.ones((spec.params["contract"], spec.params["contract"]), np.uint8)
            mask = cv2.erode(mask, kernel)
            
        return mask
    
    def compose(self, specs: List[RegionSpec], palette_overrides: Dict[str, List] = None) -> Tuple[str, Dict]:
        """
        Compose SVG from region specifications.
        
        Args:
            specs: List of RegionSpec (Claude generates these)
            palette_overrides: Optional forced palettes per region {"grass": [(85,125,60), ...]}
            
        Returns:
            (svg_string, stats_dict)
        """
        palette_overrides = palette_overrides or {}
        
        # Create all masks
        masks = {}
        for spec in specs:
            if spec.method == "remainder":
                continue  # Handle after others
            masks[spec.name] = self.create_mask(spec)
            
        # Handle remainder regions (everything not claimed)
        for spec in specs:
            if spec.method == "remainder":
                claimed = np.zeros((self.h, self.w), dtype=np.uint8)
                for name, m in masks.items():
                    claimed |= m
                # Optionally restrict remainder to a position
                if "y" in spec.params or "x" in spec.params:
                    pos_mask = self.create_mask(RegionSpec(
                        name="_pos", method="position", params=spec.params,
                        treatment="", z_order=0
                    ))
                    masks[spec.name] = ((claimed == 0) & (pos_mask > 0)).astype(np.uint8) * 255
                else:
                    masks[spec.name] = (claimed == 0).astype(np.uint8) * 255
        
        # Sort by z_order
        sorted_specs = sorted(specs, key=lambda s: s.z_order)
        
        # Process each region
        all_paths = []
        stats = {}
        
        for spec in sorted_specs:
            mask = masks.get(spec.name)
            if mask is None or np.sum(mask) == 0:
                stats[spec.name] = 0
                continue
                
            # Get treatment params
            base_treatment = TREATMENT_PRESETS.get(spec.treatment, TREATMENT_PRESETS["standard"])
            treatment = {**base_treatment, **spec.treatment_overrides}
            
            # Check for forced palette
            palette = palette_overrides.get(spec.name)
            
            # Quantize
            if palette:
                quantized = self._apply_palette(mask, palette, treatment["blur"])
            else:
                quantized = self._quantize(mask, treatment["K"], treatment["blur"])
            
            # Extract paths
            paths = self._extract_paths(quantized, mask, treatment)
            all_paths.extend(paths)
            stats[spec.name] = len(paths)
        
        # Build SVG
        svg = self._build_svg(all_paths)
        
        return svg, stats
    
    def _apply_palette(self, mask: np.ndarray, palette: List, blur: int) -> np.ndarray:
        """Apply forced color palette to region"""
        palette = np.array(palette, dtype=np.uint8)
        blurred = cv2.bilateralFilter(self.image, blur, 75, 75)
        pixels = blurred[mask > 0].astype(float)
        
        if len(pixels) == 0:
            return np.zeros_like(self.image)
            
        distances = np.zeros((len(pixels), len(palette)))
        for i, color in enumerate(palette):
            distances[:, i] = np.sqrt(np.sum((pixels - color) ** 2, axis=1))
        labels = np.argmin(distances, axis=1)
        
        result = np.zeros_like(self.image)
        result[mask > 0] = palette[labels]
        return result
    
    def _quantize(self, mask: np.ndarray, K: int, blur: int) -> np.ndarray:
        """K-means quantization"""
        blurred = cv2.bilateralFilter(self.image, blur, 75, 75)
        pixels = blurred[mask > 0]
        
        if len(pixels) == 0:
            return np.zeros_like(self.image)
            
        actual_K = min(K, max(1, len(np.unique(pixels, axis=0))))
        km = KMeans(n_clusters=actual_K, n_init=3, max_iter=100, random_state=42)
        labels = km.fit_predict(pixels)
        centers = km.cluster_centers_.astype(np.uint8)
        
        result = np.zeros_like(self.image)
        result[mask > 0] = centers[labels]
        return result
    
    def _extract_paths(self, quantized: np.ndarray, mask: np.ndarray, treatment: Dict) -> List[str]:
        """Extract SVG paths"""
        paths = []
        mode = treatment.get("mode", "fill")
        simplify = treatment.get("simplify", 1.0)
        min_area = treatment.get("min_area", 30)
        stroke_width = treatment.get("stroke_width", 2)
        
        masked = quantized.copy()
        masked[mask == 0] = 0
        
        unique_colors = np.unique(masked[mask > 0].reshape(-1, 3), axis=0)
        
        for color in unique_colors:
            if np.all(color == 0):
                continue
                
            color_mask = np.all(masked == color, axis=2).astype(np.uint8) * 255
            contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            
            for contour in contours:
                if cv2.contourArea(contour) < min_area:
                    continue
                    
                approx = cv2.approxPolyDP(contour, simplify, True)
                if len(approx) < 3:
                    continue
                    
                points = approx.squeeze()
                if len(points.shape) == 1:
                    continue
                    
                d = f"M{points[0][0]},{points[0][1]}"
                for p in points[1:]:
                    d += f"L{p[0]},{p[1]}"
                d += "Z"
                
                if mode == "outline":
                    paths.append(f'<path d="{d}" fill="none" stroke="{hex_color}" stroke-width="{stroke_width}"/>')
                elif mode == "both":
                    paths.append(f'<path d="{d}" fill="{hex_color}" stroke="#000" stroke-width="1"/>')
                else:
                    paths.append(f'<path d="{d}" fill="{hex_color}"/>')
                    
        return paths
    
    def _build_svg(self, paths: List[str]) -> str:
        """Assemble final SVG"""
        # Background from edge pixels
        edge_pixels = np.vstack([
            self.image[0, :], self.image[-1, :],
            self.image[:, 0], self.image[:, -1]
        ])
        colors, counts = np.unique(edge_pixels, axis=0, return_counts=True)
        bg = colors[np.argmax(counts)]
        bg_hex = f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}"
        
        return f'''<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}">
<rect width="{self.w}" height="{self.h}" fill="{bg_hex}"/>
{chr(10).join(paths)}
</svg>'''


def compose_from_json(image_path: str, config: Dict) -> Tuple[str, Dict]:
    """
    Main entry point - compose from a JSON config.
    
    Config format:
    {
        "regions": [
            {"name": "sky", "method": "position", "params": {"y": [0, 0.2]}, "treatment": "flat", "z_order": 0},
            {"name": "subject", "method": "bbox", "params": {"x1": 0.3, "y1": 0.4, "x2": 0.7, "y2": 0.9}, "treatment": "detailed", "z_order": 10},
            {"name": "background", "method": "remainder", "params": {}, "treatment": "simplified", "z_order": 5}
        ],
        "palettes": {
            "sky": [[135, 180, 220], [100, 150, 200]]
        }
    }
    """
    compositor = SemanticCompositor(image_path)
    
    specs = []
    for r in config.get("regions", []):
        specs.append(RegionSpec(
            name=r["name"],
            method=r["method"],
            params=r.get("params", {}),
            treatment=r.get("treatment", "standard"),
            treatment_overrides=r.get("treatment_overrides", {}),
            z_order=r.get("z_order", 0)
        ))
    
    return compositor.compose(specs, config.get("palettes", {}))


if __name__ == "__main__":
    # Test with dog image
    config = {
        "regions": [
            {"name": "grass", "method": "position", "params": {"y": [0, 0.28]}, 
             "treatment": "flat", "z_order": 0},
            {"name": "dog", "method": "mask_file", "params": {"path": "seg_mask.png"},
             "treatment": "detailed", "z_order": 10},
            {"name": "patio", "method": "remainder", "params": {},
             "treatment": "simplified", "z_order": 5}
        ],
        "palettes": {
            "grass": [[85, 125, 60], [105, 145, 75], [65, 100, 45]]
        }
    }
    
    svg, stats = compose_from_json("IMG_5584.jpeg", config)
    
    with open("semantic_dog.svg", "w") as f:
        f.write(svg)
    
    print(f"Stats: {stats}")
    print(f"Total: {sum(stats.values())} paths")
    print(f"Size: {len(svg)/1024:.1f}KB")


# === MEDIAPIPE INTEGRATION ===

def get_mediapipe_masks(image_path: str, output_dir: str = "/tmp") -> Dict[str, str]:
    """
    Run MediaPipe segmentation and return paths to generated mask files.
    
    Returns dict with keys: 'person', 'background', 'face' (if detected)
    """
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    import os
    
    img = cv2.imread(image_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    
    masks = {}
    
    # Selfie segmentation for person/background
    try:
        selfie_seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path='/home/claude/selfie_segmenter.tflite'),
                output_category_mask=True))
        result = selfie_seg.segment(mp_img)
        selfie_mask = result.category_mask.numpy_view().squeeze()
        selfie_seg.close()
        
        # Determine which value is person (usually 255, but check)
        if np.sum(selfie_mask == 255) < selfie_mask.size * 0.5:
            person_mask = (selfie_mask == 255).astype(np.uint8) * 255
        else:
            person_mask = (selfie_mask == 0).astype(np.uint8) * 255
        
        person_path = os.path.join(output_dir, "mask_person.png")
        bg_path = os.path.join(output_dir, "mask_background.png")
        
        Image.fromarray(person_mask).save(person_path)
        Image.fromarray(255 - person_mask).save(bg_path)
        
        masks['person'] = person_path
        masks['background'] = bg_path
    except Exception as e:
        print(f"Selfie segmentation failed: {e}")
    
    # Face detection
    try:
        face_detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path='/home/claude/blaze_face_short_range.tflite'),
                min_detection_confidence=0.3))
        result = face_detector.detect(mp_img)
        face_detector.close()
        
        if result.detections:
            face_mask = np.zeros((h, w), dtype=np.uint8)
            for det in result.detections:
                bbox = det.bounding_box
                pad = int(bbox.width * 0.2)
                x1 = max(0, bbox.origin_x - pad)
                y1 = max(0, bbox.origin_y - pad)
                x2 = min(w, bbox.origin_x + bbox.width + pad)
                y2 = min(h, bbox.origin_y + bbox.height + pad)
                face_mask[y1:y2, x1:x2] = 255
            
            face_path = os.path.join(output_dir, "mask_face.png")
            Image.fromarray(face_mask).save(face_path)
            masks['face'] = face_path
    except Exception as e:
        print(f"Face detection failed: {e}")
    
    return masks


def portrait_mode_auto(image_path: str, 
                       subject_treatment: str = "detailed",
                       face_treatment: str = "textured", 
                       background_treatment: str = "flat") -> Tuple[str, Dict]:
    """
    Automatic portrait mode using MediaPipe segmentation.
    
    Args:
        image_path: Path to image
        subject_treatment: Treatment for person body
        face_treatment: Treatment for face (if detected)
        background_treatment: Treatment for background
        
    Returns:
        (svg_string, stats_dict)
    """
    masks = get_mediapipe_masks(image_path)
    
    regions = []
    
    # Background first (z=0)
    if 'background' in masks:
        regions.append({
            "name": "background",
            "method": "mask_file",
            "params": {"path": masks['background']},
            "treatment": background_treatment,
            "z_order": 0
        })
    
    # Person body (z=5)
    if 'person' in masks:
        regions.append({
            "name": "person",
            "method": "mask_file", 
            "params": {"path": masks['person']},
            "treatment": subject_treatment,
            "z_order": 5
        })
    
    # Face highest detail (z=10)
    if 'face' in masks:
        regions.append({
            "name": "face",
            "method": "mask_file",
            "params": {"path": masks['face']},
            "treatment": face_treatment,
            "z_order": 10
        })
    
    config = {"regions": regions}
    return compose_from_json(image_path, config)
