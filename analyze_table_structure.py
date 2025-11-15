"""
分析 PDF 表格的真实结构，包括行数、列数、合并单元格、背景颜色和列宽
"""

import fitz
import sys
import json
from collections import defaultdict

def analyze_page_table_structure(pdf_path, page_num):
    """
    深度分析 PDF 页面中表格的真实结构
    
    Args:
        pdf_path: PDF 文件路径
        page_num: 页码 (0-based)
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    print(f"\n{'='*80}")
    print(f"分析 PDF 第 {page_num + 1} 页的表格结构")
    print(f"{'='*80}\n")
    
    # 提取所有矩形
    drawings = page.get_drawings()
    rectangles = []
    
    for item in drawings:
        if item['type'] == 'f' or item['type'] == 's':  # fill or stroke
            rect = item['rect']
            
            # 获取填充颜色和边框颜色
            fill_color = None
            stroke_color = None
            stroke_width = 0
            
            if item.get('fill'):
                fill = item['fill']
                fill_color = f"#{int(fill[0]*255):02x}{int(fill[1]*255):02x}{int(fill[2]*255):02x}".upper()
            
            if item.get('color'):
                color = item['color']
                stroke_color = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}".upper()
                stroke_width = item.get('width', 0)
            
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 过滤太小的形状
            if width >= 5 and height >= 5:
                rectangles.append({
                    'x': rect[0],
                    'y': rect[1],
                    'x2': rect[2],
                    'y2': rect[3],
                    'width': width,
                    'height': height,
                    'fill_color': fill_color,
                    'stroke_color': stroke_color,
                    'stroke_width': stroke_width
                })
    
    print(f"总共找到 {len(rectangles)} 个矩形\n")
    
    # 按 Y 坐标分组（识别行）
    tolerance = 3.0
    rows = defaultdict(list)
    
    for rect in rectangles:
        y_key = round(rect['y'] / tolerance) * tolerance
        rows[y_key].append(rect)
    
    sorted_rows = sorted(rows.keys())
    print(f"识别到 {len(sorted_rows)} 个行（Y 坐标分组）\n")
    
    # 分析每一行
    print("详细行信息：")
    print("-" * 100)
    
    all_x_positions = set()
    
    for i, y_key in enumerate(sorted_rows):
        row_cells = sorted(rows[y_key], key=lambda c: c['x'])
        
        print(f"\n第 {i+1} 行 (Y={y_key:.1f}pt):")
        print(f"  包含 {len(row_cells)} 个单元格")
        
        for j, cell in enumerate(row_cells):
            all_x_positions.add(cell['x'])
            
            print(f"    单元格 {j+1}:")
            print(f"      位置: X={cell['x']:.1f}, Y={cell['y']:.1f}")
            print(f"      尺寸: {cell['width']:.1f}pt × {cell['height']:.1f}pt")
            print(f"      填充色: {cell['fill_color']}")
            print(f"      边框色: {cell['stroke_color']} (宽度: {cell['stroke_width']:.2f}pt)")
    
    # 分析列结构
    print(f"\n{'-'*100}")
    print("\n列结构分析：")
    print(f"识别到 {len(all_x_positions)} 个不同的 X 坐标位置\n")
    
    sorted_x = sorted(all_x_positions)
    
    # 合并相近的 X 坐标（容差 10pt）
    col_tolerance = 10
    unique_cols = []
    
    for x in sorted_x:
        if not unique_cols or x - unique_cols[-1] >= col_tolerance:
            unique_cols.append(x)
    
    print(f"合并后唯一列数: {len(unique_cols)}")
    
    for i, x in enumerate(unique_cols):
        print(f"  列 {i+1}: X={x:.1f}pt")
        
        # 计算列宽（到下一列的距离）
        if i < len(unique_cols) - 1:
            col_width = unique_cols[i+1] - x
            print(f"        列宽: {col_width:.1f}pt")
    
    # 检测合并单元格
    print(f"\n{'-'*100}")
    print("\n合并单元格检测：")
    
    # 检测垂直合并（跨多行）
    for i, y_key in enumerate(sorted_rows[:-1]):  # 不包括最后一行
        row_cells = rows[y_key]
        
        for cell in row_cells:
            # 检查这个单元格是否跨越多行
            cell_bottom = cell['y2']
            rows_spanned = 1
            
            for j in range(i+1, len(sorted_rows)):
                next_y = sorted_rows[j]
                if next_y < cell_bottom - tolerance:
                    rows_spanned += 1
                else:
                    break
            
            if rows_spanned > 1:
                print(f"  检测到垂直合并: 第{i+1}行, X={cell['x']:.1f}, 跨 {rows_spanned} 行")
                print(f"    高度: {cell['height']:.1f}pt")
                print(f"    填充色: {cell['fill_color']}")
    
    # 检测水平合并（跨多列）
    for i, y_key in enumerate(sorted_rows):
        row_cells = sorted(rows[y_key], key=lambda c: c['x'])
        
        for cell in row_cells:
            # 计算这个单元格跨越了多少列
            cell_right = cell['x2']
            cols_spanned = 0
            
            for col_x in unique_cols:
                if cell['x'] <= col_x < cell_right - tolerance:
                    cols_spanned += 1
            
            if cols_spanned > 1:
                print(f"  检测到水平合并: 第{i+1}行, X={cell['x']:.1f}, 跨 {cols_spanned} 列")
                print(f"    宽度: {cell['width']:.1f}pt")
                print(f"    填充色: {cell['fill_color']}")
    
    # 提取文本内容
    print(f"\n{'-'*100}")
    print("\n文本内容（前20个）：")
    
    text_instances = page.get_text("dict")["blocks"]
    text_count = 0
    
    for block in text_instances:
        if block.get("type") == 0:  # 文本块
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text and text_count < 20:
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        print(f"  '{text}' @ X={bbox[0]:.1f}, Y={bbox[1]:.1f}")
                        text_count += 1
    
    print(f"\n{'='*80}\n")
    
    doc.close()

def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_table_structure.py <pdf文件> [页码1,页码2,...]")
        print("示例: python analyze_table_structure.py tests/安全运营周报.pdf 8,9,12")
        return
    
    pdf_path = sys.argv[1]
    
    # 默认分析第8、9、12页
    pages = [7, 8, 11]  # 0-based
    
    if len(sys.argv) >= 3:
        pages = [int(p) - 1 for p in sys.argv[2].split(',')]
    
    for page_num in pages:
        analyze_page_table_structure(pdf_path, page_num)

if __name__ == "__main__":
    main()
