#!/usr/bin/env python3
"""
Debug script to track where the triangle side lines are being filtered out.
"""

import fitz
import logging
from src.parser.pdf_parser import PDFParser
from pathlib import Path
import yaml

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def load_config():
    """Load configuration"""
    config_path = Path("config/config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def analyze_page_4():
    """Analyze page 4 in detail"""
    print("="*80)
    print("Analyzing Page 4 - Triangle Lines")
    print("="*80)
    
    config = load_config()
    config['parser']['dpi'] = 600
    
    parser = PDFParser(config['parser'])
    parser.open("tests/season_report_del.pdf")
    
    # Get raw page data
    page = parser.doc[3]  # Page 4 (0-indexed)
    drawings = page.get_drawings()
    
    print(f"\nTotal raw drawings: {len(drawings)}")
    
    # Find the diagonal lines
    diagonal_lines = []
    for i, drawing in enumerate(drawings):
        items = drawing.get("items", [])
        for item in items:
            if item[0] == "l" and len(item) >= 3:
                p1 = item[1]
                p2 = item[2]
                x1, y1 = p1.x, p1.y
                x2, y2 = p2.x, p2.y
                
                # Check if diagonal
                is_diagonal = abs(x2 - x1) > 5 and abs(y2 - y1) > 5
                if is_diagonal:
                    rect = drawing.get("rect")
                    diagonal_lines.append({
                        'index': i,
                        'coords': (x1, y1, x2, y2),
                        'rect': (rect.x0, rect.y0, rect.x1, rect.y1),
                        'fill': drawing.get("fill"),
                        'stroke': drawing.get("color"),
                        'width': drawing.get("width"),
                        'drawing': drawing
                    })
    
    print(f"\nFound {len(diagonal_lines)} diagonal lines:")
    for line in diagonal_lines:
        print(f"\n  Line {line['index']}:")
        print(f"    Coords: {line['coords']}")
        print(f"    Rect: {line['rect']}")
        print(f"    Fill: {line['fill']}")
        print(f"    Stroke: {line['stroke']}")
        print(f"    Width: {line['width']}")
    
    # Now extract using the parser pipeline
    print("\n" + "="*80)
    print("Extracting through parser pipeline...")
    print("="*80)
    
    page_data = parser.extract_page_elements(3)
    
    # Count different element types
    shapes = [e for e in page_data['elements'] if e['type'] == 'shape']
    lines = [s for s in shapes if s['shape_type'] == 'line']
    diagonal_shapes = []
    
    for shape in shapes:
        if shape['shape_type'] == 'line':
            # Check if diagonal
            width = abs(shape['x2'] - shape['x'])
            height = abs(shape['y2'] - shape['y'])
            if width > 5 and height > 5:
                diagonal_shapes.append(shape)
    
    print(f"\nExtracted elements:")
    print(f"  Total elements: {len(page_data['elements'])}")
    print(f"  Shapes: {len(shapes)}")
    print(f"  Lines: {len(lines)}")
    print(f"  Diagonal lines: {len(diagonal_shapes)}")
    
    if diagonal_shapes:
        print(f"\nDiagonal lines extracted:")
        for i, line in enumerate(diagonal_shapes):
            print(f"\n  Diagonal {i+1}:")
            print(f"    Position: ({line['x']:.2f}, {line['y']:.2f}) → ({line['x2']:.2f}, {line['y2']:.2f})")
            print(f"    Size: {line['width']:.2f} x {line['height']:.2f}")
            print(f"    Fill: {line['fill_color']}")
            print(f"    Stroke: {line['stroke_color']}, Width: {line['stroke_width']}")
    else:
        print("\n⚠️  NO DIAGONAL LINES WERE EXTRACTED!")
        print("    This confirms the lines are being filtered somewhere in the pipeline.")
    
    # Check if they're in images or charts
    images = [e for e in page_data['elements'] if e['type'] == 'image']
    print(f"\n  Images: {len(images)}")
    if images:
        for i, img in enumerate(images):
            print(f"    Image {i+1}: bbox=({img['x']:.1f}, {img['y']:.1f}, {img['x2']:.1f}, {img['y2']:.1f})")
            if img.get('is_chart'):
                print(f"      → This is a CHART image!")
    
    parser.close()
    
    # Compare diagonal line positions with image/chart positions
    if not diagonal_shapes and images:
        print("\n" + "="*80)
        print("OVERLAP ANALYSIS")
        print("="*80)
        for line in diagonal_lines:
            line_rect = line['rect']
            print(f"\nDiagonal line rect: {line_rect}")
            for i, img in enumerate(images):
                img_rect = (img['x'], img['y'], img['x2'], img['y2'])
                
                # Check overlap
                overlap_x = not (line_rect[2] < img_rect[0] or line_rect[0] > img_rect[2])
                overlap_y = not (line_rect[3] < img_rect[1] or line_rect[1] > img_rect[3])
                
                if overlap_x and overlap_y:
                    print(f"  ✗ OVERLAPS with Image {i+1}: {img_rect}")
                    if img.get('is_chart'):
                        print(f"    → Image is a CHART - lines may be part of chart!")

if __name__ == "__main__":
    analyze_page_4()
