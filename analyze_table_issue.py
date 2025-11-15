"""
分析表格识别问题：
1. 安全运营月报.pdf 第 8、9、12页 - 工作正常
2. season_report_del.pdf 第 16页 - 只识别表头2行，丢失下方5行
"""

import sys
sys.path.append('src')

import fitz
from src.parser.pdf_parser import PDFParser
from src.parser.table_detector import TableDetector

def analyze_page_cells(pdf_path, page_num):
    """分析PDF页面的单元格结构"""
    print(f"\n{'='*80}")
    print(f"分析文件: {pdf_path}, 第{page_num}页")
    print('='*80)
    
    # 解析页面
    parser = PDFParser({'dpi': 300, 'extract_images': True})
    parser.open(pdf_path)
    page_data = parser.extract_page_elements(page_num - 1)
    doc = parser.doc
    page = doc[page_num - 1]
    
    shapes = page_data.get('shapes', [])
    text_elements = page_data.get('texts', [])
    
    print(f"\n总共有 {len(shapes)} 个形状元素")
    print(f"总共有 {len(text_elements)} 个文本元素")
    
    # 按类型分组
    rectangles = [s for s in shapes if s.get('type') == 'rect']
    print(f"\n矩形元素: {len(rectangles)}")
    
    # 分析矩形尺寸分布
    if rectangles:
        widths = [r.get('width', 0) for r in rectangles]
        heights = [r.get('height', 0) for r in rectangles]
        
        print(f"\n宽度范围: {min(widths):.1f}pt ~ {max(widths):.1f}pt")
        print(f"高度范围: {min(heights):.1f}pt ~ {max(heights):.1f}pt")
        
        # 显示所有矩形的详细信息
        print(f"\n所有矩形详情 (按Y坐标排序):")
        print(f"{'序号':<5} {'X':<8} {'Y':<8} {'宽度':<8} {'高度':<8} {'填充色':<12} {'边框色':<12} {'边框宽':<6}")
        print("-" * 80)
        
        sorted_rects = sorted(rectangles, key=lambda r: r['y'])
        for i, rect in enumerate(sorted_rects):
            x = rect['x']
            y = rect['y']
            w = rect.get('width', 0)
            h = rect.get('height', 0)
            fill = rect.get('fill_color', 'None')
            stroke = rect.get('stroke_color', 'None')
            stroke_w = rect.get('stroke_width', 0)
            
            print(f"{i:<5} {x:<8.1f} {y:<8.1f} {w:<8.1f} {h:<8.1f} {fill:<12} {stroke:<12} {stroke_w:<6.2f}")
    
    # 运行表格检测
    print(f"\n{'='*80}")
    print("运行表格检测...")
    print('='*80)
    
    detector = TableDetector({
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    })
    
    tables = detector.detect_tables(shapes, page, text_elements)
    
    print(f"\n检测到 {len(tables)} 个表格")
    
    for idx, table in enumerate(tables):
        print(f"\n表格 {idx + 1}:")
        print(f"  边界框: {table['bbox']}")
        print(f"  行数: {table['rows']}")
        print(f"  列数: {table['cols']}")
        print(f"  单元格数: {len(table.get('cells', []))}")
        
        if 'grid' in table:
            grid = table['grid']
            print(f"  网格结构: {len(grid)} 行 x {len(grid[0]) if grid else 0} 列")
            
            # 显示每行的文本内容
            print(f"\n  表格内容预览:")
            for row_idx, row in enumerate(grid[:10]):  # 只显示前10行
                texts = []
                for cell in row:
                    text = cell.get('text', '').strip()
                    if text:
                        texts.append(text[:20])  # 截断长文本
                print(f"    行{row_idx + 1}: {' | '.join(texts)}")
    
    parser.close()
    return tables

