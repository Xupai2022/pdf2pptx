#!/usr/bin/env python3
"""
Layer-by-layer debugging tool for PDF to PPTX conversion
Compares each layer's output with the original HTML structure
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from main import load_config, setup_logging
from src.parser.pdf_parser import PDFParser
# Removed v1 import, now using v2 only
from src.analyzer.layout_analyzer_v2 import LayoutAnalyzerV2
from src.rebuilder.coordinate_mapper import CoordinateMapper


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def debug_layer1_parser(pdf_path, config):
    """Debug Layer 1: PDF Parser output."""
    print_section("LAYER 1: PDF Parser Output")
    
    parser = PDFParser(config['parser'])
    parser.open(pdf_path)
    page_data = parser.extract_page_elements(0)
    parser.close()
    
    print(f"Page dimensions: {page_data['width']:.2f} x {page_data['height']:.2f} points")
    print(f"Total elements extracted: {len(page_data['elements'])}")
    
    # Group elements by type
    text_elements = [e for e in page_data['elements'] if e['type'] == 'text']
    image_elements = [e for e in page_data['elements'] if e['type'] == 'image']
    shape_elements = [e for e in page_data['elements'] if e['type'] == 'shape']
    
    print(f"\nElement breakdown:")
    print(f"  Text elements: {len(text_elements)}")
    print(f"  Image elements: {len(image_elements)}")
    print(f"  Shape elements: {len(shape_elements)}")
    
    # Analyze text elements
    print(f"\n{'─'*80}")
    print("Text Elements Analysis:")
    print(f"{'─'*80}")
    
    # Group by font size
    from collections import defaultdict
    size_groups = defaultdict(list)
    for elem in text_elements:
        size = round(elem.get('font_size', 0))
        size_groups[size].append(elem)
    
    print(f"\nText grouped by font size:")
    for size in sorted(size_groups.keys(), reverse=True):
        elements = size_groups[size]
        print(f"\n  Font size {size}pt ({len(elements)} elements):")
        for i, elem in enumerate(elements[:3]):  # Show first 3
            content = elem.get('content', '')[:50]
            print(f"    [{i+1}] \"{content}\" @ ({elem['x']:.1f}, {elem['y']:.1f})")
        if len(elements) > 3:
            print(f"    ... and {len(elements)-3} more")
    
    # Analyze shapes
    print(f"\n{'─'*80}")
    print("Shape Elements Analysis:")
    print(f"{'─'*80}")
    
    for i, shape in enumerate(shape_elements[:10]):
        print(f"\n  Shape {i+1}:")
        print(f"    Type: {shape.get('shape_type', 'unknown')}")
        print(f"    Position: ({shape['x']:.1f}, {shape['y']:.1f})")
        print(f"    Size: {shape['width']:.1f} x {shape['height']:.1f}")
        print(f"    Fill: {shape.get('fill_color', 'none')}")
        print(f"    Stroke: {shape.get('stroke_color', 'none')}")
    
    return page_data


def debug_layer2_analyzer(page_data, config):
    """Debug Layer 2: Layout Analyzer output."""
    print_section("LAYER 2: Layout Analyzer Output (V2 - Improved)")
    
    analyzer = LayoutAnalyzerV2(config['analyzer'])
    layout_data = analyzer.analyze_page(page_data)
    
    print(f"Page dimensions: {layout_data['width']:.2f} x {layout_data['height']:.2f}")
    print(f"Layout regions detected: {len(layout_data['layout'])}")
    
    print(f"\n{'─'*80}")
    print("Layout Regions:")
    print(f"{'─'*80}")
    
    for i, region in enumerate(layout_data['layout']):
        role = region.get('role', 'unknown')
        bbox = region.get('bbox', [0, 0, 0, 0])
        elements = region.get('elements', [])
        z_index = region.get('z_index', 0)
        
        print(f"\n  Region {i+1}: {role.upper()}")
        print(f"    BBox: ({bbox[0]:.1f}, {bbox[1]:.1f}) → ({bbox[2]:.1f}, {bbox[3]:.1f})")
        print(f"    Size: {bbox[2]-bbox[0]:.1f} x {bbox[3]-bbox[1]:.1f}")
        print(f"    Z-index: {z_index}")
        print(f"    Elements: {len(elements)}")
        
        # Show text content if available
        if role in ['title', 'subtitle', 'paragraph']:
            text = region.get('text', '')
            if not text:
                # Try to extract from elements
                text_parts = [e.get('content', '') for e in elements if e.get('type') == 'text']
                text = ' '.join(text_parts)
            if text:
                print(f"    Content: \"{text[:80]}...\"")
    
    return layout_data


def debug_layer3_rebuilder(layout_data, config):
    """Debug Layer 3: Element Rebuilder output."""
    print_section("LAYER 3: Element Rebuilder / Coordinate Mapper Output")
    
    mapper = CoordinateMapper(config['rebuilder'])
    slide_model = mapper.create_slide_model(layout_data)
    
    print(f"Slide dimensions: {slide_model.width}\" x {slide_model.height}\"")
    print(f"Slide title: {slide_model.title or 'None'}")
    print(f"Background color: {slide_model.background_color or 'None'}")
    print(f"Total slide elements: {len(slide_model.elements)}")
    
    print(f"\n{'─'*80}")
    print("Slide Elements:")
    print(f"{'─'*80}")
    
    for i, elem in enumerate(slide_model.elements):
        print(f"\n  Element {i+1}: {elem.type.upper()}")
        print(f"    Position: ({elem.position['x']:.2f}\", {elem.position['y']:.2f}\")")
        print(f"    Size: {elem.position['width']:.2f}\" x {elem.position['height']:.2f}\"")
        print(f"    Z-index: {elem.z_index}")
        
        if elem.type == 'text':
            content = str(elem.content)[:60]
            print(f"    Content: \"{content}...\"")
            print(f"    Font: {elem.style.get('font_name', 'unknown')}")
            print(f"    Font size: {elem.style.get('font_size', 0)}pt")
            print(f"    Color: {elem.style.get('color', 'unknown')}")
        elif elem.type == 'image':
            print(f"    Image size: {len(elem.content)} bytes")
        elif elem.type == 'shape':
            print(f"    Shape type: {elem.content}")
            print(f"    Fill: {elem.style.get('fill_color', 'none')}")
    
    return slide_model


def compare_with_html():
    """Compare with original HTML structure."""
    print_section("HTML REFERENCE STRUCTURE")
    
    print("Expected structure from HTML (1920x1080):")
    print("\n1. TOP BAR (10px height, blue #0a4275)")
    print("   Position: top of page, full width")
    
    print("\n2. TITLE SECTION")
    print("   - Main title: '风险资产深度剖析' (48px, bold, blue)")
    print("   - Subtitle: '典型高风险资产案例展示' (36px, gray)")
    print("   - Underline: 20px wide, 1px height, blue")
    
    print("\n3. STATISTICS CARDS (3 columns, grid)")
    print("   Card 1: 高风险资产总数 - 8个 (red, 4xl)")
    print("   Card 2: 风险分布 - 高危4, 中危12, 低危19")
    print("   Card 3: 云存储风险 - 3个 (red, 4xl)")
    print("   Background: rgba(10, 66, 117, 0.08)")
    print("   Border-left: 4px blue")
    
    print("\n4. DETAILS SECTION (2 columns)")
    print("   Left: 关键风险资产 (3 items with icons)")
    print("   Right: 最新发现威胁 (3 items with CVSS scores)")
    print("   Icons: FontAwesome icons")
    
    print("\n5. IMPACT ANALYSIS (4 columns)")
    print("   - 敏感数据暴露")
    print("   - 远程代码执行")
    print("   - 凭据泄露")
    print("   - 已知CVE利用")
    
    print("\n6. PAGE NUMBER")
    print("   Position: bottom-right")
    print("   Content: '5'")
    
    print("\nColors:")
    print("  Primary blue: rgb(10, 66, 117) / #0a4275")
    print("  Red (danger): #dc2626")
    print("  Gray (text): #333, #666")


def main():
    """Run layer-by-layer debugging."""
    print("\n" + "="*80)
    print("  PDF to PPTX Layer-by-Layer Debugging")
    print("="*80)
    
    setup_logging('INFO')
    
    pdf_path = 'tests/test_sample.pdf'
    config = load_config()
    
    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return 1
    
    # Show HTML reference first
    compare_with_html()
    
    # Debug each layer
    try:
        page_data = debug_layer1_parser(pdf_path, config)
        layout_data = debug_layer2_analyzer(page_data, config)
        slide_model = debug_layer3_rebuilder(layout_data, config)
        
        print_section("DEBUGGING COMPLETE")
        print("✅ All layers executed successfully")
        print("\nNext steps:")
        print("1. Compare Layer 1 output with HTML structure")
        print("2. Verify font sizes match (48px, 36px, 28px, 25px)")
        print("3. Check if colors are extracted correctly (#0a4275, #dc2626)")
        print("4. Verify shape detection (top bar, cards, borders)")
        print("5. Check coordinate mapping accuracy")
        
    except Exception as e:
        print(f"\n❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
