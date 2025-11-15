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
from .table_detector import TableDetector
from .text_image_overlap_detector import TextImageOverlapDetector
from .icon_font_detector import IconFontDetector
from .gradient_detector import GradientDetector

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
        
        # Initialize border detector, shape merger, chart detector, table detector, text overlap detector, icon detector, and gradient detector
        self.border_detector = BorderDetector(config)
        self.shape_merger = ShapeMerger(config)
        self.chart_detector = ChartDetector(config)
        self.table_detector = TableDetector(config)
        self.text_overlap_detector = TextImageOverlapDetector(overlap_threshold=0.5)
        self.icon_detector = IconFontDetector(config)
        self.gradient_detector = GradientDetector(config)
        
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
    
    def _generate_page_background_without_text(self, page: fitz.Page, page_num: int) -> Optional[Dict[str, Any]]:
        """
        Generate a full-page background image without text for the given page.
        This creates a complete page render excluding text elements.
        
        CRITICAL FIX: Render full page then remove text pixels using transparency.
        Instead of masking text with opaque rectangles (which leave visible artifacts),
        we render the complete page first, then make text pixels transparent.
        This preserves ALL original PDF backgrounds, patterns, and styles perfectly.
        
        Strategy:
        1. Render the full page at high resolution (includes everything)
        2. Extract text bounding boxes to identify text regions
        3. Make text pixels transparent by setting alpha channel to 0
        4. Result: Complete original background with transparent "holes" where text was
        
        This approach avoids any visible artifacts because transparency is truly invisible,
        while preserving all original PDF visual elements (backgrounds, patterns, shapes).
        
        Args:
            page: PyMuPDF page object
            page_num: Page number for identification
            
        Returns:
            Image element dictionary with z_index=-1000, or None if generation fails
        """
        try:
            rect = page.rect
            
            # Step 1: Extract text bounding boxes
            text_bboxes = []
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            # Only include reasonable-sized text (filter noise)
                            if bbox[2] - bbox[0] > 2 and bbox[3] - bbox[1] > 2:
                                text_bboxes.append(bbox)
            
            logger.info(f"Page {page_num}: Found {len(text_bboxes)} text regions to make transparent")
            
            # Step 2: Render the full page at high resolution
            zoom = 2.0  # 2x for ~144 DPI from 72 DPI
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=True)
            
            # Step 3: Convert to PIL Image and make text regions transparent
            from PIL import Image, ImageDraw
            
            # Convert pixmap to PIL Image
            img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
            
            # Create an alpha mask for text regions
            # We'll set alpha to 0 (fully transparent) for text pixels
            alpha_mask = img.getchannel('A')  # Get current alpha channel
            draw = ImageDraw.Draw(alpha_mask)
            
            # Make each text region fully transparent
            for bbox in text_bboxes:
                # Scale bbox coordinates by zoom factor
                x0, y0, x2, y2 = bbox
                x0_scaled = int(x0 * zoom)
                y0_scaled = int(y0 * zoom)
                x2_scaled = int(x2 * zoom)
                y2_scaled = int(y2 * zoom)
                
                # Draw a black rectangle in alpha channel (0 = transparent)
                # Add a small padding (2px) to ensure complete coverage
                padding = 2
                draw.rectangle(
                    [x0_scaled - padding, y0_scaled - padding, 
                     x2_scaled + padding, y2_scaled + padding],
                    fill=0  # 0 = fully transparent
                )
            
            # Apply the modified alpha mask back to the image
            img.putalpha(alpha_mask)
            
            # Step 4: Convert back to PNG bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            image_bytes = img_bytes.getvalue()
            
            # Create image element with lowest z-index to ensure it's at the bottom
            background_element = {
                'type': 'image',
                'image_data': image_bytes,
                'image_format': 'png',
                'width_px': pix.width,
                'height_px': pix.height,
                'x': rect.x0,
                'y': rect.y0,
                'x2': rect.x1,
                'y2': rect.y1,
                'width': rect.width,
                'height': rect.height,
                'image_id': f"page{page_num}_full_background",
                'is_background': True,
                'z_index': -1000  # Ensure this is rendered at the bottom
            }
            
            logger.info(f"Generated text-free full-page background for page {page_num} "
                       f"(size: {pix.width}x{pix.height}px, {len(image_bytes)} bytes) "
                       f"by making {len(text_bboxes)} text regions transparent")
            
            return background_element
            
        except Exception as e:
            logger.error(f"Failed to generate page background for page {page_num}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def extract_page_elements(self, page_num: int) -> Dict[str, Any]:
        """
        Extract all elements from a specific page.
        
        For first and last pages, a special full-page background image is created
        (without text) and placed at z-index -1000 to serve as the bottom layer,
        while text elements are placed on top for editability.
        
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
        
        # Determine if this is first or last page
        total_pages = len(self.doc)
        is_first_page = (page_num == 0)
        is_last_page = (page_num == total_pages - 1)
        
        # For first and last pages, generate full-page background image
        if is_first_page or is_last_page:
            background_elem = self._generate_page_background_without_text(page, page_num)
            if background_elem:
                # Add background element with lowest z-index
                page_data['elements'].append(background_elem)
                logger.info(f"Page {page_num + 1}: Added full-page background layer "
                           f"({'first' if is_first_page else 'last'} page)")
            else:
                logger.warning(f"Page {page_num + 1}: Failed to generate background layer")
        
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
        
        if icon_indices:
            logger.info(f"Page {page_num}: Filtered out {len(icon_indices)} icon font text element(s)")
        
        # CRITICAL FIX: Extract shapes/drawings FIRST to detect gradient patterns
        # This prevents gradient XObjects from being extracted twice
        # IMPORTANT: Pass filtered_text_elements for page number detection in gradients
        drawing_elements, gradient_images = self._extract_drawings(page, opacity_map, page_num, filtered_text_elements)
        
        # Add gradient images to page elements (they should be rendered on bottom layer)
        if gradient_images:
            page_data['elements'].extend(gradient_images)
            logger.info(f"Page {page_num}: Detected and extracted {len(gradient_images)} gradient pattern(s) as images")
        
        # Extract images (pass text elements for overlap detection and gradient images to avoid duplicates)
        if self.extract_images:
            image_elements = self._extract_images(page, page_num, filtered_text_elements, gradient_images)
            page_data['elements'].extend(image_elements)
            
            # CRITICAL: Filter out page numbers that are within gradient regions
            # This prevents page number duplication when gradients are rendered as images
            original_count = len(filtered_text_elements)
            filtered_text_elements = [
                elem for elem in filtered_text_elements
                if not self.gradient_detector.should_exclude_text_in_gradient(elem, gradient_images)
            ]
            excluded_count = original_count - len(filtered_text_elements)
            if excluded_count > 0:
                logger.info(f"Page {page_num}: Excluded {excluded_count} page number text element(s) "
                           f"from gradient region(s) to prevent duplication")
        
        # Add filtered text elements to page data (AFTER gradient detection and filtering)
        page_data['elements'].extend(filtered_text_elements)
        
        # CRITICAL FIX: Detect TABLE regions FIRST (they have higher priority)
        # Then detect chart regions from NON-TABLE shapes only
        # This prevents tables from being misidentified as charts
        # Pass text elements to populate table cell contents
        table_regions = self.table_detector.detect_tables(
            drawing_elements, page, filtered_text_elements
        )
        
        # Mark shapes and texts in table regions for exclusion from individual rendering
        table_shape_ids = set()
        table_text_ids = set()
        
        for table_region in table_regions:
            table_bbox = table_region['bbox']
            
            # CRITICAL FIX: Do NOT extend bbox upward to include "header" text above table
            # The table's first row IS the header row - it's already part of the table cells
            # Text above the table (like explanatory paragraphs) should render as separate text boxes
            # Extending the bbox causes two major issues:
            # 1. Paragraph text above table gets incorrectly marked as table content (disappears)
            # 2. Table cell text gets excluded from text_elements, making cells empty
            #
            # Solution: Use ONLY the actual table bbox without any upward extension
            # Add small horizontal margins to catch cell borders
            extended_bbox = (
                table_bbox[0] - 5,   # Left with small margin for borders
                table_bbox[1],       # NO upward extension - use actual table top
                table_bbox[2] + 5,   # Right with small margin for borders  
                table_bbox[3]        # Bottom unchanged
            )
            
            # Mark shapes in table region (borders, cell backgrounds)
            for shape in drawing_elements:
                shape_center_x = (shape['x'] + shape['x2']) / 2
                shape_center_y = (shape['y'] + shape['y2']) / 2
                if (extended_bbox[0] <= shape_center_x <= extended_bbox[2] and
                    extended_bbox[1] <= shape_center_y <= extended_bbox[3]):
                    table_shape_ids.add(id(shape))
            
            # Mark texts in table region (use actual bbox, no extension)
            # This ensures table cell text is available for _populate_table_cells
            for text_elem in filtered_text_elements:
                tx, ty = text_elem['x'], text_elem['y']
                if (extended_bbox[0] <= tx <= extended_bbox[2] and 
                    extended_bbox[1] <= ty <= extended_bbox[3]):
                    table_text_ids.add(id(text_elem))
        
        # Add table elements to page data (as complete table objects)
        for table_region in table_regions:
            table_elem = {
                'type': 'table',
                'x': table_region['bbox'][0],
                'y': table_region['bbox'][1],
                'x2': table_region['bbox'][2],
                'y2': table_region['bbox'][3],
                'width': table_region['bbox'][2] - table_region['bbox'][0],
                'height': table_region['bbox'][3] - table_region['bbox'][1],
                'grid': table_region.get('grid', []),
                'rows': table_region.get('num_rows', table_region.get('rows', 0)),
                'cols': table_region.get('num_cols', table_region.get('cols', 0)),
                'col_widths': table_region.get('col_widths', []),  # Preserve column widths from table detector
                'row_heights': table_region.get('row_heights', [])  # Preserve row heights from table detector
            }
            page_data['elements'].append(table_elem)
        
        # Detect chart regions from non-table shapes only
        non_table_shapes = [shape for shape in drawing_elements if id(shape) not in table_shape_ids]
        chart_regions = self.chart_detector.detect_chart_regions(page, non_table_shapes)
        
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
        
        # Filter non-chart and non-table shapes to remove text decoration shapes
        # Combine both table and chart shape IDs for exclusion
        excluded_shape_ids = table_shape_ids | chart_shape_ids
        non_chart_table_shapes = [shape for shape in drawing_elements if id(shape) not in excluded_shape_ids]
        
        # CRITICAL: Filter out shapes that are text decorations (backgrounds/highlights)
        # These shapes appear as unwanted rectangles in PowerPoint
        # Only filter shapes that are NOT in tables or charts
        non_table_texts_for_filtering = [t for t in filtered_text_elements if id(t) not in table_text_ids]
        
        filtered_shapes = self.text_overlap_detector.filter_text_decoration_shapes(
            non_chart_table_shapes, non_table_texts_for_filtering
        )
        
        # Add filtered shapes to elements (tables and charts already added)
        page_data['elements'].extend(filtered_shapes)
        
        # Filter out text elements that overlap with chart images (but NOT table text)
        # Table texts are already integrated into table objects, so remove them from page_data
        if chart_regions or table_regions:
            # Remove table texts from page_data (they're now in table objects)
            page_data['elements'] = [
                elem for elem in page_data['elements']
                if elem['type'] != 'text' or id(elem) not in table_text_ids
            ]
            # Filter overlapping texts with charts
            if chart_regions:
                page_data['elements'] = self.text_overlap_detector.filter_overlapping_texts(page_data['elements'])
        
        logger.info(f"Page {page_num}: Extracted {len(page_data['elements'])} elements "
                   f"({len(table_regions)} tables, {len(chart_regions)} charts rendered as images)")
        
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
                        text = span.get("text", "")
                        
                        # Only strip leading/trailing newlines and tabs, preserve spaces
                        # Spaces at boundaries are important for text merging (e.g., "2.3.1 " + "text")
                        text = text.strip('\n\r\t')
                        
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
                        
                        # For rotated text, we need special handling of position
                        # The bbox is the rotated bounding rectangle, but for positioning in PowerPoint,
                        # we need to use the text baseline position (origin) and calculate correct dimensions
                        origin = span.get("origin", (bbox[0], bbox[1]))
                        
                        # Check if text is significantly rotated (more than 5 degrees)
                        is_rotated = abs(rotation_angle) > 5
                        
                        if is_rotated:
                            # For rotated text, use bbox as the physical boundaries
                            # but store origin for future reference if needed
                            # The key insight: bbox is already correct for the rotated text rectangle
                            # We just need to ensure we don't try to "correct" it
                            
                            # Use bbox as-is for rotated text
                            # This preserves the actual rendered position in PDF
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
                                'flags': span.get("flags", 0),
                                'is_bold': bool(span.get("flags", 0) & 2**4),
                                'is_italic': bool(span.get("flags", 0) & 2**1),
                                'rotation': rotation_angle,
                                'text_dir': line_dir,
                                'origin': origin,  # Store origin for reference
                                'is_rotated': True
                            }
                        else:
                            # For non-rotated text, use bbox as usual
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
                                'flags': span.get("flags", 0),
                                'is_bold': bool(span.get("flags", 0) & 2**4),
                                'is_italic': bool(span.get("flags", 0) & 2**1),
                                'rotation': rotation_angle,
                                'text_dir': line_dir,
                                'is_rotated': False
                            }
                        
                        text_elements.append(element)
        
        return text_elements
    
    def _extract_images(self, page: fitz.Page, page_num: int, text_elements: List[Dict[str, Any]] = None, gradient_images: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract embedded images (image XObjects) directly from PDF without cropping.
        
        CRITICAL PRINCIPLE:
        - Embedded images (XObjects) NEVER contain text - text is a separate PDF layer
        - Therefore, we should NEVER crop embedded images to avoid text overlap
        - Only when RE-RENDERING (taking a screenshot) do we need to worry about text
        - For decorative patterns, logos, icons, we always use the original embedded image
        
        CRITICAL FIX:
        - Skip images that have already been extracted as gradient patterns
        - This prevents duplicate extraction of the same XObject
        
        Args:
            page: PyMuPDF page object
            page_num: Page number for naming
            text_elements: Optional list of text elements (used only for re-render decisions)
            gradient_images: Optional list of gradient images already extracted (to avoid duplicates)
            
        Returns:
            List of image element dictionaries
        """
        image_elements = []
        image_list = page.get_images(full=True)
        
        # Text elements are only needed for re-render overlap detection
        if text_elements is None:
            text_elements = []
        
        # Build a set of xrefs that are already extracted as gradients
        gradient_xrefs = set()
        if gradient_images:
            for grad_img in gradient_images:
                # Try to find the xref for this gradient image
                # We'll check by position to identify which xref was used
                for img_info in image_list:
                    xref = img_info[0]
                    image_rects = page.get_image_rects(xref)
                    for img_rect in image_rects:
                        # Check if this rect matches the gradient image position
                        grad_x = grad_img.get('x', 0)
                        grad_y = grad_img.get('y', 0)
                        grad_x2 = grad_img.get('x2', 0)
                        grad_y2 = grad_img.get('y2', 0)
                        
                        tolerance = 1.0
                        if (abs(img_rect.x0 - grad_x) < tolerance and
                            abs(img_rect.y0 - grad_y) < tolerance and
                            abs(img_rect.x1 - grad_x2) < tolerance and
                            abs(img_rect.y1 - grad_y2) < tolerance):
                            gradient_xrefs.add(xref)
                            logger.debug(f"Page {page_num}: Marked xref {xref} as gradient (skip in normal image extraction)")
                            break
        
        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                
                # CRITICAL FIX: Skip images that are already extracted as gradients
                if xref in gradient_xrefs:
                    logger.debug(f"Page {page_num}: Skipping xref {xref} - already extracted as gradient")
                    continue
                
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
                    
                    # IMPORTANT: Keep all embedded images, including full-page backgrounds
                    # Some full-page backgrounds contain important visual elements (e.g., shield patterns)
                    # The header/footer screenshot mechanism that was causing issues has been removed
                    # So we can now safely keep all embedded images as-is
                    page_area = page.rect.width * page.rect.height
                    image_area = rect.width * rect.height
                    area_ratio = image_area / page_area if page_area > 0 else 0
                    
                    # CRITICAL FIX: Full-page background images (>80% area) must be extracted completely
                    # These often contain important decorative elements like shield patterns, watermarks, etc.
                    # They should NOT be shrunk or cropped, even if text overlaps
                    # They will be rendered on the bottommost layer in PPT, so text will appear on top
                    is_full_page_background = area_ratio > 0.80
                    
                    if is_full_page_background:
                        logger.info(f"Keeping full-page background image at page {page_num}, "
                                  f"area ratio: {area_ratio*100:.1f}%, format: {image_ext}, "
                                  f"will extract COMPLETELY without cropping")
                    
                    # IMPORTANT: We do NOT filter large embedded images (even if >25% area) because:
                    # - Complex background patterns are often embedded as large PNG images
                    # - These are intentional design elements, not accidental screenshots
                    # - Only filter if this is a RE-RENDERED screenshot (not original embedded image)
                    # 
                    # The distinction is made later by checking 'was_rerendered' flag
                    
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
                    
                    # CRITICAL FIX: For embedded images, NEVER crop to avoid text
                    # Embedded images (XObjects) do NOT contain text - text is a separate PDF layer
                    # Therefore, we should always extract the COMPLETE embedded image
                    # 
                    # Only re-render if:
                    # 1. Image is truly corrupted (quality_status == 'rerender')
                    # 2. Image is NOT a full-page background
                    # 3. Image lost its alpha channel and needs transparency restoration
                    
                    should_rerender = False
                    rerender_reason = ""
                    
                    if is_full_page_background:
                        # Always keep full-page backgrounds as-is
                        logger.info(f"Full-page background at page {page_num} will be kept AS-IS without rerendering")
                    elif quality_status == 'rerender':
                        # Image is truly corrupted (all black/white) - needs re-rendering
                        should_rerender = True
                        rerender_reason = "truly corrupted"
                    elif quality_status == 'process_alpha':
                        # PNG with black background (lost alpha) - needs transparency restoration
                        # CRITICAL FIX: Check DPI before deciding whether to rerender
                        # If DPI is too low (< 150), we should rerender for quality improvement
                        # while preserving alpha channel
                        
                        # Calculate DPI
                        scale_x = pil_image.width / rect.width if rect.width > 0 else 0
                        scale_y = pil_image.height / rect.height if rect.height > 0 else 0
                        dpi_x = scale_x * 72
                        dpi_y = scale_y * 72
                        min_dpi = min(dpi_x, dpi_y)
                        
                        # Check if DPI is acceptable
                        dpi_threshold = 150  # Minimum DPI for acceptable quality
                        
                        if min_dpi < dpi_threshold and needs_large_image_enhancement:
                            # Low DPI + large image = needs quality enhancement
                            # But ONLY if no text overlap (to avoid capturing text)
                            safe_rect = self._calculate_safe_rerender_bbox(rect, text_elements, page)
                            if safe_rect and safe_rect == rect:
                                # No text overlap, safe to enhance
                                should_rerender = True
                                rerender_reason = f"quality enhancement (DPI {min_dpi:.1f} < {dpi_threshold}, no text overlap)"
                                logger.info(f"Low DPI image at page {page_num}: {min_dpi:.1f} DPI, will rerender for quality")
                            else:
                                # Has text overlap - use image processing only
                                logger.info(f"Low DPI image at page {page_num}: {min_dpi:.1f} DPI, but has text overlap - "
                                          f"will use image processing for alpha without rerendering")
                                pil_image = self._add_alpha_channel_to_png(pil_image)
                                img_io = io.BytesIO()
                                # CRITICAL: Save DPI information to prevent resampling in python-pptx
                                dpi = pil_image.info.get('dpi', (72, 72))
                                pil_image.save(img_io, format='PNG', dpi=dpi)
                                image_bytes = img_io.getvalue()
                                image_ext = 'png'
                                logger.info(f"Added alpha channel: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, DPI={dpi}")
                        else:
                            # DPI is acceptable or not a large image - just add alpha channel
                            logger.info(f"Processing alpha channel for PNG at page {page_num} (DPI {min_dpi:.1f})")
                            pil_image = self._add_alpha_channel_to_png(pil_image)
                            img_io = io.BytesIO()
                            # CRITICAL: Save DPI information to prevent resampling in python-pptx
                            dpi = pil_image.info.get('dpi', (72, 72))
                            pil_image.save(img_io, format='PNG', dpi=dpi)
                            image_bytes = img_io.getvalue()
                            image_ext = 'png'
                            logger.info(f"Added alpha channel: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, DPI={dpi}")
                    elif quality_status == 'process_white_bg':
                        # PNG with white background that should be transparent - needs white-to-transparent conversion
                        # CRITICAL FIX: Check DPI before deciding whether to rerender
                        # If DPI is too low (< 150), we should rerender for quality improvement
                        # then convert white background to transparent
                        
                        # Calculate DPI
                        scale_x = pil_image.width / rect.width if rect.width > 0 else 0
                        scale_y = pil_image.height / rect.height if rect.height > 0 else 0
                        dpi_x = scale_x * 72
                        dpi_y = scale_y * 72
                        min_dpi = min(dpi_x, dpi_y)
                        
                        # Check if DPI is acceptable
                        dpi_threshold = 150  # Minimum DPI for acceptable quality
                        
                        if min_dpi < dpi_threshold and needs_large_image_enhancement:
                            # Low DPI + large image = needs quality enhancement
                            # But ONLY if no text overlap (to avoid capturing text)
                            # 
                            # CRITICAL: For white background images, we MUST NOT allow minor overlap
                            # because rerendering would capture text into the image (text is usually not white)
                            # This differs from black background images where alpha channel handles text properly
                            # CRITICAL: For white background images, we MUST find a safe rect that avoids text
                            # because rerendering would capture text into the image
                            original_rect = fitz.Rect(rect)  # Save original for comparison
                            safe_rect = self._calculate_safe_rerender_bbox(rect, text_elements, page, 
                                                                           allow_minor_overlap=False)
                            if safe_rect:
                                # Found a safe rect - use it for rerendering
                                rect = safe_rect  # Update rect to safe rect
                                should_rerender = True
                                
                                # Check if rect was shrunk
                                if (abs(safe_rect.x0 - original_rect.x0) < 1 and 
                                    abs(safe_rect.y0 - original_rect.y0) < 1 and
                                    abs(safe_rect.x1 - original_rect.x1) < 1 and
                                    abs(safe_rect.y1 - original_rect.y1) < 1):
                                    rerender_reason = f"quality enhancement with white-to-transparent (DPI {min_dpi:.1f} < {dpi_threshold}, no text overlap)"
                                else:
                                    rerender_reason = f"quality enhancement with white-to-transparent (DPI {min_dpi:.1f} < {dpi_threshold}, shrunk to avoid text)"
                                    logger.info(f"Shrunk image rect to avoid text: ({original_rect.x0:.1f}, {original_rect.y0:.1f}, {original_rect.x1:.1f}, {original_rect.y1:.1f}) "
                                              f"-> ({safe_rect.x0:.1f}, {safe_rect.y0:.1f}, {safe_rect.x1:.1f}, {safe_rect.y1:.1f})")
                                logger.info(f"Low DPI image at page {page_num}: {min_dpi:.1f} DPI, will rerender safe region then convert white to transparent")
                            else:
                                # Cannot find safe rect - use image processing only
                                logger.info(f"Low DPI image at page {page_num}: {min_dpi:.1f} DPI, but cannot find safe rect - "
                                          f"will convert white to transparent without rerendering")
                                pil_image = self._convert_white_bg_to_transparent(pil_image)
                                img_io = io.BytesIO()
                                # CRITICAL: Save DPI information to prevent resampling in python-pptx
                                dpi = pil_image.info.get('dpi', (72, 72))
                                pil_image.save(img_io, format='PNG', dpi=dpi)
                                image_bytes = img_io.getvalue()
                                image_ext = 'png'
                                logger.info(f"Converted white to transparent: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, DPI={dpi}")
                        else:
                            # DPI is acceptable or not a large image - just convert white to transparent
                            logger.info(f"Converting white background to transparent for PNG at page {page_num} (DPI {min_dpi:.1f})")
                            pil_image = self._convert_white_bg_to_transparent(pil_image)
                            img_io = io.BytesIO()
                            # CRITICAL: Save DPI information to prevent resampling in python-pptx
                            dpi = pil_image.info.get('dpi', (72, 72))
                            pil_image.save(img_io, format='PNG', dpi=dpi)
                            image_bytes = img_io.getvalue()
                            image_ext = 'png'
                            logger.info(f"Converted white to transparent: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, DPI={dpi}")
                    elif needs_large_image_enhancement:
                        # Large image that could benefit from quality enhancement
                        # But ONLY if:
                        # 1. DPI is too low (< 150)
                        # 2. No text overlap (to avoid capturing text)
                        
                        # Calculate DPI to check if enhancement is really needed
                        scale_x = pil_image.width / rect.width if rect.width > 0 else 0
                        scale_y = pil_image.height / rect.height if rect.height > 0 else 0
                        dpi_x = scale_x * 72
                        dpi_y = scale_y * 72
                        min_dpi = min(dpi_x, dpi_y)
                        
                        dpi_threshold = 150  # Minimum acceptable DPI
                        
                        if min_dpi < dpi_threshold:
                            # DPI is too low, check for text overlap
                            safe_rect = self._calculate_safe_rerender_bbox(rect, text_elements, page)
                            if safe_rect and safe_rect == rect:
                                # No text overlap, safe to enhance
                                should_rerender = True
                                rerender_reason = f"quality enhancement (DPI {min_dpi:.1f} < {dpi_threshold}, no text overlap)"
                                logger.info(f"Large image at page {page_num} has low DPI ({min_dpi:.1f}), will rerender for quality")
                            else:
                                # Has text overlap - keep original to avoid capturing text
                                logger.info(f"Large image at page {page_num} has low DPI ({min_dpi:.1f}) but has text overlap - "
                                          f"keeping original to avoid capturing text")
                        else:
                            # DPI is acceptable, no need to rerender
                            logger.info(f"Large image at page {page_num} has acceptable DPI ({min_dpi:.1f}), keeping original")
                    
                    # Perform re-rendering if needed
                    if should_rerender:
                        logger.info(f"Re-rendering image at page {page_num} for: {rerender_reason}")
                        # CRITICAL: Use zoom=8.0 to account for PPT scale factor (typically 2.0)
                        # This ensures final DPI > 150 even after scaling
                        zoom = 8.0  # High resolution (288 DPI -> 576 DPI after 2x scale = 288 DPI final)
                        matrix = fitz.Matrix(zoom, zoom)
                        
                        # CRITICAL: Choose alpha parameter based on background type
                        # - For images with black background (lost alpha): use alpha=True to restore transparency
                        # - For images with white background: use alpha=False first, then convert white to transparent
                        # - For other images: use alpha=False to preserve white as content
                        use_alpha = (quality_status == 'process_alpha')  # Only true for black background images
                        
                        region_pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=use_alpha)
                        image_bytes = region_pix.tobytes("png")
                        image_ext = "png"
                        
                        # Update PIL image
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        
                        logger.info(f"Re-rendered image: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, alpha={use_alpha}")
                        
                        # Post-process: Convert white background to transparent if needed
                        if quality_status == 'process_white_bg':
                            logger.info(f"Post-processing: Converting white background to transparent")
                            pil_image = self._convert_white_bg_to_transparent(pil_image)
                            img_io = io.BytesIO()
                            # CRITICAL: Save DPI information to prevent resampling in python-pptx
                            dpi = pil_image.info.get('dpi', (72, 72))
                            pil_image.save(img_io, format='PNG', dpi=dpi)
                            image_bytes = img_io.getvalue()
                            logger.info(f"White-to-transparent conversion complete: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}, DPI={dpi}")
                    
                    # CRITICAL FIX: Normalize coordinates for full-page background images
                    # Full-page backgrounds should start at (0, 0) to prevent negative offsets
                    # that cause layout issues in the final PPTX
                    if is_full_page_background:
                        # For full-page backgrounds, normalize to (0, 0) and use page dimensions
                        x = 0
                        y = 0
                        x2 = page.rect.width
                        y2 = page.rect.height
                        width = page.rect.width
                        height = page.rect.height
                        logger.debug(f"Normalized full-page background coordinates from "
                                   f"({rect.x0:.2f}, {rect.y0:.2f}) to (0, 0)")
                    else:
                        # For regular images, use actual rect coordinates
                        x = rect.x0
                        y = rect.y0
                        x2 = rect.x1
                        y2 = rect.y1
                        width = rect.width
                        height = rect.height

                    element = {
                        'type': 'image',
                        'image_data': image_bytes,
                        'image_format': image_ext,
                        'width_px': pil_image.width,
                        'height_px': pil_image.height,
                        'x': x,
                        'y': y,
                        'x2': x2,
                        'y2': y2,
                        'width': width,
                        'height': height,
                        'image_id': f"page{page_num}_img{img_index}",
                        'was_rerendered': (quality_status == 'rerender' or needs_large_image_enhancement),
                        'is_full_page_background': is_full_page_background  # Mark for bottom layer rendering
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
    
    def _extract_drawings(self, page: fitz.Page, opacity_map: Dict[str, float] = None, page_num: int = 0, 
                         text_elements: List[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract vector drawings and shapes from the page with opacity information.
        
        Args:
            page: PyMuPDF page object
            opacity_map: Mapping of graphics state names to opacity values
            page_num: Page number (0-indexed) for logging
            text_elements: Optional list of text elements for gradient page number detection
            
        Returns:
            Tuple of (drawing_elements, gradient_images)
        """
        drawing_elements = []
        gradient_images = []  # Store gradient images detected
        
        if opacity_map is None:
            opacity_map = {}
        
        try:
            # Get drawing paths
            drawings = page.get_drawings()
            
            # CRITICAL: Detect gradient patterns BEFORE processing individual shapes
            # Gradients are often complex vector patterns (especially in headers/footers)
            # that should be rendered as images instead of being converted to shapes
            # Pass text_elements for page number detection in gradient regions
            gradient_images = self.gradient_detector.detect_and_extract_gradients(
                page, drawings, page_num, text_elements
            )
            
            # Parse content stream to build a position-based opacity map
            opacity_by_position = self._parse_content_stream_opacity_enhanced(page, opacity_map)
            
            # Convert drawings to shape elements
            # CRITICAL: Preserve the PDF drawing order via pdf_index
            # In PDF, elements drawn later appear on top
            # This index will be used for proper z-ordering
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
                    'stroke_width': drawing.get("width", 1),
                    'pdf_index': idx  # CRITICAL: Preserve PDF drawing order
                }
                
                drawing_elements.append(element)
            
            # CRITICAL: Detect borders BEFORE deduplication
            # Borders are created by pairs of overlapping shapes with small offsets
            # We must detect them before deduplication removes the duplicate shapes
            border_elements = self.border_detector.detect_borders_from_shapes(drawing_elements)
            
            # Merge composite shapes (rings, donuts, etc.) BEFORE deduplication
            # This must happen before deduplication to preserve the overlapping shapes
            drawing_elements = self.shape_merger.merge_shapes(drawing_elements)
            
            # Remove exact duplicates (same position + size + colors)
            # This fixes issues like Page 6 where large rectangles are drawn twice
            drawing_elements = self._remove_exact_duplicates(drawing_elements)
            
            # Remove redundant decorative borders (larger path borders that overlap with simpler rectangles)
            # This fixes the duplicate border issue on page 6 of season_report_del.pdf
            drawing_elements = self._remove_redundant_decorative_borders(drawing_elements)
            
            # Now deduplicate overlapping shapes (removes border artifacts)
            drawing_elements = self._deduplicate_overlapping_shapes(drawing_elements)
            
            # Add detected borders after deduplication
            if border_elements:
                # Assign pdf_index to border elements (put them at the end)
                max_index = max([s.get('pdf_index', 0) for s in drawing_elements], default=0)
                for i, border in enumerate(border_elements):
                    border['pdf_index'] = max_index + i + 1
                drawing_elements.extend(border_elements)
            
            # Filter out shapes that are part of detected gradients
            # These shapes have been rendered as images and should not be duplicated as vectors
            if gradient_images:
                original_count = len(drawing_elements)
                drawing_elements = [
                    shape for shape in drawing_elements
                    if not self.gradient_detector.should_exclude_shape_in_gradient(shape, gradient_images)
                ]
                excluded_count = original_count - len(drawing_elements)
                if excluded_count > 0:
                    logger.info(f"Excluded {excluded_count} shape(s) that are part of gradient pattern(s)")
            
            # CRITICAL: DO NOT sort shapes - preserve PDF drawing order
            # The pdf_index field preserves the original PDF drawing order
            # In PDF, elements drawn later appear on top
            # Sorting by heuristics (size, type) breaks correct layering
            logger.info(f"Preserved PDF drawing order for {len(drawing_elements)} shapes")
                
        except Exception as e:
            logger.warning(f"Failed to extract drawings: {e}")
        
        # Return both gradient images and remaining shapes
        # Gradient images will be added to page elements separately
        return drawing_elements, gradient_images
    
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
    
    def _remove_exact_duplicates(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove exact duplicate shapes (same position, size, and colors).
        
        This fixes issues where PDF renders the same shape multiple times,
        like the duplicate card rectangles on page 6.
        
        Args:
            shapes: List of shape elements
            
        Returns:
            List of shapes with exact duplicates removed
        """
        if not shapes:
            return shapes
        
        seen = []
        unique_shapes = []
        
        for shape in shapes:
            # Create a signature for this shape
            # Round coordinates to 0.1pt precision to catch near-exact duplicates
            signature = (
                round(shape.get('x', 0), 1),
                round(shape.get('y', 0), 1),
                round(shape.get('width', 0), 1),
                round(shape.get('height', 0), 1),
                shape.get('fill_color'),
                shape.get('stroke_color')
            )
            
            if signature not in seen:
                seen.append(signature)
                unique_shapes.append(shape)
            else:
                logger.debug(f"Removed exact duplicate at ({shape.get('x'):.1f}, {shape.get('y'):.1f}), "
                           f"size {shape.get('width'):.1f}x{shape.get('height'):.1f}")
        
        removed_count = len(shapes) - len(unique_shapes)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} exact duplicate shape(s)")
        
        return unique_shapes
    
    def _remove_redundant_decorative_borders(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove redundant decorative border shapes that overlap with simpler card border rectangles.
        
        In some PDFs (like season_report_del.pdf page 6), each card has two overlapping white borders:
        1. An outer decorative path border (type='path', made of many line segments)
        2. An inner simple rectangle border (type='rectangle', single rect element)
        
        This creates visual duplication with 2 borders per card instead of 1.
        
        Strategy:
        - Detect pairs of overlapping white-stroke shapes (no fill)
        - If one is a complex path and the other is a simple rectangle
        - And the path completely contains the rectangle
        - Remove the redundant outer decorative path border
        
        Args:
            shapes: List of shape elements
            
        Returns:
            List of shapes with redundant decorative borders removed
        """
        if len(shapes) <= 1:
            return shapes
        
        filtered_shapes = []
        skip_indices = set()
        
        for i, shape1 in enumerate(shapes):
            if i in skip_indices:
                continue
            
            # Check if this is a potential decorative border/background 
            # (path with white stroke, large, either with or without fill)
            is_path1 = shape1.get('shape_type') == 'path'
            stroke_color1 = shape1.get('stroke_color')
            has_white_stroke1 = stroke_color1 and stroke_color1.upper() in ['#FFFFFF', '#FFF']
            is_large1 = shape1.get('width', 0) > 2 and shape1.get('height', 0) > 1
            
            # Accept both filled and unfilled paths as decorative candidates
            is_decorative_candidate = is_path1 and has_white_stroke1 and is_large1
            
            if not is_decorative_candidate:
                filtered_shapes.append(shape1)
                continue
            
            # Look for a simpler overlapping rectangle that this decorative border surrounds
            found_overlap = False
            
            for j, shape2 in enumerate(shapes):
                if i == j or j in skip_indices:
                    continue
                
                # Check if shape2 is a simple rectangle with same stroke properties
                # (regardless of fill - we just need the simpler inner border)
                is_rect2 = shape2.get('shape_type') == 'rectangle'
                stroke_color2 = shape2.get('stroke_color')
                has_white_stroke2 = stroke_color2 and stroke_color2.upper() in ['#FFFFFF', '#FFF']
                is_large2 = shape2.get('width', 0) > 2 and shape2.get('height', 0) > 1
                
                is_simple_border = is_rect2 and has_white_stroke2 and is_large2
                
                if not is_simple_border:
                    continue
                
                # Check if shape1 (decorative path) contains shape2 (simple rectangle)
                # Shape1 should be larger and contain shape2
                x1, y1 = shape1.get('x', 0), shape1.get('y', 0)
                w1, h1 = shape1.get('width', 0), shape1.get('height', 0)
                
                x2, y2 = shape2.get('x', 0), shape2.get('y', 0)
                w2, h2 = shape2.get('width', 0), shape2.get('height', 0)
                
                # Check if shape2 is inside shape1 (with some tolerance)
                tolerance = 30  # 30 points tolerance
                
                # Shape2's bounds should be inside shape1's bounds
                contains_left = x1 <= x2 + tolerance
                contains_top = y1 <= y2 + tolerance
                contains_right = (x1 + w1) >= (x2 + w2) - tolerance
                contains_bottom = (y1 + h1) >= (y2 + h2) - tolerance
                
                # Shape1 should be larger than shape2
                is_larger = w1 > w2 and h1 > h2
                
                if contains_left and contains_top and contains_right and contains_bottom and is_larger:
                    # Found an overlapping simpler rectangle inside this decorative path
                    # Skip the decorative path border (shape1)
                    skip_indices.add(i)
                    found_overlap = True
                    logger.debug(f"Removed redundant decorative border at ({x1:.1f}, {y1:.1f}) "
                               f"size {w1:.1f}x{h1:.1f}, overlaps with simpler rectangle at ({x2:.1f}, {y2:.1f})")
                    break
            
            if not found_overlap:
                filtered_shapes.append(shape1)
        
        removed_count = len(shapes) - len(filtered_shapes)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} redundant decorative border(s)")
        
        return filtered_shapes
    
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
        # Circles use Bezier curves (typically 4 curves for a perfect circle, more for approximations)
        # Key indicators: 4+ curves, aspect ratio near 1.0, curve-dominant structure
        # IMPORTANT: Distinguish between:
        #   - True circles/ovals: curves dominate, lines are just connectors (curve-to-line ratio > 1:1)
        #   - Rounded rectangles: lines dominate, curves are just for corners (curve-to-line ratio < 1:1)
        if curve_count >= 4:
            # Calculate curve dominance ratio
            # A circle has 4 curves and minimal connecting lines (8-10 items typical)
            # A rounded rectangle has 4 curves but many straight lines (20+ items typical)
            curve_to_line_ratio = curve_count / max(line_count, 1)
            total_items = curve_count + line_count
            curve_percentage = (curve_count / total_items) if total_items > 0 else 0
            
            # Strategy: Use multiple signals to distinguish circles from rounded rectangles
            # - Aspect ratio (circles are roughly square: 0.8-1.2)
            # - Curve dominance (circles have curves >= lines)
            # - Total item count (circles are simpler: 8-12 items; rounded rects are more complex: 20+ items)
            
            # Strong circle indicators (high confidence)
            is_square_aspect = 0.8 <= aspect_ratio <= 1.2
            is_curve_dominant = curve_to_line_ratio >= 1.0  # More or equal curves than lines
            is_simple_shape = total_items <= 12  # Circles are simple (typically 8-10 items)
            
            # Check for strong circle signal: square aspect + curve dominant + simple
            if is_square_aspect and is_curve_dominant and is_simple_shape:
                logger.debug(f"Detected circle: {curve_count} curves, {line_count} lines, aspect {aspect_ratio:.3f}, ratio {curve_to_line_ratio:.2f}")
                return 'oval'
            
            # Check for moderate circle signal: square aspect + either curve dominant OR simple
            # This catches cases where lines are used for connection but shape is clearly circular
            if is_square_aspect and (is_curve_dominant or is_simple_shape):
                # Additional check: if curve percentage is high (>40%), likely a circle
                if curve_percentage >= 0.4:
                    logger.debug(f"Detected circle (moderate): {curve_count} curves, {line_count} lines, aspect {aspect_ratio:.3f}, curve% {curve_percentage:.2f}")
                    return 'oval'
            
            # Check for oval/ellipse: elongated but still curve-dominant
            if 0.5 <= aspect_ratio <= 2.0 and is_curve_dominant:
                # Only classify as oval if curves clearly dominate
                if curve_percentage >= 0.5:  # At least 50% curves
                    logger.debug(f"Detected oval/ellipse: {curve_count} curves, {line_count} lines, aspect {aspect_ratio:.3f}")
                    return 'oval'
            
            # Many curves (40+) without line dominance = complex oval approximation
            if curve_count >= 40 and curve_to_line_ratio >= 0.8:
                if 0.5 <= aspect_ratio <= 2.0:
                    logger.debug(f"Detected complex oval: {curve_count} curves, aspect {aspect_ratio:.3f}")
                    return 'oval'
            
            # If we reach here, it's likely a rounded rectangle
            # (low curve-to-line ratio, or extreme aspect ratio, or many items suggesting complex shape)
            logger.debug(f"Detected rounded rectangle: {curve_count} curves, {line_count} lines, aspect {aspect_ratio:.3f}, ratio {curve_to_line_ratio:.2f}")
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
    
    def _sort_shapes_by_layer(self, shapes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort shapes by visual layer order to ensure proper rendering.
        
        Background elements (thin horizontal lines, gridlines) should be rendered first (bottom layer).
        Foreground elements (bars, columns, filled shapes) should be rendered last (top layer).
        
        This fixes issues where PDF internal order places gridlines after bar charts,
        causing gridlines to cover the bars in PowerPoint.
        
        Args:
            shapes: List of shape elements
            
        Returns:
            Sorted list of shape elements
        """
        if not shapes:
            return shapes
        
        # Categorize shapes into layers based on their visual characteristics
        layer_assignments = []
        
        for shape in shapes:
            width = shape.get('width', 0)
            height = shape.get('height', 0)
            shape_type = shape.get('shape_type', 'rectangle')
            fill_color = shape.get('fill_color')
            stroke_color = shape.get('stroke_color')
            
            # Determine layer priority (lower number = render first = bottom layer)
            # Layer 0: Background elements (thin lines, especially horizontal gridlines)
            # Layer 1: Medium elements (decorative shapes, borders)
            # Layer 2: Foreground elements (bars, filled shapes)
            layer = 1  # Default: medium layer
            
            # Detect thin horizontal lines (gridlines, baselines)
            # These are typically gray and span across the chart area
            is_thin_horizontal = (height < 5 and width > 50)
            is_thin_vertical = (width < 5 and height > 50)
            is_thin_line = is_thin_horizontal or is_thin_vertical
            
            # Detect bar chart columns (tall rectangles with fill)
            # These should be on top of gridlines
            is_bar_chart = (height > 20 and width > 10 and width < 200 and fill_color is not None)
            
            # Detect large filled shapes (backgrounds, cards)
            is_large_background = (width > 300 or height > 300) and fill_color is not None
            
            # Layer assignment logic
            if is_thin_line:
                # Thin lines (gridlines) go to background
                layer = 0
                logger.debug(f"Layer 0 (gridline): {width:.1f}x{height:.1f}, fill={fill_color}, stroke={stroke_color}")
            elif is_large_background:
                # Large backgrounds also go to background
                layer = 0
                logger.debug(f"Layer 0 (background): {width:.1f}x{height:.1f}")
            elif is_bar_chart:
                # Bar charts go to foreground
                layer = 2
                logger.debug(f"Layer 2 (bar): {width:.1f}x{height:.1f}, fill={fill_color}")
            elif shape_type in ['oval', 'circle']:
                # Circles and ovals typically foreground decoration
                layer = 2
                logger.debug(f"Layer 2 (circle): {width:.1f}x{height:.1f}")
            elif fill_color and not is_thin_line:
                # Other filled shapes go to foreground
                layer = 2
                logger.debug(f"Layer 2 (filled): {width:.1f}x{height:.1f}, fill={fill_color}")
            else:
                # Everything else stays in medium layer
                layer = 1
            
            layer_assignments.append((layer, shape))
        
        # Sort by layer (ascending), preserving original order within each layer
        layer_assignments.sort(key=lambda x: x[0])
        
        # Extract sorted shapes
        sorted_shapes = [shape for _, shape in layer_assignments]
        
        # Log layer distribution
        layer_counts = {}
        for layer, _ in layer_assignments:
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
        logger.info(f"Layer distribution: {layer_counts}")
        
        return sorted_shapes
    
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
            
            # Check 2: PNG images with black background (lost alpha channel)
            # These are RGB PNG images that should have transparency but have black backgrounds instead
            # This happens when alpha channel is lost during PDF conversion
            #
            # Detection strategy:
            # - RGB mode (no alpha channel)
            # - Significant number of black pixels in corner/edge samples (>= 4 out of 9)
            # - Not purely black (has some non-black content)
            # - Any size can be affected
            
            has_no_alpha = pil_image.mode == 'RGB'
            
            if has_no_alpha:
                # Count black pixels in corner/edge samples
                black_count = sum(1 for p in pixels if all(c < 30 for c in p[:3]))
                
                # Count white pixels in corner/edge samples
                white_count = sum(1 for p in pixels if all(c > 240 for c in p[:3]))
                
                # Check 2a: PNG with black background (lost alpha)
                # If image has significant black edges but is not purely black
                if black_count >= 4 and black_count < len(pixels):
                    # Check if there are also some colored pixels (not just black)
                    has_color = any(max(p[:3]) > 30 for p in pixels)
                    
                    if has_color:
                        # CRITICAL FIX: 这是丢失alpha通道的PNG，但不应该rerender!
                        # rerender会截图，把文字也截进去
                        # 正确做法: 保持原始XObject，通过图像处理添加alpha通道
                        #
                        # QUALITY FIX: Check if this image also needs quality enhancement
                        # LOW DPI THRESHOLD: Lower threshold from 200pt to 50pt to catch small icons/arrows
                        # Small images (like 58x58pt arrows) are especially visible when low DPI
                        # because jagged edges are more prominent at small sizes
                        is_large = rect and (rect.width > 50 or rect.height > 50)
                        needs_enhancement = False
                        
                        if is_large:
                            # Check if this is a decorative image that should NOT be enhanced
                            is_moderate_size = (width < 600 and height < 600)
                            
                            if is_moderate_size:
                                # Check color diversity to determine if decorative
                                img_array = np.array(pil_image)
                                if len(img_array.shape) == 3:
                                    unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                                    is_decorative = (30 <= unique_colors <= 500)
                                    needs_enhancement = not is_decorative
                                else:
                                    needs_enhancement = True
                            else:
                                # Large image (>600px), definitely needs enhancement check
                                needs_enhancement = True
                        
                        logger.info(
                            f"Detected PNG with black background (lost alpha): {width}x{height}px, "
                            f"{black_count}/{len(pixels)} black edge pixels - will add alpha channel via image processing"
                        )
                        # 返回'process_alpha'，并附带needs_large_image_enhancement状态
                        return ('process_alpha', needs_enhancement)
                
                # Check 2b: PNG with white background that should be transparent
                # Detection: RGB mode + significant white pixels + has non-white content
                # This is common in rendered graphics/diagrams that should have transparent backgrounds
                # 
                # CRITICAL: Must exclude decorative images (30-500 unique colors)
                # Decorative images' white pixels are part of the design, not background
                if white_count >= 4 and white_count < len(pixels):
                    # Check if there are also some colored pixels (not just white)
                    has_color = any(min(p[:3]) < 240 for p in pixels)
                    
                    if has_color:
                        # CRITICAL: Check if this is a decorative image BEFORE processing
                        # Decorative images should NOT have white background converted to transparent
                        is_moderate_size = (width < 600 and height < 600)
                        
                        if is_moderate_size:
                            # Check color diversity to determine if decorative
                            img_array = np.array(pil_image)
                            if len(img_array.shape) == 3:
                                unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                                is_decorative = (30 <= unique_colors <= 500)
                                
                                if is_decorative:
                                    # This is a decorative image - do NOT convert white to transparent
                                    # White pixels are part of the design, not background
                                    logger.info(
                                        f"Detected decorative image with white pixels: {width}x{height}px, "
                                        f"{unique_colors} colors - will NOT convert white to transparent"
                                    )
                                    # Skip white background processing for decorative images
                                    # Continue to next checks
                                else:
                                    # Not decorative, has white background that should be transparent
                                    # LOWERED THRESHOLD: 50pt instead of 200pt to catch small icons
                                    is_large = rect and (rect.width > 50 or rect.height > 50)
                                    needs_enhancement = is_large  # Large non-decorative images need enhancement
                                    
                                    logger.info(
                                        f"Detected PNG with white background (should be transparent): {width}x{height}px, "
                                        f"{white_count}/{len(pixels)} white edge pixels, {unique_colors} colors - will convert white to transparent"
                                    )
                                    return ('process_white_bg', needs_enhancement)
                            else:
                                # Can't analyze colors, treat as white background
                                # LOWERED THRESHOLD: 50pt instead of 200pt
                                is_large = rect and (rect.width > 50 or rect.height > 50)
                                needs_enhancement = is_large
                                
                                logger.info(
                                    f"Detected PNG with white background (should be transparent): {width}x{height}px, "
                                    f"{white_count}/{len(pixels)} white edge pixels - will convert white to transparent"
                                )
                                return ('process_white_bg', needs_enhancement)
                        else:
                            # Large image (>600px), likely needs white-to-transparent conversion
                            # LOWERED THRESHOLD: 50pt instead of 200pt
                            is_large = rect and (rect.width > 50 or rect.height > 50)
                            needs_enhancement = is_large
                            
                            logger.info(
                                f"Detected PNG with white background (should be transparent): {width}x{height}px, "
                                f"{white_count}/{len(pixels)} white edge pixels - will convert white to transparent"
                            )
                            return ('process_white_bg', needs_enhancement)
            
            # Check 3: Low-quality embedded icon detection
            # These are small PNG icons with no alpha channel and limited colors
            # IMPORTANT: This check only applies to embedded images, NOT vector shapes
            
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
            
            # Check 4: Large PNG images - NOW ENABLED with smart overlap detection
            # 
            # CRITICAL FIX v2: We NOW enable large image rerendering but with smart overlap detection.
            # The _extract_images method will call _calculate_safe_rerender_bbox to:
            # - Detect overlaps with text/shapes BEFORE rerendering
            # - Shrink the rerender bbox to exclude overlapping regions
            # - Only rerender the safe, non-overlapping portion
            #
            # This solves the duplication issue while still improving image quality.
            #
            # CRITICAL FIX v3: Exclude decorative images from large image enhancement
            # Decorative images are intentional design elements with moderate color diversity
            # that should NOT be rerendered as this can cause heavy cropping due to text overlaps
            #
            # Check if this is a large image that could benefit from enhancement
            # LOWERED THRESHOLD: 50pt instead of 200pt to catch small icons/arrows
            is_large = rect and (rect.width > 50 or rect.height > 50)
            needs_large_image_enhancement = False
            
            if is_large and pil_image.mode == 'RGB':
                # Check if this is a decorative image (should not be rerendered)
                # Decorative images have:
                # - Moderate dimensions (< 600px in both dimensions)
                # - Moderate color diversity (between 30-500 unique colors)
                # - These are intentional embedded design elements
                is_moderate_size = (width < 600 and height < 600)
                
                if is_moderate_size:
                    # Check color diversity
                    img_array = np.array(pil_image)
                    if len(img_array.shape) == 3:
                        unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
                        is_decorative = (30 <= unique_colors <= 500)
                        
                        if is_decorative:
                            # This is likely a decorative image - do NOT rerender
                            # Rerendering would cause heavy cropping due to text overlaps
                            logger.info(
                                f"Detected decorative image: {width}x{height}px, {unique_colors} colors - "
                                f"will keep as-is without rerendering to preserve design"
                            )
                            needs_large_image_enhancement = False
                        else:
                            # Not decorative, proceed with enhancement
                            needs_large_image_enhancement = True
                            logger.debug(
                                f"Detected large PNG image: {width}x{height}px - may re-render if no text/shape overlaps"
                            )
                    else:
                        # Can't analyze, proceed with enhancement
                        needs_large_image_enhancement = True
                        logger.debug(
                            f"Detected large PNG image: {width}x{height}px - may re-render if no text/shape overlaps"
                        )
                else:
                    # Very large image, likely needs enhancement
                    needs_large_image_enhancement = True
                    logger.debug(
                        f"Detected large PNG image: {width}x{height}px - may re-render if no text/shape overlaps"
                    )
            
            # Check 5: Low-quality rasterized vector graphics
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
                                       page: fitz.Page, allow_minor_overlap: bool = True, 
                                       overlap_threshold: float = 0.10) -> Optional[fitz.Rect]:
        """
        Calculate a safe bounding box for rerendering an image that avoids overlapping text/shapes.
        
        This method detects overlaps between the image bbox and text/shape bboxes, then shrinks
        the image bbox to exclude the overlapping regions. It tries all four shrink directions
        (top, bottom, left, right) and chooses the one that preserves the most area.
        
        Args:
            img_rect: Original image rectangle
            text_elements: List of already-extracted text elements
            page: PyMuPDF page object for shape detection
            allow_minor_overlap: If True, allow rerendering if total overlap < threshold
            overlap_threshold: Maximum allowed overlap ratio (default 0.10 = 10%)
            
        Returns:
            Safe rectangle for rerendering (or original if overlap is acceptable), or None if unsafe
        """
        # Start with the original rect
        safe_rect = fitz.Rect(img_rect)
        margin = 2.0  # Add small margin to avoid edge overlaps
        
        # Track total overlap for minor overlap tolerance
        total_overlap_area = 0.0
        overlapping_texts = []
        
        # Check overlaps with text elements
        for text_elem in text_elements:
            text_bbox = (text_elem['x'], text_elem['y'], text_elem['x2'], text_elem['y2'])
            text_rect = fitz.Rect(text_bbox)
            
            # Check if text overlaps with current safe_rect
            if safe_rect.intersects(text_rect):
                # Calculate overlap area to filter out trivial overlaps
                overlap_rect = safe_rect & text_rect
                overlap_area = overlap_rect.width * overlap_rect.height if overlap_rect else 0
                
                # CRITICAL: Ignore trivial overlaps (< 100 pt²)
                # These are typically edge cases where text barely touches image
                # Rerendering won't capture such minimal overlaps
                if overlap_area < 100:
                    logger.debug(f"Ignoring trivial overlap ({overlap_area:.1f} pt²) with text "
                               f"'{text_elem.get('content', '')[:20]}...'")
                    continue
                
                # Track overlap
                total_overlap_area += overlap_area
                overlapping_texts.append((text_elem.get('content', '')[:30], overlap_area))
                
                # Text overlaps - we need to shrink safe_rect to avoid it
                logger.debug(f"Text '{text_elem.get('content', '')[:20]}...' overlaps image at "
                           f"({text_rect.x0:.1f}, {text_rect.y0:.1f}, {text_rect.x1:.1f}, {text_rect.y1:.1f})")
                
                # Try all four shrink directions and calculate resulting areas
                # This ensures we choose the best option that preserves the most image content
                shrink_options = []
                
                # Option 1: Shrink from top (move top edge down to below text)
                top_rect = fitz.Rect(safe_rect)
                top_rect.y0 = text_rect.y1 + margin
                if top_rect.y0 < top_rect.y1:
                    top_area = top_rect.width * top_rect.height
                    shrink_options.append(('top', top_rect, top_area))
                    logger.debug(f"  Option: shrink top to y={top_rect.y0:.1f}, area={top_area:.1f}")
                
                # Option 2: Shrink from bottom (move bottom edge up to above text)
                bottom_rect = fitz.Rect(safe_rect)
                bottom_rect.y1 = text_rect.y0 - margin
                if bottom_rect.y1 > bottom_rect.y0:
                    bottom_area = bottom_rect.width * bottom_rect.height
                    shrink_options.append(('bottom', bottom_rect, bottom_area))
                    logger.debug(f"  Option: shrink bottom to y={bottom_rect.y1:.1f}, area={bottom_area:.1f}")
                
                # Option 3: Shrink from left (move left edge right to avoid text)
                left_rect = fitz.Rect(safe_rect)
                left_rect.x0 = text_rect.x1 + margin
                if left_rect.x0 < left_rect.x1:
                    left_area = left_rect.width * left_rect.height
                    shrink_options.append(('left', left_rect, left_area))
                    logger.debug(f"  Option: shrink left to x={left_rect.x0:.1f}, area={left_area:.1f}")
                
                # Option 4: Shrink from right (move right edge left to avoid text)
                right_rect = fitz.Rect(safe_rect)
                right_rect.x1 = text_rect.x0 - margin
                if right_rect.x1 > right_rect.x0:
                    right_area = right_rect.width * right_rect.height
                    shrink_options.append(('right', right_rect, right_area))
                    logger.debug(f"  Option: shrink right to x={right_rect.x1:.1f}, area={right_area:.1f}")
                
                # Choose the option with the largest remaining area
                if shrink_options:
                    best_option = max(shrink_options, key=lambda opt: opt[2])
                    direction, safe_rect, area = best_option
                    logger.debug(f"  Chose best option: shrink {direction}, area={area:.1f}")
                else:
                    # No valid shrink options - text covers entire image
                    logger.warning(f"No valid shrink options for overlapping text")
                    return None
        
        # Check if we actually shrunk the rect
        if safe_rect != img_rect:
            # We shrunk the rect - check if minor overlap tolerance applies
            if allow_minor_overlap and total_overlap_area > 0:
                image_area = img_rect.width * img_rect.height
                overlap_ratio = total_overlap_area / image_area if image_area > 0 else 0
                
                if overlap_ratio <= overlap_threshold:
                    # Minor overlap is acceptable - use original rect
                    logger.info(f"Allowing minor text overlap ({overlap_ratio*100:.1f}% < {overlap_threshold*100:.0f}%) "
                              f"for quality enhancement: {len(overlapping_texts)} texts, "
                              f"total {total_overlap_area:.1f} pt² overlap")
                    for text, area in overlapping_texts[:3]:
                        logger.debug(f"  Overlapping: '{text}' ({area:.1f} pt²)")
                    return img_rect  # Use original rect
            
            # Overlap is significant - use shrunk rect
            logger.info(f"Calculated safe rerender bbox: "
                      f"original ({img_rect.x0:.1f}, {img_rect.y0:.1f}, {img_rect.x1:.1f}, {img_rect.y1:.1f}), "
                      f"safe ({safe_rect.x0:.1f}, {safe_rect.y0:.1f}, {safe_rect.x1:.1f}, {safe_rect.y1:.1f})")
            
            # Check if the shrunk rect is still large enough
            if safe_rect.width < 20 or safe_rect.height < 20:
                logger.warning(f"Safe rerender bbox too small ({safe_rect.width:.1f}x{safe_rect.height:.1f}), "
                             f"will not rerender")
                return None
            
            return safe_rect
        else:
            # No overlap, safe to rerender entire image
            return img_rect
    
    def _check_background_for_header_footer(self, page: fitz.Page, rect: fitz.Rect, 
                                            page_num: int, region: str) -> bool:
        """
        Intelligently check if a background image contains important header or footer content.
        
        Uses smart content analysis to distinguish decorative elements from actual content:
        - Detects text elements (excluding page numbers)
        - Detects vector shapes (lines, rectangles, etc.)
        - Uses dynamic boundary detection based on actual content position
        
        Args:
            page: PyMuPDF page object
            rect: Rectangle of the background image
            page_num: Page number
            region: 'header' or 'footer'
            
        Returns:
            True if the region contains non-decorative content (excluding page numbers)
        """
        page_height = page.rect.height
        page_width = page.rect.width
        
        # STEP 1: Extract all text elements from the page
        text_dict = page.get_text("dict")
        text_elements = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text = span.get("text", "").strip()
                        if text:
                            text_elements.append({
                                'text': text,
                                'y': bbox[1],
                                'y2': bbox[3],
                                'bbox': bbox
                            })
        
        # STEP 2: Detect page numbers (pattern: N/M or just N)
        # Page numbers are typically centered, small, at very bottom/top
        def is_page_number(elem):
            text = elem['text']
            # Pattern 1: "N/M" format (e.g., "6/10", "1/10")
            if re.match(r'^\d+/\d+$', text):
                return True
            # Pattern 2: Single number at extreme edge
            if text.isdigit():
                bbox = elem['bbox']
                x_center = (bbox[0] + bbox[2]) / 2
                # Check if centered horizontally (middle 20% of page)
                is_centered = 0.4 * page_width < x_center < 0.6 * page_width
                # Check if at extreme top or bottom
                is_extreme_top = elem['y'] < page_height * 0.05
                is_extreme_bottom = elem['y'] > page_height * 0.95
                return is_centered and (is_extreme_top or is_extreme_bottom)
            return False
        
        page_numbers = [elem for elem in text_elements if is_page_number(elem)]
        non_page_text = [elem for elem in text_elements if not is_page_number(elem)]
        
        # STEP 3: Find content boundaries dynamically
        # Determine where actual content starts/ends based on text distribution
        if not non_page_text:
            # No actual text content, check for shapes
            drawings = page.get_drawings()
            if not drawings:
                return False  # No content at all
            
            # Use shape positions
            y_positions = [d.get('rect').y0 for d in drawings if d.get('rect')]
            if not y_positions:
                return False
        else:
            y_positions = [elem['y'] for elem in non_page_text]
        
        y_positions.sort()
        
        # Find content region boundaries
        # Content starts at first non-page-number element
        # Content ends at last non-page-number element
        content_top = y_positions[0] if y_positions else 0
        content_bottom = y_positions[-1] if y_positions else page_height
        
        # STEP 4: Define header/footer region intelligently
        if region == 'header':
            # Header: from page top to first content
            # BUT: Must have sufficient gap (at least 20pt) from content
            header_threshold = content_top - 5  # 5pt buffer
            
            # Check if there are shapes or text in the header area
            header_shapes = [d for d in page.get_drawings() 
                           if d.get('rect') and d.get('rect').y0 < header_threshold]
            header_text = [elem for elem in non_page_text if elem['y'] < header_threshold]
            
            has_header_content = len(header_shapes) > 0 or len(header_text) > 0
            
            if has_header_content:
                logger.info(f"Page {page_num} header: found {len(header_shapes)} shapes, "
                          f"{len(header_text)} text elements above y={header_threshold:.1f}")
            
            return has_header_content
            
        elif region == 'footer':
            # Footer: from last content to page bottom
            # BUT: Must have sufficient gap (at least 15pt) from content
            # AND: Must exclude table content that's close to bottom
            
            # Find the last significant content Y position
            # Exclude elements that are too close to page bottom (likely page numbers)
            significant_content = [y for y in y_positions if y < page_height * 0.90]
            
            if significant_content:
                content_bottom = significant_content[-1]
            
            # Footer region starts after a gap from last content
            footer_threshold = content_bottom + 10  # 10pt buffer
            
            # CRITICAL: Check if there's actual table/list content near the bottom
            # Tables/lists have multiple rows with consistent patterns
            near_bottom_text = [elem for elem in non_page_text 
                              if elem['y'] > page_height * 0.75]
            
            if len(near_bottom_text) >= 3:
                # Multiple text elements near bottom - check if this is table content
                # Strategy: Look for rows with similar Y positions (table rows)
                # Group text by Y position (within 2pt tolerance)
                y_positions = sorted(set(round(e['y'], 0) for e in near_bottom_text))
                
                # If we have multiple distinct rows (3+), it's likely a table
                if len(y_positions) >= 3:
                    # Check if the last content item is close to bottom (within 15% of page)
                    last_y = y_positions[-1]
                    if last_y > page_height * 0.85:
                        logger.info(f"Page {page_num} detected table/list content near bottom "
                                  f"({len(y_positions)} rows, last at y={last_y:.1f}), "
                                  f"skipping footer extraction")
                        return False  # This is table content, not footer
            
            # Check for shapes in the footer area (decorative elements)
            footer_shapes = [d for d in page.get_drawings() 
                           if d.get('rect') and d.get('rect').y1 > footer_threshold]
            
            # Filter out page number text
            footer_text = [elem for elem in non_page_text if elem['y'] > footer_threshold]
            
            # Footer has content if there are shapes (decorative lines, gradients)
            # BUT NOT if there's significant text (that would be actual content)
            has_footer_shapes = len(footer_shapes) > 0
            has_footer_text = len(footer_text) > 0
            
            # Accept footer if it has shapes but no significant text
            # OR if it has very minimal text (1-2 words, likely decorative)
            has_footer_content = has_footer_shapes and not has_footer_text
            
            if has_footer_content:
                logger.info(f"Page {page_num} footer: found {len(footer_shapes)} shapes, "
                          f"{len(footer_text)} text elements below y={footer_threshold:.1f}")
            
            return has_footer_content
        
        return False
    
    def _add_alpha_channel_to_png(self, pil_image: Image.Image) -> Image.Image:
        """
        Add alpha channel to RGB PNG image by making black pixels transparent.
        
        This method is used for PNG images that lost their alpha channel during PDF conversion.
        Black pixels (RGB < 30) are converted to transparent.
        
        IMPORTANT: This is image processing on the original XObject, NOT page rendering.
        The original XObject never contains text, so this method won't capture text.
        
        CRITICAL FIX: Preserve DPI information to prevent python-pptx from resampling
        the image during insertion, which can cause color distortion.
        
        Args:
            pil_image: PIL Image in RGB mode
            
        Returns:
            PIL Image in RGBA mode with alpha channel
        """
        if pil_image.mode == 'RGBA':
            # Already has alpha
            return pil_image
        
        # CRITICAL: Save original DPI information before processing
        original_dpi = pil_image.info.get('dpi', (72, 72))
        
        # Convert RGB to RGBA
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Add alpha channel
        import numpy as np
        img_array = np.array(pil_image)
        
        # Create alpha channel (255 = opaque)
        alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
        
        # Make black pixels transparent (R,G,B < 30 → alpha = 0)
        black_mask = np.all(img_array < 30, axis=2)
        alpha[black_mask] = 0
        
        # Combine RGB + Alpha
        rgba_array = np.dstack((img_array, alpha))
        
        # Convert back to PIL Image
        result_image = Image.fromarray(rgba_array, mode='RGBA')
        
        # CRITICAL: Restore DPI information to prevent resampling
        result_image.info['dpi'] = original_dpi
        
        return result_image
    
    def _convert_white_bg_to_transparent(self, pil_image: Image.Image) -> Image.Image:
        """
        Convert white background to transparent for RGB PNG images.
        
        This method is used for PNG images with white backgrounds that should be transparent
        (e.g., rendered graphics, diagrams). White pixels (RGB > 240) are converted to transparent.
        
        IMPORTANT: This is image processing on the original XObject, NOT page rendering.
        The original XObject never contains text, so this method won't capture text.
        
        CRITICAL FIX: Preserve DPI information to prevent python-pptx from resampling
        the image during insertion, which can cause color distortion.
        
        Args:
            pil_image: PIL Image in RGB mode
            
        Returns:
            PIL Image in RGBA mode with transparent white background
        """
        # CRITICAL: Save original DPI information before processing
        original_dpi = pil_image.info.get('dpi', (72, 72))
        
        if pil_image.mode == 'RGBA':
            # Already has alpha - convert white to transparent
            import numpy as np
            img_array = np.array(pil_image)
            
            # Make white pixels transparent (R,G,B > 240 → alpha = 0)
            white_mask = np.all(img_array[:, :, :3] > 240, axis=2)
            img_array[:, :, 3][white_mask] = 0
            
            result_image = Image.fromarray(img_array, mode='RGBA')
            # CRITICAL: Restore DPI information
            result_image.info['dpi'] = original_dpi
            return result_image
        
        # Convert RGB to RGBA
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Add alpha channel
        import numpy as np
        img_array = np.array(pil_image)
        
        # Create alpha channel (255 = opaque)
        alpha = np.ones((img_array.shape[0], img_array.shape[1]), dtype=np.uint8) * 255
        
        # Make white pixels transparent (R,G,B > 240 → alpha = 0)
        white_mask = np.all(img_array > 240, axis=2)
        alpha[white_mask] = 0
        
        # Combine RGB + Alpha
        rgba_array = np.dstack((img_array, alpha))
        
        # Convert back to PIL Image
        result_image = Image.fromarray(rgba_array, mode='RGBA')
        
        # CRITICAL: Restore DPI information to prevent resampling
        result_image.info['dpi'] = original_dpi
        
        return result_image
    
    def _extract_header_footer_from_background(self, page: fitz.Page, rect: fitz.Rect, 
                                               page_num: int, region: str) -> Dict[str, Any]:
        """
        Intelligently extract header or footer region using dynamic content boundaries.
        
        This method dynamically calculates extraction region based on actual content position,
        excluding page numbers and avoiding capturing table content.
        
        Args:
            page: PyMuPDF page object
            rect: Rectangle of the background image
            page_num: Page number
            region: 'header' or 'footer'
            
        Returns:
            Image element dictionary, or None if extraction fails
        """
        page_height = page.rect.height
        page_width = page.rect.width
        
        # STEP 1: Extract text to find content boundaries
        text_dict = page.get_text("dict")
        text_elements = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text = span.get("text", "").strip()
                        if text:
                            text_elements.append({'text': text, 'y': bbox[1], 'bbox': bbox})
        
        # STEP 2: Filter out page numbers
        def is_page_number(elem):
            text = elem['text']
            if re.match(r'^\d+/\d+$', text):
                return True
            if text.isdigit():
                bbox = elem['bbox']
                x_center = (bbox[0] + bbox[2]) / 2
                is_centered = 0.4 * page_width < x_center < 0.6 * page_width
                is_extreme_edge = elem['y'] < page_height * 0.05 or elem['y'] > page_height * 0.95
                return is_centered and is_extreme_edge
            return False
        
        non_page_text = [e for e in text_elements if not is_page_number(e)]
        
        # STEP 3: Find content boundaries
        if non_page_text:
            y_positions = sorted([e['y'] for e in non_page_text])
            content_top = y_positions[0]
            content_bottom = y_positions[-1]
        else:
            drawings = page.get_drawings()
            y_positions = [d.get('rect').y0 for d in drawings if d.get('rect')]
            if not y_positions:
                return None
            y_positions.sort()
            content_top = y_positions[0]
            content_bottom = y_positions[-1]
        
        # STEP 4: Define extraction region intelligently
        if region == 'header':
            extract_rect = fitz.Rect(0, 0, page_width, min(content_top - 2, page_height * 0.15))
            if extract_rect.height < 10:
                logger.debug(f"Header region too small, skipping")
                return None
        elif region == 'footer':
            significant_y = [y for y in y_positions if y < page_height * 0.90]
            if significant_y:
                content_bottom = significant_y[-1]
            footer_start = max(content_bottom + 10, page_height * 0.85)
            extract_rect = fitz.Rect(0, footer_start, page_width, page_height)
            if extract_rect.height < 8:
                logger.debug(f"Footer region too small, skipping")
                return None
        else:
            return None
        
        try:
            # Render at high resolution for quality
            zoom = 3.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, clip=extract_rect, alpha=True)
            
            # Convert to bytes
            image_data = pix.tobytes("png")
            
            # Get image dimensions
            img = Image.open(io.BytesIO(image_data))
            width_px = img.width
            height_px = img.height
            
            # Create image element
            image_elem = {
                'type': 'image',
                'image_data': image_data,
                'image_format': 'png',
                'width_px': width_px,
                'height_px': height_px,
                'x': extract_rect.x0,
                'y': extract_rect.y0,
                'x2': extract_rect.x1,
                'y2': extract_rect.y1,
                'width': extract_rect.width,
                'height': extract_rect.height,
                'image_id': f"page{page_num}_{region}",
                'is_header_footer': True,
                'region_type': region
            }
            
            logger.info(f"Extracted {region} from background at page {page_num}: "
                       f"{width_px}x{height_px}px, position ({extract_rect.x0:.1f}, {extract_rect.y0:.1f})")
            
            return image_elem
            
        except Exception as e:
            logger.warning(f"Failed to extract {region} from background: {e}")
            return None
    
    def _filter_page_numbers_in_screenshots(self, text_elements: List[Dict[str, Any]], 
                                            header_footer_regions: List[Dict[str, Any]], 
                                            page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Filter out page number text boxes that fall within header/footer screenshot regions.
        
        When we take header/footer screenshots, they include page numbers. We need to prevent
        creating separate text boxes for those page numbers to avoid duplication.
        
        Args:
            text_elements: List of text elements
            header_footer_regions: List of header/footer screenshot regions with bbox
            page: PyMuPDF page object
            
        Returns:
            Filtered list of text elements with page numbers in screenshots removed
        """
        if not header_footer_regions:
            # No header/footer screenshots, return all text elements
            return text_elements
        
        page_width = page.rect.width
        page_height = page.rect.height
        
        # Define page number detection function (same logic as in header/footer detection)
        def is_page_number(elem):
            text = elem.get('content', '').strip()
            if not text:
                return False
            
            # Pattern 1: "N/M" format (e.g., "6/10", "1/10")
            if re.match(r'^\d+/\d+$', text):
                return True
            
            # Pattern 2: Single number at extreme edge (centered)
            if text.isdigit():
                x = elem.get('x', 0)
                x2 = elem.get('x2', 0)
                y = elem.get('y', 0)
                
                x_center = (x + x2) / 2
                is_centered = 0.4 * page_width < x_center < 0.6 * page_width
                is_extreme_top = y < page_height * 0.05
                is_extreme_bottom = y > page_height * 0.95
                
                return is_centered and (is_extreme_top or is_extreme_bottom)
            
            return False
        
        # Check if a text element overlaps with any header/footer region
        def overlaps_with_region(elem, regions):
            elem_bbox = (elem['x'], elem['y'], elem['x2'], elem['y2'])
            
            for region in regions:
                region_bbox = region['bbox']
                
                # Check if text element center is within the region
                elem_center_x = (elem_bbox[0] + elem_bbox[2]) / 2
                elem_center_y = (elem_bbox[1] + elem_bbox[3]) / 2
                
                if (region_bbox[0] <= elem_center_x <= region_bbox[2] and
                    region_bbox[1] <= elem_center_y <= region_bbox[3]):
                    return True, region['type']
            
            return False, None
        
        # Filter out page numbers that are within header/footer screenshot regions
        filtered_elements = []
        filtered_count = 0
        
        for elem in text_elements:
            if elem.get('type') != 'text':
                filtered_elements.append(elem)
                continue
            
            if is_page_number(elem):
                overlaps, region_type = overlaps_with_region(elem, header_footer_regions)
                if overlaps:
                    # This page number is within a header/footer screenshot, filter it out
                    logger.info(f"Filtering page number '{elem.get('content')}' at y={elem.get('y'):.1f} "
                              f"(already included in {region_type} screenshot)")
                    filtered_count += 1
                    continue
            
            filtered_elements.append(elem)
        
        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} page number text box(es) to prevent duplication with screenshots")
        
        return filtered_elements
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
