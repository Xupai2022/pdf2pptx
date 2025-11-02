"""
PDF Parser - Main parser class for extracting content from PDF files
"""

import fitz  # PyMuPDF
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import io
from PIL import Image
from .border_detector import BorderDetector
from .shape_merger import ShapeMerger
from .chart_detector import ChartDetector
from .text_image_overlap_detector import TextImageOverlapDetector
from .icon_font_detector import IconFontDetector

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
        
        # Initialize border detector, shape merger, chart detector, text overlap detector, and icon detector
        self.border_detector = BorderDetector(config)
        self.shape_merger = ShapeMerger(config)
        self.chart_detector = ChartDetector(config)
        self.text_overlap_detector = TextImageOverlapDetector(overlap_threshold=0.5)
        self.icon_detector = IconFontDetector(config)
        
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
        
        # Extract icon fonts as images BEFORE extracting regular text
        # This prevents icon characters from being rendered as text
        icon_images = self.icon_detector.extract_icons_from_page(page, page_num)
        if icon_images:
            page_data['elements'].extend(icon_images)
            logger.info(f"Page {page_num}: Extracted {len(icon_images)} icon font(s) as images")
        
        # Extract text blocks (icons will be filtered out)
        text_elements = self._extract_text_blocks(page)
        
        # Filter out text elements that are icons
        icon_indices = self.icon_detector.get_icon_text_indices(text_elements)
        filtered_text_elements = [
            elem for i, elem in enumerate(text_elements) if i not in icon_indices
        ]
        page_data['elements'].extend(filtered_text_elements)
        
        if icon_indices:
            logger.info(f"Page {page_num}: Filtered out {len(icon_indices)} icon font text element(s)")
        
        # Extract images (pass text elements for overlap detection)
        if self.extract_images:
            image_elements = self._extract_images(page, page_num, filtered_text_elements)
            page_data['elements'].extend(image_elements)
        
        # Extract shapes/drawings with opacity information
        drawing_elements = self._extract_drawings(page, opacity_map)
        
        # Detect chart regions before adding shapes to elements
        chart_regions = self.chart_detector.detect_chart_regions(page, drawing_elements)
        
        # Convert chart regions to high-resolution images
        chart_shape_ids = set()
        for chart_region in chart_regions:
            # Render chart as image
            chart_bbox = chart_region['bbox']
            image_data = self.chart_detector.render_chart_as_image(page, chart_bbox)
            
            # Create image element to replace the chart shapes
            chart_image_elem = {
                'type': 'image',
                'image_data': image_data,
                'image_format': 'png',
                'width_px': 0,  # Will be determined from image
                'height_px': 0,
                'x': chart_bbox[0],
                'y': chart_bbox[1],
                'x2': chart_bbox[2],
                'y2': chart_bbox[3],
                'width': chart_bbox[2] - chart_bbox[0],
                'height': chart_bbox[3] - chart_bbox[1],
                'image_id': f"page{page_num}_chart_{len(chart_regions)}",
                'is_chart': True
            }
            
            # Get actual image dimensions
            try:
                pil_image = Image.open(io.BytesIO(image_data))
                chart_image_elem['width_px'] = pil_image.width
                chart_image_elem['height_px'] = pil_image.height
            except Exception as e:
                logger.warning(f"Failed to get chart image dimensions: {e}")
            
            page_data['elements'].append(chart_image_elem)
            
            # Mark shapes in this chart region for exclusion
            # Include ALL shapes that are within the chart bbox, not just clustered ones
            chart_bbox = chart_region['bbox']
            for shape in drawing_elements:
                # Check if shape is within chart region bbox
                shape_center_x = (shape['x'] + shape['x2']) / 2
                shape_center_y = (shape['y'] + shape['y2']) / 2
                
                if (chart_bbox[0] <= shape_center_x <= chart_bbox[2] and
                    chart_bbox[1] <= shape_center_y <= chart_bbox[3]):
                    chart_shape_ids.add(id(shape))
        
        # Add only non-chart shapes to elements
        for shape in drawing_elements:
            if id(shape) not in chart_shape_ids:
                page_data['elements'].append(shape)
        
        # Filter out text elements that overlap with chart images
        if chart_regions:
            page_data['elements'] = self.text_overlap_detector.filter_overlapping_texts(page_data['elements'])
        
        logger.info(f"Page {page_num}: Extracted {len(page_data['elements'])} elements ({len(chart_regions)} charts rendered as images)")
        
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
                    # Extract text direction from line
                    # dir field is a tuple (dx, dy) indicating text direction
                    line_dir = line.get("dir", (1.0, 0.0))
                    
                    for span in line.get("spans", []):
                        # Filter by font size
                        font_size = span.get("size", 0)
                        if font_size < self.min_text_size or font_size > self.max_text_size:
                            continue
                        
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text = span.get("text", "").strip()
                        
                        if not text:
                            continue
                        
                        # Calculate rotation angle from direction vector
                        # dir is (dx, dy) - the direction of text baseline
                        # angle = atan2(dy, dx) in radians, convert to degrees
                        import math
                        dx, dy = line_dir
                        rotation_angle = math.degrees(math.atan2(dy, dx))
                        
                        # Normalize angle to [-180, 180] range
                        while rotation_angle > 180:
                            rotation_angle -= 360
                        while rotation_angle < -180:
                            rotation_angle += 360
                        
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
                            'is_italic': bool(span.get("flags", 0) & 2**1),
                            'rotation': rotation_angle,  # Add rotation angle in degrees
                            'text_dir': line_dir  # Store original direction vector for reference
                        }
                        
                        text_elements.append(element)
        
        return text_elements
    
    def _extract_images(self, page: fitz.Page, page_num: int, text_elements: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract images from the page with smart overlap detection for rerendering.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number for naming
            text_elements: Optional list of already-extracted text elements for overlap detection
            
        Returns:
            List of image element dictionaries
        """
        image_elements = []
        image_list = page.get_images(full=True)
        
        # If text_elements not provided, extract them for overlap detection
        if text_elements is None:
            text_elements = []
        
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
                    
                    # Check image quality and determine action
                    quality_status, needs_large_image_enhancement = self._check_image_quality(pil_image, rect)
                    
                    # quality_status: 'good', 'rerender', or 'skip'
                    if quality_status == 'skip':
                        # This is a low-quality rasterized vector graphic that obscures
                        # the underlying clean vector shapes. Skip it entirely.
                        logger.info(f"Skipping low-quality rasterized image at page {page_num}, "
                                  f"position ({rect.x0:.1f}, {rect.y0:.1f}), "
                                  f"allowing underlying vector shapes to show")
                        continue
                    
                    if quality_status == 'rerender' or needs_large_image_enhancement:
                        # Check for text/shape overlaps BEFORE rerendering
                        safe_rect = self._calculate_safe_rerender_bbox(rect, text_elements, page)
                        
                        if safe_rect and (safe_rect.width > 20 and safe_rect.height > 20):
                            # Safe region found and is large enough to rerender
                            logger.info(f"Re-rendering image at page {page_num} with safe bbox "
                                      f"({safe_rect.x0:.1f}, {safe_rect.y0:.1f}, {safe_rect.x1:.1f}, {safe_rect.y1:.1f}), "
                                      f"original bbox ({rect.x0:.1f}, {rect.y0:.1f}, {rect.x1:.1f}, {rect.y1:.1f})")
                            zoom = 4.0  # High resolution
                            matrix = fitz.Matrix(zoom, zoom)
                            region_pix = page.get_pixmap(matrix=matrix, clip=safe_rect, alpha=False)
                            image_bytes = region_pix.tobytes("png")
                            image_ext = "png"
                            
                            # Update PIL image
                            pil_image = Image.open(io.BytesIO(image_bytes))
                            
                            # Use safe_rect as the new rect
                            rect = safe_rect
                        elif quality_status == 'rerender':
                            # For truly corrupted images, we still need to rerender even with overlap
                            logger.warning(f"Re-rendering corrupted image at page {page_num} (has overlaps but required)")
                            zoom = 4.0
                            matrix = fitz.Matrix(zoom, zoom)
                            region_pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
                            image_bytes = region_pix.tobytes("png")
                            image_ext = "png"
                            pil_image = Image.open(io.BytesIO(image_bytes))
                        else:
                            # Large image needs enhancement but has overlaps, use original
                            logger.info(f"Keeping original large image at page {page_num} due to text/shape overlaps")
                    
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
                        'image_id': f"page{page_num}_img{img_index}",
                        'was_rerendered': (quality_status == 'rerender' or needs_large_image_enhancement)
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
            
            # Convert drawings to shape elements
            for idx, drawing in enumerate(drawings):
                rect = drawing.get("rect")
                if not rect:
                    continue
                
                # PyMuPDF provides fill_opacity directly in the drawing dict!
                # Use it if available, otherwise try to match from content stream
                fill_opacity = drawing.get("fill_opacity", None)
                if fill_opacity is None:
                    fill_opacity = self._find_opacity_for_drawing(rect, opacity_by_position)
                
                # Detect actual shape type by analyzing drawing items
                detected_shape_type = self._detect_shape_type(drawing)
                
                # For single-line shapes, extract original start/end points to preserve direction
                # This is critical for diagonal lines where direction matters (/ vs \)
                line_start_x, line_start_y = rect.x0, rect.y0
                line_end_x, line_end_y = rect.x1, rect.y1
                
                if detected_shape_type == 'line':
                    # Extract actual line coordinates from drawing items
                    items = drawing.get('items', [])
                    line_items = [item for item in items if item[0] == 'l']
                    
                    if len(line_items) == 1:
                        # Single line segment - use actual start and end points
                        line_item = line_items[0]
                        start_point = line_item[1]
                        end_point = line_item[2]
                        
                        line_start_x = start_point.x
                        line_start_y = start_point.y
                        line_end_x = end_point.x
                        line_end_y = end_point.y
                        
                        logger.debug(f"Preserved line direction: ({line_start_x:.1f},{line_start_y:.1f}) -> ({line_end_x:.1f},{line_end_y:.1f})")
                
                element = {
                    'type': 'shape',
                    'shape_type': detected_shape_type,
                    'x': line_start_x,
                    'y': line_start_y,
                    'x2': line_end_x,
                    'y2': line_end_y,
                    'width': rect.width,
                    'height': rect.height,
                    'fill_color': self._rgb_to_hex(drawing.get("fill", None)),
                    'fill_opacity': fill_opacity,
                    'stroke_color': self._rgb_to_hex(drawing.get("color", None)),
                    'stroke_width': drawing.get("width", 1)
                }
                
                drawing_elements.append(element)
            
            # CRITICAL: Detect borders BEFORE deduplication
            # Borders are created by pairs of overlapping shapes with small offsets
            # We must detect them before deduplication removes the duplicate shapes
            border_elements = self.border_detector.detect_borders_from_shapes(drawing_elements)
            
            # Merge composite shapes (rings, donuts, etc.) BEFORE deduplication
            # This must happen before deduplication to preserve the overlapping shapes
            drawing_elements = self.shape_merger.merge_shapes(drawing_elements)
            
            # Now deduplicate overlapping shapes (removes border artifacts)
            drawing_elements = self._deduplicate_overlapping_shapes(drawing_elements)
            
            # Add detected borders after deduplication
            if border_elements:
                drawing_elements.extend(border_elements)
                
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
        1. Case A (Opacity-based): They have the same color, overlapping positions, 
           and different opacity values (one transparent, one opaque)
        2. Case B (Stroke+Fill duplication): They have the same stroke color and overlapping positions,
           where one is stroke-only and the other has stroke + black fill
           (This happens when PDF renders a border with two drawing layers)
        
        Args:
            shape1: First shape element
            shape2: Second shape element
            
        Returns:
            True if shapes are overlapping duplicates
        """
        # Check position overlap first (tolerance: 2pt for slight positioning differences)
        position_tolerance = 2.0
        x_overlap = abs(shape1['x'] - shape2['x']) <= position_tolerance
        y_overlap = abs(shape1['y'] - shape2['y']) <= position_tolerance
        
        # Check size similarity (tolerance: 2pt for border width differences)
        size_tolerance = 2.0
        width_similar = abs(shape1['width'] - shape2['width']) <= size_tolerance
        height_similar = abs(shape1['height'] - shape2['height']) <= size_tolerance
        
        # If positions don't overlap, not duplicates
        if not (x_overlap and y_overlap and width_similar and height_similar):
            return False
        
        # Case A: Opacity-based duplication (original logic)
        if shape1['fill_color'] == shape2['fill_color']:
            opacity1 = shape1['fill_opacity']
            opacity2 = shape2['fill_opacity']
            
            # Must have different opacity values
            if abs(opacity1 - opacity2) >= 0.001:
                # CRITICAL FIX: One must be transparent (< 0.5) and one must be FULLY opaque (>= 0.9)
                # This prevents merging shapes with different non-opaque transparency levels
                min_opacity = min(opacity1, opacity2)
                max_opacity = max(opacity1, opacity2)
                
                has_transparent = min_opacity < 0.5
                has_fully_opaque = max_opacity >= 0.9
                
                if has_transparent and has_fully_opaque:
                    return True
        
        # Case B: Stroke+Fill duplication
        # Check if both have the same stroke color
        stroke1 = shape1.get('stroke_color')
        stroke2 = shape2.get('stroke_color')
        
        if stroke1 and stroke2 and stroke1 == stroke2:
            fill1 = shape1.get('fill_color')
            fill2 = shape2.get('fill_color')
            
            # Pattern: one has stroke-only (no fill or transparent fill),
            # the other has stroke + black fill (#000000)
            has_no_fill_1 = (not fill1 or fill1.lower() == 'none')
            has_no_fill_2 = (not fill2 or fill2.lower() == 'none')
            has_black_fill_1 = (fill1 and fill1.lower() == '#000000')
            has_black_fill_2 = (fill2 and fill2.lower() == '#000000')
            
            # If one has no fill and the other has black fill, they're duplicates
            if (has_no_fill_1 and has_black_fill_2) or (has_no_fill_2 and has_black_fill_1):
                logger.debug(f"Detected stroke+fill duplication: "
                           f"shape1 fill={fill1}, shape2 fill={fill2}, stroke={stroke1}")
                return True
        
        return False
    
    def _merge_overlapping_shapes(self, shape1: Dict[str, Any], shape2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two overlapping shapes, keeping the best attributes.
        
        Strategy:
        - For opacity-based duplicates: Use the transparent shape, remove stroke
        - For stroke+fill duplicates: Use the stroke-only shape (cleaner rendering)
        
        Args:
            shape1: First shape element
            shape2: Second shape element
            
        Returns:
            Merged shape element
        """
        # Check if this is a stroke+fill duplication case
        fill1 = shape1.get('fill_color')
        fill2 = shape2.get('fill_color')
        stroke1 = shape1.get('stroke_color')
        stroke2 = shape2.get('stroke_color')
        
        has_no_fill_1 = (not fill1 or fill1.lower() == 'none')
        has_no_fill_2 = (not fill2 or fill2.lower() == 'none')
        has_black_fill_1 = (fill1 and fill1.lower() == '#000000')
        has_black_fill_2 = (fill2 and fill2.lower() == '#000000')
        
        # If one is stroke-only and the other is stroke+black fill
        if stroke1 and stroke2 and stroke1 == stroke2:
            if has_no_fill_1 and has_black_fill_2:
                # Keep stroke-only shape (shape1)
                logger.debug(f"Merged stroke+fill duplication: keeping stroke-only shape")
                return shape1.copy()
            elif has_no_fill_2 and has_black_fill_1:
                # Keep stroke-only shape (shape2)
                logger.debug(f"Merged stroke+fill duplication: keeping stroke-only shape")
                return shape2.copy()
        
        # Otherwise, use opacity-based merging (original logic)
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
    
    def _detect_shape_type(self, drawing: Dict[str, Any]) -> str:
        """
        Detect the actual shape type by analyzing drawing items (lines, curves, etc.).
        
        This method provides intelligent shape detection based on the geometric properties
        of the path, ensuring circles aren't misidentified as rectangles and lines are
        properly preserved.
        
        Args:
            drawing: PyMuPDF drawing dictionary containing items and rect
            
        Returns:
            String shape type: 'oval' (circle/ellipse), 'line', 'triangle', 'rectangle', 'path'
        """
        items = drawing.get('items', [])
        rect = drawing.get('rect')
        original_type = drawing.get('type', 'path')
        
        if not items or not rect:
            return original_type
        
        width = rect.width
        height = rect.height
        
        # Calculate aspect ratio
        aspect_ratio = width / height if height > 0 else 0
        
        # Count different item types
        line_count = sum(1 for item in items if item[0] == 'l')
        curve_count = sum(1 for item in items if item[0] == 'c')
        rect_count = sum(1 for item in items if item[0] == 're')
        
        # Total non-rect items
        path_item_count = line_count + curve_count
        
        # DETECTION LOGIC (order matters - most specific first)
        
        # 1. Circle/Oval Detection
        # Circles use Bezier curves (typically 4 curves + connecting lines)
        # Key indicators: 4+ curves, aspect ratio near 1.0 (circle) or moderately different (ellipse)
        # IMPORTANT: Rounded rectangles also have 4 curves (one per corner) but with extreme aspect ratios
        if curve_count >= 4:
            # Check aspect ratio to distinguish between:
            # - Circles/Ovals: aspect ratio 0.5 to 2.0 (not too extreme)
            # - Rounded rectangles: aspect ratio < 0.5 or > 2.0 (very elongated)
            
            if 0.9 <= aspect_ratio <= 1.1:
                # Nearly square aspect ratio = circle
                logger.debug(f"Detected circle: {curve_count} curves, aspect {aspect_ratio:.3f}")
                return 'oval'
            elif 0.5 <= aspect_ratio <= 2.0:
                # Moderate aspect ratio = ellipse/oval
                logger.debug(f"Detected oval/ellipse: {curve_count} curves, aspect {aspect_ratio:.3f}")
                return 'oval'
            else:
                # Extreme aspect ratio (< 0.5 or > 2.0) = rounded rectangle
                # Even though it has 4 curves, the shape is clearly rectangular
                logger.debug(f"Detected rounded rectangle: {curve_count} curves, aspect {aspect_ratio:.3f} (too extreme for oval)")
                return 'rectangle'
        
        # 2. Line Detection (single line, stroke-only shapes)
        # Lines are critical for triangles and other geometric shapes
        # Characteristics: 1 line item OR very thin shape with stroke but no fill
        fill = drawing.get('fill', None)
        stroke = drawing.get('color', None)
        has_fill = fill is not None
        has_stroke = stroke is not None
        
        if line_count == 1 and curve_count == 0:
            # Single line path - always preserve as line
            logger.debug(f"Detected single line: ({rect.x0:.1f},{rect.y0:.1f}) to ({rect.x1:.1f},{rect.y1:.1f})")
            return 'line'
        
        # Stroke-only thin shapes (like triangle edges)
        # These have stroke but no fill, and are thin in one dimension
        if has_stroke and not has_fill:
            # Check if it's a thin line (width or height is very small relative to the other)
            min_dim = min(width, height)
            max_dim = max(width, height)
            
            if min_dim < 5 and max_dim > 10:
                # Very thin shape - treat as line
                logger.debug(f"Detected thin stroke line: {width:.1f}x{height:.1f}, stroke only")
                return 'line'
        
        # 3. Triangle Detection
        # Triangles have exactly 3 lines forming a closed path
        if line_count == 3 and curve_count == 0:
            logger.debug(f"Detected triangle: 3 lines")
            return 'triangle'
        
        # 3.5. Star Detection
        # Stars have 10 lines forming a closed path (5 outer points + 5 inner points)
        # Check for aspect ratio close to 1.0 and 10 line segments
        if line_count == 10 and curve_count == 0:
            if 0.8 <= aspect_ratio <= 1.2:  # Nearly square
                logger.debug(f"Detected star: 10 lines, aspect {aspect_ratio:.3f}")
                return 'star'
        
        # 4. Rectangle Detection
        # Explicit rectangle command OR 4 lines forming a rectangle
        if rect_count >= 1:
            return 'rectangle'
        
        if line_count == 4 and curve_count == 0:
            # Could be a rectangle made of 4 lines
            return 'rectangle'
        
        # 5. Complex Paths
        # Multiple lines or mixed curves+lines that don't fit above patterns
        if path_item_count > 4:
            logger.debug(f"Complex path: {line_count} lines, {curve_count} curves")
            return 'path'
        
        # Default: use original type from PyMuPDF
        return original_type
    
    def _rgb_to_hex(self, color) -> str:
        """
        Convert RGB color to hex format.
        
        Args:
            color: Color value (int or tuple), or None for no fill
            
        Returns:
            Hex color string, or None if color is None (no fill)
        """
        if color is None:
            # Return None for stroke-only shapes (no fill)
            # This prevents treating unfilled shapes as black rectangles
            return None
        
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
        
        # Fallback for unexpected color format
        logger.warning(f"Unexpected color format: {color} (type: {type(color)})")
        return None
    
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
    
    def _check_image_quality(self, pil_image: Image.Image, rect: fitz.Rect = None) -> Tuple[str, bool]:
        """
        Check the quality of an embedded image and determine the appropriate action.
        
        This method detects three types of images:
        1. Truly corrupted images (all black, all white) -> 'rerender'
        2. Low-quality embedded PNG icons (small size, limited colors) -> 'rerender'
        3. Low-quality rasterized vector graphics (medium size, very limited colors, high white bg) -> 'skip'
        4. Large images that need quality enhancement -> needs_enhancement=True
        
        CRITICAL: This method ONLY processes embedded images extracted from PDF.
        Vector shapes are NOT passed to this method, so they remain untouched.
        
        Args:
            pil_image: PIL Image object from embedded image extraction
            rect: Optional rectangle for size checking in points
            
        Returns:
            Tuple of (quality_status, needs_large_image_enhancement):
                quality_status: 'good', 'rerender', or 'skip'
                needs_large_image_enhancement: True if large image needs quality boost
        """
        try:
            import numpy as np
            
            width, height = pil_image.size
            
            # Skip very small images - they're fine as-is
            if width < 10 or height < 10:
                return 'good'
            
            # Sample 9 points (corners, edges, center)
            sample_points = [
                (0, 0),  # Top-left
                (width // 2, 0),  # Top-center
                (width - 1, 0),  # Top-right
                (0, height // 2),  # Left-center
                (width // 2, height // 2),  # Center
                (width - 1, height // 2),  # Right-center
                (0, height - 1),  # Bottom-left
                (width // 2, height - 1),  # Bottom-center
                (width - 1, height - 1)  # Bottom-right
            ]
            
            pixels = []
            for x, y in sample_points:
                try:
                    pixel = pil_image.getpixel((x, y))
                    # Convert to tuple if not already
                    if not isinstance(pixel, tuple):
                        pixel = (pixel, pixel, pixel)
                    pixels.append(pixel)
                except:
                    continue
            
            if not pixels:
                return 'good'
            
            # Check 1: Truly corrupted - all pixels are the same (single color)
            first_pixel = pixels[0]
            all_same = all(p == first_pixel for p in pixels)
            
            if all_same:
                # Only re-render if it's black or white (truly corrupted)
                is_black = all(c <= 5 for c in first_pixel[:3])
                is_white = all(c >= 250 for c in first_pixel[:3])
                
                if is_black or is_white:
                    logger.debug(f"Detected truly corrupted image: {width}x{height}, all {('black' if is_black else 'white')}")
                    return ('rerender', False)
            
            # Check 2: Low-quality embedded icon detection
            # These are small PNG icons with no alpha channel and limited colors
            # IMPORTANT: This check only applies to embedded images, NOT vector shapes
            
            # Condition 1: No alpha channel (RGB mode)
            has_no_alpha = pil_image.mode == 'RGB'
            
            # Condition 2: Small size (typical for icons)
            is_small = (width <= 100 or height <= 100)
            
            # Only proceed if both conditions are met
            if has_no_alpha and is_small:
                # Convert to numpy for efficient analysis
                img_array = np.array(pil_image)
                
                # Condition 3: Limited color palette (typical for icons)
                unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                has_limited_palette = unique_colors < 200
                
                if has_limited_palette:
                    # This is likely a low-quality embedded icon
                    logger.info(
                        f"Detected low-quality embedded icon: {width}x{height}px, "
                        f"{unique_colors} colors, RGB mode - will re-render for better quality"
                    )
                    return ('rerender', False)
            
            # Check 3: Large PNG images - NOW ENABLED with smart overlap detection
            # 
            # CRITICAL FIX v2: We NOW enable large image rerendering but with smart overlap detection.
            # The _extract_images method will call _calculate_safe_rerender_bbox to:
            # - Detect overlaps with text/shapes BEFORE rerendering
            # - Shrink the rerender bbox to exclude overlapping regions
            # - Only rerender the safe, non-overlapping portion
            #
            # This solves the duplication issue while still improving image quality.
            #
            # Check if this is a large image that could benefit from enhancement
            is_large = rect and (rect.width > 200 or rect.height > 200)
            needs_large_image_enhancement = False
            
            if is_large and pil_image.mode == 'RGB':
                # Large RGB images often have quality issues
                # Signal that enhancement is desired, but let _extract_images decide
                # based on overlap detection
                needs_large_image_enhancement = True
                logger.debug(
                    f"Detected large PNG image: {width}x{height}px - may re-render if no text/shape overlaps"
                )
            
            # Check 4: Low-quality rasterized vector graphics
            # These are medium-sized PNG images that are actually poorly rasterized vector shapes
            # They should be skipped entirely to allow the underlying vector shapes to be used
            # 
            # Characteristics:
            # - Medium size (100-400px)
            # - Extremely limited colors (< 50 colors, often just 4-10)
            # - High percentage of white/near-white background (> 50%)
            # - No alpha channel (RGB mode)
            #
            # These images are created when PDF tools rasterize vector graphics,
            # and they obscure the clean vector shapes underneath.
            is_medium_size = (100 < width <= 400 and 100 < height <= 400)
            
            if has_no_alpha and is_medium_size:
                # Convert to numpy for efficient analysis
                img_array = np.array(pil_image)
                
                # Check for extremely limited color palette
                unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                has_very_limited_palette = unique_colors < 50
                
                if has_very_limited_palette:
                    # Check for high white background percentage
                    white_mask = np.all(img_array >= 240, axis=-1)
                    white_pct = np.sum(white_mask) / white_mask.size * 100
                    has_white_background = white_pct > 50
                    
                    if has_white_background:
                        # This is a low-quality rasterized vector graphic that obscures
                        # the underlying clean vector shapes. Skip it entirely.
                        logger.info(
                            f"Detected low-quality rasterized vector graphic: {width}x{height}px, "
                            f"{unique_colors} colors, {white_pct:.1f}% white background - will skip to show underlying vectors"
                        )
                        return ('skip', False)
            
            return ('good', needs_large_image_enhancement)
            
        except Exception as e:
            logger.debug(f"Error checking image quality: {e}")
            return ('good', False)
    
    def _calculate_safe_rerender_bbox(self, img_rect: fitz.Rect, text_elements: List[Dict[str, Any]], 
                                       page: fitz.Page) -> Optional[fitz.Rect]:
        """
        Calculate a safe bounding box for rerendering an image that avoids overlapping text/shapes.
        
        This method detects overlaps between the image bbox and text/shape bboxes, then shrinks
        the image bbox to exclude the overlapping regions.
        
        Args:
            img_rect: Original image rectangle
            text_elements: List of already-extracted text elements
            page: PyMuPDF page object for shape detection
            
        Returns:
            Safe rectangle for rerendering, or None if no safe region exists
        """
        # Start with the original rect
        safe_rect = fitz.Rect(img_rect)
        margin = 2.0  # Add small margin to avoid edge overlaps
        
        # Check overlaps with text elements
        for text_elem in text_elements:
            text_bbox = (text_elem['x'], text_elem['y'], text_elem['x2'], text_elem['y2'])
            text_rect = fitz.Rect(text_bbox)
            
            # Check if text overlaps with current safe_rect
            if safe_rect.intersects(text_rect):
                # Text overlaps - we need to shrink safe_rect to avoid it
                logger.debug(f"Text '{text_elem.get('content', '')[:20]}...' overlaps image at "
                           f"({text_rect.x0:.1f}, {text_rect.y0:.1f}, {text_rect.x1:.1f}, {text_rect.y1:.1f})")
                
                # Determine which edge to shrink
                # If text is at the top of image, move safe_rect's top down
                if text_rect.y0 < safe_rect.y0 + safe_rect.height * 0.3:
                    # Text is in top portion of image
                    new_y0 = text_rect.y1 + margin
                    if new_y0 < safe_rect.y1:
                        safe_rect.y0 = new_y0
                        logger.debug(f"Shrunk image top to y={new_y0:.1f} to avoid text")
                
                # If text is at the bottom of image, move safe_rect's bottom up
                elif text_rect.y1 > safe_rect.y0 + safe_rect.height * 0.7:
                    # Text is in bottom portion of image
                    new_y1 = text_rect.y0 - margin
                    if new_y1 > safe_rect.y0:
                        safe_rect.y1 = new_y1
                        logger.debug(f"Shrunk image bottom to y={new_y1:.1f} to avoid text")
                
                # If text is on the left side
                elif text_rect.x0 < safe_rect.x0 + safe_rect.width * 0.3:
                    # Text is in left portion of image
                    new_x0 = text_rect.x1 + margin
                    if new_x0 < safe_rect.x1:
                        safe_rect.x0 = new_x0
                        logger.debug(f"Shrunk image left to x={new_x0:.1f} to avoid text")
                
                # If text is on the right side
                elif text_rect.x1 > safe_rect.x0 + safe_rect.width * 0.7:
                    # Text is in right portion of image
                    new_x1 = text_rect.x0 - margin
                    if new_x1 > safe_rect.x0:
                        safe_rect.x1 = new_x1
                        logger.debug(f"Shrunk image right to x={new_x1:.1f} to avoid text")
        
        # Check if the safe_rect is still large enough to be useful
        if safe_rect.width < 20 or safe_rect.height < 20:
            logger.warning(f"Safe rerender bbox too small ({safe_rect.width:.1f}x{safe_rect.height:.1f}), "
                         f"will not rerender")
            return None
        
        # Check if we actually shrunk the rect
        if safe_rect != img_rect:
            logger.info(f"Calculated safe rerender bbox: "
                      f"original ({img_rect.x0:.1f}, {img_rect.y0:.1f}, {img_rect.x1:.1f}, {img_rect.y1:.1f}), "
                      f"safe ({safe_rect.x0:.1f}, {safe_rect.y0:.1f}, {safe_rect.x1:.1f}, {safe_rect.y1:.1f})")
            return safe_rect
        else:
            # No overlap, safe to rerender entire image
            return img_rect
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
