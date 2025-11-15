#!/usr/bin/env python3
import fitz
from pathlib import Path

pdf_path = Path("tests/行业化季报_主线测试自动化专用_APEX底座客户_2025-05-21至2025-08-18(pdfgear.com).pdf")
doc = fitz.open(str(pdf_path))
page = doc[4]

# 提取所有路径
paths = page.get_drawings()

# 按类型分类
h_lines = []
v_lines = []
rects = []

for path in paths:
    items = path.get('items', [])
    if not items:
        continue
    
    bbox = path.get('rect')
    if not bbox:
        continue
    
    width = bbox.width
    height = bbox.height
    
    # 判断类型
    if width > 5 and height < 3:
        h_lines.append(bbox)
    elif height > 5 and width < 3:
        v_lines.append(bbox)
    elif width > 10 and height > 10:
        rects.append(bbox)

print(f"水平线: {len(h_lines)} 条")
print(f"垂直线: {len(v_lines)} 条")  
print(f"矩形: {len(rects)} 个")

# 分析垂直线的X坐标分布
v_x_positions = sorted(set([round(line.x0) for line in v_lines]))
print(f"\n垂直线X坐标: {v_x_positions}")

# 计算列间距
if len(v_x_positions) >= 2:
    gaps = [v_x_positions[i+1] - v_x_positions[i] for i in range(len(v_x_positions)-1)]
    print(f"列间距: {gaps}")
    print(f"最大间距: {max(gaps)}pt")
    print(f"最小间距: {min(gaps)}pt")
    print(f"平均间距: {sum(gaps)/len(gaps):.1f}pt")

doc.close()
