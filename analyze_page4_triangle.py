#!/usr/bin/env python3
"""
分析第4页的三角形底边横线问题
"""
import fitz


def main():
    pdf_path = "tests/season_report_del.pdf"
    doc = fitz.open(pdf_path)
    page = doc[3]  # 第4页，索引3
    
    print("="*80)
    print("第4页 - 三角形分析")
    print("="*80)
    
    # 获取绘图元素
    drawings = page.get_drawings()
    
    print(f"\n绘图元素数量: {len(drawings)}")
    
    # 查找三角形和横线
    triangles = []
    horizontal_lines = []
    
    for i, drawing in enumerate(drawings):
        items = drawing.get("items", [])
        rect = drawing.get("rect")
        color = drawing.get("color")
        fill = drawing.get("fill")
        width = drawing.get("width", 1)
        
        # 统计线条
        line_count = sum(1 for item in items if item[0] == 'l')
        
        # 三角形检测（3条线）
        if line_count == 3:
            triangles.append({
                'index': i,
                'rect': rect,
                'items': items,
                'color': color,
                'fill': fill,
                'width': width
            })
        
        # 横线检测
        for item in items:
            if item[0] == 'l':  # 线条
                p1 = item[1]
                p2 = item[2]
                
                # 检测是否为水平线（y坐标相同）
                if abs(p1.y - p2.y) < 1:  # 容差1个像素
                    horizontal_lines.append({
                        'index': i,
                        'p1': (p1.x, p1.y),
                        'p2': (p2.x, p2.y),
                        'color': color,
                        'width': width,
                        'stroke': drawing.get("color") is not None,
                        'fill': drawing.get("fill") is not None
                    })
    
    print(f"\n找到 {len(triangles)} 个三角形:")
    for tri in triangles:
        print(f"\n  三角形 {tri['index']}:")
        print(f"    rect: {tri['rect']}")
        print(f"    stroke颜色: {tri['color']}")
        print(f"    fill颜色: {tri['fill']}")
        print(f"    线宽: {tri['width']}")
        print(f"    items数量: {len(tri['items'])}")
        
        # 分析三角形的边
        for j, item in enumerate(tri['items']):
            if item[0] == 'l':
                p1 = item[1]
                p2 = item[2]
                is_horizontal = abs(p1.y - p2.y) < 1
                is_vertical = abs(p1.x - p2.x) < 1
                
                edge_type = "水平" if is_horizontal else ("垂直" if is_vertical else "斜线")
                print(f"      边 {j+1} ({edge_type}): ({p1.x:.2f}, {p1.y:.2f}) -> ({p2.x:.2f}, {p2.y:.2f})")
    
    print(f"\n找到 {len(horizontal_lines)} 条横线（前10条）:")
    for line in horizontal_lines[:10]:
        stroke_status = "有stroke" if line['stroke'] else "无stroke"
        fill_status = "有fill" if line['fill'] else "无fill"
        print(f"  索引 {line['index']}: {line['p1']} -> {line['p2']}, "
              f"颜色={line['color']}, 线宽={line['width']}, {stroke_status}, {fill_status}")
    
    # 分析三角形区域内的横线
    if triangles:
        print(f"\n分析三角形区域:")
        for tri in triangles:
            tri_rect = tri['rect']
            print(f"\n  三角形 {tri['index']} 范围: {tri_rect}")
            
            # 找出在三角形范围内的横线
            lines_in_triangle = []
            for line in horizontal_lines:
                p1 = line['p1']
                p2 = line['p2']
                
                # 检查横线是否在三角形的bbox内
                if (tri_rect.x0 <= p1[0] <= tri_rect.x1 and
                    tri_rect.y0 <= p1[1] <= tri_rect.y1):
                    lines_in_triangle.append(line)
            
            print(f"    区域内的横线数量: {len(lines_in_triangle)}")
            for line in lines_in_triangle:
                print(f"      {line['p1']} -> {line['p2']}, 颜色={line['color']}, 线宽={line['width']}")
    
    doc.close()


if __name__ == "__main__":
    main()
