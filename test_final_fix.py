import yaml
from src.parser.pdf_parser import PDFParser

with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

parser = PDFParser(config['parser'])
parser.open("tests/season_report_del.pdf")
result = parser.extract_page_elements(3)
shapes = [e for e in result['elements'] if e['type'] == 'shape']

print(f"=== 最终提取的形状: {len(shapes)}个 ===\n")

for i, shape in enumerate(shapes):
    print(f"Shape {i}: ({shape['x']:.1f}, {shape['y']:.1f}), {shape['width']:.1f}x{shape['height']:.1f}")
    print(f"  类型: {shape.get('shape_type')}, 填充: {shape.get('fill_color')}, 描边: {shape.get('stroke_color')}")
    if shape.get('is_ring'):
        print(f"  Ring: {shape.get('ring_type')}")

print(f"\n应该过滤掉的大型stroke shapes:")
print("  Shape 1: (509.0, 158.4), 137.5x144.0 - 灰色斜线 ✓ 应该被过滤")
print("  Shape 3: (284.8, 163.1), 144.0x137.5 - 灰色斜线 ✓ 应该被过滤")

parser.close()
