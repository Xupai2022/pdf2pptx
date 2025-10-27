"""
PDF Parser - Main parser class for extracting content from PDF files
"""

import fitz  # PyMuPDF
import logging
import re
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
        
        # Extract ExtGState opacity mapping for this page
        opacity_map = self._extract_opacity_map(page)
        
        # Extract text blocks
        text_elements = self._extract_text_blocks(page)
        page_data['elements'].extend(text_elements)
        
        # Extract images
        if self.extract_images:
            image_elements = self._extract_images(page, page_num)
            page_data['elements'].extend(image_elements)
        
        # Extract shapes/drawings with opacity information
        drawing_elements = self._extract_drawings(page, opacity_map)
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
    
    def _extract_opacity_map(self, page: fitz.Page) -> Dict[str, float]:
        """
        Extract ExtGState opacity mapping from page resources.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            Dictionary mapping graphics state names to opacity values
        """
        opacity_map = {}
        
        try:
            # Get page object definition
            page_dict = self.doc.xref_object(page.xref, compressed=False)
            
            # Find ExtGState resources
            extgstate_pattern = r'/ExtGState\s*<<([^>]+)>>'
            match = re.search(extgstate_pattern, page_dict, re.DOTALL)
            
            if match:
                extgstate_content = match.group(1)
                # Extract graphics state references with flexible naming
                # Matches: /GS1, /G3, /a1, /Alpha2, etc.
                # Pattern: /[Name][OptionalNumber] [xref] 0 R
                gs_refs = re.findall(r'/([A-Za-z]+\d*)\s+(\d+)\s+\d+\s+R', extgstate_content)
                
                for gs_name, xref in gs_refs:
                    try:
                        # Get the graphics state object
                        gs_obj = self.doc.xref_object(int(xref), compressed=False)
                        
                        # Extract fill opacity (ca) and stroke opacity (CA)
                        ca_match = re.search(r'/ca\s+([\d.]+)', gs_obj)
                        if ca_match:
                            opacity = float(ca_match.group(1))
                            opacity_map[gs_name] = opacity
                            logger.debug(f"Extracted opacity: /{gs_name} = {opacity}")
                    except Exception as e:
                        logger.debug(f"Could not read GS object /{gs_name}: {e}")
            
        except Exception as e:
            logger.debug(f"Could not extract opacity map: {e}")
        
        return opacity_map
    
    def _extract_drawings(self, page: fitz.Page, opacity_map: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Extract vector drawings and shapes from the page with opacity information.
        
        Args:
            page: PyMuPDF page object
            opacity_map: Mapping of graphics state names to opacity values
            
        Returns:
            List of drawing element dictionaries
        """
        drawing_elements = []
        
        if opacity_map is None:
            opacity_map = {}
        
        try:
            # Get drawing paths
            drawings = page.get_drawings()
            
            # Parse content stream to build a position-based opacity map
            opacity_by_position = self._parse_content_stream_opacity_enhanced(page, opacity_map)
            
            for idx, drawing in enumerate(drawings):
                rect = drawing.get("rect")
                if not rect:
                    continue
                
                # PyMuPDF provides fill_opacity directly in the drawing dict!
                # Use it if available, otherwise try to match from content stream
                fill_opacity = drawing.get("fill_opacity", None)
                if fill_opacity is None:
                    fill_opacity = self._find_opacity_for_drawing(rect, opacity_by_position)
                
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
                    'fill_opacity': fill_opacity,
                    'stroke_color': self._rgb_to_hex(drawing.get("color", None)),
                    'stroke_width': drawing.get("width", 1)
                }
                
                drawing_elements.append(element)
            
            # Deduplicate overlapping shapes (border artifacts from HTML-to-PDF conversion)
            drawing_elements = self._deduplicate_overlapping_shapes(drawing_elements)
                
        except Exception as e:
            logger.warning(f"Failed to extract drawings: {e}")
        
        return drawing_elements
    
    def _parse_content_stream_opacity(self, page: fitz.Page, opacity_map: Dict[str, float]) -> List[float]:
        """
        Parse content stream to extract opacity for each drawing operation.
        
        Args:
            page: PyMuPDF page object
            opacity_map: Mapping of graphics state names to opacity values
            
        Returns:
            List of opacity values in drawing order
        """
        opacity_sequence = []
        current_opacity = 1.0
        
        try:
            # Get content stream
            xref = page.get_contents()[0]
            content_stream = self.doc.xref_stream(xref).decode('latin-1')
            
            # Split by whitespace to get tokens
            # PDF content stream is a sequence of operators and operands
            tokens = content_stream.split()
            
            i = 0
            while i < len(tokens):
                token = tokens[i]
                
                # Check for graphics state change: /[Name] gs (flexible pattern)
                # Matches: /GS1 gs, /G3 gs, /a1 gs, /Alpha gs, etc.
                if token.startswith('/') and i + 1 < len(tokens) and tokens[i + 1] == 'gs':
                    gs_match = re.match(r'/([A-Za-z]+\d*)', token)
                    if gs_match:
                        gs_name = gs_match.group(1)
                        current_opacity = opacity_map.get(gs_name, 1.0)
                        logger.debug(f"Graphics state changed to /{gs_name}, opacity = {current_opacity}")
                    i += 2
                    continue
                
                # Check for fill operations: 'f' or 'f*'
                # These indicate a shape has been filled
                if token in ['f', 'f*']:
                    opacity_sequence.append(current_opacity)
                    logger.debug(f"Fill operation #{len(opacity_sequence)}, opacity = {current_opacity}")
                
                i += 1
            
            logger.debug(f"Extracted {len(opacity_sequence)} opacity values from content stream")
            
        except Exception as e:
            logger.debug(f"Could not parse content stream for opacity: {e}")
        
        return opacity_sequence
    
    def _parse_content_stream_opacity_enhanced(self, page: fitz.Page, opacity_map: Dict[str, float]) -> Dict[tuple, float]:
        """
        Parse content stream to create a sequence of opacity values for filled rectangles.
        
        This method extracts the opacity sequence for all fill operations in order,
        which will be matched with get_drawings() output by analyzing overlapping patterns.
        
        Args:
            page: PyMuPDF page object
            opacity_map: Mapping of graphics state names to opacity values
            
        Returns:
            Dictionary mapping drawing characteristics to opacity values
        """
        opacity_info = {'sequence': [], 'by_size': {}}
        current_opacity = 1.0
        
        try:
            # Get content stream
            xref = page.get_contents()[0]
            content_stream = self.doc.xref_stream(xref).decode('latin-1')
            
            # Split by whitespace to get tokens
            tokens = content_stream.split()
            
            # Track recent rectangles before fill
            recent_rects = []
            
            i = 0
            while i < len(tokens):
                token = tokens[i]
                
                # Check for graphics state change: /[Name] gs
                if token.startswith('/') and i + 1 < len(tokens) and tokens[i + 1] == 'gs':
                    gs_match = re.match(r'/([A-Za-z]+\d*)', token)
                    if gs_match:
                        gs_name = gs_match.group(1)
                        current_opacity = opacity_map.get(gs_name, 1.0)
                    i += 2
                    continue
                
                # Track rectangle construction: x y width height re
                if token == 're' and i >= 4:
                    try:
                        rect_h = float(tokens[i - 1])
                        rect_w = float(tokens[i - 2])
                        rect_y = float(tokens[i - 3])
                        rect_x = float(tokens[i - 4])
                        recent_rects.append((rect_x, rect_y, abs(rect_w), abs(rect_h)))
                    except (ValueError, IndexError):
                        pass
                
                # Check for fill operations: 'f' or 'f*'
                if token in ['f', 'f*']:
                    # Record opacity for this fill operation
                    opacity_info['sequence'].append(current_opacity)
                    
                    # If we have rectangle info, also store by size
                    if recent_rects:
                        # Use the most recent rectangle before this fill
                        rect_x, rect_y, rect_w, rect_h = recent_rects[-1]
                        # Store by size key for matching
                        size_key = (round(rect_w, 0), round(rect_h, 0))
                        if size_key not in opacity_info['by_size']:
                            opacity_info['by_size'][size_key] = []
                        opacity_info['by_size'][size_key].append(current_opacity)
                        logger.debug(f"Fill op with opacity {current_opacity}, size {size_key}")
                    
                    # Clear rectangle buffer after fill
                    recent_rects = []
                
                i += 1
            
            logger.debug(f"Extracted {len(opacity_info['sequence'])} opacity values in sequence")
            logger.debug(f"Size-based groups: {len(opacity_info['by_size'])}")
            
        except Exception as e:
            logger.debug(f"Could not parse enhanced opacity info: {e}")
        
        return opacity_info
    
    def _find_opacity_for_drawing(self, rect, opacity_info: Dict) -> float:
        """
        Find the opacity value for a drawing using multiple strategies.
        
        Strategy:
        1. Match by size if the shape has a unique size in the opacity map
        2. Use the corresponding index in the opacity sequence
        3. Default to 1.0 (fully opaque)
        
        Args:
            rect: PyMuPDF Rect object
            opacity_info: Dictionary with opacity sequence and size-based mapping
            
        Returns:
            Opacity value (default 1.0 if not found)
        """
        # Try matching by size for non-standard rectangles
        size_key = (round(rect.width, 0), round(rect.height, 0))
        
        if 'by_size' in opacity_info and size_key in opacity_info['by_size']:
            opacity_list = opacity_info['by_size'][size_key]
            # If all rectangles of this size have the same opacity, use it
            unique_opacities = list(set(opacity_list))
            if len(unique_opacities) == 1:
                logger.debug(f"Matched by size {size_key} to opacity {unique_opacities[0]}")
                return unique_opacities[0]
            # If there are multiple opacities for this size, pick based on distribution
            # Prefer transparent over opaque (HTML background layers are typically more specific)
            transparent_opacities = [o for o in unique_opacities if o < 0.5]
            if transparent_opacities:
                return min(transparent_opacities)  # Use the most transparent
        
        # Default to fully opaque
        return 1.0
    
    def _deduplicate_overlapping_shapes(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate overlapping shapes that are artifacts from HTML-to-PDF conversion.
        
        When HTML/CSS containers with borders are converted to PDF, they often create
        two nearly identical rectangles:
        - One with transparency (the background)
        - One fully opaque (serving as a visual border)
        
        This method detects and merges such duplicates, keeping only the shape with
        the most specific styling (typically the one with transparency).
        
        Args:
            shapes: List of shape elements
            
        Returns:
            Deduplicated list of shape elements
        """
        if len(shapes) <= 1:
            return shapes
        
        deduplicated = []
        skip_indices = set()
        
        for i, shape1 in enumerate(shapes):
            if i in skip_indices:
                continue
            
            # Look for similar shapes
            found_duplicate = False
            
            for j in range(i + 1, len(shapes)):
                if j in skip_indices:
                    continue
                
                shape2 = shapes[j]
                
                # Check if shapes are nearly identical (overlap detection)
                if self._are_shapes_overlapping(shape1, shape2):
                    # Merge the shapes, preferring the one with transparency
                    merged = self._merge_overlapping_shapes(shape1, shape2)
                    deduplicated.append(merged)
                    skip_indices.add(i)
                    skip_indices.add(j)
                    found_duplicate = True
                    
                    logger.debug(f"Merged overlapping shapes: "
                               f"Shape1 at ({shape1['x']:.1f}, {shape1['y']:.1f}), "
                               f"Shape2 at ({shape2['x']:.1f}, {shape2['y']:.1f}), "
                               f"opacity1={shape1['fill_opacity']:.3f}, "
                               f"opacity2={shape2['fill_opacity']:.3f}")
                    break
            
            if not found_duplicate:
                deduplicated.append(shape1)
        
        return deduplicated
    
    def _are_shapes_overlapping(self, shape1: Dict[str, Any], shape2: Dict[str, Any]) -> bool:
        """
        Check if two shapes are overlapping duplicates (border artifacts).
        
        Shapes are considered duplicates if:
        1. They have the same color
        2. Their positions overlap significantly (within 2pt tolerance)
        3. Their sizes are nearly identical (within 2pt tolerance)
        4. They have different opacity values (one transparent, one opaque)
        5. CRITICAL: The transparent and opaque versions must have VERY different opacity
           (e.g., 0.03 vs 1.0, NOT 0.03 vs 0.08)
        6. NEW: Small positional offsets (<3pt) that create decorative border effects should NOT be merged
        
        Args:
            shape1: First shape element
            shape2: Second shape element
            
        Returns:
            True if shapes are overlapping duplicates
        """
        # Must have same fill color
        if shape1['fill_color'] != shape2['fill_color']:
            return False
        
        # Must have different opacity values (one transparent, one opaque)
        opacity1 = shape1['fill_opacity']
        opacity2 = shape2['fill_opacity']
        
        # Skip if both have same opacity
        if abs(opacity1 - opacity2) < 0.001:
            return False
        
        # CRITICAL FIX: One must be transparent (< 0.5) and one must be FULLY opaque (>= 0.9)
        # This prevents merging shapes with different non-opaque transparency levels
        # e.g., prevents merging 0.03 with 0.08, but allows merging 0.03 with 1.0
        min_opacity = min(opacity1, opacity2)
        max_opacity = max(opacity1, opacity2)
        
        has_transparent = min_opacity < 0.5
        has_fully_opaque = max_opacity >= 0.9  # Changed from > 0.5 to >= 0.9
        
        if not (has_transparent and has_fully_opaque):
            return False
        
        # Calculate position and size differences
        x_diff = abs(shape1['x'] - shape2['x'])
        y_diff = abs(shape1['y'] - shape2['y'])
        width_diff = abs(shape1['width'] - shape2['width'])
        height_diff = abs(shape1['height'] - shape2['height'])
        
        # CRITICAL FIX: Detect decorative border patterns
        # When two shapes have a small offset (0.5-3pt) with matching size difference,
        # this creates an intentional decorative border effect that should NOT be merged.
        # Example: shape1 at x=60 with width=1320, shape2 at x=61.5 with width=1318.5
        # creates a 1.5pt left border effect.
        decorative_offset_threshold = 3.0  # 3pt threshold for decorative borders
        
        # Check if this is a decorative border pattern:
        # - Small X offset (< 3pt) with matching width difference
        # - OR small Y offset (< 3pt) with matching height difference
        is_decorative_x_border = (
            0.5 < x_diff < decorative_offset_threshold and
            abs(x_diff - width_diff) < 0.1  # offset matches size difference
        )
        is_decorative_y_border = (
            0.5 < y_diff < decorative_offset_threshold and
            abs(y_diff - height_diff) < 0.1
        )
        
        if is_decorative_x_border or is_decorative_y_border:
            logger.debug(
                f"Detected decorative border pattern - NOT merging: "
                f"x_diff={x_diff:.2f}, y_diff={y_diff:.2f}, "
                f"width_diff={width_diff:.2f}, height_diff={height_diff:.2f}"
            )
            return False
        
        # Standard overlap detection with 2pt tolerance
        position_tolerance = 2.0
        x_overlap = x_diff <= position_tolerance
        y_overlap = y_diff <= position_tolerance
        
        # Check size similarity (tolerance: 2pt for border width differences)
        size_tolerance = 2.0
        width_similar = width_diff <= size_tolerance
        height_similar = height_diff <= size_tolerance
        
        return x_overlap and y_overlap and width_similar and height_similar
    
    def _merge_overlapping_shapes(self, shape1: Dict[str, Any], shape2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two overlapping shapes, keeping the best attributes.
        
        Strategy:
        - Use the position and size from the transparent shape (more accurate)
        - Use the transparency value from the transparent shape
        - Remove any border (stroke) since it's an artifact
        
        Args:
            shape1: First shape element
            shape2: Second shape element
            
        Returns:
            Merged shape element
        """
        # Identify which shape has transparency
        if shape1['fill_opacity'] < shape2['fill_opacity']:
            transparent_shape = shape1
            opaque_shape = shape2
        else:
            transparent_shape = shape2
            opaque_shape = shape1
        
        # Create merged shape based on transparent one
        merged = transparent_shape.copy()
        
        # Remove any stroke/border (it's an artifact from the opaque shape)
        merged['stroke_color'] = None
        merged['stroke_width'] = 0
        
        return merged
    
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
