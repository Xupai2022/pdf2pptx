import yaml
from src.parser.pdf_parser import PDFParser
from src.analyzer.layout_analyzer_v2 import LayoutAnalyzerV2

with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

parser = PDFParser(config['parser'])
parser.open("tests/season_report_del.pdf")

# Get raw page elements
result = parser.extract_page_elements(3)
raw_elements = result['elements']

print("=== Step 1: PDFParser提取的原始元素 ===")
print(f"总计: {len(raw_elements)}个元素\n")

shapes = [e for e in raw_elements if e['type'] == 'shape']
texts = [e for e in raw_elements if e['type'] == 'text']
images = [e for e in raw_elements if e['type'] == 'image']

print(f"文本: {len(texts)}")
print(f"图片: {len(images)}")
print(f"形状: {len(shapes)}\n")

print("=== 形状详细列表 ===")
for i, shape in enumerate(shapes):
    print(f"\nShape {i}:")
    print(f"  位置: ({shape['x']:.1f}, {shape['y']:.1f})")
    print(f"  尺寸: {shape['width']:.1f} x {shape['height']:.1f}")
    print(f"  类型: {shape.get('shape_type')}")
    print(f"  填充: {shape.get('fill_color')}")
    print(f"  描边: {shape.get('stroke_color')} ({shape.get('stroke_width')}pt)")
    if shape.get('is_ring'):
        print(f"  ⚠️  IS_RING: {shape.get('ring_type')}")

# Now analyze layout
analyzer = LayoutAnalyzerV2(config['analyzer'])
pages_data = [result]
analyzed_pages = analyzer.analyze_pages(pages_data)

print(f"\n\n=== Step 2: LayoutAnalyzer分析后的元素 ===")
page3_analyzed = analyzed_pages[0]
print(f"总计: {len(page3_analyzed['regions'])}个区域\n")

# Check if any elements were filtered or modified
print("检查元素是否被修改或过滤...")
if len(page3_analyzed['regions']) != len(raw_elements):
    print(f"⚠️  元素数量变化: {len(raw_elements)} -> {len(page3_analyzed['regions'])}")
else:
    print(f"✓ 元素数量保持不变: {len(raw_elements)}")

parser.close()
