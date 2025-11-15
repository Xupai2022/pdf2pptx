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
        # PDF scale correction (PDF is 75% of HTML, multiply by 1.333 to restore)
        self.pdf_to_html_scale = config.get('pdf_to_html_scale', 1.0)
        # Border width correction (PDF borders are thicker than expected)
        self.border_width_correction = config.get('border_width_correction', 1.0)
        logger.info(f"CoordinateMapper: slide {self.slide_width:.3f}×{self.slide_height:.3f}\", PDF scale: {self.pdf_to_html_scale}, border correction: {self.border_width_correction}")
    
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

        # CRITICAL FIX: Use 1:1 scale to preserve exact PDF dimensions and font sizes
        # This ensures:
        # - PDF 18pt font → PPT 18pt font (no size change)
        # - Images, shapes maintain exact sizes
        # - No artificial scaling that causes oversized fonts
        # 
        # The slide dimensions will automatically match PDF dimensions
        self.pdf_to_html_scale = 1.0
        
        # Update slide dimensions to match PDF (convert pt to inches at 72 DPI)
        if pdf_width > 0 and pdf_height > 0:
            self.slide_width = pdf_width / 72.0
            self.slide_height = pdf_height / 72.0
            logger.info(f"1:1 scale mode: PDF {pdf_width:.0f}×{pdf_height:.0f}pt → PPT {self.slide_width:.2f}×{self.slide_height:.2f}\" (no scaling)")
        else:
            logger.warning(f"Invalid PDF dimensions: {pdf_width}×{pdf_height}, using config defaults")
            self.pdf_to_html_scale = 1.0

        slide = SlideModel(slide_num, self.slide_width, self.slide_height)
        # Store the scale factor for use by StyleMapper
        slide.scale_factor = self.pdf_to_html_scale

        # CRITICAL FIX: Check if this is a first/last page with full-page background
        # For first and last pages with full-page background images (is_background=True),
        # we should ONLY render the background image and text elements.
        # All other style elements (shapes, borders, decorations) should be filtered out
        # because they are already included in the background image.
        layout_regions = layout_data.get('layout', [])
        has_background_image = False
        
        # Check if any image region has is_background=True (full-page background for first/last pages)
        for region in layout_regions:
            if region.get('role') == 'image':
                for elem in region.get('elements', []):
                    if elem.get('type') == 'image' and elem.get('is_background', False):
                        has_background_image = True
                        logger.info(f"Slide {slide_num}: Detected full-page background image "
                                   f"(first/last page mode) - will filter out shape elements")
                        break
                if has_background_image:
                    break
        
        # Process layout regions with filtering if needed
        for region in layout_regions:
            self._process_region(region, slide, pdf_width, pdf_height, 
                                filter_shapes=has_background_image)

        # Sort elements by z-index
        slide.sort_elements()

        return slide
    
    def _process_region(self, region: Dict[str, Any], slide: SlideModel, 
                       pdf_width: float, pdf_height: float, filter_shapes: bool = False):
        """
        Process a layout region and add to slide model.
        
        Args:
            region: Layout region from analyzer
            slide: Target slide model
            pdf_width: PDF page width
            pdf_height: PDF page height
            filter_shapes: If True, skip all shape/decoration elements (for first/last pages)
        """
        role = region.get('role', 'unknown')
        bbox = region.get('bbox', [0, 0, 0, 0])
        elements = region.get('elements', [])
        z_index = region.get('z_index', 0)
        
        # CRITICAL FIX: For first/last pages with full-page background images,
        # filter out all shape/decoration elements as they're already in the background
        if filter_shapes and role in ['shape', 'decoration', 'card_background', 'border', 'background']:
            logger.debug(f"Slide {slide.slide_number}: Filtering out {role} elements "
                        f"(already included in full-page background image)")
            return  # Skip processing this region entirely
        
        # Convert bbox to normalized coordinates
        position = self._pdf_to_slide_coords(bbox, pdf_width, pdf_height)
        
        if role in ['title', 'subtitle', 'heading', 'text', 'paragraph', 'header', 'footer']:
            # CRITICAL FIX: Create individual textboxes for each text element to prevent overlaps
            # Issue: Previously, all text elements in a region were merged into one large textbox
            # with the region's bbox, causing overlaps when Chinese text and numbers are adjacent.
            # 
            # Solution: Create separate textboxes for each text element using its own bbox.
            # This preserves the precise positioning from PDF and prevents artificial overlaps.
            
            # Check if this region contains multiple discrete text elements
            # If so, create individual textboxes instead of merging
            text_elements = [e for e in elements if e.get('type') == 'text']
            
            if len(text_elements) > 1:
                # Multiple text elements - create individual textboxes for each
                # Group elements by line (same Y position) and process each line
                # This allows us to fix overlaps within each line
                
                # Group by line
                lines = {}
                for elem in text_elements:
                    y_key = round(elem.get('y', 0))  # Round to nearest pt for grouping
                    if y_key not in lines:
                        lines[y_key] = []
                    lines[y_key].append(elem)
                
                # Process each line
                for y_key in sorted(lines.keys()):
                    line_elements = sorted(lines[y_key], key=lambda e: e.get('x', 0))
                    
                    # Track the rightmost x2 to prevent overlaps
                    prev_x2 = None
                    
                    for i, elem in enumerate(line_elements):
                        text = elem.get('content', '')
                        if text:
                            elem_bbox = [elem['x'], elem['y'], elem['x2'], elem['y2']]
                            
                            # OVERLAP FIX: Ensure no overlaps with previous element on same line
                            # PDF may have micro-overlaps (<1pt) or even larger overlaps
                            if prev_x2 is not None:
                                gap = elem_bbox[0] - prev_x2
                                # If overlap detected (gap < 0), shift this element right
                                if gap < 0:
                                    shift = abs(gap) + 0.5  # Add 0.5pt buffer
                                    elem_bbox[0] = prev_x2 + 0.5
                                    elem_bbox[2] = elem_bbox[0] + (elem['x2'] - elem['x'])  # Keep width
                                    logger.debug(f"Fixed overlap: '{text[:20]}' shifted right by {shift:.2f}pt")
                            
                            # Update prev_x2 for next element
                            prev_x2 = elem_bbox[2]
                            
                            elem_position = self._pdf_to_slide_coords(elem_bbox, pdf_width, pdf_height)
                            elem_style = {
                                'font_name': elem.get('font_name', 'Arial'),
                                'font_size': elem.get('font_size', 18),
                                'color': elem.get('color', '#000000'),
                                'bold': elem.get('is_bold', False),
                                'italic': elem.get('is_italic', False),
                                'rotation': elem.get('rotation', 0)
                            }
                            
                            # Title role is only for the first element
                            if role == 'title' and elem == line_elements[0] and y_key == min(lines.keys()):
                                slide.set_title(text)
                            
                            slide.add_text(text, elem_position, elem_style, z_index)
            else:
                # Single text element or merged region - use region bbox
                text = region.get('text', '')
                if not text:
                    # Fallback: merge element text manually
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
                    
                    # Apply border width correction for thin vertical shapes (card borders)
                    # PDF generates card borders at 5.55pt, but HTML specifies 4px
                    elem_width = elem['x2'] - elem['x']
                    elem_height = elem['y2'] - elem['y']
                    is_vertical_border = (elem_height > elem_width and 4 < elem_width < 7)  # Vertical border around 5.55pt
                    is_border = is_vertical_border
                    if is_border:
                        logger.debug(f"Found border shape: {elem_width:.2f} × {elem_height:.2f} pt, role={role}")
                    
                    # For lines, preserve endpoint coordinates to maintain direction (/ vs \)
                    is_line = shape_type == 'line'
                    
                    style = {
                        'fill_color': elem.get('fill_color'),
                        'fill_opacity': elem.get('fill_opacity', 1.0),
                        'stroke_color': elem.get('stroke_color'),
                        'stroke_width': elem.get('stroke_width', 1),
                        'role': role,  # Pass role to style for transparency mapping
                        'is_border': is_border,  # Flag for border-specific handling
                        'is_ring': elem.get('is_ring', False),  # Flag for ring shapes
                        'ring_color': elem.get('ring_color')  # Original ring color if applicable
                    }
                    shape_position = self._pdf_to_slide_coords(
                        [elem['x'], elem['y'], elem['x2'], elem['y2']],
                        pdf_width, pdf_height,
                        apply_border_correction=is_border,
                        preserve_endpoints=is_line
                    )
                    slide.add_shape(shape_type, shape_position, style, z_index)
        
        elif role == 'background':
            # Process background
            for elem in elements:
                if elem.get('type') == 'shape' and elem.get('fill_color'):
                    slide.set_background(color=elem.get('fill_color'))
        
        else:
            # Handle other element types (like tables)
            for elem in elements:
                elem_type = elem.get('type')
                
                if elem_type == 'table':
                    # Process table element
                    table_position = self._pdf_to_slide_coords(
                        [elem['x'], elem['y'], elem['x2'], elem['y2']],
                        pdf_width, pdf_height
                    )
                    
                    # Pass the table grid structure as content
                    table_content = {
                        'grid': elem.get('grid', []),
                        'rows': elem.get('rows', 0),
                        'cols': elem.get('cols', 0),
                        'col_widths': elem.get('col_widths', []),  # Include actual column widths from PDF
                        'row_heights': elem.get('row_heights', [])  # Include actual row heights from PDF
                    }
                    
                    slide.add_table(table_content, table_position, z_index)
    
    def _pdf_to_slide_coords(self, bbox: list, pdf_width: float, 
                            pdf_height: float, apply_border_correction: bool = False,
                            preserve_endpoints: bool = False) -> Dict[str, float]:
        """
        Convert PDF coordinates to slide coordinates.
        
        Args:
            bbox: Bounding box [x1, y1, x2, y2] in PDF coordinates
            pdf_width: PDF page width
            pdf_height: PDF page height
            apply_border_correction: Apply border width correction for thin shapes
            preserve_endpoints: If True, also include x2,y2 in result (for lines)
            
        Returns:
            Position dictionary with normalized coordinates
        """
        x1, y1, x2, y2 = bbox
        
        # Apply PDF scale correction to coordinates (PDF is 75% of HTML size)
        # This restores PDF coordinates to HTML pixel equivalents
        x1 *= self.pdf_to_html_scale
        y1 *= self.pdf_to_html_scale
        x2 *= self.pdf_to_html_scale
        y2 *= self.pdf_to_html_scale
        
        # Apply border width correction for vertical card borders
        # PDF generates card borders at 5.55pt which becomes 7.4pt after scaling
        # HTML specifies 4px borders, so we correct to 4pt
        if apply_border_correction and self.border_width_correction != 1.0:
            elem_width = x2 - x1
            elem_height = y2 - y1
            
            # Only correct vertical borders (height > width)
            if elem_height > elem_width:
                # Keep center position, adjust width to match HTML 4px
                orig_x1, orig_x2 = x1, x2
                center_x = (x1 + x2) / 2
                target_width = elem_width * self.border_width_correction
                x1 = center_x - target_width / 2
                x2 = center_x + target_width / 2
                logger.debug(f"Corrected border width: {elem_width:.2f}pt → {target_width:.2f}pt")
                logger.debug(f"  Coords before: x1={orig_x1:.2f}, x2={orig_x2:.2f} (width={orig_x2-orig_x1:.2f})")
                logger.debug(f"  Coords after:  x1={x1:.2f}, x2={x2:.2f} (width={x2-x1:.2f})")
        
        # Also scale the PDF dimensions
        scaled_pdf_width = pdf_width * self.pdf_to_html_scale
        scaled_pdf_height = pdf_height * self.pdf_to_html_scale
        
        # Normalize to 0-1 range (using scaled dimensions)
        norm_x1 = x1 / scaled_pdf_width if scaled_pdf_width > 0 else 0
        norm_y1 = y1 / scaled_pdf_height if scaled_pdf_height > 0 else 0
        norm_x2 = x2 / scaled_pdf_width if scaled_pdf_width > 0 else 0
        norm_y2 = y2 / scaled_pdf_height if scaled_pdf_height > 0 else 0
        
        norm_w = norm_x2 - norm_x1
        norm_h = norm_y2 - norm_y1
        
        # Apply margins
        content_width = self.slide_width - self.margin_left - self.margin_right
        content_height = self.slide_height - self.margin_top - self.margin_bottom
        
        # Convert to inches
        x = self.margin_left + norm_x1 * content_width
        y = self.margin_top + norm_y1 * content_height
        width = norm_w * content_width
        height = norm_h * content_height
        
        if apply_border_correction:
            logger.debug(f"  Final position (inches): x={x:.4f}, y={y:.4f}, width={width:.4f}, height={height:.4f}")
            logger.debug(f"  In points: width={width*72:.2f}pt, height={height*72:.2f}pt")
        
        result = {
            'x': x,
            'y': y,
            'width': width,
            'height': height
        }
        
        # For lines, also include endpoint coordinates to preserve direction
        if preserve_endpoints:
            x2_inches = self.margin_left + norm_x2 * content_width
            y2_inches = self.margin_top + norm_y2 * content_height
            result['x2'] = x2_inches
            result['y2'] = y2_inches
        
        return result
    
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
            'italic': first_elem.get('is_italic', False),
            'rotation': first_elem.get('rotation', 0)  # Add rotation support
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
