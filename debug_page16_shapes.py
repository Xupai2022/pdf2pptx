"""
调试第16页的shapes提取问题
"""
import sys
sys.path.append('src')

import fitz
import logging

# 设置详细日志
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

from src.parser.pdf_parser import PDFParser

def debug_page16():
    pdf_path = "tests/season_report_del.pdf"
    page_num = 15  # 0-indexed
    
    # 打开PDF
    parser = PDFParser({'dpi': 300, 'extract_images': True})
    parser.open(pdf_path)
    
    doc = parser.doc
    page = doc[page_num]
    
    print(f"\n{'='*80}")
    print(f"调试第16页 (index={page_num})")
    print('='*80)
    
    # 检查原始绘图命令
    drawings = page.get_drawings()
    print(f"\n原始绘图命令数量: {len(drawings)}")
    
    # 显示前30个绘图命令
    print(f"\n前30个绘图命令详情:")
    for i, draw in enumerate(drawings[:30]):
        draw_type = draw.get('type', 'N/A')
        rect = draw.get('rect')
        fill = draw.get('fill')
        color = draw.get('color')
        width = draw.get('width', 0)
        
        print(f"  [{i}] type={draw_type}, rect={rect}, fill={fill}, color={color}, width={width}")
    
    # 运行完整的extract逻辑
    print(f"\n{'='*80}")
    print("运行完整的 extract_page_elements...")
    print('='*80)
    
    page_data = parser.extract_page_elements(page_num)
    
    shapes = [e for e in page_data.get('elements', []) if e['type'] == 'shape']
    tables = [e for e in page_data.get('elements', []) if e['type'] == 'table']
    texts = [e for e in page_data.get('elements', []) if e['type'] == 'text']
    images = [e for e in page_data.get('elements', []) if e['type'] == 'image']
    
    print(f"\n提取结果:")
    print(f"  shapes: {len(shapes)}")
    print(f"  tables: {len(tables)}")
    print(f"  texts: {len(texts)}")
    print(f"  images: {len(images)}")
    
    if tables:
        for i, table in enumerate(tables):
            print(f"\n  表格{i+1}:")
            print(f"    bbox: {table.get('bbox', (table['x'], table['y'], table['x2'], table['y2']))}")
            print(f"    行数: {table.get('rows', 0)}")
            print(f"    列数: {table.get('cols', 0)}")
            grid = table.get('grid', [])
            if grid:
                print(f"    网格: {len(grid)} 行")
                for row_idx, row in enumerate(grid[:7]):  # 显示前7行
                    texts_in_row = []
                    for cell in row:
                        text = cell.get('text', '').strip()
                        if text:
                            texts_in_row.append(text[:15])
                    print(f"      行{row_idx+1}: {' | '.join(texts_in_row)}")
    
    # 直接调用 _extract_drawings 看看
    print(f"\n{'='*80}")
    print("直接调用 _extract_drawings...")
    print('='*80)
    
    drawing_elements, gradient_images = parser._extract_drawings(page, {}, page_num, [])
    
    print(f"\ndrawing_elements 数量: {len(drawing_elements)}")
    if drawing_elements:
        print(f"\n前20个 drawing_elements:")
        for i, elem in enumerate(drawing_elements[:20]):
            print(f"  [{i}] type={elem.get('shape_type', 'N/A')}, "
                  f"x={elem['x']:.1f}, y={elem['y']:.1f}, "
                  f"w={elem['width']:.1f}, h={elem['height']:.1f}, "
                  f"fill={elem.get('fill_color')}, stroke={elem.get('stroke_color')}")
    
    parser.close()

if __name__ == "__main__":
    debug_page16()
