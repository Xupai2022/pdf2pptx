#!/usr/bin/env python3
"""
分析第15页的括号位置问题
"""
import fitz
import math


def main():
    pdf_path = "tests/season_report_del.pdf"
    doc = fitz.open(pdf_path)
    page = doc[14]  # 第15页，索引14
    
    print("="*80)
    print("第15页 - 括号位置分析")
    print("="*80)
    
    # 获取文本
    text_dict = page.get_text("dict")
    
    # 查找"10.74.145.44 （未知业务）"相关的文本
    for block_idx, block in enumerate(text_dict.get("blocks", [])):
        if block.get("type") == 0:  # 文本块
            for line_idx, line in enumerate(block.get("lines", [])):
                line_dir = line.get("dir", (1.0, 0.0))
                dx, dy = line_dir
                rotation_angle = math.degrees(math.atan2(dy, dx))
                
                # 归一化角度
                while rotation_angle > 180:
                    rotation_angle -= 360
                while rotation_angle < -180:
                    rotation_angle += 360
                
                for span_idx, span in enumerate(line.get("spans", [])):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    
                    # 查找包含"10.74.145.44"或"未知业务"或括号的文本
                    if "10.74.145.44" in text or "未知业务" in text or "（" in text or "(" in text or "）" in text or ")" in text:
                        print(f"\n🔍 文本: '{text}'")
                        print(f"   bbox: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})")
                        print(f"   宽度: {bbox[2] - bbox[0]:.2f}")
                        print(f"   高度: {bbox[3] - bbox[1]:.2f}")
                        print(f"   旋转角度: {rotation_angle:.2f}°")
                        print(f"   dir: ({dx:.6f}, {dy:.6f})")
                        print(f"   字体: {span.get('font')}")
                        print(f"   字号: {span.get('size')}")
                        
                        # 检查是否是旋转文本
                        if abs(rotation_angle) > 1:
                            print(f"   ⚠️ 这是旋转文本")
                            
                        # 检查是否包含中文和英文混合
                        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in text)
                        has_english = any('a' <= c.lower() <= 'z' for c in text)
                        has_number = any('0' <= c <= '9' for c in text)
                        has_bracket = '(' in text or '（' in text or ')' in text or '）' in text
                        
                        if has_bracket:
                            print(f"   ⚠️ 包含括号")
                            print(f"   - 中文字符: {has_chinese}")
                            print(f"   - 英文字符: {has_english}")
                            print(f"   - 数字字符: {has_number}")
                            
                            # 分析括号类型
                            if '（' in text or '）' in text:
                                print(f"   - 使用全角括号（中文括号）")
                            if '(' in text or ')' in text:
                                print(f"   - 使用半角括号（英文括号）")
    
    # 获取words级别的文本，看看是否文本被分割了
    print(f"\n{'='*80}")
    print("Words级别分析（检查文本是否被分割）")
    print(f"{'='*80}")
    
    words = page.get_text("words")
    for word in words:
        text = word[4]
        if "10.74.145.44" in text or "未知业务" in text or ("（" in text or "(" in text):
            x0, y0, x1, y1 = word[:4]
            print(f"\nWord: '{text}'")
            print(f"  位置: ({x0:.2f}, {y0:.2f}) -> ({x1:.2f}, {y1:.2f})")
            print(f"  宽度: {x1-x0:.2f}, 高度: {y1-y0:.2f}")
    
    doc.close()


if __name__ == "__main__":
    main()
