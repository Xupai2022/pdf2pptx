import sys
sys.path.insert(0, '/home/user/webapp')

import yaml
from src.parser.pdf_parser import PDFParser

# Load config
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Parse PDF
parser = PDFParser(config)
doc = parser.parse("tests/season_report_del.pdf")
page_data = doc['pages'][3]

# Get shapes
shapes = [e for e in page_data['elements'] if e['type'] == 'shape']

print(f"=== 原始提取的形状: {len(shapes)}个 ===\n")

# Check Drawing 5 and 9 (large diagonal lines)
for i, shape in enumerate(shapes):
    width = shape['width']
    height = shape['height']
    if width > 130 and height > 130:
        print(f"Shape {i}: ({shape['x']:.1f}, {shape['y']:.1f}), {width:.1f}x{height:.1f}")
        print(f"  Type: {shape.get('shape_type')}")
        print(f"  Fill: {shape.get('fill_color')}")
        print(f"  Stroke: {shape.get('stroke_color')}")
        print(f"  Stroke width: {shape.get('stroke_width')}")
        print()

print(f"\n总共 {len(shapes)} 个shapes被提取")
