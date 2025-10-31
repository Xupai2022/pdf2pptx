import yaml
from src.parser.pdf_parser import PDFParser

with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

parser = PDFParser(config['parser'])
parser.open("tests/season_report_del.pdf")
result = parser.extract_page_elements(3)
shapes = [e for e in result['elements'] if e['type'] == 'shape']

print("=== 斜线形状分析 ===\n")

# Shape 1 and 3 are the diagonal lines
for idx in [1, 3]:
    shape = shapes[idx]
    print(f"Shape {idx} (斜线):")
    print(f"  位置: ({shape['x']:.1f}, {shape['y']:.1f}) -> ({shape['x2']:.1f}, {shape['y2']:.1f})")
    print(f"  尺寸: {shape['width']:.1f} x {shape['height']:.1f}")
    print(f"  shape_type: '{shape.get('shape_type')}'")
    print(f"  填充: {shape.get('fill_color')}")
    print(f"  描边: {shape.get('stroke_color')} ({shape.get('stroke_width')}pt)")
    print()
    
    # This will be rendered as...
    print(f"  渲染方式:")
    print(f"    - shape_type='s' -> 映射为 MSO_SHAPE.RECTANGLE")
    print(f"    - 位置: ({shape['x']:.1f}, {shape['y']:.1f})")
    print(f"    - 尺寸: {shape['width']:.1f} x {shape['height']:.1f}")
    print(f"    - 描边: {shape.get('stroke_color')}")
    print(f"    ⚠️  问题: 斜线被渲染成灰色边框的大矩形！")
    print()

parser.close()
