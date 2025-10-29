"""
Shape Merger - Intelligently merge overlapping shapes that form composite elements

This module detects and merges shapes that are rendered together in PDFs to create
visual effects like rings, donuts, or other composite shapes.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ShapeMerger:
    """
    Detects and merges overlapping shapes to form composite elements.
    
    Key patterns detected:
    1. Ring/Donut pattern: Two concentric squares/circles that form a ring
       - Outer shape: filled with color
       - Inner shape: stroke only (creates hollow center)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Shape Merger.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        # Tolerance for considering shapes as concentric (in points)
        self.concentric_tolerance = self.config.get('concentric_tolerance', 20.0)
    
    def merge_shapes(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze shapes and merge those that form composite elements.
        
        Args:
            shapes: List of shape elements from PDF
            
        Returns:
            List of shapes with merges applied
        """
        if len(shapes) < 1:
            return shapes
        
        # Step 1: Detect paired ring patterns (outer fill + inner stroke)
        merged_shapes, merged_indices = self._detect_and_merge_rings(shapes)
        
        # Step 2: Detect standalone stroke-only rings
        standalone_rings, standalone_indices = self._detect_standalone_rings(shapes, merged_indices)
        merged_shapes.extend(standalone_rings)
        merged_indices.update(standalone_indices)
        
        # Step 3: Filter out arc segments that overlap with rings
        # These are partial arcs that shouldn't be rendered as separate shapes
        filtered_indices = self._filter_arc_segments_near_rings(shapes, merged_indices, merged_shapes)
        merged_indices.update(filtered_indices)
        
        # Keep non-merged shapes
        result = []
        for i, shape in enumerate(shapes):
            if i not in merged_indices:
                result.append(shape)
        
        # Add merged/converted shapes
        result.extend(merged_shapes)
        
        if merged_shapes:
            logger.info(f"Merged/converted {len(merged_indices)} shapes into {len(merged_shapes)} composite shapes")
        
        return result
    
    def _detect_and_merge_rings(self, shapes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], set]:
        """
        Detect and merge ring/donut patterns.
        
        A ring pattern consists of:
        - An outer shape (filled, larger)
        - An inner shape (stroke only, smaller, concentric)
        
        Args:
            shapes: List of shape elements
            
        Returns:
            Tuple of (merged shapes list, set of merged shape indices)
        """
        merged_shapes = []
        merged_indices = set()
        
        # Find potential ring pairs
        for i in range(len(shapes)):
            if i in merged_indices:
                continue
            
            shape1 = shapes[i]
            
            # Look for a concentric shape
            for j in range(len(shapes)):
                if i == j or j in merged_indices:
                    continue
                
                shape2 = shapes[j]
                
                # Check if these form a ring pattern
                ring = self._try_merge_ring(shape1, shape2)
                if ring:
                    merged_shapes.append(ring)
                    merged_indices.add(i)
                    merged_indices.add(j)
                    logger.debug(f"Merged ring: shapes #{i} and #{j}")
                    break
        
        return merged_shapes, merged_indices
    
    def _detect_standalone_rings(self, shapes: List[Dict[str, Any]], 
                                 already_merged: set) -> Tuple[List[Dict[str, Any]], set]:
        """
        Detect standalone stroke-only rings (circles with thick stroke, no fill or black fill).
        
        These are circles that represent ring shapes on their own, without needing
        a separate outer fill circle.
        
        Args:
            shapes: List of shape elements
            already_merged: Indices of shapes already processed
            
        Returns:
            Tuple of (ring shapes list, set of processed shape indices)
        """
        rings = []
        processed_indices = set()
        
        for i, shape in enumerate(shapes):
            if i in already_merged:
                continue
            
            # Check if this is a circular shape (aspect ratio near 1.0)
            # Use STRICTER aspect ratio to avoid arc segments
            aspect = self._get_aspect_ratio(shape)
            if not (0.85 <= aspect <= 1.15):
                continue
            
            # Must have a visible stroke
            stroke_color = shape.get('stroke_color')
            stroke_width = shape.get('stroke_width', 0)
            
            if not stroke_color or stroke_color in ['#000000', 'None'] or stroke_width <= 0:
                continue
            
            # Must have minimal/black fill (indicating hollow center)
            fill_color = shape.get('fill_color')
            
            # Stroke-only rings typically have either:
            # 1. No fill color
            # 2. Black fill (#000000)
            # 3. Very low opacity fill
            is_hollow = (
                not fill_color or 
                fill_color in ['#000000', 'None'] or
                shape.get('fill_opacity', 1.0) <= 0.1
            )
            
            if not is_hollow:
                continue
            
            # This is a standalone stroke-only ring!
            # Convert to proper ring representation
            ring = {
                'type': 'shape',
                'shape_type': 'oval',  # Render as circle
                'x': shape['x'],
                'y': shape['y'],
                'x2': shape['x2'],
                'y2': shape['y2'],
                'width': shape['width'],
                'height': shape['height'],
                'fill_color': '#FFFFFF',  # White fill for center
                'fill_opacity': 1.0,  # Solid white
                'stroke_color': stroke_color,  # Ring color
                'stroke_width': stroke_width,  # Ring thickness
                'is_ring': True,  # Mark as ring
                'ring_color': stroke_color,  # Store original color
                'ring_type': 'standalone',  # Mark as standalone ring
                'original_shape': shape  # Keep original for debugging
            }
            
            rings.append(ring)
            processed_indices.add(i)
            
            logger.debug(f"Detected standalone ring at ({shape['x']:.1f}, {shape['y']:.1f}), "
                        f"stroke width {stroke_width}pt, color {stroke_color}")
        
        return rings, processed_indices
    
    def _try_merge_ring(self, shape1: Dict[str, Any], 
                        shape2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Try to merge two shapes as a ring pattern.
        
        Detection criteria:
        1. Both shapes are roughly square/circular (aspect ratio ~ 1.0)
        2. Shapes are concentric (centers aligned)
        3. One shape is larger (outer ring)
        4. Inner shape has stroke, outer shape has fill
        5. Same color (or complementary colors)
        6. STRICT: Outer shape must be close to square to avoid arc segments
        
        Args:
            shape1: First shape
            shape2: Second shape
            
        Returns:
            Merged ring shape if pattern detected, None otherwise
        """
        # Check if both are roughly square/circular
        # Use STRICTER aspect ratio check to avoid arc segments
        aspect1 = self._get_aspect_ratio(shape1)
        aspect2 = self._get_aspect_ratio(shape2)
        
        # CRITICAL: Tighten aspect ratio to 0.85-1.15 to exclude arc segments
        # Arc segments often have aspect ratios like 0.63 (94/150) or 0.5 (75/150)
        if not (0.85 <= aspect1 <= 1.15 and 0.85 <= aspect2 <= 1.15):
            return None
        
        # Check if centers are aligned (concentric)
        center1 = self._get_center(shape1)
        center2 = self._get_center(shape2)
        
        distance = ((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)**0.5
        
        if distance > self.concentric_tolerance:
            return None
        
        # Identify outer and inner shapes
        size1 = max(shape1['width'], shape1['height'])
        size2 = max(shape2['width'], shape2['height'])
        
        if size1 > size2:
            outer_shape = shape1
            inner_shape = shape2
        else:
            outer_shape = shape2
            inner_shape = shape1
        
        # Check ring pattern:
        # - Outer shape should have fill
        # - Inner shape should have stroke (and possibly black/transparent fill)
        outer_has_fill = (outer_shape.get('fill_color') and 
                         outer_shape.get('fill_color') not in ['#000000', 'None'])
        
        inner_has_stroke = (inner_shape.get('stroke_color') and 
                           inner_shape.get('stroke_color') not in ['#000000', 'None'] and
                           inner_shape.get('stroke_width', 0) > 0)
        
        if not (outer_has_fill and inner_has_stroke):
            return None
        
        # Check if colors match or are complementary
        outer_color = outer_shape.get('fill_color', '').lower()
        inner_color = inner_shape.get('stroke_color', '').lower()
        
        # Colors should match for a ring
        if outer_color != inner_color:
            return None
        
        # Merge into a ring shape
        # PowerPoint doesn't have a native ring shape, so we need to render it as:
        # - A circle with white fill (to cover the background)
        # - A thick stroke in the ring color (to create the ring effect)
        # 
        # Calculate the ring thickness from the inner shape's stroke width
        ring_thickness = inner_shape.get('stroke_width', 0)
        ring_color = inner_shape.get('stroke_color', outer_shape.get('fill_color'))
        
        merged = {
            'type': 'shape',
            'shape_type': 'oval',  # Mark as circular/oval
            'x': outer_shape['x'],
            'y': outer_shape['y'],
            'x2': outer_shape['x2'],
            'y2': outer_shape['y2'],
            'width': outer_shape['width'],
            'height': outer_shape['height'],
            'fill_color': '#FFFFFF',  # White fill for the center
            'fill_opacity': 1.0,  # Solid white fill
            'stroke_color': ring_color,  # Ring color from inner stroke
            'stroke_width': ring_thickness,  # Ring thickness
            'is_ring': True,  # Mark as a composite ring
            'ring_color': outer_shape.get('fill_color'),  # Original ring color for reference
            'original_shapes': [outer_shape, inner_shape]  # Keep originals for debugging
        }
        
        logger.debug(f"Created ring shape at ({merged['x']:.1f}, {merged['y']:.1f}), "
                    f"size {merged['width']:.1f}x{merged['height']:.1f}, "
                    f"ring thickness {ring_thickness}pt, color {ring_color}")
        
        return merged
    
    def _filter_arc_segments_near_rings(self, shapes: List[Dict[str, Any]], 
                                         already_merged: set,
                                         ring_shapes: List[Dict[str, Any]]) -> set:
        """
        Filter out arc segments that overlap with ring shapes.
        
        Arc segments are partial arcs (not full circles) that may be part of
        percentage rings or other composite shapes. When they overlap with
        detected ring shapes, they should be filtered out to avoid duplication.
        
        Detection criteria:
        - Shape is not already merged
        - Shape has fill but aspect ratio is not circular (< 0.85 or > 1.15)
        - Shape overlaps significantly with a ring shape
        
        Args:
            shapes: List of shape elements
            already_merged: Indices of shapes already processed
            ring_shapes: List of detected ring shapes
            
        Returns:
            Set of indices of arc segments to filter out
        """
        filtered_indices = set()
        
        if not ring_shapes:
            return filtered_indices
        
        for i, shape in enumerate(shapes):
            if i in already_merged:
                continue
            
            # Check if shape has fill color (arc segments are filled)
            fill_color = shape.get('fill_color')
            if not fill_color or fill_color in ['#000000', 'None']:
                continue
            
            # Check if shape is NOT circular (arc segment)
            aspect = self._get_aspect_ratio(shape)
            if 0.85 <= aspect <= 1.15:
                # This is close to circular, not an arc segment
                continue
            
            # Check if this arc segment overlaps with any ring
            for ring in ring_shapes:
                if self._do_shapes_overlap(shape, ring):
                    # This arc segment overlaps with a ring, filter it out
                    filtered_indices.add(i)
                    logger.debug(f"Filtered out arc segment at ({shape['x']:.1f}, {shape['y']:.1f}), "
                               f"aspect ratio {aspect:.2f}, overlaps with ring at "
                               f"({ring['x']:.1f}, {ring['y']:.1f})")
                    break
        
        return filtered_indices
    
    def _do_shapes_overlap(self, shape1: Dict[str, Any], shape2: Dict[str, Any]) -> bool:
        """
        Check if two shapes overlap significantly.
        
        Args:
            shape1: First shape
            shape2: Second shape
            
        Returns:
            True if shapes overlap by at least 30%
        """
        # Calculate overlap rectangle
        x_overlap_start = max(shape1['x'], shape2['x'])
        y_overlap_start = max(shape1['y'], shape2['y'])
        x_overlap_end = min(shape1['x2'], shape2['x2'])
        y_overlap_end = min(shape1['y2'], shape2['y2'])
        
        # Check if there is any overlap
        if x_overlap_end <= x_overlap_start or y_overlap_end <= y_overlap_start:
            return False
        
        # Calculate overlap area
        overlap_area = (x_overlap_end - x_overlap_start) * (y_overlap_end - y_overlap_start)
        
        # Calculate smaller shape area
        area1 = shape1['width'] * shape1['height']
        area2 = shape2['width'] * shape2['height']
        smaller_area = min(area1, area2)
        
        # Check if overlap is at least 30% of the smaller shape
        if smaller_area == 0:
            return False
        
        overlap_ratio = overlap_area / smaller_area
        return overlap_ratio >= 0.3
    
    def _get_aspect_ratio(self, shape: Dict[str, Any]) -> float:
        """Calculate aspect ratio (width/height) of a shape."""
        height = shape.get('height', 1)
        if height == 0:
            return 0
        return shape.get('width', 0) / height
    
    def _get_center(self, shape: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate center point of a shape."""
        center_x = (shape['x'] + shape['x2']) / 2
        center_y = (shape['y'] + shape['y2']) / 2
        return (center_x, center_y)
