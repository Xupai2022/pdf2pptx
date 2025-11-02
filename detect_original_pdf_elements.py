#!/usr/bin/env python3
"""
检测原始PDF的所有元素，特别是第4、11、15页
"""
import fitz  # PyMuPDF
import json
from pathlib import Path


def analyze_page_elements(pdf_path, page_num):
    """分析指定页面的所有元素"""
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]  # 页码从0开始
    
    print(f"\n{'='*80}")
    print(f"第 {page_num} 页分析:")
    print(f"{'='*80}")
    
    # 1. 分析文本及其旋转角度
    print("\n1. 文本元素:")
    blocks = page.get_text("dict")["blocks"]
    text_items = []
    for block in blocks:
        if block.get("type") == 0:  # 文本块
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        # 获取变换矩阵
                        bbox = span.get("bbox")
                        origin = span.get("origin")
                        
                        # 获取文本方向信息
                        # span包含字体大小、颜色等信息
                        text_info = {
                            "text": text,
                            "bbox": bbox,
                            "origin": origin,
                            "font": span.get("font"),
                            "size": span.get("size"),
                            "flags": span.get("flags"),
                            "color": span.get("color")
                        }
                        text_items.append(text_info)
                        
                        # 特殊关注某些文本
                        if "10.64.5.37" in text or "10.74.145.44" in text or "未知业务" in text:
                            print(f"  ⚠️ 关键文本: {text}")
                            print(f"     bbox: {bbox}")
                            print(f"     origin: {origin}")
                            print(f"     font: {span.get('font')}")
                            print(f"     size: {span.get('size')}")
    
    print(f"\n  共找到 {len(text_items)} 个文本元素")
    
    # 2. 分析路径/绘图元素（包括三角形、线条等）
    print("\n2. 绘图元素 (paths):")
    paths = page.get_drawings()
    print(f"  共找到 {len(paths)} 个绘图元素")
    
    # 分析特殊形状
    triangles = []
    horizontal_lines = []
    for i, path in enumerate(paths):
        items = path.get("items", [])
        rect = path.get("rect")
        color = path.get("color")
        fill = path.get("fill")
        
        # 检测三角形（3条边）
        if len(items) == 4 and items[0][0] == "l":  # 线条
            # 可能是三角形
            is_triangle = True
            for item in items:
                if item[0] not in ["l", "re", "c"]:
                    is_triangle = False
                    break
            
            if is_triangle:
                triangles.append({
                    "index": i,
                    "rect": rect,
                    "items": items,
                    "color": color,
                    "fill": fill
                })
        
        # 检测横线（水平线）
        for item in items:
            if item[0] == "l":  # 线条
                p1 = item[1]
                p2 = item[2]
                # 检测是否为水平线（y坐标相同）
                if abs(p1.y - p2.y) < 1:  # 容差1个像素
                    horizontal_lines.append({
                        "index": i,
                        "p1": (p1.x, p1.y),
                        "p2": (p2.x, p2.y),
                        "color": color,
                        "width": path.get("width")
                    })
    
    if triangles:
        print(f"  找到 {len(triangles)} 个可能的三角形:")
        for tri in triangles:
            print(f"    - 索引 {tri['index']}: rect={tri['rect']}, 颜色={tri['color']}")
            print(f"      items: {tri['items'][:2]}...")  # 只打印前2个
    
    if horizontal_lines:
        print(f"  找到 {len(horizontal_lines)} 条横线:")
        for line in horizontal_lines[:5]:  # 只打印前5条
            print(f"    - 索引 {line['index']}: {line['p1']} -> {line['p2']}, 颜色={line['color']}")
    
    # 3. 分析图片
    print("\n3. 图片元素:")
    images = page.get_images(full=True)
    print(f"  共找到 {len(images)} 个图片")
    for img in images:
        xref = img[0]
        try:
            bbox = page.get_image_bbox(img)
            print(f"    - xref: {xref}, bbox: {bbox}")
        except:
            print(f"    - xref: {xref}")
    
    # 4. 获取原始文本流（包含旋转信息）
    print("\n4. 原始文本流分析:")
    text_dict = page.get_text("rawdict")
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # 文本块
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    # 关注特定文本的矩阵信息
                    if "10.64.5.37" in text:
                        print(f"  找到 '10.64.5.37':")
                        print(f"    text: {text}")
                        print(f"    bbox: {span.get('bbox')}")
                        print(f"    origin: {span.get('origin')}")
                        print(f"    ascender: {span.get('ascender')}")
                        print(f"    descender: {span.get('descender')}")
    
    # 5. 分析文本方向（使用TextPage）
    print("\n5. 文本方向分析:")
    tp = page.get_textpage()
    # 获取所有字符及其方向
    words = page.get_text("words")  # 获取所有单词
    for word in words:
        text = word[4]
        if "10.64.5.37" in text or "10.74.145.44" in text:
            x0, y0, x1, y1 = word[:4]
            print(f"  文本: {text}")
            print(f"    位置: ({x0:.2f}, {y0:.2f}) -> ({x1:.2f}, {y1:.2f})")
            print(f"    宽度: {x1-x0:.2f}, 高度: {y1-y0:.2f}")
            # 如果宽度小于高度，说明是旋转的
            if (x1 - x0) < (y1 - y0):
                print(f"    ⚠️ 可能是旋转文本（宽度 < 高度）")
    
    doc.close()
    return {
        "text_items": len(text_items),
        "paths": len(paths),
        "triangles": len(triangles),
        "horizontal_lines": len(horizontal_lines),
        "images": len(images)
    }


def main():
    pdf_path = Path("tests/season_report_del.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF文件不存在: {pdf_path}")
        return
    
    print(f"📄 分析PDF: {pdf_path}")
    
    # 分析关键页面
    pages_to_analyze = [4, 11, 15]
    
    results = {}
    for page_num in pages_to_analyze:
        results[f"page_{page_num}"] = analyze_page_elements(pdf_path, page_num)
    
    # 打印总结
    print(f"\n{'='*80}")
    print("总结:")
    print(f"{'='*80}")
    for page, data in results.items():
        print(f"{page}: {data}")


if __name__ == "__main__":
    main()
