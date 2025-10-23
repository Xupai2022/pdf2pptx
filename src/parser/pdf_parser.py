"""
PDF Parser - Main parser class for extracting content from PDF files
"""

import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
import io
from PIL import Image

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Main PDF parser that extracts text, images, and layout information from PDF files.
    Uses PyMuPDF (fitz) for high-precision extraction.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PDF Parser with configuration.
        
        Args:
            config: Configuration dictionary containing parser settings
        """
        self.config = config
        self.dpi = config.get('dpi', 300)
        self.extract_images = config.get('extract_images', True)
        self.image_format = config.get('image_format', 'PNG')
        self.min_text_size = config.get('min_text_size', 6)
        self.max_text_size = config.get('max_text_size', 72)
        self.doc = None
        
    def open(self, pdf_path: str) -> bool:
        """
        Open a PDF file for parsing.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.doc = fitz.open(pdf_path)
            logger.info(f"Successfully opened PDF: {pdf_path}")
            logger.info(f"Total pages: {len(self.doc)}")
            return True
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path}: {e}")
            return False
    
    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None
    
    def get_page_count(self) -> int:
        """Get the total number of pages in the PDF."""
        return len(self.doc) if self.doc else 0
    
    def get_page_size(self, page_num: int) -> Tuple[float, float]:
        """
        Get the size of a specific page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            Tuple of (width, height) in points
        """
        if not self.doc or page_num >= len(self.doc):
            return (0, 0)
        
        page = self.doc[page_num]
        rect = page.rect
        return (rect.width, rect.height)
    
    def extract_page_elements(self, page_num: int) -> Dict[str, Any]:
        """
        Extract all elements from a specific page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            Dictionary containing page information and extracted elements
        """
        if not self.doc or page_num >= len(self.doc):
            logger.error(f"Invalid page number: {page_num}")
            return {}
        
        page = self.doc[page_num]
        rect = page.rect
        
        page_data = {
            'page_num': page_num,
            'width': rect.width,
            'height': rect.height,
            'elements': []
        }
        
        # Extract text blocks
        text_elements = self._extract_text_blocks(page)
        page_data['elements'].extend(text_elements)
        
        # Extract images
        if self.extract_images:
            image_elements = self._extract_images(page, page_num)
            page_data['elements'].extend(image_elements)
        
        # Extract shapes/drawings
        drawing_elements = self._extract_drawings(page)
        page_data['elements'].extend(drawing_elements)
        
        logger.info(f"Page {page_num}: Extracted {len(page_data['elements'])} elements")
        
        return page_data
    
    def _extract_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Extract text blocks with detailed formatting information.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of text element dictionaries
        """
        text_elements = []
        
        # Use dict format for detailed text information
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        # Filter by font size
                        font_size = span.get("size", 0)
                        if font_size < self.min_text_size or font_size > self.max_text_size:
                            continue
                        
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text = span.get("text", "").strip()
                        
                        if not text:
                            continue
                        
                        element = {
                            'type': 'text',
                            'content': text,
                            'x': bbox[0],
                            'y': bbox[1],
                            'x2': bbox[2],
                            'y2': bbox[3],
                            'width': bbox[2] - bbox[0],
                            'height': bbox[3] - bbox[1],
                            'font_name': span.get("font", ""),
                            'font_size': font_size,
                            'color': self._rgb_to_hex(span.get("color", 0)),
                            'flags': span.get("flags", 0),  # bold, italic, etc.
                            'is_bold': bool(span.get("flags", 0) & 2**4),
                            'is_italic': bool(span.get("flags", 0) & 2**1)
                        }
                        
                        text_elements.append(element)
        
        return text_elements
    
    def _extract_images(self, page: fitz.Page, page_num: int) -> List[Dict[str, Any]]:
        """
        Extract images from the page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number for naming
            
        Returns:
            List of image element dictionaries
        """
        image_elements = []
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = self.doc.extract_image(xref)
                
                if not base_image:
                    continue
                
                # Get image data
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Convert to PIL Image for processing
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                # Get image position on page
                image_rects = page.get_image_rects(xref)
                
                if image_rects:
                    rect = image_rects[0]  # Use first occurrence
                    
                    element = {
                        'type': 'image',
                        'image_data': image_bytes,
                        'image_format': image_ext,
                        'width_px': pil_image.width,
                        'height_px': pil_image.height,
                        'x': rect.x0,
                        'y': rect.y0,
                        'x2': rect.x1,
                        'y2': rect.y1,
                        'width': rect.width,
                        'height': rect.height,
                        'image_id': f"page{page_num}_img{img_index}"
                    }
                    
                    image_elements.append(element)
                    
            except Exception as e:
                logger.warning(f"Failed to extract image {img_index} on page {page_num}: {e}")
        
        return image_elements
    
    def _extract_drawings(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Extract vector drawings and shapes from the page.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of drawing element dictionaries
        """
        drawing_elements = []
        
        try:
            # Get drawing paths
            drawings = page.get_drawings()
            
            for drawing in drawings:
                rect = drawing.get("rect")
                if not rect:
                    continue
                
                element = {
                    'type': 'shape',
                    'shape_type': drawing.get("type", "path"),
                    'x': rect.x0,
                    'y': rect.y0,
                    'x2': rect.x1,
                    'y2': rect.y1,
                    'width': rect.width,
                    'height': rect.height,
                    'fill_color': self._rgb_to_hex(drawing.get("fill", None)),
                    'stroke_color': self._rgb_to_hex(drawing.get("color", None)),
                    'stroke_width': drawing.get("width", 1)
                }
                
                drawing_elements.append(element)
                
        except Exception as e:
            logger.warning(f"Failed to extract drawings: {e}")
        
        return drawing_elements
    
    def _rgb_to_hex(self, color) -> str:
        """
        Convert RGB color to hex format.
        
        Args:
            color: Color value (int or tuple)
            
        Returns:
            Hex color string
        """
        if color is None:
            return "#000000"
        
        if isinstance(color, int):
            # Convert integer to RGB
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            return f"#{r:02X}{g:02X}{b:02X}"
        
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            # Convert RGB tuple/list to hex
            r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            return f"#{r:02X}{g:02X}{b:02X}"
        
        return "#000000"
    
    def extract_all_pages(self) -> List[Dict[str, Any]]:
        """
        Extract elements from all pages in the PDF.
        
        Returns:
            List of page data dictionaries
        """
        if not self.doc:
            logger.error("No PDF document opened")
            return []
        
        all_pages = []
        page_count = len(self.doc)
        
        for page_num in range(page_count):
            logger.info(f"Processing page {page_num + 1}/{page_count}")
            page_data = self.extract_page_elements(page_num)
            all_pages.append(page_data)
        
        return all_pages
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
