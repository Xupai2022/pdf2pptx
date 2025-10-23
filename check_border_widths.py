#!/usr/bin/env python3
"""检查PDF中边框的实际宽度"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main import load_config
from src.parser.pdf_parser import PDFParser

config = load_config()
parser_config = config.get('parser', {})

parser = PDFParser(parser_config)
parser.open("tests/test_sample.pdf")
page_data = parser.extract_page_elements(0)
parser.close()

print("=" * 60)
print("BORDER WIDTH ANALYSIS")
print("=" * 60)

# Find thin vertical shapes (likely borders)
shapes = [e for e in page_data['elements'] if e['type'] == 'shape']

print(f"\nTotal shapes: {len(shapes)}")

# Find vertical thin shapes (borders)
vertical_thin = []
for shape in shapes:
    width = shape['width']
    height = shape['height']
    
    # Vertical borders: height > width and width < 10
    if height > width and width < 10:
        vertical_thin.append({
            'width_pdf': width,
            'height_pdf': height,
            'width_scaled': width * 1.333,  # Apply PDF scale
            'x': shape['x'],
            'y': shape['y'],
            'fill': shape.get('fill_color', 'none'),
            'stroke': shape.get('stroke_color', 'none'),
            'stroke_width': shape.get('stroke_width', 0)
        })

print(f"\nVertical thin shapes (likely borders): {len(vertical_thin)}")

vertical_thin.sort(key=lambda x: x['width_pdf'])

print("\nThinnest 10 vertical shapes:")
for i, shape in enumerate(vertical_thin[:10]):
    print(f"\n  {i+1}. Width: {shape['width_pdf']:.2f}pt (PDF) → {shape['width_scaled']:.2f}pt (scaled by 1.333)")
    print(f"     Height: {shape['height_pdf']:.1f}pt")
    print(f"     Fill: {shape['fill']}")
    print(f"     Stroke: {shape['stroke']} (width: {shape['stroke_width']})")
    print(f"     HTML expected: 4px = 4pt (after scaling)")
    print(f"     Difference: {abs(shape['width_scaled'] - 4):.2f}pt")
    
    if abs(shape['width_scaled'] - 4) < 1:
        print(f"     ✓ Matches expected border width!")

# Check for horizontal thin shapes (top bar)
horizontal_thin = []
for shape in shapes:
    width = shape['width']
    height = shape['height']
    
    # Horizontal bars: width > height and height < 20
    if width > height and height < 20:
        horizontal_thin.append({
            'width_pdf': width,
            'height_pdf': height,
            'height_scaled': height * 1.333,  # Apply PDF scale
            'x': shape['x'],
            'y': shape['y'],
            'fill': shape.get('fill_color', 'none')
        })

print(f"\n\nHorizontal thin shapes (likely top bar): {len(horizontal_thin)}")

horizontal_thin.sort(key=lambda x: x['height_pdf'])

for i, shape in enumerate(horizontal_thin[:3]):
    print(f"\n  {i+1}. Height: {shape['height_pdf']:.2f}pt (PDF) → {shape['height_scaled']:.2f}pt (scaled by 1.333)")
    print(f"     Width: {shape['width_pdf']:.1f}pt")
    print(f"     Fill: {shape['fill']}")
    print(f"     HTML expected: 10px = 10pt (after scaling)")
    print(f"     Difference: {abs(shape['height_scaled'] - 10):.2f}pt")
    
    if abs(shape['height_scaled'] - 10) < 1:
        print(f"     ✓ Matches expected top-bar height!")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("PDF is at 75% scale (1440×811 pt)")
print("HTML is at 100% scale (1920×1080 px)")
print("Scale factor: 1.333 (4/3)")
print("\nExpected after scaling:")
print("  Border width: 3pt (PDF) × 1.333 = 4pt (HTML)")
print("  Top bar height: 7.5pt (PDF) × 1.333 = 10pt (HTML)")
