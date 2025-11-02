"""
Layout Analyzer V2 - Improved layout analysis with better text grouping
"""

import logging
import re
from typing import List, Dict, Any
from ..parser.element_extractor import ElementExtractor

logger = logging.getLogger(__name__)


class LayoutAnalyzerV2:
    """
    Improved layout analyzer that preserves text structure better.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Layout Analyzer V2.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.title_threshold = config.get('title_threshold', 20)
        self.min_paragraph_chars = config.get('min_paragraph_chars', 10)
        self.group_tolerance = config.get('group_tolerance', 10)
        self.detect_headers = config.get('detect_headers', True)
        self.detect_footers = config.get('detect_footers', True)
    
    @staticmethod
    def _is_purely_numeric(text: str) -> bool:
        """检查文本是否纯数字（可包含小数点、逗号、百分号）"""
        if not text:
            return False
        # 移除常见的数字分隔符和符号
        cleaned = text.replace(',', '').replace('.', '').replace(' ', '').replace('%', '')
        return cleaned.isdigit()
    
    @staticmethod
    def _is_purely_alphabetic(text: str) -> bool:
        """检查文本是否纯ASCII字母（不包括中文等）"""
        if not text:
            return False
        cleaned = text.replace(' ', '')
        return cleaned.isalpha() and cleaned.isascii()
    
    @staticmethod
    def _has_cjk_characters(text: str) -> bool:
        """检查文本是否包含CJK字符（中日韩文字）或CJK标点符号"""
        if not text:
            return False
        # CJK Unicode ranges including punctuation
        # \u4e00-\u9fff: CJK Unified Ideographs
        # \u3400-\u4dbf: CJK Extension A
        # \u3040-\u309f: Hiragana
        # \u30a0-\u30ff: Katakana
        # \u3000-\u303f: CJK Symbols and Punctuation
        # \uff00-\uffef: Halfwidth and Fullwidth Forms (包括全角标点)
        cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\u3000-\u303f\uff00-\uffef]')
        return bool(cjk_pattern.search(text))
    
    @staticmethod
    def _should_merge_based_on_content(text1: str, text2: str, gap: float) -> tuple:
        """
        根据文本内容和间距判断是否应该合并
        
        关键规则：
        1. 如果gap <= 1pt：紧密相邻，应该合并（如"8个"）
        2. 如果gap > 2pt：如果一个是纯数字，另一个是中文，则不合并（语义分隔）
        3. 如果gap > 2pt：如果一个是纯字母，另一个是中文，则不合并
        4. 如果gap > 3pt且<=10pt：只有纯中文（非数字非字母）才考虑合并
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            gap: 两个文本之间的间距（pt）
            
        Returns:
            (should_merge, reason) 元组
        """
        # 规则1：紧密相邻，无条件合并
        if gap <= 1.0:
            return (True, "紧密相邻")
        
        # 检查内容类型
        text1_is_number = LayoutAnalyzerV2._is_purely_numeric(text1)
        text2_is_number = LayoutAnalyzerV2._is_purely_numeric(text2)
        text1_is_alpha = LayoutAnalyzerV2._is_purely_alphabetic(text1)
        text2_is_alpha = LayoutAnalyzerV2._is_purely_alphabetic(text2)
        text1_has_cjk = LayoutAnalyzerV2._has_cjk_characters(text1)
        text2_has_cjk = LayoutAnalyzerV2._has_cjk_characters(text2)
        
        # 规则2：纯数字 + 中文，且gap > 2pt，不合并（解决"44 起服务外"重叠问题）
        if gap > 2.0:
            if (text1_is_number and text2_has_cjk) or (text1_has_cjk and text2_is_number):
                return (False, f"数字与中文分隔")
            
            # 规则3：纯字母 + 中文，且gap > 2pt，不合并
            if (text1_is_alpha and text2_has_cjk) or (text1_has_cjk and text2_is_alpha):
                return (False, f"字母与中文分隔")
        
        # 规则4：中等间距（1-3pt），只有相同类型才合并
        if 1.0 < gap <= 3.0:
            # 如果两个都是中文（非数字），可以合并
            if text1_has_cjk and text2_has_cjk and not text1_is_number and not text2_is_number:
                return (True, "中文连续")
            # 如果两个都是数字，可以合并
            if text1_is_number and text2_is_number:
                return (True, "数字连续")
            # 其他情况不合并
            return (False, "内容类型不同")
        
        # 规则5：较大间距（>3pt），默认不合并，除非是纯中文词组
        if gap > 3.0:
            # 只有纯中文（非数字非字母）才考虑合并
            if (text1_has_cjk and not text1_is_number and not text1_is_alpha and
                text2_has_cjk and not text2_is_number and not text2_is_alpha):
                if gap <= 10.0:  # 仍然限制在合理范围内
                    return (True, "中文词组")
            return (False, "间距过大")
        
        return (True, "默认合并")
    
    def analyze_page(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single page with improved text grouping.
        
        Args:
            page_data: Page data from PDF parser
            
        Returns:
            Dictionary with analyzed layout structure
        """
        page_width = page_data.get('width', 0)
        page_height = page_data.get('height', 0)
        elements = page_data.get('elements', [])
        
        # Separate elements by type
        text_elements = ElementExtractor.get_text_elements(page_data)
        image_elements = ElementExtractor.get_image_elements(page_data)
        shape_elements = ElementExtractor.get_shape_elements(page_data)
        
        layout_regions = []
        
        # Process shapes first (backgrounds, decorations)
        for shape_elem in shape_elements:
            shape_area = shape_elem['width'] * shape_elem['height']
            page_area = page_width * page_height
            width = shape_elem['width']
            height = shape_elem['height']
            
            # More precise role detection based on HTML specifications
            if shape_area > page_area * 0.5:
                # Full-page background
                role = 'background'
                z_index = -1
            elif height < 15 and width > page_width * 0.9:
                # Thin horizontal bar across top (like top-bar: 10px height, full width)
                role = 'decoration'
                z_index = 0
            elif width < 10 and height > 50:
                # Narrow vertical strip (like border-left: 4px solid)
                role = 'border'
                z_index = 0
            elif width > 20 and height > 20 and width < 80 and height < 50:
                # Small rectangles (like risk badges)
                role = 'decoration'
                z_index = 1
            elif width > 200 and height > 50:
                # Large rectangles (like card backgrounds)
                role = 'card_background'
                z_index = 0
            else:
                # Default to decoration for other shapes
                role = 'decoration'
                z_index = 0
            
            layout_regions.append({
                'role': role,
                'bbox': [shape_elem['x'], shape_elem['y'], shape_elem['x2'], shape_elem['y2']],
                'elements': [shape_elem],
                'z_index': z_index
            })
        
        # Process images
        for img_elem in image_elements:
            layout_regions.append({
                'role': 'image',
                'bbox': [img_elem['x'], img_elem['y'], img_elem['x2'], img_elem['y2']],
                'elements': [img_elem],
                'z_index': 1
            })
        
        # Group text elements by spatial proximity AND style similarity
        text_groups = self._group_text_smartly(text_elements, page_width, page_height)
        
        # Convert text groups to regions
        for group in text_groups:
            layout_regions.append(group)
        
        # Sort by z-index and position
        layout_regions.sort(key=lambda r: (r.get('z_index', 0), r['bbox'][1]))
        
        return {
            'page_num': page_data.get('page_num', 0),
            'width': page_width,
            'height': page_height,
            'layout': layout_regions
        }
    
    def _group_text_smartly(self, text_elements: List[Dict[str, Any]], 
                           page_width: float, page_height: float) -> List[Dict[str, Any]]:
        """
        Group text elements intelligently based on position and style.
        
        Args:
            text_elements: List of text elements
            page_width: Page width
            page_height: Page height
            
        Returns:
            List of text region dictionaries
        """
        if not text_elements:
            return []
        
        # Sort by Y position first, then X position for reading order
        # Use original coordinates to maintain natural document flow
        def sort_key(e):
            y = e.get('y', 0)
            x = e.get('x', 0)
            return (y, x)
        
        sorted_elements = sorted(text_elements, key=sort_key)
        
        regions = []
        processed = set()
        
        for elem in sorted_elements:
            if id(elem) in processed:
                continue
            
            # Determine role based on characteristics
            font_size = elem.get('font_size', 0)
            y_pos = elem.get('y', 0)
            
            # Title detection (large font in upper area)
            if font_size >= self.title_threshold and y_pos < page_height * 0.2:
                role = 'title' if font_size >= 30 else 'subtitle'
            # Header detection (top 10%)
            elif y_pos < page_height * 0.1:
                role = 'header'
            # Footer detection (bottom 10%)
            elif y_pos > page_height * 0.9:
                role = 'footer'
            # Section heading (medium-large font)
            elif font_size >= 18:
                role = 'heading'
            # Regular text
            else:
                role = 'text'
            
            # Find nearby elements with similar characteristics
            group_elements = [elem]
            processed.add(id(elem))
            
            elem_y = elem.get('y', 0)
            elem_y2 = elem.get('y2', 0)
            elem_x = elem.get('x', 0)
            elem_x2 = elem.get('x2', 0)
            elem_font_size = elem.get('font_size', 0)
            elem_color = elem.get('color', '')
            elem_rotation = elem.get('rotation', 0)
            
            # Check if this is rotated text
            is_rotated = abs(elem_rotation) > 5  # More than 5 degrees
            
            # Look for elements on the same line or closely positioned
            # Important: Track the rightmost x2 of the current group for gap calculation
            current_x2 = elem_x2
            
            # Debug logging for specific text
            if elem.get('content', '') in ['8', '高危', '4', '12', '19']:
                logger.debug(f"Processing element: '{elem.get('content', '')}' at y={elem_y:.1f}, x={elem_x:.1f}-{elem_x2:.1f}")
            
            for other in sorted_elements:
                if id(other) in processed:
                    continue
                
                other_y = other.get('y', 0)
                other_y2 = other.get('y2', 0)
                other_x = other.get('x', 0)
                other_x2 = other.get('x2', 0)
                other_font_size = other.get('font_size', 0)
                other_color = other.get('color', '')
                other_rotation = other.get('rotation', 0)
                
                # Same line criteria
                y_diff = abs(other_y - elem_y)
                x_gap = other_x - current_x2
                
                # Check if elements have the same text style (bold, italic)
                elem_is_bold = elem.get('is_bold', False)
                elem_is_italic = elem.get('is_italic', False)
                other_is_bold = other.get('is_bold', False)
                other_is_italic = other.get('is_italic', False)
                same_style = (elem_is_bold == other_is_bold) and (elem_is_italic == other_is_italic)
                
                # Check if both elements have similar rotation (for rotated text grouping)
                same_rotation = abs(elem_rotation - other_rotation) < 5  # Within 5 degrees
                
                # Special handling for rotated text (especially brackets)
                # For rotated text, we need to use bbox-based distance instead of simple gap
                if is_rotated and same_rotation:
                    # Calculate center-to-center distance for rotated text
                    elem_center_x = (elem_x + elem_x2) / 2
                    elem_center_y = (elem_y + elem_y2) / 2
                    other_center_x = (other_x + other_x2) / 2
                    other_center_y = (other_y + other_y2) / 2
                    
                    # Euclidean distance
                    distance = ((elem_center_x - other_center_x) ** 2 + 
                               (elem_center_y - other_center_y) ** 2) ** 0.5
                    
                    # Check if this is bracket-related text
                    elem_text = elem.get('content', '')
                    other_text = other.get('content', '')
                    has_bracket = any(c in elem_text + other_text for c in ['(', ')', '（', '）'])
                    has_ip = any(c.isdigit() and '.' in elem_text for c in elem_text.split('.')) or \
                            any(c.isdigit() and '.' in other_text for c in other_text.split('.'))
                    has_chinese = self._has_cjk_characters(elem_text) or self._has_cjk_characters(other_text)
                    
                    # For rotated text with IP address + bracket + Chinese pattern
                    # Use smart grouping based on context:
                    # 1. Brackets and their content should be merged together: "(" + "text" + ")"
                    # 2. IP address should NOT merge with bracket group if they appear to be separate lines
                    if has_bracket or (has_ip and has_chinese):
                        # Check content types
                        elem_is_ip = any(c.isdigit() and '.' in elem_text for c in elem_text.split('.'))
                        other_is_ip = any(c.isdigit() and '.' in other_text for c in other_text.split('.'))
                        elem_has_bracket = any(c in elem_text for c in ['(', ')', '（', '）'])
                        other_has_bracket = any(c in other_text for c in ['(', ')', '（', '）'])
                        
                        # Check if one element is ONLY an IP address (no brackets)
                        elem_is_pure_ip = elem_is_ip and not elem_has_bracket
                        other_is_pure_ip = other_is_ip and not other_has_bracket
                        
                        # Case 1: Pure IP + bracket text
                        # These are likely separate lines - do NOT merge unless VERY close (< 8pt)
                        if (elem_is_pure_ip and other_has_bracket) or (other_is_pure_ip and elem_has_bracket):
                            # IP address and bracket text - these are separate lines
                            # Only merge if extremely close (< 8pt = essentially touching)
                            if distance < 8 and abs(other_font_size - elem_font_size) <= 2:
                                should_group = True
                                merge_reason = "IP and bracket (same position)"
                                
                                group_elements.append(other)
                                processed.add(id(other))
                                current_x2 = max(current_x2, other_x2)
                                
                                logger.debug(f"Merging rotated text '{elem_text}' + '{other_text}' "
                                           f"(distance={distance:.2f}pt, rotation={elem_rotation:.1f}°, reason={merge_reason})")
                                continue
                        
                        # Case 2: Bracket-related elements (forming "(text)" group)
                        # These should merge with moderate distance (< 50pt)
                        elif has_bracket:
                            # For -45° rotated text, use diagonal position to check if on same line
                            # Elements on the same diagonal line have similar (x + y) values
                            elem_x_center = (elem_x + elem_x2) / 2
                            elem_y_center = (elem_y + elem_y2) / 2
                            other_x_center = (other_x + other_x2) / 2
                            other_y_center = (other_y + other_y2) / 2
                            
                            elem_diagonal = elem_x_center + elem_y_center
                            other_diagonal = other_x_center + other_y_center
                            diagonal_diff = abs(elem_diagonal - other_diagonal)
                            
                            # If diagonal position differs by > 20pt, they're on different lines
                            if diagonal_diff > 20:
                                logger.debug(f"Not merging rotated text '{elem_text}' + '{other_text}' "
                                           f"(diagonal差异={diagonal_diff:.2f}pt > 20pt, different diagonal lines)")
                                continue
                            
                            if distance < 50 and abs(other_font_size - elem_font_size) <= 2:
                                should_group = True
                                merge_reason = "bracket group elements"
                                
                                group_elements.append(other)
                                processed.add(id(other))
                                current_x2 = max(current_x2, other_x2)
                                
                                logger.debug(f"Merging rotated text '{elem_text}' + '{other_text}' "
                                           f"(distance={distance:.2f}pt, diagonal差异={diagonal_diff:.2f}pt, rotation={elem_rotation:.1f}°, reason={merge_reason})")
                                continue
                
                # Group if on same line and close horizontal proximity
                # Use content-aware merging to prevent overlaps
                if y_diff <= self.group_tolerance:
                    should_group = False
                    merge_reason = ""
                    
                    # Check both directions: element could be to the left or right
                    actual_gap = x_gap
                    
                    # Direction 1: Check if other element is directly to our RIGHT
                    # Allow small negative gaps (down to -1pt) for slight overlaps
                    if x_gap >= -1.0:
                        # Use content-based merging logic
                        elem_text = elem.get('content', '')
                        other_text = other.get('content', '')
                        
                        # First check style compatibility
                        style_compatible = (
                            abs(other_font_size - elem_font_size) <= 2 and
                            other_color == elem_color and
                            same_style
                        )
                        
                        if style_compatible:
                            # Use absolute value of gap for content analysis
                            merge_result = self._should_merge_based_on_content(
                                elem_text, other_text, abs(actual_gap)
                            )
                            should_group, merge_reason = merge_result
                    
                    # Direction 2: Check if other element is directly to our LEFT
                    elif x_gap < 0:
                        other_x2 = other.get('x2', other_x)
                        left_gap = elem_x - other_x2
                        
                        if left_gap >= -1.0:
                            elem_text = elem.get('content', '')
                            other_text = other.get('content', '')
                            
                            style_compatible = (
                                abs(other_font_size - elem_font_size) <= 2 and
                                other_color == elem_color and
                                same_style
                            )
                            
                            if style_compatible:
                                # Reverse order since other is on the left
                                merge_result = self._should_merge_based_on_content(
                                    other_text, elem_text, abs(left_gap)
                                )
                                should_group, merge_reason = merge_result
                    
                    if should_group:
                        group_elements.append(other)
                        processed.add(id(other))
                        current_x2 = max(current_x2, other_x2)
                        
                        # Log merging decisions for debugging
                        if abs(actual_gap) > 2.0:
                            logger.debug(f"Merging '{elem.get('content', '')}' + '{other.get('content', '')}' "
                                       f"(gap={actual_gap:.2f}pt, reason={merge_reason})")
                    else:
                        # Log when we skip merging for interesting cases
                        if 2.0 < abs(x_gap) <= 10.0 and merge_reason:
                            logger.debug(f"Not merging '{elem.get('content', '')}' + '{other.get('content', '')}' "
                                       f"(gap={x_gap:.2f}pt, reason={merge_reason})")
            
            # Create region
            bbox = self._calculate_bbox(group_elements)
            
            # Sort group elements by x position before merging text
            sorted_group = sorted(group_elements, key=lambda e: e.get('x', 0))
            
            # Merge text (智能添加空格：CJK字符之间不加空格，其他情况根据gap判断)
            text_parts = []
            for i, e in enumerate(sorted_group):
                if i > 0:
                    # Check gap with previous element
                    prev_elem = sorted_group[i-1]
                    prev_x2 = prev_elem.get('x2', prev_elem.get('x', 0))
                    curr_x = e.get('x', 0)
                    gap = curr_x - prev_x2
                    
                    # 智能空格添加规则:
                    # 1. gap <= 1pt: 不加空格（紧密相邻）
                    # 2. gap > 1pt: 检查内容类型
                    #    - 如果都是CJK字符（包括标点），不加空格
                    #    - 否则，加空格
                    if gap > 1.0:
                        prev_text = prev_elem.get('content', '')
                        curr_text = e.get('content', '')
                        
                        # 检查是否都包含CJK字符
                        prev_has_cjk = self._has_cjk_characters(prev_text)
                        curr_has_cjk = self._has_cjk_characters(curr_text)
                        
                        # 只有在不都是CJK时才加空格
                        # CJK文字和标点之间不需要空格
                        if not (prev_has_cjk and curr_has_cjk):
                            text_parts.append(' ')
                
                text_parts.append(e.get('content', ''))
            text_content = ''.join(text_parts)
            
            # Debug logging
            if elem.get('content', '') in ['8', '高危']:
                logger.debug(f"Creating region: '{text_content}' with {len(group_elements)} elements: {[e.get('content', '') for e in group_elements]}")
            
            regions.append({
                'role': role,
                'bbox': bbox,
                'elements': group_elements,
                'text': text_content,
                'z_index': 2
            })
        
        return regions
    
    def _calculate_bbox(self, elements: List[Dict[str, Any]]) -> List[float]:
        """
        Calculate bounding box for a list of elements.
        
        Args:
            elements: List of elements
            
        Returns:
            Bounding box [x1, y1, x2, y2]
        """
        if not elements:
            return [0, 0, 0, 0]
        
        x_coords = [e.get('x', 0) for e in elements] + [e.get('x2', 0) for e in elements]
        y_coords = [e.get('y', 0) for e in elements] + [e.get('y2', 0) for e in elements]
        
        return [
            min(x_coords),
            min(y_coords),
            max(x_coords),
            max(y_coords)
        ]
