"""
Border Extractor - Extracts border elements from complex PDF paths

This module handles the extraction of border lines that are embedded within
complex path structures (such as rounded rectangles with border-left styling).
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import fitz

logger = logging.getLogger(__name__)


class BorderExtractor:
    """
    Extracts border elements from PDF drawing paths.
    
    Handles cases where borders are part of complex paths (rounded rectangles, etc.)
    rather than standalone shapes.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Border Extractor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        # Minimum length for a line to be considered a border (in points)
        self.min_border_length = self.config.get('min_border_length', 20.0)
        # Maximum width for a vertical border (in points)
        self.max_vertical_border_width = self.config.get('max_vertical_border_width', 10.0)
        # Maximum height for a horizontal border (in points)
        self.max_horizontal_border_height = self.config.get('max_horizontal_border_height', 10.0)
        # Tolerance for line straightness (in points)
        self.straightness_tolerance = self.config.get('straightness_tolerance', 1.0)
    
    def extract_borders_from_drawings(self, drawings: List[Dict[str, Any]], 
                                      page_width: float = None) -> List[Dict[str, Any]]:
        """
        Extract border elements from drawing paths.
        
        Args:
            drawings: List of drawing dictionaries from page.get_drawings()
            page_width: Page width for position-based filtering
            
        Returns:
            List of border shape dictionaries
        """
        borders = []
        
        for idx, drawing in enumerate(drawings):
            # Extract borders from this drawing's path
            drawing_borders = self._extract_borders_from_path(drawing, page_width)
            
            if drawing_borders:
                logger.debug(f"Extracted {len(drawing_borders)} border(s) from drawing {idx}")
                borders.extend(drawing_borders)
        
        # Filter to keep only visually significant borders (e.g., left borders of cards)
        borders = self._filter_significant_borders(borders, page_width)
        
        return borders
    
    def _extract_borders_from_path(self, drawing: Dict[str, Any], 
                                   page_width: float = None) -> List[Dict[str, Any]]:
        """
        Extract border lines from a single drawing path.
        
        Analyzes the path items to find straight line segments that could be borders.
        
        Args:
            drawing: Drawing dictionary with 'items', 'fill', 'fill_opacity', etc.
            page_width: Page width for position context
            
        Returns:
            List of border shape dictionaries
        """
        borders = []
        
        items = drawing.get('items', [])
        if not items:
            return borders
        
        # Get drawing properties
        fill_color = drawing.get('fill', None)
        fill_opacity = drawing.get('fill_opacity', 1.0)
        stroke_color = drawing.get('color', None)
        stroke_width = drawing.get('width', 1.0)
        rect = drawing.get('rect', None)
        
        # Extract line segments from path
        line_segments = self._extract_line_segments(items)
        
        # Analyze line segments to find borders
        for segment in line_segments:
            start_point, end_point = segment
            
            # Check if this is a potential border
            border_info = self._analyze_line_as_border(start_point, end_point, rect, page_width)
            
            if border_info:
                # Create border shape element
                border_type, border_rect = border_info
                
                border = {
                    'type': 'shape',
                    'shape_type': 'border',
                    'border_type': border_type,  # 'left', 'right', 'top', 'bottom'
                    'x': border_rect[0],
                    'y': border_rect[1],
                    'x2': border_rect[2],
                    'y2': border_rect[3],
                    'width': border_rect[2] - border_rect[0],
                    'height': border_rect[3] - border_rect[1],
                    'fill_color': self._color_to_hex(fill_color),
                    'fill_opacity': fill_opacity,
                    'stroke_color': self._color_to_hex(stroke_color) if stroke_color else None,
                    'stroke_width': stroke_width if stroke_color else 0
                }
                
                borders.append(border)
                logger.debug(f"Found {border_type} border at ({border_rect[0]:.1f}, {border_rect[1]:.1f}), "
                           f"size: {border['width']:.1f}x{border['height']:.1f}")
        
        return borders
    
    def _extract_line_segments(self, path_items: List[Tuple]) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Extract straight line segments from path items.
        
        Args:
            path_items: List of path command tuples from drawing['items']
            
        Returns:
            List of line segments as ((x1, y1), (x2, y2)) tuples
        """
        line_segments = []
        current_point = None
        
        for item in path_items:
            cmd = item[0]
            
            if cmd == 'l':  # Line to
                # Format: ('l', (x, y), start_point)
                end_point = item[1]
                start_point = item[2] if len(item) > 2 else current_point
                
                if start_point and end_point:
                    line_segments.append((start_point, end_point))
                
                current_point = end_point
            
            elif cmd == 'c':  # Cubic Bezier curve - skip for border detection
                # Curves are not borders
                end_point = item[3] if len(item) > 3 else item[1]
                current_point = end_point
            
            elif cmd == 're':  # Rectangle
                # Format: ('re', (x, y, width, height))
                rect = item[1]
                x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
                
                # Extract edges as line segments
                # Top edge
                line_segments.append(((x, y), (x + w, y)))
                # Right edge
                line_segments.append(((x + w, y), (x + w, y + h)))
                # Bottom edge
                line_segments.append(((x + w, y + h), (x, y + h)))
                # Left edge
                line_segments.append(((x, y + h), (x, y)))
                
                current_point = (x, y)
            
            elif cmd == 'm':  # Move to
                current_point = item[1]
        
        return line_segments
    
    def _analyze_line_as_border(self, start: Tuple[float, float], end: Tuple[float, float],
                               parent_rect: Optional[Any] = None, 
                               page_width: float = None) -> Optional[Tuple[str, Tuple[float, float, float, float]]]:
        """
        Analyze if a line segment is a border.
        
        Args:
            start: Start point (x, y)
            end: End point (x, y)
            parent_rect: Parent drawing rectangle for context
            page_width: Page width for position analysis
            
        Returns:
            Tuple of (border_type, rect) if it's a border, None otherwise
            border_type: 'left', 'right', 'top', 'bottom'
            rect: (x1, y1, x2, y2) bounding box
        """
        x1, y1 = start
        x2, y2 = end
        
        # Calculate line properties
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        length = max(dx, dy)
        
        # Check if line is long enough
        if length < self.min_border_length:
            return None
        
        # Check if it's a vertical line (potential left/right border)
        if dy > dx * 3 and dx < self.max_vertical_border_width:
            # It's a vertical border
            min_x = min(x1, x2)
            max_x = max(x1, x2)
            min_y = min(y1, y2)
            max_y = max(y1, y2)
            
            # Determine if it's a left or right border based on x position
            border_type = 'left'
            if parent_rect and page_width:
                # Check if this line is on the left edge of the parent rect
                parent_left = parent_rect.x0 if hasattr(parent_rect, 'x0') else None
                parent_right = parent_rect.x1 if hasattr(parent_rect, 'x1') else None
                
                if parent_left is not None and abs(min_x - parent_left) < 5:
                    border_type = 'left'
                elif parent_right is not None and abs(min_x - parent_right) < 5:
                    border_type = 'right'
                elif page_width and min_x > page_width * 0.8:
                    border_type = 'right'
            
            # Create bounding rectangle for the border
            # Use a standard width for rendering
            border_width = max(max_x - min_x, 4.0)  # Minimum 4pt visible width
            
            rect = (min_x, min_y, min_x + border_width, max_y)
            
            return (border_type, rect)
        
        # Check if it's a horizontal line (potential top/bottom border)
        elif dx > dy * 3 and dy < self.max_horizontal_border_height:
            # It's a horizontal border
            min_x = min(x1, x2)
            max_x = max(x1, x2)
            min_y = min(y1, y2)
            max_y = max(y1, y2)
            
            border_type = 'top'
            if parent_rect:
                # Check if this line is on the top or bottom edge
                parent_top = parent_rect.y0 if hasattr(parent_rect, 'y0') else None
                parent_bottom = parent_rect.y1 if hasattr(parent_rect, 'y1') else None
                
                if parent_top is not None and abs(min_y - parent_top) < 5:
                    border_type = 'top'
                elif parent_bottom is not None and abs(min_y - parent_bottom) < 5:
                    border_type = 'bottom'
            
            # Use a standard height for rendering
            border_height = max(max_y - min_y, 4.0)  # Minimum 4pt visible height
            
            rect = (min_x, min_y, max_x, min_y + border_height)
            
            return (border_type, rect)
        
        return None
    
    def _color_to_hex(self, color: Optional[Tuple]) -> str:
        """
        Convert PDF color tuple to hex string.
        
        Args:
            color: RGB tuple (r, g, b) where values are 0.0-1.0
            
        Returns:
            Hex color string like '#RRGGBB'
        """
        if not color:
            return '#000000'
        
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            r = int(color[0] * 255)
            g = int(color[1] * 255)
            b = int(color[2] * 255)
            return f'#{r:02X}{g:02X}{b:02X}'
        
        return '#000000'
    
    def filter_duplicate_borders(self, borders: List[Dict[str, Any]], 
                                 existing_shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out borders that are already represented in existing shapes.
        
        Args:
            borders: List of extracted border shapes
            existing_shapes: List of existing shape elements
            
        Returns:
            Filtered list of borders (only new borders not already present)
        """
        filtered = []
        
        for border in borders:
            is_duplicate = False
            
            for shape in existing_shapes:
                if self._are_borders_duplicate(border, shape):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered.append(border)
        
        return filtered
    
    def _are_borders_duplicate(self, border1: Dict[str, Any], border2: Dict[str, Any]) -> bool:
        """
        Check if two borders are duplicates (represent the same visual element).
        
        Args:
            border1: First border element
            border2: Second border element
            
        Returns:
            True if borders are duplicates
        """
        # Check position overlap
        tolerance = 5.0
        
        x_overlap = abs(border1['x'] - border2['x']) <= tolerance
        y_overlap = abs(border1['y'] - border2['y']) <= tolerance
        width_similar = abs(border1['width'] - border2['width']) <= tolerance
        height_similar = abs(border1['height'] - border2['height']) <= tolerance
        
        # Check color match
        color_match = border1.get('fill_color') == border2.get('fill_color')
        
        return x_overlap and y_overlap and width_similar and height_similar and color_match
    
    def _filter_significant_borders(self, borders: List[Dict[str, Any]], 
                                    page_width: float = None) -> List[Dict[str, Any]]:
        """
        Filter borders to keep only visually significant ones.
        
        Strategy:
        - Keep only left borders of content cards (not page edges)
        - Remove page-edge borders (at x=0 or x=page_width)
        - Remove duplicate/overlapping borders
        - Prefer borders with non-default opacity (more specific styling)
        
        Args:
            borders: List of border elements
            page_width: Page width for edge detection
            
        Returns:
            Filtered list of borders
        """
        if not borders:
            return borders
        
        filtered = []
        
        for border in borders:
            # Skip page-edge borders
            if page_width:
                x = border['x']
                # Skip borders at page edges (within 10pt)
                if x < 10 or x > page_width - 10:
                    logger.debug(f"Skipping page-edge border at x={x:.1f}")
                    continue
            
            # Skip white/background borders (usually not visible decorations)
            color = border.get('fill_color', '').upper()
            if color in ['#FFFFFF', '#FFF']:
                logger.debug(f"Skipping white border at ({border['x']:.1f}, {border['y']:.1f})")
                continue
            
            # Prefer left borders for card styling (common pattern in designs)
            border_type = border.get('border_type', '')
            if border_type in ['left']:
                filtered.append(border)
            # Also keep top/bottom borders if they have specific styling (non-full-opacity)
            elif border_type in ['top', 'bottom']:
                opacity = border.get('fill_opacity', 1.0)
                if opacity < 0.9:  # Has transparency = styled border
                    filtered.append(border)
        
        # Merge very similar borders (within 2pt)
        filtered = self._merge_similar_borders(filtered)
        
        logger.debug(f"Filtered {len(borders)} borders down to {len(filtered)} significant borders")
        
        return filtered
    
    def _merge_similar_borders(self, borders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge borders that are very close together (likely duplicates from overlapping paths).
        
        Args:
            borders: List of border elements
            
        Returns:
            Merged list of borders
        """
        if len(borders) <= 1:
            return borders
        
        merged = []
        used = set()
        
        for i, border1 in enumerate(borders):
            if i in used:
                continue
            
            # Find similar borders
            similar_group = [border1]
            
            for j in range(i + 1, len(borders)):
                if j in used:
                    continue
                
                border2 = borders[j]
                
                # Check if they're very similar (within 2pt)
                if (abs(border1['x'] - border2['x']) < 2 and 
                    abs(border1['y'] - border2['y']) < 2 and
                    abs(border1['width'] - border2['width']) < 2 and
                    abs(border1['height'] - border2['height']) < 2 and
                    border1.get('border_type') == border2.get('border_type') and
                    border1.get('fill_color') == border2.get('fill_color')):
                    
                    similar_group.append(border2)
                    used.add(j)
            
            # Keep the border with the most specific opacity (lowest opacity = most styled)
            best_border = min(similar_group, key=lambda b: b.get('fill_opacity', 1.0))
            merged.append(best_border)
        
        return merged
