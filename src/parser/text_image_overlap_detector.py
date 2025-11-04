"""
Text-Image Overlap Detector - Detects and removes text that overlaps with chart images
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class TextImageOverlapDetector:
    """
    Detects and filters text elements that overlap with chart images.
    Also detects and filters shape elements that are text decorations (backgrounds/highlights).
    This prevents duplicate text when charts are rendered as images with embedded labels,
    and prevents unwanted shape rectangles that are actually text decoration backgrounds.
    """
    
    def __init__(self, overlap_threshold: float = 0.5):
        """
        Initialize the overlap detector.
        
        Args:
            overlap_threshold: Minimum overlap ratio (0-1) to consider text as overlapping
        """
        self.overlap_threshold = overlap_threshold
    
    def filter_overlapping_texts(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out text elements that overlap with chart images.
        
        Args:
            elements: List of page elements (text, images, shapes)
            
        Returns:
            Filtered list of elements with overlapping texts removed
        """
        # Separate elements by type
        images = [e for e in elements if e['type'] == 'image']
        texts = [e for e in elements if e['type'] == 'text']
        other_elements = [e for e in elements if e['type'] not in ['image', 'text']]
        
        # Filter chart images (those marked as is_chart)
        chart_images = [img for img in images if img.get('is_chart', False)]
        
        if not chart_images:
            # No chart images, return all elements as-is
            return elements
        
        # Check each text element against chart images
        filtered_texts = []
        removed_count = 0
        
        for text in texts:
            should_keep = True
            
            for chart_image in chart_images:
                if self._is_text_overlapping_image(text, chart_image):
                    logger.info(f"Removing text overlapping with chart: '{text['content'][:30]}...' "
                              f"at ({text['x']:.1f}, {text['y']:.1f})")
                    should_keep = False
                    removed_count += 1
                    break
            
            if should_keep:
                filtered_texts.append(text)
        
        if removed_count > 0:
            logger.info(f"Filtered {removed_count} text element(s) overlapping with charts")
        
        # Combine filtered elements
        return other_elements + images + filtered_texts
    
    def _is_text_overlapping_image(self, text: Dict[str, Any], image: Dict[str, Any]) -> bool:
        """
        Check if a text element overlaps with an image.
        
        Args:
            text: Text element with bbox
            image: Image element with bbox
            
        Returns:
            True if text overlaps with image beyond threshold
        """
        # Get bounding boxes
        text_bbox = (text['x'], text['y'], text['x2'], text['y2'])
        image_bbox = (image['x'], image['y'], image['x2'], image['y2'])
        
        # Calculate overlap
        overlap_area = self._calculate_overlap_area(text_bbox, image_bbox)
        
        if overlap_area <= 0:
            return False
        
        # Calculate text area
        text_area = (text['x2'] - text['x']) * (text['y2'] - text['y'])
        
        if text_area <= 0:
            return False
        
        # Calculate overlap ratio
        overlap_ratio = overlap_area / text_area
        
        # Text is considered overlapping if overlap ratio exceeds threshold
        return overlap_ratio > self.overlap_threshold
    
    def _calculate_overlap_area(self, bbox1: Tuple[float, float, float, float], 
                                bbox2: Tuple[float, float, float, float]) -> float:
        """
        Calculate the overlap area between two bounding boxes.
        
        Args:
            bbox1: (x0, y0, x1, y1) of first box
            bbox2: (x0, y0, x1, y1) of second box
            
        Returns:
            Overlap area in square points
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        # Calculate intersection rectangle
        x_overlap_min = max(x1_min, x2_min)
        y_overlap_min = max(y1_min, y2_min)
        x_overlap_max = min(x1_max, x2_max)
        y_overlap_max = min(y1_max, y2_max)
        
        # Calculate overlap dimensions
        x_overlap = max(0, x_overlap_max - x_overlap_min)
        y_overlap = max(0, y_overlap_max - y_overlap_min)
        
        return x_overlap * y_overlap
    
    def filter_text_decoration_shapes(self, shapes: List[Dict[str, Any]], 
                                     texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out shapes that are text decorations (backgrounds, highlights, underlines).
        
        These shapes are positioned behind or very close to text elements in the PDF
        to provide emphasis (bold effect, highlighting, etc.) but should not be rendered
        as separate shapes in PowerPoint.
        
        Args:
            shapes: List of shape elements
            texts: List of text elements for overlap detection
            
        Returns:
            Filtered list of shapes with text decoration shapes removed
        """
        if not texts or not shapes:
            return shapes
        
        filtered_shapes = []
        removed_count = 0
        
        for shape in shapes:
            # Check if this shape is a text decoration
            if self._is_text_decoration_shape(shape, texts):
                removed_count += 1
                logger.debug(f"Filtering text decoration shape at ({shape['x']:.1f}, {shape['y']:.1f}), "
                           f"size {shape['width']:.1f}x{shape['height']:.1f}, "
                           f"fill={shape.get('fill_color', 'None')}")
            else:
                filtered_shapes.append(shape)
        
        if removed_count > 0:
            logger.info(f"Filtered {removed_count} text decoration shape(s)")
        
        return filtered_shapes
    
    def _is_text_decoration_shape(self, shape: Dict[str, Any], 
                                  texts: List[Dict[str, Any]]) -> bool:
        """
        Determine if a shape is a text decoration (background/highlight).
        
        Criteria for text decoration shapes:
        1. The shape overlaps significantly with one or more text elements
        2. The shape is relatively small (usually smaller than or similar to text size)
        3. The shape has a fill color (backgrounds are filled)
        4. The shape closely matches the text bounding box
        
        Args:
            shape: Shape element to check
            texts: List of text elements to check overlap with
            
        Returns:
            True if the shape is likely a text decoration
        """
        # Must have a fill color (decoration shapes are filled)
        if not shape.get('fill_color') or shape.get('fill_color') == 'None':
            return False
        
        shape_bbox = (shape['x'], shape['y'], shape['x2'], shape['y2'])
        shape_width = shape['width']
        shape_height = shape['height']
        
        # Check each text element for overlap
        for text in texts:
            text_bbox = (text['x'], text['y'], text['x2'], text['y2'])
            text_width = text['x2'] - text['x']
            text_height = text['y2'] - text['y']
            
            # Calculate overlap
            overlap_area = self._calculate_overlap_area(shape_bbox, text_bbox)
            
            if overlap_area <= 0:
                continue
            
            # Calculate overlap ratios
            shape_area = shape_width * shape_height
            text_area = text_width * text_height
            
            if shape_area <= 0 or text_area <= 0:
                continue
            
            # Overlap ratio relative to shape size
            shape_overlap_ratio = overlap_area / shape_area
            
            # Overlap ratio relative to text size
            text_overlap_ratio = overlap_area / text_area
            
            # Check if shape is positioned very close to text (within 2 points tolerance)
            # This catches shapes that are slightly offset but still visually associated
            x_distance = min(
                abs(shape_bbox[0] - text_bbox[0]),  # left edges
                abs(shape_bbox[2] - text_bbox[2]),  # right edges
                abs(shape_bbox[0] - text_bbox[2]),  # shape left to text right
                abs(shape_bbox[2] - text_bbox[0])   # shape right to text left
            )
            
            y_distance = min(
                abs(shape_bbox[1] - text_bbox[1]),  # top edges
                abs(shape_bbox[3] - text_bbox[3]),  # bottom edges
                abs(shape_bbox[1] - text_bbox[3]),  # shape top to text bottom
                abs(shape_bbox[3] - text_bbox[1])   # shape bottom to text top
            )
            
            is_very_close = (x_distance < 2 and y_distance < 2)
            
            # Criteria for text decoration:
            # 1. High overlap with text (>30% of shape area overlaps with text)
            # 2. Shape is small relative to text (not more than 2x text area)
            # 3. OR: shape is very close to text boundaries (within 2 points)
            
            has_high_overlap = shape_overlap_ratio > 0.3 or text_overlap_ratio > 0.3
            is_similar_size = shape_area < text_area * 2
            
            if (has_high_overlap and is_similar_size) or is_very_close:
                logger.debug(f"Text decoration detected: shape at ({shape['x']:.1f},{shape['y']:.1f}) "
                           f"overlaps {shape_overlap_ratio*100:.1f}% with text '{text['content'][:20]}'")
                return True
        
        return False
