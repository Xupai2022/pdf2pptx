"""
Coordinate Mapper - Maps PDF coordinates to PowerPoint coordinates
"""

import logging
from typing import Dict, Any, Tuple
from .slide_model import SlideModel, SlideElement

logger = logging.getLogger(__name__)


class CoordinateMapper:
    """
    Maps PDF coordinates to PowerPoint slide coordinates.
    Handles coordinate transformation and normalization.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Coordinate Mapper.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.slide_width = config.get('slide_width', 10)  # inches
        self.slide_height = config.get('slide_height', 7.5)  # inches
        self.margin_left = config.get('margin_left', 0.5)
        self.margin_right = config.get('margin_right', 0.5)
        self.margin_top = config.get('margin_top', 0.5)
        self.margin_bottom = config.get('margin_bottom', 0.5)
    
    def create_slide_model(self, layout_data: Dict[str, Any]) -> SlideModel:
        """
        Create a slide model from analyzed layout data.
        
        Args:
            layout_data: Layout data from analyzer
            
        Returns:
            SlideModel object
        """
        slide_num = layout_data.get('page_num', 0)
        pdf_width = layout_data.get('width', 0)
        pdf_height = layout_data.get('height', 0)
        
        slide = SlideModel(slide_num, self.slide_width, self.slide_height)
        
        # Process layout regions
        for region in layout_data.get('layout', []):
            self._process_region(region, slide, pdf_width, pdf_height)
        
        # Sort elements by z-index
        slide.sort_elements()
        
        return slide
    
    def _process_region(self, region: Dict[str, Any], slide: SlideModel, 
                       pdf_width: float, pdf_height: float):
        """
        Process a layout region and add to slide model.
        
        Args:
            region: Layout region from analyzer
            slide: Target slide model
            pdf_width: PDF page width
            pdf_height: PDF page height
        """
        role = region.get('role', 'unknown')
        bbox = region.get('bbox', [0, 0, 0, 0])
        elements = region.get('elements', [])
        z_index = region.get('z_index', 0)
        
        # Convert bbox to normalized coordinates
        position = self._pdf_to_slide_coords(bbox, pdf_width, pdf_height)
        
        if role in ['title', 'subtitle', 'heading', 'text', 'paragraph', 'header', 'footer']:
            # Process text content
            text = region.get('text', '')
            if not text:
                text = self._merge_element_text(elements)
            
            if text:
                style = self._extract_text_style(elements)
                
                # Set as title if it's a title role
                if role == 'title':
                    slide.set_title(text)
                
                slide.add_text(text, position, style, z_index)
        
        elif role == 'image':
            # Process image
            for elem in elements:
                if elem.get('type') == 'image':
                    image_data = elem.get('image_data')
                    image_format = elem.get('image_format', 'PNG')
                    if image_data:
                        img_position = self._pdf_to_slide_coords(
                            [elem['x'], elem['y'], elem['x2'], elem['y2']],
                            pdf_width, pdf_height
                        )
                        slide.add_image(image_data, img_position, image_format, z_index)
        
        elif role in ['shape', 'decoration', 'card_background', 'border']:
            # Process shape with role information for proper transparency handling
            for elem in elements:
                if elem.get('type') == 'shape':
                    shape_type = elem.get('shape_type', 'rectangle')
                    style = {
                        'fill_color': elem.get('fill_color'),
                        'fill_opacity': elem.get('fill_opacity', 1.0),
                        'stroke_color': elem.get('stroke_color'),
                        'stroke_width': elem.get('stroke_width', 1),
                        'role': role  # Pass role to style for transparency mapping
                    }
                    shape_position = self._pdf_to_slide_coords(
                        [elem['x'], elem['y'], elem['x2'], elem['y2']],
                        pdf_width, pdf_height
                    )
                    slide.add_shape(shape_type, shape_position, style, z_index)
        
        elif role == 'background':
            # Process background
            for elem in elements:
                if elem.get('type') == 'shape' and elem.get('fill_color'):
                    slide.set_background(color=elem.get('fill_color'))
    
    def _pdf_to_slide_coords(self, bbox: list, pdf_width: float, 
                            pdf_height: float) -> Dict[str, float]:
        """
        Convert PDF coordinates to slide coordinates.
        
        Args:
            bbox: Bounding box [x1, y1, x2, y2] in PDF coordinates
            pdf_width: PDF page width
            pdf_height: PDF page height
            
        Returns:
            Position dictionary with normalized coordinates
        """
        x1, y1, x2, y2 = bbox
        
        # Normalize to 0-1 range
        norm_x = x1 / pdf_width if pdf_width > 0 else 0
        norm_y = y1 / pdf_height if pdf_height > 0 else 0
        norm_w = (x2 - x1) / pdf_width if pdf_width > 0 else 0
        norm_h = (y2 - y1) / pdf_height if pdf_height > 0 else 0
        
        # Apply margins
        content_width = self.slide_width - self.margin_left - self.margin_right
        content_height = self.slide_height - self.margin_top - self.margin_bottom
        
        # Convert to inches
        x = self.margin_left + norm_x * content_width
        y = self.margin_top + norm_y * content_height
        width = norm_w * content_width
        height = norm_h * content_height
        
        return {
            'x': x,
            'y': y,
            'width': width,
            'height': height
        }
    
    def _extract_text_style(self, elements: list) -> Dict[str, Any]:
        """
        Extract text style from elements.
        
        Args:
            elements: List of text elements
            
        Returns:
            Style dictionary
        """
        if not elements:
            return {}
        
        # Get style from first element (could be averaged)
        first_elem = elements[0]
        
        style = {
            'font_name': first_elem.get('font_name', 'Arial'),
            'font_size': first_elem.get('font_size', 18),
            'color': first_elem.get('color', '#000000'),
            'bold': first_elem.get('is_bold', False),
            'italic': first_elem.get('is_italic', False)
        }
        
        return style
    
    def _merge_element_text(self, elements: list) -> str:
        """
        Merge text from multiple elements.
        
        Args:
            elements: List of text elements
            
        Returns:
            Merged text string
        """
        text_parts = []
        
        for elem in elements:
            if elem.get('type') == 'text':
                content = elem.get('content', '')
                if content:
                    text_parts.append(content)
        
        return ' '.join(text_parts)
