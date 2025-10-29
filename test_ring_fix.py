#!/usr/bin/env python3
"""
Test the ring fix by converting problem pages to PPTX
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer_v2 import LayoutAnalyzerV2
from src.rebuilder.coordinate_mapper import CoordinateMapper
from src.generator.pptx_generator import PPTXGenerator
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def convert_single_page(pdf_path, page_num, output_path, config):
    """Convert a single page to PPTX"""
    
    # Parse PDF
    parser = PDFParser(config['parser'])
    parser.open(pdf_path)
    page_data = parser.extract_page_elements(page_num - 1)
    parser.close()
    
    # Analyze layout
    analyzer = LayoutAnalyzerV2(config['analyzer'])
    layout_data = analyzer.analyze_page(page_data)
    
    # Build slide model
    mapper = CoordinateMapper(config['rebuilder'])
    slide_model = mapper.create_slide_model(layout_data)
    
    # Generate PPTX
    generator = PPTXGenerator(config)
    generator.generate_from_models([slide_model])
    generator.save(output_path)
    
    logger.info(f"✓ Page {page_num} converted to {output_path}")
    
    # Report ring shapes
    shapes = [e for e in page_data['elements'] if e['type'] == 'shape']
    rings = [s for s in shapes if s.get('is_ring', False)]
    
    if rings:
        logger.info(f"  Found {len(rings)} ring shape(s)")
        for ring in rings:
            ring_type = ring.get('ring_type', 'paired')
            logger.info(f"    - {ring_type} ring at ({ring['x']:.0f}, {ring['y']:.0f}), "
                       f"stroke width: {ring.get('stroke_width', 0):.1f}pt")

def main():
    pdf_path = "tests/glm-4.6.pdf"
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Configuration
    config = {
        'parser': {'dpi': 300, 'extract_images': True},
        'analyzer': {'title_threshold': 20, 'group_tolerance': 10},
        'rebuilder': {'slide_width': 10, 'slide_height': 7.5},
        'mapper': {'font_mapping': {}, 'default_font': 'Arial'},
        'generator': {'preserve_layout': True}
    }
    
    logger.info("="*80)
    logger.info("Testing Ring Shape Fix")
    logger.info("="*80)
    
    # Test pages
    test_cases = [
        (5, "page5_correct_ring.pptx", "Should show single-color ring (100%)"),
        (6, "page6_fixed_ring.pptx", "Should show ring (previously showed square)"),
        (7, "page7_fixed_ring.pptx", "Should show ring (previously showed square)"),
        (8, "page8_ring.pptx", "Should show ring with pie chart segments nearby"),
        (11, "page11_ring.pptx", "Should show ring with bar chart segments nearby"),
    ]
    
    for page_num, filename, description in test_cases:
        logger.info(f"\nPage {page_num}: {description}")
        output_path = str(output_dir / filename)
        
        try:
            convert_single_page(pdf_path, page_num, output_path, config)
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("\n" + "="*80)
    logger.info("Test Complete")
    logger.info("="*80)
    logger.info(f"Please review the generated PPTX files in {output_dir}/")
    logger.info("Verify that:")
    logger.info("  1. Pages 6 & 7 now show rings (not rounded squares)")
    logger.info("  2. All rings render with correct stroke width")
    logger.info("  3. No other shapes are incorrectly modified")

if __name__ == "__main__":
    main()
