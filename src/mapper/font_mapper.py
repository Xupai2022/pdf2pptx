"""
Font Mapper - Maps PDF fonts to PowerPoint fonts
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FontMapper:
    """
    Maps PDF font names to PowerPoint-compatible font names.
    
    CRITICAL FONT MAPPING STRATEGY:
    ================================
    For Microsoft YaHei fonts, we use "Microsoft YaHei UI" (English name) instead of
    "微软雅黑" (Chinese name) because:
    
    1. Microsoft YaHei UI has REAL Bold font files (separate font file for bold weight)
    2. "微软雅黑" only supports ALGORITHMIC bold (software simulation, looks lighter)
    3. When PPT sees "Microsoft YaHei UI" + bold=True, it loads the real bold font file
    4. This matches the visual appearance of the PDF exactly
    
    The key difference:
    - PDF: MicrosoftYaHei-Bold → Real bold font embedded in PDF
    - PPT with "微软雅黑": Software-simulated bold (looks thin)
    - PPT with "Microsoft YaHei UI" + bold=True: Real bold font (matches PDF)
    """
    
    # Default font mapping
    DEFAULT_FONT_MAP = {
        # Chinese fonts - Use Microsoft YaHei UI for real bold support
        'SimHei': 'Microsoft YaHei UI',
        'SimSun': '宋体',
        'SimSun-ExtB': '宋体',
        'NSimSun': '新宋体',
        'FangSong': '仿宋',
        'KaiTi': '楷体',
        'MicrosoftYaHei': 'Microsoft YaHei UI',  # Use UI variant for real bold support
        'MicrosoftYaHei-Bold': 'Microsoft YaHei UI',  # Use UI variant, bold set via attribute
        'MicrosoftYaHeiUI': 'Microsoft YaHei UI',
        'Microsoft-YaHei': 'Microsoft YaHei UI',

        # Western fonts
        'Helvetica': 'Arial',
        'Helvetica-Bold': 'Arial',
        'Times': 'Times New Roman',
        'Times-Roman': 'Times New Roman',
        'Times-Bold': 'Times New Roman',
        'Courier': 'Courier New',
        'Courier-Bold': 'Courier New',
        'Arial': 'Arial',
        'Arial-Bold': 'Arial',
        'Verdana': 'Verdana',
        'Verdana-Bold': 'Verdana',
        'Tahoma': 'Tahoma',
        'Georgia': 'Georgia'
    }
    
    def __init__(self, config: Dict):
        """
        Initialize Font Mapper.
        
        Args:
            config: Configuration dictionary with font mapping
        """
        self.config = config
        self.font_map = config.get('font_mapping', {})
        # Merge with default map
        self.font_map = {**self.DEFAULT_FONT_MAP, **self.font_map}
        self.default_font = config.get('default_font', 'Arial')
    
    def map_font(self, pdf_font_name: str) -> tuple:
        """
        Map a PDF font name to PowerPoint font and detect if it's a bold variant.
        
        CRITICAL: This method now returns a tuple (font_name, should_be_bold)
        to preserve bold information from font name suffixes.
        
        Args:
            pdf_font_name: Font name from PDF (e.g., "MicrosoftYaHei-Bold")
            
        Returns:
            Tuple of (mapped_font_name, should_be_bold)
            - mapped_font_name: PowerPoint font name
            - should_be_bold: True if font name indicates bold variant
        """
        if not pdf_font_name:
            return (self.default_font, False)
        
        # Detect if font name indicates bold
        # Check for -Bold suffix or Bold in the name
        should_be_bold = False
        if '-Bold' in pdf_font_name or pdf_font_name.endswith('Bold'):
            should_be_bold = True
            logger.debug(f"Detected bold font from name: {pdf_font_name}")
        
        # Try exact match
        if pdf_font_name in self.font_map:
            return (self.font_map[pdf_font_name], should_be_bold)
        
        # Try base font name (remove suffixes like -Bold, -Italic)
        # Also remove PDF font subset prefixes (e.g., "AAAAAA+")
        base_font = pdf_font_name.split('-')[0].split('+')[-1]
        if base_font in self.font_map:
            return (self.font_map[base_font], should_be_bold)
        
        # Try partial match
        for pdf_name, ppt_name in self.font_map.items():
            if pdf_name.lower() in pdf_font_name.lower():
                return (ppt_name, should_be_bold)
        
        # Fall back to default
        logger.debug(f"No mapping found for font '{pdf_font_name}', using default: {self.default_font}")
        return (self.default_font, False)
    
    def is_cjk_font(self, font_name: str) -> bool:
        """
        Check if font is a CJK (Chinese/Japanese/Korean) font.
        
        Args:
            font_name: Font name to check
            
        Returns:
            True if CJK font
        """
        cjk_fonts = ['SimHei', 'SimSun', 'Microsoft YaHei', '宋体', '黑体', 
                     '楷体', '仿宋', 'KaiTi', 'FangSong', 'NSimSun']
        
        return any(cjk in font_name for cjk in cjk_fonts)
