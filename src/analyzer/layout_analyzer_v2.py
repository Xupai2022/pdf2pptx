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
    def _colors_similar(color1: str, color2: str, threshold: int = 30) -> bool:
        """
        检查两个十六进制颜色是否相似
        
        Args:
            color1: 第一个颜色（如'#000000'或'#14161A'）
            color2: 第二个颜色
            threshold: RGB差异阈值（0-255），默认30
            
        Returns:
            如果颜色相似则返回True
        """
        # 处理空值
        if not color1 or not color2:
            return color1 == color2
        
        # 移除'#'前缀
        c1 = color1.lstrip('#')
        c2 = color2.lstrip('#')
        
        # 确保长度为6
        if len(c1) != 6 or len(c2) != 6:
            return color1 == color2
        
        try:
            # 解析RGB值
            r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
            r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
            
            # 计算欧几里得距离
            distance = ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2) ** 0.5
            
            # 阈值转换为欧几里得空间（sqrt(3) * threshold）
            max_distance = (threshold ** 2 * 3) ** 0.5
            
            return distance <= max_distance
        except ValueError:
            # 解析失败，使用严格匹配
            return color1 == color2
    
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
        0. 如果gap <= 0.5pt：超紧密相邻（几乎touching），无条件合并
        1. 如果gap <= 2pt：紧密相邻，应该合并（如"事件&威胁总览"）
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
        # 规则0：超紧密相邻（几乎touching），无条件合并
        if gap <= 0.5:
            return (True, "超紧密相邻")

        # 规则1：紧密相邻，无条件合并（从1pt放宽到2pt）
        if gap <= 2.0:
            return (True, "紧密相邻")

        # 检查内容类型
        text1_is_number = LayoutAnalyzerV2._is_purely_numeric(text1)
        text2_is_number = LayoutAnalyzerV2._is_purely_numeric(text2)
        text1_is_alpha = LayoutAnalyzerV2._is_purely_alphabetic(text1)
        text2_is_alpha = LayoutAnalyzerV2._is_purely_alphabetic(text2)
        text1_has_cjk = LayoutAnalyzerV2._has_cjk_characters(text1)
        text2_has_cjk = LayoutAnalyzerV2._has_cjk_characters(text2)
        text1_is_whitespace = text1.isspace()
        text2_is_whitespace = text2.isspace()

        # 规则0.5：如果任意一侧是纯空格，且gap <= 5pt，应该合并
        # 这允许"变更 " + " " + "34"这样的序列正确合并
        if (text1_is_whitespace or text2_is_whitespace) and gap <= 5.0:
            return (True, "含空格字符")
        
        # 规则2：纯数字 + 中文，且gap > 5pt，不合并（放宽从2pt到5pt）
        # 解决"44 起服务外"重叠问题，但允许"变更 34 次"合并（gap=3.5pt）
        if gap > 5.0:
            if (text1_is_number and text2_has_cjk) or (text1_has_cjk and text2_is_number):
                return (False, f"数字与中文分隔")

            # 规则3：纯字母 + 中文，且gap > 5pt，不合并
            if (text1_is_alpha and text2_has_cjk) or (text1_has_cjk and text2_is_alpha):
                return (False, f"字母与中文分隔")
        
        # 规则4：中等间距（2-5pt），根据内容类型判断
        if 2.0 < gap <= 5.0:
            # 如果两个都是中文（非数字），可以合并
            if text1_has_cjk and text2_has_cjk and not text1_is_number and not text2_is_number:
                return (True, "中文连续")
            # 如果两个都是数字，可以合并
            if text1_is_number and text2_is_number:
                return (True, "数字连续")
            # 中文+数字，且gap<=5pt，也应该合并（如"变更 34 次"）
            if (text1_has_cjk and text2_is_number) or (text1_is_number and text2_has_cjk):
                return (True, "中文数字组合")
            # 其他情况不合并
            return (False, "内容类型不同")
        
        # 规则5：较大间距（>5pt），默认不合并，除非是纯中文词组
        if gap > 5.0:
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
        # NEW: Extract table elements
        table_elements = [e for e in elements if e.get('type') == 'table']
        
        layout_regions = []
        
        # Process shapes first (backgrounds, decorations)
        for shape_elem in shape_elements:
            shape_area = shape_elem['width'] * shape_elem['height']
            page_area = page_width * page_height
            width = shape_elem['width']
            height = shape_elem['height']
            
            # CRITICAL: Use PDF drawing order (pdf_index) as the primary z-index
            # In PDF, elements drawn later appear on top
            # This preserves the correct layering for bar charts, gridlines, etc.
            pdf_index = shape_elem.get('pdf_index', 0)
            
            # More precise role detection based on HTML specifications
            if shape_area > page_area * 0.5:
                # Full-page background
                role = 'background'
                # Use pdf_index directly for z-index (preserve drawing order)
                z_index = pdf_index
            elif height < 15 and width > page_width * 0.9:
                # Thin horizontal bar across top (like top-bar: 10px height, full width)
                role = 'decoration'
                z_index = pdf_index
            elif width < 10 and height > 50:
                # Narrow vertical strip (like border-left: 4px solid)
                role = 'border'
                z_index = pdf_index
            elif width > 20 and height > 20 and width < 80 and height < 50:
                # Small rectangles (like risk badges)
                role = 'decoration'
                z_index = pdf_index
            elif width > 200 and height > 50:
                # Large rectangles (like card backgrounds)
                role = 'card_background'
                z_index = pdf_index
            else:
                # Default to decoration for other shapes
                role = 'decoration'
                z_index = pdf_index
            
            layout_regions.append({
                'role': role,
                'bbox': [shape_elem['x'], shape_elem['y'], shape_elem['x2'], shape_elem['y2']],
                'elements': [shape_elem],
                'z_index': z_index
            })
        
        # Process tables (tables should appear above shapes but below text)
        # Tables are complete structures that render as official PPT table objects
        for table_elem in table_elements:
            # Tables render above shapes (z_index=5000), but below regular images and text
            z_index = 5000
            
            layout_regions.append({
                'role': 'table',
                'bbox': [table_elem['x'], table_elem['y'], table_elem['x2'], table_elem['y2']],
                'elements': [table_elem],
                'z_index': z_index
            })
        
        # Process images
        # CRITICAL FIX: Full-page background images must render on the BOTTOM layer
        # Regular images appear on top of shapes, with z_index=10000
        # Background images (is_full_page_background=True OR is_background=True) use z_index=-1000 to render below everything
        for img_elem in image_elements:
            # Check if this is a full-page background image (from either marking)
            is_full_page_background = img_elem.get('is_full_page_background', False)
            is_background = img_elem.get('is_background', False)
            
            if is_full_page_background or is_background:
                # Background images go to the BOTTOM layer (below shapes and text)
                # Use element's z_index if specified, otherwise use -1000
                z_index = img_elem.get('z_index', -1000)
                logger.info(f"Full-page background image assigned z_index={z_index} (bottom layer)")
            else:
                # Regular images appear on top of shapes
                z_index = 10000
            
            layout_regions.append({
                'role': 'image',
                'bbox': [img_elem['x'], img_elem['y'], img_elem['x2'], img_elem['y2']],
                'elements': [img_elem],
                'z_index': z_index
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
                # CRITICAL FIX: Also check if they're on ACTUALLY the same line
                # by comparing if their Y ranges overlap significantly
                # This prevents merging text from adjacent lines that have tiny Y gaps (e.g., 0.02pt)
                elem_y2 = elem.get('y2', elem_y)
                other_y2 = other.get('y2', other_y)
                
                # Calculate vertical overlap
                y_overlap_start = max(elem_y, other_y)
                y_overlap_end = min(elem_y2, other_y2)
                y_overlap = max(0, y_overlap_end - y_overlap_start)
                
                # Get the average height of the two elements
                elem_height = elem_y2 - elem_y
                other_height = other_y2 - other_y
                avg_height = (elem_height + other_height) / 2
                
                # Elements are on the same line if:
                # 1. y_diff <= group_tolerance (vertical centers are close)
                # 2. AND they have significant vertical overlap (>30% of average height)
                # This prevents merging lines that just happen to be vertically close
                are_on_same_line = (y_diff <= self.group_tolerance and 
                                   (y_overlap > avg_height * 0.3 or y_diff <= 1.0))
                
                if are_on_same_line:
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
                        # 放宽颜色匹配：允许相近的颜色（如#000000和#14161A）
                        colors_match = LayoutAnalyzerV2._colors_similar(other_color, elem_color, threshold=30)

                        # 特殊处理：如果任意一侧是纯空格，忽略颜色检查（空格不可见，颜色无关紧要）
                        # 这解决了"变更 " + " " + "34 次"的合并问题（空格的颜色可能与相邻文本不同）
                        is_space_involved = elem_text.isspace() or other_text.isspace()

                        # 特殊处理：如果gap非常小(<= 1pt)且涉及数字，也忽略颜色检查
                        # 这解决了"变更 34 次"中数字颜色不同(红色)但应该在同一文本框的问题
                        elem_is_number = LayoutAnalyzerV2._is_purely_numeric(elem_text)
                        other_is_number = LayoutAnalyzerV2._is_purely_numeric(other_text)
                        is_tight_number = (abs(x_gap) <= 1.0 and (elem_is_number or other_is_number))

                        # 放宽样式检查：只要求颜色相近和字号接近，允许不同字体（如中文+符号+数字）
                        # 但如果涉及空格或紧密相邻的数字，则忽略颜色要求
                        style_compatible = (
                            abs(other_font_size - elem_font_size) <= 2 and
                            (colors_match or is_space_involved or is_tight_number)
                            # 移除same_style检查，允许不同字体的同行文本合并
                        )

                        # Debug logging for style incompatibility
                        if not style_compatible and (elem_text.isspace() or other_text.isspace() or
                                                     '变更' in elem_text or '变更' in other_text or
                                                     elem_text == '34' or other_text == '34'):
                            logger.warning(f"[STYLE] Style incompatible: '{elem_text}' (size={elem_font_size}, color={elem_color}) + "
                                         f"'{other_text}' (size={other_font_size}, color={other_color}), "
                                         f"size_diff={abs(other_font_size - elem_font_size):.1f}, colors_match={colors_match}")

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

                            # 放宽颜色匹配：允许相近的颜色（如#000000和#14161A）
                            colors_match = LayoutAnalyzerV2._colors_similar(other_color, elem_color, threshold=30)

                            # 特殊处理：如果任意一侧是纯空格，忽略颜色检查（空格不可见，颜色无关紧要）
                            is_space_involved = elem_text.isspace() or other_text.isspace()

                            # 特殊处理：如果gap非常小(<= 1pt)且涉及数字，也忽略颜色检查
                            elem_is_number = LayoutAnalyzerV2._is_purely_numeric(elem_text)
                            other_is_number = LayoutAnalyzerV2._is_purely_numeric(other_text)
                            is_tight_number = (abs(left_gap) <= 1.0 and (elem_is_number or other_is_number))

                            # 放宽样式检查：只要求颜色相近和字号接近，允许不同字体（如中文+符号+数字）
                            # 但如果涉及空格或紧密相邻的数字，则忽略颜色要求
                            style_compatible = (
                                abs(other_font_size - elem_font_size) <= 2 and
                                (colors_match or is_space_involved or is_tight_number)
                                # 移除same_style检查，允许不同字体的同行文本合并
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
                        elem_content = elem.get('content', '')
                        other_content = other.get('content', '')

                        # Special logging for whitespace or number merging
                        if (elem_content.isspace() or other_content.isspace() or
                            '变更' in elem_content or '变更' in other_content or
                            elem_content == '34' or other_content == '34'):
                            logger.info(f"[WHITESPACE/NUMBER] Merging '{elem_content}' + '{other_content}' "
                                       f"(gap={actual_gap:.2f}pt, reason={merge_reason})")
                        elif abs(actual_gap) > 2.0:
                            logger.debug(f"Merging '{elem_content}' + '{other_content}' "
                                       f"(gap={actual_gap:.2f}pt, reason={merge_reason})")
                    else:
                        # Log when we skip merging for interesting cases
                        elem_content = elem.get('content', '')
                        other_content = other.get('content', '')

                        # Special logging for whitespace or number merging failures
                        if (elem_content.isspace() or other_content.isspace() or
                            '变更' in elem_content or '变更' in other_content or
                            elem_content == '34' or other_content == '34'):
                            logger.warning(f"[WHITESPACE/NUMBER] NOT merging '{elem_content}' + '{other_content}' "
                                          f"(gap={x_gap:.2f}pt, reason={merge_reason})")
                        elif 2.0 < abs(x_gap) <= 10.0 and merge_reason:
                            logger.debug(f"Not merging '{elem_content}' + '{other_content}' "
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
                'z_index': 20000  # Text should appear on top of shapes and images
            })

        # 第二步：合并垂直方向的段落文本
        # 暂时禁用：此功能会错误地合并同一行但不同X坐标的文本
        # 例如："威胁监测响应"与下方同名文本合并，而忽略了右侧的"/ 事件&威胁总览"
        # regions = self._merge_paragraph_regions(regions)

        return regions

    def _merge_paragraph_regions(self, regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并垂直方向上的段落文本（多行合并为单个文本框）

        判断标准：
        1. 相同或相近的左边界（左对齐，允许5pt误差）
        2. 行间距 < 字号 × 1.5（正常行距范围）
        3. 相同角色（role）和相近样式
        4. 不是标题、表格等特殊内容

        Args:
            regions: 已经过水平合并的文本区域列表

        Returns:
            合并后的文本区域列表
        """
        if not regions:
            return []

        # 按Y坐标排序
        sorted_regions = sorted(regions, key=lambda r: r['bbox'][1])

        merged_regions = []
        processed = set()

        for i, region in enumerate(sorted_regions):
            if i in processed:
                continue

            # 不合并标题、表格等特殊内容
            role = region.get('role', 'text')
            if role in ['title', 'subtitle', 'header', 'footer']:
                merged_regions.append(region)
                processed.add(i)
                continue

            # 获取当前region的信息
            bbox = region['bbox']  # [x1, y1, x2, y2]
            left_x = bbox[0]
            right_x = bbox[2]
            bottom_y = bbox[3]
            elements = region.get('elements', [])

            # 获取字号（用于计算行距）
            avg_font_size = sum(e.get('font_size', 12) for e in elements) / len(elements) if elements else 12
            max_line_spacing = avg_font_size * 1.5  # 正常行距阈值

            # 尝试寻找下方的段落行
            paragraph_regions = [region]
            paragraph_indices = [i]

            for j in range(i + 1, len(sorted_regions)):
                if j in processed:
                    continue

                next_region = sorted_regions[j]
                next_role = next_region.get('role', 'text')
                next_bbox = next_region['bbox']
                next_left_x = next_bbox[0]
                next_top_y = next_bbox[1]
                next_elements = next_region.get('elements', [])

                # 检查1：角色必须是普通文本
                if next_role not in ['text', 'body']:
                    break

                # 检查2：左对齐（允许5pt误差）
                left_alignment_tolerance = 5.0
                if abs(next_left_x - left_x) > left_alignment_tolerance:
                    break

                # 检查3：行间距（当前region底部到下一region顶部的距离）
                line_gap = next_top_y - bottom_y
                if line_gap < 0 or line_gap > max_line_spacing:
                    break

                # 检查4：字号相近（允许2pt差异）
                next_avg_font_size = sum(e.get('font_size', 12) for e in next_elements) / len(next_elements) if next_elements else 12
                if abs(next_avg_font_size - avg_font_size) > 2:
                    break

                # 检查5：颜色相近
                # 获取主要颜色（第一个元素的颜色）
                current_color = elements[0].get('color', '#000000') if elements else '#000000'
                next_color = next_elements[0].get('color', '#000000') if next_elements else '#000000'
                if not LayoutAnalyzerV2._colors_similar(current_color, next_color, threshold=30):
                    break

                # 符合条件，加入段落
                paragraph_regions.append(next_region)
                paragraph_indices.append(j)
                bottom_y = next_bbox[3]  # 更新底部边界

            # 如果找到多行段落，合并它们
            if len(paragraph_regions) > 1:
                # 合并所有elements
                merged_elements = []
                text_lines = []

                for para_region in paragraph_regions:
                    merged_elements.extend(para_region.get('elements', []))
                    text_lines.append(para_region.get('text', ''))

                # 用换行符连接文本
                merged_text = '\n'.join(text_lines)

                # 计算合并后的bbox
                merged_bbox = self._calculate_bbox(merged_elements)

                # 创建合并后的region
                merged_region = {
                    'role': role,
                    'bbox': merged_bbox,
                    'elements': merged_elements,
                    'text': merged_text,
                    'z_index': region.get('z_index', 20000)
                }

                merged_regions.append(merged_region)

                # 标记所有参与合并的region为已处理
                for idx in paragraph_indices:
                    processed.add(idx)

                logger.debug(f"Merged {len(paragraph_regions)} lines into paragraph: {merged_text[:50]}...")
            else:
                # 单行，直接添加
                merged_regions.append(region)
                processed.add(i)

        return merged_regions

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
