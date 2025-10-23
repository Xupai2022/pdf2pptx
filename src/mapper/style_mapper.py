"""
Style Mapper - Maps PDF styles to PowerPoint styles
"""

import logging
from typing import Dict, Any
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from .font_mapper import FontMapper

logger = logging.getLogger(__name__)


class StyleMapper:
    """
    Maps PDF visual styles to PowerPoint attributes.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Style Mapper.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.font_mapper = FontMapper(config)
        self.preserve_colors = config.get('preserve_colors', True)
        self.default_font_size = config.get('default_font_size', 18)
        self.title_font_size = config.get('title_font_size', 32)
    
    def apply_text_style(self, text_frame, style: Dict[str, Any]):
        """
        Apply text style to a PowerPoint text frame.
        
        Args:
            text_frame: PowerPoint text frame object
            style: Style dictionary
        """
        if not text_frame or not text_frame.paragraphs:
            return
        
        paragraph = text_frame.paragraphs[0]
        
        # Font name
        font_name = style.get('font_name', '')
        mapped_font = self.font_mapper.map_font(font_name)
        
        # Font size
        font_size = style.get('font_size', self.default_font_size)
        
        # Color
        color = style.get('color', '#000000')
        rgb = self.hex_to_rgb(color)
        
        # Bold and italic
        is_bold = style.get('bold', False)
        is_italic = style.get('italic', False)
        
        # Apply to all runs in paragraph
        for run in paragraph.runs:
            run.font.name = mapped_font
            run.font.size = Pt(font_size)
            
            if self.preserve_colors:
                run.font.color.rgb = RGBColor(*rgb)
            
            run.font.bold = is_bold
            run.font.italic = is_italic
    
    def apply_shape_style(self, shape, style: Dict[str, Any]):
        """
        Apply style to a PowerPoint shape.
        
        Args:
            shape: PowerPoint shape object
            style: Style dictionary
        """
        # Fill color
        fill_color = style.get('fill_color')
        if fill_color and self.preserve_colors:
            rgb = self.hex_to_rgb(fill_color)
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(*rgb)
        else:
            shape.fill.background()
        
        # Stroke/line color
        stroke_color = style.get('stroke_color')
        stroke_width = style.get('stroke_width', 1)
        
        if stroke_color and self.preserve_colors:
            rgb = self.hex_to_rgb(stroke_color)
            shape.line.color.rgb = RGBColor(*rgb)
            shape.line.width = Pt(stroke_width)
        else:
            # No line
            shape.line.fill.background()
    
    def hex_to_rgb(self, hex_color: str) -> tuple:
        """
        Convert hex color to RGB tuple.
        
        Args:
            hex_color: Hex color string (e.g., '#FF0000')
            
        Returns:
            RGB tuple (r, g, b)
        """
        if not hex_color or not isinstance(hex_color, str):
            return (0, 0, 0)
        
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')
        
        try:
            # Convert hex to RGB
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b)
            elif len(hex_color) == 3:
                r = int(hex_color[0] * 2, 16)
                g = int(hex_color[1] * 2, 16)
                b = int(hex_color[2] * 2, 16)
                return (r, g, b)
        except ValueError:
            logger.warning(f"Invalid hex color: {hex_color}")
        
        return (0, 0, 0)
    
    def normalize_font_size(self, pdf_font_size: float, is_title: bool = False) -> float:
        """
        Normalize PDF font size to appropriate PowerPoint size.
        
        Args:
            pdf_font_size: Original PDF font size
            is_title: Whether this is a title text
            
        Returns:
            Normalized font size in points
        """
        if is_title:
            # Titles should be larger
            return max(self.title_font_size, pdf_font_size * 0.75)
        
        # Regular text
        if pdf_font_size < 10:
            return 10
        elif pdf_font_size > 36:
            return 36
        
        return pdf_font_size
