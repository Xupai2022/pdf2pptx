"""
Layout Analyzer - Analyzes page layout and structure
"""

import logging
from typing import List, Dict, Any, Tuple
from ..parser.element_extractor import ElementExtractor

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """
    Analyzes page layout to detect semantic structure.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Layout Analyzer with configuration.
        
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
        Analyze a single page and return structured layout information.
        
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
        
        # Detect layout regions
        layout_regions = []
        
        # Detect title
        title_region = self._detect_title(text_elements, page_width, page_height)
        if title_region:
            layout_regions.append(title_region)
        
        # Detect header
        if self.detect_headers:
            header_region = self._detect_header(text_elements, page_width, page_height)
            if header_region:
                layout_regions.append(header_region)
        
        # Detect footer
        if self.detect_footers:
            footer_region = self._detect_footer(text_elements, page_width, page_height)
            if footer_region:
                layout_regions.append(footer_region)
        
        # Group remaining text into content regions
        content_regions = self._detect_content_regions(text_elements, layout_regions)
        layout_regions.extend(content_regions)
        
        # Process image regions
        for img_elem in image_elements:
            layout_regions.append({
                'role': 'image',
                'bbox': [img_elem['x'], img_elem['y'], img_elem['x2'], img_elem['y2']],
                'elements': [img_elem],
                'z_index': 1  # Images typically on top
            })
        
        # Process shape regions (backgrounds, decorations)
        for shape_elem in shape_elements:
            # Large shapes are likely backgrounds
            shape_area = shape_elem['width'] * shape_elem['height']
            page_area = page_width * page_height
            
            if shape_area > page_area * 0.5:
                role = 'background'
                z_index = -1
            else:
                role = 'decoration'
                z_index = 0
            
            layout_regions.append({
                'role': role,
                'bbox': [shape_elem['x'], shape_elem['y'], shape_elem['x2'], shape_elem['y2']],
                'elements': [shape_elem],
                'z_index': z_index
            })
        
        # Sort by z-index and position
        layout_regions.sort(key=lambda r: (r.get('z_index', 0), r['bbox'][1]))
        
        return {
            'page_num': page_data.get('page_num', 0),
            'width': page_width,
            'height': page_height,
            'layout': layout_regions
        }
    
    def _detect_title(self, text_elements: List[Dict[str, Any]], 
                     page_width: float, page_height: float) -> Dict[str, Any]:
        """
        Detect the main title of the page.
        
        Args:
            text_elements: List of text elements
            page_width: Page width
            page_height: Page height
            
        Returns:
            Title region dictionary or None
        """
        if not text_elements:
            return None
        
        # Find largest text in upper portion of page
        upper_elements = [e for e in text_elements if e.get('y', 0) < page_height * 0.3]
        
        if not upper_elements:
            return None
        
        # Sort by font size
        sorted_by_size = sorted(upper_elements, key=lambda e: e.get('font_size', 0), reverse=True)
        
        # Check if largest is significantly larger
        largest = sorted_by_size[0]
        largest_size = largest.get('font_size', 0)
        
        if largest_size >= self.title_threshold:
            # Find all elements that are part of the title (similar y position)
            title_y = largest.get('y', 0)
            title_elements = [
                e for e in upper_elements 
                if abs(e.get('y', 0) - title_y) < self.group_tolerance
            ]
            
            # Calculate bounding box
            bbox = self._calculate_bbox(title_elements)
            
            # Merge text
            title_text = ElementExtractor.merge_text_on_line(title_elements)
            
            return {
                'role': 'title',
                'bbox': bbox,
                'elements': title_elements,
                'text': title_text,
                'z_index': 2
            }
        
        return None
    
    def _detect_header(self, text_elements: List[Dict[str, Any]], 
                      page_width: float, page_height: float) -> Dict[str, Any]:
        """
        Detect page header.
        
        Args:
            text_elements: List of text elements
            page_width: Page width
            page_height: Page height
            
        Returns:
            Header region dictionary or None
        """
        if not text_elements:
            return None
        
        # Header is typically in top 10% of page
        header_threshold = page_height * 0.1
        header_elements = [e for e in text_elements if e.get('y', 0) < header_threshold]
        
        if not header_elements:
            return None
        
        # Check if it's small text (not a title)
        if all(e.get('font_size', 0) < self.title_threshold for e in header_elements):
            bbox = self._calculate_bbox(header_elements)
            
            return {
                'role': 'header',
                'bbox': bbox,
                'elements': header_elements,
                'z_index': 1
            }
        
        return None
    
    def _detect_footer(self, text_elements: List[Dict[str, Any]], 
                      page_width: float, page_height: float) -> Dict[str, Any]:
        """
        Detect page footer.
        
        Args:
            text_elements: List of text elements
            page_width: Page width
            page_height: Page height
            
        Returns:
            Footer region dictionary or None
        """
        if not text_elements:
            return None
        
        # Footer is typically in bottom 10% of page
        footer_threshold = page_height * 0.9
        footer_elements = [e for e in text_elements if e.get('y', 0) > footer_threshold]
        
        if not footer_elements:
            return None
        
        bbox = self._calculate_bbox(footer_elements)
        
        return {
            'role': 'footer',
            'bbox': bbox,
            'elements': footer_elements,
            'z_index': 1
        }
    
    def _detect_content_regions(self, text_elements: List[Dict[str, Any]], 
                               existing_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect content regions (paragraphs) from remaining text.
        
        Args:
            text_elements: List of text elements
            existing_regions: Already detected regions
            
        Returns:
            List of content region dictionaries
        """
        # Filter out text that's already in existing regions
        used_elements = set()
        for region in existing_regions:
            for elem in region.get('elements', []):
                if elem.get('type') == 'text':
                    used_elements.add(id(elem))
        
        available_elements = [e for e in text_elements if id(e) not in used_elements]
        
        if not available_elements:
            return []
        
        # Group text into lines
        lines = ElementExtractor.group_by_line(available_elements, self.group_tolerance)
        
        # Group lines into paragraphs/content blocks
        content_regions = []
        current_block = []
        prev_y2 = None
        
        for line in lines:
            if not line:
                continue
            
            line_y = min(e.get('y', 0) for e in line)
            
            if prev_y2 is not None:
                gap = line_y - prev_y2
                
                # If gap is large, start new block
                if gap > self.group_tolerance * 2:
                    if current_block:
                        content_regions.append(self._create_content_region(current_block))
                        current_block = []
            
            current_block.extend(line)
            prev_y2 = max(e.get('y2', 0) for e in line)
        
        # Add last block
        if current_block:
            content_regions.append(self._create_content_region(current_block))
        
        return content_regions
    
    def _create_content_region(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a content region from a list of text elements.
        
        Args:
            elements: List of text elements
            
        Returns:
            Content region dictionary
        """
        bbox = self._calculate_bbox(elements)
        
        # Determine content type based on characteristics
        avg_font_size = sum(e.get('font_size', 0) for e in elements) / len(elements)
        
        if avg_font_size >= self.title_threshold * 0.8:
            role = 'subtitle'
        else:
            role = 'paragraph'
        
        return {
            'role': role,
            'bbox': bbox,
            'elements': elements,
            'z_index': 2
        }
    
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
