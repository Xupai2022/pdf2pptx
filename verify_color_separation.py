#!/usr/bin/env python3
"""
验证纯色和透明色的正确分离
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser.pdf_parser import PDFParser
import yaml

def verify_color_separation(pdf_path):
    """验证颜色和透明度的分离"""
    print(f"Verifying color separation for: {pdf_path}")
    print("=" * 80)
    
    # Load config
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Parse PDF
    parser = PDFParser(config.get('parser', {}))
    if not parser.open(pdf_path):
        print("Failed to open PDF")
        return
    
    # Check pages 1-5
    for page_num in range(min(5, parser.get_page_count())):
        page_data = parser.extract_page_elements(page_num)
        
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1}")
        print(f"{'='*80}")
        
        # Categorize shapes
        pure_opaque = []  # 纯色完全不透明 (opacity = 1.0)
        semi_transparent = []  # 半透明 (opacity < 1.0)
        
        for elem in page_data['elements']:
            if elem['type'] == 'shape':
                color = elem.get('fill_color', 'None')
                opacity = elem.get('fill_opacity', 1.0)
                
                if opacity == 1.0:
                    pure_opaque.append(elem)
                else:
                    semi_transparent.append(elem)
        
        # Display pure opaque shapes
        print(f"\n[Pure Opaque Shapes] (opacity = 1.0): {len(pure_opaque)}")
        color_counts = {}
        for elem in pure_opaque:
            color = elem.get('fill_color', 'None')
            color_counts[color] = color_counts.get(color, 0) + 1
        for color, count in sorted(color_counts.items()):
            print(f"  {color}: {count} shapes")
        
        # Display semi-transparent shapes with details
        print(f"\n[Semi-Transparent Shapes] (opacity < 1.0): {len(semi_transparent)}")
        for elem in semi_transparent:
            color = elem.get('fill_color', 'None')
            opacity = elem.get('fill_opacity', 1.0)
            print(f"  Color: {color}, Opacity: {opacity:.4f}")
            print(f"    Position: ({elem['x']:.1f}, {elem['y']:.1f})")
            print(f"    Size: {elem['width']:.1f} x {elem['height']:.1f}")
        
        # Critical check: Are there large shapes with transparency?
        # These should be container backgrounds
        large_transparent = [e for e in semi_transparent if e['width'] > 200 and e['height'] > 50]
        if large_transparent:
            print(f"\n[Container Backgrounds] (large + transparent): {len(large_transparent)}")
            for elem in large_transparent:
                color = elem.get('fill_color', 'None')
                opacity = elem.get('fill_opacity', 1.0)
                print(f"  ✓ Container: {color} @ opacity {opacity:.4f}")
                print(f"    Size: {elem['width']:.1f} x {elem['height']:.1f}")
    
    parser.close()
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)
    print("\n✓ Check above results:")
    print("  1. Pure opaque shapes (opacity=1.0) should be borders/decorations")
    print("  2. Semi-transparent shapes (opacity<1.0) should be container backgrounds")
    print("  3. Large semi-transparent shapes should show correct opacity (0.0314 or 0.0784)")

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "tests/glm-4.6.pdf"
    verify_color_separation(pdf_path)
