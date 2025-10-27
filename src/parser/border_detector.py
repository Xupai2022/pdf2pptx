"""
Border Detector - Detects borders by analyzing overlapping shapes with offset

This module detects borders by finding pairs of overlapping shapes where one
is slightly offset from the other, creating a visual border effect.

This is the correct approach for PDF border detection, as opposed to extracting
line segments from individual paths (which creates false positives).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class BorderDetector:
    """
    Detects borders by analyzing shape overlaps and offsets.
    
    The key insight: In PDFs with CSS-like border-left styling, the border is
    created by overlapping two rectangles with a small offset. The offset area
    is the visible border.
    
    Example:
        Shape A: x=61.5, opacity=0.03 (transparent, with border styling)
        Shape B: x=60.0, opacity=1.0 (solid, no border)
        → Visual border at x=60.0 with width=1.5pt
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Border Detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        # Minimum offset to consider as a border (in points)
        self.min_border_offset = self.config.get('min_border_offset', 1.0)
        # Maximum offset to consider as a border (in points)
        self.max_border_offset = self.config.get('max_border_offset', 10.0)
        # Tolerance for shape matching (in points)
        self.shape_match_tolerance = self.config.get('shape_match_tolerance', 5.0)
    
    def detect_borders_from_shapes(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect borders by analyzing shape overlaps.
        
        Strategy:
        1. For each shape, check ALL other shapes for potential border pairs
        2. A border is detected when two shapes overlap with a small offset
        3. Extract the offset region as a border element
        
        This approach avoids the grouping problem where shapes far apart
        (but similar in other ways) are incorrectly grouped together.
        
        Args:
            shapes: List of shape elements from PDF
            
        Returns:
            List of detected border elements
        """
        borders = []
        
        # Skip very large shapes (likely full-page backgrounds)
        # Use a more lenient threshold: skip only if BOTH dimensions are very large
        # This allows wide content boxes (like banner cards) to be analyzed
        candidate_shapes = []
        for s in shapes:
            # Skip if it's a full-page or near-full-page background
            # Typically these have BOTH large width and large height
            is_page_background = (s['width'] >= 1400 and s['height'] >= 700)
            # Also skip very thin decorative elements (likely separators, not borders)
            is_thin_line = (s['height'] <= 10 and s['width'] >= 1000)
            
            if not (is_page_background or is_thin_line):
                candidate_shapes.append(s)
        
        logger.debug(f"Analyzing {len(candidate_shapes)} candidate shapes for borders "
                    f"(filtered {len(shapes) - len(candidate_shapes)} backgrounds/decorations)")
        
        # Check every pair of shapes
        for i in range(len(candidate_shapes)):
            for j in range(i + 1, len(candidate_shapes)):
                shape1 = candidate_shapes[i]
                shape2 = candidate_shapes[j]
                
                # Quick filter: must have same color
                if shape1['fill_color'] != shape2['fill_color']:
                    continue
                
                # Quick filter: must be similar size
                if not self._are_shapes_similar_size(shape1, shape2):
                    continue
                
                # Check if this pair forms a border
                border = self._detect_border_from_pair(shape1, shape2)
                if border:
                    borders.append(border)
                    logger.debug(f"Detected border: {border['border_type']} at "
                               f"({border['x']:.1f}, {border['y']:.1f})")
        
        # Remove duplicates
        borders = self._deduplicate_borders(borders)
        
        logger.info(f"Detected {len(borders)} border(s) from shape overlaps")
        
        return borders
    
    def _are_shapes_similar_size(self, shape1: Dict[str, Any], shape2: Dict[str, Any]) -> bool:
        """
        Check if two shapes have similar size (potential border candidates).
        
        Args:
            shape1: First shape
            shape2: Second shape
            
        Returns:
            True if shapes have similar size
        """
        # Size must be similar (within 5pt tolerance for borders)
        size_tolerance = 5.0
        width_similar = abs(shape1['width'] - shape2['width']) <= size_tolerance
        height_similar = abs(shape1['height'] - shape2['height']) <= size_tolerance
        
        return width_similar and height_similar
    
    def _detect_border_from_pair(self, shape1: Dict[str, Any], 
                                 shape2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect if a border exists between two overlapping shapes.
        
        Border detection criteria:
        1. Shapes have same color and similar size
        2. One shape has transparency, one is opaque
        3. Shapes are offset by 1-10pt in one direction
        4. The offset creates a visible border
        
        Args:
            shape1: First shape
            shape2: Second shape
            
        Returns:
            Border element dict if detected, None otherwise
        """
        # Check opacity difference (one transparent, one opaque)
        opacity1 = shape1.get('fill_opacity', 1.0)
        opacity2 = shape2.get('fill_opacity', 1.0)
        
        # Both must have different opacity (one < 0.5, one >= 0.9)
        min_opacity = min(opacity1, opacity2)
        max_opacity = max(opacity1, opacity2)
        
        if not (min_opacity < 0.5 and max_opacity >= 0.9):
            return None
        
        # Identify which is transparent and which is opaque
        if opacity1 < opacity2:
            transparent_shape = shape1
            opaque_shape = shape2
        else:
            transparent_shape = shape2
            opaque_shape = shape1
        
        # Calculate offset
        dx = transparent_shape['x'] - opaque_shape['x']
        dy = transparent_shape['y'] - opaque_shape['y']
        
        # Check for left border (transparent shape offset to the right)
        if (self.min_border_offset <= dx <= self.max_border_offset and
            abs(dy) < self.shape_match_tolerance):
            
            # Border is the left edge of the opaque shape
            border_width = dx
            border_height = min(transparent_shape['height'], opaque_shape['height'])
            
            return {
                'type': 'shape',
                'shape_type': 'border',
                'border_type': 'left',
                'x': opaque_shape['x'],
                'y': opaque_shape['y'],
                'x2': opaque_shape['x'] + border_width,
                'y2': opaque_shape['y'] + border_height,
                'width': border_width,
                'height': border_height,
                'fill_color': opaque_shape['fill_color'],
                'fill_opacity': 1.0,  # Borders are always opaque
                'stroke_color': None,
                'stroke_width': 0
            }
        
        # Check for right border (transparent shape offset to the left)
        if (self.min_border_offset <= -dx <= self.max_border_offset and
            abs(dy) < self.shape_match_tolerance):
            
            border_width = -dx
            border_height = min(transparent_shape['height'], opaque_shape['height'])
            
            return {
                'type': 'shape',
                'shape_type': 'border',
                'border_type': 'right',
                'x': opaque_shape['x'] + opaque_shape['width'] - border_width,
                'y': opaque_shape['y'],
                'x2': opaque_shape['x'] + opaque_shape['width'],
                'y2': opaque_shape['y'] + border_height,
                'width': border_width,
                'height': border_height,
                'fill_color': opaque_shape['fill_color'],
                'fill_opacity': 1.0,
                'stroke_color': None,
                'stroke_width': 0
            }
        
        # Check for top border (transparent shape offset downward)
        if (self.min_border_offset <= dy <= self.max_border_offset and
            abs(dx) < self.shape_match_tolerance):
            
            border_width = min(transparent_shape['width'], opaque_shape['width'])
            border_height = dy
            
            return {
                'type': 'shape',
                'shape_type': 'border',
                'border_type': 'top',
                'x': opaque_shape['x'],
                'y': opaque_shape['y'],
                'x2': opaque_shape['x'] + border_width,
                'y2': opaque_shape['y'] + border_height,
                'width': border_width,
                'height': border_height,
                'fill_color': opaque_shape['fill_color'],
                'fill_opacity': 1.0,
                'stroke_color': None,
                'stroke_width': 0
            }
        
        # Check for bottom border (transparent shape offset upward)
        if (self.min_border_offset <= -dy <= self.max_border_offset and
            abs(dx) < self.shape_match_tolerance):
            
            border_width = min(transparent_shape['width'], opaque_shape['width'])
            border_height = -dy
            
            return {
                'type': 'shape',
                'shape_type': 'border',
                'border_type': 'bottom',
                'x': opaque_shape['x'],
                'y': opaque_shape['y'] + opaque_shape['height'] - border_height,
                'x2': opaque_shape['x'] + border_width,
                'y2': opaque_shape['y'] + opaque_shape['height'],
                'width': border_width,
                'height': border_height,
                'fill_color': opaque_shape['fill_color'],
                'fill_opacity': 1.0,
                'stroke_color': None,
                'stroke_width': 0
            }
        
        return None
    
    def _deduplicate_borders(self, borders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate borders.
        
        Args:
            borders: List of border elements
            
        Returns:
            Deduplicated list
        """
        if len(borders) <= 1:
            return borders
        
        unique = []
        
        for border in borders:
            is_duplicate = False
            
            for existing in unique:
                if self._are_borders_duplicate(border, existing):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(border)
        
        return unique
    
    def _are_borders_duplicate(self, border1: Dict[str, Any], border2: Dict[str, Any]) -> bool:
        """
        Check if two borders are duplicates.
        
        Args:
            border1: First border
            border2: Second border
            
        Returns:
            True if duplicates
        """
        tolerance = 2.0
        
        return (border1.get('border_type') == border2.get('border_type') and
                abs(border1['x'] - border2['x']) < tolerance and
                abs(border1['y'] - border2['y']) < tolerance and
                abs(border1['width'] - border2['width']) < tolerance and
                abs(border1['height'] - border2['height']) < tolerance and
                border1.get('fill_color') == border2.get('fill_color'))
    

