"""
Icon Font Detector - Detects and converts icon fonts to images

This module identifies icon fonts (Font Awesome, Material Icons, etc.) in PDF text
and converts them to high-quality bitmap images for proper rendering in PowerPoint.
"""

import fitz  # PyMuPDF
import logging
from typing import Dict, Any, List, Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import os

logger = logging.getLogger(__name__)


class IconFontDetector:
    """
    Detects icon fonts in PDF and converts them to bitmap images.
    
    Icon fonts are special fonts that use Unicode private use areas to display
    icons/symbols. Common icon fonts include:
    - Font Awesome (FontAwesome, FontAwesome6Free-Solid, etc.)
    - Material Icons (MaterialIcons, Material-Design-Icons, etc.)
    - Ionicons
    - Glyphicons
    """
    
    # Known icon font name patterns
    ICON_FONT_PATTERNS = [
        'FontAwesome',
        'Material',
        'Ionicons',
        'Glyphicons',
        'IcoFont',
        'Feather',
        'IconFont',
        'iconfont',
        'BookshelfSymbol',  # Microsoft symbol fonts
        'Webdings',
        'Wingdings'
    ]
    
    # Unicode Private Use Area ranges for icon fonts
    # These ranges are commonly used by icon fonts like Font Awesome
    PRIVATE_USE_RANGES = [
        (0xE000, 0xF8FF),   # Private Use Area
        (0xF0000, 0xFFFFF), # Supplementary Private Use Area-A
        (0x100000, 0x10FFFF) # Supplementary Private Use Area-B
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Icon Font Detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        # DPI for rendering icons (higher = better quality)
        self.icon_render_dpi = config.get('icon_render_dpi', 600)
        # Whether to enable icon font detection
        self.enable_icon_detection = config.get('enable_icon_detection', True)
    
    def is_private_use_char(self, char: str) -> bool:
        """
        Check if a character is in Unicode Private Use Area.
        
        Args:
            char: Single character string
            
        Returns:
            True if character is in private use area
        """
        if not char:
            return False
        
        code = ord(char)
        for start, end in self.PRIVATE_USE_RANGES:
            if start <= code <= end:
                return True
        
        # Also check for replacement character (often used for missing glyphs)
        if code == 0xFFFD or code == 0xFFFF:
            return True
        
        return False
    
    def is_icon_font(self, font_name: str) -> bool:
        """
        Check if a font name is an icon font.
        
        Args:
            font_name: Font name from PDF
            
        Returns:
            True if it's an icon font
        """
        if not font_name:
            return False
        
        # Check against known patterns
        for pattern in self.ICON_FONT_PATTERNS:
            if pattern in font_name:
                return True
        
        return False
    
    def contains_icon_chars(self, text: str) -> bool:
        """
        Check if text contains icon characters (private use area).
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains icon characters
        """
        return any(self.is_private_use_char(char) for char in text)
    
    def detect_icon_in_text_element(self, element: Dict[str, Any]) -> bool:
        """
        Check if a text element contains an icon font or icon characters.
        
        Args:
            element: Text element dictionary with 'font_name' and 'content' keys
            
        Returns:
            True if element contains icon font or icon characters
        """
        font_name = element.get('font_name', '')
        content = element.get('content', '')
        
        # Check if font is an icon font
        if self.is_icon_font(font_name):
            return True
        
        # Check if content contains private use area characters
        if self.contains_icon_chars(content):
            return True
        
        return False
    
    def convert_icon_to_image(
        self, 
        page: fitz.Page, 
        bbox: tuple, 
        char: str, 
        color: int, 
        size: float
    ) -> Optional[bytes]:
        """
        Convert an icon character to a high-quality bitmap image by rendering
        the PDF region containing the icon.
        
        Args:
            page: PyMuPDF page object
            bbox: Bounding box of the icon (x0, y0, x1, y1)
            char: Icon character (Unicode)
            color: Text color as integer
            size: Font size in points
            
        Returns:
            Image bytes (PNG format) or None if failed
        """
        try:
            # Expand bbox slightly to ensure complete icon capture
            x0, y0, x1, y1 = bbox
            padding = size * 0.15  # 15% padding
            expanded_bbox = fitz.Rect(
                x0 - padding,
                y0 - padding,
                x1 + padding,
                y1 + padding
            )
            
            # Calculate zoom factor based on desired DPI
            # Standard PDF resolution is 72 DPI
            zoom_factor = self.icon_render_dpi / 72.0
            
            # Create transformation matrix
            matrix = fitz.Matrix(zoom_factor, zoom_factor)
            
            # Render the icon region as a pixmap
            pixmap = page.get_pixmap(
                matrix=matrix,
                clip=expanded_bbox,
                alpha=False  # No transparency needed
            )
            
            # Convert to PNG bytes
            img_bytes = pixmap.tobytes("png")
            
            logger.debug(
                f"Rendered icon '{hex(ord(char))}' at ({x0:.1f}, {y0:.1f}) "
                f"to {pixmap.width}x{pixmap.height}px image"
            )
            
            return img_bytes
            
        except Exception as e:
            logger.warning(f"Failed to convert icon to image: {e}")
            return None
    
    def extract_icons_from_page(
        self, 
        page: fitz.Page, 
        page_num: int
    ) -> List[Dict[str, Any]]:
        """
        Extract all icon font elements from a page and convert them to images.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)
            
        Returns:
            List of image element dictionaries for icons
        """
        if not self.enable_icon_detection:
            return []
        
        icon_images = []
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks
                continue
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font_name = span.get("font", "")
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    text = span.get("text", "")
                    color = span.get("color", 0)
                    size = span.get("size", 12)
                    
                    if not text:
                        continue
                    
                    # Check if this is an icon font OR contains icon characters
                    is_icon = self.is_icon_font(font_name) or self.contains_icon_chars(text)
                    
                    if not is_icon:
                        continue
                    
                    # Convert icon to image
                    img_bytes = self.convert_icon_to_image(
                        page, bbox, text, color, size
                    )
                    
                    if img_bytes:
                        # Get image dimensions
                        try:
                            pil_image = Image.open(BytesIO(img_bytes))
                            width_px = pil_image.width
                            height_px = pil_image.height
                        except:
                            width_px = int((bbox[2] - bbox[0]) * 4)
                            height_px = int((bbox[3] - bbox[1]) * 4)
                        
                        # Create image element
                        icon_element = {
                            'type': 'image',
                            'image_data': img_bytes,
                            'image_format': 'png',
                            'width_px': width_px,
                            'height_px': height_px,
                            'x': bbox[0],
                            'y': bbox[1],
                            'x2': bbox[2],
                            'y2': bbox[3],
                            'width': bbox[2] - bbox[0],
                            'height': bbox[3] - bbox[1],
                            'image_id': f"page{page_num}_icon_{len(icon_images)}",
                            'is_icon': True,
                            'icon_font': font_name,
                            'icon_char': text,
                            'icon_unicode': hex(ord(text))
                        }
                        
                        icon_images.append(icon_element)
                        
                        logger.info(
                            f"Converted icon '{hex(ord(text))}' from {font_name} "
                            f"at ({bbox[0]:.1f}, {bbox[1]:.1f}) to image"
                        )
        
        return icon_images
    
    def get_icon_text_indices(self, text_elements: List[Dict[str, Any]]) -> set:
        """
        Get indices of text elements that are icons (to be excluded from text rendering).
        
        Args:
            text_elements: List of text elements
            
        Returns:
            Set of indices that are icons
        """
        icon_indices = set()
        
        for i, element in enumerate(text_elements):
            if self.detect_icon_in_text_element(element):
                icon_indices.add(i)
        
        return icon_indices
