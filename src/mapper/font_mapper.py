"""
Font Mapper - Maps PDF fonts to PowerPoint fonts
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FontMapper:
    """
    Maps PDF font names to PowerPoint-compatible font names.
    """
    
    # Default font mapping
    DEFAULT_FONT_MAP = {
        'SimHei': 'Microsoft YaHei',
        'SimSun': '宋体',
        'SimSun-ExtB': '宋体',
        'NSimSun': '新宋体',
        'FangSong': '仿宋',
        'KaiTi': '楷体',
        'Microsoft-YaHei': 'Microsoft YaHei',
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
    
    def map_font(self, pdf_font_name: str) -> str:
        """
        Map a PDF font name to PowerPoint font.
        
        Args:
            pdf_font_name: Font name from PDF
            
        Returns:
            Mapped PowerPoint font name
        """
        if not pdf_font_name:
            return self.default_font
        
        # Try exact match
        if pdf_font_name in self.font_map:
            return self.font_map[pdf_font_name]
        
        # Try base font name (remove suffixes like -Bold, -Italic)
        base_font = pdf_font_name.split('-')[0].split('+')[-1]
        if base_font in self.font_map:
            return self.font_map[base_font]
        
        # Try partial match
        for pdf_name, ppt_name in self.font_map.items():
            if pdf_name.lower() in pdf_font_name.lower():
                return ppt_name
        
        # Fall back to default
        logger.debug(f"No mapping found for font '{pdf_font_name}', using default: {self.default_font}")
        return self.default_font
    
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
