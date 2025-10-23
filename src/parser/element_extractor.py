"""
Element Extractor - Helper class for extracting specific types of elements
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ElementExtractor:
    """
    Helper class for extracting and filtering specific element types.
    """
    
    @staticmethod
    def get_text_elements(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract only text elements from page data."""
        return [elem for elem in page_data.get('elements', []) if elem['type'] == 'text']
    
    @staticmethod
    def get_image_elements(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract only image elements from page data."""
        return [elem for elem in page_data.get('elements', []) if elem['type'] == 'image']
    
    @staticmethod
    def get_shape_elements(page_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract only shape/drawing elements from page data."""
        return [elem for elem in page_data.get('elements', []) if elem['type'] == 'shape']
    
    @staticmethod
    def filter_by_size(elements: List[Dict[str, Any]], min_size: float = None, 
                       max_size: float = None) -> List[Dict[str, Any]]:
        """
        Filter text elements by font size.
        
        Args:
            elements: List of elements to filter
            min_size: Minimum font size
            max_size: Maximum font size
            
        Returns:
            Filtered list of elements
        """
        filtered = elements
        
        if min_size is not None:
            filtered = [e for e in filtered if e.get('font_size', 0) >= min_size]
        
        if max_size is not None:
            filtered = [e for e in filtered if e.get('font_size', 999) <= max_size]
        
        return filtered
    
    @staticmethod
    def filter_by_position(elements: List[Dict[str, Any]], 
                          x_range: tuple = None,
                          y_range: tuple = None) -> List[Dict[str, Any]]:
        """
        Filter elements by position.
        
        Args:
            elements: List of elements to filter
            x_range: Tuple of (min_x, max_x)
            y_range: Tuple of (min_y, max_y)
            
        Returns:
            Filtered list of elements
        """
        filtered = elements
        
        if x_range is not None:
            min_x, max_x = x_range
            filtered = [e for e in filtered if min_x <= e.get('x', 0) <= max_x]
        
        if y_range is not None:
            min_y, max_y = y_range
            filtered = [e for e in filtered if min_y <= e.get('y', 0) <= max_y]
        
        return filtered
    
    @staticmethod
    def sort_by_position(elements: List[Dict[str, Any]], 
                        sort_by: str = 'y') -> List[Dict[str, Any]]:
        """
        Sort elements by position.
        
        Args:
            elements: List of elements to sort
            sort_by: Sort key ('x', 'y', 'xy')
            
        Returns:
            Sorted list of elements
        """
        if sort_by == 'y':
            return sorted(elements, key=lambda e: (e.get('y', 0), e.get('x', 0)))
        elif sort_by == 'x':
            return sorted(elements, key=lambda e: (e.get('x', 0), e.get('y', 0)))
        elif sort_by == 'xy':
            return sorted(elements, key=lambda e: (e.get('x', 0), e.get('y', 0)))
        
        return elements
    
    @staticmethod
    def group_by_line(elements: List[Dict[str, Any]], 
                     tolerance: float = 5.0) -> List[List[Dict[str, Any]]]:
        """
        Group text elements that are on the same line.
        
        Args:
            elements: List of text elements
            tolerance: Y-coordinate tolerance for same line
            
        Returns:
            List of lists, each containing elements on the same line
        """
        if not elements:
            return []
        
        # Sort by y position first
        sorted_elements = sorted(elements, key=lambda e: e.get('y', 0))
        
        lines = []
        current_line = [sorted_elements[0]]
        current_y = sorted_elements[0].get('y', 0)
        
        for elem in sorted_elements[1:]:
            elem_y = elem.get('y', 0)
            
            if abs(elem_y - current_y) <= tolerance:
                # Same line
                current_line.append(elem)
            else:
                # New line
                lines.append(sorted(current_line, key=lambda e: e.get('x', 0)))
                current_line = [elem]
                current_y = elem_y
        
        # Add last line
        if current_line:
            lines.append(sorted(current_line, key=lambda e: e.get('x', 0)))
        
        return lines
    
    @staticmethod
    def group_close_elements(line_elements: List[Dict[str, Any]], 
                            gap_tolerance: float = 1.0) -> List[List[Dict[str, Any]]]:
        """
        Group elements on the same line that are very close together (gap ≤ tolerance).
        This handles cases where Chinese characters and numbers are split into separate elements.
        
        Args:
            line_elements: List of text elements on the same line (sorted by x)
            gap_tolerance: Maximum gap in points to consider elements as part of same group (default 1.0pt)
            
        Returns:
            List of element groups, each group should be merged into one textbox
        """
        if not line_elements:
            return []
        
        # Sort by x position
        sorted_elements = sorted(line_elements, key=lambda e: e.get('x', 0))
        
        groups = []
        current_group = [sorted_elements[0]]
        prev_x2 = sorted_elements[0].get('x2', sorted_elements[0].get('x', 0))
        
        for elem in sorted_elements[1:]:
            x = elem.get('x', 0)
            gap = x - prev_x2
            
            # If gap is very small (≤ tolerance), they should be in same textbox
            if gap <= gap_tolerance:
                current_group.append(elem)
            else:
                # Gap is large enough, start new group
                groups.append(current_group)
                current_group = [elem]
            
            prev_x2 = elem.get('x2', elem.get('x', 0))
        
        # Add last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    @staticmethod
    def merge_text_on_line(line_elements: List[Dict[str, Any]]) -> str:
        """
        Merge text elements on the same line into a single string.
        
        Args:
            line_elements: List of text elements on the same line
            
        Returns:
            Merged text string
        """
        if not line_elements:
            return ""
        
        # Sort by x position
        sorted_elements = sorted(line_elements, key=lambda e: e.get('x', 0))
        
        # Merge with appropriate spacing
        text_parts = []
        prev_x2 = None
        
        for elem in sorted_elements:
            text = elem.get('content', '')
            x = elem.get('x', 0)
            
            if prev_x2 is not None:
                gap = x - prev_x2
                # If gap is significant, add space
                if gap > 5:
                    text_parts.append(' ')
            
            text_parts.append(text)
            prev_x2 = elem.get('x2', x)
        
        return ''.join(text_parts)
