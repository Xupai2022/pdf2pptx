"""
直接检查PDF原始结构
"""
import fitz
import pdfplumber

def check_with_pymupdf(pdf_path, page_num):
    """使用 PyMuPDF 检查"""
    print(f"\n{'='*80}")
    print(f"PyMuPDF 分析: {pdf_path}, 第{page_num}页")
    print('='*80)
    
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    
    print(f"页面尺寸: {page.rect.width:.1f} x {page.rect.height:.1f}pt")
    
    # 获取绘图命令
    drawings = page.get_drawings()
    print(f"\n绘图命令数量: {len(drawings)}")
    
    if drawings:
        print(f"\n前30个绘图命令:")
        for i, draw in enumerate(drawings[:30]):
            print(f"  [{i}] type={draw.get('type', 'N/A')}, rect={draw.get('rect', 'N/A')}, "
                  f"fill={draw.get('fill', 'N/A')}, color={draw.get('color', 'N/A')}, "
                  f"width={draw.get('width', 0)}")
    
    # 获取文本
    text_dict = page.get_text("dict")
    blocks = text_dict.get('blocks', [])
    text_blocks = [b for b in blocks if b['type'] == 0]
    
    print(f"\n文本块数量: {len(text_blocks)}")
    if text_blocks:
        print(f"前5个文本块:")
        for i, block in enumerate(text_blocks[:5]):
            bbox = block['bbox']
            lines = block.get('lines', [])
            text = ""
            for line in lines:
                for span in line.get('spans', []):
                    text += span.get('text', '')
            print(f"  [{i}] bbox={bbox}, text={text[:50]}")
    
    doc.close()

def check_with_pdfplumber(pdf_path, page_num):
    """使用 pdfplumber 检查"""
    print(f"\n{'='*80}")
    print(f"pdfplumber 分析: {pdf_path}, 第{page_num}页")
    print('='*80)
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        
        print(f"页面尺寸: {page.width:.1f} x {page.height:.1f}pt")
        
        # 获取矩形
        rects = page.rects
        print(f"\n矩形数量: {len(rects)}")
        if rects:
            print(f"前20个矩形:")
            for i, rect in enumerate(rects[:20]):
                print(f"  [{i}] x0={rect['x0']:.1f}, top={rect['top']:.1f}, "
                      f"x1={rect['x1']:.1f}, bottom={rect['bottom']:.1f}, "
                      f"width={rect['width']:.1f}, height={rect['height']:.1f}, "
                      f"stroking_color={rect.get('stroking_color')}, "
                      f"non_stroking_color={rect.get('non_stroking_color')}")
        
        # 获取线条
        lines = page.lines
        print(f"\n线条数量: {len(lines)}")
        
        # 获取文本
        chars = page.chars
        print(f"\n字符数量: {len(chars)}")
        if chars:
            print(f"前5个字符:")
            for i, char in enumerate(chars[:5]):
                print(f"  [{i}] text={char['text']}, x0={char['x0']:.1f}, top={char['top']:.1f}, "
                      f"size={char.get('size', 'N/A')}")
        
        # 检查表格
        tables = page.find_tables()
        print(f"\n表格数量: {len(tables)}")
        for i, table in enumerate(tables):
            print(f"  表格{i+1}: {table.bbox}, {len(table.rows)}行 x {len(table.rows[0]) if table.rows else 0}列")

def main():
    pdf_path = "tests/season_report_del.pdf"
    
    # 检查第16页
    print("\n" + "="*80)
    print("检查第16页 (问题页面)")
    print("="*80)
    check_with_pymupdf(pdf_path, 16)
    check_with_pdfplumber(pdf_path, 16)
    
    # 对比正常的第7页
    print("\n" + "="*80)
    print("检查第7页 (正常页面，用于对比)")
    print("="*80)
    check_with_pymupdf(pdf_path, 7)
    check_with_pdfplumber(pdf_path, 7)

if __name__ == "__main__":
    main()
