"""
测试第9页表格转换
"""

import sys
sys.path.insert(0, '/home/user/webapp')

from src.parser.pdf_parser import PDFParser
from src.parser.table_detector import TableDetector
import logging

logging.basicConfig(level=logging.DEBUG)

def test_page_9():
    pdf_path = "tests/安全运营月报.pdf"
    page_num = 8  # 0-based, so page 9 is index 8
    
    parser = PDFParser({})
    tables_detector = TableDetector({})
    
    # Parse page
    parser.open(pdf_path)
    page_data = parser.extract_page_elements(page_num)
    parser.close()
    
    if not page_data:
        print("Failed to parse PDF")
        return
    
    shapes = page_data.get('shapes', [])
    text_elements = page_data.get('text_elements', [])
    
    print(f"\n{'='*80}")
    print(f"第9页解析结果：")
    print(f"  形状数量: {len(shapes)}")
    print(f"  文本元素: {len(text_elements)}")
    print(f"{'='*80}\n")
    
    # Detect tables
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    tables = tables_detector.detect_tables(shapes, page, text_elements)
    
    print(f"\n检测到 {len(tables)} 个表格\n")
    
    for i, table in enumerate(tables):
        print(f"表格 {i+1}:")
        print(f"  位置: {table['bbox']}")
        print(f"  行数: {table['rows']}")
        print(f"  列数: {table['cols']}")
        print(f"  单元格数: {len(table['cells'])}")
        
        if 'grid' in table:
            print(f"  网格: {table['num_rows']}行 x {table['num_cols']}列")
            print(f"  列宽: {[f'{w:.1f}pt' for w in table.get('col_widths', [])]}")
            
            # Print first few rows
            print(f"\n  前几行数据：")
            for row_idx, row in enumerate(table['grid'][:5]):
                print(f"    第{row_idx+1}行: ", end='')
                for col_idx, cell in enumerate(row[:3]):  # First 3 columns
                    text = cell.get('text', '').strip()[:20]
                    print(f"[{text}]", end=' ')
                print()
    
    doc.close()

if __name__ == "__main__":
    test_page_9()