def analyze_filtering_details(pdf_path, page_num):
    """详细分析过滤过程"""
    print(f"\n{'='*80}")
    print(f"详细分析过滤过程: {pdf_path}, 第{page_num}页")
    print('='*80)
    
    # 解析页面
    parser = PDFParser({'dpi': 300, 'extract_images': True})
    parser.open(pdf_path)
    page_data = parser.extract_page_elements(page_num - 1)
    doc = parser.doc
    page = doc[page_num - 1]
    
    shapes = page_data.get('shapes', [])
    rectangles = [s for s in shapes if s.get('type') == 'rect']
    
    print(f"\n初始矩形数量: {len(rectangles)}")
    
    # 手动执行过滤逻辑
    detector = TableDetector({
        'table_alignment_tolerance': 3.0,
        'min_table_rows': 2,
        'min_table_cols': 2
    })
    
    # 模拟 _filter_table_cell_candidates
    candidates = []
    
    print("\n第1步: 基本尺寸过滤 (width >= 10pt, height >= 10pt)")
    for i, shape in enumerate(rectangles):
        width = shape.get('width', 0)
        height = shape.get('height', 0)
        
        if width < 10 or height < 10:
            print(f"  过滤掉 [{i}]: {width:.1f}x{height:.1f}pt (太小)")
            continue
        
        # 宽高比检查
        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 100
        
        # 严格过滤thin shapes
        if height < 20 and aspect_ratio > 6:
            print(f"  过滤掉 [{i}]: {width:.1f}x{height:.1f}pt (高度<20pt, 宽高比{aspect_ratio:.1f}:1 > 6:1)")
            continue
        
        # 宽松过滤wide bars
        if height >= 20 and aspect_ratio > 25:
            print(f"  过滤掉 [{i}]: {width:.1f}x{height:.1f}pt (宽高比{aspect_ratio:.1f}:1 > 25:1)")
            continue
        
        # 必须有stroke或fill
        has_stroke = shape.get('stroke_color') is not None
        has_fill = shape.get('fill_color') is not None
        
        if has_stroke or has_fill:
            candidates.append(shape)
            print(f"  保留 [{i}]: {width:.1f}x{height:.1f}pt, 宽高比={aspect_ratio:.1f}:1, fill={shape.get('fill_color')}, stroke={shape.get('stroke_color')}")
    
    print(f"\n第1步后剩余: {len(candidates)} 个候选")
    
    if not candidates:
        print("没有候选，退出")
        doc.close()
        return
    
    # 面积过滤
    print("\n第2步: 面积过滤 (移除背景)")
    areas = [c['width'] * c['height'] for c in candidates]
    sorted_areas = sorted(areas)
    idx_75 = int(len(sorted_areas) * 0.75)
    area_75th = sorted_areas[idx_75] if sorted_areas else 1000
    background_area_threshold = area_75th * 10
    
    print(f"  75分位面积: {area_75th:.0f} sq.pt")
    print(f"  背景阈值: {background_area_threshold:.0f} sq.pt")
    
    filtered_candidates = []
    for i, shape in enumerate(candidates):
        area = shape['width'] * shape['height']
        if area > background_area_threshold:
            print(f"  过滤掉 [{i}]: 面积={area:.0f} sq.pt > 阈值={background_area_threshold:.0f} sq.pt")
            continue
        filtered_candidates.append(shape)
    
    print(f"\n第2步后剩余: {len(filtered_candidates)} 个候选")
    
    # 按Y坐标分组
    print("\n第3步: 按Y坐标分组成行")
    tolerance = 3.0
    rows = {}
    for cell in filtered_candidates:
        y = round(cell['y'] / tolerance) * tolerance
        if y not in rows:
            rows[y] = []
        rows[y].append(cell)
    
    print(f"  检测到 {len(rows)} 行")
    for y_key in sorted(rows.keys()):
        row_cells = rows[y_key]
        x_positions = [c['x'] for c in row_cells]
        print(f"  Y={y_key:.1f}pt: {len(row_cells)} 个单元格, X坐标=[{', '.join([f'{x:.1f}' for x in sorted(x_positions)])}]")
    
    doc.close()

def main():
    # 分析安全运营月报.pdf 第8页（工作正常）
    print("\n" + "="*80)
    print("测试组1: 安全运营月报.pdf (工作正常的表格)")
    print("="*80)
    
    analyze_page_cells("tests/安全运营月报.pdf", 8)
    analyze_page_cells("tests/安全运营月报.pdf", 9)
    analyze_page_cells("tests/安全运营月报.pdf", 12)
    
    # 分析 season_report_del.pdf 第16页（问题页面）
    print("\n" + "="*80)
    print("测试组2: season_report_del.pdf")
    print("="*80)
    
    print("\n第16页 (问题页面 - 只识别2行表头):")
    analyze_page_cells("tests/season_report_del.pdf", 16)
    
    # 详细分析过滤过程
    print("\n" + "="*80)
    print("详细过滤分析")
    print("="*80)
    analyze_filtering_details("tests/season_report_del.pdf", 16)
    
    # 验证其他页面不受影响
    print("\n" + "="*80)
    print("验证其他页面 (确保不会误识别)")
    print("="*80)
    
    print("\n第2页 (不应该有表格):")
    tables_p2 = analyze_page_cells("tests/season_report_del.pdf", 2)
    
    print("\n第6页 (不应该有表格):")
    tables_p6 = analyze_page_cells("tests/season_report_del.pdf", 6)
    
    print("\n第7页 (已有表格应保持):")
    tables_p7 = analyze_page_cells("tests/season_report_del.pdf", 7)
    
    print("\n第10页 (已有表格应保持):")
    tables_p10 = analyze_page_cells("tests/season_report_del.pdf", 10)
    
    print("\n第13页 (已有表格应保持):")
    tables_p13 = analyze_page_cells("tests/season_report_del.pdf", 13)

if __name__ == "__main__":
    main()
