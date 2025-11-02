#!/usr/bin/env python3
"""
详细分析第4页的所有绘图元素
"""
import fitz


def main():
    pdf_path = "tests/season_report_del.pdf"
    doc = fitz.open(pdf_path)
    page = doc[3]  # 第4页，索引3
    
    print("="*80)
    print("第4页 - 详细绘图元素分析")
    print("="*80)
    
    # 获取绘图元素
    drawings = page.get_drawings()
    
    print(f"\n总共 {len(drawings)} 个绘图元素\n")
    
    for i, drawing in enumerate(drawings):
        items = drawing.get("items", [])
        rect = drawing.get("rect")
        color = drawing.get("color")
        fill = drawing.get("fill")
        width = drawing.get("width", 1)
        
        print(f"绘图元素 {i}:")
        print(f"  rect: {rect}")
        print(f"  stroke颜色: {color}")
        print(f"  fill颜色: {fill}")
        print(f"  线宽: {width}")
        print(f"  items数量: {len(items)}")
        
        # 统计不同类型的items
        line_count = sum(1 for item in items if item[0] == 'l')
        curve_count = sum(1 for item in items if item[0] == 'c')
        rect_count = sum(1 for item in items if item[0] == 're')
        
        print(f"  线条: {line_count}, 曲线: {curve_count}, 矩形: {rect_count}")
        
        # 如果是三角形区域（中间位置，合理大小）
        if rect.x0 > 200 and rect.x0 < 500 and rect.y0 > 50 and rect.y0 < 300:
            if rect.width > 50 and rect.height > 50:
                print(f"  ⚠️ 可能是关键图形区域")
                
                # 详细打印items
                print(f"  Items详情:")
                for j, item in enumerate(items):
                    if item[0] == 'l':
                        p1 = item[1]
                        p2 = item[2]
                        is_horizontal = abs(p1.y - p2.y) < 1
                        is_vertical = abs(p1.x - p2.x) < 1
                        
                        edge_type = "水平线" if is_horizontal else ("垂直线" if is_vertical else "斜线")
                        length = ((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5
                        print(f"    线条 {j+1} ({edge_type}, 长度={length:.2f}): ({p1.x:.2f}, {p1.y:.2f}) -> ({p2.x:.2f}, {p2.y:.2f})")
                    elif item[0] == 're':
                        print(f"    矩形 {j+1}: {item}")
                    elif item[0] == 'c':
                        print(f"    曲线 {j+1}: {item}")
        
        print()
    
    doc.close()


if __name__ == "__main__":
    main()
