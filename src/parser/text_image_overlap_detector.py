"""
Text-Image Overlap Detector - Detects and removes text that overlaps with chart images
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class TextImageOverlapDetector:
    """
    Detects and filters text elements that overlap with chart images.
    This prevents duplicate text when charts are rendered as images with embedded labels.
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
