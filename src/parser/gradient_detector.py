"""
Gradient Detector - Detects gradient patterns that need to be rendered as images
"""

import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)


class GradientDetector:
    """
    Detects gradient patterns in PDF pages that should be rendered as images
    instead of being converted to vector shapes.
    
    Gradients in PDFs are often represented as many small vector shapes with
    varying colors that create a smooth color transition. These are difficult
    to recreate in PowerPoint and should be rendered as images.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the gradient detector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.min_complex_items = 100  # Minimum path items to consider as gradient
        self.footer_height_pct = 0.10  # Check bottom 10% of page
        self.header_height_pct = 0.10  # Check top 10% of page
        self.render_dpi = 4.0  # High DPI for gradient rendering
    
    def detect_and_extract_gradients(
        self,
        page: fitz.Page,
        drawings: List[Dict[str, Any]],
        page_num: int,
        text_elements: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect gradient patterns in drawings and extract them as images.
        
        This method analyzes vector drawings to find complex gradient patterns
        (especially in header/footer regions) and renders them as high-quality images.
        
        IMPORTANT: Page numbers within gradient regions are detected and stored for later filtering.
        
        Args:
            page: PyMuPDF page object
            drawings: List of drawing dictionaries from page.get_drawings()
            page_num: Page number (0-indexed)
            text_elements: Optional list of text elements for page number detection
            
        Returns:
            List of image elements representing detected gradients
        """
        gradient_images = []
        
        page_width = page.rect.width
        page_height = page.rect.height
        
        # Define header and footer regions
        header_bottom = page_height * self.header_height_pct
        footer_top = page_height * (1.0 - self.footer_height_pct)
        
        # Group drawings by region
        header_drawings = []
        footer_drawings = []
        
        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue
            
            # Check if shape is in header or footer region
            shape_center_y = (rect.y0 + rect.y1) / 2
            
            if shape_center_y < header_bottom:
                header_drawings.append(drawing)
            elif shape_center_y > footer_top:
                footer_drawings.append(drawing)
        
        # Check header for gradient patterns
        if header_drawings:
            header_gradient = self._detect_gradient_in_region(
                page, header_drawings, page_num, "header",
                fitz.Rect(0, 0, page_width, header_bottom),
                text_elements
            )
            if header_gradient:
                gradient_images.append(header_gradient)
                logger.info(f"Page {page_num}: Detected gradient pattern in header")
        
        # Check footer for gradient patterns
        if footer_drawings:
            footer_gradient = self._detect_gradient_in_region(
                page, footer_drawings, page_num, "footer",
                fitz.Rect(0, footer_top, page_width, page_height),
                text_elements
            )
            if footer_gradient:
                gradient_images.append(footer_gradient)
                logger.info(f"Page {page_num}: Detected gradient pattern in footer")
        
        return gradient_images
    
    def _detect_gradient_in_region(
        self,
        page: fitz.Page,
        drawings: List[Dict[str, Any]],
        page_num: int,
        region_name: str,
        region_rect: fitz.Rect,
        text_elements: List[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if a specific region contains a gradient pattern.
        
        A gradient pattern is identified by:
        1. Multiple shapes with complex paths (many line/curve items)
        
        CRITICAL FIX: Extract original XObject instead of rendering the region!
        - The old approach rendered the entire region (e.g., bottom 10% of page)
        - This captured extra blank space above/below the actual gradient pattern
        - The correct approach: Find and extract the original embedded image XObject
        - This ensures we get the exact size and position of the gradient pattern
        
        IMPORTANT: Page numbers within the gradient region are filtered out to prevent duplication.
        
        Args:
            page: PyMuPDF page object
            drawings: List of drawings in the region
            page_num: Page number
            region_name: Name of the region (e.g., "header", "footer")
            region_rect: Rectangle defining the region
            text_elements: Optional list of text elements for page number detection
            
        Returns:
            Image element dictionary if gradient detected, None otherwise
        """
        if not drawings:
            return None
        
        # Count total path items across all shapes
        total_items = 0
        complex_shapes = []
        
        for drawing in drawings:
            items = drawing.get("items", [])
            item_count = len(items)
            total_items += item_count
            
            # Consider shapes with many items as "complex"
            if item_count > 50:
                complex_shapes.append(drawing)
        
        # Check if this region has enough complexity to be a gradient
        # Criteria: Either many total items OR multiple complex shapes
        has_many_items = total_items > self.min_complex_items
        has_multiple_complex = len(complex_shapes) >= 2
        
        if not (has_many_items or has_multiple_complex):
            logger.debug(f"Page {page_num} {region_name}: Not a gradient "
                        f"(total_items={total_items}, complex_shapes={len(complex_shapes)})")
            return None
        
        # CRITICAL FIX: Look for the original XObject (embedded image) in this region
        # Instead of rendering the whole region, we extract the actual gradient image
        gradient_xobject = self._find_gradient_xobject_in_region(page, region_rect, page_num)
        
        if gradient_xobject:
            # Found an embedded image XObject - use it directly!
            logger.info(f"Page {page_num} {region_name}: Found gradient XObject at "
                       f"({gradient_xobject['x']:.1f}, {gradient_xobject['y']:.1f}), "
                       f"size {gradient_xobject['width']:.1f}x{gradient_xobject['height']:.1f}")
            
            # CRITICAL: Detect page numbers in this region to prevent duplication
            page_number_bboxes = []
            if text_elements:
                page_number_bboxes = self._detect_page_numbers_in_region(
                    text_elements, region_rect, page
                )
                if page_number_bboxes:
                    logger.info(f"Page {page_num} {region_name}: Detected {len(page_number_bboxes)} page number(s) "
                               f"that will be filtered from gradient region")
            
            # Use the XObject's actual position and size
            gradient_xobject['is_gradient'] = True
            gradient_xobject['gradient_region'] = region_name
            gradient_xobject['page_number_bboxes'] = page_number_bboxes
            gradient_xobject['image_id'] = f"page{page_num}_gradient_{region_name}"
            
            return gradient_xobject
        
        # Fallback: If no XObject found, the gradient is composed of vector shapes
        # CRITICAL FIX: Calculate the ACTUAL bounding box of the vector shapes
        # IMPORTANT: Gradient patterns often span the full page width (background),
        # but only part of it contains visible drawings. We should:
        # - Keep the full WIDTH of the region (X axis) to capture the entire gradient
        # - Only optimize the HEIGHT (Y axis) based on actual drawings
        logger.info(f"Page {page_num} {region_name}: No gradient XObject found, "
                   f"gradient is composed of vector shapes - calculating actual bbox")
        
        # CRITICAL: Only pass drawings that are WITHIN the region
        # The 'drawings' list contains ALL drawings classified to this region by center point,
        # but their actual rect might extend far outside. We need to clip to region bounds.
        region_drawings = []
        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue
            # Only include if the shape is actually within the region bounds
            if (rect.y0 >= region_rect.y0 and rect.y1 <= region_rect.y1):
                region_drawings.append(drawing)
        
        if not region_drawings:
            logger.warning(f"Page {page_num} {region_name}: No drawings actually within region bounds")
            return None
        
        logger.debug(f"Page {page_num} {region_name}: {len(region_drawings)} of {len(drawings)} drawings are within region bounds")
        
        # Calculate the actual bounding box of the drawings in this region
        actual_bbox = self._calculate_actual_bbox(region_drawings)
        
        if not actual_bbox:
            logger.warning(f"Page {page_num} {region_name}: Could not calculate bbox for vector gradient")
            return None
        
        # CRITICAL FIX: Keep full width (X), only optimize height (Y)
        # Gradient backgrounds often span the full page width
        # Only the Y-axis bbox matters for avoiding blank space
        actual_rect = fitz.Rect(
            region_rect.x0,      # Keep full width from region
            actual_bbox[1],       # Y0 from actual drawings
            region_rect.x1,      # Keep full width from region
            actual_bbox[3]        # Y1 from actual drawings
        )
        
        logger.info(f"Page {page_num} {region_name}: Optimized gradient bbox: "
                   f"X: full width {actual_rect.x0:.1f}-{actual_rect.x1:.1f}, "
                   f"Y: {actual_rect.y0:.1f} to {actual_rect.y1:.1f} (height: {actual_rect.height:.1f}), "
                   f"original region height: {region_rect.height:.1f}, "
                   f"saved {region_rect.height - actual_rect.height:.1f} pt of vertical blank space")
        
        # CRITICAL: Detect page numbers in this region to prevent duplication
        page_number_bboxes = []
        if text_elements:
            page_number_bboxes = self._detect_page_numbers_in_region(
                text_elements, actual_rect, page  # Use actual_rect instead of region_rect
            )
            if page_number_bboxes:
                logger.info(f"Page {page_num} {region_name}: Detected {len(page_number_bboxes)} page number(s) "
                           f"that will be filtered from gradient region")
        
        try:
            # Render at high resolution using ACTUAL bbox
            zoom = self.render_dpi
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, clip=actual_rect, alpha=True)
            
            image_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(image_data))
            
            # This is a complex pattern that should be rendered as image!
            logger.info(f"Page {page_num} {region_name}: Rendered vector gradient with "
                       f"{total_items} path items, {len(complex_shapes)} complex shapes as image "
                       f"({img.width}x{img.height}px)")
            
            return {
                'type': 'image',
                'image_data': image_data,
                'image_format': 'png',
                'width_px': img.width,
                'height_px': img.height,
                'x': actual_rect.x0,
                'y': actual_rect.y0,
                'x2': actual_rect.x1,
                'y2': actual_rect.y1,
                'width': actual_rect.width,
                'height': actual_rect.height,
                'image_id': f"page{page_num}_gradient_{region_name}",
                'is_gradient': True,
                'gradient_region': region_name,
                'page_number_bboxes': page_number_bboxes  # Store for filtering text elements later
            }
            
        except Exception as e:
            logger.warning(f"Failed to render {region_name} gradient on page {page_num}: {e}")
            return None
    
    def _check_for_color_variation(self, img: Image.Image) -> bool:
        """
        Check if an image contains significant color variation (gradient).
        
        Samples pixels across the image and checks if there's color variation
        that indicates a gradient pattern.
        
        Args:
            img: PIL Image to check
            
        Returns:
            True if significant color variation detected, False otherwise
        """
        if img.width < 20 or img.height < 5:
            return False
        
        # Sample pixels horizontally across the middle row
        mid_y = img.height // 2
        sample_count = min(10, img.width // 10)
        
        samples = []
        for i in range(sample_count):
            x = int((i + 0.5) * img.width / sample_count)
            x = min(x, img.width - 1)
            try:
                pixel = img.getpixel((x, mid_y))
                # Convert to RGB if needed
                if isinstance(pixel, int):
                    pixel = (pixel, pixel, pixel)
                samples.append(pixel[:3])  # Take RGB only
            except:
                continue
        
        if len(samples) < 2:
            return False
        
        # Calculate color variation across samples
        first_pixel = samples[0]
        max_variation = 0
        
        for pixel in samples[1:]:
            variation = max(abs(a - b) for a, b in zip(first_pixel, pixel))
            max_variation = max(max_variation, variation)
        
        # Threshold: at least 10 color units of variation indicates gradient
        threshold = 10
        has_gradient = max_variation > threshold
        
        if has_gradient:
            logger.debug(f"Color variation detected: {max_variation} > {threshold}")
        
        return has_gradient
    
    def _detect_page_numbers_in_region(
        self,
        text_elements: List[Dict[str, Any]],
        region_rect: fitz.Rect,
        page: fitz.Page
    ) -> List[tuple]:
        """
        Detect page numbers within a specific region.
        
        Page numbers are identified by:
        1. Pattern matching: "N/M" format (e.g., "3/10") or single digit
        2. Position: centered horizontally, at extreme top/bottom
        3. Located within the region rectangle
        
        Args:
            text_elements: List of text element dictionaries
            region_rect: Rectangle defining the region to check
            page: PyMuPDF page object
            
        Returns:
            List of bounding boxes (x, y, x2, y2) for detected page numbers
        """
        import re
        
        page_width = page.rect.width
        page_height = page.rect.height
        page_number_bboxes = []
        
        for elem in text_elements:
            text = elem.get('content', '').strip()
            if not text:
                continue
            
            # Pattern 1: "N/M" format (e.g., "3/10", "1/10")
            is_n_slash_m = bool(re.match(r'^\d+/\d+$', text))
            
            # Pattern 2: Single digit or double digit number
            is_single_number = text.isdigit() and len(text) <= 2
            
            if not (is_n_slash_m or is_single_number):
                continue
            
            # Check position
            elem_x = elem.get('x', 0)
            elem_x2 = elem.get('x2', 0)
            elem_y = elem.get('y', 0)
            elem_y2 = elem.get('y2', 0)
            
            # Check if element is within region
            elem_center_x = (elem_x + elem_x2) / 2
            elem_center_y = (elem_y + elem_y2) / 2
            
            if not (region_rect.x0 <= elem_center_x <= region_rect.x1 and
                    region_rect.y0 <= elem_center_y <= region_rect.y1):
                continue
            
            # For single numbers, check if centered and at extreme edge
            if is_single_number:
                is_centered = 0.4 * page_width < elem_center_x < 0.6 * page_width
                is_extreme_top = elem_y < page_height * 0.05
                is_extreme_bottom = elem_y > page_height * 0.95
                
                if not (is_centered and (is_extreme_top or is_extreme_bottom)):
                    continue
            
            # This is a page number in the region
            page_number_bboxes.append((elem_x, elem_y, elem_x2, elem_y2))
            logger.debug(f"Detected page number '{text}' in region at ({elem_x:.1f}, {elem_y:.1f})")
        
        return page_number_bboxes
    
    def should_exclude_shape_in_gradient(
        self,
        shape: Dict[str, Any],
        gradient_regions: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a shape should be excluded because it's part of a gradient.
        
        Args:
            shape: Shape dictionary
            gradient_regions: List of detected gradient region dictionaries
            
        Returns:
            True if shape is within a gradient region and should be excluded
        """
        if not gradient_regions:
            return False
        
        shape_center_x = (shape.get('x', 0) + shape.get('x2', 0)) / 2
        shape_center_y = (shape.get('y', 0) + shape.get('y2', 0)) / 2
        
        for gradient in gradient_regions:
            gx0, gy0 = gradient['x'], gradient['y']
            gx1, gy1 = gradient['x2'], gradient['y2']
            
            # Check if shape center is within gradient bbox
            if (gx0 <= shape_center_x <= gx1 and
                gy0 <= shape_center_y <= gy1):
                return True
        
        return False
    
    def _calculate_actual_bbox(self, drawings: List[Dict[str, Any]]) -> Optional[Tuple[float, float, float, float]]:
        """
        Calculate the actual bounding box of a list of drawings.
        
        This is critical for avoiding blank space in rendered gradient images.
        Instead of rendering the entire region (e.g., bottom 10% of page),
        we calculate the tight bounding box of the actual vector shapes.
        
        Args:
            drawings: List of drawing dictionaries
            
        Returns:
            Tuple of (x0, y0, x1, y1) or None if no valid drawings
        """
        if not drawings:
            return None
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        valid_count = 0
        for drawing in drawings:
            rect = drawing.get("rect")
            if not rect:
                continue
            
            min_x = min(min_x, rect.x0)
            min_y = min(min_y, rect.y0)
            max_x = max(max_x, rect.x1)
            max_y = max(max_y, rect.y1)
            valid_count += 1
        
        if valid_count == 0:
            return None
        
        return (min_x, min_y, max_x, max_y)
    
    def _find_gradient_xobject_in_region(
        self,
        page: fitz.Page,
        region_rect: fitz.Rect,
        page_num: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find the original embedded image XObject that represents the gradient pattern in a region.
        
        This is the CORRECT way to extract gradient patterns:
        - Look for embedded images (XObjects) in the region
        - Extract the original image data directly
        - Preserve the exact size and position from the PDF
        
        Args:
            page: PyMuPDF page object
            region_rect: Rectangle defining the region to search
            page_num: Page number for logging
            
        Returns:
            Image element dictionary if gradient XObject found, None otherwise
        """
        try:
            # Get all images on the page
            image_list = page.get_images(full=True)
            
            if not image_list:
                logger.debug(f"Page {page_num}: No images found on page")
                return None
            
            # Look for images that overlap with the region
            # We use overlap ratio instead of just center point to be more flexible
            best_match = None
            best_overlap_ratio = 0.0
            
            for img_info in image_list:
                xref = img_info[0]
                
                # Get image position(s) on page
                image_rects = page.get_image_rects(xref)
                
                if not image_rects:
                    continue
                
                # Check each occurrence of this image
                for img_rect in image_rects:
                    # Calculate overlap with region
                    # Overlap = intersection area / image area
                    x_overlap = max(0, min(img_rect.x1, region_rect.x1) - max(img_rect.x0, region_rect.x0))
                    y_overlap = max(0, min(img_rect.y1, region_rect.y1) - max(img_rect.y0, region_rect.y0))
                    overlap_area = x_overlap * y_overlap
                    
                    img_area = img_rect.width * img_rect.height
                    if img_area <= 0:
                        continue
                    
                    overlap_ratio = overlap_area / img_area
                    
                    # Log all images in region for debugging
                    if overlap_ratio > 0.1:
                        logger.debug(f"Page {page_num}: Found image xref={xref} with {overlap_ratio*100:.1f}% overlap, "
                                   f"position: ({img_rect.x0:.1f}, {img_rect.y0:.1f}), "
                                   f"size: {img_rect.width:.1f}x{img_rect.height:.1f}pt")
                    
                    # Keep track of the best match (highest overlap ratio)
                    # Require at least 50% overlap to consider it part of the region
                    if overlap_ratio > best_overlap_ratio and overlap_ratio >= 0.5:
                        best_overlap_ratio = overlap_ratio
                        best_match = (xref, img_rect)
            
            # If we found a good match, extract it
            if best_match:
                xref, img_rect = best_match
                
                # Extract the image
                base_image = page.parent.extract_image(xref)
                
                if not base_image:
                    logger.warning(f"Page {page_num}: Failed to extract image xref={xref}")
                    return None
                
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Convert to PIL Image to get dimensions
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                logger.info(f"Page {page_num}: Found gradient XObject in region (overlap={best_overlap_ratio*100:.1f}%), "
                          f"original size: {pil_image.width}x{pil_image.height}px, "
                          f"position: ({img_rect.x0:.1f}, {img_rect.y0:.1f}), "
                          f"PDF size: {img_rect.width:.1f}x{img_rect.height:.1f}pt")
                
                # Return the image element using original XObject data
                return {
                    'type': 'image',
                    'image_data': image_bytes,
                    'image_format': image_ext,
                    'width_px': pil_image.width,
                    'height_px': pil_image.height,
                    'x': img_rect.x0,
                    'y': img_rect.y0,
                    'x2': img_rect.x1,
                    'y2': img_rect.y1,
                    'width': img_rect.width,
                    'height': img_rect.height,
                }
            
            logger.debug(f"Page {page_num}: No suitable gradient XObject found in region "
                        f"(best overlap: {best_overlap_ratio*100:.1f}%)")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to find gradient XObject on page {page_num}: {e}")
            return None
    
    def should_exclude_text_in_gradient(
        self,
        text_elem: Dict[str, Any],
        gradient_regions: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a text element should be excluded because it's a page number within a gradient region.
        
        This prevents page number duplication when gradient patterns are rendered as images.
        
        Args:
            text_elem: Text element dictionary
            gradient_regions: List of detected gradient region dictionaries with page_number_bboxes
            
        Returns:
            True if text element is a page number within a gradient region and should be excluded
        """
        if not gradient_regions:
            return False
        
        elem_x = text_elem.get('x', 0)
        elem_y = text_elem.get('y', 0)
        elem_x2 = text_elem.get('x2', 0)
        elem_y2 = text_elem.get('y2', 0)
        
        # Check each gradient region
        for gradient in gradient_regions:
            page_number_bboxes = gradient.get('page_number_bboxes', [])
            
            # Check if this text element matches any page number bbox in this gradient
            for pn_bbox in page_number_bboxes:
                pn_x, pn_y, pn_x2, pn_y2 = pn_bbox
                
                # Check if bboxes overlap (with small tolerance)
                tolerance = 2.0
                if (abs(elem_x - pn_x) < tolerance and
                    abs(elem_y - pn_y) < tolerance and
                    abs(elem_x2 - pn_x2) < tolerance and
                    abs(elem_y2 - pn_y2) < tolerance):
                    logger.debug(f"Excluding page number text at ({elem_x:.1f}, {elem_y:.1f}) "
                               f"- already in gradient region '{gradient.get('gradient_region')}'")
                    return True
        
        return False
