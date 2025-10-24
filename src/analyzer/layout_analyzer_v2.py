"""
Layout Analyzer V2 - Improved layout analysis with better text grouping
"""

import logging
from typing import List, Dict, Any
from ..parser.element_extractor import ElementExtractor

logger = logging.getLogger(__name__)


class LayoutAnalyzerV2:
    """
    Improved layout analyzer that preserves text structure better.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Layout Analyzer V2.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.title_threshold = config.get('title_threshold', 20)
        self.min_paragraph_chars = config.get('min_paragraph_chars', 10)
        self.group_tolerance = config.get('group_tolerance', 10)
        self.detect_headers = config.get('detect_headers', True)
        self.detect_footers = config.get('detect_footers', True)
    
    def analyze_page(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single page with improved text grouping.
        
        Args:
            page_data: Page data from PDF parser
            
        Returns:
            Dictionary with analyzed layout structure
        """
        page_width = page_data.get('width', 0)
        page_height = page_data.get('height', 0)
        elements = page_data.get('elements', [])
        
        # Separate elements by type
        text_elements = ElementExtractor.get_text_elements(page_data)
        image_elements = ElementExtractor.get_image_elements(page_data)
        shape_elements = ElementExtractor.get_shape_elements(page_data)
        
        layout_regions = []
        
        # Process shapes first (backgrounds, decorations)
        for shape_elem in shape_elements:
            shape_area = shape_elem['width'] * shape_elem['height']
            page_area = page_width * page_height
            width = shape_elem['width']
            height = shape_elem['height']
            
            # More precise role detection based on HTML specifications
            if shape_area > page_area * 0.5:
                # Full-page background
                role = 'background'
                z_index = -1
            elif height < 15 and width > page_width * 0.9:
                # Thin horizontal bar across top (like top-bar: 10px height, full width)
                role = 'decoration'
                z_index = 0
            elif width < 10 and height > 50:
                # Narrow vertical strip (like border-left: 4px solid)
                role = 'border'
                z_index = 0
            elif width > 20 and height > 20 and width < 80 and height < 50:
                # Small rectangles (like risk badges)
                role = 'decoration'
                z_index = 1
            elif width > 200 and height > 50:
                # Large rectangles (like card backgrounds)
                role = 'card_background'
                z_index = 0
            else:
                # Default to decoration for other shapes
                role = 'decoration'
                z_index = 0
            
            layout_regions.append({
                'role': role,
                'bbox': [shape_elem['x'], shape_elem['y'], shape_elem['x2'], shape_elem['y2']],
                'elements': [shape_elem],
                'z_index': z_index
            })
        
        # Process images
        for img_elem in image_elements:
            layout_regions.append({
                'role': 'image',
                'bbox': [img_elem['x'], img_elem['y'], img_elem['x2'], img_elem['y2']],
                'elements': [img_elem],
                'z_index': 1
            })
        
        # Group text elements by spatial proximity AND style similarity
        text_groups = self._group_text_smartly(text_elements, page_width, page_height)
        
        # Convert text groups to regions
        for group in text_groups:
            layout_regions.append(group)
        
        # Sort by z-index and position
        layout_regions.sort(key=lambda r: (r.get('z_index', 0), r['bbox'][1]))
        
        return {
            'page_num': page_data.get('page_num', 0),
            'width': page_width,
            'height': page_height,
            'layout': layout_regions
        }
    
    def _group_text_smartly(self, text_elements: List[Dict[str, Any]], 
                           page_width: float, page_height: float) -> List[Dict[str, Any]]:
        """
        Group text elements intelligently based on position and style.
        
        Args:
            text_elements: List of text elements
            page_width: Page width
            page_height: Page height
            
        Returns:
            List of text region dictionaries
        """
        if not text_elements:
            return []
        
        # Sort by Y position first
        sorted_elements = sorted(text_elements, key=lambda e: (e.get('y', 0), e.get('x', 0)))
        
        regions = []
        processed = set()
        
        for elem in sorted_elements:
            if id(elem) in processed:
                continue
            
            # Determine role based on characteristics
            font_size = elem.get('font_size', 0)
            y_pos = elem.get('y', 0)
            
            # Title detection (large font in upper area)
            if font_size >= self.title_threshold and y_pos < page_height * 0.2:
                role = 'title' if font_size >= 30 else 'subtitle'
            # Header detection (top 10%)
            elif y_pos < page_height * 0.1:
                role = 'header'
            # Footer detection (bottom 10%)
            elif y_pos > page_height * 0.9:
                role = 'footer'
            # Section heading (medium-large font)
            elif font_size >= 18:
                role = 'heading'
            # Regular text
            else:
                role = 'text'
            
            # Find nearby elements with similar characteristics
            group_elements = [elem]
            processed.add(id(elem))
            
            elem_y = elem.get('y', 0)
            elem_y2 = elem.get('y2', 0)
            elem_x = elem.get('x', 0)
            elem_x2 = elem.get('x2', 0)
            elem_font_size = elem.get('font_size', 0)
            elem_color = elem.get('color', '')
            
            # Look for elements on the same line or closely positioned
            # Important: Track the rightmost x2 of the current group for gap calculation
            current_x2 = elem_x2
            
            # Debug logging for specific text
            if elem.get('content', '') in ['8', '高危', '4', '12', '19']:
                logger.debug(f"Processing element: '{elem.get('content', '')}' at y={elem_y:.1f}, x={elem_x:.1f}-{elem_x2:.1f}")
            
            for other in sorted_elements:
                if id(other) in processed:
                    continue
                
                other_y = other.get('y', 0)
                other_x = other.get('x', 0)
                other_x2 = other.get('x2', 0)
                other_font_size = other.get('font_size', 0)
                other_color = other.get('color', '')
                
                # Same line criteria
                y_diff = abs(other_y - elem_y)
                x_gap = other_x - current_x2
                
                # Check if elements have the same text style (bold, italic)
                elem_is_bold = elem.get('is_bold', False)
                elem_is_italic = elem.get('is_italic', False)
                other_is_bold = other.get('is_bold', False)
                other_is_italic = other.get('is_italic', False)
                same_style = (elem_is_bold == other_is_bold) and (elem_is_italic == other_is_italic)
                
                # Group if on same line and close horizontal proximity
                # Use very small gap tolerance (1pt) for tightly-coupled text like "8个", "高危4"
                # Use larger tolerance (30pt) for related text with spacing
                if y_diff <= self.group_tolerance:
                    should_group = False
                    
                    # Very close elements (gap ≤ 1pt, allow negative for overlaps or left neighbors)
                    # Check both directions: element could be to the left or right
                    
                    # Direction 1: Check if other element is directly to our RIGHT
                    if 0 <= x_gap <= 1.0:
                        # Only group if same font size, color AND style (bold/italic)
                        if abs(other_font_size - elem_font_size) <= 2 and other_color == elem_color and same_style:
                            should_group = True
                            if elem.get('content', '') in ['8', '高危', '4', '12', '19']:
                                logger.debug(f"  → Grouping '{other.get('content', '')}' on RIGHT (gap={x_gap:.2f}pt)")
                    
                    # Direction 2: Check if other element is directly to our LEFT
                    # Calculate gap from other's right edge to our left edge
                    elif x_gap < 0:
                        other_x2 = other.get('x2', other_x)
                        left_gap = elem_x - other_x2
                        # Only group if they are adjacent (gap ≤ 1pt) and same style
                        if -1.0 <= left_gap <= 1.0:
                            if abs(other_font_size - elem_font_size) <= 2 and other_color == elem_color and same_style:
                                should_group = True
                                if elem.get('content', '') in ['8', '高危', '4', '12', '19']:
                                    logger.debug(f"  → Grouping '{other.get('content', '')}' on LEFT (left_gap={left_gap:.2f}pt)")
                    elif elem.get('content', '') in ['4', '12', '19'] and y_diff <= self.group_tolerance and other.get('content', '') in ['高危', '中危', '低危']:
                        logger.debug(f"  × Checking '{other.get('content', '')}' after '{ elem.get('content', '')}' (gap={x_gap:.2f}pt, y_diff={y_diff:.2f}pt)")
                    # Moderate distance (1pt < gap ≤ 30pt) - group only if same style
                    elif 1.0 < x_gap <= self.group_tolerance * 3:
                        if other_font_size == elem_font_size and other_color == elem_color and same_style:
                            should_group = True
                            if elem.get('content', '') in ['8', '高危']:
                                logger.debug(f"  → Grouping '{other.get('content', '')}' (gap={x_gap:.2f}pt, moderate)")
                    elif elem.get('content', '') in ['8', '高危'] and y_diff <= self.group_tolerance and other.get('content', '') in ['个', '4']:
                        logger.debug(f"  × Skipping '{other.get('content', '')}' (gap={x_gap:.2f}pt, y_diff={y_diff:.2f}pt)")
                    
                    if should_group:
                        group_elements.append(other)
                        processed.add(id(other))
                        current_x2 = max(current_x2, other_x2)
            
            # Create region
            bbox = self._calculate_bbox(group_elements)
            
            # Sort group elements by x position before merging text
            sorted_group = sorted(group_elements, key=lambda e: e.get('x', 0))
            
            # Merge text (without spaces for elements with gap ≤ 1pt)
            text_parts = []
            for i, e in enumerate(sorted_group):
                if i > 0:
                    # Check gap with previous element
                    prev_x2 = sorted_group[i-1].get('x2', sorted_group[i-1].get('x', 0))
                    curr_x = e.get('x', 0)
                    gap = curr_x - prev_x2
                    # Add space only if gap > 1pt
                    if gap > 1.0:
                        text_parts.append(' ')
                text_parts.append(e.get('content', ''))
            text_content = ''.join(text_parts)
            
            # Debug logging
            if elem.get('content', '') in ['8', '高危']:
                logger.debug(f"Creating region: '{text_content}' with {len(group_elements)} elements: {[e.get('content', '') for e in group_elements]}")
            
            regions.append({
                'role': role,
                'bbox': bbox,
                'elements': group_elements,
                'text': text_content,
                'z_index': 2
            })
        
        return regions
    
    def _calculate_bbox(self, elements: List[Dict[str, Any]]) -> List[float]:
        """
        Calculate bounding box for a list of elements.
        
        Args:
            elements: List of elements
            
        Returns:
            Bounding box [x1, y1, x2, y2]
        """
        if not elements:
            return [0, 0, 0, 0]
        
        x_coords = [e.get('x', 0) for e in elements] + [e.get('x2', 0) for e in elements]
        y_coords = [e.get('y', 0) for e in elements] + [e.get('y2', 0) for e in elements]
        
        return [
            min(x_coords),
            min(y_coords),
            max(x_coords),
            max(y_coords)
        ]
