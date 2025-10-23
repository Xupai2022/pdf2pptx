"""
Element Renderer - Renders individual slide elements to PowerPoint
"""

import logging
import io
from typing import Dict, Any
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from ..rebuilder.slide_model import SlideElement
from ..mapper.style_mapper import StyleMapper

logger = logging.getLogger(__name__)


class ElementRenderer:
    """
    Renders slide elements to PowerPoint shapes.
    """
    
    def __init__(self, style_mapper: StyleMapper):
        """
        Initialize Element Renderer.
        
        Args:
            style_mapper: StyleMapper instance
        """
        self.style_mapper = style_mapper
    
    def render_text(self, slide, element: SlideElement) -> Any:
        """
        Render a text element to the slide.
        
        Args:
            slide: PowerPoint slide object
            element: SlideElement with text content
            
        Returns:
            Created shape object
        """
        position = element.position
        content = element.content
        style = element.style
        
        # Clean content - remove control characters for XML compatibility
        if isinstance(content, str):
            # Remove NULL bytes and control characters except tab, newline, carriage return
            # Also handle special Unicode characters that might cause issues
            cleaned = []
            for c in content:
                code = ord(c)
                # Allow printable characters, tab, newline, carriage return
                if code >= 32 or c in '\t\n\r':
                    # Skip private use area and other problematic ranges
                    if code < 0xE000 or code > 0xF8FF:  # Skip private use area
                        if code < 0xD800 or code > 0xDFFF:  # Skip surrogates
                            cleaned.append(c)
            content = ''.join(cleaned)
        
        if not content or not content.strip():
            return None
        
        # Create text box
        left = Inches(position['x'])
        top = Inches(position['y'])
        width = Inches(position['width'])
        height = Inches(position['height'])
        
        # Ensure minimum dimensions
        if width < Inches(0.5):
            width = Inches(1)
        if height < Inches(0.3):
            height = Inches(0.5)
        
        try:
            textbox = slide.shapes.add_textbox(left, top, width, height)
            text_frame = textbox.text_frame
            text_frame.text = content
            
            # Apply style
            self.style_mapper.apply_text_style(text_frame, style)
            
            # Text frame properties
            text_frame.word_wrap = True
            
            return textbox
            
        except Exception as e:
            logger.error(f"Failed to render text element: {e}")
            return None
    
    def render_image(self, slide, element: SlideElement) -> Any:
        """
        Render an image element to the slide.
        
        Args:
            slide: PowerPoint slide object
            element: SlideElement with image content
            
        Returns:
            Created picture object
        """
        position = element.position
        image_data = element.content
        
        # Create image stream
        image_stream = io.BytesIO(image_data)
        
        # Position and size
        left = Inches(position['x'])
        top = Inches(position['y'])
        width = Inches(position['width'])
        height = Inches(position['height'])
        
        # Ensure minimum dimensions
        if width < Inches(0.5):
            width = Inches(1)
        if height < Inches(0.5):
            height = Inches(1)
        
        try:
            picture = slide.shapes.add_picture(image_stream, left, top, width, height)
            return picture
            
        except Exception as e:
            logger.error(f"Failed to render image element: {e}")
            return None
    
    def render_shape(self, slide, element: SlideElement) -> Any:
        """
        Render a shape element to the slide.
        
        Args:
            slide: PowerPoint slide object
            element: SlideElement with shape content
            
        Returns:
            Created shape object
        """
        position = element.position
        shape_type = element.content
        style = element.style
        
        # Validate shape_type
        if not shape_type or not isinstance(shape_type, str):
            shape_type = 'rectangle'
        
        # Position and size
        left = Inches(position['x'])
        top = Inches(position['y'])
        width = Inches(position['width'])
        height = Inches(position['height'])
        
        # Ensure minimum dimensions
        if width < Inches(0.1):
            width = Inches(0.5)
        if height < Inches(0.1):
            height = Inches(0.5)
        
        try:
            # Map shape type to MSO_SHAPE
            shape_map = {
                'rectangle': MSO_SHAPE.RECTANGLE,
                'rect': MSO_SHAPE.RECTANGLE,
                'circle': MSO_SHAPE.OVAL,
                'oval': MSO_SHAPE.OVAL,
                'line': MSO_SHAPE.RECTANGLE,  # Default to rectangle
                'path': MSO_SHAPE.RECTANGLE
            }
            
            mso_shape = shape_map.get(shape_type.lower(), MSO_SHAPE.RECTANGLE)
            
            # Add shape
            shape = slide.shapes.add_shape(mso_shape, left, top, width, height)
            
            # Apply style
            self.style_mapper.apply_shape_style(shape, style)
            
            return shape
            
        except Exception as e:
            logger.error(f"Failed to render shape element: {e}")
            return None
    
    def render_element(self, slide, element: SlideElement) -> Any:
        """
        Render any element type to the slide.
        
        Args:
            slide: PowerPoint slide object
            element: SlideElement to render
            
        Returns:
            Created shape/object
        """
        if element.type == 'text':
            return self.render_text(slide, element)
        elif element.type == 'image':
            return self.render_image(slide, element)
        elif element.type == 'shape':
            return self.render_shape(slide, element)
        else:
            logger.warning(f"Unknown element type: {element.type}")
            return None
