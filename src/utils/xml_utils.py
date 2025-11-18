"""
XML Utilities for PowerPoint XML manipulation
"""

import logging
from lxml import etree
from typing import Optional

logger = logging.getLogger(__name__)


def set_run_font_xml(run, font_name: str, is_cjk: bool = False):
    """
    Set font via XML manipulation at the rPr (run properties) level.

    This sets both Latin and East Asian font attributes in the XML to ensure
    compatibility across different PowerPoint applications (Microsoft PowerPoint, WPS, etc.).

    Args:
        run: PowerPoint run object
        font_name: Font name to apply
        is_cjk: Whether this is a CJK (Chinese, Japanese, Korean) font
    """
    try:
        logger.info(f"XML Font Setting: Setting run font to '{font_name}' (CJK: {is_cjk})")

        # Access the run properties element (rPr) via the underlying lxml element (run._r)
        from pptx.oxml.xmlchemy import BaseOxmlElement
        rPr = run._r.get_or_add_rPr()

        # Define XML namespaces
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}

        # Check current XML before changes
        existing_latin = rPr.find('.//a:latin', ns)
        existing_ea = rPr.find('.//a:ea', ns)
        existing_cs = rPr.find('.//a:cs', ns)

        if existing_latin is not None:
            old_latin = existing_latin.get('typeface', 'NONE')
            logger.debug(f"XML Font Setting: Removing existing latin='{old_latin}'")
            rPr.remove(existing_latin)

        if existing_ea is not None:
            old_ea = existing_ea.get('typeface', 'NONE')
            logger.debug(f"XML Font Setting: Removing existing ea='{old_ea}'")
            rPr.remove(existing_ea)

        if existing_cs is not None:
            old_cs = existing_cs.get('typeface', 'NONE')
            logger.debug(f"XML Font Setting: Removing existing cs='{old_cs}'")
            rPr.remove(existing_cs)

        # Add Latin font element (for Western characters)
        latin_elem = etree.SubElement(
            rPr,
            '{http://schemas.openxmlformats.org/drawingml/2006/main}latin'
        )
        latin_elem.set('typeface', font_name)
        logger.debug(f"XML Font Setting: Added latin='{font_name}'")

        # For CJK fonts, also set East Asian font element
        if is_cjk:
            ea_elem = etree.SubElement(
                rPr,
                '{http://schemas.openxmlformats.org/drawingml/2006/main}ea'
            )
            ea_elem.set('typeface', font_name)
            logger.info(f"XML Font Setting: CJK font detected, added ea='{font_name}'")
        else:
            # For non-CJK fonts, set ea to the same font for consistency
            ea_elem = etree.SubElement(
                rPr,
                '{http://schemas.openxmlformats.org/drawingml/2006/main}ea'
            )
            ea_elem.set('typeface', font_name)
            logger.debug(f"XML Font Setting: Non-CJK font, added ea='{font_name}' for consistency")

        # Set Complex Script font element (for bidirectional/Arabic text)
        cs_elem = etree.SubElement(
            rPr,
            '{http://schemas.openxmlformats.org/drawingml/2006/main}cs'
        )
        cs_elem.set('typeface', font_name)
        logger.debug(f"XML Font Setting: Added cs='{font_name}'")

        logger.info(f"XML Font Setting: SUCCESS - Set run font to '{font_name}' (CJK: {is_cjk})")

    except Exception as e:
        logger.error(f"XML Font Setting: FAILED - Error setting run font '{font_name}': {e}", exc_info=True)


def is_cjk_font(font_name: str) -> bool:
    """
    Check if a font is a CJK (Chinese, Japanese, Korean) font.

    Args:
        font_name: Font name to check

    Returns:
        True if CJK font, False otherwise
    """
    if not font_name:
        return False

    # Common CJK font names (simplified and traditional)
    cjk_patterns = [
        'SimHei', 'SimSun', 'Microsoft YaHei', '微软雅黑', '宋体',
        '黑体', '楷体', '仿宋', 'KaiTi', 'FangSong',
        'NSimSun', '新宋体', 'KaiTi_GB2312', 'FangSong_GB2312',
        'MS Mincho', 'MS Gothic', 'MS PGothic', 'MS PMincho',
        'Yu Mincho', 'Yu Gothic', 'Batang', 'Dotum',
        'Hiragino', 'Hira', 'Meiryo', 'Noto Sans CJK'
    ]

    font_lower = font_name.lower()
    return any(pattern.lower() in font_lower for pattern in cjk_patterns)
