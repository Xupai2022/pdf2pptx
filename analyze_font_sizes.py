#!/usr/bin/env python3
"""
Analyze font sizes and element dimensions from PDF vs HTML reference.
This script helps determine the correct conversion factors.
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parser.pdf_parser import PDFParser
from main import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def analyze_html_reference():
    """Analyze the HTML reference file for expected dimensions."""
    html_ref = {
        'canvas': {'width': 1920, 'height': 1080},
        'top_bar': {'height': 10},  # px
        'borders': {'width': 4},  # border-left px
        'fonts': {
            'h1': 48,  # px
            'h2': 36,  # px
            'h3': 28,  # px
            'p': 25,   # px
            'risk-level': 20,  # px
            'page-number': 14,  # px
            'small-text': 20,  # px (.text-sm becomes 20px in Tailwind text-sm)
        }
    }
    
    logger.info("=" * 60)
    logger.info("HTML REFERENCE VALUES (pixels)")
    logger.info("=" * 60)
    logger.info(f"Canvas: {html_ref['canvas']['width']}×{html_ref['canvas']['height']} px")
    logger.info(f"Top bar height: {html_ref['top_bar']['height']} px")
    logger.info(f"Border width: {html_ref['borders']['width']} px")
    logger.info("\nFont sizes (CSS pixels):")
    for element, size in html_ref['fonts'].items():
        logger.info(f"  {element}: {size}px")
    
    return html_ref


def analyze_pdf_extraction(pdf_path: str):
    """Analyze what values are extracted from PDF."""
    config = load_config()
    parser_config = config.get('parser', {})
    
    logger.info("\n" + "=" * 60)
    logger.info("PDF EXTRACTION ANALYSIS")
    logger.info("=" * 60)
    
    parser = PDFParser(parser_config)
    if not parser.open(pdf_path):
        logger.error(f"Failed to open PDF: {pdf_path}")
        return None
    
    # Get first page
    page_data = parser.extract_page_elements(0)
    
    logger.info(f"\nPDF Page dimensions: {page_data['width']:.2f} × {page_data['height']:.2f} pt")
    
    # Analyze text elements by font size
    font_sizes = {}
    text_elements = [e for e in page_data['elements'] if e['type'] == 'text']
    
    for elem in text_elements:
        size = elem['font_size']
        text = elem['content'][:30]  # First 30 chars
        
        if size not in font_sizes:
            font_sizes[size] = []
        font_sizes[size].append(text)
    
    logger.info(f"\nExtracted {len(text_elements)} text elements")
    logger.info("\nFont sizes found (PDF points):")
    for size in sorted(font_sizes.keys(), reverse=True):
        texts = font_sizes[size]
        logger.info(f"  {size:.1f}pt: {len(texts)} elements")
        logger.info(f"    Example: \"{texts[0]}\"")
    
    # Analyze shapes
    shape_elements = [e for e in page_data['elements'] if e['type'] == 'shape']
    logger.info(f"\nExtracted {len(shape_elements)} shape elements")
    
    # Find thin horizontal shapes (likely top bar)
    horizontal_bars = [s for s in shape_elements if s['width'] > 500 and s['height'] < 20]
    if horizontal_bars:
        logger.info("\nPotential top bars:")
        for bar in horizontal_bars[:3]:
            logger.info(f"  Size: {bar['width']:.1f} × {bar['height']:.1f} pt")
            logger.info(f"  Fill: {bar.get('fill_color', 'none')}")
    
    # Find shapes with stroke (borders)
    bordered_shapes = [s for s in shape_elements if s.get('stroke_width') and s.get('stroke_width', 0) > 0]
    if bordered_shapes:
        logger.info("\nShapes with borders:")
        stroke_widths = {}
        for shape in bordered_shapes:
            sw = shape['stroke_width']
            if sw not in stroke_widths:
                stroke_widths[sw] = 0
            stroke_widths[sw] += 1
        
        for width, count in sorted(stroke_widths.items()):
            logger.info(f"  {width:.1f}pt stroke: {count} shapes")
    
    parser.close()
    return page_data


def calculate_conversion_factors(html_ref, pdf_data):
    """Calculate the conversion factors needed."""
    logger.info("\n" + "=" * 60)
    logger.info("CONVERSION FACTOR ANALYSIS")
    logger.info("=" * 60)
    
    # DPI calculation
    html_width = html_ref['canvas']['width']
    pdf_width = pdf_data['width']
    
    # Standard conversions
    dpi_72 = html_width / (pdf_width / 72)  # Assuming 72 DPI
    dpi_96 = html_width / (pdf_width / 96)  # Assuming 96 DPI
    dpi_144 = html_width / (pdf_width / 144)  # Assuming 144 DPI
    
    logger.info(f"\nCanvas width comparison:")
    logger.info(f"  HTML: {html_width} px")
    logger.info(f"  PDF: {pdf_width:.2f} pt")
    logger.info(f"\nDPI scenarios:")
    logger.info(f"  72 DPI:  {html_width} px ÷ ({pdf_width:.2f}pt ÷ 72) = {dpi_72:.2f}")
    logger.info(f"  96 DPI:  {html_width} px ÷ ({pdf_width:.2f}pt ÷ 96) = {dpi_96:.2f}")
    logger.info(f"  144 DPI: {html_width} px ÷ ({pdf_width:.2f}pt ÷ 144) = {dpi_144:.2f}")
    
    # PowerPoint standard
    ppt_width_72 = pdf_width / 72
    ppt_width_96 = pdf_width / 96
    
    logger.info(f"\nPowerPoint slide width:")
    logger.info(f"  At 72 DPI: {ppt_width_72:.3f} inches (standard)")
    logger.info(f"  At 96 DPI: {ppt_width_96:.3f} inches")
    
    # Recommended settings
    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDED CONFIG SETTINGS")
    logger.info("=" * 60)
    logger.info(f"\nrebuilder:")
    logger.info(f"  slide_width: {ppt_width_72:.3f}  # inches (1920px at 72 DPI)")
    logger.info(f"  slide_height: {pdf_data['height'] / 72:.3f}  # inches (1080px at 72 DPI)")
    
    # Font size analysis
    logger.info(f"\nmapper:")
    logger.info(f"  font_size_scale: 1.0  # Start with 1:1 PDF pt → PPT pt")
    logger.info(f"  # Then adjust based on actual comparison")
    
    # Element dimensions
    top_bar_px = html_ref['top_bar']['height']
    top_bar_inches = top_bar_px / 72
    border_px = html_ref['borders']['width']
    border_inches = border_px / 72
    
    logger.info(f"\nElement dimensions (HTML px → PPT inches at 72 DPI):")
    logger.info(f"  Top bar height: {top_bar_px}px = {top_bar_inches:.4f} inches = {top_bar_px}pt")
    logger.info(f"  Border width: {border_px}px = {border_inches:.4f} inches = {border_px}pt")
    
    logger.info("\n" + "=" * 60)
    logger.info("KEY INSIGHT")
    logger.info("=" * 60)
    logger.info("For HTML-to-PPT conversion:")
    logger.info("  • Use 72 DPI as conversion factor (PowerPoint standard)")
    logger.info("  • 1 HTML pixel = 1 PDF point = 1 PPT point at 72 DPI")
    logger.info("  • slide_width = 1920px ÷ 72 = 26.67 inches")
    logger.info("  • font_size_scale = 1.0 (no scaling needed if PDF matches HTML)")


def main():
    """Main analysis function."""
    # Check for test PDF
    test_pdf = Path("tests/test_sample.pdf")
    if not test_pdf.exists():
        logger.error(f"Test PDF not found: {test_pdf}")
        return
    
    # Analyze HTML reference
    html_ref = analyze_html_reference()
    
    # Analyze PDF extraction
    pdf_data = analyze_pdf_extraction(str(test_pdf))
    
    if pdf_data:
        # Calculate conversions
        calculate_conversion_factors(html_ref, pdf_data)


if __name__ == "__main__":
    main()
