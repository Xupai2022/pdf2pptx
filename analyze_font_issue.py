"""
深度分析PDF字体问题

这个脚本将帮助我们理解:
1. PDF中的字体实际信息（字体名称、flags、weight）
2. 为什么PPT显示不同
3. 如何正确映射字体并保留粗体效果
"""

import fitz  # PyMuPDF
import sys

def analyze_pdf_fonts(pdf_path):
    """深度分析PDF第一页的字体信息"""
    
    print("=" * 80)
    print("PDF字体深度分析")
    print("=" * 80)
    
    doc = fitz.open(pdf_path)
    page = doc[0]  # 第一页
    
    # 获取文本字典信息
    text_dict = page.get_text("dict")
    
    print("\n1. 检测到的所有文本和字体信息:")
    print("-" * 80)
    
    font_usage = {}
    
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # 文本块
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    font_name = span.get("font", "")
                    font_size = span.get("size", 0)
                    flags = span.get("flags", 0)
                    color = span.get("color", 0)
                    
                    # 解析flags
                    is_superscript = bool(flags & 2**0)
                    is_italic = bool(flags & 2**1)
                    is_serifed = bool(flags & 2**2)
                    is_monospaced = bool(flags & 2**3)
                    is_bold = bool(flags & 2**4)
                    
                    print(f"\n文本: '{text}'")
                    print(f"  字体名称: {font_name}")
                    print(f"  字体大小: {font_size:.2f}")
                    print(f"  Flags值: {flags} (二进制: {bin(flags)})")
                    print(f"    - 粗体(Bold): {is_bold} (bit 4)")
                    print(f"    - 斜体(Italic): {is_italic} (bit 1)")
                    print(f"    - Superscript: {is_superscript} (bit 0)")
                    print(f"    - Serifed: {is_serifed} (bit 2)")
                    print(f"    - Monospaced: {is_monospaced} (bit 3)")
                    print(f"  颜色: {color}")
                    
                    # 统计字体使用情况
                    if font_name not in font_usage:
                        font_usage[font_name] = []
                    font_usage[font_name].append({
                        'text': text,
                        'is_bold': is_bold,
                        'flags': flags
                    })
    
    print("\n" + "=" * 80)
    print("2. 字体使用统计:")
    print("-" * 80)
    
    for font_name, usages in font_usage.items():
        bold_count = sum(1 for u in usages if u['is_bold'])
        print(f"\n字体: {font_name}")
        print(f"  使用次数: {len(usages)}")
        print(f"  粗体文字数量: {bold_count}")
        print(f"  普通文字数量: {len(usages) - bold_count}")
        
        # 显示前3个示例
        print(f"  示例文字:")
        for i, usage in enumerate(usages[:3]):
            bold_str = " [粗体]" if usage['is_bold'] else ""
            print(f"    {i+1}. '{usage['text']}'{bold_str} (flags={usage['flags']})")
    
    print("\n" + "=" * 80)
    print("3. 字体嵌入信息:")
    print("-" * 80)
    
    # 获取PDF中的字体列表
    font_list = []
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref)
            if '/BaseFont' in obj:
                # 提取字体信息
                import re
                base_font_match = re.search(r'/BaseFont\s*/(\S+)', obj)
                if base_font_match:
                    base_font = base_font_match.group(1)
                    font_list.append({
                        'xref': xref,
                        'base_font': base_font,
                        'obj': obj
                    })
        except:
            pass
    
    print(f"\n找到 {len(font_list)} 个字体对象:")
    for i, font_info in enumerate(font_list, 1):
        print(f"\n{i}. xref={font_info['xref']}")
        print(f"   BaseFont: {font_info['base_font']}")
        
        # 检查是否包含字体描述符
        if '/FontDescriptor' in font_info['obj']:
            print(f"   包含FontDescriptor")
            
            # 尝试提取字体权重
            if '/FontWeight' in font_info['obj']:
                weight_match = re.search(r'/FontWeight\s+(\d+)', font_info['obj'])
                if weight_match:
                    weight = int(weight_match.group(1))
                    print(f"   FontWeight: {weight}")
                    if weight >= 700:
                        print(f"   -> 这是粗体字体 (weight >= 700)")
            
            # 检查字体名称
            if 'Bold' in font_info['base_font']:
                print(f"   -> 字体名称包含'Bold'，这是粗体字体")
    
    print("\n" + "=" * 80)
    print("4. 问题分析:")
    print("-" * 80)
    
    print("""
根据分析，字体渲染问题可能源于以下原因之一：

1. 字体名称映射问题:
   - PDF使用: MicrosoftYaHei-Bold (包含-Bold后缀)
   - 当前映射到: 微软雅黑 (没有明确的粗体变体)
   - 正确方式: 应该映射到 "Microsoft YaHei UI Bold" 或保留Bold属性

2. 字体Flags处理:
   - PDF中的flags标记了文字是否为粗体(bit 4)
   - 我们需要检查是否正确提取和应用了这个flags

3. PPT字体选择逻辑:
   - PowerPoint中"微软雅黑"和"Microsoft YaHei UI"是不同的字体
   - Microsoft YaHei UI 包含更多的粗细变体
   - 可能需要明确指定字体变体名称

4. 字体合成 vs 真实粗体:
   - "微软雅黑"可能只有常规weight，通过算法加粗显示（合成粗体）
   - "Microsoft YaHei UI"有真实的Bold变体字体文件
   - 真实粗体字体和合成粗体在视觉上有明显差异

建议的解决方案:
=================
1. 字体名称映射改进:
   - MicrosoftYaHei-Bold -> "Microsoft YaHei UI" (不是"微软雅黑")
   - 同时保留is_bold标记
   
2. Bold属性强制应用:
   - 当检测到-Bold后缀或flags bit 4时，强制设置font.bold = True
   
3. 直接使用Microsoft YaHei UI字体族:
   - 该字体族在Windows中有完整的粗细变体
   - Regular, Bold, Light等变体都是真实字体文件
   
4. 可能需要在PowerPoint中通过XML直接指定字体的typeface:
   - 不只设置font.name，还要设置font family和font weight
    """)
    
    doc.close()

if __name__ == "__main__":
    # 查找PDF文件
    import os
    import glob
    
    # 查找安全运营月报.pdf
    pdf_patterns = [
        "安全运营月报.pdf",
        "**/安全运营月报.pdf",
        "/home/user/webapp/安全运营月报.pdf"
    ]
    
    pdf_path = None
    for pattern in pdf_patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            pdf_path = matches[0]
            break
    
    if not pdf_path:
        print("错误: 找不到'安全运营月报.pdf'文件")
        print("请将PDF文件放在当前目录下")
        sys.exit(1)
    
    print(f"分析PDF文件: {pdf_path}\n")
    analyze_pdf_fonts(pdf_path)
