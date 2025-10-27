#!/usr/bin/env python3
"""
分析PDF文件中的颜色和透明度信息
"""
import fitz  # PyMuPDF
import re
import sys
from collections import defaultdict

def analyze_pdf_colors(pdf_path):
    """分析PDF中的颜色和透明度信息"""
    doc = fitz.open(pdf_path)
    print(f"PDF: {pdf_path}")
    print(f"Pages: {len(doc)}")
    print("=" * 80)
    
    for page_num in range(min(3, len(doc))):  # 只分析前3页
        page = doc[page_num]
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1}")
        print(f"{'='*80}")
        
        # 提取ExtGState透明度信息
        print("\n[ExtGState Opacity Information]")
        opacity_map = extract_opacity_map(doc, page)
        if opacity_map:
            for gs_name, opacity in opacity_map.items():
                print(f"  /{gs_name} -> opacity: {opacity}")
        else:
            print("  No ExtGState opacity found")
        
        # 提取绘图操作
        print("\n[Drawing Operations]")
        drawings = page.get_drawings()
        print(f"  Total drawings: {len(drawings)}")
        
        # 按颜色统计
        color_stats = defaultdict(int)
        opacity_stats = defaultdict(list)
        
        # 解析内容流以获取透明度序列
        gs_opacity_sequence = parse_content_stream_opacity(doc, page, opacity_map)
        
        for idx, drawing in enumerate(drawings[:20]):  # 只显示前20个
            rect = drawing.get("rect")
            fill_color = drawing.get("fill", None)
            stroke_color = drawing.get("color", None)
            
            # 获取该绘图的透明度
            opacity = gs_opacity_sequence[idx] if idx < len(gs_opacity_sequence) else 1.0
            
            if fill_color:
                color_hex = rgb_to_hex(fill_color)
                color_stats[color_hex] += 1
                opacity_stats[color_hex].append(opacity)
                
                print(f"  Drawing {idx + 1}:")
                print(f"    Type: {drawing.get('type', 'unknown')}")
                print(f"    Position: ({rect.x0:.1f}, {rect.y0:.1f}) -> ({rect.x1:.1f}, {rect.y1:.1f})")
                print(f"    Size: {rect.width:.1f} x {rect.height:.1f}")
                print(f"    Fill Color: {color_hex} (RGB: {fill_color})")
                print(f"    Opacity: {opacity}")
                if stroke_color:
                    print(f"    Stroke Color: {rgb_to_hex(stroke_color)}")
        
        # 颜色统计
        print(f"\n[Color Statistics (first 20 drawings)]")
        for color_hex, count in sorted(color_stats.items()):
            opacities = opacity_stats[color_hex]
            unique_opacities = sorted(set(opacities))
            print(f"  {color_hex}: {count} shapes, opacities: {unique_opacities}")
    
    doc.close()

def extract_opacity_map(doc, page):
    """提取页面的ExtGState透明度映射"""
    opacity_map = {}
    
    try:
        page_dict = doc.xref_object(page.xref, compressed=False)
        
        # 查找ExtGState资源
        extgstate_pattern = r'/ExtGState\s*<<([^>]+)>>'
        match = re.search(extgstate_pattern, page_dict, re.DOTALL)
        
        if match:
            extgstate_content = match.group(1)
            gs_refs = re.findall(r'/([A-Za-z]+\d*)\s+(\d+)\s+\d+\s+R', extgstate_content)
            
            for gs_name, xref in gs_refs:
                try:
                    gs_obj = doc.xref_object(int(xref), compressed=False)
                    ca_match = re.search(r'/ca\s+([\d.]+)', gs_obj)
                    if ca_match:
                        opacity = float(ca_match.group(1))
                        opacity_map[gs_name] = opacity
                except Exception as e:
                    pass
    except Exception as e:
        pass
    
    return opacity_map

def parse_content_stream_opacity(doc, page, opacity_map):
    """解析内容流以获取每个绘图操作的透明度"""
    opacity_sequence = []
    current_opacity = 1.0
    
    try:
        xref = page.get_contents()[0]
        content_stream = doc.xref_stream(xref).decode('latin-1')
        tokens = content_stream.split()
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # 图形状态变化: /Name gs
            if token.startswith('/') and i + 1 < len(tokens) and tokens[i + 1] == 'gs':
                gs_match = re.match(r'/([A-Za-z]+\d*)', token)
                if gs_match:
                    gs_name = gs_match.group(1)
                    current_opacity = opacity_map.get(gs_name, 1.0)
                i += 2
                continue
            
            # 填充操作: f 或 f*
            if token in ['f', 'f*']:
                opacity_sequence.append(current_opacity)
            
            i += 1
    except Exception as e:
        pass
    
    return opacity_sequence

def rgb_to_hex(color):
    """将RGB颜色转换为十六进制"""
    if color is None:
        return "#000000"
    
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
        return f"#{r:02X}{g:02X}{b:02X}"
    
    return "#000000"

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "tests/glm-4.6.pdf"
    analyze_pdf_colors(pdf_path)
