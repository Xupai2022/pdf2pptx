"""
分析 glm-4.6.pdf 中圆环显示问题的脚本
"""
import fitz
import json
import sys

def analyze_page_shapes(pdf_path, page_num):
    """分析指定页面的形状元素"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    print(f"\n{'='*80}")
    print(f"分析第 {page_num + 1} 页")
    print(f"{'='*80}")
    
    # 获取绘图元素
    drawings = page.get_drawings()
    print(f"\n总共 {len(drawings)} 个绘图元素\n")
    
    # 统计不同形状类型
    shape_types = {}
    circular_shapes = []  # 近似圆形的形状
    
    for idx, drawing in enumerate(drawings):
        shape_type = drawing.get("type", "unknown")
        shape_types[shape_type] = shape_types.get(shape_type, 0) + 1
        
        rect = drawing.get("rect")
        if not rect:
            continue
            
        width = rect.width
        height = rect.height
        
        # 检查是否接近正方形/圆形（宽高比接近1）
        if height > 0:
            aspect_ratio = width / height
            if 0.8 <= aspect_ratio <= 1.2:  # 接近正方形
                fill_color = drawing.get("fill")
                stroke_color = drawing.get("color")
                stroke_width = drawing.get("width", 0)
                fill_opacity = drawing.get("fill_opacity")
                if fill_opacity is None:
                    fill_opacity = 1.0
                
                circular_shapes.append({
                    'index': idx,
                    'type': shape_type,
                    'rect': (rect.x0, rect.y0, rect.x1, rect.y1),
                    'width': width,
                    'height': height,
                    'aspect_ratio': aspect_ratio,
                    'fill_color': fill_color,
                    'stroke_color': stroke_color,
                    'stroke_width': stroke_width if stroke_width is not None else 0,
                    'fill_opacity': fill_opacity
                })
    
    print("形状类型统计:")
    for shape_type, count in sorted(shape_types.items()):
        print(f"  {shape_type}: {count}")
    
    print(f"\n找到 {len(circular_shapes)} 个近似圆形的形状:")
    for shape in circular_shapes:
        print(f"\n  形状 #{shape['index']}:")
        print(f"    类型: {shape['type']}")
        print(f"    位置: ({shape['rect'][0]:.1f}, {shape['rect'][1]:.1f}) -> ({shape['rect'][2]:.1f}, {shape['rect'][3]:.1f})")
        print(f"    尺寸: {shape['width']:.1f} x {shape['height']:.1f}")
        print(f"    宽高比: {shape['aspect_ratio']:.2f}")
        print(f"    填充色: {shape['fill_color']}")
        print(f"    描边色: {shape['stroke_color']}")
        print(f"    描边宽度: {shape['stroke_width']}")
        print(f"    填充透明度: {shape['fill_opacity']:.3f}")
    
    # 检测潜在的圆环对
    print(f"\n{'='*80}")
    print("检测潜在的圆环对:")
    print(f"{'='*80}")
    
    for i, shape1 in enumerate(circular_shapes):
        for j, shape2 in enumerate(circular_shapes):
            if i >= j:
                continue
            
            # 检查中心点是否接近（同心）
            center1_x = (shape1['rect'][0] + shape1['rect'][2]) / 2
            center1_y = (shape1['rect'][1] + shape1['rect'][3]) / 2
            center2_x = (shape2['rect'][0] + shape2['rect'][2]) / 2
            center2_y = (shape2['rect'][1] + shape2['rect'][3]) / 2
            
            distance = ((center1_x - center2_x)**2 + (center1_y - center2_y)**2)**0.5
            
            if distance < 20:  # 中心点距离小于20点
                # 确定内外圈
                size1 = max(shape1['width'], shape1['height'])
                size2 = max(shape2['width'], shape2['height'])
                
                if size1 > size2:
                    outer = shape1
                    inner = shape2
                else:
                    outer = shape2
                    inner = shape1
                
                print(f"\n  潜在圆环: 形状 #{outer['index']} (外) + 形状 #{inner['index']} (内)")
                print(f"    中心距离: {distance:.1f}")
                print(f"    外圈尺寸: {max(outer['width'], outer['height']):.1f}")
                print(f"    内圈尺寸: {max(inner['width'], inner['height']):.1f}")
                print(f"    外圈填充: {outer['fill_color']} (透明度: {outer['fill_opacity']:.3f})")
                print(f"    外圈描边: {outer['stroke_color']} (宽度: {outer['stroke_width']})")
                print(f"    内圈填充: {inner['fill_color']} (透明度: {inner['fill_opacity']:.3f})")
                print(f"    内圈描边: {inner['stroke_color']} (宽度: {inner['stroke_width']})")
    
    doc.close()

def main():
    pdf_path = "tests/glm-4.6.pdf"
    
    # 分析问题页面：第5-11页 (索引 4-10)
    problem_pages = [4, 5, 6, 7, 8, 10]  # 第5, 6, 7, 8, 9, 11页
    
    for page_num in problem_pages:
        analyze_page_shapes(pdf_path, page_num)

if __name__ == "__main__":
    main()
