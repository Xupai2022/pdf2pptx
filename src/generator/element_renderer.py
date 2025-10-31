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
        
        # Store original for comparison
        original_content = content
        
        # Clean content - remove ONLY control characters that cause XML issues
        # Map private use area characters and non-characters to their standard Unicode equivalents
        # These are often used in PDFs for symbol fonts but aren't XML-compatible
        if isinstance(content, str):
            import re
            
            # Map common private use area characters to standard Unicode
            # Based on common symbol font mappings (Wingdings, Webdings, Font Awesome, etc.)
            # Font Awesome uses U+F000-U+F2FF range for icon glyphs
            symbol_map = {
                # Font Awesome icons (U+F000-U+F2FF range)
                '\uf002': '🔍',  # search
                '\uf007': '👤',  # user
                '\uf013': '⚙',  # cog / settings
                '\uf015': '🏠',  # home
                '\uf019': '⬇',  # download
                '\uf01c': '📁',  # folder
                '\uf023': '🔒',  # lock
                '\uf024': '$',  # dollar
                '\uf044': '$',  # dollar alternate
                '\uf055': '➕',  # plus-circle
                '\uf058': '✓',  # check-circle
                '\uf059': '❓',  # question-circle  
                '\uf05a': 'ℹ',  # info-circle
                '\uf05e': '🚫',  # ban / prohibited
                '\uf06a': '●',  # circle / bullet
                '\uf06e': '👁',  # eye
                '\uf071': '⚠',  # exclamation-triangle / warning
                '\uf073': '📅',  # calendar
                '\uf084': '🔑',  # key
                '\uf0c9': '☰',  # bars / menu
                '\uf0f6': '➕',  # plus-square
                '\uf146': '➖',  # minus-square
                '\uf188': '🐛',  # bug
                '\uf3ed': '📹',  # video camera
                # Wingdings / Webdings
                '\uf0a7': '■',  # Black square
                '\uf0b7': '●',  # Bullet
                '\uf0fc': '☁',  # Cloud
                # Non-characters - remove (can't be rendered in PowerPoint XML)
                '\uffff': '',   # Non-character, typically used as placeholder
                '\ufffe': '',   # Non-character
            }
            
            # Apply symbol mappings
            for old_char, new_char in symbol_map.items():
                content = content.replace(old_char, new_char)
            
            # Remove NULL bytes and problematic control characters
            # Keep normal printable characters, whitespace, and CJK characters
            # Remove only C0 control characters (0x00-0x1F) except tab, newline, carriage return
            content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', content)
            # Remove C1 control characters (0x80-0x9F)
            content = re.sub(r'[\x80-\x9F]', '', content)
            # Remove Unicode non-characters (U+FDD0 - U+FDEF, U+FFFE, U+FFFF) after mapping
            content = re.sub(r'[\uFDD0-\uFDEF\uFFFE\uFFFF]', '', content)
            
            # For remaining unmapped private use area characters (U+E000-U+F8FF),
            # replace with a generic placeholder symbol (●) so content isn't lost entirely
            # This handles custom icon fonts that we haven't mapped yet
            def replace_pua(match):
                # Replace each PUA character with a bullet point as a visible placeholder
                return '●' * len(match.group(0))
            
            content = re.sub(r'[\uE000-\uF8FF]+', replace_pua, content)
        
        if not content or not content.strip():
            if original_content and original_content.strip():
                logger.warning(f"Text cleaned away: original had {len(original_content)} chars: {repr(original_content[:50])}")
            return None
        
        # Create text box
        left = Inches(position['x'])
        top = Inches(position['y'])
        width = Inches(position['width'])
        height = Inches(position['height'])
        
        # Calculate estimated text width to prevent wrapping
        # Average character width is roughly 0.6 of font size
        font_size = style.get('font_size', 18)
        char_count = len(content.strip())
        # Estimate required width in points (1 inch = 72 points)
        estimated_width_pt = char_count * font_size * 0.6
        estimated_width_inches = estimated_width_pt / 72.0
        
        # Use larger of provided width or estimated width (with 20% padding)
        min_width = max(Inches(0.3), estimated_width_inches * 1.2)
        if width < min_width:
            width = min_width
        
        # Ensure minimum height
        if height < Inches(0.15):
            height = Inches(0.2)
        
        try:
            textbox = slide.shapes.add_textbox(left, top, width, height)
            text_frame = textbox.text_frame
            text_frame.text = content
            
            # Apply style
            self.style_mapper.apply_text_style(text_frame, style)
            
            # Text frame properties
            # Disable word wrap to prevent forced line breaks
            text_frame.word_wrap = False
            
            return textbox
            
        except Exception as e:
            logger.error(f"Failed to render text element: {e}")
            logger.error(f"Content length: {len(content)}, first 50 chars: {repr(content[:50])}")
            # Try to identify problematic characters
            for i, c in enumerate(content):
                code = ord(c)
                if code < 32 and c not in '\t\n\r':
                    logger.error(f"  Found control char at pos {i}: U+{code:04X} ({repr(c)})")
                elif 0x80 <= code <= 0x9F:
                    logger.error(f"  Found C1 control at pos {i}: U+{code:04X} ({repr(c)})")
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
        
        # Ensure reasonable dimensions (keep original size for small icons)
        if width < Inches(0.05):
            width = Inches(0.1)
        if height < Inches(0.05):
            height = Inches(0.1)
        
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
        
        # Ensure minimum dimensions (but allow thin borders)
        # Check if it's a border (thin vertical or horizontal shape)
        is_vertical_border = (position['height'] > position['width'] and position['width'] < 0.1)
        is_horizontal_border = (position['width'] > position['height'] and position['height'] < 0.1)
        is_border = is_vertical_border or is_horizontal_border
        
        if not is_border:
            # Apply minimum size only to non-border shapes
            if width < Inches(0.1):
                width = Inches(0.5)
            if height < Inches(0.1):
                height = Inches(0.5)
        
        try:
            # Special handling for lines - use connectors for proper line rendering
            if shape_type.lower() in ['line', 'triangle']:
                # For lines and triangles, we need to use connectors or stroke-only rectangles
                # Check if this has stroke but no fill
                has_stroke = style.get('stroke_color') is not None
                has_fill = style.get('fill_color') is not None
                
                if shape_type.lower() == 'line' and has_stroke and not has_fill:
                    # This is a true line - render as a connector
                    from pptx.enum.shapes import MSO_CONNECTOR
                    
                    # Calculate start and end points
                    # For horizontal lines: left to right
                    # For vertical lines: top to bottom
                    # For diagonal lines: top-left to bottom-right
                    begin_x = left
                    begin_y = top
                    end_x = left + width
                    end_y = top + height
                    
                    # Add a straight connector (line)
                    connector = slide.shapes.add_connector(
                        MSO_CONNECTOR.STRAIGHT,
                        begin_x, begin_y, end_x, end_y
                    )
                    
                    # Apply line style
                    if hasattr(connector, 'line'):
                        line = connector.line
                        # Set line color
                        if style.get('stroke_color'):
                            from pptx.util import Pt
                            from pptx.dml.color import RGBColor
                            hex_color = style['stroke_color']
                            if hex_color.startswith('#'):
                                rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
                                line.color.rgb = RGBColor(*rgb)
                        
                        # Set line width
                        stroke_width = style.get('stroke_width', 1)
                        line.width = Pt(stroke_width)
                    
                    logger.debug(f"Rendered line from ({begin_x}, {begin_y}) to ({end_x}, {end_y})")
                    return connector
            
            # Map shape type to MSO_SHAPE
            shape_map = {
                'rectangle': MSO_SHAPE.RECTANGLE,
                'rect': MSO_SHAPE.RECTANGLE,
                'circle': MSO_SHAPE.OVAL,
                'oval': MSO_SHAPE.OVAL,
                'ellipse': MSO_SHAPE.OVAL,
                'line': MSO_SHAPE.RECTANGLE,  # Fallback for lines with fill
                'triangle': MSO_SHAPE.RECTANGLE,  # Triangles as rectangles for now
                'path': MSO_SHAPE.RECTANGLE,
                'f': MSO_SHAPE.RECTANGLE,  # Fill path - default to rectangle
                's': MSO_SHAPE.RECTANGLE   # Stroke path - default to rectangle
            }
            
            # Override with OVAL if marked as a ring or if aspect ratio suggests circle
            aspect_ratio = position['width'] / position['height'] if position['height'] > 0 else 0
            is_circular = 0.8 <= aspect_ratio <= 1.2  # Nearly square suggests circular
            
            # Check if this is a merged ring shape
            is_ring = style.get('is_ring', False)
            
            if is_ring:
                # Ring shapes must be rendered as OVAL (circle) with stroke
                mso_shape = MSO_SHAPE.OVAL
                logger.debug(f"Rendering ring shape at ({position['x']:.1f}, {position['y']:.1f})")
            elif is_circular and shape_type.lower() == 'oval':
                mso_shape = MSO_SHAPE.OVAL
            else:
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
