#!/usr/bin/env python3
"""Test table detection on season_report_del.pdf page 9"""

import sys
import logging
from src.parser.pdf_parser import PDFParser

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Create config
config = {
    'dpi': 300,
    'table_alignment_tolerance': 3.0,
    'min_table_rows': 2,
    'min_table_cols': 2,
}

# Parse the PDF
parser = PDFParser(config)
parser.open("./tests/season_report_del.pdf")

# Parse page 9 (index 8)
page_num = 8
page_data = parser.extract_page_elements(page_num)

# Check for tables
print("\n" + "="*60)
print(f"RESULTS FOR PAGE {page_num + 1}")
print("="*60)

# Count elements by type
elements = page_data.get('elements', [])
print(f"\nTotal elements: {len(elements)}")

tables = [e for e in elements if e.get('type') == 'table']
shapes = [e for e in elements if e.get('type') == 'shape']
charts = [e for e in elements if e.get('type') == 'chart']
text = [e for e in elements if e.get('type') == 'text']
images = [e for e in elements if e.get('type') == 'image']

print(f"  Tables: {len(tables)}")
print(f"  Shapes: {len(shapes)}")
print(f"  Charts: {len(charts)}")
print(f"  Text: {len(text)}")
print(f"  Images: {len(images)}")

if tables:
    print(f"\n✅ Found {len(tables)} table(s)")
    for idx, table in enumerate(tables):
        print(f"\nTable {idx + 1}:")
        print(f"  Bbox: {table.get('bbox', '?')}")
        print(f"  Rows: {table.get('rows', '?')}, Cols: {table.get('cols', '?')}")
        if 'grid' in table:
            print(f"  Grid: {table.get('num_rows', '?')}x{table.get('num_cols', '?')}")
else:
    print("\n❌ No tables detected")

# Also check shapes
if 'shapes' in page_data:
    print(f"\n📊 Total shapes extracted: {len(page_data['shapes'])}")
    
    # Filter shapes on right side (X > 400)
    right_shapes = [s for s in page_data['shapes'] if s['x'] > 400]
    print(f"   Shapes on right side (X > 400): {len(right_shapes)}")
    
    # Show sample shapes
    if right_shapes:
        print("\n   Sample shapes on right side:")
        for shape in right_shapes[:5]:
            print(f"     {shape['width']:.1f}x{shape['height']:.1f} at ({shape['x']:.1f}, {shape['y']:.1f}), "
                  f"fill={shape.get('fill_color')}, stroke={shape.get('stroke_color')}")

parser.close()
