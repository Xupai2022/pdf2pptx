"""
Slide Model - Intermediate representation of a PowerPoint slide
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SlideElement:
    """Represents a single element in a slide."""
    
    def __init__(self, element_type: str, position: Dict[str, float], 
                 content: Any, style: Dict[str, Any]):
        """
        Initialize a slide element.
        
        Args:
            element_type: Type of element ('text', 'image', 'shape')
            position: Position dictionary with x, y, width, height (normalized 0-1)
            content: Content of the element
            style: Style dictionary (fonts, colors, etc.)
        """
        self.type = element_type
        self.position = position
        self.content = content
        self.style = style
        self.z_index = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'type': self.type,
            'position': self.position,
            'content': self.content,
            'style': self.style,
            'z_index': self.z_index
        }


class SlideModel:
    """
    Intermediate representation of a PowerPoint slide.
    Acts as a bridge between PDF layout and PPTX generation.
    """
    
    def __init__(self, slide_number: int, width: float = 13.333, height: float = 7.5):
        """
        Initialize a slide model.

        Args:
            slide_number: Slide number
            width: Slide width in inches (default 13.333 for 1920px at 144 DPI)
            height: Slide height in inches (default 7.5 for 1080px at 144 DPI)
        """
        self.slide_number = slide_number
        self.width = width
        self.height = height
        self.elements: List[SlideElement] = []
        self.title: Optional[str] = None
        self.background_color: Optional[str] = None
        self.background_image: Optional[bytes] = None
        self.scale_factor: Optional[float] = None  # Store the scale factor used for this slide
    
    def add_element(self, element: SlideElement):
        """Add an element to the slide."""
        self.elements.append(element)
    
    def add_text(self, text: str, position: Dict[str, float], 
                 style: Dict[str, Any], z_index: int = 0) -> SlideElement:
        """
        Add a text element to the slide.
        
        Args:
            text: Text content
            position: Position dictionary
            style: Style dictionary
            z_index: Z-index for layering
            
        Returns:
            Created SlideElement
        """
        element = SlideElement('text', position, text, style)
        element.z_index = z_index
        self.add_element(element)
        return element
    
    def add_image(self, image_data: bytes, position: Dict[str, float], 
                  image_format: str = 'PNG', z_index: int = 0) -> SlideElement:
        """
        Add an image element to the slide.
        
        Args:
            image_data: Image binary data
            position: Position dictionary
            image_format: Image format (PNG, JPEG, etc.)
            z_index: Z-index for layering
            
        Returns:
            Created SlideElement
        """
        element = SlideElement('image', position, image_data, {'format': image_format})
        element.z_index = z_index
        self.add_element(element)
        return element
    
    def add_shape(self, shape_type: str, position: Dict[str, float], 
                  style: Dict[str, Any], z_index: int = 0) -> SlideElement:
        """
        Add a shape element to the slide.
        
        Args:
            shape_type: Type of shape ('rectangle', 'circle', 'line', etc.)
            position: Position dictionary
            style: Style dictionary (fill color, stroke, etc.)
            z_index: Z-index for layering
            
        Returns:
            Created SlideElement
        """
        element = SlideElement('shape', position, shape_type, style)
        element.z_index = z_index
        self.add_element(element)
        return element
    
    def add_table(self, table_content: Dict[str, Any], position: Dict[str, float], 
                  z_index: int = 0) -> SlideElement:
        """
        Add a table element to the slide.
        
        Args:
            table_content: Table content dictionary with 'grid', 'rows', 'cols'
            position: Position dictionary
            z_index: Z-index for layering
            
        Returns:
            Created SlideElement
        """
        element = SlideElement('table', position, table_content, {})
        element.z_index = z_index
        self.add_element(element)
        return element
    
    def set_title(self, title: str):
        """Set the slide title."""
        self.title = title
    
    def set_background(self, color: str = None, image_data: bytes = None):
        """
        Set the slide background.
        
        Args:
            color: Background color (hex string)
            image_data: Background image data
        """
        if color:
            self.background_color = color
        if image_data:
            self.background_image = image_data
    
    def sort_elements(self):
        """Sort elements by z-index for proper layering."""
        self.elements.sort(key=lambda e: e.z_index)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert slide model to dictionary representation."""
        return {
            'slide_number': self.slide_number,
            'width': self.width,
            'height': self.height,
            'title': self.title,
            'background_color': self.background_color,
            'background_image': self.background_image is not None,
            'elements': [elem.to_dict() for elem in self.elements]
        }
    
    def __repr__(self) -> str:
        return f"SlideModel(slide={self.slide_number}, elements={len(self.elements)})"
