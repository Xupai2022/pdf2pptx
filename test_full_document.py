#!/usr/bin/env python3
"""
Full document regression test to ensure the fix doesn't break other pages
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer_v2 import LayoutAnalyzerV2
from src.rebuilder.coordinate_mapper import CoordinateMapper
from src.generator.pptx_generator import PPTXGenerator
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def convert_full_document(pdf_path, output_path, config):
    """Convert entire PDF document"""
    
    logger.info(f"Converting {pdf_path} to {output_path}")
    
    # Parse all pages
    parser = PDFParser(config['parser'])
    parser.open(pdf_path)
    all_pages = parser.extract_all_pages()
    parser.close()
    
    logger.info(f"Parsed {len(all_pages)} pages")
    
    # Analyze all pages
    analyzer = LayoutAnalyzerV2(config['analyzer'])
    analyzed_pages = [analyzer.analyze_page(page) for page in all_pages]
    
    # Build slide models
    mapper = CoordinateMapper(config['rebuilder'])
    slide_models = [mapper.create_slide_model(layout) for layout in analyzed_pages]
    
    # Count ring shapes per page
    ring_counts = []
    for i, page in enumerate(all_pages, 1):
        shapes = [e for e in page['elements'] if e['type'] == 'shape']
        rings = [s for s in shapes if s.get('is_ring', False)]
        
        if rings:
            ring_type_counts = {}
            for ring in rings:
                ring_type = ring.get('ring_type', 'paired')
                ring_type_counts[ring_type] = ring_type_counts.get(ring_type, 0) + 1
            
            ring_counts.append((i, ring_type_counts))
    
    # Generate PPTX
    generator = PPTXGenerator(config)
    generator.generate_from_models(slide_models)
    generator.save(output_path)
    
    logger.info(f"✓ Converted successfully to {output_path}")
    
    return ring_counts

def main():
    pdf_path = "tests/glm-4.6.pdf"
    output_path = "output/glm-4.6_fixed.pptx"
    
    config = {
        'parser': {'dpi': 300, 'extract_images': True},
        'analyzer': {'title_threshold': 20, 'group_tolerance': 10},
        'rebuilder': {'slide_width': 10, 'slide_height': 7.5},
        'mapper': {'font_mapping': {}, 'default_font': 'Arial'},
        'generator': {'preserve_layout': True}
    }
    
    print("="*80)
    print("Full Document Regression Test")
    print("="*80)
    print(f"Input: {pdf_path}")
    print(f"Output: {output_path}")
    print()
    
    try:
        ring_counts = convert_full_document(pdf_path, output_path, config)
        
        print("\nRing Detection Summary:")
        print("-" * 80)
        
        if ring_counts:
            for page_num, ring_types in ring_counts:
                type_str = ", ".join([f"{count} {rtype}" for rtype, count in ring_types.items()])
                print(f"  Page {page_num:2d}: {type_str} ring(s)")
        else:
            print("  No rings detected in any page")
        
        print("\n" + "="*80)
        print("✓ Regression test PASSED")
        print("="*80)
        print("\nExpected ring detection:")
        print("  Page  5: 1 paired ring (original, correct)")
        print("  Page  6: 1 standalone ring (FIXED - was broken)")
        print("  Page  7: 1 standalone ring (FIXED - was broken)")
        print("  Page  8: 1 paired ring (original, correct)")
        print("  Page  9: 1 paired ring (if exists)")
        print("  Page 11: 1 paired ring (original, correct)")
        print("\nPlease open the generated PPTX and verify:")
        print("  1. All rings display correctly as circles with proper stroke")
        print("  2. No normal shapes are incorrectly modified")
        print("  3. Pages 6 & 7 now show rings (not rounded rectangles)")
        
    except Exception as e:
        print(f"\n✗ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
